import { useState, useEffect } from 'react';
import { adminAPI } from '../../api';
import { useAuth } from '../../AuthContext';

export default function AdminOrders() {
  const { user } = useAuth();
  const [data, setData] = useState({ orders: [], total: 0, pages: 1, page: 1 });
  const [filter, setFilter] = useState('all');
  const [page, setPage] = useState(1);

  useEffect(() => {
    if (user?.is_admin) adminAPI.orders({ page, status: filter }).then(res => setData(res.data));
  }, [page, filter, user]);

  if (!user?.is_admin) return <div className="alert alert-danger">Access Denied</div>;

  const tabs = ['all', 'pending', 'accepted', 'completed', 'cancelled'];

  return (
    <>
      <h1 className="mb-4"><i className="bi bi-bag me-2"></i>Manage Orders</h1>
      <ul className="nav nav-tabs mb-3">
        {tabs.map(t => (
          <li key={t} className="nav-item">
            <button className={`nav-link ${filter === t ? 'active' : ''}`} onClick={() => { setFilter(t); setPage(1); }}>
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </button>
          </li>
        ))}
      </ul>
      <table className="table">
        <thead><tr><th>#</th><th>Buyer</th><th>Seller</th><th>Total</th><th>Status</th><th>Method</th><th>Date</th></tr></thead>
        <tbody>{data.orders.map(o => (
          <tr key={o.id}>
            <td>{o.id}</td><td>{o.buyer_name}</td><td>{o.seller_name}</td>
            <td>${o.total_price.toFixed(2)}</td>
            <td><span className={`badge badge-${o.status}`}>{o.status}</span></td>
            <td>{o.fulfillment_method}</td>
            <td>{new Date(o.created_at).toLocaleDateString()}</td>
          </tr>
        ))}</tbody>
      </table>
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
