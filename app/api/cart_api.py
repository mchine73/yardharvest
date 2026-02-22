"""Cart & Orders REST API endpoints."""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import CartItem, Listing, Order, OrderItem, User
from app.pricing import get_pricing_config, calculate_order_fees
from app.email_service import (
    send_order_confirmation, send_new_order_notification,
    send_order_status_update,
)
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
@login_required
def view_cart():
    items = CartItem.query.filter_by(buyer_id=current_user.id).all()
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
        },
    })


@cart_api.route('/add/<int:listing_id>', methods=['POST'])
@login_required
def add_to_cart(listing_id):
    listing = Listing.query.get_or_404(listing_id)
    if listing.seller_id == current_user.id:
        return jsonify({'error': "You can't buy your own produce!"}), 400

    data = request.get_json() or {}
    quantity = max(1, min(data.get('quantity', 1), listing.quantity_available))

    existing = CartItem.query.filter_by(buyer_id=current_user.id, listing_id=listing_id).first()
    if existing:
        existing.quantity = min(existing.quantity + quantity, listing.quantity_available)
    else:
        item = CartItem(buyer_id=current_user.id, listing_id=listing_id, quantity=quantity)
        db.session.add(item)

    db.session.commit()
    count = CartItem.query.filter_by(buyer_id=current_user.id).count()
    return jsonify({'message': f'Added {listing.title} to cart!', 'cart_count': count})


@cart_api.route('/update/<int:item_id>', methods=['PUT'])
@login_required
def update_cart(item_id):
    item = CartItem.query.get_or_404(item_id)
    if item.buyer_id != current_user.id:
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
@login_required
def remove_from_cart(item_id):
    item = CartItem.query.get_or_404(item_id)
    if item.buyer_id != current_user.id:
        return jsonify({'error': 'Not authorized'}), 403
    db.session.delete(item)
    db.session.commit()
    return jsonify({'message': 'Item removed'})


@cart_api.route('/checkout', methods=['POST'])
@login_required
def checkout():
    items = CartItem.query.filter_by(buyer_id=current_user.id).all()
    if not items:
        return jsonify({'error': 'Cart is empty'}), 400

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
            buyer_lat=current_user.latitude,
            buyer_lon=current_user.longitude,
            seller_lat=seller_user.latitude if seller_user else None,
            seller_lon=seller_user.longitude if seller_user else None,
        )

        order = Order(
            buyer_id=current_user.id,
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

    # Send email notifications for each order created
    for order in orders_created:
        try:
            send_order_confirmation(order, current_user.email)
        except Exception:
            pass  # logged inside send_email
        try:
            seller = User.query.get(order.seller_id)
            if seller:
                send_new_order_notification(order, seller.email)
        except Exception:
            pass

    return jsonify({
        'message': 'Orders placed!',
        'orders': [order_to_dict(o) for o in orders_created],
    }), 201


@cart_api.route('/count', methods=['GET'])
@login_required
def cart_count():
    count = CartItem.query.filter_by(buyer_id=current_user.id).count()
    return jsonify({'count': count})


# ---- Orders ----
orders_api = Blueprint('orders_api', __name__, url_prefix='/api/orders')


@orders_api.route('/mine', methods=['GET'])
@login_required
def my_orders():
    orders = Order.query.filter_by(buyer_id=current_user.id).order_by(Order.created_at.desc()).all()
    return jsonify([order_to_dict(o) for o in orders])


@orders_api.route('/selling', methods=['GET'])
@login_required
def seller_orders():
    if not current_user.can_sell():
        return jsonify({'error': 'Seller account required'}), 403
    orders = Order.query.filter_by(seller_id=current_user.id).order_by(Order.created_at.desc()).all()
    return jsonify([order_to_dict(o) for o in orders])


@orders_api.route('/<int:order_id>', methods=['GET'])
@login_required
def order_detail(order_id):
    order = Order.query.get_or_404(order_id)
    if order.buyer_id != current_user.id and order.seller_id != current_user.id:
        return jsonify({'error': 'Not authorized'}), 403
    return jsonify(order_to_dict(order))


@orders_api.route('/<int:order_id>/accept', methods=['POST'])
@login_required
def accept_order(order_id):
    order = Order.query.get_or_404(order_id)
    if order.seller_id != current_user.id:
        return jsonify({'error': 'Not authorized'}), 403
    order.status = 'accepted'
    db.session.commit()

    try:
        send_order_status_update(order, order.buyer.email, 'accepted')
    except Exception:
        pass

    return jsonify(order_to_dict(order))


@orders_api.route('/<int:order_id>/complete', methods=['POST'])
@login_required
def complete_order(order_id):
    order = Order.query.get_or_404(order_id)
    if order.seller_id != current_user.id:
        return jsonify({'error': 'Not authorized'}), 403
    order.status = 'completed'
    db.session.commit()

    try:
        send_order_status_update(order, order.buyer.email, 'completed')
    except Exception:
        pass

    return jsonify(order_to_dict(order))


@orders_api.route('/<int:order_id>/cancel', methods=['POST'])
@login_required
def cancel_order(order_id):
    order = Order.query.get_or_404(order_id)
    if order.buyer_id != current_user.id and order.seller_id != current_user.id:
        return jsonify({'error': 'Not authorized'}), 403
    for oi in order.items:
        oi.listing.quantity_available += oi.quantity
    order.status = 'cancelled'
    db.session.commit()

    try:
        send_order_status_update(order, order.buyer.email, 'cancelled')
    except Exception:
        pass

    return jsonify(order_to_dict(order))
