"""Garden money ledger — read/write helpers over :class:`GardenFinanceEvent`.

The webhook path writes here; the garden-admin API reads. Keeping both sides
in one module means the vocabulary (kinds, sources, statuses, the label a
manager actually reads) is defined once — the alternative is the drift we've
already paid for elsewhere, where the same rule written in three files
quietly disagreed with itself.

Nothing in here calls Stripe. Every value is either something a webhook told
us or something derived from it, so the finance screens stay fast and keep
working when Stripe is slow.
"""
import json
import logging
from datetime import datetime, timedelta, timezone

from app import db

log = logging.getLogger(__name__)

# ---- Vocabulary ------------------------------------------------------------

KINDS = ('payment', 'payment_failed', 'refund', 'dispute', 'payout', 'account')

#: Where the money came from. `stripe` covers account-level rows (payouts,
#: account status) that aren't tied to one collection.
SOURCES = ('dues_online', 'dues_in_person', 'in_person_sale', 'stripe')

#: PaymentIntent `metadata.type` -> ledger source. The metadata keys are set
#: in gardens_api (online dues) and garden_admin_api (the two in-person
#: flows); this map is the only place that translation lives.
PI_TYPE_TO_SOURCE = {
    'garden_dues': 'dues_online',
    'garden_dues_in_person': 'dues_in_person',
    'garden_in_person_sale': 'in_person_sale',
}

SOURCE_LABELS = {
    'dues_online': 'Dues paid online',
    'dues_in_person': 'Dues collected in person',
    'in_person_sale': 'In-person sale',
    'stripe': 'Stripe',
}


def _utcnow():
    return datetime.now(timezone.utc)


def _naive(dt):
    """Store naive-UTC to match every other datetime column in the app."""
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt


def from_stripe_ts(ts):
    """Stripe epoch seconds -> naive-UTC datetime (None-safe)."""
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).replace(tzinfo=None)
    except (TypeError, ValueError, OSError):
        return None


# ---- Writing ---------------------------------------------------------------

def record(kind, *, garden_id=None, user_id=None, stripe_object_id=None,
           source='stripe', status=None, amount_cents=0, fee_cents=0,
           currency='usd', description=None, counterparty=None, dues_id=None,
           collected_by_id=None, stripe_charge_id=None, stripe_event_id=None,
           connected_account_id=None, occurred_at=None):
    """Upsert one ledger row. Returns ``(event, created)``.

    The upsert key is ``(kind, stripe_object_id)`` within the same scope. It
    has to be an upsert rather than an insert because Stripe reports several
    of these cumulatively: a second partial refund on the same charge arrives
    as a fresh event carrying the *total* ``amount_refunded``, and inserting
    it would double-count money the garden never lost.

    The caller commits. Handlers are already wrapped in the webhook's
    rollback-on-error, and batching the commit keeps a payment and its dues
    settlement in one transaction.
    """
    from app.models import GardenFinanceEvent

    if kind not in KINDS:
        raise ValueError('unknown finance event kind: %r' % (kind,))
    if garden_id is None and user_id is None:
        raise ValueError('a finance event needs a garden or an account owner')

    ev = None
    if stripe_object_id:
        q = GardenFinanceEvent.query.filter_by(kind=kind,
                                               stripe_object_id=stripe_object_id)
        q = q.filter_by(garden_id=garden_id) if garden_id else q.filter_by(user_id=user_id)
        ev = q.first()

    created = ev is None
    if created:
        ev = GardenFinanceEvent(kind=kind, garden_id=garden_id, user_id=user_id,
                                stripe_object_id=stripe_object_id)
        db.session.add(ev)

    ev.source = source or ev.source or 'stripe'
    ev.status = status
    ev.amount_cents = int(amount_cents or 0)
    ev.fee_cents = int(fee_cents or 0)
    ev.net_cents = ev.amount_cents - ev.fee_cents
    ev.currency = (currency or 'usd')[:10]
    if description:
        ev.description = description[:300]
    if counterparty:
        ev.counterparty = counterparty[:160]
    if dues_id:
        ev.dues_id = dues_id
    if collected_by_id:
        ev.collected_by_id = collected_by_id
    if stripe_charge_id:
        ev.stripe_charge_id = stripe_charge_id[:255]
    if stripe_event_id:
        ev.stripe_event_id = stripe_event_id[:255]
    if connected_account_id:
        ev.connected_account_id = connected_account_id[:255]
    ev.occurred_at = _naive(occurred_at) or _utcnow().replace(tzinfo=None)
    return ev, created


