"""Stripe money, made visible to the garden manager who earned it.

Before this, a manager's money lived entirely in the Stripe dashboard: a
Tap-to-Pay sale wrote nothing anywhere in YardHarvest, an in-person dues tap
depended on the iOS app completing a finalize call, a dashboard refund never
reached the roster, and payouts and chargebacks had no representation at all.

These tests are written against those failures rather than against the code:
each one names the thing a manager could not previously see.
"""
import json
import uuid
from datetime import datetime, timezone

import pytest

from app import db as _db
from tests.conftest import login_via_api


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------
@pytest.fixture()
def garden(app, make_user):
    """A garden whose organizer has a connected Stripe account."""
    from app.models import CommunityGarden, GardenDuesRecord
    organizer = make_user(username='organizer', email='org@example.com',
                          role='manager', password='GoodPass1')
    organizer.stripe_connect_account_id = 'acct_mgr'
    member = make_user(username='member', email='member@example.com',
                       role='gardener', password='GoodPass1')
    g = CommunityGarden(name='Sunrise Garden',
                        slug='sunrise-%s' % uuid.uuid4().hex[:8],
                        organizer_id=organizer.id)
    _db.session.add(g)
    _db.session.flush()
    rec = GardenDuesRecord(garden_id=g.id, user_id=member.id, season_year=2026,
                           amount_due=50.0, amount_paid=0, status='unpaid')
    _db.session.add(rec)
    _db.session.commit()
    return {'garden': g, 'garden_id': g.id, 'public_id': g.public_id,
            'organizer_id': organizer.id, 'member_id': member.id,
            'dues_id': rec.id}


def post_event(client, event):
    return client.post('/api/webhooks/stripe', data=json.dumps(event),
                       content_type='application/json')


def pi_event(*, event_id, pi_id, metadata, amount=5000, fee=None,
             type_='payment_intent.succeeded', charge='ch_1', account=None,
             description=None, error=None):
    obj = {'id': pi_id, 'amount': amount, 'amount_received': amount,
           'currency': 'usd', 'metadata': metadata, 'latest_charge': charge,
           'transfer_data': {'destination': 'acct_mgr'}}
    if fee is not None:
        obj['application_fee_amount'] = fee
    if description:
        obj['description'] = description
    if error:
        obj['last_payment_error'] = error
    evt = {'id': event_id, 'type': type_, 'data': {'object': obj}}
    if account:
        evt['account'] = account
    return evt


def events_for(garden_id, kind=None):
    from app.models import GardenFinanceEvent
    q = GardenFinanceEvent.query.filter_by(garden_id=garden_id)
    if kind:
        q = q.filter_by(kind=kind)
    return q.all()


# ---------------------------------------------------------------------------
# Money coming in
# ---------------------------------------------------------------------------
def test_a_tap_to_pay_sale_is_recorded(client, app, garden):
    """The gap that started this: an ad-hoc sale left no trace in the app.

    The manager tapped a card at the plot gate, the money moved, and nothing
    in YardHarvest knew it had happened.
    """
    post_event(client, pi_event(
        event_id='evt_sale', pi_id='pi_sale',
        description='Tomato starts',
        amount=1200, fee=36,
        metadata={'type': 'garden_in_person_sale',
                  'garden_id': str(garden['garden_id']),
                  'collected_by_user_id': str(garden['organizer_id']),
                  'memo': 'Tomato starts'}))

    rows = events_for(garden['garden_id'], 'payment')
    assert len(rows) == 1
    ev = rows[0]
    assert ev.source == 'in_person_sale'
    assert ev.amount_cents == 1200
    assert ev.fee_cents == 36
    assert ev.net_cents == 1164          # what the garden actually keeps
    assert ev.stripe_charge_id == 'ch_1'  # so a later refund can find it
    assert ev.collected_by_id == garden['organizer_id']


