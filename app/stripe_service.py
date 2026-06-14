"""Centralized Stripe integration module.

All Stripe API calls flow through here. Dev mode returns gracefully
when STRIPE_SECRET_KEY is not set.
"""
import logging
import os
import stripe

log = logging.getLogger(__name__)


def _configure():
    stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', '')


def is_configured():
    return bool(os.environ.get('STRIPE_SECRET_KEY'))


def get_publishable_key():
    return os.environ.get('STRIPE_PUBLISHABLE_KEY', '')


# ---- Customer Management ----

def get_or_create_customer(user):
    """Ensure user has a Stripe Customer. Returns stripe_customer_id."""
    _configure()
    if user.stripe_customer_id:
        return user.stripe_customer_id
    customer = stripe.Customer.create(
        email=user.email,
        name=user.display_name or user.username,
        metadata={'yardharvest_user_id': str(user.id)},
    )
    user.stripe_customer_id = customer.id
    from app import db
    db.session.commit()
    return customer.id


# ---- Stripe Connect (Seller Payouts) ----

def ensure_connect_account(user):
    """Create the user's Stripe Connect **Express** account if missing.

    Express gives the platform control of the onboarding UX, which suits
    non-technical sellers and garden managers. The connected account requests
    both ``card_payments`` and ``transfers`` capabilities so it can be used for
    both destination charges (dues) and separate charges + transfers
    (marketplace). Returns the account id.
    """
    _configure()
    if not user.stripe_connect_account_id:
        account = stripe.Account.create(
            type='express',
            email=user.email,
            capabilities={
                'card_payments': {'requested': True},
                'transfers': {'requested': True},
                # ACH so members can pay dues by bank (us_bank_account), not
                # just card. The connected account is the merchant of record on
                # dues (on_behalf_of), so it needs this capability itself.
                'us_bank_account_ach_payments': {'requested': True},
            },
            business_profile={'name': user.display_name or user.username},
            metadata={'yardharvest_user_id': str(user.id)},
        )
        user.stripe_connect_account_id = account.id
        from app import db
        db.session.commit()
    return user.stripe_connect_account_id


def create_connect_account_link(user, return_path='/earnings'):
    """Hosted-onboarding fallback: return a Stripe-hosted onboarding URL.

    The primary onboarding path is the in-app embedded flow
    (create_account_session); this hosted Account Link is kept as a fallback
    for clients where the embedded component cannot load.

    return_path is where Stripe sends the user back after onboarding (e.g.
    '/earnings' for marketplace sellers, '/gardens/<id>/billing' for managers).
    """
    _configure()
    base_url = os.environ.get('APP_URL', 'http://localhost:5173')
    ensure_connect_account(user)
    link = stripe.AccountLink.create(
        account=user.stripe_connect_account_id,
        return_url=f'{base_url}{return_path}',
        refresh_url=f'{base_url}{return_path}',
        type='account_onboarding',
    )
    return link.url


def create_account_session(user):
    """Create an Account Session for **embedded** Connect onboarding.

    Powers Stripe's Connect embedded components so sellers and garden managers
    complete onboarding inside the app instead of being redirected to a
    Stripe-hosted page. Also enables account management and the requirements
    notification banner so onboarded users can fix issues in-app later.
    Returns the session client_secret.
    """
    _configure()
    ensure_connect_account(user)
    session = stripe.AccountSession.create(
        account=user.stripe_connect_account_id,
        components={
            'account_onboarding': {'enabled': True},
            'account_management': {'enabled': True},
            'notification_banner': {'enabled': True},
        },
    )
    return session.client_secret


def check_connect_status(user):
    """Check if Connect account onboarding is complete. Returns bool."""
    _configure()
    if not user.stripe_connect_account_id:
        return False
    try:
        account = stripe.Account.retrieve(user.stripe_connect_account_id)
    except stripe.error.StripeError:
        log.exception('Failed to retrieve Connect account %s', user.stripe_connect_account_id)
        return False
    complete = bool(account.charges_enabled and account.payouts_enabled)
    if complete and not user.stripe_onboarding_complete:
        user.stripe_onboarding_complete = True
        from app import db
        db.session.commit()
    return complete


def create_login_link(user):
    """Create a link to the Stripe Express dashboard for a connected seller."""
    _configure()
    if not user.stripe_connect_account_id:
        return None
    try:
        link = stripe.Account.create_login_link(user.stripe_connect_account_id)
        return link.url
    except stripe.error.StripeError:
        log.exception('Failed to create login link for %s', user.stripe_connect_account_id)
        return None


# ---- PaymentIntents (Marketplace Checkout) ----

def create_payment_intent(amount_cents, customer_id, metadata=None,
                          destination_account_id=None, application_fee_cents=None,
                          on_behalf_of=None, payment_method_types=None):
    """Create a Stripe PaymentIntent. Returns the PaymentIntent object.

    When destination_account_id is given, this becomes a Connect *destination
    charge*: funds are routed to the connected account (the garden manager),
    minus an optional platform application fee. Without it, it's an ordinary
    platform charge (backwards compatible).

    Payment methods are restricted to card + US bank (ACH) only — we explicitly
    do NOT offer Amazon Pay, Cash App Pay, Klarna, or other automatic methods.
    Callers may narrow further via ``payment_method_types`` (e.g. card-only for
    a connected account without the ACH capability).
    """
    _configure()
    params = {
        'amount': amount_cents,
        'currency': 'usd',
        'customer': customer_id,
        'payment_method_types': payment_method_types or ['card', 'us_bank_account'],
        'metadata': metadata or {},
    }
    if destination_account_id:
        params['transfer_data'] = {'destination': destination_account_id}
        if on_behalf_of:
            params['on_behalf_of'] = on_behalf_of
        if application_fee_cents and application_fee_cents > 0:
            params['application_fee_amount'] = application_fee_cents
    return stripe.PaymentIntent.create(**params)


