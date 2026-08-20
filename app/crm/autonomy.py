"""BDR agent execution + autonomy — request-context-free.

Everything the agent can *do* to the CRM lives here so it can be driven two
ways with one code path:

* by a human clicking Approve in the console (``views.agent_action_approve``
  is now a thin adapter: claim → ``execute_action`` → flash/redirect), and
* by the autonomous daily cycle (``run_daily_cycle``, wired into the
  15-minute cron via ``maybe_tick``), which claims and executes its own
  proposals without a human in the loop — subject to the policy flags,
  daily send cap, send window, and circuit breakers on ``AgentSettings``.

Nothing in this module reads ``request`` or ``current_user``; callers pass
the edited form values and the acting user id explicitly.
"""
import json
from dataclasses import dataclass, field
from datetime import timedelta

from app import db
from app.crm.helpers import log_activity, render_merge, smtp_send
from app.crm.models import (Campaign, Company, Contact, CrmAgentAction, Note,
                            _utcnow)

# BDR touch cadence: spacing (days) after the Nth no-reply follow-up, then the
# cap — after MAX_NO_REPLY_TOUCHES sends with no reply the lead auto-moves to
# Nurture and resurfaces via the daily cron. Protects domain reputation (and
# the lead) from an every-4-days-forever loop.
# Spacing between no-reply touches. A volunteer coordinator reads garden mail
# weekly, not daily — 4/8 days landed three emails inside twelve days, which
# reads as pressure from a stranger. 5/14 spans three weekends instead of one.
TOUCH_SPACING_DAYS = [5, 14]
MAX_NO_REPLY_TOUCHES = 3
NURTURE_RESURFACE_DAYS = 90


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------
@dataclass
class ExecResult:
    """Outcome of executing one proposal.

    ``status`` is one of:
      executed — did the thing (email sent / lead promoted / draft created …)
      failed   — attempted and the provider/DB said no (send rejected, FB error)
      skipped  — deliberately not done (no email, opted out, suppressed) — NOT
                 a failure; the autonomous cycle must not trip a breaker on it
      invalid  — the proposal can't be executed as-is (empty message, missing
                 name); caller should un-claim so it returns to the queue
    ``redirect`` is an optional (endpoint, kwargs) hint for the web adapter.
    """
    ok: bool
    status: str
    message: str
    category: str = 'success'
    redirect: tuple | None = None
    detail: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Claims — the pending→executing UPDATE is the double-execution guard
# ---------------------------------------------------------------------------
def claim_action(aid):
    """Atomically move a proposal pending → executing. True if WE won it.

    A double-click, two overlapping requests, or the cron and a human racing
    can win this UPDATE exactly once, so a proposal can never send the same
    email twice / double-advance the cadence."""
    claimed = (CrmAgentAction.query
               .filter_by(id=aid, status='pending')
               .update({'status': 'executing'}, synchronize_session=False))
    db.session.commit()
    return bool(claimed)


def unclaim_action(action):
    """Return a claimed proposal to the queue (validation early-exit)."""
    action.status = 'pending'
    db.session.commit()


def cancel_pending_actions(contact_id, reason, *, types=None):
    """Retire every pending proposal for a contact (lead replied, booked a
    meeting, unsubscribed …). Returns the number cancelled. Caller commits."""
    if not contact_id:
        return 0
    q = CrmAgentAction.query.filter_by(contact_id=contact_id, status='pending')
    if types:
        q = q.filter(CrmAgentAction.action_type.in_(list(types)))
    return q.update({'status': 'rejected', 'result': (reason or 'Superseded')[:400],
                     'reviewed_at': _utcnow()}, synchronize_session=False)


def apply_reply(contact, *, note='Lead replied — marked Engaged'):
    """The lead answered: they're Engaged, the no-reply clock resets, the next
    touch is near-term, and any queued automated follow-ups are withdrawn so
    nothing nudges someone who already wrote back. Caller commits."""
    if (contact.lead_status or 'New') in ('New', 'Working', 'Nurture'):
        contact.lead_status = 'Engaged'
    contact.followup_count = 0
    contact.last_contacted_at = _utcnow()
    contact.next_action_at = _utcnow().date() + timedelta(days=3)
    contact.next_action_note = 'Continue the conversation'
    log_activity('updated', note, contact_id=contact.id, company_id=contact.company_id)
    cancel_pending_actions(contact.id, 'Superseded: lead replied',
                           types=('follow_up_email', 'scout'))


