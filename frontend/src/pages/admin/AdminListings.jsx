import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { adminAPI } from '../../api';
import { useAuth } from '../../AuthContext';
import AdminHeader from '../../components/AdminHeader';

export default function AdminListings() {
  const { user } = useAuth();
  const [data, setData] = useState({ listings: [], total: 0, pages: 1, page: 1 });
  const [filter, setFilter] = useState('all');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  const fetchListings = () => {
    setLoading(true);
    adminAPI.listings({ page, status: filter })
      .then(res => { setData(res.data); setLoading(false); })
      .catch(() => setLoading(false));
  };
  useEffect(() => { if (user?.is_admin) fetchListings(); }, [page, filter, user]);

  if (!user?.is_admin) return <div className="alert alert-danger">Access Denied</div>;

  return (
    <>
      <AdminHeader title="Listing Moderation" icon="bi-shop" />
      <ul className="nav nav-tabs mb-3">
        {['all', 'active', 'inactive'].map(f => (
          <li key={f} className="nav-item">
            <button className={`nav-link ${filter === f ? 'active' : ''}`} onClick={() => { setFilter(f); setPage(1); }}>
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          </li>
        ))}
      </ul>
      {loading ? (
        <div className="text-center py-4"><div className="spinner-border text-success"></div></div>
      ) : (
        <table className="table">
          <thead><tr><th>Title</th><th>Seller</th><th>Category</th><th>Price</th><th>Qty</th><th>Status</th><th>Actions</th></tr></thead>
          <tbody>{data.listings.map(l => (
            <tr key={l.id}>
              <td><Link to={`/listings/${l.id}`}>{l.title}</Link></td>
              <td>{l.seller_name}</td>
              <td>{l.vegetable_type}</td>
              <td>${l.price.toFixed(2)}</td>
              <td>{l.quantity_available}</td>
              <td><span className={`badge ${l.is_active ? 'bg-success' : 'bg-secondary'}`}>{l.is_active ? 'Active' : 'Inactive'}</span></td>
              <td><button className="btn btn-sm btn-outline-warning" onClick={async () => { await adminAPI.toggleListing(l.id); fetchListings(); }}>{l.is_active ? 'Deactivate' : 'Activate'}</button></td>
            </tr>
          ))}</tbody>
        </table>
      )}
      {data.pages > 1 && (
        <nav><ul className="pagination justify-content-center">
          {Array.from({ length: data.pages }, (_, i) => (
            <li key={i} className={`page-item ${page === i + 1 ? 'active' : ''}`}><button className="page-link" onClick={() => setPage(i + 1)}>{i + 1}</button></li>
          ))}
        </ul></nav>
      )}
    </>
  );
}
