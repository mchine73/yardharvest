"""Tests for the email provider in app/email_service.send_email().

Email is sent exclusively via Zoho ZeptoMail (pay-as-you-go transactional API);
when ZEPTOMAIL_TOKEN is unset it falls through to dev-log. ZeptoMail is mocked;
no network calls and no real keys are used.
"""
from unittest.mock import MagicMock, patch

from app import email_service


def _clear_email_env(monkeypatch):
    monkeypatch.delenv('ZEPTOMAIL_TOKEN', raising=False)
    monkeypatch.delenv('ZEPTOMAIL_API_URL', raising=False)


def test_zeptomail_used_when_configured(app, monkeypatch):
    _clear_email_env(monkeypatch)
    monkeypatch.setenv('ZEPTOMAIL_TOKEN', 'tok-123')
    fake_resp = MagicMock(status_code=201)
    with app.app_context(), patch('requests.post', return_value=fake_resp) as post:
        ok = email_service.send_email('a@example.com', 'Subj', '<p>hi</p>')
    assert ok is True
    post.assert_called_once()
    _, kwargs = post.call_args
    assert kwargs['headers']['Authorization'] == 'Zoho-enczapikey tok-123'
    assert kwargs['json']['subject'] == 'Subj'
    assert kwargs['json']['to'][0]['email_address']['address'] == 'a@example.com'
    assert kwargs['json']['htmlbody'] == '<p>hi</p>'


def test_multiple_recipients_passed_to_zeptomail(app, monkeypatch):
    _clear_email_env(monkeypatch)
    monkeypatch.setenv('ZEPTOMAIL_TOKEN', 'tok-123')
    fake_resp = MagicMock(status_code=201)
    with app.app_context(), patch('requests.post', return_value=fake_resp) as post:
        email_service.send_email(['a@example.com', 'b@example.com'], 'S', '<p>x</p>')
    _, kwargs = post.call_args
    addrs = [t['email_address']['address'] for t in kwargs['json']['to']]
    assert addrs == ['a@example.com', 'b@example.com']


def test_zeptomail_non_2xx_returns_false(app, monkeypatch):
    _clear_email_env(monkeypatch)
    monkeypatch.setenv('ZEPTOMAIL_TOKEN', 'bad-token')
    fake_resp = MagicMock(status_code=401)
    with app.app_context(), patch('requests.post', return_value=fake_resp):
        ok = email_service.send_email('a@example.com', 'S', '<p>x</p>')
    assert ok is False


def test_dev_log_when_token_unset(app, monkeypatch):
    _clear_email_env(monkeypatch)
    with app.app_context():
        app.config['ZEPTOMAIL_TOKEN'] = ''
        with patch('requests.post') as post:
            ok = email_service.send_email('a@example.com', 'S', '<p>x</p>')
    assert ok is False
    post.assert_not_called()


def test_regional_api_url_honored(app, monkeypatch):
    _clear_email_env(monkeypatch)
    monkeypatch.setenv('ZEPTOMAIL_TOKEN', 'tok-123')
    monkeypatch.setenv('ZEPTOMAIL_API_URL', 'https://api.zeptomail.eu/v1.1/email')
    fake_resp = MagicMock(status_code=201)
    with app.app_context(), patch('requests.post', return_value=fake_resp) as post:
        email_service.send_email('a@example.com', 'S', '<p>x</p>')
    args, _ = post.call_args
    assert args[0] == 'https://api.zeptomail.eu/v1.1/email'
