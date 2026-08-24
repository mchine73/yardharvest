"""Flask CLI commands for scheduled tasks."""
import logging
import os
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
    app.cli.add_command(stripe_sync_accounts)
    app.cli.add_command(stripe_backfill_fees)


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


@click.command('stripe-sync-accounts')
@click.option('--dry-run', is_flag=True,
              help='Read from Stripe and report, write nothing.')
@click.option('--payouts/--no-payouts', default=True,
              help='Also backfill recent bank deposits (default: yes).')
@click.option('--payout-limit', default=10, show_default=True,
              help='How many recent payouts to pull per account.')
@click.option('--notify', is_flag=True,
              help='Notify managers whose account needs attention. Off by '
                   'default: a backfill would otherwise message everyone at '
                   'once about a state they have been in for weeks.')
@click.option('--account', 'only_account', default=None,
              help='Limit to one acct_ id, for debugging a single manager.')
@with_appcontext
def stripe_sync_accounts(dry_run, payouts, payout_limit, notify, only_account):
    """Backfill Connect account health and recent payouts from Stripe.

    Webhooks only report what happens *next*. A manager whose Stripe account
    has been fine for months emits no ``account.updated``, so after wiring up
    the Connect endpoint the finance screens would honestly — and unhelpfully —
    report "Stripe hasn't sent an account update yet" until something changed.
    Payouts Stripe already made are missing for the same reason.

    This reads the current truth once and writes it through the exact same
    helpers the webhooks use, so a backfilled account and a webhook-updated
    one are indistinguishable. Safe to re-run: ledger rows are upserted on
    the Stripe object id.

    Usage:  flask stripe-sync-accounts --dry-run
    """
    import stripe as _stripe
    from app import db, garden_finance, stripe_service
    from app.models import User

    if not stripe_service.is_configured():
        click.echo('STRIPE_SECRET_KEY is not set — nothing to sync.')
        return

    _stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', '')

    q = User.query.filter(User.stripe_connect_account_id.isnot(None),
                          User.stripe_connect_account_id != '')
    if only_account:
        q = q.filter(User.stripe_connect_account_id == only_account)
    users = q.order_by(User.id).all()

    if not users:
        click.echo('No users have a Stripe Connect account.')
        return

    click.echo('Syncing %d connected account(s)%s...'
               % (len(users), ' [dry run]' if dry_run else ''))
    synced = failed = payouts_added = notified = 0

    for user in users:
        acct_id = user.stripe_connect_account_id
        label = '%s (%s)' % (user.email, acct_id)
        try:
            account = _stripe.Account.retrieve(acct_id)
        except Exception as exc:
            # One dead account — a test-mode id under live keys, a closed
            # account — must not stop the rest of the run.
            failed += 1
            click.echo('  !! %s — %s' % (label, stripe_service.error_detail(exc)))
            continue

        before, after = garden_finance.sync_account(user, account)
        synced += 1
        arrow = after if before == after else '%s -> %s' % (before, after)
        detail = ''
        reqs = garden_finance.requirements_list(user)
        if reqs:
            detail = ' needs: %s' % ', '.join(reqs[:3])
        click.echo('  %s  %s%s' % (label, arrow, detail))

        if payouts:
            try:
                # Payouts belong to the connected account, so they have to be
                # listed *as* that account.
                recent = _stripe.Payout.list(limit=max(1, min(payout_limit, 100)),
                                             stripe_account=acct_id)
            except Exception as exc:
                click.echo('     payouts unavailable — %s'
                           % stripe_service.error_detail(exc))
                recent = None
            for payout in (getattr(recent, 'data', None) or []):
                _ev, created, _status = garden_finance.record_payout(
                    user.id, payout, connected_account_id=acct_id)
                if created:
                    payouts_added += 1

        if notify and not dry_run and after not in ('ok', 'not_started') \
                and before != after:
            from app.api.notifications_api import notify as notify_user
            from app.api.webhook_api import _organizer_gardens, _organizer_link
            gardens = _organizer_gardens(user)
            if gardens:
                title, body = garden_finance.ACCOUNT_STATE_NOTICES[after]
                notify_user(user.id, 'stripe_account', title, body,
                            _organizer_link(gardens[0], 'stripe'), gardens[0].id)
                notified += 1

    if dry_run:
        db.session.rollback()
        click.echo('Dry run — rolled back. %d account(s) read, %d failed, '
                   '%d payout(s) would be recorded.'
                   % (synced, failed, payouts_added))
        return

    db.session.commit()
    click.echo('Synced %d account(s), %d failed, %d new payout(s), '
               '%d notification(s).' % (synced, failed, payouts_added, notified))


