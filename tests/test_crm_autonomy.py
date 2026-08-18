"""Autonomous BDR cycle: gates, day-claim, budget, exclusions, breakers,
cold promotion, touch-aware context, digest. All AI + mail is faked."""
import json
from datetime import date, datetime, timedelta

import pytest

from app import db as _db
from app.crm import agent_service
import app.crm.autonomy as autonomy
from app.crm.models import (AgentSettings, Company, Contact, CrmAgentAction, _utcnow,
                            CrmAgentRun, CrmInboundReply, CrmUser, Note)


# Tue 2026-07-14 15:00 UTC == 10:00 America/Chicago (CDT) — inside the window.
NOW = datetime(2026, 7, 14, 15, 0, 0)


def _register_first_admin(client, username='autoadmin', password='secret123'):
    return client.post('/crm/register',
                       data={'username': username, 'password': password, 'confirm': password},
                       follow_redirects=True)


def _lead(app, name, email, *, status='Working', followup=0, due=True, company=None,
          opt_out=False):
    # Each lead gets its own organization by default: the cycle deliberately
    # sends at most one email per org per day, so sharing one company would
    # silently cap every fixture at a single send.
    with app.app_context():
        company = company or f'{name} Garden'
        co = Company.query.filter_by(name=company).first()
        if not co:
            co = Company(name=company, city='Lincoln', state='NE', org_type='Independent')
            _db.session.add(co)
            _db.session.flush()
        c = Contact(name=name, email=email, company_id=co.id, lead_status=status,
                    followup_count=followup, email_opt_out=opt_out,
                    next_action_at=date.today() if due else None)
        _db.session.add(c)
        _db.session.commit()
        return c.id


def _cold(app, name, email, company='Cold Org'):
    """Never-contacted New lead with an address (the scout pool)."""
    with app.app_context():
        co = Company(name=company, city='Omaha', state='NE', org_type='City-Sponsored')
        _db.session.add(co)
        _db.session.flush()
        c = Contact(name=name, email=email, company_id=co.id, lead_status='New')
        _db.session.add(c)
        _db.session.commit()
        return c.id


@pytest.fixture
def ready(app, client, monkeypatch):
    """Everything green: autonomy on, AI + mail 'configured', mailing address
    set, reply capture satisfied, fake drafter/ranker, captured sends + notices."""
    _register_first_admin(client)
    sends, notices = [], []
    monkeypatch.setattr(agent_service, 'is_configured', lambda: True)
    monkeypatch.setattr(autonomy, 'email_ready', lambda: True)
    monkeypatch.setattr(autonomy, 'smtp_send',
                        lambda to, subj, body, bcc=True, headers=None:
                        sends.append({'to': to, 'subject': subj, 'headers': headers}) or True)
    import app.email_service as es
    monkeypatch.setattr(es, 'send_email',
                        lambda to, subject, html, **k: notices.append({'to': to, 'subject': subject,
                                                                        'html': html}) or True)

    def fake_followups(leads, *, sender_name='', model=None):
        fake_followups.calls.append(leads)
        return ([{'lead_id': ld['lead_id'], 'title': f"Follow up {ld['name']}",
                  'rationale': 'due', 'subject': f"Hi {ld['name']} t{ld.get('touch_number')}",
                  'body': '<p>Hello {{first_name}}</p>'} for ld in leads], {'input_tokens': 10,
                                                                             'output_tokens': 20})
    fake_followups.calls = []
    monkeypatch.setattr(agent_service, 'draft_followups', fake_followups)

    def fake_scout(leads, *, limit=8, model=None):
        return ([{'lead_id': ld['lead_id'], 'title': f"Prospect {ld['company']}",
                  'rationale': 'fit', 'angle': 'parks timing'} for ld in leads[:limit]],
                {'input_tokens': 5, 'output_tokens': 5})
    monkeypatch.setattr(agent_service, 'scout_leads', fake_scout)

    with app.app_context():
        app.config['CRM_MAILING_ADDRESS'] = '123 Garden St, Omaha NE'
        app.config['CRM_IMAP_PASSWORD'] = 'app-pass'
        app.config['CRM_IMAP_USER'] = 'james@yardharvest.app'
        s = AgentSettings.get()
        s.autonomy_enabled = True
        s.daily_send_cap = 15
        s.last_reply_poll_ok_at = _utcnow()
        _db.session.commit()
    yield {'sends': sends, 'notices': notices, 'followups': fake_followups}
    with app.app_context():
        app.config.pop('CRM_MAILING_ADDRESS', None)
        app.config.pop('CRM_IMAP_PASSWORD', None)
        app.config.pop('CRM_IMAP_USER', None)


