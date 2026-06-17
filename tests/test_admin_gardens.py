"""Tests for the platform-admin per-garden management endpoints in admin_api.

Covers list/delist (is_active), edit, finance+impact summary, transfer of
ownership, and the FK-safe hard delete (including detaching financial history
from the Garden Pro subscription).
"""
from datetime import date, datetime, timedelta, timezone

import pytest

from app import db
from app.models import (
    CommunityGarden, GardenPlot, GardenMembership, GardenDuesRecord,
    GardenExpense, HarvestLog, GardenEvent, GardenSubscription, Refund,
)
from tests.conftest import login_via_api


@pytest.fixture()
def garden_world(db_session, make_user):
    """An admin, an organizer, a transfer target, and a fully-populated garden."""
    admin = make_user(username='boss', role='both', is_admin=True)
    organizer = make_user(username='org', role='manager')
    target = make_user(username='newowner', role='manager')

    g = CommunityGarden(name='Cascade Test Garden', slug='cascade-test-garden',
                        organizer_id=organizer.id, total_plots=1, plot_fee_annual=100.0)
    db.session.add(g)
    db.session.commit()

    db.session.add_all([
        GardenPlot(garden_id=g.id, plot_number='A1', status='assigned',
                   assigned_to_id=organizer.id),
        GardenMembership(garden_id=g.id, user_id=organizer.id, role='organizer'),
        GardenDuesRecord(garden_id=g.id, user_id=organizer.id, season_year=2026,
                         amount_due=100.0, amount_paid=40.0, status='partial'),
        GardenExpense(garden_id=g.id, title='Seeds', amount=30.0, category='seeds',
                      expense_date=date(2026, 3, 1), created_by_id=organizer.id),
        HarvestLog(garden_id=g.id, user_id=organizer.id, category='tomatoes',
                   quantity_lbs=12.5, harvest_date=date(2026, 7, 1)),
        GardenEvent(garden_id=g.id, title='Workday',
                    event_date=datetime.now(timezone.utc) + timedelta(days=10),
                    created_by_id=organizer.id),
    ])
    sub = GardenSubscription(garden_id=g.id, status='active', billing_cycle='monthly')
    db.session.add(sub)
    db.session.commit()
    # A refund referencing the subscription — the delete must detach (not orphan) it.
    db.session.add(Refund(garden_subscription_id=sub.id, refund_type='garden_pro',
                          amount=5.0, initiated_by_id=admin.id))
    db.session.commit()

    return {'admin': admin, 'organizer': organizer, 'target': target,
            'garden_id': g.id, 'sub_id': sub.id}


def _login_admin(client, world):
    assert login_via_api(client, 'boss@example.com', 'Password1').status_code == 200


def test_list_includes_active_flag(client, garden_world):
    _login_admin(client, garden_world)
    resp = client.get('/api/admin/gardens')
    assert resp.status_code == 200
    rows = {g['id']: g for g in resp.get_json()['gardens']}
    assert garden_world['garden_id'] in rows
    assert rows[garden_world['garden_id']]['is_active'] is True


def test_summary_finance_and_impact(client, garden_world):
    _login_admin(client, garden_world)
    gid = garden_world['garden_id']
    data = client.get(f'/api/admin/gardens/{gid}/summary').get_json()

    assert data['plots'] == {'total': 1, 'assigned': 1, 'available': 0, 'occupancy_pct': 100.0}
    assert data['members'] == 1
    assert data['finance']['dues_expected'] == 100.0
    assert data['finance']['dues_collected'] == 40.0
    assert data['finance']['dues_outstanding'] == 60.0
    assert data['finance']['collection_rate'] == 40.0
    assert data['finance']['expenses'] == 30.0
    assert data['finance']['net_balance'] == 10.0
    assert data['impact']['harvest_lbs'] == 12.5
    assert data['impact']['total_events'] == 1
    assert data['impact']['upcoming_events'] == 1


