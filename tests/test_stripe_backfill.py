"""`flask stripe-sync-accounts` — make the Connect endpoint correct on day one.

Webhooks only report what happens next. A manager whose Stripe account has
been healthy for months emits no `account.updated`, so without a backfill the
finance screens would report "Stripe hasn't sent an account update yet"
indefinitely, and payouts Stripe already made would never appear.

The risk this command carries is drift: a backfill that mirrors an account
*slightly* differently from the webhook leaves managers in a state neither
code path explains. The contract test at the bottom is the one that matters.
"""
import json
from unittest.mock import patch

import pytest

from app import db as _db


@pytest.fixture()
def connected(app, make_user):
    """Two managers with connected accounts, plus one without."""
    from app.models import CommunityGarden
    a = make_user(username='alma', email='alma@example.com', role='manager')
    a.stripe_connect_account_id = 'acct_alma'
    b = make_user(username='bo', email='bo@example.com', role='manager')
    b.stripe_connect_account_id = 'acct_bo'
    make_user(username='cass', email='cass@example.com', role='gardener')
    g = CommunityGarden(name='Alma Garden', slug='alma-garden', organizer_id=a.id)
    _db.session.add(g)
    _db.session.commit()
    return {'a': a.id, 'b': b.id, 'garden_id': g.id}


def account_obj(acct_id, *, charges=True, payouts=True, due=None, disabled=None):
    return {'id': acct_id, 'charges_enabled': charges,
            'payouts_enabled': payouts,
            'requirements': {'currently_due': due or [], 'past_due': [],
                             'disabled_reason': disabled}}


def payout_obj(pid, amount=4850, status='paid'):
    return {'id': pid, 'amount': amount, 'currency': 'usd', 'status': status,
            'created': 1_800_000_000, 'arrival_date': 1_800_086_400}


class FakeList:
    def __init__(self, data):
        self.data = data


def run(app, args=(), *, accounts=None, payouts=None, key='sk_test_x',
        monkeypatch=None):
    """Invoke the command with Stripe faked out."""
    accounts = accounts or {}
    payouts = payouts or {}

    def fake_retrieve(acct_id, **kw):
        value = accounts.get(acct_id)
        if isinstance(value, Exception):
            raise value
        if value is None:
            raise ValueError('No such account: %s' % acct_id)
        return value

    def fake_payouts(limit=10, stripe_account=None, **kw):
        return FakeList(payouts.get(stripe_account, []))

    env = {'STRIPE_SECRET_KEY': key} if key else {}
    with patch.dict('os.environ', env, clear=False), \
            patch('stripe.Account.retrieve', side_effect=fake_retrieve), \
            patch('stripe.Payout.list', side_effect=fake_payouts):
        if not key:
            with patch('app.stripe_service.is_configured', return_value=False):
                return app.test_cli_runner().invoke(args=['stripe-sync-accounts', *args])
        return app.test_cli_runner().invoke(args=['stripe-sync-accounts', *args])


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------
def test_it_fills_in_health_for_managers_who_never_sent_an_event(app, connected):
    from app.models import GardenFinanceEvent, User

    result = run(app, accounts={
        'acct_alma': account_obj('acct_alma'),
        'acct_bo': account_obj('acct_bo', charges=False, payouts=False,
                               due=['individual.verification.document'],
                               disabled='requirements.past_due'),
    })
    assert result.exit_code == 0, result.output

    alma = _db.session.get(User, connected['a'])
    assert alma.stripe_charges_enabled and alma.stripe_payouts_enabled
    assert alma.stripe_onboarding_complete is True
    # The NULL that made the UI say "Stripe hasn't sent an account update yet".
    assert alma.stripe_account_synced_at is not None

    bo = _db.session.get(User, connected['b'])
    assert bo.stripe_disabled_reason == 'requirements.past_due'
    assert json.loads(bo.stripe_requirements_due) == [
        'individual.verification.document']
    assert bo.stripe_onboarding_complete is False

    states = {e.user_id: e.status
              for e in GardenFinanceEvent.query.filter_by(kind='account')}
    assert states == {connected['a']: 'ok', connected['b']: 'restricted'}


def test_users_without_a_connect_account_are_left_alone(app, connected):
    from app.models import User
    run(app, accounts={'acct_alma': account_obj('acct_alma'),
                       'acct_bo': account_obj('acct_bo')})
    cass = User.query.filter_by(email='cass@example.com').one()
    assert cass.stripe_account_synced_at is None


