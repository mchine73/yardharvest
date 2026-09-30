"""Profile & Reviews REST API endpoints."""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.api.token_auth import token_or_session, get_current_user
from app import db
from app.models import User, Listing, Order, Review
from sqlalchemy.orm import joinedload
from app.helpers import geocode_address, save_listing_image
from app.api.auth_api import user_to_dict, public_user_to_dict

profile_api = Blueprint('profile_api', __name__, url_prefix='/api/profile')


@profile_api.url_value_preprocessor
def _resolve_user_url_value(endpoint, values):
    """Resolve an opaque ``usr_…`` public_id (or numeric PK) in the URL to the
    integer ``user_id`` before any handler runs (public profile pages)."""
    if values and 'user_id' in values:
        from app.helpers import resolve_user_pk
        values['user_id'] = resolve_user_pk(values['user_id'])


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


@profile_api.route('/<user_id>', methods=['GET'])
def public_profile(user_id):
    user = db.get_or_404(User, user_id)
    listings = Listing.query.options(joinedload(Listing.seller)).filter_by(
        seller_id=user_id, is_active=True).order_by(Listing.created_at.desc()).all()
    reviews = Review.query.options(joinedload(Review.reviewer)).filter_by(
        seller_id=user_id).order_by(Review.created_at.desc()).all()

    from app.api.listings_api import listing_to_dict
    return jsonify({
        'user': public_user_to_dict(user),
        'listings': [listing_to_dict(l) for l in listings],
        'reviews': [review_to_dict(r) for r in reviews],
    })


@profile_api.route('/edit', methods=['PUT'])
@token_or_session
def edit_profile():
    # Validate image file sizes (4MB per file)
    MAX_IMAGE_SIZE = 4 * 1024 * 1024
    for field in ['profile_image', 'gallery_image_1', 'gallery_image_2', 'gallery_image_3']:
        if field in request.files:
            f = request.files[field]
            f.seek(0, 2)
            size = f.tell()
            f.seek(0)
            if size > MAX_IMAGE_SIZE:
                return jsonify({'error': f'Image too large ({size // (1024*1024)}MB). Maximum is 4MB per image.'}), 400

    # Handle multipart for image uploads
    get_current_user().display_name = request.form.get('display_name', get_current_user().display_name)
    get_current_user().bio = request.form.get('bio', get_current_user().bio)
    get_current_user().gardening_story = request.form.get('gardening_story', get_current_user().gardening_story)
    years = request.form.get('years_gardening')
    if years:
        get_current_user().years_gardening = int(years)

    get_current_user().address = request.form.get('address', get_current_user().address)
    get_current_user().city = request.form.get('city', get_current_user().city)
    get_current_user().state = request.form.get('state', get_current_user().state)
    get_current_user().zip_code = request.form.get('zip_code', get_current_user().zip_code)

    # SMS fields
    phone = request.form.get('phone_number')
    if phone is not None:
        from app.sms_service import normalize_phone
        if phone.strip():
            normalized = normalize_phone(phone)
            if not normalized:
                return jsonify({'error': 'Enter a phone number we can text — 10 digits for a US number, or a + and country code for anywhere else.'}), 400
            get_current_user().phone_number = normalized
        else:
            get_current_user().phone_number = ''
    sms_opt = request.form.get('sms_opt_in')
    if sms_opt is not None:
        get_current_user().sms_opt_in = sms_opt.lower() in ('true', '1', 'on', 'yes')

    lat, lon = geocode_address(
        get_current_user().address, get_current_user().city,
        get_current_user().state, get_current_user().zip_code
    )
    get_current_user().latitude = lat
    get_current_user().longitude = lon

    if 'profile_image' in request.files:
        get_current_user().profile_image = save_listing_image(request.files['profile_image'])
    if 'gallery_image_1' in request.files:
        get_current_user().gallery_image_1 = save_listing_image(request.files['gallery_image_1'])
    if 'gallery_image_2' in request.files:
        get_current_user().gallery_image_2 = save_listing_image(request.files['gallery_image_2'])
    if 'gallery_image_3' in request.files:
        get_current_user().gallery_image_3 = save_listing_image(request.files['gallery_image_3'])

    db.session.commit()
    return jsonify(user_to_dict(get_current_user()))


