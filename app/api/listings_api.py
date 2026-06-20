"""Listings REST API endpoints."""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.api.token_auth import token_or_session, get_current_user
from app import db, limiter
from app.models import Listing, OrderItem, Order, SellerPlanting, User
from sqlalchemy.orm import joinedload
from app.helpers import (
    geocode_address, save_listing_image, haversine_miles,
    VEGETABLE_CATEGORIES, UNIT_CHOICES
)
from app.pricing import get_pricing_config
from datetime import datetime, timezone, timedelta
from sqlalchemy import func

listings_api = Blueprint('listings_api', __name__, url_prefix='/api/listings')

VALID_CATEGORIES = {v for v, _ in VEGETABLE_CATEGORIES}
VALID_UNITS = {v for v, _ in UNIT_CHOICES}


def _validate_listing_fields(title, description, price, quantity, vegetable_type, unit):
    """Validate listing create/update fields. Returns (ok, error_msg)."""
    if not title or len(title) > 150:
        return False, 'Title is required and must be under 150 characters'
    if len(description) > 5000:
        return False, 'Description must be under 5000 characters'
    if price <= 0 or price > 10000:
        return False, 'Price must be between $0.01 and $10,000'
    if quantity < 1 or quantity > 10000:
        return False, 'Quantity must be between 1 and 10,000'
    if vegetable_type and vegetable_type not in VALID_CATEGORIES:
        return False, 'Invalid category'
    if unit and unit not in VALID_UNITS:
        return False, 'Invalid unit'
    return True, ''


def listing_to_dict(listing, user_lat=None, user_lon=None):
    d = {
        'id': listing.id,
        'seller_id': listing.seller_id,
        'seller_public_id': listing.seller.public_id,
        'seller_name': listing.seller.display_name or listing.seller.username,
        'seller_username': listing.seller.username,
        'seller_image': listing.seller.profile_image,
        'seller_rating': listing.seller.avg_rating,
        'seller_review_count': listing.seller.review_count,
        'title': listing.title,
        'description': listing.description,
        'vegetable_type': listing.vegetable_type,
        'price': listing.price,
        'effective_price': listing.effective_price,
        'base_price': listing.base_price,
        'unit': listing.unit,
        'quantity_available': listing.quantity_available,
        'initial_quantity': listing.initial_quantity,
        'image_filename': listing.image_filename,
        'image_filename_2': listing.image_filename_2,
        'image_filename_3': listing.image_filename_3,
        'image_url': listing.image_url,
        'pickup_address': listing.pickup_address,
        'pickup_city': listing.pickup_city,
        'pickup_state': listing.pickup_state,
        'pickup_zip': listing.pickup_zip,
        'pickup_latitude': listing.pickup_latitude,
        'pickup_longitude': listing.pickup_longitude,
        'delivery_available': listing.delivery_available,
        'delivery_radius_miles': listing.delivery_radius_miles,
        'pickup_instructions': listing.pickup_instructions,
        'is_active': listing.is_active,
        'smart_pricing_enabled': listing.smart_pricing_enabled,
        'created_at': listing.created_at.isoformat() if listing.created_at else None,
        'updated_at': listing.updated_at.isoformat() if listing.updated_at else None,
    }
    if user_lat is not None and user_lon is not None and listing.pickup_latitude:
        dist = haversine_miles(user_lat, user_lon, listing.pickup_latitude, listing.pickup_longitude)
        d['distance'] = round(dist, 1)
        d['can_deliver'] = (
            listing.delivery_available and
            listing.delivery_radius_miles and
            dist <= listing.delivery_radius_miles
        )
    return d


@listings_api.route('/categories', methods=['GET'])
def categories():
    return jsonify({
        'categories': [{'value': v, 'label': l} for v, l in VEGETABLE_CATEGORIES],
        'units': [{'value': v, 'label': l} for v, l in UNIT_CHOICES],
    })


