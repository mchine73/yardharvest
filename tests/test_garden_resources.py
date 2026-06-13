"""Shared-resource lifecycle: add, checkout, return.

Regression guard for the checkout 500 — resource_to_dict compared a
SQLite-returned naive due_date against an aware `now`, raising
"can't compare offset-naive and offset-aware datetimes".
"""
from app import db as _db


def _setup(app, make_user, key):
    from app.models import CommunityGarden
    with app.app_context():
        org = make_user(username=f'org_{key}', email=f'org_{key}@example.com',
                        role='manager')
        g = CommunityGarden(
            name=f'Res Garden {key}', slug=f'res-garden-{key}',
            organizer_id=org.id, is_active=True, subscription_status='active',
        )
        _db.session.add(g)
        _db.session.commit()
        return g.id, org.id


def _login(client, key):
    client.post('/api/auth/login',
                json={'email': f'org_{key}@example.com', 'password': 'Password1'})


def test_add_resource_with_blank_quantity_defaults_to_one(client, app, make_user):
    gid, _ = _setup(app, make_user, 'qty')
    _login(client, 'qty')
    r = client.post(f'/api/gardens/{gid}/resources', json={
        'name': 'Wheelbarrow', 'resource_type': 'tool', 'quantity': None,
    })
    assert r.status_code == 201, r.get_json()
    assert r.get_json()['quantity'] == 1


def test_checkout_and_return_resource(client, app, make_user):
    gid, _ = _setup(app, make_user, 'co')
    _login(client, 'co')
    rid = client.post(f'/api/gardens/{gid}/resources', json={
        'name': 'Hoe', 'resource_type': 'tool', 'quantity': 1,
    }).get_json()['id']

    # Checkout must serialize cleanly (this is where the 500 used to happen)
    co = client.post(f'/api/gardens/{gid}/resources/{rid}/checkout',
                     json={'duration_days': 7})
    assert co.status_code == 200, co.get_json()
    body = co.get_json()
    assert body['checked_out_to_id'] is not None
    assert body['due_date'] is not None
    assert body['is_overdue'] is False

    ret = client.post(f'/api/gardens/{gid}/resources/{rid}/return', json={})
    assert ret.status_code == 200, ret.get_json()
    assert ret.get_json()['checked_out_to_id'] is None
