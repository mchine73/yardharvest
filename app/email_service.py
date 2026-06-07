"""Email notification service for YardHarvest.

Provides helper functions for sending branded HTML email notifications
for orders, messages, garden announcements, waitlist updates, and
subscription boxes.  All functions are wrapped in try/except so that
email failures never crash the calling API endpoint.

Backend selection (see ``send_email``):
  1. SendGrid (primary) — used when ``SENDGRID_API_KEY`` is set.
  2. Zoho ZeptoMail API (fallback) — used when ``ZEPTOMAIL_TOKEN`` is set,
     either when SendGrid is unconfigured or after it raises. ZeptoMail is
     Zoho's transactional email API; auth is a send-only token (no mailbox
     login), so it mirrors the SendGrid tier and avoids SMTP credentials.
  3. Dev log-only — when neither is configured, message details are
     logged to console so local development is unblocked.

Branding (logo, colors, tagline, footer) and per-email-type on/off
toggles are loaded from the SiteEmailConfig singleton.  Garden-specific
announcement overrides come from GardenEmailConfig.
"""
import logging
from flask import current_app, render_template_string

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
    """Send an email via SendGrid (preferred) or Zoho ZeptoMail (fallback).

    Backend selection priority:
      1. SendGrid — if SENDGRID_API_KEY is set
      2. Zoho ZeptoMail API — if ZEPTOMAIL_TOKEN is set
      3. Dev mode — logs to console if neither is configured

    Returns
    -------
    bool
        True if a real send was attempted successfully via one of the
        providers; False if it fell through to dev-log mode or all
        configured providers failed.

    Parameters
    ----------
    to : str or list[str]
        Recipient email address(es).
    subject : str
        Email subject line.
    html_body : str
        Fully-rendered HTML body.
    """
    import os
    recipients = to if isinstance(to, list) else [to]

    # --- Backend 1: SendGrid (Twilio Email API) ---
    sendgrid_key = os.environ.get('SENDGRID_API_KEY', '')
    if sendgrid_key:
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail as SGMail

            from_email = os.environ.get('SENDGRID_FROM_EMAIL',
                         current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@yardharvest.com'))
            from_name = os.environ.get('SENDGRID_FROM_NAME', 'YardHarvest')

            message = SGMail(
                from_email=(from_email, from_name),
                to_emails=recipients,
                subject=subject,
                html_content=html_body,
            )
            sg = SendGridAPIClient(sendgrid_key)
            response = sg.send(message)
            log.info('[SENDGRID] Sent "%s" to %s (status %d)', subject, ', '.join(recipients), response.status_code)
            return True
        except Exception:
            log.exception('[SENDGRID ERROR] Failed "%s" to %s — falling back to ZeptoMail', subject, ', '.join(recipients))

    # --- Backend 2: Zoho ZeptoMail (transactional API, send-only token) ---
    if _send_via_zeptomail(recipients, subject, html_body):
        return True

    # --- Backend 3: Development mode — just log ---
    log.info(
        '[EMAIL DEV] To: %s | Subject: %s | (HTML body omitted)',
        ', '.join(recipients), subject,
    )
    return False


def _send_via_zeptomail(recipients, subject, html_body):
    """Send through Zoho ZeptoMail's transactional API. Returns True on success.

    No-op (returns False) when ZEPTOMAIL_TOKEN is unset, so callers fall
    through to the next backend. Auth is a send-only "Send Mail token"
    (``Authorization: Zoho-enczapikey <token>``) — never a mailbox password.
    """
    import os
    token = os.environ.get('ZEPTOMAIL_TOKEN', '') or current_app.config.get('ZEPTOMAIL_TOKEN', '')
    if not token:
        return False

    api_url = (os.environ.get('ZEPTOMAIL_API_URL', '')
               or current_app.config.get('ZEPTOMAIL_API_URL', '')
               or 'https://api.zeptomail.com/v1.1/email')
    from_email = (os.environ.get('ZEPTOMAIL_FROM_EMAIL', '')
                  or current_app.config.get('ZEPTOMAIL_FROM_EMAIL', '')
                  or current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@yardharvest.com'))
    from_name = (os.environ.get('ZEPTOMAIL_FROM_NAME', '')
                 or current_app.config.get('ZEPTOMAIL_FROM_NAME', '')
                 or 'YardHarvest')

    payload = {
        'from': {'address': from_email, 'name': from_name},
        'to': [{'email_address': {'address': r}} for r in recipients],
        'subject': subject,
        'htmlbody': html_body,
    }
    try:
        import requests
        resp = requests.post(
            api_url,
            headers={
                'Authorization': f'Zoho-enczapikey {token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
            json=payload,
            timeout=20,
        )
        if resp.status_code in (200, 201):
            log.info('[ZEPTOMAIL] Sent "%s" to %s (status %d)',
                     subject, ', '.join(recipients), resp.status_code)
            return True
        # Do not log the response body — it can echo recipient data.
        log.error('[ZEPTOMAIL ERROR] Send failed for "%s" to %s (status %d)',
                  subject, ', '.join(recipients), resp.status_code)
        return False
    except Exception:
        log.exception('[ZEPTOMAIL ERROR] Failed "%s" to %s', subject, ', '.join(recipients))
        return False


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


def send_password_reset_email(user, token):
    """Send a branded password reset email with a 1-hour reset link.

    This is a transactional/security email — always sends regardless
    of SiteEmailConfig notification toggles.
    """
    site_url = _get_site_url()
    reset_url = f'{site_url}/reset-password?token={token}'
    display = user.display_name or user.username

    content = f'''
    <h2>Password Reset Request</h2>
    <p>Hi {display},</p>
    <p>We received a request to reset the password for your YardHarvest account.
       Click the button below to choose a new password:</p>
    <p style="text-align: center;">
      <a class="btn" href="{reset_url}">Reset Your Password</a>
    </p>
    <p style="font-size: 0.9em; color: #666;">
      This link expires in 1 hour and can only be used once.
      If you didn't request a password reset, you can safely ignore this email.</p>
    '''
    subject = _subject('Password Reset Request')
    send_email(user.email, subject, _render(content))


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
        'harvest_notification': '<h2>🌿 Tomatoes Harvest Alert!</h2>'
            '<p>Great news! <strong>Tomatoes</strong> harvests are coming in from '
            '<strong>3 growers</strong> in your community.</p>'
            '<p>Check the Harvest Forecast to see estimated quantities and timing.</p>'
            '<a href="#" class="btn">View Harvest Forecast</a>',
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


# ---------------------------------------------------------------------------
# 8. Harvest Notification (sent to interested buyers/members)
# ---------------------------------------------------------------------------

def send_harvest_notification(user_email, category, grower_count, site_url=None):
    """Notify a user that a crop they're interested in is being harvested."""
    config = _get_site_email_config()
    if not getattr(config, 'enable_harvest_notifications', True):
        return

    site = site_url or _get_site_url()
    growers_text = f'{grower_count} grower{"s" if grower_count != 1 else ""}'

    content = f"""
    <h2>🌿 {category} Harvest Alert!</h2>
    <p>Great news! <strong>{category}</strong> harvests are coming in from
       <strong>{growers_text}</strong> in your community.</p>
    <p>Check the Harvest Forecast to see estimated quantities, timing, and
       connect with growers who have produce available.</p>
    <a href="{site}/harvest-forecast" class="btn">View Harvest Forecast</a>
    <p style="font-size:13px;color:#888;margin-top:24px;">
      You're receiving this because you subscribed to {category} harvest alerts.
      Visit your <a href="{site}/harvest-forecast">Harvest Forecast</a> to
      manage your notification preferences.</p>
    """
    send_email(
        user_email,
        _subject(f'{category} Harvest Alert', config),
        _render(content, config),
    )


# ---------------------------------------------------------------------------
# 9. Garden Pro Subscription Emails
# ---------------------------------------------------------------------------

def _garden_billing_url(garden_id):
    return f'{_get_site_url()}/gardens/{garden_id}/billing'


def send_garden_trial_welcome(garden, organizer):
    """Day 0: Welcome + Quick Start guide."""
    site = _get_site_url()
    name = organizer.display_name or organizer.username
    content = f'''
    <h2>Welcome to YardHarvest Garden Management</h2>
    <p>Hi {name},</p>
    <p>Your 14-day trial of Garden Pro for <strong>{garden.name}</strong> is now active.</p>
    <p>Here's how to make the most of your first week:</p>
    <ol>
      <li><strong>Add your plots</strong> — Set up your garden layout and assign members to their plots</li>
      <li><strong>Invite your members</strong> — Share your garden link so members can join</li>
      <li><strong>Set up dues</strong> — Configure your seasonal plot fees and generate invoices with one click</li>
      <li><strong>Schedule your first workday</strong> — Create a volunteer shift and let members sign up</li>
    </ol>
    <p style="text-align:center;"><a class="btn" href="{site}/gardens/{garden.id}/admin">Go to Garden Dashboard</a></p>
    <p>Your trial includes everything: financial management, volunteer tracking, photo wall, broadcast messaging, custom email branding, and more.</p>
    <p>Questions? Reply to this email — we read every one.</p>
    '''
    send_email(organizer.email, _subject('Welcome to YardHarvest Garden Management'), _render(content))


def send_garden_trial_progress(garden, organizer):
    """Day 3: Setup progress check-in."""
    site = _get_site_url()
    name = organizer.display_name or organizer.username
    plot_count = garden.plots.count() if garden.plots else 0
    from app.models import GardenPlot
    member_ids = set()
    for p in GardenPlot.query.filter_by(garden_id=garden.id).all():
        if p.assigned_to_id:
            member_ids.add(p.assigned_to_id)
    member_count = len(member_ids)
    event_count = garden.events.count() if garden.events else 0

    tips = ''
    if plot_count == 0:
        tips += '<p>Getting started is easy — add your first plot in under a minute from the Garden Dashboard.</p>'
    if member_count == 0:
        tips += f'<p>Your members can join by visiting your garden page: <a href="{site}/gardens/{garden.id}">{site}/gardens/{garden.id}</a></p>'

    content = f'''
    <h2>How's {garden.name} coming along?</h2>
    <p>Hi {name},</p>
    <p>You've been on YardHarvest for 3 days. Here's what you've set up so far:</p>
    <table class="detail-table">
      <tr><td>Plots configured</td><td>{plot_count}</td></tr>
      <tr><td>Members joined</td><td>{member_count}</td></tr>
      <tr><td>Events scheduled</td><td>{event_count}</td></tr>
    </table>
    {tips}
    <p style="text-align:center;"><a class="btn" href="{site}/gardens/{garden.id}/admin">Continue Setting Up</a></p>
    <p style="color:#888;">11 days left in your trial.</p>
    '''
    send_email(organizer.email, _subject(f"How's {garden.name} coming along?"), _render(content))


def send_garden_trial_halfway(garden, organizer):
    """Day 7: Halfway — feature highlights."""
    site = _get_site_url()
    name = organizer.display_name or organizer.username
    content = f'''
    <h2>You're halfway through your trial</h2>
    <p>Hi {name},</p>
    <p>One week in! Here are the Pro features that save organizers the most time:</p>
    <h3>Financial Management</h3>
    <p>Generate dues for every member in one click. Track expenses by category. Send payment reminders automatically.</p>
    <p style="text-align:center;"><a class="btn" href="{site}/gardens/{garden.id}/admin">Try Financial Tools</a></p>
    <h3>Volunteer Shifts</h3>
    <p>Create workday shifts, track who shows up, and generate volunteer hour reports for grant applications.</p>
    <h3>Broadcast Messaging</h3>
    <p>Send announcements to every member via email and in-app notification — no more group text chains.</p>
    <p style="color:#888;">7 days left in your trial.</p>
    '''
    send_email(organizer.email, _subject("You're halfway through your trial"), _render(content))


def send_garden_trial_expiring(garden, organizer):
    """Day 12: Trial expiring — 2 days left."""
    site = _get_site_url()
    name = organizer.display_name or organizer.username
    sub = garden.subscription
    trial_end = sub.trial_end.strftime('%B %d, %Y') if sub and sub.trial_end else 'soon'
    billing_url = _garden_billing_url(garden.id)

    content = f'''
    <h2>Your {garden.name} trial ends in 2 days</h2>
    <p>Hi {name},</p>
    <p>Your Garden Pro trial ends on <strong>{trial_end}</strong>. Here's what happens:</p>
    <h3>What you keep (free forever):</h3>
    <p>Garden profile, member directory, plot assignments, announcements, harvest logging, basic dashboard.</p>
    <h3>What locks on {trial_end}:</h3>
    <p>Financial management (dues, expenses, reminders), volunteer shift scheduling, photo wall, broadcast messaging, custom email branding, plot grid editor, data export.</p>
    <p>Your data is never deleted — it's all there when you're ready to subscribe.</p>
    <table class="detail-table">
      <tr><td>Monthly</td><td><strong>$15/month</strong></td></tr>
      <tr><td>Annual</td><td><strong>$125/year</strong> (save $55)</td></tr>
    </table>
    <p style="text-align:center;"><a class="btn" href="{billing_url}">Subscribe to Garden Pro</a></p>
    '''
    send_email(organizer.email, _subject(f'Your {garden.name} trial ends in 2 days'), _render(content))


def send_garden_trial_ended(garden, organizer):
    """Day 14: Trial ended."""
    name = organizer.display_name or organizer.username
    billing_url = _garden_billing_url(garden.id)

    content = f'''
    <h2>Your Garden Pro trial has ended</h2>
    <p>Hi {name},</p>
    <p>Your 14-day trial for <strong>{garden.name}</strong> has ended. Pro features are now locked, but your garden profile, plots, members, and all your data remain intact.</p>
    <p>Ready to continue? Choose your plan:</p>
    <table class="detail-table">
      <tr><td>Monthly</td><td><strong>$15/month</strong> — flexible, cancel anytime</td></tr>
      <tr><td>Annual</td><td><strong>$125/year</strong> — save $55 (that's over 3 months free)</td></tr>
    </table>
    <p style="text-align:center;"><a class="btn" href="{billing_url}">Subscribe Now</a></p>
    <p>If you have questions about whether Garden Pro is right for your garden, reply to this email. We're happy to help.</p>
    '''
    send_email(organizer.email, _subject('Your Garden Pro trial has ended'), _render(content))


def send_garden_trial_reengagement(garden, organizer):
    """Day 21: Re-engagement — 1 week post-trial."""
    site = _get_site_url()
    name = organizer.display_name or organizer.username
    billing_url = _garden_billing_url(garden.id)

    from app.models import GardenPlot
    member_ids = set()
    for p in GardenPlot.query.filter_by(garden_id=garden.id).all():
        if p.assigned_to_id:
            member_ids.add(p.assigned_to_id)
    member_count = len(member_ids)

    content = f'''
    <h2>{member_count} members are waiting on {garden.name}</h2>
    <p>Hi {name},</p>
    <p>It's been a week since your Garden Pro trial ended. Your garden is still active — <strong>{member_count} members</strong> have access and are using the platform.</p>
    <p>The Pro features (dues management, volunteer tracking, messaging) would make your job as organizer a lot easier.</p>
    <table class="detail-table">
      <tr><td>Annual</td><td><strong>$125/year</strong> — works out to ~$10.42/month</td></tr>
    </table>
    <p style="text-align:center;"><a class="btn" href="{billing_url}">Reactivate Garden Pro</a></p>
    <p style="color:#888;font-size:13px;">This is our last email about upgrading. We won't ask again — but the option is always there in your garden settings.</p>
    '''
    send_email(organizer.email, _subject(f'{member_count} members are waiting on {garden.name}'), _render(content))


def send_garden_payment_failed(garden, organizer):
    """Dunning email when payment fails."""
    name = organizer.display_name or organizer.username
    billing_url = _garden_billing_url(garden.id)

    content = f'''
    <h2>Action needed: payment failed</h2>
    <p>Hi {name},</p>
    <p>We weren't able to process your Garden Pro payment for <strong>{garden.name}</strong>. Your Pro features will remain active for 7 days while you update your payment method.</p>
    <p style="text-align:center;"><a class="btn" href="{billing_url}">Update Payment Method</a></p>
    <p>If your payment isn't updated within 7 days, your garden will revert to the free plan. Your data will not be deleted.</p>
    '''
    send_email(organizer.email, _subject(f'Action needed: payment failed for {garden.name}'), _render(content))


def send_garden_subscription_cancelled(garden, organizer):
    """Confirmation email when subscription is cancelled."""
    name = organizer.display_name or organizer.username
    sub = garden.subscription
    period_end = sub.current_period_end.strftime('%B %d, %Y') if sub and sub.current_period_end else 'the end of your billing period'

    content = f'''
    <h2>{garden.name} Garden Pro cancelled</h2>
    <p>Hi {name},</p>
    <p>Your Garden Pro subscription for <strong>{garden.name}</strong> has been cancelled. You'll continue to have Pro access until <strong>{period_end}</strong>, then your garden will revert to the free plan.</p>
    <p>Your data (plots, members, financials, harvest logs) is never deleted. You can resubscribe anytime from your garden settings.</p>
    <p>We'd love to know what we could do better — reply to this email with any feedback.</p>
    '''
    send_email(organizer.email, _subject(f'{garden.name} Garden Pro cancelled'), _render(content))


# ---------------------------------------------------------------------------
# Plot Assignment Notifications
# ---------------------------------------------------------------------------

def send_plot_assigned_email(garden_name, plot_label, user_email, user_name, garden_id=None):
    """Notify user that they have been assigned a garden plot."""
    config = _get_site_config()
    if not config.enable_announcements:
        return
    name = user_name or 'Gardener'
    site_url = _site_url()
    garden_url = f'{site_url}/gardens/{garden_id}' if garden_id else site_url

    content = f'''
    <h2>You've been assigned a plot!</h2>
    <p>Hi {name},</p>
    <p>Great news — you've been assigned <strong>Plot {plot_label}</strong> at <strong>{garden_name}</strong>.</p>
    <p>Here's what to do next:</p>
    <table class="detail-table">
      <tr><td>Visit your garden page</td><td>Check plot details, rules, and upcoming events</td></tr>
      <tr><td>Meet your neighbors</td><td>Introduce yourself to fellow gardeners</td></tr>
      <tr><td>Plan your season</td><td>Use the Planting Calendar for Zone 5b guidance</td></tr>
    </table>
    <p style="text-align:center;"><a class="btn" href="{garden_url}">View Your Garden</a></p>
    '''
    send_email(user_email, _subject(f'Plot assigned at {garden_name}'), _render(content))


def send_plot_waitlisted_email(garden_name, user_email, user_name, position, garden_id=None):
    """Notify user they've been added to the waitlist."""
    name = user_name or 'Gardener'
    site_url = _site_url()
    garden_url = f'{site_url}/gardens/{garden_id}' if garden_id else site_url

    content = f'''
    <h2>You're on the waitlist</h2>
    <p>Hi {name},</p>
    <p>You've been added to the waitlist for <strong>{garden_name}</strong>. Your position is <strong>#{position}</strong>.</p>
    <p>We'll notify you as soon as a plot becomes available. In the meantime, you can check garden events and announcements.</p>
    <p style="text-align:center;"><a class="btn" href="{garden_url}">View Garden</a></p>
    '''
    send_email(user_email, _subject(f'Waitlisted for {garden_name}'), _render(content))


def send_dues_reminder_email(garden_name, user_email, user_name, amount, season_year, garden_id=None):
    """Remind a member that dues are outstanding."""
    name = user_name or 'Gardener'
    site_url = _site_url()
    garden_url = f'{site_url}/gardens/{garden_id}' if garden_id else site_url

    content = f'''
    <h2>Dues reminder for {garden_name}</h2>
    <p>Hi {name},</p>
    <p>This is a friendly reminder that your <strong>{season_year}</strong> garden dues of <strong>${amount:.2f}</strong> are outstanding for <strong>{garden_name}</strong>.</p>
    <p>You can pay online from your garden page — it only takes a moment.</p>
    <p style="text-align:center;"><a class="btn" href="{garden_url}">Pay Dues Now</a></p>
    '''
    send_email(user_email, _subject(f'Dues reminder: {garden_name}'), _render(content))


def send_shift_reminder_email(garden_name, user_email, user_name, shift_title, shift_date, garden_id=None):
    """Remind a volunteer about an upcoming shift."""
    name = user_name or 'Gardener'
    site_url = _site_url()
    garden_url = f'{site_url}/gardens/{garden_id}' if garden_id else site_url

    content = f'''
    <h2>Upcoming shift at {garden_name}</h2>
    <p>Hi {name},</p>
    <p>Just a reminder — you're signed up for <strong>{shift_title}</strong> at <strong>{garden_name}</strong> on <strong>{shift_date}</strong>.</p>
    <p style="text-align:center;"><a class="btn" href="{garden_url}">View Garden</a></p>
    '''
    send_email(user_email, _subject(f'Shift reminder: {shift_title}'), _render(content))


def send_refund_confirmation_email(order, buyer_email, refund_amount, is_full):
    """Notify buyer that a refund has been issued."""
    config = _get_site_config()
    refund_type = 'Full' if is_full else 'Partial'
    site_url = _site_url()

    content = f'''
    <h2>{refund_type} Refund Issued</h2>
    <p>A {refund_type.lower()} refund of <strong>${refund_amount:.2f}</strong> has been issued for your order <strong>#{order.id}</strong>.</p>
    <table class="detail-table">
      <tr><td>Order</td><td>#{order.id}</td></tr>
      <tr><td>Original Total</td><td>${order.total_price:.2f}</td></tr>
      <tr><td>Refund Amount</td><td>${refund_amount:.2f}</td></tr>
    </table>
    <p>The refund will appear on your statement within 5-10 business days.</p>
    <p style="text-align:center;"><a class="btn" href="{site_url}/orders/{order.id}">View Order</a></p>
    '''
    send_email(buyer_email, _subject(f'{refund_type} refund for order #{order.id}'), _render(content))
