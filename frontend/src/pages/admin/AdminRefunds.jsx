import { useState, useEffect } from 'react';
import { adminAPI } from '../../api';
import { useAuth } from '../../AuthContext';

const STATUS_BADGE = { pending: 'bg-warning text-dark', completed: 'bg-success', failed: 'bg-danger' };

export default function AdminRefunds() {
  const { user } = useAuth();
  const [refunds, setRefunds] = useState([]);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [loading, setLoading] = useState(true);

  if (!user?.is_admin) return <div className="alert alert-danger">Access denied</div>;

  useEffect(() => {
    setLoading(true);
    adminAPI.refunds({ page }).then(res => {
      setRefunds(res.data.refunds);
      setPages(res.data.pages);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [page]);

  return (
    <>
      <h1 className="mb-4"><i className="bi bi-arrow-counterclockwise me-2"></i>Refund History</h1>

      {loading ? (
        <div className="text-center py-5"><div className="spinner-border text-success"></div></div>
      ) : refunds.length === 0 ? (
        <div className="text-center py-5 text-muted">No refunds issued yet</div>
      ) : (
        <div className="table-responsive">
          <table className="table table-hover align-middle">
            <thead className="table-light">
              <tr><th>ID</th><th>Type</th><th>Reference</th><th>Amount</th><th>Reason</th><th>Status</th><th>By</th><th>Date</th></tr>
            </thead>
            <tbody>
              {refunds.map(r => (
                <tr key={r.id}>
                  <td>#{r.id}</td>
                  <td><span className={`badge ${r.refund_type === 'marketplace' ? 'bg-primary' : 'bg-info text-dark'}`}>{r.refund_type}</span></td>
                  <td>{r.order_id ? `Order #${r.order_id}` : `Sub #${r.garden_subscription_id}`}</td>
                  <td className="text-danger fw-bold">-${r.amount.toFixed(2)}</td>
                  <td><small>{r.reason || '—'}</small></td>
                  <td><span className={`badge ${STATUS_BADGE[r.status]}`}>{r.status}</span></td>
                  <td><small>{r.initiated_by}</small></td>
                  <td><small>{r.created_at ? new Date(r.created_at).toLocaleDateString() : '—'}</small></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {pages > 1 && (
        <nav><ul className="pagination justify-content-center">
          {Array.from({ length: pages }, (_, i) => (
            <li key={i} className={`page-item ${page === i + 1 ? 'active' : ''}`}>
              <button className="page-link" onClick={() => setPage(i + 1)}>{i + 1}</button>
            </li>
          ))}
        </ul></nav>
      )}
    </>
  );
}
