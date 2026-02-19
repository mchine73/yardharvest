import { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { listingsAPI, cartAPI, IMAGE_BASE } from '../api';
import { useAuth } from '../AuthContext';

export default function ListingDetail() {
  const { id } = useParams();
  const { user, refreshCounts } = useAuth();
  const navigate = useNavigate();
  const [listing, setListing] = useState(null);
  const [quantity, setQuantity] = useState(1);
  const [msg, setMsg] = useState('');

  useEffect(() => {
    listingsAPI.detail(id).then(res => setListing(res.data));
  }, [id]);

  if (!listing) return <div className="text-center py-5"><div className="spinner-border text-success"></div></div>;

  const images = [listing.image_filename, listing.image_filename_2, listing.image_filename_3].filter(Boolean);
  const priceDiff = (listing.effective_price || 0) - (listing.base_price || 0);

  const addToCart = async () => {
    try {
      await cartAPI.add(listing.id, quantity);
      setMsg('Added to cart!');
      refreshCounts();
      setTimeout(() => setMsg(''), 3000);
    } catch (err) {
      setMsg(err.response?.data?.error || 'Error adding to cart');
    }
  };

  return (
    <>
      <Link to="/browse" className="btn btn-outline-secondary mb-3"><i className="bi bi-arrow-left me-1"></i>Back</Link>
      <div className="row">
        <div className="col-md-6">
          {images.length > 1 ? (
            <div id="imgCarousel" className="carousel slide" data-bs-ride="carousel">
              <div className="carousel-inner">
                {images.map((img, i) => (
                  <div key={i} className={`carousel-item ${i === 0 ? 'active' : ''}`}>
                    <img src={`${IMAGE_BASE}${img}`} className="d-block w-100 rounded" style={{ height: 400, objectFit: 'cover' }} alt="" />
                  </div>
                ))}
              </div>
              <button className="carousel-control-prev" type="button" data-bs-target="#imgCarousel" data-bs-slide="prev"><span className="carousel-control-prev-icon"></span></button>
              <button className="carousel-control-next" type="button" data-bs-target="#imgCarousel" data-bs-slide="next"><span className="carousel-control-next-icon"></span></button>
            </div>
          ) : images.length === 1 ? (
            <img src={`${IMAGE_BASE}${images[0]}`} className="w-100 rounded" style={{ height: 400, objectFit: 'cover' }} alt="" />
          ) : (
            <div className="bg-light d-flex align-items-center justify-content-center rounded" style={{ height: 400 }}>
              <i className="bi bi-image fs-1 text-muted"></i>
            </div>
          )}
        </div>
        <div className="col-md-6">
          <h2>{listing.title}</h2>
          <p className="text-muted mb-1"><i className="bi bi-tag me-1"></i>{listing.vegetable_type}</p>

          <div className="my-3">
            <span className="fs-3 fw-bold text-success">${listing.effective_price?.toFixed(2)}</span>
            <span className="text-muted ms-1">/{listing.unit}</span>
            {priceDiff > 0.01 && (
              <span className="badge bg-warning text-dark ms-2"><i className="bi bi-graph-up me-1"></i>High demand pricing</span>
            )}
            {priceDiff > 0.01 && <div className="text-muted small">Base: ${listing.base_price?.toFixed(2)}</div>}
          </div>

          <p>{listing.description}</p>

          <div className="mb-2"><strong>Available:</strong> {listing.quantity_available} {listing.unit}</div>
          {listing.distance !== undefined && (
            <div className="mb-2"><i className="bi bi-geo-alt text-success me-1"></i>{listing.distance} miles away</div>
          )}
          {listing.delivery_available && (
            <div className="mb-2"><i className="bi bi-truck text-primary me-1"></i>Delivery available within {listing.delivery_radius_miles} mi
              {listing.can_deliver && <span className="badge bg-success ms-1">Can deliver to you!</span>}
            </div>
          )}
          {listing.pickup_instructions && (
            <div className="mb-2"><i className="bi bi-info-circle me-1"></i>{listing.pickup_instructions}</div>
          )}

          <hr />
          <div className="mb-2"><strong>Seller:</strong> <Link to={`/profile/${listing.seller_id}`}>{listing.seller_name}</Link>
            {listing.seller_rating && <span className="ms-2"><i className="bi bi-star-fill text-warning"></i> {listing.seller_rating} ({listing.seller_review_count})</span>}
          </div>

          {msg && <div className="alert alert-info py-2">{msg}</div>}

          {user && user.id !== listing.seller_id && (
            <div className="d-flex gap-2 mt-3">
              <input type="number" className="form-control" style={{ width: 80 }} min={1} max={listing.quantity_available} value={quantity} onChange={e => setQuantity(Math.max(1, parseInt(e.target.value) || 1))} />
              <button className="btn btn-success" onClick={addToCart}><i className="bi bi-cart-plus me-1"></i>Add to Cart</button>
              <Link to={`/messages/new/${listing.seller_id}?listing_id=${listing.id}`} className="btn btn-outline-primary">
                <i className="bi bi-chat me-1"></i>Message Seller
              </Link>
            </div>
          )}
          {!user && <p className="text-muted mt-3"><Link to="/login">Log in</Link> to purchase or message the seller.</p>}
        </div>
      </div>
    </>
  );
}
