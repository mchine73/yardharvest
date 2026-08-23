"""Garden Admin Portal REST API endpoints.

Admin-specific endpoints for community garden management.
All routes are under /api/gardens/{id}/admin/ to avoid conflicts
with the public gardens_api endpoints.
"""
import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.api.token_auth import token_or_session, get_current_user
from app import db, limiter
from app.tasks import run_async

log = logging.getLogger(__name__)
from app.models import (
    CommunityGarden, GardenPlot, GardenWaitlist, SharedResource, ResourceCheckoutLog,
    GardenEvent, EventRSVP, HarvestLog, GardenAnnouncement,
    GardenMessage, GardenPhoto, GardenPhotoComment, GardenPhotoLike,
    User, GardenEmailConfig, VolunteerShift, ShiftSignup,
    GardenDuesRecord, GardenExpense, GardenWeatherAlert,
    PlotAssignmentHistory, GardenMembership,
    GardenLayoutDraft, GardenComment, GardenLayoutFeature
)
from app.email_service import send_garden_announcement
from app.api.notifications_api import notify
from app.api.garden_billing_api import require_garden_pro
from datetime import datetime, timezone, date, time as dtime, timedelta
from sqlalchemy import or_, func
from sqlalchemy.orm import joinedload

garden_admin_api = Blueprint('garden_admin_api', __name__, url_prefix='/api/garden-admin')


@garden_admin_api.url_value_preprocessor
def _resolve_garden_url_value(endpoint, values):
    """Resolve an opaque ``grd_…`` public_id (or numeric PK) in the URL to the
    integer ``garden_id`` before any handler runs."""
    if values and 'garden_id' in values:
        from app.helpers import resolve_garden_pk
        values['garden_id'] = resolve_garden_pk(values['garden_id'])


# ---------------------------------------------------------------------------
# Helper: verify the current user is the garden organizer or a site admin
# ---------------------------------------------------------------------------

def require_garden_admin(garden_id):
    """Return (garden, None) if authorised, or (None, error_response) if not."""
    garden = db.session.get(CommunityGarden, garden_id)
    if not garden:
        return None, (jsonify({'error': 'Garden not found'}), 404)
    if garden.organizer_id != get_current_user().id and not get_current_user().is_admin:
        return None, (jsonify({'error': 'Not authorized — admin access required'}), 403)
    return garden, None


def require_garden_admin_pro(garden_id):
    """Return (garden, None) if authorised AND has Pro subscription, else error.

    Use this for Pro-gated endpoints (financial, shifts, photos, messaging,
    email config, plot grid editor, maintenance).
    """
    garden, err = require_garden_admin(garden_id)
    if err:
        return None, err
    allowed, pro_err = require_garden_pro(garden)
    if not allowed:
        return None, pro_err
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
        # Surfaced so the admin sees exactly where SMS/email would be delivered.
        'recipient_email': msg.recipient.email if msg.recipient else None,
        'recipient_phone': (msg.recipient.phone_number if msg.recipient and msg.recipient.sms_opt_in else None),
        'subject': msg.subject,
        'body': msg.body,
        'is_read': msg.is_read,
        'created_at': msg.created_at.isoformat() if msg.created_at else None,
    }


def photo_to_dict(photo, comments_count=None):
    # comments_count may be supplied by the caller (computed in bulk for a page
    # of photos) to avoid a per-photo COUNT query; falls back to a lazy count.
    return {
        'id': photo.id,
        'garden_id': photo.garden_id,
        'user_id': photo.user_id,
        'user_name': photo.user.display_name or photo.user.username,
        'photo_url': photo.photo_url,
        'caption': photo.caption,
        'category': photo.category,
        'likes_count': photo.likes_count,
        'comments_count': comments_count if comments_count is not None else photo.comments.count(),
        'created_at': photo.created_at.isoformat() if photo.created_at else None,
    }


def _photo_comment_counts(photo_ids):
    """Return {photo_id: comment_count} for a list of photo ids in one query."""
    if not photo_ids:
        return {}
    rows = (db.session.query(GardenPhotoComment.photo_id, func.count(GardenPhotoComment.id))
            .filter(GardenPhotoComment.photo_id.in_(photo_ids))
            .group_by(GardenPhotoComment.photo_id).all())
    return {pid: cnt for pid, cnt in rows}


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
        'recurring': event.recurring or 'none',
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

@garden_admin_api.route('/<garden_id>/dashboard', methods=['GET'])
@token_or_session
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
        recipient_id=get_current_user().id,
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

@garden_admin_api.route('/<garden_id>/plots', methods=['GET'])
@token_or_session
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
            'reserved_by_id': plot.reserved_by_id,
            'reserved_by_name': None,
            'reserved_at': plot.reserved_at.isoformat() if plot.reserved_at else None,
            'harvest_total_lbs': 0.0,
            'harvest_count': 0,
            'grid_row': plot.grid_row,
            'grid_col': plot.grid_col,
            'custom_name': plot.custom_name or '',
            'soil_type': plot.soil_type or '',
            'sun_exposure': plot.sun_exposure or '',
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

        if plot.reserved_by:
            ruser = plot.reserved_by
            d['reserved_by_name'] = ruser.display_name or ruser.username

        result.append(d)

    return jsonify(result)


# ===================================================================
#  3. PUT /{id}/admin/plots/{plot_id} — Edit plot details
# ===================================================================

@garden_admin_api.route('/<garden_id>/plots/<int:plot_id>', methods=['PUT'])
@token_or_session
def admin_edit_plot(garden_id, plot_id):
    garden, err = require_garden_admin(garden_id)
    if err:
        return err

    plot = db.session.get(GardenPlot, plot_id)
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
    if 'custom_name' in data:
        plot.custom_name = data['custom_name'].strip() if data['custom_name'] else None
    if 'soil_type' in data:
        plot.soil_type = data['soil_type'] or None
    if 'sun_exposure' in data:
        plot.sun_exposure = data['sun_exposure'] or None

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
#  3b. PUT /{id}/admin/plot-layout — Bulk update plot grid positions
# ===================================================================

@garden_admin_api.route('/<garden_id>/plot-layout', methods=['PUT'])
@token_or_session
def update_plot_layout(garden_id):
    """Save the garden layout: grid dimensions, plot placements (rectangular
    spans + rounded flag), and non-plot features ("dead zones" — sheds, paths,
    landscaping, etc.). Validates bounds and rejects overlaps so the map stays
    consistent. Features are replaced wholesale with the submitted set."""
    garden, err = require_garden_admin_pro(garden_id)
    if err:
        return err

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    rows = max(1, min(int(data.get('grid_rows', garden.grid_rows or 4)), 60))
    cols = max(1, min(int(data.get('grid_cols', garden.grid_cols or 5)), 60))

    occupied = {}  # (r, c) -> human label, for overlap + bounds checks

    def claim(r0, c0, w, h, what):
        w, h = max(1, int(w or 1)), max(1, int(h or 1))
        for r in range(r0, r0 + h):
            for c in range(c0, c0 + w):
                if not (0 <= r < rows and 0 <= c < cols):
                    return f'{what} falls outside the {rows}×{cols} grid.'
                if (r, c) in occupied:
                    return f'{what} overlaps {occupied[(r, c)]}.'
                occupied[(r, c)] = what
        return None

    # ---- Validate + stage plots ----
    plot_updates = []  # (plot, row|None, col|None, w, h, rounded)
    for pd in data.get('plots', []):
        plot = db.session.get(GardenPlot, pd.get('id'))
        if not plot or plot.garden_id != garden.id:
            continue
        gr, gc = pd.get('grid_row'), pd.get('grid_col')
        if gr is None or gc is None:
            plot_updates.append((plot, None, None, 1, 1, bool(pd.get('rounded'))))
            continue
        w, h = pd.get('grid_width', 1), pd.get('grid_height', 1)
        msg = claim(int(gr), int(gc), w, h, f'Plot {plot.plot_number}')
        if msg:
            return jsonify({'error': msg}), 400
        plot_updates.append((plot, int(gr), int(gc),
                             max(1, int(w or 1)), max(1, int(h or 1)),
                             bool(pd.get('rounded'))))

    # ---- Validate features (full replace) ----
    feature_rows = []
    for fd in data.get('features', []):
        try:
            gr, gc = int(fd['grid_row']), int(fd['grid_col'])
        except (KeyError, TypeError, ValueError):
            continue
        w, h = fd.get('grid_width', 1), fd.get('grid_height', 1)
        ftype = (fd.get('feature_type') or 'other')[:30]
        label = (fd.get('label') or '').strip()[:60]
        msg = claim(gr, gc, w, h, label or ftype)
        if msg:
            return jsonify({'error': msg}), 400
        feature_rows.append({
            'feature_type': ftype, 'label': label or None,
            'grid_row': gr, 'grid_col': gc,
            'grid_width': max(1, int(w or 1)), 'grid_height': max(1, int(h or 1)),
            'color': (fd.get('color') or '').strip()[:20] or None,
            'rounded': bool(fd.get('rounded')),
        })

    # ---- Apply (everything validated) ----
    garden.grid_rows, garden.grid_cols = rows, cols
    for plot, gr, gc, w, h, rnd in plot_updates:
        plot.grid_row, plot.grid_col = gr, gc
        plot.grid_width, plot.grid_height = w, h
        plot.rounded = rnd
    GardenLayoutFeature.query.filter_by(garden_id=garden.id).delete()
    for fr in feature_rows:
        db.session.add(GardenLayoutFeature(garden_id=garden.id, **fr))

    db.session.commit()
    return jsonify({'success': True})


# ===================================================================
#  4. PUT /{id}/admin/plots/{plot_id}/maintenance — Toggle maintenance
# ===================================================================

@garden_admin_api.route('/<garden_id>/plots/<int:plot_id>/maintenance', methods=['PUT'])
@token_or_session
def admin_toggle_maintenance(garden_id, plot_id):
    garden, err = require_garden_admin_pro(garden_id)
    if err:
        return err

    plot = db.session.get(GardenPlot, plot_id)
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

@garden_admin_api.route('/<garden_id>/announcements', methods=['POST'])
@token_or_session
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
        author_id=get_current_user().id,
        title=title,
        body=body,
        priority=priority,
        pinned=bool(data.get('pinned', False)),
    )
    db.session.add(ann)
    db.session.commit()

    # Notify all garden members (plot holders) about the announcement.
    # In-app notifications are DB writes — do them synchronously so they're
    # durable and transactional. Email + SMS are external provider calls that
    # can be slow at scale, so they fan out in the background (plain strings
    # only — never ORM objects, which detach once this request's session ends).
    try:
        assigned_plots = garden.plots.filter_by(status='assigned').all()
        member_ids = list({p.assigned_to_id for p in assigned_plots if p.assigned_to_id})
        if member_ids:
            members = User.query.filter(User.id.in_(member_ids)).all()
            member_emails = [m.email for m in members if m.email]
            sms_targets = [m.phone_number for m in members
                           if m.sms_opt_in and m.phone_number]

            for m in members:
                notify(
                    user_id=m.id,
                    type='announcement',
                    title=f'{garden.name}: {title}',
                    body=body[:200],
                    link=f'/gardens/{garden.public_id}',
                    garden_id=garden_id,
                )
            db.session.commit()

            # Fan out external sends off the request path.
            garden_name = garden.name
            if member_emails:
                run_async(send_garden_announcement, garden_name, title, body,
                          priority, member_emails, garden_id=garden_id)
            if sms_targets:
                run_async(_send_announcement_sms_batch, sms_targets, garden_name, title)
    except Exception:
        log.exception('Announcement fan-out failed for garden %d', garden_id)

    return jsonify(announcement_to_dict(ann)), 201


def _send_announcement_sms_batch(phone_numbers, garden_name, title):
    """Send announcement SMS to each opted-in member. Runs in a background
    thread; per-recipient failures are logged and do not stop the batch."""
    from app.sms_service import send_announcement_sms
    for phone in phone_numbers:
        try:
            send_announcement_sms(phone, garden_name, title)
        except Exception:
            log.exception('Announcement SMS to %s failed', phone)


# ===================================================================
#  6. GET /{id}/admin/announcements — List announcements (paginated)
# ===================================================================

@garden_admin_api.route('/<garden_id>/announcements', methods=['GET'])
@token_or_session
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

@garden_admin_api.route('/<garden_id>/announcements/<int:ann_id>', methods=['PUT'])
@token_or_session
def admin_edit_announcement(garden_id, ann_id):
    garden, err = require_garden_admin(garden_id)
    if err:
        return err

    ann = db.session.get(GardenAnnouncement, ann_id)
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

@garden_admin_api.route('/<garden_id>/announcements/<int:ann_id>', methods=['DELETE'])
@token_or_session
def admin_delete_announcement(garden_id, ann_id):
    garden, err = require_garden_admin(garden_id)
    if err:
        return err

    ann = db.session.get(GardenAnnouncement, ann_id)
    if not ann or ann.garden_id != garden_id:
        return jsonify({'error': 'Announcement not found in this garden'}), 404

    db.session.delete(ann)
    db.session.commit()
    return jsonify({'message': 'Announcement deleted'})


# ===================================================================
#  9. GET /{id}/admin/messages — List garden messages for admin
# ===================================================================

@garden_admin_api.route('/<garden_id>/messages', methods=['GET'])
@token_or_session
def admin_list_messages(garden_id):
    garden, err = require_garden_admin_pro(garden_id)
    if err:
        return err

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    per_page = min(per_page, 100)

    # Messages sent or received by the admin within this garden
    q = GardenMessage.query.filter(
        GardenMessage.garden_id == garden_id,
        or_(
            GardenMessage.sender_id == get_current_user().id,
            GardenMessage.recipient_id == get_current_user().id,
        )
    ).order_by(GardenMessage.created_at.desc()).options(
        joinedload(GardenMessage.sender), joinedload(GardenMessage.recipient),
    )

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