@profile_api.route('/dashboard', methods=['GET'])
@token_or_session
def dashboard():
    if not get_current_user().can_sell():
        return jsonify({'error': 'Seller account required'}), 403

    active_listings = Listing.query.filter_by(seller_id=get_current_user().id, is_active=True).count()
    pending_orders = Order.query.filter_by(seller_id=get_current_user().id, status='pending').count()
    completed_orders = Order.query.filter_by(seller_id=get_current_user().id, status='completed').count()
    recent_orders = Order.query.filter_by(seller_id=get_current_user().id).order_by(
        Order.created_at.desc()).limit(5).all()

    from app.api.cart_api import order_to_dict
    return jsonify({
        'active_listings': active_listings,
        'pending_orders': pending_orders,
        'completed_orders': completed_orders,
        'recent_orders': [order_to_dict(o) for o in recent_orders],
    })


@profile_api.route('/reviews/<int:order_id>', methods=['POST'])
@token_or_session
def leave_review(order_id):
    order = db.get_or_404(Order, order_id)
    if order.buyer_id != get_current_user().id:
        return jsonify({'error': 'Not authorized'}), 403
    if order.status != 'completed':
        return jsonify({'error': 'Can only review completed orders'}), 400
    if order.review:
        return jsonify({'error': 'Already reviewed'}), 400

    data = request.get_json()
    rating = data.get('rating', 5)
    if not isinstance(rating, int) or rating < 1 or rating > 5:
        return jsonify({'error': 'Rating must be between 1 and 5'}), 400
    review = Review(
        reviewer_id=get_current_user().id,
        seller_id=order.seller_id,
        order_id=order.id,
        rating=rating,
        comment=data.get('comment', '')[:1000],
    )
    db.session.add(review)
    db.session.commit()
    return jsonify(review_to_dict(review)), 201


# ===================================================================
#  BLOCKING — a member choosing not to see another member
# ===================================================================
#  Blocking is one-directional and affects only the blocker's own view:
#  the blocked member's wall posts and replies stop appearing for them.
#  The blocked member is never told. Removing someone's content for
#  everyone is a moderation decision and stays with the organizer.

def _blocked_user_to_dict(b):
    u = b.blocked
    return {
        'user_id': b.blocked_id,
        'name': (u.display_name or u.username) if u else 'Member',
        'image': u.profile_image if u else None,
        'blocked_at': b.created_at.isoformat() if b.created_at else None,
    }


@profile_api.route('/blocks', methods=['GET'])
@token_or_session
def list_blocks():
    """Everyone the signed-in member has blocked, newest first."""
    from app.models import UserBlock
    rows = (UserBlock.query
            .options(joinedload(UserBlock.blocked))
            .filter_by(blocker_id=get_current_user().id)
            .order_by(UserBlock.created_at.desc()).all())
    return jsonify([_blocked_user_to_dict(b) for b in rows])


@profile_api.route('/blocks', methods=['POST'])
@token_or_session
def create_block():
    """Block a member. Blocking someone already blocked reports success."""
    from app.models import UserBlock
    me = get_current_user()
    data = request.get_json() or {}
    raw = data.get('user_id')
    if raw is None:
        return jsonify({'error': 'user_id is required'}), 400
    from app.helpers import resolve_user_pk
    try:
        target_id = resolve_user_pk(raw)
    except Exception:
        return jsonify({'error': 'No such member'}), 404
    if not target_id or int(target_id) == me.id:
        return jsonify({'error': 'You cannot block yourself.'}), 400
    target = db.session.get(User, int(target_id))
    if not target:
        return jsonify({'error': 'No such member'}), 404

    existing = UserBlock.query.filter_by(blocker_id=me.id,
                                         blocked_id=target.id).first()
    if not existing:
        db.session.add(UserBlock(blocker_id=me.id, blocked_id=target.id))
        db.session.commit()
    return jsonify({'success': True, 'user_id': target.id,
                    'name': target.display_name or target.username}), 201


@profile_api.route('/blocks/<user_id>', methods=['DELETE'])
@token_or_session
def delete_block(user_id):
    """Unblock a member. The url_value_preprocessor above has already turned
    an opaque ``usr_…`` id into the integer primary key."""
    from app.models import UserBlock
    row = UserBlock.query.filter_by(blocker_id=get_current_user().id,
                                    blocked_id=user_id).first()
    if row:
        db.session.delete(row)
        db.session.commit()
    return jsonify({'success': True})
