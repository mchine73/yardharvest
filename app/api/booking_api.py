"""Public booking page (Calendly-style scheduling) + owner admin config.

Public endpoints (no auth) power /book:
  GET  /api/booking/config           — page copy + active meeting types
  GET  /api/booking/slots?type=slug  — open slots (UTC instants) for a type
  POST /api/booking/book             — create a booking
  GET  /api/booking/manage/<pid>     — booking detail for the manage link
  POST /api/booking/manage/<pid>/cancel

Admin endpoints (site admin) configure it:
  GET  /api/booking/admin/overview
  PUT  /api/booking/admin/settings
  POST/PUT/DELETE /api/booking/admin/types[/<id>]
  PUT  /api/booking/admin/availability
  GET  /api/booking/admin/bookings
  GET  /api/booking/admin/zoho/calendars   — list calendars to find the UID

A confirmed booking writes to the owner's Zoho calendar (best-effort) and
upserts a CRM lead (status Engaged, source 'Booking') so inbound meetings feed
the BDR funnel.
"""
import logging
import re
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo, available_timezones

from flask import Blueprint, request, jsonify

from app import db, limiter
from app.models import BookingSettings, BookingType, AvailabilityRule, Booking
from app.api.token_auth import token_or_session
from app.helpers import admin_required
from app import booking_service
from app import zoho_calendar_service as zoho
from app import email_service

log = logging.getLogger(__name__)

booking_api = Blueprint('booking_api', __name__, url_prefix='/api/booking')

_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
_VALID_TZS = available_timezones()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _slugify(text):
    s = re.sub(r'[^a-z0-9]+', '-', (text or '').lower()).strip('-')
    return s or 'meeting'


def _unique_slug(base, exclude_id=None):
    slug = base
    n = 2
    while True:
        q = BookingType.query.filter_by(slug=slug)
        if exclude_id:
            q = q.filter(BookingType.id != exclude_id)
        if not q.first():
            return slug
        slug = f'{base}-{n}'
        n += 1


def _parse_iso_utc(s):
    """Parse an ISO-8601 instant to naive UTC. Returns None on failure."""
    if not s or not isinstance(s, str):
        return None
    try:
        dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
    except ValueError:
        return None
    return booking_service.to_naive_utc(dt)


def _int(val, default=0, lo=None, hi=None):
    try:
        n = int(val)
    except (TypeError, ValueError):
        return default
    if lo is not None:
        n = max(lo, n)
    if hi is not None:
        n = min(hi, n)
    return n


def _slots_payload(bt, settings):
    starts = booking_service.available_slot_starts(bt, settings=settings)
    return [s.replace(tzinfo=timezone.utc).isoformat() for s in starts]


# ---------------------------------------------------------------------------
# Public
# ---------------------------------------------------------------------------
@booking_api.route('/config', methods=['GET'])
@limiter.limit('60 per minute')
def config():
    s = BookingSettings.get()
    types = (BookingType.query
             .filter_by(is_active=True)
             .order_by(BookingType.sort_order, BookingType.id)
             .all())
    return jsonify({
        'settings': {
            'timezone': s.timezone, 'owner_name': s.owner_name or '',
            'heading': s.heading or 'Book time', 'intro': s.intro or '',
        },
        'types': [t.to_public_dict() for t in types],
    })


@booking_api.route('/slots', methods=['GET'])
@limiter.limit('60 per minute')
def slots():
    slug = (request.args.get('type') or '').strip()
    bt = BookingType.query.filter_by(slug=slug, is_active=True).first()
    if not bt:
        return jsonify({'error': 'Meeting type not found'}), 404
    s = BookingSettings.get()
    return jsonify({
        'type': bt.to_public_dict(),
        'owner_timezone': s.timezone,
        'slots': _slots_payload(bt, s),
    })