def test_toggle_active_delists_from_public_browse(client, garden_world):
    _login_admin(client, garden_world)
    gid = garden_world['garden_id']

    # Visible in public browse while listed.
    assert 'Cascade Test Garden' in client.get('/api/gardens').get_data(as_text=True)

    resp = client.post(f'/api/admin/gardens/{gid}/toggle-active')
    assert resp.status_code == 200
    assert resp.get_json()['is_active'] is False

    # Delisted → gone from public browse, but the admin can still see/manage it.
    assert 'Cascade Test Garden' not in client.get('/api/gardens').get_data(as_text=True)
    assert client.get(f'/api/admin/gardens/{gid}/summary').get_json()['is_active'] is False

    # Explicit re-list.
    resp = client.post(f'/api/admin/gardens/{gid}/toggle-active', json={'is_active': True})
    assert resp.get_json()['is_active'] is True


def test_edit_garden_details(client, garden_world):
    _login_admin(client, garden_world)
    gid = garden_world['garden_id']
    resp = client.put(f'/api/admin/gardens/{gid}', json={
        'name': 'Renamed Garden', 'plot_fee_annual': 55.5, 'operating_model': 'communal',
    })
    assert resp.status_code == 200
    g = db.session.get(CommunityGarden, gid)
    assert g.name == 'Renamed Garden'
    assert g.plot_fee_annual == 55.5
    assert g.operating_model == 'communal'

    # Bad operating_model is rejected.
    assert client.put(f'/api/admin/gardens/{gid}', json={'operating_model': 'bogus'}).status_code == 400


def test_transfer_ownership(client, garden_world):
    _login_admin(client, garden_world)
    gid = garden_world['garden_id']
    target = garden_world['target']
    organizer = garden_world['organizer']

    resp = client.post(f'/api/admin/gardens/{gid}/transfer-ownership', json={'user_id': target.id})
    assert resp.status_code == 200

    g = db.session.get(CommunityGarden, gid)
    assert g.organizer_id == target.id
    new_mem = GardenMembership.query.filter_by(garden_id=gid, user_id=target.id).first()
    assert new_mem and new_mem.role == 'organizer'
    old_mem = GardenMembership.query.filter_by(garden_id=gid, user_id=organizer.id).first()
    assert old_mem and old_mem.role == 'co_organizer'


def test_delete_requires_exact_name_then_cascades(client, garden_world):
    _login_admin(client, garden_world)
    gid = garden_world['garden_id']
    sub_id = garden_world['sub_id']

    # Wrong confirmation name is refused.
    assert client.delete(f'/api/admin/gardens/{gid}', json={'confirm_name': 'wrong'}).status_code == 400
    assert db.session.get(CommunityGarden, gid) is not None

    # Correct name cascades.
    resp = client.delete(f'/api/admin/gardens/{gid}', json={'confirm_name': 'Cascade Test Garden'})
    assert resp.status_code == 200

    assert db.session.get(CommunityGarden, gid) is None
    assert GardenPlot.query.filter_by(garden_id=gid).count() == 0
    assert GardenDuesRecord.query.filter_by(garden_id=gid).count() == 0
    assert GardenExpense.query.filter_by(garden_id=gid).count() == 0
    assert HarvestLog.query.filter_by(garden_id=gid).count() == 0
    assert GardenEvent.query.filter_by(garden_id=gid).count() == 0
    assert GardenMembership.query.filter_by(garden_id=gid).count() == 0
    assert GardenSubscription.query.filter_by(garden_id=gid).count() == 0

    # The refund is kept for the financial record, but detached from the sub.
    refund = Refund.query.filter_by(garden_subscription_id=sub_id).first()
    assert refund is None
    kept = Refund.query.filter_by(refund_type='garden_pro').first()
    assert kept is not None and kept.garden_subscription_id is None


def test_non_admin_is_forbidden(client, garden_world):
    assert login_via_api(client, 'org@example.com', 'Password1').status_code == 200
    gid = garden_world['garden_id']
    assert client.get(f'/api/admin/gardens/{gid}/summary').status_code == 403
    assert client.post(f'/api/admin/gardens/{gid}/toggle-active').status_code == 403
    assert client.delete(f'/api/admin/gardens/{gid}', json={'confirm_name': 'Cascade Test Garden'}).status_code == 403
