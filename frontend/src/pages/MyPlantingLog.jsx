import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { plantingAPI } from '../api';
import { useAuth } from '../AuthContext';
import { useSiteConfig } from '../SiteConfigContext';

const CATEGORIES = [
  'Tomatoes','Peppers (Hot)','Peppers (Sweet)','Cucumbers','Squash (Summer)',
  'Squash (Winter)','Herbs','Leafy Greens','Root Vegetables','Beans','Corn',
  'Berries','Melons','Peas','Onions/Garlic','Brassicas','Other',
];

const STATUS_OPTIONS = ['planted', 'growing', 'harvesting', 'done'];

const STATUS_COLORS = {
  planted:    { bg: '#dbeafe', text: '#1d4ed8', label: 'Planted' },
  growing:    { bg: '#dcfce7', text: '#16a34a', label: 'Growing' },
  harvesting: { bg: '#fef3c7', text: '#d97706', label: 'Harvesting' },
  done:       { bg: '#f3f4f6', text: '#6b7280', label: 'Done' },
};

const styles = {
  page: {
    maxWidth: 900,
    margin: '0 auto',
    padding: '0 16px',
  },
  header: {
    textAlign: 'center',
    marginBottom: 28,
  },
  title: {
    fontSize: 30,
    fontWeight: 700,
    color: '#2d6a4f',
    marginBottom: 4,
  },
  subtitle: {
    color: '#666',
    fontSize: 15,
  },
  backLink: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    color: '#40916c',
    textDecoration: 'none',
    fontWeight: 600,
    fontSize: 14,
    marginBottom: 20,
  },
  formCard: {
    background: '#D8EDDF',
    borderRadius: 12,
    padding: 24,
    marginBottom: 28,
    border: '1px solid #74C69D',
  },
  formTitle: {
    fontWeight: 700,
    fontSize: 18,
    color: '#2d6a4f',
    marginBottom: 16,
  },
  formGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
    gap: 12,
    marginBottom: 12,
  },
  formGroup: {
    display: 'flex',
    flexDirection: 'column',
    gap: 4,
  },
  label: {
    fontSize: 12,
    fontWeight: 600,
    color: '#555',
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
  },
  input: {
    padding: '8px 12px',
    borderRadius: 6,
    border: '1px solid #ccc',
    fontSize: 14,
    outline: 'none',
  },
  select: {
    padding: '8px 12px',
    borderRadius: 6,
    border: '1px solid #ccc',
    fontSize: 14,
    outline: 'none',
    background: '#fff',
  },
  checkbox: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    fontSize: 14,
    color: '#333',
    marginTop: 8,
  },
  submitBtn: {
    display: 'inline-block',
    padding: '10px 24px',
    background: '#2d6a4f',
    color: '#fff',
    border: 'none',
    borderRadius: 8,
    fontWeight: 600,
    fontSize: 14,
    cursor: 'pointer',
    marginTop: 8,
  },
  harvestPreview: {
    background: '#fff',
    borderRadius: 8,
    padding: 12,
    marginTop: 12,
    border: '1px solid #74C69D',
    fontSize: 13,
    color: '#2d6a4f',
  },
  plantingCard: {
    background: '#fff',
    border: '1px solid #e5e7eb',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
  },
  plantingHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 10,
    flexWrap: 'wrap',
    gap: 8,
  },
  plantingTitle: {
    fontWeight: 700,
    fontSize: 16,
    color: '#2d6a4f',
  },
  plantingVariety: {
    fontSize: 13,
    color: '#888',
    fontStyle: 'italic',
  },
  statusBadge: (status) => ({
    display: 'inline-block',
    padding: '3px 10px',
    borderRadius: 12,
    fontSize: 12,
    fontWeight: 600,
    backgroundColor: STATUS_COLORS[status]?.bg || '#f3f4f6',
    color: STATUS_COLORS[status]?.text || '#333',
  }),
  plantingMeta: {
    fontSize: 13,
    color: '#666',
    lineHeight: 1.8,
  },
  statusButtons: {
    display: 'flex',
    gap: 6,
    flexWrap: 'wrap',
    marginTop: 10,
  },
  statusBtn: (isActive) => ({
    padding: '4px 10px',
    borderRadius: 6,
    border: isActive ? '2px solid #2d6a4f' : '1px solid #ddd',
    background: isActive ? '#D8EDDF' : '#fff',
    color: isActive ? '#2d6a4f' : '#888',
    fontSize: 12,
    fontWeight: 600,
    cursor: 'pointer',
  }),
  deleteBtn: {
    padding: '4px 10px',
    borderRadius: 6,
    border: '1px solid #fca5a5',
    background: '#fff',
    color: '#ef4444',
    fontSize: 12,
    fontWeight: 600,
    cursor: 'pointer',
    marginLeft: 'auto',
  },
  preorderToggle: {
    padding: '4px 10px',
    borderRadius: 6,
    fontSize: 12,
    fontWeight: 600,
    cursor: 'pointer',
    border: 'none',
  },
  emptyState: {
    textAlign: 'center',
    padding: 40,
    color: '#999',
  },
  filterRow: {
    display: 'flex',
    gap: 8,
    flexWrap: 'wrap',
    marginBottom: 16,
  },
  filterBtn: (active) => ({
    padding: '6px 14px',
    borderRadius: 20,
    border: active ? 'none' : '1px solid #ddd',
    background: active ? '#2d6a4f' : '#fff',
    color: active ? '#fff' : '#666',
    fontSize: 13,
    fontWeight: 600,
    cursor: 'pointer',
  }),
  loading: {
    textAlign: 'center',
    padding: 60,
    color: '#888',
  },
  loginPrompt: {
    textAlign: 'center',
    padding: 60,
  },
  error: {
    color: '#ef4444',
    fontSize: 14,
    marginBottom: 8,
  },
};


