"""Regression tests for the whole-codebase review corrections that introduce
new behavior: the Origin-check Referer fallback, the cart quantity coercion,
and the subscription refund actually issuing a Stripe refund."""
from unittest.mock import patch

from app import db as _db


# ---------------------------------------------------------------------------
# Origin check now falls back to the Referer's origin
# ---------------------------------------------------------------------------
def test_origin_check_uses_referer_when_origin_absent(client):
    """A state-changing API POST with no Origin but a foreign Referer must be
    blocked (previously a missing Origin always passed)."""
    resp = client.post('/api/auth/login',
                       json={'email': 'x@example.com', 'password': 'whatever'},
                       headers={'Referer': 'https://evil.example.com/login'})
    assert resp.status_code == 403
    assert resp.get_json()['error'] == 'Invalid origin'


def test_origin_check_allows_when_neither_header_present(client, make_user):
    """No Origin and no Referer → genuine same-origin request, allowed through."""
    make_user(username='refless', email='refless@example.com', password='GoodPass1')
    resp = client.post('/api/auth/login',
                       json={'email': 'refless@example.com', 'password': 'GoodPass1'})
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Cart quantity is coerced / validated
# ---------------------------------------------------------------------------
def test_update_cart_rejects_non_numeric_quantity(client, make_user):
    from app.models import Listing, CartItem
    buyer = make_user(username='cartbuyer', email='cartbuyer@example.com',
                      password='GoodPass1', role='both')
    seller = make_user(username='cartseller', email='cartseller@example.com',
                       role='both')
    listing = Listing(title='Tomatoes', seller_id=seller.id, price=3.0,
                      quantity_available=10, is_active=True)
    _db.session.add(listing)
    _db.session.flush()
    item = CartItem(buyer_id=buyer.id, listing_id=listing.id, quantity=1)
    _db.session.add(item)
    _db.session.commit()
    item_id = item.id

    from tests.conftest import login_via_api
    login_via_api(client, 'cartbuyer@example.com', 'GoodPass1')
    resp = client.put(f'/api/cart/update/{item_id}', json={'quantity': 'lots'})
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Subscription refund actually issues a Stripe refund + reports truthfully
# ---------------------------------------------------------------------------
def test_refund_subscription_issues_stripe_refund(client, make_user):
    from datetime import datetime, timezone, timedelta
    from app.models import CommunityGarden, GardenSubscription
    from app import stripe_service

    admin = make_user(username='refadmin', email='refadmin@example.com',
                      password='GoodPass1', role='both', is_admin=True)
    garden = CommunityGarden(name='Refund Garden', slug='refund-garden',
                             organizer_id=admin.id)
    _db.session.add(garden)
    _db.session.flush()
    now = datetime.now(timezone.utc)
    sub = GardenSubscription(
        garden_id=garden.id, status='active', billing_cycle='monthly',
        stripe_subscription_id='sub_live_1',
        current_period_start=now - timedelta(days=10),
        current_period_end=now + timedelta(days=20))
    _db.session.add(sub)
    _db.session.commit()
    sub_id = sub.id

    from tests.conftest import login_via_api
    login_via_api(client, 'refadmin@example.com', 'GoodPass1')

    with patch.object(stripe_service, 'is_configured', return_value=True), \
         patch.object(stripe_service, 'cancel_subscription_immediately'), \
         patch.object(stripe_service, 'refund_latest_subscription_invoice',
                      return_value='re_123') as do_refund:
        resp = client.post(f'/api/admin/refunds/subscription/{sub_id}', json={})

    assert resp.status_code == 200
    do_refund.assert_called_once()
    body = resp.get_json()
    assert 'refunded' in body['message'].lower()
    assert body['refund']['stripe_refund_id'] == 're_123'
