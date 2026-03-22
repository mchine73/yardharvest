import { useState } from 'react';
import { Link } from 'react-router-dom';
import { authAPI } from '../api';

export default function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await authAPI.forgotPassword(email);
      setSent(true);
    } catch (err) {
      setError(
        err.response?.data?.error ||
        'Something went wrong. Please try again.'
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="container py-5">
      <div className="row justify-content-center">
        <div className="col-md-5">
          <div className="text-center mb-4">
            <h2 className="fw-bold" style={{ color: '#2d6a4f' }}>
              <i className="bi bi-flower1 me-2"></i>YardHarvest
            </h2>
            <p className="text-muted">Reset your password</p>
          </div>

          <div className="card shadow-sm border-0" style={{ borderRadius: 12 }}>
            <div className="card-body p-4">
              {sent ? (
                <div className="text-center py-3">
                  <i className="bi bi-envelope-check fs-1 text-success"></i>
                  <h5 className="mt-3">Check your email</h5>
                  <p className="text-muted">
                    If an account exists with <strong>{email}</strong>, we've sent a password reset link.
                    The link expires in 1 hour.
                  </p>
                  <Link to="/login" className="btn btn-outline-success mt-2">
                    <i className="bi bi-arrow-left me-2"></i>Back to Sign In
                  </Link>
                </div>
              ) : (
                <>
                  {error && (
                    <div className="alert alert-danger py-2">
                      <i className="bi bi-exclamation-circle me-2"></i>{error}
                    </div>
                  )}
                  <p className="text-muted mb-3">
                    Enter your email address and we'll send you a link to reset your password.
                  </p>
                  <form onSubmit={handleSubmit}>
                    <div className="mb-3">
                      <label htmlFor="reset-email" className="form-label">Email address</label>
                      <div className="input-group">
                        <span className="input-group-text"><i className="bi bi-envelope"></i></span>
                        <input
                          type="email"
                          id="reset-email"
                          className="form-control"
                          placeholder="you@example.com"
                          value={email}
                          onChange={(e) => setEmail(e.target.value)}
                          required
                          autoFocus
                        />
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
                          Sending...
                        </>
                      ) : (
                        <>
                          <i className="bi bi-send me-2"></i>Send Reset Link
                        </>
                      )}
                    </button>
                  </form>
                  <hr className="my-3" />
                  <p className="text-center mb-0">
                    Remember your password?{' '}
                    <Link to="/login" className="text-decoration-none" style={{ color: '#2d6a4f', fontWeight: 600 }}>
                      Sign in
                    </Link>
                  </p>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
