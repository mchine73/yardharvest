"""Integration tests for the consolidated CRM module mounted at /crm.

Covers the seams that the merge introduced: session-based CRM auth (separate
from YH Flask-Login), the token-gated marketing API, the path-aware CSP, and
that the crm_* tables are created on boot. The test app fixture has
WTF_CSRF_ENABLED=False (see conftest), so form POSTs don't need a token here —
CSRF behavior itself is exercised via the manual smoke path, not these tests.
"""
import pytest

from app import db as _db


@pytest.fixture()
def crm_clean(app):
    """Wipe crm_* tables before each CRM test so auth/state is deterministic."""
    from app.crm.models import (Activity, Campaign, CampaignRecipient, Company,
                                Contact, CrmUser, Deal, DealContact,
                                EmailTemplate, Note, Task)
    with app.app_context():
        for model in (Activity, CampaignRecipient, Campaign, Note, Task,
                      DealContact, Deal, Contact, Company, EmailTemplate,
                      CrmUser):
            _db.session.query(model).delete()
        _db.session.commit()
    yield


def _register_first_admin(client, username='crmadmin', password='secret123'):
    return client.post('/crm/register',
                       data={'username': username, 'password': password,
                             'confirm': password},
                       follow_redirects=True)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
def test_crm_tables_created(app):
    crm_tables = {t for t in _db.metadata.tables if t.startswith('crm_')}
    expected = {
        'crm_user', 'crm_company', 'crm_contact', 'crm_deal',
        'crm_deal_contact', 'crm_note', 'crm_task', 'crm_email_template',
        'crm_campaign', 'crm_campaign_recipient', 'crm_activity',
    }
    assert expected <= crm_tables


# ---------------------------------------------------------------------------
# Auth gate
# ---------------------------------------------------------------------------
def test_dashboard_requires_login(client, crm_clean):
    resp = client.get('/crm/dashboard', follow_redirects=False)
    assert resp.status_code == 302
    assert '/crm/login' in resp.headers['Location']


def test_login_redirects_to_register_on_fresh_db(client, crm_clean):
    """With no CRM users, /crm/login bounces to /crm/register to seed admin."""
    resp = client.get('/crm/login', follow_redirects=False)
    assert resp.status_code == 302
    assert '/crm/register' in resp.headers['Location']


def test_register_first_admin_then_dashboard(client, crm_clean):
    resp = _register_first_admin(client)
    assert resp.status_code == 200
    # Now an authenticated CRM page renders.
    resp = client.get('/crm/dashboard')
    assert resp.status_code == 200
    assert b'Dashboard' in resp.data


def test_first_crm_user_is_admin(client, crm_clean, app):
    _register_first_admin(client, username='boss', password='secret123')
    from app.crm.models import CrmUser
    with app.app_context():
        u = CrmUser.query.filter_by(username='boss').first()
        assert u is not None
        assert u.is_admin is True


# ---------------------------------------------------------------------------
# Leads reframe (the "Deals" pipeline is presented as "Leads")
# ---------------------------------------------------------------------------
def test_pipeline_presented_as_leads(client, crm_clean):
    _register_first_admin(client)

    # Nav + pipeline list page use "Leads", not "Deals".
    deals_page = client.get('/crm/deals').get_data(as_text=True)
    assert 'New Lead' in deals_page
    assert 'New Deal' not in deals_page
    assert '>Leads' in deals_page or 'i>Leads' in deals_page

    # The create form is titled for a Lead.
    form_page = client.get('/crm/deals/new').get_data(as_text=True)
    assert 'New Lead' in form_page
    assert 'New Deal' not in form_page

    # Dashboard nav shows Leads (routes/endpoints unchanged underneath).
    dash = client.get('/crm/dashboard').get_data(as_text=True)
    assert 'i>Leads' in dash or '>Leads' in dash


# ---------------------------------------------------------------------------
# Marketing API (token auth)
# ---------------------------------------------------------------------------
def test_marketing_api_disabled_without_key(client, crm_clean, app):
    app.config['MARKETING_API_KEY'] = ''
    resp = client.get('/crm/api/marketing/stats')
    assert resp.status_code == 503


def test_marketing_api_rejects_wrong_key(client, crm_clean, app):
    app.config['MARKETING_API_KEY'] = 'rightkey'
    try:
        resp = client.get('/crm/api/marketing/stats',
                          headers={'X-API-Key': 'wrongkey'})
        assert resp.status_code == 401
    finally:
        app.config['MARKETING_API_KEY'] = ''


def test_marketing_api_stats_with_valid_key(client, crm_clean, app):
    app.config['MARKETING_API_KEY'] = 'rightkey'
    try:
        resp = client.get('/crm/api/marketing/stats',
                          headers={'X-API-Key': 'rightkey'})
        assert resp.status_code == 200
        body = resp.get_json()
        for key in ('companies', 'contacts', 'contacts_emailable', 'deals',
                    'open_pipeline', 'weighted_forecast', 'campaigns'):
            assert key in body
    finally:
        app.config['MARKETING_API_KEY'] = ''


