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
from app.crm import agent_service
from app.crm import facebook_service as fb
from app.crm.helpers import (crm_admin_required, crm_login_required,
                             current_user_id, log_activity)
from app.crm.models import (CrmFacebookAccount, CrmFacebookMessage,
                            CrmFacebookPost, ContentItem, _utcnow)

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


# ---------------------------------------------------------------------------
# Publish to Page (compose / AI draft / schedule / publish)
# ---------------------------------------------------------------------------
@crm_bp.route('/facebook/posts')
@crm_login_required
def facebook_posts():
    posts = (CrmFacebookPost.query
             .order_by(CrmFacebookPost.id.desc()).limit(100).all())
    return render_template('crm/facebook_posts.html',
                           posts=posts, account=_active_account())


@crm_bp.route('/facebook/compose', methods=['GET', 'POST'])
@crm_login_required
def facebook_compose():
    acct = _active_account()
    if request.method == 'POST':
        if not acct:
            flash('Connect a Facebook Page first.', 'warning')
            return redirect(url_for('crm.facebook_settings'))
        message = (request.form.get('message') or '').strip()
        link = (request.form.get('link') or '').strip()
        image_url = (request.form.get('image_url') or '').strip()
        action = request.form.get('action', 'publish')
        content_id = request.form.get('content_item_id', type=int)
        if not message:
            flash('Write a message for the post.', 'warning')
            return redirect(url_for('crm.facebook_compose'))
        when = None
        if action == 'schedule':
            when = _parse_dt(request.form.get('scheduled_for'))
            if not when:
                flash('Enter a valid schedule date/time.', 'warning')
                return redirect(url_for('crm.facebook_compose'))
        post = submit_post(message=message, link=link or None,
                           image_url=image_url or None, scheduled_for=when,
                           content_item_id=content_id or None,
                           created_by_id=current_user_id())
        db.session.commit()
        if post.status == 'scheduled':
            flash(f'Post scheduled for {post.scheduled_for:%b %d, %Y %H:%M} UTC.', 'success')
        elif post.status == 'published':
            flash('Posted to Facebook.', 'success')
        else:
            flash(f'Could not post: {post.error}', 'danger')
        return redirect(url_for('crm.facebook_posts'))

    # GET — optional prefill from a content-calendar item (?content_id=).
    prefill = {'message': '', 'link': '', 'content_item_id': ''}
    cid = request.args.get('content_id', type=int)
    if cid:
        item = db.session.get(ContentItem, cid)
        if item:
            prefill['message'] = item.body or item.title or ''
            prefill['content_item_id'] = item.id
    return render_template('crm/facebook_compose.html', account=acct,
                           prefill=prefill,
                           ai_configured=agent_service.is_configured())


@crm_bp.route('/facebook/ai-draft', methods=['POST'])
@crm_login_required
def facebook_ai_draft():
    if not agent_service.is_configured():
        return jsonify({'error': 'AI drafting is not configured.'}), 503
    purpose = ((request.get_json(silent=True) or {}).get('purpose') or '').strip()
    if not purpose:
        return jsonify({'error': 'Describe what the post should be about.'}), 400
    try:
        return jsonify(agent_service.draft_facebook_post(purpose))
    except agent_service.AgentError as exc:
        return jsonify({'error': str(exc)}), 502


@crm_bp.route('/facebook/posts/<int:post_id>/publish', methods=['POST'])
@crm_login_required
def facebook_publish_post(post_id):
    acct = _active_account()
    post = db.session.get(CrmFacebookPost, post_id)
    if not post:
        flash('Post not found.', 'warning')
        return redirect(url_for('crm.facebook_posts'))
    if not acct:
        flash('Connect a Facebook Page first.', 'warning')
        return redirect(url_for('crm.facebook_settings'))
    _publish_now(post, acct)
    db.session.commit()
    flash('Posted to Facebook.' if post.status == 'published'
          else f'Could not post: {post.error}',
          'success' if post.status == 'published' else 'danger')
    return redirect(url_for('crm.facebook_posts'))


