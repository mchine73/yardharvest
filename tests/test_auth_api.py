"""Tests for the /api/auth REST endpoints."""
import pytest


def test_me_unauthenticated_returns_null(client):
    """GET /api/auth/me must return 200 + null for anonymous callers.

    Regression test for a fixed bug: get_current_user() returns Flask-Login's
    AnonymousUserMixin (a truthy object with no .id) when unauthenticated, so
    the handler must gate on `.is_authenticated`, not truthiness. Previously
    `if user:` was taken and user_to_dict() crashed on user.id (HTTP 500).
    """
    resp = client.get('/api/auth/me')
    assert resp.status_code == 200
    assert resp.get_json() is None


def test_register_requires_fields(client):
    resp = client.post('/api/auth/register', json={'username': 'x'})
    assert resp.status_code == 400


def test_register_rejects_weak_password(client, enable_marketplace):
    resp = client.post('/api/auth/register', json={
        'username': 'weakuser',
        'email': 'weak@example.com',
        'password': 'short',
        'role': 'buyer',
    })
    assert resp.status_code == 400
    assert 'Password' in resp.get_json()['error']


def test_register_rejects_invalid_role(client, enable_marketplace):
    """With marketplace enabled, only buyer/seller/both are allowed."""
    resp = client.post('/api/auth/register', json={
        'username': 'roleuser',
        'email': 'role@example.com',
        'password': 'GoodPass1',
        'role': 'gardener',  # garden role not allowed when marketplace is on
    })
    assert resp.status_code == 400


def test_register_success_and_logs_in(client, enable_marketplace):
    resp = client.post('/api/auth/register', json={
        'username': 'newbie',
        'email': 'Newbie@Example.com',
        'password': 'GoodPass1',
        'role': 'buyer',
    })
    assert resp.status_code == 201
    data = resp.get_json()
    assert data['username'] == 'newbie'
    assert data['email'] == 'newbie@example.com'  # lowercased
    assert data['role'] == 'buyer'
    # register() calls login_user, so /me should now return the user
    me = client.get('/api/auth/me')
    assert me.get_json()['username'] == 'newbie'


def test_register_duplicate_email_conflicts(client, enable_marketplace):
    payload = {
        'username': 'dupe',
        'email': 'dupe@example.com',
        'password': 'GoodPass1',
        'role': 'buyer',
    }
    assert client.post('/api/auth/register', json=payload).status_code == 201
    # Different username, same email
    payload2 = dict(payload, username='dupe2')
    resp = client.post('/api/auth/register', json=payload2)
    assert resp.status_code == 409


def test_register_garden_role_when_marketplace_off(client):
    """Default (no SiteEmailConfig) -> marketplace off -> garden roles allowed."""
    resp = client.post('/api/auth/register', json={
        'username': 'gardener1',
        'email': 'g1@example.com',
        'password': 'GoodPass1',
        'role': 'gardener',
    })
    assert resp.status_code == 201
    assert resp.get_json()['role'] == 'gardener'


def test_login_success(client, make_user):
    make_user(username='loginme', email='loginme@example.com', password='GoodPass1')
    resp = client.post('/api/auth/login', json={
        'email': 'loginme@example.com',
        'password': 'GoodPass1',
    })
    assert resp.status_code == 200
    assert resp.get_json()['username'] == 'loginme'


def test_login_wrong_password(client, make_user):
    make_user(username='wrongpw', email='wrongpw@example.com', password='GoodPass1')
    resp = client.post('/api/auth/login', json={
        'email': 'wrongpw@example.com',
        'password': 'nope',
    })
    assert resp.status_code == 401


def test_login_deactivated_account(client, make_user):
    make_user(username='deact', email='deact@example.com', password='GoodPass1',
              is_active_user=False)
    resp = client.post('/api/auth/login', json={
        'email': 'deact@example.com',
        'password': 'GoodPass1',
    })
    assert resp.status_code == 403


def test_logout_clears_session(client, make_user):
    make_user(username='logoutme', email='logoutme@example.com', password='GoodPass1')
    client.post('/api/auth/login', json={
        'email': 'logoutme@example.com', 'password': 'GoodPass1',
    })
    # While logged in, an authenticated user sees their own profile.
    assert client.get('/api/auth/me').get_json()['username'] == 'logoutme'
    # A protected endpoint is reachable while authenticated.
    assert client.get('/api/listings/mine').status_code == 200

    resp = client.post('/api/auth/logout')
    assert resp.status_code == 200

    # After logout the session is cleared -> protected endpoint now 401,
    # and /api/auth/me returns null.
    assert client.get('/api/listings/mine').status_code == 401
    assert client.get('/api/auth/me').get_json() is None


def test_protected_endpoint_requires_auth(client):
    """/api/listings/mine is gated by @token_or_session -> 401 when anonymous."""
    resp = client.get('/api/listings/mine')
    assert resp.status_code == 401


def test_token_login_returns_jwt(client, make_user):
    make_user(username='mobileuser', email='mobile@example.com', password='GoodPass1')
    resp = client.post('/api/auth/token', json={
        'email': 'mobile@example.com', 'password': 'GoodPass1',
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'access_token' in data and 'refresh_token' in data
    assert data['user']['username'] == 'mobileuser'
