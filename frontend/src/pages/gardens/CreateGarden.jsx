import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { gardensAPI } from '../../api';
import { useAuth } from '../../AuthContext';
import PhotoUploadInput from '../../components/PhotoUploadInput';

export default function CreateGarden() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const [form, setForm] = useState({
    name: '',
    description: '',
    photo_url: '',
    address: '',
    city: '',
    state: '',
    zip_code: '',
    operating_model: 'allotment',
    season_start: '',
    season_end: '',
    plot_fee_annual: 0,
    rules: '',
    contact_email: user?.email || '',
    bulk_plot_count: 10,
    bulk_plot_size: '4x8 ft',
  });

  const update = (field, value) => setForm(prev => ({ ...prev, [field]: value }));

  const handleSubmit = async () => {
    if (!form.name.trim()) {
      setError('Garden name is required');
      setStep(1);
      return;
    }
    if (!form.city.trim() || !form.state.trim()) {
      setError("Please add your garden's city and state so nearby gardeners can find it.");
      setStep(2);
      return;
    }
    setSubmitting(true);
    setError('');
    try {
      const res = await gardensAPI.create(form);
      navigate(`/gardens/${res.data.public_id}`);
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to create garden');
      setSubmitting(false);
    }
  };

  if (!user) {
    return (
      <div className="text-center py-5">
        <p>Please <Link to="/login">log in</Link> to create a garden.</p>
      </div>
    );
  }

  const stepTitles = ['Basic Info', 'Location', 'Season & Rules', 'Plot Setup'];

  return (
    <div style={{ maxWidth: '700px', margin: '0 auto' }}>
      <Link to="/gardens" style={{ color: 'var(--brand-secondary)', textDecoration: 'none', fontSize: '0.9rem' }}>
        <i className="bi bi-arrow-left me-1"></i> Back to Gardens
      </Link>

      <h2 className="fw-bold mt-3 mb-4" style={{ color: 'var(--brand-secondary)' }}>
        <i className="bi bi-tree me-2"></i>Create a Community Garden
      </h2>

      {/* Progress Steps */}
      <div style={{ display: 'flex', gap: '4px', marginBottom: '32px' }}>
        {stepTitles.map((title, i) => (
          <div key={i} style={{ flex: 1, textAlign: 'center' }}>
            <div style={{
              height: '4px', borderRadius: '2px',
              backgroundColor: i + 1 <= step ? 'var(--brand-secondary)' : '#e5e7eb',
              marginBottom: '8px', transition: 'background-color 0.3s',
            }}></div>
            <span style={{
              fontSize: '0.8rem', fontWeight: i + 1 === step ? 600 : 400,
              color: i + 1 <= step ? 'var(--brand-secondary)' : '#9ca3af',
            }}>
              Step {i + 1}: {title}
            </span>
          </div>
        ))}
      </div>

      {error && <div className="alert alert-danger">{error}</div>}

      {/* Step 1: Basic Info */}
      {step === 1 && (
        <div className="card" style={{ border: 'none', boxShadow: '0 2px 12px rgba(0,0,0,0.08)' }}>
          <div className="card-body p-4">
            <h5 className="fw-bold mb-3"><i className="bi bi-info-circle me-2"></i>Basic Information</h5>
            <div className="mb-3">
              <label className="form-label fw-semibold">Garden Name *</label>
              <input type="text" className="form-control form-control-lg" placeholder="e.g. Hanscom Park Community Garden"
                value={form.name} onChange={e => update('name', e.target.value)} />
            </div>
            <div className="mb-3">
              <label className="form-label fw-semibold">Description</label>
              <textarea className="form-control" rows="4" placeholder="Describe your garden, its mission, and what makes it special..."
                value={form.description} onChange={e => update('description', e.target.value)} />
            </div>
            <PhotoUploadInput
              value={form.photo_url}
              onChange={val => update('photo_url', val)}
              label="Garden Photo"
              category="garden"
              hint="Upload a photo of your garden (optional)"
            />
            <div className="d-flex justify-content-end">
              <button className="btn btn-lg" style={{ backgroundColor: 'var(--brand-secondary)', color: 'white' }}
                onClick={() => setStep(2)}>
                Next: Location <i className="bi bi-arrow-right ms-2"></i>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Step 2: Location */}
      {step === 2 && (
        <div className="card" style={{ border: 'none', boxShadow: '0 2px 12px rgba(0,0,0,0.08)' }}>
          <div className="card-body p-4">
            <h5 className="fw-bold mb-3"><i className="bi bi-geo-alt me-2"></i>Location & Model</h5>
            <div className="mb-3">
              <label className="form-label fw-semibold">Street Address</label>
              <input type="text" className="form-control" placeholder="123 Garden St"
                value={form.address} onChange={e => update('address', e.target.value)} />
            </div>
            <div className="row g-3 mb-3">
              <div className="col-md-5">
                <label className="form-label fw-semibold">City <span className="text-danger">*</span></label>
                <input type="text" className="form-control" placeholder="e.g. Portland" value={form.city} onChange={e => update('city', e.target.value)} />
              </div>
              <div className="col-md-3">
                <label className="form-label fw-semibold">State <span className="text-danger">*</span></label>
                <input type="text" className="form-control" placeholder="e.g. OR" value={form.state} onChange={e => update('state', e.target.value)} />
              </div>
              <div className="col-md-4">
                <label className="form-label fw-semibold">ZIP Code</label>
                <input type="text" className="form-control" value={form.zip_code} onChange={e => update('zip_code', e.target.value)} />
              </div>
            </div>
            <div className="mb-3">
              <label className="form-label fw-semibold">Operating Model</label>
              <div className="row g-2">
                {[
                  { value: 'allotment', label: 'Allotment', desc: 'Individual plots assigned to gardeners', icon: 'bi-grid-3x3-gap' },
                  { value: 'communal', label: 'Communal', desc: 'Shared growing space, group decisions', icon: 'bi-people' },
                  { value: 'hybrid', label: 'Hybrid', desc: 'Mix of individual plots and shared areas', icon: 'bi-intersect' },
                ].map(model => (
                  <div key={model.value} className="col-md-4">
                    <div
                      style={{
                        border: form.operating_model === model.value ? '2px solid var(--brand-secondary)' : '2px solid #e5e7eb',
                        borderRadius: '12px', padding: '16px', cursor: 'pointer', textAlign: 'center',
                        backgroundColor: form.operating_model === model.value ? 'var(--brand-pale)' : 'white',
                        transition: 'all 0.2s',
                      }}
                      onClick={() => update('operating_model', model.value)}
                    >
                      <i className={`bi ${model.icon}`} style={{ fontSize: '1.5rem', color: 'var(--brand-secondary)' }}></i>
                      <div className="fw-bold mt-1">{model.label}</div>
                      <small className="text-muted">{model.desc}</small>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <div className="d-flex justify-content-between">
              <button className="btn btn-outline-secondary btn-lg" onClick={() => setStep(1)}>
                <i className="bi bi-arrow-left me-2"></i>Back
              </button>
              <button className="btn btn-lg" style={{ backgroundColor: 'var(--brand-secondary)', color: 'white' }}
                onClick={() => setStep(3)}>
                Next: Season & Rules <i className="bi bi-arrow-right ms-2"></i>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Step 3: Season & Rules */}
      {step === 3 && (
        <div className="card" style={{ border: 'none', boxShadow: '0 2px 12px rgba(0,0,0,0.08)' }}>
          <div className="card-body p-4">
            <h5 className="fw-bold mb-3"><i className="bi bi-calendar me-2"></i>Season, Fees & Rules</h5>
            <div className="row g-3 mb-3">
              <div className="col-md-6">
                <label className="form-label fw-semibold">Season Start</label>
                <input type="date" className="form-control" value={form.season_start}
                  onChange={e => update('season_start', e.target.value)} />
              </div>
              <div className="col-md-6">
                <label className="form-label fw-semibold">Season End</label>
                <input type="date" className="form-control" value={form.season_end}
                  onChange={e => update('season_end', e.target.value)} />
              </div>
            </div>
            <div className="row g-3 mb-3">
              <div className="col-md-6">
                <label className="form-label fw-semibold">Annual Plot Fee</label>
                <div className="input-group">
                  <span className="input-group-text">$</span>
                  <input type="number" className="form-control" step="1" min="0" inputMode="numeric"
                    value={form.plot_fee_annual} onChange={e => update('plot_fee_annual', parseInt(e.target.value, 10) || 0)} />
                </div>
                <small className="text-muted">Whole dollars. Set to 0 for free plots.</small>
              </div>
              <div className="col-md-6">
                <label className="form-label fw-semibold">Contact Email</label>
                <input type="email" className="form-control" value={form.contact_email}
                  onChange={e => update('contact_email', e.target.value)} />
              </div>
            </div>
            <div className="mb-3">
              <label className="form-label fw-semibold">Garden Rules</label>
              <textarea className="form-control" rows="5"
                placeholder="1. Water your plot at least twice a week&#10;2. Keep pathways clear&#10;3. Use organic methods only&#10;4. Attend at least 2 workdays per season"
                value={form.rules} onChange={e => update('rules', e.target.value)} />
            </div>
            <div className="d-flex justify-content-between">
              <button className="btn btn-outline-secondary btn-lg" onClick={() => setStep(2)}>
                <i className="bi bi-arrow-left me-2"></i>Back
              </button>
              <button className="btn btn-lg" style={{ backgroundColor: 'var(--brand-secondary)', color: 'white' }}
                onClick={() => setStep(4)}>
                Next: Plot Setup <i className="bi bi-arrow-right ms-2"></i>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Step 4: Plot Setup & Preview */}
      {step === 4 && (
        <div className="card" style={{ border: 'none', boxShadow: '0 2px 12px rgba(0,0,0,0.08)' }}>
          <div className="card-body p-4">
            <h5 className="fw-bold mb-3"><i className="bi bi-grid-3x3-gap me-2"></i>Initial Plot Setup</h5>
            <p className="text-muted mb-3">Set up the initial garden plots. You can always add more later.</p>
            <div className="row g-3 mb-4">
              <div className="col-md-6">
                <label className="form-label fw-semibold">Number of Plots</label>
                <input type="number" className="form-control form-control-lg" min="0" max="100"
                  value={form.bulk_plot_count} onChange={e => update('bulk_plot_count', parseInt(e.target.value) || 0)} />
              </div>
              <div className="col-md-6">
                <label className="form-label fw-semibold">Default Plot Size</label>
                <select className="form-select form-select-lg" value={form.bulk_plot_size}
                  onChange={e => update('bulk_plot_size', e.target.value)}>
                  <option value="4x4 ft">4x4 ft (Small)</option>
                  <option value="4x8 ft">4x8 ft (Standard)</option>
                  <option value="10x10 ft">10x10 ft (Large)</option>
                  <option value="10x20 ft">10x20 ft (Extra Large)</option>
                </select>
              </div>
            </div>

            {/* Preview */}
            <div style={{ backgroundColor: '#f8f9fa', borderRadius: '12px', padding: '24px', marginBottom: '24px' }}>
              <h6 className="fw-bold mb-3"><i className="bi bi-eye me-2"></i>Garden Preview</h6>
              <div className="row g-2">
                <div className="col-6">
                  <div className="small text-muted">Name</div>
                  <div className="fw-semibold">{form.name || '-'}</div>
                </div>
                <div className="col-6">
                  <div className="small text-muted">Model</div>
                  <div className="fw-semibold" style={{ textTransform: 'capitalize' }}>{form.operating_model}</div>
                </div>
                <div className="col-6">
                  <div className="small text-muted">Location</div>
                  <div className="fw-semibold">{form.city}, {form.state}</div>
                </div>
                <div className="col-6">
                  <div className="small text-muted">Plots</div>
                  <div className="fw-semibold">{form.bulk_plot_count} x {form.bulk_plot_size}</div>
                </div>
                <div className="col-6">
                  <div className="small text-muted">Annual Fee</div>
                  <div className="fw-semibold">{form.plot_fee_annual > 0 ? `$${Math.round(form.plot_fee_annual)}` : 'Free'}</div>
                </div>
                <div className="col-6">
                  <div className="small text-muted">Season</div>
                  <div className="fw-semibold">
                    {form.season_start
                      ? `${new Date(form.season_start + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} - ${form.season_end ? new Date(form.season_end + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : '?'}`
                      : 'Not set'}
                  </div>
                </div>
              </div>
            </div>

            <div className="d-flex justify-content-between">
              <button className="btn btn-outline-secondary btn-lg" onClick={() => setStep(3)}>
                <i className="bi bi-arrow-left me-2"></i>Back
              </button>
              <button className="btn btn-lg" style={{ backgroundColor: 'var(--brand-secondary)', color: 'white' }}
                onClick={handleSubmit} disabled={submitting}>
                {submitting ? (
                  <><span className="spinner-border spinner-border-sm me-2"></span>Creating...</>
                ) : (
                  <><i className="bi bi-check-circle me-2"></i>Create Garden</>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
