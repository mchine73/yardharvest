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


def error_detail(exc):
    """A safe, operator-useful one-liner for a failed Stripe call.

    Stripe error objects expose ``user_message``/``code``; their text never
    contains the secret key, so it's safe to return to the authenticated user
    who triggered the action. It's exactly what's needed to diagnose a live
    go-live misconfig (e.g. an incomplete Connect platform profile or missing
    Express branding), which a generic "please try again" hides.
    """
    msg = getattr(exc, 'user_message', None) or str(exc) or type(exc).__name__
    code = getattr(exc, 'code', None)
    return (f'{msg} (code: {code})' if code else msg)[:300]


# ---- Customer Management ----

def get_or_create_customer(user):
    """Ensure user has a Stripe Customer. Returns stripe_customer_id.

    Self-healing: if a stored id no longer exists (e.g. a test-mode customer
    after switching to live keys, or a deleted customer), create a fresh one.
    """
    _configure()
    from app import db
    if user.stripe_customer_id:
        try:
            cust = stripe.Customer.retrieve(user.stripe_customer_id)
            if not getattr(cust, 'deleted', False):
                return user.stripe_customer_id
            log.warning('Stripe customer %s is deleted; recreating', user.stripe_customer_id)
        except (stripe.error.InvalidRequestError, stripe.error.PermissionError):
            # "No such customer" / not owned by this platform — a stale/test id
            # under a different (live) key. Recreate.
            log.warning('Stored Stripe customer %s not found (likely a test id '
                        'under live keys); recreating', user.stripe_customer_id)
        except stripe.error.StripeError:
            # Transient/auth error — don't blindly recreate; reuse the stored id.
            return user.stripe_customer_id
    customer = stripe.Customer.create(
        email=user.email,
        name=user.display_name or user.username,
        metadata={'yardharvest_user_id': str(user.id)},
    )
    user.stripe_customer_id = customer.id
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
    from app import db
    # Self-healing: a stored account id that Stripe can't find (e.g. a test
    # account after switching to live keys, or a deleted account) must be
    # replaced, otherwise onboarding/dues routing would keep failing on it.
    if user.stripe_connect_account_id:
        try:
            acct = stripe.Account.retrieve(user.stripe_connect_account_id)
            if not getattr(acct, 'deleted', False):
                return user.stripe_connect_account_id
            log.warning('Connect account %s is deleted; recreating', user.stripe_connect_account_id)
        except (stripe.error.InvalidRequestError, stripe.error.PermissionError):
            # InvalidRequest = "No such account"; Permission = the account isn't
            # connected to *this* platform. Both happen for a stale test/foreign
            # id under live keys and are permanent — replace it. (A transient
            # network/auth error falls through to the StripeError branch below
            # and keeps the stored id.)
            log.warning('Stored Connect account %s not usable by this platform '
                        '(likely a test id under live keys); recreating',
                        user.stripe_connect_account_id)
        except stripe.error.StripeError:
            return user.stripe_connect_account_id
        # Recreating: the new account hasn't been onboarded.
        user.stripe_connect_account_id = None
        user.stripe_onboarding_complete = False

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
    db.session.commit()
    return user.stripe_connect_account_id


def _reset_connect_account(user):
    """Forget the stored Connect account id so the next ensure_* recreates it."""
    from app import db
    user.stripe_connect_account_id = None
    user.stripe_onboarding_complete = False
    db.session.commit()


def create_connect_account_link(user, return_path='/earnings'):
    """Hosted-onboarding fallback: return a Stripe-hosted onboarding URL.

    The primary onboarding path is the in-app embedded flow
    (create_account_session); this hosted Account Link is kept as a fallback
    for clients where the embedded component cannot load.

    return_path is where Stripe sends the user back after onboarding (e.g.
    '/earnings' for marketplace sellers, '/gardens/<id>/billing' for managers).
    """
    _configure()
    # Use the normalized public site URL (apex -> www, etc.) so Stripe returns
    # the user to a reachable page, not a bare-apex APP_URL that doesn't resolve.
    try:
        from flask import current_app
        base_url = current_app.config.get('SITE_URL') or os.environ.get('APP_URL', 'http://localhost:5173')
    except Exception:
        base_url = os.environ.get('APP_URL', 'http://localhost:5173')

    def _make_link():
        return stripe.AccountLink.create(
            account=user.stripe_connect_account_id,
            return_url=f'{base_url}{return_path}',
            refresh_url=f'{base_url}{return_path}',
            type='account_onboarding',
        )

    ensure_connect_account(user)
    try:
        return _make_link().url
    except stripe.error.InvalidRequestError:
        # The stored account isn't connected to this platform (a leftover test
        # account under live keys that retrieve() didn't flag). Force a fresh
        # account and retry once so onboarding self-heals at go-live.
        log.warning('AccountLink rejected account %s; recreating and retrying',
                    user.stripe_connect_account_id)
        _reset_connect_account(user)
        ensure_connect_account(user)
        return _make_link().url


