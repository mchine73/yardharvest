"""SMS notification service using Twilio.

Gracefully degrades when Twilio credentials are not configured (dev mode).
Env vars required for production:
  TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER
"""
import os
import re
import logging

log = logging.getLogger(__name__)

# Try to import Twilio; graceful fallback if not installed
try:
    from twilio.rest import Client as TwilioClient
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False

TWILIO_SID = os.environ.get('TWILIO_ACCOUNT_SID', '')
TWILIO_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', '')
TWILIO_FROM = os.environ.get('TWILIO_PHONE_NUMBER', '')


def is_configured():
    """True when Twilio is importable and all three credentials are present.
    Read from the live environment (not the import-time snapshot) so a freshly
    set env var is reflected without a process restart in dev."""
    return bool(
        TWILIO_AVAILABLE
        and os.environ.get('TWILIO_ACCOUNT_SID')
        and os.environ.get('TWILIO_AUTH_TOKEN')
        and os.environ.get('TWILIO_PHONE_NUMBER')
    )


# ---- Phone numbers --------------------------------------------------------

#: Twilio rejects anything that is not E.164, and its error for a badly shaped
#: number (21211) reads like a configuration fault rather than a data one. So
#: numbers are normalized where they are written AND again before a send: a
#: member who typed "402-555-1234" during signup would otherwise never receive
#: a message, and nothing in the product would say why.
_E164 = re.compile(r'^\+[1-9]\d{6,14}$')


def normalize_phone(raw):
    """Return the number in E.164 (+14025551234), or None if unreadable.

    A bare ten-digit number is assumed to be US, because that is who the
    product serves; anything international has to carry its own ``+`` and
    country code. Returning None rather than a guess is deliberate — a number
    we cannot read is better refused at the form, where someone can fix it,
    than stored and silently undeliverable forever.
    """
    if not raw:
        return None
    text = str(raw).strip()
    plus = text.startswith('+')
    digits = re.sub(r'\D', '', text)
    if not digits:
        return None

    if plus:
        candidate = '+' + digits
    elif len(digits) == 10:
        candidate = '+1' + digits
    elif len(digits) == 11 and digits.startswith('1'):
        candidate = '+' + digits
    else:
        return None
    return candidate if _E164.match(candidate) else None


#: Twilio error codes worth reacting to rather than merely logging.
STOP_REPLY = 21610       # the recipient replied STOP; carrier is blocking us
INVALID_NUMBER = 21211   # the 'to' number is not a valid E.164 number


def set_opt_in(phone, enabled):
    """Set sms_opt_in for whoever holds this number. Returns how many changed.

    Matching is on the normalized value rather than the stored string: a
    member whose number predates normalization is stored as they typed it, so
    a comparison against the E.164 form would miss them — and those are
    exactly the people an early STOP comes from. Only users with a phone are
    considered, a set small enough to scan.
    """
    from app import db
    from app.models import User

    target = normalize_phone(phone) or phone
    matched = [u for u in User.query.filter(User.phone_number.isnot(None),
                                            User.phone_number != '').all()
               if normalize_phone(u.phone_number) == target]
    changed = [u for u in matched if bool(u.sms_opt_in) != enabled]
    for user in changed:
        user.sms_opt_in = enabled
    if changed:
        db.session.commit()
    return len(changed)


def _honor_stop(phone):
    """Record that a recipient has opted out by replying STOP.

    Twilio blocks the message at the carrier and returns 21610, but nothing
    told YardHarvest, so ``sms_opt_in`` stayed true and every later send tried
    again. That is both a lie in the member's own preferences and, on a 10DLC
    number, the behaviour that gets a sender flagged.

    The same discipline the ZeptoMail webhook already applies to hard bounces,
    applied to SMS.
    """
    try:
        count = set_opt_in(phone, False)
        if count:
            log.info('SMS opt-out recorded for %d user(s) after a STOP reply',
                     count)
    except Exception:
        # Never let bookkeeping break the caller: the message is already
        # undeliverable, and losing the suppression is better than an
        # exception escaping a background notification thread.
        try:
            from app import db
            db.session.rollback()
        except Exception:
            pass
        log.exception('Could not record the SMS opt-out')


def _cred(name, fallback=''):
    """Read a credential, ignoring whitespace.

    A value pasted into a dashboard field arrives with a trailing newline
    often enough to be worth handling, and it is invisible: the variable is
    plainly set, and Twilio simply rejects it.
    """
    return (os.environ.get(name) or fallback or '').strip()


