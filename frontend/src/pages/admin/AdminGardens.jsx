import { useState, useEffect, Fragment } from 'react';
import { adminAPI } from '../../api';
import { useAuth } from '../../AuthContext';
import AdminHeader from '../../components/AdminHeader';
import AdminGardenPanel from './AdminGardenPanel';

const STATUS_BADGE = {
  free: 'bg-secondary',
  trialing: 'bg-info text-dark',
  active: 'bg-success',
  past_due: 'bg-warning text-dark',
  expired: 'bg-danger',
};

const COL_COUNT = 9;

const fmtDate = (iso) =>
  iso ? new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : null;

// Contextual billing dates (the payload always carried them; they were never
// rendered, forcing a Stripe-dashboard round-trip for "when does this renew?").
function BillingCell({ g }) {
  if (g.subscription_status === 'trialing' && g.trial_end) {
    const days = Math.ceil((new Date(g.trial_end) - Date.now()) / 86400000);
    return (
      <span className={days <= 7 ? 'text-warning-emphasis fw-semibold' : ''}>
        Trial ends {fmtDate(g.trial_end)}{days <= 7 ? ` (${Math.max(days, 0)}d)` : ''}
      </span>
    );
  }
  if (g.subscription_status === 'active' && g.current_period_end) {
    return <>{g.billing_cycle ? `${g.billing_cycle} · ` : ''}renews {fmtDate(g.current_period_end)}</>;
  }
  if (g.subscription_status === 'past_due' && g.current_period_end) {
    return <span className="text-danger">past due since {fmtDate(g.current_period_end)}</span>;
  }
  return <>{g.billing_cycle || '—'}</>;
}

