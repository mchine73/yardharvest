import { useState, useEffect, useRef, Fragment } from 'react';
import { useParams, Link, useNavigate, useSearchParams } from 'react-router-dom';
import { gardensAPI, gardenAdminAPI, gardenBillingAPI } from '../../api';
import { useAuth } from '../../AuthContext';
import PhotoLibrary from '../../components/PhotoLibrary';
import PhotoUploadInput from '../../components/PhotoUploadInput';
import QRScanner from '../../components/QRScanner';
import { toast, confirmDialog, promptDialog } from '../../components/dialog/dialogService';
import { trackEvent } from '../../hooks/useTracking';
import { useSubmit } from '../../hooks/useSubmit';
import GardenLayoutEditor from '../../components/GardenLayoutEditor';
import GardenSetupChecklist from '../../components/GardenSetupChecklist';
import GardenFunderReport from '../../components/GardenFunderReport';
import { gardenHasPro } from '../../pro';

// Status chips: pale background + dark text — one semantic system across
// plots, the wall, and dues (positive = lime, pending = gold, denied = red).
const CHIP_LIME = { backgroundColor: 'var(--yh-lime-soft)', color: 'var(--yh-lime-text)' };
const CHIP_GOLD = { backgroundColor: '#fdf1dc', color: '#8a5a00' };
const CHIP_RED = { backgroundColor: '#fde2e1', color: '#b42318' };
const CHIP_GRAY = { backgroundColor: '#ececec', color: '#5a5e66' };
const CHIP_BLUE = { backgroundColor: '#e8f0fd', color: '#3567b2' };

const PLOT_STATUS_COLORS = {
  available: CHIP_LIME,
  assigned: CHIP_BLUE,
  reserved: CHIP_GOLD,
  maintenance: CHIP_GRAY,
};

const PHOTO_CATEGORIES = ['all', 'harvest', 'plot', 'event', 'wildlife', 'bloom'];

const PRIORITY_STYLES = {
  normal: { bg: 'bg-primary', color: '#3f7ddb' },
  important: { bg: 'bg-warning', color: 'var(--brand-gold)' },
  urgent: { bg: 'bg-danger', color: '#e0564f' },
};

const RESOURCE_CONDITION_COLORS = {
  new: 'var(--brand-accent)',
  good: '#3f7ddb',
  fair: 'var(--brand-gold)',
  needs_repair: '#e0564f',
};

// Ordered for adjacency: garden operations, then people & communication,
// then money, then configuration. `section` starts a labeled group on the
// desktop sidebar (the mobile strip renders flat; the order still carries).
const SIDEBAR_TABS = [
  { key: 'dashboard', label: 'Dashboard', icon: 'bi-speedometer2' },
  { key: 'plots', label: 'Plots', icon: 'bi-grid-3x3-gap', section: 'Garden' },
  { key: 'events', label: 'Events', icon: 'bi-calendar-event' },
  { key: 'volunteers', label: 'Volunteers', icon: 'bi-people' },
  { key: 'resources', label: 'Resources', icon: 'bi-tools' },
  { key: 'members', label: 'Members', icon: 'bi-person-badge', section: 'Community' },
  { key: 'messages', label: 'Messages', icon: 'bi-envelope', pro: true },
  { key: 'announcements', label: 'Announcements', icon: 'bi-megaphone' },
  { key: 'community_wall', label: 'Community Wall', icon: 'bi-chat-square-text' },
  { key: 'photos', label: 'Photos', icon: 'bi-camera', pro: true },
  { key: 'finance', label: 'Finance', icon: 'bi-cash-stack', pro: true, section: 'Money' },
  { key: 'reports', label: 'Funder Reports', icon: 'bi-file-earmark-bar-graph', pro: true },
  { key: 'communication', label: 'Announcement Emails', icon: 'bi-envelope-gear', pro: true, section: 'Setup' },
  { key: 'settings', label: 'Settings', icon: 'bi-gear' },
];

const EXPENSE_CATEGORIES = ['supplies', 'infrastructure', 'water', 'seeds', 'tools', 'other'];
// Ownership is not assignable from here — it follows the garden and moves via
// a support-assisted transfer. Offering it created a membership row labelled
// organizer that granted nothing.
const ROLE_OPTIONS = ['co_organizer', 'treasurer', 'volunteer_lead', 'member'];
const DUES_STATUSES = { unpaid: 'bg-danger', partial: 'bg-warning text-dark', paid: 'bg-success', waived: 'bg-secondary', comp: 'bg-info' };
const DUES_STATUS_HELP = {
  unpaid: 'No payment recorded yet',
  partial: 'Partially paid',
  paid: 'Paid in full',
  waived: 'Dues forgiven by an organizer for this season',
  comp: 'Complimentary — no dues owed',
};

// Which capability each tab needs. Mirrors app/garden_permissions.py — the
// server is the authority, this only decides what to render, so a mismatch
// shows a tab that 403s rather than granting anything.
const TAB_CAPABILITY = {
  dashboard: 'view', plots: 'garden', events: 'events', volunteers: 'shifts',
  resources: 'resources', members: 'people', messages: 'content',
  announcements: 'content', community_wall: 'content', photos: 'content',
  finance: 'money', reports: 'reports', communication: 'content',
  settings: 'garden',
};

const VALID_TABS = new Set(SIDEBAR_TABS.map(t => t.key));
const FINANCE_SUBTABS = ['summary', 'dues', 'expenses', 'stripe'];
// Ledger kinds from app/garden_finance.py. The row's sentence comes from the
// server (`label`) so the phrasing matches the iOS app and the notifications;
// only the badge is client-side.
const STRIPE_EVENT_LABELS = {
  payment: 'Paid', payment_failed: 'Declined', refund: 'Refund',
  dispute: 'Chargeback', payout: 'Deposit', account: 'Account',
};
const STRIPE_EVENT_BADGES = {
  payment: 'bg-success', payment_failed: 'bg-secondary', refund: 'bg-danger',
  dispute: 'bg-danger', payout: 'bg-primary', account: 'bg-warning text-dark',
};
// "after fees and refunds" is a lie when neither applies — and it reads as a
// deduction that silently isn't happening. Say which of the two is in play.
const keptHint = (t) => {
  // While any payment's Stripe fee is unknown this is an upper bound, and
  // saying so beats a number that is quietly short by Stripe's cut.
  if (!t.fees_complete) return 'at most — some Stripe fees unknown';
  const parts = [];
  if (t.fees > 0) parts.push('platform');
  if (t.stripe_fees > 0) parts.push('Stripe');
  if (t.refunded > 0) parts.push('refunds');
  if (!parts.length) return 'no fees deducted';
  return `after ${parts.join(' + ')}`;
};
// Money actually leaving the garden — drawn red and signed.
const STRIPE_OUTGOING = (e) => e.kind === 'refund'
  || (e.kind === 'dispute' && e.status !== 'won');
// A declined charge and a failed payout name an amount that never moved;
// muting them keeps the Amount column readable as "what I have".
const stripeAmountClass = (e) => {
  if (STRIPE_OUTGOING(e)) return 'text-danger';
  if (e.kind === 'payment_failed' || (e.kind === 'payout' && e.status !== 'paid')) {
    return 'text-muted fw-normal';
  }
  return '';
};

// Local-clock date string. The backend serializes naive local datetimes, so
// prefer this over toISOString() (UTC) when prefilling date inputs — mixing
// the two shifts evening events to the next day.
const toLocalISODate = (d) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

