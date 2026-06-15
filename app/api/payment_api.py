"""Stripe Payment API endpoints — marketplace checkout + seller Connect onboarding."""
import logging
from flask import Blueprint, request, jsonify
from app.api.token_auth import token_or_session, get_current_user
from app import db, limiter
from app.models import (CartItem, Listing, Order, OrderItem, User, SellerPayout,
                        PromoCode, PromoCodeUsage, PendingCheckout)
from app.pricing import calculate_order_fees
from app.email_service import send_order_confirmation, send_new_order_notification
from app import stripe_service
from collections import defaultdict
from sqlalchemy import func as sqlfunc
from datetime import datetime, timezone
import json
import os

log = logging.getLogger(__name__)

payment_api = Blueprint('payment_api', __name__, url_prefix='/api/payments')


# ==================== Stripe Connect (Seller Onboarding) ====================

@payment_api.route('/connect/onboard', methods=['POST'])
@token_or_session
def connect_onboard():
    """Create a Stripe Connect Standard account and return the onboarding URL."""
    user = get_current_user()
    if not user.can_sell():
        return jsonify({'error': 'Only growers can set up payouts'}), 403

    if not stripe_service.is_configured():
        return jsonify({'error': 'Payment system not configured'}), 503

    try:
        url = stripe_service.create_connect_account_link(user)
        return jsonify({'url': url, 'account_id': user.stripe_connect_account_id})
    except Exception as exc:
        log.exception('Failed to create Connect onboarding link')
        return jsonify({'error': 'Failed to set up payouts. Please try again.',
                        'detail': stripe_service.error_detail(exc)}), 500


@payment_api.route('/connect/account-session', methods=['POST'])
@token_or_session
@limiter.limit("10 per minute")
def connect_account_session():
    """Create an Account Session for in-app (embedded) Connect onboarding."""
    user = get_current_user()
    if not user.can_sell():
        return jsonify({'error': 'Only growers can set up payouts'}), 403

    if not stripe_service.is_configured():
        return jsonify({'error': 'Payment system not configured'}), 503

    try:
        client_secret = stripe_service.create_account_session(user)
        return jsonify({
            'client_secret': client_secret,
            'publishable_key': stripe_service.get_publishable_key(),
            'account_id': user.stripe_connect_account_id,
        })
    except Exception as exc:
        log.exception('Failed to create Connect account session')
        return jsonify({'error': 'Failed to set up payouts. Please try again.',
                        'detail': stripe_service.error_detail(exc)}), 500


@payment_api.route('/connect/status', methods=['GET'])
@token_or_session
def connect_status():
    """Check if the seller's Stripe Connect account is fully onboarded."""
    user = get_current_user()
    if not stripe_service.is_configured():
        return jsonify({'onboarded': False, 'configured': False})

    onboarded = stripe_service.check_connect_status(user)
    dashboard_url = None
    if onboarded:
        dashboard_url = stripe_service.create_login_link(user)

    return jsonify({
        'onboarded': onboarded,
        'configured': True,
        'account_id': user.stripe_connect_account_id,
        'dashboard_url': dashboard_url,
    })


# ==================== Marketplace Checkout ====================

@payment_api.route('/create-session', methods=['POST'])
@token_or_session
@limiter.limit("5 per minute")
def create_checkout_session():
    """Create a Stripe PaymentIntent for the cart and return a client secret."""
    user = get_current_user()
    cart_items = CartItem.query.filter_by(buyer_id=user.id).all()
    if not cart_items:
        return jsonify({'error': 'Cart is empty'}), 400

    # Calculate total from effective prices
    total_cents = 0
    for ci in cart_items:
        listing = Listing.query.get(ci.listing_id)
        if listing:
            total_cents += int(listing.effective_price * ci.quantity * 100)

    # Add delivery fees per seller group, and capture a basket snapshot (the
    # exact thing the buyer is paying for) so fulfillment is deterministic and
    # can be driven by the webhook later — independent of the live cart.
    data = request.get_json() or {}
    grouped = defaultdict(list)
    for ci in cart_items:
        grouped[ci.listing.seller_id].append(ci)

    snapshot_sellers = []
    for seller_id, seller_items in grouped.items():
        seller_subtotal = sum(i.listing.effective_price * i.quantity for i in seller_items)
        fulfillment = data.get(f'fulfillment_{seller_id}', 'pickup')
        seller_user = User.query.get(seller_id)
        fees = calculate_order_fees(
            subtotal=round(seller_subtotal, 2),
            fulfillment_method=fulfillment,
            buyer_lat=user.latitude, buyer_lon=user.longitude,
            seller_lat=seller_user.latitude if seller_user else None,
            seller_lon=seller_user.longitude if seller_user else None,
        )
        if fees['delivery_fee'] > 0:
            total_cents += int(fees['delivery_fee'] * 100)
        snapshot_sellers.append({
            'seller_id': seller_id,
            'fulfillment': fulfillment,
            'items': [{'listing_id': i.listing_id, 'quantity': i.quantity,
                       'unit_price': round(i.listing.effective_price, 2)}
                      for i in seller_items],
        })

    # Apply promo code if provided
    promo_code_str = data.get('promo_code', '')
    discount_cents = 0
    if promo_code_str:
        from app.api.promo_api import validate_promo_code, calculate_discount
        promo, promo_err = validate_promo_code(promo_code_str, 'marketplace')
        if promo and not promo_err:
            discount_cents = int(calculate_discount(promo, total_cents / 100) * 100)
            total_cents = max(0, total_cents - discount_cents)

    # Dev mode — no Stripe keys
    if not stripe_service.is_configured():
        return jsonify({
            'dev_mode': True,
            'amount': total_cents,
            'discount': discount_cents,
            'currency': 'USD',
        })

    try:
        customer_id = stripe_service.get_or_create_customer(user)
        pi = stripe_service.create_payment_intent(
            amount_cents=total_cents,
            customer_id=customer_id,
            metadata={
                'type': 'marketplace_order',
                'user_id': str(user.id),
            },
        )
        # Persist the basket snapshot keyed by the PaymentIntent so either the
        # client /confirm or the webhook can fulfill the exact same order.
        _save_checkout_snapshot(pi.id, user.id, snapshot_sellers, promo_code_str)
        return jsonify({
            'client_secret': pi.client_secret,
            'payment_intent_id': pi.id,
            'publishable_key': stripe_service.get_publishable_key(),
            'amount': total_cents,
            'currency': 'USD',
            'dev_mode': False,
        })
    except Exception:
        log.exception('Stripe PaymentIntent creation failed')
        return jsonify({'error': 'Payment service temporarily unavailable. Please try again.'}), 500


