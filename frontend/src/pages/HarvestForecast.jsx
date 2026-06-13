import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { plantingAPI } from '../api';
import { useSiteConfig } from '../SiteConfigContext';
import { useAuth } from '../AuthContext';

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
  headerLinks: {
    display: 'flex',
    justifyContent: 'center',
    gap: 16,
    marginTop: 12,
  },
  headerLink: {
    color: 'var(--brand-accent)',
    textDecoration: 'none',
    fontSize: 13,
    fontWeight: 600,
  },
  backLink: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    color: 'var(--brand-accent)',
    textDecoration: 'none',
    fontWeight: 600,
    fontSize: 14,
    marginBottom: 20,
  },
  weekCard: {
    background: '#fff',
    border: '1px solid #e5e7eb',
    borderRadius: 12,
    marginBottom: 20,
    overflow: 'hidden',
  },
  weekHeader: {
    background: 'var(--brand-pale)',
    padding: '12px 20px',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  weekLabel: {
    fontWeight: 700,
    fontSize: 16,
    color: 'var(--brand-secondary)',
  },
  weekBadge: {
    background: 'var(--brand-secondary)',
    color: '#fff',
    padding: '3px 10px',
    borderRadius: 12,
    fontSize: 12,
    fontWeight: 600,
  },
  weekBody: {
    padding: 20,
  },
  emptyWeek: {
    color: '#999',
    fontStyle: 'italic',
    fontSize: 14,
  },
  categoryList: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
    gap: 12,
  },
  categoryCard: {
    background: '#f8f9fa',
    borderRadius: 8,
    padding: 14,
    border: '1px solid #e9ecef',
  },
  categoryName: {
    fontWeight: 700,
    fontSize: 15,
    color: 'var(--brand-secondary)',
    marginBottom: 6,
  },
  categoryMeta: {
    fontSize: 13,
    color: '#666',
    lineHeight: 1.6,
  },
  preorderBadge: {
    display: 'inline-block',
    background: 'var(--brand-accent)',
    color: '#fff',
    padding: '2px 8px',
    borderRadius: 10,
    fontSize: 11,
    fontWeight: 600,
    marginTop: 6,
  },
  notifyBtn: {
    display: 'inline-block',
    background: 'transparent',
    border: '1px solid var(--brand-accent)',
    color: 'var(--brand-accent)',
    padding: '4px 10px',
    borderRadius: 6,
    fontSize: 12,
    fontWeight: 600,
    cursor: 'pointer',
    marginTop: 6,
    marginLeft: 6,
  },
  emptyState: {
    textAlign: 'center',
    padding: 60,
    color: '#999',
  },
  emptyIcon: {
    fontSize: 48,
    marginBottom: 12,
    color: '#ccc',
  },
  preorderSection: {
    background: 'var(--brand-pale)',
    borderRadius: 12,
    padding: '20px 24px',
    marginBottom: 28,
    border: '1px solid var(--brand-light-green)',
  },
  preorderTitle: {
    fontWeight: 700,
    fontSize: 18,
    color: 'var(--brand-secondary)',
    marginBottom: 12,
  },
  preorderGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))',
    gap: 12,
  },
  preorderCard: {
    background: '#fff',
    borderRadius: 8,
    padding: 14,
    border: '1px solid var(--brand-light-green)',
  },
  preorderCat: {
    fontWeight: 700,
    color: 'var(--brand-secondary)',
    fontSize: 15,
  },
  preorderVariety: {
    fontSize: 13,
    color: '#666',
    fontStyle: 'italic',
  },
  preorderDetails: {
    fontSize: 13,
    color: '#555',
    marginTop: 6,
    lineHeight: 1.6,
  },
  loading: {
    textAlign: 'center',
    padding: 60,
    color: '#888',
  },
};