export default function GardenAdminDashboard() {
  const { id, tab } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { pending: sending, run: runSend } = useSubmit();
  // One hook per form: `pending` is per-instance, so each submit button gets
  // its own double-submit guard + disabled state.
  const { pending: savingEvent, run: runEvent } = useSubmit();
  const { pending: savingShift, run: runShift } = useSubmit();
  const { pending: savingAnn, run: runAnn } = useSubmit();
  const { pending: savingResource, run: runResource } = useSubmit();
  const { pending: savingExpense, run: runExpense } = useSubmit();
  const { pending: savingPlot, run: runPlot } = useSubmit();
  const { pending: savingCheckout, run: runCheckout } = useSubmit();
  const { pending: savingSettings, run: runSettings } = useSubmit();
  const [financeSubmitting, setFinanceSubmitting] = useState(false);

  const [garden, setGarden] = useState(null);
  const [payouts, setPayouts] = useState(null);
  const [loading, setLoading] = useState(true);
  // The active tab lives in the URL (/gardens/:id/admin/:tab) so refresh,
  // back/forward, and shared links keep the organizer's place.
  const [activeTab, setActiveTab] = useState(() => (VALID_TABS.has(tab) ? tab : 'dashboard'));
  const goToTab = async (key) => {
    // A drawn-but-unsaved Garden Designer layout dies with the plots tab —
    // unmounting the editor discards it silently without this gate.
    if (layoutDirty && activeTab === 'plots' && key !== 'plots') {
      if (!(await confirmDialog('Leave this tab? Your unsaved layout changes in the Garden Designer will be discarded.', { danger: true, title: 'Unsaved layout', confirmText: 'Discard changes' }))) return;
      setLayoutDirty(false);
    }
    navigate(`/gardens/${id}/admin/${key}`);
  };
  const tabRefs = useRef({});

  // Each tab's primary fetch is tracked so the UI can tell loading, load
  // failure, and Pro-gating apart from a genuinely empty garden — a failed
  // fetch must never render terminal "No X yet." copy.
  const [tabStatus, setTabStatus] = useState({});
  const [reloadNonce, setReloadNonce] = useState(0);
  const trackTab = (key, promise) => {
    setTabStatus(s => ({ ...s, [key]: 'loading' }));
    promise
      .then(() => setTabStatus(s => ({ ...s, [key]: 'ready' })))
      .catch(err => {
        const pro = err?.response?.status === 403 && err?.response?.data?.upgrade_url;
        setTabStatus(s => ({ ...s, [key]: pro ? 'pro' : 'error' }));
      });
  };

  // On the phone the tabs render as a horizontal strip — keep the active one
  // visible whether it was tapped or reached via a quick action / deep link.
  // `loading` is a dep because on first render only the spinner exists; the
  // tab buttons (and their refs) appear after the garden loads.
  useEffect(() => {
    if (loading) return;
    tabRefs.current[activeTab]?.scrollIntoView({ inline: 'center', block: 'nearest' });
  }, [activeTab, loading]);

  // Dashboard
  const [stats, setStats] = useState(null);
  const [activity, setActivity] = useState([]);

  // Plots
  const [plots, setPlots] = useState([]);
  const [waitlist, setWaitlist] = useState([]);
  const [editingPlot, setEditingPlot] = useState(null);
  const [plotForm, setPlotForm] = useState({ size: '', location_notes: '', renewal_date: '' });
  const [assigningPlot, setAssigningPlot] = useState(null);   // plot id with the assign-member select open
  const [assignUserId, setAssignUserId] = useState('');
  const [waitlistPlotPick, setWaitlistPlotPick] = useState({}); // waitlist id -> picked plot id (controlled, resets on cancel/error)

  // Garden Designer: unsaved-changes flag reported up by GardenLayoutEditor
  // so tab switches and page closes can warn before discarding a layout.
  const [layoutDirty, setLayoutDirty] = useState(false);

  // Events
  const [events, setEvents] = useState([]);
  const [showEventForm, setShowEventForm] = useState(false);
  const [editingEvent, setEditingEvent] = useState(null);
  const [eventForm, setEventForm] = useState({ title: '', description: '', event_type: 'workday', event_date: '', event_time: '09:00', duration_hours: 2, max_volunteers: '', recurring: 'none' });
  const [attendeesEvent, setAttendeesEvent] = useState(null);
  const [attendees, setAttendees] = useState([]);

  // Messages
  const [messages, setMessages] = useState([]);
  const [plotOwners, setPlotOwners] = useState([]);
  const [msgForm, setMsgForm] = useState({ recipient_id: '', subject: '', body: '', channels: ['platform'] });
  const [showBroadcast, setShowBroadcast] = useState(false);
  const [broadcastForm, setBroadcastForm] = useState({ subject: '', body: '' });
  const [editingMsg, setEditingMsg] = useState(null); // message id being edited
  const [editMsgForm, setEditMsgForm] = useState({ subject: '', body: '' });

  // Community wall moderation
  const [wallComments, setWallComments] = useState([]);
  const [wallFlaggedCount, setWallFlaggedCount] = useState(0);
  const [wallBlockedCount, setWallBlockedCount] = useState(0);
  const [wallFilter, setWallFilter] = useState('all');

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
  const [qrResource, setQrResource] = useState(null); // resource whose QR label is open
  const [editResource, setEditResource] = useState(null); // resource being edited
  const [editResForm, setEditResForm] = useState({ name: '', resource_type: 'tool', description: '', quantity: 1, condition: 'good' });
  const [checkoutForRes, setCheckoutForRes] = useState(null); // resource being lent to a member
  const [checkoutForForm, setCheckoutForForm] = useState({ user_id: '', duration_days: 3 });
  const [resMembers, setResMembers] = useState([]); // member picker options

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
  const [volunteerReportPro, setVolunteerReportPro] = useState(false);

  // Finance
  const [financeTab, setFinanceTab] = useState(() => {
    const sub = searchParams.get('sub');
    return FINANCE_SUBTABS.includes(sub) ? sub : 'summary';
  });
  const goToFinanceTab = (sub) => {
    setFinanceTab(sub);
    setSearchParams(sub === 'summary' ? {} : { sub }, { replace: true });
  };
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
  const [confirmDeleteExpense, setConfirmDeleteExpense] = useState(null);
  const [financeError, setFinanceError] = useState('');
  // Stripe money feed. Loaded only when its sub-tab is open — it is a
  // different question ("what did Stripe do") from the dues roster, and most
  // visits to Finance never ask it.
  const [stripeFeed, setStripeFeed] = useState(null);
  const [stripePayouts, setStripePayouts] = useState(null);
  const [stripeLoading, setStripeLoading] = useState(false);
  const [stripeWindow, setStripeWindow] = useState(90);

  // Members & Roles
  const [membersList, setMembersList] = useState([]);
  const [memberFilter, setMemberFilter] = useState('');

  // Knowledge Base

  // Weather
  const [weatherData, setWeatherData] = useState(null);

  useEffect(() => {
    gardensAPI.detail(id).then(res => {
      setGarden(res.data);
      setLoading(false);
    }).catch(() => setLoading(false));
    gardenBillingAPI.payoutStatus(id)
      .then(r => setPayouts(r.data))
      .catch(() => { /* non-critical: banner just won't show */ });
    // Stats load on mount (not just on the dashboard tab) so the sidebar's
    // attention badges are populated wherever the organizer lands.
    gardenAdminAPI.dashboard(id).then(r => setStats(r.data)).catch(() => {});
  }, [id]);

  // Keep tab state following the URL so back/forward and in-app links work.
  useEffect(() => {
    const next = VALID_TABS.has(tab) ? tab : 'dashboard';
    setActiveTab(prev => (prev === next ? prev : next));
  }, [tab]);
  useEffect(() => {
    const sub = searchParams.get('sub');
    const next = FINANCE_SUBTABS.includes(sub) ? sub : 'summary';
    setFinanceTab(prev => (prev === next ? prev : next));
  }, [searchParams]);

  // Capabilities come from the API (garden_permissions.py), so a co-organizer,
  // treasurer or volunteer lead reaches the portal and sees their own tabs.
  // is_admin keeps the platform operator in for support.
  const capabilities = new Set(garden?.user_capabilities || []);
  const can = (cap) => user?.is_admin || capabilities.has(cap);
  const visibleTabs = SIDEBAR_TABS.filter(t => can(TAB_CAPABILITY[t.key]));
  // Landing on a tab you cannot use (a bookmark, or a role change) shows the
  // dashboard. Derived above the loading effect on purpose: fetching a tab
  // you have no permission for turns a 403 into "check your connection".
  const effectiveTab = can(TAB_CAPABILITY[activeTab]) ? activeTab : 'dashboard';

  useEffect(() => {
    if (!garden) return;
    if (effectiveTab === 'dashboard') {
      gardenAdminAPI.dashboard(id).then(r => setStats(r.data)).catch(() => {});
      gardenAdminAPI.activity(id).then(r => setActivity(r.data.activities || r.data || [])).catch(() => {});
    }
    if (effectiveTab === 'plots') {
      trackTab('plots', Promise.all([
        gardenAdminAPI.plots(id).then(r => setPlots(r.data.plots || r.data || [])),
        gardensAPI.viewWaitlist(id).then(r => setWaitlist(r.data.waitlist || r.data || [])),
      ]));
      // For the assign-to-member control on available plots.
      gardenAdminAPI.members(id).then(r => setMembersList(r.data)).catch(() => {});
    }
    if (effectiveTab === 'events') {
      trackTab('events', gardensAPI.events(id, { show: 'all' }).then(r => setEvents(r.data)));
    }
    if (effectiveTab === 'messages') {
      trackTab('messages', gardenAdminAPI.messages(id).then(r => setMessages(r.data.messages || r.data || [])));
      Promise.all([
        gardenAdminAPI.plots(id).catch(() => ({ data: [] })),
        gardenAdminAPI.members(id).catch(() => ({ data: [] })),
      ]).then(([plotsRes, membersRes]) => {
        // Label hint: which plot (if any) each member holds.
        const plotByUser = {};
        (plotsRes.data.plots || plotsRes.data || []).forEach(p => {
          if (p.assigned_to_id) plotByUser[p.assigned_to_id] = p.plot_number;
        });
        // Recipients = every garden member (not just plot holders) so a manager
        // can message anyone. The members endpoint carries email + phone.
        const recipients = (membersRes.data.members || membersRes.data || []).map(m => ({
          id: m.user_id,
          name: plotByUser[m.user_id] ? `${m.name} (Plot ${plotByUser[m.user_id]})` : m.name,
          email: m.email || '',
          phone: m.phone_number || '',
        }));
        const unique = recipients.filter((v, i, a) => a.findIndex(t => t.id === v.id) === i);
        setPlotOwners(unique);
      }).catch(() => {});
    }
    if (effectiveTab === 'photos') {
      const params = photoFilter !== 'all' ? { category: photoFilter } : {};
      trackTab('photos', gardenAdminAPI.photos(id, params).then(r => setPhotos(r.data.photos || r.data || [])));
    }
    if (effectiveTab === 'community_wall') {
      const params = wallFilter !== 'all' ? { status: wallFilter } : {};
      trackTab('community_wall', gardenAdminAPI.comments(id, params).then(r => {
        setWallComments(r.data.comments || []);
        setWallFlaggedCount(r.data.flagged_count || 0);
        setWallBlockedCount(r.data.blocked_count || 0);
      }));
    }
    if (effectiveTab === 'announcements') {
      trackTab('announcements', gardenAdminAPI.announcements(id).then(r => setAnnouncements(r.data.announcements || r.data || [])));
    }
    if (effectiveTab === 'resources') {
      trackTab('resources', gardensAPI.resources(id).then(r => setResources(r.data)));
    }
    if (effectiveTab === 'communication') {
      // Tracking this kills the former infinite spinner on free gardens: the
      // 403 now renders the Pro panel instead of emailConfig staying null.
      trackTab('communication', gardenAdminAPI.getEmailConfig(id).then(r => setEmailConfig(r.data)));
    }
    if (effectiveTab === 'volunteers') {
      // The shift list is free; only the hours leaderboard is Pro, so it
      // must not gate the whole tab.
      trackTab('volunteers', gardensAPI.shifts(id, { show: 'all' }).then(r => setShifts(r.data)));
      gardenAdminAPI.volunteerReport(id)
        .then(r => { setVolunteerReport(r.data); setVolunteerReportPro(false); })
        .catch(err => {
          if (err?.response?.status === 403 && err?.response?.data?.upgrade_url) setVolunteerReportPro(true);
        });
    }
    if (effectiveTab === 'finance') {
      trackTab('finance', Promise.all([
        gardenAdminAPI.financeSummary(id, { season_year: duesSeason }).then(r => setFinanceSummary(r.data)),
        gardenAdminAPI.dues(id, { season_year: duesSeason }).then(r => setDues(r.data)),
        gardenAdminAPI.expenses(id, { year: duesSeason }).then(r => setExpenses(r.data)),
      ]));
    }
    if (effectiveTab === 'members') {
      trackTab('members', gardenAdminAPI.members(id).then(r => setMembersList(r.data)));
    }
    if (effectiveTab === 'dashboard') {
      gardenAdminAPI.weather(id).then(r => setWeatherData(r.data)).catch(() => {});
    }
    if (effectiveTab === 'settings') {
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
  }, [effectiveTab, garden, id, photoFilter, duesSeason, wallFilter, reloadNonce]);

  // A drawn-but-unsaved layout must survive an accidental page close.
  useEffect(() => {
    if (!layoutDirty) return;
    const onBeforeUnload = (e) => { e.preventDefault(); e.returnValue = ''; };
    window.addEventListener('beforeunload', onBeforeUnload);
    return () => window.removeEventListener('beforeunload', onBeforeUnload);
  }, [layoutDirty]);

  // Stripe money feed. Declared up here with the other hooks — the early
  // returns below (loading / not-found / not-authorized) would otherwise make
  // this effect conditional and break the hook order.
  const loadStripeMoney = () => {
    setStripeLoading(true);
    Promise.all([
      gardenAdminAPI.financeActivity(id, { days: stripeWindow, limit: 100 })
        .then(r => setStripeFeed(r.data)),
      gardenAdminAPI.financePayouts(id, { days: stripeWindow })
        .then(r => setStripePayouts(r.data)),
    ]).catch(() => { /* the panel renders its own empty state */ })
      .finally(() => setStripeLoading(false));
  };

  useEffect(() => {
    if (effectiveTab === 'finance' && financeTab === 'stripe') loadStripeMoney();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [effectiveTab, financeTab, id, stripeWindow]);

  if (loading) return <div className="text-center py-5"><div className="spinner-border" style={{ color: 'var(--brand-primary)' }}></div></div>;
  if (!garden) return <div className="text-center py-5"><p>Garden not found.</p><Link to="/gardens">Back to Gardens</Link></div>;
  // Site admins pass too: the backend already authorizes them on every
  // garden-admin endpoint (require_garden_admin), so this front-door check
  // was the only thing locking the platform operator out of the organizer
  // view during a garden review. Pro-locked tabs on free gardens still show
  // locked — expected, not a bug.

  if (!user || !can('view')) {
    return (
      <div className="text-center py-5">
        <i className="bi bi-shield-lock" style={{ fontSize: '3rem', color: 'var(--brand-primary)' }}></i>
        <h4 className="mt-3" style={{ color: 'var(--brand-primary)' }}>Not authorized.</h4>
        <p className="text-muted">You need an organizer, co-organizer, treasurer or volunteer-lead role in this garden to open its admin portal.</p>
        <Link to={`/gardens/${id}`} className="btn" style={{ backgroundColor: 'var(--brand-secondary)', color: 'white' }}>Back to Garden</Link>
      </div>
    );
  }

  // ==================== HANDLERS ====================

  const handleUpdatePlot = (plotId) => {
    runPlot(() => gardenAdminAPI.updatePlot(id, plotId, plotForm), { success: 'Plot updated', error: 'Could not update the plot.' }).then(({ ok }) => {
      if (!ok) return;
      setEditingPlot(null);
      gardenAdminAPI.plots(id).then(r => setPlots(r.data.plots || r.data || []));
    });
  };

  const handleToggleMaintenance = (plotId) => {
    gardenAdminAPI.toggleMaintenance(id, plotId).then(() => {
      toast('Maintenance status updated', { type: 'success' });
      gardenAdminAPI.plots(id).then(r => setPlots(r.data.plots || r.data || []));
    }).catch(err => toast(err.response?.data?.error || 'Error', { type: 'error' }));
  };

  const handleReleasePlot = async (plotId) => {
    if (!(await confirmDialog('Release this plot? The assigned member will lose their plot.', { danger: true, title: 'Release plot', confirmText: 'Release' }))) return;
    gardensAPI.releasePlot(id, plotId).then(() => {
      toast('Plot released — it is available again', { type: 'success' });
      gardenAdminAPI.plots(id).then(r => setPlots(r.data.plots || r.data || []));
    }).catch(err => toast(err.response?.data?.error || 'Error', { type: 'error' }));
  };

  const handleAssignPlot = (plotId, userId, opts = {}) => {
    gardensAPI.assignPlot(id, plotId, { user_id: userId }).then(() => {
      if (opts.successMsg) toast(opts.successMsg, { type: 'success' });
      setAssigningPlot(null);
      setAssignUserId('');
      gardenAdminAPI.plots(id).then(r => setPlots(r.data.plots || r.data || []));
      gardensAPI.viewWaitlist(id).then(r => setWaitlist(r.data.waitlist || r.data || []));
    }).catch(err => toast(err.response?.data?.error || 'Error', { type: 'error' }));
  };

  const handleAssignToMember = async (plot) => {
    const member = membersList.find(m => String(m.user_id) === String(assignUserId));
    if (!member) return;
    const label = plot.custom_name || `Plot #${plot.plot_number}`;
    if (!(await confirmDialog(`Assign ${label} to ${member.name}? They'll be notified.`))) return;
    handleAssignPlot(plot.id, member.user_id, { successMsg: `${label} assigned to ${member.name}` });
  };

  const handleConfirmReservation = (plotId) => {
    gardenAdminAPI.confirmReservation(id, plotId).then(() => {
      trackEvent('plot_confirmed', { garden_id: id, plot_id: plotId });
      toast('Reservation confirmed — the member has their plot', { type: 'success' });
      gardenAdminAPI.plots(id).then(r => setPlots(r.data.plots || r.data || []));
      gardensAPI.viewWaitlist(id).then(r => setWaitlist(r.data.waitlist || r.data || []));
    }).catch(err => toast(err.response?.data?.error || 'Error confirming reservation', { type: 'error' }));
  };

  const handleDeclineReservation = async (plotId) => {
    if (!(await confirmDialog('Decline this reservation? The plot will become available again.', { danger: true, title: 'Decline reservation', confirmText: 'Decline' }))) return;
    gardenAdminAPI.declineReservation(id, plotId).then(() => {
      toast('Reservation declined — the plot is available again', { type: 'success' });
      gardenAdminAPI.plots(id).then(r => setPlots(r.data.plots || r.data || []));
    }).catch(err => toast(err.response?.data?.error || 'Error declining reservation', { type: 'error' }));
  };

  const handleApproveWaitlist = (wlId, plotId, opts = {}) => {
    gardenAdminAPI.approveWaitlist(id, wlId, { plot_id: plotId }).then(() => {
      if (opts.name) toast(`Plot #${opts.plotLabel} assigned to ${opts.name}`, { type: 'success' });
      setWaitlistPlotPick(s => ({ ...s, [wlId]: '' }));
      gardenAdminAPI.plots(id).then(r => setPlots(r.data.plots || r.data || []));
      gardensAPI.viewWaitlist(id).then(r => setWaitlist(r.data.waitlist || r.data || []));
    }).catch(err => {
      // Reset the row's select so the same plot can be retried after a failure.
      setWaitlistPlotPick(s => ({ ...s, [wlId]: '' }));
      toast(err.response?.data?.error || 'Error approving', { type: 'error' });
    });
  };

  const handleDeclineWaitlist = async (wlId) => {
    if (!(await confirmDialog('Decline this waitlist entry?', { danger: true, title: 'Decline waitlist entry', confirmText: 'Decline' }))) return;
    gardenAdminAPI.declineWaitlist(id, wlId).then(() => {
      gardensAPI.viewWaitlist(id).then(r => setWaitlist(r.data.waitlist || r.data || []));
    }).catch(err => toast(err.response?.data?.error || 'Error declining', { type: 'error' }));
  };

  const handleCreateEvent = (e) => {
    e.preventDefault();
    const datetime = `${eventForm.event_date}T${eventForm.event_time}`;
    const data = { ...eventForm, event_date: datetime, max_volunteers: eventForm.max_volunteers ? parseInt(eventForm.max_volunteers) : null, duration_hours: parseFloat(eventForm.duration_hours) };
    delete data.event_time;
    // Guarded: a recurring create fans out to 9 events — a double-tap must not double it.
    runEvent(() => gardensAPI.createEvent(id, data), { success: 'Event created', error: 'Could not create the event.' }).then(({ ok }) => {
      if (!ok) return;
      setShowEventForm(false);
      setEventForm({ title: '', description: '', event_type: 'workday', event_date: '', event_time: '09:00', duration_hours: 2, max_volunteers: '', recurring: 'none' });
      gardensAPI.events(id, { show: 'all' }).then(r => setEvents(r.data));
    });
  };

  const handleUpdateEvent = (eventId) => {
    const datetime = `${eventForm.event_date}T${eventForm.event_time}`;
    const data = { ...eventForm, event_date: datetime, max_volunteers: eventForm.max_volunteers ? parseInt(eventForm.max_volunteers) : null, duration_hours: parseFloat(eventForm.duration_hours) };
    delete data.event_time;
    runEvent(() => gardenAdminAPI.updateEvent(id, eventId, data), { success: 'Event updated', error: 'Could not update the event.' }).then(({ ok }) => {
      if (!ok) return;
      setEditingEvent(null);
      setEventForm({ title: '', description: '', event_type: 'workday', event_date: '', event_time: '09:00', duration_hours: 2, max_volunteers: '', recurring: 'none' });
      gardensAPI.events(id, { show: 'all' }).then(r => setEvents(r.data));
    });
  };

  const handleDeleteEvent = async (eventId) => {
    if (!(await confirmDialog('Delete this event?', { danger: true, title: 'Delete event', confirmText: 'Delete' }))) return;
    gardenAdminAPI.deleteEvent(id, eventId).then(() => {
      toast('Event deleted', { type: 'success' });
      gardensAPI.events(id, { show: 'all' }).then(r => setEvents(r.data));
    }).catch(err => toast(err.response?.data?.error || 'Error', { type: 'error' }));
  };

  const handleViewAttendees = (eventId) => {
    if (attendeesEvent === eventId) { setAttendeesEvent(null); return; }
    setAttendeesEvent(eventId);
    gardenAdminAPI.eventAttendees(id, eventId).then(r => setAttendees(r.data.attendees || r.data || [])).catch(() => setAttendees([]));
  };

  const handleSendMessage = (e) => {
    e.preventDefault();
    if (!msgForm.channels || msgForm.channels.length === 0) {
      toast('Select at least one delivery method', { type: 'error' });
      return;
    }
    runSend(() => gardenAdminAPI.sendMessage(id, msgForm), {
      error: 'Could not send the message — please try again.',
    }).then(({ ok, data }) => {
      if (!ok) return;
      setMsgForm({ recipient_id: '', subject: '', body: '', channels: ['platform'] });
      gardenAdminAPI.messages(id).then(r => setMessages(r.data.messages || r.data || []));
      const via = data?.data?.delivered_via;
      toast(via && via.length ? `Message sent via ${via.join(', ')}` : 'Message sent', { type: 'success' });
    });
  };

  const toggleMsgChannel = (ch) => {
    setMsgForm(f => {
      const has = f.channels.includes(ch);
      const channels = has ? f.channels.filter(c => c !== ch) : [...f.channels, ch];
      return { ...f, channels };
    });
  };

  const handleEditMessage = (e) => {
    e.preventDefault();
    gardenAdminAPI.editMessage(id, editingMsg, editMsgForm).then(() => {
      setEditingMsg(null);
      gardenAdminAPI.messages(id).then(r => setMessages(r.data.messages || r.data || []));
      toast('Message updated', { type: 'success' });
    }).catch(err => toast(err.response?.data?.error || 'Error', { type: 'error' }));
  };

  const handleDeleteMessage = async (msgId) => {
    if (!(await confirmDialog('Delete this message?', { danger: true, title: 'Delete message', confirmText: 'Delete' }))) return;
    gardenAdminAPI.deleteMessage(id, msgId).then(() => {
      setMessages(msgs => msgs.filter(m => m.id !== msgId));
      toast('Message deleted', { type: 'success' });
    }).catch(err => toast(err.response?.data?.error || 'Error', { type: 'error' }));
  };

  // Role changes fire from a dropdown — an accidental tap must not silently
  // hand out (or revoke) garden powers.
  const ROLE_POWERS = {
    co_organizer: 'They will be able to run the garden — plots, members, events, shifts, resources, dues and reports. They will NOT be able to change roles, billing, or where payouts go.',
    treasurer: 'They will be able to manage dues, expenses and reports. No access to plots, members or settings.',
    volunteer_lead: 'They will be able to manage events and volunteer shifts. No access to money or members.',
    member: 'They will lose all administrative access to this garden.',
  };
  const handleChangeRole = async (m, role) => {
    if (role === m.role) return;
    if (!(await confirmDialog(`Make ${m.name} a ${role.replace('_', ' ')}? ${ROLE_POWERS[role] || ''}`))) return;
    gardenAdminAPI.changeMemberRole(id, m.user_id, { role })
      .then(() => {
        toast(`${m.name} is now a ${role.replace('_', ' ')}`, { type: 'success' });
        gardenAdminAPI.members(id).then(r => setMembersList(r.data));
      })
      .catch(err => toast(err.response?.data?.error || 'Error', { type: 'error' }));
  };

  const copyInviteLink = async () => {
    const inviteUrl = `${window.location.origin}/gardens/${garden?.public_id || id}`;
    try {
      await navigator.clipboard.writeText(inviteUrl);
      toast('Invite link copied — share it with your gardeners.', { type: 'success' });
    } catch {
      toast(inviteUrl, { type: 'info' });
    }
  };

  const reloadWall = () => {
    const params = wallFilter !== 'all' ? { status: wallFilter } : {};
    gardenAdminAPI.comments(id, params).then(r => {
      setWallComments(r.data.comments || []);
      setWallFlaggedCount(r.data.flagged_count || 0);
      setWallBlockedCount(r.data.blocked_count || 0);
    }).catch(() => {});
  };

  const handleApproveComment = (commentId) => {
    gardenAdminAPI.approveComment(id, commentId).then(() => {
      reloadWall();
      toast('Comment approved', { type: 'success' });
    }).catch(err => toast(err.response?.data?.error || 'Error', { type: 'error' }));
  };

  const handleRemoveComment = async (commentId) => {
    const ok = await confirmDialog('Remove this comment from the community wall? This cannot be undone.', { title: 'Remove comment', confirmText: 'Remove', danger: true });
    if (!ok) return;
    gardenAdminAPI.deleteComment(id, commentId).then(() => {
      setWallComments(cs => cs.filter(c => c.id !== commentId));
      setWallFlaggedCount(c => Math.max(0, c - (wallComments.find(x => x.id === commentId)?.status === 'flagged' ? 1 : 0)));
      toast('Comment removed', { type: 'success' });
    }).catch(err => toast(err.response?.data?.error || 'Error', { type: 'error' }));
  };

  const handleBroadcast = (e) => {
    e.preventDefault();
    runSend(() => gardenAdminAPI.broadcastMessage(id, broadcastForm), {
      error: 'Could not post the broadcast — please try again.',
    }).then(({ ok, data }) => {
      if (!ok) return;
      setShowBroadcast(false);
      setBroadcastForm({ subject: '', body: '' });
      gardenAdminAPI.messages(id).then(r => setMessages(r.data.messages || r.data || []));
      const n = data?.data?.recipients_count;
      toast(n != null ? `Posted to ${n} plot holder${n === 1 ? '' : 's'}` : 'Broadcast posted', { type: 'success' });
    });
  };

  const handlePostPhoto = (e) => {
    e.preventDefault();
    gardenAdminAPI.postPhoto(id, photoForm).then(() => {
      setShowPhotoForm(false);
      setPhotoForm({ photo_url: '', caption: '', category: 'harvest' });
      gardenAdminAPI.photos(id, photoFilter !== 'all' ? { category: photoFilter } : {}).then(r => setPhotos(r.data.photos || r.data || []));
    }).catch(err => toast(err.response?.data?.error || 'Error', { type: 'error' }));
  };

  const handleDeletePhoto = async (photoId) => {
    if (!(await confirmDialog('Delete this photo?', { danger: true, title: 'Delete photo', confirmText: 'Delete' }))) return;
    gardenAdminAPI.deletePhoto(id, photoId).then(() => {
      setPhotos(prev => prev.filter(p => p.id !== photoId));
    }).catch(err => toast(err.response?.data?.error || 'Error', { type: 'error' }));
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
    }).catch(err => toast(err.response?.data?.error || 'Error', { type: 'error' }));
  };

  const handleCreateAnnouncement = (e) => {
    e.preventDefault();
    runAnn(() => gardenAdminAPI.createAnnouncement(id, annForm), { success: 'Announcement posted — assigned plot holders are being notified', error: 'Could not post the announcement.' }).then(({ ok }) => {
      if (!ok) return;
      setShowAnnForm(false);
      setAnnForm({ title: '', body: '', priority: 'normal', pinned: false });
      gardenAdminAPI.announcements(id).then(r => setAnnouncements(r.data.announcements || r.data || []));
    });
  };

  const handleUpdateAnnouncement = (annId) => {
    runAnn(() => gardenAdminAPI.updateAnnouncement(id, annId, annForm), { success: 'Announcement updated', error: 'Could not update the announcement.' }).then(({ ok }) => {
      if (!ok) return;
      setEditingAnn(null);
      setAnnForm({ title: '', body: '', priority: 'normal', pinned: false });
      gardenAdminAPI.announcements(id).then(r => setAnnouncements(r.data.announcements || r.data || []));
    });
  };

  const handleDeleteAnnouncement = async (annId) => {
    if (!(await confirmDialog('Delete this announcement?', { danger: true, title: 'Delete announcement', confirmText: 'Delete' }))) return;
    gardenAdminAPI.deleteAnnouncement(id, annId).then(() => {
      toast('Announcement deleted', { type: 'success' });
      setAnnouncements(prev => prev.filter(a => a.id !== annId));
    }).catch(err => toast(err.response?.data?.error || 'Error', { type: 'error' }));
  };

  const handleAddResource = (e) => {
    e.preventDefault();
    const qty = parseInt(resForm.quantity, 10);
    runResource(
      () => gardensAPI.addResource(id, { ...resForm, quantity: Number.isNaN(qty) || qty < 1 ? 1 : qty }),
      { success: 'Resource added — print its QR label to tag the item.', error: 'Could not add the resource.' },
    ).then(({ ok, data }) => {
      if (!ok) return;
      setShowResForm(false);
      setResForm({ name: '', resource_type: 'tool', description: '', quantity: 1, condition: 'good' });
      gardensAPI.resources(id).then(r => setResources(r.data));
      // Continue straight into QR creation for the resource just added.
      if (data?.data?.id) setQrResource(data.data);
    });
  };

  const handlePrintQR = (resource) => {
    const url = gardensAPI.resourceQR(id, resource.id);
    const w = window.open('', '_blank', 'width=420,height=560');
    if (!w) { toast('Pop-up blocked — allow pop-ups to print the QR label.', { type: 'error' }); return; }
    const esc = (s) => String(s || '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
    w.document.write(`<!doctype html><html><head><title>QR — ${esc(resource.name)}</title>
      <style>body{font-family:Arial,Helvetica,sans-serif;text-align:center;margin:32px;color:#16181d}
      h2{margin:0 0 4px}p{margin:0 0 16px;color:#6b7280;text-transform:capitalize}
      img{width:280px;height:280px}small{display:block;margin-top:12px;color:#9ca3af}</style></head>
      <body><h2>${esc(resource.name)}</h2><p>${esc(resource.resource_type)}</p>
      <img src="${url}" alt="QR code" onload="window.focus();window.print();" />
      <small>Scan to check out / return · ${esc(garden?.name || '')}</small></body></html>`);
    w.document.close();
  };

  const handleReturnResource = (resId) => {
    gardensAPI.returnResource(id, resId).then(() => {
      gardensAPI.resources(id).then(r => setResources(r.data));
    }).catch(err => toast(err.response?.data?.error || 'Error', { type: 'error' }));
  };

  const handleUpdateCondition = (resId, condition) => {
    gardenAdminAPI.updateResourceCondition(id, resId, { condition }).then(() => {
      gardensAPI.resources(id).then(r => setResources(r.data));
    }).catch(err => toast(err.response?.data?.error || 'Error', { type: 'error' }));
  };

  const reloadResources = () => gardensAPI.resources(id).then(r => setResources(r.data)).catch(() => {});

  const openEditResource = (res) => {
    setEditResForm({
      name: res.name || '', resource_type: res.resource_type || 'tool',
      description: res.description || '', quantity: res.quantity || 1,
      condition: res.condition || 'good',
    });
    setEditResource(res);
  };

  const handleSaveEditResource = (e) => {
    e.preventDefault();
    const qty = parseInt(editResForm.quantity, 10);
    gardenAdminAPI.updateResource(id, editResource.id, { ...editResForm, quantity: Number.isNaN(qty) || qty < 1 ? 1 : qty }).then(() => {
      setEditResource(null);
      reloadResources();
      toast('Tool updated', { type: 'success' });
    }).catch(err => toast(err.response?.data?.error || 'Error', { type: 'error' }));
  };

  const handleDeleteResource = async (res) => {
    const checkedOut = !!res.checked_out_to_id;
    const msg = checkedOut
      ? `"${res.name}" is checked out to ${res.checked_out_to_name || 'a member'}. Delete it anyway? The checkout record will be removed.`
      : `Delete "${res.name}" from inventory? This cannot be undone.`;
    if (!(await confirmDialog(msg, { danger: true, title: 'Delete tool', confirmText: 'Delete' }))) return;
    gardenAdminAPI.deleteResource(id, res.id, checkedOut).then(() => {
      setResources(rs => rs.filter(r => r.id !== res.id));
      toast('Tool deleted', { type: 'success' });
    }).catch(err => toast(err.response?.data?.error || 'Error', { type: 'error' }));
  };

  const handleToggleService = async (res) => {
    if (res.out_of_service) {
      gardenAdminAPI.setResourceService(id, res.id, { out_of_service: false }).then(() => {
        reloadResources();
        toast('Tool returned to service', { type: 'success' });
      }).catch(err => toast(err.response?.data?.error || 'Error', { type: 'error' }));
      return;
    }
    const note = await promptDialog('Reason it\'s out of service (optional):', {
      title: `Take "${res.name}" out of service`, confirmText: 'Take out of service', placeholder: 'e.g. broken handle, needs sharpening',
    });
    if (note === null) return; // cancelled
    gardenAdminAPI.setResourceService(id, res.id, { out_of_service: true, note }).then(() => {
      reloadResources();
      toast('Tool marked out of service', { type: 'success' });
    }).catch(err => toast(err.response?.data?.error || 'Error', { type: 'error' }));
  };

  const handleForceReturn = async (res) => {
    if (!(await confirmDialog(`Return "${res.name}" from ${res.checked_out_to_name || 'its borrower'}?`, { title: 'Return tool', confirmText: 'Return' }))) return;
    gardenAdminAPI.forceReturnResource(id, res.id, {}).then(() => {
      reloadResources();
      toast('Tool returned', { type: 'success' });
    }).catch(err => toast(err.response?.data?.error || 'Error', { type: 'error' }));
  };

  const handleExtendDue = async (res) => {
    const val = await promptDialog('Extend the due date by how many days?', {
      title: `Extend "${res.name}"`, confirmText: 'Extend', defaultValue: '7',
    });
    if (val === null) return;
    const days = parseInt(val, 10);
    if (Number.isNaN(days) || days < 1) { toast('Enter a number of days', { type: 'error' }); return; }
    gardenAdminAPI.extendResourceDue(id, res.id, { days }).then(() => {
      reloadResources();
      toast(`Due date extended by ${days} day${days > 1 ? 's' : ''}`, { type: 'success' });
    }).catch(err => toast(err.response?.data?.error || 'Error', { type: 'error' }));
  };

  const openCheckoutFor = (res) => {
    setCheckoutForForm({ user_id: '', duration_days: 3 });
    setCheckoutForRes(res);
    gardenAdminAPI.members(id).then(r => setResMembers(r.data.members || r.data || [])).catch(() => setResMembers([]));
  };

  const handleCheckoutFor = (e) => {
    e.preventDefault();
    if (!checkoutForForm.user_id) { toast('Select a member', { type: 'error' }); return; }
    runCheckout(() => gardenAdminAPI.checkoutResourceFor(id, checkoutForRes.id, {
      user_id: parseInt(checkoutForForm.user_id, 10),
      duration_days: parseInt(checkoutForForm.duration_days, 10) || 3,
    }), { success: 'Tool checked out', error: 'Could not check the tool out.' }).then(({ ok }) => {
      if (!ok) return;
      setCheckoutForRes(null);
      reloadResources();
    });
  };

  const handleSaveSettings = (e) => {
    e.preventDefault();
    runSettings(() => gardenAdminAPI.updateSettings(id, settingsForm), { error: 'Could not save settings.' }).then(({ ok }) => {
      if (!ok) return;
      setSettingsSaved(true);
      setTimeout(() => setSettingsSaved(false), 3000);
      gardensAPI.detail(id).then(res => setGarden(res.data));
    });
  };

  // The Garden Photo becomes the banner on the garden page + the "Explore
  // Gardens" card. Persist it the moment it's uploaded/removed (a focused
  // photo_url-only PUT) rather than waiting for the full "Save Settings"
  // submit — that way the banner updates immediately and never depends on the
  // rest of the form being valid or on form-state timing.
  const handleGardenPhotoChange = (val) => {
    setSettingsForm(prev => ({ ...prev, photo_url: val }));
    gardenAdminAPI.updateSettings(id, { photo_url: val }).then(() => {
      // Patch photo_url in place rather than refetching the whole garden —
      // a refetch re-runs the settings effect and would wipe any unsaved edits
      // to the other fields. (The settings effect keys off `garden`.)
      setGarden(prev => (prev ? { ...prev, photo_url: val } : prev));
    }).catch(err => toast(err.response?.data?.error || 'Error saving photo', { type: 'error' }));
  };

  // ==================== RENDER HELPERS ====================

  const btnStyle = { backgroundColor: 'var(--yh-lime)', color: 'var(--yh-ink)', border: '1px solid var(--yh-lime)', fontWeight: 500 };
  const btnOutlineStyle = { border: '1px solid var(--yh-border)', color: 'var(--yh-ink)', backgroundColor: '#fff' };
  const headingStyle = { color: 'var(--text-dark)' };

  const renderDashboard = () => (
    <div>
      <GardenSetupChecklist garden={garden} payouts={payouts} onGoToTab={goToTab} />
      {payouts && payouts.configured && !payouts.ready && (
        <div className="alert alert-warning d-flex flex-wrap align-items-center justify-content-between gap-2 mb-4">
          <div>
            <i className="bi bi-bank me-2"></i>
            <strong>Finish account payout set-up</strong> — connect a Stripe account
            so collected member dues are paid out to you.
          </div>
          <Link to={`/gardens/${id}/billing`} className="btn btn-warning btn-sm fw-semibold">
            <i className="bi bi-arrow-right-circle me-1"></i>Finish setup
          </Link>
        </div>
      )}
      <h4 className="fw-bold mb-4" style={headingStyle}><i className="bi bi-speedometer2 me-2"></i>Dashboard Overview</h4>
      {/* Stat Cards */}
      <div className="row g-3 mb-4">
        {[
          { label: 'Total Plots', value: stats?.plots?.total ?? '--', icon: 'bi-grid-3x3-gap', tab: 'plots' },
          { label: 'Occupied Plots', value: stats?.plots?.assigned ?? '--', icon: 'bi-grid-fill', tab: 'plots' },
          { label: 'Available Plots', value: stats?.plots?.available ?? '--', icon: 'bi-plus-square-dotted', tab: 'plots' },
          { label: 'Waitlist Size', value: stats?.waitlist_count ?? '--', icon: 'bi-people-fill', tab: 'plots' },
          { label: 'Upcoming Events', value: stats?.upcoming_events?.length ?? '--', icon: 'bi-calendar-check', tab: 'events' },
          { label: 'Total Harvest (lbs)', value: stats?.total_harvest_lbs != null ? Math.round(stats.total_harvest_lbs) : '--', icon: 'bi-basket2-fill' },
        ].map((s, i) => (
          <div key={i} className="col-6 col-md-4 col-lg-2">
            <div
              className="card h-100"
              style={{ border: '1px solid var(--yh-border)', borderRadius: '14px', boxShadow: 'none', background: 'var(--yh-surface-2)', cursor: s.tab ? 'pointer' : 'default' }}
              {...(s.tab ? {
                role: 'button', tabIndex: 0,
                title: `Open ${SIDEBAR_TABS.find(t => t.key === s.tab)?.label}`,
                onClick: () => goToTab(s.tab),
                onKeyDown: (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); goToTab(s.tab); } },
              } : {})}
            >
              <div className="card-body text-center py-3">
                <i className={`bi ${s.icon}`} style={{ fontSize: '1.4rem', color: 'var(--brand-secondary)' }}></i>
                <div style={{ fontSize: '1.6rem', fontWeight: 'bold', color: 'var(--brand-primary)' }}>{s.value}</div>
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
            <button className="btn" style={btnStyle} onClick={() => { goToTab('events'); setShowEventForm(true); }}>
              <i className="bi bi-calendar-plus me-1"></i>Create Event
            </button>
            <button className="btn" style={btnStyle} onClick={() => { goToTab('announcements'); setShowAnnForm(true); }}>
              <i className="bi bi-megaphone me-1"></i>Post Announcement
            </button>
            <button className="btn" style={btnStyle} onClick={() => goToTab('messages')}>
              <i className="bi bi-envelope-plus me-1"></i>Send Message
            </button>
            <button className="btn" style={btnOutlineStyle} onClick={() => goToTab('photos')}>
              <i className="bi bi-camera me-1"></i>View Photos
            </button>
            <button className="btn" style={btnOutlineStyle} onClick={() => goToTab('plots')}>
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
              <div style={{ fontSize: '2rem', fontWeight: 'bold', color: 'var(--brand-secondary)' }}>{weatherData.weather.temp_f}°F</div>
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
                    <button className="btn btn-sm btn-outline-secondary ms-2" onClick={() => gardenAdminAPI.dismissWeatherAlert(id, a.id).then(() => gardenAdminAPI.weather(id).then(r => setWeatherData(r.data))).catch(err => toast(err.response?.data?.error || 'Could not dismiss the alert', { type: 'error' }))}>Dismiss</button>
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
                  <div style={{ width: '36px', height: '36px', borderRadius: '50%', backgroundColor: 'var(--brand-cream)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                    <i className={`bi ${a.icon || 'bi-activity'}`} style={{ color: 'var(--brand-secondary)', fontSize: '0.9rem' }}></i>
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

      {/* How people get plots — reservation vs waitlist trips up new organizers */}
      <p className="text-muted" style={{ fontSize: '.9rem', maxWidth: '75ch' }}>
        Members join from your public garden page in two ways: they can <strong>reserve a specific
        plot</strong> (it shows below as <em>reserved · Pending</em> until you confirm or decline) or{' '}
        <strong>join the waitlist</strong> for the next available one — approving a waitlist entry
        assigns the plot and notifies them.
      </p>

      <div className="table-responsive mb-4">
        <table className="table table-hover align-middle">
          <thead style={{ backgroundColor: 'var(--brand-cream)' }}>
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
                    <span className="badge" style={PLOT_STATUS_COLORS[plot.status] || CHIP_GRAY}>
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
                      {plot.status === 'available' && (
                        assigningPlot === plot.id ? (
                          <span className="d-inline-flex align-items-center gap-1">
                            <select
                              className="form-select form-select-sm"
                              style={{ width: 'auto', minWidth: 140 }}
                              value={assignUserId}
                              onChange={e => setAssignUserId(e.target.value)}
                            >
                              <option value="">Choose member…</option>
                              {membersList.map(m => <option key={m.user_id} value={m.user_id}>{m.name}</option>)}
                            </select>
                            <button className="btn btn-sm" style={btnStyle} disabled={!assignUserId} onClick={() => handleAssignToMember(plot)}>Assign</button>
                            <button className="btn btn-sm btn-outline-secondary" onClick={() => { setAssigningPlot(null); setAssignUserId(''); }}>Cancel</button>
                          </span>
                        ) : (
                          <button className="btn btn-sm" style={btnOutlineStyle} title="Assign this plot to a member directly" onClick={() => { setAssigningPlot(plot.id); setAssignUserId(''); }}>
                            <i className="bi bi-person-plus me-1"></i>Assign
                          </button>
                        )
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
                    <td colSpan="7" style={{ backgroundColor: 'var(--brand-cream)' }}>
                      <div className="table-inline-editor">
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
          <thead style={{ backgroundColor: 'var(--brand-cream)' }}>
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
                      <select className="form-select form-select-sm" style={{ width: '140px' }}
                        value={waitlistPlotPick[w.id] || ''}
                        onChange={async (e) => {
                          const plotId = e.target.value;
                          if (!plotId) return;
                          setWaitlistPlotPick(s => ({ ...s, [w.id]: plotId }));
                          const p = plots.find(pl => String(pl.id) === plotId);
                          const name = w.user_name || w.name;
                          if (!(await confirmDialog(`Assign Plot #${p?.plot_number} to ${name}? They'll be notified.`))) {
                            setWaitlistPlotPick(s => ({ ...s, [w.id]: '' }));
                            return;
                          }
                          handleApproveWaitlist(w.id, parseInt(plotId), { name, plotLabel: p?.plot_number });
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

      {/* Garden Designer — below the daily work (plots + waitlist approvals) */}
      <div className="card mt-4" style={{ border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
        <div className="card-body">
          <div className="d-flex justify-content-between align-items-center mb-3">
            <h5 className="fw-bold mb-0"><i className="bi bi-grid-3x3-gap me-2"></i>Garden Designer</h5>
            <button className="btn btn-sm btn-outline-secondary" onClick={() => window.print()} title="Print layout">
              <i className="bi bi-printer"></i>
            </button>
          </div>

          <GardenLayoutEditor
            gardenId={id}
            plots={plots}
            isPro={gardenHasPro(garden)}
            gridRows={garden?.grid_rows}
            gridCols={garden?.grid_cols}
            onDirtyChange={setLayoutDirty}
            onSaved={() => gardenAdminAPI.plots(id).then(r => setPlots(r.data.plots || r.data || [])).catch(() => {})}
          />
        </div>
      </div>
    </div>
  );

  const renderEventForm = (isEdit = false) => (
    <div className="card mb-4" style={{ border: '1px solid var(--yh-border)' }}>
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
              <div className="form-text">RSVPs close when full — leave blank for unlimited.</div>
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
            <div className="col-md-3">
              <label className="form-label">Repeats</label>
              <select className="form-select" value={eventForm.recurring} onChange={e => setEventForm({ ...eventForm, recurring: e.target.value })}>
                <option value="none">One-time</option>
                <option value="weekly">Weekly</option>
                <option value="biweekly">Every 2 weeks</option>
                <option value="monthly">Monthly</option>
              </select>
              <div className="form-text">
                {isEdit
                  ? 'Updates this occurrence only — it won’t regenerate the series.'
                  : (eventForm.recurring === 'none'
                      ? 'Set a cadence to create a recurring volunteer opportunity.'
                      : 'Creates this date plus 8 more occurrences.')}
              </div>
            </div>
            <div className="col-12">
              <label className="form-label">Description</label>
              <textarea className="form-control" rows="2" value={eventForm.description} onChange={e => setEventForm({ ...eventForm, description: e.target.value })}></textarea>
            </div>
            <div className="col-12 d-flex gap-2">
              <button type="submit" className="btn" style={btnStyle} disabled={savingEvent}>{savingEvent ? 'Saving…' : isEdit ? 'Update Event' : 'Create Event'}</button>
              <button type="button" className="btn" style={btnOutlineStyle} onClick={() => { setShowEventForm(false); setEditingEvent(null); setEventForm({ title: '', description: '', event_type: 'workday', event_date: '', event_time: '09:00', duration_hours: 2, max_volunteers: '', recurring: 'none' }); }}>Cancel</button>
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
          <thead style={{ backgroundColor: 'var(--brand-cream)' }}>
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
                      {ev.recurring && ev.recurring !== 'none' && (
                        <span className="badge ms-2" style={{ backgroundColor: 'var(--brand-light-green)', color: 'var(--text-dark)', textTransform: 'capitalize' }}>
                          <i className="bi bi-arrow-repeat me-1"></i>{ev.recurring === 'biweekly' ? 'Every 2 wks' : ev.recurring}
                        </span>
                      )}
                      {ev.description && <div className="text-muted small">{ev.description.slice(0, 60)}{ev.description.length > 60 ? '...' : ''}</div>}
                    </td>
                    <td className="small">
                      {evDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}<br />
                      <span className="text-muted">{evDate.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })} ({ev.duration_hours}h)</span>
                    </td>
                    <td>
                      <span className="badge" style={{ backgroundColor: { workday: 'var(--brand-accent)', workshop: '#3f7ddb', social: '#8b5cf6', meeting: '#6b7280', harvest_day: 'var(--brand-gold)' }[ev.event_type] || '#6b7280', textTransform: 'capitalize' }}>
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
                            event_date: toLocalISODate(d),
                            event_time: d.toTimeString().slice(0, 5),
                            duration_hours: ev.duration_hours,
                            max_volunteers: ev.max_volunteers || '',
                            recurring: ev.recurring || 'none',
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
                      <td colSpan="5" style={{ backgroundColor: 'var(--brand-cream)' }}>
                        <div className="p-2 table-inline-editor">
                          <h6 className="fw-bold small mb-2">Attendees for {ev.title}</h6>
                          {attendees.length === 0 ? (
                            <p className="text-muted small mb-0">No RSVPs yet.</p>
                          ) : (
                            <div className="d-flex flex-wrap gap-2">
                              {attendees.map((att, i) => (
                                <span key={i} className="badge" style={{ backgroundColor: att.status === 'going' ? 'var(--brand-accent)' : 'var(--brand-gold)', fontSize: '0.8rem', fontWeight: 500 }}>
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
      <div className="card mb-4" style={{ border: '1px solid var(--yh-border)' }}>
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
                    <option value="">Select member...</option>
                    {plotOwners.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
                  </select>
                </div>
                <div className="col-md-8">
                  <label className="form-label">Subject</label>
                  <input type="text" className="form-control" required value={msgForm.subject} onChange={e => setMsgForm({ ...msgForm, subject: e.target.value })} />
                </div>
                {(() => {
                  const r = plotOwners.find(o => String(o.id) === String(msgForm.recipient_id));
                  if (!r) return null;
                  return (
                    <div className="col-12">
                      <div className="d-flex flex-wrap gap-3 small text-muted px-1">
                        <span><i className="bi bi-envelope me-1"></i>{r.email || <em>no email on file</em>}</span>
                        <span><i className="bi bi-phone me-1"></i>{r.phone || <em>no SMS number on file</em>}</span>
                      </div>
                    </div>
                  );
                })()}
                <div className="col-12">
                  <label className="form-label d-block">Delivery</label>
                  {(() => {
                    const r = plotOwners.find(o => String(o.id) === String(msgForm.recipient_id));
                    const opts = [
                      { key: 'platform', label: 'In-app', icon: 'bi-app-indicator', disabled: false },
                      { key: 'email', label: 'Email', icon: 'bi-envelope', disabled: r ? !r.email : false },
                      { key: 'sms', label: 'SMS', icon: 'bi-phone', disabled: r ? !r.phone : false },
                    ];
                    return (
                      <div className="d-flex flex-wrap gap-3">
                        {opts.map(o => (
                          <div className="form-check" key={o.key}>
                            <input className="form-check-input" type="checkbox" id={`ch-${o.key}`}
                              checked={msgForm.channels.includes(o.key)}
                              disabled={o.disabled}
                              onChange={() => toggleMsgChannel(o.key)} />
                            <label className="form-check-label" htmlFor={`ch-${o.key}`}>
                              <i className={`bi ${o.icon} me-1`}></i>{o.label}
                              {o.disabled && <span className="text-muted small"> (unavailable)</span>}
                            </label>
                          </div>
                        ))}
                      </div>
                    );
                  })()}
                </div>
                <div className="col-12">
                  <label className="form-label">Message</label>
                  <textarea className="form-control" rows="3" required value={msgForm.body} onChange={e => setMsgForm({ ...msgForm, body: e.target.value })}></textarea>
                </div>
                <div className="col-12">
                  <button type="submit" className="btn" style={btnStyle} disabled={sending}><i className="bi bi-send me-1"></i>{sending ? 'Sending…' : 'Send'}</button>
                </div>
              </div>
            </form>
          ) : (
            <form onSubmit={handleBroadcast}>
              <div className="alert" style={{ ...CHIP_GOLD, border: 'none' }}>
                <i className="bi bi-broadcast me-1"></i>This posts an in-app message to every plot holder. It does not send email or SMS — use the{' '}
                <a href={`/gardens/${id}/admin/announcements`} onClick={(e) => { e.preventDefault(); goToTab('announcements'); }} style={{ color: 'inherit', fontWeight: 600 }}>Announcements tab</a> for email.
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
                  <button type="submit" className="btn" style={btnStyle} disabled={sending}><i className="bi bi-broadcast me-1"></i>{sending ? 'Posting…' : 'Send Broadcast'}</button>
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
          <div key={msg.id} className="list-group-item" style={{ borderLeft: msg.is_read ? '3px solid var(--brand-gold)' : '3px solid var(--brand-secondary)' }}>
            {editingMsg === msg.id ? (
              <form onSubmit={handleEditMessage}>
                <div className="mb-2">
                  <label className="form-label small fw-bold">Subject</label>
                  <input type="text" className="form-control form-control-sm" required value={editMsgForm.subject} onChange={e => setEditMsgForm({ ...editMsgForm, subject: e.target.value })} />
                </div>
                <div className="mb-2">
                  <label className="form-label small fw-bold">Message</label>
                  <textarea className="form-control form-control-sm" rows="3" required value={editMsgForm.body} onChange={e => setEditMsgForm({ ...editMsgForm, body: e.target.value })}></textarea>
                </div>
                <div className="d-flex gap-2">
                  <button type="submit" className="btn btn-sm" style={btnStyle}><i className="bi bi-check-lg me-1"></i>Save</button>
                  <button type="button" className="btn btn-sm btn-outline-secondary" onClick={() => setEditingMsg(null)}>Cancel</button>
                </div>
              </form>
            ) : (
              <>
                <div className="d-flex justify-content-between align-items-start">
                  <div>
                    <h6 className="mb-1 fw-bold small">{msg.subject}</h6>
                    <div className="text-muted small">
                      {msg.sender_name && <span><i className="bi bi-person me-1"></i>{msg.sender_name} &rarr; </span>}
                      {msg.recipient_name && <span>{msg.recipient_name}</span>}
                      {msg.is_broadcast && <span className="badge bg-info ms-1">Broadcast</span>}
                    </div>
                    {!msg.is_broadcast && (msg.recipient_email || msg.recipient_phone) && (
                      <div className="text-muted" style={{ fontSize: '0.72rem' }}>
                        {msg.recipient_email && <span className="me-2"><i className="bi bi-envelope me-1"></i>{msg.recipient_email}</span>}
                        {msg.recipient_phone && <span><i className="bi bi-phone me-1"></i>{msg.recipient_phone}</span>}
                      </div>
                    )}
                  </div>
                  <div className="text-end">
                    <div className="text-muted" style={{ fontSize: '0.75rem' }}>
                      {msg.created_at && new Date(msg.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}
                    </div>
                    {!msg.is_read && <span className="badge" style={{ backgroundColor: 'var(--brand-secondary)' }}>Unread</span>}
                    <div className="mt-1 d-flex gap-1 justify-content-end">
                      <button className="btn btn-sm btn-outline-secondary py-0 px-1" title="Edit"
                        onClick={() => { setEditingMsg(msg.id); setEditMsgForm({ subject: msg.subject || '', body: msg.body || '' }); }}>
                        <i className="bi bi-pencil"></i>
                      </button>
                      <button className="btn btn-sm btn-outline-danger py-0 px-1" title="Delete" onClick={() => handleDeleteMessage(msg.id)}>
                        <i className="bi bi-trash"></i>
                      </button>
                    </div>
                  </div>
                </div>
                {msg.body && <p className="small mt-2 mb-0 text-muted">{msg.body.slice(0, 150)}{msg.body.length > 150 ? '...' : ''}</p>}
              </>
            )}
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

  const renderCommunityWall = () => (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-2">
        <h4 className="fw-bold mb-0" style={headingStyle}><i className="bi bi-chat-square-text me-2"></i>Community Wall</h4>
        {wallFlaggedCount > 0 && (
          <span className="badge" style={CHIP_GOLD}>
            <i className="bi bi-flag me-1"></i>{wallFlaggedCount} flagged for review
          </span>
        )}
      </div>
      <p className="text-muted small mb-3">
        Comments are screened by the AI moderator on submission. <strong>Flagged</strong> comments stay
        visible to members but are surfaced here to approve or remove; <strong>Auto-denied</strong> posts
        were blocked before going public — review them and “Publish anyway” if the moderator got it wrong.
      </p>

      {/* Filter */}
      <ul className="nav nav-tabs mb-3">
        {[
          { k: 'all', label: 'All' },
          { k: 'flagged', label: `Flagged${wallFlaggedCount ? ` (${wallFlaggedCount})` : ''}` },
          { k: 'approved', label: 'Approved' },
          { k: 'blocked', label: `Auto-denied${wallBlockedCount ? ` (${wallBlockedCount})` : ''}` },
        ].map(t => (
          <li key={t.k} className="nav-item">
            <button className={`nav-link ${wallFilter === t.k ? 'active' : ''}`} onClick={() => setWallFilter(t.k)}>{t.label}</button>
          </li>
        ))}
      </ul>

      {wallComments.length === 0 ? (
        <p className="text-muted text-center py-4">
          {wallFilter === 'flagged' ? 'No flagged comments — the wall is all clear.'
            : wallFilter === 'blocked' ? 'No auto-denied posts — the moderator hasn’t blocked anything.'
            : 'No comments yet.'}
        </p>
      ) : (
        <div className="list-group">
          {wallComments.map(c => (
            <div key={c.id} className="list-group-item"
              style={{ borderLeft: c.status === 'flagged' ? '4px solid var(--brand-gold)'
                : c.status === 'blocked' ? '4px solid #dc2626'
                : '4px solid var(--brand-accent)' }}>
              <div className="d-flex justify-content-between align-items-start gap-3">
                <div style={{ flex: 1 }}>
                  <div className="d-flex align-items-center gap-2 mb-1">
                    <strong className="small">{c.author_name}</strong>
                    {c.status === 'flagged' ? (
                      <span className="badge" style={CHIP_GOLD}><i className="bi bi-flag me-1"></i>Flagged</span>
                    ) : c.status === 'blocked' ? (
                      <span className="badge" style={CHIP_RED}><i className="bi bi-shield-x me-1"></i>Auto-denied</span>
                    ) : (
                      <span className="badge" style={CHIP_LIME}><i className="bi bi-check2 me-1"></i>Approved</span>
                    )}
                    {c.created_at && <span className="text-muted" style={{ fontSize: '0.72rem' }}>{new Date(c.created_at).toLocaleString()}</span>}
                  </div>
                  <div className="small" style={{ whiteSpace: 'pre-wrap' }}>{c.body}</div>
                  {c.moderation_reason && (
                    <div className="text-muted mt-1" style={{ fontSize: '0.72rem' }}>
                      <i className="bi bi-robot me-1"></i>Moderator: {c.moderation_reason}
                    </div>
                  )}
                </div>
                <div className="d-flex flex-column gap-1">
                  {(c.status === 'flagged' || c.status === 'blocked') && (
                    <button className="btn btn-sm btn-outline-success" onClick={() => handleApproveComment(c.id)}>
                      <i className="bi bi-check-lg me-1"></i>{c.status === 'blocked' ? 'Publish anyway' : 'Approve'}
                    </button>
                  )}
                  <button className="btn btn-sm btn-outline-danger" onClick={() => handleRemoveComment(c.id)}>
                    <i className="bi bi-trash me-1"></i>Remove
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
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
          <button className="btn" style={btnStyle} onClick={() => {
            // Closing the form keeps the draft; only a switch out of edit
            // mode resets the fields.
            if (showAnnForm && !editingAnn) { setShowAnnForm(false); return; }
            if (editingAnn) setAnnForm({ title: '', body: '', priority: 'normal', pinned: false });
            setEditingAnn(null);
            setShowAnnForm(true);
          }}>
            <i className="bi bi-plus-circle me-1"></i>New Announcement
          </button>
        </div>

        {/* Create / Edit Form */}
        {(showAnnForm || editingAnn) && (
          <div className="card mb-4" style={{ border: '1px solid var(--yh-border)' }}>
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
                    {!editingAnn && (
                      <div className="form-text">
                        <i className="bi bi-send me-1"></i>Posting notifies every assigned plot holder
                        in-app, by email, and by SMS where they've opted in — sent notifications can't be recalled.
                      </div>
                    )}
                  </div>
                  <div className="col-12 d-flex gap-2">
                    <button type="submit" className="btn" style={btnStyle} disabled={savingAnn}>{savingAnn ? 'Posting…' : editingAnn ? 'Update' : 'Post Announcement'}</button>
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
            <div key={ann.id} className="list-group-item" style={{ borderLeft: `4px solid ${PRIORITY_STYLES[ann.priority]?.color || '#3f7ddb'}` }}>
              <div className="d-flex justify-content-between align-items-start">
                <div style={{ flex: 1 }}>
                  <div className="d-flex align-items-center gap-2 mb-1">
                    {ann.pinned && <i className="bi bi-pin-fill" style={{ color: 'var(--brand-secondary)' }} title="Pinned"></i>}
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
              <i className="bi bi-megaphone" style={{ fontSize: '2.5rem', color: 'var(--brand-gold)' }}></i>
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
        <div className="card mb-4" style={{ border: '1px solid var(--yh-border)' }}>
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
                  <button type="submit" className="btn" style={btnStyle} disabled={savingResource}>{savingResource ? 'Adding…' : 'Add Resource'}</button>
                  <button type="button" className="btn" style={btnOutlineStyle} onClick={() => setShowResForm(false)}>Cancel</button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      <div className="table-responsive">
        <table className="table table-hover align-middle">
          <thead style={{ backgroundColor: 'var(--brand-cream)' }}>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Qty</th>
              <th>Condition</th>
              <th>Status</th>
              <th className="text-end">Manage</th>
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
                  {res.status === 'out_of_service' ? (
                    <div>
                      <span className="badge bg-secondary"><i className="bi bi-wrench-adjustable me-1"></i>Out of service</span>
                      {res.service_note && <div className="text-muted small mt-1">{res.service_note}</div>}
                    </div>
                  ) : res.checked_out_to_name ? (
                    <div>
                      <span className={`badge ${res.is_overdue ? 'bg-danger' : 'bg-warning text-dark'}`}>
                        <i className={`bi ${res.is_overdue ? 'bi-exclamation-triangle' : 'bi-arrow-up-right'} me-1`}></i>
                        {res.is_overdue ? 'Overdue' : 'Checked out'}
                      </span>
                      <div className="small mt-1"><i className="bi bi-person me-1"></i>{res.checked_out_to_name}</div>
                      {res.due_date && (
                        <div className={`small ${res.is_overdue ? 'text-danger fw-semibold' : 'text-muted'}`}>
                          Due {new Date(res.due_date).toLocaleDateString()}
                        </div>
                      )}
                    </div>
                  ) : (
                    <span className="badge bg-success"><i className="bi bi-check-circle me-1"></i>Available</span>
                  )}
                </td>
                <td className="text-end">
                  <div className="dropdown">
                    <button className="btn btn-sm btn-outline-secondary dropdown-toggle" data-bs-toggle="dropdown" aria-expanded="false">
                      <i className="bi bi-gear me-1"></i>Manage
                    </button>
                    <ul className="dropdown-menu dropdown-menu-end">
                      {res.status === 'available' && (
                        <>
                          <li><button className="dropdown-item" onClick={() => openCheckoutFor(res)}><i className="bi bi-box-arrow-right me-2"></i>Check out for member</button></li>
                          <li><button className="dropdown-item" onClick={() => handleToggleService(res)}><i className="bi bi-wrench-adjustable me-2"></i>Take out of service</button></li>
                        </>
                      )}
                      {(res.status === 'checked_out' || res.status === 'overdue') && (
                        <>
                          <li><button className="dropdown-item" onClick={() => handleForceReturn(res)}><i className="bi bi-arrow-return-left me-2"></i>Return tool</button></li>
                          <li><button className="dropdown-item" onClick={() => handleExtendDue(res)}><i className="bi bi-calendar-plus me-2"></i>Extend due date</button></li>
                        </>
                      )}
                      {res.status === 'out_of_service' && (
                        <li><button className="dropdown-item" onClick={() => handleToggleService(res)}><i className="bi bi-check-circle me-2"></i>Return to service</button></li>
                      )}
                      <li><button className="dropdown-item" onClick={() => openEditResource(res)}><i className="bi bi-pencil me-2"></i>Edit details</button></li>
                      <li><button className="dropdown-item" onClick={() => setQrResource(res)}><i className="bi bi-qr-code me-2"></i>QR code</button></li>
                      <li><hr className="dropdown-divider" /></li>
                      <li><button className="dropdown-item text-danger" onClick={() => handleDeleteResource(res)}><i className="bi bi-trash me-2"></i>Delete</button></li>
                    </ul>
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
        <div className="yh-pop-backdrop" onClick={() => setScannedResource(null)}>
          <div className="yh-pop-card" style={{ maxWidth: 360 }} onClick={e => e.stopPropagation()}>
              <div className="modal-body text-center p-4">
                <h5>{scannedResource.name}</h5>
                <p className="text-muted small mb-1">{scannedResource.resource_type}</p>
                <span className={`badge ${scannedResource.checked_out_to_id ? 'bg-warning text-dark' : 'bg-success'} fs-6 mb-3`}>
                  {scannedResource.checked_out_to_id ? `Checked out to ${scannedResource.checked_out_to_name || 'someone'}` : 'Available'}
                </span>
                <div className="d-grid gap-2">
                  {!scannedResource.checked_out_to_id ? (
                    <button className="btn btn-lg" style={btnStyle} onClick={() => {
                      gardensAPI.checkoutResource(id, scannedResource.id, {}).then(() => {
                        setScannedResource(null);
                        gardensAPI.resources(id).then(r => setResources(r.data));
                      }).catch(err => toast(err.response?.data?.error || 'Checkout failed', { type: 'error' }));
                    }}><i className="bi bi-box-arrow-right me-2"></i>Check Out</button>
                  ) : (
                    <button className="btn btn-lg" style={btnStyle} onClick={() => {
                      gardensAPI.returnResource(id, scannedResource.id, {}).then(() => {
                        setScannedResource(null);
                        gardensAPI.resources(id).then(r => setResources(r.data));
                      }).catch(err => toast(err.response?.data?.error || 'Return failed', { type: 'error' }));
                    }}><i className="bi bi-box-arrow-in-left me-2"></i>Return</button>
                  )}
                  <button className="btn btn-outline-secondary" onClick={() => { setScannedResource(null); setShowQRScanner(true); }}>
                    <i className="bi bi-qr-code-scan me-1"></i>Scan Another
                  </button>
                </div>
              </div>
            </div>
          </div>
      )}

      {/* QR Code label — view / print / download */}
      {qrResource && (
        <div className="yh-pop-backdrop" onClick={() => setQrResource(null)}>
          <div className="yh-pop-card" style={{ maxWidth: 380 }} onClick={e => e.stopPropagation()}>
              <div className="modal-header">
                <h5 className="modal-title" style={headingStyle}><i className="bi bi-qr-code me-2"></i>Resource QR Code</h5>
                <button type="button" className="btn-close" onClick={() => setQrResource(null)}></button>
              </div>
              <div className="modal-body text-center p-4">
                <h6 className="fw-bold mb-0">{qrResource.name}</h6>
                <p className="text-muted small mb-3" style={{ textTransform: 'capitalize' }}>{qrResource.resource_type}</p>
                <img src={gardensAPI.resourceQR(id, qrResource.id)} alt={`QR code for ${qrResource.name}`}
                  style={{ width: 220, height: 220, border: '1px solid #e5e7eb', borderRadius: 8 }} />
                <p className="text-muted small mt-3 mb-3">
                  Print this code and attach it to the item. Members scan it from the
                  garden page to check the resource out or return it.
                </p>
                <div className="d-grid gap-2">
                  <button className="btn" style={btnStyle} onClick={() => handlePrintQR(qrResource)}>
                    <i className="bi bi-printer me-2"></i>Print Label
                  </button>
                  <a className="btn btn-outline-secondary" href={gardensAPI.resourceQR(id, qrResource.id)}
                    download={`qr-${qrResource.name.replace(/\s+/g, '-').toLowerCase()}.png`}>
                    <i className="bi bi-download me-2"></i>Download PNG
                  </a>
                  <button className="btn btn-link text-muted" onClick={() => setQrResource(null)}>Close</button>
                </div>
              </div>
            </div>
          </div>
      )}

      {/* Edit tool details */}
      {editResource && (
        <div className="yh-pop-backdrop" onClick={() => setEditResource(null)}>
          <div className="yh-pop-card" style={{ maxWidth: 560 }} onClick={e => e.stopPropagation()}>
              <div className="modal-header">
                <h5 className="modal-title" style={headingStyle}><i className="bi bi-pencil me-2"></i>Edit Tool</h5>
                <button type="button" className="btn-close" onClick={() => setEditResource(null)}></button>
              </div>
              <form onSubmit={handleSaveEditResource}>
                <div className="modal-body">
                  <div className="row g-3">
                    <div className="col-md-7">
                      <label className="form-label">Name</label>
                      <input type="text" className="form-control" required value={editResForm.name} onChange={e => setEditResForm({ ...editResForm, name: e.target.value })} />
                    </div>
                    <div className="col-md-5">
                      <label className="form-label">Type</label>
                      <input className="form-control" list="edit-resource-types" value={editResForm.resource_type} onChange={e => setEditResForm({ ...editResForm, resource_type: e.target.value })} />
                      <datalist id="edit-resource-types">
                        {['tool', 'supply', 'infrastructure', 'equipment', 'seed', 'other'].map(t => <option key={t} value={t} />)}
                      </datalist>
                    </div>
                    <div className="col-md-4">
                      <label className="form-label">Quantity</label>
                      <input type="number" min="1" className="form-control" value={editResForm.quantity}
                        onChange={e => { const v = parseInt(e.target.value, 10); setEditResForm({ ...editResForm, quantity: Number.isNaN(v) ? '' : v }); }} />
                    </div>
                    <div className="col-md-8">
                      <label className="form-label">Condition</label>
                      <select className="form-select" value={editResForm.condition} onChange={e => setEditResForm({ ...editResForm, condition: e.target.value })}>
                        <option value="new">New</option>
                        <option value="good">Good</option>
                        <option value="fair">Fair</option>
                        <option value="needs_repair">Needs Repair</option>
                      </select>
                    </div>
                    <div className="col-12">
                      <label className="form-label">Description</label>
                      <input type="text" className="form-control" value={editResForm.description} onChange={e => setEditResForm({ ...editResForm, description: e.target.value })} />
                    </div>
                  </div>
                </div>
                <div className="modal-footer">
                  <button type="button" className="btn" style={btnOutlineStyle} onClick={() => setEditResource(null)}>Cancel</button>
                  <button type="submit" className="btn" style={btnStyle} disabled={savingPlot}><i className="bi bi-check-lg me-1"></i>{savingPlot ? 'Saving…' : 'Save Changes'}</button>
                </div>
              </form>
            </div>
          </div>
      )}

      {/* Check out for a member */}
      {checkoutForRes && (
        <div className="yh-pop-backdrop" onClick={() => setCheckoutForRes(null)}>
          <div className="yh-pop-card" style={{ maxWidth: 400 }} onClick={e => e.stopPropagation()}>
              <div className="modal-header">
                <h5 className="modal-title" style={headingStyle}><i className="bi bi-box-arrow-right me-2"></i>Check Out Tool</h5>
                <button type="button" className="btn-close" onClick={() => setCheckoutForRes(null)}></button>
              </div>
              <form onSubmit={handleCheckoutFor}>
                <div className="modal-body">
                  <p className="mb-3"><strong>{checkoutForRes.name}</strong> <span className="text-muted small text-capitalize">· {checkoutForRes.resource_type}</span></p>
                  <div className="mb-3">
                    <label className="form-label">Lend to member</label>
                    <select className="form-select" required value={checkoutForForm.user_id} onChange={e => setCheckoutForForm({ ...checkoutForForm, user_id: e.target.value })}>
                      <option value="">Select a member…</option>
                      {resMembers.map(m => <option key={m.user_id} value={m.user_id}>{m.name}</option>)}
                    </select>
                  </div>
                  <div className="mb-1">
                    <label className="form-label">Loan length</label>
                    <div className="d-flex gap-2">
                      {[1, 3, 7, 14].map(d => (
                        <button type="button" key={d}
                          className={`btn btn-sm flex-grow-1 ${parseInt(checkoutForForm.duration_days, 10) === d ? '' : 'btn-outline-secondary'}`}
                          style={parseInt(checkoutForForm.duration_days, 10) === d ? btnStyle : undefined}
                          onClick={() => setCheckoutForForm({ ...checkoutForForm, duration_days: d })}>
                          {d}d
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
                <div className="modal-footer">
                  <button type="button" className="btn" style={btnOutlineStyle} onClick={() => setCheckoutForRes(null)}>Cancel</button>
                  <button type="submit" className="btn" style={btnStyle} disabled={savingCheckout}><i className="bi bi-box-arrow-right me-1"></i>{savingCheckout ? 'Checking out…' : 'Check Out'}</button>
                </div>
              </form>
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
        <div className="alert" style={{ backgroundColor: 'var(--brand-pale)', color: 'var(--brand-primary)', border: 'none' }}>
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
                <label className="form-label">Annual Plot Fee</label>
                <div className="input-group">
                  <span className="input-group-text">$</span>
                  <input type="number" className="form-control" step="1" min="0" inputMode="numeric"
                    value={settingsForm.plot_fee_annual || ''}
                    onChange={e => setSettingsForm({ ...settingsForm, plot_fee_annual: parseInt(e.target.value, 10) || 0 })} />
                </div>
                <div className="form-text">Whole dollars (e.g. 40). Set to 0 for free plots.</div>
              </div>
              <div className="col-md-3">
                <label className="form-label">Operating Model</label>
                <select className="form-select" value={settingsForm.operating_model || 'individual'} onChange={e => setSettingsForm({ ...settingsForm, operating_model: e.target.value })}>
                  <option value="individual">Individual Plots</option>
                  <option value="collective">Collective</option>
                  <option value="hybrid">Hybrid</option>
                </select>
                <div className="form-text">Individual: members tend their own plots. Collective: everyone works shared beds. Hybrid: both.</div>
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
                  onChange={handleGardenPhotoChange}
                  label="Garden Photo"
                  category="garden"
                  gardenId={parseInt(id)}
                  hint="Upload a photo to use as your garden's banner. It saves and appears on the garden page and the Explore Gardens list right away."
                />
              </div>
            </div>
          </div>
        </div>

        <button type="submit" className="btn btn-lg mb-4" style={btnStyle} disabled={savingSettings}>
          <i className="bi bi-check-circle me-2"></i>{savingSettings ? 'Saving…' : 'Save Settings'}
        </button>
      </form>

      {/* Danger Zone */}
      {garden?.is_active === false ? (
        <div className="card" style={{ border: '2px solid var(--brand-accent)' }}>
          <div className="card-body">
            <h6 className="fw-bold text-success mb-3"><i className="bi bi-arrow-counterclockwise me-2"></i>Garden Deactivated</h6>
            <p className="small text-muted mb-3">This garden is currently deactivated and hidden from public listings. Reinstating it will make it visible again and let members resume logging activity.</p>
            <button className="btn btn-success" onClick={async () => {
              if (!(await confirmDialog('Reinstate this garden? It will reappear in public listings and members can resume activity.', { title: 'Reinstate garden', confirmText: 'Reinstate' }))) return;
              gardenAdminAPI.updateSettings(id, { is_active: true }).then(() => {
                toast('Garden reinstated.', { type: 'success' });
                gardensAPI.detail(id).then(res => setGarden(res.data));
              }).catch(err => toast(err.response?.data?.error || 'Error', { type: 'error' }));
            }}>
              <i className="bi bi-power me-1"></i>Reinstate Garden
            </button>
          </div>
        </div>
      ) : (
        <div className="card" style={{ border: '2px solid #e0564f' }}>
          <div className="card-body">
            <h6 className="fw-bold text-danger mb-3"><i className="bi bi-exclamation-triangle me-2"></i>Danger Zone</h6>
            <p className="small text-muted mb-3">Deactivating the garden will hide it from public listings. Members will retain their plot assignments but will not be able to log new activity. You can reinstate the garden from this page at any time.</p>
            <button className="btn btn-outline-danger" onClick={async () => {
              if (!(await confirmDialog('Are you sure you want to deactivate this garden? It will be hidden from listings.', { danger: true, title: 'Deactivate garden', confirmText: 'Deactivate' }))) return;
              gardenAdminAPI.updateSettings(id, { is_active: false }).then(() => {
                toast('Garden deactivated.', { type: 'success' });
                gardensAPI.detail(id).then(res => setGarden(res.data));
              }).catch(err => toast(err.response?.data?.error || 'Error', { type: 'error' }));
            }}>
              <i className="bi bi-power me-1"></i>Deactivate Garden
            </button>
          </div>
        </div>
      )}
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
      }).catch(err =>
        toast(err.response?.data?.error || 'Error saving email settings',
              { type: 'error' }));
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
          <button type="submit" className="btn mt-3" style={btnStyle}><i className="bi bi-check-circle me-2"></i>Save Email Settings</button>
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
    runShift(() => gardenAdminAPI.createShift(id, data), { success: 'Shift created', error: 'Could not create the shift.' }).then(({ ok }) => {
      if (!ok) return;
      setShowShiftForm(false);
      setShiftForm({ title: '', description: '', shift_date: '', start_time: '09:00', end_time: '12:00', max_volunteers: '', recurring: 'none' });
      loadShifts();
    });
  };

  const handleDeleteShift = async (shiftId) => {
    if (!(await confirmDialog('Delete this shift and all signups?', { danger: true, title: 'Delete shift', confirmText: 'Delete' }))) return;
    gardenAdminAPI.deleteShift(id, shiftId).then(() => loadShifts()).catch(err => toast(err.response?.data?.error || 'Error', { type: 'error' }));
  };

  const handleRemindShift = (shiftId) => {
    gardenAdminAPI.remindShift(id, shiftId)
      .then(r => {
        const n = r.data.reminded;
        toast(n ? `Reminder sent to ${n} volunteer${n === 1 ? '' : 's'}.` : 'No signed-up volunteers to remind.', { type: n ? 'success' : 'info' });
      })
      .catch(err => toast(err.response?.data?.error || 'Error sending reminders', { type: 'error' }));
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
    }).catch(err => toast(err.response?.data?.error || 'Error', { type: 'error' }));
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
        <div className="card mb-4" style={{ backgroundColor: 'var(--brand-cream)', border: '1px solid var(--brand-gold)' }}>
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
                  <div className="form-text">Signups close when full — leave blank for unlimited.</div>
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
                <div className="col-12"><button type="submit" className="btn" style={btnStyle} disabled={savingShift}><i className="bi bi-check-circle me-1"></i>{savingShift ? 'Creating…' : 'Create Shift'}</button></div>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Shifts Table */}
      <div className="table-responsive mb-4">
        <table className="table table-hover align-middle">
          <thead style={{ backgroundColor: 'var(--brand-cream)' }}><tr><th>Title</th><th>Date</th><th>Time</th><th>Signups</th><th>Recurring</th><th>Actions</th></tr></thead>
          <tbody>
            {shifts.map(s => (
              <Fragment key={s.id}>
                <tr>
                  <td><strong>{s.title}</strong>{s.description && <div className="text-muted small">{s.description.substring(0, 80)}</div>}</td>
                  <td>{s.shift_date}</td>
                  <td>{s.start_time} - {s.end_time}</td>
                  <td><span className="badge" style={{ backgroundColor: 'var(--brand-secondary)' }}>{s.signup_count}{s.max_volunteers ? `/${s.max_volunteers}` : ''}</span></td>
                  <td>{s.recurring !== 'none' && <span className="badge bg-info">{s.recurring}</span>}</td>
                  <td>
                    <div className="d-flex gap-1">
                      <button className="btn btn-sm" style={btnOutlineStyle} title="View attendees" onClick={() => handleViewShiftAttendees(s.id)}><i className="bi bi-people"></i></button>
                      <button className="btn btn-sm" style={btnOutlineStyle} title="Remind volunteers" disabled={!s.signup_count} onClick={() => handleRemindShift(s.id)}><i className="bi bi-bell"></i></button>
                      <button className="btn btn-sm btn-outline-danger" title="Delete shift" onClick={() => handleDeleteShift(s.id)}><i className="bi bi-trash"></i></button>
                    </div>
                  </td>
                </tr>
                {viewingShiftAttendees === s.id && (
                  <tr><td colSpan="6" style={{ backgroundColor: 'var(--brand-cream)' }}>
                    <div className="p-2 table-inline-editor">
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
                                  <button className="btn btn-sm btn-outline-success" onClick={async () => {
                                    const def = a.hours_logged || ((new Date(`2000-01-01T${s.end_time}`) - new Date(`2000-01-01T${s.start_time}`)) / 3600000).toFixed(1);
                                    const entered = await promptDialog('How many hours did this volunteer work?', { title: 'Log attendance', defaultValue: def, inputType: 'number', confirmText: 'Mark attended' });
                                    if (entered === null) return;
                                    handleMarkAttendance(s.id, [{ user_id: a.user_id, status: 'attended', hours_logged: parseFloat(entered) || 0 }]);
                                  }}>Attended</button>
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
          {volunteerReportPro ? (
            <p className="text-muted mb-0">
              <i className="bi bi-lock me-1"></i>The hours leaderboard is part of Garden Pro.{' '}
              <Link to={`/gardens/${id}/billing`}>See plans</Link>
            </p>
          ) : volunteerReport.length === 0 ? <p className="text-muted">No volunteer data yet.</p> : (
            <table className="table table-sm">
              <thead style={{ backgroundColor: 'var(--brand-cream)' }}><tr><th>#</th><th>Name</th><th>Hours</th><th>Shifts</th><th>No Shows</th></tr></thead>
              <tbody>{volunteerReport.slice(0, 10).map((v, i) => (
                <tr key={v.user_id}>
                  <td>{i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : i + 1}</td>
                  <td><strong>{v.user_name}</strong></td>
                  <td><span className="fw-bold" style={{ color: 'var(--brand-secondary)' }}>{v.total_hours.toFixed(1)}</span></td>
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

  // Finance uses the shared fixed-position toast — the old inline alert was
  // pinned to the top of the tab, offscreen when acting deep in the dues table.
  const showFinanceToast = (msg, type = 'success') => toast(msg, { type: type === 'danger' ? 'error' : 'success' });

  const handleWaiveDues = async (d) => {
    const owed = (d.amount_due - d.amount_paid).toFixed(2);
    const ok = await confirmDialog(`Waive $${owed} for ${d.user_name} for the ${duesSeason} season? They will no longer owe dues this season.`);
    if (!ok) return;
    gardenAdminAPI.waiveDues(id, d.id)
      .then(() => { showFinanceToast(`Dues waived for ${d.user_name}`); loadFinance(); })
      .catch(err => showFinanceToast(err.response?.data?.error || 'Could not waive dues', 'danger'));
  };

  const handleUndoWaive = (d) => {
    // Recompute the status the record would have had; the waive overwrote
    // payment_method with 'waived', so clear it (the original is lost).
    const status = d.amount_paid >= d.amount_due ? 'paid' : d.amount_paid > 0 ? 'partial' : 'unpaid';
    gardenAdminAPI.updateDues(id, d.id, { status, payment_method: '' })
      .then(() => { showFinanceToast(`Waive undone for ${d.user_name}`); loadFinance(); })
      .catch(err => showFinanceToast(err.response?.data?.error || 'Could not undo the waive', 'danger'));
  };

  const handleGenerateDues = () => {
    if (financeSubmitting) return;
    setFinanceError('');
    setFinanceSubmitting(true);
    gardenAdminAPI.generateDues(id, { season_year: duesSeason, amount: parseFloat(generateDuesAmount) })
      .then(r => { showFinanceToast(r.data.message); setShowGenerateDuesModal(false); setGenerateDuesAmount(''); loadFinance(); })
      .catch(err => { setFinanceError(err.response?.data?.error || 'Failed to generate dues'); })
      .finally(() => setFinanceSubmitting(false));
  };

  const handleRecordPayment = (duesId) => {
    if (financeSubmitting) return;
    setFinanceSubmitting(true);
    gardenAdminAPI.updateDues(id, duesId, paymentForm).then(() => {
      setShowPaymentModal(null);
      setPaymentForm({ amount_paid: '', payment_method: 'cash', payment_note: '' });
      showFinanceToast('Payment recorded successfully');
      loadFinance();
    }).catch(err => showFinanceToast(err.response?.data?.error || 'Error recording payment', 'danger'))
      .finally(() => setFinanceSubmitting(false));
  };

  const handleCreateExpense = (e) => {
    e.preventDefault();
    runExpense(() => gardenAdminAPI.createExpense(id, { ...expenseForm, amount: parseFloat(expenseForm.amount) }), { error: 'Could not log the expense.' }).then(({ ok }) => {
      if (!ok) return;
      setShowExpenseForm(false);
      setExpenseForm({ title: '', amount: '', category: 'supplies', expense_date: '', paid_by: '', notes: '' });
      showFinanceToast('Expense logged successfully');
      loadFinance();
    });
  };

  const renderFinance = () => (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h4 className="fw-bold mb-0" style={headingStyle}><i className="bi bi-cash-stack me-2"></i>Finance</h4>
        <div className="d-flex align-items-center gap-2 flex-wrap">
          <Link to={`/gardens/${id}/billing`} className="btn btn-sm btn-outline-secondary">
            <i className="bi bi-bank me-1"></i>Billing &amp; Payouts
          </Link>
          <div className="dropdown">
            <button className="btn btn-sm btn-outline-success dropdown-toggle" data-bs-toggle="dropdown" aria-expanded="false">
              <i className="bi bi-download me-1"></i>Export CSV
            </button>
            <ul className="dropdown-menu dropdown-menu-end">
              <li><button className="dropdown-item" onClick={() => window.open(gardenAdminAPI.exportFinanceCSV(id, 'dues'), '_blank')}><i className="bi bi-receipt me-2"></i>Dues</button></li>
              <li><button className="dropdown-item" onClick={() => window.open(gardenAdminAPI.exportFinanceCSV(id, 'expenses'), '_blank')}><i className="bi bi-cart me-2"></i>Expenses</button></li>
            </ul>
          </div>
          <i className="bi bi-calendar3" style={{ color: 'var(--brand-secondary)' }}></i>
          <label className="fw-semibold small mb-0" style={{ color: 'var(--brand-secondary)' }}>Year:</label>
          <select className="form-select form-select-sm" style={{ width: '110px', borderColor: 'var(--brand-gold)' }}
            value={duesSeason} onChange={e => setDuesSeason(parseInt(e.target.value))}>
            {[...Array(7)].map((_, i) => { const y = new Date().getFullYear() - 3 + i; return <option key={y} value={y}>{y}</option>; })}
          </select>
        </div>
      </div>


      {/* Generate Dues Modal */}
      {showGenerateDuesModal && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.5)', zIndex: 1050, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          onClick={(e) => { if (e.target === e.currentTarget) setShowGenerateDuesModal(false); }}>
          <div className="card" style={{ width: '440px', maxWidth: '90%', border: 'none', boxShadow: '0 8px 32px rgba(0,0,0,0.2)', borderRadius: '16px' }}>
            <div className="card-body p-4">
              <div className="d-flex justify-content-between align-items-center mb-3">
                <h5 className="fw-bold mb-0" style={{ color: 'var(--brand-secondary)' }}><i className="bi bi-receipt me-2"></i>Generate Dues</h5>
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
                <button className="btn" style={btnStyle} onClick={handleGenerateDues} disabled={financeSubmitting || !generateDuesAmount || parseFloat(generateDuesAmount) <= 0}>
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
              <h5 className="fw-bold mb-3" style={{ color: '#e0564f' }}><i className="bi bi-exclamation-triangle me-2"></i>Delete Expense</h5>
              <p>Are you sure you want to delete <strong>"{confirmDeleteExpense.title}"</strong> (${confirmDeleteExpense.amount.toFixed(2)})?</p>
              <div className="d-flex gap-2 justify-content-end">
                <button className="btn btn-outline-secondary" onClick={() => setConfirmDeleteExpense(null)}>Cancel</button>
                <button className="btn btn-danger" onClick={() => {
                  gardenAdminAPI.deleteExpense(id, confirmDeleteExpense.id)
                    .then(() => { showFinanceToast('Expense deleted'); loadFinance(); })
                    .catch(err => showFinanceToast(err.response?.data?.error || 'Could not delete the expense', 'danger'));
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
            { label: 'Dues Expected', value: `$${financeSummary.total_dues_expected.toFixed(2)}`, color: 'var(--brand-secondary)' },
            { label: 'Collected', value: `$${financeSummary.total_collected.toFixed(2)}`, color: 'var(--brand-accent)' },
            { label: 'Outstanding', value: `$${financeSummary.outstanding.toFixed(2)}`, color: '#e0564f' },
            { label: 'Collection Rate', value: `${financeSummary.collection_rate}%`, color: '#3f7ddb' },
            { label: 'Expenses', value: `$${financeSummary.expenses_total.toFixed(2)}`, color: 'var(--brand-gold)' },
            { label: 'Net Balance', value: `$${financeSummary.net_balance.toFixed(2)}`, color: financeSummary.net_balance >= 0 ? 'var(--brand-accent)' : '#e0564f' },
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
        {FINANCE_SUBTABS.map(t => (
          <li key={t} className="nav-item"><button className={`nav-link ${financeTab === t ? 'active' : ''}`} onClick={() => goToFinanceTab(t)}>{t.charAt(0).toUpperCase() + t.slice(1)}</button></li>
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
              <thead style={{ backgroundColor: 'var(--brand-cream)' }}><tr><th>Member</th><th>Due</th><th>Paid</th><th>Status</th><th>Method</th><th>Actions</th></tr></thead>
              <tbody>
                {dues.map(d => (
                  <Fragment key={d.id}>
                    <tr>
                      <td><strong>{d.user_name}</strong></td>
                      <td>${d.amount_due.toFixed(2)}</td>
                      <td>${d.amount_paid.toFixed(2)}</td>
                      <td><span className={`badge ${DUES_STATUSES[d.status] || 'bg-secondary'}`} title={DUES_STATUS_HELP[d.status] || ''}>{d.status}</span></td>
                      <td>{d.payment_method || '--'}</td>
                      <td>
                        <div className="d-flex gap-1">
                          {d.status !== 'paid' && d.status !== 'waived' && (
                            <>
                              <button className="btn btn-sm btn-outline-success" onClick={() => { setShowPaymentModal(d.id); setPaymentForm({ amount_paid: (d.amount_due - d.amount_paid).toFixed(2), payment_method: 'cash', payment_note: '' }); }}>Pay</button>
                              <button className="btn btn-sm btn-outline-secondary" onClick={() => handleWaiveDues(d)}>Waive</button>
                              <button className="btn btn-sm btn-outline-info" onClick={() => gardenAdminAPI.remindDues(id, d.id).then(r => showFinanceToast(r.data.message)).catch(err => showFinanceToast(err.response?.data?.error || 'Error sending reminder', 'danger'))}>Remind</button>
                            </>
                          )}
                          {d.status === 'waived' && (
                            <button className="btn btn-sm btn-outline-secondary" title="Restore this record to unpaid/partial" onClick={() => handleUndoWaive(d)}>Undo waive</button>
                          )}
                        </div>
                      </td>
                    </tr>
                    {showPaymentModal === d.id && (
                      <tr><td colSpan="6" style={{ backgroundColor: 'var(--brand-cream)' }}>
                        <div className="row g-2 p-2 table-inline-editor">
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
                            <button className="btn btn-sm btn-success" onClick={() => handleRecordPayment(d.id)} disabled={financeSubmitting}>Save</button>
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
            <div className="card mb-3" style={{ backgroundColor: 'var(--brand-cream)', border: '1px solid var(--brand-gold)' }}>
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
                    <div className="col-12"><button type="submit" className="btn" style={btnStyle} disabled={savingExpense}><i className="bi bi-check-circle me-1"></i>{savingExpense ? 'Logging…' : 'Log Expense'}</button></div>
                  </div>
                </form>
              </div>
            </div>
          )}
          <div className="table-responsive">
            <table className="table table-hover align-middle">
              <thead style={{ backgroundColor: 'var(--brand-cream)' }}><tr><th>Date</th><th>Title</th><th>Category</th><th>Amount</th><th>Paid By</th><th>Actions</th></tr></thead>
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

      {financeTab === 'stripe' && (
        <div>
          {/* Connected-account health. Shown first because a restricted
              account is the one thing that stops money moving at all, and it
              used to surface only as a failed charge in front of a member. */}
          {stripeFeed?.stripe_status && !stripeFeed.stripe_status.ok && (
            <div className={`alert ${stripeFeed.stripe_status.state === 'restricted' ? 'alert-danger' : 'alert-warning'} d-flex align-items-start gap-2`}>
              <i className="bi bi-exclamation-triangle-fill mt-1"></i>
              <div className="flex-grow-1">
                <div className="fw-bold">
                  {stripeFeed.stripe_status.state === 'restricted'
                    ? 'Stripe paused your payouts'
                    : stripeFeed.stripe_status.state === 'not_started'
                      ? 'No payout account yet'
                      : 'Stripe needs more information'}
                </div>
                <div className="small">{stripeFeed.stripe_status.message}</div>
                {stripeFeed.stripe_status.requirements_due?.length > 0 && (
                  <div className="small mt-1">
                    Still needed: {stripeFeed.stripe_status.requirements_due.slice(0, 4).map(r => r.replace(/[._]/g, ' ')).join(', ')}
                  </div>
                )}
                <div className="d-flex gap-2 mt-2 flex-wrap">
                  <Link to={`/gardens/${id}/billing`} className="btn btn-sm btn-dark">
                    <i className="bi bi-bank me-1"></i>Fix in Billing &amp; Payouts
                  </Link>
                  <Link to="/help/stripe-pitfalls" className="btn btn-sm btn-outline-secondary">
                    What does this mean?
                  </Link>
                </div>
              </div>
            </div>
          )}

          {/* A NULL sync time means no account.updated has ever reached us,
              i.e. the Connect webhook endpoint isn't wired up. Saying so beats
              rendering a confidently empty screen.

              Only when an account actually EXISTS, though. With no connected
              account there is nothing for Stripe to have sent an update about,
              and the banner above already says "No payout account yet" — so
              this one added noise and pointed at the wrong problem. */}
          {stripeFeed?.stripe_status?.account_id
            && !stripeFeed.stripe_status.synced_at && (
            <div className="alert alert-secondary small">
              <i className="bi bi-info-circle me-1"></i>
              Stripe hasn&apos;t sent an account update yet, so payout and account
              status may be incomplete. Payments you take will still appear below.
            </div>
          )}

          <div className="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-3">
            <div className="text-muted small">
              <i className="bi bi-lightning-charge me-1"></i>
              Straight from Stripe — card payments, refunds, chargebacks and bank deposits.
            </div>
            <div className="d-flex align-items-center gap-2">
              <label className="small fw-semibold mb-0 text-muted">Window:</label>
              <select className="form-select form-select-sm" style={{ width: '130px' }}
                value={stripeWindow} onChange={e => setStripeWindow(parseInt(e.target.value))}>
                <option value={30}>Last 30 days</option>
                <option value={90}>Last 90 days</option>
                <option value={365}>Last year</option>
              </select>
              <button className="btn btn-sm btn-outline-secondary" onClick={loadStripeMoney} disabled={stripeLoading}>
                <i className="bi bi-arrow-clockwise me-1"></i>Refresh
              </button>
            </div>
          </div>

          {stripeFeed?.totals && (
            <div className="row g-3 mb-4">
              {[
                { label: 'Card money in', value: `$${stripeFeed.totals.collected.toFixed(2)}`, color: 'var(--brand-accent)', hint: `${stripeFeed.totals.payment_count} payment${stripeFeed.totals.payment_count === 1 ? '' : 's'}` },
                { label: 'Platform fees', value: `$${stripeFeed.totals.fees.toFixed(2)}`, color: 'var(--brand-gold)', hint: 'taken by YardHarvest' },
                { label: 'Stripe fees', value: stripeFeed.totals.fees_complete ? `$${stripeFeed.totals.stripe_fees.toFixed(2)}` : `$${stripeFeed.totals.stripe_fees.toFixed(2)}+`, color: 'var(--brand-gold)', hint: stripeFeed.totals.fees_complete ? 'card processing' : `${stripeFeed.totals.unknown_fee_count} not looked up yet` },
                { label: 'You keep', value: `$${stripeFeed.totals.kept.toFixed(2)}`, color: 'var(--brand-secondary)', hint: keptHint(stripeFeed.totals) },
                { label: 'Refunded', value: `$${stripeFeed.totals.refunded.toFixed(2)}`, color: '#e0564f', hint: 'returned to payers' },
                { label: 'Disputed', value: `$${stripeFeed.totals.disputed.toFixed(2)}`, color: '#e0564f', hint: 'held by Stripe' },
                { label: 'Deposited to bank', value: `$${(stripePayouts?.paid_total ?? 0).toFixed(2)}`, color: '#3f7ddb', hint: 'across your Stripe account' },
              ].map((s, i) => (
                <div key={i} className="col-6 col-md-4 col-lg-2">
                  <div className="card h-100" style={{ border: 'none', borderLeft: `4px solid ${s.color}`, boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
                    <div className="card-body text-center py-3">
                      <div style={{ fontSize: '1.4rem', fontWeight: 'bold', color: s.color }}>{s.value}</div>
                      <div style={{ fontSize: '0.75rem', color: '#6b7280' }}>{s.label}</div>
                      <div style={{ fontSize: '0.68rem', color: '#9ca3af' }}>{s.hint}</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Deposits are account-level: one payout can cover several gardens,
              so it is reported separately rather than folded into the totals
              above. Saying that out loud stops a manager reconciling one
              garden's collections against a deposit and coming up short. */}
          {stripePayouts && (
            <div className="card mb-4" style={{ border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
              <div className="card-body">
                <div className="d-flex justify-content-between align-items-center mb-2">
                  <h6 className="fw-bold mb-0" style={headingStyle}><i className="bi bi-bank me-2"></i>To your bank</h6>
                  {stripePayouts.failed_count > 0 && (
                    <span className="badge bg-danger">{stripePayouts.failed_count} failed</span>
                  )}
                </div>
                {stripePayouts.last_payout_at ? (
                  <p className="small text-muted mb-2">
                    Last deposit <strong>${stripePayouts.last_payout_amount.toFixed(2)}</strong> on{' '}
                    {new Date(stripePayouts.last_payout_at).toLocaleDateString()} —{' '}
                    ${stripePayouts.paid_total.toFixed(2)} across {stripePayouts.paid_count} deposit{stripePayouts.paid_count === 1 ? '' : 's'} in this window.
                  </p>
                ) : (
                  <p className="small text-muted mb-2">
                    No deposits in this window. Stripe pays out on its own schedule once your account is verified.
                  </p>
                )}
                <div className="text-muted" style={{ fontSize: '0.75rem' }}>
                  Deposits cover your whole Stripe account, which may include your other gardens.
                </div>
              </div>
            </div>
          )}

          <div className="table-responsive">
            <table className="table table-hover align-middle">
              <thead style={{ backgroundColor: 'var(--brand-cream)' }}>
                <tr><th>When</th><th>What happened</th><th>Member</th><th className="text-end">Amount</th></tr>
              </thead>
              <tbody>
                {(stripeFeed?.events || []).map(e => (
                  <tr key={e.id}>
                    <td className="text-nowrap small text-muted">
                      {e.occurred_at ? new Date(e.occurred_at).toLocaleDateString() : '--'}
                    </td>
                    <td>
                      <span className={`badge me-2 ${STRIPE_EVENT_BADGES[e.kind] || 'bg-secondary'}`}>
                        {STRIPE_EVENT_LABELS[e.kind] || e.kind}
                      </span>
                      {e.label}
                      {e.description && <div className="text-muted small">{e.description}</div>}
                      {e.kind === 'payment' && (e.fee > 0 || e.stripe_fee > 0) && (
                        <div className="text-muted" style={{ fontSize: '0.7rem' }}>
                          ${e.net.toFixed(2)} after fees
                        </div>
                      )}
                      {e.scope === 'account' && <div className="text-muted" style={{ fontSize: '0.7rem' }}>account-wide</div>}
                    </td>
                    <td className="small">{e.counterparty || '--'}</td>
                    <td className={`text-end fw-bold ${stripeAmountClass(e)}`}>
                      {e.kind === 'account' ? '--'
                        : `${STRIPE_OUTGOING(e) ? '-' : ''}$${e.amount.toFixed(2)}`}
                    </td>
                  </tr>
                ))}
                {!stripeLoading && (stripeFeed?.events || []).length === 0 && (
                  <tr><td colSpan="4" className="text-center text-muted py-4">
                    Nothing from Stripe in this window. Dues paid online and anything
                    collected with Tap to Pay in the app will appear here.
                  </td></tr>
                )}
                {stripeLoading && (
                  <tr><td colSpan="4" className="text-center text-muted py-4">Loading…</td></tr>
                )}
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
  const filteredMembers = membersList.filter(m => {
    if (!memberFilter) return true;
    const q = memberFilter.toLowerCase();
    return (m.name || '').toLowerCase().includes(q) || (m.email || '').toLowerCase().includes(q) || (m.role || '').toLowerCase().includes(q);
  });

  const renderMembers = () => (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-4 flex-wrap gap-2">
        <h4 className="fw-bold mb-0" style={headingStyle}><i className="bi bi-person-badge me-2"></i>Members & Roles</h4>
        <div className="d-flex gap-2">
          <button className="btn btn-sm" style={btnStyle} onClick={copyInviteLink}>
            <i className="bi bi-link-45deg me-1"></i>Copy invite link
          </button>
          <button className="btn btn-outline-success btn-sm" onClick={() => window.open(gardenAdminAPI.exportMembersCSV(id), '_blank')}>
            <i className="bi bi-download me-1"></i>Export CSV
          </button>
        </div>
      </div>

      <div className="mb-3">
        <div className="input-group input-group-sm" style={{ maxWidth: 300 }}>
          <span className="input-group-text"><i className="bi bi-search"></i></span>
          <input type="text" className="form-control" placeholder="Search members..." value={memberFilter} onChange={e => setMemberFilter(e.target.value)} />
        </div>
      </div>

      <div className="table-responsive">
        <table className="table table-hover align-middle">
          <thead style={{ backgroundColor: 'var(--brand-cream)' }}><tr><th>Name</th><th>Phone</th><th>Plot</th><th>Role</th><th>Dues</th><th>Actions</th></tr></thead>
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
                    onChange={e => handleChangeRole(m, e.target.value)}
                    disabled={m.user_id === garden.organizer_id}>
                    {ROLE_OPTIONS.map(r => <option key={r} value={r}>{r.replace('_', ' ')}</option>)}
                  </select>
                </td>
                <td className="small">
                  {m.dues_status ? (
                    <button
                      type="button"
                      className={`badge border-0 ${m.dues_status === 'paid' ? 'bg-success' : m.dues_status === 'waived' ? 'bg-info' : 'bg-warning text-dark'}`}
                      style={{ cursor: 'pointer' }}
                      title="Open in Finance › Dues"
                      onClick={() => navigate(`/gardens/${id}/admin/finance?sub=dues`)}
                    >
                      {m.dues_status}{m.dues_status === 'partial' ? ` ($${m.amount_paid}/$${m.amount_due})` : ''}
                    </button>
                  ) : <span className="text-muted">—</span>}
                </td>
                <td>
                  {m.user_id !== garden.organizer_id && (
                    <button className="btn btn-sm btn-outline-danger" onClick={async () => {
                      if (!(await confirmDialog(`Remove ${m.name}? Their plots will be released.`, { danger: true, title: 'Remove member', confirmText: 'Remove' }))) return;
                      gardenAdminAPI.removeMember(id, m.user_id).then(() => gardenAdminAPI.members(id).then(r => setMembersList(r.data))).catch(err => toast(err.response?.data?.error || 'Error', { type: 'error' }));
                    }}><i className="bi bi-person-x me-1"></i>Remove</button>
                  )}
                  {m.user_id === garden.organizer_id && <span className="badge" style={{ backgroundColor: 'var(--brand-secondary)' }}>Owner</span>}
                </td>
              </tr>
            ))}
            {filteredMembers.length === 0 && (
              <tr><td colSpan="6" className="text-center py-5">
                {membersList.length === 0 ? (
                  <>
                    <i className="bi bi-people" style={{ fontSize: '1.8rem', color: 'var(--yh-muted)' }}></i>
                    <div className="fw-semibold mt-2">No members yet</div>
                    <div className="text-muted small mb-3" style={{ maxWidth: 380, margin: '0 auto' }}>
                      Gardeners join from your public garden page — share your invite link to get started.
                    </div>
                    <button className="btn btn-sm" style={btnStyle} onClick={copyInviteLink}>
                      <i className="bi bi-link-45deg me-1"></i>Copy invite link
                    </button>
                  </>
                ) : <span className="text-muted">No members match your search.</span>}
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="text-muted small">{membersList.length} member{membersList.length !== 1 ? 's' : ''} total</p>
    </div>
  );

  const PRO_TAB_COPY = {
    finance: 'Dues tracking, expense logging, and CSV export are part of Garden Pro.',
    messages: 'Direct and broadcast member messaging is part of Garden Pro.',
    communication: 'Custom announcement email branding is part of Garden Pro.',
    photos: 'The photo gallery with likes and comments is part of Garden Pro.',
  };

  // Central tab gate: loading spinner, Pro upsell, or load-error with retry.
  // Falls through (null) for ready tabs and untracked ones (settings, reports
  // — the funder report component gates itself).
  const renderTabGate = () => {
    const st = tabStatus[activeTab];
    if (st === 'loading') {
      return <div className="text-center py-5"><div className="spinner-border" style={{ color: 'var(--yh-ink)' }}></div></div>;
    }
    if (st === 'pro') {
      return (
        <div className="card" style={{ border: '1px solid var(--yh-border)', borderRadius: 14 }}>
          <div className="card-body text-center py-5">
            <i className="bi bi-lock" style={{ fontSize: '2rem', color: 'var(--yh-muted)' }}></i>
            <h5 className="fw-bold mt-2">This is a Garden Pro feature</h5>
            <p className="text-muted mb-3" style={{ maxWidth: 440, margin: '0 auto' }}>
              {PRO_TAB_COPY[activeTab] || 'This feature is part of Garden Pro.'}
            </p>
            <Link to={`/gardens/${id}/billing`} className="btn" style={{ backgroundColor: '#22242a', color: '#e3ff8f', fontWeight: 600 }}>
              <i className="bi bi-arrow-up-circle me-1"></i>See Garden Pro plans
            </Link>
            <div className="form-text mt-2">Starts with a free trial — no commitment.</div>
          </div>
        </div>
      );
    }
    if (st === 'error') {
      return (
        <div className="alert alert-warning d-flex flex-wrap align-items-center justify-content-between gap-2">
          <span><i className="bi bi-wifi-off me-2"></i>Couldn't load this tab — check your connection.</span>
          <button className="btn btn-sm btn-outline-secondary" onClick={() => setReloadNonce(n => n + 1)}>Try again</button>
        </div>
      );
    }
    return null;
  };

  const renderContent = () => {
    const gate = renderTabGate();
    if (gate) return gate;
    switch (effectiveTab) {
      case 'dashboard': return renderDashboard();
      case 'plots': return renderPlots();
      case 'events': return renderEvents();
      case 'volunteers': return renderVolunteers();
      case 'finance': return renderFinance();
      case 'reports': return <GardenFunderReport gardenId={id} garden={garden} />;
      case 'members': return renderMembers();
      case 'messages': return renderMessages();
      case 'photos': return renderPhotos();
      case 'community_wall': return renderCommunityWall();
      case 'announcements': return renderAnnouncements();
      case 'resources': return renderResources();
      case 'communication': return renderEmail();
      case 'settings': return renderSettings();
      default: return renderDashboard();
    }
  };

  return (
    <div>
      {/* Top Banner (styles live in App.css so the mobile query can compact it) */}
      <div className="garden-admin-banner">
        <div className="d-flex justify-content-between align-items-center">
          <div>
            <Link to={`/gardens/${id}`} style={{ color: 'var(--yh-muted)', textDecoration: 'none', fontSize: '0.85rem' }}>
              <i className="bi bi-arrow-left me-1"></i>Back to Garden
            </Link>
            <h2 className="fw-bold mt-1 mb-0" style={{ color: 'var(--yh-ink)' }}><i className="bi bi-house-gear me-2"></i>{garden.name} <span style={{ fontWeight: 400, opacity: 0.6 }}>Admin Portal</span></h2>
          </div>
          <div className="d-flex align-items-center gap-3">
            <a href={`/gardens/${id}`} target="_blank" rel="noopener"
               className="btn btn-sm btn-outline-secondary"
               title="Opens in a new tab so you keep your place here">
              <i className="bi bi-eye me-1"></i>View public page
            </a>
            <div className="text-end d-none d-md-block">
              <div className="small" style={{ opacity: 0.7 }}>Organizer</div>
              <div className="fw-semibold">{garden.organizer_name}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Sidebar + Content Layout */}
      <div className="d-flex garden-admin-layout" style={{ gap: '0', minHeight: '600px' }}>
        {/* Sidebar */}
        <div className="garden-admin-sidebar" style={{
          width: '220px',
          flexShrink: 0,
          backgroundColor: '#fff',
          borderRight: '1px solid var(--yh-border)',
          borderRadius: '12px 0 0 12px',
          padding: '16px 0',
        }}>
          <nav aria-label="Garden admin sections">
            {visibleTabs.map(tab => {
              const badge = tab.key === 'plots'
                ? (stats?.waitlist_count ?? 0) + (stats?.plots?.reserved ?? 0)
                : tab.key === 'messages' ? (stats?.unread_messages_count ?? 0) : 0;
              const locked = tab.pro && !gardenHasPro(garden);
              return (
                <Fragment key={tab.key}>
                {tab.section && (
                  <div className="d-none d-md-block text-uppercase" aria-hidden="true"
                       style={{ padding: '14px 20px 4px', fontSize: '0.68rem', letterSpacing: '0.06em', color: 'var(--yh-muted)', opacity: 0.8 }}>
                    {tab.section}
                  </div>
                )}
                <button
                  ref={el => { tabRefs.current[tab.key] = el; }}
                  className="btn w-100 text-start d-flex align-items-center gap-2"
                  style={{
                    padding: '10px 20px',
                    border: 'none',
                    borderRadius: '0',
                    fontSize: '0.9rem',
                    fontWeight: activeTab === tab.key ? 600 : 400,
                    backgroundColor: activeTab === tab.key ? 'var(--yh-lime-soft)' : 'transparent',
                    color: activeTab === tab.key ? 'var(--yh-ink)' : 'var(--yh-muted)',
                    borderLeft: activeTab === tab.key ? '3px solid var(--yh-lime-text)' : '3px solid transparent',
                    transition: 'all 0.15s ease',
                  }}
                  onClick={() => goToTab(tab.key)}
                  aria-current={effectiveTab === tab.key ? 'page' : undefined}
                >
                  <i className={`bi ${tab.icon}`}></i>
                  {tab.label}
                  {locked && (
                    <i className="bi bi-lock ms-auto" style={{ fontSize: '0.75rem', opacity: 0.6 }}
                       title="Garden Pro feature" aria-label="Garden Pro feature"></i>
                  )}
                  {badge > 0 && (
                    <span
                      className="badge rounded-pill ms-auto"
                      style={{ backgroundColor: 'var(--yh-ink)', color: '#e3ff8f', fontSize: '0.68rem' }}
                      title={tab.key === 'plots' ? 'Waitlist entries and pending reservations' : 'Unread messages'}
                    >
                      {badge}
                    </span>
                  )}
                </button>
                </Fragment>
              );
            })}
            <a
              href="/static/garden-admin-guide.html" target="_blank" rel="noopener"
              className="btn w-100 text-start d-flex align-items-center gap-2"
              style={{
                padding: '10px 20px', border: 'none', borderRadius: 0, fontSize: '0.9rem',
                color: 'var(--yh-muted)', borderLeft: '3px solid transparent',
                borderTop: '1px solid var(--yh-border)', marginTop: 8,
              }}
            >
              <i className="bi bi-question-circle"></i>Help &amp; guide
              <i className="bi bi-box-arrow-up-right ms-auto" style={{ fontSize: '0.7rem', opacity: 0.6 }}></i>
            </a>
            <Link to="/help" className="btn btn-sm btn-outline-secondary ms-2">
              <i className="bi bi-life-preserver me-1"></i>Help Center
            </Link>
          </nav>
        </div>

        {/* Main Content Area */}
        <div className="garden-admin-content" style={{ flex: 1, padding: '24px', backgroundColor: '#fff', borderRadius: '0 12px 12px 0', border: '1px solid var(--brand-border)', borderLeft: 'none' }}>
          {renderContent()}
        </div>
      </div>
    </div>
  );
}
