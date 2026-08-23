"""Webhook handlers — Stripe events + ZeptoMail bounce/complaint notifications."""
import logging
import os
import re
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, current_app
from app import db
from app import garden_finance
from app import stripe_service
from app.api.notifications_api import notify as notify_user

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
            # Handlers take the whole event as well as its object: Connect
            # events (payouts, account.updated) identify the garden manager
            # ONLY through the top-level `account` field, which isn't on the
            # object itself.
            handler(data_obj, event)
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


#: Read a field off a Stripe object that may be a dict or an SDK object.
#: Defined in garden_finance so the backfill CLI reads objects the same way.
_get = garden_finance.field


def _int_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _event_account(event):
    """The connected account a Connect event came from (``acct_...``), or ''.

    Platform events (a destination charge, a subscription) carry no
    ``account``; events forwarded from a connected account — payouts and
    ``account.updated`` — do, and it is the only link back to the manager.
    """
    return _get(event, 'account', '') or ''


def _latest_charge_id(pi):
    """The charge behind a PaymentIntent, across API versions.

    Newer versions expose ``latest_charge`` (id or expanded object); older
    ones nest ``charges.data[0]``. Refunds and disputes arrive keyed by charge
    id, so without this the money that came in and the money that went back
    out can never be joined.
    """
    latest = _get(pi, 'latest_charge')
    if isinstance(latest, str) and latest:
        return latest
    if latest is not None:
        cid = _get(latest, 'id')
        if cid:
            return cid
    charges = _get(pi, 'charges') or {}
    data = _get(charges, 'data') or []
    return _get(data[0], 'id') if data else None


def _destination_account(pi):
    """The connected account a destination charge routes to."""
    transfer_data = _get(pi, 'transfer_data') or {}
    return _get(transfer_data, 'destination') or _get(pi, 'on_behalf_of') or None


def _payer_name(meta):
    """Display name for whoever paid, from the PI metadata user ids."""
    from app.models import User
    uid = _int_or_none(meta.get('payer_user_id') or meta.get('user_id'))
    if not uid:
        return None
    user = db.session.get(User, uid)
    return (user.display_name or user.username) if user else None


def _organizer_link(garden, sub='stripe'):
    """Deep link straight to the garden's Stripe money feed.

    ``sub`` is the finance sub-tab the dashboard reads off the query string —
    see FINANCE_SUBTABS in GardenAdminDashboard.jsx.
    """
    return '/gardens/%s/admin/finance?sub=%s' % (garden.public_id or garden.id, sub)


def handle_payment_intent_succeeded(pi, event=None):
    """Webhook-driven fulfillment for a succeeded PaymentIntent.

    Routes by metadata.type: marketplace orders are marked paid (their backup
    confirmation), and garden money (online dues, in-person dues, ad-hoc
    in-person sales) is both fulfilled and written to the garden's finance
    ledger here, so neither collection nor visibility depends on a client
    calling back. Idempotent: guards on current state so repeated deliveries
    are no-ops.
    """
    pi_id = pi.get('id', '') if isinstance(pi, dict) else pi.id
    meta = _pi_metadata(pi)
    pi_type = meta.get('type', '')

    if pi_type in garden_finance.PI_TYPE_TO_SOURCE:
        # Every garden collection gets a ledger row — including the ad-hoc
        # Tap-to-Pay sales that previously left no trace anywhere in
        # YardHarvest, and the in-person dues taps whose fulfillment used to
        # depend entirely on the iOS app getting its finalize call through.
        _record_garden_payment(pi, meta, event)
        if pi_type in ('garden_dues', 'garden_dues_in_person'):
            _fulfill_dues_from_pi(pi_id, meta,
                                  in_person=pi_type.endswith('_in_person'))
        db.session.commit()
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


def _fulfill_dues_from_pi(pi_id, meta, in_person=False):
    """Mark a GardenDuesRecord paid from its PaymentIntent. Idempotent.

    ``in_person`` records the tap as ``tap_to_pay`` rather than ``online`` so
    the roster shows how the money was actually taken. This path is the
    guarantee for Tap to Pay the same way it already was for the web: the iOS
    finalize call is the fast path, but a dropped connection at the plot gate
    used to leave a paid member marked unpaid, because no webhook route
    existed for ``garden_dues_in_person`` at all.
    """
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
    rec.payment_method = 'tap_to_pay' if in_person else 'online'
    rec.payment_date = date.today()
    rec.stripe_payment_intent_id = pi_id
    rec.payment_note = (f'Stripe Terminal (Tap to Pay): {pi_id}' if in_person
                        else f'Stripe: {pi_id}')
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
                body=(f'{payer_name} paid ${rec.amount_due:.2f} for '
                      f'{rec.season_year} season dues '
                      f'{"in person" if in_person else "online"}.'),
                link=f'/gardens/{garden.public_id}/admin/finance',
                garden_id=rec.garden_id,
            )
            db.session.commit()
    except Exception:
        log.exception('Failed to notify organizer of dues payment for rec %s', dues_id)


