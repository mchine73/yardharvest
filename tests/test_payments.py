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
        rec = _db.session.get(GardenDuesRecord, g['dues_id'])
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
        assert _db.session.get(GardenDuesRecord, g['dues_id']).status == 'paid'


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
# Connect embedded onboarding (Account Sessions, in-app flow)
# ---------------------------------------------------------------------------
def test_account_session_enables_embedded_onboarding(app, make_user):
    """create_account_session creates the Express account if missing and
    requests the embedded onboarding/management components."""
    from app import stripe_service
    with app.app_context():
        user = make_user(username='seller_emb', email='seller_emb@example.com', role='seller')
        fake_account = MagicMock(id='acct_emb_1')
        fake_session = MagicMock(client_secret='accs_secret_1')
        with patch.dict('os.environ', {'STRIPE_SECRET_KEY': 'sk_test'}), \
                patch('stripe.Account.create', return_value=fake_account), \
                patch('stripe.AccountSession.create', return_value=fake_session) as sess_create:
            secret = stripe_service.create_account_session(user)
        assert secret == 'accs_secret_1'
        assert user.stripe_connect_account_id == 'acct_emb_1'
        _, kwargs = sess_create.call_args
        assert kwargs['account'] == 'acct_emb_1'
        assert kwargs['components']['account_onboarding'] == {'enabled': True}
        assert kwargs['components']['account_management'] == {'enabled': True}


def test_account_session_endpoint_returns_secret(client, app, make_user):
    with app.app_context():
        make_user(username='seller_emb2', email='seller_emb2@example.com', role='seller')
    client.post('/api/auth/login', json={'email': 'seller_emb2@example.com', 'password': 'Password1'})

    fake_account = MagicMock(id='acct_emb_2')
    fake_session = MagicMock(client_secret='accs_secret_2')
    with patch.dict('os.environ', {'STRIPE_SECRET_KEY': 'sk_test',
                                   'STRIPE_PUBLISHABLE_KEY': 'pk_test'}), \
            patch('stripe.Account.create', return_value=fake_account), \
            patch('stripe.AccountSession.create', return_value=fake_session):
        resp = client.post('/api/payments/connect/account-session')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['client_secret'] == 'accs_secret_2'
    assert body['publishable_key'] == 'pk_test'
    assert body['account_id'] == 'acct_emb_2'


def test_account_session_endpoint_requires_seller(client, app, make_user):
    with app.app_context():
        make_user(username='buyer_emb', email='buyer_emb@example.com', role='buyer')
    client.post('/api/auth/login', json={'email': 'buyer_emb@example.com', 'password': 'Password1'})
    with patch.dict('os.environ', {'STRIPE_SECRET_KEY': 'sk_test'}):
        resp = client.post('/api/payments/connect/account-session')
    assert resp.status_code == 403


def test_account_session_endpoint_unconfigured(client, app, make_user):
    with app.app_context():
        make_user(username='seller_emb3', email='seller_emb3@example.com', role='seller')
    client.post('/api/auth/login', json={'email': 'seller_emb3@example.com', 'password': 'Password1'})
    with patch.dict('os.environ', {'STRIPE_SECRET_KEY': ''}):
        resp = client.post('/api/payments/connect/account-session')
    assert resp.status_code == 503


def test_garden_payout_account_session_organizer_only(client, app, garden_with_dues):
    """The garden manager gets a session; a non-manager member gets 403."""
    from app.models import User
    g = garden_with_dues
    with app.app_context():
        organizer_email = _db.session.get(User, g['organizer_id']).email
        member_email = _db.session.get(User, g['member_id']).email

    fake_account = MagicMock(id='acct_org_1')
    fake_session = MagicMock(client_secret='accs_org_secret')

    client.post('/api/auth/login', json={'email': organizer_email, 'password': 'Password1'})
    with patch.dict('os.environ', {'STRIPE_SECRET_KEY': 'sk_test',
                                   'STRIPE_PUBLISHABLE_KEY': 'pk_test'}), \
            patch('stripe.Account.create', return_value=fake_account), \
            patch('stripe.AccountSession.create', return_value=fake_session):
        resp = client.post(f"/api/gardens/{g['garden_id']}/payouts/account-session")
    assert resp.status_code == 200
    assert resp.get_json()['client_secret'] == 'accs_org_secret'

    client.post('/api/auth/login', json={'email': member_email, 'password': 'Password1'})
    with patch.dict('os.environ', {'STRIPE_SECRET_KEY': 'sk_test'}):
        resp = client.post(f"/api/gardens/{g['garden_id']}/payouts/account-session")
    assert resp.status_code == 403


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


