"""Flask CLI commands for scheduled tasks."""
import logging
import click
from flask.cli import with_appcontext
from datetime import datetime, timezone, timedelta

log = logging.getLogger(__name__)


def register_cli(app):
    """Register CLI commands with the Flask app."""
    app.cli.add_command(garden_trial_lifecycle)
    app.cli.add_command(analytics_cleanup)
    app.cli.add_command(crm_set_password)
    app.cli.add_command(publish_due_facebook_posts)
    app.cli.add_command(crm_daily)
    app.cli.add_command(crm_export)
    app.cli.add_command(indexnow_submit)
    app.cli.add_command(crm_agent_tick)
    app.cli.add_command(crm_agent_cycle)
    app.cli.add_command(crm_agent_poll)


@click.command('crm-set-password')
@click.argument('username')
@with_appcontext
def crm_set_password(username):
    """Set (or create) a CRM user's password.

    The new password is read from the CRM_NEW_PASSWORD environment variable so
    it never appears on the command line or in process/CI logs. If the user
    does not exist it is created with role 'admin'.

    Usage:  CRM_NEW_PASSWORD=... flask crm-set-password admin
    """
    import os
    from app import db
    from app.crm.models import CrmUser

    new_password = os.environ.get('CRM_NEW_PASSWORD', '')
    if not new_password:
        raise click.ClickException('CRM_NEW_PASSWORD environment variable is not set.')

    user = CrmUser.query.filter_by(username=username).first()
    if user:
        user.set_password(new_password)
        action = 'updated'
    else:
        user = CrmUser(username=username, role='admin')
        user.set_password(new_password)
        db.session.add(user)
        action = 'created (role=admin)'
    db.session.commit()
    # Never echo the password itself.
    click.echo(f"CRM user '{username}' password {action}.")


@click.command('garden-trial-lifecycle')
@with_appcontext
def garden_trial_lifecycle():
    """Daily task: expire trials, send onboarding emails at day 3/7/12/14/21."""
    run_garden_trial_lifecycle()


