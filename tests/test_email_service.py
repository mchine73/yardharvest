"""Tests for the email provider chain in app/email_service.send_email().

Chain: SendGrid (primary) -> Zoho ZeptoMail API (fallback) -> dev-log.
Both providers are mocked; no network calls and no real keys are used.
"""
from unittest.mock import MagicMock, patch

from app import email_service


def _clear_email_env(monkeypatch):
    monkeypatch.delenv('SENDGRID_API_KEY', raising=False)
    monkeypatch.delenv('ZEPTOMAIL_TOKEN', raising=False)
    monkeypatch.delenv('ZEPTOMAIL_API_URL', raising=False)


def test_sendgrid_used_when_configured(app, monkeypatch):
    _clear_email_env(monkeypatch)
    monkeypatch.setenv('SENDGRID_API_KEY', 'SG.test')
    sg_instance = MagicMock()
    sg_instance.send.return_value = MagicMock(status_code=202)
    with app.app_context(), \
            patch('sendgrid.SendGridAPIClient', return_value=sg_instance), \
            patch('requests.post') as post:
        ok = email_service.send_email('a@example.com', 'Subj', '<p>hi</p>')
    assert ok is True
    sg_instance.send.assert_called_once()
    post.assert_not_called()  # ZeptoMail not reached when SendGrid succeeds


def test_zeptomail_used_when_no_sendgrid(app, monkeypatch):
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


def test_falls_back_to_zeptomail_when_sendgrid_raises(app, monkeypatch):
    _clear_email_env(monkeypatch)
    monkeypatch.setenv('SENDGRID_API_KEY', 'SG.test')
    monkeypatch.setenv('ZEPTOMAIL_TOKEN', 'tok-123')
    fake_resp = MagicMock(status_code=201)
    with app.app_context(), \
            patch('sendgrid.SendGridAPIClient', side_effect=RuntimeError('sg down')), \
            patch('requests.post', return_value=fake_resp) as post:
        ok = email_service.send_email('a@example.com', 'Subj', '<p>hi</p>')
    assert ok is True
    post.assert_called_once()


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


def test_dev_log_when_nothing_configured(app, monkeypatch):
    _clear_email_env(monkeypatch)
    # Config (loaded at import with empty env) also has no ZEPTOMAIL_TOKEN.
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
