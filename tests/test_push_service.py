"""Push routing: iOS tokens go to APNs, Android tokens to FCM HTTP v1."""
import json
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa

from app import push_service


@pytest.fixture(scope='module')
def rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in ('APNS_TEAM_ID', 'APNS_KEY_ID', 'APNS_PRIVATE_KEY', 'APNS_PRIVATE_KEY_FILE',
              'FCM_SERVICE_ACCOUNT_JSON', 'FCM_SERVICE_ACCOUNT_FILE'):
        monkeypatch.delenv(k, raising=False)
    push_service._fcm_cache.update(token=None, exp=0.0)
    push_service._jwt_cache.update(token=None, iat=0.0)


def _service_account(rsa_key):
    pem = rsa_key.private_bytes(serialization.Encoding.PEM,
                                serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption()).decode()
    return {'type': 'service_account', 'project_id': 'yardharvest-test',
            'private_key_id': 'kid123', 'private_key': pem,
            'client_email': 'push@yardharvest-test.iam.gserviceaccount.com'}


def _configure_fcm(monkeypatch, rsa_key):
    monkeypatch.setenv('FCM_SERVICE_ACCOUNT_JSON', json.dumps(_service_account(rsa_key)))


def _configure_apns(monkeypatch):
    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(serialization.Encoding.PEM,
                            serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()
    monkeypatch.setenv('APNS_TEAM_ID', 'TEAM')
    monkeypatch.setenv('APNS_KEY_ID', 'KEY')
    monkeypatch.setenv('APNS_PRIVATE_KEY', pem)


class _Resp:
    def __init__(self, status_code, body=None):
        self.status_code = status_code
        self._body = body or {}

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f'HTTP {self.status_code}')


class _FakeGoogle:
    """Stands in for httpx.post: the OAuth exchange, then FCM sends."""

    def __init__(self, send_status=200, send_body=None):
        self.oauth_calls = []
        self.sends = []
        self.send_status = send_status
        self.send_body = send_body

    def __call__(self, url, **kw):
        if url == push_service.GOOGLE_TOKEN_URL:
            self.oauth_calls.append(kw['data'])
            return _Resp(200, {'access_token': 'ya29.test', 'expires_in': 3600})
        self.sends.append((url, kw))
        return _Resp(self.send_status, self.send_body)


def _android_user(**kw):
    return SimpleNamespace(id=1, device_token='fcm-token', device_platform='android', **kw)


def test_each_platform_is_configured_on_its_own(monkeypatch, rsa_key):
    assert not push_service.is_configured()
    _configure_fcm(monkeypatch, rsa_key)
    assert push_service.fcm_configured() and push_service.is_configured()
    assert not push_service.apns_configured()


def test_android_push_goes_to_fcm_v1(monkeypatch, rsa_key):
    _configure_fcm(monkeypatch, rsa_key)
    google = _FakeGoogle()
    monkeypatch.setattr('httpx.post', google)

    ok = push_service.send_push(_android_user(), 'Plot assigned', body='Bed 4 is yours',
                                link='/gardens/7', garden_id=7, badge=3, ntype='plot_assigned')

    assert ok is True
    url, kw = google.sends[0]
    assert url == 'https://fcm.googleapis.com/v1/projects/yardharvest-test/messages:send'
    assert kw['headers']['authorization'] == 'Bearer ya29.test'
    message = kw['json']['message']
    assert message['token'] == 'fcm-token'
    assert message['notification'] == {'title': 'Plot assigned', 'body': 'Bed 4 is yours'}
    # Data values must all be strings, with the keys the app routes on.
    assert message['data'] == {'type': 'plot_assigned', 'link': '/gardens/7', 'garden_id': '7'}
    assert message['android']['notification'] == {'channel_id': 'garden_updates',
                                                  'notification_count': 3}


def test_the_oauth_assertion_is_a_signed_service_account_jwt(monkeypatch, rsa_key):
    _configure_fcm(monkeypatch, rsa_key)
    google = _FakeGoogle()
    monkeypatch.setattr('httpx.post', google)
    push_service.send_push(_android_user(), 'Hi')

    form = google.oauth_calls[0]
    assert form['grant_type'] == 'urn:ietf:params:oauth:grant-type:jwt-bearer'
    claims = jwt.decode(form['assertion'], rsa_key.public_key(), algorithms=['RS256'],
                        audience=push_service.GOOGLE_TOKEN_URL)
    assert claims['iss'] == 'push@yardharvest-test.iam.gserviceaccount.com'
    assert claims['scope'] == push_service.FCM_SCOPE
    assert jwt.get_unverified_header(form['assertion'])['kid'] == 'kid123'


