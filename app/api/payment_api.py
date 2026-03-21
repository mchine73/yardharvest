"""Gr4vy Payment API endpoints."""
import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.api.token_auth import token_or_session, get_current_user
from app import db, limiter
from app.models import CartItem, Listing, Order, OrderItem, User
from app.pricing import calculate_order_fees
from app.email_service import (
    send_order_confirmation, send_new_order_notification,
)
from collections import defaultdict
from sqlalchemy import func as sqlfunc
import os

log = logging.getLogger(__name__)

payment_api = Blueprint('payment_api', __name__, url_prefix='/api/payments')


def _get_gr4vy_private_key():
    """Load Gr4vy private key from file path or inline env var.

    Returns (private_key_str, error_response) — one will be None.
    """
    gr4vy_key_path = os.environ.get('GR4VY_PRIVATE_KEY_PATH', '')
    gr4vy_key_raw = os.environ.get('GR4VY_PRIVATE_KEY', '')

    if gr4vy_key_path:
        try:
            with open(gr4vy_key_path) as f:
                return f.read(), None
        except FileNotFoundError:
            log.error('GR4VY_PRIVATE_KEY_PATH points to non-existent file: %s', gr4vy_key_path)
            return None, (jsonify({'error': 'Payment configuration error. Please contact support.'}), 500)
    elif gr4vy_key_raw:
        return gr4vy_key_raw, None
    else:
        return None, None  # No key configured — dev mode


@payment_api.route('/create-session', methods=['POST'])
@token_or_session
@limiter.limit("5 per minute")
def create_checkout_session():
    """Create a Gr4vy checkout session and return an embed token."""
    # Get cart items for current user
    cart_items = CartItem.query.filter_by(buyer_id=get_current_user().id).all()
    if not cart_items:
        return jsonify({'error': 'Cart is empty'}), 400

    # Calculate subtotal from effective prices
    total_cents = 0
    gr4vy_cart_items = []
    for ci in cart_items:
        listing = Listing.query.get(ci.listing_id)
        if listing:
            price = listing.effective_price
            item_total = int(price * ci.quantity * 100)  # convert to cents
            total_cents += item_total
            gr4vy_cart_items.append({
                'name': listing.title,
                'quantity': ci.quantity,
                'unit_amount': int(price * 100),
            })

    # Add delivery fees for each seller group
    data = request.get_json() or {}
    grouped = defaultdict(list)
    for ci in cart_items:
        grouped[ci.listing.seller_id].append(ci)

    total_delivery_cents = 0
    for seller_id, seller_items in grouped.items():
        seller_subtotal = sum(i.listing.effective_price * i.quantity for i in seller_items)
        fulfillment = data.get(f'fulfillment_{seller_id}', 'pickup')
        seller_user = User.query.get(seller_id)
        fees = calculate_order_fees(
            subtotal=round(seller_subtotal, 2),
            fulfillment_method=fulfillment,
            buyer_lat=get_current_user().latitude,
            buyer_lon=get_current_user().longitude,
            seller_lat=seller_user.latitude if seller_user else None,
            seller_lon=seller_user.longitude if seller_user else None,
        )
        if fees['delivery_fee'] > 0:
            total_delivery_cents += int(fees['delivery_fee'] * 100)

    total_cents += total_delivery_cents
    if total_delivery_cents > 0:
        gr4vy_cart_items.append({
            'name': 'Delivery Fee',
            'quantity': 1,
            'unit_amount': total_delivery_cents,
        })

    # Check if Gr4vy is configured via environment variables
    gr4vy_id = os.environ.get('GR4VY_ID', '')
    private_key, key_error = _get_gr4vy_private_key()

    if key_error:
        return key_error

    if not gr4vy_id or not private_key:
        # Development mode - return a mock token for testing
        return jsonify({
            'token': 'dev-mock-token',
            'amount': total_cents,
            'currency': 'USD',
            'gr4vy_id': gr4vy_id or 'sandbox',
            'environment': 'sandbox',
            'cart_items': gr4vy_cart_items,
            'dev_mode': True,
        })

    gr4vy_env = os.environ.get('GR4VY_ENVIRONMENT', 'sandbox')

    try:
        from gr4vy import Gr4vy, auth, models

        client = Gr4vy(
            id=gr4vy_id,
            server=gr4vy_env,
            bearer_auth=auth.with_token(private_key),
        )

        # Create checkout session
        session = client.checkout_sessions.create(
            checkout_session_create=models.CheckoutSessionCreate(
                cart_items=[
                    models.CartItem(
                        name=item['name'],
                        quantity=item['quantity'],
                        unit_amount=item['unit_amount'],
                    ) for item in gr4vy_cart_items
                ],
                metadata={
                    'user_id': str(get_current_user().id),
                    'user_email': get_current_user().email,
                },
            )
        )

        # Generate embed token
        token = auth.get_embed_token(
            private_key,
            embed_params={
                'amount': total_cents,
                'currency': 'USD',
                'buyer_external_identifier': str(get_current_user().id),
            },
            checkout_session_id=session.id,
        )

        return jsonify({
            'token': token,
            'amount': total_cents,
            'currency': 'USD',
            'gr4vy_id': gr4vy_id,
            'environment': gr4vy_env,
            'cart_items': gr4vy_cart_items,
            'checkout_session_id': session.id,
            'dev_mode': False,
        })
    except ImportError:
        log.error('gr4vy Python SDK not installed')
        return jsonify({'error': 'Payment system not configured.'}), 503
    except Exception:
        log.exception('Gr4vy checkout session creation failed')
        return jsonify({'error': 'Payment service temporarily unavailable. Please try again.'}), 500


