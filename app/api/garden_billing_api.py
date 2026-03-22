"""Garden Pro subscription billing API endpoints."""
import logging
import os
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify, current_app
from app.api.token_auth import token_or_session, get_current_user
from app import db, limiter
from app.models import CommunityGarden, GardenSubscription

log = logging.getLogger(__name__)

garden_billing_api = Blueprint('garden_billing_api', __name__, url_prefix='/api/gardens')


def _get_garden_or_403(garden_id):
    """Return garden if current user is the organizer, else 403."""
    garden = CommunityGarden.query.get_or_404(garden_id)
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
        'created_at': sub.created_at.isoformat() if sub.created_at else None,
    }


@garden_billing_api.route('/<int:garden_id>/billing/start-trial', methods=['POST'])
@token_or_session
def start_trial(garden_id):
    """Start a 14-day Garden Pro trial. No payment required."""
    garden = _get_garden_or_403(garden_id)
    if not garden:
        return jsonify({'error': 'Not authorized'}), 403

    # Check if subscription already exists
    existing = GardenSubscription.query.filter_by(garden_id=garden_id).first()
    if existing:
        return jsonify({'error': f'Garden already has a subscription (status: {existing.status})'}), 400

    trial_days = current_app.config.get('GARDEN_TRIAL_DAYS', 14)
    now = datetime.now(timezone.utc)

    sub = GardenSubscription(
        garden_id=garden_id,
        status='trialing',
        trial_start=now,
        trial_end=now + timedelta(days=trial_days),
    )
    db.session.add(sub)
    garden.subscription_status = 'trialing'
    db.session.commit()

    # Send welcome email
    try:
        from app.email_service import send_garden_trial_welcome
        organizer = garden.organizer
        send_garden_trial_welcome(garden, organizer)
    except Exception:
        pass

    return jsonify({
        'message': f'{trial_days}-day Garden Pro trial started!',
        'subscription': subscription_to_dict(sub),
    }), 201


@garden_billing_api.route('/<int:garden_id>/billing/create-checkout', methods=['POST'])
@token_or_session
@limiter.limit("5 per minute")
def create_checkout(garden_id):
    """Create a Gr4vy checkout session for Garden Pro subscription payment."""
    garden = _get_garden_or_403(garden_id)
    if not garden:
        return jsonify({'error': 'Not authorized'}), 403

    data = request.get_json() or {}
    billing_cycle = data.get('billing_cycle', 'monthly')
    if billing_cycle not in ('monthly', 'yearly'):
        return jsonify({'error': 'billing_cycle must be monthly or yearly'}), 400

    if billing_cycle == 'monthly':
        amount_cents = current_app.config.get('GARDEN_PRO_PRICE_MONTHLY', 1500)
        item_name = 'Garden Pro - Monthly'
    else:
        amount_cents = current_app.config.get('GARDEN_PRO_PRICE_YEARLY', 12500)
        item_name = 'Garden Pro - Annual'

    gr4vy_id = os.environ.get('GR4VY_ID', '')
    from app.api.payment_api import _get_gr4vy_private_key
    private_key, key_error = _get_gr4vy_private_key()
    if key_error:
        return key_error

    if not gr4vy_id or not private_key:
        # Dev mode — return mock checkout session
        return jsonify({
            'token': 'dev-mock-garden-pro',
            'amount': amount_cents,
            'currency': 'USD',
            'gr4vy_id': gr4vy_id or 'sandbox',
            'environment': 'sandbox',
            'billing_cycle': billing_cycle,
            'garden_id': garden_id,
            'dev_mode': True,
        })

    gr4vy_env = os.environ.get('GR4VY_ENVIRONMENT', 'sandbox')
    try:
        from gr4vy import Gr4vy, auth, models
        client = Gr4vy(
            id=gr4vy_id,
            server=gr4vy_env,
            bearer_auth=auth.with_token(private_key),
        )
        session = client.checkout_sessions.create(
            checkout_session_create=models.CheckoutSessionCreate(
                cart_items=[
                    models.CartItem(name=item_name, quantity=1, unit_amount=amount_cents),
                ],
                metadata={
                    'type': 'garden_pro',
                    'garden_id': str(garden_id),
                    'billing_cycle': billing_cycle,
                    'user_id': str(get_current_user().id),
                },
            )
        )
        token = auth.get_embed_token(
            private_key,
            embed_params={
                'amount': amount_cents,
                'currency': 'USD',
                'buyer_external_identifier': str(get_current_user().id),
            },
            checkout_session_id=session.id,
        )
        return jsonify({
            'token': token,
            'amount': amount_cents,
            'currency': 'USD',
            'gr4vy_id': gr4vy_id,
            'environment': gr4vy_env,
            'billing_cycle': billing_cycle,
            'checkout_session_id': session.id,
            'dev_mode': False,
        })
    except ImportError:
        log.error('gr4vy Python SDK not installed')
        return jsonify({'error': 'Payment system not configured.'}), 503
    except Exception:
        log.exception('Gr4vy garden checkout session creation failed')
        return jsonify({'error': 'Payment service temporarily unavailable. Please try again.'}), 500


