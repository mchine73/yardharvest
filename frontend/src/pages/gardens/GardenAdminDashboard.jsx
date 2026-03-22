import { useState, useEffect, Fragment } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { gardensAPI, gardenAdminAPI } from '../../api';
import { useAuth } from '../../AuthContext';
import PhotoLibrary from '../../components/PhotoLibrary';
import PhotoUploadInput from '../../components/PhotoUploadInput';
import QRScanner from '../../components/QRScanner';

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
  { key: 'volunteers', label: 'Volunteers', icon: 'bi-people' },
  { key: 'finance', label: 'Finance', icon: 'bi-cash-stack' },
  { key: 'members', label: 'Members', icon: 'bi-person-badge' },
  { key: 'knowledge', label: 'Knowledge Base', icon: 'bi-book' },
  { key: 'messages', label: 'Messages', icon: 'bi-envelope' },
  { key: 'photos', label: 'Photos', icon: 'bi-camera' },
  { key: 'announcements', label: 'Announcements', icon: 'bi-megaphone' },
  { key: 'resources', label: 'Resources', icon: 'bi-tools' },
  { key: 'communication', label: 'Communication', icon: 'bi-chat-dots' },
  { key: 'settings', label: 'Settings', icon: 'bi-gear' },
];

const EXPENSE_CATEGORIES = ['supplies', 'infrastructure', 'water', 'seeds', 'tools', 'other'];
const KNOWLEDGE_CATEGORIES = ['planting', 'composting', 'pests', 'watering', 'soil', 'tools', 'seasonal', 'general'];
const ROLE_OPTIONS = ['organizer', 'co_organizer', 'treasurer', 'volunteer_lead', 'member'];
const DUES_STATUSES = { unpaid: 'bg-danger', partial: 'bg-warning text-dark', paid: 'bg-success', waived: 'bg-secondary', comp: 'bg-info' };

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

  // Plot Layout Editor
  const [gridRows, setGridRows] = useState(4);
  const [gridCols, setGridCols] = useState(5);
  const [plotPlacements, setPlotPlacements] = useState({});
  const [selectedUnplacedPlot, setSelectedUnplacedPlot] = useState(null);
  const [layoutSaving, setLayoutSaving] = useState(false);
  const [layoutDirty, setLayoutDirty] = useState(false);
  const [layoutDrafts, setLayoutDrafts] = useState([]);

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
  const [showQRScanner, setShowQRScanner] = useState(false);
  const [scannedResource, setScannedResource] = useState(null);

  // Settings
  const [settingsForm, setSettingsForm] = useState({});
  const [settingsSaved, setSettingsSaved] = useState(false);

  // Email Config
  const [emailConfig, setEmailConfig] = useState(null);
  const [emailSaved, setEmailSaved] = useState(false);

  // Volunteers
  const [shifts, setShifts] = useState([]);
  const [showShiftForm, setShowShiftForm] = useState(false);
  const [editingShift, setEditingShift] = useState(null);
  const [shiftForm, setShiftForm] = useState({ title: '', description: '', shift_date: '', start_time: '09:00', end_time: '12:00', max_volunteers: '', recurring: 'none' });
  const [shiftAttendees, setShiftAttendees] = useState([]);
  const [viewingShiftAttendees, setViewingShiftAttendees] = useState(null);
  const [volunteerReport, setVolunteerReport] = useState([]);

  // Finance
  const [financeTab, setFinanceTab] = useState('summary');
  const [financeSummary, setFinanceSummary] = useState(null);
  const [dues, setDues] = useState([]);
  const [duesSeason, setDuesSeason] = useState(new Date().getFullYear());
  const [expenses, setExpenses] = useState([]);
  const [showExpenseForm, setShowExpenseForm] = useState(false);
  const [expenseForm, setExpenseForm] = useState({ title: '', amount: '', category: 'supplies', expense_date: '', paid_by: '', notes: '' });
  const [showPaymentModal, setShowPaymentModal] = useState(null);
  const [paymentForm, setPaymentForm] = useState({ amount_paid: '', payment_method: 'cash', payment_note: '' });
  const [showGenerateDuesModal, setShowGenerateDuesModal] = useState(false);
  const [generateDuesAmount, setGenerateDuesAmount] = useState('');
  const [financeToast, setFinanceToast] = useState(null);
  const [confirmDeleteExpense, setConfirmDeleteExpense] = useState(null);
  const [financeError, setFinanceError] = useState('');

  // Members & Roles
  const [membersList, setMembersList] = useState([]);

  // Knowledge Base
  const [articles, setArticles] = useState([]);
  const [showArticleForm, setShowArticleForm] = useState(false);
  const [editingArticle, setEditingArticle] = useState(null);
  const [articleForm, setArticleForm] = useState({ title: '', body: '', category: 'general', pinned: false });

  // Weather
  const [weatherData, setWeatherData] = useState(null);

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
      gardenAdminAPI.listDrafts(id).then(r => setLayoutDrafts(r.data)).catch(() => {});
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
    if (activeTab === 'communication') {
      gardenAdminAPI.getEmailConfig(id).then(r => setEmailConfig(r.data)).catch(() => {});
    }
    if (activeTab === 'volunteers') {
      gardensAPI.shifts(id, { show: 'all' }).then(r => setShifts(r.data)).catch(() => {});
      gardenAdminAPI.volunteerReport(id).then(r => setVolunteerReport(r.data)).catch(() => {});
    }
    if (activeTab === 'finance') {
      gardenAdminAPI.financeSummary(id, { season_year: duesSeason }).then(r => setFinanceSummary(r.data)).catch(() => {});
      gardenAdminAPI.dues(id, { season_year: duesSeason }).then(r => setDues(r.data)).catch(() => {});
      gardenAdminAPI.expenses(id, { year: duesSeason }).then(r => setExpenses(r.data)).catch(() => {});
    }
    if (activeTab === 'members') {
      gardenAdminAPI.members(id).then(r => setMembersList(r.data)).catch(() => {});
    }
    if (activeTab === 'knowledge') {
      gardensAPI.knowledge(id).then(r => setArticles(r.data)).catch(() => {});
    }
    if (activeTab === 'dashboard') {
      gardenAdminAPI.weather(id).then(r => setWeatherData(r.data)).catch(() => {});
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
  }, [activeTab, garden, id, photoFilter, duesSeason]);

  // Initialize grid dimensions from garden data
  useEffect(() => {
    if (garden) {
      setGridRows(garden.grid_rows || 4);
      setGridCols(garden.grid_cols || 5);
    }
  }, [garden]);

  // Initialize plot placements from existing plot data
  useEffect(() => {
    if (plots.length > 0) {
      const placements = {};
      plots.forEach(p => {
        if (p.grid_row != null && p.grid_col != null) {
          placements[`${p.grid_row}-${p.grid_col}`] = p.id;
        }
      });
      setPlotPlacements(placements);
    }
  }, [plots]);

  if (loading) return <div className="text-center py-5"><div className="spinner-border" style={{ color: '#1B4D3E' }}></div></div>;
  if (!garden) return <div className="text-center py-5"><p>Garden not found.</p><Link to="/gardens">Back to Gardens</Link></div>;
  if (!user || user.id !== garden.organizer_id) {
    return (
      <div className="text-center py-5">
        <i className="bi bi-shield-lock" style={{ fontSize: '3rem', color: '#1B4D3E' }}></i>
        <h4 className="mt-3" style={{ color: '#1B4D3E' }}>Not authorized.</h4>
        <p className="text-muted">Only the garden organizer can access this admin portal.</p>
        <Link to={`/gardens/${id}`} className="btn" style={{ backgroundColor: '#2D6A4F', color: 'white' }}>Back to Garden</Link>
      </div>
    );
  }

  // ==================== HANDLERS ====================

  // --- Plot Layout Editor ---
  const unplacedPlots = plots.filter(p => !Object.values(plotPlacements).includes(p.id));

  const handleCellClick = (row, col) => {
    const key = `${row}-${col}`;
    if (plotPlacements[key]) {
      // Remove plot from this cell
      const newPlacements = { ...plotPlacements };
      delete newPlacements[key];
      setPlotPlacements(newPlacements);
      setLayoutDirty(true);
    } else if (selectedUnplacedPlot) {
      // Place the selected plot here
      const newPlacements = { ...plotPlacements };
      newPlacements[key] = selectedUnplacedPlot;
      setPlotPlacements(newPlacements);
      setSelectedUnplacedPlot(null);
      setLayoutDirty(true);
    }
  };

  const handleSaveLayout = async () => {
    setLayoutSaving(true);
    try {
      const plotUpdates = plots.map(p => {
        const entry = Object.entries(plotPlacements).find(([, pid]) => pid === p.id);
        if (entry) {
          const [key] = entry;
          const [row, col] = key.split('-').map(Number);
          return { id: p.id, grid_row: row, grid_col: col };
        }
        return { id: p.id, grid_row: null, grid_col: null };
      });
      await gardenAdminAPI.updatePlotLayout(id, {
        grid_rows: gridRows,
        grid_cols: gridCols,
        plots: plotUpdates,
      });
      setLayoutDirty(false);
      // Refresh plots
      gardenAdminAPI.plots(id).then(r => setPlots(r.data.plots || r.data || []));
    } catch (err) {
      alert(err.response?.data?.error || 'Error saving layout');
    }
    setLayoutSaving(false);
  };

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

  const btnStyle = { backgroundColor: '#2D6A4F', color: 'white', border: 'none' };
  const btnOutlineStyle = { border: '1px solid #2D6A4F', color: '#2D6A4F', backgroundColor: 'transparent' };
  const headingStyle = { color: '#1A2E25' };

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
            <div className="card h-100" style={{ border: 'none', borderLeft: '4px solid #D4A843', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
              <div className="card-body text-center py-3">
                <i className={`bi ${s.icon}`} style={{ fontSize: '1.4rem', color: '#2D6A4F' }}></i>
                <div style={{ fontSize: '1.6rem', fontWeight: 'bold', color: '#1B4D3E' }}>{s.value}</div>
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

      {/* Weather Card */}
      {weatherData && weatherData.weather && (
        <div className="card mb-4" style={{ border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
          <div className="card-body">
            <h6 className="fw-bold mb-3" style={headingStyle}><i className="bi bi-cloud-sun me-2"></i>Current Weather</h6>
            <div className="d-flex align-items-center gap-3">
              <div style={{ fontSize: '2rem', fontWeight: 'bold', color: '#2D6A4F' }}>{weatherData.weather.temp_f}°F</div>
              <div>
                <div className="fw-semibold">{weatherData.weather.conditions}</div>
                <div className="text-muted small">Feels like {weatherData.weather.feels_like_f}°F &middot; Humidity {weatherData.weather.humidity}% &middot; Wind {weatherData.weather.wind_mph} mph</div>
                {weatherData.weather.source === 'mock' && <div className="text-muted small fst-italic">(Demo data — set OPENWEATHER_API_KEY for live weather)</div>}
              </div>
            </div>
            {weatherData.alerts && weatherData.alerts.length > 0 && (
              <div className="mt-3">
                {weatherData.alerts.map(a => (
                  <div key={a.id} className={`alert ${a.severity === 'critical' ? 'alert-danger' : a.severity === 'warning' ? 'alert-warning' : 'alert-info'} py-2 mb-2`}>
                    <i className={`bi ${a.alert_type === 'frost' ? 'bi-snow' : a.alert_type === 'heat' ? 'bi-thermometer-high' : a.alert_type === 'storm' ? 'bi-cloud-lightning' : 'bi-exclamation-triangle'} me-2`}></i>
                    <strong>{a.alert_type}:</strong> {a.message}
                    <button className="btn btn-sm btn-outline-secondary ms-2" onClick={() => gardenAdminAPI.dismissWeatherAlert(id, a.id).then(() => gardenAdminAPI.weather(id).then(r => setWeatherData(r.data)))}>Dismiss</button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

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
                  <div style={{ width: '36px', height: '36px', borderRadius: '50%', backgroundColor: '#F8F6F0', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                    <i className={`bi ${a.icon || 'bi-activity'}`} style={{ color: '#2D6A4F', fontSize: '0.9rem' }}></i>
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

      {/* Plot Layout Editor */}
      <div className="card mb-4" style={{ border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
        <div className="card-body">
          <div className="d-flex justify-content-between align-items-center mb-2">
            <h5 className="fw-bold mb-0"><i className="bi bi-grid-3x3-gap me-2"></i>Garden Designer</h5>
            <div className="d-flex align-items-center gap-2">
              <button className="btn btn-sm btn-outline-success" onClick={() => {
                gardenAdminAPI.createDraft(id, { name: `Draft ${new Date().toLocaleDateString()}` }).then(() => {
                  gardenAdminAPI.listDrafts(id).then(r => setLayoutDrafts(r.data));
                }).catch(err => alert(err.response?.data?.error || 'Error creating draft'));
              }}><i className="bi bi-plus-lg me-1"></i>New Draft</button>
              <button className="btn btn-sm btn-outline-secondary" onClick={() => window.print()} title="Print layout">
                <i className="bi bi-printer"></i>
              </button>
            </div>
          </div>

          {/* Draft selector */}
          {layoutDrafts.length > 0 && (
            <div className="d-flex align-items-center gap-2 mb-2">
              <small className="text-muted">Drafts:</small>
              {layoutDrafts.filter(d => d.is_active).map(d => (
                <span key={d.id} className="badge bg-info text-dark" style={{ cursor: 'pointer' }} onClick={() => {
                  // Load draft into the editor
                  const data = d.layout_data || {};
                  if (data.placements) {
                    const newPlacements = {};
                    Object.entries(data.placements).forEach(([k, v]) => { newPlacements[k] = v.plot_id; });
                    setPlotPlacements(newPlacements);
                  }
                  setGridRows(d.grid_rows);
                  setGridCols(d.grid_cols);
                  setLayoutDirty(true);
                }}>
                  <i className="bi bi-file-earmark me-1"></i>{d.name}
                </span>
              ))}
            </div>
          )}

          <div className="d-flex align-items-center gap-3 mb-3">
            <div className="d-flex align-items-center gap-2">
              <label className="small fw-semibold mb-0">Rows:</label>
              <input type="number" className="form-control form-control-sm" style={{ width: '60px' }}
                min="2" max="20" value={gridRows}
                onChange={e => { setGridRows(parseInt(e.target.value) || 2); setLayoutDirty(true); }} />
            </div>
            <div className="d-flex align-items-center gap-2">
              <label className="small fw-semibold mb-0">Cols:</label>
              <input type="number" className="form-control form-control-sm" style={{ width: '60px' }}
                min="2" max="20" value={gridCols}
                onChange={e => { setGridCols(parseInt(e.target.value) || 2); setLayoutDirty(true); }} />
            </div>
          </div>

          {/* Color Legend */}
          <div className="d-flex gap-3 mb-3" style={{ fontSize: '0.8rem' }}>
            {Object.entries({ available: '#40916c', assigned: '#3b82f6', reserved: '#f59e0b', maintenance: '#6b7280' }).map(([status, color]) => (
              <span key={status} style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span style={{ width: '12px', height: '12px', borderRadius: '3px', backgroundColor: color, display: 'inline-block' }}></span>
                <span style={{ textTransform: 'capitalize' }}>{status}</span>
              </span>
            ))}
          </div>

          <div className="row">
            <div className="col-md-9">
              {/* Grid */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: `repeat(${gridCols}, 1fr)`,
                gap: '4px',
                maxWidth: '700px',
              }}>
                {Array.from({ length: gridRows * gridCols }, (_, idx) => {
                  const row = Math.floor(idx / gridCols);
                  const col = idx % gridCols;
                  const key = `${row}-${col}`;
                  const plotId = plotPlacements[key];
                  const plot = plotId ? plots.find(p => p.id === plotId) : null;

                  if (plot) {
                    return (
                      <div key={idx} onClick={() => handleCellClick(row, col)}
                        title={`#${plot.plot_number}${plot.custom_name ? ' "' + plot.custom_name + '"' : ''}\nStatus: ${plot.status}${plot.assigned_to_name ? '\nAssigned: ' + plot.assigned_to_name : ''}${plot.size ? '\nSize: ' + plot.size : ''}${plot.soil_type ? '\nSoil: ' + plot.soil_type : ''}${plot.sun_exposure ? '\nSun: ' + plot.sun_exposure.replace('_', ' ') : ''}\nClick to remove`}
                        style={{
                          aspectRatio: '1', borderRadius: '6px', cursor: 'pointer',
                          backgroundColor: { available: '#40916c', assigned: '#3b82f6', reserved: '#f59e0b', maintenance: '#6b7280' }[plot.status] || '#6b7280',
                          color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center',
                          fontSize: '0.75rem', fontWeight: 'bold',
                          transition: 'transform 0.1s',
                        }}
                        onMouseEnter={e => e.currentTarget.style.transform = 'scale(1.05)'}
                        onMouseLeave={e => e.currentTarget.style.transform = 'scale(1)'}
                      >
                        <div style={{ lineHeight: 1.1, textAlign: 'center' }}>
                          <div>#{plot.plot_number}</div>
                          {(plot.custom_name || (plot.assigned_to_name)) && (
                            <div style={{ fontSize: '0.6rem', fontWeight: 'normal', opacity: 0.85, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '100%', padding: '0 2px' }}>
                              {plot.custom_name || plot.assigned_to_name || ''}
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  }
                  return (
                    <div key={idx} onClick={() => handleCellClick(row, col)}
                      title={selectedUnplacedPlot ? 'Click to place plot here' : 'Select a plot from the list first'}
                      style={{
                        aspectRatio: '1', borderRadius: '6px',
                        backgroundColor: selectedUnplacedPlot ? '#d1fae5' : '#f3f4f6',
                        border: selectedUnplacedPlot ? '2px dashed #40916c' : '1px dashed #d1d5db',
                        cursor: selectedUnplacedPlot ? 'pointer' : 'default',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: '0.6rem', color: '#9ca3af',
                        transition: 'background-color 0.2s',
                      }}
                      onMouseEnter={e => { if (selectedUnplacedPlot) e.currentTarget.style.backgroundColor = '#a7f3d0'; }}
                      onMouseLeave={e => { if (selectedUnplacedPlot) e.currentTarget.style.backgroundColor = '#d1fae5'; }}
                    >{selectedUnplacedPlot ? '+' : ''}</div>
                  );
                })}
              </div>
            </div>

            <div className="col-md-3">
              {/* Unplaced Plots */}
              <h6 className="fw-bold mb-2 small">Unplaced Plots ({unplacedPlots.length})</h6>
              {unplacedPlots.length === 0 ? (
                <p className="text-muted small">All plots placed!</p>
              ) : (
                <div style={{ maxHeight: '300px', overflowY: 'auto' }}>
                  {unplacedPlots.map(p => (
                    <div key={p.id}
                      onClick={() => setSelectedUnplacedPlot(selectedUnplacedPlot === p.id ? null : p.id)}
                      style={{
                        padding: '8px', marginBottom: '4px', borderRadius: '6px', cursor: 'pointer',
                        backgroundColor: selectedUnplacedPlot === p.id ? '#d1fae5' : '#f8f9fa',
                        border: selectedUnplacedPlot === p.id ? '2px solid #40916c' : '1px solid #e5e7eb',
                        fontSize: '0.8rem',
                      }}>
                      <strong>#{p.plot_number}</strong>
                      <span className="ms-1 text-muted">{p.size || ''}</span>
                      <span className="badge ms-1" style={{
                        backgroundColor: { available: '#40916c', assigned: '#3b82f6', reserved: '#f59e0b', maintenance: '#6b7280' }[p.status],
                        color: 'white', fontSize: '0.6rem',
                      }}>{p.status}</span>
                    </div>
                  ))}
                </div>
              )}
              <p className="text-muted small mt-2">
                <i className="bi bi-info-circle me-1"></i>
                Select a plot, then click an empty cell to place it. Click an occupied cell to remove it.
              </p>
            </div>
          </div>

          {/* Save Button */}
          <div className="mt-3 d-flex align-items-center gap-3">
            <button className="btn" style={{ backgroundColor: '#2d6a4f', color: 'white' }}
              onClick={handleSaveLayout} disabled={!layoutDirty || layoutSaving}>
              {layoutSaving ? (
                <><span className="spinner-border spinner-border-sm me-2"></span>Saving...</>
              ) : (
                <><i className="bi bi-check-lg me-2"></i>Save Layout</>
              )}
            </button>
            {layoutDirty && <span className="text-warning small"><i className="bi bi-exclamation-triangle me-1"></i>Unsaved changes</span>}
          </div>
        </div>
      </div>

      <div className="table-responsive mb-4">
        <table className="table table-hover align-middle">
          <thead style={{ backgroundColor: '#F8F6F0' }}>
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
                  <td><strong>#{plot.plot_number}</strong>{plot.custom_name && <div className="text-muted small fst-italic">{plot.custom_name}</div>}</td>
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
                        setPlotForm({ size: plot.size || '', location_notes: plot.location_notes || '', renewal_date: plot.renewal_date || '', custom_name: plot.custom_name || '', soil_type: plot.soil_type || '', sun_exposure: plot.sun_exposure || '' });
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
                    <td colSpan="7" style={{ backgroundColor: '#F8F6F0' }}>
                      <div className="row g-2 p-2">
                        <div className="col-md-2">
                          <label className="form-label small fw-bold">Custom Name</label>
                          <input type="text" className="form-control form-control-sm" placeholder="e.g. Sunny Corner" value={plotForm.custom_name} onChange={e => setPlotForm({ ...plotForm, custom_name: e.target.value })} />
                        </div>
                        <div className="col-md-2">
                          <label className="form-label small fw-bold">Size</label>
                          <input type="text" className="form-control form-control-sm" placeholder="e.g. 4x8 ft" value={plotForm.size} onChange={e => setPlotForm({ ...plotForm, size: e.target.value })} />
                        </div>
                        <div className="col-md-2">
                          <label className="form-label small fw-bold">Soil Type</label>
                          <select className="form-select form-select-sm" value={plotForm.soil_type} onChange={e => setPlotForm({ ...plotForm, soil_type: e.target.value })}>
                            <option value="">--</option>
                            <option value="clay">Clay</option>
                            <option value="loam">Loam</option>
                            <option value="sandy">Sandy</option>
                            <option value="silt">Silt</option>
                            <option value="mixed">Mixed</option>
                          </select>
                        </div>
                        <div className="col-md-2">
                          <label className="form-label small fw-bold">Sun</label>
                          <select className="form-select form-select-sm" value={plotForm.sun_exposure} onChange={e => setPlotForm({ ...plotForm, sun_exposure: e.target.value })}>
                            <option value="">--</option>
                            <option value="full_sun">Full Sun</option>
                            <option value="partial_shade">Partial Shade</option>
                            <option value="full_shade">Full Shade</option>
                          </select>
                        </div>
                        <div className="col-md-2">
                          <label className="form-label small fw-bold">Renewal Date</label>
                          <input type="date" className="form-control form-control-sm" value={plotForm.renewal_date} onChange={e => setPlotForm({ ...plotForm, renewal_date: e.target.value })} />
                        </div>
                        <div className="col-md-2 d-flex align-items-end gap-1">
                          <button className="btn btn-sm" style={btnStyle} onClick={() => handleUpdatePlot(plot.id)}>Save</button>
                          <button className="btn btn-sm btn-outline-secondary" onClick={() => setEditingPlot(null)}>Cancel</button>
                        </div>
                      </div>
                      <div className="row g-2 px-2 pb-2">
                        <div className="col-md-6">
                          <label className="form-label small fw-bold">Location Notes</label>
                          <input type="text" className="form-control form-control-sm" placeholder="e.g. Row B, near water spigot" value={plotForm.location_notes} onChange={e => setPlotForm({ ...plotForm, location_notes: e.target.value })} />
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
          <thead style={{ backgroundColor: '#F8F6F0' }}>
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
    <div className="card mb-4" style={{ border: '2px solid #D4A843' }}>
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
          <thead style={{ backgroundColor: '#F8F6F0' }}>
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
                      <td colSpan="5" style={{ backgroundColor: '#F8F6F0' }}>
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
      <div className="card mb-4" style={{ border: '2px solid #D4A843' }}>
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
          <div key={msg.id} className="list-group-item" style={{ borderLeft: msg.is_read ? '3px solid #D4A843' : '3px solid #2D6A4F' }}>
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
                {!msg.is_read && <span className="badge" style={{ backgroundColor: '#2D6A4F' }}>Unread</span>}
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
      <h4 className="fw-bold mb-4"><i className="bi bi-images me-2"></i>Photo Library</h4>
      <PhotoLibrary gardenId={parseInt(id)} />
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
          <div className="card mb-4" style={{ border: '2px solid #D4A843' }}>
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
                    {ann.pinned && <i className="bi bi-pin-fill" style={{ color: '#2D6A4F' }} title="Pinned"></i>}
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
              <i className="bi bi-megaphone" style={{ fontSize: '2.5rem', color: '#D4A843' }}></i>
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
        <div>
          <button className="btn btn-outline-success btn-sm me-2" onClick={() => setShowQRScanner(true)}>
            <i className="bi bi-qr-code-scan me-1"></i>Scan QR
          </button>
          <button className="btn" style={btnStyle} onClick={() => setShowResForm(!showResForm)}>
            <i className="bi bi-plus-circle me-1"></i>Add Resource
          </button>
        </div>
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
        <div className="card mb-4" style={{ border: '2px solid #D4A843' }}>
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
                  <input className="form-control" list="resource-types" value={resForm.resource_type} onChange={e => setResForm({ ...resForm, resource_type: e.target.value })} placeholder="e.g. tool, supply" />
                  <datalist id="resource-types">
                    <option value="tool" />
                    <option value="supply" />
                    <option value="infrastructure" />
                    <option value="equipment" />
                    <option value="seed" />
                    <option value="other" />
                  </datalist>
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
          <thead style={{ backgroundColor: '#F8F6F0' }}>
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

      {/* QR Scanner Modal */}
      <QRScanner
        isOpen={showQRScanner}
        onClose={() => { setShowQRScanner(false); setScannedResource(null); }}
        onScan={(gardenId, resourceId) => {
          setShowQRScanner(false);
          const found = resources.find(r => r.id === resourceId);
          if (found) {
            setScannedResource(found);
          } else {
            gardensAPI.resourceLookup(`/gardens/${gardenId}/resources/${resourceId}/scan`).then(res => {
              setScannedResource(res.data.resource);
            }).catch(() => setScannedResource(null));
          }
        }}
      />

      {/* Scanned Resource Quick Action */}
      {scannedResource && (
        <div className="modal d-block" style={{ backgroundColor: 'rgba(0,0,0,0.5)' }} onClick={() => setScannedResource(null)}>
          <div className="modal-dialog modal-dialog-centered modal-sm" onClick={e => e.stopPropagation()}>
            <div className="modal-content" style={{ borderRadius: 12 }}>
              <div className="modal-body text-center p-4">
                <h5>{scannedResource.name}</h5>
                <p className="text-muted small mb-1">{scannedResource.resource_type}</p>
                <span className={`badge ${scannedResource.checked_out_to_id ? 'bg-warning text-dark' : 'bg-success'} fs-6 mb-3`}>
                  {scannedResource.checked_out_to_id ? `Checked out to ${scannedResource.checked_out_to_name || 'someone'}` : 'Available'}
                </span>
                <div className="d-grid gap-2">
                  {!scannedResource.checked_out_to_id ? (
                    <button className="btn btn-success btn-lg" onClick={() => {
                      gardensAPI.checkoutResource(id, scannedResource.id, {}).then(() => {
                        setScannedResource(null);
                        gardensAPI.resources(id).then(r => setResources(r.data));
                      }).catch(err => alert(err.response?.data?.error || 'Checkout failed'));
                    }}><i className="bi bi-box-arrow-right me-2"></i>Check Out</button>
                  ) : (
                    <button className="btn btn-primary btn-lg" onClick={() => {
                      gardensAPI.returnResource(id, scannedResource.id, {}).then(() => {
                        setScannedResource(null);
                        gardensAPI.resources(id).then(r => setResources(r.data));
                      }).catch(err => alert(err.response?.data?.error || 'Return failed'));
                    }}><i className="bi bi-box-arrow-in-left me-2"></i>Return</button>
                  )}
                  <button className="btn btn-outline-secondary" onClick={() => { setScannedResource(null); setShowQRScanner(true); }}>
                    <i className="bi bi-qr-code-scan me-1"></i>Scan Another
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
  };

  const renderSettings = () => (
    <div>
      <h4 className="fw-bold mb-4" style={headingStyle}><i className="bi bi-gear me-2"></i>Garden Settings</h4>

      {settingsSaved && (
        <div className="alert" style={{ backgroundColor: '#D8EDDF', color: '#1B4D3E', border: 'none' }}>
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
                <PhotoUploadInput
                  value={settingsForm.photo_url || ''}
                  onChange={val => setSettingsForm({ ...settingsForm, photo_url: val })}
                  label="Garden Photo"
                  category="garden"
                  gardenId={parseInt(id)}
                  hint="Upload a photo of your garden"
                />
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

  // ==================== VOLUNTEERS TAB ====================
  const loadShifts = () => {
    gardensAPI.shifts(id, { show: 'all' }).then(r => setShifts(r.data)).catch(() => {});
    gardenAdminAPI.volunteerReport(id).then(r => setVolunteerReport(r.data)).catch(() => {});
  };

  const handleCreateShift = (e) => {
    e.preventDefault();
    const data = { ...shiftForm, max_volunteers: shiftForm.max_volunteers ? parseInt(shiftForm.max_volunteers) : null };
    gardenAdminAPI.createShift(id, data).then(() => {
      setShowShiftForm(false);
      setShiftForm({ title: '', description: '', shift_date: '', start_time: '09:00', end_time: '12:00', max_volunteers: '', recurring: 'none' });
      loadShifts();
    }).catch(err => alert(err.response?.data?.error || 'Error creating shift'));
  };

  const handleDeleteShift = (shiftId) => {
    if (!confirm('Delete this shift and all signups?')) return;
    gardenAdminAPI.deleteShift(id, shiftId).then(() => loadShifts()).catch(err => alert(err.response?.data?.error || 'Error'));
  };

  const handleViewShiftAttendees = (shiftId) => {
    if (viewingShiftAttendees === shiftId) { setViewingShiftAttendees(null); return; }
    setViewingShiftAttendees(shiftId);
    gardenAdminAPI.shiftAttendees(id, shiftId).then(r => setShiftAttendees(r.data)).catch(() => setShiftAttendees([]));
  };

  const handleMarkAttendance = (shiftId, records) => {
    gardenAdminAPI.markAttendance(id, shiftId, { records }).then(() => {
      gardenAdminAPI.shiftAttendees(id, shiftId).then(r => setShiftAttendees(r.data));
      loadShifts();
    }).catch(err => alert(err.response?.data?.error || 'Error'));
  };

  const renderVolunteers = () => (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h4 className="fw-bold mb-0" style={headingStyle}><i className="bi bi-people me-2"></i>Volunteer Shifts</h4>
        <button className="btn" style={btnStyle} onClick={() => setShowShiftForm(!showShiftForm)}>
          <i className="bi bi-plus-circle me-1"></i>{showShiftForm ? 'Cancel' : 'Create Shift'}
        </button>
      </div>

      {showShiftForm && (
        <div className="card mb-4" style={{ backgroundColor: '#F8F6F0', border: '1px solid #D4A843' }}>
          <div className="card-body">
            <form onSubmit={handleCreateShift}>
              <div className="row g-3">
                <div className="col-md-6">
                  <label className="form-label fw-semibold">Title *</label>
                  <input type="text" className="form-control" value={shiftForm.title} onChange={e => setShiftForm({ ...shiftForm, title: e.target.value })} required />
                </div>
                <div className="col-md-3">
                  <label className="form-label fw-semibold">Date *</label>
                  <input type="date" className="form-control" value={shiftForm.shift_date} onChange={e => setShiftForm({ ...shiftForm, shift_date: e.target.value })} required />
                </div>
                <div className="col-md-3">
                  <label className="form-label fw-semibold">Max Volunteers</label>
                  <input type="number" className="form-control" value={shiftForm.max_volunteers} onChange={e => setShiftForm({ ...shiftForm, max_volunteers: e.target.value })} />
                </div>
                <div className="col-md-3">
                  <label className="form-label fw-semibold">Start Time *</label>
                  <input type="time" className="form-control" value={shiftForm.start_time} onChange={e => setShiftForm({ ...shiftForm, start_time: e.target.value })} required />
                </div>
                <div className="col-md-3">
                  <label className="form-label fw-semibold">End Time *</label>
                  <input type="time" className="form-control" value={shiftForm.end_time} onChange={e => setShiftForm({ ...shiftForm, end_time: e.target.value })} required />
                </div>
                <div className="col-md-3">
                  <label className="form-label fw-semibold">Recurring</label>
                  <select className="form-select" value={shiftForm.recurring} onChange={e => setShiftForm({ ...shiftForm, recurring: e.target.value })}>
                    <option value="none">None</option>
                    <option value="weekly">Weekly</option>
                    <option value="biweekly">Biweekly</option>
                    <option value="monthly">Monthly</option>
                  </select>
                </div>
                <div className="col-12">
                  <label className="form-label fw-semibold">Description</label>
                  <textarea className="form-control" rows={2} value={shiftForm.description} onChange={e => setShiftForm({ ...shiftForm, description: e.target.value })} />
                </div>
                <div className="col-12"><button type="submit" className="btn" style={btnStyle}><i className="bi bi-check-circle me-1"></i>Create Shift</button></div>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Shifts Table */}
      <div className="table-responsive mb-4">
        <table className="table table-hover align-middle">
          <thead style={{ backgroundColor: '#F8F6F0' }}><tr><th>Title</th><th>Date</th><th>Time</th><th>Signups</th><th>Recurring</th><th>Actions</th></tr></thead>
          <tbody>
            {shifts.map(s => (
              <Fragment key={s.id}>
                <tr>
                  <td><strong>{s.title}</strong>{s.description && <div className="text-muted small">{s.description.substring(0, 80)}</div>}</td>
                  <td>{s.shift_date}</td>
                  <td>{s.start_time} - {s.end_time}</td>
                  <td><span className="badge" style={{ backgroundColor: '#2D6A4F' }}>{s.signup_count}{s.max_volunteers ? `/${s.max_volunteers}` : ''}</span></td>
                  <td>{s.recurring !== 'none' && <span className="badge bg-info">{s.recurring}</span>}</td>
                  <td>
                    <div className="d-flex gap-1">
                      <button className="btn btn-sm" style={btnOutlineStyle} onClick={() => handleViewShiftAttendees(s.id)}><i className="bi bi-people"></i></button>
                      <button className="btn btn-sm btn-outline-danger" onClick={() => handleDeleteShift(s.id)}><i className="bi bi-trash"></i></button>
                    </div>
                  </td>
                </tr>
                {viewingShiftAttendees === s.id && (
                  <tr><td colSpan="6" style={{ backgroundColor: '#F8F6F0' }}>
                    <div className="p-2">
                      <h6 className="fw-bold">Attendees — {s.title}</h6>
                      {shiftAttendees.length === 0 ? <p className="text-muted small">No signups yet.</p> : (
                        <table className="table table-sm mb-2">
                          <thead><tr><th>Name</th><th>Status</th><th>Hours</th><th>Actions</th></tr></thead>
                          <tbody>{shiftAttendees.map(a => (
                            <tr key={a.id}>
                              <td>{a.user_name}</td>
                              <td><span className={`badge ${a.status === 'attended' ? 'bg-success' : a.status === 'no_show' ? 'bg-danger' : 'bg-secondary'}`}>{a.status}</span></td>
                              <td>{a.hours_logged ?? '--'}</td>
                              <td>
                                <div className="d-flex gap-1">
                                  <button className="btn btn-sm btn-outline-success" onClick={() => handleMarkAttendance(s.id, [{ user_id: a.user_id, status: 'attended', hours_logged: parseFloat(prompt('Hours worked:', a.hours_logged || ((new Date(`2000-01-01T${s.end_time}`) - new Date(`2000-01-01T${s.start_time}`)) / 3600000).toFixed(1))) || 0 }])}>Attended</button>
                                  <button className="btn btn-sm btn-outline-danger" onClick={() => handleMarkAttendance(s.id, [{ user_id: a.user_id, status: 'no_show' }])}>No Show</button>
                                </div>
                              </td>
                            </tr>
                          ))}</tbody>
                        </table>
                      )}
                    </div>
                  </td></tr>
                )}
              </Fragment>
            ))}
            {shifts.length === 0 && <tr><td colSpan="6" className="text-center text-muted py-4">No shifts scheduled.</td></tr>}
          </tbody>
        </table>
      </div>

      {/* Volunteer Leaderboard */}
      <h5 className="fw-bold mb-3" style={headingStyle}><i className="bi bi-trophy me-2"></i>Volunteer Leaderboard</h5>
      <div className="card" style={{ border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
        <div className="card-body">
          {volunteerReport.length === 0 ? <p className="text-muted">No volunteer data yet.</p> : (
            <table className="table table-sm">
              <thead style={{ backgroundColor: '#F8F6F0' }}><tr><th>#</th><th>Name</th><th>Hours</th><th>Shifts</th><th>No Shows</th></tr></thead>
              <tbody>{volunteerReport.slice(0, 10).map((v, i) => (
                <tr key={v.user_id}>
                  <td>{i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : i + 1}</td>
                  <td><strong>{v.user_name}</strong></td>
                  <td><span className="fw-bold" style={{ color: '#2D6A4F' }}>{v.total_hours.toFixed(1)}</span></td>
                  <td>{v.shifts_attended}</td>
                  <td>{v.no_shows > 0 && <span className="text-danger">{v.no_shows}</span>}</td>
                </tr>
              ))}</tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );

  // ==================== FINANCE TAB ====================
  const loadFinance = () => {
    gardenAdminAPI.financeSummary(id, { season_year: duesSeason }).then(r => setFinanceSummary(r.data)).catch(() => {});
    gardenAdminAPI.dues(id, { season_year: duesSeason }).then(r => setDues(r.data)).catch(() => {});
    gardenAdminAPI.expenses(id, { year: duesSeason }).then(r => setExpenses(r.data)).catch(() => {});
  };

  const showFinanceToast = (msg, type = 'success') => {
    setFinanceToast({ msg, type });
    setTimeout(() => setFinanceToast(null), 4000);
  };

  const handleGenerateDues = () => {
    setFinanceError('');
    gardenAdminAPI.generateDues(id, { season_year: duesSeason, amount: parseFloat(generateDuesAmount) })
      .then(r => { showFinanceToast(r.data.message); setShowGenerateDuesModal(false); setGenerateDuesAmount(''); loadFinance(); })
      .catch(err => { setFinanceError(err.response?.data?.error || 'Failed to generate dues'); });
  };

  const handleRecordPayment = (duesId) => {
    gardenAdminAPI.updateDues(id, duesId, paymentForm).then(() => {
      setShowPaymentModal(null);
      setPaymentForm({ amount_paid: '', payment_method: 'cash', payment_note: '' });
      showFinanceToast('Payment recorded successfully');
      loadFinance();
    }).catch(err => showFinanceToast(err.response?.data?.error || 'Error recording payment', 'danger'));
  };

  const handleCreateExpense = (e) => {
    e.preventDefault();
    gardenAdminAPI.createExpense(id, { ...expenseForm, amount: parseFloat(expenseForm.amount) }).then(() => {
      setShowExpenseForm(false);
      setExpenseForm({ title: '', amount: '', category: 'supplies', expense_date: '', paid_by: '', notes: '' });
      showFinanceToast('Expense logged successfully');
      loadFinance();
    }).catch(err => showFinanceToast(err.response?.data?.error || 'Error logging expense', 'danger'));
  };

  const renderFinance = () => (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h4 className="fw-bold mb-0" style={headingStyle}><i className="bi bi-cash-stack me-2"></i>Finance</h4>
        <div className="d-flex align-items-center gap-2">
          <i className="bi bi-calendar3" style={{ color: '#2D6A4F' }}></i>
          <label className="fw-semibold small mb-0" style={{ color: '#2D6A4F' }}>Year:</label>
          <select className="form-select form-select-sm" style={{ width: '110px', borderColor: '#D4A843' }}
            value={duesSeason} onChange={e => setDuesSeason(parseInt(e.target.value))}>
            {[...Array(7)].map((_, i) => { const y = new Date().getFullYear() - 3 + i; return <option key={y} value={y}>{y}</option>; })}
          </select>
        </div>
      </div>

      {/* Toast Notification */}
      {financeToast && (
        <div className={`alert alert-${financeToast.type === 'danger' ? 'danger' : 'success'} alert-dismissible fade show py-2`} role="alert">
          <i className={`bi ${financeToast.type === 'danger' ? 'bi-exclamation-triangle' : 'bi-check-circle'} me-2`}></i>
          {financeToast.msg}
          <button type="button" className="btn-close" onClick={() => setFinanceToast(null)}></button>
        </div>
      )}

      {/* Generate Dues Modal */}
      {showGenerateDuesModal && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.5)', zIndex: 1050, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          onClick={(e) => { if (e.target === e.currentTarget) setShowGenerateDuesModal(false); }}>
          <div className="card" style={{ width: '440px', maxWidth: '90%', border: 'none', boxShadow: '0 8px 32px rgba(0,0,0,0.2)', borderRadius: '16px' }}>
            <div className="card-body p-4">
              <div className="d-flex justify-content-between align-items-center mb-3">
                <h5 className="fw-bold mb-0" style={{ color: '#2D6A4F' }}><i className="bi bi-receipt me-2"></i>Generate Dues</h5>
                <button className="btn-close" onClick={() => { setShowGenerateDuesModal(false); setFinanceError(''); }}></button>
              </div>
              <p className="text-muted small mb-3">Create dues records for all current plot holders for the <strong>{duesSeason}</strong> season.</p>
              {financeError && <div className="alert alert-danger py-2 small">{financeError}</div>}
              <div className="mb-3">
                <label className="form-label fw-semibold">Annual Dues Amount ($) *</label>
                <input type="number" step="0.01" min="0" className="form-control form-control-lg"
                  placeholder="e.g. 50.00" value={generateDuesAmount}
                  onChange={e => setGenerateDuesAmount(e.target.value)}
                  autoFocus />
                <small className="text-muted">Based on plot fee: ${garden.plot_fee_annual || 0}</small>
              </div>
              <div className="d-flex gap-2 justify-content-end">
                <button className="btn btn-outline-secondary" onClick={() => { setShowGenerateDuesModal(false); setFinanceError(''); }}>Cancel</button>
                <button className="btn" style={btnStyle} onClick={handleGenerateDues} disabled={!generateDuesAmount || parseFloat(generateDuesAmount) <= 0}>
                  <i className="bi bi-check-circle me-1"></i>Generate Dues
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Delete Expense Confirmation Modal */}
      {confirmDeleteExpense && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.5)', zIndex: 1050, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          onClick={(e) => { if (e.target === e.currentTarget) setConfirmDeleteExpense(null); }}>
          <div className="card" style={{ width: '400px', maxWidth: '90%', border: 'none', boxShadow: '0 8px 32px rgba(0,0,0,0.2)', borderRadius: '16px' }}>
            <div className="card-body p-4">
              <h5 className="fw-bold mb-3" style={{ color: '#dc3545' }}><i className="bi bi-exclamation-triangle me-2"></i>Delete Expense</h5>
              <p>Are you sure you want to delete <strong>"{confirmDeleteExpense.title}"</strong> (${confirmDeleteExpense.amount.toFixed(2)})?</p>
              <div className="d-flex gap-2 justify-content-end">
                <button className="btn btn-outline-secondary" onClick={() => setConfirmDeleteExpense(null)}>Cancel</button>
                <button className="btn btn-danger" onClick={() => {
                  gardenAdminAPI.deleteExpense(id, confirmDeleteExpense.id).then(() => { showFinanceToast('Expense deleted'); loadFinance(); });
                  setConfirmDeleteExpense(null);
                }}><i className="bi bi-trash me-1"></i>Delete</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Summary Cards */}
      {financeSummary && (
        <div className="row g-3 mb-4">
          {[
            { label: 'Dues Expected', value: `$${financeSummary.total_dues_expected.toFixed(2)}`, color: '#2D6A4F' },
            { label: 'Collected', value: `$${financeSummary.total_collected.toFixed(2)}`, color: '#40916c' },
            { label: 'Outstanding', value: `$${financeSummary.outstanding.toFixed(2)}`, color: '#dc3545' },
            { label: 'Collection Rate', value: `${financeSummary.collection_rate}%`, color: '#3b82f6' },
            { label: 'Expenses', value: `$${financeSummary.expenses_total.toFixed(2)}`, color: '#f59e0b' },
            { label: 'Net Balance', value: `$${financeSummary.net_balance.toFixed(2)}`, color: financeSummary.net_balance >= 0 ? '#40916c' : '#dc3545' },
          ].map((s, i) => (
            <div key={i} className="col-6 col-md-4 col-lg-2">
              <div className="card h-100" style={{ border: 'none', borderLeft: `4px solid ${s.color}`, boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
                <div className="card-body text-center py-3">
                  <div style={{ fontSize: '1.4rem', fontWeight: 'bold', color: s.color }}>{s.value}</div>
                  <div style={{ fontSize: '0.75rem', color: '#6b7280' }}>{s.label}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Sub-tabs */}
      <ul className="nav nav-tabs mb-3">
        {['summary', 'dues', 'expenses'].map(t => (
          <li key={t} className="nav-item"><button className={`nav-link ${financeTab === t ? 'active' : ''}`} onClick={() => setFinanceTab(t)}>{t.charAt(0).toUpperCase() + t.slice(1)}</button></li>
        ))}
      </ul>

      {financeTab === 'dues' && (
        <div>
          <div className="d-flex justify-content-between align-items-center mb-3">
            <div className="text-muted small"><i className="bi bi-info-circle me-1"></i>Showing dues for <strong>{duesSeason}</strong></div>
            <button className="btn" style={btnStyle} onClick={() => { setGenerateDuesAmount(String(garden.plot_fee_annual || 50)); setFinanceError(''); setShowGenerateDuesModal(true); }}><i className="bi bi-plus-circle me-1"></i>Generate Dues</button>
          </div>
          <div className="table-responsive">
            <table className="table table-hover align-middle">
              <thead style={{ backgroundColor: '#F8F6F0' }}><tr><th>Member</th><th>Due</th><th>Paid</th><th>Status</th><th>Method</th><th>Actions</th></tr></thead>
              <tbody>
                {dues.map(d => (
                  <Fragment key={d.id}>
                    <tr>
                      <td><strong>{d.user_name}</strong></td>
                      <td>${d.amount_due.toFixed(2)}</td>
                      <td>${d.amount_paid.toFixed(2)}</td>
                      <td><span className={`badge ${DUES_STATUSES[d.status] || 'bg-secondary'}`}>{d.status}</span></td>
                      <td>{d.payment_method || '--'}</td>
                      <td>
                        <div className="d-flex gap-1">
                          {d.status !== 'paid' && d.status !== 'waived' && (
                            <>
                              <button className="btn btn-sm btn-outline-success" onClick={() => { setShowPaymentModal(d.id); setPaymentForm({ amount_paid: (d.amount_due - d.amount_paid).toFixed(2), payment_method: 'cash', payment_note: '' }); }}>Pay</button>
                              <button className="btn btn-sm btn-outline-secondary" onClick={() => gardenAdminAPI.waiveDues(id, d.id).then(() => loadFinance())}>Waive</button>
                              <button className="btn btn-sm btn-outline-info" onClick={() => gardenAdminAPI.remindDues(id, d.id).then(r => showFinanceToast(r.data.message)).catch(err => showFinanceToast(err.response?.data?.error || 'Error sending reminder', 'danger'))}>Remind</button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                    {showPaymentModal === d.id && (
                      <tr><td colSpan="6" style={{ backgroundColor: '#F8F6F0' }}>
                        <div className="row g-2 p-2">
                          <div className="col-md-3">
                            <label className="form-label small fw-bold">Amount</label>
                            <input type="number" step="0.01" className="form-control form-control-sm" value={paymentForm.amount_paid} onChange={e => setPaymentForm({ ...paymentForm, amount_paid: e.target.value })} />
                          </div>
                          <div className="col-md-3">
                            <label className="form-label small fw-bold">Method</label>
                            <select className="form-select form-select-sm" value={paymentForm.payment_method} onChange={e => setPaymentForm({ ...paymentForm, payment_method: e.target.value })}>
                              {['cash', 'check', 'venmo', 'online', 'zelle', 'other'].map(m => <option key={m} value={m}>{m}</option>)}
                            </select>
                          </div>
                          <div className="col-md-4">
                            <label className="form-label small fw-bold">Note</label>
                            <input type="text" className="form-control form-control-sm" value={paymentForm.payment_note} onChange={e => setPaymentForm({ ...paymentForm, payment_note: e.target.value })} />
                          </div>
                          <div className="col-md-2 d-flex align-items-end gap-1">
                            <button className="btn btn-sm btn-success" onClick={() => handleRecordPayment(d.id)}>Save</button>
                            <button className="btn btn-sm btn-outline-secondary" onClick={() => setShowPaymentModal(null)}>Cancel</button>
                          </div>
                        </div>
                      </td></tr>
                    )}
                  </Fragment>
                ))}
                {dues.length === 0 && <tr><td colSpan="6" className="text-center text-muted py-4">No dues records. Click "Generate Dues" to create them.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {financeTab === 'expenses' && (
        <div>
          <div className="d-flex justify-content-end mb-3">
            <button className="btn" style={btnStyle} onClick={() => setShowExpenseForm(!showExpenseForm)}>
              <i className="bi bi-plus-circle me-1"></i>{showExpenseForm ? 'Cancel' : 'Log Expense'}
            </button>
          </div>
          {showExpenseForm && (
            <div className="card mb-3" style={{ backgroundColor: '#F8F6F0', border: '1px solid #D4A843' }}>
              <div className="card-body">
                <form onSubmit={handleCreateExpense}>
                  <div className="row g-3">
                    <div className="col-md-4">
                      <label className="form-label fw-semibold">Title *</label>
                      <input type="text" className="form-control" value={expenseForm.title} onChange={e => setExpenseForm({ ...expenseForm, title: e.target.value })} required />
                    </div>
                    <div className="col-md-2">
                      <label className="form-label fw-semibold">Amount *</label>
                      <input type="number" step="0.01" className="form-control" value={expenseForm.amount} onChange={e => setExpenseForm({ ...expenseForm, amount: e.target.value })} required />
                    </div>
                    <div className="col-md-3">
                      <label className="form-label fw-semibold">Category</label>
                      <select className="form-select" value={expenseForm.category} onChange={e => setExpenseForm({ ...expenseForm, category: e.target.value })}>
                        {EXPENSE_CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                      </select>
                    </div>
                    <div className="col-md-3">
                      <label className="form-label fw-semibold">Date</label>
                      <input type="date" className="form-control" value={expenseForm.expense_date} onChange={e => setExpenseForm({ ...expenseForm, expense_date: e.target.value })} />
                    </div>
                    <div className="col-md-4">
                      <label className="form-label fw-semibold">Paid By</label>
                      <input type="text" className="form-control" value={expenseForm.paid_by} onChange={e => setExpenseForm({ ...expenseForm, paid_by: e.target.value })} />
                    </div>
                    <div className="col-md-8">
                      <label className="form-label fw-semibold">Notes</label>
                      <input type="text" className="form-control" value={expenseForm.notes} onChange={e => setExpenseForm({ ...expenseForm, notes: e.target.value })} />
                    </div>
                    <div className="col-12"><button type="submit" className="btn" style={btnStyle}><i className="bi bi-check-circle me-1"></i>Log Expense</button></div>
                  </div>
                </form>
              </div>
            </div>
          )}
          <div className="table-responsive">
            <table className="table table-hover align-middle">
              <thead style={{ backgroundColor: '#F8F6F0' }}><tr><th>Date</th><th>Title</th><th>Category</th><th>Amount</th><th>Paid By</th><th>Actions</th></tr></thead>
              <tbody>
                {expenses.map(e => (
                  <tr key={e.id}>
                    <td>{e.expense_date}</td>
                    <td><strong>{e.title}</strong>{e.notes && <div className="text-muted small">{e.notes}</div>}</td>
                    <td><span className="badge bg-secondary">{e.category}</span></td>
                    <td className="fw-bold">${e.amount.toFixed(2)}</td>
                    <td>{e.paid_by || '--'}</td>
                    <td><button className="btn btn-sm btn-outline-danger" onClick={() => setConfirmDeleteExpense(e)}><i className="bi bi-trash"></i></button></td>
                  </tr>
                ))}
                {expenses.length === 0 && <tr><td colSpan="6" className="text-center text-muted py-4">No expenses logged.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {financeTab === 'summary' && financeSummary && (
        <div>
          <div className="row g-3">
            <div className="col-md-6">
              <div className="card" style={{ border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
                <div className="card-body">
                  <h6 className="fw-bold" style={headingStyle}>Dues Overview — {duesSeason}</h6>
                  <div className="d-flex justify-content-between py-1"><span>Total Members</span><span className="fw-bold">{financeSummary.dues_count}</span></div>
                  <div className="d-flex justify-content-between py-1"><span>Paid</span><span className="fw-bold text-success">{financeSummary.paid_count}</span></div>
                  <div className="d-flex justify-content-between py-1"><span>Unpaid</span><span className="fw-bold text-danger">{financeSummary.unpaid_count}</span></div>
                  <div className="progress mt-2" style={{ height: '8px' }}>
                    <div className="progress-bar bg-success" style={{ width: `${financeSummary.collection_rate}%` }}></div>
                  </div>
                  <div className="text-muted small mt-1">{financeSummary.collection_rate}% collected</div>
                </div>
              </div>
            </div>
            <div className="col-md-6">
              <div className="card" style={{ border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
                <div className="card-body">
                  <h6 className="fw-bold" style={headingStyle}>Expenses by Category</h6>
                  {Object.entries(financeSummary.by_category).length === 0 ? <p className="text-muted small">No expenses this year.</p> : (
                    Object.entries(financeSummary.by_category).map(([cat, amt]) => (
                      <div key={cat} className="d-flex justify-content-between py-1">
                        <span className="text-capitalize">{cat}</span>
                        <span className="fw-bold">${amt.toFixed(2)}</span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );

  // ==================== MEMBERS TAB ====================
  const [memberFilter, setMemberFilter] = useState('');
  const filteredMembers = membersList.filter(m => {
    if (!memberFilter) return true;
    const q = memberFilter.toLowerCase();
    return (m.name || '').toLowerCase().includes(q) || (m.email || '').toLowerCase().includes(q) || (m.role || '').toLowerCase().includes(q);
  });

  const renderMembers = () => (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h4 className="fw-bold mb-0" style={headingStyle}><i className="bi bi-person-badge me-2"></i>Members & Roles</h4>
        <button className="btn btn-outline-success btn-sm" onClick={() => window.open(gardenAdminAPI.exportMembersCSV(id), '_blank')}>
          <i className="bi bi-download me-1"></i>Export CSV
        </button>
      </div>

      <div className="mb-3">
        <div className="input-group input-group-sm" style={{ maxWidth: 300 }}>
          <span className="input-group-text"><i className="bi bi-search"></i></span>
          <input type="text" className="form-control" placeholder="Search members..." value={memberFilter} onChange={e => setMemberFilter(e.target.value)} />
        </div>
      </div>

      <div className="table-responsive">
        <table className="table table-hover align-middle">
          <thead style={{ backgroundColor: '#F8F6F0' }}><tr><th>Name</th><th>Phone</th><th>Plot</th><th>Role</th><th>Dues</th><th>Actions</th></tr></thead>
          <tbody>
            {filteredMembers.map(m => (
              <tr key={m.user_id}>
                <td>
                  <strong>{m.name}</strong>
                  <div className="text-muted" style={{ fontSize: '0.8rem' }}>{m.email}</div>
                  {m.address && <div className="text-muted" style={{ fontSize: '0.75rem' }}>{m.address}{m.city ? `, ${m.city}` : ''}{m.state ? `, ${m.state}` : ''} {m.zip_code || ''}</div>}
                </td>
                <td className="small">{m.phone_number || <span className="text-muted">—</span>}</td>
                <td className="small">
                  {m.plot_number ? (
                    <span><strong>{m.plot_number}</strong>{m.plot_custom_name ? <span className="text-muted ms-1">({m.plot_custom_name})</span> : ''}</span>
                  ) : <span className="text-muted">—</span>}
                </td>
                <td>
                  <select className="form-select form-select-sm" style={{ width: '150px' }} value={m.role}
                    onChange={e => gardenAdminAPI.changeMemberRole(id, m.user_id, { role: e.target.value }).then(() => gardenAdminAPI.members(id).then(r => setMembersList(r.data))).catch(err => alert(err.response?.data?.error || 'Error'))}
                    disabled={m.user_id === garden.organizer_id}>
                    {ROLE_OPTIONS.map(r => <option key={r} value={r}>{r.replace('_', ' ')}</option>)}
                  </select>
                </td>
                <td className="small">
                  {m.dues_status ? (
                    <span className={`badge ${m.dues_status === 'paid' ? 'bg-success' : m.dues_status === 'waived' ? 'bg-info' : 'bg-warning text-dark'}`}>
                      {m.dues_status}{m.dues_status === 'partial' ? ` ($${m.amount_paid}/$${m.amount_due})` : ''}
                    </span>
                  ) : <span className="text-muted">—</span>}
                </td>
                <td>
                  {m.user_id !== garden.organizer_id && (
                    <button className="btn btn-sm btn-outline-danger" onClick={() => {
                      if (!confirm(`Remove ${m.name}? Their plots will be released.`)) return;
                      gardenAdminAPI.removeMember(id, m.user_id).then(() => gardenAdminAPI.members(id).then(r => setMembersList(r.data))).catch(err => alert(err.response?.data?.error || 'Error'));
                    }}><i className="bi bi-person-x me-1"></i>Remove</button>
                  )}
                  {m.user_id === garden.organizer_id && <span className="badge" style={{ backgroundColor: '#2D6A4F' }}>Owner</span>}
                </td>
              </tr>
            ))}
            {filteredMembers.length === 0 && <tr><td colSpan="6" className="text-center text-muted py-4">No members found.</td></tr>}
          </tbody>
        </table>
      </div>
      <p className="text-muted small">{membersList.length} member{membersList.length !== 1 ? 's' : ''} total</p>
    </div>
  );

  // ==================== KNOWLEDGE BASE TAB ====================
  const loadArticles = () => gardensAPI.knowledge(id).then(r => setArticles(r.data)).catch(() => {});

  const handleCreateArticle = (e) => {
    e.preventDefault();
    gardenAdminAPI.createArticle(id, articleForm).then(() => {
      setShowArticleForm(false);
      setArticleForm({ title: '', body: '', category: 'general', pinned: false });
      loadArticles();
    }).catch(err => alert(err.response?.data?.error || 'Error'));
  };

  const handleUpdateArticle = (artId) => {
    gardenAdminAPI.updateArticle(id, artId, articleForm).then(() => {
      setEditingArticle(null);
      setArticleForm({ title: '', body: '', category: 'general', pinned: false });
      loadArticles();
    }).catch(err => alert(err.response?.data?.error || 'Error'));
  };

  const renderKnowledge = () => (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h4 className="fw-bold mb-0" style={headingStyle}><i className="bi bi-book me-2"></i>Knowledge Base</h4>
        <button className="btn" style={btnStyle} onClick={() => { setShowArticleForm(!showArticleForm); setEditingArticle(null); }}>
          <i className="bi bi-plus-circle me-1"></i>{showArticleForm ? 'Cancel' : 'New Article'}
        </button>
      </div>

      {(showArticleForm || editingArticle) && (
        <div className="card mb-4" style={{ backgroundColor: '#F8F6F0', border: '1px solid #D4A843' }}>
          <div className="card-body">
            <form onSubmit={editingArticle ? (e) => { e.preventDefault(); handleUpdateArticle(editingArticle); } : handleCreateArticle}>
              <div className="row g-3">
                <div className="col-md-6">
                  <label className="form-label fw-semibold">Title *</label>
                  <input type="text" className="form-control" value={articleForm.title} onChange={e => setArticleForm({ ...articleForm, title: e.target.value })} required />
                </div>
                <div className="col-md-3">
                  <label className="form-label fw-semibold">Category</label>
                  <select className="form-select" value={articleForm.category} onChange={e => setArticleForm({ ...articleForm, category: e.target.value })}>
                    {KNOWLEDGE_CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
                <div className="col-md-3 d-flex align-items-end">
                  <div className="form-check">
                    <input className="form-check-input" type="checkbox" checked={articleForm.pinned} onChange={e => setArticleForm({ ...articleForm, pinned: e.target.checked })} id="pinnedCheck" />
                    <label className="form-check-label" htmlFor="pinnedCheck">Pinned</label>
                  </div>
                </div>
                <div className="col-12">
                  <label className="form-label fw-semibold">Body *</label>
                  <textarea className="form-control" rows={5} value={articleForm.body} onChange={e => setArticleForm({ ...articleForm, body: e.target.value })} required />
                </div>
                <div className="col-12">
                  <button type="submit" className="btn" style={btnStyle}><i className="bi bi-check-circle me-1"></i>{editingArticle ? 'Update' : 'Create'} Article</button>
                  {editingArticle && <button type="button" className="btn btn-outline-secondary ms-2" onClick={() => { setEditingArticle(null); setArticleForm({ title: '', body: '', category: 'general', pinned: false }); }}>Cancel</button>}
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      {articles.map(a => (
        <div key={a.id} className="card mb-3" style={{ border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
          <div className="card-body">
            <div className="d-flex justify-content-between align-items-start">
              <div>
                <h5 className="fw-bold mb-1" style={headingStyle}>
                  {a.pinned && <i className="bi bi-pin-fill me-1" style={{ color: '#f59e0b' }}></i>}
                  {a.title}
                </h5>
                <div className="mb-2">
                  <span className="badge bg-secondary me-1">{a.category}</span>
                  <span className="text-muted small">by {a.author_name} &middot; {a.created_at && new Date(a.created_at).toLocaleDateString()}</span>
                </div>
              </div>
              <div className="d-flex gap-1">
                <button className="btn btn-sm" style={btnOutlineStyle} onClick={() => {
                  setEditingArticle(a.id);
                  setArticleForm({ title: a.title, body: a.body, category: a.category, pinned: a.pinned });
                  setShowArticleForm(false);
                }}><i className="bi bi-pencil"></i></button>
                <button className="btn btn-sm btn-outline-danger" onClick={() => {
                  if (confirm('Delete this article?')) gardenAdminAPI.deleteArticle(id, a.id).then(() => loadArticles());
                }}><i className="bi bi-trash"></i></button>
              </div>
            </div>
            <div className="mt-2" style={{ whiteSpace: 'pre-wrap' }}>{a.body}</div>
          </div>
        </div>
      ))}
      {articles.length === 0 && <p className="text-muted text-center py-4">No articles yet. Click "New Article" to share knowledge with your garden members.</p>}
    </div>
  );

  const renderContent = () => {
    switch (activeTab) {
      case 'dashboard': return renderDashboard();
      case 'plots': return renderPlots();
      case 'events': return renderEvents();
      case 'volunteers': return renderVolunteers();
      case 'finance': return renderFinance();
      case 'members': return renderMembers();
      case 'knowledge': return renderKnowledge();
      case 'messages': return renderMessages();
      case 'photos': return renderPhotos();
      case 'announcements': return renderAnnouncements();
      case 'resources': return renderResources();
      case 'communication': return renderEmail();
      case 'settings': return renderSettings();
      default: return renderDashboard();
    }
  };

  return (
    <div>
      {/* Top Banner */}
      <div style={{
        background: 'linear-gradient(135deg, #1B4D3E, #2D6A4F)',
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
            <h2 className="fw-bold mt-1 mb-0" style={{ color: 'white' }}><i className="bi bi-house-gear me-2"></i>{garden.name} <span style={{ fontWeight: 400, opacity: 0.85 }}>Admin Portal</span></h2>
          </div>
          <div className="text-end d-none d-md-block">
            <div className="small" style={{ opacity: 0.7 }}>Organizer</div>
            <div className="fw-semibold">{garden.organizer_name}</div>
          </div>
        </div>
      </div>

      {/* Sidebar + Content Layout */}
      <div className="d-flex garden-admin-layout" style={{ gap: '0', minHeight: '600px' }}>
        {/* Sidebar */}
        <div className="garden-admin-sidebar" style={{
          width: '220px',
          flexShrink: 0,
          backgroundColor: '#F8F6F0',
          borderRight: '3px solid #D4A843',
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
                  backgroundColor: activeTab === tab.key ? '#1B4D3E' : 'transparent',
                  color: activeTab === tab.key ? 'white' : '#1B4D3E',
                  borderLeft: activeTab === tab.key ? '4px solid #D4A843' : '4px solid transparent',
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
        <div className="garden-admin-content" style={{ flex: 1, padding: '24px', backgroundColor: '#fff', borderRadius: '0 12px 12px 0', border: '1px solid #C8E6D4', borderLeft: 'none' }}>
          {renderContent()}
        </div>
      </div>
    </div>
  );
}
