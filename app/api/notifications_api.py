"""In-app notification endpoints."""
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app.api.token_auth import token_or_session, get_current_user
from app import db
from app.models import Notification, User

notifications_api = Blueprint('notifications_api', __name__, url_prefix='/api/notifications')


@notifications_api.route('', methods=['GET'])
@token_or_session
def list_notifications():
    """Get current user's notifications (newest first)."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    unread_only = request.args.get('unread_only', 'false') == 'true'

    q = Notification.query.filter_by(user_id=get_current_user().id)
    if unread_only:
        q = q.filter_by(is_read=False)
    q = q.order_by(Notification.created_at.desc())

    paginated = q.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'notifications': [_notif_to_dict(n) for n in paginated.items],
        'unread_count': Notification.query.filter_by(user_id=get_current_user().id, is_read=False).count(),
        'total': paginated.total,
        'page': paginated.page,
        'pages': paginated.pages,
    })


@notifications_api.route('/unread-count', methods=['GET'])
@token_or_session
def unread_count():
    """Quick endpoint for badge count."""
    count = Notification.query.filter_by(user_id=get_current_user().id, is_read=False).count()
    return jsonify({'unread_count': count})


@notifications_api.route('/<int:notif_id>/read', methods=['POST'])
@token_or_session
def mark_read(notif_id):
    """Mark a single notification as read."""
    notif = db.get_or_404(Notification, notif_id)
    if notif.user_id != get_current_user().id:
        return jsonify({'error': 'Forbidden'}), 403
    notif.is_read = True
    db.session.commit()
    return jsonify({'ok': True})


@notifications_api.route('/mark-all-read', methods=['POST'])
@token_or_session
def mark_all_read():
    """Mark all notifications as read."""
    Notification.query.filter_by(
        user_id=get_current_user().id, is_read=False
    ).update({'is_read': True})
    db.session.commit()
    return jsonify({'ok': True})


@notifications_api.route('/<int:notif_id>', methods=['DELETE'])
@token_or_session
def delete_notification(notif_id):
    """Delete a single notification."""
    notif = db.get_or_404(Notification, notif_id)
    if notif.user_id != get_current_user().id:
        return jsonify({'error': 'Forbidden'}), 403
    db.session.delete(notif)
    db.session.commit()
    return jsonify({'ok': True})


def _notif_to_dict(n):
    return {
        'id': n.id,
        'type': n.type,
        'title': n.title,
        'body': n.body,
        'link': n.link,
        'garden_id': n.garden_id,
        'is_read': n.is_read,
        'created_at': n.created_at.isoformat() if n.created_at else None,
    }


# ---------------------------------------------------------------------------
# Notification Preferences (per-user email + SMS settings)
# ---------------------------------------------------------------------------

PREF_FIELDS = [
    'email_order_updates', 'email_messages', 'email_harvest_alerts',
    'email_garden_announcements', 'sms_opt_in',
]


@notifications_api.route('/preferences', methods=['GET'])
@token_or_session
def get_preferences():
    """Get current user's notification preferences."""
    user = get_current_user()
    return jsonify({
        'email_order_updates': getattr(user, 'email_order_updates', True),
        'email_messages': getattr(user, 'email_messages', True),
        'email_harvest_alerts': getattr(user, 'email_harvest_alerts', True),
        'email_garden_announcements': getattr(user, 'email_garden_announcements', True),
        'sms_opt_in': user.sms_opt_in or False,
        'phone_number': user.phone_number or '',
    })


@notifications_api.route('/preferences', methods=['PUT'])
@token_or_session
def update_preferences():
    """Update current user's notification preferences."""
    user = get_current_user()
    data = request.get_json() or {}

    for field in PREF_FIELDS:
        if field in data:
            setattr(user, field, bool(data[field]))

    if 'phone_number' in data:
        phone = (data['phone_number'] or '').strip()
        if phone and len(phone) > 20:
            return jsonify({'error': 'Phone number too long'}), 400
        user.phone_number = phone

    db.session.commit()
    return jsonify({'message': 'Preferences updated'})


# ---- Helper to create notifications from anywhere in the app ----

def notify(user_id, type, title, body='', link='', garden_id=None):
    """Create an in-app notification for a user, and push it to their phone.

    The APNs send is best-effort and never raises; a dead device token is
    cleared on the user row and persisted by the caller's commit, same as
    the notification row itself.
    """
    n = Notification(
        user_id=user_id,
        type=type,
        title=title,
        body=body,
        link=link,
        garden_id=garden_id,
    )
    db.session.add(n)
    from app import push_service
    if push_service.is_configured():
        user = db.session.get(User, user_id)
        if user is not None:
            unread = Notification.query.filter_by(
                user_id=user_id, is_read=False).count() + 1
            push_service.send_push(user, title, body=body, link=link,
                                   garden_id=garden_id, badge=unread,
                                   ntype=type)
    # Caller is responsible for db.session.commit()
    return n
