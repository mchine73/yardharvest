import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { listingsAPI, IMAGE_BASE } from '../api';

export default function MyListings() {
  const [listings, setListings] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetch = () => listingsAPI.mine().then(res => { setListings(res.data); setLoading(false); });
  useEffect(() => { fetch(); }, []);

  const toggle = async (id) => { await listingsAPI.toggle(id); fetch(); };
  const del = async (id) => { if (confirm('Remove this listing?')) { await listingsAPI.delete(id); fetch(); } };

  if (loading) return <div className="text-center py-5"><div className="spinner-border text-success"></div></div>;

  return (
    <>
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h1><i className="bi bi-basket me-2"></i>My Listings</h1>
        <Link to="/listings/create" className="btn btn-success"><i className="bi bi-plus-circle me-1"></i>New Listing</Link>
      </div>
      {listings.length === 0 ? (
        <p className="text-muted">No listings yet. Create your first one!</p>
      ) : (
        <div className="table-responsive">
          <table className="table align-middle">
            <thead><tr><th></th><th>Title</th><th>Price</th><th>Qty</th><th>Status</th><th>Actions</th></tr></thead>
            <tbody>
              {listings.map(l => (
                <tr key={l.id}>
                  <td>{l.image_filename ? <img src={`${IMAGE_BASE}${l.image_filename}`} alt="" style={{ width: 50, height: 50, objectFit: 'cover' }} className="rounded" /> : l.image_url ? <img src={l.image_url} alt="" style={{ width: 50, height: 50, objectFit: 'cover' }} className="rounded" /> : <i className="bi bi-image text-muted"></i>}</td>
                  <td><Link to={`/listings/${l.id}`}>{l.title}</Link></td>
                  <td>${l.price.toFixed(2)} / {l.unit}</td>
                  <td>{l.quantity_available}</td>
                  <td><span className={`badge ${l.is_active ? 'bg-success' : 'bg-secondary'}`}>{l.is_active ? 'Active' : 'Inactive'}</span></td>
                  <td>
                    <div className="d-flex gap-1">
                      <Link to={`/listings/${l.id}/edit`} className="btn btn-sm btn-outline-primary"><i className="bi bi-pencil"></i></Link>
                      <button className="btn btn-sm btn-outline-warning" onClick={() => toggle(l.id)}>{l.is_active ? 'Deactivate' : 'Activate'}</button>
                      <button className="btn btn-sm btn-outline-danger" onClick={() => del(l.id)}><i className="bi bi-trash"></i></button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
