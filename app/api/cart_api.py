"""Cart & Orders REST API endpoints."""
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.api.token_auth import token_or_session, get_current_user
from app import db, limiter
from app.models import CartItem, Listing, Order, OrderItem, User
from app.pricing import get_pricing_config, calculate_order_fees
from app.email_service import (
    send_order_confirmation, send_new_order_notification,
    send_order_status_update,
)
from app.sms_service import send_order_sms, send_status_sms
from collections import defaultdict
from sqlalchemy import func as sqlfunc

cart_api = Blueprint('cart_api', __name__, url_prefix='/api/cart')


def cart_item_to_dict(item):
    return {
        'id': item.id,
        'listing_id': item.listing_id,
        'quantity': item.quantity,
        'listing': {
            'id': item.listing.id,
            'title': item.listing.title,
            'price': item.listing.price,
            'effective_price': item.listing.effective_price,
            'unit': item.listing.unit,
            'image_filename': item.listing.image_filename,
            'image_url': item.listing.image_url,
            'quantity_available': item.listing.quantity_available,
            'seller_id': item.listing.seller_id,
            'seller_name': item.listing.seller.display_name or item.listing.seller.username,
            'delivery_available': item.listing.delivery_available,
        },
        'subtotal': round(item.listing.effective_price * item.quantity, 2),
    }


def order_to_dict(order):
    return {
        'id': order.id,
        'buyer_id': order.buyer_id,
        'seller_id': order.seller_id,
        'buyer_name': order.buyer.display_name or order.buyer.username,
        'seller_name': order.seller_user.display_name or order.seller_user.username,
        'total_price': order.total_price,
        'subtotal': order.subtotal or order.total_price,
        'delivery_fee': order.delivery_fee or 0,
        'platform_commission': order.platform_commission or 0,
        'commission_rate': order.commission_rate or 0,
        'seller_earnings': order.seller_earnings or order.total_price,
        'status': order.status,
        'fulfillment_method': order.fulfillment_method,
        'notes': order.notes,
        'has_review': order.review is not None,
        'delivery_provider': getattr(order, 'delivery_provider', 'self') or 'self',
        'doordash_tracking_url': getattr(order, 'doordash_tracking_url', None),
        'created_at': order.created_at.isoformat() if order.created_at else None,
        'updated_at': order.updated_at.isoformat() if order.updated_at else None,
        'items': [{
            'id': oi.id,
            'listing_id': oi.listing_id,
            'listing_title': oi.listing.title if oi.listing else 'Removed',
            'listing_image': oi.listing.image_filename if oi.listing else None,
            'listing_image_url': oi.listing.image_url if oi.listing else None,
            'quantity': oi.quantity,
            'unit_price': oi.unit_price,
            'subtotal': round(oi.unit_price * oi.quantity, 2),
        } for oi in order.items],
    }


@cart_api.route('', methods=['GET'])
@token_or_session
def view_cart():
    items = CartItem.query.filter_by(buyer_id=get_current_user().id).all()
    grouped = defaultdict(list)
    for item in items:
        seller = item.listing.seller
        grouped[seller.id].append(item)

    result = []
    grand_total = 0
    for seller_id, seller_items in grouped.items():
        seller = seller_items[0].listing.seller
        seller_total = sum(i.listing.effective_price * i.quantity for i in seller_items)
        grand_total += seller_total
        result.append({
            'seller_id': seller.id,
            'seller_name': seller.display_name or seller.username,
            'items': [cart_item_to_dict(i) for i in seller_items],
            'subtotal': round(seller_total, 2),
        })

    config = get_pricing_config()
    return jsonify({
        'groups': result,
        'grand_total': round(grand_total, 2),
        'item_count': sum(len(g['items']) for g in result),
        'fee_info': {
            'commission_enabled': bool(config.commission_enabled),
            'platform_commission_pct': config.platform_commission_pct or 0,
            'delivery_fees_enabled': bool(config.delivery_fees_enabled),
            'delivery_fee_flat': config.delivery_fee_flat or 0,
            'per_mile_enabled': bool(config.per_mile_enabled),
            'delivery_fee_per_mile': config.delivery_fee_per_mile or 0,
            'free_delivery_enabled': bool(config.free_delivery_enabled),
            'delivery_fee_free_threshold': config.delivery_fee_free_threshold or 0,
            'doordash_enabled': bool(getattr(config, 'doordash_enabled', False)),
        },
    })


@cart_api.route('/add/<int:listing_id>', methods=['POST'])
@token_or_session
def add_to_cart(listing_id):
    listing = Listing.query.get_or_404(listing_id)
    if listing.seller_id == get_current_user().id:
        return jsonify({'error': "You can't buy your own produce!"}), 400
    if not listing.is_active:
        return jsonify({'error': 'This listing is no longer available'}), 400
    if listing.quantity_available <= 0:
        return jsonify({'error': 'This item is out of stock'}), 400

    data = request.get_json() or {}
    quantity = max(1, min(data.get('quantity', 1), listing.quantity_available))

    existing = CartItem.query.filter_by(buyer_id=get_current_user().id, listing_id=listing_id).first()
    if existing:
        existing.quantity = min(existing.quantity + quantity, listing.quantity_available)
    else:
        item = CartItem(buyer_id=get_current_user().id, listing_id=listing_id, quantity=quantity)
        db.session.add(item)

    db.session.commit()
    count = CartItem.query.filter_by(buyer_id=get_current_user().id).count()
    return jsonify({'message': f'Added {listing.title} to cart!', 'cart_count': count})