# ---------------------------------------------------------------------------
# Gates
# ---------------------------------------------------------------------------
def test_cycle_gated_when_disabled(app, ready):
    with app.app_context():
        s = AgentSettings.get()
        s.autonomy_enabled = False
        _db.session.commit()
        assert autonomy.run_daily_cycle(now=NOW) is None
        gates = autonomy.cycle_gates(s, autonomy.local_now(s, NOW))
        assert any('switched off' in g for g in gates)


def test_cycle_gates_weekend_and_hour(app, ready):
    with app.app_context():
        s = AgentSettings.get()
        sat = datetime(2026, 7, 18, 15, 0)            # Saturday
        assert any('Weekend' in g for g in autonomy.cycle_gates(s, autonomy.local_now(s, sat)))
        early = datetime(2026, 7, 14, 12, 0)          # 07:00 CDT
        assert any('send hour' in g for g in autonomy.cycle_gates(s, autonomy.local_now(s, early)))
        # force ignores the window but not the switches
        assert autonomy.cycle_gates(s, autonomy.local_now(s, early), force=True) == []


def test_env_kill_switch(app, ready, monkeypatch):
    monkeypatch.setenv('CRM_AGENT_AUTONOMY', 'off')
    with app.app_context():
        assert autonomy.run_daily_cycle(now=NOW) is None


def test_gate_requires_reply_capture_health(app, ready):
    with app.app_context():
        s = AgentSettings.get()
        s.last_reply_poll_ok_at = _utcnow() - timedelta(hours=30)
        s.imap_last_error = 'AUTHENTICATIONFAILED'
        _db.session.commit()
        gates = autonomy.cycle_gates(s, autonomy.local_now(s, NOW))
        assert any('Reply capture' in g and 'AUTHENTICATIONFAILED' in g for g in gates)
        assert autonomy.run_daily_cycle(now=NOW) is None


# ---------------------------------------------------------------------------
# Happy path + budget + claim
# ---------------------------------------------------------------------------
def test_cycle_sends_due_followups_and_digests(app, ready):
    ids = [_lead(app, f'Lead {i}', f'lead{i}@example.com') for i in range(3)]
    with app.app_context():
        summary = autonomy.run_daily_cycle(now=NOW, poll=False)
        assert summary is not None
        assert len(summary['sent']) == 3 and len(ready['sends']) == 3
        # actions are stamped auto, executed, and the cadence advanced
        acts = CrmAgentAction.query.filter(CrmAgentAction.contact_id.in_(ids)).all()
        assert len(acts) == 3 and all(a.status == 'executed' and a.auto_executed for a in acts)
        for cid in ids:
            c = _db.session.get(Contact, cid)
            assert c.followup_count == 1 and c.next_action_at == date.today() + timedelta(days=4)
        # List-Unsubscribe rode along on automated 1:1 mail
        assert all('List-Unsubscribe' in (s['headers'] or {}) for s in ready['sends'])
        # run ledger + digest
        run = CrmAgentRun.query.filter_by(kind='autonomous').first()
        assert run.status == 'done' and run.cost_usd > 0
        assert ready['notices'] and '3 sent' in ready['notices'][-1]['subject']
        s = AgentSettings.get()
        assert s.last_cycle_date == date(2026, 7, 14) and s.cycle_lock_until is None
        assert s.last_cycle_summary['sent'][0]['contact'] == 'Lead 0'


