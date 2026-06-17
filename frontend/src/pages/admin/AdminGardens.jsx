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

const COL_COUNT = 8;

export default function AdminGardens() {
  const { user } = useAuth();
  const [gardens, setGardens] = useState([]);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [statusFilter, setStatusFilter] = useState('');
  const [activeFilter, setActiveFilter] = useState('');   // '', 'true', 'false'
  const [search, setSearch] = useState('');
  const [query, setQuery] = useState('');                 // committed search term
  const [loading, setLoading] = useState(true);
  const [expandedGarden, setExpandedGarden] = useState(null);

  if (!user?.is_admin) return <div className="alert alert-danger">Access denied</div>;

  const load = () => {
    setLoading(true);
    adminAPI.gardens({ page, status: statusFilter, active: activeFilter, q: query }).then(res => {
      setGardens(res.data.gardens);
      setPages(res.data.pages);
      setTotal(res.data.total);
      setLoading(false);
    }).catch(() => setLoading(false));
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

  const tabs = [
    { label: 'All', value: '' },
    { label: 'Trialing', value: 'trialing' },
    { label: 'Active', value: 'active' },
    { label: 'Expired', value: 'expired' },
    { label: 'Free', value: 'free' },
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
                    <td>{g.billing_cycle || '—'}</td>
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