@garden_admin_api.route('/<garden_id>/messages', methods=['POST'])
@token_or_session
def admin_send_message(garden_id):
    garden, err = require_garden_admin_pro(garden_id)
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

    recipient = db.session.get(User, recipient_id)
    if not recipient:
        return jsonify({'error': 'Recipient not found'}), 404

    # Delivery channels the admin opted into: 'platform' (in-app, default),
    # 'email', 'sms'. The message is always recorded; email/SMS are extra.
    channels = data.get('channels') or ['platform']
    if isinstance(channels, str):
        channels = [channels]
    channels = {c.lower() for c in channels} or {'platform'}

    msg = GardenMessage(
        garden_id=garden_id,
        sender_id=get_current_user().id,
        recipient_id=recipient_id,
        subject=subject,
        body=body,
    )
    db.session.add(msg)

    sender_name = get_current_user().display_name or get_current_user().username
    # Platform delivery = in-app notification (always create the record; only
    # raise the notification when 'platform' was chosen).
    if 'platform' in channels:
        notify(
            user_id=recipient_id,
            type='message',
            title=f'Message from {sender_name}',
            body=(subject or body[:100]),
            link=f'/gardens/{garden.public_id}',
            garden_id=garden_id,
        )
    db.session.commit()

    delivered = ['platform'] if 'platform' in channels else []
    # Email + SMS fan out off the request path (plain strings only).
    if 'email' in channels and recipient.email:
        gname = garden.name
        subj = subject or f'Message from {gname}'
        run_async(_send_garden_dm_email, recipient.email,
                  recipient.display_name or recipient.username, gname, subj, body)
        delivered.append('email')
    if 'sms' in channels and recipient.sms_opt_in and recipient.phone_number:
        run_async(_send_garden_dm_sms, recipient.phone_number, garden.name, body)
        delivered.append('sms')

    out = message_to_dict(msg)
    out['delivered_via'] = delivered
    return jsonify(out), 201


def _send_garden_dm_email(to_email, to_name, garden_name, subject, body):
    """Background: deliver a garden admin direct message by email."""
    try:
        from app.email_service import send_email, _render, _esc
        content = (f'<h2>{_esc(subject)}</h2><p>Hi {_esc(to_name)},</p>'
                   f'<p>{_esc(body)}</p>'
                   f'<p style="color:#888;font-size:13px;">Sent via {_esc(garden_name)} on YardHarvest.</p>')
        send_email(to_email, subject, _render(content), from_name=garden_name)
    except Exception:
        log.exception('Garden DM email to %s failed', to_email)


def _send_garden_dm_sms(phone, garden_name, body):
    """Background: deliver a garden admin direct message by SMS."""
    try:
        from app.sms_service import send_sms
        send_sms(phone, f'{garden_name}: {body[:300]}')
    except Exception:
        log.exception('Garden DM SMS to %s failed', phone)


# ===================================================================
# 11. POST /{id}/admin/messages/broadcast — Broadcast to all plot owners
# ===================================================================

@garden_admin_api.route('/<garden_id>/messages/broadcast', methods=['POST'])
@token_or_session
def admin_broadcast_message(garden_id):
    garden, err = require_garden_admin_pro(garden_id)
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
            sender_id=get_current_user().id,
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


@garden_admin_api.route('/<garden_id>/messages/<int:msg_id>', methods=['PUT'])
@token_or_session
def admin_edit_message(garden_id, msg_id):
    """Edit a sent message (subject/body) — sender only, like announcements."""
    garden, err = require_garden_admin_pro(garden_id)
    if err:
        return err
    msg = db.get_or_404(GardenMessage, msg_id)
    if msg.garden_id != garden_id:
        return jsonify({'error': 'Message not in this garden'}), 400
    if msg.sender_id != get_current_user().id and not get_current_user().is_admin:
        return jsonify({'error': 'Only the sender can edit this message'}), 403
    data = request.get_json() or {}
    if 'subject' in data:
        msg.subject = (data['subject'] or '').strip()
    if 'body' in data:
        body = (data['body'] or '').strip()
        if not body:
            return jsonify({'error': 'Message body cannot be empty'}), 400
        msg.body = body
    db.session.commit()
    return jsonify(message_to_dict(msg))


@garden_admin_api.route('/<garden_id>/messages/<int:msg_id>', methods=['DELETE'])
@token_or_session
def admin_delete_message(garden_id, msg_id):
    """Delete a sent message — sender (or admin) only, like announcements."""
    garden, err = require_garden_admin_pro(garden_id)
    if err:
        return err
    msg = db.get_or_404(GardenMessage, msg_id)
    if msg.garden_id != garden_id:
        return jsonify({'error': 'Message not in this garden'}), 400
    if msg.sender_id != get_current_user().id and not get_current_user().is_admin:
        return jsonify({'error': 'Only the sender can delete this message'}), 403
    db.session.delete(msg)
    db.session.commit()
    return jsonify({'message': 'Message deleted'})


# ===================================================================
#  FINANCE — CSV export (dues + expenses)
# ===================================================================

@garden_admin_api.route('/<garden_id>/finance/export', methods=['GET'])
@token_or_session
def export_finance_csv(garden_id):
    """Export the garden's finances as a CSV download.

    ?kind=dues (default) | expenses ; optional ?season=YYYY for dues.
    """
    import csv
    import io
    from flask import Response

    garden, err = require_garden_admin_pro(garden_id)
    if err:
        return err

    kind = (request.args.get('kind') or 'dues').lower()
    slug = garden.name.lower().replace(' ', '-')[:30]
    buf = io.StringIO()
    writer = csv.writer(buf)

    if kind == 'expenses':
        writer.writerow(['Date', 'Title', 'Category', 'Amount', 'Paid By', 'Notes'])
        expenses = (GardenExpense.query.filter_by(garden_id=garden_id)
                    .order_by(GardenExpense.expense_date.desc()).all())
        for e in expenses:
            writer.writerow([
                e.expense_date.isoformat() if e.expense_date else '',
                e.title or '', e.category or '', f'{e.amount:.2f}',
                e.paid_by or '', (e.notes or '').replace('\n', ' '),
            ])
        filename = f'{slug}-expenses.csv'
    else:
        season = request.args.get('season', type=int)
        writer.writerow(['Season', 'Member', 'Email', 'Amount Due', 'Amount Paid',
                         'Status', 'Method', 'Payment Date'])
        q = GardenDuesRecord.query.filter_by(garden_id=garden_id)
        if season:
            q = q.filter_by(season_year=season)
        records = q.order_by(GardenDuesRecord.season_year.desc()).all()
        for r in records:
            member = db.session.get(User, r.user_id)
            writer.writerow([
                r.season_year,
                (member.display_name or member.username) if member else f'User {r.user_id}',
                member.email if member else '',
                f'{r.amount_due:.2f}', f'{(r.amount_paid or 0):.2f}',
                r.status or '', r.payment_method or '',
                r.payment_date.isoformat() if r.payment_date else '',
            ])
        filename = f'{slug}-dues.csv'

    return Response(
        buf.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )


# ===================================================================
#  COMMUNITY WALL — comment moderation panel
# ===================================================================

def _admin_comment_to_dict(c):
    return {
        'id': c.id,
        'garden_id': c.garden_id,
        'author_id': c.author_id,
        'author_name': (c.author.display_name or c.author.username) if c.author else 'Member',
        'body': c.body,
        'status': c.status,
        'moderation_reason': c.moderation_reason,
        'created_at': c.created_at.isoformat() if c.created_at else None,
    }


@garden_admin_api.route('/<garden_id>/comments', methods=['GET'])
@token_or_session
def admin_list_comments(garden_id):
    """Moderation feed of the comment wall. ?status=all|flagged|approved|blocked.
    'all' is the live wall (approved + flagged); 'blocked' is the auto-denied feed
    (comments the AI moderator rejected — never shown publicly)."""
    garden, err = require_garden_admin(garden_id)
    if err:
        return err
    status = (request.args.get('status') or 'all').lower()
    q = GardenComment.query.options(joinedload(GardenComment.author)).filter_by(garden_id=garden_id)
    if status in ('flagged', 'approved', 'blocked'):
        q = q.filter(GardenComment.status == status)
    else:  # 'all' = the live wall; auto-denied posts have their own tab
        q = q.filter(GardenComment.status.in_(('approved', 'flagged')))
    comments = q.order_by(GardenComment.created_at.desc()).limit(500).all()
    flagged_count = GardenComment.query.filter_by(garden_id=garden_id, status='flagged').count()
    blocked_count = GardenComment.query.filter_by(garden_id=garden_id, status='blocked').count()
    return jsonify({
        'comments': [_admin_comment_to_dict(c) for c in comments],
        'flagged_count': flagged_count,
        'blocked_count': blocked_count,
        'total': len(comments),
    })


@garden_admin_api.route('/<garden_id>/comments/<int:comment_id>/approve', methods=['POST'])
@token_or_session
def admin_approve_comment(garden_id, comment_id):
    """Clear a flag — the comment stays public with status 'approved'."""
    garden, err = require_garden_admin(garden_id)
    if err:
        return err
    comment = db.get_or_404(GardenComment, comment_id)
    if comment.garden_id != garden_id:
        return jsonify({'error': 'Comment not in this garden'}), 400
    comment.status = 'approved'
    comment.moderation_reason = None
    db.session.commit()
    return jsonify(_admin_comment_to_dict(comment))


@garden_admin_api.route('/<garden_id>/comments/<int:comment_id>', methods=['DELETE'])
@token_or_session
def admin_delete_comment(garden_id, comment_id):
    """Remove a comment from the wall entirely."""
    garden, err = require_garden_admin(garden_id)
    if err:
        return err
    comment = db.get_or_404(GardenComment, comment_id)
    if comment.garden_id != garden_id:
        return jsonify({'error': 'Comment not in this garden'}), 400
    db.session.delete(comment)
    db.session.commit()
    return jsonify({'success': True})


# ===================================================================
# 12. GET /{id}/admin/messages/{msg_id} — Read single message
# ===================================================================

@garden_admin_api.route('/<garden_id>/messages/<int:msg_id>', methods=['GET'])
@token_or_session
def admin_read_message(garden_id, msg_id):
    garden, err = require_garden_admin_pro(garden_id)
    if err:
        return err

    msg = db.session.get(GardenMessage, msg_id)
    if not msg or msg.garden_id != garden_id:
        return jsonify({'error': 'Message not found in this garden'}), 404

    # Ensure admin is sender or recipient
    if msg.sender_id != get_current_user().id and msg.recipient_id != get_current_user().id:
        return jsonify({'error': 'Not authorized to view this message'}), 403

    # Mark as read if admin is the recipient
    if msg.recipient_id == get_current_user().id and not msg.is_read:
        msg.is_read = True
        db.session.commit()

    return jsonify(message_to_dict(msg))


# ===================================================================
# 13. GET /{id}/admin/photos — List photos for moderation
# ===================================================================

@garden_admin_api.route('/<garden_id>/photos', methods=['GET'])
@token_or_session
def admin_list_photos(garden_id):
    garden, err = require_garden_admin_pro(garden_id)
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

    q = q.order_by(GardenPhoto.created_at.desc()).options(joinedload(GardenPhoto.user))
    pagination = q.paginate(page=page, per_page=per_page, error_out=False)

    # One grouped query for all comment counts on this page (avoids N+1).
    counts = _photo_comment_counts([p.id for p in pagination.items])

    return jsonify({
        'photos': [photo_to_dict(p, comments_count=counts.get(p.id, 0)) for p in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'page': pagination.page,
        'has_next': pagination.has_next,
        'has_prev': pagination.has_prev,
    })


# ===================================================================
# 14. POST /{id}/admin/photos — Post a photo
# ===================================================================

@garden_admin_api.route('/<garden_id>/photos', methods=['POST'])
@token_or_session
def admin_post_photo(garden_id):
    garden, err = require_garden_admin_pro(garden_id)
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
        user_id=get_current_user().id,
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

@garden_admin_api.route('/<garden_id>/photos/<int:photo_id>', methods=['DELETE'])
@token_or_session
def admin_delete_photo(garden_id, photo_id):
    garden, err = require_garden_admin_pro(garden_id)
    if err:
        return err

    photo = db.session.get(GardenPhoto, photo_id)
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

@garden_admin_api.route('/<garden_id>/photos/<int:photo_id>/like', methods=['POST'])
@token_or_session
def admin_toggle_photo_like(garden_id, photo_id):
    garden, err = require_garden_admin_pro(garden_id)
    if err:
        return err

    photo = db.session.get(GardenPhoto, photo_id)
    if not photo or photo.garden_id != garden_id:
        return jsonify({'error': 'Photo not found in this garden'}), 404

    existing = GardenPhotoLike.query.filter_by(
        photo_id=photo_id, user_id=get_current_user().id
    ).first()

    if existing:
        db.session.delete(existing)
        photo.likes_count = max(0, photo.likes_count - 1)
        liked = False
    else:
        like = GardenPhotoLike(photo_id=photo_id, user_id=get_current_user().id)
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

@garden_admin_api.route('/<garden_id>/photos/<int:photo_id>/comments', methods=['POST'])
@token_or_session
def admin_add_photo_comment(garden_id, photo_id):
    garden, err = require_garden_admin_pro(garden_id)
    if err:
        return err

    photo = db.session.get(GardenPhoto, photo_id)
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
        user_id=get_current_user().id,
        content=content,
    )
    db.session.add(comment)
    db.session.commit()

    return jsonify(comment_to_dict(comment)), 201


# ===================================================================
# 18. GET /{id}/admin/photos/{photo_id}/comments — Get comments
# ===================================================================

@garden_admin_api.route('/<garden_id>/photos/<int:photo_id>/comments', methods=['GET'])
@token_or_session
def admin_get_photo_comments(garden_id, photo_id):
    garden, err = require_garden_admin_pro(garden_id)
    if err:
        return err

    photo = db.session.get(GardenPhoto, photo_id)
    if not photo or photo.garden_id != garden_id:
        return jsonify({'error': 'Photo not found in this garden'}), 404

    comments = photo.comments.all()
    return jsonify([comment_to_dict(c) for c in comments])