export default function MyPlantingLog() {
  const { user } = useAuth();
  const { marketplaceEnabled } = useSiteConfig();
  const navigate = useNavigate();
  const [plantings, setPlantings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('all');
  const [error, setError] = useState('');

  // Form state
  const [form, setForm] = useState({
    category: '',
    variety: '',
    planted_date: new Date().toISOString().split('T')[0],
    quantity_estimate: '',
    weight_lbs: '',
    sale_price: '',
    price_unit: 'lb',
    allow_preorder: false,
    auto_list_on_harvest: false,
    notes: '',
  });
  const [harvestPreview, setHarvestPreview] = useState(null);
  const [priceGuide, setPriceGuide] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!user) {
      setLoading(false);
      return;
    }
    loadPlantings();
  }, [user]);

  // Preview harvest dates when category or planted_date change
  useEffect(() => {
    if (form.category && form.planted_date) {
      plantingAPI.guideCategory(form.category)
        .then(res => {
          const guide = res.data;
          if (guide.days_to_harvest_min) {
            const planted = new Date(form.planted_date + 'T00:00:00');
            const hStart = new Date(planted);
            hStart.setDate(hStart.getDate() + guide.days_to_harvest_min);
            const hEnd = new Date(planted);
            hEnd.setDate(hEnd.getDate() + guide.days_to_harvest_max);
            setHarvestPreview({
              start: hStart.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
              end: hEnd.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
              daysMin: guide.days_to_harvest_min,
              daysMax: guide.days_to_harvest_max,
            });
          } else {
            setHarvestPreview(null);
          }
        })
        .catch(() => setHarvestPreview(null));
    } else {
      setHarvestPreview(null);
    }
    // Fetch price guide when category changes
    if (form.category) {
      plantingAPI.priceGuide(form.category)
        .then(res => setPriceGuide(res.data))
        .catch(() => setPriceGuide(null));
    } else {
      setPriceGuide(null);
    }
  }, [form.category, form.planted_date]);

  const loadPlantings = () => {
    setLoading(true);
    plantingAPI.myPlantings()
      .then(res => setPlantings(res.data))
      .catch(err => console.error('Failed to load plantings:', err))
      .finally(() => setLoading(false));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (!form.category || !form.planted_date) {
      setError('Category and planting date are required.');
      return;
    }
    setSubmitting(true);
    try {
      await plantingAPI.createPlanting(form);
      setForm({
        category: '',
        variety: '',
        planted_date: new Date().toISOString().split('T')[0],
        quantity_estimate: '',
        weight_lbs: '',
        sale_price: '',
        price_unit: 'lb',
        allow_preorder: false,
        auto_list_on_harvest: false,
        notes: '',
      });
      setPriceGuide(null);
      loadPlantings();
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to create planting.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleStatusChange = async (id, newStatus) => {
    try {
      await plantingAPI.updatePlanting(id, { status: newStatus });
      setPlantings(prev =>
        prev.map(p => p.id === id ? { ...p, status: newStatus } : p)
      );
    } catch (err) {
      console.error('Failed to update status:', err);
    }
  };

  const handleTogglePreorder = async (id, current) => {
    try {
      await plantingAPI.updatePlanting(id, { allow_preorder: !current });
      setPlantings(prev =>
        prev.map(p => p.id === id ? { ...p, allow_preorder: !current } : p)
      );
    } catch (err) {
      console.error('Failed to toggle preorder:', err);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Remove this planting from your log?')) return;
    try {
      await plantingAPI.deletePlanting(id);
      setPlantings(prev => prev.filter(p => p.id !== id));
    } catch (err) {
      console.error('Failed to delete planting:', err);
    }
  };

  const handleCreateListing = async (id) => {
    try {
      const res = await plantingAPI.createListingFromPlanting(id);
      setPlantings(prev =>
        prev.map(p => p.id === id ? { ...p, linked_listing_id: res.data.listing_id } : p)
      );
      navigate(`/listings/${res.data.listing_id}/edit`);
    } catch (err) {
      console.error('Failed to create listing:', err);
      alert(err.response?.data?.error || 'Failed to create listing');
    }
  };

  const handleToggleAutoList = async (id, current) => {
    try {
      await plantingAPI.updatePlanting(id, { auto_list_on_harvest: !current });
      setPlantings(prev =>
        prev.map(p => p.id === id ? { ...p, auto_list_on_harvest: !current } : p)
      );
    } catch (err) {
      console.error('Failed to toggle auto-list:', err);
    }
  };

  if (!user) {
    return (
      <div style={styles.page}>
        <div style={styles.loginPrompt}>
          <h2 style={{ color: '#2d6a4f' }}>Sign In Required</h2>
          <p style={{ color: '#666' }}>
            Log in to track your plantings and share harvest forecasts with the community.
          </p>
          <Link to="/login" style={{ ...styles.submitBtn, textDecoration: 'none' }}>
            Sign In
          </Link>
        </div>
      </div>
    );
  }

  const filtered = statusFilter === 'all'
    ? plantings
    : plantings.filter(p => p.status === statusFilter);

  return (
    <div style={styles.page}>
      <Link to="/planting-calendar" style={styles.backLink}>
        <i className="bi bi-arrow-left"></i> Back to Planting Calendar
      </Link>

      <div style={styles.header}>
        <h1 style={styles.title}>
          <i className="bi bi-journal-plus me-2"></i>
          My Planting Log
        </h1>
        <p style={styles.subtitle}>
          Track your plantings and share harvest estimates with the community
        </p>
      </div>

      {/* Add New Planting Form */}
      <div style={styles.formCard}>
        <div style={styles.formTitle}>
          <i className="bi bi-plus-circle me-2"></i>
          Log a New Planting
        </div>
        <form onSubmit={handleSubmit}>
          {error && <div style={styles.error}>{error}</div>}
          <div style={styles.formGrid}>
            <div style={styles.formGroup}>
              <label style={styles.label}>Category *</label>
              <select
                style={styles.select}
                value={form.category}
                onChange={e => setForm(f => ({ ...f, category: e.target.value }))}
              >
                <option value="">Select...</option>
                {CATEGORIES.map(c => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
            <div style={styles.formGroup}>
              <label style={styles.label}>Variety</label>
              <input
                style={styles.input}
                type="text"
                placeholder="e.g. Roma, Cherokee Purple"
                value={form.variety}
                onChange={e => setForm(f => ({ ...f, variety: e.target.value }))}
              />
            </div>
            <div style={styles.formGroup}>
              <label style={styles.label}>Date Planted *</label>
              <input
                style={styles.input}
                type="date"
                value={form.planted_date}
                onChange={e => setForm(f => ({ ...f, planted_date: e.target.value }))}
              />
            </div>
            <div style={styles.formGroup}>
              <label style={styles.label}>Quantity Estimate</label>
              <input
                style={styles.input}
                type="text"
                placeholder='e.g. "50 ears", "3 bushels"'
                value={form.quantity_estimate}
                onChange={e => setForm(f => ({ ...f, quantity_estimate: e.target.value }))}
              />
            </div>
          </div>
          <div style={styles.formGrid}>
            <div style={styles.formGroup}>
              <label style={styles.label}>Weight (lbs)</label>
              <input
                style={styles.input}
                type="number"
                step="0.1"
                min="0"
                placeholder="e.g. 20"
                value={form.weight_lbs}
                onChange={e => setForm(f => ({ ...f, weight_lbs: e.target.value }))}
              />
            </div>
            <div style={styles.formGroup}>
              <label style={styles.label}>Sale Price ($)</label>
              <input
                style={styles.input}
                type="number"
                step="0.01"
                min="0"
                placeholder={priceGuide ? priceGuide.avg_price.toFixed(2) : 'e.g. 3.50'}
                value={form.sale_price}
                onChange={e => setForm(f => ({ ...f, sale_price: e.target.value }))}
              />
            </div>
            <div style={styles.formGroup}>
              <label style={styles.label}>Price Unit</label>
              <select
                style={styles.select}
                value={form.price_unit}
                onChange={e => setForm(f => ({ ...f, price_unit: e.target.value }))}
              >
                <option value="lb">per lb</option>
                <option value="each">each</option>
                <option value="bunch">per bunch</option>
                <option value="pint">per pint</option>
                <option value="quart">per quart</option>
                <option value="dozen">per dozen</option>
              </select>
            </div>
          </div>
          {priceGuide && (
            <div style={{ ...styles.harvestPreview, borderColor: '#40916c', marginBottom: 12 }}>
              <i className="bi bi-tag me-1"></i>
              <strong>Suggested:</strong> ${priceGuide.low_price.toFixed(2)} – ${priceGuide.high_price.toFixed(2)} / {priceGuide.unit}
              <span style={{ color: '#888', marginLeft: 8, fontSize: 12 }}>
                ({priceGuide.sample_size > 0 ? `based on ${priceGuide.sample_size} recent sales` : 'community average'})
              </span>
            </div>
          )}
          <div style={styles.formGroup}>
            <label style={styles.label}>Notes</label>
            <input
              style={styles.input}
              type="text"
              placeholder="Any notes about this planting..."
              value={form.notes}
              onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
            />
          </div>
          {marketplaceEnabled && (
            <label style={styles.checkbox}>
              <input
                type="checkbox"
                checked={form.allow_preorder}
                onChange={e => setForm(f => ({ ...f, allow_preorder: e.target.checked }))}
              />
              Allow community members to pre-order this harvest
            </label>
          )}
          {marketplaceEnabled && (
            <label style={styles.checkbox}>
              <input
                type="checkbox"
                checked={form.auto_list_on_harvest || false}
                onChange={e => setForm(f => ({ ...f, auto_list_on_harvest: e.target.checked }))}
              />
              Auto-list on marketplace when harvest begins
              {form.sale_price && parseFloat(form.sale_price) > 0 && (
                <span style={{ color: '#16a34a', marginLeft: 8, fontSize: 12 }}>
                  <i className="bi bi-lightning-fill me-1"></i>Will auto-activate at ${parseFloat(form.sale_price).toFixed(2)}/{form.price_unit}
                </span>
              )}
            </label>
          )}
          {harvestPreview && (
            <div style={styles.harvestPreview}>
              <i className="bi bi-calendar-check me-1"></i>
              <strong>Estimated Harvest:</strong> {harvestPreview.start} - {harvestPreview.end}{' '}
              ({harvestPreview.daysMin}-{harvestPreview.daysMax} days from planting)
            </div>
          )}
          <button type="submit" style={styles.submitBtn} disabled={submitting}>
            {submitting ? 'Saving...' : 'Add Planting'}
          </button>
        </form>
      </div>

      {/* Plantings List */}
      {loading ? (
        <div style={styles.loading}>Loading your plantings...</div>
      ) : (
        <>
          <div style={styles.filterRow}>
            <button
              style={styles.filterBtn(statusFilter === 'all')}
              onClick={() => setStatusFilter('all')}
            >
              All ({plantings.length})
            </button>
            {STATUS_OPTIONS.map(s => {
              const count = plantings.filter(p => p.status === s).length;
              return (
                <button
                  key={s}
                  style={styles.filterBtn(statusFilter === s)}
                  onClick={() => setStatusFilter(s)}
                >
                  {STATUS_COLORS[s].label} ({count})
                </button>
              );
            })}
          </div>

          {filtered.length === 0 ? (
            <div style={styles.emptyState}>
              <i className="bi bi-journal" style={{ fontSize: 36, display: 'block', marginBottom: 8 }}></i>
              {plantings.length === 0
                ? 'No plantings logged yet. Add your first planting above!'
                : `No plantings with status "${statusFilter}".`}
            </div>
          ) : (
            filtered.map(p => (
              <div key={p.id} style={styles.plantingCard}>
                <div style={styles.plantingHeader}>
                  <div>
                    <span style={styles.plantingTitle}>{p.category}</span>
                    {p.variety && (
                      <span style={styles.plantingVariety}> - {p.variety}</span>
                    )}
                  </div>
                  <span style={styles.statusBadge(p.status)}>
                    {STATUS_COLORS[p.status]?.label || p.status}
                  </span>
                </div>
                <div style={styles.plantingMeta}>
                  <div>
                    <i className="bi bi-calendar me-1"></i>
                    Planted: {formatDate(p.planted_date)}
                  </div>
                  {p.estimated_harvest_start && (
                    <div>
                      <i className="bi bi-calendar-check me-1"></i>
                      Est. Harvest: {formatDate(p.estimated_harvest_start)}
                      {p.estimated_harvest_end && p.estimated_harvest_end !== p.estimated_harvest_start
                        ? ` - ${formatDate(p.estimated_harvest_end)}`
                        : ''}
                    </div>
                  )}
                  {(p.quantity_estimate || p.weight_lbs) && (
                    <div>
                      <i className="bi bi-box me-1"></i>
                      {p.weight_lbs ? `~${p.weight_lbs} lbs` : ''}
                      {p.weight_lbs && p.quantity_estimate ? ` (${p.quantity_estimate})` : p.quantity_estimate || ''}
                    </div>
                  )}
                  {p.sale_price > 0 && (
                    <div>
                      <i className="bi bi-tag me-1"></i>
                      <span style={{ color: '#16a34a', fontWeight: 600 }}>
                        ${p.sale_price.toFixed(2)}/{p.price_unit || 'lb'}
                      </span>
                    </div>
                  )}
                  {p.notes && (
                    <div>
                      <i className="bi bi-chat-left-text me-1"></i>
                      {p.notes}
                    </div>
                  )}
                </div>
                <div style={styles.statusButtons}>
                  {STATUS_OPTIONS.map(s => {
                    const tooltips = {
                      planted: 'Mark as planted — seeds are in the ground',
                      growing: 'Mark as growing — sprouts are establishing',
                      harvesting: 'Mark as harvesting — actively picking produce',
                      done: 'Mark as done — harvest complete',
                    };
                    return (
                      <button
                        key={s}
                        style={{ ...styles.statusBtn(p.status === s), transition: 'all 0.15s ease' }}
                        onClick={() => handleStatusChange(p.id, s)}
                        title={tooltips[s]}
                        onMouseEnter={e => { if (p.status !== s) e.currentTarget.style.opacity = '0.7'; }}
                        onMouseLeave={e => { e.currentTarget.style.opacity = '1'; }}
                      >
                        {STATUS_COLORS[s].label}
                      </button>
                    );
                  })}
                  {marketplaceEnabled && (
                    <button
                      style={{
                        ...styles.preorderToggle,
                        background: p.allow_preorder ? '#dcfce7' : '#f3f4f6',
                        color: p.allow_preorder ? '#16a34a' : '#888',
                        border: `1px solid ${p.allow_preorder ? '#86efac' : '#ddd'}`,
                      }}
                      onClick={() => handleTogglePreorder(p.id, p.allow_preorder)}
                      title={p.allow_preorder ? 'Visible in marketplace for pre-ordering — click to disable' : 'Make available for pre-order in the marketplace'}
                    >
                      <i className={`bi ${p.allow_preorder ? 'bi-bag-check-fill' : 'bi-bag'} me-1`}></i>
                      {p.allow_preorder ? 'Pre-order On' : 'Pre-order Off'}
                    </button>
                  )}
                  {marketplaceEnabled && (
                    <button
                      style={{
                        ...styles.preorderToggle,
                        background: p.auto_list_on_harvest ? '#dbeafe' : '#f3f4f6',
                        color: p.auto_list_on_harvest ? '#1d4ed8' : '#888',
                        border: `1px solid ${p.auto_list_on_harvest ? '#93c5fd' : '#ddd'}`,
                      }}
                      onClick={() => handleToggleAutoList(p.id, p.auto_list_on_harvest)}
                      title={p.auto_list_on_harvest ? 'Automatically creates a marketplace listing when you mark harvest — click to disable' : 'Auto-create marketplace listing when harvest begins'}
                    >
                      <i className={`bi ${p.auto_list_on_harvest ? 'bi-lightning-fill' : 'bi-lightning'} me-1`}></i>
                      {p.auto_list_on_harvest ? 'Auto-list On' : 'Auto-list Off'}
                    </button>
                  )}
                  {marketplaceEnabled && (p.status === 'harvesting' || p.status === 'done') && !p.linked_listing_id && (
                    <button
                      style={{
                        padding: '4px 10px',
                        borderRadius: 6,
                        border: '1px solid #86efac',
                        background: '#dcfce7',
                        color: '#16a34a',
                        fontSize: 12,
                        fontWeight: 600,
                        cursor: 'pointer',
                      }}
                      onClick={() => handleCreateListing(p.id)}
                    >
                      <i className="bi bi-shop me-1"></i>
                      List on Marketplace
                    </button>
                  )}
                  {marketplaceEnabled && p.linked_listing_id && (
                    <Link
                      to={`/listings/${p.linked_listing_id}`}
                      style={{
                        padding: '4px 10px',
                        borderRadius: 6,
                        border: '1px solid #93c5fd',
                        background: '#dbeafe',
                        color: '#1d4ed8',
                        fontSize: 12,
                        fontWeight: 600,
                        textDecoration: 'none',
                        display: 'inline-flex',
                        alignItems: 'center',
                      }}
                    >
                      <i className="bi bi-box-arrow-up-right me-1"></i>
                      View Listing
                    </Link>
                  )}
                  <button
                    style={styles.deleteBtn}
                    onClick={() => handleDelete(p.id)}
                  >
                    <i className="bi bi-trash me-1"></i>
                    Remove
                  </button>
                </div>
              </div>
            ))
          )}
        </>
      )}
    </div>
  );
}

function formatDate(isoStr) {
  if (!isoStr) return '';
  const d = new Date(isoStr + 'T00:00:00');
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}
