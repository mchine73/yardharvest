"""The autonomous BDR daily cycle — selection, budget, batches, breakers, digest.

Split from ``autonomy.py`` (execution primitives) only for size; the public
names are re-exported there (``autonomy.run_daily_cycle`` etc.). Nothing here
touches ``request``; the caller (cron tick / CLI / a run_async thread from the
console) owns the process lifetime. Every send commits on its own, so a crash
mid-cycle loses nothing already done, and the atomic day-claim guarantees a
re-run can't double-send.
"""
import json
import logging
import os
import re
from datetime import timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_

from app import db
from app.crm import autonomy as A
from app.crm.models import (AgentSettings, Contact, CrmAgentAction, CrmAgentRun,
                            CrmEmailEvent, CrmInboundReply, CrmUser, Note, _utcnow)

log = logging.getLogger(__name__)

CYCLE_LOCK_MINUTES = 15          # lease on a running cycle (guards force/manual overlap)
DRAFT_CHUNK = 10                 # leads per draft_followups call (bounded output time)
COLD_POOL = 40                   # cold leads shown to the ranker per cycle
RECENT_REPLY_DAYS = 7            # never auto-touch someone who wrote back this recently


# ---------------------------------------------------------------------------
# Settings / clock / gates
# ---------------------------------------------------------------------------
def get_settings():
    return AgentSettings.get()


def env_autonomy_off():
    """Emergency stop from the environment: CRM_AGENT_AUTONOMY=off (or 0/false)
    freezes the cycle regardless of the DB switch — no code deploy needed."""
    v = (os.environ.get('CRM_AGENT_AUTONOMY') or '').strip().lower()
    return v in ('off', '0', 'false', 'no')


def _tz(settings):
    try:
        return ZoneInfo(settings.timezone or 'America/Chicago')
    except Exception:
        return ZoneInfo('America/Chicago')


def local_now(settings, now=None):
    """Aware local datetime in the operator's timezone. ``now`` is naive UTC
    (the convention across the CRM models) or None for the real clock."""
    base = (now or _utcnow()).replace(tzinfo=timezone.utc)
    return base.astimezone(_tz(settings))


def local_midnight_utc(now_local):
    """Naive-UTC datetime of local midnight — for 'sends today' counting."""
    m = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    return m.astimezone(timezone.utc).replace(tzinfo=None)


def is_send_window(settings, now_local):
    if settings.weekdays_only and now_local.weekday() >= 5:
        return False
    return now_local.hour >= int(settings.send_hour_local or 9)


def sends_today(settings, now_local):
    """Auto-executed follow-up sends since local midnight — counted from rows,
    never a counter, so a crashed cycle can't lose or inflate the budget."""
    since = local_midnight_utc(now_local)
    return (CrmAgentAction.query
            .filter(CrmAgentAction.auto_executed.is_(True),
                    CrmAgentAction.action_type == 'follow_up_email',
                    CrmAgentAction.status == 'executed',
                    CrmAgentAction.reviewed_at >= since,
                    ~CrmAgentAction.result.like('Skipped%'))
            .count())


def hard_bounces_24h(now=None):
    since = (now or _utcnow()) - timedelta(hours=24)
    return (CrmEmailEvent.query
            .filter(CrmEmailEvent.event_type.in_(('hard', 'complaint')),
                    CrmEmailEvent.created_at >= since).count())


def imap_configured():
    from flask import current_app
    cfg = current_app.config
    return bool((os.environ.get('CRM_IMAP_PASSWORD') or cfg.get('CRM_IMAP_PASSWORD'))
                and (cfg.get('CRM_IMAP_USER') or cfg.get('CRM_FROM_EMAIL')))


def mailing_address_set():
    from flask import current_app
    return bool(os.environ.get('CRM_MAILING_ADDRESS')
                or current_app.config.get('CRM_MAILING_ADDRESS'))


def ai_spend_today(settings, now_local):
    """(spent, budget) in dollars for the local day.

    Every model call is already priced into CrmAgentRun.cost_usd, so the stop
    reads the ledger rather than a counter that a crashed run could leave
    wrong. Matters most now that enrichment and scouting can fire unattended:
    a stuck loop that quietly spends all night is the failure mode worth
    engineering against.
    """
    budget = float(settings.daily_ai_budget_usd or 0)
    if budget <= 0:
        return 0.0, 0.0
    start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    start_utc = start_local.astimezone(timezone.utc).replace(tzinfo=None)
    total = (db.session.query(func.coalesce(func.sum(CrmAgentRun.cost_usd), 0.0))
             .filter(CrmAgentRun.created_at >= start_utc).scalar() or 0.0)
    return float(total), budget


def cycle_gates(settings, now_local, *, force=False):
    """Human-readable reasons the cycle will NOT send right now (empty = go).
    Shown on the console so the operator can see why nothing happened."""
    from app.crm import agent_service
    gates = []
    if env_autonomy_off():
        gates.append('Emergency stop set in the environment (CRM_AGENT_AUTONOMY=off).')
    if not settings.autonomy_enabled:
        gates.append('Autonomy is switched off.')
    if settings.paused_reason:
        gates.append(f'Paused: {settings.paused_reason}')
    if not force:
        if settings.weekdays_only and now_local.weekday() >= 5:
            gates.append('Weekend — sends are weekdays only.')
        elif now_local.hour < int(settings.send_hour_local or 9):
            gates.append(f'Waiting for the send hour ({int(settings.send_hour_local or 9):02d}:00 '
                         f'{settings.timezone}).')
    if not agent_service.is_configured():
        gates.append('AI is not configured (ANTHROPIC_API_KEY).')
    spent, budget = ai_spend_today(settings, now_local)
    if budget and spent >= budget:
        gates.append(f'Daily AI budget reached (${spent:.2f} of ${budget:.2f}) — '
                     f'resets at local midnight.')
    if not A.email_ready():
        gates.append('Email is not configured (ZEPTOMAIL_TOKEN).')
    if not mailing_address_set():
        gates.append('CRM_MAILING_ADDRESS is not set (CAN-SPAM postal address).')
    if settings.require_reply_capture:
        if not imap_configured():
            gates.append('Reply capture is not configured (CRM_IMAP_PASSWORD) — '
                         'required so nobody who replied gets another follow-up.')
        elif not settings.last_reply_poll_ok_at or (
                _utcnow() - settings.last_reply_poll_ok_at) > timedelta(hours=24):
            gates.append('Reply capture has not succeeded in the last 24h — '
                         f'{settings.imap_last_error or "no successful poll yet"}.')
    return gates


