"""Email notification service for YardHarvest.

Provides helper functions for sending branded HTML email notifications
for orders, messages, garden announcements, waitlist updates, and
subscription boxes.  All functions are wrapped in try/except so that
email failures never crash the calling API endpoint.

If MAIL_USERNAME is not configured (empty string), the service will
log the email details instead of attempting to send -- this keeps the
development experience smooth when SMTP credentials are not available.
"""
import logging
from flask import current_app, render_template_string
from flask_mail import Message

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Base HTML email template with YardHarvest branding
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
    .email-header { background-color: #2d6a2e; padding: 24px 32px; text-align: center; }
    .email-header h1 { color: #ffffff; margin: 0; font-size: 24px; font-weight: 700; letter-spacing: 0.5px; }
    .email-header p { color: #c8e6c9; margin: 4px 0 0; font-size: 13px; }
    .email-body { padding: 32px; line-height: 1.6; }
    .email-body h2 { color: #2d6a2e; margin-top: 0; }
    .email-body p { margin: 12px 0; }
    .btn { display: inline-block; background-color: #2d6a2e; color: #ffffff !important; text-decoration: none; padding: 12px 28px; border-radius: 6px; font-weight: 600; margin: 16px 0; }
    .btn:hover { background-color: #245523; }
    .detail-table { width: 100%; border-collapse: collapse; margin: 16px 0; }
    .detail-table td { padding: 8px 12px; border-bottom: 1px solid #e8e8e8; }
    .detail-table td:first-child { font-weight: 600; color: #555; width: 40%; }
    .email-footer { background-color: #f4f7f4; padding: 20px 32px; text-align: center; font-size: 12px; color: #888; }
    .email-footer a { color: #2d6a2e; text-decoration: none; }
    .priority-urgent { color: #c62828; font-weight: 700; }
    .priority-important { color: #e65100; font-weight: 600; }
  </style>
</head>
<body>
  <div class="email-wrapper">
    <div class="email-header">
      <h1>YardHarvest</h1>
      <p>Fresh from your neighbor's garden</p>
    </div>
    <div class="email-body">
      {{ content }}
    </div>
    <div class="email-footer">
      <p>
        <a href="{{ site_url }}">Visit YardHarvest</a>
      </p>
      <p>You received this email because you have an account on YardHarvest.<br>
         If you believe this was sent in error, please contact us.</p>
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


def _render(content_html):
    """Wrap *content_html* inside the branded base template."""
    return render_template_string(
        BASE_TEMPLATE,
        content=content_html,
        site_url=_get_site_url(),
    )


# ---------------------------------------------------------------------------
# 1. Order Confirmation (sent to buyer)
# ---------------------------------------------------------------------------

def send_order_confirmation(order, buyer_email):
    """Notify the buyer that their order has been placed successfully."""
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
        <tr style="border-bottom:2px solid #2d6a2e;">
          <th style="text-align:left;padding:8px;">Item</th>
          <th style="text-align:center;padding:8px;">Qty</th>
          <th style="text-align:right;padding:8px;">Price</th>
        </tr>
      </thead>
      <tbody>{items_html}</tbody>
    </table>
    <a href="{site}/orders" class="btn">View Your Orders</a>
    """
    send_email(buyer_email, f'YardHarvest - Order #{order.id} Confirmed', _render(content))


# ---------------------------------------------------------------------------
# 2. New Order Notification (sent to seller)
# ---------------------------------------------------------------------------

def send_new_order_notification(order, seller_email):
    """Notify the seller that a new order has been placed."""
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
    send_email(seller_email, f'YardHarvest - New Order #{order.id} from {buyer_name}', _render(content))


# ---------------------------------------------------------------------------
# 3. Order Status Update (sent to buyer)
# ---------------------------------------------------------------------------

def send_order_status_update(order, buyer_email, new_status):
    """Notify the buyer that their order status has changed."""
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
    send_email(buyer_email, f'YardHarvest - Order #{order.id} {label}', _render(content))


# ---------------------------------------------------------------------------
# 4. New Message Notification
# ---------------------------------------------------------------------------

def send_message_notification(sender_name, recipient_email, preview):
    """Notify a user that they have received a new message."""
    site = _get_site_url()
    # Truncate preview to a reasonable length
    short_preview = (preview[:120] + '...') if len(preview) > 120 else preview

    content = f"""
    <h2>New Message from {sender_name}</h2>
    <p>You have a new message on YardHarvest:</p>
    <blockquote style="border-left:4px solid #2d6a2e; padding:12px 16px; background:#f9faf9; margin:16px 0; border-radius:4px;">
      {short_preview}
    </blockquote>
    <a href="{site}/messages" class="btn">View Messages</a>
    """
    send_email(recipient_email, f'YardHarvest - New message from {sender_name}', _render(content))


# ---------------------------------------------------------------------------
# 5. Garden Announcement
# ---------------------------------------------------------------------------

def send_garden_announcement(garden_name, announcement_title, announcement_body,
                             priority, member_emails):
    """Notify garden members of a new announcement.

    Parameters
    ----------
    garden_name : str
    announcement_title : str
    announcement_body : str
    priority : str  -- 'normal', 'important', or 'urgent'
    member_emails : list[str]
    """
    if not member_emails:
        return

    site = _get_site_url()
    priority_class = ''
    priority_badge = ''
    if priority == 'urgent':
        priority_class = 'priority-urgent'
        priority_badge = '<span class="priority-urgent">[URGENT]</span> '
    elif priority == 'important':
        priority_class = 'priority-important'
        priority_badge = '<span class="priority-important">[IMPORTANT]</span> '

    content = f"""
    <h2>{priority_badge}New Announcement - {garden_name}</h2>
    <h3 class="{priority_class}">{announcement_title}</h3>
    <p>{announcement_body}</p>
    <a href="{site}/gardens" class="btn">View Garden</a>
    """
    subject = f'YardHarvest - {garden_name}: {announcement_title}'
    send_email(member_emails, subject, _render(content))


# ---------------------------------------------------------------------------
# 6. Waitlist Notification
# ---------------------------------------------------------------------------

def send_waitlist_notification(garden_name, user_email):
    """Notify a user that they have been added to a garden waitlist."""
    site = _get_site_url()

    content = f"""
    <h2>You're on the Waitlist!</h2>
    <p>You've been added to the waitlist for <strong>{garden_name}</strong>.</p>
    <p>We'll notify you as soon as a plot becomes available. In the meantime, feel free
       to explore the garden's events and community features.</p>
    <a href="{site}/gardens" class="btn">Browse Gardens</a>
    """
    send_email(user_email, f'YardHarvest - Waitlist Confirmation for {garden_name}', _render(content))


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
    site = _get_site_url()

    content = f"""
    <h2>Your Box is Ready!</h2>
    <p>A new box preview has been published for <strong>{plan_name}</strong>.</p>
    <p><strong>What's in the box:</strong></p>
    <blockquote style="border-left:4px solid #2d6a2e; padding:12px 16px; background:#f9faf9; margin:16px 0; border-radius:4px;">
      {box_details}
    </blockquote>
    <a href="{site}/subscriptions" class="btn">View Subscription</a>
    """
    send_email(subscriber_email, f'YardHarvest - New Box Preview for {plan_name}', _render(content))
