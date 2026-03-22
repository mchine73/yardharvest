"""Stripe webhook handler for async event processing."""
import logging
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from app import db
from app import stripe_service

log = logging.getLogger(__name__)

webhook_api = Blueprint('webhook_api', __name__, url_prefix='/api/webhooks')


@webhook_api.route('/stripe', methods=['POST'])
def stripe_webhook():
    """Handle incoming Stripe webhook events."""
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature', '')

    try:
        event = stripe_service.construct_webhook_event(payload, sig_header)
    except Exception:
        log.exception('Stripe webhook signature verification failed')
        return jsonify({'error': 'Invalid signature'}), 400

    if event is None:
        # STRIPE_WEBHOOK_SECRET not set — skip verification in dev
        import json
        try:
            event = json.loads(payload)
        except Exception:
            return jsonify({'error': 'Invalid payload'}), 400

    event_type = event.get('type', '') if isinstance(event, dict) else event['type']
    data_obj = event.get('data', {}).get('object', {}) if isinstance(event, dict) else event['data']['object']

    handler = EVENT_HANDLERS.get(event_type)
    if handler:
        try:
            handler(data_obj)
        except Exception:
            log.exception('Error handling Stripe event %s', event_type)
    else:
        log.debug('Unhandled Stripe event type: %s', event_type)

    return jsonify({'status': 'ok'}), 200


# ==================== Event Handlers ====================

def handle_payment_intent_succeeded(pi):
    """Backup confirmation: mark order payment as succeeded."""
    from app.models import Order
    pi_id = pi.get('id', '') if isinstance(pi, dict) else pi.id
    orders = Order.query.filter_by(stripe_payment_intent_id=pi_id).all()
    for order in orders:
        if order.payment_status != 'succeeded':
            order.payment_status = 'succeeded'
    if orders:
        db.session.commit()


def handle_payment_intent_failed(pi):
    """Mark order payment as failed."""
    from app.models import Order
    pi_id = pi.get('id', '') if isinstance(pi, dict) else pi.id
    orders = Order.query.filter_by(stripe_payment_intent_id=pi_id).all()
    for order in orders:
        order.payment_status = 'failed'
    if orders:
        db.session.commit()


def handle_subscription_updated(sub):
    """Sync GardenSubscription status and period dates from Stripe."""
    from app.models import GardenSubscription, CommunityGarden
    sub_id = sub.get('id', '') if isinstance(sub, dict) else sub.id
    gs = GardenSubscription.query.filter_by(stripe_subscription_id=sub_id).first()
    if not gs:
        return

    status = sub.get('status', '') if isinstance(sub, dict) else sub.status
    gs.status = status
    period_start = sub.get('current_period_start') if isinstance(sub, dict) else sub.current_period_start
    period_end = sub.get('current_period_end') if isinstance(sub, dict) else sub.current_period_end
    if period_start:
        gs.current_period_start = datetime.fromtimestamp(period_start, tz=timezone.utc)
    if period_end:
        gs.current_period_end = datetime.fromtimestamp(period_end, tz=timezone.utc)
    cancel_at = sub.get('cancel_at_period_end', False) if isinstance(sub, dict) else sub.cancel_at_period_end
    gs.cancel_at_period_end = bool(cancel_at)

    garden = CommunityGarden.query.get(gs.garden_id)
    if garden:
        garden.subscription_status = 'active' if status == 'active' else status
    db.session.commit()


def handle_subscription_deleted(sub):
    """Set GardenSubscription status to expired."""
    from app.models import GardenSubscription, CommunityGarden
    sub_id = sub.get('id', '') if isinstance(sub, dict) else sub.id
    gs = GardenSubscription.query.filter_by(stripe_subscription_id=sub_id).first()
    if not gs:
        return

    gs.status = 'expired'
    garden = CommunityGarden.query.get(gs.garden_id)
    if garden:
        garden.subscription_status = 'expired'
    db.session.commit()

    try:
        from app.email_service import send_garden_trial_ended
        send_garden_trial_ended(garden, garden.organizer)
    except Exception:
        pass


def handle_invoice_payment_failed(invoice):
    """Set subscription to past_due and send dunning email."""
    from app.models import GardenSubscription, CommunityGarden
    sub_id = invoice.get('subscription', '') if isinstance(invoice, dict) else getattr(invoice, 'subscription', '')
    if not sub_id:
        return

    gs = GardenSubscription.query.filter_by(stripe_subscription_id=sub_id).first()
    if not gs:
        return

    gs.status = 'past_due'
    garden = CommunityGarden.query.get(gs.garden_id)
    if garden:
        garden.subscription_status = 'past_due'
    db.session.commit()

    try:
        from app.email_service import send_garden_payment_failed
        send_garden_payment_failed(garden, garden.organizer)
    except Exception:
        pass


def handle_account_updated(account):
    """Sync Connect account onboarding status."""
    from app.models import User
    acct_id = account.get('id', '') if isinstance(account, dict) else account.id
    user = User.query.filter_by(stripe_connect_account_id=acct_id).first()
    if not user:
        return

    charges_enabled = account.get('charges_enabled', False) if isinstance(account, dict) else account.charges_enabled
    payouts_enabled = account.get('payouts_enabled', False) if isinstance(account, dict) else account.payouts_enabled
    if charges_enabled and payouts_enabled:
        user.stripe_onboarding_complete = True
        db.session.commit()


def handle_transfer_created(transfer):
    """Record a SellerPayout when Stripe creates a transfer."""
    from app.models import SellerPayout, User
    tr_id = transfer.get('id', '') if isinstance(transfer, dict) else transfer.id
    destination = transfer.get('destination', '') if isinstance(transfer, dict) else transfer.destination

    # Skip if already recorded
    existing = SellerPayout.query.filter_by(stripe_transfer_id=tr_id).first()
    if existing:
        return

    user = User.query.filter_by(stripe_connect_account_id=destination).first()
    if not user:
        return

    amount = transfer.get('amount', 0) if isinstance(transfer, dict) else transfer.amount
    payout = SellerPayout(
        seller_id=user.id,
        amount=amount / 100.0,
        status='completed',
        stripe_transfer_id=tr_id,
        payout_reference=tr_id,
        completed_at=datetime.now(timezone.utc),
    )
    db.session.add(payout)
    db.session.commit()


EVENT_HANDLERS = {
    'payment_intent.succeeded': handle_payment_intent_succeeded,
    'payment_intent.payment_failed': handle_payment_intent_failed,
    'customer.subscription.updated': handle_subscription_updated,
    'customer.subscription.deleted': handle_subscription_deleted,
    'invoice.payment_failed': handle_invoice_payment_failed,
    'account.updated': handle_account_updated,
    'transfer.created': handle_transfer_created,
}
