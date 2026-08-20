"""The funnel baseline — the numbers you need before tuning anything.

Every recommendation in the conversion plan presumes emails that may never
have left the building: the autonomous cycle is gated on reply capture being
healthy, and it fails closed. Rather than ask the operator to run six SQL
queries against Render Postgres, this module computes them once and renders
the same block two ways — ``flask crm baseline`` in a shell, and a collapsed
panel on the agent console.

Read-only by construction: nothing here writes, sends, or calls a model.
"""
from datetime import timedelta

import click
from flask import current_app
from sqlalchemy import func

from app import db
from app.crm import crm_bp

# Shared inbox / role addresses: mail to these reaches "whoever checks it",
# which is why a named human is the unit that matters for supply, not a row.
GENERIC_LOCALPARTS = (
    'info', 'office', 'hello', 'admin', 'contact', 'mail', 'email', 'team',
    'inquiries', 'enquiries', 'general', 'support', 'help', 'staff',
    'volunteer', 'volunteers', 'garden', 'gardens', 'membership', 'members',
)


def _is_generic(contact):
    """True when this address reaches a role, not a person."""
    from app.crm.agent_service import is_placeholder_name
    addr = (contact.email or '').strip().lower()
    local = addr.split('@')[0] if '@' in addr else addr
    if local in GENERIC_LOCALPARTS:
        return True
    return is_placeholder_name(contact.name)


def build_baseline(days=30):
    """Compute the whole baseline as plain data. Never raises on a missing
    product-side table — a CRM-only deployment still gets the outreach half."""
    from app.crm.models import (AgentSettings, Company, Contact, CrmAgentAction,
                                CrmAgentRun, CrmInboundReply, _utcnow)  # noqa: F401
    from app.crm import autonomy as A

    now = _utcnow()
    since = now - timedelta(days=days)
    out = {'days': days, 'generated_at': now}

    # ---- is the sender actually sending? ---------------------------------
    sends = (db.session.query(func.date(CrmAgentAction.reviewed_at),
                              func.count(CrmAgentAction.id))
             .filter(CrmAgentAction.status == 'executed',
                     CrmAgentAction.action_type == 'follow_up_email',
                     CrmAgentAction.reviewed_at >= since)
             .group_by(func.date(CrmAgentAction.reviewed_at))
             .order_by(func.date(CrmAgentAction.reviewed_at).desc()).all())
    out['sends_by_day'] = [(str(d), n) for d, n in sends]
    out['sends_total'] = sum(n for _, n in sends)
    out['sends_auto'] = (CrmAgentAction.query
                         .filter(CrmAgentAction.status == 'executed',
                                 CrmAgentAction.action_type == 'follow_up_email',
                                 CrmAgentAction.auto_executed.is_(True),
                                 CrmAgentAction.reviewed_at >= since).count())

    # ---- did anyone write back? ------------------------------------------
    out['replies'] = dict(
        db.session.query(CrmInboundReply.classification,
                         func.count(CrmInboundReply.id))
        .filter(CrmInboundReply.created_at >= since)
        .group_by(CrmInboundReply.classification).all())
    out['replies_total'] = sum(out['replies'].values())

    # ---- meetings ---------------------------------------------------------
    try:
        from app.models import Booking
        out['bookings_total'] = Booking.query.count()
        out['bookings_recent'] = (Booking.query
                                  .filter(Booking.created_at >= since).count())
    except Exception:  # noqa: BLE001 — CRM-only deployment
        out['bookings_total'] = out['bookings_recent'] = None

    # ---- the thing we are actually selling -------------------------------
    try:
        from app.models import CommunityGarden, GardenSubscription
        out['gardens_total'] = CommunityGarden.query.count()
        out['subs_by_status'] = dict(
            db.session.query(GardenSubscription.status,
                             func.count(GardenSubscription.id))
            .group_by(GardenSubscription.status).all())
        out['subs_total'] = sum(out['subs_by_status'].values())
    except Exception:  # noqa: BLE001
        out['gardens_total'] = out['subs_total'] = None
        out['subs_by_status'] = {}

    settings = AgentSettings.get()
    out['match_matched'] = settings.last_match_matched
    out['match_total'] = settings.last_match_total
    out['match_run_at'] = settings.last_match_run_at
    out['platform_status'] = dict(
        db.session.query(Contact.platform_status, func.count(Contact.id))
        .filter(Contact.platform_status.isnot(None))
        .group_by(Contact.platform_status).all())

    # ---- supply: who can we actually email, and are they decision-makers? -
    emailable = (Contact.query
                 .filter(Contact.email.isnot(None), Contact.email != '',
                         Contact.email_opt_out.is_(False))
                 .join(Company, Contact.company_id == Company.id, isouter=True)
                 .add_columns(Company.org_type).all())
    supply = {}
    for contact, org_type in emailable:
        key = org_type or '(untyped)'
        row = supply.setdefault(key, {'named': 0, 'generic': 0})
        row['generic' if _is_generic(contact) else 'named'] += 1
    out['supply'] = dict(sorted(supply.items(),
                                key=lambda kv: -(kv[1]['named'] + kv[1]['generic'])))
    out['supply_named'] = sum(v['named'] for v in supply.values())
    out['supply_generic'] = sum(v['generic'] for v in supply.values())

    # Runway: never-contacted leads we could still start, over the daily pace.
    cold = (Contact.query
            .filter(Contact.lead_status == 'New',
                    Contact.last_contacted_at.is_(None),
                    Contact.email.isnot(None), Contact.email != '',
                    Contact.email_opt_out.is_(False)).count())
    cap = max(1, int(settings.daily_send_cap or 15))
    out['cold_pool'] = cold
    out['runway_days'] = round(cold / cap, 1)

    # ---- can it run at all? ----------------------------------------------
    local_now = A.local_now(settings)
    out['gates'] = A.cycle_gates(settings, local_now)
    out['autonomy_enabled'] = bool(settings.autonomy_enabled)
    out['paused_reason'] = settings.paused_reason
    out['last_reply_poll_ok_at'] = settings.last_reply_poll_ok_at
    out['imap_last_error'] = settings.imap_last_error
    out['last_cycle_date'] = settings.last_cycle_date
    out['sends_today'] = A.sends_today(settings, local_now)
    out['daily_send_cap'] = settings.daily_send_cap

    last_tick = (CrmAgentRun.query.order_by(CrmAgentRun.created_at.desc()).first())
    out['last_run_at'] = last_tick.created_at if last_tick else None
    out['ai_spend_30d'] = float(
        db.session.query(func.coalesce(func.sum(CrmAgentRun.cost_usd), 0))
        .filter(CrmAgentRun.created_at >= since).scalar() or 0)

    # ---- which mailbox are we reading? -----------------------------------
    # Whether this is a dedicated sales inbox or also receives vendor mail
    # decides how aggressively unmatched replies may be surfaced.
    cfg = current_app.config
    out['imap_user'] = (cfg.get('CRM_IMAP_USER') or cfg.get('CRM_FROM_EMAIL')
                        or '(unset)')
    out['imap_host'] = cfg.get('CRM_IMAP_HOST') or '(unset)'
    out['imap_mailbox'] = cfg.get('CRM_IMAP_MAILBOX') or 'INBOX'

    # The single question this whole command exists to answer.
    out['sender_live'] = bool(out['sends_total']) and not out['gates']
    return out


