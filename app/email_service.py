"""Email notification service for YardHarvest.

Provides helper functions for sending branded HTML email notifications
for orders, messages, garden announcements, waitlist updates, and
subscription boxes.  All functions are wrapped in try/except so that
email failures never crash the calling API endpoint.

Email is sent exclusively through **Zoho ZeptoMail** — Zoho's pay-as-you-go
transactional email API. Auth is a send-only token (``ZEPTOMAIL_TOKEN``); there
is no mailbox login, no SMTP, and no monthly-subscription provider.

Backend selection (see ``send_email``):
  1. Zoho ZeptoMail API — used when ``ZEPTOMAIL_TOKEN`` is set.
  2. Dev log-only — when the token is unset, message details are logged to
     console so local development is unblocked.

Branding (logo, colors, tagline, footer) and per-email-type on/off
toggles are loaded from the SiteEmailConfig singleton.  Garden-specific
announcement overrides come from GardenEmailConfig.
"""
import html
import logging
from flask import current_app, render_template_string

log = logging.getLogger(__name__)


def _esc(value):
    """HTML-escape a user-provided value for safe interpolation into an
    f-string email body. Use for any field an organizer or member controls
    (announcement title/body, closing text, captions, names)."""
    return html.escape(str(value or ''))

# ---------------------------------------------------------------------------
# Dynamic base template (uses Jinja2 variables from config)
# ---------------------------------------------------------------------------

