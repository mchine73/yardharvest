"""Tests for the booking page: slot math (pure), the public book/manage flow
(with Zoho mocked), the CRM lead tie-in, and admin config CRUD."""
from datetime import datetime
from types import SimpleNamespace

import pytest

from app import db
from app.models import BookingSettings, BookingType, AvailabilityRule, Booking
from app import booking_service


# ---------------------------------------------------------------------------
# Pure slot-generation logic
# ---------------------------------------------------------------------------
def _settings(**kw):
    base = dict(timezone='UTC', min_notice_hours=0, max_advance_days=2,
                slot_granularity_min=30)
    base.update(kw)
    return SimpleNamespace(**base)


def _rule(dow, start, end):
    return SimpleNamespace(day_of_week=dow, start_min=start, end_min=end)


def test_generate_slots_basic():
    # Wed 2026-07-01 09:00 UTC; one Wednesday window 09:00–11:00, 30-min slots.
    now = datetime(2026, 7, 1, 9, 0)
    slots = booking_service.generate_slots(
        duration_min=30, buffer_before_min=0, buffer_after_min=0,
        rules=[_rule(2, 540, 660)], settings=_settings(), now_utc=now)
    assert [s.strftime('%H:%M') for s in slots] == ['09:00', '09:30', '10:00', '10:30']


def test_generate_slots_respects_min_notice():
    now = datetime(2026, 7, 1, 9, 0)
    slots = booking_service.generate_slots(
        duration_min=30, buffer_before_min=0, buffer_after_min=0,
        rules=[_rule(2, 540, 660)], settings=_settings(min_notice_hours=2),
        now_utc=now)
    assert slots == []   # everything is within the 2-hour notice window


def test_generate_slots_skips_busy_overlap():
    now = datetime(2026, 7, 1, 9, 0)
    busy = [(datetime(2026, 7, 1, 9, 30), datetime(2026, 7, 1, 10, 0))]
    slots = booking_service.generate_slots(
        duration_min=30, buffer_before_min=0, buffer_after_min=0,
        rules=[_rule(2, 540, 660)], settings=_settings(),
        now_utc=now, busy_intervals=busy)
    times = [s.strftime('%H:%M') for s in slots]
    assert '09:30' not in times and times == ['09:00', '10:00', '10:30']


def test_generate_slots_blocked_date_excluded():
    now = datetime(2026, 7, 1, 9, 0)
    blocked = {datetime(2026, 7, 1).date()}
    slots = booking_service.generate_slots(
        duration_min=30, buffer_before_min=0, buffer_after_min=0,
        rules=[_rule(2, 540, 660)], settings=_settings(),
        now_utc=now, blocked_dates=blocked)
    assert slots == []


# ---------------------------------------------------------------------------
# Integration: public flow
# ---------------------------------------------------------------------------
def _seed(db_session):
    s = BookingSettings.get()
    s.timezone = 'UTC'
    s.min_notice_hours = 0
    s.max_advance_days = 7
    bt = BookingType(name='Intro Call', slug='intro-call', duration_min=30, is_active=True)
    db_session.add(bt)
    for dow in range(7):
        db_session.add(AvailabilityRule(day_of_week=dow, start_min=0, end_min=1439))
    db_session.commit()
    return bt


def _first_slot(client):
    r = client.get('/api/booking/slots?type=intro-call')
    assert r.status_code == 200
    slots = r.get_json()['slots']
    assert slots, 'expected at least one open slot'
    return slots[0]


def test_config_lists_active_types(client, db_session):
    _seed(db_session)
    r = client.get('/api/booking/config')
    assert r.status_code == 200
    data = r.get_json()
    assert [t['slug'] for t in data['types']] == ['intro-call']


def test_book_creates_booking_and_crm_lead(client, db_session):
    _seed(db_session)
    start = _first_slot(client)
    r = client.post('/api/booking/book', json={
        'type': 'intro-call', 'start': start, 'name': 'Pat Booker',
        'email': 'Pat@Example.com', 'notes': 'looking forward', 'timezone': 'America/Chicago'})
    assert r.status_code == 201, r.get_json()
    body = r.get_json()
    assert body['manage_path'].startswith('/book/manage/bkg_')

    b = Booking.query.filter_by(invitee_email='pat@example.com').first()
    assert b is not None and b.status == 'confirmed'
    assert b.zoho_sync_status == 'skipped'   # Zoho unconfigured in tests

    # CRM tie-in: a lead was upserted + linked.
    from app.crm.models import Contact, Activity
    c = Contact.query.filter_by(email='pat@example.com').first()
    assert c is not None and c.source == 'Booking' and c.lead_status == 'Engaged'
    assert b.crm_contact_id == c.id
    assert Activity.query.filter_by(contact_id=c.id, kind='meeting').count() == 1


def test_book_syncs_to_zoho_when_configured(client, db_session, monkeypatch):
    _seed(db_session)
    import app.zoho_calendar_service as zoho
    monkeypatch.setattr(zoho, 'is_configured', lambda: True)
    monkeypatch.setattr(zoho, 'has_calendar', lambda: True)
    captured = {}

    def fake_create(**kw):
        captured.update(kw)
        return 'evt_abc123'
    monkeypatch.setattr(zoho, 'create_event', fake_create)

    start = _first_slot(client)
    r = client.post('/api/booking/book', json={
        'type': 'intro-call', 'start': start, 'name': 'Sam', 'email': 'sam@example.com'})
    assert r.status_code == 201
    b = Booking.query.filter_by(invitee_email='sam@example.com').first()
    assert b.zoho_sync_status == 'synced' and b.zoho_event_uid == 'evt_abc123'
    assert captured['attendee_email'] == 'sam@example.com'