# ---------------------------------------------------------------------------
# Lead selection + touch-aware context
# ---------------------------------------------------------------------------
_SENT_NOTE_RE = re.compile(r'^\[Email (?:sent|logged) to [^\]]*\]\s*(.*)$')


def _prior_emails(contact, limit=3):
    """Subjects + openings of emails we already sent this contact, from the
    timeline Notes the send path writes ('[Email sent to …] subject\\n\\nbody').
    Best-effort — degrades to [] if the note format ever changes."""
    out = []
    notes = (Note.query.filter_by(contact_id=contact.id)
             .filter(Note.content.like('[Email %'))
             .order_by(Note.created_at.desc()).limit(limit).all())
    for n in notes:
        first, _, rest = (n.content or '').partition('\n')
        m = _SENT_NOTE_RE.match(first.strip())
        if not m:
            continue
        body_txt = re.sub(r'<[^>]+>', ' ', rest or '')
        body_txt = re.sub(r'\s+', ' ', body_txt).strip()
        out.append({'date': n.created_at.strftime('%b %d') if n.created_at else '',
                    'subject': m.group(1).strip()[:120],
                    'snippet': body_txt[:160]})
    return out


def _followup_context(contact, *, angle=None):
    """The fact-only lead context PLUS the touch-aware fields so touches 1/2/3
    aren't drafted from identical scaffolding."""
    from app.crm.views import _lead_context
    ctx = _lead_context(contact)
    touch = int(contact.followup_count or 0) + 1
    ctx.update({
        'touch_number': touch,
        'max_touches': A.MAX_NO_REPLY_TOUCHES,
        'is_final': touch >= A.MAX_NO_REPLY_TOUCHES,
        'angle': angle or contact.next_action_note or None,
        'prior_emails': _prior_emails(contact),
    })
    return ctx


def _pending_contact_ids():
    return {a.contact_id for a in
            db.session.query(CrmAgentAction.contact_id)
            .filter(CrmAgentAction.status.in_(('pending', 'executing')),
                    CrmAgentAction.contact_id.isnot(None)).all()}


def _recently_replied_ids(days=RECENT_REPLY_DAYS):
    since = _utcnow() - timedelta(days=days)
    return {r.contact_id for r in
            db.session.query(CrmInboundReply.contact_id)
            .filter(CrmInboundReply.created_at >= since,
                    CrmInboundReply.contact_id.isnot(None)).all()}


def _eligible_due_leads(settings, limit):
    """Due leads the cycle may email WITHOUT a human: New/Working only (an
    Engaged lead replied or booked — a person owns that conversation), with
    an address, not opted out / suppressed, under the touch cap, no proposal
    already pending, and no reply captured this week."""
    from app.crm.views import _due_leads
    from app.email_service import is_email_suppressed
    if limit <= 0:
        return []
    pending = _pending_contact_ids()
    replied = _recently_replied_ids()
    # One organization gets at most one email per cycle: two notes landing at
    # the same garden on the same morning reads as a blast, not a person.
    seen_orgs = _orgs_emailed_today()
    out = []
    for c in _due_leads(limit=max(120, limit * 6)):
        if (c.lead_status or 'New') not in ('New', 'Working'):
            continue
        if getattr(c, 'on_platform', False):
            continue          # they already have a garden — a cold intro insults them
        if not c.email or c.email_opt_out or c.id in pending or c.id in replied:
            continue
        if int(c.followup_count or 0) >= A.MAX_NO_REPLY_TOUCHES:
            continue
        if c.company_id and c.company_id in seen_orgs:
            continue
        if is_email_suppressed(c.email):
            continue
        out.append(c)
        if c.company_id:
            seen_orgs.add(c.company_id)
        if len(out) >= limit:
            break
    return out


def _orgs_emailed_today(now_local=None):
    """Company ids the agent already emailed since local midnight."""
    settings = get_settings()
    since = local_midnight_utc(now_local or local_now(settings))
    rows = (db.session.query(CrmAgentAction.company_id)
            .filter(CrmAgentAction.auto_executed.is_(True),
                    CrmAgentAction.status == 'executed',
                    CrmAgentAction.action_type == 'follow_up_email',
                    CrmAgentAction.reviewed_at >= since,
                    CrmAgentAction.company_id.isnot(None)).all())
    return {r.company_id for r in rows}


def _cold_pool(limit=COLD_POOL):
    """Never-contacted New leads with an address — the same pool the manual
    'Scout leads' button ranks. Excludes anything already proposed."""
    from app.email_service import is_email_suppressed
    pending = _pending_contact_ids()
    replied = _recently_replied_ids()
    seen_orgs = _orgs_emailed_today()
    # Ordered by the ICP score rather than by id, so the pool the cycle sees
    # is the best of everything we hold — not whichever rows were imported
    # first. The over-fetch leaves room for the suppression/dedupe filters
    # below without dropping back to arbitrary ordering.
    from app.crm import icp
    from app.crm.models import Company
    settings = get_settings()
    score = icp.score_expression(settings.operator_weight)
    cold = (Contact.query.outerjoin(Company, Contact.company_id == Company.id)
            .filter(Contact.lead_status == 'New',
                    Contact.last_contacted_at.is_(None),
                    Contact.email.isnot(None), Contact.email != '',
                    or_(Contact.platform_status.is_(None),
                        Contact.platform_status == 'none'))
            .order_by(score.desc(), Contact.id).limit(limit * 3).all())
    out = []
    for c in cold:
        if c.id in pending or c.id in replied or c.email_opt_out:
            continue
        if c.company_id and c.company_id in seen_orgs:
            continue          # one email per organization per day
        if is_email_suppressed(c.email):
            continue
        out.append(c)
        if c.company_id:
            seen_orgs.add(c.company_id)
        if len(out) >= limit:
            break
    return out