def test_an_in_person_dues_tap_settles_without_the_phone(client, app, garden):
    """`garden_dues_in_person` had no webhook route at all.

    The iOS finalize call was the *only* thing that marked the record paid, so
    a dropped connection after a successful tap left a paying member owing.
    """
    post_event(client, pi_event(
        event_id='evt_tap', pi_id='pi_tap', amount=5000,
        metadata={'type': 'garden_dues_in_person',
                  'garden_id': str(garden['garden_id']),
                  'dues_id': str(garden['dues_id']),
                  'payer_user_id': str(garden['member_id']),
                  'collected_by_user_id': str(garden['organizer_id'])}))

    from app.models import GardenDuesRecord
    rec = _db.session.get(GardenDuesRecord, garden['dues_id'])
    assert rec.status == 'paid'
    assert rec.amount_paid == rec.amount_due
    assert rec.payment_method == 'tap_to_pay'
    assert rec.stripe_payment_intent_id == 'pi_tap'

    ev = events_for(garden['garden_id'], 'payment')[0]
    assert ev.source == 'dues_in_person'
    assert ev.dues_id == garden['dues_id']
    assert ev.counterparty == 'member'


def test_online_dues_still_settle_and_now_show_up(client, app, garden):
    post_event(client, pi_event(
        event_id='evt_online', pi_id='pi_online', fee=150,
        metadata={'type': 'garden_dues', 'garden_id': str(garden['garden_id']),
                  'dues_id': str(garden['dues_id']),
                  'user_id': str(garden['member_id'])}))

    from app.models import GardenDuesRecord
    rec = _db.session.get(GardenDuesRecord, garden['dues_id'])
    assert rec.status == 'paid'
    assert rec.payment_method == 'online'

    ev = events_for(garden['garden_id'], 'payment')[0]
    assert ev.source == 'dues_online'
    assert ev.fee_cents == 150


def test_a_redelivered_payment_does_not_double_count(client, app, garden):
    evt = pi_event(event_id='evt_dup', pi_id='pi_dup',
                   metadata={'type': 'garden_in_person_sale',
                             'garden_id': str(garden['garden_id'])})
    post_event(client, evt)
    second = post_event(client, evt)
    assert second.get_json().get('duplicate') is True
    assert len(events_for(garden['garden_id'], 'payment')) == 1


def test_the_same_payment_under_a_new_event_id_still_does_not_double_count(
        client, app, garden):
    """Stripe's idempotency ledger keys on event id, but the same PaymentIntent
    can legitimately arrive under two event ids. The ledger row is keyed on the
    Stripe object, so the money is counted once either way."""
    for eid in ('evt_a', 'evt_b'):
        post_event(client, pi_event(
            event_id=eid, pi_id='pi_same',
            metadata={'type': 'garden_in_person_sale',
                      'garden_id': str(garden['garden_id'])}))
    assert len(events_for(garden['garden_id'], 'payment')) == 1


def test_a_declined_tap_is_recorded_without_touching_the_dues(client, app, garden):
    post_event(client, pi_event(
        event_id='evt_fail', pi_id='pi_fail',
        type_='payment_intent.payment_failed',
        error={'code': 'card_declined', 'message': 'Your card was declined.'},
        metadata={'type': 'garden_dues_in_person',
                  'garden_id': str(garden['garden_id']),
                  'dues_id': str(garden['dues_id'])}))

    from app.models import GardenDuesRecord
    assert _db.session.get(GardenDuesRecord, garden['dues_id']).status == 'unpaid'
    failed = events_for(garden['garden_id'], 'payment_failed')
    assert len(failed) == 1
    assert failed[0].status == 'card_declined'
    assert failed[0].fee_cents == 0


def test_a_marketplace_payment_is_not_mistaken_for_garden_money(client, app, garden):
    post_event(client, pi_event(event_id='evt_mkt', pi_id='pi_mkt', metadata={}))
    assert events_for(garden['garden_id']) == []


# ---------------------------------------------------------------------------
# Money going back out
# ---------------------------------------------------------------------------
def _pay_dues(client, garden, pi_id='pi_paid', charge='ch_paid'):
    post_event(client, pi_event(
        event_id='evt_%s' % pi_id, pi_id=pi_id, charge=charge, amount=5000,
        metadata={'type': 'garden_dues', 'garden_id': str(garden['garden_id']),
                  'dues_id': str(garden['dues_id']),
                  'user_id': str(garden['member_id'])}))


