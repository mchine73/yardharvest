"""Reply capture: IMAP poll with a fake fetcher, parsing, classification
routing, lifecycle effects, pending-proposal withdrawal, dedupe, and the
reply_email approve path."""
from datetime import date, timedelta
from email.message import EmailMessage

import pytest

from app import db as _db
from app.crm import agent_service
import app.crm.autonomy as autonomy
from app.crm.models import (AgentSettings, Company, Contact, CrmAgentAction,
                            CrmInboundReply, Note, _utcnow)


def _register_first_admin(client, username='replyadmin', password='secret123'):
    return client.post('/crm/register',
                       data={'username': username, 'password': password, 'confirm': password},
                       follow_redirects=True)


def _lead(app, name, email, *, status='Working', followup=1, pending=True):
    with app.app_context():
        co = Company(name=f'{name} Org', city='Lincoln', state='NE', org_type='Independent')
        _db.session.add(co)
        _db.session.flush()
        c = Contact(name=name, email=email, company_id=co.id, lead_status=status,
                    followup_count=followup, next_action_at=date.today() + timedelta(days=4))
        _db.session.add(c)
        _db.session.flush()
        _db.session.add(Note(contact_id=c.id,
                             content=f'[Email sent to {email}] Quick question about plots\n\n<p>Hi {name}</p>'))
        if pending:
            _db.session.add(CrmAgentAction(action_type='follow_up_email', status='pending',
                                           contact_id=c.id, title='Follow up',
                                           payload_json='{"subject":"Hi","body":"Hello"}'))
        _db.session.commit()
        return c.id


def _raw(from_addr, subject, body, *, from_name='Pat', headers=None, message_id=None):
    m = EmailMessage()
    m['From'] = f'{from_name} <{from_addr}>'
    m['To'] = 'james@yardharvest.app'
    m['Subject'] = subject
    m['Message-ID'] = message_id or f'<{abs(hash((from_addr, subject, body)))}@example.com>'
    m['Date'] = 'Tue, 14 Jul 2026 10:00:00 -0500'
    for k, v in (headers or {}).items():
        m[k] = v
    m.set_content(body)
    return m.as_bytes()


class FakeFetcher:
    """Same 4-method surface as ImapFetcher, backed by an in-memory list."""

    def __init__(self, messages, *, uidvalidity=100, fail_open=None):
        self.messages = list(messages)          # [(uid, raw)]
        self.uidvalidity = uidvalidity
        self.fail_open = fail_open
        self.opened = self.closed = False

    def open(self):
        if self.fail_open:
            raise self.fail_open
        self.opened = True

    def state(self):
        nxt = (max(u for u, _ in self.messages) + 1) if self.messages else 1
        return self.uidvalidity, nxt

    def fetch_after(self, last_uid, limit=200):
        return [(u, r) for u, r in self.messages if u > last_uid][:limit]

    def close(self):
        self.closed = True


@pytest.fixture
def ready(app, client, monkeypatch):
    _register_first_admin(client)
    notices, sends = [], []
    monkeypatch.setattr(agent_service, 'is_configured', lambda: True)
    monkeypatch.setattr(autonomy, 'email_ready', lambda: True)
    monkeypatch.setattr(autonomy, 'smtp_send',
                        lambda to, subj, body, bcc=True, headers=None:
                        sends.append({'to': to, 'subject': subj, 'headers': headers}) or True)
    import app.email_service as es
    monkeypatch.setattr(es, 'send_email',
                        lambda to, subject, html, **k: notices.append({'to': to, 'subject': subject}) or True)
    classes = {}

    def fake_classify(text, *, subject='', model=None):
        # test controls the answer via the subject; deterministic unsubscribe still runs first
        if autonomy_replies_unsub(text, subject):
            return ({'classification': 'unsubscribe', 'summary': 'stop', 'suggested_next_step': ''}, {})
        label = classes.get(subject, 'interested')
        return ({'classification': label, 'summary': f'{label} summary',
                 'suggested_next_step': 'x'}, {'input_tokens': 3, 'output_tokens': 3})
    monkeypatch.setattr(agent_service, 'classify_reply', fake_classify)
    monkeypatch.setattr(agent_service, 'draft_reply',
                        lambda ctx, sender_name='', model=None:
                        ({'subject': f"Re: {ctx['inbound_subject']}", 'body': '<p>Thanks!</p>'},
                         {'input_tokens': 2, 'output_tokens': 2}))
    with app.app_context():
        app.config['CRM_IMAP_PASSWORD'] = 'x'
        # Explicit user: don't depend on CRM_FROM_EMAIL surviving other modules.
        app.config['CRM_IMAP_USER'] = 'james@yardharvest.app'
        s = AgentSettings.get()
        s.imap_uidvalidity = 100
        s.imap_last_uid = 0
        _db.session.commit()
    yield {'notices': notices, 'sends': sends, 'classes': classes}
    with app.app_context():
        app.config.pop('CRM_IMAP_PASSWORD', None)
        app.config.pop('CRM_IMAP_USER', None)


