"""Subscription Plans REST API endpoints."""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import SubscriptionPlan, Subscription, BoxPreview
from datetime import datetime, timezone

subscriptions_api = Blueprint('subscriptions_api', __name__, url_prefix='/api/subscriptions')


def plan_to_dict(plan):
    return {
        'id': plan.id,
        'seller_id': plan.seller_id,
        'seller_name': plan.seller.display_name or plan.seller.username,
        'seller_username': plan.seller.username,
        'seller_image': plan.seller.profile_image,
        'seller_rating': plan.seller.avg_rating,
        'seller_review_count': plan.seller.review_count,
        'title': plan.title,
        'description': plan.description,
        'price': plan.price,
        'frequency': plan.frequency,
        'fulfillment_day': plan.fulfillment_day,
        'season_start': plan.season_start.isoformat() if plan.season_start else None,
        'season_end': plan.season_end.isoformat() if plan.season_end else None,
        'max_subscribers': plan.max_subscribers,
        'is_active': plan.is_active,
        'photo_url': plan.photo_url,
        'box_size': plan.box_size,
        'includes_delivery': plan.includes_delivery,
        'delivery_radius_miles': plan.delivery_radius_miles,
        'subscriber_count': plan.subscriptions.filter(
            Subscription.status.in_(['active', 'paused'])
        ).count(),
        'created_at': plan.created_at.isoformat() if plan.created_at else None,
    }


def subscription_to_dict(sub):
    return {
        'id': sub.id,
        'plan_id': sub.plan_id,
        'buyer_id': sub.buyer_id,
        'status': sub.status,
        'dietary_notes': sub.dietary_notes,
        'substitution_pref': sub.substitution_pref,
        'delivery_preference': sub.delivery_preference,
        'created_at': sub.created_at.isoformat() if sub.created_at else None,
        'paused_at': sub.paused_at.isoformat() if sub.paused_at else None,
        'cancelled_at': sub.cancelled_at.isoformat() if sub.cancelled_at else None,
        'plan': plan_to_dict(sub.plan),
    }


def preview_to_dict(preview):
    return {
        'id': preview.id,
        'plan_id': preview.plan_id,
        'week_of': preview.week_of.isoformat() if preview.week_of else None,
        'items_description': preview.items_description,
        'photo_url': preview.photo_url,
        'is_published': preview.is_published,
        'created_at': preview.created_at.isoformat() if preview.created_at else None,
    }


# ---- Browse Plans ----

@subscriptions_api.route('/plans', methods=['GET'])
def browse_plans():
    page = request.args.get('page', 1, type=int)
    per_page = 12
    frequency = request.args.get('frequency', '')
    box_size = request.args.get('box_size', '')
    delivery = request.args.get('delivery', '')
    sort = request.args.get('sort', 'newest')

    q = SubscriptionPlan.query.filter_by(is_active=True)

    if frequency:
        q = q.filter_by(frequency=frequency)
    if box_size:
        q = q.filter_by(box_size=box_size)
    if delivery and delivery.lower() == 'true':
        q = q.filter_by(includes_delivery=True)

    if sort == 'price_asc':
        q = q.order_by(SubscriptionPlan.price.asc())
    elif sort == 'price_desc':
        q = q.order_by(SubscriptionPlan.price.desc())
    elif sort == 'popular':
        # Sort by subscriber count handled after query
        pass
    else:
        q = q.order_by(SubscriptionPlan.created_at.desc())

    if sort == 'popular':
        plans = q.all()
        plans.sort(key=lambda p: p.subscriptions.filter(
            Subscription.status.in_(['active', 'paused'])
        ).count(), reverse=True)
        total = len(plans)
        start = (page - 1) * per_page
        paged = plans[start:start + per_page]
        return jsonify({
            'plans': [plan_to_dict(p) for p in paged],
            'total': total,
            'pages': (total + per_page - 1) // per_page,
            'page': page,
            'has_next': start + per_page < total,
            'has_prev': page > 1,
        })

    pagination = q.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        'plans': [plan_to_dict(p) for p in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'page': pagination.page,
        'has_next': pagination.has_next,
        'has_prev': pagination.has_prev,
    })


