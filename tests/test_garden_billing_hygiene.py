"""Product-side conversion hygiene tests.

- /subscribe verifies the subscription with Stripe server-side (no more
  activating on a client-supplied id, and no more activating when the
  retrieve raised).
- The Stripe webhook activates a paid subscription by metadata.garden_id when
  no local row knows the stripe_subscription_id (browser never reached
  /subscribe).
- require_garden_pro honors the 7-day past_due grace the dunning email
  promises.
- Day-21 re-engagement never claims "0 members are waiting".
- create_garden sends the day-0 welcome; start-trial and paid activation ping
  the operator.
"""
import itertools
import json
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app import db as _db
from app import stripe_service
from tests.conftest import login_via_api

_counter = itertools.count()


def _naive_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture()
def billing_garden(db_session, make_user):
    """Organizer (logged-in-able) + garden with no subscription."""
    from app.models import CommunityGarden
    n = next(_counter)
    organizer = make_user(username=f'billorg{n}',
                          email=f'billorg{n}@example.com',
                          role='manager', password='GoodPass1')
    garden = CommunityGarden(
        name=f'Billing Garden {n}',
        slug=f'billing-garden-{n}-{uuid.uuid4().hex[:6]}',
        city='Omaha', state='NE',
        organizer_id=organizer.id)
    db_session.add(garden)
    db_session.commit()
    return garden, organizer


def _post_event(client, event):
    return client.post('/api/webhooks/stripe', data=json.dumps(event),
                       content_type='application/json')


def _sub_event(sub_id, garden_id, status='active', event_id=None, meta=None):
    now = int(datetime.now(timezone.utc).timestamp())
    metadata = {'type': 'garden_pro', 'garden_id': str(garden_id),
                'billing_cycle': 'monthly'}
    if meta is not None:
        metadata = meta
    return {
        'id': event_id or f'evt_{uuid.uuid4().hex[:12]}',
        'type': 'customer.subscription.updated',
        'data': {'object': {
            'id': sub_id,
            'status': status,
            'current_period_start': now,
            'current_period_end': now + 30 * 86400,
            'cancel_at_period_end': False,
            'metadata': metadata,
        }},
    }


# ---------------------------------------------------------------------------
# /subscribe server-side verification
# ---------------------------------------------------------------------------
def test_subscribe_does_not_activate_when_stripe_retrieve_fails(client, billing_garden):
    garden, organizer = billing_garden
    garden_id = garden.id
    login_via_api(client, organizer.email, 'GoodPass1')

    with patch.object(stripe_service, 'is_configured', return_value=True), \
         patch.object(stripe_service, 'retrieve_subscription',
                      side_effect=Exception('stripe down')):
        resp = client.post(f'/api/gardens/{garden_id}/billing/subscribe',
                           json={'subscription_id': 'sub_x'})
    assert resp.status_code == 502

    from app.models import CommunityGarden, GardenSubscription
    assert _db.session.get(CommunityGarden, garden_id).subscription_status != 'active'
    assert GardenSubscription.query.filter_by(garden_id=garden_id,
                                              status='active').count() == 0


def test_subscribe_rejects_unpaid_subscription(client, billing_garden):
    garden, organizer = billing_garden
    garden_id = garden.id
    login_via_api(client, organizer.email, 'GoodPass1')

    fake = SimpleNamespace(status='incomplete', current_period_end=None,
                           metadata={'garden_id': str(garden_id)})
    with patch.object(stripe_service, 'is_configured', return_value=True), \
         patch.object(stripe_service, 'retrieve_subscription', return_value=fake):
        resp = client.post(f'/api/gardens/{garden_id}/billing/subscribe',
                           json={'subscription_id': 'sub_x'})
    assert resp.status_code == 400

    from app.models import CommunityGarden
    assert _db.session.get(CommunityGarden, garden_id).subscription_status != 'active'


