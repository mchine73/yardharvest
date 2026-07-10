"""Tests for the upgraded CRM marketing layer: segments, content calendar,
marketing hub, lead scoring, AI Studio (Claude mocked), and the hardened
ZeptoMail helpers."""
import json

import pytest

from app import db as _db
from app.crm import agent_service
from app import email_service


@pytest.fixture()
def crm_clean(app):
    """Wipe crm_* tables before each test so auth/state is deterministic."""
    from app.crm.models import (Activity, Campaign, CampaignRecipient, Company,
                                Contact, ContentItem, CrmUser, Deal,
                                DealContact, EmailTemplate, Note, Segment,
                                Task)
    with app.app_context():
        for model in (Activity, CampaignRecipient, ContentItem, Campaign,
                      Note, Task, DealContact, Deal, Contact, Segment,
                      Company, EmailTemplate, CrmUser):
            _db.session.query(model).delete()
        _db.session.commit()
    yield


@pytest.fixture()
def crm_admin(client, crm_clean):
    client.post('/crm/register',
                data={'username': 'crmadmin', 'password': 'secret123',
                      'confirm': 'secret123'},
                follow_redirects=True)
    yield client


@pytest.fixture()
def sample_org(app, crm_admin):
    from app.crm.models import Company, Contact
    with app.app_context():
        company = Company(name='Test Garden', city='Omaha', state='NE',
                          org_type='Independent')
        _db.session.add(company)
        _db.session.flush()
        contact = Contact(name='Jane Coordinator', email='jane@test.org',
                          company_id=company.id)
        _db.session.add(contact)
        _db.session.commit()
        return {'company': company.id, 'contact': contact.id}


SAMPLE_DESIGN = {
    "strategy_summary": "Target NE gardens before fiscal year end.",
    "campaign": {
        "name": "NE Spring Pilot",
        "subject": "Less admin this season, {{first_name}}?",
        "body": "Hi {{first_name}},\n\nSpring is busy at {{company}}...",
        "audience": {"state": "NE", "org_type": "", "tag": ""},
    },
    "content_plan": [
        {"title": "Teaser social post", "channel": "Social",
         "days_from_now": 0, "notes": "Tease the pilot offer."},
        {"title": "Follow-up email", "channel": "Email",
         "days_from_now": 7, "notes": "Nudge non-openers."},
        {"title": "Bogus item", "channel": "Skywriting",
         "days_from_now": 3, "notes": "Invalid channel - must be skipped."},
    ],
    "model": "claude-opus-4-8",
}


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
def test_new_marketing_tables_created(app):
    crm_tables = {t for t in _db.metadata.tables if t.startswith('crm_')}
    assert {'crm_segment', 'crm_content_item'} <= crm_tables


# ---------------------------------------------------------------------------
# Marketing hub
# ---------------------------------------------------------------------------
def test_marketing_hub_renders(crm_admin, sample_org):
    resp = crm_admin.get('/crm/marketing')
    assert resp.status_code == 200
    assert b'Marketing Hub' in resp.data
    assert b'Marketing Funnel' in resp.data


# ---------------------------------------------------------------------------
# Lead scoring
# ---------------------------------------------------------------------------
def test_contacts_list_shows_lead_score(crm_admin, sample_org):
    resp = crm_admin.get('/crm/contacts')
    assert resp.status_code == 200
    assert b'Lead Score' in resp.data
    assert b'score-pill' in resp.data


def test_lead_score_properties(app, sample_org):
    from app.crm.models import Contact
    with app.app_context():
        c = _db.session.get(Contact, sample_org['contact'])
        # email (15) + company (15) = 30 -> Warm
        assert c.lead_score == 30
        assert c.lead_grade == 'Warm'


