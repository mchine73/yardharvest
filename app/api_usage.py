"""Record and report usage of the metered third-party APIs the platform pays for.

Why this exists: every costly failure in this area has been silent. ZeptoMail
is prepaid, and when the credits ran out in July 2026 every send failed while
/api/health/email still said ``auth_ok: true`` — the probe proves the token
authenticates, not that there is money behind it. Nothing counted sends, so
nothing noticed. Campaigns showed "sent", BDR leads advanced their follow-up
counts, and no mail went out.

So: a row per call, written by :func:`record`, read by :func:`report` for the
admin API Usage page.

Two rules make it safe to call from anywhere:

* **It never raises.** Usage accounting failing must not fail the send it is
  accounting for.
* **It writes on its own connection**, never through ``db.session``. Committing
  through the request's session would commit the caller's half-finished work
  along with the usage row; and a send that *happened* must still be counted
  when the request that triggered it later rolls back.

Costs are ESTIMATES from list prices (below). They are for "is spend moving",
not for reconciling an invoice.
"""
import logging
import math
from datetime import datetime, timedelta, timezone

log = logging.getLogger(__name__)

# --- List prices (USD), checked 2026-10-31. Update here when a provider reprices.
#
# ZeptoMail: pay-as-you-go credits, 1 credit = 10,000 emails = $2.50, and
# usage is counted PER RECIPIENT — one email with 1 To and 3 BCC is 4.
ZEPTOMAIL_USD_PER_RECIPIENT = 2.50 / 10_000
# Twilio US long code: ~$0.0083 base per outbound segment plus a carrier
# pass-through fee of roughly $0.0035-$0.005 (AT&T, T-Mobile, Verizon differ).
# The midpoint is used; the true figure depends on who the recipient's
# carrier is, which nothing here knows.
TWILIO_USD_PER_SEGMENT = 0.0083 + 0.0040

PROVIDERS = {
    'zeptomail': 'ZeptoMail (email)',
    'twilio': 'Twilio (SMS)',
    'anthropic': 'Anthropic (AI)',
}


def sms_segments(body):
    """How many billable segments Twilio will charge for *body*.

    GSM-7 fits 160 characters in one segment and 153 per segment once split.
    One character outside GSM-7 — an emoji, a curly quote, an accented capital
    Twilio cannot map — switches the whole message to UCS-2: 70, then 67. That
    is why a Spanish SMS can cost more than the English one beside it.
    """
    text = body or ''
    gsm = set('@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !"#¤%&\'()*+,-./0123456789:;<=>?'
              '¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà'
              '^{}\\[~]|€')
    if all(c in gsm for c in text):
        single, multi = 160, 153
    else:
        single, multi = 70, 67
    n = len(text)
    if n <= single:
        return 1
    return int(math.ceil(n / float(multi)))


def estimate_cost(provider, *, units=1, model=None, input_tokens=0, output_tokens=0):
    """List-price estimate for one recorded call."""
    if provider == 'zeptomail':
        return round(units * ZEPTOMAIL_USD_PER_RECIPIENT, 6)
    if provider == 'twilio':
        return round(units * TWILIO_USD_PER_SEGMENT, 6)
    if provider == 'anthropic':
        # One price table for the whole app: the agent's, so a repricing is
        # a one-line change rather than a hunt.
        from app.crm.agent_service import estimate_cost as _model_cost
        return _model_cost(model, input_tokens, output_tokens)
    return 0.0


def record(provider, operation, *, units=1, ok=True, model=None,
           input_tokens=0, output_tokens=0, error=None, cost_usd=None):
    """Count one call. Never raises; never touches the caller's transaction."""
    try:
        from flask import has_app_context
        if not has_app_context():
            return
        from app import db
        from app.models import ApiUsageEvent

        units = max(0, int(units or 0))
        if cost_usd is None:
            # A failed call is still a call — but ZeptoMail and Twilio do not
            # bill a rejected send, so only successes carry a cost there.
            billable = ok or provider == 'anthropic'
            cost_usd = estimate_cost(provider, units=units, model=model,
                                     input_tokens=input_tokens,
                                     output_tokens=output_tokens) if billable else 0.0
        with db.engine.begin() as conn:
            if conn.dialect.name == 'sqlite':
                # SQLite has one writer. If the caller has flushed but not
                # committed, this connection waits for the lock — 5 seconds by
                # default, on a request thread, before giving up. Dev and tests
                # only (production is Postgres, with row-level locks); a lost
                # usage row there is fine, a five-second stall per send is not.
                conn.exec_driver_sql('PRAGMA busy_timeout = 100')
            conn.execute(ApiUsageEvent.__table__.insert().values(
                created_at=datetime.now(timezone.utc),
                provider=provider,
                operation=operation,
                units=units,
                ok=bool(ok),
                model=(model or None),
                input_tokens=int(input_tokens or 0),
                output_tokens=int(output_tokens or 0),
                cost_usd=float(cost_usd or 0.0),
                error=(str(error)[:200] if error else None),
            ))
    except Exception:          # noqa: BLE001 — accounting must never break a send
        log.debug('API usage not recorded for %s/%s', provider, operation,
                  exc_info=True)


