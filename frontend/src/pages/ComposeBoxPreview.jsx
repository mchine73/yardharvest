import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { subscriptionsAPI } from '../api';
import PhotoUploadInput from '../components/PhotoUploadInput';

const styles = {
  container: { maxWidth: 800, margin: '0 auto' },
  header: { color: '#2d6a4f', marginBottom: 8 },
  subtitle: { color: '#888', marginBottom: 24, fontSize: 14 },
  backBtn: {
    display: 'inline-flex', alignItems: 'center', gap: 6,
    color: '#40916c', textDecoration: 'none', marginBottom: 16, fontSize: 14,
  },
  grid: { display: 'grid', gridTemplateColumns: '1fr 320px', gap: 24 },
  formCard: {
    border: '1px solid #D8EDDF', borderRadius: 12, padding: 24, background: '#fff',
  },
  formGroup: { marginBottom: 18 },
  label: { display: 'block', fontSize: 14, fontWeight: 500, color: '#333', marginBottom: 5 },
  input: {
    width: '100%', padding: '10px 12px', borderRadius: 8, border: '1px solid #ccc',
    fontSize: 14, boxSizing: 'border-box',
  },
  textarea: {
    width: '100%', padding: '10px 12px', borderRadius: 8, border: '1px solid #ccc',
    fontSize: 14, minHeight: 140, resize: 'vertical', boxSizing: 'border-box',
    fontFamily: 'inherit',
  },
  checkbox: { display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', marginBottom: 16 },
  submitBtn: {
    padding: '10px 24px', borderRadius: 8, border: 'none',
    background: '#2d6a4f', color: '#fff', fontSize: 15, fontWeight: 600,
    cursor: 'pointer', width: '100%',
  },
  submitBtnDisabled: {
    padding: '10px 24px', borderRadius: 8, border: 'none',
    background: '#ccc', color: '#666', fontSize: 15, cursor: 'not-allowed', width: '100%',
  },
  previewSidebar: { alignSelf: 'start', position: 'sticky', top: 20 },
  previewLabel: { fontSize: 13, fontWeight: 600, color: '#888', marginBottom: 8, textTransform: 'uppercase', letterSpacing: 0.5 },
  previewCard: {
    border: '1px solid #D8EDDF', borderRadius: 12, overflow: 'hidden', background: '#fff',
  },
  previewImgPlaceholder: {
    height: 150, background: '#D8EDDF', display: 'flex',
    alignItems: 'center', justifyContent: 'center', color: '#40916c', fontSize: 36,
  },
  previewImg: { width: '100%', height: 150, objectFit: 'cover' },
  previewBody: { padding: 14 },
  previewDate: { fontSize: 14, fontWeight: 600, color: '#2d6a4f', marginBottom: 6 },
  previewItems: { fontSize: 14, color: '#444', whiteSpace: 'pre-line', lineHeight: 1.6 },
  previewDraft: {
    display: 'inline-block', fontSize: 11, fontWeight: 600, color: '#856404',
    background: '#fff3cd', padding: '2px 8px', borderRadius: 10, marginTop: 8,
  },
  previewPublished: {
    display: 'inline-block', fontSize: 11, fontWeight: 600, color: '#2d6a4f',
    background: '#D8EDDF', padding: '2px 8px', borderRadius: 10, marginTop: 8,
  },
  alert: { padding: '10px 14px', borderRadius: 8, marginBottom: 12, fontSize: 14 },
  alertError: { background: '#fce4ec', color: '#c62828' },
  alertSuccess: { background: '#D8EDDF', color: '#2d6a4f' },
  hint: { fontSize: 12, color: '#888', marginTop: 4 },
  spinner: { textAlign: 'center', padding: 60, color: '#40916c' },
  pastPreviews: { marginTop: 28 },
  pastPreviewItem: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: '10px 14px', borderRadius: 8, border: '1px solid #eee', marginBottom: 8,
    background: '#fafafa',
  },
};