export default function HarvestForecast() {
  const { marketplaceEnabled } = useSiteConfig();
  const { user } = useAuth();
  const [forecast, setForecast] = useState([]);
  const [preorders, setPreorders] = useState([]);
  const [notified, setNotified] = useState(new Set());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const promises = [plantingAPI.forecast()];
    if (marketplaceEnabled) promises.push(plantingAPI.preorders());
    Promise.all(promises)
      .then(([fRes, pRes]) => {
        setForecast(fRes.data);
        if (pRes) setPreorders(pRes.data);
      })
      .catch(err => console.error('Failed to load forecast:', err))
      .finally(() => setLoading(false));
  }, [marketplaceEnabled]);

  // Load user's existing harvest notification subscriptions
  useEffect(() => {
    if (user) {
      plantingAPI.getInterests()
        .then(res => setNotified(new Set(res.data.map(i => i.category))))
        .catch(() => {});
    }
  }, [user]);

  const handleNotify = async (category) => {
    if (!user) return;
    try {
      if (notified.has(category)) {
        await plantingAPI.unsubscribe(category);
        setNotified(prev => { const next = new Set(prev); next.delete(category); return next; });
      } else {
        await plantingAPI.subscribe({
          category,
          notify_email: true,
          notify_sms: !!(user.sms_opt_in && user.phone_number),
        });
        setNotified(prev => new Set(prev).add(category));
      }
    } catch (err) {
      console.error('Failed to update notification preference:', err);
    }
  };

  if (loading) return <div style={styles.loading}>Loading harvest forecast...</div>;

  const hasAnyData = forecast.some(w => w.categories.length > 0);

  return (
    <div style={styles.page}>
      <Link to="/planting-calendar" style={styles.backLink}>
        <i className="bi bi-arrow-left"></i> Back to Planting Calendar
      </Link>

      <div style={styles.header}>
        <h1 style={styles.title}>
          <i className="bi bi-graph-up-arrow me-2"></i>
          Harvest Forecast
        </h1>
        <p style={styles.subtitle}>
          {marketplaceEnabled
            ? 'What local growers expect to harvest in the coming weeks'
            : 'Community harvest forecast based on planting logs'}
        </p>
        {user && (
          <div style={styles.headerLinks}>
            <Link to="/my-planting-log" style={styles.headerLink}>
              <i className="bi bi-journal-text me-1"></i>Log your own plantings
            </Link>
          </div>
        )}
      </div>

      {/* Pre-order Section (marketplace only) */}
      {marketplaceEnabled && preorders.length > 0 && (
        <div style={styles.preorderSection}>
          <div style={styles.preorderTitle}>
            <i className="bi bi-bag-check me-2"></i>
            Available for Pre-Order
          </div>
          <div style={styles.preorderGrid}>
            {preorders.map(p => (
              <div key={p.id} style={styles.preorderCard}>
                <div style={styles.preorderCat}>{p.category}</div>
                {p.variety && <div style={styles.preorderVariety}>{p.variety}</div>}
                <div style={styles.preorderDetails}>
                  <div>
                    <i className="bi bi-person me-1"></i>
                    {p.seller_name}
                  </div>
                  {p.quantity_estimate && (
                    <div>
                      <i className="bi bi-box me-1"></i>
                      Est. {p.quantity_estimate}
                    </div>
                  )}
                  <div>
                    <i className="bi bi-calendar me-1"></i>
                    Expected {formatDate(p.estimated_harvest_start)}
                    {p.estimated_harvest_end && p.estimated_harvest_end !== p.estimated_harvest_start
                      ? ` - ${formatDate(p.estimated_harvest_end)}`
                      : ''}
                  </div>
                </div>
                <Link
                  to={`/messages/new/${p.seller_id}`}
                  style={{
                    display: 'inline-block',
                    marginTop: 8,
                    padding: '4px 12px',
                    background: 'var(--brand-secondary)',
                    color: '#fff',
                    borderRadius: 6,
                    fontSize: 12,
                    fontWeight: 600,
                    textDecoration: 'none',
                  }}
                >
                  Contact to Pre-Order
                </Link>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Weekly Forecast */}
      {!hasAnyData && (!marketplaceEnabled || preorders.length === 0) ? (
        <div style={styles.emptyState}>
          <div style={styles.emptyIcon}>
            <i className="bi bi-calendar-x"></i>
          </div>
          <h3>No Harvest Data Yet</h3>
          <p>
            When growers log their plantings, harvest forecasts will appear here.
            <br />
            Growers can add their plantings from the{' '}
            <Link to="/my-planting-log" style={{ color: 'var(--brand-secondary)' }}>Planting Log</Link>.
          </p>
        </div>
      ) : (
        forecast.map((week, wi) => (
          <div key={wi} style={styles.weekCard}>
            <div style={styles.weekHeader}>
              <div style={styles.weekLabel}>
                <i className="bi bi-calendar-week me-2"></i>
                {week.week_label}
              </div>
              {week.categories.length > 0 && (
                <span style={styles.weekBadge}>
                  {week.categories.length} {week.categories.length === 1 ? 'crop' : 'crops'}
                </span>
              )}
            </div>
            <div style={styles.weekBody}>
              {week.categories.length === 0 ? (
                <div style={styles.emptyWeek}>
                  No harvests expected this week
                </div>
              ) : (
                <div style={styles.categoryList}>
                  {week.categories.map((cat, ci) => (
                    <div key={ci} style={styles.categoryCard}>
                      <div style={styles.categoryName}>{cat.category}</div>
                      <div style={styles.categoryMeta}>
                        <div>
                          <i className="bi bi-people me-1"></i>
                          {cat.seller_count} {cat.seller_count === 1 ? 'grower' : 'growers'}
                        </div>
                        {cat.quantities.length > 0 && (
                          <div>
                            <i className="bi bi-box me-1"></i>
                            {cat.quantities.slice(0, 3).join(', ')}
                            {cat.quantities.length > 3 && ' ...'}
                          </div>
                        )}
                      </div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 4 }}>
                        {marketplaceEnabled && cat.has_preorder && (
                          <span style={styles.preorderBadge}>Pre-order Available</span>
                        )}
                        {user ? (
                          <button
                            style={{
                              ...styles.notifyBtn,
                              ...(notified.has(cat.category) ? {
                                background: 'var(--brand-accent)',
                                color: '#fff',
                              } : {}),
                            }}
                            onClick={() => handleNotify(cat.category)}
                          >
                            <i className={`bi ${notified.has(cat.category) ? 'bi-bell-fill' : 'bi-bell'} me-1`}></i>
                            {notified.has(cat.category) ? 'Notified' : 'Notify Me'}
                          </button>
                        ) : (
                          <Link
                            to="/login"
                            style={{
                              ...styles.notifyBtn,
                              textDecoration: 'none',
                            }}
                          >
                            <i className="bi bi-bell me-1"></i>
                            Log in to get notified
                          </Link>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))
      )}
    </div>
  );
}

function formatDate(isoStr) {
  if (!isoStr) return '';
  const d = new Date(isoStr + 'T00:00:00');
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}