# ---------------------------------------------------------------------------
# Checkout snapshot (create-session) + webhook-driven marketplace fulfillment
# ---------------------------------------------------------------------------
def test_create_session_persists_checkout_snapshot(client, app, make_user):
    """create-session stores a PendingCheckout snapshot keyed by the PI id."""
    from app.models import Listing, CartItem, PendingCheckout
    with app.app_context():
        seller = make_user(username='seller3', email='seller3@example.com', role='seller')
        listing = Listing(seller_id=seller.id, title='Kale', description='Leafy',
                          price=3.0, quantity_available=10, vegetable_type='Kale',
                          unit='bunch', is_active=True)
        _db.session.add(listing)
        _db.session.commit()
        seller_id, listing_id = seller.id, listing.id
        make_user(username='buyer3', email='buyer3@example.com', role='buyer')
    with app.app_context():
        from app.models import User
        buyer = User.query.filter_by(email='buyer3@example.com').first()
        _db.session.add(CartItem(buyer_id=buyer.id, listing_id=listing_id, quantity=2))
        _db.session.commit()

    client.post('/api/auth/login', json={'email': 'buyer3@example.com', 'password': 'Password1'})

    fake_pi = MagicMock(id='pi_snap_1', client_secret='cs_snap_1')
    with patch('app.stripe_service.is_configured', return_value=True), \
            patch('app.stripe_service.get_or_create_customer', return_value='cus_1'), \
            patch('app.stripe_service.get_publishable_key', return_value='pk_test'), \
            patch('app.stripe_service.create_payment_intent', return_value=fake_pi):
        resp = client.post('/api/payments/create-session',
                           json={f'fulfillment_{seller_id}': 'pickup'})
    assert resp.status_code == 200
    assert resp.get_json()['payment_intent_id'] == 'pi_snap_1'

    with app.app_context():
        pc = PendingCheckout.query.filter_by(payment_intent_id='pi_snap_1').first()
        assert pc is not None
        payload = json.loads(pc.payload_json)
        assert payload['sellers'][0]['seller_id'] == seller_id
        assert payload['sellers'][0]['items'][0]['listing_id'] == listing_id
        assert payload['sellers'][0]['items'][0]['quantity'] == 2


def test_webhook_fulfills_marketplace_from_snapshot(client, app, make_user):
    """payment_intent.succeeded with a snapshot routes to fulfill_payment_intent.

    fulfill_payment_intent is patched (its order-creation uses Postgres-only
    SQL func greatest); we assert the webhook invokes it with the snapshot's
    buyer id — i.e. the webhook will create the order even with no /confirm.
    """
    from app.models import PendingCheckout
    with app.app_context():
        buyer = make_user(username='buyer4', email='buyer4@example.com', role='buyer')
        _db.session.add(PendingCheckout(payment_intent_id='pi_wh_1', buyer_id=buyer.id,
                                        payload_json=json.dumps({'sellers': [], 'promo_code': ''})))
        _db.session.commit()
        buyer_id = buyer.id

    evt = {'id': 'evt_mkt', 'type': 'payment_intent.succeeded',
           'data': {'object': {'id': 'pi_wh_1', 'metadata': {'type': 'marketplace_order',
                                                             'user_id': str(buyer_id)}}}}
    with patch('app.api.payment_api.fulfill_payment_intent',
               return_value=([], True)) as fulfill:
        resp = _post_event(client, evt)
    assert resp.status_code == 200
    fulfill.assert_called_once_with('pi_wh_1', buyer_id)


def test_admin_can_set_garden_dues_fee(client, app, make_user):
    """The garden dues platform fee is admin-editable via /api/admin/pricing."""
    with app.app_context():
        make_user(username='adm', email='adm@example.com', role='both', is_admin=True)
    client.post('/api/auth/login', json={'email': 'adm@example.com', 'password': 'Password1'})
    r = client.put('/api/admin/pricing', json={'garden_dues_fee_percent': 2.5})
    assert r.status_code == 200
    g = client.get('/api/admin/pricing')
    assert g.status_code == 200
    assert g.get_json()['config']['garden_dues_fee_percent'] == 2.5


