"""Tests for the CRM ↔ Facebook integration (Slice 1): service helpers, the
settings page, and the webhook (handshake verify + signed message ingestion).
Graph API network calls are never made here."""
import hashlib
import hmac
import json

import pytest

from app import db as _db
from app.crm import facebook_service as fb


@pytest.fixture()
def crm_admin(client):
    from app.crm.models import (CrmUser, CrmFacebookAccount, CrmFacebookMessage,
                                CrmFacebookPost)
    with client.application.app_context():
        for model in (CrmFacebookMessage, CrmFacebookPost, CrmFacebookAccount, CrmUser):
            _db.session.query(model).delete()
        _db.session.commit()
    client.post('/crm/register',
                data={'username': 'fbadmin', 'password': 'secret123',
                      'confirm': 'secret123'},
                follow_redirects=True)
    return client


# --- service helpers --------------------------------------------------------
def test_is_configured(monkeypatch):
    monkeypatch.delenv('FACEBOOK_APP_ID', raising=False)
    monkeypatch.delenv('FACEBOOK_APP_SECRET', raising=False)
    assert not fb.is_configured()
    monkeypatch.setenv('FACEBOOK_APP_ID', 'a')
    monkeypatch.setenv('FACEBOOK_APP_SECRET', 'b')
    assert fb.is_configured()


def test_oauth_url(monkeypatch):
    monkeypatch.setenv('FACEBOOK_APP_ID', 'APPID')
    u = fb.oauth_url('https://www.yardharvest.app/crm/facebook/callback', 'STATE123')
    assert 'client_id=APPID' in u
    assert 'state=STATE123' in u
    # pages_messaging is intentionally omitted (needs Meta's Messaging use case).
    assert 'pages_manage_posts' in u and 'pages_messaging' not in u


def test_verify_webhook_challenge(monkeypatch):
    monkeypatch.setenv('FACEBOOK_WEBHOOK_VERIFY_TOKEN', 'tok')
    assert fb.verify_webhook_challenge('subscribe', 'tok', '99') == '99'
    assert fb.verify_webhook_challenge('subscribe', 'wrong', '99') is None
    assert fb.verify_webhook_challenge('unsubscribe', 'tok', '99') is None


def test_verify_signature(monkeypatch):
    monkeypatch.setenv('FACEBOOK_APP_SECRET', 'sek')
    body = b'{"hello":"world"}'
    good = 'sha256=' + hmac.new(b'sek', body, hashlib.sha256).hexdigest()
    assert fb.verify_signature(body, good)
    assert not fb.verify_signature(body, 'sha256=deadbeef')
    assert not fb.verify_signature(body, '')


# --- settings page ----------------------------------------------------------
def test_settings_page_unconfigured(crm_admin, monkeypatch):
    monkeypatch.delenv('FACEBOOK_APP_ID', raising=False)
    monkeypatch.delenv('FACEBOOK_APP_SECRET', raising=False)
    resp = crm_admin.get('/crm/facebook')
    assert resp.status_code == 200
    assert b'Facebook Integration' in resp.data
    assert b'Not configured' in resp.data


def test_settings_page_configured_shows_connect(crm_admin, monkeypatch):
    monkeypatch.setenv('FACEBOOK_APP_ID', 'a')
    monkeypatch.setenv('FACEBOOK_APP_SECRET', 'b')
    resp = crm_admin.get('/crm/facebook')
    assert resp.status_code == 200
    assert b'Connect Facebook Page' in resp.data


# --- webhook ----------------------------------------------------------------
def test_webhook_challenge_roundtrip(client, monkeypatch):
    monkeypatch.setenv('FACEBOOK_WEBHOOK_VERIFY_TOKEN', 'verifyme')
    ok = client.get('/crm/api/facebook/webhook?hub.mode=subscribe'
                    '&hub.verify_token=verifyme&hub.challenge=314159')
    assert ok.status_code == 200 and ok.get_data(as_text=True) == '314159'
    bad = client.get('/crm/api/facebook/webhook?hub.mode=subscribe'
                     '&hub.verify_token=nope&hub.challenge=314159')
    assert bad.status_code == 403


def test_webhook_rejects_bad_signature(client, monkeypatch):
    monkeypatch.setenv('FACEBOOK_APP_SECRET', 'sek')
    resp = client.post('/crm/api/facebook/webhook', data=b'{}',
                       headers={'X-Hub-Signature-256': 'sha256=bad',
                                'Content-Type': 'application/json'})
    assert resp.status_code == 403


