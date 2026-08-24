"""What Stripe actually charged, rather than what we assumed.

The ledger used to net out only YardHarvest's own application fee, so "You
keep" meant "collected minus our cut". That is right only while the platform
absorbs Stripe's processing fee. Once the connected account bears it instead,
every deposit was overstated by roughly 3% — on the one screen built so a
manager would not have to open Stripe.

The rule these tests defend: report the fee Stripe reports, or report that we
don't know it. Never split the difference.
"""
import json
from contextlib import contextmanager
from unittest.mock import patch

from tests.test_garden_finance import garden, pi_event, post_event  # noqa: F401


@contextmanager
def stripe_live(*, charge=None, error=None):
    """A properly signed webhook arriving at a Stripe-configured deployment.

    `construct_webhook_event` has to be stubbed as well as the key: with real
    keys present the endpoint refuses unsigned events outright, which is the
    guard that stops anyone who finds the URL from forging a paid dues record.
    """
    side = {'side_effect': error} if error else {'return_value': charge}
    with patch.dict('os.environ', {'STRIPE_SECRET_KEY': 'sk_test'}, clear=False):
        with patch('app.stripe_service.construct_webhook_event',
                   side_effect=lambda payload, sig: json.loads(payload)):
            with patch('stripe.Charge.retrieve', **side):
                yield


def fake_charge(fee_cents, *, net_cents=None, charge_id='ch_1'):
    """A Charge with transfer.destination_payment.balance_transaction expanded
    — the shape `connected_charge_fee` asks Stripe for.

    `net` is omitted unless a test supplies one. A fixture that reported net
    zero would be telling a lie no real charge tells, and the code now stores
    Stripe's net, so that lie would land in the assertions.
    """
    txn = {'id': 'txn_1', 'fee': fee_cents}
    if net_cents is not None:
        txn['net'] = net_cents
    return {
        'id': charge_id,
        'transfer': {
            'id': 'tr_1',
            'destination_payment': {'id': 'py_1', 'balance_transaction': txn},
        },
    }


def sale(client, *, garden_id, fee=None, event_id='evt_fee', pi_id='pi_fee',
         amount=5000):
    return post_event(client, pi_event(
        event_id=event_id, pi_id=pi_id, amount=amount, fee=fee,
        metadata={'type': 'garden_in_person_sale', 'garden_id': str(garden_id)}))


def payments_for(garden_id):
    from app.models import GardenFinanceEvent
    return GardenFinanceEvent.query.filter_by(garden_id=garden_id,
                                              kind='payment').all()


# ---------------------------------------------------------------------------
# The webhook path
# ---------------------------------------------------------------------------
def test_the_fee_stripe_charged_the_manager_is_recorded(client, app, garden):
    with stripe_live(charge=fake_charge(175)):
        sale(client, garden_id=garden['garden_id'], fee=150)

    ev = payments_for(garden['garden_id'])[0]
    assert ev.fee_cents == 150          # YardHarvest's cut
    assert ev.stripe_fee_cents == 175   # Stripe's cut, as reported
    assert ev.net_cents == 5000 - 150 - 175


def test_when_stripe_cannot_be_reached_the_fee_is_unknown_not_zero(client, app, garden):
    """A wrong fee is worse than a missing one: someone reconciles against
    this screen and believes it over their bank."""
    with stripe_live(error=RuntimeError('boom')):
        resp = sale(client, garden_id=garden['garden_id'], fee=150)

    assert resp.status_code == 200      # the payment is still recorded
    ev = payments_for(garden['garden_id'])[0]
    assert ev.stripe_fee_cents is None
    assert ev.amount_cents == 5000


def test_a_platform_that_absorbs_the_fee_records_a_real_zero(client, app, garden):
    """Zero is a fact and must be distinguishable from "not looked up"."""
    with stripe_live(charge=fake_charge(0)):
        sale(client, garden_id=garden['garden_id'], fee=150)

    ev = payments_for(garden['garden_id'])[0]
    assert ev.stripe_fee_cents == 0
    assert ev.net_cents == 4850