@cart_api.route('/update/<int:item_id>', methods=['PUT'])
@token_or_session
def update_cart(item_id):
    item = CartItem.query.get_or_404(item_id)
    if item.buyer_id != get_current_user().id:
        return jsonify({'error': 'Not authorized'}), 403

    data = request.get_json() or {}
    quantity = data.get('quantity', 1)
    if quantity <= 0:
        db.session.delete(item)
    else:
        item.quantity = min(quantity, item.listing.quantity_available)
    db.session.commit()
    return jsonify({'message': 'Cart updated'})


@cart_api.route('/remove/<int:item_id>', methods=['DELETE'])
@token_or_session
def remove_from_cart(item_id):
    item = CartItem.query.get_or_404(item_id)
    if item.buyer_id != get_current_user().id:
        return jsonify({'error': 'Not authorized'}), 403
    db.session.delete(item)
    db.session.commit()
    return jsonify({'message': 'Item removed'})


@cart_api.route('/checkout', methods=['POST'])
@limiter.limit("5 per minute")
@token_or_session
def checkout():
    items = CartItem.query.filter_by(buyer_id=get_current_user().id).all()
    if not items:
        return jsonify({'error': 'Cart is empty'}), 400

    # Validate all listings are still active and in stock
    for item in items:
        if not item.listing.is_active:
            return jsonify({'error': f'"{item.listing.title}" is no longer available. Please remove it from your cart.'}), 400
        if item.listing.quantity_available < item.quantity:
            return jsonify({'error': f'"{item.listing.title}" only has {item.listing.quantity_available} available.'}), 400

    data = request.get_json() or {}
    notes = data.get('notes', '')

    grouped = defaultdict(list)
    for item in items:
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
            # M11: Atomic inventory decrement — prevents race conditions
            Listing.query.filter_by(id=item.listing_id).update(
                {Listing.quantity_available: sqlfunc.greatest(
                    0, Listing.quantity_available - item.quantity
                )},
                synchronize_session='fetch'
            )

        for item in seller_items:
            db.session.delete(item)

        orders_created.append(order)

    db.session.commit()

    # DoorDash delivery creation for delivery orders (if enabled)
    pricing_cfg = get_pricing_config()
    if getattr(pricing_cfg, 'doordash_enabled', False):
        from app.doordash_service import create_delivery
        for order in orders_created:
            if order.fulfillment_method == 'delivery':
                try:
                    seller_u = User.query.get(order.seller_id)
                    pickup_addr = f"{seller_u.address}, {seller_u.city}, {seller_u.state} {seller_u.zip_code}" if seller_u else ''
                    dropoff_addr = f"{get_current_user().address}, {get_current_user().city}, {get_current_user().state} {get_current_user().zip_code}"
                    dd_result = create_delivery(order, pickup_addr, dropoff_addr)
                    order.doordash_delivery_id = dd_result.get('delivery_id')
                    order.doordash_tracking_url = dd_result.get('tracking_url')
                    order.delivery_provider = 'doordash'
                except Exception:
                    pass  # Graceful fallback — seller self-delivers
        db.session.commit()

    # Send email notifications for each order created
    for order in orders_created:
        try:
            send_order_confirmation(order, get_current_user().email)
        except Exception:
            pass  # logged inside send_email
        try:
            seller = User.query.get(order.seller_id)
            if seller:
                send_new_order_notification(order, seller.email)
        except Exception:
            pass
        # SMS notification for buyer (if opted in)
        try:
            if get_current_user().sms_opt_in and get_current_user().phone_number:
                send_order_sms(order, get_current_user().phone_number)
        except Exception:
            pass

    return jsonify({
        'message': 'Orders placed!',
        'orders': [order_to_dict(o) for o in orders_created],
    }), 201


@cart_api.route('/count', methods=['GET'])
@token_or_session
def cart_count():
    count = CartItem.query.filter_by(buyer_id=get_current_user().id).count()
    return jsonify({'count': count})


# ---- Orders ----
orders_api = Blueprint('orders_api', __name__, url_prefix='/api/orders')


@orders_api.route('/mine', methods=['GET'])
@token_or_session
def my_orders():
    orders = Order.query.filter_by(buyer_id=get_current_user().id).order_by(Order.created_at.desc()).all()
    return jsonify([order_to_dict(o) for o in orders])


