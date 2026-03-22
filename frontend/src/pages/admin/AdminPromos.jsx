import { useState, useEffect } from 'react';
import { adminAPI } from '../../api';
import { useAuth } from '../../AuthContext';

export default function AdminPromos() {
  const { user } = useAuth();
  const [promos, setPromos] = useState([]);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ code: '', description: '', discount_type: 'percentage', discount_value: '', scope: 'both', max_uses: '', expires_at: '' });
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');
  const [expandedPromo, setExpandedPromo] = useState(null);
  const [usages, setUsages] = useState([]);

  if (!user?.is_admin) return <div className="alert alert-danger">Access denied</div>;

  const load = () => {
    setLoading(true);
    adminAPI.promos({ page }).then(res => {
      setPromos(res.data.promos);
      setPages(res.data.pages);
      setLoading(false);
    }).catch(() => setLoading(false));
  };

  useEffect(() => { load(); }, [page]);

  const handleCreate = async (e) => {
    e.preventDefault();
    setCreating(true);
    setError('');
    try {
      const payload = {
        ...form,
        discount_value: parseFloat(form.discount_value),
        max_uses: form.max_uses ? parseInt(form.max_uses) : null,
        expires_at: form.expires_at || null,
      };
      await adminAPI.createPromo(payload);
      setShowCreate(false);
      setForm({ code: '', description: '', discount_type: 'percentage', discount_value: '', scope: 'both', max_uses: '', expires_at: '' });
      load();
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to create promo code');
    }
    setCreating(false);
  };

  const toggleActive = async (promo) => {
    if (promo.is_active) {
      await adminAPI.deactivatePromo(promo.id);
    } else {
      await adminAPI.updatePromo(promo.id, { is_active: true });
    }
    load();
  };

  const viewUsages = (promoId) => {
    if (expandedPromo === promoId) { setExpandedPromo(null); return; }
    setExpandedPromo(promoId);
    adminAPI.promoDetail(promoId).then(res => setUsages(res.data.usages || []));
  };

  const scopeBadge = { marketplace: 'bg-primary', garden_pro: 'bg-info text-dark', both: 'bg-secondary' };

  return (
    <>
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h1><i className="bi bi-ticket-perforated me-2"></i>Promo Codes</h1>
        <button className="btn btn-success" onClick={() => setShowCreate(!showCreate)}>
          <i className="bi bi-plus-circle me-1"></i>Create Code
        </button>
      </div>

      {showCreate && (
        <div className="card mb-4 border-success">
          <div className="card-header bg-success text-white">New Promo Code</div>
          <div className="card-body">
            {error && <div className="alert alert-danger py-2">{error}</div>}
            <form onSubmit={handleCreate}>
              <div className="row g-3">
                <div className="col-md-3">
                  <label className="form-label">Code</label>
                  <input className="form-control text-uppercase" value={form.code} onChange={e => setForm({ ...form, code: e.target.value })} placeholder="SPRING25" required />
                </div>
                <div className="col-md-5">
                  <label className="form-label">Description</label>
                  <input className="form-control" value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} placeholder="Spring season discount" />
                </div>
                <div className="col-md-2">
                  <label className="form-label">Type</label>
                  <select className="form-select" value={form.discount_type} onChange={e => setForm({ ...form, discount_type: e.target.value })}>
                    <option value="percentage">Percentage</option>
                    <option value="fixed">Fixed ($)</option>
                  </select>
                </div>
                <div className="col-md-2">
                  <label className="form-label">Value</label>
                  <div className="input-group">
                    {form.discount_type === 'fixed' && <span className="input-group-text">$</span>}
                    <input type="number" className="form-control" value={form.discount_value} onChange={e => setForm({ ...form, discount_value: e.target.value })} placeholder="25" required min="0.01" step="0.01" />
                    {form.discount_type === 'percentage' && <span className="input-group-text">%</span>}
                  </div>
                </div>
                <div className="col-md-3">
                  <label className="form-label">Scope</label>
                  <select className="form-select" value={form.scope} onChange={e => setForm({ ...form, scope: e.target.value })}>
                    <option value="both">Both</option>
                    <option value="marketplace">Marketplace</option>
                    <option value="garden_pro">Garden Pro</option>
                  </select>
                </div>
                <div className="col-md-3">
                  <label className="form-label">Max Uses</label>
                  <input type="number" className="form-control" value={form.max_uses} onChange={e => setForm({ ...form, max_uses: e.target.value })} placeholder="Unlimited" min="1" />
                </div>
                <div className="col-md-3">
                  <label className="form-label">Expires</label>
                  <input type="date" className="form-control" value={form.expires_at} onChange={e => setForm({ ...form, expires_at: e.target.value })} />
                </div>
                <div className="col-md-3 d-flex align-items-end">
                  <button type="submit" className="btn btn-success w-100" disabled={creating}>
                    {creating ? <span className="spinner-border spinner-border-sm"></span> : 'Create'}
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      {loading ? (
        <div className="text-center py-5"><div className="spinner-border text-success"></div></div>
      ) : promos.length === 0 ? (
        <div className="text-center py-5 text-muted">No promo codes yet</div>
      ) : (
        <div className="table-responsive">
          <table className="table table-hover align-middle">
            <thead className="table-light">
              <tr><th>Code</th><th>Type</th><th>Discount</th><th>Scope</th><th>Uses</th><th>Expires</th><th>Status</th><th>Actions</th></tr>
            </thead>
            <tbody>
              {promos.map(p => (
                <>
                  <tr key={p.id}>
                    <td><code className="fs-6">{p.code}</code>{p.description && <><br /><small className="text-muted">{p.description}</small></>}</td>
                    <td>{p.discount_type === 'percentage' ? '%' : '$'}</td>
                    <td className="fw-bold text-success">{p.discount_type === 'percentage' ? `${p.discount_value}%` : `$${p.discount_value.toFixed(2)}`}</td>
                    <td><span className={`badge ${scopeBadge[p.scope]}`}>{p.scope}</span></td>
                    <td>{p.current_uses}{p.max_uses ? ` / ${p.max_uses}` : ''}</td>
                    <td><small>{p.expires_at ? new Date(p.expires_at).toLocaleDateString() : 'Never'}</small></td>
                    <td><span className={`badge ${p.is_active ? 'bg-success' : 'bg-danger'}`}>{p.is_active ? 'Active' : 'Inactive'}</span></td>
                    <td>
                      <div className="btn-group btn-group-sm">
                        <button className="btn btn-outline-primary" onClick={() => viewUsages(p.id)}>
                          <i className="bi bi-eye me-1"></i>Usage
                        </button>
                        <button className={`btn ${p.is_active ? 'btn-outline-danger' : 'btn-outline-success'}`} onClick={() => toggleActive(p)}>
                          {p.is_active ? 'Deactivate' : 'Activate'}
                        </button>
                      </div>
                    </td>
                  </tr>
                  {expandedPromo === p.id && (
                    <tr key={`${p.id}-usage`}>
                      <td colSpan="8" className="bg-light">
                        {usages.length === 0 ? (
                          <p className="text-muted text-center py-2 mb-0">No usage yet</p>
                        ) : (
                          <table className="table table-sm mb-0">
                            <thead><tr><th>User</th><th>Discount</th><th>Reference</th><th>Date</th></tr></thead>
                            <tbody>
                              {usages.map(u => (
                                <tr key={u.id}>
                                  <td>{u.user}</td>
                                  <td className="text-success">${u.discount_applied.toFixed(2)}</td>
                                  <td>{u.order_id ? `Order #${u.order_id}` : u.garden_subscription_id ? `Sub #${u.garden_subscription_id}` : '—'}</td>
                                  <td><small>{u.used_at ? new Date(u.used_at).toLocaleDateString() : '—'}</small></td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        )}
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {pages > 1 && (
        <nav><ul className="pagination justify-content-center">
          {Array.from({ length: pages }, (_, i) => (
            <li key={i} className={`page-item ${page === i + 1 ? 'active' : ''}`}>
              <button className="page-link" onClick={() => setPage(i + 1)}>{i + 1}</button>
            </li>
          ))}
        </ul></nav>
      )}
    </>
  );
}