def _record_garden_payment(pi, meta, event=None, failed=False):
    """Write a garden collection (or a failed one) to the finance ledger.

    Returns the ledger row, or None when the PaymentIntent can't be tied to a
    garden — which is the normal outcome for marketplace charges and for
    metadata written by an older build.
    """
    from app.models import CommunityGarden

    garden_id = _int_or_none(meta.get('garden_id'))
    if not garden_id:
        return None
    garden = db.session.get(CommunityGarden, garden_id)
    if not garden:
        return None

    source = garden_finance.PI_TYPE_TO_SOURCE.get(meta.get('type'), 'stripe')
    amount = _get(pi, 'amount_received') or _get(pi, 'amount') or 0
    description = _get(pi, 'description') or meta.get('memo') or None
    status = 'succeeded'
    if failed:
        err = _get(pi, 'last_payment_error') or {}
        status = _get(err, 'code') or 'failed'
        description = _get(err, 'message') or description
        # A failed intent never received anything; `amount` is what was asked.
        amount = _get(pi, 'amount') or 0

    # What Stripe itself took, read from the connected account's balance
    # transaction rather than assumed. Costs one API call per payment, and
    # returns None (recorded as "not known") rather than a guess if anything
    # goes wrong — the backfill command fills those in later.
    charge_id = _latest_charge_id(pi)
    destination = _destination_account(pi)
    stripe_fee = None
    if not failed and charge_id and destination and stripe_service.is_configured():
        try:
            stripe_fee, _net = stripe_service.connected_charge_fee(
                charge_id, destination)
        except Exception:
            log.exception('Stripe fee lookup failed for %s', charge_id)

    ev, _created = garden_finance.record(
        'payment_failed' if failed else 'payment',
        garden_id=garden_id,
        stripe_object_id=_get(pi, 'id') or '',
        source=source,
        status=status,
        amount_cents=amount,
        fee_cents=0 if failed else (_get(pi, 'application_fee_amount') or 0),
        stripe_fee_cents=stripe_fee,
        currency=_get(pi, 'currency') or 'usd',
        description=description,
        counterparty=_payer_name(meta),
        dues_id=_int_or_none(meta.get('dues_id')),
        collected_by_id=_int_or_none(meta.get('collected_by_user_id')),
        stripe_charge_id=charge_id,
        stripe_event_id=_get(event, 'id') or '',
        connected_account_id=destination,
        occurred_at=garden_finance.from_stripe_ts(_get(pi, 'created')),
    )
    return ev


def handle_payment_intent_failed(pi, event=None):
    """Mark an order payment failed, or ledger a failed garden collection.

    A declined tap at the plot gate is worth recording: the manager saw an
    error on the phone and needs somewhere to check whether the money ever
    arrived.
    """
    from app.models import Order
    pi_id = pi.get('id', '') if isinstance(pi, dict) else pi.id

    meta = _pi_metadata(pi)
    if meta.get('type') in garden_finance.PI_TYPE_TO_SOURCE:
        _record_garden_payment(pi, meta, event, failed=True)
        db.session.commit()
        return

    orders = Order.query.filter_by(stripe_payment_intent_id=pi_id).all()
    for order in orders:
        order.payment_status = 'failed'
    if orders:
        db.session.commit()