def test_one_dead_account_does_not_stop_the_run(app, connected):
    """A leftover test-mode id under live keys is exactly the case that would
    otherwise abort a backfill halfway through."""
    from app.models import User
    result = run(app, accounts={
        'acct_alma': RuntimeError('No such account: acct_alma'),
        'acct_bo': account_obj('acct_bo'),
    })
    assert result.exit_code == 0, result.output
    assert '1 failed' in result.output
    assert _db.session.get(User, connected['a']).stripe_account_synced_at is None
    assert _db.session.get(User, connected['b']).stripe_account_synced_at is not None


def test_dry_run_reads_but_writes_nothing(app, connected):
    from app.models import GardenFinanceEvent, User
    result = run(app, ['--dry-run'],
                 accounts={'acct_alma': account_obj('acct_alma'),
                           'acct_bo': account_obj('acct_bo')},
                 payouts={'acct_alma': [payout_obj('po_dry')]})
    assert 'Dry run' in result.output
    assert _db.session.get(User, connected['a']).stripe_account_synced_at is None
    assert GardenFinanceEvent.query.count() == 0


def test_a_single_account_can_be_targeted(app, connected):
    from app.models import User
    run(app, ['--account', 'acct_bo'],
        accounts={'acct_alma': account_obj('acct_alma'),
                  'acct_bo': account_obj('acct_bo')})
    assert _db.session.get(User, connected['a']).stripe_account_synced_at is None
    assert _db.session.get(User, connected['b']).stripe_account_synced_at is not None


def test_without_a_stripe_key_it_says_so_instead_of_failing(app, connected):
    result = run(app, key=None, accounts={})
    assert result.exit_code == 0
    assert 'not set' in result.output


# ---------------------------------------------------------------------------
# Payouts
# ---------------------------------------------------------------------------
def test_it_seeds_the_deposits_a_manager_already_received(app, connected):
    from app.models import GardenFinanceEvent
    run(app, accounts={'acct_alma': account_obj('acct_alma'),
                       'acct_bo': account_obj('acct_bo')},
        payouts={'acct_alma': [payout_obj('po_1'), payout_obj('po_2', 900,
                                                              status='failed')]})
    rows = GardenFinanceEvent.query.filter_by(kind='payout').all()
    assert len(rows) == 2
    assert {r.status for r in rows} == {'paid', 'failed'}
    # Account-scoped: a payout can span several gardens.
    assert all(r.garden_id is None and r.user_id == connected['a'] for r in rows)
    assert all(r.connected_account_id == 'acct_alma' for r in rows)


def test_running_it_twice_does_not_duplicate_anything(app, connected):
    """It will be run more than once — after wiring the endpoint, and again
    when someone wonders whether it worked."""
    from app.models import GardenFinanceEvent
    args = dict(accounts={'acct_alma': account_obj('acct_alma'),
                          'acct_bo': account_obj('acct_bo')},
                payouts={'acct_alma': [payout_obj('po_1')]})
    run(app, **args)
    second = run(app, **args)
    assert '0 new payout' in second.output
    assert GardenFinanceEvent.query.filter_by(kind='payout').count() == 1
    assert GardenFinanceEvent.query.filter_by(kind='account').count() == 2


def test_payouts_can_be_skipped(app, connected):
    from app.models import GardenFinanceEvent
    run(app, ['--no-payouts'],
        accounts={'acct_alma': account_obj('acct_alma'),
                  'acct_bo': account_obj('acct_bo')},
        payouts={'acct_alma': [payout_obj('po_1')]})
    assert GardenFinanceEvent.query.filter_by(kind='payout').count() == 0


