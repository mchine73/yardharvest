"""CRM-internal helpers: auth proxy, decorators, mail-merge, activity log, SMTP.

The CRM uses its own session-based auth (separate from YH's Flask-Login)
because the two systems have distinct user tables (``crm_user`` vs ``user``).
A ``current_user`` proxy mimics the Flask-Login interface so templates can
keep using ``current_user.is_authenticated`` / ``current_user.is_admin`` etc.
without changes.
"""
import functools
import os
import re
import uuid
from datetime import date, datetime

from flask import (current_app, flash, g, has_request_context, redirect,
                   request, session, url_for)
from werkzeug.utils import secure_filename

from app import db


# ---------------------------------------------------------------------------
# Session keys
# ---------------------------------------------------------------------------
SESSION_USER_KEY = '_crm_user_id'


# ---------------------------------------------------------------------------
# CRM "current user" proxy (Flask-Login-style interface)
# ---------------------------------------------------------------------------
class _CrmCurrentUser:
    """Lazy proxy that loads the CRM user for the current request.

    Cached per-request in ``flask.g.crm_user_cache`` so the DB is hit at most
    once per request even when templates reference ``current_user`` repeatedly.
    """

    def _load(self):
        if not has_request_context():
            return None
        cache = getattr(g, '_crm_user_cache', None)
        if cache is not None:
            return cache or None  # 0 / None sentinel both fall through
        uid = session.get(SESSION_USER_KEY)
        if not uid:
            g._crm_user_cache = 0
            return None
        # Local import — models import db from app, which imports back to here
        # via views; circular avoidance.
        from app.crm.models import CrmUser
        user = db.session.get(CrmUser, int(uid))
        g._crm_user_cache = user or 0
        return user

    # Flask-Login compatibility -------------------------------------------------
    @property
    def is_authenticated(self):
        return self._load() is not None

    @property
    def is_anonymous(self):
        return self._load() is None

    @property
    def is_active(self):
        return self._load() is not None

    def get_id(self):
        u = self._load()
        return str(u.id) if u else None

    # CrmUser passthrough -------------------------------------------------------
    @property
    def id(self):
        u = self._load()
        return u.id if u else None

    @property
    def username(self):
        u = self._load()
        return u.username if u else None

    @property
    def email(self):
        u = self._load()
        return u.email if u else None

    @property
    def role(self):
        u = self._load()
        return u.role if u else None

    @property
    def is_admin(self):
        u = self._load()
        return bool(u and u.is_admin)

    @property
    def can_edit(self):
        u = self._load()
        return bool(u and u.can_edit)

    def __bool__(self):
        return self._load() is not None


current_user = _CrmCurrentUser()


def login_crm_user(user):
    """Mark the given ``CrmUser`` as logged in for this session."""
    session[SESSION_USER_KEY] = user.id
    # Bust the per-request cache so a downstream `current_user` access reflects
    # the new identity within the same request.
    if has_request_context():
        g._crm_user_cache = user


def logout_crm_user():
    session.pop(SESSION_USER_KEY, None)
    if has_request_context():
        g._crm_user_cache = 0


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------
def crm_login_required(view):
    """Require a logged-in CRM user; redirect to /crm/login otherwise."""
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('crm.login', next=request.path))
        return view(*args, **kwargs)
    return wrapped


def crm_admin_required(view):
    """Require a logged-in CRM user with admin role."""
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('crm.login', next=request.path))
        if not current_user.is_admin:
            from flask import abort
            abort(403)
        return view(*args, **kwargs)
    return wrapped


# ---------------------------------------------------------------------------
# Mail merge
# ---------------------------------------------------------------------------
_MERGE_RE = re.compile(r'{{\s*([\w]+)\s*}}')


def merge_context(contact, deal=None):
    """Build the token->value map for a recipient."""
    company = contact.company if contact else None
    name = (contact.name if contact else '') or ''
    parts = name.split()
    sender = ''
    if has_request_context() and current_user.is_authenticated:
        sender = current_user.username
    return {
        'first_name': parts[0] if parts else '',
        'last_name': ' '.join(parts[1:]) if len(parts) > 1 else '',
        'contact_name': name,
        'email': (contact.email if contact else '') or '',
        'phone': (contact.phone if contact else '') or '',
        'company': company.name if company else '',
        'city': (company.city if company else '') or '',
        'state': (company.state if company else '') or '',
        'org_type': (company.org_type if company else '') or '',
        'website': (company.website if company else '') or '',
        'deal_title': deal.title if deal else '',
        'deal_amount': (f"${deal.amount:,.0f}" if deal and deal.amount else ''),
        'deal_stage': deal.stage if deal else '',
        'today': date.today().strftime('%B %d, %Y'),
        'sender_name': sender,
    }


