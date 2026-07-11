import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { useSiteConfig } from '../SiteConfigContext';

// Garden-mode pages, ordered by operator frequency. The dormant marketplace
// pages collapse under one dropdown that renders only when the marketplace
// is enabled (they stay URL-reachable either way).
const LINKS = [
  { to: '/admin', label: 'Dashboard', end: true },
  { to: '/admin/gardens', label: 'Gardens' },
  { to: '/admin/booking', label: 'Booking' },
  { to: '/admin/users', label: 'Users' },
  { to: '/admin/analytics', label: 'Analytics' },
  { to: '/admin/pricing', label: 'Pricing' },
  { to: '/admin/email-settings', label: 'Communication' },
];
const MKT_LINKS = [
  { to: '/admin/listings', label: 'Listings' },
  { to: '/admin/orders', label: 'Orders' },
  { to: '/admin/refunds', label: 'Refunds' },
  { to: '/admin/promos', label: 'Promos' },
  { to: '/admin/stats', label: 'Marketplace P&L' },
];

const pill = ({ isActive }) =>
  `btn btn-sm ${isActive ? 'btn-dark' : 'btn-outline-secondary'} rounded-pill`;

/**
 * Shared admin page header: back arrow + title row (with an optional `right`
 * slot for page controls) and, always, the section subnav below it — the
 * console previously had NO lateral navigation, so every hop between two
 * admin pages went page -> back -> hub -> page.
 *
 * backTo defaults to '/admin' (navigate(-1) broke from bookmarks/new tabs);
 * the arrow hides when it would point at the current page.
 */
export default function AdminHeader({ title, icon, backTo = '/admin', right }) {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const { marketplaceEnabled } = useSiteConfig();
  const showBack = backTo !== pathname;

  return (
    <div className="mb-4">
      <div className="d-flex align-items-center flex-wrap gap-2">
        {showBack && (
          <button
            className="btn btn-outline-secondary me-2 d-flex align-items-center justify-content-center"
            onClick={() => navigate(backTo)}
            title="Go back"
            style={{ width: '38px', height: '38px', borderRadius: '50%', padding: 0 }}
          >
            <i className="bi bi-arrow-left"></i>
          </button>
        )}
        <h2 className="mb-0 fw-bold">
          {icon && <i className={`bi ${icon} me-2`}></i>}
          {title}
        </h2>
        {right && <div className="ms-auto d-flex align-items-center flex-wrap gap-2">{right}</div>}
      </div>
      <nav className="d-flex flex-wrap gap-1 mt-2" aria-label="Admin sections">
        {LINKS.map((l) => (
          <NavLink key={l.to} to={l.to} end={l.end} className={pill}>
            {l.label}
          </NavLink>
        ))}
        {marketplaceEnabled && (
          <div className="btn-group btn-group-sm">
            <button className="btn btn-sm btn-outline-secondary rounded-pill dropdown-toggle"
                    data-bs-toggle="dropdown">
              Marketplace
            </button>
            <ul className="dropdown-menu">
              {MKT_LINKS.map((l) => (
                <li key={l.to}>
                  <NavLink className="dropdown-item" to={l.to}>{l.label}</NavLink>
                </li>
              ))}
            </ul>
          </div>
        )}
      </nav>
    </div>
  );
}
