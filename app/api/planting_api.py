"""Planting Calendar & Harvest Forecasting REST API endpoints."""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import PlantingGuide, SellerPlanting, User
from datetime import datetime, date, timedelta

planting_api = Blueprint('planting_api', __name__, url_prefix='/api/planting')


# ---------------------------------------------------------------------------
# Seed data initializer
# ---------------------------------------------------------------------------

def init_planting_guide():
    """Insert Zone 5b planting guide data if the table is empty."""
    if PlantingGuide.query.first() is not None:
        return

    guides = [
        {
            'category': 'Tomatoes',
            'seed_indoor_start_doy': 60,
            'direct_sow_start_doy': None,
            'direct_sow_end_doy': None,
            'transplant_start_doy': 120,
            'transplant_end_doy': 150,
            'days_to_harvest_min': 60,
            'days_to_harvest_max': 85,
            'succession_interval_days': 14,
            'frost_sensitive': True,
            'notes': 'Start indoors 6-8 weeks before last frost (approx Mar 1). Transplant after all danger of frost. Stake or cage at planting time. Mulch heavily after soil warms.',
            'companion_plants': 'Basil, Carrots, Parsley, Marigolds',
            'avoid_near': 'Brassicas, Fennel, Corn',
        },
        {
            'category': 'Peppers (Hot)',
            'seed_indoor_start_doy': 46,
            'direct_sow_start_doy': None,
            'direct_sow_end_doy': None,
            'transplant_start_doy': 130,
            'transplant_end_doy': 155,
            'days_to_harvest_min': 65,
            'days_to_harvest_max': 90,
            'succession_interval_days': None,
            'frost_sensitive': True,
            'notes': 'Start indoors 10-12 weeks before last frost (approx Feb 15). Peppers need warm soil (65F+). Harden off gradually over 7-10 days.',
            'companion_plants': 'Basil, Tomatoes, Carrots, Onions',
            'avoid_near': 'Fennel, Brassicas',
        },
        {
            'category': 'Peppers (Sweet)',
            'seed_indoor_start_doy': 46,
            'direct_sow_start_doy': None,
            'direct_sow_end_doy': None,
            'transplant_start_doy': 130,
            'transplant_end_doy': 155,
            'days_to_harvest_min': 65,
            'days_to_harvest_max': 90,
            'succession_interval_days': None,
            'frost_sensitive': True,
            'notes': 'Start indoors 10-12 weeks before last frost (approx Feb 15). Needs warm soil. Bell peppers take longer than most sweet varieties.',
            'companion_plants': 'Basil, Tomatoes, Carrots, Spinach',
            'avoid_near': 'Fennel, Brassicas',
        },
        {
            'category': 'Cucumbers',
            'seed_indoor_start_doy': None,
            'direct_sow_start_doy': 135,
            'direct_sow_end_doy': 180,
            'transplant_start_doy': None,
            'transplant_end_doy': None,
            'days_to_harvest_min': 50,
            'days_to_harvest_max': 65,
            'succession_interval_days': 14,
            'frost_sensitive': True,
            'notes': 'Direct sow after soil reaches 60F. Can start indoors 3-4 weeks before transplanting. Provide trellis for better fruit and space efficiency.',
            'companion_plants': 'Beans, Corn, Peas, Radishes, Sunflowers',
            'avoid_near': 'Potatoes, Aromatic herbs',
        },
        {
            'category': 'Squash (Summer)',
            'seed_indoor_start_doy': None,
            'direct_sow_start_doy': 135,
            'direct_sow_end_doy': 180,
            'transplant_start_doy': None,
            'transplant_end_doy': None,
            'days_to_harvest_min': 45,
            'days_to_harvest_max': 55,
            'succession_interval_days': 21,
            'frost_sensitive': True,
            'notes': 'Direct sow after last frost when soil is warm. Harvest frequently when small for best flavor. Very productive - 2-3 plants feeds a family.',
            'companion_plants': 'Corn, Beans, Nasturtiums, Marigolds',
            'avoid_near': 'Potatoes',
        },
        {
            'category': 'Squash (Winter)',
            'seed_indoor_start_doy': None,
            'direct_sow_start_doy': 135,
            'direct_sow_end_doy': 160,
            'transplant_start_doy': None,
            'transplant_end_doy': None,
            'days_to_harvest_min': 85,
            'days_to_harvest_max': 110,
            'succession_interval_days': None,
            'frost_sensitive': True,
            'notes': 'Needs long warm season. Direct sow after frost. Cure in sun for 10 days after harvest for storage. Butternut, acorn, and spaghetti squash do well in Omaha.',
            'companion_plants': 'Corn, Beans, Nasturtiums',
            'avoid_near': 'Potatoes',
        },
        {
            'category': 'Herbs',
            'seed_indoor_start_doy': 60,
            'direct_sow_start_doy': 120,
            'direct_sow_end_doy': 180,
            'transplant_start_doy': 120,
            'transplant_end_doy': 150,
            'days_to_harvest_min': 30,
            'days_to_harvest_max': 60,
            'succession_interval_days': 21,
            'frost_sensitive': False,
            'notes': 'Many herbs (parsley, cilantro, dill) can be direct sown early. Basil is frost-sensitive - wait until after May 10. Perennial herbs (thyme, oregano, chives) overwinter well in Zone 5b.',
            'companion_plants': 'Most vegetables benefit from nearby herbs',
            'avoid_near': 'Varies by herb type',
        },
        {
            'category': 'Leafy Greens',
            'seed_indoor_start_doy': None,
            'direct_sow_start_doy': 90,
            'direct_sow_end_doy': 260,
            'transplant_start_doy': None,
            'transplant_end_doy': None,
            'days_to_harvest_min': 30,
            'days_to_harvest_max': 60,
            'succession_interval_days': 14,
            'frost_sensitive': False,
            'notes': 'Cool-season crop. Spring sowing: late March to late April. Fall sowing: mid-August to mid-September. Lettuce, spinach, kale, Swiss chard. Use shade cloth in summer heat.',
            'companion_plants': 'Carrots, Radishes, Strawberries, Chives',
            'avoid_near': 'Celery, Parsley (competition)',
        },
        {
            'category': 'Root Vegetables',
            'seed_indoor_start_doy': None,
            'direct_sow_start_doy': 100,
            'direct_sow_end_doy': 250,
            'transplant_start_doy': None,
            'transplant_end_doy': None,
            'days_to_harvest_min': 50,
            'days_to_harvest_max': 80,
            'succession_interval_days': 14,
            'frost_sensitive': False,
            'notes': 'Carrots, beets, radishes, turnips. Spring sowing: early April. Fall sowing: late July to early September. Radishes mature in 25-30 days. Carrots need loose, rock-free soil.',
            'companion_plants': 'Peas, Beans, Lettuce, Onions',
            'avoid_near': 'Dill (attracts carrot fly)',
        },
        {
            'category': 'Beans',
            'seed_indoor_start_doy': None,
            'direct_sow_start_doy': 135,
            'direct_sow_end_doy': 180,
            'transplant_start_doy': None,
            'transplant_end_doy': None,
            'days_to_harvest_min': 50,
            'days_to_harvest_max': 65,
            'succession_interval_days': 14,
            'frost_sensitive': True,
            'notes': 'Direct sow after last frost when soil is 60F+. Bush beans produce earlier; pole beans produce longer. Inoculate with rhizobia for best nitrogen fixation.',
            'companion_plants': 'Corn, Squash, Carrots, Cucumbers',
            'avoid_near': 'Onions, Garlic, Fennel',
        },
        {
            'category': 'Corn',
            'seed_indoor_start_doy': None,
            'direct_sow_start_doy': 130,
            'direct_sow_end_doy': 160,
            'transplant_start_doy': None,
            'transplant_end_doy': None,
            'days_to_harvest_min': 65,
            'days_to_harvest_max': 90,
            'succession_interval_days': 14,
            'frost_sensitive': True,
            'notes': 'Direct sow when soil is 60F+. Plant in blocks (at least 4 rows) for good pollination, not single rows. Sweet corn varieties do well in Nebraska.',
            'companion_plants': 'Beans, Squash, Peas, Cucumbers',
            'avoid_near': 'Tomatoes (corn earworm)',
        },
        {
            'category': 'Berries',
            'seed_indoor_start_doy': None,
            'direct_sow_start_doy': None,
            'direct_sow_end_doy': None,
            'transplant_start_doy': 100,
            'transplant_end_doy': 130,
            'days_to_harvest_min': 365,
            'days_to_harvest_max': 730,
            'succession_interval_days': None,
            'frost_sensitive': False,
            'notes': 'Perennials. Plant bare-root stock in early-mid April. Strawberries produce the first year (day-neutral) or second year (June-bearing). Raspberries and blackberries fruit in year 2+.',
            'companion_plants': 'Borage, Lettuce, Spinach, Thyme',
            'avoid_near': 'Tomatoes, Peppers, Eggplant (disease spread)',
        },
        {
            'category': 'Melons',
            'seed_indoor_start_doy': 75,
            'direct_sow_start_doy': None,
            'direct_sow_end_doy': None,
            'transplant_start_doy': 140,
            'transplant_end_doy': 155,
            'days_to_harvest_min': 75,
            'days_to_harvest_max': 95,
            'succession_interval_days': None,
            'frost_sensitive': True,
            'notes': 'Start indoors 4 weeks before transplanting. Needs warm soil (70F+) and long season. Use black plastic mulch to warm soil. Cantaloupe and watermelon both do well.',
            'companion_plants': 'Corn, Sunflowers, Nasturtiums',
            'avoid_near': 'Potatoes, Cucumbers (disease cross)',
        },
        {
            'category': 'Peas',
            'seed_indoor_start_doy': None,
            'direct_sow_start_doy': 80,
            'direct_sow_end_doy': 100,
            'transplant_start_doy': None,
            'transplant_end_doy': None,
            'days_to_harvest_min': 55,
            'days_to_harvest_max': 70,
            'succession_interval_days': 10,
            'frost_sensitive': False,
            'notes': 'Cool-season crop - plant as early as soil can be worked (late March). Peas tolerate light frost. Provide trellis. Can also plant fall crop in late August.',
            'companion_plants': 'Carrots, Radishes, Turnips, Corn',
            'avoid_near': 'Onions, Garlic',
        },
        {
            'category': 'Onions/Garlic',
            'seed_indoor_start_doy': 60,
            'direct_sow_start_doy': None,
            'direct_sow_end_doy': None,
            'transplant_start_doy': 100,
            'transplant_end_doy': 120,
            'days_to_harvest_min': 90,
            'days_to_harvest_max': 120,
            'succession_interval_days': None,
            'frost_sensitive': False,
            'notes': 'Onion sets or transplants go out in early-mid April. Garlic is planted in October for next summer harvest. Choose long-day onion varieties for Nebraska.',
            'companion_plants': 'Carrots, Beets, Lettuce, Tomatoes',
            'avoid_near': 'Beans, Peas',
        },
        {
            'category': 'Brassicas',
            'seed_indoor_start_doy': 45,
            'direct_sow_start_doy': None,
            'direct_sow_end_doy': None,
            'transplant_start_doy': 90,
            'transplant_end_doy': 230,
            'days_to_harvest_min': 55,
            'days_to_harvest_max': 85,
            'succession_interval_days': 14,
            'frost_sensitive': False,
            'notes': 'Cool-season. Spring: start indoors mid-Feb, transplant late March/April. Fall: start indoors mid-June, transplant late July/Aug. Includes broccoli, cabbage, cauliflower, Brussels sprouts, kale.',
            'companion_plants': 'Onions, Garlic, Dill, Celery, Potatoes',
            'avoid_near': 'Tomatoes, Peppers, Strawberries',
        },
        {
            'category': 'Other',
            'seed_indoor_start_doy': None,
            'direct_sow_start_doy': 120,
            'direct_sow_end_doy': 180,
            'transplant_start_doy': None,
            'transplant_end_doy': None,
            'days_to_harvest_min': 45,
            'days_to_harvest_max': 90,
            'succession_interval_days': None,
            'frost_sensitive': True,
            'notes': 'Varies by crop. Check specific variety requirements. Omaha Zone 5b last frost ~April 25, first frost ~October 10.',
            'companion_plants': 'Varies',
            'avoid_near': 'Varies',
        },
    ]

    for g in guides:
        db.session.add(PlantingGuide(zone='5b', **g))
    db.session.commit()


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def guide_to_dict(g):
    return {
        'id': g.id,
        'category': g.category,
        'zone': g.zone,
        'seed_indoor_start_doy': g.seed_indoor_start_doy,
        'direct_sow_start_doy': g.direct_sow_start_doy,
        'direct_sow_end_doy': g.direct_sow_end_doy,
        'transplant_start_doy': g.transplant_start_doy,
        'transplant_end_doy': g.transplant_end_doy,
        'days_to_harvest_min': g.days_to_harvest_min,
        'days_to_harvest_max': g.days_to_harvest_max,
        'succession_interval_days': g.succession_interval_days,
        'frost_sensitive': g.frost_sensitive,
        'notes': g.notes,
        'companion_plants': g.companion_plants,
        'avoid_near': g.avoid_near,
    }