def find_payment(*, payment_intent_id=None, charge_id=None):
    """The `payment` row a refund or dispute belongs to, if we saw the charge.

    Disputes arrive carrying a charge id and (depending on API version) a
    payment-intent id, but never the garden metadata — so the only reliable
    way back to a garden is the payment row we wrote when the money came in.
    """
    from app.models import GardenFinanceEvent
    q = GardenFinanceEvent.query.filter_by(kind='payment')
    if payment_intent_id:
        row = q.filter_by(stripe_object_id=payment_intent_id).first()
        if row:
            return row
    if charge_id:
        return q.filter_by(stripe_charge_id=charge_id).first()
    return None


def account_owner(connected_account_id):
    """The user whose Connect account this is, or None."""
    if not connected_account_id:
        return None
    from app.models import User
    return User.query.filter_by(
        stripe_connect_account_id=connected_account_id).first()


# ---- Reading ---------------------------------------------------------------

def activity_query(garden, *, kinds=None, since=None):
    """Everything a manager should see on one garden's money feed.

    Deliberately a union of two scopes: the garden's own payments plus the
    organizer's account-level payouts and status changes. A manager asking
    "where's my money" needs both halves — the collection and the deposit —
    and they live at different scopes in Stripe.
    """
    from app.models import GardenFinanceEvent
    scope = [GardenFinanceEvent.garden_id == garden.id]
    if garden.organizer_id:
        scope.append(db.and_(GardenFinanceEvent.garden_id.is_(None),
                             GardenFinanceEvent.user_id == garden.organizer_id))
    q = GardenFinanceEvent.query.filter(db.or_(*scope))
    if kinds:
        q = q.filter(GardenFinanceEvent.kind.in_(list(kinds)))
    if since:
        q = q.filter(GardenFinanceEvent.occurred_at >= _naive(since))
    return q.order_by(GardenFinanceEvent.occurred_at.desc(),
                      GardenFinanceEvent.id.desc())


def label_for(ev):
    """One line a manager can read without knowing Stripe's vocabulary."""
    money = '$%s' % format((ev.amount_cents or 0) / 100.0, ',.2f')
    if ev.kind == 'payment':
        who = ' - %s' % ev.counterparty if ev.counterparty else ''
        return '%s %s%s' % (SOURCE_LABELS.get(ev.source, 'Payment'), money, who)
    if ev.kind == 'payment_failed':
        return 'Payment of %s did not go through' % money
    if ev.kind == 'refund':
        return 'Refunded %s' % money
    if ev.kind == 'dispute':
        if ev.status == 'won':
            return 'Chargeback for %s resolved in your favor' % money
        if ev.status == 'lost':
            return 'Chargeback for %s lost - funds withdrawn' % money
        return 'Chargeback opened for %s - response needed' % money
    if ev.kind == 'payout':
        if ev.status == 'failed':
            return 'Payout of %s to your bank failed' % money
        if ev.status == 'in_transit':
            return '%s on the way to your bank' % money
        return '%s deposited to your bank' % money
    if ev.kind == 'account':
        if ev.status == 'restricted':
            return 'Stripe has restricted this account'
        if ev.status == 'action_needed':
            return 'Stripe needs more information before you can be paid'
        return 'Stripe account is in good standing'
    return ev.description or ev.kind


def to_dict(ev):
    return {
        'id': ev.id,
        'kind': ev.kind,
        'source': ev.source,
        'status': ev.status,
        'scope': 'garden' if ev.garden_id else 'account',
        'label': label_for(ev),
        'amount': round((ev.amount_cents or 0) / 100.0, 2),
        'fee': round((ev.fee_cents or 0) / 100.0, 2),
        'net': round((ev.net_cents or 0) / 100.0, 2),
        'currency': ev.currency,
        'description': ev.description,
        'counterparty': ev.counterparty,
        'dues_id': ev.dues_id,
        'stripe_object_id': ev.stripe_object_id,
        'occurred_at': ev.occurred_at.isoformat() if ev.occurred_at else None,
    }


