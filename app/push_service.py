"""Push delivery: APNs for the iOS app, FCM for the Android app.

Same contract as stripe_service: a graceful no-op until the environment is
configured, and each platform is configured on its own.

APNs is four variables:

  APNS_TEAM_ID      Apple Developer team (B8YCYXF76V)
  APNS_KEY_ID       the .p8 auth key's id
  APNS_PRIVATE_KEY  the .p8 PEM contents (newlines may be escaped as \\n)
  APNS_USE_SANDBOX  set truthy for Xcode-run (development) builds

APNS_BUNDLE_ID defaults to the shipping bundle id.

FCM is one: FCM_SERVICE_ACCOUNT_JSON, the Firebase service-account key file's
contents (or FCM_SERVICE_ACCOUNT_FILE, a Render Secret File path holding it).
The project id comes from the key itself.

Tokens are per-user (User.device_token + User.device_platform, one device
each — last writer wins), registered by the apps on sign-in.
"""
import json
import logging
import os
import time

log = logging.getLogger(__name__)

_jwt_cache = {'token': None, 'iat': 0.0}
_fcm_cache = {'token': None, 'exp': 0.0}

FCM_SCOPE = 'https://www.googleapis.com/auth/firebase.messaging'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
# Must match PushManager.CHANNEL_ID in the Android app.
FCM_CHANNEL_ID = 'garden_updates'


def apns_configured():
    return bool(os.environ.get('APNS_TEAM_ID')
                and os.environ.get('APNS_KEY_ID')
                and (os.environ.get('APNS_PRIVATE_KEY')
                     or os.environ.get('APNS_PRIVATE_KEY_FILE')))


def fcm_configured():
    return bool(os.environ.get('FCM_SERVICE_ACCOUNT_JSON')
                or os.environ.get('FCM_SERVICE_ACCOUNT_FILE'))


def is_configured():
    """True when either platform can deliver."""
    return apns_configured() or fcm_configured()


def _load_private_key():
    """The .p8 contents, from APNS_PRIVATE_KEY or an APNS_PRIVATE_KEY_FILE
    (a Render Secret File path — those preserve multi-line values exactly).
    """
    path = os.environ.get('APNS_PRIVATE_KEY_FILE')
    if path and os.path.exists(path):
        with open(path) as f:
            return f.read()
    return os.environ.get('APNS_PRIVATE_KEY', '')


def _normalize_pem(raw):
    """Rebuild a valid PEM from however the key survived the paste.

    Env-var editors flatten multi-line values: newlines become spaces, or
    vanish, or arrive as literal backslash-n. All of those carry the same
    base64 payload, so extract it and rewrap at 64 columns rather than
    demanding a pixel-perfect paste. A bare base64 blob (someone copied
    only the middle) gets the PKCS#8 header put back on.
    """
    import re
    key = raw.strip().strip('"').strip("'")
    key = key.replace('\\n', '\n')
    if '-----BEGIN' not in key:
        body = re.sub(r'\s+', '', key)
        if not body:
            return key
        lines = [body[i:i + 64] for i in range(0, len(body), 64)]
        return ('-----BEGIN PRIVATE KEY-----\n'
                + '\n'.join(lines) + '\n-----END PRIVATE KEY-----\n')
    m = re.match(r'-----BEGIN ([A-Z ]+)-----(.*)-----END \1-----', key, re.S)
    if m:
        label = m.group(1)
        body = re.sub(r'\s+', '', m.group(2))
        lines = [body[i:i + 64] for i in range(0, len(body), 64)]
        return (f'-----BEGIN {label}-----\n'
                + '\n'.join(lines) + f'\n-----END {label}-----\n')
    return key


def _provider_token():
    """ES256 provider JWT, cached for 40 minutes (Apple allows 20-60)."""
    import jwt
    now = time.time()
    if _jwt_cache['token'] and now - _jwt_cache['iat'] < 2400:
        return _jwt_cache['token']
    key = _normalize_pem(_load_private_key())
    token = jwt.encode(
        {'iss': os.environ['APNS_TEAM_ID'], 'iat': int(now)},
        key, algorithm='ES256',
        headers={'kid': os.environ['APNS_KEY_ID']},
    )
    _jwt_cache.update(token=token, iat=now)
    return token


def _load_service_account():
    """The Firebase service-account key as a dict; raises if unusable."""
    path = os.environ.get('FCM_SERVICE_ACCOUNT_FILE')
    if path and os.path.exists(path):
        with open(path) as f:
            raw = f.read()
    else:
        raw = os.environ.get('FCM_SERVICE_ACCOUNT_JSON', '')
    info = json.loads(raw)
    missing = [k for k in ('project_id', 'client_email', 'private_key')
               if not info.get(k)]
    if missing:
        raise ValueError(f'service account key is missing {", ".join(missing)}')
    return info


