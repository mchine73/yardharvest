import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation, Trans } from 'react-i18next';
import SmsConsentNote from '../components/SmsConsentNote';
import { profileAPI, authAPI } from '../api';
import { useAuth } from '../AuthContext';
import { currentLocale } from '../i18n/dates';

const MAX_IMAGE_MB = 4;
const MAX_IMAGE_BYTES = MAX_IMAGE_MB * 1024 * 1024;

export default function EditProfile() {
  const { t } = useTranslation();
  const { user, fetchUser } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    display_name: user?.display_name || '',
    bio: user?.bio || '',
    gardening_story: user?.gardening_story || '',
    years_gardening: user?.years_gardening || '',
    address: user?.address || '',
    city: user?.city || '',
    state: user?.state || '',
    zip_code: user?.zip_code || '',
    phone_number: user?.phone_number || '',
    sms_opt_in: user?.sms_opt_in || false,
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  // Email change (verified via link sent to the new address)
  const [newEmail, setNewEmail] = useState('');
  const [emailPassword, setEmailPassword] = useState('');
  const [emailMsg, setEmailMsg] = useState('');
  const [emailError, setEmailError] = useState('');
  const [emailSending, setEmailSending] = useState(false);

  const submitEmailChange = async (e) => {
    e.preventDefault();
    setEmailMsg('');
    setEmailError('');
    setEmailSending(true);
    try {
      await authAPI.requestEmailChange(newEmail.trim(), emailPassword);
      setEmailMsg(t('profile.emailSent', { email: newEmail.trim().toLowerCase() }));
      setNewEmail('');
      setEmailPassword('');
    } catch (err) {
      setEmailError(err.response?.data?.error || t('profile.errEmailSend'));
    } finally {
      setEmailSending(false);
    }
  };

  const handleChange = (e) => setForm({ ...form, [e.target.name]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setError('');

    // Client-side image size validation
    const imageFields = ['profile_image', 'gallery_image_1', 'gallery_image_2', 'gallery_image_3'];
    const imageLabels = {
      profile_image: t('profile.profileImage'),
      gallery_image_1: t('profile.galleryImage', { n: 1 }),
      gallery_image_2: t('profile.galleryImage', { n: 2 }),
      gallery_image_3: t('profile.galleryImage', { n: 3 }),
    };
    for (const name of imageFields) {
      const file = e.target.elements[name]?.files[0];
      if (file && file.size > MAX_IMAGE_BYTES) {
        const size = (file.size / (1024 * 1024)).toLocaleString(currentLocale(), { minimumFractionDigits: 1, maximumFractionDigits: 1 });
        setError(t('profile.errImageTooLarge', { field: imageLabels[name], size, max: MAX_IMAGE_MB }));
        return;
      }
    }

    setSaving(true);
    const fd = new FormData();
    Object.entries(form).forEach(([k, v]) => fd.append(k, v));
    imageFields.forEach(name => {
      const file = e.target.elements[name]?.files[0];
      if (file) fd.append(name, file);
    });
    try {
      await profileAPI.update(fd);
      await fetchUser();
      navigate(`/profile/${user.public_id}`);
    } catch (err) {
      setError(err.response?.data?.error || t('profile.errUpdate'));
      setSaving(false);
    }
  };

  if (!user) return <p>{t('profile.pleaseLogIn')}</p>;

  return (
    <div className="row justify-content-center">
      <div className="col-md-8">
        <h2 className="mb-3"><i className="bi bi-pencil me-2"></i>{t('profile.title')}</h2>
        <p className="text-muted mb-4">{t('profile.intro')}</p>

        {error && <div className="alert alert-danger"><i className="bi bi-exclamation-triangle me-2"></i>{error}</div>}

        <form onSubmit={submit}>
          <div className="row g-3">
            <div className="col-md-6"><label className="form-label">{t('profile.displayName')}</label><input className="form-control" name="display_name" value={form.display_name} onChange={handleChange} /></div>
            <div className="col-md-6"><label className="form-label">{t('profile.yearsGardening')}</label><input type="number" className="form-control" name="years_gardening" value={form.years_gardening} onChange={handleChange} /></div>
            <div className="col-12"><label className="form-label">{t('profile.bio')}</label><textarea className="form-control" name="bio" rows={2} value={form.bio} onChange={handleChange} placeholder={t('profile.bioPlaceholder')} /></div>
            <div className="col-12">
              <label className="form-label">{t('profile.gardeningStory')}</label>
              <textarea className="form-control" name="gardening_story" rows={4} value={form.gardening_story} onChange={handleChange}
                placeholder={t('profile.storyPlaceholder')} />
            </div>
            <div className="col-md-6"><label className="form-label">{t('profile.address')}</label><input className="form-control" name="address" value={form.address} onChange={handleChange} /></div>
            <div className="col-md-3"><label className="form-label">{t('profile.city')}</label><input className="form-control" name="city" value={form.city} onChange={handleChange} /></div>
            <div className="col-md-1"><label className="form-label">{t('profile.state')}</label><input className="form-control" name="state" value={form.state} onChange={handleChange} /></div>
            <div className="col-md-2"><label className="form-label">{t('profile.zip')}</label><input className="form-control" name="zip_code" value={form.zip_code} onChange={handleChange} /></div>
            <div className="col-12"><hr /></div>
            <div className="col-md-6">
              <label className="form-label"><i className="bi bi-telephone me-1"></i>{t('profile.phoneNumber')}</label>
              <input className="form-control" name="phone_number" type="tel" value={form.phone_number} onChange={handleChange} placeholder="+1 (555) 555-5555" />
              <small className="text-muted">{t('profile.phoneHelp')}</small>
            </div>
            <div className="col-md-6 d-flex align-items-end">
              <div className="form-check form-switch">
                <input className="form-check-input" type="checkbox" id="smsOptIn"
                  checked={form.sms_opt_in}
                  onChange={e => setForm({ ...form, sms_opt_in: e.target.checked })} />
                <label className="form-check-label" htmlFor="smsOptIn">{t('profile.smsOptIn')}</label>
                <br /><small className="text-muted">{t('profile.smsOptInHelp')}</small>
              </div>
            </div>
            <div className="col-12">
              <SmsConsentNote />
            </div>
            <div className="col-12"><hr /><p className="text-muted small mb-2"><i className="bi bi-camera me-1"></i>{t('profile.imagesNote', { max: MAX_IMAGE_MB })}</p></div>
            <div className="col-md-6"><label className="form-label">{t('profile.profileImage')}</label><input type="file" className="form-control" name="profile_image" accept="image/*" /></div>
            <div className="col-md-6"><label className="form-label">{t('profile.galleryImage', { n: 1 })}</label><input type="file" className="form-control" name="gallery_image_1" accept="image/*" /></div>
            <div className="col-md-6"><label className="form-label">{t('profile.galleryImage', { n: 2 })}</label><input type="file" className="form-control" name="gallery_image_2" accept="image/*" /></div>
            <div className="col-md-6"><label className="form-label">{t('profile.galleryImage', { n: 3 })}</label><input type="file" className="form-control" name="gallery_image_3" accept="image/*" /></div>
          </div>
          <button type="submit" className="btn btn-success mt-3" disabled={saving}>{saving ? t('profile.saving') : t('profile.saveProfile')}</button>
        </form>

        {/* Account Email (change requires verification of the new address) */}
        <div className="card mt-4 mb-4">
          <div className="card-body">
            <h5 className="mb-1"><i className="bi bi-envelope-at me-2"></i>{t('profile.accountEmail')}</h5>
            <p className="text-muted small mb-3">
              <Trans i18nKey="profile.emailIntro" values={{ email: user.email }} components={{ b: <strong /> }} />
            </p>
            {emailMsg && <div className="alert alert-success py-2"><i className="bi bi-check-circle me-2"></i>{emailMsg}</div>}
            {emailError && <div className="alert alert-danger py-2"><i className="bi bi-exclamation-triangle me-2"></i>{emailError}</div>}
            <form onSubmit={submitEmailChange}>
              <div className="row g-3">
                <div className="col-md-6">
                  <label className="form-label">{t('profile.newEmail')}</label>
                  <input type="email" className="form-control" value={newEmail} required
                    onChange={e => setNewEmail(e.target.value)} placeholder={t('common.emailPlaceholder')} autoComplete="email" />
                </div>
                <div className="col-md-6">
                  <label className="form-label">{t('profile.currentPassword')}</label>
                  <input type="password" className="form-control" value={emailPassword} required
                    onChange={e => setEmailPassword(e.target.value)} autoComplete="current-password" />
                </div>
              </div>
              <button type="submit" className="btn btn-outline-success mt-3" disabled={emailSending || !newEmail || !emailPassword}>
                {emailSending ? <span className="spinner-border spinner-border-sm me-2"></span> : <i className="bi bi-send me-2"></i>}
                {t('profile.sendVerification')}
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
