import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ordersAPI } from '../api';

export default function Orders() {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    ordersAPI.mine().then(res => { setOrders(res.data); setLoading(false); });
  }, []);

  const cancel = async (id) => {
    if (!confirm('Cancel this order?')) return;
    await ordersAPI.cancel(id);
    const res = await ordersAPI.mine();
    setOrders(res.data);
  };

  if (loading) return <div className="text-center py-5"><div className="spinner-border text-success"></div></div>;

  return (
    <>
      <h1 className="mb-4"><i className="bi bi-bag me-2"></i>My Orders</h1>
      {orders.length === 0 ? (
        <p className="text-muted">No orders yet. <Link to="/browse">Browse produce</Link></p>
      ) : (
        orders.map(o => (
          <div key={o.id} className="card mb-3">
            <div className="card-body">
              <div className="d-flex justify-content-between align-items-start">
                <div>
                  <h5>Order #{o.id} — {o.seller_name}</h5>
                  <span className={`badge badge-${o.status}`}>{o.status}</span>
                  <span className="text-muted ms-2">{new Date(o.created_at).toLocaleDateString()}</span>
                </div>
                <span className="fs-5 fw-bold text-success">${o.total_price.toFixed(2)}</span>
              </div>
              <div className="mt-2 text-muted small">{o.items.map(i => i.listing_title).join(', ')}</div>
              <div className="mt-2 d-flex gap-2">
                <Link to={`/orders/${o.id}`} className="btn btn-sm btn-outline-primary">View Details</Link>
                {o.status === 'pending' && <button className="btn btn-sm btn-outline-danger" onClick={() => cancel(o.id)}>Cancel</button>}
                {o.status === 'completed' && !o.has_review && <Link to={`/orders/${o.id}/review`} className="btn btn-sm btn-outline-warning">Leave Review</Link>}
              </div>
            </div>
          </div>
        ))
      )}
    </>
  );
}