def refund_event(event_id, charge, refunded, amount=5000, pi='pi_paid'):
    return {'id': event_id, 'type': 'charge.refunded',
            'data': {'object': {'id': charge, 'payment_intent': pi,
                                'amount': amount, 'amount_refunded': refunded,
                                'currency': 'usd'}}}


def test_a_full_refund_puts_the_member_back_on_the_roster(client, app, garden):
    """A refund issued from the Stripe dashboard used to leave the roster
    claiming the member had paid — turning a refund into forgiven dues."""
    _pay_dues(client, garden)
    post_event(client, refund_event('evt_ref', 'ch_paid', 5000))

    from app.models import GardenDuesRecord, Notification
    rec = _db.session.get(GardenDuesRecord, garden['dues_id'])
    assert rec.status == 'unpaid'
    assert rec.amount_paid == 0

    ref = events_for(garden['garden_id'], 'refund')[0]
    assert ref.status == 'full'
    assert ref.amount_cents == 5000
    assert Notification.query.filter_by(user_id=garden['organizer_id'],
                                        type='dues_refunded').count() == 1


def test_a_partial_refund_leaves_the_dues_settled(client, app, garden):
    _pay_dues(client, garden)
    post_event(client, refund_event('evt_part', 'ch_paid', 1000))

    from app.models import GardenDuesRecord
    assert _db.session.get(GardenDuesRecord, garden['dues_id']).status == 'paid'
    ref = events_for(garden['garden_id'], 'refund')[0]
    assert ref.status == 'partial'
    assert ref.amount_cents == 1000


def test_two_partial_refunds_report_the_running_total_not_the_sum(client, app, garden):
    """Stripe reports `amount_refunded` cumulatively. Appending a row per
    delivery would say $30 was returned when only $20 ever was."""
    _pay_dues(client, garden)
    post_event(client, refund_event('evt_p1', 'ch_paid', 1000))
    post_event(client, refund_event('evt_p2', 'ch_paid', 2000))

    rows = events_for(garden['garden_id'], 'refund')
    assert len(rows) == 1
    assert rows[0].amount_cents == 2000


def test_a_refund_on_a_charge_we_never_saw_is_ignored(client, app, garden):
    post_event(client, refund_event('evt_unknown', 'ch_other', 500, pi='pi_other'))
    assert events_for(garden['garden_id'], 'refund') == []


# ---------------------------------------------------------------------------
# Chargebacks
# ---------------------------------------------------------------------------
def dispute_event(event_id, status, *, charge='ch_paid', amount=5000,
                  dispute_id='dp_1', type_='charge.dispute.created'):
    return {'id': event_id, 'type': type_,
            'data': {'object': {'id': dispute_id, 'charge': charge,
                                'payment_intent': 'pi_paid', 'amount': amount,
                                'currency': 'usd', 'status': status,
                                'reason': 'fraudulent'}}}


def test_a_chargeback_reaches_the_manager_while_it_can_still_be_answered(
        client, app, garden):
    _pay_dues(client, garden)
    post_event(client, dispute_event('evt_dp', 'needs_response'))

    from app.models import Notification
    row = events_for(garden['garden_id'], 'dispute')[0]
    assert row.status == 'needs_response'
    assert row.amount_cents == 5000
    assert 'fraudulent' in (row.description or '')
    assert Notification.query.filter_by(user_id=garden['organizer_id'],
                                        type='payment_dispute').count() == 1


def test_a_dispute_that_closes_updates_the_same_row(client, app, garden):
    _pay_dues(client, garden)
    post_event(client, dispute_event('evt_dp1', 'needs_response'))
    post_event(client, dispute_event('evt_dp2', 'won',
                                     type_='charge.dispute.closed'))

    rows = events_for(garden['garden_id'], 'dispute')
    assert len(rows) == 1
    assert rows[0].status == 'won'


