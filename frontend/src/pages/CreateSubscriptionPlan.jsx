import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { subscriptionsAPI } from '../api';
import PhotoUploadInput from '../components/PhotoUploadInput';

const styles = {
  container: { maxWidth: 700, margin: '0 auto' },
  header: { color: '#1d8a5f', marginBottom: 8 },
  subtitle: { color: '#888', marginBottom: 24, fontSize: 14 },
  steps: { display: 'flex', gap: 0, marginBottom: 28 },
  step: {
    flex: 1, textAlign: 'center', padding: '10px 0', fontSize: 13, fontWeight: 500,
    background: '#f5f5f5', color: '#999', borderBottom: '3px solid #e0e0e0',
    cursor: 'pointer', transition: 'all 0.2s',
  },
  stepActive: {
    flex: 1, textAlign: 'center', padding: '10px 0', fontSize: 13, fontWeight: 600,
    background: '#ecf7f1', color: '#1d8a5f', borderBottom: '3px solid #1d8a5f',
    cursor: 'pointer',
  },
  stepDone: {
    flex: 1, textAlign: 'center', padding: '10px 0', fontSize: 13, fontWeight: 500,
    background: '#e8f4f0', color: '#2aa873', borderBottom: '3px solid #2aa873',
    cursor: 'pointer',
  },
  card: {
    border: '1px solid #ecf7f1', borderRadius: 12, padding: 24, background: '#fff',
  },
  formGroup: { marginBottom: 18 },
  label: { display: 'block', fontSize: 14, fontWeight: 500, color: '#333', marginBottom: 5 },
  input: {
    width: '100%', padding: '10px 12px', borderRadius: 8, border: '1px solid #ccc',
    fontSize: 14, boxSizing: 'border-box',
  },
  textarea: {
    width: '100%', padding: '10px 12px', borderRadius: 8, border: '1px solid #ccc',
    fontSize: 14, minHeight: 80, resize: 'vertical', boxSizing: 'border-box',
  },
  select: {
    width: '100%', padding: '10px 12px', borderRadius: 8, border: '1px solid #ccc',
    fontSize: 14, background: '#fff', boxSizing: 'border-box',
  },
  row: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 },
  btnRow: { display: 'flex', justifyContent: 'space-between', marginTop: 20 },
  btnPrimary: {
    padding: '10px 24px', borderRadius: 8, border: 'none',
    background: '#1d8a5f', color: '#fff', fontSize: 15, fontWeight: 600,
    cursor: 'pointer',
  },
  btnSecondary: {
    padding: '10px 24px', borderRadius: 8, border: '1px solid #ccc',
    background: '#fff', color: '#555', fontSize: 15, cursor: 'pointer',
  },
  btnDisabled: {
    padding: '10px 24px', borderRadius: 8, border: 'none',
    background: '#ccc', color: '#666', fontSize: 15, cursor: 'not-allowed',
  },
  previewBox: {
    border: '1px solid #ecf7f1', borderRadius: 12, overflow: 'hidden',
    background: '#fff', maxWidth: 380, margin: '0 auto',
  },
  previewImgPlaceholder: {
    height: 160, background: '#ecf7f1', display: 'flex',
    alignItems: 'center', justifyContent: 'center', color: '#2aa873', fontSize: 48,
  },
  previewBody: { padding: 16 },
  previewTitle: { fontSize: 18, fontWeight: 600, color: '#1d8a5f', marginBottom: 4 },
  previewDetail: { fontSize: 13, color: '#666', marginBottom: 2 },
  previewPrice: { fontSize: 22, fontWeight: 700, color: '#1d8a5f', marginTop: 8 },
  checkbox: { display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' },
  alert: { padding: '10px 14px', borderRadius: 8, marginBottom: 12, fontSize: 14, background: '#fce4ec', color: '#c62828' },
};

const STEPS = ['Basics', 'Pricing & Frequency', 'Season & Capacity', 'Delivery Options'];