@crm_bp.route('/facebook/posts/<int:post_id>/delete', methods=['POST'])
@crm_login_required
def facebook_delete_post(post_id):
    post = db.session.get(CrmFacebookPost, post_id)
    if post and post.status != 'published':
        db.session.delete(post)
        db.session.commit()
        flash('Post removed.', 'success')
    return redirect(url_for('crm.facebook_posts'))


def _fetch_image_head(url):
    """Fetch just enough of *url* to learn (status_code, content_type).
    Split out so tests can stub the network."""
    import requests
    r = requests.get(url, timeout=10, stream=True,
                     headers={'User-Agent': 'YardHarvest-ImageCheck/1.0'})
    try:
        return r.status_code, (r.headers.get('Content-Type') or '')
    finally:
        r.close()


def resolve_image_url(image_url):
    """Return a DIRECT, publicly fetchable image URL for Facebook (or None).

    Facebook downloads the photo itself and fails with the cryptic
    "Missing or invalid image file (code 324)" when it can't. Two local
    causes are handled here:
    - our own uploads hand out ``{SITE_URL}/media/<ref>``, which 301-redirects
      to the Cloudinary CDN — FB's fetcher is unreliable across redirect
      hops, so resolve to the final CDN URL before publishing;
    - pasted URLs may be a web PAGE (or broken/auth-gated) rather than a raw
      image — pre-flight them and raise fb.FacebookError with an actionable
      message NOW, instead of a 324 at publish (or worse, at cron time for
      scheduled posts).
    The pre-flight is skipped under TESTING (unit tests stub _fetch_image_head).
    """
    url = (image_url or '').strip()
    if not url:
        return None
    base = (current_app.config.get('SITE_URL') or '').rstrip('/')
    if url.startswith('/'):
        url = f'{base}{url}'                      # absolutize our own refs

    marker = '/media/'
    if marker in url and (not base or url.startswith(base)):
        ref = url.split(marker, 1)[1]
        from app import cloudinary_service
        if cloudinary_service.is_configured():
            direct = cloudinary_service.delivery_url(ref)
            if direct:
                url = direct                       # no redirect hop for FB

    if current_app.config.get('TESTING'):
        return url
    try:
        status, ctype = _fetch_image_head(url)
    except Exception as exc:
        raise fb.FacebookError(
            'Could not fetch the image to verify it '
            f'({exc.__class__.__name__}). Facebook must be able to download '
            'it publicly — upload the photo in the composer instead.')
    if status != 200 or not ctype.lower().startswith('image/'):
        raise fb.FacebookError(
            'The image URL is not a direct, publicly reachable image '
            f'(got HTTP {status}, type {ctype or "unknown"}). Upload the '
            'photo in the composer, or paste a direct image link '
            '(one that opens as a bare image in the browser).')
    return url


def _publish_now(post, acct):
    try:
        # Retrying a post that previously FAILED ON A TIMEOUT is ambiguous —
        # that request was sent, so it may have actually published. Check the
        # Page feed first so "Post now" on a failed post can't double-post.
        if (post.status == 'failed'
                and 'timed out' in (post.error or '').lower()):
            existing = fb.find_recent_post(
                acct.page_id, acct.page_access_token, post.message,
                window_minutes=24 * 60)
            if existing:
                post.fb_post_id = existing
                post.status = 'published'
                post.published_at = _utcnow()
                post.error = None
                log_activity('facebook',
                             'Recovered a timed-out Facebook post (it had '
                             'published successfully)')
                return
        post.fb_post_id = fb.publish_post(acct.page_id, acct.page_access_token,
                                          post.message, post.link or None,
                                          image_url=resolve_image_url(post.image_url))
        post.status = 'published'
        post.published_at = _utcnow()
        post.error = None
        log_activity('facebook',
                     'Published a Facebook photo post' if post.image_url
                     else 'Published a Facebook post')
    except fb.FacebookError as exc:
        post.status = 'failed'
        post.error = str(exc)[:400]