def test_pay_dues_routes_to_manager_connect_account(client, app, garden_with_dues):
    """A dues PaymentIntent is a destination charge to the manager's connected
    account (transfer_data.destination + on_behalf_of)."""
    from app import stripe_service
    from app.models import User
    g = garden_with_dues
    with app.app_context():
        organizer = _db.session.get(User, g['organizer_id'])
        organizer.stripe_connect_account_id = 'acct_mgr_1'
        _db.session.commit()

    client.post('/api/auth/login',
                json={'email': 'member@example.com', 'password': 'Password1'})

    captured = {}

    def fake_pi(**kwargs):
        captured.update(kwargs)
        return MagicMock(client_secret='cs_1', id='pi_dues_x')

    with patch.dict('os.environ', {'STRIPE_SECRET_KEY': 'sk_test'}), \
            patch.object(stripe_service, 'connect_account_ready', return_value=True), \
            patch.object(stripe_service, 'connect_payment_method_types',
                         return_value=['card', 'us_bank_account']), \
            patch.object(stripe_service, 'get_or_create_customer', return_value='cus_1'), \
            patch.object(stripe_service, 'create_payment_intent', side_effect=fake_pi):
        resp = client.post(
            f"/api/gardens/{g['garden_id']}/dues/{g['dues_id']}/pay", json={})

    assert resp.status_code == 200
    body = resp.get_json()
    assert body['routed_to_manager'] is True
    # The charge is routed to (and on behalf of) the manager's connected account.
    assert captured['destination_account_id'] == 'acct_mgr_1'
    assert captured['on_behalf_of'] == 'acct_mgr_1'
    assert captured['metadata']['type'] == 'garden_dues'


def test_pay_dues_blocked_when_manager_not_payout_ready(client, app, garden_with_dues):
    """If the manager hasn't completed payout onboarding, dues collection is
    refused (409) rather than charged to the platform — so collected dues always
    reach the manager's connected account."""
    from app import stripe_service
    g = garden_with_dues
    client.post('/api/auth/login',
                json={'email': 'member@example.com', 'password': 'Password1'})

    with patch.dict('os.environ', {'STRIPE_SECRET_KEY': 'sk_test'}), \
            patch.object(stripe_service, 'connect_account_ready', return_value=False), \
            patch.object(stripe_service, 'create_payment_intent') as pi:
        resp = client.post(
            f"/api/gardens/{g['garden_id']}/dues/{g['dues_id']}/pay", json={})

    assert resp.status_code == 409
    assert resp.get_json()['reason'] == 'manager_payout_not_ready'
    pi.assert_not_called()  # no charge created


def test_pay_dues_platform_fallback_when_switch_off(client, app, garden_with_dues):
    """With PricingConfig.dues_require_payout_ready=False, a not-payout-ready
    manager falls back to a plain platform charge (collection still works)."""
    from app import stripe_service
    from app.pricing import get_pricing_config
    g = garden_with_dues
    with app.app_context():
        cfg = get_pricing_config()
        cfg.dues_require_payout_ready = False
        _db.session.commit()

    client.post('/api/auth/login',
                json={'email': 'member@example.com', 'password': 'Password1'})
    captured = {}

    def fake_pi(**kwargs):
        captured.update(kwargs)
        return MagicMock(client_secret='cs', id='pi_plat')

    with patch.dict('os.environ', {'STRIPE_SECRET_KEY': 'sk_test'}), \
            patch.object(stripe_service, 'connect_account_ready', return_value=False), \
            patch.object(stripe_service, 'get_or_create_customer', return_value='cus'), \
            patch.object(stripe_service, 'create_payment_intent', side_effect=fake_pi):
        resp = client.post(
            f"/api/gardens/{g['garden_id']}/dues/{g['dues_id']}/pay", json={})

    assert resp.status_code == 200
    assert resp.get_json()['routed_to_manager'] is False
    assert captured['destination_account_id'] is None  # plain platform charge


def test_admin_pricing_dues_switch_round_trips(client, app, make_user):
    """The dues_require_payout_ready switch is settable + readable via the API."""
    with app.app_context():
        make_user(username='padm', email='padm@example.com', role='both', is_admin=True)
    client.post('/api/auth/login', json={'email': 'padm@example.com', 'password': 'Password1'})
    assert client.put('/api/admin/pricing',
                      json={'dues_require_payout_ready': False}).status_code == 200
    cfg = client.get('/api/admin/pricing').get_json()['config']
    assert cfg['dues_require_payout_ready'] is False


