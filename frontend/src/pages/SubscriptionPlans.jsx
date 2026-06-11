import { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { subscriptionsAPI, IMAGE_BASE } from '../api';

const styles = {
  container: { maxWidth: 1100, margin: '0 auto' },
  header: { color: '#1d8a5f', marginBottom: 24 },
  filtersRow: { display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 24, alignItems: 'center' },
  select: {
    padding: '8px 12px', borderRadius: 8, border: '1px solid #ccc', fontSize: 14,
    background: '#fff', cursor: 'pointer',
  },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300, 1fr))', gap: 20 },
  card: {
    border: '1px solid #ecf7f1', borderRadius: 12, overflow: 'hidden',
    background: '#fff', transition: 'box-shadow 0.2s', cursor: 'pointer',
  },
  cardHover: { boxShadow: '0 4px 16px rgba(22,111,76,0.15)' },
  cardImg: { width: '100%', height: 180, objectFit: 'cover', background: '#ecf7f1' },
  cardImgPlaceholder: {
    width: '100%', height: 180, background: '#ecf7f1',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    color: '#2aa873', fontSize: 48,
  },
  cardBody: { padding: 16 },
  cardTitle: { fontSize: 18, fontWeight: 600, color: '#1d8a5f', margin: '0 0 4px' },
  cardSeller: { fontSize: 13, color: '#666', marginBottom: 8 },
  badges: { display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 },
  badge: {
    padding: '3px 10px', borderRadius: 12, fontSize: 12, fontWeight: 500,
    background: '#ecf7f1', color: '#1d8a5f',
  },
  badgeDelivery: { background: '#cce5ff', color: '#004085' },
  priceRow: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 },
  price: { fontSize: 20, fontWeight: 700, color: '#1d8a5f' },
  capacity: { fontSize: 13, color: '#888' },
  season: { fontSize: 12, color: '#666', marginTop: 4 },
  spinner: { textAlign: 'center', padding: 60, color: '#2aa873' },
  empty: { textAlign: 'center', padding: 60, color: '#888' },
  pagination: { display: 'flex', justifyContent: 'center', gap: 8, marginTop: 24 },
  pageBtn: {
    padding: '8px 14px', borderRadius: 8, border: '1px solid #2aa873',
    background: '#fff', color: '#2aa873', cursor: 'pointer', fontSize: 14,
  },
  pageBtnActive: {
    padding: '8px 14px', borderRadius: 8, border: '1px solid #1d8a5f',
    background: '#1d8a5f', color: '#fff', cursor: 'pointer', fontSize: 14,
  },
  pageBtnDisabled: {
    padding: '8px 14px', borderRadius: 8, border: '1px solid #ccc',
    background: '#f5f5f5', color: '#ccc', cursor: 'not-allowed', fontSize: 14,
  },
};

