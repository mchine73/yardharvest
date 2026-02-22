"""Email notification service for YardHarvest.

Provides helper functions for sending branded HTML email notifications
for orders, messages, garden announcements, waitlist updates, and
subscription boxes.  All functions are wrapped in try/except so that
email failures never crash the calling API endpoint.

If MAIL_USERNAME is not configured (empty string), the service will
log the email details instead of attempting to send -- this keeps the
development experience smooth when SMTP credentials are not available.

Branding (logo, colors, tagline, footer) and per-email-type on/off
toggles are loaded from the SiteEmailConfig singleton.  Garden-specific
announcement overrides come from GardenEmailConfig.
"""
import logging
from flask import current_app, render_template_string
from flask_mail import Message

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dynamic base template (uses Jinja2 variables from config)
# ---------------------------------------------------------------------------

BASE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body { margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f4f7f4; color: #333; }
    .email-wrapper { max-width: 600px; margin: 0 auto; background: #ffffff; }
    .email-header { background-color: {{ header_color }}; padding: 24px 32px; text-align: center; }
    .email-header h1 { color: #ffffff; margin: 0; font-size: 24px; font-weight: 700; letter-spacing: 0.5px; }
    .email-header p { color: rgba(255,255,255,0.75); margin: 4px 0 0; font-size: 13px; }
    .email-header img { max-height: 48px; margin-bottom: 8px; }
    .email-body { padding: 32px; line-height: 1.6; }
    .email-body h2 { color: {{ header_color }}; margin-top: 0; }
    .email-body p { margin: 12px 0; }
    .btn { display: inline-block; background-color: {{ header_color }}; color: #ffffff !important; text-decoration: none; padding: 12px 28px; border-radius: 6px; font-weight: 600; margin: 16px 0; }
    .btn:hover { opacity: 0.9; }
    .detail-table { width: 100%; border-collapse: collapse; margin: 16px 0; }
    .detail-table td { padding: 8px 12px; border-bottom: 1px solid #e8e8e8; }
    .detail-table td:first-child { font-weight: 600; color: #555; width: 40%; }
    .email-footer { background-color: #f4f7f4; padding: 20px 32px; text-align: center; font-size: 12px; color: #888; }
    .email-footer a { color: {{ header_color }}; text-decoration: none; }
    .priority-urgent { color: #c62828; font-weight: 700; }
    .priority-important { color: #e65100; font-weight: 600; }
  </style>
</head>
<body>
  <div class="email-wrapper">
    <div class="email-header">
      {% if logo_url %}<img src="{{ logo_url }}" alt="{{ from_name }}">{% endif %}
      <h1>{{ from_name }}</h1>
      {% if tagline %}<p>{{ tagline }}</p>{% endif %}
    </div>
    <div class="email-body">
      {{ content }}
    </div>
    <div class="email-footer">
      <p>
        <a href="{{ site_url }}">Visit {{ from_name }}</a>
      </p>
      {% if footer_text %}
      <p>{{ footer_text }}</p>
      {% else %}
      <p>You received this email because you have an account on {{ from_name }}.<br>
         If you believe this was sent in error, please contact us.</p>
      {% endif %}
    </div>
  </div>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Site URL helper (default for development)
# ---------------------------------------------------------------------------

SITE_URL = 'http://localhost:5173'


def _get_site_url():
    """Return the frontend site URL from config or fallback."""
    return current_app.config.get('SITE_URL', SITE_URL)


# ---------------------------------------------------------------------------
# Config helpers — cached per-request
# ---------------------------------------------------------------------------

def _get_site_email_config():
    """Load the SiteEmailConfig singleton, creating defaults if missing."""
    from app.models import SiteEmailConfig
    from app import db
    config = SiteEmailConfig.query.first()
    if not config:
        config = SiteEmailConfig()
        db.session.add(config)
        db.session.commit()
    return config


def _get_garden_email_config(garden_id):
    """Load the GardenEmailConfig for a specific garden, or None."""
    from app.models import GardenEmailConfig
    return GardenEmailConfig.query.filter_by(garden_id=garden_id).first()


# ---------------------------------------------------------------------------
# Generic email sender
# ---------------------------------------------------------------------------

def send_email(to, subject, html_body):
    """Send an email via Flask-Mail.

    If MAIL_USERNAME is empty (no SMTP credentials configured), the email
    content is logged to the console instead of being sent.  This prevents
    crashes during local development.

    Parameters
    ----------
    to : str or list[str]
        Recipient email address(es).
    subject : str
        Email subject line.
    html_body : str
        Fully-rendered HTML body.
    """
    try:
        mail_username = current_app.config.get('MAIL_USERNAME', '')
        if not mail_username:
            # Development mode -- just log
            recipients = to if isinstance(to, list) else [to]
            log.info(
                '[EMAIL DEV] To: %s | Subject: %s | (HTML body omitted)',
                ', '.join(recipients), subject,
            )
            return

        from app import mail  # import here to avoid circular imports

        recipients = to if isinstance(to, list) else [to]
        msg = Message(
            subject=subject,
            recipients=recipients,
            html=html_body,
        )
        mail.send(msg)
        log.info('[EMAIL] Sent "%s" to %s', subject, ', '.join(recipients))
    except Exception:
        log.exception('[EMAIL ERROR] Failed to send "%s" to %s', subject, to)


def _render(content_html, config=None):
    """Wrap *content_html* inside the branded base template.

    Uses SiteEmailConfig for branding if *config* is not provided.
    """
    if config is None:
        try:
            config = _get_site_email_config()
        except Exception:
            config = None

    return render_template_string(
        BASE_TEMPLATE,
        content=content_html,
        site_url=_get_site_url(),
        header_color=getattr(config, 'header_color', '#2d6a2e') or '#2d6a2e',
        logo_url=getattr(config, 'logo_url', '') or '',
        tagline=getattr(config, 'tagline', "Fresh from your neighbor's garden") or '',
        from_name=getattr(config, 'from_name', 'YardHarvest') or 'YardHarvest',
        footer_text=getattr(config, 'footer_text', '') or '',
    )


def _subject(label, config=None):
    """Build a subject line with the configured prefix."""
    if config is None:
        try:
            config = _get_site_email_config()
        except Exception:
            config = None
    prefix = getattr(config, 'subject_prefix', 'YardHarvest') or 'YardHarvest'
    return f'{prefix} - {label}'


def preview_email(template_type, config=None):
    """Render a sample email for live preview in admin settings.

    Returns the full HTML string.
    """
    samples = {
        'order_confirmation': '<h2>Order Confirmed!</h2><p>Thanks for your order! Here\'s a summary:</p>'
            '<table class="detail-table"><tr><td>Order #</td><td>12345</td></tr>'
            '<tr><td>Seller</td><td>Green Thumb Sarah</td></tr>'
            '<tr><td>Fulfillment</td><td>Pickup</td></tr>'
            '<tr><td>Total</td><td><strong>$24.50</strong></td></tr></table>',
        'status_update': '<h2>Order #12345 - Accepted</h2>'
            '<p>Green Thumb Sarah has accepted your order and will prepare it for pickup.</p>',
        'message': '<h2>New Message from Green Thumb Sarah</h2>'
            '<p>You have a new message:</p>'
            '<blockquote style="border-left:4px solid #2d6a2e;padding:12px 16px;background:#f9faf9;margin:16px 0;border-radius:4px;">'
            'Hi! Your tomatoes are ready for pickup. Come by anytime after 3 PM today.</blockquote>',
        'announcement': '<h2>New Announcement - Sunrise Community Garden</h2>'
            '<h3>Spring Planting Day This Saturday!</h3>'
            '<p>Join us for our annual spring planting day. Bring your tools and enthusiasm!</p>',
    }
    content = samples.get(template_type, samples['order_confirmation'])
    return _render(content, config=config)


# ---------------------------------------------------------------------------
# 1. Order Confirmation (sent to buyer)
# ---------------------------------------------------------------------------

def send_order_confirmation(order, buyer_email):
    """Notify the buyer that their order has been placed successfully."""
    config = _get_site_email_config()
    if not config.enable_order_confirmation:
        return

    site = _get_site_url()
    items_html = ''
    for oi in order.items:
        title = oi.listing.title if oi.listing else 'Item'
        items_html += (
            f'<tr><td>{title}</td>'
            f'<td style="text-align:center">{oi.quantity}</td>'
            f'<td style="text-align:right">${oi.unit_price:.2f}</td></tr>'
        )

    content = f"""
    <h2>Order Confirmed!</h2>
    <p>Thanks for your order! Here's a summary:</p>
    <table class="detail-table">
      <tr><td>Order #</td><td>{order.id}</td></tr>
      <tr><td>Seller</td><td>{order.seller_user.display_name or order.seller_user.username}</td></tr>
      <tr><td>Fulfillment</td><td>{order.fulfillment_method.title()}</td></tr>
      <tr><td>Total</td><td><strong>${order.total_price:.2f}</strong></td></tr>
    </table>
    <table style="width:100%;border-collapse:collapse;margin:16px 0;">
      <thead>
        <tr style="border-bottom:2px solid {config.header_color};">
          <th style="text-align:left;padding:8px;">Item</th>
          <th style="text-align:center;padding:8px;">Qty</th>
          <th style="text-align:right;padding:8px;">Price</th>
        </tr>
      </thead>
      <tbody>{items_html}</tbody>
    </table>
    <a href="{site}/orders" class="btn">View Your Orders</a>
    """
    send_email(buyer_email, _subject(f'Order #{order.id} Confirmed', config), _render(content, config))


# ---------------------------------------------------------------------------
# 2. New Order Notification (sent to seller)
# ---------------------------------------------------------------------------

def send_new_order_notification(order, seller_email):
    """Notify the seller that a new order has been placed."""
    config = _get_site_email_config()
    if not config.enable_order_confirmation:
        return

    site = _get_site_url()
    buyer_name = order.buyer.display_name or order.buyer.username
    items_summary = ', '.join(
        f'{oi.quantity}x {oi.listing.title}' for oi in order.items if oi.listing
    )

    content = f"""
    <h2>New Order Received!</h2>
    <p>You have a new order from <strong>{buyer_name}</strong>.</p>
    <table class="detail-table">
      <tr><td>Order #</td><td>{order.id}</td></tr>
      <tr><td>Items</td><td>{items_summary}</td></tr>
      <tr><td>Fulfillment</td><td>{order.fulfillment_method.title()}</td></tr>
      <tr><td>Total</td><td><strong>${order.total_price:.2f}</strong></td></tr>
    </table>
    <a href="{site}/orders/selling" class="btn">View Seller Dashboard</a>
    """
    send_email(seller_email, _subject(f'New Order #{order.id} from {buyer_name}', config), _render(content, config))


# ---------------------------------------------------------------------------
# 3. Order Status Update (sent to buyer)
# ---------------------------------------------------------------------------

def send_order_status_update(order, buyer_email, new_status):
    """Notify the buyer that their order status has changed."""
    config = _get_site_email_config()
    if not config.enable_status_updates:
        return

    site = _get_site_url()
    status_labels = {
        'accepted': 'Accepted',
        'completed': 'Completed',
        'cancelled': 'Cancelled',
    }
    label = status_labels.get(new_status, new_status.title())
    seller_name = order.seller_user.display_name or order.seller_user.username

    status_messages = {
        'accepted': f'{seller_name} has accepted your order and will prepare it for {order.fulfillment_method}.',
        'completed': f'Your order with {seller_name} has been marked as completed. Enjoy your fresh produce!',
        'cancelled': f'Your order with {seller_name} has been cancelled.',
    }
    detail = status_messages.get(new_status, f'Your order status has been updated to {label}.')

    content = f"""
    <h2>Order #{order.id} - {label}</h2>
    <p>{detail}</p>
    <table class="detail-table">
      <tr><td>Order #</td><td>{order.id}</td></tr>
      <tr><td>Seller</td><td>{seller_name}</td></tr>
      <tr><td>Status</td><td><strong>{label}</strong></td></tr>
      <tr><td>Total</td><td>${order.total_price:.2f}</td></tr>
    </table>
    <a href="{site}/orders" class="btn">View Order Details</a>
    """
    send_email(buyer_email, _subject(f'Order #{order.id} {label}', config), _render(content, config))


# ---------------------------------------------------------------------------
# 4. New Message Notification
# ---------------------------------------------------------------------------

def send_message_notification(sender_name, recipient_email, preview):
    """Notify a user that they have received a new message."""
    config = _get_site_email_config()
    if not config.enable_messages:
        return

    site = _get_site_url()
    # Truncate preview to a reasonable length
    short_preview = (preview[:120] + '...') if len(preview) > 120 else preview

    content = f"""
    <h2>New Message from {sender_name}</h2>
    <p>You have a new message:</p>
    <blockquote style="border-left:4px solid {config.header_color}; padding:12px 16px; background:#f9faf9; margin:16px 0; border-radius:4px;">
      {short_preview}
    </blockquote>
    <a href="{site}/messages" class="btn">View Messages</a>
    """
    send_email(recipient_email, _subject(f'New message from {sender_name}', config), _render(content, config))


# ---------------------------------------------------------------------------
# 5. Garden Announcement
# ---------------------------------------------------------------------------

def send_garden_announcement(garden_name, announcement_title, announcement_body,
                             priority, member_emails, garden_id=None):
    """Notify garden members of a new announcement.

    Parameters
    ----------
    garden_name : str
    announcement_title : str
    announcement_body : str
    priority : str  -- 'normal', 'important', or 'urgent'
    member_emails : list[str]
    garden_id : int, optional -- for garden-specific email config
    """
    if not member_emails:
        return

    config = _get_site_email_config()
    if not config.enable_announcements:
        return

    # Load garden-specific overrides
    garden_config = _get_garden_email_config(garden_id) if garden_id else None

    site = _get_site_url()
    priority_class = ''
    priority_badge = ''
    accent = (garden_config.accent_color if garden_config and garden_config.accent_color
              else config.header_color)
    if priority == 'urgent':
        priority_class = 'priority-urgent'
        priority_badge = '<span class="priority-urgent">[URGENT]</span> '
    elif priority == 'important':
        priority_class = 'priority-important'
        priority_badge = '<span class="priority-important">[IMPORTANT]</span> '

    closing = ''
    if garden_config and garden_config.closing_text:
        closing = f'<p style="margin-top:24px;color:#666;font-style:italic;">{garden_config.closing_text}</p>'

    content = f"""
    <h2>{priority_badge}New Announcement - {garden_name}</h2>
    <h3 class="{priority_class}">{announcement_title}</h3>
    <p>{announcement_body}</p>
    {closing}
    <a href="{site}/gardens" class="btn">View Garden</a>
    """

    # Subject prefix: garden-specific if available, else site-wide
    prefix = (garden_config.subject_prefix if garden_config and garden_config.subject_prefix
              else config.subject_prefix or 'YardHarvest')
    subject = f'{prefix} - {garden_name}: {announcement_title}'
    send_email(member_emails, subject, _render(content, config))


# ---------------------------------------------------------------------------
# 6. Waitlist Notification
# ---------------------------------------------------------------------------

def send_waitlist_notification(garden_name, user_email):
    """Notify a user that they have been added to a garden waitlist."""
    config = _get_site_email_config()
    site = _get_site_url()

    content = f"""
    <h2>You're on the Waitlist!</h2>
    <p>You've been added to the waitlist for <strong>{garden_name}</strong>.</p>
    <p>We'll notify you as soon as a plot becomes available. In the meantime, feel free
       to explore the garden's events and community features.</p>
    <a href="{site}/gardens" class="btn">Browse Gardens</a>
    """
    send_email(user_email, _subject(f'Waitlist Confirmation for {garden_name}', config), _render(content, config))


# ---------------------------------------------------------------------------
# 7. Subscription Box Notification
# ---------------------------------------------------------------------------

def send_subscription_box_notification(plan_name, subscriber_email, box_details):
    """Notify a subscriber that a new box preview has been published.

    Parameters
    ----------
    plan_name : str
    subscriber_email : str
    box_details : str  -- description of what is in the box
    """
    config = _get_site_email_config()
    if not config.enable_subscription_boxes:
        return

    site = _get_site_url()

    content = f"""
    <h2>Your Box is Ready!</h2>
    <p>A new box preview has been published for <strong>{plan_name}</strong>.</p>
    <p><strong>What's in the box:</strong></p>
    <blockquote style="border-left:4px solid {config.header_color}; padding:12px 16px; background:#f9faf9; margin:16px 0; border-radius:4px;">
      {box_details}
    </blockquote>
    <a href="{site}/subscriptions" class="btn">View Subscription</a>
    """
    send_email(subscriber_email, _subject(f'New Box Preview for {plan_name}', config), _render(content, config))
