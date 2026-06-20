"""Community Gardens REST API endpoints."""
from flask import Blueprint, request, jsonify, abort
from flask_login import login_required, current_user
from app.api.token_auth import token_or_session, get_current_user
from app import db
from app.models import (
    CommunityGarden, GardenPlot, GardenWaitlist, SharedResource,
    GardenEvent, EventRSVP, HarvestLog, User, ResourceCheckoutLog,
    VolunteerShift, ShiftSignup, PlotAssignmentHistory,
    GardenWeatherAlert, GardenDuesRecord,
    GardenAnnouncement, GardenComment, GardenCommentLike, GardenLayoutFeature
)
from sqlalchemy.orm import joinedload
from app.helpers import format_display_name
from app.api.notifications_api import notify
from datetime import datetime, timezone, timedelta, date, time as dtime
from sqlalchemy import func
import re
import logging

log = logging.getLogger(__name__)

gardens_api = Blueprint('gardens_api', __name__, url_prefix='/api/gardens')


@gardens_api.url_value_preprocessor
def _resolve_garden_url_value(endpoint, values):
    """Resolve an opaque ``grd_…`` public_id (or numeric PK) in the URL to the
    integer ``garden_id`` before any handler runs, so downstream queries are
    unchanged. Numeric refs pass through; unknown public_ids 404."""
    if values and 'garden_id' in values:
        from app.helpers import resolve_garden_pk
        values['garden_id'] = resolve_garden_pk(values['garden_id'])


# Upper bound on plots created in a single request (DoS / fat-finger guard).
MAX_BULK_PLOTS = 1000


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text


def garden_to_dict(garden, include_stats=False):
    d = {
        'id': garden.id,
        'public_id': garden.public_id,
        'name': garden.name,
        'slug': garden.slug,
        'description': garden.description,
        'address': garden.address,
        'city': garden.city,
        'state': garden.state,
        'zip_code': garden.zip_code,
        'photo_url': garden.photo_url,
        'total_plots': garden.total_plots,
        'plot_fee_annual': garden.plot_fee_annual,
        'operating_model': garden.operating_model,
        'season_start': garden.season_start.isoformat() if garden.season_start else None,
        'season_end': garden.season_end.isoformat() if garden.season_end else None,
        'rules': garden.rules,
        'contact_email': garden.contact_email,
        'is_active': garden.is_active,
        'max_checkouts_per_member': garden.max_checkouts_per_member or 3,
        'latitude': garden.latitude,
        'longitude': garden.longitude,
        'weather_alerts_enabled': garden.weather_alerts_enabled or False,
        'grid_rows': garden.grid_rows or 4,
        'grid_cols': garden.grid_cols or 5,
        'organizer_id': garden.organizer_id,
        'organizer_name': format_display_name(garden.organizer.display_name or garden.organizer.username),
        'created_at': garden.created_at.isoformat() if garden.created_at else None,
    }
    if include_stats:
        d['available_plots'] = garden.plots.filter_by(status='available').count()
        d['assigned_plots'] = garden.plots.filter_by(status='assigned').count()
        d['member_count'] = garden.plots.filter_by(status='assigned').count()
        d['waitlist_count'] = GardenWaitlist.query.filter_by(
            garden_id=garden.id, status='waiting'
        ).count()
        d['upcoming_events'] = garden.events.filter(
            GardenEvent.event_date >= datetime.now(timezone.utc)
        ).count()
        total_harvest = db.session.query(
            db.func.coalesce(db.func.sum(HarvestLog.quantity_lbs), 0)
        ).filter_by(garden_id=garden.id).scalar()
        d['total_harvest_lbs'] = float(total_harvest)
    else:
        d['available_plots'] = garden.plots.filter_by(status='available').count()
    return d


def plot_to_dict(plot):
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
        'reserved_by_id': plot.reserved_by_id,
        'reserved_at': plot.reserved_at.isoformat() if plot.reserved_at else None,
        'grid_row': plot.grid_row,
        'grid_col': plot.grid_col,
        'grid_width': plot.grid_width or 1,
        'grid_height': plot.grid_height or 1,
        'rounded': bool(plot.rounded),
        'soil_type': plot.soil_type,
        'sun_exposure': plot.sun_exposure,
        'custom_name': plot.custom_name,
    }
    if plot.assigned_to:
        d['assigned_to_name'] = format_display_name(plot.assigned_to.display_name or plot.assigned_to.username)
    else:
        d['assigned_to_name'] = None
    if plot.reserved_by:
        d['reserved_by_name'] = format_display_name(plot.reserved_by.display_name or plot.reserved_by.username)
    else:
        d['reserved_by_name'] = None
    return d


def feature_to_dict(f):
    return {
        'id': f.id,
        'feature_type': f.feature_type,
        'label': f.label,
        'grid_row': f.grid_row,
        'grid_col': f.grid_col,
        'grid_width': f.grid_width or 1,
        'grid_height': f.grid_height or 1,
        'color': f.color,
        'rounded': bool(f.rounded),
    }


@gardens_api.route('/<garden_id>/layout-features', methods=['GET'])
def list_layout_features(garden_id):
    """Public: non-plot map features (sheds, paths, landscaping, public areas,
    water, compost) so the garden map reflects the real space for everyone."""
    garden = db.get_or_404(CommunityGarden, garden_id)
    feats = GardenLayoutFeature.query.filter_by(garden_id=garden.id).all()
    return jsonify([feature_to_dict(f) for f in feats])


def resource_to_dict(res):
    now = datetime.now(timezone.utc)
    # SQLite returns naive datetimes; normalize to UTC-aware so the comparison
    # below never raises "can't compare offset-naive and offset-aware datetimes".
    due = res.due_date
    if due is not None and due.tzinfo is None:
        due = due.replace(tzinfo=timezone.utc)
    is_overdue = bool(due and res.checked_out_to_id and due < now)
    out_of_service = bool(getattr(res, 'out_of_service', False))
    if out_of_service:
        status = 'out_of_service'
    elif is_overdue:
        status = 'overdue'
    elif res.checked_out_to_id:
        status = 'checked_out'
    else:
        status = 'available'
    d = {
        'id': res.id,
        'garden_id': res.garden_id,
        'name': res.name,
        'resource_type': res.resource_type,
        'description': res.description,
        'quantity': res.quantity,
        'condition': res.condition,
        'checked_out_to_id': res.checked_out_to_id,
        'checked_out_at': res.checked_out_at.isoformat() if res.checked_out_at else None,
        'checkout_duration_days': res.checkout_duration_days or 3,
        'due_date': res.due_date.isoformat() if res.due_date else None,
        'is_overdue': is_overdue,
        'out_of_service': out_of_service,
        'service_note': getattr(res, 'service_note', None),
        'status': status,
    }
    if res.checked_out_to:
        d['checked_out_to_name'] = format_display_name(res.checked_out_to.display_name or res.checked_out_to.username)
    else:
        d['checked_out_to_name'] = None
    return d


def event_to_dict(event):
    d = {
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
        'created_by_name': format_display_name(event.created_by.display_name or event.created_by.username),
        'created_at': event.created_at.isoformat() if event.created_at else None,
        'rsvp_going': event.rsvps.filter_by(status='going').count(),
        'rsvp_maybe': event.rsvps.filter_by(status='maybe').count(),
    }
    if get_current_user().is_authenticated:
        user_rsvp = event.rsvps.filter_by(user_id=get_current_user().id).first()
        d['user_rsvp'] = user_rsvp.status if user_rsvp else None
    else:
        d['user_rsvp'] = None
    return d


def harvest_to_dict(harvest):
    return {
        'id': harvest.id,
        'garden_id': harvest.garden_id,
        'user_id': harvest.user_id,
        'user_name': format_display_name(harvest.user.display_name or harvest.user.username),
        'category': harvest.category,
        'variety': harvest.variety,
        'quantity_lbs': harvest.quantity_lbs,
        'harvest_date': harvest.harvest_date.isoformat() if harvest.harvest_date else None,
        'destination': harvest.destination,
        'notes': harvest.notes,
        'created_at': harvest.created_at.isoformat() if harvest.created_at else None,
    }