# ---------------------------------------------------------------------------
# Usage / cost bookkeeping across several model calls in one cycle
# ---------------------------------------------------------------------------
class _Usage:
    def __init__(self):
        self.by_model = {}

    def add(self, model, usage):
        if not usage:
            return
        m = self.by_model.setdefault(model or 'unknown',
                                     {'input_tokens': 0, 'output_tokens': 0, 'web_searches': 0})
        for k in m:
            m[k] += int(usage.get(k) or 0)

    def totals(self):
        from app.crm import agent_service
        tot = {'input_tokens': 0, 'output_tokens': 0, 'web_searches': 0, 'cost_usd': 0.0}
        for model, u in self.by_model.items():
            tot['input_tokens'] += u['input_tokens']
            tot['output_tokens'] += u['output_tokens']
            tot['web_searches'] += u['web_searches']
            tot['cost_usd'] += agent_service.estimate_cost(
                model, u['input_tokens'], u['output_tokens'], u['web_searches'])
        tot['cost_usd'] = round(tot['cost_usd'], 4)
        tot['model'] = ','.join(sorted(self.by_model))[:40] if self.by_model else None
        return tot


def _record_run(run_id, usage, *, error=None):
    run = db.session.get(CrmAgentRun, run_id) if run_id else None
    if not run:
        return
    t = usage.totals()
    run.model = t['model']
    run.input_tokens = t['input_tokens']
    run.output_tokens = t['output_tokens']
    run.web_searches = t['web_searches']
    run.cost_usd = t['cost_usd']
    if run.status == 'running':
        run.status = 'failed' if error else 'done'
        run.error = (str(error)[:500] if error else None)
        run.finished_at = _utcnow()
    db.session.commit()


# ---------------------------------------------------------------------------
# Breakers + operator notices
# ---------------------------------------------------------------------------
def _operator_email(settings):
    from flask import current_app
    return (settings.digest_email or current_app.config.get('CRM_FROM_EMAIL')
            or 'james@yardharvest.app')


def _notice(settings, subject, content_html):
    """Internal notice to the operator (digest / alerts) — platform mail, not
    outreach: no signature block, no CAN-SPAM footer, neutral shell."""
    from app.email_service import send_email, render_booking_email
    try:
        html = render_booking_email(content_html, owner_name='the YardHarvest CRM')
        return bool(send_email(_operator_email(settings), subject, html))
    except Exception:  # noqa: BLE001
        log.exception('Operator notice failed: %s', subject)
        return False


def trip_breaker(settings, reason):
    """Pause autonomy until an operator clears it, and say so loudly."""
    settings.paused_reason = (reason or 'Paused')[:300]
    settings.paused_at = _utcnow()
    db.session.commit()
    log.error('BDR autonomy PAUSED: %s', reason)
    _notice(settings, '⚠️ BDR agent paused itself',
            f'<p>The autonomous BDR agent stopped sending and needs you:</p>'
            f'<p><strong>{reason}</strong></p>'
            f'<p>Nothing else will go out until you press <em>Resume</em> in the '
            f'agent console.</p>')


# ---------------------------------------------------------------------------
# The batches
# ---------------------------------------------------------------------------
def _new_action(contact, d, *, action_type, payload, created_by_id):
    a = CrmAgentAction(
        action_type=action_type, status='pending',
        contact_id=contact.id, company_id=contact.company_id,
        title=(d.get('title') or f'Follow up with {contact.name}')[:200],
        rationale=d.get('rationale'),
        payload_json=json.dumps(payload), created_by_id=created_by_id)
    db.session.add(a)
    db.session.commit()
    return a


def _auto_headers():
    """List-Unsubscribe on automated one-to-one mail — cheap goodwill with
    Gmail/Yahoo bulk-sender heuristics at 15/day from one address."""
    try:
        from app.email_service import _list_unsubscribe_headers
        return _list_unsubscribe_headers()
    except Exception:  # noqa: BLE001
        return None


def _qa_draft(contact, draft, usage, summary, *, touch=None):
    """Quality gate between a draft and a real person.

    Deterministic lint first (free), then a second model re-reads it as a
    critic and either approves, returns a corrected version, or holds it.
    Returns (subject, body) to send, or None to HOLD — held drafts stay in
    the approval queue for a human instead of going out."""
    from app.crm import agent_service
    # Sentence-case the subject before anything judges it. The drafter already
    # does this, but a draft can also arrive from a stale queue row or a
    # different code path, and casing is far too mechanical a reason to hold
    # an otherwise good email.
    subject = agent_service.normalize_subject(draft.get('subject'))
    body = draft.get('body', '')
    personal = not agent_service.is_placeholder_name(contact.name)
    issues = agent_service.lint_email(subject, body, contact_name=contact.name,
                                      personal=personal)
    try:
        review, u = agent_service.review_email(
            subject, body, contact_name=contact.name, personal=personal,
            company=contact.company.name if contact.company else None,
            touch_number=touch, known_issues=issues)
        usage.add(agent_service.QA_MODEL, u)
    except agent_service.AgentError as e:
        # Reviewer unavailable: trust lint alone — clean drafts still go, a
        # flagged draft waits for a human rather than risking the send.
        log.warning('Pre-send review failed: %s', e)
        if issues:
            summary['held'].append({'contact': contact.name, 'why': '; '.join(issues[:3])})
            return None
        return subject, body

    if review['verdict'] == 'hold':
        summary['held'].append({'contact': contact.name,
                                'why': '; '.join((review.get('issues') or issues)[:3])
                                       or 'held by the pre-send review'})
        return None
    subject = agent_service.normalize_subject(review['subject'])
    body = review['body']
    if review['verdict'] == 'fixed':
        summary['fixed'].append({'contact': contact.name,
                                 'why': '; '.join((review.get('issues') or [])[:2])})
    # Re-lint the (possibly rewritten) copy — a fix must not introduce a
    # different problem, and this is the check that actually blocks a send.
    final = agent_service.lint_email(subject, body, contact_name=contact.name,
                                     personal=personal)
    if final:
        summary['held'].append({'contact': contact.name, 'why': '; '.join(final[:3])})
        return None
    return subject, body


