"""APNs push delivery.

Same contract as stripe_service: a graceful no-op until the environment is
configured. Configuration is four variables:

  APNS_TEAM_ID      Apple Developer team (B8YCYXF76V)
  APNS_KEY_ID       the .p8 auth key's id
  APNS_PRIVATE_KEY  the .p8 PEM contents (newlines may be escaped as \\n)
  APNS_USE_SANDBOX  set truthy for Xcode-run (development) builds

APNS_BUNDLE_ID defaults to the shipping bundle id. Tokens are per-user
(User.device_token, one device each — last writer wins), registered by the
iOS app on sign-in.
"""
import logging
import os
import time

log = logging.getLogger(__name__)

_jwt_cache = {'token': None, 'iat': 0.0}


def is_configured():
    return bool(os.environ.get('APNS_TEAM_ID')
                and os.environ.get('APNS_KEY_ID')
                and os.environ.get('APNS_PRIVATE_KEY'))


def _provider_token():
    """ES256 provider JWT, cached for 40 minutes (Apple allows 20-60)."""
    import jwt
    now = time.time()
    if _jwt_cache['token'] and now - _jwt_cache['iat'] < 2400:
        return _jwt_cache['token']
    key = os.environ['APNS_PRIVATE_KEY'].replace('\\n', '\n')
    token = jwt.encode(
        {'iss': os.environ['APNS_TEAM_ID'], 'iat': int(now)},
        key, algorithm='ES256',
        headers={'kid': os.environ['APNS_KEY_ID']},
    )
    _jwt_cache.update(token=token, iat=now)
    return token


def send_push(user, title, body='', link='', garden_id=None, badge=None, ntype=''):
    """Best-effort APNs alert to one user. Returns True on 200.

    Never raises: push is a bonus channel and no caller should fail because
    Apple was slow. A permanently-dead token (Unregistered/BadDeviceToken)
    clears User.device_token WITHOUT committing — the caller's own commit
    (notify()'s contract) persists it alongside the notification row.
    """
    token = getattr(user, 'device_token', None)
    if not is_configured() or not token:
        return False
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
