"""Reply capture — poll the operator's mailbox over IMAP and feed replies back
into the BDR loop.

This is the autonomous cycle's safety net: a lead who writes back must never
receive another automated follow-up. Every poll:

  fetch new mail (UID > last seen) → skip our own / auto-replies / bounces →
  match the sender to a CRM contact → classify (deterministic first, then
  the model) → apply the lifecycle effect (Engaged / Disqualified /
  unsubscribed / snoozed) → withdraw pending automated proposals for that
  contact → store a CrmInboundReply → for interested/other, draft a reply
  as a QUEUED ``reply_email`` proposal for the operator to approve.

Read-only against the mailbox: EXAMINE + BODY.PEEK[] leave unread flags
untouched. Progress is tracked by UID on AgentSettings so a re-poll can
never double-act; ``message_id`` is unique for the same reason.
"""
import email
import email.utils
import imaplib
import logging
import re
import ssl
from datetime import timedelta
from email.header import decode_header, make_header

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app import db
from app.crm import autonomy as A
from app.crm.helpers import log_activity
from app.crm.models import (AgentSettings, Company, Contact, CrmAgentAction,
                            CrmInboundReply, Note, _utcnow)

log = logging.getLogger(__name__)

POLL_LEASE_MINUTES = 10
POLL_BATCH = 200
SNIPPET_MAX = 2000
OOO_SNOOZE_DAYS = 7


# ---------------------------------------------------------------------------
# IMAP transport (real one; tests inject a fake with the same 3 methods)
# ---------------------------------------------------------------------------
class ImapFetcher:
    """Thin read-only wrapper over imaplib for one poll."""

    def __init__(self, host, port, user, password, mailbox='INBOX', timeout=30):
        self.host, self.port, self.user, self.password = host, int(port or 993), user, password
        self.mailbox = mailbox or 'INBOX'
        self.timeout = timeout
        self._conn = None

    def open(self):
        ctx = ssl.create_default_context()
        self._conn = imaplib.IMAP4_SSL(self.host, self.port, ssl_context=ctx, timeout=self.timeout)
        self._conn.login(self.user, self.password)
        # EXAMINE = read-only select: nothing we do can flip \Seen.
        typ, data = self._conn.select(self.mailbox, readonly=True)
        if typ != 'OK':
            raise imaplib.IMAP4.error(f'Could not open mailbox {self.mailbox}: {data}')

    def state(self):
        """(uidvalidity, uidnext) for the selected mailbox."""
        typ, data = self._conn.status(self.mailbox, '(UIDVALIDITY UIDNEXT)')
        if typ != 'OK':
            raise imaplib.IMAP4.error(f'STATUS failed: {data}')
        text = data[0].decode() if isinstance(data[0], bytes) else str(data[0])
        m_v = re.search(r'UIDVALIDITY (\d+)', text)
        m_n = re.search(r'UIDNEXT (\d+)', text)
        return (int(m_v.group(1)) if m_v else 0, int(m_n.group(1)) if m_n else 1)

    def fetch_after(self, last_uid, limit=POLL_BATCH):
        """[(uid, raw_bytes)] for messages with UID > last_uid, ascending."""
        typ, data = self._conn.uid('SEARCH', None, f'UID {int(last_uid) + 1}:*')
        if typ != 'OK':
            raise imaplib.IMAP4.error(f'UID SEARCH failed: {data}')
        raw = data[0] or b''
        # 'n:*' also returns the highest UID even when it's <= n — filter client-side.
        uids = sorted(int(u) for u in raw.split() if int(u) > int(last_uid))[:limit]
        out = []
        for uid in uids:
            typ, msg = self._conn.uid('FETCH', str(uid), '(BODY.PEEK[])')
            if typ != 'OK' or not msg or not isinstance(msg[0], tuple):
                continue
            out.append((uid, msg[0][1]))
        return out

    def close(self):
        try:
            if self._conn is not None:
                try:
                    self._conn.close()
                except Exception:  # noqa: BLE001
                    pass
                self._conn.logout()
        except Exception:  # noqa: BLE001
            pass


