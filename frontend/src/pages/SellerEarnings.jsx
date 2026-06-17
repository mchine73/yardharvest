import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { earningsAPI, paymentAPI } from '../api';
import StripeConnectOnboarding from '../components/StripeConnectOnboarding';

const STATUS_BADGE = {
  pending: 'bg-warning text-dark',
  accepted: 'bg-info text-white',
  completed: 'bg-success',
  cancelled: 'bg-danger',
};

export default function SellerEarnings() {
  const [summary, setSummary] = useState(null);
  const [history, setHistory] = useState(null);
  const [payouts, setPayouts] = useState([]);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [connectStatus, setConnectStatus] = useState(null);
  const [connectLoading, setConnectLoading] = useState(false);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [setupError, setSetupError] = useState('');

  const refreshConnectStatus = () =>
    paymentAPI.connectStatus().then(res => setConnectStatus(res.data)).catch(() => {});

  // When the embedded flow can't load, show the real reason and keep the seller
  // in-app (the hosted-setup link below lets them proceed) — don't silently
  // bounce to Stripe. Mirrors the garden payout flow.
  const handleEmbedError = (err) => {
    const d = err?.response?.data;
    const reason = d?.detail || d?.error || err?.message
      || 'on-site setup could not load';
    setSetupError(`Couldn't load on-site payout setup — ${reason}. `
      + `You can use Stripe's hosted setup below.`);
  };

  // Manual fallback: open Stripe's hosted onboarding in a new tab.
  const openHostedOnboarding = async () => {
    setConnectLoading(true);
    try {
      const res = await paymentAPI.connectOnboard();
      if (res.data.url) window.open(res.data.url, '_blank');
    } catch (err) {
      setSetupError(err.response?.data?.detail || err.response?.data?.error
        || 'Could not start hosted payout setup.');
    }
    setConnectLoading(false);
  };

  useEffect(() => {
    Promise.all([
      earningsAPI.summary(),
      earningsAPI.history({ page }),
      earningsAPI.payouts(),
    ]).then(([sRes, hRes, pRes]) => {
      setSummary(sRes.data);
      setHistory(hRes.data);
      setPayouts(pRes.data);
      setLoading(false);
    }).catch(() => { setLoading(false); setError('Failed to load earnings data.'); });
    paymentAPI.connectStatus().then(res => setConnectStatus(res.data)).catch(() => {});
  }, [page]);

  if (loading) return <div className="text-center py-5"><div className="spinner-border text-success"></div></div>;
  if (error) return <div className="alert alert-danger"><i className="bi bi-exclamation-triangle me-2"></i>{error}</div>;

  return (
    <>
      <h1 className="mb-4"><i className="bi bi-cash-stack me-2"></i>Grower Earnings</h1>

      {/* Stripe Connect Payout Setup (in-app embedded onboarding) */}
      {connectStatus && !connectStatus.onboarded && connectStatus.configured && (
        <>
          <div className="alert alert-info d-flex align-items-center justify-content-between mb-4">
            <div>
              <i className="bi bi-bank me-2"></i>
              <strong>Set up payouts</strong> — Connect your bank account to receive earnings directly.
            </div>
            <button className="btn btn-primary btn-sm" disabled={connectLoading} onClick={() => setShowOnboarding(s => !s)}>
              {connectLoading ? <span className="spinner-border spinner-border-sm"></span> : <><i className="bi bi-link-45deg me-1"></i>{showOnboarding ? 'Hide Setup' : 'Set Up Payouts'}</>}
            </button>
          </div>
          {showOnboarding && (
            <div className="card mb-4">
              <div className="card-body">
                <h5 className="mb-3"><i className="bi bi-bank me-2"></i>Payout Setup</h5>
                {setupError && (
                  <div className="alert alert-warning py-2"><i className="bi bi-exclamation-triangle me-2"></i>{setupError}</div>
                )}
                <StripeConnectOnboarding
                  fetchAccountSession={paymentAPI.connectAccountSession}
                  onComplete={() => { setShowOnboarding(false); refreshConnectStatus(); }}
                  onError={handleEmbedError}
                />
                <button className="btn btn-link btn-sm text-muted px-0 mt-2"
                        onClick={openHostedOnboarding} disabled={connectLoading}>
                  Having trouble? Use Stripe's hosted setup instead
                </button>
              </div>
            </div>
          )}
        </>
      )}
      {connectStatus?.onboarded && (
        <div className="alert alert-success d-flex align-items-center justify-content-between mb-4">
          <div><i className="bi bi-check-circle me-2"></i><strong>Payouts active</strong> — Earnings are automatically transferred to your bank account.</div>
          {connectStatus.dashboard_url && (
            <a href={connectStatus.dashboard_url} target="_blank" rel="noopener noreferrer" className="btn btn-outline-success btn-sm">
              <i className="bi bi-box-arrow-up-right me-1"></i>Stripe Dashboard
            </a>
          )}
        </div>
      )}

      {/* Summary Cards */}
      {summary && (
        <div className="row mb-4">
          {[
            { label: 'Total Earnings', value: `$${(summary.total_earnings || 0).toFixed(2)}`, icon: 'bi-currency-dollar', color: 'success' },
            { label: 'Pending Earnings', value: `$${(summary.pending_earnings || 0).toFixed(2)}`, icon: 'bi-clock-history', color: 'warning' },
            { label: 'This Month', value: `$${(summary.this_month || 0).toFixed(2)}`, icon: 'bi-calendar-check', color: 'primary' },
            { label: 'Last Month', value: `$${(summary.last_month || 0).toFixed(2)}`, icon: 'bi-calendar', color: 'info' },
          ].map(s => (
            <div key={s.label} className="col-md-3">
              <div className="card stat-card mb-3"><div className="card-body">
                <div className="d-flex justify-content-between align-items-center">
                  <div><h6 className="text-muted mb-1">{s.label}</h6><h3 className={`text-${s.color} mb-0`}>{s.value}</h3></div>
                  <i className={`bi ${s.icon} fs-2 text-${s.color}`}></i>
                </div>
              </div></div>
            </div>
          ))}
        </div>
      )}

      {summary && (
        <div className="row mb-4">
          <div className="col-md-6">
            <div className="card"><div className="card-body">
              <div className="d-flex justify-content-between">
                <span className="text-muted">Avg Commission Rate</span>
                <strong>{((summary.avg_commission_rate || 0) * 100).toFixed(1)}%</strong>
              </div>
              <div className="d-flex justify-content-between mt-1">
                <span className="text-muted">Completed Orders</span>
                <strong>{summary.completed_orders}</strong>
              </div>
            </div></div>
          </div>
        </div>
      )}

      {/* Earnings History */}
      <h4 className="mb-3">Earnings History</h4>
      {history && history.orders.length > 0 ? (
        <>
          <div className="table-responsive">
            <table className="table table-hover">
              <thead>
                <tr>
                  <th>Order</th>
                  <th>Buyer</th>
                  <th>Subtotal</th>
                  <th>Commission</th>
                  <th>Delivery Fee</th>
                  <th>Your Earnings</th>
                  <th>Status</th>
                  <th>Date</th>
                </tr>
              </thead>
              <tbody>
                {history.orders.map(o => (
                  <tr key={o.id}>
                    <td><Link to={`/orders/${o.id}`}>#{o.id}</Link></td>
                    <td>{o.buyer_name}</td>
                    <td>${(o.subtotal || 0).toFixed(2)}</td>
                    <td className="text-danger">-${(o.platform_commission || 0).toFixed(2)}</td>
                    <td>{o.delivery_fee > 0 ? `$${o.delivery_fee.toFixed(2)}` : '-'}</td>
                    <td className="fw-bold text-success">${(o.seller_earnings || 0).toFixed(2)}</td>
                    <td><span className={`badge ${STATUS_BADGE[o.status] || 'bg-secondary'}`}>{o.status}</span></td>
                    <td>{o.created_at ? new Date(o.created_at).toLocaleDateString() : '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {history.pages > 1 && (
            <div className="d-flex justify-content-center gap-2">
              <button className="btn btn-sm btn-outline-success" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</button>
              <span className="align-self-center text-muted">Page {page} of {history.pages}</span>
              <button className="btn btn-sm btn-outline-success" disabled={!history.has_next} onClick={() => setPage(page + 1)}>Next</button>
            </div>
          )}
        </>
      ) : (
        <p className="text-muted">No earnings history yet. Complete your first sale to see earnings here.</p>
      )}

      {/* Payout History */}
      {payouts.length > 0 && (
        <>
          <h4 className="mt-4 mb-3">Payout History</h4>
          <table className="table">
            <thead><tr><th>ID</th><th>Amount</th><th>Period</th><th>Status</th><th>Date</th></tr></thead>
            <tbody>
              {payouts.map(p => (
                <tr key={p.id}>
                  <td>#{p.id}</td>
                  <td className="fw-bold">${p.amount.toFixed(2)}</td>
                  <td>{p.period_start && p.period_end ? `${p.period_start} - ${p.period_end}` : '-'}</td>
                  <td><span className={`badge ${p.status === 'completed' ? 'bg-success' : p.status === 'pending' ? 'bg-warning text-dark' : 'bg-secondary'}`}>{p.status}</span></td>
                  <td>{p.created_at ? new Date(p.created_at).toLocaleDateString() : '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </>
  );
}