export default function AdminGardens() {
  useAuth();   // access is enforced by the requireAdmin route guard
  const [gardens, setGardens] = useState([]);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [statusCounts, setStatusCounts] = useState({});
  const [statusFilter, setStatusFilter] = useState('');
  const [activeFilter, setActiveFilter] = useState('');   // '', 'true', 'false'
  const [search, setSearch] = useState('');
  const [query, setQuery] = useState('');                 // committed search term
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [expandedGarden, setExpandedGarden] = useState(null);

  const load = () => {
    setLoading(true);
    setLoadError(false);
    adminAPI.gardens({ page, status: statusFilter, active: activeFilter, q: query }).then(res => {
      setGardens(res.data.gardens);
      setPages(res.data.pages);
      setTotal(res.data.total);
      setStatusCounts(res.data.status_counts || {});
      setLoading(false);
    }).catch(() => { setLoadError(true); setLoading(false); });
  };

  useEffect(() => { load(); }, [page, statusFilter, activeFilter, query]);

  const toggleManage = (gardenId) => {
    setExpandedGarden((cur) => (cur === gardenId ? null : gardenId));
  };

  const submitSearch = (e) => {
    e.preventDefault();
    setPage(1);
    setQuery(search.trim());
  };

  const totalCount = Object.values(statusCounts).reduce((a, b) => a + b, 0);
  const withCount = (label, n) => (n != null ? `${label} (${n})` : label);
  const tabs = [
    { label: withCount('All', totalCount || null), value: '' },
    { label: withCount('Trialing', statusCounts.trialing ?? 0), value: 'trialing' },
    { label: withCount('Active', statusCounts.active ?? 0), value: 'active' },
    // Read-only monitoring: past_due arrives via Stripe webhooks only.
    { label: withCount('Past due', statusCounts.past_due ?? 0), value: 'past_due' },
    { label: withCount('Expired', statusCounts.expired ?? 0), value: 'expired' },
    { label: withCount('Free', statusCounts.free ?? 0), value: 'free' },
  ];

  const listingFilters = [
    { label: 'All', value: '' },
    { label: 'Listed', value: 'true' },
    { label: 'Delisted', value: 'false' },
  ];

  return (
    <>
      <div className="d-flex justify-content-between align-items-center mb-4">
        <AdminHeader title="Garden Management" icon="bi-tree" />
        <span className="badge bg-secondary fs-6">{total} gardens</span>
      </div>

      <div className="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">
        <ul className="nav nav-tabs mb-0">
          {tabs.map(t => (
            <li key={t.value} className="nav-item">
              <button className={`nav-link ${statusFilter === t.value ? 'active' : ''}`} onClick={() => { setStatusFilter(t.value); setPage(1); }}>{t.label}</button>
            </li>
          ))}
        </ul>

        <div className="d-flex align-items-center gap-2">
          <div className="btn-group btn-group-sm" role="group" aria-label="Listing filter">
            {listingFilters.map(lf => (
              <button
                key={lf.value}
                className={`btn ${activeFilter === lf.value ? 'btn-success' : 'btn-outline-success'}`}
                onClick={() => { setActiveFilter(lf.value); setPage(1); }}
              >{lf.label}</button>
            ))}
          </div>
          <form className="input-group input-group-sm" style={{ width: 240 }} onSubmit={submitSearch}>
            <input className="form-control" placeholder="Search gardens…" value={search} onChange={(e) => setSearch(e.target.value)} />
            <button className="btn btn-outline-secondary" type="submit"><i className="bi bi-search"></i></button>
          </form>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-5"><div className="spinner-border text-success"></div></div>
      ) : loadError ? (
        <div className="alert alert-warning d-flex align-items-center justify-content-between">
          <span><i className="bi bi-wifi-off me-2"></i>Couldn’t load gardens.</span>
          <button className="btn btn-sm btn-outline-secondary" onClick={load}>Try again</button>
        </div>
      ) : gardens.length === 0 ? (
        <div className="text-center py-5 text-muted">No gardens found</div>
      ) : (
        <div className="table-responsive">
          <table className="table table-hover align-middle">
            <thead className="table-light">
              <tr>
                <th>Garden</th>
                <th>Organizer</th>
                <th>Members</th>
                <th>Plots</th>
                <th>Listing</th>
                <th>Subscription</th>
                <th>Billing</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {gardens.map(g => (
                <Fragment key={g.id}>
                  <tr className={expandedGarden === g.id ? 'table-active' : ''}>
                    <td><strong>{g.name}</strong><br /><small className="text-muted">ID: {g.id}</small></td>
                    <td>{g.organizer.name}<br /><small className="text-muted">{g.organizer.email}</small></td>
                    <td><span className="badge bg-primary">{g.member_count}</span></td>
                    <td>{g.plot_count}</td>
                    <td>
                      {g.is_active
                        ? <span className="badge bg-success"><i className="bi bi-eye me-1"></i>Listed</span>
                        : <span className="badge bg-secondary"><i className="bi bi-eye-slash me-1"></i>Delisted</span>}
                    </td>
                    <td><span className={`badge ${STATUS_BADGE[g.subscription_status] || 'bg-secondary'}`}>{g.subscription_status}</span></td>
                    <td style={{ fontSize: '.85rem' }}><BillingCell g={g} /></td>
                    <td style={{ fontSize: '.85rem' }}>{fmtDate(g.created_at) || '—'}</td>
                    <td>
                      <button className={`btn btn-sm ${expandedGarden === g.id ? 'btn-success' : 'btn-outline-success'}`} onClick={() => toggleManage(g.id)}>
                        <i className={`bi ${expandedGarden === g.id ? 'bi-chevron-up' : 'bi-sliders'} me-1`}></i>
                        Manage
                      </button>
                    </td>
                  </tr>
                  {expandedGarden === g.id && (
                    <tr>
                      <td colSpan={COL_COUNT} className="bg-light p-0">
                        <AdminGardenPanel
                          garden={g}
                          onChanged={load}
                          onClose={() => setExpandedGarden(null)}
                        />
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {pages > 1 && (
        <nav><ul className="pagination justify-content-center">
          {Array.from({ length: pages }, (_, i) => (
            <li key={i} className={`page-item ${page === i + 1 ? 'active' : ''}`}>
              <button className="page-link" onClick={() => setPage(i + 1)}>{i + 1}</button>
            </li>
          ))}
        </ul></nav>
      )}
    </>
  );
}
