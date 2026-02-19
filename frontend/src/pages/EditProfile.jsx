import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { profileAPI } from '../api';
import { useAuth } from '../AuthContext';

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
  });
  const [saving, setSaving] = useState(false);

  const handleChange = (e) => setForm({ ...form, [e.target.name]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    const fd = new FormData();
    Object.entries(form).forEach(([k, v]) => fd.append(k, v));
    ['profile_image', 'gallery_image_1', 'gallery_image_2', 'gallery_image_3'].forEach(name => {
      const file = e.target.elements[name]?.files[0];
      if (file) fd.append(name, file);
    });
    try {
      await profileAPI.update(fd);
      await fetchUser();
      navigate(`/profile/${user.id}`);
    } catch {
      alert('Error updating profile');
      setSaving(false);
    }
  };

  if (!user) return <p>Please log in.</p>;

  return (
    <div className="row justify-content-center">
      <div className="col-md-8">
        <h2 className="mb-4"><i className="bi bi-pencil me-2"></i>Edit Profile</h2>
        <form onSubmit={submit}>
          <div className="row g-3">
            <div className="col-md-6"><label className="form-label">Display Name</label><input className="form-control" name="display_name" value={form.display_name} onChange={handleChange} /></div>
            <div className="col-md-6"><label className="form-label">Years Gardening</label><input type="number" className="form-control" name="years_gardening" value={form.years_gardening} onChange={handleChange} /></div>
            <div className="col-12"><label className="form-label">Bio</label><textarea className="form-control" name="bio" rows={2} value={form.bio} onChange={handleChange} /></div>
            <div className="col-12"><label className="form-label">Gardening Story</label><textarea className="form-control" name="gardening_story" rows={4} value={form.gardening_story} onChange={handleChange} /></div>
            <div className="col-md-6"><label className="form-label">Address</label><input className="form-control" name="address" value={form.address} onChange={handleChange} /></div>
            <div className="col-md-3"><label className="form-label">City</label><input className="form-control" name="city" value={form.city} onChange={handleChange} /></div>
            <div className="col-md-1"><label className="form-label">State</label><input className="form-control" name="state" value={form.state} onChange={handleChange} /></div>
            <div className="col-md-2"><label className="form-label">ZIP</label><input className="form-control" name="zip_code" value={form.zip_code} onChange={handleChange} /></div>
            <div className="col-md-6"><label className="form-label">Profile Image</label><input type="file" className="form-control" name="profile_image" accept="image/*" /></div>
            <div className="col-md-6"><label className="form-label">Gallery Image 1</label><input type="file" className="form-control" name="gallery_image_1" accept="image/*" /></div>
            <div className="col-md-6"><label className="form-label">Gallery Image 2</label><input type="file" className="form-control" name="gallery_image_2" accept="image/*" /></div>
            <div className="col-md-6"><label className="form-label">Gallery Image 3</label><input type="file" className="form-control" name="gallery_image_3" accept="image/*" /></div>
          </div>
          <button type="submit" className="btn btn-success mt-3" disabled={saving}>{saving ? 'Saving...' : 'Save Profile'}</button>
        </form>
      </div>
    </div>
  );
}