def autonomy_replies_unsub(text, subject):
    return bool(agent_service._UNSUB_RE.search(f'{subject}\n{text}'))


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------
def test_parse_inbound_strips_quotes_and_detects_auto():
    raw = _raw('pat@example.com', 'Re: plots', 'Sounds good, send details.\n\nOn Tue James wrote:\n> hi')
    p = autonomy.parse_inbound(raw)
    assert p['from_email'] == 'pat@example.com' and p['text'] == 'Sounds good, send details.'
    assert p['is_auto'] is False and p['message_id'].startswith('<')
    auto = _raw('pat@example.com', 'Automatic reply: plots', 'I am away', headers={'Auto-Submitted': 'auto-replied'})
    assert autonomy.parse_inbound(auto)['is_auto'] is True
    dsn = _raw('MAILER-DAEMON@mx.example.com', 'Undelivered', 'bounce')
    assert autonomy.parse_inbound(dsn)['is_daemon'] is True


# ---------------------------------------------------------------------------
# First poll baseline + validity reset
# ---------------------------------------------------------------------------
def test_first_poll_baselines_without_replaying_history(app, ready):
    cid = _lead(app, 'Hist', 'hist@example.com')
    with app.app_context():
        s = AgentSettings.get()
        s.imap_last_uid = None          # never polled
        _db.session.commit()
        f = FakeFetcher([(5, _raw('hist@example.com', 'old', 'ancient reply'))], uidvalidity=777)
        r = autonomy.poll_replies(fetcher=f)
        assert r['fetched'] == 0 and r.get('baseline') == 5
        s = AgentSettings.get()
        assert s.imap_uidvalidity == 777 and s.imap_last_uid == 5 and s.last_reply_poll_ok_at
        assert CrmInboundReply.query.count() == 0
        # a NEW message after the baseline is processed on the next poll
        f.messages.append((6, _raw('hist@example.com', 'new', 'Interested, tell me more')))
        r2 = autonomy.poll_replies(fetcher=f, now=_utcnow() + timedelta(minutes=20))
        assert r2['matched'] == 1
        assert _db.session.get(Contact, cid).lead_status == 'Engaged'


# ---------------------------------------------------------------------------
# Routing matrix
# ---------------------------------------------------------------------------
def test_interested_reply_engages_cancels_pending_and_drafts_reply(app, ready):
    cid = _lead(app, 'Pat', 'pat@example.com')
    with app.app_context():
        f = FakeFetcher([(1, _raw('pat@example.com', 'Re: Quick question', 'Yes, tell me more!'))])
        r = autonomy.poll_replies(fetcher=f)
        assert r['matched'] == 1 and r['errors'] == []
        c = _db.session.get(Contact, cid)
        assert c.lead_status == 'Engaged' and c.followup_count == 0
        acts = CrmAgentAction.query.filter_by(contact_id=cid).order_by(CrmAgentAction.id).all()
        assert acts[0].status == 'rejected' and 'replied' in acts[0].result
        assert acts[1].action_type == 'reply_email' and acts[1].status == 'pending'
        assert acts[1].payload['subject'] == 'Re: Re: Quick question'
        assert acts[1].payload['in_reply_to'].startswith('<')
        row = CrmInboundReply.query.one()
        assert row.classification == 'interested' and row.agent_action_id == acts[1].id
        # the operator was pinged about an interested reply
        assert any('interested' in n['subject'] for n in ready['notices'])
        # and the digest-style summary was recorded on the poll result
        assert r['handled'][0]['contact'] == 'Pat'


def test_not_interested_disqualifies(app, ready):
    cid = _lead(app, 'Nope', 'nope@example.com')
    ready['classes']['Re: no thanks'] = 'not_interested'
    with app.app_context():
        autonomy.poll_replies(fetcher=FakeFetcher([(1, _raw('nope@example.com', 'Re: no thanks', 'We use another tool.'))]))
        c = _db.session.get(Contact, cid)
        assert c.lead_status == 'Disqualified' and c.next_action_at is None
        assert CrmAgentAction.query.filter_by(contact_id=cid, status='pending').count() == 0
        assert CrmAgentAction.query.filter_by(contact_id=cid, action_type='reply_email').count() == 0


def test_unsubscribe_reply_suppresses(app, ready):
    cid = _lead(app, 'Stop', 'stop@example.com')
    from app.models import EmailUnsubscribe
    with app.app_context():
        autonomy.poll_replies(fetcher=FakeFetcher([(1, _raw('stop@example.com', 'Re: hi', 'Please remove me from your list.'))]))
        c = _db.session.get(Contact, cid)
        assert c.email_opt_out and c.lead_status == 'Disqualified'
        assert EmailUnsubscribe.query.filter_by(email='stop@example.com').one().source == 'reply'
        assert CrmAgentAction.query.filter_by(contact_id=cid, status='pending').count() == 0