def test_no_lookup_is_attempted_when_stripe_is_unconfigured(client, app, garden):
    with patch('stripe.Charge.retrieve') as retrieve:
        sale(client, garden_id=garden['garden_id'], fee=150)
    retrieve.assert_not_called()
    assert payments_for(garden['garden_id'])[0].stripe_fee_cents is None


# ---------------------------------------------------------------------------
# Totals
# ---------------------------------------------------------------------------
def test_kept_nets_out_both_cuts(client, app, garden):
    from app import garden_finance
    with stripe_live(charge=fake_charge(175)):
        sale(client, garden_id=garden['garden_id'], fee=150)

    t = garden_finance.totals(garden['garden_id'])
    assert t['collected'] == 50.0
    assert t['fees'] == 1.50
    assert t['stripe_fees'] == 1.75
    assert t['kept'] == 46.75
    assert t['fees_complete'] is True
    assert t['unknown_fee_count'] == 0


def test_an_unknown_fee_marks_the_total_incomplete(client, app, garden):
    """`kept` becomes an upper bound, and the clients say so rather than
    quietly reporting a figure short by Stripe's cut."""
    from app import garden_finance
    with stripe_live(error=RuntimeError('boom')):
        sale(client, garden_id=garden['garden_id'], fee=150)

    t = garden_finance.totals(garden['garden_id'])
    assert t['fees_complete'] is False
    assert t['unknown_fee_count'] == 1
    assert t['stripe_fees'] == 0        # nothing known, nothing counted
    assert t['kept'] == 48.50           # ceiling: platform fee only


def test_the_api_reports_the_breakdown(client, app, garden):
    from tests.conftest import login_via_api
    with stripe_live(charge=fake_charge(175)):
        sale(client, garden_id=garden['garden_id'], fee=150)

    login_via_api(client, 'org@example.com', 'GoodPass1')
    body = client.get('/api/garden-admin/%d/finance/activity'
                      % garden['garden_id']).get_json()
    assert body['totals']['stripe_fees'] == 1.75
    assert body['totals']['kept'] == 46.75
    assert body['events'][0]['stripe_fee'] == 1.75


# ---------------------------------------------------------------------------
# The backfill
# ---------------------------------------------------------------------------
def run_backfill(app, args=(), *, charge=None, error=None, key='sk_test'):
    side = {'side_effect': error} if error else {'return_value': charge}
    env = {'STRIPE_SECRET_KEY': key} if key else {}
    with patch.dict('os.environ', env, clear=False):
        with patch('stripe.Charge.retrieve', **side):
            if not key:
                with patch('app.stripe_service.is_configured', return_value=False):
                    return app.test_cli_runner().invoke(
                        args=['stripe-backfill-fees', *args])
            return app.test_cli_runner().invoke(args=['stripe-backfill-fees', *args])


def test_the_backfill_fills_in_rows_recorded_before_we_asked(client, app, garden):
    with patch('stripe.Charge.retrieve'):   # unconfigured -> recorded as NULL
        sale(client, garden_id=garden['garden_id'], fee=150)
    assert payments_for(garden['garden_id'])[0].stripe_fee_cents is None

    result = run_backfill(app, charge=fake_charge(175))
    assert result.exit_code == 0, result.output

    ev = payments_for(garden['garden_id'])[0]
    assert ev.stripe_fee_cents == 175
    assert ev.net_cents == 4675


def test_the_backfill_is_safe_to_re_run(client, app, garden):
    with patch('stripe.Charge.retrieve'):
        sale(client, garden_id=garden['garden_id'], fee=150)
    run_backfill(app, charge=fake_charge(175))
    second = run_backfill(app, charge=fake_charge(999))
    assert 'already knows' in second.output
    assert payments_for(garden['garden_id'])[0].stripe_fee_cents == 175


def test_the_backfill_dry_run_writes_nothing(client, app, garden):
    with patch('stripe.Charge.retrieve'):
        sale(client, garden_id=garden['garden_id'], fee=150)
    result = run_backfill(app, ['--dry-run'], charge=fake_charge(175))
    assert 'Dry run' in result.output
    assert payments_for(garden['garden_id'])[0].stripe_fee_cents is None


