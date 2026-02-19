import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { gardensAPI } from '../../api';
import { useAuth } from '../../AuthContext';

const MODEL_LABELS = {
  allotment: 'Allotment',
  communal: 'Communal',
  hybrid: 'Hybrid',
};

const MODEL_COLORS = {
  allotment: '#2d6a4f',
  communal: '#3b82f6',
  hybrid: '#8b5cf6',
};

function GardenCard({ garden, role, roleColor, roleIcon }) {
  return (
    <div className="col-md-6 col-lg-4">
      <Link to={`/gardens/${garden.id}`} style={{ textDecoration: 'none', color: 'inherit' }}>
        <div className="card h-100" style={{
          border: 'none',
          boxShadow: '0 2px 12px rgba(0,0,0,0.08)',
          borderRadius: '12px',
          overflow: 'hidden',
          transition: 'transform 0.2s, box-shadow 0.2s',
          cursor: 'pointer',
        }}
          onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-3px)'; e.currentTarget.style.boxShadow = '0 6px 20px rgba(0,0,0,0.12)'; }}
          onMouseLeave={e => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = '0 2px 12px rgba(0,0,0,0.08)'; }}
        >
          <div style={{
            height: '120px',
            background: garden.photo_url
              ? `url(${garden.photo_url}) center/cover`
              : 'linear-gradient(135deg, #d8f3dc, #95d5b2)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            position: 'relative',
          }}>
            {!garden.photo_url && (
              <i className="bi bi-flower2" style={{ fontSize: '2.5rem', color: '#2d6a4f', opacity: 0.3 }}></i>
            )}
            <div style={{
              position: 'absolute', top: '8px', right: '8px',
              backgroundColor: roleColor, color: 'white',
              padding: '3px 10px', borderRadius: '12px',
              fontSize: '0.75rem', fontWeight: 600,
            }}>
              <i className={`bi ${roleIcon} me-1`}></i>{role}
            </div>
          </div>
          <div className="card-body py-3">
            <div className="d-flex align-items-center gap-2 mb-1">
              <span style={{
                backgroundColor: MODEL_COLORS[garden.operating_model] || '#6b7280',
                color: 'white', padding: '1px 8px', borderRadius: '10px',
                fontSize: '0.7rem', fontWeight: 600,
              }}>{MODEL_LABELS[garden.operating_model]}</span>
            </div>
            <h6 className="fw-bold mb-1">{garden.name}</h6>
            <p className="text-muted small mb-0">
              <i className="bi bi-geo-alt me-1"></i>
              {garden.city}, {garden.state}
            </p>
          </div>
          <div className="card-footer bg-white border-top-0 py-2 px-3">
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem' }}>
              <span className="text-muted">{garden.total_plots} plots</span>
              <span style={{ color: '#40916c', fontWeight: 600 }}>{garden.available_plots} available</span>
            </div>
          </div>
        </div>
      </Link>
    </div>
  );
}

export default function MyGardens() {
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) { setLoading(false); return; }
    gardensAPI.myGardens().then(res => {
      setData(res.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [user]);

  if (!user) {
    return (
      <div className="text-center py-5">
        <i className="bi bi-person-lock" style={{ fontSize: '3rem', color: '#95d5b2' }}></i>
        <p className="text-muted mt-3 fs-5">Please <Link to="/login">log in</Link> to view your gardens.</p>
      </div>
    );
  }

  if (loading) return <div className="text-center py-5"><div className="spinner-border" style={{ color: '#2d6a4f' }}></div></div>;

  const totalInvolved = (data?.organized?.length || 0) + (data?.plot_holder?.length || 0) + (data?.waitlisted?.length || 0);

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-4">
        <div>
          <h2 className="fw-bold mb-1" style={{ color: '#2d6a4f' }}>
            <i className="bi bi-person-workspace me-2"></i>My Gardens
          </h2>
          <p className="text-muted mb-0">Your community garden involvement hub</p>
        </div>
        <div className="d-flex gap-2">
          <Link to="/gardens" className="btn btn-outline-success">
            <i className="bi bi-search me-1"></i>Browse Gardens
          </Link>
          <Link to="/gardens/create" className="btn" style={{ backgroundColor: '#2d6a4f', color: 'white' }}>
            <i className="bi bi-plus-circle me-1"></i>Create Garden
          </Link>
        </div>
      </div>

      {totalInvolved === 0 ? (
        <div className="text-center py-5">
          <div style={{
            width: '120px', height: '120px', borderRadius: '50%',
            backgroundColor: '#d8f3dc', margin: '0 auto 20px',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <i className="bi bi-tree" style={{ fontSize: '3rem', color: '#2d6a4f' }}></i>
          </div>
          <h4 className="fw-bold mb-2">No Gardens Yet</h4>
          <p className="text-muted mb-4" style={{ maxWidth: '400px', margin: '0 auto' }}>
            You are not part of any community gardens yet. Browse available gardens or create your own!
          </p>
          <div className="d-flex justify-content-center gap-3">
            <Link to="/gardens" className="btn btn-lg" style={{ backgroundColor: '#2d6a4f', color: 'white' }}>
              <i className="bi bi-search me-2"></i>Browse Gardens
            </Link>
            <Link to="/gardens/create" className="btn btn-lg btn-outline-success">
              <i className="bi bi-plus-circle me-2"></i>Create Garden
            </Link>
          </div>
        </div>
      ) : (
        <>
          {/* Gardens I Organize */}
          {data.organized && data.organized.length > 0 && (
            <div className="mb-5">
              <h4 className="fw-bold mb-3">
                <i className="bi bi-star me-2" style={{ color: '#f59e0b' }}></i>
                Gardens I Organize ({data.organized.length})
              </h4>
              <div className="row g-4">
                {data.organized.map(g => (
                  <GardenCard key={g.id} garden={g} role="Organizer" roleColor="#f59e0b" roleIcon="bi-star" />
                ))}
              </div>
            </div>
          )}

          {/* Gardens Where I Have Plots */}
          {data.plot_holder && data.plot_holder.length > 0 && (
            <div className="mb-5">
              <h4 className="fw-bold mb-3">
                <i className="bi bi-grid-3x3-gap me-2" style={{ color: '#40916c' }}></i>
                My Plot Gardens ({data.plot_holder.length})
              </h4>
              <div className="row g-4">
                {data.plot_holder.map(g => (
                  <GardenCard key={g.id} garden={g} role="Plot Holder" roleColor="#40916c" roleIcon="bi-grid-3x3-gap" />
                ))}
              </div>
            </div>
          )}

          {/* Gardens I'm on Waitlist For */}
          {data.waitlisted && data.waitlisted.length > 0 && (
            <div className="mb-5">
              <h4 className="fw-bold mb-3">
                <i className="bi bi-hourglass-split me-2" style={{ color: '#6b7280' }}></i>
                Waitlisted ({data.waitlisted.length})
              </h4>
              <div className="row g-4">
                {data.waitlisted.map(g => (
                  <GardenCard key={g.id} garden={g} role="Waitlisted" roleColor="#6b7280" roleIcon="bi-hourglass-split" />
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
