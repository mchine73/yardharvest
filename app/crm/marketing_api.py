"""Token-authenticated marketing API used by the ``marketing_agent`` CLI.

Mounted on ``crm_bp`` under ``/crm/api/marketing/*``. The CLI hits these
endpoints (with ``X-API-Key: <MARKETING_API_KEY>``) to discover audience
segments, fetch candidate contacts, and POST draft campaigns for human review.

The marketing API never sends email and never bypasses contact opt-outs: drafts
are inspected and sent from the web UI like any other campaign.
"""
import functools

from flask import current_app, request, url_for

from app import db
from app.crm import crm_bp
from app.crm.models import (Campaign, Company, Contact, Deal, MERGE_FIELDS)


def require_api_key(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        configured = current_app.config.get('MARKETING_API_KEY')
        if not configured:
            return {'error': 'Marketing API disabled (no MARKETING_API_KEY set)'}, 503
        supplied = (request.headers.get('X-API-Key')
                    or request.args.get('api_key'))
        if supplied != configured:
            return {'error': 'Invalid or missing API key'}, 401
        return view(*args, **kwargs)
    return wrapped


def _contact_payload(c):
    parts = (c.name or '').split()
    return {
        'id': c.id,
        'name': c.name,
        'first_name': parts[0] if parts else '',
        'email': c.email,
        'phone': c.phone,
        'opted_out': bool(c.email_opt_out),
        'company': c.company.name if c.company else None,
        'city': c.company.city if c.company else None,
        'state': c.company.state if c.company else None,
        'org_type': c.company.org_type if c.company else None,
    }


@crm_bp.route('/api/marketing/stats')
@require_api_key
def api_stats():
    open_deals = Deal.query.filter(~Deal.stage.in_(['Closed Won', 'Closed Lost']))
    return {
        'companies': Company.query.count(),
        'contacts': Contact.query.count(),
        'contacts_emailable': Contact.query.filter(
            Contact.email.isnot(None), Contact.email != '',
            Contact.email_opt_out.isnot(True)).count(),
        'deals': Deal.query.count(),
        'open_pipeline': sum((d.amount or 0) for d in open_deals),
        'weighted_forecast': sum(d.weighted_amount for d in open_deals),
        'campaigns': Campaign.query.count(),
    }


@crm_bp.route('/api/marketing/segments')
@require_api_key
def api_segments():
    def breakdown(col):
        rows = (db.session.query(col, db.func.count(Company.id))
                .group_by(col).all())
        return {(k or '—'): n for k, n in rows}
    stage_rows = (db.session.query(Deal.stage, db.func.count(Deal.id))
                  .group_by(Deal.stage).all())
    return {
        'by_state': breakdown(Company.state),
        'by_type': breakdown(Company.org_type),
        'deals_by_stage': {k: n for k, n in stage_rows},
    }


@crm_bp.route('/api/marketing/audience')
@require_api_key
def api_audience():
    state = request.args.get('state', '', type=str)
    org_type = request.args.get('type', '', type=str)
    tag = request.args.get('tag', '', type=str)
    limit = min(request.args.get('limit', 200, type=int), 1000)
    include_opted_out = request.args.get('include_opted_out') == '1'

    query = (Contact.query.filter(Contact.email.isnot(None), Contact.email != '')
             .outerjoin(Company, Contact.company_id == Company.id))
    if not include_opted_out:
        query = query.filter(Contact.email_opt_out.isnot(True))
    if state:
        query = query.filter(Company.state == state)
    if org_type:
        query = query.filter(Company.org_type == org_type)
    if tag:
        query = query.filter(Company.tags.ilike(f'%{tag}%'))
    contacts = query.order_by(Contact.name).limit(limit).all()
    return {
        'count': len(contacts),
        'filters': {'state': state, 'type': org_type, 'tag': tag},
        'contacts': [_contact_payload(c) for c in contacts],
    }


@crm_bp.route('/api/marketing/merge-fields')
@require_api_key
def api_merge_fields():
    return {'merge_fields': [{'token': t, 'description': d}
                             for t, d in MERGE_FIELDS]}


@crm_bp.route('/api/marketing/campaigns', methods=['GET', 'POST'])
@require_api_key
def api_campaigns():
    if request.method == 'GET':
        return {'campaigns': [{
            'id': c.id, 'name': c.name, 'subject': c.subject,
            'status': c.status, 'audience': c.audience_desc,
            'recipients': len(c.recipients),
            'sent': c.count('sent'), 'logged': c.count('logged'),
            'opted_out': c.count('opted_out'),
        } for c in Campaign.query.order_by(Campaign.created_at.desc()).all()]}

    # POST -> create a DRAFT campaign (never auto-sends; review/send in the UI)
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    subject = (data.get('subject') or '').strip()
    body = (data.get('body') or '').strip()
    if not (name and subject and body):
        return {'error': 'name, subject and body are required'}, 400
    state = data.get('state', '')
    org_type = data.get('type', '')
    tag = data.get('tag', '')

    # Inline audience evaluation (matches the UI filter; kept here to avoid
    # importing the helper from views.py and keep the API module self-contained).
    audience_query = (Contact.query.filter(Contact.email.isnot(None),
                                           Contact.email != '')
                      .outerjoin(Company, Contact.company_id == Company.id))
    if state:
        audience_query = audience_query.filter(Company.state == state)
    if org_type:
        audience_query = audience_query.filter(Company.org_type == org_type)
    if tag:
        audience_query = audience_query.filter(Company.tags.ilike(f'%{tag}%'))
    audience = audience_query.all()

    bits = [b for b in (state, org_type, (f'tag:{tag}' if tag else '')) if b]
    campaign = Campaign(name=name, subject=subject, body=body, status='draft',
                        audience_desc=', '.join(bits) or 'All contacts with email')
    db.session.add(campaign)
    db.session.commit()
    return {
        'id': campaign.id, 'status': 'draft',
        'estimated_recipients': len(audience),
        'opted_out_excluded': sum(1 for c in audience if c.email_opt_out),
        'review_url': url_for('crm.campaign_detail', cid=campaign.id, _external=True),
    }, 201
