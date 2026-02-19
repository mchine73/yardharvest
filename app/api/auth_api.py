"""Auth REST API endpoints."""
from flask import Blueprint, request, jsonify, session
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User
from app.helpers import geocode_address

auth_api = Blueprint('auth_api', __name__, url_prefix='/api/auth')


@auth_api.route('/me', methods=['GET'])
def me():
    if current_user.is_authenticated:
        return jsonify(user_to_dict(current_user))
    return jsonify(None)


@auth_api.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Validate required fields
    for field in ['username', 'email', 'password', 'role']:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 400

    if User.query.filter_by(email=data['email'].lower()).first():
        return jsonify({'error': 'Email already registered'}), 409
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
@login_required
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
        'created_at': user.created_at.isoformat() if user.created_at else None,
    }
