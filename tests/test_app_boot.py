"""Tests that the app factory boots and registers expected routes."""
import os


def test_create_app_succeeds(app):
    assert app is not None
    assert app.config['TESTING'] is True


def test_uses_expected_test_db(app):
    uri = app.config['SQLALCHEMY_DATABASE_URI']
    test_db_url = os.environ.get('TEST_DATABASE_URL')
    if test_db_url:
        # CI runs the suite against Postgres via TEST_DATABASE_URL.
        assert uri == test_db_url
    else:
        # Local default: a throwaway temp-file SQLite DB (never :memory:).
        assert uri.startswith('sqlite:///')
        assert ':memory:' not in uri


def _rules(app):
    return {r.rule for r in app.url_map.iter_rules()}


def test_auth_api_routes_registered(app):
    rules = _rules(app)
    assert '/api/auth/register' in rules
    assert '/api/auth/login' in rules
    assert '/api/auth/logout' in rules
    assert '/api/auth/me' in rules


def test_listings_and_cart_api_registered(app):
    rules = _rules(app)
    assert '/api/listings/browse' in rules
    assert '/api/cart/add/<int:listing_id>' in rules
    assert '/api/orders/mine' in rules


def test_expected_blueprints_registered(app):
    names = set(app.blueprints.keys())
    # REST API blueprints (always registered)
    assert 'auth_api' in names
    assert 'listings_api' in names
    assert 'cart_api' in names
    # CRM blueprint (always registered after the consolidation)
    assert 'crm' in names


def test_crm_routes_registered(app):
    """The consolidated CRM module mounts pages + marketing API under /crm."""
    rules = _rules(app)
    assert '/crm/dashboard' in rules
    assert '/crm/login' in rules
    assert '/crm/api/marketing/stats' in rules


def test_planting_guide_seeded_on_boot(app):
    """create_app() runs init_planting_guide() -- the table should be populated."""
    from app.models import PlantingGuide
    with app.app_context():
        assert PlantingGuide.query.count() > 0


# ---------------------------------------------------------------------------
# Sentry must never be able to stop anything
# ---------------------------------------------------------------------------
# A stale DSN left over from a lapsed trial printed a twenty-line BadDsn
# traceback on every CLI invocation. The command underneath kept working, but
# it read as a crash — enough to make an operator abandon a backfill that was
# running fine. Error reporting failing must not look worse than the errors it
# reports.

def test_a_malformed_dsn_does_not_stop_the_app(monkeypatch, caplog):
    import logging
    from app import _init_sentry
    monkeypatch.setenv('SENTRY_DSN', 'https://o123.ingest.sentry.io/456')  # no key
    with caplog.at_level(logging.WARNING):
        _init_sentry()          # must not raise
    assert any('Sentry is DISABLED' in r.message for r in caplog.records)


def test_the_warning_says_what_a_good_dsn_looks_like(monkeypatch, caplog):
    import logging
    from app import _init_sentry
    monkeypatch.setenv('SENTRY_DSN', 'not-even-a-url')
    with caplog.at_level(logging.WARNING):
        _init_sentry()
    msg = ' '.join(r.getMessage() for r in caplog.records)
    assert 'public-key' in msg, 'the fix should be obvious from the log line'


def test_no_dsn_is_silent(monkeypatch, caplog):
    """The normal state for this deployment now — no Sentry, no noise."""
    import logging
    from app import _init_sentry
    monkeypatch.setenv('SENTRY_DSN', '   ')
    with caplog.at_level(logging.DEBUG):
        _init_sentry()
    assert not caplog.records