def test_the_access_token_is_reused_across_sends(monkeypatch, rsa_key):
    _configure_fcm(monkeypatch, rsa_key)
    google = _FakeGoogle()
    monkeypatch.setattr('httpx.post', google)
    push_service.send_push(_android_user(), 'One')
    push_service.send_push(_android_user(), 'Two')
    assert len(google.oauth_calls) == 1
    assert len(google.sends) == 2


@pytest.mark.parametrize('code', ['UNREGISTERED', 'SENDER_ID_MISMATCH'])
def test_a_dead_fcm_token_is_cleared_without_committing(monkeypatch, rsa_key, code):
    _configure_fcm(monkeypatch, rsa_key)
    body = {'error': {'code': 404, 'status': 'NOT_FOUND', 'details': [
        {'@type': 'type.googleapis.com/google.firebase.fcm.v1.FcmError', 'errorCode': code}]}}
    monkeypatch.setattr('httpx.post', _FakeGoogle(send_status=404, send_body=body))
    user = _android_user()
    assert push_service.send_push(user, 'Hi') is False
    assert user.device_token is None


def test_a_transient_fcm_failure_keeps_the_token(monkeypatch, rsa_key):
    _configure_fcm(monkeypatch, rsa_key)
    body = {'error': {'code': 503, 'status': 'UNAVAILABLE'}}
    monkeypatch.setattr('httpx.post', _FakeGoogle(send_status=503, send_body=body))
    user = _android_user()
    assert push_service.send_push(user, 'Hi') is False
    assert user.device_token == 'fcm-token'


def test_a_broken_key_never_raises(monkeypatch):
    monkeypatch.setenv('FCM_SERVICE_ACCOUNT_JSON', '{"project_id": "x"}')
    assert push_service.send_push(_android_user(), 'Hi') is False


def test_android_tokens_are_never_sent_to_apple(monkeypatch):
    _configure_apns(monkeypatch)

    def no_network(*a, **kw):
        raise AssertionError('no request expected')
    monkeypatch.setattr('httpx.post', no_network)
    monkeypatch.setattr('httpx.Client', no_network)
    assert push_service.send_push(_android_user(), 'Hi') is False


def test_ios_tokens_still_go_to_apns(monkeypatch, rsa_key):
    _configure_apns(monkeypatch)
    _configure_fcm(monkeypatch, rsa_key)
    seen = {}

    class FakeClient:
        def __init__(self, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def post(self, url, json=None, headers=None):
            seen['url'] = url
            seen['payload'] = json
            return _Resp(200)

    monkeypatch.setattr('httpx.Client', FakeClient)
    monkeypatch.setattr('httpx.post', lambda *a, **kw: pytest.fail('FCM used for iOS'))
    for platform in ('ios', None):
        user = SimpleNamespace(id=2, device_token='apns-token', device_platform=platform)
        assert push_service.send_push(user, 'Hi', garden_id=3, badge=1) is True
        assert seen['url'].endswith('/3/device/apns-token')
        assert seen['payload']['garden_id'] == 3


def test_health_reports_fcm_key_state_without_echoing_it(client, monkeypatch, rsa_key):
    assert client.get('/api/health/config').get_json()['fcm_configured'] is False
    _configure_fcm(monkeypatch, rsa_key)
    resp = client.get('/api/health/config')
    assert resp.get_json()['fcm_configured'] is True
    assert 'PRIVATE KEY' not in resp.get_data(as_text=True)
    monkeypatch.setenv('FCM_SERVICE_ACCOUNT_JSON', 'not json')
    assert client.get('/api/health/config').get_json()['fcm_configured'] == 'key_error'


def test_device_token_records_the_platform(client, make_user):
    make_user('droid', password='Password1')
    login = client.post('/api/auth/token', json={'email': 'droid@example.com',
                                                  'password': 'Password1'})
    auth = {'Authorization': f"Bearer {login.get_json()['access_token']}"}

    resp = client.put('/api/auth/device-token', headers=auth,
                      json={'device_token': 'fcm-token', 'platform': 'android'})
    assert resp.status_code == 200
    from app.models import User
    user = User.query.filter_by(username='droid').first()
    assert (user.device_token, user.device_platform) == ('fcm-token', 'android')

    resp = client.put('/api/auth/device-token', headers=auth,
                      json={'device_token': 't', 'platform': 'windows-phone'})
    assert resp.status_code == 400
