"""Tests for the verified email-change flow.

Standard protocol: re-authenticate with the current password, send a signed
single-use 24h token to the NEW address, change nothing until the link is
confirmed, and notify the old address at request and completion time.
"""
from unittest.mock import patch

from app import db as _db


def _login(client, email, password='Password1'):
    return client.post('/api/auth/login', json={'email': email, 'password': password})


def _request_change(client, new_email, password='Password1'):
    return client.post('/api/auth/request-email-change',
                       json={'new_email': new_email, 'password': password})


def test_request_requires_correct_password(client, app, make_user):
    with app.app_context():
        make_user(username='ec1', email='ec1@example.com', role='gardener')
    _login(client, 'ec1@example.com')
    resp = _request_change(client, 'ec1new@example.com', password='WrongPass1')
    assert resp.status_code == 403
    assert 'password' in resp.get_json()['error'].lower()


def test_request_rejects_invalid_and_duplicate_email(client, app, make_user):
    with app.app_context():
        make_user(username='ec2', email='ec2@example.com', role='gardener')
        make_user(username='ec2b', email='taken@example.com', role='gardener')
    _login(client, 'ec2@example.com')

    assert _request_change(client, 'not-an-email').status_code == 400
    assert _request_change(client, 'ec2@example.com').status_code == 400  # same address
    resp = _request_change(client, 'taken@example.com')
    assert resp.status_code == 409
    # Generic error — must not confirm the address belongs to an account
    assert 'taken' not in resp.get_json()['error'].lower()


def test_request_sends_verification_and_notice(client, app, make_user):
    with app.app_context():
        user = make_user(username='ec3', email='ec3@example.com', role='gardener')
        uid = user.id
    _login(client, 'ec3@example.com')

    with patch('app.email_service.send_email_change_verification') as verify_mock, \
            patch('app.email_service.send_email_change_notice') as notice_mock:
        resp = _request_change(client, 'ec3new@example.com')
    assert resp.status_code == 200
    verify_mock.assert_called_once()
    # args[0] is the current_user LocalProxy (unresolvable after the request);
    # the new address and token are what matter here.
    args, _ = verify_mock.call_args
    assert args[1] == 'ec3new@example.com'
    assert args[2]  # signed token present
    notice_mock.assert_called_once()
    assert notice_mock.call_args[0][1] == 'ec3new@example.com'

    # Email must NOT change until the link is confirmed
    from app.models import User
    with app.app_context():
        assert _db.session.get(User, uid).email == 'ec3@example.com'


def test_confirm_updates_email_and_token_is_single_use(client, app, make_user):
    from app.api.token_auth import generate_email_change_token
    from app.models import User
    with app.app_context():
        user = make_user(username='ec4', email='ec4@example.com', role='gardener')
        uid = user.id
        token = generate_email_change_token(user, 'ec4new@example.com')

    with patch('app.email_service.send_email_changed_confirmation') as confirm_mock:
        resp = client.post('/api/auth/confirm-email-change', json={'token': token})
    assert resp.status_code == 200
    assert resp.get_json()['email'] == 'ec4new@example.com'
    confirm_mock.assert_called_once()
    # Old-address notification gets the previous email
    assert confirm_mock.call_args[0][1] == 'ec4@example.com'

    with app.app_context():
        assert _db.session.get(User, uid).email == 'ec4new@example.com'

    # Re-using the same token must fail (email no longer matches)
    resp2 = client.post('/api/auth/confirm-email-change', json={'token': token})
    assert resp2.status_code == 400

    # And the user can log in with the new address
    assert _login(client, 'ec4new@example.com').status_code == 200


def test_confirm_rejects_garbage_and_expired_tokens(client, app, make_user):
    import jwt as pyjwt
    from datetime import datetime, timedelta, timezone
    with app.app_context():
        user = make_user(username='ec5', email='ec5@example.com', role='gardener')
        secret = app.config.get('JWT_SECRET_KEY', app.config['SECRET_KEY'])
        now = datetime.now(timezone.utc)
        expired = pyjwt.encode({
            'user_id': user.id, 'new_email': 'x@example.com', 'cur': user.email,
            'type': 'email_change', 'iat': now - timedelta(hours=25),
            'exp': now - timedelta(hours=1),
        }, secret, algorithm='HS256')

    assert client.post('/api/auth/confirm-email-change',
                       json={'token': 'garbage'}).status_code == 400
    assert client.post('/api/auth/confirm-email-change',
                       json={'token': expired}).status_code == 400
    assert client.post('/api/auth/confirm-email-change',
                       json={}).status_code == 400


def test_confirm_rejects_address_claimed_after_request(client, app, make_user):
    from app.api.token_auth import generate_email_change_token
    with app.app_context():
        user = make_user(username='ec6', email='ec6@example.com', role='gardener')
        token = generate_email_change_token(user, 'contested@example.com')
        # Someone else registers the address before the link is clicked
        make_user(username='ec6b', email='contested@example.com', role='gardener')

    resp = client.post('/api/auth/confirm-email-change', json={'token': token})
    assert resp.status_code == 409


def test_request_requires_auth(client):
    resp = client.post('/api/auth/request-email-change',
                       json={'new_email': 'x@example.com', 'password': 'Password1'})
    assert resp.status_code in (401, 302)  # unauthenticated
