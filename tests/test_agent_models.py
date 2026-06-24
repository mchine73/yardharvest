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
