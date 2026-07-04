from flask import Flask, jsonify, request as flask_request, send_from_directory, Response
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
    from app.api.booking_api import booking_api

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
    csrf.exempt(booking_api)

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
    app.register_blueprint(booking_api)

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

    def _crm_error_page(code, heading, message):
        """Minimal, dependency-free error page for server-rendered /crm pages.
        The CRM is NOT the React SPA — handing its errors to the SPA renders the
        marketplace 'Page Not Found' on a CRM URL, which is misleading and hides
        real 500s. Plain HTML so it can't fail while we're already handling an
        error; styled to match the CRM ink/lime skin with a link back in."""
        html = (
            '<!doctype html><html><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{code} — YardHarvest CRM</title>'
            '<style>body{margin:0;font-family:Onest,Inter,system-ui,sans-serif;'
            'background:#f2f3f3;color:#22242a;display:flex;min-height:100vh;'
            'align-items:center;justify-content:center}.c{max-width:520px;'
            'padding:40px;text-align:center}h1{font-size:3rem;margin:0 0 .25rem}'
            'p{color:#6b6e76;margin:0 0 1.5rem}a{display:inline-block;'
            'background:#22242a;color:#e3ff8f;text-decoration:none;font-weight:600;'
            'padding:12px 22px;border-radius:10px}</style></head><body><div class="c">'
            f'<h1>{code}</h1><p>{message}</p>'
            '<a href="/crm/dashboard">Back to CRM dashboard</a>'
            '</div></body></html>'
        )
        return html, code

    @app.errorhandler(403)
    def forbidden(e):
        if flask_request.path.startswith('/api/'):
            return jsonify({'error': 'Access denied'}), 403
        if flask_request.path.startswith('/crm'):
            return _crm_error_page(403, 'Forbidden',
                                   "You don't have access to that CRM page.")
        if is_spa_mode:
            return send_from_directory(spa_dir, 'index.html')
        return app.jinja_env.get_template('errors/404.html').render(), 403

    @app.errorhandler(500)
    def server_error(e):
        if flask_request.path.startswith('/api/'):
            return jsonify({'error': 'Internal server error'}), 500
        if flask_request.path.startswith('/crm'):
            return _crm_error_page(
                500, 'Something went wrong',
                'The CRM hit an unexpected error. The team has been notified.')
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
    # Use 404 handler approach so API blueprint routes are never overridden.
    # index.html is served through app.seo.serve_spa_index, which injects
    # per-route title/description/canonical/OG/JSON-LD so no-JS crawlers
    # (GPTBot/ClaudeBot/Perplexity, social scrapers) see real page identity.
    if is_spa_mode:
        from app import seo as _seo

        @app.route('/')
        def serve_spa_root():
            return _seo.serve_spa_index(spa_dir, '/')

        @app.errorhandler(404)
        def spa_not_found(e):
            # API routes get JSON errors
            if flask_request.path.startswith('/api/'):
                return jsonify({'error': 'Not found'}), 404
            # CRM is server-rendered — never hand its 404s to the marketplace SPA
            if flask_request.path.startswith('/crm'):
                return _crm_error_page(404, 'Page not found',
                                       "That CRM page doesn't exist.")
            # Check if it's a real file in dist (JS, CSS, images)
            path = flask_request.path.lstrip('/')
            full_path = os.path.join(spa_dir, path)
            if path and os.path.isfile(full_path):
                resp = send_from_directory(spa_dir, path)
                # Vite content-hashes everything under assets/ — safe to cache
                # forever; a deploy changes the filename, not the content.
                if path.startswith('assets/'):
                    resp.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
                return resp
            # Everything else: serve index.html for React Router
            return _seo.serve_spa_index(spa_dir, flask_request.path)
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
    # --- SEO: robots.txt + dynamic sitemap.xml --------------------------------
    # Served as explicit routes (not via the SPA catch-all) so crawlers always
    # get them. The sitemap enumerates static public pages plus every active
    # garden (and active listings when the marketplace is on) so search engines
    # can discover the individual content pages a client-rendered SPA hides.
    def _site_base():
        return (app.config.get('SITE_URL') or 'https://www.yardharvest.app').rstrip('/')

    @app.route('/robots.txt')
    def robots_txt():
        base = _site_base()
        body = (
            "User-agent: *\n"
            "Allow: /\n"
            "Disallow: /admin\n"
            "Disallow: /dashboard\n"
            "Disallow: /cart\n"
            "Disallow: /checkout\n"
            "Disallow: /orders\n"
            "Disallow: /messages\n"
            "Disallow: /profile/edit\n"
            "Disallow: /login\n"
            "Disallow: /register\n"
            "Disallow: /book/manage/\n"
            f"\nSitemap: {base}/sitemap.xml\n"
        )
        return Response(body, mimetype='text/plain')

    @app.route('/llms.txt')
    def llms_txt():
        """llms.txt — a plain-language site guide for AI/answer engines (GEO).
        The SPA's client-rendered pages are invisible to non-JS crawlers, so
        this is the authoritative summary they CAN read."""
        base = _site_base()
        body = f"""# YardHarvest

> YardHarvest is an all-in-one management platform for community gardens in
> the United States: plot and waitlist management, member dues billing (online
> payments via Stripe), events and volunteer scheduling, member messaging, and
> harvest/impact reporting for boards, funders, and city councils.
> Tagline: "Less admin, more garden."

## Who it's for

- Volunteer-run community gardens that manage plots, dues, waitlists, and
  volunteers (usually on spreadsheets today)
- Urban-agriculture nonprofits running several gardens that need funder-ready
  impact reporting
- Municipal / city parks community-garden programs

## Pricing

Garden Pro is $15/month or $125/year per garden with a 14-day free trial —
see {base}/pricing. Multi-garden networks and city programs get volume
pricing with centralized billing (email james@yardharvest.app).

## Key pages

- Product overview: {base}/
- Pricing and FAQ: {base}/pricing
- About: {base}/about
- The Community Garden Guide (free, practical guide to starting and running a
  community garden — 8 chapters from finding land to harvest reporting):
  {base}/about/guide
- Browse community gardens: {base}/gardens
- Planting calendar (free tool): {base}/planting-calendar
- Book a 30-minute intro call: {base}/book

## Contact

James Goodman — james@yardharvest.app — or book directly at {base}/book.
"""
        return Response(body, mimetype='text/plain')

    @app.route('/sitemap.xml')
    def sitemap_xml():
        from xml.sax.saxutils import escape as _xesc
        from app.models import CommunityGarden, Listing, SiteEmailConfig
        base = _site_base()
        cfg = SiteEmailConfig.query.first()
        mkt = bool(getattr(cfg, 'marketplace_enabled', False)) if cfg else False

        entries = []  # (loc, lastmod|None, changefreq, priority)
        static = [('/', 'daily', '1.0'), ('/about', 'monthly', '0.6'),
                  ('/pricing', 'monthly', '0.8'), ('/gardens', 'daily', '0.9'),
                  ('/book', 'weekly', '0.8'),
                  ('/about/guide', 'monthly', '0.8'),
                  ('/planting-calendar', 'weekly', '0.7'),
                  ('/harvest-forecast', 'weekly', '0.6'), ('/groups', 'weekly', '0.5')]
        from app.seo import GUIDE_META
        static += [(f'/about/guide/{slug}', 'monthly', '0.7') for slug in GUIDE_META]
        if mkt:
            static += [('/browse', 'daily', '0.9'), ('/search', 'weekly', '0.6')]
        for path, freq, prio in static:
            entries.append((base + path, None, freq, prio))

        try:
            for g in CommunityGarden.query.filter_by(is_active=True).all():
                lm = getattr(g, 'updated_at', None) or getattr(g, 'created_at', None)
                entries.append((f'{base}/gardens/{g.id}', lm, 'weekly', '0.8'))
            if mkt:
                for lst in Listing.query.filter_by(is_active=True).all():
                    lm = getattr(lst, 'updated_at', None) or getattr(lst, 'created_at', None)
                    entries.append((f'{base}/listings/{lst.id}', lm, 'weekly', '0.7'))
        except Exception:  # never let a sitemap query 500 the route
            app.logger.exception('sitemap query failed')

        parts = ['<?xml version="1.0" encoding="UTF-8"?>',
                 '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        for loc, lm, freq, prio in entries:
            parts.append('  <url>')
            parts.append(f'    <loc>{_xesc(loc)}</loc>')
            if lm is not None:
                try:
                    parts.append(f'    <lastmod>{lm.date().isoformat()}</lastmod>')
                except Exception:
                    pass
            parts.append(f'    <changefreq>{freq}</changefreq>')
            parts.append(f'    <priority>{prio}</priority>')
            parts.append('  </url>')
        parts.append('</urlset>')
        return Response('\n'.join(parts), mimetype='application/xml')

    # --- Email unsubscribe (List-Unsubscribe target) -------------------------
    # Bulk emails carry a List-Unsubscribe header pointing here. GET shows a
    # confirm form (we never unsubscribe on GET, so link scanners/prefetch can't
    # opt people out); POST adds the address to the global suppression list.
    def _unsubscribe_page(base, email='', done=False, error=None):
        from markupsafe import escape
        e = escape(email)
        if done:
            inner = (
                '<h1>You’re unsubscribed</h1>'
                f'<p>{e} will no longer receive garden announcements or campaign '
                'emails from YardHarvest. Account and transactional messages '
                '(receipts, password resets) may still be sent.</p>'
                f'<a class="btn" href="{base}/">Back to YardHarvest</a>')
        else:
            err = f'<p style="color:#b42318">{escape(error)}</p>' if error else ''
            inner = (
                '<h1>Unsubscribe</h1>'
                '<p>Enter your email to stop receiving garden announcements and '
                'campaign emails. Transactional emails (receipts, password resets) '
                f'are not affected.</p>{err}'
                '<form method="post" style="display:flex;gap:8px;flex-wrap:wrap;justify-content:center">'
                f'<input type="email" name="email" required placeholder="you@example.com" value="{e}" '
                'style="padding:11px 14px;border:1px solid #c9ccd1;border-radius:10px;min-width:240px">'
                '<button type="submit" style="padding:11px 20px;border:0;border-radius:10px;'
                'background:#22242a;color:#e3ff8f;font-weight:600;cursor:pointer">Unsubscribe</button>'
                '</form>')
        html = (
            '<!doctype html><html><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Unsubscribe — YardHarvest</title><style>'
            'body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;'
            'font-family:Onest,Inter,system-ui,sans-serif;background:#f2f3f3;color:#22242a}'
            '.c{max-width:520px;padding:40px;text-align:center}h1{margin:0 0 .5rem}'
            'p{color:#6b6e76}a.btn{display:inline-block;margin-top:1rem;background:#22242a;color:#e3ff8f;'
            'text-decoration:none;font-weight:600;padding:12px 22px;border-radius:10px}'
            '</style></head><body><div class="c">' + inner + '</div></body></html>')
        return Response(html, mimetype='text/html')

    @app.route('/unsubscribe', methods=['GET', 'POST'])
    @limiter.limit('20 per hour')
    def unsubscribe():
        from app.models import EmailUnsubscribe
        base = _site_base()
        if flask_request.method == 'POST':
            email = (flask_request.form.get('email') or '').strip().lower()
            if not email or '@' not in email:
                return _unsubscribe_page(base, email=email,
                                         error='Please enter a valid email address.'), 400
            try:
                if not EmailUnsubscribe.query.filter_by(email=email).first():
                    db.session.add(EmailUnsubscribe(email=email, source='self_service'))
                # Reflect in CRM contacts so the CRM UI stays consistent.
                from app.crm.models import Contact
                for c in Contact.query.filter(Contact.email.ilike(email)).all():
                    c.email_opt_out = True
                db.session.commit()
            except Exception:
                db.session.rollback()
                app.logger.exception('unsubscribe failed')
            return _unsubscribe_page(base, email=email, done=True)
        return _unsubscribe_page(base, email=(flask_request.args.get('email') or '').strip())

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
            'zoho_calendar_configured': bool(os.environ.get('ZOHO_REFRESH_TOKEN')
                                             and os.environ.get('ZOHO_CLIENT_ID')),
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

    @app.route('/api/health/sms')
    @limiter.limit('6 per minute')
    def health_sms():
        """Live Twilio credential check for SMS — no message is sent.
        ``configured`` = the twilio package + all 3 creds are present;
        ``auth_ok`` = those creds authenticate (a free account fetch). ``toggles``
        shows which SMS notification types are switched on — a send also needs
        its type enabled (SiteEmailConfig). Rate-limited; booleans only."""
        from app import sms_service
        configured = sms_service.is_configured()
        out = {
            'configured': configured,
            'available': sms_service.TWILIO_AVAILABLE,
            'from_number_set': bool(os.environ.get('TWILIO_PHONE_NUMBER')),
            'auth_ok': sms_service.auth_ok() if configured else False,
        }
        try:
            from app.models import SiteEmailConfig
            cfg = SiteEmailConfig.query.first()
            out['toggles'] = {
                'order_confirmation': bool(getattr(cfg, 'enable_sms_order_confirmation', False)),
                'status_updates': bool(getattr(cfg, 'enable_sms_status_updates', False)),
                'messages': bool(getattr(cfg, 'enable_sms_messages', False)),
                'harvest_notifications': bool(getattr(cfg, 'enable_sms_harvest_notifications', False)),
            } if cfg else {}
        except Exception:
            out['toggles'] = {}
        return jsonify(out)

    @app.route('/api/health/zoho-calendar')
    @limiter.limit('6 per minute')
    def health_zoho_calendar():
        """Live Zoho Calendar credential check for the booking page — nothing is
        written. ``configured`` = the 3 OAuth creds are present; ``auth_ok`` =
        the refresh token exchanges + lists calendars; ``calendar_uid_set`` =
        a target calendar UID is configured (required to write events).
        Booleans + error text only; rate-limited."""
        from app import zoho_calendar_service
        return jsonify(zoho_calendar_service.auth_check())

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