def test_daily_cap_and_day_claim(app, ready):
    for i in range(4):
        _lead(app, f'Lead {i}', f'cap{i}@example.com')
    with app.app_context():
        s = AgentSettings.get()
        s.daily_send_cap = 2
        _db.session.commit()
        first = autonomy.run_daily_cycle(now=NOW, poll=False)
        assert len(first['sent']) == 2
        # same local day: already claimed
        assert autonomy.run_daily_cycle(now=NOW + timedelta(minutes=15), poll=False) is None
        # forced re-run: allowed, but the budget is already spent (counted from rows)
        forced = autonomy.run_daily_cycle(now=NOW + timedelta(minutes=30), force=True, poll=False)
        assert forced is not None and forced['budget_start'] == 0 and forced['sent'] == []
        assert len(ready['sends']) == 2


# ---------------------------------------------------------------------------
# Exclusions
# ---------------------------------------------------------------------------
def test_cycle_excludes_engaged_optout_capped_pending_and_recent_repliers(app, ready):
    ok = _lead(app, 'Ada Fields', 'ok@example.com')
    engaged = _lead(app, 'Eve Marsh', 'eng@example.com', status='Engaged')
    optout = _lead(app, 'Otto Vance', 'opt@example.com', opt_out=True)
    capped = _lead(app, 'Cap Rowan', 'cap@example.com', followup=3)
    pending = _lead(app, 'Perry Dunn', 'pend@example.com')
    replied = _lead(app, 'Remy Blake', 'rep@example.com')
    with app.app_context():
        _db.session.add(CrmAgentAction(action_type='follow_up_email', status='pending',
                                       contact_id=pending, title='x', payload_json='{}'))
        _db.session.add(CrmInboundReply(contact_id=replied, from_email='rep@example.com',
                                        message_id='m1', classification='interested'))
        _db.session.commit()
        summary = autonomy.run_daily_cycle(now=NOW, poll=False)
        assert [x['contact'] for x in summary['sent']] == ['Ada Fields']
        assert summary['needs_human'] == 1     # the Engaged lead is flagged for a human
        for cid in (engaged, optout, capped, pending, replied):
            assert _db.session.get(Contact, cid).followup_count in (0, 3)


def test_suppressed_is_skipped_not_failed(app, ready):
    _lead(app, 'Sunny Park', 'supp@example.com')
    from app.models import EmailUnsubscribe
    with app.app_context():
        _db.session.add(EmailUnsubscribe(email='supp@example.com', source='self'))
        _db.session.commit()
        summary = autonomy.run_daily_cycle(now=NOW, poll=False)
        assert summary['sent'] == [] and summary['failed'] == [] and summary['breaker'] is None
        # the eligibility filter drops suppressed leads before drafting
        assert ready['followups'].calls == []


# ---------------------------------------------------------------------------
# Breakers
# ---------------------------------------------------------------------------
def test_consecutive_send_failures_trip_breaker(app, ready, monkeypatch):
    names = ['Fern Adams', 'Gus Iverson', 'Hana Ruiz', 'Ivan Poole', 'Jo Nakamura']
    for i, nm in enumerate(names):
        _lead(app, nm, f'f{i}@example.com')
    monkeypatch.setattr(autonomy, 'smtp_send', lambda *a, **k: False)   # provider rejects
    with app.app_context():
        summary = autonomy.run_daily_cycle(now=NOW, poll=False)
        assert summary['breaker'] and '3 consecutive' in summary['breaker']
        assert len(summary['failed']) == 3 and summary['sent'] == []
        s = AgentSettings.get()
        assert s.paused_reason and s.paused_at
        # alert + digest both went to the operator, digest flagged
        subjects = [n['subject'] for n in ready['notices']]
        assert any('paused itself' in x for x in subjects)
        assert subjects[-1].startswith('⚠️')
        # failed sends did NOT advance the cadence
        assert all(c.followup_count == 0 for c in Contact.query.all())
        # and the pause gates the next cycle
        assert autonomy.run_daily_cycle(now=NOW + timedelta(days=1), poll=False) is None