def test_fulfill_payment_intent_idempotent(app, make_user):
    """fulfill_payment_intent returns existing orders (created_now=False) and
    creates nothing new when the PI already has orders."""
    from app.api.payment_api import fulfill_payment_intent
    from app.models import Order
    with app.app_context():
        seller = make_user(username='seller5', email='seller5@example.com', role='seller')
        buyer = make_user(username='buyer5', email='buyer5@example.com', role='buyer')
        _db.session.add(Order(buyer_id=buyer.id, seller_id=seller.id, total_price=5.0,
                              status='pending', payment_status='succeeded',
                              stripe_payment_intent_id='pi_idem_1'))
        _db.session.commit()
        orders, created = fulfill_payment_intent('pi_idem_1', buyer.id)
        assert created is False
        assert len(orders) == 1
        assert Order.query.filter_by(stripe_payment_intent_id='pi_idem_1').count() == 1


# ---------------------------------------------------------------------------
# Webhook signature enforcement
# ---------------------------------------------------------------------------
def test_webhook_rejects_unsigned_when_stripe_configured(client, monkeypatch):
    """With real Stripe keys present but no webhook secret, unsigned events
    must be rejected — otherwise forged payment events could mark orders paid."""
    monkeypatch.setenv('STRIPE_SECRET_KEY', 'sk_test_x')
    monkeypatch.delenv('STRIPE_WEBHOOK_SECRET', raising=False)
    resp = client.post('/api/webhooks/stripe', json={
        'id': 'evt_forged', 'type': 'payment_intent.succeeded',
        'data': {'object': {'id': 'pi_forged', 'metadata': {}}},
    })
    assert resp.status_code == 503


