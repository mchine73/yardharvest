import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { listingsAPI } from '../api';
import ListingCard from '../components/ListingCard';

export default function Home() {
  const [listings, setListings] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listingsAPI.featured().then(res => {
      setListings(res.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  return (
    <>
      <div className="hero-section text-center mb-4">
        <h1 className="display-4 fw-bold"><i className="bi bi-flower1 me-2"></i>YardHarvest</h1>
        <p className="lead mb-4">Fresh produce from your neighbor's garden — as local as it gets</p>
        <div className="d-flex justify-content-center gap-3">
          <Link to="/browse" className="btn btn-light btn-lg"><i className="bi bi-grid me-2"></i>Browse Produce</Link>
          <Link to="/search" className="btn btn-outline-light btn-lg"><i className="bi bi-search me-2"></i>Search Nearby</Link>
        </div>
      </div>

      <h2 className="mb-3"><i className="bi bi-star me-2"></i>Featured Listings</h2>
      {loading ? (
        <div className="text-center py-5"><div className="spinner-border text-success"></div></div>
      ) : listings.length === 0 ? (
        <p className="text-muted">No listings yet. Be the first to sell!</p>
      ) : (
        <div className="row">{listings.map(l => <ListingCard key={l.id} listing={l} />)}</div>
      )}

      <div className="row mt-5 text-center">
        <div className="col-md-3"><div className="p-3"><i className="bi bi-basket2 fs-1 text-success"></i><h5 className="mt-2">List</h5><p className="text-muted">Sellers list their garden surplus</p></div></div>
        <div className="col-md-3"><div className="p-3"><i className="bi bi-binoculars fs-1 text-success"></i><h5 className="mt-2">Browse</h5><p className="text-muted">Buyers find produce nearby</p></div></div>
        <div className="col-md-3"><div className="p-3"><i className="bi bi-chat-dots fs-1 text-success"></i><h5 className="mt-2">Connect</h5><p className="text-muted">Message sellers directly</p></div></div>
        <div className="col-md-3"><div className="p-3"><i className="bi bi-bag-check fs-1 text-success"></i><h5 className="mt-2">Harvest</h5><p className="text-muted">Pick up fresh, local produce</p></div></div>
      </div>
    </>
  );
}
