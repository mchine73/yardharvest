"""CRM view functions, registered on ``crm_bp`` (mounted at ``/crm``).

This is the consolidated counterpart of the standalone CRM app's ``app.py``.
Each route declared here uses the ``crm.`` endpoint prefix automatically by
virtue of being registered on the blueprint, so ``url_for('crm.dashboard')``
etc. is the correct way to reference these views from anywhere in the app.
"""
import base64
import csv
import io
import json
import re
import uuid
from datetime import date, datetime, timedelta
from urllib.parse import quote

from flask import (abort, current_app, flash, redirect, render_template,
                   request, Response, send_from_directory, url_for)

from app import db
from app.crm import crm_bp
from app.crm.forms import (AICampaignForm, CampaignForm, ChangePasswordForm,
                           ComposeEmailForm, CompanyForm, ContactForm,
                           ContentItemForm, DealContactForm, DealForm,
                           EmailTemplateForm, ImportForm, LoginForm, NoteForm,
                           RegisterForm, ResetPasswordForm, SegmentForm,
                           TaskForm)
from app.crm.helpers import (crm_admin_required, crm_login_required,
                             crm_upload_folder, current_user,
                             current_user_id, log_activity, login_crm_user,
                             logout_crm_user, merge_context, render_merge,
                             save_image, smtp_send)
from app.crm.models import (CONTENT_CHANNELS, CONTENT_STATUSES, STAGES,
                            LEAD_STATUSES, LEAD_OPEN_STATUSES, LEAD_SOURCES,
                            Activity, Campaign, CampaignRecipient, Company,
                            Contact, ContentItem, CrmAgentAction, CrmUser, Deal,
                            DealContact, EmailTemplate, MERGE_FIELDS, Note,
                            Segment, Task, _utcnow)
from sqlalchemy import or_, and_


PER_PAGE = 10

# Endpoints (already namespaced as ``crm.<name>`` once on the blueprint) that
# are reachable without authentication.
_PUBLIC_ENDPOINTS = {'crm.login', 'crm.register', 'crm.static',
                     'crm.track_open', 'crm.track_click'}


# ---------------------------------------------------------------------------
# Blueprint-wide auth gate
# ---------------------------------------------------------------------------
@crm_bp.before_request
def require_crm_login():
    """Require a logged-in CRM user for every route except the public ones."""
    if request.endpoint in _PUBLIC_ENDPOINTS:
        return
    # Marketing API uses token auth (enforced per-route) — see marketing_api.py
    if request.path.startswith('/crm/api/'):
        return
    if not current_user.is_authenticated:
        return redirect(url_for('crm.login', next=request.path))


@crm_bp.context_processor
def inject_crm_user():
    """Expose the CRM session user to templates as ``current_user``.

    This shadows the Flask-Login ``current_user`` inside CRM templates so the
    36 templates lifted from the standalone CRM app don't need editing.

    Also exposes email templates (for the embedded compose modal) to every
    authenticated CRM page.
    """
    ctx = {'current_user': current_user, 'merge_fields': MERGE_FIELDS}
    if current_user.is_authenticated:
        ctx['email_templates'] = (EmailTemplate.query
                                  .order_by(EmailTemplate.name).all())
    return ctx


# ---------------------------------------------------------------------------
# Uploads (contact photos)
# ---------------------------------------------------------------------------
@crm_bp.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(crm_upload_folder(), filename)


# NOTE: deliberately under /crm/ (not /crm/api/) so the login gate covers it.
@crm_bp.route('/email/upload-image', methods=['POST'])
def email_upload_image():
    """Upload an image for a CRM email; returns an absolute URL to embed.

    Stores via the shared image pipeline (Cloudinary in prod, else local disk),
    served by the /media/<ref> route. Returns an ABSOLUTE url (SITE_URL-prefixed)
    so it loads in recipients' inboxes."""
    from flask import jsonify
    f = request.files.get('image') or request.files.get('file')
    if not f or not f.filename:
        return jsonify({'error': 'No image provided'}), 400
    try:
        from app.helpers import save_photo
        ref, _size, _w, _h = save_photo(f)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception:
        current_app.logger.exception('CRM email image upload failed')
        return jsonify({'error': 'Upload failed. Try a smaller image.'}), 400
    base = (current_app.config.get('SITE_URL') or '').rstrip('/')
    return jsonify({'url': f'{base}/media/{ref}'})


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@crm_bp.route('/')
def index():
    return redirect(url_for('crm.dashboard'))


@crm_bp.route('/dashboard')
def dashboard():
    deals_by_stage = {s: Deal.query.filter_by(stage=s).count() for s in STAGES}

    open_deals = Deal.query.filter(~Deal.stage.in_(['Closed Won', 'Closed Lost']))
    open_value = sum((d.amount or 0) for d in open_deals)
    weighted_value = sum(d.weighted_amount for d in open_deals)
    won_value = sum((d.amount or 0)
                    for d in Deal.query.filter_by(stage='Closed Won'))

    today = date.today()
    week_ahead = today + timedelta(days=7)
    overdue_tasks = (Task.query.filter(Task.done.is_(False),
                                       Task.due_date.isnot(None),
                                       Task.due_date < today)
                     .order_by(Task.due_date).all())
    upcoming_tasks = (Task.query.filter(Task.done.is_(False),
                                        Task.due_date.isnot(None),
                                        Task.due_date >= today,
                                        Task.due_date <= week_ahead)
                      .order_by(Task.due_date).all())

    recent_activity = (Activity.query.order_by(Activity.created_at.desc())
                       .limit(8).all())

    # Seasonal outreach tip (gardens are seasonal; gov FYs often end June 30)
    season_tips = {
        1: "Budget season: many cities draft FY budgets now — get proposals to decision-makers.",
        2: "Budget season: confirm funding line-items before councils finalize budgets.",
        3: "Spring is peak community-garden activity — strong engagement window for outreach.",
        4: "Spring planting season: gardens are active and responsive — push pilots now.",
        5: "Fiscal year-end nearing (many orgs end June 30) — confirm budget commitments.",
        6: "Fiscal year-end (June 30 for many) — close commitments before budgets reset.",
        7: "New fiscal year started — fresh budgets available; re-engage stalled deals.",
        8: "Fresh FY budgets in hand — good time to revive Qualification-stage deals.",
        9: "Fall planning season — line up renewals and next-season pilots.",
        10: "Grant cycles ramping for next year — align proposals with funding timelines.",
        11: "Year-end giving season — coordinate with nonprofit funding pushes.",
        12: "Year-end: wrap commitments and tee up Q1 budget-season outreach.",
    }
    season_tip = season_tips.get(date.today().month)

    email_contacts = (Contact.query
                      .filter(Contact.email.isnot(None), Contact.email != '',
                              Contact.email_opt_out.isnot(True))
                      .order_by(Contact.name).all())

    return render_template(
        'crm/dashboard.html',
        season_tip=season_tip,
        total_companies=Company.query.count(),
        total_contacts=Contact.query.count(),
        total_deals=Deal.query.count(),
        deals_by_stage=deals_by_stage,
        open_value=open_value,
        weighted_value=weighted_value,
        won_value=won_value,
        overdue_tasks=overdue_tasks,
        upcoming_tasks=upcoming_tasks,
        recent_activity=recent_activity,
        email_contacts=email_contacts,
        today=today,  # _task_row.html needs it to flag overdue rows
    )


# ---------------------------------------------------------------------------
# Companies
# ---------------------------------------------------------------------------
@crm_bp.route('/companies')
def list_companies():
    q = request.args.get('q', '', type=str)
    state = request.args.get('state', '', type=str)
    org_type = request.args.get('type', '', type=str)
    tag = request.args.get('tag', '', type=str)
    page = request.args.get('page', 1, type=int)
    query = Company.query
    if q:
        query = query.filter(Company.name.ilike(f'%{q}%'))
    if state:
        query = query.filter(Company.state == state)
    if org_type:
        query = query.filter(Company.org_type == org_type)
    if tag:
        query = query.filter(Company.tags.ilike(f'%{tag}%'))
    pagination = query.order_by(Company.name).paginate(
        page=page, per_page=PER_PAGE, error_out=False)
    states = [s[0] for s in db.session.query(Company.state)
              .filter(Company.state.isnot(None)).distinct().order_by(Company.state)]
    return render_template('crm/companies.html', companies=pagination.items,
                           pagination=pagination, q=q, state=state,
                           org_type=org_type, states=states, tag=tag)


@crm_bp.route('/companies/new', methods=['GET', 'POST'])
def new_company():
    form = CompanyForm()
    if form.validate_on_submit():
        company = Company(
            name=form.name.data,
            city=form.city.data or None,
            state=form.state.data or None,
            org_type=form.org_type.data or None,
            website=form.website.data or None,
            tags=form.tags.data or None,
            fiscal_year_end=form.fiscal_year_end.data or None,
        )
        db.session.add(company)
        db.session.flush()
        log_activity('created', f'Organization "{company.name}" created',
                     company_id=company.id)
        db.session.commit()
        flash('Company created', 'success')
        return redirect(url_for('crm.company_detail', coid=company.id))
    return render_template('crm/CompanyForm.html', form=form, company=None)


@crm_bp.route('/companies/<int:coid>')
def company_detail(coid):
    company = db.get_or_404(Company, coid)
    activities = (Activity.query.filter_by(company_id=coid)
                  .order_by(Activity.created_at.desc()).limit(50).all())
    return render_template('crm/company_detail.html', company=company,
                           note_form=NoteForm(), task_form=TaskForm(),
                           activities=activities, today=date.today())


@crm_bp.route('/companies/<int:coid>/notes', methods=['POST'])
def add_company_note(coid):
    company = db.get_or_404(Company, coid)
    form = NoteForm()
    if form.validate_on_submit():
        db.session.add(Note(content=form.content.data, company_id=company.id))
        log_activity('note', 'Note added', company_id=company.id)
        db.session.commit()
        flash('Note added', 'success')
    return redirect(url_for('crm.company_detail', coid=coid))