def render_text(b):
    """The same block, as something you can paste into a message."""
    L = []
    A_ = L.append
    A_('YardHarvest CRM — funnel baseline'
       f' ({b["generated_at"]:%Y-%m-%d %H:%M} UTC, last {b["days"]} days)')
    A_('=' * 64)
    A_('')
    A_(f'SENDER LIVE: {"YES" if b["sender_live"] else "NO"}')
    if b['gates']:
        for g in b['gates']:
            A_(f'  blocked: {g}')
    A_(f'  autonomy_enabled={b["autonomy_enabled"]}'
       f' paused={b["paused_reason"] or "no"}'
       f' sends_today={b["sends_today"]}/{b["daily_send_cap"]}')
    A_(f'  last reply poll OK: {b["last_reply_poll_ok_at"] or "never"}'
       + (f'  |  IMAP error: {b["imap_last_error"]}' if b['imap_last_error'] else ''))
    A_(f'  last agent run: {b["last_run_at"] or "never"}')
    A_(f'  mailbox polled: {b["imap_user"]} @ {b["imap_host"]}/{b["imap_mailbox"]}')
    A_('')
    A_(f'SENDS ({b["days"]}d): {b["sends_total"]} total, {b["sends_auto"]} unattended')
    for d, n in b['sends_by_day'][:10]:
        A_(f'  {d}  {n}')
    if not b['sends_by_day']:
        A_('  (none — nothing has been sent)')
    A_('')
    A_(f'REPLIES ({b["days"]}d): {b["replies_total"]}')
    for k, n in sorted(b['replies'].items(), key=lambda kv: -kv[1]):
        A_(f'  {k or "(unclassified)"}: {n}')
    A_(f'MEETINGS: {b["bookings_total"]} all time, {b["bookings_recent"]} in {b["days"]}d')
    A_('')
    A_(f'PRODUCT: {b["gardens_total"]} gardens, {b["subs_total"]} subscription rows')
    for k, n in sorted(b['subs_by_status'].items()):
        A_(f'  {k}: {n}')
    if b['subs_total'] == 0:
        A_('  (nobody is on the trial path yet — the cold CTA is what creates the first one)')
    if b['match_total'] is not None:
        A_(f'  matched to a CRM contact: {b["match_matched"]}/{b["match_total"]}'
           f' (last run {b["match_run_at"] or "never"})')
    for k, n in sorted(b['platform_status'].items()):
        A_(f'  contacts marked {k}: {n}')
    A_('')
    A_(f'SUPPLY: {b["supply_named"]} named humans, {b["supply_generic"]} shared inboxes')
    for org, row in b['supply'].items():
        A_(f'  {org}: {row["named"]} named / {row["generic"]} generic')
    A_(f'  cold pool {b["cold_pool"]} leads = {b["runway_days"]} days of runway'
       f' at {b["daily_send_cap"]}/day')
    A_('')
    A_(f'AI SPEND ({b["days"]}d): ${b["ai_spend_30d"]:.2f}')
    return '\n'.join(L)


@crm_bp.cli.command('baseline')
@click.option('--days', default=30, show_default=True,
              help='Window for the send/reply/spend counts.')
def baseline_command(days):
    """Print the funnel baseline (read-only)."""
    click.echo(render_text(build_baseline(days=days)))


# The ICP backfill command lives with its logic in app.crm.icp; registered
# here so every CRM CLI command is hung off the blueprint in one place.
from app.crm import icp as _icp        # noqa: E402
_icp.register_cli(crm_bp)
