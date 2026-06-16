from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import CartItem, Listing, Order, OrderItem
from collections import defaultdict

cart_bp = Blueprint('cart', __name__)


@cart_bp.route('/cart')
@login_required
def view_cart():
    items = CartItem.query.filter_by(buyer_id=current_user.id).all()
    grouped = defaultdict(list)
    for item in items:
        grouped[item.listing.seller].append(item)

    totals = {}
    for seller, seller_items in grouped.items():
        totals[seller.id] = sum(i.listing.effective_price * i.quantity for i in seller_items)

    grand_total = sum(totals.values())
    return render_template('cart/cart.html', grouped=grouped, totals=totals, grand_total=grand_total)


@cart_bp.route('/cart/add/<int:listing_id>', methods=['POST'])
@login_required
def add_to_cart(listing_id):
    listing = db.get_or_404(Listing, listing_id)

    if listing.seller_id == current_user.id:
        flash("You can't buy your own produce!", 'warning')
        return redirect(url_for('listings.detail', listing_id=listing_id))

    quantity = request.form.get('quantity', 1, type=int)
    quantity = max(1, min(quantity, listing.quantity_available))

    existing = CartItem.query.filter_by(buyer_id=current_user.id, listing_id=listing_id).first()
    if existing:
        existing.quantity = min(existing.quantity + quantity, listing.quantity_available)
    else:
        item = CartItem(buyer_id=current_user.id, listing_id=listing_id, quantity=quantity)
        db.session.add(item)

    db.session.commit()
    flash(f'Added {listing.title} to cart!', 'success')
    return redirect(url_for('listings.detail', listing_id=listing_id))


@cart_bp.route('/cart/update/<int:item_id>', methods=['POST'])
@login_required
def update_cart(item_id):
    item = db.get_or_404(CartItem, item_id)
    if item.buyer_id != current_user.id:
        flash('Not authorized.', 'danger')
        return redirect(url_for('cart.view_cart'))

    quantity = request.form.get('quantity', 1, type=int)
    if quantity <= 0:
        db.session.delete(item)
    else:
        item.quantity = min(quantity, item.listing.quantity_available)
    db.session.commit()
    return redirect(url_for('cart.view_cart'))


@cart_bp.route('/cart/remove/<int:item_id>', methods=['POST'])
@login_required
def remove_from_cart(item_id):
    item = db.get_or_404(CartItem, item_id)
    if item.buyer_id != current_user.id:
        flash('Not authorized.', 'danger')
        return redirect(url_for('cart.view_cart'))
    db.session.delete(item)
    db.session.commit()
    flash('Item removed from cart.', 'info')
    return redirect(url_for('cart.view_cart'))


@cart_bp.route('/cart/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    items = CartItem.query.filter_by(buyer_id=current_user.id).all()
    if not items:
        flash('Your cart is empty.', 'info')
        return redirect(url_for('listings.browse'))

    grouped = defaultdict(list)
    for item in items:
        grouped[item.listing.seller].append(item)

    if request.method == 'POST':
        notes = request.form.get('notes', '')

        for seller, seller_items in grouped.items():
            total = sum(i.listing.effective_price * i.quantity for i in seller_items)
            fulfillment = request.form.get(f'fulfillment_{seller.id}', 'pickup')

            order = Order(
                buyer_id=current_user.id,
                seller_id=seller.id,
                total_price=total,
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
                item.listing.quantity_available = max(0, item.listing.quantity_available - item.quantity)

            for item in seller_items:
                db.session.delete(item)

        db.session.commit()
        flash('Order placed! The seller will review your request.', 'success')
        return redirect(url_for('cart.my_orders'))

    totals = {}
    for seller, seller_items in grouped.items():
        totals[seller.id] = sum(i.listing.effective_price * i.quantity for i in seller_items)
    grand_total = sum(totals.values())

    return render_template('cart/checkout.html', grouped=grouped, totals=totals, grand_total=grand_total)


@cart_bp.route('/orders')
@login_required
def my_orders():
    orders = Order.query.filter_by(buyer_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template('cart/orders.html', orders=orders)


@cart_bp.route('/seller/orders')
@login_required
def seller_orders():
    if not current_user.can_sell():
        flash('Seller account required.', 'warning')
        return redirect(url_for('main.index'))
    orders = Order.query.filter_by(seller_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template('cart/seller_orders.html', orders=orders)


@cart_bp.route('/orders/<int:order_id>')
@login_required
def order_detail(order_id):
    order = db.get_or_404(Order, order_id)
    if order.buyer_id != current_user.id and order.seller_id != current_user.id:
        flash('Not authorized.', 'danger')
        return redirect(url_for('main.index'))
    return render_template('cart/order_detail.html', order=order)


@cart_bp.route('/orders/<int:order_id>/accept', methods=['POST'])
@login_required
def accept_order(order_id):
    order = db.get_or_404(Order, order_id)
    if order.seller_id != current_user.id:
        flash('Not authorized.', 'danger')
        return redirect(url_for('main.index'))
    order.status = 'accepted'
    db.session.commit()
    flash('Order accepted!', 'success')
    return redirect(url_for('cart.seller_orders'))


@cart_bp.route('/orders/<int:order_id>/complete', methods=['POST'])
@login_required
def complete_order(order_id):
    order = db.get_or_404(Order, order_id)
    if order.seller_id != current_user.id:
        flash('Not authorized.', 'danger')
        return redirect(url_for('main.index'))
    order.status = 'completed'
    db.session.commit()
    flash('Order marked complete!', 'success')
    return redirect(url_for('cart.seller_orders'))


@cart_bp.route('/orders/<int:order_id>/cancel', methods=['POST'])
@login_required
def cancel_order(order_id):
    order = db.get_or_404(Order, order_id)
    if order.buyer_id != current_user.id and order.seller_id != current_user.id:
        flash('Not authorized.', 'danger')
        return redirect(url_for('main.index'))

    for oi in order.items:
        oi.listing.quantity_available += oi.quantity

    order.status = 'cancelled'
    db.session.commit()
    flash('Order cancelled.', 'info')

    if current_user.id == order.buyer_id:
        return redirect(url_for('cart.my_orders'))
    return redirect(url_for('cart.seller_orders'))