def clean_host(raw, default='imap.zoho.com'):
    """Coerce whatever was pasted into the env var into a bare hostname.

    A scheme, a port, a trailing slash or stray whitespace all produce a
    DNS failure ("Name or service not known") that reads like a broken
    integration rather than a typo, so normalize instead of trusting it."""
    h = (raw or '').strip().strip('"\'')
    h = re.sub(r'^[a-z][\w+.-]*://', '', h, flags=re.I)   # imaps:// https:// …
    h = h.split('/')[0].split('?')[0]                      # path / query
    if h.count(':') == 1:                                  # host:993
        h = h.split(':')[0]
    h = h.strip().strip('.').lower()
    return h or default


def _fetcher_from_config():
    from flask import current_app
    import os
    cfg = current_app.config
    return ImapFetcher(
        host=clean_host(os.environ.get('CRM_IMAP_HOST') or cfg.get('CRM_IMAP_HOST')),
        port=cfg.get('CRM_IMAP_PORT') or 993,
        user=(cfg.get('CRM_IMAP_USER') or cfg.get('CRM_FROM_EMAIL')
              or 'james@yardharvest.app').strip(),
        password=os.environ.get('CRM_IMAP_PASSWORD') or cfg.get('CRM_IMAP_PASSWORD') or '',
        mailbox=cfg.get('CRM_IMAP_MAILBOX') or 'INBOX')


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------
_QUOTE_CUT = re.compile(
    r'^(On .{0,200}wrote:\s*$|-{2,}\s*Original Message\s*-{2,}|From:\s.+|Sent from my .+|'
    r'_{5,}|Sent:\s.+|>\s?.*)$', re.I)
_SIG_CUT = re.compile(r'^-- ?$')
_OOO_SUBJECT = re.compile(
    r'^(auto(matic)?[ -]?reply|automatic response|out of (the )?office|ooo\b|away from (my )?(desk|office)|'
    r'on (annual )?leave|vacation (auto|reply))', re.I)
_DAEMON = re.compile(r'^(mailer-daemon|postmaster|noreply|no-reply|do-not-reply)@', re.I)


def _dec(value):
    if not value:
        return ''
    try:
        return str(make_header(decode_header(value)))
    except Exception:  # noqa: BLE001
        return str(value)


def _text_from(msg):
    """Prefer text/plain; fall back to text/html → text."""
    plain, html = None, None
    parts = msg.walk() if msg.is_multipart() else [msg]
    for part in parts:
        ctype = part.get_content_type()
        if part.get_content_disposition() == 'attachment':
            continue
        try:
            payload = part.get_payload(decode=True)
        except Exception:  # noqa: BLE001
            payload = None
        if payload is None:
            continue
        charset = part.get_content_charset() or 'utf-8'
        try:
            body = payload.decode(charset, errors='replace')
        except LookupError:
            body = payload.decode('utf-8', errors='replace')
        if ctype == 'text/plain' and plain is None:
            plain = body
        elif ctype == 'text/html' and html is None:
            html = body
    if plain is not None:
        return plain
    if html is not None:
        from app.email_service import _html_to_text
        return _html_to_text(html)
    return ''


def strip_quoted(text):
    """Keep only what the sender typed: cut at the first quoted-history marker
    and drop a trailing '-- ' signature. Capped for storage/prompt size."""
    lines = (text or '').replace('\r\n', '\n').split('\n')
    keep = []
    for ln in lines:
        s = ln.strip()
        if _SIG_CUT.match(s) or _QUOTE_CUT.match(s):
            break
        keep.append(ln)
    out = '\n'.join(keep).strip()
    return out[:SNIPPET_MAX]


def is_auto_reply(msg, subject=''):
    """Auto-responders / DSNs / list mail — never a human reply."""
    auto = (msg.get('Auto-Submitted') or '').strip().lower()
    if auto and auto != 'no':
        return True
    prec = (msg.get('Precedence') or '').strip().lower()
    if prec in ('bulk', 'junk', 'auto_reply', 'list'):
        return True
    for h in ('X-Autoreply', 'X-Autorespond', 'X-Auto-Response-Suppress'):
        if msg.get(h):
            return True
    if (msg.get_content_type() or '') == 'multipart/report':
        return True
    if _OOO_SUBJECT.search(subject or ''):
        return True
    return False


