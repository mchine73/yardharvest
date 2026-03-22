import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
});

// ---- Auth ----
export const authAPI = {
  me: () => api.get('/auth/me'),
  login: (email, password) => api.post('/auth/login', { email, password }),
  register: (data) => api.post('/auth/register', data),
  logout: () => api.post('/auth/logout'),
  forgotPassword: (email) => api.post('/auth/forgot-password', { email }),
  resetPassword: (token, password) => api.post('/auth/reset-password', { token, password }),
};

// ---- Listings ----
export const listingsAPI = {
  featured: (params) => api.get('/listings/featured', { params }),
  browse: (params) => api.get('/listings/browse', { params }),
  search: (params) => api.get('/listings/search', { params }),
  detail: (id) => api.get(`/listings/${id}`),
  categories: () => api.get('/listings/categories'),
  mine: () => api.get('/listings/mine'),
  create: (formData) => api.post('/listings', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
  update: (id, formData) => api.put(`/listings/${id}`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
  toggle: (id) => api.post(`/listings/${id}/toggle`),
  delete: (id) => api.delete(`/listings/${id}`),
};

// ---- Cart ----
export const cartAPI = {
  get: () => api.get('/cart'),
  add: (listingId, quantity = 1) => api.post(`/cart/add/${listingId}`, { quantity }),
  update: (itemId, quantity) => api.put(`/cart/update/${itemId}`, { quantity }),
  remove: (itemId) => api.delete(`/cart/remove/${itemId}`),
  checkout: (data) => api.post('/cart/checkout', data),
  count: () => api.get('/cart/count'),
};

// ---- Payments (Gr4vy) ----
export const paymentAPI = {
  createSession: (data) => api.post('/payments/create-session', data || {}),
  confirmPayment: (data) => api.post('/payments/confirm', data),
};

// ---- Orders ----
export const ordersAPI = {
  mine: () => api.get('/orders/mine'),
  selling: () => api.get('/orders/selling'),
  detail: (id) => api.get(`/orders/${id}`),
  accept: (id) => api.post(`/orders/${id}/accept`),
  complete: (id) => api.post(`/orders/${id}/complete`),
  cancel: (id) => api.post(`/orders/${id}/cancel`),
};

// ---- Messages ----
export const messagesAPI = {
  inbox: () => api.get('/messages/inbox'),
  thread: (threadId) => api.get(`/messages/thread/${threadId}`),
  send: (data) => api.post('/messages/send', data),
  unreadCount: () => api.get('/messages/unread_count'),
};

// ---- Profile ----
export const profileAPI = {
  get: (userId) => api.get(`/profile/${userId}`),
  update: (formData) => api.put('/profile/edit', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
  dashboard: () => api.get('/profile/dashboard'),
  leaveReview: (orderId, data) => api.post(`/profile/reviews/${orderId}`, data),
};

// ---- Admin ----
export const adminAPI = {
  dashboard: () => api.get('/admin/dashboard'),
  users: (params) => api.get('/admin/users', { params }),
  toggleUserActive: (id) => api.post(`/admin/users/${id}/toggle-active`),
  toggleUserAdmin: (id) => api.post(`/admin/users/${id}/toggle-admin`),
  listings: (params) => api.get('/admin/listings', { params }),
  toggleListing: (id) => api.post(`/admin/listings/${id}/toggle`),
  orders: (params) => api.get('/admin/orders', { params }),
  getPricing: () => api.get('/admin/pricing'),
  updatePricing: (data) => api.put('/admin/pricing', data),
  // Email config
  getEmailConfig: () => api.get('/admin/email-config'),
  updateEmailConfig: (data) => api.put('/admin/email-config', data),
  previewEmail: (type) => api.get(`/admin/email-preview/${type}`),
  platformStats: (params) => api.get('/admin/platform-stats', { params }),
  twilioStatus: () => api.get('/admin/twilio-status'),
  testSms: (data) => api.post('/admin/test-sms', data),
  siteConfig: () => api.get('/admin/site-config'),
};

// ---- Subscriptions ----
export const subscriptionsAPI = {
  browsePlans: (params) => api.get('/subscriptions/plans', { params }),
  planDetail: (id) => api.get(`/subscriptions/plans/${id}`),
  createPlan: (data) => api.post('/subscriptions/plans', data),
  updatePlan: (id, data) => api.put(`/subscriptions/plans/${id}`, data),
  deletePlan: (id) => api.delete(`/subscriptions/plans/${id}`),
  planPreviews: (planId) => api.get(`/subscriptions/plans/${planId}/previews`),
  createPreview: (planId, data) => api.post(`/subscriptions/plans/${planId}/previews`, data),
  subscribe: (planId, data) => api.post(`/subscriptions/plans/${planId}/subscribe`, data),
  mySubscriptions: () => api.get('/subscriptions/mine'),
  myPlans: () => api.get('/subscriptions/my-plans'),
  pause: (id) => api.put(`/subscriptions/${id}/pause`),
  resume: (id) => api.put(`/subscriptions/${id}/resume`),
  cancel: (id) => api.put(`/subscriptions/${id}/cancel`),
};

// ---- Planting Calendar & Harvest Forecasting ----
export const plantingAPI = {
  guide: () => api.get('/planting/guide'),
  guideCategory: (category) => api.get(`/planting/guide/${encodeURIComponent(category)}`),
  calendar: () => api.get('/planting/calendar'),
  forecast: () => api.get('/planting/forecast'),
  myPlantings: () => api.get('/planting/my-plantings'),
  createPlanting: (data) => api.post('/planting/my-plantings', data),
  updatePlanting: (id, data) => api.put(`/planting/my-plantings/${id}`, data),
  deletePlanting: (id) => api.delete(`/planting/my-plantings/${id}`),
  createListingFromPlanting: (id) => api.post(`/planting/my-plantings/${id}/create-listing`),
  preorders: () => api.get('/planting/preorders'),
  getInterests: () => api.get('/planting/harvest-interests'),
  subscribe: (data) => api.post('/planting/harvest-interests', data),
  unsubscribe: (category) => api.delete(`/planting/harvest-interests/${encodeURIComponent(category)}`),
};

// ---- Neighborhood Groups ----
export const groupsAPI = {
  browse: (params) => api.get('/groups', { params }),
  detail: (id) => api.get(`/groups/${id}`),
  create: (data) => api.post('/groups', data),
  update: (id, data) => api.put(`/groups/${id}`, data),
  join: (id) => api.post(`/groups/${id}/join`),
  leave: (id) => api.post(`/groups/${id}/leave`),
  members: (id) => api.get(`/groups/${id}/members`),
  changeRole: (groupId, userId, data) => api.post(`/groups/${groupId}/members/${userId}/role`, data),
  feed: (id, params) => api.get(`/groups/${id}/feed`, { params }),
  createPost: (groupId, data) => api.post(`/groups/${groupId}/posts`, data),
  getPost: (groupId, postId) => api.get(`/groups/${groupId}/posts/${postId}`),
  editPost: (groupId, postId, data) => api.put(`/groups/${groupId}/posts/${postId}`, data),
  deletePost: (groupId, postId) => api.delete(`/groups/${groupId}/posts/${postId}`),
  pinPost: (groupId, postId) => api.post(`/groups/${groupId}/posts/${postId}/pin`),
  getComments: (groupId, postId) => api.get(`/groups/${groupId}/posts/${postId}/comments`),
  addComment: (groupId, postId, data) => api.post(`/groups/${groupId}/posts/${postId}/comments`, data),
  listings: (id) => api.get(`/groups/${id}/listings`),
  myGroups: () => api.get('/groups/my-groups'),
  neighborhoods: () => api.get('/groups/neighborhoods'),
};

// ---- Garden Billing ----
export const gardenBillingAPI = {
  status: (gardenId) => api.get(`/gardens/${gardenId}/billing/status`),
  startTrial: (gardenId) => api.post(`/gardens/${gardenId}/billing/start-trial`),
  createCheckout: (gardenId, data) => api.post(`/gardens/${gardenId}/billing/create-checkout`, data),
  subscribe: (gardenId, data) => api.post(`/gardens/${gardenId}/billing/subscribe`, data),
  cancel: (gardenId) => api.post(`/gardens/${gardenId}/billing/cancel`),
};

// ---- Community Gardens ----
export const gardensAPI = {
  // Garden CRUD
  browse: (params) => api.get('/gardens', { params }),
  detail: (id) => api.get(`/gardens/${id}`),
  create: (data) => api.post('/gardens', data),
  update: (id, data) => api.put(`/gardens/${id}`, data),

  // Plots
  plots: (gardenId) => api.get(`/gardens/${gardenId}/plots`),
  addPlots: (gardenId, data) => api.post(`/gardens/${gardenId}/plots`, data),
  assignPlot: (gardenId, plotId, data) => api.put(`/gardens/${gardenId}/plots/${plotId}/assign`, data),
  releasePlot: (gardenId, plotId) => api.put(`/gardens/${gardenId}/plots/${plotId}/release`),

  // Plot Reservation
  reservePlot: (gardenId, plotId) => api.post(`/gardens/${gardenId}/plots/${plotId}/reserve`),

  // Plot Rename (by owner)
  renamePlot: (gardenId, plotId, data) => api.put(`/gardens/${gardenId}/plots/${plotId}/rename`, data),

  // Waitlist
  joinWaitlist: (gardenId, data) => api.post(`/gardens/${gardenId}/waitlist`, data),
  viewWaitlist: (gardenId) => api.get(`/gardens/${gardenId}/waitlist`),

  // Resources
  resources: (gardenId) => api.get(`/gardens/${gardenId}/resources`),
  addResource: (gardenId, data) => api.post(`/gardens/${gardenId}/resources`, data),
  checkoutResource: (gardenId, resId, data) => api.post(`/gardens/${gardenId}/resources/${resId}/checkout`, data),
  returnResource: (gardenId, resId, data) => api.post(`/gardens/${gardenId}/resources/${resId}/return`, data),
  overdueResources: (gardenId) => api.get(`/gardens/${gardenId}/resources/overdue`),
  resourceQR: (gardenId, resId) => `/api/gardens/${gardenId}/resources/${resId}/qr`,

  // Events
  events: (gardenId, params) => api.get(`/gardens/${gardenId}/events`, { params }),
  createEvent: (gardenId, data) => api.post(`/gardens/${gardenId}/events`, data),
  rsvpEvent: (gardenId, eventId, data) => api.post(`/gardens/${gardenId}/events/${eventId}/rsvp`, data),
  cancelRsvp: (gardenId, eventId) => api.delete(`/gardens/${gardenId}/events/${eventId}/rsvp`),

  // Harvests
  harvests: (gardenId, params) => api.get(`/gardens/${gardenId}/harvests`, { params }),
  logHarvest: (gardenId, data) => api.post(`/gardens/${gardenId}/harvests`, data),

  // Impact
  impact: (gardenId) => api.get(`/gardens/${gardenId}/impact`),

  // Members
  members: (gardenId) => api.get(`/gardens/${gardenId}/members`),

  // My Gardens
  myGardens: () => api.get('/gardens/my-gardens'),

  // Volunteer Shifts
  shifts: (gardenId, params) => api.get(`/gardens/${gardenId}/shifts`, { params }),
  signupShift: (gardenId, shiftId) => api.post(`/gardens/${gardenId}/shifts/${shiftId}/signup`),
  cancelShiftSignup: (gardenId, shiftId) => api.delete(`/gardens/${gardenId}/shifts/${shiftId}/signup`),
  volunteerHours: (gardenId) => api.get(`/gardens/${gardenId}/volunteer-hours`),

  // Plot History
  plotHistory: (gardenId, plotId) => api.get(`/gardens/${gardenId}/plots/${plotId}/history`),

  // Knowledge Base (public read)
  knowledge: (gardenId, params) => api.get(`/gardens/${gardenId}/knowledge`, { params }),

  // Weather Alerts (public read)
  weatherAlerts: (gardenId) => api.get(`/gardens/${gardenId}/weather/alerts`),

  // Announcements (public read)
  announcements: (gardenId) => api.get(`/gardens/${gardenId}/announcements`),

  // Dues (member self-service payment)
  myDues: (gardenId) => api.get(`/gardens/${gardenId}/my-dues`),
  payDues: (gardenId, duesId) => api.post(`/gardens/${gardenId}/dues/${duesId}/pay`),
  confirmDuesPayment: (gardenId, duesId, data) => api.post(`/gardens/${gardenId}/dues/${duesId}/confirm-payment`, data),
};

// ---- Garden Admin Portal ----
export const gardenAdminAPI = {
  // Dashboard & Activity
  dashboard: (gardenId) => api.get(`/garden-admin/${gardenId}/dashboard`),
  activity: (gardenId) => api.get(`/garden-admin/${gardenId}/activity`),

  // Plot Management (enhanced admin view)
  plots: (gardenId) => api.get(`/garden-admin/${gardenId}/plots`),
  updatePlot: (gardenId, plotId, data) => api.put(`/garden-admin/${gardenId}/plots/${plotId}`, data),
  toggleMaintenance: (gardenId, plotId) => api.put(`/garden-admin/${gardenId}/plots/${plotId}/maintenance`),
  updatePlotLayout: (gardenId, data) => api.put(`/garden-admin/${gardenId}/plot-layout`, data),

  // Plot Reservation Management
  confirmReservation: (gardenId, plotId) => api.post(`/garden-admin/${gardenId}/plots/${plotId}/confirm`),
  declineReservation: (gardenId, plotId) => api.post(`/garden-admin/${gardenId}/plots/${plotId}/decline-reservation`),

  // Waitlist Management
  approveWaitlist: (gardenId, wlId, data) => api.post(`/garden-admin/${gardenId}/waitlist/${wlId}/approve`, data),
  declineWaitlist: (gardenId, wlId) => api.post(`/garden-admin/${gardenId}/waitlist/${wlId}/decline`),

  // Announcements
  announcements: (gardenId, params) => api.get(`/garden-admin/${gardenId}/announcements`, { params }),
  createAnnouncement: (gardenId, data) => api.post(`/garden-admin/${gardenId}/announcements`, data),
  updateAnnouncement: (gardenId, annId, data) => api.put(`/garden-admin/${gardenId}/announcements/${annId}`, data),
  deleteAnnouncement: (gardenId, annId) => api.delete(`/garden-admin/${gardenId}/announcements/${annId}`),

  // Messages
  messages: (gardenId) => api.get(`/garden-admin/${gardenId}/messages`),
  sendMessage: (gardenId, data) => api.post(`/garden-admin/${gardenId}/messages`, data),
  broadcastMessage: (gardenId, data) => api.post(`/garden-admin/${gardenId}/messages/broadcast`, data),
  readMessage: (gardenId, msgId) => api.get(`/garden-admin/${gardenId}/messages/${msgId}`),

  // Photos (Social Media Lite)
  photos: (gardenId, params) => api.get(`/garden-admin/${gardenId}/photos`, { params }),
  postPhoto: (gardenId, data) => api.post(`/garden-admin/${gardenId}/photos`, data),
  deletePhoto: (gardenId, photoId) => api.delete(`/garden-admin/${gardenId}/photos/${photoId}`),
  likePhoto: (gardenId, photoId) => api.post(`/garden-admin/${gardenId}/photos/${photoId}/like`),
  photoComments: (gardenId, photoId) => api.get(`/garden-admin/${gardenId}/photos/${photoId}/comments`),
  addPhotoComment: (gardenId, photoId, data) => api.post(`/garden-admin/${gardenId}/photos/${photoId}/comments`, data),

  // Resource Management
  updateResourceCondition: (gardenId, resId, data) => api.put(`/garden-admin/${gardenId}/resources/${resId}/condition`, data),

  // Settings
  updateSettings: (gardenId, data) => api.put(`/garden-admin/${gardenId}/settings`, data),

  // Email config
  getEmailConfig: (gardenId) => api.get(`/garden-admin/${gardenId}/email-config`),
  updateEmailConfig: (gardenId, data) => api.put(`/garden-admin/${gardenId}/email-config`, data),
  previewEmail: (gardenId) => api.get(`/garden-admin/${gardenId}/email-preview`),

  // Event Management (admin-enhanced)
  updateEvent: (gardenId, eventId, data) => api.put(`/garden-admin/${gardenId}/events/${eventId}`, data),
  deleteEvent: (gardenId, eventId) => api.delete(`/garden-admin/${gardenId}/events/${eventId}`),
  eventAttendees: (gardenId, eventId) => api.get(`/garden-admin/${gardenId}/events/${eventId}/attendees`),

  // Volunteer Shifts (admin)
  createShift: (gardenId, data) => api.post(`/garden-admin/${gardenId}/shifts`, data),
  updateShift: (gardenId, shiftId, data) => api.put(`/garden-admin/${gardenId}/shifts/${shiftId}`, data),
  deleteShift: (gardenId, shiftId) => api.delete(`/garden-admin/${gardenId}/shifts/${shiftId}`),
  shiftAttendees: (gardenId, shiftId) => api.get(`/garden-admin/${gardenId}/shifts/${shiftId}/attendees`),
  markAttendance: (gardenId, shiftId, data) => api.post(`/garden-admin/${gardenId}/shifts/${shiftId}/attendance`, data),
  volunteerReport: (gardenId) => api.get(`/garden-admin/${gardenId}/volunteer-report`),

  // Dues (admin)
  dues: (gardenId, params) => api.get(`/garden-admin/${gardenId}/dues`, { params }),
  generateDues: (gardenId, data) => api.post(`/garden-admin/${gardenId}/dues/generate`, data),
  updateDues: (gardenId, duesId, data) => api.put(`/garden-admin/${gardenId}/dues/${duesId}`, data),
  waiveDues: (gardenId, duesId) => api.post(`/garden-admin/${gardenId}/dues/${duesId}/waive`),
  remindDues: (gardenId, duesId) => api.post(`/garden-admin/${gardenId}/dues/${duesId}/remind`),

  // Expenses (admin)
  expenses: (gardenId, params) => api.get(`/garden-admin/${gardenId}/expenses`, { params }),
  createExpense: (gardenId, data) => api.post(`/garden-admin/${gardenId}/expenses`, data),
  updateExpense: (gardenId, expId, data) => api.put(`/garden-admin/${gardenId}/expenses/${expId}`, data),
  deleteExpense: (gardenId, expId) => api.delete(`/garden-admin/${gardenId}/expenses/${expId}`),
  financeSummary: (gardenId, params) => api.get(`/garden-admin/${gardenId}/finance-summary`, { params }),

  // Weather (admin)
  weather: (gardenId) => api.get(`/garden-admin/${gardenId}/weather`),
  createWeatherAlert: (gardenId, data) => api.post(`/garden-admin/${gardenId}/weather/alerts`, data),
  dismissWeatherAlert: (gardenId, alertId) => api.delete(`/garden-admin/${gardenId}/weather/alerts/${alertId}`),

  // Rotation Report (admin)
  rotationReport: (gardenId) => api.get(`/garden-admin/${gardenId}/rotation-report`),

  // Members & Roles (admin)
  members: (gardenId) => api.get(`/garden-admin/${gardenId}/members`),
  exportMembersCSV: (gardenId) => `/api/garden-admin/${gardenId}/members/export`,
  changeMemberRole: (gardenId, userId, data) => api.post(`/garden-admin/${gardenId}/members/${userId}/role`, data),
  removeMember: (gardenId, userId) => api.delete(`/garden-admin/${gardenId}/members/${userId}`),

  // Knowledge Base (admin CRUD)
  createArticle: (gardenId, data) => api.post(`/garden-admin/${gardenId}/knowledge`, data),
  updateArticle: (gardenId, artId, data) => api.put(`/garden-admin/${gardenId}/knowledge/${artId}`, data),
  deleteArticle: (gardenId, artId) => api.delete(`/garden-admin/${gardenId}/knowledge/${artId}`),
};

// ---- Notifications ----
export const notificationsAPI = {
  list: (params) => api.get('/notifications', { params }),
  unreadCount: () => api.get('/notifications/unread-count'),
  markRead: (id) => api.post(`/notifications/${id}/read`),
  markAllRead: () => api.post('/notifications/mark-all-read'),
  delete: (id) => api.delete(`/notifications/${id}`),
};

// ---- Seller Earnings ----
export const earningsAPI = {
  summary: () => api.get('/earnings/summary'),
  history: (params) => api.get('/earnings/history', { params }),
  payouts: () => api.get('/earnings/payouts'),
};

// ---- Photos ----
export const photosAPI = {
  upload: (formData) => api.post('/photos/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
  list: (params) => api.get('/photos', { params }),
  delete: (id) => api.delete(`/photos/${id}`),
  gardenPhotos: (gardenId, params) => api.get(`/photos/garden/${gardenId}`, { params }),
};

export const IMAGE_BASE = '/static/uploads/';

export default api;