def test_a_lost_dispute_counts_against_the_garden_but_a_won_one_does_not(
        client, app, garden):
    from app import garden_finance
    _pay_dues(client, garden)
    post_event(client, dispute_event('evt_l1', 'lost',
                                     type_='charge.dispute.closed'))
    assert garden_finance.totals(garden['garden_id'])['disputed'] == 50.0

    post_event(client, dispute_event('evt_l2', 'won',
                                     type_='charge.dispute.closed'))
    assert garden_finance.totals(garden['garden_id'])['disputed'] == 0


# ---------------------------------------------------------------------------
# Payouts (Connect events)
# ---------------------------------------------------------------------------
def payout_event(event_id, status, amount=4850, *, payout_id='po_1',
                 account='acct_mgr', failure=None):
    # Stripe timestamps are epoch seconds; keep them recent so the default
    # 90-day feed window doesn't quietly hide the row.
    now = int(datetime.now(timezone.utc).timestamp())
    obj = {'id': payout_id, 'amount': amount, 'currency': 'usd',
           'status': status, 'created': now - 86_400,
           'arrival_date': now - 3_600}
    if failure:
        obj['failure_message'] = failure
    return {'id': event_id, 'type': 'payout.%s' % status,
            'account': account, 'data': {'object': obj}}


def test_a_payout_answers_when_the_money_reached_the_bank(client, app, garden):
    """The question the app could not answer at all. Payouts are emitted by
    the *connected* account, so `event.account` is the only link back."""
    post_event(client, payout_event('evt_po', 'paid'))

    from app.models import GardenFinanceEvent, Notification
    row = GardenFinanceEvent.query.filter_by(kind='payout').one()
    assert row.user_id == garden['organizer_id']
    assert row.garden_id is None       # account-level, not this garden's
    assert row.amount_cents == 4850
    assert Notification.query.filter_by(user_id=garden['organizer_id'],
                                        type='payout').count() == 1


def test_a_payout_is_shown_in_the_feed_but_never_added_to_garden_totals(
        client, app, garden):
    """A payout can cover several gardens. Counting it as income for one of
    them would make that garden's books wrong."""
    from app import garden_finance
    _pay_dues(client, garden)
    post_event(client, payout_event('evt_po2', 'paid'))

    feed = garden_finance.activity_query(garden['garden']).all()
    assert {e.kind for e in feed} == {'payment', 'payout'}
    assert garden_finance.totals(garden['garden_id'])['collected'] == 50.0


def test_a_failed_payout_is_surfaced_with_stripes_reason(client, app, garden):
    post_event(client, payout_event('evt_pof', 'failed',
                                    failure='Account closed'))
    from app.models import GardenFinanceEvent, Notification
    row = GardenFinanceEvent.query.filter_by(kind='payout').one()
    assert row.status == 'failed'
    assert row.description == 'Account closed'
    note = Notification.query.filter_by(user_id=garden['organizer_id'],
                                        type='payout').one()
    assert 'Account closed' in note.body


def test_a_payout_from_an_account_we_do_not_know_is_ignored(client, app, garden):
    post_event(client, payout_event('evt_po3', 'paid', account='acct_stranger'))
    from app.models import GardenFinanceEvent
    assert GardenFinanceEvent.query.filter_by(kind='payout').count() == 0


# ---------------------------------------------------------------------------
# Connected-account health
# ---------------------------------------------------------------------------
def account_event(event_id, *, charges=True, payouts=True, due=None,
                  disabled=None, account='acct_mgr'):
    return {'id': event_id, 'type': 'account.updated', 'account': account,
            'data': {'object': {
                'id': account, 'charges_enabled': charges,
                'payouts_enabled': payouts,
                'requirements': {'currently_due': due or [],
                                 'past_due': [],
                                 'disabled_reason': disabled}}}}


