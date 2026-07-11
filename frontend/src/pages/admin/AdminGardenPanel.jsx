import { useState, useEffect, useCallback } from 'react';
import { adminAPI } from '../../api';
import { toast, confirmDialog } from '../../components/dialog/dialogService';

const SUB_STATUSES = ['free', 'trialing', 'active', 'expired'];
const OPERATING_MODELS = ['allotment', 'communal', 'hybrid'];

const money = (v) => `$${Number(v || 0).toFixed(2)}`;

const TABS = [
  { key: 'overview', label: 'Overview', icon: 'bi-speedometer2' },
  { key: 'edit', label: 'Edit details', icon: 'bi-pencil-square' },
  { key: 'members', label: 'Members', icon: 'bi-people' },
  { key: 'ownership', label: 'Ownership', icon: 'bi-person-badge' },
  { key: 'danger', label: 'Danger zone', icon: 'bi-exclamation-octagon' },
];

/**
 * AdminGardenPanel — centralized platform-admin controls for one garden.
 * Rendered inside an expanded table row in AdminGardens.
 *
 *   onChanged() — reload the parent list (after any mutation)
 *   onClose()   — collapse this panel (after delete)
 */
export default function AdminGardenPanel({ garden, onChanged, onClose }) {
  const [tab, setTab] = useState('overview');

  return (
    <div className="p-3">
      <ul className="nav nav-pills mb-3" style={{ gap: '0.25rem' }}>
        {TABS.map((t) => (
          <li className="nav-item" key={t.key}>
            <button
              className={`nav-link py-1 px-3 ${tab === t.key ? 'active' : ''} ${t.key === 'danger' && tab === t.key ? 'bg-danger' : ''}`}
              onClick={() => setTab(t.key)}
            >
              <i className={`bi ${t.icon} me-1`}></i>{t.label}
            </button>
          </li>
        ))}
      </ul>

      {tab === 'overview' && <OverviewTab garden={garden} onChanged={onChanged} />}
      {tab === 'edit' && <EditTab garden={garden} onChanged={onChanged} />}
      {tab === 'members' && <MembersTab garden={garden} />}
      {tab === 'ownership' && <OwnershipTab garden={garden} onChanged={onChanged} />}
      {tab === 'danger' && <DangerTab garden={garden} onChanged={onChanged} onClose={onClose} />}
    </div>
  );
}

function StatCard({ label, value, sub, tone = 'secondary' }) {
  return (
    <div className="col">
      <div className="border rounded p-2 h-100">
        <div className={`text-${tone} fw-semibold`} style={{ fontSize: '1.25rem', lineHeight: 1.1 }}>{value}</div>
        <div className="text-muted" style={{ fontSize: '0.8rem' }}>{label}</div>
        {sub != null && <div className="text-muted" style={{ fontSize: '0.72rem' }}>{sub}</div>}
      </div>
    </div>
  );
}

