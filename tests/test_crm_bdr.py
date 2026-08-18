"""CRM BDR workflow: lead lifecycle on contacts + the AI agent approval queue
('man in the middle' — the agent proposes, a human approves before anything
sends). The test app has WTF_CSRF_ENABLED=False, so form POSTs need no token,
and conftest's db_session wipes crm_* tables between tests.
"""
import json
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
        # next_action_at=today = the explicit "promote to queue" step: since
        # the import-flood fix, a never-worked lead is due only when OWNED or
        # given a next action (Contact.is_due), so test leads opt in here.
        c = Contact(name='Pat Grower', email=email, company_id=co.id,
                    lead_status=status, next_action_at=date.today())
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


def _pending_action(app, cid=None, action_type='follow_up_email'):
    from app.crm.models import CrmAgentAction
    with app.app_context():
        a = CrmAgentAction(action_type=action_type, status='pending',
                           contact_id=cid, title='X', payload_json='{}')
        _db.session.add(a)
        _db.session.commit()
        return a.id


def test_dismiss_bad_fit_disqualifies(client, app):
    _register_first_admin(client)
    cid = _make_lead(app)
    aid = _pending_action(app, cid)
    client.post(f'/crm/agent/actions/{aid}/reject',
                data={'reason': 'bad_fit'}, follow_redirects=True)
    from app.crm.models import CrmAgentAction, Contact
    with app.app_context():
        c = _db.session.get(Contact, cid)
        assert c.lead_status == 'Disqualified' and c.next_action_at is None
        assert _db.session.get(CrmAgentAction, aid).status == 'rejected'


def test_dismiss_reached_out_marks_contacted(client, app):
    _register_first_admin(client)
    cid = _make_lead(app)                                   # New, never contacted
    aid = _pending_action(app, cid)
    client.post(f'/crm/agent/actions/{aid}/reject',
                data={'reason': 'reached_out'}, follow_redirects=True)
    from app.crm.models import Contact
    with app.app_context():
        c = _db.session.get(Contact, cid)
        assert c.last_contacted_at is not None and c.lead_status == 'Working'


def test_dismiss_snooze_defers(client, app):
    from datetime import timedelta
    _register_first_admin(client)
    cid = _make_lead(app)
    aid = _pending_action(app, cid, action_type='scout')
    client.post(f'/crm/agent/actions/{aid}/reject',
                data={'reason': 'snooze_1m'}, follow_redirects=True)
    from app.crm.models import Contact, _utcnow
    with app.app_context():
        c = _db.session.get(Contact, cid)
        assert c.next_action_at == _utcnow().date() + timedelta(days=30)
        assert c.lead_status == 'Working'         # left the cold pool until it resurfaces


def test_dismiss_other_records_note_no_contact(client, app):
    """Campaign proposals (no contact) record the note, no lifecycle change."""
    _register_first_admin(client)
    aid = _pending_action(app, cid=None, action_type='campaign')
    client.post(f'/crm/agent/actions/{aid}/reject',
                data={'reason': 'other', 'note': 'duplicate of last week'},
                follow_redirects=True)
    from app.crm.models import CrmAgentAction
    with app.app_context():
        a = _db.session.get(CrmAgentAction, aid)
        assert a.status == 'rejected' and 'duplicate of last week' in a.result


def test_scout_web_proposes_dedupes_and_approves_into_funnel(client, app, monkeypatch):
    """Web scout creates new_lead proposals (deduped vs existing companies);
    approving one creates the Company + a New/Scout-sourced Contact."""
    _register_first_admin(client)
    from app.crm import agent_service
    from app.crm.models import CrmAgentAction, Company, Contact
    with app.app_context():
        _db.session.add(Company(name='Existing Garden'))
        _db.session.commit()
    monkeypatch.setattr(agent_service, 'is_configured', lambda: True)
    monkeypatch.setattr(agent_service, 'scout_new_leads', lambda **k: ([
        {'name': 'Existing Garden', 'city': 'A', 'state': 'NE', 'org_type': 'Independent',
         'website': '', 'contact_name': '', 'contact_email': '', 'contact_title': '',
         'fit': 'dup', 'source_url': 'https://x/1'},
        {'name': 'Fresh Roots Collective', 'city': 'Omaha', 'state': 'NE',
         'org_type': 'Nonprofit', 'website': 'https://fresh.org', 'contact_name': 'Sam',
         'contact_email': 'sam@fresh.org', 'contact_title': 'Director',
         'fit': 'Multi-garden nonprofit — strong fit.', 'source_url': 'https://fresh.org/about'},
    ], {}))

    r = client.post('/crm/agent/scout-web', follow_redirects=True)
    # The redirected console renders the new_lead card + the Find-new-leads form.
    assert r.status_code == 200
    assert b'Fresh Roots Collective' in r.data and b'add to CRM' in r.data
    assert b'/crm/agent/scout-web' in r.data
    with app.app_context():
        props = (CrmAgentAction.query
                 .filter_by(action_type='new_lead', status='pending').all())
        assert len(props) == 1                      # 'Existing Garden' deduped out
        assert props[0].payload['name'] == 'Fresh Roots Collective'
        aid = props[0].id

    client.post(f'/crm/agent/actions/{aid}/approve', follow_redirects=True)
    with app.app_context():
        co = Company.query.filter(Company.name == 'Fresh Roots Collective').first()
        assert co is not None and co.org_type == 'Nonprofit'
        c = Contact.query.filter_by(company_id=co.id).first()
        assert c.lead_status == 'New' and c.source == 'Scout'
        assert c.email == 'sam@fresh.org' and c.next_action_at is not None
        assert _db.session.get(CrmAgentAction, aid).status == 'executed'


