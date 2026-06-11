import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { gardensAPI } from '../../api';
import { useAuth } from '../../AuthContext';

const CONDITION_COLORS = {
  new: '#2aa873',
  good: '#3f7ddb',
  fair: '#d99a2b',
  needs_repair: '#e0564f',
};

export default function ResourceScan() {
  const { id, resId } = useParams();
  const { user } = useAuth();
  const [resource, setResource] = useState(null);
  const [garden, setGarden] = useState(null);
  const [loading, setLoading] = useState(true);
  const [checkoutDuration, setCheckoutDuration] = useState(3);
  const [msg, setMsg] = useState('');
  const [history, setHistory] = useState([]);

  const loadHistory = () => {
    gardensAPI.resourceHistory(id, resId).then(r => setHistory(r.data)).catch(() => {});
  };

  useEffect(() => {
    Promise.all([
      gardensAPI.detail(id),
      gardensAPI.resources(id),
    ]).then(([gardenRes, resourcesRes]) => {
      setGarden(gardenRes.data);
      const res = resourcesRes.data.find(r => r.id === parseInt(resId));
      setResource(res || null);
      setLoading(false);
    }).catch(() => setLoading(false));
    loadHistory();
  }, [id, resId]);

  const handleCheckout = () => {
    gardensAPI.checkoutResource(id, parseInt(resId), { duration_days: checkoutDuration }).then(res => {
      setResource(res.data);
      setMsg('Checked out successfully!');
    }).catch(err => setMsg(err.response?.data?.error || 'Error checking out'));
  };

  const handleReturn = () => {
    gardensAPI.returnResource(id, parseInt(resId)).then(res => {
      setResource(res.data);
      setMsg('Returned successfully!');
    }).catch(err => setMsg(err.response?.data?.error || 'Error returning'));
  };

  if (loading) return <div className="text-center py-5"><div className="spinner-border" style={{ color: '#1d8a5f' }}></div></div>;
  if (!resource) return (
    <div className="text-center py-5">
      <i className="bi bi-exclamation-circle" style={{ fontSize: '3rem', color: '#e0564f' }}></i>
      <h4 className="mt-3">Resource Not Found</h4>
      <Link to={`/gardens/${id}`} className="btn btn-outline-success mt-2">Back to Garden</Link>
    </div>
  );

  const isCheckedOut = !!resource.checked_out_to_id;
  const isCheckedOutByMe = user && resource.checked_out_to_id === user.id;

  return (
    <div style={{ maxWidth: '500px', margin: '0 auto' }}>
      <div className="text-center mb-4">
        <i className="bi bi-qr-code-scan" style={{ fontSize: '2.5rem', color: '#1d8a5f' }}></i>
        <h3 className="fw-bold mt-2">{resource.name}</h3>
        {garden && <p className="text-muted">{garden.name}</p>}
      </div>

      {msg && (
        <div className={`alert ${msg.includes('Error') || msg.includes('error') ? 'alert-danger' : 'alert-success'}`}>
          {msg}
        </div>
      )}

      <div className="card mb-4" style={{ border: '2px solid #7fd4ab', borderRadius: '12px' }}>
        <div className="card-body">
          <div className="row text-center mb-3">
            <div className="col-4">
              <small className="text-muted d-block">Type</small>
              <span style={{ textTransform: 'capitalize' }}>{resource.resource_type}</span>
            </div>
            <div className="col-4">
              <small className="text-muted d-block">Condition</small>
              <span className="badge" style={{ backgroundColor: CONDITION_COLORS[resource.condition] || '#6b7280' }}>
                {resource.condition?.replace('_', ' ')}
              </span>
            </div>
            <div className="col-4">
              <small className="text-muted d-block">Status</small>
              {isCheckedOut ? (
                <span className={resource.is_overdue ? 'text-danger fw-bold' : 'text-warning'}>Checked Out</span>
              ) : (
                <span className="text-success">Available</span>
              )}
            </div>
          </div>

          {resource.description && <p className="text-muted small mb-3">{resource.description}</p>}

          {isCheckedOut && (
            <div className="alert alert-light mb-3">
              <small className="text-muted">Checked out by:</small>
              <div className="fw-semibold">{resource.checked_out_to_name}</div>
              {resource.due_date && (
                <div className={`small ${resource.is_overdue ? 'text-danger fw-bold' : 'text-muted'}`}>
                  Due: {new Date(resource.due_date).toLocaleDateString()}
                  {resource.is_overdue && ' (OVERDUE)'}
                </div>
              )}
            </div>
          )}

          {!user && (
            <div className="alert alert-info">
              <Link to="/login">Log in</Link> to check out or return this resource.
            </div>
          )}

          {user && !isCheckedOut && (
            <div>
              <p className="fw-semibold mb-2">Select checkout duration:</p>
              <div className="d-flex gap-2 justify-content-center mb-3">
                {[1, 3, 7].map(d => (
                  <button key={d}
                    className={`btn ${checkoutDuration === d ? 'btn-success' : 'btn-outline-success'} px-4`}
                    onClick={() => setCheckoutDuration(d)}>
                    {d} day{d > 1 ? 's' : ''}
                  </button>
                ))}
              </div>
              <button className="btn btn-lg w-100" style={{ backgroundColor: '#1d8a5f', color: 'white', padding: '14px' }} onClick={handleCheckout}>
                <i className="bi bi-box-arrow-up-right me-2"></i>Check Out
              </button>
            </div>
          )}

          {isCheckedOutByMe && (
            <button className="btn btn-primary btn-lg w-100" style={{ padding: '14px' }} onClick={handleReturn}>
              <i className="bi bi-arrow-return-left me-2"></i>Return Item
            </button>
          )}
        </div>
      </div>

      {/* Checkout History */}
      {history.length > 0 && (
        <div className="card mb-4" style={{ borderRadius: 12 }}>
          <div className="card-body">
            <h6 className="fw-bold mb-3"><i className="bi bi-clock-history me-2"></i>Recent History</h6>
            {history.slice(0, 5).map((h, i) => (
              <div key={i} className="d-flex justify-content-between align-items-center py-2 border-bottom">
                <div>
                  <div className="fw-semibold small">{h.user_name}</div>
                  <div className="text-muted" style={{ fontSize: '0.75rem' }}>
                    {h.checked_out_at ? new Date(h.checked_out_at).toLocaleDateString() : ''} — {h.returned_at ? new Date(h.returned_at).toLocaleDateString() : 'not returned'}
                  </div>
                </div>
                <span className="badge bg-light text-dark small">{h.duration_days}d</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="text-center">
        <Link to={`/gardens/${id}`} className="btn btn-outline-secondary">
          <i className="bi bi-arrow-left me-1"></i>Back to Garden
        </Link>
      </div>
    </div>
  );
}