def test_webhook_ingests_signed_message(client, app, monkeypatch):
    from app.crm.models import CrmFacebookMessage
    monkeypatch.setenv('FACEBOOK_APP_SECRET', 'sek')
    payload = {'object': 'page', 'entry': [{'messaging': [{
        'sender': {'id': 'psid_1'}, 'timestamp': 1700000000000,
        'message': {'mid': 'mid_abc', 'text': 'Hello from a customer'},
    }]}]}
    raw = json.dumps(payload).encode()
    sig = 'sha256=' + hmac.new(b'sek', raw, hashlib.sha256).hexdigest()
    resp = client.post('/crm/api/facebook/webhook', data=raw,
                       headers={'X-Hub-Signature-256': sig,
                                'Content-Type': 'application/json'})
    assert resp.status_code == 200
    with app.app_context():
        m = CrmFacebookMessage.query.filter_by(fb_message_id='mid_abc').first()
        assert m is not None
        assert m.direction == 'in' and m.text == 'Hello from a customer'
        assert m.sender_id == 'psid_1'


# --- publishing / scheduling / inbox (Slice 2 & 3) --------------------------
@pytest.fixture()
def connected(crm_admin, monkeypatch):
    monkeypatch.setenv('FACEBOOK_APP_ID', 'a')
    monkeypatch.setenv('FACEBOOK_APP_SECRET', 'b')
    from app.crm.models import CrmFacebookAccount
    with crm_admin.application.app_context():
        _db.session.add(CrmFacebookAccount(
            page_id='pg1', page_name='Test Page',
            page_access_token='tok', active=True))
        _db.session.commit()
    return crm_admin


def test_compose_publish_now(connected, monkeypatch):
    from app.crm import facebook_service as fb_svc
    from app.crm.models import CrmFacebookPost
    monkeypatch.setattr(fb_svc, 'publish_post', lambda *a, **k: 'pg1_post1')
    resp = connected.post('/crm/facebook/compose',
                          data={'message': 'Hello world', 'action': 'publish'},
                          follow_redirects=True)
    assert resp.status_code == 200
    with connected.application.app_context():
        p = CrmFacebookPost.query.first()
        assert p.status == 'published' and p.fb_post_id == 'pg1_post1'


def test_compose_schedule(connected):
    from app.crm.models import CrmFacebookPost
    connected.post('/crm/facebook/compose',
                   data={'message': 'Later', 'action': 'schedule',
                         'scheduled_for': '2030-01-01T09:00'},
                   follow_redirects=True)
    with connected.application.app_context():
        p = CrmFacebookPost.query.filter_by(status='scheduled').first()
        assert p is not None and p.scheduled_for is not None


def test_publish_scheduled_posts_runs(connected, monkeypatch):
    from datetime import datetime, timezone, timedelta
    from app.crm import facebook_service as fb_svc
    from app.crm.facebook_views import publish_scheduled_posts
    from app.crm.models import CrmFacebookPost
    monkeypatch.setattr(fb_svc, 'publish_post', lambda *a, **k: 'pid')
    past = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
    with connected.application.app_context():
        _db.session.add(CrmFacebookPost(
            message='due', status='scheduled', scheduled_for=past))
        _db.session.commit()
        assert publish_scheduled_posts() == 1
        assert CrmFacebookPost.query.filter_by(status='published').count() == 1


def test_ai_draft_route(crm_admin, monkeypatch):
    from app.crm import agent_service
    monkeypatch.setattr(agent_service, 'is_configured', lambda: True)
    monkeypatch.setattr(agent_service, 'draft_facebook_post',
                        lambda purpose, model=None: {'message': 'Drafted!', 'link': ''})
    resp = crm_admin.post('/crm/facebook/ai-draft', json={'purpose': 'spring sale'})
    assert resp.status_code == 200
    assert resp.get_json()['message'] == 'Drafted!'


def test_ai_draft_requires_purpose(crm_admin, monkeypatch):
    from app.crm import agent_service
    monkeypatch.setattr(agent_service, 'is_configured', lambda: True)
    assert crm_admin.post('/crm/facebook/ai-draft', json={'purpose': '  '}).status_code == 400


def test_reply_sends_and_logs(connected, monkeypatch):
    from app.crm import facebook_service as fb_svc
    from app.crm.models import CrmFacebookMessage
    sent = {}
    monkeypatch.setattr(fb_svc, 'send_message',
                        lambda page_id, tok, rid, text: sent.update(rid=rid, text=text) or {'ok': 1})
    resp = connected.post('/crm/facebook/reply',
                          data={'sender_id': 'psid9', 'text': 'hi back'},
                          follow_redirects=True)
    assert resp.status_code == 200 and sent['rid'] == 'psid9'
    with connected.application.app_context():
        assert CrmFacebookMessage.query.filter_by(direction='out', sender_id='psid9').count() == 1


