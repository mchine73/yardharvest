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
    # Multipart: a plain-text alternative ships alongside the HTML for better
    # inbox placement (HTML-only mail is a spam signal).
    assert kwargs['json']['textbody'] == 'hi'


def test_html_to_text_strips_markup_and_keeps_links_text():
    txt = email_service._html_to_text(
        '<style>.x{}</style><h2>Welcome</h2><p>Hello &amp; '
        '<a href="https://x.test">click</a></p><br><div>Bye</div>')
    assert '<' not in txt and '>' not in txt
    assert 'Welcome' in txt and 'Hello & click' in txt and 'Bye' in txt
    assert '.x{}' not in txt  # style block dropped


def test_crm_email_footer_has_no_account_claim(app):
    """CRM/outreach emails must NOT carry the platform 'you have an account /
    sent in error' footer — they get an unsubscribe-only footer instead."""
    with app.app_context():
        crm_html = email_service.render_sales_email('Hi there, quick question.')
        platform_html = email_service._render('<p>Account notice</p>')
    # CRM body: no account claim; has an unsubscribe link.
    assert 'have an account' not in crm_html
    assert 'sent in error' not in crm_html
    assert '/unsubscribe' in crm_html
    assert 'received this email from' in crm_html
    # Platform body: keeps the account / sent-in-error footer.
    assert 'have an account' in platform_html
    assert 'sent in error' in platform_html


def test_render_works_outside_request_context(app):
    """Regression: emails are rendered from run_async background threads, which
    have an app context but NO request context. The inject_globals context
    processor must not assume current_user is bound — otherwise _render raises
    AttributeError and the whole email send fails silently."""
    with app.app_context():  # app context only, no request/login context
        html = email_service._render('<h2>Hi</h2><p>Body</p>')
    assert 'email-wrapper' in html
    assert 'Hi' in html


def test_send_email_from_background_context(app, monkeypatch):
    """A full send (render + ZeptoMail) must succeed with no request context."""
    _clear_email_env(monkeypatch)
    monkeypatch.setenv('ZEPTOMAIL_TOKEN', 'tok-123')
    fake_resp = MagicMock(status_code=201)
    with app.app_context(), patch('requests.post', return_value=fake_resp) as post:
        ok = email_service.send_email('a@example.com', 'Subj',
                                      email_service._render('<p>hi</p>'))
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
