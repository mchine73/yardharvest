"""Garden Pro subscription billing API endpoints — Stripe Subscriptions."""
import logging
import os
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify
from app.api.token_auth import token_or_session, get_current_user
from app import db, limiter
from app.models import CommunityGarden, GardenSubscription, PricingConfig
from app import stripe_service

log = logging.getLogger(__name__)

garden_billing_api = Blueprint('garden_billing_api', __name__, url_prefix='/api/gardens')


@garden_billing_api.url_value_preprocessor
def _resolve_garden_url_value(endpoint, values):
    """Resolve an opaque ``grd_…`` public_id (or numeric PK) in the URL to the
    integer ``garden_id`` before any handler runs."""
    if values and 'garden_id' in values:
        from app.helpers import resolve_garden_pk
        values['garden_id'] = resolve_garden_pk(values['garden_id'])


# Cache Stripe Price IDs (set on first billing request)
_stripe_prices = {'monthly': None, 'yearly': None}


def _get_pro_pricing():
    """Get Garden Pro pricing from PricingConfig (admin-configurable)."""
    config = PricingConfig.query.first()
    return {
        'enabled': getattr(config, 'garden_pro_enabled', True) if config else True,
        'trial_days': getattr(config, 'garden_pro_trial_days', 14) if config else 14,
        'monthly_cents': getattr(config, 'garden_pro_monthly_cents', 1500) if config else 1500,
        'yearly_cents': getattr(config, 'garden_pro_yearly_cents', 12500) if config else 12500,
    }


def _get_or_create_stripe_prices():
    """Ensure Stripe Product and Prices exist. Returns (monthly_price_id, yearly_price_id)."""
    if _stripe_prices['monthly'] and _stripe_prices['yearly']:
        return _stripe_prices['monthly'], _stripe_prices['yearly']
    pricing = _get_pro_pricing()
    m, y = stripe_service.ensure_garden_pro_products(
        pricing['monthly_cents'], pricing['yearly_cents']
    )
    _stripe_prices['monthly'] = m
    _stripe_prices['yearly'] = y
    return m, y


def _get_garden_or_403(garden_id):
    """Return garden if current user is the organizer, else 403."""
    garden = db.get_or_404(CommunityGarden, garden_id)
    if garden.organizer_id != get_current_user().id and not get_current_user().is_admin:
        return None
    return garden


def subscription_to_dict(sub):
    return {
        'id': sub.id,
        'garden_id': sub.garden_id,
        'billing_cycle': sub.billing_cycle,
        'status': sub.status,
        'trial_start': sub.trial_start.isoformat() if sub.trial_start else None,
        'trial_end': sub.trial_end.isoformat() if sub.trial_end else None,
        'current_period_start': sub.current_period_start.isoformat() if sub.current_period_start else None,
        'current_period_end': sub.current_period_end.isoformat() if sub.current_period_end else None,
        'cancel_at_period_end': sub.cancel_at_period_end,
        'admin_granted': bool(sub.admin_granted),
        'created_at': sub.created_at.isoformat() if sub.created_at else None,
    }


