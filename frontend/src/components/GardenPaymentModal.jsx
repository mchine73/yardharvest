import { useState, useRef, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { gardenBillingAPI } from '../api';

// Dynamically load Stripe.js (only when a real payment is needed).
function loadStripeJs(t) {
  return new Promise((resolve, reject) => {
    if (window.Stripe) return resolve(window.Stripe);
    const s = document.createElement('script');
    s.src = 'https://js.stripe.com/v3/';
    s.onload = () => resolve(window.Stripe);
    s.onerror = () => reject(new Error(t('payment.errLoadStripe')));
    document.body.appendChild(s);
  });
}

/**
 * Garden Pro payment modal.
 * Flow: choose cycle -> create checkout -> (dev mode: activate) | (live: card -> confirm -> activate).
 * Props: gardenId, gardenName, defaultCycle, pricing {monthly, yearly}, onClose, onSuccess(message)
 *
 * `pricing` is required and comes from the server (PricingConfig, set in the
 * admin console). There is deliberately no default: a checkout screen must
 * never show a number the platform did not give it, and a hardcoded fallback
 * is exactly how a page ends up quoting a price the charge does not match.
 */
export default function GardenPaymentModal({
  gardenId, gardenName, defaultCycle = 'monthly', pricing,
  onClose, onSuccess,
}) {
  const { t } = useTranslation();
  const priceOf = (cycle) => {
    const amount = pricing?.[cycle];
    return typeof amount === 'number' ? `$${amount}` : '—';
  };
  const [cycle, setCycle] = useState(defaultCycle);
  const [stage, setStage] = useState('select'); // select | card | processing
  const [error, setError] = useState('');
  const [checkout, setCheckout] = useState(null); // {client_secret, subscription_id, publishable_key}
  const cardRef = useRef(null);
  const stripeRef = useRef(null);
  const cardElRef = useRef(null);

  // Mount the Stripe Card Element once we're on the card stage with a client secret.
  useEffect(() => {
    let cancelled = false;
    if (stage !== 'card' || !checkout || !checkout.publishable_key) return;
    (async () => {
      try {
        const Stripe = await loadStripeJs(t);
        if (cancelled) return;
        const stripe = Stripe(checkout.publishable_key);
        const elements = stripe.elements();
        const card = elements.create('card', { hidePostalCode: false });
        card.mount(cardRef.current);
        stripeRef.current = stripe;
        cardElRef.current = card;
      } catch (e) {
        setError(e.message || t('payment.errInitForm'));
      }
    })();
    return () => {
      cancelled = true;
      if (cardElRef.current) { try { cardElRef.current.destroy(); } catch (_) { /* noop */ } }
    };
  }, [stage, checkout]);

  const startCheckout = async () => {
    setError('');
    setStage('processing');
    try {
      const res = await gardenBillingAPI.createCheckout(gardenId, { billing_cycle: cycle });
      if (res.data.dev_mode) {
        // Stripe not configured — activate directly (dev/demo).
        const sub = await gardenBillingAPI.subscribe(gardenId, { billing_cycle: cycle });
        onSuccess?.(sub.data.message || t('payment.activated'));
        return;
      }
      setCheckout(res.data);
      setStage('card');
    } catch (err) {
      setError(err.response?.data?.error || t('payment.errStartCheckout'));
      setStage('select');
    }
  };

  const pay = async () => {
    if (!stripeRef.current || !cardElRef.current) {
      setError(t('payment.errFormNotReady'));
      return;
    }
    setError('');
    setStage('processing');
    try {
      const { error: stripeErr, paymentIntent } = await stripeRef.current.confirmCardPayment(
        checkout.client_secret,
        { payment_method: { card: cardElRef.current } },
      );
      if (stripeErr) {
        setError(stripeErr.message || t('payment.errFailed'));
        setStage('card');
        return;
      }
      if (paymentIntent && paymentIntent.status === 'succeeded') {
        const sub = await gardenBillingAPI.subscribe(gardenId, {
          billing_cycle: cycle,
          subscription_id: checkout.subscription_id,
          payment_reference: paymentIntent.id,
        });
        onSuccess?.(sub.data.message || t('payment.activated'));
      } else {
        setError(t('payment.errNotCompleted'));
        setStage('card');
      }
    } catch (err) {
      setError(err.response?.data?.error || t('payment.errProcessing'));
      setStage('card');
    }
  };

  const busy = stage === 'processing';

  return (
    <div className="modal d-block" tabIndex="-1" style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}>
      <div className="modal-dialog modal-dialog-centered">
        <div className="modal-content" style={{ borderRadius: 12 }}>
          <div className="modal-header">
            <h5 className="modal-title"><i className="bi bi-credit-card me-2"></i>{t('payment.title')}</h5>
            <button type="button" className="btn-close" onClick={onClose} disabled={busy}></button>
          </div>
          <div className="modal-body">
            {gardenName && <p className="text-muted mb-3">{gardenName}</p>}
            {error && <div className="alert alert-danger py-2"><i className="bi bi-exclamation-circle me-2"></i>{error}</div>}

            {stage !== 'card' && (
              <>
                <label className="form-label fw-semibold">{t('payment.chooseCycle')}</label>
                <div className="row g-2 mb-2">
                  <div className="col-6">
                    <div
                      onClick={() => !busy && setCycle('monthly')}
                      className={`card h-100 text-center p-3 ${cycle === 'monthly' ? 'border-success' : ''}`}
                      style={{ cursor: 'pointer', borderWidth: cycle === 'monthly' ? 2 : 1 }}
                    >
                      <div className="fw-semibold">{t('organizer.monthly')}</div>
                      <div className="fs-4 fw-bold" style={{ color: 'var(--brand-secondary)' }}>{priceOf('monthly')}</div>
                      <div className="small text-muted">{t('organizer.perMonth')}</div>
                    </div>
                  </div>
                  <div className="col-6">
                    <div
                      onClick={() => !busy && setCycle('yearly')}
                      className={`card h-100 text-center p-3 ${cycle === 'yearly' ? 'border-success' : ''}`}
                      style={{ cursor: 'pointer', borderWidth: cycle === 'yearly' ? 2 : 1 }}
                    >
                      <span className="badge bg-success mb-1">{t('payment.bestValue')}</span>
                      <div className="fw-semibold">{t('organizer.annual')}</div>
                      <div className="fs-4 fw-bold" style={{ color: 'var(--brand-secondary)' }}>{priceOf('yearly')}</div>
                      <div className="small text-muted">{t('organizer.perYear')}</div>
                    </div>
                  </div>
                </div>
              </>
            )}

            {stage === 'card' && (
              <div className="mb-2">
                <label className="form-label fw-semibold">{t('payment.cardDetails')}</label>
                <div ref={cardRef} className="form-control" style={{ paddingTop: 12, paddingBottom: 12 }}></div>
                <div className="form-text"><i className="bi bi-lock me-1"></i>{t('payment.securedByStripe')}</div>
              </div>
            )}
          </div>
          <div className="modal-footer">
            <button className="btn btn-outline-secondary" onClick={onClose} disabled={busy}>{t('dialog.cancel')}</button>
            {stage === 'card' ? (
              <button className="btn btn-success" onClick={pay} disabled={busy}>
                {busy ? <span className="spinner-border spinner-border-sm me-2"></span> : <i className="bi bi-credit-card me-2"></i>}
                {t('payment.paySubscribe')}
              </button>
            ) : (
              <button className="btn btn-success" onClick={startCheckout} disabled={busy}>
                {busy ? <span className="spinner-border spinner-border-sm me-2"></span> : <i className="bi bi-arrow-right me-2"></i>}
                {t('payment.continue')}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
