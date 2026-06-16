"""Planting Calendar & Harvest Forecasting REST API endpoints."""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.api.token_auth import token_or_session, get_current_user
from app import db
from app.models import PlantingGuide, SellerPlanting, User, Listing, HarvestInterest
from datetime import datetime, date, timedelta
import re
import logging

log = logging.getLogger(__name__)

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

    try:
        for g in guides:
            db.session.add(PlantingGuide(zone='5b', **g))
        db.session.commit()
    except Exception:
        db.session.rollback()


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
        'linked_listing_id': p.linked_listing_id,
        'auto_list_on_harvest': p.auto_list_on_harvest or False,
        'weight_lbs': p.weight_lbs,
        'sale_price': p.sale_price,
        'price_unit': p.price_unit or 'lb',
        'created_at': p.created_at.isoformat() if p.created_at else None,
    }


# Category mapping from planting categories to listing vegetable_types
PLANTING_TO_LISTING_CATEGORY = {
    'Tomatoes': 'Tomatoes',
    'Peppers (Hot)': 'Peppers',
    'Peppers (Sweet)': 'Peppers',
    'Cucumbers': 'Cucumbers',
    'Squash (Summer)': 'Squash',
    'Squash (Winter)': 'Squash',
    'Herbs': 'Herbs',
    'Leafy Greens': 'Greens',
    'Root Vegetables': 'Root Vegetables',
    'Beans': 'Beans',
    'Corn': 'Corn',
    'Berries': 'Berries',
    'Melons': 'Melons',
    'Peas': 'Peas',
    'Onions/Garlic': 'Onions',
    'Brassicas': 'Greens',
    'Other': 'Other',
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
@token_or_session
def get_my_plantings():
    """Seller's planting log."""
    plantings = SellerPlanting.query.filter_by(seller_id=get_current_user().id)\
        .order_by(SellerPlanting.planted_date.desc()).all()
    return jsonify([planting_to_dict(p) for p in plantings])


@planting_api.route('/my-plantings', methods=['POST'])
@token_or_session
def create_planting():
    """Log a new planting. Auto-calculates estimated harvest dates from guide."""
    if not get_current_user().can_sell():
        return jsonify({'error': 'Seller account required to log plantings'}), 403
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
        seller_id=get_current_user().id,
        category=category,
        variety=variety,
        planted_date=planted_date,
        estimated_harvest_start=estimated_harvest_start,
        estimated_harvest_end=estimated_harvest_end,
        quantity_estimate=quantity_estimate,
        allow_preorder=allow_preorder,
        auto_list_on_harvest=data.get('auto_list_on_harvest', False),
        notes=notes,
        status='planted',
        weight_lbs=float(data['weight_lbs']) if data.get('weight_lbs') else None,
        sale_price=float(data['sale_price']) if data.get('sale_price') else None,
        price_unit=data.get('price_unit', 'lb') or 'lb',
    )
    db.session.add(planting)
    db.session.commit()

    return jsonify(planting_to_dict(planting)), 201


@planting_api.route('/my-plantings/<int:id>', methods=['PUT'])
@token_or_session
def update_planting(id):
    """Update planting status or details."""
    planting = db.get_or_404(SellerPlanting, id)
    if planting.seller_id != get_current_user().id:
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    old_status = planting.status

    if 'status' in data:
        if data['status'] in ('planted', 'growing', 'harvesting', 'done'):
            planting.status = data['status']
    if 'variety' in data:
        planting.variety = data['variety']
    if 'quantity_estimate' in data:
        planting.quantity_estimate = data['quantity_estimate']
    if 'allow_preorder' in data:
        planting.allow_preorder = data['allow_preorder']
    if 'auto_list_on_harvest' in data:
        planting.auto_list_on_harvest = bool(data['auto_list_on_harvest'])
    if 'notes' in data:
        planting.notes = data['notes']
    if 'weight_lbs' in data:
        planting.weight_lbs = float(data['weight_lbs']) if data['weight_lbs'] else None
    if 'sale_price' in data:
        planting.sale_price = float(data['sale_price']) if data['sale_price'] else None
    if 'price_unit' in data:
        planting.price_unit = data['price_unit'] or 'lb'
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

    # Auto-create listing when status changes to 'harvesting' and auto_list is on
    if (planting.status == 'harvesting' and old_status != 'harvesting'
            and planting.auto_list_on_harvest and not planting.linked_listing_id):
        listing = _create_listing_from_planting(planting)
        if listing:
            planting.linked_listing_id = listing.id

    # Harvest notifications — notify interested users when status becomes 'harvesting'
    if planting.status == 'harvesting' and old_status != 'harvesting':
        _send_harvest_notifications(planting)

    db.session.commit()
    return jsonify(planting_to_dict(planting))