def test_hard_bounce_breaker(app, ready):
    _lead(app, 'Bea Lowell', 'b@example.com')
    from app.crm.models import CrmEmailEvent
    with app.app_context():
        for _ in range(3):
            _db.session.add(CrmEmailEvent(email='x@example.com', event_type='hard'))
        _db.session.commit()
        summary = autonomy.run_daily_cycle(now=NOW, poll=False)
        assert 'hard bounces' in summary['breaker'] and summary['sent'] == []


# ---------------------------------------------------------------------------
# Cold promotion + touch-aware context
# ---------------------------------------------------------------------------
def test_cold_leads_promoted_and_introduced_within_budget(app, ready):
    c1 = _cold(app, 'Cold One', 'c1@example.com', company='Org One')
    c2 = _cold(app, 'Cold Two', 'c2@example.com', company='Org Two')
    with app.app_context():
        s = AgentSettings.get()
        s.daily_send_cap = 1
        _db.session.commit()
        summary = autonomy.run_daily_cycle(now=NOW, poll=False)
        assert len(summary['promoted']) == 1 and len(summary['sent']) == 1
        promoted_id = c1 if summary['promoted'][0]['contact'] == 'Cold One' else c2
        c = _db.session.get(Contact, promoted_id)
        assert c.lead_status == 'Working' and c.owner_id is not None
        assert c.followup_count == 1 and c.source == 'Scout'
        # the intro was drafted as touch 1 with the scout's angle
        ctx = ready['followups'].calls[-1][0]
        assert ctx['touch_number'] == 1 and ctx['angle'] == 'parks timing'
        # a scout proposal + a follow-up proposal, both auto
        kinds = sorted(a.action_type for a in CrmAgentAction.query.filter_by(contact_id=promoted_id))
        assert kinds == ['follow_up_email', 'scout']


def test_followup_context_carries_touch_and_prior_emails(app, ready):
    cid = _lead(app, 'Third Touch', 'third@example.com', followup=2)
    with app.app_context():
        _db.session.add(Note(contact_id=cid,
                             content='[Email sent to third@example.com] Quick question about plots\n\n'
                                     '<p>Hi Third, I noticed your garden...</p>'))
        _db.session.commit()
        c = _db.session.get(Contact, cid)
        ctx = autonomy._followup_context(c)
        assert ctx['touch_number'] == 3 and ctx['is_final'] is True
        assert ctx['prior_emails'][0]['subject'] == 'Quick question about plots'
        assert 'noticed your garden' in ctx['prior_emails'][0]['snippet']
        # third touch executes → auto-Nurture
        summary = autonomy.run_daily_cycle(now=NOW, poll=False)
        assert summary['nurtured'] == ['Third Touch']
        assert _db.session.get(Contact, cid).lead_status == 'Nurture'


def test_digest_html_mentions_pipeline_runway_and_console_link(app, ready):
    with app.app_context():
        s = AgentSettings.get()
        html = autonomy.build_digest_html({'date': 'Tue Jul 14', 'cap': 15, 'sent': [], 'promoted': [],
                                           'replies': [{'contact': 'Pat', 'classification': 'interested',
                                                        'summary': 'wants pricing', 'action': 'reply drafted'}],
                                           'runway': {'due': 2, 'cold': 1, 'days': 0}}, s)
        assert 'wants pricing' in html and 'Find new leads' in html and '/crm/agent' in html
