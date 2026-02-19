"""Profile & Reviews REST API endpoints."""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import User, Listing, Order, Review
from app.helpers import geocode_address, save_listing_image
from app.api.auth_api import user_to_dict

profile_api = Blueprint('profile_api', __name__, url_prefix='/api/profile')


def review_to_dict(r):
    return {
        'id': r.id,
        'reviewer_id': r.reviewer_id,
        'reviewer_name': r.reviewer.display_name or r.reviewer.username,
        'reviewer_image': r.reviewer.profile_image,
        'seller_id': r.seller_id,
        'order_id': r.order_id,
        'rating': r.rating,
        'comment': r.comment,
        'created_at': r.created_at.isoformat() if r.created_at else None,
    }


@profile_api.route('/<int:user_id>', methods=['GET'])
def public_profile(user_id):
    user = User.query.get_or_404(user_id)
    listings = Listing.query.filter_by(seller_id=user_id, is_active=True).order_by(
        Listing.created_at.desc()).all()
    reviews = Review.query.filter_by(seller_id=user_id).order_by(Review.created_at.desc()).all()

    from app.api.listings_api import listing_to_dict
    return jsonify({
        'user': user_to_dict(user),
        'listings': [listing_to_dict(l) for l in listings],
        'reviews': [review_to_dict(r) for r in reviews],
    })


@profile_api.route('/edit', methods=['PUT'])
@login_required
def edit_profile():
    # Handle multipart for image uploads
    current_user.display_name = request.form.get('display_name', current_user.display_name)
    current_user.bio = request.form.get('bio', current_user.bio)
    current_user.gardening_story = request.form.get('gardening_story', current_user.gardening_story)
    years = request.form.get('years_gardening')
    if years:
        current_user.years_gardening = int(years)

    current_user.address = request.form.get('address', current_user.address)
    current_user.city = request.form.get('city', current_user.city)
    current_user.state = request.form.get('state', current_user.state)
    current_user.zip_code = request.form.get('zip_code', current_user.zip_code)

    lat, lon = geocode_address(
        current_user.address, current_user.city,
        current_user.state, current_user.zip_code
    )
    current_user.latitude = lat
    current_user.longitude = lon

    if 'profile_image' in request.files:
        current_user.profile_image = save_listing_image(request.files['profile_image'])
    if 'gallery_image_1' in request.files:
        current_user.gallery_image_1 = save_listing_image(request.files['gallery_image_1'])
    if 'gallery_image_2' in request.files:
        current_user.gallery_image_2 = save_listing_image(request.files['gallery_image_2'])
    if 'gallery_image_3' in request.files:
        current_user.gallery_image_3 = save_listing_image(request.files['gallery_image_3'])

    db.session.commit()
    return jsonify(user_to_dict(current_user))


@profile_api.route('/dashboard', methods=['GET'])
@login_required
def dashboard():
    if not current_user.can_sell():
        return jsonify({'error': 'Seller account required'}), 403

    active_listings = Listing.query.filter_by(seller_id=current_user.id, is_active=True).count()
    pending_orders = Order.query.filter_by(seller_id=current_user.id, status='pending').count()
    completed_orders = Order.query.filter_by(seller_id=current_user.id, status='completed').count()
    recent_orders = Order.query.filter_by(seller_id=current_user.id).order_by(
        Order.created_at.desc()).limit(5).all()

    from app.api.cart_api import order_to_dict
    return jsonify({
        'active_listings': active_listings,
        'pending_orders': pending_orders,
        'completed_orders': completed_orders,
        'recent_orders': [order_to_dict(o) for o in recent_orders],
    })


@profile_api.route('/reviews/<int:order_id>', methods=['POST'])
@login_required
def leave_review(order_id):
    order = Order.query.get_or_404(order_id)
    if order.buyer_id != current_user.id:
        return jsonify({'error': 'Not authorized'}), 403
    if order.status != 'completed':
        return jsonify({'error': 'Can only review completed orders'}), 400
    if order.review:
        return jsonify({'error': 'Already reviewed'}), 400

    data = request.get_json()
    review = Review(
        reviewer_id=current_user.id,
        seller_id=order.seller_id,
        order_id=order.id,
        rating=data.get('rating', 5),
        comment=data.get('comment', ''),
    )
    db.session.add(review)
    db.session.commit()
    return jsonify(review_to_dict(review)), 201