BASE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    /* YardHarvest lime / Onest email skin. Onest falls back to system fonts in
       clients that can't load it; the lime CTA + ink headings carry the brand. */
    body { margin: 0; padding: 0; font-family: 'Onest', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f2f3f3; color: #22242a; }
    .email-wrapper { max-width: 600px; margin: 24px auto; background: #ffffff; border: 1px solid #e5e6e6; border-radius: 14px; overflow: hidden; }
    .email-header { background-color: {{ header_color }}; padding: 28px 32px; text-align: center; border-bottom: 3px solid #e3ff8f; }
    .email-header h1 { color: #ffffff; margin: 0; font-size: 24px; font-weight: 700; letter-spacing: -0.02em; }
    .email-header p { color: rgba(255,255,255,0.72); margin: 6px 0 0; font-size: 13px; }
    .email-header img { max-height: 44px; margin-bottom: 10px; }
    .email-body { padding: 32px; line-height: 1.6; font-size: 15px; color: #22242a; }
    .email-body h2 { color: #22242a; margin-top: 0; font-weight: 600; letter-spacing: -0.02em; }
    .email-body p { margin: 12px 0; }
    .email-body img { max-width: 100%; height: auto; border-radius: 8px; margin: 8px 0; }
    .email-body a { color: #3b6d11; }
    .email-body ul, .email-body ol { margin: 12px 0; padding-left: 22px; }
    .btn { display: inline-block; background-color: #e3ff8f; color: #22242a !important; text-decoration: none; padding: 13px 28px; border-radius: 10px; font-weight: 700; margin: 18px 0; }
    .btn:hover { filter: brightness(0.97); }
    .detail-table { width: 100%; border-collapse: collapse; margin: 16px 0; }
    .detail-table td { padding: 10px 12px; border-bottom: 1px solid #eceeec; }
    .detail-table td:first-child { font-weight: 600; color: #6b6e76; width: 40%; }
    .email-footer { background-color: #f2f3f3; padding: 22px 32px; text-align: center; font-size: 12px; color: #6b6e76; }
    .email-footer a { color: #3b6d11; text-decoration: none; font-weight: 600; }
    .priority-urgent { color: #c62828; font-weight: 700; }
    .priority-important { color: #e65100; font-weight: 600; }
  </style>
</head>
<body>
  <div class="email-wrapper">
    <div class="email-header">
      {% if logo_url %}<img src="{{ logo_url }}" alt="{{ from_name }}">{% endif %}
      <h1>{{ from_name }}</h1>
      {% if tagline %}<p>{{ tagline }}</p>{% endif %}
    </div>
    <div class="email-body">
      {# content is HTML assembled by this service; user-supplied substrings
         within it are escaped at interpolation via _esc(). Marked safe so the
         scaffold HTML renders instead of being shown as literal tags. #}
      {{ content | safe }}
    </div>
    <div class="email-footer">
      <p>
        <a href="{{ site_url }}">Visit {{ from_name }}</a>
      </p>
      {% if footer_text %}
      <p>{{ footer_text }}</p>
      {% else %}
      <p>You received this email because you have an account on {{ from_name }}.<br>
         If you believe this was sent in error, please contact
         <a href="mailto:James@yardharvest.app">James@yardharvest.app</a>.</p>
      {% endif %}
    </div>
  </div>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Site URL helper (default for development)
# ---------------------------------------------------------------------------

SITE_URL = 'http://localhost:5173'


def _get_site_url():
    """Return the frontend site URL from config or fallback."""
    return current_app.config.get('SITE_URL', SITE_URL)


# ---------------------------------------------------------------------------
# Config helpers — cached per-request
# ---------------------------------------------------------------------------

def _get_site_email_config():
    """Load the SiteEmailConfig singleton, creating defaults if missing."""
    from app.models import SiteEmailConfig
    from app import db
    config = SiteEmailConfig.query.first()
    if not config:
        config = SiteEmailConfig()
        db.session.add(config)
        db.session.commit()
    return config


def _get_garden_email_config(garden_id):
    """Load the GardenEmailConfig for a specific garden, or None."""
    from app.models import GardenEmailConfig
    return GardenEmailConfig.query.filter_by(garden_id=garden_id).first()


# ---------------------------------------------------------------------------
# Generic email sender
# ---------------------------------------------------------------------------

def send_email(to, subject, html_body, from_name=None, from_email=None):
    """Send a transactional email via Zoho ZeptoMail.

    Backend selection priority:
      1. Zoho ZeptoMail API — if ZEPTOMAIL_TOKEN is set
      2. Dev mode — logs to console if not configured

    ZeptoMail is the platform's sole email provider (pay-as-you-go transactional
    API, send-only token — no mailbox login, no monthly subscription).

    Returns
    -------
    bool
        True if ZeptoMail accepted the message; False if it fell through to
        dev-log mode (token unset) or the send failed.

    Parameters
    ----------
    to : str or list[str]
        Recipient email address(es).
    subject : str
        Email subject line.
    html_body : str
        Fully-rendered HTML body.
    from_name : str, optional
        Override the sender display name (e.g. a garden's own name for
        announcements). Falls back to the configured ZEPTOMAIL_FROM_NAME.
    from_email : str, optional
        Override the sender address (e.g. the CRM's personal address). Falls
        back to ZEPTOMAIL_FROM_EMAIL / MAIL_DEFAULT_SENDER. Must be on a domain
        verified in the ZeptoMail Mail Agent.
    """
    recipients = to if isinstance(to, list) else [to]

    # --- Backend 1: Zoho ZeptoMail (transactional API, send-only token) ---
    if _send_via_zeptomail(recipients, subject, html_body,
                           from_name=from_name, from_email=from_email):
        return True

    # Distinguish a real failure from dev/unconfigured: if ZeptoMail IS
    # configured, a False here means the send genuinely failed — log at ERROR
    # (so Sentry/ops see it) rather than the misleading dev-mode INFO line that
    # made prod failures look like normal dev behavior.
    if is_configured():
        log.error('Email send FAILED (ZeptoMail configured) — to=%s subject=%s',
                  ', '.join(recipients), subject)
        return False

    # --- Backend 2: Development mode (unconfigured) — just log ---
    log.info(
        '[EMAIL DEV] To: %s | Subject: %s | (HTML body omitted)',
        ', '.join(recipients), subject,
    )
    return False


def _zepto_auth_header(token):
    """Build the ZeptoMail Authorization header value.

    Tolerates common paste artifacts in the configured token: surrounding
    quotes, newlines, an "Authorization:" label, and the Zoho-enczapikey
    scheme prefix being present or absent.
    """
    token = (token or '').strip().strip('"').strip("'").strip()
    token = ' '.join(token.split())  # collapse internal newlines/spaces
    if token.lower().startswith('authorization:'):
        token = token.split(':', 1)[1].strip()
    if token.lower().startswith('zoho-enczapikey'):
        return token
    return f'Zoho-enczapikey {token}'


def _zepto_api_url(configured):
    """Normalize ZEPTOMAIL_API_URL to the full single-send endpoint.

    Accepts a bare host ("api.zeptomail.com"), a base URL, or the full
    endpoint and always returns https://<host>/v1.1/email. A wrong path
    returns ZeptoMail's HTML 404 page instead of an API error, which is
    confusing to debug.
    """
    url = (configured or '').strip().rstrip('/')
    if not url:
        return 'https://api.zeptomail.com/v1.1/email'
    if not url.startswith('http'):
        url = f'https://{url}'
    if url.endswith('/v1.1/email'):
        return url
    if url.endswith('/v1.1'):
        return f'{url}/email'
    return f'{url}/v1.1/email'


def _log_zepto_failure(resp, context):
    """Log a send failure with an actionable hint (never the response body)."""
    body = (resp.text or '').strip()
    if body.lower().startswith(('<!doctype', '<html')):
        log.error('[ZEPTOMAIL ERROR] %s: HTTP %d returned an HTML page, not '
                  'an API response — check ZEPTOMAIL_API_URL', context,
                  resp.status_code)
    elif resp.status_code == 401:
        log.error('[ZEPTOMAIL ERROR] %s: HTTP 401 — ZEPTOMAIL_TOKEN is not a '
                  'valid Send Mail Token (copy it from ZeptoMail > Mail '
                  'Agents > Setup Info > API tab)', context)
    else:
        log.error('[ZEPTOMAIL ERROR] %s: HTTP %d', context, resp.status_code)


def is_configured():
    """True when a ZeptoMail send token is present (env or app config)."""
    import os
    return bool(os.environ.get('ZEPTOMAIL_TOKEN', '')
                or current_app.config.get('ZEPTOMAIL_TOKEN', ''))


def auth_check():
    """Live ZeptoMail credential probe — no email is sent.

    Posts an intentionally empty payload: a valid token gets a 4xx
    validation error (auth passed), an invalid token gets 401/403.
    Returns a dict suitable for the /api/health/email endpoint.
    """
    import os
    out = {'configured': is_configured(), 'auth_ok': False, 'error': None}
    if not out['configured']:
        return out
    token = (os.environ.get('ZEPTOMAIL_TOKEN', '')
             or current_app.config.get('ZEPTOMAIL_TOKEN', ''))
    api_url = _zepto_api_url(os.environ.get('ZEPTOMAIL_API_URL', '')
                             or current_app.config.get('ZEPTOMAIL_API_URL', ''))
    try:
        import requests
        resp = requests.post(
            api_url,
            headers={
                'Authorization': _zepto_auth_header(token),
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
            json={},
            timeout=10,
        )
        body = (resp.text or '').strip()
        if body.lower().startswith(('<!doctype', '<html')):
            out['error'] = (f'HTTP {resp.status_code} returned an HTML page — '
                            'check ZEPTOMAIL_API_URL')
        elif resp.status_code in (401, 403):
            out['error'] = (f'HTTP {resp.status_code} — ZEPTOMAIL_TOKEN is not a '
                            'valid Send Mail Token')
        else:
            # Any API-shaped response that is not an auth error means the
            # token authenticated (the empty payload itself is rejected 4xx).
            out['auth_ok'] = True
    except Exception as exc:
        out['error'] = f'{type(exc).__name__}: {exc}'[:300]
    return out


def _send_via_zeptomail(recipients, subject, html_body, from_name=None, from_email=None):
    """Send through Zoho ZeptoMail's transactional API. Returns True on success.

    No-op (returns False) when ZEPTOMAIL_TOKEN is unset, so callers fall
    through to the next backend. Auth is a send-only "Send Mail token"
    (``Authorization: Zoho-enczapikey <token>``) — never a mailbox password.
    """
    import os
    token = os.environ.get('ZEPTOMAIL_TOKEN', '') or current_app.config.get('ZEPTOMAIL_TOKEN', '')
    if not token:
        return False

    api_url = _zepto_api_url(os.environ.get('ZEPTOMAIL_API_URL', '')
                             or current_app.config.get('ZEPTOMAIL_API_URL', ''))
    from_email = (from_email
                  or os.environ.get('ZEPTOMAIL_FROM_EMAIL', '')
                  or current_app.config.get('ZEPTOMAIL_FROM_EMAIL', '')
                  or current_app.config.get('MAIL_DEFAULT_SENDER', 'no_reply@yardharvest.app'))
    from_name = (from_name
                 or os.environ.get('ZEPTOMAIL_FROM_NAME', '')
                 or current_app.config.get('ZEPTOMAIL_FROM_NAME', '')
                 or 'YardHarvest')

    payload = {
        'from': {'address': from_email, 'name': from_name},
        'to': [{'email_address': {'address': r}} for r in recipients],
        'subject': subject,
        'htmlbody': html_body,
    }
    try:
        import requests
        resp = requests.post(
            api_url,
            headers={
                'Authorization': _zepto_auth_header(token),
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
            json=payload,
            timeout=20,
        )
        if resp.status_code in (200, 201):
            log.info('[ZEPTOMAIL] Sent "%s" to %s (status %d)',
                     subject, ', '.join(recipients), resp.status_code)
            return True
        # Do not log the response body — it can echo recipient data.
        _log_zepto_failure(resp, f'send "{subject}"')
        return False
    except Exception:
        log.exception('[ZEPTOMAIL ERROR] Failed "%s" to %s', subject, ', '.join(recipients))
        return False


def send_batch_via_zeptomail(recipients, subject, html_body, *,
                             default_merge_info=None, from_email=None,
                             from_name=None):
    """Send ONE ZeptoMail batch request to many recipients in a single call.

    ZeptoMail's batch endpoint accepts per-recipient ``merge_info`` and
    ``{{token}}`` placeholders in the subject/htmlbody, which map cleanly onto
    the CRM's ``merge_context()`` dict and ``{{token}}`` templates (the CRM and
    ZeptoMail use the *same* double-curly-brace delimiter, so no translation is
    needed). The raw (un-rendered) subject/body are sent once; ZeptoMail does
    the per-recipient substitution server-side.

    Confirmed contract (Zoho ZeptoMail docs,
    https://www.zoho.com/zeptomail/help/api/batch-email-sending.html):
      * Endpoint: ``<host>/v1.1/email/batch`` (derived from ZEPTOMAIL_API_URL
        by swapping the trailing ``/email`` for ``/email/batch``).
      * Auth header: ``Authorization: Zoho-enczapikey <token>``.
      * Payload: ``from`` {address,name}; ``to`` is a list of
        ``{"email_address": {"address": ...}, "merge_info": {...}}``; plus
        ``subject`` and ``htmlbody`` containing ``{{token}}`` placeholders.
      * Merge placeholders are delimited with double curly braces ``{{key}}``.
      * Max 500 recipients per batch request.

    Parameters
    ----------
    recipients : list[dict]
        Each item: ``{'email': <addr>, 'merge_info': {<token>: <value>}}``.
        ``merge_info`` is optional per recipient; when absent, the top-level
        *default_merge_info* (if any) is used by ZeptoMail.
    subject, html_body : str
        Raw template strings containing ``{{token}}`` placeholders.
    default_merge_info : dict, optional
        Top-level merge_info applied to recipients lacking their own.

    Returns
    -------
    dict
        ``{'ok': bool, 'configured': bool, 'count': int, 'status': int|None}``.
        * ``configured`` is False (and ``ok`` False) when ZEPTOMAIL_TOKEN is
          unset, signalling the caller to fall back to per-contact sends.
        * ``ok`` is True only when ZeptoMail accepted the batch (HTTP 200/201).
        * ``count`` is the number of recipients in the batch.

    Never logs message bodies or recipient PII beyond aggregate counts.
    """
    import os
    token = os.environ.get('ZEPTOMAIL_TOKEN', '') or current_app.config.get('ZEPTOMAIL_TOKEN', '')
    if not token:
        return {'ok': False, 'configured': False, 'count': 0, 'status': None}

    clean = [r for r in (recipients or []) if r and r.get('email')]
    if not clean:
        return {'ok': False, 'configured': True, 'count': 0, 'status': None}

    # Derive the batch endpoint from the (normalized) single-send URL — honors
    # regional hosts, e.g. https://api.zeptomail.eu/v1.1/email -> .../batch.
    api_url = _zepto_api_url(os.environ.get('ZEPTOMAIL_API_URL', '')
                             or current_app.config.get('ZEPTOMAIL_API_URL', '')
                             ) + '/batch'

    from_email = (from_email
                  or os.environ.get('ZEPTOMAIL_FROM_EMAIL', '')
                  or current_app.config.get('ZEPTOMAIL_FROM_EMAIL', '')
                  or current_app.config.get('MAIL_DEFAULT_SENDER', 'no_reply@yardharvest.app'))
    from_name = (from_name
                 or os.environ.get('ZEPTOMAIL_FROM_NAME', '')
                 or current_app.config.get('ZEPTOMAIL_FROM_NAME', '')
                 or 'YardHarvest')

    to_list = []
    for r in clean:
        entry = {'email_address': {'address': r['email']}}
        mi = r.get('merge_info')
        if mi:
            entry['merge_info'] = mi
        to_list.append(entry)

    payload = {
        'from': {'address': from_email, 'name': from_name},
        'to': to_list,
        'subject': subject,
        'htmlbody': html_body,
    }
    if default_merge_info:
        payload['merge_info'] = default_merge_info

    count = len(to_list)
    try:
        import requests
        resp = requests.post(
            api_url,
            headers={
                'Authorization': _zepto_auth_header(token),
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
            json=payload,
            timeout=30,
        )
        if resp.status_code in (200, 201):
            log.info('[ZEPTOMAIL BATCH] Sent "%s" to %d recipient(s) (status %d)',
                     subject, count, resp.status_code)
            return {'ok': True, 'configured': True, 'count': count,
                    'status': resp.status_code}
        # Do not log the response body — it can echo recipient data.
        _log_zepto_failure(resp, f'batch "{subject}" ({count} recipients)')
        return {'ok': False, 'configured': True, 'count': count,
                'status': resp.status_code}
    except Exception:
        log.exception('[ZEPTOMAIL BATCH ERROR] Failed "%s" for %d recipient(s)',
                      subject, count)
        return {'ok': False, 'configured': True, 'count': count, 'status': None}


def _render(content_html, config=None):
    """Wrap *content_html* inside the branded base template.

    Uses SiteEmailConfig for branding if *config* is not provided.
    """
    if config is None:
        try:
            config = _get_site_email_config()
        except Exception:
            config = None

    return render_template_string(
        BASE_TEMPLATE,
        content=content_html,
        site_url=_get_site_url(),
        header_color=getattr(config, 'header_color', '#22242a') or '#22242a',
        logo_url=getattr(config, 'logo_url', '') or '',
        tagline=getattr(config, 'tagline', 'Less admin, more garden') or '',
        from_name=getattr(config, 'from_name', 'YardHarvest') or 'YardHarvest',
        footer_text=getattr(config, 'footer_text', '') or '',
    )


# Email-safe HTML allowlist for CRM sales emails (Quill output + templates).
_EMAIL_ALLOWED_TAGS = [
    'p', 'br', 'span', 'div', 'h1', 'h2', 'h3', 'h4', 'strong', 'b', 'em', 'i',
    'u', 's', 'a', 'ul', 'ol', 'li', 'blockquote', 'img', 'hr', 'pre', 'code',
    'table', 'thead', 'tbody', 'tr', 'td', 'th',
]
# No 'style' attr: without a CSS sanitizer bleach strips it anyway, so we omit
# it (clean, no inline-CSS surface) and make images responsive via the shell's
# .email-body img rule instead.
_EMAIL_ALLOWED_ATTRS = {
    '*': ['class', 'align'],
    'a': ['href', 'title', 'target', 'rel'],
    'img': ['src', 'alt', 'width', 'height'],
}
_EMAIL_ALLOWED_PROTOCOLS = ['http', 'https', 'mailto', 'tel']


def sanitize_email_html(html):
    """Strip anything unsafe from a user/AI-authored HTML email body.

    Allows a small set of email-safe tags/attrs (incl. <img>), drops <script>,
    event handlers, javascript: URLs, etc. Use on any body that may contain
    HTML (rich composer, templates, AI drafts, imported merge values)."""
    import bleach
    return bleach.clean(html or '', tags=_EMAIL_ALLOWED_TAGS,
                        attributes=_EMAIL_ALLOWED_ATTRS,
                        protocols=_EMAIL_ALLOWED_PROTOCOLS, strip=True)


def render_sales_email(body, config=None):
    """Render a CRM sales-email body inside the branded lime/Onest shell.

    Accepts HTML (from the rich composer / templates / AI) — sanitized — or
    plain text — escaped with newlines preserved. Returns full HTML to send."""
    body = body or ''
    if '<' in body and '>' in body:          # looks like HTML
        content = sanitize_email_html(body)
    else:                                     # plain text -> paragraphs
        paras = [p.strip() for p in body.split('\n\n')]
        content = ''.join(
            '<p>' + _esc(p).replace('\n', '<br>') + '</p>' for p in paras if p)
    return _render(content, config=config)


def _subject(label, config=None):
    """Build a subject line with the configured prefix."""
    if config is None:
        try:
            config = _get_site_email_config()
        except Exception:
            config = None
    prefix = getattr(config, 'subject_prefix', 'YardHarvest') or 'YardHarvest'
    return f'{prefix} - {label}'


def send_password_reset_email(user, token):
    """Send a branded password reset email with a 1-hour reset link.

    This is a transactional/security email — always sends regardless
    of SiteEmailConfig notification toggles.
    """
    site_url = _get_site_url()
    reset_url = f'{site_url}/reset-password?token={token}'
    display = _esc(user.display_name or user.username)

    content = f'''
    <h2>Password Reset Request</h2>
    <p>Hi {display},</p>
    <p>We received a request to reset the password for your YardHarvest account.
       Click the button below to choose a new password:</p>
    <p style="text-align: center;">
      <a class="btn" href="{reset_url}">Reset Your Password</a>
    </p>
    <p style="font-size: 0.9em; color: #666;">
      This link expires in 1 hour and can only be used once.
      If you didn't request a password reset, you can safely ignore this email.</p>
    '''
    subject = _subject('Password Reset Request')
    send_email(user.email, subject, _render(content))


def preview_email(template_type, config=None, garden_config=None, garden_name=None):
    """Render a sample email for live preview in admin settings.

    When previewing the ``announcement`` template with a ``garden_config``, the
    sample reflects that garden's accent color, closing text, and name — so the
    preview matches what members will actually receive.

    Returns the full HTML string.
    """
    if template_type == 'announcement' and (garden_config or garden_name):
        accent = (garden_config.accent_color if garden_config and garden_config.accent_color
                  else (config.header_color if config else '#22242a'))
        name = _esc(garden_name or 'Sunrise Community Garden')
        closing = ''
        if garden_config and garden_config.closing_text:
            closing = (f'<p style="margin-top:24px;color:#666;font-style:italic;">'
                       f'{_esc(garden_config.closing_text)}</p>')
        content = (f'<h2 style="color:{accent};">New Announcement - {name}</h2>'
                   '<h3>Spring Planting Day This Saturday!</h3>'
                   '<p>Join us for our annual spring planting day. Bring your tools and enthusiasm!</p>'
                   f'{closing}')
        return _render(content, config=config)

    samples = {
        'order_confirmation': '<h2>Order Confirmed!</h2><p>Thanks for your order! Here\'s a summary:</p>'
            '<table class="detail-table"><tr><td>Order #</td><td>12345</td></tr>'
            '<tr><td>Seller</td><td>Green Thumb Sarah</td></tr>'
            '<tr><td>Fulfillment</td><td>Pickup</td></tr>'
            '<tr><td>Total</td><td><strong>$24.50</strong></td></tr></table>',
        'status_update': '<h2>Order #12345 - Accepted</h2>'
            '<p>Green Thumb Sarah has accepted your order and will prepare it for pickup.</p>',
        'message': '<h2>New Message from Green Thumb Sarah</h2>'
            '<p>You have a new message:</p>'
            '<blockquote style="border-left:4px solid #2d6a2e;padding:12px 16px;background:#f9faf9;margin:16px 0;border-radius:4px;">'
            'Hi! Your tomatoes are ready for pickup. Come by anytime after 3 PM today.</blockquote>',
        'announcement': '<h2>New Announcement - Sunrise Community Garden</h2>'
            '<h3>Spring Planting Day This Saturday!</h3>'
            '<p>Join us for our annual spring planting day. Bring your tools and enthusiasm!</p>',
        'harvest_notification': '<h2>🌿 Tomatoes Harvest Alert!</h2>'
            '<p>Great news! <strong>Tomatoes</strong> harvests are coming in from '
            '<strong>3 growers</strong> in your community.</p>'
            '<p>Check the Harvest Forecast to see estimated quantities and timing.</p>'
            '<a href="#" class="btn">View Harvest Forecast</a>',
    }
    content = samples.get(template_type, samples['order_confirmation'])
    return _render(content, config=config)


# ---------------------------------------------------------------------------
# 1. Order Confirmation (sent to buyer)
# ---------------------------------------------------------------------------

def send_order_confirmation(order, buyer_email):
    """Notify the buyer that their order has been placed successfully."""
    config = _get_site_email_config()
    if not config.enable_order_confirmation:
        return

    site = _get_site_url()
    items_html = ''
    for oi in order.items:
        title = _esc(oi.listing.title if oi.listing else 'Item')
        items_html += (
            f'<tr><td>{title}</td>'
            f'<td style="text-align:center">{oi.quantity}</td>'
            f'<td style="text-align:right">${oi.unit_price:.2f}</td></tr>'
        )

    content = f"""
    <h2>Order Confirmed!</h2>
    <p>Thanks for your order! Here's a summary:</p>
    <table class="detail-table">
      <tr><td>Order #</td><td>{order.id}</td></tr>
      <tr><td>Seller</td><td>{_esc(order.seller_user.display_name or order.seller_user.username)}</td></tr>
      <tr><td>Fulfillment</td><td>{order.fulfillment_method.title()}</td></tr>
      <tr><td>Total</td><td><strong>${order.total_price:.2f}</strong></td></tr>
    </table>
    <table style="width:100%;border-collapse:collapse;margin:16px 0;">
      <thead>
        <tr style="border-bottom:2px solid {config.header_color};">
          <th style="text-align:left;padding:8px;">Item</th>
          <th style="text-align:center;padding:8px;">Qty</th>
          <th style="text-align:right;padding:8px;">Price</th>
        </tr>
      </thead>
      <tbody>{items_html}</tbody>
    </table>
    <a href="{site}/orders" class="btn">View Your Orders</a>
    """
    send_email(buyer_email, _subject(f'Order #{order.id} Confirmed', config), _render(content, config))


# ---------------------------------------------------------------------------
# 2. New Order Notification (sent to seller)
# ---------------------------------------------------------------------------

def send_new_order_notification(order, seller_email):
    """Notify the seller that a new order has been placed."""
    config = _get_site_email_config()
    if not config.enable_order_confirmation:
        return

    site = _get_site_url()
    buyer_name = order.buyer.display_name or order.buyer.username
    items_summary = _esc(', '.join(
        f'{oi.quantity}x {oi.listing.title}' for oi in order.items if oi.listing
    ))

    content = f"""
    <h2>New Order Received!</h2>
    <p>You have a new order from <strong>{_esc(buyer_name)}</strong>.</p>
    <table class="detail-table">
      <tr><td>Order #</td><td>{order.id}</td></tr>
      <tr><td>Items</td><td>{items_summary}</td></tr>
      <tr><td>Fulfillment</td><td>{order.fulfillment_method.title()}</td></tr>
      <tr><td>Total</td><td><strong>${order.total_price:.2f}</strong></td></tr>
    </table>
    <a href="{site}/orders/selling" class="btn">View Seller Dashboard</a>
    """
    send_email(seller_email, _subject(f'New Order #{order.id} from {buyer_name}', config), _render(content, config))


# ---------------------------------------------------------------------------
# 3. Order Status Update (sent to buyer)
# ---------------------------------------------------------------------------

def send_order_status_update(order, buyer_email, new_status):
    """Notify the buyer that their order status has changed."""
    config = _get_site_email_config()
    if not config.enable_status_updates:
        return

    site = _get_site_url()
    status_labels = {
        'accepted': 'Accepted',
        'completed': 'Completed',
        'cancelled': 'Cancelled',
    }
    label = status_labels.get(new_status, new_status.title())
    seller_name = _esc(order.seller_user.display_name or order.seller_user.username)
    fulfillment = _esc(order.fulfillment_method)

    status_messages = {
        'accepted': f'{seller_name} has accepted your order and will prepare it for {fulfillment}.',
        'completed': f'Your order with {seller_name} has been marked as completed. Enjoy your fresh produce!',
        'cancelled': f'Your order with {seller_name} has been cancelled.',
    }
    detail = status_messages.get(new_status, f'Your order status has been updated to {label}.')

    content = f"""
    <h2>Order #{order.id} - {label}</h2>
    <p>{detail}</p>
    <table class="detail-table">
      <tr><td>Order #</td><td>{order.id}</td></tr>
      <tr><td>Seller</td><td>{seller_name}</td></tr>
      <tr><td>Status</td><td><strong>{label}</strong></td></tr>
      <tr><td>Total</td><td>${order.total_price:.2f}</td></tr>
    </table>
    <a href="{site}/orders" class="btn">View Order Details</a>
    """
    send_email(buyer_email, _subject(f'Order #{order.id} {label}', config), _render(content, config))


# ---------------------------------------------------------------------------
# 4. New Message Notification
# ---------------------------------------------------------------------------

def send_message_notification(sender_name, recipient_email, preview):
    """Notify a user that they have received a new message."""
    config = _get_site_email_config()
    if not config.enable_messages:
        return

    site = _get_site_url()
    # Truncate preview to a reasonable length (escape — both are user content)
    short_preview = (preview[:120] + '...') if len(preview) > 120 else preview
    safe_sender = _esc(sender_name)
    safe_preview = _esc(short_preview)

    content = f"""
    <h2>New Message from {safe_sender}</h2>
    <p>You have a new message:</p>
    <blockquote style="border-left:4px solid {config.header_color}; padding:12px 16px; background:#f9faf9; margin:16px 0; border-radius:4px;">
      {safe_preview}
    </blockquote>
    <a href="{site}/messages" class="btn">View Messages</a>
    """
    send_email(recipient_email, _subject(f'New message from {sender_name}', config), _render(content, config))


# ---------------------------------------------------------------------------
# 5. Garden Announcement
# ---------------------------------------------------------------------------

def send_garden_announcement(garden_name, announcement_title, announcement_body,
                             priority, member_emails, garden_id=None):
    """Notify garden members of a new announcement.

    Parameters
    ----------
    garden_name : str
    announcement_title : str
    announcement_body : str
    priority : str  -- 'normal', 'important', or 'urgent'
    member_emails : list[str]
    garden_id : int, optional -- for garden-specific email config
    """
    if not member_emails:
        return

    config = _get_site_email_config()
    if not config.enable_announcements:
        return

    # Load garden-specific overrides
    garden_config = _get_garden_email_config(garden_id) if garden_id else None

    site = _get_site_url()
    # All four interpolated values below are organizer-controlled — escape them.
    safe_garden = _esc(garden_name)
    safe_title = _esc(announcement_title)
    safe_body = _esc(announcement_body)
    priority_class = ''
    priority_badge = ''
    accent = (garden_config.accent_color if garden_config and garden_config.accent_color
              else config.header_color)
    if priority == 'urgent':
        priority_class = 'priority-urgent'
        priority_badge = '<span class="priority-urgent">[URGENT]</span> '
    elif priority == 'important':
        priority_class = 'priority-important'
        priority_badge = '<span class="priority-important">[IMPORTANT]</span> '

    closing = ''
    if garden_config and garden_config.closing_text:
        closing = (f'<p style="margin-top:24px;color:#666;font-style:italic;">'
                   f'{_esc(garden_config.closing_text)}</p>')

    content = f"""
    <h2 style="color:{accent};">{priority_badge}New Announcement - {safe_garden}</h2>
    <h3 class="{priority_class}">{safe_title}</h3>
    <p>{safe_body}</p>
    {closing}
    <a href="{site}/gardens" class="btn">View Garden</a>
    """

    # Subject prefix: garden-specific if available, else site-wide
    prefix = (garden_config.subject_prefix if garden_config and garden_config.subject_prefix
              else config.subject_prefix or 'YardHarvest')
    subject = f'{prefix} - {garden_name}: {announcement_title}'
    # Sender display name: the garden's own name if configured, else default.
    from_name = garden_config.sender_name if garden_config and garden_config.sender_name else None
    send_email(member_emails, subject, _render(content, config), from_name=from_name)


# ---------------------------------------------------------------------------
# 6. Waitlist Notification
# ---------------------------------------------------------------------------

def send_waitlist_notification(garden_name, user_email):
    """Notify a user that they have been added to a garden waitlist."""
    config = _get_site_email_config()
    site = _get_site_url()

    content = f"""
    <h2>You're on the Waitlist!</h2>
    <p>You've been added to the waitlist for <strong>{_esc(garden_name)}</strong>.</p>
    <p>We'll notify you as soon as a plot becomes available. In the meantime, feel free
       to explore the garden's events and community features.</p>
    <a href="{site}/gardens" class="btn">Browse Gardens</a>
    """
    send_email(user_email, _subject(f'Waitlist Confirmation for {garden_name}', config), _render(content, config))


# ---------------------------------------------------------------------------
# 7. Subscription Box Notification
# ---------------------------------------------------------------------------

def send_subscription_box_notification(plan_name, subscriber_email, box_details):
    """Notify a subscriber that a new box preview has been published.

    Parameters
    ----------
    plan_name : str
    subscriber_email : str
    box_details : str  -- description of what is in the box
    """
    config = _get_site_email_config()
    if not config.enable_subscription_boxes:
        return

    site = _get_site_url()

    content = f"""
    <h2>Your Box is Ready!</h2>
    <p>A new box preview has been published for <strong>{_esc(plan_name)}</strong>.</p>
    <p><strong>What's in the box:</strong></p>
    <blockquote style="border-left:4px solid {config.header_color}; padding:12px 16px; background:#f9faf9; margin:16px 0; border-radius:4px;">
      {_esc(box_details)}
    </blockquote>
    <a href="{site}/subscriptions" class="btn">View Subscription</a>
    """
    send_email(subscriber_email, _subject(f'New Box Preview for {plan_name}', config), _render(content, config))


# ---------------------------------------------------------------------------
# 8. Harvest Notification (sent to interested buyers/members)
# ---------------------------------------------------------------------------

def send_harvest_notification(user_email, category, grower_count, site_url=None):
    """Notify a user that a crop they're interested in is being harvested."""
    config = _get_site_email_config()
    if not getattr(config, 'enable_harvest_notifications', True):
        return

    site = site_url or _get_site_url()
    growers_text = f'{grower_count} grower{"s" if grower_count != 1 else ""}'
    cat = _esc(category)

    content = f"""
    <h2>🌿 {cat} Harvest Alert!</h2>
    <p>Great news! <strong>{cat}</strong> harvests are coming in from
       <strong>{growers_text}</strong> in your community.</p>
    <p>Check the Harvest Forecast to see estimated quantities, timing, and
       connect with growers who have produce available.</p>
    <a href="{site}/harvest-forecast" class="btn">View Harvest Forecast</a>
    <p style="font-size:13px;color:#888;margin-top:24px;">
      You're receiving this because you subscribed to {cat} harvest alerts.
      Visit your <a href="{site}/harvest-forecast">Harvest Forecast</a> to
      manage your notification preferences.</p>
    """
    send_email(
        user_email,
        _subject(f'{category} Harvest Alert', config),
        _render(content, config),
    )


# ---------------------------------------------------------------------------
# 9. Garden Pro Subscription Emails
# ---------------------------------------------------------------------------

def _garden_path(garden_id):
    """Resolve a garden's opaque public_id for building email links. Accepts a
    PK (looked up) or an already-opaque public_id (returned as-is); falls back
    to the given value if the garden can't be found."""
    if not garden_id:
        return garden_id
    if not str(garden_id).isdigit():
        return garden_id
    from app import db
    from app.models import CommunityGarden
    pid = db.session.query(CommunityGarden.public_id).filter_by(id=int(garden_id)).scalar()
    return pid or garden_id


def _garden_billing_url(garden_id):
    return f'{_get_site_url()}/gardens/{_garden_path(garden_id)}/billing'


def send_garden_trial_welcome(garden, organizer):
    """Day 0: Welcome + Quick Start guide."""
    site = _get_site_url()
    name = _esc(organizer.display_name or organizer.username)
    content = f'''
    <h2>Welcome to YardHarvest Garden Management</h2>
    <p>Hi {name},</p>
    <p>Your 14-day trial of Garden Pro for <strong>{_esc(garden.name)}</strong> is now active.</p>
    <p>Here's how to make the most of your first week:</p>
    <ol>
      <li><strong>Add your plots</strong> — Set up your garden layout and assign members to their plots</li>
      <li><strong>Invite your members</strong> — Share your garden link so members can join</li>
      <li><strong>Set up dues</strong> — Configure your seasonal plot fees and generate invoices with one click</li>
      <li><strong>Schedule your first workday</strong> — Create a volunteer shift and let members sign up</li>
    </ol>
    <p style="text-align:center;"><a class="btn" href="{site}/gardens/{garden.public_id}/admin">Go to Garden Dashboard</a></p>
    <p>Your trial includes everything: financial management, volunteer tracking, photo wall, broadcast messaging, custom email branding, and more.</p>
    <p>Questions? Reply to this email — we read every one.</p>
    '''
    send_email(organizer.email, _subject('Welcome to YardHarvest Garden Management'), _render(content))


def send_garden_trial_progress(garden, organizer):
    """Day 3: Setup progress check-in."""
    site = _get_site_url()
    name = _esc(organizer.display_name or organizer.username)
    plot_count = garden.plots.count() if garden.plots else 0
    from app.models import GardenPlot
    member_ids = set()
    for p in GardenPlot.query.filter_by(garden_id=garden.id).all():
        if p.assigned_to_id:
            member_ids.add(p.assigned_to_id)
    member_count = len(member_ids)
    event_count = garden.events.count() if garden.events else 0

    tips = ''
    if plot_count == 0:
        tips += '<p>Getting started is easy — add your first plot in under a minute from the Garden Dashboard.</p>'
    if member_count == 0:
        tips += f'<p>Your members can join by visiting your garden page: <a href="{site}/gardens/{garden.public_id}">{site}/gardens/{garden.public_id}</a></p>'

    content = f'''
    <h2>How's {_esc(garden.name)} coming along?</h2>
    <p>Hi {name},</p>
    <p>You've been on YardHarvest for 3 days. Here's what you've set up so far:</p>
    <table class="detail-table">
      <tr><td>Plots configured</td><td>{plot_count}</td></tr>
      <tr><td>Members joined</td><td>{member_count}</td></tr>
      <tr><td>Events scheduled</td><td>{event_count}</td></tr>
    </table>
    {tips}
    <p style="text-align:center;"><a class="btn" href="{site}/gardens/{garden.public_id}/admin">Continue Setting Up</a></p>
    <p style="color:#888;">11 days left in your trial.</p>
    '''
    send_email(organizer.email, _subject(f"How's {garden.name} coming along?"), _render(content))


def send_garden_trial_halfway(garden, organizer):
    """Day 7: Halfway — feature highlights."""
    site = _get_site_url()
    name = _esc(organizer.display_name or organizer.username)
    content = f'''
    <h2>You're halfway through your trial</h2>
    <p>Hi {name},</p>
    <p>One week in! Here are the Pro features that save organizers the most time:</p>
    <h3>Financial Management</h3>
    <p>Generate dues for every member in one click. Track expenses by category. Send payment reminders automatically.</p>
    <p style="text-align:center;"><a class="btn" href="{site}/gardens/{garden.public_id}/admin">Try Financial Tools</a></p>
    <h3>Volunteer Shifts</h3>
    <p>Create workday shifts, track who shows up, and generate volunteer hour reports for grant applications.</p>
    <h3>Broadcast Messaging</h3>
    <p>Send announcements to every member via email and in-app notification — no more group text chains.</p>
    <p style="color:#888;">7 days left in your trial.</p>
    '''
    send_email(organizer.email, _subject("You're halfway through your trial"), _render(content))


def send_garden_trial_expiring(garden, organizer):
    """Day 12: Trial expiring — 2 days left."""
    site = _get_site_url()
    name = _esc(organizer.display_name or organizer.username)
    sub = garden.subscription
    trial_end = sub.trial_end.strftime('%B %d, %Y') if sub and sub.trial_end else 'soon'
    billing_url = _garden_billing_url(garden.id)

    content = f'''
    <h2>Your {_esc(garden.name)} trial ends in 2 days</h2>
    <p>Hi {name},</p>
    <p>Your Garden Pro trial ends on <strong>{trial_end}</strong>. Here's what happens:</p>
    <h3>What you keep (free forever):</h3>
    <p>Garden profile, member directory, plot assignments, announcements, harvest logging, basic dashboard.</p>
    <h3>What locks on {trial_end}:</h3>
    <p>Financial management (dues, expenses, reminders), volunteer shift scheduling, photo wall, broadcast messaging, custom email branding, plot grid editor, data export.</p>
    <p>Your data is never deleted — it's all there when you're ready to subscribe.</p>
    <table class="detail-table">
      <tr><td>Monthly</td><td><strong>$15/month</strong></td></tr>
      <tr><td>Annual</td><td><strong>$125/year</strong> (save $55)</td></tr>
    </table>
    <p style="text-align:center;"><a class="btn" href="{billing_url}">Subscribe to Garden Pro</a></p>
    '''
    send_email(organizer.email, _subject(f'Your {garden.name} trial ends in 2 days'), _render(content))


def send_garden_trial_ended(garden, organizer):
    """Day 14: Trial ended."""
    name = _esc(organizer.display_name or organizer.username)
    billing_url = _garden_billing_url(garden.id)

    content = f'''
    <h2>Your Garden Pro trial has ended</h2>
    <p>Hi {name},</p>
    <p>Your 14-day trial for <strong>{_esc(garden.name)}</strong> has ended. Pro features are now locked, but your garden profile, plots, members, and all your data remain intact.</p>
    <p>Ready to continue? Choose your plan:</p>
    <table class="detail-table">
      <tr><td>Monthly</td><td><strong>$15/month</strong> — flexible, cancel anytime</td></tr>
      <tr><td>Annual</td><td><strong>$125/year</strong> — save $55 (that's over 3 months free)</td></tr>
    </table>
    <p style="text-align:center;"><a class="btn" href="{billing_url}">Subscribe Now</a></p>
    <p>If you have questions about whether Garden Pro is right for your garden, reply to this email. We're happy to help.</p>
    '''
    send_email(organizer.email, _subject('Your Garden Pro trial has ended'), _render(content))


def send_garden_trial_reengagement(garden, organizer):
    """Day 21: Re-engagement — 1 week post-trial."""
    site = _get_site_url()
    name = _esc(organizer.display_name or organizer.username)
    billing_url = _garden_billing_url(garden.id)

    from app.models import GardenPlot
    member_ids = set()
    for p in GardenPlot.query.filter_by(garden_id=garden.id).all():
        if p.assigned_to_id:
            member_ids.add(p.assigned_to_id)
    member_count = len(member_ids)

    content = f'''
    <h2>{member_count} members are waiting on {_esc(garden.name)}</h2>
    <p>Hi {name},</p>
    <p>It's been a week since your Garden Pro trial ended. Your garden is still active — <strong>{member_count} members</strong> have access and are using the platform.</p>
    <p>The Pro features (dues management, volunteer tracking, messaging) would make your job as organizer a lot easier.</p>
    <table class="detail-table">
      <tr><td>Annual</td><td><strong>$125/year</strong> — works out to ~$10.42/month</td></tr>
    </table>
    <p style="text-align:center;"><a class="btn" href="{billing_url}">Reactivate Garden Pro</a></p>
    <p style="color:#888;font-size:13px;">This is our last email about upgrading. We won't ask again — but the option is always there in your garden settings.</p>
    '''
    send_email(organizer.email, _subject(f'{member_count} members are waiting on {garden.name}'), _render(content))


def send_garden_payment_failed(garden, organizer):
    """Dunning email when payment fails."""
    name = _esc(organizer.display_name or organizer.username)
    billing_url = _garden_billing_url(garden.id)

    content = f'''
    <h2>Action needed: payment failed</h2>
    <p>Hi {name},</p>
    <p>We weren't able to process your Garden Pro payment for <strong>{_esc(garden.name)}</strong>. Your Pro features will remain active for 7 days while you update your payment method.</p>
    <p style="text-align:center;"><a class="btn" href="{billing_url}">Update Payment Method</a></p>
    <p>If your payment isn't updated within 7 days, your garden will revert to the free plan. Your data will not be deleted.</p>
    '''
    send_email(organizer.email, _subject(f'Action needed: payment failed for {garden.name}'), _render(content))


def send_garden_subscription_cancelled(garden, organizer):
    """Confirmation email when subscription is cancelled."""
    name = _esc(organizer.display_name or organizer.username)
    sub = garden.subscription
    period_end = sub.current_period_end.strftime('%B %d, %Y') if sub and sub.current_period_end else 'the end of your billing period'

    content = f'''
    <h2>{_esc(garden.name)} Garden Pro cancelled</h2>
    <p>Hi {name},</p>
    <p>Your Garden Pro subscription for <strong>{_esc(garden.name)}</strong> has been cancelled. You'll continue to have Pro access until <strong>{period_end}</strong>, then your garden will revert to the free plan.</p>
    <p>Your data (plots, members, financials, harvest logs) is never deleted. You can resubscribe anytime from your garden settings.</p>
    <p>We'd love to know what we could do better — reply to this email with any feedback.</p>
    '''
    send_email(organizer.email, _subject(f'{garden.name} Garden Pro cancelled'), _render(content))


# ---------------------------------------------------------------------------
# Plot Assignment Notifications
# ---------------------------------------------------------------------------

def send_plot_assigned_email(garden_name, plot_label, user_email, user_name, garden_id=None):
    """Notify user that they have been assigned a garden plot."""
    config = _get_site_email_config()
    if not config.enable_announcements:
        return
    name = _esc(user_name or 'Gardener')
    site_url = _get_site_url()
    garden_url = f'{site_url}/gardens/{_garden_path(garden_id)}' if garden_id else site_url

    content = f'''
    <h2>You've been assigned a plot!</h2>
    <p>Hi {name},</p>
    <p>Great news — you've been assigned <strong>Plot {_esc(plot_label)}</strong> at <strong>{_esc(garden_name)}</strong>.</p>
    <p>Here's what to do next:</p>
    <table class="detail-table">
      <tr><td>Visit your garden page</td><td>Check plot details, rules, and upcoming events</td></tr>
      <tr><td>Meet your neighbors</td><td>Introduce yourself to fellow gardeners</td></tr>
      <tr><td>Plan your season</td><td>Use the Planting Calendar for Zone 5b guidance</td></tr>
    </table>
    <p style="text-align:center;"><a class="btn" href="{garden_url}">View Your Garden</a></p>
    '''
    send_email(user_email, _subject(f'Plot assigned at {garden_name}'), _render(content))


def send_plot_waitlisted_email(garden_name, user_email, user_name, position, garden_id=None):
    """Notify user they've been added to the waitlist."""
    name = _esc(user_name or 'Gardener')
    site_url = _get_site_url()
    garden_url = f'{site_url}/gardens/{_garden_path(garden_id)}' if garden_id else site_url

    content = f'''
    <h2>You're on the waitlist</h2>
    <p>Hi {name},</p>
    <p>You've been added to the waitlist for <strong>{_esc(garden_name)}</strong>. Your position is <strong>#{position}</strong>.</p>
    <p>We'll notify you as soon as a plot becomes available. In the meantime, you can check garden events and announcements.</p>
    <p style="text-align:center;"><a class="btn" href="{garden_url}">View Garden</a></p>
    '''
    send_email(user_email, _subject(f'Waitlisted for {garden_name}'), _render(content))


def send_dues_reminder_email(garden_name, user_email, user_name, amount, season_year, garden_id=None):
    """Remind a member that dues are outstanding."""
    name = _esc(user_name or 'Gardener')
    g = _esc(garden_name)
    site_url = _get_site_url()
    garden_url = f'{site_url}/gardens/{_garden_path(garden_id)}' if garden_id else site_url

    content = f'''
    <h2>Dues reminder for {g}</h2>
    <p>Hi {name},</p>
    <p>This is a friendly reminder that your <strong>{season_year}</strong> garden dues of <strong>${amount:.2f}</strong> are outstanding for <strong>{g}</strong>.</p>
    <p>You can pay online from your garden page — it only takes a moment.</p>
    <p style="text-align:center;"><a class="btn" href="{garden_url}">Pay Dues Now</a></p>
    '''
    send_email(user_email, _subject(f'Dues reminder: {garden_name}'), _render(content))


def send_shift_reminder_email(garden_name, user_email, user_name, shift_title, shift_date, garden_id=None):
    """Remind a volunteer about an upcoming shift."""
    name = _esc(user_name or 'Gardener')
    g = _esc(garden_name)
    st = _esc(shift_title)
    site_url = _get_site_url()
    garden_url = f'{site_url}/gardens/{_garden_path(garden_id)}' if garden_id else site_url

    content = f'''
    <h2>Upcoming shift at {g}</h2>
    <p>Hi {name},</p>
    <p>Just a reminder — you're signed up for <strong>{st}</strong> at <strong>{g}</strong> on <strong>{_esc(shift_date)}</strong>.</p>
    <p style="text-align:center;"><a class="btn" href="{garden_url}">View Garden</a></p>
    '''
    send_email(user_email, _subject(f'Shift reminder: {shift_title}'), _render(content))


def send_email_change_verification(user, new_email, token):
    """Send the verification link to the NEW address. Transactional/security
    email — always sends regardless of notification toggles."""
    site_url = _get_site_url()
    verify_url = f'{site_url}/verify-email-change?token={token}'
    display = _esc(user.display_name or user.username)

    content = f'''
    <h2>Verify your new email address</h2>
    <p>Hi {display},</p>
    <p>A request was made to change the email on your YardHarvest account to
       <strong>{_esc(new_email)}</strong>. Click the button below to confirm:</p>
    <p style="text-align: center;">
      <a class="btn" href="{verify_url}">Verify Email Address</a>
    </p>
    <p style="font-size: 0.9em; color: #666;">
      This link expires in 24 hours and can only be used once. Your account
      email will not change until you confirm. If you didn't request this,
      you can safely ignore this email.</p>
    '''
    send_email(new_email, _subject('Verify your new email address'), _render(content))


def send_email_change_notice(user, new_email):
    """Security notice to the CURRENT address that a change was requested."""
    display = _esc(user.display_name or user.username)
    site_url = _get_site_url()

    content = f'''
    <h2>Email change requested</h2>
    <p>Hi {display},</p>
    <p>A request was made to change your YardHarvest account email to
       <strong>{_esc(new_email)}</strong>. Nothing changes until that address is
       verified.</p>
    <p>If this wasn't you, <a href="{site_url}/forgot-password">reset your
       password</a> immediately to secure your account.</p>
    '''
    send_email(user.email, _subject('Email change requested on your account'), _render(content))


def send_email_changed_confirmation(user, old_email):
    """Notify the OLD address that the account email has been changed."""
    display = _esc(user.display_name or user.username)
    site_url = _get_site_url()

    content = f'''
    <h2>Your account email was changed</h2>
    <p>Hi {display},</p>
    <p>The email on your YardHarvest account was changed from
       <strong>{_esc(old_email)}</strong> to <strong>{_esc(user.email)}</strong>.</p>
    <p>If this wasn't you, <a href="{site_url}/forgot-password">reset your
       password</a> immediately and contact support.</p>
    '''
    send_email(old_email, _subject('Your account email was changed'), _render(content))


def send_shift_signup_email(garden_name, user_email, user_name, shift_title, shift_date, garden_id=None):
    """Confirm to a volunteer that their shift signup was received."""
    name = _esc(user_name or 'Gardener')
    g = _esc(garden_name)
    st = _esc(shift_title)
    site_url = _get_site_url()
    garden_url = f'{site_url}/gardens/{_garden_path(garden_id)}' if garden_id else site_url

    content = f'''
    <h2>You're signed up!</h2>
    <p>Hi {name},</p>
    <p>You're confirmed for <strong>{st}</strong> at <strong>{g}</strong> on <strong>{_esc(shift_date)}</strong>.</p>
    <p>If your plans change, you can cancel your signup from the garden's events page.</p>
    <p style="text-align:center;"><a class="btn" href="{garden_url}">View Garden</a></p>
    '''
    send_email(user_email, _subject(f'Signed up: {shift_title}'), _render(content))


def send_event_cancelled_email(garden_name, event_title, event_date, recipient_emails, garden_id=None):
    """Notify RSVP'd members/volunteers that a garden event was cancelled."""
    if not recipient_emails:
        return
    g = _esc(garden_name)
    et = _esc(event_title)
    site_url = _get_site_url()
    garden_url = f'{site_url}/gardens/{_garden_path(garden_id)}' if garden_id else site_url

    content = f'''
    <h2>Event cancelled</h2>
    <p><strong>{et}</strong> at <strong>{g}</strong>{f' on <strong>{_esc(event_date)}</strong>' if event_date else ''} has been cancelled.</p>
    <p>We're sorry for any inconvenience. Keep an eye on the garden page for upcoming events.</p>
    <p style="text-align:center;"><a class="btn" href="{garden_url}">View Garden</a></p>
    '''
    send_email(recipient_emails, _subject(f'Cancelled: {event_title} at {garden_name}'), _render(content))


def send_refund_confirmation_email(order, buyer_email, refund_amount, is_full):
    """Notify buyer that a refund has been issued."""
    config = _get_site_email_config()
    refund_type = 'Full' if is_full else 'Partial'
    site_url = _get_site_url()

    content = f'''
    <h2>{refund_type} Refund Issued</h2>
    <p>A {refund_type.lower()} refund of <strong>${refund_amount:.2f}</strong> has been issued for your order <strong>#{order.id}</strong>.</p>
    <table class="detail-table">
      <tr><td>Order</td><td>#{order.id}</td></tr>
      <tr><td>Original Total</td><td>${order.total_price:.2f}</td></tr>
      <tr><td>Refund Amount</td><td>${refund_amount:.2f}</td></tr>
    </table>
    <p>The refund will appear on your statement within 5-10 business days.</p>
    <p style="text-align:center;"><a class="btn" href="{site_url}/orders/{order.id}">View Order</a></p>
    '''
    send_email(buyer_email, _subject(f'{refund_type} refund for order #{order.id}'), _render(content))