function OverviewTab({ garden, onChanged }) {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    adminAPI.gardenSummary(garden.id)
      .then((res) => setSummary(res.data))
      .catch(() => toast('Could not load garden summary', { type: 'error' }))
      .finally(() => setLoading(false));
  }, [garden.id]);

  useEffect(() => { load(); }, [load]);

  const toggleActive = () => {
    setBusy(true);
    adminAPI.toggleGardenActive(garden.id)
      .then((res) => { toast(res.data.message, { type: 'success' }); load(); onChanged(); })
      .catch((e) => toast(e.response?.data?.error || 'Failed', { type: 'error' }))
      .finally(() => setBusy(false));
  };

  const setStatus = async (status) => {
    // The endpoint has two branches with inverted semantics: trialing/active/
    // expired set an ADMIN GRANT (overrides Stripe, clears any scheduled
    // cancellation) while 'free' expires the sub and CLEARS the grant. A
    // misclick can comp a paying garden or lock out a customer — confirm with
    // status-aware consequence copy before firing.
    const msg = status === 'free'
      ? `Remove "${garden.name}"'s subscription? This expires the sub and clears any admin grant.`
      : `Set "${garden.name}" to ${status} as an ADMIN GRANT? This overrides Stripe billing state and clears any scheduled cancellation.`;
    const ok = await confirmDialog(msg, { danger: true, confirmText: 'Change status' });
    if (!ok) return;
    setBusy(true);
    adminAPI.updateGardenSubscription(garden.id, { status })
      .then(() => { toast(`Subscription set to ${status}`, { type: 'success' }); load(); onChanged(); })
      .catch((e) => toast(e.response?.data?.error || 'Failed', { type: 'error' }))
      .finally(() => setBusy(false));
  };

  if (loading) return <div className="text-center py-3"><div className="spinner-border spinner-border-sm text-success"></div></div>;
  if (!summary) return <p className="text-muted">No data.</p>;

  const f = summary.finance, im = summary.impact, p = summary.plots;
  const listed = summary.is_active;

  return (
    <div>
      <div className="d-flex flex-wrap gap-2 align-items-center mb-3">
        <span className={`badge ${listed ? 'bg-success' : 'bg-secondary'}`}>
          <i className={`bi ${listed ? 'bi-eye' : 'bi-eye-slash'} me-1`}></i>
          {listed ? 'Listed' : 'Delisted'}
        </span>
        <button className="btn btn-sm btn-outline-secondary" onClick={toggleActive} disabled={busy}>
          {listed ? 'Delist from discovery' : 'List in discovery'}
        </button>

        <span className="vr mx-1"></span>

        <span className="text-muted small">Subscription:</span>
        <div className="btn-group btn-group-sm">
          <button className="btn btn-outline-secondary dropdown-toggle" data-bs-toggle="dropdown" disabled={busy}>
            {summary.subscription.status}{summary.subscription.admin_granted ? ' (admin)' : ''}
          </button>
          <ul className="dropdown-menu">
            {SUB_STATUSES.map((s) => (
              <li key={s}>
                <button className="dropdown-item" onClick={() => setStatus(s)}
                        disabled={s === summary.subscription.status}>
                  {s}{s === summary.subscription.status ? ' (current)' : ''}
                </button>
              </li>
            ))}
          </ul>
        </div>
        {/* The dates the override overrides — from the list-row prop (same
            payload; setStatus's onChanged() reload keeps the two in sync). */}
        {garden.trial_end && summary.subscription.status === 'trialing' && (
          <span className="text-muted small">trial ends {new Date(garden.trial_end).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</span>
        )}
        {garden.current_period_end && summary.subscription.status === 'active' && (
          <span className="text-muted small">renews {new Date(garden.current_period_end).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</span>
        )}
      </div>

      <div className="row row-cols-2 row-cols-md-4 g-2 mb-2">
        <StatCard label="Plot occupancy" value={`${p.occupancy_pct}%`} sub={`${p.assigned}/${p.total} assigned`} tone="success" />
        <StatCard label="Members" value={summary.members} tone="primary" />
        <StatCard label="Harvest logged" value={`${im.harvest_lbs} lb`} tone="success" />
        <StatCard label="Events" value={im.total_events} sub={`${im.upcoming_events} upcoming`} tone="info" />
      </div>
      <div className="row row-cols-2 row-cols-md-4 g-2">
        <StatCard label="Dues collected" value={money(f.dues_collected)} sub={`${f.collection_rate}% of ${money(f.dues_expected)}`} tone="success" />
        <StatCard label="Dues outstanding" value={money(f.dues_outstanding)} tone={f.dues_outstanding > 0 ? 'warning' : 'secondary'} />
        <StatCard label="Expenses" value={money(f.expenses)} tone="danger" />
        <StatCard label="Net balance" value={money(f.net_balance)} tone={f.net_balance >= 0 ? 'success' : 'danger'} />
      </div>
    </div>
  );
}

const FIELDS = [
  { key: 'name', label: 'Name', type: 'text', col: 6 },
  { key: 'contact_email', label: 'Contact email', type: 'email', col: 6 },
  { key: 'address', label: 'Address', type: 'text', col: 6 },
  { key: 'city', label: 'City', type: 'text', col: 3 },
  { key: 'state', label: 'State', type: 'text', col: 3 },
  { key: 'zip_code', label: 'ZIP', type: 'text', col: 3 },
  { key: 'plot_fee_annual', label: 'Annual plot fee ($)', type: 'number', col: 3 },
  { key: 'season_start', label: 'Season start', type: 'date', col: 3 },
  { key: 'season_end', label: 'Season end', type: 'date', col: 3 },
];

function EditTab({ garden, onChanged }) {
  const [form, setForm] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    adminAPI.gardenDetails(garden.id)
      .then((res) => setForm(res.data.garden))
      .catch(() => toast('Could not load garden details', { type: 'error' }))
      .finally(() => setLoading(false));
  }, [garden.id]);

  const set = (k, v) => setForm((prev) => ({ ...prev, [k]: v }));

  const save = (e) => {
    e.preventDefault();
    setSaving(true);
    adminAPI.updateGarden(garden.id, form)
      .then(() => { toast('Garden updated', { type: 'success' }); onChanged(); })
      .catch((err) => toast(err.response?.data?.error || 'Update failed', { type: 'error' }))
      .finally(() => setSaving(false));
  };

  if (loading || !form) return <div className="text-center py-3"><div className="spinner-border spinner-border-sm text-success"></div></div>;

  return (
    <form onSubmit={save}>
      <div className="row g-2">
        {FIELDS.map((fld) => (
          <div className={`col-md-${fld.col}`} key={fld.key}>
            <label className="form-label small mb-0">{fld.label}</label>
            <input
              type={fld.type}
              className="form-control form-control-sm"
              value={form[fld.key] ?? ''}
              step={fld.type === 'number' ? '0.01' : undefined}
              onChange={(e) => set(fld.key, e.target.value)}
            />
          </div>
        ))}
        <div className="col-md-3">
          <label className="form-label small mb-0">Operating model</label>
          <select className="form-select form-select-sm" value={form.operating_model || 'allotment'} onChange={(e) => set('operating_model', e.target.value)}>
            {OPERATING_MODELS.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
        </div>
        <div className="col-12">
          <label className="form-label small mb-0">Description</label>
          <textarea className="form-control form-control-sm" rows="2" value={form.description ?? ''} onChange={(e) => set('description', e.target.value)} />
        </div>
        <div className="col-12">
          <label className="form-label small mb-0">Rules</label>
          <textarea className="form-control form-control-sm" rows="2" value={form.rules ?? ''} onChange={(e) => set('rules', e.target.value)} />
        </div>
      </div>
      <div className="mt-3">
        <button type="submit" className="btn btn-sm btn-success" disabled={saving}>
          {saving ? 'Saving…' : 'Save changes'}
        </button>
      </div>
    </form>
  );
}

