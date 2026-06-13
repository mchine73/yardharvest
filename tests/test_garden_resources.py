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


# ---- Admin tool management ---------------------------------------------

def _add_tool(client, gid, name='Spade'):
    return client.post(f'/api/gardens/{gid}/resources',
                       json={'name': name, 'resource_type': 'tool', 'quantity': 1}).get_json()['id']


def test_admin_edit_resource(client, app, make_user):
    gid, _ = _setup(app, make_user, 'edit')
    _login(client, 'edit')
    rid = _add_tool(client, gid)
    r = client.put(f'/api/garden-admin/{gid}/resources/{rid}',
                   json={'name': 'Long-handled Spade', 'quantity': 3, 'condition': 'fair'})
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body['name'] == 'Long-handled Spade'
    assert body['quantity'] == 3
    assert body['condition'] == 'fair'


def test_admin_out_of_service_blocks_checkout(client, app, make_user):
    gid, _ = _setup(app, make_user, 'oos')
    member = None
    with app.app_context():
        member = make_user(username='m_oos', email='m_oos@example.com').id
    _login(client, 'oos')
    rid = _add_tool(client, gid)
    # take out of service
    r = client.post(f'/api/garden-admin/{gid}/resources/{rid}/service',
                    json={'out_of_service': True, 'note': 'broken'})
    assert r.status_code == 200, r.get_json()
    assert r.get_json()['status'] == 'out_of_service'
    # member cannot check it out
    co = client.post(f'/api/garden-admin/{gid}/resources/{rid}/checkout-for',
                     json={'user_id': member, 'duration_days': 3})
    assert co.status_code == 400
    # return to service, then checkout-for works
    client.post(f'/api/garden-admin/{gid}/resources/{rid}/service', json={'out_of_service': False})
    co2 = client.post(f'/api/garden-admin/{gid}/resources/{rid}/checkout-for',
                      json={'user_id': member, 'duration_days': 7})
    assert co2.status_code == 200, co2.get_json()
    assert co2.get_json()['checked_out_to_id'] == member


def test_admin_force_return_and_extend(client, app, make_user):
    gid, _ = _setup(app, make_user, 'fr')
    with app.app_context():
        member = make_user(username='m_fr', email='m_fr@example.com').id
    _login(client, 'fr')
    rid = _add_tool(client, gid)
    client.post(f'/api/garden-admin/{gid}/resources/{rid}/checkout-for',
                json={'user_id': member, 'duration_days': 3})
    # extend
    ext = client.post(f'/api/garden-admin/{gid}/resources/{rid}/extend', json={'days': 5})
    assert ext.status_code == 200, ext.get_json()
    # force return
    fr = client.post(f'/api/garden-admin/{gid}/resources/{rid}/force-return', json={})
    assert fr.status_code == 200, fr.get_json()
    assert fr.get_json()['checked_out_to_id'] is None


def test_admin_delete_resource_guarded(client, app, make_user):
    gid, _ = _setup(app, make_user, 'del')
    with app.app_context():
        member = make_user(username='m_del', email='m_del@example.com').id
    _login(client, 'del')
    rid = _add_tool(client, gid)
    client.post(f'/api/garden-admin/{gid}/resources/{rid}/checkout-for',
                json={'user_id': member, 'duration_days': 3})
    # delete is blocked while checked out (409) without force
    blocked = client.delete(f'/api/garden-admin/{gid}/resources/{rid}')
    assert blocked.status_code == 409
    # force delete succeeds
    forced = client.delete(f'/api/garden-admin/{gid}/resources/{rid}?force=1')
    assert forced.status_code == 200, forced.get_json()