export default function SubscriptionPlans() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [plans, setPlans] = useState([]);
  const [pagination, setPagination] = useState({});
  const [loading, setLoading] = useState(true);
  const [hoveredCard, setHoveredCard] = useState(null);

  const page = parseInt(searchParams.get('page') || '1');
  const frequency = searchParams.get('frequency') || '';
  const box_size = searchParams.get('box_size') || '';
  const delivery = searchParams.get('delivery') || '';
  const sort = searchParams.get('sort') || 'newest';

  useEffect(() => {
    setLoading(true);
    subscriptionsAPI.browsePlans({ page, frequency, box_size, delivery, sort }).then(res => {
      setPlans(res.data.plans);
      setPagination(res.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [page, frequency, box_size, delivery, sort]);

  const updateFilter = (key, value) => {
    const p = new URLSearchParams(searchParams);
    if (value) {
      p.set(key, value);
    } else {
      p.delete(key);
    }
    p.delete('page');
    setSearchParams(p);
  };

  const formatFreq = (f) => {
    const map = { weekly: 'Weekly', biweekly: 'Bi-weekly', monthly: 'Monthly' };
    return map[f] || f;
  };

  const formatSize = (s) => {
    const map = { small: 'Small', medium: 'Medium', large: 'Large', family: 'Family' };
    return map[s] || s;
  };

  return (
    <div style={styles.container}>
      <h1 style={styles.header}>
        <i className="bi bi-box-seam me-2"></i>Subscription Boxes
      </h1>
      <p style={{ color: '#555', marginBottom: 20 }}>
        Subscribe to a local grower's seasonal produce box. Fresh, local harvests delivered on a regular schedule.
      </p>

      <div style={styles.filtersRow}>
        <select style={styles.select} value={frequency} onChange={e => updateFilter('frequency', e.target.value)}>
          <option value="">All Frequencies</option>
          <option value="weekly">Weekly</option>
          <option value="biweekly">Bi-weekly</option>
          <option value="monthly">Monthly</option>
        </select>
        <select style={styles.select} value={box_size} onChange={e => updateFilter('box_size', e.target.value)}>
          <option value="">All Sizes</option>
          <option value="small">Small</option>
          <option value="medium">Medium</option>
          <option value="large">Large</option>
          <option value="family">Family</option>
        </select>
        <select style={styles.select} value={delivery} onChange={e => updateFilter('delivery', e.target.value)}>
          <option value="">Pickup & Delivery</option>
          <option value="true">Delivery Available</option>
        </select>
        <select style={styles.select} value={sort} onChange={e => updateFilter('sort', e.target.value)}>
          <option value="newest">Newest</option>
          <option value="price_asc">Price: Low to High</option>
          <option value="price_desc">Price: High to Low</option>
          <option value="popular">Most Popular</option>
        </select>
      </div>

      {loading ? (
        <div style={styles.spinner}><div className="spinner-border text-success"></div></div>
      ) : plans.length === 0 ? (
        <div style={styles.empty}>
          <i className="bi bi-box" style={{ fontSize: 48, color: '#7fd4ab' }}></i>
          <p style={{ marginTop: 12 }}>No subscription plans found. Try adjusting your filters.</p>
        </div>
      ) : (
        <div style={styles.grid}>
          {plans.map(plan => (
            <Link
              to={`/subscriptions/plans/${plan.id}`}
              key={plan.id}
              style={{
                ...styles.card,
                ...(hoveredCard === plan.id ? styles.cardHover : {}),
                textDecoration: 'none', color: 'inherit',
              }}
              onMouseEnter={() => setHoveredCard(plan.id)}
              onMouseLeave={() => setHoveredCard(null)}
            >
              {plan.photo_url ? (
                <img src={plan.photo_url.startsWith('http') ? plan.photo_url : `${IMAGE_BASE}${plan.photo_url}`} style={styles.cardImg} alt={plan.title} />
              ) : (
                <div style={styles.cardImgPlaceholder}>
                  <i className="bi bi-basket"></i>
                </div>
              )}
              <div style={styles.cardBody}>
                <h3 style={styles.cardTitle}>{plan.title}</h3>
                <div style={styles.cardSeller}>
                  <i className="bi bi-person-circle me-1"></i>
                  {plan.seller_name}
                  {plan.seller_rating && (
                    <span className="ms-2">
                      <i className="bi bi-star-fill" style={{ color: '#d99a2b', fontSize: 12 }}></i> {plan.seller_rating}
                    </span>
                  )}
                </div>
                <div style={styles.badges}>
                  <span style={styles.badge}>{formatFreq(plan.frequency)}</span>
                  <span style={styles.badge}>{formatSize(plan.box_size)}</span>
                  {plan.includes_delivery && (
                    <span style={{ ...styles.badge, ...styles.badgeDelivery }}>
                      <i className="bi bi-truck me-1"></i>Delivery
                    </span>
                  )}
                </div>
                <div style={styles.priceRow}>
                  <span style={styles.price}>${plan.price.toFixed(2)}<span style={{ fontSize: 13, fontWeight: 400, color: '#888' }}>/{plan.frequency === 'monthly' ? 'mo' : plan.frequency === 'biweekly' ? '2wk' : 'wk'}</span></span>
                  <span style={styles.capacity}>
                    {plan.subscriber_count}/{plan.max_subscribers} subscribed
                  </span>
                </div>
                {plan.season_start && plan.season_end && (
                  <div style={styles.season}>
                    <i className="bi bi-calendar3 me-1"></i>
                    {new Date(plan.season_start).toLocaleDateString()} - {new Date(plan.season_end).toLocaleDateString()}
                  </div>
                )}
              </div>
            </Link>
          ))}
        </div>
      )}

      {pagination.pages > 1 && (
        <div style={styles.pagination}>
          <button
            style={pagination.has_prev ? styles.pageBtn : styles.pageBtnDisabled}
            disabled={!pagination.has_prev}
            onClick={() => { const p = new URLSearchParams(searchParams); p.set('page', page - 1); setSearchParams(p); }}
          >Previous</button>
          {Array.from({ length: pagination.pages }, (_, i) => (
            <button
              key={i}
              style={page === i + 1 ? styles.pageBtnActive : styles.pageBtn}
              onClick={() => { const p = new URLSearchParams(searchParams); p.set('page', i + 1); setSearchParams(p); }}
            >{i + 1}</button>
          ))}
          <button
            style={pagination.has_next ? styles.pageBtn : styles.pageBtnDisabled}
            disabled={!pagination.has_next}
            onClick={() => { const p = new URLSearchParams(searchParams); p.set('page', page + 1); setSearchParams(p); }}
          >Next</button>
        </div>
      )}
    </div>
  );
}
