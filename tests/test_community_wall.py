"""Community wall (public garden page): comment posting + photo wall.

Regressions:
- post_comment/list_comments called an undefined _resolve_garden_or_404 → 500.
- photos_api had no garden-id resolver, so loading photos by the opaque grd_…
  public_id (the form the frontend uses) errored against the integer column in
  Postgres. Both endpoints must accept the public_id URL the SPA actually sends.
"""
import io
from unittest.mock import patch

from PIL import Image

from app import db as _db
from tests.conftest import login_via_api


def _make_garden(app, owner_id):
    from app.models import CommunityGarden
    with app.app_context():
        g = CommunityGarden(name='Wall Garden', slug='wall-garden-test',
                            organizer_id=owner_id, is_active=True)
        _db.session.add(g)
        _db.session.commit()
        return g.id, g.public_id


def test_post_and_list_comment_by_public_id(client, make_user, app):
    user = make_user(username='wallposter')
    gid, gpub = _make_garden(app, user.id)
    assert login_via_api(client, 'wallposter@example.com', 'Password1').status_code == 200

    # Post via the opaque public_id URL the SPA uses.
    r = client.post(f'/api/gardens/{gpub}/comments', json={'body': 'Lovely tomatoes this year!'})
    assert r.status_code == 201, f'comment POST -> {r.status_code}: {r.get_data(as_text=True)[:400]}'

    r = client.get(f'/api/gardens/{gpub}/comments')
    assert r.status_code == 200, r.get_data(as_text=True)[:400]
    assert any(c['body'] == 'Lovely tomatoes this year!' for c in r.get_json())


def test_photo_wall_by_public_id(client, make_user, app):
    user = make_user(username='wallphoto')
    gid, gpub = _make_garden(app, user.id)
    assert login_via_api(client, 'wallphoto@example.com', 'Password1').status_code == 200

    buf = io.BytesIO()
    Image.new('RGB', (16, 16), 'green').save(buf, 'PNG')
    buf.seek(0)
    up = client.post('/api/photos/upload',
                     data={'photo': (buf, 'wall.png'), 'garden_id': str(gid),
                           'category': 'garden'},
                     content_type='multipart/form-data')
    assert up.status_code == 201, f'upload -> {up.status_code}: {up.get_data(as_text=True)[:400]}'

    # The reload the SPA does after upload — by public_id, not numeric id.
    r = client.get(f'/api/photos/garden/{gpub}')
    assert r.status_code == 200, r.get_data(as_text=True)[:400]
    photos = r.get_json()['photos']
    assert len(photos) == 1 and photos[0]['category'] == 'garden'


def test_comment_threading(client, make_user, app):
    user = make_user(username='threader')
    gid, gpub = _make_garden(app, user.id)
    assert login_via_api(client, 'threader@example.com', 'Password1').status_code == 200

    top = client.post(f'/api/gardens/{gpub}/comments', json={'body': 'Top-level comment'})
    assert top.status_code == 201
    top_id = top.get_json()['id']

    reply = client.post(f'/api/gardens/{gpub}/comments',
                        json={'body': 'A reply', 'parent_id': top_id})
    assert reply.status_code == 201, reply.get_data(as_text=True)[:300]
    assert reply.get_json()['parent_id'] == top_id

    # A reply to the reply flattens to the same top-level parent (one-level threads).
    nested = client.post(f'/api/gardens/{gpub}/comments',
                         json={'body': 'reply to reply', 'parent_id': reply.get_json()['id']})
    assert nested.status_code == 201
    assert nested.get_json()['parent_id'] == top_id


def test_comment_like_toggle(client, make_user, app):
    user = make_user(username='liker')
    gid, gpub = _make_garden(app, user.id)
    assert login_via_api(client, 'liker@example.com', 'Password1').status_code == 200

    c = client.post(f'/api/gardens/{gpub}/comments', json={'body': 'Like me'})
    cid = c.get_json()['id']

    r1 = client.post(f'/api/gardens/{gpub}/comments/{cid}/like')
    assert r1.status_code == 200 and r1.get_json() == {'likes_count': 1, 'liked': True}

    r2 = client.post(f'/api/gardens/{gpub}/comments/{cid}/like')
    assert r2.status_code == 200 and r2.get_json() == {'likes_count': 0, 'liked': False}

    # Listing reflects like state for the current user.
    client.post(f'/api/gardens/{gpub}/comments/{cid}/like')
    listed = client.get(f'/api/gardens/{gpub}/comments').get_json()
    me = next(x for x in listed if x['id'] == cid)
    assert me['likes_count'] == 1 and me['liked_by_me'] is True


def test_auto_denied_comment_stored_and_in_admin_tab(client, make_user, app):
    # The garden owner is its admin, so the same client can post + moderate.
    owner = make_user(username='wallowner')
    gid, gpub = _make_garden(app, owner.id)
    assert login_via_api(client, 'wallowner@example.com', 'Password1').status_code == 200

    # Force the AI moderator to block this post.
    with patch('app.moderation_service.moderate_comment', return_value=('block', 'spam/abuse')):
        r = client.post(f'/api/gardens/{gpub}/comments', json={'body': 'buy cheap pills now'})
    assert r.status_code == 422 and r.get_json()['moderation'] == 'block'

    # Never appears on the public wall.
    public = client.get(f'/api/gardens/{gpub}/comments').get_json()
    assert all(c['body'] != 'buy cheap pills now' for c in public)

    # Shows in the admin Auto-denied tab with the moderator reason + a count.
    denied = client.get(f'/api/garden-admin/{gpub}/comments?status=blocked').get_json()
    assert denied['blocked_count'] == 1
    row = next(c for c in denied['comments'] if c['body'] == 'buy cheap pills now')
    assert row['status'] == 'blocked' and row['moderation_reason'] == 'spam/abuse'

    # The live "All" wall excludes auto-denied posts.
    all_wall = client.get(f'/api/garden-admin/{gpub}/comments?status=all').get_json()
    assert all(c['status'] != 'blocked' for c in all_wall['comments'])

    # "Publish anyway" (approve) overrides the block and clears the reason.
    client.post(f"/api/garden-admin/{gpub}/comments/{row['id']}/approve")
    published = client.get(f'/api/gardens/{gpub}/comments').get_json()
    assert any(c['body'] == 'buy cheap pills now' for c in published)
