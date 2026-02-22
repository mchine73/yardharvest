"""Community Gardens REST API endpoints."""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import (
    CommunityGarden, GardenPlot, GardenWaitlist, SharedResource,
    GardenEvent, EventRSVP, HarvestLog, User, ResourceCheckoutLog
)
from app.email_service import send_waitlist_notification
from datetime import datetime, timezone, timedelta
import re

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
        'organizer_id': garden.organizer_id,
        'organizer_name': garden.organizer.display_name or garden.organizer.username,
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
    }
    if plot.assigned_to:
        d['assigned_to_name'] = plot.assigned_to.display_name or plot.assigned_to.username
    else:
        d['assigned_to_name'] = None
    if plot.reserved_by:
        d['reserved_by_name'] = plot.reserved_by.display_name or plot.reserved_by.username
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
        d['checked_out_to_name'] = res.checked_out_to.display_name or res.checked_out_to.username
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
        'created_by_name': event.created_by.display_name or event.created_by.username,
        'created_at': event.created_at.isoformat() if event.created_at else None,
        'rsvp_going': event.rsvps.filter_by(status='going').count(),
        'rsvp_maybe': event.rsvps.filter_by(status='maybe').count(),
    }
    if current_user.is_authenticated:
        user_rsvp = event.rsvps.filter_by(user_id=current_user.id).first()
        d['user_rsvp'] = user_rsvp.status if user_rsvp else None
    else:
        d['user_rsvp'] = None
    return d


def harvest_to_dict(harvest):
    return {
        'id': harvest.id,
        'garden_id': harvest.garden_id,
        'user_id': harvest.user_id,
        'user_name': harvest.user.display_name or harvest.user.username,
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
        'user_name': entry.user.display_name or entry.user.username,
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
    if current_user.is_authenticated:
        data['user_is_organizer'] = garden.organizer_id == current_user.id
        data['user_has_plot'] = garden.plots.filter_by(
            assigned_to_id=current_user.id, status='assigned'
        ).count() > 0
        data['user_on_waitlist'] = GardenWaitlist.query.filter_by(
            garden_id=garden_id, user_id=current_user.id, status='waiting'
        ).count() > 0
        data['user_has_reservation'] = garden.plots.filter_by(
            reserved_by_id=current_user.id, status='reserved'
        ).count() > 0

    return jsonify(data)


@gardens_api.route('', methods=['POST'])
@login_required
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
        organizer_id=current_user.id,
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
@login_required
def update_garden(garden_id):
    garden = CommunityGarden.query.get_or_404(garden_id)
    if garden.organizer_id != current_user.id:
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
@login_required
def add_plots(garden_id):
    garden = CommunityGarden.query.get_or_404(garden_id)
    if garden.organizer_id != current_user.id:
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
@login_required
def assign_plot(garden_id, plot_id):
    garden = CommunityGarden.query.get_or_404(garden_id)
    if garden.organizer_id != current_user.id:
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
@login_required
def release_plot(garden_id, plot_id):
    garden = CommunityGarden.query.get_or_404(garden_id)
    if garden.organizer_id != current_user.id:
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


# ---- Plot Reservation (self-service) ----

@gardens_api.route('/<int:garden_id>/plots/<int:plot_id>/reserve', methods=['POST'])
@login_required
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
        assigned_to_id=current_user.id, status='assigned'
    ).first()
    if existing_plot:
        return jsonify({'error': 'You already have a plot in this garden'}), 400

    existing_reservation = garden.plots.filter_by(
        reserved_by_id=current_user.id, status='reserved'
    ).first()
    if existing_reservation:
        return jsonify({'error': 'You already have a pending reservation'}), 400

    plot.status = 'reserved'
    plot.reserved_by_id = current_user.id
    plot.reserved_at = datetime.now(timezone.utc)

    # Remove user from waitlist if they were on it
    wl_entry = GardenWaitlist.query.filter_by(
        garden_id=garden_id, user_id=current_user.id, status='waiting'
    ).first()
    if wl_entry:
        wl_entry.status = 'offered'

    db.session.commit()
    return jsonify(plot_to_dict(plot))


# ---- Waitlist ----

@gardens_api.route('/<int:garden_id>/waitlist', methods=['POST'])
@login_required
def join_waitlist(garden_id):
    garden = CommunityGarden.query.get_or_404(garden_id)

    # Check if already on waitlist
    existing = GardenWaitlist.query.filter_by(
        garden_id=garden_id, user_id=current_user.id, status='waiting'
    ).first()
    if existing:
        return jsonify({'error': 'Already on waitlist'}), 400

    data = request.get_json() or {}
    entry = GardenWaitlist(
        garden_id=garden_id,
        user_id=current_user.id,
        plot_size_pref=data.get('plot_size_pref', ''),
        notes=data.get('notes', ''),
    )
    db.session.add(entry)
    db.session.commit()

    # Notify the user via email that they've been added to the waitlist
    try:
        send_waitlist_notification(garden.name, current_user.email)
    except Exception:
        pass

    return jsonify(waitlist_to_dict(entry)), 201


@gardens_api.route('/<int:garden_id>/waitlist', methods=['GET'])
@login_required
def view_waitlist(garden_id):
    garden = CommunityGarden.query.get_or_404(garden_id)
    if garden.organizer_id != current_user.id:
        return jsonify({'error': 'Not authorized'}), 403

    entries = GardenWaitlist.query.filter_by(
        garden_id=garden_id
    ).order_by(GardenWaitlist.requested_at).all()
    return jsonify([waitlist_to_dict(e) for e in entries])


