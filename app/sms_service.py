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


def _get_client():
    """Return Twilio client or None if not configured."""
    if not TWILIO_AVAILABLE:
        return None
    if not TWILIO_SID or not TWILIO_TOKEN or not TWILIO_FROM:
        return None
    return TwilioClient(TWILIO_SID, TWILIO_TOKEN)


def send_sms(to, body):
    """Send an SMS message. Returns True on success, False on failure."""
    client = _get_client()
    if not client:
        log.debug('SMS DEV: message queued (%d chars)', len(body))
        return False
    try:
        client.messages.create(
            body=body,
            from_=TWILIO_FROM,
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
