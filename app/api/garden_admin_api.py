"""Garden Admin Portal REST API endpoints.

Admin-specific endpoints for community garden management.
All routes are under /api/gardens/{id}/admin/ to avoid conflicts
with the public gardens_api endpoints.
"""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import (
    CommunityGarden, GardenPlot, GardenWaitlist, SharedResource,
    GardenEvent, EventRSVP, HarvestLog, GardenAnnouncement,
    GardenMessage, GardenPhoto, GardenPhotoComment, GardenPhotoLike,
    User
)
from app.email_service import send_garden_announcement
from datetime import datetime, timezone
from sqlalchemy import or_

garden_admin_api = Blueprint('garden_admin_api', __name__, url_prefix='/api/garden-admin')


# ---------------------------------------------------------------------------
# Helper: verify the current user is the garden organizer or a site admin
# ---------------------------------------------------------------------------

def require_garden_admin(garden_id):
    """Return (garden, None) if authorised, or (None, error_response) if not."""
    garden = CommunityGarden.query.get(garden_id)
    if not garden:
        return None, (jsonify({'error': 'Garden not found'}), 404)
    if garden.organizer_id != current_user.id and not current_user.is_admin:
        return None, (jsonify({'error': 'Not authorized — admin access required'}), 403)
    return garden, None


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def announcement_to_dict(ann):
    return {
        'id': ann.id,
        'garden_id': ann.garden_id,
        'author_id': ann.author_id,
        'author_name': ann.author.display_name or ann.author.username,
        'title': ann.title,
        'body': ann.body,
        'priority': ann.priority,
        'pinned': ann.pinned,
        'created_at': ann.created_at.isoformat() if ann.created_at else None,
    }


def message_to_dict(msg):
    return {
        'id': msg.id,
        'garden_id': msg.garden_id,
        'sender_id': msg.sender_id,
        'sender_name': msg.sender.display_name or msg.sender.username,
        'recipient_id': msg.recipient_id,
        'recipient_name': msg.recipient.display_name or msg.recipient.username,
        'subject': msg.subject,
        'body': msg.body,
        'is_read': msg.is_read,
        'created_at': msg.created_at.isoformat() if msg.created_at else None,
    }


def photo_to_dict(photo):
    return {
        'id': photo.id,
        'garden_id': photo.garden_id,
        'user_id': photo.user_id,
        'user_name': photo.user.display_name or photo.user.username,
        'photo_url': photo.photo_url,
        'caption': photo.caption,
        'category': photo.category,
        'likes_count': photo.likes_count,
        'comments_count': photo.comments.count(),
        'created_at': photo.created_at.isoformat() if photo.created_at else None,
    }


def comment_to_dict(comment):
    return {
        'id': comment.id,
        'photo_id': comment.photo_id,
        'user_id': comment.user_id,
        'user_name': comment.user.display_name or comment.user.username,
        'content': comment.content,
        'created_at': comment.created_at.isoformat() if comment.created_at else None,
    }


def event_to_dict_admin(event):
    return {
        'id': event.id,
        'garden_id': event.garden_id,
        'title': event.title,
        'description': event.description,
        'event_type': event.event_type,
        'event_date': event.event_date.isoformat() if event.event_date else None,
        'duration_hours': event.duration_hours,
        'max_volunteers': event.max_volunteers,
        'created_by_id': event.created_by_id,
        'created_by_name': event.created_by.display_name or event.created_by.username,
        'created_at': event.created_at.isoformat() if event.created_at else None,
        'rsvp_going': event.rsvps.filter_by(status='going').count(),
        'rsvp_maybe': event.rsvps.filter_by(status='maybe').count(),
        'rsvp_not_going': event.rsvps.filter_by(status='not_going').count(),
    }


# ===================================================================
#  1. GET /{id}/admin/dashboard — Admin overview
# ===================================================================