# ---------------------------------------------------------------------------
# Helpers shared by branches
# ---------------------------------------------------------------------------
def _location_conflicts(company, city, state):
    """True when a same-name company sits in a clearly DIFFERENT place than
    the incoming city/state — i.e. it's a different org that happens to share
    a generic name. Blank values on either side are inconclusive (no
    conflict), so orgs without location data still dedupe by name."""
    new_city = (city or '').strip().lower()
    new_state = (state or '').strip().lower()
    have_city = (company.city or '').strip().lower()
    have_state = (company.state or '').strip().lower()
    if new_state and have_state and new_state != have_state:
        return True
    return bool(new_city and have_city and new_city != have_city)


def _finish(action, status, result, actor_id, *, auto=False):
    action.status = status
    action.result = (result or '')[:400]
    action.reviewed_at = _utcnow()
    action.reviewed_by_id = actor_id
    if auto and hasattr(action, 'auto_executed'):
        action.auto_executed = True


def email_ready():
    """True when outbound mail is really configured (ZeptoMail token present).
    Module-level so the cycle can gate on it and tests can patch it."""
    from app.email_service import is_configured
    return bool(is_configured())


# ---------------------------------------------------------------------------
# execute_action — the one place a proposal turns into a real-world effect
# ---------------------------------------------------------------------------
def execute_action(action, *, form=None, actor_id=None, auto=False, extra_headers=None):
    """Execute an already-CLAIMED proposal and return an ExecResult.

    ``form`` — a dict-like of the reviewer's edits (``request.form`` for the
    web adapter, ``{}``/None for autonomous runs; values fall back to the
    stored payload). ``actor_id`` — CrmUser id recorded as reviewer (None
    when nobody clicked). ``auto`` — mark the action as executed by the
    autonomous cycle. ``extra_headers`` — MIME headers to add to a send
    (the cycle passes List-Unsubscribe). Commits on every terminal outcome;
    on ``invalid`` the caller decides whether to un-claim.
    """
    form = form or {}
    p = action.payload or {}
    kind = action.action_type

    if kind == 'campaign':
        # Materialize a DRAFT campaign; the human reviews recipients and sends.
        campaign = Campaign(
            name=(p.get('name') or 'Untitled campaign')[:160],
            subject=(p.get('subject') or '')[:200], body=p.get('body') or '',
            status='draft', created_by=actor_id,
            audience_state=p.get('audience_state') or None,
            audience_org_type=p.get('audience_org_type') or None,
            audience_tag=p.get('audience_tag') or None,
            audience_desc=p.get('audience_desc') or 'All contacts with email')
        db.session.add(campaign)
        db.session.flush()
        _finish(action, 'executed', f'Created draft campaign #{campaign.id}', actor_id, auto=auto)
        db.session.commit()
        return ExecResult(True, 'executed',
                          'Draft campaign created — review the audience and send when ready.',
                          redirect=('crm.campaign_detail', {'cid': campaign.id}),
                          detail={'campaign_id': campaign.id})

    if kind == 'facebook_post':
        # The reviewer edited the copy, attached a photo, and optionally set a
        # schedule before approving — publish (or schedule) it now.
        from app.crm.facebook_views import submit_post, _parse_dt
        message = (form.get('message') or p.get('message') or '').strip()
        link = (form.get('link') or p.get('link') or '').strip()
        image_url = (form.get('image_url') or p.get('image_url') or '').strip()
        when = _parse_dt(form.get('scheduled_for'))
        if not message:
            return ExecResult(False, 'invalid', 'Write a message before posting.', 'warning')
        post = submit_post(message=message, link=link or None,
                           image_url=image_url or None, scheduled_for=when,
                           created_by_id=actor_id)
        if post.status == 'scheduled':
            result = f'Scheduled post #{post.id} for {post.scheduled_for:%b %d %H:%M} UTC'
            msg, cat, status = (f'Post scheduled for {post.scheduled_for:%b %d, %Y %H:%M} UTC.',
                                'success', 'executed')
        elif post.status == 'published':
            result, msg, cat, status = f'Published post #{post.id}', 'Posted to Facebook.', 'success', 'executed'
        elif post.status == 'draft':
            result = f'Saved post #{post.id} as a draft (no Page connected)'
            msg, cat, status = 'Saved as a draft — connect a Page to publish it.', 'warning', 'executed'
        else:
            result = f'Post failed: {post.error}'
            msg, cat, status = f'Could not post: {post.error}', 'danger', 'failed'
        action.payload_json = json.dumps({
            'message': message, 'link': link, 'image_url': image_url,
            'hashtags': p.get('hashtags', []),
            'image_idea': p.get('image_idea', '')})
        _finish(action, status, result, actor_id, auto=auto)
        db.session.commit()
        return ExecResult(status == 'executed', status, msg, cat, detail={'post_id': post.id})

    if kind == 'new_lead':
        # A web-scouted org → create the Company (dedupe by name) + a New lead
        # Contact owned by the reviewer, due today, so it enters the work queue.
        from sqlalchemy import func
        from app.email_service import is_email_suppressed
        name = (p.get('name') or '').strip()
        if not name:
            return ExecResult(False, 'invalid', 'That lead is missing a name.', 'warning')
        company = (Company.query
                   .filter(func.lower(Company.name) == name.lower()).first())
        # Collision-aware dedup: generic names repeat constantly in this
        # vertical ("Community Garden", "Parks & Recreation"). If the
        # same-name match sits in a DIFFERENT city/state than the scouted
        # org, it is a different org — attaching would silently discard the
        # scouted location and misdirect outreach to the wrong company.
        if company is not None and _location_conflicts(company, p.get('city'), p.get('state')):
            company = None
        if not company:
            company = Company(name=name[:160], city=(p.get('city') or '')[:80],
                              state=(p.get('state') or '')[:20],
                              org_type=(p.get('org_type') or None),
                              website=(p.get('website') or '')[:255], tags='Scout')
            db.session.add(company)
            db.session.flush()
        contact = Contact(
            name=(p.get('contact_name') or f'Info — {name}')[:120],
            email=(p.get('contact_email') or None),
            phone=(p.get('contact_phone') or None),
            # Both skills already asked for a title and then dropped it.
            # "Executive Director" is what says whether this person decides.
            title=((p.get('contact_title') or '').strip()[:120] or None),
            email_opt_out=is_email_suppressed(p.get('contact_email')),
            company_id=company.id, lead_status='New', source='Scout',
            owner_id=actor_id, next_action_at=_utcnow().date())
        db.session.add(contact)
        db.session.flush()
        bits = [b for b in (p.get('fit'),
                            (f"Source: {p['source_url']}" if p.get('source_url') else None))
                if b]
        if bits:
            db.session.add(Note(content='[Scouted lead] ' + ' — '.join(bits),
                                contact_id=contact.id, company_id=company.id))
        log_activity('created', f'Added scouted lead "{name}"',
                     contact_id=contact.id, company_id=company.id)
        _finish(action, 'executed', f'Added {name} to CRM (contact #{contact.id})', actor_id, auto=auto)
        db.session.commit()
        return ExecResult(True, 'executed', f'Added {name} to your leads — it’s now in the funnel.',
                          detail={'contact_id': contact.id})

    contact = db.session.get(Contact, action.contact_id) if action.contact_id else None
    if not contact:
        _finish(action, 'failed', 'Contact no longer exists', actor_id, auto=auto)
        db.session.commit()
        return ExecResult(False, 'failed', 'That contact no longer exists.', 'danger')

    if kind == 'scout':
        # Promote a cold, scouted lead into the active working queue so the
        # engagement agent can then draft the first touch.
        angle = p.get('angle')
        if (contact.lead_status or 'New') == 'New':
            contact.lead_status = 'Working'
        if not contact.owner_id:
            contact.owner_id = actor_id
        if not contact.source:
            contact.source = 'Scout'
        contact.next_action_at = _utcnow().date()
        if angle and not contact.next_action_note:
            contact.next_action_note = angle[:200]
        log_activity('updated', ('Scouted → working' + (f': {angle}' if angle else ''))[:400],
                     contact_id=contact.id, company_id=contact.company_id)
        _finish(action, 'executed', f'Started working {contact.name}', actor_id, auto=auto)
        db.session.commit()
        return ExecResult(True, 'executed',
                          f'{contact.name} is now in your working queue — draft an intro from the queue.',
                          detail={'contact_id': contact.id})

    if kind not in ('follow_up_email', 'reply_email'):
        return ExecResult(False, 'invalid', 'That proposal type can’t be executed yet.', 'warning')

    # ---- follow_up_email / reply_email: an actual send -------------------
    # The reviewer may have edited the draft before approving; autonomous
    # runs pass no form and use the stored draft verbatim.
    subject_raw = (form.get('subject') if form.get('subject') is not None else p.get('subject') or '').strip()
    body_raw = (form.get('body') if form.get('body') is not None else p.get('body') or '').strip()
    subject = render_merge(subject_raw, contact)
    body = render_merge(body_raw, contact)

    # Pre-checks: these are SKIPS, not failures — the lead simply can't be
    # emailed. Autonomy must not burn the cadence or trip a breaker on them.
    from app.email_service import is_email_suppressed
    skip = None
    if not contact.email:
        skip = 'no email address'
    elif contact.email_opt_out:
        skip = 'opted out'
    elif is_email_suppressed(contact.email):
        skip = 'on the suppression list'
    if skip:
        # Human approvals used to "log" the email in this case; keep that
        # record for the timeline but don't advance the cadence.
        log_activity('email', f'Email not sent (BDR agent, {skip}): {subject}',
                     contact_id=contact.id, company_id=contact.company_id)
        _finish(action, 'executed', f'Skipped — {skip}', actor_id, auto=auto)
        action.payload_json = json.dumps({'subject': subject_raw, 'body': body_raw})
        db.session.commit()
        return ExecResult(False, 'skipped', f'Not sent — {contact.name} is {skip}.', 'warning',
                          detail={'skip': skip})

    headers = dict(extra_headers or {})
    if kind == 'reply_email' and p.get('in_reply_to'):
        headers.update({'In-Reply-To': p['in_reply_to'], 'References': p['in_reply_to']})
    recipient = contact.email
    # Own the Message-ID so a reply that comes back from a different address
    # than the one we mailed can still be threaded to this contact.
    from app.crm.helpers import new_message_id
    mid = new_message_id()
    sent = smtp_send(recipient, subject, body, headers=headers or None, message_id=mid)
    if not sent and email_ready():
        # ZeptoMail is configured and rejected/failed the send. Don't pretend
        # it went out, don't advance the cadence, and surface it to whoever is
        # (or isn't) watching.
        _finish(action, 'failed', f'Send failed to {recipient} (provider rejected)', actor_id, auto=auto)
        action.payload_json = json.dumps({'subject': subject_raw, 'body': body_raw})
        db.session.commit()
        return ExecResult(False, 'failed', f'Send to {contact.name} failed — check the email service.', 'danger')
    verb = 'Email sent' if sent else 'Email logged'

    who = 'BDR agent' if kind == 'follow_up_email' else 'BDR agent reply'
    log_activity('email', f'{verb} ({who}): {subject}',
                 contact_id=contact.id, company_id=contact.company_id)
    db.session.add(Note(
        content=f'[{verb} to {recipient}] {subject}\n\n{body}',
        contact_id=contact.id))

    if kind == 'reply_email':
        # Answering a lead who wrote to us: they're Engaged already; keep the
        # conversation warm without touching the no-reply cadence.
        contact.last_contacted_at = _utcnow()
        contact.next_action_at = _utcnow().date() + timedelta(days=3)
        contact.next_action_note = 'Awaiting their reply'
        outcome = f'Replied to {contact.name}; next check-in in 3 days.'
    else:
        # Advance the lifecycle: contacted now, nudge status forward, then apply
        # the touch cadence — no-reply follow-ups space out 4d → 8d, and after the
        # cap the lead auto-moves to Nurture (resurfaced by the daily cron in ~90
        # days) instead of being emailed every few days forever. A reply or a
        # booked meeting resets followup_count (see apply_reply / booking upsert).
        contact.last_contacted_at = _utcnow()
        if (contact.lead_status or 'New') == 'New':
            contact.lead_status = 'Working'
        contact.followup_count = (contact.followup_count or 0) + 1
        if contact.followup_count >= MAX_NO_REPLY_TOUCHES:
            contact.lead_status = 'Nurture'
            contact.next_action_at = _utcnow().date() + timedelta(days=NURTURE_RESURFACE_DAYS)
            contact.next_action_note = 'Auto-nurtured after no-reply follow-ups'
            log_activity('updated',
                         f'Auto-nurtured after {contact.followup_count} no-reply '
                         f'follow-ups — resurfaces in ~{NURTURE_RESURFACE_DAYS} days',
                         contact_id=contact.id, company_id=contact.company_id)
            outcome = (f'{contact.name} moved to Nurture after '
                       f'{contact.followup_count} touches with no reply.')
        else:
            spacing = TOUCH_SPACING_DAYS[min(contact.followup_count,
                                             len(TOUCH_SPACING_DAYS)) - 1]
            contact.next_action_at = _utcnow().date() + timedelta(days=spacing)
            contact.next_action_note = 'Awaiting reply to follow-up'
            outcome = (f'{contact.name} is now “{contact.lead_status}”, '
                       f'next touch in {spacing} days.')

    # message_id/sent_subject are what autonomy_replies matches an inbound
    # reply against when it arrives from an address we never mailed.
    action.payload_json = json.dumps({**p, 'subject': subject_raw, 'body': body_raw,
                                      'message_id': mid, 'sent_subject': subject})
    _finish(action, 'executed', f'{verb} to {recipient}', actor_id, auto=auto)
    db.session.commit()
    return ExecResult(True, 'executed', f'{verb}. {outcome}',
                      detail={'sent': bool(sent), 'contact_id': contact.id,
                              'subject': subject, 'touch': contact.followup_count})