@booking_api.route('/book', methods=['POST'])
@limiter.limit('10 per hour')
def book():
    data = request.get_json(silent=True) or {}
    slug = (data.get('type') or '').strip()
    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip().lower()
    notes = (data.get('notes') or '').strip()
    phone = (data.get('phone') or '').strip()
    visitor_tz = (data.get('timezone') or '').strip()
    start = _parse_iso_utc(data.get('start'))

    if not (name and email and slug and start):
        return jsonify({'error': 'Name, email, meeting type, and time are required.'}), 400
    if not _EMAIL_RE.match(email):
        return jsonify({'error': 'Please enter a valid email address.'}), 400
    if visitor_tz and visitor_tz not in _VALID_TZS:
        visitor_tz = ''  # ignore a bogus tz rather than fail

    bt = BookingType.query.filter_by(slug=slug, is_active=True).first()
    if not bt:
        return jsonify({'error': 'Meeting type not found.'}), 404

    settings = BookingSettings.get()
    if not booking_service.slot_is_open(bt, start, settings=settings):
        return jsonify({'error': 'Sorry, that time is no longer available. '
                                 'Please pick another slot.'}), 409

    booking = Booking(
        booking_type_id=bt.id,
        start_at=start,
        end_at=start + timedelta(minutes=bt.duration_min),
        invitee_timezone=visitor_tz or settings.timezone,
        invitee_name=name[:120], invitee_email=email[:120],
        invitee_phone=phone[:30] or None, notes=notes or None,
        status='confirmed',
        zoho_sync_status='pending',
    )
    db.session.add(booking)
    db.session.commit()  # booking is saved first; integrations are best-effort

    _sync_to_zoho(booking, settings)
    _upsert_crm_lead(booking, bt, settings)
    db.session.commit()

    # Notifications (best-effort — never fail the booking on a mail error).
    try:
        email_service.send_booking_confirmation(booking, owner_name=settings.owner_name)
        email_service.send_booking_owner_notification(booking, owner_name=settings.owner_name)
    except Exception:  # noqa: BLE001
        log.exception('[BOOKING] confirmation email failed for %s', booking.public_id)

    return jsonify({'booking': booking.to_dict(),
                    'manage_path': f'/book/manage/{booking.public_id}'}), 201


def _sync_to_zoho(booking, settings):
    """Create the calendar event; record sync status on the booking row."""
    if not (zoho.is_configured() and zoho.has_calendar()):
        booking.zoho_sync_status = 'skipped'
        return
    bt = booking.booking_type
    try:
        desc = (f'Booked via YardHarvest.\nWith: {booking.invitee_name} '
                f'<{booking.invitee_email}>')
        if booking.invitee_phone:
            desc += f'\nPhone: {booking.invitee_phone}'
        if booking.notes:
            desc += f'\nNotes: {booking.notes}'
        uid = zoho.create_event(
            title=f'{bt.name}: {booking.invitee_name}',
            start_utc=booking.start_at, end_utc=booking.end_at,
            description=desc, location=(bt.location or ''),
            attendee_email=booking.invitee_email,
            attendee_name=booking.invitee_name,
        )
        booking.zoho_event_uid = uid
        booking.zoho_sync_status = 'synced'
        booking.zoho_sync_error = None
    except Exception as exc:  # noqa: BLE001 — degrade, don't fail the booking
        booking.zoho_sync_status = 'failed'
        booking.zoho_sync_error = str(exc)[:255]
        log.warning('[BOOKING] Zoho sync failed for %s: %s', booking.public_id, exc)