def test_subscribe_requires_subscription_id_when_stripe_configured(client, billing_garden):
    garden, organizer = billing_garden
    login_via_api(client, organizer.email, 'GoodPass1')
    with patch.object(stripe_service, 'is_configured', return_value=True):
        resp = client.post(f'/api/gardens/{garden.id}/billing/subscribe', json={})
    assert resp.status_code == 400


def test_subscribe_rejects_foreign_garden_subscription(client, billing_garden):
    garden, organizer = billing_garden
    garden_id = garden.id
    login_via_api(client, organizer.email, 'GoodPass1')

    fake = SimpleNamespace(status='active',
                           current_period_end=int(datetime.now(timezone.utc).timestamp()) + 86400,
                           metadata={'garden_id': str(garden_id + 999)})
    with patch.object(stripe_service, 'is_configured', return_value=True), \
         patch.object(stripe_service, 'retrieve_subscription', return_value=fake):
        resp = client.post(f'/api/gardens/{garden_id}/billing/subscribe',
                           json={'subscription_id': 'sub_other'})
    assert resp.status_code == 400


def test_subscribe_activates_verified_subscription(client, billing_garden):
    garden, organizer = billing_garden
    garden_id = garden.id
    login_via_api(client, organizer.email, 'GoodPass1')

    period_end = int(datetime.now(timezone.utc).timestamp()) + 30 * 86400
    fake = SimpleNamespace(status='active', current_period_end=period_end,
                           metadata={'garden_id': str(garden_id)})
    with patch.object(stripe_service, 'is_configured', return_value=True), \
         patch.object(stripe_service, 'retrieve_subscription', return_value=fake), \
         patch('app.email_service.send_operator_conversion_ping') as ping:
        resp = client.post(f'/api/gardens/{garden_id}/billing/subscribe',
                           json={'subscription_id': 'sub_ok'})
    assert resp.status_code == 200

    from app.models import CommunityGarden, GardenSubscription
    assert _db.session.get(CommunityGarden, garden_id).subscription_status == 'active'
    sub = GardenSubscription.query.filter_by(garden_id=garden_id).first()
    assert sub.status == 'active'
    assert sub.stripe_subscription_id == 'sub_ok'
    ping.assert_called_once()
    assert ping.call_args[0][0] == 'paid'


# ---------------------------------------------------------------------------
# Webhook activation fallback (metadata.garden_id)
# ---------------------------------------------------------------------------
def test_webhook_fallback_activates_unlinked_paid_subscription(client, billing_garden, monkeypatch):
    monkeypatch.delenv('STRIPE_SECRET_KEY', raising=False)
    garden, organizer = billing_garden
    garden_id = garden.id
    # Local trialing row that never learned its stripe id (/subscribe missed).
    from app.models import GardenSubscription
    start = _naive_now() - timedelta(days=5)
    local = GardenSubscription(garden_id=garden_id, status='trialing',
                               trial_start=start,
                               trial_end=start + timedelta(days=14))
    _db.session.add(local)
    _db.session.commit()

    with patch('app.email_service.send_operator_conversion_ping') as ping:
        resp = _post_event(client, _sub_event('sub_fallback_1', garden_id))
    assert resp.status_code == 200

    from app.models import CommunityGarden
    _db.session.refresh(local)
    assert local.stripe_subscription_id == 'sub_fallback_1'
    assert local.status == 'active'
    assert local.current_period_end is not None
    assert _db.session.get(CommunityGarden, garden_id).subscription_status == 'active'
    ping.assert_called_once()
    assert ping.call_args[0][0] == 'paid'


def test_webhook_fallback_creates_row_when_none_exists(client, billing_garden, monkeypatch):
    monkeypatch.delenv('STRIPE_SECRET_KEY', raising=False)
    garden, organizer = billing_garden
    garden_id = garden.id

    resp = _post_event(client, _sub_event('sub_fallback_2', garden_id))
    assert resp.status_code == 200

    from app.models import CommunityGarden, GardenSubscription
    sub = GardenSubscription.query.filter_by(garden_id=garden_id).first()
    assert sub is not None
    assert sub.stripe_subscription_id == 'sub_fallback_2'
    assert sub.status == 'active'
    assert sub.billing_cycle == 'monthly'
    assert _db.session.get(CommunityGarden, garden_id).subscription_status == 'active'


