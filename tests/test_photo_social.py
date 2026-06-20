"""Garden photo wall social features: upvotes + comments on the Photo model.

Covers the like toggle, the comment CRUD, and that the public garden photo
listing surfaces likes_count / liked_by_me / comments_count so the wall can
render the social state without N+1 queries.
"""
from app import db as _db
from tests.conftest import login_via_api


def _make_garden_with_photo(app, owner_id):
    from app.models import CommunityGarden, Photo
    with app.app_context():
        g = CommunityGarden(name='Photo Garden', slug='photo-garden-test',
                            organizer_id=owner_id, is_active=True)
        _db.session.add(g)
        _db.session.flush()
        p = Photo(user_id=owner_id, garden_id=g.id, filename='abc.jpg',
                  category='garden', caption='Tomatoes')
        _db.session.add(p)
        _db.session.commit()
        return g.id, p.id


def _garden_member_photo_comment(app, organizer_id, member_id, slug='perm-garden'):
    """A garden owned by `organizer_id` with a photo + comment posted by a
    different member (`member_id`) — so deletion-permission groups are distinct."""
    from app.models import CommunityGarden, Photo, PhotoComment
    with app.app_context():
        g = CommunityGarden(name='Perm Garden', slug=slug,
                            organizer_id=organizer_id, is_active=True)
        _db.session.add(g)
        _db.session.flush()
        p = Photo(user_id=member_id, garden_id=g.id, filename='m.jpg',
                  category='garden', caption='Mine')
        _db.session.add(p)
        _db.session.flush()
        c = PhotoComment(photo_id=p.id, user_id=member_id, content='hi')
        _db.session.add(c)
        _db.session.commit()
        return g.id, p.id, c.id


def test_like_toggle(client, make_user, app):
    owner = make_user(username='likeuser', email='likeuser@example.com', role='both')
    gid, pid = _make_garden_with_photo(app, owner.id)
    assert login_via_api(client, 'likeuser@example.com', 'Password1').status_code == 200

    r = client.post(f'/api/photos/{pid}/like')
    assert r.status_code == 200
    body = r.get_json()
    assert body['liked'] is True and body['likes_count'] == 1

    # Toggling again removes the upvote.
    r = client.post(f'/api/photos/{pid}/like')
    assert r.get_json()['liked'] is False and r.get_json()['likes_count'] == 0


def test_like_requires_auth(client, make_user, app):
    owner = make_user(username='anonlike', email='anonlike@example.com', role='both')
    _gid, pid = _make_garden_with_photo(app, owner.id)
    r = client.post(f'/api/photos/{pid}/like')
    assert r.status_code == 401


def test_comment_crud(client, make_user, app):
    owner = make_user(username='cmtuser', email='cmtuser@example.com', role='both')
    gid, pid = _make_garden_with_photo(app, owner.id)
    assert login_via_api(client, 'cmtuser@example.com', 'Password1').status_code == 200

    # Empty comment rejected.
    assert client.post(f'/api/photos/{pid}/comments', json={'content': '  '}).status_code == 400

    r = client.post(f'/api/photos/{pid}/comments', json={'content': 'Looking great!'})
    assert r.status_code == 201
    cid = r.get_json()['id']

    r = client.get(f'/api/photos/{pid}/comments')
    assert r.status_code == 200
    comments = r.get_json()['comments']
    assert len(comments) == 1 and comments[0]['content'] == 'Looking great!'

    # Author can delete their comment.
    assert client.delete(f'/api/photos/{pid}/comments/{cid}').status_code == 200
    assert client.get(f'/api/photos/{pid}/comments').get_json()['comments'] == []


def test_garden_photos_includes_social_state(client, make_user, app):
    owner = make_user(username='socuser', email='socuser@example.com', role='both')
    gid, pid = _make_garden_with_photo(app, owner.id)
    assert login_via_api(client, 'socuser@example.com', 'Password1').status_code == 200
    client.post(f'/api/photos/{pid}/like')
    client.post(f'/api/photos/{pid}/comments', json={'content': 'Nice'})

    r = client.get(f'/api/photos/garden/{gid}')
    assert r.status_code == 200
    photo = r.get_json()['photos'][0]
    assert photo['likes_count'] == 1
    assert photo['liked_by_me'] is True
    assert photo['comments_count'] == 1
    assert photo['can_delete'] is True  # owner viewing their own photo