def test_a_restriction_is_visible_before_a_tap_fails_in_front_of_a_member(
        client, app, garden):
    from app import garden_finance
    from app.models import Notification, User

    post_event(client, account_event('evt_ok'))
    post_event(client, account_event('evt_bad', charges=False, payouts=False,
                                     due=['individual.verification.document'],
                                     disabled='requirements.past_due'))

    organizer = _db.session.get(User, garden['organizer_id'])
    assert organizer.stripe_charges_enabled is False
    # The old handler could only ever latch this True.
    assert organizer.stripe_onboarding_complete is False
    assert garden_finance.account_state(organizer) == 'restricted'
    assert garden_finance.requirements_list(organizer) == [
        'individual.verification.document']
    # Only transitions are announced, so the manager gets the completion of
    # onboarding and then the restriction — not one message per Stripe event.
    titles = [n.title for n in Notification.query.filter_by(
        user_id=garden['organizer_id'], type='stripe_account')
        .order_by(Notification.id).all()]
    assert titles == ['Stripe account is ready', 'Stripe paused your payouts']


def test_an_account_that_recovers_says_so(client, app, garden):
    from app import garden_finance
    from app.models import Notification, User

    post_event(client, account_event('evt_r1', charges=False, payouts=False,
                                     disabled='requirements.past_due'))
    post_event(client, account_event('evt_r2'))

    organizer = _db.session.get(User, garden['organizer_id'])
    assert garden_finance.account_state(organizer) == 'ok'
    titles = [n.title for n in Notification.query.filter_by(
        user_id=garden['organizer_id'], type='stripe_account').all()]
    assert 'Stripe account is ready' in titles


def test_repeated_identical_account_events_do_not_flood_the_feed(client, app, garden):
    """Stripe emits account.updated constantly. One row per *state*, one
    notification per *transition* — otherwise the feed is unreadable."""
    from app.models import GardenFinanceEvent, Notification
    post_event(client, account_event('evt_base'))          # -> ok
    for i in range(3):
        post_event(client, account_event('evt_same_%d' % i, charges=False,
                                         payouts=False))   # -> action_needed x3

    rows = GardenFinanceEvent.query.filter_by(kind='account').all()
    assert sorted(r.status for r in rows) == ['action_needed', 'ok']
    assert Notification.query.filter_by(user_id=garden['organizer_id'],
                                        type='stripe_account').count() == 2


def test_an_account_event_for_a_stranger_is_a_no_op(client, app, garden):
    resp = post_event(client, account_event('evt_x', account='acct_nobody'))
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# What the manager sees
# ---------------------------------------------------------------------------
def _login_organizer(client):
    return login_via_api(client, 'org@example.com', 'GoodPass1')


def test_the_activity_feed_shows_both_halves_of_where_the_money_went(
        client, app, garden):
    _pay_dues(client, garden)
    post_event(client, payout_event('evt_feed_po', 'paid'))
    _login_organizer(client)

    resp = client.get('/api/garden-admin/%d/finance/activity' % garden['garden_id'])
    assert resp.status_code == 200
    body = resp.get_json()
    kinds = {e['kind'] for e in body['events']}
    assert kinds == {'payment', 'payout'}
    assert body['totals']['collected'] == 50.0
    # Every row carries a line a manager can read without knowing Stripe.
    assert all(e['label'] for e in body['events'])
    assert any(e['scope'] == 'account' for e in body['events'])


def test_the_feed_is_readable_without_garden_pro(client, app, garden):
    """The endpoints that TAKE this money aren't Pro-gated, so the record of
    it isn't either — a paywall between someone and their own collections is
    the wrong trade."""
    from app.models import CommunityGarden
    g = _db.session.get(CommunityGarden, garden['garden_id'])
    assert g.subscription_status in (None, 'none')
    _pay_dues(client, garden)
    _login_organizer(client)
    resp = client.get('/api/garden-admin/%d/finance/activity' % garden['garden_id'])
    assert resp.status_code == 200
    assert len(resp.get_json()['events']) == 1


def test_someone_elses_garden_stays_private(client, app, garden, make_user):
    make_user(username='nosy', email='nosy@example.com', role='manager',
              password='GoodPass1')
    login_via_api(client, 'nosy@example.com', 'GoodPass1')
    resp = client.get('/api/garden-admin/%d/finance/activity' % garden['garden_id'])
    assert resp.status_code == 403


