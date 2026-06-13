import { useState, useEffect } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { listingsAPI } from '../api';
import ListingCard from '../components/ListingCard';

function PreorderCard({ item }) {
  return (
    <div className="col-md-6 col-lg-3 mb-4">
      <div className="card listing-card h-100 shadow-sm" style={{ borderTop: '3px solid var(--brand-gold)' }}>
        <div className="card-body d-flex flex-column">
          <div className="d-flex justify-content-between align-items-start mb-2">
            <span className="badge" style={{ backgroundColor: 'var(--brand-gold)', color: '#1a1a1a' }}>
              <i className="bi bi-clock me-1"></i>Pre-Order
            </span>
            {item.estimated_harvest_start && (
              <small className="text-muted">
                <i className="bi bi-calendar3 me-1"></i>
                {new Date(item.estimated_harvest_start + 'T00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
              </small>
            )}
          </div>
          <h6 className="card-title" style={{ overflow: 'hidden', textOverflow: 'ellipsis', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>
            {item.variety || item.vegetable_type}
          </h6>
          <p className="text-muted small mb-1"><i className="bi bi-person"></i> {item.seller_name}</p>
          <div className="mt-auto">
            <div className="d-flex justify-content-between align-items-center">
              <div>
                {item.sale_price ? (
                  <><span className="fw-bold text-success fs-5">${item.sale_price.toFixed(2)}</span><small className="text-muted ms-1">/{item.price_unit || 'lb'}</small></>
                ) : (
                  <span className="text-muted fst-italic">Price TBD</span>
                )}
              </div>
              {item.distance !== undefined && item.distance !== null && (
                <small className="text-muted"><i className="bi bi-geo-alt"></i> {item.distance} mi</small>
              )}
            </div>
            <Link to={`/messages/new/${item.seller_id}`} className="btn btn-sm btn-outline-warning w-100 mt-2">
              <i className="bi bi-chat me-1"></i>Contact to Pre-Order
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function Browse() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [listings, setListings] = useState([]);
  const [preorders, setPreorders] = useState([]);
  const [categories, setCategories] = useState([]);
  const [pagination, setPagination] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const page = parseInt(searchParams.get('page') || '1');
  const type = searchParams.get('type') || '';

  useEffect(() => {
    listingsAPI.categories()
      .then(res => setCategories(res.data.categories))
      .catch(() => {});
  }, []);

  useEffect(() => {
    setLoading(true);
    setError(null);
    listingsAPI.browse({ page, type })
      .then(res => {
        setListings(res.data.listings);
        setPreorders(res.data.preorders || []);
        setPagination(res.data);
        setLoading(false);
      })
      .catch(() => {
        setLoading(false);
        setError('Failed to load listings. Please try again.');
      });
  }, [page, type]);

  const setFilter = (t) => {
    const p = new URLSearchParams();
    if (t) p.set('type', t);
    setSearchParams(p);
  };

  return (
    <>
      <h1 className="mb-3"><i className="bi bi-grid me-2"></i>Browse Produce</h1>
      <div className="mb-3">
        <select className="form-select w-auto d-inline-block" value={type} onChange={e => setFilter(e.target.value)}>
          <option value="">All Categories</option>
          {categories.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
        </select>
      </div>

      {error && <div className="alert alert-danger">{error}</div>}

      {loading ? (
        <div className="text-center py-5"><div className="spinner-border text-success"></div></div>
      ) : listings.length === 0 ? (
        <div className="text-center py-5">
          <i className="bi bi-search fs-1 text-muted"></i>
          <h5 className="mt-3 text-muted">No listings found</h5>
          <p className="text-muted">Try adjusting your filters or check back later.</p>
        </div>
      ) : (
        <>
          {preorders.length > 0 && (
            <div className="mb-4">
              <h5 className="mb-3" style={{ color: '#b45309' }}>
                <i className="bi bi-clock-history me-2"></i>Coming Soon — Pre-Order
                <span className="badge bg-warning text-dark ms-2" style={{ fontSize: '0.7rem' }}>{preorders.length}</span>
              </h5>
              <div className="row">{preorders.map(p => <PreorderCard key={p.id} item={p} />)}</div>
              {listings.length > 0 && <hr />}
            </div>
          )}
          {listings.length > 0 ? (
            <div className="row">{listings.map(l => <ListingCard key={l.id} listing={l} />)}</div>
          ) : preorders.length === 0 && (
            <div className="text-center py-5">
              <i className="bi bi-search fs-1 text-muted"></i>
              <h5 className="mt-3 text-muted">No listings found</h5>
              <p className="text-muted">Try adjusting your filters or check back later.</p>
            </div>
          )}
        </>
      )}

      {pagination.pages > 1 && (
        <nav className="mt-3">
          <ul className="pagination justify-content-center">
            <li className={`page-item ${!pagination.has_prev ? 'disabled' : ''}`}>
              <button className="page-link" disabled={!pagination.has_prev} onClick={() => setSearchParams({ page: page - 1, ...(type ? { type } : {}) })}>Previous</button>
            </li>
            {Array.from({ length: pagination.pages }, (_, i) => (
              <li key={i} className={`page-item ${page === i + 1 ? 'active' : ''}`}>
                <button className="page-link" onClick={() => setSearchParams({ page: i + 1, ...(type ? { type } : {}) })}>{i + 1}</button>
              </li>
            ))}
            <li className={`page-item ${!pagination.has_next ? 'disabled' : ''}`}>
              <button className="page-link" disabled={!pagination.has_next} onClick={() => setSearchParams({ page: page + 1, ...(type ? { type } : {}) })}>Next</button>
            </li>
          </ul>
        </nav>
      )}
    </>
  );
}
