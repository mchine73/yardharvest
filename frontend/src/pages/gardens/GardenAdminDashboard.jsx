import { useState, useEffect, Fragment } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { gardensAPI, gardenAdminAPI } from '../../api';
import { useAuth } from '../../AuthContext';

const PLOT_STATUS_COLORS = {
  available: '#40916c',
  assigned: '#3b82f6',
  reserved: '#f59e0b',
  maintenance: '#6b7280',
};

const PHOTO_CATEGORIES = ['all', 'harvest', 'plot', 'event', 'wildlife', 'bloom'];

const PRIORITY_STYLES = {
  normal: { bg: 'bg-primary', color: '#0d6efd' },
  important: { bg: 'bg-warning', color: '#ffc107' },
  urgent: { bg: 'bg-danger', color: '#dc3545' },
};

const RESOURCE_CONDITION_COLORS = {
  new: '#40916c',
  good: '#3b82f6',
  fair: '#f59e0b',
  needs_repair: '#dc3545',
};

const SIDEBAR_TABS = [
  { key: 'dashboard', label: 'Dashboard', icon: 'bi-speedometer2' },
  { key: 'plots', label: 'Plots', icon: 'bi-grid-3x3-gap' },
  { key: 'events', label: 'Events', icon: 'bi-calendar-event' },
  { key: 'messages', label: 'Messages', icon: 'bi-envelope' },
  { key: 'photos', label: 'Photos', icon: 'bi-camera' },
  { key: 'announcements', label: 'Announcements', icon: 'bi-megaphone' },
  { key: 'resources', label: 'Resources', icon: 'bi-tools' },
  { key: 'email', label: 'Email', icon: 'bi-envelope-at' },
  { key: 'settings', label: 'Settings', icon: 'bi-gear' },
];