# ---------------------------------------------------------------------------
# Segments
# ---------------------------------------------------------------------------
def test_segment_crud_and_campaign_prefill(crm_admin, sample_org, app):
    resp = crm_admin.post('/crm/segments/new', data={
        'name': 'Nebraska gardens', 'description': 'NE orgs',
        'state': 'NE', 'org_type': '', 'tag': '',
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b'Nebraska gardens' in resp.data

    from app.crm.models import Segment
    with app.app_context():
        seg = Segment.query.filter_by(name='Nebraska gardens').first()
        assert seg is not None and seg.state == 'NE'
        sid = seg.id

    # Launching a campaign from the segment prefills the audience filters
    resp = crm_admin.get(f'/crm/campaigns/new?segment={sid}')
    assert b'Nebraska gardens' in resp.data
    assert b'NE' in resp.data


# ---------------------------------------------------------------------------
# Content calendar
# ---------------------------------------------------------------------------
def test_content_calendar_and_item_crud(crm_admin, app):
    resp = crm_admin.get('/crm/content')
    assert resp.status_code == 200
    assert b'Content Calendar' in resp.data

    resp = crm_admin.post('/crm/content/new', data={
        'title': 'Spring newsletter', 'channel': 'Email', 'status': 'Idea',
        'scheduled_date': '', 'campaign': '0', 'body': 'Outline...',
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b'Spring newsletter' in resp.data  # appears in unscheduled list

    from app.crm.models import ContentItem
    with app.app_context():
        item = ContentItem.query.filter_by(title='Spring newsletter').first()
        assert item is not None and item.channel == 'Email'


# ---------------------------------------------------------------------------
# AI Studio (Claude mocked)
# ---------------------------------------------------------------------------
def test_ai_studio_page_renders(crm_admin):
    resp = crm_admin.get('/crm/ai')
    assert resp.status_code == 200
    assert b'AI Studio' in resp.data


def test_ai_generate_queues_campaign_proposal(crm_admin, sample_org, monkeypatch):
    """AI Studio designs run in the BACKGROUND (Opus blew the 30s gunicorn
    timeout synchronously) and land as a 'campaign' proposal in the approval
    queue — approving materializes the usual reviewable draft."""
    captured = {}

    def fake_design(goal, context, model=None):
        captured['goal'] = goal
        captured['context'] = context
        return dict(SAMPLE_DESIGN)

    monkeypatch.setattr(agent_service, 'is_configured', lambda: True)
    monkeypatch.setattr(agent_service, 'design_campaign', fake_design)
    resp = crm_admin.post('/crm/ai/generate', data={
        'goal': 'spring pilot push', 'state': 'NE', 'org_type': '', 'tag': '',
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert captured['goal'] == 'spring pilot push'
    assert captured['context']['constraints']['state'] == 'NE'
    from app.crm.models import CrmAgentAction
    a = CrmAgentAction.query.filter_by(status='pending',
                                       action_type='campaign').first()
    assert a is not None
    payload = json.loads(a.payload_json)
    assert payload['name'] == SAMPLE_DESIGN['campaign']['name']
    assert payload['audience_state'] == 'NE'


def test_ai_generate_requires_goal(crm_admin):
    resp = crm_admin.post('/crm/ai/generate', data={'goal': ''},
                          follow_redirects=True)
    assert b'Describe a campaign goal' in resp.data


def test_ai_generate_records_failed_run(crm_admin, monkeypatch):
    """A design failure is recorded as a FAILED agent run (surfaced on the
    console banner) instead of a silent 'found nothing' — the request itself
    has already returned by the time the background job errors."""
    monkeypatch.setattr(agent_service, 'is_configured', lambda: True)

    def boom(goal, context, model=None):
        raise agent_service.AgentError('Claude is rate-limited right now')
    monkeypatch.setattr(agent_service, 'design_campaign', boom)
    resp = crm_admin.post('/crm/ai/generate', data={'goal': 'anything'},
                          follow_redirects=True)
    assert resp.status_code == 200
    from app.crm.models import CrmAgentRun
    run = CrmAgentRun.query.order_by(CrmAgentRun.id.desc()).first()
    assert run is not None and run.kind == 'design'
    assert run.status == 'failed'
    assert 'rate-limited' in (run.error or '')


# --- AI email template agent -------------------------------------------------

def test_ai_draft_template_returns_json(crm_admin, monkeypatch):
    monkeypatch.setattr(agent_service, 'is_configured', lambda: True)
    monkeypatch.setattr(agent_service, 'draft_template',
                        lambda purpose, model=None: {
                            'name': 'Re-engage', 'subject': 'Hi {{first_name}}',
                            'body': 'Quick note for {{company}}.'})
    resp = crm_admin.post('/crm/templates/ai-draft',
                          json={'purpose': 'win back quiet contacts'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['subject'] == 'Hi {{first_name}}'
    assert '{{company}}' in data['body']


def test_ai_draft_template_requires_purpose(crm_admin, monkeypatch):
    monkeypatch.setattr(agent_service, 'is_configured', lambda: True)
    resp = crm_admin.post('/crm/templates/ai-draft', json={'purpose': '  '})
    assert resp.status_code == 400


def test_ai_draft_template_unconfigured(crm_admin, monkeypatch):
    monkeypatch.setattr(agent_service, 'is_configured', lambda: False)
    resp = crm_admin.post('/crm/templates/ai-draft', json={'purpose': 'x'})
    assert resp.status_code == 503


def test_ai_apply_creates_campaign_and_content(crm_admin, sample_org, app):
    resp = crm_admin.post('/crm/ai/apply',
                          data={'design': json.dumps(SAMPLE_DESIGN)},
                          follow_redirects=True)
    assert resp.status_code == 200
    from app.crm.models import Campaign, ContentItem
    with app.app_context():
        campaign = Campaign.query.filter_by(name='NE Spring Pilot').first()
        assert campaign is not None and campaign.status == 'draft'
        assert campaign.audience_desc == 'NE'
        items = ContentItem.query.filter_by(campaign_id=campaign.id).all()
        assert len(items) == 2  # invalid channel skipped
        assert {i.channel for i in items} == {'Social', 'Email'}


def test_ai_apply_rejects_malformed_design(crm_admin):
    resp = crm_admin.post('/crm/ai/apply', data={'design': 'not json'},
                          follow_redirects=True)
    assert b'Could not read the design' in resp.data


# ---------------------------------------------------------------------------
# ZeptoMail hardening (pure helpers)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize('configured,expected', [
    ('', 'https://api.zeptomail.com/v1.1/email'),
    ('https://api.zeptomail.com', 'https://api.zeptomail.com/v1.1/email'),
    ('api.zeptomail.com', 'https://api.zeptomail.com/v1.1/email'),
    ('https://api.zeptomail.com/v1.1', 'https://api.zeptomail.com/v1.1/email'),
    ('https://api.zeptomail.com/v1.1/email',
     'https://api.zeptomail.com/v1.1/email'),
    ('https://api.zeptomail.eu', 'https://api.zeptomail.eu/v1.1/email'),
])
def test_zepto_api_url_normalization(configured, expected):
    assert email_service._zepto_api_url(configured) == expected


@pytest.mark.parametrize('raw,expected', [
    ('abc123', 'Zoho-enczapikey abc123'),
    ('Zoho-enczapikey abc123', 'Zoho-enczapikey abc123'),
    ('"abc123"', 'Zoho-enczapikey abc123'),
    ('Authorization: Zoho-enczapikey abc123', 'Zoho-enczapikey abc123'),
    ('  abc123  ', 'Zoho-enczapikey abc123'),
])
def test_zepto_auth_header_tolerates_paste_artifacts(raw, expected):
    assert email_service._zepto_auth_header(raw) == expected


# ---------------------------------------------------------------------------
# Prospect -> Lead conversion
# ---------------------------------------------------------------------------
def test_convert_company_to_lead(crm_admin, app):
    from app.crm.models import Company, Deal
    with app.app_context():
        c = Company(name='Prospect Org', tags='Prospect, Omaha')
        _db.session.add(c)
        _db.session.commit()
        cid = c.id
    resp = crm_admin.post(f'/crm/companies/{cid}/convert', follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        deal = Deal.query.filter_by(company_id=cid).first()
        assert deal is not None and deal.stage == 'Lead'
        c = _db.session.get(Company, cid)
        assert 'prospect' not in (c.tags or '').lower()  # tag swapped
        assert 'lead' in (c.tags or '').lower()