def parse_inbound(raw):
    """Parse raw RFC822 bytes → dict(from_email, from_name, subject,
    message_id, in_reply_to, date, text, is_auto, is_daemon)."""
    msg = email.message_from_bytes(raw)
    name, addr = email.utils.parseaddr(_dec(msg.get('From')))
    subject = _dec(msg.get('Subject'))
    date = None
    try:
        d = email.utils.parsedate_to_datetime(msg.get('Date'))
        if d is not None:
            date = d.astimezone(tz=None).replace(tzinfo=None) if d.tzinfo else d
            # normalize to naive UTC like the rest of the CRM
            if d.tzinfo:
                from datetime import timezone
                date = d.astimezone(timezone.utc).replace(tzinfo=None)
    except Exception:  # noqa: BLE001
        date = None
    return {
        'from_email': (addr or '').strip().lower(),
        'from_name': (name or '').strip()[:160],
        'subject': subject[:300],
        'message_id': (msg.get('Message-ID') or '').strip()[:255] or None,
        'in_reply_to': (msg.get('In-Reply-To') or '').strip()[:255] or None,
        'date': date,
        'text': strip_quoted(_text_from(msg)),
        'is_auto': is_auto_reply(msg, subject),
        'is_daemon': bool(_DAEMON.match(addr or '')),
        'is_ooo': bool(_OOO_SUBJECT.search(subject or '')) or
                  (msg.get('Auto-Submitted') or '').lower().startswith('auto-replied'),
    }


# ---------------------------------------------------------------------------
# Applying a reply to the CRM
# ---------------------------------------------------------------------------
def _own_domain():
    from flask import current_app
    addr = current_app.config.get('CRM_FROM_EMAIL') or 'james@yardharvest.app'
    return addr.split('@')[-1].lower()


# Addresses a person owns rather than an organization. A reply from one of
# these tells us nothing about which company the sender belongs to, so the
# domain-match tier below must never fire on them.
FREEMAIL_DOMAINS = frozenset("""
gmail.com googlemail.com yahoo.com ymail.com outlook.com hotmail.com live.com
msn.com icloud.com me.com mac.com aol.com protonmail.com proton.me pm.me
gmx.com mail.com zoho.com fastmail.com comcast.net att.net verizon.net
sbcglobal.net cox.net earthlink.net charter.net bellsouth.net roadrunner.com
""".split())

# How far back a "Re: <something we sent>" subject is still evidence.
SUBJECT_MATCH_DAYS = 30


def _domain_of(addr):
    return (addr or '').rsplit('@', 1)[-1].strip().lower()


def _match_contact(addr):
    """The address we mailed replied. The common case, and the only tier that
    needs no corroboration."""
    if not addr:
        return None
    return (Contact.query.filter(func.lower(Contact.email) == addr)
            .order_by(Contact.last_contacted_at.desc().nullslast(), Contact.id.desc())
            .first())


def _match_by_thread(parsed):
    """Match on a Message-ID we generated (autonomy.execute_action stores it).

    This is the tier that recovers the reply we were losing: we mail
    info@garden.org, the coordinator answers from her own address, and the
    only thing connecting the two is the In-Reply-To header pointing at our
    send. Exact id, so there is nothing to be wrong about."""
    ids = []
    for header in ('in_reply_to', 'references'):
        raw = parsed.get(header) or ''
        ids += re.findall(r'<[^<>@\s]+@[^<>\s]+>', raw)
    for mid in ids[:10]:
        action = (CrmAgentAction.query
                  .filter(CrmAgentAction.contact_id.isnot(None),
                          CrmAgentAction.payload_json.like(f'%{mid}%'))
                  .order_by(CrmAgentAction.id.desc()).first())
        if action and action.contact_id:
            contact = db.session.get(Contact, action.contact_id)
            if contact:
                return contact, f'threaded to our message {mid}'
    return None, None


def _looks_like_a_reply_to_us(parsed):
    """Corroboration for an address we have never mailed.

    Only two things count: the subject is a reply to a subject we actually
    sent recently, or the sender's domain belongs to a company in the CRM and
    is not a freemail host. Everything else stays skipped — the mailbox may
    also receive Stripe, GitHub and vendor mail, and a needs-you queue full of
    invoices is a queue nobody reads."""
    subject = (parsed.get('subject') or '').strip()
    stripped = re.sub(r'^\s*(re|fwd?|aw|sv)\s*:\s*', '', subject, flags=re.I).strip()
    if stripped and re.match(r'^\s*(re|fwd?)\s*:', subject, re.I):
        cutoff = _utcnow() - timedelta(days=SUBJECT_MATCH_DAYS)
        sent = (Note.query.filter(Note.content.like('[Email %'),
                                  Note.created_at >= cutoff)
                .order_by(Note.created_at.desc()).limit(300).all())
        for note in sent:
            first = (note.content or '').partition(chr(10))[0]
            subj = re.sub(r'^\[[^\]]*\]\s*', '', first).strip()
            if subj and subj.lower() == stripped.lower():
                return f'subject replies to "{subj[:60]}", which we sent'

    domain = _domain_of(parsed.get('from_email'))
    if domain and domain not in FREEMAIL_DOMAINS:
        company = (Company.query
                   .filter(Company.website.ilike(f'%{domain}%')).first())
        if company:
            return f'sender is at {domain}, the domain for {company.name}'
    return None


