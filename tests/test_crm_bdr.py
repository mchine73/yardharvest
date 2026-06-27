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

    assert client.post(f'/crm/campaigns/{cid}/send', follow_redirects=True).status_code == 200
    with app.app_context():
        recips = CampaignRecipient.query.filter_by(campaign_id=cid).all()
        assert len(recips) == 1 and recips[0].token


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