def auth_ok():
    """Real credential check: do the SID/token actually authenticate with
    Twilio? Fetches the account resource (no SMS sent, no cost) so it's safe to
    expose as an ops probe. Returns False on any failure (bad creds, missing
    package, network)."""
    return auth_detail()[0]


def auth_detail():
    """``(ok, error)`` — the same check, but saying why it failed.

    Returning a bare False was a dead end: credentials present, Twilio
    refusing them, and no way to tell a rotated token from an API Key SID
    pasted where the Account SID belongs. Twilio's own error names it. The
    message never contains the token — it is the same reasoning that makes
    /api/health/stripe safe to expose.
    """
    if not is_configured():
        return False, 'not configured'
    try:
        client = _get_client()
        if not client:
            return False, 'twilio client could not be constructed'
        client.api.accounts(_cred('TWILIO_ACCOUNT_SID', TWILIO_SID)).fetch()
        return True, None
    except Exception as exc:
        return False, ('%s: %s' % (type(exc).__name__, exc))[:300]


def _get_client():
    """Return Twilio client or None if not configured."""
    if not TWILIO_AVAILABLE:
        return None
    sid = _cred('TWILIO_ACCOUNT_SID', TWILIO_SID)
    token = _cred('TWILIO_AUTH_TOKEN', TWILIO_TOKEN)
    if not sid or not token or not _cred('TWILIO_PHONE_NUMBER', TWILIO_FROM):
        return None
    return TwilioClient(sid, token)


def _may_text(number):
    """``(allowed, reason)`` — has the holder of this number agreed to texts?

    Consent is already checked at every call site, and this does not replace
    that: a caller that knows the recipient should still decide before doing
    the work of composing a message. This is the backstop. Fourteen call sites
    each repeating ``sms_opt_in and phone_number`` is the shape that has
    drifted in this codebase five times, and consent is a worse thing to drift
    on than a price — the cost of the last check being missed is a text to
    someone who said no, on a number whose 10DLC registration depends on not
    doing that.

    Fails closed. A number belonging to no user is refused rather than assumed
    fine: every real send goes to a member, so no match means either a bug or
    a deliberate send that should say so with ``require_opt_in=False``.
    """
    from app.models import User

    holders = [u for u in User.query.filter(User.phone_number.isnot(None),
                                            User.phone_number != '').all()
               if normalize_phone(u.phone_number) == number]
    if not holders:
        return False, 'no member holds that number'
    if not any(u.sms_opt_in for u in holders):
        return False, 'the member has not opted in to SMS'
    return True, None


def send_sms(to, body, require_opt_in=True):
    """Send an SMS message. Returns True on success, False on failure.

    ``require_opt_in=False`` is for sends that are not to a member acting on
    their own preferences — the platform admin's test message to a number they
    typed themselves. Everything else leaves it on.
    """
    client = _get_client()
    if not client:
        log.debug('SMS DEV: message queued (%d chars)', len(body))
        return False

    # Normalize here as well as at every write point. Numbers stored before
    # this existed are still in whatever shape their owner typed, and Twilio
    # answers those with an error that reads like a configuration fault.
    number = normalize_phone(to)
    if not number:
        log.warning('SMS not sent: %r is not a usable phone number', to)
        return False

    if require_opt_in:
        try:
            allowed, reason = _may_text(number)
        except Exception:
            # If consent cannot be checked, it has not been established.
            # Refusing is the safe direction, and raising out of a background
            # notification thread would be worse than a missed message.
            log.exception('Could not check SMS consent for %s; not sending',
                          number)
            allowed, reason = False, 'consent could not be checked'
        if not allowed:
            # Warning, not debug: a legitimate notification blocked here is a
            # caller passing the wrong number, and a silent skip would be
            # indistinguishable from a delivery that simply never arrived.
            log.warning('SMS not sent to %s — %s', number, reason)
            return False

    try:
        client.messages.create(
            body=body,
            from_=_cred('TWILIO_PHONE_NUMBER', TWILIO_FROM),
            to=number,
        )
        return True
    except Exception as e:
        code = getattr(e, 'code', None)
        if code == STOP_REPLY:
            _honor_stop(number)
            log.info('SMS blocked: recipient has replied STOP; opt-in cleared')
        elif code == INVALID_NUMBER:
            log.error('SMS rejected: Twilio will not accept %s as a '
                      'destination', number)
        else:
            log.error('SMS send failed: %s', e)
        return False


