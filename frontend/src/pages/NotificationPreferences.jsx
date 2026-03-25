import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { notificationsAPI } from '../api';

export default function NotificationPreferences() {
  const [prefs, setPrefs] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    notificationsAPI.preferences().then(res => {
      setPrefs(res.data);
      setLoading(false);
    }).catch(() => { setLoading(false); setError('Failed to load preferences.'); });
  }, []);

  const toggle = (field) => {
    setPrefs(prev => ({ ...prev, [field]: !prev[field] }));
  };

  const save = async () => {
    setSaving(true);
    setSuccess('');
    setError('');
    try {
      await notificationsAPI.updatePreferences(prefs);
      setSuccess('Preferences saved!');
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to save preferences.');
    }
    setSaving(false);
  };

  if (loading) return <div className="text-center py-5"><div className="spinner-border text-success"></div></div>;

  return (
    <>
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h1><i className="bi bi-bell me-2"></i>Notification Preferences</h1>
        <Link to="/profile/edit" className="btn btn-outline-secondary btn-sm"><i className="bi bi-arrow-left me-1"></i>Back to Profile</Link>
      </div>

      {error && <div className="alert alert-danger py-2"><i className="bi bi-exclamation-triangle me-2"></i>{error}</div>}
      {success && <div className="alert alert-success py-2"><i className="bi bi-check-circle me-2"></i>{success}</div>}

      {prefs && (
        <>
          {/* Email Notifications */}
          <div className="card mb-4">
            <div className="card-header"><i className="bi bi-envelope me-2"></i><strong>Email Notifications</strong></div>
            <div className="card-body">
              {[
                { field: 'email_order_updates', label: 'Order updates', desc: 'Confirmation emails when you place or receive orders, and status changes' },
                { field: 'email_messages', label: 'Direct messages', desc: 'Email when someone sends you a message on the platform' },
                { field: 'email_harvest_alerts', label: 'Harvest alerts', desc: 'Notifications when crops you follow are being harvested' },
                { field: 'email_garden_announcements', label: 'Garden announcements', desc: 'Updates and announcements from gardens you belong to' },
              ].map(({ field, label, desc }) => (
                <div key={field} className="d-flex justify-content-between align-items-center py-2 border-bottom">
                  <div>
                    <div className="fw-semibold">{label}</div>
                    <small className="text-muted">{desc}</small>
                  </div>
                  <div className="form-check form-switch">
                    <input className="form-check-input" type="checkbox" role="switch" checked={prefs[field] ?? true} onChange={() => toggle(field)} />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* SMS Notifications */}
          <div className="card mb-4">
            <div className="card-header"><i className="bi bi-phone me-2"></i><strong>SMS Notifications</strong></div>
            <div className="card-body">
              <div className="d-flex justify-content-between align-items-center py-2 border-bottom">
                <div>
                  <div className="fw-semibold">Enable SMS notifications</div>
                  <small className="text-muted">Receive text messages for order updates, harvest alerts, and important reminders</small>
                </div>
                <div className="form-check form-switch">
                  <input className="form-check-input" type="checkbox" role="switch" checked={prefs.sms_opt_in || false} onChange={() => toggle('sms_opt_in')} />
                </div>
              </div>

              {prefs.sms_opt_in && (
                <div className="mt-3">
                  <label className="form-label fw-semibold">Phone number</label>
                  <input
                    type="tel"
                    className="form-control"
                    style={{ maxWidth: '300px' }}
                    placeholder="+1 (555) 123-4567"
                    value={prefs.phone_number || ''}
                    onChange={e => setPrefs(prev => ({ ...prev, phone_number: e.target.value }))}
                  />
                  <small className="text-muted">Standard messaging rates may apply. You can opt out anytime.</small>
                </div>
              )}
            </div>
          </div>

          {/* Info Box */}
          <div className="card mb-4 border-success">
            <div className="card-body py-3" style={{ backgroundColor: '#f0f9f4' }}>
              <div className="d-flex align-items-start">
                <i className="bi bi-info-circle text-success me-2 mt-1"></i>
                <div>
                  <small className="text-muted">
                    <strong>Note:</strong> Security and account emails (password resets, payment confirmations) are always sent regardless of these preferences.
                    Platform-wide notification settings are managed by the site administrator.
                  </small>
                </div>
              </div>
            </div>
          </div>

          <button className="btn btn-success" onClick={save} disabled={saving}>
            {saving ? <><span className="spinner-border spinner-border-sm me-2"></span>Saving...</> : <><i className="bi bi-check-lg me-2"></i>Save Preferences</>}
          </button>
        </>
      )}
    </>
  );
}