def run_garden_trial_lifecycle():
    """The trial-lifecycle work as a plain callable.

    Split out of the click command so the agent heartbeat can run it too:
    Render has no free cron instance type, so the cron declared in
    render.yaml was never provisioned and nothing was running this.
    """
    from app import db
    from app.models import CommunityGarden, GardenSubscription, as_utc

    now = datetime.now(timezone.utc)
    today = now.date()

    # 1. Expire ended trials
    expired = GardenSubscription.query.filter(
        GardenSubscription.status == 'trialing',
        GardenSubscription.trial_end <= now,
    ).all()
    for sub in expired:
        sub.status = 'expired'
        garden = db.session.get(CommunityGarden, sub.garden_id)
        if garden:
            garden.subscription_status = 'expired'
        log.info('Trial expired for garden_id=%d', sub.garden_id)
    if expired:
        db.session.commit()
        click.echo(f'Expired {len(expired)} trial(s)')

    # 2. Expire cancelled subscriptions past their period end
    cancelled = GardenSubscription.query.filter(
        GardenSubscription.status == 'active',
        GardenSubscription.cancel_at_period_end == True,
        GardenSubscription.current_period_end <= now,
    ).all()
    for sub in cancelled:
        sub.status = 'expired'
        garden = db.session.get(CommunityGarden, sub.garden_id)
        if garden:
            garden.subscription_status = 'expired'
        log.info('Cancelled subscription expired for garden_id=%d', sub.garden_id)
    if cancelled:
        db.session.commit()
        click.echo(f'Expired {len(cancelled)} cancelled subscription(s)')

    # 3. Send onboarding emails based on trial_start date
    from app.email_service import (
        send_garden_trial_progress,
        send_garden_trial_halfway,
        send_garden_trial_expiring,
        send_garden_trial_ended,
        send_garden_trial_reengagement,
    )
    from app.sms_service import send_garden_trial_expiring_sms, send_garden_trial_ended_sms

    active_trials = GardenSubscription.query.filter(
        GardenSubscription.trial_start.isnot(None),
    ).all()

    # The drip ladder: (day, required status, sender key). Instead of exact-day
    # matching (a missed heartbeat day skipped that email forever), each sub
    # remembers the highest drip day already sent (last_drip_day) and we send
    # the HIGHEST due step per run — so after a 5-day outage the day-3 email
    # goes today and day-7 tomorrow, never a burst of every missed step.
    def _drip_send(day, sub, garden, organizer):
        billing_url = f'{_get_site_url()}/gardens/{garden.public_id}/billing'
        if day == 3:
            send_garden_trial_progress(garden, organizer)
            click.echo(f'Day 3 email sent for garden {garden.name}')
        elif day == 7:
            send_garden_trial_halfway(garden, organizer)
            click.echo(f'Day 7 email sent for garden {garden.name}')
        elif day == 12:
            send_garden_trial_expiring(garden, organizer)
            if organizer.sms_opt_in and organizer.phone_number:
                send_garden_trial_expiring_sms(organizer.phone_number, garden.name, billing_url)
            click.echo(f'Day 12 email+SMS sent for garden {garden.name}')
        elif day == 14:
            send_garden_trial_ended(garden, organizer)
            if organizer.sms_opt_in and organizer.phone_number:
                send_garden_trial_ended_sms(organizer.phone_number, garden.name, billing_url)
            click.echo(f'Day 14 email+SMS sent for garden {garden.name}')
        elif day == 21:
            send_garden_trial_reengagement(garden, organizer)
            click.echo(f'Day 21 re-engagement email sent for garden {garden.name}')

    DRIP_LADDER = (
        (3, 'trialing'),
        (7, 'trialing'),
        (12, 'trialing'),
        (14, 'expired'),   # depends on the expiry step above having run first
        (21, 'expired'),
    )

    drip_dirty = False
    for sub in active_trials:
        try:
            trial_start = as_utc(sub.trial_start)
            if not trial_start:
                continue
            days_since = (now - trial_start).days
            garden = db.session.get(CommunityGarden, sub.garden_id)
            if not garden:
                continue
            organizer = garden.organizer

            already = sub.last_drip_day or 0
            due = [d for d, status in DRIP_LADDER
                   if already < d <= days_since and sub.status == status]
            if not due:
                continue
            day = max(due)  # one email per run per sub; skips superseded steps
            _drip_send(day, sub, garden, organizer)
            sub.last_drip_day = day
            drip_dirty = True
        except Exception as e:
            log.error('Error sending trial email for garden_id=%d: %s', sub.garden_id, e)
    if drip_dirty:
        db.session.commit()

    # 4. Day-2 nudge for gardens that never started a trial: "start your free
    # 14-day trial". Send-once via CommunityGarden.trial_nudge_sent_at; the
    # >=2-days filter (rather than an exact-day match) means a missed heartbeat
    # can't skip a garden forever.
    try:
        from app.email_service import send_garden_trial_nudge
        nudge_gardens = CommunityGarden.query.filter(
            CommunityGarden.trial_nudge_sent_at.is_(None),
            CommunityGarden.is_active == True,  # noqa: E712
            CommunityGarden.created_at <= now - timedelta(days=2),
        ).all()
        nudged = 0
        for garden in nudge_gardens:
            if garden.subscription is not None:
                continue
            organizer = garden.organizer
            if not organizer or not organizer.email:
                continue
            try:
                send_garden_trial_nudge(garden, organizer)
                garden.trial_nudge_sent_at = now
                nudged += 1
            except Exception as e:
                log.error('Trial nudge failed for garden_id=%d: %s', garden.id, e)
        if nudged:
            db.session.commit()
            click.echo(f'Sent {nudged} trial nudge(s)')
    except Exception as e:
        log.error('Trial nudge sweep failed: %s', e)

    # Also publish any due scheduled Facebook posts (daily fallback; a more
    # frequent cron runs `publish-due-facebook-posts` for precise scheduling).
    try:
        from app.crm.facebook_views import publish_scheduled_posts
        n = publish_scheduled_posts()
        if n:
            click.echo(f'Published {n} scheduled Facebook post(s)')
    except Exception as e:
        log.error('Facebook scheduled-post publish failed: %s', e)

    # CRM/booking daily jobs piggyback the same daily cron (adding a separate
    # cron service would require re-applying render.yaml — avoided on purpose).
    _run_crm_daily_jobs()

    click.echo('Garden trial lifecycle check complete.')


