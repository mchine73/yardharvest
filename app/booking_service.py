"""Availability / slot computation for the booking page.

All datetimes here are **naive UTC** (matching how Booking rows are stored).
Availability windows are defined in the owner's timezone (BookingSettings.
timezone); we expand each weekly window into concrete UTC instants, then drop
any that violate min-notice / horizon, collide with an existing booking (plus
buffers) or a busy time on the owner's real calendar, or fall on a day that's
already at its per-day cap.

``generate_slots`` is a pure function (no DB / network) so the slot logic is
unit-testable; ``available_slot_starts`` is the DB/Zoho-backed orchestrator.
"""
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

log = logging.getLogger(__name__)


def utc_now_naive():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_naive_utc(dt):
    """Coerce any datetime (aware or naive) to naive UTC. Naive is assumed UTC."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _overlaps(a_start, a_end, b_start, b_end):
    return a_start < b_end and b_start < a_end


def generate_slots(*, duration_min, buffer_before_min, buffer_after_min,
                   rules, settings, now_utc, busy_intervals=None,
                   blocked_dates=None):
    """Return a sorted list of naive-UTC start datetimes that are bookable.

    Parameters
    ----------
    rules : iterable of objects with .day_of_week (0=Mon..6=Sun), .start_min,
        .end_min (minutes from midnight, owner-local time).
    settings : object with .timezone, .min_notice_hours, .max_advance_days,
        .slot_granularity_min.
    now_utc : naive-UTC "now".
    busy_intervals : list of (start_naive_utc, end_naive_utc) already-expanded
        busy blocks (existing bookings incl. their buffers, + Zoho events).
    blocked_dates : set of owner-local ``date`` that are at the per-day cap.
    """
    busy_intervals = busy_intervals or []
    blocked_dates = blocked_dates or set()
    try:
        tz = ZoneInfo(settings.timezone or 'America/Chicago')
    except Exception:
        tz = ZoneInfo('America/Chicago')

    duration = timedelta(minutes=duration_min)
    buf_before = timedelta(minutes=buffer_before_min or 0)
    buf_after = timedelta(minutes=buffer_after_min or 0)
    step = max(5, int(settings.slot_granularity_min or 30))

    earliest = now_utc + timedelta(hours=settings.min_notice_hours or 0)
    latest = now_utc + timedelta(days=settings.max_advance_days or 30)

    # Bucket rules by weekday for quick lookup.
    by_day = {}
    for r in rules:
        by_day.setdefault(r.day_of_week, []).append(r)
    if not by_day:
        return []

    now_local_date = now_utc.replace(tzinfo=timezone.utc).astimezone(tz).date()
    found = set()
    for day_offset in range((settings.max_advance_days or 30) + 1):
        d = now_local_date + timedelta(days=day_offset)
        if d in blocked_dates:
            continue
        for r in by_day.get(d.weekday(), []):
            m = int(r.start_min)
            while m + duration_min <= int(r.end_min):
                hh, mm = divmod(m, 60)
                m += step
                # Build the owner-local wall time, convert to naive UTC.
                local_dt = datetime(d.year, d.month, d.day, hh, mm, tzinfo=tz)
                start = local_dt.astimezone(timezone.utc).replace(tzinfo=None)
                end = start + duration
                if start < earliest or start > latest:
                    continue
                block_s, block_e = start - buf_before, end + buf_after
                if any(_overlaps(block_s, block_e, bs, be)
                       for bs, be in busy_intervals):
                    continue
                found.add(start)
    return sorted(found)


def _expanded_booking_busy(bookings):
    """Turn confirmed bookings into busy intervals expanded by their buffers."""
    out = []
    for b in bookings:
        bt = b.booking_type
        bb = timedelta(minutes=(bt.buffer_before_min if bt else 0) or 0)
        ba = timedelta(minutes=(bt.buffer_after_min if bt else 0) or 0)
        out.append((to_naive_utc(b.start_at) - bb, to_naive_utc(b.end_at) + ba))
    return out


def _capacity_blocked_dates(bookings, settings):
    """Owner-local dates already at the per-day cap (max_per_day > 0)."""
    cap = int(settings.max_per_day or 0)
    if cap <= 0:
        return set()
    try:
        tz = ZoneInfo(settings.timezone or 'America/Chicago')
    except Exception:
        tz = ZoneInfo('America/Chicago')
    counts = {}
    for b in bookings:
        d = to_naive_utc(b.start_at).replace(tzinfo=timezone.utc).astimezone(tz).date()
        counts[d] = counts.get(d, 0) + 1
    return {d for d, n in counts.items() if n >= cap}


def available_slot_starts(booking_type, settings=None):
    """Compute bookable naive-UTC start instants for one meeting type.

    DB + Zoho backed. Best-effort on the Zoho read — a failure degrades to
    YardHarvest-only conflict checking (returns no busy blocks)."""
    from app.models import BookingSettings, AvailabilityRule, Booking
    settings = settings or BookingSettings.get()
    now_utc = utc_now_naive()
    horizon_end = now_utc + timedelta(days=(settings.max_advance_days or 30) + 1)

    rules = AvailabilityRule.query.all()
    if not rules:
        return []

    existing = (Booking.query
                .filter(Booking.status == 'confirmed',
                        Booking.start_at < horizon_end,
                        Booking.end_at > now_utc)
                .all())
    busy = _expanded_booking_busy(existing)
    blocked_dates = _capacity_blocked_dates(existing, settings)

    if settings.block_zoho_busy:
        try:
            from app import zoho_calendar_service as zoho
            if zoho.is_configured() and zoho.has_calendar():
                busy += zoho.get_busy_intervals(
                    now_utc.replace(tzinfo=timezone.utc),
                    horizon_end.replace(tzinfo=timezone.utc))
        except Exception:  # noqa: BLE001 — never let a calendar hiccup block booking
            log.warning('[BOOKING] Zoho busy fetch failed; using DB-only availability',
                        exc_info=True)

    return generate_slots(
        duration_min=booking_type.duration_min,
        buffer_before_min=booking_type.buffer_before_min,
        buffer_after_min=booking_type.buffer_after_min,
        rules=rules, settings=settings, now_utc=now_utc,
        busy_intervals=busy, blocked_dates=blocked_dates,
    )


def slot_is_open(booking_type, start_utc_naive, settings=None):
    """Re-validate (at booking time) that a specific start is still bookable."""
    target = start_utc_naive.replace(second=0, microsecond=0)
    return any(s.replace(second=0, microsecond=0) == target
               for s in available_slot_starts(booking_type, settings=settings))
