"""Funder-report endpoint: date-ranged aggregates a grant report needs
(harvest, participation, volunteering, events, finance, equivalents),
Pro-gated, with per-request valuation rates."""
from datetime import date, datetime, time, timedelta, timezone

from app import db as _db


def _world(app, make_user, pro=True):
    """Organizer + Pro garden with data inside AND outside the report window."""
    from app.models import (CommunityGarden, GardenMembership, GardenPlot,
                            HarvestLog, VolunteerShift, ShiftSignup,
                            GardenEvent, EventRSVP, GardenDuesRecord,
                            GardenExpense)
    with app.app_context():
        mgr = make_user(username='frmgr', email='frmgr@example.com', role='manager')
        helper = make_user(username='frhelper', email='frhelper@example.com')
        g = CommunityGarden(name='Funder Test Garden', slug='funder-test-garden',
                            organizer_id=mgr.id, is_active=True,
                            subscription_status='active' if pro else 'free')
        _db.session.add(g)
        _db.session.flush()

        _db.session.add_all([
            GardenMembership(garden_id=g.id, user_id=mgr.id, role='organizer'),
            GardenMembership(garden_id=g.id, user_id=helper.id),
            GardenPlot(garden_id=g.id, plot_number='A1', status='assigned',
                       assigned_to_id=mgr.id),
            GardenPlot(garden_id=g.id, plot_number='A2', status='available'),
        ])

        # Harvest: 10 lbs food_bank + 5 lbs personal IN the window,
        # 100 lbs outside it (must be excluded).
        _db.session.add_all([
            HarvestLog(garden_id=g.id, user_id=mgr.id, category='Tomatoes',
                       quantity_lbs=10.0, harvest_date=date(2026, 6, 15),
                       destination='food_bank'),
            HarvestLog(garden_id=g.id, user_id=helper.id, category='Squash',
                       quantity_lbs=5.0, harvest_date=date(2026, 6, 20),
                       destination='personal'),
            HarvestLog(garden_id=g.id, user_id=mgr.id, category='Corn',
                       quantity_lbs=100.0, harvest_date=date(2025, 6, 15),
                       destination='food_bank'),
        ])

        # One shift in-window with 2 attended hours; one outside.
        s1 = VolunteerShift(garden_id=g.id, title='Weeding',
                            shift_date=date(2026, 6, 10),
                            start_time=time(9, 0), end_time=time(11, 0),
                            created_by_id=mgr.id)
        s2 = VolunteerShift(garden_id=g.id, title='Old shift',
                            shift_date=date(2025, 6, 10),
                            start_time=time(9, 0), end_time=time(11, 0),
                            created_by_id=mgr.id)
        _db.session.add_all([s1, s2])
        _db.session.flush()
        _db.session.add_all([
            ShiftSignup(shift_id=s1.id, user_id=helper.id, status='attended',
                        hours_logged=2.0),
            ShiftSignup(shift_id=s2.id, user_id=helper.id, status='attended',
                        hours_logged=8.0),
        ])

        ev = GardenEvent(garden_id=g.id, title='Workday', event_type='workday',
                         event_date=datetime(2026, 6, 12, 10, tzinfo=timezone.utc),
                         created_by_id=mgr.id)
        _db.session.add(ev)
        _db.session.flush()
        _db.session.add(EventRSVP(event_id=ev.id, user_id=helper.id, status='going'))

        _db.session.add_all([
            GardenDuesRecord(garden_id=g.id, user_id=mgr.id, season_year=2026,
                             amount_due=100.0, amount_paid=60.0, status='partial'),
            GardenExpense(garden_id=g.id, title='Seeds', amount=25.0,
                          category='seeds', expense_date=date(2026, 5, 1),
                          created_by_id=mgr.id),
        ])
        _db.session.commit()
        return g.id


def test_funder_report_aggregates_within_range(client, app, make_user):
    gid = _world(app, make_user)
    client.post('/api/auth/login', json={'email': 'frmgr@example.com',
                                         'password': 'Password1'})
    r = client.get(f'/api/garden-admin/{gid}/funder-report'
                   '?start=2026-01-01&end=2026-12-31')
    assert r.status_code == 200, r.get_json()
    d = r.get_json()

    # Harvest: only 2026 rows (the 100-lb 2025 harvest is excluded).
    assert d['harvest']['total_lbs'] == 15.0
    assert d['harvest']['food_bank_lbs'] == 10.0
    assert d['harvest']['gardeners'] == 2
    assert {c['category'] for c in d['harvest']['by_category']} == {'Tomatoes', 'Squash'}

    # Participation.
    assert d['participation']['members_total'] == 2
    assert d['participation']['plots_total'] == 2
    assert d['participation']['occupancy_pct'] == 50

    # Volunteering: only the in-window attended hours.
    assert d['volunteering']['hours'] == 2.0
    assert d['volunteering']['shifts_held'] == 1
    assert d['volunteering']['volunteers'] == 1
    assert d['volunteering']['value_usd'] == round(2.0 * d['rates']['volunteer_rate'], 2)

    # Events + finance.
    assert d['events']['held'] == 1 and d['events']['rsvps_going'] == 1
    assert d['finance']['dues_collected'] == 60.0
    assert d['finance']['expenses_total'] == 25.0
    assert d['finance']['net'] == 35.0

    # Equivalents from the documented rates.
    assert d['equivalents']['produce_value_usd'] == round(15.0 * d['rates']['produce_rate'], 2)
    assert d['equivalents']['meals'] == round(10.0 / d['rates']['lbs_per_meal'])
    assert d['equivalents']['co2_saved_lbs'] == 20.0


def test_funder_report_respects_custom_rates(client, app, make_user):
    gid = _world(app, make_user)
    client.post('/api/auth/login', json={'email': 'frmgr@example.com',
                                         'password': 'Password1'})
    d = client.get(f'/api/garden-admin/{gid}/funder-report'
                   '?start=2026-01-01&end=2026-12-31'
                   '&produce_rate=4.5&volunteer_rate=20').get_json()
    assert d['rates']['produce_rate'] == 4.5
    assert d['equivalents']['produce_value_usd'] == round(15.0 * 4.5, 2)
    assert d['volunteering']['value_usd'] == 40.0


def test_funder_report_is_pro_gated(client, app, make_user):
    gid = _world(app, make_user, pro=False)
    client.post('/api/auth/login', json={'email': 'frmgr@example.com',
                                         'password': 'Password1'})
    r = client.get(f'/api/garden-admin/{gid}/funder-report')
    assert r.status_code == 403
    assert 'Garden Pro' in r.get_json()['error']
