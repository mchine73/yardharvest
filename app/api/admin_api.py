"""Admin REST API endpoints."""
import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import User, Listing, Order, PricingConfig, SiteEmailConfig
from app.helpers import admin_required, VEGETABLE_CATEGORIES
from app.pricing import get_pricing_config, get_category_stats
from app.api.auth_api import user_to_dict
from app.api.cart_api import order_to_dict
from app.email_service import preview_email, _get_site_email_config
from sqlalchemy import func

log = logging.getLogger(__name__)

admin_api = Blueprint('admin_api', __name__, url_prefix='/api/admin')


@admin_api.route('/version', methods=['GET'])
def version():
    return jsonify({'version': 'v3-image-urls', 'deployed': True})


@admin_api.route('/seed', methods=['GET', 'POST'])
@login_required
@admin_required
def trigger_seed():
    """Seed the database if incomplete. Admin-only."""
    user_count = User.query.count()
    listing_count = Listing.query.count()

    force = request.args.get('force', '').lower() in ('1', 'true', 'yes')

    # Only skip if fully seeded (8 users + 18 listings) and not forcing
    if user_count >= 8 and listing_count >= 18 and not force:
        return jsonify({'message': f'Already seeded: {user_count} users, {listing_count} listings. Add ?force=1 to re-seed.', 'version': 'v2'})

    try:
        from seed import seed
        seed()
        final_users = User.query.count()
        final_listings = Listing.query.count()
        return jsonify({
            'message': 'Seed complete!',
            'users': final_users,
            'listings': final_listings,
        })
    except Exception as e:
        db.session.rollback()
        log.exception('Database seed failed')
        return jsonify({'error': 'Database seed failed. Check server logs.'}), 500


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
    platform_revenue = db.session.query(
        func.coalesce(func.sum(Order.platform_commission), 0)
    ).filter_by(status='completed').scalar()
    delivery_fees_collected = db.session.query(
        func.coalesce(func.sum(Order.delivery_fee), 0)
    ).filter_by(status='completed').scalar()
    seller_payouts_total = db.session.query(
        func.coalesce(func.sum(Order.seller_earnings), 0)
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
        'platform_revenue': float(platform_revenue),
        'delivery_fees_collected': float(delivery_fees_collected),
        'seller_payouts_total': float(seller_payouts_total),
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
            'commission_enabled': bool(config.commission_enabled),
            'platform_commission_pct': config.platform_commission_pct or 0,
            'delivery_fees_enabled': bool(config.delivery_fees_enabled),
            'delivery_fee_flat': config.delivery_fee_flat or 0,
            'per_mile_enabled': bool(config.per_mile_enabled),
            'delivery_fee_per_mile': config.delivery_fee_per_mile or 0,
            'free_delivery_enabled': bool(config.free_delivery_enabled),
            'delivery_fee_free_threshold': config.delivery_fee_free_threshold or 0,
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
    config.commission_enabled = data.get('commission_enabled', config.commission_enabled)
    config.platform_commission_pct = float(data.get('platform_commission_pct', config.platform_commission_pct or 0))
    config.delivery_fees_enabled = data.get('delivery_fees_enabled', config.delivery_fees_enabled)
    config.delivery_fee_flat = float(data.get('delivery_fee_flat', config.delivery_fee_flat or 0))
    config.per_mile_enabled = data.get('per_mile_enabled', config.per_mile_enabled)
    config.delivery_fee_per_mile = float(data.get('delivery_fee_per_mile', config.delivery_fee_per_mile or 0))
    config.free_delivery_enabled = data.get('free_delivery_enabled', config.free_delivery_enabled)
    config.delivery_fee_free_threshold = float(data.get('delivery_fee_free_threshold', config.delivery_fee_free_threshold or 0))
    db.session.commit()
    return jsonify({'message': 'Pricing config updated'})


# ---------------------------------------------------------------------------
# Email Configuration
# ---------------------------------------------------------------------------

def _email_config_to_dict(config):
    return {
        'logo_url': config.logo_url or '',
        'header_color': config.header_color or '#2d6a2e',
        'tagline': config.tagline or '',
        'footer_text': config.footer_text or '',
        'from_name': config.from_name or 'YardHarvest',
        'subject_prefix': config.subject_prefix or 'YardHarvest',
        'enable_order_confirmation': bool(config.enable_order_confirmation),
        'enable_status_updates': bool(config.enable_status_updates),
        'enable_messages': bool(config.enable_messages),
        'enable_announcements': bool(config.enable_announcements),
        'enable_subscription_boxes': bool(config.enable_subscription_boxes),
    }


@admin_api.route('/email-config', methods=['GET'])
@login_required
@admin_required
def get_email_config():
    config = _get_site_email_config()
    return jsonify(_email_config_to_dict(config))


@admin_api.route('/email-config', methods=['PUT'])
@login_required
@admin_required
def update_email_config():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    config = _get_site_email_config()

    # Branding fields
    if 'logo_url' in data:
        config.logo_url = (data['logo_url'] or '')[:500]
    if 'header_color' in data:
        color = data['header_color'] or '#2d6a2e'
        if len(color) <= 7:
            config.header_color = color
    if 'tagline' in data:
        config.tagline = (data['tagline'] or '')[:200]
    if 'footer_text' in data:
        config.footer_text = (data['footer_text'] or '')[:1000]
    if 'from_name' in data:
        config.from_name = (data['from_name'] or 'YardHarvest')[:100]
    if 'subject_prefix' in data:
        config.subject_prefix = (data['subject_prefix'] or 'YardHarvest')[:50]

    # Notification toggles
    for toggle in ['enable_order_confirmation', 'enable_status_updates',
                   'enable_messages', 'enable_announcements', 'enable_subscription_boxes']:
        if toggle in data:
            setattr(config, toggle, bool(data[toggle]))

    db.session.commit()
    return jsonify(_email_config_to_dict(config))


@admin_api.route('/email-preview/<template_type>', methods=['GET'])
@login_required
@admin_required
def email_preview(template_type):
    """Render a sample email for live preview with current config."""
    valid_types = ['order_confirmation', 'status_update', 'message', 'announcement']
    if template_type not in valid_types:
        return jsonify({'error': f'Invalid template type. Choose from: {", ".join(valid_types)}'}), 400

    config = _get_site_email_config()
    html = preview_email(template_type, config)
    return jsonify({'html': html, 'type': template_type})
