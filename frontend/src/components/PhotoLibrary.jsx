import { useState, useEffect, useRef } from 'react';
import { photosAPI } from '../api';

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
  const fileInputRef = useRef(null);

  const loadPhotos = (pageNum = 1, cat = category) => {
    setLoading(true);
    const params = { page: pageNum, per_page: 20 };
    if (cat !== 'all') params.category = cat;
    if (gardenId) params.garden_id = gardenId;

    const fetchFn = gardenId && cat === 'all' && !params.category
      ? photosAPI.gardenPhotos(gardenId, params)
      : photosAPI.list(params);

    fetchFn.then(res => {
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
    for (const file of files) {
      const formData = new FormData();
      formData.append('photo', file);
      formData.append('category', uploadCategory);
      formData.append('caption', caption);
      if (gardenId) formData.append('garden_id', gardenId);

      try {
        await photosAPI.upload(formData);
      } catch (err) {
        alert(`Failed to upload ${file.name}: ${err.response?.data?.error || 'Error'}`);
      }
    }
    setUploading(false);
    setCaption('');
    if (fileInputRef.current) fileInputRef.current.value = '';
    loadPhotos(1, category);
  };

  const handleDelete = async (photoId) => {
    if (!window.confirm('Delete this photo?')) return;
    try {
      await photosAPI.delete(photoId);
      setPhotos(prev => prev.filter(p => p.id !== photoId));
    } catch (err) {
      alert(err.response?.data?.error || 'Error deleting photo');
    }
  };

  const formatSize = (bytes) => {
    if (!bytes) return '';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div>
      {/* Upload Section */}
      <div className="card mb-4" style={{ border: '2px dashed #74C69D', backgroundColor: '#D8EDDF' }}>
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
              <button className="btn w-100" style={{ backgroundColor: '#2d6a4f', color: 'white' }}
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
        <div className="text-center py-5"><div className="spinner-border" style={{ color: '#2d6a4f' }}></div></div>
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
                    style={{ width: '100%', height: '160px', objectFit: 'cover' }}
                    loading="lazy" />
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
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

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
