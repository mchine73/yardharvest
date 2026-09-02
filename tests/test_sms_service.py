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


# ---------------------------------------------------------------------------
# The setup probe
# ---------------------------------------------------------------------------
# `configured` is an AND of three variables, so a missing SID and a missing
# from-number looked identical from outside — exactly when you need to tell
# them apart, and the only way to see an env var that never reached the
# process. Presence only; the probe never echoes a value.

def test_the_probe_names_which_variable_is_missing(client, monkeypatch):
    monkeypatch.setenv('TWILIO_ACCOUNT_SID', 'ACtest')
    monkeypatch.delenv('TWILIO_AUTH_TOKEN', raising=False)
    monkeypatch.setenv('TWILIO_PHONE_NUMBER', '+14025551234')

    body = client.get('/api/health/sms').get_json()
    assert body['account_sid_set'] is True
    assert body['auth_token_set'] is False
    assert body['from_number_set'] is True
    assert body['configured'] is False


def test_a_from_number_twilio_would_reject_is_caught_at_setup(client, monkeypatch):
    from app import sms_service
    monkeypatch.setattr(sms_service, 'auth_detail', lambda: (False, 'stubbed'))
    """A number pasted with dashes or parentheses is the likeliest reason a
    fully "configured" account fails at send time with a useless error."""
    monkeypatch.setenv('TWILIO_ACCOUNT_SID', 'ACtest')
    monkeypatch.setenv('TWILIO_AUTH_TOKEN', 'tok')
    monkeypatch.setenv('TWILIO_PHONE_NUMBER', '(402) 555-1234')

    body = client.get('/api/health/sms').get_json()
    assert body['from_number_set'] is True
    assert body['from_number_is_e164'] is False


def test_a_good_number_passes_the_format_check(client, monkeypatch):
    from app import sms_service
    monkeypatch.setattr(sms_service, 'auth_detail', lambda: (False, 'stubbed'))
    monkeypatch.setenv('TWILIO_ACCOUNT_SID', 'ACtest')
    monkeypatch.setenv('TWILIO_AUTH_TOKEN', 'tok')
    monkeypatch.setenv('TWILIO_PHONE_NUMBER', '+14025551234')
    assert client.get('/api/health/sms').get_json()['from_number_is_e164'] is True


def test_the_probe_never_echoes_a_credential(client, monkeypatch):
    """Now that the probe reports Twilio's error text, this guards that too."""
    from app import sms_service
    monkeypatch.setenv('TWILIO_ACCOUNT_SID', 'ACsecretsid')
    monkeypatch.setenv('TWILIO_AUTH_TOKEN', 'supersecrettoken')
    monkeypatch.setenv('TWILIO_PHONE_NUMBER', '+14025551234')
    monkeypatch.setattr(sms_service, 'auth_detail',
                        lambda: (False, 'TwilioRestException: HTTP 401 error'))

    raw = client.get('/api/health/sms').get_data(as_text=True)
    assert 'ACsecretsid' not in raw
    assert 'supersecrettoken' not in raw


def test_a_rejected_credential_says_why(client, monkeypatch):
    """Returning a bare False was a dead end: credentials present, Twilio
    refusing them, no way to tell a rotated token from the wrong account."""
    from app import sms_service
    monkeypatch.setenv('TWILIO_ACCOUNT_SID', 'ACtest')
    monkeypatch.setenv('TWILIO_AUTH_TOKEN', 'tok')
    monkeypatch.setenv('TWILIO_PHONE_NUMBER', '+14025551234')
    monkeypatch.setattr(
        sms_service, 'auth_detail',
        lambda: (False, 'TwilioRestException: HTTP 401 error: Authentication Error'))

    body = client.get('/api/health/sms').get_json()
    assert body['auth_ok'] is False
    assert 'Authentication Error' in body['error']


def test_an_api_key_sid_is_caught_without_a_network_call(client, monkeypatch):
    """An API Key SID starts SK, an Account SID starts AC. Pasting the wrong
    one is the commonest setup mistake and needs no round trip to spot."""
    from app import sms_service
    monkeypatch.setenv('TWILIO_ACCOUNT_SID', 'SK0123456789abcdef')
    monkeypatch.setenv('TWILIO_AUTH_TOKEN', 'tok')
    monkeypatch.setenv('TWILIO_PHONE_NUMBER', '+14025551234')
    monkeypatch.setattr(sms_service, 'auth_detail', lambda: (False, 'nope'))

    assert client.get('/api/health/sms').get_json()['account_sid_looks_right'] is False


def test_a_credential_pasted_with_a_trailing_newline_still_works(monkeypatch):
    """Dashboard fields collect trailing whitespace, and it is invisible: the
    variable is plainly set and Twilio simply rejects it."""
    from app import sms_service
    monkeypatch.setenv('TWILIO_ACCOUNT_SID', 'ACtest\n')
    monkeypatch.setenv('TWILIO_AUTH_TOKEN', ' tok ')
    monkeypatch.setenv('TWILIO_PHONE_NUMBER', '+14025551234\n')
    assert sms_service._cred('TWILIO_ACCOUNT_SID') == 'ACtest'
    assert sms_service._cred('TWILIO_AUTH_TOKEN') == 'tok'
    assert sms_service._cred('TWILIO_PHONE_NUMBER') == '+14025551234'