def _upsert_crm_lead(booking, bt, settings):
    """Upsert a CRM contact and log the meeting (feeds the BDR funnel).

    Best-effort: a CRM failure rolls back only the CRM changes — the booking
    (already committed) survives. Uses user_id=None on the activity since the
    booker is anonymous (no CRM user in the request)."""
    try:
        from app.crm.models import Contact, Activity, _utcnow
        from sqlalchemy import func
        contact = (Contact.query
                   .filter(func.lower(Contact.email) == booking.invitee_email)
                   .first())
        now = _utcnow()
        # The correct next touch is the day AFTER the meeting (a post-meeting
        # follow-up) — due-today would make the agent draft another email
        # BEFORE the meeting even happens.
        followup_date = booking.end_at.date() + timedelta(days=1)
        if contact is None:
            contact = Contact(
                name=booking.invitee_name[:120], email=booking.invitee_email[:120],
                phone=booking.invitee_phone, lead_status='Engaged',
                source='Booking', last_contacted_at=now,
                next_action_at=followup_date,
                next_action_note=f'Post-meeting follow-up ({bt.name})',
            )
            db.session.add(contact)
            db.session.flush()
        else:
            contact.last_contacted_at = now
            if (contact.lead_status or 'New') in ('New', 'Working', 'Nurture'):
                contact.lead_status = 'Engaged'
            # Booking a meeting IS a reply — reset the no-reply clock and aim
            # the next action past the meeting.
            contact.followup_count = 0
            contact.next_action_at = followup_date
            contact.next_action_note = f'Post-meeting follow-up ({bt.name})'
            if not contact.phone and booking.invitee_phone:
                contact.phone = booking.invitee_phone
            # Withdraw any queued automated follow-ups — a person who just
            # booked a meeting must not get a "just checking in" nudge.
            from app.crm.autonomy import cancel_pending_actions
            cancel_pending_actions(contact.id, 'Superseded: meeting booked',
                                   types=('follow_up_email', 'scout'))

        when = booking.start_at.replace(tzinfo=timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
        db.session.add(Activity(
            kind='meeting',
            description=f'Booked "{bt.name}" for {when} via the booking page.',
            contact_id=contact.id, user_id=None))
        booking.crm_contact_id = contact.id
    except Exception:  # noqa: BLE001
        db.session.rollback()
        log.exception('[BOOKING] CRM upsert failed for %s', booking.public_id)


@booking_api.route('/manage/<public_id>', methods=['GET'])
@limiter.limit('30 per minute')
def manage(public_id):
    booking = Booking.query.filter_by(public_id=public_id).first()
    if not booking:
        return jsonify({'error': 'Booking not found'}), 404
    return jsonify({'booking': booking.to_dict()})


@booking_api.route('/manage/<public_id>/cancel', methods=['POST'])
@limiter.limit('20 per hour')
def cancel(public_id):
    booking = Booking.query.filter_by(public_id=public_id).first()
    if not booking:
        return jsonify({'error': 'Booking not found'}), 404
    if booking.status == 'cancelled':
        return jsonify({'booking': booking.to_dict()})  # idempotent

    booking.status = 'cancelled'
    booking.cancelled_at = datetime.now(timezone.utc).replace(tzinfo=None)
    if booking.zoho_event_uid:
        zoho.delete_event(booking.zoho_event_uid)  # best-effort
    # Reflect cancellation in the CRM timeline + retarget the next action:
    # a "post-meeting follow-up" aimed at a meeting that won't happen becomes
    # a near-term re-engage instead.
    if booking.crm_contact_id:
        try:
            from app.crm.models import Activity, Contact, _utcnow
            db.session.add(Activity(
                kind='meeting',
                description=f'Cancelled booking ({booking.public_id}).',
                contact_id=booking.crm_contact_id, user_id=None))
            c = db.session.get(Contact, booking.crm_contact_id)
            if c and (c.next_action_note or '').startswith('Post-meeting follow-up'):
                c.next_action_at = _utcnow().date() + timedelta(days=2)
                c.next_action_note = 'Meeting cancelled — re-engage'
        except Exception:  # noqa: BLE001
            log.exception('[BOOKING] CRM cancel-log failed')
    settings = BookingSettings.get()
    db.session.commit()
    try:
        email_service.send_booking_cancellation(booking, owner_name=settings.owner_name)
    except Exception:  # noqa: BLE001
        log.exception('[BOOKING] cancellation email failed for %s', booking.public_id)
    return jsonify({'booking': booking.to_dict()})


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------
@booking_api.route('/admin/overview', methods=['GET'])
@token_or_session
@admin_required
def admin_overview():
    s = BookingSettings.get()
    types = BookingType.query.order_by(BookingType.sort_order, BookingType.id).all()
    rules = AvailabilityRule.query.order_by(
        AvailabilityRule.day_of_week, AvailabilityRule.start_min).all()
    return jsonify({
        'settings': s.to_dict(),
        'types': [t.to_admin_dict() for t in types],
        'availability': [r.to_dict() for r in rules],
        'zoho': {'configured': zoho.is_configured(),
                 'calendar_uid_set': zoho.has_calendar()},
    })


@booking_api.route('/admin/settings', methods=['PUT'])
@token_or_session
@admin_required
def admin_update_settings():
    data = request.get_json(silent=True) or {}
    s = BookingSettings.get()
    if 'timezone' in data:
        tz = (data.get('timezone') or '').strip()
        if tz not in _VALID_TZS:
            return jsonify({'error': f'Unknown timezone: {tz}'}), 400
        s.timezone = tz
    if 'owner_name' in data:
        s.owner_name = (data.get('owner_name') or '').strip()[:120]
    if 'heading' in data:
        s.heading = (data.get('heading') or '').strip()[:160]
    if 'intro' in data:
        s.intro = (data.get('intro') or '').strip()
    if 'min_notice_hours' in data:
        s.min_notice_hours = _int(data.get('min_notice_hours'), 12, lo=0, hi=24 * 30)
    if 'max_advance_days' in data:
        s.max_advance_days = _int(data.get('max_advance_days'), 30, lo=1, hi=365)
    if 'slot_granularity_min' in data:
        s.slot_granularity_min = _int(data.get('slot_granularity_min'), 30, lo=5, hi=240)
    if 'max_per_day' in data:
        s.max_per_day = _int(data.get('max_per_day'), 0, lo=0, hi=50)
    if 'block_zoho_busy' in data:
        s.block_zoho_busy = bool(data.get('block_zoho_busy'))
    db.session.commit()
    return jsonify({'settings': s.to_dict()})


def _apply_type_fields(bt, data):
    if 'name' in data:
        bt.name = (data.get('name') or '').strip()[:120] or bt.name
    if 'description' in data:
        bt.description = (data.get('description') or '').strip()
    if 'duration_min' in data:
        bt.duration_min = _int(data.get('duration_min'), bt.duration_min or 30, lo=5, hi=480)
    if 'location' in data:
        bt.location = (data.get('location') or '').strip()[:255]
    if 'buffer_before_min' in data:
        bt.buffer_before_min = _int(data.get('buffer_before_min'), 0, lo=0, hi=240)
    if 'buffer_after_min' in data:
        bt.buffer_after_min = _int(data.get('buffer_after_min'), 0, lo=0, hi=240)
    if 'color' in data:
        c = (data.get('color') or '').strip()
        if re.match(r'^#[0-9a-fA-F]{6}$', c):
            bt.color = c
    if 'is_active' in data:
        bt.is_active = bool(data.get('is_active'))
    if 'sort_order' in data:
        bt.sort_order = _int(data.get('sort_order'), 0, lo=0, hi=999)


@booking_api.route('/admin/types', methods=['POST'])
@token_or_session
@admin_required
def admin_create_type():
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Name is required.'}), 400
    bt = BookingType(name=name[:120], duration_min=30)
    _apply_type_fields(bt, data)
    base = _slugify(data.get('slug') or name)
    bt.slug = _unique_slug(base)
    db.session.add(bt)
    db.session.commit()
    return jsonify({'type': bt.to_admin_dict()}), 201


@booking_api.route('/admin/types/<int:type_id>', methods=['PUT'])
@token_or_session
@admin_required
def admin_update_type(type_id):
    bt = db.session.get(BookingType, type_id)
    if not bt:
        return jsonify({'error': 'Not found'}), 404
    data = request.get_json(silent=True) or {}
    _apply_type_fields(bt, data)
    if data.get('slug'):
        bt.slug = _unique_slug(_slugify(data['slug']), exclude_id=bt.id)
    db.session.commit()
    return jsonify({'type': bt.to_admin_dict()})


@booking_api.route('/admin/types/<int:type_id>', methods=['DELETE'])
@token_or_session
@admin_required
def admin_delete_type(type_id):
    bt = db.session.get(BookingType, type_id)
    if not bt:
        return jsonify({'error': 'Not found'}), 404
    # Preserve history: if any bookings reference this type, deactivate instead
    # of deleting (the FK would block a hard delete anyway).
    if bt.bookings.first():
        bt.is_active = False
        db.session.commit()
        return jsonify({'deactivated': True})
    db.session.delete(bt)
    db.session.commit()
    return jsonify({'deleted': True})


@booking_api.route('/admin/availability', methods=['PUT'])
@token_or_session
@admin_required
def admin_set_availability():
    data = request.get_json(silent=True) or {}
    rules = data.get('rules')
    if not isinstance(rules, list):
        return jsonify({'error': 'Expected a "rules" array.'}), 400
    clean = []
    for r in rules:
        try:
            dow = int(r['day_of_week']); start = int(r['start_min']); end = int(r['end_min'])
        except (KeyError, TypeError, ValueError):
            return jsonify({'error': 'Each rule needs day_of_week, start_min, end_min.'}), 400
        if not (0 <= dow <= 6 and 0 <= start < end <= 1440):
            return jsonify({'error': 'Invalid rule range.'}), 400
        clean.append((dow, start, end))
    AvailabilityRule.query.delete()
    for dow, start, end in clean:
        db.session.add(AvailabilityRule(day_of_week=dow, start_min=start, end_min=end))
    db.session.commit()
    return jsonify({'availability': [r.to_dict() for r in
                                     AvailabilityRule.query.order_by(
                                         AvailabilityRule.day_of_week,
                                         AvailabilityRule.start_min).all()]})


@booking_api.route('/admin/bookings', methods=['GET'])
@token_or_session
@admin_required
def admin_bookings():
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    upcoming = (Booking.query
                .filter(Booking.status == 'confirmed', Booking.start_at >= now)
                .order_by(Booking.start_at).limit(100).all())
    recent = (Booking.query
              .filter(Booking.start_at < now)
              .order_by(Booking.start_at.desc()).limit(50).all())
    return jsonify({'upcoming': [b.to_dict() for b in upcoming],
                    'past': [b.to_dict() for b in recent]})


@booking_api.route('/admin/zoho/calendars', methods=['GET'])
@token_or_session
@admin_required
def admin_zoho_calendars():
    """List the account's calendars so the owner can find their calendar UID."""
    if not zoho.is_configured():
        return jsonify({'configured': False, 'calendars': [],
                        'error': 'Zoho OAuth env vars not set.'})
    try:
        return jsonify({'configured': True, 'calendars': zoho.list_calendars()})
    except Exception as exc:  # noqa: BLE001
        return jsonify({'configured': True, 'calendars': [],
                        'error': str(exc)[:300]}), 502