@garden_admin_api.route('/<int:garden_id>/dashboard', methods=['GET'])
@login_required
def admin_dashboard(garden_id):
    garden, err = require_garden_admin(garden_id)
    if err:
        return err

    now = datetime.now(timezone.utc)

    # Plot occupancy
    total_plots = garden.plots.count()
    assigned_plots = garden.plots.filter_by(status='assigned').count()
    available_plots = garden.plots.filter_by(status='available').count()
    maintenance_plots = garden.plots.filter_by(status='maintenance').count()
    reserved_plots = garden.plots.filter_by(status='reserved').count()

    # Waitlist
    waitlist_count = GardenWaitlist.query.filter_by(
        garden_id=garden_id, status='waiting'
    ).count()

    # Harvest stats
    total_harvest_lbs = db.session.query(
        db.func.coalesce(db.func.sum(HarvestLog.quantity_lbs), 0)
    ).filter_by(garden_id=garden_id).scalar()

    # Upcoming events (next 5)
    upcoming_events = garden.events.filter(
        GardenEvent.event_date >= now
    ).order_by(GardenEvent.event_date).limit(5).all()

    # Recent announcements (last 5)
    recent_announcements = GardenAnnouncement.query.filter_by(
        garden_id=garden_id
    ).order_by(GardenAnnouncement.created_at.desc()).limit(5).all()

    # Unread messages (messages received by admin that are unread)
    unread_messages_count = GardenMessage.query.filter_by(
        garden_id=garden_id,
        recipient_id=current_user.id,
        is_read=False,
    ).count()

    # Recent photos (last 6)
    recent_photos = GardenPhoto.query.filter_by(
        garden_id=garden_id
    ).order_by(GardenPhoto.created_at.desc()).limit(6).all()

    # Plots nearing renewal (within 30 days)
    from datetime import timedelta
    renewal_cutoff = (now + timedelta(days=30)).date()
    expiring_plots = garden.plots.filter(
        GardenPlot.status == 'assigned',
        GardenPlot.renewal_date != None,  # noqa: E711
        GardenPlot.renewal_date <= renewal_cutoff,
    ).count()

    return jsonify({
        'garden_id': garden.id,
        'garden_name': garden.name,
        'is_active': garden.is_active,
        'plots': {
            'total': total_plots,
            'assigned': assigned_plots,
            'available': available_plots,
            'maintenance': maintenance_plots,
            'reserved': reserved_plots,
            'occupancy_pct': round(assigned_plots / total_plots * 100, 1) if total_plots else 0,
            'expiring_soon': expiring_plots,
        },
        'waitlist_count': waitlist_count,
        'total_harvest_lbs': float(total_harvest_lbs),
        'unread_messages_count': unread_messages_count,
        'upcoming_events': [event_to_dict_admin(e) for e in upcoming_events],
        'recent_announcements': [announcement_to_dict(a) for a in recent_announcements],
        'recent_photos': [photo_to_dict(p) for p in recent_photos],
    })


# ===================================================================
#  2. GET /{id}/admin/plots — Enhanced plot list
# ===================================================================

@garden_admin_api.route('/<int:garden_id>/plots', methods=['GET'])
@login_required
def admin_list_plots(garden_id):
    garden, err = require_garden_admin(garden_id)
    if err:
        return err

    plots = garden.plots.order_by(GardenPlot.plot_number).all()
    result = []

    for plot in plots:
        d = {
            'id': plot.id,
            'garden_id': plot.garden_id,
            'plot_number': plot.plot_number,
            'size': plot.size,
            'location_notes': plot.location_notes,
            'status': plot.status,
            'assigned_to_id': plot.assigned_to_id,
            'assigned_date': plot.assigned_date.isoformat() if plot.assigned_date else None,
            'renewal_date': plot.renewal_date.isoformat() if plot.renewal_date else None,
            'assigned_to_name': None,
            'assigned_to_email': None,
            'harvest_total_lbs': 0.0,
            'harvest_count': 0,
        }

        if plot.assigned_to:
            user = plot.assigned_to
            d['assigned_to_name'] = user.display_name or user.username
            d['assigned_to_email'] = user.email

            # Harvest stats for this member in this garden
            harvest_agg = db.session.query(
                db.func.coalesce(db.func.sum(HarvestLog.quantity_lbs), 0),
                db.func.count(HarvestLog.id),
            ).filter_by(
                garden_id=garden_id,
                user_id=user.id,
            ).first()
            d['harvest_total_lbs'] = float(harvest_agg[0])
            d['harvest_count'] = harvest_agg[1]

        result.append(d)

    return jsonify(result)


# ===================================================================
#  3. PUT /{id}/admin/plots/{plot_id} — Edit plot details
# ===================================================================

