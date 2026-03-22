"""Admin REST API endpoints."""
import logging
from datetime import datetime, timedelta, timezone
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.api.token_auth import token_or_session, get_current_user
from app import db
from app.models import User, Listing, Order, OrderItem, PricingConfig, SiteEmailConfig
from app.helpers import admin_required, VEGETABLE_CATEGORIES
from app.pricing import get_pricing_config, get_category_stats
from app.api.auth_api import user_to_dict
from app.api.cart_api import order_to_dict
from app.email_service import preview_email, _get_site_email_config
from sqlalchemy import func

log = logging.getLogger(__name__)

admin_api = Blueprint('admin_api', __name__, url_prefix='/api/admin')


@admin_api.route('/version', methods=['GET'])
@token_or_session
@admin_required
def version():
    return jsonify({'version': 'v3-image-urls', 'deployed': True})


@admin_api.route('/seed', methods=['GET', 'POST'])
@token_or_session
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
@token_or_session
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
@token_or_session
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
@token_or_session
@admin_required
def toggle_user_active(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == get_current_user().id:
        return jsonify({'error': 'Cannot suspend yourself'}), 400
    user.is_active_user = not user.is_active_user
    db.session.commit()
    return jsonify(user_to_dict(user))


@admin_api.route('/users/<int:user_id>/toggle-admin', methods=['POST'])
@token_or_session
@admin_required
def toggle_user_admin(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == get_current_user().id:
        return jsonify({'error': 'Cannot change your own admin status'}), 400
    user.is_admin = not user.is_admin
    db.session.commit()
    return jsonify(user_to_dict(user))


@admin_api.route('/listings', methods=['GET'])
@token_or_session
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
@token_or_session
@admin_required
def toggle_listing(listing_id):
    listing = Listing.query.get_or_404(listing_id)
    listing.is_active = not listing.is_active
    db.session.commit()
    return jsonify({'is_active': listing.is_active})


@admin_api.route('/orders', methods=['GET'])
@token_or_session
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
@token_or_session
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
            'doordash_enabled': bool(getattr(config, 'doordash_enabled', False)),
            'doordash_subsidy_pct': getattr(config, 'doordash_subsidy_pct', 0) or 0,
            'doordash_max_subsidy': getattr(config, 'doordash_max_subsidy', 5.0) or 5.0,
            'garden_pro_enabled': bool(getattr(config, 'garden_pro_enabled', True)),
            'garden_pro_trial_days': getattr(config, 'garden_pro_trial_days', 14) or 14,
            'garden_pro_monthly_cents': getattr(config, 'garden_pro_monthly_cents', 1500) or 1500,
            'garden_pro_yearly_cents': getattr(config, 'garden_pro_yearly_cents', 12500) or 12500,
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
@token_or_session
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
    # DoorDash Drive
    if 'doordash_enabled' in data:
        config.doordash_enabled = bool(data['doordash_enabled'])
    if 'doordash_subsidy_pct' in data:
        config.doordash_subsidy_pct = float(data['doordash_subsidy_pct'] or 0)
    if 'doordash_max_subsidy' in data:
        config.doordash_max_subsidy = float(data['doordash_max_subsidy'] or 5.0)
    # Garden Pro subscription
    if 'garden_pro_enabled' in data:
        config.garden_pro_enabled = bool(data['garden_pro_enabled'])
    if 'garden_pro_trial_days' in data:
        config.garden_pro_trial_days = int(data['garden_pro_trial_days'] or 14)
    if 'garden_pro_monthly_cents' in data:
        config.garden_pro_monthly_cents = int(data['garden_pro_monthly_cents'] or 1500)
    if 'garden_pro_yearly_cents' in data:
        config.garden_pro_yearly_cents = int(data['garden_pro_yearly_cents'] or 12500)
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
        'enable_sms_order_confirmation': bool(getattr(config, 'enable_sms_order_confirmation', False)),
        'enable_sms_status_updates': bool(getattr(config, 'enable_sms_status_updates', False)),
        'enable_sms_messages': bool(getattr(config, 'enable_sms_messages', False)),
        'marketplace_enabled': bool(getattr(config, 'marketplace_enabled', False)),
        'enable_harvest_notifications': bool(getattr(config, 'enable_harvest_notifications', True)),
        'enable_sms_harvest_notifications': bool(getattr(config, 'enable_sms_harvest_notifications', False)),
    }


@admin_api.route('/email-config', methods=['GET'])
@token_or_session
@admin_required
def get_email_config():
    config = _get_site_email_config()
    return jsonify(_email_config_to_dict(config))


@admin_api.route('/email-config', methods=['PUT'])
@token_or_session
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

    # Notification toggles (email + SMS)
    for toggle in ['enable_order_confirmation', 'enable_status_updates',
                   'enable_messages', 'enable_announcements', 'enable_subscription_boxes',
                   'enable_sms_order_confirmation', 'enable_sms_status_updates',
                   'enable_sms_messages', 'marketplace_enabled',
                   'enable_harvest_notifications', 'enable_sms_harvest_notifications']:
        if toggle in data:
            setattr(config, toggle, bool(data[toggle]))

    db.session.commit()
    return jsonify(_email_config_to_dict(config))


@admin_api.route('/email-preview/<template_type>', methods=['GET'])
@token_or_session
@admin_required
def email_preview(template_type):
    """Render a sample email for live preview with current config."""
    valid_types = ['order_confirmation', 'status_update', 'message', 'announcement', 'harvest_notification']
    if template_type not in valid_types:
        return jsonify({'error': f'Invalid template type. Choose from: {", ".join(valid_types)}'}), 400

    config = _get_site_email_config()
    html = preview_email(template_type, config)
    return jsonify({'html': html, 'type': template_type})


@admin_api.route('/site-config', methods=['GET'])
def get_site_config():
    """Public endpoint for frontend feature flags."""
    config = SiteEmailConfig.query.first()
    return jsonify({
        'marketplace_enabled': config.marketplace_enabled if config else False,
    })


@admin_api.route('/public-pricing', methods=['GET'])
def public_pricing():
    """Public endpoint for the pricing page — returns Garden Pro and marketplace pricing."""
    pricing = get_pricing_config()
    site_config = SiteEmailConfig.query.first()
    return jsonify({
        'garden_pro': {
            'enabled': bool(getattr(pricing, 'garden_pro_enabled', True)),
            'trial_days': getattr(pricing, 'garden_pro_trial_days', 14) or 14,
            'monthly': (getattr(pricing, 'garden_pro_monthly_cents', 1500) or 1500) / 100,
            'yearly': (getattr(pricing, 'garden_pro_yearly_cents', 12500) or 12500) / 100,
        },
        'marketplace': {
            'enabled': site_config.marketplace_enabled if site_config else False,
            'commission_rate': pricing.platform_commission_pct or 0,
            'commission_enabled': bool(pricing.commission_enabled),
            'smart_pricing_enabled': bool(pricing.enabled),
            'price_floor_pct': pricing.floor_pct or 0.70,
            'price_ceiling_pct': pricing.ceiling_pct or 2.0,
            'delivery_fee_flat': pricing.delivery_fee_flat or 0,
            'delivery_fees_enabled': bool(pricing.delivery_fees_enabled),
            'free_delivery_threshold': pricing.delivery_fee_free_threshold or 0,
            'free_delivery_enabled': bool(pricing.free_delivery_enabled),
            'doordash_enabled': bool(getattr(pricing, 'doordash_enabled', False)),
        },
    })


# ---------------------------------------------------------------------------
# Platform Statistics / P&L
# ---------------------------------------------------------------------------

def _period_start(period):
    """Return the start datetime for the given period string."""
    now = datetime.now(timezone.utc)
    if period == 'week':
        return now - timedelta(days=7)
    if period == 'month':
        return now - timedelta(days=30)
    if period == 'quarter':
        return now - timedelta(days=90)
    if period == 'year':
        return now - timedelta(days=365)
    return None  # 'all' — no filter


@admin_api.route('/platform-stats', methods=['GET'])
@token_or_session
@admin_required
def platform_stats():
    period = request.args.get('period', 'month')
    start = _period_start(period)

    # Base query — all orders in period (any status)
    base = Order.query
    if start:
        base = base.filter(Order.created_at >= start)

    # --- Revenue (completed only) ---
    completed = base.filter(Order.status == 'completed')
    gross_sales = db.session.query(
        func.coalesce(func.sum(Order.total_price), 0)
    ).filter(Order.status == 'completed')
    if start:
        gross_sales = gross_sales.filter(Order.created_at >= start)
    gross_sales = float(gross_sales.scalar())

    commissions = db.session.query(
        func.coalesce(func.sum(Order.platform_commission), 0)
    ).filter(Order.status == 'completed')
    if start:
        commissions = commissions.filter(Order.created_at >= start)
    commissions = float(commissions.scalar())

    delivery_fees = db.session.query(
        func.coalesce(func.sum(Order.delivery_fee), 0)
    ).filter(Order.status == 'completed')
    if start:
        delivery_fees = delivery_fees.filter(Order.created_at >= start)
    delivery_fees = float(delivery_fees.scalar())

    seller_payouts = db.session.query(
        func.coalesce(func.sum(Order.seller_earnings), 0)
    ).filter(Order.status == 'completed')
    if start:
        seller_payouts = seller_payouts.filter(Order.created_at >= start)
    seller_payouts = float(seller_payouts.scalar())

    net_platform_revenue = round(commissions + delivery_fees, 2)

    # --- Order metrics ---
    total_orders = base.count()
    completed_count = base.filter(Order.status == 'completed').count()
    orders_by_status = {}
    for status_val in ['pending', 'accepted', 'completed', 'cancelled']:
        orders_by_status[status_val] = base.filter(Order.status == status_val).count()

    avg_order_q = db.session.query(func.avg(Order.total_price)).filter(Order.status == 'completed')
    if start:
        avg_order_q = avg_order_q.filter(Order.created_at >= start)
    avg_order_value = float(avg_order_q.scalar() or 0)

    completion_rate = round(completed_count / total_orders * 100, 1) if total_orders > 0 else 0

    # --- User metrics ---
    total_users = User.query.count()
    new_users = User.query
    if start:
        new_users = new_users.filter(User.created_at >= start)
    new_users_count = new_users.count() if start else total_users

    # Active sellers/buyers in period (have at least 1 order)
    active_sellers_q = db.session.query(func.count(func.distinct(Order.seller_id)))
    active_buyers_q = db.session.query(func.count(func.distinct(Order.buyer_id)))
    if start:
        active_sellers_q = active_sellers_q.filter(Order.created_at >= start)
        active_buyers_q = active_buyers_q.filter(Order.created_at >= start)
    active_sellers = active_sellers_q.scalar() or 0
    active_buyers = active_buyers_q.scalar() or 0

    # --- Top 5 Sellers ---
    top_sellers_q = db.session.query(
        Order.seller_id,
        func.sum(Order.total_price).label('revenue'),
        func.count(Order.id).label('order_count')
    ).filter(Order.status == 'completed')
    if start:
        top_sellers_q = top_sellers_q.filter(Order.created_at >= start)
    top_sellers_q = top_sellers_q.group_by(Order.seller_id).order_by(
        func.sum(Order.total_price).desc()
    ).limit(5).all()

    top_sellers = []
    for row in top_sellers_q:
        seller = User.query.get(row.seller_id)
        top_sellers.append({
            'name': (seller.display_name or seller.username) if seller else 'Unknown',
            'revenue': round(float(row.revenue), 2),
            'order_count': row.order_count,
        })

    # --- Top 5 Categories ---
    categories_dict = dict(VEGETABLE_CATEGORIES)
    top_categories_q = db.session.query(
        Listing.vegetable_type,
        func.count(OrderItem.id).label('order_count'),
        func.sum(OrderItem.unit_price * OrderItem.quantity).label('revenue')
    ).join(OrderItem, OrderItem.listing_id == Listing.id
    ).join(Order, Order.id == OrderItem.order_id
    ).filter(Order.status == 'completed')
    if start:
        top_categories_q = top_categories_q.filter(Order.created_at >= start)
    top_categories_q = top_categories_q.group_by(Listing.vegetable_type).order_by(
        func.sum(OrderItem.unit_price * OrderItem.quantity).desc()
    ).limit(5).all()

    top_categories = []
    for row in top_categories_q:
        top_categories.append({
            'category': categories_dict.get(row.vegetable_type, row.vegetable_type or 'Other'),
            'order_count': row.order_count,
            'revenue': round(float(row.revenue or 0), 2),
        })

    return jsonify({
        'period': period,
        'revenue': {
            'gross_sales': round(gross_sales, 2),
            'platform_commissions': round(commissions, 2),
            'delivery_fees': round(delivery_fees, 2),
            'net_platform_revenue': round(net_platform_revenue, 2),
            'seller_payouts': round(seller_payouts, 2),
        },
        'orders': {
            'total': total_orders,
            'avg_order_value': round(avg_order_value, 2),
            'completion_rate': completion_rate,
            'by_status': orders_by_status,
        },
        'users': {
            'total': total_users,
            'new_in_period': new_users_count,
            'active_sellers': active_sellers,
            'active_buyers': active_buyers,
        },
        'top_sellers': top_sellers,
        'top_categories': top_categories,
    })


# ---------------------------------------------------------------------------
# Twilio SMS Status & Test
# ---------------------------------------------------------------------------

@admin_api.route('/twilio-status', methods=['GET'])
@login_required
def twilio_status():
    if not current_user.is_admin:
        return jsonify({'error': 'Admin required'}), 403
    import os
    sid = os.environ.get('TWILIO_ACCOUNT_SID', '')
    token = os.environ.get('TWILIO_AUTH_TOKEN', '')
    phone = os.environ.get('TWILIO_PHONE_NUMBER', '')
    configured = bool(sid and token and phone)
    return jsonify({
        'configured': configured,
        'phone_last4': phone[-4:] if phone else None,
    })


@admin_api.route('/test-sms', methods=['POST'])
@login_required
def test_sms():
    if not current_user.is_admin:
        return jsonify({'error': 'Admin required'}), 403
    data = request.get_json() or {}
    phone = data.get('phone', '')
    if not phone:
        return jsonify({'error': 'Phone number required'}), 400
    try:
        from app.sms_service import send_sms
        send_sms(phone, 'YardHarvest: This is a test SMS from your platform admin settings.')
        return jsonify({'success': True, 'message': f'Test SMS sent to {phone}'})
    except Exception as e:
        return jsonify({'error': f'Failed to send test SMS: {str(e)}'}), 500