def test_the_payouts_endpoint_totals_only_completed_deposits(client, app, garden):
    post_event(client, payout_event('evt_p_ok', 'paid', 4000))
    post_event(client, payout_event('evt_p_bad', 'failed', 900,
                                    payout_id='po_2'))
    _login_organizer(client)

    body = client.get('/api/garden-admin/%d/finance/payouts'
                      % garden['garden_id']).get_json()
    assert body['paid_total'] == 40.0
    assert body['paid_count'] == 1
    assert body['failed_count'] == 1
    assert len(body['payouts']) == 2


def test_stripe_status_says_not_synced_when_no_connect_webhook_has_landed(
        client, app, garden):
    """A NULL sync time is the diagnosis, not a detail: it means no
    account.updated has ever arrived, i.e. the Connect endpoint isn't wired."""
    _login_organizer(client)
    body = client.get('/api/garden-admin/%d/finance/stripe-status'
                      % garden['garden_id']).get_json()
    assert body['synced_at'] is None
    assert body['state'] == 'action_needed'


def test_stripe_status_reflects_what_the_webhook_last_said(client, app, garden):
    post_event(client, account_event('evt_status'))
    _login_organizer(client)
    body = client.get('/api/garden-admin/%d/finance/stripe-status'
                      % garden['garden_id']).get_json()
    assert body['ok'] is True
    assert body['state'] == 'ok'
    assert body['charges_enabled'] and body['payouts_enabled']
    assert body['synced_at']


def test_the_season_summary_reports_stripe_money_beside_the_roster(client, app, garden):
    """The roster's "collected" includes cash and says nothing about fees.
    Stripe's figure is reported alongside it rather than merged into it."""
    from app.models import CommunityGarden, GardenSubscription
    g = _db.session.get(CommunityGarden, garden['garden_id'])
    g.subscription_status = 'active'
    _db.session.add(GardenSubscription(garden_id=g.id, status='active'))
    _db.session.commit()

    post_event(client, pi_event(
        event_id='evt_sum', pi_id='pi_sum', amount=2500, fee=75,
        metadata={'type': 'garden_in_person_sale',
                  'garden_id': str(garden['garden_id'])}))
    _login_organizer(client)

    body = client.get('/api/garden-admin/%d/finance-summary?season_year=%d'
                      % (garden['garden_id'], 2026)).get_json()
    assert body['total_collected'] == 0        # roster: nobody paid dues
    assert body['stripe']['collected'] == 25.0  # but $25 of card money arrived
    assert body['stripe']['fees'] == 0.75
    assert body['stripe']['kept'] == 24.25
    assert body['stripe']['by_source']['in_person_sale'] == 25.0


# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------
def test_connect_events_can_be_signed_by_their_own_endpoint_secret(monkeypatch):
    """Stripe issues one signing secret per endpoint, and Connect events need
    their own endpoint. A single-secret verifier rejects every one of them
    with what looks in the logs exactly like an attack."""
    from app import stripe_service
    monkeypatch.setenv('STRIPE_WEBHOOK_SECRET', 'whsec_platform')
    monkeypatch.setenv('STRIPE_CONNECT_WEBHOOK_SECRET', 'whsec_connect')
    assert stripe_service.webhook_secrets() == ['whsec_platform', 'whsec_connect']

    tried = []

    class Boom(Exception):
        pass

    def fake_construct(payload, sig, secret):
        tried.append(secret)
        if secret != 'whsec_connect':
            raise stripe_service.stripe.error.SignatureVerificationError(
                'bad sig', sig)
        return {'id': 'evt_connect', 'type': 'payout.paid'}

    monkeypatch.setattr(stripe_service.stripe.Webhook, 'construct_event',
                        staticmethod(fake_construct))
    event = stripe_service.construct_webhook_event('{}', 'sig')
    assert event['id'] == 'evt_connect'
    assert tried == ['whsec_platform', 'whsec_connect']


def test_no_secret_at_all_still_returns_none(monkeypatch):
    from app import stripe_service
    monkeypatch.delenv('STRIPE_WEBHOOK_SECRET', raising=False)
    monkeypatch.delenv('STRIPE_CONNECT_WEBHOOK_SECRET', raising=False)
    assert stripe_service.construct_webhook_event('{}', 'sig') is None