@listings_api.route('/featured', methods=['GET'])
def featured():
    """Smart featured listings combining proximity, age, and demand signals."""
    # Accept optional browser geolocation override via query params
    user_lat = request.args.get('lat', type=float)
    user_lon = request.args.get('lon', type=float)

    # Fall back to profile coordinates
    if user_lat is None and get_current_user().is_authenticated:
        user_lat = get_current_user().latitude
        user_lon = get_current_user().longitude

    # Fetch eligible listings (active with stock). Eager-load seller (used by
    # listing_to_dict) and cap the candidate pool — scoring already favors
    # recency, so the newest 500 are the meaningful candidates.
    all_listings = (Listing.query
                    .options(joinedload(Listing.seller))
                    .filter_by(is_active=True)
                    .filter(Listing.quantity_available > 0)
                    .order_by(Listing.created_at.desc())
                    .limit(500).all())

    if not all_listings:
        return jsonify([])

    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)

    # Batch-fetch recent sales velocity for all listing IDs
    listing_ids = [l.id for l in all_listings]
    velocity_data = {}
    try:
        sales_rows = db.session.query(
            OrderItem.listing_id,
            func.coalesce(func.sum(OrderItem.quantity), 0).label('sold')
        ).join(Order).filter(
            OrderItem.listing_id.in_(listing_ids),
            Order.created_at >= seven_days_ago,
            Order.status != 'cancelled',
        ).group_by(OrderItem.listing_id).all()
        for row in sales_rows:
            velocity_data[row.listing_id] = int(row.sold)
    except Exception:
        pass

    # Score each listing
    scored = []
    for listing in all_listings:
        # Factor 1: Proximity (40% weight)
        proximity_score = 0.5  # default for anonymous / no-location users
        if user_lat is not None and user_lon is not None and listing.pickup_latitude:
            dist = haversine_miles(user_lat, user_lon,
                                   listing.pickup_latitude, listing.pickup_longitude)
            # Inverse distance: 0 mi → 1.0, 5 mi → 0.67, 15 mi → 0.4, 50+ mi → ~0.1
            proximity_score = 1.0 / (1.0 + dist / 10.0)

        # Factor 2: Persistence / Age (35% weight)
        # Items that have been listed longer (but still have stock) get boosted
        created = listing.created_at
        if created:
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            days_old = (now - created).total_seconds() / 86400.0
        else:
            days_old = 0
        # 0 days → 0.1, 3 days → 0.5, 7+ days → 0.8-1.0
        persistence_score = min(0.1 + (days_old / 10.0), 1.0)

        # Factor 3: Demand / Velocity (25% weight)
        recent_sales = velocity_data.get(listing.id, 0)
        initial_qty = listing.initial_quantity or listing.quantity_available or 1
        velocity_ratio = recent_sales / max(initial_qty, 1)
        velocity_score = min(velocity_ratio * 2.0, 1.0)  # scale up: 50% sold → 1.0

        # Combined weighted score
        score = (
            proximity_score * 0.40 +
            persistence_score * 0.35 +
            velocity_score * 0.25
        )
        scored.append((score, listing))

    # Sort by score descending, take top 8
    scored.sort(key=lambda x: x[0], reverse=True)
    top = [item[1] for item in scored[:8]]

    return jsonify([listing_to_dict(l, user_lat, user_lon) for l in top])


def _preorder_to_listing_dict(p, user_lat=None, user_lon=None):
    """Convert a SellerPlanting preorder into a listing-like dict for marketplace display."""
    from app.api.planting_api import PLANTING_TO_LISTING_CATEGORY
    seller = db.session.get(User, p.seller_id)
    distance = None
    if user_lat and user_lon and seller and seller.latitude and seller.longitude:
        distance = round(haversine_miles(user_lat, user_lon, seller.latitude, seller.longitude), 1)
    return {
        'id': f'preorder-{p.id}',
        'planting_id': p.id,
        'is_preorder': True,
        'title': f'{p.variety or p.category} (Pre-Order)',
        'vegetable_type': PLANTING_TO_LISTING_CATEGORY.get(p.category, p.category),
        'price': p.sale_price,
        'effective_price': p.sale_price,
        'base_price': p.sale_price,
        'unit': p.price_unit or 'lb',
        'quantity_available': int(p.weight_lbs) if p.weight_lbs else None,
        'seller_id': p.seller_id,
        'seller_name': seller.display_name or seller.username if seller else 'Grower',
        'distance': distance,
        'estimated_harvest_start': p.estimated_harvest_start.isoformat() if p.estimated_harvest_start else None,
        'estimated_harvest_end': p.estimated_harvest_end.isoformat() if p.estimated_harvest_end else None,
        'description': f"Pre-order: {p.variety or p.category}. Expected harvest: {p.estimated_harvest_start}",
        'image_url': None,
        'image_filename': None,
        'created_at': p.created_at.isoformat() if p.created_at else None,
    }


