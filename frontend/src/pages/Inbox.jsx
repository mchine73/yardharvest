import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { messagesAPI, IMAGE_BASE } from '../api';
import { useAuth } from '../AuthContext';

export default function Inbox() {
  const { refreshCounts } = useAuth();
  const navigate = useNavigate();
  const [threads, setThreads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    messagesAPI.inbox()
      .then(res => { setThreads(res.data); setLoading(false); refreshCounts(); })
      .catch(() => { setLoading(false); setError('Failed to load messages.'); });
  }, []);

  const timeAgo = (date) => {
    const diff = Date.now() - new Date(date).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  };

  if (loading) return <div className="text-center py-5"><div className="spinner-border text-success"></div></div>;
  if (error) return <div className="alert alert-danger"><i className="bi bi-exclamation-triangle me-2"></i>{error}</div>;

  return (
    <>
      <h1 className="mb-4"><i className="bi bi-chat-dots me-2"></i>Messages</h1>
      {threads.length === 0 ? (
        <p className="text-muted">No conversations yet.</p>
      ) : (
        <div className="list-group">
          {threads.map(t => (
            <div key={t.thread_id}
              className={`list-group-item list-group-item-action thread-item ${t.unread > 0 ? 'unread' : ''}`}
              onClick={() => navigate(`/messages/thread/${t.thread_id}`)}
            >
              <div className="d-flex align-items-center">
                <div className="me-3">
                  {t.other_user.profile_image ? (
                    <img src={`${IMAGE_BASE}${t.other_user.profile_image}`} alt="" className="rounded-circle" style={{ width: 48, height: 48, objectFit: 'cover' }} />
                  ) : (
                    <div className="bg-success text-white rounded-circle d-flex align-items-center justify-content-center" style={{ width: 48, height: 48 }}>
                      <i className="bi bi-person fs-4"></i>
                    </div>
                  )}
                </div>
                <div className="flex-grow-1">
                  <div className="d-flex justify-content-between">
                    <strong>{t.other_user.display_name}</strong>
                    <small className="text-muted">{timeAgo(t.last_message.created_at)}</small>
                  </div>
                  <div className="text-muted small">{t.last_message.body.substring(0, 50)}{t.last_message.body.length > 50 ? '...' : ''}</div>
                  {t.listing && <small className="text-success">Re: {t.listing.title}</small>}
                </div>
                {t.unread > 0 && <span className="badge bg-success ms-2">{t.unread}</span>}
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
