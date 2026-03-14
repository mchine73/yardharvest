import { useState, useRef, useEffect, useCallback } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../AuthContext';
import { useSiteConfig } from '../SiteConfigContext';
import { notificationsAPI } from '../api';

export default function Navbar() {
  const { user, logout, cartCount, unreadCount, notifCount, setNotifCount } = useAuth();
  const { marketplaceEnabled } = useSiteConfig();
  const navigate = useNavigate();
  const location = useLocation();

  // Menu state
  const [mobileOpen, setMobileOpen] = useState(false);
  const [marketplaceOpen, setMarketplaceOpen] = useState(false);
  const [gardensOpen, setGardensOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [notifLoading, setNotifLoading] = useState(false);

  // Refs for click-outside detection
  const navRef = useRef(null);
  const marketplaceRef = useRef(null);
  const gardensRef = useRef(null);
  const profileRef = useRef(null);
  const notifRef = useRef(null);

  // Close all menus
  const closeAll = useCallback(() => {
    setMobileOpen(false);
    setMarketplaceOpen(false);
    setGardensOpen(false);
    setProfileOpen(false);
    setNotifOpen(false);
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
        if (marketplaceRef.current && !marketplaceRef.current.contains(e.target)) {
          setMarketplaceOpen(false);
        }
        if (gardensRef.current && !gardensRef.current.contains(e.target)) {
          setGardensOpen(false);
        }
        if (profileRef.current && !profileRef.current.contains(e.target)) {
          setProfileOpen(false);
        }
        if (notifRef.current && !notifRef.current.contains(e.target)) {
          setNotifOpen(false);
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

  const toggleMarketplace = () => {
    setMarketplaceOpen(prev => !prev);
    setGardensOpen(false);
    setProfileOpen(false);
    setNotifOpen(false);
  };

  const toggleGardens = () => {
    setGardensOpen(prev => !prev);
    setMarketplaceOpen(false);
    setProfileOpen(false);
    setNotifOpen(false);
  };

  const toggleProfile = () => {
    setProfileOpen(prev => !prev);
    setMarketplaceOpen(false);
    setGardensOpen(false);
    setNotifOpen(false);
  };

  const toggleNotifications = () => {
    const opening = !notifOpen;
    setNotifOpen(opening);
    setMarketplaceOpen(false);
    setGardensOpen(false);
    setProfileOpen(false);
    if (opening) loadNotifications();
  };

  const loadNotifications = async () => {
    setNotifLoading(true);
    try {
      const res = await notificationsAPI.list({ per_page: 10 });
      setNotifications(res.data.notifications || []);
    } catch { /* ignore */ }
    setNotifLoading(false);
  };

  const handleMarkAllRead = async () => {
    try {
      await notificationsAPI.markAllRead();
      setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
      setNotifCount(0);
    } catch { /* ignore */ }
  };

  const handleNotifClick = async (notif) => {
    if (!notif.is_read) {
      try {
        await notificationsAPI.markRead(notif.id);
        setNotifications(prev => prev.map(n => n.id === notif.id ? { ...n, is_read: true } : n));
        setNotifCount(prev => Math.max(0, prev - 1));
      } catch { /* ignore */ }
    }
    closeAll();
    if (notif.link) navigate(notif.link);
  };

  const timeAgo = (dateStr) => {
    if (!dateStr) return '';
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    return `${days}d ago`;
  };

  const NOTIF_ICONS = {
    plot_reserved: 'bi-flag text-warning',
    plot_confirmed: 'bi-check-circle text-success',
    plot_declined: 'bi-x-circle text-danger',
    announcement: 'bi-megaphone text-primary',
    message: 'bi-chat-dots text-info',
    shift_signup: 'bi-people text-success',
    dues_reminder: 'bi-cash-stack text-warning',
    waitlist_approved: 'bi-check2-circle text-success',
    waitlist_declined: 'bi-x-circle text-danger',
    harvest_ready: 'bi-basket2 text-success',
  };

  const toggleMobile = () => {
    setMobileOpen(prev => !prev);
    setMarketplaceOpen(false);
    setGardensOpen(false);
    setProfileOpen(false);
    setNotifOpen(false);
  };

  return (
    <nav className="yh-navbar sticky-top" ref={navRef}>
      <div className="container">
        <div className="navbar-top-bar">
          <Link className="navbar-brand" to="/" onClick={closeAll}>
            <i className="bi bi-flower1 me-2"></i>YardHarvest
          </Link>

          <div className="navbar-desktop-nav">
            {marketplaceEnabled && (
              <>
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
                  <ul className={`nav-dropdown-menu ${marketplaceOpen ? 'nav-dropdown-menu-open' : ''}`} role="menu">
                    <li role="none"><Link className="nav-dropdown-item" to="/browse" role="menuitem" onClick={closeAll}><i className="bi bi-grid me-2"></i>Browse</Link></li>
                    <li role="none"><Link className="nav-dropdown-item" to="/search" role="menuitem" onClick={closeAll}><i className="bi bi-search me-2"></i>Search</Link></li>
                    <li role="none"><Link className="nav-dropdown-item" to="/subscriptions" role="menuitem" onClick={closeAll}><i className="bi bi-box me-2"></i>Boxes</Link></li>
                    <li role="none"><Link className="nav-dropdown-item" to="/groups" role="menuitem" onClick={closeAll}><i className="bi bi-people me-2"></i>Groups</Link></li>
                  </ul>
                </div>

                <div className="nav-product-divider"></div>
              </>
            )}

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
              <ul className={`nav-dropdown-menu ${gardensOpen ? 'nav-dropdown-menu-open' : ''}`} role="menu">
                <li role="none"><Link className="nav-dropdown-item" to="/gardens" role="menuitem" onClick={closeAll}><i className="bi bi-tree me-2"></i>Explore Gardens</Link></li>
                <li role="none"><Link className="nav-dropdown-item" to="/planting-calendar" role="menuitem" onClick={closeAll}><i className="bi bi-calendar3 me-2"></i>Planting Calendar</Link></li>
                <li role="none"><Link className="nav-dropdown-item" to="/harvest-forecast" role="menuitem" onClick={closeAll}><i className="bi bi-graph-up me-2"></i>Harvest Forecast</Link></li>
              </ul>
            </div>

            <Link className="nav-dropdown-trigger" to="/about" onClick={closeAll}>
              <i className="bi bi-info-circle me-1"></i>About
            </Link>
          </div>

          <div className="navbar-desktop-user">
            {user ? (
              <>
                {/* Notification bell */}
                <div className="nav-dropdown nav-dropdown-notif" ref={notifRef} style={{ position: 'relative' }}>
                  <button
                    className="nav-link"
                    onClick={toggleNotifications}
                    title="Notifications"
                    style={{ background: 'none', border: 'none', cursor: 'pointer', position: 'relative', padding: '0.25rem 0.5rem' }}
                  >
                    <i className="bi bi-bell"></i>
                    {notifCount > 0 && (
                      <span className="badge bg-danger" style={{
                        fontSize: '0.6rem', position: 'absolute', top: 0, right: 0,
                        borderRadius: '50%', minWidth: '16px', height: '16px',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                      }}>{notifCount > 9 ? '9+' : notifCount}</span>
                    )}
                  </button>
                  {notifOpen && (
                    <div style={{
                      position: 'absolute', top: '100%', right: 0, width: '360px',
                      backgroundColor: '#fff', borderRadius: '8px', boxShadow: '0 4px 20px rgba(0,0,0,0.15)',
                      zIndex: 1050, border: '1px solid #e0e0e0', maxHeight: '440px', overflow: 'hidden',
                    }}>
                      <div style={{
                        padding: '12px 16px', borderBottom: '1px solid #eee',
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      }}>
                        <strong style={{ fontSize: '0.95rem' }}>Notifications</strong>
                        {notifCount > 0 && (
                          <button onClick={handleMarkAllRead} style={{ background: 'none', border: 'none', color: '#1B4D3E', fontSize: '0.8rem', cursor: 'pointer' }}>
                            Mark all read
                          </button>
                        )}
                      </div>
                      <div style={{ maxHeight: '360px', overflowY: 'auto' }}>
                        {notifLoading ? (
                          <div style={{ padding: '20px', textAlign: 'center', color: '#999' }}>Loading...</div>
                        ) : notifications.length === 0 ? (
                          <div style={{ padding: '20px', textAlign: 'center', color: '#999' }}>No notifications</div>
                        ) : notifications.map(n => (
                          <div
                            key={n.id}
                            onClick={() => handleNotifClick(n)}
                            style={{
                              padding: '10px 16px', cursor: 'pointer', borderBottom: '1px solid #f5f5f5',
                              backgroundColor: n.is_read ? '#fff' : '#D8EDDF',
                            }}
                            onMouseEnter={e => e.currentTarget.style.backgroundColor = n.is_read ? '#f9f9f9' : '#C8E6D4'}
                            onMouseLeave={e => e.currentTarget.style.backgroundColor = n.is_read ? '#fff' : '#D8EDDF'}
                          >
                            <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
                              <i className={`bi ${NOTIF_ICONS[n.type] || 'bi-bell text-secondary'}`} style={{ fontSize: '1.1rem', marginTop: '2px' }}></i>
                              <div style={{ flex: 1, minWidth: 0 }}>
                                <div style={{ fontSize: '0.85rem', fontWeight: n.is_read ? 400 : 600, lineHeight: 1.3 }}>{n.title}</div>
                                {n.body && <div style={{ fontSize: '0.78rem', color: '#666', marginTop: '2px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{n.body}</div>}
                                <div style={{ fontSize: '0.7rem', color: '#999', marginTop: '3px' }}>{timeAgo(n.created_at)}</div>
                              </div>
                              {!n.is_read && <div style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: '#1B4D3E', marginTop: '6px', flexShrink: 0 }}></div>}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                <Link className="nav-link" to="/messages" title="Messages" onClick={closeAll}>
                  <i className="bi bi-chat-dots"></i>
                  {unreadCount > 0 && <span className="badge bg-danger ms-1" style={{ fontSize: '0.65rem' }}>{unreadCount}</span>}
                </Link>
                {marketplaceEnabled && (
                  <Link className="nav-link" to="/cart" title="Cart" onClick={closeAll}>
                    <i className="bi bi-cart3"></i>
                    {cartCount > 0 && <span className="badge bg-warning text-dark ms-1" style={{ fontSize: '0.65rem' }}>{cartCount}</span>}
                  </Link>
                )}
                {user.is_admin && (
                  <Link className="nav-link" to="/admin" title="Admin" onClick={closeAll}>
                    <i className="bi bi-shield-lock" style={{ color: '#ffc107' }}></i>
                  </Link>
                )}

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
                  <ul className={`nav-dropdown-menu nav-dropdown-menu-end ${profileOpen ? 'nav-dropdown-menu-open' : ''}`} role="menu">
                    <li role="none"><Link className="nav-dropdown-item" to={`/profile/${user.id}`} role="menuitem" onClick={closeAll}><i className="bi bi-person me-2"></i>My Profile</Link></li>
                    <li role="none"><Link className="nav-dropdown-item" to="/profile/edit" role="menuitem" onClick={closeAll}><i className="bi bi-pencil me-2"></i>Edit Profile</Link></li>
                    {marketplaceEnabled && (
                      <li role="none"><Link className="nav-dropdown-item" to="/orders" role="menuitem" onClick={closeAll}><i className="bi bi-bag me-2"></i>My Orders</Link></li>
                    )}
                    {marketplaceEnabled && (
                      <li role="none"><Link className="nav-dropdown-item" to="/my-subscriptions" role="menuitem" onClick={closeAll}><i className="bi bi-box me-2"></i>My Subscriptions</Link></li>
                    )}
                    {marketplaceEnabled && user.can_sell && (
                      <>
                        <li role="none"><hr className="nav-dropdown-divider" /></li>
                        <li role="none"><Link className="nav-dropdown-item" to="/dashboard" role="menuitem" onClick={closeAll}><i className="bi bi-speedometer2 me-2"></i>Seller Dashboard</Link></li>
                        <li role="none"><Link className="nav-dropdown-item" to="/my-listings" role="menuitem" onClick={closeAll}><i className="bi bi-list-ul me-2"></i>My Listings</Link></li>
                        <li role="none"><Link className="nav-dropdown-item" to="/seller/orders" role="menuitem" onClick={closeAll}><i className="bi bi-truck me-2"></i>Seller Orders</Link></li>
                        <li role="none"><Link className="nav-dropdown-item" to="/seller/subscriptions" role="menuitem" onClick={closeAll}><i className="bi bi-box-seam me-2"></i>Subscription Plans</Link></li>
                      </>
                    )}
                    <li role="none"><hr className="nav-dropdown-divider" /></li>
                    <li role="none"><Link className="nav-dropdown-item" to="/my-planting-log" role="menuitem" onClick={closeAll}><i className="bi bi-journal-text me-2"></i>Planting Log</Link></li>
                    <li role="none"><Link className="nav-dropdown-item" to="/gardens/my-gardens" role="menuitem" onClick={closeAll}><i className="bi bi-tree me-2" style={{ color: '#40916C' }}></i>My Gardens</Link></li>
                    <li role="none"><hr className="nav-dropdown-divider" /></li>
                    <li role="none"><button className="nav-dropdown-item nav-dropdown-item-danger" onClick={handleLogout} role="menuitem"><i className="bi bi-box-arrow-right me-2"></i>Logout</button></li>
                  </ul>
                </div>
              </>
            ) : (
              <>
                <Link className="nav-link" to="/login" onClick={closeAll}>Login</Link>
                <Link className="nav-link nav-link-register" to="/register" onClick={closeAll}>Register</Link>
              </>
            )}
          </div>

          <button className="navbar-hamburger" onClick={toggleMobile} aria-label="Toggle navigation" aria-expanded={mobileOpen}>
            <i className={`bi ${mobileOpen ? 'bi-x-lg' : 'bi-list'}`}></i>
          </button>
        </div>

        {/* Mobile slide-down panel */}
        <div className={`navbar-mobile-panel ${mobileOpen ? 'navbar-mobile-panel-open' : ''}`}>
          {marketplaceEnabled && (
            <div className="mobile-section">
              <div className="mobile-section-header mobile-section-header-mkt"><i className="bi bi-shop me-2"></i>Marketplace</div>
              <Link className="mobile-nav-link" to="/browse" onClick={closeAll}><i className="bi bi-grid me-2"></i>Browse</Link>
              <Link className="mobile-nav-link" to="/search" onClick={closeAll}><i className="bi bi-search me-2"></i>Search</Link>
              <Link className="mobile-nav-link" to="/subscriptions" onClick={closeAll}><i className="bi bi-box me-2"></i>Boxes</Link>
              <Link className="mobile-nav-link" to="/groups" onClick={closeAll}><i className="bi bi-people me-2"></i>Groups</Link>
            </div>
          )}
          <div className="mobile-section">
            <div className="mobile-section-header mobile-section-header-garden"><i className="bi bi-tree me-2"></i>Gardens</div>
            <Link className="mobile-nav-link" to="/gardens" onClick={closeAll}><i className="bi bi-tree me-2"></i>Explore Gardens</Link>
            <Link className="mobile-nav-link" to="/planting-calendar" onClick={closeAll}><i className="bi bi-calendar3 me-2"></i>Planting Calendar</Link>
            <Link className="mobile-nav-link" to="/harvest-forecast" onClick={closeAll}><i className="bi bi-graph-up me-2"></i>Harvest Forecast</Link>
          </div>
          <div className="mobile-section">
            <Link className="mobile-nav-link" to="/about" onClick={closeAll}><i className="bi bi-info-circle me-2"></i>About</Link>
          </div>
          <div className="mobile-section">
            {user ? (
              <>
                <div className="mobile-section-header"><i className="bi bi-person-circle me-2"></i>{user.display_name || user.username}</div>
                <button className="mobile-nav-link" onClick={toggleNotifications} style={{ background: 'none', border: 'none', width: '100%', textAlign: 'left', cursor: 'pointer' }}>
                  <i className="bi bi-bell me-2"></i>Notifications
                  {notifCount > 0 && <span className="badge bg-danger ms-2" style={{ fontSize: '0.65rem' }}>{notifCount}</span>}
                </button>
                <Link className="mobile-nav-link" to="/messages" onClick={closeAll}>
                  <i className="bi bi-chat-dots me-2"></i>Messages
                  {unreadCount > 0 && <span className="badge bg-danger ms-2" style={{ fontSize: '0.65rem' }}>{unreadCount}</span>}
                </Link>
                {marketplaceEnabled && (
                  <Link className="mobile-nav-link" to="/cart" onClick={closeAll}>
                    <i className="bi bi-cart3 me-2"></i>Cart
                    {cartCount > 0 && <span className="badge bg-warning text-dark ms-2" style={{ fontSize: '0.65rem' }}>{cartCount}</span>}
                  </Link>
                )}
                <Link className="mobile-nav-link" to={`/profile/${user.id}`} onClick={closeAll}><i className="bi bi-person me-2"></i>My Profile</Link>
                <Link className="mobile-nav-link" to="/profile/edit" onClick={closeAll}><i className="bi bi-pencil me-2"></i>Edit Profile</Link>
                {marketplaceEnabled && <Link className="mobile-nav-link" to="/orders" onClick={closeAll}><i className="bi bi-bag me-2"></i>My Orders</Link>}
                {marketplaceEnabled && <Link className="mobile-nav-link" to="/my-subscriptions" onClick={closeAll}><i className="bi bi-box me-2"></i>My Subscriptions</Link>}
                {marketplaceEnabled && user.can_sell && (
                  <>
                    <div className="mobile-nav-divider"></div>
                    <Link className="mobile-nav-link" to="/dashboard" onClick={closeAll}><i className="bi bi-speedometer2 me-2"></i>Seller Dashboard</Link>
                    <Link className="mobile-nav-link" to="/my-listings" onClick={closeAll}><i className="bi bi-list-ul me-2"></i>My Listings</Link>
                    <Link className="mobile-nav-link" to="/seller/orders" onClick={closeAll}><i className="bi bi-truck me-2"></i>Seller Orders</Link>
                    <Link className="mobile-nav-link" to="/seller/subscriptions" onClick={closeAll}><i className="bi bi-box-seam me-2"></i>Subscription Plans</Link>
                  </>
                )}
                <div className="mobile-nav-divider"></div>
                <Link className="mobile-nav-link" to="/my-planting-log" onClick={closeAll}><i className="bi bi-journal-text me-2"></i>Planting Log</Link>
                <Link className="mobile-nav-link" to="/gardens/my-gardens" onClick={closeAll}><i className="bi bi-tree me-2" style={{ color: '#40916C' }}></i>My Gardens</Link>
                {user.is_admin && <Link className="mobile-nav-link" to="/admin" onClick={closeAll}><i className="bi bi-shield-lock me-2" style={{ color: '#ffc107' }}></i>Admin</Link>}
                <div className="mobile-nav-divider"></div>
                <button className="mobile-nav-link mobile-nav-link-danger" onClick={handleLogout}><i className="bi bi-box-arrow-right me-2"></i>Logout</button>
              </>
            ) : (
              <>
                <Link className="mobile-nav-link" to="/login" onClick={closeAll}><i className="bi bi-box-arrow-in-right me-2"></i>Login</Link>
                <Link className="mobile-nav-link mobile-nav-link-register" to="/register" onClick={closeAll}><i className="bi bi-person-plus me-2"></i>Register</Link>
              </>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}
