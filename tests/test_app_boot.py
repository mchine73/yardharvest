"""Tests that the app factory boots and registers expected routes."""


def test_create_app_succeeds(app):
    assert app is not None
    assert app.config['TESTING'] is True


def test_uses_temp_sqlite_db(app):
    uri = app.config['SQLALCHEMY_DATABASE_URI']
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
