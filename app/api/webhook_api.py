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
# ZeptoMail POSTs a notification on Soft bounce, Hard bounce, Feedback loop
# (spam complaint), Open and Click (per the notifications ticked in the Agent's
# Webhooks tab). We react to all of them:
#   * hard bounce / complaint  -> suppress the address immediately (global list
#     + Contact.email_opt_out). Repeated sends to dead/complaining addresses are
#     exactly what tanks domain reputation and lands the rest in junk.
#   * soft bounce              -> transient (full mailbox, greylisting, server
#     down). Record a strike on the CRM Contact; only suppress once the strikes
#     reach SOFT_BOUNCE_SUPPRESS_THRESHOLD (default 3).
#   * open / click             -> the address is alive; clear its soft strikes.
#
# The payload shape varies (and differs across ZeptoMail's bounce vs. webhook
# formats), so we parse it tolerantly: collect "event type" strings, recipient
# addresses, and a human reason from sets of known keys, then classify.

_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

# Keys whose string values describe what happened (the event/bounce type).
# 'object' carries ZeptoMail's real event marker (event_data[].object =
# "softbounce"/"hardbounce"/...); its other values ("email") match no
# classifier keyword, so the noise is harmless.
_TYPE_KEYS = ('event', 'event_name', 'bounce_type', 'type', 'sub_event',
              'reason', 'status', 'category', 'object')
# Keys whose values hold the *recipient* address. Deliberately excludes
# 'from'/'sender'/'bounce_address' so we never suppress our own addresses.
_RECIPIENT_KEYS = ('bounced_recipient', 'recipient', 'email_address',
                   'to', 'to_address')
# Keys whose string values carry a human-readable bounce reason.
_REASON_KEYS = ('reason', 'diagnostic_message', 'description', 'detail',
                'message')
# Payload keys ZeptoMail may use to carry the shared auth/agent key.
_AUTH_KEYS = ('mailagent_key', 'auth_key', 'authentication_key', 'authkey',
              'webhook_key')


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


def _gather_bounce(node, types, recipients, reasons=None, bounced=None):
    """Recursively collect type-signal strings, recipient emails, and reasons.

    ``bounced`` (a set, when given) separately collects addresses under
    ``bounced_recipient`` keys — ZeptoMail's real payloads list ALL of the
    email's recipients under ``email_info.to``, but only the bounced_recipient
    actually bounced, and bounce handling must act on that address alone.

    ZeptoMail's live webhook format wraps type values in arrays
    (``"event_name": ["softbounce"]``), so list values under type keys are
    collected item-by-item, not just bare strings.
    """
    if isinstance(node, dict):
        for k, v in node.items():
            kl = k.lower()
            if kl in _TYPE_KEYS:
                if isinstance(v, str):
                    types.append(v.lower())
                elif isinstance(v, (list, tuple)):
                    types.extend(s.lower() for s in v if isinstance(s, str))
            if reasons is not None and kl in _REASON_KEYS and isinstance(v, str) and v.strip():
                reasons.append(v.strip())
            if kl in _RECIPIENT_KEYS:
                _emails_from(v, recipients)
                if bounced is not None and kl == 'bounced_recipient':
                    _emails_from(v, bounced)
            _gather_bounce(v, types, recipients, reasons, bounced)
    elif isinstance(node, (list, tuple)):
        for item in node:
            _gather_bounce(item, types, recipients, reasons, bounced)


def _classify_bounce(types):
    """Classify the collected type signals.

    Returns one of: 'complaint', 'hard', 'soft', 'engagement', or None
    (no recognizable signal). Order matters — 'soft bounce' contains both
    'soft' and 'bounce', so soft is checked before hard."""
    blob = ' '.join(types)
    if not blob:
        return None
    if any(s in blob for s in ('complaint', 'spam', 'abuse', 'feedback')):
        return 'complaint'
    if any(s in blob for s in ('open', 'click')):
        return 'engagement'
    if any(s in blob for s in ('soft', 'defer', 'delay', 'transient', 'temporary')):
        return 'soft'
    if any(s in blob for s in ('hard', 'bounce', 'invalid', 'block',
                               'undeliver', 'dropped', 'fail')):
        return 'hard'
    return None


def _soft_bounce_threshold():
    """Soft-bounce strikes before a CRM contact is auto-suppressed."""
    try:
        return max(1, int(os.environ.get('SOFT_BOUNCE_SUPPRESS_THRESHOLD', '3')))
    except (TypeError, ValueError):
        return 3


def _webhook_authorized(secret, data):
    """True if the configured secret is presented via header, query, bearer, or
    a known payload key (ZeptoMail's auth-key mechanism varies)."""
    auth = request.headers.get('Authorization', '')
    if auth.lower().startswith('bearer '):
        auth = auth[7:]
    provided = (request.headers.get('X-Webhook-Token')
                or auth or request.args.get('token', '')).strip()
    if provided and provided == secret:
        return True
    if isinstance(data, dict):
        for k in _AUTH_KEYS:
            v = data.get(k)
            if isinstance(v, str) and v.strip() == secret:
                return True
    return False


def _commit_webhook():
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        log.exception('Failed to commit ZeptoMail webhook updates')