@garden_billing_api.route('/<int:garden_id>/billing/subscribe', methods=['POST'])
@token_or_session
def subscribe(garden_id):
    """Activate a paid Garden Pro subscription after payment confirmation."""
    garden = _get_garden_or_403(garden_id)
    if not garden:
        return jsonify({'error': 'Not authorized'}), 403

    data = request.get_json() or {}
    billing_cycle = data.get('billing_cycle', 'monthly')
    if billing_cycle not in ('monthly', 'yearly'):
        return jsonify({'error': 'billing_cycle must be monthly or yearly'}), 400

    payment_ref = data.get('payment_reference', '')

    now = datetime.now(timezone.utc)
    if billing_cycle == 'monthly':
        period_end = now + timedelta(days=30)
    else:
        period_end = now + timedelta(days=365)

    sub = GardenSubscription.query.filter_by(garden_id=garden_id).first()
    if sub:
        sub.status = 'active'
        sub.billing_cycle = billing_cycle
        sub.current_period_start = now
        sub.current_period_end = period_end
        sub.cancel_at_period_end = False
        sub.payment_reference = payment_ref
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
        )
        db.session.add(sub)

    garden.subscription_status = 'active'
    db.session.commit()

    price = current_app.config.get('GARDEN_PRO_PRICE_MONTHLY', 1500) if billing_cycle == 'monthly' else current_app.config.get('GARDEN_PRO_PRICE_YEARLY', 12500)

    return jsonify({
        'message': f'Garden Pro activated! ${price / 100:.2f}/{billing_cycle}',
        'subscription': subscription_to_dict(sub),
    })


@garden_billing_api.route('/<int:garden_id>/billing/cancel', methods=['POST'])
@token_or_session
def cancel(garden_id):
    """Cancel Garden Pro subscription at the end of the current billing period."""
    garden = _get_garden_or_403(garden_id)
    if not garden:
        return jsonify({'error': 'Not authorized'}), 403

    sub = GardenSubscription.query.filter_by(garden_id=garden_id).first()
    if not sub or sub.status not in ('active', 'trialing'):
        return jsonify({'error': 'No active subscription to cancel'}), 400

    sub.cancel_at_period_end = True
    sub.cancelled_at = datetime.now(timezone.utc)
    db.session.commit()

    # Send cancellation email
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


@garden_billing_api.route('/<int:garden_id>/billing/status', methods=['GET'])
@token_or_session
def billing_status(garden_id):
    """Get current Garden Pro subscription status."""
    garden = _get_garden_or_403(garden_id)
    if not garden:
        return jsonify({'error': 'Not authorized'}), 403

    sub = GardenSubscription.query.filter_by(garden_id=garden_id).first()
    now = datetime.now(timezone.utc)

    pricing = {
        'monthly': current_app.config.get('GARDEN_PRO_PRICE_MONTHLY', 1500) / 100,
        'yearly': current_app.config.get('GARDEN_PRO_PRICE_YEARLY', 12500) / 100,
    }

    if not sub:
        return jsonify({
            'status': 'none',
            'trial_available': True,
            'trial_days': current_app.config.get('GARDEN_TRIAL_DAYS', 14),
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
        'pricing': pricing,
    })


def require_garden_pro(garden):
    """Check if a garden has an active or trialing subscription.
    Returns (allowed: bool, error_response) tuple.
    """
    if garden.subscription_status in ('trialing', 'active'):
        return True, None
    return False, (jsonify({
        'error': 'Garden Pro subscription required',
        'upgrade_url': f'/gardens/{garden.id}/billing',
    }), 403)
