import { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { subscriptionsAPI, IMAGE_BASE } from '../api';
import { useAuth } from '../AuthContext';

const styles = {
  container: { maxWidth: 1000, margin: '0 auto' },
  backBtn: {
    display: 'inline-flex', alignItems: 'center', gap: 6,
    color: '#2aa873', textDecoration: 'none', marginBottom: 16, fontSize: 14,
  },
  hero: { borderRadius: 16, overflow: 'hidden', marginBottom: 24 },
  heroImg: { width: '100%', height: 320, objectFit: 'cover' },
  heroPlaceholder: {
    width: '100%', height: 320, background: '#ecf7f1',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    color: '#2aa873', fontSize: 64,
  },
  grid: { display: 'grid', gridTemplateColumns: '1fr 340px', gap: 28 },
  mainCol: {},
  sidebar: {
    border: '1px solid #ecf7f1', borderRadius: 12, padding: 20,
    background: '#f8fdf9', alignSelf: 'start', position: 'sticky', top: 20,
  },
  title: { fontSize: 28, fontWeight: 700, color: '#1d8a5f', marginBottom: 8 },
  description: { color: '#444', lineHeight: 1.6, marginBottom: 20 },
  sectionTitle: { fontSize: 18, fontWeight: 600, color: '#1d8a5f', marginBottom: 12, marginTop: 24 },
  infoGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 20 },
  infoItem: {
    background: '#ecf7f1', borderRadius: 8, padding: 12,
    display: 'flex', alignItems: 'center', gap: 10,
  },
  infoIcon: { fontSize: 20, color: '#1d8a5f' },
  infoLabel: { fontSize: 12, color: '#666' },
  infoValue: { fontSize: 14, fontWeight: 600, color: '#1d8a5f' },
  sellerCard: {
    display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16,
    padding: 12, background: '#fff', borderRadius: 8, border: '1px solid #e0e0e0',
  },
  sellerAvatar: { width: 48, height: 48, borderRadius: '50%', objectFit: 'cover', background: '#ecf7f1' },
  sellerAvatarPlaceholder: {
    width: 48, height: 48, borderRadius: '50%', background: '#ecf7f1',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    color: '#2aa873', fontSize: 20,
  },
  price: { fontSize: 28, fontWeight: 700, color: '#1d8a5f', textAlign: 'center', marginBottom: 4 },
  priceFreq: { fontSize: 14, color: '#888', textAlign: 'center', marginBottom: 16 },
  capacityBar: {
    height: 8, borderRadius: 4, background: '#e0e0e0', marginBottom: 4, overflow: 'hidden',
  },
  capacityFill: { height: '100%', borderRadius: 4, background: '#2aa873', transition: 'width 0.3s' },
  capacityText: { fontSize: 12, color: '#888', textAlign: 'center', marginBottom: 16 },
  subscribeBtn: {
    width: '100%', padding: '12px 0', borderRadius: 8, border: 'none',
    background: '#1d8a5f', color: '#fff', fontSize: 16, fontWeight: 600,
    cursor: 'pointer', transition: 'background 0.2s',
  },
  subscribeBtnDisabled: {
    width: '100%', padding: '12px 0', borderRadius: 8, border: 'none',
    background: '#ccc', color: '#666', fontSize: 16, fontWeight: 600,
    cursor: 'not-allowed',
  },
  manageBadge: {
    textAlign: 'center', padding: '10px 0', borderRadius: 8,
    background: '#ecf7f1', color: '#1d8a5f', fontWeight: 600, marginBottom: 8,
  },
  previewCard: {
    border: '1px solid #e0e0e0', borderRadius: 10, overflow: 'hidden', marginBottom: 12,
    background: '#fff',
  },
  previewImg: { width: '100%', height: 160, objectFit: 'cover' },
  previewBody: { padding: 12 },
  previewDate: { fontSize: 13, fontWeight: 600, color: '#1d8a5f', marginBottom: 4 },
  previewItems: { fontSize: 14, color: '#444', whiteSpace: 'pre-line' },
  formGroup: { marginBottom: 14 },
  label: { display: 'block', fontSize: 13, fontWeight: 500, color: '#555', marginBottom: 4 },
  input: { width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid #ccc', fontSize: 14 },
  select: { width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid #ccc', fontSize: 14, background: '#fff' },
  alert: { padding: '10px 14px', borderRadius: 8, marginBottom: 12, fontSize: 14 },
  alertError: { background: '#fce4ec', color: '#c62828' },
  alertSuccess: { background: '#ecf7f1', color: '#1d8a5f' },
  spinner: { textAlign: 'center', padding: 60, color: '#2aa873' },
};

export default function SubscriptionPlanDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [plan, setPlan] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    dietary_notes: '',
    substitution_pref: 'seller_choice',
    delivery_preference: 'pickup',
  });
  const [msg, setMsg] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    subscriptionsAPI.planDetail(id).then(res => setPlan(res.data)).catch(() => {});
  }, [id]);

  if (!plan) return <div style={styles.spinner}><div className="spinner-border text-success"></div></div>;

  const capacityPct = Math.round((plan.subscriber_count / plan.max_subscribers) * 100);
  const isFull = plan.subscriber_count >= plan.max_subscribers;
  const isOwner = user && user.id === plan.seller_id;
  const hasSubscription = plan.user_subscription != null;

  const freqLabel = { weekly: 'per week', biweekly: 'every 2 weeks', monthly: 'per month' }[plan.frequency] || plan.frequency;
  const sizeLabel = { small: 'Small', medium: 'Medium', large: 'Large', family: 'Family' }[plan.box_size] || plan.box_size;

  const handleSubscribe = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError('');
    try {
      await subscriptionsAPI.subscribe(plan.id, form);
      setMsg('Successfully subscribed!');
      setShowForm(false);
      // Refresh plan data
      const res = await subscriptionsAPI.planDetail(id);
      setPlan(res.data);
    } catch (err) {
      setError(err.response?.data?.error || 'Error subscribing');
    }
    setSubmitting(false);
  };

  return (
    <div style={styles.container}>
      <Link to="/subscriptions" style={styles.backBtn}>
        <i className="bi bi-arrow-left"></i> Back to Plans
      </Link>

      <div style={styles.hero}>
        {plan.photo_url ? (
          <img
            src={plan.photo_url.startsWith('http') ? plan.photo_url : `${IMAGE_BASE}${plan.photo_url}`}
            style={styles.heroImg}
            alt={plan.title}
          />
        ) : (
          <div style={styles.heroPlaceholder}>
            <i className="bi bi-basket"></i>
          </div>
        )}
      </div>

      <div style={styles.grid}>
        <div style={styles.mainCol}>
          <h1 style={styles.title}>{plan.title}</h1>
          <p style={styles.description}>{plan.description}</p>

          <div style={styles.infoGrid}>
            <div style={styles.infoItem}>
              <i className="bi bi-calendar-week" style={styles.infoIcon}></i>
              <div>
                <div style={styles.infoLabel}>Frequency</div>
                <div style={styles.infoValue}>{plan.frequency.charAt(0).toUpperCase() + plan.frequency.slice(1)}</div>
              </div>
            </div>
            <div style={styles.infoItem}>
              <i className="bi bi-box" style={styles.infoIcon}></i>
              <div>
                <div style={styles.infoLabel}>Box Size</div>
                <div style={styles.infoValue}>{sizeLabel}</div>
              </div>
            </div>
            <div style={styles.infoItem}>
              <i className="bi bi-calendar-range" style={styles.infoIcon}></i>
              <div>
                <div style={styles.infoLabel}>Fulfillment Day</div>
                <div style={styles.infoValue}>{plan.fulfillment_day.charAt(0).toUpperCase() + plan.fulfillment_day.slice(1)}</div>
              </div>
            </div>
            <div style={styles.infoItem}>
              <i className="bi bi-truck" style={styles.infoIcon}></i>
              <div>
                <div style={styles.infoLabel}>Delivery</div>
                <div style={styles.infoValue}>{plan.includes_delivery ? `Within ${plan.delivery_radius_miles} mi` : 'Pickup Only'}</div>
              </div>
            </div>
          </div>

          {plan.season_start && plan.season_end && (
            <>
              <h3 style={styles.sectionTitle}><i className="bi bi-calendar3 me-2"></i>Season</h3>
              <p style={{ color: '#555' }}>
                {new Date(plan.season_start).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}
                {' '}&mdash;{' '}
                {new Date(plan.season_end).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}
              </p>
            </>
          )}

          {plan.recent_previews && plan.recent_previews.length > 0 && (
            <>
              <h3 style={styles.sectionTitle}><i className="bi bi-eye me-2"></i>Recent Box Previews</h3>
              {plan.recent_previews.map(preview => (
                <div key={preview.id} style={styles.previewCard}>
                  {preview.photo_url && (
                    <img
                      src={preview.photo_url.startsWith('http') ? preview.photo_url : `${IMAGE_BASE}${preview.photo_url}`}
                      style={styles.previewImg}
                      alt="Box preview"
                    />
                  )}
                  <div style={styles.previewBody}>
                    <div style={styles.previewDate}>
                      Week of {new Date(preview.week_of).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}
                    </div>
                    <div style={styles.previewItems}>{preview.items_description}</div>
                  </div>
                </div>
              ))}
            </>
          )}
        </div>

        <div style={styles.sidebar}>
          <Link to={`/profile/${plan.seller_id}`} style={{ textDecoration: 'none', color: 'inherit' }}>
            <div style={styles.sellerCard}>
              {plan.seller_image ? (
                <img src={`${IMAGE_BASE}${plan.seller_image}`} style={styles.sellerAvatar} alt="" />
              ) : (
                <div style={styles.sellerAvatarPlaceholder}><i className="bi bi-person"></i></div>
              )}
              <div>
                <div style={{ fontWeight: 600, color: '#1d8a5f' }}>{plan.seller_name}</div>
                {plan.seller_rating && (
                  <div style={{ fontSize: 13, color: '#888' }}>
                    <i className="bi bi-star-fill" style={{ color: '#d99a2b' }}></i> {plan.seller_rating} ({plan.seller_review_count} reviews)
                  </div>
                )}
              </div>
            </div>
          </Link>

          <div style={styles.price}>${plan.price.toFixed(2)}</div>
          <div style={styles.priceFreq}>{freqLabel}</div>

          <div style={styles.capacityBar}>
            <div style={{ ...styles.capacityFill, width: `${Math.min(capacityPct, 100)}%` }}></div>
          </div>
          <div style={styles.capacityText}>{plan.subscriber_count} of {plan.max_subscribers} spots filled</div>

          {msg && <div style={{ ...styles.alert, ...styles.alertSuccess }}>{msg}</div>}
          {error && <div style={{ ...styles.alert, ...styles.alertError }}>{error}</div>}

          {!user && (
            <p style={{ textAlign: 'center', fontSize: 14, color: '#888' }}>
              <Link to="/login">Log in</Link> to subscribe
            </p>
          )}

          {user && isOwner && (
            <div style={styles.manageBadge}>
              <i className="bi bi-gear me-1"></i>You own this plan
            </div>
          )}

          {user && hasSubscription && !isOwner && (
            <>
              <div style={styles.manageBadge}>
                <i className="bi bi-check-circle me-1"></i>
                Subscribed ({plan.user_subscription.status})
              </div>
              <Link
                to="/my-subscriptions"
                style={{ ...styles.subscribeBtn, display: 'block', textAlign: 'center', textDecoration: 'none', background: '#2aa873' }}
              >
                Manage Subscription
              </Link>
            </>
          )}

          {user && !isOwner && !hasSubscription && !showForm && (
            <button
              style={isFull ? styles.subscribeBtnDisabled : styles.subscribeBtn}
              disabled={isFull}
              onClick={() => setShowForm(true)}
            >
              {isFull ? 'Plan Full' : 'Subscribe Now'}
            </button>
          )}

          {showForm && (
            <form onSubmit={handleSubscribe} style={{ marginTop: 12 }}>
              <div style={styles.formGroup}>
                <label style={styles.label}>Dietary Notes / Allergies</label>
                <textarea
                  style={{ ...styles.input, minHeight: 60 }}
                  value={form.dietary_notes}
                  onChange={e => setForm({ ...form, dietary_notes: e.target.value })}
                  placeholder="e.g. No cilantro, nut allergy"
                />
              </div>
              <div style={styles.formGroup}>
                <label style={styles.label}>Substitution Preference</label>
                <select
                  style={styles.select}
                  value={form.substitution_pref}
                  onChange={e => setForm({ ...form, substitution_pref: e.target.value })}
                >
                  <option value="seller_choice">Seller's choice</option>
                  <option value="no_subs">No substitutions</option>
                  <option value="similar_only">Similar items only</option>
                </select>
              </div>
              {plan.includes_delivery && (
                <div style={styles.formGroup}>
                  <label style={styles.label}>Fulfillment Method</label>
                  <select
                    style={styles.select}
                    value={form.delivery_preference}
                    onChange={e => setForm({ ...form, delivery_preference: e.target.value })}
                  >
                    <option value="pickup">Pickup</option>
                    <option value="delivery">Delivery</option>
                  </select>
                </div>
              )}
              <button type="submit" style={styles.subscribeBtn} disabled={submitting}>
                {submitting ? 'Subscribing...' : 'Confirm Subscription'}
              </button>
              <button
                type="button"
                onClick={() => setShowForm(false)}
                style={{ ...styles.subscribeBtn, background: '#e0e0e0', color: '#555', marginTop: 8 }}
              >
                Cancel
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