def test_double_booking_returns_409(client, db_session):
    _seed(db_session)
    start = _first_slot(client)
    payload = {'type': 'intro-call', 'start': start, 'name': 'A', 'email': 'a@example.com'}
    assert client.post('/api/booking/book', json=payload).status_code == 201
    payload2 = {**payload, 'email': 'b@example.com'}
    assert client.post('/api/booking/book', json=payload2).status_code == 409


def test_book_validates_input(client, db_session):
    _seed(db_session)
    start = _first_slot(client)
    # bad email
    r = client.post('/api/booking/book', json={
        'type': 'intro-call', 'start': start, 'name': 'X', 'email': 'not-an-email'})
    assert r.status_code == 400
    # missing fields
    assert client.post('/api/booking/book', json={'type': 'intro-call'}).status_code == 400


def test_booking_emails_use_scheduling_shell(client, db_session, monkeypatch):
    """Both booking emails (guest confirmation + owner notification) render in
    the scheduling shell — not the platform account-holder template."""
    _seed(db_session)
    sent = []
    from app import email_service
    monkeypatch.setattr(email_service, 'send_email',
                        lambda to, subject, html, **k: sent.append(html) or True)
    start = _first_slot(client)
    r = client.post('/api/booking/book', json={
        'type': 'intro-call', 'start': start, 'name': 'Shell Test',
        'email': 'shell@example.com'})
    assert r.status_code == 201
    assert len(sent) == 2   # guest confirmation + owner notification
    for html in sent:
        assert 'Scheduling' in html
        assert 'have an account' not in html


def test_manage_and_cancel(client, db_session):
    _seed(db_session)
    start = _first_slot(client)
    r = client.post('/api/booking/book', json={
        'type': 'intro-call', 'start': start, 'name': 'Cancel Me', 'email': 'c@example.com'})
    pid = r.get_json()['booking']['public_id']

    assert client.get(f'/api/booking/manage/{pid}').status_code == 200
    rc = client.post(f'/api/booking/manage/{pid}/cancel')
    assert rc.status_code == 200 and rc.get_json()['booking']['status'] == 'cancelled'
    # cancelled slot frees up again
    r2 = client.post('/api/booking/book', json={
        'type': 'intro-call', 'start': start, 'name': 'New', 'email': 'n@example.com'})
    assert r2.status_code == 201


def test_manage_unknown_404(client, db_session):
    _seed(db_session)
    assert client.get('/api/booking/manage/bkg_nope').status_code == 404


# ---------------------------------------------------------------------------
# Admin config
# ---------------------------------------------------------------------------
def _login_admin(client, make_user):
    make_user(username='boss', email='boss@example.com', is_admin=True)
    r = client.post('/api/auth/login', json={'email': 'boss@example.com', 'password': 'Password1'})
    assert r.status_code == 200


def test_admin_requires_auth(client, db_session):
    assert client.get('/api/booking/admin/overview').status_code == 401


def test_admin_crud_flow(client, db_session, make_user):
    _login_admin(client, make_user)
    assert client.get('/api/booking/admin/overview').status_code == 200

    # create a type (slug auto-generated)
    r = client.post('/api/booking/admin/types',
                    json={'name': 'Strategy Session', 'duration_min': 45, 'location': 'Phone'})
    assert r.status_code == 201
    t = r.get_json()['type']
    assert t['slug'] == 'strategy-session' and t['duration_min'] == 45

    # update settings (timezone validated)
    assert client.put('/api/booking/admin/settings',
                      json={'timezone': 'America/Denver', 'min_notice_hours': 4}).status_code == 200
    assert client.put('/api/booking/admin/settings',
                      json={'timezone': 'Not/AZone'}).status_code == 400

    # set availability
    r = client.put('/api/booking/admin/availability', json={'rules': [
        {'day_of_week': 0, 'start_min': 540, 'end_min': 1020},
        {'day_of_week': 2, 'start_min': 600, 'end_min': 900}]})
    assert r.status_code == 200 and len(r.get_json()['availability']) == 2
    # invalid range rejected
    assert client.put('/api/booking/admin/availability', json={'rules': [
        {'day_of_week': 0, 'start_min': 900, 'end_min': 540}]}).status_code == 400

    # delete the type (no bookings → hard delete)
    assert client.delete(f"/api/booking/admin/types/{t['id']}").status_code == 200


def test_admin_delete_type_with_bookings_deactivates(client, db_session, make_user):
    bt = _seed(db_session)
    start = _first_slot(client)
    client.post('/api/booking/book', json={
        'type': 'intro-call', 'start': start, 'name': 'A', 'email': 'a@example.com'})
    _login_admin(client, make_user)
    r = client.delete(f'/api/booking/admin/types/{bt.id}')
    assert r.status_code == 200 and r.get_json().get('deactivated') is True
    assert db.session.get(BookingType, bt.id).is_active is False