@webhook_api.route('/zeptomail', methods=['POST'])
def zeptomail_webhook():
    """React to ZeptoMail soft/hard bounces, complaints, opens and clicks.

    Hard bounces and complaints suppress immediately; soft bounces accrue
    strikes on the CRM contact and only suppress past a threshold; opens/clicks
    clear those strikes. Always returns 200 so ZeptoMail won't retry-storm."""
    data = request.get_json(silent=True) or {}
    secret = (current_app.config.get('ZEPTOMAIL_WEBHOOK_SECRET') or '').strip()
    if secret and not _webhook_authorized(secret, data):
        log.warning('ZeptoMail webhook rejected: bad/missing token')
        return jsonify({'error': 'unauthorized'}), 403

    types, recipients, reasons, bounced = [], set(), [], set()
    _gather_bounce(data, types, recipients, reasons, bounced)
    kind = _classify_bounce(types)
    if not kind or not recipients:
        # Unknown shape / no recipient — acknowledge (so ZeptoMail doesn't
        # retry-storm), but leave a trail: a payload that LOOKS like an event
        # yet doesn't classify means their format drifted and we're silently
        # dropping data.
        if data:
            log.warning('ZeptoMail webhook: unrecognized payload — kind=%s '
                        'recipients=%d keys=%s types=%s',
                        kind, len(recipients), sorted(data)[:8], types[:8])
        return jsonify({'status': 'ok', 'suppressed': 0}), 200

    # Never act on our own sending identities, even if they appear as a
    # recipient (e.g. a test send to ourselves that bounced).
    own = {a.strip().lower() for a in (
        current_app.config.get('CRM_FROM_EMAIL') or '',
        current_app.config.get('ZEPTOMAIL_FROM_EMAIL') or '',
        current_app.config.get('MAIL_DEFAULT_SENDER') or '',
    ) if a}
    # Bounce/complaint payloads list every To recipient under email_info.to but
    # only bounced_recipient actually failed — act on those alone when present,
    # so a co-recipient on the same email is never suppressed.
    pool = bounced if (kind != 'engagement' and bounced) else recipients
    targets = sorted(e for e in pool if e not in own)
    reason = reasons[0][:255] if reasons else None

    from app.models import EmailUnsubscribe
    from app.crm.models import Contact, CrmEmailEvent, Activity
    now = datetime.now(timezone.utc)

    def _contacts(email):
        return Contact.query.filter(Contact.email.ilike(email)).all()

    def _log_event(email, event_type, contacts):
        """Persist the event for the deliverability dashboard (history — the
        Contact columns only hold the latest state)."""
        db.session.add(CrmEmailEvent(
            email=email[:120], event_type=event_type,
            reason=reason,
            contact_id=contacts[0].id if contacts else None))

    # Open/click proves the address is alive — clear soft-bounce strikes.
    if kind == 'engagement':
        etype = 'click' if 'click' in ' '.join(types) else 'open'
        recovered = 0
        for email in targets:
            contacts = _contacts(email)
            _log_event(email, etype, contacts)
            for c in contacts:
                if c.soft_bounce_count:
                    c.soft_bounce_count = 0
                    recovered += 1
        _commit_webhook()
        return jsonify({'status': 'ok', 'suppressed': 0, 'recovered': recovered}), 200

    threshold = _soft_bounce_threshold()
    added = 0          # addresses newly added to the global suppression list
    soft_recorded = 0  # soft-bounce strikes recorded on CRM contacts
    def _log_bounce_activity(contact, label):
        """Put the bounce on the contact's CRM timeline so it's visible in the
        BDR agent's context (draft_followups reads recent timeline entries)."""
        desc = f'Email {label}'
        if reason:
            desc += f' — {reason}'
        db.session.add(Activity(kind='bounce', description=desc[:400],
                                contact_id=contact.id, user_id=None))

    for email in targets:
        contacts = _contacts(email)
        try:
            if kind == 'soft':
                _log_event(email, 'soft', contacts)
                if contacts:
                    soft_recorded += 1
                escalate = False
                for c in contacts:
                    c.soft_bounce_count = (c.soft_bounce_count or 0) + 1
                    c.last_bounce_at = now
                    c.last_bounce_type = 'soft'
                    c.last_bounce_reason = reason
                    _log_bounce_activity(
                        c, f'soft-bounced (strike {c.soft_bounce_count} of {threshold})')
                    if c.soft_bounce_count >= threshold:
                        c.email_opt_out = True
                        escalate = True
                if escalate and not EmailUnsubscribe.query.filter_by(email=email).first():
                    db.session.add(EmailUnsubscribe(email=email, source='soft_bounce'))
                    added += 1
            else:
                # Hard bounce or complaint — suppress now.
                btype = 'complaint' if kind == 'complaint' else 'hard'
                src = 'complaint' if kind == 'complaint' else 'bounce'
                _log_event(email, btype, contacts)
                if not EmailUnsubscribe.query.filter_by(email=email).first():
                    db.session.add(EmailUnsubscribe(email=email, source=src))
                    added += 1
                for c in contacts:
                    c.email_opt_out = True
                    c.last_bounce_at = now
                    c.last_bounce_type = btype
                    c.last_bounce_reason = reason
                    _log_bounce_activity(
                        c, 'hard-bounced — address suppressed' if btype == 'hard'
                        else 'flagged as spam complaint — address suppressed')
        except Exception:
            log.exception('Failed to process bounced address %s', email)
    _commit_webhook()
    log.info('ZeptoMail webhook: %s — suppressed %d, soft-recorded %d', kind, added, soft_recorded)
    return jsonify({'status': 'ok', 'suppressed': added, 'soft_recorded': soft_recorded}), 200
