import { useState, useEffect, useRef } from 'react';
import { photosAPI } from '../api';
import { confirmDialog, lightbox } from './dialog/dialogService';

const CATEGORIES = ['all', 'general', 'garden', 'harvest', 'event', 'plot'];

export default function PhotoLibrary({ gardenId = null }) {
  const [photos, setPhotos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [category, setCategory] = useState('all');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [uploadCategory, setUploadCategory] = useState('general');
  const [caption, setCaption] = useState('');
  const [uploadError, setUploadError] = useState('');
  const fileInputRef = useRef(null);
  // Upvotes + comments
  const [openId, setOpenId] = useState(null);
  const [commentsMap, setCommentsMap] = useState({});
  const [commentText, setCommentText] = useState('');
  const [posting, setPosting] = useState(false);
  const [proRequired, setProRequired] = useState(false);

  const loadPhotos = (pageNum = 1, cat = category) => {
    setLoading(true);
    const params = { page: pageNum, per_page: 20 };
    if (cat !== 'all') params.category = cat;
    if (gardenId) params.garden_id = gardenId;

    // For a garden, always show the whole wall (every member's photos) with
    // social counts; the personal /photos list is only for non-garden contexts.
    const fetchFn = gardenId
      ? photosAPI.gardenPhotos(gardenId, params)
      : photosAPI.list(params);

    fetchFn.then(res => {
      setProRequired(!!res.data.pro_required);
      if (pageNum === 1) {
        setPhotos(res.data.photos || []);
      } else {
        setPhotos(prev => [...prev, ...(res.data.photos || [])]);
      }
      setTotalPages(res.data.pages || 1);
      setPage(pageNum);
      setLoading(false);
    }).catch(() => setLoading(false));
  };

  useEffect(() => {
    loadPhotos(1, category);
  }, [category, gardenId]);

  const handleUpload = async (e) => {
    const files = Array.from(e.target.files);
    if (files.length === 0) return;

    setUploading(true);
    setUploadError('');
    for (const file of files) {
      const formData = new FormData();
      formData.append('photo', file);
      formData.append('category', uploadCategory);
      formData.append('caption', caption);
      if (gardenId) formData.append('garden_id', gardenId);

      try {
        await photosAPI.upload(formData);
      } catch (err) {
        setUploadError(err.response?.data?.error || `Failed to upload ${file.name}. Please try again.`);
      }
    }
    setUploading(false);
    setCaption('');
    if (fileInputRef.current) fileInputRef.current.value = '';
    loadPhotos(1, category);
  };

  const handleDelete = async (photoId) => {
    if (!(await confirmDialog('Delete this photo?', { danger: true, confirmText: 'Delete', title: 'Delete photo' }))) return;
    try {
      await photosAPI.delete(photoId);
      setPhotos(prev => prev.filter(p => p.id !== photoId));
      if (openId === photoId) setOpenId(null);
    } catch (err) {
      setUploadError(err.response?.data?.error || 'Failed to delete photo. Please try again.');
    }
  };

  const handleLike = async (photoId) => {
    try {
      const r = await photosAPI.like(photoId);
      setPhotos(prev => prev.map(p => p.id === photoId
        ? { ...p, liked_by_me: r.data.liked, likes_count: r.data.likes_count } : p));
    } catch (err) {
      setUploadError(err.response?.data?.error || 'Could not update upvote.');
    }
  };

  const toggleComments = async (photoId) => {
    if (openId === photoId) { setOpenId(null); return; }
    setOpenId(photoId);
    setCommentText('');
    if (!commentsMap[photoId]) {
      try {
        const r = await photosAPI.comments(photoId);
        setCommentsMap(prev => ({ ...prev, [photoId]: r.data.comments || [] }));
      } catch {
        setCommentsMap(prev => ({ ...prev, [photoId]: [] }));
      }
    }
  };

  const addComment = async (photoId) => {
    if (!commentText.trim()) return;
    setPosting(true);
    try {
      const r = await photosAPI.addComment(photoId, { content: commentText.trim() });
      setCommentsMap(prev => ({ ...prev, [photoId]: [...(prev[photoId] || []), r.data] }));
      setCommentText('');
      setPhotos(prev => prev.map(p => p.id === photoId
        ? { ...p, comments_count: (p.comments_count || 0) + 1 } : p));
    } catch (err) {
      setUploadError(err.response?.data?.error || 'Failed to post comment.');
    }
    setPosting(false);
  };

  const deleteComment = async (photoId, commentId) => {
    if (!(await confirmDialog('Delete this comment?', { danger: true, confirmText: 'Delete', title: 'Delete comment' }))) return;
    try {
      await photosAPI.deleteComment(photoId, commentId);
      setCommentsMap(prev => ({ ...prev, [photoId]: (prev[photoId] || []).filter(c => c.id !== commentId) }));
      setPhotos(prev => prev.map(p => p.id === photoId
        ? { ...p, comments_count: Math.max(0, (p.comments_count || 0) - 1) } : p));
    } catch (err) {
      setUploadError(err.response?.data?.error || 'Failed to delete comment.');
    }
  };

  const formatSize = (bytes) => {
    if (!bytes) return '';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  if (proRequired) {
    return (
      <div className="text-center py-5" style={{ border: '1px dashed var(--brand-border)', borderRadius: 'var(--radius-lg, 14px)', background: 'var(--brand-pale)' }}>
        <i className="bi bi-images" style={{ fontSize: '2.4rem', color: 'var(--brand-primary)' }}></i>
        <h5 className="fw-bold mt-2 mb-1">Photo gallery is a Garden Pro feature</h5>
        <p className="text-muted mb-3" style={{ maxWidth: 460, margin: '0 auto' }}>
          Upgrade to Garden Pro to share photos with likes &amp; comments on your garden page.
        </p>
        <a className="btn btn-success" href={`/gardens/${gardenId}/billing`}>
          <i className="bi bi-stars me-1"></i>Upgrade to Garden Pro
        </a>
      </div>
    );
  }

  return (
    <div>
      {uploadError && (
        <div className="alert alert-danger py-2 d-flex justify-content-between align-items-center mb-3">
          <span><i className="bi bi-exclamation-circle me-2"></i>{uploadError}</span>
          <button className="btn-close btn-sm" onClick={() => setUploadError('')}></button>
        </div>
      )}
      {/* Upload Section */}
      <div className="card mb-4" style={{ border: '2px dashed var(--brand-light-green)', backgroundColor: 'var(--brand-pale)' }}>
        <div className="card-body">
          <div className="row align-items-end g-3">
            <div className="col-md-3">
              <label className="form-label small fw-semibold">Category</label>
              <select className="form-select form-select-sm" value={uploadCategory}
                onChange={e => setUploadCategory(e.target.value)}>
                {CATEGORIES.filter(c => c !== 'all').map(c => (
                  <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>
                ))}
              </select>
            </div>
            <div className="col-md-4">
              <label className="form-label small fw-semibold">Caption (optional)</label>
              <input type="text" className="form-control form-control-sm" placeholder="Add a caption..."
                value={caption} onChange={e => setCaption(e.target.value)} />
            </div>
            <div className="col-md-5">
              <input type="file" ref={fileInputRef} accept="image/*" multiple
                className="d-none" onChange={handleUpload} />
              <button className="btn w-100" style={{ backgroundColor: 'var(--brand-secondary)', color: 'white' }}
                onClick={() => fileInputRef.current?.click()} disabled={uploading}>
                {uploading ? (
                  <><span className="spinner-border spinner-border-sm me-2"></span>Uploading...</>
                ) : (
                  <><i className="bi bi-cloud-upload me-2"></i>Upload Photos</>
                )}
              </button>
              <div className="text-muted small mt-1">Max 20MB per image. Auto-resized to ≤ 4MB.</div>
            </div>
          </div>
        </div>
      </div>

      {/* Filter */}
      <div className="d-flex justify-content-between align-items-center mb-3">
        <div className="d-flex gap-2">
          {CATEGORIES.map(c => (
            <button key={c}
              className={`btn btn-sm ${category === c ? 'btn-success' : 'btn-outline-secondary'}`}
              onClick={() => setCategory(c)}>
              {c.charAt(0).toUpperCase() + c.slice(1)}
            </button>
          ))}
        </div>
        <span className="text-muted small">{photos.length} photo{photos.length !== 1 ? 's' : ''}</span>
      </div>

      {/* Photo Grid */}
      {loading && photos.length === 0 ? (
        <div className="text-center py-5"><div className="spinner-border" style={{ color: 'var(--brand-secondary)' }}></div></div>
      ) : photos.length === 0 ? (
        <div className="text-center py-5 text-muted">
          <i className="bi bi-image" style={{ fontSize: '3rem' }}></i>
          <p className="mt-2">No photos yet. Upload your first one!</p>
        </div>
      ) : (
        <div className="row g-3">
          {photos.map(photo => (
            <div key={photo.id} className="col-6 col-md-4 col-lg-3">
              <div className="card h-100" style={{ border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.06)', overflow: 'hidden' }}>
                <div style={{ position: 'relative' }}>
                  <img src={photo.url} alt={photo.caption || 'Photo'}
                    style={{ width: '100%', height: '160px', objectFit: 'cover', cursor: 'zoom-in' }}
                    loading="lazy"
                    onClick={() => lightbox(photo.url, { alt: photo.caption || 'Photo', caption: photo.caption })} />
                  <button className="btn btn-sm btn-danger"
                    style={{ position: 'absolute', top: '8px', right: '8px', opacity: 0.8, borderRadius: '50%', width: '28px', height: '28px', padding: 0 }}
                    onClick={() => handleDelete(photo.id)}
                    title="Delete photo">
                    <i className="bi bi-trash" style={{ fontSize: '0.7rem' }}></i>
                  </button>
                  <span className="badge" style={{
                    position: 'absolute', bottom: '8px', left: '8px',
                    backgroundColor: 'rgba(0,0,0,0.6)', fontSize: '0.65rem',
                  }}>{photo.category}</span>
                </div>
                <div className="card-body p-2">
                  {photo.caption && <p className="small mb-1" style={{ lineHeight: 1.3 }}>{photo.caption}</p>}
                  <div className="text-muted" style={{ fontSize: '0.7rem' }}>
                    {photo.width}&times;{photo.height} &middot; {formatSize(photo.file_size)}
                    {photo.uploaded_at && <span className="ms-1">&middot; {new Date(photo.uploaded_at).toLocaleDateString()}</span>}
                  </div>
                  <div className="d-flex align-items-center gap-3 mt-1">
                    <button type="button" className="btn btn-sm p-0 border-0 bg-transparent d-inline-flex align-items-center"
                      style={{ color: photo.liked_by_me ? 'var(--brand-secondary)' : '#888', fontSize: '0.78rem' }}
                      onClick={() => handleLike(photo.id)} title="Upvote">
                      <i className={`bi ${photo.liked_by_me ? 'bi-hand-thumbs-up-fill' : 'bi-hand-thumbs-up'} me-1`}></i>
                      {photo.likes_count > 0 ? photo.likes_count : 'Upvote'}
                    </button>
                    <button type="button" className="btn btn-sm p-0 border-0 bg-transparent d-inline-flex align-items-center"
                      style={{ color: openId === photo.id ? 'var(--brand-secondary)' : '#888', fontSize: '0.78rem' }}
                      onClick={() => toggleComments(photo.id)} title="Comments">
                      <i className="bi bi-chat me-1"></i>
                      {photo.comments_count > 0 ? photo.comments_count : 'Comment'}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Expanded comments for the selected photo */}
      {openId && (() => {
        const p = photos.find(x => x.id === openId);
        if (!p) return null;
        const list = commentsMap[openId] || [];
        return (
          <div className="card mt-3" style={{ border: '1px solid #e5e6e6', borderRadius: '12px' }}>
            <div className="card-body py-3">
              <div className="d-flex justify-content-between align-items-center mb-2">
                <h6 className="fw-bold mb-0"><i className="bi bi-chat-dots me-2"></i>Comments{p.caption ? ` · ${p.caption}` : ''}</h6>
                <button className="btn btn-sm btn-link text-muted p-0" onClick={() => setOpenId(null)} title="Close"><i className="bi bi-x-lg"></i></button>
              </div>
              {list.length === 0 ? (
                <p className="text-muted small mb-2">No comments yet. Be the first!</p>
              ) : (
                <div className="mb-2">
                  {list.map(c => (
                    <div key={c.id} className="d-flex justify-content-between align-items-start py-1" style={{ borderBottom: '1px solid #f1f2f2' }}>
                      <div className="small">
                        <span className="fw-semibold">{c.user_name}</span>{' '}
                        <span style={{ whiteSpace: 'pre-wrap' }}>{c.content}</span>
                        {c.created_at && <span className="text-muted ms-2" style={{ fontSize: '0.7rem' }}>{new Date(c.created_at).toLocaleDateString()}</span>}
                      </div>
                      <button className="btn btn-sm btn-link text-danger p-0 ms-2" title="Delete comment" onClick={() => deleteComment(p.id, c.id)}>
                        <i className="bi bi-trash" style={{ fontSize: '0.7rem' }}></i>
                      </button>
                    </div>
                  ))}
                </div>
              )}
              <div className="d-flex gap-2">
                <input type="text" className="form-control form-control-sm" placeholder="Add a comment…" maxLength={1000}
                  value={commentText} onChange={e => setCommentText(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addComment(p.id); } }} />
                <button className="btn btn-sm" style={{ backgroundColor: 'var(--brand-secondary)', color: 'white' }}
                  disabled={posting || !commentText.trim()} onClick={() => addComment(p.id)}>
                  {posting ? '…' : 'Post'}
                </button>
              </div>
            </div>
          </div>
        );
      })()}

      {/* Load More */}
      {page < totalPages && (
        <div className="text-center mt-4">
          <button className="btn btn-outline-success" onClick={() => loadPhotos(page + 1)} disabled={loading}>
            {loading ? 'Loading...' : 'Load More'}
          </button>
        </div>
      )}
    </div>
  );
}