def create_account_session(user):
    """Create an Account Session for **embedded** Connect onboarding.

    Powers Stripe's Connect embedded components so sellers and garden managers
    complete onboarding inside the app instead of being redirected to a
    Stripe-hosted page. Also enables account management and the requirements
    notification banner so onboarded users can fix issues in-app later.
    Returns the session client_secret.
    """
    _configure()

    def _make_session():
        return stripe.AccountSession.create(
            account=user.stripe_connect_account_id,
            components={
                # Collect bank/external-account details inline. (For Express
                # accounts Stripe still opens its own secure auth popup mid-flow
                # to verify the account — that popup is required and can't be
                # disabled without switching to Custom accounts.)
                'account_onboarding': {
                    'enabled': True,
                    'features': {'external_account_collection': True},
                },
                'account_management': {'enabled': True},
                'notification_banner': {'enabled': True},
            },
        )

    ensure_connect_account(user)
    try:
        return _make_session().client_secret
    except stripe.error.InvalidRequestError:
        # Stale/foreign account id under live keys — recreate and retry once.
        log.warning('AccountSession rejected account %s; recreating and retrying',
                    user.stripe_connect_account_id)
        _reset_connect_account(user)
        ensure_connect_account(user)
        return _make_session().client_secret


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
        'payment_method_types': payment_method_types or ['card', 'us_bank_account'],
        'metadata': metadata or {},
    }
    if customer_id:
        params['customer'] = customer_id
    if destination_account_id:
        params['transfer_data'] = {'destination': destination_account_id}
        if on_behalf_of:
            params['on_behalf_of'] = on_behalf_of
        if application_fee_cents and application_fee_cents > 0:
            params['application_fee_amount'] = application_fee_cents
    return stripe.PaymentIntent.create(**params)


def get_connect_account(user):
    """``(account, error)`` — one Account.retrieve, shareable across checks.

    Several gates in a single request each used to retrieve the same account.
    Callers that run more than one check should retrieve once through here and
    pass the result down, rather than paying a Stripe round-trip per gate.
    """
    if not user or not user.stripe_connect_account_id:
        return None, 'no connected account on this user'
    _configure()
    try:
        return stripe.Account.retrieve(user.stripe_connect_account_id), None
    except stripe.error.StripeError as e:
        log.exception('Failed to retrieve connect account %s',
                      user.stripe_connect_account_id)
        return None, error_detail(e)
    except Exception as e:
        log.exception('Failed to retrieve connect account %s',
                      user.stripe_connect_account_id)
        return None, f'{type(e).__name__}: {e}'[:200]


def connect_account_ready(user, acct=None):
    """True if the user's connected account can accept charges & payouts.

    Pass ``acct`` to reuse an account already fetched in this request.
    """
    if acct is None:
        acct, _err = get_connect_account(user)
    if acct is None:
        return False
    return bool(acct.charges_enabled and acct.payouts_enabled)


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


# ---- Tap to Pay (Stripe Terminal, card_present) ----

def _account_capabilities(user, acct=None):
    """``(capabilities, error)`` for the user's connected account.

    Returns the capability map and ``None`` on success, or ``{}`` and a short
    error string when the account couldn't be read. Callers must distinguish
    the two: "capability isn't active" and "we couldn't ask" are different
    problems with different fixes, and reporting them identically sends the
    operator looking in the wrong place.
    """
    if acct is None:
        acct, err = get_connect_account(user)
        if err or acct is None:
            return {}, err or 'account unavailable'
    caps = ((acct.get('capabilities') if isinstance(acct, dict)
             else getattr(acct, 'capabilities', None)) or {})
    return caps, None


