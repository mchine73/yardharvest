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

# Permissions needed for Publish-to-Page + Page-inbox. Each is granted only
# after Meta App Review (see docs/integrations/facebook-setup.md).
SCOPES = [
    'pages_show_list',          # list the admin's Pages during connect
    'pages_read_engagement',    # read Page posts/comments
    'pages_manage_posts',       # publish to the Page feed
    'pages_messaging',          # send/receive Page (Messenger) messages
    'pages_manage_metadata',    # subscribe the Page to webhooks
    'pages_read_user_content',  # read user comments/messages on the Page
]


class FacebookError(Exception):
    """Raised when a Graph API call fails; message is safe to surface."""


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


def _post(path, params=None, data=None):
    try:
        r = requests.post(f'{GRAPH}{path}', params=params, data=data, timeout=TIMEOUT)
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
    """Subscribe the Page to the app's webhook for feed + message events."""
    return _post(f'/{page_id}/subscribed_apps', data={
        'subscribed_fields': 'feed,messages,messaging_postbacks',
        'access_token': page_token,
    })


# ---------------------------------------------------------------------------
# Publish to Page
# ---------------------------------------------------------------------------
def publish_post(page_id, page_token, message, link=None):
    """Publish a post to the Page feed. Returns the new post id."""
    payload = {'message': message, 'access_token': page_token}
    if link:
        payload['link'] = link
    data = _post(f'/{page_id}/feed', data=payload)
    return data.get('id')


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
