"""Zoho Calendar integration for the booking page.

All Zoho Calendar API calls flow through here. Mirrors the graceful-degrade
pattern of ``stripe_service``/``email_service``: if the OAuth credentials are
unset (or a call fails), bookings still save + email — they just don't sync to
the calendar. Nothing here raises into the request path except ``create_event``
(whose failure the caller records as ``zoho_sync_status='failed'`` and moves on).

Auth: server-side OAuth2. A long-lived refresh token (generated once by the
account owner at https://api-console.zoho.com) is exchanged on demand for a
1-hour access token. Scope: ``ZohoCalendar.event.ALL`` (event.READ also covers
the free/busy conflict check).

Quirk worth remembering: Zoho's create/list endpoints take the event/range
payload as a URL-encoded ``eventdata``/``range`` *query parameter*, not a JSON
body. Datetimes use the iso8601-basic format ``yyyyMMddTHHmmssZ`` (UTC).
"""
import logging
import time
from datetime import datetime, timezone

import requests
from flask import current_app

log = logging.getLogger(__name__)

_TIMEOUT = 15
# Cached access token per process: (token, expires_at_epoch).
_token_cache = {'token': None, 'exp': 0.0}


def _cfg(key, default=''):
    try:
        val = current_app.config.get(key)
        if val:
            return val
    except RuntimeError:
        pass  # no app context
    import os
    return os.environ.get(key, default)


def is_configured():
    """True when the three OAuth credentials are present. A calendar UID is
    additionally required to actually write events (see ``create_event``)."""
    return bool(_cfg('ZOHO_CLIENT_ID') and _cfg('ZOHO_CLIENT_SECRET')
                and _cfg('ZOHO_REFRESH_TOKEN'))


def has_calendar():
    return bool(_cfg('ZOHO_CALENDAR_UID'))


class ZohoCalendarError(RuntimeError):
    """Raised when a Zoho Calendar call fails (caller records + degrades)."""


# ---------------------------------------------------------------------------
# OAuth
# ---------------------------------------------------------------------------
def get_access_token(force=False):
    """Return a valid access token, refreshing via the refresh token as needed.

    Cached in-process until ~1 min before expiry. Raises ZohoCalendarError on
    an auth failure (bad/expired refresh token, wrong data center, etc.)."""
    now = time.time()
    if not force and _token_cache['token'] and _token_cache['exp'] - 60 > now:
        return _token_cache['token']
    if not is_configured():
        raise ZohoCalendarError('Zoho Calendar is not configured')

    url = f"{_cfg('ZOHO_ACCOUNTS_URL', 'https://accounts.zoho.com')}/oauth/v2/token"
    try:
        resp = requests.post(url, data={
            'refresh_token': _cfg('ZOHO_REFRESH_TOKEN'),
            'client_id': _cfg('ZOHO_CLIENT_ID'),
            'client_secret': _cfg('ZOHO_CLIENT_SECRET'),
            'grant_type': 'refresh_token',
        }, timeout=_TIMEOUT)
    except requests.RequestException as exc:
        raise ZohoCalendarError(f'token request failed: {exc}') from exc

    data = {}
    try:
        data = resp.json()
    except ValueError:
        pass
    token = data.get('access_token')
    if not token:
        # Zoho returns 200 with an "error" field on bad creds.
        raise ZohoCalendarError(
            f"token exchange failed (HTTP {resp.status_code}): "
            f"{data.get('error') or resp.text[:160]}")
    _token_cache['token'] = token
    _token_cache['exp'] = now + int(data.get('expires_in', 3600))
    return token


def _auth_headers():
    return {'Authorization': f'Zoho-oauthtoken {get_access_token()}'}


def auth_check():
    """Live credential probe for the health endpoint. Booleans + error text
    only — never the token or calendar names."""
    out = {'configured': is_configured(), 'calendar_uid_set': has_calendar(),
           'auth_ok': False, 'num_calendars': None, 'error': None}
    if not out['configured']:
        return out
    try:
        cals = list_calendars()
        out['auth_ok'] = True
        out['num_calendars'] = len(cals)
    except ZohoCalendarError as exc:
        out['error'] = str(exc)[:300]
    except Exception as exc:  # noqa: BLE001 — surface, don't crash the probe
        out['error'] = f'{type(exc).__name__}: {exc}'[:300]
    return out


# ---------------------------------------------------------------------------
# Calendar discovery / free-busy
# ---------------------------------------------------------------------------
def _api(path):
    return f"{_cfg('ZOHO_CALENDAR_API_URL', 'https://calendar.zoho.com/api/v1')}{path}"


def list_calendars():
    """Return [{'uid', 'name', 'is_default'}] for the account's calendars.

    Used by the admin setup screen so the owner can find their calendar UID."""
    try:
        resp = requests.get(_api('/calendars'), headers=_auth_headers(), timeout=_TIMEOUT)
    except requests.RequestException as exc:
        raise ZohoCalendarError(f'calendars request failed: {exc}') from exc
    if resp.status_code == 401:
        raise ZohoCalendarError('HTTP 401 — token rejected (check refresh token / data center)')
    if resp.status_code >= 400:
        raise ZohoCalendarError(f'calendars HTTP {resp.status_code}: {resp.text[:160]}')
    try:
        cals = resp.json().get('calendars', [])
    except ValueError:
        raise ZohoCalendarError('calendars response was not JSON')
    out = []
    for c in cals:
        out.append({
            'uid': c.get('uid') or c.get('caluid') or c.get('id'),
            'name': c.get('name') or c.get('calendarName') or '(unnamed)',
            'is_default': bool(c.get('isdefault') or c.get('is_default')),
        })
    return out


