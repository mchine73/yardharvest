import os
import sys
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, 'instance')
os.makedirs(INSTANCE_DIR, exist_ok=True)


class Config:
    # SECRET_KEY: required in production, dev-only fallback otherwise
    SECRET_KEY = os.environ.get('SECRET_KEY', '')
    if not SECRET_KEY:
        if os.environ.get('FLASK_ENV') == 'production' or os.environ.get('DATABASE_URL'):
            print("FATAL: SECRET_KEY environment variable must be set in production.", file=sys.stderr)
            print("Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\"", file=sys.stderr)
            sys.exit(1)
        else:
            SECRET_KEY = 'yardharvest-dev-secret-DO-NOT-USE-IN-PROD'

    # Session cookie security
    SESSION_COOKIE_SAMESITE = 'Lax'       # Blocks cross-origin POST with cookies (CSRF defense)
    SESSION_COOKIE_HTTPONLY = True          # Prevents JavaScript access to session cookie
    SESSION_COOKIE_SECURE = bool(os.environ.get('DATABASE_URL'))  # HTTPS-only in production
    PERMANENT_SESSION_LIFETIME = 86400     # 24 hours

    # Database: use DATABASE_URL env var for production (PostgreSQL),
    # fallback to SQLite for local development
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        # Render uses postgres:// but SQLAlchemy requires postgresql://
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        SQLALCHEMY_DATABASE_URI = database_url
    else:
        SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(INSTANCE_DIR, 'yardharvest.db')

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'app', 'static', 'uploads')
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024  # 8 MB max upload
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    LISTINGS_PER_PAGE = 12
    DEFAULT_SEARCH_RADIUS_MILES = 10

    # CORS origins (comma-separated in env, defaults to localhost for dev)
    CORS_ORIGINS = os.environ.get(
        'CORS_ORIGINS',
        'http://localhost:5173,http://127.0.0.1:5173'
    ).split(',')
