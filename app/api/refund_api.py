"""Refund API endpoints — admin-only refund management."""
import logging
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from app.api.token_auth import token_or_session, get_current_user
from app import db
from app.models import Order, Refund, SellerPayout, GardenSubscription, CommunityGarden
from app.helpers import admin_required
from app import stripe_service

log = logging.getLogger(__name__)

refund_api = Blueprint('refund_api', __name__, url_prefix='/api/admin/refunds')


def refund_to_dict(r):
    return {
        'id': r.id,
        'order_id': r.order_id,
        'garden_subscription_id': r.garden_subscription_id,
        'refund_type': r.refund_type,
        'amount': r.amount,
        'reason': r.reason,
        'status': r.status,
        'stripe_refund_id': r.stripe_refund_id,
        'initiated_by': r.initiated_by.display_name or r.initiated_by.username if r.initiated_by else None,
        'created_at': r.created_at.isoformat() if r.created_at else None,
        'completed_at': r.completed_at.isoformat() if r.completed_at else None,
    }


@refund_api.route('', methods=['GET'])
@token_or_session
@admin_required
def list_refunds():
    """List all refunds with pagination."""
    page = request.args.get('page', 1, type=int)
    refunds = Refund.query.order_by(Refund.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    return jsonify({
        'refunds': [refund_to_dict(r) for r in refunds.items],
        'page': refunds.page,
        'pages': refunds.pages,
        'total': refunds.total,
    })


@refund_api.route('/order/<int:order_id>', methods=['POST'])
@token_or_session
@admin_required
def refund_order(order_id):
    """Issue a full or partial refund on a marketplace order."""
    order = Order.query.get_or_404(order_id)
    data = request.get_json() or {}
    amount = data.get('amount', order.total_price)
    reason = data.get('reason', '')

    if not isinstance(amount, (int, float)) or amount <= 0:
        return jsonify({'error': 'Invalid refund amount'}), 400

    already_refunded = order.refund_amount or 0
    max_refundable = order.total_price - already_refunded
    if amount > max_refundable:
        return jsonify({'error': f'Maximum refundable amount is ${max_refundable:.2f}'}), 400

    amount_cents = int(round(amount * 100))
    stripe_refund_id = None
    stripe_reversal_id = None
    status = 'completed'

    # Issue Stripe refund
    if stripe_service.is_configured() and order.stripe_payment_intent_id:
        try:
            sr = stripe_service.create_refund(order.stripe_payment_intent_id, amount_cents)
            stripe_refund_id = sr.id
        except Exception:
            log.exception('Stripe refund failed for order %d', order_id)
            status = 'failed'

        # Reverse seller payout if applicable
        if status == 'completed':
            payout = SellerPayout.query.filter_by(
                seller_id=order.seller_id,
                stripe_transfer_id=db.not_(None)
            ).filter(SellerPayout.stripe_transfer_id.isnot(None)).first()
            if payout and payout.stripe_transfer_id:
                try:
                    seller_refund_pct = amount / order.total_price
                    reversal_cents = int(round(order.seller_earnings * seller_refund_pct * 100))
                    rev = stripe_service.reverse_transfer(payout.stripe_transfer_id, reversal_cents)
                    stripe_reversal_id = rev.id
                except Exception:
                    log.exception('Transfer reversal failed for order %d', order_id)

    # Create refund record
    refund = Refund(
        order_id=order_id,
        refund_type='marketplace',
        amount=amount,
        reason=reason,
        status=status,
        stripe_refund_id=stripe_refund_id,
        stripe_reversal_id=stripe_reversal_id,
        initiated_by_id=get_current_user().id,
        completed_at=datetime.now(timezone.utc) if status == 'completed' else None,
    )
    db.session.add(refund)

    # Update order
    if status == 'completed':
        order.refund_amount = (order.refund_amount or 0) + amount
        if order.refund_amount >= order.total_price:
            order.refund_status = 'full'
        else:
            order.refund_status = 'partial'

    db.session.commit()

    return jsonify({
        'message': f'Refund of ${amount:.2f} {"issued" if status == "completed" else "failed"}',
        'refund': refund_to_dict(refund),
    })


@refund_api.route('/subscription/<int:sub_id>', methods=['POST'])
@token_or_session
@admin_required
def refund_subscription(sub_id):
    """Cancel and refund a Garden Pro subscription."""
    sub = GardenSubscription.query.get_or_404(sub_id)
    data = request.get_json() or {}
    reason = data.get('reason', 'Admin-initiated refund')

    stripe_refund_id = None
    status = 'completed'

    # Cancel in Stripe
    if stripe_service.is_configured() and sub.stripe_subscription_id:
        try:
            stripe_service.cancel_subscription_immediately(sub.stripe_subscription_id)
        except Exception:
            log.exception('Stripe subscription cancellation failed for %s', sub.stripe_subscription_id)
            status = 'failed'

    # Determine refund amount (prorated)
    amount = 0
    if sub.current_period_start and sub.current_period_end and sub.billing_cycle:
        from app.models import PricingConfig
        config = PricingConfig.query.first()
        if sub.billing_cycle == 'monthly':
            full_amount = (getattr(config, 'garden_pro_monthly_cents', 1500) if config else 1500) / 100
        else:
            full_amount = (getattr(config, 'garden_pro_yearly_cents', 12500) if config else 12500) / 100
        now = datetime.now(timezone.utc)
        total_days = (sub.current_period_end - sub.current_period_start).days or 1
        used_days = (now - sub.current_period_start).days
        remaining_pct = max(0, (total_days - used_days) / total_days)
        amount = round(full_amount * remaining_pct, 2)

    refund = Refund(
        garden_subscription_id=sub_id,
        refund_type='garden_pro',
        amount=amount,
        reason=reason,
        status=status,
        stripe_refund_id=stripe_refund_id,
        initiated_by_id=get_current_user().id,
        completed_at=datetime.now(timezone.utc) if status == 'completed' else None,
    )
    db.session.add(refund)

    if status == 'completed':
        sub.status = 'expired'
        sub.cancel_at_period_end = False
        garden = CommunityGarden.query.get(sub.garden_id)
        if garden:
            garden.subscription_status = 'expired'

    db.session.commit()

    return jsonify({
        'message': f'Subscription cancelled. Prorated refund: ${amount:.2f}',
        'refund': refund_to_dict(refund),
    })
