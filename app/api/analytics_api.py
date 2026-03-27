"""First-party analytics API — event ingestion and admin dashboard data."""
import json
import logging
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify
from flask_login import current_user
from app.api.token_auth import token_or_session, get_current_user
from app import db, limiter
from app.models import AnalyticsEvent, SiteEmailConfig
from app.helpers import admin_required
from sqlalchemy import func, distinct, desc, text

log = logging.getLogger(__name__)

analytics_api = Blueprint('analytics_api', __name__)

ALLOWED_EVENTS = {
    'page_view', 'listing_view', 'garden_view', 'search',
    'add_to_cart', 'checkout_start', 'checkout_complete',
    'register_start', 'register_complete',
    'plot_reserve', 'plot_confirmed',
    'login', 'message_sent',
}


def _analytics_enabled():
    config = SiteEmailConfig.query.first()
    return getattr(config, 'analytics_enabled', True) if config else True


def _period_start(period):
    now = datetime.now(timezone.utc)
    if period == 'day':
        return now - timedelta(days=1)
    elif period == 'week':
        return now - timedelta(weeks=1)
    elif period == 'month':
        return now - timedelta(days=30)
    elif period == 'quarter':
        return now - timedelta(days=90)
    elif period == 'year':
        return now - timedelta(days=365)
    return datetime(2020, 1, 1, tzinfo=timezone.utc)


# ==================== Public: Event Ingestion ====================

@analytics_api.route('/api/analytics/event', methods=['POST'])
@limiter.limit("60 per minute")
def record_event():
    """Record an analytics event. Only works if analytics is enabled and user consented."""
    if not _analytics_enabled():
        return jsonify({'ok': True, 'tracked': False}), 200

    data = request.get_json() or {}
    event_type = data.get('event_type', '')
    if event_type not in ALLOWED_EVENTS:
        return jsonify({'ok': True, 'tracked': False}), 200

    session_id = data.get('session_id', '')
    if not session_id or len(session_id) > 64:
        return jsonify({'ok': True, 'tracked': False}), 200

    # Determine user_id if authenticated
    user_id = None
    try:
        if current_user and current_user.is_authenticated:
            user_id = current_user.id
    except Exception:
        pass

    metadata = data.get('metadata')
    metadata_str = json.dumps(metadata) if metadata else None

    event = AnalyticsEvent(
        session_id=session_id[:64],
        user_id=user_id,
        event_type=event_type,
        page_url=(data.get('page_url', '') or '')[:500],
        referrer=(data.get('referrer', '') or '')[:500],
        metadata_json=metadata_str,
        device_type=(data.get('device_type', '') or '')[:20],
    )
    db.session.add(event)
    db.session.commit()

    return jsonify({'ok': True, 'tracked': True}), 201


# ==================== Public: Consent Config ====================

@analytics_api.route('/api/analytics/config', methods=['GET'])
def get_analytics_config():
    """Public endpoint — returns whether consent is required and analytics is enabled."""
    config = SiteEmailConfig.query.first()
    return jsonify({
        'analytics_enabled': getattr(config, 'analytics_enabled', True) if config else True,
        'cookie_consent_required': getattr(config, 'cookie_consent_required', True) if config else True,
    })


# ==================== Admin: Analytics Dashboard ====================

@analytics_api.route('/api/admin/analytics/overview', methods=['GET'])
@token_or_session
@admin_required
def analytics_overview():
    """Dashboard overview — KPIs, top pages, top referrers, device breakdown."""
    period = request.args.get('period', 'month')
    since = _period_start(period)

    base = AnalyticsEvent.query.filter(AnalyticsEvent.created_at >= since)

    # KPIs
    total_events = base.count()
    page_views = base.filter_by(event_type='page_view').count()
    unique_sessions = db.session.query(
        func.count(distinct(AnalyticsEvent.session_id))
    ).filter(AnalyticsEvent.created_at >= since).scalar() or 0
    unique_users = db.session.query(
        func.count(distinct(AnalyticsEvent.user_id))
    ).filter(
        AnalyticsEvent.created_at >= since,
        AnalyticsEvent.user_id.isnot(None)
    ).scalar() or 0

    # Bounce rate (sessions with only 1 page view)
    session_counts = db.session.query(
        AnalyticsEvent.session_id,
        func.count(AnalyticsEvent.id).label('cnt')
    ).filter(
        AnalyticsEvent.created_at >= since,
        AnalyticsEvent.event_type == 'page_view'
    ).group_by(AnalyticsEvent.session_id).subquery()

    total_sessions_with_pv = db.session.query(func.count()).select_from(session_counts).scalar() or 0
    bounce_sessions = db.session.query(func.count()).select_from(session_counts).filter(
        session_counts.c.cnt == 1
    ).scalar() or 0
    bounce_rate = round(bounce_sessions / total_sessions_with_pv * 100, 1) if total_sessions_with_pv > 0 else 0

    # Top pages
    top_pages = db.session.query(
        AnalyticsEvent.page_url,
        func.count(AnalyticsEvent.id).label('views'),
        func.count(distinct(AnalyticsEvent.session_id)).label('unique_visitors')
    ).filter(
        AnalyticsEvent.created_at >= since,
        AnalyticsEvent.event_type == 'page_view',
        AnalyticsEvent.page_url.isnot(None)
    ).group_by(AnalyticsEvent.page_url).order_by(desc('views')).limit(15).all()

    # Top referrers
    top_referrers = db.session.query(
        AnalyticsEvent.referrer,
        func.count(AnalyticsEvent.id).label('visits')
    ).filter(
        AnalyticsEvent.created_at >= since,
        AnalyticsEvent.event_type == 'page_view',
        AnalyticsEvent.referrer.isnot(None),
        AnalyticsEvent.referrer != ''
    ).group_by(AnalyticsEvent.referrer).order_by(desc('visits')).limit(10).all()

    # Device breakdown
    devices = db.session.query(
        AnalyticsEvent.device_type,
        func.count(distinct(AnalyticsEvent.session_id)).label('sessions')
    ).filter(
        AnalyticsEvent.created_at >= since,
        AnalyticsEvent.device_type.isnot(None),
        AnalyticsEvent.device_type != ''
    ).group_by(AnalyticsEvent.device_type).all()

    return jsonify({
        'period': period,
        'kpis': {
            'total_events': total_events,
            'page_views': page_views,
            'unique_sessions': unique_sessions,
            'unique_users': unique_users,
            'bounce_rate': bounce_rate,
        },
        'top_pages': [{'url': p[0], 'views': p[1], 'unique_visitors': p[2]} for p in top_pages],
        'top_referrers': [{'referrer': r[0], 'visits': r[1]} for r in top_referrers],
        'devices': {d[0]: d[1] for d in devices},
    })


