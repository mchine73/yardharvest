"""Auth REST API endpoints."""
import re
from flask import Blueprint, request, jsonify, session
from flask_login import login_user, logout_user, login_required, current_user
from app import db, limiter
from app.models import User
from app.helpers import geocode_address
from app.api.token_auth import generate_tokens, decode_token, token_or_session, get_current_user

auth_api = Blueprint('auth_api', __name__, url_prefix='/api/auth')


def validate_password(password):
    """Enforce minimum password strength.

    Returns (ok: bool, message: str).
    """
    if len(password) < 8:
        return False, 'Password must be at least 8 characters'
    if not re.search(r'[A-Z]', password):
        return False, 'Password must contain at least one uppercase letter'
    if not re.search(r'[a-z]', password):
        return False, 'Password must contain at least one lowercase letter'
    if not re.search(r'[0-9]', password):
        return False, 'Password must contain at least one number'
    return True, ''


@auth_api.route('/me', methods=['GET'])
def me():
    # Support both session (web) and token (mobile) auth
    user = get_current_user()
    if user:
        return jsonify(user_to_dict(user))
    return jsonify(None)


@auth_api.route('/register', methods=['POST'])
@limiter.limit("3 per minute")
def register():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Validate required fields
    for field in ['username', 'email', 'password', 'role']:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 400

    # H6: Password strength validation
    ok, msg = validate_password(data['password'])
    if not ok:
        return jsonify({'error': msg}), 400

    # H9: Generic email error to prevent account enumeration
    # (Usernames are public via profiles, so specific error is OK there)
    if User.query.filter_by(email=data['email'].lower()).first():
        return jsonify({'error': 'Unable to create account with this email'}), 409
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Username already taken'}), 409

    user = User(
        username=data['username'],
        email=data['email'].lower(),
        role=data['role'],
        display_name=data.get('display_name', data['username']),
        address=data.get('address', ''),
        city=data.get('city', ''),
        state=data.get('state', ''),
        zip_code=data.get('zip_code', ''),
    )
    user.set_password(data['password'])

    lat, lon = geocode_address(
        data.get('address', ''), data.get('city', ''),
        data.get('state', ''), data.get('zip_code', '')
    )
    user.latitude = lat
    user.longitude = lon

    db.session.add(user)
    db.session.commit()
    login_user(user)
    return jsonify(user_to_dict(user)), 201


@auth_api.route('/login', methods=['POST'])
@limiter.limit("5 per minute")
def login():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    user = User.query.filter_by(email=data.get('email', '').lower()).first()
    if user and user.check_password(data.get('password', '')):
        login_user(user)
        return jsonify(user_to_dict(user))
    return jsonify({'error': 'Invalid email or password'}), 401


@auth_api.route('/logout', methods=['POST'])
@token_or_session
def logout():
    logout_user()
    return jsonify({'message': 'Logged out'})


def user_to_dict(user):
    return {
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'role': user.role,
        'display_name': user.display_name,
        'bio': user.bio,
        'address': user.address,
        'city': user.city,
        'state': user.state,
        'zip_code': user.zip_code,
        'latitude': user.latitude,
        'longitude': user.longitude,
        'profile_image': user.profile_image,
        'gardening_story': user.gardening_story,
        'years_gardening': user.years_gardening,
        'gallery_image_1': user.gallery_image_1,
        'gallery_image_2': user.gallery_image_2,
        'gallery_image_3': user.gallery_image_3,
        'is_admin': user.is_admin,
        'is_active_user': user.is_active_user,
        'avg_rating': user.avg_rating,
        'review_count': user.review_count,
        'can_sell': user.can_sell(),
        'can_buy': user.can_buy(),
        'phone_number': user.phone_number or '',
        'sms_opt_in': bool(user.sms_opt_in),
        'created_at': user.created_at.isoformat() if user.created_at else None,
    }


# ---------- Mobile Token Auth Endpoints (JWT) ----------

@auth_api.route('/token', methods=['POST'])
@limiter.limit("5 per minute")
def token_login():
    """Exchange email+password for JWT access and refresh tokens (mobile)."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    user = User.query.filter_by(email=data.get('email', '').lower()).first()
    if not user or not user.check_password(data.get('password', '')):
        return jsonify({'error': 'Invalid email or password'}), 401

    if not user.is_active_user:
        return jsonify({'error': 'Account is deactivated'}), 403

    tokens = generate_tokens(user)
    return jsonify({
        'user': user_to_dict(user),
        **tokens,
    })


@auth_api.route('/token/refresh', methods=['POST'])
@limiter.limit("10 per minute")
def token_refresh():
    """Exchange a valid refresh token for a new access token."""
    data = request.get_json()
    refresh_token = data.get('refresh_token', '') if data else ''
    if not refresh_token:
        return jsonify({'error': 'refresh_token is required'}), 400

    payload = decode_token(refresh_token, expected_type='refresh')
    if not payload:
        return jsonify({'error': 'Invalid or expired refresh token'}), 401

    user = User.query.get(payload['user_id'])
    if not user or not user.is_active_user:
        return jsonify({'error': 'User not found or deactivated'}), 401

    tokens = generate_tokens(user)
    return jsonify({
        'user': user_to_dict(user),
        **tokens,
    })


@auth_api.route('/token/register', methods=['POST'])
@limiter.limit("3 per minute")
def token_register():
    """Register a new account and return JWT tokens (mobile)."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    for field in ['username', 'email', 'password', 'role']:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 400

    ok, msg = validate_password(data['password'])
    if not ok:
        return jsonify({'error': msg}), 400

    if User.query.filter_by(email=data['email'].lower()).first():
        return jsonify({'error': 'Unable to create account with this email'}), 409
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Username already taken'}), 409

    user = User(
        username=data['username'],
        email=data['email'].lower(),
        role=data['role'],
        display_name=data.get('display_name', data['username']),
        address=data.get('address', ''),
        city=data.get('city', ''),
        state=data.get('state', ''),
        zip_code=data.get('zip_code', ''),
    )
    user.set_password(data['password'])

    lat, lon = geocode_address(
        data.get('address', ''), data.get('city', ''),
        data.get('state', ''), data.get('zip_code', '')
    )
    user.latitude = lat
    user.longitude = lon

    db.session.add(user)
    db.session.commit()

    tokens = generate_tokens(user)
    return jsonify({
        'user': user_to_dict(user),
        **tokens,
    }), 201


@auth_api.route('/device-token', methods=['PUT'])
@token_or_session
def update_device_token():
    """Store APNs/FCM device token for push notifications (mobile)."""
    user = get_current_user()
    data = request.get_json()
    if not data or not data.get('device_token'):
        return jsonify({'error': 'device_token is required'}), 400

    user.device_token = data['device_token']
    user.device_platform = data.get('platform', 'ios')
    db.session.commit()
    return jsonify({'message': 'Device token updated'})
