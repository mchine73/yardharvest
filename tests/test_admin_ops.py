"""The admin API Usage page and garden-manager messaging.

API usage exists because every costly failure here was silent: ZeptoMail is
prepaid, and when the credits ran out every send failed while the health probe
stayed green. So the tests that matter most are the ones that prove a FAILED
send is counted, and that counting can never break the send it counts.

Manager messaging is mostly about reaching the right people exactly once and
never reaching people the admin did not look at.
"""
import json
from unittest import mock

import pytest

from app import api_usage, db
from app.models import (ApiUsageEvent, CommunityGarden, EmailUnsubscribe,
                        GardenMembership, ManagerBroadcast, Notification)
from tests.conftest import login_via_api


@pytest.fixture()
def admin_login(client, make_user):
    admin = make_user(username='boss', is_admin=True)
    assert login_via_api(client, admin.email, 'Password1').status_code == 200
    return admin


# ---------------------------------------------------------------------------
# The ledger
# ---------------------------------------------------------------------------

def test_record_writes_a_row_with_an_estimated_cost(db_session):
    api_usage.record('zeptomail', 'email.send', units=4)
    row = ApiUsageEvent.query.one()
    assert (row.provider, row.operation, row.units, row.ok) == ('zeptomail', 'email.send', 4, True)
    # Billed per recipient: four of them at $2.50 per 10,000.
    assert row.cost_usd == pytest.approx(4 * 2.50 / 10_000)


def test_a_failed_send_is_counted_but_not_billed(db_session):
    """The July outage was a run of failures nobody counted."""
    api_usage.record('zeptomail', 'email.send', units=1, ok=False, error='HTTP 402')
    row = ApiUsageEvent.query.one()
    assert row.ok is False and row.error == 'HTTP 402'
    assert row.cost_usd == 0.0   # ZeptoMail does not charge for a rejected send


def test_a_failed_model_call_still_costs_its_tokens(db_session):
    api_usage.record('anthropic', 'moderation', ok=False, model='claude-sonnet-5',
                     input_tokens=1_000_000, output_tokens=0)
    assert ApiUsageEvent.query.one().cost_usd == pytest.approx(3.0)


def test_record_never_raises(db_session):
    with mock.patch('app.db.engine.begin', side_effect=RuntimeError('db down')):
        api_usage.record('twilio', 'sms.send')   # must not propagate


def test_record_does_not_commit_the_callers_transaction(db_session, make_user):
    """It writes on its own connection, so pending work stays pending.

    Holds on every database: the danger this guards against is committing
    someone else's half-finished request, and record() never touches
    db.session.
    """
    import time
    owner = make_user(username='owner')
    g = CommunityGarden(name='Pending', slug='pending', organizer_id=owner.id)
    db.session.add(g)
    db.session.flush()
    started = time.monotonic()
    api_usage.record('zeptomail', 'email.send')
    # On SQLite the caller's flush holds the only write lock. record() must
    # give up quickly rather than stall the request for SQLite's default 5s.
    assert time.monotonic() - started < 2
    db.session.rollback()
    assert CommunityGarden.query.filter_by(slug='pending').first() is None


def test_a_usage_row_survives_the_callers_rollback(db_session, make_user):
    """A send that happened is counted even if its request later fails.

    Only true where two connections can write at once. SQLite has a single
    writer, so the caller's flush blocks the usage write there; production
    runs Postgres, which is what this asserts against.
    """
    if db.engine.dialect.name != 'postgresql':
        pytest.skip('needs concurrent writers; production is Postgres')
    owner = make_user(username='owner2')
    db.session.add(CommunityGarden(name='Pending2', slug='pending2', organizer_id=owner.id))
    db.session.flush()
    api_usage.record('zeptomail', 'email.send')
    db.session.rollback()
    assert ApiUsageEvent.query.count() == 1


