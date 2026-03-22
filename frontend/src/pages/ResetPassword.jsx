import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { authAPI } from '../api';

export default function ResetPassword() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');

  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const passwordValid = password.length >= 8 &&
    /[A-Z]/.test(password) &&
    /[a-z]/.test(password) &&
    /[0-9]/.test(password);
  const passwordsMatch = password === confirm && confirm.length > 0;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!passwordValid) {
      setError('Password must be at least 8 characters with uppercase, lowercase, and a number.');
      return;
    }
    if (!passwordsMatch) {
      setError('Passwords do not match.');
      return;
    }
    setError('');
    setSubmitting(true);
    try {
      await authAPI.resetPassword(token, password);
      setSuccess(true);
    } catch (err) {
      setError(
        err.response?.data?.error ||
        'Something went wrong. Please try again.'
      );
    } finally {
      setSubmitting(false);
    }
  };

  if (!token) {
    return (
      <div className="container py-5">
        <div className="row justify-content-center">
          <div className="col-md-5 text-center">
            <i className="bi bi-exclamation-triangle fs-1 text-warning"></i>
            <h4 className="mt-3">Invalid Reset Link</h4>
            <p className="text-muted">This password reset link is missing or invalid.</p>
            <Link to="/forgot-password" className="btn btn-outline-success">
              Request a New Link
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="container py-5">
      <div className="row justify-content-center">
        <div className="col-md-5">
          <div className="text-center mb-4">
            <h2 className="fw-bold" style={{ color: '#2d6a4f' }}>
              <i className="bi bi-flower1 me-2"></i>YardHarvest
            </h2>
            <p className="text-muted">Choose a new password</p>
          </div>

          <div className="card shadow-sm border-0" style={{ borderRadius: 12 }}>
            <div className="card-body p-4">
              {success ? (
                <div className="text-center py-3">
                  <i className="bi bi-check-circle fs-1 text-success"></i>
                  <h5 className="mt-3">Password Reset</h5>
                  <p className="text-muted">Your password has been updated. You can now sign in with your new password.</p>
                  <Link to="/login" className="btn btn-success mt-2">
                    <i className="bi bi-box-arrow-in-right me-2"></i>Sign In
                  </Link>
                </div>
              ) : (
                <>
                  {error && (
                    <div className="alert alert-danger py-2">
                      <i className="bi bi-exclamation-circle me-2"></i>{error}
                    </div>
                  )}
                  <form onSubmit={handleSubmit}>
                    <div className="mb-3">
                      <label htmlFor="new-password" className="form-label">New Password</label>
                      <div className="input-group">
                        <span className="input-group-text"><i className="bi bi-lock"></i></span>
                        <input
                          type="password"
                          id="new-password"
                          className="form-control"
                          placeholder="Enter new password"
                          value={password}
                          onChange={(e) => setPassword(e.target.value)}
                          required
                          autoFocus
                        />
                      </div>
                      {password.length > 0 && (
                        <div className="mt-1" style={{ fontSize: '0.8rem' }}>
                          <span className={password.length >= 8 ? 'text-success' : 'text-muted'}>
                            <i className={`bi ${password.length >= 8 ? 'bi-check-circle-fill' : 'bi-circle'} me-1`}></i>8+ characters
                          </span>{' '}
                          <span className={/[A-Z]/.test(password) ? 'text-success' : 'text-muted'}>
                            <i className={`bi ${/[A-Z]/.test(password) ? 'bi-check-circle-fill' : 'bi-circle'} me-1`}></i>Uppercase
                          </span>{' '}
                          <span className={/[a-z]/.test(password) ? 'text-success' : 'text-muted'}>
                            <i className={`bi ${/[a-z]/.test(password) ? 'bi-check-circle-fill' : 'bi-circle'} me-1`}></i>Lowercase
                          </span>{' '}
                          <span className={/[0-9]/.test(password) ? 'text-success' : 'text-muted'}>
                            <i className={`bi ${/[0-9]/.test(password) ? 'bi-check-circle-fill' : 'bi-circle'} me-1`}></i>Number
                          </span>
                        </div>
                      )}
                    </div>
                    <div className="mb-3">
                      <label htmlFor="confirm-password" className="form-label">Confirm Password</label>
                      <div className="input-group">
                        <span className="input-group-text"><i className="bi bi-lock-fill"></i></span>
                        <input
                          type="password"
                          id="confirm-password"
                          className="form-control"
                          placeholder="Confirm new password"
                          value={confirm}
                          onChange={(e) => setConfirm(e.target.value)}
                          required
                        />
                      </div>
                      {confirm.length > 0 && (
                        <div className="mt-1" style={{ fontSize: '0.8rem' }}>
                          {passwordsMatch ? (
                            <span className="text-success"><i className="bi bi-check-circle-fill me-1"></i>Passwords match</span>
                          ) : (
                            <span className="text-danger"><i className="bi bi-x-circle me-1"></i>Passwords do not match</span>
                          )}
                        </div>
                      )}
                    </div>
                    <button
                      type="submit"
                      className="btn w-100"
                      style={{ backgroundColor: '#2d6a4f', color: 'white', fontWeight: 600 }}
                      disabled={submitting || !passwordValid || !passwordsMatch}
                    >
                      {submitting ? (
                        <>
                          <span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true" />
                          Resetting...
                        </>
                      ) : (
                        <>
                          <i className="bi bi-shield-check me-2"></i>Reset Password
                        </>
                      )}
                    </button>
                  </form>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