@orders_api.route('/selling', methods=['GET'])
@token_or_session
def seller_orders():
    if not get_current_user().can_sell():
        return jsonify({'error': 'Seller account required'}), 403
    orders = Order.query.filter_by(seller_id=get_current_user().id).order_by(Order.created_at.desc()).all()
    return jsonify([order_to_dict(o) for o in orders])


@orders_api.route('/<int:order_id>', methods=['GET'])
@token_or_session
def order_detail(order_id):
    order = Order.query.get_or_404(order_id)
    if order.buyer_id != get_current_user().id and order.seller_id != get_current_user().id:
        return jsonify({'error': 'Not authorized'}), 403
    return jsonify(order_to_dict(order))


@orders_api.route('/<int:order_id>/accept', methods=['POST'])
@token_or_session
def accept_order(order_id):
    order = Order.query.get_or_404(order_id)
    if order.seller_id != get_current_user().id:
        return jsonify({'error': 'Not authorized'}), 403
    if order.status != 'pending':
        return jsonify({'error': f'Cannot accept an order that is {order.status}'}), 400
    order.status = 'accepted'
    db.session.commit()

    try:
        send_order_status_update(order, order.buyer.email, 'accepted')
    except Exception:
        pass
    try:
        if order.buyer.sms_opt_in and order.buyer.phone_number:
            send_status_sms(order, order.buyer.phone_number, 'accepted')
    except Exception:
        pass

    return jsonify(order_to_dict(order))


@orders_api.route('/<int:order_id>/complete', methods=['POST'])
@token_or_session
def complete_order(order_id):
    order = Order.query.get_or_404(order_id)
    if order.seller_id != get_current_user().id:
        return jsonify({'error': 'Not authorized'}), 403
    if order.status != 'accepted':
        return jsonify({'error': f'Cannot complete an order that is {order.status}. Accept it first.'}), 400
    order.status = 'completed'
    db.session.commit()

    try:
        send_order_status_update(order, order.buyer.email, 'completed')
    except Exception:
        pass
    try:
        if order.buyer.sms_opt_in and order.buyer.phone_number:
            send_status_sms(order, order.buyer.phone_number, 'completed')
    except Exception:
        pass

    return jsonify(order_to_dict(order))


@orders_api.route('/<int:order_id>/cancel', methods=['POST'])
@token_or_session
def cancel_order(order_id):
    order = Order.query.get_or_404(order_id)
    if order.buyer_id != get_current_user().id and order.seller_id != get_current_user().id:
        if not get_current_user().is_admin:
            return jsonify({'error': 'Not authorized'}), 403
    if order.status in ('completed', 'cancelled'):
        return jsonify({'error': f'Cannot cancel an order that is already {order.status}'}), 400
    for oi in order.items:
        oi.listing.quantity_available += oi.quantity
    order.status = 'cancelled'

    # Auto-refund if payment was completed via Stripe
    if order.stripe_payment_intent_id and order.payment_status == 'succeeded':
        from app import stripe_service
        from app.models import Refund, SellerPayout
        import logging
        _log = logging.getLogger(__name__)
        refund_status = 'completed'
        stripe_refund_id = None
        stripe_reversal_id = None

        if stripe_service.is_configured():
            try:
                sr = stripe_service.create_refund(order.stripe_payment_intent_id)
                stripe_refund_id = sr.id
            except Exception:
                _log.exception('Auto-refund failed for order %d', order.id)
                refund_status = 'failed'

            if refund_status == 'completed':
                payout = SellerPayout.query.filter(
                    SellerPayout.seller_id == order.seller_id,
                    SellerPayout.stripe_transfer_id.isnot(None)
                ).first()
                if payout and payout.stripe_transfer_id:
                    try:
                        rev = stripe_service.reverse_transfer(payout.stripe_transfer_id,
                                                              int(round(order.seller_earnings * 100)))
                        stripe_reversal_id = rev.id
                    except Exception:
                        _log.exception('Auto transfer reversal failed for order %d', order.id)

        refund = Refund(
            order_id=order.id,
            refund_type='marketplace',
            amount=order.total_price,
            reason='Order cancelled',
            status=refund_status,
            stripe_refund_id=stripe_refund_id,
            stripe_reversal_id=stripe_reversal_id,
            initiated_by_id=get_current_user().id,
            completed_at=datetime.now(timezone.utc) if refund_status == 'completed' else None,
        )
        db.session.add(refund)
        if refund_status == 'completed':
            order.refund_status = 'full'
            order.refund_amount = order.total_price

    db.session.commit()

    try:
        send_order_status_update(order, order.buyer.email, 'cancelled')
    except Exception:
        pass
    try:
        if order.refund_status == 'full':
            from app.email_service import send_refund_confirmation_email
            send_refund_confirmation_email(order, order.buyer.email,
                                           order.refund_amount, is_full=True)
    except Exception:
        pass
    try:
        if order.buyer.sms_opt_in and order.buyer.phone_number:
            send_status_sms(order, order.buyer.phone_number, 'cancelled')
    except Exception:
        pass

    return jsonify(order_to_dict(order))
