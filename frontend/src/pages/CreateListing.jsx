import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { listingsAPI } from '../api';

export default function CreateListing() {
  const navigate = useNavigate();
  const [categories, setCategories] = useState([]);
  const [units, setUnits] = useState([]);
  const [useProfile, setUseProfile] = useState(true);
  const [delivery, setDelivery] = useState(false);
  const [form, setForm] = useState({ title: '', description: '', vegetable_type: '', price: '', unit: 'each', quantity_available: 1, delivery_radius_miles: 5, pickup_instructions: '', pickup_address: '', pickup_city: '', pickup_state: '', pickup_zip: '' });
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    listingsAPI.categories().then(res => { setCategories(res.data.categories); setUnits(res.data.units); });
  }, []);

  const handleChange = (e) => setForm({ ...form, [e.target.name]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    const fd = new FormData();
    Object.entries(form).forEach(([k, v]) => fd.append(k, v));
    fd.append('use_profile_address', useProfile);
    fd.append('delivery_available', delivery);
    ['image', 'image_2', 'image_3'].forEach(name => {
      const file = e.target.elements[name]?.files[0];
      if (file) fd.append(name, file);
    });
    try {
      const res = await listingsAPI.create(fd);
      navigate(`/listings/${res.data.id}`);
    } catch (err) {
      alert(err.response?.data?.error || 'Error creating listing');
      setSubmitting(false);
    }
  };

  return (
    <div className="row justify-content-center">
      <div className="col-md-8">
        <h2 className="mb-4"><i className="bi bi-plus-circle me-2"></i>Create Listing</h2>
        <form onSubmit={submit}>
          <div className="row g-3">
            <div className="col-12"><label className="form-label">Title</label><input className="form-control" name="title" value={form.title} onChange={handleChange} required /></div>
            <div className="col-12"><label className="form-label">Description</label><textarea className="form-control" name="description" rows={3} value={form.description} onChange={handleChange} /></div>
            <div className="col-md-4">
              <label className="form-label">Category</label>
              <select className="form-select" name="vegetable_type" value={form.vegetable_type} onChange={handleChange} required>
                <option value="">Select...</option>
                {categories.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
              </select>
            </div>
            <div className="col-md-3"><label className="form-label">Price</label><input type="number" step="0.01" className="form-control" name="price" value={form.price} onChange={handleChange} required /></div>
            <div className="col-md-3">
              <label className="form-label">Unit</label>
              <select className="form-select" name="unit" value={form.unit} onChange={handleChange}>
                {units.map(u => <option key={u.value} value={u.value}>{u.label}</option>)}
              </select>
            </div>
            <div className="col-md-2"><label className="form-label">Quantity</label><input type="number" className="form-control" name="quantity_available" value={form.quantity_available} onChange={handleChange} min={1} required /></div>
            <div className="col-12">
              <div className="form-check"><input className="form-check-input" type="checkbox" checked={useProfile} onChange={e => setUseProfile(e.target.checked)} id="useProfile" /><label className="form-check-label" htmlFor="useProfile">Use my profile address for pickup</label></div>
            </div>
            {!useProfile && (
              <>
                <div className="col-md-6"><input className="form-control" name="pickup_address" placeholder="Pickup Address" value={form.pickup_address} onChange={handleChange} /></div>
                <div className="col-md-3"><input className="form-control" name="pickup_city" placeholder="City" value={form.pickup_city} onChange={handleChange} /></div>
                <div className="col-md-1"><input className="form-control" name="pickup_state" placeholder="ST" value={form.pickup_state} onChange={handleChange} /></div>
                <div className="col-md-2"><input className="form-control" name="pickup_zip" placeholder="ZIP" value={form.pickup_zip} onChange={handleChange} /></div>
              </>
            )}
            <div className="col-md-6">
              <div className="form-check"><input className="form-check-input" type="checkbox" checked={delivery} onChange={e => setDelivery(e.target.checked)} id="delivery" /><label className="form-check-label" htmlFor="delivery">Offer delivery</label></div>
              {delivery && <input type="number" className="form-control mt-2" name="delivery_radius_miles" value={form.delivery_radius_miles} onChange={handleChange} placeholder="Delivery radius (miles)" />}
            </div>
            <div className="col-12"><label className="form-label">Pickup Instructions</label><textarea className="form-control" name="pickup_instructions" rows={2} value={form.pickup_instructions} onChange={handleChange} placeholder="e.g. Text when you arrive" /></div>
            <div className="col-md-4"><label className="form-label">Image 1</label><input type="file" className="form-control" name="image" accept="image/*" /></div>
            <div className="col-md-4"><label className="form-label">Image 2</label><input type="file" className="form-control" name="image_2" accept="image/*" /></div>
            <div className="col-md-4"><label className="form-label">Image 3</label><input type="file" className="form-control" name="image_3" accept="image/*" /></div>
          </div>
          <button type="submit" className="btn btn-success mt-3" disabled={submitting}>{submitting ? 'Creating...' : 'Create Listing'}</button>
        </form>
      </div>
    </div>
  );
}