def _run_crm_daily_jobs():
    """Booking meeting reminders + nurture-lead resurfacing (send/act once)."""
    try:
        from app.booking_service import send_due_reminders
        n = send_due_reminders()
        if n:
            click.echo(f'Sent {n} meeting reminder(s)')
    except Exception as e:
        log.error('Booking reminder job failed: %s', e)
    try:
        from app.crm.helpers import resurface_nurture_leads
        n = resurface_nurture_leads()
        if n:
            click.echo(f'Resurfaced {n} nurture lead(s) into the working queue')
    except Exception as e:
        log.error('Nurture resurface job failed: %s', e)
    # Weekly (Mondays) CRM backup rides the existing daily cron — deliberately
    # NOT a new render.yaml cron (blueprint re-apply reverts the DB plan).
    if datetime.now(timezone.utc).weekday() == 0:
        try:
            manifest, emailed = run_crm_export()
            rows = sum(manifest['tables'].values())
            click.echo(f'CRM weekly backup: {rows} rows, '
                       f'{"emailed" if emailed else "NOT emailed"}')
        except Exception as e:
            log.error('CRM weekly backup failed: %s', e)


@click.command('crm-daily')
@with_appcontext
def crm_daily():
    """Run the CRM/booking daily jobs on their own (normally they ride the
    garden-trial-lifecycle cron)."""
    _run_crm_daily_jobs()
    click.echo('CRM daily jobs complete.')


def run_crm_export(email_to=None):
    """Build the CRM system-of-record export and email it off-box.

    The zip lands in the operator's mailbox — durable storage that survives
    the free-Postgres 90-day expiry risk without new infrastructure. Returns
    (manifest, emailed) so callers/CLI can report. Facebook tokens and
    password hashes are excluded by design (see app/crm/export.py).
    """
    import os
    from flask import current_app
    from app.crm.export import build_export_zip
    from app.email_service import send_email

    data, manifest = build_export_zip()
    to = (email_to
          or os.environ.get('CRM_EXPORT_EMAIL', '')
          or current_app.config.get('CRM_EXPORT_EMAIL', '')
          or current_app.config.get('CRM_FROM_EMAIL', ''))
    emailed = False
    if to:
        stamp = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        rows = sum(manifest['tables'].values())
        table_lines = ''.join(
            f'<li>{t}: {n} rows</li>' for t, n in manifest['tables'].items())
        emailed = send_email(
            to,
            f'CRM backup {stamp} ({rows} rows)',
            f'<p>Attached: CRM system-of-record export ({rows} rows).</p>'
            f'<ul>{table_lines}</ul>'
            '<p>Facebook tokens and passwords are never included.</p>',
            attachments=[{'name': f'crm-export-{stamp}.zip',
                          'mime_type': 'application/zip',
                          'content': data}],
        )
    return manifest, emailed


@click.command('crm-export')
@click.option('--email', 'email_to', default=None,
              help='Address to send the export zip to (default: CRM_EXPORT_EMAIL '
                   'or CRM_FROM_EMAIL). Also use before applying migrations.')
@with_appcontext
def crm_export(email_to):
    """Export the CRM system-of-record (companies/contacts/deals/campaigns...)
    as a zip of CSVs and email it off-box. Run this before schema migrations
    as the pre-migration snapshot."""
    manifest, emailed = run_crm_export(email_to)
    rows = sum(manifest['tables'].values())
    click.echo(f'Export built: {rows} rows across {len(manifest["tables"])} tables.')
    click.echo('Emailed off-box.' if emailed
               else 'NOT emailed (no recipient configured or send failed).')


@click.command('publish-due-facebook-posts')
@with_appcontext
def publish_due_facebook_posts():
    """Publish scheduled CRM Facebook posts whose time has arrived, then tick
    the autonomous BDR agent.

    The agent tick rides this 15-minute cron rather than getting its own
    service: a new cron in render.yaml means re-applying the blueprint, which
    reverts the paid DB plan (see docs/integrations/crm-agent-autonomy.md).
    The tick is idempotent (DB claims/leases) and never raises, so Facebook
    publishing is unaffected by anything the agent does.
    """
    from app.crm.facebook_views import publish_scheduled_posts
    n = publish_scheduled_posts()
    click.echo(f'Published {n} scheduled Facebook post(s).')
    try:
        from app.crm.autonomy import maybe_tick
        out = maybe_tick()
        if out.get('polled'):
            click.echo(f"Replies: {out['polled']}")
        if out.get('cycle'):
            click.echo(f"BDR cycle: {out['cycle']}")
        if out.get('errors'):
            click.echo(f"Agent tick errors: {out['errors']}")
    except Exception:  # noqa: BLE001
        log.exception('BDR agent tick failed')