@crm_bp.route('/companies/<int:coid>/convert', methods=['POST'])
def convert_company_to_lead(coid):
    """One-click Prospect -> Lead: open a Deal at stage 'Lead' for this company
    and swap its 'Prospect' tag for 'Lead'. A Lead in this CRM *is* a Deal at the
    Lead stage, so this needs no schema change and immediately shows up on the
    board, the org's leads, and reports."""
    company = db.get_or_404(Company, coid)
    deal = Deal(title=f'{company.name} — Lead', stage='Lead',
                company_id=company.id, owner_id=current_user_id())
    db.session.add(deal)
    db.session.flush()
    # Tag swap: drop "Prospect", add "Lead" (case-insensitive).
    tags = [t for t in company.tag_list if t.lower() != 'prospect']
    if not any(t.lower() == 'lead' for t in tags):
        tags.append('Lead')
    company.tags = ', '.join(tags) or None
    log_activity('created', f'Converted to Lead — "{deal.title}"',
                 deal_id=deal.id, company_id=company.id)
    db.session.commit()
    flash('Converted to Lead — opened a new deal at the Lead stage.', 'success')
    return redirect(url_for('crm.deal_detail', did=deal.id))


@crm_bp.route('/companies/<int:coid>/tasks', methods=['POST'])
def add_company_task(coid):
    company = db.get_or_404(Company, coid)
    form = TaskForm()
    if form.validate_on_submit():
        db.session.add(Task(title=form.title.data, due_date=form.due_date.data,
                            priority=form.priority.data, company_id=company.id))
        log_activity('task', f'Task added: {form.title.data}',
                     company_id=company.id)
        db.session.commit()
        flash('Task added', 'success')
    return redirect(url_for('crm.company_detail', coid=coid))


@crm_bp.route('/companies/<int:coid>/edit', methods=['GET', 'POST'])
def edit_company(coid):
    company = db.get_or_404(Company, coid)
    form = CompanyForm(obj=company)
    if form.validate_on_submit():
        company.name = form.name.data
        company.city = form.city.data or None
        company.state = form.state.data or None
        company.org_type = form.org_type.data or None
        company.website = form.website.data or None
        company.tags = form.tags.data or None
        company.fiscal_year_end = form.fiscal_year_end.data or None
        log_activity('updated', 'Organization details updated',
                     company_id=company.id)
        db.session.commit()
        flash('Company updated', 'success')
        return redirect(url_for('crm.company_detail', coid=company.id))
    return render_template('crm/CompanyForm.html', form=form, company=company)


@crm_bp.route('/companies/<int:coid>/delete', methods=['POST'])
def delete_company(coid):
    company = db.get_or_404(Company, coid)
    db.session.delete(company)
    db.session.commit()
    flash('Company deleted', 'warning')
    return redirect(url_for('crm.list_companies'))


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------
def _company_choices():
    return [(0, '— None —')] + [(c.id, c.name)
                                for c in Company.query.order_by(Company.name)]


@crm_bp.route('/contacts')
def list_contacts():
    q = request.args.get('q', '', type=str)
    page = request.args.get('page', 1, type=int)
    query = Contact.query
    if q:
        query = query.filter(
            db.or_(Contact.name.ilike(f'%{q}%'),
                   Contact.email.ilike(f'%{q}%')))
    pagination = query.order_by(Contact.name).paginate(
        page=page, per_page=PER_PAGE, error_out=False)
    return render_template('crm/contacts.html', contacts=pagination.items,
                           pagination=pagination, q=q)


@crm_bp.route('/contacts/new', methods=['GET', 'POST'])
def new_contact():
    form = ContactForm()
    form.company.choices = _company_choices()
    if form.validate_on_submit():
        contact = Contact(
            name=form.name.data,
            email=form.email.data,
            phone=form.phone.data,
            company_id=form.company.data or None,
            image=save_image(form.image.data),
            email_opt_out=form.email_opt_out.data,
        )
        db.session.add(contact)
        db.session.flush()
        log_activity('created', f'Contact "{contact.name}" created',
                     contact_id=contact.id, company_id=contact.company_id)
        db.session.commit()
        flash('Contact created', 'success')
        return redirect(url_for('crm.view_contact', cid=contact.id))
    return render_template('crm/ContactForm.html', form=form, contact=None)


@crm_bp.route('/contacts/<int:cid>/edit', methods=['GET', 'POST'])
def edit_contact(cid):
    contact = db.get_or_404(Contact, cid)
    form = ContactForm(obj=contact)
    form.company.choices = _company_choices()
    if request.method == 'GET':
        form.company.data = contact.company_id or 0
    if form.validate_on_submit():
        contact.name = form.name.data
        contact.email = form.email.data
        contact.phone = form.phone.data
        contact.company_id = form.company.data or None
        contact.email_opt_out = form.email_opt_out.data
        if form.image.data:
            contact.image = save_image(form.image.data)
        log_activity('updated', 'Contact details updated',
                     contact_id=contact.id, company_id=contact.company_id)
        db.session.commit()
        flash('Contact updated', 'success')
        return redirect(url_for('crm.view_contact', cid=contact.id))
    return render_template('crm/ContactForm.html', form=form, contact=contact)


@crm_bp.route('/contacts/<int:cid>', methods=['GET', 'POST'])
def view_contact(cid):
    contact = db.get_or_404(Contact, cid)
    form = NoteForm()
    if form.validate_on_submit():
        db.session.add(Note(content=form.content.data, contact_id=contact.id))
        log_activity('note', 'Note added', contact_id=contact.id,
                     company_id=contact.company_id)
        db.session.commit()
        flash('Note added', 'success')
        return redirect(url_for('crm.view_contact', cid=contact.id))
    activities = (Activity.query.filter_by(contact_id=cid)
                  .order_by(Activity.created_at.desc()).limit(50).all())
    return render_template('crm/contact_view.html', contact=contact, form=form,
                           task_form=TaskForm(), activities=activities,
                           today=date.today(), lead_statuses=LEAD_STATUSES,
                           lead_sources=LEAD_SOURCES,
                           owners=CrmUser.query.order_by(CrmUser.username).all())


@crm_bp.route('/contacts/<int:cid>/tasks', methods=['POST'])
def add_contact_task(cid):
    contact = db.get_or_404(Contact, cid)
    form = TaskForm()
    if form.validate_on_submit():
        db.session.add(Task(title=form.title.data, due_date=form.due_date.data,
                            priority=form.priority.data, contact_id=contact.id))
        log_activity('task', f'Task added: {form.title.data}',
                     contact_id=contact.id, company_id=contact.company_id)
        db.session.commit()
        flash('Task added', 'success')
    return redirect(url_for('crm.view_contact', cid=cid))


@crm_bp.route('/contacts/<int:cid>/delete', methods=['POST'])
def delete_contact(cid):
    contact = db.get_or_404(Contact, cid)
    db.session.delete(contact)
    db.session.commit()
    flash('Contact deleted', 'warning')
    return redirect(url_for('crm.list_contacts'))


# ---------------------------------------------------------------------------
# Deals
# ---------------------------------------------------------------------------
def _contact_choices():
    return [(0, '— None —')] + [(c.id, c.name)
                                for c in Contact.query.order_by(Contact.name)]


@crm_bp.route('/deals')
def list_deals():
    stage = request.args.get('stage', '', type=str)
    owner = request.args.get('owner', '', type=str)
    page = request.args.get('page', 1, type=int)
    query = Deal.query
    if stage:
        query = query.filter_by(stage=stage)
    if owner == 'me' and current_user.is_authenticated:
        query = query.filter_by(owner_id=current_user.id)
    pagination = query.order_by(Deal.created_at.desc()).paginate(
        page=page, per_page=PER_PAGE, error_out=False)
    return render_template('crm/deals.html', deals=pagination.items,
                           pagination=pagination, stage=stage, stages=STAGES,
                           owner=owner)


@crm_bp.route('/kanban')
def kanban():
    columns = {}
    totals = {}
    for s in STAGES:
        deals = (Deal.query.filter_by(stage=s)
                 .order_by(Deal.created_at.desc()).all())
        columns[s] = deals
        totals[s] = sum((d.amount or 0) for d in deals)
    return render_template('crm/kanban.html', columns=columns, totals=totals,
                           stages=STAGES)


def _company_for_contact(contact_id):
    """Derive a deal's company from its linked contact."""
    if not contact_id:
        return None
    c = db.session.get(Contact, contact_id)
    return c.company_id if c else None


@crm_bp.route('/deals/new', methods=['GET', 'POST'])
def new_deal():
    form = DealForm()
    form.contact.choices = _contact_choices()
    if form.validate_on_submit():
        contact_id = form.contact.data or None
        deal = Deal(
            title=form.title.data,
            amount=form.amount.data,
            stage=form.stage.data,
            contact_id=contact_id,
            company_id=_company_for_contact(contact_id),
            owner_id=current_user_id(),
            funding_source=form.funding_source.data or None,
            grant_status=form.grant_status.data or None,
            budget_decision_date=form.budget_decision_date.data,
            rfp_due_date=form.rfp_due_date.data,
        )
        if deal.stage in ('Closed Won', 'Closed Lost'):
            deal.close_date = date.today()
        db.session.add(deal)
        db.session.flush()
        log_activity('created', f'Lead "{deal.title}" created '
                     f'({deal.stage})', deal_id=deal.id,
                     company_id=deal.company_id, contact_id=deal.contact_id)
        db.session.commit()
        flash('Lead created', 'success')
        return redirect(url_for('crm.deal_detail', did=deal.id))
    return render_template('crm/deal_form.html', form=form, deal=None)


@crm_bp.route('/deals/<int:did>/edit', methods=['GET', 'POST'])
def edit_deal(did):
    deal = db.get_or_404(Deal, did)
    form = DealForm(obj=deal)
    form.contact.choices = _contact_choices()
    if request.method == 'GET':
        form.contact.data = deal.contact_id or 0
    if form.validate_on_submit():
        old_stage = deal.stage
        deal.title = form.title.data
        deal.amount = form.amount.data
        deal.stage = form.stage.data
        deal.contact_id = form.contact.data or None
        deal.company_id = _company_for_contact(deal.contact_id)
        deal.funding_source = form.funding_source.data or None
        deal.grant_status = form.grant_status.data or None
        deal.budget_decision_date = form.budget_decision_date.data
        deal.rfp_due_date = form.rfp_due_date.data
        if deal.stage != old_stage:
            log_activity('stage_change',
                         f'Stage changed: {old_stage} → {deal.stage}',
                         deal_id=deal.id, company_id=deal.company_id)
            if deal.stage in ('Closed Won', 'Closed Lost') and not deal.close_date:
                deal.close_date = date.today()
            if deal.stage not in ('Closed Won', 'Closed Lost'):
                deal.close_date = None
        else:
            log_activity('updated', 'Lead details updated', deal_id=deal.id,
                         company_id=deal.company_id)
        db.session.commit()
        flash('Lead updated', 'success')
        return redirect(url_for('crm.deal_detail', did=deal.id))
    return render_template('crm/deal_form.html', form=form, deal=deal)


