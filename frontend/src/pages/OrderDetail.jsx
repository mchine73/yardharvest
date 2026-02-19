import { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { ordersAPI, IMAGE_BASE } from '../api';
import { useAuth } from '../AuthContext';

const STATUS_BADGE = {
  pending: 'bg-warning text-dark',
  accepted: 'bg-info text-white',
  completed: 'bg-success',
  cancelled: 'bg-danger',
};

export default function OrderDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [order, setOrder] = useState(null);

  const fetchOrder = () => ordersAPI.detail(id).then(res => setOrder(res.data));
  useEffect(() => { fetchOrder(); }, [id]);

  const action = async (fn) => { await fn(id); fetchOrder(); };

  if (!order) return <div className="text-center py-5"><div className="spinner-border text-success"></div></div>;

  const isSeller = user?.id === order.seller_id;
  const isBuyer = user?.id === order.buyer_id;

  return (
    <>
      <Link to={isSeller ? '/seller/orders' : '/orders'} className="btn btn-outline-secondary mb-3"><i className="bi bi-arrow-left me-1"></i>Back</Link>
      <div className="card">
        <div className="card-header d-flex justify-content-between">
          <h4 className="mb-0">Order #{order.id}</h4>
          <span className={`badge ${STATUS_BADGE[order.status] || 'bg-secondary'} fs-6`}>{order.status}</span>
        </div>
        <div className="card-body">
          <div className="row mb-3">
            <div className="col-md-6"><strong>Buyer:</strong> <Link to={`/profile/${order.buyer_id}`}>{order.buyer_name}</Link></div>
            <div className="col-md-6"><strong>Seller:</strong> <Link to={`/profile/${order.seller_id}`}>{order.seller_name}</Link></div>
          </div>
          <div className="row mb-3">
            <div className="col-md-6"><strong>Fulfillment:</strong> {order.fulfillment_method}</div>
            <div className="col-md-6"><strong>Date:</strong> {new Date(order.created_at).toLocaleString()}</div>
          </div>
          {order.notes && <div className="mb-3"><strong>Notes:</strong> {order.notes}</div>}
          <h5>Items</h5>
          <table className="table">
            <thead><tr><th></th><th>Item</th><th>Qty</th><th>Price</th><th>Subtotal</th></tr></thead>
            <tbody>
              {order.items.map(item => (
                <tr key={item.id}>
                  <td>{item.listing_image ? <img src={`${IMAGE_BASE}${item.listing_image}`} alt="" style={{ width: 40, height: 40, objectFit: 'cover' }} className="rounded" /> : item.image_url ? <img src={item.image_url} alt="" style={{ width: 40, height: 40, objectFit: 'cover' }} className="rounded" /> : <i className="bi bi-basket text-muted"></i>}</td>
                  <td><Link to={`/listings/${item.listing_id}`}>{item.listing_title}</Link></td>
                  <td>{item.quantity}</td>
                  <td>${item.unit_price.toFixed(2)}</td>
                  <td>${item.subtotal.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr><td colSpan={4} className="text-end">Items Subtotal:</td><td>${(order.subtotal || order.total_price).toFixed(2)}</td></tr>
              {order.delivery_fee > 0 && <tr><td colSpan={4} className="text-end">Delivery Fee:</td><td>${order.delivery_fee.toFixed(2)}</td></tr>}
              <tr><td colSpan={4} className="text-end fw-bold">Total:</td><td className="fw-bold text-success">${order.total_price.toFixed(2)}</td></tr>
              {isSeller && order.platform_commission > 0 && (
                <>
                  <tr className="table-light"><td colSpan={4} className="text-end text-muted small">Platform Commission ({(order.commission_rate * 100).toFixed(0)}%):</td><td className="text-muted small">-${order.platform_commission.toFixed(2)}</td></tr>
                  <tr className="table-light"><td colSpan={4} className="text-end fw-bold">Your Earnings:</td><td className="fw-bold text-primary">${(order.seller_earnings || order.total_price).toFixed(2)}</td></tr>
                </>
              )}
            </tfoot>
          </table>
          <div className="d-flex gap-2">
            {isSeller && order.status === 'pending' && <button className="btn btn-primary" onClick={() => action(ordersAPI.accept)}>Accept Order</button>}
            {isSeller && order.status === 'accepted' && <button className="btn btn-success" onClick={() => action(ordersAPI.complete)}>Mark Complete</button>}
            {(order.status === 'pending' || order.status === 'accepted') && <button className="btn btn-outline-danger" onClick={() => action(ordersAPI.cancel)}>Cancel</button>}
            {isBuyer && order.status === 'completed' && !order.has_review && <Link to={`/orders/${order.id}/review`} className="btn btn-warning">Leave Review</Link>}
          </div>
        </div>
      </div>
    </>
  );
}