def test_out_of_office_snoozes_without_engaging(app, ready):
    cid = _lead(app, 'Away', 'away@example.com')
    with app.app_context():
        raw = _raw('away@example.com', 'Automatic reply: Quick question', 'I am out until Monday.',
                   headers={'Auto-Submitted': 'auto-replied'})
        autonomy.poll_replies(fetcher=FakeFetcher([(1, raw)]))
        c = _db.session.get(Contact, cid)
        assert c.lead_status == 'Working'                     # NOT engaged
        assert c.next_action_at >= date.today() + timedelta(days=7)
        assert CrmAgentAction.query.filter_by(contact_id=cid, status='pending').count() == 0
        assert CrmInboundReply.query.one().classification == 'out_of_office'


def test_own_domain_daemon_and_unknown_senders_are_ignored(app, ready):
    _lead(app, 'Known', 'known@example.com')
    with app.app_context():
        msgs = [(1, _raw('james@yardharvest.app', 'BCC copy', 'our own outbound copy')),
                (2, _raw('MAILER-DAEMON@mx.example.com', 'Undelivered', 'bounce')),
                (3, _raw('stranger@example.com', 'hello', 'not a lead'))]
        r = autonomy.poll_replies(fetcher=FakeFetcher(msgs))
        assert r['fetched'] == 3 and r['matched'] == 0 and r['skipped'] == 3
        assert CrmInboundReply.query.count() == 0
        assert AgentSettings.get().imap_last_uid == 3      # progress still advances


def test_duplicate_message_id_processed_once(app, ready):
    cid = _lead(app, 'Dup', 'dup@example.com')
    with app.app_context():
        raw = _raw('dup@example.com', 'Re: hi', 'Interested!', message_id='<same@example.com>')
        autonomy.poll_replies(fetcher=FakeFetcher([(1, raw)]))
        # mailbox rebuilt: same message reappears under a new UID/validity
        s = AgentSettings.get()
        s.imap_uidvalidity = 100
        s.imap_last_uid = 1
        _db.session.commit()
        r = autonomy.poll_replies(fetcher=FakeFetcher([(2, raw)]), now=_utcnow() + timedelta(minutes=20))
        assert r['matched'] == 0 and CrmInboundReply.query.filter_by(contact_id=cid).count() == 1
        assert CrmAgentAction.query.filter_by(contact_id=cid, action_type='reply_email').count() == 1


def test_imap_failure_records_error_and_keeps_ok_stamp(app, ready):
    with app.app_context():
        s = AgentSettings.get()
        s.last_reply_poll_ok_at = _utcnow() - timedelta(hours=2)
        _db.session.commit()
        before = s.last_reply_poll_ok_at
        r = autonomy.poll_replies(fetcher=FakeFetcher([], fail_open=RuntimeError('AUTHENTICATIONFAILED')))
        assert r['errors'] and 'AUTHENTICATIONFAILED' in r['errors'][0]
        s = AgentSettings.get()
        assert 'AUTHENTICATIONFAILED' in s.imap_last_error
        assert s.last_reply_poll_ok_at == before          # not refreshed on failure
        assert s.poll_lock_until is None                  # lease released


def test_poll_lease_prevents_overlap(app, ready):
    with app.app_context():
        s = AgentSettings.get()
        s.poll_lock_until = _utcnow() + timedelta(minutes=5)
        _db.session.commit()
        r = autonomy.poll_replies(fetcher=FakeFetcher([]))
        assert r['errors'] == ['another poll holds the lease']


# ---------------------------------------------------------------------------
# reply_email execution + maybe_tick
# ---------------------------------------------------------------------------
def test_approving_reply_email_threads_and_keeps_engaged(client, app, ready):
    cid = _lead(app, 'Pat', 'pat@example.com')
    with app.app_context():
        autonomy.poll_replies(fetcher=FakeFetcher([(1, _raw('pat@example.com', 'Re: Q', 'Yes please',
                                                            message_id='<orig@example.com>'))]))
        a = CrmAgentAction.query.filter_by(contact_id=cid, action_type='reply_email').one()
        aid = a.id
    r = client.post(f'/crm/agent/actions/{aid}/approve',
                    data={'subject': 'Re: Q', 'body': '<p>Great — here you go.</p>'},
                    follow_redirects=True)
    assert b'Email sent' in r.data
    assert ready['sends'][-1]['headers']['In-Reply-To'] == '<orig@example.com>'
    with app.app_context():
        c = _db.session.get(Contact, cid)
        assert c.lead_status == 'Engaged' and c.followup_count == 0   # cadence untouched
        assert _db.session.get(CrmAgentAction, aid).status == 'executed'


def test_maybe_tick_polls_and_never_raises(app, ready, monkeypatch):
    calls = []
    monkeypatch.setattr(autonomy, 'poll_replies', lambda **k: calls.append('poll') or {'fetched': 0})
    monkeypatch.setattr(autonomy, 'run_daily_cycle', lambda **k: (_ for _ in ()).throw(RuntimeError('boom')))
    with app.app_context():
        out = autonomy.maybe_tick()
        assert calls == ['poll'] and out['errors'] and 'boom' in out['errors'][0]
