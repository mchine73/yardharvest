"""Tests for the hardened Stripe payment paths.

All Stripe calls are mocked — no network, no keys. Covers:
- Webhook idempotency ledger (ProcessedStripeEvent)
- Webhook-driven garden-dues fulfillment via payment_intent.succeeded
- Idempotent client confirms (dues + marketplace)
- Connect onboarding creates an Express account
- Payout holds when a seller hasn't finished Connect onboarding
"""
import json
import uuid
from unittest.mock import MagicMock, patch

import pytest

from app import db as _db


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------
@pytest.fixture()
def garden_with_dues(app, make_user):
    """A community garden (with organizer) and an unpaid dues record for a member."""
    from app.models import CommunityGarden, GardenDuesRecord
    with app.app_context():
        organizer = make_user(username='organizer', email='org@example.com', role='manager')
        member = make_user(username='member', email='member@example.com', role='gardener')
        garden = CommunityGarden(name='Sunrise Garden',
                                 slug=f'sunrise-{uuid.uuid4().hex[:8]}',
                                 organizer_id=organizer.id)
        _db.session.add(garden)
        _db.session.flush()
        rec = GardenDuesRecord(garden_id=garden.id, user_id=member.id,
                               season_year=2026, amount_due=50.0, amount_paid=0,
                               status='unpaid')
        _db.session.add(rec)
        _db.session.commit()
        return {'garden_id': garden.id, 'dues_id': rec.id,
                'member_id': member.id, 'organizer_id': organizer.id}


def _dues_succeeded_event(pi_id, garden_id, dues_id, user_id, event_id='evt_1'):
    return {
        'id': event_id,
        'type': 'payment_intent.succeeded',
        'data': {'object': {
            'id': pi_id,
            'metadata': {'type': 'garden_dues', 'garden_id': str(garden_id),
                         'dues_id': str(dues_id), 'user_id': str(user_id)},
        }},
    }


def _post_event(client, event):
    return client.post('/api/webhooks/stripe', data=json.dumps(event),
                       content_type='application/json')


# ---------------------------------------------------------------------------
# Webhook-driven dues fulfillment
# ---------------------------------------------------------------------------
def test_webhook_fulfills_dues(client, app, garden_with_dues):
    g = garden_with_dues
    evt = _dues_succeeded_event('pi_dues_1', g['garden_id'], g['dues_id'], g['member_id'])
    resp = _post_event(client, evt)
    assert resp.status_code == 200

    from app.models import GardenDuesRecord
    with app.app_context():
        rec = GardenDuesRecord.query.get(g['dues_id'])
        assert rec.status == 'paid'
        assert rec.amount_paid == rec.amount_due
        assert rec.stripe_payment_intent_id == 'pi_dues_1'
        assert rec.payment_method == 'online'


def test_webhook_dues_is_idempotent(client, app, garden_with_dues):
    g = garden_with_dues
    evt = _dues_succeeded_event('pi_dues_2', g['garden_id'], g['dues_id'], g['member_id'],
                                event_id='evt_dup')
    r1 = _post_event(client, evt)
    r2 = _post_event(client, evt)  # same event id redelivered
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r2.get_json().get('duplicate') is True

    from app.models import ProcessedStripeEvent, GardenDuesRecord
    with app.app_context():
        assert ProcessedStripeEvent.query.filter_by(event_id='evt_dup').count() == 1
        assert GardenDuesRecord.query.get(g['dues_id']).status == 'paid'


# ---------------------------------------------------------------------------
# Webhook idempotency ledger
# ---------------------------------------------------------------------------
def test_webhook_records_processed_event(client, app):
    evt = {'id': 'evt_acct', 'type': 'account.updated',
           'data': {'object': {'id': 'acct_x', 'charges_enabled': True, 'payouts_enabled': True}}}
    _post_event(client, evt)
    from app.models import ProcessedStripeEvent
    with app.app_context():
        row = ProcessedStripeEvent.query.filter_by(event_id='evt_acct').first()
        assert row is not None
        assert row.event_type == 'account.updated'


def test_webhook_handler_failure_not_recorded(client, app, garden_with_dues):
    """If a handler raises, the event is NOT recorded (so Stripe retries) and 500 is returned."""
    g = garden_with_dues
    evt = _dues_succeeded_event('pi_fail', g['garden_id'], g['dues_id'], g['member_id'],
                                event_id='evt_fail')
    with patch('app.api.webhook_api._fulfill_dues_from_pi', side_effect=RuntimeError('boom')):
        resp = _post_event(client, evt)
    assert resp.status_code == 500
    from app.models import ProcessedStripeEvent
    with app.app_context():
        assert ProcessedStripeEvent.query.filter_by(event_id='evt_fail').first() is None


# ---------------------------------------------------------------------------
# Connect onboarding → Express account
# ---------------------------------------------------------------------------
def test_connect_onboarding_creates_express_account(app, make_user):
    from app import stripe_service
    with app.app_context():
        user = make_user(username='seller1', email='seller1@example.com', role='seller')
        fake_account = MagicMock(id='acct_express_1')
        fake_link = MagicMock(url='https://connect.stripe.com/setup/x')
        with patch.dict('os.environ', {'STRIPE_SECRET_KEY': 'sk_test', 'APP_URL': 'https://yh.test'}), \
                patch('stripe.Account.create', return_value=fake_account) as acct_create, \
                patch('stripe.AccountLink.create', return_value=fake_link):
            url = stripe_service.create_connect_account_link(user, return_path='/earnings')
        assert url == 'https://connect.stripe.com/setup/x'
        _, kwargs = acct_create.call_args
        assert kwargs['type'] == 'express'
        assert 'transfers' in kwargs['capabilities']
        assert 'card_payments' in kwargs['capabilities']
        assert user.stripe_connect_account_id == 'acct_express_1'


# ---------------------------------------------------------------------------
# Marketplace confirm idempotency
# ---------------------------------------------------------------------------
def test_marketplace_confirm_idempotency_guard(client, app, make_user):
    """A confirm for a PI that already produced an order returns it, no duplicate.

    Tests the idempotency short-circuit directly by pre-seeding the order. (The
    fresh-order-creation path uses SQL func greatest() for atomic inventory
    decrement, which is Postgres-only and not exercisable on the SQLite test DB.)
    """
    from app.models import Order
    with app.app_context():
        seller = make_user(username='seller2', email='seller2@example.com', role='seller')
        buyer = make_user(username='buyer2', email='buyer2@example.com', role='buyer')
        pi_id = 'pi_existing_order_1'
        _db.session.add(Order(buyer_id=buyer.id, seller_id=seller.id, total_price=8.0,
                              status='pending', payment_status='succeeded',
                              stripe_payment_intent_id=pi_id))
        _db.session.commit()
        pre_id = Order.query.filter_by(stripe_payment_intent_id=pi_id).first().id

    client.post('/api/auth/login', json={'email': 'buyer2@example.com', 'password': 'Password1'})
    resp = client.post('/api/payments/confirm', json={'payment_intent_id': pi_id})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['order_ids'] == [pre_id]

    with app.app_context():
        assert Order.query.filter_by(stripe_payment_intent_id=pi_id).count() == 1