def _auto_send_batch(leads, settings, summary, usage, budget, *, sender, actor_id):
    """Draft in chunks → quality-check → persist proposals → claim → execute.
    Returns the number of real sends. Stops at the budget or when the breaker
    trips. Drafts that fail the quality gate are left pending for a human."""
    from app.crm import agent_service
    if budget <= 0 or not leads:
        return 0
    sent = 0
    failures = 0
    leads = leads[:budget]
    headers = _auto_headers()
    for i in range(0, len(leads), DRAFT_CHUNK):
        chunk = leads[i:i + DRAFT_CHUNK]
        ctxs = [_followup_context(c) for c in chunk]
        try:
            drafts, u = agent_service.draft_followups(ctxs, sender_name=sender)
        except agent_service.AgentError as e:
            summary['errors'].append(f'Drafting failed: {e}')
            log.warning('Autonomous drafting failed: %s', e)
            continue
        usage.add(agent_service.EMAIL_MODEL, u)
        by_id = {c.id: c for c in chunk}
        touch_by_id = {ctx['lead_id']: ctx.get('touch_number') for ctx in ctxs}
        drafted_ids = set()
        for d in drafts:
            c = by_id.get(d.get('lead_id'))
            if not c:
                continue
            drafted_ids.add(c.id)
            checked = _qa_draft(c, d, usage, summary, touch=touch_by_id.get(c.id))
            if checked is None:
                # Held: keep the draft in the queue, flagged, for a human.
                _new_action(c, {**d, 'title': f'[Needs review] {d.get("title") or c.name}'[:200],
                                'rationale': (d.get('rationale') or '') +
                                             ' — held by the pre-send quality check.'},
                            action_type='follow_up_email',
                            payload={'subject': d.get('subject', ''), 'body': d.get('body', '')},
                            created_by_id=actor_id)
                continue
            d = {**d, 'subject': checked[0], 'body': checked[1]}
            a = _new_action(c, d, action_type='follow_up_email',
                            payload={'subject': d.get('subject', ''), 'body': d.get('body', '')},
                            created_by_id=actor_id)
            if not A.claim_action(a.id):
                continue
            res = A.execute_action(a, form=None, actor_id=actor_id, auto=True,
                                   extra_headers=headers)
            entry = {'contact': c.name, 'company': c.company.name if c.company else '',
                     'subject': res.detail.get('subject') or d.get('subject', ''),
                     'touch': int(c.followup_count or 0), 'status': res.status}
            if res.status == 'executed' and res.detail.get('sent'):
                sent += 1
                failures = 0
                summary['sent'].append(entry)
                if (c.lead_status or '') == 'Nurture':
                    summary['nurtured'].append(c.name)
            elif res.status == 'skipped':
                summary['skipped'].append({**entry, 'why': res.detail.get('skip')})
            elif res.status == 'executed':
                # 'Email logged' — mail unconfigured; the gate should have
                # stopped us. Count as a failure so it can't loop.
                failures += 1
                summary['failed'].append({**entry, 'why': 'email not configured'})
            else:
                failures += 1
                summary['failed'].append({**entry, 'why': res.message})
            if failures >= int(settings.max_consecutive_send_failures or 3):
                trip_breaker(settings, f'{failures} consecutive send failures '
                                       f'(last: {res.message})')
                summary['breaker'] = settings.paused_reason
                return sent
            if sent >= budget:
                return sent
        for c in chunk:
            if c.id not in drafted_ids:
                summary['skipped'].append({'contact': c.name, 'why': 'no draft returned'})
    return sent


def _promote_cold(settings, summary, usage, budget, *, actor_id):
    """Pick the best of the cold pool, promote as many as the budget allows
    (New → Working, owned by the operator), and return them so intros can be
    drafted.

    Ranking is a deterministic score (app.crm.icp), not a model call: the old
    Sonnet ranker saw only the first 40 leads by id, cost money on every cycle
    to answer a question with no judgement in it, and its prompt led with
    independents while the thesis says the payers are operators, nonprofits
    and city programs. The score reads the whole pool for nothing.
    """
    from app.crm import icp
    if budget <= 0:
        return []
    pool = _cold_pool()
    if not pool:
        return []
    picks = [{'lead_id': r['contact'].id,
              'title': (f"Prospect {r['contact'].company.name}"
                        if r['contact'].company else f"Prospect {r['contact'].name}"),
              'rationale': ('Best fit in the cold pool right now: '
                            + ('; '.join(r['why']) if r['why']
                               else 'nothing else in the pool scores higher')
                            + f" (score {r['score']})"),
              # The old ranker invented an angle per lead. The score's reasons
              # are the same thing grounded in facts we hold — "runs 4 sites"
              # is a better opening than a model's guess at one.
              'angle': '; '.join(r['why'])}
             for r in icp.rank(pool, settings.operator_weight, limit=min(budget, 8))]
    by_id = {c.id: c for c in pool}
    promoted = []
    for p in picks:
        c = by_id.get(p.get('lead_id'))
        if not c or len(promoted) >= budget:
            continue
        a = _new_action(c, {'title': p.get('title') or f'Prospect {c.company.name if c.company else c.name}',
                            'rationale': p.get('rationale')},
                        action_type='scout', payload={'angle': p.get('angle', '')},
                        created_by_id=actor_id)
        if not A.claim_action(a.id):
            continue
        res = A.execute_action(a, form=None, actor_id=actor_id, auto=True)
        if res.ok:
            db.session.refresh(c)
            promoted.append(c)
            summary['promoted'].append({'contact': c.name,
                                        'company': c.company.name if c.company else '',
                                        'angle': (p.get('angle') or '')[:120]})
    return promoted


