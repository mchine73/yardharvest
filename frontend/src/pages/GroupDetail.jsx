import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { groupsAPI, IMAGE_BASE } from '../api';
import { useAuth } from '../AuthContext';
import { confirmDialog } from '../components/dialog/dialogService';
import { formatDate, formatDateTime, formatTime, DAY_MONTH_YEAR, HOUR_MINUTE } from '../i18n/dates';

const POST_TYPE_BADGES = {
  update: { bg: 'var(--brand-pale)', color: 'var(--brand-secondary)' },
  question: { bg: '#dbeafe', color: '#1d4ed8' },
  photo: { bg: '#ede9fe', color: '#7c3aed' },
  event: { bg: '#ffedd5', color: '#c2410c' },
  trade: { bg: '#fef3c7', color: '#b45309' },
};

const ROLE_BADGES = {
  admin: { bg: 'var(--brand-secondary)', color: '#fff' },
  moderator: { bg: 'var(--brand-accent)', color: '#fff' },
  member: { bg: '#e0e0e0', color: '#555' },
};

// Labels for the post_type / role slugs. Written out as literal t() calls
// (not keys stored in the maps above) so keys.test can check every one.
// An unknown slug returns undefined and the caller falls back to the raw value.
const postTypeLabel = (t, type) => ({
  update: t('groups.typeUpdate'),
  question: t('groups.typeQuestion'),
  photo: t('groups.typePhoto'),
  event: t('groups.typeEvent'),
  trade: t('groups.typeTrade'),
})[type];

const roleLabel = (t, role) => ({
  admin: t('groups.roleAdmin'),
  moderator: t('groups.roleModerator'),
  member: t('groups.roleMember'),
})[role];

