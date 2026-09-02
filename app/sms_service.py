"""SMS notification service using Twilio.

Gracefully degrades when Twilio credentials are not configured (dev mode).
Env vars required for production:
  TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER
"""
import os
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


def send_sms(to, body):
    """Send an SMS message. Returns True on success, False on failure."""
    client = _get_client()
    if not client:
        log.debug('SMS DEV: message queued (%d chars)', len(body))
        return False
    try:
        client.messages.create(
            body=body,
            from_=_cred('TWILIO_PHONE_NUMBER', TWILIO_FROM),
            to=to,
        )
        return True
    except Exception as e:
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