@crm_bp.route('/deals/<int:did>')
def deal_detail(did):
    deal = db.get_or_404(Deal, did)
    link_form = DealContactForm()
    link_form.contact.choices = _contact_choices()
    activities = (Activity.query.filter_by(deal_id=did)
                  .order_by(Activity.created_at.desc()).limit(50).all())
    return render_template('crm/deal_detail.html', deal=deal,
                           note_form=NoteForm(), task_form=TaskForm(),
                           link_form=link_form, activities=activities,
                           stages=STAGES, today=date.today())


@crm_bp.route('/deals/<int:did>/stage', methods=['POST'])
def set_deal_stage(did):
    """Quick stage change (used by kanban + detail page)."""
    deal = db.get_or_404(Deal, did)
    new_stage = request.form.get('stage', '')
    reason = (request.form.get('reason') or '').strip()
    if new_stage in STAGES and new_stage != deal.stage:
        old = deal.stage
        deal.stage = new_stage
        if new_stage in ('Closed Won', 'Closed Lost'):
            if not deal.close_date:
                deal.close_date = date.today()
            deal.closed_reason = reason or deal.closed_reason
        else:
            deal.close_date = None
            deal.closed_reason = None
        desc = f'Stage changed: {old} → {new_stage}'
        if reason:
            desc += f' ({reason})'
        log_activity('stage_change', desc, deal_id=deal.id,
                     company_id=deal.company_id)
        db.session.commit()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return {'ok': True, 'stage': deal.stage}
    flash('Stage updated', 'success')
    return redirect(request.referrer or url_for('crm.deal_detail', did=did))


@crm_bp.route('/deals/<int:did>/notes', methods=['POST'])
def add_deal_note(did):
    deal = db.get_or_404(Deal, did)
    form = NoteForm()
    if form.validate_on_submit():
        db.session.add(Note(content=form.content.data, deal_id=deal.id))
        log_activity('note', 'Note added', deal_id=deal.id,
                     company_id=deal.company_id)
        db.session.commit()
        flash('Note added', 'success')
    return redirect(url_for('crm.deal_detail', did=did))


@crm_bp.route('/deals/<int:did>/tasks', methods=['POST'])
def add_deal_task(did):
    deal = db.get_or_404(Deal, did)
    form = TaskForm()
    if form.validate_on_submit():
        db.session.add(Task(title=form.title.data, due_date=form.due_date.data,
                            priority=form.priority.data, deal_id=deal.id))
        log_activity('task', f'Task added: {form.title.data}', deal_id=deal.id,
                     company_id=deal.company_id)
        db.session.commit()
        flash('Task added', 'success')
    return redirect(url_for('crm.deal_detail', did=did))


@crm_bp.route('/deals/<int:did>/contacts', methods=['POST'])
def add_deal_contact(did):
    deal = db.get_or_404(Deal, did)
    form = DealContactForm()
    form.contact.choices = _contact_choices()
    if form.validate_on_submit() and form.contact.data:
        db.session.add(DealContact(deal_id=deal.id, contact_id=form.contact.data,
                                   role=form.role.data))
        c = db.session.get(Contact, form.contact.data)
        log_activity('updated',
                     f'Linked {c.name if c else "contact"} as {form.role.data}',
                     deal_id=deal.id, company_id=deal.company_id)
        db.session.commit()
        flash('Contact linked', 'success')
    return redirect(url_for('crm.deal_detail', did=did))


@crm_bp.route('/deals/<int:did>/contacts/<int:link_id>/delete', methods=['POST'])
def remove_deal_contact(did, link_id):
    link = db.get_or_404(DealContact, link_id)
    if link.deal_id != did:
        abort(404)
    db.session.delete(link)
    db.session.commit()
    flash('Contact unlinked', 'warning')
    return redirect(url_for('crm.deal_detail', did=did))


@crm_bp.route('/deals/<int:did>/delete', methods=['POST'])
def delete_deal(did):
    deal = db.get_or_404(Deal, did)
    db.session.delete(deal)
    db.session.commit()
    flash('Lead deleted', 'warning')
    return redirect(url_for('crm.list_deals'))


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------
@crm_bp.route('/tasks')
def list_tasks():
    show = request.args.get('show', 'open')
    query = Task.query
    if show == 'open':
        query = query.filter(Task.done.is_(False))
    elif show == 'done':
        query = query.filter(Task.done.is_(True))
    tasks = query.order_by(Task.done, Task.due_date.is_(None),
                           Task.due_date, Task.id.desc()).all()
    return render_template('crm/tasks.html', tasks=tasks, show=show,
                           today=date.today())


@crm_bp.route('/tasks/<int:tid>/toggle', methods=['POST'])
def toggle_task(tid):
    task = db.get_or_404(Task, tid)
    task.done = not task.done
    db.session.commit()
    return redirect(request.referrer or url_for('crm.list_tasks'))


@crm_bp.route('/tasks/<int:tid>/delete', methods=['POST'])
def delete_task(tid):
    task = db.get_or_404(Task, tid)
    db.session.delete(task)
    db.session.commit()
    flash('Task deleted', 'warning')
    return redirect(request.referrer or url_for('crm.list_tasks'))


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------
@crm_bp.route('/reports')
def reports():
    deals = Deal.query.all()
    value_by_stage = {s: 0 for s in STAGES}
    count_by_stage = {s: 0 for s in STAGES}
    for d in deals:
        value_by_stage[d.stage] += (d.amount or 0)
        count_by_stage[d.stage] += 1

    by_state, by_type = {}, {}
    for c in Company.query.all():
        by_state[c.state or '—'] = by_state.get(c.state or '—', 0) + 1
        by_type[c.org_type or '—'] = by_type.get(c.org_type or '—', 0) + 1

    won = count_by_stage['Closed Won']
    lost = count_by_stage['Closed Lost']
    win_rate = round(100 * won / (won + lost)) if (won + lost) else 0
    open_value = sum(v for s, v in value_by_stage.items()
                     if s not in ('Closed Won', 'Closed Lost'))
    weighted = sum(d.weighted_amount for d in deals if d.is_open)

    return render_template('crm/reports.html',
                           value_by_stage=value_by_stage,
                           count_by_stage=count_by_stage,
                           by_state=dict(sorted(by_state.items())),
                           by_type=by_type, win_rate=win_rate,
                           open_value=open_value, weighted=weighted,
                           won_value=value_by_stage['Closed Won'], stages=STAGES)


# ---------------------------------------------------------------------------
# CSV Export / Import
# ---------------------------------------------------------------------------
def _csv_response(rows, header, filename):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    writer.writerows(rows)
    return Response(buf.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition':
                             f'attachment; filename={filename}'})


@crm_bp.route('/export/companies.csv')
def export_companies():
    rows = [(c.name, c.city, c.state, c.org_type, c.website,
             len(c.contacts), len(c.deals))
            for c in Company.query.order_by(Company.name)]
    return _csv_response(rows, ['Name', 'City', 'State', 'Type', 'Website',
                                'Contacts', 'Leads'], 'companies.csv')


@crm_bp.route('/export/deals.csv')
def export_deals():
    rows = [(d.title, d.amount or 0, d.stage,
             d.company.name if d.company else '',
             d.contact.name if d.contact else '',
             d.close_date.isoformat() if d.close_date else '',
             d.closed_reason or '')
            for d in Deal.query.order_by(Deal.stage)]
    return _csv_response(rows, ['Title', 'Amount', 'Stage', 'Company',
                                'Primary Contact', 'Close Date', 'Reason'],
                         'leads.csv')


@crm_bp.route('/import', methods=['GET', 'POST'])
def import_data():
    form = ImportForm()
    if form.validate_on_submit() and form.file.data:
        raw = form.file.data.read().decode('utf-8-sig', errors='replace')
        reader = csv.DictReader(io.StringIO(raw))

        def _get(row, *keys):
            for k in keys:
                v = row.get(k)
                if v and v.strip():
                    return v.strip()
            return None

        # Dedupe against existing companies (case-insensitive name match) so
        # re-importing the same file doesn't create duplicates.
        existing = {(c.name or '').strip().lower()
                    for c in Company.query.with_entities(Company.name).all()}

        created = skipped = contacts_added = 0
        for row in reader:
            name = _get(row, 'Name', 'name')
            if not name:
                continue
            if name.lower() in existing:
                skipped += 1
                continue
            existing.add(name.lower())

            company = Company(
                name=name,
                city=_get(row, 'City', 'city'),
                state=_get(row, 'State', 'state'),
                org_type=_get(row, 'Type', 'org_type'),
                website=_get(row, 'Website', 'website'),
                tags=_get(row, 'Tags', 'tags'),
            )
            db.session.add(company)
            db.session.flush()
            log_activity('created', f'Imported "{company.name}"',
                         company_id=company.id)
            created += 1

            # Optional public org contact (Email / Contact name / Phone columns)
            email = _get(row, 'Email', 'email')
            contact_name = _get(row, 'Contact', 'contact', 'Contact Name')
            phone = _get(row, 'Phone', 'phone')
            if email or contact_name or phone:
                db.session.add(Contact(
                    name=contact_name or f'Info — {name}',
                    email=email,
                    phone=phone,
                    company_id=company.id,
                ))
                contacts_added += 1

            # Optional source / notes column
            note = _get(row, 'Notes', 'notes', 'Note', 'note', 'Source')
            if note:
                db.session.add(Note(content=note, company_id=company.id))

        db.session.commit()
        msg = f'Imported {created} organization(s)'
        if contacts_added:
            msg += f', {contacts_added} contact(s)'
        if skipped:
            msg += f' — skipped {skipped} duplicate(s)'
        flash(msg, 'success')
        return redirect(url_for('crm.list_companies'))
    return render_template('crm/import.html', form=form)


# ---------------------------------------------------------------------------
# Email templates
# ---------------------------------------------------------------------------
@crm_bp.route('/templates')
def list_templates():
    templates = EmailTemplate.query.order_by(EmailTemplate.name).all()
    return render_template('crm/templates.html', templates=templates)