@click.command('stripe-backfill-fees')
@click.option('--dry-run', is_flag=True, help='Report, write nothing.')
@click.option('--limit', default=500, show_default=True,
              help='Maximum payments to look up in one run.')
@with_appcontext
def stripe_backfill_fees(dry_run, limit):
    """Fill in what Stripe charged on payments recorded before we asked.

    The ledger originally stored only the platform's own application fee, so
    "You keep" was really "collected minus our cut" — correct only while the
    platform absorbed Stripe's processing fee. Rows written before that
    changed have `stripe_fee_cents` NULL, and the finance screens flag the
    total as an upper bound until they are filled in.

    Only touches payment rows that are still NULL, so it is safe to re-run and
    cheap to run again after a failure.

    Usage:  flask stripe-backfill-fees --dry-run
    """
    from app import db, garden_finance, stripe_service
    from app.models import GardenFinanceEvent

    if not stripe_service.is_configured():
        click.echo('STRIPE_SECRET_KEY is not set - nothing to look up.')
        return

    rows = (GardenFinanceEvent.query
            .filter(GardenFinanceEvent.kind == 'payment',
                    GardenFinanceEvent.stripe_fee_cents.is_(None),
                    GardenFinanceEvent.stripe_charge_id.isnot(None),
                    GardenFinanceEvent.connected_account_id.isnot(None))
            .order_by(GardenFinanceEvent.occurred_at.desc())
            .limit(max(1, min(limit, 5000))).all())
    if not rows:
        click.echo('Every recorded payment already knows its Stripe fee.')
        return

    click.echo('Looking up %d payment(s)%s...'
               % (len(rows), ' [dry run]' if dry_run else ''))
    filled = unknown = 0
    # Which definition of "net" Stripe is using, tallied across the run.
    #   ours   - the balance transaction already nets our application fee
    #   plus   - it nets only Stripe's fee, so ours = theirs - application fee
    #   other  - neither; the delta is printed per row
    agree = {'ours': 0, 'plus_app_fee': 0, 'other': 0, 'no_net': 0}

    for ev in rows:
        fee, stripe_net = stripe_service.connected_charge_fee(
            ev.stripe_charge_id, ev.connected_account_id)
        if fee is None:
            unknown += 1
            click.echo('  ?? %s - Stripe did not report a fee yet'
                       % ev.stripe_object_id)
            continue
        ev.stripe_fee_cents = fee
        amount = ev.amount_cents or 0
        app_fee = ev.fee_cents or 0
        # Our definition: what the garden keeps after BOTH cuts.
        ev.net_cents = amount - app_fee - fee
        filled += 1

        # Reconcile against the net Stripe reports on the balance transaction.
        # We compute rather than take it because that transaction nets Stripe's
        # fee but not our application fee, which is transferred back to the
        # platform separately. This says out loud whether that is true, instead
        # of leaving a fetched value discarded and the reasoning in a comment.
        note = ''
        if stripe_net is None:
            agree['no_net'] += 1
            note = '  | Stripe reported no net'
        elif stripe_net == ev.net_cents:
            agree['ours'] += 1
            note = '  | Stripe net matches'
        elif stripe_net == ev.net_cents + app_fee:
            agree['plus_app_fee'] += 1
            note = '  | Stripe net $%.2f = ours + app fee (as expected)' % (
                stripe_net / 100.0)
        else:
            agree['other'] += 1
            note = '  | MISMATCH: Stripe net $%.2f, ours $%.2f (delta $%.2f)' % (
                stripe_net / 100.0, ev.net_cents / 100.0,
                (stripe_net - ev.net_cents) / 100.0)

        click.echo('  %s  $%.2f charged, $%.2f app fee, $%.2f Stripe fee, '
                   '$%.2f kept%s'
                   % (ev.stripe_object_id, amount / 100.0, app_fee / 100.0,
                      fee / 100.0, ev.net_cents / 100.0, note))

    if filled:
        click.echo('')
        click.echo('Net reconciliation: %d match ours, %d are ours + the app '
                   'fee, %d neither, %d had no net.'
                   % (agree['ours'], agree['plus_app_fee'], agree['other'],
                      agree['no_net']))
        if agree['other']:
            click.echo('  ^ Some rows reconcile to neither definition. Send '
                       'this output back before running without --dry-run.')
        elif agree['ours'] and not agree['plus_app_fee']:
            click.echo('  ^ Stripe already nets the application fee, so the '
                       'kept figure could be taken from Stripe directly.')

    if dry_run:
        db.session.rollback()
        click.echo('Dry run - rolled back. %d would be filled, %d unknown.'
                   % (filled, unknown))
        return
    db.session.commit()
    click.echo('Filled %d payment(s); %d still unknown.' % (filled, unknown))