def test_scout_web_records_usage_and_cost(client, app, monkeypatch):
    """An agent run records token/web-search usage + an estimated cost on
    crm_agent_run — even when it returns zero leads (the search still cost)."""
    _register_first_admin(client)
    from app.crm import agent_service
    from app.crm.models import CrmAgentRun
    monkeypatch.setattr(agent_service, 'is_configured', lambda: True)
    monkeypatch.setattr(agent_service, 'scout_new_leads', lambda **k: ([], {
        'model': 'claude-opus-4-8', 'input_tokens': 10000,
        'output_tokens': 4000, 'web_searches': 4}))
    client.post('/crm/agent/scout-web', follow_redirects=True)
    with app.app_context():
        run = (CrmAgentRun.query.filter_by(kind='scout_web')
               .order_by(CrmAgentRun.id.desc()).first())
        assert run is not None and run.status == 'done'
        assert run.web_searches == 4 and run.model == 'claude-opus-4-8'
        assert run.cost_usd and run.cost_usd > 0


def test_agent_console_shows_ai_usage_panel(client, app):
    _register_first_admin(client)
    from app.crm.models import CrmAgentRun
    with app.app_context():
        _db.session.add(CrmAgentRun(
            kind='scout_web', status='done', model='claude-opus-4-8',
            input_tokens=10000, output_tokens=4000, web_searches=4, cost_usd=0.16))
        _db.session.commit()
    html = client.get('/crm/agent').get_data(as_text=True)
    assert 'AI usage' in html and 'web search' in html


def _approve_new_followup(client, app, cid):
    """Insert a pending follow-up proposal for cid and approve it."""
    from app.crm.models import CrmAgentAction
    with app.app_context():
        a = CrmAgentAction(action_type='follow_up_email', status='pending',
                           contact_id=cid, title='T', payload_json='{}')
        _db.session.add(a)
        _db.session.commit()
        aid = a.id
    r = client.post(f'/crm/agent/actions/{aid}/approve',
                    data={'subject': 'S', 'body': 'B'}, follow_redirects=True)
    assert r.status_code == 200


def test_touch_cadence_escalates_then_nurtures(client, app):
    """No-reply follow-ups space 4d -> 8d, then the 3rd send auto-moves the
    lead to Nurture ~90 days out instead of emailing forever."""
    _register_first_admin(client)
    cid = _make_lead(app)
    from app.crm.models import Contact
    from datetime import timedelta

    _approve_new_followup(client, app, cid)
    with app.app_context():
        c = _db.session.get(Contact, cid)
        today = c.last_contacted_at.date()
        assert c.followup_count == 1
        assert c.next_action_at == today + timedelta(days=4)

    _approve_new_followup(client, app, cid)
    with app.app_context():
        c = _db.session.get(Contact, cid)
        assert c.followup_count == 2
        assert c.next_action_at == c.last_contacted_at.date() + timedelta(days=8)
        assert c.lead_status == 'Working'

    _approve_new_followup(client, app, cid)
    with app.app_context():
        c = _db.session.get(Contact, cid)
        assert c.followup_count == 3
        assert c.lead_status == 'Nurture'
        assert c.next_action_at == c.last_contacted_at.date() + timedelta(days=90)
        assert 'nurtured' in (c.next_action_note or '').lower()


