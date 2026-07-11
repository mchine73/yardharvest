import { useState, useEffect } from 'react';
import { adminAPI } from '../../api';
import { useAuth } from '../../AuthContext';
import { useSubmit } from '../../hooks/useSubmit';
import AdminHeader from '../../components/AdminHeader';

export default function AdminPricing() {
  const { user } = useAuth();
  const [config, setConfig] = useState(null);
  const [stats, setStats] = useState([]);
  const [loadError, setLoadError] = useState(false);
  const { pending: saving, run: runSave } = useSubmit();

  const load = () => {
    setLoadError(false);
    adminAPI.getPricing().then(res => {
      setConfig(res.data.config);
      setStats(res.data.category_stats);
    }).catch(() => setLoadError(true));
  };
  useEffect(() => { if (user?.is_admin) load(); }, [user]);

  if (!user?.is_admin) return <div className="alert alert-danger">Access Denied</div>;
  if (loadError) return (
    <div className="alert alert-warning d-flex align-items-center justify-content-between">
      <span><i className="bi bi-wifi-off me-2"></i>Couldn’t load pricing.</span>
      <button className="btn btn-sm btn-outline-secondary" onClick={load}>Try again</button>
    </div>
  );
  if (!config) return <div className="text-center py-5"><div className="spinner-border text-success"></div></div>;

  // This saves LIVE subscription pricing — a silent failure previously let
  // the operator walk away believing new prices were in effect.
  const save = (e) => {
    e.preventDefault();
    runSave(() => adminAPI.updatePricing(config),
            { success: 'Pricing configuration saved!' });
  };

  const update = (field, value) => setConfig({ ...config, [field]: value });

  return (
    <>
      <AdminHeader title="Pricing & Fees" icon="bi-cash-stack" />
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

          {/* ── Garden Pro Subscription ── */}
          <div className="card mb-3">
            <div className="card-body">
              <div className="form-check form-switch mb-2">
                <input className="form-check-input" type="checkbox" id="gardenProToggle" checked={config.garden_pro_enabled || false} onChange={e => update('garden_pro_enabled', e.target.checked)} />
                <label className="form-check-label fw-bold" htmlFor="gardenProToggle"><i className="bi bi-tree me-1"></i>Garden Pro Subscriptions</label>
                {!config.garden_pro_enabled && <span className="badge bg-secondary ms-2">OFF</span>}
              </div>
              <p className="text-muted small mb-2">
                When enabled, community garden organizers can subscribe to Garden Pro for advanced features
                (financial management, volunteer tracking, photo wall, messaging, email branding).
                New gardens receive a free trial before payment is required.
              </p>
              <div className="row g-3">
                <div className="col-md-3">
                  <label className="form-label">Free Trial Length</label>
                  <div className="input-group">
                    <input type="number" min={1} max={90} className="form-control"
                      value={config.garden_pro_trial_days || 14}
                      onChange={e => update('garden_pro_trial_days', parseInt(e.target.value) || 14)}
                      disabled={!config.garden_pro_enabled} />
                    <span className="input-group-text">days</span>
                  </div>
                </div>
                <div className="col-md-3">
                  <label className="form-label">Monthly Price</label>
                  <div className="input-group">
                    <span className="input-group-text">$</span>
                    <input type="number" step={0.01} min={0} className="form-control"
                      value={((config.garden_pro_monthly_cents || 1500) / 100).toFixed(2)}
                      onChange={e => update('garden_pro_monthly_cents', Math.round(parseFloat(e.target.value || 0) * 100))}
                      disabled={!config.garden_pro_enabled} />
                    <span className="input-group-text">/mo</span>
                  </div>
                </div>
                <div className="col-md-3">
                  <label className="form-label">Annual Price</label>
                  <div className="input-group">
                    <span className="input-group-text">$</span>
                    <input type="number" step={0.01} min={0} className="form-control"
                      value={((config.garden_pro_yearly_cents || 12500) / 100).toFixed(2)}
                      onChange={e => update('garden_pro_yearly_cents', Math.round(parseFloat(e.target.value || 0) * 100))}
                      disabled={!config.garden_pro_enabled} />
                    <span className="input-group-text">/yr</span>
                  </div>
                </div>
                <div className="col-md-3 d-flex align-items-end">
                  {config.garden_pro_enabled && (
                    <span className="text-success small">
                      <i className="bi bi-tag me-1"></i>
                      {Math.round(100 - ((config.garden_pro_yearly_cents || 12500) / ((config.garden_pro_monthly_cents || 1500) * 12)) * 100)}% annual discount
                    </span>
                  )}
                </div>
              </div>
              {config.garden_pro_enabled && (
                <div className="alert alert-info mt-3 mb-0 small">
                  <i className="bi bi-info-circle me-1"></i>
                  <strong>How it works:</strong> New gardens get a {config.garden_pro_trial_days || 14}-day free trial with all Pro features.
                  After the trial, organizers choose monthly (${((config.garden_pro_monthly_cents || 1500) / 100).toFixed(2)}/mo)
                  or annual (${((config.garden_pro_yearly_cents || 12500) / 100).toFixed(2)}/yr).
                  Pro features lock if the trial expires without subscribing.
                </div>
              )}
              <hr className="my-3" />
              <div className="row g-3 align-items-end">
                <div className="col-md-4">
                  <label className="form-label"><i className="bi bi-percent me-1"></i>Dues Platform Fee</label>
                  <div className="input-group">
                    <input type="number" step={0.1} min={0} max={100} className="form-control"
                      value={config.garden_dues_fee_percent ?? 0}
                      onChange={e => update('garden_dues_fee_percent', parseFloat(e.target.value) || 0)} />
                    <span className="input-group-text">%</span>
                  </div>
                </div>
                <div className="col-md-8">
                  <span className="text-muted small">
                    <i className="bi bi-info-circle me-1"></i>
                    Platform fee taken from each member dues payment (a Stripe application fee on the charge routed to the garden manager). 0% = the manager keeps 100% of dues.
                  </span>
                </div>
              </div>
              <hr className="my-3" />
              <div className="form-check form-switch mb-1">
                <input className="form-check-input" type="checkbox" id="duesRequirePayout"
                  checked={config.dues_require_payout_ready ?? true}
                  onChange={e => update('dues_require_payout_ready', e.target.checked)} />
                <label className="form-check-label fw-bold" htmlFor="duesRequirePayout">
                  <i className="bi bi-shield-check me-1"></i>Require payout setup before collecting dues
                </label>
              </div>
              <span className="text-muted small">
                <i className="bi bi-info-circle me-1"></i>
                {config.dues_require_payout_ready ?? true
                  ? 'ON (recommended): members can only pay dues once the garden manager has finished Stripe payout onboarding, so every payment is routed straight to the manager’s account.'
                  : 'OFF: if the manager hasn’t finished payout setup, dues are charged to the platform instead and must be reconciled to the manager manually.'}
              </span>
            </div>
          </div>

          <button type="submit" className="btn btn-success mt-3" disabled={saving}>
            {saving ? 'Saving…' : 'Save Configuration'}
          </button>
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
