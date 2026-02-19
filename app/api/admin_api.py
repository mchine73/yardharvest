"""Admin REST API endpoints."""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import User, Listing, Order, PricingConfig
from app.helpers import admin_required, VEGETABLE_CATEGORIES
from app.pricing import get_pricing_config, get_category_stats
from app.api.auth_api import user_to_dict
from app.api.cart_api import order_to_dict
from sqlalchemy import func

admin_api = Blueprint('admin_api', __name__, url_prefix='/api/admin')


@admin_api.route('/seed', methods=['POST'])
def trigger_seed():
    """Seed the database if empty. Protected by secret token."""
    import os
    token = request.args.get('token', '')
    expected = os.environ.get('SECRET_KEY', '')
    if not token or token != expected:
        return jsonify({'error': 'Unauthorized'}), 403

    user_count = User.query.count()
    if user_count > 0:
        return jsonify({'message': f'Database already has {user_count} users — skipping seed.'})

    try:
        from seed import seed
        seed()
        final_count = User.query.count()
        listing_count = Listing.query.count()
        return jsonify({
            'message': 'Seed complete!',
            'users': final_count,
            'listings': listing_count,
        })
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500


@admin_api.route('/dashboard', methods=['GET'])
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

    return jsonify({
        'total_users': total_users,
        'total_sellers': total_sellers,
        'total_buyers': total_buyers,
        'total_listings': total_listings,
        'total_orders': total_orders,
        'revenue': float(revenue),
        'pending_count': pending_count,
        'completed_count': completed_count,
        'cancelled_count': cancelled_count,
        'recent_orders': [order_to_dict(o) for o in recent_orders],
        'recent_users': [user_to_dict(u) for u in recent_users],
    })


@admin_api.route('/users', methods=['GET'])
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
    pagination = q.order_by(User.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return jsonify({
        'users': [user_to_dict(u) for u in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'page': pagination.page,
    })


@admin_api.route('/users/<int:user_id>/toggle-active', methods=['POST'])
@login_required
@admin_required
def toggle_user_active(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        return jsonify({'error': 'Cannot suspend yourself'}), 400
    user.is_active_user = not user.is_active_user
    db.session.commit()
    return jsonify(user_to_dict(user))


@admin_api.route('/users/<int:user_id>/toggle-admin', methods=['POST'])
@login_required
@admin_required
def toggle_user_admin(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        return jsonify({'error': 'Cannot change your own admin status'}), 400
    user.is_admin = not user.is_admin
    db.session.commit()
    return jsonify(user_to_dict(user))


@admin_api.route('/listings', methods=['GET'])
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

    from app.api.listings_api import listing_to_dict
    pagination = q.order_by(Listing.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return jsonify({
        'listings': [listing_to_dict(l) for l in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'page': pagination.page,
    })


@admin_api.route('/listings/<int:listing_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_listing(listing_id):
    listing = Listing.query.get_or_404(listing_id)
    listing.is_active = not listing.is_active
    db.session.commit()
    return jsonify({'is_active': listing.is_active})


@admin_api.route('/orders', methods=['GET'])
@login_required
@admin_required
def orders():
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', 'all')
    q = Order.query
    if status_filter != 'all':
        q = q.filter_by(status=status_filter)
    pagination = q.order_by(Order.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return jsonify({
        'orders': [order_to_dict(o) for o in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'page': pagination.page,
    })


@admin_api.route('/pricing', methods=['GET'])
@login_required
@admin_required
def get_pricing():
    config = get_pricing_config()
    stats = get_category_stats()
    categories = dict(VEGETABLE_CATEGORIES)
    return jsonify({
        'config': {
            'enabled': config.enabled,
            'global_multiplier': config.global_multiplier,
            'supply_weight': config.supply_weight,
            'velocity_weight': config.velocity_weight,
            'time_decay_weight': config.time_decay_weight,
            'floor_pct': config.floor_pct,
            'ceiling_pct': config.ceiling_pct,
        },
        'category_stats': [{
            'vegetable_type': s.vegetable_type,
            'label': categories.get(s.vegetable_type, s.vegetable_type),
            'count': s.count,
            'avg_price': round(float(s.avg_price or 0), 2),
            'avg_base_price': round(float(s.avg_base_price or 0), 2),
            'min_price': float(s.min_price or 0),
            'max_price': float(s.max_price or 0),
        } for s in stats],
    })


@admin_api.route('/pricing', methods=['PUT'])
@login_required
@admin_required
def update_pricing():
    data = request.get_json()
    config = get_pricing_config()
    config.enabled = data.get('enabled', config.enabled)
    config.global_multiplier = float(data.get('global_multiplier', config.global_multiplier))
    config.supply_weight = float(data.get('supply_weight', config.supply_weight))
    config.velocity_weight = float(data.get('velocity_weight', config.velocity_weight))
    config.time_decay_weight = float(data.get('time_decay_weight', config.time_decay_weight))
    config.floor_pct = float(data.get('floor_pct', config.floor_pct))
    config.ceiling_pct = float(data.get('ceiling_pct', config.ceiling_pct))
    db.session.commit()
    return jsonify({'message': 'Pricing config updated'})
