import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { adminAPI, bookingAPI } from '../../api';
import { useAuth } from '../../AuthContext';
import { useSiteConfig } from '../../SiteConfigContext';
import AdminHeader from '../../components/AdminHeader';

const ORDER_BADGE = {
  pending: 'bg-warning text-dark',
  accepted: 'bg-info text-white',
  completed: 'bg-success',
  cancelled: 'bg-danger',
};
const SUB_BADGE = {
  free: 'bg-secondary',
  trialing: 'bg-info text-dark',
  active: 'bg-success',
  past_due: 'bg-warning text-dark',
  expired: 'bg-danger',
};

const fmtDate = (iso) =>
  iso ? new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : '—';

// Week-over-week delta chip (pattern shared with AdminAnalytics).
function Delta({ now, prev }) {
  if (prev == null) return null;
  const diff = now - prev;
  if (diff === 0) return <span className="text-muted small ms-1">±0 wk</span>;
  return (
    <span className={`small ms-1 ${diff > 0 ? 'text-success' : 'text-danger'}`}>
      {diff > 0 ? '▲' : '▼'}{Math.abs(diff)} wk
    </span>
  );
}

export default function AdminDashboard() {
  const { user } = useAuth();
  const { marketplaceEnabled } = useSiteConfig();
  const [data, setData] = useState(null);
  const [bookings, setBookings] = useState(null);
  const [error, setError] = useState(null);

  const load = () => {
    setError(null);
    adminAPI.dashboard()
      .then(res => setData(res.data))
      .catch(() => setError('Failed to load dashboard data.'));
    // Same call AdminBooking makes — no new endpoint.
    bookingAPI.admin.bookings()
      .then(res => setBookings(res.data.upcoming || []))
      .catch(() => setBookings([]));
  };
  useEffect(() => { if (user?.is_admin) load(); }, [user]);

  if (!user?.is_admin) return <div className="alert alert-danger text-center"><h4>Access Denied</h4></div>;
  if (error) return (
    <div className="alert alert-warning d-flex align-items-center justify-content-between">
      <span><i className="bi bi-wifi-off me-2"></i>{error}</span>
      <button className="btn btn-sm btn-outline-secondary" onClick={load}>Try again</button>
    </div>
  );
  if (!data) return <div className="text-center py-5"><div className="spinner-border text-success"></div></div>;

  const g = data.gardens || { total: 0, status_counts: {}, new: {} };
  const sc = g.status_counts || {};
  const soonestTrial = (data.trials_ending_soon || [])[0];

  const tiles = [
    { label: 'Gardens', value: g.total, sub: <Delta now={g.new?.this_week} prev={g.new?.last_week} />, icon: 'bi-tree' },
    { label: 'Active subs', value: sc.active || 0, icon: 'bi-patch-check' },
    { label: 'Trialing', value: sc.trialing || 0, icon: 'bi-hourglass-split',
      sub: soonestTrial ? <span className="text-muted small">next ends {fmtDate(soonestTrial.trial_end)}</span> : null },
    { label: 'Past due', value: sc.past_due || 0, icon: 'bi-exclamation-octagon',
      danger: (sc.past_due || 0) > 0 },
    { label: 'New users (wk)', value: data.users_new?.this_week ?? 0, icon: 'bi-person-plus',
      sub: <Delta now={data.users_new?.this_week} prev={data.users_new?.last_week} /> },
    { label: 'Estimated MRR', value: `$${(data.estimated_mrr || 0).toFixed(0)}`, icon: 'bi-cash-coin',
      sub: <span className="text-muted small" title="From pricing config × active subs (annual ÷12). Promos and legacy prices drift from actual Stripe charges.">estimate</span> },
    { label: 'Upcoming meetings', value: bookings == null ? '…' : bookings.length, icon: 'bi-calendar-check',
      to: '/admin/booking' },
  ];

  const mktStats = [
    { label: 'Sellers', value: data.total_sellers, icon: 'bi-shop' },
    { label: 'Listings', value: data.total_listings, icon: 'bi-basket' },
    { label: 'Orders', value: data.total_orders, icon: 'bi-bag' },
    { label: 'Gross Revenue', value: `$${data.revenue.toFixed(2)}`, icon: 'bi-currency-dollar' },
    { label: 'Platform Revenue', value: `$${(data.platform_revenue || 0).toFixed(2)}`, icon: 'bi-bank' },
  ];

  return (
    <>
      <AdminHeader title="Admin Dashboard" icon="bi-shield-lock" backTo="/" />

      <div className="row mb-4">
        {tiles.map(t => (
          <div key={t.label} className="col-6 col-md-4 col-lg-3 col-xl-auto flex-xl-fill">
            <div className={`card stat-card text-center mb-3 ${t.danger ? 'border-danger' : ''}`}>
              <div className="card-body py-3">
                <i className={`bi ${t.icon} fs-4 ${t.danger ? 'text-danger' : ''}`}></i>
                <h4 className="mb-0">{t.to ? <Link to={t.to} className="text-decoration-none text-reset">{t.value}</Link> : t.value}</h4>
                <small className="text-muted d-block">{t.label}{t.sub}</small>
              </div>
            </div>
          </div>
        ))}
      </div>

      {(data.trials_ending_soon || []).length > 0 && (
        <div className="alert alert-warning py-2 d-flex flex-wrap align-items-center gap-2" style={{ fontSize: '.9rem' }}>
          <i className="bi bi-alarm"></i>
          <strong>Trials ending within 7 days:</strong>
          {data.trials_ending_soon.map(t => (
            <span key={t.garden_id} className="badge text-bg-light border">
              {t.name} · {t.days_left}d
            </span>
          ))}
          <Link to="/admin/gardens" className="ms-auto">Review gardens →</Link>
        </div>
      )}

      <div className="row">
        <div className="col-md-8">
          <div className="d-flex align-items-center justify-content-between">
            <h4>Newest Gardens</h4>
            <Link to="/admin/gardens" className="small">All gardens →</Link>
          </div>
          <table className="table table-sm align-middle">
            <thead><tr><th>Garden</th><th>Organizer</th><th>Status</th><th>Created</th></tr></thead>
            <tbody>{(data.newest_gardens || []).map(ng => (
              <tr key={ng.id}>
                <td><Link to="/admin/gardens" className="text-decoration-none fw-semibold">{ng.name}</Link></td>
                <td>{ng.organizer}</td>
                <td><span className={`badge ${SUB_BADGE[ng.status] || 'bg-secondary'}`}>{ng.status}</span></td>
                <td className="text-muted">{fmtDate(ng.created_at)}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
        <div className="col-md-4">
          <div className="d-flex align-items-center justify-content-between">
            <h4>New Users</h4>
            <Link to="/admin/users" className="small">All users →</Link>
          </div>
          {data.recent_users.map(u => (
            <div key={u.id} className="d-flex justify-content-between mb-2">
              <Link to="/admin/users" className="text-decoration-none text-reset">{u.display_name || u.username}</Link>
              <span className="text-muted small">{fmtDate(u.created_at)}</span>
            </div>
          ))}
        </div>
      </div>

      {marketplaceEnabled && (
        <>
          <hr />
          <h5 className="text-muted">Marketplace</h5>
          <div className="row mb-3">
            {mktStats.map(s => (
              <div key={s.label} className="col-6 col-md-4 col-lg-2">
                <div className="card stat-card text-center mb-3"><div className="card-body py-3">
                  <i className={`bi ${s.icon} fs-4`}></i>
                  <h5 className="mb-0">{s.value}</h5>
                  <small className="text-muted">{s.label}</small>
                </div></div>
              </div>
            ))}
          </div>
          <h5>Recent Orders</h5>
          <table className="table table-sm">
            <thead><tr><th>#</th><th>Buyer</th><th>Seller</th><th>Total</th><th>Status</th></tr></thead>
            <tbody>{data.recent_orders.slice(0, 5).map(o => (
              <tr key={o.id}><td>{o.id}</td><td>{o.buyer_name}</td><td>{o.seller_name}</td><td>${o.total_price.toFixed(2)}</td><td><span className={`badge ${ORDER_BADGE[o.status] || 'bg-secondary'}`}>{o.status}</span></td></tr>
            ))}</tbody>
          </table>
        </>
      )}
    </>
  );
}
