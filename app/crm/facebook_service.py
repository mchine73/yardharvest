"""Facebook (Meta) Graph API integration for the CRM.

Powers two CRM capabilities:
  * Publish to Page  — post/schedule CRM content to a connected Facebook Page.
  * Page inbox       — read/reply to the Page's Messenger conversations.

Configuration is via env (set in Render / .env):
  FACEBOOK_APP_ID, FACEBOOK_APP_SECRET   — your Meta Developer app credentials.
  FACEBOOK_WEBHOOK_VERIFY_TOKEN          — any random string; must match the
                                           value entered in the Meta webhook UI.

The connected **Page** and its long-lived access token are stored in the DB
(CrmFacebookAccount) after the admin completes the OAuth connect flow. All
calls degrade gracefully (return None / [] / raise FacebookError) when the app
isn't configured or no Page is connected, mirroring stripe_service /
agent_service. No secret values are ever returned to the browser.
"""
import hashlib
import hmac
import logging
import os

import requests

log = logging.getLogger(__name__)

GRAPH_VERSION = os.environ.get('FACEBOOK_GRAPH_VERSION', 'v21.0')
GRAPH = f'https://graph.facebook.com/{GRAPH_VERSION}'
OAUTH_DIALOG = f'https://www.facebook.com/{GRAPH_VERSION}/dialog/oauth'
TIMEOUT = 20

# Permissions needed for Publish-to-Page. The Messenger inbox needs
# `pages_messaging`, which Meta only grants through its separate Messaging use
# case — requesting it under the "Manage everything on your Page" use case makes
# the OAuth dialog reject the whole connect ("Invalid Scopes: pages_messaging").
# So it's omitted here; re-add it once the Messaging use case is configured.
# See docs/integrations/facebook-setup.md.
SCOPES = [
    'pages_show_list',          # list the admin's Pages during connect
    'pages_read_engagement',    # read Page posts/comments
    'pages_manage_posts',       # publish to the Page feed
    'pages_manage_metadata',    # subscribe the Page to webhooks
    'pages_read_user_content',  # read user comments on the Page
]


class FacebookError(Exception):
    """Raised when a Graph API call fails; message is safe to surface."""


class FacebookTimeout(FacebookError):
    """The request timed out. For WRITES this is ambiguous — the request was
    sent, so the post may or may not have landed; recover by checking the
    Page feed before retrying (see publish_post)."""


def is_configured():
    """True when the Meta app credentials are present."""
    return bool(os.environ.get('FACEBOOK_APP_ID')
                and os.environ.get('FACEBOOK_APP_SECRET'))


def app_id():
    return os.environ.get('FACEBOOK_APP_ID', '')


def _app_secret():
    return os.environ.get('FACEBOOK_APP_SECRET', '')


def webhook_verify_token():
    """Shared token used to verify the webhook subscription handshake."""
    return os.environ.get('FACEBOOK_WEBHOOK_VERIFY_TOKEN', '')


# ---------------------------------------------------------------------------
# OAuth connect flow
# ---------------------------------------------------------------------------
def oauth_url(redirect_uri, state):
    """Build the Facebook Login dialog URL the admin is sent to."""
    from urllib.parse import urlencode
    return OAUTH_DIALOG + '?' + urlencode({
        'client_id': app_id(),
        'redirect_uri': redirect_uri,
        'state': state,
        'scope': ','.join(SCOPES),
        'response_type': 'code',
    })


