"""CRM BDR workflow: lead lifecycle on contacts + the AI agent approval queue
('man in the middle' — the agent proposes, a human approves before anything
sends). The test app has WTF_CSRF_ENABLED=False, so form POSTs need no token,
and conftest's db_session wipes crm_* tables between tests.
"""
from datetime import date, timedelta

from app import db as _db


def _register_first_admin(client, username='bdradmin', password='secret123'):
    return client.post('/crm/register',
                       data={'username': username, 'password': password, 'confirm': password},
                       follow_redirects=True)


def _make_lead(app, email='pat@example.com', status='New'):
    from app.crm.models import Company, Contact
    with app.app_context():
        co = Company(name='Maple Garden', city='Lincoln', state='NE', org_type='Independent')
        _db.session.add(co)
        _db.session.flush()
        c = Contact(name='Pat Grower', email=email, company_id=co.id, lead_status=status)
        _db.session.add(c)
        _db.session.commit()
        return c.id


def test_set_lead_fields(client, app):
    _register_first_admin(client)
    cid = _make_lead(app)
    r = client.post(f'/crm/contacts/{cid}/lead', data={
        'lead_status': 'Working', 'source': 'Referral',
        'next_action_at': date.today().isoformat(), 'next_action_note': 'Call back'},
        follow_redirects=True)
    assert r.status_code == 200
    from app.crm.models import Contact
    with app.app_context():
        c = _db.session.get(Contact, cid)
        assert c.lead_status == 'Working' and c.source == 'Referral'
        assert c.next_action_at == date.today() and c.next_action_note == 'Call back'


def test_log_touch_advances_contact(client, app):
    _register_first_admin(client)
    cid = _make_lead(app)
    r = client.post(f'/crm/contacts/{cid}/log',
                    data={'touch': 'call', 'outcome': 'Connected', 'note': 'Nice chat'},
                    follow_redirects=True)
    assert r.status_code == 200
    from app.crm.models import Contact, Activity
    with app.app_context():
        c = _db.session.get(Contact, cid)
        assert c.last_contacted_at is not None
        assert c.lead_status == 'Working'                       # New -> Working
        # Anchor to the same request's UTC date (avoids local/UTC day-boundary flake).
        assert c.next_action_at == c.last_contacted_at.date() + timedelta(days=3)
        assert Activity.query.filter_by(contact_id=cid, kind='call').count() == 1


def test_qualify_creates_deal(client, app):
    _register_first_admin(client)
    cid = _make_lead(app)
    r = client.post(f'/crm/contacts/{cid}/qualify', data={}, follow_redirects=True)
    assert r.status_code == 200
    from app.crm.models import Contact, Deal
    with app.app_context():
        c = _db.session.get(Contact, cid)
        assert c.lead_status == 'Qualified'
        assert Deal.query.filter_by(contact_id=cid).count() == 1