def card_present_capability_status(user, acct=None):
    """``(status, detail)`` for the capability Terminal actually depends on.

    Stripe has no ``card_present_payments`` capability — requesting one is
    rejected with ``parameter_unknown``. Card-present acceptance rides on the
    ordinary ``card_payments`` capability, so that is what gets checked here;
    there is nothing extra to request for Tap to Pay.

    status is the capability string ('active'/'pending'/'inactive', or None
    when it could not be determined); detail is a short operator-facing
    explanation when the account could not be read, else None.
    """
    caps, err = _account_capabilities(user, acct=acct)
    if err:
        return None, f"couldn't read the connected account ({err})"
    return caps.get('card_payments'), None


def connect_card_present_ready(user, acct=None):
    """True if the connected account can accept card-present charges.

    Same underlying capability as online card payments — see
    :func:`card_present_capability_status`.
    """
    status, _detail = card_present_capability_status(user, acct=acct)
    return status == 'active'


def ensure_terminal_location(user, acct=None):
    """Return a Stripe Terminal Location id for the connected account.

    Tap to Pay requires the reader to be registered to a Location that belongs
    to the *connected* account. Reuses the first existing Location; creates one
    from the manager's profile if they have none. Returns None on failure so
    callers can surface a clear error rather than handing the SDK a bad id.
    """
    if not user or not user.stripe_connect_account_id:
        return None
    _configure()
    acct_id = user.stripe_connect_account_id
    try:
        existing = stripe.terminal.Location.list(limit=1, stripe_account=acct_id)
        data = existing.get('data') if isinstance(existing, dict) else existing.data
        if data:
            return data[0].id
    except stripe.error.StripeError:
        log.exception('Failed to list Terminal locations for %s', acct_id)
        return None

    # A Location needs a real address. Reuse whatever the manager already gave
    # Stripe during Connect onboarding rather than inventing one — a bogus
    # address here would be wrong for every manager outside that city.
    address = None
    candidates = ()
    try:
        if acct is None:
            acct, _err = get_connect_account(user)
        if acct is None:
            log.warning('No account object available for %s; cannot resolve '
                        'a Terminal address', acct_id)
            return None
        biz = (getattr(acct, 'business_profile', None) or {})
        company = (getattr(acct, 'company', None) or {})
        # Express accounts store the address in different places depending on
        # business_type: `company.address` for companies, `individual.address`
        # for sole traders — which is what most garden organizers are. Check
        # every location rather than assuming one.
        individual = (getattr(acct, 'individual', None) or {})
        candidates = (
            ('business_profile.support_address', biz.get('support_address')),
            ('company.address', company.get('address')),
            ('individual.address', individual.get('address')),
        )
        for label, candidate in candidates:
            if not candidate:
                continue
            fields = {k: v for k, v in dict(candidate).items()
                      if k in ('line1', 'line2', 'city', 'state',
                               'country', 'postal_code') and v}
            # Stripe needs at minimum a country and a street line.
            if fields.get('country') and fields.get('line1'):
                address = fields
                log.info('Using %s for Terminal location on %s', label, acct_id)
                break
    except stripe.error.StripeError:
        log.exception('Failed to read address for %s', acct_id)

    if not address:
        # Name what was actually present — "add an address" is useless advice
        # when the operator can plainly see one in the dashboard.
        try:
            present = {label: sorted(dict(c).keys()) if c else None
                       for label, c in candidates}
        except Exception:
            present = 'unavailable'
        log.warning('No usable Terminal address for %s (needs country+line1). '
                    'Fields seen: %s', acct_id, present)
        return None

    try:
        loc = stripe.terminal.Location.create(
            display_name=(user.display_name or user.username or 'Garden')[:100],
            address=address,
            metadata={'yardharvest_user_id': str(user.id)},
            stripe_account=acct_id,
        )
        log.info('Created Terminal location %s for %s', loc.id, acct_id)
        return loc.id
    except stripe.error.StripeError:
        log.exception('Failed to create Terminal location for %s', acct_id)
        return None


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