@garden_admin_api.route('/<int:garden_id>/plots/<int:plot_id>', methods=['PUT'])
@login_required
def admin_edit_plot(garden_id, plot_id):
    garden, err = require_garden_admin(garden_id)
    if err:
        return err

    plot = GardenPlot.query.get(plot_id)
    if not plot or plot.garden_id != garden_id:
        return jsonify({'error': 'Plot not found in this garden'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    if 'size' in data:
        plot.size = data['size']
    if 'location_notes' in data:
        plot.location_notes = data['location_notes']
    if 'status' in data:
        valid_statuses = ('available', 'assigned', 'reserved', 'maintenance')
        if data['status'] not in valid_statuses:
            return jsonify({'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'}), 400
        plot.status = data['status']
    if 'renewal_date' in data:
        if data['renewal_date']:
            try:
                plot.renewal_date = datetime.strptime(data['renewal_date'], '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'error': 'renewal_date must be in YYYY-MM-DD format'}), 400
        else:
            plot.renewal_date = None

    db.session.commit()

    return jsonify({
        'id': plot.id,
        'garden_id': plot.garden_id,
        'plot_number': plot.plot_number,
        'size': plot.size,
        'location_notes': plot.location_notes,
        'status': plot.status,
        'assigned_to_id': plot.assigned_to_id,
        'assigned_to_name': (plot.assigned_to.display_name or plot.assigned_to.username) if plot.assigned_to else None,
        'assigned_date': plot.assigned_date.isoformat() if plot.assigned_date else None,
        'renewal_date': plot.renewal_date.isoformat() if plot.renewal_date else None,
    })


# ===================================================================
#  4. PUT /{id}/admin/plots/{plot_id}/maintenance — Toggle maintenance
# ===================================================================

@garden_admin_api.route('/<int:garden_id>/plots/<int:plot_id>/maintenance', methods=['PUT'])
@login_required
def admin_toggle_maintenance(garden_id, plot_id):
    garden, err = require_garden_admin(garden_id)
    if err:
        return err

    plot = GardenPlot.query.get(plot_id)
    if not plot or plot.garden_id != garden_id:
        return jsonify({'error': 'Plot not found in this garden'}), 404

    if plot.status == 'maintenance':
        plot.status = 'available'
    else:
        if plot.status == 'assigned':
            return jsonify({
                'error': 'Cannot put an assigned plot into maintenance. Release the plot first.'
            }), 400
        plot.status = 'maintenance'

    db.session.commit()

    return jsonify({
        'id': plot.id,
        'plot_number': plot.plot_number,
        'status': plot.status,
        'message': f'Plot {plot.plot_number} is now {plot.status}',
    })


# ===================================================================
#  5. POST /{id}/admin/announcements — Create announcement
# ===================================================================

@garden_admin_api.route('/<int:garden_id>/announcements', methods=['POST'])
@login_required
def admin_create_announcement(garden_id):
    garden, err = require_garden_admin(garden_id)
    if err:
        return err

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    title = (data.get('title') or '').strip()
    body = (data.get('body') or '').strip()
    if not title:
        return jsonify({'error': 'Title is required'}), 400
    if not body:
        return jsonify({'error': 'Body is required'}), 400

    priority = data.get('priority', 'normal')
    if priority not in ('normal', 'important', 'urgent'):
        return jsonify({'error': 'priority must be normal, important, or urgent'}), 400

    ann = GardenAnnouncement(
        garden_id=garden_id,
        author_id=current_user.id,
        title=title,
        body=body,
        priority=priority,
        pinned=bool(data.get('pinned', False)),
    )
    db.session.add(ann)
    db.session.commit()

    # Email all garden members (plot holders) about the announcement
    try:
        assigned_plots = garden.plots.filter_by(status='assigned').all()
        member_ids = list({p.assigned_to_id for p in assigned_plots if p.assigned_to_id})
        if member_ids:
            members = User.query.filter(User.id.in_(member_ids)).all()
            member_emails = [m.email for m in members if m.email]
            if member_emails:
                send_garden_announcement(
                    garden.name, title, body, priority, member_emails,
                )
    except Exception:
        pass

    return jsonify(announcement_to_dict(ann)), 201


# ===================================================================
#  6. GET /{id}/admin/announcements — List announcements (paginated)
# ===================================================================

@garden_admin_api.route('/<int:garden_id>/announcements', methods=['GET'])
@login_required
def admin_list_announcements(garden_id):
    garden, err = require_garden_admin(garden_id)
    if err:
        return err

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    per_page = min(per_page, 100)

    q = GardenAnnouncement.query.filter_by(garden_id=garden_id)

    # Pinned first, then by creation date desc
    q = q.order_by(GardenAnnouncement.pinned.desc(), GardenAnnouncement.created_at.desc())

    pagination = q.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'announcements': [announcement_to_dict(a) for a in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'page': pagination.page,
        'has_next': pagination.has_next,
        'has_prev': pagination.has_prev,
    })


# ===================================================================
#  7. PUT /{id}/admin/announcements/{ann_id} — Edit announcement
# ===================================================================

@garden_admin_api.route('/<int:garden_id>/announcements/<int:ann_id>', methods=['PUT'])
@login_required
def admin_edit_announcement(garden_id, ann_id):
    garden, err = require_garden_admin(garden_id)
    if err:
        return err

    ann = GardenAnnouncement.query.get(ann_id)
    if not ann or ann.garden_id != garden_id:
        return jsonify({'error': 'Announcement not found in this garden'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    if 'title' in data:
        title = data['title'].strip()
        if not title:
            return jsonify({'error': 'Title cannot be empty'}), 400
        ann.title = title
    if 'body' in data:
        body = data['body'].strip()
        if not body:
            return jsonify({'error': 'Body cannot be empty'}), 400
        ann.body = body
    if 'priority' in data:
        if data['priority'] not in ('normal', 'important', 'urgent'):
            return jsonify({'error': 'priority must be normal, important, or urgent'}), 400
        ann.priority = data['priority']
    if 'pinned' in data:
        ann.pinned = bool(data['pinned'])

    db.session.commit()
    return jsonify(announcement_to_dict(ann))


# ===================================================================
#  8. DELETE /{id}/admin/announcements/{ann_id} — Delete announcement
# ===================================================================

@garden_admin_api.route('/<int:garden_id>/announcements/<int:ann_id>', methods=['DELETE'])
@login_required
def admin_delete_announcement(garden_id, ann_id):
    garden, err = require_garden_admin(garden_id)
    if err:
        return err

    ann = GardenAnnouncement.query.get(ann_id)
    if not ann or ann.garden_id != garden_id:
        return jsonify({'error': 'Announcement not found in this garden'}), 404

    db.session.delete(ann)
    db.session.commit()
    return jsonify({'message': 'Announcement deleted'})


# ===================================================================
#  9. GET /{id}/admin/messages — List garden messages for admin
# ===================================================================

@garden_admin_api.route('/<int:garden_id>/messages', methods=['GET'])
@login_required
def admin_list_messages(garden_id):
    garden, err = require_garden_admin(garden_id)
    if err:
        return err

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    per_page = min(per_page, 100)

    # Messages sent or received by the admin within this garden
    q = GardenMessage.query.filter(
        GardenMessage.garden_id == garden_id,
        or_(
            GardenMessage.sender_id == current_user.id,
            GardenMessage.recipient_id == current_user.id,
        )
    ).order_by(GardenMessage.created_at.desc())

    pagination = q.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'messages': [message_to_dict(m) for m in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'page': pagination.page,
        'has_next': pagination.has_next,
        'has_prev': pagination.has_prev,
    })


# ===================================================================
# 10. POST /{id}/admin/messages — Send message to a plot owner
# ===================================================================

@garden_admin_api.route('/<int:garden_id>/messages', methods=['POST'])
@login_required
def admin_send_message(garden_id):
    garden, err = require_garden_admin(garden_id)
    if err:
        return err

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    recipient_id = data.get('recipient_id')
    subject = (data.get('subject') or '').strip()
    body = (data.get('body') or '').strip()

    if not recipient_id:
        return jsonify({'error': 'recipient_id is required'}), 400
    if not body:
        return jsonify({'error': 'Message body is required'}), 400

    recipient = User.query.get(recipient_id)
    if not recipient:
        return jsonify({'error': 'Recipient not found'}), 404

    msg = GardenMessage(
        garden_id=garden_id,
        sender_id=current_user.id,
        recipient_id=recipient_id,
        subject=subject,
        body=body,
    )
    db.session.add(msg)
    db.session.commit()

    return jsonify(message_to_dict(msg)), 201


# ===================================================================
# 11. POST /{id}/admin/messages/broadcast — Broadcast to all plot owners
# ===================================================================

@garden_admin_api.route('/<int:garden_id>/messages/broadcast', methods=['POST'])
@login_required
def admin_broadcast_message(garden_id):
    garden, err = require_garden_admin(garden_id)
    if err:
        return err

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    subject = (data.get('subject') or '').strip()
    body = (data.get('body') or '').strip()

    if not body:
        return jsonify({'error': 'Message body is required'}), 400

    # Get all distinct plot owners in this garden
    assigned_plots = garden.plots.filter_by(status='assigned').all()
    recipient_ids = list({p.assigned_to_id for p in assigned_plots if p.assigned_to_id})

    if not recipient_ids:
        return jsonify({'error': 'No plot owners to message'}), 400

    messages_created = []
    for rid in recipient_ids:
        msg = GardenMessage(
            garden_id=garden_id,
            sender_id=current_user.id,
            recipient_id=rid,
            subject=subject,
            body=body,
        )
        db.session.add(msg)
        messages_created.append(msg)

    db.session.commit()

    return jsonify({
        'message': f'Broadcast sent to {len(messages_created)} plot owner(s)',
        'recipients_count': len(messages_created),
    }), 201


# ===================================================================
# 12. GET /{id}/admin/messages/{msg_id} — Read single message
# ===================================================================

@garden_admin_api.route('/<int:garden_id>/messages/<int:msg_id>', methods=['GET'])
@login_required
def admin_read_message(garden_id, msg_id):
    garden, err = require_garden_admin(garden_id)
    if err:
        return err

    msg = GardenMessage.query.get(msg_id)
    if not msg or msg.garden_id != garden_id:
        return jsonify({'error': 'Message not found in this garden'}), 404

    # Ensure admin is sender or recipient
    if msg.sender_id != current_user.id and msg.recipient_id != current_user.id:
        return jsonify({'error': 'Not authorized to view this message'}), 403

    # Mark as read if admin is the recipient
    if msg.recipient_id == current_user.id and not msg.is_read:
        msg.is_read = True
        db.session.commit()

    return jsonify(message_to_dict(msg))


# ===================================================================
# 13. GET /{id}/admin/photos — List photos for moderation
# ===================================================================

@garden_admin_api.route('/<int:garden_id>/photos', methods=['GET'])
@login_required
def admin_list_photos(garden_id):
    garden, err = require_garden_admin(garden_id)
    if err:
        return err

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    per_page = min(per_page, 100)
    category = request.args.get('category', '').strip()

    q = GardenPhoto.query.filter_by(garden_id=garden_id)

    if category:
        valid_categories = ('general', 'harvest', 'plot', 'event', 'wildlife', 'bloom')
        if category not in valid_categories:
            return jsonify({'error': f'Invalid category. Must be one of: {", ".join(valid_categories)}'}), 400
        q = q.filter_by(category=category)

    q = q.order_by(GardenPhoto.created_at.desc())
    pagination = q.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'photos': [photo_to_dict(p) for p in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'page': pagination.page,
        'has_next': pagination.has_next,
        'has_prev': pagination.has_prev,
    })


# ===================================================================
# 14. POST /{id}/admin/photos — Post a photo
# ===================================================================

@garden_admin_api.route('/<int:garden_id>/photos', methods=['POST'])
@login_required
def admin_post_photo(garden_id):
    garden, err = require_garden_admin(garden_id)
    if err:
        return err

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    photo_url = (data.get('photo_url') or '').strip()
    if not photo_url:
        return jsonify({'error': 'photo_url is required'}), 400

    category = data.get('category', 'general')
    valid_categories = ('general', 'harvest', 'plot', 'event', 'wildlife', 'bloom')
    if category not in valid_categories:
        return jsonify({'error': f'Invalid category. Must be one of: {", ".join(valid_categories)}'}), 400

    photo = GardenPhoto(
        garden_id=garden_id,
        user_id=current_user.id,
        photo_url=photo_url,
        caption=(data.get('caption') or '').strip(),
        category=category,
    )
    db.session.add(photo)
    db.session.commit()

    return jsonify(photo_to_dict(photo)), 201


# ===================================================================
# 15. DELETE /{id}/admin/photos/{photo_id} — Delete any photo
# ===================================================================

@garden_admin_api.route('/<int:garden_id>/photos/<int:photo_id>', methods=['DELETE'])
@login_required
def admin_delete_photo(garden_id, photo_id):
    garden, err = require_garden_admin(garden_id)
    if err:
        return err

    photo = GardenPhoto.query.get(photo_id)
    if not photo or photo.garden_id != garden_id:
        return jsonify({'error': 'Photo not found in this garden'}), 404

    # Delete related likes and comments first
    GardenPhotoLike.query.filter_by(photo_id=photo_id).delete()
    GardenPhotoComment.query.filter_by(photo_id=photo_id).delete()
    db.session.delete(photo)
    db.session.commit()

    return jsonify({'message': 'Photo deleted'})


# ===================================================================
# 16. POST /{id}/admin/photos/{photo_id}/like — Like/unlike toggle
# ===================================================================

@garden_admin_api.route('/<int:garden_id>/photos/<int:photo_id>/like', methods=['POST'])
@login_required
def admin_toggle_photo_like(garden_id, photo_id):
    garden, err = require_garden_admin(garden_id)
    if err:
        return err

    photo = GardenPhoto.query.get(photo_id)
    if not photo or photo.garden_id != garden_id:
        return jsonify({'error': 'Photo not found in this garden'}), 404

    existing = GardenPhotoLike.query.filter_by(
        photo_id=photo_id, user_id=current_user.id
    ).first()

    if existing:
        db.session.delete(existing)
        photo.likes_count = max(0, photo.likes_count - 1)
        liked = False
    else:
        like = GardenPhotoLike(photo_id=photo_id, user_id=current_user.id)
        db.session.add(like)
        photo.likes_count = photo.likes_count + 1
        liked = True

    db.session.commit()

    return jsonify({
        'photo_id': photo_id,
        'liked': liked,
        'likes_count': photo.likes_count,
    })


# ===================================================================
# 17. POST /{id}/admin/photos/{photo_id}/comments — Add comment
# ===================================================================

@garden_admin_api.route('/<int:garden_id>/photos/<int:photo_id>/comments', methods=['POST'])
@login_required
def admin_add_photo_comment(garden_id, photo_id):
    garden, err = require_garden_admin(garden_id)
    if err:
        return err

    photo = GardenPhoto.query.get(photo_id)
    if not photo or photo.garden_id != garden_id:
        return jsonify({'error': 'Photo not found in this garden'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    content = (data.get('content') or '').strip()
    if not content:
        return jsonify({'error': 'Comment content is required'}), 400

    comment = GardenPhotoComment(
        photo_id=photo_id,
        user_id=current_user.id,
        content=content,
    )
    db.session.add(comment)
    db.session.commit()

    return jsonify(comment_to_dict(comment)), 201


# ===================================================================
# 18. GET /{id}/admin/photos/{photo_id}/comments — Get comments
# ===================================================================

@garden_admin_api.route('/<int:garden_id>/photos/<int:photo_id>/comments', methods=['GET'])
@login_required
def admin_get_photo_comments(garden_id, photo_id):
    garden, err = require_garden_admin(garden_id)
    if err:
        return err

    photo = GardenPhoto.query.get(photo_id)
    if not photo or photo.garden_id != garden_id:
        return jsonify({'error': 'Photo not found in this garden'}), 404

    comments = photo.comments.all()
    return jsonify([comment_to_dict(c) for c in comments])


# ===================================================================
# 19. PUT /{id}/admin/settings — Update garden settings
# ===================================================================

@garden_admin_api.route('/<int:garden_id>/settings', methods=['PUT'])
@login_required
def admin_update_settings(garden_id):
    garden, err = require_garden_admin(garden_id)
    if err:
        return err

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    # String fields
    if 'name' in data:
        name = data['name'].strip()
        if not name:
            return jsonify({'error': 'Garden name cannot be empty'}), 400
        garden.name = name
    if 'description' in data:
        garden.description = data['description']
    if 'address' in data:
        garden.address = data['address']
    if 'city' in data:
        garden.city = data['city']
    if 'state' in data:
        garden.state = data['state']
    if 'zip_code' in data:
        garden.zip_code = data['zip_code']
    if 'rules' in data:
        garden.rules = data['rules']
    if 'contact_email' in data:
        garden.contact_email = data['contact_email']
    if 'photo_url' in data:
        garden.photo_url = data['photo_url']
    if 'operating_model' in data:
        garden.operating_model = data['operating_model']

    # Numeric fields
    if 'plot_fee_annual' in data:
        try:
            garden.plot_fee_annual = float(data['plot_fee_annual'])
        except (TypeError, ValueError):
            return jsonify({'error': 'plot_fee_annual must be a number'}), 400

    # Date fields
    if 'season_start' in data:
        if data['season_start']:
            try:
                garden.season_start = datetime.strptime(data['season_start'], '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'error': 'season_start must be in YYYY-MM-DD format'}), 400
        else:
            garden.season_start = None
    if 'season_end' in data:
        if data['season_end']:
            try:
                garden.season_end = datetime.strptime(data['season_end'], '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'error': 'season_end must be in YYYY-MM-DD format'}), 400
        else:
            garden.season_end = None

    # Boolean
    if 'is_active' in data:
        garden.is_active = bool(data['is_active'])

    db.session.commit()

    return jsonify({
        'message': 'Settings updated',
        'garden': {
            'id': garden.id,
            'name': garden.name,
            'description': garden.description,
            'address': garden.address,
            'city': garden.city,
            'state': garden.state,
            'zip_code': garden.zip_code,
            'photo_url': garden.photo_url,
            'rules': garden.rules,
            'contact_email': garden.contact_email,
            'plot_fee_annual': garden.plot_fee_annual,
            'operating_model': garden.operating_model,
            'season_start': garden.season_start.isoformat() if garden.season_start else None,
            'season_end': garden.season_end.isoformat() if garden.season_end else None,
            'is_active': garden.is_active,
        },
    })


# ===================================================================
# 20. GET /{id}/admin/activity — Recent activity feed
# ===================================================================

@garden_admin_api.route('/<int:garden_id>/activity', methods=['GET'])
@login_required
def admin_activity_feed(garden_id):
    garden, err = require_garden_admin(garden_id)
    if err:
        return err

    activities = []

    # New plot assignments (members)
    recent_assignments = garden.plots.filter(
        GardenPlot.status == 'assigned',
        GardenPlot.assigned_date != None,  # noqa: E711
    ).order_by(GardenPlot.assigned_date.desc()).limit(20).all()

    for plot in recent_assignments:
        if plot.assigned_to and plot.assigned_date:
            activities.append({
                'type': 'new_member',
                'date': datetime.combine(plot.assigned_date, datetime.min.time()).replace(
                    tzinfo=timezone.utc
                ).isoformat(),
                'description': f'{plot.assigned_to.display_name or plot.assigned_to.username} assigned to plot {plot.plot_number}',
                'user_id': plot.assigned_to_id,
                'user_name': plot.assigned_to.display_name or plot.assigned_to.username,
            })

    # Recent harvests
    recent_harvests = HarvestLog.query.filter_by(
        garden_id=garden_id
    ).order_by(HarvestLog.created_at.desc()).limit(20).all()

    for h in recent_harvests:
        activities.append({
            'type': 'harvest',
            'date': h.created_at.isoformat() if h.created_at else None,
            'description': f'{h.user.display_name or h.user.username} harvested {h.quantity_lbs} lbs of {h.variety or h.category}',
            'user_id': h.user_id,
            'user_name': h.user.display_name or h.user.username,
        })

    # Recent RSVPs
    recent_rsvps = db.session.query(EventRSVP).join(GardenEvent).filter(
        GardenEvent.garden_id == garden_id
    ).order_by(EventRSVP.id.desc()).limit(20).all()

    for rsvp in recent_rsvps:
        event = GardenEvent.query.get(rsvp.event_id)
        user = User.query.get(rsvp.user_id)
        if event and user:
            activities.append({
                'type': 'rsvp',
                'date': event.created_at.isoformat() if event.created_at else None,
                'description': f'{user.display_name or user.username} RSVPed "{rsvp.status}" to {event.title}',
                'user_id': rsvp.user_id,
                'user_name': user.display_name or user.username,
            })

    # Recent photos
    recent_photos = GardenPhoto.query.filter_by(
        garden_id=garden_id
    ).order_by(GardenPhoto.created_at.desc()).limit(20).all()

    for p in recent_photos:
        activities.append({
            'type': 'photo',
            'date': p.created_at.isoformat() if p.created_at else None,
            'description': f'{p.user.display_name or p.user.username} posted a photo' + (f': {p.caption[:50]}' if p.caption else ''),
            'user_id': p.user_id,
            'user_name': p.user.display_name or p.user.username,
            'photo_url': p.photo_url,
        })

    # Sort all activities by date descending and take the latest 20
    activities.sort(key=lambda a: a.get('date') or '', reverse=True)
    activities = activities[:20]

    return jsonify(activities)


# ===================================================================
# 21. PUT /{id}/admin/events/{event_id} — Edit an event
# ===================================================================

@garden_admin_api.route('/<int:garden_id>/events/<int:event_id>', methods=['PUT'])
@login_required
def admin_edit_event(garden_id, event_id):
    garden, err = require_garden_admin(garden_id)
    if err:
        return err

    event = GardenEvent.query.get(event_id)
    if not event or event.garden_id != garden_id:
        return jsonify({'error': 'Event not found in this garden'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    if 'title' in data:
        title = data['title'].strip()
        if not title:
            return jsonify({'error': 'Title cannot be empty'}), 400
        event.title = title
    if 'description' in data:
        event.description = data['description']
    if 'event_type' in data:
        event.event_type = data['event_type']
    if 'event_date' in data:
        try:
            event.event_date = datetime.fromisoformat(data['event_date'])
        except (ValueError, TypeError):
            return jsonify({'error': 'event_date must be a valid ISO date string'}), 400
    if 'duration_hours' in data:
        try:
            event.duration_hours = float(data['duration_hours'])
        except (TypeError, ValueError):
            return jsonify({'error': 'duration_hours must be a number'}), 400
    if 'max_volunteers' in data:
        event.max_volunteers = data['max_volunteers']

    db.session.commit()
    return jsonify(event_to_dict_admin(event))


# ===================================================================
# 22. DELETE /{id}/admin/events/{event_id} — Delete an event
# ===================================================================

@garden_admin_api.route('/<int:garden_id>/events/<int:event_id>', methods=['DELETE'])
@login_required
def admin_delete_event(garden_id, event_id):
    garden, err = require_garden_admin(garden_id)
    if err:
        return err

    event = GardenEvent.query.get(event_id)
    if not event or event.garden_id != garden_id:
        return jsonify({'error': 'Event not found in this garden'}), 404

    # Delete related RSVPs first
    EventRSVP.query.filter_by(event_id=event_id).delete()
    db.session.delete(event)
    db.session.commit()

    return jsonify({'message': 'Event deleted'})


# ===================================================================
# 23. GET /{id}/admin/events/{event_id}/attendees — List RSVPs
# ===================================================================

@garden_admin_api.route('/<int:garden_id>/events/<int:event_id>/attendees', methods=['GET'])
@login_required
def admin_event_attendees(garden_id, event_id):
    garden, err = require_garden_admin(garden_id)
    if err:
        return err

    event = GardenEvent.query.get(event_id)
    if not event or event.garden_id != garden_id:
        return jsonify({'error': 'Event not found in this garden'}), 404

    rsvps = event.rsvps.all()
    attendees = []
    for rsvp in rsvps:
        user = User.query.get(rsvp.user_id)
        if user:
            attendees.append({
                'user_id': user.id,
                'username': user.username,
                'display_name': user.display_name,
                'email': user.email,
                'status': rsvp.status,
            })

    # Group by status for summary
    going = [a for a in attendees if a['status'] == 'going']
    maybe = [a for a in attendees if a['status'] == 'maybe']
    not_going = [a for a in attendees if a['status'] == 'not_going']

    return jsonify({
        'event_id': event_id,
        'event_title': event.title,
        'summary': {
            'going': len(going),
            'maybe': len(maybe),
            'not_going': len(not_going),
            'total': len(attendees),
        },
        'attendees': attendees,
    })
