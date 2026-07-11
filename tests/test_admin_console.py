"""Platform-admin console behaviors: the email-config partial-payload
contract (which the marketplace kill-switch isolation depends on) and
admin mutation guards."""
import pytest

from tests.conftest import login_via_api


@pytest.fixture()
def admin_client(client, db_session, make_user):
    make_user(username='consoleadmin', is_admin=True)
    assert login_via_api(client, 'consoleadmin@example.com',
                         'Password1').status_code == 200
    return client


def test_email_config_partial_payload_leaves_toggles(admin_client):
    """update_email_config applies per-key partial updates: a payload WITHOUT
    marketplace_enabled must leave the mode untouched. The frontend now
    deliberately excludes the kill-switch from every bulk save ("Save
    Changes" / "Save & preview") and flips it only via its own confirmed
    call — this test documents the backend contract that isolation relies on."""
    r = admin_client.put('/api/admin/email-config',
                         json={'marketplace_enabled': True})
    assert r.status_code == 200
    assert r.get_json()['marketplace_enabled'] is True

    # A bulk settings save without the key must not flip the mode.
    r = admin_client.put('/api/admin/email-config',
                         json={'from_name': 'YardHarvest'})
    assert r.status_code == 200
    assert r.get_json()['marketplace_enabled'] is True

    # An empty payload is rejected (400) — and still flips nothing.
    r = admin_client.put('/api/admin/email-config', json={})
    assert r.status_code == 400
    r = admin_client.get('/api/admin/email-config')
    assert r.get_json()['marketplace_enabled'] is True


def test_dashboard_garden_vitals(admin_client, db_session, make_user):
    """The /admin/dashboard payload now answers the operator's weekly
    questions: status counts, trials ending within EXACTLY 7 days (boundary-
    prone), week-over-week deltas, and annual-normalized estimated MRR."""
    from datetime import datetime, timedelta, timezone
    from app import db
    from app.models import CommunityGarden, GardenSubscription

    org = make_user(username='vitalorg', role='manager')
    now = datetime.now(timezone.utc)

    def garden(slug, status=None, trial_end=None, cycle=None, created=None):
        g = CommunityGarden(name=slug, slug=slug, organizer_id=org.id)
        if created:
            g.created_at = created
        db.session.add(g)
        db.session.flush()
        if status:
            db.session.add(GardenSubscription(garden_id=g.id, status=status,
                                              billing_cycle=cycle,
                                              trial_end=trial_end))
        return g

    garden('vit-free')                                        # free (no sub)
    garden('vit-active-m', 'active', cycle='monthly')
    garden('vit-active-y', 'active', cycle='yearly')
    garden('vit-trial-in', 'trialing', trial_end=now + timedelta(days=6))
    garden('vit-trial-out', 'trialing', trial_end=now + timedelta(days=8))
    garden('vit-old', created=now - timedelta(days=10))       # last week's cohort
    db.session.commit()

    d = admin_client.get('/api/admin/dashboard').get_json()

    sc = d['gardens']['status_counts']
    assert sc['active'] == 2 and sc['trialing'] == 2 and sc['free'] >= 2
    # 7-day window boundary: 6 days out IN, 8 days out OUT.
    names = {t['name'] for t in d['trials_ending_soon']}
    assert 'vit-trial-in' in names and 'vit-trial-out' not in names
    # Week-over-week: 5 gardens created now vs 1 ten days ago.
    assert d['gardens']['new']['this_week'] == 5
    assert d['gardens']['new']['last_week'] == 1
    # MRR: monthly $15 + yearly $125/12 (defaults), annual normalized.
    assert d['estimated_mrr'] == pytest.approx(15.0 + 125.0 / 12, abs=0.02)
    # Dead marketplace fields are gone from the payload.
    assert 'pending_count' not in d and 'total_buyers' not in d
    # New Users rows carry a signup date.
    assert all('created_at' in u for u in d['recent_users'])