def test_webhook_fallback_ignores_incomplete_subscription(client, billing_garden, monkeypatch):
    """create_checkout makes an 'incomplete' Stripe sub before payment — the
    fallback must never activate that shell."""
    monkeypatch.delenv('STRIPE_SECRET_KEY', raising=False)
    garden, organizer = billing_garden
    garden_id = garden.id

    resp = _post_event(client, _sub_event('sub_shell', garden_id, status='incomplete'))
    assert resp.status_code == 200

    from app.models import CommunityGarden, GardenSubscription
    assert GardenSubscription.query.filter_by(garden_id=garden_id).count() == 0
    assert _db.session.get(CommunityGarden, garden_id).subscription_status != 'active'


def test_webhook_fallback_is_idempotent_per_event(client, billing_garden, monkeypatch):
    monkeypatch.delenv('STRIPE_SECRET_KEY', raising=False)
    garden, organizer = billing_garden
    evt = _sub_event('sub_fallback_3', garden.id, event_id='evt_fixed_1')
    assert _post_event(client, evt).status_code == 200
    resp = _post_event(client, evt)
    assert resp.status_code == 200
    assert resp.get_json().get('duplicate') is True


# ---------------------------------------------------------------------------
# past_due 7-day grace in require_garden_pro
# ---------------------------------------------------------------------------
def test_past_due_within_grace_keeps_pro(billing_garden):
    from app.models import GardenSubscription
    from app.api.garden_billing_api import require_garden_pro
    garden, organizer = billing_garden
    garden.subscription_status = 'past_due'
    sub = GardenSubscription(garden_id=garden.id, status='past_due',
                             current_period_end=_naive_now() - timedelta(days=3))
    _db.session.add(sub)
    _db.session.commit()

    allowed, err = require_garden_pro(garden)
    assert allowed is True
    assert err is None


def test_past_due_beyond_grace_is_gated(billing_garden):
    from app.models import GardenSubscription
    from app.api.garden_billing_api import require_garden_pro
    garden, organizer = billing_garden
    garden.subscription_status = 'past_due'
    sub = GardenSubscription(garden_id=garden.id, status='past_due',
                             current_period_end=_naive_now() - timedelta(days=10))
    _db.session.add(sub)
    _db.session.commit()

    allowed, err = require_garden_pro(garden)
    assert allowed is False
    assert err is not None


# ---------------------------------------------------------------------------
# Day-21 re-engagement subject never says "0 members"
# ---------------------------------------------------------------------------
def test_reengagement_zero_members_gets_numberless_subject(billing_garden):
    from app.email_service import send_garden_trial_reengagement
    garden, organizer = billing_garden
    with patch('app.email_service.send_email') as send:
        send_garden_trial_reengagement(garden, organizer)
    send.assert_called_once()
    subject = send.call_args[0][1]
    assert 'members are waiting' not in subject
    assert '0' not in subject.replace(garden.name, '')


def test_reengagement_with_members_keeps_count_subject(billing_garden, make_user):
    from app.models import GardenPlot
    from app.email_service import send_garden_trial_reengagement
    garden, organizer = billing_garden
    member = make_user(username=f'plotmem{next(_counter)}',
                       email=f'plotmem{next(_counter)}@example.com')
    _db.session.add(GardenPlot(garden_id=garden.id, plot_number='A1',
                               status='assigned', assigned_to_id=member.id))
    _db.session.commit()

    with patch('app.email_service.send_email') as send:
        send_garden_trial_reengagement(garden, organizer)
    subject = send.call_args[0][1]
    assert '1 members are waiting' in subject


