"""The CRM email drafters run synchronously inside a web request, so they use a
faster model (Sonnet 4.6) than the Opus default to stay under the request
timeout. These tests pin that split and verify each drafter passes the model.

A fake ``anthropic`` module is injected so no network call (or real SDK) is
needed; we capture the ``model`` argument each drafter sends.
"""
import json
import sys
import types

from app.crm import agent_service


def _install_fake_anthropic(monkeypatch, capture):
    fake = types.ModuleType('anthropic')

    class _Block:
        type = 'text'

        def __init__(self, text):
            self.text = text

    class _Resp:
        def __init__(self, text):
            self.content = [_Block(text)]
            self.stop_reason = 'end_turn'
            self.usage = None
            self.model = 'fake'

    class _Messages:
        def create(self, **kwargs):
            capture['model'] = kwargs.get('model')
            capture['kwargs'] = kwargs
            return _Resp(capture['response_json'])

    class Anthropic:
        def __init__(self, *a, **k):
            self.messages = _Messages()

    fake.Anthropic = Anthropic
    monkeypatch.setitem(sys.modules, 'anthropic', fake)


def test_email_model_split_constants():
    assert agent_service.EMAIL_MODEL == 'claude-sonnet-4-6'
    assert agent_service.DEFAULT_MODEL == 'claude-opus-4-8'


def test_draft_followups_uses_email_model(monkeypatch):
    monkeypatch.setattr(agent_service, 'is_configured', lambda: True)
    capture = {'response_json': json.dumps({'drafts': [{
        'lead_id': 1, 'title': 'Follow up', 'rationale': 'because',
        'subject': 'Hi', 'body': 'Body'}]})}
    _install_fake_anthropic(monkeypatch, capture)
    leads = [{'lead_id': 1, 'name': 'Pat', 'company': 'Maple', 'city': 'Lincoln',
              'state': 'NE', 'org_type': 'Independent', 'lead_status': 'New',
              'days_since_contact': None, 'recent': []}]
    drafts, _u = agent_service.draft_followups(leads)
    assert capture['model'] == 'claude-sonnet-4-6'
    assert drafts and drafts[0]['subject'] == 'Hi'


def test_draft_campaign_uses_email_model(monkeypatch):
    monkeypatch.setattr(agent_service, 'is_configured', lambda: True)
    capture = {'response_json': json.dumps({
        'name': 'C', 'subject': 'S', 'body': 'B'})}
    _install_fake_anthropic(monkeypatch, capture)
    camp, _u = agent_service.draft_campaign('introduce us', audience_count=5)
    assert capture['model'] == 'claude-sonnet-4-6'
    assert camp['subject'] == 'S'


def test_draft_template_uses_email_model(monkeypatch):
    monkeypatch.setattr(agent_service, 'is_configured', lambda: True)
    capture = {'response_json': json.dumps({
        'name': 'T', 'subject': 'S', 'body': '<p>B</p>'})}
    _install_fake_anthropic(monkeypatch, capture)
    tmpl = agent_service.draft_template('a welcome note')
    assert capture['model'] == 'claude-sonnet-4-6'
    assert tmpl['name'] == 'T'


def test_scout_new_leads_uses_opus_websearch_and_guards_fabrication(monkeypatch):
    """Net-new scout runs on Opus 4.8 with the web_search tool, parses the JSON
    array, and drops any lead lacking a real source_url (no-fabrication guard)."""
    monkeypatch.setattr(agent_service, 'is_configured', lambda: True)
    capture = {'response_json': json.dumps([
        {'name': 'Maple Roots Garden', 'city': 'Lincoln', 'state': 'NE',
         'org_type': 'Independent', 'website': 'https://maple.org',
         'contact_name': 'Pat', 'contact_email': 'pat@maple.org',
         'contact_title': 'Coordinator', 'fit': 'Independent garden, plots + dues.',
         'source_url': 'https://maple.org/about'},
        {'name': 'No Source Garden', 'city': 'X', 'state': 'NE',
         'org_type': 'Independent', 'website': '', 'contact_name': '',
         'contact_email': '', 'contact_title': '', 'fit': 'x', 'source_url': ''},
    ])}
    _install_fake_anthropic(monkeypatch, capture)
    leads, _u = agent_service.scout_new_leads(count=5)
    assert capture['model'] == 'claude-opus-4-8'
    tools = capture['kwargs'].get('tools', [])
    assert any('web_search' in (t.get('type', '')) for t in tools)
    # The lead with no source_url is dropped; the cited one survives.
    assert [l['name'] for l in leads] == ['Maple Roots Garden']
    assert leads[0]['source_url'] == 'https://maple.org/about'


def test_agent_prompts_include_booking_page(monkeypatch):
    """The BDR agent's skills know the scheduling page: the shared brand voice
    (system prompt for every skill) and the follow-up drafting prompt both
    carry https://www.yardharvest.app/book as the meeting CTA."""
    assert 'https://www.yardharvest.app/book' in agent_service.BRAND_VOICE

    monkeypatch.setattr(agent_service, 'is_configured', lambda: True)
    capture = {'response_json': json.dumps({'drafts': [{
        'lead_id': 1, 'title': 'Follow up', 'rationale': 'because',
        'subject': 'Hi', 'body': '<p>Body</p>'}]})}
    _install_fake_anthropic(monkeypatch, capture)
    agent_service.draft_followups([{'lead_id': 1, 'name': 'Pat', 'company': 'Maple',
                                    'city': 'Lincoln', 'state': 'NE',
                                    'org_type': 'Independent', 'lead_status': 'New',
                                    'days_since_contact': None, 'recent': []}])
    user_prompt = capture['kwargs']['messages'][0]['content']
    assert 'https://www.yardharvest.app/book' in user_prompt
    system_text = capture['kwargs']['system'][0]['text']
    assert 'https://www.yardharvest.app/book' in system_text


def test_estimate_cost():
    """Cost estimate combines token prices + web-search price; unknown model
    falls back to Opus rates."""
    # 1M opus in ($5) + 1M out ($25) + 1000 web searches ($10) = $40.
    assert abs(agent_service.estimate_cost('claude-opus-4-8', 1_000_000, 1_000_000, 1000) - 40.0) < 0.01
    assert agent_service.estimate_cost('claude-sonnet-4-6', 1_000_000, 0, 0) == 3.0
    assert agent_service.estimate_cost('made-up-model', 1_000_000, 0, 0) == 5.0   # opus fallback
    assert agent_service.estimate_cost(None, 0, 0, 0) == 0.0


def test_scout_keeps_default_opus_model(monkeypatch):
    """Non-email skills stay on the Opus default."""
    monkeypatch.setattr(agent_service, 'is_configured', lambda: True)
    capture = {'response_json': json.dumps({'picks': [{
        'lead_id': 1, 'title': 'Prospect Maple', 'rationale': 'fit', 'angle': 'hook'}]})}
    _install_fake_anthropic(monkeypatch, capture)
    picks, _u = agent_service.scout_leads([{'lead_id': 1, 'company': 'Maple',
                                            'city': 'Lincoln', 'state': 'NE',
                                            'org_type': 'Independent', 'name': 'Pat',
                                            'website': None}])
    assert capture['model'] == 'claude-opus-4-8'
    assert picks and picks[0]['lead_id'] == 1
