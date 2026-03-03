import { useState, useEffect } from 'react';
import { adminAPI, ordersAPI } from '../../api';
import { useAuth } from '../../AuthContext';
import AdminHeader from '../../components/AdminHeader';

const STATUS_BADGE = {
  pending: 'bg-warning text-dark',
  accepted: 'bg-info text-white',
  completed: 'bg-success',
  cancelled: 'bg-danger',
};

export default function AdminOrders() {
  const { user } = useAuth();
  const [data, setData] = useState({ orders: [], total: 0, pages: 1, page: 1 });
  const [filter, setFilter] = useState('all');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [cancelling, setCancelling] = useState(null);

  const loadOrders = () => {
    if (user?.is_admin) {
      setLoading(true);
      adminAPI.orders({ page, status: filter })
        .then(res => { setData(res.data); setLoading(false); })
        .catch(() => setLoading(false));
    }
  };

  useEffect(() => { loadOrders(); }, [page, filter, user]);

  const handleCancel = async (orderId) => {
    if (!window.confirm(`Cancel order #${orderId}? This will restore inventory and notify the buyer.`)) return;
    setCancelling(orderId);
    try {
      await ordersAPI.cancel(orderId);
      loadOrders();
    } catch (err) {
      alert(err.response?.data?.error || 'Failed to cancel order');
    }
    setCancelling(null);
  };

  if (!user?.is_admin) return <div className="alert alert-danger">Access Denied</div>;

  const tabs = ['all', 'pending', 'accepted', 'completed', 'cancelled'];

  return (
    <>
      <AdminHeader title="Order Management" icon="bi-box-seam" />
      <ul className="nav nav-tabs mb-3">
        {tabs.map(t => (
          <li key={t} className="nav-item">
            <button className={`nav-link ${filter === t ? 'active' : ''}`} onClick={() => { setFilter(t); setPage(1); }}>
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </button>
          </li>
        ))}
      </ul>
      {loading ? (
        <div className="text-center py-4"><div className="spinner-border text-success"></div></div>
      ) : (
        <table className="table">
          <thead><tr><th>#</th><th>Buyer</th><th>Seller</th><th>Total</th><th>Status</th><th>Method</th><th>Date</th><th>Actions</th></tr></thead>
          <tbody>{data.orders.map(o => (
            <tr key={o.id}>
              <td>{o.id}</td><td>{o.buyer_name}</td><td>{o.seller_name}</td>
              <td>${o.total_price.toFixed(2)}</td>
              <td><span className={`badge ${STATUS_BADGE[o.status] || 'bg-secondary'}`}>{o.status}</span></td>
              <td>{o.fulfillment_method}{o.delivery_provider === 'doordash' && <span className="badge bg-danger ms-1" style={{fontSize:'0.65rem'}}>DD</span>}</td>
              <td>{new Date(o.created_at).toLocaleDateString()}</td>
              <td>
                {o.status !== 'cancelled' && (
                  <button className="btn btn-sm btn-outline-danger" disabled={cancelling === o.id}
                    onClick={() => handleCancel(o.id)}>
                    {cancelling === o.id ? <span className="spinner-border spinner-border-sm"></span> : <><i className="bi bi-x-circle me-1"></i>Cancel</>}
                  </button>
                )}
              </td>
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
