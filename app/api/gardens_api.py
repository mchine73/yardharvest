"""Community Gardens REST API endpoints."""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.api.token_auth import token_or_session, get_current_user
from app import db
from app.models import (
    CommunityGarden, GardenPlot, GardenWaitlist, SharedResource,
    GardenEvent, EventRSVP, HarvestLog, User, ResourceCheckoutLog,
    VolunteerShift, ShiftSignup, PlotAssignmentHistory,
    GardenKnowledgeArticle, GardenWeatherAlert, GardenDuesRecord,
    GardenAnnouncement
)
from app.email_service import send_waitlist_notification
from app.helpers import format_display_name
from app.api.notifications_api import notify
from datetime import datetime, timezone, timedelta, date, time as dtime
from sqlalchemy import func
import re
import logging

log = logging.getLogger(__name__)

gardens_api = Blueprint('gardens_api', __name__, url_prefix='/api/gardens')


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text


def garden_to_dict(garden, include_stats=False):
    d = {
        'id': garden.id,
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


def resource_to_dict(res):
    now = datetime.now(timezone.utc)
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
        'is_overdue': bool(res.due_date and res.checked_out_to_id and res.due_date < now),
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

    pagination = q.order_by(CommunityGarden.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return jsonify({
        'gardens': [garden_to_dict(g) for g in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'page': pagination.page,
        'has_next': pagination.has_next,
        'has_prev': pagination.has_prev,
    })


@gardens_api.route('/<int:garden_id>', methods=['GET'])
def garden_detail(garden_id):
    garden = CommunityGarden.query.get_or_404(garden_id)
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

    # Also support bulk plot creation by count
    bulk_count = int(data.get('bulk_plot_count', 0))
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


@gardens_api.route('/<int:garden_id>', methods=['PUT'])
@token_or_session
def update_garden(garden_id):
    garden = CommunityGarden.query.get_or_404(garden_id)
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

@gardens_api.route('/<int:garden_id>/plots', methods=['GET'])
def list_plots(garden_id):
    garden = CommunityGarden.query.get_or_404(garden_id)
    plots = garden.plots.order_by(GardenPlot.plot_number).all()
    return jsonify([plot_to_dict(p) for p in plots])


@gardens_api.route('/<int:garden_id>/plots', methods=['POST'])
@token_or_session
def add_plots(garden_id):
    garden = CommunityGarden.query.get_or_404(garden_id)
    if garden.organizer_id != get_current_user().id:
        return jsonify({'error': 'Not authorized'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    plots_data = data.get('plots', [])
    bulk_count = int(data.get('bulk_count', 0))
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


@gardens_api.route('/<int:garden_id>/plots/<int:plot_id>/assign', methods=['PUT'])
@token_or_session
def assign_plot(garden_id, plot_id):
    garden = CommunityGarden.query.get_or_404(garden_id)
    if garden.organizer_id != get_current_user().id:
        return jsonify({'error': 'Not authorized'}), 403

    plot = GardenPlot.query.get_or_404(plot_id)
    if plot.garden_id != garden_id:
        return jsonify({'error': 'Plot not in this garden'}), 400

    data = request.get_json()
    if not data or not data.get('user_id'):
        return jsonify({'error': 'user_id required'}), 400

    user = User.query.get_or_404(data['user_id'])
    plot.assigned_to_id = user.id
    plot.status = 'assigned'
    plot.assigned_date = datetime.now(timezone.utc).date()

    db.session.commit()
    return jsonify(plot_to_dict(plot))


@gardens_api.route('/<int:garden_id>/plots/<int:plot_id>/release', methods=['PUT'])
@token_or_session
def release_plot(garden_id, plot_id):
    garden = CommunityGarden.query.get_or_404(garden_id)
    if garden.organizer_id != get_current_user().id:
        return jsonify({'error': 'Not authorized'}), 403

    plot = GardenPlot.query.get_or_404(plot_id)
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

@gardens_api.route('/<int:garden_id>/plots/<int:plot_id>/rename', methods=['PUT'])
@token_or_session
def rename_plot(garden_id, plot_id):
    """Allow a plot owner to set a custom name for their plot."""
    user = get_current_user()
    garden = CommunityGarden.query.get_or_404(garden_id)
    plot = GardenPlot.query.get_or_404(plot_id)
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

@gardens_api.route('/<int:garden_id>/plots/<int:plot_id>/reserve', methods=['POST'])
@token_or_session
def reserve_plot(garden_id, plot_id):
    """User reserves an available plot (pending organizer confirmation)."""
    garden = CommunityGarden.query.get_or_404(garden_id)
    plot = GardenPlot.query.get_or_404(plot_id)

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

    plot.status = 'reserved'
    plot.reserved_by_id = get_current_user().id
    plot.reserved_at = datetime.now(timezone.utc)

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
        link=f'/gardens/{garden_id}/admin?tab=plots',
        garden_id=garden_id,
    )

    db.session.commit()
    return jsonify(plot_to_dict(plot))


# ---- Waitlist ----

@gardens_api.route('/<int:garden_id>/waitlist', methods=['POST'])
@token_or_session
def join_waitlist(garden_id):
    garden = CommunityGarden.query.get_or_404(garden_id)

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
        send_waitlist_notification(garden.name, get_current_user().email)
    except Exception:
        pass

    return jsonify(waitlist_to_dict(entry)), 201


@gardens_api.route('/<int:garden_id>/waitlist', methods=['GET'])
@token_or_session
def view_waitlist(garden_id):
    garden = CommunityGarden.query.get_or_404(garden_id)
    if garden.organizer_id != get_current_user().id and not get_current_user().is_admin:
        return jsonify({'error': 'Not authorized'}), 403

    entries = GardenWaitlist.query.filter_by(
        garden_id=garden_id
    ).order_by(GardenWaitlist.requested_at).all()
    return jsonify([waitlist_to_dict(e) for e in entries])


# ---- Resources ----

@gardens_api.route('/<int:garden_id>/resources', methods=['GET'])
def list_resources(garden_id):
    try:
        garden = CommunityGarden.query.get_or_404(garden_id)
        resources = SharedResource.query.filter_by(garden_id=garden_id).order_by(SharedResource.name).all()
        return jsonify([resource_to_dict(r) for r in resources])
    except Exception as e:
        log.error('Resources error for garden_id=%d: %s', garden_id, e)
        return jsonify({'error': 'Failed to load resources'}), 500


@gardens_api.route('/<int:garden_id>/resources', methods=['POST'])
@token_or_session
def add_resource(garden_id):
    garden = CommunityGarden.query.get_or_404(garden_id)
    if garden.organizer_id != get_current_user().id and not get_current_user().is_admin:
        return jsonify({'error': 'Only the garden organizer can add resources'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Resource name is required'}), 400

    res = SharedResource(
        garden_id=garden_id,
        name=name,
        resource_type=data.get('resource_type', 'tool'),
        description=data.get('description', ''),
        quantity=int(data.get('quantity', 1)),
        condition=data.get('condition', 'good'),
    )
    db.session.add(res)
    db.session.commit()
    return jsonify(resource_to_dict(res)), 201


@gardens_api.route('/<int:garden_id>/resources/<int:res_id>/checkout', methods=['POST'])
@token_or_session
def checkout_resource(garden_id, res_id):
    garden = CommunityGarden.query.get_or_404(garden_id)
    res = SharedResource.query.get_or_404(res_id)
    if res.garden_id != garden_id:
        return jsonify({'error': 'Resource not in this garden'}), 400
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


@gardens_api.route('/<int:garden_id>/resources/<int:res_id>/return', methods=['POST'])
@token_or_session
def return_resource(garden_id, res_id):
    res = SharedResource.query.get_or_404(res_id)
    if res.garden_id != garden_id:
        return jsonify({'error': 'Resource not in this garden'}), 400
    if res.checked_out_to_id != get_current_user().id:
        # Allow organizer to return for anyone
        garden = CommunityGarden.query.get(garden_id)
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


@gardens_api.route('/<int:garden_id>/resources/<int:res_id>/qr', methods=['GET'])
def resource_qr_code(garden_id, res_id):
    """Return a QR code PNG image for a resource."""
    from flask import Response, current_app
    from app.qr_service import generate_resource_qr

    CommunityGarden.query.get_or_404(garden_id)
    SharedResource.query.get_or_404(res_id)

    base_url = current_app.config.get('RENDER_EXTERNAL_URL', request.host_url.rstrip('/'))
    png_bytes = generate_resource_qr(garden_id, res_id, base_url)

    if png_bytes is None:
        return jsonify({'error': 'QR code generation not available (install qrcode[pil])'}), 503

    return Response(png_bytes, mimetype='image/png', headers={
        'Content-Disposition': f'inline; filename=resource-{res_id}-qr.png'
    })


@gardens_api.route('/<int:garden_id>/resources/overdue', methods=['GET'])
@token_or_session
def overdue_resources(garden_id):
    """List overdue resources for this garden (organizer/admin only)."""
    garden = CommunityGarden.query.get_or_404(garden_id)
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
            resource = SharedResource.query.get(int(match.group(2)))

    if not resource:
        return jsonify({'error': 'Resource not found'}), 404

    garden = CommunityGarden.query.get(resource.garden_id)
    return jsonify({
        'garden_id': resource.garden_id,
        'garden_name': garden.name if garden else '',
        'resource_id': resource.id,
        'resource': resource_to_dict(resource),
    })


@gardens_api.route('/<int:garden_id>/resources/<int:res_id>/history', methods=['GET'])
def resource_history(garden_id, res_id):
    """Get checkout history for a resource."""
    resource = SharedResource.query.get_or_404(res_id)
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

@gardens_api.route('/<int:garden_id>/events', methods=['GET'])
def list_events(garden_id):
    garden = CommunityGarden.query.get_or_404(garden_id)
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


@gardens_api.route('/<int:garden_id>/events', methods=['POST'])
@token_or_session
def create_event(garden_id):
    garden = CommunityGarden.query.get_or_404(garden_id)
    if garden.organizer_id != get_current_user().id and not get_current_user().is_admin:
        return jsonify({'error': 'Only the garden organizer can create events'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    title = data.get('title', '').strip()
    event_date_str = data.get('event_date', '')
    if not title or not event_date_str:
        return jsonify({'error': 'Title and event_date are required'}), 400

    event = GardenEvent(
        garden_id=garden_id,
        title=title,
        description=data.get('description', ''),
        event_type=data.get('event_type', 'workday'),
        event_date=datetime.fromisoformat(event_date_str),
        duration_hours=float(data.get('duration_hours', 2.0)),
        max_volunteers=data.get('max_volunteers'),
        created_by_id=get_current_user().id,
    )
    db.session.add(event)
    db.session.commit()
    return jsonify(event_to_dict(event)), 201


@gardens_api.route('/<int:garden_id>/events/<int:event_id>/rsvp', methods=['POST'])
@token_or_session
def rsvp_event(garden_id, event_id):
    event = GardenEvent.query.get_or_404(event_id)
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
        # Check max volunteers
        if event.max_volunteers:
            going_count = event.rsvps.filter_by(status='going').count()
            if status == 'going' and going_count >= event.max_volunteers:
                return jsonify({'error': 'Event is full'}), 400
        rsvp = EventRSVP(
            event_id=event_id,
            user_id=get_current_user().id,
            status=status,
        )
        db.session.add(rsvp)

    db.session.commit()
    return jsonify(event_to_dict(event))


@gardens_api.route('/<int:garden_id>/events/<int:event_id>/rsvp', methods=['DELETE'])
@token_or_session
def cancel_rsvp(garden_id, event_id):
    event = GardenEvent.query.get_or_404(event_id)
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

@gardens_api.route('/<int:garden_id>/harvests', methods=['GET'])
def list_harvests(garden_id):
    garden = CommunityGarden.query.get_or_404(garden_id)

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


@gardens_api.route('/<int:garden_id>/harvests', methods=['POST'])
@token_or_session
def log_harvest(garden_id):
    garden = CommunityGarden.query.get_or_404(garden_id)

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

@gardens_api.route('/<int:garden_id>/impact', methods=['GET'])
def impact_stats(garden_id):
    garden = CommunityGarden.query.get_or_404(garden_id)

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

    # Monthly harvest trend
    monthly_trend = db.session.query(
        db.func.strftime('%Y-%m', HarvestLog.harvest_date),
        db.func.sum(HarvestLog.quantity_lbs)
    ).filter_by(garden_id=garden_id).group_by(
        db.func.strftime('%Y-%m', HarvestLog.harvest_date)
    ).order_by(db.func.strftime('%Y-%m', HarvestLog.harvest_date)).all()

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

@gardens_api.route('/<int:garden_id>/members', methods=['GET'])
def list_members(garden_id):
    garden = CommunityGarden.query.get_or_404(garden_id)

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

@gardens_api.route('/<int:garden_id>/announcements', methods=['GET'])
def list_announcements(garden_id):
    """Public endpoint to view garden announcements."""
    garden = CommunityGarden.query.get_or_404(garden_id)
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


@gardens_api.route('/<int:garden_id>/shifts', methods=['GET'])
def list_shifts(garden_id):
    """List upcoming volunteer shifts for a garden."""
    garden = CommunityGarden.query.get_or_404(garden_id)
    show = request.args.get('show', 'upcoming')
    q = VolunteerShift.query.filter_by(garden_id=garden_id)
    if show == 'upcoming':
        q = q.filter(VolunteerShift.shift_date >= date.today())
    shifts = q.order_by(VolunteerShift.shift_date, VolunteerShift.start_time).all()
    return jsonify([shift_to_dict(s) for s in shifts])


@gardens_api.route('/<int:garden_id>/shifts/<int:shift_id>/signup', methods=['POST'])
@token_or_session
def signup_for_shift(garden_id, shift_id):
    """Sign up for a volunteer shift."""
    shift = VolunteerShift.query.get_or_404(shift_id)
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
        link=f'/gardens/{garden_id}/admin?tab=volunteers',
        garden_id=garden_id,
    )

    db.session.commit()
    return jsonify({'message': 'Signed up successfully'}), 201


@gardens_api.route('/<int:garden_id>/shifts/<int:shift_id>/signup', methods=['DELETE'])
@token_or_session
def cancel_shift_signup(garden_id, shift_id):
    """Cancel signup for a volunteer shift."""
    signup = ShiftSignup.query.filter_by(shift_id=shift_id, user_id=get_current_user().id).first()
    if not signup:
        return jsonify({'error': 'Not signed up for this shift'}), 404
    db.session.delete(signup)
    db.session.commit()
    return jsonify({'message': 'Signup cancelled'})


@gardens_api.route('/<int:garden_id>/volunteer-hours', methods=['GET'])
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

@gardens_api.route('/<int:garden_id>/plots/<int:plot_id>/history', methods=['GET'])
def plot_history(garden_id, plot_id):
    """Get assignment history for a specific plot."""
    entries = PlotAssignmentHistory.query.filter_by(
        garden_id=garden_id, plot_id=plot_id
    ).order_by(PlotAssignmentHistory.season_year.desc()).all()
    return jsonify([{
        'id': e.id,
        'plot_id': e.plot_id,
        'user_id': e.user_id,
        'user_name': User.query.get(e.user_id).display_name if User.query.get(e.user_id) else 'Unknown',
        'season_year': e.season_year,
        'assigned_date': e.assigned_date.isoformat() if e.assigned_date else None,
        'released_date': e.released_date.isoformat() if e.released_date else None,
        'notes': e.notes,
    } for e in entries])


# ===================================================================
#  KNOWLEDGE BASE — Public read endpoints
# ===================================================================

@gardens_api.route('/<int:garden_id>/knowledge', methods=['GET'])
def list_knowledge(garden_id):
    """List knowledge articles for a garden (garden-specific + platform-wide)."""
    from sqlalchemy import or_
    category = request.args.get('category')
    q = GardenKnowledgeArticle.query.filter(
        or_(GardenKnowledgeArticle.garden_id == garden_id, GardenKnowledgeArticle.garden_id.is_(None))
    )
    if category:
        q = q.filter_by(category=category)
    articles = q.order_by(GardenKnowledgeArticle.pinned.desc(), GardenKnowledgeArticle.created_at.desc()).all()
    return jsonify([{
        'id': a.id,
        'garden_id': a.garden_id,
        'author_id': a.author_id,
        'author_name': User.query.get(a.author_id).display_name if User.query.get(a.author_id) else 'Unknown',
        'title': a.title,
        'body': a.body,
        'category': a.category,
        'pinned': a.pinned,
        'created_at': a.created_at.isoformat() if a.created_at else None,
        'updated_at': a.updated_at.isoformat() if a.updated_at else None,
    } for a in articles])


# ===================================================================
#  WEATHER ALERTS — Public read
# ===================================================================

@gardens_api.route('/<int:garden_id>/weather/alerts', methods=['GET'])
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


# ---------------------------------------------------------------------------
# Garden Dues — Member self-service payment via Stripe
# ---------------------------------------------------------------------------

@gardens_api.route('/<int:garden_id>/my-dues', methods=['GET'])
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


@gardens_api.route('/<int:garden_id>/dues/<int:dues_id>/pay', methods=['POST'])
@token_or_session
def pay_dues(garden_id, dues_id):
    """Create a Stripe PaymentIntent for a dues payment."""
    import logging
    log = logging.getLogger(__name__)
    from app import stripe_service

    rec = GardenDuesRecord.query.get_or_404(dues_id)
    if rec.garden_id != garden_id or rec.user_id != get_current_user().id:
        return jsonify({'error': 'Dues record not found'}), 404
    if rec.status in ('paid', 'waived', 'comp'):
        return jsonify({'error': 'Dues already paid or waived'}), 400

    garden = CommunityGarden.query.get_or_404(garden_id)
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

    try:
        customer_id = stripe_service.get_or_create_customer(get_current_user())
        pi = stripe_service.create_payment_intent(
            amount_cents=amount_cents,
            customer_id=customer_id,
            metadata={
                'type': 'garden_dues',
                'garden_id': str(garden_id),
                'dues_id': str(rec.id),
                'user_id': str(get_current_user().id),
            },
        )
        return jsonify({
            'client_secret': pi.client_secret,
            'payment_intent_id': pi.id,
            'publishable_key': stripe_service.get_publishable_key(),
            'amount': amount_cents,
            'currency': 'USD',
            'dues_id': rec.id,
            'dev_mode': False,
        })
    except Exception:
        log.exception('Stripe dues PaymentIntent creation failed')
        return jsonify({'error': 'Payment service temporarily unavailable.'}), 500


@gardens_api.route('/<int:garden_id>/dues/<int:dues_id>/confirm-payment', methods=['POST'])
@token_or_session
def confirm_dues_payment(garden_id, dues_id):
    """After Stripe payment, update the dues record."""
    import logging
    log = logging.getLogger(__name__)
    from app import stripe_service

    rec = GardenDuesRecord.query.get_or_404(dues_id)
    if rec.garden_id != garden_id or rec.user_id != get_current_user().id:
        return jsonify({'error': 'Dues record not found'}), 404

    data = request.get_json() or {}
    payment_intent_id = data.get('payment_intent_id', '')

    if not payment_intent_id:
        return jsonify({'error': 'Payment intent ID is required'}), 400

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
    rec.payment_note = f'Stripe: {payment_intent_id}'

    # Notify garden organizer
    garden = CommunityGarden.query.get(garden_id)
    payer_name = get_current_user().display_name or get_current_user().username
    notify(
        user_id=garden.organizer_id,
        type='dues_paid',
        title=f'{payer_name} paid dues',
        body=f'{payer_name} paid ${rec.amount_due:.2f} for {rec.season_year} season dues via online payment.',
        link=f'/gardens/{garden_id}/admin?tab=finance',
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
