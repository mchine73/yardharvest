import { BrowserRouter, Routes, Route, Link, Navigate } from 'react-router-dom';
import { AuthProvider } from './AuthContext';
import { SiteConfigProvider, useSiteConfig } from './SiteConfigContext';
import Navbar from './components/Navbar';
import ProtectedRoute from './components/ProtectedRoute';
import CookieConsent from './components/CookieConsent';
import GardenTrialPopup from './components/GardenTrialPopup';
import DialogHost from './components/dialog/DialogHost';
import { usePageTracking } from './hooks/useTracking';

// Auth pages
import Login from './pages/Login';
import Register from './pages/Register';
import ForgotPassword from './pages/ForgotPassword';
import ResetPassword from './pages/ResetPassword';
import VerifyEmailChange from './pages/VerifyEmailChange';

// Public pages
import Home from './pages/Home';
import About from './pages/About';
import Pricing from './pages/Pricing';
import Browse from './pages/Browse';
import Search from './pages/Search';
import ListingDetail from './pages/ListingDetail';
import NotFound from './pages/NotFound';

// Seller pages
import CreateListing from './pages/CreateListing';
import EditListing from './pages/EditListing';
import MyListings from './pages/MyListings';
import Dashboard from './pages/Dashboard';
import SellerOrders from './pages/SellerOrders';
import SellerEarnings from './pages/SellerEarnings';

// Buyer pages
import Cart from './pages/Cart';
import Checkout from './pages/Checkout';
import Orders from './pages/Orders';
import OrderDetail from './pages/OrderDetail';
import LeaveReview from './pages/LeaveReview';

// Messages
import Inbox from './pages/Inbox';
import Thread from './pages/Thread';
import NewMessage from './pages/NewMessage';

// Profile
import PublicProfile from './pages/PublicProfile';
import EditProfile from './pages/EditProfile';
import NotificationPreferences from './pages/NotificationPreferences';

// Subscriptions
import SubscriptionPlans from './pages/SubscriptionPlans';
import SubscriptionPlanDetail from './pages/SubscriptionPlanDetail';
import ManageSubscriptions from './pages/ManageSubscriptions';
import CreateSubscriptionPlan from './pages/CreateSubscriptionPlan';
import SellerSubscriptionDashboard from './pages/SellerSubscriptionDashboard';
import ComposeBoxPreview from './pages/ComposeBoxPreview';

// Neighborhood Groups
import GroupsDiscover from './pages/GroupsDiscover';
import GroupDetail from './pages/GroupDetail';
import CreateGroup from './pages/CreateGroup';
import GroupPostDetail from './pages/GroupPostDetail';

// Planting Calendar & Harvest Forecasting
import PlantingCalendar from './pages/PlantingCalendar';
import HarvestForecast from './pages/HarvestForecast';
import MyPlantingLog from './pages/MyPlantingLog';
import PlantingGuideDetail from './pages/PlantingGuideDetail';

// Community Gardens
import GardenHome from './pages/gardens/GardenHome';
import GardenDetail from './pages/gardens/GardenDetail';
import CreateGarden from './pages/gardens/CreateGarden';
import GardenEvents from './pages/gardens/GardenEvents';
import GardenImpact from './pages/gardens/GardenImpact';
import MyGardens from './pages/gardens/MyGardens';
import GardenAdminDashboard from './pages/gardens/GardenAdminDashboard';
import GardenBilling from './pages/gardens/GardenBilling';
import ResourceScan from './pages/gardens/ResourceScan';

// Admin
import AdminDashboard from './pages/admin/AdminDashboard';
import AdminUsers from './pages/admin/AdminUsers';
import AdminListings from './pages/admin/AdminListings';
import AdminOrders from './pages/admin/AdminOrders';
import AdminPricing from './pages/admin/AdminPricing';
import AdminEmailSettings from './pages/admin/AdminEmailSettings';
import AdminStats from './pages/admin/AdminStats';
import AdminAnalytics from './pages/admin/AdminAnalytics';
import AdminGardens from './pages/admin/AdminGardens';
import AdminRefunds from './pages/admin/AdminRefunds';
import AdminPromos from './pages/admin/AdminPromos';