@click.command('crm-agent-tick')
@with_appcontext
def crm_agent_tick():
    """Run one autonomous BDR heartbeat (poll replies, run the cycle if due).

    Same work the Facebook-scheduler cron does every 15 minutes; here for
    ops/manual runs. Safe to run repeatedly — the DB claims make it a no-op
    outside the send window or once the day's cycle has run."""
    from app.crm.autonomy import maybe_tick
    click.echo(maybe_tick())


@click.command('crm-agent-cycle')
@click.option('--force', is_flag=True, help='Ignore the send-window/once-a-day gates.')
@with_appcontext
def crm_agent_cycle(force):
    """Run the autonomous BDR cycle now (still respects the kill switch,
    pause, AI/email config, and the daily send cap)."""
    from app.crm.autonomy import run_daily_cycle, cycle_gates, get_settings, local_now
    s = get_settings()
    out = run_daily_cycle(force=force)
    if out is None:
        gates = cycle_gates(s, local_now(s), force=force)
        click.echo('Cycle did not run: ' + ('; '.join(gates) if gates
                                            else 'already ran today (use --force).'))
        return
    click.echo(f"sent={len(out['sent'])} promoted={len(out['promoted'])} "
               f"replies={len(out['replies'])} skipped={len(out['skipped'])} "
               f"failed={len(out['failed'])} cost=${out.get('cost_usd', 0):.4f}")
    if out.get('breaker'):
        click.echo(f"PAUSED: {out['breaker']}")


@click.command('crm-agent-poll')
@with_appcontext
def crm_agent_poll():
    """Poll the reply mailbox once (IMAP) and apply what it finds."""
    from app.crm.autonomy import poll_replies
    click.echo(poll_replies())


def _get_site_url():
    from flask import current_app
    return current_app.config.get('SITE_URL', 'http://localhost:5173')


@click.command('analytics-cleanup')
@with_appcontext
def analytics_cleanup():
    """Daily task: delete analytics events older than retention period."""
    from app import db
    from app.models import AnalyticsEvent, SiteEmailConfig

    config = SiteEmailConfig.query.first()
    retention_days = getattr(config, 'analytics_retention_days', 90) if config else 90
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

    deleted = AnalyticsEvent.query.filter(AnalyticsEvent.created_at < cutoff).delete()
    db.session.commit()
    click.echo(f'Analytics cleanup: deleted {deleted} events older than {retention_days} days.')


@click.command('indexnow-submit')
@with_appcontext
def indexnow_submit():
    """Submit the sitemap's URLs to IndexNow (Bing et al.) so new/changed
    pages are discovered immediately instead of waiting on a crawl.

    Needs INDEXNOW_KEY set (any 32+ char hex string) and the matching
    {key}.txt served at the site root (the app does this automatically).
    Run after content changes or a deploy; IndexNow treats resubmission of
    unchanged URLs as a no-op, so occasional full submits are safe.
    """
    import os
    import re as _re
    import requests
    from flask import current_app

    key = (os.environ.get('INDEXNOW_KEY', '')
           or current_app.config.get('INDEXNOW_KEY', '')).strip()
    if not key:
        click.echo('INDEXNOW_KEY is not set — nothing submitted.')
        return
    base = (current_app.config.get('SITE_URL')
            or 'https://www.yardharvest.app').rstrip('/')
    client = current_app.test_client()
    xml = client.get('/sitemap.xml').get_data(as_text=True)
    urls = _re.findall(r'<loc>([^<]+)</loc>', xml)
    if not urls:
        click.echo('Sitemap returned no URLs — nothing submitted.')
        return
    host = base.split('://', 1)[-1]
    resp = requests.post(
        'https://api.indexnow.org/indexnow',
        json={'host': host, 'key': key,
              'keyLocation': f'{base}/{key}.txt', 'urlList': urls},
        timeout=20)
    click.echo(f'Submitted {len(urls)} URLs to IndexNow — HTTP {resp.status_code}'
               + ('' if resp.status_code in (200, 202) else f' ({resp.text[:200]})'))
