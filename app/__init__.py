from flask import Flask, jsonify, request as flask_request, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFProtect
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config import Config
import os

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address, default_limits=[], storage_uri="memory://")


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Email: Zoho ZeptoMail (sole provider, API-based). The only mail config
    # that survives here is the default From address; the ZeptoMail token is
    # read from env in email_service.
    app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@yardharvest.com')

    db.init_app(app)
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
            return  # Same-origin requests may omit Origin header
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
        script_src = (
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net"
            if is_crm
            else "script-src 'self' https://cdn.jsdelivr.net https://js.stripe.com"
        )
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            f"{script_src}; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net; "
            "img-src 'self' data: blob: https://*.tile.openstreetmap.org https://res.cloudinary.com; "
            "connect-src 'self' https://api.stripe.com; "
            "frame-src https://js.stripe.com; "
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
        if current_user.is_authenticated:
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
    def health_config():
        """Unauthenticated config-presence health check. Booleans only — never
        exposes secret values. Lets ops verify which integrations the running
        container actually sees (env wiring), without dashboard access."""
        from app import cloudinary_service
        # Full non-secret cloudinary diagnosis (presence booleans + parsed cloud
        # + exact error). Never exposes api_key/api_secret values.
        cl = cloudinary_service.diagnose()
        return jsonify({
            'cloudinary_configured': cloudinary_service.is_configured(),
            'cloudinary_cloud': cl['cloud'],
            'cloudinary_url_ok': cl['url_ok'],
            'cloudinary_has_key': cl['has_key'],
            'cloudinary_has_secret': cl['has_secret'],
            'cloudinary_pkg_ok': cl['pkg_ok'],
            'cloudinary_error': cl['error'],
            'stripe_configured': bool(os.environ.get('STRIPE_SECRET_KEY')),
            'stripe_webhook_configured': bool(os.environ.get('STRIPE_WEBHOOK_SECRET')),
            'zeptomail_configured': bool(os.environ.get('ZEPTOMAIL_TOKEN')
                                         or app.config.get('ZEPTOMAIL_TOKEN')),
            'app_url_set': bool(os.environ.get('APP_URL')),
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

    with app.app_context():
        db.create_all()
        from app.api.planting_api import init_planting_guide
        init_planting_guide()

    # Register CLI commands (garden trial lifecycle, etc.)
    from app.cli import register_cli
    register_cli(app)

    return app