def waitlist_to_dict(entry):
    return {
        'id': entry.id,
        'garden_id': entry.garden_id,
        'user_id': entry.user_id,
        'user_name': format_display_name(entry.user.display_name or entry.user.username),
        'requested_at': entry.requested_at.isoformat() if entry.requested_at else None,
        'plot_size_pref': entry.plot_size_pref,
        'notes': entry.notes,
        'status': entry.status,
        'position': entry.position or 0,
    }


# ---- Garden CRUD ----

@gardens_api.route('', methods=['GET'])
def browse_gardens():
    page = request.args.get('page', 1, type=int)
    per_page = 12
    search = request.args.get('search', '').strip()
    model_filter = request.args.get('operating_model', '')

    q = CommunityGarden.query.filter_by(is_active=True)

    if search:
        kw = f'%{search}%'
        q = q.filter(
            (CommunityGarden.name.ilike(kw)) |
            (CommunityGarden.description.ilike(kw)) |
            (CommunityGarden.city.ilike(kw))
        )
    if model_filter:
        q = q.filter_by(operating_model=model_filter)

    pagination = (q.options(joinedload(CommunityGarden.organizer))
                  .order_by(CommunityGarden.created_at.desc())
                  .paginate(page=page, per_page=per_page, error_out=False))
    return jsonify({
        'gardens': [garden_to_dict(g) for g in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'page': pagination.page,
        'has_next': pagination.has_next,
        'has_prev': pagination.has_prev,
    })


@gardens_api.route('/<garden_id>', methods=['GET'])
def garden_detail(garden_id):
    # garden_id has already been resolved to an integer PK by the blueprint's
    # url_value_preprocessor (accepts the opaque grd_… public_id or a PK).
    garden = db.get_or_404(CommunityGarden, garden_id)
    data = garden_to_dict(garden, include_stats=True)

    # Upcoming events
    upcoming = garden.events.filter(
        GardenEvent.event_date >= datetime.now(timezone.utc)
    ).order_by(GardenEvent.event_date).limit(5).all()
    data['upcoming_events_list'] = [event_to_dict(e) for e in upcoming]

    # Check user involvement
    data['user_is_organizer'] = False
    data['user_has_plot'] = False
    data['user_on_waitlist'] = False
    data['user_has_reservation'] = False
    data['reserved_plots'] = garden.plots.filter_by(status='reserved').count()
    if get_current_user().is_authenticated:
        data['user_is_organizer'] = garden.organizer_id == get_current_user().id
        data['user_has_plot'] = garden.plots.filter_by(
            assigned_to_id=get_current_user().id, status='assigned'
        ).count() > 0
        data['user_on_waitlist'] = GardenWaitlist.query.filter_by(
            garden_id=garden_id, user_id=get_current_user().id, status='waiting'
        ).count() > 0
        data['user_has_reservation'] = garden.plots.filter_by(
            reserved_by_id=get_current_user().id, status='reserved'
        ).count() > 0

    return jsonify(data)


@gardens_api.route('', methods=['POST'])
@token_or_session
def create_garden():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Garden name is required'}), 400

    slug = slugify(name)
    # Ensure unique slug
    base_slug = slug
    counter = 1
    while CommunityGarden.query.filter_by(slug=slug).first():
        slug = f'{base_slug}-{counter}'
        counter += 1

    garden = CommunityGarden(
        name=name,
        slug=slug,
        description=data.get('description', ''),
        address=data.get('address', ''),
        city=data.get('city', 'Omaha'),
        state=data.get('state', 'NE'),
        zip_code=data.get('zip_code', ''),
        photo_url=data.get('photo_url', ''),
        total_plots=int(data.get('total_plots', 0)),
        plot_fee_annual=float(data.get('plot_fee_annual', 0.0)),
        operating_model=data.get('operating_model', 'allotment'),
        rules=data.get('rules', ''),
        contact_email=data.get('contact_email', ''),
        organizer_id=get_current_user().id,
    )

    season_start = data.get('season_start')
    season_end = data.get('season_end')
    if season_start:
        garden.season_start = datetime.strptime(season_start, '%Y-%m-%d').date()
    if season_end:
        garden.season_end = datetime.strptime(season_end, '%Y-%m-%d').date()

    db.session.add(garden)
    db.session.flush()

    # Auto-create plots if initial_plots provided
    initial_plots = data.get('initial_plots', [])
    for p in initial_plots:
        plot = GardenPlot(
            garden_id=garden.id,
            plot_number=p.get('plot_number', ''),
            size=p.get('size', ''),
            location_notes=p.get('location_notes', ''),
        )
        db.session.add(plot)

    # Also support bulk plot creation by count (clamped — guards against a
    # single request creating millions of rows / bad input).
    try:
        bulk_count = int(data.get('bulk_plot_count', 0) or 0)
    except (TypeError, ValueError):
        bulk_count = 0
    bulk_count = max(0, min(bulk_count, MAX_BULK_PLOTS))
    bulk_size = data.get('bulk_plot_size', '4x8 ft')
    for i in range(bulk_count):
        plot = GardenPlot(
            garden_id=garden.id,
            plot_number=str(i + 1),
            size=bulk_size,
        )
        db.session.add(plot)

    garden.total_plots = len(initial_plots) + bulk_count

    db.session.commit()
    return jsonify(garden_to_dict(garden, include_stats=True)), 201


@gardens_api.route('/<garden_id>', methods=['PUT'])
@token_or_session
def update_garden(garden_id):
    garden = db.get_or_404(CommunityGarden, garden_id)
    if garden.organizer_id != get_current_user().id:
        return jsonify({'error': 'Not authorized'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    garden.name = data.get('name', garden.name)
    garden.description = data.get('description', garden.description)
    garden.address = data.get('address', garden.address)
    garden.city = data.get('city', garden.city)
    garden.state = data.get('state', garden.state)
    garden.zip_code = data.get('zip_code', garden.zip_code)
    garden.photo_url = data.get('photo_url', garden.photo_url)
    garden.plot_fee_annual = float(data.get('plot_fee_annual', garden.plot_fee_annual))
    garden.operating_model = data.get('operating_model', garden.operating_model)
    garden.rules = data.get('rules', garden.rules)
    garden.contact_email = data.get('contact_email', garden.contact_email)

    season_start = data.get('season_start')
    season_end = data.get('season_end')
    if season_start:
        garden.season_start = datetime.strptime(season_start, '%Y-%m-%d').date()
    if season_end:
        garden.season_end = datetime.strptime(season_end, '%Y-%m-%d').date()

    db.session.commit()
    return jsonify(garden_to_dict(garden, include_stats=True))


# ---- Plot Management ----

@gardens_api.route('/<garden_id>/plots', methods=['GET'])
def list_plots(garden_id):
    garden = db.get_or_404(CommunityGarden, garden_id)
    plots = garden.plots.order_by(GardenPlot.plot_number).all()
    return jsonify([plot_to_dict(p) for p in plots])


@gardens_api.route('/<garden_id>/plots', methods=['POST'])
@token_or_session
def add_plots(garden_id):
    garden = db.get_or_404(CommunityGarden, garden_id)
    if garden.organizer_id != get_current_user().id:
        return jsonify({'error': 'Not authorized'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    plots_data = data.get('plots', [])
    try:
        bulk_count = int(data.get('bulk_count', 0) or 0)
    except (TypeError, ValueError):
        bulk_count = 0
    bulk_count = max(0, min(bulk_count, MAX_BULK_PLOTS))
    bulk_size = data.get('bulk_size', '4x8 ft')

    created = []

    # Get current max plot number for auto-numbering
    existing_count = garden.plots.count()

    for p in plots_data:
        plot = GardenPlot(
            garden_id=garden.id,
            plot_number=p.get('plot_number', str(existing_count + len(created) + 1)),
            size=p.get('size', ''),
            location_notes=p.get('location_notes', ''),
        )
        db.session.add(plot)
        created.append(plot)

    for i in range(bulk_count):
        plot = GardenPlot(
            garden_id=garden.id,
            plot_number=str(existing_count + len(created) + 1),
            size=bulk_size,
        )
        db.session.add(plot)
        created.append(plot)

    garden.total_plots = garden.plots.count() + len(created)
    db.session.commit()
    return jsonify([plot_to_dict(p) for p in created]), 201


@gardens_api.route('/<garden_id>/plots/<int:plot_id>/assign', methods=['PUT'])
@token_or_session
def assign_plot(garden_id, plot_id):
    garden = db.get_or_404(CommunityGarden, garden_id)
    if garden.organizer_id != get_current_user().id:
        return jsonify({'error': 'Not authorized'}), 403

    plot = db.get_or_404(GardenPlot, plot_id)
    if plot.garden_id != garden_id:
        return jsonify({'error': 'Plot not in this garden'}), 400

    data = request.get_json()
    if not data or not data.get('user_id'):
        return jsonify({'error': 'user_id required'}), 400

    user = db.get_or_404(User, data['user_id'])
    plot.assigned_to_id = user.id
    plot.status = 'assigned'
    plot.assigned_date = datetime.now(timezone.utc).date()

    # Notify the assigned member: in-app + SMS (per-user opt-in)
    notify(
        user_id=user.id,
        type='plot_assigned',
        title=f'Plot {plot.plot_number} assigned to you',
        body=f'You have been assigned plot {plot.plot_number} in {garden.name}. Happy gardening!',
        link=f'/gardens/{garden.public_id}',
        garden_id=garden_id,
    )
    if user.sms_opt_in and user.phone_number:
        from app.sms_service import send_plot_assigned_sms
        send_plot_assigned_sms(user.phone_number, garden.name, plot.plot_number)

    db.session.commit()
    return jsonify(plot_to_dict(plot))


@gardens_api.route('/<garden_id>/plots/<int:plot_id>/release', methods=['PUT'])
@token_or_session
def release_plot(garden_id, plot_id):
    garden = db.get_or_404(CommunityGarden, garden_id)
    if garden.organizer_id != get_current_user().id:
        return jsonify({'error': 'Not authorized'}), 403

    plot = db.get_or_404(GardenPlot, plot_id)
    if plot.garden_id != garden_id:
        return jsonify({'error': 'Plot not in this garden'}), 400

    plot.assigned_to_id = None
    plot.status = 'available'
    plot.assigned_date = None
    plot.renewal_date = None
    plot.reserved_by_id = None
    plot.reserved_at = None

    db.session.commit()
    return jsonify(plot_to_dict(plot))


# ---- Plot Rename (owner self-service) ----

@gardens_api.route('/<garden_id>/plots/<int:plot_id>/rename', methods=['PUT'])
@token_or_session
def rename_plot(garden_id, plot_id):
    """Allow a plot owner to set a custom name for their plot."""
    user = get_current_user()
    garden = db.get_or_404(CommunityGarden, garden_id)
    plot = db.get_or_404(GardenPlot, plot_id)
    if plot.garden_id != garden_id:
        return jsonify({'error': 'Plot not in this garden'}), 400
    if plot.assigned_to_id != user.id and user.id != garden.organizer_id:
        return jsonify({'error': 'Only the plot owner or garden organizer can rename a plot'}), 403
    data = request.get_json() or {}
    custom_name = data.get('custom_name', '').strip()
    if len(custom_name) > 100:
        return jsonify({'error': 'Name must be 100 characters or less'}), 400
    plot.custom_name = custom_name if custom_name else None
    db.session.commit()
    return jsonify(plot_to_dict(plot))


# ---- Plot Reservation (self-service) ----

@gardens_api.route('/<garden_id>/plots/<int:plot_id>/reserve', methods=['POST'])
@token_or_session
def reserve_plot(garden_id, plot_id):
    """User reserves an available plot (pending organizer confirmation)."""
    garden = db.get_or_404(CommunityGarden, garden_id)
    plot = db.get_or_404(GardenPlot, plot_id)

    if plot.garden_id != garden_id:
        return jsonify({'error': 'Plot not in this garden'}), 400
    if plot.status != 'available':
        return jsonify({'error': 'Plot is not available'}), 400

    # Check if user already has a plot or pending reservation in this garden
    existing_plot = garden.plots.filter_by(
        assigned_to_id=get_current_user().id, status='assigned'
    ).first()
    if existing_plot:
        return jsonify({'error': 'You already have a plot in this garden'}), 400

    existing_reservation = garden.plots.filter_by(
        reserved_by_id=get_current_user().id, status='reserved'
    ).first()
    if existing_reservation:
        return jsonify({'error': 'You already have a pending reservation'}), 400

    # Atomic claim: only flip the row if it's STILL available, so two concurrent
    # requests can't both reserve the same plot (the earlier status check above
    # is just a fast path). synchronize_session='fetch' keeps the loaded `plot`
    # in sync for the response.
    claimed = (db.session.query(GardenPlot)
               .filter(GardenPlot.id == plot_id, GardenPlot.status == 'available')
               .update({GardenPlot.status: 'reserved',
                        GardenPlot.reserved_by_id: get_current_user().id,
                        GardenPlot.reserved_at: datetime.now(timezone.utc)},
                       synchronize_session='fetch'))
    if not claimed:
        db.session.rollback()
        return jsonify({'error': 'Plot is no longer available'}), 409

    # Remove user from waitlist if they were on it
    wl_entry = GardenWaitlist.query.filter_by(
        garden_id=garden_id, user_id=get_current_user().id, status='waiting'
    ).first()
    if wl_entry:
        wl_entry.status = 'offered'

    # Notify the garden organizer about the new reservation
    requester_name = get_current_user().display_name or get_current_user().username
    notify(
        user_id=garden.organizer_id,
        type='plot_reserved',
        title=f'Plot {plot.plot_number} reservation request',
        body=f'{requester_name} has requested plot {plot.plot_number} in {garden.name}. Please review and confirm or decline.',
        link=f'/gardens/{garden.public_id}/admin?tab=plots',
        garden_id=garden_id,
    )

    db.session.commit()
    return jsonify(plot_to_dict(plot))


# ---- Waitlist ----

@gardens_api.route('/<garden_id>/waitlist', methods=['POST'])
@token_or_session
def join_waitlist(garden_id):
    garden = db.get_or_404(CommunityGarden, garden_id)

    # Check if already on waitlist
    existing = GardenWaitlist.query.filter_by(
        garden_id=garden_id, user_id=get_current_user().id, status='waiting'
    ).first()
    if existing:
        return jsonify({'error': 'Already on waitlist'}), 400

    data = request.get_json() or {}
    entry = GardenWaitlist(
        garden_id=garden_id,
        user_id=get_current_user().id,
        plot_size_pref=data.get('plot_size_pref', ''),
        notes=data.get('notes', ''),
    )
    db.session.add(entry)
    db.session.commit()

    # Notify the user via email that they've been added to the waitlist
    try:
        position = GardenWaitlist.query.filter_by(
            garden_id=garden_id, status='waiting').count()
        from app.email_service import send_plot_waitlisted_email
        send_plot_waitlisted_email(
            garden.name, get_current_user().email,
            get_current_user().display_name or get_current_user().username,
            position, garden_id=garden_id)
    except Exception:
        pass  # logged inside send_email

    return jsonify(waitlist_to_dict(entry)), 201


@gardens_api.route('/<garden_id>/waitlist', methods=['GET'])
@token_or_session
def view_waitlist(garden_id):
    garden = db.get_or_404(CommunityGarden, garden_id)
    if garden.organizer_id != get_current_user().id and not get_current_user().is_admin:
        return jsonify({'error': 'Not authorized'}), 403

    entries = GardenWaitlist.query.filter_by(
        garden_id=garden_id
    ).order_by(GardenWaitlist.requested_at).all()
    return jsonify([waitlist_to_dict(e) for e in entries])


# ---- Resources ----

@gardens_api.route('/<garden_id>/resources', methods=['GET'])
def list_resources(garden_id):
    try:
        garden = db.get_or_404(CommunityGarden, garden_id)
        resources = SharedResource.query.filter_by(garden_id=garden_id).order_by(SharedResource.name).all()
        return jsonify([resource_to_dict(r) for r in resources])
    except Exception as e:
        log.error('Resources error for garden_id=%d: %s', garden_id, e)
        return jsonify({'error': 'Failed to load resources'}), 500


@gardens_api.route('/<garden_id>/resources', methods=['POST'])
@token_or_session
def add_resource(garden_id):
    garden = db.get_or_404(CommunityGarden, garden_id)
    if garden.organizer_id != get_current_user().id and not get_current_user().is_admin:
        return jsonify({'error': 'Only the garden organizer can add resources'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Resource name is required'}), 400

    try:
        quantity = int(data.get('quantity') or 1)
    except (TypeError, ValueError):
        quantity = 1
    if quantity < 1:
        quantity = 1

    res = SharedResource(
        garden_id=garden_id,
        name=name,
        resource_type=data.get('resource_type') or 'tool',
        description=data.get('description') or '',
        quantity=quantity,
        condition=data.get('condition') or 'good',
    )
    db.session.add(res)
    db.session.commit()
    return jsonify(resource_to_dict(res)), 201


@gardens_api.route('/<garden_id>/resources/<int:res_id>/checkout', methods=['POST'])
@token_or_session
def checkout_resource(garden_id, res_id):
    garden = db.get_or_404(CommunityGarden, garden_id)
    res = db.get_or_404(SharedResource, res_id)
    if res.garden_id != garden_id:
        return jsonify({'error': 'Resource not in this garden'}), 400
    if res.out_of_service:
        return jsonify({'error': 'This item is out of service and cannot be checked out'}), 400
    if res.checked_out_to_id:
        return jsonify({'error': 'Resource already checked out'}), 400

    # Enforce max checkouts per member
    max_co = garden.max_checkouts_per_member or 3
    current_checkouts = SharedResource.query.filter_by(
        garden_id=garden_id, checked_out_to_id=get_current_user().id
    ).count()
    if current_checkouts >= max_co:
        return jsonify({'error': f'You can only check out {max_co} items at a time'}), 400

    data = request.get_json() or {}
    duration = data.get('duration_days', 3)
    if duration not in [1, 3, 7]:
        duration = 3

    now = datetime.now(timezone.utc)
    res.checked_out_to_id = get_current_user().id
    res.checked_out_at = now
    res.due_date = now + timedelta(days=duration)

    # Create checkout log
    log = ResourceCheckoutLog(
        resource_id=res.id,
        user_id=get_current_user().id,
        garden_id=garden_id,
        checked_out_at=now,
        due_date=res.due_date,
        duration_days=duration,
        condition_at_checkout=res.condition,
    )
    db.session.add(log)
    db.session.commit()
    return jsonify(resource_to_dict(res))


@gardens_api.route('/<garden_id>/resources/<int:res_id>/return', methods=['POST'])
@token_or_session
def return_resource(garden_id, res_id):
    res = db.get_or_404(SharedResource, res_id)
    if res.garden_id != garden_id:
        return jsonify({'error': 'Resource not in this garden'}), 400
    if res.checked_out_to_id != get_current_user().id:
        # Allow organizer to return for anyone
        garden = db.session.get(CommunityGarden, garden_id)
        if garden.organizer_id != get_current_user().id:
            return jsonify({'error': 'Not authorized'}), 403

    data = request.get_json() or {}
    condition_at_return = data.get('condition_at_return')

    # Update the latest checkout log
    log = ResourceCheckoutLog.query.filter_by(
        resource_id=res.id, user_id=res.checked_out_to_id, returned_at=None
    ).order_by(ResourceCheckoutLog.checked_out_at.desc()).first()
    if log:
        log.returned_at = datetime.now(timezone.utc)
        if condition_at_return:
            log.condition_at_return = condition_at_return

    # Update condition if provided
    if condition_at_return:
        res.condition = condition_at_return

    res.checked_out_to_id = None
    res.checked_out_at = None
    res.due_date = None
    db.session.commit()
    return jsonify(resource_to_dict(res))


@gardens_api.route('/<garden_id>/resources/<int:res_id>/qr', methods=['GET'])
def resource_qr_code(garden_id, res_id):
    """Return a QR code PNG image for a resource."""
    from flask import Response, current_app
    from app.qr_service import generate_resource_qr

    garden = db.get_or_404(CommunityGarden, garden_id)
    db.get_or_404(SharedResource, res_id)

    base_url = current_app.config.get('RENDER_EXTERNAL_URL', request.host_url.rstrip('/'))
    # Encode the opaque public_id in the scannable URL (not the sequential PK).
    png_bytes = generate_resource_qr(garden.public_id, res_id, base_url)

    if png_bytes is None:
        return jsonify({'error': 'QR code generation not available (install qrcode[pil])'}), 503

    return Response(png_bytes, mimetype='image/png', headers={
        'Content-Disposition': f'inline; filename=resource-{res_id}-qr.png'
    })


@gardens_api.route('/<garden_id>/resources/overdue', methods=['GET'])
@token_or_session
def overdue_resources(garden_id):
    """List overdue resources for this garden (organizer/admin only)."""
    garden = db.get_or_404(CommunityGarden, garden_id)
    if garden.organizer_id != get_current_user().id and not get_current_user().is_admin:
        return jsonify({'error': 'Only the garden organizer can view overdue resources'}), 403
    now = datetime.now(timezone.utc)

    overdue = SharedResource.query.filter(
        SharedResource.garden_id == garden_id,
        SharedResource.checked_out_to_id.isnot(None),
        SharedResource.due_date.isnot(None),
        SharedResource.due_date < now,
    ).all()

    return jsonify([resource_to_dict(r) for r in overdue])


@gardens_api.route('/resources/lookup', methods=['GET'])
@token_or_session
def resource_lookup():
    """Look up a resource by QR token or URL path for in-app scanner."""
    token = request.args.get('token', '')
    if not token:
        return jsonify({'error': 'token parameter is required'}), 400

    # Try to find by qr_code_token field
    resource = SharedResource.query.filter_by(qr_code_token=token).first()

    # Also try parsing as a URL path: /gardens/{id}/resources/{resId}/scan
    if not resource:
        match = re.search(r'/gardens/(\d+)/resources/(\d+)/scan', token)
        if match:
            resource = db.session.get(SharedResource, int(match.group(2)))

    if not resource:
        return jsonify({'error': 'Resource not found'}), 404

    garden = db.session.get(CommunityGarden, resource.garden_id)
    return jsonify({
        'garden_id': resource.garden_id,
        'garden_name': garden.name if garden else '',
        'resource_id': resource.id,
        'resource': resource_to_dict(resource),
    })


@gardens_api.route('/<garden_id>/resources/<int:res_id>/history', methods=['GET'])
def resource_history(garden_id, res_id):
    """Get checkout history for a resource."""
    resource = db.get_or_404(SharedResource, res_id)
    if resource.garden_id != garden_id:
        return jsonify({'error': 'Resource not found in this garden'}), 404

    logs = ResourceCheckoutLog.query.filter_by(resource_id=res_id).order_by(
        ResourceCheckoutLog.checked_out_at.desc()
    ).limit(10).all()

    return jsonify([{
        'user_name': log.user.display_name or log.user.username if log.user else 'Unknown',
        'checked_out_at': log.checked_out_at.isoformat() if log.checked_out_at else None,
        'returned_at': log.returned_at.isoformat() if log.returned_at else None,
        'duration_days': log.duration_days,
        'condition_at_checkout': log.condition_at_checkout,
        'condition_at_return': log.condition_at_return,
    } for log in logs])


# ---- Events ----

@gardens_api.route('/<garden_id>/events', methods=['GET'])
def list_events(garden_id):
    garden = db.get_or_404(CommunityGarden, garden_id)
    show = request.args.get('show', 'all')  # upcoming, past, all

    q = garden.events
    now = datetime.now(timezone.utc)
    if show == 'upcoming':
        q = q.filter(GardenEvent.event_date >= now)
        q = q.order_by(GardenEvent.event_date)
    elif show == 'past':
        q = q.filter(GardenEvent.event_date < now)
        q = q.order_by(GardenEvent.event_date.desc())
    else:
        q = q.order_by(GardenEvent.event_date.desc())

    events = q.all()
    return jsonify([event_to_dict(e) for e in events])


@gardens_api.route('/<garden_id>/events', methods=['POST'])
@token_or_session
def create_event(garden_id):
    garden = db.get_or_404(CommunityGarden, garden_id)
    if garden.organizer_id != get_current_user().id and not get_current_user().is_admin:
        return jsonify({'error': 'Only the garden organizer can create events'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    title = data.get('title', '').strip()
    event_date_str = data.get('event_date', '')
    if not title or not event_date_str:
        return jsonify({'error': 'Title and event_date are required'}), 400

    recurring = data.get('recurring', 'none') or 'none'
    if recurring not in ('none', 'weekly', 'biweekly', 'monthly'):
        return jsonify({'error': 'recurring must be one of none, weekly, biweekly, monthly'}), 400

    start_dt = datetime.fromisoformat(event_date_str)
    event = GardenEvent(
        garden_id=garden_id,
        title=title,
        description=data.get('description', ''),
        event_type=data.get('event_type', 'workday'),
        event_date=start_dt,
        duration_hours=float(data.get('duration_hours', 2.0)),
        max_volunteers=data.get('max_volunteers'),
        recurring=recurring,
        created_by_id=get_current_user().id,
    )
    db.session.add(event)

    # Expand a recurring volunteer opportunity into a series: the original plus
    # up to 8 future occurrences (mirrors volunteer-shift recurrence).
    if recurring != 'none':
        from datetime import timedelta
        step_days = {'weekly': 7, 'biweekly': 14, 'monthly': 30}[recurring]
        for i in range(1, 9):
            db.session.add(GardenEvent(
                garden_id=garden_id,
                title=title,
                description=data.get('description', ''),
                event_type=data.get('event_type', 'workday'),
                event_date=start_dt + timedelta(days=step_days * i),
                duration_hours=float(data.get('duration_hours', 2.0)),
                max_volunteers=data.get('max_volunteers'),
                recurring=recurring,
                created_by_id=get_current_user().id,
            ))

    db.session.commit()
    return jsonify(event_to_dict(event)), 201


@gardens_api.route('/<garden_id>/events/<int:event_id>/rsvp', methods=['POST'])
@token_or_session
def rsvp_event(garden_id, event_id):
    event = db.get_or_404(GardenEvent, event_id)
    if event.garden_id != garden_id:
        return jsonify({'error': 'Event not in this garden'}), 400

    data = request.get_json() or {}
    status = data.get('status', 'going')

    existing = EventRSVP.query.filter_by(
        event_id=event_id, user_id=get_current_user().id
    ).first()

    if existing:
        existing.status = status
    else:
        # Check max volunteers. Lock the event row first so concurrent RSVPs
        # serialise on the capacity check (otherwise two requests could both
        # pass it and overfill the event).
        if event.max_volunteers and status == 'going':
            db.session.query(GardenEvent).filter_by(
                id=event_id).with_for_update().first()
            going_count = event.rsvps.filter_by(status='going').count()
            if going_count >= event.max_volunteers:
                return jsonify({'error': 'Event is full'}), 400
        rsvp = EventRSVP(
            event_id=event_id,
            user_id=get_current_user().id,
            status=status,
        )
        db.session.add(rsvp)

    db.session.commit()
    return jsonify(event_to_dict(event))


@gardens_api.route('/<garden_id>/events/<int:event_id>/rsvp', methods=['DELETE'])
@token_or_session
def cancel_rsvp(garden_id, event_id):
    event = db.get_or_404(GardenEvent, event_id)
    if event.garden_id != garden_id:
        return jsonify({'error': 'Event not in this garden'}), 400

    existing = EventRSVP.query.filter_by(
        event_id=event_id, user_id=get_current_user().id
    ).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()

    return jsonify(event_to_dict(event))


# ---- Harvest ----

@gardens_api.route('/<garden_id>/harvests', methods=['GET'])
def list_harvests(garden_id):
    garden = db.get_or_404(CommunityGarden, garden_id)

    category = request.args.get('category', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    q = garden.harvests
    if category:
        q = q.filter_by(category=category)
    if date_from:
        q = q.filter(HarvestLog.harvest_date >= datetime.strptime(date_from, '%Y-%m-%d').date())
    if date_to:
        q = q.filter(HarvestLog.harvest_date <= datetime.strptime(date_to, '%Y-%m-%d').date())

    harvests = q.order_by(HarvestLog.harvest_date.desc()).all()
    return jsonify([harvest_to_dict(h) for h in harvests])


@gardens_api.route('/<garden_id>/harvests', methods=['POST'])
@token_or_session
def log_harvest(garden_id):
    garden = db.get_or_404(CommunityGarden, garden_id)

    # Verify the user is a member of this garden (organizer, plot holder, or admin)
    from app.models import GardenPlot
    is_organizer = garden.organizer_id == get_current_user().id
    has_plot = GardenPlot.query.filter_by(
        garden_id=garden_id, assigned_to_id=get_current_user().id
    ).first() is not None
    if not is_organizer and not has_plot and not get_current_user().is_admin:
        return jsonify({'error': 'Only garden members can log harvests'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    harvest_date_str = data.get('harvest_date', '')
    if not harvest_date_str:
        return jsonify({'error': 'harvest_date is required'}), 400

    harvest = HarvestLog(
        garden_id=garden_id,
        user_id=get_current_user().id,
        category=data.get('category', ''),
        variety=data.get('variety', ''),
        quantity_lbs=float(data.get('quantity_lbs', 0)),
        harvest_date=datetime.strptime(harvest_date_str, '%Y-%m-%d').date(),
        destination=data.get('destination', 'personal'),
        notes=data.get('notes', ''),
    )
    db.session.add(harvest)
    db.session.commit()
    return jsonify(harvest_to_dict(harvest)), 201


# ---- Impact Dashboard ----

@gardens_api.route('/<garden_id>/impact', methods=['GET'])
def impact_stats(garden_id):
    garden = db.get_or_404(CommunityGarden, garden_id)

    # Total harvest
    total_lbs = db.session.query(
        db.func.coalesce(db.func.sum(HarvestLog.quantity_lbs), 0)
    ).filter_by(garden_id=garden_id).scalar()

    # Food bank donations
    food_bank_lbs = db.session.query(
        db.func.coalesce(db.func.sum(HarvestLog.quantity_lbs), 0)
    ).filter_by(garden_id=garden_id, destination='food_bank').scalar()

    # Shared produce
    shared_lbs = db.session.query(
        db.func.coalesce(db.func.sum(HarvestLog.quantity_lbs), 0)
    ).filter_by(garden_id=garden_id, destination='shared').scalar()

    # Harvest by category
    category_breakdown = db.session.query(
        HarvestLog.category,
        db.func.sum(HarvestLog.quantity_lbs)
    ).filter_by(garden_id=garden_id).group_by(HarvestLog.category).all()

    # Monthly harvest trend. strftime() is SQLite-only and raises on Postgres
    # (prod), so pick a portable month expression per dialect.
    if db.engine.dialect.name == 'postgresql':
        month_expr = db.func.to_char(HarvestLog.harvest_date, 'YYYY-MM')
    else:
        month_expr = db.func.strftime('%Y-%m', HarvestLog.harvest_date)
    monthly_trend = db.session.query(
        month_expr,
        db.func.sum(HarvestLog.quantity_lbs)
    ).filter_by(garden_id=garden_id).group_by(month_expr).order_by(month_expr).all()

    # Active gardeners (plot holders)
    active_gardeners = garden.plots.filter_by(status='assigned').count()

    # Total events held
    total_events = garden.events.count()

    # Volunteer hours estimate (sum of event_duration * going_rsvps per event)
    vol_hours = 0.0
    past_events = garden.events.filter(
        GardenEvent.event_date < datetime.now(timezone.utc)
    ).all()
    for ev in past_events:
        going = ev.rsvps.filter_by(status='going').count()
        vol_hours += ev.duration_hours * going

    # CO2 saved estimate (2 lbs CO2 per lb food rescued/shared)
    rescued_lbs = float(food_bank_lbs) + float(shared_lbs)
    co2_saved = rescued_lbs * 2.0

    # Destination breakdown
    dest_breakdown = db.session.query(
        HarvestLog.destination,
        db.func.sum(HarvestLog.quantity_lbs)
    ).filter_by(garden_id=garden_id).group_by(HarvestLog.destination).all()

    return jsonify({
        'total_harvest_lbs': float(total_lbs),
        'food_bank_lbs': float(food_bank_lbs),
        'shared_lbs': float(shared_lbs),
        'co2_saved_lbs': co2_saved,
        'active_gardeners': active_gardeners,
        'total_events': total_events,
        'volunteer_hours': round(vol_hours, 1),
        'category_breakdown': [
            {'category': cat or 'Uncategorized', 'lbs': float(lbs or 0)}
            for cat, lbs in category_breakdown
        ],
        'monthly_trend': [
            {'month': month, 'lbs': float(lbs or 0)}
            for month, lbs in monthly_trend
        ],
        'destination_breakdown': [
            {'destination': dest or 'personal', 'lbs': float(lbs or 0)}
            for dest, lbs in dest_breakdown
        ],
    })


# ---- Members ----

@gardens_api.route('/<garden_id>/members', methods=['GET'])
def list_members(garden_id):
    garden = db.get_or_404(CommunityGarden, garden_id)

    # Plot holders
    assigned_plots = garden.plots.filter_by(status='assigned').all()
    members = []
    seen_users = set()
    for plot in assigned_plots:
        if plot.assigned_to_id and plot.assigned_to_id not in seen_users:
            seen_users.add(plot.assigned_to_id)
            members.append({
                'user_id': plot.assigned_to_id,
                'name': format_display_name(plot.assigned_to.display_name or plot.assigned_to.username),
                'role': 'plot_holder',
                'plot_number': plot.plot_number,
                'since': plot.assigned_date.isoformat() if plot.assigned_date else None,
            })

    # Organizer
    if garden.organizer_id not in seen_users:
        members.insert(0, {
            'user_id': garden.organizer_id,
            'name': format_display_name(garden.organizer.display_name or garden.organizer.username),
            'role': 'organizer',
            'plot_number': None,
            'since': garden.created_at.isoformat() if garden.created_at else None,
        })

    return jsonify(members)


# ---- Announcements (public) ----

@gardens_api.route('/<garden_id>/announcements', methods=['GET'])
def list_announcements(garden_id):
    """Public endpoint to view garden announcements."""
    garden = db.get_or_404(CommunityGarden, garden_id)
    announcements = GardenAnnouncement.query.filter_by(
        garden_id=garden_id
    ).order_by(
        GardenAnnouncement.pinned.desc(),
        GardenAnnouncement.created_at.desc()
    ).limit(10).all()
    return jsonify([{
        'id': a.id,
        'title': a.title,
        'body': a.body,
        'priority': a.priority,
        'pinned': a.pinned,
        'author_name': format_display_name(a.author.display_name or a.author.username) if a.author else 'Unknown',
        'created_at': a.created_at.isoformat() if a.created_at else None,
    } for a in announcements])


# ---- My Gardens ----

@gardens_api.route('/my-gardens', methods=['GET'])
@token_or_session
def my_gardens():
    # Gardens I organize
    organized = CommunityGarden.query.filter_by(
        organizer_id=get_current_user().id, is_active=True
    ).all()

    # Gardens where I have a plot
    my_plots = GardenPlot.query.filter_by(
        assigned_to_id=get_current_user().id, status='assigned'
    ).all()
    plot_garden_ids = list(set(p.garden_id for p in my_plots))
    plot_gardens = CommunityGarden.query.filter(
        CommunityGarden.id.in_(plot_garden_ids)
    ).all() if plot_garden_ids else []

    # Gardens I'm on waitlist for
    waitlist_entries = GardenWaitlist.query.filter_by(
        user_id=get_current_user().id, status='waiting'
    ).all()
    waitlist_garden_ids = [w.garden_id for w in waitlist_entries]
    waitlist_gardens = CommunityGarden.query.filter(
        CommunityGarden.id.in_(waitlist_garden_ids)
    ).all() if waitlist_garden_ids else []

    return jsonify({
        'organized': [garden_to_dict(g) for g in organized],
        'plot_holder': [garden_to_dict(g) for g in plot_gardens],
        'waitlisted': [garden_to_dict(g) for g in waitlist_gardens],
    })


# ===================================================================
#  VOLUNTEER SHIFTS — Public endpoints
# ===================================================================

def shift_to_dict(shift):
    signup_count = shift.signups.count()
    d = {
        'id': shift.id,
        'garden_id': shift.garden_id,
        'title': shift.title,
        'description': shift.description,
        'shift_date': shift.shift_date.isoformat() if shift.shift_date else None,
        'start_time': shift.start_time.strftime('%H:%M') if shift.start_time else None,
        'end_time': shift.end_time.strftime('%H:%M') if shift.end_time else None,
        'max_volunteers': shift.max_volunteers,
        'recurring': shift.recurring or 'none',
        'signup_count': signup_count,
        'spots_left': (shift.max_volunteers - signup_count) if shift.max_volunteers else None,
        'created_by_name': format_display_name(shift.created_by.display_name or shift.created_by.username),
        'created_at': shift.created_at.isoformat() if shift.created_at else None,
    }
    if get_current_user().is_authenticated:
        my_signup = shift.signups.filter_by(user_id=get_current_user().id).first()
        d['user_signed_up'] = my_signup is not None
        d['user_signup_status'] = my_signup.status if my_signup else None
    else:
        d['user_signed_up'] = False
        d['user_signup_status'] = None
    return d


@gardens_api.route('/<garden_id>/shifts', methods=['GET'])
def list_shifts(garden_id):
    """List upcoming volunteer shifts for a garden."""
    garden = db.get_or_404(CommunityGarden, garden_id)
    show = request.args.get('show', 'upcoming')
    q = VolunteerShift.query.filter_by(garden_id=garden_id)
    if show == 'upcoming':
        q = q.filter(VolunteerShift.shift_date >= date.today())
    shifts = q.order_by(VolunteerShift.shift_date, VolunteerShift.start_time).all()
    return jsonify([shift_to_dict(s) for s in shifts])


@gardens_api.route('/<garden_id>/shifts/<int:shift_id>/signup', methods=['POST'])
@token_or_session
def signup_for_shift(garden_id, shift_id):
    """Sign up for a volunteer shift."""
    shift = db.get_or_404(VolunteerShift, shift_id)
    if shift.garden_id != garden_id:
        return jsonify({'error': 'Shift not in this garden'}), 400

    existing = ShiftSignup.query.filter_by(shift_id=shift_id, user_id=get_current_user().id).first()
    if existing:
        return jsonify({'error': 'Already signed up'}), 400

    if shift.max_volunteers and shift.signups.count() >= shift.max_volunteers:
        return jsonify({'error': 'Shift is full'}), 400

    signup = ShiftSignup(shift_id=shift_id, user_id=get_current_user().id)
    db.session.add(signup)

    # Notify the shift creator (organizer)
    volunteer_name = get_current_user().display_name or get_current_user().username
    notify(
        user_id=shift.created_by_id,
        type='shift_signup',
        title=f'{volunteer_name} signed up for {shift.title}',
        body=f'{volunteer_name} signed up for the shift on {shift.shift_date}.',
        link=f'/gardens/{shift.garden.public_id}/admin?tab=volunteers',
        garden_id=garden_id,
    )

    db.session.commit()

    # Confirmation email to the volunteer
    try:
        garden = db.session.get(CommunityGarden, garden_id)
        from app.email_service import send_shift_signup_email
        send_shift_signup_email(
            garden.name if garden else 'your garden', get_current_user().email,
            volunteer_name, shift.title,
            shift.shift_date.isoformat() if shift.shift_date else '',
            garden_id=garden_id)
    except Exception:
        pass  # logged inside send_email

    return jsonify({'message': 'Signed up successfully'}), 201


@gardens_api.route('/<garden_id>/shifts/<int:shift_id>/signup', methods=['DELETE'])
@token_or_session
def cancel_shift_signup(garden_id, shift_id):
    """Cancel signup for a volunteer shift."""
    signup = ShiftSignup.query.filter_by(shift_id=shift_id, user_id=get_current_user().id).first()
    if not signup:
        return jsonify({'error': 'Not signed up for this shift'}), 404
    db.session.delete(signup)
    db.session.commit()
    return jsonify({'message': 'Signup cancelled'})


@gardens_api.route('/<garden_id>/volunteer-hours', methods=['GET'])
@token_or_session
def my_volunteer_hours(garden_id):
    """Get current user's volunteer hour summary for a garden."""
    signups = ShiftSignup.query.join(VolunteerShift).filter(
        VolunteerShift.garden_id == garden_id,
        ShiftSignup.user_id == get_current_user().id
    ).all()
    total_hours = sum(s.hours_logged or 0 for s in signups)
    attended = sum(1 for s in signups if s.status == 'attended')
    no_shows = sum(1 for s in signups if s.status == 'no_show')
    return jsonify({
        'total_hours': total_hours,
        'shifts_attended': attended,
        'no_shows': no_shows,
        'total_signups': len(signups),
    })


# ===================================================================
#  PLOT HISTORY — Public endpoints
# ===================================================================

@gardens_api.route('/<garden_id>/plots/<int:plot_id>/history', methods=['GET'])
def plot_history(garden_id, plot_id):
    """Get assignment history for a specific plot."""
    entries = PlotAssignmentHistory.query.filter_by(
        garden_id=garden_id, plot_id=plot_id
    ).order_by(PlotAssignmentHistory.season_year.desc()).all()
    uids = {e.user_id for e in entries if e.user_id}
    users = ({u.id: u for u in User.query.filter(User.id.in_(uids)).all()}
             if uids else {})
    return jsonify([{
        'id': e.id,
        'plot_id': e.plot_id,
        'user_id': e.user_id,
        'user_name': (users[e.user_id].display_name
                      if e.user_id in users else 'Unknown'),
        'season_year': e.season_year,
        'assigned_date': e.assigned_date.isoformat() if e.assigned_date else None,
        'released_date': e.released_date.isoformat() if e.released_date else None,
        'notes': e.notes,
    } for e in entries])


# ===================================================================
#  WEATHER ALERTS — Public read
# ===================================================================

@gardens_api.route('/<garden_id>/weather/alerts', methods=['GET'])
def active_weather_alerts(garden_id):
    """Get active weather alerts for a garden."""
    now = datetime.now(timezone.utc)
    alerts = GardenWeatherAlert.query.filter(
        GardenWeatherAlert.garden_id == garden_id,
        (GardenWeatherAlert.active_until.is_(None)) | (GardenWeatherAlert.active_until >= now)
    ).order_by(GardenWeatherAlert.created_at.desc()).all()
    return jsonify([{
        'id': a.id,
        'alert_type': a.alert_type,
        'message': a.message,
        'severity': a.severity,
        'active_from': a.active_from.isoformat() if a.active_from else None,
        'active_until': a.active_until.isoformat() if a.active_until else None,
        'auto_generated': a.auto_generated,
        'created_at': a.created_at.isoformat() if a.created_at else None,
    } for a in alerts])


# ===================================================================
#  COMMENT WALL — Public, AI-moderated
# ===================================================================

def _comment_to_dict(c, current_user_id=None, is_admin=False, liked_ids=None):
    return {
        'id': c.id,
        'garden_id': c.garden_id,
        'parent_id': c.parent_id,
        'author_id': c.author_id,
        'author_name': format_display_name(
            c.author.display_name or c.author.username) if c.author else 'Member',
        'author_image': c.author.profile_image if c.author else None,
        'body': c.body,
        'status': c.status,
        'likes_count': c.likes_count or 0,
        'liked_by_me': bool(liked_ids and c.id in liked_ids),
        'created_at': c.created_at.isoformat() if c.created_at else None,
        # The frontend shows a delete control only when this is true.
        'can_delete': bool(current_user_id and (c.author_id == current_user_id or is_admin)),
    }


@gardens_api.route('/<garden_id>/comments', methods=['GET'])
def list_comments(garden_id):
    """Public comment wall for a garden (approved + flagged are visible)."""
    garden = db.get_or_404(CommunityGarden, garden_id)
    user = get_current_user()
    uid = user.id if user.is_authenticated else None
    is_admin = bool(user.is_authenticated and (user.is_admin or garden.organizer_id == uid))
    comments = (GardenComment.query
                .filter(GardenComment.garden_id == garden.id,
                        GardenComment.status.in_(('approved', 'flagged')))
                .order_by(GardenComment.created_at.desc())
                .limit(200).all())
    # One query for the current user's likes across these comments (no N+1).
    liked_ids = set()
    if uid and comments:
        liked_ids = {row[0] for row in db.session.query(GardenCommentLike.comment_id)
                     .filter(GardenCommentLike.user_id == uid,
                             GardenCommentLike.comment_id.in_([c.id for c in comments]))}
    return jsonify([_comment_to_dict(c, uid, is_admin, liked_ids) for c in comments])


@gardens_api.route('/<garden_id>/comments', methods=['POST'])
@token_or_session
def post_comment(garden_id):
    """Post a comment. Runs the AI moderator: 'block' is rejected (reason
    returned), 'flag' posts but alerts the garden organizer, 'allow' posts."""
    garden = db.get_or_404(CommunityGarden, garden_id)
    data = request.get_json() or {}
    body = (data.get('body') or '').strip()
    if not body:
        return jsonify({'error': 'Comment cannot be empty'}), 400
    if len(body) > 2000:
        return jsonify({'error': 'Comment is too long (max 2000 characters)'}), 400

    # Optional reply target. One-level threading: a reply always attaches to the
    # top-level comment, so threads never nest more than one deep.
    parent_id = data.get('parent_id')
    if parent_id is not None:
        parent = GardenComment.query.filter_by(id=parent_id, garden_id=garden.id).first()
        if not parent:
            return jsonify({'error': 'The comment you are replying to was not found.'}), 400
        parent_id = parent.parent_id or parent.id

    from app.moderation_service import moderate_comment
    decision, reason = moderate_comment(body)
    if decision == 'block':
        # Persist the auto-denied comment (status='blocked') instead of discarding
        # it — it stays off the public wall but appears in the admin "Auto-denied"
        # tab so a manager can review false positives (and publish if warranted).
        denied = GardenComment(
            garden_id=garden.id,
            author_id=get_current_user().id,
            body=body,
            parent_id=parent_id,
            status='blocked',
            moderation_reason=reason or None,
        )
        db.session.add(denied)
        db.session.commit()
        return jsonify({
            'error': 'Your comment was held by moderation and not posted.',
            'reason': reason or 'It may violate community standards.',
            'moderation': 'block',
        }), 422

    comment = GardenComment(
        garden_id=garden.id,
        author_id=get_current_user().id,
        body=body,
        parent_id=parent_id,
        status='flagged' if decision == 'flag' else 'approved',
        moderation_reason=reason if decision == 'flag' else None,
    )
    db.session.add(comment)
    db.session.commit()

    # Flagged comments post immediately but alert the organizer to review.
    if decision == 'flag' and garden.organizer_id:
        try:
            author = get_current_user()
            notify(
                user_id=garden.organizer_id,
                type='comment_flagged',
                title=f'Comment flagged for review — {garden.name}',
                body=f'A comment by {author.display_name or author.username} was '
                     f'auto-flagged: "{body[:120]}"',
                link=f'/gardens/{garden.public_id}',
                garden_id=garden.id,
            )
            db.session.commit()
        except Exception:
            log.exception('Failed to notify organizer of flagged comment')

    user = get_current_user()
    return jsonify(_comment_to_dict(comment, user.id, True)), 201


@gardens_api.route('/<garden_id>/comments/<int:comment_id>/like', methods=['POST'])
@token_or_session
def like_comment(garden_id, comment_id):
    """Toggle the current user's like on a comment; returns the new count + state."""
    garden = db.get_or_404(CommunityGarden, garden_id)
    comment = db.get_or_404(GardenComment, comment_id)
    if comment.garden_id != garden.id:
        abort(404)
    uid = get_current_user().id
    existing = GardenCommentLike.query.filter_by(comment_id=comment.id, user_id=uid).first()
    if existing:
        db.session.delete(existing)
        comment.likes_count = max(0, (comment.likes_count or 0) - 1)
        liked = False
    else:
        db.session.add(GardenCommentLike(comment_id=comment.id, user_id=uid))
        comment.likes_count = (comment.likes_count or 0) + 1
        liked = True
    db.session.commit()
    return jsonify({'likes_count': comment.likes_count, 'liked': liked})


@gardens_api.route('/<garden_id>/comments/<int:comment_id>', methods=['DELETE'])
@token_or_session
def delete_comment(garden_id, comment_id):
    """Delete a comment — allowed for the author or a garden admin/organizer."""
    garden = db.get_or_404(CommunityGarden, garden_id)
    comment = db.get_or_404(GardenComment, comment_id)
    if comment.garden_id != garden.id:
        return jsonify({'error': 'Comment not in this garden'}), 400
    user = get_current_user()
    is_admin = user.is_admin or garden.organizer_id == user.id
    if comment.author_id != user.id and not is_admin:
        return jsonify({'error': 'Not authorized'}), 403
    db.session.delete(comment)
    db.session.commit()
    return jsonify({'success': True})


# ---------------------------------------------------------------------------
# Garden Dues — Member self-service payment via Stripe
# ---------------------------------------------------------------------------

@gardens_api.route('/<garden_id>/my-dues', methods=['GET'])
@token_or_session
def my_dues(garden_id):
    """Get current user's dues records for this garden."""
    records = GardenDuesRecord.query.filter_by(
        garden_id=garden_id, user_id=get_current_user().id
    ).order_by(GardenDuesRecord.season_year.desc()).all()
    return jsonify([{
        'id': r.id,
        'season_year': r.season_year,
        'amount_due': r.amount_due,
        'amount_paid': r.amount_paid,
        'status': r.status,
        'payment_method': r.payment_method,
        'payment_date': r.payment_date.isoformat() if r.payment_date else None,
        'payment_note': r.payment_note,
    } for r in records])


@gardens_api.route('/<garden_id>/dues/<int:dues_id>/pay', methods=['POST'])
@token_or_session
def pay_dues(garden_id, dues_id):
    """Create a Stripe PaymentIntent for a dues payment."""
    import logging
    log = logging.getLogger(__name__)
    from app import stripe_service

    rec = db.get_or_404(GardenDuesRecord, dues_id)
    if rec.garden_id != garden_id or rec.user_id != get_current_user().id:
        return jsonify({'error': 'Dues record not found'}), 404
    if rec.status in ('paid', 'waived', 'comp'):
        return jsonify({'error': 'Dues already paid or waived'}), 400

    garden = db.get_or_404(CommunityGarden, garden_id)
    remaining = rec.amount_due - rec.amount_paid
    if remaining <= 0:
        return jsonify({'error': 'No balance due'}), 400

    amount_cents = int(round(remaining * 100))

    if not stripe_service.is_configured():
        return jsonify({
            'dev_mode': True,
            'amount': amount_cents,
            'currency': 'USD',
            'dues_id': rec.id,
        })

    # Dues should route to the garden manager's Stripe Connect account. The
    # admin switch PricingConfig.dues_require_payout_ready (default True) decides
    # what happens when the manager ISN'T payout-ready yet:
    #   True  → refuse collection (409) so dues are never charged to the platform.
    #   False → fall back to a plain platform charge so collection still works
    #           (those dues land with the platform until reconciled manually).
    from app.pricing import get_pricing_config
    organizer = garden.organizer
    manager_ready = bool(organizer and stripe_service.connect_account_ready(organizer))
    require_ready = bool(getattr(get_pricing_config(), 'dues_require_payout_ready', True))
    if not manager_ready and require_ready:
        return jsonify({
            'error': "This garden hasn't finished payout setup yet, so online "
                     "dues can't be collected. Please ask your garden manager to "
                     "complete payout onboarding, then try again.",
            'reason': 'manager_payout_not_ready',
        }), 409

    try:
        from flask import current_app
        customer_id = stripe_service.get_or_create_customer(get_current_user())

        destination = None
        application_fee_cents = None
        routed_to_manager = False
        # Card + US bank only (never Amazon Pay / Cash App Pay / Klarna).
        payment_method_types = ['card', 'us_bank_account']
        if manager_ready:
            # Destination charge → funds go directly to the manager's connected
            # account, on behalf of the manager (merchant of record), minus an
            # optional platform application fee. On a destination charge the
            # connected account is merchant of record, so only offer bank (ACH)
            # when that account actually has the capability.
            destination = organizer.stripe_connect_account_id
            payment_method_types = stripe_service.connect_payment_method_types(organizer)
            # Admin-set platform fee on dues (PricingConfig), with the legacy
            # GARDEN_DUES_FEE_PERCENT env var as a fallback for back-compat.
            fee_pct = getattr(get_pricing_config(), 'garden_dues_fee_percent', 0) or 0
            if not fee_pct:
                fee_pct = float(current_app.config.get('GARDEN_DUES_FEE_PERCENT', 0) or 0)
            application_fee_cents = int(round(amount_cents * fee_pct / 100)) if fee_pct else None
            routed_to_manager = True
        # else: switch is OFF and manager isn't ready → plain platform charge.

        pi = stripe_service.create_payment_intent(
            amount_cents=amount_cents,
            customer_id=customer_id,
            metadata={
                'type': 'garden_dues',
                'garden_id': str(garden_id),
                'dues_id': str(rec.id),
                'user_id': str(get_current_user().id),
                'routed_to_manager': str(routed_to_manager),
            },
            destination_account_id=destination,
            application_fee_cents=application_fee_cents,
            on_behalf_of=destination,
            payment_method_types=payment_method_types,
        )
        return jsonify({
            'client_secret': pi.client_secret,
            'payment_intent_id': pi.id,
            'publishable_key': stripe_service.get_publishable_key(),
            'amount': amount_cents,
            'currency': 'USD',
            'dues_id': rec.id,
            'routed_to_manager': routed_to_manager,
            'dev_mode': False,
        })
    except Exception:
        log.exception('Stripe dues PaymentIntent creation failed')
        return jsonify({'error': 'Payment service temporarily unavailable.'}), 500


@gardens_api.route('/<garden_id>/dues/<int:dues_id>/confirm-payment', methods=['POST'])
@token_or_session
def confirm_dues_payment(garden_id, dues_id):
    """After Stripe payment, update the dues record."""
    import logging
    log = logging.getLogger(__name__)
    from app import stripe_service

    rec = db.get_or_404(GardenDuesRecord, dues_id)
    if rec.garden_id != garden_id or rec.user_id != get_current_user().id:
        return jsonify({'error': 'Dues record not found'}), 404

    data = request.get_json() or {}
    payment_intent_id = data.get('payment_intent_id', '')

    if not payment_intent_id:
        return jsonify({'error': 'Payment intent ID is required'}), 400

    # Idempotency: the Stripe webhook (payment_intent.succeeded) may have
    # already settled this record. If so, return success without re-notifying.
    # This endpoint is the instant-UX path; the webhook is the guarantee.
    if rec.status == 'paid' and rec.stripe_payment_intent_id == payment_intent_id:
        return jsonify({
            'message': 'Payment already confirmed — dues paid!',
            'dues': {
                'id': rec.id, 'season_year': rec.season_year,
                'amount_due': rec.amount_due, 'amount_paid': rec.amount_paid,
                'status': rec.status, 'payment_method': rec.payment_method,
                'payment_date': rec.payment_date.isoformat() if rec.payment_date else None,
            },
        })

    # Verify with Stripe
    if stripe_service.is_configured() and not payment_intent_id.startswith('dev-'):
        try:
            pi = stripe_service.retrieve_payment_intent(payment_intent_id)
            if pi.status != 'succeeded':
                return jsonify({'error': 'Payment has not been completed'}), 400
        except Exception:
            log.exception('Stripe verification failed for %s', payment_intent_id)
            return jsonify({'error': 'Unable to verify payment. Please contact support.'}), 500

    # Update dues record
    rec.amount_paid = rec.amount_due
    rec.status = 'paid'
    rec.payment_method = 'online'
    rec.payment_date = date.today()
    rec.stripe_payment_intent_id = payment_intent_id
    rec.payment_note = f'Stripe: {payment_intent_id}'

    # Notify garden organizer
    garden = db.session.get(CommunityGarden, garden_id)
    payer_name = get_current_user().display_name or get_current_user().username
    notify(
        user_id=garden.organizer_id,
        type='dues_paid',
        title=f'{payer_name} paid dues',
        body=f'{payer_name} paid ${rec.amount_due:.2f} for {rec.season_year} season dues via online payment.',
        link=f'/gardens/{garden.public_id}/admin?tab=finance',
        garden_id=garden_id,
    )

    db.session.commit()

    return jsonify({
        'message': 'Payment confirmed — dues paid!',
        'dues': {
            'id': rec.id,
            'season_year': rec.season_year,
            'amount_due': rec.amount_due,
            'amount_paid': rec.amount_paid,
            'status': rec.status,
            'payment_method': rec.payment_method,
            'payment_date': rec.payment_date.isoformat() if rec.payment_date else None,
        },
    })
