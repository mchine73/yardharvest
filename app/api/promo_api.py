"""Promo code API — admin CRUD + public validation."""
import logging
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from app.api.token_auth import token_or_session, get_current_user
from app import db
from app.models import PromoCode, PromoCodeUsage
from app.helpers import admin_required

log = logging.getLogger(__name__)

promo_api = Blueprint('promo_api', __name__)


def promo_to_dict(p):
    return {
        'id': p.id,
        'code': p.code,
        'description': p.description,
        'discount_type': p.discount_type,
        'discount_value': p.discount_value,
        'scope': p.scope,
        'max_uses': p.max_uses,
        'current_uses': p.current_uses,
        'expires_at': p.expires_at.isoformat() if p.expires_at else None,
        'is_active': p.is_active,
        'created_at': p.created_at.isoformat() if p.created_at else None,
    }


def validate_promo_code(code, scope):
    """Validate a promo code. Returns (promo, error_message)."""
    promo = PromoCode.query.filter(
        db.func.upper(PromoCode.code) == code.strip().upper()
    ).first()
    if not promo:
        return None, 'Promo code not found'
    if not promo.is_active:
        return None, 'This promo code is no longer active'
    if promo.expires_at and promo.expires_at < datetime.now(timezone.utc):
        return None, 'This promo code has expired'
    if promo.max_uses and promo.current_uses >= promo.max_uses:
        return None, 'This promo code has reached its usage limit'
    if promo.scope != 'both' and promo.scope != scope:
        return None, f'This promo code is not valid for {scope}'
    return promo, None


def calculate_discount(promo, subtotal):
    """Calculate discount amount from a promo code and subtotal."""
    if promo.discount_type == 'percentage':
        return round(subtotal * (promo.discount_value / 100), 2)
    else:  # fixed
        return min(promo.discount_value, subtotal)


# ==================== Admin CRUD ====================

@promo_api.route('/api/admin/promos', methods=['GET'])
@token_or_session
@admin_required
def list_promos():
    """List all promo codes."""
    page = request.args.get('page', 1, type=int)
    promos = PromoCode.query.order_by(PromoCode.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    return jsonify({
        'promos': [promo_to_dict(p) for p in promos.items],
        'page': promos.page,
        'pages': promos.pages,
        'total': promos.total,
    })


@promo_api.route('/api/admin/promos', methods=['POST'])
@token_or_session
@admin_required
def create_promo():
    """Create a new promo code."""
    data = request.get_json() or {}
    code = data.get('code', '').strip().upper()
    if not code or len(code) > 50:
        return jsonify({'error': 'Code is required (max 50 chars)'}), 400

    if PromoCode.query.filter(db.func.upper(PromoCode.code) == code).first():
        return jsonify({'error': 'A promo code with this name already exists'}), 400

    discount_type = data.get('discount_type', '')
    if discount_type not in ('percentage', 'fixed'):
        return jsonify({'error': 'discount_type must be percentage or fixed'}), 400

    discount_value = data.get('discount_value', 0)
    if not isinstance(discount_value, (int, float)) or discount_value <= 0:
        return jsonify({'error': 'discount_value must be positive'}), 400
    if discount_type == 'percentage' and discount_value > 100:
        return jsonify({'error': 'Percentage discount cannot exceed 100'}), 400

    scope = data.get('scope', 'both')
    if scope not in ('marketplace', 'garden_pro', 'both'):
        return jsonify({'error': 'scope must be marketplace, garden_pro, or both'}), 400

    expires_at = None
    if data.get('expires_at'):
        try:
            expires_at = datetime.fromisoformat(data['expires_at'].replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            return jsonify({'error': 'Invalid expires_at date format'}), 400

    promo = PromoCode(
        code=code,
        description=data.get('description', ''),
        discount_type=discount_type,
        discount_value=discount_value,
        scope=scope,
        max_uses=data.get('max_uses'),
        expires_at=expires_at,
        created_by_id=get_current_user().id,
    )
    db.session.add(promo)
    db.session.commit()

    return jsonify({'message': f'Promo code {code} created', 'promo': promo_to_dict(promo)}), 201


@promo_api.route('/api/admin/promos/<int:promo_id>', methods=['GET'])
@token_or_session
@admin_required
def promo_detail(promo_id):
    """Get promo code detail with usage history."""
    promo = PromoCode.query.get_or_404(promo_id)
    usages = PromoCodeUsage.query.filter_by(promo_code_id=promo_id).order_by(
        PromoCodeUsage.used_at.desc()
    ).limit(50).all()

    usage_list = []
    for u in usages:
        from app.models import User
        user = User.query.get(u.user_id)
        usage_list.append({
            'id': u.id,
            'user': user.display_name or user.username if user else 'Unknown',
            'discount_applied': u.discount_applied,
            'order_id': u.order_id,
            'garden_subscription_id': u.garden_subscription_id,
            'used_at': u.used_at.isoformat() if u.used_at else None,
        })

    result = promo_to_dict(promo)
    result['usages'] = usage_list
    return jsonify(result)


@promo_api.route('/api/admin/promos/<int:promo_id>', methods=['PUT'])
@token_or_session
@admin_required
def update_promo(promo_id):
    """Update a promo code."""
    promo = PromoCode.query.get_or_404(promo_id)
    data = request.get_json() or {}

    if 'description' in data:
        promo.description = data['description']
    if 'discount_value' in data and isinstance(data['discount_value'], (int, float)):
        promo.discount_value = data['discount_value']
    if 'max_uses' in data:
        promo.max_uses = data['max_uses']
    if 'expires_at' in data:
        if data['expires_at']:
            try:
                promo.expires_at = datetime.fromisoformat(data['expires_at'].replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                pass
        else:
            promo.expires_at = None
    if 'is_active' in data:
        promo.is_active = bool(data['is_active'])

    db.session.commit()
    return jsonify({'message': 'Promo code updated', 'promo': promo_to_dict(promo)})


@promo_api.route('/api/admin/promos/<int:promo_id>/deactivate', methods=['POST'])
@token_or_session
@admin_required
def deactivate_promo(promo_id):
    """Deactivate a promo code."""
    promo = PromoCode.query.get_or_404(promo_id)
    promo.is_active = False
    db.session.commit()
    return jsonify({'message': f'Promo code {promo.code} deactivated'})


# ==================== Public Validation ====================

@promo_api.route('/api/promos/validate', methods=['POST'])
@token_or_session
def validate_promo():
    """Validate a promo code for a given scope."""
    data = request.get_json() or {}
    code = data.get('code', '')
    scope = data.get('scope', 'marketplace')

    if not code:
        return jsonify({'valid': False, 'reason': 'Please enter a promo code'}), 400

    promo, error = validate_promo_code(code, scope)
    if error:
        return jsonify({'valid': False, 'reason': error})

    return jsonify({
        'valid': True,
        'code': promo.code,
        'discount_type': promo.discount_type,
        'discount_value': promo.discount_value,
        'description': promo.description,
    })