# ===================================================================
# 19. PUT /{id}/admin/settings — Update garden settings
# ===================================================================

@garden_admin_api.route('/<garden_id>/settings', methods=['PUT'])
@token_or_session
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

    # Integer fields
    if 'max_checkouts_per_member' in data:
        try:
            garden.max_checkouts_per_member = max(1, min(10, int(data['max_checkouts_per_member'])))
        except (TypeError, ValueError):
            garden.max_checkouts_per_member = 3

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

@garden_admin_api.route('/<garden_id>/activity', methods=['GET'])
@token_or_session
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
        event = db.session.get(GardenEvent, rsvp.event_id)
        user = db.session.get(User, rsvp.user_id)
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

@garden_admin_api.route('/<garden_id>/events/<int:event_id>', methods=['PUT'])
@token_or_session
def admin_edit_event(garden_id, event_id):
    garden, err = require_garden_admin(garden_id)
    if err:
        return err

    event = db.session.get(GardenEvent, event_id)
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
    if 'recurring' in data:
        recurring = data['recurring'] or 'none'
        if recurring not in ('none', 'weekly', 'biweekly', 'monthly'):
            return jsonify({'error': 'recurring must be one of none, weekly, biweekly, monthly'}), 400
        # Editing only updates this occurrence's cadence label; it does not
        # regenerate the series (consistent with volunteer-shift edits).
        event.recurring = recurring

    db.session.commit()
    return jsonify(event_to_dict_admin(event))


# ===================================================================
# 22. DELETE /{id}/admin/events/{event_id} — Delete an event
# ===================================================================

@garden_admin_api.route('/<garden_id>/events/<int:event_id>', methods=['DELETE'])
@token_or_session
def admin_delete_event(garden_id, event_id):
    garden, err = require_garden_admin(garden_id)
    if err:
        return err

    event = db.session.get(GardenEvent, event_id)
    if not event or event.garden_id != garden_id:
        return jsonify({'error': 'Event not found in this garden'}), 404

    # Capture RSVP'd users before deleting so they can be notified
    rsvp_user_ids = [r.user_id for r in
                     EventRSVP.query.filter_by(event_id=event_id).all()]
    event_title = event.title
    event_date = event.event_date.isoformat() if event.event_date else None

    # Delete related RSVPs first
    EventRSVP.query.filter_by(event_id=event_id).delete()
    db.session.delete(event)
    db.session.commit()

    # Notify everyone who had RSVP'd (email + in-app)
    if rsvp_user_ids:
        try:
            attendees = User.query.filter(User.id.in_(rsvp_user_ids)).all()
            emails = [u.email for u in attendees if u.email]
            if emails:
                from app.email_service import send_event_cancelled_email
                send_event_cancelled_email(garden.name, event_title, event_date,
                                           emails, garden_id=garden_id)
            for u in attendees:
                notify(
                    user_id=u.id,
                    type='event_cancelled',
                    title=f'Cancelled: {event_title}',
                    body=f'The event "{event_title}" at {garden.name} has been cancelled.',
                    link=f'/gardens/{garden.public_id}',
                    garden_id=garden_id,
                )
            db.session.commit()
        except Exception:
            pass  # logged inside send_email

    return jsonify({'message': 'Event deleted'})


# ===================================================================
# 23. GET /{id}/admin/events/{event_id}/attendees — List RSVPs
# ===================================================================

@garden_admin_api.route('/<garden_id>/events/<int:event_id>/attendees', methods=['GET'])
@token_or_session
def admin_event_attendees(garden_id, event_id):
    garden, err = require_garden_admin(garden_id)
    if err:
        return err

    event = db.session.get(GardenEvent, event_id)
    if not event or event.garden_id != garden_id:
        return jsonify({'error': 'Event not found in this garden'}), 404

    rsvps = event.rsvps.all()
    attendees = []
    for rsvp in rsvps:
        user = db.session.get(User, rsvp.user_id)
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


# ---------------------------------------------------------------------------
# Email Configuration (per-garden)
# ---------------------------------------------------------------------------

def _garden_email_config_to_dict(config):
    return {
        'garden_id': config.garden_id,
        'sender_name': config.sender_name or '',
        'subject_prefix': config.subject_prefix or '',
        'closing_text': config.closing_text or '',
        'accent_color': config.accent_color or '#2d6a2e',
    }


@garden_admin_api.route('/<garden_id>/email-config', methods=['GET'])
@token_or_session
def get_garden_email_config(garden_id):
    garden, err = require_garden_admin_pro(garden_id)
    if err:
        return err

    config = GardenEmailConfig.query.filter_by(garden_id=garden_id).first()
    if not config:
        config = GardenEmailConfig(garden_id=garden_id)
        db.session.add(config)
        db.session.commit()

    return jsonify(_garden_email_config_to_dict(config))


@garden_admin_api.route('/<garden_id>/email-config', methods=['PUT'])
@token_or_session
def update_garden_email_config(garden_id):
    garden, err = require_garden_admin_pro(garden_id)
    if err:
        return err

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    config = GardenEmailConfig.query.filter_by(garden_id=garden_id).first()
    if not config:
        config = GardenEmailConfig(garden_id=garden_id)
        db.session.add(config)

    if 'sender_name' in data:
        config.sender_name = (data['sender_name'] or '')[:100]
    if 'subject_prefix' in data:
        config.subject_prefix = (data['subject_prefix'] or '')[:50]
    if 'closing_text' in data:
        config.closing_text = (data['closing_text'] or '')[:300]
    if 'accent_color' in data:
        color = data['accent_color'] or '#2d6a2e'
        if len(color) <= 7:
            config.accent_color = color

    db.session.commit()
    return jsonify(_garden_email_config_to_dict(config))


@garden_admin_api.route('/<garden_id>/email-preview', methods=['GET'])
@token_or_session
def preview_garden_email(garden_id):
    """Preview an announcement email with garden-specific config."""
    garden, err = require_garden_admin_pro(garden_id)
    if err:
        return err

    from app.email_service import preview_email, _get_site_email_config
    config = _get_site_email_config()
    garden_config = GardenEmailConfig.query.filter_by(garden_id=garden_id).first()
    html = preview_email('announcement', config, garden_config=garden_config,
                         garden_name=garden.name)
    return jsonify({'html': html})


# ---------------------------------------------------------------------------
# Plot Reservation Management (Organizer confirms/declines user reservations)
# ---------------------------------------------------------------------------

@garden_admin_api.route('/<garden_id>/plots/<int:plot_id>/confirm', methods=['POST'])
@token_or_session
def confirm_reservation(garden_id, plot_id):
    """Organizer confirms a reserved plot -> status becomes 'assigned'."""
    garden, err = require_garden_admin(garden_id)
    if err:
        return err

    plot = db.get_or_404(GardenPlot, plot_id)
    if plot.garden_id != garden_id:
        return jsonify({'error': 'Plot not in this garden'}), 400
    if plot.status != 'reserved' or not plot.reserved_by_id:
        return jsonify({'error': 'Plot is not reserved'}), 400

    # Assign the plot to the user who reserved it
    reserved_user_id = plot.reserved_by_id
    plot.assigned_to_id = reserved_user_id
    plot.status = 'assigned'
    plot.assigned_date = datetime.now(timezone.utc).date()
    plot.reserved_by_id = None
    plot.reserved_at = None

    # Update waitlist entry if it exists
    wl = GardenWaitlist.query.filter_by(
        garden_id=garden_id, user_id=plot.assigned_to_id
    ).filter(GardenWaitlist.status.in_(['waiting', 'offered'])).first()
    if wl:
        wl.status = 'accepted'

    # Notify the user that their reservation was confirmed (in-app + SMS)
    notify(
        user_id=reserved_user_id,
        type='plot_confirmed',
        title=f'Plot {plot.plot_number} confirmed!',
        body=f'Your reservation for plot {plot.plot_number} in {garden.name} has been confirmed. Happy gardening!',
        link=f'/gardens/{garden.public_id}',
        garden_id=garden_id,
    )
    reserved_user = db.session.get(User, reserved_user_id)
    if reserved_user and reserved_user.sms_opt_in and reserved_user.phone_number:
        from app.sms_service import send_plot_assigned_sms
        send_plot_assigned_sms(reserved_user.phone_number, garden.name, plot.plot_number)
    if reserved_user and reserved_user.email:
        try:
            from app.email_service import send_plot_assigned_email
            send_plot_assigned_email(
                garden.name, plot.plot_number, reserved_user.email,
                reserved_user.display_name or reserved_user.username,
                garden_id=garden_id)
        except Exception:
            pass  # logged inside send_email

    db.session.commit()

    from app.api.gardens_api import plot_to_dict
    return jsonify(plot_to_dict(plot))


@garden_admin_api.route('/<garden_id>/plots/<int:plot_id>/decline-reservation', methods=['POST'])
@token_or_session
def decline_reservation(garden_id, plot_id):
    """Organizer declines a reservation -> plot goes back to 'available'."""
    garden, err = require_garden_admin(garden_id)
    if err:
        return err

    plot = db.get_or_404(GardenPlot, plot_id)
    if plot.garden_id != garden_id:
        return jsonify({'error': 'Plot not in this garden'}), 400
    if plot.status != 'reserved':
        return jsonify({'error': 'Plot is not reserved'}), 400

    declined_user_id = plot.reserved_by_id
    plot.status = 'available'
    plot.reserved_by_id = None
    plot.reserved_at = None

    # Notify the user that their reservation was declined
    if declined_user_id:
        notify(
            user_id=declined_user_id,
            type='plot_declined',
            title=f'Plot {plot.plot_number} reservation declined',
            body=f'Your reservation for plot {plot.plot_number} in {garden.name} was not approved. You may join the waitlist or reserve another available plot.',
            link=f'/gardens/{garden.public_id}',
            garden_id=garden_id,
        )

    db.session.commit()

    from app.api.gardens_api import plot_to_dict
    return jsonify(plot_to_dict(plot))


# ---------------------------------------------------------------------------
# Waitlist Management (Organizer approves/declines waitlist entries)
# ---------------------------------------------------------------------------

@garden_admin_api.route('/<garden_id>/waitlist/<int:wl_id>/approve', methods=['POST'])
@token_or_session
def approve_waitlist(garden_id, wl_id):
    """Approve a waitlist entry: assign user to a chosen available plot."""
    garden, err = require_garden_admin(garden_id)
    if err:
        return err

    entry = db.get_or_404(GardenWaitlist, wl_id)
    if entry.garden_id != garden_id:
        return jsonify({'error': 'Waitlist entry not in this garden'}), 400
    if entry.status != 'waiting':
        return jsonify({'error': 'Entry is not in waiting status'}), 400

    data = request.get_json() or {}
    plot_id = data.get('plot_id')
    if not plot_id:
        return jsonify({'error': 'plot_id required'}), 400

    plot = db.get_or_404(GardenPlot, plot_id)
    if plot.garden_id != garden_id:
        return jsonify({'error': 'Plot not in this garden'}), 400
    if plot.status != 'available':
        return jsonify({'error': 'Plot is not available'}), 400

    # Assign the plot
    plot.assigned_to_id = entry.user_id
    plot.status = 'assigned'
    plot.assigned_date = datetime.now(timezone.utc).date()

    # Update waitlist status
    entry.status = 'accepted'

    # Notify the user they got a plot from the waitlist (in-app + SMS)
    notify(
        user_id=entry.user_id,
        type='waitlist_approved',
        title=f'Waitlist approved — Plot {plot.plot_number}!',
        body=f'You have been assigned plot {plot.plot_number} in {garden.name} from the waitlist.',
        link=f'/gardens/{garden.public_id}',
        garden_id=garden_id,
    )
    wl_user = db.session.get(User, entry.user_id)
    if wl_user and wl_user.sms_opt_in and wl_user.phone_number:
        from app.sms_service import send_plot_assigned_sms
        send_plot_assigned_sms(wl_user.phone_number, garden.name, plot.plot_number)
    if wl_user and wl_user.email:
        try:
            from app.email_service import send_plot_assigned_email
            send_plot_assigned_email(
                garden.name, plot.plot_number, wl_user.email,
                wl_user.display_name or wl_user.username,
                garden_id=garden_id)
        except Exception:
            pass  # logged inside send_email

    db.session.commit()

    from app.api.gardens_api import plot_to_dict, waitlist_to_dict
    return jsonify({
        'plot': plot_to_dict(plot),
        'waitlist_entry': waitlist_to_dict(entry),
    })


@garden_admin_api.route('/<garden_id>/waitlist/<int:wl_id>/decline', methods=['POST'])
@token_or_session
def decline_waitlist(garden_id, wl_id):
    """Decline a waitlist entry."""
    garden, err = require_garden_admin(garden_id)
    if err:
        return err

    entry = db.get_or_404(GardenWaitlist, wl_id)
    if entry.garden_id != garden_id:
        return jsonify({'error': 'Waitlist entry not in this garden'}), 400

    entry.status = 'declined'

    # Notify the user their waitlist entry was declined
    notify(
        user_id=entry.user_id,
        type='waitlist_declined',
        title='Waitlist update',
        body=f'Your waitlist request for {garden.name} was not approved at this time.',
        link=f'/gardens/{garden.public_id}',
        garden_id=garden_id,
    )

    db.session.commit()

    from app.api.gardens_api import waitlist_to_dict
    return jsonify(waitlist_to_dict(entry))


# ---------------------------------------------------------------------------
# Resource Condition Management
# ---------------------------------------------------------------------------

@garden_admin_api.route('/<garden_id>/resources/<int:res_id>/condition', methods=['PUT'])
@token_or_session
def update_resource_condition(garden_id, res_id):
    """Organizer updates the condition of a shared resource (maintenance — Pro)."""
    garden, err = require_garden_admin_pro(garden_id)
    if err:
        return err

    res = db.get_or_404(SharedResource, res_id)
    if res.garden_id != garden_id:
        return jsonify({'error': 'Resource not in this garden'}), 400

    data = request.get_json() or {}
    condition = data.get('condition')
    if condition not in ('new', 'good', 'fair', 'needs_repair'):
        return jsonify({'error': 'Invalid condition'}), 400

    res.condition = condition
    db.session.commit()

    from app.api.gardens_api import resource_to_dict
    return jsonify(resource_to_dict(res))