def _since(days):
    return datetime.now(timezone.utc) - timedelta(days=int(days))


def report(days=30):
    """Everything the admin API Usage page shows, for the last *days* days."""
    from sqlalchemy import func, case
    from app import db
    from app.models import ApiUsageEvent
    from app.crm.models import CrmAgentRun

    days = max(1, min(int(days or 30), 365))
    since = _since(days)
    E = ApiUsageEvent

    rows = (db.session.query(
        E.provider, E.operation,
        func.count(E.id),
        func.coalesce(func.sum(E.units), 0),
        func.coalesce(func.sum(case((E.ok.is_(False), 1), else_=0)), 0),
        func.coalesce(func.sum(E.cost_usd), 0.0),
        func.coalesce(func.sum(E.input_tokens), 0),
        func.coalesce(func.sum(E.output_tokens), 0),
    ).filter(E.created_at >= since)
     .group_by(E.provider, E.operation).all())

    operations = [{
        'provider': p, 'operation': op, 'calls': int(calls), 'units': int(units),
        'failed': int(failed), 'cost_usd': round(float(cost), 4),
        'input_tokens': int(tin), 'output_tokens': int(tout),
    } for p, op, calls, units, failed, cost, tin, tout in rows]

    # The BDR agent already keeps its own ledger; read it rather than double-
    # recording every agent call into this one.
    A = CrmAgentRun
    agent_rows = (db.session.query(
        A.kind, A.model,
        func.count(A.id),
        func.coalesce(func.sum(case((A.status == 'failed', 1), else_=0)), 0),
        func.coalesce(func.sum(A.cost_usd), 0.0),
        func.coalesce(func.sum(A.input_tokens), 0),
        func.coalesce(func.sum(A.output_tokens), 0),
        func.coalesce(func.sum(A.web_searches), 0),
    ).filter(A.created_at >= since)
     .group_by(A.kind, A.model).all())
    for kind, model, runs, failed, cost, tin, tout, searches in agent_rows:
        operations.append({
            'provider': 'anthropic', 'operation': 'agent.%s' % (kind or 'run'),
            'model': model, 'calls': int(runs), 'units': int(runs),
            'failed': int(failed), 'cost_usd': round(float(cost), 4),
            'input_tokens': int(tin), 'output_tokens': int(tout),
            'web_searches': int(searches),
        })

    providers = {}
    for o in operations:
        p = providers.setdefault(o['provider'], {
            'provider': o['provider'], 'label': PROVIDERS.get(o['provider'], o['provider']),
            'calls': 0, 'units': 0, 'failed': 0, 'cost_usd': 0.0})
        for k in ('calls', 'units', 'failed'):
            p[k] += o[k]
        p['cost_usd'] = round(p['cost_usd'] + o['cost_usd'], 4)
    for p in providers.values():
        p['failure_rate'] = round(p['failed'] / p['calls'], 4) if p['calls'] else 0.0

    # Daily series for the chart: one row per (day, provider).
    day = func.date(E.created_at)
    daily_rows = (db.session.query(
        day, E.provider,
        func.count(E.id),
        func.coalesce(func.sum(E.cost_usd), 0.0),
        func.coalesce(func.sum(case((E.ok.is_(False), 1), else_=0)), 0),
    ).filter(E.created_at >= since)
     .group_by(day, E.provider).order_by(day).all())
    daily = [{'day': str(d), 'provider': p, 'calls': int(c),
              'cost_usd': round(float(cost), 4), 'failed': int(f)}
             for d, p, c, cost, f in daily_rows]

    recent_failures = [{
        'at': e.created_at.isoformat() if e.created_at else None,
        'provider': e.provider, 'operation': e.operation,
        'error': e.error,
    } for e in (E.query.filter(E.created_at >= since, E.ok.is_(False))
                .order_by(E.created_at.desc()).limit(25).all())]

    first = db.session.query(func.min(E.created_at)).scalar()
    total_cost = round(sum(p['cost_usd'] for p in providers.values()), 4)
    return {
        'days': days,
        'providers': sorted(providers.values(), key=lambda p: -p['cost_usd']),
        'operations': sorted(operations, key=lambda o: -o['cost_usd']),
        'daily': daily,
        'recent_failures': recent_failures,
        'total_cost_usd': total_cost,
        # Projected from the window's run rate. Said plainly in the UI as a
        # projection, because a quiet week makes it look cheaper than a month.
        'monthly_run_rate_usd': round(total_cost / days * 30, 2),
        # Email, SMS and moderation are only counted from the day this shipped.
        # The page says so, rather than letting an empty history read as zero.
        'tracking_since': first.isoformat() if first else None,
        'rates': {
            'zeptomail_per_recipient': ZEPTOMAIL_USD_PER_RECIPIENT,
            'twilio_per_segment': TWILIO_USD_PER_SEGMENT,
        },
    }

