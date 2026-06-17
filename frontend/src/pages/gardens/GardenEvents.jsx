import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { gardensAPI } from '../../api';
import { useAuth } from '../../AuthContext';
import { toast } from '../../components/dialog/dialogService';

const EVENT_TYPE_COLORS = {
  workday: 'var(--brand-accent)',
  workshop: '#3f7ddb',
  social: '#8b5cf6',
  meeting: '#6b7280',
  harvest_day: 'var(--brand-gold)',
};

const EVENT_TYPE_ICONS = {
  workday: 'bi-tools',
  workshop: 'bi-lightbulb',
  social: 'bi-emoji-smile',
  meeting: 'bi-chat-dots',
  harvest_day: 'bi-basket2',
};

export default function GardenEvents() {
  const { id } = useParams();
  const { user } = useAuth();
  const [garden, setGarden] = useState(null);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showFilter, setShowFilter] = useState('upcoming');
  const [showCreateForm, setShowCreateForm] = useState(false);

  const [eventForm, setEventForm] = useState({
    title: '',
    description: '',
    event_type: 'workday',
    event_date: '',
    event_time: '09:00',
    duration_hours: 2,
    max_volunteers: '',
    recurring: 'none',
  });

  useEffect(() => {
    Promise.all([
      gardensAPI.detail(id),
      gardensAPI.events(id, { show: 'all' }),
    ]).then(([gardenRes, eventsRes]) => {
      setGarden(gardenRes.data);
      setEvents(eventsRes.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [id]);

  const fetchEvents = (filter) => {
    setShowFilter(filter);
    gardensAPI.events(id, { show: filter }).then(r => setEvents(r.data));
  };

  const handleRsvp = (eventId, status) => {
    gardensAPI.rsvpEvent(id, eventId, { status }).then(() => {
      gardensAPI.events(id, { show: showFilter }).then(r => setEvents(r.data));
    });
  };

  const handleCancelRsvp = (eventId) => {
    gardensAPI.cancelRsvp(id, eventId).then(() => {
      gardensAPI.events(id, { show: showFilter }).then(r => setEvents(r.data));
    });
  };

  const handleCreateEvent = (e) => {
    e.preventDefault();
    const dateTime = `${eventForm.event_date}T${eventForm.event_time}:00`;
    gardensAPI.createEvent(id, {
      title: eventForm.title,
      description: eventForm.description,
      event_type: eventForm.event_type,
      event_date: dateTime,
      duration_hours: parseFloat(eventForm.duration_hours),
      max_volunteers: eventForm.max_volunteers ? parseInt(eventForm.max_volunteers) : null,
      recurring: eventForm.recurring,
    }).then(() => {
      setShowCreateForm(false);
      setEventForm({ title: '', description: '', event_type: 'workday', event_date: '', event_time: '09:00', duration_hours: 2, max_volunteers: '', recurring: 'none' });
      gardensAPI.events(id, { show: showFilter }).then(r => setEvents(r.data));
    }).catch(err => toast(err.response?.data?.error || 'Error creating event', { type: 'error' }));
  };

  if (loading) return <div className="text-center py-5"><div className="spinner-border" style={{ color: 'var(--brand-secondary)' }}></div></div>;
  if (!garden) return <div className="text-center py-5"><p>Garden not found</p></div>;

  const now = new Date();

  // Group events by month for calendar view
  const eventsByMonth = {};
  events.forEach(event => {
    const date = new Date(event.event_date);
    const key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
    if (!eventsByMonth[key]) eventsByMonth[key] = [];
    eventsByMonth[key].push(event);
  });

  return (
    <div>
      <Link to={`/gardens/${id}`} style={{ color: 'var(--brand-secondary)', textDecoration: 'none', fontSize: '0.9rem' }}>
        <i className="bi bi-arrow-left me-1"></i> Back to {garden.name}
      </Link>

      <div className="d-flex justify-content-between align-items-center mt-3 mb-4">
        <h2 className="fw-bold mb-0" style={{ color: 'var(--brand-secondary)' }}>
          <i className="bi bi-calendar-event me-2"></i>Events - {garden.name}
        </h2>
        {user && (
          <button className="btn" style={{ backgroundColor: 'var(--brand-secondary)', color: 'white' }}
            onClick={() => setShowCreateForm(!showCreateForm)}>
            <i className="bi bi-plus-circle me-2"></i>Create Event
          </button>
        )}
      </div>

      {/* Create Event Form */}
      {showCreateForm && (
        <div className="card mb-4" style={{ border: '2px solid var(--brand-light-green)', borderRadius: '12px' }}>
          <div className="card-body p-4">
            <h5 className="fw-bold mb-3">Create New Event</h5>
            <form onSubmit={handleCreateEvent}>
              <div className="row g-3">
                <div className="col-md-8">
                  <label className="form-label fw-semibold">Event Title *</label>
                  <input type="text" className="form-control" required placeholder="e.g. Spring Cleanup Workday"
                    value={eventForm.title} onChange={e => setEventForm({ ...eventForm, title: e.target.value })} />
                </div>
                <div className="col-md-4">
                  <label className="form-label fw-semibold">Event Type</label>
                  <select className="form-select" value={eventForm.event_type}
                    onChange={e => setEventForm({ ...eventForm, event_type: e.target.value })}>
                    <option value="workday">Workday</option>
                    <option value="workshop">Workshop</option>
                    <option value="social">Social</option>
                    <option value="meeting">Meeting</option>
                    <option value="harvest_day">Harvest Day</option>
                  </select>
                </div>
                <div className="col-md-4">
                  <label className="form-label fw-semibold">Date *</label>
                  <input type="date" className="form-control" required
                    value={eventForm.event_date} onChange={e => setEventForm({ ...eventForm, event_date: e.target.value })} />
                </div>
                <div className="col-md-3">
                  <label className="form-label fw-semibold">Time</label>
                  <input type="time" className="form-control"
                    value={eventForm.event_time} onChange={e => setEventForm({ ...eventForm, event_time: e.target.value })} />
                </div>
                <div className="col-md-2">
                  <label className="form-label fw-semibold">Hours</label>
                  <input type="number" className="form-control" step="0.5" min="0.5"
                    value={eventForm.duration_hours} onChange={e => setEventForm({ ...eventForm, duration_hours: e.target.value })} />
                </div>
                <div className="col-md-3">
                  <label className="form-label fw-semibold">Max Volunteers</label>
                  <input type="number" className="form-control" min="1" placeholder="Unlimited"
                    value={eventForm.max_volunteers} onChange={e => setEventForm({ ...eventForm, max_volunteers: e.target.value })} />
                </div>
                <div className="col-md-3">
                  <label className="form-label fw-semibold">Repeats</label>
                  <select className="form-select" value={eventForm.recurring}
                    onChange={e => setEventForm({ ...eventForm, recurring: e.target.value })}>
                    <option value="none">One-time</option>
                    <option value="weekly">Weekly</option>
                    <option value="biweekly">Every 2 weeks</option>
                    <option value="monthly">Monthly</option>
                  </select>
                  <div className="form-text">
                    {eventForm.recurring === 'none'
                      ? 'Set a cadence for a recurring volunteer opportunity.'
                      : 'Creates this date plus 8 more occurrences.'}
                  </div>
                </div>
                <div className="col-12">
                  <label className="form-label fw-semibold">Description</label>
                  <textarea className="form-control" rows="3" placeholder="What will happen at this event? What should people bring?"
                    value={eventForm.description} onChange={e => setEventForm({ ...eventForm, description: e.target.value })} />
                </div>
                <div className="col-12">
                  <button type="submit" className="btn me-2" style={{ backgroundColor: 'var(--brand-secondary)', color: 'white' }}>
                    <i className="bi bi-calendar-plus me-2"></i>Create Event
                  </button>
                  <button type="button" className="btn btn-outline-secondary" onClick={() => setShowCreateForm(false)}>Cancel</button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Filter Tabs */}
      <div className="btn-group mb-4">
        {['upcoming', 'past', 'all'].map(filter => (
          <button key={filter} className={`btn ${showFilter === filter ? 'btn-success' : 'btn-outline-success'}`}
            style={showFilter === filter ? { backgroundColor: 'var(--brand-secondary)', borderColor: 'var(--brand-secondary)' } : {}}
            onClick={() => fetchEvents(filter)}>
            {filter === 'upcoming' ? 'Upcoming' : filter === 'past' ? 'Past' : 'All'}
          </button>
        ))}
      </div>

      {/* Calendar View by Month */}
      {events.length === 0 ? (
        <div className="text-center py-5">
          <i className="bi bi-calendar-x" style={{ fontSize: '3rem', color: 'var(--brand-light-green)' }}></i>
          <p className="text-muted mt-3 fs-5">
            {showFilter === 'upcoming' ? 'No upcoming events scheduled.' : 'No events found.'}
          </p>
        </div>
      ) : (
        Object.entries(eventsByMonth).map(([monthKey, monthEvents]) => {
          const [year, month] = monthKey.split('-');
          const monthName = new Date(parseInt(year), parseInt(month) - 1).toLocaleString('en-US', { month: 'long', year: 'numeric' });
          return (
            <div key={monthKey} className="mb-4">
              <h5 className="fw-bold mb-3" style={{ color: 'var(--brand-secondary)' }}>
                <i className="bi bi-calendar3 me-2"></i>{monthName}
              </h5>
              <div className="row g-3">
                {monthEvents.map(event => {
                  const eventDate = new Date(event.event_date);
                  const isPast = eventDate < now;
                  const spotsLeft = event.max_volunteers ? event.max_volunteers - event.rsvp_going : null;
                  return (
                    <div key={event.id} className="col-md-6 col-lg-4">
                      <div className="card h-100" style={{
                        border: 'none',
                        boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
                        borderRadius: '12px',
                        opacity: isPast ? 0.7 : 1,
                        overflow: 'hidden',
                      }}>
                        {/* Event Type Header */}
                        <div style={{
                          backgroundColor: EVENT_TYPE_COLORS[event.event_type] || '#6b7280',
                          padding: '12px 16px',
                          color: 'white',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                        }}>
                          <span style={{ fontWeight: 600, fontSize: '0.85rem', textTransform: 'capitalize' }}>
                            <i className={`bi ${EVENT_TYPE_ICONS[event.event_type] || 'bi-calendar'} me-2`}></i>
                            {event.event_type?.replace('_', ' ')}
                          </span>
                          {isPast && <span className="badge bg-dark">Past</span>}
                        </div>

                        <div className="card-body">
                          <h6 className="fw-bold mb-2">{event.title}</h6>

                          {/* Date & Time */}
                          <div className="mb-2">
                            <div className="small">
                              <i className="bi bi-calendar me-1" style={{ color: 'var(--brand-secondary)' }}></i>
                              {eventDate.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}
                            </div>
                            <div className="small">
                              <i className="bi bi-clock me-1" style={{ color: 'var(--brand-secondary)' }}></i>
                              {eventDate.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}
                              {' - '}
                              {new Date(eventDate.getTime() + event.duration_hours * 3600000).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}
                              <span className="text-muted ms-1">({event.duration_hours}h)</span>
                            </div>
                          </div>

                          {event.description && (
                            <p className="small text-muted mb-2" style={{
                              overflow: 'hidden', textOverflow: 'ellipsis',
                              display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical',
                            }}>{event.description}</p>
                          )}

                          {/* RSVP Info */}
                          <div style={{
                            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                            padding: '8px 12px', backgroundColor: '#f8f9fa', borderRadius: '8px',
                            fontSize: '0.85rem',
                          }}>
                            <span>
                              <strong>{event.rsvp_going}</strong> going
                              {event.rsvp_maybe > 0 && <span className="text-muted"> + {event.rsvp_maybe} maybe</span>}
                            </span>
                            {spotsLeft !== null && (
                              <span style={{ color: spotsLeft <= 3 ? '#e0564f' : '#6b7280' }}>
                                {spotsLeft > 0 ? `${spotsLeft} spots left` : 'Full'}
                              </span>
                            )}
                          </div>

                          <div className="small text-muted mt-2">
                            Created by {event.created_by_name}
                          </div>
                        </div>

                        {/* RSVP Buttons */}
                        {user && !isPast && (
                          <div className="card-footer bg-white" style={{ borderTop: '1px solid #f0f0f0', padding: '12px 16px' }}>
                            <div className="d-flex gap-2">
                              <button
                                className={`btn btn-sm flex-fill ${event.user_rsvp === 'going' ? 'btn-success' : 'btn-outline-success'}`}
                                style={event.user_rsvp === 'going' ? { backgroundColor: '#22242a', borderColor: '#22242a' } : {}}
                                onClick={() => handleRsvp(event.id, 'going')}
                                disabled={event.user_rsvp === 'going'}
                              >
                                <i className="bi bi-check-circle me-1"></i>Going
                              </button>
                              <button
                                className={`btn btn-sm flex-fill ${event.user_rsvp === 'maybe' ? 'btn-warning' : 'btn-outline-warning'}`}
                                onClick={() => handleRsvp(event.id, 'maybe')}
                                disabled={event.user_rsvp === 'maybe'}
                              >
                                <i className="bi bi-question-circle me-1"></i>Maybe
                              </button>
                              {event.user_rsvp && (
                                <button className="btn btn-sm btn-outline-danger" onClick={() => handleCancelRsvp(event.id)}>
                                  <i className="bi bi-x-circle"></i>
                                </button>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })
      )}
    </div>
  );
}
