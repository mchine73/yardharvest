import { useState } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import { messagesAPI } from '../api';
import { toast } from '../components/dialog/dialogService';

export default function NewMessage() {
  const { userId } = useParams();
  const [searchParams] = useSearchParams();
  const listingId = searchParams.get('listing_id');
  const navigate = useNavigate();
  const [body, setBody] = useState('');
  const [sending, setSending] = useState(false);

  const send = async (e) => {
    e.preventDefault();
    if (!body.trim()) return;
    setSending(true);
    try {
      const res = await messagesAPI.send({ recipient_id: parseInt(userId), listing_id: listingId ? parseInt(listingId) : null, body });
      navigate(`/messages/thread/${res.data.thread_id}`);
    } catch {
      toast('Failed to send message', { type: 'error' });
      setSending(false);
    }
  };

  return (
    <div className="row justify-content-center">
      <div className="col-md-6">
        <h2 className="mb-4"><i className="bi bi-chat-dots me-2"></i>New Message</h2>
        <form onSubmit={send}>
          <div className="mb-3">
            <textarea className="form-control" rows={4} value={body} onChange={e => setBody(e.target.value)} placeholder="Write your message..." />
          </div>
          <button className="btn btn-success" type="submit" disabled={sending}>
            {sending ? 'Sending...' : 'Send Message'}
          </button>
        </form>
      </div>
    </div>
  );
}
