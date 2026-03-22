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

def create_connect_account_link(user):
    """Create a Stripe Connect Standard account and return the onboarding URL."""
    _configure()
    base_url = os.environ.get('APP_URL', 'http://localhost:5173')
    if not user.stripe_connect_account_id:
        account = stripe.Account.create(
            type='standard',
            email=user.email,
            metadata={'yardharvest_user_id': str(user.id)},
        )
        user.stripe_connect_account_id = account.id
        from app import db
        db.session.commit()
    link = stripe.AccountLink.create(
        account=user.stripe_connect_account_id,
        return_url=f'{base_url}/earnings',
        refresh_url=f'{base_url}/earnings',
        type='account_onboarding',
    )
    return link.url


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

def create_payment_intent(amount_cents, customer_id, metadata=None):
    """Create a Stripe PaymentIntent. Returns the PaymentIntent object."""
    _configure()
    return stripe.PaymentIntent.create(
        amount=amount_cents,
        currency='usd',
        customer=customer_id,
        automatic_payment_methods={'enabled': True},
        metadata=metadata or {},
    )


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
        payment_settings={'save_default_payment_method': 'on_subscription'},
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
