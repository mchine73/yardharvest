import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { profileAPI, IMAGE_BASE } from '../api';
import { useAuth } from '../AuthContext';
import ListingCard from '../components/ListingCard';

export default function PublicProfile() {
  const { userId } = useParams();
  const { user: me } = useAuth();
  const [data, setData] = useState(null);

  useEffect(() => {
    profileAPI.get(userId).then(res => setData(res.data));
  }, [userId]);

  if (!data) return <div className="text-center py-5"><div className="spinner-border text-success"></div></div>;

  const { user, listings, reviews } = data;
  const gallery = [user.gallery_image_1, user.gallery_image_2, user.gallery_image_3].filter(Boolean);

  return (
    <>
      <div className="row">
        <div className="col-md-4">
          <div className="card">
            <div className="card-body text-center">
              {user.profile_image ? (
                <img src={`${IMAGE_BASE}${user.profile_image}`} className="rounded-circle mb-3" style={{ width: 120, height: 120, objectFit: 'cover' }} alt="" />
              ) : (
                <div className="bg-success text-white rounded-circle d-inline-flex align-items-center justify-content-center mb-3" style={{ width: 120, height: 120 }}><i className="bi bi-person fs-1"></i></div>
              )}
              <h3>{user.display_name || user.username}</h3>
              <p className="text-muted">@{user.username}</p>
              {user.city && <p><i className="bi bi-geo-alt me-1"></i>{user.city}, {user.state}</p>}
              {user.avg_rating && (
                <div className="star-rating mb-2">
                  {[1,2,3,4,5].map(s => <i key={s} className={`bi ${s <= Math.round(user.avg_rating) ? 'bi-star-fill' : 'bi-star'}`}></i>)}
                  <span className="ms-1">{user.avg_rating} ({user.review_count})</span>
                </div>
              )}
              {user.years_gardening && <p className="text-muted"><i className="bi bi-calendar-heart me-1"></i>{user.years_gardening} years gardening</p>}
              {user.bio && <p>{user.bio}</p>}
              {me && me.id !== parseInt(userId) && (
                <Link to={`/messages/new/${user.id}`} className="btn btn-outline-success mt-2"><i className="bi bi-chat me-1"></i>Message</Link>
              )}
            </div>
          </div>
        </div>
        <div className="col-md-8">
          {user.gardening_story && (
            <div className="card mb-3"><div className="card-body"><h5><i className="bi bi-book me-2"></i>My Gardening Story</h5><p>{user.gardening_story}</p></div></div>
          )}
          {gallery.length > 0 && (
            <div className="card mb-3"><div className="card-body"><h5><i className="bi bi-images me-2"></i>Garden Gallery</h5><div className="row">{gallery.map((img, i) => (
              <div key={i} className="col-4"><img src={`${IMAGE_BASE}${img}`} className="w-100 rounded" style={{ height: 150, objectFit: 'cover' }} alt="" /></div>
            ))}</div></div></div>
          )}
          {listings.length > 0 && (
            <><h4 className="mt-3 mb-3">Active Listings</h4><div className="row">{listings.map(l => <ListingCard key={l.id} listing={l} />)}</div></>
          )}
          {reviews.length > 0 && (
            <><h4 className="mt-3 mb-3">Reviews</h4>{reviews.map(r => (
              <div key={r.id} className="card mb-2"><div className="card-body">
                <div className="d-flex justify-content-between"><strong>{r.reviewer_name}</strong><span className="star-rating">{[1,2,3,4,5].map(s => <i key={s} className={`bi ${s <= r.rating ? 'bi-star-fill' : 'bi-star'}`}></i>)}</span></div>
                {r.comment && <p className="mt-1 mb-0">{r.comment}</p>}
                <small className="text-muted">{new Date(r.created_at).toLocaleDateString()}</small>
              </div></div>
            ))}</>
          )}
        </div>
      </div>
    </>
  );
}
