import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { cartAPI, IMAGE_BASE } from '../api';
import { useAuth } from '../AuthContext';

export default function Cart() {
  const { refreshCounts } = useAuth();
  const [cart, setCart] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionError, setActionError] = useState('');

  const fetchCart = async () => {
    try {
      const res = await cartAPI.get();
      setCart(res.data);
      setLoading(false);
      refreshCounts();
    } catch {
      setLoading(false);
      setError('Failed to load cart.');
    }
  };

  useEffect(() => { fetchCart(); }, []);

  const updateQty = async (itemId, qty) => {
    setActionError('');
    try {
      await cartAPI.update(itemId, qty);
      fetchCart();
    } catch {
      setActionError('Failed to update quantity. Please try again.');
    }
  };

  const remove = async (itemId) => {
    setActionError('');
    try {
      await cartAPI.remove(itemId);
      fetchCart();
    } catch {
      setActionError('Failed to remove item. Please try again.');
    }
  };

  if (loading) return <div className="text-center py-5"><div className="spinner-border text-success"></div></div>;
  if (error) return <div className="alert alert-danger">{error}</div>;

  if (!cart || cart.item_count === 0) {
    return (
      <div className="text-center py-5">
        <i className="bi bi-cart-x fs-1 text-muted"></i>
        <h3 className="mt-3">Your cart is empty</h3>
        <Link to="/browse" className="btn btn-success mt-2">Browse Produce</Link>
      </div>
    );
  }

  return (
    <>
      <h1 className="mb-4"><i className="bi bi-cart3 me-2"></i>Shopping Cart</h1>
      {actionError && (
        <div className="alert alert-danger py-2 d-flex justify-content-between align-items-center">
          <span><i className="bi bi-exclamation-circle me-2"></i>{actionError}</span>
          <button className="btn-close btn-sm" onClick={() => setActionError('')}></button>
        </div>
      )}
      {cart.groups.map(group => (
        <div key={group.seller_id} className="card mb-3">
          <div className="card-header bg-light"><strong>{group.seller_name}</strong></div>
          <div className="card-body">
            {group.items.map(item => (
              <div key={item.id} className="d-flex align-items-center mb-2 pb-2 border-bottom">
                {(item.listing.image_filename || item.listing.image_url) && (
                  <img src={item.listing.image_filename ? `${IMAGE_BASE}${item.listing.image_filename}` : item.listing.image_url} alt="" className="rounded me-3" style={{ width: 60, height: 60, objectFit: 'cover' }} />
                )}
                <div className="flex-grow-1">
                  <Link to={`/listings/${item.listing_id}`} className="text-decoration-none fw-bold">{item.listing.title}</Link>
                  <div className="text-muted small">${(item.listing.effective_price ?? item.listing.price ?? 0).toFixed(2)} / {item.listing.unit}</div>
                </div>
                <div className="d-flex align-items-center gap-2">
                  <input type="number" className="form-control form-control-sm" style={{ width: 70 }} min={1} max={item.listing.quantity_available} value={item.quantity} onChange={e => updateQty(item.id, parseInt(e.target.value) || 1)} />
                  <span className="fw-bold">${item.subtotal.toFixed(2)}</span>
                  <button className="btn btn-sm btn-outline-danger" onClick={() => remove(item.id)}><i className="bi bi-trash"></i></button>
                </div>
              </div>
            ))}
            <div className="text-end"><strong>Subtotal: ${group.subtotal.toFixed(2)}</strong></div>
          </div>
        </div>
      ))}
      {/* Fee Info — only show if delivery fees are enabled */}
      {cart.fee_info?.delivery_fees_enabled && (
        <div className="card mb-3 border-info">
          <div className="card-body py-2">
            <small className="text-muted">
              <i className="bi bi-truck me-1"></i>
              Delivery fee: ${cart.fee_info.delivery_fee_flat.toFixed(2)}/order
              {cart.fee_info.per_mile_enabled && cart.fee_info.delivery_fee_per_mile > 0 && <> + ${cart.fee_info.delivery_fee_per_mile.toFixed(2)}/mi</>}
              {cart.fee_info.free_delivery_enabled && cart.fee_info.delivery_fee_free_threshold > 0 && <> &middot; Free delivery on orders over ${cart.fee_info.delivery_fee_free_threshold.toFixed(2)}</>}
            </small>
          </div>
        </div>
      )}
      <div className="d-flex justify-content-between align-items-center mt-3 flex-wrap gap-2">
        <h4 className="mb-0">Subtotal: <span className="text-success">${cart.grand_total.toFixed(2)}</span></h4>
        <div className="d-flex gap-2">
          <Link to="/browse" className="btn btn-outline-success"><i className="bi bi-arrow-left me-1"></i>Continue Shopping</Link>
          <Link to="/checkout" className="btn btn-success btn-lg"><i className="bi bi-bag-check me-2"></i>Proceed to Checkout</Link>
        </div>
      </div>
    </>
  );
}
