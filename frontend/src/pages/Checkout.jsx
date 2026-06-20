import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { cartAPI, paymentAPI, promoAPI } from '../api';
import { trackEvent } from '../hooks/useTracking';
import { useAuth } from '../AuthContext';
import { loadStripe } from '@stripe/stripe-js';
import { Elements, PaymentElement, useStripe, useElements } from '@stripe/react-stripe-js';

function StripePaymentForm({ onSuccess, onCancel, amount }) {
  const stripe = useStripe();
  const elements = useElements();
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!stripe || !elements) return;
    setProcessing(true);
    setError('');

    const { error: stripeError, paymentIntent } = await stripe.confirmPayment({
      elements,
      redirect: 'if_required',
    });

    if (stripeError) {
      setError(stripeError.message);
      setProcessing(false);
    } else if (paymentIntent && paymentIntent.status === 'succeeded') {
      onSuccess(paymentIntent);
    } else {
      setError('Payment was not completed. Please try again.');
      setProcessing(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <PaymentElement />
      {error && <div className="alert alert-danger mt-3"><i className="bi bi-exclamation-triangle me-2"></i>{error}</div>}
      <div className="d-flex gap-2 mt-3">
        <button type="submit" className="btn btn-success btn-lg flex-grow-1" disabled={!stripe || processing}>
          {processing ? <><span className="spinner-border spinner-border-sm me-2"></span>Processing...</> : <><i className="bi bi-lock me-2"></i>Pay ${(amount / 100).toFixed(2)}</>}
        </button>
        <button type="button" className="btn btn-outline-secondary" onClick={onCancel} disabled={processing}>Cancel</button>
      </div>
    </form>
  );
}

