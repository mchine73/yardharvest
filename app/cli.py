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
    from app import db
    from app.models import CommunityGarden, GardenSubscription

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

    for sub in active_trials:
        trial_start = sub.trial_start
        if not trial_start:
            continue
        days_since = (now - trial_start).days
        garden = db.session.get(CommunityGarden, sub.garden_id)
        if not garden:
            continue
        organizer = garden.organizer

        try:
            if days_since == 3 and sub.status == 'trialing':
                send_garden_trial_progress(garden, organizer)
                click.echo(f'Day 3 email sent for garden {garden.name}')

            elif days_since == 7 and sub.status == 'trialing':
                send_garden_trial_halfway(garden, organizer)
                click.echo(f'Day 7 email sent for garden {garden.name}')

            elif days_since == 12 and sub.status == 'trialing':
                send_garden_trial_expiring(garden, organizer)
                billing_url = f'{_get_site_url()}/gardens/{garden.public_id}/billing'
                if organizer.sms_opt_in and organizer.phone_number:
                    send_garden_trial_expiring_sms(organizer.phone_number, garden.name, billing_url)
                click.echo(f'Day 12 email+SMS sent for garden {garden.name}')

            elif days_since == 14 and sub.status == 'expired':
                send_garden_trial_ended(garden, organizer)
                billing_url = f'{_get_site_url()}/gardens/{garden.public_id}/billing'
                if organizer.sms_opt_in and organizer.phone_number:
                    send_garden_trial_ended_sms(organizer.phone_number, garden.name, billing_url)
                click.echo(f'Day 14 email+SMS sent for garden {garden.name}')

            elif days_since == 21 and sub.status == 'expired':
                send_garden_trial_reengagement(garden, organizer)
                click.echo(f'Day 21 re-engagement email sent for garden {garden.name}')

        except Exception as e:
            log.error('Error sending trial email for garden_id=%d day=%d: %s', garden.id, days_since, e)

    # Also publish any due scheduled Facebook posts (daily fallback; a more
    # frequent cron runs `publish-due-facebook-posts` for precise scheduling).
    try:
        from app.crm.facebook_views import publish_scheduled_posts
        n = publish_scheduled_posts()
        if n:
            click.echo(f'Published {n} scheduled Facebook post(s)')
    except Exception as e:
        log.error('Facebook scheduled-post publish failed: %s', e)

    click.echo('Garden trial lifecycle check complete.')


@click.command('publish-due-facebook-posts')
@with_appcontext
def publish_due_facebook_posts():
    """Publish scheduled CRM Facebook posts whose time has arrived."""
    from app.crm.facebook_views import publish_scheduled_posts
    n = publish_scheduled_posts()
    click.echo(f'Published {n} scheduled Facebook post(s).')


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