def _get_garden_resource(garden_id, res_id):
    """Resolve (garden, resource, error). Resource must belong to the garden."""
    garden, err = require_garden_admin(garden_id)
    if err:
        return None, None, err
    res = db.get_or_404(SharedResource, res_id)
    if res.garden_id != garden_id:
        return None, None, (jsonify({'error': 'Resource not in this garden'}), 400)
    return garden, res, None


@garden_admin_api.route('/<garden_id>/resources/<int:res_id>', methods=['PUT'])
@token_or_session
def admin_update_resource(garden_id, res_id):
    """Edit/adjust a tool's details (name, type, description, quantity, condition)."""
    _g, res, err = _get_garden_resource(garden_id, res_id)
    if err:
        return err
    from app.api.gardens_api import resource_to_dict
    data = request.get_json() or {}
    if 'name' in data:
        name = (data.get('name') or '').strip()
        if not name:
            return jsonify({'error': 'Name is required'}), 400
        res.name = name
    if 'resource_type' in data:
        res.resource_type = (data.get('resource_type') or 'tool').strip()
    if 'description' in data:
        res.description = data.get('description') or ''
    if 'quantity' in data:
        try:
            q = int(data.get('quantity'))
        except (TypeError, ValueError):
            q = res.quantity or 1
        res.quantity = q if q and q >= 1 else 1
    if 'condition' in data and data['condition'] in ('new', 'good', 'fair', 'needs_repair'):
        res.condition = data['condition']
    db.session.commit()
    return jsonify(resource_to_dict(res))


@garden_admin_api.route('/<garden_id>/resources/<int:res_id>', methods=['DELETE'])
@token_or_session
def admin_delete_resource(garden_id, res_id):
    """Delete a tool from inventory. Blocks if checked out unless ?force=1."""
    _g, res, err = _get_garden_resource(garden_id, res_id)
    if err:
        return err
    force = request.args.get('force') in ('1', 'true', 'yes')
    if res.checked_out_to_id and not force:
        return jsonify({
            'error': 'This tool is currently checked out. Return it first, '
                     'or confirm deletion to remove it anyway.',
            'checked_out': True,
        }), 409
    # Detach open checkout logs from the deleted resource gracefully.
    ResourceCheckoutLog.query.filter_by(resource_id=res.id).delete()
    db.session.delete(res)
    db.session.commit()
    return jsonify({'success': True})


@garden_admin_api.route('/<garden_id>/resources/<int:res_id>/service', methods=['POST'])
@token_or_session
def admin_set_resource_service(garden_id, res_id):
    """Take a tool out of service (repair/maintenance) or return it to service."""
    _g, res, err = _get_garden_resource(garden_id, res_id)
    if err:
        return err
    ok, perr = require_garden_pro(_g)  # service/maintenance is a Pro feature
    if perr:
        return perr
    from app.api.gardens_api import resource_to_dict
    data = request.get_json() or {}
    out = bool(data.get('out_of_service'))
    if out and res.checked_out_to_id:
        return jsonify({
            'error': 'Return the tool from its borrower before taking it out of service.',
        }), 409
    res.out_of_service = out
    res.service_note = (data.get('note') or '').strip()[:300] if out else None
    db.session.commit()
    return jsonify(resource_to_dict(res))


@garden_admin_api.route('/<garden_id>/resources/<int:res_id>/force-return', methods=['POST'])
@token_or_session
def admin_force_return_resource(garden_id, res_id):
    """Admin returns a tool regardless of who has it checked out."""
    _g, res, err = _get_garden_resource(garden_id, res_id)
    if err:
        return err
    from app.api.gardens_api import resource_to_dict
    if not res.checked_out_to_id:
        return jsonify({'error': 'This tool is not checked out'}), 400
    data = request.get_json() or {}
    condition_at_return = data.get('condition_at_return')

    log = ResourceCheckoutLog.query.filter_by(
        resource_id=res.id, user_id=res.checked_out_to_id, returned_at=None
    ).order_by(ResourceCheckoutLog.checked_out_at.desc()).first()
    if log:
        log.returned_at = datetime.now(timezone.utc)
        if condition_at_return:
            log.condition_at_return = condition_at_return
    if condition_at_return in ('new', 'good', 'fair', 'needs_repair'):
        res.condition = condition_at_return
    res.checked_out_to_id = None
    res.checked_out_at = None
    res.due_date = None
    db.session.commit()
    return jsonify(resource_to_dict(res))


@garden_admin_api.route('/<garden_id>/resources/<int:res_id>/checkout-for', methods=['POST'])
@token_or_session
def admin_checkout_for_member(garden_id, res_id):
    """Admin checks a tool out on behalf of a member (in-person lending — Pro)."""
    _g, res, err = _get_garden_resource(garden_id, res_id)
    if err:
        return err
    ok, perr = require_garden_pro(_g)  # tool checkout is a Pro feature
    if perr:
        return perr
    from app.api.gardens_api import resource_to_dict
    if res.out_of_service:
        return jsonify({'error': 'This tool is out of service'}), 400
    if res.checked_out_to_id:
        return jsonify({'error': 'This tool is already checked out'}), 400
    data = request.get_json() or {}
    user_id = data.get('user_id')
    member = db.session.get(User, user_id) if user_id else None
    if not member:
        return jsonify({'error': 'Select a member to check this tool out to'}), 400
    try:
        duration = int(data.get('duration_days', 3))
    except (TypeError, ValueError):
        duration = 3
    if duration < 1:
        duration = 3

    now = datetime.now(timezone.utc)
    res.checked_out_to_id = member.id
    res.checked_out_at = now
    res.due_date = now + timedelta(days=duration)
    db.session.add(ResourceCheckoutLog(
        resource_id=res.id, user_id=member.id, garden_id=garden_id,
        checked_out_at=now, due_date=res.due_date, duration_days=duration,
        condition_at_checkout=res.condition,
    ))
    db.session.commit()
    return jsonify(resource_to_dict(res))


@garden_admin_api.route('/<garden_id>/resources/<int:res_id>/extend', methods=['POST'])
@token_or_session
def admin_extend_resource_due(garden_id, res_id):
    """Extend the due date of an active checkout by N days (default 7 — Pro)."""
    _g, res, err = _get_garden_resource(garden_id, res_id)
    if err:
        return err
    ok, perr = require_garden_pro(_g)  # checkout management is a Pro feature
    if perr:
        return perr
    from app.api.gardens_api import resource_to_dict
    if not res.checked_out_to_id or not res.due_date:
        return jsonify({'error': 'This tool is not checked out'}), 400
    data = request.get_json() or {}
    try:
        days = int(data.get('days', 7))
    except (TypeError, ValueError):
        days = 7
    if days < 1:
        days = 7
    base = res.due_date
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    res.due_date = base + timedelta(days=days)
    log = ResourceCheckoutLog.query.filter_by(
        resource_id=res.id, user_id=res.checked_out_to_id, returned_at=None
    ).order_by(ResourceCheckoutLog.checked_out_at.desc()).first()
    if log:
        log.due_date = res.due_date
    db.session.commit()
    return jsonify(resource_to_dict(res))


# ===================================================================
#  VOLUNTEER SHIFTS — Admin endpoints
# ===================================================================

@garden_admin_api.route('/<garden_id>/shifts', methods=['POST'])
@token_or_session
def create_shift(garden_id):
    """Create a new volunteer shift."""
    garden, err = require_garden_admin_pro(garden_id)
    if err:
        return err
    data = request.get_json() or {}
    title = data.get('title', '').strip()
    if not title:
        return jsonify({'error': 'Title is required'}), 400
    shift_date_str = data.get('shift_date')
    start_time_str = data.get('start_time')
    end_time_str = data.get('end_time')
    if not shift_date_str or not start_time_str or not end_time_str:
        return jsonify({'error': 'Date and times are required'}), 400

    try:
        shift_date = date.fromisoformat(shift_date_str)
        start_time = dtime.fromisoformat(start_time_str)
        end_time = dtime.fromisoformat(end_time_str)
    except ValueError:
        return jsonify({'error': 'Invalid date/time format'}), 400

    shift = VolunteerShift(
        garden_id=garden_id,
        title=title,
        description=data.get('description', '').strip(),
        shift_date=shift_date,
        start_time=start_time,
        end_time=end_time,
        max_volunteers=data.get('max_volunteers') or None,
        recurring=data.get('recurring', 'none'),
        created_by_id=get_current_user().id,
    )
    db.session.add(shift)
    db.session.commit()

    # Generate recurring instances if needed
    recurring = data.get('recurring', 'none')
    if recurring and recurring != 'none':
        deltas = {'weekly': 7, 'biweekly': 14, 'monthly': 30}
        step = deltas.get(recurring, 0)
        if step:
            for i in range(1, 9):  # up to 8 additional instances
                new_date = shift_date + __import__('datetime').timedelta(days=step * i)
                rs = VolunteerShift(
                    garden_id=garden_id, title=title,
                    description=shift.description,
                    shift_date=new_date, start_time=start_time, end_time=end_time,
                    max_volunteers=shift.max_volunteers,
                    recurring=recurring, created_by_id=get_current_user().id,
                )
                db.session.add(rs)
            db.session.commit()

    from app.api.gardens_api import shift_to_dict
    return jsonify(shift_to_dict(shift)), 201


@garden_admin_api.route('/<garden_id>/shifts/<int:shift_id>', methods=['PUT'])
@token_or_session
def update_shift(garden_id, shift_id):
    """Edit a volunteer shift."""
    garden, err = require_garden_admin_pro(garden_id)
    if err:
        return err
    shift = db.get_or_404(VolunteerShift, shift_id)
    if shift.garden_id != garden_id:
        return jsonify({'error': 'Shift not in this garden'}), 400

    data = request.get_json() or {}
    if 'title' in data:
        shift.title = data['title'].strip()
    if 'description' in data:
        shift.description = data['description'].strip()
    if 'shift_date' in data:
        shift.shift_date = date.fromisoformat(data['shift_date'])
    if 'start_time' in data:
        shift.start_time = dtime.fromisoformat(data['start_time'])
    if 'end_time' in data:
        shift.end_time = dtime.fromisoformat(data['end_time'])
    if 'max_volunteers' in data:
        shift.max_volunteers = data['max_volunteers'] or None
    if 'recurring' in data:
        shift.recurring = data['recurring']
    db.session.commit()

    from app.api.gardens_api import shift_to_dict
    return jsonify(shift_to_dict(shift))


@garden_admin_api.route('/<garden_id>/shifts/<int:shift_id>', methods=['DELETE'])
@token_or_session
def delete_shift(garden_id, shift_id):
    """Delete a volunteer shift and its signups."""
    garden, err = require_garden_admin_pro(garden_id)
    if err:
        return err
    shift = db.get_or_404(VolunteerShift, shift_id)
    if shift.garden_id != garden_id:
        return jsonify({'error': 'Shift not in this garden'}), 400
    db.session.delete(shift)
    db.session.commit()
    return jsonify({'message': 'Shift deleted'})


@garden_admin_api.route('/<garden_id>/shifts/<int:shift_id>/attendees', methods=['GET'])
@token_or_session
def shift_attendees(garden_id, shift_id):
    """List signups for a shift."""
    garden, err = require_garden_admin_pro(garden_id)
    if err:
        return err
    shift = db.get_or_404(VolunteerShift, shift_id)
    if shift.garden_id != garden_id:
        return jsonify({'error': 'Shift not in this garden'}), 400
    signups = shift.signups.all()
    return jsonify([{
        'id': s.id,
        'user_id': s.user_id,
        'user_name': s.user.display_name or s.user.username,
        'status': s.status,
        'hours_logged': s.hours_logged,
        'checked_in_at': s.checked_in_at.isoformat() if s.checked_in_at else None,
        'notes': s.notes,
    } for s in signups])


@garden_admin_api.route('/<garden_id>/shifts/<int:shift_id>/attendance', methods=['POST'])
@token_or_session
def mark_attendance(garden_id, shift_id):
    """Batch mark attendance for a shift. Body: {records: [{user_id, status, hours_logged}]}"""
    garden, err = require_garden_admin_pro(garden_id)
    if err:
        return err
    shift = db.get_or_404(VolunteerShift, shift_id)
    if shift.garden_id != garden_id:
        return jsonify({'error': 'Shift not in this garden'}), 400

    data = request.get_json() or {}
    records = data.get('records', [])
    for rec in records:
        signup = ShiftSignup.query.filter_by(shift_id=shift_id, user_id=rec['user_id']).first()
        if signup:
            signup.status = rec.get('status', signup.status)
            if rec.get('hours_logged') is not None:
                signup.hours_logged = float(rec['hours_logged'])
            if rec.get('status') == 'attended' and not signup.checked_in_at:
                signup.checked_in_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({'message': 'Attendance updated'})


@garden_admin_api.route('/<garden_id>/shifts/<int:shift_id>/remind', methods=['POST'])
@token_or_session
def remind_shift(garden_id, shift_id):
    """Remind every signed-up volunteer about a shift: in-app + email + SMS.

    SMS is sent only to volunteers who opted in and have a phone number;
    email/SMS failures are swallowed so one bad contact can't abort the batch.
    """
    garden, err = require_garden_admin_pro(garden_id)
    if err:
        return err
    shift = db.get_or_404(VolunteerShift, shift_id)
    if shift.garden_id != garden_id:
        return jsonify({'error': 'Shift not in this garden'}), 400

    signups = shift.signups.filter(ShiftSignup.status == 'signed_up').all()
    date_str = shift.shift_date.strftime('%b %d, %Y') if shift.shift_date else ''
    time_str = ''
    if shift.start_time and shift.end_time:
        time_str = f"{shift.start_time.strftime('%I:%M %p')}–{shift.end_time.strftime('%I:%M %p')}"

    from app.email_service import send_email
    from app.sms_service import send_shift_reminder_sms

    reminded = 0
    for su in signups:
        member = db.session.get(User, su.user_id)
        if not member:
            continue
        notify(
            user_id=member.id,
            type='shift_reminder',
            title=f'Reminder: {shift.title}',
            body=f'You are signed up for {shift.title} at {garden.name} on {date_str}.',
            link=f'/gardens/{garden.public_id}',
            garden_id=garden_id,
        )
        if member.email:
            try:
                send_email(
                    member.email,
                    f'Volunteer shift reminder — {garden.name}',
                    f'Hi {member.display_name or member.username},\n\n'
                    f'This is a reminder that you are signed up for "{shift.title}" '
                    f'at {garden.name} on {date_str}{(" (" + time_str + ")") if time_str else ""}.\n\n'
                    f'See you there!\n\n— {garden.name}'
                )
            except Exception:
                pass
        if member.sms_opt_in and member.phone_number:
            send_shift_reminder_sms(member.phone_number, garden.name, shift.title, date_str)
        reminded += 1

    db.session.commit()
    return jsonify({'reminded': reminded})