@crm_bp.route('/templates/new', methods=['GET', 'POST'])
@crm_bp.route('/templates/<int:tid>/edit', methods=['GET', 'POST'])
def edit_template(tid=None):
    template = db.get_or_404(EmailTemplate, tid) if tid else None
    form = EmailTemplateForm(obj=template)
    if form.validate_on_submit():
        if not template:
            template = EmailTemplate()
            db.session.add(template)
        template.name = form.name.data
        template.subject = form.subject.data
        template.body = form.body.data
        db.session.commit()
        flash('Template saved', 'success')
        return redirect(url_for('crm.list_templates'))
    from app.crm import agent_service
    return render_template('crm/template_form.html', form=form, template=template,
                           merge_fields=MERGE_FIELDS,
                           ai_configured=agent_service.is_configured())


@crm_bp.route('/templates/<int:tid>/delete', methods=['POST'])
def delete_template(tid):
    template = db.get_or_404(EmailTemplate, tid)
    db.session.delete(template)
    db.session.commit()
    flash('Template deleted', 'warning')
    return redirect(url_for('crm.list_templates'))


@crm_bp.route('/templates/ai-draft', methods=['POST'])
def ai_draft_template():
    """AI email-template agent: a described purpose -> Claude drafts a reusable
    template (name/subject/body) returned as JSON for the editor to fill in.
    Never saves on its own — the human reviews and clicks Save."""
    from app.crm import agent_service
    if not agent_service.is_configured():
        return {'error': 'AI drafting isn’t configured yet — set '
                'ANTHROPIC_API_KEY to enable it.'}, 503
    data = request.get_json(silent=True) or {}
    purpose = (data.get('purpose') or '').strip()
    if not purpose:
        return {'error': 'Describe what this template is for first.'}, 400
    try:
        tpl = agent_service.draft_template(purpose)
    except agent_service.AgentError as e:
        return {'error': str(e)}, 502
    return {'name': tpl['name'], 'subject': tpl['subject'], 'body': tpl['body']}


# ---------------------------------------------------------------------------
# Email composition (sends via the shared YH ZeptoMail backend)
# ---------------------------------------------------------------------------
def _send_or_log_email(form, *, contact, deal=None):
    """Render merge fields, send via SMTP if configured, always log."""
    opted_out = bool(contact and contact.email_opt_out)
    recipient = contact.email if (contact and not opted_out) else None
    subject = render_merge(form.subject.data, contact, deal)
    body = render_merge(form.body.data, contact, deal)
    sent = smtp_send(recipient, subject, body)
    verb = 'Email sent' if sent else 'Email logged'
    log_activity('email', f'{verb}: {subject}',
                 contact_id=contact.id if contact else None,
                 company_id=(contact.company_id if contact else
                             (deal.company_id if deal else None)),
                 deal_id=deal.id if deal else None)
    db.session.add(Note(
        content=f'[{verb} to {recipient or "n/a"}] {subject}\n\n{body}',
        contact_id=contact.id if contact else None,
        deal_id=deal.id if deal else None))
    db.session.commit()
    return sent


@crm_bp.route('/contacts/<int:cid>/email', methods=['GET', 'POST'])
def email_contact(cid):
    contact = db.get_or_404(Contact, cid)
    form = ComposeEmailForm()
    templates = EmailTemplate.query.order_by(EmailTemplate.name).all()
    form.template.choices = [(0, '— None —')] + [(t.id, t.name) for t in templates]
    if form.validate_on_submit():
        sent = _send_or_log_email(form, contact=contact)
        flash('Email sent' if sent else 'Email logged to timeline', 'success')
        return redirect(url_for('crm.view_contact', cid=cid))
    return render_template('crm/email_compose.html', form=form, contact=contact,
                           deal=None, templates=templates,
                           merge_fields=MERGE_FIELDS)


@crm_bp.route('/deals/<int:did>/email', methods=['GET', 'POST'])
def email_deal(did):
    deal = db.get_or_404(Deal, did)
    form = ComposeEmailForm()
    templates = EmailTemplate.query.order_by(EmailTemplate.name).all()
    form.template.choices = [(0, '— None —')] + [(t.id, t.name) for t in templates]
    if form.validate_on_submit():
        sent = _send_or_log_email(form, contact=deal.contact, deal=deal)
        flash('Email sent' if sent else 'Email logged to timeline', 'success')
        return redirect(url_for('crm.deal_detail', did=did))
    return render_template('crm/email_compose.html', form=form, contact=deal.contact,
                           deal=deal, templates=templates,
                           merge_fields=MERGE_FIELDS)


@crm_bp.route('/email/send', methods=['POST'])
def email_send():
    """Generic send target for the embedded compose modal used across the CRM
    (contact/company/deal pages, list rows, dashboard). Recipient comes from a
    hidden contact_id (set by the trigger) or a picked contact_id (dashboard);
    deal_id optionally links the email to a deal. Redirects back to the page."""
    form = ComposeEmailForm()
    contact_id = request.form.get('contact_id', type=int)
    deal_id = request.form.get('deal_id', type=int)
    deal = db.session.get(Deal, deal_id) if deal_id else None
    contact = db.session.get(Contact, contact_id) if contact_id else (deal.contact if deal else None)
    back = request.referrer or url_for('crm.dashboard')
    if not contact:
        flash('Pick a recipient to email.', 'warning')
        return redirect(back)
    if form.validate_on_submit():
        sent = _send_or_log_email(form, contact=contact, deal=deal)
        flash('Email sent' if sent else 'Email logged to timeline', 'success')
    else:
        flash('Subject and body are required.', 'warning')
    return redirect(back)


# NOTE: deliberately NOT under /crm/api/ — that prefix is exempt from the CRM
# login gate (it's reserved for the token-authed marketing API), so a route
# there would be world-readable. Keeping tid as the last path segment preserves
# the url_for(...).slice(0,-1)+id trick used by the compose modal / pickers.
@crm_bp.route('/templates/json/<int:tid>')
def api_template(tid):
    t = db.get_or_404(EmailTemplate, tid)
    return {'subject': t.subject or '', 'body': t.body or ''}


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
@crm_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('crm.dashboard'))
    # Fresh install: no users yet -> create the first admin.
    if CrmUser.query.first() is None:
        return redirect(url_for('crm.register'))
    form = LoginForm()
    if form.validate_on_submit():
        user = CrmUser.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            if user.needs_password_rehash():
                user.set_password(form.password.data)
                db.session.commit()
            login_crm_user(user)
            nxt = request.args.get('next')
            return redirect(nxt or url_for('crm.dashboard'))
        flash('Invalid username or password', 'danger')
    return render_template('crm/login.html', form=form)


@crm_bp.route('/register', methods=['GET', 'POST'])
def register():
    # First user becomes admin; afterwards registration is admin-only.
    has_users = CrmUser.query.first() is not None
    if has_users and not (current_user.is_authenticated and current_user.is_admin):
        abort(403)
    form = RegisterForm()
    if form.validate_on_submit():
        if CrmUser.query.filter_by(username=form.username.data).first():
            flash('Username already taken', 'danger')
        else:
            user = CrmUser(username=form.username.data,
                           email=form.email.data or None,
                           role='admin' if not has_users else 'member')
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            flash('Account created', 'success')
            if not has_users:
                login_crm_user(user)
                return redirect(url_for('crm.dashboard'))
            return redirect(url_for('crm.list_users'))
    return render_template('crm/register.html', form=form, first_user=not has_users)


@crm_bp.route('/logout', methods=['POST'])
def logout():
    logout_crm_user()
    return redirect(url_for('crm.login'))


@crm_bp.route('/admin')
@crm_login_required
def admin_portal():
    if not current_user.is_admin:
        abort(403)
    stats = {
        'users': CrmUser.query.count(),
        'companies': Company.query.count(),
        'contacts': Contact.query.count(),
        'deals': Deal.query.count(),
        'templates': EmailTemplate.query.count(),
    }
    recent_users = CrmUser.query.order_by(CrmUser.created_at.desc()).limit(5).all()
    return render_template('crm/admin.html', stats=stats, recent_users=recent_users)


@crm_bp.route('/account/password', methods=['GET', 'POST'])
@crm_login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        # Re-fetch the live ORM object — current_user is a proxy
        user = db.session.get(CrmUser, current_user.id)
        if not user.check_password(form.current_password.data):
            flash('Current password is incorrect', 'danger')
        else:
            user.set_password(form.new_password.data)
            db.session.commit()
            flash('Password changed', 'success')
            return redirect(url_for('crm.dashboard'))
    return render_template('crm/change_password.html', form=form)


@crm_bp.route('/users')
@crm_login_required
def list_users():
    if not current_user.is_admin:
        abort(403)
    return render_template('crm/users.html',
                           users=CrmUser.query.order_by(CrmUser.username).all())


@crm_bp.route('/users/<int:uid>/password', methods=['GET', 'POST'])
@crm_login_required
def reset_user_password(uid):
    if not current_user.is_admin:
        abort(403)
    user = db.get_or_404(CrmUser, uid)
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.new_password.data)
        db.session.commit()
        flash(f"Password reset for {user.username}", 'success')
        return redirect(url_for('crm.list_users'))
    return render_template('crm/reset_password.html', form=form, user=user)


# ---------------------------------------------------------------------------
# Campaigns
# ---------------------------------------------------------------------------
def _campaign_audience(state, org_type, tag):
    """Contacts with an email address, filtered by org attributes."""
    query = (Contact.query.filter(Contact.email.isnot(None),
                                  Contact.email != '')
             .outerjoin(Company, Contact.company_id == Company.id))
    if state:
        query = query.filter(Company.state == state)
    if org_type:
        query = query.filter(Company.org_type == org_type)
    if tag:
        query = query.filter(Company.tags.ilike(f'%{tag}%'))
    return query.order_by(Contact.name).all()


def _campaign_form_choices(form):
    templates = EmailTemplate.query.order_by(EmailTemplate.name).all()
    form.template.choices = [(0, '— None —')] + [(t.id, t.name) for t in templates]
    states = [s[0] for s in db.session.query(Company.state)
              .filter(Company.state.isnot(None)).distinct().order_by(Company.state)]
    form.state.choices = [('', 'All states')] + [(s, s) for s in states]
    return templates


def _audience_desc(form):
    bits = []
    if form.state.data:
        bits.append(form.state.data)
    if form.org_type.data:
        bits.append(form.org_type.data)
    if form.tag.data:
        bits.append(f'tag:{form.tag.data}')
    return ', '.join(bits) if bits else 'All contacts with email'


# 1x1 transparent GIF returned by the open-tracking endpoint.
_TRACKING_PIXEL = base64.b64decode(
    'R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7')


