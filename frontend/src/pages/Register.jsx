import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { trackEvent } from '../hooks/useTracking';
import { useAuth } from '../AuthContext';
import { useSiteConfig } from '../SiteConfigContext';
import { authAPI } from '../api';
import SmsConsentNote from '../components/SmsConsentNote';
import { useTranslation, Trans } from 'react-i18next';

export default function Register() {
  const { t } = useTranslation();
  const { login } = useAuth();
  const { marketplaceEnabled } = useSiteConfig();
  const navigate = useNavigate();

  const [step, setStep] = useState(1);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // Step 1: Account basics
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  // Step 2: Profile info
  const [displayName, setDisplayName] = useState('');
  const [role, setRole] = useState('both');
  const [address, setAddress] = useState('');
  const [city, setCity] = useState('');
  const [state, setState] = useState('');
  const [zipCode, setZipCode] = useState('');
  const [phoneNumber, setPhoneNumber] = useState('');
  const [smsOptIn, setSmsOptIn] = useState(false);

  const validateStep1 = () => {
    if (!username.trim()) return t('register.errUsernameRequired');
    if (username.length < 3) return t('register.errUsernameShort');
    if (!email.trim()) return t('register.errEmailRequired');
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return t('register.errEmailInvalid');
    if (!password) return t('register.errPasswordRequired');
    if (password.length < 6) return t('register.errPasswordShort');
    if (password !== confirmPassword) return t('register.errPasswordMismatch');
    return null;
  };

  const handleNext = () => {
    const err = validateStep1();
    if (err) { setError(err); return; }
    setError('');
    setStep(2);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);

    try {
      await authAPI.register({
        username: username.trim(),
        email: email.trim().toLowerCase(),
        password,
        role,
        display_name: displayName.trim() || username.trim(),
        address: address.trim(),
        city: city.trim(),
        state: state.trim(),
        zip_code: zipCode.trim(),
        phone_number: phoneNumber.trim(),
        sms_opt_in: smsOptIn,
      });
      trackEvent('register_complete', { role });

      // Auto-login after registration
      await login(email.trim().toLowerCase(), password);
      // Route new users straight to their first action by role (default: browse gardens).
      navigate(role === 'manager' ? '/gardens/create' : role === 'gardener' ? '/gardens' : '/');
    } catch (err) {
      setError(
        err.response?.data?.error ||
        err.message ||
        t('register.failed')
      );
    } finally {
      setSubmitting(false);
    }
  };

  // Marketplace ON -> buyer/seller/both. Marketplace HIDDEN -> garden roles only.
  const marketplaceRoles = [
    { value: 'buyer', icon: 'bi-basket2', label: t('register.roleBuyer'), desc: t('register.roleBuyerDesc') },
    { value: 'seller', icon: 'bi-shop', label: t('register.roleSeller'), desc: t('register.roleSellerDesc') },
    { value: 'both', icon: 'bi-arrow-left-right', label: t('register.roleBoth'), desc: t('register.roleBothDesc') },
  ];
  const gardenRoles = [
    { value: 'manager', icon: 'bi-clipboard2-check', label: t('register.roleManager'), desc: t('register.roleManagerDesc') },
    { value: 'gardener', icon: 'bi-flower1', label: t('register.roleGardener'), desc: t('register.roleGardenerDesc') },
  ];
  const roleOptions = marketplaceEnabled ? marketplaceRoles : gardenRoles;

  // Keep the selected role valid for the current option set.
  useEffect(() => {
    setRole(marketplaceEnabled ? 'both' : 'manager');
  }, [marketplaceEnabled]);

  // Funnel: someone landed on the registration form.
  useEffect(() => { trackEvent('register_start'); }, []);

  return (
    <div className="container py-5">
      <div className="row justify-content-center">
        <div className="col-md-6 col-lg-5">
          {/* Header */}
          <div className="text-center mb-4">
            <h1 className="fw-bold fs-2" style={{ color: 'var(--brand-secondary)' }}>
              <img src="/sunflower.svg" alt="" className="me-2" style={{ height: '1.15em', width: '1.15em', borderRadius: '0.22em', verticalAlign: '-0.2em' }} />{t('register.heading')}
            </h1>
            <p className="text-muted">
              {marketplaceEnabled ? t('register.taglineMarketplace') : t('register.tagline')}
            </p>
          </div>

          {/* Step indicator */}
          <div className="d-flex justify-content-center mb-4">
            <div className="d-flex align-items-center gap-2">
              <span style={{
                width: 32, height: 32, borderRadius: '50%',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontWeight: 600, fontSize: 14,
                backgroundColor: 'var(--brand-secondary)', color: 'white',
              }}>1</span>
              <div style={{
                width: 48, height: 2,
                backgroundColor: step >= 2 ? 'var(--brand-secondary)' : '#dee2e6',
              }}></div>
              <span style={{
                width: 32, height: 32, borderRadius: '50%',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontWeight: 600, fontSize: 14,
                backgroundColor: step >= 2 ? 'var(--brand-secondary)' : '#dee2e6',
                color: step >= 2 ? 'white' : '#999',
              }}>2</span>
            </div>
          </div>

          <div className="card shadow-sm border-0" style={{ borderRadius: 12 }}>
            <div className="card-body p-4">
              {error && (
                <div className="alert alert-danger py-2" role="alert">
                  <i className="bi bi-exclamation-circle me-2"></i>{error}
                </div>
              )}

              {step === 1 ? (
                <>
                  <h5 className="mb-3" style={{ color: 'var(--brand-secondary)' }}>{t('register.accountHeading')}</h5>

                  <div className="mb-3">
                    <label htmlFor="reg-username" className="form-label">
                      {t('register.username')} <span className="text-danger">*</span>
                    </label>
                    <div className="input-group">
                      <span className="input-group-text"><i className="bi bi-person"></i></span>
                      <input
                        type="text"
                        id="reg-username"
                        className="form-control"
                        placeholder={t('register.usernamePlaceholder')}
                        value={username}
                        onChange={(e) => setUsername(e.target.value)}
                        required
                        autoFocus
                      />
                    </div>
                  </div>

                  <div className="mb-3">
                    <label htmlFor="reg-email" className="form-label">
                      {t('register.emailLabel')} <span className="text-danger">*</span>
                    </label>
                    <div className="input-group">
                      <span className="input-group-text"><i className="bi bi-envelope"></i></span>
                      <input
                        type="email"
                        id="reg-email"
                        className="form-control"
                        placeholder={t('common.emailPlaceholder')}
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        required
                      />
                    </div>
                  </div>

                  <div className="mb-3">
                    <label htmlFor="reg-password" className="form-label">
                      {t('register.password')} <span className="text-danger">*</span>
                    </label>
                    <div className="input-group">
                      <span className="input-group-text"><i className="bi bi-lock"></i></span>
                      <input
                        type="password"
                        id="reg-password"
                        className="form-control"
                        placeholder={t('register.passwordPlaceholder')}
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        required
                      />
                    </div>
                  </div>

                  <div className="mb-4">
                    <label htmlFor="reg-confirm" className="form-label">
                      {t('register.confirmPassword')} <span className="text-danger">*</span>
                    </label>
                    <div className="input-group">
                      <span className="input-group-text"><i className="bi bi-lock-fill"></i></span>
                      <input
                        type="password"
                        id="reg-confirm"
                        className="form-control"
                        placeholder={t('register.confirmPasswordPlaceholder')}
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        required
                      />
                    </div>
                    {password && confirmPassword && password !== confirmPassword && (
                      <small className="text-danger">
                        <i className="bi bi-x-circle me-1"></i>Passwords don't match
                      </small>
                    )}
                    {password && confirmPassword && password === confirmPassword && (
                      <small className="text-success">
                        <i className="bi bi-check-circle me-1"></i>Passwords match
                      </small>
                    )}
                  </div>

                  <button
                    className="btn w-100 mb-3"
                    style={{ backgroundColor: 'var(--brand-secondary)', color: 'white', fontWeight: 600 }}
                    onClick={handleNext}
                  >
                    {t('register.continue')} <i className="bi bi-arrow-right ms-2"></i>
                  </button>
                </>
              ) : (
                <form onSubmit={handleSubmit}>
                  <h5 className="mb-3" style={{ color: 'var(--brand-secondary)' }}>{t('register.profileHeading')}</h5>

                  <div className="mb-3">
                    <label htmlFor="reg-display" className="form-label">{t('register.displayName')}</label>
                    <input
                      type="text"
                      id="reg-display"
                      className="form-control"
                      placeholder={username || t('register.displayNamePlaceholder')}
                      value={displayName}
                      onChange={(e) => setDisplayName(e.target.value)}
                    />
                    <small className="text-muted">{t('register.displayNameHelp')}</small>
                  </div>

                  {/* Role Selection */}
                  <div className="mb-3">
                    <label className="form-label">
                      {marketplaceEnabled ? t('register.roleQuestionMarketplace') : t('register.roleQuestion')} <span className="text-danger">*</span>
                    </label>
                    <div className="d-flex gap-2">
                      {roleOptions.map(opt => (
                        <div
                          key={opt.value}
                          onClick={() => setRole(opt.value)}
                          style={{
                            flex: 1, padding: '12px 8px', borderRadius: 10, cursor: 'pointer',
                            textAlign: 'center', transition: 'all 0.2s',
                            border: role === opt.value ? '2px solid var(--brand-secondary)' : '2px solid #dee2e6',
                            backgroundColor: role === opt.value ? 'var(--brand-pale)' : 'white',
                          }}
                        >
                          <i className={`bi ${opt.icon}`} style={{
                            fontSize: 24,
                            color: role === opt.value ? 'var(--brand-secondary)' : '#999',
                          }}></i>
                          <div style={{
                            fontWeight: 600, fontSize: 13, marginTop: 4,
                            color: role === opt.value ? 'var(--brand-secondary)' : '#666',
                          }}>
                            {opt.label}
                          </div>
                          <div style={{ fontSize: 11, color: '#999', marginTop: 2 }}>
                            {opt.desc}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Location */}
                  <div className="mb-3">
                    <label className="form-label">{t('register.location')}</label>
                    <input
                      type="text"
                      className="form-control mb-2"
                      placeholder={t('register.addressPlaceholder')}
                      value={address}
                      onChange={(e) => setAddress(e.target.value)}
                    />
                    <div className="row g-2">
                      <div className="col-5">
                        <input
                          type="text"
                          className="form-control"
                          placeholder={t('register.cityPlaceholder')}
                          value={city}
                          onChange={(e) => setCity(e.target.value)}
                        />
                      </div>
                      <div className="col-3">
                        <input
                          type="text"
                          className="form-control"
                          placeholder={t('register.statePlaceholder')}
                          value={state}
                          onChange={(e) => setState(e.target.value)}
                          maxLength={2}
                        />
                      </div>
                      <div className="col-4">
                        <input
                          type="text"
                          className="form-control"
                          placeholder={t('register.zipPlaceholder')}
                          value={zipCode}
                          onChange={(e) => setZipCode(e.target.value)}
                          maxLength={10}
                        />
                      </div>
                    </div>
                    <small className="text-muted">{t('register.locationHelp')}</small>
                  </div>

                  {/* Optional phone + SMS opt-in */}
                  <div className="mb-3">
                    <label className="form-label">{t('register.phone')} <span className="text-muted">{t('register.optional')}</span></label>
                    <input
                      type="tel"
                      className="form-control"
                      placeholder="+1 (555) 555-5555"
                      value={phoneNumber}
                      onChange={(e) => setPhoneNumber(e.target.value)}
                    />
                    <div className="form-check mt-2">
                      <input
                        className="form-check-input"
                        type="checkbox"
                        id="reg-sms-opt-in"
                        checked={smsOptIn}
                        onChange={(e) => setSmsOptIn(e.target.checked)}
                      />
                      <label className="form-check-label" htmlFor="reg-sms-opt-in">
                        {t('register.smsOptIn')}
                      </label>
                    </div>
                    <SmsConsentNote className="mt-1" />
                  </div>

                  <div className="d-flex gap-2 mt-4">
                    <button
                      type="button"
                      className="btn btn-outline-secondary"
                      onClick={() => { setStep(1); setError(''); }}
                    >
                      <i className="bi bi-arrow-left me-1"></i> {t('register.back')}
                    </button>
                    <button
                      type="submit"
                      className="btn flex-grow-1"
                      style={{ backgroundColor: 'var(--brand-secondary)', color: 'white', fontWeight: 600 }}
                      disabled={submitting}
                    >
                      {submitting ? (
                        <>
                          <span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true" />
                          {t('register.submitting')}
                        </>
                      ) : (
                        <>
                          <i className="bi bi-check-circle me-2"></i>{t('register.submit')}
                        </>
                      )}
                    </button>
                  </div>
                  <p className="text-muted text-center mt-3 mb-0" style={{ fontSize: '0.8rem' }}>
                    {/* One sentence, two links. Split into fragments a
                        translator could not reorder it: Spanish puts the
                        possessive on each noun, so "our Terms and Privacy
                        Policy" becomes "nuestros Terminos ... y nuestro
                        Aviso ...". <Trans> keeps it one string. */}
                    <Trans i18nKey="register.legal">
                      By creating an account, you agree to our <Link to="/terms">Terms of Service</Link> and <Link to="/privacy">Privacy Policy</Link>.
                    </Trans>
                  </p>
                </form>
              )}

              <hr className="my-3" />
              <p className="text-center mb-0">
                {t('register.haveAccount')}{' '}
                <Link to="/login" className="text-decoration-none" style={{ color: 'var(--brand-secondary)', fontWeight: 600 }}>
                  {t('common.signIn')}
                </Link>
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