export default function ComposeBoxPreview() {
  const { id: planId } = useParams();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    week_of: '',
    items_description: '',
    photo_url: '',
    is_published: false,
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [pastPreviews, setPastPreviews] = useState([]);
  const [planTitle, setPlanTitle] = useState('');

  useEffect(() => {
    subscriptionsAPI.planDetail(planId).then(res => {
      setPlanTitle(res.data.title);
    }).catch(() => {});
    subscriptionsAPI.planPreviews(planId).then(res => {
      setPastPreviews(res.data);
    }).catch(() => {});
  }, [planId]);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setForm(prev => ({ ...prev, [name]: type === 'checkbox' ? checked : value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.week_of) {
      setError('Please select a week date.');
      return;
    }
    if (!form.items_description.trim()) {
      setError('Please describe the box contents.');
      return;
    }
    setSubmitting(true);
    setError('');
    setSuccess('');
    try {
      await subscriptionsAPI.createPreview(planId, form);
      setSuccess('Box preview created successfully!');
      setForm({ week_of: '', items_description: '', photo_url: '', is_published: false });
      // Refresh past previews
      const res = await subscriptionsAPI.planPreviews(planId);
      setPastPreviews(res.data);
    } catch (err) {
      setError(err.response?.data?.error || 'Error creating preview');
    }
    setSubmitting(false);
  };

  const formatDate = (d) => {
    if (!d) return 'Select a date';
    return new Date(d + 'T00:00').toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });
  };

  return (
    <div style={styles.container}>
      <Link to="/seller/subscriptions" style={styles.backBtn}>
        <i className="bi bi-arrow-left"></i> Back to Dashboard
      </Link>

      <h1 style={styles.header}>
        <i className="bi bi-pencil-square me-2"></i>Compose Box Preview
      </h1>
      <p style={styles.subtitle}>
        {planTitle ? `For: ${planTitle}` : 'Loading plan...'}
        {' '}&mdash; Let your subscribers know what to expect in their next box.
      </p>

      {error && <div style={{ ...styles.alert, ...styles.alertError }}>{error}</div>}
      {success && <div style={{ ...styles.alert, ...styles.alertSuccess }}>{success}</div>}

      <div style={styles.grid}>
        <form style={styles.formCard} onSubmit={handleSubmit}>
          <div style={styles.formGroup}>
            <label style={styles.label}>Week Of *</label>
            <input
              style={styles.input}
              type="date"
              name="week_of"
              value={form.week_of}
              onChange={handleChange}
            />
            <div style={styles.hint}>The date of the week this box is for.</div>
          </div>

          <div style={styles.formGroup}>
            <label style={styles.label}>Box Contents *</label>
            <textarea
              style={styles.textarea}
              name="items_description"
              value={form.items_description}
              onChange={handleChange}
              placeholder={"Example:\n- 2 lbs heirloom tomatoes\n- 1 bunch kale\n- 3 ears sweet corn\n- 1 pint cherry tomatoes\n- 1 bunch fresh basil\n- 2 summer squash"}
            />
            <div style={styles.hint}>List each item on its own line. Subscribers love knowing exactly what they'll get!</div>
          </div>

          <div style={styles.formGroup}>
            <PhotoUploadInput
              value={form.photo_url}
              onChange={val => setForm(prev => ({ ...prev, photo_url: val }))}
              label="Box Photo"
              category="general"
              hint="Upload a photo of this week's box (optional)"
            />
          </div>

          <label style={styles.checkbox}>
            <input
              type="checkbox"
              name="is_published"
              checked={form.is_published}
              onChange={handleChange}
            />
            <span style={{ fontSize: 14, fontWeight: 500, color: '#333' }}>
              Publish immediately (visible to subscribers)
            </span>
          </label>

          <button
            type="submit"
            style={submitting ? styles.submitBtnDisabled : styles.submitBtn}
            disabled={submitting}
          >
            {submitting ? 'Saving...' : 'Save Box Preview'}
          </button>
        </form>

        <div style={styles.previewSidebar}>
          <div style={styles.previewLabel}>Live Preview</div>
          <div style={styles.previewCard}>
            {form.photo_url ? (
              <img src={form.photo_url} style={styles.previewImg} alt="Box preview" onError={e => { e.target.style.display = 'none'; }} />
            ) : (
              <div style={styles.previewImgPlaceholder}>
                <i className="bi bi-camera"></i>
              </div>
            )}
            <div style={styles.previewBody}>
              <div style={styles.previewDate}>
                Week of {formatDate(form.week_of)}
              </div>
              <div style={styles.previewItems}>
                {form.items_description || 'Box contents will appear here...'}
              </div>
              {form.is_published ? (
                <span style={styles.previewPublished}>Published</span>
              ) : (
                <span style={styles.previewDraft}>Draft</span>
              )}
            </div>
          </div>
        </div>
      </div>

      {pastPreviews.length > 0 && (
        <div style={styles.pastPreviews}>
          <h4 style={{ color: '#2d6a4f', marginBottom: 12 }}>
            <i className="bi bi-clock-history me-2"></i>Past Previews
          </h4>
          {pastPreviews.map(p => (
            <div key={p.id} style={styles.pastPreviewItem}>
              <div>
                <strong style={{ color: '#2d6a4f' }}>
                  Week of {new Date(p.week_of).toLocaleDateString()}
                </strong>
                <div style={{ fontSize: 13, color: '#888', marginTop: 2 }}>
                  {p.items_description?.substring(0, 80)}{p.items_description?.length > 80 ? '...' : ''}
                </div>
              </div>
              <span style={p.is_published ? styles.previewPublished : styles.previewDraft}>
                {p.is_published ? 'Published' : 'Draft'}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