# ---------------------------------------------------------------------------
# Day-0 welcome on garden creation
# ---------------------------------------------------------------------------
def test_create_garden_sends_welcome(client, make_user):
    organizer = make_user(username='welcomeorg', email='welcomeorg@example.com',
                          role='manager', password='GoodPass1')
    login_via_api(client, 'welcomeorg@example.com', 'GoodPass1')
    with patch('app.email_service.send_garden_welcome') as welcome:
        resp = client.post('/api/gardens', json={'name': 'Welcome Test Garden'})
    assert resp.status_code == 201
    welcome.assert_called_once()
    garden_arg, organizer_arg = welcome.call_args[0]
    assert garden_arg.name == 'Welcome Test Garden'
    assert organizer_arg.email == 'welcomeorg@example.com'


def test_welcome_email_failure_does_not_fail_create(client, make_user):
    make_user(username='welcomeorg2', email='welcomeorg2@example.com',
              role='manager', password='GoodPass1')
    login_via_api(client, 'welcomeorg2@example.com', 'GoodPass1')
    with patch('app.email_service.send_garden_welcome',
               side_effect=Exception('smtp down')):
        resp = client.post('/api/gardens', json={'name': 'Welcome Test Garden 2'})
    assert resp.status_code == 201


# ---------------------------------------------------------------------------
# Operator conversion pings
# ---------------------------------------------------------------------------
def test_start_trial_pings_operator(client, billing_garden):
    garden, organizer = billing_garden
    login_via_api(client, organizer.email, 'GoodPass1')
    with patch('app.email_service.send_operator_conversion_ping') as ping, \
         patch('app.email_service.send_garden_trial_welcome'):
        resp = client.post(f'/api/gardens/{garden.id}/billing/start-trial')
    assert resp.status_code == 201
    ping.assert_called_once()
    assert ping.call_args[0][0] == 'trial_started'


def test_operator_ping_content_and_crm_link(app, billing_garden):
    from app.email_service import send_operator_conversion_ping
    from app.crm.models import Contact
    garden, organizer = billing_garden
    contact = Contact(name='Org Contact', email=organizer.email.upper())
    _db.session.add(contact)
    _db.session.commit()

    app.config['OPERATOR_ALERT_EMAIL'] = 'ops@example.com'
    try:
        with patch('app.email_service.send_email', return_value=True) as send:
            send_operator_conversion_ping('trial_started', garden, organizer)
    finally:
        app.config.pop('OPERATOR_ALERT_EMAIL', None)

    send.assert_called_once()
    to, subject, body = send.call_args[0][:3]
    assert to == 'ops@example.com'
    assert 'Trial started' in subject
    assert garden.name in subject
    assert organizer.email in body
    assert 'Omaha, NE' in body
    assert '/admin/gardens' in body
    assert f'/crm/contacts/{contact.id}' in body


def test_operator_ping_never_raises(billing_garden):
    from app.email_service import send_operator_conversion_ping
    garden, organizer = billing_garden
    with patch('app.email_service.send_email', side_effect=Exception('boom')):
        # Must swallow, not raise, into the request path.
        result = send_operator_conversion_ping('paid', garden, organizer)
    assert result is False


def test_invoice_payment_failed_pings_operator_once(client, billing_garden, monkeypatch):
    monkeypatch.delenv('STRIPE_SECRET_KEY', raising=False)
    garden, organizer = billing_garden
    from app.models import GardenSubscription
    sub = GardenSubscription(garden_id=garden.id, status='active',
                             stripe_subscription_id='sub_dunning_1')
    _db.session.add(sub)
    _db.session.commit()

    def _evt(event_id):
        return {'id': event_id, 'type': 'invoice.payment_failed',
                'data': {'object': {'subscription': 'sub_dunning_1'}}}

    with patch('app.email_service.send_operator_conversion_ping') as ping, \
         patch('app.email_service.send_garden_payment_failed'):
        assert _post_event(client, _evt('evt_dun_1')).status_code == 200
        # A retry attempt arrives as a NEW event id — no second ping.
        assert _post_event(client, _evt('evt_dun_2')).status_code == 200
    ping.assert_called_once()
    assert ping.call_args[0][0] == 'past_due'
    _db.session.refresh(sub)
    assert sub.status == 'past_due'
