import { useState, useRef } from 'react';
import { photosAPI } from '../api';
import { useTranslation } from 'react-i18next';

/**
 * Reusable photo upload input that replaces URL text fields.
 * Uploads via /api/photos/upload and returns the resulting path.
 *
 * Props:
 *   value     - current photo URL (or path like /static/uploads/...)
 *   onChange  - called with the new URL string after upload
 *   label     - field label (default: "Photo")
 *   category  - photo category for the database (default: "general")
 *   gardenId  - optional garden ID to associate the photo with
 *   hint      - optional helper text below the input
 */
export default function PhotoUploadInput({ value, onChange, label = null, category = 'general', gardenId = null, hint = null }) {
  const { t } = useTranslation();
  // Defaulting the label to the English word 'Photo' put English on a
  // Spanish form without any caller doing anything wrong.
  const fieldLabel = label ?? t('upload.photo');
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const fileRef = useRef(null);

  const handleFileSelect = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setError('');

    const formData = new FormData();
    formData.append('photo', file);
    formData.append('category', category);
    if (gardenId) formData.append('garden_id', gardenId);

    try {
      const res = await photosAPI.upload(formData);
      onChange(res.data.url); // e.g. "/static/uploads/photo_abc123.jpg"
    } catch (err) {
      setError(err.response?.data?.error || t('photo.errUploadFailed'));
    }

    setUploading(false);
    if (fileRef.current) fileRef.current.value = '';
  };

  const handleRemove = () => {
    onChange('');
  };

  return (
    <div className="mb-3">
      <label className="form-label fw-semibold">{fieldLabel}</label>

      {value ? (
        <div style={{
          border: '2px solid var(--brand-light-green)',
          borderRadius: '12px',
          padding: '12px',
          backgroundColor: 'var(--brand-pale)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <img
              src={value}
              alt={t('upload.uploaded')}
              style={{
                width: '80px',
                height: '80px',
                objectFit: 'cover',
                borderRadius: '8px',
                border: '1px solid #ddd',
              }}
              onError={e => { e.target.style.display = 'none'; }}
            />
            <div style={{ flex: 1 }}>
              <div className="text-success small fw-semibold mb-1">
                <i className="bi bi-check-circle me-1"></i>{t('upload.photoUploaded')}
              </div>
              <div className="d-flex gap-2">
                <input type="file" ref={fileRef} accept="image/*" className="d-none" onChange={handleFileSelect} />
                <button
                  type="button"
                  className="btn btn-sm btn-outline-secondary"
                  onClick={() => fileRef.current?.click()}
                  disabled={uploading}
                >
                  <i className="bi bi-arrow-repeat me-1"></i>{t('upload.replace')}
                </button>
                <button
                  type="button"
                  className="btn btn-sm btn-outline-danger"
                  onClick={handleRemove}
                >
                  <i className="bi bi-trash me-1"></i>{t('upload.remove')}
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div>
          <input type="file" ref={fileRef} accept="image/*" className="d-none" onChange={handleFileSelect} />
          <button
            type="button"
            className="btn w-100"
            style={{
              border: '2px dashed var(--brand-light-green)',
              backgroundColor: 'var(--brand-pale)',
              color: 'var(--brand-secondary)',
              padding: '20px',
              borderRadius: '12px',
            }}
            onClick={() => fileRef.current?.click()}
            disabled={uploading}
          >
            {uploading ? (
              <>
                <span className="spinner-border spinner-border-sm me-2"></span>
                {t('upload.uploading')}
              </>
            ) : (
              <>
                <i className="bi bi-cloud-upload" style={{ fontSize: '1.5rem', display: 'block', marginBottom: '4px' }}></i>
                {t('upload.clickToUpload')}
              </>
            )}
          </button>
          <small className="text-muted d-block mt-1">
            {hint || t('photo.photoHint')}
          </small>
        </div>
      )}

      {error && (
        <div className="text-danger small mt-1">
          <i className="bi bi-exclamation-triangle me-1"></i>{error}
        </div>
      )}
    </div>
  );
}
