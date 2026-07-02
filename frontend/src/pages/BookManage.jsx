import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { bookingAPI } from '../api';

function dateLabel(iso) {
  return new Date(iso).toLocaleDateString(undefined, {
    weekday: 'long', month: 'long', day: 'numeric', year: 'numeric',
  });
}
function timeLabel(iso) {
  return new Date(iso).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
}

export default function BookManage() {
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
        ? 'Booking not found.'
        : "We couldn't load your booking — please refresh to try again."))
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
      setCancelError('Could not cancel — please try again.');
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
        <p className="mt-3">{error || 'Booking not found.'}</p>
        <Link to="/book" className="btn btn-success">Book a time</Link>
      </div>
    );
  }

  const cancelled = booking.status === 'cancelled';
  return (
    <div className="mx-auto" style={{ maxWidth: 560 }}>
      <h1 className="h4 mb-4">Manage your booking</h1>
      <div className={`card shadow-sm ${cancelled ? 'border-danger' : ''}`}>
        <div className="card-body">
          {cancelled && <span className="badge bg-danger mb-2">Cancelled</span>}
          <h5 className="mb-3">{booking.type_name}</h5>
          <p className="mb-1"><i className="bi bi-calendar-event me-2 text-success" />{dateLabel(booking.start_at)}</p>
          <p className="mb-1"><i className="bi bi-clock me-2 text-success" />
            {timeLabel(booking.start_at)} ({booking.duration_min} min) · {booking.invitee_timezone}</p>
          {booking.location && <p className="mb-1"><i className="bi bi-geo-alt me-2 text-success" />{booking.location}</p>}
          <p className="mb-0 text-muted small">Booked by {booking.invitee_name} ({booking.invitee_email})</p>
        </div>
      </div>

      {!cancelled && (
        <div className="mt-4">
          {!confirming ? (
            <div className="d-flex gap-2">
              <Link to="/book" className="btn btn-outline-success">
                <i className="bi bi-calendar-plus me-1" />Book another time
              </Link>
              <button className="btn btn-outline-danger" onClick={() => setConfirming(true)}>
                Cancel this booking
              </button>
            </div>
          ) : (
            <div className="alert alert-light border">
              <p className="mb-2">Cancel this booking? This can't be undone.</p>
              {cancelError && <div className="alert alert-warning" role="alert">{cancelError}</div>}
              <button className="btn btn-danger me-2" onClick={doCancel} disabled={cancelling}>
                {cancelling ? 'Cancelling…' : 'Yes, cancel'}
              </button>
              <button className="btn btn-link" onClick={() => setConfirming(false)}>Keep it</button>
            </div>
          )}
        </div>
      )}
      {cancelled && (
        <div className="mt-4">
          <Link to="/book" className="btn btn-success"><i className="bi bi-calendar-plus me-1" />Book a new time</Link>
        </div>
      )}
    </div>
  );
}