@planting_api.route('/my-plantings/<int:id>', methods=['DELETE'])
@token_or_session
def delete_planting(id):
    """Remove a planting."""
    planting = db.get_or_404(SellerPlanting, id)
    if planting.seller_id != get_current_user().id:
        return jsonify({'error': 'Access denied'}), 403

    db.session.delete(planting)
    db.session.commit()
    return jsonify({'message': 'Planting deleted'})


# ---------------------------------------------------------------------------
# Harvest Interest / Notification Subscriptions
# ---------------------------------------------------------------------------

@planting_api.route('/harvest-interests', methods=['GET'])
@token_or_session
def get_harvest_interests():
    """Get current user's harvest notification subscriptions."""
    user = get_current_user()
    interests = HarvestInterest.query.filter_by(user_id=user.id).all()
    return jsonify([{
        'category': i.category,
        'notify_email': i.notify_email,
        'notify_sms': i.notify_sms,
    } for i in interests])


@planting_api.route('/harvest-interests', methods=['POST'])
@token_or_session
def subscribe_harvest_interest():
    """Subscribe to harvest notifications for a crop category."""
    user = get_current_user()
    data = request.get_json()
    category = (data.get('category') or '').strip()
    if not category:
        return jsonify({'error': 'Category required'}), 400

    existing = HarvestInterest.query.filter_by(user_id=user.id, category=category).first()
    if existing:
        return jsonify({'error': 'Already subscribed'}), 409

    interest = HarvestInterest(
        user_id=user.id,
        category=category,
        notify_email=data.get('notify_email', True),
        notify_sms=data.get('notify_sms', bool(getattr(user, 'sms_opt_in', False) and getattr(user, 'phone_number', None))),
    )
    db.session.add(interest)
    db.session.commit()
    return jsonify({
        'category': category,
        'notify_email': interest.notify_email,
        'notify_sms': interest.notify_sms,
    }), 201


@planting_api.route('/harvest-interests/<path:category>', methods=['DELETE'])
@token_or_session
def unsubscribe_harvest_interest(category):
    """Unsubscribe from harvest notifications for a crop category."""
    user = get_current_user()
    interest = HarvestInterest.query.filter_by(user_id=user.id, category=category).first()
    if not interest:
        return jsonify({'error': 'Not subscribed'}), 404
    db.session.delete(interest)
    db.session.commit()
    return jsonify({'removed': category})


def _send_harvest_notifications(planting):
    """Notify all users interested in this category that harvests are starting."""
    try:
        from app.api.notifications_api import notify
        from app.email_service import send_harvest_notification
        from app.sms_service import send_harvest_sms

        interests = HarvestInterest.query.filter_by(category=planting.category).filter(
            HarvestInterest.user_id != planting.seller_id
        ).all()

        for interest in interests:
            user = interest.user
            # In-app notification
            try:
                notify(
                    user_id=user.id,
                    type='harvest_ready',
                    title=f'{planting.category} harvest starting!',
                    body=f'A grower in your community has started harvesting {planting.category}.',
                    link='/harvest-forecast',
                )
            except Exception:
                pass  # Don't fail the whole update for notification issues

            # Email notification
            if interest.notify_email:
                grower_count = db.session.query(
                    db.func.count(db.distinct(SellerPlanting.seller_id))
                ).filter(
                    SellerPlanting.category == planting.category,
                    SellerPlanting.status == 'harvesting',
                ).scalar() or 1
                try:
                    send_harvest_notification(user.email, planting.category, grower_count)
                except Exception:
                    pass

            # SMS notification
            if interest.notify_sms and getattr(user, 'sms_opt_in', False) and getattr(user, 'phone_number', None):
                try:
                    send_harvest_sms(user.phone_number, planting.category)
                except Exception:
                    pass
    except Exception as e:
        log.error('Harvest notification error: %s', e)


