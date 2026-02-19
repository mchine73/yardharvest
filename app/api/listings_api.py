"""Listings REST API endpoints."""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Listing, OrderItem, Order
from app.helpers import (
    geocode_address, save_listing_image, haversine_miles,
    VEGETABLE_CATEGORIES, UNIT_CHOICES
)
from app.pricing import get_pricing_config
from datetime import datetime, timezone, timedelta
from sqlalchemy import func

listings_api = Blueprint('listings_api', __name__, url_prefix='/api/listings')


def listing_to_dict(listing, user_lat=None, user_lon=None):
    d = {
        'id': listing.id,
        'seller_id': listing.seller_id,
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
    if user_lat is None and current_user.is_authenticated:
        user_lat = current_user.latitude
        user_lon = current_user.longitude

    # Fetch all eligible listings (active with stock)
    all_listings = Listing.query.filter_by(is_active=True).filter(
        Listing.quantity_available > 0
    ).all()

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


@listings_api.route('/browse', methods=['GET'])
def browse():
    page = request.args.get('page', 1, type=int)
    veg_type = request.args.get('type', '')
    per_page = 12

    q = Listing.query.filter_by(is_active=True).filter(Listing.quantity_available > 0)
    if veg_type:
        q = q.filter_by(vegetable_type=veg_type)

    pagination = q.order_by(Listing.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    user_lat = current_user.latitude if current_user.is_authenticated else None
    user_lon = current_user.longitude if current_user.is_authenticated else None

    return jsonify({
        'listings': [listing_to_dict(l, user_lat, user_lon) for l in pagination.items],
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
        kw = f'%{keyword}%'
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

    listings = q.order_by(Listing.created_at.desc()).all()
    if current_user.is_authenticated:
        user_lat = current_user.latitude
        user_lon = current_user.longitude
    return jsonify({
        'listings': [listing_to_dict(l, user_lat, user_lon) for l in listings],
        'user_lat': user_lat,
        'user_lon': user_lon,
    })


@listings_api.route('/<int:listing_id>', methods=['GET'])
def detail(listing_id):
    listing = Listing.query.get_or_404(listing_id)
    user_lat = current_user.latitude if current_user.is_authenticated else None
    user_lon = current_user.longitude if current_user.is_authenticated else None
    return jsonify(listing_to_dict(listing, user_lat, user_lon))


@listings_api.route('', methods=['POST'])
@login_required
def create():
    if not current_user.can_sell():
        return jsonify({'error': 'Seller account required'}), 403

    # Handle multipart form data for image uploads
    title = request.form.get('title', '')
    description = request.form.get('description', '')
    vegetable_type = request.form.get('vegetable_type', '')
    price = float(request.form.get('price', 0))
    unit = request.form.get('unit', 'each')
    quantity = int(request.form.get('quantity_available', 1))
    delivery = request.form.get('delivery_available', 'false').lower() == 'true'
    radius = float(request.form.get('delivery_radius_miles', 0))
    instructions = request.form.get('pickup_instructions', '')
    use_profile = request.form.get('use_profile_address', 'true').lower() == 'true'

    config = get_pricing_config()
    listing = Listing(
        seller_id=current_user.id,
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
        listing.pickup_address = current_user.address
        listing.pickup_city = current_user.city
        listing.pickup_state = current_user.state
        listing.pickup_zip = current_user.zip_code
        listing.pickup_latitude = current_user.latitude
        listing.pickup_longitude = current_user.longitude
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
@login_required
def update(listing_id):
    listing = Listing.query.get_or_404(listing_id)
    if listing.seller_id != current_user.id:
        return jsonify({'error': 'Not authorized'}), 403

    listing.title = request.form.get('title', listing.title)
    listing.description = request.form.get('description', listing.description)
    listing.vegetable_type = request.form.get('vegetable_type', listing.vegetable_type)
    new_price = float(request.form.get('price', listing.price))
    if new_price != listing.base_price:
        config = get_pricing_config()
        listing.base_price = new_price
        listing.price_floor = round(new_price * config.floor_pct, 2)
        listing.price_ceiling = round(new_price * config.ceiling_pct, 2)
    listing.price = new_price
    listing.unit = request.form.get('unit', listing.unit)
    listing.quantity_available = int(request.form.get('quantity_available', listing.quantity_available))
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
@login_required
def toggle(listing_id):
    listing = Listing.query.get_or_404(listing_id)
    if listing.seller_id != current_user.id:
        return jsonify({'error': 'Not authorized'}), 403
    listing.is_active = not listing.is_active
    db.session.commit()
    return jsonify({'is_active': listing.is_active})


@listings_api.route('/<int:listing_id>', methods=['DELETE'])
@login_required
def delete(listing_id):
    listing = Listing.query.get_or_404(listing_id)
    if listing.seller_id != current_user.id:
        return jsonify({'error': 'Not authorized'}), 403
    listing.is_active = False
    db.session.commit()
    return jsonify({'message': 'Listing removed'})


@listings_api.route('/mine', methods=['GET'])
@login_required
def my_listings():
    if not current_user.can_sell():
        return jsonify({'error': 'Seller account required'}), 403
    listings = Listing.query.filter_by(seller_id=current_user.id).order_by(Listing.created_at.desc()).all()
    return jsonify([listing_to_dict(l) for l in listings])