def test_a_payout_listing_failure_still_leaves_the_account_synced(app, connected):
    from app.models import User

    def boom(*a, **kw):
        raise RuntimeError('payouts unavailable for this account')

    with patch.dict('os.environ', {'STRIPE_SECRET_KEY': 'sk_test_x'}), \
            patch('stripe.Account.retrieve',
                  side_effect=lambda acct, **kw: account_obj(acct)), \
            patch('stripe.Payout.list', side_effect=boom):
        result = app.test_cli_runner().invoke(args=['stripe-sync-accounts'])
    assert result.exit_code == 0, result.output
    assert 'payouts unavailable' in result.output
    assert _db.session.get(User, connected['a']).stripe_account_synced_at is not None


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------
def test_a_backfill_stays_quiet_by_default(app, connected):
    """Messaging every manager at once about a state they have been in for
    weeks is not news, it is noise.

    Set up a genuine transition (unknown -> restricted) on a manager who owns
    a garden, so silence here is a decision rather than an accident.
    """
    from app.models import Notification
    run(app, accounts={
        'acct_alma': account_obj('acct_alma', charges=False, payouts=False,
                                 disabled='requirements.past_due'),
        'acct_bo': account_obj('acct_bo')})

    from app.models import User
    assert _db.session.get(User, connected['a']).stripe_disabled_reason
    assert Notification.query.filter_by(type='stripe_account').count() == 0


def test_notify_tells_only_the_managers_who_need_to_act(app, connected):
    from app.models import Notification
    run(app, ['--notify'],
        accounts={'acct_alma': account_obj('acct_alma'),          # ok
                  'acct_bo': account_obj('acct_bo', charges=False,
                                         payouts=False)})          # needs action
    # Alma ends up healthy (nothing to act on) and Bo's state is unchanged
    # from where it started, so neither is worth a message.
    assert Notification.query.filter_by(type='stripe_account').count() == 0

    from app.models import CommunityGarden
    _db.session.add(CommunityGarden(name='Bo Garden', slug='bo-garden',
                                    organizer_id=connected['b']))
    _db.session.commit()
    run(app, ['--notify'],
        accounts={'acct_alma': account_obj('acct_alma'),
                  'acct_bo': account_obj('acct_bo', charges=True, payouts=True)})
    run(app, ['--notify'],
        accounts={'acct_alma': account_obj('acct_alma'),
                  'acct_bo': account_obj('acct_bo', charges=False, payouts=False)})
    notes = Notification.query.filter_by(user_id=connected['b'],
                                         type='stripe_account').all()
    assert [n.title for n in notes] == ['Stripe needs more information']
    assert notes[0].link.startswith('/gardens/grd_')
    assert '/admin/finance?sub=stripe' in notes[0].link


# ---------------------------------------------------------------------------
# The drift guard
# ---------------------------------------------------------------------------
def test_the_backfill_and_the_webhook_agree_exactly(app, connected, client):
    """Same Stripe Account, two code paths, identical resulting state.

    This codebase has been bitten repeatedly by one rule written down in two
    places. An account mirrored one way by the webhook and another way by the
    backfill would put managers in a state neither path explains — and the
    symptom would be a finance screen that quietly disagrees with Stripe.
    """
    from app.models import GardenFinanceEvent, User

    account = account_obj('acct_alma', charges=False, payouts=True,
                          due=['company.tax_id'], disabled=None)

    def snapshot(user):
        return {
            'charges': user.stripe_charges_enabled,
            'payouts': user.stripe_payouts_enabled,
            'requirements': user.stripe_requirements_due,
            'disabled': user.stripe_disabled_reason,
            'onboarded': user.stripe_onboarding_complete,
        }

    # Path A — the backfill.
    run(app, ['--account', 'acct_alma', '--no-payouts'],
        accounts={'acct_alma': account})
    via_cli = snapshot(_db.session.get(User, connected['a']))
    cli_row = GardenFinanceEvent.query.filter_by(kind='account').one()
    cli_ledger = (cli_row.stripe_object_id, cli_row.status, cli_row.description)

    # Reset the user, keep nothing but the account id.
    alma = _db.session.get(User, connected['a'])
    alma.stripe_charges_enabled = False
    alma.stripe_payouts_enabled = False
    alma.stripe_requirements_due = None
    alma.stripe_disabled_reason = None
    alma.stripe_account_synced_at = None
    alma.stripe_onboarding_complete = False
    GardenFinanceEvent.query.delete()
    _db.session.commit()

    # Path B — the webhook.
    client.post('/api/webhooks/stripe',
                data=json.dumps({'id': 'evt_agree', 'type': 'account.updated',
                                 'account': 'acct_alma',
                                 'data': {'object': account}}),
                content_type='application/json')
    via_webhook = snapshot(_db.session.get(User, connected['a']))
    hook_row = GardenFinanceEvent.query.filter_by(kind='account').one()
    hook_ledger = (hook_row.stripe_object_id, hook_row.status,
                   hook_row.description)

    assert via_cli == via_webhook
    assert cli_ledger == hook_ledger