@pytest.mark.parametrize('body,segments', [
    ('a' * 160, 1),
    ('a' * 161, 2),     # 153 per segment once split
    ('a' * 306, 2),
    ('a' * 307, 3),
    ('Hola 👋', 1),     # outside GSM-7 → UCS-2, 70 per segment
    ('👋' + 'a' * 70, 2),
])
def test_sms_segments(body, segments):
    assert api_usage.sms_segments(body) == segments


# ---------------------------------------------------------------------------
# Instrumented call sites
# ---------------------------------------------------------------------------

def _zepto_response(status):
    r = mock.Mock()
    r.status_code = status
    r.headers = {}
    r.text = ''
    return r


def test_zeptomail_send_is_recorded_per_recipient_including_bcc(app, db_session):
    from app.email_service import _send_via_zeptomail
    app.config['ZEPTOMAIL_TOKEN'] = 'test-token'
    try:
        with mock.patch('requests.post', return_value=_zepto_response(201)):
            assert _send_via_zeptomail(['a@x.com'], 'Hi', '<p>x</p>',
                                       bcc=['b@x.com', 'c@x.com'])
    finally:
        app.config.pop('ZEPTOMAIL_TOKEN', None)
    row = ApiUsageEvent.query.one()
    assert (row.operation, row.units, row.ok) == ('email.send', 3, True)


def test_zeptomail_out_of_credits_is_recorded_as_a_failure(app, db_session):
    from app.email_service import _send_via_zeptomail
    app.config['ZEPTOMAIL_TOKEN'] = 'test-token'
    try:
        with mock.patch('requests.post', return_value=_zepto_response(402)):
            assert not _send_via_zeptomail(['a@x.com'], 'Hi', '<p>x</p>')
    finally:
        app.config.pop('ZEPTOMAIL_TOKEN', None)
    row = ApiUsageEvent.query.one()
    assert row.ok is False and row.error == 'HTTP 402'


def test_nothing_is_recorded_when_email_is_not_configured(app, db_session):
    """Dev mode sends nothing, so it must count nothing."""
    from app.email_service import _send_via_zeptomail
    app.config.pop('ZEPTOMAIL_TOKEN', None)
    with mock.patch.dict('os.environ', {'ZEPTOMAIL_TOKEN': ''}):
        assert not _send_via_zeptomail(['a@x.com'], 'Hi', '<p>x</p>')
    assert ApiUsageEvent.query.count() == 0


def test_moderation_records_its_tokens(app, db_session):
    from app import moderation_service
    resp = mock.Mock()
    resp.model = 'claude-sonnet-5'
    resp.usage = mock.Mock(input_tokens=1200, output_tokens=40)
    block = mock.Mock(type='text', text='{"decision":"allow","reason":""}')
    resp.content = [block]
    client = mock.Mock()
    client.messages.create.return_value = resp
    with mock.patch.object(moderation_service, 'is_configured', return_value=True), \
            mock.patch('anthropic.Anthropic', return_value=client):
        assert moderation_service.moderate_comment('nice tomatoes') == ('allow', '')
    row = ApiUsageEvent.query.one()
    assert (row.provider, row.operation) == ('anthropic', 'moderation')
    assert (row.input_tokens, row.output_tokens) == (1200, 40)
    assert row.cost_usd > 0


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------

def test_usage_report_requires_admin(client, make_user):
    u = make_user(username='plain')
    login_via_api(client, u.email, 'Password1')
    assert client.get('/api/admin/api-usage').status_code in (401, 403)