def planting_to_dict(p):
    return {
        'id': p.id,
        'seller_id': p.seller_id,
        'seller_name': p.seller.display_name or p.seller.username,
        'category': p.category,
        'variety': p.variety,
        'planted_date': p.planted_date.isoformat() if p.planted_date else None,
        'estimated_harvest_start': p.estimated_harvest_start.isoformat() if p.estimated_harvest_start else None,
        'estimated_harvest_end': p.estimated_harvest_end.isoformat() if p.estimated_harvest_end else None,
        'quantity_estimate': p.quantity_estimate,
        'status': p.status,
        'allow_preorder': p.allow_preorder,
        'notes': p.notes,
        'created_at': p.created_at.isoformat() if p.created_at else None,
    }


def doy_to_month_day(doy):
    """Convert day-of-year (1-366) to (month, day) for a non-leap reference year."""
    if doy is None:
        return None
    d = date(2025, 1, 1) + timedelta(days=doy - 1)
    return {'month': d.month, 'day': d.day, 'label': d.strftime('%b %d')}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@planting_api.route('/guide', methods=['GET'])
def get_full_guide():
    """Get full planting guide (all categories for zone 5b)."""
    guides = PlantingGuide.query.filter_by(zone='5b').order_by(PlantingGuide.category).all()
    return jsonify([guide_to_dict(g) for g in guides])


