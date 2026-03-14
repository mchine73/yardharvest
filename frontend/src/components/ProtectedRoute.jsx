import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../AuthContext';

/**
 * ProtectedRoute — wraps route content behind authentication.
 *
 * Props:
 *   requireSeller  – if true, user must have can_sell === true
 *   requireAdmin   – if true, user must have is_admin === true
 *   children       – the JSX to render when authorized
 */
export default function ProtectedRoute({ requireSeller, requireAdmin, children }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  // Show spinner while auth state is loading
  if (loading) {
    return (
      <div className="text-center py-5">
        <div className="spinner-border text-success" role="status">
          <span className="visually-hidden">Loading...</span>
        </div>
      </div>
    );
  }

  // Not logged in — redirect to login, preserving intended destination
  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // Seller check
  if (requireSeller && !user.can_sell) {
    return (
      <div className="text-center py-5">
        <i className="bi bi-shop fs-1 text-muted"></i>
        <h3 className="mt-3">Seller Access Required</h3>
        <p className="text-muted">
          You need to become a seller to access this page.
          Update your profile to enable selling.
        </p>
        <a href="/profile/edit" className="btn btn-success">
          <i className="bi bi-pencil me-2"></i>Edit Profile
        </a>
      </div>
    );
  }

  // Admin check
  if (requireAdmin && !user.is_admin) {
    return (
      <div className="text-center py-5">
        <i className="bi bi-shield-lock fs-1 text-danger"></i>
        <h3 className="mt-3">Access Denied</h3>
        <p className="text-muted">You do not have permission to view this page.</p>
      </div>
    );
  }

  return children;
}