def _save_checkout_snapshot(payment_intent_id, buyer_id, sellers, promo_code):
    """Upsert the PendingCheckout snapshot for a PaymentIntent."""
    payload = json.dumps({'sellers': sellers, 'promo_code': promo_code or ''})
    pc = PendingCheckout.query.filter_by(payment_intent_id=payment_intent_id).first()
    if pc:
        pc.payload_json = payload
        pc.fulfilled = False
    else:
        db.session.add(PendingCheckout(payment_intent_id=payment_intent_id,
                                       buyer_id=buyer_id, payload_json=payload))
    db.session.commit()


@payment_api.route('/confirm', methods=['POST'])
@token_or_session
def confirm_payment():
    """After Stripe payment completes, verify and create orders."""
    user = get_current_user()
    data = request.json or {}
    payment_intent_id = data.get('payment_intent_id', '')
    notes = data.get('notes', '')

    if not payment_intent_id:
        return jsonify({'error': 'Payment intent ID is required'}), 400
    if len(payment_intent_id) > 255:
        return jsonify({'error': 'Invalid payment intent ID'}), 400
    if len(notes) > 2000:
        return jsonify({'error': 'Notes must be under 2000 characters'}), 400

    # Verify with Stripe
    is_production = bool(os.environ.get('DATABASE_URL'))

    if not stripe_service.is_configured():
        if is_production:
            log.error('Stripe not configured in production — rejecting order')
            return jsonify({'error': 'Payment system not configured. Please contact support.'}), 503
        else:
            log.warning('DEV MODE: Skipping payment verification (Stripe not configured)')
    else:
        try:
            pi = stripe_service.retrieve_payment_intent(payment_intent_id)
            if pi.status != 'succeeded':
                return jsonify({'error': 'Payment has not been completed'}), 400
        except Exception:
            log.exception('Stripe PaymentIntent verification failed for %s', payment_intent_id)
            return jsonify({'error': 'Unable to verify payment. Please contact support.'}), 500

    # Fulfill from the basket snapshot (preferred) or the live cart (dev mode).
    # Shared with the webhook + idempotent, so a charge always yields orders.
    fulfillment_map = {k[len('fulfillment_'):]: v for k, v in (data or {}).items()
                       if isinstance(k, str) and k.startswith('fulfillment_')}
    orders, created = fulfill_payment_intent(
        payment_intent_id, user.id, notes=notes,
        promo_code=data.get('promo_code', ''), fulfillment_map=fulfillment_map)
    if not orders:
        return jsonify({'error': 'Cart is empty'}), 400
    return jsonify({
        'message': 'Payment confirmed and orders created' if created else 'Payment already confirmed',
        'order_ids': [o.id for o in orders],
        'payment_reference': payment_intent_id,
    })


