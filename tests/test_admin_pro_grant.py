"""An admin setting a garden to 'active' must unlock every Pro feature.

The gate is written down in several places — the shared `require_garden_pro`,
plus standalone copies in photos and resources, plus the tab lock in the
dashboard. This asserts they all agree, because the failure mode is silent:
the organizer sees Pro tabs unlock and then one of them 403s.
"""
import pytest

from app import db as _db
from app.models import CommunityGarden, GardenSubscription, User
from tests.conftest import login_via_api


@pytest.fixture()
def garden(db_session, make_user):
    organizer = make_user(username='organizer', email='organizer@example.com',
                          role='manager', password='GoodPass1')
    g = CommunityGarden(name='Wallstreet Garden', slug='wallstreet-garden',
                        organizer_id=organizer.id)
    _db.session.add(g)
    _db.session.commit()
    return g


@pytest.fixture()
def admin(make_user):
    return make_user(username='platformadmin', email='padmin@example.com',
                     role='both', password='GoodPass1', is_admin=True)


def _grant(client, garden, status='active'):
    return client.post(f'/api/admin/gardens/{garden.id}/subscription-status',
                       json={'status': status})


def _all_gates(garden):
    """Every Pro check in the codebase, called against one garden.

    Named so a failure says which surface disagreed rather than just 'False'.
    """
    from app.api.garden_billing_api import require_garden_pro
    from app.api.gardens_api import _resources_pro_or_403
    from app.api.photos_api import _garden_is_pro

    return {
        'dues / shifts / messaging (require_garden_pro)': require_garden_pro(garden)[0],
        'tool checkout + QR (resources)': _resources_pro_or_403(garden) is None,
        'photo gallery (photos)': _garden_is_pro(garden.id),
    }


def test_an_admin_grant_unlocks_every_pro_surface(client, app, garden, admin):
    """The requirement, asserted against every gate at once."""
    locked = _all_gates(garden)
    assert not any(locked.values()), locked

    login_via_api(client, 'padmin@example.com', 'GoodPass1')
    assert _grant(client, garden).status_code == 200

    g = _db.session.get(CommunityGarden, garden.id)
    unlocked = _all_gates(g)
    assert all(unlocked.values()), f'still gated after an admin grant: {unlocked}'


def test_the_grant_writes_both_places_the_gates_read(client, app, garden, admin):
    """The status lives on the garden (what every gate reads) and on the
    subscription (what the billing page shows). Writing one and not the other
    is how a garden ends up unlocked but showing 'expired', or the reverse."""
    login_via_api(client, 'padmin@example.com', 'GoodPass1')
    _grant(client, garden)

    g = _db.session.get(CommunityGarden, garden.id)
    sub = GardenSubscription.query.filter_by(garden_id=garden.id).one()
    assert g.subscription_status == 'active'
    assert sub.status == 'active'
    assert sub.admin_granted is True
    # A stale cancel flag would let the nightly job expire the grant.
    assert sub.cancel_at_period_end is False


def test_a_grant_over_an_existing_expired_subscription_still_unlocks(
        client, app, garden, admin):
    """The common case: a trial ran out, then the admin comps them."""
    _db.session.add(GardenSubscription(garden_id=garden.id, status='expired',
                                       cancel_at_period_end=True))
    garden.subscription_status = 'expired'
    _db.session.commit()

    login_via_api(client, 'padmin@example.com', 'GoodPass1')
    _grant(client, garden)

    g = _db.session.get(CommunityGarden, garden.id)
    assert all(_all_gates(g).values())
    sub = GardenSubscription.query.filter_by(garden_id=garden.id).one()
    assert sub.cancel_at_period_end is False


def test_the_nightly_lifecycle_job_never_revokes_an_admin_grant(client, app, garden,
                                                                admin, monkeypatch):
    """The grant has to survive the job that runs every day on the heartbeat —
    it creates the subscription with a trial_start, which is what the drip
    ladder selects on."""
    from datetime import timedelta
    import app.cli as cli

    login_via_api(client, 'padmin@example.com', 'GoodPass1')
    _grant(client, garden)

    # Age it well past every trial and drip boundary.
    sub = GardenSubscription.query.filter_by(garden_id=garden.id).one()
    sub.trial_start = sub.trial_start - timedelta(days=60)
    sub.trial_end = sub.trial_end - timedelta(days=60)
    sub.current_period_end = sub.current_period_end - timedelta(days=60)
    _db.session.commit()

    for name in ('send_garden_trial_progress', 'send_garden_trial_halfway',
                 'send_garden_trial_expiring', 'send_garden_trial_ended',
                 'send_garden_trial_reengagement'):
        monkeypatch.setattr(f'app.email_service.{name}',
                            lambda *a, **k: pytest.fail(
                                'an admin-granted garden must not get trial email'))

    cli.run_garden_trial_lifecycle()

    g = _db.session.get(CommunityGarden, garden.id)
    assert g.subscription_status == 'active'
    assert all(_all_gates(g).values())


def test_setting_a_garden_back_to_free_relocks_everything(client, app, garden, admin):
    login_via_api(client, 'padmin@example.com', 'GoodPass1')
    _grant(client, garden)
    assert all(_all_gates(_db.session.get(CommunityGarden, garden.id)).values())

    assert _grant(client, garden, status='free').status_code == 200
    g = _db.session.get(CommunityGarden, garden.id)
    assert not any(_all_gates(g).values())
    assert GardenSubscription.query.filter_by(garden_id=garden.id).one().admin_granted is False


def test_every_gate_agrees_on_which_statuses_are_pro(app, garden):
    """The set is written down in several files. They must not drift — a
    garden that is Pro for dues but not for photos is worse than either.

    A subscription row with a fresh period end has to exist for this to mean
    anything: the past_due grace in require_garden_pro needs an anchor, and
    without one every gate says no for the same reason and the comparison
    proves nothing.
    """
    from datetime import datetime, timedelta, timezone

    _db.session.add(GardenSubscription(
        garden_id=garden.id, status='past_due',
        current_period_end=datetime.now(timezone.utc) - timedelta(days=1)))
    _db.session.commit()

    for status in ('active', 'trialing', 'expired', 'free', 'none', 'past_due'):
        garden.subscription_status = status
        _db.session.commit()
        g = _db.session.get(CommunityGarden, garden.id)
        verdicts = _all_gates(g)
        assert len(set(verdicts.values())) == 1, (
            f'gates disagree for status={status!r}: {verdicts}')
