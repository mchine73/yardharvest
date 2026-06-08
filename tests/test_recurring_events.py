"""Recurring volunteer opportunities: creating a garden event with a cadence
expands it into a series (the original + 8 future occurrences), while a
one-time event stays a single row.

Covers POST /api/gardens/<id>/events {recurring} and that event_to_dict
surfaces the cadence.
"""
from datetime import datetime, timedelta

from app import db as _db


def _make_garden(app, make_user, key):
    """Create an organizer + garden unique to `key` (the test DB is shared
    across this module, so reusing an email/slug would collide)."""
    from app.models import CommunityGarden
    with app.app_context():
        mgr = make_user(username=f'evtmgr_{key}', email=f'evtmgr_{key}@example.com',
                        role='manager')
        g = CommunityGarden(name=f'Recurring Events Garden {key}',
                            slug=f'recurring-events-garden-{key}',
                            organizer_id=mgr.id, is_active=True)
        _db.session.add(g)
        _db.session.commit()
        return g.id


def _login(client, key):
    client.post('/api/auth/login',
                json={'email': f'evtmgr_{key}@example.com', 'password': 'Password1'})


def test_one_time_event_creates_single_row(client, app, make_user):
    gid = _make_garden(app, make_user, 'onetime')
    _login(client, 'onetime')
    r = client.post(f'/api/gardens/{gid}/events', json={
        'title': 'Single Workday', 'event_type': 'workday',
        'event_date': '2026-05-01T09:00', 'duration_hours': 2,
    })
    assert r.status_code == 201, r.get_json()
    assert r.get_json()['recurring'] == 'none'
    with app.app_context():
        from app.models import GardenEvent
        assert GardenEvent.query.filter_by(garden_id=gid).count() == 1


def test_weekly_event_expands_into_series(client, app, make_user):
    gid = _make_garden(app, make_user, 'weekly')
    _login(client, 'weekly')
    start = '2026-05-01T09:00'
    r = client.post(f'/api/gardens/{gid}/events', json={
        'title': 'Weekly Volunteer Day', 'event_type': 'workday',
        'event_date': start, 'duration_hours': 3, 'max_volunteers': 10,
        'recurring': 'weekly',
    })
    assert r.status_code == 201, r.get_json()
    body = r.get_json()
    assert body['recurring'] == 'weekly'

    with app.app_context():
        from app.models import GardenEvent
        events = (GardenEvent.query.filter_by(garden_id=gid)
                  .order_by(GardenEvent.event_date).all())
        # Original + 8 future occurrences.
        assert len(events) == 9
        assert all(e.recurring == 'weekly' for e in events)
        assert all(e.max_volunteers == 10 for e in events)
        # Spacing is exactly 7 days between consecutive occurrences.
        base = datetime.fromisoformat(start)
        for i, e in enumerate(events):
            assert e.event_date == base + timedelta(days=7 * i)


def test_invalid_recurring_value_rejected(client, app, make_user):
    gid = _make_garden(app, make_user, 'invalid')
    _login(client, 'invalid')
    r = client.post(f'/api/gardens/{gid}/events', json={
        'title': 'Bad cadence', 'event_date': '2026-05-01T09:00',
        'recurring': 'hourly',
    })
    assert r.status_code == 400
    assert 'recurring' in r.get_json()['error']


def test_edit_event_updates_cadence_without_regenerating(client, app, make_user):
    gid = _make_garden(app, make_user, 'edit')
    _login(client, 'edit')
    r = client.post(f'/api/gardens/{gid}/events', json={
        'title': 'One-off', 'event_date': '2026-05-01T09:00',
    })
    eid = r.get_json()['id']
    r2 = client.put(f'/api/garden-admin/{gid}/events/{eid}', json={'recurring': 'monthly'})
    assert r2.status_code == 200, r2.get_json()
    assert r2.get_json()['recurring'] == 'monthly'
    with app.app_context():
        from app.models import GardenEvent
        # Editing the cadence must NOT spawn new rows.
        assert GardenEvent.query.filter_by(garden_id=gid).count() == 1
