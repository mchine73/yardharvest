import { Link } from 'react-router-dom';
import { IMAGE_BASE } from '../api';

export default function ListingCard({ listing }) {
  const img = listing.image_filename
    ? `${IMAGE_BASE}${listing.image_filename}`
    : listing.image_url || '/placeholder-produce.svg';

  const priceDiff = listing.effective_price && listing.base_price
    ? listing.effective_price - listing.base_price
    : 0;

  return (
    <div className="col-md-6 col-lg-3 mb-4">
      <div className="card listing-card h-100 shadow-sm">
        <img src={img} className="card-img-top" alt={listing.title}
             style={{ height: '200px', objectFit: 'cover' }} />
        <div className="card-body d-flex flex-column">
          <h6 className="card-title" style={{
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
          }}>{listing.title}</h6>
          <p className="text-muted small mb-1">
            <i className="bi bi-person"></i> {listing.seller_name || 'Local Grower'}
          </p>
          <div className="mt-auto">
            <div className="d-flex justify-content-between align-items-center">
              <div>
                {listing.effective_price != null || listing.price != null ? (
                  <>
                    <span className="fw-bold text-success fs-5">
                      ${(listing.effective_price ?? listing.price ?? 0).toFixed(2)}
                    </span>
                    <small className="text-muted ms-1">/{listing.unit || 'unit'}</small>
                  </>
                ) : (
                  <span className="text-muted">Price TBD</span>
                )}
              </div>
              {priceDiff > 0.01 && (
                <span className="badge bg-warning text-dark">
                  <i className="bi bi-graph-up"></i> High demand
                </span>
              )}
            </div>
            {listing.distance !== undefined && (
              <small className="text-muted">
                <i className="bi bi-geo-alt"></i> {listing.distance} mi away
              </small>
            )}
            <div className="mt-2">
              <Link to={`/listings/${listing.id}`} className="btn btn-sm btn-outline-success w-100">
                View Details
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