def _inject_tracking(html, token, base):
    """Append an open-tracking pixel and route absolute links through the click
    tracker. `token` is a real token, or the literal '{{tracking_token}}'
    placeholder for ZeptoMail's per-recipient batch merge. No-op without a base
    URL (tracking links must be absolute to work in an email client)."""
    if not base:
        return html

    def _wrap(m):
        url = m.group(2)
        if not url.startswith(('http://', 'https://')) or '/crm/t/' in url:
            return m.group(0)
        return f'{m.group(1)}{base}/crm/t/click/{token}?u={quote(url, safe="")}{m.group(3)}'

    html = re.sub(r'(<a\b[^>]*\bhref=")([^"]+)(")', _wrap, html, flags=re.IGNORECASE)
    return (f'{html}<img src="{base}/crm/t/open/{token}" width="1" height="1" '
            f'alt="" style="display:none">')


def _dispatch_campaign(campaign, audience):
    """Send a campaign (subject/body already set on it) to `audience` and
    record per-recipient status + activity/notes. Returns counts. Shared by the
    compose-and-send form and the 'send a saved draft' action.

    Opted-out contacts are skipped and recorded 'opted_out'. When ZeptoMail is
    configured, one batch request is sent with {{token}} merge fields; otherwise
    it falls back to per-contact sends via the shared backend.
    """
    import os
    counts = {'sent': 0, 'logged': 0, 'opted_out': 0}
    sendable = [c for c in audience if not c.email_opt_out]
    # A unique tracking token per sendable recipient (open pixel + click links).
    tokens = {c.id: uuid.uuid4().hex for c in sendable}
    base = (current_app.config.get('SITE_URL', '') or '').rstrip('/')

    batch_status = None  # applied to every sendable recipient when set
    if sendable and (os.environ.get('ZEPTOMAIL_TOKEN', '')
                     or current_app.config.get('ZEPTOMAIL_TOKEN', '')):
        from app.email_service import send_batch_via_zeptomail, render_sales_email
        # Brand + sanitize the campaign body; {{tokens}} survive bleach (text)
        # so ZeptoMail still does its per-recipient server-side merge. Tracking is
        # injected AFTER sanitize (our own safe markup) with a {{tracking_token}}
        # placeholder that ZeptoMail substitutes per recipient.
        html_template = render_sales_email(campaign.body)
        html_template = _inject_tracking(html_template, '{{tracking_token}}', base)
        batch_recipients = [{'email': c.email,
                             'merge_info': {**merge_context(c),
                                            'tracking_token': tokens[c.id]}}
                            for c in sendable]
        # Campaigns send from the personal CRM address (CAMPAIGN_FROM_ADDRESS
        # overrides; otherwise CRM_FROM_EMAIL). Fall back hard to james@ so an
        # unset/empty value can never leak the platform no_reply address.
        campaign_sender = (os.environ.get('CAMPAIGN_FROM_ADDRESS', '')
                           or current_app.config.get('CAMPAIGN_FROM_ADDRESS', '')
                           or current_app.config.get('CRM_FROM_EMAIL', '')
                           or 'james@yardharvest.app')
        # Personal display name ("James Goodman <james@…>") for engagement.
        campaign_sender_name = (os.environ.get('CAMPAIGN_FROM_NAME', '')
                                or current_app.config.get('CAMPAIGN_FROM_NAME', '')
                                or current_app.config.get('CRM_FROM_NAME', '')
                                or 'James Goodman')
        result = send_batch_via_zeptomail(
            batch_recipients, campaign.subject, html_template,
            from_email=campaign_sender, from_name=campaign_sender_name)
        if result.get('configured'):
            batch_status = 'sent' if result.get('ok') else 'logged'

    for contact in audience:
        if contact.email_opt_out:
            status = 'opted_out'
        else:
            if batch_status is not None:
                status = batch_status
            else:
                ok = smtp_send(contact.email,
                               render_merge(campaign.subject, contact),
                               render_merge(campaign.body, contact))
                status = 'sent' if ok else 'logged'
            subj = render_merge(campaign.subject, contact)
            body = render_merge(campaign.body, contact)
            log_activity('email', f"Campaign '{campaign.name}': {subj}",
                         contact_id=contact.id, company_id=contact.company_id)
            db.session.add(Note(
                content=f'[Campaign: {campaign.name}] {subj}\n\n{body}',
                contact_id=contact.id))
        counts[status] = counts.get(status, 0) + 1
        db.session.add(CampaignRecipient(campaign_id=campaign.id,
                                         contact_id=contact.id, status=status,
                                         token=tokens.get(contact.id)))
    db.session.commit()
    return counts


def _campaign_sent_flash(counts):
    flash(f"Campaign sent — {counts.get('sent', 0)} sent, "
          f"{counts.get('logged', 0)} logged, "
          f"{counts.get('opted_out', 0)} skipped (opted out)", 'success')


@crm_bp.route('/campaigns')
def list_campaigns():
    campaigns = Campaign.query.order_by(Campaign.created_at.desc()).all()
    return render_template('crm/campaigns.html', campaigns=campaigns)


@crm_bp.route('/campaigns/new', methods=['GET', 'POST'])
def new_campaign():
    form = CampaignForm()
    templates = _campaign_form_choices(form)
    preview = None

    # Prefill audience filters when launched from a saved segment
    if request.method == 'GET' and request.args.get('segment'):
        seg = db.session.get(Segment, request.args.get('segment', type=int))
        if seg:
            form.state.data = seg.state or ''
            form.org_type.data = seg.org_type or ''
            form.tag.data = seg.tag or ''
            form.name.data = f'{seg.name} — '

    if form.validate_on_submit():
        audience = _campaign_audience(form.state.data, form.org_type.data,
                                      form.tag.data)

        if form.send.data:
            campaign = Campaign(
                name=form.name.data, subject=form.subject.data,
                body=form.body.data, status='sent',
                created_by=current_user_id(), sent_at=_utcnow(),
                audience_desc=_audience_desc(form),
                audience_state=form.state.data or None,
                audience_org_type=form.org_type.data or None,
                audience_tag=form.tag.data or None)
            db.session.add(campaign)
            db.session.flush()
            counts = _dispatch_campaign(campaign, audience)
            _campaign_sent_flash(counts)
            return redirect(url_for('crm.campaign_detail', cid=campaign.id))

        # Preview (form.preview.data)
        sample = audience[:5]
        preview = {
            'count': len(audience),
            'opted_out': sum(1 for c in audience if c.email_opt_out),
            'samples': [{
                'name': c.name, 'email': c.email,
                'opted_out': c.email_opt_out,
                'subject': render_merge(form.subject.data, c),
                'body': render_merge(form.body.data, c),
            } for c in sample],
        }

    return render_template('crm/campaign_new.html', form=form, templates=templates,
                           merge_fields=MERGE_FIELDS, preview=preview)


@crm_bp.route('/campaigns/<int:cid>')
def campaign_detail(cid):
    campaign = db.get_or_404(Campaign, cid)
    audience = _campaign_audience(campaign.audience_state, campaign.audience_org_type,
                                  campaign.audience_tag)
    return render_template('crm/campaign_detail.html', campaign=campaign,
                           audience_count=len(audience),
                           opted_out=sum(1 for c in audience if c.email_opt_out))


@crm_bp.route('/campaigns/<int:cid>/send', methods=['POST'])
def send_campaign(cid):
    """Send a saved draft campaign to its audience (reconstructed from the
    stored filters). Idempotent guard: a campaign already 'sent' is not resent."""
    campaign = db.get_or_404(Campaign, cid)
    if campaign.status == 'sent':
        flash('This campaign has already been sent.', 'warning')
        return redirect(url_for('crm.campaign_detail', cid=cid))
    audience = _campaign_audience(campaign.audience_state, campaign.audience_org_type,
                                  campaign.audience_tag)
    if not audience:
        flash('No recipients match this campaign’s audience.', 'warning')
        return redirect(url_for('crm.campaign_detail', cid=cid))
    campaign.status = 'sent'
    campaign.sent_at = _utcnow()
    db.session.flush()
    counts = _dispatch_campaign(campaign, audience)
    _campaign_sent_flash(counts)
    return redirect(url_for('crm.campaign_detail', cid=cid))


@crm_bp.route('/t/open/<token>')
def track_open(token):
    """Open-tracking pixel (public; hit by the recipient's email client)."""
    r = CampaignRecipient.query.filter_by(token=token).first()
    if r and not r.opened_at:
        r.opened_at = _utcnow()
        db.session.commit()
    return Response(_TRACKING_PIXEL, mimetype='image/gif', headers={
        'Cache-Control': 'no-store, no-cache, must-revalidate, private',
        'Pragma': 'no-cache'})


@crm_bp.route('/t/click/<token>')
def track_click(token):
    """Click-tracking redirect (public). Records the click, then forwards to the
    real destination — only ever to an absolute http(s) URL."""
    url = request.args.get('u', '')
    r = CampaignRecipient.query.filter_by(token=token).first()
    if r:
        now = _utcnow()
        if not r.clicked_at:
            r.clicked_at = now
        if not r.opened_at:        # a click implies an open
            r.opened_at = now
        db.session.commit()
    if url.startswith(('http://', 'https://')):
        return redirect(url)
    return redirect(url_for('crm.dashboard'))


def _segment_totals():
    """Org counts by state/type, for AI context (mirrors the marketing API)."""
    from sqlalchemy import func

    def grp(col):
        rows = db.session.query(col, func.count(Company.id)).group_by(col).all()
        return {(k or '—'): n for k, n in rows}
    return {'by_state': grp(Company.state), 'by_type': grp(Company.org_type)}


