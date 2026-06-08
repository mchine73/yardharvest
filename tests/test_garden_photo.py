"""The garden-settings 'Garden Photo' becomes the banner on both the browse
list and the garden detail page.

Proves the data flow: PUT /garden-admin/<id>/settings {photo_url} -> persisted
on the garden -> returned by GET /api/gardens (browse cards) AND
GET /api/gardens/<id> (detail banner). The frontend renders garden.photo_url as
the card/banner background on GardenHome and GardenDetail.
"""
from app import db as _db


def _make_garden(app, make_user, name):
    from app.models import CommunityGarden
    with app.app_context():
        mgr = make_user(username='gpmgr', email='gpmgr@example.com', role='manager')
        g = CommunityGarden(name=name, slug='sunrise-banner-test-garden',
                            organizer_id=mgr.id, is_active=True)
        _db.session.add(g)
        _db.session.commit()
        return g.id


def test_garden_photo_flows_to_browse_and_detail(client, app, make_user):
    name = 'Sunrise Banner Test Garden'
    gid = _make_garden(app, make_user, name)
    client.post('/api/auth/login', json={'email': 'gpmgr@example.com', 'password': 'Password1'})

    photo = '/media/yardharvest/garden_banner_abc'
    r = client.put(f'/api/garden-admin/{gid}/settings', json={'photo_url': photo})
    assert r.status_code == 200, r.get_json()

    # Detail page (the garden's own page banner)
    rd = client.get(f'/api/gardens/{gid}')
    assert rd.status_code == 200
    assert rd.get_json()['photo_url'] == photo

    # Browse list ("looking for gardens") — search to be deterministic
    rb = client.get('/api/gardens', query_string={'search': 'Sunrise Banner Test'})
    assert rb.status_code == 200
    match = next((x for x in rb.get_json()['gardens'] if x['id'] == gid), None)
    assert match is not None and match['photo_url'] == photo
