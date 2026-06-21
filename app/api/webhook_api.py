"""Webhook handlers — Stripe events + ZeptoMail bounce/complaint notifications."""
import logging
import os
import re
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, current_app
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
                link=f'/gardens/{garden.public_id}/admin?tab=finance',
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


# ==================== ZeptoMail bounce / complaint webhook ====================
#
# ZeptoMail can POST a notification whenever a message hard-bounces or a
# recipient marks it as spam. We add those addresses to the global suppression
# list so we stop mailing them — repeated sends to dead/complaining addresses
# are exactly what tanks domain reputation and lands the rest in junk.
#
# The payload shape varies (and differs across ZeptoMail's bounce vs. webhook
# formats), so we parse it tolerantly: collect "event type" strings from a set
# of known keys, collect recipient addresses from a set of known recipient
# keys, and only suppress when the event clearly reads as a hard bounce or
# complaint. Soft/transient bounces are ignored — they retry and recover.

_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

# Keys whose string values describe what happened (the event/bounce type).
_TYPE_KEYS = ('event', 'event_name', 'bounce_type', 'type', 'sub_event',
              'reason', 'status', 'category')
# Keys whose values hold the *recipient* address. Deliberately excludes
# 'from'/'sender' so we never suppress our own sending address.
_RECIPIENT_KEYS = ('bounced_recipient', 'recipient', 'email_address',
                   'to', 'to_address')


def _emails_from(value, out):
    """Pull every email-looking address out of a recipient field (which may be
    a bare string, an {'address': ...} object, or a list of either)."""
    if isinstance(value, str):
        v = value.strip().lower()
        if _EMAIL_RE.match(v):
            out.add(v)
    elif isinstance(value, dict):
        for k in ('address', 'email_address', 'email', 'recipient'):
            if k in value:
                _emails_from(value[k], out)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _emails_from(item, out)


def _gather_bounce(node, types, recipients):
    """Recursively collect type-signal strings and recipient emails."""
    if isinstance(node, dict):
        for k, v in node.items():
            kl = k.lower()
            if kl in _TYPE_KEYS and isinstance(v, str):
                types.append(v.lower())
            if kl in _RECIPIENT_KEYS:
                _emails_from(v, recipients)
            _gather_bounce(v, types, recipients)
    elif isinstance(node, (list, tuple)):
        for item in node:
            _gather_bounce(item, types, recipients)


def _classify_bounce(types):
    """Return ('bounce'|'complaint'|None) from the collected type signals.

    None means "don't suppress" — either no recognizable signal, or a purely
    soft/transient bounce that will retry."""
    blob = ' '.join(types)
    if not blob:
        return None
    is_complaint = any(s in blob for s in ('complaint', 'spam', 'abuse'))
    if is_complaint:
        return 'complaint'
    is_soft = any(s in blob for s in ('soft', 'defer', 'delay', 'transient'))
    if is_soft:
        return None
    is_hard = ('hard' in blob or 'bounce' in blob or 'invalid' in blob
               or 'block' in blob or 'undeliver' in blob)
    return 'bounce' if is_hard else None


@webhook_api.route('/zeptomail', methods=['POST'])
def zeptomail_webhook():
    """Auto-suppress hard bounces and spam complaints reported by ZeptoMail."""
    secret = (current_app.config.get('ZEPTOMAIL_WEBHOOK_SECRET') or '').strip()
    if secret:
        auth = request.headers.get('Authorization', '')
        if auth.lower().startswith('bearer '):
            auth = auth[7:]
        provided = (request.headers.get('X-Webhook-Token')
                    or auth or request.args.get('token', '')).strip()
        if provided != secret:
            log.warning('ZeptoMail webhook rejected: bad/missing token')
            return jsonify({'error': 'unauthorized'}), 403

    data = request.get_json(silent=True) or {}
    types, recipients = [], set()
    _gather_bounce(data, types, recipients)
    source = _classify_bounce(types)
    if not source or not recipients:
        # Opens/clicks/soft bounces/unknown shapes — acknowledge, do nothing.
        return jsonify({'status': 'ok', 'suppressed': 0}), 200

    # Never suppress our own sending identities, even if they appear as a
    # recipient (e.g. a test send to ourselves that bounced).
    own = {a.strip().lower() for a in (
        current_app.config.get('CRM_FROM_EMAIL') or '',
        current_app.config.get('ZEPTOMAIL_FROM_EMAIL') or '',
        current_app.config.get('MAIL_DEFAULT_SENDER') or '',
    ) if a}

    from app.models import EmailUnsubscribe
    added = 0
    for email in sorted(recipients):
        if email in own:
            continue
        try:
            if not EmailUnsubscribe.query.filter_by(email=email).first():
                db.session.add(EmailUnsubscribe(email=email, source=source))
                added += 1
            # Keep the CRM UI consistent with the suppression list.
            from app.crm.models import Contact
            for c in Contact.query.filter(Contact.email.ilike(email)).all():
                c.email_opt_out = True
        except Exception:
            log.exception('Failed to suppress bounced address %s', email)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        log.exception('Failed to commit ZeptoMail suppressions')
    log.info('ZeptoMail webhook: %s — suppressed %d new address(es)', source, added)
    return jsonify({'status': 'ok', 'suppressed': added}), 200
