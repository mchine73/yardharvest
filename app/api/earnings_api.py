"""Seller Earnings REST API endpoints."""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.api.token_auth import token_or_session, get_current_user
from app import db
from app.models import Order, SellerPayout
from sqlalchemy import func
from datetime import datetime, timezone, timedelta

earnings_api = Blueprint('earnings_api', __name__, url_prefix='/api/earnings')


@earnings_api.route('/summary', methods=['GET'])
@token_or_session
def summary():
    """Earnings summary for the current seller."""
    if not get_current_user().can_sell():
        return jsonify({'error': 'Seller account required'}), 403

    sid = get_current_user().id

    # Total earnings from completed orders
    total_earnings = db.session.query(
        func.coalesce(func.sum(Order.seller_earnings), 0)
    ).filter_by(seller_id=sid, status='completed').scalar()

    # Pending earnings (accepted but not completed)
    pending_earnings = db.session.query(
        func.coalesce(func.sum(Order.seller_earnings), 0)
    ).filter(
        Order.seller_id == sid,
        Order.status.in_(['pending', 'accepted']),
    ).scalar()

    # This month
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    this_month = db.session.query(
        func.coalesce(func.sum(Order.seller_earnings), 0)
    ).filter(
        Order.seller_id == sid,
        Order.status == 'completed',
        Order.created_at >= month_start,
    ).scalar()

    # Last month
    last_month_end = month_start - timedelta(seconds=1)
    last_month_start = last_month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month = db.session.query(
        func.coalesce(func.sum(Order.seller_earnings), 0)
    ).filter(
        Order.seller_id == sid,
        Order.status == 'completed',
        Order.created_at >= last_month_start,
        Order.created_at <= last_month_end,
    ).scalar()

    # Average commission rate
    avg_commission = db.session.query(
        func.coalesce(func.avg(Order.commission_rate), 0)
    ).filter(
        Order.seller_id == sid,
        Order.status == 'completed',
        Order.commission_rate > 0,
    ).scalar()

    # Total orders completed
    completed_orders = Order.query.filter_by(
        seller_id=sid, status='completed'
    ).count()

    return jsonify({
        'total_earnings': round(float(total_earnings), 2),
        'pending_earnings': round(float(pending_earnings), 2),
        'this_month': round(float(this_month), 2),
        'last_month': round(float(last_month), 2),
        'avg_commission_rate': round(float(avg_commission), 4),
        'completed_orders': completed_orders,
    })


@earnings_api.route('/history', methods=['GET'])
@token_or_session
def history():
    """Paginated order-by-order earnings breakdown."""
    if not get_current_user().can_sell():
        return jsonify({'error': 'Seller account required'}), 403

    page = request.args.get('page', 1, type=int)
    per_page = 20

    pagination = Order.query.filter(
        Order.seller_id == get_current_user().id,
        Order.status.in_(['completed', 'accepted', 'pending']),
    ).order_by(Order.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    orders = [{
        'id': o.id,
        'buyer_name': o.buyer.display_name or o.buyer.username,
        'subtotal': o.subtotal or o.total_price,
        'delivery_fee': o.delivery_fee or 0,
        'platform_commission': o.platform_commission or 0,
        'commission_rate': o.commission_rate or 0,
        'seller_earnings': o.seller_earnings or o.total_price,
        'total_price': o.total_price,
        'status': o.status,
        'fulfillment_method': o.fulfillment_method,
        'created_at': o.created_at.isoformat() if o.created_at else None,
        'item_count': len(o.items),
    } for o in pagination.items]

    return jsonify({
        'orders': orders,
        'total': pagination.total,
        'pages': pagination.pages,
        'page': pagination.page,
        'has_next': pagination.has_next,
    })


@earnings_api.route('/payouts', methods=['GET'])
@token_or_session
def payouts():
    """Payout history for the current seller."""
    if not get_current_user().can_sell():
        return jsonify({'error': 'Seller account required'}), 403

    payouts = SellerPayout.query.filter_by(
        seller_id=get_current_user().id
    ).order_by(SellerPayout.created_at.desc()).all()

    return jsonify([{
        'id': p.id,
        'amount': p.amount,
        'status': p.status,
        'period_start': p.period_start.isoformat() if p.period_start else None,
        'period_end': p.period_end.isoformat() if p.period_end else None,
        'payout_reference': p.payout_reference,
        'notes': p.notes,
        'created_at': p.created_at.isoformat() if p.created_at else None,
        'completed_at': p.completed_at.isoformat() if p.completed_at else None,
    } for p in payouts])
