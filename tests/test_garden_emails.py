"""Tests that garden-management email notifications are wired to their triggers.

All email sends are mocked at the email_service function level — these tests
assert the API endpoints CALL the right notification, not ZeptoMail delivery
(covered in test_email_service.py).
"""
import uuid
from datetime import date, datetime, time, timedelta, timezone
from unittest.mock import patch

import pytest

from app import db as _db


@pytest.fixture()
def garden_setup(app, make_user):
    """Organizer + member + active-Pro garden with one plot."""
    from app.models import CommunityGarden, GardenPlot
    with app.app_context():
        organizer = make_user(username='g_org', email='g_org@example.com', role='manager')
        member = make_user(username='g_member', email='g_member@example.com', role='gardener')
        garden = CommunityGarden(name='Email Test Garden',
                                 slug=f'email-test-{uuid.uuid4().hex[:8]}',
                                 organizer_id=organizer.id,
                                 subscription_status='active')
        _db.session.add(garden)
        _db.session.flush()
        plot = GardenPlot(garden_id=garden.id, plot_number='A1', status='available')
        _db.session.add(plot)
        _db.session.commit()
        return {'garden_id': garden.id, 'plot_id': plot.id,
                'organizer_id': organizer.id, 'member_id': member.id,
                'organizer_email': organizer.email, 'member_email': member.email}


def _login(client, email):
    return client.post('/api/auth/login', json={'email': email, 'password': 'Password1'})


# ---------------------------------------------------------------------------
# Plot assignment emails
# ---------------------------------------------------------------------------
def test_confirm_reservation_sends_plot_assigned_email(client, app, garden_setup):
    g = garden_setup
    from app.models import GardenPlot
    with app.app_context():
        plot = _db.session.get(GardenPlot, g['plot_id'])
        plot.status = 'reserved'
        plot.reserved_by_id = g['member_id']
        plot.reserved_at = datetime.now(timezone.utc)
        _db.session.commit()

    _login(client, g['organizer_email'])
    with patch('app.email_service.send_plot_assigned_email') as mock_send:
        resp = client.post(f"/api/garden-admin/{g['garden_id']}/plots/{g['plot_id']}/confirm")
    assert resp.status_code == 200
    mock_send.assert_called_once()
    args, kwargs = mock_send.call_args
    assert args[0] == 'Email Test Garden'
    assert args[1] == 'A1'
    assert args[2] == g['member_email']


def test_approve_waitlist_sends_plot_assigned_email(client, app, garden_setup):
    g = garden_setup
    from app.models import GardenWaitlist
    with app.app_context():
        entry = GardenWaitlist(garden_id=g['garden_id'], user_id=g['member_id'],
                               status='waiting')
        _db.session.add(entry)
        _db.session.commit()
        wl_id = entry.id

    _login(client, g['organizer_email'])
    with patch('app.email_service.send_plot_assigned_email') as mock_send:
        resp = client.post(f"/api/garden-admin/{g['garden_id']}/waitlist/{wl_id}/approve",
                           json={'plot_id': g['plot_id']})
    assert resp.status_code == 200
    mock_send.assert_called_once()
    assert mock_send.call_args[0][2] == g['member_email']


# ---------------------------------------------------------------------------
# Waitlist join email (with position)
# ---------------------------------------------------------------------------
def test_join_waitlist_sends_waitlisted_email(client, app, garden_setup):
    g = garden_setup
    _login(client, g['member_email'])
    with patch('app.email_service.send_plot_waitlisted_email') as mock_send:
        resp = client.post(f"/api/gardens/{g['garden_id']}/waitlist", json={})
    assert resp.status_code == 201
    mock_send.assert_called_once()
    args, kwargs = mock_send.call_args
    assert args[1] == g['member_email']
    assert args[3] == 1  # first (and only) waiting entry


# ---------------------------------------------------------------------------
# Dues reminder uses the branded template
# ---------------------------------------------------------------------------
def test_remind_dues_sends_branded_reminder(client, app, garden_setup):
    g = garden_setup
    from app.models import GardenDuesRecord
    with app.app_context():
        rec = GardenDuesRecord(garden_id=g['garden_id'], user_id=g['member_id'],
                               season_year=2026, amount_due=60.0, amount_paid=10.0,
                               status='partial')
        _db.session.add(rec)
        _db.session.commit()
        dues_id = rec.id

    _login(client, g['organizer_email'])
    with patch('app.email_service.send_dues_reminder_email') as mock_send:
        resp = client.post(f"/api/garden-admin/{g['garden_id']}/dues/{dues_id}/remind")
    assert resp.status_code == 200
    mock_send.assert_called_once()
    args, kwargs = mock_send.call_args
    assert args[0] == 'Email Test Garden'
    assert args[1] == g['member_email']
    assert args[3] == pytest.approx(50.0)  # remaining = due - paid