def fulfill_payment_intent(payment_intent_id, buyer_id, notes='',
                           promo_code='', fulfillment_map=None):
    """Create marketplace orders for a paid PaymentIntent. Idempotent.

    Called by both the client ``/confirm`` (instant path) and the Stripe
    webhook (guarantee path). Builds orders from the PendingCheckout snapshot
    when present (the exact basket the buyer was charged for), else from the
    buyer's live cart (dev mode / legacy). Decrements stock, clears the cart,
    and pays sellers (transfer when payout-ready, else a held 'pending' payout).

    Returns ``(orders, created_now)``.
    """
    # Idempotency: already produced orders for this PI -> return them.
    existing = Order.query.filter_by(
        buyer_id=buyer_id, stripe_payment_intent_id=payment_intent_id).all()
    if existing:
        return existing, False

    user = User.query.get(buyer_id)
    if not user:
        return [], False

    configured = stripe_service.is_configured()
    fulfillment_map = fulfillment_map or {}

    # Normalize seller groups from the snapshot (preferred) or the live cart.
    snapshot = PendingCheckout.query.filter_by(payment_intent_id=payment_intent_id).first()
    if snapshot:
        payload = json.loads(snapshot.payload_json)
        groups = payload.get('sellers', [])
        if not promo_code:
            promo_code = payload.get('promo_code', '')
    else:
        cart_items = CartItem.query.filter_by(buyer_id=buyer_id).all()
        if not cart_items:
            return [], False
        grouped = defaultdict(list)
        for ci in cart_items:
            grouped[ci.listing.seller_id].append(ci)
        groups = [{
            'seller_id': sid,
            'fulfillment': fulfillment_map.get(str(sid), 'pickup'),
            'items': [{'listing_id': i.listing_id, 'quantity': i.quantity,
                       'unit_price': round(i.listing.effective_price, 2)} for i in items],
        } for sid, items in grouped.items()]

    if not groups:
        return [], False

    orders_created = []
    for g in groups:
        seller_id = g['seller_id']
        fulfillment = g.get('fulfillment', 'pickup')
        items = g.get('items', [])
        item_subtotal = round(sum(it['unit_price'] * it['quantity'] for it in items), 2)
        seller_user = User.query.get(seller_id)
        fees = calculate_order_fees(
            subtotal=item_subtotal,
            fulfillment_method=fulfillment,
            buyer_lat=user.latitude, buyer_lon=user.longitude,
            seller_lat=seller_user.latitude if seller_user else None,
            seller_lon=seller_user.longitude if seller_user else None,
        )

        order = Order(
            buyer_id=buyer_id, seller_id=seller_id, subtotal=item_subtotal,
            delivery_fee=fees['delivery_fee'], platform_commission=fees['commission'],
            commission_rate=fees['commission_rate'], seller_earnings=fees['seller_earnings'],
            total_price=fees['total'], status='pending', fulfillment_method=fulfillment,
            notes=notes, payment_reference=payment_intent_id,
            stripe_payment_intent_id=payment_intent_id,
            payment_status='succeeded' if configured else 'completed',
        )
        db.session.add(order)
        db.session.flush()

        for it in items:
            db.session.add(OrderItem(
                order_id=order.id, listing_id=it['listing_id'],
                quantity=it['quantity'], unit_price=it['unit_price'],
            ))
            Listing.query.filter_by(id=it['listing_id']).update(
                {Listing.quantity_available: sqlfunc.greatest(
                    0, Listing.quantity_available - it['quantity'])},
                synchronize_session='fetch',
            )
            # Clear the matching cart item if still present.
            CartItem.query.filter_by(buyer_id=buyer_id, listing_id=it['listing_id']).delete()

        orders_created.append(order)

        # Pay the seller when payout-ready; else hold a 'pending' payout so the
        # amount owed is tracked, never silently kept by the platform.
        if configured:
            if seller_user and stripe_service.connect_account_ready(seller_user):
                try:
                    transfer = stripe_service.create_transfer(
                        amount_cents=int(fees['seller_earnings'] * 100),
                        destination_account_id=seller_user.stripe_connect_account_id,
                        transfer_group=payment_intent_id,
                    )
                    db.session.add(SellerPayout(
                        seller_id=seller_id, amount=fees['seller_earnings'],
                        status='completed', payout_reference=transfer.id,
                        stripe_transfer_id=transfer.id,
                        completed_at=datetime.now(timezone.utc),
                    ))
                except Exception:
                    log.exception('Stripe Transfer failed for seller %s', seller_id)
                    db.session.add(SellerPayout(
                        seller_id=seller_id, amount=fees['seller_earnings'],
                        status='pending', payout_reference=payment_intent_id))
            else:
                db.session.add(SellerPayout(
                    seller_id=seller_id, amount=fees['seller_earnings'],
                    status='pending', payout_reference=payment_intent_id))

    # Promo usage.
    if promo_code and orders_created:
        from app.api.promo_api import validate_promo_code, calculate_discount
        promo, _ = validate_promo_code(promo_code, 'marketplace')
        if promo:
            total_subtotal = sum(o.total_price for o in orders_created)
            discount = calculate_discount(promo, total_subtotal)
            for order in orders_created:
                order.discount_amount = round(discount * (order.total_price / total_subtotal), 2) if total_subtotal > 0 else 0
                order.promo_code_id = promo.id
            db.session.add(PromoCodeUsage(
                promo_code_id=promo.id, user_id=buyer_id,
                order_id=orders_created[0].id, discount_applied=discount))
            promo.current_uses = (promo.current_uses or 0) + 1

    if snapshot:
        snapshot.fulfilled = True
    db.session.commit()

    # Notifications (best-effort).
    for order in orders_created:
        try:
            send_order_confirmation(order, user.email)
        except Exception:
            pass
        try:
            seller = User.query.get(order.seller_id)
            if seller:
                send_new_order_notification(order, seller.email)
        except Exception:
            pass

    return orders_created, True
