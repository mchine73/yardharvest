"""Community wall (public garden page): comment posting + photo wall.

Regressions:
- post_comment/list_comments called an undefined _resolve_garden_or_404 → 500.
- photos_api had no garden-id resolver, so loading photos by the opaque grd_…
  public_id (the form the frontend uses) errored against the integer column in
  Postgres. Both endpoints must accept the public_id URL the SPA actually sends.
"""
import io

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
