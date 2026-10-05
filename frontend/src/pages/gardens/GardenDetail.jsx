import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { gardensAPI, messagesAPI, photosAPI, IMAGE_BASE } from '../../api';
import { useAuth } from '../../AuthContext';
import Seo from '../../components/Seo';
import { trackEvent } from '../../hooks/useTracking';
import { useSubmit } from '../../hooks/useSubmit';
import { toast, lightbox, confirmDialog } from '../../components/dialog/dialogService';
import { useTranslation } from 'react-i18next';
import { formatDate, formatTime, DAY_MONTH, HOUR_MINUTE, WEEKDAY_DAY_MONTH, WEEKDAY_MONTH_TIME } from '../../i18n/dates';
import { loadStripe } from '@stripe/stripe-js';
import { Elements, PaymentElement, useStripe, useElements } from '@stripe/react-stripe-js';

function DuesPaymentForm({ amount, onSuccess, onCancel }) {
  const { t } = useTranslation();
  const stripe = useStripe();
  const elements = useElements();
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState('');
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!stripe || !elements) return;
    setProcessing(true);
    setError('');
    const { error: stripeError, paymentIntent } = await stripe.confirmPayment({ elements, redirect: 'if_required' });
    if (stripeError) { setError(stripeError.message); setProcessing(false); }
    else if (paymentIntent?.status === 'succeeded') { onSuccess(paymentIntent); }
    else { setError(t('garden.errPaymentIncomplete')); setProcessing(false); }
  };
  return (
    <form onSubmit={handleSubmit}>
      <PaymentElement />
      {error && <div className="alert alert-danger mt-2 py-1 small">{error}</div>}
      <div className="d-flex gap-1 mt-2">
        <button type="submit" className="btn btn-success btn-sm flex-grow-1" disabled={!stripe || processing}>
          {processing ? <span className="spinner-border spinner-border-sm"></span> : <>{t('garden.payAmount', { amount: (amount / 100).toFixed(2) })}</>}
        </button>
        <button type="button" className="btn btn-outline-secondary btn-sm" onClick={onCancel} disabled={processing}>{t('garden.cancel')}</button>
      </div>
    </form>
  );
}

// Vocabularies straight from app/models.py. Each rendered its raw slug
// until now - lowercase and English, which was wrong in English too.
const ALERT_TYPE_KEYS = {
  frost: 'garden.alertFrost', heat: 'garden.alertHeat', storm: 'garden.alertStorm',
};
const PLOT_STATUS_KEYS = {
  available: 'garden.statusAvailable', assigned: 'garden.statusAssigned',
  reserved: 'garden.statusReserved', maintenance: 'garden.statusMaintenance',
};
const plotStatus = (v, t) => (PLOT_STATUS_KEYS[v] ? t(PLOT_STATUS_KEYS[v]) : v);
const PRIORITY_KEYS = {
  normal: 'garden.priorityNormal', important: 'garden.priorityImportant',
  urgent: 'garden.priorityUrgent',
};
const EVENT_TYPE_KEYS = {
  workday: 'garden.eventTypeWorkday', workshop: 'garden.eventTypeWorkshop',
  social: 'garden.eventTypeSocial', meeting: 'garden.eventTypeMeeting',
  harvest_day: 'garden.eventTypeHarvestDay',
};
const DUES_STATUS_KEYS = {
  unpaid: 'garden.duesUnpaid', partial: 'garden.duesPartial',
  paid: 'garden.duesPaid', waived: 'garden.duesWaived', comp: 'garden.duesComp',
};
const PLOT_COLORS = {
  available: '#2aa873',
  assigned: '#3f7ddb',
  reserved: '#d99a2b',
  maintenance: '#6b7280',
};

const FEATURE_META = {
  path: { labelKey: 'garden.legendPath', color: '#d8cba3' },
  shed: { labelKey: 'garden.legendShed', color: '#8b5e3c' },
  table: { labelKey: 'garden.legendTable', color: '#a9744f' },
  water: { labelKey: 'garden.legendWater', color: '#6bb7e6' },
  compost: { labelKey: 'garden.legendCompost', color: '#6b8e23' },
  landscaping: { labelKey: 'garden.legendLandscaping', color: '#4a9b5e' },
  public: { labelKey: 'garden.legendPublicArea', color: '#9aa0a6' },
  other: { labelKey: 'garden.legendFeature', color: '#7a7d85' },
};

const EVENT_TYPE_COLORS = {
  workday: '#2aa873',
  workshop: '#3f7ddb',
  social: '#8b5cf6',
  meeting: '#6b7280',
  harvest_day: '#d99a2b',
};

const RESOURCE_CONDITION_COLORS = {
  new: '#2aa873',
  good: '#3f7ddb',
  fair: '#d99a2b',
  needs_repair: '#e0564f',
};