import 'bootstrap/dist/css/bootstrap.min.css';
import 'bootstrap-icons/font/bootstrap-icons.css';
import './App.css';

function AppContent() {
  const { marketplaceEnabled } = useSiteConfig();
  const mktGuard = (element) => marketplaceEnabled ? element : <Navigate to="/gardens" replace />;
  usePageTracking();

  return (
    <>
      <Navbar />
      <DialogHost />
      <CookieConsent />
      <GardenTrialPopup />
      <main className="container py-4">
        <Routes>
          {/* Public */}
          <Route path="/" element={<Home />} />
          <Route path="/about" element={<About />} />
          <Route path="/pricing" element={<Pricing />} />
          <Route path="/browse" element={mktGuard(<Browse />)} />
          <Route path="/search" element={mktGuard(<Search />)} />
          <Route path="/listings/:id" element={<ListingDetail />} />
          <Route path="/profile/:userId" element={<PublicProfile />} />

          {/* Auth */}
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route path="/verify-email-change" element={<VerifyEmailChange />} />

          {/* Seller (requires auth + seller + marketplace) */}
          <Route path="/listings/create" element={mktGuard(<ProtectedRoute requireSeller><CreateListing /></ProtectedRoute>)} />
          <Route path="/listings/:id/edit" element={<ProtectedRoute requireSeller><EditListing /></ProtectedRoute>} />
          <Route path="/my-listings" element={mktGuard(<ProtectedRoute requireSeller><MyListings /></ProtectedRoute>)} />
          <Route path="/dashboard" element={mktGuard(<ProtectedRoute requireSeller><Dashboard /></ProtectedRoute>)} />
          <Route path="/seller/orders" element={mktGuard(<ProtectedRoute requireSeller><SellerOrders /></ProtectedRoute>)} />
          <Route path="/seller/subscriptions" element={mktGuard(<ProtectedRoute requireSeller><SellerSubscriptionDashboard /></ProtectedRoute>)} />
          <Route path="/earnings" element={mktGuard(<ProtectedRoute requireSeller><SellerEarnings /></ProtectedRoute>)} />

          {/* Buyer (requires auth + marketplace) */}
          <Route path="/cart" element={mktGuard(<ProtectedRoute><Cart /></ProtectedRoute>)} />
          <Route path="/checkout" element={mktGuard(<ProtectedRoute><Checkout /></ProtectedRoute>)} />
          <Route path="/orders" element={mktGuard(<ProtectedRoute><Orders /></ProtectedRoute>)} />
          <Route path="/orders/:id" element={<ProtectedRoute><OrderDetail /></ProtectedRoute>} />
          <Route path="/orders/:id/review" element={<ProtectedRoute><LeaveReview /></ProtectedRoute>} />

          {/* Messages (requires auth) */}
          <Route path="/messages" element={<ProtectedRoute><Inbox /></ProtectedRoute>} />
          <Route path="/messages/thread/:threadId" element={<ProtectedRoute><Thread /></ProtectedRoute>} />
          <Route path="/messages/new/:userId" element={<ProtectedRoute><NewMessage /></ProtectedRoute>} />

          {/* Profile (requires auth) */}
          <Route path="/profile/edit" element={<ProtectedRoute><EditProfile /></ProtectedRoute>} />
          <Route path="/notifications/preferences" element={<ProtectedRoute><NotificationPreferences /></ProtectedRoute>} />

          {/* Subscriptions (requires marketplace + auth for management) */}
          <Route path="/subscriptions" element={mktGuard(<SubscriptionPlans />)} />
          <Route path="/subscriptions/plans/:id" element={mktGuard(<SubscriptionPlanDetail />)} />
          <Route path="/subscriptions/create" element={mktGuard(<ProtectedRoute requireSeller><CreateSubscriptionPlan /></ProtectedRoute>)} />
          <Route path="/subscriptions/plans/:id/compose" element={mktGuard(<ProtectedRoute requireSeller><ComposeBoxPreview /></ProtectedRoute>)} />
          <Route path="/my-subscriptions" element={mktGuard(<ProtectedRoute><ManageSubscriptions /></ProtectedRoute>)} />

          {/* Neighborhood Groups */}
          <Route path="/groups" element={<GroupsDiscover />} />
          <Route path="/groups/create" element={<ProtectedRoute><CreateGroup /></ProtectedRoute>} />
          <Route path="/groups/:id" element={<GroupDetail />} />
          <Route path="/groups/:id/posts/:postId" element={<GroupPostDetail />} />

          {/* Planting Calendar & Harvest Forecasting */}
          <Route path="/planting-calendar" element={<PlantingCalendar />} />
          <Route path="/harvest-forecast" element={<HarvestForecast />} />
          <Route path="/my-planting-log" element={<ProtectedRoute><MyPlantingLog /></ProtectedRoute>} />
          <Route path="/planting-guide/:category" element={<PlantingGuideDetail />} />

          {/* Community Gardens */}
          <Route path="/gardens" element={<GardenHome />} />
          <Route path="/gardens/create" element={<ProtectedRoute><CreateGarden /></ProtectedRoute>} />
          <Route path="/gardens/my-gardens" element={<ProtectedRoute><MyGardens /></ProtectedRoute>} />
          <Route path="/gardens/:id" element={<GardenDetail />} />
          <Route path="/gardens/:id/events" element={<GardenEvents />} />
          <Route path="/gardens/:id/impact" element={<GardenImpact />} />
          <Route path="/gardens/:id/resources/:resId/scan" element={<ResourceScan />} />
          <Route path="/gardens/:id/admin" element={<ProtectedRoute><GardenAdminDashboard /></ProtectedRoute>} />
          <Route path="/gardens/:id/billing" element={<ProtectedRoute><GardenBilling /></ProtectedRoute>} />

          {/* Admin (requires auth + admin) */}
          <Route path="/admin" element={<ProtectedRoute requireAdmin><AdminDashboard /></ProtectedRoute>} />
          <Route path="/admin/users" element={<ProtectedRoute requireAdmin><AdminUsers /></ProtectedRoute>} />
          <Route path="/admin/listings" element={<ProtectedRoute requireAdmin><AdminListings /></ProtectedRoute>} />
          <Route path="/admin/orders" element={<ProtectedRoute requireAdmin><AdminOrders /></ProtectedRoute>} />
          <Route path="/admin/pricing" element={<ProtectedRoute requireAdmin><AdminPricing /></ProtectedRoute>} />
          <Route path="/admin/email-settings" element={<ProtectedRoute requireAdmin><AdminEmailSettings /></ProtectedRoute>} />
          <Route path="/admin/stats" element={<ProtectedRoute requireAdmin><AdminStats /></ProtectedRoute>} />
          <Route path="/admin/gardens" element={<ProtectedRoute requireAdmin><AdminGardens /></ProtectedRoute>} />
          <Route path="/admin/refunds" element={<ProtectedRoute requireAdmin><AdminRefunds /></ProtectedRoute>} />
          <Route path="/admin/promos" element={<ProtectedRoute requireAdmin><AdminPromos /></ProtectedRoute>} />
          <Route path="/admin/analytics" element={<ProtectedRoute requireAdmin><AdminAnalytics /></ProtectedRoute>} />

          {/* 404 Catch-All */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
      <footer className="yh-footer mt-5">
        <div className="container text-center">
          <p className="mb-1">&copy; {new Date().getFullYear()} YardHarvest — Fresh from your neighbor's garden</p>
          <p className="mb-0" style={{ fontSize: '0.85rem', opacity: 0.6 }}>
            <Link to="/about" className="me-3">About</Link>
            {marketplaceEnabled && <Link to="/browse" className="me-3">Marketplace</Link>}
            <Link to="/gardens" className="me-3">Community Gardens</Link>
            <Link to="/planting-calendar" className="me-3">Planting Calendar</Link>
            <Link to="/harvest-forecast" className="me-3">Harvest Forecast</Link>
            <Link to="/about">Contact</Link>
          </p>
        </div>
      </footer>
    </>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <SiteConfigProvider>
          <AppContent />
        </SiteConfigProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
