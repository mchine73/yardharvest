import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { listingsAPI } from '../api';
import { useSiteConfig } from '../SiteConfigContext';
import { useAuth } from '../AuthContext';
import ListingCard from '../components/ListingCard';
import Seo from '../components/Seo';

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

  // Gentle reveal-on-scroll for the hero + feature cards. The hidden state is
  // scoped under body.yh-animate (added here), so it only applies when this
  // effect runs — content is never left hidden if JS/IO is unavailable.
  useEffect(() => {
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduce || !('IntersectionObserver' in window)) return;
    document.body.classList.add('yh-animate');
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -8% 0px' });
    document.querySelectorAll('.yh-reveal').forEach((el) => io.observe(el));
    return () => { io.disconnect(); document.body.classList.remove('yh-animate'); };
  }, [marketplaceEnabled, user, loading]);

  const features = marketplaceEnabled ? [
    { icon: 'bi-basket2', title: 'List', body: 'Growers share their garden harvest', lime: false },
    { icon: 'bi-binoculars', title: 'Browse', body: 'Buyers find produce nearby', lime: true },
    { icon: 'bi-chat-dots', title: 'Connect', body: 'Message growers directly', lime: false },
    { icon: 'bi-bag-check', title: 'Harvest', body: 'Pick up fresh, local produce', lime: false },
  ] : [
    { icon: 'bi-clipboard-check', title: 'Organize', body: 'Plots, members, dues and waitlists in one place', lime: false },
    { icon: 'bi-people', title: 'Coordinate', body: 'Events, volunteer shifts and announcements', lime: true },
    { icon: 'bi-flower2', title: 'Grow', body: 'Planting guides and harvest tracking for members', lime: false },
    { icon: 'bi-graph-up-arrow', title: 'Show impact', body: 'Harvest, participation and donation data for funders', lime: false },
  ];

  return (
    <>
      <Seo
        path="/"
        jsonLd={{
          '@context': 'https://schema.org',
          '@type': 'Organization',
          name: 'YardHarvest',
          url: 'https://www.yardharvest.app/',
          logo: 'https://www.yardharvest.app/og-image.png',
        }}
      />
      {/* Hero */}
      <div className="text-center py-5 yh-hero-glow">
        <span className="yh-badge-lime mb-3 yh-reveal">
          <b>New</b><span>{marketplaceEnabled ? 'Fresh picks near you' : 'Garden Pro is here'}</span>
        </span>
        {marketplaceEnabled ? (
          <>
            <h1 className="yh-hero-title">Fresh from your<br />neighbor's <span className="yh-highlight">garden</span></h1>
            <p className="yh-hero-sub">As local as it gets — buy and sell home-grown produce with the people right around you.</p>
            <div className="d-flex justify-content-center gap-2 flex-wrap">
              <Link to="/browse" className="yh-btn-dark"><i className="bi bi-grid"></i>Browse produce</Link>
              <Link to="/search" className="yh-btn-ghost"><i className="bi bi-search"></i>Search nearby</Link>
            </div>
          </>
        ) : (
          <>
            <h1 className="yh-hero-title yh-reveal" style={{ '--rd': '0.1s' }}>Less admin,<br />more <span className="yh-highlight">garden</span>.</h1>
            <p className="yh-hero-sub yh-reveal" style={{ '--rd': '0.24s' }}>Plots, dues, volunteers, events and funder-ready impact — one home for the people who run community gardens.</p>
            <div className="d-flex justify-content-center gap-2 flex-wrap yh-reveal" style={{ '--rd': '0.38s' }}>
              <Link to="/gardens" className="yh-btn-dark"><i className="bi bi-tree"></i>Explore gardens</Link>
              <Link to="/pricing" className="yh-btn-ghost"><i className="bi bi-clipboard-check"></i>For organizers</Link>
            </div>
            <p className="yh-hero-stats yh-reveal" style={{ '--rd': '0.52s' }}>Free 14-day trial · No credit card · Cancel anytime</p>
          </>
        )}
      </div>

      {marketplaceEnabled && (
        <>
          <h2 className="h4 mb-3"><i className="bi bi-star me-2"></i>Featured listings</h2>
          {error ? (
            <div className="alert alert-warning"><i className="bi bi-exclamation-triangle me-2"></i>{error}</div>
          ) : loading ? (
            <div className="text-center py-5"><div className="spinner-border text-success"></div></div>
          ) : listings.length === 0 ? (
            <div className="text-center py-4">
              <i className="bi bi-basket2 fs-2 text-muted"></i>
              <p className="text-muted mt-2">No listings yet — be the first to share your harvest!</p>
              <Link to="/listings/create" className="yh-btn-ghost">Create a listing</Link>
            </div>
          ) : (
            <div className="row">{listings.map(l => <ListingCard key={l.id} listing={l} />)}</div>
          )}
        </>
      )}

      {/* Feature cards */}
      <div className="row g-3 mt-4">
        {features.map((f, i) => (
          <div className="col-6 col-md-3" key={f.title}>
            <div className="yh-feature-card yh-reveal text-center" style={{ '--rd': `${i * 0.15}s` }}>
              <span className="yh-feature-num">{i + 1}</span>
              <span className={`yh-ficon mx-auto${f.lime ? ' lime' : ''}`}><i className={`bi ${f.icon}`}></i></span>
              <p className="fw-medium mb-1">{f.title}</p>
              <p className="mb-0" style={{ color: 'var(--yh-muted)', fontSize: '0.9rem' }}>{f.body}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Product showcase — garden admin portal */}
      {!marketplaceEnabled && (
        <div className="text-center mt-5">
          <span className="yh-badge-lime mb-3">Garden admin portal</span>
          <h2 className="h3 mb-2 mt-2">One dashboard to run your whole garden</h2>
          <p className="mb-4" style={{ color: 'var(--yh-muted)', maxWidth: 620, margin: '0 auto' }}>
            Plots, dues, events, volunteers, messages and funder-ready impact — all managed from one simple place.
          </p>
          <figure className="mb-0 yh-reveal" style={{
            maxWidth: 980, margin: '0 auto',
            borderRadius: 16, overflow: 'hidden',
            border: '1px solid var(--yh-border, #e6e8e0)',
            boxShadow: '0 18px 50px rgba(20,40,20,0.14)',
          }}>
            <img src="/garden-admin-preview.png" loading="lazy"
                 alt="YardHarvest garden admin portal dashboard showing plots, events, volunteers and quick actions"
                 style={{ width: '100%', height: 'auto', display: 'block' }} />
          </figure>
        </div>
      )}

      {/* Networks & city programs (garden mode) */}
      {!marketplaceEnabled && (
        <div className="yh-band-dark text-center mt-5 p-4 p-md-5 yh-reveal">
          <h2 className="h3 mb-2" style={{ color: '#fff' }}>Run a garden network or city program?</h2>
          <p className="mb-3" style={{ color: 'rgba(255,255,255,0.7)', maxWidth: 600, margin: '0 auto' }}>
            Manage every garden from one place — volume pricing per garden, online dues collection,
            and network-wide impact reporting for boards, funders and councils.
          </p>
          <Link to="/pricing" className="yh-btn-lime"><i className="bi bi-arrow-right"></i>See network pricing</Link>
        </div>
      )}

      {/* Final CTA */}
      {!user && (
        <div className="yh-band-lime text-center mt-4 p-4 p-md-5 yh-reveal">
          <h2 className="h3 mb-2">Ready to get started?</h2>
          <p className="mb-3" style={{ color: '#2e3a1a' }}>Set up your garden in minutes. No card required for the trial.</p>
          <Link to="/register" className="yh-btn-dark"><i className="bi bi-person-plus"></i>Create free account</Link>
        </div>
      )}
    </>
  );
}
