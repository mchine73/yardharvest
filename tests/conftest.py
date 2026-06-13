"""Shared pytest fixtures for the YardHarvest test suite.

Notes on the harness:
- We use a temp *file* SQLite DB (NOT :memory:) because Flask-SQLAlchemy may
  open multiple connections and an in-memory DB is per-connection.
- The DB URI must be set on the Config class BEFORE create_app() runs, because
  create_app() calls db.create_all() internally during app construction.
- SECRET_KEY must be present in the environment before config.py is imported,
  otherwise the dev fallback is used (fine) -- we set it explicitly for clarity.
- The REST /api/* blueprints are CSRF-exempt. HTML form blueprints use Flask-WTF
  CSRF, so we disable CSRF on the test app for any form POSTs.
"""
import os
import tempfile

import pytest

# Ensure a SECRET_KEY is present before config.py is imported.
os.environ.setdefault('SECRET_KEY', 'test-secret')
os.environ.pop('FLASK_ENV', None)

# Test database selection:
#   TEST_DATABASE_URL set  -> use it (CI runs the suite against Postgres so the
#                             Postgres-only paths, e.g. func.greatest in earnings,
#                             are actually exercised — SQLite can't run them).
#   otherwise              -> a throwaway temp-file SQLite DB (fast local default).
# We read TEST_DATABASE_URL (not DATABASE_URL) so this never points at a real
# database, and we clear DATABASE_URL so config.py doesn't treat tests as prod.
os.environ.pop('DATABASE_URL', None)
_test_db_url = os.environ.get('TEST_DATABASE_URL', '')

from config import Config  # noqa: E402

_db_fd = _db_path = None
if _test_db_url:
    Config.SQLALCHEMY_DATABASE_URI = _test_db_url
else:
    # Point the database at a temp file BEFORE create_app() runs.
    _db_fd, _db_path = tempfile.mkstemp(suffix='.db')
    Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///' + _db_path.replace('\\', '/')

from app import create_app, db as _db, limiter as _limiter  # noqa: E402
from app.models import User, SiteEmailConfig  # noqa: E402


@pytest.fixture(scope='session')
def app():
    """Session-scoped Flask app backed by a temp-file SQLite DB."""
    application = create_app()
    application.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,   # disable CSRF for HTML form POSTs in tests
        RATELIMIT_ENABLED=False,  # disable Flask-Limiter so repeated calls don't 429
    )
    # The limiter reads its config at init_app time, so toggle it off directly.
    _limiter.enabled = False

    yield application

    # Teardown: drop tables and remove the temp DB file (SQLite only).
    with application.app_context():
        _db.session.remove()
        _db.drop_all()
        _db.engine.dispose()
    if _db_fd is not None:
        os.close(_db_fd)
        try:
            os.remove(_db_path)
        except OSError:
            pass


@pytest.fixture()
def db_session(app):
    """Provide the SQLAlchemy session inside an app context.

    Cleans up any rows created during the test so tests stay isolated.
    """
    with app.app_context():
        yield _db.session
        _db.session.rollback()
        # Wipe data between tests in FK-safe order (children before parents) so
        # this works on Postgres (CI), which enforces foreign keys — SQLite does
        # not, which is why a selective per-model delete passed locally but the
        # garden tables (referencing user) violated FKs on Postgres at teardown.
        # Keep the PlantingGuide reference rows seeded once at app startup.
        keep = {'planting_guide'}
        for table in reversed(_db.metadata.sorted_tables):
            if table.name in keep:
                continue
            _db.session.execute(table.delete())
        _db.session.commit()


@pytest.fixture()
def client(app, db_session):
    """A Flask test client. Depends on db_session so data is cleaned between tests."""
    return app.test_client()


# ---- Helper fixtures / factories ----

@pytest.fixture()
def make_user(db_session):
    """Factory to create and persist a User with a known password."""
    created = []

    def _make(username='alice', email=None, password='Password1', role='both',
              **kwargs):
        email = email or f'{username}@example.com'
        user = User(
            username=username,
            email=email.lower(),
            role=role,
            display_name=kwargs.pop('display_name', username),
            **kwargs,
        )
        user.set_password(password)
        db_session.add(user)
        db_session.commit()
        created.append(user.id)
        return user

    return _make


@pytest.fixture()
def enable_marketplace(db_session):
    """Create a SiteEmailConfig with marketplace enabled.

    Needed because allowed_signup_roles() returns garden roles
    (manager/gardener) unless marketplace_enabled is True.
    """
    cfg = SiteEmailConfig(marketplace_enabled=True)
    db_session.add(cfg)
    db_session.commit()
    return cfg


def login_via_api(client, email, password):
    """Log a user in through the REST auth API; returns the response."""
    return client.post('/api/auth/login', json={'email': email, 'password': password})
