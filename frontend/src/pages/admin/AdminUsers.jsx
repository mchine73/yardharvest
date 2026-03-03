import { useState, useEffect } from 'react';
import { adminAPI } from '../../api';
import { useAuth } from '../../AuthContext';
import AdminHeader from '../../components/AdminHeader';

export default function AdminUsers() {
  const { user } = useAuth();
  const [data, setData] = useState({ users: [], total: 0, pages: 1, page: 1 });
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  const fetchUsers = () => {
    setLoading(true);
    adminAPI.users({ q: search, page })
      .then(res => { setData(res.data); setLoading(false); })
      .catch(() => setLoading(false));
  };
  useEffect(() => { if (user?.is_admin) fetchUsers(); }, [page, user]);

  const doSearch = (e) => { e.preventDefault(); setPage(1); fetchUsers(); };

  if (!user?.is_admin) return <div className="alert alert-danger">Access Denied</div>;

  return (
    <>
      <AdminHeader title="User Management" icon="bi-people" />
      <form onSubmit={doSearch} className="d-flex gap-2 mb-3">
        <input className="form-control" placeholder="Search users..." value={search} onChange={e => setSearch(e.target.value)} />
        <button className="btn btn-primary">Search</button>
      </form>
      {loading ? (
        <div className="text-center py-4"><div className="spinner-border text-success"></div></div>
      ) : (
        <table className="table">
          <thead><tr><th>Username</th><th>Email</th><th>Role</th><th>Status</th><th>Admin</th><th>Actions</th></tr></thead>
          <tbody>{data.users.map(u => (
            <tr key={u.id}>
              <td>{u.display_name || u.username}</td>
              <td>{u.email}</td>
              <td><span className="badge bg-secondary">{u.role}</span></td>
              <td><span className={`badge ${u.is_active_user ? 'bg-success' : 'bg-danger'}`}>{u.is_active_user ? 'Active' : 'Suspended'}</span></td>
              <td>{u.is_admin && <span className="badge bg-warning text-dark">Admin</span>}</td>
              <td>
                <button className="btn btn-sm btn-outline-warning me-1" onClick={async () => { await adminAPI.toggleUserActive(u.id); fetchUsers(); }}>
                  {u.is_active_user ? 'Suspend' : 'Activate'}
                </button>
                <button className="btn btn-sm btn-outline-info" onClick={async () => { await adminAPI.toggleUserAdmin(u.id); fetchUsers(); }}>
                  {u.is_admin ? 'Remove Admin' : 'Make Admin'}
                </button>
              </td>
            </tr>
          ))}</tbody>
        </table>
      )}
      {data.pages > 1 && (
        <nav><ul className="pagination justify-content-center">
          {Array.from({ length: data.pages }, (_, i) => (
            <li key={i} className={`page-item ${page === i + 1 ? 'active' : ''}`}>
              <button className="page-link" onClick={() => setPage(i + 1)}>{i + 1}</button>
            </li>
          ))}
        </ul></nav>
      )}
    </>
  );
}
