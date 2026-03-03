import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { listingsAPI } from '../api';
import { useSiteConfig } from '../SiteConfigContext';
import ListingCard from '../components/ListingCard';

export default function Home() {
  const { marketplaceEnabled } = useSiteConfig();
  const [listings, setListings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    // Try to get browser geolocation for proximity-based featured listings
    const fetchFeatured = (lat, lon) => {
      const params = {};
      if (lat != null && lon != null) { params.lat = lat; params.lon = lon; }
      listingsAPI.featured(params).then(res => {
        setListings(res.data);
        setLoading(false);
      }).catch(() => { setLoading(false); setError('Unable to load featured listings.'); });
    };

    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        pos => fetchFeatured(pos.coords.latitude, pos.coords.longitude),
        () => fetchFeatured(null, null),  // denied or error — no geo
        { timeout: 5000, maximumAge: 300000 }
      );
    } else {
      fetchFeatured(null, null);
    }
  }, []);

  return (
    <>
      <div className="hero-section text-center mb-4">
        <h1 className="display-4 fw-bold"><i className="bi bi-flower1 me-2"></i>YardHarvest</h1>
        {marketplaceEnabled ? (
          <>
            <p className="lead mb-4">Fresh produce from your neighbor's garden — as local as it gets</p>
            <div className="d-flex justify-content-center gap-3">
              <Link to="/browse" className="btn btn-light btn-lg"><i className="bi bi-grid me-2"></i>Browse Produce</Link>
              <Link to="/search" className="btn btn-outline-light btn-lg"><i className="bi bi-search me-2"></i>Search Nearby</Link>
            </div>
          </>
        ) : (
          <>
            <p className="lead mb-4">Community garden management — grow together, share locally</p>
            <div className="d-flex justify-content-center gap-3">
              <Link to="/gardens" className="btn btn-light btn-lg"><i className="bi bi-tree me-2"></i>Explore Gardens</Link>
              <Link to="/planting-calendar" className="btn btn-outline-light btn-lg"><i className="bi bi-calendar3 me-2"></i>Planting Calendar</Link>
            </div>
          </>
        )}
      </div>

      {marketplaceEnabled && (
        <>
          <h2 className="mb-3"><i className="bi bi-star me-2"></i>Featured Listings</h2>
          {error ? (
            <div className="alert alert-warning"><i className="bi bi-exclamation-triangle me-2"></i>{error}</div>
          ) : loading ? (
            <div className="text-center py-5"><div className="spinner-border text-success"></div></div>
          ) : listings.length === 0 ? (
            <p className="text-muted">No listings yet. Be the first to sell!</p>
          ) : (
            <div className="row">{listings.map(l => <ListingCard key={l.id} listing={l} />)}</div>
          )}
        </>
      )}

      {marketplaceEnabled ? (
        <div className="row mt-5 text-center">
          <div className="col-md-3"><div className="p-3"><i className="bi bi-basket2 fs-1 text-success"></i><h5 className="mt-2">List</h5><p className="text-muted">Sellers list their garden surplus</p></div></div>
          <div className="col-md-3"><div className="p-3"><i className="bi bi-binoculars fs-1 text-success"></i><h5 className="mt-2">Browse</h5><p className="text-muted">Buyers find produce nearby</p></div></div>
          <div className="col-md-3"><div className="p-3"><i className="bi bi-chat-dots fs-1 text-success"></i><h5 className="mt-2">Connect</h5><p className="text-muted">Message sellers directly</p></div></div>
          <div className="col-md-3"><div className="p-3"><i className="bi bi-bag-check fs-1 text-success"></i><h5 className="mt-2">Harvest</h5><p className="text-muted">Pick up fresh, local produce</p></div></div>
        </div>
      ) : (
        <div className="row mt-5 text-center">
          <div className="col-md-3"><div className="p-3"><i className="bi bi-binoculars fs-1 text-success"></i><h5 className="mt-2">Find</h5><p className="text-muted">Discover community gardens near you</p></div></div>
          <div className="col-md-3"><div className="p-3"><i className="bi bi-flag fs-1 text-success"></i><h5 className="mt-2">Join</h5><p className="text-muted">Reserve a plot and start growing</p></div></div>
          <div className="col-md-3"><div className="p-3"><i className="bi bi-flower2 fs-1 text-success"></i><h5 className="mt-2">Grow</h5><p className="text-muted">Get planting guides and harvest tracking</p></div></div>
          <div className="col-md-3"><div className="p-3"><i className="bi bi-people fs-1 text-success"></i><h5 className="mt-2">Share</h5><p className="text-muted">Connect with fellow gardeners</p></div></div>
        </div>
      )}
    </>
  );
}
