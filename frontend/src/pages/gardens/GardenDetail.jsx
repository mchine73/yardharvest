import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { gardensAPI } from '../../api';
import { useAuth } from '../../AuthContext';

const PLOT_COLORS = {
  available: '#40916c',
  assigned: '#3b82f6',
  reserved: '#f59e0b',
  maintenance: '#6b7280',
};

const EVENT_TYPE_COLORS = {
  workday: '#40916c',
  workshop: '#3b82f6',
  social: '#8b5cf6',
  meeting: '#6b7280',
  harvest_day: '#f59e0b',
};

const RESOURCE_CONDITION_COLORS = {
  new: '#40916c',
  good: '#3b82f6',
  fair: '#f59e0b',
  needs_repair: '#dc3545',
};

export default function GardenDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const [garden, setGarden] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');

  // Tab data
  const [plots, setPlots] = useState([]);
  const [resources, setResources] = useState([]);
  const [events, setEvents] = useState([]);
  const [harvests, setHarvests] = useState([]);
  const [impact, setImpact] = useState(null);
  const [members, setMembers] = useState([]);

  // Forms
  const [showHarvestForm, setShowHarvestForm] = useState(false);
  const [harvestForm, setHarvestForm] = useState({ category: '', variety: '', quantity_lbs: '', harvest_date: '', destination: 'personal', notes: '' });
  const [showResourceForm, setShowResourceForm] = useState(false);
  const [resourceForm, setResourceForm] = useState({ name: '', resource_type: 'tool', description: '', quantity: 1, condition: 'good' });
  const [showWaitlistForm, setShowWaitlistForm] = useState(false);
  const [waitlistForm, setWaitlistForm] = useState({ plot_size_pref: '', notes: '' });

  useEffect(() => {
    gardensAPI.detail(id).then(res => {
      setGarden(res.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    if (!garden) return;
    const noop = () => {};
    if (activeTab === 'plots') gardensAPI.plots(id).then(r => setPlots(r.data)).catch(noop);
    if (activeTab === 'resources') gardensAPI.resources(id).then(r => setResources(r.data)).catch(noop);
    if (activeTab === 'events') gardensAPI.events(id, { show: 'all' }).then(r => setEvents(r.data)).catch(noop);
    if (activeTab === 'harvest') gardensAPI.harvests(id).then(r => setHarvests(r.data)).catch(noop);
    if (activeTab === 'impact') gardensAPI.impact(id).then(r => setImpact(r.data)).catch(noop);
    if (activeTab === 'overview') gardensAPI.members(id).then(r => setMembers(r.data)).catch(noop);
  }, [activeTab, garden, id]);

  const handleRsvp = (eventId, status) => {
    gardensAPI.rsvpEvent(id, eventId, { status }).then(() => {
      gardensAPI.events(id, { show: 'all' }).then(r => setEvents(r.data));
    });
  };

  const handleCancelRsvp = (eventId) => {
    gardensAPI.cancelRsvp(id, eventId).then(() => {
      gardensAPI.events(id, { show: 'all' }).then(r => setEvents(r.data));
    });
  };

  const handleCheckout = (resId) => {
    gardensAPI.checkoutResource(id, resId).then(() => {
      gardensAPI.resources(id).then(r => setResources(r.data));
    });
  };

  const handleReturn = (resId) => {
    gardensAPI.returnResource(id, resId).then(() => {
      gardensAPI.resources(id).then(r => setResources(r.data));
    });
  };

  const handleLogHarvest = (e) => {
    e.preventDefault();
    gardensAPI.logHarvest(id, {
      ...harvestForm,
      quantity_lbs: parseFloat(harvestForm.quantity_lbs),
    }).then(() => {
      setShowHarvestForm(false);
      setHarvestForm({ category: '', variety: '', quantity_lbs: '', harvest_date: '', destination: 'personal', notes: '' });
      gardensAPI.harvests(id).then(r => setHarvests(r.data));
    });
  };

  const handleAddResource = (e) => {
    e.preventDefault();
    gardensAPI.addResource(id, resourceForm).then(() => {
      setShowResourceForm(false);
      setResourceForm({ name: '', resource_type: 'tool', description: '', quantity: 1, condition: 'good' });
      gardensAPI.resources(id).then(r => setResources(r.data));
    });
  };

  const handleJoinWaitlist = (e) => {
    e.preventDefault();
    gardensAPI.joinWaitlist(id, waitlistForm).then(() => {
      setShowWaitlistForm(false);
      setWaitlistForm({ plot_size_pref: '', notes: '' });
      gardensAPI.detail(id).then(res => setGarden(res.data));
    }).catch(err => alert(err.response?.data?.error || 'Error joining waitlist'));
  };

  if (loading) return <div className="text-center py-5"><div className="spinner-border" style={{ color: '#2d6a4f' }}></div></div>;
  if (!garden) return <div className="text-center py-5"><p>Garden not found</p></div>;

  const tabs = [
    { key: 'overview', label: 'Overview', icon: 'bi-info-circle' },
    { key: 'plots', label: 'Plots', icon: 'bi-grid-3x3' },
    { key: 'resources', label: 'Resources', icon: 'bi-tools' },
    { key: 'events', label: 'Events', icon: 'bi-calendar-event' },
    { key: 'harvest', label: 'Harvest Log', icon: 'bi-basket2' },
    { key: 'impact', label: 'Impact', icon: 'bi-bar-chart' },
  ];

  const now = new Date();

  return (
    <div>
      {/* Header */}
      <div style={{
        background: garden.photo_url
          ? `linear-gradient(rgba(0,0,0,0.5), rgba(0,0,0,0.6)), url(${garden.photo_url}) center/cover`
          : 'linear-gradient(135deg, #2d6a4f, #40916c)',
        borderRadius: '16px',
        padding: '40px 32px',
        color: 'white',
        marginBottom: '24px',
      }}>
        <Link to="/gardens" style={{ color: 'rgba(255,255,255,0.8)', textDecoration: 'none', fontSize: '0.9rem' }}>
          <i className="bi bi-arrow-left me-1"></i> All Gardens
        </Link>
        <h1 className="fw-bold mt-2 mb-1">{garden.name}</h1>
        <p className="mb-2" style={{ opacity: 0.9 }}>
          <i className="bi bi-geo-alt me-1"></i>
          {garden.address && `${garden.address}, `}{garden.city}, {garden.state} {garden.zip_code}
        </p>
        <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', fontSize: '0.9rem' }}>
          <span><i className="bi bi-person me-1"></i> Organized by {garden.organizer_name}</span>
          <span><i className="bi bi-grid-3x3-gap me-1"></i> {garden.total_plots} plots</span>
          <span style={{ color: garden.available_plots > 0 ? '#95d5b2' : '#fca5a5' }}>
            {garden.available_plots > 0 ? `${garden.available_plots} available` : 'All plots assigned'}
          </span>
        </div>
        {garden.user_is_organizer && (
          <Link to={`/gardens/${id}/admin`}
                className="btn mt-3"
                style={{ backgroundColor: '#c9a96e', color: '#3a2010', fontWeight: 600, borderRadius: '8px' }}>
            <i className="bi bi-shield-lock me-2"></i>Admin Portal
          </Link>
        )}
      </div>

      {/* Tabs */}
      <ul className="nav nav-tabs mb-4">
        {tabs.map(tab => (
          <li key={tab.key} className="nav-item">
            <button
              className={`nav-link ${activeTab === tab.key ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.key)}
              style={activeTab === tab.key ? { color: '#2d6a4f', borderBottomColor: '#2d6a4f', fontWeight: 600 } : { color: '#6b7280' }}
            >
              <i className={`bi ${tab.icon} me-1`}></i> {tab.label}
            </button>
          </li>
        ))}
      </ul>

      {/* Overview Tab */}
      {activeTab === 'overview' && (
        <div className="row">
          <div className="col-md-8">
            <div className="card mb-4" style={{ border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
              <div className="card-body">
                <h5 className="fw-bold mb-3">About This Garden</h5>
                <p style={{ whiteSpace: 'pre-wrap' }}>{garden.description || 'No description provided.'}</p>

                {garden.rules && (
                  <>
                    <h6 className="fw-bold mt-4 mb-2"><i className="bi bi-clipboard-check me-2"></i>Garden Rules</h6>
                    <p style={{ whiteSpace: 'pre-wrap', backgroundColor: '#f8f9fa', padding: '16px', borderRadius: '8px' }}>
                      {garden.rules}
                    </p>
                  </>
                )}
              </div>
            </div>

            {/* Quick Stats */}
            <div className="row g-3 mb-4">
              {[
                { label: 'Total Plots', value: garden.total_plots, icon: 'bi-grid-3x3-gap', color: '#2d6a4f' },
                { label: 'Available', value: garden.available_plots, icon: 'bi-check-circle', color: '#40916c' },
                { label: 'Members', value: garden.member_count, icon: 'bi-people', color: '#3b82f6' },
                { label: 'Harvest (lbs)', value: Math.round(garden.total_harvest_lbs), icon: 'bi-basket2', color: '#f59e0b' },
              ].map((stat, i) => (
                <div key={i} className="col-6 col-md-3">
                  <div style={{
                    textAlign: 'center',
                    padding: '20px 12px',
                    backgroundColor: '#f8f9fa',
                    borderRadius: '12px',
                    borderLeft: `4px solid ${stat.color}`,
                  }}>
                    <i className={`bi ${stat.icon}`} style={{ fontSize: '1.5rem', color: stat.color }}></i>
                    <div style={{ fontSize: '1.8rem', fontWeight: 'bold', color: '#1a1a1a' }}>{stat.value}</div>
                    <div style={{ fontSize: '0.8rem', color: '#6b7280' }}>{stat.label}</div>
                  </div>
                </div>
              ))}
            </div>

            {/* Upcoming Events Preview */}
            {garden.upcoming_events_list && garden.upcoming_events_list.length > 0 && (
              <div className="card mb-4" style={{ border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
                <div className="card-body">
                  <h5 className="fw-bold mb-3"><i className="bi bi-calendar-event me-2"></i>Upcoming Events</h5>
                  {garden.upcoming_events_list.map(event => (
                    <div key={event.id} style={{
                      display: 'flex', alignItems: 'center', gap: '12px',
                      padding: '12px', borderRadius: '8px', backgroundColor: '#f8f9fa', marginBottom: '8px',
                    }}>
                      <span style={{
                        backgroundColor: EVENT_TYPE_COLORS[event.event_type] || '#6b7280',
                        color: 'white', padding: '4px 10px', borderRadius: '8px', fontSize: '0.75rem', fontWeight: 600,
                      }}>{event.event_type}</span>
                      <div style={{ flex: 1 }}>
                        <strong>{event.title}</strong>
                        <div className="text-muted small">
                          {new Date(event.event_date).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}
                        </div>
                      </div>
                      <span className="text-muted small">{event.rsvp_going} going</span>
                    </div>
                  ))}
                  <button className="btn btn-sm btn-outline-success mt-2" onClick={() => setActiveTab('events')}>View All Events</button>
                </div>
              </div>
            )}
          </div>

          <div className="col-md-4">
            {/* Garden Info Card */}
            <div className="card mb-4" style={{ border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
              <div className="card-body">
                <h5 className="fw-bold mb-3">Garden Details</h5>
                <div className="mb-2">
                  <small className="text-muted">Operating Model</small>
                  <div className="fw-semibold" style={{ textTransform: 'capitalize' }}>{garden.operating_model}</div>
                </div>
                {garden.plot_fee_annual > 0 && (
                  <div className="mb-2">
                    <small className="text-muted">Annual Plot Fee</small>
                    <div className="fw-semibold">${garden.plot_fee_annual.toFixed(2)}</div>
                  </div>
                )}
                {garden.season_start && (
                  <div className="mb-2">
                    <small className="text-muted">Season</small>
                    <div className="fw-semibold">
                      {new Date(garden.season_start + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                      {' - '}
                      {garden.season_end && new Date(garden.season_end + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                    </div>
                  </div>
                )}
                {garden.contact_email && (
                  <div className="mb-2">
                    <small className="text-muted">Contact</small>
                    <div className="fw-semibold">{garden.contact_email}</div>
                  </div>
                )}
                <div className="mb-2">
                  <small className="text-muted">On Waitlist</small>
                  <div className="fw-semibold">{garden.waitlist_count} people</div>
                </div>
              </div>
            </div>

            {/* Join / Waitlist Actions */}
            {user && !garden.user_is_organizer && !garden.user_has_plot && !garden.user_on_waitlist && (
              <div className="card mb-4" style={{ border: '2px solid #95d5b2', borderRadius: '12px' }}>
                <div className="card-body text-center">
                  <h6 className="fw-bold mb-2">Want to join this garden?</h6>
                  <p className="text-muted small mb-3">
                    {garden.available_plots > 0
                      ? 'Plots are available! Join the waitlist and the organizer will assign you one.'
                      : 'All plots are assigned. Join the waitlist to be notified when one opens up.'}
                  </p>
                  <button className="btn w-100" style={{ backgroundColor: '#2d6a4f', color: 'white' }}
                    onClick={() => setShowWaitlistForm(true)}>
                    <i className="bi bi-person-plus me-2"></i>Join Waitlist
                  </button>
                </div>
              </div>
            )}
            {garden.user_on_waitlist && (
              <div className="alert" style={{ backgroundColor: '#d8f3dc', color: '#2d6a4f', border: 'none' }}>
                <i className="bi bi-hourglass-split me-2"></i>You are on the waitlist for this garden.
              </div>
            )}
            {garden.user_has_plot && (
              <div className="alert" style={{ backgroundColor: '#d8f3dc', color: '#2d6a4f', border: 'none' }}>
                <i className="bi bi-check-circle me-2"></i>You have a plot in this garden!
              </div>
            )}

            {/* Members */}
            {members.length > 0 && (
              <div className="card" style={{ border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
                <div className="card-body">
                  <h6 className="fw-bold mb-3"><i className="bi bi-people me-2"></i>Members ({members.length})</h6>
                  {members.slice(0, 8).map((m, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                      <div style={{
                        width: '32px', height: '32px', borderRadius: '50%',
                        backgroundColor: m.role === 'organizer' ? '#2d6a4f' : '#95d5b2',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        color: 'white', fontSize: '0.8rem', fontWeight: 'bold',
                      }}>
                        {m.name.charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <div className="fw-semibold small">{m.name}</div>
                        <div className="text-muted" style={{ fontSize: '0.75rem' }}>
                          {m.role === 'organizer' ? 'Organizer' : `Plot ${m.plot_number}`}
                        </div>
                      </div>
                    </div>
                  ))}
                  {members.length > 8 && <p className="text-muted small mt-2">+ {members.length - 8} more</p>}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Plots Tab */}
      {activeTab === 'plots' && (
        <div>
          <div className="d-flex justify-content-between align-items-center mb-3">
            <h5 className="fw-bold mb-0">Garden Plots</h5>
            <div style={{ display: 'flex', gap: '12px', fontSize: '0.8rem' }}>
              {Object.entries(PLOT_COLORS).map(([status, color]) => (
                <span key={status} style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <span style={{ width: '12px', height: '12px', borderRadius: '3px', backgroundColor: color, display: 'inline-block' }}></span>
                  <span style={{ textTransform: 'capitalize' }}>{status}</span>
                </span>
              ))}
            </div>
          </div>
          <div className="row g-2">
            {plots.map(plot => (
              <div key={plot.id} className="col-6 col-md-4 col-lg-3">
                <div style={{
                  border: `2px solid ${PLOT_COLORS[plot.status] || '#6b7280'}`,
                  borderRadius: '10px',
                  padding: '16px',
                  textAlign: 'center',
                  backgroundColor: plot.status === 'available' ? '#f0fdf4' : '#fff',
                  minHeight: '100px',
                }}>
                  <div style={{ fontSize: '1.2rem', fontWeight: 'bold', color: PLOT_COLORS[plot.status] }}>
                    #{plot.plot_number}
                  </div>
                  <div className="text-muted small">{plot.size}</div>
                  {plot.location_notes && <div className="text-muted" style={{ fontSize: '0.7rem' }}>{plot.location_notes}</div>}
                  {plot.assigned_to_name && (
                    <div style={{ fontSize: '0.8rem', marginTop: '4px', fontWeight: 600 }}>
                      <i className="bi bi-person me-1"></i>{plot.assigned_to_name}
                    </div>
                  )}
                  <span style={{
                    display: 'inline-block', marginTop: '4px',
                    backgroundColor: PLOT_COLORS[plot.status],
                    color: 'white', padding: '1px 8px', borderRadius: '8px',
                    fontSize: '0.7rem', fontWeight: 600, textTransform: 'capitalize',
                  }}>{plot.status}</span>
                </div>
              </div>
            ))}
          </div>
          {plots.length === 0 && <p className="text-muted text-center py-4">No plots have been set up yet.</p>}
        </div>
      )}

      {/* Resources Tab */}
      {activeTab === 'resources' && (
        <div>
          <div className="d-flex justify-content-between align-items-center mb-3">
            <h5 className="fw-bold mb-0">Shared Resources</h5>
            {user && (
              <button className="btn btn-sm" style={{ backgroundColor: '#2d6a4f', color: 'white' }}
                onClick={() => setShowResourceForm(!showResourceForm)}>
                <i className="bi bi-plus-circle me-1"></i>Add Resource
              </button>
            )}
          </div>

          {showResourceForm && (
            <div className="card mb-4" style={{ border: '2px solid #95d5b2' }}>
              <div className="card-body">
                <form onSubmit={handleAddResource}>
                  <div className="row g-3">
                    <div className="col-md-4">
                      <label className="form-label">Name</label>
                      <input type="text" className="form-control" required
                        value={resourceForm.name} onChange={e => setResourceForm({ ...resourceForm, name: e.target.value })} />
                    </div>
                    <div className="col-md-3">
                      <label className="form-label">Type</label>
                      <select className="form-select" value={resourceForm.resource_type}
                        onChange={e => setResourceForm({ ...resourceForm, resource_type: e.target.value })}>
                        <option value="tool">Tool</option>
                        <option value="supply">Supply</option>
                        <option value="infrastructure">Infrastructure</option>
                      </select>
                    </div>
                    <div className="col-md-2">
                      <label className="form-label">Qty</label>
                      <input type="number" className="form-control" min="1"
                        value={resourceForm.quantity} onChange={e => setResourceForm({ ...resourceForm, quantity: parseInt(e.target.value) })} />
                    </div>
                    <div className="col-md-3">
                      <label className="form-label">Condition</label>
                      <select className="form-select" value={resourceForm.condition}
                        onChange={e => setResourceForm({ ...resourceForm, condition: e.target.value })}>
                        <option value="new">New</option>
                        <option value="good">Good</option>
                        <option value="fair">Fair</option>
                        <option value="needs_repair">Needs Repair</option>
                      </select>
                    </div>
                    <div className="col-12">
                      <label className="form-label">Description</label>
                      <input type="text" className="form-control"
                        value={resourceForm.description} onChange={e => setResourceForm({ ...resourceForm, description: e.target.value })} />
                    </div>
                    <div className="col-12">
                      <button type="submit" className="btn me-2" style={{ backgroundColor: '#2d6a4f', color: 'white' }}>Add</button>
                      <button type="button" className="btn btn-outline-secondary" onClick={() => setShowResourceForm(false)}>Cancel</button>
                    </div>
                  </div>
                </form>
              </div>
            </div>
          )}

          <div className="table-responsive">
            <table className="table table-hover">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Type</th>
                  <th>Qty</th>
                  <th>Condition</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {resources.map(res => (
                  <tr key={res.id}>
                    <td>
                      <strong>{res.name}</strong>
                      {res.description && <div className="text-muted small">{res.description}</div>}
                    </td>
                    <td><span style={{ textTransform: 'capitalize' }}>{res.resource_type}</span></td>
                    <td>{res.quantity}</td>
                    <td>
                      <span style={{
                        backgroundColor: RESOURCE_CONDITION_COLORS[res.condition] || '#6b7280',
                        color: 'white', padding: '2px 8px', borderRadius: '8px', fontSize: '0.75rem',
                      }}>{res.condition?.replace('_', ' ')}</span>
                    </td>
                    <td>
                      {res.checked_out_to_id ? (
                        <span className="text-warning small">
                          <i className="bi bi-arrow-up-right me-1"></i>
                          {res.checked_out_to_name}
                        </span>
                      ) : (
                        <span className="text-success small"><i className="bi bi-check-circle me-1"></i>Available</span>
                      )}
                    </td>
                    <td>
                      {user && !res.checked_out_to_id && (
                        <button className="btn btn-sm btn-outline-success" onClick={() => handleCheckout(res.id)}>Check Out</button>
                      )}
                      {user && res.checked_out_to_id === user.id && (
                        <button className="btn btn-sm btn-outline-primary" onClick={() => handleReturn(res.id)}>Return</button>
                      )}
                    </td>
                  </tr>
                ))}
                {resources.length === 0 && (
                  <tr><td colSpan="6" className="text-center text-muted py-4">No shared resources yet.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Events Tab */}
      {activeTab === 'events' && (
        <div>
          <div className="d-flex justify-content-between align-items-center mb-3">
            <h5 className="fw-bold mb-0">Garden Events</h5>
            {user && (
              <Link to={`/gardens/${id}/events`} className="btn btn-sm" style={{ backgroundColor: '#2d6a4f', color: 'white' }}>
                <i className="bi bi-plus-circle me-1"></i>Manage Events
              </Link>
            )}
          </div>

          {events.length === 0 ? (
            <p className="text-muted text-center py-4">No events scheduled yet.</p>
          ) : (
            <div className="row g-3">
              {events.map(event => {
                const eventDate = new Date(event.event_date);
                const isPast = eventDate < now;
                return (
                  <div key={event.id} className="col-md-6">
                    <div className="card" style={{
                      border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
                      opacity: isPast ? 0.7 : 1,
                      borderLeft: `4px solid ${EVENT_TYPE_COLORS[event.event_type] || '#6b7280'}`,
                    }}>
                      <div className="card-body">
                        <div className="d-flex justify-content-between align-items-start mb-2">
                          <span style={{
                            backgroundColor: EVENT_TYPE_COLORS[event.event_type] || '#6b7280',
                            color: 'white', padding: '2px 10px', borderRadius: '8px',
                            fontSize: '0.75rem', fontWeight: 600, textTransform: 'capitalize',
                          }}>{event.event_type?.replace('_', ' ')}</span>
                          {isPast && <span className="badge bg-secondary">Past</span>}
                        </div>
                        <h6 className="fw-bold mb-1">{event.title}</h6>
                        <p className="text-muted small mb-2">
                          <i className="bi bi-calendar me-1"></i>
                          {eventDate.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })} at{' '}
                          {eventDate.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}
                          <span className="ms-2"><i className="bi bi-clock me-1"></i>{event.duration_hours}h</span>
                        </p>
                        {event.description && <p className="small mb-2">{event.description}</p>}
                        <div className="d-flex justify-content-between align-items-center">
                          <span className="small text-muted">
                            <i className="bi bi-people me-1"></i>{event.rsvp_going} going
                            {event.rsvp_maybe > 0 && `, ${event.rsvp_maybe} maybe`}
                            {event.max_volunteers && ` / ${event.max_volunteers} max`}
                          </span>
                          {user && !isPast && (
                            <div className="d-flex gap-1">
                              {event.user_rsvp === 'going' ? (
                                <button className="btn btn-sm btn-success" disabled>Going</button>
                              ) : (
                                <button className="btn btn-sm btn-outline-success" onClick={() => handleRsvp(event.id, 'going')}>Going</button>
                              )}
                              {event.user_rsvp === 'maybe' ? (
                                <button className="btn btn-sm btn-warning" disabled>Maybe</button>
                              ) : (
                                <button className="btn btn-sm btn-outline-warning" onClick={() => handleRsvp(event.id, 'maybe')}>Maybe</button>
                              )}
                              {event.user_rsvp && (
                                <button className="btn btn-sm btn-outline-danger" onClick={() => handleCancelRsvp(event.id)}>
                                  <i className="bi bi-x"></i>
                                </button>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Harvest Log Tab */}
      {activeTab === 'harvest' && (
        <div>
          <div className="d-flex justify-content-between align-items-center mb-3">
            <h5 className="fw-bold mb-0">Harvest Log</h5>
            {user && (
              <button className="btn btn-sm" style={{ backgroundColor: '#2d6a4f', color: 'white' }}
                onClick={() => setShowHarvestForm(!showHarvestForm)}>
                <i className="bi bi-plus-circle me-1"></i>Log Harvest
              </button>
            )}
          </div>

          {showHarvestForm && (
            <div className="card mb-4" style={{ border: '2px solid #95d5b2' }}>
              <div className="card-body">
                <h6 className="fw-bold mb-3">Log a Harvest</h6>
                <form onSubmit={handleLogHarvest}>
                  <div className="row g-3">
                    <div className="col-md-3">
                      <label className="form-label">Category</label>
                      <select className="form-select" required
                        value={harvestForm.category} onChange={e => setHarvestForm({ ...harvestForm, category: e.target.value })}>
                        <option value="">Select...</option>
                        <option value="tomatoes">Tomatoes</option>
                        <option value="peppers">Peppers</option>
                        <option value="greens">Greens</option>
                        <option value="herbs">Herbs</option>
                        <option value="squash">Squash</option>
                        <option value="beans">Beans</option>
                        <option value="root_vegetables">Root Vegetables</option>
                        <option value="corn">Corn</option>
                        <option value="berries">Berries</option>
                        <option value="other">Other</option>
                      </select>
                    </div>
                    <div className="col-md-3">
                      <label className="form-label">Variety</label>
                      <input type="text" className="form-control" placeholder="e.g. Cherokee Purple"
                        value={harvestForm.variety} onChange={e => setHarvestForm({ ...harvestForm, variety: e.target.value })} />
                    </div>
                    <div className="col-md-2">
                      <label className="form-label">Pounds</label>
                      <input type="number" className="form-control" step="0.1" min="0.1" required
                        value={harvestForm.quantity_lbs} onChange={e => setHarvestForm({ ...harvestForm, quantity_lbs: e.target.value })} />
                    </div>
                    <div className="col-md-2">
                      <label className="form-label">Date</label>
                      <input type="date" className="form-control" required
                        value={harvestForm.harvest_date} onChange={e => setHarvestForm({ ...harvestForm, harvest_date: e.target.value })} />
                    </div>
                    <div className="col-md-2">
                      <label className="form-label">Destination</label>
                      <select className="form-select" value={harvestForm.destination}
                        onChange={e => setHarvestForm({ ...harvestForm, destination: e.target.value })}>
                        <option value="personal">Personal</option>
                        <option value="shared">Shared</option>
                        <option value="food_bank">Food Bank</option>
                        <option value="marketplace">Marketplace</option>
                      </select>
                    </div>
                    <div className="col-12">
                      <button type="submit" className="btn me-2" style={{ backgroundColor: '#2d6a4f', color: 'white' }}>Log Harvest</button>
                      <button type="button" className="btn btn-outline-secondary" onClick={() => setShowHarvestForm(false)}>Cancel</button>
                    </div>
                  </div>
                </form>
              </div>
            </div>
          )}

          <div className="table-responsive">
            <table className="table table-hover">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Gardener</th>
                  <th>Category</th>
                  <th>Variety</th>
                  <th>Pounds</th>
                  <th>Destination</th>
                </tr>
              </thead>
              <tbody>
                {harvests.map(h => (
                  <tr key={h.id}>
                    <td>{new Date(h.harvest_date + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</td>
                    <td>{h.user_name}</td>
                    <td style={{ textTransform: 'capitalize' }}>{h.category?.replace('_', ' ')}</td>
                    <td>{h.variety}</td>
                    <td><strong>{h.quantity_lbs}</strong> lbs</td>
                    <td>
                      <span style={{
                        padding: '2px 8px', borderRadius: '8px', fontSize: '0.75rem',
                        backgroundColor: h.destination === 'food_bank' ? '#fef3c7' : h.destination === 'shared' ? '#dbeafe' : '#f3f4f6',
                        color: h.destination === 'food_bank' ? '#92400e' : h.destination === 'shared' ? '#1e40af' : '#374151',
                      }}>{h.destination?.replace('_', ' ')}</span>
                    </td>
                  </tr>
                ))}
                {harvests.length === 0 && (
                  <tr><td colSpan="6" className="text-center text-muted py-4">No harvests logged yet.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Impact Tab */}
      {activeTab === 'impact' && (
        <div>
          <div className="d-flex justify-content-between align-items-center mb-3">
            <h5 className="fw-bold mb-0">Impact Dashboard</h5>
            <Link to={`/gardens/${id}/impact`} className="btn btn-sm btn-outline-success">
              <i className="bi bi-graph-up me-1"></i>Full Dashboard
            </Link>
          </div>

          {impact ? (
            <>
              {/* Big Stats */}
              <div className="row g-3 mb-4">
                {[
                  { label: 'Total Harvested', value: `${Math.round(impact.total_harvest_lbs)} lbs`, icon: 'bi-basket2', color: '#2d6a4f' },
                  { label: 'Food Bank Donations', value: `${Math.round(impact.food_bank_lbs)} lbs`, icon: 'bi-heart', color: '#dc3545' },
                  { label: 'CO2 Saved', value: `${Math.round(impact.co2_saved_lbs)} lbs`, icon: 'bi-cloud', color: '#3b82f6' },
                  { label: 'Active Gardeners', value: impact.active_gardeners, icon: 'bi-people', color: '#8b5cf6' },
                  { label: 'Events Held', value: impact.total_events, icon: 'bi-calendar-check', color: '#f59e0b' },
                  { label: 'Volunteer Hours', value: impact.volunteer_hours, icon: 'bi-clock-history', color: '#40916c' },
                ].map((stat, i) => (
                  <div key={i} className="col-6 col-md-4 col-lg-2">
                    <div style={{
                      textAlign: 'center', padding: '20px 8px',
                      backgroundColor: '#f8f9fa', borderRadius: '12px',
                      borderTop: `4px solid ${stat.color}`,
                    }}>
                      <i className={`bi ${stat.icon}`} style={{ fontSize: '1.5rem', color: stat.color }}></i>
                      <div style={{ fontSize: '1.5rem', fontWeight: 'bold', marginTop: '4px' }}>{stat.value}</div>
                      <div style={{ fontSize: '0.75rem', color: '#6b7280' }}>{stat.label}</div>
                    </div>
                  </div>
                ))}
              </div>

              {/* Category Breakdown Bar Chart */}
              {impact.category_breakdown.length > 0 && (
                <div className="card mb-4" style={{ border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
                  <div className="card-body">
                    <h6 className="fw-bold mb-3">Harvest by Category</h6>
                    {impact.category_breakdown.map((cat, i) => {
                      const maxLbs = Math.max(...impact.category_breakdown.map(c => c.lbs));
                      const pct = maxLbs > 0 ? (cat.lbs / maxLbs) * 100 : 0;
                      return (
                        <div key={i} className="mb-2">
                          <div className="d-flex justify-content-between mb-1">
                            <span className="small fw-semibold" style={{ textTransform: 'capitalize' }}>{cat.category?.replace('_', ' ')}</span>
                            <span className="small text-muted">{cat.lbs} lbs</span>
                          </div>
                          <div style={{ backgroundColor: '#e5e7eb', borderRadius: '4px', height: '20px' }}>
                            <div style={{
                              width: `${pct}%`, backgroundColor: '#40916c',
                              borderRadius: '4px', height: '100%', transition: 'width 0.5s',
                            }}></div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Destination Breakdown */}
              {impact.destination_breakdown.length > 0 && (
                <div className="card" style={{ border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
                  <div className="card-body">
                    <h6 className="fw-bold mb-3">Where Produce Goes</h6>
                    <div className="row g-3">
                      {impact.destination_breakdown.map((dest, i) => (
                        <div key={i} className="col-6 col-md-3">
                          <div style={{
                            textAlign: 'center', padding: '16px', borderRadius: '10px',
                            backgroundColor: dest.destination === 'food_bank' ? '#fef3c7'
                              : dest.destination === 'shared' ? '#dbeafe'
                              : dest.destination === 'marketplace' ? '#d8f3dc'
                              : '#f3f4f6',
                          }}>
                            <div style={{ fontSize: '1.3rem', fontWeight: 'bold' }}>{Math.round(dest.lbs)} lbs</div>
                            <div className="small" style={{ textTransform: 'capitalize' }}>{dest.destination?.replace('_', ' ')}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="text-center py-5"><div className="spinner-border" style={{ color: '#2d6a4f' }}></div></div>
          )}
        </div>
      )}

      {/* Waitlist Form Modal (overlay) */}
      {showWaitlistForm && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.5)', zIndex: 1050,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }} onClick={() => setShowWaitlistForm(false)}>
          <div className="card" style={{ maxWidth: '480px', width: '90%' }} onClick={e => e.stopPropagation()}>
            <div className="card-body">
              <h5 className="fw-bold mb-3">Join Waitlist - {garden.name}</h5>
              <form onSubmit={handleJoinWaitlist}>
                <div className="mb-3">
                  <label className="form-label">Preferred Plot Size</label>
                  <input type="text" className="form-control" placeholder="e.g. 4x8 ft"
                    value={waitlistForm.plot_size_pref}
                    onChange={e => setWaitlistForm({ ...waitlistForm, plot_size_pref: e.target.value })} />
                </div>
                <div className="mb-3">
                  <label className="form-label">Notes for Organizer</label>
                  <textarea className="form-control" rows="3" placeholder="Tell the organizer about your gardening experience..."
                    value={waitlistForm.notes}
                    onChange={e => setWaitlistForm({ ...waitlistForm, notes: e.target.value })} />
                </div>
                <div className="d-flex gap-2">
                  <button type="submit" className="btn" style={{ backgroundColor: '#2d6a4f', color: 'white' }}>
                    <i className="bi bi-person-plus me-2"></i>Join Waitlist
                  </button>
                  <button type="button" className="btn btn-outline-secondary" onClick={() => setShowWaitlistForm(false)}>Cancel</button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
