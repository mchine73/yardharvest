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
    assert 'pages_manage_posts' in u and 'pages_messaging' in u


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