def _get(path, params):
    try:
        r = requests.get(f'{GRAPH}{path}', params=params, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise FacebookError(f'Network error talking to Facebook: {exc}')
    if r.status_code >= 400:
        raise FacebookError(_error_message(r))
    return r.json()


def _post(path, params=None, data=None, timeout=None):
    try:
        r = requests.post(f'{GRAPH}{path}', params=params, data=data,
                          timeout=timeout or TIMEOUT)
    except requests.Timeout as exc:
        raise FacebookTimeout(f'Facebook timed out: {exc}')
    except requests.RequestException as exc:
        raise FacebookError(f'Network error talking to Facebook: {exc}')
    if r.status_code >= 400:
        raise FacebookError(_error_message(r))
    return r.json()


def _error_message(resp):
    try:
        err = resp.json().get('error', {})
        msg = err.get('message') or resp.text
        code = err.get('code')
        return f'Facebook API error: {msg}' + (f' (code {code})' if code else '')
    except Exception:
        return f'Facebook API error (HTTP {resp.status_code})'


def exchange_code_for_user_token(code, redirect_uri):
    """Exchange an OAuth ``code`` for a (short-lived) user access token."""
    data = _get('/oauth/access_token', {
        'client_id': app_id(),
        'client_secret': _app_secret(),
        'redirect_uri': redirect_uri,
        'code': code,
    })
    return data.get('access_token')


def long_lived_user_token(short_token):
    """Upgrade a short-lived user token to a long-lived one (~60 days)."""
    data = _get('/oauth/access_token', {
        'grant_type': 'fb_exchange_token',
        'client_id': app_id(),
        'client_secret': _app_secret(),
        'fb_exchange_token': short_token,
    })
    return data.get('access_token')


def list_pages(user_token):
    """List Pages the user administers, each with its own access token.

    Page tokens derived from a long-lived user token are effectively
    long-lived, which is what we persist.
    """
    data = _get('/me/accounts', {
        'access_token': user_token,
        'fields': 'id,name,access_token,category',
    })
    return data.get('data', [])


def subscribe_page_webhook(page_id, page_token):
    """Subscribe the Page to the app's webhook. Only ``feed`` while messaging is
    off — the ``messages``/``messaging_postbacks`` fields require the
    pages_messaging permission (see SCOPES note). Re-add them with that scope."""
    return _post(f'/{page_id}/subscribed_apps', data={
        'subscribed_fields': 'feed',
        'access_token': page_token,
    })


# ---------------------------------------------------------------------------
# Publish to Page
# ---------------------------------------------------------------------------
# Publishing gets a longer budget than reads: photo posts make Facebook fetch
# the image from our CDN server-side, which routinely outlasts the 20s read
# timeout (observed in prod as "Read timed out. (read timeout=20)").
PUBLISH_TIMEOUT = 60


def find_recent_post(page_id, page_token, message, window_minutes=30):
    """Return the id of a recent Page post whose message starts with ours, or
    None. Used to disambiguate a publish TIMEOUT (the request was sent — the
    post may have landed) before retrying, so a retry can never double-post.
    Prefix-match because photo captions may have a link appended. Best-effort:
    returns None on any error."""
    target = (message or '').strip()[:100]
    if not target:
        return None
    try:
        data = _get(f'/{page_id}/feed', {
            'access_token': page_token,
            'fields': 'id,message,created_time', 'limit': 10})
    except FacebookError:
        return None
    from datetime import datetime, timezone, timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    for p in data.get('data', []):
        msg = (p.get('message') or '').strip()
        if not msg.startswith(target):
            continue
        created = p.get('created_time') or ''
        try:
            if datetime.strptime(created, '%Y-%m-%dT%H:%M:%S%z') < cutoff:
                continue
        except ValueError:
            pass  # unparseable timestamp — accept the match
        return p.get('id')
    return None


def _publish_once(page_id, page_token, message, link, image_url):
    if image_url:
        caption = message or ''
        if link and link not in caption:
            caption = (caption + '\n\n' + link).strip()
        data = _post(f'/{page_id}/photos',
                     data={'url': image_url, 'caption': caption,
                           'access_token': page_token},
                     timeout=PUBLISH_TIMEOUT)
        return data.get('post_id') or data.get('id')
    payload = {'message': message, 'access_token': page_token}
    if link:
        payload['link'] = link
    data = _post(f'/{page_id}/feed', data=payload, timeout=PUBLISH_TIMEOUT)
    return data.get('id')


def publish_post(page_id, page_token, message, link=None, image_url=None):
    """Publish a post to the Page. Returns the new Page post id.

    With ``image_url`` it publishes a PHOTO post via /{page_id}/photos (the
    photo's ``url`` + a ``caption``); the /photos response returns both a photo
    id and the ``post_id`` of the resulting Page story — we return the story id
    so it matches a normal feed post. A photo post can't carry a link preview
    card, so any ``link`` is appended to the caption as plain text. Without an
    image it's a normal /{page_id}/feed post (with an optional link preview).

    Timeout recovery: a timeout on a publish is ambiguous (the request was
    sent). We check the Page feed for the post; if it landed we return its id,
    otherwise we retry ONCE, and if that also times out we check again before
    giving up — so a timeout can never cause a duplicate post."""
    try:
        return _publish_once(page_id, page_token, message, link, image_url)
    except FacebookTimeout:
        existing = find_recent_post(page_id, page_token, message)
        if existing:
            return existing          # it landed — the timeout was on the reply
        try:
            return _publish_once(page_id, page_token, message, link, image_url)
        except FacebookTimeout:
            existing = find_recent_post(page_id, page_token, message)
            if existing:
                return existing
            raise FacebookError(
                'Facebook timed out twice while publishing. The post may still '
                'appear on the Page shortly — check before posting again.')


# ---------------------------------------------------------------------------
# Page inbox (Messenger conversations)
# ---------------------------------------------------------------------------
def list_conversations(page_id, page_token, limit=25):
    data = _get(f'/{page_id}/conversations', {
        'access_token': page_token,
        'fields': 'id,snippet,updated_time,unread_count,participants',
        'limit': limit,
    })
    return data.get('data', [])


def list_messages(conversation_id, page_token, limit=25):
    data = _get(f'/{conversation_id}/messages', {
        'access_token': page_token,
        'fields': 'id,message,from,created_time',
        'limit': limit,
    })
    return data.get('data', [])


def send_message(page_id, page_token, recipient_id, text):
    """Send a Messenger message from the Page to a user (PSID)."""
    import json as _json
    return _post(f'/{page_id}/messages', params={'access_token': page_token}, data={
        'recipient': _json.dumps({'id': recipient_id}),
        'messaging_type': 'RESPONSE',
        'message': _json.dumps({'text': text}),
    })


# ---------------------------------------------------------------------------
# Webhook helpers
# ---------------------------------------------------------------------------
def verify_webhook_challenge(mode, token, challenge):
    """Return the challenge string if the subscription handshake is valid."""
    expected = webhook_verify_token()
    if mode == 'subscribe' and expected and token == expected:
        return challenge
    return None


def verify_signature(payload_bytes, header_value):
    """Validate the X-Hub-Signature-256 header against the app secret.

    Returns True when valid. If no app secret is configured we can't verify, so
    return False (callers reject) — webhook events are only trusted when signed.
    """
    secret = _app_secret()
    if not secret or not header_value:
        return False
    if not header_value.startswith('sha256='):
        return False
    expected = hmac.new(secret.encode('utf-8'), payload_bytes,
                        hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header_value.split('=', 1)[1])
