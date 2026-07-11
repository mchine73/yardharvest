"""Admin REST API endpoints."""
import logging
from datetime import datetime, timedelta, timezone
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.api.token_auth import token_or_session, get_current_user
from app import db
from app.models import (User, Listing, Order, OrderItem, PricingConfig, SiteEmailConfig,
                        CommunityGarden, GardenSubscription, GardenMembership, GardenPlot)
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
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(10).all()
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()

    # ---- Garden-mode vitals (the live business): subscription-status
    # counts, week-over-week signups, trials ending soon, estimated MRR,
    # newest gardens. The old payload measured only the dormant marketplace.
    from datetime import timedelta
    from app.models import CommunityGarden, GardenSubscription
    from app.pricing import get_pricing_config

    now = datetime.now(timezone.utc)
    week_ago, two_weeks_ago = now - timedelta(days=7), now - timedelta(days=14)
    sub_status_col = func.coalesce(GardenSubscription.status, 'free')
    garden_status_counts = {s: n for s, n in
                            db.session.query(sub_status_col, func.count(CommunityGarden.id))
                            .select_from(CommunityGarden)
                            .outerjoin(GardenSubscription,
                                       GardenSubscription.garden_id == CommunityGarden.id)
                            .group_by(sub_status_col).all()}

    def _week_pair(model):
        this_week = model.query.filter(model.created_at >= week_ago).count()
        last_week = model.query.filter(model.created_at >= two_weeks_ago,
                                       model.created_at < week_ago).count()
        return {'this_week': this_week, 'last_week': last_week}

    def _aware(dt):
        # DB datetimes come back offset-naive (stored as UTC) — normalize
        # before arithmetic with the aware `now`.
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    trials_ending = [{
        'garden_id': g.id, 'name': g.name,
        'trial_end': s.trial_end.isoformat(),
        'days_left': max(0, (_aware(s.trial_end) - now).days),
    } for g, s in (db.session.query(CommunityGarden, GardenSubscription)
                   .join(GardenSubscription,
                         GardenSubscription.garden_id == CommunityGarden.id)
                   .filter(GardenSubscription.status == 'trialing',
                           GardenSubscription.trial_end.isnot(None),
                           GardenSubscription.trial_end >= now,
                           GardenSubscription.trial_end <= now + timedelta(days=7))
                   .order_by(GardenSubscription.trial_end).all())]

    # Estimated MRR from pricing config x active subs (annual normalized /12).
    # An ESTIMATE by design: subs predating a price change or created with a
    # garden_pro promo drift from actual Stripe charges — the UI labels it so.
    pricing = get_pricing_config()
    cycle_counts = dict(db.session.query(GardenSubscription.billing_cycle,
                                         func.count(GardenSubscription.id))
                        .filter(GardenSubscription.status == 'active')
                        .group_by(GardenSubscription.billing_cycle).all())
    mrr_cents = (cycle_counts.get('monthly', 0) * (pricing.garden_pro_monthly_cents or 0)
                 + round(cycle_counts.get('yearly', 0) * (pricing.garden_pro_yearly_cents or 0) / 12))

    garden_status_of = dict(db.session.query(GardenSubscription.garden_id,
                                             GardenSubscription.status).all())
    newest_gardens = [{
        'id': g.id, 'name': g.name,
        'organizer': (organizer.display_name or organizer.username) if organizer else 'Unknown',
        'status': garden_status_of.get(g.id, 'free'),
        'created_at': g.created_at.isoformat() if g.created_at else None,
    } for g, organizer in (db.session.query(CommunityGarden, User)
                           .outerjoin(User, User.id == CommunityGarden.organizer_id)
                           .order_by(CommunityGarden.created_at.desc())
                           .limit(6).all())]

    return jsonify({
        'total_users': total_users,
        'total_sellers': total_sellers,
        'total_listings': total_listings,
        'total_orders': total_orders,
        'revenue': float(revenue),
        'platform_revenue': float(platform_revenue),
        'delivery_fees_collected': float(delivery_fees_collected),
        'seller_payouts_total': float(seller_payouts_total),
        'recent_orders': [order_to_dict(o) for o in recent_orders],
        # Minimal on purpose: the dashboard needs name + signup date, not the
        # full own-profile dict (and user_to_dict has no created_at).
        'recent_users': [{
            'id': u.id,
            'username': u.username,
            'display_name': u.display_name,
            'created_at': u.created_at.isoformat() if u.created_at else None,
        } for u in recent_users],
        # Garden-mode vitals
        'gardens': {
            'total': CommunityGarden.query.count(),
            'status_counts': garden_status_counts,
            'new': _week_pair(CommunityGarden),
        },
        'users_new': _week_pair(User),
        'trials_ending_soon': trials_ending,
        'estimated_mrr': mrr_cents / 100.0,
        'newest_gardens': newest_gardens,
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
    user = db.get_or_404(User, user_id)
    if user.id == get_current_user().id:
        return jsonify({'error': 'Cannot suspend yourself'}), 400
    user.is_active_user = not user.is_active_user
    db.session.commit()
    return jsonify(user_to_dict(user))


@admin_api.route('/users/<int:user_id>/toggle-admin', methods=['POST'])
@token_or_session
@admin_required
def toggle_user_admin(user_id):
    user = db.get_or_404(User, user_id)
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
    listing = db.get_or_404(Listing, listing_id)
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
            'garden_dues_fee_percent': getattr(config, 'garden_dues_fee_percent', 0) or 0,
            'dues_require_payout_ready': bool(getattr(config, 'dues_require_payout_ready', True)),
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
    if 'garden_dues_fee_percent' in data:
        config.garden_dues_fee_percent = float(data['garden_dues_fee_percent'] or 0)
    if 'dues_require_payout_ready' in data:
        config.dues_require_payout_ready = bool(data['dues_require_payout_ready'])
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
        seller = db.session.get(User, row.seller_id)
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


# ==================== Admin Garden Management ====================

@admin_api.route('/gardens', methods=['GET'])
@token_or_session
@admin_required
def admin_gardens():
    """List all community gardens with subscription info and member counts.

    Status filtering happens in SQL BEFORE pagination. The old version
    paginated the unfiltered query and discarded non-matching rows inside the
    per-page loop, so the status tabs silently dropped gardens that fell on
    other pages and total/pages were always unfiltered — wrong exactly during
    the weekly billing-health check. The subscription outer join cannot
    duplicate gardens (GardenSubscription.garden_id is unique).

    NOTE: filter on the coalesced GardenSubscription.status — never on the
    denormalized CommunityGarden.subscription_status column — so the tabs
    can't drift from the badges, which derive from the same coalesce.
    """
    from sqlalchemy import func, or_
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    search = request.args.get('q', '')
    active_filter = request.args.get('active', '')

    sub_status_col = func.coalesce(GardenSubscription.status, 'free')

    def _base_query():
        q = (CommunityGarden.query
             .outerjoin(GardenSubscription,
                        GardenSubscription.garden_id == CommunityGarden.id)
             .outerjoin(User, User.id == CommunityGarden.organizer_id))
        if search:
            like = f'%{search}%'
            # The operator's real lookup is often "the garden of the person
            # who just emailed me" — search the organizer too.
            q = q.filter(or_(CommunityGarden.name.ilike(like),
                             User.email.ilike(like),
                             User.username.ilike(like),
                             User.display_name.ilike(like)))
        if active_filter in ('true', '1'):
            q = q.filter(CommunityGarden.is_active.is_(True))
        elif active_filter in ('false', '0'):
            q = q.filter(CommunityGarden.is_active.is_(False))
        return q

    # Per-status counts for the tab labels — one grouped query over the same
    # coalesced expression (also surfaces any unexpected status value).
    status_counts = {s: n for s, n in
                     _base_query()
                     .with_entities(sub_status_col, func.count(CommunityGarden.id))
                     .group_by(sub_status_col).all()}

    query = _base_query()
    if status_filter:
        query = query.filter(sub_status_col == status_filter)

    gardens = query.order_by(CommunityGarden.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )

    # Batched page lookups (the old loop ran 4 queries per row).
    ids = [g.id for g in gardens.items]
    subs = {s.garden_id: s for s in GardenSubscription.query
            .filter(GardenSubscription.garden_id.in_(ids or [0]))}
    member_counts = dict(db.session.query(
        GardenMembership.garden_id, func.count(GardenMembership.id))
        .filter(GardenMembership.garden_id.in_(ids or [0]))
        .group_by(GardenMembership.garden_id).all())
    plot_counts = dict(db.session.query(
        GardenPlot.garden_id, func.count(GardenPlot.id))
        .filter(GardenPlot.garden_id.in_(ids or [0]))
        .group_by(GardenPlot.garden_id).all())
    organizers = {u.id: u for u in User.query.filter(
        User.id.in_({g.organizer_id for g in gardens.items} or {0}))}

    results = []
    for g in gardens.items:
        sub = subs.get(g.id)
        member_count = member_counts.get(g.id, 0)
        plot_count = plot_counts.get(g.id, 0)
        organizer = organizers.get(g.organizer_id)

        sub_status = sub.status if sub else 'free'

        results.append({
            'id': g.id,
            'name': g.name,
            'organizer': {
                'id': organizer.id if organizer else None,
                'name': organizer.display_name or organizer.username if organizer else 'Unknown',
                'email': organizer.email if organizer else '',
            },
            'member_count': member_count,
            'plot_count': plot_count,
            'is_active': g.is_active,
            'subscription_status': sub_status,
            'billing_cycle': sub.billing_cycle if sub else None,
            'trial_end': sub.trial_end.isoformat() if sub and sub.trial_end else None,
            'current_period_end': sub.current_period_end.isoformat() if sub and sub.current_period_end else None,
            'created_at': g.created_at.isoformat() if g.created_at else None,
        })

    return jsonify({
        'gardens': results,
        'page': gardens.page,
        'pages': gardens.pages,
        'total': gardens.total,
        'status_counts': status_counts,
    })


@admin_api.route('/gardens/<int:garden_id>/members', methods=['GET'])
@token_or_session
@admin_required
def admin_garden_members(garden_id):
    """List all members of a garden with their plot assignments."""
    garden = db.get_or_404(CommunityGarden, garden_id)
    memberships = GardenMembership.query.filter_by(garden_id=garden_id).all()

    members = []
    for m in memberships:
        user = db.session.get(User, m.user_id)
        if not user:
            continue
        plot = GardenPlot.query.filter_by(garden_id=garden_id, assigned_to_id=user.id).first()
        members.append({
            'id': user.id,
            'name': user.display_name or user.username,
            'email': user.email,
            'phone': user.phone_number or '',
            'role': m.role,
            'plot_number': plot.plot_number if plot else None,
            'plot_status': plot.status if plot else None,
            'joined_at': m.joined_at.isoformat() if m.joined_at else None,
        })

    return jsonify({
        'garden_name': garden.name,
        'members': members,
    })


@admin_api.route('/gardens/<int:garden_id>/subscription-status', methods=['POST'])
@token_or_session
@admin_required
def admin_update_garden_subscription(garden_id):
    """Admin override to set a garden's subscription status."""
    garden = db.get_or_404(CommunityGarden, garden_id)
    data = request.get_json() or {}
    new_status = data.get('status', '')

    if new_status not in ('free', 'trialing', 'active', 'expired'):
        return jsonify({'error': 'Invalid status. Must be: free, trialing, active, expired'}), 400

    sub = GardenSubscription.query.filter_by(garden_id=garden_id).first()

    if new_status == 'free':
        garden.subscription_status = 'free'
        if sub:
            sub.status = 'expired'
            sub.admin_granted = False
    else:
        garden.subscription_status = new_status
        if sub:
            sub.status = new_status
            # This is an admin grant: mark it so the billing page hides the
            # "cancellation scheduled" banner, and clear any stale cancel flag.
            sub.admin_granted = True
            sub.cancel_at_period_end = False
        else:
            from datetime import timedelta
            now = datetime.now(timezone.utc)
            sub = GardenSubscription(
                garden_id=garden_id,
                status=new_status,
                admin_granted=True,
                trial_start=now,
                trial_end=now + timedelta(days=14) if new_status == 'trialing' else now,
                current_period_start=now,
                current_period_end=now + timedelta(days=30),
            )
            db.session.add(sub)

    db.session.commit()
    return jsonify({'message': f'Garden subscription status updated to {new_status}'})


def _garden_admin_dict(garden):
    """Serialize a garden's editable core fields for admin responses."""
    return {
        'id': garden.id,
        'name': garden.name,
        'description': garden.description,
        'address': garden.address,
        'city': garden.city,
        'state': garden.state,
        'zip_code': garden.zip_code,
        'contact_email': garden.contact_email,
        'rules': garden.rules,
        'photo_url': garden.photo_url,
        'plot_fee_annual': garden.plot_fee_annual,
        'operating_model': garden.operating_model,
        'season_start': garden.season_start.isoformat() if garden.season_start else None,
        'season_end': garden.season_end.isoformat() if garden.season_end else None,
        'is_active': garden.is_active,
    }


@admin_api.route('/gardens/<int:garden_id>/details', methods=['GET'])
@token_or_session
@admin_required
def admin_garden_details(garden_id):
    """Return a garden's editable core fields (for the admin edit form)."""
    garden = db.get_or_404(CommunityGarden, garden_id)
    return jsonify({'garden': _garden_admin_dict(garden)})


@admin_api.route('/gardens/<int:garden_id>/toggle-active', methods=['POST'])
@token_or_session
@admin_required
def admin_toggle_garden_active(garden_id):
    """List / delist a garden.

    Delisting (is_active=False) removes the garden from the public garden
    browse + search; the organizer and existing members keep full access via
    direct links (this mirrors the platform-wide ``is_active`` semantics). Pass
    an explicit ``{"is_active": bool}`` to set a specific state, or omit it to
    toggle.
    """
    garden = db.get_or_404(CommunityGarden, garden_id)
    data = request.get_json(silent=True) or {}
    if 'is_active' in data:
        garden.is_active = bool(data['is_active'])
    else:
        garden.is_active = not garden.is_active
    db.session.commit()
    return jsonify({
        'message': 'Garden listed' if garden.is_active else 'Garden delisted',
        'is_active': garden.is_active,
    })


@admin_api.route('/gardens/<int:garden_id>', methods=['PUT'])
@token_or_session
@admin_required
def admin_update_garden(garden_id):
    """Edit a garden's core details as a platform admin (no impersonation)."""
    garden = db.get_or_404(CommunityGarden, garden_id)
    data = request.get_json() or {}

    if 'name' in data:
        name = (data['name'] or '').strip()
        if not name:
            return jsonify({'error': 'Name cannot be empty'}), 400
        garden.name = name[:150]
    for field in ('description', 'address', 'city', 'state', 'zip_code',
                  'contact_email', 'rules', 'photo_url'):
        if field in data:
            setattr(garden, field, (data[field] or None))
    if 'operating_model' in data:
        om = (data['operating_model'] or '').strip()
        if om and om not in ('allotment', 'communal', 'hybrid'):
            return jsonify({'error': 'operating_model must be allotment, communal or hybrid'}), 400
        if om:
            garden.operating_model = om
    if 'plot_fee_annual' in data:
        try:
            garden.plot_fee_annual = max(0.0, float(data['plot_fee_annual'] or 0))
        except (TypeError, ValueError):
            return jsonify({'error': 'plot_fee_annual must be a number'}), 400
    for field in ('season_start', 'season_end'):
        if field in data:
            val = data[field]
            if val:
                try:
                    setattr(garden, field, datetime.strptime(val, '%Y-%m-%d').date())
                except ValueError:
                    return jsonify({'error': f'{field} must be in YYYY-MM-DD format'}), 400
            else:
                setattr(garden, field, None)

    db.session.commit()
    return jsonify({'message': 'Garden updated', 'garden': _garden_admin_dict(garden)})


@admin_api.route('/gardens/<int:garden_id>/summary', methods=['GET'])
@token_or_session
@admin_required
def admin_garden_summary(garden_id):
    """Read-only finance + impact roll-up for one garden."""
    from app.models import GardenDuesRecord, GardenExpense, HarvestLog, GardenEvent
    garden = db.get_or_404(CommunityGarden, garden_id)

    plots = GardenPlot.query.filter_by(garden_id=garden_id).all()
    total_plots = len(plots)
    assigned = sum(1 for p in plots if p.status == 'assigned')
    available = sum(1 for p in plots if p.status == 'available')

    def _sum(model, col):
        return db.session.query(
            func.coalesce(func.sum(col), 0.0)
        ).filter(model.garden_id == garden_id).scalar() or 0.0

    dues_expected = float(_sum(GardenDuesRecord, GardenDuesRecord.amount_due))
    dues_collected = float(_sum(GardenDuesRecord, GardenDuesRecord.amount_paid))
    expenses = float(_sum(GardenExpense, GardenExpense.amount))
    harvest_lbs = float(_sum(HarvestLog, HarvestLog.quantity_lbs))

    now = datetime.now(timezone.utc)
    total_events = GardenEvent.query.filter_by(garden_id=garden_id).count()
    upcoming_events = GardenEvent.query.filter(
        GardenEvent.garden_id == garden_id, GardenEvent.event_date >= now
    ).count()

    sub = GardenSubscription.query.filter_by(garden_id=garden_id).first()

    return jsonify({
        'garden_id': garden.id,
        'name': garden.name,
        'is_active': garden.is_active,
        'plots': {
            'total': total_plots,
            'assigned': assigned,
            'available': available,
            'occupancy_pct': round((assigned / total_plots) * 100, 1) if total_plots else 0,
        },
        'members': GardenMembership.query.filter_by(garden_id=garden_id).count(),
        'finance': {
            'dues_expected': round(dues_expected, 2),
            'dues_collected': round(dues_collected, 2),
            'dues_outstanding': round(dues_expected - dues_collected, 2),
            'collection_rate': round((dues_collected / dues_expected) * 100, 1) if dues_expected else 0,
            'expenses': round(expenses, 2),
            'net_balance': round(dues_collected - expenses, 2),
        },
        'impact': {
            'harvest_lbs': round(harvest_lbs, 1),
            'total_events': total_events,
            'upcoming_events': upcoming_events,
        },
        'subscription': {
            'status': sub.status if sub else 'free',
            'billing_cycle': sub.billing_cycle if sub else None,
            'admin_granted': sub.admin_granted if sub else False,
            'trial_end': sub.trial_end.isoformat() if sub and sub.trial_end else None,
            'current_period_end': sub.current_period_end.isoformat() if sub and sub.current_period_end else None,
        },
    })


@admin_api.route('/gardens/<int:garden_id>/transfer-ownership', methods=['POST'])
@token_or_session
@admin_required
def admin_transfer_garden(garden_id):
    """Reassign a garden's organizer to another user.

    The new owner gets an ``organizer`` membership; the previous organizer is
    demoted to ``co_organizer`` (kept as a member, not locked out).
    """
    garden = db.get_or_404(CommunityGarden, garden_id)
    data = request.get_json() or {}
    try:
        new_owner_id = int(data.get('user_id'))
    except (TypeError, ValueError):
        return jsonify({'error': 'A valid user_id is required'}), 400

    new_owner = db.session.get(User, new_owner_id)
    if not new_owner:
        return jsonify({'error': 'User not found'}), 404
    old_owner_id = garden.organizer_id
    if old_owner_id == new_owner.id:
        return jsonify({'error': 'That user is already the organizer'}), 400

    garden.organizer_id = new_owner.id

    new_mem = GardenMembership.query.filter_by(garden_id=garden_id, user_id=new_owner.id).first()
    if new_mem:
        new_mem.role = 'organizer'
    else:
        db.session.add(GardenMembership(garden_id=garden_id, user_id=new_owner.id, role='organizer'))

    old_mem = GardenMembership.query.filter_by(garden_id=garden_id, user_id=old_owner_id).first()
    if old_mem and old_mem.role == 'organizer':
        old_mem.role = 'co_organizer'

    db.session.commit()
    return jsonify({
        'message': f'Ownership transferred to {new_owner.display_name or new_owner.username}',
        'organizer': {
            'id': new_owner.id,
            'name': new_owner.display_name or new_owner.username,
            'email': new_owner.email,
        },
    })


def _purge_garden(garden):
    """Delete every record that references this garden, in FK-safe order, so the
    garden row itself can then be removed. Backs the admin hard-delete.

    Children that reference a grandchild table (event/shift/photo/plot/resource)
    are removed first; user-owned records (notifications, photo library) are kept
    but unlinked; financial history (refunds, promo usage) is detached from the
    Garden Pro subscription before that subscription row is dropped.
    """
    from app.models import (
        GardenPlot, GardenWaitlist, SharedResource, ResourceCheckoutLog,
        GardenEvent, EventRSVP, HarvestLog, GardenAnnouncement, GardenComment,
        GardenMessage, GardenPhoto, GardenPhotoComment, GardenPhotoLike,
        VolunteerShift, ShiftSignup, GardenDuesRecord, GardenExpense,
        GardenWeatherAlert, PlotAssignmentHistory, GardenKnowledgeArticle,
        GardenEmailConfig, GardenLayoutDraft, Notification, Photo,
        Refund, PromoCodeUsage,
    )
    gid = garden.id

    def _del(q):
        q.delete(synchronize_session=False)

    # 1. Grandchildren — reference an event/shift/photo, no garden_id of their own.
    event_ids = db.session.query(GardenEvent.id).filter_by(garden_id=gid)
    shift_ids = db.session.query(VolunteerShift.id).filter_by(garden_id=gid)
    photo_ids = db.session.query(GardenPhoto.id).filter_by(garden_id=gid)
    _del(EventRSVP.query.filter(EventRSVP.event_id.in_(event_ids)))
    _del(ShiftSignup.query.filter(ShiftSignup.shift_id.in_(shift_ids)))
    _del(GardenPhotoComment.query.filter(GardenPhotoComment.photo_id.in_(photo_ids)))
    _del(GardenPhotoLike.query.filter(GardenPhotoLike.photo_id.in_(photo_ids)))

    # 2. Records that reference a plot/resource — delete before those parents.
    _del(ResourceCheckoutLog.query.filter_by(garden_id=gid))
    _del(PlotAssignmentHistory.query.filter_by(garden_id=gid))

    # 3. Detach financial history from the Garden Pro subscription, then drop it.
    sub = GardenSubscription.query.filter_by(garden_id=gid).first()
    if sub:
        Refund.query.filter_by(garden_subscription_id=sub.id).update(
            {'garden_subscription_id': None}, synchronize_session=False)
        PromoCodeUsage.query.filter_by(garden_subscription_id=sub.id).update(
            {'garden_subscription_id': None}, synchronize_session=False)

    # 4. Direct children keyed by garden_id (knowledge articles: NULL = platform
    #    -wide, so filter_by(garden_id=gid) leaves shared articles untouched).
    for Model in (GardenPlot, GardenWaitlist, SharedResource, GardenEvent,
                  HarvestLog, GardenAnnouncement, GardenComment, GardenMessage,
                  GardenPhoto, VolunteerShift, GardenDuesRecord, GardenExpense,
                  GardenWeatherAlert, GardenMembership, GardenKnowledgeArticle,
                  GardenEmailConfig, GardenLayoutDraft, GardenSubscription):
        _del(Model.query.filter_by(garden_id=gid))

    # 5. User-owned records: keep the row, just unlink the (now-gone) garden.
    Notification.query.filter_by(garden_id=gid).update(
        {'garden_id': None}, synchronize_session=False)
    Photo.query.filter_by(garden_id=gid).update(
        {'garden_id': None}, synchronize_session=False)


@admin_api.route('/gardens/<int:garden_id>', methods=['DELETE'])
@token_or_session
@admin_required
def admin_delete_garden(garden_id):
    """Permanently delete a garden and all of its related records.

    Destructive and irreversible. Requires the garden's exact name echoed back
    as ``{"confirm_name": "..."}`` as a safety interlock.
    """
    garden = db.get_or_404(CommunityGarden, garden_id)
    data = request.get_json(silent=True) or {}
    if (data.get('confirm_name') or '').strip() != garden.name:
        return jsonify({'error': 'confirm_name must exactly match the garden name'}), 400

    name = garden.name
    _purge_garden(garden)
    db.session.delete(garden)
    db.session.commit()
    return jsonify({'message': f'Garden "{name}" and all related records were deleted'})