def render_merge(text, contact, deal=None):
    """Replace {{token}} placeholders. Unknown tokens are left untouched."""
    if not text:
        return text or ''
    ctx = merge_context(contact, deal)

    def repl(m):
        key = m.group(1).strip().lower()
        return str(ctx.get(key, m.group(0)))
    return _MERGE_RE.sub(repl, text)


# ---------------------------------------------------------------------------
# Activity log
# ---------------------------------------------------------------------------
def current_user_id():
    return current_user.id if current_user.is_authenticated else None


def log_activity(kind, description, *, contact_id=None, company_id=None,
                 deal_id=None):
    """Record a timeline/audit entry and refresh the deal's activity clock.

    Caller commits.
    """
    from app.crm.models import Activity, Deal, _utcnow
    db.session.add(Activity(kind=kind, description=description,
                            contact_id=contact_id, company_id=company_id,
                            deal_id=deal_id, user_id=current_user_id()))
    if deal_id:
        deal = db.session.get(Deal, deal_id)
        if deal:
            deal.last_activity_at = _utcnow()


# ---------------------------------------------------------------------------
# Email sending — uses the shared YardHarvest mail backend.
# ---------------------------------------------------------------------------
def smtp_send(recipient, subject, body):
    """Attempt a real send; return True on success, False if logged-only.

    Routes through the YardHarvest ``email_service.send_email``, which sends via
    Zoho ZeptoMail's transactional API. ``send_email`` returns True only when
    ZeptoMail actually accepted the message, so the CRM can record "Email sent"
    vs "Email logged" accurately (no env-var guessing).

    Despite the legacy name, this no longer touches SMTP — it's an HTTPS API.
    """
    if not recipient:
        return False
    try:
        from flask import current_app
        from app.email_service import send_email, render_sales_email
        # CRM bodies may now be rich HTML (composer/templates/AI) or plain text.
        # render_sales_email sanitizes HTML (allowlist incl. <img>) or escapes
        # plain text, then wraps it in the branded lime/Onest email shell. The
        # sanitize step also neutralizes any HTML in merged contact/company
        # values, so we no longer hand-escape here.
        html_body = render_sales_email(body or '')
        # CRM mail always sends from the personal CRM identity, never the
        # platform no_reply / brand name — fall back hard even if the config
        # values are blank, so an unset/empty env var can't leak the defaults.
        crm_from = current_app.config.get('CRM_FROM_EMAIL') or 'james@yardharvest.app'
        crm_name = current_app.config.get('CRM_FROM_NAME') or 'James Goodman'
        # BCC the operator on every individual CRM email so they keep a copy of
        # all outbound mail. Configurable via CRM_BCC_EMAIL (set '' to disable);
        # _send_via_zeptomail drops it when it equals the direct recipient.
        bcc_addr = (current_app.config.get('CRM_BCC_EMAIL', crm_from) or '').strip()
        bcc = [bcc_addr] if bcc_addr else None
        return bool(send_email(recipient, subject, html_body,
                               from_email=crm_from, from_name=crm_name, bcc=bcc))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# File uploads (contact photos, CSV imports)
# ---------------------------------------------------------------------------
def crm_upload_folder():
    """Return (and ensure) the on-disk folder for CRM uploads."""
    base = current_app.config.get('UPLOAD_FOLDER', 'uploads')
    folder = os.path.join(base, 'crm')
    os.makedirs(folder, exist_ok=True)
    return folder


def save_image(file_storage):
    """Save an uploaded image with a unique name; return the stored filename."""
    if not file_storage or not file_storage.filename:
        return None
    ext = os.path.splitext(secure_filename(file_storage.filename))[1]
    filename = f"{uuid.uuid4().hex}{ext}"
    file_storage.save(os.path.join(crm_upload_folder(), filename))
    return filename