def connect_account_ready(user):
    """True if the user's connected account can accept charges & payouts."""
    if not user or not user.stripe_connect_account_id:
        return False
    _configure()
    try:
        acct = stripe.Account.retrieve(user.stripe_connect_account_id)
        return bool(acct.charges_enabled and acct.payouts_enabled)
    except Exception:
        log.exception('Failed to check connect readiness for %s',
                      user.stripe_connect_account_id)
        return False


def connect_payment_method_types(user):
    """Payment methods allowed for a destination charge to this connected
    account. Card is always allowed; us_bank_account (ACH) only if the account
    has that capability *active* — otherwise Stripe rejects the PaymentIntent
    (with on_behalf_of, the connected account must support the method). Returns
    card-only on any error, so dues collection never breaks.
    """
    types = ['card']
    if not user or not user.stripe_connect_account_id:
        return types
    _configure()
    try:
        acct = stripe.Account.retrieve(user.stripe_connect_account_id)
        caps = (acct.get('capabilities') if isinstance(acct, dict)
                else getattr(acct, 'capabilities', None)) or {}
        if caps.get('us_bank_account_ach_payments') == 'active':
            types.append('us_bank_account')
    except Exception:
        log.exception('Failed to read capabilities for %s',
                      user.stripe_connect_account_id)
    return types


def retrieve_payment_intent(payment_intent_id):
    """Retrieve a PaymentIntent by ID."""
    _configure()
    return stripe.PaymentIntent.retrieve(payment_intent_id)


def create_transfer(amount_cents, destination_account_id, transfer_group=None):
    """Create a Transfer to a connected account (seller payout)."""
    _configure()
    return stripe.Transfer.create(
        amount=amount_cents,
        currency='usd',
        destination=destination_account_id,
        transfer_group=transfer_group,
    )


# ---- Subscriptions (Garden Pro) ----

def create_subscription(customer_id, price_id, metadata=None):
    """Create a Stripe Subscription (incomplete — needs payment confirmation)."""
    _configure()
    return stripe.Subscription.create(
        customer=customer_id,
        items=[{'price': price_id}],
        payment_behavior='default_incomplete',
        payment_settings={
            'save_default_payment_method': 'on_subscription',
            # Card + US bank only — no Amazon Pay / Cash App Pay / Klarna.
            'payment_method_types': ['card', 'us_bank_account'],
        },
        expand=['latest_invoice.payment_intent'],
        metadata=metadata or {},
    )


def retrieve_subscription(subscription_id):
    """Retrieve a Stripe Subscription by ID."""
    _configure()
    return stripe.Subscription.retrieve(subscription_id)


def cancel_subscription_at_period_end(subscription_id):
    """Mark a Stripe Subscription for cancellation at period end."""
    _configure()
    return stripe.Subscription.modify(subscription_id, cancel_at_period_end=True)


def ensure_garden_pro_products(monthly_cents, yearly_cents):
    """Create or retrieve Garden Pro Stripe Product and Price objects.
    Returns (monthly_price_id, yearly_price_id).
    """
    _configure()
    # Find or create product
    products = stripe.Product.search(query="metadata['type']:'garden_pro'")
    if products.data:
        product = products.data[0]
    else:
        product = stripe.Product.create(
            name='Garden Pro',
            description='Community garden management subscription',
            metadata={'type': 'garden_pro'},
        )

    # Find existing prices or create new ones
    prices = stripe.Price.list(product=product.id, active=True)
    monthly_price_id = None
    yearly_price_id = None
    for p in prices.data:
        if p.recurring and p.recurring.interval == 'month' and p.unit_amount == monthly_cents:
            monthly_price_id = p.id
        if p.recurring and p.recurring.interval == 'year' and p.unit_amount == yearly_cents:
            yearly_price_id = p.id

    if not monthly_price_id:
        mp = stripe.Price.create(
            product=product.id,
            unit_amount=monthly_cents,
            currency='usd',
            recurring={'interval': 'month'},
            metadata={'billing_cycle': 'monthly'},
        )
        monthly_price_id = mp.id

    if not yearly_price_id:
        yp = stripe.Price.create(
            product=product.id,
            unit_amount=yearly_cents,
            currency='usd',
            recurring={'interval': 'year'},
            metadata={'billing_cycle': 'yearly'},
        )
        yearly_price_id = yp.id

    return monthly_price_id, yearly_price_id


# ---- Refunds ----

def create_refund(payment_intent_id, amount_cents=None):
    """Issue a full or partial refund on a PaymentIntent."""
    _configure()
    params = {'payment_intent': payment_intent_id}
    if amount_cents is not None:
        params['amount'] = amount_cents
    return stripe.Refund.create(**params)


def reverse_transfer(transfer_id, amount_cents=None):
    """Reverse a transfer to a connected account (claw back seller payout)."""
    _configure()
    params = {}
    if amount_cents is not None:
        params['amount'] = amount_cents
    return stripe.Transfer.create_reversal(transfer_id, **params)


def cancel_subscription_immediately(subscription_id):
    """Cancel a Stripe Subscription immediately (not at period end)."""
    _configure()
    return stripe.Subscription.cancel(subscription_id, prorate=True)


# ---- Webhooks ----

def construct_webhook_event(payload, sig_header):
    """Verify and construct a Stripe webhook event."""
    endpoint_secret = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
    if not endpoint_secret:
        return None
    return stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