def _get_active_preorders(veg_type=None, keyword=None):
    """Query active preorders, optionally filtered by category or keyword."""
    from datetime import date as dt_date
    today = dt_date.today()
    q = SellerPlanting.query.filter(
        SellerPlanting.allow_preorder == True,
        SellerPlanting.status.in_(['planted', 'growing']),
        SellerPlanting.estimated_harvest_start != None,
        SellerPlanting.estimated_harvest_start >= today,
    )
    if veg_type:
        from app.api.planting_api import PLANTING_TO_LISTING_CATEGORY
        matching_cats = [k for k, v in PLANTING_TO_LISTING_CATEGORY.items() if v == veg_type]
        if matching_cats:
            q = q.filter(SellerPlanting.category.in_(matching_cats))
    if keyword:
        kw = f'%{keyword}%'
        q = q.filter(
            (SellerPlanting.category.ilike(kw)) | (SellerPlanting.variety.ilike(kw))
        )
    return q.order_by(SellerPlanting.estimated_harvest_start).all()


@listings_api.route('/browse', methods=['GET'])
def browse():
    page = request.args.get('page', 1, type=int)
    veg_type = request.args.get('type', '')
    preorder_only = request.args.get('preorder_only', '').lower() == 'true'
    per_page = 12

    user_lat = get_current_user().latitude if get_current_user().is_authenticated else None
    user_lon = get_current_user().longitude if get_current_user().is_authenticated else None

    # Get preorders
    preorders_raw = _get_active_preorders(veg_type=veg_type)
    preorder_dicts = [_preorder_to_listing_dict(p, user_lat, user_lon) for p in preorders_raw]

    if preorder_only:
        # Only return preorders, paginated
        start = (page - 1) * per_page
        end = start + per_page
        page_items = preorder_dicts[start:end]
        return jsonify({
            'listings': page_items,
            'total': len(preorder_dicts),
            'pages': max(1, -(-len(preorder_dicts) // per_page)),
            'page': page,
            'has_next': end < len(preorder_dicts),
            'has_prev': page > 1,
            'preorder_count': len(preorder_dicts),
        })

    q = Listing.query.options(joinedload(Listing.seller)).filter_by(is_active=True).filter(Listing.quantity_available > 0)
    if veg_type:
        q = q.filter_by(vegetable_type=veg_type)

    pagination = q.order_by(Listing.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'listings': [listing_to_dict(l, user_lat, user_lon) for l in pagination.items],
        'preorders': preorder_dicts if page == 1 else [],  # Only show preorders on page 1
        'preorder_count': len(preorder_dicts),
        'total': pagination.total,
        'pages': pagination.pages,
        'page': pagination.page,
        'has_next': pagination.has_next,
        'has_prev': pagination.has_prev,
    })


@listings_api.route('/search', methods=['GET'])
def search():
    from app.helpers import get_nearby_listings
    keyword = request.args.get('keyword', '')
    veg_type = request.args.get('vegetable_type', '')
    location = request.args.get('location', '')
    radius = request.args.get('radius', 10, type=float)
    max_price = request.args.get('max_price', type=float)
    delivery_only = request.args.get('delivery_only', '').lower() == 'true'

    q = Listing.query.filter_by(is_active=True).filter(Listing.quantity_available > 0)
    if keyword:
        # Escape SQL LIKE wildcards in user input
        keyword_escaped = keyword.replace('%', r'\%').replace('_', r'\_')
        kw = f'%{keyword_escaped}%'
        q = q.filter((Listing.title.ilike(kw)) | (Listing.description.ilike(kw)))
    if veg_type:
        q = q.filter_by(vegetable_type=veg_type)
    if max_price:
        q = q.filter(Listing.price <= max_price)
    if delivery_only:
        q = q.filter_by(delivery_available=True)

    user_lat, user_lon = None, None
    if location:
        lat, lon = geocode_address(None, location, '', '')
        if lat and lon:
            user_lat, user_lon = lat, lon
            nearby = get_nearby_listings(lat, lon, radius)
            if keyword or veg_type or max_price or delivery_only:
                ids = {l.id for l in q.all()}
                nearby = [l for l in nearby if l.id in ids]
            return jsonify({
                'listings': [listing_to_dict(l, user_lat, user_lon) for l in nearby],
                'user_lat': user_lat,
                'user_lon': user_lon,
            })

    listings = q.options(joinedload(Listing.seller)).order_by(Listing.created_at.desc()).all()
    if get_current_user().is_authenticated:
        user_lat = get_current_user().latitude
        user_lon = get_current_user().longitude

    # Include preorders in search results
    preorders_raw = _get_active_preorders(veg_type=veg_type, keyword=keyword)
    preorder_dicts = [_preorder_to_listing_dict(p, user_lat, user_lon) for p in preorders_raw]

    return jsonify({
        'listings': [listing_to_dict(l, user_lat, user_lon) for l in listings],
        'preorders': preorder_dicts,
        'preorder_count': len(preorder_dicts),
        'user_lat': user_lat,
        'user_lon': user_lon,
    })


@listings_api.route('/<int:listing_id>', methods=['GET'])
def detail(listing_id):
    listing = db.get_or_404(Listing, listing_id)
    # Hide inactive listings unless the owner is viewing
    current = get_current_user()
    if not listing.is_active and (not current.is_authenticated or current.id != listing.seller_id):
        return jsonify({'error': 'Listing not found'}), 404
    user_lat = current.latitude if current.is_authenticated else None
    user_lon = current.longitude if current.is_authenticated else None
    return jsonify(listing_to_dict(listing, user_lat, user_lon))


@listings_api.route('', methods=['POST'])
@token_or_session
@limiter.limit("10 per minute")
def create():
    if not get_current_user().can_sell():
        return jsonify({'error': 'Seller account required'}), 403

    # Handle multipart form data for image uploads
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    vegetable_type = request.form.get('vegetable_type', '')
    try:
        price = float(request.form.get('price', 0))
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid price'}), 400
    unit = request.form.get('unit', 'each')
    try:
        quantity = int(request.form.get('quantity_available', 1))
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid quantity'}), 400
    delivery = request.form.get('delivery_available', 'false').lower() == 'true'
    radius = float(request.form.get('delivery_radius_miles', 0))
    instructions = request.form.get('pickup_instructions', '')
    use_profile = request.form.get('use_profile_address', 'true').lower() == 'true'

    # H7: Input validation
    ok, msg = _validate_listing_fields(title, description, price, quantity, vegetable_type, unit)
    if not ok:
        return jsonify({'error': msg}), 400

    config = get_pricing_config()
    listing = Listing(
        seller_id=get_current_user().id,
        title=title,
        description=description,
        vegetable_type=vegetable_type,
        price=price,
        base_price=price,
        initial_quantity=quantity,
        price_floor=round(price * config.floor_pct, 2),
        price_ceiling=round(price * config.ceiling_pct, 2),
        smart_pricing_enabled=True,
        unit=unit,
        quantity_available=quantity,
        delivery_available=delivery,
        delivery_radius_miles=radius,
        pickup_instructions=instructions,
    )

    if use_profile:
        listing.pickup_address = get_current_user().address
        listing.pickup_city = get_current_user().city
        listing.pickup_state = get_current_user().state
        listing.pickup_zip = get_current_user().zip_code
        listing.pickup_latitude = get_current_user().latitude
        listing.pickup_longitude = get_current_user().longitude
    else:
        listing.pickup_address = request.form.get('pickup_address', '')
        listing.pickup_city = request.form.get('pickup_city', '')
        listing.pickup_state = request.form.get('pickup_state', '')
        listing.pickup_zip = request.form.get('pickup_zip', '')
        lat, lon = geocode_address(
            listing.pickup_address, listing.pickup_city,
            listing.pickup_state, listing.pickup_zip
        )
        listing.pickup_latitude = lat
        listing.pickup_longitude = lon

    if 'image' in request.files:
        listing.image_filename = save_listing_image(request.files['image'])
    if 'image_2' in request.files:
        listing.image_filename_2 = save_listing_image(request.files['image_2'])
    if 'image_3' in request.files:
        listing.image_filename_3 = save_listing_image(request.files['image_3'])

    db.session.add(listing)
    db.session.commit()
    return jsonify(listing_to_dict(listing)), 201


@listings_api.route('/<int:listing_id>', methods=['PUT'])
@token_or_session
def update(listing_id):
    listing = db.get_or_404(Listing, listing_id)
    if listing.seller_id != get_current_user().id:
        return jsonify({'error': 'Not authorized'}), 403

    title = request.form.get('title', listing.title).strip()
    description = request.form.get('description', listing.description).strip()
    vegetable_type = request.form.get('vegetable_type', listing.vegetable_type)
    try:
        new_price = float(request.form.get('price', listing.price))
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid price'}), 400
    unit = request.form.get('unit', listing.unit)
    try:
        new_quantity = int(request.form.get('quantity_available', listing.quantity_available))
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid quantity'}), 400

    # H7: Input validation
    ok, msg = _validate_listing_fields(title, description, new_price, new_quantity, vegetable_type, unit)
    if not ok:
        return jsonify({'error': msg}), 400

    listing.title = title
    listing.description = description
    listing.vegetable_type = vegetable_type
    if new_price != listing.base_price:
        config = get_pricing_config()
        listing.base_price = new_price
        listing.price_floor = round(new_price * config.floor_pct, 2)
        listing.price_ceiling = round(new_price * config.ceiling_pct, 2)
    listing.price = new_price
    listing.unit = unit
    listing.quantity_available = new_quantity
    listing.delivery_available = request.form.get('delivery_available', 'false').lower() == 'true'
    listing.delivery_radius_miles = float(request.form.get('delivery_radius_miles', listing.delivery_radius_miles))
    listing.pickup_instructions = request.form.get('pickup_instructions', listing.pickup_instructions)

    if 'image' in request.files:
        listing.image_filename = save_listing_image(request.files['image'])
    if 'image_2' in request.files:
        listing.image_filename_2 = save_listing_image(request.files['image_2'])
    if 'image_3' in request.files:
        listing.image_filename_3 = save_listing_image(request.files['image_3'])

    db.session.commit()
    return jsonify(listing_to_dict(listing))


@listings_api.route('/<int:listing_id>/toggle', methods=['POST'])
@token_or_session
def toggle(listing_id):
    listing = db.get_or_404(Listing, listing_id)
    if listing.seller_id != get_current_user().id:
        return jsonify({'error': 'Not authorized'}), 403
    listing.is_active = not listing.is_active
    db.session.commit()
    return jsonify({'is_active': listing.is_active})


@listings_api.route('/<int:listing_id>', methods=['DELETE'])
@token_or_session
def delete(listing_id):
    listing = db.get_or_404(Listing, listing_id)
    if listing.seller_id != get_current_user().id:
        return jsonify({'error': 'Not authorized'}), 403
    listing.is_active = False
    db.session.commit()
    return jsonify({'message': 'Listing removed'})


@listings_api.route('/mine', methods=['GET'])
@token_or_session
def my_listings():
    if not get_current_user().can_sell():
        return jsonify({'error': 'Seller account required'}), 403
    listings = Listing.query.filter_by(seller_id=get_current_user().id).order_by(Listing.created_at.desc()).all()
    return jsonify([listing_to_dict(l) for l in listings])
