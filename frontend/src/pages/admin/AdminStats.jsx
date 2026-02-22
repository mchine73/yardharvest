import { useState, useEffect } from 'react';
import { adminAPI } from '../../api';
import { useAuth } from '../../AuthContext';

const PERIODS = [
  { key: 'week', label: 'This Week' },
  { key: 'month', label: 'This Month' },
  { key: 'quarter', label: 'This Quarter' },
  { key: 'year', label: 'This Year' },
  { key: 'all', label: 'All Time' },
];

export default function AdminStats() {
  const { user } = useAuth();
  const [period, setPeriod] = useState('month');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (user?.is_admin) {
      setLoading(true);
      adminAPI.platformStats({ period })
        .then(res => setData(res.data))
        .catch(() => {})
        .finally(() => setLoading(false));
    }
  }, [user, period]);

  if (!user?.is_admin) return <div className="alert alert-danger">Access Denied</div>;

  return (
    <>
      <h1 className="mb-4"><i className="bi bi-bar-chart-line me-2"></i>Platform Statistics</h1>

      {/* Period Toggles */}
      <div className="btn-group mb-4" role="group">
        {PERIODS.map(p => (
          <button
            key={p.key}
            className={`btn ${period === p.key ? 'btn-success' : 'btn-outline-success'}`}
            onClick={() => setPeriod(p.key)}
          >
            {p.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="text-center py-5"><div className="spinner-border text-success"></div></div>
      ) : !data ? (
        <div className="alert alert-warning">Failed to load statistics.</div>
      ) : (
        <>
          {/* P&L Summary */}
          <div className="card mb-4 border-success">
            <div className="card-header bg-success text-white">
              <i className="bi bi-currency-dollar me-2"></i>Revenue &amp; P&amp;L
            </div>
            <div className="card-body">
              <div className="row text-center">
                <div className="col-6 col-md">
                  <small className="text-muted d-block">Gross Sales</small>
                  <h4 className="mb-0">${data.revenue.gross_sales.toFixed(2)}</h4>
                </div>
                <div className="col-6 col-md">
                  <small className="text-muted d-block">Commissions</small>
                  <h4 className="mb-0 text-info">${data.revenue.platform_commissions.toFixed(2)}</h4>
                </div>
                <div className="col-6 col-md mt-3 mt-md-0">
                  <small className="text-muted d-block">Delivery Fees</small>
                  <h4 className="mb-0 text-warning">${data.revenue.delivery_fees.toFixed(2)}</h4>
                </div>
                <div className="col-6 col-md mt-3 mt-md-0">
                  <small className="text-muted d-block">Net Platform Revenue</small>
                  <h4 className="mb-0 text-success fw-bold">${data.revenue.net_platform_revenue.toFixed(2)}</h4>
                </div>
                <div className="col-12 col-md mt-3 mt-md-0">
                  <small className="text-muted d-block">Seller Payouts</small>
                  <h4 className="mb-0">${data.revenue.seller_payouts.toFixed(2)}</h4>
                </div>
              </div>
            </div>
          </div>

          {/* Order Metrics */}
          <div className="row mb-4">
            {[
              { label: 'Total Orders', value: data.orders.total, icon: 'bi-bag', color: 'primary' },
              { label: 'Avg Order Value', value: `$${data.orders.avg_order_value.toFixed(2)}`, icon: 'bi-receipt', color: 'info' },
              { label: 'Completion Rate', value: `${data.orders.completion_rate}%`, icon: 'bi-check-circle', color: 'success' },
            ].map(s => (
              <div key={s.label} className="col-md-4 mb-3">
                <div className="card text-center h-100">
                  <div className="card-body">
                    <i className={`bi ${s.icon} fs-3 text-${s.color}`}></i>
                    <h3 className="mb-0">{s.value}</h3>
                    <small className="text-muted">{s.label}</small>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Order Status Breakdown */}
          <div className="card mb-4">
            <div className="card-header"><i className="bi bi-pie-chart me-2"></i>Orders by Status</div>
            <div className="card-body">
              <div className="row text-center">
                {Object.entries(data.orders.by_status).map(([status, count]) => (
                  <div key={status} className="col-6 col-md-3">
                    <span className={`badge mb-1 ${
                      status === 'completed' ? 'bg-success' :
                      status === 'pending' ? 'bg-warning text-dark' :
                      status === 'accepted' ? 'bg-info' :
                      'bg-danger'
                    }`}>{status}</span>
                    <h4 className="mb-0">{count}</h4>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* User Metrics */}
          <div className="row mb-4">
            {[
              { label: 'Total Users', value: data.users.total, icon: 'bi-people', color: 'primary' },
              { label: period === 'all' ? 'Total Users' : 'New Users', value: data.users.new_in_period, icon: 'bi-person-plus', color: 'info' },
              { label: 'Active Sellers', value: data.users.active_sellers, icon: 'bi-shop', color: 'success' },
              { label: 'Active Buyers', value: data.users.active_buyers, icon: 'bi-cart', color: 'warning' },
            ].map(s => (
              <div key={s.label + s.icon} className="col-6 col-md-3 mb-3">
                <div className="card text-center h-100">
                  <div className="card-body py-3">
                    <i className={`bi ${s.icon} fs-4 text-${s.color}`}></i>
                    <h4 className="mb-0">{s.value}</h4>
                    <small className="text-muted">{s.label}</small>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Top Sellers & Top Categories */}
          <div className="row">
            <div className="col-md-6 mb-4">
              <div className="card h-100">
                <div className="card-header"><i className="bi bi-trophy me-2"></i>Top Sellers</div>
                <div className="card-body p-0">
                  {data.top_sellers.length === 0 ? (
                    <p className="text-muted text-center py-3">No completed orders in this period.</p>
                  ) : (
                    <table className="table table-sm mb-0">
                      <thead><tr><th>#</th><th>Seller</th><th>Revenue</th><th>Orders</th></tr></thead>
                      <tbody>
                        {data.top_sellers.map((s, i) => (
                          <tr key={i}>
                            <td>{i + 1}</td>
                            <td>{s.name}</td>
                            <td>${s.revenue.toFixed(2)}</td>
                            <td>{s.order_count}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              </div>
            </div>
            <div className="col-md-6 mb-4">
              <div className="card h-100">
                <div className="card-header"><i className="bi bi-tags me-2"></i>Top Categories</div>
                <div className="card-body p-0">
                  {data.top_categories.length === 0 ? (
                    <p className="text-muted text-center py-3">No completed orders in this period.</p>
                  ) : (
                    <table className="table table-sm mb-0">
                      <thead><tr><th>#</th><th>Category</th><th>Revenue</th><th>Items Sold</th></tr></thead>
                      <tbody>
                        {data.top_categories.map((c, i) => (
                          <tr key={i}>
                            <td>{i + 1}</td>
                            <td>{c.category}</td>
                            <td>${c.revenue.toFixed(2)}</td>
                            <td>{c.order_count}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </>
  );
}