def _last_sent(contact):
    n = (Note.query.filter_by(contact_id=contact.id)
         .filter(Note.content.like('[Email %')).order_by(Note.created_at.desc()).first())
    if not n:
        return '', ''
    first, _, rest = (n.content or '').partition('\n')
    subj = re.sub(r'^\[[^\]]*\]\s*', '', first).strip()
    body = re.sub(r'<[^>]+>', ' ', rest or '')
    return subj[:200], re.sub(r'\s+', ' ', body).strip()[:400]


def _surface_unmatched(parsed, uid, uidvalidity, why, summary):
    """Put a reply we cannot attribute in front of a human, once.

    Nothing is sent and no lead is created — the operator decides whether this
    is a person worth adding. Stored as a contact-less CrmInboundReply so it
    shows in the needs-you queue and the digest alongside real replies."""
    mid = parsed.get('message_id') or f'uid:{uidvalidity}:{uid}'
    if CrmInboundReply.query.filter_by(message_id=mid).first():
        return None
    addr = parsed.get('from_email') or ''
    row = CrmInboundReply(
        contact_id=None, from_email=addr, from_name=parsed.get('from_name'),
        subject=parsed.get('subject'), snippet=(parsed.get('text') or '')[:2000],
        message_id=mid, in_reply_to=parsed.get('in_reply_to'),
        imap_uidvalidity=uidvalidity, imap_uid=uid,
        classification='unmatched',
        summary=f'Looks like a reply to us — {why}. Not linked to any contact.',
        action_taken='Needs a human: attach to a contact, or add them as a lead',
        received_at=parsed.get('date'))
    db.session.add(row)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return None
    summary.setdefault('unmatched', []).append({'from': addr,
                                                'subject': parsed.get('subject') or '',
                                                'why': why})
    log.info('Surfaced unmatched reply from %s (%s)', addr, why)
    return 'Surfaced for review'


