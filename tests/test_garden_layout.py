"""Garden layout designer: rectangular plot spans, rounded flag, and non-plot
features ("dead zones"), with bounds + overlap validation on save."""
from app import db as _db
from tests.conftest import login_via_api


def _make_pro_garden(app, owner_id):
    from app.models import CommunityGarden, GardenPlot
    with app.app_context():
        g = CommunityGarden(name='Layout Garden', slug='layout-garden-test',
                            organizer_id=owner_id, is_active=True,
                            subscription_status='active')  # Pro-gated editor
        _db.session.add(g)
        _db.session.flush()
        p1 = GardenPlot(garden_id=g.id, plot_number='A1', status='available')
        p2 = GardenPlot(garden_id=g.id, plot_number='A2', status='available')
        _db.session.add_all([p1, p2])
        _db.session.commit()
        return g.public_id, p1.id, p2.id


def _login(client, make_user, app, uname):
    owner = make_user(username=uname, email=f'{uname}@example.com', role='both')
    gpub, p1, p2 = _make_pro_garden(app, owner.id)
    assert login_via_api(client, f'{uname}@example.com', 'Password1').status_code == 200
    return gpub, p1, p2


def test_save_layout_with_spans_and_features(client, make_user, app):
    gpub, p1, p2 = _login(client, make_user, app, 'layoutadmin')
    payload = {
        'grid_rows': 10, 'grid_cols': 10,
        'plots': [
            {'id': p1, 'grid_row': 0, 'grid_col': 0, 'grid_width': 2, 'grid_height': 2, 'rounded': True},
            {'id': p2, 'grid_row': 5, 'grid_col': 5},
        ],
        'features': [
            {'feature_type': 'shed', 'label': 'Tool Shed', 'grid_row': 2, 'grid_col': 2,
             'grid_width': 2, 'grid_height': 1, 'color': '#8b5e3c', 'rounded': True},
        ],
    }
    r = client.put(f'/api/garden-admin/{gpub}/plot-layout', json=payload)
    assert r.status_code == 200, r.get_data(as_text=True)

    plots = client.get(f'/api/gardens/{gpub}/plots').get_json()
    a1 = next(p for p in plots if p['id'] == p1)
    assert a1['grid_width'] == 2 and a1['grid_height'] == 2 and a1['rounded'] is True

    feats = client.get(f'/api/gardens/{gpub}/layout-features').get_json()
    assert len(feats) == 1
    assert feats[0]['feature_type'] == 'shed' and feats[0]['label'] == 'Tool Shed'
    assert feats[0]['grid_width'] == 2 and feats[0]['rounded'] is True


def test_layout_rejects_overlap(client, make_user, app):
    gpub, p1, p2 = _login(client, make_user, app, 'ovadmin')
    payload = {'grid_rows': 5, 'grid_cols': 5, 'plots': [
        {'id': p1, 'grid_row': 0, 'grid_col': 0, 'grid_width': 2, 'grid_height': 2},
        {'id': p2, 'grid_row': 1, 'grid_col': 1},  # overlaps p1's 2x2 block
    ]}
    r = client.put(f'/api/garden-admin/{gpub}/plot-layout', json=payload)
    assert r.status_code == 400 and 'overlap' in r.get_json()['error'].lower()


def test_layout_rejects_out_of_bounds(client, make_user, app):
    gpub, p1, p2 = _login(client, make_user, app, 'oobadmin')
    payload = {'grid_rows': 5, 'grid_cols': 5, 'plots': [
        {'id': p1, 'grid_row': 4, 'grid_col': 4, 'grid_width': 3, 'grid_height': 1},  # spills off grid
    ]}
    r = client.put(f'/api/garden-admin/{gpub}/plot-layout', json=payload)
    assert r.status_code == 400 and 'outside' in r.get_json()['error'].lower()
