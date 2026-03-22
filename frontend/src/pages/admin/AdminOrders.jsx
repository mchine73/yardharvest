import { useState, useEffect } from 'react';
import { adminAPI, ordersAPI } from '../../api';
import { useAuth } from '../../AuthContext';
import AdminHeader from '../../components/AdminHeader';

const STATUS_BADGE = {
  pending: 'bg-warning text-dark',
  accepted: 'bg-info text-white',
  completed: 'bg-success',
  cancelled: 'bg-danger',
};

export default function AdminOrders() {
  const { user } = useAuth();
  const [data, setData] = useState({ orders: [], total: 0, pages: 1, page: 1 });
  const [filter, setFilter] = useState('all');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [cancelling, setCancelling] = useState(null);
  const [refundModal, setRefundModal] = useState(null);
  const [refundAmount, setRefundAmount] = useState('');
  const [refundReason, setRefundReason] = useState('');
  const [refunding, setRefunding] = useState(false);

  const loadOrders = () => {
    if (user?.is_admin) {
      setLoading(true);
      adminAPI.orders({ page, status: filter })
        .then(res => { setData(res.data); setLoading(false); })
        .catch(() => setLoading(false));
    }
  };

  useEffect(() => { loadOrders(); }, [page, filter, user]);

  const handleCancel = async (orderId) => {
    if (!window.confirm(`Cancel order #${orderId}? This will restore inventory and notify the buyer.`)) return;
    setCancelling(orderId);
    try {
      await ordersAPI.cancel(orderId);
      loadOrders();
    } catch (err) {
      alert(err.response?.data?.error || 'Failed to cancel order');
    }
    setCancelling(null);
  };

  const handleRefund = async () => {
    setRefunding(true);
    try {
      const amt = parseFloat(refundAmount);
      await adminAPI.refundOrder(refundModal.id, { amount: amt, reason: refundReason });
      setRefundModal(null);
      setRefundAmount('');
      setRefundReason('');
      loadOrders();
    } catch (err) {
      alert(err.response?.data?.error || 'Refund failed');
    }
    setRefunding(false);
  };

  if (!user?.is_admin) return <div className="alert alert-danger">Access Denied</div>;

  const tabs = ['all', 'pending', 'accepted', 'completed', 'cancelled'];

  return (
    <>
      <AdminHeader title="Order Management" icon="bi-box-seam" />
      <ul className="nav nav-tabs mb-3">
        {tabs.map(t => (
          <li key={t} className="nav-item">
            <button className={`nav-link ${filter === t ? 'active' : ''}`} onClick={() => { setFilter(t); setPage(1); }}>
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </button>
          </li>
        ))}
      </ul>
      {loading ? (
        <div className="text-center py-4"><div className="spinner-border text-success"></div></div>
      ) : (
        <table className="table">
          <thead><tr><th>#</th><th>Buyer</th><th>Seller</th><th>Total</th><th>Status</th><th>Method</th><th>Date</th><th>Actions</th></tr></thead>
          <tbody>{data.orders.map(o => (
            <tr key={o.id}>
              <td>{o.id}</td><td>{o.buyer_name}</td><td>{o.seller_name}</td>
              <td>${o.total_price.toFixed(2)}</td>
              <td><span className={`badge ${STATUS_BADGE[o.status] || 'bg-secondary'}`}>{o.status}</span></td>
              <td>{o.fulfillment_method}{o.delivery_provider === 'doordash' && <span className="badge bg-danger ms-1" style={{fontSize:'0.65rem'}}>DD</span>}</td>
              <td>{new Date(o.created_at).toLocaleDateString()}</td>
              <td>
                <div className="btn-group btn-group-sm">
                  {o.status !== 'cancelled' && (
                    <button className="btn btn-outline-danger" disabled={cancelling === o.id}
                      onClick={() => handleCancel(o.id)}>
                      {cancelling === o.id ? <span className="spinner-border spinner-border-sm"></span> : <><i className="bi bi-x-circle me-1"></i>Cancel</>}
                    </button>
                  )}
                  {o.payment_status === 'succeeded' && o.refund_status !== 'full' && (
                    <button className="btn btn-outline-warning" onClick={() => { setRefundModal(o); setRefundAmount(o.total_price - (o.refund_amount || 0)); }}>
                      <i className="bi bi-arrow-counterclockwise me-1"></i>Refund
                    </button>
                  )}
                </div>
              </td>
            </tr>
          ))}</tbody>
        </table>
      )}
      {data.pages > 1 && (
        <nav><ul className="pagination justify-content-center">
          {Array.from({ length: data.pages }, (_, i) => (
            <li key={i} className={`page-item ${page === i + 1 ? 'active' : ''}`}><button className="page-link" onClick={() => setPage(i + 1)}>{i + 1}</button></li>
          ))}
        </ul></nav>
      )}
      {/* Refund Modal */}
      {refundModal && (
        <div className="modal d-block" style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}>
          <div className="modal-dialog">
            <div className="modal-content">
              <div className="modal-header">
                <h5 className="modal-title"><i className="bi bi-arrow-counterclockwise me-2"></i>Refund Order #{refundModal.id}</h5>
                <button className="btn-close" onClick={() => setRefundModal(null)}></button>
              </div>
              <div className="modal-body">
                <p>Order total: <strong>${refundModal.total_price.toFixed(2)}</strong>
                  {(refundModal.refund_amount || 0) > 0 && <span className="text-muted ms-2">(already refunded: ${(refundModal.refund_amount || 0).toFixed(2)})</span>}
                </p>
                <div className="mb-3">
                  <label className="form-label">Refund Amount</label>
                  <div className="input-group">
                    <span className="input-group-text">$</span>
                    <input type="number" className="form-control" value={refundAmount} onChange={e => setRefundAmount(e.target.value)}
                      min="0.01" max={refundModal.total_price - (refundModal.refund_amount || 0)} step="0.01" />
                  </div>
                </div>
                <div className="mb-3">
                  <label className="form-label">Reason</label>
                  <textarea className="form-control" rows={2} value={refundReason} onChange={e => setRefundReason(e.target.value)} placeholder="Optional reason for refund..." />
                </div>
              </div>
              <div className="modal-footer">
                <button className="btn btn-secondary" onClick={() => setRefundModal(null)}>Cancel</button>
                <button className="btn btn-warning" disabled={refunding || !refundAmount || parseFloat(refundAmount) <= 0} onClick={handleRefund}>
                  {refunding ? <span className="spinner-border spinner-border-sm"></span> : <><i className="bi bi-arrow-counterclockwise me-1"></i>Issue Refund</>}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
