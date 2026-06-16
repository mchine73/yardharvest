"""CRM ↔ Facebook (Meta) integration views, registered on ``crm_bp``.

Slice 1: settings page + OAuth connect flow (admin connects a Page) + the
webhook receiver (handshake verify + signed message ingestion). Publishing and
the inbox UI build on this foundation.

Webhook lives under ``/crm/api/facebook/webhook`` so it's exempt from the CRM
login gate (``require_crm_login`` skips ``/crm/api/``); it's also CSRF-exempt
(Facebook can't send our token) and instead authenticated by the X-Hub
signature.
"""
import logging
import secrets
from datetime import datetime, timezone

from flask import (current_app, flash, jsonify, redirect, render_template,
                   request, session, url_for)

from app import csrf, db
from app.crm import crm_bp
from app.crm import facebook_service as fb
from app.crm.helpers import crm_admin_required, current_user_id, log_activity
from app.crm.models import CrmFacebookAccount, CrmFacebookMessage

log = logging.getLogger(__name__)

_STATE_KEY = '_fb_oauth_state'
_PAGES_KEY = '_fb_oauth_pages'


def _active_account():
    return (CrmFacebookAccount.query
            .filter_by(active=True).order_by(CrmFacebookAccount.id.desc()).first())


def _redirect_uri():
    # Absolute callback URL (prod host resolves to www.yardharvest.app).
    return url_for('crm.facebook_callback', _external=True)


# ---------------------------------------------------------------------------
# Settings page
# ---------------------------------------------------------------------------
@crm_bp.route('/facebook')
@crm_admin_required
def facebook_settings():
    return render_template(
        'crm/facebook.html',
        configured=fb.is_configured(),
        account=_active_account(),
        scopes=fb.SCOPES,
        webhook_url=url_for('crm.facebook_webhook', _external=True),
        webhook_token_set=bool(fb.webhook_verify_token()),
    )


# ---------------------------------------------------------------------------
# OAuth connect flow
# ---------------------------------------------------------------------------
@crm_bp.route('/facebook/connect')
@crm_admin_required
def facebook_connect():
    if not fb.is_configured():
        flash('Set FACEBOOK_APP_ID and FACEBOOK_APP_SECRET first (see the setup guide).', 'warning')
        return redirect(url_for('crm.facebook_settings'))
    state = secrets.token_urlsafe(24)
    session[_STATE_KEY] = state
    return redirect(fb.oauth_url(_redirect_uri(), state))


@crm_bp.route('/facebook/callback')
@crm_admin_required
def facebook_callback():
    if request.args.get('error'):
        flash(f"Facebook connection was cancelled: {request.args.get('error_description', request.args.get('error'))}", 'warning')
        return redirect(url_for('crm.facebook_settings'))
    # CSRF protection for the OAuth round-trip.
    if not request.args.get('state') or request.args.get('state') != session.pop(_STATE_KEY, None):
        flash('Facebook connection failed a security check (state mismatch). Please try again.', 'danger')
        return redirect(url_for('crm.facebook_settings'))
    code = request.args.get('code')
    if not code:
        flash('Facebook did not return an authorization code.', 'danger')
        return redirect(url_for('crm.facebook_settings'))
    try:
        user_token = fb.exchange_code_for_user_token(code, _redirect_uri())
        user_token = fb.long_lived_user_token(user_token) or user_token
        pages = fb.list_pages(user_token)
    except fb.FacebookError as exc:
        flash(str(exc), 'danger')
        return redirect(url_for('crm.facebook_settings'))
    if not pages:
        flash('No Facebook Pages found for this account. You must be an admin of a Page.', 'warning')
        return redirect(url_for('crm.facebook_settings'))
    # Stash the page list (incl. tokens) in the session briefly for selection.
    session[_PAGES_KEY] = {'user_token': user_token, 'pages': [
        {'id': p['id'], 'name': p.get('name', p['id']),
         'access_token': p.get('access_token', ''),
         'category': p.get('category', '')} for p in pages]}
    if len(pages) == 1:
        return _connect_page(pages[0]['id'])
    return render_template('crm/facebook_select_page.html',
                           pages=session[_PAGES_KEY]['pages'])


