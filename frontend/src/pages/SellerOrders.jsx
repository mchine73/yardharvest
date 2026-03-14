import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ordersAPI } from '../api';

export default function SellerOrders() {
  const [orders, setOrders] = useState([]);
  const [filter, setFilter] = useState('all');
  const [loading, setLoading] = useState(true);

  const fetchOrders = () => ordersAPI.selling().then(res => { setOrders(res.data); setLoading(false); });
  useEffect(() => { fetchOrders(); }, []);

  const action = async (id, fn) => { await fn(id); fetchOrders(); };

  const filtered = filter === 'all' ? orders : orders.filter(o => o.status === filter);
  const tabs = ['all', 'pending', 'accepted', 'completed', 'cancelled'];

  if (loading) return <div className="text-center py-5"><div className="spinner-border text-success"></div></div>;

  return (
    <>
      <h1 className="mb-4"><i className="bi bi-box-seam me-2"></i>Grower Orders</h1>
      <ul className="nav nav-tabs mb-3">
        {tabs.map(t => (
          <li key={t} className="nav-item">
            <button className={`nav-link ${filter === t ? 'active' : ''}`} onClick={() => setFilter(t)}>
              {t.charAt(0).toUpperCase() + t.slice(1)} {t !== 'all' && `(${orders.filter(o => o.status === t).length})`}
            </button>
          </li>
        ))}
      </ul>
      {filtered.length === 0 ? (
        <div className="text-center py-4">
          <i className="bi bi-box-seam fs-2 text-muted"></i>
          <p className="text-muted mt-2">No orders yet. Orders from buyers will appear here.</p>
        </div>
      ) : filtered.map(o => (
        <div key={o.id} className="card mb-3">
          <div className="card-body">
            <div className="d-flex justify-content-between align-items-start">
              <div>
                <h5>Order #{o.id} — from {o.buyer_name}</h5>
                <span className={`badge badge-${o.status}`}>{o.status}</span>
                <span className="text-muted ms-2">{new Date(o.created_at).toLocaleDateString()}</span>
                <span className="text-muted ms-2">({o.fulfillment_method})</span>
                {o.delivery_provider === 'doordash' && <span className="badge bg-danger ms-2">DoorDash</span>}
              </div>
              <span className="fs-5 fw-bold text-success">${o.total_price.toFixed(2)}</span>
            </div>
            <div className="mt-2 text-muted small">{o.items.map(i => `${i.listing_title} x${i.quantity}`).join(', ')}</div>
            <div className="mt-2 d-flex gap-2 flex-wrap">
              <Link to={`/orders/${o.id}`} className="btn btn-sm btn-outline-primary">Details</Link>
              {o.doordash_tracking_url && <a href={o.doordash_tracking_url} target="_blank" rel="noopener noreferrer" className="btn btn-sm btn-outline-danger"><i className="bi bi-truck me-1"></i>Track</a>}
              {o.status === 'pending' && <button className="btn btn-sm btn-primary" onClick={() => action(o.id, ordersAPI.accept)}>Accept</button>}
              {o.status === 'accepted' && <button className="btn btn-sm btn-success" onClick={() => action(o.id, ordersAPI.complete)}>Complete</button>}
              {(o.status === 'pending' || o.status === 'accepted') && <button className="btn btn-sm btn-outline-danger" onClick={() => action(o.id, ordersAPI.cancel)}>Cancel</button>}
            </div>
          </div>
        </div>
      ))}
    </>
  );
}