@planting_api.route('/guide/<category>', methods=['GET'])
def get_category_guide(category):
    """Get guide for a specific category."""
    g = PlantingGuide.query.filter_by(category=category, zone='5b').first()
    if not g:
        return jsonify({'error': 'Category not found'}), 404
    return jsonify(guide_to_dict(g))


@planting_api.route('/calendar', methods=['GET'])
def get_calendar():
    """Get calendar view data: month-by-month activity for all categories."""
    guides = PlantingGuide.query.filter_by(zone='5b').order_by(PlantingGuide.category).all()
    result = []
    for g in guides:
        entry = {
            'category': g.category,
            'frost_sensitive': g.frost_sensitive,
            'activities': [],
        }
        # Indoor seeding window (single point, shown as ~2 week window)
        if g.seed_indoor_start_doy:
            entry['activities'].append({
                'type': 'indoor_seed',
                'label': 'Start Indoors',
                'start': doy_to_month_day(g.seed_indoor_start_doy),
                'end': doy_to_month_day(g.seed_indoor_start_doy + 14),
                'start_doy': g.seed_indoor_start_doy,
                'end_doy': g.seed_indoor_start_doy + 14,
            })
        # Direct sow window
        if g.direct_sow_start_doy and g.direct_sow_end_doy:
            entry['activities'].append({
                'type': 'direct_sow',
                'label': 'Direct Sow',
                'start': doy_to_month_day(g.direct_sow_start_doy),
                'end': doy_to_month_day(g.direct_sow_end_doy),
                'start_doy': g.direct_sow_start_doy,
                'end_doy': g.direct_sow_end_doy,
            })
        # Transplant window
        if g.transplant_start_doy and g.transplant_end_doy:
            entry['activities'].append({
                'type': 'transplant',
                'label': 'Transplant',
                'start': doy_to_month_day(g.transplant_start_doy),
                'end': doy_to_month_day(g.transplant_end_doy),
                'start_doy': g.transplant_start_doy,
                'end_doy': g.transplant_end_doy,
            })
        # Harvest window (calculated from transplant/sow end + days_to_harvest)
        harvest_ref_start = g.transplant_start_doy or g.direct_sow_start_doy
        harvest_ref_end = g.transplant_end_doy or g.direct_sow_end_doy
        if harvest_ref_start and g.days_to_harvest_min:
            h_start = harvest_ref_start + g.days_to_harvest_min
            h_end = (harvest_ref_end or harvest_ref_start) + g.days_to_harvest_max
            # Cap at first frost (day 283 = Oct 10)
            h_end = min(h_end, 283)
            entry['activities'].append({
                'type': 'harvest',
                'label': 'Harvest',
                'start': doy_to_month_day(h_start),
                'end': doy_to_month_day(h_end),
                'start_doy': h_start,
                'end_doy': h_end,
            })

        result.append(entry)
    return jsonify(result)