@garden_admin_api.route('/<garden_id>/volunteer-report', methods=['GET'])
@token_or_session
def volunteer_report(garden_id):
    """Volunteer hours summary by member."""
    garden, err = require_garden_admin_pro(garden_id)
    if err:
        return err
    signups = ShiftSignup.query.join(VolunteerShift).filter(
        VolunteerShift.garden_id == garden_id
    ).all()
    member_stats = {}
    for s in signups:
        uid = s.user_id
        if uid not in member_stats:
            member_stats[uid] = {'user_id': uid, 'user_name': s.user.display_name or s.user.username,
                                 'total_hours': 0, 'shifts_attended': 0, 'no_shows': 0}
        if s.status == 'attended':
            member_stats[uid]['shifts_attended'] += 1
            member_stats[uid]['total_hours'] += s.hours_logged or 0
        elif s.status == 'no_show':
            member_stats[uid]['no_shows'] += 1
    report = sorted(member_stats.values(), key=lambda x: x['total_hours'], reverse=True)
    return jsonify(report)


# Funder-report valuation defaults. Overridable per-request so organizers can
# match whatever standard their funder requires; the report footnotes always
# state the rates used.
FUNDER_PRODUCE_RATE = 3.00      # $ per lb of fresh produce (common CG figure)
FUNDER_VOLUNTEER_RATE = 33.49   # $ per volunteer hour (Independent Sector 2024)
FUNDER_LBS_PER_MEAL = 1.2       # Feeding America meal equivalence
FUNDER_CO2_PER_LB = 2.0         # matches the public impact page's factor


