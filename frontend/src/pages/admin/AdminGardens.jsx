import { useState, useEffect } from 'react';
import { adminAPI } from '../../api';
import { useAuth } from '../../AuthContext';

const STATUS_BADGE = {
  free: 'bg-secondary',
  trialing: 'bg-info text-dark',
  active: 'bg-success',
  past_due: 'bg-warning text-dark',
  expired: 'bg-danger',
};

export default function AdminGardens() {
  const { user } = useAuth();
  const [gardens, setGardens] = useState([]);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [expandedGarden, setExpandedGarden] = useState(null);
  const [members, setMembers] = useState([]);
  const [membersLoading, setMembersLoading] = useState(false);

  if (!user?.is_admin) return <div className="alert alert-danger">Access denied</div>;

  const load = () => {
    setLoading(true);
    adminAPI.gardens({ page, status: statusFilter }).then(res => {
      setGardens(res.data.gardens);
      setPages(res.data.pages);
      setTotal(res.data.total);
      setLoading(false);
    }).catch(() => setLoading(false));
  };

  useEffect(() => { load(); }, [page, statusFilter]);

  const viewMembers = (gardenId) => {
    if (expandedGarden === gardenId) { setExpandedGarden(null); return; }
    setExpandedGarden(gardenId);
    setMembersLoading(true);
    adminAPI.gardenMembers(gardenId).then(res => {
      setMembers(res.data.members);
      setMembersLoading(false);
    }).catch(() => setMembersLoading(false));
  };

  const updateStatus = (gardenId, newStatus) => {
    adminAPI.updateGardenSubscription(gardenId, { status: newStatus }).then(() => load());
  };

  const tabs = [
    { label: 'All', value: '' },
    { label: 'Trialing', value: 'trialing' },
    { label: 'Active', value: 'active' },
    { label: 'Expired', value: 'expired' },
    { label: 'Free', value: 'free' },
  ];

  return (
    <>
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h1><i className="bi bi-tree me-2"></i>Garden Management</h1>
        <span className="badge bg-secondary fs-6">{total} gardens</span>
      </div>

      <ul className="nav nav-tabs mb-3">
        {tabs.map(t => (
          <li key={t.value} className="nav-item">
            <button className={`nav-link ${statusFilter === t.value ? 'active' : ''}`} onClick={() => { setStatusFilter(t.value); setPage(1); }}>{t.label}</button>
          </li>
        ))}
      </ul>

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
                <th>Subscription</th>
                <th>Billing</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {gardens.map(g => (
                <>
                  <tr key={g.id}>
                    <td><strong>{g.name}</strong><br /><small className="text-muted">ID: {g.id}</small></td>
                    <td>{g.organizer.name}<br /><small className="text-muted">{g.organizer.email}</small></td>
                    <td><span className="badge bg-primary">{g.member_count}</span></td>
                    <td>{g.plot_count}</td>
                    <td><span className={`badge ${STATUS_BADGE[g.subscription_status] || 'bg-secondary'}`}>{g.subscription_status}</span></td>
                    <td>{g.billing_cycle || '—'}</td>
                    <td>
                      <div className="btn-group btn-group-sm">
                        <button className="btn btn-outline-primary" onClick={() => viewMembers(g.id)}>
                          <i className={`bi ${expandedGarden === g.id ? 'bi-chevron-up' : 'bi-people'} me-1`}></i>
                          {expandedGarden === g.id ? 'Hide' : 'Members'}
                        </button>
                        <div className="btn-group btn-group-sm">
                          <button className="btn btn-outline-secondary dropdown-toggle" data-bs-toggle="dropdown">Status</button>
                          <ul className="dropdown-menu">
                            {['free', 'trialing', 'active', 'expired'].map(s => (
                              <li key={s}><button className="dropdown-item" onClick={() => updateStatus(g.id, s)}>{s.charAt(0).toUpperCase() + s.slice(1)}</button></li>
                            ))}
                          </ul>
                        </div>
                      </div>
                    </td>
                  </tr>
                  {expandedGarden === g.id && (
                    <tr key={`${g.id}-members`}>
                      <td colSpan="7" className="bg-light">
                        {membersLoading ? (
                          <div className="text-center py-3"><div className="spinner-border spinner-border-sm text-success"></div></div>
                        ) : members.length === 0 ? (
                          <p className="text-muted text-center py-2 mb-0">No members</p>
                        ) : (
                          <table className="table table-sm mb-0">
                            <thead><tr><th>Name</th><th>Email</th><th>Phone</th><th>Role</th><th>Plot</th><th>Joined</th></tr></thead>
                            <tbody>
                              {members.map(m => (
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
                        )}
                      </td>
                    </tr>
                  )}
                </>
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
