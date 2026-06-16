"""Regression tests for security fixes from the whole-codebase review:

1. Private neighbourhood-group content (single post, comments, listings) is
   member-gated like the feed — no IDOR by post/group id.
2. /api/auth/token/refresh honours token_version, so a logout / password reset
   revokes outstanding refresh tokens (not just access tokens).
3. The CRM template-JSON endpoint sits behind the CRM login gate (it used to
   live under /crm/api/, which is exempt, leaking template content).
"""
from app import db as _db
from tests.conftest import login_via_api


# ---------------------------------------------------------------------------
# 1. Private group IDOR
# ---------------------------------------------------------------------------
def _make_private_group(make_user):
    from app.models import NeighborhoodGroup, GroupPost
    owner = make_user(username='grp_owner', email='grp_owner@example.com')
    group = NeighborhoodGroup(name='Secret Garden Club', slug='secret-club',
                              is_public=False, created_by_id=owner.id)
    _db.session.add(group)
    _db.session.flush()
    post = GroupPost(group_id=group.id, author_id=owner.id, content='members only')
    _db.session.add(post)
    _db.session.commit()
    return group.id, post.id


def test_private_group_post_blocks_anonymous(client, make_user):
    gid, pid = _make_private_group(make_user)
    assert client.get(f'/api/groups/{gid}/posts/{pid}').status_code == 401
    assert client.get(f'/api/groups/{gid}/posts/{pid}/comments').status_code == 401
    assert client.get(f'/api/groups/{gid}/listings').status_code == 401


def test_private_group_post_blocks_non_member(client, make_user):
    gid, pid = _make_private_group(make_user)
    make_user(username='outsider', email='outsider@example.com',
              password='Password1')
    login_via_api(client, 'outsider@example.com', 'Password1')
    assert client.get(f'/api/groups/{gid}/posts/{pid}').status_code == 403
    assert client.get(f'/api/groups/{gid}/posts/{pid}/comments').status_code == 403
    assert client.get(f'/api/groups/{gid}/listings').status_code == 403


def test_public_group_post_is_readable(client, make_user):
    from app.models import NeighborhoodGroup, GroupPost
    owner = make_user(username='pub_owner', email='pub_owner@example.com')
    group = NeighborhoodGroup(name='Open Club', slug='open-club',
                              is_public=True, created_by_id=owner.id)
    _db.session.add(group)
    _db.session.flush()
    post = GroupPost(group_id=group.id, author_id=owner.id, content='hello all')
    _db.session.add(post)
    _db.session.commit()
    assert client.get(f'/api/groups/{group.id}/posts/{post.id}').status_code == 200


# ---------------------------------------------------------------------------
# 2. Refresh token honours token_version
# ---------------------------------------------------------------------------
def test_refresh_token_revoked_after_version_bump(client, make_user):
    user = make_user(username='refresher', email='refresher@example.com',
                     password='Password1')
    uid = user.id
    tok = client.post('/api/auth/token',
                      json={'email': 'refresher@example.com',
                            'password': 'Password1'})
    assert tok.status_code == 200
    refresh_token = tok.get_json()['refresh_token']

    # Sanity: it works before revocation.
    ok = client.post('/api/auth/token/refresh',
                     json={'refresh_token': refresh_token})
    assert ok.status_code == 200

    # Bump token_version (what logout / password reset do).
    from app.models import User
    u = _db.session.get(User, uid)
    u.token_version = (u.token_version or 0) + 1
    _db.session.commit()

    revoked = client.post('/api/auth/token/refresh',
                          json={'refresh_token': refresh_token})
    assert revoked.status_code == 401


# ---------------------------------------------------------------------------
# 3. CRM template-JSON endpoint is behind the login gate
# ---------------------------------------------------------------------------
def test_crm_template_json_requires_login(client):
    # Unauthenticated -> redirected to the CRM login (302), not 200 JSON.
    resp = client.get('/crm/templates/json/1', follow_redirects=False)
    assert resp.status_code == 302
    assert '/crm/login' in resp.headers.get('Location', '')


def test_old_crm_api_template_route_no_longer_leaks_json(client):
    # The old /crm/api/templates/<id> path (exempt from the login gate) must no
    # longer serve the template JSON. It now matches no CRM route and falls
    # through to the SPA shell / 404 — either way, no template content leaks.
    resp = client.get('/crm/api/templates/1', follow_redirects=False)
    assert 'application/json' not in (resp.content_type or '')
    assert b'"subject"' not in resp.data
