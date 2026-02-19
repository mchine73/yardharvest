import { useState, useEffect } from 'react';
import { adminAPI } from '../../api';
import { useAuth } from '../../AuthContext';

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
      <h1 className="mb-4"><i className="bi bi-graph-up me-2"></i>Dynamic Pricing</h1>
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
