"""Analytics ingestion whitelist + conversion-funnel counting.

The funnel was returning zeros because the frontend never emitted the funnel
events (only page_view). The frontend now calls trackEvent(...) at each step;
these tests pin the backend contract those events rely on: the ingest whitelist
accepts the funnel events, and the funnel endpoint counts distinct sessions.
"""
from tests.conftest import login_via_api


def _event(client, event_type, session_id, metadata=None):
    return client.post('/api/analytics/event', json={
        'event_type': event_type,
        'session_id': session_id,
        'page_url': '/x',
        'metadata': metadata,
    })


def test_ingest_whitelist(client):
    ok = _event(client, 'listing_view', 's1')
    assert ok.status_code == 201 and ok.get_json()['tracked'] is True

    bad = _event(client, 'totally_made_up_event', 's1')
    assert bad.status_code == 200 and bad.get_json()['tracked'] is False


def test_funnel_counts_distinct_sessions(client, make_user, app):
    # Session A completes the marketplace funnel; B drops after add-to-cart;
    # C is a registration start.
    for ev in ('listing_view', 'add_to_cart', 'checkout_start', 'checkout_complete'):
        assert _event(client, ev, 'sa').get_json()['tracked'] is True
    _event(client, 'listing_view', 'sb')
    _event(client, 'add_to_cart', 'sb')
    _event(client, 'register_start', 'sc')

    make_user(username='analyticsadmin', email='aa@example.com', role='both', is_admin=True)
    assert login_via_api(client, 'aa@example.com', 'Password1').status_code == 200

    r = client.get('/api/admin/analytics/funnel?period=year')
    assert r.status_code == 200, r.get_data(as_text=True)
    data = r.get_json()
    assert data['marketplace'] == {
        'listing_view': 2, 'add_to_cart': 2,
        'checkout_start': 1, 'checkout_complete': 1,
    }
    assert data['registration']['register_start'] == 1
    assert data['registration']['register_complete'] == 0
