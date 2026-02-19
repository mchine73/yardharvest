import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { groupsAPI } from '../api';
import { useAuth } from '../AuthContext';

const NEIGHBORHOODS = [
  'Dundee', 'Benson', 'Blackstone', 'Aksarben', 'Midtown',
  'Elkhorn', 'Papillion', 'Ralston', 'Florence', 'Little Italy',
];

export default function CreateGroup() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    name: '',
    description: '',
    neighborhood: '',
    zip_code: '',
    cover_photo_url: '',
    is_public: true,
  });
  const [preview, setPreview] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  if (!user) {
    return (
      <div className="text-center py-5">
        <p>Please <Link to="/login">log in</Link> to create a group.</p>
      </div>
    );
  }

  const handleChange = (field, value) => {
    setForm({ ...form, [field]: value });
  };

  const handleSubmit = async () => {
    if (!form.name.trim()) {
      setError('Group name is required');
      return;
    }
    setSubmitting(true);
    setError('');
    try {
      const res = await groupsAPI.create(form);
      navigate(`/groups/${res.data.id}`);
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to create group');
      setSubmitting(false);
    }
  };

  const s = {
    page: { maxWidth: 720, margin: '0 auto' },
    header: {
      marginBottom: 32,
    },
    title: { fontSize: 28, fontWeight: 700, color: '#1b4332', marginBottom: 8 },
    subtitle: { color: '#666', fontSize: 15 },
    card: {
      backgroundColor: '#fff',
      border: '1px solid #e0e0e0',
      borderRadius: 16,
      padding: 32,
      marginBottom: 24,
    },
    label: {
      display: 'block',
      fontSize: 14,
      fontWeight: 600,
      color: '#1b4332',
      marginBottom: 6,
    },
    hint: { fontSize: 12, color: '#888', marginTop: 4, marginBottom: 16 },
    toggleContainer: {
      display: 'flex',
      gap: 12,
      marginBottom: 16,
    },
    toggleBtn: (active) => ({
      flex: 1,
      padding: '14px 20px',
      borderRadius: 10,
      border: active ? '2px solid #2d6a4f' : '1px solid #ddd',
      backgroundColor: active ? '#d8f3dc' : '#fff',
      color: active ? '#2d6a4f' : '#666',
      cursor: 'pointer',
      fontWeight: active ? 700 : 400,
      textAlign: 'center',
      fontSize: 14,
    }),
    previewCard: {
      border: '1px solid #d8f3dc',
      borderRadius: 16,
      overflow: 'hidden',
      marginBottom: 24,
    },
    previewCover: {
      height: 140,
      background: form.cover_photo_url
        ? `url(${form.cover_photo_url}) center/cover`
        : 'linear-gradient(135deg, #95d5b2 0%, #40916c 100%)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
    },
    previewBody: { padding: 24 },
    previewName: { fontSize: 22, fontWeight: 700, color: '#1b4332', marginBottom: 4 },
    previewNeighborhood: { fontSize: 13, color: '#40916c', fontWeight: 600, marginBottom: 8 },
    previewDesc: { fontSize: 14, color: '#555' },
    actions: {
      display: 'flex',
      gap: 12,
      justifyContent: 'flex-end',
    },
  };

  return (
    <div style={s.page}>
      <div style={s.header}>
        <Link to="/groups" style={{ color: '#40916c', textDecoration: 'none', fontSize: 14 }}>
          <i className="bi bi-arrow-left me-1"></i> Back to Groups
        </Link>
        <h1 style={s.title}>
          <i className="bi bi-plus-circle me-2"></i>
          Create a Garden Group
        </h1>
        <p style={s.subtitle}>Start a local gardening community in your Omaha neighborhood.</p>
      </div>

      {error && (
        <div className="alert alert-danger">{error}</div>
      )}

      {!preview ? (
        <>
          <div style={s.card}>
            <label style={s.label}>Group Name *</label>
            <input
              type="text"
              className="form-control mb-1"
              placeholder="e.g., Dundee Gardeners"
              value={form.name}
              onChange={e => handleChange('name', e.target.value)}
              maxLength={120}
            />
            <div style={s.hint}>{form.name.length}/120 characters</div>

            <label style={s.label}>Description</label>
            <textarea
              className="form-control mb-1"
              rows={4}
              placeholder="Tell people about your group. What's your focus? Who should join?"
              value={form.description}
              onChange={e => handleChange('description', e.target.value)}
            />
            <div style={s.hint}>Describe your group's purpose and activities</div>

            <label style={s.label}>Neighborhood</label>
            <select
              className="form-select mb-1"
              value={form.neighborhood}
              onChange={e => handleChange('neighborhood', e.target.value)}
            >
              <option value="">Select a neighborhood...</option>
              {NEIGHBORHOODS.map(n => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
            <div style={s.hint}>Choose an Omaha neighborhood</div>

            <label style={s.label}>ZIP Code</label>
            <input
              type="text"
              className="form-control mb-1"
              placeholder="e.g., 68132"
              value={form.zip_code}
              onChange={e => handleChange('zip_code', e.target.value)}
              maxLength={10}
              style={{ maxWidth: 200 }}
            />
            <div style={s.hint}>Optional but helps with local search</div>

            <label style={s.label}>Cover Photo URL</label>
            <input
              type="url"
              className="form-control mb-1"
              placeholder="https://example.com/photo.jpg"
              value={form.cover_photo_url}
              onChange={e => handleChange('cover_photo_url', e.target.value)}
            />
            <div style={s.hint}>Optional cover image URL for your group</div>

            <label style={s.label}>Visibility</label>
            <div style={s.toggleContainer}>
              <button
                type="button"
                style={s.toggleBtn(form.is_public)}
                onClick={() => handleChange('is_public', true)}
              >
                <i className="bi bi-globe me-2"></i>
                Public
                <div style={{ fontSize: 12, fontWeight: 400, marginTop: 4 }}>Anyone can see and join</div>
              </button>
              <button
                type="button"
                style={s.toggleBtn(!form.is_public)}
                onClick={() => handleChange('is_public', false)}
              >
                <i className="bi bi-lock me-2"></i>
                Private
                <div style={{ fontSize: 12, fontWeight: 400, marginTop: 4 }}>Members only can see posts</div>
              </button>
            </div>
          </div>

          <div style={s.actions}>
            <Link to="/groups" className="btn btn-outline-secondary">Cancel</Link>
            <button
              className="btn btn-success"
              onClick={() => setPreview(true)}
              disabled={!form.name.trim()}
            >
              Preview <i className="bi bi-arrow-right ms-1"></i>
            </button>
          </div>
        </>
      ) : (
        <>
          <h5 style={{ color: '#1b4332', marginBottom: 16, fontWeight: 600 }}>
            <i className="bi bi-eye me-2"></i>Preview
          </h5>
          <div style={s.previewCard}>
            <div style={s.previewCover}>
              {!form.cover_photo_url && (
                <i className="bi bi-flower2" style={{ fontSize: 48, color: 'rgba(255,255,255,0.6)' }}></i>
              )}
            </div>
            <div style={s.previewBody}>
              <div style={s.previewName}>{form.name}</div>
              {form.neighborhood && (
                <div style={s.previewNeighborhood}>
                  <i className="bi bi-geo-alt-fill me-1"></i>
                  {form.neighborhood}, Omaha, NE {form.zip_code}
                </div>
              )}
              <div style={s.previewDesc}>{form.description || 'No description provided.'}</div>
              <div style={{ marginTop: 12, fontSize: 13, color: '#888' }}>
                <i className="bi bi-{form.is_public ? 'globe' : 'lock'} me-1"></i>
                {form.is_public ? 'Public group' : 'Private group'}
              </div>
            </div>
          </div>

          <div style={s.actions}>
            <button
              className="btn btn-outline-secondary"
              onClick={() => setPreview(false)}
            >
              <i className="bi bi-arrow-left me-1"></i> Edit
            </button>
            <button
              className="btn btn-success"
              onClick={handleSubmit}
              disabled={submitting}
            >
              {submitting ? (
                <><span className="spinner-border spinner-border-sm me-2"></span>Creating...</>
              ) : (
                <><i className="bi bi-check-circle me-1"></i> Create Group</>
              )}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
