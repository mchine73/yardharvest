import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { groupsAPI, IMAGE_BASE } from '../api';
import { useAuth } from '../AuthContext';
import { toast } from '../components/dialog/dialogService';

const POST_TYPE_BADGES = {
  update: { bg: '#D8EDDF', color: '#2d6a4f', label: 'Update' },
  question: { bg: '#dbeafe', color: '#1d4ed8', label: 'Question' },
  photo: { bg: '#ede9fe', color: '#7c3aed', label: 'Photo' },
  event: { bg: '#ffedd5', color: '#c2410c', label: 'Event' },
  trade: { bg: '#fef3c7', color: '#b45309', label: 'Trade' },
};

export default function GroupPostDetail() {
  const { id: groupId, postId } = useParams();
  const { user } = useAuth();
  const [post, setPost] = useState(null);
  const [comments, setComments] = useState([]);
  const [group, setGroup] = useState(null);
  const [loading, setLoading] = useState(true);
  const [newComment, setNewComment] = useState('');
  const [commenting, setCommenting] = useState(false);

  useEffect(() => {
    Promise.all([
      groupsAPI.getPost(groupId, postId),
      groupsAPI.getComments(groupId, postId),
      groupsAPI.detail(groupId),
    ]).then(([postRes, commentsRes, groupRes]) => {
      setPost(postRes.data);
      setComments(commentsRes.data);
      setGroup(groupRes.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [groupId, postId]);

  const handleComment = async () => {
    if (!newComment.trim()) return;
    setCommenting(true);
    try {
      await groupsAPI.addComment(groupId, postId, { content: newComment });
      const res = await groupsAPI.getComments(groupId, postId);
      setComments(res.data);
      setNewComment('');
    } catch (err) {
      toast(err.response?.data?.error || 'Failed to post comment', { type: 'error' });
    }
    setCommenting(false);
  };

  const isMember = group?.my_membership != null;

  if (loading) return <div className="text-center py-5"><div className="spinner-border text-success"></div></div>;
  if (!post) return <div className="text-center py-5 text-muted">Post not found</div>;

  const typeBadge = POST_TYPE_BADGES[post.post_type] || POST_TYPE_BADGES.update;

  const s = {
    breadcrumb: {
      marginBottom: 24,
      fontSize: 14,
    },
    breadcrumbLink: { color: '#40916c', textDecoration: 'none' },
    postCard: {
      backgroundColor: '#fff',
      border: '1px solid #e0e0e0',
      borderRadius: 16,
      padding: 32,
      marginBottom: 32,
    },
    postHeader: {
      display: 'flex',
      alignItems: 'center',
      gap: 14,
      marginBottom: 20,
    },
    avatar: {
      width: 48,
      height: 48,
      borderRadius: '50%',
      backgroundColor: '#74C69D',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      color: '#fff',
      fontWeight: 700,
      fontSize: 20,
      flexShrink: 0,
    },
    badge: {
      display: 'inline-block',
      padding: '3px 12px',
      borderRadius: 14,
      fontSize: 12,
      fontWeight: 600,
      backgroundColor: typeBadge.bg,
      color: typeBadge.color,
    },
    eventDetails: {
      backgroundColor: '#fff7ed',
      border: '1px solid #fed7aa',
      borderRadius: 12,
      padding: '16px 20px',
      marginBottom: 20,
    },
    eventRow: {
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      marginBottom: 6,
      fontSize: 15,
      color: '#92400e',
    },
    commentsList: {
      marginBottom: 24,
    },
    commentCard: {
      display: 'flex',
      gap: 12,
      padding: '16px 0',
      borderBottom: '1px solid #f0f0f0',
    },
    commentAvatar: {
      width: 36,
      height: 36,
      borderRadius: '50%',
      backgroundColor: '#D8EDDF',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      color: '#2d6a4f',
      fontWeight: 700,
      fontSize: 14,
      flexShrink: 0,
    },
    commentForm: {
      backgroundColor: '#f8fdf9',
      border: '1px solid #D8EDDF',
      borderRadius: 12,
      padding: 20,
    },
    pinnedBanner: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 6,
      padding: '4px 12px',
      borderRadius: 8,
      backgroundColor: '#fef3c7',
      color: '#b45309',
      fontSize: 12,
      fontWeight: 600,
      marginBottom: 16,
    },
  };

  return (
    <div style={{ maxWidth: 760, margin: '0 auto' }}>
      {/* Breadcrumb */}
      <div style={s.breadcrumb}>
        <Link to="/groups" style={s.breadcrumbLink}>Groups</Link>
        <span style={{ margin: '0 8px', color: '#ccc' }}>/</span>
        <Link to={`/groups/${groupId}`} style={s.breadcrumbLink}>{group?.name || 'Group'}</Link>
        <span style={{ margin: '0 8px', color: '#ccc' }}>/</span>
        <span style={{ color: '#888' }}>Post</span>
      </div>

      {/* Post */}
      <div style={s.postCard}>
        {post.pinned && (
          <div style={s.pinnedBanner}>
            <i className="bi bi-pin-fill"></i> Pinned Post
          </div>
        )}

        <div style={s.postHeader}>
          <div style={s.avatar}>
            {post.author_image ? (
              <img src={IMAGE_BASE + post.author_image} alt="" style={{ width: 48, height: 48, borderRadius: '50%', objectFit: 'cover' }} />
            ) : (
              post.author_name.charAt(0).toUpperCase()
            )}
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 700, color: '#1b4332', fontSize: 16 }}>
              <Link to={`/profile/${post.author_id}`} style={{ color: 'inherit', textDecoration: 'none' }}>
                {post.author_name}
              </Link>
            </div>
            <div style={{ fontSize: 13, color: '#888' }}>
              {new Date(post.created_at).toLocaleDateString('en-US', {
                weekday: 'long', month: 'long', day: 'numeric', year: 'numeric',
                hour: 'numeric', minute: '2-digit',
              })}
            </div>
          </div>
          <span style={s.badge}>{typeBadge.label}</span>
        </div>

        {post.title && (
          <h4 style={{ color: '#1b4332', fontWeight: 700, marginBottom: 12 }}>{post.title}</h4>
        )}

        <div style={{ fontSize: 15, color: '#333', lineHeight: 1.7, whiteSpace: 'pre-wrap', marginBottom: 16 }}>
          {post.content}
        </div>

        {post.photo_url && (
          <div style={{ marginBottom: 16 }}>
            <img
              src={post.photo_url}
              alt="Post photo"
              style={{ maxWidth: '100%', borderRadius: 10 }}
            />
          </div>
        )}

        {post.post_type === 'event' && post.event_date && (
          <div style={s.eventDetails}>
            <h6 style={{ color: '#92400e', fontWeight: 700, marginBottom: 12 }}>
              <i className="bi bi-calendar-event me-2"></i>Event Details
            </h6>
            <div style={s.eventRow}>
              <i className="bi bi-calendar3"></i>
              <strong>
                {new Date(post.event_date).toLocaleDateString('en-US', {
                  weekday: 'long', month: 'long', day: 'numeric', year: 'numeric',
                })}
              </strong>
            </div>
            <div style={s.eventRow}>
              <i className="bi bi-clock"></i>
              {new Date(post.event_date).toLocaleTimeString('en-US', {
                hour: 'numeric', minute: '2-digit',
              })}
            </div>
            {post.event_location && (
              <div style={s.eventRow}>
                <i className="bi bi-geo-alt-fill"></i>
                {post.event_location}
              </div>
            )}
            <div style={{ marginTop: 12, fontSize: 13, color: '#92400e', fontStyle: 'italic' }}>
              Leave a comment to let others know you'll be there!
            </div>
          </div>
        )}
      </div>

      {/* Comments */}
      <div style={{ marginBottom: 24 }}>
        <h5 style={{ color: '#1b4332', fontWeight: 700, marginBottom: 16 }}>
          <i className="bi bi-chat-dots me-2"></i>
          Comments ({comments.length})
        </h5>

        {comments.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 32, color: '#888', backgroundColor: '#f8f9fa', borderRadius: 12 }}>
            <i className="bi bi-chat-square" style={{ fontSize: 28, display: 'block', marginBottom: 8 }}></i>
            <p style={{ margin: 0 }}>No comments yet. Be the first to respond!</p>
          </div>
        ) : (
          <div style={s.commentsList}>
            {comments.map(c => (
              <div key={c.id} style={s.commentCard}>
                <div style={s.commentAvatar}>
                  {c.author_image ? (
                    <img src={IMAGE_BASE + c.author_image} alt="" style={{ width: 36, height: 36, borderRadius: '50%', objectFit: 'cover' }} />
                  ) : (
                    c.author_name.charAt(0).toUpperCase()
                  )}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ marginBottom: 4 }}>
                    <Link
                      to={`/profile/${c.author_id}`}
                      style={{ fontWeight: 600, color: '#1b4332', textDecoration: 'none', fontSize: 14 }}
                    >
                      {c.author_name}
                    </Link>
                    <span style={{ fontSize: 12, color: '#999', marginLeft: 10 }}>
                      {new Date(c.created_at).toLocaleDateString('en-US', {
                        month: 'short', day: 'numeric',
                        hour: 'numeric', minute: '2-digit',
                      })}
                    </span>
                  </div>
                  <div style={{ fontSize: 14, color: '#444', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
                    {c.content}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Comment Form */}
      {user && isMember ? (
        <div style={s.commentForm}>
          <h6 style={{ color: '#2d6a4f', fontWeight: 600, marginBottom: 12 }}>
            <i className="bi bi-reply me-1"></i>Leave a Comment
          </h6>
          <textarea
            className="form-control mb-2"
            rows={3}
            placeholder="Share your thoughts..."
            value={newComment}
            onChange={e => setNewComment(e.target.value)}
          />
          <button
            className="btn btn-success"
            onClick={handleComment}
            disabled={commenting || !newComment.trim()}
          >
            {commenting ? 'Posting...' : 'Post Comment'}
          </button>
        </div>
      ) : user && !isMember ? (
        <div style={{ textAlign: 'center', padding: 24, backgroundColor: '#f8f9fa', borderRadius: 12, color: '#666' }}>
          <p style={{ margin: 0 }}>
            <Link to={`/groups/${groupId}`} style={{ color: '#2d6a4f', fontWeight: 600 }}>Join this group</Link> to leave a comment.
          </p>
        </div>
      ) : (
        <div style={{ textAlign: 'center', padding: 24, backgroundColor: '#f8f9fa', borderRadius: 12, color: '#666' }}>
          <p style={{ margin: 0 }}>
            <Link to="/login" style={{ color: '#2d6a4f', fontWeight: 600 }}>Log in</Link> to leave a comment.
          </p>
        </div>
      )}
    </div>
  );
}