export default function GardenDetail() {
  const { t } = useTranslation();
  const { id } = useParams();
  const { user } = useAuth();
  const { pending: reserving, run: runReserve } = useSubmit();
  const [garden, setGarden] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');

  // Tab data
  const [plots, setPlots] = useState([]);
  const [features, setFeatures] = useState([]);
  const [resources, setResources] = useState([]);
  const [events, setEvents] = useState([]);
  const [harvests, setHarvests] = useState([]);
  const [impact, setImpact] = useState(null);
  const [members, setMembers] = useState([]);

  // Shifts & Knowledge
  const [shifts, setShifts] = useState([]);
  const [volunteerHours, setVolunteerHours] = useState(null);
  const [announcements, setAnnouncements] = useState([]);
  const [weatherAlerts, setWeatherAlerts] = useState([]);
  const [plotHistory, setPlotHistory] = useState(null);
  const [selectedPlot, setSelectedPlot] = useState(null);

  // Forms
  const [showHarvestForm, setShowHarvestForm] = useState(false);
  const [harvestForm, setHarvestForm] = useState({ category: '', variety: '', quantity_lbs: '', harvest_date: '', destination: 'personal', notes: '' });
  const [showResourceForm, setShowResourceForm] = useState(false);
  const [resourceForm, setResourceForm] = useState({ name: '', resource_type: 'tool', description: '', quantity: 1, condition: 'good' });
  const [showWaitlistForm, setShowWaitlistForm] = useState(false);
  const [waitlistForm, setWaitlistForm] = useState({ plot_size_pref: '', notes: '' });
  const [showReserveModal, setShowReserveModal] = useState(false);
  const [availablePlots, setAvailablePlots] = useState([]);
  const [showCheckoutModal, setShowCheckoutModal] = useState(null); // resource id
  const [checkoutDuration, setCheckoutDuration] = useState(3);

  // Plot rename
  const [editingPlotName, setEditingPlotName] = useState(false);
  const [plotNameInput, setPlotNameInput] = useState('');
  const [plotNameSaving, setPlotNameSaving] = useState(false);

  // Contact organizer messaging
  const [showContactOrganizer, setShowContactOrganizer] = useState(false);
  const [contactMsg, setContactMsg] = useState('');
  const [contactSending, setContactSending] = useState(false);

  // Community: photo wall + comment wall
  const [photos, setPhotos] = useState([]);
  const [comments, setComments] = useState([]);
  const [photoUploading, setPhotoUploading] = useState(false);
  const [photosProRequired, setPhotosProRequired] = useState(false);
  const [openPhoto, setOpenPhoto] = useState(null);      // photo id whose comments are expanded
  const [photoComments, setPhotoComments] = useState({}); // { [photoId]: comment[] }
  const [photoCommentText, setPhotoCommentText] = useState('');
  const [photoCommentPosting, setPhotoCommentPosting] = useState(false);
  const [commentBody, setCommentBody] = useState('');
  const [commentPosting, setCommentPosting] = useState(false);
  const [commentError, setCommentError] = useState('');
  const [replyTo, setReplyTo] = useState(null);
  const [replyBody, setReplyBody] = useState('');
  const [replyPosting, setReplyPosting] = useState(false);

  // Dues payment via Stripe
  const [myDues, setMyDues] = useState([]);
  const [selectedDuesId, setSelectedDuesId] = useState(null);
  const [duesSessionData, setDuesSessionData] = useState(null);
  const [duesStripePromise, setDuesStripePromise] = useState(null);
  const [duesPayStep, setDuesPayStep] = useState('idle'); // idle | paying | processing
  const [duesPayError, setDuesPayError] = useState('');

  useEffect(() => {
    gardensAPI.detail(id).then(res => {
      setGarden(res.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    if (!garden) return;
    const noop = () => {};
    if (activeTab === 'plots') {
      gardensAPI.plots(id).then(r => setPlots(r.data)).catch(noop);
      gardensAPI.layoutFeatures(id).then(r => setFeatures(r.data)).catch(noop);
    }
    if (activeTab === 'resources') gardensAPI.resources(id).then(r => setResources(r.data)).catch(noop);
    if (activeTab === 'events') gardensAPI.events(id, { show: 'all' }).then(r => setEvents(r.data)).catch(noop);
    if (activeTab === 'harvest') gardensAPI.harvests(id).then(r => setHarvests(r.data)).catch(noop);
    if (activeTab === 'impact') gardensAPI.impact(id).then(r => setImpact(r.data)).catch(noop);
    if (activeTab === 'community') {
      photosAPI.gardenPhotos(id).then(r => { setPhotos(r.data.photos || []); setPhotosProRequired(!!r.data.pro_required); }).catch(noop);
      gardensAPI.comments(id).then(r => setComments(r.data)).catch(noop);
    }
    if (activeTab === 'shifts') {
      gardensAPI.shifts(id).then(r => setShifts(r.data)).catch(noop);
      if (user) gardensAPI.volunteerHours(id).then(r => setVolunteerHours(r.data)).catch(noop);
    }
    if (activeTab === 'overview') {
      gardensAPI.members(id).then(r => setMembers(r.data)).catch(noop);
      gardensAPI.weatherAlerts(id).then(r => setWeatherAlerts(r.data)).catch(noop);
      gardensAPI.announcements(id).then(r => setAnnouncements(r.data)).catch(noop);
      gardensAPI.shifts(id).then(r => setShifts(r.data)).catch(noop);
      if (user && garden.user_has_plot) gardensAPI.myDues(id).then(r => setMyDues(r.data)).catch(noop);
    }
  }, [activeTab, garden, id]);

  const handleRsvp = (eventId, status) => {
    gardensAPI.rsvpEvent(id, eventId, { status }).then(() => {
      gardensAPI.events(id, { show: 'all' }).then(r => setEvents(r.data));
      toast(status === 'going' ? t('garden.toastRsvpGoing') : t('garden.toastRsvpUpdated'), { type: 'success' });
    }).catch(err => toast(err.response?.data?.error || t('garden.errRsvpSave'), { type: 'error' }));
  };

  const handleCancelRsvp = (eventId) => {
    gardensAPI.cancelRsvp(id, eventId).then(() => {
      gardensAPI.events(id, { show: 'all' }).then(r => setEvents(r.data));
      toast(t('garden.toastRsvpCancelled'), { type: 'success' });
    }).catch(err => toast(err.response?.data?.error || t('garden.errRsvpCancel'), { type: 'error' }));
  };

  const handleCheckout = (resId, duration) => {
    gardensAPI.checkoutResource(id, resId, { duration_days: duration }).then(() => {
      setShowCheckoutModal(null);
      gardensAPI.resources(id).then(r => setResources(r.data));
    }).catch(err => toast(err.response?.data?.error || t('garden.errCheckOut'), { type: 'error' }));
  };

  const handleReturn = (resId) => {
    gardensAPI.returnResource(id, resId).then(() => {
      gardensAPI.resources(id).then(r => setResources(r.data));
      toast(t('garden.toastResourceReturned'), { type: 'success' });
    }).catch(err => toast(err.response?.data?.error || t('garden.errResourceReturn'), { type: 'error' }));
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
      toast(t('garden.toastHarvestLogged'), { type: 'success' });
    }).catch(err => toast(err.response?.data?.error || t('garden.errHarvestLog'), { type: 'error' }));
  };

  const handleAddResource = (e) => {
    e.preventDefault();
    const payload = { ...resourceForm, quantity: Number(resourceForm.quantity) > 0 ? Number(resourceForm.quantity) : 1 };
    gardensAPI.addResource(id, payload).then(() => {
      setShowResourceForm(false);
      setResourceForm({ name: '', resource_type: 'tool', description: '', quantity: 1, condition: 'good' });
      gardensAPI.resources(id).then(r => setResources(r.data));
      toast(t('garden.toastResourceAdded'), { type: 'success' });
    }).catch(err => toast(err.response?.data?.error || t('garden.errAddResource'), { type: 'error' }));
  };

  const handleJoinWaitlist = (e) => {
    e.preventDefault();
    gardensAPI.joinWaitlist(id, waitlistForm).then(() => {
      setShowWaitlistForm(false);
      setWaitlistForm({ plot_size_pref: '', notes: '' });
      gardensAPI.detail(id).then(res => setGarden(res.data));
      toast(t('garden.toastOnWaitlist'), { type: 'success' });
    }).catch(err => toast(err.response?.data?.error || t('garden.errWaitlistJoin'), { type: 'error' }));
  };

  const openReserveModal = () => {
    gardensAPI.plots(id).then(r => {
      const avail = (r.data || []).filter(p => p.status === 'available');
      setAvailablePlots(avail);
      setShowReserveModal(true);
    });
  };

  // Funnel: a garden detail page was viewed (fires once per garden id).
  useEffect(() => { trackEvent('garden_view', { garden_id: id }); }, [id]);

  const handleReservePlot = async (plotId) => {
    const plot = availablePlots.find(p => p.id === plotId);
    const fee = Number(garden?.plot_fee_annual) || 0;
    const label = plot
      ? t('garden.plotNumber', { number: plot.plot_number })
      : t('garden.thisPlot');
    const feeLine = fee > 0
      ? t('garden.feeLine', { amount: Math.round(fee) })
      : t('garden.feeFree');
    const ok = await confirmDialog(t('garden.reserveConfirm', { label, fee: feeLine }),
      { title: t('garden.reservePlotTitle'), confirmText: t('garden.reservePlot') });
    if (!ok) return;
    const res = await runReserve(() => gardensAPI.reservePlot(id, plotId), {
      success: t('garden.toastPlotReserved'),
      error: t('garden.errPlotReserve'),
    });
    if (!res.ok) return;
    trackEvent('plot_reserve', { garden_id: id, plot_id: plotId });
    setShowReserveModal(false);
    gardensAPI.detail(id).then(r => setGarden(r.data));
  };

  const handleContactOrganizer = async (e) => {
    e.preventDefault();
    if (!contactMsg.trim() || !garden.organizer_id) return;
    setContactSending(true);
    try {
      await messagesAPI.send({
        recipient_id: garden.organizer_id,
        body: `[${garden.name}] ${contactMsg.trim()}`,
      });
      setContactMsg('');
      setShowContactOrganizer(false);
      toast(t('garden.toastMessageSent'), { type: 'success' });
    } catch (err) {
      toast(err.response?.data?.error || t('garden.errSendMessage'), { type: 'error' });
    }
    setContactSending(false);
  };

  // Dues payment handlers
  const handlePayDues = async (duesId) => {
    setSelectedDuesId(duesId);
    setDuesPayError('');
    setDuesPayStep('paying');
    try {
      const res = await gardensAPI.payDues(id, duesId);
      setDuesSessionData(res.data);
      if (!res.data.dev_mode && res.data.publishable_key) {
        setDuesStripePromise(loadStripe(res.data.publishable_key));
      }
    } catch (err) {
      setDuesPayError(err.response?.data?.error || t('garden.errInitPayment'));
      setDuesPayStep('idle');
    }
  };

  const handleDuesPaymentComplete = async (paymentIntent) => {
    setDuesPayStep('processing');
    try {
      await gardensAPI.confirmDuesPayment(id, selectedDuesId, {
        payment_intent_id: paymentIntent?.id || `dev-${Date.now()}`,
      });
      const res = await gardensAPI.myDues(id);
      setMyDues(res.data);
      setDuesPayStep('idle');
      setDuesSessionData(null);
      setSelectedDuesId(null);
      setDuesStripePromise(null);
    } catch (err) {
      setDuesPayError(err.response?.data?.error || t('garden.errConfirmPayment'));
      setDuesPayStep('paying');
    }
  };

  const handleDevDuesPayment = async () => {
    await handleDuesPaymentComplete({
      id: `dev-test-${Date.now()}`,
      status: 'succeeded',
    });
  };

  // Community: photo wall + comment wall handlers
  const handlePhotoUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setPhotoUploading(true);
    try {
      const fd = new FormData();
      fd.append('photo', file);
      fd.append('garden_id', garden.id);
      fd.append('category', 'garden');
      await photosAPI.upload(fd);
      const r = await photosAPI.gardenPhotos(id);
      setPhotos(r.data.photos || []);
      toast(t('garden.toastPhotoPosted'), { type: 'success' });
    } catch (err) {
      toast(err.response?.data?.error || t('garden.errUploadPhoto'), { type: 'error' });
    }
    setPhotoUploading(false);
    e.target.value = '';
  };

  const handleDeletePhoto = async (photoId) => {
    try {
      await photosAPI.delete(photoId);
      setPhotos(photos.filter(p => p.id !== photoId));
      if (openPhoto === photoId) setOpenPhoto(null);
    } catch (err) {
      toast(err.response?.data?.error || t('garden.errDeletePhoto'), { type: 'error' });
    }
  };

  const handleLikePhoto = async (photoId) => {
    if (!user) { toast(t('garden.toastSignInUpvote'), { type: 'info' }); return; }
    try {
      const r = await photosAPI.like(photoId);
      setPhotos(prev => prev.map(p => p.id === photoId
        ? { ...p, liked_by_me: r.data.liked, likes_count: r.data.likes_count } : p));
    } catch (err) {
      toast(err.response?.data?.error || t('garden.errUpvote'), { type: 'error' });
    }
  };

  const handleTogglePhotoComments = async (photoId) => {
    if (openPhoto === photoId) { setOpenPhoto(null); return; }
    setOpenPhoto(photoId);
    setPhotoCommentText('');
    if (!photoComments[photoId]) {
      try {
        const r = await photosAPI.comments(photoId);
        setPhotoComments(prev => ({ ...prev, [photoId]: r.data.comments || [] }));
      } catch {
        setPhotoComments(prev => ({ ...prev, [photoId]: [] }));
      }
    }
  };

  const handleAddPhotoComment = async (photoId) => {
    if (!photoCommentText.trim()) return;
    setPhotoCommentPosting(true);
    try {
      const r = await photosAPI.addComment(photoId, { content: photoCommentText.trim() });
      setPhotoComments(prev => ({ ...prev, [photoId]: [...(prev[photoId] || []), r.data] }));
      setPhotoCommentText('');
      setPhotos(prev => prev.map(p => p.id === photoId
        ? { ...p, comments_count: (p.comments_count || 0) + 1 } : p));
    } catch (err) {
      toast(err.response?.data?.error || t('garden.errPostComment'), { type: 'error' });
    }
    setPhotoCommentPosting(false);
  };

  const handleDeletePhotoComment = async (photoId, commentId) => {
    try {
      await photosAPI.deleteComment(photoId, commentId);
      setPhotoComments(prev => ({
        ...prev,
        [photoId]: (prev[photoId] || []).filter(c => c.id !== commentId),
      }));
      setPhotos(prev => prev.map(p => p.id === photoId
        ? { ...p, comments_count: Math.max(0, (p.comments_count || 0) - 1) } : p));
    } catch (err) {
      toast(err.response?.data?.error || t('garden.errDeleteComment'), { type: 'error' });
    }
  };

  const handlePostComment = async (e) => {
    e.preventDefault();
    if (!commentBody.trim()) return;
    setCommentPosting(true);
    setCommentError('');
    try {
      await gardensAPI.addComment(id, { body: commentBody.trim() });
      setCommentBody('');
      const r = await gardensAPI.comments(id);
      setComments(r.data);
      toast(t('garden.toastCommentPosted'), { type: 'success' });
    } catch (err) {
      if (err.response?.status === 422 && err.response?.data?.moderation === 'block') {
        setCommentError(err.response.data.error || t('garden.errCommentRejected'));
      } else {
        setCommentError(err.response?.data?.error || t('garden.errCommentPost'));
      }
    }
    setCommentPosting(false);
  };

  const handleDeleteComment = async (commentId) => {
    try {
      await gardensAPI.deleteComment(id, commentId);
      // Drop the comment and any of its replies.
      setComments(comments.filter(c => c.id !== commentId && c.parent_id !== commentId));
    } catch (err) {
      toast(err.response?.data?.error || t('garden.errDeleteComment'), { type: 'error' });
    }
  };

  const handleLikeComment = async (commentId) => {
    if (!user) { toast(t('garden.toastSignInLike'), { type: 'info' }); return; }
    try {
      const r = await gardensAPI.likeComment(id, commentId);
      setComments(prev => prev.map(c => c.id === commentId
        ? { ...c, liked_by_me: r.data.liked, likes_count: r.data.likes_count } : c));
    } catch (err) {
      toast(err.response?.data?.error || t('garden.errLike'), { type: 'error' });
    }
  };

  const handleReply = async (parentId) => {
    if (!replyBody.trim()) return;
    setReplyPosting(true);
    try {
      await gardensAPI.addComment(id, { body: replyBody.trim(), parent_id: parentId });
      setReplyBody('');
      setReplyTo(null);
      const r = await gardensAPI.comments(id);
      setComments(r.data);
      toast(t('garden.toastReplyPosted'), { type: 'success' });
    } catch (err) {
      toast(err.response?.data?.error || t('garden.errPostReply'), { type: 'error' });
    }
    setReplyPosting(false);
  };

  // One comment card. `isReply` tones down the accent + hides the Reply button
  // (threads stay one level deep).
  const renderComment = (c, isReply) => (
    <div key={c.id} style={{
      padding: '10px 12px', borderRadius: '10px', backgroundColor: '#f8f9fa', marginBottom: '8px',
      borderLeft: c.status === 'flagged' ? '4px solid #d99a2b'
        : (isReply ? '4px solid #cbd5c0' : '4px solid #7fd4ab'),
    }}>
      <div className="d-flex justify-content-between align-items-start">
        <div style={{ flex: 1 }}>
          <div className="fw-semibold small">
            {c.author_name}
            {c.status === 'flagged' && (
              <span className="badge ms-2" style={{ backgroundColor: '#fef3c7', color: '#92400e', fontSize: '0.6rem' }}>
                <i className="bi bi-flag me-1"></i>{t('garden.underReview')}
              </span>
            )}
          </div>
          <div className="small mt-1" style={{ whiteSpace: 'pre-wrap' }}>{c.body}</div>
          <div className="d-flex align-items-center gap-3 mt-2">
            <button type="button" className="btn btn-sm p-0 border-0 bg-transparent d-inline-flex align-items-center"
              style={{ color: c.liked_by_me ? '#e0245e' : 'var(--yh-muted)', fontSize: '0.78rem' }}
              onClick={() => handleLikeComment(c.id)} title={user ? t('garden.like') : t('garden.signInToLike')}>
              <i className={`bi ${c.liked_by_me ? 'bi-heart-fill' : 'bi-heart'} me-1`}></i>
              {c.likes_count > 0 ? c.likes_count : t('garden.like')}
            </button>
            {!isReply && user && (
              <button type="button" className="btn btn-sm p-0 border-0 bg-transparent text-muted"
                style={{ fontSize: '0.78rem' }}
                onClick={() => { setReplyTo(replyTo === c.id ? null : c.id); setReplyBody(''); }}>
                <i className="bi bi-reply me-1"></i>{t('garden.reply')}
              </button>
            )}
            {c.created_at && (
              <span className="text-muted" style={{ fontSize: '0.7rem' }}>
                {formatDate(c.created_at)}
              </span>
            )}
          </div>
        </div>
        {c.can_delete && (
          <button className="btn btn-sm btn-link text-danger p-0 ms-2" title={t('garden.deleteComment')} onClick={() => handleDeleteComment(c.id)}>
            <i className="bi bi-trash"></i>
          </button>
        )}
      </div>
    </div>
  );

  if (loading) return <div className="text-center py-5"><div className="spinner-border" style={{ color: 'var(--yh-ink)' }}></div></div>;
  if (!garden) return <div className="text-center py-5"><p>{t('garden.notFound')}</p></div>;

  const tabs = [
    { key: 'overview', label: t('garden.tabOverview'), icon: 'bi-info-circle' },
    { key: 'plots', label: t('garden.tabPlots'), icon: 'bi-grid-3x3' },
    { key: 'resources', label: t('garden.tabResources'), icon: 'bi-tools' },
    { key: 'events', label: t('garden.tabEvents'), icon: 'bi-calendar-event' },
    { key: 'shifts', label: t('garden.tabVolunteer'), icon: 'bi-people' },
    { key: 'harvest', label: t('garden.tabHarvestLog'), icon: 'bi-basket2' },
    { key: 'community', label: t('garden.tabCommunity'), icon: 'bi-chat-square-text' },
  ];

  const now = new Date();

  return (
    <div>
      <Seo
        title={garden.name}
        path={`/gardens/${garden.id}`}
        description={(garden.description || t('garden.seoFallback', { name: garden.name })).slice(0, 160)}
        image={garden.photo_url || undefined}
        type="article"
        jsonLd={{
          '@context': 'https://schema.org',
          '@type': 'Place',
          name: garden.name,
          description: garden.description || undefined,
          address: {
            '@type': 'PostalAddress',
            addressLocality: garden.city,
            addressRegion: garden.state,
          },
        }}
      />
      {/* Header */}
      <div style={{
        background: garden.photo_url
          ? `linear-gradient(rgba(0,0,0,0.5), rgba(0,0,0,0.6)), url(${garden.photo_url}) center/cover`
          : '#dce8ce',
        border: garden.photo_url ? 'none' : '1px solid #cfdec0',
        borderRadius: '16px',
        padding: '40px 32px',
        color: garden.photo_url ? 'white' : 'var(--yh-ink)',
        marginBottom: '24px',
      }}>
        <Link to="/gardens" style={{ color: garden.photo_url ? 'rgba(255,255,255,0.8)' : 'var(--yh-muted)', textDecoration: 'none', fontSize: '0.9rem' }}>
          <i className="bi bi-arrow-left me-1"></i> {t('garden.allGardens')}
        </Link>
        <h1 className="fw-bold mt-2 mb-1" style={{ color: garden.photo_url ? 'white' : 'var(--yh-ink)' }}>{garden.name}</h1>
        <p className="mb-2" style={{ opacity: 0.85 }}>
          <i className="bi bi-geo-alt me-1"></i>
          {garden.address && `${garden.address}, `}{garden.city}, {garden.state} {garden.zip_code}
        </p>
        <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', fontSize: '0.9rem' }}>
          <span><i className="bi bi-person me-1"></i> {t('garden.organizedBy', { name: garden.organizer_name })}</span>
          <span><i className="bi bi-grid-3x3-gap me-1"></i> {t('garden.plotsCount', { count: garden.total_plots })}</span>
          <span style={{ color: garden.available_plots > 0 ? (garden.photo_url ? '#7fd4ab' : '#3b6d11') : (garden.photo_url ? '#fca5a5' : '#993556'), fontWeight: 500 }}>
            {garden.available_plots > 0
              ? t('garden.availableCount', { count: garden.available_plots })
              : t('garden.allPlotsAssigned')}
          </span>
        </div>
        {garden.user_is_organizer && (
          <Link to={`/gardens/${id}/admin`}
                className="btn mt-3"
                style={{ backgroundColor: 'var(--yh-lime)', color: 'var(--yh-ink)', fontWeight: 500, borderRadius: '10px' }}>
            <i className="bi bi-shield-lock me-2"></i>{t('garden.adminPortal')}
          </Link>
        )}
      </div>

      {/* Tabs */}
      <ul className="nav nav-tabs mb-4 garden-detail-tabs">
        {tabs.map(tab => (
          <li key={tab.key} className="nav-item">
            <button
              className={`nav-link ${activeTab === tab.key ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.key)}
              style={activeTab === tab.key ? { color: '#22242a', borderBottomColor: '#22242a', fontWeight: 600 } : { color: '#6b7280' }}
            >
              <i className={`bi ${tab.icon} me-1`}></i> {tab.label}
            </button>
          </li>
        ))}
      </ul>

      {/* Overview Tab */}
      {activeTab === 'overview' && (
        <div className="row">
          {/* Weather Alerts Banner */}
          {weatherAlerts.length > 0 && (
            <div className="col-12 mb-3">
              {weatherAlerts.map(a => (
                <div key={a.id} className={`alert ${a.severity === 'critical' ? 'alert-danger' : a.severity === 'warning' ? 'alert-warning' : 'alert-info'} py-2 mb-2`}>
                  <i className={`bi ${a.alert_type === 'frost' ? 'bi-snow' : a.alert_type === 'heat' ? 'bi-thermometer-high' : a.alert_type === 'storm' ? 'bi-cloud-lightning' : 'bi-exclamation-triangle'} me-2`}></i>
                  <strong>{ALERT_TYPE_KEYS[a.alert_type] ? t(ALERT_TYPE_KEYS[a.alert_type]) : t('garden.alertGeneric')}:</strong> {a.message}
                </div>
              ))}
            </div>
          )}
          <div className="col-md-8">
            <div className="card mb-4" style={{ border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
              <div className="card-body">
                <h5 className="fw-bold mb-3">{t('garden.about')}</h5>
                <p style={{ whiteSpace: 'pre-wrap' }}>{garden.description || t('garden.noDescription')}</p>

                {garden.rules && (
                  <>
                    <h6 className="fw-bold mt-4 mb-2"><i className="bi bi-clipboard-check me-2"></i>{t('garden.rules')}</h6>
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
                { label: t('garden.totalPlots'), value: garden.total_plots, icon: 'bi-grid-3x3-gap', color: 'var(--yh-ink)' },
                { label: t('garden.available'), value: garden.available_plots, icon: 'bi-check-circle', color: '#2aa873' },
                { label: t('garden.members'), value: garden.member_count, icon: 'bi-people', color: '#3f7ddb' },
                { label: t('garden.harvestLbs'), value: Math.round(garden.total_harvest_lbs), icon: 'bi-basket2', color: '#d99a2b' },
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
                  <h5 className="fw-bold mb-3"><i className="bi bi-calendar-event me-2"></i>{t('garden.upcomingEvents')}</h5>
                  {garden.upcoming_events_list.map(event => (
                    <div key={event.id} style={{
                      display: 'flex', alignItems: 'center', gap: '12px',
                      padding: '12px', borderRadius: '8px', backgroundColor: '#f8f9fa', marginBottom: '8px',
                    }}>
                      <span style={{
                        backgroundColor: EVENT_TYPE_COLORS[event.event_type] || '#6b7280',
                        color: 'white', padding: '4px 10px', borderRadius: '8px', fontSize: '0.75rem', fontWeight: 600,
                      }}>{EVENT_TYPE_KEYS[event.event_type] ? t(EVENT_TYPE_KEYS[event.event_type]) : event.event_type}</span>
                      <div style={{ flex: 1 }}>
                        <strong>{event.title}</strong>
                        <div className="text-muted small">
                          {formatDate(event.event_date, WEEKDAY_MONTH_TIME)}
                        </div>
                      </div>
                      <span className="text-muted small">{t('garden.rsvpGoingCount', { count: event.rsvp_going })}</span>
                    </div>
                  ))}
                  <button className="btn btn-sm btn-outline-success mt-2" onClick={() => setActiveTab('events')}>{t('garden.viewAllEvents')}</button>
                </div>
              </div>
            )}

            {/* Garden News & Announcements */}
            {announcements.length > 0 && (
              <div className="card mb-4" style={{ border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
                <div className="card-body">
                  <h5 className="fw-bold mb-3"><i className="bi bi-megaphone me-2"></i>{t('garden.news')}</h5>
                  {announcements.map(a => (
                    <div key={a.id} style={{
                      padding: '12px', borderRadius: '8px', backgroundColor: '#f8f9fa', marginBottom: '8px',
                      borderLeft: `4px solid ${a.pinned ? '#d99a2b' : a.priority === 'high' ? '#e0564f' : a.priority === 'medium' ? '#3f7ddb' : '#2aa873'}`,
                    }}>
                      <div className="d-flex align-items-start gap-2">
                        {a.pinned && <i className="bi bi-pin-fill" style={{ color: '#d99a2b' }}></i>}
                        <div style={{ flex: 1 }}>
                          <strong>{a.title}</strong>
                          {a.priority && a.priority !== 'low' && (
                            <span className="badge ms-2" style={{
                              backgroundColor: a.priority === 'high' ? '#fee2e2' : '#dbeafe',
                              color: a.priority === 'urgent' ? '#991b1b' : '#1e40af',
                              fontSize: '0.65rem',
                            }}>{PRIORITY_KEYS[a.priority] ? t(PRIORITY_KEYS[a.priority]) : a.priority}</span>
                          )}
                          <div className="text-muted small mt-1">{a.body}</div>
                          <div className="text-muted" style={{ fontSize: '0.7rem', marginTop: '4px' }}>
                            <i className="bi bi-person me-1"></i>{a.author_name}
                            {a.created_at && <span className="ms-2"><i className="bi bi-clock me-1"></i>{formatDate(a.created_at)}</span>}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Volunteer Opportunities */}
            {shifts.length > 0 && (
              <div className="card mb-4" style={{ border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
                <div className="card-body">
                  <h5 className="fw-bold mb-3"><i className="bi bi-people me-2"></i>{t('garden.volunteerOpportunities')}</h5>
                  {shifts.slice(0, 3).map(s => (
                    <div key={s.id} style={{
                      display: 'flex', alignItems: 'center', gap: '12px',
                      padding: '12px', borderRadius: '8px', backgroundColor: '#f8f9fa', marginBottom: '8px',
                    }}>
                      <div style={{
                        width: '48px', height: '48px', borderRadius: '10px',
                        backgroundColor: '#ecf7f1', display: 'flex', alignItems: 'center', justifyContent: 'center',
                        color: 'var(--yh-ink)', fontWeight: 'bold', fontSize: '0.8rem', flexShrink: 0,
                      }}>
                        {s.shift_date && formatDate(s.shift_date + 'T00:00:00', DAY_MONTH)}
                      </div>
                      <div style={{ flex: 1 }}>
                        <strong>{s.title}</strong>
                        <div className="text-muted small">{s.start_time} - {s.end_time}</div>
                      </div>
                      <span className="badge" style={{ backgroundColor: '#22242a' }}>
                        {s.signup_count}{s.max_volunteers ? `/${s.max_volunteers}` : ''}
                      </span>
                    </div>
                  ))}
                  <button className="btn btn-sm btn-outline-success mt-2" onClick={() => setActiveTab('shifts')}>{t('garden.viewAllShifts')}</button>
                </div>
              </div>
            )}
          </div>

          <div className="col-md-4">
            {/* Growing Tools */}
            <div className="card mb-4" style={{ border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
              <div className="card-body">
                <h5 className="fw-bold mb-3"><i className="bi bi-flower1 me-2"></i>{t('garden.growingTools')}</h5>
                <div className="d-flex flex-column gap-2">
                  <Link to="/planting-calendar" className="text-decoration-none d-flex align-items-center gap-2" style={{ color: 'var(--yh-ink)' }}>
                    <i className="bi bi-calendar3"></i> {t('garden.plantingCalendar')}
                  </Link>
                  <Link to="/harvest-forecast" className="text-decoration-none d-flex align-items-center gap-2" style={{ color: 'var(--yh-ink)' }}>
                    <i className="bi bi-graph-up"></i> {t('garden.harvestForecast')}
                  </Link>
                  <Link to="/my-planting-log" className="text-decoration-none d-flex align-items-center gap-2" style={{ color: 'var(--yh-ink)' }}>
                    <i className="bi bi-journal-text"></i> {t('garden.myPlantingLog')}
                  </Link>
                </div>
              </div>
            </div>
            {/* Garden Info Card */}
            <div className="card mb-4" style={{ border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
              <div className="card-body">
                <h5 className="fw-bold mb-3">{t('garden.details')}</h5>
                <div className="mb-2">
                  <small className="text-muted">{t('garden.operatingModel')}</small>
                  <div className="fw-semibold">{t(`garden.model${(garden.operating_model || 'allotment')
                    .replace(/^./, (c) => c.toUpperCase())}`, garden.operating_model)}</div>
                </div>
                {garden.plot_fee_annual > 0 && (
                  <div className="mb-2">
                    <small className="text-muted">{t('garden.annualPlotFee')}</small>
                    <div className="fw-semibold">${Math.round(garden.plot_fee_annual)}</div>
                  </div>
                )}
                {garden.season_start && (
                  <div className="mb-2">
                    <small className="text-muted">{t('garden.season')}</small>
                    <div className="fw-semibold">
                      {formatDate(garden.season_start + 'T00:00:00', DAY_MONTH)}
                      {' - '}
                      {garden.season_end && formatDate(garden.season_end + 'T00:00:00', DAY_MONTH)}
                    </div>
                  </div>
                )}
                {garden.contact_email && (
                  <div className="mb-2">
                    <small className="text-muted">{t('garden.contact')}</small>
                    <div className="fw-semibold">{garden.contact_email}</div>
                  </div>
                )}
                <div className="mb-2">
                  <small className="text-muted">{t('garden.onWaitlist')}</small>
                  <div className="fw-semibold">{t('garden.waitlistPeople', { count: garden.waitlist_count })}</div>
                </div>
              </div>
            </div>

            {/* Join / Reserve / Waitlist Actions */}
            {user && !garden.user_is_organizer && !garden.user_has_plot && !garden.user_on_waitlist && !garden.user_has_reservation && (
              <div className="card mb-4" style={{ border: '2px solid #7fd4ab', borderRadius: '12px' }}>
                <div className="card-body text-center">
                  <h6 className="fw-bold mb-2">{t('garden.wantToJoin')}</h6>
                  {garden.available_plots > 0 ? (
                    <>
                      <p className="text-muted small mb-3">
                        <span className="badge bg-success me-1">{garden.available_plots}</span>
                        plot{garden.available_plots > 1 ? 's' : ''} available! Reserve one and the organizer will confirm your spot.
                      </p>
                      <button className="btn w-100 mb-2" style={{ backgroundColor: 'var(--yh-lime)', color: 'var(--yh-ink)' }}
                        onClick={openReserveModal}>
                        <i className="bi bi-bookmark-plus me-2"></i>{t('garden.reservePlotTitle')}
                      </button>
                      <button className="btn btn-outline-secondary btn-sm w-100"
                        onClick={() => setShowWaitlistForm(true)}>
                        <i className="bi bi-hourglass me-1"></i>{t('garden.joinWaitlistInstead')}
                      </button>
                    </>
                  ) : (
                    <>
                      <p className="text-muted small mb-3">
                        {t('garden.allPlotsTaken')}
                      </p>
                      <button className="btn w-100" style={{ backgroundColor: 'var(--yh-lime)', color: 'var(--yh-ink)' }}
                        onClick={() => setShowWaitlistForm(true)}>
                        <i className="bi bi-person-plus me-2"></i>{t('garden.joinWaitlist')}
                      </button>
                    </>
                  )}
                </div>
              </div>
            )}
            {garden.user_has_reservation && (
              <div className="alert" style={{ backgroundColor: '#fff3cd', color: '#856404', border: 'none' }}>
                <i className="bi bi-bookmark-check me-2"></i>{t('garden.pendingReservation')}
              </div>
            )}
            {garden.user_on_waitlist && (
              <div className="alert" style={{ backgroundColor: '#ecf7f1', color: 'var(--yh-ink)', border: 'none' }}>
                <i className="bi bi-hourglass-split me-2"></i>{t('garden.onWaitlistFor')}
              </div>
            )}
            {garden.user_has_plot && (
              <div className="alert" style={{ backgroundColor: '#ecf7f1', color: 'var(--yh-ink)', border: 'none' }}>
                <i className="bi bi-check-circle me-2"></i>{t('garden.youHavePlot')}
              </div>
            )}

            {/* My Dues Card */}
            {user && garden.user_has_plot && myDues.length > 0 && (
              <div className="card mb-4" style={{ border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
                <div className="card-body">
                  <h6 className="fw-bold mb-3"><i className="bi bi-receipt me-2"></i>{t('garden.myDues')}</h6>
                  {myDues.map(d => {
                    const remaining = Math.max(0, d.amount_due - d.amount_paid);
                    const isPaid = d.status === 'paid' || d.status === 'waived' || d.status === 'comp';
                    return (
                      <div key={d.id} style={{
                        padding: '12px', borderRadius: '8px', backgroundColor: '#f8f9fa', marginBottom: '8px',
                        borderLeft: `4px solid ${isPaid ? '#2aa873' : '#d99a2b'}`,
                      }}>
                        <div className="d-flex justify-content-between align-items-center">
                          <div>
                            <strong>{d.season_year}</strong>
                            <span className="ms-2 badge" style={{
                              backgroundColor: isPaid ? '#d1fae5' : '#fef3c7',
                              color: isPaid ? '#065f46' : '#92400e',
                            }}>{DUES_STATUS_KEYS[d.status] ? t(DUES_STATUS_KEYS[d.status]) : d.status}</span>
                          </div>
                          <div className="text-end">
                            <div className="fw-bold">${d.amount_due.toFixed(2)}</div>
                            {d.amount_paid > 0 && !isPaid && (
                              <div className="text-muted small">{t('garden.paidAmount', { amount: d.amount_paid.toFixed(2) })}</div>
                            )}
                          </div>
                        </div>
                        {d.payment_date && isPaid && (
                          <div className="text-muted small mt-1">
                            <i className="bi bi-check2 me-1"></i>{t('garden.paidOn', { date: formatDate(d.payment_date) })}
                            {d.payment_method && ` via ${d.payment_method}`}
                          </div>
                        )}
                        {!isPaid && remaining > 0 && (
                          <div className="mt-2">
                            {selectedDuesId === d.id && duesPayStep === 'paying' && duesSessionData ? (
                              duesSessionData.dev_mode ? (
                                <div className="text-center p-3" style={{ border: '2px dashed #22242a', borderRadius: '8px', backgroundColor: '#fff' }}>
                                  <p className="fw-bold text-success mb-1">
                                    <i className="bi bi-credit-card-2-front me-2"></i>{t('garden.testPayment')}
                                  </p>
                                  <p className="fs-5 fw-bold mb-1">${remaining.toFixed(2)}</p>
                                  <p className="text-muted small mb-2">Dev mode — no real charges</p>
                                  <button className="btn btn-success btn-sm w-100 mb-1" onClick={handleDevDuesPayment}>
                                    <i className="bi bi-check-circle me-1"></i>{t('garden.completeTestPayment')}
                                  </button>
                                  <button className="btn btn-outline-secondary btn-sm w-100" onClick={() => { setDuesPayStep('idle'); setDuesSessionData(null); setSelectedDuesId(null); }}>
                                    {t('garden.cancel')}
                                  </button>
                                </div>
                              ) : duesStripePromise && duesSessionData.client_secret ? (
                                <div>
                                  <Elements stripe={duesStripePromise} options={{ clientSecret: duesSessionData.client_secret, appearance: { theme: 'stripe' } }}>
                                    <DuesPaymentForm amount={duesSessionData.amount} onSuccess={handleDuesPaymentComplete} onCancel={() => { setDuesPayStep('idle'); setDuesSessionData(null); setSelectedDuesId(null); setDuesStripePromise(null); }} />
                                  </Elements>
                                </div>
                              ) : (
                                <div className="text-center py-2"><div className="spinner-border spinner-border-sm text-success"></div></div>
                              )
                            ) : selectedDuesId === d.id && duesPayStep === 'processing' ? (
                              <div className="text-center py-2">
                                <div className="spinner-border spinner-border-sm text-success me-2"></div>
                                {t('garden.processingPayment')}
                              </div>
                            ) : (
                              <button className="btn btn-sm w-100" style={{ backgroundColor: 'var(--yh-lime)', color: 'var(--yh-ink)' }}
                                onClick={() => handlePayDues(d.id)}>
                                <i className="bi bi-credit-card me-1"></i>{t('garden.payNowAmount', { amount: remaining.toFixed(2) })}
                              </button>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                  {duesPayError && (
                    <div className="alert alert-danger py-2 mt-2 mb-0 small">
                      <i className="bi bi-exclamation-triangle me-1"></i>{duesPayError}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Members */}
            {members.length > 0 && (
              <div className="card" style={{ border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
                <div className="card-body">
                  <h6 className="fw-bold mb-3"><i className="bi bi-people me-2"></i>{t('garden.membersWithCount', { count: members.length })}</h6>
                  {members.slice(0, 8).map((m, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                      <div style={{
                        width: '32px', height: '32px', borderRadius: '50%',
                        backgroundColor: m.role === 'organizer' ? '#22242a' : '#7fd4ab',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        color: 'white', fontSize: '0.8rem', fontWeight: 'bold',
                      }}>
                        {m.name.charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <div className="fw-semibold small">{m.name}</div>
                        <div className="text-muted" style={{ fontSize: '0.75rem' }}>
                          {m.role === 'organizer' ? t('garden.organizer') : t('garden.plotShort', { number: m.plot_number })}
                        </div>
                      </div>
                    </div>
                  ))}
                  {members.length > 8 && <p className="text-muted small mt-2">{t('garden.plusMoreCount', { count: members.length - 8 })}</p>}
                </div>
              </div>
            )}

            {/* Contact Organizer */}
            {user && !garden.user_is_organizer && (
              <div className="card mt-3" style={{ border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
                <div className="card-body">
                  {!showContactOrganizer ? (
                    <button
                      className="btn w-100"
                      style={{ backgroundColor: 'var(--yh-lime)', color: 'var(--yh-ink)', borderRadius: '8px' }}
                      onClick={() => setShowContactOrganizer(true)}
                    >
                      <i className="bi bi-envelope me-2"></i>{t('garden.contactOrganizer')}
                    </button>
                  ) : (
                    <form onSubmit={handleContactOrganizer}>
                      <h6 className="fw-bold mb-2"><i className="bi bi-envelope me-2"></i>{t('garden.messageToOrganizer', { name: garden.organizer_name })}</h6>
                      <textarea
                        className="form-control mb-2"
                        rows="3"
                        placeholder={t('garden.messagePlaceholder')}
                        value={contactMsg}
                        onChange={e => setContactMsg(e.target.value)}
                        required
                      />
                      <div className="d-flex gap-2">
                        <button type="submit" className="btn btn-sm" style={{ backgroundColor: 'var(--yh-lime)', color: 'var(--yh-ink)' }} disabled={contactSending}>
                          {contactSending ? t('garden.sending') : t('garden.send')}
                        </button>
                        <button type="button" className="btn btn-sm btn-outline-secondary" onClick={() => setShowContactOrganizer(false)}>
                          {t('garden.cancel')}
                        </button>
                      </div>
                    </form>
                  )}
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
            <h5 className="fw-bold mb-0">{t('garden.plotsTitle')}</h5>
            <div style={{ display: 'flex', gap: '12px', fontSize: '0.8rem' }}>
              {Object.entries(PLOT_COLORS).map(([status, color]) => (
                <span key={status} style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <span style={{ width: '12px', height: '12px', borderRadius: '3px', backgroundColor: color, display: 'inline-block' }}></span>
                  <span>{t(`garden.status${status.replace(/^./, (c) => c.toUpperCase())}`, status)}</span>
                </span>
              ))}
            </div>
          </div>

          {/* Visual Grid Map */}
          {(plots.some(p => p.grid_row != null) || features.length > 0) && (
            <div className="card mb-4" style={{ border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.06)', overflow: 'auto' }}>
              <div className="card-body">
                <h6 className="fw-bold mb-3"><i className="bi bi-grid-3x3-gap me-2"></i>{t('garden.map')}</h6>
                {(() => {
                  const cols = garden.grid_cols || 5;
                  const rows = garden.grid_rows || 4;
                  const CELL = 46;
                  return (
                    <div style={{
                      display: 'grid',
                      gridTemplateColumns: `repeat(${cols}, ${CELL}px)`,
                      gridTemplateRows: `repeat(${rows}, ${CELL}px)`,
                      width: cols * CELL, maxWidth: '100%',
                      backgroundSize: `${CELL}px ${CELL}px`,
                      backgroundImage: 'linear-gradient(to right,#ececdf 1px,transparent 1px),linear-gradient(to bottom,#ececdf 1px,transparent 1px)',
                    }}>
                      {features.map(f => {
                        const meta = FEATURE_META[f.feature_type] || FEATURE_META.other;
                        return (
                          <div key={`f${f.id}`} title={f.label || t(meta.labelKey)} style={{
                            gridColumn: `${f.grid_col + 1} / span ${f.grid_width || 1}`,
                            gridRow: `${f.grid_row + 1} / span ${f.grid_height || 1}`,
                            margin: 2, background: f.color || meta.color, opacity: 0.9,
                            borderRadius: f.rounded ? CELL / 2 : 6,
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            fontSize: '0.6rem', color: '#22242a', fontWeight: 600, textAlign: 'center',
                            backgroundImage: 'repeating-linear-gradient(45deg,rgba(255,255,255,.18) 0 6px,transparent 6px 12px)',
                            overflow: 'hidden', lineHeight: 1.05,
                          }}>{f.label || t(meta.labelKey)}</div>
                        );
                      })}
                      {plots.filter(p => p.grid_row != null && p.grid_col != null).map(plot => (
                        <div key={plot.id}
                          title={`${t('garden.plotNumber', { number: plot.plot_number })}${plot.custom_name ? ` "${plot.custom_name}"` : ''} — ${plotStatus(plot.status, t)}${plot.assigned_to_name ? ` (${plot.assigned_to_name})` : ''}`}
                          onClick={() => { setSelectedPlot(selectedPlot === plot.id ? null : plot.id); gardensAPI.plotHistory(id, plot.id).then(r => setPlotHistory(r.data)).catch(() => setPlotHistory(null)); }}
                          style={{
                            gridColumn: `${plot.grid_col + 1} / span ${plot.grid_width || 1}`,
                            gridRow: `${plot.grid_row + 1} / span ${plot.grid_height || 1}`,
                            margin: 2, cursor: 'pointer',
                            backgroundColor: PLOT_COLORS[plot.status] || '#6b7280',
                            color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center',
                            fontSize: '0.75rem', fontWeight: 'bold',
                            borderRadius: plot.rounded ? CELL / 2 : 6,
                            border: selectedPlot === plot.id ? '3px solid #000' : 'none',
                            opacity: plot.status === 'maintenance' ? 0.6 : 1,
                          }}>#{plot.plot_number}</div>
                      ))}
                    </div>
                  );
                })()}
                {/* Selected Plot Detail */}
                {selectedPlot && (() => {
                  const p = plots.find(pl => pl.id === selectedPlot);
                  if (!p) return null;
                  const isMyPlot = user && p.assigned_to_id === user.id;
                  return (
                    <div className="mt-3 p-3" style={{ backgroundColor: '#f8f9fa', borderRadius: '8px' }}>
                      <div className="d-flex justify-content-between">
                        <div>
                          <strong>Plot #{p.plot_number}</strong>
                          {p.custom_name && <span className="ms-1 fst-italic" style={{ color: '#16181d' }}>"{p.custom_name}"</span>}
                          <span className="badge ms-2" style={{ backgroundColor: PLOT_COLORS[p.status] }}>{plotStatus(p.status, t)}</span>
                          {p.assigned_to_name && <span className="ms-2"><i className="bi bi-person me-1"></i>{p.assigned_to_name}</span>}
                        </div>
                        <button className="btn btn-sm btn-outline-secondary" onClick={() => { setSelectedPlot(null); setEditingPlotName(false); }}>{t('garden.close')}</button>
                      </div>
                      <div className="text-muted small mt-1">
                        {p.size && <span className="me-3">Size: {p.size}</span>}
                        {p.soil_type && <span className="me-3">Soil: {p.soil_type}</span>}
                        {p.sun_exposure && <span>Sun: {p.sun_exposure.replace('_', ' ')}</span>}
                      </div>
                      {/* Plot Rename — only for the assigned owner */}
                      {isMyPlot && (
                        <div className="mt-2">
                          {editingPlotName ? (
                            <div className="d-flex align-items-center gap-2">
                              <input type="text" className="form-control form-control-sm" style={{ maxWidth: '220px' }}
                                placeholder="e.g. Sunny Corner" value={plotNameInput} maxLength={100}
                                onChange={e => setPlotNameInput(e.target.value)}
                                onKeyDown={e => { if (e.key === 'Enter') {
                                  setPlotNameSaving(true);
                                  gardensAPI.renamePlot(id, p.id, { custom_name: plotNameInput }).then(() => {
                                    gardensAPI.plots(id).then(r => setPlots(r.data));
                                    setEditingPlotName(false);
                                  }).finally(() => setPlotNameSaving(false));
                                }}}
                                autoFocus />
                              <button className="btn btn-sm btn-success" disabled={plotNameSaving} onClick={() => {
                                setPlotNameSaving(true);
                                gardensAPI.renamePlot(id, p.id, { custom_name: plotNameInput }).then(() => {
                                  gardensAPI.plots(id).then(r => setPlots(r.data));
                                  setEditingPlotName(false);
                                }).finally(() => setPlotNameSaving(false));
                              }}>{plotNameSaving ? '…' : t('garden.save')}</button>
                              <button className="btn btn-sm btn-outline-secondary" onClick={() => setEditingPlotName(false)}>{t('garden.cancel')}</button>
                            </div>
                          ) : (
                            <button className="btn btn-sm btn-outline-primary mt-1" onClick={() => { setPlotNameInput(p.custom_name || ''); setEditingPlotName(true); }}>
                              <i className="bi bi-pencil me-1"></i>{p.custom_name ? t('garden.renamePlot') : t('garden.namePlot')}
                            </button>
                          )}
                        </div>
                      )}
                      {plotHistory && plotHistory.length > 0 && (
                        <div className="mt-2">
                          <div className="fw-semibold small">{t('garden.assignmentHistory')}</div>
                          {plotHistory.map(h => (
                            <div key={h.id} className="small text-muted">{h.season_year}: {h.user_name} ({h.assigned_date}{h.released_date ? ` — ${h.released_date}` : ' — present'})</div>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })()}
              </div>
            </div>
          )}

          {/* Plot Cards */}
          <div className="row g-2">
            {plots.map(plot => {
              const cardContent = (
                <>
                  <div style={{ fontSize: '1.2rem', fontWeight: 'bold', color: PLOT_COLORS[plot.status] }}>
                    #{plot.plot_number}
                  </div>
                  {plot.custom_name && <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#16181d', fontStyle: 'italic' }}>{plot.custom_name}</div>}
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
                  }}>{plotStatus(plot.status, t)}</span>
                  {plot.status === 'available' && user && (
                    <div style={{ fontSize: '0.7rem', color: 'var(--yh-ink)', marginTop: '6px', fontWeight: 600 }}>
                      {t('garden.clickToReserve')}
                    </div>
                  )}
                  {plot.status === 'available' && !user && (
                    <div style={{ fontSize: '0.7rem', color: 'var(--yh-ink)', marginTop: '6px', fontWeight: 600 }}>
                      {t('garden.signUpToReserve')}
                    </div>
                  )}
                </>
              );

              const cardStyle = {
                border: `2px solid ${PLOT_COLORS[plot.status] || '#6b7280'}`,
                borderRadius: '10px',
                padding: '16px',
                textAlign: 'center',
                backgroundColor: plot.status === 'available' ? '#ecf7f1' : '#fff',
                minHeight: '100px',
                ...(plot.status === 'available' && user ? { cursor: 'pointer' } : {}),
              };

              return (
                <div key={plot.id} className="col-6 col-md-4 col-lg-3">
                  {plot.status === 'available' && !user ? (
                    <Link to="/register" style={{ textDecoration: 'none', color: 'inherit' }}>
                      <div style={cardStyle}>
                        {cardContent}
                      </div>
                    </Link>
                  ) : plot.status === 'available' && user ? (
                    <div style={cardStyle} onClick={openReserveModal}>
                      {cardContent}
                    </div>
                  ) : (
                    <div style={cardStyle}>
                      {cardContent}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
          {plots.length === 0 && (
            <div className="text-center text-muted py-4">
              <i className="bi bi-grid-3x3-gap d-block mb-2" style={{ fontSize: '2rem', color: '#ccc' }}></i>
              This garden is just getting started — plots will appear here soon. Check back or join the waitlist to be first in line.
            </div>
          )}
        </div>
      )}

      {/* Resources Tab */}
      {activeTab === 'resources' && (
        <div>
          <div className="d-flex justify-content-between align-items-center mb-3">
            <h5 className="fw-bold mb-0">{t('garden.resourcesTitle')}</h5>
            {user && garden.user_is_organizer && (
              <button className="btn btn-sm" style={{ backgroundColor: 'var(--yh-lime)', color: 'var(--yh-ink)' }}
                onClick={() => setShowResourceForm(!showResourceForm)}>
                <i className="bi bi-plus-circle me-1"></i>{t('garden.addResource')}
              </button>
            )}
          </div>

          {showResourceForm && (
            <div className="card mb-4" style={{ border: '2px solid #7fd4ab' }}>
              <div className="card-body">
                <form onSubmit={handleAddResource}>
                  <div className="row g-3">
                    <div className="col-md-4">
                      <label className="form-label">{t('garden.name')}</label>
                      <input type="text" className="form-control" required
                        value={resourceForm.name} onChange={e => setResourceForm({ ...resourceForm, name: e.target.value })} />
                    </div>
                    <div className="col-md-3">
                      <label className="form-label">{t('garden.type')}</label>
                      <select className="form-select" value={resourceForm.resource_type}
                        onChange={e => setResourceForm({ ...resourceForm, resource_type: e.target.value })}>
                        <option value="tool">{t('garden.typeTool')}</option>
                        <option value="supply">{t('garden.typeSupply')}</option>
                        <option value="infrastructure">{t('garden.typeInfrastructure')}</option>
                      </select>
                    </div>
                    <div className="col-md-2">
                      <label className="form-label">{t('garden.qty')}</label>
                      <input type="number" className="form-control" min="1"
                        value={resourceForm.quantity}
                        onChange={e => { const v = parseInt(e.target.value, 10); setResourceForm({ ...resourceForm, quantity: Number.isNaN(v) ? '' : v }); }} />
                    </div>
                    <div className="col-md-3">
                      <label className="form-label">{t('garden.condition')}</label>
                      <select className="form-select" value={resourceForm.condition}
                        onChange={e => setResourceForm({ ...resourceForm, condition: e.target.value })}>
                        <option value="new">{t('garden.conditionNew')}</option>
                        <option value="good">{t('garden.conditionGood')}</option>
                        <option value="fair">{t('garden.conditionFair')}</option>
                        <option value="needs_repair">{t('garden.conditionNeedsRepair')}</option>
                      </select>
                    </div>
                    <div className="col-12">
                      <label className="form-label">{t('garden.description')}</label>
                      <input type="text" className="form-control"
                        value={resourceForm.description} onChange={e => setResourceForm({ ...resourceForm, description: e.target.value })} />
                    </div>
                    <div className="col-12">
                      <button type="submit" className="btn me-2" style={{ backgroundColor: 'var(--yh-lime)', color: 'var(--yh-ink)' }}>Add</button>
                      <button type="button" className="btn btn-outline-secondary" onClick={() => setShowResourceForm(false)}>{t('garden.cancel')}</button>
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
                  <th>{t('garden.name')}</th>
                  <th>{t('garden.type')}</th>
                  <th>{t('garden.qty')}</th>
                  <th>{t('garden.condition')}</th>
                  <th>{t('garden.status')}</th>
                  <th>{t('garden.actions')}</th>
                </tr>
              </thead>
              <tbody>
                {resources.map(res => (
                  <tr key={res.id}>
                    <td>
                      <strong>{res.name}</strong>
                      {res.description && <div className="text-muted small">{res.description}</div>}
                    </td>
                    <td><span>{t(`garden.type${res.resource_type.replace(/^./, (c) => c.toUpperCase())}`, res.resource_type)}</span></td>
                    <td>{res.quantity}</td>
                    <td>
                      <span style={{
                        backgroundColor: RESOURCE_CONDITION_COLORS[res.condition] || '#6b7280',
                        color: 'white', padding: '2px 8px', borderRadius: '8px', fontSize: '0.75rem',
                      }}>{res.condition?.replace('_', ' ')}</span>
                    </td>
                    <td>
                      {res.checked_out_to_id ? (
                        <div>
                          <span className={`small ${res.is_overdue ? 'text-danger fw-bold' : 'text-warning'}`}>
                            <i className={`bi ${res.is_overdue ? 'bi-exclamation-triangle' : 'bi-arrow-up-right'} me-1`}></i>
                            {res.checked_out_to_name}
                          </span>
                          {res.due_date && (
                            <div className={`small ${res.is_overdue ? 'text-danger' : 'text-muted'}`}>
                              Due: {formatDate(res.due_date)}
                              {res.is_overdue && ' (OVERDUE)'}
                            </div>
                          )}
                        </div>
                      ) : (
                        <span className="text-success small"><i className="bi bi-check-circle me-1"></i>{t('garden.available')}</span>
                      )}
                    </td>
                    <td>
                      {user && !res.checked_out_to_id && (
                        <button className="btn btn-sm btn-outline-success" onClick={() => { setShowCheckoutModal(res.id); setCheckoutDuration(3); }}>{t('garden.checkOut')}</button>
                      )}
                      {user && res.checked_out_to_id === user.id && (
                        <button className="btn btn-sm btn-outline-primary" onClick={() => handleReturn(res.id)}>{t('garden.returnItem')}</button>
                      )}
                    </td>
                  </tr>
                ))}
                {resources.length === 0 && (
                  <tr><td colSpan="6" className="text-center text-muted py-4">{t('garden.noResources')}</td></tr>
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
            <h5 className="fw-bold mb-0">{t('garden.eventsTitle')}</h5>
            {user && (
              <Link to={`/gardens/${id}/events`} className="btn btn-sm" style={{ backgroundColor: 'var(--yh-lime)', color: 'var(--yh-ink)' }}>
                <i className="bi bi-plus-circle me-1"></i>{t('garden.manageEvents')}
              </Link>
            )}
          </div>

          {events.length === 0 ? (
            <p className="text-muted text-center py-4">{t('garden.noEvents')}</p>
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
                          {isPast && <span className="badge bg-secondary">{t('garden.past')}</span>}
                        </div>
                        <h6 className="fw-bold mb-1">{event.title}</h6>
                        <p className="text-muted small mb-2">
                          <i className="bi bi-calendar me-1"></i>
                          {formatDate(eventDate, WEEKDAY_DAY_MONTH)} at{' '}
                          {formatTime(eventDate, HOUR_MINUTE)}
                          <span className="ms-2"><i className="bi bi-clock me-1"></i>{event.duration_hours}h</span>
                        </p>
                        {event.description && <p className="small mb-2">{event.description}</p>}
                        <div className="d-flex justify-content-between align-items-center">
                          <span className="small text-muted">
                            <i className="bi bi-people me-1"></i>{t('garden.rsvpGoingCount', { count: event.rsvp_going })}
                            {event.rsvp_maybe > 0 && t('garden.rsvpMaybeSuffix', { count: event.rsvp_maybe })}
                            {event.max_volunteers && ` / ${event.max_volunteers} max`}
                          </span>
                          {user && !isPast && (
                            <div className="d-flex gap-1">
                              {event.user_rsvp === 'going' ? (
                                <button className="btn btn-sm btn-success" disabled>{t('garden.going')}</button>
                              ) : (
                                <button className="btn btn-sm btn-outline-success" onClick={() => handleRsvp(event.id, 'going')}>{t('garden.going')}</button>
                              )}
                              {event.user_rsvp === 'maybe' ? (
                                <button className="btn btn-sm btn-warning" disabled>{t('garden.maybe')}</button>
                              ) : (
                                <button className="btn btn-sm btn-outline-warning" onClick={() => handleRsvp(event.id, 'maybe')}>{t('garden.maybe')}</button>
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
            <h5 className="fw-bold mb-0">{t('garden.harvestTitle')}</h5>
            {user && (
              <button className="btn btn-sm" style={{ backgroundColor: 'var(--yh-lime)', color: 'var(--yh-ink)' }}
                onClick={() => setShowHarvestForm(!showHarvestForm)}>
                <i className="bi bi-plus-circle me-1"></i>{t('garden.logHarvest')}
              </button>
            )}
          </div>

          {showHarvestForm && (
            <div className="card mb-4" style={{ border: '2px solid #7fd4ab' }}>
              <div className="card-body">
                <h6 className="fw-bold mb-3">{t('garden.logAHarvest')}</h6>
                <form onSubmit={handleLogHarvest}>
                  <div className="row g-3">
                    <div className="col-md-3">
                      <label className="form-label">{t('garden.category')}</label>
                      <select className="form-select" required
                        value={harvestForm.category} onChange={e => setHarvestForm({ ...harvestForm, category: e.target.value })}>
                        <option value="">{t('garden.select')}</option>
                        <option value="tomatoes">{t('garden.catTomatoes')}</option>
                        <option value="peppers">{t('garden.catPeppers')}</option>
                        <option value="greens">{t('garden.catGreens')}</option>
                        <option value="herbs">{t('garden.catHerbs')}</option>
                        <option value="squash">{t('garden.catSquash')}</option>
                        <option value="beans">{t('garden.catBeans')}</option>
                        <option value="root_vegetables">{t('garden.catRootVegetables')}</option>
                        <option value="corn">{t('garden.catCorn')}</option>
                        <option value="berries">{t('garden.catBerries')}</option>
                        <option value="other">{t('garden.catOther')}</option>
                      </select>
                    </div>
                    <div className="col-md-3">
                      <label className="form-label">{t('garden.variety')}</label>
                      <input type="text" className="form-control" placeholder="e.g. Cherokee Purple"
                        value={harvestForm.variety} onChange={e => setHarvestForm({ ...harvestForm, variety: e.target.value })} />
                    </div>
                    <div className="col-md-2">
                      <label className="form-label">{t('garden.pounds')}</label>
                      <input type="number" className="form-control" step="0.1" min="0.1" required
                        value={harvestForm.quantity_lbs} onChange={e => setHarvestForm({ ...harvestForm, quantity_lbs: e.target.value })} />
                    </div>
                    <div className="col-md-2">
                      <label className="form-label">{t('garden.date')}</label>
                      <input type="date" className="form-control" required
                        value={harvestForm.harvest_date} onChange={e => setHarvestForm({ ...harvestForm, harvest_date: e.target.value })} />
                    </div>
                    <div className="col-md-2">
                      <label className="form-label">{t('garden.destination')}</label>
                      <select className="form-select" value={harvestForm.destination}
                        onChange={e => setHarvestForm({ ...harvestForm, destination: e.target.value })}>
                        <option value="personal">{t('garden.destPersonal')}</option>
                        <option value="shared">{t('garden.destShared')}</option>
                        <option value="food_bank">{t('garden.destFoodBank')}</option>
                        <option value="marketplace">{t('garden.destMarketplace')}</option>
                      </select>
                    </div>
                    <div className="col-12">
                      <button type="submit" className="btn me-2" style={{ backgroundColor: 'var(--yh-lime)', color: 'var(--yh-ink)' }}>{t('garden.logHarvest')}</button>
                      <button type="button" className="btn btn-outline-secondary" onClick={() => setShowHarvestForm(false)}>{t('garden.cancel')}</button>
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
                  <th>{t('garden.date')}</th>
                  <th>{t('garden.gardener')}</th>
                  <th>{t('garden.category')}</th>
                  <th>{t('garden.variety')}</th>
                  <th>{t('garden.pounds')}</th>
                  <th>{t('garden.destination')}</th>
                </tr>
              </thead>
              <tbody>
                {harvests.map(h => (
                  <tr key={h.id}>
                    <td>{formatDate(h.harvest_date + 'T00:00:00', DAY_MONTH)}</td>
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
                  <tr><td colSpan="6" className="text-center text-muted py-4">{t('garden.noHarvests')}</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Volunteer Shifts Tab */}
      {activeTab === 'shifts' && (
        <div>
          <h5 className="fw-bold mb-3">{t('garden.shiftsTitle')}</h5>

          {user && volunteerHours && (
            <div className="card mb-3" style={{ border: 'none', borderLeft: '4px solid #22242a', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
              <div className="card-body py-2">
                <div className="d-flex gap-4">
                  <div><strong style={{ color: 'var(--yh-ink)' }}>{volunteerHours.total_hours.toFixed(1)}</strong> <span className="text-muted small">hours</span></div>
                  <div><strong>{volunteerHours.shifts_attended}</strong> <span className="text-muted small">shifts attended</span></div>
                  <div><strong>{volunteerHours.total_signups}</strong> <span className="text-muted small">total signups</span></div>
                </div>
              </div>
            </div>
          )}

          {shifts.length === 0 ? (
            <p className="text-muted">{t('garden.noShifts')}</p>
          ) : (
            <div className="row g-3">
              {shifts.map(s => (
                <div key={s.id} className="col-md-6">
                  <div className="card h-100" style={{ border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
                    <div className="card-body">
                      <h6 className="fw-bold mb-1">{s.title}</h6>
                      <div className="text-muted small mb-2">
                        <i className="bi bi-calendar me-1"></i>{s.shift_date} &middot; {s.start_time} - {s.end_time}
                      </div>
                      {s.description && <p className="small mb-2">{s.description}</p>}
                      <div className="d-flex justify-content-between align-items-center">
                        <span className="badge" style={{ backgroundColor: '#22242a' }}>
                          {t('garden.signedUpCount', {
                            count: s.max_volunteers ? `${s.signup_count}/${s.max_volunteers}` : s.signup_count,
                          })}
                        </span>
                        {user && (
                          s.user_signed_up ? (
                            <button className="btn btn-sm btn-outline-danger" onClick={() => {
                              gardensAPI.cancelShiftSignup(id, s.id).then(() => {
                                gardensAPI.shifts(id).then(r => setShifts(r.data));
                                gardensAPI.volunteerHours(id).then(r => setVolunteerHours(r.data));
                              });
                            }}>{t('garden.cancelSignup')}</button>
                          ) : (
                            <button className="btn btn-sm" style={{ backgroundColor: 'var(--yh-lime)', color: 'var(--yh-ink)' }}
                              disabled={s.spots_left === 0}
                              onClick={() => {
                                gardensAPI.signupShift(id, s.id).then(() => {
                                  gardensAPI.shifts(id).then(r => setShifts(r.data));
                                  gardensAPI.volunteerHours(id).then(r => setVolunteerHours(r.data));
                                }).catch(err => toast(err.response?.data?.error || t('garden.errGeneric'), { type: 'error' }));
                              }}>
                              {s.spots_left === 0 ? t('garden.full') : t('garden.signUp')}
                            </button>
                          )
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}


      {/* Community Tab — photo wall + comment wall */}
      {activeTab === 'community' && (
        <div className="row">
          {/* Photo Wall — Garden Pro feature; hidden for non-Pro gardens */}
          {!photosProRequired && (
          <div className="col-lg-7 mb-4">
            <div className="d-flex justify-content-between align-items-center mb-3">
              <h5 className="fw-bold mb-0"><i className="bi bi-images me-2"></i>{t('garden.photoWall')}</h5>
              {user && (
                <label className="btn btn-sm mb-0" style={{ backgroundColor: 'var(--yh-lime)', color: 'var(--yh-ink)', cursor: 'pointer' }}>
                  {photoUploading ? (
                    <><span className="spinner-border spinner-border-sm me-1"></span>{t('garden.uploading')}</>
                  ) : (
                    <><i className="bi bi-camera me-1"></i>{t('garden.addPhoto')}</>
                  )}
                  <input type="file" accept="image/*" hidden onChange={handlePhotoUpload} disabled={photoUploading} />
                </label>
              )}
            </div>
            {photos.length === 0 ? (
              <p className="text-muted text-center py-4">No photos yet. {user ? t('garden.beFirst') : ''}</p>
            ) : (
              <div className="row g-2">
                {photos.map(p => {
                  const canDelete = p.can_delete ?? (user && (p.user_id === user.id || garden.user_is_organizer || user.is_admin));
                  const src = p.url || `${IMAGE_BASE}${p.filename}`;
                  return (
                    <div key={p.id} className="col-6 col-md-4">
                      <div style={{ borderRadius: '10px', overflow: 'hidden', boxShadow: '0 2px 8px rgba(0,0,0,0.08)', background: 'white' }}>
                        <div style={{ position: 'relative' }}>
                          <img src={src} alt={p.caption || 'Garden photo'}
                            style={{ width: '100%', height: '140px', objectFit: 'cover', display: 'block', cursor: 'zoom-in' }}
                            onClick={() => lightbox(src, { alt: p.caption || 'Garden photo', caption: p.caption })} />
                          {canDelete && (
                            <button
                              className="btn btn-sm btn-danger"
                              title={t('garden.deletePhoto')}
                              style={{ position: 'absolute', top: '6px', right: '6px', padding: '2px 8px', opacity: 0.9 }}
                              onClick={(e) => { e.stopPropagation(); handleDeletePhoto(p.id); }}>
                              <i className="bi bi-trash"></i>
                            </button>
                          )}
                          <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, background: 'linear-gradient(transparent, rgba(0,0,0,0.65))', color: 'white', padding: '14px 8px 6px', fontSize: '0.72rem' }}>
                            {p.caption && <div className="text-truncate">{p.caption}</div>}
                            <div style={{ opacity: 0.85 }}><i className="bi bi-person me-1"></i>{p.user_name}</div>
                          </div>
                        </div>
                        <div className="d-flex align-items-center gap-3 px-2 py-1">
                          <button type="button" className="btn btn-sm p-0 border-0 bg-transparent d-inline-flex align-items-center"
                            style={{ color: p.liked_by_me ? '#3b6d11' : 'var(--yh-muted)', fontSize: '0.8rem' }}
                            onClick={() => handleLikePhoto(p.id)} title={user ? t('garden.upvote') : t('garden.signInToUpvote')}>
                            <i className={`bi ${p.liked_by_me ? 'bi-hand-thumbs-up-fill' : 'bi-hand-thumbs-up'} me-1`}></i>
                            {p.likes_count > 0 ? p.likes_count : t('garden.upvote')}
                          </button>
                          <button type="button" className="btn btn-sm p-0 border-0 bg-transparent d-inline-flex align-items-center"
                            style={{ fontSize: '0.8rem', color: openPhoto === p.id ? 'var(--yh-ink)' : 'var(--yh-muted)' }}
                            onClick={() => handleTogglePhotoComments(p.id)} title={t('garden.comments')}>
                            <i className="bi bi-chat me-1"></i>
                            {p.comments_count > 0 ? p.comments_count : 'Comment'}
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Expanded comments for the selected photo */}
            {openPhoto && (() => {
              const p = photos.find(x => x.id === openPhoto);
              if (!p) return null;
              const list = photoComments[openPhoto] || [];
              return (
                <div className="card mt-3" style={{ border: '1px solid #e5e6e6', borderRadius: '12px' }}>
                  <div className="card-body py-3">
                    <div className="d-flex justify-content-between align-items-center mb-2">
                      <h6 className="fw-bold mb-0"><i className="bi bi-chat-dots me-2"></i>{p.caption ? t('garden.commentsFor', { caption: p.caption }) : t('garden.comments')}</h6>
                      <button className="btn btn-sm btn-link text-muted p-0" onClick={() => setOpenPhoto(null)} title={t('garden.close')}><i className="bi bi-x-lg"></i></button>
                    </div>
                    {list.length === 0 ? (
                      <p className="text-muted small mb-2">{t('garden.noCommentsYet')}{user ? ` ${t('garden.beTheFirst')}` : ''}</p>
                    ) : (
                      <div className="mb-2">
                        {list.map(c => {
                          // Three groups only: the comment's creator, the garden admin (organizer), or a site admin.
                          const canDeleteComment = user && (c.user_id === user.id || garden.user_is_organizer || user.is_admin);
                          return (
                            <div key={c.id} className="d-flex justify-content-between align-items-start py-1" style={{ borderBottom: '1px solid #f1f2f2' }}>
                              <div className="small">
                                <span className="fw-semibold">{c.user_name}</span>{' '}
                                <span style={{ whiteSpace: 'pre-wrap' }}>{c.content}</span>
                                {c.created_at && <span className="text-muted ms-2" style={{ fontSize: '0.7rem' }}>{formatDate(c.created_at)}</span>}
                              </div>
                              {canDeleteComment && (
                                <button className="btn btn-sm btn-link text-danger p-0 ms-2" title={t('garden.deleteComment')} onClick={() => handleDeletePhotoComment(p.id, c.id)}>
                                  <i className="bi bi-trash" style={{ fontSize: '0.7rem' }}></i>
                                </button>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}
                    {user ? (
                      <div className="d-flex gap-2">
                        <input type="text" className="form-control form-control-sm" placeholder={t('garden.addComment')} maxLength={1000}
                          value={photoCommentText} onChange={e => setPhotoCommentText(e.target.value)}
                          onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); handleAddPhotoComment(p.id); } }} />
                        <button className="btn btn-sm" style={{ backgroundColor: 'var(--yh-lime)', color: 'var(--yh-ink)' }}
                          disabled={photoCommentPosting || !photoCommentText.trim()} onClick={() => handleAddPhotoComment(p.id)}>
                          {photoCommentPosting ? '…' : t('garden.post')}
                        </button>
                      </div>
                    ) : (
                      <p className="text-muted small mb-0"><Link to="/login">{t('garden.signIn')}</Link> to comment.</p>
                    )}
                  </div>
                </div>
              );
            })()}
          </div>
          )}

          {/* Comment Wall */}
          <div className={photosProRequired ? 'col-12' : 'col-lg-5'}>
            <h5 className="fw-bold mb-3"><i className="bi bi-chat-dots me-2"></i>{t('garden.commentWall')}</h5>
            {user ? (
              <form onSubmit={handlePostComment} className="mb-3">
                <textarea
                  className="form-control mb-2"
                  rows="2"
                  placeholder={t('garden.commentPlaceholder')}
                  maxLength={1000}
                  value={commentBody}
                  onChange={e => { setCommentBody(e.target.value); setCommentError(''); }}
                />
                {commentError && (
                  <div className="alert alert-warning py-2 mb-2 small">
                    <i className="bi bi-shield-exclamation me-1"></i>{commentError}
                  </div>
                )}
                <button type="submit" className="btn btn-sm" style={{ backgroundColor: 'var(--yh-lime)', color: 'var(--yh-ink)' }} disabled={commentPosting || !commentBody.trim()}>
                  {commentPosting ? <><span className="spinner-border spinner-border-sm me-1"></span>{t('garden.posting')}</> : <><i className="bi bi-send me-1"></i>{t('garden.post')}</>}
                </button>
              </form>
            ) : (
              <p className="text-muted small mb-3"><Link to="/login">{t('garden.signIn')}</Link> to join the conversation.</p>
            )}
            {comments.length === 0 ? (
              <p className="text-muted text-center py-3">{t('garden.noComments')}</p>
            ) : (
              comments.filter(c => !c.parent_id).map(top => {
                const replies = comments
                  .filter(r => r.parent_id === top.id)
                  .sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
                return (
                  <div key={top.id}>
                    {renderComment(top, false)}
                    {(replies.length > 0 || replyTo === top.id) && (
                      <div style={{ marginLeft: '18px', borderLeft: '2px solid #e5e6e6', paddingLeft: '10px' }}>
                        {replies.map(r => renderComment(r, true))}
                        {replyTo === top.id && (
                          <div className="mb-2">
                            <textarea className="form-control form-control-sm mb-1" rows="2"
                              placeholder={t('garden.replyTo', { name: top.author_name })} maxLength={1000}
                              value={replyBody} onChange={e => setReplyBody(e.target.value)} />
                            <button className="btn btn-sm me-1" style={{ backgroundColor: 'var(--yh-lime)', color: 'var(--yh-ink)' }}
                              disabled={replyPosting || !replyBody.trim()} onClick={() => handleReply(top.id)}>
                              {replyPosting ? t('garden.postingEllipsis') : t('garden.reply')}
                            </button>
                            <button className="btn btn-sm btn-link text-muted" onClick={() => { setReplyTo(null); setReplyBody(''); }}>{t('garden.cancel')}</button>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}

      {/* Impact Tab — hidden for now, keeping backend + GardenImpact.jsx for future use */}

      {/* Waitlist Form Modal (overlay) */}
      {showWaitlistForm && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.5)', zIndex: 1050,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }} onClick={() => setShowWaitlistForm(false)}>
          <div className="card" style={{ maxWidth: '480px', width: '90%' }} onClick={e => e.stopPropagation()}>
            <div className="card-body">
              <h5 className="fw-bold mb-3">{t('garden.joinWaitlistFor', { name: garden.name })}</h5>
              <form onSubmit={handleJoinWaitlist}>
                <div className="mb-3">
                  <label className="form-label">{t('garden.preferredPlotSize')}</label>
                  <input type="text" className="form-control" placeholder="e.g. 4x8 ft"
                    value={waitlistForm.plot_size_pref}
                    onChange={e => setWaitlistForm({ ...waitlistForm, plot_size_pref: e.target.value })} />
                </div>
                <div className="mb-3">
                  <label className="form-label">{t('garden.notesForOrganizer')}</label>
                  <textarea className="form-control" rows="3" placeholder={t('garden.notesPlaceholder')}
                    value={waitlistForm.notes}
                    onChange={e => setWaitlistForm({ ...waitlistForm, notes: e.target.value })} />
                </div>
                <div className="d-flex gap-2">
                  <button type="submit" className="btn" style={{ backgroundColor: 'var(--yh-lime)', color: 'var(--yh-ink)' }}>
                    <i className="bi bi-person-plus me-2"></i>{t('garden.joinWaitlist')}
                  </button>
                  <button type="button" className="btn btn-outline-secondary" onClick={() => setShowWaitlistForm(false)}>{t('garden.cancel')}</button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* Checkout Duration Modal (overlay) */}
      {showCheckoutModal && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.5)', zIndex: 1050,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }} onClick={() => setShowCheckoutModal(null)}>
          <div className="card" style={{ maxWidth: '400px', width: '90%' }} onClick={e => e.stopPropagation()}>
            <div className="card-body text-center">
              <h5 className="fw-bold mb-3"><i className="bi bi-box-arrow-up-right me-2"></i>{t('garden.checkOutTool')}</h5>
              <p className="text-muted small mb-3">{t('garden.howLong')}</p>
              <div className="d-flex gap-2 justify-content-center mb-4">
                {[1, 3, 7].map(d => (
                  <button key={d}
                    className={`btn ${checkoutDuration === d ? 'btn-success' : 'btn-outline-success'} px-4`}
                    onClick={() => setCheckoutDuration(d)}>
                    {d} day{d > 1 ? 's' : ''}
                  </button>
                ))}
              </div>
              <div className="d-flex gap-2 justify-content-center">
                <button className="btn" style={{ backgroundColor: 'var(--yh-lime)', color: 'var(--yh-ink)' }}
                  onClick={() => handleCheckout(showCheckoutModal, checkoutDuration)}>
                  <i className="bi bi-check-lg me-1"></i>{t('garden.confirmCheckout')}
                </button>
                <button className="btn btn-outline-secondary" onClick={() => setShowCheckoutModal(null)}>{t('garden.cancel')}</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Reserve Plot Modal (overlay) */}
      {showReserveModal && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.5)', zIndex: 1050,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }} onClick={() => setShowReserveModal(false)}>
          <div className="card" style={{ maxWidth: '500px', width: '90%' }} onClick={e => e.stopPropagation()}>
            <div className="card-body">
              <h5 className="fw-bold mb-3"><i className="bi bi-bookmark-plus me-2"></i>{t('garden.reservePlotTitle')}</h5>
              <p className="text-muted small mb-3">
                {t('garden.selectAvailablePlot')}
              </p>
              {availablePlots.length === 0 ? (
                <div className="alert alert-warning mb-0">{t('garden.noPlotsAvailable')}</div>
              ) : (
                <div className="list-group">
                  {availablePlots.map(plot => (
                    <button key={plot.id} className="list-group-item list-group-item-action d-flex justify-content-between align-items-center"
                      onClick={() => handleReservePlot(plot.id)} disabled={reserving}>
                      <div>
                        <strong>Plot #{plot.plot_number}</strong>
                        {plot.size && <span className="text-muted ms-2">({plot.size})</span>}
                        {plot.location_notes && <div className="text-muted small">{plot.location_notes}</div>}
                      </div>
                      <span className="badge" style={{ backgroundColor: '#2aa873' }}>{t('garden.available')}</span>
                    </button>
                  ))}
                </div>
              )}
              <div className="mt-3">
                <button className="btn btn-outline-secondary w-100" onClick={() => setShowReserveModal(false)}>{t('garden.cancel')}</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