@payment_api.route('/confirm', methods=['POST'])
@token_or_session
def confirm_payment():
    """After Gr4vy payment completes, create orders with payment reference."""
    data = request.json or {}
    transaction_id = data.get('transaction_id', '')
    transaction_status = data.get('transaction_status', '')
    notes = data.get('notes', '')

    # Input validation
    if not transaction_id:
        return jsonify({'error': 'Transaction ID is required'}), 400
    if len(transaction_id) > 255:
        return jsonify({'error': 'Invalid transaction ID'}), 400
    if len(notes) > 2000:
        return jsonify({'error': 'Notes must be under 2000 characters'}), 400

    # Verify transaction with Gr4vy — REQUIRE payment provider in production
    gr4vy_id = os.environ.get('GR4VY_ID', '')
    private_key, _ = _get_gr4vy_private_key()
    is_production = bool(os.environ.get('DATABASE_URL'))

    if not gr4vy_id or not private_key:
        if is_production:
            log.error('Payment provider not configured in production — rejecting order')
            return jsonify({'error': 'Payment system not configured. Please contact support.'}), 503
        else:
            log.warning('DEV MODE: Skipping payment verification (Gr4vy not configured)')
    else:
        try:
            from gr4vy import Gr4vy, auth
            gr4vy_env = os.environ.get('GR4VY_ENVIRONMENT', 'sandbox')
            client = Gr4vy(
                id=gr4vy_id,
                server=gr4vy_env,
                bearer_auth=auth.with_token(private_key),
            )
            txn = client.transactions.get(transaction_id=transaction_id)
            if txn.status not in ('authorized', 'captured', 'buyer_approval_succeeded'):
                return jsonify({'error': 'Payment has not been completed'}), 400
        except Exception:
            log.exception('Gr4vy transaction verification failed for %s', transaction_id)
            return jsonify({'error': 'Unable to verify payment. Please contact support.'}), 500

    # Get cart items
    cart_items = CartItem.query.filter_by(buyer_id=get_current_user().id).all()
    if not cart_items:
        return jsonify({'error': 'Cart is empty'}), 400

    # Group by seller (same pattern as existing checkout in cart_api.py)
    grouped = defaultdict(list)
    for item in cart_items:
        grouped[item.listing.seller_id].append(item)

    orders_created = []
    for seller_id, seller_items in grouped.items():
        item_subtotal = sum(i.listing.effective_price * i.quantity for i in seller_items)
        fulfillment = data.get(f'fulfillment_{seller_id}', 'pickup')

        # Calculate fees using shared calculator
        seller_user = User.query.get(seller_id)
        fees = calculate_order_fees(
            subtotal=round(item_subtotal, 2),
            fulfillment_method=fulfillment,
            buyer_lat=get_current_user().latitude,
            buyer_lon=get_current_user().longitude,
            seller_lat=seller_user.latitude if seller_user else None,
            seller_lon=seller_user.longitude if seller_user else None,
        )

        order = Order(
            buyer_id=get_current_user().id,
            seller_id=seller_id,
            subtotal=round(item_subtotal, 2),
            delivery_fee=fees['delivery_fee'],
            platform_commission=fees['commission'],
            commission_rate=fees['commission_rate'],
            seller_earnings=fees['seller_earnings'],
            total_price=fees['total'],
            status='pending',
            fulfillment_method=fulfillment,
            notes=notes,
            payment_reference=transaction_id,
            payment_status=transaction_status or 'completed',
        )
        db.session.add(order)
        db.session.flush()

        for item in seller_items:
            oi = OrderItem(
                order_id=order.id,
                listing_id=item.listing_id,
                quantity=item.quantity,
                unit_price=item.listing.effective_price,
            )
            db.session.add(oi)
            # Atomic inventory decrement — prevents race conditions
            Listing.query.filter_by(id=item.listing_id).update(
                {Listing.quantity_available: sqlfunc.greatest(
                    0, Listing.quantity_available - item.quantity
                )},
                synchronize_session='fetch'
            )

        # Delete cart items individually (matches existing pattern)
        for item in seller_items:
            db.session.delete(item)

        orders_created.append(order)

    db.session.commit()

    # Send email notifications (same as existing checkout)
    for order in orders_created:
        try:
            send_order_confirmation(order, get_current_user().email)
        except Exception:
            pass
        try:
            seller = User.query.get(order.seller_id)
            if seller:
                send_new_order_notification(order, seller.email)
        except Exception:
            pass

    return jsonify({
        'message': 'Payment confirmed and orders created',
        'order_ids': [o.id for o in orders_created],
        'payment_reference': transaction_id,
    })
