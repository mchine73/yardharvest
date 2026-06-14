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

    # JWT signing key — separate from session SECRET_KEY for defense-in-depth
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', SECRET_KEY + '-jwt')

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
    # Accept large originals (modern phone/camera photos are routinely 5-15 MB).
    # save_photo() resizes + compresses every upload down to <= 4 MB server-side
    # AFTER the request is received, so this only governs the raw request body.
    # Must stay >= the "max 20 MB" we advertise in the upload UI, else Flask
    # rejects oversized originals with a 413 before the resize ever runs.
    MAX_CONTENT_LENGTH = 25 * 1024 * 1024  # 25 MB max upload (resized to <= 4 MB)
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    LISTINGS_PER_PAGE = 12
    DEFAULT_SEARCH_RADIUS_MILES = 10

    # CORS origins (comma-separated in env, defaults to localhost for dev)
    _cors_raw = os.environ.get(
        'CORS_ORIGINS',
        'http://localhost:5173,http://127.0.0.1:5173'
    )
    CORS_ORIGINS = [o.strip() for o in _cors_raw.split(',') if o.strip()]

    # Auto-detect Render URL so CORS/Origin validation works without manual config
    _render_url = os.environ.get('RENDER_EXTERNAL_URL', '')
    if _render_url and _render_url not in CORS_ORIGINS:
        CORS_ORIGINS.append(_render_url)

    # Public site URL used to build links in emails (password reset, email
    # verification, garden/billing links). Resolve from an explicit SITE_URL,
    # then APP_URL, then the wired custom domain in prod, then the
    # Render-provided URL, falling back to the dev frontend.
    _is_production = bool(os.environ.get('FLASK_ENV') == 'production'
                          or os.environ.get('DATABASE_URL'))
    SITE_URL = (os.environ.get('SITE_URL', '')
                or os.environ.get('APP_URL', '')
                or ('https://www.yardharvest.app' if _is_production else '')
                or _render_url
                or 'http://localhost:5173').rstrip('/')
    # Only www.yardharvest.app is wired (DNS + TLS); the bare apex does not
    # resolve. Force the www host for ANY yardharvest.app value — regardless of
    # scheme, a missing scheme, a trailing path, or apex-vs-www — so email links
    # never land on the unreachable apex.
    _host = SITE_URL.split('://')[-1].split('/')[0].strip().lower()
    if _host in ('yardharvest.app', 'www.yardharvest.app'):
        SITE_URL = 'https://www.yardharvest.app'

    # Garden Pro subscription pricing
    GARDEN_TRIAL_DAYS = int(os.environ.get('GARDEN_TRIAL_DAYS', 14))
    GARDEN_PRO_PRICE_MONTHLY = int(os.environ.get('GARDEN_PRO_PRICE_MONTHLY', 1500))  # cents
    GARDEN_PRO_PRICE_YEARLY = int(os.environ.get('GARDEN_PRO_PRICE_YEARLY', 12500))   # cents

    # Platform fee (%) taken from each garden DUES payment routed to the
    # manager's connected account. 0 = manager receives 100% of dues.
    GARDEN_DUES_FEE_PERCENT = float(os.environ.get('GARDEN_DUES_FEE_PERCENT', 0))

    # CRM marketing API token — gates the /crm/api/marketing/* endpoints used
    # by the marketing_agent CLI. Unset = API disabled (503).
    MARKETING_API_KEY = os.environ.get('MARKETING_API_KEY', '')

    # Email default From address. Must be an address on a domain verified in
    # the ZeptoMail Mail Agent, or sends are rejected.
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'no_reply@yardharvest.app')

    # Zoho ZeptoMail (transactional email API) — the platform's sole email
    # provider (pay-as-you-go; send-only "Send Mail token", not a mailbox
    # password). Unset = email is logged-only. ZEPTOMAIL_API_URL lets you point
    # at a regional data center (e.g. https://api.zeptomail.eu/v1.1/email).
    ZEPTOMAIL_TOKEN = os.environ.get('ZEPTOMAIL_TOKEN', '')
    ZEPTOMAIL_API_URL = os.environ.get('ZEPTOMAIL_API_URL', 'https://api.zeptomail.com/v1.1/email')
    # The from address ZeptoMail sends as. Defaults to a yardharvest.app address
    # (the verified sending domain); override per-environment with the env var.
    ZEPTOMAIL_FROM_EMAIL = os.environ.get('ZEPTOMAIL_FROM_EMAIL', 'no_reply@yardharvest.app')
    ZEPTOMAIL_FROM_NAME = os.environ.get('ZEPTOMAIL_FROM_NAME', 'YardHarvest')
    # CRM emails (individual sends + campaigns) send from a personal address for
    # better engagement — distinct from the platform's no_reply address. Must
    # also be on the verified yardharvest.app domain.
    CRM_FROM_EMAIL = os.environ.get('CRM_FROM_EMAIL', 'james@yardharvest.app')

    # Cloudinary object storage for user-uploaded images. Single env var
    # CLOUDINARY_URL = cloudinary://<api_key>:<api_secret>@<cloud_name>.
    # When set, uploads go to Cloudinary (CDN, survives deploys); unset = local
    # disk under UPLOAD_FOLDER (dev). Either way images resolve via /media/<ref>.
    CLOUDINARY_URL = os.environ.get('CLOUDINARY_URL', '')