@planting_api.route('/forecast', methods=['GET'])
def get_forecast():
    """Harvest forecast: what's coming in next 8 weeks based on SellerPlantings."""
    today = date.today()
    end_date = today + timedelta(weeks=8)

    plantings = SellerPlanting.query.filter(
        SellerPlanting.status.in_(['planted', 'growing', 'harvesting']),
        SellerPlanting.estimated_harvest_start <= end_date,
        SellerPlanting.estimated_harvest_end >= today,
    ).all()

    # Aggregate by week and category
    weeks = []
    for w in range(8):
        week_start = today + timedelta(weeks=w)
        week_end = week_start + timedelta(days=6)
        week_data = {
            'week_start': week_start.isoformat(),
            'week_end': week_end.isoformat(),
            'week_label': f'{week_start.strftime("%b %d")} - {week_end.strftime("%b %d")}',
            'categories': {},
        }
        for p in plantings:
            if p.estimated_harvest_start and p.estimated_harvest_end:
                if p.estimated_harvest_start <= week_end and p.estimated_harvest_end >= week_start:
                    cat = p.category
                    if cat not in week_data['categories']:
                        week_data['categories'][cat] = {
                            'category': cat,
                            'seller_count': 0,
                            'sellers': set(),
                            'quantities': [],
                            'has_preorder': False,
                        }
                    week_data['categories'][cat]['sellers'].add(p.seller_id)
                    if p.quantity_estimate:
                        week_data['categories'][cat]['quantities'].append(p.quantity_estimate)
                    if p.allow_preorder:
                        week_data['categories'][cat]['has_preorder'] = True

        # Convert sets to counts for JSON serialization
        for cat in week_data['categories']:
            cat_data = week_data['categories'][cat]
            cat_data['seller_count'] = len(cat_data['sellers'])
            del cat_data['sellers']

        week_data['categories'] = list(week_data['categories'].values())
        weeks.append(week_data)

    return jsonify(weeks)