def test_usage_report_totals_failures_and_run_rate(client, admin_login):
    api_usage.record('zeptomail', 'email.send', units=10)
    api_usage.record('zeptomail', 'email.send', units=1, ok=False, error='HTTP 402')
    api_usage.record('twilio', 'sms.send', units=2)
    data = client.get('/api/admin/api-usage?days=30').get_json()

    by = {p['provider']: p for p in data['providers']}
    assert by['zeptomail']['calls'] == 2 and by['zeptomail']['failed'] == 1
    assert by['zeptomail']['failure_rate'] == 0.5
    assert by['twilio']['units'] == 2
    assert data['total_cost_usd'] == pytest.approx(
        10 * api_usage.ZEPTOMAIL_USD_PER_RECIPIENT + 2 * api_usage.TWILIO_USD_PER_SEGMENT, abs=1e-6)
    assert data['monthly_run_rate_usd'] == pytest.approx(data['total_cost_usd'], abs=0.01)
    assert data['recent_failures'][0]['error'] == 'HTTP 402'
    assert data['tracking_since'] is not None
    assert {d['provider'] for d in data['daily']} == {'zeptomail', 'twilio'}


def test_usage_report_includes_the_bdr_agent(client, admin_login):
    from app.crm.models import CrmAgentRun
    db.session.add(CrmAgentRun(kind='follow_up', status='done', model='claude-sonnet-5',
                               input_tokens=500, output_tokens=200, cost_usd=0.42))
    db.session.commit()
    data = client.get('/api/admin/api-usage').get_json()
    agent = [o for o in data['operations'] if o['operation'] == 'agent.follow_up']
    assert agent and agent[0]['cost_usd'] == pytest.approx(0.42)


# ---------------------------------------------------------------------------
# Manager messaging
# ---------------------------------------------------------------------------

@pytest.fixture()
def gardens(db_session, make_user):
    """Two owners, one co-organizer, one treasurer, one person owning two gardens."""
    multi = make_user(username='multi', display_name='Mia Multi')
    solo = make_user(username='solo', display_name='Sol Solo')
    co = make_user(username='coorg', display_name='Coco Co')
    treasurer = make_user(username='tres', display_name='Tess Treasurer')
    gone = make_user(username='gone', display_name='Gone Owner')

    g1 = CommunityGarden(name='Apple Garden', slug='apple', organizer_id=multi.id,
                         state='NE', subscription_status='active')
    g2 = CommunityGarden(name='Bean Garden', slug='bean', organizer_id=multi.id,
                         state='NE', subscription_status='trialing')
    g3 = CommunityGarden(name='Corn Garden', slug='corn', organizer_id=solo.id,
                         state='IA', subscription_status='none')
    g4 = CommunityGarden(name='Dormant Garden', slug='dormant', organizer_id=gone.id,
                         state='NE', is_active=False)
    db.session.add_all([g1, g2, g3, g4])
    db.session.commit()
    db.session.add_all([
        GardenMembership(garden_id=g1.id, user_id=co.id, role='co_organizer'),
        GardenMembership(garden_id=g3.id, user_id=treasurer.id, role='treasurer'),
    ])
    db.session.commit()
    return {'multi': multi, 'solo': solo, 'co': co, 'treasurer': treasurer,
            'gone': gone, 'g1': g1, 'g2': g2, 'g3': g3, 'g4': g4}


def _preview(client, audience):
    return client.post('/api/admin/manager-broadcast/preview',
                       json={'audience': audience}).get_json()


def test_someone_managing_two_gardens_is_one_recipient(client, admin_login, gardens):
    data = _preview(client, {'roles': 'owners'})
    names = [r['name'] for r in data['recipients']]
    assert names.count('Mia Multi') == 1
    mia = next(r for r in data['recipients'] if r['name'] == 'Mia Multi')
    assert mia['gardens'] == ['Apple Garden', 'Bean Garden']


def test_inactive_gardens_are_left_out_by_default(client, admin_login, gardens):
    names = {r['name'] for r in _preview(client, {'roles': 'owners'})['recipients']}
    assert 'Gone Owner' not in names
    names = {r['name'] for r in _preview(
        client, {'roles': 'owners', 'active_only': False})['recipients']}
    assert 'Gone Owner' in names


