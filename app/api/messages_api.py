"""Messages REST API endpoints."""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.api.token_auth import token_or_session, get_current_user
from app import db, limiter
from app.models import Message, User, Listing
from app.email_service import send_message_notification
from sqlalchemy import or_, func

messages_api = Blueprint('messages_api', __name__, url_prefix='/api/messages')


def message_to_dict(msg):
    return {
        'id': msg.id,
        'thread_id': msg.thread_id,
        'sender_id': msg.sender_id,
        'recipient_id': msg.recipient_id,
        'sender_name': msg.sender.display_name or msg.sender.username,
        'recipient_name': msg.recipient.display_name or msg.recipient.username,
        'listing_id': msg.listing_id,
        'body': msg.body,
        'is_read': msg.is_read,
        'created_at': msg.created_at.isoformat() if msg.created_at else None,
    }


@messages_api.route('/inbox', methods=['GET'])
@token_or_session
def inbox():
    subq = db.session.query(
        Message.thread_id,
        func.max(Message.id).label('max_id')
    ).filter(
        or_(Message.sender_id == get_current_user().id, Message.recipient_id == get_current_user().id)
    ).group_by(Message.thread_id).subquery()

    latest_messages = db.session.query(Message).join(
        subq, Message.id == subq.c.max_id
    ).order_by(Message.created_at.desc()).all()

    threads = []
    for msg in latest_messages:
        other_id = msg.recipient_id if msg.sender_id == get_current_user().id else msg.sender_id
        other_user = User.query.get(other_id)
        unread = Message.query.filter_by(
            thread_id=msg.thread_id, recipient_id=get_current_user().id, is_read=False
        ).count()
        threads.append({
            'thread_id': msg.thread_id,
            'other_user': {
                'id': other_user.id,
                'display_name': other_user.display_name or other_user.username,
                'profile_image': other_user.profile_image,
            },
            'last_message': message_to_dict(msg),
            'unread': unread,
            'listing': {
                'id': msg.listing.id,
                'title': msg.listing.title,
            } if msg.listing else None,
        })

    return jsonify(threads)


@messages_api.route('/thread/<thread_id>', methods=['GET'])
@token_or_session
def thread(thread_id):
    messages = Message.query.filter_by(thread_id=thread_id).filter(
        or_(Message.sender_id == get_current_user().id, Message.recipient_id == get_current_user().id)
    ).order_by(Message.created_at.asc()).all()

    if not messages:
        return jsonify({'error': 'Conversation not found'}), 404

    # Mark as read
    Message.query.filter_by(
        thread_id=thread_id, recipient_id=get_current_user().id, is_read=False
    ).update({'is_read': True})
    db.session.commit()

    first = messages[0]
    other_id = first.recipient_id if first.sender_id == get_current_user().id else first.sender_id
    other_user = User.query.get(other_id)

    return jsonify({
        'messages': [message_to_dict(m) for m in messages],
        'other_user': {
            'id': other_user.id,
            'display_name': other_user.display_name or other_user.username,
            'profile_image': other_user.profile_image,
        },
        'listing_id': first.listing_id,
    })


@messages_api.route('/send', methods=['POST'])
@token_or_session
@limiter.limit("20 per minute")
def send():
    data = request.get_json()
    if not data or not data.get('body'):
        return jsonify({'error': 'Message body required'}), 400

    # H7: Input validation
    body = data['body'].strip()
    if not body:
        return jsonify({'error': 'Message body required'}), 400
    if len(body) > 5000:
        return jsonify({'error': 'Message must be under 5000 characters'}), 400

    recipient_id = int(data.get('recipient_id', 0))
    if recipient_id == get_current_user().id:
        return jsonify({'error': 'Cannot send messages to yourself'}), 400
    if not User.query.get(recipient_id):
        return jsonify({'error': 'Recipient not found'}), 404

    listing_id = int(data['listing_id']) if data.get('listing_id') else None

    thread_id = Message.make_thread_id(get_current_user().id, recipient_id, listing_id)

    msg = Message(
        thread_id=thread_id,
        sender_id=get_current_user().id,
        recipient_id=recipient_id,
        listing_id=listing_id,
        body=body,
    )
    db.session.add(msg)
    db.session.commit()

    # Notify the recipient via email and SMS
    try:
        recipient = User.query.get(recipient_id)
        if recipient:
            sender_name = get_current_user().display_name or get_current_user().username
            send_message_notification(sender_name, recipient.email, data['body'])
            # SMS notification (was missing — function existed but was never called)
            if getattr(recipient, 'sms_opt_in', False) and getattr(recipient, 'phone_number', None):
                from app.sms_service import send_message_notification_sms
                send_message_notification_sms(recipient.phone_number, sender_name)
    except Exception:
        pass

    return jsonify(message_to_dict(msg)), 201


@messages_api.route('/unread_count', methods=['GET'])
@token_or_session
def unread_count():
    count = Message.query.filter_by(recipient_id=get_current_user().id, is_read=False).count()
    return jsonify({'count': count})