def totals(garden_id, *, since=None, until=None):
    """Garden-scoped money totals. Account-level payout rows are excluded on
    purpose — see the model docstring."""
    from app.models import GardenFinanceEvent
    q = GardenFinanceEvent.query.filter(GardenFinanceEvent.garden_id == garden_id)
    if since:
        q = q.filter(GardenFinanceEvent.occurred_at >= _naive(since))
    if until:
        q = q.filter(GardenFinanceEvent.occurred_at <= _naive(until))

    cents = {'collected': 0, 'fees': 0, 'net': 0, 'refunded': 0, 'disputed': 0}
    by_source = {'dues_online': 0, 'dues_in_person': 0, 'in_person_sale': 0}
    payments = failed = 0
    for ev in q.all():
        if ev.kind == 'payment':
            cents['collected'] += ev.amount_cents or 0
            cents['fees'] += ev.fee_cents or 0
            cents['net'] += ev.net_cents or 0
            payments += 1
            if ev.source in by_source:
                by_source[ev.source] += ev.amount_cents or 0
        elif ev.kind == 'refund':
            cents['refunded'] += ev.amount_cents or 0
        elif ev.kind == 'dispute' and ev.status != 'won':
            cents['disputed'] += ev.amount_cents or 0
        elif ev.kind == 'payment_failed':
            failed += 1

    out = {k: round(v / 100.0, 2) for k, v in cents.items()}
    out['by_source'] = {k: round(v / 100.0, 2) for k, v in by_source.items()}
    out['payment_count'] = payments
    out['failed_count'] = failed
    # What the garden actually keeps: net of fees, less anything given back.
    out['kept'] = round(out['net'] - out['refunded'], 2)
    return out


def payout_summary(user_id, *, days=90):
    """Recent deposits to the organizer's bank, newest first, plus a total."""
    from app.models import GardenFinanceEvent
    since = _utcnow() - timedelta(days=days)
    rows = (GardenFinanceEvent.query
            .filter(GardenFinanceEvent.user_id == user_id,
                    GardenFinanceEvent.kind == 'payout',
                    GardenFinanceEvent.occurred_at >= _naive(since))
            .order_by(GardenFinanceEvent.occurred_at.desc()).all())
    paid = [r for r in rows if r.status == 'paid']
    return {
        'window_days': days,
        'paid_total': round(sum(r.amount_cents or 0 for r in paid) / 100.0, 2),
        'paid_count': len(paid),
        'last_payout_at': paid[0].occurred_at.isoformat() if paid else None,
        'last_payout_amount': round((paid[0].amount_cents or 0) / 100.0, 2) if paid else 0,
        'failed_count': sum(1 for r in rows if r.status == 'failed'),
        'payouts': [to_dict(r) for r in rows[:25]],
    }


def requirements_list(user):
    """Stripe's currently-due requirement keys for this account (may be [])."""
    raw = getattr(user, 'stripe_requirements_due', None)
    if not raw:
        return []
    try:
        val = json.loads(raw)
        return [str(v) for v in val][:25] if isinstance(val, list) else []
    except (ValueError, TypeError):
        return []


def account_state(user):
    """`ok` / `action_needed` / `restricted` / `not_started`.

    Derived from the mirrored webhook state, so it reflects Stripe's own view
    of the account rather than whether we once saw onboarding finish.
    """
    if not user or not getattr(user, 'stripe_connect_account_id', None):
        return 'not_started'
    if getattr(user, 'stripe_disabled_reason', None):
        return 'restricted'
    if not (user.stripe_charges_enabled and user.stripe_payouts_enabled):
        return 'action_needed'
    if requirements_list(user):
        return 'action_needed'
    return 'ok'


ACCOUNT_STATE_MESSAGES = {
    'not_started': 'Connect a Stripe account to collect payments and get paid.',
    'restricted': 'Stripe has paused this account. Open your Stripe dashboard '
                  'to see what it needs.',
    'action_needed': 'Stripe needs a few more details before money can reach '
                     'your bank.',
    'ok': 'Payments and payouts are both enabled.',
}


def stripe_status(garden):
    """Connected-account health for one garden's finance screens."""
    organizer = garden.organizer
    state = account_state(organizer)
    synced = getattr(organizer, 'stripe_account_synced_at', None) if organizer else None
    return {
        'state': state,
        'message': ACCOUNT_STATE_MESSAGES[state],
        'ok': state == 'ok',
        'charges_enabled': bool(getattr(organizer, 'stripe_charges_enabled', False)),
        'payouts_enabled': bool(getattr(organizer, 'stripe_payouts_enabled', False)),
        'disabled_reason': getattr(organizer, 'stripe_disabled_reason', None),
        'requirements_due': requirements_list(organizer) if organizer else [],
        'account_id': getattr(organizer, 'stripe_connect_account_id', None),
        # NULL means no account.updated event has ever reached us — which is
        # itself the diagnosis (the Connect webhook isn't wired up), so the
        # clients render it as "not synced yet" rather than "healthy".
        'synced_at': synced.isoformat() if synced else None,
    }
