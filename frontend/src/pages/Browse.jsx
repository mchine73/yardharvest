import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { listingsAPI } from '../api';
import ListingCard from '../components/ListingCard';

export default function Browse() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [listings, setListings] = useState([]);
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
        <div className="row">{listings.map(l => <ListingCard key={l.id} listing={l} />)}</div>
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