def test_webhook_bad_signature_rejected(client, monkeypatch):
    """With a webhook secret set, an invalid signature returns 400."""
    monkeypatch.setenv('STRIPE_WEBHOOK_SECRET', 'whsec_test')
    resp = client.post('/api/webhooks/stripe',
                       data='{"id": "evt_x", "type": "noop"}',
                       headers={'Stripe-Signature': 't=1,v1=bad'},
                       content_type='application/json')
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Payment method restriction: card + US bank only (no Amazon Pay / Cash App /
# Klarna). Guards create_payment_intent and the capability-aware Connect list.
# ---------------------------------------------------------------------------

def test_payment_intent_restricts_to_card_and_bank(app):
    with app.app_context():
        with patch('stripe.PaymentIntent.create',
                   return_value=MagicMock(id='pi_x', client_secret='cs_x')) as pic:
            from app import stripe_service
            with patch.object(stripe_service, '_configure'):
                stripe_service.create_payment_intent(500, 'cus_1', metadata={})
        kw = pic.call_args.kwargs
        assert kw['payment_method_types'] == ['card', 'us_bank_account']
        assert 'automatic_payment_methods' not in kw


def test_payment_intent_honors_explicit_method_types(app):
    with app.app_context():
        with patch('stripe.PaymentIntent.create',
                   return_value=MagicMock(id='pi_x', client_secret='cs_x')) as pic:
            from app import stripe_service
            with patch.object(stripe_service, '_configure'):
                stripe_service.create_payment_intent(
                    500, 'cus_1', metadata={}, payment_method_types=['card'])
        assert pic.call_args.kwargs['payment_method_types'] == ['card']


def test_connect_payment_method_types_gates_ach_on_capability(app, make_user):
    from app import stripe_service
    with app.app_context():
        u = make_user(username='mgr_pm', email='mgr_pm@example.com')
        u.stripe_connect_account_id = 'acct_test'
        # ACH active -> card + bank
        with patch('stripe.Account.retrieve',
                   return_value={'capabilities': {'us_bank_account_ach_payments': 'active'}}):
            with patch.object(stripe_service, '_configure'):
                assert stripe_service.connect_payment_method_types(u) == ['card', 'us_bank_account']
        # ACH inactive -> card only (so the PI never errors on on_behalf_of)
        with patch('stripe.Account.retrieve',
                   return_value={'capabilities': {'us_bank_account_ach_payments': 'inactive'}}):
            with patch.object(stripe_service, '_configure'):
                assert stripe_service.connect_payment_method_types(u) == ['card']


# ---------------------------------------------------------------------------
# Self-healing of stale Stripe IDs (e.g. test-mode ids after a live-key switch)
# ---------------------------------------------------------------------------

def test_get_or_create_customer_recreates_stale_id(app, make_user):
    import stripe as _stripe
    from app import stripe_service
    with app.app_context():
        u = make_user(username='cust_heal', email='cust_heal@example.com')
        u.stripe_customer_id = 'cus_stale_test'
        with patch.object(stripe_service, '_configure'), \
             patch('stripe.Customer.retrieve',
                   side_effect=_stripe.error.InvalidRequestError('No such customer', 'id')), \
             patch('stripe.Customer.create', return_value=MagicMock(id='cus_new')) as create:
            cid = stripe_service.get_or_create_customer(u)
        assert cid == 'cus_new'
        assert u.stripe_customer_id == 'cus_new'
        create.assert_called_once()


def test_get_or_create_customer_keeps_valid_id(app, make_user):
    from app import stripe_service
    with app.app_context():
        u = make_user(username='cust_ok', email='cust_ok@example.com')
        u.stripe_customer_id = 'cus_valid'
        with patch.object(stripe_service, '_configure'), \
             patch('stripe.Customer.retrieve', return_value=MagicMock(deleted=False)), \
             patch('stripe.Customer.create') as create:
            assert stripe_service.get_or_create_customer(u) == 'cus_valid'
        create.assert_not_called()


def test_ensure_connect_account_recreates_stale_id(app, make_user):
    import stripe as _stripe
    from app import stripe_service
    with app.app_context():
        u = make_user(username='conn_heal', email='conn_heal@example.com')
        u.stripe_connect_account_id = 'acct_stale_test'
        u.stripe_onboarding_complete = True
        with patch.object(stripe_service, '_configure'), \
             patch('stripe.Account.retrieve',
                   side_effect=_stripe.error.InvalidRequestError('No such account', 'id')), \
             patch('stripe.Account.create', return_value=MagicMock(id='acct_new')) as create:
            aid = stripe_service.ensure_connect_account(u)
        assert aid == 'acct_new'
        assert u.stripe_connect_account_id == 'acct_new'
        assert u.stripe_onboarding_complete is False
        create.assert_called_once()


def test_ensure_connect_account_recreates_on_permission_error(app, make_user):
    """A test/foreign account id under live keys raises PermissionError on
    retrieve (not InvalidRequestError) — it must still be recreated, not kept."""
    import stripe as _stripe
    from app import stripe_service
    with app.app_context():
        u = make_user(username='conn_perm', email='conn_perm@example.com')
        u.stripe_connect_account_id = 'acct_test_foreign'
        u.stripe_onboarding_complete = True
        with patch.object(stripe_service, '_configure'), \
             patch('stripe.Account.retrieve',
                   side_effect=_stripe.error.PermissionError(
                       'The account is not connected to this platform')), \
             patch('stripe.Account.create', return_value=MagicMock(id='acct_live')):
            aid = stripe_service.ensure_connect_account(u)
        assert aid == 'acct_live'
        assert u.stripe_connect_account_id == 'acct_live'
        assert u.stripe_onboarding_complete is False


def test_create_connect_account_link_retries_after_rejected_account(app, make_user):
    """If AccountLink.create rejects a stale account (retrieve returned it as
    'valid'), the link path must recreate the account and retry once."""
    import stripe as _stripe
    from app import stripe_service
    with app.app_context():
        u = make_user(username='link_heal', email='link_heal@example.com')
        u.stripe_connect_account_id = 'acct_zombie'
        u.stripe_onboarding_complete = True

        # retrieve() keeps returning the stored id as "live" (the gap the retry
        # closes); AccountLink rejects it once, then succeeds on the fresh id.
        link_results = [
            _stripe.error.InvalidRequestError(
                'account not connected to your platform', 'account'),
            MagicMock(url='https://connect.stripe.com/setup/live'),
        ]
        with patch.object(stripe_service, '_configure'), \
             patch('stripe.Account.retrieve',
                   return_value=MagicMock(deleted=False)), \
             patch('stripe.Account.create', return_value=MagicMock(id='acct_fresh')), \
             patch('stripe.AccountLink.create', side_effect=link_results) as link:
            url = stripe_service.create_connect_account_link(u, return_path='/x')
        assert url == 'https://connect.stripe.com/setup/live'
        assert link.call_count == 2
        assert u.stripe_connect_account_id == 'acct_fresh'
