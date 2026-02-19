import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { profileAPI } from '../api';

const STATUS_BADGE = {
  pending: 'bg-warning text-dark',
  accepted: 'bg-info text-white',
  completed: 'bg-success',
  cancelled: 'bg-danger',
};

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    profileAPI.dashboard()
      .then(res => setData(res.data))
      .catch(() => setError('Failed to load dashboard data.'));
  }, []);

  if (error) return <div className="alert alert-danger">{error}</div>;
  if (!data) return <div className="text-center py-5"><div className="spinner-border text-success"></div></div>;

  return (
    <>
      <h1 className="mb-4"><i className="bi bi-speedometer2 me-2"></i>Seller Dashboard</h1>
      <div className="row mb-4">
        {[
          { label: 'Active Listings', value: data.active_listings, icon: 'bi-basket', color: 'success' },
          { label: 'Pending Orders', value: data.pending_orders, icon: 'bi-clock', color: 'warning' },
          { label: 'Completed Orders', value: data.completed_orders, icon: 'bi-check-circle', color: 'primary' },
        ].map(s => (
          <div key={s.label} className="col-md-4">
            <div className="card stat-card mb-3"><div className="card-body">
              <div className="d-flex justify-content-between align-items-center">
                <div><h6 className="text-muted mb-1">{s.label}</h6><h2 className={`text-${s.color} mb-0`}>{s.value}</h2></div>
                <i className={`bi ${s.icon} fs-1 text-${s.color}`}></i>
              </div>
            </div></div>
          </div>
        ))}
      </div>
      <div className="d-flex gap-2 mb-4 flex-wrap">
        <Link to="/listings/create" className="btn btn-success"><i className="bi bi-plus-circle me-1"></i>New Listing</Link>
        <Link to="/seller/orders" className="btn btn-outline-primary"><i className="bi bi-box-seam me-1"></i>Seller Orders</Link>
        <Link to="/profile/edit" className="btn btn-outline-secondary"><i className="bi bi-pencil me-1"></i>Edit Profile</Link>
      </div>
      <h4>Recent Orders</h4>
      {data.recent_orders.length === 0 ? <p className="text-muted">No orders yet.</p> : (
        <table className="table">
          <thead><tr><th>#</th><th>Buyer</th><th>Total</th><th>Status</th><th>Date</th><th></th></tr></thead>
          <tbody>{data.recent_orders.map(o => (
            <tr key={o.id}>
              <td>{o.id}</td><td>{o.buyer_name}</td><td>${o.total_price.toFixed(2)}</td>
              <td><span className={`badge ${STATUS_BADGE[o.status] || 'bg-secondary'}`}>{o.status}</span></td>
              <td>{new Date(o.created_at).toLocaleDateString()}</td>
              <td><Link to={`/orders/${o.id}`} className="btn btn-sm btn-outline-primary">View</Link></td>
            </tr>
          ))}</tbody>
        </table>
      )}
    </>
  );
}