def handle_inbound(parsed, uid, uidvalidity, settings, summary):
    """Apply one parsed inbound message. Returns the action_taken string
    (or None when ignored). Commits its own work."""
    from app.crm import agent_service
    addr = parsed.get('from_email') or ''
    if not addr or parsed.get('is_daemon') or addr.endswith('@' + _own_domain()):
        return None

    # Tier 1: the address we mailed. Tier 2: a Message-ID we generated, which
    # is how a coordinator replying from her own address to our info@ mail
    # still lands on the right contact.
    contact = _match_contact(addr)
    matched_via = 'sender address' if contact else None
    if not contact:
        contact, matched_via = _match_by_thread(parsed)
    if not contact:
        # Nobody we know. Only surface it if it actually looks like a reply to
        # us; the rest is vendor mail and must stay out of the queue.
        why = _looks_like_a_reply_to_us(parsed)
        if why:
            _surface_unmatched(parsed, uid, uidvalidity, why, summary)
        return None
    mid = parsed.get('message_id') or f'uid:{uidvalidity}:{uid}'
    if CrmInboundReply.query.filter_by(message_id=mid).first():
        return None
    text = parsed.get('text') or ''
    subject = parsed.get('subject') or ''
    if matched_via and matched_via != 'sender address':
        log_activity('email', f'Reply from {addr} — {matched_via}',
                     contact_id=contact.id, company_id=contact.company_id)

    # ---- classify: deterministic first, model second ----
    usage = {}
    if parsed.get('is_auto') or parsed.get('is_ooo'):
        cls = {'classification': 'out_of_office', 'summary': 'Automatic reply / out of office.',
               'suggested_next_step': 'Snooze a week.'}
    else:
        try:
            cls, usage = agent_service.classify_reply(text, subject=subject)
        except agent_service.AgentError as e:
            log.warning('Reply classification failed for %s: %s', addr, e)
            cls = {'classification': 'other', 'summary': 'Could not classify automatically.',
                   'suggested_next_step': 'Read and reply by hand.'}
    label = cls.get('classification') or 'other'

    row = CrmInboundReply(
        contact_id=contact.id, from_email=addr, from_name=parsed.get('from_name'),
        subject=subject[:300], snippet=text[:SNIPPET_MAX], message_id=mid,
        in_reply_to=parsed.get('in_reply_to'), imap_uidvalidity=uidvalidity, imap_uid=uid,
        classification=label, summary=(cls.get('summary') or '')[:300],
        received_at=parsed.get('date'))
    db.session.add(row)
    try:
        db.session.flush()
    except IntegrityError:
        db.session.rollback()
        return None

    # ---- apply ----
    action = ''
    if label == 'unsubscribe':
        from app.models import EmailUnsubscribe
        if not EmailUnsubscribe.query.filter_by(email=addr).first():
            db.session.add(EmailUnsubscribe(email=addr, source='reply'))
        contact.email_opt_out = True
        contact.lead_status = 'Disqualified'
        contact.next_action_at = None
        contact.next_action_note = 'Unsubscribed by reply'
        A.cancel_pending_actions(contact.id, 'Superseded: lead unsubscribed by reply')
        log_activity('updated', 'Replied asking to stop — unsubscribed & disqualified',
                     contact_id=contact.id, company_id=contact.company_id)
        action = 'Unsubscribed, disqualified, pending outreach withdrawn'
    elif label == 'not_interested':
        contact.lead_status = 'Disqualified'
        contact.next_action_at = None
        contact.next_action_note = 'Declined by reply'
        A.cancel_pending_actions(contact.id, 'Superseded: lead declined by reply')
        log_activity('updated', f'Replied — not interested: {cls.get("summary") or ""}'[:400],
                     contact_id=contact.id, company_id=contact.company_id)
        action = 'Disqualified, pending outreach withdrawn'
    elif label == 'out_of_office':
        base = contact.next_action_at or _utcnow().date()
        contact.next_action_at = max(base, _utcnow().date() + timedelta(days=OOO_SNOOZE_DAYS))
        contact.next_action_note = 'Out of office — snoozed'
        A.cancel_pending_actions(contact.id, 'Superseded: out-of-office reply',
                                 types=('follow_up_email', 'scout'))
        log_activity('updated', 'Auto-reply / out of office — next touch pushed a week',
                     contact_id=contact.id, company_id=contact.company_id)
        action = f'Snoozed {OOO_SNOOZE_DAYS} days'
    else:   # interested / no_budget / other
        # no_budget belongs here, not with the declines. Money being the only
        # obstacle is not a rejection when there is a free plan — it is the one
        # objection we can answer today, so it stays Engaged and gets a draft.
        A.apply_reply(contact, note=f'Lead replied ({label}) — marked Engaged')
        db.session.add(Note(contact_id=contact.id,
                            content=f'[Reply received] {subject}\n\n{text[:1500]}'))
        if label == 'no_budget':
            contact.next_action_note = 'Cost is the obstacle — free plan offered'
            action = 'Marked Engaged (cost objection), pending outreach withdrawn'
        else:
            action = 'Marked Engaged, pending outreach withdrawn'
        # Draft a response for the operator to approve (auto_replies stays a
        # policy flag; default off — a human answers a human).
        try:
            co = contact.company
            last_subj, last_snip = _last_sent(contact)
            draft, du = agent_service.draft_reply({
                'name': contact.name, 'company': co.name if co else None,
                'city': co.city if co else None, 'state': co.state if co else None,
                'org_type': co.org_type if co else None,
                'inbound_subject': subject, 'inbound_text': text,
                'classification': label, 'last_sent_subject': last_subj,
                'last_sent_snippet': last_snip})
            for k, v in (du or {}).items():
                usage[k] = int(usage.get(k) or 0) + int(v or 0)
            a = CrmAgentAction(
                action_type='reply_email', status='pending',
                contact_id=contact.id, company_id=contact.company_id,
                title=f'Reply to {contact.name}'[:200],
                rationale=(cls.get('summary') or 'They replied.')[:400],
                payload_json=__import__('json').dumps({
                    'subject': draft.get('subject', ''), 'body': draft.get('body', ''),
                    'in_reply_to': mid if mid.startswith('<') else None,
                    'inbound_snippet': text[:800], 'classification': label}),
                created_by_id=settings.operator_user_id)
            db.session.add(a)
            db.session.flush()
            row.agent_action_id = a.id
            if settings.auto_replies:
                # Same quality gate as outbound: a reply that fails it waits
                # for a human rather than going out unreviewed.
                bad = agent_service.lint_email(draft.get('subject', ''), draft.get('body', ''),
                                               contact_name=contact.name)
                db.session.commit()
                if bad:
                    action += f'; reply held for review ({bad[0]})'
                elif A.claim_action(a.id):
                    A.execute_action(a, form=None, actor_id=settings.operator_user_id, auto=True)
                    action += '; reply auto-sent'
            else:
                action += '; reply drafted for your approval'
        except agent_service.AgentError as e:
            log.warning('Reply drafting failed for %s: %s', addr, e)
            action += '; reply drafting failed (write it by hand)'
    row.action_taken = action[:300]
    db.session.commit()

    entry = {'contact': contact.name, 'company': contact.company.name if contact.company else '',
             'classification': label, 'summary': cls.get('summary') or '', 'action': action,
             'usage': usage}
    summary.setdefault('handled', []).append(entry)
    if (settings.notify_on_interested and not settings.auto_replies
            and label in ('interested', 'no_budget')):
        _notify_interested(settings, contact, subject, text, cls.get('summary') or '')
    return action


