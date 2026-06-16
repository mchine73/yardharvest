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
        # STRIPE_WEBHOOK_SECRET not set. Only acceptable in dev, where Stripe
        # itself is unconfigured (no STRIPE_SECRET_KEY) and events come from
        # the test suite. If real Stripe keys are present, unsigned events
        # MUST be rejected — otherwise anyone who finds this endpoint can
        # forge payment_intent.succeeded and mark orders/dues as paid.
        if stripe_service.is_configured():
            log.error('Stripe webhook received but STRIPE_WEBHOOK_SECRET is '
                      'not set — rejecting unsigned event. Set the secret '
                      'from the Stripe dashboard webhook config.')
            return jsonify({'error': 'Webhook signature verification not '
                                     'configured'}), 503
        import json
        try:
            event = json.loads(payload)
        except Exception:
            return jsonify({'error': 'Invalid payload'}), 400

    event_type = event.get('type', '') if isinstance(event, dict) else event['type']
    event_id = event.get('id', '') if isinstance(event, dict) else getattr(event, 'id', '')
    data_obj = event.get('data', {}).get('object', {}) if isinstance(event, dict) else event['data']['object']

    # Idempotency: Stripe delivers at-least-once and retries for up to 72h, so
    # the same event.id can arrive repeatedly. Skip if we've already processed
    # it. (Handlers are also written to be idempotent as defense-in-depth.)
    from app.models import ProcessedStripeEvent
    if event_id:
        already = ProcessedStripeEvent.query.filter_by(event_id=event_id).first()
        if already:
            log.info('Skipping already-processed Stripe event %s (%s)', event_id, event_type)
            return jsonify({'status': 'ok', 'duplicate': True}), 200

    handler = EVENT_HANDLERS.get(event_type)
    if handler:
        try:
            handler(data_obj)
        except Exception:
            # Roll back any partial work and do NOT record the event as
            # processed — return 500 so Stripe retries the delivery.
            db.session.rollback()
            log.exception('Error handling Stripe event %s', event_type)
            return jsonify({'error': 'handler failed'}), 500
    else:
        log.debug('Unhandled Stripe event type: %s', event_type)

    # Record the event so retries short-circuit.
    if event_id:
        try:
            db.session.add(ProcessedStripeEvent(event_id=event_id, event_type=event_type))
            db.session.commit()
        except Exception:
            db.session.rollback()  # UNIQUE race — another delivery beat us; fine.

    return jsonify({'status': 'ok'}), 200


# ==================== Event Handlers ====================

def _pi_metadata(pi):
    """Extract the metadata dict from a PaymentIntent (object or dict)."""
    if isinstance(pi, dict):
        return pi.get('metadata', {}) or {}
    return dict(getattr(pi, 'metadata', {}) or {})


def handle_payment_intent_succeeded(pi):
    """Webhook-driven fulfillment for a succeeded PaymentIntent.

    Routes by metadata.type: marketplace orders are marked paid (their backup
    confirmation), and garden dues are fully fulfilled here so collection no
    longer depends on the buyer's browser calling the confirm endpoint.
    Idempotent: guards on current state so repeated deliveries are no-ops.
    """
    pi_id = pi.get('id', '') if isinstance(pi, dict) else pi.id
    meta = _pi_metadata(pi)
    pi_type = meta.get('type', '')

    if pi_type == 'garden_dues':
        _fulfill_dues_from_pi(pi_id, meta)
        return

    # Marketplace order: fulfill from the basket snapshot. This is the
    # guarantee path — it creates the orders (stock decrement, cart clear,
    # seller payouts) even if the buyer never returned to /confirm. Idempotent:
    # a no-op if /confirm already produced the orders for this PI.
    from app.models import Order, PendingCheckout
    pc = PendingCheckout.query.filter_by(payment_intent_id=pi_id).first()
    if pc:
        from app.api.payment_api import fulfill_payment_intent
        fulfill_payment_intent(pi_id, pc.buyer_id)
        return

    # Legacy/dev PI with no snapshot: just mark any existing orders paid.
    orders = Order.query.filter_by(stripe_payment_intent_id=pi_id).all()
    changed = False
    for order in orders:
        if order.payment_status != 'succeeded':
            order.payment_status = 'succeeded'
            changed = True
    if changed:
        db.session.commit()


def _fulfill_dues_from_pi(pi_id, meta):
    """Mark a GardenDuesRecord paid from its PaymentIntent. Idempotent."""
    from app.models import GardenDuesRecord, CommunityGarden, User
    from datetime import date
    dues_id = meta.get('dues_id')
    if not dues_id:
        return
    rec = db.session.get(GardenDuesRecord, int(dues_id))
    if not rec:
        return
    # Idempotency guard: already settled by this PI (or otherwise paid).
    if rec.status == 'paid' and rec.stripe_payment_intent_id == pi_id:
        return
    rec.amount_paid = rec.amount_due
    rec.status = 'paid'
    rec.payment_method = 'online'
    rec.payment_date = date.today()
    rec.stripe_payment_intent_id = pi_id
    rec.payment_note = f'Stripe: {pi_id}'
    db.session.commit()

    # Notify the organizer once (only on the transition to paid).
    try:
        from app.api.gardens_api import notify
        garden = db.session.get(CommunityGarden, rec.garden_id)
        payer = db.session.get(User, rec.user_id)
        payer_name = (payer.display_name or payer.username) if payer else 'A member'
        if garden:
            notify(
                user_id=garden.organizer_id,
                type='dues_paid',
                title=f'{payer_name} paid dues',
                body=f'{payer_name} paid ${rec.amount_due:.2f} for {rec.season_year} season dues online.',
                link=f'/gardens/{rec.garden_id}/admin?tab=finance',
                garden_id=rec.garden_id,
            )
            db.session.commit()
    except Exception:
        log.exception('Failed to notify organizer of dues payment for rec %s', dues_id)


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

    garden = db.session.get(CommunityGarden, gs.garden_id)
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
    garden = db.session.get(CommunityGarden, gs.garden_id)
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
    garden = db.session.get(CommunityGarden, gs.garden_id)
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


def handle_charge_refunded(charge):
    """Sync refund status when a refund is issued from Stripe Dashboard."""
    from app.models import Order, Refund
    pi_id = charge.get('payment_intent', '') if isinstance(charge, dict) else getattr(charge, 'payment_intent', '')
    if not pi_id:
        return

    orders = Order.query.filter_by(stripe_payment_intent_id=pi_id).all()
    amount_refunded = charge.get('amount_refunded', 0) if isinstance(charge, dict) else getattr(charge, 'amount_refunded', 0)
    amount_refunded_dollars = amount_refunded / 100.0

    for order in orders:
        order.refund_amount = amount_refunded_dollars
        if amount_refunded_dollars >= order.total_price:
            order.refund_status = 'full'
        elif amount_refunded_dollars > 0:
            order.refund_status = 'partial'

    if orders:
        db.session.commit()


EVENT_HANDLERS = {
    'payment_intent.succeeded': handle_payment_intent_succeeded,
    'payment_intent.payment_failed': handle_payment_intent_failed,
    'customer.subscription.updated': handle_subscription_updated,
    'customer.subscription.deleted': handle_subscription_deleted,
    'invoice.payment_failed': handle_invoice_payment_failed,
    'account.updated': handle_account_updated,
    'transfer.created': handle_transfer_created,
    'charge.refunded': handle_charge_refunded,
}
