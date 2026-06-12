import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { listingsAPI } from '../api';
import { useSiteConfig } from '../SiteConfigContext';
import { useAuth } from '../AuthContext';
import ListingCard from '../components/ListingCard';

export default function Home() {
  const { marketplaceEnabled } = useSiteConfig();
  const { user } = useAuth();
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
        <h1 className="display-4 fw-bold"><img src="/sunflower.svg" alt="" className="me-2" style={{ height: '1.1em', width: '1.1em', borderRadius: '0.18em', verticalAlign: '-0.15em' }} />YardHarvest</h1>
        {marketplaceEnabled ? (
          <>
            <p className="lead mb-4">Fresh from your neighbor's garden — as local as it gets</p>
            <div className="d-flex justify-content-center gap-3">
              <Link to="/browse" className="btn btn-light btn-lg"><i className="bi bi-grid me-2"></i>Browse Produce</Link>
              <Link to="/search" className="btn btn-outline-light btn-lg"><i className="bi bi-search me-2"></i>Search Nearby</Link>
            </div>
          </>
        ) : (
          <>
            <p className="lead mb-2">Less admin, more garden</p>
            <p className="mb-4" style={{ opacity: 0.85, maxWidth: 640, margin: '0 auto' }}>
              Plots, dues, volunteers, events, and impact reporting for community gardens —
              from a single garden to a citywide network.
            </p>
            <div className="d-flex justify-content-center gap-3 flex-wrap">
              <Link to="/gardens" className="btn btn-light btn-lg"><i className="bi bi-tree me-2"></i>Explore Gardens</Link>
              <Link to="/pricing" className="btn btn-outline-light btn-lg"><i className="bi bi-clipboard-check me-2"></i>For Organizers</Link>
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
            <div className="text-center py-4">
              <i className="bi bi-basket2 fs-2 text-muted"></i>
              <p className="text-muted mt-2">No listings yet — be the first to share your harvest!</p>
              <Link to="/listings/create" className="btn btn-sm btn-outline-success">Create a Listing</Link>
            </div>
          ) : (
            <div className="row">{listings.map(l => <ListingCard key={l.id} listing={l} />)}</div>
          )}
        </>
      )}

      {marketplaceEnabled ? (
        <div className="row mt-5 text-center">
          <div className="col-md-3"><div className="p-3"><i className="bi bi-basket2 fs-1 text-success"></i><h5 className="mt-2">List</h5><p className="text-muted">Growers share their garden harvest</p></div></div>
          <div className="col-md-3"><div className="p-3"><i className="bi bi-binoculars fs-1 text-success"></i><h5 className="mt-2">Browse</h5><p className="text-muted">Buyers find produce nearby</p></div></div>
          <div className="col-md-3"><div className="p-3"><i className="bi bi-chat-dots fs-1 text-success"></i><h5 className="mt-2">Connect</h5><p className="text-muted">Message growers directly</p></div></div>
          <div className="col-md-3"><div className="p-3"><i className="bi bi-bag-check fs-1 text-success"></i><h5 className="mt-2">Harvest</h5><p className="text-muted">Pick up fresh, local produce</p></div></div>
        </div>
      ) : (
        <>
          <div className="row mt-5 text-center">
            <div className="col-md-3"><div className="p-3"><i className="bi bi-clipboard-check fs-1 text-success"></i><h5 className="mt-2">Organize</h5><p className="text-muted">Plots, members, dues, and waitlists in one place</p></div></div>
            <div className="col-md-3"><div className="p-3"><i className="bi bi-people fs-1 text-success"></i><h5 className="mt-2">Coordinate</h5><p className="text-muted">Events, volunteer shifts, and announcements</p></div></div>
            <div className="col-md-3"><div className="p-3"><i className="bi bi-flower2 fs-1 text-success"></i><h5 className="mt-2">Grow</h5><p className="text-muted">Planting guides and harvest tracking for members</p></div></div>
            <div className="col-md-3"><div className="p-3"><i className="bi bi-graph-up-arrow fs-1 text-success"></i><h5 className="mt-2">Show Impact</h5><p className="text-muted">Harvest, participation, and donation data for funders</p></div></div>
          </div>

          {/* Networks & city programs */}
          <div className="text-center mt-4 p-4" style={{ background: 'linear-gradient(135deg, #166f4c, #1d8a5f)', borderRadius: '14px', color: 'white' }}>
            <h4 className="fw-bold mb-2"><i className="bi bi-building me-2"></i>Run a garden network or city program?</h4>
            <p className="mb-3" style={{ opacity: 0.9, maxWidth: 640, margin: '0 auto' }}>
              Manage every garden from one place — volume pricing per garden, online dues collection,
              and network-wide impact reporting for boards, funders, and councils.
            </p>
            <Link to="/pricing" className="btn btn-light fw-semibold" style={{ color: '#166f4c' }}>
              <i className="bi bi-arrow-right-circle me-2"></i>See Network Pricing
            </Link>
          </div>
        </>
      )}

      {!user && (
        <div className="text-center mt-4 p-4" style={{ background: '#ecf7f1', borderRadius: '12px' }}>
          <h3 className="fw-bold" style={{ color: '#166f4c' }}>Ready to get started?</h3>
          <p className="text-muted">Join your local gardening community today.</p>
          <Link to="/register" className="btn btn-success btn-lg">
            <i className="bi bi-person-plus me-2"></i>Create Free Account
          </Link>
        </div>
      )}
    </>
  );
}
