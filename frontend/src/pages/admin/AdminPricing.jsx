import { useState, useEffect } from 'react';
import { adminAPI } from '../../api';
import { useAuth } from '../../AuthContext';
import AdminHeader from '../../components/AdminHeader';

export default function AdminPricing() {
  const { user } = useAuth();
  const [config, setConfig] = useState(null);
  const [stats, setStats] = useState([]);
  const [msg, setMsg] = useState('');

  useEffect(() => {
    if (user?.is_admin) {
      adminAPI.getPricing().then(res => {
        setConfig(res.data.config);
        setStats(res.data.category_stats);
      });
    }
  }, [user]);

  if (!user?.is_admin) return <div className="alert alert-danger">Access Denied</div>;
  if (!config) return <div className="text-center py-5"><div className="spinner-border text-success"></div></div>;

  const save = async (e) => {
    e.preventDefault();
    await adminAPI.updatePricing(config);
    setMsg('Pricing configuration saved!');
    setTimeout(() => setMsg(''), 3000);
  };

  const update = (field, value) => setConfig({ ...config, [field]: value });

  return (
    <>
      <AdminHeader title="Pricing & Fees" icon="bi-cash-stack" />
      {msg && <div className="alert alert-success">{msg}</div>}
      <form onSubmit={save} className="card mb-4">
        <div className="card-body">
          <div className="row g-3">
            <div className="col-md-12">
              <div className="form-check form-switch">
                <input className="form-check-input" type="checkbox" checked={config.enabled} onChange={e => update('enabled', e.target.checked)} />
                <label className="form-check-label fw-bold">Enable Dynamic Pricing</label>
              </div>
            </div>
            {[
              { key: 'global_multiplier', label: 'Global Multiplier', step: 0.1 },
              { key: 'supply_weight', label: 'Supply Weight', step: 0.05 },
              { key: 'velocity_weight', label: 'Velocity Weight', step: 0.05 },
              { key: 'time_decay_weight', label: 'Time Decay Weight', step: 0.05 },
              { key: 'floor_pct', label: 'Price Floor %', step: 0.05 },
              { key: 'ceiling_pct', label: 'Price Ceiling %', step: 0.1 },
            ].map(f => (
              <div key={f.key} className="col-md-4">
                <label className="form-label">{f.label}</label>
                <input type="number" step={f.step} className="form-control" value={config[f.key]} onChange={e => update(f.key, parseFloat(e.target.value))} />
              </div>
            ))}
          </div>

          <hr />
          <h5 className="mt-3"><i className="bi bi-bank me-2"></i>Platform Economics</h5>

          {/* ── Commission ── */}
          <div className="card mb-3">
            <div className="card-body">
              <div className="form-check form-switch mb-2">
                <input className="form-check-input" type="checkbox" id="commissionToggle" checked={config.commission_enabled} onChange={e => update('commission_enabled', e.target.checked)} />
                <label className="form-check-label fw-bold" htmlFor="commissionToggle">Platform Commission</label>
                {!config.commission_enabled && <span className="badge bg-secondary ms-2">OFF</span>}
              </div>
              <p className="text-muted small mb-2">When enabled, the platform takes a percentage of each order's subtotal. Seller receives subtotal minus commission.</p>
              <div className="row g-3">
                <div className="col-md-4">
                  <label className="form-label">Commission Rate</label>
                  <div className="input-group">
                    <input type="number" step={0.01} min={0} max={1} className="form-control" value={config.platform_commission_pct} onChange={e => update('platform_commission_pct', parseFloat(e.target.value) || 0)} disabled={!config.commission_enabled} />
                    <span className="input-group-text">{((config.platform_commission_pct || 0) * 100).toFixed(0)}%</span>
                  </div>
                  <small className="text-muted">e.g. 0.08 = 8%</small>
                </div>
              </div>
            </div>
          </div>

          {/* ── Delivery Fees ── */}
          <div className="card mb-3">
            <div className="card-body">
              <div className="form-check form-switch mb-2">
                <input className="form-check-input" type="checkbox" id="deliveryToggle" checked={config.delivery_fees_enabled} onChange={e => update('delivery_fees_enabled', e.target.checked)} />
                <label className="form-check-label fw-bold" htmlFor="deliveryToggle">Delivery Fees</label>
                {!config.delivery_fees_enabled && <span className="badge bg-secondary ms-2">OFF</span>}
              </div>
              <p className="text-muted small mb-2">When enabled, buyers who select delivery are charged a fee per seller order. Fee goes to the platform.</p>
              <div className="row g-3">
                <div className="col-md-4">
                  <label className="form-label">Flat Delivery Fee</label>
                  <div className="input-group">
                    <span className="input-group-text">$</span>
                    <input type="number" step={0.01} min={0} className="form-control" value={config.delivery_fee_flat} onChange={e => update('delivery_fee_flat', parseFloat(e.target.value) || 0)} disabled={!config.delivery_fees_enabled} />
                  </div>
                  <small className="text-muted">Base fee per delivery order</small>
                </div>
              </div>

              {/* Sub-feature: Per-Mile Surcharge */}
              <div className="mt-3 ms-4 border-start ps-3">
                <div className="form-check form-switch mb-2">
                  <input className="form-check-input" type="checkbox" id="perMileToggle" checked={config.per_mile_enabled} onChange={e => update('per_mile_enabled', e.target.checked)} disabled={!config.delivery_fees_enabled} />
                  <label className="form-check-label" htmlFor="perMileToggle">Per-Mile Surcharge</label>
                  {config.delivery_fees_enabled && !config.per_mile_enabled && <span className="badge bg-secondary ms-2">OFF</span>}
                </div>
                <div className="row g-3">
                  <div className="col-md-6">
                    <div className="input-group">
                      <span className="input-group-text">$</span>
                      <input type="number" step={0.01} min={0} className="form-control" value={config.delivery_fee_per_mile} onChange={e => update('delivery_fee_per_mile', parseFloat(e.target.value) || 0)} disabled={!config.delivery_fees_enabled || !config.per_mile_enabled} />
                      <span className="input-group-text">/ mile</span>
                    </div>
                    <small className="text-muted">Added to flat fee based on buyer-seller distance</small>
                  </div>
                </div>
              </div>

              {/* Sub-feature: Free Delivery Threshold */}
              <div className="mt-3 ms-4 border-start ps-3">
                <div className="form-check form-switch mb-2">
                  <input className="form-check-input" type="checkbox" id="freeDeliveryToggle" checked={config.free_delivery_enabled} onChange={e => update('free_delivery_enabled', e.target.checked)} disabled={!config.delivery_fees_enabled} />
                  <label className="form-check-label" htmlFor="freeDeliveryToggle">Free Delivery Threshold</label>
                  {config.delivery_fees_enabled && !config.free_delivery_enabled && <span className="badge bg-secondary ms-2">OFF</span>}
                </div>
                <div className="row g-3">
                  <div className="col-md-6">
                    <div className="input-group">
                      <span className="input-group-text">$</span>
                      <input type="number" step={0.01} min={0} className="form-control" value={config.delivery_fee_free_threshold} onChange={e => update('delivery_fee_free_threshold', parseFloat(e.target.value) || 0)} disabled={!config.delivery_fees_enabled || !config.free_delivery_enabled} />
                    </div>
                    <small className="text-muted">Orders at or above this subtotal get free delivery</small>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* ── DoorDash Delivery ── */}
          <div className="card mb-3">
            <div className="card-body">
              <div className="form-check form-switch mb-2">
                <input className="form-check-input" type="checkbox" id="doordashToggle" checked={config.doordash_enabled || false} onChange={e => update('doordash_enabled', e.target.checked)} />
                <label className="form-check-label fw-bold" htmlFor="doordashToggle"><i className="bi bi-truck me-1"></i>DoorDash Drive Delivery</label>
                {!config.doordash_enabled && <span className="badge bg-secondary ms-2">OFF</span>}
              </div>
              <p className="text-muted small mb-2">
                When enabled, delivery orders are fulfilled through DoorDash Drive. The platform can subsidize a percentage of the delivery fee to keep costs low for buyers.
                Requires <code>DOORDASH_DEVELOPER_ID</code>, <code>DOORDASH_KEY_ID</code>, and <code>DOORDASH_SIGNING_SECRET</code> environment variables.
              </p>
              <div className="row g-3">
                <div className="col-md-4">
                  <label className="form-label">Platform Delivery Subsidy</label>
                  <div className="input-group">
                    <input type="number" step={0.01} min={0} max={1} className="form-control"
                      value={config.doordash_subsidy_pct || 0}
                      onChange={e => update('doordash_subsidy_pct', parseFloat(e.target.value) || 0)}
                      disabled={!config.doordash_enabled} />
                    <span className="input-group-text">{((config.doordash_subsidy_pct || 0) * 100).toFixed(0)}%</span>
                  </div>
                  <small className="text-muted">Percentage of delivery fee the platform absorbs (e.g. 0.50 = 50%)</small>
                </div>
                <div className="col-md-4">
                  <label className="form-label">Max Subsidy per Order</label>
                  <div className="input-group">
                    <span className="input-group-text">$</span>
                    <input type="number" step={0.50} min={0} className="form-control"
                      value={config.doordash_max_subsidy || 5.0}
                      onChange={e => update('doordash_max_subsidy', parseFloat(e.target.value) || 0)}
                      disabled={!config.doordash_enabled} />
                  </div>
                  <small className="text-muted">Maximum dollar amount the platform subsidizes per delivery</small>
                </div>
              </div>
              {config.doordash_enabled && (
                <div className="alert alert-info mt-3 mb-0 small">
                  <i className="bi bi-info-circle me-1"></i>
                  <strong>How it works:</strong> When a buyer chooses delivery, DoorDash provides the actual delivery quote.
                  The platform absorbs up to {((config.doordash_subsidy_pct || 0) * 100).toFixed(0)}% of the fee (max ${(config.doordash_max_subsidy || 5).toFixed(2)}).
                  The buyer pays the remainder. Without DoorDash credentials configured, the system falls back to mock quotes in dev mode.
                </div>
              )}
            </div>
          </div>

          <button type="submit" className="btn btn-success mt-3">Save Configuration</button>
        </div>
      </form>

      <h4>Category Stats</h4>
      <table className="table">
        <thead><tr><th>Category</th><th>Count</th><th>Avg Price</th><th>Avg Base</th><th>Min</th><th>Max</th></tr></thead>
        <tbody>{stats.map(s => (
          <tr key={s.vegetable_type}>
            <td>{s.label}</td><td>{s.count}</td>
            <td>${s.avg_price.toFixed(2)}</td><td>${s.avg_base_price.toFixed(2)}</td>
            <td>${s.min_price.toFixed(2)}</td><td>${s.max_price.toFixed(2)}</td>
          </tr>
        ))}</tbody>
      </table>
    </>
  );
}