def _notify_interested(settings, contact, subject, text, summary_txt):
    from app.crm.autonomy_cycle import _notice, _esc
    from flask import current_app
    base = (current_app.config.get('SITE_URL') or 'https://www.yardharvest.app').rstrip('/')
    co = contact.company.name if contact.company else ''
    _notice(settings, f'💬 {contact.name} replied — interested',
            f"<p><strong>{_esc(contact.name)}</strong>{(' at ' + _esc(co)) if co else ''} replied to your "
            f"outreach.</p><p><em>{_esc(summary_txt)}</em></p>"
            f"<blockquote style='border-left:3px solid #e3ff8f;padding-left:10px;color:#444'>"
            f"{_esc(text[:800])}</blockquote>"
            f"<p>A reply is drafted and waiting for your approval: "
            f"<a href='{base}/crm/agent'>open the agent console →</a></p>")


# ---------------------------------------------------------------------------
# The poll
# ---------------------------------------------------------------------------
def _claim_poll(settings, now):
    stmt = (db.update(AgentSettings).where(AgentSettings.id == settings.id)
            .where(db.or_(AgentSettings.poll_lock_until.is_(None),
                          AgentSettings.poll_lock_until < now))
            .values(poll_lock_until=now + timedelta(minutes=POLL_LEASE_MINUTES)))
    res = db.session.execute(stmt.execution_options(synchronize_session=False))
    db.session.commit()
    return res.rowcount == 1


def poll_replies(*, fetcher=None, now=None):
    """Poll the reply mailbox once. Returns {'fetched','matched','skipped',
    'errors','handled'}. Never raises for IMAP problems — records them on
    settings.imap_last_error (the cycle gate reads that) and returns."""
    from app.crm.autonomy_cycle import get_settings, imap_configured
    settings = get_settings()
    now = now or _utcnow()
    result = {'fetched': 0, 'matched': 0, 'skipped': 0, 'errors': [], 'handled': []}
    if fetcher is None:
        if not imap_configured():
            result['errors'].append('IMAP not configured')
            return result
        fetcher = _fetcher_from_config()
    if not _claim_poll(settings, now):
        result['errors'].append('another poll holds the lease')
        return result
    ok = False
    try:
        fetcher.open()
        validity, uidnext = fetcher.state()
        db.session.refresh(settings)
        if settings.imap_uidvalidity != validity or settings.imap_last_uid is None:
            # First poll, or the mailbox was rebuilt: baseline at "now" so a
            # historic inbox is never replayed into the CRM.
            settings.imap_uidvalidity = validity
            settings.imap_last_uid = max(0, int(uidnext) - 1)
            settings.imap_last_error = None
            db.session.commit()
            ok = True
            result['baseline'] = settings.imap_last_uid
            return result
        for uid, raw in fetcher.fetch_after(settings.imap_last_uid, POLL_BATCH):
            result['fetched'] += 1
            try:
                parsed = parse_inbound(raw)
                taken = handle_inbound(parsed, uid, validity, settings, result)
                if taken:
                    result['matched'] += 1
                else:
                    result['skipped'] += 1
            except Exception as e:  # noqa: BLE001
                db.session.rollback()
                log.exception('Inbound message uid=%s failed', uid)
                result['errors'].append(f'uid {uid}: {e}')
            # advance per message so partial progress survives a crash
            settings.imap_last_uid = uid
            db.session.commit()
        settings.imap_last_error = None
        ok = True
    except Exception as e:  # noqa: BLE001
        db.session.rollback()
        log.warning('Reply poll failed: %s', e)
        # Store the actionable explanation, not the raw socket text — this is
        # what the console shows and what the 24h breaker reports.
        detail = explain_imap_error(e, fetcher)
        result['errors'].append(detail[:400])
        settings.imap_last_error = detail[:400]
    finally:
        try:
            fetcher.close()
        except Exception:  # noqa: BLE001
            pass
        settings.poll_lock_until = None
        settings.last_reply_poll_at = now
        if ok:
            settings.last_reply_poll_ok_at = now
        db.session.commit()
    return result


