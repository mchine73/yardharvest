import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../AuthContext';

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await login(email, password);
      navigate('/');
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        err.response?.data?.error ||
        err.message ||
        'Login failed. Please check your credentials.'
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="container py-5">
      <div className="row justify-content-center">
        <div className="col-md-5">
          {/* Header */}
          <div className="text-center mb-4">
            <h2 className="fw-bold" style={{ color: '#2d6a4f' }}>
              <img src="/sunflower.svg" alt="" className="me-2" style={{ height: '1.15em', width: '1.15em', borderRadius: '0.22em', verticalAlign: '-0.2em' }} />YardHarvest
            </h2>
            <p className="text-muted">Sign in to your account</p>
          </div>

          <div className="card shadow-sm border-0" style={{ borderRadius: 12 }}>
            <div className="card-body p-4">
              {error && (
                <div className="alert alert-danger py-2" role="alert">
                  <i className="bi bi-exclamation-circle me-2"></i>{error}
                </div>
              )}

              <form onSubmit={handleSubmit}>
                <div className="mb-3">
                  <label htmlFor="login-email" className="form-label">
                    Email address
                  </label>
                  <div className="input-group">
                    <span className="input-group-text"><i className="bi bi-envelope"></i></span>
                    <input
                      type="email"
                      id="login-email"
                      className="form-control"
                      placeholder="you@example.com"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      required
                      autoFocus
                    />
                  </div>
                </div>

                <div className="mb-3">
                  <label htmlFor="login-password" className="form-label">
                    Password
                  </label>
                  <div className="input-group">
                    <span className="input-group-text"><i className="bi bi-lock"></i></span>
                    <input
                      type="password"
                      id="login-password"
                      className="form-control"
                      placeholder="Enter your password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                    />
                  </div>
                  <div className="text-end mt-1">
                    <Link
                      to="/forgot-password"
                      className="text-decoration-none"
                      style={{ fontSize: '0.85rem', color: '#40916c' }}
                    >
                      Forgot your password?
                    </Link>
                  </div>
                </div>

                <button
                  type="submit"
                  className="btn w-100 mb-3"
                  style={{ backgroundColor: '#2d6a4f', color: 'white', fontWeight: 600 }}
                  disabled={submitting}
                >
                  {submitting ? (
                    <>
                      <span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true" />
                      Signing in...
                    </>
                  ) : (
                    <>
                      <i className="bi bi-box-arrow-in-right me-2"></i>Sign In
                    </>
                  )}
                </button>
              </form>

              <hr className="my-3" />
              <p className="text-center mb-0">
                Don&apos;t have an account?{' '}
                <Link to="/register" className="text-decoration-none" style={{ color: '#2d6a4f', fontWeight: 600 }}>
                  Create one
                </Link>
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
