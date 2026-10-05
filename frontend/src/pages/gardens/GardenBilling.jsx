import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { gardenBillingAPI, gardensAPI } from '../../api';
import GardenPaymentModal from '../../components/GardenPaymentModal';
import StripeConnectOnboarding from '../../components/StripeConnectOnboarding';
import { confirmDialog } from '../../components/dialog/dialogService';
import { useTranslation, Trans } from 'react-i18next';
import { formatDate } from '../../i18n/dates';

export default function GardenBilling() {
  const { t } = useTranslation();
  const { id } = useParams();
  const [billing, setBilling] = useState(null);
  const [garden, setGarden] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionMsg, setActionMsg] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [payCycle, setPayCycle] = useState('monthly');
  const [showPay, setShowPay] = useState(false);
  const [payouts, setPayouts] = useState(null);
  const [connecting, setConnecting] = useState(false);

  useEffect(() => {
    gardenBillingAPI.payoutStatus(id)
      .then((r) => setPayouts(r.data))
      .catch(() => { /* non-critical */ });
  }, [id]);

  // ?onboard=1 opens the Connect flow immediately, so the setup checklist can
  // send someone straight into onboarding instead of dropping them on a page
  // and hoping they find the button.
  const [showOnboarding, setShowOnboarding] = useState(
    () => new URLSearchParams(window.location.search).get('onboard') === '1');

  const refreshPayouts = () =>
    gardenBillingAPI.payoutStatus(id).then((r) => setPayouts(r.data)).catch(() => {});

  // When the embedded flow can't load, show the real reason (don't silently
  // bounce). The "Use Stripe's hosted setup" link below lets them proceed.
  const handleEmbedError = (err) => {
    const d = err?.response?.data;
    const reason = d?.detail || d?.error || err?.message
      || 'on-site setup could not load';
    setError(`Couldn't load on-site payout setup — ${reason}. `
      + `You can use Stripe's hosted setup below.`);
  };

  // Fallback when the embedded component can't load: hosted onboarding link.
  const connectPayoutsHosted = async () => {
    setShowOnboarding(false);
    setConnecting(true);
    setError('');
    try {
      const res = await gardenBillingAPI.payoutConnect(id);
      if (res.data.url) window.location.href = res.data.url;
    } catch (err) {
      const d = err.response?.data;
      setError([d?.error || t('organizer.errPayoutStart'), d?.detail]
        .filter(Boolean).join(' — '));
      setConnecting(false);
    }
  };

  const reloadBilling = () => gardenBillingAPI.status(id).then((r) => setBilling(r.data));

  const openPay = (cycle) => { setPayCycle(cycle); setShowPay(true); };

  const handlePaid = (message) => {
    setShowPay(false);
    setActionMsg(message || t('organizer.toastProActivated'));
    reloadBilling();
  };

  useEffect(() => {
    Promise.all([
      gardenBillingAPI.status(id),
      gardensAPI.detail(id),
    ]).then(([billingRes, gardenRes]) => {
      setBilling(billingRes.data);
      setGarden(gardenRes.data);
    }).catch(() => setError(t('organizer.errBillingLoad')))
      .finally(() => setLoading(false));
  }, [id]);

  const startTrial = async () => {
    setSubmitting(true);
    setError('');
    try {
      const res = await gardenBillingAPI.startTrial(id);
      setActionMsg(res.data.message);
      setBilling({ ...billing, status: 'trialing', subscription: res.data.subscription, trial_days_remaining: billing?.trial_days || 14 });
    } catch (err) {
      setError(err.response?.data?.error || t('organizer.errTrialStart'));
    } finally {
      setSubmitting(false);
    }
  };

  const cancelSub = async () => {
    if (!(await confirmDialog(t('organizer.confirmCancelSub'), { danger: true, title: t('organizer.cancelSubTitle'), confirmText: t('organizer.cancelSubTitle'), cancelText: t('organizer.keepIt') }))) return;
    setSubmitting(true);
    setError('');
    try {
      const res = await gardenBillingAPI.cancel(id);
      setActionMsg(res.data.message);
      setBilling({ ...billing, cancel_at_period_end: true });
    } catch (err) {
      setError(err.response?.data?.error || t('organizer.errCancel'));
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <div className="text-center py-5"><div className="spinner-border text-success"></div></div>;

  const status = billing?.status || 'none';
  // Straight from the server (PricingConfig / admin console). No literal
  // fallback — showing an invented price on a billing page is worse than
  // showing a dash while it loads.
  const pricing = billing?.pricing || {};
  const priceOf = (cycle) => (typeof pricing[cycle] === 'number' ? `$${pricing[cycle]}` : '—');
  // Computed, never stated. The hardcoded "Save $55 — over 3 months free"
  // was derived from $15/$125; at the real $12/$60 the saving is $84 and
  // seven months, so the page was understating its own offer.
  const annualSaving = (typeof pricing.monthly === 'number'
                        && typeof pricing.yearly === 'number')
    ? Math.round(pricing.monthly * 12 - pricing.yearly) : null;
  const monthsFree = (annualSaving && pricing.monthly)
    ? Math.floor(annualSaving / pricing.monthly) : null;

  return (
    <div className="container py-4">
      <div className="row justify-content-center">
        <div className="col-md-8">
          <Link to={`/gardens/${id}/admin`} className="text-decoration-none text-muted mb-3 d-inline-block">
            <i className="bi bi-arrow-left me-1"></i>{t('organizer.backToDashboard')}
          </Link>

          <h2 className="mb-1" style={{ color: 'var(--brand-primary)' }}>
            <i className="bi bi-credit-card me-2"></i>{t('organizer.billingTitle')}
          </h2>
          <p className="text-muted mb-4">{garden?.name}</p>

          {error && <div className="alert alert-danger py-2"><i className="bi bi-exclamation-circle me-2"></i>{error}</div>}
          {actionMsg && <div className="alert alert-success py-2"><i className="bi bi-check-circle me-2"></i>{actionMsg}</div>}

          {/* Current Status Card */}
          <div className="card shadow-sm mb-4" style={{ borderRadius: 12 }}>
            <div className="card-body p-4">
              <div className="d-flex justify-content-between align-items-center mb-3">
                <h5 className="mb-0">{t('organizer.currentPlan')}</h5>
                <span className={`badge ${status === 'active' ? 'bg-success' : status === 'trialing' ? 'bg-info' : 'bg-secondary'} fs-6`}>
                  {status === 'active' ? t('organizer.planPro')
                    : status === 'trialing' ? t('organizer.planTrial')
                    : status === 'expired' ? t('organizer.planExpired')
                    : t('organizer.planFree')}
                </span>
              </div>

              {status === 'trialing' && (
                <div className="alert alert-info py-2 mb-0">
                  <i className="bi bi-clock me-2"></i>
                  <Trans i18nKey="organizer.trialRemaining"
                         values={{ count: billing.trial_days_remaining }}>
                    <strong>{'{{count}}'} days</strong> remaining in your trial. All Pro features are unlocked.
                  </Trans>
                </div>
              )}

              {status === 'active' && billing.admin_granted && (
                <div className="alert alert-success py-2 mb-0">
                  <i className="bi bi-patch-check me-2"></i>
                  {t('organizer.grantedNote')}
                </div>
              )}

              {status === 'active' && billing.cancel_at_period_end && !billing.admin_granted && (
                <div className="alert alert-warning py-2 mb-0">
                  <i className="bi bi-exclamation-triangle me-2"></i>
                  {t('organizer.cancellationScheduled', {
                    date: formatDate(billing.subscription?.current_period_end) || t('organizer.periodEnd'),
                  })}
                </div>
              )}

              {status === 'active' && !billing.cancel_at_period_end && billing.subscription && (
                <div>
                  <p className="mb-1"><strong>{t('organizer.billingCycle')}</strong> {billing.subscription.billing_cycle}</p>
                  <p className="mb-1"><strong>{t('organizer.periodEnds')}</strong> {new Date(billing.subscription.current_period_end).toLocaleDateString()}</p>
                  <button className="btn btn-outline-danger btn-sm mt-2" onClick={cancelSub} disabled={submitting}>
                    {t('organizer.cancelSubscription')}
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Payouts (Stripe Connect) — receive member dues */}
          {payouts && (
            <div className="card shadow-sm mb-4" style={{ borderRadius: 12 }}>
              <div className="card-body p-4">
                <div className="d-flex justify-content-between align-items-center mb-2">
                  <h5 className="mb-0"><i className="bi bi-bank me-2"></i>{t('organizer.duesPayouts')}</h5>
                  {payouts.ready && <span className="badge bg-success">{t('organizer.connected')}</span>}
                </div>
                {!payouts.configured ? (
                  <p className="text-muted mb-0">
                    {t('organizer.payoutsUnavailable')}
                  </p>
                ) : payouts.ready ? (
                  <div>
                    <p className="mb-2 text-success">
                      <i className="bi bi-check-circle me-2"></i>
                      {t('organizer.duesDirect')}
                    </p>
                    {payouts.dashboard_url && (
                      <a href={payouts.dashboard_url} target="_blank" rel="noopener noreferrer"
                         className="btn btn-outline-success btn-sm">
                        <i className="bi bi-box-arrow-up-right me-1"></i>{t('organizer.viewStripePayouts')}
                      </a>
                    )}
                  </div>
                ) : (
                  <div>
                    <p className="text-muted mb-3">
                      {t('organizer.payoutsIntro')}
                    </p>
                    {showOnboarding ? (
                      <>
                        <p className="text-muted small mb-2"><i className="bi bi-shield-lock me-1"></i>
                          Stripe opens a brief secure popup to verify your identity and bank details —
                          please allow popups for this site if prompted.</p>
                        <StripeConnectOnboarding
                          fetchAccountSession={() => gardenBillingAPI.payoutAccountSession(id)}
                          onComplete={() => {
                            setShowOnboarding(false);
                            setActionMsg(t('organizer.toastPayoutSaved'));
                            refreshPayouts();
                          }}
                          onError={handleEmbedError}
                        />
                        <button className="btn btn-link btn-sm text-muted px-0 mt-2"
                                onClick={connectPayoutsHosted} disabled={connecting}>
                          {t('organizer.stripeHostedFallback')}
                        </button>
                      </>
                    ) : (
                      <>
                        <button className="btn btn-success"
                                onClick={() => { setError(''); setShowOnboarding(true); }}
                                disabled={connecting}>
                          {connecting
                            ? <span className="spinner-border spinner-border-sm me-2"></span>
                            : <i className="bi bi-bank me-2"></i>}
                          {payouts.onboarded ? t('organizer.finishPayoutSetup') : t('organizer.setUpPayouts')}
                        </button>
                      </>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Upgrade / Subscribe Section */}
          {(status === 'none' || status === 'expired') && (
            <>
              {status === 'none' && billing?.trial_available && (
                <div className="card shadow-sm mb-4 border-success" style={{ borderRadius: 12, borderWidth: 2 }}>
                  <div className="card-body p-4 text-center">
                    <i className="bi bi-gift fs-1 text-success"></i>
                    <h4 className="mt-2">{billing?.trial_days
                    ? t('organizer.startTrialDays', { days: billing.trial_days })
                    : t('organizer.startTrial')}</h4>
                    <p className="text-muted">{t('organizer.trialFullAccess')}</p>
                    <button
                      className="btn btn-success btn-lg"
                      onClick={startTrial}
                      disabled={submitting}
                    >
                      {submitting ? <span className="spinner-border spinner-border-sm me-2"></span> : <i className="bi bi-rocket-takeoff me-2"></i>}
                      {t('organizer.startFreeTrial')}
                    </button>
                  </div>
                </div>
              )}

              <h4 className="mb-3">{t('organizer.choosePlan')}</h4>
              <div className="row g-3">
                <div className="col-md-6">
                  <div className="card h-100 shadow-sm" style={{ borderRadius: 12 }}>
                    <div className="card-body p-4 text-center">
                      <h5>{t('organizer.monthly')}</h5>
                      <div className="display-5 fw-bold" style={{ color: 'var(--brand-secondary)' }}>{priceOf('monthly')}</div>
                      <p className="text-muted">{t('organizer.perMonth')}</p>
                      <p className="small text-muted">{t('organizer.flexibleCancel')}</p>
                      <button
                        className="btn btn-outline-success w-100"
                        onClick={() => openPay('monthly')}
                        disabled={submitting}
                      >
                        {t('organizer.subscribeMonthly')}
                      </button>
                    </div>
                  </div>
                </div>
                <div className="col-md-6">
                  <div className="card h-100 shadow-sm border-success" style={{ borderRadius: 12, borderWidth: 2 }}>
                    <div className="card-body p-4 text-center">
                      <span className="badge bg-success mb-2">{t('organizer.bestValue')}</span>
                      <h5>{t('organizer.annual')}</h5>
                      <div className="display-5 fw-bold" style={{ color: 'var(--brand-secondary)' }}>{priceOf('yearly')}</div>
                      <p className="text-muted">{t('organizer.perYear')}</p>
                      {annualSaving > 0 && (
                        <p className="small text-success fw-bold">
                          {monthsFree > 0
                            ? t('organizer.saveAnnualMonths', { amount: annualSaving, months: monthsFree })
                            : t('organizer.saveAnnual', { amount: annualSaving })}
                        </p>
                      )}
                      <button
                        className="btn btn-success w-100"
                        onClick={() => openPay('yearly')}
                        disabled={submitting}
                      >
                        {t('organizer.subscribeAnnually')}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </>
          )}

          {/* Trialing — show subscribe options */}
          {status === 'trialing' && (
            <>
              <h4 className="mb-3">{t('organizer.subscribeToKeep')}</h4>
              <div className="row g-3">
                <div className="col-md-6">
                  <div className="card h-100 shadow-sm" style={{ borderRadius: 12 }}>
                    <div className="card-body p-4 text-center">
                      <h5>{t('organizer.monthly')}</h5>
                      <div className="display-5 fw-bold" style={{ color: 'var(--brand-secondary)' }}>{priceOf('monthly')}</div>
                      <p className="text-muted">{t('organizer.perMonth')}</p>
                      <button className="btn btn-outline-success w-100" onClick={() => openPay('monthly')} disabled={submitting}>
                        {t('organizer.subscribeMonthly')}
                      </button>
                    </div>
                  </div>
                </div>
                <div className="col-md-6">
                  <div className="card h-100 shadow-sm border-success" style={{ borderRadius: 12, borderWidth: 2 }}>
                    <div className="card-body p-4 text-center">
                      <span className="badge bg-success mb-2">{t('organizer.bestValue')}</span>
                      <h5>{t('organizer.annual')}</h5>
                      <div className="display-5 fw-bold" style={{ color: 'var(--brand-secondary)' }}>{priceOf('yearly')}</div>
                      <p className="text-muted">
                        {annualSaving > 0
                          ? t('organizer.perYearSave', { amount: annualSaving })
                          : t('organizer.perYear')}
                      </p>
                      <button className="btn btn-success w-100" onClick={() => openPay('yearly')} disabled={submitting}>
                        {t('organizer.subscribeAnnually')}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </>
          )}

          {/* Feature List */}
          <div className="card shadow-sm mt-4" style={{ borderRadius: 12 }}>
            <div className="card-body p-4">
              <h5>{t('organizer.included')}</h5>
              <div className="row mt-3">
                <div className="col-md-6">
                  <ul className="list-unstyled">
                    <li className="mb-2"><i className="bi bi-check-circle-fill text-success me-2"></i>{t('organizer.featUnlimitedPlots')}</li>
                    <li className="mb-2"><i className="bi bi-check-circle-fill text-success me-2"></i>{t('organizer.featFinancial')}</li>
                    <li className="mb-2"><i className="bi bi-check-circle-fill text-success me-2"></i>{t('organizer.featShifts')}</li>
                    <li className="mb-2"><i className="bi bi-check-circle-fill text-success me-2"></i>{t('organizer.featAttendance')}</li>
                  </ul>
                </div>
                <div className="col-md-6">
                  <ul className="list-unstyled">
                    <li className="mb-2"><i className="bi bi-check-circle-fill text-success me-2"></i>{t('organizer.featPhotoWall')}</li>
                    <li className="mb-2"><i className="bi bi-check-circle-fill text-success me-2"></i>{t('organizer.featBroadcast')}</li>
                    <li className="mb-2"><i className="bi bi-check-circle-fill text-success me-2"></i>{t('organizer.featBranding')}</li>
                    <li className="mb-2"><i className="bi bi-check-circle-fill text-success me-2"></i>{t('organizer.featGridExport')}</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>

        </div>
      </div>

      {showPay && (
        <GardenPaymentModal
          gardenId={id}
          gardenName={garden?.name}
          defaultCycle={payCycle}
          pricing={pricing}
          onClose={() => setShowPay(false)}
          onSuccess={handlePaid}
        />
      )}
    </div>
  );
}
