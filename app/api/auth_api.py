"""Auth REST API endpoints."""
import re
from flask import Blueprint, request, jsonify, session
from flask_login import login_user, logout_user, login_required, current_user
from app import db, limiter
from app.models import User, SiteEmailConfig
from app.helpers import geocode_address
from app.api.token_auth import (generate_tokens, decode_token, token_or_session,
                                get_current_user, generate_reset_token, verify_reset_token,
                                generate_email_change_token, verify_email_change_token)

auth_api = Blueprint('auth_api', __name__, url_prefix='/api/auth')


def allowed_signup_roles():
    """Roles a new user may self-register with.

    Marketplace ON  -> buyer / seller / both (normal marketplace signup).
    Marketplace HIDDEN -> manager (Garden Manager) / gardener (New Gardener).
    """
    cfg = SiteEmailConfig.query.first()
    marketplace_on = cfg.marketplace_enabled if cfg else False
    if marketplace_on:
        return ('buyer', 'seller', 'both')
    return ('manager', 'gardener')


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
    # Support both session (web) and token (mobile) auth.
    # get_current_user() never returns None — it returns Flask-Login's
    # AnonymousUserMixin (which is truthy but has no .id) when unauthenticated,
    # so we must gate on .is_authenticated, not on truthiness.
    user = get_current_user()
    if user.is_authenticated:
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

    # Validate username format: alphanumeric + underscore/dash, 3-30 chars
    import re as _re
    if not _re.match(r'^[a-zA-Z0-9_-]{3,30}$', data['username']):
        return jsonify({'error': 'Username must be 3-30 characters and contain only letters, numbers, underscores, or dashes'}), 400

    # H9: Generic email error to prevent account enumeration
    # (Usernames are public via profiles, so specific error is OK there)
    if User.query.filter_by(email=data['email'].lower()).first():
        return jsonify({'error': 'Unable to create account with this email'}), 409
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Username already taken'}), 409

    # Validate role against the context-aware allowlist
    ALLOWED_ROLES = allowed_signup_roles()
    if data['role'] not in ALLOWED_ROLES:
        return jsonify({'error': f'Invalid role. Must be one of: {", ".join(ALLOWED_ROLES)}'}), 400

    # Validate password max length to prevent hash DoS
    if len(data['password']) > 128:
        return jsonify({'error': 'Password must be 128 characters or fewer'}), 400

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
        if not user.is_active_user:
            return jsonify({'error': 'Account is deactivated'}), 403
        session.clear()  # Prevent session fixation
        login_user(user)
        return jsonify(user_to_dict(user))
    return jsonify({'error': 'Invalid email or password'}), 401


@auth_api.route('/logout', methods=['POST'])
@token_or_session
def logout():
    # Increment token_version to revoke all outstanding JWT tokens
    user = get_current_user()
    if user.is_authenticated and hasattr(user, 'token_version'):
        user.token_version = (user.token_version or 0) + 1
        db.session.commit()
    logout_user()
    return jsonify({'message': 'Logged out'})


@auth_api.route('/forgot-password', methods=['POST'])
@limiter.limit("3 per hour")
def forgot_password():
    """Send a password reset link via email. Always returns success to prevent enumeration."""
    data = request.get_json()
    if not data or not data.get('email'):
        return jsonify({'error': 'Email is required'}), 400

    user = User.query.filter_by(email=data['email'].lower()).first()
    if user and user.is_active_user:
        token = generate_reset_token(user)
        try:
            from app.email_service import send_password_reset_email
            send_password_reset_email(user, token)
        except Exception:
            pass  # Don't reveal whether the email exists

    return jsonify({'message': 'If an account exists with that email, a password reset link has been sent.'})


@auth_api.route('/reset-password', methods=['POST'])
@limiter.limit("5 per hour")
def reset_password():
    """Reset password using a valid reset token."""
    data = request.get_json()
    if not data or not data.get('token') or not data.get('password'):
        return jsonify({'error': 'Token and new password are required'}), 400

    user = verify_reset_token(data['token'])
    if not user:
        return jsonify({'error': 'Invalid or expired reset link. Please request a new one.'}), 400

    ok, msg = validate_password(data['password'])
    if not ok:
        return jsonify({'error': msg}), 400

    if len(data['password']) > 128:
        return jsonify({'error': 'Password must be 128 characters or fewer'}), 400

    user.set_password(data['password'])
    # Revoke all outstanding JWT tokens
    user.token_version = (user.token_version or 0) + 1
    db.session.commit()
    return jsonify({'message': 'Password has been reset. You can now log in.'})