@crm_bp.route('/campaigns/ai', methods=['GET', 'POST'])
def ai_campaign():
    """In-CRM AI marketing agent: a goal + audience filters -> Claude drafts a
    campaign -> saved as a DRAFT for human review (never auto-sent)."""
    from app.crm import agent_service
    form = AICampaignForm()
    states = [s[0] for s in db.session.query(Company.state)
              .filter(Company.state.isnot(None)).distinct().order_by(Company.state)]
    form.state.choices = [('', 'All states')] + [(s, s) for s in states]

    configured = agent_service.is_configured()
    total_emailable = (Contact.query
                       .filter(Contact.email.isnot(None), Contact.email != '',
                               Contact.email_opt_out.isnot(True)).count())

    if form.validate_on_submit():
        if not configured:
            flash('AI drafting isn’t configured yet — set ANTHROPIC_API_KEY to '
                  'enable it.', 'warning')
            return redirect(url_for('crm.ai_campaign'))

        audience = _campaign_audience(form.state.data, form.org_type.data,
                                      form.tag.data)
        if not audience:
            flash('No recipients match those filters — adjust the audience and '
                  'try again.', 'warning')
            return render_template('crm/campaign_ai.html', form=form,
                                   configured=configured,
                                   total_emailable=total_emailable)

        sample = [{
            'first_name': (c.name or '').split()[0] if c.name else '',
            'name': c.name,
            'company': c.company.name if c.company else None,
            'city': c.company.city if c.company else None,
            'state': c.company.state if c.company else None,
            'org_type': c.company.org_type if c.company else None,
        } for c in audience[:8]]

        try:
            campaign_data, _usage = agent_service.draft_campaign(
                form.goal.data, segments=_segment_totals(),
                sample_recipients=sample, audience_count=len(audience))
        except agent_service.AgentError as e:
            flash(str(e), 'danger')
            return render_template('crm/campaign_ai.html', form=form,
                                   configured=configured,
                                   total_emailable=total_emailable)

        bits = [b for b in (form.state.data, form.org_type.data,
                            (f'tag:{form.tag.data}' if form.tag.data else '')) if b]
        campaign = Campaign(
            name=(form.name.data.strip() if form.name.data else '')
                 or campaign_data['name'],
            subject=campaign_data['subject'], body=campaign_data['body'],
            status='draft',
            audience_desc=', '.join(bits) or 'All contacts with email',
            audience_state=form.state.data or None,
            audience_org_type=form.org_type.data or None,
            audience_tag=form.tag.data or None,
            created_by=current_user_id())
        db.session.add(campaign)
        db.session.commit()
        flash('AI drafted a campaign — review it, edit if needed, then send.',
              'success')
        return redirect(url_for('crm.campaign_detail', cid=campaign.id))

    return render_template('crm/campaign_ai.html', form=form,
                           configured=configured,
                           total_emailable=total_emailable)


# ---------------------------------------------------------------------------
# Marketing hub
# ---------------------------------------------------------------------------
@crm_bp.route('/marketing')
def marketing_hub():
    contacts_total = Contact.query.count()
    emailable = Contact.query.filter(Contact.email.isnot(None),
                                     Contact.email != '',
                                     Contact.email_opt_out.isnot(True)).count()
    engaged_ids = {a.contact_id for a in
                   Activity.query.filter(Activity.kind == 'email',
                                         Activity.contact_id.isnot(None))}
    in_deals = (Contact.query.join(Deal, Deal.contact_id == Contact.id)
                .filter(~Deal.stage.in_(['Closed Won', 'Closed Lost']))
                .distinct().count())
    won = (Contact.query.join(Deal, Deal.contact_id == Contact.id)
           .filter(Deal.stage == 'Closed Won').distinct().count())
    funnel = [
        ('All contacts', contacts_total),
        ('Emailable', emailable),
        ('Engaged (emailed)', len(engaged_ids)),
        ('In open leads', in_deals),
        ('Customers (won)', won),
    ]

    campaigns = Campaign.query.order_by(Campaign.created_at.desc()).limit(5).all()
    campaign_stats = {
        'total': Campaign.query.count(),
        'sent': Campaign.query.filter_by(status='sent').count(),
        'draft': Campaign.query.filter_by(status='draft').count(),
        'recipients': CampaignRecipient.query.count(),
    }

    segments = Segment.query.order_by(Segment.name).all()
    segment_counts = {s.id: len(_campaign_audience(s.state or '',
                                                   s.org_type or '',
                                                   s.tag or ''))
                      for s in segments}

    today = date.today()
    upcoming_content = (ContentItem.query
                        .filter(ContentItem.status != 'Published',
                                ContentItem.scheduled_date.isnot(None),
                                ContentItem.scheduled_date >= today)
                        .order_by(ContentItem.scheduled_date).limit(6).all())

    grades = {'Hot': 0, 'Warm': 0, 'Cold': 0}
    all_contacts = Contact.query.all()
    for c in all_contacts:
        grades[c.lead_grade] += 1
    hot_leads = sorted((c for c in all_contacts if c.lead_grade == 'Hot'),
                       key=lambda c: -c.lead_score)[:5]

    return render_template('crm/marketing.html', funnel=funnel,
                           campaigns=campaigns, campaign_stats=campaign_stats,
                           segments=segments, segment_counts=segment_counts,
                           upcoming_content=upcoming_content, grades=grades,
                           hot_leads=hot_leads, today=today)


# ---------------------------------------------------------------------------
# Segments
# ---------------------------------------------------------------------------
@crm_bp.route('/segments')
def list_segments():
    segments = Segment.query.order_by(Segment.name).all()
    counts = {s.id: len(_campaign_audience(s.state or '', s.org_type or '',
                                           s.tag or '')) for s in segments}
    return render_template('crm/segments.html', segments=segments,
                           counts=counts)


@crm_bp.route('/segments/new', methods=['GET', 'POST'])
@crm_bp.route('/segments/<int:sid>/edit', methods=['GET', 'POST'])
def edit_segment(sid=None):
    segment = db.get_or_404(Segment, sid) if sid else None
    form = SegmentForm(obj=segment)
    states = [s[0] for s in db.session.query(Company.state)
              .filter(Company.state.isnot(None)).distinct()
              .order_by(Company.state)]
    form.state.choices = [('', 'All states')] + [(s, s) for s in states]
    if form.validate_on_submit():
        if not segment:
            segment = Segment()
            db.session.add(segment)
        segment.name = form.name.data
        segment.description = form.description.data or None
        segment.state = form.state.data or None
        segment.org_type = form.org_type.data or None
        segment.tag = form.tag.data or None
        db.session.commit()
        flash('Segment saved', 'success')
        return redirect(url_for('crm.list_segments'))
    audience = (_campaign_audience(segment.state or '', segment.org_type or '',
                                   segment.tag or '') if segment else None)
    return render_template('crm/segment_form.html', form=form, segment=segment,
                           audience=audience)


@crm_bp.route('/segments/<int:sid>/delete', methods=['POST'])
def delete_segment(sid):
    segment = db.get_or_404(Segment, sid)
    db.session.delete(segment)
    db.session.commit()
    flash('Segment deleted', 'warning')
    return redirect(url_for('crm.list_segments'))


# ---------------------------------------------------------------------------
# Content calendar
# ---------------------------------------------------------------------------
@crm_bp.route('/content')
def content_calendar():
    try:
        year = int(request.args.get('year', date.today().year))
        month = int(request.args.get('month', date.today().month))
        date(year, month, 1)
    except ValueError:
        year, month = date.today().year, date.today().month
    first = date(year, month, 1)
    prev_month = (first - timedelta(days=1)).replace(day=1)
    next_month = (first + timedelta(days=31)).replace(day=1)

    import calendar as _cal
    weeks = _cal.Calendar(firstweekday=6).monthdatescalendar(year, month)

    items = (ContentItem.query
             .filter(ContentItem.scheduled_date >= weeks[0][0],
                     ContentItem.scheduled_date <= weeks[-1][-1])
             .order_by(ContentItem.scheduled_date).all())
    by_day = {}
    for it in items:
        by_day.setdefault(it.scheduled_date, []).append(it)

    unscheduled = (ContentItem.query
                   .filter(ContentItem.scheduled_date.is_(None))
                   .order_by(ContentItem.created_at.desc()).all())

    return render_template('crm/content_calendar.html', weeks=weeks,
                           by_day=by_day, month_name=first.strftime('%B %Y'),
                           month=month, year=year, prev_month=prev_month,
                           next_month=next_month, unscheduled=unscheduled,
                           today=date.today(), channels=CONTENT_CHANNELS)


@crm_bp.route('/content/new', methods=['GET', 'POST'])
@crm_bp.route('/content/<int:iid>/edit', methods=['GET', 'POST'])
def edit_content(iid=None):
    item = db.get_or_404(ContentItem, iid) if iid else None
    form = ContentItemForm(obj=item)
    campaigns = Campaign.query.order_by(Campaign.created_at.desc()).all()
    form.campaign.choices = [(0, '— None —')] + [(c.id, c.name)
                                                 for c in campaigns]
    if request.method == 'GET':
        if item:
            form.campaign.data = item.campaign_id or 0
        elif request.args.get('date'):
            try:
                form.scheduled_date.data = date.fromisoformat(
                    request.args['date'])
            except ValueError:
                pass
    if form.validate_on_submit():
        if not item:
            item = ContentItem(owner_id=current_user_id())
            db.session.add(item)
        item.title = form.title.data
        item.channel = form.channel.data
        item.status = form.status.data
        item.scheduled_date = form.scheduled_date.data
        item.campaign_id = form.campaign.data or None
        item.body = form.body.data or None
        db.session.commit()
        flash('Content saved', 'success')
        return redirect(url_for('crm.content_calendar'))
    return render_template('crm/content_form.html', form=form, item=item)


@crm_bp.route('/content/<int:iid>/status', methods=['POST'])
def set_content_status(iid):
    item = db.get_or_404(ContentItem, iid)
    status = request.form.get('status', '')
    if status in CONTENT_STATUSES:
        item.status = status
        db.session.commit()
        flash('Status updated', 'success')
    return redirect(request.referrer or url_for('crm.content_calendar'))


@crm_bp.route('/content/<int:iid>/delete', methods=['POST'])
def delete_content(iid):
    item = db.get_or_404(ContentItem, iid)
    db.session.delete(item)
    db.session.commit()
    flash('Content deleted', 'warning')
    return redirect(url_for('crm.content_calendar'))


# ---------------------------------------------------------------------------
# AI Studio — full campaign design (targeting + email + content plan)
# ---------------------------------------------------------------------------
def _ai_context(constraints):
    """Live CRM snapshot handed to the design model."""
    from sqlalchemy import func

    def breakdown(col):
        rows = db.session.query(col, func.count(Company.id)).group_by(col).all()
        return {(k or 'unknown'): n for k, n in rows}
    return {
        'constraints': constraints,
        'contacts': Contact.query.count(),
        'emailable': Contact.query.filter(
            Contact.email.isnot(None), Contact.email != '',
            Contact.email_opt_out.isnot(True)).count(),
        'by_state': breakdown(Company.state),
        'by_type': breakdown(Company.org_type),
        'segments': [{'name': s.name, 'filters': s.filter_desc}
                     for s in Segment.query.order_by(Segment.name)],
        'recent_campaigns': [
            {'name': c.name, 'subject': c.subject}
            for c in Campaign.query.order_by(
                Campaign.created_at.desc()).limit(5)],
        'today': date.today().isoformat(),
    }