def test_agent_run_proposes_then_approve_executes(client, app, monkeypatch):
    _register_first_admin(client)
    cid = _make_lead(app)

    from app.crm import agent_service
    monkeypatch.setattr(agent_service, 'is_configured', lambda: True)

    def fake_followups(leads, *, sender_name='', model=None):
        lid = leads[0]['lead_id']
        return ([{'lead_id': lid, 'title': 'Follow up with Pat',
                  'rationale': 'New lead, never contacted',
                  'subject': 'Hi {{first_name}}',
                  'body': 'Hello {{first_name}} at {{company}} — quick intro.'}], {})
    monkeypatch.setattr(agent_service, 'draft_followups', fake_followups)

    # Run agent → a PENDING proposal (nothing sent yet).
    assert client.post('/crm/agent/run', follow_redirects=True).status_code == 200
    from app.crm.models import CrmAgentAction, Contact
    with app.app_context():
        pend = CrmAgentAction.query.filter_by(status='pending').all()
        assert len(pend) == 1 and pend[0].contact_id == cid
        aid = pend[0].id
        # Lead untouched until approval (man in the middle).
        assert _db.session.get(Contact, cid).last_contacted_at is None

    # Approve (with an edit) → executes + advances the lifecycle.
    r = client.post(f'/crm/agent/actions/{aid}/approve',
                    data={'subject': 'Hi {{first_name}}', 'body': 'Hello {{first_name}}!'},
                    follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        a = _db.session.get(CrmAgentAction, aid)
        assert a.status == 'executed'
        c = _db.session.get(Contact, cid)
        assert c.last_contacted_at is not None
        assert c.lead_status == 'Working'
        assert c.next_action_at == c.last_contacted_at.date() + timedelta(days=4)


def test_agent_run_noop_when_unconfigured(client, app, monkeypatch):
    _register_first_admin(client)
    _make_lead(app)
    from app.crm import agent_service
    monkeypatch.setattr(agent_service, 'is_configured', lambda: False)
    assert client.post('/crm/agent/run', follow_redirects=True).status_code == 200
    from app.crm.models import CrmAgentAction
    with app.app_context():
        assert CrmAgentAction.query.count() == 0


def test_reject_proposal(client, app):
    _register_first_admin(client)
    cid = _make_lead(app)
    from app.crm.models import CrmAgentAction
    with app.app_context():
        a = CrmAgentAction(action_type='follow_up_email', status='pending',
                           contact_id=cid, title='X', payload_json='{}')
        _db.session.add(a)
        _db.session.commit()
        aid = a.id
    r = client.post(f'/crm/agent/actions/{aid}/reject',
                    data={'reason': 'not now'}, follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        assert _db.session.get(CrmAgentAction, aid).status == 'rejected'


def test_leads_queue_renders(client, app):
    _register_first_admin(client)
    _make_lead(app)
    assert client.get('/crm/leads').status_code == 200
    assert client.get('/crm/leads?view=all').status_code == 200
    assert client.get('/crm/agent').status_code == 200


def test_scout_proposes_then_approve_promotes(client, app, monkeypatch):
    _register_first_admin(client)
    cid = _make_lead(app)                                  # cold New lead w/ email

    from app.crm import agent_service
    monkeypatch.setattr(agent_service, 'is_configured', lambda: True)

    def fake_scout(leads, *, limit=8, model=None):
        lid = leads[0]['lead_id']
        return ([{'lead_id': lid, 'title': 'Prospect Maple Garden',
                  'rationale': 'Independent garden in NE — strong ICP fit.',
                  'angle': 'Lead with getting their Saturdays back.'}], {})
    monkeypatch.setattr(agent_service, 'scout_leads', fake_scout)

    # Scout → a PENDING scout proposal (lead not yet worked).
    assert client.post('/crm/agent/scout', follow_redirects=True).status_code == 200
    from app.crm.models import CrmAgentAction, Contact
    with app.app_context():
        pend = CrmAgentAction.query.filter_by(status='pending', action_type='scout').all()
        assert len(pend) == 1 and pend[0].contact_id == cid
        aid = pend[0].id
        assert _db.session.get(Contact, cid).lead_status == 'New'

    # Approve → promotes the lead into the working queue.
    assert client.post(f'/crm/agent/actions/{aid}/approve', data={},
                       follow_redirects=True).status_code == 200
    with app.app_context():
        a = _db.session.get(CrmAgentAction, aid)
        assert a.status == 'executed'
        c = _db.session.get(Contact, cid)
        assert c.lead_status == 'Working'
        assert c.owner_id is not None
        assert c.source == 'Scout'
        assert c.next_action_at is not None


def test_scout_noop_when_unconfigured(client, app, monkeypatch):
    _register_first_admin(client)
    _make_lead(app)
    from app.crm import agent_service
    monkeypatch.setattr(agent_service, 'is_configured', lambda: False)
    assert client.post('/crm/agent/scout', follow_redirects=True).status_code == 200
    from app.crm.models import CrmAgentAction
    with app.app_context():
        assert CrmAgentAction.query.count() == 0
