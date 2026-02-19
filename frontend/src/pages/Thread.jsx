import { useState, useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { messagesAPI } from '../api';
import { useAuth } from '../AuthContext';

export default function Thread() {
  const { threadId } = useParams();
  const { user, refreshCounts } = useAuth();
  const [messages, setMessages] = useState([]);
  const [otherUser, setOtherUser] = useState(null);
  const [listingId, setListingId] = useState(null);
  const [body, setBody] = useState('');
  const bottomRef = useRef(null);

  const fetchThread = async () => {
    const res = await messagesAPI.thread(threadId);
    setMessages(res.data.messages);
    setOtherUser(res.data.other_user);
    setListingId(res.data.listing_id);
    refreshCounts();
  };

  useEffect(() => { fetchThread(); }, [threadId]);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const send = async (e) => {
    e.preventDefault();
    if (!body.trim()) return;
    await messagesAPI.send({ recipient_id: otherUser.id, listing_id: listingId, body });
    setBody('');
    fetchThread();
  };

  return (
    <>
      <h4 className="mb-3"><i className="bi bi-chat me-2"></i>Chat with {otherUser?.display_name || '...'}</h4>
      <div className="card" style={{ height: '60vh', display: 'flex', flexDirection: 'column' }}>
        <div className="card-body overflow-auto flex-grow-1">
          {messages.map(m => (
            <div key={m.id} className={`mb-2 p-2 ${m.sender_id === user.id ? 'chat-mine text-end' : 'chat-theirs'}`}>
              <div>{m.body}</div>
              <small className="text-muted">{new Date(m.created_at).toLocaleTimeString()}</small>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
        <div className="card-footer">
          <form onSubmit={send} className="d-flex gap-2">
            <input className="form-control" value={body} onChange={e => setBody(e.target.value)} placeholder="Type a message..." />
            <button className="btn btn-success" type="submit"><i className="bi bi-send"></i></button>
          </form>
        </div>
      </div>
    </>
  );
}