def _ai_states():
    return [s[0] for s in db.session.query(Company.state)
            .filter(Company.state.isnot(None)).distinct()
            .order_by(Company.state)]


@crm_bp.route('/ai')
def ai_studio_page():
    from app.crm import agent_service
    return render_template('crm/ai_studio.html', design=None, goal='',
                           configured=agent_service.is_configured(),
                           states=_ai_states())


@crm_bp.route('/ai/generate', methods=['POST'])
def ai_generate():
    from app.crm import agent_service
    goal = (request.form.get('goal') or '').strip()
    constraints = {
        'state': (request.form.get('state') or '').strip(),
        'org_type': (request.form.get('org_type') or '').strip(),
        'tag': (request.form.get('tag') or '').strip(),
    }
    if not goal:
        flash('Describe a campaign goal first.', 'warning')
        return redirect(url_for('crm.ai_studio_page'))
    try:
        design = agent_service.design_campaign(goal, _ai_context(constraints))
    except agent_service.AgentError as exc:
        flash(str(exc), 'danger')
        return redirect(url_for('crm.ai_studio_page'))

    aud = design.get('campaign', {}).get('audience', {})
    audience = _campaign_audience(aud.get('state', ''),
                                  aud.get('org_type', ''), aud.get('tag', ''))
    return render_template(
        'crm/ai_studio.html', design=design, goal=goal,
        configured=True, states=_ai_states(),
        audience_count=len(audience),
        opted_out=sum(1 for c in audience if c.email_opt_out),
        design_json=json.dumps(design), merge_fields=MERGE_FIELDS,
        today=date.today())


@crm_bp.route('/ai/apply', methods=['POST'])
def ai_apply():
    try:
        design = json.loads(request.form.get('design', ''))
        camp = design['campaign']
        aud = camp.get('audience', {})
    except (ValueError, KeyError, TypeError):
        flash('Could not read the design — generate it again.', 'danger')
        return redirect(url_for('crm.ai_studio_page'))

    bits = [b for b in (aud.get('state', ''), aud.get('org_type', ''),
                        (f"tag:{aud['tag']}" if aud.get('tag') else '')) if b]
    campaign = Campaign(
        name=camp.get('name') or 'AI campaign',
        subject=camp.get('subject') or '', body=camp.get('body') or '',
        status='draft', created_by=current_user_id(),
        audience_desc=', '.join(bits) or 'All contacts with email',
        audience_state=aud.get('state') or None,
        audience_org_type=aud.get('org_type') or None,
        audience_tag=aud.get('tag') or None)
    db.session.add(campaign)
    db.session.flush()

    created_items = 0
    for item in design.get('content_plan', []):
        channel = item.get('channel')
        if channel not in CONTENT_CHANNELS:
            continue
        days = item.get('days_from_now')
        scheduled = (date.today() + timedelta(days=max(int(days), 0))
                     if isinstance(days, int) else None)
        db.session.add(ContentItem(
            title=(item.get('title') or 'Untitled')[:200],
            channel=channel, status='Idea', scheduled_date=scheduled,
            body=item.get('notes') or None, campaign_id=campaign.id,
            owner_id=current_user_id()))
        created_items += 1
    db.session.commit()
    flash(f'Draft campaign "{campaign.name}" created with {created_items} '
          'content item(s) on the calendar. Review before sending.', 'success')
    return redirect(url_for('crm.campaign_detail', cid=campaign.id))


# ===========================================================================
# BDR lead lifecycle + AI BDR agent (propose → human approval → execute)
# ===========================================================================
def _due_leads(limit=200, owner_id=None):
    """Open leads that need a touch now: a next action that's due, or a lead
    that's never been contacted. Soonest-due first."""
    today = _utcnow().date()
    q = Contact.query.filter(Contact.lead_status.in_(LEAD_OPEN_STATUSES))
    if owner_id:
        q = q.filter(Contact.owner_id == owner_id)
    q = q.filter(or_(
        Contact.next_action_at <= today,
        and_(Contact.next_action_at.is_(None), Contact.last_contacted_at.is_(None)),
    ))
    return (q.order_by(Contact.next_action_at.is_(None), Contact.next_action_at,
                       Contact.name).limit(limit).all())


def _lead_context(c):
    """Fact-only context for the agent — never invents anything."""
    recent = [a.description for a in
              Activity.query.filter_by(contact_id=c.id)
              .order_by(Activity.created_at.desc()).limit(4).all()]
    co = c.company
    return {
        'lead_id': c.id,
        'name': c.name,
        'first_name': (c.name or '').split(' ')[0],
        'company': co.name if co else None,
        'city': co.city if co else None,
        'state': co.state if co else None,
        'org_type': co.org_type if co else None,
        'lead_status': c.lead_status,
        'days_since_contact': c.days_since_contact,
        'recent': recent,
    }


@crm_bp.route('/agent')
def agent_console():
    from app.crm import agent_service
    pending = (CrmAgentAction.query.filter_by(status='pending')
               .order_by(CrmAgentAction.created_at.desc()).all())
    recent = (CrmAgentAction.query.filter(CrmAgentAction.status != 'pending')
              .order_by(CrmAgentAction.reviewed_at.desc()).limit(10).all())
    cold_count = Contact.query.filter(
        Contact.lead_status == 'New', Contact.last_contacted_at.is_(None),
        Contact.email.isnot(None), Contact.email != '').count()
    return render_template('crm/agent.html',
                           pending=pending, recent=recent,
                           due_count=len(_due_leads(limit=500)),
                           cold_count=cold_count,
                           ai_configured=agent_service.is_configured())


@crm_bp.route('/agent/run', methods=['POST'])
def agent_run():
    """Have the agent draft follow-ups for due leads as PENDING proposals."""
    from app.crm import agent_service
    if not agent_service.is_configured():
        flash('AI drafting isn’t configured yet (set ANTHROPIC_API_KEY).', 'warning')
        return redirect(url_for('crm.agent_console'))

    # Don't re-propose for a lead that already has a pending follow-up.
    pending_ids = {a.contact_id for a in CrmAgentAction.query
                   .filter_by(status='pending', action_type='follow_up_email').all()}
    leads = [c for c in _due_leads(limit=10)
             if c.id not in pending_ids and c.email and not c.email_opt_out]
    if not leads:
        flash('No leads are due for follow-up right now.', 'info')
        return redirect(url_for('crm.agent_console'))

    sender = current_user.username if current_user.is_authenticated else ''
    try:
        drafts, _usage = agent_service.draft_followups(
            [_lead_context(c) for c in leads], sender_name=sender)
    except agent_service.AgentError as e:
        flash(str(e), 'danger')
        return redirect(url_for('crm.agent_console'))

    by_id = {c.id: c for c in leads}
    created = 0
    for d in drafts:
        c = by_id.get(d.get('lead_id'))
        if not c:
            continue
        db.session.add(CrmAgentAction(
            action_type='follow_up_email', status='pending',
            contact_id=c.id, company_id=c.company_id,
            title=(d.get('title') or f'Follow up with {c.name}')[:200],
            rationale=d.get('rationale'),
            payload_json=json.dumps({'subject': d.get('subject', ''),
                                     'body': d.get('body', '')}),
            created_by_id=current_user_id()))
        created += 1
    db.session.commit()
    if created:
        flash(f'The BDR agent proposed {created} follow-up'
              f'{"s" if created != 1 else ""} for your review.', 'success')
    else:
        flash('The agent didn’t return any usable drafts. Try again.', 'warning')
    return redirect(url_for('crm.agent_console'))


@crm_bp.route('/agent/scout', methods=['POST'])
def agent_scout():
    """Have the agent pick the best cold leads to start prospecting (proposals).
    Works only over real leads already in the CRM — never invents organizations."""
    from app.crm import agent_service
    if not agent_service.is_configured():
        flash('AI drafting isn’t configured yet (set ANTHROPIC_API_KEY).', 'warning')
        return redirect(url_for('crm.agent_console'))

    proposed = {a.contact_id for a in CrmAgentAction.query
                .filter(CrmAgentAction.status == 'pending').all()}
    cold = (Contact.query.filter(Contact.lead_status == 'New',
                                 Contact.last_contacted_at.is_(None),
                                 Contact.email.isnot(None), Contact.email != '')
            .order_by(Contact.id).limit(25).all())
    cold = [c for c in cold if c.id not in proposed and not c.email_opt_out]
    if not cold:
        flash('No new cold leads to scout right now.', 'info')
        return redirect(url_for('crm.agent_console'))

    def _ctx(c):
        co = c.company
        return {'lead_id': c.id, 'name': c.name,
                'company': co.name if co else None,
                'city': co.city if co else None, 'state': co.state if co else None,
                'org_type': co.org_type if co else None,
                'website': co.website if co else None}
    try:
        picks, _u = agent_service.scout_leads([_ctx(c) for c in cold])
    except agent_service.AgentError as e:
        flash(str(e), 'danger')
        return redirect(url_for('crm.agent_console'))

    by_id = {c.id: c for c in cold}
    created = 0
    for p in picks:
        c = by_id.get(p.get('lead_id'))
        if not c:
            continue
        db.session.add(CrmAgentAction(
            action_type='scout', status='pending',
            contact_id=c.id, company_id=c.company_id,
            title=(p.get('title') or f'Prospect {c.company.name if c.company else c.name}')[:200],
            rationale=p.get('rationale'),
            payload_json=json.dumps({'angle': p.get('angle', '')}),
            created_by_id=current_user_id()))
        created += 1
    db.session.commit()
    if created:
        flash(f'The agent surfaced {created} lead{"s" if created != 1 else ""} to prospect — review below.',
              'success')
    else:
        flash('The agent didn’t surface any picks. Try again.', 'warning')
    return redirect(url_for('crm.agent_console'))