def submit_post(*, message, link=None, image_url=None, scheduled_for=None,
                content_item_id=None, created_by_id=None):
    """Create a CrmFacebookPost and either schedule it or publish it now.

    Shared by the compose form and by approving an agent ``facebook_post``
    proposal (the man-in-the-middle queue). Adds + flushes the row but leaves
    the COMMIT to the caller. Returns the post; inspect ``post.status``
    (scheduled / published / draft / failed) to message the user. When no Page
    is connected an immediate post is saved as a ``draft`` rather than failing,
    so it can be published from Posts once a Page is connected."""
    acct = _active_account()
    post = CrmFacebookPost(
        message=message, link=link or None, image_url=image_url or None,
        content_item_id=content_item_id or None, created_by_id=created_by_id)
    if scheduled_for:
        post.status = 'scheduled'
        post.scheduled_for = scheduled_for
        db.session.add(post)
        log_activity('facebook', 'Scheduled a Facebook post')
    else:
        db.session.add(post)
        db.session.flush()
        if acct:
            _publish_now(post, acct)
        else:
            post.status = 'draft'
            log_activity('facebook', 'Saved a Facebook post draft')
    return post


def _parse_dt(value):
    from datetime import datetime
    if not value:
        return None
    for fmt in ('%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M', '%Y-%m-%dT%H:%M:%S'):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def publish_scheduled_posts():
    """Publish scheduled posts whose time has arrived (called by the daily
    cron). Returns the count published. Scheduled times are treated as UTC."""
    acct = _active_account()
    if not acct or not fb.is_configured():
        return 0
    now = _utcnow()
    due = CrmFacebookPost.query.filter(
        CrmFacebookPost.status == 'scheduled',
        CrmFacebookPost.scheduled_for.isnot(None),
        CrmFacebookPost.scheduled_for <= now,
    ).all()
    published = 0
    for post in due:
        _publish_now(post, acct)
        if post.status == 'published':
            published += 1
    db.session.commit()
    return published


# ---------------------------------------------------------------------------
# Page inbox (Messenger)
# ---------------------------------------------------------------------------
@crm_bp.route('/facebook/inbox')
@crm_login_required
def facebook_inbox():
    msgs = (CrmFacebookMessage.query
            .order_by(CrmFacebookMessage.id.desc()).limit(500).all())
    threads = {}
    for m in msgs:
        threads.setdefault(m.sender_id or 'unknown', []).append(m)
    conversations = []
    for sender_id, items in threads.items():
        ordered = sorted(items, key=lambda x: x.id)
        conversations.append({
            'sender_id': sender_id,
            'name': next((i.sender_name for i in items if i.sender_name), sender_id),
            'messages': ordered,
            'last': ordered[-1],
        })
    conversations.sort(key=lambda c: c['last'].id, reverse=True)
    return render_template('crm/facebook_inbox.html',
                           account=_active_account(), conversations=conversations)


@crm_bp.route('/facebook/reply', methods=['POST'])
@crm_login_required
def facebook_reply():
    acct = _active_account()
    recipient = (request.form.get('sender_id') or '').strip()
    text = (request.form.get('text') or '').strip()
    if not acct:
        flash('Connect a Facebook Page first.', 'warning')
        return redirect(url_for('crm.facebook_settings'))
    if not recipient or not text:
        flash('Nothing to send.', 'warning')
        return redirect(url_for('crm.facebook_inbox'))
    try:
        fb.send_message(acct.page_id, acct.page_access_token, recipient, text)
        db.session.add(CrmFacebookMessage(
            sender_id=recipient, sender_name=recipient, direction='out',
            text=text, created_time=_utcnow()))
        db.session.commit()
        log_activity('facebook', 'Replied to a Facebook message')
        flash('Reply sent.', 'success')
    except fb.FacebookError as exc:
        flash(f'Could not send: {exc}', 'danger')
    return redirect(url_for('crm.facebook_inbox'))
