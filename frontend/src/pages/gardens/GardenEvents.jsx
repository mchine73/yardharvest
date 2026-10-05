import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { gardensAPI } from '../../api';
import { useTranslation } from 'react-i18next';
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

// Was rendering "harvest day" from a naive underscore replace.
const EVENT_TYPE_KEYS = {
  workday: 'garden.eventTypeWorkday', workshop: 'garden.eventTypeWorkshop',
  social: 'garden.eventTypeSocial', meeting: 'garden.eventTypeMeeting',
  harvest_day: 'garden.eventTypeHarvestDay',
};

export default function GardenEvents() {
  const { t } = useTranslation();
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
    }).catch(err => toast(err.response?.data?.error || t('garden.errEventCreate'), { type: 'error' }));
  };

  if (loading) return <div className="text-center py-5"><div className="spinner-border" style={{ color: 'var(--brand-secondary)' }}></div></div>;
  if (!garden) return <div className="text-center py-5"><p>{t('garden.notFound')}</p></div>;

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
        <i className="bi bi-arrow-left me-1"></i> {t('garden.backToGarden', { name: garden.name })}
      </Link>

      <div className="d-flex justify-content-between align-items-center mt-3 mb-4">
        <h2 className="fw-bold mb-0" style={{ color: 'var(--brand-secondary)' }}>
          <i className="bi bi-calendar-event me-2"></i>{t('garden.eventsFor', { name: garden.name })}
        </h2>
        {user && (
          <button className="btn" style={{ backgroundColor: 'var(--brand-secondary)', color: 'white' }}
            onClick={() => setShowCreateForm(!showCreateForm)}>
            <i className="bi bi-plus-circle me-2"></i>{t('organizer.createEvent')}
          </button>
        )}
      </div>

      {/* Create Event Form */}
      {showCreateForm && (
        <div className="card mb-4" style={{ border: '2px solid var(--brand-light-green)', borderRadius: '12px' }}>
          <div className="card-body p-4">
            <h5 className="fw-bold mb-3">{t('organizer.createNewEvent')}</h5>
            <form onSubmit={handleCreateEvent}>
              <div className="row g-3">
                <div className="col-md-8">
                  <label className="form-label fw-semibold">{t('organizer.eventTitle')} *</label>
                  <input type="text" className="form-control" required placeholder={t('organizer.eventTitlePlaceholder')}
                    value={eventForm.title} onChange={e => setEventForm({ ...eventForm, title: e.target.value })} />
                </div>
                <div className="col-md-4">
                  <label className="form-label fw-semibold">{t('organizer.eventType')}</label>
                  <select className="form-select" value={eventForm.event_type}
                    onChange={e => setEventForm({ ...eventForm, event_type: e.target.value })}>
                    <option value="workday">{t('organizer.typeWorkday')}</option>
                    <option value="workshop">{t('organizer.typeWorkshop')}</option>
                    <option value="social">{t('organizer.typeSocial')}</option>
                    <option value="meeting">{t('organizer.typeMeeting')}</option>
                    <option value="harvest_day">{t('organizer.typeHarvestDay')}</option>
                  </select>
                </div>
                <div className="col-md-4">
                  <label className="form-label fw-semibold">{t('garden.date')} *</label>
                  <input type="date" className="form-control" required
                    value={eventForm.event_date} onChange={e => setEventForm({ ...eventForm, event_date: e.target.value })} />
                </div>
                <div className="col-md-3">
                  <label className="form-label fw-semibold">{t('organizer.time')}</label>
                  <input type="time" className="form-control"
                    value={eventForm.event_time} onChange={e => setEventForm({ ...eventForm, event_time: e.target.value })} />
                </div>
                <div className="col-md-2">
                  <label className="form-label fw-semibold">{t('organizer.hours')}</label>
                  <input type="number" className="form-control" step="0.5" min="0.5"
                    value={eventForm.duration_hours} onChange={e => setEventForm({ ...eventForm, duration_hours: e.target.value })} />
                </div>
                <div className="col-md-3">
                  <label className="form-label fw-semibold">{t('organizer.maxVolunteers')}</label>
                  <input type="number" className="form-control" min="1" placeholder={t('organizer.unlimited')}
                    value={eventForm.max_volunteers} onChange={e => setEventForm({ ...eventForm, max_volunteers: e.target.value })} />
                </div>
                <div className="col-md-3">
                  <label className="form-label fw-semibold">{t('organizer.repeats')}</label>
                  <select className="form-select" value={eventForm.recurring}
                    onChange={e => setEventForm({ ...eventForm, recurring: e.target.value })}>
                    <option value="none">{t('organizer.repeatOnce')}</option>
                    <option value="weekly">{t('organizer.repeatWeekly')}</option>
                    <option value="biweekly">{t('organizer.repeatBiweekly')}</option>
                    <option value="monthly">{t('organizer.repeatMonthly')}</option>
                  </select>
                  <div className="form-text">
                    {eventForm.recurring === 'none'
                      ? t('garden.recurNewHelp')
                      : t('garden.recurMore')}
                  </div>
                </div>
                <div className="col-12">
                  <label className="form-label fw-semibold">{t('garden.description')}</label>
                  <textarea className="form-control" rows="3" placeholder={t('organizer.descriptionPlaceholder')}
                    value={eventForm.description} onChange={e => setEventForm({ ...eventForm, description: e.target.value })} />
                </div>
                <div className="col-12">
                  <button type="submit" className="btn me-2" style={{ backgroundColor: 'var(--brand-secondary)', color: 'white' }}>
                    <i className="bi bi-calendar-plus me-2"></i>{t('organizer.createEvent')}
                  </button>
                  <button type="button" className="btn btn-outline-secondary" onClick={() => setShowCreateForm(false)}>{t('garden.cancel')}</button>
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
            {filter === 'upcoming' ? t('garden.filterUpcoming') : filter === 'past' ? t('garden.filterPast') : t('garden.filterAll')}
          </button>
        ))}
      </div>

      {/* Calendar View by Month */}
      {events.length === 0 ? (
        <div className="text-center py-5">
          <i className="bi bi-calendar-x" style={{ fontSize: '3rem', color: '#ccc' }}></i>
          <p className="text-muted mt-3 fs-5">
            {showFilter === 'upcoming' ? t('garden.noUpcomingEvents') : t('garden.noEventsFound')}
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
                            {EVENT_TYPE_KEYS[event.event_type] ? t(EVENT_TYPE_KEYS[event.event_type]) : event.event_type}
                          </span>
                          {isPast && <span className="badge bg-dark">{t('garden.past')}</span>}
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
                              {event.rsvp_maybe > 0 && <span className="text-muted"> {t('garden.rsvpMaybeCount', { count: event.rsvp_maybe })}</span>}
                            </span>
                            {spotsLeft !== null && (
                              <span style={{ color: spotsLeft <= 3 ? '#e0564f' : '#6b7280' }}>
                                {spotsLeft > 0 ? t('garden.spotsLeftCount', { count: spotsLeft }) : t('garden.full')}
                              </span>
                            )}
                          </div>

                          <div className="small text-muted mt-2">
                            {t('garden.createdBy', { name: event.created_by_name })}
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
                                <i className="bi bi-check-circle me-1"></i>{t('garden.going')}
                              </button>
                              <button
                                className={`btn btn-sm flex-fill ${event.user_rsvp === 'maybe' ? 'btn-warning' : 'btn-outline-warning'}`}
                                onClick={() => handleRsvp(event.id, 'maybe')}
                                disabled={event.user_rsvp === 'maybe'}
                              >
                                <i className="bi bi-question-circle me-1"></i>{t('garden.maybe')}
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