# ---------------------------------------------------------------------------
# Digest
# ---------------------------------------------------------------------------
def _runway(settings):
    """How many more weekday cycles the current due+cold pool can feed at the
    daily cap — a nudge to click 'Find new leads' before the loop starves."""
    due = len(_eligible_due_leads(settings, 500))
    cold = len(_cold_pool(500))
    per_day = max(1, int(settings.daily_send_cap or 15))
    touches = due + cold * A.MAX_NO_REPLY_TOUCHES   # each cold lead ≈ up to 3 touches
    return {'due': due, 'cold': cold, 'days': touches // per_day}


SUPPLY_RUNWAY_DAYS = 5          # top up when the pool is under a working week
MAX_PENDING_NEW_LEADS = 20      # don't pile proposals nobody has approved


def _top_up_supply(settings, summary, usage, now_local):
    """Refill the cold pool without being asked, within the day's AI budget.

    Both halves stay honest about their risk. Enrichment is unattended: it
    only ever adds a contact whose address came off a page it can cite, and
    the outbound QA gate still stands between that address and an email.
    Web scouting is not: it invents nothing, but it decides an organization is
    worth pursuing, so results stay proposals for a human — the checkpoint is
    cheap because approving is one click and the alternative is a queue full
    of orgs nobody chose.
    """
    from app.crm.views import ENRICH_BATCH, _async_enrich, _enrichment_targets
    if not (settings.auto_enrich or settings.auto_new_leads):
        return
    runway = _runway(settings)
    if runway['days'] >= SUPPLY_RUNWAY_DAYS:
        return
    spent, budget = ai_spend_today(settings, now_local)
    if budget and spent >= budget:
        summary.setdefault('supply', []).append(
            f'Pool is thin ({runway["days"]}d) but the daily AI budget is spent.')
        return
    actor_id = _operator_id(settings)

    if settings.auto_enrich:
        targets = _enrichment_targets().limit(ENRICH_BATCH).all()
        if targets:
            try:
                u = _async_enrich([c.id for c in targets], actor_id)
                usage.add((u or {}).get('model'), u or {})
                summary.setdefault('supply', []).append(
                    f'Enriched {len(targets)} organizations (payer types first).')
            except Exception as e:  # noqa: BLE001
                log.exception('Unattended enrichment failed')
                summary['errors'].append(f'Enrichment failed: {e}')

    if settings.auto_new_leads:
        pending = (CrmAgentAction.query
                   .filter_by(status='pending', action_type='new_lead').count())
        if pending >= MAX_PENDING_NEW_LEADS:
            summary.setdefault('supply', []).append(
                f'{pending} new-lead proposals already waiting — not scouting more.')
            return
        from app.crm.models import Company
        from app.crm.views import _async_scout_web
        # Exclude what we already hold so the search spends its budget on
        # organizations that are actually new.
        exclude = [c.name for c in Company.query.with_entities(Company.name)
                   .order_by(Company.id.desc()).limit(200).all() if c.name]
        try:
            u = _async_scout_web('', exclude, actor_id)
            usage.add((u or {}).get('model'), u or {})
            summary.setdefault('supply', []).append(
                'Searched the web for new organizations — proposals are waiting for you.')
        except Exception as e:  # noqa: BLE001
            log.exception('Unattended scouting failed')
            summary['errors'].append(f'Web scouting failed: {e}')


def _esc(s):
    return str(s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def funnel_rates(days=30, now=None):
    """Reply rate by touch number and by organization type.

    The one number that tells you whether the message, the cadence and the
    targeting are working — and the CRM could not produce it, because it held
    each lead's status now and nothing about how it got there.

    Counts an outbound as answered when a human reply arrived within 14 days
    of it. Daemon bounces and out-of-office notices are excluded: they say
    something about the address, nothing about the message.
    """
    from app.crm.models import Company, CrmInboundReply

    stamp = now or _utcnow()
    since = stamp - timedelta(days=days)
    sends = (db.session.query(CrmAgentAction, Contact, Company)
             .join(Contact, CrmAgentAction.contact_id == Contact.id)
             .outerjoin(Company, Contact.company_id == Company.id)
             .filter(CrmAgentAction.status == 'executed',
                     CrmAgentAction.action_type == 'follow_up_email',
                     # reviewed_at is when the action ran — for an
                     # executed follow-up that is the send time.
                     CrmAgentAction.reviewed_at >= since)
             .all())
    if not sends:
        return {'days': days, 'sends': 0, 'by_touch': [], 'by_org': [], 'by_cta': []}

    contact_ids = {c.id for _a, c, _co in sends}
    replies = (CrmInboundReply.query
               .filter(CrmInboundReply.contact_id.in_(contact_ids),
                       CrmInboundReply.created_at >= since,
                       ~CrmInboundReply.classification.in_(
                           ('out_of_office', 'unmatched', 'not_outreach')))
               .all())
    replied_by_contact = {}
    for r in replies:
        prev = replied_by_contact.get(r.contact_id)
        if prev is None or r.created_at < prev:
            replied_by_contact[r.contact_id] = r.created_at

    def bucket(key_fn):
        rows = {}
        for action, contact, company in sends:
            key = key_fn(action, contact, company)
            slot = rows.setdefault(key, {'key': key, 'sent': 0, 'replied': 0})
            slot['sent'] += 1
            answered = replied_by_contact.get(contact.id)
            if answered and action.reviewed_at and                     timedelta(0) <= (answered - action.reviewed_at) <= timedelta(days=14):
                slot['replied'] += 1
        for slot in rows.values():
            slot['rate'] = (100.0 * slot['replied'] / slot['sent']) if slot['sent'] else 0.0
        return sorted(rows.values(), key=lambda r: str(r['key']))

    def touch_of(action, contact, _co):
        payload = action.payload or {}
        n = payload.get('touch_number')
        return f'touch {n}' if n else 'touch ?'

    return {
        'days': days,
        'sends': len(sends),
        'by_touch': bucket(touch_of),
        'by_org': bucket(lambda a, c, co: (co.org_type if co and co.org_type
                                           else 'untyped')),
        'by_cta': bucket(lambda a, c, co: a.cta_type or 'unrecorded'),
    }


def build_digest_html(summary, settings):
    """The morning email.

    Ordered by what it asks of the reader: what needs you now (with a link to
    the exact card), what is happening today, then yesterday's log. The old
    version led with counts and ended with one generic link, which meant every
    action still cost a hunt through the console.
    """
    from flask import current_app
    base = (current_app.config.get('SITE_URL') or 'https://www.yardharvest.app').rstrip('/')
    out = []
    p = out.append
    muted = "color:#6b7280;font-size:.9em"

    p(f"<h2 style='margin:0 0 6px'>BDR agent \u2014 {_esc(summary.get('date'))}</h2>")
    if summary.get('breaker'):
        p(f"<p style='color:#b42318'><strong>Paused itself:</strong> "
          f"{_esc(summary['breaker'])}</p>")

    # ---- 1. NEEDS YOU - each row links to the card that resolves it -------
    queue = _pending_for_you()
    if queue:
        p(f"<h3 style='margin:14px 0 4px'>Needs you ({len(queue)})</h3><ul style='margin:0'>")
        for a in queue[:12]:
            who = a.contact.name if a.contact else (a.company.name if a.company else '-')
            kind = ('reply' if a.action_type == 'reply_email'
                    else 'held' if (a.title or '').startswith('[Needs review]')
                    else (a.action_type or '').replace('_', ' '))
            p(f"<li><a href='{base}/crm/agent#action-{a.id}'><strong>{_esc(who)}</strong></a> "
              f"\u2014 {_esc(kind)}: {_esc((a.title or '')[:90])}</li>")
        p('</ul>')

    # ---- 2. TODAY --------------------------------------------------------
    meetings = _meetings_next_48h()
    if meetings:
        p("<h3 style='margin:14px 0 4px'>Meetings, next 48h</h3><ul style='margin:0'>")
        for b in meetings:
            link = f"{base}/crm/contacts/{b.crm_contact_id}" if b.crm_contact_id else None
            name = (f"<a href='{link}'>{_esc(b.invitee_name)}</a>" if link
                    else _esc(b.invitee_name))
            p(f"<li>{b.start_at:%a %H:%M} UTC \u2014 {name} "
              f"<span style='{muted}'>{_esc(b.invitee_email)}</span></li>")
        p('</ul>')

    human = _needs_human_leads()
    if human:
        p(f"<h3 style='margin:14px 0 4px'>Your leads, overdue ({len(human)})</h3>"
          f"<p style='{muted}'>Engaged and qualified leads \u2014 the agent never "
          f"emails these.</p><ul style='margin:0'>")
        for c in human[:12]:
            note = f" \u00b7 {_esc(c.next_action_note)}" if c.next_action_note else ''
            p(f"<li><a href='{base}/crm/contacts/{c.id}'>{_esc(c.name)}</a> "
              f"<span style='{muted}'>{_esc(c.lead_status)}{note}</span></li>")
        p('</ul>')

    plat = _platform_movements()
    if plat['converted'] or plat['trials_ending']:
        p("<h3 style='margin:14px 0 4px'>On the platform</h3><ul style='margin:0'>")
        for name in plat['converted']:
            p(f"<li><strong>{_esc(name)}</strong> went Pro this week</li>")
        for name, ends in plat['trials_ending']:
            p(f"<li>{_esc(name)} \u2014 trial ends {ends:%b %d}</li>")
        p('</ul>')
        if settings.last_match_total:
            p(f"<p style='{muted}'>{settings.last_match_matched or 0} of "
              f"{settings.last_match_total} subscriptions matched to a CRM contact "
              f"(matched on email, so this under-counts).</p>")

    # ---- 3. WHAT THE AGENT DID -------------------------------------------
    sent = summary.get('sent', [])
    replies = summary.get('replies', [])
    promoted = summary.get('promoted', [])
    # ---- WHAT IS WORKING -------------------------------------------------
    rates = summary.get('rates') or {}
    if rates.get('sends'):
        p(f"<h3 style='margin:14px 0 4px'>What is working "
          f"<span style='{muted}'>(last {rates['days']} days, "
          f"{rates['sends']} sends)</span></h3>")

        def _line(label, rows):
            if not rows:
                return
            parts = [f"{_esc(r['key'])} <strong>{r['rate']:.0f}%</strong> "
                     f"<span style='{muted}'>({r['replied']}/{r['sent']})</span>"
                     for r in rows]
            p(f"<p style='margin:2px 0'>{label}: " + ' · '.join(parts) + "</p>")

        _line('By touch', rates.get('by_touch'))
        _line('By org type', rates.get('by_org'))
        _line('By ask', rates.get('by_cta'))
        p(f"<p style='{muted};margin-top:2px'>A reply counts when a human "
          f"answered within 14 days. Bounces and out-of-office are excluded.</p>")

    p("<h3 style='margin:14px 0 4px'>Yesterday</h3>")
    p(f"<p><strong>{len(sent)}</strong> emails sent (cap {_esc(summary.get('cap'))}) \u00b7 "
      f"<strong>{len(promoted)}</strong> cold leads started \u00b7 "
      f"<strong>{len(replies)}</strong> replies captured \u00b7 "
      f"<strong>{len(summary.get('meetings', []))}</strong> meetings booked \u00b7 "
      f"~${float(summary.get('cost_usd') or 0):.2f} AI</p>")
    if replies:
        p('<ul style="margin:0">')
        for x in replies:
            p(f"<li><strong>{_esc(x.get('contact'))}</strong> \u2014 "
              f"{_esc(x.get('classification'))}: {_esc(x.get('summary'))} "
              f"<em>({_esc(x.get('action'))})</em></li>")
        p('</ul>')
    if sent:
        p(f"<p style='{muted}'>Sent: " + _esc('; '.join(
            f"{x.get('contact')} (touch {x.get('touch')})" for x in sent[:12])) + '</p>')
    if promoted:
        p(f"<p style='{muted}'>Started: " + _esc(', '.join(
            str(x.get('contact')) for x in promoted[:12])) + '</p>')
    if summary.get('nurtured'):
        p(f"<p style='{muted}'>Moved to Nurture after the last touch: "
          f"{_esc(', '.join(summary['nurtured']))}</p>")
    if summary.get('fixed'):
        p(f"<p style='{muted}'>Auto-corrected before sending ({len(summary['fixed'])}): "
          + _esc('; '.join(f"{x.get('contact')} ({x.get('why')})"
                           for x in summary['fixed'][:6] if x.get('why'))) + '</p>')
    if summary.get('held'):
        p(f"<p style='{muted}'>Held by the pre-send check ({len(summary['held'])}) "
          f"\u2014 they are in the queue above: "
          + _esc('; '.join(f"{x.get('contact')} ({x.get('why')})"
                           for x in summary['held'][:8])) + '</p>')
    if summary.get('skipped'):
        p(f"<p style='{muted}'>Skipped {len(summary['skipped'])}: "
          + _esc('; '.join(f"{x.get('contact')} ({x.get('why')})"
                           for x in summary['skipped'][:10])) + '</p>')
    if summary.get('failed'):
        p("<p style='color:#b42318'>Failed "
          f"{len(summary['failed'])}: "
          + _esc('; '.join(f"{x.get('contact')} ({x.get('why')})"
                           for x in summary['failed'][:10])) + '</p>')
    if summary.get('errors'):
        p("<p style='color:#b42318'>Errors: "
          + _esc('; '.join(summary['errors'][:5])) + '</p>')

    rw = summary.get('runway') or {}
    if rw:
        low = ' \u2014 the pool is running low.' if (rw.get('days') or 0) < 5 else '.'
        p(f"<p style='{muted}'><strong>Pipeline:</strong> {rw.get('due', 0)} due \u00b7 "
          f"{rw.get('cold', 0)} cold \u2014 about {rw.get('days', 0)} more weekday "
          f"cycles{low}</p>")

    p(f"<p style='margin-top:14px'><a href='{base}/crm/agent'>Open the console</a></p>")
    return '\n'.join(out)


def send_daily_digest(summary, settings):
    if not settings.digest_enabled:
        return False
    n = len(summary.get('sent', []))
    waiting = len(_pending_for_you())
    # Lead the subject with the ask, not the activity - this is the one line
    # that gets read on a phone lock screen.
    if waiting:
        subj = (f"{waiting} need{'s' if waiting == 1 else ''} you · {n} sent"
                f" — {summary.get('date')}")
    else:
        subj = (f"BDR agent: {n} sent, {len(summary.get('replies', []))} replies"
                f" — {summary.get('date')}")
    if summary.get('breaker'):
        subj = '⚠️ ' + subj
    return _notice(settings, subj, build_digest_html(summary, settings))


# ---------------------------------------------------------------------------
# The cycle
# ---------------------------------------------------------------------------
class _Stop(Exception):
    """Internal: end the cycle early (breaker tripped) but still finalize."""


def _claim_cycle(settings, now_utc, today_local, force):
    """Atomic day-claim: exactly one process wins a given local date (or a
    forced run, if no cycle holds the lease). rowcount==1 means we own it.

    A run that started today but never finished AND whose lease has expired
    (the process was killed — a spun-down web service, a redeploy) can be
    re-claimed the same day to finish the work. That can't double-send: the
    budget is counted from executed rows, not from a counter."""
    stmt = (db.update(AgentSettings)
            .where(AgentSettings.id == settings.id)
            .where(or_(AgentSettings.cycle_lock_until.is_(None),
                       AgentSettings.cycle_lock_until < now_utc)))
    if not force:
        stmt = stmt.where(or_(
            AgentSettings.last_cycle_date.is_(None),
            AgentSettings.last_cycle_date < today_local,
            and_(AgentSettings.last_cycle_date == today_local,
                 AgentSettings.last_cycle_finished_at.is_(None))))
    stmt = stmt.values(cycle_lock_until=now_utc + timedelta(minutes=CYCLE_LOCK_MINUTES),
                       last_cycle_started_at=now_utc, last_cycle_date=today_local,
                       last_cycle_finished_at=None, last_cycle_summary_json=None)
    res = db.session.execute(stmt.execution_options(synchronize_session=False))
    db.session.commit()
    return res.rowcount == 1


def _release_cycle(settings, summary):
    settings.cycle_lock_until = None
    settings.last_cycle_finished_at = _utcnow()
    settings.last_cycle_summary_json = json.dumps(summary, default=str)
    db.session.commit()


def _operator_id(settings):
    if settings.operator_user_id:
        return settings.operator_user_id
    u = (CrmUser.query.filter_by(role='admin').order_by(CrmUser.id).first()
         or CrmUser.query.order_by(CrmUser.id).first())
    return u.id if u else None


def _needs_human_leads(limit=500):
    """Open leads a person owns and owes a touch. The agent never emails these
    — Engaged and Qualified mean a real conversation is in progress — so the
    digest has to name them, not count them."""
    from app.crm.views import _due_leads
    from app.crm.models import LEAD_HUMAN_STATUSES
    return [c for c in _due_leads(limit=limit)
            if (c.lead_status or 'New') in LEAD_HUMAN_STATUSES]


def _needs_human_count():
    return len(_needs_human_leads())


def _pending_for_you():
    """Everything sitting in the approval queue, newest first — replies first
    because a person is waiting on the other end of those."""
    rows = (CrmAgentAction.query.filter_by(status='pending')
            .order_by(CrmAgentAction.id.desc()).limit(30).all())
    rows.sort(key=lambda a: (0 if a.action_type == 'reply_email'
                             else 1 if (a.title or '').startswith('[Needs review]')
                             else 2, -(a.id or 0)))
    return rows


def _meetings_next_48h(now=None):
    try:
        from app.models import Booking
        start = now or _utcnow()
        return (Booking.query
                .filter(Booking.status == 'confirmed',
                        Booking.start_at >= start - timedelta(hours=1),
                        Booking.start_at <= start + timedelta(hours=48))
                .order_by(Booking.start_at).all())
    except Exception:  # noqa: BLE001
        return []


def _platform_movements():
    """Trials about to lapse and gardens that went Pro this week — the only
    two product events that should interrupt a founder's morning."""
    out = {'trials_ending': [], 'converted': []}
    try:
        from app.models import CommunityGarden, GardenSubscription
        now = _utcnow()
        for sub in (GardenSubscription.query
                    .filter(GardenSubscription.status == 'trialing',
                            GardenSubscription.trial_end.isnot(None),
                            GardenSubscription.trial_end <= now + timedelta(days=7))
                    .order_by(GardenSubscription.trial_end).all()):
            g = db.session.get(CommunityGarden, sub.garden_id)
            out['trials_ending'].append((g.name if g else f'Garden #{sub.garden_id}',
                                         sub.trial_end))
        for sub in (GardenSubscription.query
                    .filter(GardenSubscription.status == 'active',
                            GardenSubscription.updated_at >= now - timedelta(days=7))
                    .all()):
            g = db.session.get(CommunityGarden, sub.garden_id)
            out['converted'].append(g.name if g else f'Garden #{sub.garden_id}')
    except Exception:  # noqa: BLE001
        pass
    return out


def _meetings_today(now_local):
    try:
        from app.models import Booking
        since = local_midnight_utc(now_local)
        rows = Booking.query.filter(Booking.created_at >= since,
                                    Booking.status == 'confirmed').all()
        return [f"{b.invitee_name} — {b.start_at:%b %d %H:%M} UTC" for b in rows]
    except Exception:  # noqa: BLE001
        return []


def run_daily_cycle(*, now=None, force=False, poll=True):
    """One autonomous BDR cycle. Returns the summary dict, or None when the
    cycle didn't run (gated, or another process already claimed today)."""
    from flask import current_app
    settings = get_settings()
    now_utc = now or _utcnow()
    now_local = local_now(settings, now_utc)
    gates = cycle_gates(settings, now_local, force=force)
    if gates:
        log.info('BDR cycle gated: %s', gates)
        return None
    if not _claim_cycle(settings, now_utc, now_local.date(), force):
        log.info('BDR cycle already ran/running for %s', now_local.date())
        return None
    db.session.refresh(settings)

    run = CrmAgentRun(kind='autonomous', status='running')
    db.session.add(run)
    db.session.commit()
    run_id = run.id
    usage = _Usage()
    summary = {'date': now_local.strftime('%a %b %d, %Y'), 'cap': int(settings.daily_send_cap or 15),
               'sent': [], 'promoted': [], 'replies': [], 'skipped': [], 'failed': [],
               'nurtured': [], 'errors': [], 'meetings': [], 'held': [], 'fixed': [],
               'breaker': None}
    actor_id = _operator_id(settings)
    sender = current_app.config.get('CRM_FROM_NAME') or ''
    try:
        # 1. Replies first — anyone who wrote back must drop out before we send.
        if poll and imap_configured():
            try:
                pr = A.poll_replies(now=now_utc)
                summary['replies'] = pr.get('handled', [])
            except Exception as e:  # noqa: BLE001
                summary['errors'].append(f'Reply poll failed: {e}')
                log.exception('Reply poll inside cycle failed')
            db.session.refresh(settings)
            if settings.require_reply_capture and (
                    not settings.last_reply_poll_ok_at
                    or (_utcnow() - settings.last_reply_poll_ok_at) > timedelta(hours=24)):
                trip_breaker(settings, 'Reply capture is failing — refusing to send blind.')
                summary['breaker'] = settings.paused_reason
                raise _Stop()
        # 2. Hard-bounce breaker.
        hb = hard_bounces_24h(now_utc)
        if hb >= int(settings.max_hard_bounces_24h or 3):
            trip_breaker(settings, f'{hb} hard bounces/complaints in the last 24h.')
            summary['breaker'] = settings.paused_reason
            raise _Stop()
        # 3. Budget.
        budget = max(0, int(settings.daily_send_cap or 15) - sends_today(settings, now_local))
        summary['budget_start'] = budget
        # 4. Follow-ups to due leads.
        if settings.auto_followups and budget > 0:
            leads = _eligible_due_leads(settings, budget)
            n = _auto_send_batch(leads, settings, summary, usage, budget,
                                 sender=sender, actor_id=actor_id)
            budget -= n
            if summary['breaker']:
                raise _Stop()
        # 5. Fill the rest with cold intros.
        if settings.auto_promote_cold and settings.auto_followups and budget > 0:
            promoted = _promote_cold(settings, summary, usage, budget, actor_id=actor_id)
            if promoted:
                n = _auto_send_batch(promoted, settings, summary, usage, budget,
                                     sender=sender, actor_id=actor_id)
                budget -= n
                if summary['breaker']:
                    raise _Stop()
        # 6. Keep the pool from running dry. The digest used to nag the
        #    operator to press two buttons; the agent can do it, and a lead
        #    pool that empties silently is how a sender goes quiet without
        #    anybody noticing.
        _top_up_supply(settings, summary, usage, now_local)
    except _Stop:
        pass
    except Exception as e:  # noqa: BLE001
        log.exception('Autonomous cycle crashed')
        db.session.rollback()
        summary['errors'].append(f'Cycle crashed: {e}')
        _record_run(run_id, usage, error=e)
    finally:
        db.session.refresh(settings)
        try:
            summary['meetings'] = _meetings_today(now_local)
            summary['needs_human'] = _needs_human_count()
            summary['runway'] = _runway(settings)
            summary['rates'] = funnel_rates()
        except Exception:  # noqa: BLE001
            log.exception('Digest extras failed')
        t = usage.totals()
        summary['cost_usd'] = t['cost_usd']
        summary['tokens'] = t['input_tokens'] + t['output_tokens']
        r = db.session.get(CrmAgentRun, run_id)
        if r is not None and r.status == 'running':
            _record_run(run_id, usage)
        _release_cycle(settings, summary)
        try:
            send_daily_digest(summary, settings)
        except Exception:  # noqa: BLE001
            log.exception('Digest failed')
    return summary