# ---- Resources ----

@gardens_api.route('/<int:garden_id>/resources', methods=['GET'])
def list_resources(garden_id):
    garden = CommunityGarden.query.get_or_404(garden_id)
    resources = garden.resources.order_by(SharedResource.name).all()
    return jsonify([resource_to_dict(r) for r in resources])


@gardens_api.route('/<int:garden_id>/resources', methods=['POST'])
@login_required
def add_resource(garden_id):
    garden = CommunityGarden.query.get_or_404(garden_id)

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
@login_required
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
        garden_id=garden_id, checked_out_to_id=current_user.id
    ).count()
    if current_checkouts >= max_co:
        return jsonify({'error': f'You can only check out {max_co} items at a time'}), 400

    data = request.get_json() or {}
    duration = data.get('duration_days', 3)
    if duration not in [1, 3, 7]:
        duration = 3

    now = datetime.now(timezone.utc)
    res.checked_out_to_id = current_user.id
    res.checked_out_at = now
    res.due_date = now + timedelta(days=duration)

    # Create checkout log
    log = ResourceCheckoutLog(
        resource_id=res.id,
        user_id=current_user.id,
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
@login_required
def return_resource(garden_id, res_id):
    res = SharedResource.query.get_or_404(res_id)
    if res.garden_id != garden_id:
        return jsonify({'error': 'Resource not in this garden'}), 400
    if res.checked_out_to_id != current_user.id:
        # Allow organizer to return for anyone
        garden = CommunityGarden.query.get(garden_id)
        if garden.organizer_id != current_user.id:
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
@login_required
def overdue_resources(garden_id):
    """List overdue resources for this garden."""
    garden = CommunityGarden.query.get_or_404(garden_id)
    now = datetime.now(timezone.utc)

    overdue = SharedResource.query.filter(
        SharedResource.garden_id == garden_id,
        SharedResource.checked_out_to_id.isnot(None),
        SharedResource.due_date.isnot(None),
        SharedResource.due_date < now,
    ).all()

    return jsonify([resource_to_dict(r) for r in overdue])


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
@login_required
def create_event(garden_id):
    garden = CommunityGarden.query.get_or_404(garden_id)

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
        created_by_id=current_user.id,
    )
    db.session.add(event)
    db.session.commit()
    return jsonify(event_to_dict(event)), 201


@gardens_api.route('/<int:garden_id>/events/<int:event_id>/rsvp', methods=['POST'])
@login_required
def rsvp_event(garden_id, event_id):
    event = GardenEvent.query.get_or_404(event_id)
    if event.garden_id != garden_id:
        return jsonify({'error': 'Event not in this garden'}), 400

    data = request.get_json() or {}
    status = data.get('status', 'going')

    existing = EventRSVP.query.filter_by(
        event_id=event_id, user_id=current_user.id
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
            user_id=current_user.id,
            status=status,
        )
        db.session.add(rsvp)

    db.session.commit()
    return jsonify(event_to_dict(event))


@gardens_api.route('/<int:garden_id>/events/<int:event_id>/rsvp', methods=['DELETE'])
@login_required
def cancel_rsvp(garden_id, event_id):
    event = GardenEvent.query.get_or_404(event_id)
    if event.garden_id != garden_id:
        return jsonify({'error': 'Event not in this garden'}), 400

    existing = EventRSVP.query.filter_by(
        event_id=event_id, user_id=current_user.id
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
@login_required
def log_harvest(garden_id):
    garden = CommunityGarden.query.get_or_404(garden_id)

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    harvest_date_str = data.get('harvest_date', '')
    if not harvest_date_str:
        return jsonify({'error': 'harvest_date is required'}), 400

    harvest = HarvestLog(
        garden_id=garden_id,
        user_id=current_user.id,
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
                'name': plot.assigned_to.display_name or plot.assigned_to.username,
                'role': 'plot_holder',
                'plot_number': plot.plot_number,
                'since': plot.assigned_date.isoformat() if plot.assigned_date else None,
            })

    # Organizer
    if garden.organizer_id not in seen_users:
        members.insert(0, {
            'user_id': garden.organizer_id,
            'name': garden.organizer.display_name or garden.organizer.username,
            'role': 'organizer',
            'plot_number': None,
            'since': garden.created_at.isoformat() if garden.created_at else None,
        })

    return jsonify(members)


# ---- My Gardens ----

@gardens_api.route('/my-gardens', methods=['GET'])
@login_required
def my_gardens():
    # Gardens I organize
    organized = CommunityGarden.query.filter_by(
        organizer_id=current_user.id, is_active=True
    ).all()

    # Gardens where I have a plot
    my_plots = GardenPlot.query.filter_by(
        assigned_to_id=current_user.id, status='assigned'
    ).all()
    plot_garden_ids = list(set(p.garden_id for p in my_plots))
    plot_gardens = CommunityGarden.query.filter(
        CommunityGarden.id.in_(plot_garden_ids)
    ).all() if plot_garden_ids else []

    # Gardens I'm on waitlist for
    waitlist_entries = GardenWaitlist.query.filter_by(
        user_id=current_user.id, status='waiting'
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
