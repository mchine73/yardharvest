import { useState, useRef, useEffect } from 'react';
import { gardenBillingAPI } from '../api';

// Dynamically load Stripe.js (only when a real payment is needed).
function loadStripeJs() {
  return new Promise((resolve, reject) => {
    if (window.Stripe) return resolve(window.Stripe);
    const s = document.createElement('script');
    s.src = 'https://js.stripe.com/v3/';
    s.onload = () => resolve(window.Stripe);
    s.onerror = () => reject(new Error('Could not load Stripe.js'));
    document.body.appendChild(s);
  });
}

/**
 * Garden Pro payment modal.
 * Flow: choose cycle -> create checkout -> (dev mode: activate) | (live: card -> confirm -> activate).
 * Props: gardenId, gardenName, defaultCycle, pricing {monthly, yearly}, onClose, onSuccess(message)
 */
export default function GardenPaymentModal({
  gardenId, gardenName, defaultCycle = 'monthly', pricing = { monthly: 15, yearly: 125 },
  onClose, onSuccess,
}) {
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
        const Stripe = await loadStripeJs();
        if (cancelled) return;
        const stripe = Stripe(checkout.publishable_key);
        const elements = stripe.elements();
        const card = elements.create('card', { hidePostalCode: false });
        card.mount(cardRef.current);
        stripeRef.current = stripe;
        cardElRef.current = card;
      } catch (e) {
        setError(e.message || 'Could not initialize payment form.');
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
        onSuccess?.(sub.data.message || 'Garden Pro activated.');
        return;
      }
      setCheckout(res.data);
      setStage('card');
    } catch (err) {
      setError(err.response?.data?.error || 'Could not start checkout. Please try again.');
      setStage('select');
    }
  };

  const pay = async () => {
    if (!stripeRef.current || !cardElRef.current) {
      setError('Payment form not ready yet.');
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
        setError(stripeErr.message || 'Payment failed.');
        setStage('card');
        return;
      }
      if (paymentIntent && paymentIntent.status === 'succeeded') {
        const sub = await gardenBillingAPI.subscribe(gardenId, {
          billing_cycle: cycle,
          subscription_id: checkout.subscription_id,
          payment_reference: paymentIntent.id,
        });
        onSuccess?.(sub.data.message || 'Garden Pro activated.');
      } else {
        setError('Payment was not completed. Please try again.');
        setStage('card');
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Payment could not be processed.');
      setStage('card');
    }
  };

  const busy = stage === 'processing';

  return (
    <div className="modal d-block" tabIndex="-1" style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}>
      <div className="modal-dialog modal-dialog-centered">
        <div className="modal-content" style={{ borderRadius: 12 }}>
          <div className="modal-header">
            <h5 className="modal-title"><i className="bi bi-credit-card me-2"></i>Garden Pro Payment</h5>
            <button type="button" className="btn-close" onClick={onClose} disabled={busy}></button>
          </div>
          <div className="modal-body">
            {gardenName && <p className="text-muted mb-3">{gardenName}</p>}
            {error && <div className="alert alert-danger py-2"><i className="bi bi-exclamation-circle me-2"></i>{error}</div>}

            {stage !== 'card' && (
              <>
                <label className="form-label fw-semibold">Choose a billing cycle</label>
                <div className="row g-2 mb-2">
                  <div className="col-6">
                    <div
                      onClick={() => !busy && setCycle('monthly')}
                      className={`card h-100 text-center p-3 ${cycle === 'monthly' ? 'border-success' : ''}`}
                      style={{ cursor: 'pointer', borderWidth: cycle === 'monthly' ? 2 : 1 }}
                    >
                      <div className="fw-semibold">Monthly</div>
                      <div className="fs-4 fw-bold" style={{ color: 'var(--brand-secondary)' }}>${pricing.monthly}</div>
                      <div className="small text-muted">per month</div>
                    </div>
                  </div>
                  <div className="col-6">
                    <div
                      onClick={() => !busy && setCycle('yearly')}
                      className={`card h-100 text-center p-3 ${cycle === 'yearly' ? 'border-success' : ''}`}
                      style={{ cursor: 'pointer', borderWidth: cycle === 'yearly' ? 2 : 1 }}
                    >
                      <span className="badge bg-success mb-1">Best value</span>
                      <div className="fw-semibold">Annual</div>
                      <div className="fs-4 fw-bold" style={{ color: 'var(--brand-secondary)' }}>${pricing.yearly}</div>
                      <div className="small text-muted">per year</div>
                    </div>
                  </div>
                </div>
              </>
            )}

            {stage === 'card' && (
              <div className="mb-2">
                <label className="form-label fw-semibold">Card details</label>
                <div ref={cardRef} className="form-control" style={{ paddingTop: 12, paddingBottom: 12 }}></div>
                <div className="form-text"><i className="bi bi-lock me-1"></i>Secured by Stripe. We never store your card.</div>
              </div>
            )}
          </div>
          <div className="modal-footer">
            <button className="btn btn-outline-secondary" onClick={onClose} disabled={busy}>Cancel</button>
            {stage === 'card' ? (
              <button className="btn btn-success" onClick={pay} disabled={busy}>
                {busy ? <span className="spinner-border spinner-border-sm me-2"></span> : <i className="bi bi-credit-card me-2"></i>}
                Pay & Subscribe
              </button>
            ) : (
              <button className="btn btn-success" onClick={startCheckout} disabled={busy}>
                {busy ? <span className="spinner-border spinner-border-sm me-2"></span> : <i className="bi bi-arrow-right me-2"></i>}
                Continue to payment
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
