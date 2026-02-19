import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { subscriptionsAPI, IMAGE_BASE } from '../api';

const styles = {
  container: { maxWidth: 1000, margin: '0 auto' },
  header: { color: '#2d6a4f', marginBottom: 8 },
  subtitle: { color: '#888', marginBottom: 24, fontSize: 14 },
  topActions: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 },
  createBtn: {
    display: 'inline-flex', alignItems: 'center', gap: 6, padding: '10px 20px',
    borderRadius: 8, background: '#2d6a4f', color: '#fff', textDecoration: 'none',
    fontWeight: 600, fontSize: 14,
  },
  statsRow: { display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 24 },
  stat: {
    background: '#d8f3dc', borderRadius: 12, padding: 20, textAlign: 'center',
  },
  statValue: { fontSize: 28, fontWeight: 700, color: '#2d6a4f' },
  statLabel: { fontSize: 13, color: '#40916c', marginTop: 4 },
  card: {
    border: '1px solid #d8f3dc', borderRadius: 12, overflow: 'hidden',
    background: '#fff', marginBottom: 16,
  },
  cardHeader: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: '14px 20px', background: '#f8fdf9', borderBottom: '1px solid #d8f3dc',
  },
  cardTitle: { fontSize: 18, fontWeight: 600, color: '#2d6a4f', margin: 0 },
  toggleBtn: {
    padding: '4px 12px', borderRadius: 6, border: '1px solid #ccc',
    fontSize: 12, fontWeight: 500, cursor: 'pointer', background: '#fff',
  },
  toggleActive: { borderColor: '#2d6a4f', color: '#2d6a4f' },
  toggleInactive: { borderColor: '#dc3545', color: '#dc3545' },
  cardBody: { padding: 20 },
  cardMeta: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 12, marginBottom: 16 },
  metaItem: {},
  metaLabel: { fontSize: 11, color: '#888', textTransform: 'uppercase', letterSpacing: 0.5 },
  metaValue: { fontSize: 15, fontWeight: 600, color: '#2d6a4f' },
  subscriberList: { marginTop: 12 },
  subscriberItem: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: '8px 12px', borderRadius: 6, background: '#f9f9f9', marginBottom: 6,
    fontSize: 14,
  },
  subscriberName: { fontWeight: 500, color: '#333' },
  subscriberDetail: { fontSize: 12, color: '#888' },
  statusDot: {
    width: 8, height: 8, borderRadius: '50%', display: 'inline-block', marginRight: 6,
  },
  cardActions: {
    display: 'flex', gap: 8, paddingTop: 12, borderTop: '1px solid #eee',
  },
  actionBtn: {
    padding: '6px 14px', borderRadius: 6, border: '1px solid #d8f3dc',
    background: '#fff', color: '#2d6a4f', fontSize: 13, fontWeight: 500,
    cursor: 'pointer', textDecoration: 'none', display: 'inline-flex',
    alignItems: 'center', gap: 4,
  },
  empty: { textAlign: 'center', padding: 60, color: '#888' },
  spinner: { textAlign: 'center', padding: 60, color: '#40916c' },
  alert: { padding: '10px 14px', borderRadius: 8, marginBottom: 12, fontSize: 14, background: '#fce4ec', color: '#c62828' },
};

