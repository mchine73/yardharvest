"""Fully-featured analytics dashboard: trend timeseries, period-over-period
comparison, visitor segments (new/returning, logged-in/anon), referrer
channels, and CSV export. The timeseries bucket SQL is dialect-specific
(SQLite strftime / Postgres to_char), so these run on both in CI."""
from datetime import datetime, timezone, timedelta

from app import db as _db
from app.models import AnalyticsEvent
from tests.conftest import login_via_api


def _ev(client, event_type, session_id, **kw):
    return client.post('/api/analytics/event', json={
        'event_type': event_type,
        'session_id': session_id,
        'page_url': kw.get('page_url', '/x'),
        'referrer': kw.get('referrer', ''),
        'metadata': kw.get('metadata'),
        'device_type': kw.get('device_type', 'desktop'),
    })


def _admin_login(client, make_user):
    make_user(username='aadmin', email='aadmin@example.com', role='both', is_admin=True)
    assert login_via_api(client, 'aadmin@example.com', 'Password1').status_code == 200


def test_timeseries_gap_filled_and_counts(client, make_user):
    for _ in range(3):
        assert _ev(client, 'page_view', 's1').get_json()['tracked'] is True
    _ev(client, 'page_view', 's2')
    _admin_login(client, make_user)

    data = client.get('/api/admin/analytics/timeseries?period=month').get_json()
    assert data['granularity'] == 'day'
    # Gap-filled to a continuous daily series (~30 days), not just days with data.
    assert isinstance(data['series'], list) and len(data['series']) >= 28
    assert sum(p['page_views'] for p in data['series']) == 4
    assert sum(p['sessions'] for p in data['series']) >= 2

    # The 'day' period buckets hourly.
    assert client.get('/api/admin/analytics/timeseries?period=day').get_json()['granularity'] == 'hour'


def test_overview_segments_channels_previous(client, make_user, app):
    # Backdate an event so session 'ret' qualifies as a returning visitor.
    with app.app_context():
        _db.session.add(AnalyticsEvent(
            session_id='ret', event_type='page_view', page_url='/x',
            created_at=datetime.now(timezone.utc) - timedelta(days=60)))
        _db.session.commit()
    _ev(client, 'page_view', 'ret')                                           # returning
    _ev(client, 'page_view', 'fresh1')                                        # new, Direct
    _ev(client, 'page_view', 'fresh2', referrer='https://www.google.com/x')   # new, Search
    _admin_login(client, make_user)

    data = client.get('/api/admin/analytics/overview?period=month').get_json()
    seg = data['segments']
    assert seg['returning_sessions'] >= 1
    assert seg['new_sessions'] >= 2
    assert seg['anon_sessions'] >= 3 and seg['logged_in_sessions'] == 0
    channels = {c['channel'] for c in data['channels']}
    assert 'Search' in channels and 'Direct' in channels
    assert 'previous' in data  # present (possibly zeros) for a bounded period


def test_csv_export(client, make_user):
    _ev(client, 'page_view', 'csv1', page_url='/home')
    _admin_login(client, make_user)

    r = client.get('/api/admin/analytics/export.csv?period=month')
    assert r.status_code == 200
    assert 'text/csv' in r.content_type
    assert 'attachment' in r.headers.get('Content-Disposition', '')
    lines = r.get_data(as_text=True).splitlines()
    assert lines[0].startswith('created_at,event_type,session_id')
    assert any('/home' in ln for ln in lines[1:])


def test_dashboard_requires_admin(client, make_user):
    make_user(username='plain', email='plain@example.com', role='both')
    assert login_via_api(client, 'plain@example.com', 'Password1').status_code == 200
    assert client.get('/api/admin/analytics/timeseries?period=month').status_code in (401, 403)
    assert client.get('/api/admin/analytics/export.csv').status_code in (401, 403)
