import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Link, Navigate } from 'react-router-dom';
import { AuthProvider } from './AuthContext';
import { SiteConfigProvider, useSiteConfig } from './SiteConfigContext';
import Navbar from './components/Navbar';
import ProtectedRoute from './components/ProtectedRoute';
import CookieConsent from './components/CookieConsent';
import GardenTrialPopup from './components/GardenTrialPopup';
import DialogHost from './components/dialog/DialogHost';
import { usePageTracking } from './hooks/useTracking';

// Eager: the landing page and 404 (first paint / tiny).
import Home from './pages/Home';
import NotFound from './pages/NotFound';

// Everything else is route-split (React.lazy) so the initial bundle stays
// small — heavy pages (GardenAdminDashboard, maps via Leaflet, the QR scanner,
// Stripe checkout, admin) only download when their route is visited.
// Auth pages
const Login = lazy(() => import('./pages/Login'));
const Register = lazy(() => import('./pages/Register'));
const ForgotPassword = lazy(() => import('./pages/ForgotPassword'));
const ResetPassword = lazy(() => import('./pages/ResetPassword'));
const VerifyEmailChange = lazy(() => import('./pages/VerifyEmailChange'));

// Public pages
const About = lazy(() => import('./pages/About'));
const Pricing = lazy(() => import('./pages/Pricing'));
const Terms = lazy(() => import('./pages/Terms'));
const Privacy = lazy(() => import('./pages/Privacy'));
const Browse = lazy(() => import('./pages/Browse'));
const Search = lazy(() => import('./pages/Search'));
const ListingDetail = lazy(() => import('./pages/ListingDetail'));

// Seller pages
const CreateListing = lazy(() => import('./pages/CreateListing'));
const EditListing = lazy(() => import('./pages/EditListing'));
const MyListings = lazy(() => import('./pages/MyListings'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const SellerOrders = lazy(() => import('./pages/SellerOrders'));
const SellerEarnings = lazy(() => import('./pages/SellerEarnings'));

// Buyer pages
const Cart = lazy(() => import('./pages/Cart'));
const Checkout = lazy(() => import('./pages/Checkout'));
const Orders = lazy(() => import('./pages/Orders'));
const OrderDetail = lazy(() => import('./pages/OrderDetail'));
const LeaveReview = lazy(() => import('./pages/LeaveReview'));

// Messages
const Inbox = lazy(() => import('./pages/Inbox'));
const Thread = lazy(() => import('./pages/Thread'));
const NewMessage = lazy(() => import('./pages/NewMessage'));

// Profile
const PublicProfile = lazy(() => import('./pages/PublicProfile'));
const EditProfile = lazy(() => import('./pages/EditProfile'));
const NotificationPreferences = lazy(() => import('./pages/NotificationPreferences'));

// Subscriptions
const SubscriptionPlans = lazy(() => import('./pages/SubscriptionPlans'));
const SubscriptionPlanDetail = lazy(() => import('./pages/SubscriptionPlanDetail'));
const ManageSubscriptions = lazy(() => import('./pages/ManageSubscriptions'));
const CreateSubscriptionPlan = lazy(() => import('./pages/CreateSubscriptionPlan'));
const SellerSubscriptionDashboard = lazy(() => import('./pages/SellerSubscriptionDashboard'));
const ComposeBoxPreview = lazy(() => import('./pages/ComposeBoxPreview'));

// Neighborhood Groups
const GroupsDiscover = lazy(() => import('./pages/GroupsDiscover'));
const GroupDetail = lazy(() => import('./pages/GroupDetail'));
const CreateGroup = lazy(() => import('./pages/CreateGroup'));
const GroupPostDetail = lazy(() => import('./pages/GroupPostDetail'));

// Planting Calendar & Harvest Forecasting
const PlantingCalendar = lazy(() => import('./pages/PlantingCalendar'));
const HarvestForecast = lazy(() => import('./pages/HarvestForecast'));
const MyPlantingLog = lazy(() => import('./pages/MyPlantingLog'));
const PlantingGuideDetail = lazy(() => import('./pages/PlantingGuideDetail'));

// Community Gardens
const GardenHome = lazy(() => import('./pages/gardens/GardenHome'));
const GardenDetail = lazy(() => import('./pages/gardens/GardenDetail'));
const CreateGarden = lazy(() => import('./pages/gardens/CreateGarden'));
const GardenEvents = lazy(() => import('./pages/gardens/GardenEvents'));
const GardenImpact = lazy(() => import('./pages/gardens/GardenImpact'));
const MyGardens = lazy(() => import('./pages/gardens/MyGardens'));
const GardenAdminDashboard = lazy(() => import('./pages/gardens/GardenAdminDashboard'));
const GardenBilling = lazy(() => import('./pages/gardens/GardenBilling'));
const ResourceScan = lazy(() => import('./pages/gardens/ResourceScan'));

// Admin
const AdminDashboard = lazy(() => import('./pages/admin/AdminDashboard'));
const AdminUsers = lazy(() => import('./pages/admin/AdminUsers'));
const AdminListings = lazy(() => import('./pages/admin/AdminListings'));
const AdminOrders = lazy(() => import('./pages/admin/AdminOrders'));
const AdminPricing = lazy(() => import('./pages/admin/AdminPricing'));
const AdminEmailSettings = lazy(() => import('./pages/admin/AdminEmailSettings'));
const AdminStats = lazy(() => import('./pages/admin/AdminStats'));
const AdminAnalytics = lazy(() => import('./pages/admin/AdminAnalytics'));
const AdminGardens = lazy(() => import('./pages/admin/AdminGardens'));
const AdminRefunds = lazy(() => import('./pages/admin/AdminRefunds'));
const AdminPromos = lazy(() => import('./pages/admin/AdminPromos'));

import 'bootstrap/dist/css/bootstrap.min.css';
import 'bootstrap-icons/font/bootstrap-icons.css';
import './App.css';

function RouteFallback() {
  return (
    <div className="text-center py-5">
      <div className="spinner-border text-success" role="status">
        <span className="visually-hidden">Loading…</span>
      </div>
    </div>
  );
}

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
        <Suspense fallback={<RouteFallback />}>
        <Routes>
          {/* Public */}
          <Route path="/" element={<Home />} />
          <Route path="/about" element={<About />} />
          <Route path="/pricing" element={<Pricing />} />
          <Route path="/terms" element={<Terms />} />
          <Route path="/privacy" element={<Privacy />} />
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
        </Suspense>
      </main>
      <footer className="yh-footer mt-5">
        <div className="container text-center">
          <p className="mb-1">&copy; {new Date().getFullYear()} YardHarvest — {marketplaceEnabled ? "Fresh from your neighbor's garden" : 'Less admin, more garden'}</p>
          <p className="mb-0" style={{ fontSize: '0.85rem', opacity: 0.6 }}>
            <Link to="/about" className="me-3">About</Link>
            {marketplaceEnabled && <Link to="/browse" className="me-3">Marketplace</Link>}
            <Link to="/gardens" className="me-3">Community Gardens</Link>
            <Link to="/planting-calendar" className="me-3">Planting Calendar</Link>
            <Link to="/harvest-forecast" className="me-3">Harvest Forecast</Link>
            <Link to="/about" className="me-3">Contact</Link>
            <Link to="/terms" className="me-3">Terms</Link>
            <Link to="/privacy">Privacy</Link>
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