# ---------------------------------------------------------------------------
# Public surface: the daily cycle lives in autonomy_cycle.py and reply
# capture in autonomy_replies.py (size only); both are re-exported here so
# callers/tests use ``autonomy.run_daily_cycle`` / ``autonomy.poll_replies``.
# Imported last so those modules can import the primitives above.
# ---------------------------------------------------------------------------
from app.crm.autonomy_replies import (  # noqa: E402,F401
    ImapFetcher, handle_inbound, is_auto_reply, parse_inbound, poll_replies,
    strip_quoted, test_imap_connection)
from app.crm.autonomy_cycle import (  # noqa: E402,F401
    build_digest_html, cycle_gates, env_autonomy_off, get_settings,
    hard_bounces_24h, imap_configured, is_send_window, local_now,
    run_daily_cycle, send_daily_digest, sends_today, trip_breaker,
    _eligible_due_leads, _followup_context, _prior_emails, _cold_pool)


def maybe_tick(*, now=None, daily_jobs=True):
    """The heartbeat: poll replies when due, run the daily cycle if it's time
    and unclaimed, and carry the once-a-day housekeeping.

    Driven by an external scheduler (GitHub Actions → POST /crm/api/agent/tick)
    because Render has no free cron instance type, so the crons declared in
    render.yaml were never provisioned. Never raises — a failure in one part
    must not stop the others."""
    out = {'polled': None, 'cycle': None, 'daily': None, 'errors': []}
    try:
        settings = get_settings()
        now_utc = now or _utcnow()
        if imap_configured() and (
                settings.last_reply_poll_at is None
                or (now_utc - settings.last_reply_poll_at) >= timedelta(minutes=14)):
            r = poll_replies(now=now_utc)
            out['polled'] = {k: r.get(k) for k in ('fetched', 'matched', 'skipped', 'errors')}
    except Exception as e:  # noqa: BLE001
        out['errors'].append(f'poll: {e}')
    try:
        s = run_daily_cycle(now=now, poll=False)
        out['cycle'] = ({'sent': len(s.get('sent', [])), 'promoted': len(s.get('promoted', [])),
                         'breaker': s.get('breaker'), 'errors': s.get('errors')}
                        if s else None)
    except Exception as e:  # noqa: BLE001
        out['errors'].append(f'cycle: {e}')
    if daily_jobs:
        # Scheduled Facebook posts need per-tick granularity, not once a day.
        try:
            from app.crm.facebook_views import publish_scheduled_posts
            n = publish_scheduled_posts()
            if n:
                out['facebook'] = n
        except Exception as e:  # noqa: BLE001
            out['errors'].append(f'facebook: {e}')
        try:
            out['daily'] = run_daily_jobs_once(now=now)
        except Exception as e:  # noqa: BLE001
            out['errors'].append(f'daily jobs: {e}')
    return out