# ---------------------------------------------------------------------------
# Event cancellation notifies RSVPs
# ---------------------------------------------------------------------------
def test_delete_event_emails_rsvps(client, app, garden_setup):
    g = garden_setup
    from app.models import GardenEvent, EventRSVP
    with app.app_context():
        event = GardenEvent(garden_id=g['garden_id'], title='Spring Workday',
                            event_date=datetime.now(timezone.utc) + timedelta(days=7),
                            created_by_id=g['organizer_id'])
        _db.session.add(event)
        _db.session.flush()
        _db.session.add(EventRSVP(event_id=event.id, user_id=g['member_id']))
        _db.session.commit()
        event_id = event.id

    _login(client, g['organizer_email'])
    with patch('app.email_service.send_event_cancelled_email') as mock_send:
        resp = client.delete(f"/api/garden-admin/{g['garden_id']}/events/{event_id}")
    assert resp.status_code == 200
    mock_send.assert_called_once()
    args, kwargs = mock_send.call_args
    assert args[1] == 'Spring Workday'
    assert g['member_email'] in args[3]

    from app.models import Notification
    with app.app_context():
        n = Notification.query.filter_by(user_id=g['member_id'],
                                         type='event_cancelled').first()
        assert n is not None


def test_delete_event_without_rsvps_sends_nothing(client, app, garden_setup):
    g = garden_setup
    from app.models import GardenEvent
    with app.app_context():
        event = GardenEvent(garden_id=g['garden_id'], title='Quiet Event',
                            event_date=datetime.now(timezone.utc) + timedelta(days=3),
                            created_by_id=g['organizer_id'])
        _db.session.add(event)
        _db.session.commit()
        event_id = event.id

    _login(client, g['organizer_email'])
    with patch('app.email_service.send_event_cancelled_email') as mock_send:
        resp = client.delete(f"/api/garden-admin/{g['garden_id']}/events/{event_id}")
    assert resp.status_code == 200
    mock_send.assert_not_called()


# ---------------------------------------------------------------------------
# Shift signup confirmation
# ---------------------------------------------------------------------------
def test_shift_signup_sends_confirmation(client, app, garden_setup):
    g = garden_setup
    from app.models import VolunteerShift
    with app.app_context():
        shift = VolunteerShift(garden_id=g['garden_id'], title='Compost Turn',
                               shift_date=date.today() + timedelta(days=5),
                               start_time=time(9, 0), end_time=time(11, 0),
                               created_by_id=g['organizer_id'])
        _db.session.add(shift)
        _db.session.commit()
        shift_id = shift.id

    _login(client, g['member_email'])
    with patch('app.email_service.send_shift_signup_email') as mock_send:
        resp = client.post(f"/api/gardens/{g['garden_id']}/shifts/{shift_id}/signup")
    assert resp.status_code == 201
    mock_send.assert_called_once()
    args, kwargs = mock_send.call_args
    assert args[1] == g['member_email']
    assert args[3] == 'Compost Turn'


# ---------------------------------------------------------------------------
# Email health probe
# ---------------------------------------------------------------------------
def test_health_email_unconfigured(client):
    with patch.dict('os.environ', {'ZEPTOMAIL_TOKEN': ''}):
        resp = client.get('/api/health/email')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['configured'] is False
    assert body['auth_ok'] is False


def test_health_email_valid_token(client):
    class FakeResp:
        status_code = 400  # validation error on empty payload = token authenticated
        text = '{"error":{"code":"TM_3201"}}'

    with patch.dict('os.environ', {'ZEPTOMAIL_TOKEN': 'tok'}), \
            patch('requests.post', return_value=FakeResp()):
        resp = client.get('/api/health/email')
    body = resp.get_json()
    assert body['configured'] is True
    assert body['auth_ok'] is True
    assert body['error'] is None


def test_health_email_bad_token(client):
    class FakeResp:
        status_code = 401
        text = '{"error":"unauthorized"}'

    with patch.dict('os.environ', {'ZEPTOMAIL_TOKEN': 'bad'}), \
            patch('requests.post', return_value=FakeResp()):
        resp = client.get('/api/health/email')
    body = resp.get_json()
    assert body['configured'] is True
    assert body['auth_ok'] is False
    assert 'ZEPTOMAIL_TOKEN' in body['error']