def _is_sms_enabled(toggle_name):
    """Check if a specific SMS toggle is enabled in SiteEmailConfig."""
    try:
        from app.models import SiteEmailConfig
        config = SiteEmailConfig.query.first()
        if not config:
            return False
        return getattr(config, toggle_name, False)
    except Exception:
        return False


def send_order_sms(order, phone):
    """Send order confirmation SMS to buyer."""
    if not _is_sms_enabled('enable_sms_order_confirmation'):
        return
    if not phone:
        return
    body = (
        f"YardHarvest: Your order #{order.id} has been placed! "
        f"Total: ${order.total_price:.2f}. "
        f"Your seller will be in touch soon."
    )
    send_sms(phone, body)


def send_status_sms(order, phone, new_status):
    """Send order status update SMS."""
    if not _is_sms_enabled('enable_sms_status_updates'):
        return
    if not phone:
        return
    status_labels = {
        'accepted': 'has been accepted by your seller',
        'completed': 'is ready for pickup/delivery',
        'cancelled': 'has been cancelled',
    }
    label = status_labels.get(new_status, f'status changed to {new_status}')
    body = f"YardHarvest: Order #{order.id} {label}."
    send_sms(phone, body)


def send_message_notification_sms(phone, sender_name):
    """Send new message alert SMS."""
    if not _is_sms_enabled('enable_sms_messages'):
        return
    if not phone:
        return
    body = f"YardHarvest: You have a new message from {sender_name}. Log in to read it."
    send_sms(phone, body)


def send_harvest_sms(phone, category):
    """Send harvest alert SMS to subscribed user."""
    if not _is_sms_enabled('enable_sms_harvest_notifications'):
        return
    if not phone:
        return
    body = (
        f"YardHarvest: {category} harvests are coming in! "
        f"Check the Harvest Forecast to connect with growers."
    )
    send_sms(phone, body)


def send_garden_trial_expiring_sms(phone, garden_name, billing_url):
    """Day 12: SMS reminder that Garden Pro trial ends in 2 days."""
    if not phone:
        return
    body = (
        f"YardHarvest: Your Garden Pro trial for {garden_name} ends in 2 days. "
        f"Subscribe to keep financial tools, volunteer tracking, and more: {billing_url}"
    )
    send_sms(phone, body)


def send_garden_trial_ended_sms(phone, garden_name, billing_url):
    """Day 14: SMS notification that Garden Pro trial has ended."""
    if not phone:
        return
    body = (
        f"YardHarvest: Your Garden Pro trial has ended. "
        f"Your data is safe. Subscribe anytime to unlock all features: {billing_url}"
    )
    send_sms(phone, body)


def send_plot_assigned_sms(phone, garden_name, plot_label):
    """Notify user via SMS that they've been assigned a garden plot."""
    if not phone:
        return
    body = f"YardHarvest: You've been assigned Plot {plot_label} at {garden_name}! Log in to view your garden."
    send_sms(phone, body)


def send_dues_reminder_sms(phone, garden_name, amount):
    """SMS reminder for outstanding garden dues."""
    if not phone:
        return
    body = f"YardHarvest: Friendly reminder — your {garden_name} dues of ${amount:.2f} are outstanding. Pay online from your garden page."
    send_sms(phone, body)


def send_shift_reminder_sms(phone, garden_name, shift_title, shift_date):
    """SMS reminder for upcoming volunteer shift."""
    if not phone:
        return
    body = f"YardHarvest: Reminder — you're signed up for {shift_title} at {garden_name} on {shift_date}."
    send_sms(phone, body)


def send_refund_sms(phone, order_id, refund_amount):
    """SMS notification that a refund has been issued."""
    if not phone:
        return
    body = f"YardHarvest: A refund of ${refund_amount:.2f} has been issued for order #{order_id}. It will appear on your statement within 5-10 business days."
    send_sms(phone, body)


def send_announcement_sms(phone, garden_name, title):
    """SMS notification for garden announcements."""
    if not _is_sms_enabled('enable_sms_messages'):
        return
    if not phone:
        return
    body = f"YardHarvest: New announcement from {garden_name}: {title[:80]}. Log in to read more."
    send_sms(phone, body)
