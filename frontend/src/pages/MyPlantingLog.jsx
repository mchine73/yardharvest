import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useTranslation, Trans } from 'react-i18next';
import { plantingAPI } from '../api';
import { useAuth } from '../AuthContext';
import { useSiteConfig } from '../SiteConfigContext';
import { toast, confirmDialog } from '../components/dialog/dialogService';
import { formatDate as formatLocaleDate, DAY_MONTH, DAY_MONTH_YEAR } from '../i18n/dates';
import { PLANTING_CATEGORIES as CATEGORIES, cropLabel } from '../data/plantingCrops';

const STATUS_OPTIONS = ['planted', 'growing', 'harvesting', 'done'];

// Keys, not text: module scope runs before any t() exists.
const STATUS_COLORS = {
  planted:    { bg: '#dbeafe', text: '#1d4ed8', labelKey: 'plantingLog.statusPlanted' },
  growing:    { bg: '#dcfce7', text: '#16a34a', labelKey: 'plantingLog.statusGrowing' },
  harvesting: { bg: '#fef3c7', text: '#d97706', labelKey: 'plantingLog.statusHarvesting' },
  done:       { bg: '#f3f4f6', text: '#6b7280', labelKey: 'plantingLog.statusDone' },
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
    color: 'var(--brand-secondary)',
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
    color: 'var(--brand-secondary)',
    textDecoration: 'none',
    fontWeight: 600,
    fontSize: 14,
    marginBottom: 20,
  },
  formCard: {
    background: 'var(--brand-pale)',
    borderRadius: 12,
    padding: 24,
    marginBottom: 28,
    border: '1px solid var(--brand-light-green)',
  },
  formTitle: {
    fontWeight: 700,
    fontSize: 18,
    color: 'var(--brand-secondary)',
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
    background: 'var(--brand-secondary)',
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
    border: '1px solid var(--brand-light-green)',
    fontSize: 13,
    color: 'var(--brand-secondary)',
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
    color: 'var(--brand-secondary)',
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
    border: isActive ? '2px solid var(--brand-secondary)' : '1px solid #ddd',
    background: isActive ? 'var(--brand-pale)' : '#fff',
    color: isActive ? 'var(--brand-secondary)' : '#888',
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
    background: active ? 'var(--brand-secondary)' : '#fff',
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
  const { t } = useTranslation();
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
              start: formatLocaleDate(hStart, DAY_MONTH),
              end: formatLocaleDate(hEnd, DAY_MONTH),
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
      setError(t('plantingLog.errRequired'));
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
      setError(err.response?.data?.error || t('plantingLog.errCreate'));
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
    if (!(await confirmDialog(t('plantingLog.confirmRemove'), { danger: true, title: t('plantingLog.confirmRemoveTitle'), confirmText: t('dash.remove') }))) return;
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
      toast(err.response?.data?.error || t('plantingLog.errCreateListing'), { type: 'error' });
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

  // The unit a price is quoted in ("lb", "each", ...) is a stored slug. "lb"
  // has no key on purpose: the abbreviation is the same in both languages,
  // so it falls through to the slug itself.
  const unitLabel = (unit) => t(`plantingLog.unit_${unit}`, unit);
  const statusLabel = (status) =>
    (STATUS_COLORS[status] ? t(STATUS_COLORS[status].labelKey) : status);

  if (!user) {
    return (
      <div style={styles.page}>
        <div style={styles.loginPrompt}>
          <h2 style={{ color: 'var(--brand-secondary)' }}>{t('plantingLog.signInTitle')}</h2>
          <p style={{ color: '#666' }}>
            {t('plantingLog.signInBody')}
          </p>
          <Link to="/login" style={{ ...styles.submitBtn, textDecoration: 'none' }}>
            {t('common.signIn')}
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
        <i className="bi bi-arrow-left"></i> {t('plantingCalendar.backToCalendar')}
      </Link>

      <div style={styles.header}>
        <h1 style={styles.title}>
          <i className="bi bi-journal-plus me-2"></i>
          {t('garden.myPlantingLog')}
        </h1>
        <p style={styles.subtitle}>
          {t('plantingLog.subtitle')}
        </p>
      </div>

      {/* Add New Planting Form */}
      <div style={styles.formCard}>
        <div style={styles.formTitle}>
          <i className="bi bi-plus-circle me-2"></i>
          {t('plantingLog.formTitle')}
        </div>
        <form onSubmit={handleSubmit}>
          {error && <div style={styles.error}>{error}</div>}
          <div style={styles.formGrid}>
            <div style={styles.formGroup}>
              <label style={styles.label}>{t('plantingLog.categoryRequired')}</label>
              <select
                style={styles.select}
                value={form.category}
                onChange={e => setForm(f => ({ ...f, category: e.target.value }))}
              >
                <option value="">{t('garden.select')}</option>
                {CATEGORIES.map(c => (
                  <option key={c} value={c}>{cropLabel(t, c)}</option>
                ))}
              </select>
            </div>
            <div style={styles.formGroup}>
              <label style={styles.label}>{t('garden.variety')}</label>
              <input
                style={styles.input}
                type="text"
                placeholder={t('plantingLog.varietyPlaceholder')}
                value={form.variety}
                onChange={e => setForm(f => ({ ...f, variety: e.target.value }))}
              />
            </div>
            <div style={styles.formGroup}>
              <label style={styles.label}>{t('plantingLog.datePlantedRequired')}</label>
              <input
                style={styles.input}
                type="date"
                value={form.planted_date}
                onChange={e => setForm(f => ({ ...f, planted_date: e.target.value }))}
              />
            </div>
            <div style={styles.formGroup}>
              <label style={styles.label}>{t('plantingLog.quantityEstimate')}</label>
              <input
                style={styles.input}
                type="text"
                placeholder={t('plantingLog.quantityPlaceholder')}
                value={form.quantity_estimate}
                onChange={e => setForm(f => ({ ...f, quantity_estimate: e.target.value }))}
              />
            </div>
          </div>
          <div style={styles.formGrid}>
            <div style={styles.formGroup}>
              <label style={styles.label}>{t('plantingLog.weight')}</label>
              <input
                style={styles.input}
                type="number"
                step="0.1"
                min="0"
                placeholder={t('plantingLog.weightPlaceholder')}
                value={form.weight_lbs}
                onChange={e => setForm(f => ({ ...f, weight_lbs: e.target.value }))}
              />
            </div>
            <div style={styles.formGroup}>
              <label style={styles.label}>{t('plantingLog.salePrice')}</label>
              <input
                style={styles.input}
                type="number"
                step="0.01"
                min="0"
                placeholder={priceGuide ? priceGuide.avg_price.toFixed(2) : t('plantingLog.pricePlaceholder')}
                value={form.sale_price}
                onChange={e => setForm(f => ({ ...f, sale_price: e.target.value }))}
              />
            </div>
            <div style={styles.formGroup}>
              <label style={styles.label}>{t('plantingLog.priceUnit')}</label>
              <select
                style={styles.select}
                value={form.price_unit}
                onChange={e => setForm(f => ({ ...f, price_unit: e.target.value }))}
              >
                <option value="lb">{t('plantingLog.perLb')}</option>
                <option value="each">{t('plantingLog.perEach')}</option>
                <option value="bunch">{t('plantingLog.perBunch')}</option>
                <option value="pint">{t('plantingLog.perPint')}</option>
                <option value="quart">{t('plantingLog.perQuart')}</option>
                <option value="dozen">{t('plantingLog.perDozen')}</option>
              </select>
            </div>
          </div>
          {priceGuide && (
            <div style={{ ...styles.harvestPreview, borderColor: 'var(--brand-accent)', marginBottom: 12 }}>
              <i className="bi bi-tag me-1"></i>
              <Trans
                i18nKey="plantingLog.suggested"
                values={{ low: priceGuide.low_price.toFixed(2), high: priceGuide.high_price.toFixed(2), unit: unitLabel(priceGuide.unit) }}
                components={{ b: <strong /> }}
              />
              <span style={{ color: '#888', marginLeft: 8, fontSize: 12 }}>
                ({priceGuide.sample_size > 0 ? t('plantingLog.basedOnSales', { count: priceGuide.sample_size }) : t('plantingLog.communityAverage')})
              </span>
            </div>
          )}
          <div style={styles.formGroup}>
            <label style={styles.label}>{t('dash.notes')}</label>
            <input
              style={styles.input}
              type="text"
              placeholder={t('plantingLog.notesPlaceholder')}
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
              {t('plantingLog.allowPreorder')}
            </label>
          )}
          {marketplaceEnabled && (
            <label style={styles.checkbox}>
              <input
                type="checkbox"
                checked={form.auto_list_on_harvest || false}
                onChange={e => setForm(f => ({ ...f, auto_list_on_harvest: e.target.checked }))}
              />
              {t('plantingLog.autoList')}
              {form.sale_price && parseFloat(form.sale_price) > 0 && (
                <span style={{ color: '#16a34a', marginLeft: 8, fontSize: 12 }}>
                  <i className="bi bi-lightning-fill me-1"></i>{t('plantingLog.willAutoActivate', { price: parseFloat(form.sale_price).toFixed(2), unit: unitLabel(form.price_unit) })}
                </span>
              )}
            </label>
          )}
          {harvestPreview && (
            <div style={styles.harvestPreview}>
              <i className="bi bi-calendar-check me-1"></i>
              <Trans
                i18nKey="plantingLog.estimatedHarvest"
                values={{ start: harvestPreview.start, end: harvestPreview.end, min: harvestPreview.daysMin, max: harvestPreview.daysMax }}
                components={{ b: <strong /> }}
              />
            </div>
          )}
          <button type="submit" style={styles.submitBtn} disabled={submitting}>
            {submitting ? t('dash.savingEllipsis') : t('plantingLog.addPlanting')}
          </button>
        </form>
      </div>

      {/* Plantings List */}
      {loading ? (
        <div style={styles.loading}>{t('plantingLog.loading')}</div>
      ) : (
        <>
          <div style={styles.filterRow}>
            <button
              style={styles.filterBtn(statusFilter === 'all')}
              onClick={() => setStatusFilter('all')}
            >
              {t('garden.filterAll')} ({plantings.length})
            </button>
            {STATUS_OPTIONS.map(s => {
              const count = plantings.filter(p => p.status === s).length;
              return (
                <button
                  key={s}
                  style={styles.filterBtn(statusFilter === s)}
                  onClick={() => setStatusFilter(s)}
                >
                  {statusLabel(s)} ({count})
                </button>
              );
            })}
          </div>

          {filtered.length === 0 ? (
            <div style={styles.emptyState}>
              <i className="bi bi-journal" style={{ fontSize: 36, display: 'block', marginBottom: 8 }}></i>
              {plantings.length === 0
                ? t('plantingLog.empty')
                : t('plantingLog.emptyStatus', { status: statusLabel(statusFilter) })}
            </div>
          ) : (
            filtered.map(p => (
              <div key={p.id} style={styles.plantingCard}>
                <div style={styles.plantingHeader}>
                  <div>
                    <span style={styles.plantingTitle}>{cropLabel(t, p.category)}</span>
                    {p.variety && (
                      <span style={styles.plantingVariety}> - {p.variety}</span>
                    )}
                  </div>
                  <span style={styles.statusBadge(p.status)}>
                    {statusLabel(p.status)}
                  </span>
                </div>
                <div style={styles.plantingMeta}>
                  <div>
                    <i className="bi bi-calendar me-1"></i>
                    {t('plantingLog.plantedOn', { date: formatDate(p.planted_date) })}
                  </div>
                  {p.estimated_harvest_start && (
                    <div>
                      <i className="bi bi-calendar-check me-1"></i>
                      {p.estimated_harvest_end && p.estimated_harvest_end !== p.estimated_harvest_start
                        ? t('plantingLog.estHarvestRange', { start: formatDate(p.estimated_harvest_start), end: formatDate(p.estimated_harvest_end) })
                        : t('plantingLog.estHarvest', { date: formatDate(p.estimated_harvest_start) })}
                    </div>
                  )}
                  {(p.quantity_estimate || p.weight_lbs) && (
                    <div>
                      <i className="bi bi-box me-1"></i>
                      {p.weight_lbs ? t('plantingLog.weightLbs', { weight: p.weight_lbs }) : ''}
                      {p.weight_lbs && p.quantity_estimate ? ` (${p.quantity_estimate})` : p.quantity_estimate || ''}
                    </div>
                  )}
                  {p.sale_price > 0 && (
                    <div>
                      <i className="bi bi-tag me-1"></i>
                      <span style={{ color: '#16a34a', fontWeight: 600 }}>
                        ${p.sale_price.toFixed(2)}/{unitLabel(p.price_unit || 'lb')}
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
                      planted: t('plantingLog.tipPlanted'),
                      growing: t('plantingLog.tipGrowing'),
                      harvesting: t('plantingLog.tipHarvesting'),
                      done: t('plantingLog.tipDone'),
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
                        {statusLabel(s)}
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
                      title={p.allow_preorder ? t('plantingLog.preorderOnTip') : t('plantingLog.preorderOffTip')}
                    >
                      <i className={`bi ${p.allow_preorder ? 'bi-bag-check-fill' : 'bi-bag'} me-1`}></i>
                      {p.allow_preorder ? t('plantingLog.preorderOn') : t('plantingLog.preorderOff')}
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
                      title={p.auto_list_on_harvest ? t('plantingLog.autoListOnTip') : t('plantingLog.autoListOffTip')}
                    >
                      <i className={`bi ${p.auto_list_on_harvest ? 'bi-lightning-fill' : 'bi-lightning'} me-1`}></i>
                      {p.auto_list_on_harvest ? t('plantingLog.autoListOn') : t('plantingLog.autoListOff')}
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
                      {t('plantingLog.listOnMarketplace')}
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
                      {t('plantingLog.viewListing')}
                    </Link>
                  )}
                  <button
                    style={styles.deleteBtn}
                    onClick={() => handleDelete(p.id)}
                  >
                    <i className="bi bi-trash me-1"></i>
                    {t('dash.remove')}
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

// A server ISO date (YYYY-MM-DD) as a local calendar day, in the page's
// language. The T00:00:00 keeps it from parsing as UTC midnight, which is the
// previous day anywhere west of Greenwich.
function formatDate(isoStr) {
  if (!isoStr) return '';
  return formatLocaleDate(isoStr + 'T00:00:00', DAY_MONTH_YEAR);
}
