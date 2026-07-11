import { useState, useEffect } from 'react';
import { adminAPI } from '../../api';
import { useAuth } from '../../AuthContext';
import { useSiteConfig } from '../../SiteConfigContext';
import { useSubmit } from '../../hooks/useSubmit';
import { toast, confirmDialog } from '../../components/dialog/dialogService';
import AdminHeader from '../../components/AdminHeader';

export default function AdminEmailSettings() {
  const { user } = useAuth();
  const { refreshConfig: refreshSiteConfig } = useSiteConfig();
  const [config, setConfig] = useState(null);
  const [previewHtml, setPreviewHtml] = useState('');
  const [previewType, setPreviewType] = useState('order_confirmation');
  const { pending: saving, run: runSave } = useSubmit();
  const { pending: switching, run: runSwitch } = useSubmit();

  useEffect(() => {
    if (user?.is_admin) {
      adminAPI.getEmailConfig().then(res => setConfig(res.data));
    }
  }, [user]);

  // Live preview: auto-load when config first arrives and whenever the template
  // type changes (reflects saved settings). The "Save & preview" button applies
  // unsaved edits first. configLoaded (a boolean) keeps this from re-firing on
  // every keystroke into the settings fields.
  const configLoaded = !!config;
  useEffect(() => {
    if (!configLoaded) return;
    let cancelled = false;
    adminAPI.previewEmail(previewType)
      .then(res => { if (!cancelled) setPreviewHtml(res.data.html); })
      .catch(() => { if (!cancelled) setPreviewHtml('<p>Failed to load preview.</p>'); });
    return () => { cancelled = true; };
  }, [previewType, configLoaded]);

  if (!user?.is_admin) return <div className="alert alert-danger">Access Denied</div>;
  if (!config) return <div className="text-center py-5"><div className="spinner-border text-success"></div></div>;

  const update = (field, value) => setConfig({ ...config, [field]: value });

  // The marketplace kill-switch is deliberately EXCLUDED from every bulk
  // save payload (the backend applies per-key partial updates): flipping the
  // entire public site is its own immediate, confirmed action below — it can
  // no longer be silently persisted by "Save Changes" or "Save & preview".
  const _configPayload = () => {
    const { marketplace_enabled, ...rest } = config;
    return rest;
  };

  const save = async (e) => {
    e.preventDefault();
    const res = await runSave(() => adminAPI.updateEmailConfig(_configPayload()),
                              { success: 'Settings saved!' });
    if (res.ok) {
      setConfig(res.data.data);
      refreshSiteConfig();
    }
  };

  const loadPreview = async () => {
    try {
      // Save first so preview reflects current settings
      await adminAPI.updateEmailConfig(_configPayload());
      const res = await adminAPI.previewEmail(previewType);
      setPreviewHtml(res.data.html);
    } catch {
      setPreviewHtml('<p>Failed to load preview.</p>');
      toast('Could not save/preview — check your connection.', { type: 'error' });
    }
  };

  const toggleMarketplace = async (next) => {
    const ok = await confirmDialog(
      next
        ? 'Enable the marketplace for ALL users? This changes the entire public site immediately.'
        : 'Disable the marketplace for ALL users? The public site switches to garden-only mode immediately.',
      { danger: true, confirmText: next ? 'Enable marketplace' : 'Disable marketplace' });
    if (!ok) return;
    const res = await runSwitch(
      () => adminAPI.updateEmailConfig({ marketplace_enabled: next }),
      { success: `Marketplace ${next ? 'enabled' : 'disabled'} site-wide.` });
    if (res.ok) {
      setConfig({ ...config, marketplace_enabled: next });
      refreshSiteConfig();
    }
  };

  const TOGGLES = [
    { key: 'enable_order_confirmation', label: 'Order Confirmations', icon: 'bi-bag-check' },
    { key: 'enable_status_updates', label: 'Status Updates', icon: 'bi-arrow-repeat' },
    { key: 'enable_messages', label: 'Message Alerts', icon: 'bi-chat-dots' },
    { key: 'enable_announcements', label: 'Garden Announcements', icon: 'bi-megaphone' },
    { key: 'enable_subscription_boxes', label: 'Subscription Boxes', icon: 'bi-box-seam' },
    { key: 'enable_harvest_notifications', label: 'Harvest Alerts', icon: 'bi-basket2' },
  ];

  const PREVIEW_TYPES = [
    { value: 'order_confirmation', label: 'Order Confirmation' },
    { value: 'status_update', label: 'Status Update' },
    { value: 'message', label: 'Message Notification' },
    { value: 'announcement', label: 'Garden Announcement' },
    { value: 'harvest_notification', label: 'Harvest Alert' },
  ];

  return (
    <>
      <AdminHeader title="Communication Settings" icon="bi-chat-dots" />

      {/* Platform mode — an IMMEDIATE confirmed action, not a form field. */}
      <div className="card mb-4">
        <div className="card-body">
          <h5 className="fw-bold mb-3"><i className="bi bi-toggles me-2"></i>Platform Features</h5>
          <div className="d-flex align-items-center justify-content-between">
            <div>
              <h6 className="mb-1">Marketplace</h6>
              <p className="text-muted small mb-0">Enable the marketplace for buying and selling produce. When disabled, only garden management features are shown. Changing this takes effect immediately after confirmation.</p>
            </div>
            <div className="form-check form-switch">
              <input className="form-check-input" type="checkbox" role="switch"
                checked={config.marketplace_enabled || false}
                disabled={switching}
                onChange={e => toggleMarketplace(e.target.checked)}
                style={{ width: '3rem', height: '1.5rem' }}
              />
            </div>
          </div>
        </div>
      </div>

      <form onSubmit={save}>
        {/* Branding Section */}
        <div className="card mb-4">
          <div className="card-header"><h5 className="mb-0"><i className="bi bi-palette me-2"></i>Email Branding</h5></div>
          <div className="card-body">
            <div className="row g-3">
              <div className="col-md-6">
                <label className="form-label fw-semibold">Logo URL</label>
                <input type="url" className="form-control" value={config.logo_url}
                  onChange={e => update('logo_url', e.target.value)}
                  placeholder="https://example.com/logo.png" />
                <small className="text-muted">Leave blank to show text header only</small>
              </div>
              <div className="col-md-6">
                <label className="form-label fw-semibold">Header Color</label>
                <div className="d-flex gap-2 align-items-center">
                  <input type="color" className="form-control form-control-color"
                    value={config.header_color}
                    onChange={e => update('header_color', e.target.value)} />
                  <input type="text" className="form-control" style={{ maxWidth: 120 }}
                    value={config.header_color}
                    onChange={e => update('header_color', e.target.value)}
                    maxLength={7} />
                </div>
              </div>
              <div className="col-md-6">
                <label className="form-label fw-semibold">Tagline</label>
                <input type="text" className="form-control" value={config.tagline}
                  onChange={e => update('tagline', e.target.value)}
                  placeholder="Less admin, more garden" maxLength={200} />
              </div>
              <div className="col-md-6">
                <label className="form-label fw-semibold">From Name</label>
                <input type="text" className="form-control" value={config.from_name}
                  onChange={e => update('from_name', e.target.value)}
                  placeholder="YardHarvest" maxLength={100} />
              </div>
              <div className="col-md-6">
                <label className="form-label fw-semibold">Subject Prefix</label>
                <input type="text" className="form-control" value={config.subject_prefix}
                  onChange={e => update('subject_prefix', e.target.value)}
                  placeholder="YardHarvest" maxLength={50} />
                <small className="text-muted">Prepended to all email subjects</small>
              </div>
              <div className="col-12">
                <label className="form-label fw-semibold">Footer Text</label>
                <textarea className="form-control" rows={2} value={config.footer_text}
                  onChange={e => update('footer_text', e.target.value)}
                  placeholder="Custom footer message (optional)" maxLength={1000} />
              </div>
            </div>
          </div>
        </div>

        {/* Notification Toggles */}
        <div className="card mb-4">
          <div className="card-header"><h5 className="mb-0"><i className="bi bi-toggles me-2"></i>Email Notifications</h5></div>
          <div className="card-body">
            {TOGGLES.map(t => (
              <div key={t.key} className="form-check form-switch mb-3">
                <input className="form-check-input" type="checkbox"
                  checked={config[t.key]}
                  onChange={e => update(t.key, e.target.checked)} />
                <label className="form-check-label">
                  <i className={`bi ${t.icon} me-2`}></i>{t.label}
                </label>
              </div>
            ))}
          </div>
        </div>

        {/* SMS Notifications */}
        <div className="card mb-4">
          <div className="card-header"><h5 className="mb-0"><i className="bi bi-telephone me-2"></i>SMS Notifications</h5></div>
          <div className="card-body">
            <p className="text-muted small mb-3">Send SMS notifications to users who opt in. Requires Twilio credentials in environment variables (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER).</p>
            <div className="form-check form-switch mb-3">
              <input className="form-check-input" type="checkbox"
                checked={config.enable_sms_order_confirmation || false}
                onChange={e => update('enable_sms_order_confirmation', e.target.checked)} />
              <label className="form-check-label">
                <i className="bi bi-bag-check me-2"></i>SMS Order Confirmations
              </label>
            </div>
            <div className="form-check form-switch mb-3">
              <input className="form-check-input" type="checkbox"
                checked={config.enable_sms_status_updates || false}
                onChange={e => update('enable_sms_status_updates', e.target.checked)} />
              <label className="form-check-label">
                <i className="bi bi-arrow-repeat me-2"></i>SMS Status Updates
              </label>
            </div>
            <div className="form-check form-switch mb-3">
              <input className="form-check-input" type="checkbox"
                checked={config.enable_sms_messages || false}
                onChange={e => update('enable_sms_messages', e.target.checked)} />
              <label className="form-check-label">
                <i className="bi bi-chat-dots me-2"></i>SMS Message Alerts
              </label>
            </div>
            <div className="form-check form-switch mb-3">
              <input className="form-check-input" type="checkbox"
                checked={config.enable_sms_harvest_notifications || false}
                onChange={e => update('enable_sms_harvest_notifications', e.target.checked)} />
              <label className="form-check-label">
                <i className="bi bi-basket2 me-2"></i>SMS Harvest Alerts
              </label>
            </div>
          </div>
        </div>

        <div className="d-flex gap-2 mb-4">
          <button type="submit" className="btn btn-success" disabled={saving}>
            {saving ? <><span className="spinner-border spinner-border-sm me-2"></span>Saving...</> : <><i className="bi bi-check-lg me-1"></i>Save Changes</>}
          </button>
        </div>
      </form>

      {/* Preview Section */}
      <div className="card mb-4">
        <div className="card-header"><h5 className="mb-0"><i className="bi bi-eye me-2"></i>Email Preview</h5></div>
        <div className="card-body">
          <div className="d-flex gap-2 mb-3">
            <select className="form-select" style={{ maxWidth: 250 }}
              value={previewType} onChange={e => setPreviewType(e.target.value)}>
              {PREVIEW_TYPES.map(p => (
                <option key={p.value} value={p.value}>{p.label}</option>
              ))}
            </select>
            <button type="button" className="btn btn-outline-success" onClick={loadPreview}>
              <i className="bi bi-arrow-clockwise me-1"></i>Save &amp; preview
            </button>
          </div>
          {previewHtml && (
            <div className="border rounded p-0" style={{ maxHeight: 600, overflow: 'auto' }}>
              <iframe
                srcDoc={previewHtml}
                title="Email Preview"
                style={{ width: '100%', height: 500, border: 'none' }}
                sandbox=""
              />
            </div>
          )}
        </div>
      </div>
    </>
  );
}