export default function CreateSubscriptionPlan() {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [form, setForm] = useState({
    title: '',
    description: '',
    photo_url: '',
    price: '',
    frequency: 'weekly',
    fulfillment_day: 'saturday',
    box_size: 'medium',
    season_start: '',
    season_end: '',
    max_subscribers: 20,
    includes_delivery: false,
    delivery_radius_miles: 10,
  });

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setForm(prev => ({ ...prev, [name]: type === 'checkbox' ? checked : value }));
  };

  const canNext = () => {
    if (step === 0) return form.title.trim().length > 0;
    if (step === 1) return form.price && parseFloat(form.price) > 0;
    return true;
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    setError('');
    try {
      const payload = {
        ...form,
        price: parseFloat(form.price),
        max_subscribers: parseInt(form.max_subscribers),
        delivery_radius_miles: parseFloat(form.delivery_radius_miles),
      };
      if (!payload.season_start) delete payload.season_start;
      if (!payload.season_end) delete payload.season_end;
      const res = await subscriptionsAPI.createPlan(payload);
      navigate(`/subscriptions/plans/${res.data.id}`);
    } catch (err) {
      setError(err.response?.data?.error || 'Error creating plan');
      setSubmitting(false);
    }
  };

  const freqLabel = { weekly: 'per week', biweekly: 'every 2 weeks', monthly: 'per month' }[form.frequency];
  const sizeLabel = { small: 'Small', medium: 'Medium', large: 'Large', family: 'Family' }[form.box_size];

  return (
    <div style={styles.container}>
      <h1 style={styles.header}>
        <i className="bi bi-plus-circle me-2"></i>Create Subscription Plan
      </h1>
      <p style={styles.subtitle}>Set up a recurring produce box for your customers.</p>

      <div style={styles.steps}>
        {STEPS.map((label, i) => (
          <div
            key={i}
            style={i === step ? styles.stepActive : i < step ? styles.stepDone : styles.step}
            onClick={() => { if (i < step) setStep(i); }}
          >
            {i < step ? <i className="bi bi-check-circle me-1"></i> : `${i + 1}. `}
            {label}
          </div>
        ))}
      </div>

      {error && <div style={styles.alert}>{error}</div>}

      <div style={styles.card}>
        {step === 0 && (
          <>
            <div style={styles.formGroup}>
              <label style={styles.label}>Plan Title *</label>
              <input
                style={styles.input}
                name="title"
                value={form.title}
                onChange={handleChange}
                placeholder="e.g. Weekly Veggie Box"
              />
            </div>
            <div style={styles.formGroup}>
              <label style={styles.label}>Description</label>
              <textarea
                style={styles.textarea}
                name="description"
                value={form.description}
                onChange={handleChange}
                placeholder="Describe what subscribers can expect in their box each week..."
              />
            </div>
            <div style={styles.formGroup}>
              <PhotoUploadInput
                value={form.photo_url}
                onChange={val => setForm(prev => ({ ...prev, photo_url: val }))}
                label="Plan Photo"
                category="general"
                hint="Upload a photo for this subscription plan (optional)"
              />
            </div>
          </>
        )}

        {step === 1 && (
          <>
            <div style={styles.row}>
              <div style={styles.formGroup}>
                <label style={styles.label}>Price ($) *</label>
                <input
                  style={styles.input}
                  type="number"
                  step="0.01"
                  min="0"
                  name="price"
                  value={form.price}
                  onChange={handleChange}
                  placeholder="25.00"
                />
              </div>
              <div style={styles.formGroup}>
                <label style={styles.label}>Frequency</label>
                <select style={styles.select} name="frequency" value={form.frequency} onChange={handleChange}>
                  <option value="weekly">Weekly</option>
                  <option value="biweekly">Bi-weekly</option>
                  <option value="monthly">Monthly</option>
                </select>
              </div>
            </div>
            <div style={styles.row}>
              <div style={styles.formGroup}>
                <label style={styles.label}>Fulfillment Day</label>
                <select style={styles.select} name="fulfillment_day" value={form.fulfillment_day} onChange={handleChange}>
                  {['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'].map(d => (
                    <option key={d} value={d}>{d.charAt(0).toUpperCase() + d.slice(1)}</option>
                  ))}
                </select>
              </div>
              <div style={styles.formGroup}>
                <label style={styles.label}>Box Size</label>
                <select style={styles.select} name="box_size" value={form.box_size} onChange={handleChange}>
                  <option value="small">Small (1-2 people)</option>
                  <option value="medium">Medium (2-3 people)</option>
                  <option value="large">Large (3-4 people)</option>
                  <option value="family">Family (5+ people)</option>
                </select>
              </div>
            </div>
          </>
        )}

        {step === 2 && (
          <>
            <div style={styles.row}>
              <div style={styles.formGroup}>
                <label style={styles.label}>Season Start</label>
                <input
                  style={styles.input}
                  type="date"
                  name="season_start"
                  value={form.season_start}
                  onChange={handleChange}
                />
              </div>
              <div style={styles.formGroup}>
                <label style={styles.label}>Season End</label>
                <input
                  style={styles.input}
                  type="date"
                  name="season_end"
                  value={form.season_end}
                  onChange={handleChange}
                />
              </div>
            </div>
            <div style={styles.formGroup}>
              <label style={styles.label}>Max Subscribers</label>
              <input
                style={styles.input}
                type="number"
                min="1"
                name="max_subscribers"
                value={form.max_subscribers}
                onChange={handleChange}
              />
              <span style={{ fontSize: 12, color: '#888' }}>
                Limit how many people can subscribe to this plan.
              </span>
            </div>
          </>
        )}

        {step === 3 && (
          <>
            <div style={styles.formGroup}>
              <label style={styles.checkbox}>
                <input
                  type="checkbox"
                  name="includes_delivery"
                  checked={form.includes_delivery}
                  onChange={handleChange}
                />
                <span style={{ fontSize: 14, fontWeight: 500, color: '#333' }}>Offer delivery</span>
              </label>
            </div>
            {form.includes_delivery && (
              <div style={styles.formGroup}>
                <label style={styles.label}>Delivery Radius (miles)</label>
                <input
                  style={styles.input}
                  type="number"
                  min="1"
                  name="delivery_radius_miles"
                  value={form.delivery_radius_miles}
                  onChange={handleChange}
                />
              </div>
            )}

            <h4 style={{ color: '#1d8a5f', marginTop: 28, marginBottom: 16 }}>Preview</h4>
            <div style={styles.previewBox}>
              <div style={styles.previewImgPlaceholder}>
                <i className="bi bi-basket"></i>
              </div>
              <div style={styles.previewBody}>
                <div style={styles.previewTitle}>{form.title || 'Plan Title'}</div>
                <div style={styles.previewDetail}>{sizeLabel} box &middot; {form.frequency}</div>
                <div style={styles.previewDetail}>
                  {form.fulfillment_day.charAt(0).toUpperCase() + form.fulfillment_day.slice(1)}s
                  {form.includes_delivery ? ' | Delivery available' : ' | Pickup only'}
                </div>
                {form.season_start && form.season_end && (
                  <div style={styles.previewDetail}>
                    {new Date(form.season_start + 'T00:00').toLocaleDateString()} - {new Date(form.season_end + 'T00:00').toLocaleDateString()}
                  </div>
                )}
                <div style={styles.previewPrice}>
                  ${parseFloat(form.price || 0).toFixed(2)}
                  <span style={{ fontSize: 13, fontWeight: 400, color: '#888' }}> {freqLabel}</span>
                </div>
                <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
                  0/{form.max_subscribers} subscribed
                </div>
              </div>
            </div>
          </>
        )}

        <div style={styles.btnRow}>
          {step > 0 ? (
            <button style={styles.btnSecondary} onClick={() => setStep(step - 1)}>
              <i className="bi bi-arrow-left me-1"></i>Back
            </button>
          ) : (
            <div></div>
          )}
          {step < STEPS.length - 1 ? (
            <button
              style={canNext() ? styles.btnPrimary : styles.btnDisabled}
              disabled={!canNext()}
              onClick={() => setStep(step + 1)}
            >
              Next<i className="bi bi-arrow-right ms-1"></i>
            </button>
          ) : (
            <button
              style={submitting ? styles.btnDisabled : styles.btnPrimary}
              disabled={submitting}
              onClick={handleSubmit}
            >
              {submitting ? 'Creating...' : 'Create Plan'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