export default function GardenAdminDashboard() {
  const { id } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();

  const [garden, setGarden] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('dashboard');

  // Dashboard
  const [stats, setStats] = useState(null);
  const [activity, setActivity] = useState([]);

  // Plots
  const [plots, setPlots] = useState([]);
  const [waitlist, setWaitlist] = useState([]);
  const [editingPlot, setEditingPlot] = useState(null);
  const [plotForm, setPlotForm] = useState({ size: '', location_notes: '', renewal_date: '' });

  // Events
  const [events, setEvents] = useState([]);
  const [showEventForm, setShowEventForm] = useState(false);
  const [editingEvent, setEditingEvent] = useState(null);
  const [eventForm, setEventForm] = useState({ title: '', description: '', event_type: 'workday', event_date: '', event_time: '09:00', duration_hours: 2, max_volunteers: '' });
  const [attendeesEvent, setAttendeesEvent] = useState(null);
  const [attendees, setAttendees] = useState([]);

  // Messages
  const [messages, setMessages] = useState([]);
  const [plotOwners, setPlotOwners] = useState([]);
  const [msgForm, setMsgForm] = useState({ recipient_id: '', subject: '', body: '' });
  const [showBroadcast, setShowBroadcast] = useState(false);
  const [broadcastForm, setBroadcastForm] = useState({ subject: '', body: '' });

  // Photos
  const [photos, setPhotos] = useState([]);
  const [photoFilter, setPhotoFilter] = useState('all');
  const [showPhotoForm, setShowPhotoForm] = useState(false);
  const [photoForm, setPhotoForm] = useState({ photo_url: '', caption: '', category: 'harvest' });
  const [expandedComments, setExpandedComments] = useState(null);
  const [photoComments, setPhotoComments] = useState([]);
  const [commentText, setCommentText] = useState('');

  // Announcements
  const [announcements, setAnnouncements] = useState([]);
  const [showAnnForm, setShowAnnForm] = useState(false);
  const [editingAnn, setEditingAnn] = useState(null);
  const [annForm, setAnnForm] = useState({ title: '', body: '', priority: 'normal', pinned: false });

  // Resources
  const [resources, setResources] = useState([]);
  const [showResForm, setShowResForm] = useState(false);
  const [resForm, setResForm] = useState({ name: '', resource_type: 'tool', description: '', quantity: 1, condition: 'good' });

  // Settings
  const [settingsForm, setSettingsForm] = useState({});
  const [settingsSaved, setSettingsSaved] = useState(false);

  // Email Config
  const [emailConfig, setEmailConfig] = useState(null);
  const [emailSaved, setEmailSaved] = useState(false);

  useEffect(() => {
    gardensAPI.detail(id).then(res => {
      setGarden(res.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    if (!garden) return;
    if (activeTab === 'dashboard') {
      gardenAdminAPI.dashboard(id).then(r => setStats(r.data)).catch(() => {});
      gardenAdminAPI.activity(id).then(r => setActivity(r.data.activities || r.data || [])).catch(() => {});
    }
    if (activeTab === 'plots') {
      gardenAdminAPI.plots(id).then(r => setPlots(r.data.plots || r.data || [])).catch(() => {});
      gardensAPI.viewWaitlist(id).then(r => setWaitlist(r.data.waitlist || r.data || [])).catch(() => {});
    }
    if (activeTab === 'events') {
      gardensAPI.events(id, { show: 'all' }).then(r => setEvents(r.data)).catch(() => {});
    }
    if (activeTab === 'messages') {
      gardenAdminAPI.messages(id).then(r => setMessages(r.data.messages || r.data || [])).catch(() => {});
      gardenAdminAPI.plots(id).then(r => {
        const owners = (r.data.plots || r.data || []).filter(p => p.assigned_to_id).map(p => ({ id: p.assigned_to_id, name: p.assigned_to_name }));
        const unique = owners.filter((v, i, a) => a.findIndex(t => t.id === v.id) === i);
        setPlotOwners(unique);
      }).catch(() => {});
    }
    if (activeTab === 'photos') {
      const params = photoFilter !== 'all' ? { category: photoFilter } : {};
      gardenAdminAPI.photos(id, params).then(r => setPhotos(r.data.photos || r.data || [])).catch(() => {});
    }
    if (activeTab === 'announcements') {
      gardenAdminAPI.announcements(id).then(r => setAnnouncements(r.data.announcements || r.data || [])).catch(() => {});
    }
    if (activeTab === 'resources') {
      gardensAPI.resources(id).then(r => setResources(r.data)).catch(() => {});
    }
    if (activeTab === 'email') {
      gardenAdminAPI.getEmailConfig(id).then(r => setEmailConfig(r.data)).catch(() => {});
    }
    if (activeTab === 'settings') {
      setSettingsForm({
        name: garden.name || '',
        description: garden.description || '',
        address: garden.address || '',
        city: garden.city || '',
        state: garden.state || '',
        zip_code: garden.zip_code || '',
        contact_email: garden.contact_email || '',
        plot_fee_annual: garden.plot_fee_annual || 0,
        operating_model: garden.operating_model || 'individual',
        season_start: garden.season_start || '',
        season_end: garden.season_end || '',
        rules: garden.rules || '',
        photo_url: garden.photo_url || '',
        max_checkouts_per_member: garden.max_checkouts_per_member ?? 3,
      });
    }
  }, [activeTab, garden, id, photoFilter]);

  if (loading) return <div className="text-center py-5"><div className="spinner-border" style={{ color: '#5a3921' }}></div></div>;
  if (!garden) return <div className="text-center py-5"><p>Garden not found.</p><Link to="/gardens">Back to Gardens</Link></div>;
  if (!user || user.id !== garden.organizer_id) {
    return (
      <div className="text-center py-5">
        <i className="bi bi-shield-lock" style={{ fontSize: '3rem', color: '#5a3921' }}></i>
        <h4 className="mt-3" style={{ color: '#5a3921' }}>Not authorized.</h4>
        <p className="text-muted">Only the garden organizer can access this admin portal.</p>
        <Link to={`/gardens/${id}`} className="btn" style={{ backgroundColor: '#7c4a1e', color: 'white' }}>Back to Garden</Link>
      </div>
    );
  }

  // ==================== HANDLERS ====================

  const handleUpdatePlot = (plotId) => {
    gardenAdminAPI.updatePlot(id, plotId, plotForm).then(() => {
      setEditingPlot(null);
      gardenAdminAPI.plots(id).then(r => setPlots(r.data.plots || r.data || []));
    }).catch(err => alert(err.response?.data?.error || 'Error updating plot'));
  };

  const handleToggleMaintenance = (plotId) => {
    gardenAdminAPI.toggleMaintenance(id, plotId).then(() => {
      gardenAdminAPI.plots(id).then(r => setPlots(r.data.plots || r.data || []));
    }).catch(err => alert(err.response?.data?.error || 'Error'));
  };

  const handleReleasePlot = (plotId) => {
    if (!confirm('Release this plot? The assigned member will lose their plot.')) return;
    gardensAPI.releasePlot(id, plotId).then(() => {
      gardenAdminAPI.plots(id).then(r => setPlots(r.data.plots || r.data || []));
    }).catch(err => alert(err.response?.data?.error || 'Error'));
  };

  const handleAssignPlot = (plotId, userId) => {
    gardensAPI.assignPlot(id, plotId, { user_id: userId }).then(() => {
      gardenAdminAPI.plots(id).then(r => setPlots(r.data.plots || r.data || []));
      gardensAPI.viewWaitlist(id).then(r => setWaitlist(r.data.waitlist || r.data || []));
    }).catch(err => alert(err.response?.data?.error || 'Error'));
  };

  const handleConfirmReservation = (plotId) => {
    gardenAdminAPI.confirmReservation(id, plotId).then(() => {
      gardenAdminAPI.plots(id).then(r => setPlots(r.data.plots || r.data || []));
      gardensAPI.viewWaitlist(id).then(r => setWaitlist(r.data.waitlist || r.data || []));
    }).catch(err => alert(err.response?.data?.error || 'Error confirming reservation'));
  };

  const handleDeclineReservation = (plotId) => {
    if (!confirm('Decline this reservation? The plot will become available again.')) return;
    gardenAdminAPI.declineReservation(id, plotId).then(() => {
      gardenAdminAPI.plots(id).then(r => setPlots(r.data.plots || r.data || []));
    }).catch(err => alert(err.response?.data?.error || 'Error declining reservation'));
  };

  const handleApproveWaitlist = (wlId, plotId) => {
    gardenAdminAPI.approveWaitlist(id, wlId, { plot_id: plotId }).then(() => {
      gardenAdminAPI.plots(id).then(r => setPlots(r.data.plots || r.data || []));
      gardensAPI.viewWaitlist(id).then(r => setWaitlist(r.data.waitlist || r.data || []));
    }).catch(err => alert(err.response?.data?.error || 'Error approving'));
  };

  const handleDeclineWaitlist = (wlId) => {
    if (!confirm('Decline this waitlist entry?')) return;
    gardenAdminAPI.declineWaitlist(id, wlId).then(() => {
      gardensAPI.viewWaitlist(id).then(r => setWaitlist(r.data.waitlist || r.data || []));
    }).catch(err => alert(err.response?.data?.error || 'Error declining'));
  };

  const handleCreateEvent = (e) => {
    e.preventDefault();
    const datetime = `${eventForm.event_date}T${eventForm.event_time}`;
    const data = { ...eventForm, event_date: datetime, max_volunteers: eventForm.max_volunteers ? parseInt(eventForm.max_volunteers) : null, duration_hours: parseFloat(eventForm.duration_hours) };
    delete data.event_time;
    gardensAPI.createEvent(id, data).then(() => {
      setShowEventForm(false);
      setEventForm({ title: '', description: '', event_type: 'workday', event_date: '', event_time: '09:00', duration_hours: 2, max_volunteers: '' });
      gardensAPI.events(id, { show: 'all' }).then(r => setEvents(r.data));
    }).catch(err => alert(err.response?.data?.error || 'Error creating event'));
  };

  const handleUpdateEvent = (eventId) => {
    const datetime = `${eventForm.event_date}T${eventForm.event_time}`;
    const data = { ...eventForm, event_date: datetime, max_volunteers: eventForm.max_volunteers ? parseInt(eventForm.max_volunteers) : null, duration_hours: parseFloat(eventForm.duration_hours) };
    delete data.event_time;
    gardenAdminAPI.updateEvent(id, eventId, data).then(() => {
      setEditingEvent(null);
      setEventForm({ title: '', description: '', event_type: 'workday', event_date: '', event_time: '09:00', duration_hours: 2, max_volunteers: '' });
      gardensAPI.events(id, { show: 'all' }).then(r => setEvents(r.data));
    }).catch(err => alert(err.response?.data?.error || 'Error'));
  };

  const handleDeleteEvent = (eventId) => {
    if (!confirm('Delete this event?')) return;
    gardenAdminAPI.deleteEvent(id, eventId).then(() => {
      gardensAPI.events(id, { show: 'all' }).then(r => setEvents(r.data));
    }).catch(err => alert(err.response?.data?.error || 'Error'));
  };

  const handleViewAttendees = (eventId) => {
    if (attendeesEvent === eventId) { setAttendeesEvent(null); return; }
    setAttendeesEvent(eventId);
    gardenAdminAPI.eventAttendees(id, eventId).then(r => setAttendees(r.data.attendees || r.data || [])).catch(() => setAttendees([]));
  };

  const handleSendMessage = (e) => {
    e.preventDefault();
    gardenAdminAPI.sendMessage(id, msgForm).then(() => {
      setMsgForm({ recipient_id: '', subject: '', body: '' });
      gardenAdminAPI.messages(id).then(r => setMessages(r.data.messages || r.data || []));
    }).catch(err => alert(err.response?.data?.error || 'Error'));
  };

  const handleBroadcast = (e) => {
    e.preventDefault();
    gardenAdminAPI.broadcastMessage(id, broadcastForm).then(() => {
      setShowBroadcast(false);
      setBroadcastForm({ subject: '', body: '' });
      gardenAdminAPI.messages(id).then(r => setMessages(r.data.messages || r.data || []));
    }).catch(err => alert(err.response?.data?.error || 'Error'));
  };

  const handlePostPhoto = (e) => {
    e.preventDefault();
    gardenAdminAPI.postPhoto(id, photoForm).then(() => {
      setShowPhotoForm(false);
      setPhotoForm({ photo_url: '', caption: '', category: 'harvest' });
      gardenAdminAPI.photos(id, photoFilter !== 'all' ? { category: photoFilter } : {}).then(r => setPhotos(r.data.photos || r.data || []));
    }).catch(err => alert(err.response?.data?.error || 'Error'));
  };

  const handleDeletePhoto = (photoId) => {
    if (!confirm('Delete this photo?')) return;
    gardenAdminAPI.deletePhoto(id, photoId).then(() => {
      setPhotos(prev => prev.filter(p => p.id !== photoId));
    }).catch(err => alert(err.response?.data?.error || 'Error'));
  };

  const handleLikePhoto = (photoId) => {
    gardenAdminAPI.likePhoto(id, photoId).then(() => {
      setPhotos(prev => prev.map(p => p.id === photoId ? { ...p, likes_count: (p.user_liked ? p.likes_count - 1 : p.likes_count + 1), user_liked: !p.user_liked } : p));
    }).catch(() => {});
  };

  const handleToggleComments = (photoId) => {
    if (expandedComments === photoId) { setExpandedComments(null); return; }
    setExpandedComments(photoId);
    gardenAdminAPI.photoComments(id, photoId).then(r => setPhotoComments(r.data.comments || r.data || [])).catch(() => setPhotoComments([]));
  };

  const handleAddComment = (photoId) => {
    if (!commentText.trim()) return;
    gardenAdminAPI.addPhotoComment(id, photoId, { content: commentText }).then(() => {
      setCommentText('');
      gardenAdminAPI.photoComments(id, photoId).then(r => setPhotoComments(r.data.comments || r.data || []));
      setPhotos(prev => prev.map(p => p.id === photoId ? { ...p, comments_count: (p.comments_count || 0) + 1 } : p));
    }).catch(err => alert(err.response?.data?.error || 'Error'));
  };

  const handleCreateAnnouncement = (e) => {
    e.preventDefault();
    gardenAdminAPI.createAnnouncement(id, annForm).then(() => {
      setShowAnnForm(false);
      setAnnForm({ title: '', body: '', priority: 'normal', pinned: false });
      gardenAdminAPI.announcements(id).then(r => setAnnouncements(r.data.announcements || r.data || []));
    }).catch(err => alert(err.response?.data?.error || 'Error'));
  };

  const handleUpdateAnnouncement = (annId) => {
    gardenAdminAPI.updateAnnouncement(id, annId, annForm).then(() => {
      setEditingAnn(null);
      setAnnForm({ title: '', body: '', priority: 'normal', pinned: false });
      gardenAdminAPI.announcements(id).then(r => setAnnouncements(r.data.announcements || r.data || []));
    }).catch(err => alert(err.response?.data?.error || 'Error'));
  };

  const handleDeleteAnnouncement = (annId) => {
    if (!confirm('Delete this announcement?')) return;
    gardenAdminAPI.deleteAnnouncement(id, annId).then(() => {
      setAnnouncements(prev => prev.filter(a => a.id !== annId));
    }).catch(err => alert(err.response?.data?.error || 'Error'));
  };

  const handleAddResource = (e) => {
    e.preventDefault();
    gardensAPI.addResource(id, { ...resForm, quantity: parseInt(resForm.quantity) }).then(() => {
      setShowResForm(false);
      setResForm({ name: '', resource_type: 'tool', description: '', quantity: 1, condition: 'good' });
      gardensAPI.resources(id).then(r => setResources(r.data));
    }).catch(err => alert(err.response?.data?.error || 'Error'));
  };

  const handleReturnResource = (resId) => {
    gardensAPI.returnResource(id, resId).then(() => {
      gardensAPI.resources(id).then(r => setResources(r.data));
    }).catch(err => alert(err.response?.data?.error || 'Error'));
  };

  const handleUpdateCondition = (resId, condition) => {
    gardenAdminAPI.updateResourceCondition(id, resId, { condition }).then(() => {
      gardensAPI.resources(id).then(r => setResources(r.data));
    }).catch(err => alert(err.response?.data?.error || 'Error'));
  };

  const handleSaveSettings = (e) => {
    e.preventDefault();
    gardenAdminAPI.updateSettings(id, settingsForm).then(() => {
      setSettingsSaved(true);
      setTimeout(() => setSettingsSaved(false), 3000);
      gardensAPI.detail(id).then(res => setGarden(res.data));
    }).catch(err => alert(err.response?.data?.error || 'Error saving settings'));
  };

  // ==================== RENDER HELPERS ====================

  const btnStyle = { backgroundColor: '#7c4a1e', color: 'white', border: 'none' };
  const btnOutlineStyle = { border: '1px solid #7c4a1e', color: '#7c4a1e', backgroundColor: 'transparent' };
  const headingStyle = { color: '#5a3921' };

  const renderDashboard = () => (
    <div>
      <h4 className="fw-bold mb-4" style={headingStyle}><i className="bi bi-speedometer2 me-2"></i>Dashboard Overview</h4>
      {/* Stat Cards */}
      <div className="row g-3 mb-4">
        {[
          { label: 'Total Plots', value: stats?.plots?.total ?? '--', icon: 'bi-grid-3x3-gap' },
          { label: 'Occupied Plots', value: stats?.plots?.assigned ?? '--', icon: 'bi-grid-fill' },
          { label: 'Available Plots', value: stats?.plots?.available ?? '--', icon: 'bi-plus-square-dotted' },
          { label: 'Waitlist Size', value: stats?.waitlist_count ?? '--', icon: 'bi-people-fill' },
          { label: 'Upcoming Events', value: stats?.upcoming_events?.length ?? '--', icon: 'bi-calendar-check' },
          { label: 'Total Harvest (lbs)', value: stats?.total_harvest_lbs != null ? Math.round(stats.total_harvest_lbs) : '--', icon: 'bi-basket2-fill' },
        ].map((s, i) => (
          <div key={i} className="col-6 col-md-4 col-lg-2">
            <div className="card h-100" style={{ border: 'none', borderLeft: '4px solid #c9a96e', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
              <div className="card-body text-center py-3">
                <i className={`bi ${s.icon}`} style={{ fontSize: '1.4rem', color: '#7c4a1e' }}></i>
                <div style={{ fontSize: '1.6rem', fontWeight: 'bold', color: '#5a3921' }}>{s.value}</div>
                <div style={{ fontSize: '0.75rem', color: '#6b7280' }}>{s.label}</div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Quick Actions */}
      <div className="card mb-4" style={{ border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
        <div className="card-body">
          <h6 className="fw-bold mb-3" style={headingStyle}>Quick Actions</h6>
          <div className="d-flex flex-wrap gap-2">
            <button className="btn" style={btnStyle} onClick={() => { setActiveTab('events'); setShowEventForm(true); }}>
              <i className="bi bi-calendar-plus me-1"></i>Create Event
            </button>
            <button className="btn" style={btnStyle} onClick={() => { setActiveTab('announcements'); setShowAnnForm(true); }}>
              <i className="bi bi-megaphone me-1"></i>Post Announcement
            </button>
            <button className="btn" style={btnStyle} onClick={() => setActiveTab('messages')}>
              <i className="bi bi-envelope-plus me-1"></i>Send Message
            </button>
            <button className="btn" style={btnOutlineStyle} onClick={() => setActiveTab('photos')}>
              <i className="bi bi-camera me-1"></i>View Photos
            </button>
            <button className="btn" style={btnOutlineStyle} onClick={() => setActiveTab('plots')}>
              <i className="bi bi-grid-3x3-gap me-1"></i>Manage Plots
            </button>
          </div>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="card" style={{ border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
        <div className="card-body">
          <h6 className="fw-bold mb-3" style={headingStyle}><i className="bi bi-clock-history me-2"></i>Recent Activity</h6>
          {activity.length === 0 ? (
            <p className="text-muted">No recent activity.</p>
          ) : (
            <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
              {activity.slice(0, 10).map((a, i) => (
                <div key={i} className="d-flex align-items-start gap-3 py-2" style={{ borderBottom: '1px solid #f0ece0' }}>
                  <div style={{ width: '36px', height: '36px', borderRadius: '50%', backgroundColor: '#f5eed9', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                    <i className={`bi ${a.icon || 'bi-activity'}`} style={{ color: '#7c4a1e', fontSize: '0.9rem' }}></i>
                  </div>
                  <div style={{ flex: 1 }}>
                    <div className="small">{a.description || a.message}</div>
                    <div className="text-muted" style={{ fontSize: '0.75rem' }}>
                      {a.user_name && <span className="fw-semibold">{a.user_name} &middot; </span>}
                      {(a.created_at || a.date) && new Date(a.created_at || a.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );

  const renderPlots = () => (
    <div>
      <h4 className="fw-bold mb-4" style={headingStyle}><i className="bi bi-grid-3x3-gap me-2"></i>Plot Management</h4>
      <div className="table-responsive mb-4">
        <table className="table table-hover align-middle">
          <thead style={{ backgroundColor: '#f5eed9' }}>
            <tr>
              <th>Plot #</th>
              <th>Size</th>
              <th>Status</th>
              <th>Assigned To</th>
              <th>Assigned Date</th>
              <th>Renewal Date</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {plots.map(plot => (
              <Fragment key={plot.id}>
                <tr>
                  <td><strong>#{plot.plot_number}</strong></td>
                  <td>{plot.size || '--'}</td>
                  <td>
                    <span className="badge" style={{ backgroundColor: PLOT_STATUS_COLORS[plot.status] || '#6b7280' }}>
                      {plot.status}
                    </span>
                    {plot.status === 'reserved' && <span className="badge bg-warning text-dark ms-1">Pending</span>}
                  </td>
                  <td>
                    {plot.assigned_to_name || plot.reserved_by_name || <span className="text-muted">--</span>}
                    {plot.reserved_by_name && <div className="text-muted" style={{ fontSize: '0.75rem' }}>Reserved {plot.reserved_at ? new Date(plot.reserved_at).toLocaleDateString() : ''}</div>}
                  </td>
                  <td>{plot.assigned_date ? new Date(plot.assigned_date).toLocaleDateString() : '--'}</td>
                  <td>{plot.renewal_date ? new Date(plot.renewal_date).toLocaleDateString() : '--'}</td>
                  <td>
                    <div className="d-flex gap-1 flex-wrap">
                      {plot.status === 'reserved' && (
                        <>
                          <button className="btn btn-sm btn-success" title="Confirm Reservation" onClick={() => handleConfirmReservation(plot.id)}>
                            <i className="bi bi-check-lg"></i> Confirm
                          </button>
                          <button className="btn btn-sm btn-outline-danger" title="Decline Reservation" onClick={() => handleDeclineReservation(plot.id)}>
                            <i className="bi bi-x-lg"></i> Decline
                          </button>
                        </>
                      )}
                      <button className="btn btn-sm" style={btnOutlineStyle} title="Edit" onClick={() => {
                        if (editingPlot === plot.id) { setEditingPlot(null); return; }
                        setEditingPlot(plot.id);
                        setPlotForm({ size: plot.size || '', location_notes: plot.location_notes || '', renewal_date: plot.renewal_date || '' });
                      }}>
                        <i className="bi bi-pencil"></i>
                      </button>
                      <button className="btn btn-sm btn-outline-secondary" title="Toggle Maintenance" onClick={() => handleToggleMaintenance(plot.id)}>
                        <i className="bi bi-wrench"></i>
                      </button>
                      {plot.assigned_to_id && (
                        <button className="btn btn-sm btn-outline-danger" title="Release Plot" onClick={() => handleReleasePlot(plot.id)}>
                          <i className="bi bi-x-circle"></i>
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
                {editingPlot === plot.id && (
                  <tr>
                    <td colSpan="7" style={{ backgroundColor: '#faf6ed' }}>
                      <div className="row g-2 p-2">
                        <div className="col-md-3">
                          <label className="form-label small fw-bold">Size</label>
                          <input type="text" className="form-control form-control-sm" value={plotForm.size} onChange={e => setPlotForm({ ...plotForm, size: e.target.value })} />
                        </div>
                        <div className="col-md-4">
                          <label className="form-label small fw-bold">Location Notes</label>
                          <input type="text" className="form-control form-control-sm" value={plotForm.location_notes} onChange={e => setPlotForm({ ...plotForm, location_notes: e.target.value })} />
                        </div>
                        <div className="col-md-3">
                          <label className="form-label small fw-bold">Renewal Date</label>
                          <input type="date" className="form-control form-control-sm" value={plotForm.renewal_date} onChange={e => setPlotForm({ ...plotForm, renewal_date: e.target.value })} />
                        </div>
                        <div className="col-md-2 d-flex align-items-end gap-1">
                          <button className="btn btn-sm" style={btnStyle} onClick={() => handleUpdatePlot(plot.id)}>Save</button>
                          <button className="btn btn-sm btn-outline-secondary" onClick={() => setEditingPlot(null)}>Cancel</button>
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
            {plots.length === 0 && <tr><td colSpan="7" className="text-center text-muted py-4">No plots configured.</td></tr>}
          </tbody>
        </table>
      </div>

      {/* Waitlist */}
      <h5 className="fw-bold mb-3" style={headingStyle}><i className="bi bi-people me-2"></i>Waitlist</h5>
      <div className="table-responsive">
        <table className="table table-hover align-middle">
          <thead style={{ backgroundColor: '#f5eed9' }}>
            <tr>
              <th>#</th>
              <th>Name</th>
              <th>Requested Date</th>
              <th>Size Preference</th>
              <th>Notes</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {waitlist.filter(w => w.status === 'waiting').map((w, idx) => (
              <tr key={w.id}>
                <td><span className="badge bg-secondary">{idx + 1}</span></td>
                <td><strong>{w.user_name || w.name}</strong></td>
                <td>{w.requested_at ? new Date(w.requested_at).toLocaleDateString() : (w.created_at ? new Date(w.created_at).toLocaleDateString() : '--')}</td>
                <td>{w.plot_size_pref || '--'}</td>
                <td className="small">{w.notes || '--'}</td>
                <td><span className="badge bg-warning text-dark">{w.status}</span></td>
                <td>
                  <div className="d-flex gap-1 align-items-center">
                    {plots.filter(p => p.status === 'available').length > 0 ? (
                      <select className="form-select form-select-sm" style={{ width: '140px' }} defaultValue="" onChange={(e) => {
                        if (e.target.value) handleApproveWaitlist(w.id, parseInt(e.target.value));
                      }}>
                        <option value="">Approve → Plot...</option>
                        {plots.filter(p => p.status === 'available').map(p => (
                          <option key={p.id} value={p.id}>Plot #{p.plot_number}</option>
                        ))}
                      </select>
                    ) : (
                      <span className="text-muted small">No plots</span>
                    )}
                    <button className="btn btn-sm btn-outline-danger" title="Decline" onClick={() => handleDeclineWaitlist(w.id)}>
                      <i className="bi bi-x-lg"></i>
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {waitlist.filter(w => w.status === 'waiting').length === 0 && (
              <tr><td colSpan="7" className="text-center text-muted py-4">No one on the waitlist.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Processed Waitlist Entries */}
      {waitlist.filter(w => w.status !== 'waiting').length > 0 && (
        <>
          <h6 className="fw-bold mt-4 mb-2 text-muted">Processed Entries</h6>
          <div className="table-responsive">
            <table className="table table-sm text-muted">
              <thead><tr><th>Name</th><th>Status</th><th>Date</th></tr></thead>
              <tbody>
                {waitlist.filter(w => w.status !== 'waiting').map(w => (
                  <tr key={w.id}>
                    <td>{w.user_name || w.name}</td>
                    <td>
                      <span className={`badge ${w.status === 'accepted' ? 'bg-success' : w.status === 'offered' ? 'bg-info' : 'bg-danger'}`}>
                        {w.status}
                      </span>
                    </td>
                    <td>{w.requested_at ? new Date(w.requested_at).toLocaleDateString() : '--'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );

  const renderEventForm = (isEdit = false) => (
    <div className="card mb-4" style={{ border: '2px solid #c9a96e' }}>
      <div className="card-body">
        <h6 className="fw-bold mb-3" style={headingStyle}>{isEdit ? 'Edit Event' : 'Create New Event'}</h6>
        <form onSubmit={isEdit ? (e) => { e.preventDefault(); handleUpdateEvent(editingEvent); } : handleCreateEvent}>
          <div className="row g-3">
            <div className="col-md-6">
              <label className="form-label">Title</label>
              <input type="text" className="form-control" required value={eventForm.title} onChange={e => setEventForm({ ...eventForm, title: e.target.value })} />
            </div>
            <div className="col-md-3">
              <label className="form-label">Type</label>
              <select className="form-select" value={eventForm.event_type} onChange={e => setEventForm({ ...eventForm, event_type: e.target.value })}>
                <option value="workday">Workday</option>
                <option value="workshop">Workshop</option>
                <option value="social">Social</option>
                <option value="meeting">Meeting</option>
                <option value="harvest_day">Harvest Day</option>
              </select>
            </div>
            <div className="col-md-3">
              <label className="form-label">Max Volunteers</label>
              <input type="number" className="form-control" min="1" value={eventForm.max_volunteers} onChange={e => setEventForm({ ...eventForm, max_volunteers: e.target.value })} />
            </div>
            <div className="col-md-3">
              <label className="form-label">Date</label>
              <input type="date" className="form-control" required value={eventForm.event_date} onChange={e => setEventForm({ ...eventForm, event_date: e.target.value })} />
            </div>
            <div className="col-md-3">
              <label className="form-label">Time</label>
              <input type="time" className="form-control" required value={eventForm.event_time} onChange={e => setEventForm({ ...eventForm, event_time: e.target.value })} />
            </div>
            <div className="col-md-3">
              <label className="form-label">Duration (hours)</label>
              <input type="number" className="form-control" step="0.5" min="0.5" value={eventForm.duration_hours} onChange={e => setEventForm({ ...eventForm, duration_hours: e.target.value })} />
            </div>
            <div className="col-12">
              <label className="form-label">Description</label>
              <textarea className="form-control" rows="2" value={eventForm.description} onChange={e => setEventForm({ ...eventForm, description: e.target.value })}></textarea>
            </div>
            <div className="col-12 d-flex gap-2">
              <button type="submit" className="btn" style={btnStyle}>{isEdit ? 'Update Event' : 'Create Event'}</button>
              <button type="button" className="btn" style={btnOutlineStyle} onClick={() => { setShowEventForm(false); setEditingEvent(null); setEventForm({ title: '', description: '', event_type: 'workday', event_date: '', event_time: '09:00', duration_hours: 2, max_volunteers: '' }); }}>Cancel</button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );

  const renderEvents = () => (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h4 className="fw-bold mb-0" style={headingStyle}><i className="bi bi-calendar-event me-2"></i>Events</h4>
        <button className="btn" style={btnStyle} onClick={() => { setShowEventForm(!showEventForm); setEditingEvent(null); }}>
          <i className="bi bi-plus-circle me-1"></i>Create Event
        </button>
      </div>

      {(showEventForm && !editingEvent) && renderEventForm(false)}
      {editingEvent && renderEventForm(true)}

      <div className="table-responsive">
        <table className="table table-hover align-middle">
          <thead style={{ backgroundColor: '#f5eed9' }}>
            <tr>
              <th>Title</th>
              <th>Date</th>
              <th>Type</th>
              <th>RSVP</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {events.map(ev => {
              const evDate = new Date(ev.event_date);
              const isPast = evDate < new Date();
              return (
                <Fragment key={ev.id}>
                  <tr style={{ opacity: isPast ? 0.6 : 1 }}>
                    <td>
                      <strong>{ev.title}</strong>
                      {ev.description && <div className="text-muted small">{ev.description.slice(0, 60)}{ev.description.length > 60 ? '...' : ''}</div>}
                    </td>
                    <td className="small">
                      {evDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}<br />
                      <span className="text-muted">{evDate.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })} ({ev.duration_hours}h)</span>
                    </td>
                    <td>
                      <span className="badge" style={{ backgroundColor: { workday: '#40916c', workshop: '#3b82f6', social: '#8b5cf6', meeting: '#6b7280', harvest_day: '#f59e0b' }[ev.event_type] || '#6b7280', textTransform: 'capitalize' }}>
                        {ev.event_type?.replace('_', ' ')}
                      </span>
                    </td>
                    <td>
                      <span className="small">{ev.rsvp_going || 0} going</span>
                      {ev.max_volunteers && <span className="text-muted small"> / {ev.max_volunteers}</span>}
                    </td>
                    <td>
                      <div className="d-flex gap-1">
                        <button className="btn btn-sm" style={btnOutlineStyle} title="Edit" onClick={() => {
                          setEditingEvent(ev.id);
                          setShowEventForm(false);
                          const d = new Date(ev.event_date);
                          setEventForm({
                            title: ev.title,
                            description: ev.description || '',
                            event_type: ev.event_type,
                            event_date: d.toISOString().split('T')[0],
                            event_time: d.toTimeString().slice(0, 5),
                            duration_hours: ev.duration_hours,
                            max_volunteers: ev.max_volunteers || '',
                          });
                        }}>
                          <i className="bi bi-pencil"></i>
                        </button>
                        <button className="btn btn-sm btn-outline-info" title="Attendees" onClick={() => handleViewAttendees(ev.id)}>
                          <i className="bi bi-people"></i>
                        </button>
                        <button className="btn btn-sm btn-outline-danger" title="Delete" onClick={() => handleDeleteEvent(ev.id)}>
                          <i className="bi bi-trash"></i>
                        </button>
                      </div>
                    </td>
                  </tr>
                  {attendeesEvent === ev.id && (
                    <tr>
                      <td colSpan="5" style={{ backgroundColor: '#faf6ed' }}>
                        <div className="p-2">
                          <h6 className="fw-bold small mb-2">Attendees for {ev.title}</h6>
                          {attendees.length === 0 ? (
                            <p className="text-muted small mb-0">No RSVPs yet.</p>
                          ) : (
                            <div className="d-flex flex-wrap gap-2">
                              {attendees.map((att, i) => (
                                <span key={i} className="badge" style={{ backgroundColor: att.status === 'going' ? '#40916c' : '#f59e0b', fontSize: '0.8rem', fontWeight: 500 }}>
                                  {att.display_name || att.username || att.user_name || att.name} ({att.status})
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
            {events.length === 0 && <tr><td colSpan="5" className="text-center text-muted py-4">No events yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );

  const renderMessages = () => (
    <div>
      <h4 className="fw-bold mb-4" style={headingStyle}><i className="bi bi-envelope me-2"></i>Messages</h4>

      {/* Send Message Form */}
      <div className="card mb-4" style={{ border: '2px solid #c9a96e' }}>
        <div className="card-body">
          <div className="d-flex justify-content-between align-items-center mb-3">
            <h6 className="fw-bold mb-0" style={headingStyle}>Send Message</h6>
            <button className="btn btn-sm" style={btnStyle} onClick={() => setShowBroadcast(!showBroadcast)}>
              <i className="bi bi-broadcast me-1"></i>Broadcast to All
            </button>
          </div>
          {!showBroadcast ? (
            <form onSubmit={handleSendMessage}>
              <div className="row g-3">
                <div className="col-md-4">
                  <label className="form-label">Recipient</label>
                  <select className="form-select" required value={msgForm.recipient_id} onChange={e => setMsgForm({ ...msgForm, recipient_id: e.target.value })}>
                    <option value="">Select plot owner...</option>
                    {plotOwners.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
                  </select>
                </div>
                <div className="col-md-8">
                  <label className="form-label">Subject</label>
                  <input type="text" className="form-control" required value={msgForm.subject} onChange={e => setMsgForm({ ...msgForm, subject: e.target.value })} />
                </div>
                <div className="col-12">
                  <label className="form-label">Message</label>
                  <textarea className="form-control" rows="3" required value={msgForm.body} onChange={e => setMsgForm({ ...msgForm, body: e.target.value })}></textarea>
                </div>
                <div className="col-12">
                  <button type="submit" className="btn" style={btnStyle}><i className="bi bi-send me-1"></i>Send</button>
                </div>
              </div>
            </form>
          ) : (
            <form onSubmit={handleBroadcast}>
              <div className="alert" style={{ backgroundColor: '#fef3c7', color: '#92400e', border: 'none' }}>
                <i className="bi bi-broadcast me-1"></i>This message will be sent to all plot owners in the garden.
              </div>
              <div className="row g-3">
                <div className="col-12">
                  <label className="form-label">Subject</label>
                  <input type="text" className="form-control" required value={broadcastForm.subject} onChange={e => setBroadcastForm({ ...broadcastForm, subject: e.target.value })} />
                </div>
                <div className="col-12">
                  <label className="form-label">Message</label>
                  <textarea className="form-control" rows="3" required value={broadcastForm.body} onChange={e => setBroadcastForm({ ...broadcastForm, body: e.target.value })}></textarea>
                </div>
                <div className="col-12 d-flex gap-2">
                  <button type="submit" className="btn" style={btnStyle}><i className="bi bi-broadcast me-1"></i>Send Broadcast</button>
                  <button type="button" className="btn" style={btnOutlineStyle} onClick={() => setShowBroadcast(false)}>Cancel</button>
                </div>
              </div>
            </form>
          )}
        </div>
      </div>

      {/* Message History */}
      <h6 className="fw-bold mb-3" style={headingStyle}>Message History</h6>
      <div className="list-group">
        {messages.map(msg => (
          <div key={msg.id} className="list-group-item" style={{ borderLeft: msg.is_read ? '3px solid #c9a96e' : '3px solid #7c4a1e' }}>
            <div className="d-flex justify-content-between align-items-start">
              <div>
                <h6 className="mb-1 fw-bold small">{msg.subject}</h6>
                <div className="text-muted small">
                  {msg.sender_name && <span><i className="bi bi-person me-1"></i>{msg.sender_name} &rarr; </span>}
                  {msg.recipient_name && <span>{msg.recipient_name}</span>}
                  {msg.is_broadcast && <span className="badge bg-info ms-1">Broadcast</span>}
                </div>
              </div>
              <div className="text-end">
                <div className="text-muted" style={{ fontSize: '0.75rem' }}>
                  {msg.created_at && new Date(msg.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}
                </div>
                {!msg.is_read && <span className="badge" style={{ backgroundColor: '#7c4a1e' }}>Unread</span>}
              </div>
            </div>
            {msg.body && <p className="small mt-2 mb-0 text-muted">{msg.body.slice(0, 150)}{msg.body.length > 150 ? '...' : ''}</p>}
          </div>
        ))}
        {messages.length === 0 && <p className="text-muted text-center py-4">No messages yet.</p>}
      </div>
    </div>
  );

  const renderPhotos = () => (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-3">
        <h4 className="fw-bold mb-0" style={headingStyle}><i className="bi bi-camera me-2"></i>Garden Photos</h4>
        <button className="btn" style={btnStyle} onClick={() => setShowPhotoForm(!showPhotoForm)}>
          <i className="bi bi-plus-circle me-1"></i>Post Photo
        </button>
      </div>

      {/* Category Filters */}
      <div className="d-flex flex-wrap gap-2 mb-4">
        {PHOTO_CATEGORIES.map(cat => (
          <button key={cat} className="btn btn-sm" style={photoFilter === cat ? { ...btnStyle, borderRadius: '20px' } : { ...btnOutlineStyle, borderRadius: '20px' }} onClick={() => setPhotoFilter(cat)}>
            {cat.charAt(0).toUpperCase() + cat.slice(1)}
          </button>
        ))}
      </div>

      {/* Post Photo Form */}
      {showPhotoForm && (
        <div className="card mb-4" style={{ border: '2px solid #c9a96e' }}>
          <div className="card-body">
            <h6 className="fw-bold mb-3" style={headingStyle}>Post a Photo</h6>
            <form onSubmit={handlePostPhoto}>
              <div className="row g-3">
                <div className="col-md-6">
                  <label className="form-label">Photo URL</label>
                  <input type="url" className="form-control" required placeholder="https://..." value={photoForm.photo_url} onChange={e => setPhotoForm({ ...photoForm, photo_url: e.target.value })} />
                </div>
                <div className="col-md-3">
                  <label className="form-label">Category</label>
                  <select className="form-select" value={photoForm.category} onChange={e => setPhotoForm({ ...photoForm, category: e.target.value })}>
                    <option value="harvest">Harvest</option>
                    <option value="plot">Plot</option>
                    <option value="event">Event</option>
                    <option value="wildlife">Wildlife</option>
                    <option value="bloom">Bloom</option>
                  </select>
                </div>
                <div className="col-12">
                  <label className="form-label">Caption</label>
                  <input type="text" className="form-control" value={photoForm.caption} onChange={e => setPhotoForm({ ...photoForm, caption: e.target.value })} />
                </div>
                <div className="col-12 d-flex gap-2">
                  <button type="submit" className="btn" style={btnStyle}>Post Photo</button>
                  <button type="button" className="btn" style={btnOutlineStyle} onClick={() => setShowPhotoForm(false)}>Cancel</button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Photo Grid */}
      <div className="row g-3">
        {photos.map(photo => (
          <div key={photo.id} className="col-md-4">
            <div className="card h-100" style={{ border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.08)', borderRadius: '12px', overflow: 'hidden' }}>
              {/* Photo Thumbnail / Placeholder */}
              {photo.photo_url ? (
                <div style={{ height: '200px', backgroundImage: `url(${photo.photo_url})`, backgroundSize: 'cover', backgroundPosition: 'center', position: 'relative' }}>
                  <button className="btn btn-sm btn-danger" style={{ position: 'absolute', top: '8px', right: '8px', opacity: 0.9 }} onClick={() => handleDeletePhoto(photo.id)} title="Delete">
                    <i className="bi bi-trash"></i>
                  </button>
                </div>
              ) : (
                <div style={{ height: '200px', backgroundColor: '#f5eed9', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', position: 'relative' }}>
                  <i className="bi bi-camera" style={{ fontSize: '3rem', color: '#c9a96e' }}></i>
                  <span className="text-muted small mt-1">{photo.category || 'Photo'}</span>
                  <button className="btn btn-sm btn-danger" style={{ position: 'absolute', top: '8px', right: '8px', opacity: 0.9 }} onClick={() => handleDeletePhoto(photo.id)} title="Delete">
                    <i className="bi bi-trash"></i>
                  </button>
                </div>
              )}
              <div className="card-body">
                <p className="small mb-1">{photo.caption || <span className="text-muted">No caption</span>}</p>
                <div className="d-flex justify-content-between align-items-center text-muted" style={{ fontSize: '0.75rem' }}>
                  <span><i className="bi bi-person me-1"></i>{photo.user_name || 'Member'}</span>
                  <span>{photo.created_at && new Date(photo.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</span>
                </div>
                <div className="d-flex gap-3 mt-2">
                  <button className="btn btn-sm p-0" style={{ border: 'none', background: 'none', color: photo.user_liked ? '#dc3545' : '#6b7280' }} onClick={() => handleLikePhoto(photo.id)}>
                    <i className={`bi ${photo.user_liked ? 'bi-heart-fill' : 'bi-heart'}`}></i>
                    <span className="ms-1 small">{photo.likes_count || 0}</span>
                  </button>
                  <button className="btn btn-sm p-0" style={{ border: 'none', background: 'none', color: '#6b7280' }} onClick={() => handleToggleComments(photo.id)}>
                    <i className="bi bi-chat"></i>
                    <span className="ms-1 small">{photo.comments_count || 0}</span>
                  </button>
                  <span className="badge ms-auto" style={{ backgroundColor: '#f5eed9', color: '#7c4a1e', fontSize: '0.7rem' }}>
                    {photo.category}
                  </span>
                </div>

                {/* Comments Section */}
                {expandedComments === photo.id && (
                  <div className="mt-3 pt-2" style={{ borderTop: '1px solid #f0ece0' }}>
                    {photoComments.length === 0 && <p className="text-muted small">No comments yet.</p>}
                    {photoComments.map((c, i) => (
                      <div key={i} className="mb-2">
                        <span className="fw-bold small">{c.user_name}</span>
                        <span className="text-muted small ms-2">{c.created_at && new Date(c.created_at).toLocaleDateString()}</span>
                        <p className="small mb-0">{c.content || c.body}</p>
                      </div>
                    ))}
                    <div className="input-group input-group-sm mt-2">
                      <input type="text" className="form-control" placeholder="Add comment..." value={commentText} onChange={e => setCommentText(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); handleAddComment(photo.id); } }} />
                      <button className="btn" style={btnStyle} onClick={() => handleAddComment(photo.id)}>
                        <i className="bi bi-send"></i>
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
        {photos.length === 0 && (
          <div className="col-12 text-center py-5">
            <i className="bi bi-camera" style={{ fontSize: '3rem', color: '#c9a96e' }}></i>
            <p className="text-muted mt-2">No photos posted yet. Be the first!</p>
          </div>
        )}
      </div>
    </div>
  );

  const renderAnnouncements = () => {
    const pinned = announcements.filter(a => a.pinned);
    const unpinned = announcements.filter(a => !a.pinned);
    const sorted = [...pinned, ...unpinned];

    return (
      <div>
        <div className="d-flex justify-content-between align-items-center mb-4">
          <h4 className="fw-bold mb-0" style={headingStyle}><i className="bi bi-megaphone me-2"></i>Announcements</h4>
          <button className="btn" style={btnStyle} onClick={() => { setShowAnnForm(!showAnnForm); setEditingAnn(null); setAnnForm({ title: '', body: '', priority: 'normal', pinned: false }); }}>
            <i className="bi bi-plus-circle me-1"></i>New Announcement
          </button>
        </div>

        {/* Create / Edit Form */}
        {(showAnnForm || editingAnn) && (
          <div className="card mb-4" style={{ border: '2px solid #c9a96e' }}>
            <div className="card-body">
              <h6 className="fw-bold mb-3" style={headingStyle}>{editingAnn ? 'Edit Announcement' : 'Create Announcement'}</h6>
              <form onSubmit={editingAnn ? (e) => { e.preventDefault(); handleUpdateAnnouncement(editingAnn); } : handleCreateAnnouncement}>
                <div className="row g-3">
                  <div className="col-md-6">
                    <label className="form-label">Title</label>
                    <input type="text" className="form-control" required value={annForm.title} onChange={e => setAnnForm({ ...annForm, title: e.target.value })} />
                  </div>
                  <div className="col-md-3">
                    <label className="form-label">Priority</label>
                    <select className="form-select" value={annForm.priority} onChange={e => setAnnForm({ ...annForm, priority: e.target.value })}>
                      <option value="normal">Normal</option>
                      <option value="important">Important</option>
                      <option value="urgent">Urgent</option>
                    </select>
                  </div>
                  <div className="col-md-3 d-flex align-items-end">
                    <div className="form-check">
                      <input className="form-check-input" type="checkbox" id="pinned" checked={annForm.pinned} onChange={e => setAnnForm({ ...annForm, pinned: e.target.checked })} />
                      <label className="form-check-label" htmlFor="pinned"><i className="bi bi-pin me-1"></i>Pinned</label>
                    </div>
                  </div>
                  <div className="col-12">
                    <label className="form-label">Body</label>
                    <textarea className="form-control" rows="4" required value={annForm.body} onChange={e => setAnnForm({ ...annForm, body: e.target.value })}></textarea>
                  </div>
                  <div className="col-12 d-flex gap-2">
                    <button type="submit" className="btn" style={btnStyle}>{editingAnn ? 'Update' : 'Post Announcement'}</button>
                    <button type="button" className="btn" style={btnOutlineStyle} onClick={() => { setShowAnnForm(false); setEditingAnn(null); }}>Cancel</button>
                  </div>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Announcements List */}
        <div className="list-group">
          {sorted.map(ann => (
            <div key={ann.id} className="list-group-item" style={{ borderLeft: `4px solid ${PRIORITY_STYLES[ann.priority]?.color || '#0d6efd'}` }}>
              <div className="d-flex justify-content-between align-items-start">
                <div style={{ flex: 1 }}>
                  <div className="d-flex align-items-center gap-2 mb-1">
                    {ann.pinned && <i className="bi bi-pin-fill" style={{ color: '#7c4a1e' }} title="Pinned"></i>}
                    <h6 className="mb-0 fw-bold">{ann.title}</h6>
                    <span className={`badge ${PRIORITY_STYLES[ann.priority]?.bg || 'bg-primary'}`} style={{ fontSize: '0.7rem' }}>
                      {ann.priority}
                    </span>
                  </div>
                  <p className="small mb-1" style={{ whiteSpace: 'pre-wrap' }}>{ann.body}</p>
                  <div className="text-muted" style={{ fontSize: '0.75rem' }}>
                    {ann.author_name && <span>{ann.author_name} &middot; </span>}
                    {ann.created_at && new Date(ann.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                  </div>
                </div>
                <div className="d-flex gap-1 ms-3">
                  <button className="btn btn-sm" style={btnOutlineStyle} title="Edit" onClick={() => {
                    setEditingAnn(ann.id);
                    setShowAnnForm(false);
                    setAnnForm({ title: ann.title, body: ann.body, priority: ann.priority, pinned: ann.pinned || false });
                  }}>
                    <i className="bi bi-pencil"></i>
                  </button>
                  <button className="btn btn-sm btn-outline-danger" title="Delete" onClick={() => handleDeleteAnnouncement(ann.id)}>
                    <i className="bi bi-trash"></i>
                  </button>
                </div>
              </div>
            </div>
          ))}
          {announcements.length === 0 && (
            <div className="text-center py-5">
              <i className="bi bi-megaphone" style={{ fontSize: '2.5rem', color: '#c9a96e' }}></i>
              <p className="text-muted mt-2">No announcements yet.</p>
            </div>
          )}
        </div>
      </div>
    );
  };

  const renderResources = () => {
    const overdueItems = resources.filter(r => r.is_overdue);
    return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h4 className="fw-bold mb-0" style={headingStyle}><i className="bi bi-tools me-2"></i>Shared Resources</h4>
        <button className="btn" style={btnStyle} onClick={() => setShowResForm(!showResForm)}>
          <i className="bi bi-plus-circle me-1"></i>Add Resource
        </button>
      </div>

      {/* Overdue Alert */}
      {overdueItems.length > 0 && (
        <div className="alert alert-danger d-flex align-items-center mb-4">
          <i className="bi bi-exclamation-triangle-fill me-2 fs-5"></i>
          <div>
            <strong>{overdueItems.length} overdue item{overdueItems.length > 1 ? 's' : ''}!</strong>
            <div className="small mt-1">
              {overdueItems.map(r => (
                <span key={r.id} className="me-3">
                  <strong>{r.name}</strong> — checked out by {r.checked_out_to_name} (due {new Date(r.due_date).toLocaleDateString()})
                </span>
              ))}
            </div>
          </div>
        </div>
      )}

      {showResForm && (
        <div className="card mb-4" style={{ border: '2px solid #c9a96e' }}>
          <div className="card-body">
            <h6 className="fw-bold mb-3" style={headingStyle}>Add New Resource</h6>
            <form onSubmit={handleAddResource}>
              <div className="row g-3">
                <div className="col-md-4">
                  <label className="form-label">Name</label>
                  <input type="text" className="form-control" required value={resForm.name} onChange={e => setResForm({ ...resForm, name: e.target.value })} />
                </div>
                <div className="col-md-3">
                  <label className="form-label">Type</label>
                  <select className="form-select" value={resForm.resource_type} onChange={e => setResForm({ ...resForm, resource_type: e.target.value })}>
                    <option value="tool">Tool</option>
                    <option value="supply">Supply</option>
                    <option value="infrastructure">Infrastructure</option>
                  </select>
                </div>
                <div className="col-md-2">
                  <label className="form-label">Qty</label>
                  <input type="number" className="form-control" min="1" value={resForm.quantity} onChange={e => setResForm({ ...resForm, quantity: e.target.value })} />
                </div>
                <div className="col-md-3">
                  <label className="form-label">Condition</label>
                  <select className="form-select" value={resForm.condition} onChange={e => setResForm({ ...resForm, condition: e.target.value })}>
                    <option value="new">New</option>
                    <option value="good">Good</option>
                    <option value="fair">Fair</option>
                    <option value="needs_repair">Needs Repair</option>
                  </select>
                </div>
                <div className="col-12">
                  <label className="form-label">Description</label>
                  <input type="text" className="form-control" value={resForm.description} onChange={e => setResForm({ ...resForm, description: e.target.value })} />
                </div>
                <div className="col-12 d-flex gap-2">
                  <button type="submit" className="btn" style={btnStyle}>Add Resource</button>
                  <button type="button" className="btn" style={btnOutlineStyle} onClick={() => setShowResForm(false)}>Cancel</button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      <div className="table-responsive">
        <table className="table table-hover align-middle">
          <thead style={{ backgroundColor: '#f5eed9' }}>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Qty</th>
              <th>Condition</th>
              <th>Checked Out To</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {resources.map(res => (
              <tr key={res.id} style={res.is_overdue ? { backgroundColor: '#fff5f5' } : {}}>
                <td>
                  <strong>{res.name}</strong>
                  {res.description && <div className="text-muted small">{res.description}</div>}
                </td>
                <td style={{ textTransform: 'capitalize' }}>{res.resource_type}</td>
                <td>{res.quantity}</td>
                <td>
                  <select className="form-select form-select-sm" style={{ width: '120px' }}
                    value={res.condition || 'good'}
                    onChange={e => handleUpdateCondition(res.id, e.target.value)}>
                    <option value="new">New</option>
                    <option value="good">Good</option>
                    <option value="fair">Fair</option>
                    <option value="needs_repair">Needs Repair</option>
                  </select>
                </td>
                <td>
                  {res.checked_out_to_name ? (
                    <div>
                      <span className={res.is_overdue ? 'text-danger fw-bold' : 'text-warning'}>
                        <i className={`bi ${res.is_overdue ? 'bi-exclamation-triangle' : 'bi-arrow-up-right'} me-1`}></i>
                        {res.checked_out_to_name}
                      </span>
                      {res.due_date && (
                        <div className={`small ${res.is_overdue ? 'text-danger' : 'text-muted'}`}>
                          Due: {new Date(res.due_date).toLocaleDateString()}
                          {res.is_overdue && ' (OVERDUE)'}
                        </div>
                      )}
                    </div>
                  ) : (
                    <span className="text-success"><i className="bi bi-check-circle me-1"></i>Available</span>
                  )}
                </td>
                <td>
                  <div className="d-flex gap-1">
                    {res.checked_out_to_id && (
                      <button className="btn btn-sm" style={btnOutlineStyle} onClick={() => handleReturnResource(res.id)}>
                        <i className="bi bi-arrow-return-left me-1"></i>Return
                      </button>
                    )}
                    <a href={gardensAPI.resourceQR(id, res.id)} target="_blank" rel="noopener noreferrer"
                      className="btn btn-sm btn-outline-secondary" title="Download QR Code">
                      <i className="bi bi-qr-code"></i>
                    </a>
                  </div>
                </td>
              </tr>
            ))}
            {resources.length === 0 && <tr><td colSpan="6" className="text-center text-muted py-4">No resources yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
  };

  const renderSettings = () => (
    <div>
      <h4 className="fw-bold mb-4" style={headingStyle}><i className="bi bi-gear me-2"></i>Garden Settings</h4>

      {settingsSaved && (
        <div className="alert" style={{ backgroundColor: '#d8f3dc', color: '#2d6a4f', border: 'none' }}>
          <i className="bi bi-check-circle me-2"></i>Settings saved successfully!
        </div>
      )}

      <form onSubmit={handleSaveSettings}>
        <div className="card mb-4" style={{ border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
          <div className="card-body">
            <h6 className="fw-bold mb-3" style={headingStyle}>General Information</h6>
            <div className="row g-3">
              <div className="col-md-6">
                <label className="form-label">Garden Name</label>
                <input type="text" className="form-control" required value={settingsForm.name || ''} onChange={e => setSettingsForm({ ...settingsForm, name: e.target.value })} />
              </div>
              <div className="col-md-6">
                <label className="form-label">Contact Email</label>
                <input type="email" className="form-control" value={settingsForm.contact_email || ''} onChange={e => setSettingsForm({ ...settingsForm, contact_email: e.target.value })} />
              </div>
              <div className="col-12">
                <label className="form-label">Description</label>
                <textarea className="form-control" rows="3" value={settingsForm.description || ''} onChange={e => setSettingsForm({ ...settingsForm, description: e.target.value })}></textarea>
              </div>
            </div>
          </div>
        </div>

        <div className="card mb-4" style={{ border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
          <div className="card-body">
            <h6 className="fw-bold mb-3" style={headingStyle}>Location</h6>
            <div className="row g-3">
              <div className="col-md-6">
                <label className="form-label">Address</label>
                <input type="text" className="form-control" value={settingsForm.address || ''} onChange={e => setSettingsForm({ ...settingsForm, address: e.target.value })} />
              </div>
              <div className="col-md-3">
                <label className="form-label">City</label>
                <input type="text" className="form-control" value={settingsForm.city || ''} onChange={e => setSettingsForm({ ...settingsForm, city: e.target.value })} />
              </div>
              <div className="col-md-1">
                <label className="form-label">State</label>
                <input type="text" className="form-control" maxLength="2" value={settingsForm.state || ''} onChange={e => setSettingsForm({ ...settingsForm, state: e.target.value })} />
              </div>
              <div className="col-md-2">
                <label className="form-label">Zip</label>
                <input type="text" className="form-control" value={settingsForm.zip_code || ''} onChange={e => setSettingsForm({ ...settingsForm, zip_code: e.target.value })} />
              </div>
            </div>
          </div>
        </div>

        <div className="card mb-4" style={{ border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
          <div className="card-body">
            <h6 className="fw-bold mb-3" style={headingStyle}>Operations</h6>
            <div className="row g-3">
              <div className="col-md-3">
                <label className="form-label">Annual Plot Fee ($)</label>
                <input type="number" className="form-control" step="0.01" min="0" value={settingsForm.plot_fee_annual || ''} onChange={e => setSettingsForm({ ...settingsForm, plot_fee_annual: parseFloat(e.target.value) || 0 })} />
              </div>
              <div className="col-md-3">
                <label className="form-label">Operating Model</label>
                <select className="form-select" value={settingsForm.operating_model || 'individual'} onChange={e => setSettingsForm({ ...settingsForm, operating_model: e.target.value })}>
                  <option value="individual">Individual Plots</option>
                  <option value="collective">Collective</option>
                  <option value="hybrid">Hybrid</option>
                </select>
              </div>
              <div className="col-md-3">
                <label className="form-label">Season Start</label>
                <input type="date" className="form-control" value={settingsForm.season_start || ''} onChange={e => setSettingsForm({ ...settingsForm, season_start: e.target.value })} />
              </div>
              <div className="col-md-3">
                <label className="form-label">Season End</label>
                <input type="date" className="form-control" value={settingsForm.season_end || ''} onChange={e => setSettingsForm({ ...settingsForm, season_end: e.target.value })} />
              </div>
              <div className="col-md-3">
                <label className="form-label">Max Tool Checkouts</label>
                <input type="number" className="form-control" min="1" max="10"
                  value={settingsForm.max_checkouts_per_member ?? 3}
                  onChange={e => setSettingsForm({ ...settingsForm, max_checkouts_per_member: parseInt(e.target.value) || 3 })} />
                <div className="form-text">Per member at a time</div>
              </div>
            </div>
          </div>
        </div>

        <div className="card mb-4" style={{ border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
          <div className="card-body">
            <h6 className="fw-bold mb-3" style={headingStyle}>Additional Details</h6>
            <div className="row g-3">
              <div className="col-12">
                <label className="form-label">Garden Rules</label>
                <textarea className="form-control" rows="4" placeholder="Enter garden rules and policies..." value={settingsForm.rules || ''} onChange={e => setSettingsForm({ ...settingsForm, rules: e.target.value })}></textarea>
              </div>
              <div className="col-12">
                <label className="form-label">Photo URL</label>
                <input type="url" className="form-control" placeholder="https://..." value={settingsForm.photo_url || ''} onChange={e => setSettingsForm({ ...settingsForm, photo_url: e.target.value })} />
              </div>
            </div>
          </div>
        </div>

        <button type="submit" className="btn btn-lg mb-4" style={btnStyle}>
          <i className="bi bi-check-circle me-2"></i>Save Settings
        </button>
      </form>

      {/* Danger Zone */}
      <div className="card" style={{ border: '2px solid #dc3545' }}>
        <div className="card-body">
          <h6 className="fw-bold text-danger mb-3"><i className="bi bi-exclamation-triangle me-2"></i>Danger Zone</h6>
          <p className="small text-muted mb-3">Deactivating the garden will hide it from public listings. Members will retain their plot assignments but will not be able to log new activity.</p>
          <button className="btn btn-outline-danger" onClick={() => {
            if (!confirm('Are you sure you want to deactivate this garden? It will be hidden from listings.')) return;
            gardenAdminAPI.updateSettings(id, { is_active: false }).then(() => {
              alert('Garden deactivated.');
              gardensAPI.detail(id).then(res => setGarden(res.data));
            }).catch(err => alert(err.response?.data?.error || 'Error'));
          }}>
            <i className="bi bi-power me-1"></i>Deactivate Garden
          </button>
        </div>
      </div>
    </div>
  );

  const renderEmail = () => {
    if (!emailConfig) return <div className="text-center py-3"><div className="spinner-border spinner-border-sm text-success"></div></div>;
    const eu = (field, value) => setEmailConfig({ ...emailConfig, [field]: value });
    const saveEmail = (e) => {
      e.preventDefault();
      gardenAdminAPI.updateEmailConfig(id, emailConfig).then(r => {
        setEmailConfig(r.data);
        setEmailSaved(true);
        setTimeout(() => setEmailSaved(false), 3000);
      });
    };
    return (
      <div>
        <h4 className="fw-bold mb-4" style={headingStyle}><i className="bi bi-envelope-at me-2"></i>Announcement Email Settings</h4>
        {emailSaved && <div className="alert alert-success py-2"><i className="bi bi-check-circle me-2"></i>Email settings saved!</div>}
        <form onSubmit={saveEmail}>
          <div className="row g-3">
            <div className="col-md-6">
              <label className="form-label fw-semibold">Sender Name</label>
              <input type="text" className="form-control" value={emailConfig.sender_name} onChange={e => eu('sender_name', e.target.value)} placeholder={garden?.name || 'Garden Name'} maxLength={100} />
              <small className="text-muted">Override display name for announcement emails</small>
            </div>
            <div className="col-md-6">
              <label className="form-label fw-semibold">Subject Prefix</label>
              <input type="text" className="form-control" value={emailConfig.subject_prefix} onChange={e => eu('subject_prefix', e.target.value)} placeholder="[Garden Name]" maxLength={50} />
              <small className="text-muted">Prepended to announcement email subjects</small>
            </div>
            <div className="col-md-6">
              <label className="form-label fw-semibold">Closing Text</label>
              <input type="text" className="form-control" value={emailConfig.closing_text} onChange={e => eu('closing_text', e.target.value)} placeholder="Happy Gardening!" maxLength={300} />
              <small className="text-muted">Custom sign-off for announcements</small>
            </div>
            <div className="col-md-6">
              <label className="form-label fw-semibold">Accent Color</label>
              <div className="d-flex gap-2 align-items-center">
                <input type="color" className="form-control form-control-color" value={emailConfig.accent_color} onChange={e => eu('accent_color', e.target.value)} />
                <input type="text" className="form-control" style={{ maxWidth: 120 }} value={emailConfig.accent_color} onChange={e => eu('accent_color', e.target.value)} maxLength={7} />
              </div>
            </div>
          </div>
          <button type="submit" className="btn btn-success mt-3"><i className="bi bi-check-circle me-2"></i>Save Email Settings</button>
        </form>
      </div>
    );
  };

  const renderContent = () => {
    switch (activeTab) {
      case 'dashboard': return renderDashboard();
      case 'plots': return renderPlots();
      case 'events': return renderEvents();
      case 'messages': return renderMessages();
      case 'photos': return renderPhotos();
      case 'announcements': return renderAnnouncements();
      case 'resources': return renderResources();
      case 'email': return renderEmail();
      case 'settings': return renderSettings();
      default: return renderDashboard();
    }
  };

  return (
    <div>
      {/* Top Banner */}
      <div style={{
        background: 'linear-gradient(135deg, #5a3921, #7c4a1e)',
        borderRadius: '12px',
        padding: '28px 32px',
        color: 'white',
        marginBottom: '24px',
      }}>
        <div className="d-flex justify-content-between align-items-center">
          <div>
            <Link to={`/gardens/${id}`} style={{ color: 'rgba(255,255,255,0.7)', textDecoration: 'none', fontSize: '0.85rem' }}>
              <i className="bi bi-arrow-left me-1"></i>Back to Garden
            </Link>
            <h2 className="fw-bold mt-1 mb-0"><i className="bi bi-house-gear me-2"></i>{garden.name} <span style={{ fontWeight: 400, opacity: 0.85 }}>Admin Portal</span></h2>
          </div>
          <div className="text-end d-none d-md-block">
            <div className="small" style={{ opacity: 0.7 }}>Organizer</div>
            <div className="fw-semibold">{garden.organizer_name}</div>
          </div>
        </div>
      </div>

      {/* Sidebar + Content Layout */}
      <div className="d-flex" style={{ gap: '0', minHeight: '600px' }}>
        {/* Sidebar */}
        <div style={{
          width: '220px',
          flexShrink: 0,
          backgroundColor: '#f5eed9',
          borderRight: '3px solid #c9a96e',
          borderRadius: '12px 0 0 12px',
          padding: '16px 0',
        }}>
          <nav>
            {SIDEBAR_TABS.map(tab => (
              <button
                key={tab.key}
                className="btn w-100 text-start d-flex align-items-center gap-2"
                style={{
                  padding: '10px 20px',
                  border: 'none',
                  borderRadius: '0',
                  fontSize: '0.9rem',
                  fontWeight: activeTab === tab.key ? 600 : 400,
                  backgroundColor: activeTab === tab.key ? '#5a3921' : 'transparent',
                  color: activeTab === tab.key ? 'white' : '#5a3921',
                  borderLeft: activeTab === tab.key ? '4px solid #c9a96e' : '4px solid transparent',
                  transition: 'all 0.15s ease',
                }}
                onClick={() => setActiveTab(tab.key)}
              >
                <i className={`bi ${tab.icon}`}></i>
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        {/* Main Content Area */}
        <div style={{ flex: 1, padding: '24px', backgroundColor: '#fff', borderRadius: '0 12px 12px 0', border: '1px solid #e5e0d0', borderLeft: 'none' }}>
          {renderContent()}
        </div>
      </div>
    </div>
  );
}
