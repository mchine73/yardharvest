import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { subscriptionsAPI, IMAGE_BASE } from '../api';
import { confirmDialog } from '../components/dialog/dialogService';

const styles = {
  container: { maxWidth: 900, margin: '0 auto' },
  header: { color: 'var(--brand-secondary)', marginBottom: 24 },
  empty: { textAlign: 'center', padding: 60, color: '#888' },
  card: {
    border: '1px solid var(--brand-pale)', borderRadius: 12, padding: 20,
    marginBottom: 16, background: '#fff', display: 'flex', gap: 16,
  },
  cardImg: { width: 120, height: 120, borderRadius: 10, objectFit: 'cover', flexShrink: 0 },
  cardImgPlaceholder: {
    width: 120, height: 120, borderRadius: 10, background: 'var(--brand-pale)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    color: 'var(--brand-accent)', fontSize: 36, flexShrink: 0,
  },
  cardBody: { flex: 1 },
  topRow: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 4 },
  title: { fontSize: 18, fontWeight: 600, color: 'var(--brand-secondary)', margin: 0 },
  statusBadge: {
    padding: '3px 10px', borderRadius: 12, fontSize: 12, fontWeight: 600,
    textTransform: 'uppercase', letterSpacing: 0.5,
  },
  statusActive: { background: 'var(--brand-pale)', color: 'var(--brand-secondary)' },
  statusPaused: { background: '#fff3cd', color: '#856404' },
  statusCancelled: { background: '#f8d7da', color: '#721c24' },
  sellerName: { fontSize: 13, color: '#888', marginBottom: 8 },
  details: { fontSize: 14, color: '#555', marginBottom: 10, lineHeight: 1.6 },
  actions: { display: 'flex', gap: 8, flexWrap: 'wrap' },
  btn: {
    padding: '6px 14px', borderRadius: 6, border: 'none', fontSize: 13,
    fontWeight: 500, cursor: 'pointer', transition: 'background 0.2s',
  },
  btnPause: { background: '#fff3cd', color: '#856404' },
  btnResume: { background: 'var(--brand-pale)', color: 'var(--brand-secondary)' },
  btnCancel: { background: '#f8d7da', color: '#721c24' },
  btnView: { background: '#e8f4f0', color: 'var(--brand-secondary)' },
  notes: {
    fontSize: 13, color: '#666', background: '#f9f9f9', borderRadius: 6,
    padding: '6px 10px', marginTop: 8,
  },
  alert: { padding: '10px 14px', borderRadius: 8, marginBottom: 12, fontSize: 14 },
  alertError: { background: '#fce4ec', color: '#c62828' },
  spinner: { textAlign: 'center', padding: 60, color: 'var(--brand-accent)' },
};

function getStatusStyle(status) {
  if (status === 'active') return styles.statusActive;
  if (status === 'paused') return styles.statusPaused;
  return styles.statusCancelled;
}