export default function Checkout() {
  const navigate = useNavigate();
  const { refreshCounts } = useAuth();
  const [cart, setCart] = useState(null);
  const [notes, setNotes] = useState('');
  const [fulfillment, setFulfillment] = useState({});
  const [submitting, setSubmitting] = useState(false);

  const [paymentStep, setPaymentStep] = useState('review');
  const [sessionData, setSessionData] = useState(null);
  const [stripePromise, setStripePromise] = useState(null);
  const [paymentError, setPaymentError] = useState('');
  const [promoCode, setPromoCode] = useState('');
  const [promoResult, setPromoResult] = useState(null);
  const [promoChecking, setPromoChecking] = useState(false);

  useEffect(() => {
    cartAPI.get().then(res => {
      setCart(res.data);
      trackEvent('checkout_start');
      const f = {};
      res.data.groups.forEach(g => { f[g.seller_id] = 'pickup'; });
      setFulfillment(f);
    }).catch(() => setPaymentError('Failed to load cart. Please try again.'));
  }, []);

  const proceedToPayment = async () => {
    setSubmitting(true);
    setPaymentError('');
    try {
      const payload = {};
      Object.entries(fulfillment).forEach(([sid, method]) => {
        payload[`fulfillment_${sid}`] = method;
      });
      if (promoResult?.valid) payload.promo_code = promoResult.code;
      const res = await paymentAPI.createSession(payload);
      setSessionData(res.data);
      if (!res.data.dev_mode && res.data.publishable_key) {
        setStripePromise(loadStripe(res.data.publishable_key));
      }
      setPaymentStep('paying');
    } catch (err) {
      setPaymentError(err.response?.data?.error || 'Failed to initialize payment');
    } finally {
      setSubmitting(false);
    }
  };

  const handlePaymentSuccess = async (paymentIntent) => {
    setPaymentStep('processing');
    try {
      const data = {
        payment_intent_id: paymentIntent?.id || `dev-${Date.now()}`,
        notes,
      };
      if (promoResult?.valid) data.promo_code = promoResult.code;
      Object.entries(fulfillment).forEach(([sid, method]) => {
        data[`fulfillment_${sid}`] = method;
      });
      await paymentAPI.confirmPayment(data);
      trackEvent('checkout_complete');
      refreshCounts();
      navigate('/orders');
    } catch (err) {
      setPaymentError(err.response?.data?.error || 'Failed to confirm payment');
      setPaymentStep('paying');
    }
  };

  const handleDevPayment = async () => {
    await handlePaymentSuccess({ id: `dev-test-${Date.now()}`, status: 'succeeded' });
  };

  if (!cart) return <div className="text-center py-5"><div className="spinner-border text-success"></div></div>;

  return (
    <>
      <h1 className="mb-4"><i className="bi bi-bag-check me-2"></i>Checkout</h1>

      {cart.groups.map(group => (
        <div key={group.seller_id} className="card mb-3">
          <div className="card-header"><strong>Order from {group.seller_name}</strong> — ${group.subtotal.toFixed(2)}</div>
          <div className="card-body">
            {group.items.map(item => (
              <div key={item.id} className="d-flex justify-content-between mb-1">
                <span>{item.listing.title} x{item.quantity}</span>
                <span>${item.subtotal.toFixed(2)}</span>
              </div>
            ))}
            <hr />
            <div className="form-check form-check-inline">
              <input className="form-check-input" type="radio" id={`pickup_${group.seller_id}`} name={`ful_${group.seller_id}`} checked={fulfillment[group.seller_id] === 'pickup'} onChange={() => setFulfillment({ ...fulfillment, [group.seller_id]: 'pickup' })} disabled={paymentStep !== 'review'} />
              <label className="form-check-label" htmlFor={`pickup_${group.seller_id}`}>Pickup</label>
            </div>
            <div className="form-check form-check-inline">
              <input className="form-check-input" type="radio" id={`delivery_${group.seller_id}`} name={`ful_${group.seller_id}`} checked={fulfillment[group.seller_id] === 'delivery'} onChange={() => setFulfillment({ ...fulfillment, [group.seller_id]: 'delivery' })} disabled={paymentStep !== 'review'} />
              <label className="form-check-label" htmlFor={`delivery_${group.seller_id}`}>Delivery</label>
            </div>
            {fulfillment[group.seller_id] === 'delivery' && cart.fee_info?.delivery_fees_enabled && (
              <div className="mt-2">
                <small className="text-muted">
                  <i className="bi bi-truck me-1"></i>
                  {cart.fee_info.doordash_enabled ? <span className="text-danger fw-semibold">DoorDash Delivery</span> : <>Delivery fee: ${cart.fee_info.delivery_fee_flat.toFixed(2)}</>}
                  {!cart.fee_info.doordash_enabled && cart.fee_info.per_mile_enabled && cart.fee_info.delivery_fee_per_mile > 0 && <> + distance-based surcharge</>}
                  {cart.fee_info.free_delivery_enabled && cart.fee_info.delivery_fee_free_threshold > 0 && group.subtotal >= cart.fee_info.delivery_fee_free_threshold && <span className="text-success ms-1">(FREE - order qualifies!)</span>}
                </small>
                {cart.fee_info.doordash_enabled && <div><small className="text-muted">Delivery powered by DoorDash Drive. Final fee calculated at checkout.</small></div>}
              </div>
            )}
          </div>
        </div>
      ))}

      <div className="mb-3">
        <label className="form-label">Notes for seller(s)</label>
        <textarea className="form-control" rows={2} value={notes} onChange={e => setNotes(e.target.value)} placeholder="Any special requests..." disabled={paymentStep !== 'review'} />
      </div>

      <div className="card mb-3">
        <div className="card-body py-2">
          <div className="d-flex justify-content-between"><span>Subtotal</span><span>${cart.grand_total.toFixed(2)}</span></div>
          {Object.values(fulfillment).some(f => f === 'delivery') && cart.fee_info?.delivery_fees_enabled && (
            <div className="d-flex justify-content-between text-muted"><span><i className="bi bi-truck me-1"></i>Delivery Fee (estimated)</span><span>${cart.fee_info.delivery_fee_flat.toFixed(2)}</span></div>
          )}
          {cart.fee_info?.commission_enabled && cart.fee_info.platform_commission_pct > 0 && (
            <div className="d-flex justify-content-between text-muted small"><span>Platform service fee ({(cart.fee_info.platform_commission_pct * 100).toFixed(0)}%)</span><span>Included</span></div>
          )}
          <hr className="my-1" />
          <div className="d-flex justify-content-between fw-bold"><span>Estimated Total</span><span className="text-success">${(cart.grand_total + (Object.values(fulfillment).some(f => f === 'delivery') && cart.fee_info?.delivery_fees_enabled ? cart.fee_info.delivery_fee_flat : 0)).toFixed(2)}</span></div>
        </div>
      </div>

      {/* Promo Code */}
      {paymentStep === 'review' && (
        <div className="card mb-3">
          <div className="card-body py-2">
            <div className="d-flex gap-2 align-items-center">
              <i className="bi bi-ticket-perforated text-muted"></i>
              <input className="form-control form-control-sm" style={{ maxWidth: '200px' }} placeholder="Promo code" value={promoCode} onChange={e => setPromoCode(e.target.value)} />
              <button className="btn btn-sm btn-outline-success" disabled={!promoCode || promoChecking} onClick={async () => {
                setPromoChecking(true);
                try {
                  const res = await promoAPI.validate({ code: promoCode, scope: 'marketplace' });
                  setPromoResult(res.data);
                } catch (err) {
                  setPromoResult({ valid: false, reason: err.response?.data?.reason || 'Invalid code' });
                }
                setPromoChecking(false);
              }}>
                {promoChecking ? <span className="spinner-border spinner-border-sm"></span> : 'Apply'}
              </button>
              {promoResult?.valid && (
                <span className="badge bg-success"><i className="bi bi-check-circle me-1"></i>{promoResult.discount_type === 'percentage' ? `${promoResult.discount_value}% off` : `$${promoResult.discount_value.toFixed(2)} off`}</span>
              )}
              {promoResult && !promoResult.valid && (
                <span className="text-danger small"><i className="bi bi-x-circle me-1"></i>{promoResult.reason}</span>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="d-flex justify-content-end align-items-center mb-4">
        {paymentStep === 'review' && (
          <button className="btn btn-success btn-lg" onClick={proceedToPayment} disabled={submitting}>
            {submitting ? <><span className="spinner-border spinner-border-sm me-2"></span>Initializing Payment...</> : <><i className="bi bi-credit-card me-2"></i>Pay with Card</>}
          </button>
        )}
      </div>

      {paymentError && <div className="alert alert-danger" role="alert"><i className="bi bi-exclamation-triangle me-2"></i>{paymentError}</div>}

      {paymentStep === 'paying' && sessionData && (
        <div className="card border-success mb-4">
          <div className="card-header bg-success text-white"><i className="bi bi-shield-lock me-2"></i>Secure Payment</div>
          <div className="card-body">
            {sessionData.dev_mode ? (
              <div className="text-center py-4">
                <div className="card mx-auto" style={{ maxWidth: '400px', border: '2px dashed #22242a' }}>
                  <div className="card-body">
                    <h5 className="card-title text-success mb-3"><i className="bi bi-credit-card-2-front me-2"></i>Test Payment</h5>
                    <p className="fs-3 fw-bold mb-2">${(sessionData.amount / 100).toFixed(2)} USD</p>
                    <p className="text-muted small mb-4"><i className="bi bi-info-circle me-1"></i>Development mode — no real charges</p>
                    <button className="btn btn-success btn-lg w-100" onClick={handleDevPayment}><i className="bi bi-check-circle me-2"></i>Complete Test Payment</button>
                    <button className="btn btn-outline-secondary mt-2 w-100" onClick={() => { setPaymentStep('review'); setSessionData(null); }}>Cancel</button>
                  </div>
                </div>
              </div>
            ) : stripePromise && sessionData.client_secret ? (
              <Elements stripe={stripePromise} options={{ clientSecret: sessionData.client_secret, appearance: { theme: 'stripe' } }}>
                <StripePaymentForm amount={sessionData.amount} onSuccess={handlePaymentSuccess} onCancel={() => { setPaymentStep('review'); setSessionData(null); }} />
              </Elements>
            ) : (
              <div className="text-center py-4"><div className="spinner-border text-success"></div></div>
            )}
          </div>
        </div>
      )}

      {paymentStep === 'processing' && (
        <div className="text-center py-5">
          <div className="spinner-border text-success mb-3" style={{ width: '3rem', height: '3rem' }}></div>
          <h5>Processing your payment...</h5>
          <p className="text-muted">Please do not close this page.</p>
        </div>
      )}
    </>
  );
}