def refund_latest_subscription_invoice(subscription_id, amount_cents=None):
    """Refund (optionally partial) the most recent invoice of a subscription.

    Resolves the subscription's latest invoice → its PaymentIntent and issues a
    Stripe ``Refund``. Returns the refund id, or ``None`` if there's no charged
    invoice to refund. Raises ``StripeError`` on a genuine API failure so the
    caller can record the refund as not-issued rather than claiming success.
    """
    _configure()
    sub = stripe.Subscription.retrieve(
        subscription_id, expand=['latest_invoice.payment_intent'])
    invoice = getattr(sub, 'latest_invoice', None)
    pi = getattr(invoice, 'payment_intent', None) if invoice else None
    pi_id = getattr(pi, 'id', None) or (pi if isinstance(pi, str) else None)
    if not pi_id:
        return None
    params = {'payment_intent': pi_id}
    if amount_cents and amount_cents > 0:
        params['amount'] = amount_cents
    return stripe.Refund.create(**params).id


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


def connected_charge_fee(charge_id, connected_account_id):
    """What Stripe actually charged the connected account for one payment.

    Returns ``(fee_cents, net_cents)``, or ``(None, None)`` when it cannot be
    determined — never a guess. A wrong fee is worse than a missing one here:
    the finance screens exist so a manager doesn't have to open Stripe, and a
    number that is quietly 3% off is exactly the kind of thing someone
    reconciles against and trusts over their own bank statement.

    Why this is not simply ``charge.balance_transaction``: on a destination
    charge the charge itself lives on the *platform*, and its balance
    transaction describes the platform's side. The money the manager actually
    receives arrives on **their** account as a separate "destination payment",
    and that object's balance transaction is the only place Stripe's fee
    appears when the connected account bears it.

    Reading it rather than modelling it means this stays correct whichever way
    fee liability is configured — and survives that setting being changed.
    """
    if not charge_id or not connected_account_id:
        return None, None
    _configure()

    def _field(obj, key):
        if obj is None:
            return None
        return obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)

    try:
        # One round trip: Stripe expands up to four levels deep.
        charge = stripe.Charge.retrieve(
            charge_id, expand=['transfer.destination_payment.balance_transaction'])
    except Exception:
        log.exception('Could not read charge %s for fee lookup', charge_id)
        return None, None

    transfer = _field(charge, 'transfer')
    payment = _field(transfer, 'destination_payment')
    txn = _field(payment, 'balance_transaction')

    # Fall back to explicit retrieves when the expansion came back as bare ids
    # (older API versions, or an object the platform can't expand through).
    try:
        if payment is not None and not isinstance(payment, str) and txn is None:
            txn_id = _field(payment, 'balance_transaction')
            if isinstance(txn_id, str):
                txn = stripe.BalanceTransaction.retrieve(
                    txn_id, stripe_account=connected_account_id)
        elif isinstance(payment, str):
            full = stripe.Charge.retrieve(payment,
                                          stripe_account=connected_account_id,
                                          expand=['balance_transaction'])
            txn = _field(full, 'balance_transaction')
            if isinstance(txn, str):
                txn = stripe.BalanceTransaction.retrieve(
                    txn, stripe_account=connected_account_id)
    except Exception:
        log.exception('Could not read the connected-account balance '
                      'transaction for charge %s', charge_id)
        return None, None

    fee = _field(txn, 'fee')
    net = _field(txn, 'net')
    if fee is None:
        return None, None
    try:
        return int(fee), (int(net) if net is not None else None)
    except (TypeError, ValueError):
        return None, None


