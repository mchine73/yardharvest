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
import functools
import logging
import re
from flask import current_app, render_template_string
from flask_babel import format_date, gettext as _, ngettext
from app.i18n import force_locale

log = logging.getLogger(__name__)


def _html_to_text(html_body):
    """Derive a readable plain-text alternative from an HTML email body.

    Sending a multipart message (text + HTML) instead of HTML-only is a
    significant inbox-placement signal — most spam filters penalize HTML-only
    mail. Tokens like ``{{first_name}}`` survive the strip, so this also works
    on un-rendered ZeptoMail batch templates.
    """
    if not html_body:
        return ''
    text = re.sub(r'(?is)<(style|script|head)[^>]*>.*?</\1>', '', html_body)
    text = re.sub(r'(?i)<br\s*/?>', '\n', text)
    text = re.sub(r'(?i)</(p|div|tr|h[1-6]|li|table|ul|ol)>', '\n', text)
    text = re.sub(r'(?s)<[^>]+>', '', text)        # remaining tags
    text = html.unescape(text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n[ \t]+', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _esc(value):
    """HTML-escape a user-provided value for safe interpolation into an
    f-string email body. Use for any field an organizer or member controls
    (announcement title/body, closing text, captions, names)."""
    return html.escape(str(value or ''))

# ---------------------------------------------------------------------------
# Dynamic base template (uses Jinja2 variables from config)
# ---------------------------------------------------------------------------

# YardHarvest brand (frontend/src/App.css). Emails are the one surface where a
# stale admin setting can drift the brand without anyone noticing, so the shell
# keeps the palette here rather than trusting whatever is in the config row.
BRAND_INK = '#22242a'
BRAND_LIME = '#e3ff8f'
BRAND_MUTED = '#6b6e76'
_MIN_HEADER_CONTRAST = 4.5          # WCAG AA for the large header wordmark


def _relative_luminance(hex_color):
    """WCAG relative luminance of a #rrggbb color."""
    h = (hex_color or '').lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    if len(h) != 6:
        raise ValueError(hex_color)
    channels = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255
        channels.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = channels
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast_with_white(hex_color):
    return 1.05 / (_relative_luminance(hex_color) + 0.05)


def header_band_color(configured):
    """The header background to actually paint.

    The header wordmark is white, so a light ``header_color`` renders white on
    light — unreadable, and off-brand besides. Anything that fails AA against
    white falls back to the brand ink. A deliberate dark brand color still
    works; a leftover from an older palette corrects itself.
    """
    candidate = (configured or '').strip() or BRAND_INK
    try:
        if _contrast_with_white(candidate) >= _MIN_HEADER_CONTRAST:
            return candidate
    except ValueError:
        pass
    return BRAND_INK


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
        <a href="{{ site_url }}">{{ footer_visit }}</a>
      </p>
      {% if footer_text %}
      <p>{{ footer_text }}</p>
      {% else %}
      <p>{{ footer_reason }}<br>
         {{ footer_contact }}
         <a href="mailto:James@yardharvest.app">James@yardharvest.app</a>.</p>
      {% endif %}
    </div>
  </div>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Booking template — appointment emails (confirmations, owner notifications,
# cancellations). The recipient is a meeting guest who usually has NO platform
# account, so this shell drops the account-holder footer and the big brand
# banner in favor of a slim wordmark + a "just reply" footer.
# ---------------------------------------------------------------------------

BOOKING_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body { margin: 0; padding: 0; font-family: 'Onest', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f2f3f3; color: #22242a; }
    .email-wrapper { max-width: 560px; margin: 24px auto; background: #ffffff; border: 1px solid #e5e6e6; border-radius: 14px; overflow: hidden; }
    .email-header { padding: 24px 32px 16px; border-bottom: 3px solid #e3ff8f; }
    .email-header .wordmark { font-size: 18px; font-weight: 800; letter-spacing: -0.02em; color: #22242a; }
    .email-header .kicker { font-size: 12px; color: #6b6e76; margin-top: 2px; }
    .email-body { padding: 28px 32px; line-height: 1.6; font-size: 15px; color: #22242a; }
    .email-body h2 { color: #22242a; margin-top: 0; font-weight: 600; letter-spacing: -0.02em; }
    .email-body p { margin: 12px 0; }
    .email-body a { color: #3b6d11; }
    .btn { display: inline-block; background-color: #e3ff8f; color: #22242a !important; text-decoration: none; padding: 13px 28px; border-radius: 10px; font-weight: 700; margin: 18px 0; }
    .detail-table { width: 100%; border-collapse: collapse; margin: 16px 0; }
    .detail-table td { padding: 10px 12px; border-bottom: 1px solid #eceeec; }
    .detail-table td:first-child { font-weight: 600; color: #6b6e76; width: 40%; }
    .email-footer { background-color: #f2f3f3; padding: 18px 32px; font-size: 12px; color: #6b6e76; text-align: center; }
    .email-footer a { color: #3b6d11; text-decoration: none; font-weight: 600; }
  </style>
</head>
<body>
  <div class="email-wrapper">
    <div class="email-header">
      <div class="wordmark">YardHarvest</div>
      <div class="kicker">Scheduling</div>
    </div>
    <div class="email-body">
      {{ content | safe }}
    </div>
    <div class="email-footer">
      <p>This email is about a meeting booked through {{ owner_name }}&#39;s
         scheduling page at <a href="{{ site_url }}/book">{{ site_host }}/book</a>.</p>
      <p>Need to make a change? Use the link above — or just reply to this email.</p>
    </div>
  </div>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Outreach template — CRM sales mail (agent follow-ups, one-off sends,
# campaigns). Deliberately looks like a personally written email: white
# background, no banner, no logo, plain typography — which reads better and
# lands better than brand-shell marketing mail. Footer keeps the CAN-SPAM
# essentials (identity + unsubscribe) and nothing else.
# ---------------------------------------------------------------------------

OUTREACH_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body { margin: 0; padding: 0; background-color: #ffffff; font-family: 'Onest', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #22242a; }
    .email-body { max-width: 560px; margin: 0 auto; padding: 28px 20px 8px; line-height: 1.65; font-size: 15px; color: #22242a; }
    .email-body p { margin: 13px 0; }
    .email-body a { color: #3b6d11; }
    .email-body img { max-width: 100%; height: auto; border-radius: 8px; margin: 8px 0; }
    .email-body ul, .email-body ol { margin: 12px 0; padding-left: 22px; }
    .email-body h1, .email-body h2, .email-body h3 { letter-spacing: -0.02em; }
    .email-signature { max-width: 560px; margin: 0 auto; padding: 4px 20px 18px; line-height: 1.5; font-size: 14px; color: #22242a; }
    .email-signature a { color: #3b6d11; text-decoration: none; }
    .email-footer { max-width: 560px; margin: 0 auto; padding: 14px 20px 26px; font-size: 12px; color: #9a9da4; border-top: 1px solid #eceeec; }
    .email-footer a { color: #9a9da4; }
  </style>
</head>
<body>
  <div class="email-body">
    {{ content | safe }}
  </div>
  <div class="email-signature">
    <p style="margin: 0;"><strong>James Goodman</strong><br>
       Founder<br>
       <a href="{{ site_url }}">YardHarvest.app</a></p>
  </div>
  <div class="email-footer">
    <p>You received this email from {{ from_name }} at YardHarvest
       (<a href="{{ site_url }}">{{ site_host }}</a>).
       <a href="{{ site_url }}/unsubscribe">Unsubscribe</a></p>
    {% if mailing_address %}<p>{{ mailing_address }}</p>{% endif %}
  </div>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Site URL helper (default for development)
# ---------------------------------------------------------------------------

SITE_URL = 'http://localhost:5173'


def in_recipient_language(resolve):
    """Render this email in its recipient's language.

    `resolve` is given the sender's own arguments and returns whatever
    force_locale understands — a User, a language code, or an address to look
    up. The decorator form exists because wrapping a body in `with` means
    re-indenting every line of a long f-string, and re-indenting HTML by hand
    is how you lose a closing tag. Declaring the rule at the top of the
    function says the same thing more plainly:

        @in_recipient_language(lambda garden, organizer: organizer)
        def send_garden_trial_welcome(garden, organizer):
            ...

    The senders converted before this existed use an explicit `with
    force_locale(...)` inside the body. The two are equivalent; the inline
    form is left alone rather than churned.
    """
    def decorate(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                target = resolve(*args, **kwargs)
            except Exception:
                target = None
            with force_locale(target):
                return fn(*args, **kwargs)
        return wrapper
    return decorate


def _by_language(addresses):
    """Group addresses by the language their owner reads.

    A bulk send renders ONE body, so a garden announcement to forty members
    cannot be in two languages at once. Grouping lets each language get its
    own batch — the cost is one extra send per language actually present,
    which on a single-language garden is no extra send at all.

    Returns {language-or-None: [addresses]}. The None group keeps whatever
    language the request is already in.
    """
    groups = {}
    if not addresses:
        return groups
    try:
        from app.models import User
        wanted = {str(a).strip().lower() for a in addresses if a}
        rows = User.query.filter(User.email.in_(list(wanted))).all()
        known = {u.email: getattr(u, 'language', None) for u in rows}
    except Exception:
        log.debug('Could not group recipients by language', exc_info=True)
        known = {}
    for address in addresses:
        if not address:
            continue
        groups.setdefault(known.get(str(address).strip().lower()), []).append(address)
    return groups


def _recipient_language(to):
    """The stored language of whoever this message is addressed to.

    An email is written in its RECIPIENT's language, not in the language of
    whoever triggered it. These senders take an address rather than a user —
    `send_dues_reminder_email(garden_name, user_email, ...)` — so the address
    is what we resolve the preference from. An organizer clicking "send dues
    reminders" is one English request producing forty messages in forty
    members' languages.

    Returns None for an address with no account (a booking guest, an invite to
    someone who has not signed up), which leaves the language unchanged.
    """
    if not to:
        return None
    address = (to[0] if isinstance(to, (list, tuple)) and to else to)
    try:
        from app.models import User
        user = User.query.filter(
            User.email == str(address).strip().lower()).first()
        return getattr(user, 'language', None) if user else None
    except Exception:
        # Never let a language lookup stop a message going out.
        log.debug('Could not resolve the recipient language', exc_info=True)
        return None


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

def is_email_suppressed(email):
    """True if the address has globally unsubscribed from bulk email
    (announcements, campaigns). Transactional mail ignores this list."""
    if not email:
        return False
    try:
        from app.models import EmailUnsubscribe
        return EmailUnsubscribe.query.filter_by(
            email=email.strip().lower()).first() is not None
    except Exception:
        return False


def _list_unsubscribe_headers():
    """ZeptoMail mime_headers giving recipients a standard one-step opt-out of
    bulk mail (Gmail/Yahoo bulk-sender requirement; improves inbox placement)."""
    base = _get_site_url()
    return {
        'List-Unsubscribe':
            f'<mailto:james@yardharvest.app?subject=Unsubscribe>, <{base}/unsubscribe>',
    }


def send_email(to, subject, html_body, from_name=None, from_email=None, bulk=False,
               bcc=None, attachments=None, mime_headers=None):
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
    mime_headers : dict, optional
        Extra MIME headers (e.g. In-Reply-To/References for threading, or the
        List-Unsubscribe pair for automated one-to-one mail). Merged on top of
        the bulk List-Unsubscribe headers when ``bulk`` is set.
    """
    recipients = to if isinstance(to, list) else [to]

    headers = dict(_list_unsubscribe_headers()) if bulk else {}
    if mime_headers:
        headers.update(mime_headers)
    mime_headers = headers or None
    bcc_list = [bcc] if isinstance(bcc, str) else (list(bcc) if bcc else None)
    # --- Backend 1: Zoho ZeptoMail (transactional API, send-only token) ---
    if _send_via_zeptomail(recipients, subject, html_body,
                           from_name=from_name, from_email=from_email,
                           mime_headers=mime_headers, bcc=bcc_list,
                           attachments=attachments):
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


def _send_via_zeptomail(recipients, subject, html_body, from_name=None,
                        from_email=None, mime_headers=None, bcc=None,
                        attachments=None):
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
        'textbody': _html_to_text(html_body),  # multipart: better inbox placement
    }
    if bcc:
        # Don't BCC an address that's already a direct recipient (no dup copy).
        tos = {r.lower() for r in recipients}
        bcc_clean = [b for b in bcc if b and b.lower() not in tos]
        if bcc_clean:
            payload['bcc'] = [{'email_address': {'address': b}} for b in bcc_clean]
    if mime_headers:
        payload['mime_headers'] = mime_headers
    if attachments:
        # ZeptoMail attachment shape: name + mime_type + base64 content.
        import base64
        payload['attachments'] = [{
            'name': a['name'],
            'mime_type': a.get('mime_type', 'application/octet-stream'),
            'content': base64.b64encode(a['content']).decode('ascii'),
        } for a in attachments]
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

    clean = [r for r in (recipients or [])
             if r and r.get('email') and not is_email_suppressed(r['email'])]
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
        'textbody': _html_to_text(html_body),  # multipart: better inbox placement
        'mime_headers': _list_unsubscribe_headers(),  # bulk mail: List-Unsubscribe
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
    """Wrap *content_html* inside the branded PLATFORM template.

    This shell (banner header + account-holder footer) is exclusively for
    platform messages to account holders — orders, garden notifications,
    account/security mail, trial drips. Booking mail uses
    ``render_booking_email`` and CRM outreach uses ``render_outreach_email``;
    each audience gets a footer that is actually true for them.

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
        header_color=header_band_color(getattr(config, 'header_color', None)),
        logo_url=getattr(config, 'logo_url', '') or '',
        # A tagline the admin typed is their words and is left alone. The
        # fallback is our own copy, so it follows the recipient's language —
        # otherwise every Spanish email carries an English line under the logo.
        tagline=(getattr(config, 'tagline', None)
                 or _('Less admin, more garden')),
        from_name=getattr(config, 'from_name', 'YardHarvest') or 'YardHarvest',
        footer_text=getattr(config, 'footer_text', '') or '',
        # The shell's own prose. Translated here rather than inside the
        # template because this string is assembled in Python and pybabel
        # only scans app/templates for Jinja.
        footer_visit=_('Visit %(name)s', name=_brand(config)),
        footer_reason=_('You received this email because you have an account '
                        'on %(name)s.', name=_brand(config)),
        footer_contact=_('If you believe this was sent in error, please '
                         'contact'),
    )


def _brand(config):
    return getattr(config, 'from_name', 'YardHarvest') or 'YardHarvest'


def _site_host():
    """Bare host of the public site (e.g. ``www.yardharvest.app``) for footers."""
    return _get_site_url().split('://')[-1].split('/')[0]


def render_booking_email(content_html, owner_name=''):
    """Wrap booking content (confirmations, cancellations, owner notices) in
    the scheduling shell — slim wordmark, no account-holder claim, and a
    "just reply" footer, since the guest usually has no platform account."""
    return render_template_string(
        BOOKING_TEMPLATE,
        content=content_html,
        site_url=_get_site_url(),
        site_host=_site_host(),
        owner_name=owner_name or 'the host',
    )


def render_outreach_email(content_html, from_name=None):
    """Wrap CRM outreach content in the plain personal-letter shell (no
    banner/logo — reads like an individually written email) with a minimal
    identity + unsubscribe footer."""
    if from_name is None:
        try:
            from_name = current_app.config.get('CRM_FROM_NAME') or 'James Goodman'
        except Exception:
            from_name = 'James Goodman'
    # CAN-SPAM requires a physical postal address on commercial mail; the
    # shared footer means one-to-one BDR mail inherits it too, not just
    # campaigns. Configure via CRM_MAILING_ADDRESS (env or config).
    try:
        import os
        mailing_address = (os.environ.get('CRM_MAILING_ADDRESS', '')
                           or current_app.config.get('CRM_MAILING_ADDRESS', ''))
    except Exception:
        mailing_address = ''
    return render_template_string(
        OUTREACH_TEMPLATE,
        content=content_html,
        site_url=_get_site_url(),
        site_host=_site_host(),
        from_name=from_name,
        mailing_address=mailing_address,
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
    """Render a CRM sales-email body inside the plain OUTREACH shell (no brand
    banner — reads like a personally written email).

    Accepts HTML (from the rich composer / templates / AI) — sanitized — or
    plain text — escaped with newlines preserved. Returns full HTML to send.
    ``config`` is accepted for backwards compatibility but unused (the outreach
    shell deliberately ignores site branding)."""
    body = body or ''
    if '<' in body and '>' in body:          # looks like HTML
        content = sanitize_email_html(body)
    else:                                     # plain text -> paragraphs
        paras = [p.strip() for p in body.split('\n\n')]
        content = ''.join(
            '<p>' + _esc(p).replace('\n', '<br>') + '</p>' for p in paras if p)
    return render_outreach_email(content)


def _subject(label, config=None):
    """Build a subject line with the configured prefix."""
    label = re.sub(r'[\r\n\t]+', ' ', str(label))
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

    with force_locale(user):
        content = f'''
    <h2>{_('Password Reset Request')}</h2>
    <p>{_('Hi %(name)s,', name=display)}</p>
    <p>{_('We received a request to reset the password for your YardHarvest account. Click the button below to choose a new password:')}</p>
    <p style="text-align: center;">
      <a class="btn" href="{reset_url}">{_('Reset Your Password')}</a>
    </p>
    <p style="font-size: 0.9em; color: #6b6e76;">
      {_("This link expires in 1 hour and can only be used once. If you didn't request a password reset, you can safely ignore this email.")}</p>
    '''
        subject = _subject(_('Password Reset Request'))
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
            closing = (f'<p style="margin-top:24px;color:#6b6e76;font-style:italic;">'
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
            '<blockquote style="border-left:4px solid #e3ff8f;padding:12px 16px;background:#f9faf9;margin:16px 0;border-radius:4px;">'
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

@in_recipient_language(lambda order, buyer_email: _recipient_language(buyer_email))
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
    <h2>{_('Order Confirmed!')}</h2>
    <p>{_("Thanks for your order! Here's a summary:")}</p>
    <table class="detail-table">
      <tr><td>{_('Order #')}</td><td>{order.id}</td></tr>
      <tr><td>{_('Seller')}</td><td>{_esc(order.seller_user.display_name or order.seller_user.username)}</td></tr>
      <tr><td>{_('Fulfillment')}</td><td>{order.fulfillment_method.title()}</td></tr>
      <tr><td>{_('Total')}</td><td><strong>${order.total_price:.2f}</strong></td></tr>
    </table>
    <table style="width:100%;border-collapse:collapse;margin:16px 0;">
      <thead>
        <tr style="border-bottom:2px solid {config.header_color};">
          <th style="text-align:left;padding:8px;">{_('Item')}</th>
          <th style="text-align:center;padding:8px;">{_('Qty')}</th>
          <th style="text-align:right;padding:8px;">{_('Price')}</th>
        </tr>
      </thead>
      <tbody>{items_html}</tbody>
    </table>
    <a href="{site}/orders" class="btn">{_('View Your Orders')}</a>
    """
    send_email(buyer_email, _subject(f'Order #{order.id} Confirmed', config), _render(content, config))


# ---------------------------------------------------------------------------
# 2. New Order Notification (sent to seller)
# ---------------------------------------------------------------------------

@in_recipient_language(lambda order, seller_email: _recipient_language(seller_email))
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
    <h2>{_('New Order Received!')}</h2>
    <p>{_('You have a new order from <strong>%(buyer)s</strong>.', buyer=_esc(buyer_name))}</p>
    <table class="detail-table">
      <tr><td>{_('Order #')}</td><td>{order.id}</td></tr>
      <tr><td>{_('Items')}</td><td>{items_summary}</td></tr>
      <tr><td>{_('Fulfillment')}</td><td>{order.fulfillment_method.title()}</td></tr>
      <tr><td>{_('Total')}</td><td><strong>${order.total_price:.2f}</strong></td></tr>
    </table>
    <a href="{site}/orders/selling" class="btn">{_('View Seller Dashboard')}</a>
    """
    send_email(seller_email,
               _subject(_('New Order #%(order)s from %(buyer)s', order=order.id, buyer=buyer_name), config),
               _render(content, config))


# ---------------------------------------------------------------------------
# 3. Order Status Update (sent to buyer)
# ---------------------------------------------------------------------------

@in_recipient_language(lambda order, buyer_email, new_status: _recipient_language(buyer_email))
def send_order_status_update(order, buyer_email, new_status):
    """Notify the buyer that their order status has changed."""
    config = _get_site_email_config()
    if not config.enable_status_updates:
        return

    site = _get_site_url()
    status_labels = {
        'accepted': _('Accepted'),
        'completed': _('Completed'),
        'cancelled': _('Cancelled'),
    }
    label = status_labels.get(new_status, new_status.title())
    seller_name = _esc(order.seller_user.display_name or order.seller_user.username)
    fulfillment = _esc(order.fulfillment_method)

    status_messages = {
        'accepted': _('%(seller)s has accepted your order and will prepare it for %(fulfillment)s.',
                      seller=seller_name, fulfillment=fulfillment),
        'completed': _('Your order with %(seller)s has been marked as completed. Enjoy your fresh produce!',
                       seller=seller_name),
        'cancelled': _('Your order with %(seller)s has been cancelled.', seller=seller_name),
    }
    detail = status_messages.get(
        new_status,
        _('Your order status has been updated to %(status)s.', status=label))

    content = f"""
    <h2>{_('Order #%(order)s - %(status)s', order=order.id, status=label)}</h2>
    <p>{detail}</p>
    <table class="detail-table">
      <tr><td>{_('Order #')}</td><td>{order.id}</td></tr>
      <tr><td>{_('Seller')}</td><td>{seller_name}</td></tr>
      <tr><td>{_('Status')}</td><td><strong>{label}</strong></td></tr>
      <tr><td>{_('Total')}</td><td>${order.total_price:.2f}</td></tr>
    </table>
    <a href="{site}/orders" class="btn">{_('View Order Details')}</a>
    """
    send_email(buyer_email,
               _subject(_('Order #%(order)s %(status)s', order=order.id, status=label), config),
               _render(content, config))


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

    with force_locale(_recipient_language(recipient_email)):
        content = f"""
    <h2>{_('New Message from %(sender)s', sender=safe_sender)}</h2>
    <p>{_('You have a new message:')}</p>
    <blockquote style="border-left:4px solid {config.header_color}; padding:12px 16px; background:#f9faf9; margin:16px 0; border-radius:4px;">
      {safe_preview}
    </blockquote>
    <a href="{site}/messages" class="btn">{_('View Messages')}</a>
    """
        send_email(recipient_email,
                   _subject(_('New message from %(sender)s', sender=sender_name), config),
                   _render(content, config))


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

    # Honor the global unsubscribe list (announcements are bulk mail).
    member_emails = [e for e in member_emails if not is_email_suppressed(e)]
    if not member_emails:
        return

    # Load garden-specific overrides
    garden_config = _get_garden_email_config(garden_id) if garden_id else None

    site = _get_site_url()
    # All four interpolated values below are organizer-controlled — escape them.
    safe_garden = _esc(garden_name)
    safe_title = _esc(announcement_title)
    safe_body = _esc(announcement_body)
    priority_class = ''
    accent = (garden_config.accent_color if garden_config and garden_config.accent_color
              else config.header_color)
    if priority == 'urgent':
        priority_class = 'priority-urgent'
    elif priority == 'important':
        priority_class = 'priority-important'

    closing = ''
    if garden_config and garden_config.closing_text:
        closing = (f'<p style="margin-top:24px;color:#6b6e76;font-style:italic;">'
                   f'{_esc(garden_config.closing_text)}</p>')

    # Built inside the per-language loop below.

    # Subject prefix: garden-specific if available, else site-wide
    prefix = (garden_config.subject_prefix if garden_config and garden_config.subject_prefix
              else config.subject_prefix or 'YardHarvest')
    subject = f'{prefix} - {garden_name}: {announcement_title}'
    # Sender display name: the garden's own name if configured, else default.
    from_name = garden_config.sender_name if garden_config and garden_config.sender_name else None
    # One batch per language. A bulk send renders ONE body, so forty members
    # across two languages need two sends — and a single-language garden still
    # takes exactly one. The announcement's own title and body are the
    # organizer's words and stay exactly as written; only the wrapper around
    # them is ours to translate.
    for language, group in _by_language(member_emails).items():
        with force_locale(language):
            if priority == 'urgent':
                badge = f'<span class="priority-urgent">[{_("URGENT")}]</span> '
            elif priority == 'important':
                badge = f'<span class="priority-important">[{_("IMPORTANT")}]</span> '
            else:
                badge = ''
            content = f"""
    <h2 style="color:{accent};">{badge}{_('New Announcement - %(garden)s', garden=safe_garden)}</h2>
    <h3 class="{priority_class}">{safe_title}</h3>
    <p>{safe_body}</p>
    {closing}
    <a href="{site}/gardens" class="btn">{_('View Garden')}</a>
    """
            send_email(group, subject, _render(content, config),
                       from_name=from_name, bulk=True)


# ---------------------------------------------------------------------------
# 6. Waitlist Notification
# ---------------------------------------------------------------------------

def send_waitlist_notification(garden_name, user_email):
    """Notify a user that they have been added to a garden waitlist."""
    config = _get_site_email_config()
    site = _get_site_url()

    with force_locale(_recipient_language(user_email)):
        content = f"""
    <h2>{_("You're on the Waitlist!")}</h2>
    <p>{_('You have been added to the waitlist for <strong>%(garden)s</strong>.', garden=_esc(garden_name))}</p>
    <p>{_("We will let you know as soon as a plot becomes available. In the meantime, feel free to explore the garden's events and community features.")}</p>
    <a href="{site}/gardens" class="btn">{_('Browse Gardens')}</a>
    """
        send_email(user_email,
                   _subject(_('Waitlist Confirmation for %(garden)s', garden=garden_name), config),
                   _render(content, config))


# ---------------------------------------------------------------------------
# 7. Subscription Box Notification
# ---------------------------------------------------------------------------

@in_recipient_language(lambda plan_name, subscriber_email, box_details: _recipient_language(subscriber_email))
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
    <h2>{_('Your Box is Ready!')}</h2>
    <p>{_('A new box preview has been published for <strong>%(plan)s</strong>.', plan=_esc(plan_name))}</p>
    <p><strong>{_("What's in the box:")}</strong></p>
    <blockquote style="border-left:4px solid {config.header_color}; padding:12px 16px; background:#f9faf9; margin:16px 0; border-radius:4px;">
      {_esc(box_details)}
    </blockquote>
    <a href="{site}/subscriptions" class="btn">{_('View Subscription')}</a>
    """
    send_email(subscriber_email,
               _subject(_('New Box Preview for %(plan)s', plan=plan_name), config),
               _render(content, config))


# ---------------------------------------------------------------------------
# 8. Harvest Notification (sent to interested buyers/members)
# ---------------------------------------------------------------------------

def send_harvest_notification(user_email, category, grower_count, site_url=None):
    """Notify a user that a crop they're interested in is being harvested."""
    config = _get_site_email_config()
    if not getattr(config, 'enable_harvest_notifications', True):
        return

    site = site_url or _get_site_url()
    cat = _esc(category)

    with force_locale(_recipient_language(user_email)):
        # Pluralised by the catalog, not by appending "s": the rule differs per
        # language and gluing it on in English cannot be translated at all.
        growers_text = ngettext('%(num)s grower', '%(num)s growers', grower_count)

        content = f"""
        <h2>🌿 {_('%(category)s Harvest Alert!', category=cat)}</h2>
        <p>{_('Great news! <strong>%(category)s</strong> harvests are coming in from <strong>%(growers)s</strong> in your community.', category=cat, growers=growers_text)}</p>
        <p>{_('Check the Harvest Forecast to see estimated quantities, timing, and connect with growers who have produce available.')}</p>
        <a href="{site}/harvest-forecast" class="btn">{_('View Harvest Forecast')}</a>
        <p style="font-size:13px;color:#6b6e76;margin-top:24px;">
          {_("You're receiving this because you subscribed to %(category)s harvest alerts.", category=cat)}
          {_('Visit your <a href="%(url)s">Harvest Forecast</a> to manage your notification preferences.', url=f'{site}/harvest-forecast')}</p>
    """
        send_email(
            user_email,
            _subject(_('%(category)s Harvest Alert', category=category), config),
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


def _pro_pricing():
    """Garden Pro pricing for email copy — whatever the admin console holds."""
    from app.pricing import garden_pro_pricing
    return garden_pro_pricing()


def _usd(cents):
    """Format cents as an email-friendly dollar string ($15, $10.42)."""
    dollars = cents / 100
    return f'${dollars:,.0f}' if dollars == int(dollars) else f'${dollars:,.2f}'


@in_recipient_language(lambda garden, organizer: organizer)
def send_garden_trial_welcome(garden, organizer):
    """Day 0 of the trial: Welcome + Quick Start guide."""
    site = _get_site_url()
    name = _esc(organizer.display_name or organizer.username)
    trial_days = _pro_pricing()['trial_days']
    content = f'''
    <h2>{_('Welcome to YardHarvest Garden Management')}</h2>
    <p>{_('Hi %(name)s,', name=name)}</p>
    <p>{_('Your %(days)s-day trial of Garden Pro for <strong>%(garden)s</strong> is now active.', days=trial_days, garden=_esc(garden.name))}</p>
    <p>{_("Here's how to make the most of your first week:")}</p>
    <ol>
      <li><strong>{_('Add your plots')}</strong> — {_('Set up your garden layout and assign members to their plots')}</li>
      <li><strong>{_('Invite your members')}</strong> — {_('Share your garden link so members can join')}</li>
      <li><strong>{_('Set up dues')}</strong> — {_('Configure your seasonal plot fees and generate invoices with one click')}</li>
      <li><strong>{_('Schedule your first workday')}</strong> — {_('Create a volunteer shift and let members sign up')}</li>
    </ol>
    <p style="text-align:center;"><a class="btn" href="{site}/gardens/{garden.public_id}/admin">{_('Go to Garden Dashboard')}</a></p>
    <p>{_('Your trial includes everything: financial management, volunteer tracking, photo wall, broadcast messaging, custom email branding, and more.')}</p>
    <p>{_('Questions? Reply to this email — we read every one.')}</p>
    '''
    send_email(organizer.email,
               _subject(_('Welcome to YardHarvest Garden Management')),
               _render(content))


@in_recipient_language(lambda garden, organizer: organizer)
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
        tips += f'<p>{_("Getting started is easy — add your first plot in under a minute from the Garden Dashboard.")}</p>'
    if member_count == 0:
        garden_link = f'{site}/gardens/{garden.public_id}'
        tips += f'<p>{_("Your members can join by visiting your garden page:")} <a href="{garden_link}">{garden_link}</a></p>'

    days_left = max(_pro_pricing()['trial_days'] - 3, 0)
    content = f'''
    <h2>{_('How is %(garden)s coming along?', garden=_esc(garden.name))}</h2>
    <p>{_('Hi %(name)s,', name=name)}</p>
    <p>{_("You've been on YardHarvest for 3 days. Here's what you've set up so far:")}</p>
    <table class="detail-table">
      <tr><td>{_('Plots configured')}</td><td>{plot_count}</td></tr>
      <tr><td>{_('Members joined')}</td><td>{member_count}</td></tr>
      <tr><td>{_('Events scheduled')}</td><td>{event_count}</td></tr>
    </table>
    {tips}
    <p style="text-align:center;"><a class="btn" href="{site}/gardens/{garden.public_id}/admin">{_('Continue Setting Up')}</a></p>
    <p style="color:#6b6e76;">{ngettext('%(num)s day left in your trial.', '%(num)s days left in your trial.', days_left)}</p>
    '''
    send_email(organizer.email,
               _subject(_('How is %(garden)s coming along?', garden=garden.name)),
               _render(content))


@in_recipient_language(lambda garden, organizer: organizer)
def send_garden_trial_halfway(garden, organizer):
    """Day 7: Halfway — feature highlights."""
    site = _get_site_url()
    name = _esc(organizer.display_name or organizer.username)
    days_left = max(_pro_pricing()['trial_days'] - 7, 0)
    content = f'''
    <h2>{_("You're halfway through your trial")}</h2>
    <p>{_('Hi %(name)s,', name=name)}</p>
    <p>{_('One week in! Here are the Pro features that save organizers the most time:')}</p>
    <h3>{_('Financial Management')}</h3>
    <p>{_('Generate dues for every member in one click. Track expenses by category. Send payment reminders automatically.')}</p>
    <p style="text-align:center;"><a class="btn" href="{site}/gardens/{garden.public_id}/admin">{_('Try Financial Tools')}</a></p>
    <h3>{_('Volunteer Shifts')}</h3>
    <p>{_('Create workday shifts, track who shows up, and generate volunteer hour reports for grant applications.')}</p>
    <h3>{_('Broadcast Messaging')}</h3>
    <p>{_('Send announcements to every member via email and in-app notification — no more group text chains.')}</p>
    <p style="color:#6b6e76;">{ngettext('%(num)s day left in your trial.', '%(num)s days left in your trial.', days_left)}</p>
    '''
    send_email(organizer.email,
               _subject(_("You're halfway through your trial")),
               _render(content))


@in_recipient_language(lambda garden, organizer: organizer)
def send_garden_trial_expiring(garden, organizer):
    """Day 12: Trial expiring — 2 days left."""
    name = _esc(organizer.display_name or organizer.username)
    sub = garden.subscription
    trial_end = (format_date(sub.trial_end, format='long')
                 if sub and sub.trial_end else _('soon'))
    billing_url = _garden_billing_url(garden.id)
    pricing = _pro_pricing()
    monthly, yearly = _usd(pricing['monthly_cents']), _usd(pricing['yearly_cents'])
    savings_cents = pricing['monthly_cents'] * 12 - pricing['yearly_cents']
    save_txt = (f" {_('(save %(amount)s)', amount=_usd(savings_cents))}"
                if savings_cents > 0 else '')

    content = f'''
    <h2>{_('Your %(garden)s trial ends in 2 days', garden=_esc(garden.name))}</h2>
    <p>{_('Hi %(name)s,', name=name)}</p>
    <p>{_("Your Garden Pro trial ends on <strong>%(date)s</strong>. Here's what happens:", date=trial_end)}</p>
    <h3>{_('What you keep (free forever):')}</h3>
    <p>{_('Garden profile, member directory, plot assignments, announcements, harvest logging, basic dashboard.')}</p>
    <h3>{_('What locks on %(date)s:', date=trial_end)}</h3>
    <p>{_('Financial management (dues, expenses, reminders), volunteer shift scheduling, photo wall, broadcast messaging, custom email branding, plot grid editor, data export.')}</p>
    <p>{_("Your data is never deleted — it's all there when you're ready to subscribe.")}</p>
    <table class="detail-table">
      <tr><td>{_('Monthly')}</td><td><strong>{_('%(amount)s/month', amount=monthly)}</strong></td></tr>
      <tr><td>{_('Annual')}</td><td><strong>{_('%(amount)s/year', amount=yearly)}</strong>{save_txt}</td></tr>
    </table>
    <p style="text-align:center;"><a class="btn" href="{billing_url}">{_('Subscribe to Garden Pro')}</a></p>
    '''
    send_email(organizer.email,
               _subject(_('Your %(garden)s trial ends in 2 days', garden=garden.name)),
               _render(content))


@in_recipient_language(lambda garden, organizer: organizer)
def send_garden_trial_ended(garden, organizer):
    """Day 14: Trial ended."""
    name = _esc(organizer.display_name or organizer.username)
    billing_url = _garden_billing_url(garden.id)
    pricing = _pro_pricing()
    monthly, yearly = _usd(pricing['monthly_cents']), _usd(pricing['yearly_cents'])
    savings_cents = pricing['monthly_cents'] * 12 - pricing['yearly_cents']
    save_txt = ''
    if savings_cents > 0:
        save_txt = f' — save {_usd(savings_cents)}'
        months_free = savings_cents // pricing['monthly_cents'] if pricing['monthly_cents'] else 0
        if months_free >= 1:
            save_txt += f" (that's over {months_free} month{'s' if months_free != 1 else ''} free)"

    content = f'''
    <h2>{_('Your Garden Pro trial has ended')}</h2>
    <p>{_('Hi %(name)s,', name=name)}</p>
    <p>{_('Your %(days)s-day trial for <strong>%(garden)s</strong> has ended. Pro features are now locked, but your garden profile, plots, members, and all your data remain intact.', days=pricing['trial_days'], garden=_esc(garden.name))}</p>
    <p>{_('Ready to continue? Choose your plan:')}</p>
    <table class="detail-table">
      <tr><td>{_('Monthly')}</td><td><strong>{_('%(amount)s/month', amount=monthly)}</strong> — {_('flexible, cancel anytime')}</td></tr>
      <tr><td>{_('Annual')}</td><td><strong>{_('%(amount)s/year', amount=yearly)}</strong>{save_txt}</td></tr>
    </table>
    <p style="text-align:center;"><a class="btn" href="{billing_url}">{_('Subscribe Now')}</a></p>
    <p>{_("If you have questions about whether Garden Pro is right for your garden, reply to this email. We're happy to help.")}</p>
    '''
    send_email(organizer.email, _subject(_('Your Garden Pro trial has ended')),
               _render(content))


@in_recipient_language(lambda garden, organizer: organizer)
def send_garden_trial_reengagement(garden, organizer):
    """Day 21: Re-engagement — 1 week post-trial."""
    name = _esc(organizer.display_name or organizer.username)
    billing_url = _garden_billing_url(garden.id)
    pricing = _pro_pricing()
    yearly = _usd(pricing['yearly_cents'])
    yearly_per_month = _usd(round(pricing['yearly_cents'] / 12))

    from app.models import GardenPlot
    member_ids = set()
    for p in GardenPlot.query.filter_by(garden_id=garden.id).all():
        if p.assigned_to_id:
            member_ids.add(p.assigned_to_id)
    member_count = len(member_ids)

    # "0 members are waiting" is a subject that argues against subscribing —
    # never state the number when there isn't one.
    if member_count > 0:
        subject_line = ngettext('%(num)s member is waiting on %(garden)s',
                                '%(num)s members are waiting on %(garden)s',
                                member_count, garden=garden.name)
        headline = ngettext('%(num)s member is waiting on %(garden)s',
                            '%(num)s members are waiting on %(garden)s',
                            member_count, garden=_esc(garden.name))
        # Pluralised by the catalog rather than by appending an "s".
        members = ngettext('<strong>%(num)s member</strong>',
                           '<strong>%(num)s members</strong>', member_count)
        status_line = _('Your garden is still active — %(members)s have access '
                        'and are using the platform.', members=members)
    else:
        subject_line = _('%(garden)s is ready when you are', garden=garden.name)
        headline = _('%(garden)s is ready when you are', garden=_esc(garden.name))
        status_line = _('Your garden is still active, and everything you set '
                        'up is saved.')

    content = f'''
    <h2>{headline}</h2>
    <p>{_('Hi %(name)s,', name=name)}</p>
    <p>{_("It's been a week since your Garden Pro trial ended.")} {status_line}</p>
    <p>{_('The Pro features (dues management, volunteer tracking, messaging) would make your job as organizer a lot easier.')}</p>
    <table class="detail-table">
      <tr><td>{_('Annual')}</td><td><strong>{_('%(amount)s/year', amount=yearly)}</strong> — {_('works out to ~%(amount)s/month', amount=yearly_per_month)}</td></tr>
    </table>
    <p style="text-align:center;"><a class="btn" href="{billing_url}">{_('Reactivate Garden Pro')}</a></p>
    <p style="color:{BRAND_MUTED};font-size:13px;">{_("This is our last email about upgrading. We won't ask again — but the option is always there in your garden settings.")}</p>
    '''
    send_email(organizer.email, _subject(subject_line), _render(content))


@in_recipient_language(lambda garden, organizer: organizer)
def send_garden_payment_failed(garden, organizer):
    """Dunning email when payment fails."""
    name = _esc(organizer.display_name or organizer.username)
    billing_url = _garden_billing_url(garden.id)

    content = f'''
    <h2>{_('Action needed: payment failed')}</h2>
    <p>{_('Hi %(name)s,', name=name)}</p>
    <p>{_('We were not able to process your Garden Pro payment for <strong>%(garden)s</strong>. Your Pro features stay active for 7 days while you update your payment method.', garden=_esc(garden.name))}</p>
    <p style="text-align:center;"><a class="btn" href="{billing_url}">{_('Update Payment Method')}</a></p>
    <p>{_('If your payment is not updated within 7 days, your garden returns to the free plan. Your data will not be deleted.')}</p>
    '''
    send_email(organizer.email,
               _subject(_('Action needed: payment failed for %(garden)s', garden=garden.name)),
               _render(content))


@in_recipient_language(lambda garden, organizer: organizer)
def send_garden_subscription_cancelled(garden, organizer):
    """Confirmation email when subscription is cancelled."""
    name = _esc(organizer.display_name or organizer.username)
    sub = garden.subscription
    period_end = sub.current_period_end.strftime('%B %d, %Y') if sub and sub.current_period_end else 'the end of your billing period'

    content = f'''
    <h2>{_('Garden Pro cancelled for %(garden)s', garden=_esc(garden.name))}</h2>
    <p>{_('Hi %(name)s,', name=name)}</p>
    <p>{_('Your Garden Pro subscription for <strong>%(garden)s</strong> has been cancelled. You keep Pro access until <strong>%(date)s</strong>, then your garden returns to the free plan.', garden=_esc(garden.name), date=period_end)}</p>
    <p>{_('Your data (plots, members, financials, harvest logs) is never deleted. You can subscribe again at any time from your garden settings.')}</p>
    <p>{_('We would like to know what we could do better — reply to this email with any feedback.')}</p>
    '''
    send_email(organizer.email,
               _subject(_('Garden Pro cancelled for %(garden)s', garden=garden.name)),
               _render(content))


@in_recipient_language(lambda garden, organizer: organizer)
def send_garden_welcome(garden, organizer):
    """Day 0 of the GARDEN (not the trial): welcome the organizer on create.

    Mentions the free plan and that a Garden Pro trial is available from the
    billing page — it does NOT auto-start a trial.
    """
    site = _get_site_url()
    name = _esc(organizer.display_name or organizer.username)
    trial_days = _pro_pricing()['trial_days']
    billing_url = _garden_billing_url(garden.id)
    content = f'''
    <h2>{_('Welcome to YardHarvest')}</h2>
    <p>{_('Hi %(name)s,', name=name)}</p>
    <p>{_('<strong>%(garden)s</strong> is set up and live on YardHarvest.', garden=_esc(garden.name))}</p>
    <p>{_('You are on the free plan, which includes your garden profile, member directory, plot assignments, announcements, harvest logging, and the basic dashboard — free forever.')}</p>
    <p>{_('A few good first steps:')}</p>
    <ol>
      <li><strong>{_('Add your plots')}</strong> — {_('Set up your garden layout from the dashboard')}</li>
      <li><strong>{_('Invite your members')}</strong> — {_('Share your garden link so members can join')}</li>
    </ol>
    <p style="text-align:center;"><a class="btn" href="{site}/gardens/{garden.public_id}/admin">{_('Go to Garden Dashboard')}</a></p>
    <p>{_('When you are ready for more — dues collection, volunteer shifts, broadcast messaging, and the rest of Garden Pro — a free %(days)s-day trial is waiting on your <a href="%(url)s">billing page</a>. No card required.', days=trial_days, url=billing_url)}</p>
    <p>{_('Questions? Reply to this email — we read every one.')}</p>
    '''
    send_email(organizer.email,
               _subject(_('Welcome to YardHarvest — %(garden)s is live', garden=garden.name)),
               _render(content))


@in_recipient_language(lambda garden, organizer: organizer)
def send_garden_trial_nudge(garden, organizer):
    """Day 2 after garden creation with no trial started: invite them to it."""
    site = _get_site_url()
    name = _esc(organizer.display_name or organizer.username)
    trial_days = _pro_pricing()['trial_days']
    billing_url = _garden_billing_url(garden.id)
    garden_link = f'{site}/gardens/{garden.public_id}'
    content = f'''
    <h2>{_('Start your free %(days)s-day Garden Pro trial', days=trial_days)}</h2>
    <p>{_('Hi %(name)s,', name=name)}</p>
    <p>{_('<strong>%(garden)s</strong> has been on YardHarvest for a couple of days — a good moment to see what Garden Pro does for organizers.', garden=_esc(garden.name))}</p>
    <p>{_('The trial unlocks everything for %(days)s days: dues collection and financial tracking, volunteer shift scheduling, broadcast messaging, the photo wall, custom email branding, and data export. No card required, and everything you set up stays if you decide it is not for you.', days=trial_days)}</p>
    <p style="text-align:center;"><a class="btn" href="{billing_url}">{_('Start Your Free Trial')}</a></p>
    <p>{_('Prefer to keep it simple? The free plan is not going anywhere — your garden page is at <a href="%(url)s">%(url)s</a>.', url=garden_link)}</p>
    '''
    send_email(organizer.email,
               _subject(_('Start your free %(days)s-day Garden Pro trial', days=trial_days)),
               _render(content))


# ---------------------------------------------------------------------------
# Operator conversion pings (internal — to the platform operator, not users)
# ---------------------------------------------------------------------------

_OPERATOR_PING_LABELS = {
    'trial_started': 'Trial started',
    'paid': 'Paid subscription activated',
    'past_due': 'Payment past due',
}


def send_operator_conversion_ping(kind, garden, organizer, contact_id=None):
    """Short plain email to the operator on a conversion event.

    kind: 'trial_started' | 'paid' | 'past_due'. Recipient is
    OPERATOR_ALERT_EMAIL (falling back to CRM_FROM_EMAIL). Never raises into
    the calling request path — failures are logged and swallowed here.
    """
    try:
        to = (current_app.config.get('OPERATOR_ALERT_EMAIL')
              or current_app.config.get('CRM_FROM_EMAIL'))
        if not to or not garden:
            return False
        label = _OPERATOR_PING_LABELS.get(kind, kind)
        site = _get_site_url()

        org_name = ''
        org_email = ''
        if organizer:
            org_name = organizer.display_name or organizer.username or ''
            org_email = organizer.email or ''

        place = ', '.join(p for p in (garden.city, garden.state) if p)

        # CRM cross-link when this organizer is a known CRM contact.
        if contact_id is None and org_email:
            try:
                from sqlalchemy import func
                from app.crm.models import Contact
                contact = Contact.query.filter(
                    func.lower(Contact.email) == org_email.lower()).first()
                contact_id = contact.id if contact else None
            except Exception:
                contact_id = None

        lines = [
            f'<p><strong>{_esc(label)}</strong>: {_esc(garden.name)}</p>',
            f'<p>Organizer: {_esc(org_name)} &lt;{_esc(org_email)}&gt;</p>',
        ]
        if place:
            lines.append(f'<p>Location: {_esc(place)}</p>')
        lines.append(f'<p><a href="{site}/admin/gardens">Platform admin — gardens</a></p>')
        if contact_id:
            lines.append(f'<p><a href="{site}/crm/contacts/{contact_id}">CRM contact</a></p>')

        return send_email(to, f'[YardHarvest] {label}: {garden.name}', '\n'.join(lines))
    except Exception:
        log.exception('Operator conversion ping (%s) failed', kind)
        return False


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

    with force_locale(_recipient_language(user_email)):
        content = f'''
    <h2>{_("You've been assigned a plot!")}</h2>
    <p>{_('Hi %(name)s,', name=name)}</p>
    <p>{_('Great news — you have been assigned <strong>Plot %(plot)s</strong> at <strong>%(garden)s</strong>.', plot=_esc(plot_label), garden=_esc(garden_name))}</p>
    <p>{_("Here's what to do next:")}</p>
    <table class="detail-table">
      <tr><td>{_('Visit your garden page')}</td><td>{_('Check plot details, rules, and upcoming events')}</td></tr>
      <tr><td>{_('Meet your neighbors')}</td><td>{_('Introduce yourself to fellow gardeners')}</td></tr>
      <tr><td>{_('Plan your season')}</td><td>{_('Use the Planting Calendar for Zone 5b guidance')}</td></tr>
    </table>
    <p style="text-align:center;"><a class="btn" href="{garden_url}">{_('View Your Garden')}</a></p>
    '''
        send_email(user_email,
                   _subject(_('Plot assigned at %(garden)s', garden=garden_name)),
                   _render(content))


def send_plot_waitlisted_email(garden_name, user_email, user_name, position, garden_id=None):
    """Notify user they've been added to the waitlist."""
    name = _esc(user_name or 'Gardener')
    site_url = _get_site_url()
    garden_url = f'{site_url}/gardens/{_garden_path(garden_id)}' if garden_id else site_url

    with force_locale(_recipient_language(user_email)):
        content = f'''
    <h2>{_("You're on the waitlist")}</h2>
    <p>{_('Hi %(name)s,', name=name)}</p>
    <p>{_('You have been added to the waitlist for <strong>%(garden)s</strong>. Your position is <strong>#%(position)s</strong>.', garden=_esc(garden_name), position=position)}</p>
    <p>{_('We will let you know as soon as a plot becomes available. In the meantime, you can check garden events and announcements.')}</p>
    <p style="text-align:center;"><a class="btn" href="{garden_url}">{_('View Garden')}</a></p>
    '''
        send_email(user_email,
                   _subject(_('Waitlisted for %(garden)s', garden=garden_name)),
                   _render(content))


def send_dues_reminder_email(garden_name, user_email, user_name, amount, season_year, garden_id=None):
    """Remind a member that dues are outstanding."""
    name = _esc(user_name or 'Gardener')
    g = _esc(garden_name)
    site_url = _get_site_url()
    garden_url = f'{site_url}/gardens/{_garden_path(garden_id)}' if garden_id else site_url

    with force_locale(_recipient_language(user_email)):
        content = f'''
    <h2>{_('Dues reminder for %(garden)s', garden=g)}</h2>
    <p>{_('Hi %(name)s,', name=name)}</p>
    <p>{_('This is a friendly reminder that your <strong>%(year)s</strong> garden dues of <strong>$%(amount)s</strong> are outstanding for <strong>%(garden)s</strong>.', year=season_year, amount='%.2f' % amount, garden=g)}</p>
    <p>{_('You can pay online from your garden page — it only takes a moment.')}</p>
    <p style="text-align:center;"><a class="btn" href="{garden_url}">{_('Pay Dues Now')}</a></p>
    '''
        send_email(user_email,
                   _subject(_('Dues reminder: %(garden)s', garden=garden_name)),
                   _render(content))


def send_shift_reminder_email(garden_name, user_email, user_name, shift_title, shift_date, garden_id=None):
    """Remind a volunteer about an upcoming shift."""
    name = _esc(user_name or 'Gardener')
    g = _esc(garden_name)
    st = _esc(shift_title)
    site_url = _get_site_url()
    garden_url = f'{site_url}/gardens/{_garden_path(garden_id)}' if garden_id else site_url

    with force_locale(_recipient_language(user_email)):
        content = f'''
    <h2>{_('Upcoming shift at %(garden)s', garden=g)}</h2>
    <p>{_('Hi %(name)s,', name=name)}</p>
    <p>{_('Just a reminder — you are signed up for <strong>%(shift)s</strong> at <strong>%(garden)s</strong> on <strong>%(date)s</strong>.', shift=st, garden=g, date=_esc(shift_date))}</p>
    <p style="text-align:center;"><a class="btn" href="{garden_url}">{_('View Garden')}</a></p>
    '''
        send_email(user_email,
                   _subject(_('Shift reminder: %(shift)s', shift=shift_title)),
                   _render(content))


def send_email_change_verification(user, new_email, token):
    """Send the verification link to the NEW address. Transactional/security
    email — always sends regardless of notification toggles."""
    site_url = _get_site_url()
    verify_url = f'{site_url}/verify-email-change?token={token}'
    display = _esc(user.display_name or user.username)

    with force_locale(user):
        content = f'''
    <h2>{_('Verify your new email address')}</h2>
    <p>{_('Hi %(name)s,', name=display)}</p>
    <p>{_('A request was made to change the email on your YardHarvest account to <strong>%(email)s</strong>. Click the button below to confirm:', email=_esc(new_email))}</p>
    <p style="text-align: center;">
      <a class="btn" href="{verify_url}">{_('Verify Email Address')}</a>
    </p>
    <p style="font-size: 0.9em; color: #6b6e76;">
      {_("This link expires in 24 hours and can only be used once. Your account email will not change until you confirm. If you didn't request this, you can safely ignore this email.")}</p>
    '''
        send_email(new_email, _subject(_('Verify your new email address')),
                   _render(content))


def send_email_change_notice(user, new_email):
    """Security notice to the CURRENT address that a change was requested."""
    display = _esc(user.display_name or user.username)
    site_url = _get_site_url()

    with force_locale(user):
        content = f'''
    <h2>{_('Email change requested')}</h2>
    <p>{_('Hi %(name)s,', name=display)}</p>
    <p>{_('A request was made to change your YardHarvest account email to <strong>%(email)s</strong>. Nothing changes until that address is verified.', email=_esc(new_email))}</p>
    <p>{_('If this was not you, <a href="%(url)s">reset your password</a> immediately to secure your account.', url=f'{site_url}/forgot-password')}</p>
    '''
        send_email(user.email,
                   _subject(_('Email change requested on your account')),
                   _render(content))


def send_email_changed_confirmation(user, old_email):
    """Notify the OLD address that the account email has been changed."""
    display = _esc(user.display_name or user.username)
    site_url = _get_site_url()

    with force_locale(user):
        content = f'''
    <h2>{_('Your account email was changed')}</h2>
    <p>{_('Hi %(name)s,', name=display)}</p>
    <p>{_('The email on your YardHarvest account was changed from <strong>%(old)s</strong> to <strong>%(new)s</strong>.', old=_esc(old_email), new=_esc(user.email))}</p>
    <p>{_('If this was not you, <a href="%(url)s">reset your password</a> immediately and contact support.', url=f'{site_url}/forgot-password')}</p>
    '''
        send_email(old_email, _subject(_('Your account email was changed')),
                   _render(content))


def send_shift_signup_email(garden_name, user_email, user_name, shift_title, shift_date, garden_id=None):
    """Confirm to a volunteer that their shift signup was received."""
    name = _esc(user_name or 'Gardener')
    g = _esc(garden_name)
    st = _esc(shift_title)
    site_url = _get_site_url()
    garden_url = f'{site_url}/gardens/{_garden_path(garden_id)}' if garden_id else site_url

    with force_locale(_recipient_language(user_email)):
        content = f'''
    <h2>{_("You're signed up!")}</h2>
    <p>{_('Hi %(name)s,', name=name)}</p>
    <p>{_('You are confirmed for <strong>%(shift)s</strong> at <strong>%(garden)s</strong> on <strong>%(date)s</strong>.', shift=st, garden=g, date=_esc(shift_date))}</p>
    <p>{_("If your plans change, you can cancel your signup from the garden's events page.")}</p>
    <p style="text-align:center;"><a class="btn" href="{garden_url}">{_('View Garden')}</a></p>
    '''
        send_email(user_email,
                   _subject(_('Signed up: %(shift)s', shift=shift_title)),
                   _render(content))


def send_event_cancelled_email(garden_name, event_title, event_date, recipient_emails, garden_id=None):
    """Notify RSVP'd members/volunteers that a garden event was cancelled."""
    if not recipient_emails:
        return
    g = _esc(garden_name)
    et = _esc(event_title)
    site_url = _get_site_url()
    garden_url = f'{site_url}/gardens/{_garden_path(garden_id)}' if garden_id else site_url

    # One batch per language: a cancellation notice to thirty members cannot
    # be rendered once and still be in each of their languages.
    for language, group in _by_language(recipient_emails).items():
        with force_locale(language):
            when = (f" {_('on <strong>%(date)s</strong>', date=_esc(event_date))}"
                    if event_date else '')
            content = f'''
    <h2>{_('Event cancelled')}</h2>
    <p>{_('<strong>%(event)s</strong> at <strong>%(garden)s</strong>%(when)s has been cancelled.', event=et, garden=g, when=when)}</p>
    <p>{_('We are sorry for any inconvenience. Keep an eye on the garden page for upcoming events.')}</p>
    <p style="text-align:center;"><a class="btn" href="{garden_url}">{_('View Garden')}</a></p>
    '''
            send_email(group,
                       _subject(_('Cancelled: %(event)s at %(garden)s',
                                  event=event_title, garden=garden_name)),
                       _render(content))


def send_refund_confirmation_email(order, buyer_email, refund_amount, is_full):
    """Notify buyer that a refund has been issued."""
    config = _get_site_email_config()
    refund_type = 'Full' if is_full else 'Partial'
    site_url = _get_site_url()

    with force_locale(_recipient_language(buyer_email)):
        amount = '%.2f' % refund_amount
        heading = _('Full Refund Issued') if is_full else _('Partial Refund Issued')
        sentence = (
            _('A full refund of <strong>$%(amount)s</strong> has been issued for your order <strong>#%(order)s</strong>.', amount=amount, order=order.id)
            if is_full else
            _('A partial refund of <strong>$%(amount)s</strong> has been issued for your order <strong>#%(order)s</strong>.', amount=amount, order=order.id))
        subject = (_('Full refund for order #%(order)s', order=order.id) if is_full
                   else _('Partial refund for order #%(order)s', order=order.id))
        content = f'''
    <h2>{heading}</h2>
    <p>{sentence}</p>
    <table class="detail-table">
      <tr><td>{_('Order')}</td><td>#{order.id}</td></tr>
      <tr><td>{_('Original Total')}</td><td>${order.total_price:.2f}</td></tr>
      <tr><td>{_('Refund Amount')}</td><td>${refund_amount:.2f}</td></tr>
    </table>
    <p>{_('The refund will appear on your statement within 5-10 business days.')}</p>
    <p style="text-align:center;"><a class="btn" href="{site_url}/orders/{order.id}">{_('View Order')}</a></p>
    '''
        send_email(buyer_email, _subject(subject), _render(content))


# ---------------------------------------------------------------------------
# Booking page (Calendly-style scheduling → owner's calendar)
# ---------------------------------------------------------------------------
def _fmt_booking_time(start_utc_naive, tzname):
    """Render a naive-UTC instant as a friendly local string in *tzname*,
    e.g. "Tuesday, July 1, 2026 · 2:30 PM CDT"."""
    from datetime import timezone as _tz
    from zoneinfo import ZoneInfo
    try:
        tz = ZoneInfo(tzname or 'America/Chicago')
    except Exception:
        tz = ZoneInfo('America/Chicago')
    local = start_utc_naive.replace(tzinfo=_tz.utc).astimezone(tz)
    # %-d isn't portable (Windows); strip a leading zero manually.
    day = local.strftime('%A, %B %d, %Y').replace(' 0', ' ')
    clock = local.strftime('%I:%M %p %Z').lstrip('0')
    return f'{day} · {clock}'


def _booking_owner_email():
    try:
        return (current_app.config.get('CRM_FROM_EMAIL')
                or current_app.config.get('MAIL_DEFAULT_SENDER')
                or 'james@yardharvest.app')
    except Exception:
        return 'james@yardharvest.app'


def send_booking_confirmation(booking, owner_name=''):
    """Confirmation to the person who booked, with a manage/cancel link."""
    bt = booking.booking_type
    site_url = _get_site_url()
    when = _fmt_booking_time(booking.start_at, booking.invitee_timezone)
    manage_url = f'{site_url}/book/manage/{booking.public_id}'
    name = _esc(booking.invitee_name or 'there')
    loc = _esc(bt.location or '') if bt else ''
    host = _esc(owner_name or 'the host')
    loc_row = f'<tr><td>Location</td><td>{loc}</td></tr>' if loc else ''
    content = f'''
    <h2>You&#39;re booked!</h2>
    <p>Hi {name}, your meeting is confirmed.</p>
    <table class="detail-table">
      <tr><td>What</td><td>{_esc(bt.name) if bt else 'Meeting'}</td></tr>
      <tr><td>When</td><td>{when}</td></tr>
      <tr><td>Duration</td><td>{bt.duration_min if bt else ''} minutes</td></tr>
      {loc_row}
      <tr><td>With</td><td>{host}</td></tr>
    </table>
    <p style="text-align:center;"><a class="btn" href="{manage_url}">Reschedule or cancel</a></p>
    <p style="font-size:0.9em;color:#6b6e76;">Times are shown in your timezone
       ({_esc(booking.invitee_timezone or 'local time')}). Add it to your calendar
       — you may also receive a calendar invitation.</p>
    '''
    send_email(booking.invitee_email,
               _subject(f'Confirmed: {bt.name if bt else "meeting"} · {when}'),
               render_booking_email(content, owner_name=owner_name))


def send_booking_owner_notification(booking, owner_name=''):
    """Notify the owner that a new meeting was booked."""
    bt = booking.booking_type
    settings_tz = None
    try:
        from app.models import BookingSettings
        settings_tz = BookingSettings.get().timezone
    except Exception:
        settings_tz = 'America/Chicago'
    when = _fmt_booking_time(booking.start_at, settings_tz)
    notes = _esc(booking.notes or '').replace('\n', '<br>')
    notes_row = f'<tr><td>Notes</td><td>{notes}</td></tr>' if notes else ''
    phone_row = (f'<tr><td>Phone</td><td>{_esc(booking.invitee_phone)}</td></tr>'
                 if booking.invitee_phone else '')
    content = f'''
    <h2>New booking</h2>
    <table class="detail-table">
      <tr><td>What</td><td>{_esc(bt.name) if bt else 'Meeting'}</td></tr>
      <tr><td>When</td><td>{when} (your time)</td></tr>
      <tr><td>Who</td><td>{_esc(booking.invitee_name)} &lt;{_esc(booking.invitee_email)}&gt;</td></tr>
      {phone_row}
      {notes_row}
    </table>
    <p style="font-size:0.9em;color:#6b6e76;">This was booked through your YardHarvest scheduling page.</p>
    '''
    send_email(_booking_owner_email(),
               _subject(f'New booking: {booking.invitee_name} · {when}'),
               render_booking_email(content, owner_name=owner_name))


def send_booking_reminder(booking, owner_name=''):
    """24h-before reminder to the guest (and a short one to the owner)."""
    bt = booking.booking_type
    when = _fmt_booking_time(booking.start_at, booking.invitee_timezone)
    manage_url = f'{_get_site_url()}/book/manage/{booking.public_id}'
    name = _esc(booking.invitee_name or 'there')
    loc = _esc(bt.location or '') if bt else ''
    loc_row = f'<tr><td>Location</td><td>{loc}</td></tr>' if loc else ''
    content = f'''
    <h2>See you soon!</h2>
    <p>Hi {name}, a quick reminder about your upcoming meeting.</p>
    <table class="detail-table">
      <tr><td>What</td><td>{_esc(bt.name) if bt else 'Meeting'}</td></tr>
      <tr><td>When</td><td>{when}</td></tr>
      {loc_row}
      <tr><td>With</td><td>{_esc(owner_name or 'the host')}</td></tr>
    </table>
    <p style="text-align:center;"><a class="btn" href="{manage_url}">Reschedule or cancel</a></p>
    '''
    send_email(booking.invitee_email,
               _subject(f'Reminder: {bt.name if bt else "meeting"} · {when}'),
               render_booking_email(content, owner_name=owner_name))
    try:
        from app.models import BookingSettings
        tz = BookingSettings.get().timezone
    except Exception:
        tz = 'America/Chicago'
    when_owner = _fmt_booking_time(booking.start_at, tz)
    ocontent = f'''
    <h2>Meeting tomorrow</h2>
    <p><strong>{_esc(booking.invitee_name)}</strong> — {_esc(bt.name) if bt else 'meeting'}
       on <strong>{when_owner}</strong> (your time).</p>
    '''
    send_email(_booking_owner_email(),
               _subject(f'Reminder: {booking.invitee_name} · {when_owner}'),
               render_booking_email(ocontent, owner_name=owner_name))


def send_booking_cancellation(booking, owner_name='', notify_owner=True):
    """Tell both parties a booking was cancelled."""
    bt = booking.booking_type
    when_inv = _fmt_booking_time(booking.start_at, booking.invitee_timezone)
    content = f'''
    <h2>Booking cancelled</h2>
    <p>Your {_esc(bt.name) if bt else 'meeting'} on <strong>{when_inv}</strong> has been cancelled.</p>
    <p style="text-align:center;"><a class="btn" href="{_get_site_url()}/book">Book another time</a></p>
    '''
    send_email(booking.invitee_email,
               _subject(f'Cancelled: {bt.name if bt else "meeting"} · {when_inv}'),
               render_booking_email(content, owner_name=owner_name))
    if notify_owner:
        try:
            from app.models import BookingSettings
            tz = BookingSettings.get().timezone
        except Exception:
            tz = 'America/Chicago'
        when_owner = _fmt_booking_time(booking.start_at, tz)
        ocontent = f'''
        <h2>Booking cancelled</h2>
        <p><strong>{_esc(booking.invitee_name)}</strong> cancelled their
           {_esc(bt.name) if bt else 'meeting'} on <strong>{when_owner}</strong> (your time).</p>
        '''
        send_email(_booking_owner_email(),
                   _subject(f'Cancelled: {booking.invitee_name} · {when_owner}'),
                   render_booking_email(ocontent, owner_name=owner_name))