def test_posts_and_inbox_render(connected):
    assert connected.get('/crm/facebook/posts').status_code == 200
    assert connected.get('/crm/facebook/inbox').status_code == 200


def test_compose_page_renders_with_photo_field(connected):
    r = connected.get('/crm/facebook/compose')
    assert r.status_code == 200
    assert b'image_url' in r.data and b'Photo' in r.data


# --- rich drafts + photos + agent man-in-the-middle (Slice 4) ----------------
def test_fb_post_schema_has_rich_fields():
    from app.crm import agent_service
    props = agent_service.FB_POST_SCHEMA['properties']
    assert {'message', 'link', 'hashtags', 'image_idea', 'alternates'} <= set(props)


def test_clean_hashtags_normalizes():
    from app.crm.agent_service import _clean_hashtags
    out = _clean_hashtags(['garden', '#Garden', '  community ', '#', '', 'a', 'b', 'c', 'd'])
    # leading '#', de-spaced, case-insensitive dedupe, capped at 5
    assert out[:2] == ['#garden', '#community']
    assert all(h.startswith('#') for h in out)
    assert len(out) <= 5


def test_publish_post_uses_photos_when_image(monkeypatch):
    calls = []
    monkeypatch.setattr(fb, '_post',
                        lambda path, params=None, data=None: (calls.append((path, data))
                                                              or {'id': 'photo1', 'post_id': 'pg_story1'}))
    pid = fb.publish_post('pg1', 'tok', 'hello', link='https://x.com', image_url='https://img/x.jpg')
    assert calls[0][0] == '/pg1/photos'
    assert calls[0][1]['url'] == 'https://img/x.jpg'
    assert calls[0][1]['caption'].startswith('hello')
    assert 'https://x.com' in calls[0][1]['caption']   # link folded into caption
    assert pid == 'pg_story1'                            # story id, not photo id


def test_publish_post_uses_feed_without_image(monkeypatch):
    calls = []
    monkeypatch.setattr(fb, '_post',
                        lambda path, params=None, data=None: (calls.append((path, data))
                                                              or {'id': 'pg_feed1'}))
    pid = fb.publish_post('pg1', 'tok', 'hello', link='https://x.com')
    assert calls[0][0] == '/pg1/feed'
    assert calls[0][1]['link'] == 'https://x.com'
    assert pid == 'pg_feed1'


def test_compose_publish_with_image(connected, monkeypatch):
    from app.crm import facebook_service as fb_svc
    from app.crm.models import CrmFacebookPost
    seen = {}
    monkeypatch.setattr(fb_svc, 'publish_post',
                        lambda pid, tok, msg, link=None, image_url=None:
                        seen.update(image_url=image_url) or 'pg1_p2')
    resp = connected.post('/crm/facebook/compose',
                          data={'message': 'Pic post', 'image_url': 'https://img/a.jpg',
                                'action': 'publish'},
                          follow_redirects=True)
    assert resp.status_code == 200
    with connected.application.app_context():
        p = CrmFacebookPost.query.filter_by(message='Pic post').first()
        assert p is not None and p.image_url == 'https://img/a.jpg' and p.status == 'published'
    assert seen['image_url'] == 'https://img/a.jpg'


def test_agent_proposes_and_approves_facebook_post(connected, monkeypatch):
    from app.crm import agent_service
    from app.crm import facebook_service as fb_svc
    from app.crm.models import CrmAgentAction, CrmFacebookPost
    monkeypatch.setattr(agent_service, 'is_configured', lambda: True)
    monkeypatch.setattr(agent_service, 'propose_facebook_posts',
                        lambda **k: ([{'title': 'Spring sale', 'rationale': 'spring',
                                       'message': 'Come!', 'link': '',
                                       'hashtags': ['#garden'], 'image_idea': 'tomatoes',
                                       'alternates': []}], {}))
    r = connected.post('/crm/agent/facebook', follow_redirects=True)
    # The redirected agent console must render the facebook_post editor card.
    assert r.status_code == 200 and b'Approve' in r.data
    with connected.application.app_context():
        act = (CrmAgentAction.query
               .filter_by(action_type='facebook_post', status='pending').first())
        assert act is not None and act.payload['message'] == 'Come!'
        aid = act.id

    monkeypatch.setattr(fb_svc, 'publish_post', lambda *a, **k: 'pg1_p9')
    connected.post(f'/crm/agent/actions/{aid}/approve',
                   data={'message': 'Come now!', 'image_url': 'https://img/z.jpg'},
                   follow_redirects=True)
    with connected.application.app_context():
        p = CrmFacebookPost.query.filter_by(message='Come now!').first()
        assert p is not None and p.image_url == 'https://img/z.jpg' and p.status == 'published'
        assert _db.session.get(CrmAgentAction, aid).status == 'executed'