def run_daily_jobs_once(*, now=None):
    """Once-a-day housekeeping that was supposed to ride the Render crons
    (never provisioned — no free cron instance type): meeting reminders,
    nurture resurfacing, the Monday CRM backup, and the garden trial
    lifecycle. Claimed once per LOCAL day off the settings row, so repeated
    heartbeats run it exactly once."""
    import logging
    from app.crm.models import AgentSettings
    from sqlalchemy import or_ as _or
    log = logging.getLogger(__name__)
    settings = get_settings()
    today = local_now(settings, now or _utcnow()).date()
    claimed = db.session.execute(
        db.update(AgentSettings)
        .where(AgentSettings.id == settings.id)
        .where(_or(AgentSettings.last_daily_jobs_date.is_(None),
                   AgentSettings.last_daily_jobs_date < today))
        .values(last_daily_jobs_date=today)
        .execution_options(synchronize_session=False)).rowcount
    db.session.commit()
    if not claimed:
        return None
    done = []
    for label, fn in (('crm-daily', _crm_daily), ('trial-lifecycle', _trial_lifecycle),
                      ('platform-match', reconcile_platform_status)):
        try:
            fn()
            done.append(label)
        except Exception:  # noqa: BLE001
            log.exception('%s failed', label)
            done.append(f'{label}:failed')
    return done