def handle_subscription_updated(sub, event=None):
    """Sync GardenSubscription status and period dates from Stripe.

    Also the activation-of-last-resort: a local row only learns its
    stripe_subscription_id in /subscribe, which the buyer's browser may never
    reach after paying. When no local row matches the Stripe id, fall back to
    metadata.garden_id (stamped at creation in create_checkout) and adopt the
    subscription — so a PAID subscription always activates locally.
    """
    from app.models import GardenSubscription, CommunityGarden

    def _get(key, default=None):
        return sub.get(key, default) if isinstance(sub, dict) else getattr(sub, key, default)

    sub_id = _get('id', '')
    status = _get('status', '')
    meta = _get('metadata', {}) or {}
    if not isinstance(meta, dict):
        meta = dict(meta)

    gs = GardenSubscription.query.filter_by(stripe_subscription_id=sub_id).first()
    newly_adopted = False
    if not gs:
        # Fallback path. Only garden_pro subscriptions, and only once Stripe
        # says the money side is real — never adopt the 'incomplete' shell
        # create_checkout makes before payment confirmation.
        if meta.get('type') != 'garden_pro' or not meta.get('garden_id'):
            return
        if status not in ('active', 'trialing', 'past_due'):
            return
        try:
            garden_id = int(meta['garden_id'])
        except (TypeError, ValueError):
            return
        if not db.session.get(CommunityGarden, garden_id):
            return
        gs = GardenSubscription.query.filter_by(garden_id=garden_id).first()
        if gs is None:
            gs = GardenSubscription(garden_id=garden_id)
            db.session.add(gs)
        elif gs.stripe_subscription_id and gs.stripe_subscription_id != sub_id:
            # Row already bound to a different Stripe subscription — don't
            # silently rebind; that one's updates arrive under its own id.
            log.warning('Stripe sub %s carries garden_id=%s but that garden is '
                        'bound to %s; ignoring', sub_id, garden_id,
                        gs.stripe_subscription_id)
            return
        gs.stripe_subscription_id = sub_id
        if meta.get('billing_cycle') in ('monthly', 'yearly'):
            gs.billing_cycle = meta['billing_cycle']
        gs.payment_reference = gs.payment_reference or sub_id
        newly_adopted = True

    gs.status = status
    period_start = _get('current_period_start')
    period_end = _get('current_period_end')
    if period_start:
        gs.current_period_start = datetime.fromtimestamp(period_start, tz=timezone.utc)
    if period_end:
        gs.current_period_end = datetime.fromtimestamp(period_end, tz=timezone.utc)
    gs.cancel_at_period_end = bool(_get('cancel_at_period_end', False))

    garden = db.session.get(CommunityGarden, gs.garden_id)
    if garden:
        garden.subscription_status = 'active' if status == 'active' else status
    db.session.commit()

    if newly_adopted and status == 'active' and garden:
        try:
            from app.email_service import send_operator_conversion_ping
            send_operator_conversion_ping('paid', garden, garden.organizer)
            from app.crm.autonomy import record_platform_event
            record_platform_event('paid', garden, garden.organizer)
        except Exception:
            log.exception('Operator paid-conversion ping failed for garden %d', gs.garden_id)


def handle_subscription_deleted(sub, event=None):
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


def handle_invoice_payment_failed(invoice, event=None):
    """Set subscription to past_due and send dunning email."""
    from app.models import GardenSubscription, CommunityGarden
    sub_id = invoice.get('subscription', '') if isinstance(invoice, dict) else getattr(invoice, 'subscription', '')
    if not sub_id:
        return

    gs = GardenSubscription.query.filter_by(stripe_subscription_id=sub_id).first()
    if not gs:
        return

    was_past_due = gs.status == 'past_due'
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

    # Operator ping only on the TRANSITION to past_due — Stripe retries the
    # invoice for days and each attempt is a fresh event id, so without the
    # guard the operator would get one ping per retry.
    if garden and not was_past_due:
        try:
            from app.email_service import send_operator_conversion_ping
            send_operator_conversion_ping('past_due', garden, garden.organizer)
            from app.crm.autonomy import record_platform_event
            record_platform_event('past_due', garden, garden.organizer)
        except Exception:
            log.exception('Operator past-due ping failed for garden %d', gs.garden_id)


def _organizer_gardens(user):
    """Gardens this user organizes, oldest first."""
    from app.models import CommunityGarden
    if not user:
        return []
    return (CommunityGarden.query.filter_by(organizer_id=user.id)
            .order_by(CommunityGarden.id).all())


def handle_account_updated(account, event=None):
    """Mirror the connected account's health, and tell the manager when it slips.

    Previously this only ever latched ``stripe_onboarding_complete`` to True.
    Stripe disabling an account - a verification deadline passing, a document
    going stale - was invisible until a tap failed in front of a member. Now
    both directions are recorded, the current requirements are stored for the
    finance screens, and a fall out of good standing raises a notification
    while it can still be fixed.

    The mirroring itself lives in ``garden_finance.sync_account`` so the
    backfill CLI produces identical state; this handler adds only the part
    specific to an event arriving - deciding whether the change is worth
    telling someone about.
    """
    from app.models import User

    acct_id = _get(account, 'id') or ''
    user = User.query.filter_by(stripe_connect_account_id=acct_id).first()
    if not user:
        return

    before, after = garden_finance.sync_account(
        user, account, event_id=_get(event, 'id') or '')
    db.session.commit()

    if after == before or after == 'not_started':
        return
    gardens = _organizer_gardens(user)
    if not gardens:
        return
    title, body = garden_finance.ACCOUNT_STATE_NOTICES[after]
    try:
        notify_user(user.id, 'stripe_account', title, body,
                    _organizer_link(gardens[0], 'stripe'), gardens[0].id)
        db.session.commit()
    except Exception:
        db.session.rollback()
        log.exception('Failed to notify %s of Connect account state %s',
                      user.id, after)


