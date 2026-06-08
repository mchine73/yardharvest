"""Reproduce the EXACT full settings payload the frontend sends, to confirm
photo_url persists when sent alongside every other settingsForm field."""
from app import db as _db


def _make_garden(app, make_user):
    from app.models import CommunityGarden
    with app.app_context():
        mgr = make_user(username='fpmgr', email='fpmgr@example.com', role='manager')
        g = CommunityGarden(name='Full Payload Garden', slug='full-payload-garden',
                            organizer_id=mgr.id, is_active=True,
                            operating_model='allotment')
        _db.session.add(g)
        _db.session.commit()
        return g.id


def test_full_settings_payload_persists_photo_url(client, app, make_user):
    gid = _make_garden(app, make_user)
    client.post('/api/auth/login', json={'email': 'fpmgr@example.com', 'password': 'Password1'})

    # Mirror GardenAdminDashboard.jsx settingsForm exactly
    payload = {
        'name': 'Full Payload Garden',
        'description': 'desc',
        'address': '123 St',
        'city': 'Omaha',
        'state': 'NE',
        'zip_code': '68000',
        'contact_email': 'g@example.com',
        'plot_fee_annual': 40.0,
        'operating_model': 'allotment',
        'season_start': '2026-03-01',
        'season_end': '2026-10-20',
        'rules': 'be nice',
        'photo_url': '/media/yardharvest/newbanner123',
        'max_checkouts_per_member': 3,
    }
    r = client.put(f'/api/garden-admin/{gid}/settings', json=payload)
    assert r.status_code == 200, r.get_json()

    rd = client.get(f'/api/gardens/{gid}')
    assert rd.get_json()['photo_url'] == '/media/yardharvest/newbanner123', rd.get_json()