def test_other_user_cannot_delete_comment(client, make_user, app):
    owner = make_user(username='owner2', email='owner2@example.com', role='both')
    gid, pid = _make_garden_with_photo(app, owner.id)
    make_user(username='intruder', email='intruder@example.com', role='both')

    assert login_via_api(client, 'owner2@example.com', 'Password1').status_code == 200
    cid = client.post(f'/api/photos/{pid}/comments', json={'content': 'mine'}).get_json()['id']

    assert login_via_api(client, 'intruder@example.com', 'Password1').status_code == 200
    # Not the comment creator, not the garden admin, not a site admin -> 403.
    assert client.delete(f'/api/photos/{pid}/comments/{cid}').status_code == 403


# ---- Three groups may remove: creator, garden admin (organizer), site admin ----

def test_garden_admin_can_delete_member_photo_and_comment(client, make_user, app):
    org = make_user(username='gadmin', email='gadmin@example.com', role='both')
    member = make_user(username='gmember', email='gmember@example.com', role='both')
    gid, pid, cid = _garden_member_photo_comment(app, org.id, member.id, slug='ga-perm')

    assert login_via_api(client, 'gadmin@example.com', 'Password1').status_code == 200
    # Listing marks the member's photo deletable for the organizer.
    photo = client.get(f'/api/photos/garden/{gid}').get_json()['photos'][0]
    assert photo['can_delete'] is True
    assert client.delete(f'/api/photos/{pid}/comments/{cid}').status_code == 200
    assert client.delete(f'/api/photos/{pid}').status_code == 200


def test_site_admin_can_delete_member_photo_and_comment(client, make_user, app):
    org = make_user(username='sorg', email='sorg@example.com', role='both')
    member = make_user(username='smember', email='smember@example.com', role='both')
    make_user(username='superadmin', email='superadmin@example.com', role='both', is_admin=True)
    gid, pid, cid = _garden_member_photo_comment(app, org.id, member.id, slug='sa-perm')

    assert login_via_api(client, 'superadmin@example.com', 'Password1').status_code == 200
    assert client.delete(f'/api/photos/{pid}/comments/{cid}').status_code == 200
    assert client.delete(f'/api/photos/{pid}').status_code == 200


def test_photo_owner_cannot_delete_others_comment(client, make_user, app):
    """A photo's poster is NOT automatically a moderator — they can't delete a
    comment they didn't write unless they're the garden/site admin."""
    org = make_user(username='poorg', email='poorg@example.com', role='both')
    owner = make_user(username='poowner', email='poowner@example.com', role='both')
    commenter = make_user(username='pocom', email='pocom@example.com', role='both')
    # Garden owned by org; photo posted by `owner` (a plain member).
    from app.models import CommunityGarden, Photo
    with app.app_context():
        g = CommunityGarden(name='PO Garden', slug='po-perm', organizer_id=org.id, is_active=True)
        _db.session.add(g)
        _db.session.flush()
        p = Photo(user_id=owner.id, garden_id=g.id, filename='po.jpg', category='garden')
        _db.session.add(p)
        _db.session.commit()
        gid, pid = g.id, p.id

    assert login_via_api(client, 'pocom@example.com', 'Password1').status_code == 200
    cid = client.post(f'/api/photos/{pid}/comments', json={'content': 'hey'}).get_json()['id']

    # The photo owner (not the comment author, not a garden/site admin) -> 403.
    assert login_via_api(client, 'poowner@example.com', 'Password1').status_code == 200
    assert client.delete(f'/api/photos/{pid}/comments/{cid}').status_code == 403


def test_stranger_cannot_delete_member_photo(client, make_user, app):
    org = make_user(username='strorg', email='strorg@example.com', role='both')
    member = make_user(username='strmem', email='strmem@example.com', role='both')
    make_user(username='stranger', email='stranger@example.com', role='both')
    gid, pid, _cid = _garden_member_photo_comment(app, org.id, member.id, slug='str-perm')

    assert login_via_api(client, 'stranger@example.com', 'Password1').status_code == 200
    assert client.delete(f'/api/photos/{pid}').status_code == 403