export default function SellerSubscriptionDashboard() {
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = () => {
    setLoading(true);
    subscriptionsAPI.myPlans().then(res => {
      setPlans(res.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  };

  useEffect(load, []);

  const togglePlan = async (planId, currentActive) => {
    setError('');
    try {
      if (currentActive) {
        await subscriptionsAPI.deletePlan(planId);
      } else {
        await subscriptionsAPI.updatePlan(planId, { is_active: true });
      }
      load();
    } catch (err) {
      setError(err.response?.data?.error || 'Error updating plan');
    }
  };

  if (loading) return <div style={styles.spinner}><div className="spinner-border text-success"></div></div>;

  const totalSubscribers = plans.reduce((sum, p) => sum + p.subscriber_count, 0);
  const totalRevenue = plans.reduce((sum, p) => {
    const multiplier = { weekly: 4, biweekly: 2, monthly: 1 }[p.frequency] || 4;
    return sum + (p.price * p.subscriber_count * multiplier);
  }, 0);
  const activePlans = plans.filter(p => p.is_active).length;

  return (
    <div style={styles.container}>
      <div style={styles.topActions}>
        <div>
          <h1 style={styles.header}>
            <i className="bi bi-box-seam me-2"></i>My Subscription Plans
          </h1>
          <p style={styles.subtitle}>Manage your CSA-style produce boxes.</p>
        </div>
        <Link to="/subscriptions/create" style={styles.createBtn}>
          <i className="bi bi-plus-circle"></i> New Plan
        </Link>
      </div>

      {error && <div style={styles.alert}>{error}</div>}

      <div style={styles.statsRow}>
        <div style={styles.stat}>
          <div style={styles.statValue}>{activePlans}</div>
          <div style={styles.statLabel}>Active Plans</div>
        </div>
        <div style={styles.stat}>
          <div style={styles.statValue}>{totalSubscribers}</div>
          <div style={styles.statLabel}>Total Subscribers</div>
        </div>
        <div style={styles.stat}>
          <div style={styles.statValue}>${totalRevenue.toFixed(0)}</div>
          <div style={styles.statLabel}>Est. Monthly Revenue</div>
        </div>
      </div>

      {plans.length === 0 ? (
        <div style={styles.empty}>
          <i className="bi bi-box" style={{ fontSize: 48, color: '#95d5b2' }}></i>
          <p style={{ marginTop: 12 }}>You haven't created any subscription plans yet.</p>
          <Link to="/subscriptions/create" style={styles.createBtn}>
            <i className="bi bi-plus-circle"></i> Create Your First Plan
          </Link>
        </div>
      ) : (
        plans.map(plan => (
          <div key={plan.id} style={styles.card}>
            <div style={styles.cardHeader}>
              <Link to={`/subscriptions/plans/${plan.id}`} style={{ textDecoration: 'none' }}>
                <h3 style={styles.cardTitle}>{plan.title}</h3>
              </Link>
              <button
                style={{
                  ...styles.toggleBtn,
                  ...(plan.is_active ? styles.toggleActive : styles.toggleInactive),
                }}
                onClick={() => togglePlan(plan.id, plan.is_active)}
              >
                {plan.is_active ? 'Active' : 'Inactive'}
              </button>
            </div>
            <div style={styles.cardBody}>
              <div style={styles.cardMeta}>
                <div style={styles.metaItem}>
                  <div style={styles.metaLabel}>Price</div>
                  <div style={styles.metaValue}>${plan.price.toFixed(2)} / {plan.frequency}</div>
                </div>
                <div style={styles.metaItem}>
                  <div style={styles.metaLabel}>Box Size</div>
                  <div style={styles.metaValue}>
                    {plan.box_size.charAt(0).toUpperCase() + plan.box_size.slice(1)}
                  </div>
                </div>
                <div style={styles.metaItem}>
                  <div style={styles.metaLabel}>Subscribers</div>
                  <div style={styles.metaValue}>
                    {plan.subscriber_count} / {plan.max_subscribers}
                  </div>
                </div>
                <div style={styles.metaItem}>
                  <div style={styles.metaLabel}>Fulfillment</div>
                  <div style={styles.metaValue}>
                    {plan.fulfillment_day.charAt(0).toUpperCase() + plan.fulfillment_day.slice(1)}s
                  </div>
                </div>
                {plan.season_start && (
                  <div style={styles.metaItem}>
                    <div style={styles.metaLabel}>Season</div>
                    <div style={{ ...styles.metaValue, fontSize: 13 }}>
                      {new Date(plan.season_start).toLocaleDateString()} - {new Date(plan.season_end).toLocaleDateString()}
                    </div>
                  </div>
                )}
                <div style={styles.metaItem}>
                  <div style={styles.metaLabel}>Delivery</div>
                  <div style={styles.metaValue}>
                    {plan.includes_delivery ? `Within ${plan.delivery_radius_miles} mi` : 'Pickup Only'}
                  </div>
                </div>
              </div>

              {plan.active_subscribers && plan.active_subscribers.length > 0 && (
                <div style={styles.subscriberList}>
                  <strong style={{ fontSize: 13, color: '#555' }}>Subscribers:</strong>
                  {plan.active_subscribers.map(sub => (
                    <div key={sub.id} style={styles.subscriberItem}>
                      <div>
                        <span
                          style={{
                            ...styles.statusDot,
                            background: sub.status === 'active' ? '#40916c' : '#f59e0b',
                          }}
                        ></span>
                        <span style={styles.subscriberName}>{sub.buyer_name}</span>
                      </div>
                      <div style={styles.subscriberDetail}>
                        {sub.delivery_preference}
                        {sub.dietary_notes && ` | ${sub.dietary_notes}`}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <div style={styles.cardActions}>
                <Link
                  to={`/subscriptions/plans/${plan.id}/compose`}
                  style={styles.actionBtn}
                >
                  <i className="bi bi-pencil-square"></i> Compose Box Preview
                </Link>
                <Link
                  to={`/subscriptions/plans/${plan.id}`}
                  style={styles.actionBtn}
                >
                  <i className="bi bi-eye"></i> View Plan
                </Link>
              </div>
            </div>
          </div>
        ))
      )}
    </div>
  );
}
