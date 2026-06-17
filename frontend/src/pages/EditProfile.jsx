import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { profileAPI, authAPI } from '../api';
import { useAuth } from '../AuthContext';

const MAX_IMAGE_MB = 4;
const MAX_IMAGE_BYTES = MAX_IMAGE_MB * 1024 * 1024;

export default function EditProfile() {
  const { user, fetchUser } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    display_name: user?.display_name || '',
    bio: user?.bio || '',
    gardening_story: user?.gardening_story || '',
    years_gardening: user?.years_gardening || '',
    address: user?.address || '',
    city: user?.city || '',
    state: user?.state || '',
    zip_code: user?.zip_code || '',
    phone_number: user?.phone_number || '',
    sms_opt_in: user?.sms_opt_in || false,
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  // Email change (verified via link sent to the new address)
  const [newEmail, setNewEmail] = useState('');
  const [emailPassword, setEmailPassword] = useState('');
  const [emailMsg, setEmailMsg] = useState('');
  const [emailError, setEmailError] = useState('');
  const [emailSending, setEmailSending] = useState(false);

  const submitEmailChange = async (e) => {
    e.preventDefault();
    setEmailMsg('');
    setEmailError('');
    setEmailSending(true);
    try {
      const res = await authAPI.requestEmailChange(newEmail.trim(), emailPassword);
      setEmailMsg(res.data.message);
      setNewEmail('');
      setEmailPassword('');
    } catch (err) {
      setEmailError(err.response?.data?.error || 'Failed to send verification email. Please try again.');
    } finally {
      setEmailSending(false);
    }
  };

  const handleChange = (e) => setForm({ ...form, [e.target.name]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setError('');

    // Client-side image size validation
    const imageFields = ['profile_image', 'gallery_image_1', 'gallery_image_2', 'gallery_image_3'];
    for (const name of imageFields) {
      const file = e.target.elements[name]?.files[0];
      if (file && file.size > MAX_IMAGE_BYTES) {
        setError(`${name.replace(/_/g, ' ')} is too large (${(file.size / (1024 * 1024)).toFixed(1)}MB). Maximum is ${MAX_IMAGE_MB}MB per image.`);
        return;
      }
    }

    setSaving(true);
    const fd = new FormData();
    Object.entries(form).forEach(([k, v]) => fd.append(k, v));
    imageFields.forEach(name => {
      const file = e.target.elements[name]?.files[0];
      if (file) fd.append(name, file);
    });
    try {
      await profileAPI.update(fd);
      await fetchUser();
      navigate(`/profile/${user.public_id}`);
    } catch (err) {
      setError(err.response?.data?.error || 'Error updating profile. Please try again.');
      setSaving(false);
    }
  };

  if (!user) return <p>Please log in.</p>;

  return (
    <div className="row justify-content-center">
      <div className="col-md-8">
        <h2 className="mb-3"><i className="bi bi-pencil me-2"></i>Edit Profile</h2>
        <p className="text-muted mb-4">Your profile tells your story to the community. Add photos of your garden and share what inspires you to grow.</p>

        {error && <div className="alert alert-danger"><i className="bi bi-exclamation-triangle me-2"></i>{error}</div>}

        <form onSubmit={submit}>
          <div className="row g-3">
            <div className="col-md-6"><label className="form-label">Display Name</label><input className="form-control" name="display_name" value={form.display_name} onChange={handleChange} /></div>
            <div className="col-md-6"><label className="form-label">Years Gardening</label><input type="number" className="form-control" name="years_gardening" value={form.years_gardening} onChange={handleChange} /></div>
            <div className="col-12"><label className="form-label">Bio</label><textarea className="form-control" name="bio" rows={2} value={form.bio} onChange={handleChange} placeholder="A brief introduction about yourself" /></div>
            <div className="col-12">
              <label className="form-label">Gardening Story</label>
              <textarea className="form-control" name="gardening_story" rows={4} value={form.gardening_story} onChange={handleChange}
                placeholder="Tell us about your gardening journey &#8212; how you started, what you love to grow, your favorite gardening moment..." />
            </div>
            <div className="col-md-6"><label className="form-label">Address</label><input className="form-control" name="address" value={form.address} onChange={handleChange} /></div>
            <div className="col-md-3"><label className="form-label">City</label><input className="form-control" name="city" value={form.city} onChange={handleChange} /></div>
            <div className="col-md-1"><label className="form-label">State</label><input className="form-control" name="state" value={form.state} onChange={handleChange} /></div>
            <div className="col-md-2"><label className="form-label">ZIP</label><input className="form-control" name="zip_code" value={form.zip_code} onChange={handleChange} /></div>
            <div className="col-12"><hr /></div>
            <div className="col-md-6">
              <label className="form-label"><i className="bi bi-telephone me-1"></i>Phone Number</label>
              <input className="form-control" name="phone_number" type="tel" value={form.phone_number} onChange={handleChange} placeholder="+1 (555) 555-5555" />
              <small className="text-muted">For SMS notifications (optional)</small>
            </div>
            <div className="col-md-6 d-flex align-items-end">
              <div className="form-check form-switch">
                <input className="form-check-input" type="checkbox" id="smsOptIn"
                  checked={form.sms_opt_in}
                  onChange={e => setForm({ ...form, sms_opt_in: e.target.checked })} />
                <label className="form-check-label" htmlFor="smsOptIn">Receive SMS notifications</label>
                <br /><small className="text-muted">Order confirmations, status updates, and messages</small>
              </div>
            </div>
            <div className="col-12"><hr /><p className="text-muted small mb-2"><i className="bi bi-camera me-1"></i>Images must be under {MAX_IMAGE_MB}MB each. Supported formats: PNG, JPG, GIF, WebP.</p></div>
            <div className="col-md-6"><label className="form-label">Profile Image</label><input type="file" className="form-control" name="profile_image" accept="image/*" /></div>
            <div className="col-md-6"><label className="form-label">Gallery Image 1</label><input type="file" className="form-control" name="gallery_image_1" accept="image/*" /></div>
            <div className="col-md-6"><label className="form-label">Gallery Image 2</label><input type="file" className="form-control" name="gallery_image_2" accept="image/*" /></div>
            <div className="col-md-6"><label className="form-label">Gallery Image 3</label><input type="file" className="form-control" name="gallery_image_3" accept="image/*" /></div>
          </div>
          <button type="submit" className="btn btn-success mt-3" disabled={saving}>{saving ? 'Saving...' : 'Save Profile'}</button>
        </form>

        {/* Account Email (change requires verification of the new address) */}
        <div className="card mt-4 mb-4">
          <div className="card-body">
            <h5 className="mb-1"><i className="bi bi-envelope-at me-2"></i>Account Email</h5>
            <p className="text-muted small mb-3">
              Currently <strong>{user.email}</strong>. To change it, enter your new address and
              current password — we'll email a verification link to the new address. Your email
              only updates after you confirm the link.
            </p>
            {emailMsg && <div className="alert alert-success py-2"><i className="bi bi-check-circle me-2"></i>{emailMsg}</div>}
            {emailError && <div className="alert alert-danger py-2"><i className="bi bi-exclamation-triangle me-2"></i>{emailError}</div>}
            <form onSubmit={submitEmailChange}>
              <div className="row g-3">
                <div className="col-md-6">
                  <label className="form-label">New Email Address</label>
                  <input type="email" className="form-control" value={newEmail} required
                    onChange={e => setNewEmail(e.target.value)} placeholder="you@example.com" autoComplete="email" />
                </div>
                <div className="col-md-6">
                  <label className="form-label">Current Password</label>
                  <input type="password" className="form-control" value={emailPassword} required
                    onChange={e => setEmailPassword(e.target.value)} autoComplete="current-password" />
                </div>
              </div>
              <button type="submit" className="btn btn-outline-success mt-3" disabled={emailSending || !newEmail || !emailPassword}>
                {emailSending ? <span className="spinner-border spinner-border-sm me-2"></span> : <i className="bi bi-send me-2"></i>}
                Send Verification Email
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
