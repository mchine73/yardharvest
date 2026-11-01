import { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { authAPI } from '../api';
import { useAuth } from '../AuthContext';

export default function VerifyEmailChange() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const { fetchUser } = useAuth();
  const [status, setStatus] = useState('verifying'); // verifying | success | error
  const [message, setMessage] = useState('');

  useEffect(() => {
    const token = searchParams.get('token');
    if (!token) {
      setStatus('error');
      setMessage(t('verifyEmail.missingToken'));
      return;
    }
    authAPI.confirmEmailChange(token)
      .then(async () => {
        setStatus('success');
        setMessage(t('verifyEmail.updatedBody'));
        // Refresh the session user if logged in so the new email shows everywhere
        try { await fetchUser(); } catch { /* not logged in is fine */ }
      })
      .catch((err) => {
        setStatus('error');
        setMessage(err.response?.data?.error || t('verifyEmail.errFallback'));
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="row justify-content-center">
      <div className="col-md-6">
        <div className="card mt-5 text-center">
          <div className="card-body p-5">
            {status === 'verifying' && (
              <>
                <div className="spinner-border text-success mb-3"></div>
                <h4>{t('verifyEmail.verifying')}</h4>
              </>
            )}
            {status === 'success' && (
              <>
                <i className="bi bi-check-circle-fill text-success" style={{ fontSize: '3rem' }}></i>
                <h4 className="mt-3">{t('verifyEmail.updated')}</h4>
                <p className="text-muted">{message}</p>
                <Link to="/profile/edit" className="btn btn-success mt-2">{t('verifyEmail.backToProfile')}</Link>
              </>
            )}
            {status === 'error' && (
              <>
                <i className="bi bi-x-circle-fill text-danger" style={{ fontSize: '3rem' }}></i>
                <h4 className="mt-3">{t('verifyEmail.failed')}</h4>
                <p className="text-muted">{message}</p>
                <Link to="/profile/edit" className="btn btn-outline-success mt-2">{t('verifyEmail.backToProfile')}</Link>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