@crm_bp.route('/facebook/select-page', methods=['POST'])
@crm_admin_required
def facebook_select_page():
    page_id = (request.form.get('page_id') or '').strip()
    return _connect_page(page_id)


def _connect_page(page_id):
    stash = session.get(_PAGES_KEY) or {}
    page = next((p for p in stash.get('pages', []) if p['id'] == page_id), None)
    if not page or not page.get('access_token'):
        flash('That Page selection expired — please reconnect.', 'warning')
        return redirect(url_for('crm.facebook_settings'))

    # Replace any existing connection.
    CrmFacebookAccount.query.delete()
    acct = CrmFacebookAccount(
        page_id=page['id'], page_name=page['name'],
        page_access_token=page['access_token'],
        user_access_token=stash.get('user_token'),
        active=True, connected_by_id=current_user_id(),
    )
    db.session.add(acct)
    db.session.commit()
    session.pop(_PAGES_KEY, None)
    session.pop(_STATE_KEY, None)

    # Subscribe the Page to our webhook (best-effort; needs app review live).
    try:
        fb.subscribe_page_webhook(page['id'], page['access_token'])
    except fb.FacebookError as exc:
        log.warning('Page webhook subscribe failed: %s', exc)
        flash(f'Connected, but webhook subscription needs attention: {exc}', 'warning')
    log_activity('facebook', f'Connected Facebook Page "{page["name"]}"')
    flash(f'Connected Facebook Page: {page["name"]}', 'success')
    return redirect(url_for('crm.facebook_settings'))


@crm_bp.route('/facebook/disconnect', methods=['POST'])
@crm_admin_required
def facebook_disconnect():
    CrmFacebookAccount.query.delete()
    db.session.commit()
    log_activity('facebook', 'Disconnected Facebook Page')
    flash('Facebook Page disconnected.', 'success')
    return redirect(url_for('crm.facebook_settings'))


# ---------------------------------------------------------------------------
# Webhook (handshake verify + signed message ingestion)
# ---------------------------------------------------------------------------
@crm_bp.route('/api/facebook/webhook', methods=['GET', 'POST'])
@csrf.exempt
def facebook_webhook():
    if request.method == 'GET':
        challenge = fb.verify_webhook_challenge(
            request.args.get('hub.mode'),
            request.args.get('hub.verify_token'),
            request.args.get('hub.challenge'),
        )
        if challenge is not None:
            return challenge, 200
        return 'Verification failed', 403

    # POST: verify the signature before trusting anything.
    if not fb.verify_signature(request.get_data(),
                               request.headers.get('X-Hub-Signature-256', '')):
        log.warning('Facebook webhook signature verification failed')
        return 'invalid signature', 403

    payload = request.get_json(silent=True) or {}
    if payload.get('object') == 'page':
        for entry in payload.get('entry', []):
            for msg in entry.get('messaging', []):
                _ingest_messaging_event(msg)
    db.session.commit()
    return 'EVENT_RECEIVED', 200


def _ingest_messaging_event(event):
    """Persist an inbound Messenger message (skip our own echoes)."""
    m = event.get('message') or {}
    mid = m.get('mid')
    if not mid or m.get('is_echo'):
        return
    if CrmFacebookMessage.query.filter_by(fb_message_id=mid).first():
        return
    ts = event.get('timestamp')
    created = None
    if ts:
        created = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).replace(tzinfo=None)
    sender = (event.get('sender') or {}).get('id', '')
    db.session.add(CrmFacebookMessage(
        fb_message_id=mid, sender_id=sender, sender_name=sender,
        direction='in', text=m.get('text', ''), created_time=created,
    ))