def _crm_daily():
    from app.cli import _run_crm_daily_jobs
    _run_crm_daily_jobs()


def _trial_lifecycle():
    """Garden trial expiries + onboarding drip — the other job the missing
    cron was supposed to run."""
    from app.cli import run_garden_trial_lifecycle
    run_garden_trial_lifecycle()


# Ordered by depth in the funnel, so a contact who organises two gardens takes
# the status of the further-along one. A lapsed subscription outranks a bare
# garden deliberately: "they had a garden" is true but "they paid and stopped"
# is the fact worth acting on.
_PLATFORM_RANK = ['none', 'registered', 'garden', 'expired', 'past_due',
                  'trialing', 'active']


def _rank(status):
    try:
        return _PLATFORM_RANK.index(status or 'none')
    except ValueError:
        return 0


def reconcile_platform_status(*, now=None):
    """Match CRM contacts to product accounts by email and record how far each
    one got: none → registered → garden → trialing → active (past_due/expired
    rank below registered so a lapsed garden still reads as "on the platform").

    This is the only thing that makes a sale visible to the CRM. It is
    deliberately a nightly batch rather than a request-path hook: matching on
    lowercase email is lossy (an organiser often signs up from a different
    address than the scraped ``info@``), so we compute a match RATE and report
    it honestly instead of pretending every subscription found its lead.

    Returns ``(matched, total_subscriptions)``.
    """
    from sqlalchemy import func
    from app.models import User, CommunityGarden
    from app.crm.models import Contact, Activity

    settings = get_settings()
    stamp = now or _utcnow()

    # email -> best status seen for that email
    best = {}

    def offer(email, status):
        addr = (email or '').strip().lower()
        if not addr:
            return
        if _rank(status) > _rank(best.get(addr)):
            best[addr] = status

    for user in User.query.filter(User.email.isnot(None)).all():
        offer(user.email, 'registered')

    total_subs = 0
    matched_subs = 0
    sub_emails = []
    for garden in CommunityGarden.query.all():
        organizer = getattr(garden, 'organizer', None)
        email = getattr(organizer, 'email', None)
        if not email:
            continue
        offer(email, 'garden')
        sub = getattr(garden, 'subscription', None)
        if sub is not None:
            total_subs += 1
            sub_emails.append((email or '').strip().lower())
            # GardenSubscription.status already uses our vocabulary
            # (trialing/active/past_due/cancelled/expired); cancelled reads as
            # expired for our purposes — the garden exists, the money stopped.
            status = 'expired' if sub.status == 'cancelled' else sub.status
            offer(email, status)

    if not best:
        settings.last_match_run_at = stamp
        settings.last_match_matched = 0
        settings.last_match_total = total_subs
        db.session.commit()
        return 0, total_subs

    matched_addrs = set()
    contacts = (Contact.query
                .filter(Contact.email.isnot(None))
                .filter(func.lower(Contact.email).in_(list(best)))
                .all())
    for contact in contacts:
        addr = (contact.email or '').strip().lower()
        status = best.get(addr)
        if not status or status == contact.platform_status:
            continue
        first_time = not contact.platform_status
        contact.platform_status = status
        contact.platform_status_at = stamp
        matched_addrs.add(addr)
        db.session.add(Activity(
            kind='updated', user_id=None, contact_id=contact.id,
            company_id=contact.company_id,
            description=('Signed up on the platform' if first_time
                         else f'Platform status: {status}')))

    matched_subs = len([a for a in sub_emails if a in {
        (c.email or '').strip().lower() for c in contacts}])
    settings.last_match_run_at = stamp
    settings.last_match_matched = matched_subs
    settings.last_match_total = total_subs
    db.session.commit()
    return matched_subs, total_subs