@subscriptions_api.route('/plans/<int:plan_id>', methods=['GET'])
def plan_detail(plan_id):
    plan = SubscriptionPlan.query.get_or_404(plan_id)
    data = plan_to_dict(plan)
    # Include recent previews
    recent_previews = plan.previews.filter_by(is_published=True).limit(5).all()
    data['recent_previews'] = [preview_to_dict(p) for p in recent_previews]
    # Check if current user is subscribed
    data['user_subscription'] = None
    if current_user.is_authenticated:
        existing = Subscription.query.filter_by(
            plan_id=plan_id, buyer_id=current_user.id
        ).filter(Subscription.status.in_(['active', 'paused'])).first()
        if existing:
            data['user_subscription'] = subscription_to_dict(existing)
    return jsonify(data)


# ---- Create / Update / Delete Plans ----

@subscriptions_api.route('/plans', methods=['POST'])
@login_required
def create_plan():
    if not current_user.can_sell():
        return jsonify({'error': 'Seller account required'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    title = data.get('title', '').strip()
    price = data.get('price')
    if not title or price is None:
        return jsonify({'error': 'Title and price are required'}), 400

    plan = SubscriptionPlan(
        seller_id=current_user.id,
        title=title,
        description=data.get('description', ''),
        price=float(price),
        frequency=data.get('frequency', 'weekly'),
        fulfillment_day=data.get('fulfillment_day', 'saturday'),
        max_subscribers=int(data.get('max_subscribers', 20)),
        photo_url=data.get('photo_url', ''),
        box_size=data.get('box_size', 'medium'),
        includes_delivery=bool(data.get('includes_delivery', False)),
        delivery_radius_miles=float(data.get('delivery_radius_miles', 10.0)),
    )

    season_start = data.get('season_start')
    season_end = data.get('season_end')
    if season_start:
        plan.season_start = datetime.strptime(season_start, '%Y-%m-%d').date()
    if season_end:
        plan.season_end = datetime.strptime(season_end, '%Y-%m-%d').date()

    db.session.add(plan)
    db.session.commit()
    return jsonify(plan_to_dict(plan)), 201


@subscriptions_api.route('/plans/<int:plan_id>', methods=['PUT'])
@login_required
def update_plan(plan_id):
    plan = SubscriptionPlan.query.get_or_404(plan_id)
    if plan.seller_id != current_user.id:
        return jsonify({'error': 'Not authorized'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    plan.title = data.get('title', plan.title)
    plan.description = data.get('description', plan.description)
    plan.price = float(data.get('price', plan.price))
    plan.frequency = data.get('frequency', plan.frequency)
    plan.fulfillment_day = data.get('fulfillment_day', plan.fulfillment_day)
    plan.max_subscribers = int(data.get('max_subscribers', plan.max_subscribers))
    plan.photo_url = data.get('photo_url', plan.photo_url)
    plan.box_size = data.get('box_size', plan.box_size)
    plan.includes_delivery = bool(data.get('includes_delivery', plan.includes_delivery))
    plan.delivery_radius_miles = float(data.get('delivery_radius_miles', plan.delivery_radius_miles))

    season_start = data.get('season_start')
    season_end = data.get('season_end')
    if season_start:
        plan.season_start = datetime.strptime(season_start, '%Y-%m-%d').date()
    if season_end:
        plan.season_end = datetime.strptime(season_end, '%Y-%m-%d').date()

    db.session.commit()
    return jsonify(plan_to_dict(plan))


@subscriptions_api.route('/plans/<int:plan_id>', methods=['DELETE'])
@login_required
def deactivate_plan(plan_id):
    plan = SubscriptionPlan.query.get_or_404(plan_id)
    if plan.seller_id != current_user.id:
        return jsonify({'error': 'Not authorized'}), 403
    plan.is_active = False
    db.session.commit()
    return jsonify({'message': 'Plan deactivated'})


# ---- Box Previews ----

@subscriptions_api.route('/plans/<int:plan_id>/previews', methods=['GET'])
def plan_previews(plan_id):
    plan = SubscriptionPlan.query.get_or_404(plan_id)
    previews = plan.previews.filter_by(is_published=True).all()
    return jsonify([preview_to_dict(p) for p in previews])


@subscriptions_api.route('/plans/<int:plan_id>/previews', methods=['POST'])
@login_required
def create_preview(plan_id):
    plan = SubscriptionPlan.query.get_or_404(plan_id)
    if plan.seller_id != current_user.id:
        return jsonify({'error': 'Not authorized'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    week_of = data.get('week_of')
    if not week_of:
        return jsonify({'error': 'week_of date is required'}), 400

    preview = BoxPreview(
        plan_id=plan_id,
        week_of=datetime.strptime(week_of, '%Y-%m-%d').date(),
        items_description=data.get('items_description', ''),
        photo_url=data.get('photo_url', ''),
        is_published=bool(data.get('is_published', False)),
    )
    db.session.add(preview)
    db.session.commit()
    return jsonify(preview_to_dict(preview)), 201


# ---- Subscribe / Manage Subscriptions ----

@subscriptions_api.route('/plans/<int:plan_id>/subscribe', methods=['POST'])
@login_required
def subscribe(plan_id):
    plan = SubscriptionPlan.query.get_or_404(plan_id)
    if not plan.is_active:
        return jsonify({'error': 'This plan is no longer active'}), 400

    # Check capacity
    active_count = plan.subscriptions.filter(
        Subscription.status.in_(['active', 'paused'])
    ).count()
    if active_count >= plan.max_subscribers:
        return jsonify({'error': 'This plan is full'}), 400

    # Check if already subscribed
    existing = Subscription.query.filter_by(
        plan_id=plan_id, buyer_id=current_user.id
    ).filter(Subscription.status.in_(['active', 'paused'])).first()
    if existing:
        return jsonify({'error': 'You are already subscribed to this plan'}), 400

    data = request.get_json() or {}
    sub = Subscription(
        plan_id=plan_id,
        buyer_id=current_user.id,
        dietary_notes=data.get('dietary_notes', ''),
        substitution_pref=data.get('substitution_pref', 'seller_choice'),
        delivery_preference=data.get('delivery_preference', 'pickup'),
    )
    db.session.add(sub)
    db.session.commit()
    return jsonify(subscription_to_dict(sub)), 201


@subscriptions_api.route('/mine', methods=['GET'])
@login_required
def my_subscriptions():
    subs = Subscription.query.filter_by(buyer_id=current_user.id).order_by(
        Subscription.created_at.desc()
    ).all()
    return jsonify([subscription_to_dict(s) for s in subs])


@subscriptions_api.route('/my-plans', methods=['GET'])
@login_required
def my_plans():
    if not current_user.can_sell():
        return jsonify({'error': 'Seller account required'}), 403
    plans = SubscriptionPlan.query.filter_by(seller_id=current_user.id).order_by(
        SubscriptionPlan.created_at.desc()
    ).all()
    result = []
    for plan in plans:
        d = plan_to_dict(plan)
        # Include all subscribers for seller dashboard
        active_subs = plan.subscriptions.filter(
            Subscription.status.in_(['active', 'paused'])
        ).all()
        d['active_subscribers'] = [{
            'id': s.id,
            'buyer_name': s.buyer.display_name or s.buyer.username,
            'status': s.status,
            'dietary_notes': s.dietary_notes,
            'substitution_pref': s.substitution_pref,
            'delivery_preference': s.delivery_preference,
        } for s in active_subs]
        result.append(d)
    return jsonify(result)


@subscriptions_api.route('/<int:sub_id>/pause', methods=['PUT'])
@login_required
def pause_subscription(sub_id):
    sub = Subscription.query.get_or_404(sub_id)
    if sub.buyer_id != current_user.id:
        return jsonify({'error': 'Not authorized'}), 403
    if sub.status != 'active':
        return jsonify({'error': 'Can only pause active subscriptions'}), 400
    sub.status = 'paused'
    sub.paused_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(subscription_to_dict(sub))


@subscriptions_api.route('/<int:sub_id>/resume', methods=['PUT'])
@login_required
def resume_subscription(sub_id):
    sub = Subscription.query.get_or_404(sub_id)
    if sub.buyer_id != current_user.id:
        return jsonify({'error': 'Not authorized'}), 403
    if sub.status != 'paused':
        return jsonify({'error': 'Can only resume paused subscriptions'}), 400
    sub.status = 'active'
    sub.paused_at = None
    db.session.commit()
    return jsonify(subscription_to_dict(sub))


@subscriptions_api.route('/<int:sub_id>/cancel', methods=['PUT'])
@login_required
def cancel_subscription(sub_id):
    sub = Subscription.query.get_or_404(sub_id)
    if sub.buyer_id != current_user.id:
        return jsonify({'error': 'Not authorized'}), 403
    if sub.status == 'cancelled':
        return jsonify({'error': 'Already cancelled'}), 400
    sub.status = 'cancelled'
    sub.cancelled_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(subscription_to_dict(sub))
