import { Link } from 'react-router-dom';

export default function NotFound() {
  return (
    <div>
      <div
        className="hero-section text-center"
        style={{
          padding: '4rem 2rem',
          borderRadius: '16px',
          marginBottom: '2rem',
        }}
      >
        <div style={{ fontSize: '4rem', marginBottom: '0.5rem' }}>
          <i className="bi bi-signpost-split"></i>
        </div>
        <h1 className="display-4 fw-bold mb-3">Page Not Found</h1>
        <p className="lead mb-0" style={{ opacity: 0.9 }}>
          Sorry, we couldn't find the page you were looking for.
        </p>
      </div>

      <div className="text-center py-4">
        <p className="text-muted mb-4" style={{ fontSize: '1.1rem' }}>
          The page may have been moved, removed, or you may have mistyped the address.
        </p>
        <div className="d-flex justify-content-center gap-3 flex-wrap">
          <Link to="/" className="btn btn-success btn-lg px-4">
            <i className="bi bi-house me-2"></i>Go Home
          </Link>
          <Link to="/gardens" className="btn btn-outline-success btn-lg px-4">
            <i className="bi bi-tree me-2"></i>Browse Gardens
          </Link>
        </div>
      </div>
    </div>
  );
}