@garden_admin_api.route('/<garden_id>/funder-report', methods=['GET'])
@token_or_session
def funder_report(garden_id):
    """Date-ranged, funder-facing impact report (Pro).

    Aggregates everything a grant report needs — harvest, participation,
    volunteering, events, finance — over [start, end] plus valuation
    equivalents. Volunteer hours are LOGGED attended-shift hours (not the
    public impact page's RSVP estimate); event participation is reported
    separately so the two are never conflated.
    """
    garden, err = require_garden_admin_pro(garden_id)
    if err:
        return err

    def _parse_date(name, default):
        raw = (request.args.get(name) or '').strip()
        if not raw:
            return default
        try:
            return date.fromisoformat(raw)
        except ValueError:
            return default

    def _parse_rate(name, default, lo=0.0, hi=10000.0):
        try:
            v = float(request.args.get(name, default))
        except (TypeError, ValueError):
            return default
        return min(max(v, lo), hi)

    today = datetime.now(timezone.utc).date()
    start = _parse_date('start', date(today.year, 1, 1))
    end = _parse_date('end', today)
    if end < start:
        start, end = end, start
    # Datetime bounds for DateTime columns (end day inclusive).
    start_dt = datetime.combine(start, dtime.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(end, dtime.max, tzinfo=timezone.utc)

    produce_rate = _parse_rate('produce_rate', FUNDER_PRODUCE_RATE)
    volunteer_rate = _parse_rate('volunteer_rate', FUNDER_VOLUNTEER_RATE)

    # The public-id preprocessor already resolved garden_id to the integer PK.
    gid = garden.id

    # ---- Harvest -----------------------------------------------------------
    h_base = HarvestLog.query.filter(
        HarvestLog.garden_id == gid,
        HarvestLog.harvest_date >= start, HarvestLog.harvest_date <= end)
    total_lbs = float(h_base.with_entities(
        func.coalesce(func.sum(HarvestLog.quantity_lbs), 0)).scalar())
    by_category = [
        {'category': c or 'Uncategorized', 'lbs': round(float(lbs or 0), 1)}
        for c, lbs in h_base.with_entities(
            HarvestLog.category, func.sum(HarvestLog.quantity_lbs))
        .group_by(HarvestLog.category)
        .order_by(func.sum(HarvestLog.quantity_lbs).desc()).all()]
    by_destination = {
        (d or 'personal'): round(float(lbs or 0), 1)
        for d, lbs in h_base.with_entities(
            HarvestLog.destination, func.sum(HarvestLog.quantity_lbs))
        .group_by(HarvestLog.destination).all()}
    harvest_gardeners = h_base.with_entities(
        func.count(func.distinct(HarvestLog.user_id))).scalar() or 0
    food_bank_lbs = by_destination.get('food_bank', 0.0)
    shared_lbs = by_destination.get('shared', 0.0)

    # ---- Participation -----------------------------------------------------
    members_total = GardenMembership.query.filter_by(garden_id=gid).count()
    members_new = GardenMembership.query.filter(
        GardenMembership.garden_id == gid,
        GardenMembership.joined_at >= start_dt,
        GardenMembership.joined_at <= end_dt).count()
    plots_total = GardenPlot.query.filter_by(garden_id=gid).count()
    plots_assigned = GardenPlot.query.filter_by(
        garden_id=gid, status='assigned').count()

    # ---- Volunteering (logged attended-shift hours) ------------------------
    shift_rows = (ShiftSignup.query.join(VolunteerShift)
                  .filter(VolunteerShift.garden_id == gid,
                          VolunteerShift.shift_date >= start,
                          VolunteerShift.shift_date <= end,
                          ShiftSignup.status == 'attended').all())
    volunteer_hours = round(sum(s.hours_logged or 0 for s in shift_rows), 1)
    shifts_held = (VolunteerShift.query
                   .filter(VolunteerShift.garden_id == gid,
                           VolunteerShift.shift_date >= start,
                           VolunteerShift.shift_date <= end).count())
    volunteers = len({s.user_id for s in shift_rows})

    # ---- Events ------------------------------------------------------------
    e_base = GardenEvent.query.filter(
        GardenEvent.garden_id == gid,
        GardenEvent.event_date >= start_dt, GardenEvent.event_date <= end_dt)
    events_held = e_base.count()
    events_by_type = {
        (t or 'other'): n for t, n in e_base.with_entities(
            GardenEvent.event_type, func.count(GardenEvent.id))
        .group_by(GardenEvent.event_type).all()}
    event_rsvps = (EventRSVP.query.join(GardenEvent)
                   .filter(GardenEvent.garden_id == gid,
                           GardenEvent.event_date >= start_dt,
                           GardenEvent.event_date <= end_dt,
                           EventRSVP.status == 'going').count())

    # ---- Finance -----------------------------------------------------------
    # Dues are per season-year records, so filter by the seasons the period
    # touches; expenses filter by their actual dates.
    dues_rows = GardenDuesRecord.query.filter(
        GardenDuesRecord.garden_id == gid,
        GardenDuesRecord.season_year >= start.year,
        GardenDuesRecord.season_year <= end.year).all()
    dues_expected = round(sum(d.amount_due or 0 for d in dues_rows), 2)
    dues_collected = round(sum(d.amount_paid or 0 for d in dues_rows), 2)
    x_base = GardenExpense.query.filter(
        GardenExpense.garden_id == gid,
        GardenExpense.expense_date >= start, GardenExpense.expense_date <= end)
    expenses_total = round(float(x_base.with_entities(
        func.coalesce(func.sum(GardenExpense.amount), 0)).scalar()), 2)
    expenses_by_category = {
        (c or 'other'): round(float(a or 0), 2)
        for c, a in x_base.with_entities(
            GardenExpense.category, func.sum(GardenExpense.amount))
        .group_by(GardenExpense.category).all()}

    return jsonify({
        'garden': {
            'name': garden.name,
            'city': garden.city, 'state': garden.state,
            'season_start': garden.season_start.isoformat() if garden.season_start else None,
            'season_end': garden.season_end.isoformat() if garden.season_end else None,
        },
        'period': {'start': start.isoformat(), 'end': end.isoformat()},
        'harvest': {
            'total_lbs': round(total_lbs, 1),
            'by_category': by_category,
            'by_destination': by_destination,
            'food_bank_lbs': food_bank_lbs,
            'shared_lbs': shared_lbs,
            'gardeners': harvest_gardeners,
        },
        'participation': {
            'members_total': members_total,
            'members_new': members_new,
            'plots_total': plots_total,
            'plots_assigned': plots_assigned,
            'occupancy_pct': round(100 * plots_assigned / plots_total) if plots_total else 0,
        },
        'volunteering': {
            'shifts_held': shifts_held,
            'volunteers': volunteers,
            'hours': volunteer_hours,
            'value_usd': round(volunteer_hours * volunteer_rate, 2),
        },
        'events': {
            'held': events_held,
            'by_type': events_by_type,
            'rsvps_going': event_rsvps,
        },
        'finance': {
            'dues_expected': dues_expected,
            'dues_collected': dues_collected,
            'expenses_total': expenses_total,
            'expenses_by_category': expenses_by_category,
            'net': round(dues_collected - expenses_total, 2),
        },
        'equivalents': {
            'meals': round((food_bank_lbs + shared_lbs) / FUNDER_LBS_PER_MEAL),
            'produce_value_usd': round(total_lbs * produce_rate, 2),
            'co2_saved_lbs': round((food_bank_lbs + shared_lbs) * FUNDER_CO2_PER_LB, 1),
        },
        'rates': {
            'produce_rate': produce_rate,
            'volunteer_rate': volunteer_rate,
            'lbs_per_meal': FUNDER_LBS_PER_MEAL,
            'co2_per_lb': FUNDER_CO2_PER_LB,
        },
    })


# ===================================================================
#  DUES COLLECTION — Admin endpoints
# ===================================================================

@garden_admin_api.route('/<garden_id>/dues', methods=['GET'])
@token_or_session
def list_dues(garden_id):
    """List dues records, filterable by season_year and status."""
    garden, err = require_garden_admin_pro(garden_id)
    if err:
        return err
    q = GardenDuesRecord.query.filter_by(garden_id=garden_id)
    season = request.args.get('season_year')
    if season:
        q = q.filter_by(season_year=int(season))
    status = request.args.get('status')
    if status and status != 'all':
        q = q.filter_by(status=status)
    records = q.order_by(GardenDuesRecord.created_at.desc()).all()
    return jsonify([{
        'id': r.id, 'user_id': r.user_id,
        'user_name': db.session.get(User, r.user_id).display_name if db.session.get(User, r.user_id) else 'Unknown',
        'season_year': r.season_year, 'amount_due': r.amount_due,
        'amount_paid': r.amount_paid, 'status': r.status,
        'payment_method': r.payment_method,
        'payment_date': r.payment_date.isoformat() if r.payment_date else None,
        'payment_note': r.payment_note,
        'created_at': r.created_at.isoformat() if r.created_at else None,
    } for r in records])


@garden_admin_api.route('/<garden_id>/dues/generate', methods=['POST'])
@token_or_session
def generate_dues(garden_id):
    """Auto-generate dues for all current plot holders."""
    garden, err = require_garden_admin_pro(garden_id)
    if err:
        return err
    data = request.get_json() or {}
    season_year = data.get('season_year', date.today().year)
    amount = data.get('amount') or garden.plot_fee_annual or 0

    plots = GardenPlot.query.filter_by(garden_id=garden_id, status='assigned').all()
    created = 0
    for p in plots:
        if not p.assigned_to_id:
            continue
        existing = GardenDuesRecord.query.filter_by(
            garden_id=garden_id, user_id=p.assigned_to_id, season_year=season_year
        ).first()
        if not existing:
            rec = GardenDuesRecord(
                garden_id=garden_id, user_id=p.assigned_to_id,
                season_year=season_year, amount_due=amount,
            )
            db.session.add(rec)
            created += 1
    db.session.commit()
    return jsonify({'message': f'Generated {created} dues records', 'created': created})


@garden_admin_api.route('/<garden_id>/dues/<int:dues_id>', methods=['PUT'])
@token_or_session
def update_dues(garden_id, dues_id):
    """Record payment on a dues record."""
    garden, err = require_garden_admin_pro(garden_id)
    if err:
        return err
    rec = db.get_or_404(GardenDuesRecord, dues_id)
    if rec.garden_id != garden_id:
        return jsonify({'error': 'Record not in this garden'}), 400
    data = request.get_json() or {}
    if 'amount_paid' in data:
        rec.amount_paid = float(data['amount_paid'])
    if 'payment_method' in data:
        rec.payment_method = data['payment_method']
    if 'payment_note' in data:
        rec.payment_note = data['payment_note']
    if 'status' in data:
        rec.status = data['status']
    else:
        if rec.amount_paid >= rec.amount_due:
            rec.status = 'paid'
        elif rec.amount_paid > 0:
            rec.status = 'partial'
    if rec.amount_paid > 0 and not rec.payment_date:
        rec.payment_date = date.today()
    db.session.commit()
    return jsonify({'message': 'Dues updated'})


@garden_admin_api.route('/<garden_id>/dues/<int:dues_id>/waive', methods=['POST'])
@token_or_session
def waive_dues(garden_id, dues_id):
    """Waive dues for a member."""
    garden, err = require_garden_admin_pro(garden_id)
    if err:
        return err
    rec = db.get_or_404(GardenDuesRecord, dues_id)
    if rec.garden_id != garden_id:
        return jsonify({'error': 'Record not in this garden'}), 400
    rec.status = 'waived'
    rec.payment_method = 'waived'
    db.session.commit()
    return jsonify({'message': 'Dues waived'})


@garden_admin_api.route('/<garden_id>/dues/<int:dues_id>/remind', methods=['POST'])
@token_or_session
def remind_dues(garden_id, dues_id):
    """Send payment reminder email/SMS to member."""
    garden, err = require_garden_admin_pro(garden_id)
    if err:
        return err
    rec = db.get_or_404(GardenDuesRecord, dues_id)
    if rec.garden_id != garden_id:
        return jsonify({'error': 'Record not in this garden'}), 400
    member = db.session.get(User, rec.user_id)
    if not member:
        return jsonify({'error': 'Member not found'}), 404
    # Send branded email reminder (with pay-online link)
    try:
        from app.email_service import send_dues_reminder_email
        send_dues_reminder_email(
            garden.name, member.email,
            member.display_name or member.username,
            rec.amount_due - rec.amount_paid, rec.season_year,
            garden_id=garden_id)
    except Exception:
        pass

    # SMS reminder (per-user opt-in)
    remaining = rec.amount_due - rec.amount_paid
    if member.sms_opt_in and member.phone_number:
        try:
            from app.sms_service import send_dues_reminder_sms
            send_dues_reminder_sms(member.phone_number, garden.name, remaining)
        except Exception:
            pass

    # In-app notification
    notify(
        user_id=rec.user_id,
        type='dues_reminder',
        title=f'Payment reminder — {garden.name}',
        body=f'Your garden dues of ${remaining:.2f} for {rec.season_year} are outstanding.',
        link=f'/gardens/{garden.public_id}',
        garden_id=garden_id,
    )
    db.session.commit()

    return jsonify({'message': f'Reminder sent to {member.display_name or member.username}'})


# ===================================================================
#  EXPENSES — Admin endpoints
# ===================================================================

@garden_admin_api.route('/<garden_id>/expenses', methods=['GET'])
@token_or_session
def list_expenses(garden_id):
    """List garden expenses."""
    garden, err = require_garden_admin_pro(garden_id)
    if err:
        return err
    q = GardenExpense.query.filter_by(garden_id=garden_id)
    category = request.args.get('category')
    if category and category != 'all':
        q = q.filter_by(category=category)
    year = request.args.get('year', type=int)
    if year:
        q = q.filter(func.extract('year', GardenExpense.expense_date) == year)
    expenses = q.order_by(GardenExpense.expense_date.desc()).all()
    return jsonify([{
        'id': e.id, 'title': e.title, 'amount': e.amount,
        'category': e.category,
        'expense_date': e.expense_date.isoformat() if e.expense_date else None,
        'paid_by': e.paid_by, 'receipt_url': e.receipt_url,
        'notes': e.notes,
        'created_by_name': db.session.get(User, e.created_by_id).display_name if db.session.get(User, e.created_by_id) else 'Unknown',
        'created_at': e.created_at.isoformat() if e.created_at else None,
    } for e in expenses])


@garden_admin_api.route('/<garden_id>/expenses', methods=['POST'])
@token_or_session
def create_expense(garden_id):
    """Log a garden expense."""
    garden, err = require_garden_admin_pro(garden_id)
    if err:
        return err
    data = request.get_json() or {}
    title = data.get('title', '').strip()
    if not title:
        return jsonify({'error': 'Title is required'}), 400
    expense = GardenExpense(
        garden_id=garden_id, title=title,
        amount=float(data.get('amount', 0)),
        category=data.get('category', 'other'),
        expense_date=date.fromisoformat(data['expense_date']) if data.get('expense_date') else date.today(),
        paid_by=data.get('paid_by', '').strip(),
        receipt_url=data.get('receipt_url', '').strip(),
        notes=data.get('notes', '').strip(),
        created_by_id=get_current_user().id,
    )
    db.session.add(expense)
    db.session.commit()
    return jsonify({'message': 'Expense logged', 'id': expense.id}), 201


@garden_admin_api.route('/<garden_id>/expenses/<int:exp_id>', methods=['PUT'])
@token_or_session
def update_expense(garden_id, exp_id):
    """Edit an expense."""
    garden, err = require_garden_admin_pro(garden_id)
    if err:
        return err
    exp = db.get_or_404(GardenExpense, exp_id)
    if exp.garden_id != garden_id:
        return jsonify({'error': 'Expense not in this garden'}), 400
    data = request.get_json() or {}
    for field in ('title', 'category', 'paid_by', 'receipt_url', 'notes'):
        if field in data:
            setattr(exp, field, data[field].strip() if isinstance(data[field], str) else data[field])
    if 'amount' in data:
        exp.amount = float(data['amount'])
    if 'expense_date' in data:
        exp.expense_date = date.fromisoformat(data['expense_date'])
    db.session.commit()
    return jsonify({'message': 'Expense updated'})


@garden_admin_api.route('/<garden_id>/expenses/<int:exp_id>', methods=['DELETE'])
@token_or_session
def delete_expense(garden_id, exp_id):
    """Delete an expense."""
    garden, err = require_garden_admin_pro(garden_id)
    if err:
        return err
    exp = db.get_or_404(GardenExpense, exp_id)
    if exp.garden_id != garden_id:
        return jsonify({'error': 'Expense not in this garden'}), 400
    db.session.delete(exp)
    db.session.commit()
    return jsonify({'message': 'Expense deleted'})


@garden_admin_api.route('/<garden_id>/finance-summary', methods=['GET'])
@token_or_session
def finance_summary(garden_id):
    """Financial dashboard data."""
    garden, err = require_garden_admin_pro(garden_id)
    if err:
        return err
    season = request.args.get('season_year', date.today().year, type=int)

    dues = GardenDuesRecord.query.filter_by(garden_id=garden_id, season_year=season).all()
    total_expected = sum(d.amount_due for d in dues)
    total_collected = sum(d.amount_paid for d in dues)
    outstanding = total_expected - total_collected
    collection_rate = (total_collected / total_expected * 100) if total_expected > 0 else 0

    expenses = GardenExpense.query.filter_by(garden_id=garden_id).filter(
        func.extract('year', GardenExpense.expense_date) == season
    ).all()
    expenses_total = sum(e.amount for e in expenses)
    by_category = {}
    for e in expenses:
        cat = e.category or 'other'
        by_category[cat] = by_category.get(cat, 0) + e.amount

    from app import garden_finance
    stripe_totals = garden_finance.totals(
        garden_id,
        since=datetime(season, 1, 1, tzinfo=timezone.utc),
        until=datetime(season, 12, 31, 23, 59, 59, tzinfo=timezone.utc))

    return jsonify({
        'season_year': season,
        'total_dues_expected': total_expected,
        'total_collected': total_collected,
        'outstanding': outstanding,
        'collection_rate': round(collection_rate, 1),
        'expenses_total': expenses_total,
        'net_balance': total_collected - expenses_total,
        'by_category': by_category,
        'dues_count': len(dues),
        'paid_count': sum(1 for d in dues if d.status == 'paid'),
        'unpaid_count': sum(1 for d in dues if d.status == 'unpaid'),
        # What Stripe actually reported for this season: card money in, fees
        # taken, refunds and chargebacks out. The dues figures above are the
        # roster's view (they include cash and cheques and say nothing about
        # fees), so the two are reported side by side rather than merged.
        'stripe': stripe_totals,
        'stripe_status': garden_finance.stripe_status(garden),
    })


# ===================================================================
#  STRIPE MONEY FEED — what the webhooks saw, for the manager
# ===================================================================
#
# Deliberately gated on require_garden_admin, NOT require_garden_admin_pro,
# even though the rest of the Finance tab is Pro. These endpoints show a
# manager money that already moved through their own Stripe account, and the
# endpoints that take that money (collect-in-person, in-person-charge) are not
# Pro-gated either. Putting a paywall between someone and the record of their
# own collections is the wrong trade.

def _finance_window(days_default=90):
    """(since, days) from ?days=, clamped to something a query can serve."""
    days = request.args.get('days', days_default, type=int) or days_default
    days = max(1, min(int(days), 730))
    return datetime.now(timezone.utc) - timedelta(days=days), days


@garden_admin_api.route('/<garden_id>/finance/activity', methods=['GET'])
@token_or_session
def finance_activity(garden_id):
    """Money events Stripe reported for this garden, newest first.

    Includes the organizer's account-level payout rows so the feed answers
    both halves of "where is my money" — what came in, and when it left
    Stripe for the bank.
    """
    from app import garden_finance

    garden, err = require_garden_admin(garden_id)
    if err:
        return err

    since, days = _finance_window()
    kinds = [k for k in (request.args.get('kind', '') or '').split(',') if k]
    limit = max(1, min(request.args.get('limit', 50, type=int) or 50, 200))

    q = garden_finance.activity_query(garden, kinds=kinds or None, since=since)
    rows = q.limit(limit).all()
    return jsonify({
        'events': [garden_finance.to_dict(e) for e in rows],
        'window_days': days,
        'count': len(rows),
        'totals': garden_finance.totals(garden.id, since=since),
        'stripe_status': garden_finance.stripe_status(garden),
    })


@garden_admin_api.route('/<garden_id>/finance/payouts', methods=['GET'])
@token_or_session
def finance_payouts(garden_id):
    """Deposits Stripe made to the manager's bank.

    Payouts belong to the connected account, which can span more than one
    garden, so they are reported as an account-level figure rather than folded
    into this garden's totals.
    """
    from app import garden_finance

    garden, err = require_garden_admin(garden_id)
    if err:
        return err
    if not garden.organizer_id:
        return jsonify({'payouts': [], 'paid_total': 0, 'paid_count': 0})

    _since, days = _finance_window()
    out = garden_finance.payout_summary(garden.organizer_id, days=days)
    out['stripe_status'] = garden_finance.stripe_status(garden)
    out['account_level'] = True
    return jsonify(out)


@garden_admin_api.route('/<garden_id>/finance/stripe-status', methods=['GET'])
@token_or_session
def finance_stripe_status(garden_id):
    """Can this garden take money, and can that money reach a bank?

    Answered from the state mirrored by the ``account.updated`` webhook, so it
    costs no Stripe round-trip on a normal (healthy) load. The Express
    dashboard link is fetched only when something is actually wrong, which is
    the one time a manager needs to go there.
    """
    from app import garden_finance, stripe_service

    garden, err = require_garden_admin(garden_id)
    if err:
        return err

    status = garden_finance.stripe_status(garden)
    status['stripe_configured'] = stripe_service.is_configured()
    status['billing_path'] = '/gardens/%s/billing' % (garden.public_id or garden.id)
    status['dashboard_url'] = None
    if not status['ok'] and status['account_id'] and stripe_service.is_configured():
        try:
            status['dashboard_url'] = stripe_service.create_login_link(garden.organizer)
        except Exception:
            log.exception('Express login link failed for garden %s', garden_id)
    return jsonify(status)


# ===================================================================
#  WEATHER — Admin endpoints
# ===================================================================

@garden_admin_api.route('/<garden_id>/weather', methods=['GET'])
@token_or_session
def garden_weather(garden_id):
    """Get current weather + active alerts for a garden."""
    garden, err = require_garden_admin(garden_id)
    if err:
        return err

    weather_data = None
    if garden.latitude and garden.longitude:
        try:
            from app.weather_service import get_current_weather
            weather_data = get_current_weather(garden.latitude, garden.longitude)
        except Exception:
            pass

    now = datetime.now(timezone.utc)
    alerts = GardenWeatherAlert.query.filter(
        GardenWeatherAlert.garden_id == garden_id,
        (GardenWeatherAlert.active_until.is_(None)) | (GardenWeatherAlert.active_until >= now)
    ).order_by(GardenWeatherAlert.created_at.desc()).all()

    return jsonify({
        'weather': weather_data,
        'alerts': [{
            'id': a.id, 'alert_type': a.alert_type, 'message': a.message,
            'severity': a.severity, 'auto_generated': a.auto_generated,
            'active_from': a.active_from.isoformat() if a.active_from else None,
            'active_until': a.active_until.isoformat() if a.active_until else None,
            'created_at': a.created_at.isoformat() if a.created_at else None,
        } for a in alerts],
        'weather_enabled': garden.weather_alerts_enabled or False,
        'has_location': bool(garden.latitude and garden.longitude),
    })


@garden_admin_api.route('/<garden_id>/weather/alerts', methods=['POST'])
@token_or_session
def create_weather_alert(garden_id):
    """Create a manual weather alert."""
    garden, err = require_garden_admin(garden_id)
    if err:
        return err
    data = request.get_json() or {}
    alert = GardenWeatherAlert(
        garden_id=garden_id,
        alert_type=data.get('alert_type', 'info'),
        message=data.get('message', '').strip(),
        severity=data.get('severity', 'info'),
        active_until=datetime.fromisoformat(data['active_until']) if data.get('active_until') else None,
        auto_generated=False,
    )
    db.session.add(alert)
    db.session.commit()
    return jsonify({'message': 'Alert created', 'id': alert.id}), 201


@garden_admin_api.route('/<garden_id>/weather/alerts/<int:alert_id>', methods=['DELETE'])
@token_or_session
def dismiss_weather_alert(garden_id, alert_id):
    """Dismiss/delete a weather alert."""
    garden, err = require_garden_admin(garden_id)
    if err:
        return err
    alert = db.get_or_404(GardenWeatherAlert, alert_id)
    if alert.garden_id != garden_id:
        return jsonify({'error': 'Alert not in this garden'}), 400
    db.session.delete(alert)
    db.session.commit()
    return jsonify({'message': 'Alert dismissed'})


# ===================================================================
#  PLOT ASSIGNMENT HISTORY — Admin endpoints
# ===================================================================

@garden_admin_api.route('/<garden_id>/rotation-report', methods=['GET'])
@token_or_session
def rotation_report(garden_id):
    """All plots with their assignment history per season."""
    garden, err = require_garden_admin(garden_id)
    if err:
        return err
    plots = GardenPlot.query.filter_by(garden_id=garden_id).order_by(GardenPlot.plot_number).all()
    result = []
    for p in plots:
        history = PlotAssignmentHistory.query.filter_by(plot_id=p.id).order_by(
            PlotAssignmentHistory.season_year.desc()
        ).all()
        result.append({
            'plot_id': p.id, 'plot_number': p.plot_number, 'status': p.status,
            'current_holder': (p.assigned_to.display_name or p.assigned_to.username) if p.assigned_to else None,
            'history': [{
                'season_year': h.season_year,
                'user_name': db.session.get(User, h.user_id).display_name if db.session.get(User, h.user_id) else 'Unknown',
                'assigned_date': h.assigned_date.isoformat() if h.assigned_date else None,
                'released_date': h.released_date.isoformat() if h.released_date else None,
            } for h in history],
        })
    return jsonify(result)


# ===================================================================
#  GARDEN MEMBERSHIP ROLES — Admin endpoints
# ===================================================================

@garden_admin_api.route('/<garden_id>/members', methods=['GET'])
@token_or_session
def list_members(garden_id):
    """List all members with rich profile, plot, and dues data."""
    garden, err = require_garden_admin(garden_id)
    if err:
        return err
    # Get all plot holders + membership records
    plots = GardenPlot.query.filter_by(garden_id=garden_id, status='assigned').all()
    member_ids = set(p.assigned_to_id for p in plots if p.assigned_to_id)
    member_ids.add(garden.organizer_id)

    memberships = {m.user_id: m for m in GardenMembership.query.filter_by(garden_id=garden_id).all()}
    # Build plot lookup: user_id -> plot info
    plot_lookup = {}
    for p in plots:
        if p.assigned_to_id:
            plot_lookup[p.assigned_to_id] = {
                'plot_number': p.plot_number,
                'plot_custom_name': p.custom_name or '',
                'plot_status': p.status,
            }
    # Build dues lookup for current season
    from datetime import date
    season = date.today().year
    dues_records = GardenDuesRecord.query.filter_by(garden_id=garden_id, season_year=season).all()
    dues_lookup = {d.user_id: d for d in dues_records}

    result = []
    for uid in member_ids:
        u = db.session.get(User, uid)
        if not u:
            continue
        membership = memberships.get(uid)
        role = membership.role if membership else ('organizer' if uid == garden.organizer_id else 'member')
        plot = plot_lookup.get(uid, {})
        dues = dues_lookup.get(uid)
        result.append({
            'user_id': u.id,
            'name': u.display_name or u.username,
            'email': u.email,
            'phone_number': u.phone_number or '',
            'address': u.address or '',
            'city': u.city or '',
            'state': u.state or '',
            'zip_code': u.zip_code or '',
            'profile_image': u.profile_image,
            'role': role,
            'plot_number': plot.get('plot_number', ''),
            'plot_custom_name': plot.get('plot_custom_name', ''),
            'plot_status': plot.get('plot_status', ''),
            'dues_status': dues.status if dues else '',
            'amount_due': dues.amount_due if dues else 0,
            'amount_paid': dues.amount_paid if dues else 0,
            'joined_at': membership.joined_at.isoformat() if membership and membership.joined_at else None,
        })
    return jsonify(result)


@garden_admin_api.route('/<garden_id>/members/export', methods=['GET'])
@token_or_session
def export_members_csv(garden_id):
    """Export garden members as a CSV file."""
    garden, err = require_garden_admin(garden_id)
    if err:
        return err

    import csv, io
    from datetime import date

    # Reuse the same member aggregation logic
    plots = GardenPlot.query.filter_by(garden_id=garden_id, status='assigned').all()
    member_ids = set(p.assigned_to_id for p in plots if p.assigned_to_id)
    member_ids.add(garden.organizer_id)
    memberships = {m.user_id: m for m in GardenMembership.query.filter_by(garden_id=garden_id).all()}
    plot_lookup = {}
    for p in plots:
        if p.assigned_to_id:
            plot_lookup[p.assigned_to_id] = p
    season = date.today().year
    dues_records = GardenDuesRecord.query.filter_by(garden_id=garden_id, season_year=season).all()
    dues_lookup = {d.user_id: d for d in dues_records}

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Name', 'Email', 'Phone', 'Address', 'City', 'State', 'Zip',
                     'Plot #', 'Plot Name', 'Role', 'Dues Status', 'Amount Due', 'Amount Paid', 'Joined'])

    for uid in sorted(member_ids):
        u = db.session.get(User, uid)
        if not u:
            continue
        membership = memberships.get(uid)
        role = membership.role if membership else ('organizer' if uid == garden.organizer_id else 'member')
        p = plot_lookup.get(uid)
        dues = dues_lookup.get(uid)
        writer.writerow([
            u.display_name or u.username,
            u.email,
            u.phone_number or '',
            u.address or '',
            u.city or '',
            u.state or '',
            u.zip_code or '',
            p.plot_number if p else '',
            p.custom_name or '' if p else '',
            role,
            dues.status if dues else '',
            f'{dues.amount_due:.2f}' if dues else '',
            f'{dues.amount_paid:.2f}' if dues else '',
            membership.joined_at.strftime('%Y-%m-%d') if membership and membership.joined_at else '',
        ])

    slug = garden.name.lower().replace(' ', '-')[:30]
    filename = f'members-{slug}-{date.today().isoformat()}.csv'
    from flask import Response
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )


@garden_admin_api.route('/<garden_id>/members/<int:user_id>/role', methods=['POST'])
@token_or_session
def change_member_role(garden_id, user_id):
    """Change a member's role."""
    garden, err = require_garden_admin(garden_id)
    if err:
        return err
    data = request.get_json() or {}
    role = data.get('role', 'member')
    if role not in ('organizer', 'co_organizer', 'treasurer', 'volunteer_lead', 'member'):
        return jsonify({'error': 'Invalid role'}), 400

    membership = GardenMembership.query.filter_by(garden_id=garden_id, user_id=user_id).first()
    if membership:
        membership.role = role
    else:
        membership = GardenMembership(garden_id=garden_id, user_id=user_id, role=role)
        db.session.add(membership)
    db.session.commit()
    return jsonify({'message': f'Role updated to {role}'})


@garden_admin_api.route('/<garden_id>/members/<int:user_id>', methods=['DELETE'])
@token_or_session
def remove_member(garden_id, user_id):
    """Remove a member from the garden (release their plot)."""
    garden, err = require_garden_admin(garden_id)
    if err:
        return err
    if user_id == garden.organizer_id:
        return jsonify({'error': 'Cannot remove the garden organizer'}), 400
    # Release any plots
    plots = GardenPlot.query.filter_by(garden_id=garden_id, assigned_to_id=user_id).all()
    for p in plots:
        p.status = 'available'
        p.assigned_to_id = None
        p.assigned_date = None
    # Remove membership record
    membership = GardenMembership.query.filter_by(garden_id=garden_id, user_id=user_id).first()
    if membership:
        db.session.delete(membership)
    db.session.commit()
    return jsonify({'message': 'Member removed'})


# ===================================================================
#  LAYOUT DRAFTS — Garden redesign planning (Pro-gated)
# ===================================================================

import json as _json


def _draft_to_dict(draft):
    return {
        'id': draft.id,
        'garden_id': draft.garden_id,
        'name': draft.name,
        'grid_rows': draft.grid_rows,
        'grid_cols': draft.grid_cols,
        'layout_data': _json.loads(draft.layout_data) if draft.layout_data else {},
        'notes': draft.notes or '',
        'is_active': draft.is_active,
        'created_at': draft.created_at.isoformat() if draft.created_at else None,
        'updated_at': draft.updated_at.isoformat() if draft.updated_at else None,
    }


@garden_admin_api.route('/<garden_id>/layout-drafts', methods=['POST'])
@token_or_session
def create_layout_draft(garden_id):
    """Create a new layout draft initialized from the current live layout."""
    garden, err = require_garden_admin_pro(garden_id)
    if err:
        return err

    data = request.get_json() or {}
    name = (data.get('name') or '').strip() or f'Draft {datetime.now(timezone.utc).strftime("%b %d")}'

    # Build placements from current live plots
    plots = GardenPlot.query.filter_by(garden_id=garden_id).all()
    placements = {}
    for p in plots:
        if p.grid_row is not None and p.grid_col is not None:
            key = f'{p.grid_row}-{p.grid_col}'
            placements[key] = {
                'plot_id': p.id,
                'plot_number': p.plot_number,
                'status': p.status,
                'size': p.size or '',
                'custom_name': p.custom_name or '',
                'assigned_to': (p.assigned_to.display_name or p.assigned_to.username) if p.assigned_to else '',
            }

    layout_data = _json.dumps({'placements': placements, 'annotations': {}})

    draft = GardenLayoutDraft(
        garden_id=garden_id,
        name=name,
        grid_rows=garden.grid_rows,
        grid_cols=garden.grid_cols,
        layout_data=layout_data,
        notes=data.get('notes', ''),
    )
    db.session.add(draft)
    db.session.commit()
    return jsonify(_draft_to_dict(draft)), 201


@garden_admin_api.route('/<garden_id>/layout-drafts', methods=['GET'])
@token_or_session
def list_layout_drafts(garden_id):
    """List all layout drafts for this garden."""
    garden, err = require_garden_admin_pro(garden_id)
    if err:
        return err
    drafts = GardenLayoutDraft.query.filter_by(garden_id=garden_id).order_by(
        GardenLayoutDraft.updated_at.desc()
    ).all()
    return jsonify([_draft_to_dict(d) for d in drafts])


@garden_admin_api.route('/<garden_id>/layout-drafts/<int:draft_id>', methods=['GET'])
@token_or_session
def get_layout_draft(garden_id, draft_id):
    """Get a specific layout draft."""
    garden, err = require_garden_admin_pro(garden_id)
    if err:
        return err
    draft = db.get_or_404(GardenLayoutDraft, draft_id)
    if draft.garden_id != garden_id:
        return jsonify({'error': 'Draft not found in this garden'}), 404
    return jsonify(_draft_to_dict(draft))


@garden_admin_api.route('/<garden_id>/layout-drafts/<int:draft_id>', methods=['PUT'])
@token_or_session
def save_layout_draft(garden_id, draft_id):
    """Save changes to a layout draft."""
    garden, err = require_garden_admin_pro(garden_id)
    if err:
        return err
    draft = db.get_or_404(GardenLayoutDraft, draft_id)
    if draft.garden_id != garden_id:
        return jsonify({'error': 'Draft not found in this garden'}), 404

    data = request.get_json() or {}
    if 'name' in data:
        draft.name = data['name'][:100]
    if 'grid_rows' in data:
        draft.grid_rows = max(2, min(20, int(data['grid_rows'])))
    if 'grid_cols' in data:
        draft.grid_cols = max(2, min(20, int(data['grid_cols'])))
    if 'layout_data' in data:
        draft.layout_data = _json.dumps(data['layout_data'])
    if 'notes' in data:
        draft.notes = data['notes'][:2000]
    draft.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(_draft_to_dict(draft))


@garden_admin_api.route('/<garden_id>/layout-drafts/<int:draft_id>', methods=['DELETE'])
@token_or_session
def delete_layout_draft(garden_id, draft_id):
    """Delete a layout draft."""
    garden, err = require_garden_admin_pro(garden_id)
    if err:
        return err
    draft = db.get_or_404(GardenLayoutDraft, draft_id)
    if draft.garden_id != garden_id:
        return jsonify({'error': 'Draft not found in this garden'}), 404
    db.session.delete(draft)
    db.session.commit()
    return jsonify({'message': 'Draft deleted'})


@garden_admin_api.route('/<garden_id>/layout-drafts/<int:draft_id>/publish', methods=['POST'])
@token_or_session
def publish_layout_draft(garden_id, draft_id):
    """Apply a draft layout to the live garden, updating plot positions and grid dimensions."""
    garden, err = require_garden_admin_pro(garden_id)
    if err:
        return err
    draft = db.get_or_404(GardenLayoutDraft, draft_id)
    if draft.garden_id != garden_id:
        return jsonify({'error': 'Draft not found in this garden'}), 404

    layout = _json.loads(draft.layout_data) if draft.layout_data else {}
    placements = layout.get('placements', {})

    # Update grid dimensions
    garden.grid_rows = draft.grid_rows
    garden.grid_cols = draft.grid_cols

    # Clear all plot grid positions first
    plots = GardenPlot.query.filter_by(garden_id=garden_id).all()
    plot_map = {p.id: p for p in plots}
    for p in plots:
        p.grid_row = None
        p.grid_col = None

    # Apply placements from draft
    for key, placement in placements.items():
        parts = key.split('-')
        if len(parts) != 2:
            continue
        row, col = int(parts[0]), int(parts[1])
        plot_id = placement.get('plot_id')
        if plot_id and plot_id in plot_map:
            plot_map[plot_id].grid_row = row
            plot_map[plot_id].grid_col = col

    db.session.commit()

    # Mark draft as no longer active (published)
    draft.is_active = False
    draft.notes = (draft.notes or '') + f'\n[Published {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")} UTC]'
    db.session.commit()

    return jsonify({'message': f'Layout "{draft.name}" published to live garden', 'grid_rows': garden.grid_rows, 'grid_cols': garden.grid_cols})


# ===================================================================
#  STRIPE TAP TO PAY — Tap-to-Pay on iPhone for in-person dues
# ===================================================================