def handle_transfer_created(transfer, event=None):
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


def handle_charge_refunded(charge, event=None):
    """Sync refund status when a refund is issued from Stripe Dashboard."""
    from app.models import Order, Refund
    pi_id = charge.get('payment_intent', '') if isinstance(charge, dict) else getattr(charge, 'payment_intent', '')

    # Garden money first — a refund issued from the Stripe dashboard was
    # previously invisible here, so a member could be refunded and still show
    # as paid on the roster forever.
    if _record_garden_refund(charge, event):
        return
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


def _record_garden_refund(charge, event=None):
    """Ledger a refund against a garden payment. True if it was ours.

    Stripe reports ``amount_refunded`` cumulatively, so the ledger row is
    upserted on the charge id — two partial refunds leave one row holding the
    running total rather than two rows that add up to more than was ever
    charged.
    """
    charge_id = _get(charge, 'id') or ''
    pi_id = _get(charge, 'payment_intent') or ''
    paid = garden_finance.find_payment(payment_intent_id=pi_id, charge_id=charge_id)
    if not paid or not paid.garden_id:
        return False

    refunded = _get(charge, 'amount_refunded') or 0
    if refunded <= 0:
        return False
    charged = _get(charge, 'amount') or paid.amount_cents or 0
    full = refunded >= charged > 0

    garden_finance.record(
        'refund', garden_id=paid.garden_id,
        stripe_object_id=charge_id or pi_id,
        source=paid.source, status='full' if full else 'partial',
        amount_cents=refunded, currency=_get(charge, 'currency') or paid.currency,
        description=('Refund issued in Stripe' if full
                     else 'Partial refund issued in Stripe'),
        counterparty=paid.counterparty, dues_id=paid.dues_id,
        stripe_charge_id=charge_id, stripe_event_id=_get(event, 'id') or '',
        connected_account_id=paid.connected_account_id,
    )
    if full and paid.dues_id:
        _unsettle_refunded_dues(paid)
    db.session.commit()
    return True


def _unsettle_refunded_dues(paid):
    """Put a fully-refunded dues record back on the roster as owing.

    Leaving it marked paid would quietly turn a refund into forgiven dues —
    the roster is what the manager chases from, so it has to match the money.
    """
    from app.models import CommunityGarden, GardenDuesRecord
    rec = db.session.get(GardenDuesRecord, paid.dues_id)
    if not rec or rec.status != 'paid':
        return
    if rec.stripe_payment_intent_id and rec.stripe_payment_intent_id != paid.stripe_object_id:
        return  # settled by a different payment; leave it alone
    rec.status = 'unpaid'
    rec.amount_paid = 0
    rec.payment_date = None
    rec.payment_note = 'Refunded in Stripe (%s)' % paid.stripe_object_id

    garden = db.session.get(CommunityGarden, rec.garden_id)
    if garden:
        notify_user(garden.organizer_id, 'dues_refunded',
                    'Dues payment refunded',
                    'A $%.2f dues payment for %s was refunded in Stripe, so '
                    'the record is unpaid again.' % (rec.amount_due, rec.season_year),
                    _organizer_link(garden, 'stripe'), garden.id)