export default function ManageSubscriptions() {
  const [subs, setSubs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = () => {
    setLoading(true);
    subscriptionsAPI.mySubscriptions().then(res => {
      setSubs(res.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  };

  useEffect(load, []);

  const handleAction = async (subId, action) => {
    setError('');
    try {
      if (action === 'pause') await subscriptionsAPI.pause(subId);
      else if (action === 'resume') await subscriptionsAPI.resume(subId);
      else if (action === 'cancel') {
        if (!(await confirmDialog('Are you sure you want to cancel this subscription?', { danger: true, title: 'Cancel subscription', confirmText: 'Cancel it', cancelText: 'Keep it' }))) return;
        await subscriptionsAPI.cancel(subId);
      }
      load();
    } catch (err) {
      setError(err.response?.data?.error || 'Error updating subscription');
    }
  };

  if (loading) return <div style={styles.spinner}><div className="spinner-border text-success"></div></div>;

  const activeSubs = subs.filter(s => s.status !== 'cancelled');
  const cancelledSubs = subs.filter(s => s.status === 'cancelled');

  return (
    <div style={styles.container}>
      <h1 style={styles.header}>
        <i className="bi bi-box-seam me-2"></i>My Subscriptions
      </h1>

      {error && <div style={{ ...styles.alert, ...styles.alertError }}>{error}</div>}

      {subs.length === 0 ? (
        <div style={styles.empty}>
          <i className="bi bi-box" style={{ fontSize: 48, color: 'var(--brand-light-green)' }}></i>
          <p style={{ marginTop: 12 }}>You don't have any subscriptions yet.</p>
          <Link
            to="/subscriptions"
            style={{
              display: 'inline-block', padding: '10px 20px', borderRadius: 8,
              background: 'var(--brand-secondary)', color: '#fff', textDecoration: 'none',
              fontWeight: 500, marginTop: 8,
            }}
          >
            Browse Subscription Plans
          </Link>
        </div>
      ) : (
        <>
          {activeSubs.length > 0 && (
            <>
              <h5 style={{ color: '#555', marginBottom: 12 }}>Active & Paused</h5>
              {activeSubs.map(sub => {
                const plan = sub.plan;
                return (
                  <div key={sub.id} style={styles.card}>
                    {plan.photo_url ? (
                      <img
                        src={plan.photo_url.startsWith('http') ? plan.photo_url : `${IMAGE_BASE}${plan.photo_url}`}
                        style={styles.cardImg}
                        alt=""
                      />
                    ) : (
                      <div style={styles.cardImgPlaceholder}><i className="bi bi-basket"></i></div>
                    )}
                    <div style={styles.cardBody}>
                      <div style={styles.topRow}>
                        <Link to={`/subscriptions/plans/${plan.id}`} style={{ textDecoration: 'none' }}>
                          <h3 style={styles.title}>{plan.title}</h3>
                        </Link>
                        <span style={{ ...styles.statusBadge, ...getStatusStyle(sub.status) }}>
                          {sub.status}
                        </span>
                      </div>
                      <div style={styles.sellerName}>
                        <i className="bi bi-person me-1"></i>{plan.seller_name}
                      </div>
                      <div style={styles.details}>
                        <strong>${plan.price.toFixed(2)}</strong> / {plan.frequency}
                        {' '}&middot;{' '}
                        {plan.box_size.charAt(0).toUpperCase() + plan.box_size.slice(1)} box
                        {' '}&middot;{' '}
                        {sub.delivery_preference === 'delivery' ? 'Delivery' : 'Pickup'}
                        {' '}&middot;{' '}
                        {plan.fulfillment_day.charAt(0).toUpperCase() + plan.fulfillment_day.slice(1)}s
                      </div>
                      {sub.dietary_notes && (
                        <div style={styles.notes}>
                          <i className="bi bi-info-circle me-1"></i>
                          {sub.dietary_notes}
                        </div>
                      )}
                      <div style={styles.actions}>
                        <Link
                          to={`/subscriptions/plans/${plan.id}`}
                          style={{ ...styles.btn, ...styles.btnView, textDecoration: 'none' }}
                        >
                          <i className="bi bi-eye me-1"></i>View Plan
                        </Link>
                        {sub.status === 'active' && (
                          <button
                            style={{ ...styles.btn, ...styles.btnPause }}
                            onClick={() => handleAction(sub.id, 'pause')}
                          >
                            <i className="bi bi-pause-circle me-1"></i>Pause
                          </button>
                        )}
                        {sub.status === 'paused' && (
                          <button
                            style={{ ...styles.btn, ...styles.btnResume }}
                            onClick={() => handleAction(sub.id, 'resume')}
                          >
                            <i className="bi bi-play-circle me-1"></i>Resume
                          </button>
                        )}
                        {sub.status !== 'cancelled' && (
                          <button
                            style={{ ...styles.btn, ...styles.btnCancel }}
                            onClick={() => handleAction(sub.id, 'cancel')}
                          >
                            <i className="bi bi-x-circle me-1"></i>Cancel
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </>
          )}

          {cancelledSubs.length > 0 && (
            <>
              <h5 style={{ color: '#888', marginTop: 24, marginBottom: 12 }}>Cancelled</h5>
              {cancelledSubs.map(sub => {
                const plan = sub.plan;
                return (
                  <div key={sub.id} style={{ ...styles.card, opacity: 0.6 }}>
                    {plan.photo_url ? (
                      <img
                        src={plan.photo_url.startsWith('http') ? plan.photo_url : `${IMAGE_BASE}${plan.photo_url}`}
                        style={styles.cardImg}
                        alt=""
                      />
                    ) : (
                      <div style={styles.cardImgPlaceholder}><i className="bi bi-basket"></i></div>
                    )}
                    <div style={styles.cardBody}>
                      <div style={styles.topRow}>
                        <h3 style={styles.title}>{plan.title}</h3>
                        <span style={{ ...styles.statusBadge, ...styles.statusCancelled }}>cancelled</span>
                      </div>
                      <div style={styles.sellerName}>{plan.seller_name}</div>
                      <div style={styles.details}>
                        Cancelled on {new Date(sub.cancelled_at).toLocaleDateString()}
                      </div>
                    </div>
                  </div>
                );
              })}
            </>
          )}
        </>
      )}
    </div>
  );
}