def _as_utc(dt):
    """Normalize a possibly-naive datetime to aware UTC for safe comparison."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@garden_billing_api.route('/billing/my-alerts', methods=['GET'])
@token_or_session
def my_billing_alerts():
    """Gardens owned by the current user whose free trial has ended and which
    still need payment. Powers the global trial-expiry payment popup."""
    user = get_current_user()
    if not user:
        return jsonify({'needs_payment': []})
    now = datetime.now(timezone.utc)
    gardens = CommunityGarden.query.filter_by(organizer_id=user.id).all()
    alerts = []
    for g in gardens:
        sub = g.subscription
        if not sub or sub.status == 'active':
            continue
        trial_ended = sub.status == 'expired' or (
            sub.status == 'trialing' and sub.trial_end
            and _as_utc(sub.trial_end) <= now
        )
        if not trial_ended:
            continue
        alerts.append({
            'garden_id': g.id,
            'garden_name': getattr(g, 'name', f'Garden {g.id}'),
            'status': sub.status,
            'trial_end': sub.trial_end.isoformat() if sub.trial_end else None,
        })
    return jsonify({'needs_payment': alerts})


@garden_billing_api.route('/<garden_id>/billing/start-trial', methods=['POST'])
@token_or_session
def start_trial(garden_id):
    """Start a 14-day Garden Pro trial. No payment required."""
    garden = _get_garden_or_403(garden_id)
    if not garden:
        return jsonify({'error': 'Not authorized'}), 403

    existing = GardenSubscription.query.filter_by(garden_id=garden_id).first()
    if existing:
        return jsonify({'error': f'Garden already has a subscription (status: {existing.status})'}), 400

    pricing = _get_pro_pricing()
    if not pricing['enabled']:
        return jsonify({'error': 'Garden Pro subscriptions are currently disabled'}), 400

    trial_days = pricing['trial_days']
    now = datetime.now(timezone.utc)

    sub = GardenSubscription(
        garden_id=garden_id,
        status='trialing',
        trial_start=now,
        trial_end=now + timedelta(days=trial_days),
    )
    db.session.add(sub)
    garden.subscription_status = 'trialing'

    # Pre-create Stripe Customer for conversion
    if stripe_service.is_configured():
        try:
            stripe_service.get_or_create_customer(garden.organizer)
        except Exception:
            pass

    db.session.commit()

    try:
        from app.email_service import send_garden_trial_welcome
        send_garden_trial_welcome(garden, garden.organizer)
    except Exception:
        pass

    return jsonify({
        'message': f'{trial_days}-day Garden Pro trial started!',
        'subscription': subscription_to_dict(sub),
    }), 201


@garden_billing_api.route('/<garden_id>/billing/create-checkout', methods=['POST'])
@token_or_session
@limiter.limit("5 per minute")
def create_checkout(garden_id):
    """Create a Stripe Subscription (incomplete) and return client_secret for payment."""
    garden = _get_garden_or_403(garden_id)
    if not garden:
        return jsonify({'error': 'Not authorized'}), 403

    data = request.get_json() or {}
    billing_cycle = data.get('billing_cycle', 'monthly')
    if billing_cycle not in ('monthly', 'yearly'):
        return jsonify({'error': 'billing_cycle must be monthly or yearly'}), 400

    pricing = _get_pro_pricing()
    if not pricing['enabled']:
        return jsonify({'error': 'Garden Pro subscriptions are currently disabled'}), 400

    amount_cents = pricing['monthly_cents'] if billing_cycle == 'monthly' else pricing['yearly_cents']

    # Dev mode
    if not stripe_service.is_configured():
        return jsonify({
            'dev_mode': True,
            'amount': amount_cents,
            'currency': 'USD',
            'billing_cycle': billing_cycle,
            'garden_id': garden_id,
        })

    try:
        customer_id = stripe_service.get_or_create_customer(garden.organizer)
        monthly_price, yearly_price = _get_or_create_stripe_prices()
        price_id = monthly_price if billing_cycle == 'monthly' else yearly_price

        subscription = stripe_service.create_subscription(
            customer_id=customer_id,
            price_id=price_id,
            metadata={
                'garden_id': str(garden_id),
                'type': 'garden_pro',
                'billing_cycle': billing_cycle,
            },
        )

        client_secret = subscription.latest_invoice.payment_intent.client_secret

        return jsonify({
            'client_secret': client_secret,
            'subscription_id': subscription.id,
            'publishable_key': stripe_service.get_publishable_key(),
            'amount': amount_cents,
            'currency': 'USD',
            'billing_cycle': billing_cycle,
            'dev_mode': False,
        })
    except Exception:
        log.exception('Stripe subscription creation failed for garden %d', garden_id)
        return jsonify({'error': 'Payment service temporarily unavailable. Please try again.'}), 500


@garden_billing_api.route('/<garden_id>/billing/subscribe', methods=['POST'])
@token_or_session
def subscribe(garden_id):
    """Activate a paid Garden Pro subscription after Stripe payment confirmation."""
    garden = _get_garden_or_403(garden_id)
    if not garden:
        return jsonify({'error': 'Not authorized'}), 403

    data = request.get_json() or {}
    billing_cycle = data.get('billing_cycle', 'monthly')
    if billing_cycle not in ('monthly', 'yearly'):
        return jsonify({'error': 'billing_cycle must be monthly or yearly'}), 400

    stripe_subscription_id = data.get('subscription_id', '')
    payment_ref = data.get('payment_reference', stripe_subscription_id)

    now = datetime.now(timezone.utc)

    # Try to get period dates from Stripe
    period_end = now + timedelta(days=30 if billing_cycle == 'monthly' else 365)
    if stripe_service.is_configured() and stripe_subscription_id:
        try:
            stripe_sub = stripe_service.retrieve_subscription(stripe_subscription_id)
            if stripe_sub.status in ('active', 'trialing'):
                period_end = datetime.fromtimestamp(stripe_sub.current_period_end, tz=timezone.utc)
        except Exception:
            log.exception('Failed to retrieve Stripe subscription %s', stripe_subscription_id)

    sub = GardenSubscription.query.filter_by(garden_id=garden_id).first()
    if sub:
        sub.status = 'active'
        sub.billing_cycle = billing_cycle
        sub.current_period_start = now
        sub.current_period_end = period_end
        sub.cancel_at_period_end = False
        sub.payment_reference = payment_ref
        sub.stripe_subscription_id = stripe_subscription_id
    else:
        sub = GardenSubscription(
            garden_id=garden_id,
            billing_cycle=billing_cycle,
            status='active',
            trial_start=now,
            trial_end=now,
            current_period_start=now,
            current_period_end=period_end,
            payment_reference=payment_ref,
            stripe_subscription_id=stripe_subscription_id,
        )
        db.session.add(sub)

    garden.subscription_status = 'active'
    db.session.commit()

    pricing = _get_pro_pricing()
    price = pricing['monthly_cents'] if billing_cycle == 'monthly' else pricing['yearly_cents']

    return jsonify({
        'message': f'Garden Pro activated! ${price / 100:.2f}/{billing_cycle}',
        'subscription': subscription_to_dict(sub),
    })


@garden_billing_api.route('/<garden_id>/billing/cancel', methods=['POST'])
@token_or_session
def cancel(garden_id):
    """Cancel Garden Pro subscription at the end of the current billing period."""
    garden = _get_garden_or_403(garden_id)
    if not garden:
        return jsonify({'error': 'Not authorized'}), 403

    sub = GardenSubscription.query.filter_by(garden_id=garden_id).first()
    if not sub or sub.status not in ('active', 'trialing'):
        return jsonify({'error': 'No active subscription to cancel'}), 400

    # Cancel in Stripe if subscription exists
    if sub.stripe_subscription_id and stripe_service.is_configured():
        try:
            stripe_service.cancel_subscription_at_period_end(sub.stripe_subscription_id)
        except Exception:
            log.exception('Failed to cancel Stripe subscription %s', sub.stripe_subscription_id)

    sub.cancel_at_period_end = True
    db.session.commit()

    try:
        from app.email_service import send_garden_subscription_cancelled
        send_garden_subscription_cancelled(garden, garden.organizer)
    except Exception:
        pass

    period_end = sub.current_period_end or sub.trial_end
    return jsonify({
        'message': f'Subscription will be cancelled at end of current period ({period_end.strftime("%b %d, %Y") if period_end else "now"}).',
        'subscription': subscription_to_dict(sub),
    })


@garden_billing_api.route('/<garden_id>/billing/status', methods=['GET'])
@token_or_session
def billing_status(garden_id):
    """Get current Garden Pro subscription status."""
    garden = _get_garden_or_403(garden_id)
    if not garden:
        return jsonify({'error': 'Not authorized'}), 403

    sub = GardenSubscription.query.filter_by(garden_id=garden_id).first()
    now = datetime.now(timezone.utc)

    pro = _get_pro_pricing()
    pricing = {
        'monthly': pro['monthly_cents'] / 100,
        'yearly': pro['yearly_cents'] / 100,
    }

    if not sub:
        return jsonify({
            'status': 'none',
            'trial_available': True,
            'trial_days': pro['trial_days'],
            'pricing': pricing,
        })

    trial_days_remaining = 0
    if sub.status == 'trialing' and sub.trial_end:
        remaining = (sub.trial_end - now).total_seconds()
        trial_days_remaining = max(0, int(remaining / 86400))

    return jsonify({
        'status': sub.status,
        'subscription': subscription_to_dict(sub),
        'trial_days_remaining': trial_days_remaining,
        'cancel_at_period_end': sub.cancel_at_period_end,
        'admin_granted': bool(sub.admin_granted),
        'pricing': pricing,
    })


def require_garden_pro(garden):
    """Check if a garden has an active or trialing subscription."""
    if garden.subscription_status in ('trialing', 'active'):
        return True, None
    return False, (jsonify({
        'error': 'Garden Pro subscription required',
        'upgrade_url': f'/gardens/{garden.public_id}/billing',
    }), 403)


# ----------------------------------------------------------------- Payouts
# Lets a garden manager connect a Stripe account so member DUES are paid out
# to them (Connect destination charges), instead of to the platform.

@garden_billing_api.route('/<garden_id>/payouts/status', methods=['GET'])
@token_or_session
def payouts_status(garden_id):
    """Stripe Connect payout status for this garden's manager (organizer)."""
    garden = _get_garden_or_403(garden_id)
    if not garden:
        return jsonify({'error': 'Not authorized'}), 403

    if not stripe_service.is_configured():
        return jsonify({'configured': False, 'ready': False, 'onboarded': False})

    organizer = garden.organizer
    ready = stripe_service.connect_account_ready(organizer)
    dashboard_url = stripe_service.create_login_link(organizer) if ready else None
    return jsonify({
        'configured': True,
        'onboarded': bool(organizer and organizer.stripe_connect_account_id),
        'ready': ready,
        'account_id': organizer.stripe_connect_account_id if organizer else None,
        'dashboard_url': dashboard_url,
    })


