import { useState, useRef, useEffect, useCallback } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../AuthContext';

export default function Navbar() {
  const { user, logout, cartCount, unreadCount } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  // Menu state
  const [mobileOpen, setMobileOpen] = useState(false);
  const [marketplaceOpen, setMarketplaceOpen] = useState(false);
  const [gardensOpen, setGardensOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);

  // Refs for click-outside detection
  const navRef = useRef(null);
  const marketplaceRef = useRef(null);
  const gardensRef = useRef(null);
  const profileRef = useRef(null);

  // Close all menus
  const closeAll = useCallback(() => {
    setMobileOpen(false);
    setMarketplaceOpen(false);
    setGardensOpen(false);
    setProfileOpen(false);
  }, []);

  // Close everything on route change
  useEffect(() => {
    closeAll();
  }, [location.pathname, closeAll]);

  // Click outside to close dropdowns and mobile menu
  useEffect(() => {
    function handleClickOutside(e) {
      if (navRef.current && !navRef.current.contains(e.target)) {
        closeAll();
      } else {
        // Close individual dropdowns if click is outside them
        if (marketplaceRef.current && !marketplaceRef.current.contains(e.target)) {
          setMarketplaceOpen(false);
        }
        if (gardensRef.current && !gardensRef.current.contains(e.target)) {
          setGardensOpen(false);
        }
        if (profileRef.current && !profileRef.current.contains(e.target)) {
          setProfileOpen(false);
        }
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [closeAll]);

  const handleLogout = async () => {
    closeAll();
    await logout();
    navigate('/');
  };

  // Toggle helpers that close sibling dropdowns
  const toggleMarketplace = () => {
    setMarketplaceOpen(prev => !prev);
    setGardensOpen(false);
    setProfileOpen(false);
  };

  const toggleGardens = () => {
    setGardensOpen(prev => !prev);
    setMarketplaceOpen(false);
    setProfileOpen(false);
  };

  const toggleProfile = () => {
    setProfileOpen(prev => !prev);
    setMarketplaceOpen(false);
    setGardensOpen(false);
  };

  const isGardenPage = ['/gardens', '/planting-calendar', '/harvest-forecast'].some(prefix => location.pathname.startsWith(prefix));

  const toggleMobile = () => {
    setMobileOpen(prev => !prev);
    // Reset dropdowns when toggling mobile
    setMarketplaceOpen(false);
    setGardensOpen(false);
    setProfileOpen(false);
  };

  return (
    <nav className={`yh-navbar sticky-top ${isGardenPage ? 'yh-navbar-garden' : ''}`} ref={navRef}>
      <div className="container">
        {/* Top bar: Brand + desktop dropdowns + hamburger */}
        <div className="navbar-top-bar">
          {/* Brand */}
          <Link className="navbar-brand" to="/" onClick={closeAll}>
            <i className="bi bi-flower1 me-2"></i>YardHarvest
          </Link>

          {/* Desktop nav items */}
          <div className="navbar-desktop-nav">
            {/* Marketplace dropdown */}
            <div className="nav-dropdown nav-dropdown-mkt" ref={marketplaceRef}>
              <button
                className="nav-dropdown-trigger"
                onClick={toggleMarketplace}
                aria-expanded={marketplaceOpen}
                aria-haspopup="true"
              >
                <i className="bi bi-shop me-1"></i>
                Marketplace
                <i className={`bi bi-chevron-down nav-chevron ${marketplaceOpen ? 'nav-chevron-open' : ''}`}></i>
              </button>
              <ul
                className={`nav-dropdown-menu ${marketplaceOpen ? 'nav-dropdown-menu-open' : ''}`}
                role="menu"
              >
                <li role="none">
                  <Link className="nav-dropdown-item" to="/browse" role="menuitem" onClick={closeAll}>
                    <i className="bi bi-grid me-2"></i>Browse
                  </Link>
                </li>
                <li role="none">
                  <Link className="nav-dropdown-item" to="/search" role="menuitem" onClick={closeAll}>
                    <i className="bi bi-search me-2"></i>Search
                  </Link>
                </li>
                <li role="none">
                  <Link className="nav-dropdown-item" to="/subscriptions" role="menuitem" onClick={closeAll}>
                    <i className="bi bi-box me-2"></i>Boxes
                  </Link>
                </li>
                <li role="none">
                  <Link className="nav-dropdown-item" to="/groups" role="menuitem" onClick={closeAll}>
                    <i className="bi bi-people me-2"></i>Groups
                  </Link>
                </li>
              </ul>
            </div>

            {/* Divider */}
            <div className="nav-product-divider"></div>

            {/* Gardens dropdown */}
            <div className="nav-dropdown nav-dropdown-garden" ref={gardensRef}>
              <button
                className="nav-dropdown-trigger nav-dropdown-trigger-garden"
                onClick={toggleGardens}
                aria-expanded={gardensOpen}
                aria-haspopup="true"
              >
                <i className="bi bi-tree me-1"></i>
                Gardens
                <i className={`bi bi-chevron-down nav-chevron ${gardensOpen ? 'nav-chevron-open' : ''}`}></i>
              </button>
              <ul
                className={`nav-dropdown-menu ${gardensOpen ? 'nav-dropdown-menu-open' : ''}`}
                role="menu"
              >
                <li role="none">
                  <Link className="nav-dropdown-item" to="/gardens" role="menuitem" onClick={closeAll}>
                    <i className="bi bi-tree me-2"></i>Explore Gardens
                  </Link>
                </li>
                <li role="none">
                  <Link className="nav-dropdown-item" to="/planting-calendar" role="menuitem" onClick={closeAll}>
                    <i className="bi bi-calendar3 me-2"></i>Planting Calendar
                  </Link>
                </li>
                <li role="none">
                  <Link className="nav-dropdown-item" to="/harvest-forecast" role="menuitem" onClick={closeAll}>
                    <i className="bi bi-graph-up me-2"></i>Harvest Forecast
                  </Link>
                </li>
              </ul>
            </div>

            {/* About link */}
            <Link className="nav-dropdown-trigger" to="/about" onClick={closeAll}>
              <i className="bi bi-info-circle me-1"></i>About
            </Link>
          </div>

          {/* Desktop user section */}
          <div className="navbar-desktop-user">
            {user ? (
              <>
                <Link className="nav-link" to="/messages" title="Messages" onClick={closeAll}>
                  <i className="bi bi-chat-dots"></i>
                  {unreadCount > 0 && (
                    <span className="badge bg-danger ms-1" style={{ fontSize: '0.65rem' }}>{unreadCount}</span>
                  )}
                </Link>
                <Link className="nav-link" to="/cart" title="Cart" onClick={closeAll}>
                  <i className="bi bi-cart3"></i>
                  {cartCount > 0 && (
                    <span className="badge bg-warning text-dark ms-1" style={{ fontSize: '0.65rem' }}>{cartCount}</span>
                  )}
                </Link>
                {user.is_admin && (
                  <Link className="nav-link" to="/admin" title="Admin" onClick={closeAll}>
                    <i className="bi bi-shield-lock" style={{ color: '#ffc107' }}></i>
                  </Link>
                )}

                {/* Profile dropdown */}
                <div className="nav-dropdown nav-dropdown-profile" ref={profileRef}>
                  <button
                    className="nav-dropdown-trigger nav-dropdown-trigger-profile"
                    onClick={toggleProfile}
                    aria-expanded={profileOpen}
                    aria-haspopup="true"
                  >
                    <i className="bi bi-person-circle me-1"></i>
                    {user.display_name || user.username}
                    <i className={`bi bi-chevron-down nav-chevron ${profileOpen ? 'nav-chevron-open' : ''}`}></i>
                  </button>
                  <ul
                    className={`nav-dropdown-menu nav-dropdown-menu-end ${profileOpen ? 'nav-dropdown-menu-open' : ''}`}
                    role="menu"
                  >
                    <li role="none">
                      <Link className="nav-dropdown-item" to={`/profile/${user.id}`} role="menuitem" onClick={closeAll}>
                        <i className="bi bi-person me-2"></i>My Profile
                      </Link>
                    </li>
                    <li role="none">
                      <Link className="nav-dropdown-item" to="/profile/edit" role="menuitem" onClick={closeAll}>
                        <i className="bi bi-pencil me-2"></i>Edit Profile
                      </Link>
                    </li>
                    <li role="none">
                      <Link className="nav-dropdown-item" to="/orders" role="menuitem" onClick={closeAll}>
                        <i className="bi bi-bag me-2"></i>My Orders
                      </Link>
                    </li>
                    <li role="none">
                      <Link className="nav-dropdown-item" to="/my-subscriptions" role="menuitem" onClick={closeAll}>
                        <i className="bi bi-box me-2"></i>My Subscriptions
                      </Link>
                    </li>
                    {user.can_sell && (
                      <>
                        <li role="none"><hr className="nav-dropdown-divider" /></li>
                        <li role="none">
                          <Link className="nav-dropdown-item" to="/dashboard" role="menuitem" onClick={closeAll}>
                            <i className="bi bi-speedometer2 me-2"></i>Seller Dashboard
                          </Link>
                        </li>
                        <li role="none">
                          <Link className="nav-dropdown-item" to="/my-listings" role="menuitem" onClick={closeAll}>
                            <i className="bi bi-list-ul me-2"></i>My Listings
                          </Link>
                        </li>
                        <li role="none">
                          <Link className="nav-dropdown-item" to="/seller/orders" role="menuitem" onClick={closeAll}>
                            <i className="bi bi-truck me-2"></i>Seller Orders
                          </Link>
                        </li>
                        <li role="none">
                          <Link className="nav-dropdown-item" to="/seller/subscriptions" role="menuitem" onClick={closeAll}>
                            <i className="bi bi-box-seam me-2"></i>Subscription Plans
                          </Link>
                        </li>
                        <li role="none">
                          <Link className="nav-dropdown-item" to="/my-planting-log" role="menuitem" onClick={closeAll}>
                            <i className="bi bi-journal-text me-2"></i>Planting Log
                          </Link>
                        </li>
                      </>
                    )}
                    <li role="none"><hr className="nav-dropdown-divider" /></li>
                    <li role="none">
                      <Link className="nav-dropdown-item" to="/gardens/my-gardens" role="menuitem" onClick={closeAll}>
                        <i className="bi bi-tree me-2" style={{ color: '#7c4a1e' }}></i>My Gardens
                      </Link>
                    </li>
                    <li role="none"><hr className="nav-dropdown-divider" /></li>
                    <li role="none">
                      <button className="nav-dropdown-item nav-dropdown-item-danger" onClick={handleLogout} role="menuitem">
                        <i className="bi bi-box-arrow-right me-2"></i>Logout
                      </button>
                    </li>
                  </ul>
                </div>
              </>
            ) : (
              <>
                <Link className="nav-link" to="/login" onClick={closeAll}>Login</Link>
                <Link className="nav-link nav-link-register" to="/register" onClick={closeAll}>
                  Register
                </Link>
              </>
            )}
          </div>

          {/* Hamburger button (mobile only) */}
          <button
            className="navbar-hamburger"
            onClick={toggleMobile}
            aria-label="Toggle navigation"
            aria-expanded={mobileOpen}
          >
            <i className={`bi ${mobileOpen ? 'bi-x-lg' : 'bi-list'}`}></i>
          </button>
        </div>

        {/* Mobile slide-down panel */}
        <div className={`navbar-mobile-panel ${mobileOpen ? 'navbar-mobile-panel-open' : ''}`}>
          {/* Marketplace section */}
          <div className="mobile-section">
            <div className="mobile-section-header mobile-section-header-mkt">
              <i className="bi bi-shop me-2"></i>Marketplace
            </div>
            <Link className="mobile-nav-link" to="/browse" onClick={closeAll}>
              <i className="bi bi-grid me-2"></i>Browse
            </Link>
            <Link className="mobile-nav-link" to="/search" onClick={closeAll}>
              <i className="bi bi-search me-2"></i>Search
            </Link>
            <Link className="mobile-nav-link" to="/subscriptions" onClick={closeAll}>
              <i className="bi bi-box me-2"></i>Boxes
            </Link>
            <Link className="mobile-nav-link" to="/groups" onClick={closeAll}>
              <i className="bi bi-people me-2"></i>Groups
            </Link>
          </div>

          {/* Gardens section */}
          <div className="mobile-section">
            <div className="mobile-section-header mobile-section-header-garden">
              <i className="bi bi-tree me-2"></i>Gardens
            </div>
            <Link className="mobile-nav-link" to="/gardens" onClick={closeAll}>
              <i className="bi bi-tree me-2"></i>Explore Gardens
            </Link>
            <Link className="mobile-nav-link" to="/planting-calendar" onClick={closeAll}>
              <i className="bi bi-calendar3 me-2"></i>Planting Calendar
            </Link>
            <Link className="mobile-nav-link" to="/harvest-forecast" onClick={closeAll}>
              <i className="bi bi-graph-up me-2"></i>Harvest Forecast
            </Link>
          </div>

          {/* About section */}
          <div className="mobile-section">
            <Link className="mobile-nav-link" to="/about" onClick={closeAll}>
              <i className="bi bi-info-circle me-2"></i>About
            </Link>
          </div>

          {/* User section */}
          <div className="mobile-section">
            {user ? (
              <>
                <div className="mobile-section-header">
                  <i className="bi bi-person-circle me-2"></i>
                  {user.display_name || user.username}
                </div>
                <Link className="mobile-nav-link" to="/messages" onClick={closeAll}>
                  <i className="bi bi-chat-dots me-2"></i>Messages
                  {unreadCount > 0 && (
                    <span className="badge bg-danger ms-2" style={{ fontSize: '0.65rem' }}>{unreadCount}</span>
                  )}
                </Link>
                <Link className="mobile-nav-link" to="/cart" onClick={closeAll}>
                  <i className="bi bi-cart3 me-2"></i>Cart
                  {cartCount > 0 && (
                    <span className="badge bg-warning text-dark ms-2" style={{ fontSize: '0.65rem' }}>{cartCount}</span>
                  )}
                </Link>
                <Link className="mobile-nav-link" to={`/profile/${user.id}`} onClick={closeAll}>
                  <i className="bi bi-person me-2"></i>My Profile
                </Link>
                <Link className="mobile-nav-link" to="/profile/edit" onClick={closeAll}>
                  <i className="bi bi-pencil me-2"></i>Edit Profile
                </Link>
                <Link className="mobile-nav-link" to="/orders" onClick={closeAll}>
                  <i className="bi bi-bag me-2"></i>My Orders
                </Link>
                <Link className="mobile-nav-link" to="/my-subscriptions" onClick={closeAll}>
                  <i className="bi bi-box me-2"></i>My Subscriptions
                </Link>
                {user.can_sell && (
                  <>
                    <div className="mobile-nav-divider"></div>
                    <Link className="mobile-nav-link" to="/dashboard" onClick={closeAll}>
                      <i className="bi bi-speedometer2 me-2"></i>Seller Dashboard
                    </Link>
                    <Link className="mobile-nav-link" to="/my-listings" onClick={closeAll}>
                      <i className="bi bi-list-ul me-2"></i>My Listings
                    </Link>
                    <Link className="mobile-nav-link" to="/seller/orders" onClick={closeAll}>
                      <i className="bi bi-truck me-2"></i>Seller Orders
                    </Link>
                    <Link className="mobile-nav-link" to="/seller/subscriptions" onClick={closeAll}>
                      <i className="bi bi-box-seam me-2"></i>Subscription Plans
                    </Link>
                    <Link className="mobile-nav-link" to="/my-planting-log" onClick={closeAll}>
                      <i className="bi bi-journal-text me-2"></i>Planting Log
                    </Link>
                  </>
                )}
                <div className="mobile-nav-divider"></div>
                <Link className="mobile-nav-link" to="/gardens/my-gardens" onClick={closeAll}>
                  <i className="bi bi-tree me-2" style={{ color: '#7c4a1e' }}></i>My Gardens
                </Link>
                {user.is_admin && (
                  <Link className="mobile-nav-link" to="/admin" onClick={closeAll}>
                    <i className="bi bi-shield-lock me-2" style={{ color: '#ffc107' }}></i>Admin
                  </Link>
                )}
                <div className="mobile-nav-divider"></div>
                <button className="mobile-nav-link mobile-nav-link-danger" onClick={handleLogout}>
                  <i className="bi bi-box-arrow-right me-2"></i>Logout
                </button>
              </>
            ) : (
              <>
                <Link className="mobile-nav-link" to="/login" onClick={closeAll}>
                  <i className="bi bi-box-arrow-in-right me-2"></i>Login
                </Link>
                <Link className="mobile-nav-link mobile-nav-link-register" to="/register" onClick={closeAll}>
                  <i className="bi bi-person-plus me-2"></i>Register
                </Link>
              </>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}