def test_a_payment_stripe_will_not_report_on_stays_unknown(client, app, garden):
    with patch('stripe.Charge.retrieve'):
        sale(client, garden_id=garden['garden_id'], fee=150)
    result = run_backfill(app, error=RuntimeError('no such charge'))
    assert '1 still unknown' in result.output
    assert payments_for(garden['garden_id'])[0].stripe_fee_cents is None

# ---------------------------------------------------------------------------
# Where the net comes from
# ---------------------------------------------------------------------------
# YardHarvest charges no platform fee on garden collections, so what a garden
# receives is simply what Stripe says it received. Deriving it by subtraction
# was arithmetic standing in for an authority we were already calling: Stripe
# accounts for partial capture, currency conversion and cross-border
# settlement, and the subtraction cannot see any of them.


def seed_unknown(client, garden, *, amount=5000, app_fee=150):
    with patch('stripe.Charge.retrieve'):      # unconfigured -> fee recorded NULL
        sale(client, garden_id=garden['garden_id'], fee=app_fee, amount=amount)
    return payments_for(garden['garden_id'])[0]


def test_the_net_is_taken_from_stripe(client, app, garden):
    seed_unknown(client, garden)
    run_backfill(app, charge=fake_charge(175, net_cents=4825))
    ev = payments_for(garden['garden_id'])[0]
    assert ev.stripe_fee_cents == 175
    # Stripe reported 48.25 after its own fee; our platform fee comes off that.
    assert ev.net_cents == 4825 - 150


def test_when_stripe_disagrees_with_the_subtraction_stripe_wins(client, app, garden):
    """A difference is not an error. It is Stripe accounting for something the
    arithmetic cannot see, and it is reported rather than absorbed."""
    seed_unknown(client, garden)
    result = run_backfill(app, ['--dry-run'], charge=fake_charge(175, net_cents=4000))
    assert 'Stripe says $38.50 net; subtraction said $46.75' in result.output
    assert 'Stripe won, which is the point' in result.output

    run_backfill(app, charge=fake_charge(175, net_cents=4000))
    assert payments_for(garden['garden_id'])[0].net_cents == 4000 - 150


def test_a_payment_with_no_net_falls_back_to_subtraction(client, app, garden):
    """Stripe not reporting a net must not leave the row blank — the
    subtraction is a worse answer than Stripe's, and a better one than none."""
    seed_unknown(client, garden)
    result = run_backfill(app, ['--dry-run'], charge=fake_charge(175))
    assert 'fell back to subtraction' in result.output

    run_backfill(app, charge=fake_charge(175))
    assert payments_for(garden['garden_id'])[0].net_cents == 5000 - 150 - 175


def test_agreement_is_reported_quietly(client, app, garden):
    seed_unknown(client, garden)
    result = run_backfill(app, ['--dry-run'], charge=fake_charge(175, net_cents=4825))
    assert '1 from Stripe and matching the subtraction' in result.output
    assert 'differing' in result.output   # the tally names every bucket


# ---------------------------------------------------------------------------
# The platform fee we do not charge
# ---------------------------------------------------------------------------
def test_a_garden_with_no_platform_fee_says_so(client, app, garden):
    """YardHarvest takes nothing from garden collections. The finance screens
    use this to drop the tile entirely rather than render a permanent $0.00
    where a real number should be."""
    from app import garden_finance
    with stripe_live(charge=fake_charge(175, net_cents=4825)):
        sale(client, garden_id=garden['garden_id'], fee=None)

    t = garden_finance.totals(garden['garden_id'])
    assert t['has_platform_fee'] is False
    assert t['fees'] == 0
    # With no cut of ours, what the garden keeps is exactly Stripe's net.
    assert t['kept'] == 48.25


def test_a_configured_platform_fee_brings_the_line_back(client, app, garden):
    """The mechanism is shared with the marketplace, so it has to still work
    the moment a fee is set."""
    from app import garden_finance
    with stripe_live(charge=fake_charge(175, net_cents=4825)):
        sale(client, garden_id=garden['garden_id'], fee=150)

    t = garden_finance.totals(garden['garden_id'])
    assert t['has_platform_fee'] is True
    assert t['fees'] == 1.50
    assert t['kept'] == 46.75
