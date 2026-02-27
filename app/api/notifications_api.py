"""In-app notification endpoints."""
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app.api.token_auth import token_or_session, get_current_user
from app import db
from app.models import Notification

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
    notif = Notification.query.get_or_404(notif_id)
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
    notif = Notification.query.get_or_404(notif_id)
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


# ---- Helper to create notifications from anywhere in the app ----

def notify(user_id, type, title, body='', link='', garden_id=None):
    """Create an in-app notification for a user."""
    n = Notification(
        user_id=user_id,
        type=type,
        title=title,
        body=body,
        link=link,
        garden_id=garden_id,
    )
    db.session.add(n)
    # Caller is responsible for db.session.commit()
    return n