def _fmt(dt):
    """Format a UTC datetime as Zoho's iso8601-basic ``yyyyMMddTHHmmssZ``."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.strftime('%Y%m%dT%H%M%SZ')


def _parse_zoho_dt(s):
    """Parse a Zoho datetime string to a naive-UTC datetime (best-effort).

    Handles ``yyyyMMddTHHmmssZ``, ``yyyyMMddTHHmmss+hhmm`` and the all-day
    ``yyyyMMdd`` form. Returns None if unparseable."""
    if not s:
        return None
    s = s.strip()
    try:
        if len(s) == 8:  # all-day yyyyMMdd
            return datetime.strptime(s, '%Y%m%d')
        if s.endswith('Z'):
            return datetime.strptime(s, '%Y%m%dT%H%M%SZ')
        # offset form: yyyyMMddTHHmmss±hhmm
        base, sign = s[:15], s[15:16]
        if sign in ('+', '-') and len(s) >= 20:
            naive = datetime.strptime(base, '%Y%m%dT%H%M%S')
            oh, om = int(s[16:18]), int(s[18:20])
            from datetime import timedelta
            delta = timedelta(hours=oh, minutes=om)
            return naive - delta if sign == '+' else naive + delta
        return datetime.strptime(base, '%Y%m%dT%H%M%S')
    except (ValueError, IndexError):
        return None


def get_busy_intervals(start_utc, end_utc):
    """Return [(start_naive_utc, end_naive_utc)] of existing events in the window.

    Best-effort: returns [] (no blocking) if not configured or on any error, so
    a Zoho hiccup degrades to YardHarvest-only conflict checking rather than
    breaking availability."""
    if not (is_configured() and has_calendar()):
        return []
    uid = _cfg('ZOHO_CALENDAR_UID')
    import json
    rng = json.dumps({'start': _fmt(start_utc), 'end': _fmt(end_utc)})
    try:
        resp = requests.get(_api(f'/calendars/{uid}/events'),
                            headers=_auth_headers(), params={'range': rng},
                            timeout=_TIMEOUT)
        if resp.status_code >= 400:
            log.warning('[ZOHO] busy fetch HTTP %s: %s', resp.status_code, resp.text[:160])
            return []
        events = resp.json().get('events', [])
    except (requests.RequestException, ValueError) as exc:
        log.warning('[ZOHO] busy fetch failed: %s', exc)
        return []

    busy = []
    for ev in events:
        dt = ev.get('dateandtime') or {}
        s = _parse_zoho_dt(dt.get('start'))
        e = _parse_zoho_dt(dt.get('end'))
        if not s:
            continue
        if not e:
            e = s
        if ev.get('isallday') and len(str(dt.get('start') or '')) == 8:
            # All-day: block the whole UTC day window it covers.
            from datetime import timedelta
            e = max(e, s + timedelta(days=1))
        busy.append((s, e))
    return busy


# ---------------------------------------------------------------------------
# Event create / delete
# ---------------------------------------------------------------------------
def create_event(*, title, start_utc, end_utc, description='', location='',
                  attendee_email=None, attendee_name=None):
    """Create a calendar event and return its Zoho uid.

    Raises ZohoCalendarError on any failure (caller records 'failed')."""
    if not (is_configured() and has_calendar()):
        raise ZohoCalendarError('Zoho Calendar not configured (need creds + calendar UID)')
    import json
    uid = _cfg('ZOHO_CALENDAR_UID')
    eventdata = {
        'title': title[:255],
        'dateandtime': {'start': _fmt(start_utc), 'end': _fmt(end_utc), 'timezone': 'UTC'},
        'reminders': [{'action': 'email', 'minutes': 30}],
    }
    if description:
        eventdata['description'] = description[:9000]
    if location:
        eventdata['location'] = location[:255]
    if attendee_email:
        eventdata['attendees'] = [{'email': attendee_email}]

    try:
        resp = requests.post(_api(f'/calendars/{uid}/events'),
                             headers=_auth_headers(),
                             params={'eventdata': json.dumps(eventdata)},
                             timeout=_TIMEOUT)
    except requests.RequestException as exc:
        raise ZohoCalendarError(f'create request failed: {exc}') from exc
    if resp.status_code >= 400:
        raise ZohoCalendarError(f'create HTTP {resp.status_code}: {resp.text[:200]}')
    try:
        body = resp.json()
    except ValueError:
        raise ZohoCalendarError('create response was not JSON')
    # Response shape: {"events":[{"uid":"..."}]} (occasionally a bare object).
    events = body.get('events') or []
    if events and isinstance(events, list):
        ev_uid = events[0].get('uid')
        if ev_uid:
            return ev_uid
    ev_uid = body.get('uid')
    if ev_uid:
        return ev_uid
    raise ZohoCalendarError(f'create returned no event uid: {str(body)[:160]}')


def delete_event(event_uid):
    """Delete an event by uid. Best-effort — returns True on success, False
    otherwise (a cancel should still proceed even if the calendar delete fails)."""
    if not (event_uid and is_configured() and has_calendar()):
        return False
    uid = _cfg('ZOHO_CALENDAR_UID')
    try:
        resp = requests.delete(_api(f'/calendars/{uid}/events/{event_uid}'),
                               headers=_auth_headers(), timeout=_TIMEOUT)
        if resp.status_code < 400:
            return True
        log.warning('[ZOHO] delete HTTP %s: %s', resp.status_code, resp.text[:160])
    except requests.RequestException as exc:
        log.warning('[ZOHO] delete failed: %s', exc)
    return False
