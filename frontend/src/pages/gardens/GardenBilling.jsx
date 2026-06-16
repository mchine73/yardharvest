import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { gardenBillingAPI, gardensAPI } from '../../api';
import GardenPaymentModal from '../../components/GardenPaymentModal';
import StripeConnectOnboarding from '../../components/StripeConnectOnboarding';
import { confirmDialog } from '../../components/dialog/dialogService';

export default function GardenBilling() {
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

  const [showOnboarding, setShowOnboarding] = useState(false);

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
      setError([d?.error || 'Failed to start payout setup', d?.detail]
        .filter(Boolean).join(' — '));
      setConnecting(false);
    }
  };

  const reloadBilling = () => gardenBillingAPI.status(id).then((r) => setBilling(r.data));

  const openPay = (cycle) => { setPayCycle(cycle); setShowPay(true); };

  const handlePaid = (message) => {
    setShowPay(false);
    setActionMsg(message || 'Garden Pro activated!');
    reloadBilling();
  };

  useEffect(() => {
    Promise.all([
      gardenBillingAPI.status(id),
      gardensAPI.detail(id),
    ]).then(([billingRes, gardenRes]) => {
      setBilling(billingRes.data);
      setGarden(gardenRes.data);
    }).catch(() => setError('Failed to load billing info'))
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
      setError(err.response?.data?.error || 'Failed to start trial');
    } finally {
      setSubmitting(false);
    }
  };

  const cancelSub = async () => {
    if (!(await confirmDialog("Cancel your Garden Pro subscription? You'll keep access until the end of your current billing period.", { danger: true, title: 'Cancel subscription', confirmText: 'Cancel subscription', cancelText: 'Keep it' }))) return;
    setSubmitting(true);
    setError('');
    try {
      const res = await gardenBillingAPI.cancel(id);
      setActionMsg(res.data.message);
      setBilling({ ...billing, cancel_at_period_end: true });
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to cancel');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <div className="text-center py-5"><div className="spinner-border text-success"></div></div>;

  const status = billing?.status || 'none';
  const pricing = billing?.pricing || { monthly: 15, yearly: 125 };

  return (
    <div className="container py-4">
      <div className="row justify-content-center">
        <div className="col-md-8">
          <Link to={`/gardens/${id}/admin`} className="text-decoration-none text-muted mb-3 d-inline-block">
            <i className="bi bi-arrow-left me-1"></i>Back to Dashboard
          </Link>

          <h2 className="mb-1" style={{ color: 'var(--brand-primary)' }}>
            <i className="bi bi-credit-card me-2"></i>Garden Pro Billing
          </h2>
          <p className="text-muted mb-4">{garden?.name}</p>

          {error && <div className="alert alert-danger py-2"><i className="bi bi-exclamation-circle me-2"></i>{error}</div>}
          {actionMsg && <div className="alert alert-success py-2"><i className="bi bi-check-circle me-2"></i>{actionMsg}</div>}

          {/* Current Status Card */}
          <div className="card shadow-sm mb-4" style={{ borderRadius: 12 }}>
            <div className="card-body p-4">
              <div className="d-flex justify-content-between align-items-center mb-3">
                <h5 className="mb-0">Current Plan</h5>
                <span className={`badge ${status === 'active' ? 'bg-success' : status === 'trialing' ? 'bg-info' : 'bg-secondary'} fs-6`}>
                  {status === 'active' ? 'Garden Pro' : status === 'trialing' ? 'Trial' : status === 'expired' ? 'Expired' : 'Free'}
                </span>
              </div>

              {status === 'trialing' && (
                <div className="alert alert-info py-2 mb-0">
                  <i className="bi bi-clock me-2"></i>
                  <strong>{billing.trial_days_remaining} days</strong> remaining in your trial.
                  All Pro features are unlocked.
                </div>
              )}

              {status === 'active' && billing.admin_granted && (
                <div className="alert alert-success py-2 mb-0">
                  <i className="bi bi-patch-check me-2"></i>
                  Garden Pro has been granted to your garden by the YardHarvest team. No billing action is required.
                </div>
              )}

              {status === 'active' && billing.cancel_at_period_end && !billing.admin_granted && (
                <div className="alert alert-warning py-2 mb-0">
                  <i className="bi bi-exclamation-triangle me-2"></i>
                  Cancellation scheduled. Pro access continues until {billing.subscription?.current_period_end ? new Date(billing.subscription.current_period_end).toLocaleDateString() : 'end of period'}.
                </div>
              )}

              {status === 'active' && !billing.cancel_at_period_end && billing.subscription && (
                <div>
                  <p className="mb-1"><strong>Billing cycle:</strong> {billing.subscription.billing_cycle}</p>
                  <p className="mb-1"><strong>Current period ends:</strong> {new Date(billing.subscription.current_period_end).toLocaleDateString()}</p>
                  <button className="btn btn-outline-danger btn-sm mt-2" onClick={cancelSub} disabled={submitting}>
                    Cancel Subscription
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
                  <h5 className="mb-0"><i className="bi bi-bank me-2"></i>Dues Payouts</h5>
                  {payouts.ready && <span className="badge bg-success">Connected</span>}
                </div>
                {!payouts.configured ? (
                  <p className="text-muted mb-0">
                    Online dues payouts are unavailable until the platform's payment system is configured.
                  </p>
                ) : payouts.ready ? (
                  <div>
                    <p className="mb-2 text-success">
                      <i className="bi bi-check-circle me-2"></i>
                      Member dues are paid directly to your connected Stripe account.
                    </p>
                    {payouts.dashboard_url && (
                      <a href={payouts.dashboard_url} target="_blank" rel="noopener noreferrer"
                         className="btn btn-outline-success btn-sm">
                        <i className="bi bi-box-arrow-up-right me-1"></i>View Stripe payouts
                      </a>
                    )}
                  </div>
                ) : (
                  <div>
                    <p className="text-muted mb-3">
                      Connect a Stripe account so member dues are paid out to you. Without this,
                      collected dues stay with the platform.
                    </p>
                    {showOnboarding ? (
                      <>
                        <StripeConnectOnboarding
                          fetchAccountSession={() => gardenBillingAPI.payoutAccountSession(id)}
                          onComplete={() => {
                            setShowOnboarding(false);
                            setActionMsg('Payout setup saved.');
                            refreshPayouts();
                          }}
                          onError={handleEmbedError}
                        />
                        <button className="btn btn-link btn-sm text-muted px-0 mt-2"
                                onClick={connectPayoutsHosted} disabled={connecting}>
                          Having trouble? Use Stripe's hosted setup instead
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
                          {payouts.onboarded ? 'Finish payout setup' : 'Set up payouts'}
                        </button>
                        <p className="text-muted small mt-2 mb-0">
                          Securely enter your details right here — no need to leave YardHarvest.
                        </p>
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
                    <h4 className="mt-2">Start Your Free 14-Day Trial</h4>
                    <p className="text-muted">Full access to all Garden Pro features. No payment required.</p>
                    <button
                      className="btn btn-success btn-lg"
                      onClick={startTrial}
                      disabled={submitting}
                    >
                      {submitting ? <span className="spinner-border spinner-border-sm me-2"></span> : <i className="bi bi-rocket-takeoff me-2"></i>}
                      Start Free Trial
                    </button>
                  </div>
                </div>
              )}

              <h4 className="mb-3">Choose Your Plan</h4>
              <div className="row g-3">
                <div className="col-md-6">
                  <div className="card h-100 shadow-sm" style={{ borderRadius: 12 }}>
                    <div className="card-body p-4 text-center">
                      <h5>Monthly</h5>
                      <div className="display-5 fw-bold" style={{ color: 'var(--brand-secondary)' }}>${pricing.monthly}</div>
                      <p className="text-muted">per month</p>
                      <p className="small text-muted">Flexible. Cancel anytime.</p>
                      <button
                        className="btn btn-outline-success w-100"
                        onClick={() => openPay('monthly')}
                        disabled={submitting}
                      >
                        Subscribe Monthly
                      </button>
                    </div>
                  </div>
                </div>
                <div className="col-md-6">
                  <div className="card h-100 shadow-sm border-success" style={{ borderRadius: 12, borderWidth: 2 }}>
                    <div className="card-body p-4 text-center">
                      <span className="badge bg-success mb-2">Best Value</span>
                      <h5>Annual</h5>
                      <div className="display-5 fw-bold" style={{ color: 'var(--brand-secondary)' }}>${pricing.yearly}</div>
                      <p className="text-muted">per year</p>
                      <p className="small text-success fw-bold">Save $55 — over 3 months free</p>
                      <button
                        className="btn btn-success w-100"
                        onClick={() => openPay('yearly')}
                        disabled={submitting}
                      >
                        Subscribe Annually
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
              <h4 className="mb-3">Subscribe Now to Keep Pro Features</h4>
              <div className="row g-3">
                <div className="col-md-6">
                  <div className="card h-100 shadow-sm" style={{ borderRadius: 12 }}>
                    <div className="card-body p-4 text-center">
                      <h5>Monthly</h5>
                      <div className="display-5 fw-bold" style={{ color: 'var(--brand-secondary)' }}>${pricing.monthly}</div>
                      <p className="text-muted">per month</p>
                      <button className="btn btn-outline-success w-100" onClick={() => openPay('monthly')} disabled={submitting}>
                        Subscribe Monthly
                      </button>
                    </div>
                  </div>
                </div>
                <div className="col-md-6">
                  <div className="card h-100 shadow-sm border-success" style={{ borderRadius: 12, borderWidth: 2 }}>
                    <div className="card-body p-4 text-center">
                      <span className="badge bg-success mb-2">Best Value</span>
                      <h5>Annual</h5>
                      <div className="display-5 fw-bold" style={{ color: 'var(--brand-secondary)' }}>${pricing.yearly}</div>
                      <p className="text-muted">per year — save $55</p>
                      <button className="btn btn-success w-100" onClick={() => openPay('yearly')} disabled={submitting}>
                        Subscribe Annually
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
              <h5>What's included in Garden Pro</h5>
              <div className="row mt-3">
                <div className="col-md-6">
                  <ul className="list-unstyled">
                    <li className="mb-2"><i className="bi bi-check-circle-fill text-success me-2"></i>Unlimited plots</li>
                    <li className="mb-2"><i className="bi bi-check-circle-fill text-success me-2"></i>Financial management (dues, expenses)</li>
                    <li className="mb-2"><i className="bi bi-check-circle-fill text-success me-2"></i>Volunteer shift scheduling</li>
                    <li className="mb-2"><i className="bi bi-check-circle-fill text-success me-2"></i>Attendance tracking & reports</li>
                  </ul>
                </div>
                <div className="col-md-6">
                  <ul className="list-unstyled">
                    <li className="mb-2"><i className="bi bi-check-circle-fill text-success me-2"></i>Photo wall with comments</li>
                    <li className="mb-2"><i className="bi bi-check-circle-fill text-success me-2"></i>Broadcast messaging</li>
                    <li className="mb-2"><i className="bi bi-check-circle-fill text-success me-2"></i>Custom email branding</li>
                    <li className="mb-2"><i className="bi bi-check-circle-fill text-success me-2"></i>Plot grid editor & data export</li>
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