@garden_admin_api.route('/terminal/connection_token', methods=['POST'])
@token_or_session
def terminal_connection_token():
    """Issue a Stripe Terminal connection token for the iOS SDK.

    The iOS Stripe Terminal SDK exchanges this short-lived token for a
    session it uses to discover readers (Tap-to-Pay on iPhone = the device
    itself) and process payments. The token is scoped to the manager's
    Stripe Connect account so funds and reader registration both flow
    through them, not the platform.
    """
    import logging
    log = logging.getLogger(__name__)
    from app import stripe_service
    import stripe as _stripe

    if not stripe_service.is_configured():
        return jsonify({'error': 'Payments are not configured on this instance.'}), 503

    user = get_current_user()

    # The manager must have completed Connect onboarding so we have an
    # account to scope the token to. Tap-to-Pay routes the charge through
    # that account.
    # Retrieve the connected account once and reuse it for every gate below.
    # Each check used to fetch it independently, so a single tap cost four
    # Stripe round-trips before the card sheet could appear.
    acct, acct_err = stripe_service.get_connect_account(user)
    if not getattr(user, 'stripe_connect_account_id', None) or not stripe_service.connect_account_ready(user, acct=acct):
        return jsonify({
            'error': (f'Could not read your Stripe account ({acct_err}).'
                      if acct_err else
                      "Finish payout onboarding before collecting in person."),
            'reason': 'manager_payout_not_ready',
        }), 409

    # Card-present acceptance rides on the ordinary `card_payments` capability
    # — Stripe has no separate card_present one. Check it and refuse early with
    # an actionable reason rather than letting the token creation fail opaquely.
    cap_status, cap_detail = stripe_service.card_present_capability_status(user, acct=acct)
    if cap_status != 'active':
        # Say what was actually found. "Still being enabled" reads as a wait
        # when the real cause may be a Stripe error, the wrong account, or a
        # capability Stripe has explicitly declined.
        if cap_detail:
            msg = f'Tap to Pay is unavailable: {cap_detail}.'
        elif cap_status == 'pending':
            msg = ('Stripe is still reviewing card payments for this account '
                   '(card_payments: pending). Check the connected account in '
                   'your Stripe dashboard for outstanding requirements.')
        elif cap_status == 'inactive':
            msg = ('Card payments are switched off for this account '
                   '(card_payments: inactive). Open the connected account in '
                   'your Stripe dashboard to see what it is waiting on.')
        else:
            msg = ('Card payments are not enabled on this account '
                   f'(card_payments: {cap_status or "not present"}).')
        return jsonify({
            'error': msg,
            'reason': 'card_present_not_active',
            'capability_status': cap_status,
            'capability_detail': cap_detail,
            'connect_account_id': getattr(user, 'stripe_connect_account_id', None),
        }), 409

    # Tap to Pay connects the device as a reader registered to a Location on
    # the manager's own account.
    location_id = stripe_service.ensure_terminal_location(user, acct=acct)
    if not location_id:
        return jsonify({
            'error': ('Could not set up a payment location for your account. '
                      'Add a business address in your Stripe dashboard, then '
                      'try again.'),
            'reason': 'terminal_location_unavailable',
        }), 409

    try:
        _stripe.api_key = _os_get('STRIPE_SECRET_KEY')
        token = _stripe.terminal.ConnectionToken.create(
            stripe_account=user.stripe_connect_account_id,
        )
        return jsonify({'secret': token.secret, 'location_id': location_id})
    except _stripe.error.StripeError as e:
        log.exception('Terminal connection_token creation failed')
        return jsonify({'error': stripe_service.error_detail(e)}), 500


@garden_admin_api.route('/<int:garden_id>/dues/<int:dues_id>/collect-in-person', methods=['POST'])
@token_or_session
@limiter.limit("12 per minute")
def collect_dues_in_person(garden_id, dues_id):
    """Create a `card_present` PaymentIntent for an in-person dues collection.

    Routed as a destination charge to the manager's Connect account — same
    pattern as the gardener-side ``pay_dues`` flow, just with a different
    payment method type. The iOS Terminal SDK consumes the client_secret to
    drive the tap-card UX, then we mark the record paid via finalize.
    """
    import logging
    log = logging.getLogger(__name__)
    from app import stripe_service
    from app.pricing import dues_fee_cents

    garden, err = require_garden_admin(garden_id)
    if err:
        return err

    rec = db.session.get(GardenDuesRecord, dues_id)
    if not rec or rec.garden_id != garden_id:
        return jsonify({'error': 'Dues record not found'}), 404
    if rec.status in ('paid', 'waived', 'comp'):
        return jsonify({'error': 'Dues already settled'}), 400

    remaining = rec.amount_due - rec.amount_paid
    if remaining <= 0:
        return jsonify({'error': 'No balance due'}), 400

    if not stripe_service.is_configured():
        return jsonify({'error': 'Payments are not configured on this instance.'}), 503

    organizer = garden.organizer
    if not organizer or not stripe_service.connect_account_ready(organizer):
        return jsonify({
            'error': "Finish payout onboarding before collecting in person.",
            'reason': 'manager_payout_not_ready',
        }), 409

    # charges_enabled alone doesn't prove the account can take *card-present*
    # money; Stripe rejects the PaymentIntent below without this capability.
    if not stripe_service.connect_card_present_ready(organizer):
        return jsonify({
            'error': ("In-person card payments aren't enabled on this garden's "
                      "Stripe account yet."),
            'reason': 'card_present_not_active',
        }), 409

    # The reader is connected under the *signed-in user's* Connect account —
    # that's what the connection token is scoped to — while the charge is
    # created on the garden organizer's. When those differ the PaymentIntent is
    # invisible to the reader, and Stripe reports it as "No such
    # payment_intent". Say what actually went wrong instead.
    collector = get_current_user()
    if (getattr(collector, 'stripe_connect_account_id', None)
            != organizer.stripe_connect_account_id):
        return jsonify({
            'error': ("In-person charges for this garden have to be taken by its "
                      "organizer — your Stripe account isn't the one that "
                      "receives its payouts."),
            'reason': 'reader_account_mismatch',
        }), 409

    amount_cents = int(round(remaining * 100))
    application_fee_cents = dues_fee_cents(amount_cents)

    try:
        import stripe as _stripe
        _stripe.api_key = _os_get('STRIPE_SECRET_KEY')
        pi = _stripe.PaymentIntent.create(
            amount=amount_cents,
            currency='usd',
            payment_method_types=['card_present'],
            capture_method='automatic',
            metadata={
                'type': 'garden_dues_in_person',
                'garden_id': str(garden_id),
                'dues_id': str(rec.id),
                'collected_by_user_id': str(get_current_user().id),
                'payer_user_id': str(rec.user_id),
            },
            # Direct charge ON the connected account, not a destination charge
            # on the platform. The Terminal connection token is scoped to this
            # account, so a PaymentIntent living on the platform is invisible to
            # the reader — Stripe answers "No such payment_intent". The platform
            # still takes its cut via application_fee_amount.
            application_fee_amount=application_fee_cents,
            stripe_account=organizer.stripe_connect_account_id,
            # Stable key: re-tapping the same record+amount reuses one PaymentIntent
            # within Stripe's 24h window instead of creating duplicates.
            idempotency_key=f'dues-{rec.id}-{amount_cents}',
        )
        return jsonify({
            'client_secret': pi.client_secret,
            'payment_intent_id': pi.id,
            'amount': amount_cents,
            'currency': 'usd',
            'dues_id': rec.id,
            'connected_account_id': organizer.stripe_connect_account_id,
        })
    except _stripe.error.StripeError as e:
        log.exception('Tap-to-pay PaymentIntent creation failed')
        return jsonify({'error': stripe_service.error_detail(e)}), 500


@garden_admin_api.route('/<int:garden_id>/dues/<int:dues_id>/finalize-in-person', methods=['POST'])
@token_or_session
@limiter.limit("20 per minute")
def finalize_dues_in_person(garden_id, dues_id):
    """After Terminal processes the tap, mark the dues record paid.

    The Stripe webhook (``payment_intent.succeeded``) is the authoritative
    source — this endpoint is the instant-UX path for the iOS SDK to settle
    the record while the webhook catches up.
    """
    import logging
    log = logging.getLogger(__name__)
    from app import stripe_service
    import stripe as _stripe

    garden, err = require_garden_admin(garden_id)
    if err:
        return err

    rec = db.session.get(GardenDuesRecord, dues_id)
    if not rec or rec.garden_id != garden_id:
        return jsonify({'error': 'Dues record not found'}), 404

    data = request.get_json() or {}
    payment_intent_id = data.get('payment_intent_id', '').strip()
    if not payment_intent_id:
        return jsonify({'error': 'payment_intent_id is required'}), 400

    # Idempotent — webhook may have already settled it.
    if rec.status == 'paid' and getattr(rec, 'stripe_payment_intent_id', None) == payment_intent_id:
        return jsonify({'message': 'Already finalized', 'dues_status': rec.status})

    if stripe_service.is_configured():
        try:
            _stripe.api_key = _os_get('STRIPE_SECRET_KEY')
            # In-person PaymentIntents live on the connected account, so the
            # lookup has to be scoped there too.
            organizer = garden.organizer
            pi = _stripe.PaymentIntent.retrieve(
                payment_intent_id,
                stripe_account=getattr(organizer, 'stripe_connect_account_id', None),
            )
            if pi.status != 'succeeded':
                return jsonify({
                    'error': f'Payment is in status "{pi.status}"; cannot finalize yet.',
                }), 400
        except _stripe.error.StripeError as e:
            log.exception('Tap-to-pay PI retrieve failed')
            return jsonify({'error': stripe_service.error_detail(e)}), 500

    rec.amount_paid = rec.amount_due
    rec.status = 'paid'
    rec.payment_method = 'tap_to_pay'
    rec.payment_date = date.today()
    if hasattr(rec, 'stripe_payment_intent_id'):
        rec.stripe_payment_intent_id = payment_intent_id
    rec.payment_note = f'Stripe Terminal (Tap to Pay): {payment_intent_id}'
    db.session.commit()

    # Notify the member (in-app) and bump the badge.
    payer = User.query.get(rec.user_id)
    if payer:
        notify(
            user_id=payer.id,
            type='dues_paid',
            title='Dues collected in person',
            body=f'Your dues for {garden.name} were marked paid via Tap to Pay.',
            link=f'/gardens/{garden_id}',
            garden_id=garden_id,
        )

    return jsonify({
        'message': 'Dues marked paid.',
        'dues_status': rec.status,
    })


def _os_get(key):
    """Tiny helper to read env without `import os` at module top of every block."""
    import os
    return os.environ.get(key, '')


@garden_admin_api.route('/<int:garden_id>/in-person-charge', methods=['POST'])
@token_or_session
@limiter.limit("12 per minute")
def in_person_ad_hoc_charge(garden_id):
    """Create a `card_present` PaymentIntent for an ad-hoc in-person charge.

    Unlike ``collect_dues_in_person`` this isn't tied to a specific dues
    record — the manager enters any amount + memo and collects. Useful for
    plant/seedling sales, tool deposits, day-pass workshops, etc. Funds
    route to the manager's Connect account as a destination charge; the
    Stripe Connect dashboard is the system of record for the sale.
    """
    import logging
    log = logging.getLogger(__name__)
    from app import stripe_service
    from app.pricing import dues_fee_cents
    import stripe as _stripe

    garden, err = require_garden_admin(garden_id)
    if err:
        return err

    if not stripe_service.is_configured():
        return jsonify({'error': 'Payments are not configured on this instance.'}), 503

    organizer = garden.organizer
    if not organizer or not stripe_service.connect_account_ready(organizer):
        return jsonify({
            'error': "Finish payout onboarding before collecting in person.",
            'reason': 'manager_payout_not_ready',
        }), 409

    # charges_enabled alone doesn't prove the account can take *card-present*
    # money; Stripe rejects the PaymentIntent below without this capability.
    if not stripe_service.connect_card_present_ready(organizer):
        return jsonify({
            'error': ("In-person card payments aren't enabled on this garden's "
                      "Stripe account yet."),
            'reason': 'card_present_not_active',
        }), 409

    # The reader is connected under the *signed-in user's* Connect account —
    # that's what the connection token is scoped to — while the charge is
    # created on the garden organizer's. When those differ the PaymentIntent is
    # invisible to the reader, and Stripe reports it as "No such
    # payment_intent". Say what actually went wrong instead.
    collector = get_current_user()
    if (getattr(collector, 'stripe_connect_account_id', None)
            != organizer.stripe_connect_account_id):
        return jsonify({
            'error': ("In-person charges for this garden have to be taken by its "
                      "organizer — your Stripe account isn't the one that "
                      "receives its payouts."),
            'reason': 'reader_account_mismatch',
        }), 409

    data = request.get_json() or {}
    try:
        amount_cents = int(data.get('amount_cents') or 0)
    except (TypeError, ValueError):
        amount_cents = 0
    if amount_cents < 50:  # Stripe minimum is $0.50 USD
        return jsonify({'error': 'Amount must be at least $0.50.'}), 400
    if amount_cents > 1_000_000:  # $10,000 sanity ceiling
        return jsonify({'error': 'Amount exceeds the per-transaction ceiling.'}), 400

    memo = (data.get('memo') or '').strip()[:300]
    application_fee_cents = dues_fee_cents(amount_cents)
    # Ad-hoc amounts aren't unique, so dedupe on a client-supplied key (the iOS
    # client reuses it on retry); fall back to a fresh key when absent.
    import uuid
    idem_key = (data.get('idempotency_key') or '').strip() or uuid.uuid4().hex

    try:
        _stripe.api_key = _os_get('STRIPE_SECRET_KEY')
        pi = _stripe.PaymentIntent.create(
            amount=amount_cents,
            currency='usd',
            payment_method_types=['card_present'],
            capture_method='automatic',
            description=memo or 'Garden in-person sale',
            metadata={
                'type': 'garden_in_person_sale',
                'garden_id': str(garden_id),
                'collected_by_user_id': str(get_current_user().id),
                'memo': memo,
            },
            # Direct charge on the connected account — see the dues flow above.
            application_fee_amount=application_fee_cents,
            stripe_account=organizer.stripe_connect_account_id,
            idempotency_key=idem_key,
        )
        return jsonify({
            'client_secret': pi.client_secret,
            'payment_intent_id': pi.id,
            'amount': amount_cents,
            'currency': 'usd',
            'connected_account_id': organizer.stripe_connect_account_id,
        })
    except _stripe.error.StripeError as e:
        log.exception('Ad-hoc in-person PI creation failed')
        return jsonify({'error': stripe_service.error_detail(e)}), 500