@auth_api.route('/request-email-change', methods=['POST'])
@token_or_session
@limiter.limit("3 per hour")
def request_email_change():
    """Start an email change: re-authenticate, then send a verification
    link to the NEW address. The account email only changes after the
    link is confirmed. A security notice goes to the current address."""
    user = get_current_user()
    data = request.get_json() or {}
    new_email = (data.get('new_email') or '').strip().lower()
    password = data.get('password') or ''

    if not new_email or not password:
        return jsonify({'error': 'New email and current password are required'}), 400
    if not user.check_password(password):
        return jsonify({'error': 'Current password is incorrect'}), 403
    if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', new_email):
        return jsonify({'error': 'Please enter a valid email address'}), 400
    if new_email == user.email:
        return jsonify({'error': 'That is already your email address'}), 400
    # Generic error to prevent account enumeration (mirrors registration)
    if User.query.filter_by(email=new_email).first():
        return jsonify({'error': 'Unable to use this email address'}), 409

    token = generate_email_change_token(user, new_email)
    try:
        from app.email_service import (send_email_change_verification,
                                       send_email_change_notice)
        send_email_change_verification(user, new_email, token)
        send_email_change_notice(user, new_email)
    except Exception:
        pass  # logged inside send_email

    return jsonify({'message': f'Verification email sent to {new_email}. '
                               'Your email will update once you confirm the link '
                               '(valid for 24 hours).'})


@auth_api.route('/confirm-email-change', methods=['POST'])
@limiter.limit("10 per hour")
def confirm_email_change():
    """Complete an email change using the verification token from the link."""
    data = request.get_json() or {}
    token = data.get('token') or ''
    if not token:
        return jsonify({'error': 'Token is required'}), 400

    user, new_email = verify_email_change_token(token)
    if not user or not new_email:
        return jsonify({'error': 'Invalid or expired verification link. '
                                 'Please request the change again.'}), 400

    # The address may have been claimed since the request was made
    if User.query.filter(User.email == new_email, User.id != user.id).first():
        return jsonify({'error': 'Unable to use this email address'}), 409

    old_email = user.email
    user.email = new_email
    db.session.commit()

    try:
        from app.email_service import send_email_changed_confirmation
        send_email_changed_confirmation(user, old_email)
    except Exception:
        pass  # logged inside send_email

    return jsonify({'message': 'Your email address has been updated.',
                    'email': user.email})


def public_user_to_dict(user):
    """Safe user dict for public profiles — omits PII."""
    return {
        'id': user.id,
        'username': user.username,
        'display_name': user.display_name,
        'bio': user.bio,
        'city': user.city,
        'state': user.state,
        'profile_image': user.profile_image,
        'gardening_story': user.gardening_story,
        'years_gardening': user.years_gardening,
        'gallery_image_1': user.gallery_image_1,
        'gallery_image_2': user.gallery_image_2,
        'gallery_image_3': user.gallery_image_3,
        'avg_rating': user.avg_rating,
        'review_count': user.review_count,
        'can_sell': user.can_sell(),
        'can_buy': user.can_buy(),
        'created_at': user.created_at.isoformat() if user.created_at else None,
    }


def user_to_dict(user):
    """Full user dict — only for the authenticated user viewing their own data."""
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

    # Validate role against the context-aware allowlist
    ALLOWED_ROLES = allowed_signup_roles()
    if data['role'] not in ALLOWED_ROLES:
        return jsonify({'error': f'Invalid role. Must be one of: {", ".join(ALLOWED_ROLES)}'}), 400

    # Validate password max length to prevent hash DoS
    if len(data['password']) > 128:
        return jsonify({'error': 'Password must be 128 characters or fewer'}), 400

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
