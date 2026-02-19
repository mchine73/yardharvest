import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { plantingAPI } from '../api';
import { useAuth } from '../AuthContext';

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
    background: '#d8f3dc',
    borderRadius: 12,
    padding: 24,
    marginBottom: 28,
    border: '1px solid #95d5b2',
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
    border: '1px solid #95d5b2',
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
    background: isActive ? '#d8f3dc' : '#fff',
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
    allow_preorder: false,
    notes: '',
  });
  const [harvestPreview, setHarvestPreview] = useState(null);
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
        allow_preorder: false,
        notes: '',
      });
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
                placeholder='e.g. "20 lbs", "50 ears"'
                value={form.quantity_estimate}
                onChange={e => setForm(f => ({ ...f, quantity_estimate: e.target.value }))}
              />
            </div>
          </div>
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
          <label style={styles.checkbox}>
            <input
              type="checkbox"
              checked={form.allow_preorder}
              onChange={e => setForm(f => ({ ...f, allow_preorder: e.target.checked }))}
            />
            Allow community members to pre-order this harvest
          </label>
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
                  {p.quantity_estimate && (
                    <div>
                      <i className="bi bi-box me-1"></i>
                      Quantity: {p.quantity_estimate}
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
                  {STATUS_OPTIONS.map(s => (
                    <button
                      key={s}
                      style={styles.statusBtn(p.status === s)}
                      onClick={() => handleStatusChange(p.id, s)}
                    >
                      {STATUS_COLORS[s].label}
                    </button>
                  ))}
                  <button
                    style={{
                      ...styles.preorderToggle,
                      background: p.allow_preorder ? '#dcfce7' : '#f3f4f6',
                      color: p.allow_preorder ? '#16a34a' : '#888',
                      border: `1px solid ${p.allow_preorder ? '#86efac' : '#ddd'}`,
                    }}
                    onClick={() => handleTogglePreorder(p.id, p.allow_preorder)}
                    title={p.allow_preorder ? 'Pre-orders enabled' : 'Enable pre-orders'}
                  >
                    <i className={`bi ${p.allow_preorder ? 'bi-bag-check-fill' : 'bi-bag'} me-1`}></i>
                    {p.allow_preorder ? 'Pre-order On' : 'Pre-order Off'}
                  </button>
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
