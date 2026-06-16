from flask import Flask, jsonify, request as flask_request, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFProtect
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from config import Config
import os

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address, default_limits=[], storage_uri="memory://")
migrate = Migrate()


def _init_sentry():
    """Initialize Sentry error tracking if SENTRY_DSN is configured.

    No-op when SENTRY_DSN is unset (local dev, or before the DSN is added in
    Render), so this is safe to call unconditionally. Traces are sampled
    lightly; PII is not sent by default.
    """
    dsn = os.environ.get('SENTRY_DSN', '')
    if not dsn:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration
        sentry_sdk.init(
            dsn=dsn,
            integrations=[FlaskIntegration()],
            environment=os.environ.get('SENTRY_ENVIRONMENT', 'production'),
            traces_sample_rate=float(os.environ.get('SENTRY_TRACES_SAMPLE_RATE', '0.05')),
            send_default_pii=False,
        )
    except Exception:
        import logging
        logging.getLogger(__name__).exception('Sentry init failed; continuing without it')


def create_app():
    _init_sentry()
    app = Flask(__name__)
    app.config.from_object(Config)

    # Email: Zoho ZeptoMail (sole provider, API-based). The only mail config
    # that survives here is the default From address; the ZeptoMail token is
    # read from env in email_service.
    app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', 'no_reply@yardharvest.app')

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'
    csrf.init_app(app)
    limiter.init_app(app)

    # Enable CORS for React frontend
    CORS(app, supports_credentials=True, origins=app.config.get('CORS_ORIGINS', ['http://localhost:5173']))

    # Defense-in-depth: validate Origin header on state-changing API requests.
    # Primary CSRF defense is SameSite=Lax session cookies (set in config.py).
    @app.before_request
    def validate_origin():
        if flask_request.method in ('GET', 'HEAD', 'OPTIONS'):
            return  # Safe methods pass through
        if not flask_request.path.startswith('/api/'):
            return  # Only protect API routes
        # Skip Origin check for mobile clients using Bearer token auth
        auth_header = flask_request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            return
        origin = flask_request.headers.get('Origin', '')
        if not origin:
            # No Origin header — fall back to the Referer's origin so a forged
            # cross-site POST that strips Origin still can't slip through. A
            # genuine same-origin request without either header is allowed
            # (SameSite=Lax cookies remain the primary CSRF defense).
            referer = flask_request.headers.get('Referer', '')
            if not referer:
                return
            from urllib.parse import urlsplit
            parts = urlsplit(referer)
            if not parts.scheme or not parts.netloc:
                return
            origin = f'{parts.scheme}://{parts.netloc}'
        allowed = set(app.config.get('CORS_ORIGINS', []))
        # Also allow same-origin (SPA served from same Flask server)
        host = flask_request.host_url.rstrip('/')
        allowed.add(host)
        # Handle X-Forwarded-Proto for reverse proxies (Render, etc.)
        scheme = flask_request.headers.get('X-Forwarded-Proto', flask_request.scheme)
        forwarded_host = f"{scheme}://{flask_request.host}"
        allowed.add(forwarded_host)
        if origin not in allowed:
            return jsonify({'error': 'Invalid origin'}), 403

    # Security headers — defense-in-depth against XSS, clickjacking, MIME sniffing
    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        # Content Security Policy. The CRM (server-rendered Jinja, admin-only)
        # uses inline event handlers (onclick/onchange/onsubmit) lifted from the
        # standalone CRM app — those require 'unsafe-inline' in script-src.
        # The public marketplace SPA keeps the strict CSP.
        is_crm = flask_request.path.startswith('/crm')
        # Stripe surfaces: js.stripe.com powers card Elements; the embedded
        # Connect components (in-app payout onboarding) additionally load
        # Connect.js and render iframes from connect-js.stripe.com and call
        # api/merchant-ui-api.stripe.com. All three must be allowed in
        # script-src/frame-src/connect-src or onboarding can't initialize.
        stripe_scripts = "https://js.stripe.com https://connect-js.stripe.com"
        script_src = (
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net"
            if is_crm
            else f"script-src 'self' https://cdn.jsdelivr.net {stripe_scripts}"
        )
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            f"{script_src}; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net; "
            # Allow images from any HTTPS host: user/garden photos can be
            # Cloudinary CDN uploads, OpenStreetMap tiles, or external/seed URLs
            # (e.g. stock photos). Images can't execute code, so this is low risk
            # while script-src stays locked down.
            "img-src 'self' data: blob: https:; "
            "connect-src 'self' https://api.stripe.com "
            "https://connect-js.stripe.com https://merchant-ui-api.stripe.com; "
            "frame-src https://js.stripe.com https://connect-js.stripe.com; "
            "object-src 'none'; "
            "base-uri 'self'"
        )
        if os.environ.get('DATABASE_URL'):  # Production only
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response

    # Make Flask-Login return 401 JSON for API requests; for CRM paths the CRM
    # blueprint runs its own session-based auth and redirects to /crm/login —
    # this handler is only reached for YH (marketplace) auth-protected routes.
    @login_manager.unauthorized_handler
    def unauthorized():
        if flask_request.path.startswith('/api/'):
            return jsonify({'error': 'Authentication required'}), 401
        from flask import redirect, url_for
        if flask_request.path.startswith('/crm'):
            return redirect(url_for('crm.login', next=flask_request.path))
        return redirect(url_for('auth.login'))

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Detect if React SPA build exists (production mode)
    spa_dir = os.path.join(os.path.dirname(app.root_path), 'frontend', 'dist')
    is_spa_mode = os.path.isdir(spa_dir)

    # ---- Original template-based blueprints (only in dev, when no SPA build) ----
    if not is_spa_mode:
        from app.routes.auth import auth_bp
        from app.routes.main import main_bp
        from app.routes.listings import listings_bp
        from app.routes.cart import cart_bp
        from app.routes.messages import messages_bp
        from app.routes.profile import profile_bp
        from app.routes.admin import admin_bp

        app.register_blueprint(auth_bp)
        app.register_blueprint(main_bp)
        app.register_blueprint(listings_bp)
        app.register_blueprint(cart_bp)
        app.register_blueprint(messages_bp)
        app.register_blueprint(profile_bp)
        app.register_blueprint(admin_bp)

    # ---- New REST API blueprints ----
    from app.api.auth_api import auth_api
    from app.api.listings_api import listings_api
    from app.api.cart_api import cart_api, orders_api
    from app.api.messages_api import messages_api
    from app.api.profile_api import profile_api
    from app.api.admin_api import admin_api
    from app.api.subscriptions_api import subscriptions_api
    from app.api.planting_api import planting_api
    from app.api.groups_api import groups_api
    from app.api.gardens_api import gardens_api
    from app.api.garden_admin_api import garden_admin_api
    from app.api.payment_api import payment_api
    from app.api.earnings_api import earnings_api
    from app.api.notifications_api import notifications_api
    from app.api.photos_api import photos_api
    from app.api.garden_billing_api import garden_billing_api
    from app.api.webhook_api import webhook_api
    from app.api.refund_api import refund_api
    from app.api.promo_api import promo_api
    from app.api.analytics_api import analytics_api

    # CSRF protection for API routes is handled via:
    # 1. SameSite=Lax session cookies (blocks cross-origin POST with credentials)
    # 2. Origin header validation (before_request middleware above)
    # Token-based CSRF is exempted since APIs use JSON + session cookies
    csrf.exempt(auth_api)
    csrf.exempt(listings_api)
    csrf.exempt(cart_api)
    csrf.exempt(orders_api)
    csrf.exempt(messages_api)
    csrf.exempt(profile_api)
    csrf.exempt(admin_api)
    csrf.exempt(subscriptions_api)
    csrf.exempt(planting_api)
    csrf.exempt(groups_api)
    csrf.exempt(gardens_api)
    csrf.exempt(garden_admin_api)
    csrf.exempt(payment_api)
    csrf.exempt(earnings_api)
    csrf.exempt(notifications_api)
    csrf.exempt(photos_api)
    csrf.exempt(garden_billing_api)
    csrf.exempt(webhook_api)
    csrf.exempt(refund_api)
    csrf.exempt(promo_api)
    csrf.exempt(analytics_api)

    app.register_blueprint(auth_api)
    app.register_blueprint(listings_api)
    app.register_blueprint(cart_api)
    app.register_blueprint(orders_api)
    app.register_blueprint(messages_api)
    app.register_blueprint(profile_api)
    app.register_blueprint(admin_api)
    app.register_blueprint(subscriptions_api)
    app.register_blueprint(planting_api)
    app.register_blueprint(groups_api)
    app.register_blueprint(gardens_api)
    app.register_blueprint(garden_admin_api)
    app.register_blueprint(payment_api)
    app.register_blueprint(earnings_api)
    app.register_blueprint(notifications_api)
    app.register_blueprint(photos_api)
    app.register_blueprint(garden_billing_api)
    app.register_blueprint(webhook_api)
    app.register_blueprint(refund_api)
    app.register_blueprint(promo_api)
    app.register_blueprint(analytics_api)

    # ---- CRM module (sales pipeline, mounted at /crm) ----
    # Consolidated from the former standalone yardharvest-crm Render service.
    # Auth is session-based and lives at /crm/login (separate from YH's auth).
    from app.crm import crm_bp
    from app.crm.marketing_api import (api_stats, api_segments, api_audience,
                                       api_merge_fields, api_campaigns)
    # The marketing API uses X-API-Key auth (not Flask-WTF CSRF tokens), so
    # exempt the JSON endpoints — the rest of the CRM blueprint keeps CSRF on
    # for its HTML forms.
    for view in (api_stats, api_segments, api_audience, api_merge_fields,
                 api_campaigns):
        csrf.exempt(view)
    app.register_blueprint(crm_bp)

    @app.context_processor
    def inject_globals():
        # current_user is None outside a request context (e.g. when an email
        # template is rendered from a run_async background thread), so guard with
        # getattr — otherwise None.is_authenticated raises and the email send
        # (and any other off-request template render) fails.
        if getattr(current_user, 'is_authenticated', False):
            from app.models import CartItem, Message
            cart_count = CartItem.query.filter_by(buyer_id=current_user.id).count()
            unread_count = Message.query.filter_by(
                recipient_id=current_user.id, is_read=False
            ).count()
            return dict(cart_count=cart_count, unread_count=unread_count)
        return dict(cart_count=0, unread_count=0)

    @app.errorhandler(403)
    def forbidden(e):
        if flask_request.path.startswith('/api/'):
            return jsonify({'error': 'Access denied'}), 403
        if is_spa_mode:
            return send_from_directory(spa_dir, 'index.html')
        return app.jinja_env.get_template('errors/404.html').render(), 403

    @app.errorhandler(500)
    def server_error(e):
        if flask_request.path.startswith('/api/'):
            return jsonify({'error': 'Internal server error'}), 500
        if is_spa_mode:
            return send_from_directory(spa_dir, 'index.html')
        return app.jinja_env.get_template('errors/500.html').render(), 500

    @app.errorhandler(429)
    def rate_limited(e):
        if flask_request.path.startswith('/api/'):
            return jsonify({'error': 'Too many requests. Please try again later.'}), 429
        return 'Too many requests', 429

    @app.errorhandler(413)
    def payload_too_large(e):
        # Flask aborts with 413 when the request body exceeds MAX_CONTENT_LENGTH,
        # before any view runs. Return JSON so the SPA shows a real message
        # instead of choking on an HTML error page (which surfaced as a silent
        # "Upload failed" on the photo upload control).
        mb = app.config.get('MAX_CONTENT_LENGTH', 0) // (1024 * 1024)
        msg = f'File too large. Maximum upload size is {mb} MB.'
        if flask_request.path.startswith('/api/'):
            return jsonify({'error': msg}), 413
        return msg, 413

    # Serve React SPA in production (when frontend/dist exists)
    # Use 404 handler approach so API blueprint routes are never overridden
    if is_spa_mode:
        @app.route('/')
        def serve_spa_root():
            return send_from_directory(spa_dir, 'index.html')

        @app.errorhandler(404)
        def spa_not_found(e):
            # API routes get JSON errors
            if flask_request.path.startswith('/api/'):
                return jsonify({'error': 'Not found'}), 404
            # Check if it's a real file in dist (JS, CSS, images)
            path = flask_request.path.lstrip('/')
            full_path = os.path.join(spa_dir, path)
            if path and os.path.isfile(full_path):
                return send_from_directory(spa_dir, path)
            # Everything else: serve index.html for React Router
            return send_from_directory(spa_dir, 'index.html')
    else:
        @app.errorhandler(404)
        def not_found(e):
            if flask_request.path.startswith('/api/'):
                return jsonify({'error': 'Not found'}), 404
            return app.jinja_env.get_template('errors/404.html').render(), 404

    # Unified media route. Image columns store a reference produced by the
    # upload helpers: a bare filename (local disk) or a Cloudinary public_id.
    # The frontend always requests /media/<ref>; this serves the local file in
    # dev, else 301-redirects to the Cloudinary CDN. Registered explicitly so it
    # takes precedence over the SPA 404 catch-all.
    @app.route('/api/health/config')
    @limiter.limit('6 per minute')
    def health_config():
        """Unauthenticated config-presence health check. Booleans only — never
        exposes secret values. Lets ops verify which integrations the running
        container sees (env wiring) without dashboard access. Rate-limited to
        deter fingerprinting, matching the other /api/health/* probes."""
        from app import cloudinary_service
        from app import sms_service
        return jsonify({
            'cloudinary_configured': cloudinary_service.is_configured(),
            'cloudinary_ok': cloudinary_service.is_working(),
            'stripe_configured': bool(os.environ.get('STRIPE_SECRET_KEY')),
            'stripe_webhook_configured': bool(os.environ.get('STRIPE_WEBHOOK_SECRET')),
            'zeptomail_configured': bool(os.environ.get('ZEPTOMAIL_TOKEN')
                                         or app.config.get('ZEPTOMAIL_TOKEN')),
            'twilio_configured': sms_service.is_configured(),
            'ai_marketing_configured': bool(os.environ.get('ANTHROPIC_API_KEY')),
            'app_url_set': bool(os.environ.get('APP_URL')),
            # Resolved public URL used to build email links (not a secret) —
            # lets ops verify reset/verification links without a test send.
            'site_url': app.config.get('SITE_URL'),
            # Deployed git commit (Render sets RENDER_GIT_COMMIT) so a deploy's
            # liveness/version is verifiable without dashboard access.
            'git_commit': (os.environ.get('RENDER_GIT_COMMIT', '') or '')[:7],
        })

    @app.route('/api/health/stripe')
    @limiter.limit('6 per minute')
    def health_stripe():
        """Live Stripe credential check. ``auth_ok`` proves the secret key
        authenticates (free Balance.retrieve); ``connect_ok`` proves Connect
        is enabled on the platform account (Account.list). ``error`` carries
        the Stripe error class + message — these never contain the key, and
        they're exactly what ops needs to fix a misconfigured key. Booleans
        and error text only; rate-limited to deter abuse."""
        import stripe as _stripe
        from app import stripe_service
        out = {'configured': stripe_service.is_configured(),
               'auth_ok': False, 'connect_ok': False, 'error': None}
        if not out['configured']:
            return jsonify(out)
        _stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', '')
        out['mode'] = ('live' if _stripe.api_key.startswith(('sk_live', 'rk_live'))
                       else 'test')
        try:
            _stripe.Balance.retrieve()
            out['auth_ok'] = True
        except Exception as exc:
            out['error'] = f'{type(exc).__name__}: {exc}'[:300]
            return jsonify(out)
        try:
            _stripe.Account.list(limit=1)
            out['connect_ok'] = True
        except Exception as exc:
            out['error'] = f'{type(exc).__name__}: {exc}'[:300]
        return jsonify(out)

    @app.route('/api/health/email')
    @limiter.limit('6 per minute')
    def health_email():
        """Live ZeptoMail credential check — no email is sent. ``auth_ok``
        proves the send token authenticates (an empty payload is posted; a
        valid token gets a validation error back, a bad one gets 401/403).
        Booleans and error text only; rate-limited to deter abuse."""
        from app import email_service
        return jsonify(email_service.auth_check())

    @app.route('/api/health/ai')
    @limiter.limit('6 per minute')
    def health_ai():
        """Live credential check for the AI marketing agent. Performs a free
        Anthropic ``models.list()`` ping (no token cost). Rate-limited to deter
        abuse. ``auth_ok`` is True only if ANTHROPIC_API_KEY actually works."""
        from app.crm import agent_service
        configured = agent_service.is_configured()
        return jsonify({
            'configured': configured,
            'auth_ok': agent_service.auth_ok() if configured else False,
        })

    @app.route('/media/<path:filename>')
    def media_file(filename):
        from flask import redirect
        local_dir = app.config['UPLOAD_FOLDER']
        local_path = os.path.join(local_dir, filename)
        if os.path.isfile(local_path):
            return send_from_directory(local_dir, filename)
        from app import cloudinary_service
        if cloudinary_service.is_configured():
            url = cloudinary_service.delivery_url(filename)
            if url:
                return redirect(url, code=301)
        return jsonify({'error': 'Not found'}), 404

    # Schema management:
    #   Production (DATABASE_URL set) — schema is owned by Alembic migrations
    #     (flask db upgrade, run from build.sh via db_upgrade.py). create_all is
    #     skipped so a missing migration can't be silently masked by auto-create.
    #   Dev / tests (no DATABASE_URL) — create_all builds the SQLite schema so
    #     local work needs no migration step.
    #   YH_NO_CREATE_ALL=1 — internal escape hatch used only when autogenerating
    #     a migration against an empty database.
    skip_create_all = bool(os.environ.get('DATABASE_URL')) or os.environ.get('YH_NO_CREATE_ALL') == '1'
    with app.app_context():
        if not skip_create_all:
            db.create_all()
        try:
            from app.api.planting_api import init_planting_guide
            init_planting_guide()
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                'init_planting_guide skipped (tables may not exist yet)')

    # Register CLI commands (garden trial lifecycle, etc.)
    from app.cli import register_cli
    register_cli(app)

    return app