export default function GroupDetail() {
  const { t } = useTranslation();
  const { id } = useParams();
  const { user } = useAuth();
  const [group, setGroup] = useState(null);
  const [activeTab, setActiveTab] = useState('feed');
  const [loading, setLoading] = useState(true);

  // Feed state
  const [posts, setPosts] = useState([]);
  const [feedPage, setFeedPage] = useState(1);
  const [feedPagination, setFeedPagination] = useState({});
  const [feedLoading, setFeedLoading] = useState(false);

  // Members state
  const [members, setMembers] = useState([]);
  const [membersLoading, setMembersLoading] = useState(false);

  // Listings state
  const [listings, setListings] = useState([]);
  const [listingsLoading, setListingsLoading] = useState(false);

  // Composer state
  const [showComposer, setShowComposer] = useState(false);
  const [newPost, setNewPost] = useState({ post_type: 'update', title: '', content: '', event_date: '', event_location: '' });
  const [posting, setPosting] = useState(false);

  useEffect(() => {
    groupsAPI.detail(id).then(res => {
      setGroup(res.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    if (activeTab === 'feed') loadFeed();
    if (activeTab === 'members') loadMembers();
    if (activeTab === 'listings') loadListings();
    if (activeTab === 'events') loadFeed('event');
  }, [activeTab, feedPage]);

  const loadFeed = (type) => {
    setFeedLoading(true);
    const params = { page: feedPage };
    if (type) params.type = type;
    groupsAPI.feed(id, params).then(res => {
      setPosts(res.data.posts);
      setFeedPagination(res.data);
      setFeedLoading(false);
    }).catch(() => setFeedLoading(false));
  };

  const loadMembers = () => {
    setMembersLoading(true);
    groupsAPI.members(id).then(res => {
      setMembers(res.data);
      setMembersLoading(false);
    }).catch(() => setMembersLoading(false));
  };

  const loadListings = () => {
    setListingsLoading(true);
    groupsAPI.listings(id).then(res => {
      setListings(res.data);
      setListingsLoading(false);
    }).catch(() => setListingsLoading(false));
  };

  const handleJoin = () => {
    groupsAPI.join(id).then(() => {
      groupsAPI.detail(id).then(res => setGroup(res.data));
    });
  };

  const handleLeave = async () => {
    if (!(await confirmDialog(t('groups.confirmLeave'), { title: t('groups.leaveGroupTitle'), confirmText: t('groups.leave') }))) return;
    groupsAPI.leave(id).then(() => {
      groupsAPI.detail(id).then(res => setGroup(res.data));
    });
  };

  const handlePost = () => {
    if (!newPost.content.trim()) return;
    setPosting(true);
    groupsAPI.createPost(id, newPost).then(() => {
      setNewPost({ post_type: 'update', title: '', content: '', event_date: '', event_location: '' });
      setShowComposer(false);
      setPosting(false);
      loadFeed();
    }).catch(() => setPosting(false));
  };

  const handleDeletePost = async (postId) => {
    if (!(await confirmDialog(t('groups.confirmDeletePost'), { danger: true, title: t('groups.deletePostTitle'), confirmText: t('groups.delete') }))) return;
    groupsAPI.deletePost(id, postId).then(() => loadFeed());
  };

  const handlePinPost = (postId) => {
    groupsAPI.pinPost(id, postId).then(() => loadFeed());
  };

  const isMember = group?.my_membership != null;
  const myRole = group?.my_membership?.role;
  const canModerate = myRole === 'admin' || myRole === 'moderator';

  if (loading) return <div className="text-center py-5"><div className="spinner-border text-success"></div></div>;
  if (!group) return <div className="text-center py-5 text-muted">{t('groups.notFound')}</div>;

  const s = {
    header: {
      background: group.cover_photo_url
        ? `linear-gradient(rgba(0,0,0,0.3), rgba(0,0,0,0.5)), url(${group.cover_photo_url}) center/cover`
        : 'linear-gradient(135deg, var(--brand-secondary) 0%, var(--brand-accent) 50%, #52b788 100%)',
      color: '#fff',
      borderRadius: 16,
      padding: '48px 32px 32px',
      marginBottom: 24,
    },
    headerName: { fontSize: 32, fontWeight: 700, marginBottom: 4 },
    headerNeighborhood: { fontSize: 15, opacity: 0.9, marginBottom: 12 },
    headerDesc: { fontSize: 15, opacity: 0.85, maxWidth: 700, marginBottom: 16 },
    headerStats: { display: 'flex', gap: 24, fontSize: 14, opacity: 0.9, marginBottom: 16 },
    joinBtn: {
      padding: '10px 28px',
      borderRadius: 8,
      border: 'none',
      backgroundColor: 'var(--brand-pale)',
      color: 'var(--brand-secondary)',
      fontWeight: 700,
      fontSize: 15,
      cursor: 'pointer',
    },
    leaveBtn: {
      padding: '10px 28px',
      borderRadius: 8,
      border: '2px solid rgba(255,255,255,0.6)',
      backgroundColor: 'transparent',
      color: '#fff',
      fontWeight: 600,
      fontSize: 15,
      cursor: 'pointer',
    },
    tabs: {
      display: 'flex',
      gap: 0,
      borderBottom: '2px solid #e0e0e0',
      marginBottom: 24,
    },
    tab: (active) => ({
      padding: '12px 24px',
      cursor: 'pointer',
      fontWeight: active ? 700 : 500,
      color: active ? 'var(--brand-secondary)' : '#777',
      borderBottom: active ? '3px solid var(--brand-secondary)' : '3px solid transparent',
      marginBottom: -2,
      fontSize: 15,
      background: 'none',
      border: 'none',
      borderBottomWidth: 3,
      borderBottomStyle: 'solid',
      borderBottomColor: active ? 'var(--brand-secondary)' : 'transparent',
    }),
    composer: {
      backgroundColor: '#f8fdf9',
      border: '1px solid var(--brand-pale)',
      borderRadius: 12,
      padding: 20,
      marginBottom: 24,
    },
    postCard: {
      backgroundColor: '#fff',
      border: '1px solid #e8e8e8',
      borderRadius: 12,
      padding: 20,
      marginBottom: 16,
    },
    postHeader: { display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 },
    avatar: {
      width: 40,
      height: 40,
      borderRadius: '50%',
      backgroundColor: 'var(--brand-light-green)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      color: '#fff',
      fontWeight: 700,
      fontSize: 16,
    },
    badge: (type) => {
      const cfg = POST_TYPE_BADGES[type] || POST_TYPE_BADGES.update;
      return {
        display: 'inline-block',
        padding: '2px 10px',
        borderRadius: 12,
        fontSize: 11,
        fontWeight: 600,
        backgroundColor: cfg.bg,
        color: cfg.color,
      };
    },
    memberCard: {
      border: '1px solid #e8e8e8',
      borderRadius: 12,
      padding: 16,
      display: 'flex',
      alignItems: 'center',
      gap: 12,
    },
    roleBadge: (role) => {
      const cfg = ROLE_BADGES[role] || ROLE_BADGES.member;
      return {
        display: 'inline-block',
        padding: '2px 10px',
        borderRadius: 12,
        fontSize: 11,
        fontWeight: 600,
        backgroundColor: cfg.bg,
        color: cfg.color,
      };
    },
    listingCard: {
      border: '1px solid #e8e8e8',
      borderRadius: 12,
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'column',
    },
    listingImg: {
      height: 120,
      backgroundColor: 'var(--brand-pale)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
    },
    eventCard: {
      backgroundColor: '#fff',
      border: '1px solid #ffedd5',
      borderLeft: '4px solid #c2410c',
      borderRadius: 12,
      padding: 20,
      marginBottom: 16,
    },
    pinnedBadge: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 4,
      fontSize: 11,
      fontWeight: 600,
      color: '#b45309',
      marginLeft: 8,
    },
  };

  return (
    <>
      {/* Header */}
      <div style={s.header}>
        <h1 style={s.headerName}>{group.name}</h1>
        {group.neighborhood && (
          <div style={s.headerNeighborhood}>
            <i className="bi bi-geo-alt-fill me-1"></i>
            {group.neighborhood}, {group.city}, {group.state}
          </div>
        )}
        <div style={s.headerDesc}>{group.description}</div>
        <div style={s.headerStats}>
          <span><i className="bi bi-people-fill me-1"></i>{t('groups.memberCount', { count: group.member_count })}</span>
          <span><i className="bi bi-chat-square-text me-1"></i>{t('groups.postCount', { count: group.post_count })}</span>
          <span><i className="bi bi-person me-1"></i>{t('groups.createdBy', { name: group.created_by_name })}</span>
        </div>
        {user && !isMember && (
          <button style={s.joinBtn} onClick={handleJoin}>
            <i className="bi bi-plus-circle me-1"></i> {t('groups.joinGroup')}
          </button>
        )}
        {user && isMember && (
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <span style={s.roleBadge(myRole)}>
              {roleLabel(t, myRole) || t('groups.roleMember')}
            </span>
            {myRole !== 'admin' && (
              <button style={s.leaveBtn} onClick={handleLeave}>{t('groups.leaveGroup')}</button>
            )}
          </div>
        )}
        {!user && (
          <Link to="/login" style={{ ...s.joinBtn, textDecoration: 'none' }}>
            {t('groups.loginToJoin')}
          </Link>
        )}
      </div>

      {/* Tabs */}
      <div style={s.tabs}>
        {['feed', 'members', 'listings', 'events'].map(tab => (
          <button
            key={tab}
            style={s.tab(activeTab === tab)}
            onClick={() => { setActiveTab(tab); setFeedPage(1); }}
          >
            <i className={`bi bi-${
              tab === 'feed' ? 'rss' :
              tab === 'members' ? 'people' :
              tab === 'listings' ? 'shop' :
              'calendar-event'
            } me-1`}></i>
            {tab === 'feed' ? t('groups.tabFeed') :
              tab === 'members' ? t('groups.tabMembers') :
              tab === 'listings' ? t('groups.tabListings') :
              t('groups.tabEvents')}
          </button>
        ))}
      </div>

      {/* Feed Tab */}
      {activeTab === 'feed' && (
        <div>
          {isMember && (
            <div style={{ marginBottom: 20 }}>
              {!showComposer ? (
                <button
                  className="btn btn-outline-success w-100"
                  style={{ borderRadius: 12, padding: 14 }}
                  onClick={() => setShowComposer(true)}
                >
                  <i className="bi bi-pencil-square me-2"></i>
                  {t('groups.shareSomething')}
                </button>
              ) : (
                <div style={s.composer}>
                  <div className="mb-2">
                    <select
                      className="form-select form-select-sm w-auto d-inline-block"
                      value={newPost.post_type}
                      onChange={e => setNewPost({ ...newPost, post_type: e.target.value })}
                    >
                      <option value="update">{t('groups.typeUpdate')}</option>
                      <option value="question">{t('groups.typeQuestion')}</option>
                      <option value="photo">{t('groups.typePhoto')}</option>
                      <option value="event">{t('groups.typeEvent')}</option>
                      <option value="trade">{t('groups.typeTrade')}</option>
                    </select>
                  </div>
                  <input
                    type="text"
                    className="form-control mb-2"
                    placeholder={t('groups.titleOptional')}
                    value={newPost.title}
                    onChange={e => setNewPost({ ...newPost, title: e.target.value })}
                  />
                  <textarea
                    className="form-control mb-2"
                    rows={3}
                    placeholder={t('groups.whatsOnYourMind')}
                    value={newPost.content}
                    onChange={e => setNewPost({ ...newPost, content: e.target.value })}
                  />
                  {newPost.post_type === 'event' && (
                    <div className="row mb-2">
                      <div className="col-md-6">
                        <input
                          type="datetime-local"
                          className="form-control"
                          value={newPost.event_date}
                          onChange={e => setNewPost({ ...newPost, event_date: e.target.value })}
                        />
                      </div>
                      <div className="col-md-6">
                        <input
                          type="text"
                          className="form-control"
                          placeholder={t('groups.eventLocation')}
                          value={newPost.event_location}
                          onChange={e => setNewPost({ ...newPost, event_location: e.target.value })}
                        />
                      </div>
                    </div>
                  )}
                  <div className="d-flex gap-2">
                    <button
                      className="btn btn-success"
                      onClick={handlePost}
                      disabled={posting || !newPost.content.trim()}
                    >
                      {posting ? t('groups.posting') : t('groups.post')}
                    </button>
                    <button
                      className="btn btn-outline-secondary"
                      onClick={() => setShowComposer(false)}
                    >
                      {t('groups.cancel')}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {feedLoading ? (
            <div className="text-center py-4"><div className="spinner-border text-success spinner-border-sm"></div></div>
          ) : posts.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 40, color: '#888' }}>
              <i className="bi bi-chat-square" style={{ fontSize: 36, display: 'block', marginBottom: 8 }}></i>
              <p>{t('groups.noPosts')}</p>
            </div>
          ) : (
            posts.map(p => (
              <div key={p.id} style={s.postCard}>
                <div style={s.postHeader}>
                  <div style={s.avatar}>
                    {p.author_image ? (
                      <img src={IMAGE_BASE + p.author_image} alt="" style={{ width: 40, height: 40, borderRadius: '50%', objectFit: 'cover' }} />
                    ) : (
                      p.author_name.charAt(0).toUpperCase()
                    )}
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 600, color: 'var(--brand-primary)' }}>
                      {p.author_name}
                      {p.pinned && (
                        <span style={s.pinnedBadge}>
                          <i className="bi bi-pin-fill"></i> {t('groups.pinned')}
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: 12, color: '#888' }}>
                      {formatDate(p.created_at, DAY_MONTH_YEAR)}
                    </div>
                  </div>
                  <span style={s.badge(p.post_type)}>
                    {postTypeLabel(t, p.post_type) || p.post_type}
                  </span>
                </div>

                {p.title && <h6 style={{ fontWeight: 700, color: 'var(--brand-primary)', marginBottom: 8 }}>{p.title}</h6>}
                <p style={{ color: '#444', marginBottom: 12, whiteSpace: 'pre-wrap' }}>{p.content}</p>

                {p.post_type === 'event' && p.event_date && (
                  <div style={{
                    backgroundColor: '#fff7ed',
                    borderRadius: 8,
                    padding: '10px 14px',
                    marginBottom: 12,
                    fontSize: 14,
                  }}>
                    <i className="bi bi-calendar-event me-2" style={{ color: '#c2410c' }}></i>
                    <strong>{formatDateTime(p.event_date, { weekday: 'long', month: 'long', day: 'numeric', hour: 'numeric', minute: '2-digit' })}</strong>
                    {p.event_location && (
                      <span style={{ marginLeft: 16 }}>
                        <i className="bi bi-geo-alt me-1" style={{ color: '#c2410c' }}></i>
                        {p.event_location}
                      </span>
                    )}
                  </div>
                )}

                <div style={{ display: 'flex', alignItems: 'center', gap: 16, fontSize: 13, color: '#777' }}>
                  <Link
                    to={`/groups/${id}/posts/${p.id}`}
                    style={{ color: 'var(--brand-secondary)', textDecoration: 'none', fontWeight: 500 }}
                  >
                    <i className="bi bi-chat me-1"></i>
                    {t('groups.commentCount', { count: p.comment_count })}
                  </Link>
                  {canModerate && (
                    <button
                      onClick={() => handlePinPost(p.id)}
                      style={{ background: 'none', border: 'none', color: '#888', cursor: 'pointer', fontSize: 13 }}
                    >
                      <i className={`bi bi-pin${p.pinned ? '-fill' : ''} me-1`}></i>
                      {p.pinned ? t('groups.unpin') : t('groups.pin')}
                    </button>
                  )}
                  {(user && (p.author_id === user.id || canModerate)) && (
                    <button
                      onClick={() => handleDeletePost(p.id)}
                      style={{ background: 'none', border: 'none', color: '#e0564f', cursor: 'pointer', fontSize: 13 }}
                    >
                      <i className="bi bi-trash me-1"></i>{t('groups.delete')}
                    </button>
                  )}
                </div>
              </div>
            ))
          )}

          {feedPagination.pages > 1 && (
            <nav className="mt-3">
              <ul className="pagination justify-content-center">
                <li className={`page-item ${!feedPagination.has_prev ? 'disabled' : ''}`}>
                  <button className="page-link" onClick={() => setFeedPage(feedPage - 1)}>{t('groups.previous')}</button>
                </li>
                {Array.from({ length: feedPagination.pages }, (_, i) => (
                  <li key={i} className={`page-item ${feedPage === i + 1 ? 'active' : ''}`}>
                    <button className="page-link" onClick={() => setFeedPage(i + 1)}>{i + 1}</button>
                  </li>
                ))}
                <li className={`page-item ${!feedPagination.has_next ? 'disabled' : ''}`}>
                  <button className="page-link" onClick={() => setFeedPage(feedPage + 1)}>{t('groups.next')}</button>
                </li>
              </ul>
            </nav>
          )}
        </div>
      )}

      {/* Members Tab */}
      {activeTab === 'members' && (
        <div>
          {membersLoading ? (
            <div className="text-center py-4"><div className="spinner-border text-success spinner-border-sm"></div></div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 16 }}>
              {members.map(m => (
                <div key={m.id} style={s.memberCard}>
                  <div style={s.avatar}>
                    {m.profile_image ? (
                      <img src={IMAGE_BASE + m.profile_image} alt="" style={{ width: 40, height: 40, borderRadius: '50%', objectFit: 'cover' }} />
                    ) : (
                      m.display_name.charAt(0).toUpperCase()
                    )}
                  </div>
                  <div style={{ flex: 1 }}>
                    <Link to={`/profile/${m.user_public_id}`} style={{ fontWeight: 600, color: 'var(--brand-primary)', textDecoration: 'none' }}>
                      {m.display_name}
                    </Link>
                    <div style={{ fontSize: 12, color: '#888' }}>
                      {t('groups.joinedOn', { date: formatDate(m.joined_at) })}
                    </div>
                  </div>
                  <span style={s.roleBadge(m.role)}>
                    {roleLabel(t, m.role) || m.role}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Listings Tab */}
      {activeTab === 'listings' && (
        <div>
          {listingsLoading ? (
            <div className="text-center py-4"><div className="spinner-border text-success spinner-border-sm"></div></div>
          ) : listings.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 40, color: '#888' }}>
              <i className="bi bi-shop" style={{ fontSize: 36, display: 'block', marginBottom: 8 }}></i>
              <p>{t('groups.noListings')}</p>
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: 16 }}>
              {listings.map(l => (
                <Link
                  key={l.id}
                  to={`/listings/${l.id}`}
                  style={{ textDecoration: 'none', color: 'inherit' }}
                >
                  <div style={s.listingCard}>
                    <div style={s.listingImg}>
                      {l.image_filename ? (
                        <img src={IMAGE_BASE + l.image_filename} alt="" style={{ width: '100%', height: 120, objectFit: 'cover' }} />
                      ) : l.image_url ? (
                        <img src={l.image_url} alt="" style={{ width: '100%', height: 120, objectFit: 'cover' }} />
                      ) : (
                        <i className="bi bi-basket" style={{ fontSize: 36, color: '#ccc' }}></i>
                      )}
                    </div>
                    <div style={{ padding: 14 }}>
                      <div style={{ fontWeight: 600, color: 'var(--brand-primary)', marginBottom: 4 }}>{l.title}</div>
                      <div style={{ fontSize: 13, color: 'var(--brand-secondary)', marginBottom: 4 }}>
                        ${l.price.toFixed(2)} / {l.unit}
                      </div>
                      <div style={{ fontSize: 12, color: '#888' }}>
                        <i className="bi bi-person me-1"></i>{l.seller_name}
                      </div>
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Events Tab */}
      {activeTab === 'events' && (
        <div>
          {feedLoading ? (
            <div className="text-center py-4"><div className="spinner-border text-success spinner-border-sm"></div></div>
          ) : posts.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 40, color: '#888' }}>
              <i className="bi bi-calendar-event" style={{ fontSize: 36, display: 'block', marginBottom: 8 }}></i>
              <p>{isMember ? t('groups.noEventsMember') : t('groups.noEvents')}</p>
            </div>
          ) : (
            posts.map(p => (
              <div key={p.id} style={s.eventCard}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 16 }}>
                  {p.event_date && (
                    <div style={{
                      minWidth: 60,
                      textAlign: 'center',
                      backgroundColor: '#fff',
                      border: '1px solid #fed7aa',
                      borderRadius: 8,
                      padding: '8px 4px',
                    }}>
                      <div style={{ fontSize: 11, fontWeight: 700, color: '#c2410c', textTransform: 'uppercase' }}>
                        {formatDate(p.event_date, { month: 'short' })}
                      </div>
                      <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--brand-primary)' }}>
                        {new Date(p.event_date).getDate()}
                      </div>
                    </div>
                  )}
                  <div style={{ flex: 1 }}>
                    <h6 style={{ fontWeight: 700, color: 'var(--brand-primary)', marginBottom: 4 }}>
                      {p.title || t('groups.communityEvent')}
                    </h6>
                    <div style={{ fontSize: 13, color: '#666', marginBottom: 6 }}>
                      {p.event_date && (
                        <span>
                          <i className="bi bi-clock me-1"></i>
                          {formatTime(p.event_date, HOUR_MINUTE)}
                        </span>
                      )}
                      {p.event_location && (
                        <span style={{ marginLeft: 12 }}>
                          <i className="bi bi-geo-alt me-1"></i>{p.event_location}
                        </span>
                      )}
                    </div>
                    <p style={{ fontSize: 14, color: '#555', marginBottom: 8 }}>{p.content}</p>
                    <div style={{ fontSize: 12, color: '#888' }}>
                      {t('groups.postedBy', { name: p.author_name })}
                      <span style={{ marginLeft: 12 }}>
                        <i className="bi bi-chat me-1"></i>{t('groups.commentCount', { count: p.comment_count })}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </>
  );
}