def connected_balance(connected_account_id):
    """What Stripe is currently holding for a connected account.

    Returns ``{'pending', 'available', 'currency'}`` in cents, or None if it
    cannot be read.

    This is the answer to "what is Stripe going to pay me", and it is not the
    same question as the finance ledger's. The ledger reconstructs money from
    the payments we were told about, so it is only ever as complete as the
    webhooks that arrived. The balance is Stripe's own count of what it holds:
    authoritative, and it includes anything our records missed.

    ``pending`` is money still settling; ``available`` is cleared and waiting
    for the next scheduled payout.
    """
    if not connected_account_id:
        return None
    _configure()
    try:
        bal = stripe.Balance.retrieve(stripe_account=connected_account_id)
    except Exception:
        log.exception('Could not read the balance for %s', connected_account_id)
        return None

    def _pick(bucket):
        """Total for the account's own currency.

        A connected account can hold several currencies. Summing across them
        would invent a number in no currency at all, so take USD when present
        and otherwise the first currency Stripe lists.
        """
        entries = (bal.get(bucket) if isinstance(bal, dict)
                   else getattr(bal, bucket, None)) or []
        if not entries:
            return 0, None
        wanted = None
        for e in entries:
            cur = e.get('currency') if isinstance(e, dict) else getattr(e, 'currency', None)
            if cur == 'usd':
                wanted = 'usd'
                break
        if wanted is None:
            first = entries[0]
            wanted = (first.get('currency') if isinstance(first, dict)
                      else getattr(first, 'currency', None))
        total = 0
        for e in entries:
            cur = e.get('currency') if isinstance(e, dict) else getattr(e, 'currency', None)
            if cur != wanted:
                continue
            amt = e.get('amount') if isinstance(e, dict) else getattr(e, 'amount', 0)
            total += int(amt or 0)
        return total, wanted

    pending, cur_p = _pick('pending')
    available, cur_a = _pick('available')
    return {'pending': pending, 'available': available,
            'currency': cur_a or cur_p or 'usd'}


#: Stripe's payout-schedule intervals, phrased for someone who has not read
#: the API reference.
_SCHEDULE_WORDS = {
    'daily': 'daily',
    'weekly': 'weekly',
    'monthly': 'monthly',
    'manual': 'only when you request it',
}


def payout_schedule(connected_account_id):
    """When Stripe pays this account out, in words. None if unreadable.

    Without this the balance is half an answer: a manager looking at money
    Stripe is holding wants to know when it leaves, and "daily, two days
    after a payment clears" is the part that stops them worrying.
    """
    if not connected_account_id:
        return None
    _configure()
    try:
        acct = stripe.Account.retrieve(connected_account_id)
    except Exception:
        log.exception('Could not read the payout schedule for %s',
                      connected_account_id)
        return None

    settings = (acct.get('settings') if isinstance(acct, dict)
                else getattr(acct, 'settings', None)) or {}
    payouts = (settings.get('payouts') if isinstance(settings, dict)
               else getattr(settings, 'payouts', None)) or {}
    schedule = (payouts.get('schedule') if isinstance(payouts, dict)
                else getattr(payouts, 'schedule', None)) or {}

    def _get(key, default=None):
        return (schedule.get(key, default) if isinstance(schedule, dict)
                else getattr(schedule, key, default))

    interval = _get('interval') or 'unknown'
    delay = _get('delay_days')
    words = _SCHEDULE_WORDS.get(interval, interval)
    if interval == 'manual':
        text = 'Stripe pays out only when you request it.'
    elif delay:
        text = 'Stripe pays out %s, about %s day%s after a payment clears.' % (
            words, delay, '' if delay == 1 else 's')
    else:
        text = 'Stripe pays out %s.' % words
    return {'interval': interval, 'delay_days': delay, 'description': text,
            'weekly_anchor': _get('weekly_anchor'),
            'monthly_anchor': _get('monthly_anchor')}


# ---- Webhooks ----

def webhook_secrets():
    """Every signing secret this deployment will accept, in order.

    Stripe issues a **separate** signing secret per endpoint, and Connect
    events (payouts, ``account.updated`` on a connected account) require their
    own endpoint. So a single-secret verifier silently rejects every Connect
    event with a signature failure — which looks identical to an attack in the
    logs. ``STRIPE_CONNECT_WEBHOOK_SECRET`` is that second endpoint's secret;
    it is optional, and omitting it simply means Connect events are not being
    received.
    """
    return [s for s in (os.environ.get('STRIPE_WEBHOOK_SECRET', ''),
                        os.environ.get('STRIPE_CONNECT_WEBHOOK_SECRET', ''))
            if s.strip()]


def construct_webhook_event(payload, sig_header):
    """Verify and construct a Stripe webhook event.

    Tries each configured signing secret and returns the first that verifies;
    raises the last error if none do. Returns None when no secret is set at
    all (dev), which the caller turns into a hard refusal whenever real Stripe
    keys are present.
    """
    secrets = webhook_secrets()
    if not secrets:
        return None
    last_error = None
    for secret in secrets:
        try:
            return stripe.Webhook.construct_event(payload, sig_header, secret)
        except stripe.error.SignatureVerificationError as exc:
            last_error = exc
    raise last_error