function MembersTab({ garden }) {
  const [members, setMembers] = useState(null);

  useEffect(() => {
    adminAPI.gardenMembers(garden.id)
      .then((res) => setMembers(res.data.members))
      .catch(() => setMembers([]));
  }, [garden.id]);

  if (members === null) return <div className="text-center py-3"><div className="spinner-border spinner-border-sm text-success"></div></div>;
  if (members.length === 0) return <p className="text-muted mb-0">No members.</p>;

  return (
    <table className="table table-sm mb-0">
      <thead><tr><th>Name</th><th>Email</th><th>Phone</th><th>Role</th><th>Plot</th><th>Joined</th></tr></thead>
      <tbody>
        {members.map((m) => (
          <tr key={m.id}>
            <td>{m.name}</td>
            <td><small>{m.email}</small></td>
            <td><small>{m.phone || '—'}</small></td>
            <td><span className="badge bg-info text-dark">{m.role}</span></td>
            <td>{m.plot_number || '—'}</td>
            <td><small>{m.joined_at ? new Date(m.joined_at).toLocaleDateString() : '—'}</small></td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function OwnershipTab({ garden, onChanged }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState(null);
  const [searching, setSearching] = useState(false);
  const [busy, setBusy] = useState(false);

  const search = (e) => {
    e.preventDefault();
    if (!query.trim()) return;
    setSearching(true);
    adminAPI.users({ q: query.trim() })
      .then((res) => setResults(res.data.users))
      .catch(() => setResults([]))
      .finally(() => setSearching(false));
  };

  const transfer = async (u) => {
    const ok = await confirmDialog(
      `Make ${u.display_name || u.username} (${u.email}) the organizer of "${garden.name}"? The current organizer becomes a co-organizer.`,
      { title: 'Transfer ownership', confirmText: 'Transfer', icon: 'bi-person-badge' }
    );
    if (!ok) return;
    setBusy(true);
    adminAPI.transferGarden(garden.id, { user_id: u.id })
      .then((res) => { toast(res.data.message, { type: 'success' }); onChanged(); })
      .catch((err) => toast(err.response?.data?.error || 'Transfer failed', { type: 'error' }))
      .finally(() => setBusy(false));
  };

  return (
    <div>
      <p className="mb-2">
        Current organizer: <strong>{garden.organizer?.name}</strong>{' '}
        <small className="text-muted">{garden.organizer?.email}</small>
      </p>
      <form className="input-group input-group-sm mb-2" style={{ maxWidth: 460 }} onSubmit={search}>
        <input className="form-control" placeholder="Search users by name or email…" value={query} onChange={(e) => setQuery(e.target.value)} />
        <button className="btn btn-outline-secondary" type="submit" disabled={searching}>
          {searching ? '…' : 'Search'}
        </button>
      </form>
      {results !== null && (
        results.length === 0 ? (
          <p className="text-muted small mb-0">No matching users.</p>
        ) : (
          <ul className="list-group list-group-flush" style={{ maxWidth: 560 }}>
            {results.map((u) => (
              <li key={u.id} className="list-group-item d-flex justify-content-between align-items-center px-0">
                <span>{u.display_name || u.username} <small className="text-muted">{u.email}</small></span>
                <button className="btn btn-sm btn-outline-success" disabled={busy || u.id === garden.organizer?.id} onClick={() => transfer(u)}>
                  {u.id === garden.organizer?.id ? 'Current' : 'Make organizer'}
                </button>
              </li>
            ))}
          </ul>
        )
      )}
    </div>
  );
}

function DangerTab({ garden, onChanged, onClose }) {
  const [confirmName, setConfirmName] = useState('');
  const [busy, setBusy] = useState(false);

  const del = () => {
    setBusy(true);
    adminAPI.deleteGarden(garden.id, { confirm_name: confirmName })
      .then((res) => { toast(res.data.message, { type: 'success' }); onClose?.(); onChanged(); })
      .catch((err) => toast(err.response?.data?.error || 'Delete failed', { type: 'error' }))
      .finally(() => setBusy(false));
  };

  return (
    <div className="border border-danger rounded p-3" style={{ maxWidth: 560 }}>
      <h6 className="text-danger"><i className="bi bi-exclamation-octagon me-1"></i>Delete this garden</h6>
      <p className="small text-muted mb-2">
        Permanently deletes <strong>{garden.name}</strong> and all of its plots, dues, expenses,
        events, photos, resources, announcements and memberships. This cannot be undone.
        To delist without deleting, use <em>Overview → Delist from discovery</em>.
      </p>
      <label className="form-label small mb-1">Type the garden name to confirm:</label>
      <input className="form-control form-control-sm mb-2" value={confirmName} onChange={(e) => setConfirmName(e.target.value)} placeholder={garden.name} />
      <button className="btn btn-sm btn-danger" disabled={busy || confirmName.trim() !== garden.name} onClick={del}>
        {busy ? 'Deleting…' : 'Delete garden permanently'}
      </button>
    </div>
  );
}