def _fcm_assertion(info, now):
    """The RS256-signed JWT Google trades for an access token. Local only,
    so the health probe can prove the key parses without a network call."""
    import jwt
    headers = {'kid': info['private_key_id']} if info.get('private_key_id') else None
    return jwt.encode(
        {'iss': info['client_email'], 'scope': FCM_SCOPE,
         'aud': GOOGLE_TOKEN_URL, 'iat': int(now), 'exp': int(now) + 3600},
        _normalize_pem(info['private_key']), algorithm='RS256', headers=headers,
    )


def _fcm_access_token(info):
    """OAuth access token for FCM, cached until five minutes before expiry."""
    now = time.time()
    if _fcm_cache['token'] and now < _fcm_cache['exp'] - 300:
        return _fcm_cache['token']
    import httpx
    r = httpx.post(GOOGLE_TOKEN_URL, timeout=5.0, data={
        'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
        'assertion': _fcm_assertion(info, now),
    })
    r.raise_for_status()
    body = r.json()
    _fcm_cache.update(token=body['access_token'],
                      exp=now + int(body.get('expires_in', 3600)))
    return _fcm_cache['token']


def send_push(user, title, body='', link='', garden_id=None, badge=None, ntype=''):
    """Best-effort alert to one user's phone. Returns True on delivery.

    Never raises: push is a bonus channel and no caller should fail because
    Apple or Google was slow. A permanently-dead token clears
    User.device_token WITHOUT committing — the caller's own commit
    (notify()'s contract) persists it alongside the notification row.
    """
    token = getattr(user, 'device_token', None)
    if not token:
        return False
    if (getattr(user, 'device_platform', None) or 'ios') == 'android':
        if not fcm_configured():
            return False
        return _send_fcm(user, token, title, body, link, garden_id, badge, ntype)
    if not apns_configured():
        return False
    return _send_apns(user, token, title, body, link, garden_id, badge, ntype)


def _send_apns(user, token, title, body, link, garden_id, badge, ntype):
    try:
        import httpx
        host = ('https://api.sandbox.push.apple.com'
                if os.environ.get('APNS_USE_SANDBOX')
                else 'https://api.push.apple.com')
        topic = os.environ.get('APNS_BUNDLE_ID', 'app.yardharvest.manager')
        payload = {
            'aps': {'alert': {'title': title, 'body': body or ''},
                    'sound': 'default'},
            'link': link or '',
            'type': ntype or '',
        }
        if garden_id is not None:
            payload['garden_id'] = garden_id
        if badge is not None:
            payload['aps']['badge'] = int(badge)
        with httpx.Client(http2=True, timeout=5.0) as client:
            r = client.post(
                f'{host}/3/device/{token}',
                json=payload,
                headers={'authorization': f'bearer {_provider_token()}',
                         'apns-topic': topic,
                         'apns-push-type': 'alert',
                         'apns-priority': '10'},
            )
        if r.status_code == 200:
            return True
        reason = ''
        try:
            reason = (r.json() or {}).get('reason', '')
        except Exception:
            pass
        if reason in ('BadDeviceToken', 'Unregistered', 'DeviceTokenNotForTopic'):
            log.info('APNs token dead for user %s (%s); clearing', user.id, reason)
            user.device_token = None  # persisted by the caller's commit
        else:
            log.warning('APNs %s for user %s: %s', r.status_code, user.id, reason)
        return False
    except Exception:
        log.exception('APNs send failed for user %s', getattr(user, 'id', '?'))
        return False


def _fcm_error_code(response):
    """FCM's own error code (UNREGISTERED, …) from a v1 error body."""
    try:
        err = (response.json() or {}).get('error') or {}
    except Exception:
        return ''
    for detail in err.get('details') or []:
        if detail.get('errorCode'):
            return detail['errorCode']
    return err.get('status', '')


def _send_fcm(user, token, title, body, link, garden_id, badge, ntype):
    try:
        import httpx
        info = _load_service_account()
        # FCM data values must be strings. The app reads type/link/garden_id
        # from the tapped notification's extras, same keys as the APNs payload.
        data = {'type': ntype or '', 'link': link or ''}
        if garden_id is not None:
            data['garden_id'] = str(garden_id)
        notification = {'channel_id': FCM_CHANNEL_ID}
        if badge is not None:
            notification['notification_count'] = int(badge)
        message = {
            'token': token,
            'notification': {'title': title, 'body': body or ''},
            'data': data,
            'android': {'priority': 'HIGH', 'notification': notification},
        }
        r = httpx.post(
            f'https://fcm.googleapis.com/v1/projects/{info["project_id"]}/messages:send',
            json={'message': message}, timeout=5.0,
            headers={'authorization': f'Bearer {_fcm_access_token(info)}'},
        )
        if r.status_code == 200:
            return True
        code = _fcm_error_code(r)
        if code in ('UNREGISTERED', 'SENDER_ID_MISMATCH'):
            log.info('FCM token dead for user %s (%s); clearing', user.id, code)
            user.device_token = None  # persisted by the caller's commit
        else:
            if r.status_code == 401:
                _fcm_cache.update(token=None, exp=0.0)  # refetch next time
            log.warning('FCM %s for user %s: %s', r.status_code, user.id, code)
        return False
    except Exception:
        log.exception('FCM send failed for user %s', getattr(user, 'id', '?'))
        return False
