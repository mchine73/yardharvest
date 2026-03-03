import { useNavigate } from 'react-router-dom';

export default function AdminHeader({ title, icon, backTo }) {
  const navigate = useNavigate();
  return (
    <div className="d-flex align-items-center mb-4">
      <button
        className="btn btn-outline-secondary me-3 d-flex align-items-center justify-content-center"
        onClick={() => backTo ? navigate(backTo) : navigate(-1)}
        title="Go back"
        style={{ width: '38px', height: '38px', borderRadius: '50%', padding: 0 }}
      >
        <i className="bi bi-arrow-left"></i>
      </button>
      <h2 className="mb-0 fw-bold">
        {icon && <i className={`bi ${icon} me-2`}></i>}
        {title}
      </h2>
    </div>
  );
}
