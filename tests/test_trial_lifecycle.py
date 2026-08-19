"""Garden trial-lifecycle drip tests.

Covers the naive/aware datetime bug (tz-less columns return NAIVE datetimes;
the drip subtracted them from an aware `now` and the whole job aborted with
TypeError on the first trialing sub), the last_drip_day catch-up mechanism,
the day-2 trial nudge for gardens with no subscription, and the
/billing/status naive trial_end 500.

All sends are mocked at the email_service / sms_service function level — the
drip imports them at call time, so patching the module attribute works.
"""
import itertools
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app import db as _db
from tests.conftest import login_via_api


def _naive_now():
    """Aware-UTC now stripped naive — exactly what the tz-less columns return."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


_counter = itertools.count()


@pytest.fixture()
def make_trial(db_session, make_user):
    """Factory: organizer + garden + GardenSubscription with a NAIVE
    trial_start `days_ago` days (plus an hour) in the past."""
    from app.models import CommunityGarden, GardenSubscription

    def _make(days_ago, status='trialing', last_drip_day=None, trial_len=14,
              sms=False):
        n = next(_counter)
        extra = {'sms_opt_in': True, 'phone_number': '+14025550100'} if sms else {}
        organizer = make_user(username=f'trialorg{n}',
                              email=f'trialorg{n}@example.com',
                              role='manager', **extra)
        garden = CommunityGarden(
            name=f'Trial Garden {n}',
            slug=f'trial-garden-{n}-{uuid.uuid4().hex[:6]}',
            organizer_id=organizer.id,
            subscription_status=status)
        db_session.add(garden)
        db_session.flush()
        start = _naive_now() - timedelta(days=days_ago, hours=1)
        sub = GardenSubscription(
            garden_id=garden.id, status=status,
            trial_start=start,                              # NAIVE on purpose
            trial_end=start + timedelta(days=trial_len),    # NAIVE on purpose
            last_drip_day=last_drip_day)
        db_session.add(sub)
        db_session.commit()
        return garden, sub, organizer

    return _make


def _run():
    from app.cli import run_garden_trial_lifecycle
    run_garden_trial_lifecycle()


# ---------------------------------------------------------------------------
# Naive trial_start must not crash the drip, and the right email must fire
# ---------------------------------------------------------------------------
def test_day3_naive_trial_start_sends_progress(make_trial):
    garden, sub, organizer = make_trial(3)
    with patch('app.email_service.send_garden_trial_progress') as progress, \
         patch('app.email_service.send_garden_trial_halfway') as halfway:
        _run()
    progress.assert_called_once()
    assert progress.call_args[0][0].id == garden.id
    halfway.assert_not_called()
    _db.session.refresh(sub)
    assert sub.last_drip_day == 3


def test_day5_catchup_sends_missed_day3(make_trial):
    """A missed heartbeat (nothing sent by day 5, last_drip_day NULL) must
    still deliver the day-3 email instead of skipping it forever."""
    garden, sub, organizer = make_trial(5, last_drip_day=None)
    with patch('app.email_service.send_garden_trial_progress') as progress, \
         patch('app.email_service.send_garden_trial_halfway') as halfway:
        _run()
    progress.assert_called_once()
    halfway.assert_not_called()  # not due yet — no spraying ahead
    _db.session.refresh(sub)
    assert sub.last_drip_day == 3


def test_day12_sends_expiring_email_and_sms(make_trial):
    garden, sub, organizer = make_trial(12, last_drip_day=7, sms=True)
    with patch('app.email_service.send_garden_trial_expiring') as expiring, \
         patch('app.sms_service.send_garden_trial_expiring_sms') as sms:
        _run()
    expiring.assert_called_once()
    sms.assert_called_once()
    assert sms.call_args[0][0] == '+14025550100'
    _db.session.refresh(sub)
    assert sub.last_drip_day == 12


def test_day14_expires_then_sends_ended(make_trial):
    """Expiry runs before the drip, so a trial hitting day 14 flips to
    'expired' and gets the 'trial ended' email in the same run."""
    garden, sub, organizer = make_trial(14, status='trialing', last_drip_day=12)
    with patch('app.email_service.send_garden_trial_ended') as ended:
        _run()
    ended.assert_called_once()
    _db.session.refresh(sub)
    _db.session.refresh(garden)
    assert sub.status == 'expired'
    assert garden.subscription_status == 'expired'
    assert sub.last_drip_day == 14


def test_day21_sends_reengagement(make_trial):
    garden, sub, organizer = make_trial(21, status='expired', last_drip_day=14)
    with patch('app.email_service.send_garden_trial_reengagement') as reeng:
        _run()
    reeng.assert_called_once()
    _db.session.refresh(sub)
    assert sub.last_drip_day == 21


def test_drip_never_double_sends(make_trial):
    garden, sub, organizer = make_trial(3)
    with patch('app.email_service.send_garden_trial_progress') as progress:
        _run()
        _run()
    progress.assert_called_once()


def test_converted_sub_gets_no_drip(make_trial):
    """An 'active' (paid) subscription matches no drip step."""
    garden, sub, organizer = make_trial(7, status='active')
    with patch('app.email_service.send_garden_trial_progress') as progress, \
         patch('app.email_service.send_garden_trial_halfway') as halfway:
        _run()
    progress.assert_not_called()
    halfway.assert_not_called()


# ---------------------------------------------------------------------------
# Day-2 nudge for gardens that never started a trial
# ---------------------------------------------------------------------------
def test_day2_nudge_sent_once(db_session, make_user):
    from app.models import CommunityGarden
    organizer = make_user(username='nudgeorg', email='nudgeorg@example.com',
                          role='manager')
    garden = CommunityGarden(
        name='Nudge Garden', slug=f'nudge-garden-{uuid.uuid4().hex[:6]}',
        organizer_id=organizer.id,
        created_at=_naive_now() - timedelta(days=3))
    db_session.add(garden)
    db_session.commit()

    with patch('app.email_service.send_garden_trial_nudge') as nudge:
        _run()
        _run()  # marker set — second run must not re-send
    nudge.assert_called_once()
    assert nudge.call_args[0][0].id == garden.id
    _db.session.refresh(garden)
    assert garden.trial_nudge_sent_at is not None


def test_no_nudge_for_fresh_or_subscribed_gardens(db_session, make_user, make_trial):
    from app.models import CommunityGarden
    organizer = make_user(username='freshorg', email='freshorg@example.com',
                          role='manager')
    fresh = CommunityGarden(
        name='Fresh Garden', slug=f'fresh-garden-{uuid.uuid4().hex[:6]}',
        organizer_id=organizer.id, created_at=_naive_now())
    db_session.add(fresh)
    db_session.commit()
    # A garden WITH a subscription, old enough to qualify otherwise.
    make_trial(3)

    with patch('app.email_service.send_garden_trial_nudge') as nudge, \
         patch('app.email_service.send_garden_trial_progress'):
        _run()
    nudge.assert_not_called()


# ---------------------------------------------------------------------------
# /billing/status must survive a naive trial_end (used to 500 with TypeError)
# ---------------------------------------------------------------------------
def test_billing_status_with_naive_trial_end(client, db_session, make_user):
    from app.models import CommunityGarden, GardenSubscription
    organizer = make_user(username='statorg', email='statorg@example.com',
                          role='manager', password='GoodPass1')
    garden = CommunityGarden(
        name='Status Garden', slug=f'status-garden-{uuid.uuid4().hex[:6]}',
        organizer_id=organizer.id, subscription_status='trialing')
    db_session.add(garden)
    db_session.flush()
    start = _naive_now() - timedelta(days=2)
    sub = GardenSubscription(
        garden_id=garden.id, status='trialing',
        trial_start=start,
        trial_end=_naive_now() + timedelta(days=5, hours=2))  # NAIVE
    db_session.add(sub)
    db_session.commit()
    garden_id = garden.id

    login_via_api(client, 'statorg@example.com', 'GoodPass1')
    resp = client.get(f'/api/gardens/{garden_id}/billing/status')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['status'] == 'trialing'
    assert body['trial_days_remaining'] == 5