DEFAULT_PRICES = {
    'Tomatoes': (2.50, 4.00, 'lb'), 'Peppers (Hot)': (3.00, 6.00, 'lb'),
    'Peppers (Sweet)': (2.50, 4.50, 'lb'), 'Cucumbers': (1.00, 2.50, 'each'),
    'Squash (Summer)': (1.50, 3.00, 'lb'), 'Squash (Winter)': (2.00, 4.00, 'each'),
    'Herbs': (2.00, 4.00, 'bunch'), 'Leafy Greens': (3.00, 5.00, 'lb'),
    'Root Vegetables': (2.00, 3.50, 'lb'), 'Beans': (3.00, 5.00, 'lb'),
    'Corn': (0.50, 1.00, 'each'), 'Berries': (4.00, 8.00, 'pint'),
    'Melons': (3.00, 6.00, 'each'), 'Peas': (3.00, 5.00, 'lb'),
    'Onions/Garlic': (1.50, 3.00, 'lb'), 'Brassicas': (2.00, 4.00, 'lb'),
}


@planting_api.route('/price-guide', methods=['GET'])
def price_guide():
    """Get recommended pricing for a crop category based on recent sales."""
    category = request.args.get('category', '')
    if not category:
        return jsonify({'error': 'category parameter required'}), 400

    # Map planting category to listing category
    listing_cat = PLANTING_TO_LISTING_CATEGORY.get(category, category)

    # Query recent completed listing prices for this category
    from sqlalchemy import func as sqlfunc
    results = db.session.query(
        sqlfunc.avg(Listing.price),
        sqlfunc.min(Listing.price),
        sqlfunc.max(Listing.price),
        sqlfunc.count(Listing.id),
    ).filter(
        Listing.vegetable_type == listing_cat,
        Listing.price > 0,
    ).first()

    avg_price, low_price, high_price, sample_size = results
    if sample_size and sample_size >= 3:
        return jsonify({
            'avg_price': round(avg_price, 2),
            'low_price': round(low_price, 2),
            'high_price': round(high_price, 2),
            'unit': 'lb',
            'sample_size': sample_size,
            'source': 'marketplace',
        })

    # Fallback to defaults
    defaults = DEFAULT_PRICES.get(category, (2.00, 5.00, 'lb'))
    return jsonify({
        'avg_price': round((defaults[0] + defaults[1]) / 2, 2),
        'low_price': defaults[0],
        'high_price': defaults[1],
        'unit': defaults[2],
        'sample_size': 0,
        'source': 'default',
    })


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


def _parse_quantity(quantity_estimate):
    """Extract a numeric quantity from estimate string like '10 lbs' or '20-30 each'."""
    if not quantity_estimate:
        return 1
    numbers = re.findall(r'\d+', str(quantity_estimate))
    if numbers:
        return max(1, int(numbers[0]))
    return 1


def _create_listing_from_planting(planting):
    """Create a Listing from a SellerPlanting's data.
    If sale_price is set, listing is created as active (ready to sell).
    Otherwise, it's a draft requiring the seller to set a price.
    """
    category = PLANTING_TO_LISTING_CATEGORY.get(planting.category, 'Other')
    title = f"Fresh {planting.variety or planting.category}"
    # Use weight_lbs if available, otherwise parse from quantity_estimate
    quantity = int(planting.weight_lbs) if planting.weight_lbs else _parse_quantity(planting.quantity_estimate)
    desc = f"Home-grown {planting.variety or planting.category}."
    if planting.notes:
        desc += f" {planting.notes}"

    has_price = planting.sale_price and planting.sale_price > 0

    listing = Listing(
        seller_id=planting.seller_id,
        title=title,
        description=desc,
        vegetable_type=category,
        price=planting.sale_price if has_price else 0.0,
        unit=planting.price_unit or 'lb',
        quantity_available=max(1, quantity),
        is_active=has_price,  # Auto-activate if price is set
    )
    db.session.add(listing)
    db.session.flush()
    return listing


@planting_api.route('/my-plantings/<int:id>/create-listing', methods=['POST'])
@token_or_session
def create_listing_from_planting(id):
    """Create a marketplace listing from a planting log entry."""
    planting = db.get_or_404(SellerPlanting, id)
    if planting.seller_id != get_current_user().id:
        return jsonify({'error': 'Access denied'}), 403

    if planting.linked_listing_id:
        return jsonify({'error': 'This planting already has a linked listing'}), 400

    listing = _create_listing_from_planting(planting)
    planting.linked_listing_id = listing.id
    db.session.commit()

    return jsonify({
        'message': 'Listing created! Set your price and activate it.',
        'listing_id': listing.id,
        'planting': planting_to_dict(planting),
    }), 201
