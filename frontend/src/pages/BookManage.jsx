import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { bookingAPI } from '../api';
import Seo from '../components/Seo';
import { formatDate, formatTime, HOUR_MINUTE } from '../i18n/dates';

function dateLabel(iso) {
  return formatDate(iso, { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' });
}
function timeLabel(iso) {
  return formatTime(iso, HOUR_MINUTE);
}

export default function BookManage() {
  const { t } = useTranslation();
  const { publicId } = useParams();
  const [booking, setBooking] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [confirming, setConfirming] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [cancelError, setCancelError] = useState('');

  useEffect(() => {
    bookingAPI.getManage(publicId)
      .then((r) => setBooking(r.data.booking))
      .catch((err) => setError(err.response?.status === 404
        ? t('book.notFound')
        : t('book.loadError')))
      .finally(() => setLoading(false));
  }, [publicId]);

  async function doCancel() {
    setCancelling(true);
    setCancelError('');
    try {
      const r = await bookingAPI.cancel(publicId);
      setBooking(r.data.booking);
      setConfirming(false);
    } catch {
      setCancelError(t('book.cancelError'));
    } finally {
      setCancelling(false);
    }
  }

  if (loading) {
    return <div className="text-center py-5"><div className="spinner-border text-success" /></div>;
  }
  if (error || !booking) {
    return (
      <div className="text-center py-5">
        <i className="bi bi-exclamation-circle text-muted" style={{ fontSize: '2.5rem' }} />
        <p className="mt-3">{error || t('book.notFound')}</p>
        <Link to="/book" className="btn btn-success">{t('book.bookATime')}</Link>
      </div>
    );
  }

  const cancelled = booking.status === 'cancelled';
  return (
    <div className="mx-auto" style={{ maxWidth: 560 }}>
      <Seo title={t('book.manageTitle')} noindex />
      <h1 className="h4 mb-4">{t('book.manageTitle')}</h1>
      <div className={`card shadow-sm ${cancelled ? 'border-danger' : ''}`}>
        <div className="card-body">
          {cancelled && <span className="badge bg-danger mb-2">{t('book.cancelled')}</span>}
          <h5 className="mb-3">{booking.type_name}</h5>
          <p className="mb-1"><i className="bi bi-calendar-event me-2 text-success" />{dateLabel(booking.start_at)}</p>
          <p className="mb-1"><i className="bi bi-clock me-2 text-success" />
            {timeLabel(booking.start_at)} ({t('book.duration', { count: booking.duration_min })}) · {booking.invitee_timezone}</p>
          {booking.location && <p className="mb-1"><i className="bi bi-geo-alt me-2 text-success" />{booking.location}</p>}
          <p className="mb-0 text-muted small">{t('book.bookedBy', { name: booking.invitee_name, email: booking.invitee_email })}</p>
        </div>
      </div>

      {!cancelled && (
        <div className="mt-4">
          {!confirming ? (
            <div className="d-flex gap-2">
              <Link to="/book" className="btn btn-outline-success">
                <i className="bi bi-calendar-plus me-1" />{t('book.bookAnother')}
              </Link>
              <button className="btn btn-outline-danger" onClick={() => setConfirming(true)}>
                {t('book.cancelBooking')}
              </button>
            </div>
          ) : (
            <div className="alert alert-light border">
              <p className="mb-2">{t('book.cancelConfirm')}</p>
              {cancelError && <div className="alert alert-warning" role="alert">{cancelError}</div>}
              <button className="btn btn-danger me-2" onClick={doCancel} disabled={cancelling}>
                {cancelling ? t('book.cancelling') : t('book.yesCancel')}
              </button>
              <button className="btn btn-link" onClick={() => setConfirming(false)}>{t('book.keepIt')}</button>
            </div>
          )}
        </div>
      )}
      {cancelled && (
        <div className="mt-4">
          <Link to="/book" className="btn btn-success"><i className="bi bi-calendar-plus me-1" />{t('book.bookNew')}</Link>
        </div>
      )}
    </div>
  );
}
