import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { gardensAPI } from '../../api';
import { useAuth } from '../../AuthContext';
import { useTranslation } from 'react-i18next';
import PhotoUploadInput from '../../components/PhotoUploadInput';
import { toast } from '../../components/dialog/dialogService';
import { trackEvent } from '../../hooks/useTracking';

export default function CreateGarden() {
  const { t } = useTranslation();
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
      trackEvent('garden_created', { garden_id: res.data.public_id });
      toast("Garden created! Here's your dashboard.", { type: 'success' });
      navigate(`/gardens/${res.data.public_id}/admin`);
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

  const stepTitles = [t('upload.stepBasicInfo'), t('upload.stepLocation'),
                      t('upload.stepSeasonRules'), t('upload.stepPlotSetup')];

  return (
    <div style={{ maxWidth: '700px', margin: '0 auto' }}>
      <Link to="/gardens" style={{ color: 'var(--brand-secondary)', textDecoration: 'none', fontSize: '0.9rem' }}>
        <i className="bi bi-arrow-left me-1"></i> {t('organizer.backToGardens')}
      </Link>

      <h2 className="fw-bold mt-3 mb-4" style={{ color: 'var(--brand-secondary)' }}>
        <i className="bi bi-tree me-2"></i>{t('organizer.createTitle')}
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
              {t('upload.stepLabel', { number: i + 1, title })}
            </span>
          </div>
        ))}
      </div>

      {error && <div className="alert alert-danger">{error}</div>}

      {/* Step 1: Basic Info */}
      {step === 1 && (
        <div className="card" style={{ border: 'none', boxShadow: '0 2px 12px rgba(0,0,0,0.08)' }}>
          <div className="card-body p-4">
            <h5 className="fw-bold mb-3"><i className="bi bi-info-circle me-2"></i>{t('organizer.basicInfo')}</h5>
            <div className="mb-3">
              <label className="form-label fw-semibold">{t('organizer.gardenName')} *</label>
              <input type="text" className="form-control form-control-lg" placeholder="e.g. Hanscom Park Community Garden"
                value={form.name} onChange={e => update('name', e.target.value)} />
            </div>
            <div className="mb-3">
              <label className="form-label fw-semibold">{t('garden.description')}</label>
              <textarea className="form-control" rows="4" placeholder={t('organizer.descriptionPlaceholderGarden')}
                value={form.description} onChange={e => update('description', e.target.value)} />
            </div>
            <PhotoUploadInput
              value={form.photo_url}
              onChange={val => update('photo_url', val)}
              label={t('upload.gardenPhoto')}
              category="garden"
              hint={t('upload.gardenPhotoHint')}
            />
            <div className="d-flex justify-content-end">
              <button className="btn btn-lg" style={{ backgroundColor: 'var(--brand-secondary)', color: 'white' }}
                onClick={() => setStep(2)}>
                {t('organizer.nextLocation')} <i className="bi bi-arrow-right ms-2"></i>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Step 2: Location */}
      {step === 2 && (
        <div className="card" style={{ border: 'none', boxShadow: '0 2px 12px rgba(0,0,0,0.08)' }}>
          <div className="card-body p-4">
            <h5 className="fw-bold mb-3"><i className="bi bi-geo-alt me-2"></i>{t('organizer.locationModel')}</h5>
            <div className="mb-3">
              <label className="form-label fw-semibold">{t('organizer.streetAddress')}</label>
              <input type="text" className="form-control" placeholder="123 Garden St"
                value={form.address} onChange={e => update('address', e.target.value)} />
            </div>
            <div className="row g-3 mb-3">
              <div className="col-md-5">
                <label className="form-label fw-semibold">{t('organizer.city')} <span className="text-danger">*</span></label>
                <input type="text" className="form-control" placeholder="e.g. Portland" value={form.city} onChange={e => update('city', e.target.value)} />
              </div>
              <div className="col-md-3">
                <label className="form-label fw-semibold">{t('organizer.state')} <span className="text-danger">*</span></label>
                <input type="text" className="form-control" placeholder="e.g. OR" value={form.state} onChange={e => update('state', e.target.value)} />
              </div>
              <div className="col-md-4">
                <label className="form-label fw-semibold">{t('organizer.zipCode')}</label>
                <input type="text" className="form-control" value={form.zip_code} onChange={e => update('zip_code', e.target.value)} />
              </div>
            </div>
            <div className="mb-3">
              <label className="form-label fw-semibold">{t('garden.operatingModel')}</label>
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
                <i className="bi bi-arrow-left me-2"></i>{t('organizer.back')}
              </button>
              <button className="btn btn-lg" style={{ backgroundColor: 'var(--brand-secondary)', color: 'white' }}
                onClick={() => setStep(3)}>
                {t('organizer.nextSeason')} <i className="bi bi-arrow-right ms-2"></i>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Step 3: Season & Rules */}
      {step === 3 && (
        <div className="card" style={{ border: 'none', boxShadow: '0 2px 12px rgba(0,0,0,0.08)' }}>
          <div className="card-body p-4">
            <h5 className="fw-bold mb-3"><i className="bi bi-calendar me-2"></i>{t('organizer.seasonFeesRules')}</h5>
            <div className="row g-3 mb-3">
              <div className="col-md-6">
                <label className="form-label fw-semibold">{t('organizer.seasonStart')}</label>
                <input type="date" className="form-control" value={form.season_start}
                  onChange={e => update('season_start', e.target.value)} />
              </div>
              <div className="col-md-6">
                <label className="form-label fw-semibold">{t('organizer.seasonEnd')}</label>
                <input type="date" className="form-control" value={form.season_end}
                  onChange={e => update('season_end', e.target.value)} />
              </div>
            </div>
            <div className="row g-3 mb-3">
              <div className="col-md-6">
                <label className="form-label fw-semibold">{t('garden.annualPlotFee')}</label>
                <div className="input-group">
                  <span className="input-group-text">$</span>
                  <input type="number" className="form-control" step="1" min="0" inputMode="numeric"
                    value={form.plot_fee_annual} onChange={e => update('plot_fee_annual', parseInt(e.target.value, 10) || 0)} />
                </div>
                <small className="text-muted">{t('organizer.wholeDollars')}</small>
              </div>
              <div className="col-md-6">
                <label className="form-label fw-semibold">{t('organizer.contactEmail')}</label>
                <input type="email" className="form-control" value={form.contact_email}
                  onChange={e => update('contact_email', e.target.value)} />
              </div>
            </div>
            <div className="mb-3">
              <label className="form-label fw-semibold">{t('garden.rules')}</label>
              <textarea className="form-control" rows="5"
                placeholder="1. Water your plot at least twice a week&#10;2. Keep pathways clear&#10;3. Use organic methods only&#10;4. Attend at least 2 workdays per season"
                value={form.rules} onChange={e => update('rules', e.target.value)} />
            </div>
            <div className="d-flex justify-content-between">
              <button className="btn btn-outline-secondary btn-lg" onClick={() => setStep(2)}>
                <i className="bi bi-arrow-left me-2"></i>{t('organizer.back')}
              </button>
              <button className="btn btn-lg" style={{ backgroundColor: 'var(--brand-secondary)', color: 'white' }}
                onClick={() => setStep(4)}>
                {t('organizer.nextPlots')} <i className="bi bi-arrow-right ms-2"></i>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Step 4: Plot Setup & Preview */}
      {step === 4 && (
        <div className="card" style={{ border: 'none', boxShadow: '0 2px 12px rgba(0,0,0,0.08)' }}>
          <div className="card-body p-4">
            <h5 className="fw-bold mb-3"><i className="bi bi-grid-3x3-gap me-2"></i>{t('organizer.initialPlots')}</h5>
            <p className="text-muted mb-3">{t('organizer.initialPlotsHelp')}</p>
            <div className="row g-3 mb-4">
              <div className="col-md-6">
                <label className="form-label fw-semibold">{t('organizer.numberOfPlots')}</label>
                <input type="number" className="form-control form-control-lg" min="0" max="100"
                  value={form.bulk_plot_count} onChange={e => update('bulk_plot_count', parseInt(e.target.value) || 0)} />
              </div>
              <div className="col-md-6">
                <label className="form-label fw-semibold">{t('organizer.defaultPlotSize')}</label>
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
              <h6 className="fw-bold mb-3"><i className="bi bi-eye me-2"></i>{t('organizer.preview')}</h6>
              <div className="row g-2">
                <div className="col-6">
                  <div className="small text-muted">{t('garden.name')}</div>
                  <div className="fw-semibold">{form.name || '-'}</div>
                </div>
                <div className="col-6">
                  <div className="small text-muted">{t('organizer.model')}</div>
                  <div className="fw-semibold" style={{ textTransform: 'capitalize' }}>{form.operating_model}</div>
                </div>
                <div className="col-6">
                  <div className="small text-muted">{t('organizer.location')}</div>
                  <div className="fw-semibold">{form.city}, {form.state}</div>
                </div>
                <div className="col-6">
                  <div className="small text-muted">{t('garden.tabPlots')}</div>
                  <div className="fw-semibold">{form.bulk_plot_count} x {form.bulk_plot_size}</div>
                </div>
                <div className="col-6">
                  <div className="small text-muted">{t('organizer.annualFee')}</div>
                  <div className="fw-semibold">{form.plot_fee_annual > 0 ? `$${Math.round(form.plot_fee_annual)}` : 'Free'}</div>
                </div>
                <div className="col-6">
                  <div className="small text-muted">{t('garden.season')}</div>
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
                <i className="bi bi-arrow-left me-2"></i>{t('organizer.back')}
              </button>
              <button className="btn btn-lg" style={{ backgroundColor: 'var(--brand-secondary)', color: 'white' }}
                onClick={handleSubmit} disabled={submitting}>
                {submitting ? (
                  <><span className="spinner-border spinner-border-sm me-2"></span>{t('organizer.creating')}</>
                ) : (
                  <><i className="bi bi-check-circle me-2"></i>{t('gardensList.createGardenShort')}</>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
