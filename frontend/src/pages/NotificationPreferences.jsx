import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { notificationsAPI } from '../api';
import SmsConsentNote from '../components/SmsConsentNote';
import { useTranslation } from 'react-i18next';

export default function NotificationPreferences() {
  const { t } = useTranslation();
  const [prefs, setPrefs] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    notificationsAPI.preferences().then(res => {
      setPrefs(res.data);
      setLoading(false);
    }).catch(() => { setLoading(false); setError(t('notificationPreferences.loadFailed')); });
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
      setSuccess(t('notificationPreferences.saved'));
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError(err.response?.data?.error || t('notificationPreferences.saveFailed'));
    }
    setSaving(false);
  };

  if (loading) return <div className="text-center py-5"><div className="spinner-border text-success"></div></div>;

  return (
    <>
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h1><i className="bi bi-bell me-2"></i>{t('notificationPreferences.title')}</h1>
        <Link to="/profile/edit" className="btn btn-outline-secondary btn-sm"><i className="bi bi-arrow-left me-1"></i>{t('notificationPreferences.backToProfile')}</Link>
      </div>

      {error && <div className="alert alert-danger py-2"><i className="bi bi-exclamation-triangle me-2"></i>{error}</div>}
      {success && <div className="alert alert-success py-2"><i className="bi bi-check-circle me-2"></i>{success}</div>}

      {prefs && (
        <>
          {/* Email Notifications */}
          <div className="card mb-4">
            <div className="card-header"><i className="bi bi-envelope me-2"></i><strong>{t('notificationPreferences.emailHeading')}</strong></div>
            <div className="card-body">
              {[
                { field: 'email_order_updates', label: t('notificationPreferences.orderUpdates'), desc: t('notificationPreferences.orderUpdatesHelp') },
                { field: 'email_messages', label: t('notificationPreferences.directMessages'), desc: t('notificationPreferences.directMessagesHelp') },
                { field: 'email_harvest_alerts', label: t('notificationPreferences.harvestAlerts'), desc: t('notificationPreferences.harvestAlertsHelp') },
                { field: 'email_garden_announcements', label: t('notificationPreferences.gardenAnnouncements'), desc: t('notificationPreferences.gardenAnnouncementsHelp') },
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
            <div className="card-header"><i className="bi bi-phone me-2"></i><strong>{t('notificationPreferences.smsHeading')}</strong></div>
            <div className="card-body">
              <div className="d-flex justify-content-between align-items-center py-2 border-bottom">
                <div>
                  <div className="fw-semibold">{t('notificationPreferences.smsEnable')}</div>
                  <small className="text-muted">{t('notificationPreferences.smsEnableHelp')}</small>
                </div>
                <div className="form-check form-switch">
                  <input className="form-check-input" type="checkbox" role="switch" checked={prefs.sms_opt_in || false} onChange={() => toggle('sms_opt_in')} />
                </div>
              </div>

              {prefs.sms_opt_in && (
                <div className="mt-3">
                  <label className="form-label fw-semibold">{t('notificationPreferences.phoneNumber')}</label>
                  <input
                    type="tel"
                    className="form-control"
                    style={{ maxWidth: '300px' }}
                    placeholder="+1 (555) 123-4567"
                    value={prefs.phone_number || ''}
                    onChange={e => setPrefs(prev => ({ ...prev, phone_number: e.target.value }))}
                  />
                  <SmsConsentNote className="mt-2" />
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
                    <strong>{t('notificationPreferences.noteLabel')}</strong> {t('notificationPreferences.noteBody')}
                    Platform-wide notification settings are managed by the site administrator.
                  </small>
                </div>
              </div>
            </div>
          </div>

          <button className="btn btn-success" onClick={save} disabled={saving}>
            {saving ? <><span className="spinner-border spinner-border-sm me-2"></span>{t('notificationPreferences.submitting')}</> : <><i className="bi bi-check-lg me-2"></i>{t('notificationPreferences.submit')}</>}
          </button>
        </>
      )}
    </>
  );
}