class _HostInfo:
    """Whatever the caller passed, expose host/port/user/mailbox safely."""

    def __init__(self, f):
        self.host = getattr(f, 'host', None) or 'the mail server'
        self.port = getattr(f, 'port', None) or 993
        self.user = getattr(f, 'user', None) or 'the mailbox user'
        self.mailbox = getattr(f, 'mailbox', None) or 'INBOX'


def explain_imap_error(exc, fetcher):
    """Turn a raw IMAP/socket exception into something an operator can act on.
    The raw text ("gaierror: [Errno -2] Name or service not known") reads like
    a broken integration when it's almost always a typo in one env var."""
    import socket
    fetcher = _HostInfo(fetcher)
    msg = str(exc)
    if isinstance(exc, socket.gaierror) or 'Name or service not known' in msg \
            or 'nodename nor servname' in msg or 'getaddrinfo' in msg:
        return (f'Could not find the mail server “{fetcher.host}”. Check '
                f'CRM_IMAP_HOST in Render — it must be a bare hostname with no '
                f'scheme or port (Zoho is imap.zoho.com, or imappro.zoho.com '
                f'for paid organization accounts). Unset it to use the default.')
    if isinstance(exc, (socket.timeout, TimeoutError)) or 'timed out' in msg.lower():
        return (f'Timed out reaching {fetcher.host}:{fetcher.port}. Check the host '
                f'and that IMAP is enabled on the mailbox.')
    if 'yet to enable IMAP' in msg or 'IMAP is not enabled' in msg \
            or ('[ALERT]' in msg and 'IMAP' in msg):
        # Zoho disables IMAP for every org user by default — this is the
        # expected first-run error, and it's fixed in Zoho, not here.
        return ('IMAP is switched off for this mailbox in Zoho. As the admin: '
                'Admin Console (mailadmin.zoho.com) → Users → '
                f'{fetcher.user} → Mailbox Settings → Mailbox Actions → turn on '
                '“IMAP access”. Then in the mailbox itself: Settings → Mail '
                'Accounts → IMAP Access → Enable. Retry after a minute.')
    if 'AUTHENTICATIONFAILED' in msg or 'Invalid credentials' in msg or 'LOGIN failed' in msg:
        return (f'{fetcher.host} rejected the login for {fetcher.user}. Zoho needs an '
                f'application-specific password (not your account password), and IMAP '
                f'Access must be enabled for that mailbox.')
    if 'certificate' in msg.lower() or 'SSL' in msg:
        return f'TLS problem talking to {fetcher.host}: {msg[:160]}'
    if 'Could not open mailbox' in msg:
        return f'Connected to {fetcher.host}, but the mailbox “{fetcher.mailbox}” does not exist.'
    return f'{fetcher.host}: {exc.__class__.__name__} — {msg[:200]}'


def test_imap_connection():
    """Ops helper for the console's 'Test connection' button: (ok, message)."""
    from app.crm.autonomy_cycle import imap_configured
    if not imap_configured():
        return False, ('Reply capture isn’t configured yet — set CRM_IMAP_PASSWORD '
                       '(an app-specific password) in Render.')
    f = _fetcher_from_config()
    try:
        f.open()
        validity, uidnext = f.state()
        return True, (f'Connected to {f.host} as {f.user}; mailbox {f.mailbox} '
                      f'(UIDVALIDITY {validity}, next UID {uidnext}).')
    except Exception as e:  # noqa: BLE001
        return False, explain_imap_error(e, f)
    finally:
        f.close()
