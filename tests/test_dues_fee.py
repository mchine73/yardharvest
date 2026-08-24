"""One platform-fee rule for every way a garden takes money.

The fee used to be resolved at each call site. Only the online-dues path
honored the legacy `GARDEN_DUES_FEE_PERCENT` env var, so a deployment with
that variable set charged a platform fee on web payments and silently waived
it on every Tap-to-Pay collection — same money, same garden, different answer
depending on which button someone pressed.

The last test is the one that matters: it drives all three collection
endpoints and asserts they hand Stripe the same `application_fee_amount`.
"""
import uuid
from unittest.mock import MagicMock, patch

import pytest

from app import db as _db


@pytest.fixture()
def priced(app, make_user):
    """A garden with a payout-ready organizer and one $50 unpaid dues record."""
    from app.models import CommunityGarden, GardenDuesRecord, PricingConfig
    organizer = make_user(username='mgr', email='mgr@example.com',
                          role='manager', password='GoodPass1')
    organizer.stripe_connect_account_id = 'acct_mgr'
    member = make_user(username='mem', email='mem@example.com',
                       role='gardener', password='GoodPass1')
    g = CommunityGarden(name='Fee Garden', slug='fee-%s' % uuid.uuid4().hex[:8],
                        organizer_id=organizer.id)
    _db.session.add(g)
    _db.session.flush()
    rec = GardenDuesRecord(garden_id=g.id, user_id=member.id, season_year=2026,
                           amount_due=50.0, amount_paid=0, status='unpaid')
    _db.session.add(rec)
    _db.session.add(PricingConfig())
    _db.session.commit()
    return {'garden_id': g.id, 'dues_id': rec.id}


def set_fee(pct):
    from app.models import PricingConfig
    cfg = PricingConfig.query.first()
    cfg.garden_dues_fee_percent = pct
    _db.session.commit()


# ---------------------------------------------------------------------------
# The resolver
# ---------------------------------------------------------------------------
def test_no_fee_is_configured_by_default(app, priced):
    """The column default is 0 — the manager keeps everything, and Stripe gets
    no application fee at all rather than a zero-valued one."""
    from app.pricing import dues_fee_cents, dues_fee_percent
    assert dues_fee_percent() == 0
    assert dues_fee_cents(5000) is None


def test_a_configured_percentage_is_applied(app, priced):
    from app.pricing import dues_fee_cents
    set_fee(2.9)
    assert dues_fee_cents(5000) == 145
    assert dues_fee_cents(1200) == 35      # 34.8, rounded
    assert dues_fee_cents(0) is None


def test_the_legacy_env_var_still_works(app, priced):
    """Deployments configured before the admin console existed must not
    silently start collecting nothing."""
    from app.pricing import dues_fee_percent
    app.config['GARDEN_DUES_FEE_PERCENT'] = 5.0
    try:
        assert dues_fee_percent() == 5.0
        # The admin console wins over the env var when both are set.
        set_fee(2.0)
        assert dues_fee_percent() == 2.0
    finally:
        app.config['GARDEN_DUES_FEE_PERCENT'] = 0


def test_a_nonsense_percentage_charges_nothing_rather_than_exploding(app, priced):
    """A misconfigured fee must never be the reason a manager can't take
    money — and a 150% fee would be rejected by Stripe mid-charge."""
    from app.pricing import dues_fee_cents, dues_fee_percent
    for bad in (-5, 150):
        set_fee(bad)
        assert dues_fee_percent() == 0
        assert dues_fee_cents(5000) is None


# ---------------------------------------------------------------------------
# The drift guard
# ---------------------------------------------------------------------------
def _capture_in_person(client, app, priced, path, payload=None):
    """Drive one garden-admin collection endpoint, return the PI kwargs."""
    from app import stripe_service
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return MagicMock(client_secret='cs_x', id='pi_x')

    client.post('/api/auth/login',
                json={'email': 'mgr@example.com', 'password': 'GoodPass1'})
    with patch.dict('os.environ', {'STRIPE_SECRET_KEY': 'sk_test'}), \
            patch.object(stripe_service, 'is_configured', return_value=True), \
            patch.object(stripe_service, 'connect_account_ready', return_value=True), \
            patch.object(stripe_service, 'connect_card_present_ready',
                         return_value=True), \
            patch('stripe.PaymentIntent.create', side_effect=fake_create):
        resp = client.post(path, json=payload or {})
    assert resp.status_code == 200, resp.get_json()
    return captured


def _capture_online(client, app, priced):
    from app import stripe_service
    captured = {}

    def fake_pi(**kwargs):
        captured.update(kwargs)
        return MagicMock(client_secret='cs_x', id='pi_online')

    client.post('/api/auth/login',
                json={'email': 'mem@example.com', 'password': 'GoodPass1'})
    with patch.dict('os.environ', {'STRIPE_SECRET_KEY': 'sk_test'}), \
            patch.object(stripe_service, 'connect_account_ready', return_value=True), \
            patch.object(stripe_service, 'connect_payment_method_types',
                         return_value=['card']), \
            patch.object(stripe_service, 'get_or_create_customer', return_value='cus_1'), \
            patch.object(stripe_service, 'create_payment_intent', side_effect=fake_pi):
        resp = client.post('/api/gardens/%d/dues/%d/pay'
                           % (priced['garden_id'], priced['dues_id']), json={})
    assert resp.status_code == 200, resp.get_json()
    return captured


def test_every_way_of_taking_50_dollars_charges_the_same_platform_fee(
        client, app, priced):
    """Online dues, an in-person dues tap, and an ad-hoc Tap-to-Pay sale.

    Same garden, same $50, so the platform's cut must be identical. It wasn't:
    the two in-person paths never read the env fallback.
    """
    set_fee(2.9)
    expected = 145  # 5000 * 2.9%

    online = _capture_online(client, app, priced)
    in_person_dues = _capture_in_person(
        client, app, priced,
        '/api/garden-admin/%d/dues/%d/collect-in-person'
        % (priced['garden_id'], priced['dues_id']))
    ad_hoc = _capture_in_person(
        client, app, priced,
        '/api/garden-admin/%d/in-person-charge' % priced['garden_id'],
        {'amount_cents': 5000, 'memo': 'Plant sale'})

    assert online['application_fee_cents'] == expected
    assert in_person_dues['application_fee_amount'] == expected
    assert ad_hoc['application_fee_amount'] == expected


def test_the_env_fallback_now_reaches_the_in_person_paths_too(client, app, priced):
    """The actual bug: with only the env var set, Tap to Pay charged no fee
    while the website charged 5%."""
    app.config['GARDEN_DUES_FEE_PERCENT'] = 5.0
    try:
        ad_hoc = _capture_in_person(
            client, app, priced,
            '/api/garden-admin/%d/in-person-charge' % priced['garden_id'],
            {'amount_cents': 5000, 'memo': 'Plant sale'})
        assert ad_hoc['application_fee_amount'] == 250
    finally:
        app.config['GARDEN_DUES_FEE_PERCENT'] = 0


def test_with_no_fee_configured_stripe_gets_no_application_fee(client, app, priced):
    """None, not 0 — a zero application fee would create an ApplicationFee
    object on every single charge."""
    ad_hoc = _capture_in_person(
        client, app, priced,
        '/api/garden-admin/%d/in-person-charge' % priced['garden_id'],
        {'amount_cents': 5000})
    assert ad_hoc['application_fee_amount'] is None
