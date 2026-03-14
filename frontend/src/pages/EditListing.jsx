import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { listingsAPI } from '../api';

export default function EditListing() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [categories, setCategories] = useState([]);
  const [units, setUnits] = useState([]);
  const [form, setForm] = useState(null);
  const [delivery, setDelivery] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [actionError, setActionError] = useState('');

  useEffect(() => {
    Promise.all([listingsAPI.detail(id), listingsAPI.categories()]).then(([lRes, cRes]) => {
      const l = lRes.data;
      setForm({ title: l.title, description: l.description || '', vegetable_type: l.vegetable_type || '', price: l.price, unit: l.unit, quantity_available: l.quantity_available, delivery_radius_miles: l.delivery_radius_miles || 5, pickup_instructions: l.pickup_instructions || '' });
      setDelivery(l.delivery_available);
      setCategories(cRes.data.categories);
      setUnits(cRes.data.units);
    }).catch(() => setError('Failed to load listing data.'));
  }, [id]);

  if (error) return <div className="alert alert-danger"><i className="bi bi-exclamation-triangle me-2"></i>{error}</div>;
  if (!form) return <div className="text-center py-5"><div className="spinner-border text-success"></div></div>;

  const handleChange = (e) => setForm({ ...form, [e.target.name]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    const fd = new FormData();
    Object.entries(form).forEach(([k, v]) => fd.append(k, v));
    fd.append('delivery_available', delivery);
    ['image', 'image_2', 'image_3'].forEach(name => {
      const file = e.target.elements[name]?.files[0];
      if (file) fd.append(name, file);
    });
    try {
      await listingsAPI.update(id, fd);
      navigate(`/listings/${id}`);
    } catch {
      setActionError('Failed to update listing. Please try again.');
      setSubmitting(false);
    }
  };

  return (
    <div className="row justify-content-center">
      <div className="col-md-8">
        <h2 className="mb-4"><i className="bi bi-pencil me-2"></i>Edit Listing</h2>
        {actionError && (
          <div className="alert alert-danger py-2 d-flex justify-content-between align-items-center">
            <span><i className="bi bi-exclamation-circle me-2"></i>{actionError}</span>
            <button className="btn-close btn-sm" onClick={() => setActionError('')}></button>
          </div>
        )}
        <form onSubmit={submit}>
          <div className="row g-3">
            <div className="col-12"><label className="form-label">Title</label><input className="form-control" name="title" value={form.title} onChange={handleChange} required /></div>
            <div className="col-12"><label className="form-label">Description</label><textarea className="form-control" name="description" rows={3} value={form.description} onChange={handleChange} /></div>
            <div className="col-md-4"><label className="form-label">Category</label><select className="form-select" name="vegetable_type" value={form.vegetable_type} onChange={handleChange}><option value="">Select...</option>{categories.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}</select></div>
            <div className="col-md-3"><label className="form-label">Price</label><input type="number" step="0.01" className="form-control" name="price" value={form.price} onChange={handleChange} required /></div>
            <div className="col-md-3"><label className="form-label">Unit</label><select className="form-select" name="unit" value={form.unit} onChange={handleChange}>{units.map(u => <option key={u.value} value={u.value}>{u.label}</option>)}</select></div>
            <div className="col-md-2"><label className="form-label">Quantity</label><input type="number" className="form-control" name="quantity_available" value={form.quantity_available} onChange={handleChange} min={1} /></div>
            <div className="col-md-6">
              <div className="form-check"><input className="form-check-input" type="checkbox" checked={delivery} onChange={e => setDelivery(e.target.checked)} id="del" /><label className="form-check-label" htmlFor="del">I can deliver to buyers</label></div>
              <small className="text-muted">Delivery fees are set by the platform. This indicates you're willing to deliver within a radius.</small>
              {delivery && (
                <div className="mt-2">
                  <label className="form-label small fw-semibold">Maximum delivery distance</label>
                  <select className="form-select" name="delivery_radius_miles" value={form.delivery_radius_miles} onChange={handleChange}>
                    <option value="1">1 mile</option>
                    <option value="5">5 miles</option>
                    <option value="10">10 miles</option>
                    <option value="15">15 miles</option>
                    <option value="25">25 miles</option>
                  </select>
                  <small className="text-muted">How far you'll travel to deliver. Buyers outside this range can still pick up.</small>
                </div>
              )}
            </div>
            <div className="col-12"><label className="form-label">Pickup Instructions</label><textarea className="form-control" name="pickup_instructions" rows={2} value={form.pickup_instructions} onChange={handleChange} /></div>
            <div className="col-md-4"><label className="form-label">New Image 1</label><input type="file" className="form-control" name="image" accept="image/*" /></div>
            <div className="col-md-4"><label className="form-label">New Image 2</label><input type="file" className="form-control" name="image_2" accept="image/*" /></div>
            <div className="col-md-4"><label className="form-label">New Image 3</label><input type="file" className="form-control" name="image_3" accept="image/*" /></div>
          </div>
          <button type="submit" className="btn btn-success mt-3" disabled={submitting}>{submitting ? 'Saving...' : 'Save Changes'}</button>
        </form>
      </div>
    </div>
  );
}