@crm_bp.route('/agent/campaign', methods=['POST'])
def agent_campaign():
    """Agent drafts a campaign for the largest emailable segment as a proposal.
    Approving it creates a DRAFT campaign for the human to review and send (mass
    send stays a deliberate second step)."""
    from app.crm import agent_service
    from sqlalchemy import func
    if not agent_service.is_configured():
        flash('AI drafting isn’t configured yet (set ANTHROPIC_API_KEY).', 'warning')
        return redirect(url_for('crm.agent_console'))

    row = (db.session.query(Company.state, func.count(Contact.id))
           .join(Contact, Contact.company_id == Company.id)
           .filter(Contact.email.isnot(None), Contact.email != '',
                   Company.state.isnot(None), Company.state != '')
           .group_by(Company.state).order_by(func.count(Contact.id).desc()).first())
    if not row or not row[1]:
        flash('No emailable segments to build a campaign from yet.', 'info')
        return redirect(url_for('crm.agent_console'))
    state, audience_count = row[0], row[1]

    goal = (f'Introduce YardHarvest to community gardens, urban-ag nonprofits, and '
            f'parks programs in {state}, and invite a 15-minute intro call.')
    try:
        camp, _u = agent_service.draft_campaign(goal, segments=_segment_totals(),
                                                audience_count=audience_count)
    except agent_service.AgentError as e:
        flash(str(e), 'danger')
        return redirect(url_for('crm.agent_console'))

    db.session.add(CrmAgentAction(
        action_type='campaign', status='pending',
        title=(camp.get('name') or f'Campaign — {state}')[:200],
        rationale=f'{audience_count} emailable contacts in {state} — the largest segment to activate.',
        payload_json=json.dumps({
            'name': camp.get('name'), 'subject': camp.get('subject'),
            'body': camp.get('body'), 'audience_state': state,
            'audience_desc': state, 'audience_count': audience_count}),
        created_by_id=current_user_id()))
    db.session.commit()
    flash(f'The agent drafted a campaign for {state} ({audience_count} contacts) — review below.',
          'success')
    return redirect(url_for('crm.agent_console'))


@crm_bp.route('/agent/actions/<int:aid>/approve', methods=['POST'])
def agent_action_approve(aid):
    """Approve a proposal — this is where the action actually executes."""
    action = db.get_or_404(CrmAgentAction, aid)
    if action.status != 'pending':
        flash('That proposal was already handled.', 'info')
        return redirect(url_for('crm.agent_console'))

    if action.action_type == 'campaign':
        # Materialize a DRAFT campaign; the human reviews recipients and sends.
        p = action.payload or {}
        campaign = Campaign(
            name=(p.get('name') or 'Untitled campaign')[:160],
            subject=(p.get('subject') or '')[:200], body=p.get('body') or '',
            status='draft', created_by=current_user_id(),
            audience_state=p.get('audience_state') or None,
            audience_org_type=p.get('audience_org_type') or None,
            audience_tag=p.get('audience_tag') or None,
            audience_desc=p.get('audience_desc') or 'All contacts with email')
        db.session.add(campaign)
        db.session.flush()
        action.status = 'executed'
        action.result = f'Created draft campaign #{campaign.id}'
        action.reviewed_at = _utcnow()
        action.reviewed_by_id = current_user_id()
        db.session.commit()
        flash('Draft campaign created — review the audience and send when ready.', 'success')
        return redirect(url_for('crm.campaign_detail', cid=campaign.id))

    contact = db.session.get(Contact, action.contact_id)
    if not contact:
        action.status = 'failed'
        action.result = 'Contact no longer exists'
        action.reviewed_at = _utcnow()
        action.reviewed_by_id = current_user_id()
        db.session.commit()
        flash('That contact no longer exists.', 'danger')
        return redirect(url_for('crm.agent_console'))

    if action.action_type == 'scout':
        # Promote a cold, scouted lead into the active working queue so the
        # engagement agent can then draft the first touch.
        angle = (action.payload or {}).get('angle')
        if (contact.lead_status or 'New') == 'New':
            contact.lead_status = 'Working'
        if not contact.owner_id:
            contact.owner_id = current_user_id()
        if not contact.source:
            contact.source = 'Scout'
        contact.next_action_at = _utcnow().date()
        if angle and not contact.next_action_note:
            contact.next_action_note = angle[:200]
        log_activity('updated', (f'Scouted → working' + (f': {angle}' if angle else ''))[:400],
                     contact_id=contact.id, company_id=contact.company_id)
        action.status = 'executed'
        action.result = f'Started working {contact.name}'
        action.reviewed_at = _utcnow()
        action.reviewed_by_id = current_user_id()
        db.session.commit()
        flash(f'{contact.name} is now in your working queue — draft an intro from the queue.',
              'success')
        return redirect(url_for('crm.agent_console'))

    if action.action_type != 'follow_up_email':
        flash('That proposal type can’t be executed yet.', 'warning')
        return redirect(url_for('crm.agent_console'))

    # The reviewer may have edited the draft before approving.
    subject_raw = (request.form.get('subject') or '').strip()
    body_raw = (request.form.get('body') or '').strip()
    subject = render_merge(subject_raw, contact)
    body = render_merge(body_raw, contact)
    recipient = contact.email if not contact.email_opt_out else None
    sent = smtp_send(recipient, subject, body)
    verb = 'Email sent' if sent else 'Email logged'

    log_activity('email', f'{verb} (BDR agent): {subject}',
                 contact_id=contact.id, company_id=contact.company_id)
    db.session.add(Note(
        content=f'[{verb} to {recipient or "n/a"}] {subject}\n\n{body}',
        contact_id=contact.id))

    # Advance the lifecycle: contacted now, nudge status forward, schedule the
    # next touch so the lead resurfaces in the queue if they go quiet.
    contact.last_contacted_at = _utcnow()
    if (contact.lead_status or 'New') == 'New':
        contact.lead_status = 'Working'
    contact.next_action_at = _utcnow().date() + timedelta(days=4)
    contact.next_action_note = 'Awaiting reply to follow-up'

    action.status = 'executed'
    action.result = f'{verb} to {recipient or "n/a"}'
    action.payload_json = json.dumps({'subject': subject_raw, 'body': body_raw})
    action.reviewed_at = _utcnow()
    action.reviewed_by_id = current_user_id()
    db.session.commit()
    flash(f'{verb}. {contact.name} is now “{contact.lead_status}”, next touch in 4 days.',
          'success')
    return redirect(url_for('crm.agent_console'))


@crm_bp.route('/agent/actions/<int:aid>/reject', methods=['POST'])
def agent_action_reject(aid):
    action = db.get_or_404(CrmAgentAction, aid)
    if action.status == 'pending':
        action.status = 'rejected'
        action.result = (request.form.get('reason') or 'Dismissed by reviewer')[:400]
        action.reviewed_at = _utcnow()
        action.reviewed_by_id = current_user_id()
        db.session.commit()
    flash('Proposal dismissed.', 'info')
    return redirect(url_for('crm.agent_console'))


@crm_bp.route('/leads')
def list_leads():
    """The BDR work queue — open leads to work, soonest-due first."""
    status = request.args.get('status', '')
    view = request.args.get('view', 'due')   # 'due' | 'all'
    today = _utcnow().date()
    q = Contact.query
    if status in LEAD_STATUSES:
        q = q.filter(Contact.lead_status == status)
    if view == 'due':
        q = q.filter(Contact.lead_status.in_(LEAD_OPEN_STATUSES)).filter(or_(
            Contact.next_action_at <= today,
            and_(Contact.next_action_at.is_(None), Contact.last_contacted_at.is_(None)),
        ))
    leads = (q.order_by(Contact.next_action_at.is_(None), Contact.next_action_at,
                        Contact.name).limit(200).all())
    counts = {s: Contact.query.filter_by(lead_status=s).count() for s in LEAD_STATUSES}
    return render_template('crm/leads.html', leads=leads, status=status, view=view,
                           statuses=LEAD_STATUSES, owners=CrmUser.query.order_by(CrmUser.username).all(),
                           counts=counts, due_count=len(_due_leads(limit=500)), today=today)


@crm_bp.route('/contacts/<int:cid>/lead', methods=['POST'])
def set_lead_fields(cid):
    """Set lead status / owner / source / next action on a contact."""
    c = db.get_or_404(Contact, cid)
    old = c.lead_status
    status = request.form.get('lead_status')
    if status in LEAD_STATUSES:
        c.lead_status = status
    c.owner_id = request.form.get('owner_id', type=int) or None
    src = (request.form.get('source') or '').strip()
    c.source = src[:60] or None
    na = (request.form.get('next_action_at') or '').strip()
    try:
        c.next_action_at = date.fromisoformat(na) if na else None
    except ValueError:
        pass
    c.next_action_note = (request.form.get('next_action_note') or '').strip()[:200] or None
    if c.lead_status != old:
        log_activity('updated', f'Lead status: {old} → {c.lead_status}',
                     contact_id=c.id, company_id=c.company_id)
    db.session.commit()
    flash('Lead updated.', 'success')
    return redirect(request.referrer or url_for('crm.view_contact', cid=cid))


@crm_bp.route('/contacts/<int:cid>/log', methods=['POST'])
def log_touch(cid):
    """Log a call or meeting (with outcome) and advance the contact clock."""
    c = db.get_or_404(Contact, cid)
    touch = request.form.get('touch', 'call')   # 'call' | 'meeting'
    outcome = (request.form.get('outcome') or '').strip()
    note = (request.form.get('note') or '').strip()
    label = 'Meeting' if touch == 'meeting' else 'Call'
    desc = f'{label} logged'
    if outcome:
        desc += f' — {outcome}'
    if note:
        desc += f': {note}'
    log_activity('meeting' if touch == 'meeting' else 'call', desc[:400],
                 contact_id=c.id, company_id=c.company_id)
    c.last_contacted_at = _utcnow()
    if (c.lead_status or 'New') == 'New':
        c.lead_status = 'Working'
    c.next_action_at = _utcnow().date() + timedelta(days=7 if touch == 'meeting' else 3)
    db.session.commit()
    flash(f'{label} logged.', 'success')
    return redirect(request.referrer or url_for('crm.view_contact', cid=cid))


@crm_bp.route('/contacts/<int:cid>/qualify', methods=['POST'])
def qualify_lead(cid):
    """Mark a lead Qualified and spin up a Deal (the handoff into the pipeline)."""
    c = db.get_or_404(Contact, cid)
    c.lead_status = 'Qualified'
    default_title = f'{c.company.name if c.company else c.name} — Garden Pro'
    title = (request.form.get('title') or default_title).strip()[:200]
    deal = Deal(title=title, stage='Lead', contact_id=c.id, company_id=c.company_id,
                owner_id=c.owner_id, created_at=_utcnow())
    db.session.add(deal)
    db.session.flush()
    log_activity('stage_change', f'Qualified → created lead “{deal.title}”',
                 contact_id=c.id, company_id=c.company_id, deal_id=deal.id)
    db.session.commit()
    flash('Lead qualified — a deal was created in the pipeline.', 'success')
    return redirect(url_for('crm.deal_detail', did=deal.id))
