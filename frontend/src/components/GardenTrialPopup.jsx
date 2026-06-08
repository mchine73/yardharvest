import { useState, useEffect } from 'react';
import { useAuth } from '../AuthContext';
import { gardenBillingAPI } from '../api';
import GardenPaymentModal from './GardenPaymentModal';

/**
 * Globally-mounted popup. When a logged-in user owns a garden whose free trial
 * has ended (and isn't yet paid), it prompts them to enter payment information.
 * Dismissals are remembered for the browser session so it isn't naggy.
 */
export default function GardenTrialPopup() {
  const { user } = useAuth();
  const [alert, setAlert] = useState(null);   // {garden_id, garden_name}
  const [showPayment, setShowPayment] = useState(false);

  useEffect(() => {
    if (!user) { setAlert(null); return; }
    let cancelled = false;
    gardenBillingAPI.myAlerts()
      .then((res) => {
        if (cancelled) return;
        const list = res.data?.needs_payment || [];
        const pending = list.find(
          (g) => sessionStorage.getItem(`trialPopupDismissed:${g.garden_id}`) !== '1',
        );
        if (pending) setAlert(pending);
      })
      .catch(() => { /* silent — non-critical */ });
    return () => { cancelled = true; };
  }, [user]);

  if (!alert) return null;

  const dismiss = () => {
    sessionStorage.setItem(`trialPopupDismissed:${alert.garden_id}`, '1');
    setAlert(null);
  };

  if (showPayment) {
    return (
      <GardenPaymentModal
        gardenId={alert.garden_id}
        gardenName={alert.garden_name}
        onClose={() => setShowPayment(false)}
        onSuccess={() => { setShowPayment(false); setAlert(null); }}
      />
    );
  }

  return (
    <div className="modal d-block" tabIndex="-1" style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}>
      <div className="modal-dialog modal-dialog-centered">
        <div className="modal-content" style={{ borderRadius: 12 }}>
          <div className="modal-header" style={{ backgroundColor: '#1B4D3E', color: 'white' }}>
            <h5 className="modal-title"><i className="bi bi-clock-history me-2"></i>Your free trial has ended</h5>
          </div>
          <div className="modal-body text-center py-4">
            <img src="/sunflower.svg" alt="" style={{ width: '2.5rem', height: '2.5rem', borderRadius: '0.5rem' }} />
            <h5 className="mt-2 mb-1">{alert.garden_name}</h5>
            <p className="text-muted mb-0">
              Your Garden Pro free trial has finished. Add payment information to keep
              managing plots, dues, volunteers, and events without interruption.
            </p>
          </div>
          <div className="modal-footer">
            <button className="btn btn-outline-secondary" onClick={dismiss}>Remind me later</button>
            <button className="btn btn-success" onClick={() => setShowPayment(true)}>
              <i className="bi bi-credit-card me-2"></i>Add payment information
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
