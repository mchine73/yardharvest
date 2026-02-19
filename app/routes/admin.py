from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import User, Listing, Order, OrderItem, Review, Message, PricingConfig
from app.helpers import admin_required, VEGETABLE_CATEGORIES
from app.pricing import get_pricing_config, get_category_stats
from sqlalchemy import func

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/')
@login_required
@admin_required
def dashboard():
    total_users = User.query.count()
    total_sellers = User.query.filter(User.role.in_(['seller', 'both'])).count()
    total_buyers = User.query.filter(User.role.in_(['buyer', 'both'])).count()
    total_listings = Listing.query.filter_by(is_active=True).count()
    total_orders = Order.query.count()
    revenue = db.session.query(
        func.coalesce(func.sum(Order.total_price), 0)
    ).filter_by(status='completed').scalar()
    pending_count = Order.query.filter_by(status='pending').count()
    completed_count = Order.query.filter_by(status='completed').count()
    cancelled_count = Order.query.filter_by(status='cancelled').count()
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(10).all()
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()

    return render_template('admin/dashboard.html',
                           total_users=total_users,
                           total_sellers=total_sellers,
                           total_buyers=total_buyers,
                           total_listings=total_listings,
                           total_orders=total_orders,
                           revenue=revenue,
                           pending_count=pending_count,
                           completed_count=completed_count,
                           cancelled_count=cancelled_count,
                           recent_orders=recent_orders,
                           recent_users=recent_users)


@admin_bp.route('/users')
@login_required
@admin_required
def users():
    search = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    q = User.query
    if search:
        q = q.filter(
            (User.username.ilike(f'%{search}%')) |
            (User.email.ilike(f'%{search}%')) |
            (User.display_name.ilike(f'%{search}%'))
        )
    users = q.order_by(User.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    return render_template('admin/users.html', users=users, search=search)


@admin_bp.route('/users/<int:user_id>/toggle-active', methods=['POST'])
@login_required
@admin_required
def toggle_user_active(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('You cannot suspend yourself.', 'warning')
        return redirect(url_for('admin.users'))
    user.is_active_user = not user.is_active_user
    db.session.commit()
    status = "activated" if user.is_active_user else "suspended"
    flash(f'User {user.username} has been {status}.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/toggle-admin', methods=['POST'])
@login_required
@admin_required
def toggle_user_admin(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('You cannot change your own admin status.', 'warning')
        return redirect(url_for('admin.users'))
    user.is_admin = not user.is_admin
    db.session.commit()
    status = "promoted to admin" if user.is_admin else "removed from admin"
    flash(f'User {user.username} has been {status}.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/listings')
@login_required
@admin_required
def listings():
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'all')
    q = Listing.query
    if status_filter == 'active':
        q = q.filter_by(is_active=True)
    elif status_filter == 'inactive':
        q = q.filter_by(is_active=False)
    listings = q.order_by(Listing.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    return render_template('admin/listings.html',
                           listings=listings,
                           status_filter=status_filter)


@admin_bp.route('/listings/<int:listing_id>/deactivate', methods=['POST'])
@login_required
@admin_required
def deactivate_listing(listing_id):
    listing = Listing.query.get_or_404(listing_id)
    listing.is_active = False
    db.session.commit()
    flash(f'Listing "{listing.title}" deactivated.', 'success')
    return redirect(url_for('admin.listings'))


@admin_bp.route('/listings/<int:listing_id>/activate', methods=['POST'])
@login_required
@admin_required
def activate_listing(listing_id):
    listing = Listing.query.get_or_404(listing_id)
    listing.is_active = True
    db.session.commit()
    flash(f'Listing "{listing.title}" activated.', 'success')
    return redirect(url_for('admin.listings'))


@admin_bp.route('/orders')
@login_required
@admin_required
def orders():
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'all')
    q = Order.query
    if status_filter != 'all':
        q = q.filter_by(status=status_filter)
    orders = q.order_by(Order.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    return render_template('admin/orders.html',
                           orders=orders,
                           status_filter=status_filter)


@admin_bp.route('/pricing', methods=['GET', 'POST'])
@login_required
@admin_required
def pricing():
    config = get_pricing_config()
    if request.method == 'POST':
        config.enabled = 'enabled' in request.form
        config.global_multiplier = float(request.form.get('global_multiplier', 1.0))
        config.supply_weight = float(request.form.get('supply_weight', 0.5))
        config.velocity_weight = float(request.form.get('velocity_weight', 0.3))
        config.time_decay_weight = float(request.form.get('time_decay_weight', 0.2))
        config.floor_pct = float(request.form.get('floor_pct', 0.70))
        config.ceiling_pct = float(request.form.get('ceiling_pct', 2.0))
        db.session.commit()
        flash('Pricing configuration updated.', 'success')
        return redirect(url_for('admin.pricing'))

    category_stats = get_category_stats()
    categories = dict(VEGETABLE_CATEGORIES)
    return render_template('admin/pricing.html',
                           config=config,
                           category_stats=category_stats,
                           categories=categories)
