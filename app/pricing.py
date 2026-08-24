"""Dynamic pricing algorithm for YardHarvest listings."""
import logging
import os
from datetime import datetime, timezone, timedelta

log = logging.getLogger(__name__)


def get_pricing_config():
    """Get the singleton PricingConfig row, creating defaults if missing."""
    from app import db
    from app.models import PricingConfig
    config = PricingConfig.query.first()
    if not config:
        config = PricingConfig()
        db.session.add(config)
        db.session.commit()
    return config


def dues_fee_percent():
    """The platform's cut of a garden collection, as a percentage.

    One resolver for all three collection channels — online dues, in-person
    dues, and ad-hoc Tap-to-Pay sales. They each used to read the config
    themselves, and only the online path honored the legacy
    ``GARDEN_DUES_FEE_PERCENT`` env var, so a deployment with that variable
    set charged a platform fee on web payments and silently waived it on
    every in-person collection. Same money, same garden, different answer
    depending on which button someone pressed.

    Returns 0.0 (charge no fee) rather than raising, on any failure: a
    misconfigured fee must never be the reason a manager can't take money.
    """
    value = 0.0
    try:
        value = float(getattr(get_pricing_config(), 'garden_dues_fee_percent', 0) or 0)
    except Exception:  # no app context, no DB, bad column value
        log.exception('Could not read garden_dues_fee_percent; assuming 0')

    if not value:
        # Back-compat: the env var this column replaced.
        try:
            from flask import current_app
            value = float(current_app.config.get('GARDEN_DUES_FEE_PERCENT', 0) or 0)
        except Exception:
            try:
                value = float(os.environ.get('GARDEN_DUES_FEE_PERCENT', 0) or 0)
            except (TypeError, ValueError):
                value = 0.0

    if value < 0 or value > 100:
        log.warning('garden dues fee of %s%% is out of range; charging none', value)
        return 0.0
    return value


def dues_fee_cents(amount_cents):
    """Stripe ``application_fee_amount`` for a collection of this size.

    Returns ``None`` when no fee applies, which is what the Stripe API wants —
    passing 0 would create a zero-value ApplicationFee object on every charge.
    """
    pct = dues_fee_percent()
    if not pct or not amount_cents:
        return None
    return int(round(int(amount_cents) * pct / 100))


# The Garden Pro fields that every surface must agree on. The fallbacks live
# on the model columns, so there is exactly one place a default is written
# down — not one per email, endpoint and template.
_GARDEN_PRO_FIELDS = ('garden_pro_enabled', 'garden_pro_trial_days',
                      'garden_pro_monthly_cents', 'garden_pro_yearly_cents')


_GARDEN_PRO_DEFAULTS = {}


def _column_defaults():
    """The PricingConfig columns' own defaults, for when no row exists yet.

    Read from the model once and cached: table metadata needs no database, so
    the fallback stays available even when the query below cannot run.
    """
    if not _GARDEN_PRO_DEFAULTS:
        from app.models import PricingConfig
        columns = PricingConfig.__table__.columns
        for name in _GARDEN_PRO_FIELDS:
            column = columns[name]
            _GARDEN_PRO_DEFAULTS[name] = column.default.arg if column.default is not None else None
    return _GARDEN_PRO_DEFAULTS


def garden_pro_pricing():
    """Garden Pro price, trial length and availability.

    The one resolver every surface reads — billing, the payment modal, the
    public pricing page, trial emails, outreach copy and the structured data
    search engines index. Whatever the admin console holds is what everyone
    quotes; nothing re-states a price in a template, an email or config.py,
    because a second copy is a copy that eventually disagrees. It did: the
    marketing site's schema.org offers said $15/$125 from config.py while the
    console charged something else.

    Read-only and never raises — a missing row or an unavailable database
    falls back to the model's column defaults rather than breaking a page.
    """
    row = None
    try:
        from app.models import PricingConfig
        row = PricingConfig.query.first()
    except Exception:      # noqa: BLE001 — pricing must never break a render
        row = None

    defaults = _column_defaults()

    def value(name):
        found = getattr(row, name, None) if row is not None else None
        return defaults[name] if found is None else found

    enabled, trial_days, monthly_cents, yearly_cents = (value(f) for f in _GARDEN_PRO_FIELDS)
    return {
        'enabled': bool(enabled),
        'trial_days': int(trial_days),
        'monthly_cents': int(monthly_cents),
        'yearly_cents': int(yearly_cents),
        'monthly': int(monthly_cents) / 100,
        'yearly': int(yearly_cents) / 100,
    }