@analytics_api.route('/api/admin/analytics/funnel', methods=['GET'])
@token_or_session
@admin_required
def analytics_funnel():
    """Conversion funnel data — marketplace, garden, registration."""
    period = request.args.get('period', 'month')
    since = _period_start(period)

    def count_event(event_type):
        return db.session.query(
            func.count(distinct(AnalyticsEvent.session_id))
        ).filter(
            AnalyticsEvent.created_at >= since,
            AnalyticsEvent.event_type == event_type
        ).scalar() or 0

    return jsonify({
        'period': period,
        'marketplace': {
            'listing_view': count_event('listing_view'),
            'add_to_cart': count_event('add_to_cart'),
            'checkout_start': count_event('checkout_start'),
            'checkout_complete': count_event('checkout_complete'),
        },
        'garden': {
            'garden_view': count_event('garden_view'),
            'plot_reserve': count_event('plot_reserve'),
            'plot_confirmed': count_event('plot_confirmed'),
        },
        'registration': {
            'register_start': count_event('register_start'),
            'register_complete': count_event('register_complete'),
        },
    })


@analytics_api.route('/api/admin/analytics/search', methods=['GET'])
@token_or_session
@admin_required
def analytics_search():
    """Search analytics — top queries, zero-result searches."""
    period = request.args.get('period', 'month')
    since = _period_start(period)

    search_events = AnalyticsEvent.query.filter(
        AnalyticsEvent.created_at >= since,
        AnalyticsEvent.event_type == 'search',
        AnalyticsEvent.metadata_json.isnot(None)
    ).order_by(desc(AnalyticsEvent.created_at)).limit(500).all()

    query_counts = {}
    zero_results = {}
    for ev in search_events:
        try:
            meta = json.loads(ev.metadata_json)
            q = meta.get('query', '').strip().lower()
            if not q:
                continue
            query_counts[q] = query_counts.get(q, 0) + 1
            if meta.get('result_count', 1) == 0:
                zero_results[q] = zero_results.get(q, 0) + 1
        except Exception:
            continue

    top_queries = sorted(query_counts.items(), key=lambda x: -x[1])[:20]
    top_zero = sorted(zero_results.items(), key=lambda x: -x[1])[:10]

    return jsonify({
        'period': period,
        'top_queries': [{'query': q, 'count': c} for q, c in top_queries],
        'zero_result_queries': [{'query': q, 'count': c} for q, c in top_zero],
        'total_searches': len(search_events),
    })


@analytics_api.route('/api/admin/analytics/events', methods=['GET'])
@token_or_session
@admin_required
def analytics_events():
    """Raw event log — paginated, filterable."""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 100)
    event_type = request.args.get('event_type', '')

    q = AnalyticsEvent.query.order_by(desc(AnalyticsEvent.created_at))
    if event_type:
        q = q.filter_by(event_type=event_type)

    pagination = q.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'events': [{
            'id': e.id,
            'session_id': e.session_id[:8] + '...',
            'user_id': e.user_id,
            'event_type': e.event_type,
            'page_url': e.page_url,
            'referrer': e.referrer,
            'metadata': json.loads(e.metadata_json) if e.metadata_json else None,
            'device_type': e.device_type,
            'created_at': e.created_at.isoformat() if e.created_at else None,
        } for e in pagination.items],
        'page': pagination.page,
        'pages': pagination.pages,
        'total': pagination.total,
    })