def test_role_scope_widens(client, admin_login, gardens):
    owners = _preview(client, {'roles': 'owners'})['count']
    with_co = _preview(client, {'roles': 'owners_and_co'})['count']
    staff = _preview(client, {'roles': 'all_staff'})['count']
    assert (owners, with_co, staff) == (2, 3, 4)


def test_plan_and_state_filters(client, admin_login, gardens):
    trialing = {r['name'] for r in _preview(
        client, {'roles': 'owners', 'plans': ['trialing']})['recipients']}
    assert trialing == {'Mia Multi'}
    iowa = {r['name'] for r in _preview(
        client, {'roles': 'owners', 'states': ['ia']})['recipients']}
    assert iowa == {'Sol Solo'}


def test_deleted_accounts_are_never_included(client, admin_login, gardens):
    from datetime import datetime, timezone
    gardens['solo'].deleted_at = datetime.now(timezone.utc)
    db.session.commit()
    names = {r['name'] for r in _preview(client, {'roles': 'owners'})['recipients']}
    assert 'Sol Solo' not in names


def test_preview_flags_suppressed_addresses(client, admin_login, gardens):
    db.session.add(EmailUnsubscribe(email=gardens['solo'].email))
    db.session.commit()
    data = _preview(client, {'roles': 'owners'})
    assert data['suppressed'] == 1 and data['emailable'] == data['count'] - 1


def _send(client, **kw):
    payload = {'subject': 'Season update', 'body': 'Line one.\n\nLine <two>.',
               'channels': ['email', 'inapp'], 'audience': {'roles': 'owners'}}
    payload.update(kw)
    return client.post('/api/admin/manager-broadcast', json=payload)


def test_send_refuses_without_a_preview_count(client, admin_login, gardens):
    assert _send(client).status_code == 400


def test_send_refuses_when_the_audience_changed_since_preview(client, admin_login, gardens):
    """Never reach people nobody looked at."""
    r = _send(client, expected_count=99)
    assert r.status_code == 409
    assert ManagerBroadcast.query.count() == 0


def test_send_delivers_records_and_skips_suppressed(client, admin_login, gardens):
    db.session.add(EmailUnsubscribe(email=gardens['solo'].email))
    db.session.commit()
    count = _preview(client, {'roles': 'owners'})['count']
    sent = []
    with mock.patch('app.email_service.send_email',
                    side_effect=lambda to, subj, html, **k: sent.append((to, html)) or True):
        r = _send(client, expected_count=count)
    assert r.status_code == 201, r.get_json()
    b = r.get_json()['broadcast']
    assert (b['recipient_count'], b['emailed'], b['suppressed'], b['notified']) == (2, 1, 1, 2)

    # The unsubscribed owner got the in-app notice but not the email.
    assert [to for to, _ in sent] == [gardens['multi'].email]
    assert Notification.query.filter_by(user_id=gardens['solo'].id,
                                        type='platform_message').count() == 1

    # Plain text in, safe HTML out: the angle brackets arrive as text.
    html = sent[0][1]
    assert '&lt;two&gt;' in html and '<two>' not in html
    assert 'Hi Mia Multi' in html and 'Apple Garden, Bean Garden' in html

    history = client.get('/api/admin/manager-broadcasts').get_json()['broadcasts']
    assert history[0]['subject'] == 'Season update'


def test_send_validates_its_inputs(client, admin_login, gardens):
    assert _send(client, subject='', expected_count=2).status_code == 400
    assert _send(client, channels=[], expected_count=2).status_code == 400
    assert _send(client, body='x' * 5001, expected_count=2).status_code == 400


def test_messaging_requires_admin(client, make_user, gardens):
    u = make_user(username='plain2')
    login_via_api(client, u.email, 'Password1')
    assert client.post('/api/admin/manager-broadcast/preview', json={}).status_code in (401, 403)
    assert _send(client, expected_count=2).status_code in (401, 403)