def test_mark_replied_resets_clock(client, app):
    _register_first_admin(client)
    cid = _make_lead(app)
    from app.crm.models import Contact
    from datetime import timedelta
    with app.app_context():
        c = _db.session.get(Contact, cid)
        c.followup_count = 2
        c.lead_status = 'Working'
        _db.session.commit()
    r = client.post(f'/crm/contacts/{cid}/replied', follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        c = _db.session.get(Contact, cid)
        assert c.lead_status == 'Engaged' and c.followup_count == 0
        assert c.next_action_at == c.last_contacted_at.date() + timedelta(days=3)


def test_agent_run_skips_no_email_leads_without_starving(client, app, monkeypatch):
    """Due leads without an email (front of the queue) must not consume the
    drafting slots — the run over-fetches, filters, then caps."""
    _register_first_admin(client)
    from app.crm.models import Contact, CrmAgentAction
    from app.crm import agent_service
    with app.app_context():
        # 12 due leads with NO email sit at the front of the queue…
        # (next_action_at=today = promoted/due under the import-flood fix)
        for i in range(12):
            _db.session.add(Contact(name=f'NoMail {i}', lead_status='New',
                                     next_action_at=date.today()))
        # …and one emailable lead behind them.
        c = Contact(name='Mailable', email='mailable@example.com',
                    lead_status='New', next_action_at=date.today())
        _db.session.add(c)
        _db.session.commit()
        cid = c.id

    monkeypatch.setattr(agent_service, 'is_configured', lambda: True)

    def fake_followups(leads, *, sender_name='', model=None):
        return ([{'lead_id': ld['lead_id'], 'title': 'T', 'rationale': 'r',
                  'subject': 'S', 'body': 'B'} for ld in leads], {})
    monkeypatch.setattr(agent_service, 'draft_followups', fake_followups)

    assert client.post('/crm/agent/run', follow_redirects=True).status_code == 200
    with app.app_context():
        pend = CrmAgentAction.query.filter_by(status='pending',
                                              action_type='follow_up_email').all()
        assert [a.contact_id for a in pend] == [cid]


def test_nurture_resurface(client, app):
    """The daily job returns dated Nurture leads to the working queue; undated
    Nurture leads stay parked."""
    _register_first_admin(client)
    from app.crm.models import Contact, _utcnow
    from app.crm.helpers import resurface_nurture_leads
    from datetime import timedelta
    with app.app_context():
        due = Contact(name='Comeback', lead_status='Nurture', followup_count=3,
                      next_action_at=_utcnow().date() - timedelta(days=1))
        parked = Contact(name='Parked', lead_status='Nurture')
        _db.session.add_all([due, parked])
        _db.session.commit()
        did, pid = due.id, parked.id

        assert resurface_nurture_leads() == 1
        d = _db.session.get(Contact, did)
        assert d.lead_status == 'Working' and d.followup_count == 0
        assert d.next_action_at == _utcnow().date()
        assert _db.session.get(Contact, pid).lead_status == 'Nurture'


def test_enrich_run_fills_fields_from_web(client, app, monkeypatch):
    """The enrichment run targets companies with no emailable contact, fills
    verified fields (email onto the email-less contact, phone, website), and
    cites the source in a Note + timeline entry. Companies that already have
    an emailable contact are not touched."""
    _register_first_admin(client)
    from app.crm import agent_service
    from app.crm.models import Company, Contact, Note, Activity
    with app.app_context():
        needy = Company(name='Maple Roots', city='Lincoln', state='NE')
        covered = Company(name='Covered Org')
        _db.session.add_all([needy, covered])
        _db.session.flush()
        _db.session.add(Contact(name='Info — Maple Roots', company_id=needy.id))
        _db.session.add(Contact(name='Has Mail', email='ok@covered.org',
                                company_id=covered.id))
        _db.session.commit()
        needy_id, covered_id = needy.id, covered.id

    monkeypatch.setattr(agent_service, 'is_configured', lambda: True)
    enriched_ids = []

    def fake_enrich(ctx, model=None):
        enriched_ids.append(ctx['name'])
        return ({'email': 'garden@maple.org', 'phone': '555-0100',
                 'contact_name': 'Pat Smith', 'contact_title': 'Coordinator',
                 'website': 'https://maple.org',
                 'source_url': 'https://maple.org/contact',
                 'found_note': 'Contact page lists email + phone.'},
                {'model': 'claude-opus-4-8', 'input_tokens': 1000,
                 'output_tokens': 300, 'web_searches': 3})
    monkeypatch.setattr(agent_service, 'enrich_company', fake_enrich)

    assert client.post('/crm/agent/enrich', follow_redirects=True).status_code == 200
    with app.app_context():
        # Only the company without an emailable contact was targeted.
        assert enriched_ids == ['Maple Roots']
        c = Contact.query.filter_by(company_id=needy_id).first()
        assert c.email == 'garden@maple.org' and c.phone == '555-0100'
        assert c.name == 'Pat Smith'          # generic 'Info —' name upgraded
        assert _db.session.get(Company, needy_id).website == 'https://maple.org'
        note = Note.query.filter_by(company_id=needy_id).first()
        assert note and 'maple.org/contact' in note.content
        act = Activity.query.filter_by(company_id=needy_id, kind='updated').first()
        assert act and 'Enriched from the web' in act.description
        # The covered company was untouched.
        assert Contact.query.filter_by(company_id=covered_id).count() == 1
        # Usage recorded on the run (cost visibility).
        from app.crm.models import CrmAgentRun
        run = (CrmAgentRun.query.filter_by(kind='enrich')
               .order_by(CrmAgentRun.id.desc()).first())
        assert run is not None and run.status == 'done' and run.web_searches == 3


def test_new_lead_approve_applies_phone(client, app):
    _register_first_admin(client)
    from app.crm.models import CrmAgentAction, Contact
    with app.app_context():
        a = CrmAgentAction(action_type='new_lead', status='pending',
                           title='New lead: Phoned Garden',
                           payload_json=json.dumps({
                               'name': 'Phoned Garden', 'city': 'Omaha', 'state': 'NE',
                               'org_type': 'Independent', 'website': '',
                               'contact_name': 'Sam', 'contact_email': 's@pg.org',
                               'contact_title': '', 'contact_phone': '555-0199',
                               'fit': 'x', 'source_url': 'https://pg.org'}))
        _db.session.add(a)
        _db.session.commit()
        aid = a.id
    assert client.post(f'/crm/agent/actions/{aid}/approve',
                       follow_redirects=True).status_code == 200
    with app.app_context():
        c = Contact.query.filter_by(email='s@pg.org').first()
        assert c is not None and c.phone == '555-0199'


def test_deliverability_dashboard_renders(client, app):
    """The deliverability page shows setup instructions until the webhook has
    delivered events, then flips to the connected state with the event feed."""
    _register_first_admin(client)
    html = client.get('/crm/deliverability').get_data(as_text=True)
    assert 'Email Deliverability' in html
    assert 'No delivery events received yet' in html   # webhook not connected

    from app.crm.models import CrmEmailEvent
    with app.app_context():
        _db.session.add(CrmEmailEvent(email='gone@example.com',
                                      event_type='hard', reason='550 user unknown'))
        _db.session.commit()
    html = client.get('/crm/deliverability').get_data(as_text=True)
    assert 'Webhook connected' in html
    assert 'gone@example.com' in html and 'hard bounce' in html


def test_dismiss_dropdown_renders(client, app):
    _register_first_admin(client)
    cid = _make_lead(app)
    _pending_action(app, cid)
    html = client.get('/crm/agent').get_data(as_text=True)
    assert 'value="bad_fit"' in html and 'value="reached_out"' in html
    assert 'value="snooze_1m"' in html and 'value="other"' in html


def test_leads_queue_renders(client, app):
    _register_first_admin(client)
    _make_lead(app)
    assert client.get('/crm/leads').status_code == 200
    assert client.get('/crm/leads?view=all').status_code == 200
    assert client.get('/crm/agent').status_code == 200


def test_pending_count_endpoint(client, app):
    _register_first_admin(client)
    cid = _make_lead(app)
    from app.crm.models import CrmAgentAction
    with app.app_context():
        _db.session.add(CrmAgentAction(action_type='scout', status='pending',
                                       contact_id=cid, title='X', payload_json='{}'))
        _db.session.commit()
    r = client.get('/crm/agent/pending-count')
    j = r.get_json()
    assert r.status_code == 200 and j['pending'] == 1 and j['drafting'] is False


def test_drafting_run_tracking(client, app):
    """The banner relies on this DB flag: true while a job runs, false once done."""
    from app.crm import views
    from app.crm.models import CrmAgentRun
    with app.app_context():
        assert views.drafting_in_progress() is False
        rid = views._begin_drafting('follow_up')
        assert views.drafting_in_progress() is True
        views._finish_drafting(rid)
        assert views.drafting_in_progress() is False
        assert _db.session.get(CrmAgentRun, rid).status == 'done'


def test_pending_count_reflects_running_job(client, app):
    """A running crm_agent_run row makes the poll report drafting=true (the
    signal that keeps the banner up until the job actually finishes)."""
    _register_first_admin(client)
    from app.crm.models import CrmAgentRun
    with app.app_context():
        _db.session.add(CrmAgentRun(kind='follow_up', status='running'))
        _db.session.commit()
    assert client.get('/crm/agent/pending-count').get_json()['drafting'] is True


def test_agent_console_has_autorefresh_wiring(client, app):
    _register_first_admin(client)
    html = client.get('/crm/agent').get_data(as_text=True)
    assert 'id="approvalQueue"' in html and 'data-pending-count' in html
    assert '/crm/agent/pending-count' in html       # poll endpoint wired into the page


def test_followup_card_uses_rich_editor(client, app):
    """A pending follow-up email is edited in the Quill rich-text editor (same
    generator/editor as the email composer), not a plain textarea."""
    _register_first_admin(client)
    cid = _make_lead(app)
    from app.crm.models import CrmAgentAction
    with app.app_context():
        _db.session.add(CrmAgentAction(
            action_type='follow_up_email', status='pending', contact_id=cid,
            title='Follow up', payload_json='{"subject":"Hi","body":"<p>Hello</p>"}'))
        _db.session.commit()
    html = client.get('/crm/agent').get_data(as_text=True)
    assert 'rich-body' in html                      # body textarea flagged for Quill
    assert 'quill' in html.lower()                  # rich editor partial loaded


def test_scout_only_queue_skips_rich_editor(client, app):
    """Quill isn't loaded when there are no follow-up emails to edit (guard)."""
    _register_first_admin(client)
    cid = _make_lead(app)
    from app.crm.models import CrmAgentAction
    with app.app_context():
        _db.session.add(CrmAgentAction(action_type='scout', status='pending',
                                       contact_id=cid, title='Scout', payload_json='{}'))
        _db.session.commit()
    html = client.get('/crm/agent').get_data(as_text=True)
    assert 'quill' not in html.lower()


def test_run_followups_redirects_with_drafting_flag(client, app, monkeypatch):
    _register_first_admin(client)
    _make_lead(app)
    from app.crm import agent_service
    monkeypatch.setattr(agent_service, 'is_configured', lambda: True)
    monkeypatch.setattr(agent_service, 'draft_followups',
                        lambda leads, **k: ([], {}))   # no drafts; just check the kickoff
    # follow_redirects=False so we can see the redirect carries the baseline
    # pending count as ?drafting=<n> (so the console can poll until it grows).
    r = client.post('/crm/agent/run')
    assert r.status_code == 302 and 'drafting=' in r.headers['Location']


def test_agent_console_links_contact_and_company_in_new_tab(client, app):
    """A proposal card lists the company and links BOTH the contact and the
    company to their pages, each opening in a new window (target=_blank)."""
    _register_first_admin(client)
    cid = _make_lead(app)
    from app.crm.models import CrmAgentAction, Contact
    with app.app_context():
        coid = _db.session.get(Contact, cid).company_id
        _db.session.add(CrmAgentAction(
            action_type='scout', status='pending', contact_id=cid,
            company_id=coid, title='Reach Maple Garden', payload_json='{}'))
        _db.session.commit()
    html = client.get('/crm/agent').get_data(as_text=True)
    assert 'Maple Garden' in html                       # company is listed
    assert ('/crm/contacts/%d' % cid) in html           # contact links to its page
    assert ('/crm/companies/%d' % coid) in html         # company links to its page
    # Contact + company anchors both open a new window (plus the guide link).
    assert html.count('target="_blank"') >= 3


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


# ---- Phase 3: campaign tracking + agent campaign proposals ----

def test_campaign_open_click_tracking(client, app):
    from app.crm.models import Campaign, CampaignRecipient, Contact, Company
    with app.app_context():
        co = Company(name='Org', state='NE')
        _db.session.add(co)
        _db.session.flush()
        c = Contact(name='Pat', email='pat@example.com', company_id=co.id)
        _db.session.add(c)
        _db.session.flush()
        camp = Campaign(name='C1', subject='s', body='b', status='sent')
        _db.session.add(camp)
        _db.session.flush()
        r = CampaignRecipient(campaign_id=camp.id, contact_id=c.id, status='sent', token='tok123')
        _db.session.add(r)
        _db.session.commit()
        rid = r.id

    # Tracking endpoints are PUBLIC (no CRM login).
    ro = client.get('/crm/t/open/tok123')
    assert ro.status_code == 200 and 'image' in ro.content_type
    rc = client.get('/crm/t/click/tok123?u=https://example.com/x', follow_redirects=False)
    assert rc.status_code in (301, 302) and 'example.com' in rc.headers.get('Location', '')
    with app.app_context():
        r = _db.session.get(CampaignRecipient, rid)
        assert r.opened_at is not None and r.clicked_at is not None

    # Unknown token and non-http target are handled safely (no crash, no open redirect).
    assert client.get('/crm/t/open/nope').status_code == 200
    bad = client.get('/crm/t/click/nope?u=javascript:alert(1)', follow_redirects=False)
    assert bad.status_code in (301, 302) and 'javascript:' not in bad.headers.get('Location', '')


def test_campaign_send_assigns_tracking_tokens(client, app):
    _register_first_admin(client)
    from app.crm.models import Campaign, Contact, Company, CampaignRecipient
    with app.app_context():
        co = Company(name='Org', state='NE')
        _db.session.add(co)
        _db.session.flush()
        _db.session.add(Contact(name='Pat', email='pat@example.com', company_id=co.id))
        camp = Campaign(name='C', subject='Hi', body='Hello {{first_name}}',
                        status='draft', audience_state='NE')
        _db.session.add(camp)
        _db.session.commit()
        cid = camp.id

    # Two-step checkpoint: the first POST snapshots the recipient list for
    # review (nothing dispatched), the second confirms the reviewed list.
    assert client.post(f'/crm/campaigns/{cid}/send', follow_redirects=True).status_code == 200
    with app.app_context():
        pend = CampaignRecipient.query.filter_by(campaign_id=cid).all()
        assert len(pend) == 1 and pend[0].status == 'pending' and not pend[0].token
    assert client.post(f'/crm/campaigns/{cid}/send', follow_redirects=True).status_code == 200
    with app.app_context():
        recips = CampaignRecipient.query.filter_by(campaign_id=cid).all()
        assert len(recips) == 1 and recips[0].token
        assert recips[0].status != 'pending'


def test_agent_campaign_propose_then_approve_creates_draft(client, app, monkeypatch):
    _register_first_admin(client)
    _make_lead(app)                                  # Company in NE + emailable contact

    from app.crm import agent_service
    monkeypatch.setattr(agent_service, 'is_configured', lambda: True)
    monkeypatch.setattr(agent_service, 'draft_campaign',
                        lambda goal, **k: ({'name': 'NE intro',
                                            'subject': 'Hello {{company}}',
                                            'body': 'Hi {{first_name}}'}, {}))

    assert client.post('/crm/agent/campaign', follow_redirects=True).status_code == 200
    from app.crm.models import CrmAgentAction, Campaign
    with app.app_context():
        a = CrmAgentAction.query.filter_by(status='pending', action_type='campaign').first()
        assert a is not None
        aid = a.id

    assert client.post(f'/crm/agent/actions/{aid}/approve', data={},
                       follow_redirects=True).status_code == 200
    with app.app_context():
        assert _db.session.get(CrmAgentAction, aid).status == 'executed'
        assert Campaign.query.filter_by(audience_state='NE', status='draft').count() == 1


def test_failed_drafting_records_error_not_done(client, app):
    """A worker exception must record status='failed' + the error detail —
    previously the finally clause forced 'done', so a failed scout was
    indistinguishable from 'ran fine, found nothing new'."""
    import pytest
    from app.crm import views
    from app.crm.models import CrmAgentRun
    with app.app_context():
        rid = views._begin_drafting('scout_web')

        def boom():
            raise RuntimeError('anthropic 529 overloaded')

        with pytest.raises(RuntimeError):
            views._run_and_finish(rid, boom)
        run = _db.session.get(CrmAgentRun, rid)
        assert run.status == 'failed'
        assert 'overloaded' in (run.error or '')
        assert run.finished_at is not None
        # A late duplicate finish must NOT overwrite the terminal failure.
        views._finish_drafting(rid)
        assert _db.session.get(CrmAgentRun, rid).status == 'failed'
        assert views.drafting_in_progress() is False


def test_stalled_run_reported_and_ages_out(client, app):
    """A 'running' row older than the stall cutoff (dead worker) must age out
    of drafting_in_progress AND be reported as 'stalled', not 'found nothing'."""
    from datetime import timedelta
    from app.crm import views
    from app.crm.models import CrmAgentRun
    with app.app_context():
        run = CrmAgentRun(kind='enrich', status='running')
        run.created_at = views._utcnow() - timedelta(minutes=views.DRAFTING_STALL_MINUTES + 5)
        _db.session.add(run)
        _db.session.commit()
        assert views.drafting_in_progress() is False
        outcome = views._last_run_outcome()
        assert outcome['status'] == 'stalled' and outcome['kind'] == 'enrich'


def test_console_surfaces_failed_run(client, app):
    """The console tells the operator the last run failed (so they retry)
    instead of silently showing an unchanged queue."""
    _register_first_admin(client)
    from app.crm import views
    from app.crm.models import CrmAgentRun
    with app.app_context():
        run = CrmAgentRun(kind='scout_web', status='failed',
                          error='API key expired', finished_at=views._utcnow())
        _db.session.add(run)
        _db.session.commit()
    html = client.get('/crm/agent').get_data(as_text=True)
    assert 'failed' in html and 'API key expired' in html
    # pending-count exposes the same outcome for the banner poll
    data = client.get('/crm/agent/pending-count').get_json()
    assert data['last_run']['status'] == 'failed'


def test_positive_call_resets_no_reply_cadence(client, app):
    """A logged 'Connected' call must reset followup_count so the next agent
    email doesn't trip the auto-Nurture cap right after a great conversation."""
    _register_first_admin(client)
    cid = _make_lead(app)
    from app.crm.models import Contact
    with app.app_context():
        c = _db.session.get(Contact, cid)
        c.followup_count = 2                       # one email from auto-Nurture
        _db.session.commit()
    client.post(f'/crm/contacts/{cid}/log',
                data={'touch': 'call', 'outcome': 'Connected', 'note': ''},
                follow_redirects=True)
    with app.app_context():
        assert _db.session.get(Contact, cid).followup_count == 0
    # A neutral outcome must NOT reset the counter.
    with app.app_context():
        c = _db.session.get(Contact, cid)
        c.followup_count = 2
        _db.session.commit()
    client.post(f'/crm/contacts/{cid}/log',
                data={'touch': 'call', 'outcome': 'Left voicemail', 'note': ''},
                follow_redirects=True)
    with app.app_context():
        assert _db.session.get(Contact, cid).followup_count == 2


def test_imported_unowned_lead_not_instantly_due(client, app):
    """A bulk import must not flood the Due queue: never-worked leads are due
    only once owned (or given an explicit next action)."""
    _register_first_admin(client)
    from io import BytesIO
    csv_body = ('Name,City,State,Type,Email\n'
                'Flood Org,Omaha,NE,Independent,flood@example.com\n')
    client.post('/crm/import',
                data={'file': (BytesIO(csv_body.encode()), 'leads.csv')},
                content_type='multipart/form-data', follow_redirects=True)
    from app.crm.models import Contact
    from app.crm.views import _due_leads
    with app.app_context():
        c = Contact.query.filter_by(email='flood@example.com').first()
        assert c.source == 'Import'                # provenance stamped
        assert c.is_due is False                   # not in the queue yet
        assert c.id not in {x.id for x in _due_leads()}
        # Assigning an owner is the explicit promote-to-queue step. Use the
        # real registered admin's id — Postgres enforces the FK (a hardcoded
        # id=1 passed on SQLite only because its FK enforcement is off).
        from app.crm.models import CrmUser
        c.owner_id = CrmUser.query.first().id
        _db.session.commit()
        assert c.is_due is True
        assert c.id in {x.id for x in _due_leads()}


def test_followup_dedup_symmetric_with_scout(client, app, monkeypatch):
    """A lead with a pending SCOUT proposal must not also get a follow-up
    proposal in the same pass (one lead, one card)."""
    _register_first_admin(client)
    cid = _make_lead(app)
    from app.crm.models import CrmAgentAction
    from app.crm.views import _async_draft_followups
    with app.app_context():
        _db.session.add(CrmAgentAction(
            action_type='scout', status='pending', contact_id=cid,
            title='Prospect Maple Garden', payload_json='{}'))
        _db.session.commit()
    from app.crm import agent_service
    monkeypatch.setattr(agent_service, 'draft_followups',
                        lambda leads, sender_name='': (
                            [{'lead_id': cid, 'title': 'Follow up',
                              'subject': 's', 'body': 'b'}], {}))
    with app.app_context():
        _async_draft_followups([cid], 'James', 1)
        follow = CrmAgentAction.query.filter_by(
            contact_id=cid, action_type='follow_up_email').count()
        assert follow == 0                         # scout card already covers it


def test_lead_queue_shows_grade_and_signal_badges(client, app):
    """The work queue answers 'who next and why': grade badge, no-email badge,
    bounced badge, and the nurture-overdue canary all render."""
    _register_first_admin(client)
    from datetime import date, timedelta
    from app.crm.models import Company, Contact
    with app.app_context():
        co = Company(name='Badge Org', state='NE')
        _db.session.add(co)
        _db.session.flush()
        _db.session.add(Contact(name='No Mail', email=None, company_id=co.id,
                                lead_status='Working',
                                next_action_at=date.today()))
        _db.session.add(Contact(name='Bounced Guy', email='b@example.com',
                                company_id=co.id, lead_status='Working',
                                last_bounce_type='hard',
                                next_action_at=date.today()))
        _db.session.add(Contact(name='Overdue Nurture', email='n@example.com',
                                company_id=co.id, lead_status='Nurture',
                                next_action_at=date.today() - timedelta(days=3)))
        _db.session.commit()
    html = client.get('/crm/leads?view=all').get_data(as_text=True)
    assert 'no email' in html
    assert 'bounced' in html
    assert 'overdue to resurface' in html          # nurture canary
    for g in ('Hot', 'Warm', 'Cold'):
        assert f'>{g}</a>' in html                 # grade filter buttons


def test_new_lead_approve_respects_location_collision(client, app):
    """Approving a scouted org whose name matches an EXISTING company in a
    different city/state must create a DISTINCT company — not graft the
    scouted contact onto the wrong org (generic names repeat constantly)."""
    _register_first_admin(client)
    from app.crm.models import Company, Contact, CrmAgentAction
    with app.app_context():
        _db.session.add(Company(name='Community Garden', city='Boston',
                                state='MA', org_type='Independent'))
        a = CrmAgentAction(
            action_type='new_lead', status='pending',
            title='Add Community Garden (Denver)',
            payload_json=json.dumps({
                'name': 'Community Garden', 'city': 'Denver', 'state': 'CO',
                'org_type': 'Independent', 'website': 'https://cg-denver.org',
                'source_url': 'https://cg-denver.org/about',
                'contact_email': 'hello@cg-denver.org'}))
        _db.session.add(a)
        _db.session.commit()
        aid = a.id

    client.post(f'/crm/agent/actions/{aid}/approve', follow_redirects=True)
    with app.app_context():
        gardens = Company.query.filter(
            Company.name == 'Community Garden').all()
        assert len(gardens) == 2                       # distinct org created
        denver = next(g for g in gardens if g.state == 'CO')
        assert denver.city == 'Denver'
        c = Contact.query.filter_by(email='hello@cg-denver.org').first()
        assert c is not None and c.company_id == denver.id
        # Same-name SAME-place still dedupes (no third company).
        boston = next(g for g in gardens if g.state == 'MA')
        assert boston.city == 'Boston'


def test_import_same_name_different_state_still_imports(client, app):
    """Import dedup is collision-aware: 'Community Garden' in a different
    state is a different org and must not be skipped as a duplicate."""
    _register_first_admin(client)
    from app.crm.models import Company
    with app.app_context():
        _db.session.add(Company(name='Community Garden', city='Boston',
                                state='MA'))
        _db.session.commit()
    from io import BytesIO
    csv_body = ('Name,City,State,Type\n'
                'Community Garden,Denver,CO,Independent\n'   # new org
                'Community Garden,Boston,MA,Independent\n')  # true duplicate
    client.post('/crm/import',
                data={'file': (BytesIO(csv_body.encode()), 'leads.csv')},
                content_type='multipart/form-data', follow_redirects=True)
    with app.app_context():
        assert Company.query.filter_by(name='Community Garden').count() == 2


def test_mark_replied_withdraws_pending_followups(client, app):
    """A reply must retire any queued automated follow-up — otherwise the
    autonomous cycle would nudge someone who already answered."""
    _register_first_admin(client)
    cid = _make_lead(app, email='replied@example.com', status='Working')
    aid = _pending_action(app, cid=cid)
    client.post(f'/crm/contacts/{cid}/replied', follow_redirects=True)
    from app.crm.models import CrmAgentAction, Contact
    with app.app_context():
        a = _db.session.get(CrmAgentAction, aid)
        assert a.status == 'rejected'
        assert 'replied' in (a.result or '').lower()
        c = _db.session.get(Contact, cid)
        assert c.lead_status == 'Engaged' and c.followup_count == 0


def test_execute_action_skips_opted_out_without_advancing_cadence(client, app, monkeypatch):
    """Approving a follow-up for an opted-out contact is a SKIP: nothing is
    sent, and the no-reply cadence must not advance (previously it 'logged'
    the email and burned a touch)."""
    _register_first_admin(client)
    cid = _make_lead(app, email='optout@example.com', status='Working')
    from app.crm.models import Contact, CrmAgentAction
    with app.app_context():
        c = _db.session.get(Contact, cid)
        c.email_opt_out = True
        _db.session.commit()
    aid = _pending_action(app, cid=cid)
    import app.crm.autonomy as autonomy
    sends = []
    monkeypatch.setattr(autonomy, 'smtp_send', lambda *a, **k: sends.append(1) or True)
    r = client.post(f'/crm/agent/actions/{aid}/approve',
                    data={'subject': 'Hi', 'body': 'Hello'}, follow_redirects=True)
    assert b'Not sent' in r.data
    assert sends == []
    with app.app_context():
        c = _db.session.get(Contact, cid)
        assert c.followup_count == 0
        a = _db.session.get(CrmAgentAction, aid)
        assert a.status == 'executed' and 'Skipped' in a.result