def handle_charge_dispute(dispute, event=None):
    """A cardholder disputed a garden charge, or the dispute closed.

    Chargebacks are the one money event a manager cannot afford to learn
    about late: Stripe pulls the funds back immediately and the window to
    submit evidence is days, not weeks.
    """
    charge_id = _get(dispute, 'charge') or ''
    pi_id = _get(dispute, 'payment_intent') or ''
    paid = garden_finance.find_payment(payment_intent_id=pi_id, charge_id=charge_id)
    if not paid or not paid.garden_id:
        return

    raw_status = (_get(dispute, 'status') or '').lower()
    status = raw_status if raw_status in ('won', 'lost') else 'needs_response'
    amount = _get(dispute, 'amount') or paid.amount_cents or 0
    reason = _get(dispute, 'reason') or None

    _ev, created = garden_finance.record(
        'dispute', garden_id=paid.garden_id,
        stripe_object_id=_get(dispute, 'id') or charge_id,
        source=paid.source, status=status, amount_cents=amount,
        currency=_get(dispute, 'currency') or paid.currency,
        description=('Reason: %s' % reason) if reason else None,
        counterparty=paid.counterparty, dues_id=paid.dues_id,
        stripe_charge_id=charge_id, stripe_event_id=_get(event, 'id') or '',
        connected_account_id=paid.connected_account_id,
    )
    db.session.commit()

    from app.models import CommunityGarden
    garden = db.session.get(CommunityGarden, paid.garden_id)
    if not garden:
        return
    money = amount / 100.0
    if created and status == 'needs_response':
        title = 'Payment disputed'
        body = ('A $%.2f payment was disputed by the cardholder. Respond in '
                'your Stripe dashboard before the deadline or the funds stay '
                'withdrawn.' % money)
    elif status == 'lost':
        title = 'Dispute lost'
        body = 'The $%.2f disputed payment was decided against you.' % money
    elif status == 'won':
        title = 'Dispute resolved in your favor'
        body = 'The $%.2f disputed payment was returned to you.' % money
    else:
        return
    try:
        notify_user(garden.organizer_id, 'payment_dispute', title, body,
                    _organizer_link(garden, 'stripe'), garden.id)
        db.session.commit()
    except Exception:
        db.session.rollback()
        log.exception('Failed to notify garden %s of dispute', garden.id)


def handle_payout(payout, event=None):
    """A Stripe payout to the manager's bank moved.

    This is a **Connect** event: it is emitted by the connected account, not
    the platform, so ``event.account`` is the only thing tying it to a garden
    manager. Without it, "when does the money actually reach my bank" had no
    answer inside YardHarvest at all.
    """
    acct_id = _event_account(event) or _get(payout, 'account') or ''
    owner = garden_finance.account_owner(acct_id)
    if not owner:
        return

    _ev, _created, status = garden_finance.record_payout(
        owner.id, payout, event_id=_get(event, 'id') or '',
        connected_account_id=acct_id)
    db.session.commit()

    if status == 'in_transit':
        return
    gardens = _organizer_gardens(owner)
    if not gardens:
        return
    pretty = format((_get(payout, 'amount') or 0) / 100.0, ',.2f')
    if status == 'paid':
        title = 'Money deposited'
        body = ('$%s from your garden collections landed in your bank '
                'account.' % pretty)
    else:
        title = 'Payout failed'
        body = ('Stripe could not deposit $%s. ' % pretty) + (
            _get(payout, 'failure_message')
            or 'Check your bank details in Stripe.')
    try:
        notify_user(owner.id, 'payout', title, body,
                    _organizer_link(gardens[0], 'stripe'), gardens[0].id)
        db.session.commit()
    except Exception:
        db.session.rollback()
        log.exception('Failed to notify %s of payout %s', owner.id, status)


EVENT_HANDLERS = {
    'payment_intent.succeeded': handle_payment_intent_succeeded,
    'payment_intent.payment_failed': handle_payment_intent_failed,
    'customer.subscription.created': handle_subscription_updated,
    'customer.subscription.updated': handle_subscription_updated,
    'customer.subscription.deleted': handle_subscription_deleted,
    'invoice.payment_failed': handle_invoice_payment_failed,
    'account.updated': handle_account_updated,
    'transfer.created': handle_transfer_created,
    'charge.refunded': handle_charge_refunded,
    # Chargebacks on garden money. `updated` is included so a dispute that
    # changes state without closing still refreshes what the manager sees.
    'charge.dispute.created': handle_charge_dispute,
    'charge.dispute.updated': handle_charge_dispute,
    'charge.dispute.closed': handle_charge_dispute,
    # Connect events - delivered only to an endpoint that listens on
    # connected accounts. See docs/integrations/stripe-webhooks.md.
    'payout.created': handle_payout,
    'payout.paid': handle_payout,
    'payout.failed': handle_payout,
}

#: Events Stripe only delivers to an endpoint that listens on **connected
#: accounts**. Enabling them on the platform endpoint alone means they never
#: arrive — silently, which is how "why can't I see my payouts" happens.
#: /api/health/stripe/webhooks reports these separately for that reason.
CONNECT_EVENTS = frozenset({'account.updated', 'payout.created',
                            'payout.paid', 'payout.failed'})


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
