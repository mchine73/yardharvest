"""Dynamic pricing algorithm for YardHarvest listings."""
from datetime import datetime, timezone, timedelta


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
