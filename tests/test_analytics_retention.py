"""Analytics retention: the period has to be enforced, not merely configured.

The command existed, the retention period was configurable and documented,
and nothing ever called it — so events accumulated forever while the product
said they were kept for 90 days. Storing personal data longer than you told
people is a storage-limitation problem (GDPR Art. 5(1)(e)) and a broken
promise regardless of which privacy regime applies.

The test that matters here is the last one: that the daily job actually runs
it. The others would all have passed before the bug was fixed.
"""
from datetime import datetime, timedelta, timezone

from app import db as _db
from app.models import AnalyticsEvent, SiteEmailConfig


def _event(days_old, path='/'):
    ev = AnalyticsEvent(
    session_id='sess-%s-%s' % (days_old, path.strip('/') or 'root'),
    event_type='page_view', page_url=path,
    created_at=datetime.now(timezone.utc) - timedelta(days=days_old))
    _db.session.add(ev)
    return ev


def test_events_past_the_period_are_deleted(db_session, app):
    from app.cli import run_analytics_cleanup
    _event(120, '/old')
    _event(10, '/recent')
    _db.session.commit()

    deleted, days = run_analytics_cleanup()
    assert deleted == 1 and days == 90
    remaining = [e.page_url for e in AnalyticsEvent.query.all()]
    assert remaining == ['/recent']


def test_the_configured_period_is_the_one_used(db_session, app):
    """An admin who sets 30 days must get 30 days, not the default."""
    from app.cli import run_analytics_cleanup
    cfg = SiteEmailConfig.query.first() or SiteEmailConfig()
    cfg.analytics_retention_days = 30
    _db.session.add(cfg)
    _event(45, '/past-30')
    _event(20, '/inside-30')
    _db.session.commit()

    deleted, days = run_analytics_cleanup()
    assert days == 30 and deleted == 1
    assert [e.page_url for e in AnalyticsEvent.query.all()] == ['/inside-30']


def test_nothing_to_delete_is_not_an_error(db_session, app):
    from app.cli import run_analytics_cleanup
    _event(5)
    _db.session.commit()
    deleted, _days = run_analytics_cleanup()
    assert deleted == 0
    assert AnalyticsEvent.query.count() == 1


def test_the_daily_job_actually_runs_it(db_session, app):
    """The bug. Retention was implemented and unreachable: registered as a CLI
    command that no cron invoked. It now rides the daily job, the same way the
    weekly CRM backup does — deliberately not a new render.yaml cron, because a
    blueprint re-apply reverts the database plan."""
    from app.cli import _run_crm_daily_jobs
    _event(200, '/ancient')
    _event(1, '/today')
    _db.session.commit()

    _run_crm_daily_jobs()

    assert [e.page_url for e in AnalyticsEvent.query.all()] == ['/today']


def test_a_failure_there_does_not_stop_the_other_daily_work(db_session, app, monkeypatch):
    """Each job in the daily runner is isolated; retention blowing up must not
    take the booking reminders and nurture resurfacing down with it."""
    import app.cli as cli
    called = {}
    monkeypatch.setattr(cli, 'run_analytics_cleanup',
                    lambda: (_ for _ in ()).throw(RuntimeError('boom')))
    monkeypatch.setattr('app.crm.helpers.resurface_nurture_leads',
                    lambda: called.setdefault('resurfaced', True) or 0)
    cli._run_crm_daily_jobs()      # must not raise
    assert called.get('resurfaced') is True
