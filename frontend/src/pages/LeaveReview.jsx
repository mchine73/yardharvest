import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { profileAPI } from '../api';

export default function LeaveReview() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [rating, setRating] = useState(5);
  const [comment, setComment] = useState('');
  const [hover, setHover] = useState(0);
  const [submitting, setSubmitting] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await profileAPI.leaveReview(id, { rating, comment });
      navigate('/orders');
    } catch (err) {
      alert(err.response?.data?.error || 'Error submitting review');
      setSubmitting(false);
    }
  };

  return (
    <div className="row justify-content-center">
      <div className="col-md-6">
        <h2 className="mb-4"><i className="bi bi-star me-2"></i>Leave a Review</h2>
        <form onSubmit={submit}>
          <div className="mb-3">
            <label className="form-label">Rating</label>
            <div className="star-rating fs-2">
              {[1, 2, 3, 4, 5].map(star => (
                <i key={star}
                  className={`bi ${star <= (hover || rating) ? 'bi-star-fill' : 'bi-star'}`}
                  style={{ cursor: 'pointer' }}
                  onClick={() => setRating(star)}
                  onMouseEnter={() => setHover(star)}
                  onMouseLeave={() => setHover(0)}
                ></i>
              ))}
            </div>
          </div>
          <div className="mb-3">
            <label className="form-label">Comment</label>
            <textarea className="form-control" rows={4} value={comment} onChange={e => setComment(e.target.value)} placeholder="How was your experience?" />
          </div>
          <button type="submit" className="btn btn-success" disabled={submitting}>
            {submitting ? 'Submitting...' : 'Submit Review'}
          </button>
        </form>
      </div>
    </div>
  );
}