def calculate_smart_price(listing):
    """
    Calculate dynamic price based on supply, velocity, and time decay.

    Supply factor: low stock -> price up, full stock -> price slightly down
    Velocity factor: fast recent sales -> price up
    Time decay: old listings with stock -> price down

    Formula: smart_price = base_price * (1 + weighted_adjustment * global_multiplier)
    Clamped between price_floor and price_ceiling.
    """
    from app import db
    from app.models import OrderItem, Order

    config = get_pricing_config()

    base = listing.base_price or listing.price
    if not base:
        return listing.price or 0

    # If pricing disabled globally or per-listing, return base
    if not config.enabled or not listing.smart_pricing_enabled:
        return base

    initial_qty = listing.initial_quantity or listing.quantity_available or 1
    current_qty = listing.quantity_available or 0
    floor_price = listing.price_floor or (base * config.floor_pct)
    ceil_price = listing.price_ceiling or (base * config.ceiling_pct)

    # Factor 1: Supply Ratio
    # ratio=0 (sold out) -> factor=+1.0, ratio=0.5 -> factor=0.0, ratio=1.0 -> factor=-0.3
    if initial_qty > 0:
        supply_ratio = current_qty / initial_qty
    else:
        supply_ratio = 1.0
    supply_factor = 1.0 - (supply_ratio * 1.3)
    supply_factor = max(-0.3, min(1.0, supply_factor))

    # Factor 2: Sales Velocity (orders in last 7 days)
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    try:
        recent_sales = db.session.query(
            db.func.coalesce(db.func.sum(OrderItem.quantity), 0)
        ).join(Order).filter(
            OrderItem.listing_id == listing.id,
            Order.created_at >= seven_days_ago,
            Order.status != 'cancelled'
        ).scalar() or 0
    except Exception:
        recent_sales = 0

    if initial_qty > 0:
        velocity_ratio = recent_sales / initial_qty
    else:
        velocity_ratio = 0
    velocity_factor = min(1.0, velocity_ratio)

    # Factor 3: Time Decay
    if listing.created_at:
        created = listing.created_at
        now = datetime.now(timezone.utc)
        # Handle naive datetimes from SQLite
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        days_listed = (now - created).days
    else:
        days_listed = 0
    if days_listed <= 2:
        time_decay_factor = 0.0
    else:
        age_factor = min(days_listed / 30.0, 1.0)
        time_decay_factor = -0.3 * age_factor * supply_ratio

    # Combine with weights
    adjustment = (
        supply_factor * config.supply_weight +
        velocity_factor * config.velocity_weight +
        time_decay_factor * config.time_decay_weight
    ) * config.global_multiplier

    smart_price = base * (1.0 + adjustment)
    smart_price = max(floor_price, min(ceil_price, smart_price))

    return round(smart_price, 2)


def calculate_order_fees(subtotal, fulfillment_method,
                         buyer_lat=None, buyer_lon=None,
                         seller_lat=None, seller_lon=None):
    """Calculate platform commission and delivery fee for an order.

    Respects on/off switches in PricingConfig:
      - commission_enabled: master toggle for platform commission
      - delivery_fees_enabled: master toggle for delivery charges
      - per_mile_enabled: toggle for distance-based surcharge
      - free_delivery_enabled: toggle for free delivery threshold

    Returns dict with commission, commission_rate, delivery_fee,
    total (buyer pays), and seller_earnings.
    """
    config = get_pricing_config()

    # ── Commission ──
    if config.commission_enabled:
        commission_rate = config.platform_commission_pct or 0
        commission = round(subtotal * commission_rate, 2)
    else:
        commission_rate = 0
        commission = 0

    # ── Delivery Fee ──
    delivery_fee = 0.0
    if fulfillment_method == 'delivery' and config.delivery_fees_enabled:
        # Check free-delivery threshold (only if that sub-feature is on)
        if config.free_delivery_enabled:
            threshold = config.delivery_fee_free_threshold or 0
            if threshold > 0 and subtotal >= threshold:
                delivery_fee = 0.0
                # Skip all further delivery fee calc — it's free
                total = round(subtotal + delivery_fee, 2)
                seller_net = round(subtotal - commission, 2)
                return {
                    'commission': commission,
                    'commission_rate': commission_rate,
                    'delivery_fee': 0.0,
                    'total': total,
                    'seller_earnings': seller_net,
                }

        # Flat delivery fee
        delivery_fee = config.delivery_fee_flat or 0

        # Per-mile surcharge (only if that sub-feature is on)
        if config.per_mile_enabled:
            per_mile = config.delivery_fee_per_mile or 0
            if per_mile > 0 and buyer_lat and seller_lat:
                from app.helpers import haversine_miles
                dist = haversine_miles(buyer_lat, buyer_lon,
                                       seller_lat, seller_lon)
                delivery_fee += round(dist * per_mile, 2)

    # ── DoorDash Subsidy ──
    doordash_subsidy = 0.0
    if fulfillment_method == 'delivery' and getattr(config, 'doordash_enabled', False):
        subsidy_pct = getattr(config, 'doordash_subsidy_pct', 0) or 0
        max_subsidy = getattr(config, 'doordash_max_subsidy', 5.0) or 5.0
        if subsidy_pct > 0 and delivery_fee > 0:
            doordash_subsidy = min(delivery_fee * subsidy_pct, max_subsidy)
            delivery_fee = round(delivery_fee - doordash_subsidy, 2)
            delivery_fee = max(0, delivery_fee)

    total = round(subtotal + delivery_fee, 2)
    seller_net = round(subtotal - commission, 2)

    return {
        'commission': commission,
        'commission_rate': commission_rate,
        'delivery_fee': round(delivery_fee, 2),
        'doordash_subsidy': round(doordash_subsidy, 2),
        'total': total,
        'seller_earnings': seller_net,
    }


def get_category_stats():
    """Get pricing stats per vegetable category for admin dashboard."""
    from app import db
    from app.models import Listing
    from sqlalchemy import func

    stats = db.session.query(
        Listing.vegetable_type,
        func.count(Listing.id).label('count'),
        func.avg(Listing.price).label('avg_price'),
        func.avg(Listing.base_price).label('avg_base_price'),
        func.min(Listing.price).label('min_price'),
        func.max(Listing.price).label('max_price'),
    ).filter(
        Listing.is_active == True,
        Listing.quantity_available > 0
    ).group_by(Listing.vegetable_type).all()

    return stats
