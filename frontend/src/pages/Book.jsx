import { useState, useEffect, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import { bookingAPI } from '../api';
import Seo from '../components/Seo';

const VISITOR_TZ = Intl.DateTimeFormat().resolvedOptions().timeZone || 'local time';

function localDateKey(iso) {
  // en-CA renders as YYYY-MM-DD in the browser's local timezone — a stable key.
  return new Date(iso).toLocaleDateString('en-CA');
}
function dateLabel(iso) {
  return new Date(iso).toLocaleDateString(undefined, {
    weekday: 'long', month: 'long', day: 'numeric',
  });
}
function timeLabel(iso) {
  return new Date(iso).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
}
function monthKey(dateKey) {
  return dateKey.slice(0, 7);                     // 'YYYY-MM-DD' -> 'YYYY-MM'
}
function stepMonth(cursor, delta) {
  const [y, m] = cursor.split('-').map(Number);
  const d = new Date(y, m - 1 + delta, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

/** Month-grid date picker: days with open slots are clickable. */
function MonthCalendar({ cursor, byDate, activeDate, todayKey, minMonth, maxMonth, onPickDate, onStep }) {
  const [y, m] = cursor.split('-').map(Number);
  const daysInMonth = new Date(y, m, 0).getDate();
  const startPad = new Date(y, m - 1, 1).getDay();  // 0 = Sunday
  const label = new Date(y, m - 1, 1).toLocaleDateString(undefined, { month: 'long', year: 'numeric' });
  const cells = [...Array(startPad).fill(null),
                 ...Array.from({ length: daysInMonth }, (_, i) => i + 1)];
  return (
    <div className="card shadow-sm">
      <div className="card-body p-3">
        <div className="d-flex align-items-center justify-content-between mb-2">
          <button type="button" className="btn btn-sm btn-link text-secondary px-2"
                  disabled={cursor <= minMonth} onClick={() => onStep(-1)}
                  aria-label="Previous month">
            <i className="bi bi-chevron-left" />
          </button>
          <strong>{label}</strong>
          <button type="button" className="btn btn-sm btn-link text-secondary px-2"
                  disabled={cursor >= maxMonth} onClick={() => onStep(1)}
                  aria-label="Next month">
            <i className="bi bi-chevron-right" />
          </button>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 4 }}>
          {['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'].map((d) => (
            <div key={d} className="text-center text-muted small">{d}</div>
          ))}
          {cells.map((d, i) => {
            if (d === null) return <div key={`pad-${i}`} />;
            const key = `${cursor}-${String(d).padStart(2, '0')}`;
            const open = byDate.has(key);
            const cls = key === activeDate ? 'btn-success'
              : open ? 'btn-outline-success' : 'btn-light text-muted';
            return (
              <button key={key} type="button" disabled={!open}
                      className={`btn btn-sm ${cls} px-0${key === todayKey ? ' fw-bold' : ''}`}
                      aria-pressed={key === activeDate}
                      onClick={() => onPickDate(key)}>
                {d}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default function Book() {
  const { slug } = useParams();
  const [cfg, setCfg] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [typeSlug, setTypeSlug] = useState(slug || '');
  const [slotsData, setSlotsData] = useState(null);   // { type, owner_timezone, slots }
  const [slotsLoading, setSlotsLoading] = useState(false);
  const [slotsError, setSlotsError] = useState(false);
  const [activeDate, setActiveDate] = useState('');
  const [monthCursor, setMonthCursor] = useState(''); // 'YYYY-MM'; '' = first month with slots
  const [picked, setPicked] = useState('');           // chosen slot ISO

  const [form, setForm] = useState({ name: '', email: '', phone: '', notes: '' });
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);         // { booking, manage_path }

  // Load page config once.
  useEffect(() => {
    bookingAPI.config()
      .then((r) => {
        setCfg(r.data);
        if (!slug && r.data.types.length === 1) setTypeSlug(r.data.types[0].slug);
      })
      .catch(() => setError('Booking is not available right now.'))
      .finally(() => setLoading(false));
  }, [slug]);

  // Load slots whenever a meeting type is selected.
  useEffect(() => {
    if (!typeSlug) { setSlotsData(null); return; }
    setSlotsLoading(true);
    setSlotsError(false);
    setPicked(''); setActiveDate(''); setMonthCursor('');
    bookingAPI.slots(typeSlug)
      .then((r) => setSlotsData(r.data))
      .catch(() => { setSlotsError(true); setSlotsData({ type: null, slots: [] }); })
      .finally(() => setSlotsLoading(false));
  }, [typeSlug]);

  const byDate = useMemo(() => {
    const map = new Map();
    (slotsData?.slots || []).forEach((iso) => {
      const k = localDateKey(iso);
      if (!map.has(k)) map.set(k, []);
      map.get(k).push(iso);
    });
    return map;
  }, [slotsData]);

  const dateKeys = useMemo(() => [...byDate.keys()].sort(), [byDate]);
  useEffect(() => {
    if (dateKeys.length && !activeDate) setActiveDate(dateKeys[0]);
  }, [dateKeys, activeDate]);

  const selectedType = cfg?.types.find((t) => t.slug === typeSlug);

  async function submit(e) {
    e.preventDefault();
    setSubmitting(true); setError('');
    try {
      const r = await bookingAPI.book({
        type: typeSlug, start: picked,
        name: form.name, email: form.email,
        phone: form.phone, notes: form.notes,
        timezone: VISITOR_TZ,
      });
      setResult(r.data);
    } catch (err) {
      setError(err.response?.data?.error || 'Something went wrong. Please try again.');
      // A 409 means the slot was taken — refresh availability.
      if (err.response?.status === 409) {
        setPicked('');
        setSlotsError(false);
        bookingAPI.slots(typeSlug).then((r) => setSlotsData(r.data)).catch(() => setSlotsError(true));
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return <div className="text-center py-5"><div className="spinner-border text-success" /></div>;
  }

  if (!cfg) {
    return <div className="alert alert-warning" role="alert">{error || 'Booking is not available right now.'}</div>;
  }

  // ---- Confirmed ----
  if (result) {
    const b = result.booking;
    return (
      <div className="mx-auto" style={{ maxWidth: 560 }}>
        <div className="text-center py-4">
          <i className="bi bi-check-circle-fill text-success" style={{ fontSize: '3rem' }} />
          <h2 className="mt-3">You're booked!</h2>
          <p className="text-muted mb-4">A confirmation has been sent to {b.invitee_email}.</p>
        </div>
        <div className="card shadow-sm">
          <div className="card-body">
            <h5 className="mb-3">{b.type_name}</h5>
            <p className="mb-1"><i className="bi bi-calendar-event me-2 text-success" />
              {dateLabel(b.start_at)}</p>
            <p className="mb-1"><i className="bi bi-clock me-2 text-success" />
              {timeLabel(b.start_at)} ({b.duration_min} min) · {b.invitee_timezone}</p>
            {b.location && <p className="mb-1"><i className="bi bi-geo-alt me-2 text-success" />{b.location}</p>}
          </div>
        </div>
        <div className="text-center mt-4">
          <Link to={`/book/manage/${b.public_id}`} className="btn btn-outline-secondary btn-sm">
            Reschedule or cancel
          </Link>
        </div>
      </div>
    );
  }

  const showTypePicker = !typeSlug || !selectedType;

  return (
    <div className="mx-auto" style={{ maxWidth: 760 }}>
      <Seo
        title="Book time with James"
        path="/book"
        description="Schedule a 30-minute intro call about YardHarvest — pick any open time that works for you, no back-and-forth."
      />
      <div className="mb-4">
        <h1 className="h3 mb-1">{cfg?.settings.heading || 'Book a time'}</h1>
        {cfg?.settings.owner_name && (
          <p className="text-muted mb-1">with {cfg.settings.owner_name}</p>
        )}
        {cfg?.settings.intro && <p className="text-muted">{cfg.settings.intro}</p>}
      </div>

      {error && (showTypePicker || !picked) && <div className="alert alert-warning" role="alert">{error}</div>}

      {/* Step 1 — pick a meeting type */}
      {showTypePicker && (
        <div className="row g-3">
          {(cfg?.types || []).length === 0 && (
            <p className="text-muted">No meeting types are available right now.</p>
          )}
          {(cfg?.types || []).map((t) => (
            <div className="col-md-6" key={t.slug}>
              <button
                className="card h-100 w-100 text-start border-0 shadow-sm booking-type-card"
                style={{ borderLeft: `4px solid ${t.color}`, cursor: 'pointer' }}
                onClick={() => setTypeSlug(t.slug)}
              >
                <div className="card-body">
                  <h5 className="card-title mb-1">{t.name}</h5>
                  <p className="text-muted small mb-2">
                    <i className="bi bi-clock me-1" />{t.duration_min} min
                    {t.location && <> · <i className="bi bi-geo-alt me-1" />{t.location}</>}
                  </p>
                  {t.description && <p className="card-text small mb-0">{t.description}</p>}
                </div>
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Step 2 + 3 — date/time + details */}
      {!showTypePicker && (
        <>
          <button className="btn btn-link px-0 mb-2" onClick={() => { setTypeSlug(''); setPicked(''); setError(''); }}>
            <i className="bi bi-arrow-left me-1" />Choose a different meeting
          </button>
          <div className="card shadow-sm mb-3">
            <div className="card-body">
              <h5 className="mb-0">{selectedType.name}</h5>
              <small className="text-muted">
                <i className="bi bi-clock me-1" />{selectedType.duration_min} min
                {selectedType.location && <> · {selectedType.location}</>}
              </small>
            </div>
          </div>

          {slotsLoading ? (
            <div className="text-center py-4"><div className="spinner-border text-success" /></div>
          ) : slotsError ? (
            <div className="alert alert-warning">
              We couldn't load available times — please refresh and try again.
            </div>
          ) : dateKeys.length === 0 ? (
            <div className="alert alert-light border">
              No open times in the next little while. Please check back later.
            </div>
          ) : !picked ? (
            <div className="row">
              <div className="col-md-6 mb-3">
                <MonthCalendar
                  cursor={monthCursor || monthKey(dateKeys[0])}
                  byDate={byDate}
                  activeDate={activeDate}
                  todayKey={new Date().toLocaleDateString('en-CA')}
                  minMonth={monthKey(dateKeys[0])}
                  maxMonth={monthKey(dateKeys[dateKeys.length - 1])}
                  onPickDate={(k) => { setActiveDate(k); setError(''); }}
                  onStep={(delta) => setMonthCursor(
                    stepMonth(monthCursor || monthKey(dateKeys[0]), delta))}
                />
              </div>
              <div className="col-md-6">
                <p className="text-muted small mb-2">
                  Times shown in <strong>{VISITOR_TZ}</strong>
                </p>
                {activeDate && byDate.has(activeDate) && (
                  <p className="fw-medium mb-2">{dateLabel(byDate.get(activeDate)[0])}</p>
                )}
                <div className="d-flex flex-wrap gap-2">
                  {(byDate.get(activeDate) || []).map((iso) => (
                    <button key={iso} className="btn btn-outline-success"
                            onClick={() => { setPicked(iso); setError(''); }}>
                      {timeLabel(iso)}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            /* Step 3 — details form */
            <form onSubmit={submit}>
              <button type="button" className="btn btn-link px-0 mb-2" onClick={() => { setPicked(''); setError(''); }}>
                <i className="bi bi-arrow-left me-1" />Pick a different time
              </button>
              <div className="alert alert-success py-2">
                <i className="bi bi-calendar-check me-2" />
                {dateLabel(picked)} at {timeLabel(picked)} · {VISITOR_TZ}
              </div>
              <div className="mb-3">
                <label className="form-label" htmlFor="book-name">Name *</label>
                <input id="book-name" className="form-control" required autoFocus autoComplete="name" value={form.name}
                       onChange={(e) => setForm({ ...form, name: e.target.value })} />
              </div>
              <div className="mb-3">
                <label className="form-label" htmlFor="book-email">Email *</label>
                <input id="book-email" type="email" className="form-control" required autoComplete="email" value={form.email}
                       onChange={(e) => setForm({ ...form, email: e.target.value })} />
              </div>
              <div className="mb-3">
                <label className="form-label" htmlFor="book-phone">Phone <span className="text-muted">(optional)</span></label>
                <input id="book-phone" type="tel" className="form-control" autoComplete="tel" value={form.phone}
                       onChange={(e) => setForm({ ...form, phone: e.target.value })} />
              </div>
              <div className="mb-3">
                <label className="form-label" htmlFor="book-notes">Anything you'd like to share? <span className="text-muted">(optional)</span></label>
                <textarea id="book-notes" className="form-control" rows={3} value={form.notes}
                          onChange={(e) => setForm({ ...form, notes: e.target.value })} />
              </div>
              {error && <div className="alert alert-warning" role="alert">{error}</div>}
              <button className="btn btn-success" type="submit" disabled={submitting}>
                {submitting ? 'Booking…' : 'Confirm booking'}
              </button>
            </form>
          )}
        </>
      )}
    </div>
  );
}
