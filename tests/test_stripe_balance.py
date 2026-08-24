"""What Stripe is holding, and when it leaves.

The finance ledger reconstructs a garden's money from the payments we were
told about, so it is only ever as complete as the webhooks that arrived. It
answers "what did we record". It does not answer "what is Stripe going to pay
me", which is the question a manager staring at a $0.00 deposit total is
actually asking — and Stripe knows it exactly.
"""
from unittest.mock import patch

import pytest

from app import db as _db
from tests.conftest import login_via_api
from tests.test_garden_finance import garden  # noqa: F401


def balance(available=0, pending=0, currency='usd'):
    return {
        'object': 'balance',
        'available': [{'amount': available, 'currency': currency}],
        'pending': [{'amount': pending, 'currency': currency}],
    }


def account(interval='daily', delay_days=2):
    return {
        'id': 'acct_mgr',
        'settings': {'payouts': {'schedule': {
            'interval': interval, 'delay_days': delay_days,
        }}},
    }


# ---------------------------------------------------------------------------
# Reading the balance
# ---------------------------------------------------------------------------
def test_it_reports_what_stripe_holds(app):
    from app import stripe_service
    with patch.dict('os.environ', {'STRIPE_SECRET_KEY': 'sk_test'}), \
            patch('stripe.Balance.retrieve', return_value=balance(available=1900,
                                                                  pending=5700)):
        out = stripe_service.connected_balance('acct_mgr')
    assert out == {'pending': 5700, 'available': 1900, 'currency': 'usd'}


def test_it_never_sums_across_currencies(app):
    """A connected account can hold several. Adding them would invent a figure
    in no currency at all."""
    from app import stripe_service
    multi = {
        'available': [{'amount': 1000, 'currency': 'usd'},
                      {'amount': 9999, 'currency': 'eur'}],
        'pending': [{'amount': 500, 'currency': 'usd'}],
    }
    with patch.dict('os.environ', {'STRIPE_SECRET_KEY': 'sk_test'}), \
            patch('stripe.Balance.retrieve', return_value=multi):
        out = stripe_service.connected_balance('acct_mgr')
    assert out['available'] == 1000
    assert out['currency'] == 'usd'


def test_an_unreachable_balance_is_none_not_zero(app):
    """Zero would read as "Stripe has nothing for you", which is a different
    and much more alarming statement than "we could not ask"."""
    from app import stripe_service
    with patch.dict('os.environ', {'STRIPE_SECRET_KEY': 'sk_test'}), \
            patch('stripe.Balance.retrieve', side_effect=RuntimeError('down')):
        assert stripe_service.connected_balance('acct_mgr') is None
    assert stripe_service.connected_balance('') is None


# ---------------------------------------------------------------------------
# When it leaves
# ---------------------------------------------------------------------------
def test_the_schedule_is_phrased_for_someone_who_has_not_read_the_api_docs(app):
    from app import stripe_service
    with patch.dict('os.environ', {'STRIPE_SECRET_KEY': 'sk_test'}), \
            patch('stripe.Account.retrieve', return_value=account('daily', 2)):
        out = stripe_service.payout_schedule('acct_mgr')
    assert out['interval'] == 'daily'
    assert out['description'] == (
        'Stripe pays out daily, about 2 days after a payment clears.')


def test_a_manual_schedule_says_it_will_not_pay_itself(app):
    """The one setting where money sits forever unless someone acts."""
    from app import stripe_service
    with patch.dict('os.environ', {'STRIPE_SECRET_KEY': 'sk_test'}), \
            patch('stripe.Account.retrieve',
                  return_value=account('manual', None)):
        out = stripe_service.payout_schedule('acct_mgr')
    assert 'only when you request it' in out['description']


# ---------------------------------------------------------------------------
# What the manager gets
# ---------------------------------------------------------------------------
def test_the_payouts_endpoint_carries_the_balance_and_schedule(client, app, garden):
    from app import stripe_service
    login_via_api(client, 'org@example.com', 'GoodPass1')
    with patch.dict('os.environ', {'STRIPE_SECRET_KEY': 'sk_test'}), \
            patch.object(stripe_service, 'is_configured', return_value=True), \
            patch('stripe.Balance.retrieve',
                  return_value=balance(available=1900, pending=5700)), \
            patch('stripe.Account.retrieve', return_value=account()):
        body = client.get('/api/garden-admin/%d/finance/payouts'
                          % garden['garden_id']).get_json()

    assert body['balance'] == {'pending': 5700, 'available': 1900, 'currency': 'usd'}
    assert 'daily' in body['schedule']['description']
    # The deposit history is still there — this adds to it rather than replacing.
    assert 'payouts' in body and 'paid_total' in body


def test_stripe_being_down_does_not_hide_the_deposit_history(client, app, garden):
    """The ledger half works offline; losing the balance must not take the
    rest of the page with it."""
    from app import stripe_service
    login_via_api(client, 'org@example.com', 'GoodPass1')
    with patch.dict('os.environ', {'STRIPE_SECRET_KEY': 'sk_test'}), \
            patch.object(stripe_service, 'is_configured', return_value=True), \
            patch('stripe.Balance.retrieve', side_effect=RuntimeError('down')), \
            patch('stripe.Account.retrieve', side_effect=RuntimeError('down')):
        resp = client.get('/api/garden-admin/%d/finance/payouts'
                          % garden['garden_id'])

    assert resp.status_code == 200
    body = resp.get_json()
    assert body['balance'] is None
    assert body['schedule'] is None
    assert body['paid_total'] == 0


def test_a_garden_with_no_connected_account_asks_stripe_nothing(client, app, garden):
    from app import stripe_service
    from app.models import CommunityGarden, User
    g = _db.session.get(CommunityGarden, garden['garden_id'])
    _db.session.get(User, g.organizer_id).stripe_connect_account_id = None
    _db.session.commit()

    login_via_api(client, 'org@example.com', 'GoodPass1')
    with patch.dict('os.environ', {'STRIPE_SECRET_KEY': 'sk_test'}), \
            patch.object(stripe_service, 'is_configured', return_value=True), \
            patch('stripe.Balance.retrieve') as bal:
        body = client.get('/api/garden-admin/%d/finance/payouts'
                          % garden['garden_id']).get_json()
    bal.assert_not_called()
    assert body['balance'] is None
