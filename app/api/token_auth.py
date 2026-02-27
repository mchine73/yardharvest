"""JWT token authentication for mobile clients.

Provides token-based auth alongside Flask-Login session auth so both
the React web app (cookies) and React Native mobile app (Bearer tokens)
can use the same API endpoints.
"""
import jwt
from datetime import datetime, timezone, timedelta
from functools import wraps
from flask import request, jsonify, g, current_app
from flask_login import current_user


# Token lifetimes
ACCESS_TOKEN_EXPIRY = timedelta(hours=1)
REFRESH_TOKEN_EXPIRY = timedelta(days=30)


def generate_tokens(user):
    """Generate access + refresh JWT tokens for a user."""
    secret = current_app.config['SECRET_KEY']
    now = datetime.now(timezone.utc)

    access_payload = {
        'user_id': user.id,
        'email': user.email,
        'role': user.role,
        'type': 'access',
        'iat': now,
        'exp': now + ACCESS_TOKEN_EXPIRY,
    }

    refresh_payload = {
        'user_id': user.id,
        'type': 'refresh',
        'iat': now,
        'exp': now + REFRESH_TOKEN_EXPIRY,
    }

    access_token = jwt.encode(access_payload, secret, algorithm='HS256')
    refresh_token = jwt.encode(refresh_payload, secret, algorithm='HS256')

    return {
        'access_token': access_token,
        'refresh_token': refresh_token,
        'expires_in': int(ACCESS_TOKEN_EXPIRY.total_seconds()),
    }


def decode_token(token, expected_type='access'):
    """Decode and validate a JWT token. Returns payload dict or None."""
    try:
        secret = current_app.config['SECRET_KEY']
        payload = jwt.decode(token, secret, algorithms=['HS256'])
        if payload.get('type') != expected_type:
            return None
        return payload
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def _get_user_from_token():
    """Extract user from Authorization: Bearer header if present."""
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None

    token = auth_header[7:]
    payload = decode_token(token, expected_type='access')
    if not payload:
        return None

    from app.models import User
    user = User.query.get(payload['user_id'])
    if user and user.is_active_user:
        return user
    return None


def get_current_user():
    """Return the authenticated user from either session or token.

    Use this instead of flask_login.current_user in endpoint bodies
    when you need to support both auth methods.
    """
    # Check Flask-Login session first (web)
    if current_user.is_authenticated:
        return current_user
    # Check Bearer token (mobile)
    return getattr(g, '_token_user', None)


def token_or_session(f):
    """Decorator that accepts either session cookie OR Bearer token auth.

    Drop-in replacement for @login_required that also works with JWT tokens.
    Sets g._token_user when token auth is used so get_current_user() works.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # Session auth (web) — already authenticated by Flask-Login
        if current_user.is_authenticated:
            return f(*args, **kwargs)

        # Token auth (mobile) — check Bearer header
        user = _get_user_from_token()
        if user:
            g._token_user = user
            return f(*args, **kwargs)

        return jsonify({'error': 'Authentication required'}), 401
    return decorated