@planting_api.route('/my-plantings', methods=['GET'])
@login_required
def get_my_plantings():
    """Seller's planting log."""
    plantings = SellerPlanting.query.filter_by(seller_id=current_user.id)\
        .order_by(SellerPlanting.planted_date.desc()).all()
    return jsonify([planting_to_dict(p) for p in plantings])


@planting_api.route('/my-plantings', methods=['POST'])
@login_required
def create_planting():
    """Log a new planting. Auto-calculates estimated harvest dates from guide."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    category = data.get('category')
    variety = data.get('variety', '')
    planted_date_str = data.get('planted_date')
    quantity_estimate = data.get('quantity_estimate', '')
    allow_preorder = data.get('allow_preorder', False)
    notes = data.get('notes', '')

    if not category or not planted_date_str:
        return jsonify({'error': 'Category and planted_date are required'}), 400

    try:
        planted_date = date.fromisoformat(planted_date_str)
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

    # Auto-calculate harvest window from guide
    guide = PlantingGuide.query.filter_by(category=category, zone='5b').first()
    estimated_harvest_start = None
    estimated_harvest_end = None
    if guide and guide.days_to_harvest_min:
        estimated_harvest_start = planted_date + timedelta(days=guide.days_to_harvest_min)
        estimated_harvest_end = planted_date + timedelta(days=guide.days_to_harvest_max)

    planting = SellerPlanting(
        seller_id=current_user.id,
        category=category,
        variety=variety,
        planted_date=planted_date,
        estimated_harvest_start=estimated_harvest_start,
        estimated_harvest_end=estimated_harvest_end,
        quantity_estimate=quantity_estimate,
        allow_preorder=allow_preorder,
        notes=notes,
        status='planted',
    )
    db.session.add(planting)
    db.session.commit()

    return jsonify(planting_to_dict(planting)), 201


@planting_api.route('/my-plantings/<int:id>', methods=['PUT'])
@login_required
def update_planting(id):
    """Update planting status or details."""
    planting = SellerPlanting.query.get_or_404(id)
    if planting.seller_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    if 'status' in data:
        if data['status'] in ('planted', 'growing', 'harvesting', 'done'):
            planting.status = data['status']
    if 'variety' in data:
        planting.variety = data['variety']
    if 'quantity_estimate' in data:
        planting.quantity_estimate = data['quantity_estimate']
    if 'allow_preorder' in data:
        planting.allow_preorder = data['allow_preorder']
    if 'notes' in data:
        planting.notes = data['notes']
    if 'estimated_harvest_start' in data and data['estimated_harvest_start']:
        try:
            planting.estimated_harvest_start = date.fromisoformat(data['estimated_harvest_start'])
        except ValueError:
            pass
    if 'estimated_harvest_end' in data and data['estimated_harvest_end']:
        try:
            planting.estimated_harvest_end = date.fromisoformat(data['estimated_harvest_end'])
        except ValueError:
            pass

    db.session.commit()
    return jsonify(planting_to_dict(planting))


@planting_api.route('/my-plantings/<int:id>', methods=['DELETE'])
@login_required
def delete_planting(id):
    """Remove a planting."""
    planting = SellerPlanting.query.get_or_404(id)
    if planting.seller_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403

    db.session.delete(planting)
    db.session.commit()
    return jsonify({'message': 'Planting deleted'})


@planting_api.route('/preorders', methods=['GET'])
def get_preorders():
    """Browse items available for pre-order."""
    today = date.today()
    plantings = SellerPlanting.query.filter(
        SellerPlanting.allow_preorder == True,
        SellerPlanting.status.in_(['planted', 'growing']),
        SellerPlanting.estimated_harvest_start != None,
        SellerPlanting.estimated_harvest_start >= today,
    ).order_by(SellerPlanting.estimated_harvest_start).all()

    return jsonify([planting_to_dict(p) for p in plantings])
