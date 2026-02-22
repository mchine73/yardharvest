import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import { AuthProvider } from './AuthContext';
import Navbar from './components/Navbar';

// Auth pages
import Login from './pages/Login';
import Register from './pages/Register';

// Public pages
import Home from './pages/Home';
import About from './pages/About';
import Browse from './pages/Browse';
import Search from './pages/Search';
import ListingDetail from './pages/ListingDetail';

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
import ResourceScan from './pages/gardens/ResourceScan';

// Admin
import AdminDashboard from './pages/admin/AdminDashboard';
import AdminUsers from './pages/admin/AdminUsers';
import AdminListings from './pages/admin/AdminListings';
import AdminOrders from './pages/admin/AdminOrders';
import AdminPricing from './pages/admin/AdminPricing';
import AdminEmailSettings from './pages/admin/AdminEmailSettings';
import AdminStats from './pages/admin/AdminStats';

import 'bootstrap/dist/css/bootstrap.min.css';
import 'bootstrap-icons/font/bootstrap-icons.css';
import './App.css';

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Navbar />
        <main className="container py-4">
          <Routes>
            {/* Public */}
            <Route path="/" element={<Home />} />
            <Route path="/about" element={<About />} />
            <Route path="/browse" element={<Browse />} />
            <Route path="/search" element={<Search />} />
            <Route path="/listings/:id" element={<ListingDetail />} />
            <Route path="/profile/:userId" element={<PublicProfile />} />

            {/* Auth */}
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />

            {/* Seller */}
            <Route path="/listings/create" element={<CreateListing />} />
            <Route path="/listings/:id/edit" element={<EditListing />} />
            <Route path="/my-listings" element={<MyListings />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/seller/orders" element={<SellerOrders />} />
            <Route path="/earnings" element={<SellerEarnings />} />

            {/* Buyer */}
            <Route path="/cart" element={<Cart />} />
            <Route path="/checkout" element={<Checkout />} />
            <Route path="/orders" element={<Orders />} />
            <Route path="/orders/:id" element={<OrderDetail />} />
            <Route path="/orders/:id/review" element={<LeaveReview />} />

            {/* Messages */}
            <Route path="/messages" element={<Inbox />} />
            <Route path="/messages/thread/:threadId" element={<Thread />} />
            <Route path="/messages/new/:userId" element={<NewMessage />} />

            {/* Profile */}
            <Route path="/profile/edit" element={<EditProfile />} />

            {/* Subscriptions */}
            <Route path="/subscriptions" element={<SubscriptionPlans />} />
            <Route path="/subscriptions/plans/:id" element={<SubscriptionPlanDetail />} />
            <Route path="/subscriptions/create" element={<CreateSubscriptionPlan />} />
            <Route path="/subscriptions/plans/:id/compose" element={<ComposeBoxPreview />} />
            <Route path="/my-subscriptions" element={<ManageSubscriptions />} />
            <Route path="/seller/subscriptions" element={<SellerSubscriptionDashboard />} />

            {/* Neighborhood Groups */}
            <Route path="/groups" element={<GroupsDiscover />} />
            <Route path="/groups/create" element={<CreateGroup />} />
            <Route path="/groups/:id" element={<GroupDetail />} />
            <Route path="/groups/:id/posts/:postId" element={<GroupPostDetail />} />

            {/* Planting Calendar & Harvest Forecasting */}
            <Route path="/planting-calendar" element={<PlantingCalendar />} />
            <Route path="/harvest-forecast" element={<HarvestForecast />} />
            <Route path="/my-planting-log" element={<MyPlantingLog />} />
            <Route path="/planting-guide/:category" element={<PlantingGuideDetail />} />

            {/* Community Gardens */}
            <Route path="/gardens" element={<GardenHome />} />
            <Route path="/gardens/create" element={<CreateGarden />} />
            <Route path="/gardens/my-gardens" element={<MyGardens />} />
            <Route path="/gardens/:id" element={<GardenDetail />} />
            <Route path="/gardens/:id/events" element={<GardenEvents />} />
            <Route path="/gardens/:id/impact" element={<GardenImpact />} />
            <Route path="/gardens/:id/resources/:resId/scan" element={<ResourceScan />} />
            <Route path="/gardens/:id/admin" element={<GardenAdminDashboard />} />

            {/* Admin */}
            <Route path="/admin" element={<AdminDashboard />} />
            <Route path="/admin/users" element={<AdminUsers />} />
            <Route path="/admin/listings" element={<AdminListings />} />
            <Route path="/admin/orders" element={<AdminOrders />} />
            <Route path="/admin/pricing" element={<AdminPricing />} />
            <Route path="/admin/email-settings" element={<AdminEmailSettings />} />
            <Route path="/admin/stats" element={<AdminStats />} />
          </Routes>
        </main>
        <footer className="yh-footer mt-5">
          <div className="container text-center">
            <p className="mb-1">&copy; 2025 YardHarvest — Fresh from your neighbor's garden</p>
            <p className="mb-0" style={{ fontSize: '0.85rem', opacity: 0.6 }}>
              <Link to="/about" className="me-3">About</Link>
              <Link to="/browse" className="me-3">Marketplace</Link>
              <Link to="/gardens">Community Gardens</Link>
            </p>
          </div>
        </footer>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