@garden_billing_api.route('/<garden_id>/payouts/connect', methods=['POST'])
@token_or_session
@limiter.limit("5 per minute")
def payouts_connect(garden_id):
    """Start Stripe Connect onboarding for the garden manager; returns a URL.

    Returns the manager back to this garden's billing page when finished.
    """
    garden = _get_garden_or_403(garden_id)
    if not garden:
        return jsonify({'error': 'Not authorized'}), 403
    if not stripe_service.is_configured():
        return jsonify({'error': 'Payment system not configured'}), 503

    organizer = garden.organizer
    if not organizer:
        return jsonify({'error': 'Garden has no manager on file'}), 400
    try:
        url = stripe_service.create_connect_account_link(
            organizer, return_path=f'/gardens/{garden.public_id}/billing')
        return jsonify({'url': url, 'account_id': organizer.stripe_connect_account_id})
    except Exception as exc:
        log.exception('Garden payout onboarding failed for garden %d', garden_id)
        return jsonify({'error': 'Failed to start payout setup. Please try again.',
                        'detail': stripe_service.error_detail(exc)}), 500


@garden_billing_api.route('/<garden_id>/payouts/account-session', methods=['POST'])
@token_or_session
@limiter.limit("10 per minute")
def payouts_account_session(garden_id):
    """Account Session for in-app (embedded) Connect onboarding of the manager."""
    garden = _get_garden_or_403(garden_id)
    if not garden:
        return jsonify({'error': 'Not authorized'}), 403
    if not stripe_service.is_configured():
        return jsonify({'error': 'Payment system not configured'}), 503

    organizer = garden.organizer
    if not organizer:
        return jsonify({'error': 'Garden has no manager on file'}), 400
    if organizer.id != get_current_user().id:
        # Embedded onboarding collects the manager's own identity/bank details,
        # so only the manager themselves may run it (admins can still send the
        # hosted link via /payouts/connect).
        return jsonify({'error': 'Only the garden manager can complete payout onboarding'}), 403
    try:
        client_secret = stripe_service.create_account_session(organizer)
        return jsonify({
            'client_secret': client_secret,
            'publishable_key': stripe_service.get_publishable_key(),
            'account_id': organizer.stripe_connect_account_id,
        })
    except Exception as exc:
        log.exception('Garden payout account session failed for garden %d', garden_id)
        return jsonify({'error': 'Failed to start payout setup. Please try again.',
                        'detail': stripe_service.error_detail(exc)}), 500
