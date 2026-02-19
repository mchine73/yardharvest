import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { cartAPI, paymentAPI } from '../api';
import { useAuth } from '../AuthContext';
import Embed from '@gr4vy/embed-react';

export default function Checkout() {
  const navigate = useNavigate();
  const { refreshCounts } = useAuth();
  const [cart, setCart] = useState(null);
  const [notes, setNotes] = useState('');
  const [fulfillment, setFulfillment] = useState({});
  const [submitting, setSubmitting] = useState(false);

  // Payment flow state
  const [paymentStep, setPaymentStep] = useState('review'); // review | paying | processing
  const [sessionData, setSessionData] = useState(null);
  const [paymentError, setPaymentError] = useState('');

  useEffect(() => {
    cartAPI.get().then(res => {
      setCart(res.data);
      const f = {};
      res.data.groups.forEach(g => { f[g.seller_id] = 'pickup'; });
      setFulfillment(f);
    }).catch(() => setPaymentError('Failed to load cart. Please try again.'));
  }, []);

  const proceedToPayment = async () => {
    setSubmitting(true);
    setPaymentError('');
    try {
      const res = await paymentAPI.createSession();
      setSessionData(res.data);
      setPaymentStep('paying');
    } catch (err) {
      setPaymentError(err.response?.data?.error || 'Failed to initialize payment');
    } finally {
      setSubmitting(false);
    }
  };

  const handlePaymentComplete = async (transaction) => {
    setPaymentStep('processing');
    try {
      const data = {
        transaction_id: transaction?.id || `dev-${Date.now()}`,
        transaction_status: transaction?.status || 'completed',
        notes,
      };
      Object.entries(fulfillment).forEach(([sid, method]) => {
        data[`fulfillment_${sid}`] = method;
      });
      await paymentAPI.confirmPayment(data);
      refreshCounts();
      navigate('/orders');
    } catch (err) {
      setPaymentError(err.response?.data?.error || 'Failed to confirm payment');
      setPaymentStep('paying');
    }
  };

  const handleDevPayment = async () => {
    await handlePaymentComplete({
      id: `dev-test-${Date.now()}`,
      status: 'completed',
    });
  };

  if (!cart) return <div className="text-center py-5"><div className="spinner-border text-success"></div></div>;

  return (
    <>
      <h1 className="mb-4"><i className="bi bi-bag-check me-2"></i>Checkout</h1>

      {/* Cart Summary */}
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
          </div>
        </div>
      ))}

      <div className="mb-3">
        <label className="form-label">Notes for seller(s)</label>
        <textarea className="form-control" rows={2} value={notes} onChange={e => setNotes(e.target.value)} placeholder="Any special requests..." disabled={paymentStep !== 'review'} />
      </div>

      <div className="d-flex justify-content-between align-items-center mb-4">
        <h4>Total: <span className="text-success">${cart.grand_total.toFixed(2)}</span></h4>

        {paymentStep === 'review' && (
          <button className="btn btn-success btn-lg" onClick={proceedToPayment} disabled={submitting}>
            {submitting ? (
              <>
                <span className="spinner-border spinner-border-sm me-2"></span>
                Initializing Payment...
              </>
            ) : (
              <>
                <i className="bi bi-credit-card me-2"></i>
                Pay with Gr4vy
              </>
            )}
          </button>
        )}
      </div>

      {paymentError && (
        <div className="alert alert-danger" role="alert">
          <i className="bi bi-exclamation-triangle me-2"></i>{paymentError}
        </div>
      )}

      {/* Payment Section */}
      {paymentStep === 'paying' && sessionData && (
        <div className="card border-success mb-4">
          <div className="card-header bg-success text-white">
            <i className="bi bi-shield-lock me-2"></i>Secure Payment
          </div>
          <div className="card-body">
            {sessionData.dev_mode ? (
              /* Dev Mode - Simulated Payment UI */
              <div className="text-center py-4">
                <div className="card mx-auto" style={{ maxWidth: '400px', border: '2px dashed #198754' }}>
                  <div className="card-body">
                    <h5 className="card-title text-success mb-3">
                      <i className="bi bi-credit-card-2-front me-2"></i>Test Payment
                    </h5>
                    <p className="fs-3 fw-bold mb-2">${(sessionData.amount / 100).toFixed(2)} USD</p>
                    <p className="text-muted small mb-4">
                      <i className="bi bi-info-circle me-1"></i>
                      Development mode — no real charges
                    </p>
                    <button className="btn btn-success btn-lg w-100" onClick={handleDevPayment}>
                      <i className="bi bi-check-circle me-2"></i>Complete Test Payment
                    </button>
                    <button className="btn btn-outline-secondary mt-2 w-100" onClick={() => { setPaymentStep('review'); setSessionData(null); }}>
                      Cancel
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              /* Real Gr4vy Embed */
              <Embed
                gr4vyId={sessionData.gr4vy_id}
                environment={sessionData.environment}
                token={sessionData.token}
                amount={sessionData.amount}
                currency={sessionData.currency}
                country="US"
                onComplete={(transaction) => handlePaymentComplete(transaction)}
              />
            )}
          </div>
        </div>
      )}

      {/* Processing State */}
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