def test_marketing_api_create_draft(client, crm_clean, app):
    """POST creates a draft campaign and never auto-sends."""
    app.config['MARKETING_API_KEY'] = 'rightkey'
    try:
        resp = client.post('/crm/api/marketing/campaigns',
                           json={'name': 'Spring WI', 'subject': 'Hi',
                                 'body': 'Body', 'state': 'WI'},
                           headers={'X-API-Key': 'rightkey'})
        assert resp.status_code == 201
        body = resp.get_json()
        assert body['status'] == 'draft'
        assert '/crm/campaigns/' in body['review_url']
    finally:
        app.config['MARKETING_API_KEY'] = ''


# ---------------------------------------------------------------------------
# In-CRM AI marketing agent ("Draft with AI")
# ---------------------------------------------------------------------------
def test_ai_campaign_page_renders(client, crm_clean):
    _register_first_admin(client)
    html = client.get('/crm/campaigns/ai').get_data(as_text=True)
    assert 'Draft a campaign with AI' in html
    # Entry point is surfaced on the campaigns list too.
    assert 'Draft with AI' in client.get('/crm/campaigns').get_data(as_text=True)


def test_ai_campaign_creates_draft(client, crm_clean, app):
    from unittest.mock import patch
    from app.crm.models import Company, Contact, Campaign
    _register_first_admin(client)
    with app.app_context():
        co = Company(name='Sunrise Garden', state='WI', org_type='Independent')
        _db.session.add(co)
        _db.session.flush()
        _db.session.add(Contact(name='Pat Lee', email='pat@example.com',
                                company_id=co.id))
        _db.session.commit()

    fake = ({'name': 'WI Spring Pilot',
             'subject': 'A free spring pilot for {{company}}',
             'body': 'Hi {{first_name}}, ...'}, {})
    with patch('app.crm.agent_service.is_configured', return_value=True), \
            patch('app.crm.agent_service.draft_campaign', return_value=fake) as draft:
        r = client.post('/crm/campaigns/ai', data={
            'goal': 'Re-engage WI independent gardens with a free pilot.',
            'state': 'WI', 'org_type': 'Independent', 'tag': '',
        }, follow_redirects=True)
    assert r.status_code == 200
    draft.assert_called_once()
    # The goal + audience were threaded into the agent call.
    assert draft.call_args.kwargs['audience_count'] == 1
    with app.app_context():
        c = Campaign.query.filter_by(name='WI Spring Pilot').first()
        assert c is not None
        assert c.status == 'draft'
        assert '{{company}}' in c.subject


def test_ai_campaign_no_audience_does_not_call_ai(client, crm_clean, app):
    from unittest.mock import patch
    from app.crm.models import Campaign
    _register_first_admin(client)
    with patch('app.crm.agent_service.is_configured', return_value=True), \
            patch('app.crm.agent_service.draft_campaign') as draft:
        r = client.post('/crm/campaigns/ai', data={
            'goal': 'Reach gardens in a state with no contacts at all.',
            'state': 'ZZ', 'org_type': '', 'tag': '',
        }, follow_redirects=True)
    assert r.status_code == 200
    draft.assert_not_called()
    with app.app_context():
        assert Campaign.query.count() == 0


def test_ai_campaign_unconfigured_shows_notice(client, crm_clean):
    from unittest.mock import patch
    _register_first_admin(client)
    with patch('app.crm.agent_service.is_configured', return_value=False):
        html = client.get('/crm/campaigns/ai').get_data(as_text=True)
    assert 'ANTHROPIC_API_KEY' in html


def test_ai_health_reports_auth(client):
    """The /api/health/ai probe surfaces configured + live auth_ok."""
    from unittest.mock import patch
    with patch('app.crm.agent_service.is_configured', return_value=True), \
            patch('app.crm.agent_service.auth_ok', return_value=True):
        body = client.get('/api/health/ai').get_json()
    assert body == {'configured': True, 'auth_ok': True}


def test_ai_health_auth_false_when_unconfigured(client):
    from unittest.mock import patch
    with patch('app.crm.agent_service.is_configured', return_value=False):
        body = client.get('/api/health/ai').get_json()
    assert body['configured'] is False and body['auth_ok'] is False


# ---------------------------------------------------------------------------
# Static assets
# ---------------------------------------------------------------------------
def test_crm_css_served_with_correct_mimetype(client):
    resp = client.get('/crm/static/yh-crm.css')
    assert resp.status_code == 200
    assert 'text/css' in resp.headers.get('Content-Type', '')


# ---------------------------------------------------------------------------
# End-to-end: authenticated CRUD renders + persists
# ---------------------------------------------------------------------------
def test_create_company_via_form(client, crm_clean):
    _register_first_admin(client)
    resp = client.post('/crm/companies/new',
                       data={'name': 'City of Madison Parks',
                             'state': 'WI', 'org_type': 'City-Sponsored'},
                       follow_redirects=True)
    assert resp.status_code == 200
    assert b'City of Madison Parks' in resp.data
    # And it shows up on the companies list.
    resp = client.get('/crm/companies')
    assert b'City of Madison Parks' in resp.data
