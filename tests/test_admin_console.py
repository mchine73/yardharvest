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
