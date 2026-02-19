import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { adminAPI } from '../../api';
import { useAuth } from '../../AuthContext';

export default function AdminDashboard() {
  const { user } = useAuth();
  const [data, setData] = useState(null);

  useEffect(() => {
    if (user?.is_admin) adminAPI.dashboard().then(res => setData(res.data));
  }, [user]);

  if (!user?.is_admin) return <div className="alert alert-danger text-center"><h4>Access Denied</h4></div>;
  if (!data) return <div className="text-center py-5"><div className="spinner-border text-success"></div></div>;

  const stats = [
    { label: 'Users', value: data.total_users, icon: 'bi-people', color: 'primary' },
    { label: 'Sellers', value: data.total_sellers, icon: 'bi-shop', color: 'success' },
    { label: 'Buyers', value: data.total_buyers, icon: 'bi-cart3', color: 'info' },
    { label: 'Listings', value: data.total_listings, icon: 'bi-basket', color: 'warning' },
    { label: 'Orders', value: data.total_orders, icon: 'bi-bag', color: 'secondary' },
    { label: 'Revenue', value: `$${data.revenue.toFixed(2)}`, icon: 'bi-currency-dollar', color: 'success' },
  ];

  return (
    <>
      <h1 className="mb-4"><i className="bi bi-shield-lock me-2"></i>Admin Dashboard</h1>
      <div className="row mb-4">
        {stats.map(s => (
          <div key={s.label} className="col-md-2">
            <div className="card stat-card text-center mb-3"><div className="card-body">
              <i className={`bi ${s.icon} fs-3 text-${s.color}`}></i>
              <h4 className="mb-0">{s.value}</h4>
              <small className="text-muted">{s.label}</small>
            </div></div>
          </div>
        ))}
      </div>
      <div className="d-flex gap-2 mb-4">
        <Link to="/admin/users" className="btn btn-primary"><i className="bi bi-people me-1"></i>Manage Users</Link>
        <Link to="/admin/listings" className="btn btn-success"><i className="bi bi-basket me-1"></i>Manage Listings</Link>
        <Link to="/admin/orders" className="btn btn-info text-white"><i className="bi bi-bag me-1"></i>Manage Orders</Link>
        <Link to="/admin/pricing" className="btn btn-warning"><i className="bi bi-graph-up me-1"></i>Pricing Config</Link>
      </div>
      <div className="row">
        <div className="col-md-8">
          <h4>Recent Orders</h4>
          <table className="table table-sm">
            <thead><tr><th>#</th><th>Buyer</th><th>Seller</th><th>Total</th><th>Status</th></tr></thead>
            <tbody>{data.recent_orders.slice(0, 5).map(o => (
              <tr key={o.id}><td>{o.id}</td><td>{o.buyer_name}</td><td>{o.seller_name}</td><td>${o.total_price.toFixed(2)}</td><td><span className={`badge badge-${o.status}`}>{o.status}</span></td></tr>
            ))}</tbody>
          </table>
        </div>
        <div className="col-md-4">
          <h4>New Users</h4>
          {data.recent_users.map(u => (
            <div key={u.id} className="d-flex justify-content-between mb-2">
              <span>{u.display_name || u.username}</span>
              <span className="badge bg-secondary">{u.role}</span>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
