from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import Message, User, Listing
from app.forms import MessageForm
from sqlalchemy import or_, and_, func

messages_bp = Blueprint('messages', __name__)


@messages_bp.route('/messages')
@login_required
def inbox():
    subq = db.session.query(
        Message.thread_id,
        func.max(Message.id).label('max_id')
    ).filter(
        or_(Message.sender_id == current_user.id, Message.recipient_id == current_user.id)
    ).group_by(Message.thread_id).subquery()

    latest_messages = db.session.query(Message).join(
        subq, Message.id == subq.c.max_id
    ).order_by(Message.created_at.desc()).all()

    threads = []
    for msg in latest_messages:
        other_id = msg.recipient_id if msg.sender_id == current_user.id else msg.sender_id
        other_user = User.query.get(other_id)
        unread = Message.query.filter_by(
            thread_id=msg.thread_id, recipient_id=current_user.id, is_read=False
        ).count()
        threads.append({
            'thread_id': msg.thread_id,
            'other_user': other_user,
            'last_message': msg,
            'unread': unread,
            'listing': msg.listing,
        })

    return render_template('messages/inbox.html', threads=threads)


@messages_bp.route('/messages/thread/<thread_id>')
@login_required
def thread(thread_id):
    messages = Message.query.filter_by(thread_id=thread_id).filter(
        or_(Message.sender_id == current_user.id, Message.recipient_id == current_user.id)
    ).order_by(Message.created_at.asc()).all()

    if not messages:
        flash('Conversation not found.', 'warning')
        return redirect(url_for('messages.inbox'))

    Message.query.filter_by(
        thread_id=thread_id, recipient_id=current_user.id, is_read=False
    ).update({'is_read': True})
    db.session.commit()

    first = messages[0]
    other_id = first.recipient_id if first.sender_id == current_user.id else first.sender_id
    other_user = User.query.get(other_id)

    form = MessageForm()
    form.recipient_id.data = str(other_id)
    if first.listing_id:
        form.listing_id.data = str(first.listing_id)

    return render_template('messages/thread.html', messages=messages,
                           other_user=other_user, form=form, thread_id=thread_id)


@messages_bp.route('/messages/send', methods=['POST'])
@login_required
def send():
    form = MessageForm()
    if form.validate_on_submit():
        recipient_id = int(form.recipient_id.data)
        listing_id = int(form.listing_id.data) if form.listing_id.data else None

        thread_id = Message.make_thread_id(current_user.id, recipient_id, listing_id)

        msg = Message(
            thread_id=thread_id,
            sender_id=current_user.id,
            recipient_id=recipient_id,
            listing_id=listing_id,
            body=form.body.data,
        )
        db.session.add(msg)
        db.session.commit()
        return redirect(url_for('messages.thread', thread_id=thread_id))

    flash('Could not send message.', 'danger')
    return redirect(url_for('messages.inbox'))


@messages_bp.route('/messages/new/<int:user_id>')
@login_required
def new_thread(user_id):
    other_user = User.query.get_or_404(user_id)
    listing_id = request.args.get('listing_id', type=int)

    thread_id = Message.make_thread_id(current_user.id, user_id, listing_id)

    existing = Message.query.filter_by(thread_id=thread_id).first()
    if existing:
        return redirect(url_for('messages.thread', thread_id=thread_id))

    form = MessageForm()
    form.recipient_id.data = str(user_id)
    if listing_id:
        form.listing_id.data = str(listing_id)

    listing = Listing.query.get(listing_id) if listing_id else None
    return render_template('messages/new_thread.html', other_user=other_user,
                           form=form, listing=listing)
