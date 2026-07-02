import { useState, useEffect } from 'react';
import { bookingAPI } from '../../api';
import { confirmDialog } from '../../components/dialog/dialogService';

const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
const COMMON_TZS = [
  'America/New_York', 'America/Chicago', 'America/Denver', 'America/Los_Angeles',
  'America/Phoenix', 'America/Anchorage', 'Pacific/Honolulu', 'UTC',
];

const toTime = (min) => `${String(Math.floor(min / 60)).padStart(2, '0')}:${String(min % 60).padStart(2, '0')}`;
const toMin = (t) => { const [h, m] = (t || '0:0').split(':').map(Number); return h * 60 + m; };
const fmtDT = (iso) => new Date(iso).toLocaleString(undefined,
  { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });

const BLANK_TYPE = {
  name: '', duration_min: 30, location: '', description: '',
  buffer_before_min: 0, buffer_after_min: 0, color: '#5b8c3e', is_active: true,
};

export default function AdminBooking() {
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [settings, setSettings] = useState(null);
  const [types, setTypes] = useState([]);
  const [rules, setRules] = useState([]);
  const [zoho, setZoho] = useState({});
  const [bookings, setBookings] = useState({ upcoming: [], past: [] });
  const [toast, setToast] = useState(null);

  const [typeForm, setTypeForm] = useState(null);   // null = closed; else {…type}
  const [zohoCals, setZohoCals] = useState(null);
  const [saving, setSaving] = useState(false);

  function flash(msg, variant = 'success') { setToast({ msg, variant }); setTimeout(() => setToast(null), 2500); }

  function load() {
    setLoadError(false);
    Promise.all([bookingAPI.admin.overview(), bookingAPI.admin.bookings()])
      .then(([o, b]) => {
        setSettings(o.data.settings);
        setTypes(o.data.types);
        setRules(o.data.availability);
        setZoho(o.data.zoho || {});
        setBookings(b.data);
      })
      .catch(() => setLoadError(true))
      .finally(() => setLoading(false));
  }
  useEffect(load, []);

  // ---- settings ----
  async function saveSettings() {
    try {
      await bookingAPI.admin.saveSettings(settings);
      flash('Settings saved');
    } catch (e) {
      flash(e.response?.data?.error || 'Could not save settings', 'error');
    }
  }

  // ---- availability ----
  function addWindow(day) {
    setRules([...rules, { day_of_week: day, start_min: 540, end_min: 1020, _k: Math.random() }]);
  }
  function updateWindow(idx, field, value) {
    const next = [...rules]; next[idx] = { ...next[idx], [field]: value }; setRules(next);
  }
  function removeWindow(idx) { setRules(rules.filter((_, i) => i !== idx)); }
  async function saveAvailability() {
    const payload = rules.map((r) => ({
      day_of_week: r.day_of_week, start_min: r.start_min, end_min: r.end_min,
    }));
    try {
      const r = await bookingAPI.admin.setAvailability(payload);
      setRules(r.data.availability);
      flash('Availability saved');
    } catch (e) {
      flash(e.response?.data?.error || 'Could not save availability', 'error');
    }
  }

  // ---- types ----
  async function saveType() {
    setSaving(true);
    try {
      if (typeForm.id) await bookingAPI.admin.updateType(typeForm.id, typeForm);
      else await bookingAPI.admin.createType(typeForm);
      setTypeForm(null);
      flash('Meeting type saved');
      load();
    } catch (e) {
      flash(e.response?.data?.error || 'Could not save meeting type', 'error');
    } finally {
      setSaving(false);
    }
  }
  async function deleteType(t) {
    if (!(await confirmDialog(`Delete "${t.name}"?`, { danger: true, title: 'Delete meeting type', confirmText: 'Delete' }))) return;
    try {
      const r = await bookingAPI.admin.deleteType(t.id);
      flash(r.data?.deactivated ? 'Meeting type hidden (it has existing bookings)' : 'Meeting type removed');
      load();
    } catch (e) {
      flash(e.response?.data?.error || 'Could not delete meeting type', 'error');
    }
  }

  async function listCalendars() {
    setZohoCals({ loading: true });
    try {
      const r = await bookingAPI.admin.zohoCalendars();
      setZohoCals(r.data);
    } catch (e) {
      setZohoCals({ error: e.response?.data?.error || 'Failed to reach Zoho' });
    }
  }

  if (loading) return <div className="text-center py-5"><div className="spinner-border text-success" /></div>;
  if (loadError || !settings) {
    return (
      <div className="alert alert-warning">
        Couldn't load booking settings —{' '}
        <button className="btn btn-link p-0 align-baseline" onClick={() => { setLoading(true); load(); }}>try again</button>.
      </div>
    );
  }

  return (
    <div className="mx-auto" style={{ maxWidth: 880 }}>
      <div className="d-flex align-items-center justify-content-between mb-3">
        <h1 className="h3 mb-0">Booking page</h1>
        <a href="/book" target="_blank" rel="noreferrer" className="btn btn-outline-success btn-sm">
          <i className="bi bi-box-arrow-up-right me-1" />View public page
        </a>
      </div>
      {toast && <div className={`alert py-2 ${toast.variant === 'error' ? 'alert-warning' : 'alert-success'}`} role={toast.variant === 'error' ? 'alert' : 'status'}>{toast.msg}</div>}

      {/* ---- Page settings ---- */}
      <div className="card shadow-sm mb-4">
        <div className="card-header bg-white"><strong>Page settings</strong></div>
        <div className="card-body">
          <div className="row g-3">
            <div className="col-md-6">
              <label className="form-label">Your timezone</label>
              <input className="form-control" list="tzlist" value={settings.timezone}
                     onChange={(e) => setSettings({ ...settings, timezone: e.target.value })} />
              <datalist id="tzlist">{COMMON_TZS.map((t) => <option key={t} value={t} />)}</datalist>
            </div>
            <div className="col-md-6">
              <label className="form-label">Display name</label>
              <input className="form-control" value={settings.owner_name}
                     onChange={(e) => setSettings({ ...settings, owner_name: e.target.value })} />
            </div>
            <div className="col-12">
              <label className="form-label">Heading</label>
              <input className="form-control" value={settings.heading}
                     onChange={(e) => setSettings({ ...settings, heading: e.target.value })} />
            </div>
            <div className="col-12">
              <label className="form-label">Intro text</label>
              <textarea className="form-control" rows={2} value={settings.intro}
                        onChange={(e) => setSettings({ ...settings, intro: e.target.value })} />
            </div>
            <div className="col-md-3">
              <label className="form-label">Min notice (hrs)</label>
              <input type="number" min="0" className="form-control" value={settings.min_notice_hours}
                     onChange={(e) => setSettings({ ...settings, min_notice_hours: +e.target.value })} />
            </div>
            <div className="col-md-3">
              <label className="form-label">Bookable up to (days)</label>
              <input type="number" min="1" className="form-control" value={settings.max_advance_days}
                     onChange={(e) => setSettings({ ...settings, max_advance_days: +e.target.value })} />
            </div>
            <div className="col-md-3">
              <label className="form-label">Slot every (min)</label>
              <input type="number" min="5" step="5" className="form-control" value={settings.slot_granularity_min}
                     onChange={(e) => setSettings({ ...settings, slot_granularity_min: +e.target.value })} />
            </div>
            <div className="col-md-3">
              <label className="form-label">Max / day (0 = ∞)</label>
              <input type="number" min="0" className="form-control" value={settings.max_per_day}
                     onChange={(e) => setSettings({ ...settings, max_per_day: +e.target.value })} />
            </div>
            <div className="col-12">
              <div className="form-check">
                <input className="form-check-input" type="checkbox" id="zbusy"
                       checked={settings.block_zoho_busy}
                       onChange={(e) => setSettings({ ...settings, block_zoho_busy: e.target.checked })} />
                <label className="form-check-label" htmlFor="zbusy">
                  Hide times I'm already busy on my Zoho calendar
                </label>
              </div>
            </div>
          </div>
          <button className="btn btn-success mt-3" onClick={saveSettings}>Save settings</button>
        </div>
      </div>

      {/* ---- Weekly availability ---- */}
      <div className="card shadow-sm mb-4">
        <div className="card-header bg-white d-flex justify-content-between align-items-center">
          <strong>Weekly availability</strong>
          <small className="text-muted">in {settings.timezone}</small>
        </div>
        <div className="card-body">
          {DAYS.map((dayName, day) => (
            <div className="d-flex align-items-start mb-2" key={day}>
              <div style={{ width: 110 }} className="pt-1 fw-medium">{dayName}</div>
              <div className="flex-grow-1">
                {rules.filter((r) => r.day_of_week === day).length === 0 && (
                  <span className="text-muted small">Unavailable</span>
                )}
                {rules.map((r, idx) => r.day_of_week === day && (
                  <div className="d-flex align-items-center gap-2 mb-1" key={r._k ?? idx}>
                    <input type="time" className="form-control form-control-sm" style={{ width: 130 }}
                           value={toTime(r.start_min)}
                           onChange={(e) => updateWindow(idx, 'start_min', toMin(e.target.value))} />
                    <span>–</span>
                    <input type="time" className="form-control form-control-sm" style={{ width: 130 }}
                           value={toTime(r.end_min)}
                           onChange={(e) => updateWindow(idx, 'end_min', toMin(e.target.value))} />
                    <button className="btn btn-sm btn-link text-danger" onClick={() => removeWindow(idx)}>
                      <i className="bi bi-x-lg" />
                    </button>
                  </div>
                ))}
                <button className="btn btn-sm btn-link px-0" onClick={() => addWindow(day)}>
                  <i className="bi bi-plus-lg me-1" />Add hours
                </button>
              </div>
            </div>
          ))}
          <button className="btn btn-success mt-2" onClick={saveAvailability}>Save availability</button>
        </div>
      </div>

      {/* ---- Meeting types ---- */}
      <div className="card shadow-sm mb-4">
        <div className="card-header bg-white d-flex justify-content-between align-items-center">
          <strong>Meeting types</strong>
          <button className="btn btn-sm btn-success" onClick={() => setTypeForm({ ...BLANK_TYPE })}>
            <i className="bi bi-plus-lg me-1" />Add type
          </button>
        </div>
        <div className="card-body">
          {types.length === 0 && <p className="text-muted mb-0">No meeting types yet. Add one to start taking bookings.</p>}
          {types.map((t) => (
            <div className="d-flex align-items-center border-bottom py-2" key={t.id}>
              <span className="me-2" style={{ width: 10, height: 10, borderRadius: '50%', background: t.color, display: 'inline-block' }} />
              <div className="flex-grow-1">
                <div className="fw-medium">{t.name} {!t.is_active && <span className="badge bg-secondary ms-1">hidden</span>}</div>
                <small className="text-muted">{t.duration_min} min · /book/{t.slug}{t.location ? ` · ${t.location}` : ''}</small>
              </div>
              <button className="btn btn-sm btn-outline-secondary me-2" onClick={() => setTypeForm({ ...t })}>Edit</button>
              <button className="btn btn-sm btn-outline-danger" onClick={() => deleteType(t)}>Delete</button>
            </div>
          ))}
        </div>
      </div>

      {/* type editor */}
      {typeForm && (
        <div className="card shadow-sm mb-4 border-success">
          <div className="card-header bg-white"><strong>{typeForm.id ? 'Edit' : 'New'} meeting type</strong></div>
          <div className="card-body">
            <div className="row g-3">
              <div className="col-md-8">
                <label className="form-label">Name *</label>
                <input className="form-control" value={typeForm.name}
                       onChange={(e) => setTypeForm({ ...typeForm, name: e.target.value })} />
              </div>
              <div className="col-md-4">
                <label className="form-label">Duration (min)</label>
                <input type="number" min="5" className="form-control" value={typeForm.duration_min}
                       onChange={(e) => setTypeForm({ ...typeForm, duration_min: +e.target.value })} />
              </div>
              <div className="col-md-8">
                <label className="form-label">Location <span className="text-muted">(e.g. Phone call, a video link)</span></label>
                <input className="form-control" value={typeForm.location}
                       onChange={(e) => setTypeForm({ ...typeForm, location: e.target.value })} />
              </div>
              <div className="col-md-4">
                <label className="form-label">Color</label>
                <input type="color" className="form-control form-control-color" value={typeForm.color}
                       onChange={(e) => setTypeForm({ ...typeForm, color: e.target.value })} />
              </div>
              <div className="col-12">
                <label className="form-label">Description</label>
                <textarea className="form-control" rows={2} value={typeForm.description}
                          onChange={(e) => setTypeForm({ ...typeForm, description: e.target.value })} />
              </div>
              <div className="col-md-4">
                <label className="form-label">Buffer before (min)</label>
                <input type="number" min="0" className="form-control" value={typeForm.buffer_before_min}
                       onChange={(e) => setTypeForm({ ...typeForm, buffer_before_min: +e.target.value })} />
              </div>
              <div className="col-md-4">
                <label className="form-label">Buffer after (min)</label>
                <input type="number" min="0" className="form-control" value={typeForm.buffer_after_min}
                       onChange={(e) => setTypeForm({ ...typeForm, buffer_after_min: +e.target.value })} />
              </div>
              <div className="col-md-4 d-flex align-items-end">
                <div className="form-check">
                  <input className="form-check-input" type="checkbox" id="tactive"
                         checked={typeForm.is_active}
                         onChange={(e) => setTypeForm({ ...typeForm, is_active: e.target.checked })} />
                  <label className="form-check-label" htmlFor="tactive">Active (shown publicly)</label>
                </div>
              </div>
            </div>
            <div className="mt-3">
              <button className="btn btn-success me-2" onClick={saveType} disabled={saving}>{saving ? 'Saving…' : 'Save'}</button>
              <button className="btn btn-link" onClick={() => setTypeForm(null)}>Cancel</button>
            </div>
          </div>
        </div>
      )}

      {/* ---- Zoho calendar ---- */}
      <div className="card shadow-sm mb-4">
        <div className="card-header bg-white"><strong>Zoho Calendar sync</strong></div>
        <div className="card-body">
          <p className="mb-2">
            {zoho.configured
              ? <span className="text-success"><i className="bi bi-check-circle-fill me-1" />OAuth connected</span>
              : <span className="text-muted"><i className="bi bi-dash-circle me-1" />Not connected — bookings still save &amp; email, just won't sync to your calendar.</span>}
            {zoho.configured && !zoho.calendar_uid_set && (
              <span className="text-warning ms-2"><i className="bi bi-exclamation-triangle me-1" />No calendar UID set</span>)}
          </p>
          {zoho.configured && (
            <button className="btn btn-sm btn-outline-secondary" onClick={listCalendars}>
              List my calendars (find the UID)
            </button>
          )}
          {zohoCals?.loading && <div className="spinner-border spinner-border-sm ms-2" />}
          {zohoCals?.error && <div className="alert alert-warning mt-2 mb-0 py-2">{zohoCals.error}</div>}
          {zohoCals?.calendars && (
            <ul className="list-group mt-2">
              {zohoCals.calendars.map((c) => (
                <li className="list-group-item d-flex justify-content-between" key={c.uid}>
                  <span>{c.name} {c.is_default && <span className="badge bg-light text-dark">default</span>}</span>
                  <code className="small">{c.uid}</code>
                </li>
              ))}
            </ul>
          )}
          <p className="text-muted small mt-2 mb-0">
            Set <code>ZOHO_CLIENT_ID</code>, <code>ZOHO_CLIENT_SECRET</code>,
            <code> ZOHO_REFRESH_TOKEN</code> and <code>ZOHO_CALENDAR_UID</code> in the
            server environment, then redeploy.
          </p>
        </div>
      </div>

      {/* ---- Upcoming bookings ---- */}
      <div className="card shadow-sm mb-5">
        <div className="card-header bg-white"><strong>Upcoming bookings</strong></div>
        <div className="card-body">
          {bookings.upcoming.length === 0 && <p className="text-muted mb-0">No upcoming bookings.</p>}
          {bookings.upcoming.map((b) => (
            <div className="d-flex align-items-center border-bottom py-2" key={b.public_id}>
              <div className="flex-grow-1">
                <div className="fw-medium">{fmtDT(b.start_at)} · {b.type_name}</div>
                <small className="text-muted">{b.invitee_name} ({b.invitee_email})</small>
              </div>
              {b.zoho_sync_status === 'synced' && <span className="badge bg-success-subtle text-success">on calendar</span>}
              {b.zoho_sync_status === 'failed' && <span className="badge bg-danger-subtle text-danger">sync failed</span>}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
