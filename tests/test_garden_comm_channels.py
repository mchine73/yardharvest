"""Garden organizer communication flows fan out to email (ZeptoMail) AND
SMS (Twilio) for members who opted into SMS.

Each test patches the email/SMS send functions and asserts the endpoint calls
them — proving the wiring, independent of whether real credentials are set.
SMS is gated on per-user opt-in (sms_opt_in + phone_number).
"""
from unittest.mock import patch

from app import db as _db


def _setup(app, make_user, key, *, sms_opt_in=True):
    """Create an organizer + a Pro garden + one opted-in member. Returns ids."""
    from app.models import CommunityGarden
    with app.app_context():
        org = make_user(username=f'org_{key}', email=f'org_{key}@example.com',
                        role='manager')
        member = make_user(
            username=f'mem_{key}', email=f'mem_{key}@example.com',
            phone_number='+15551234567', sms_opt_in=sms_opt_in,
        )
        g = CommunityGarden(
            name=f'Comm Garden {key}', slug=f'comm-garden-{key}',
            organizer_id=org.id, is_active=True,
            subscription_status='active',  # unlock Pro-gated endpoints
        )
        _db.session.add(g)
        _db.session.commit()
        return g.id, org.id, member.id


def _login_org(client, key):
    client.post('/api/auth/login',
                json={'email': f'org_{key}@example.com', 'password': 'Password1'})


def _assign_plot(app, gid, member_id, number='A1'):
    from app.models import GardenPlot
    with app.app_context():
        plot = GardenPlot(garden_id=gid, plot_number=number, status='assigned',
                          assigned_to_id=member_id)
        _db.session.add(plot)
        _db.session.commit()
        return plot.id


# --------------------------------------------------------------------------
def test_announcement_emails_and_texts_members(client, app, make_user):
    gid, _org, member_id = _setup(app, make_user, 'ann')
    _assign_plot(app, gid, member_id)
    _login_org(client, 'ann')

    with patch('app.api.garden_admin_api.send_garden_announcement') as email, \
            patch('app.sms_service.send_announcement_sms') as sms:
        r = client.post(f'/api/garden-admin/{gid}/announcements', json={
            'title': 'Workday Saturday', 'body': 'Come help out!', 'priority': 'normal',
        })
    assert r.status_code == 201, r.get_json()
    email.assert_called_once()           # ZeptoMail to member emails
    sms.assert_called_once()             # Twilio to the opted-in member
    args = sms.call_args[0]
    assert args[0] == '+15551234567'


def test_dues_reminder_emails_and_texts(client, app, make_user):
    gid, _org, member_id = _setup(app, make_user, 'dues')
    _login_org(client, 'dues')
    from app.models import GardenDuesRecord
    with app.app_context():
        rec = GardenDuesRecord(garden_id=gid, user_id=member_id, season_year=2026,
                               amount_due=40, amount_paid=0, status='unpaid')
        _db.session.add(rec)
        _db.session.commit()
        rec_id = rec.id

    with patch('app.email_service.send_email') as email, \
            patch('app.sms_service.send_dues_reminder_sms') as sms:
        r = client.post(f'/api/garden-admin/{gid}/dues/{rec_id}/remind')
    assert r.status_code == 200, r.get_json()
    email.assert_called_once()
    sms.assert_called_once()
    assert sms.call_args[0][0] == '+15551234567'


def test_plot_assignment_texts_member(client, app, make_user):
    gid, _org, member_id = _setup(app, make_user, 'plot')
    _login_org(client, 'plot')
    from app.models import GardenPlot
    with app.app_context():
        plot = GardenPlot(garden_id=gid, plot_number='B2', status='available')
        _db.session.add(plot)
        _db.session.commit()
        plot_id = plot.id

    with patch('app.sms_service.send_plot_assigned_sms') as sms:
        r = client.put(f'/api/gardens/{gid}/plots/{plot_id}/assign',
                       json={'user_id': member_id})
    assert r.status_code == 200, r.get_json()
    sms.assert_called_once()
    assert sms.call_args[0][0] == '+15551234567'


def test_shift_reminder_emails_and_texts(client, app, make_user):
    gid, _org, member_id = _setup(app, make_user, 'shift')
    _login_org(client, 'shift')
    from app.models import VolunteerShift, ShiftSignup
    from datetime import date, time as dtime
    with app.app_context():
        shift = VolunteerShift(garden_id=gid, title='Weeding Crew',
                               shift_date=date(2026, 5, 9),
                               start_time=dtime(9, 0), end_time=dtime(12, 0),
                               created_by_id=member_id)
        _db.session.add(shift)
        _db.session.commit()
        _db.session.add(ShiftSignup(shift_id=shift.id, user_id=member_id,
                                    status='signed_up'))
        _db.session.commit()
        shift_id = shift.id

    with patch('app.email_service.send_email') as email, \
            patch('app.sms_service.send_shift_reminder_sms') as sms:
        r = client.post(f'/api/garden-admin/{gid}/shifts/{shift_id}/remind')
    assert r.status_code == 200, r.get_json()
    assert r.get_json()['reminded'] == 1
    email.assert_called_once()
    sms.assert_called_once()
    assert sms.call_args[0][0] == '+15551234567'


def test_garden_dm_email_channel_sends(client, app, make_user):
    """A direct message with the 'email' channel reaches send_email with the
    recipient's address; 'platform'-only does not send email."""
    gid, _org, member_id = _setup(app, make_user, 'dm')
    _login_org(client, 'dm')

    with patch('app.email_service.send_email') as email:
        r = client.post(f'/api/garden-admin/{gid}/messages', json={
            'recipient_id': member_id, 'subject': 'Hi', 'body': 'Hello there',
            'channels': ['platform', 'email'],
        })
    assert r.status_code == 201, r.get_json()
    assert 'email' in r.get_json()['delivered_via']
    email.assert_called_once()
    assert email.call_args[0][0] == 'mem_dm@example.com'

    with patch('app.email_service.send_email') as email2:
        r2 = client.post(f'/api/garden-admin/{gid}/messages', json={
            'recipient_id': member_id, 'subject': 'Hi2', 'body': 'Platform only',
            'channels': ['platform'],
        })
    assert r2.status_code == 201, r2.get_json()
    assert 'email' not in r2.get_json()['delivered_via']
    email2.assert_not_called()


def test_no_sms_when_member_not_opted_in(client, app, make_user):
    """A member without sms_opt_in still gets email but no SMS."""
    gid, _org, member_id = _setup(app, make_user, 'noopt', sms_opt_in=False)
    _assign_plot(app, gid, member_id)
    _login_org(client, 'noopt')

    with patch('app.api.garden_admin_api.send_garden_announcement') as email, \
            patch('app.sms_service.send_announcement_sms') as sms:
        r = client.post(f'/api/garden-admin/{gid}/announcements', json={
            'title': 'No SMS please', 'body': 'Email only.', 'priority': 'normal',
        })
    assert r.status_code == 201, r.get_json()
    email.assert_called_once()
    sms.assert_not_called()


def test_health_reports_twilio_configured_flag(client):
    """The health endpoint exposes a twilio_configured boolean (parity with the
    other integrations). False here since tests set no Twilio env vars."""
    body = client.get('/api/health/config').get_json()
    assert 'twilio_configured' in body
    assert body['twilio_configured'] is False
