"""Twilio SMS service: config gating, the live auth probe, and /api/health/sms.

No real Twilio calls — the client is mocked. Verifies the wiring that lets ops
confirm SMS is live after the credentials are set on Render.
"""
from unittest import mock

from app import sms_service

_CREDS = {
    'TWILIO_ACCOUNT_SID': 'AC123',
    'TWILIO_AUTH_TOKEN': 'tok',
    'TWILIO_PHONE_NUMBER': '+15555550100',
}


def _set_creds(monkeypatch, **overrides):
    for k, v in {**_CREDS, **overrides}.items():
        monkeypatch.setenv(k, v)


def _clear_creds(monkeypatch):
    for k in _CREDS:
        monkeypatch.delenv(k, raising=False)


def test_is_configured_requires_all_three(monkeypatch):
    _clear_creds(monkeypatch)
    assert sms_service.is_configured() is False
    monkeypatch.setenv('TWILIO_ACCOUNT_SID', 'AC123')
    monkeypatch.setenv('TWILIO_AUTH_TOKEN', 'tok')
    assert sms_service.is_configured() is False          # still missing the number
    monkeypatch.setenv('TWILIO_PHONE_NUMBER', '+15555550100')
    assert sms_service.is_configured() is bool(sms_service.TWILIO_AVAILABLE)


def test_auth_ok_false_when_unconfigured(monkeypatch):
    _clear_creds(monkeypatch)
    assert sms_service.auth_ok() is False


def test_auth_ok_true_when_account_fetches(monkeypatch):
    _set_creds(monkeypatch)
    if not sms_service.TWILIO_AVAILABLE:
        return                                          # package absent — skip
    fake = mock.Mock()
    monkeypatch.setattr(sms_service, '_get_client', lambda: fake)
    assert sms_service.auth_ok() is True
    fake.api.accounts.assert_called_once_with('AC123')   # validated the right account


def test_auth_ok_false_on_bad_creds(monkeypatch):
    _set_creds(monkeypatch, TWILIO_AUTH_TOKEN='bad')
    if not sms_service.TWILIO_AVAILABLE:
        return
    fake = mock.Mock()
    fake.api.accounts.return_value.fetch.side_effect = Exception('401 unauthorized')
    monkeypatch.setattr(sms_service, '_get_client', lambda: fake)
    assert sms_service.auth_ok() is False


def test_send_sms_noop_when_unconfigured(monkeypatch):
    """Unconfigured → graceful no-op returning False (logged only, never raises)."""
    _clear_creds(monkeypatch)
    assert sms_service.send_sms('+15555551234', 'hi') is False


def test_health_sms_endpoint(client, monkeypatch):
    _clear_creds(monkeypatch)
    r = client.get('/api/health/sms')
    assert r.status_code == 200
    j = r.get_json()
    assert j['configured'] is False and j['auth_ok'] is False
    assert 'available' in j and 'from_number_set' in j and 'toggles' in j
