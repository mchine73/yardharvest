import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { gardensAPI } from '../../api';
import { useAuth } from '../../AuthContext';
import Seo from '../../components/Seo';
import { useTranslation } from 'react-i18next';

// Keys, not text: this object is built at module load, where there is no t().
// They point at the same garden.* keys the detail page uses, so one garden
// cannot be an "Allotment" on this page and "Individual plots" on the next.
const MODEL_LABEL_KEYS = {
  allotment: 'garden.modelAllotment',
  communal: 'garden.modelCommunal',
  hybrid: 'garden.modelHybrid',
};

const MODEL_COLORS = {
  allotment: 'var(--brand-secondary)',
  communal: '#3f7ddb',
  hybrid: '#8b5cf6',
};

export default function GardenHome() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [gardens, setGardens] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [search, setSearch] = useState('');
  const [modelFilter, setModelFilter] = useState('');
  const [page, setPage] = useState(1);
  const [pagination, setPagination] = useState({});

  const fetchGardens = (p = 1) => {
    setLoading(true);
    setLoadError(false);
    const params = { page: p };
    if (search) params.search = search;
    if (modelFilter) params.operating_model = modelFilter;
    gardensAPI.browse(params).then(res => {
      setGardens(res.data.gardens);
      setPagination(res.data);
      setPage(res.data.page);
      setLoading(false);
    }).catch(() => { setLoadError(true); setLoading(false); });
  };

  useEffect(() => { fetchGardens(); }, []);

  const handleSearch = (e) => {
    e.preventDefault();
    fetchGardens(1);
  };

  return (
    <div>
      <Seo
        title={t('gardensList.title')}
        path="/gardens"
        description={t('gardensList.seoDescription')}
      />
      {/* Hero Section — earthy garden palette */}
      <div className="hero-garden text-center">
        <h1 style={{ fontSize: '2.5rem', fontWeight: 'bold', marginBottom: '12px' }}>
          <i className="bi bi-tree me-3"></i>{t('gardensList.title')}
        </h1>
        <p style={{ fontSize: '1.2rem', opacity: 0.9, maxWidth: '600px', margin: '0 auto 24px' }}>
          {t('gardensList.heroLead')}
        </p>
        <div style={{ display: 'flex', gap: '12px', justifyContent: 'center', flexWrap: 'wrap' }}>
          {user && (
            <Link to="/gardens/create" className="yh-btn-dark">
              <i className="bi bi-plus-circle"></i>{t('gardensList.createGarden')}
            </Link>
          )}
          <Link to="/gardens/my-gardens" className="yh-btn-ghost">
            <i className="bi bi-person-workspace"></i>{t('gardensList.myGardens')}
          </Link>
        </div>
      </div>

      {/* Search & Filter */}
      <div className="card mb-4" style={{ border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }}>
        <div className="card-body">
          <form onSubmit={handleSearch}>
            <div className="row g-3 align-items-end">
              <div className="col-md-6">
                <label className="form-label fw-semibold">{t('gardensList.searchLabel')}</label>
                <input
                  type="text"
                  className="form-control"
                  placeholder={t('gardensList.searchPlaceholder')}
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
              <div className="col-md-3">
                <label className="form-label fw-semibold">{t('garden.operatingModel')}</label>
                <select className="form-select" value={modelFilter} onChange={(e) => setModelFilter(e.target.value)}>
                  <option value="">{t('gardensList.allModels')}</option>
                  <option value="allotment">{t('garden.modelAllotment')}</option>
                  <option value="communal">{t('garden.modelCommunal')}</option>
                  <option value="hybrid">{t('garden.modelHybrid')}</option>
                </select>
              </div>
              <div className="col-md-3">
                <button type="submit" className="btn btn-garden w-100">
                  <i className="bi bi-search me-2"></i>{t('gardensList.searchButton')}
                </button>
              </div>
            </div>
          </form>
        </div>
      </div>

      {/* Gardens Grid */}
      {loading ? (
        <div className="text-center py-5"><div className="spinner-border" style={{ color: 'var(--brand-secondary)' }}></div></div>
      ) : loadError ? (
        <div className="text-center py-5">
          <i className="bi bi-wifi-off" style={{ fontSize: '3rem', color: 'var(--yh-muted)' }}></i>
          <p className="text-muted mt-3 fs-5">{t('gardensList.loadError')}</p>
          <button className="btn btn-garden mt-2" onClick={() => fetchGardens(page)}>
            <i className="bi bi-arrow-clockwise me-2"></i>{t('gardensList.tryAgain')}
          </button>
        </div>
      ) : gardens.length === 0 ? (
        <div className="text-center py-5">
          <i className="bi bi-tree" style={{ fontSize: '3rem', color: 'var(--brand-gold)' }}></i>
          <p className="text-muted mt-3 fs-5">{t('gardensList.empty')}</p>
          {user && (
            <Link to="/gardens/create" className="btn btn-garden mt-2">
              <i className="bi bi-plus-circle me-2"></i>{t('gardensList.createGardenShort')}
            </Link>
          )}
        </div>
      ) : (
        <>
          <div className="row g-4">
            {gardens.map(garden => (
              <div key={garden.id} className="col-md-6 col-lg-4">
                <Link to={`/gardens/${garden.public_id}`} style={{ textDecoration: 'none', color: 'inherit' }}>
                  <div className="card h-100" style={{
                    border: 'none',
                    boxShadow: '0 2px 12px rgba(0,0,0,0.08)',
                    borderRadius: '12px',
                    overflow: 'hidden',
                    transition: 'transform 0.2s, box-shadow 0.2s',
                    cursor: 'pointer',
                  }}
                  onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-4px)'; e.currentTarget.style.boxShadow = '0 8px 24px rgba(0,0,0,0.12)'; }}
                  onMouseLeave={e => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = '0 2px 12px rgba(0,0,0,0.08)'; }}
                  >
                    {/* Photo or placeholder */}
                    <div style={{
                      height: '160px',
                      background: garden.photo_url
                        ? `url(${garden.photo_url}) center/cover`
                        : '#dce8ce',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}>
                      {!garden.photo_url && (
                        <i className="bi bi-flower2" style={{ fontSize: '3rem', color: 'var(--brand-secondary)', opacity: 0.4 }}></i>
                      )}
                    </div>
                    <div className="card-body">
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                        <span style={{
                          backgroundColor: MODEL_COLORS[garden.operating_model] || '#6b7280',
                          color: 'white',
                          padding: '2px 10px',
                          borderRadius: '12px',
                          fontSize: '0.75rem',
                          fontWeight: 600,
                        }}>
                          {MODEL_LABEL_KEYS[garden.operating_model]
                            ? t(MODEL_LABEL_KEYS[garden.operating_model])
                            : garden.operating_model}
                        </span>
                      </div>
                      <h5 className="card-title fw-bold mb-1">{garden.name}</h5>
                      <p className="text-muted small mb-2">
                        <i className="bi bi-geo-alt me-1"></i>
                        {garden.address ? `${garden.address}, ` : ''}{garden.city}, {garden.state}
                      </p>
                      <p className="card-text text-muted small" style={{
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        display: '-webkit-box',
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical',
                      }}>
                        {garden.description}
                      </p>
                    </div>
                    <div className="card-footer bg-white border-top-0" style={{ padding: '12px 20px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                        <span>
                          <i className="bi bi-grid-3x3 me-1" style={{ color: 'var(--brand-secondary)' }}></i>
                          {t('garden.plotsCount', { count: garden.total_plots })}
                        </span>
                        <span style={{
                          color: garden.available_plots > 0 ? 'var(--brand-accent)' : '#e0564f',
                          fontWeight: 600,
                        }}>
                          {garden.available_plots > 0
                            ? t('garden.availableCount', { count: garden.available_plots })
                            : t('gardensList.fullJoinWaitlist')}
                        </span>
                      </div>
                    </div>
                  </div>
                </Link>
              </div>
            ))}
          </div>

          {/* Pagination */}
          {pagination.pages > 1 && (
            <nav className="mt-4">
              <ul className="pagination justify-content-center">
                <li className={`page-item ${!pagination.has_prev ? 'disabled' : ''}`}>
                  <button className="page-link" onClick={() => fetchGardens(page - 1)}>{t('gardensList.previous')}</button>
                </li>
                {Array.from({ length: pagination.pages }, (_, i) => (
                  <li key={i + 1} className={`page-item ${page === i + 1 ? 'active' : ''}`}>
                    <button className="page-link" onClick={() => fetchGardens(i + 1)}
                      style={page === i + 1 ? { backgroundColor: 'var(--brand-secondary)', borderColor: 'var(--brand-secondary)' } : {}}>
                      {i + 1}
                    </button>
                  </li>
                ))}
                <li className={`page-item ${!pagination.has_next ? 'disabled' : ''}`}>
                  <button className="page-link" onClick={() => fetchGardens(page + 1)}>{t('gardensList.next')}</button>
                </li>
              </ul>
            </nav>
          )}
        </>
      )}

      {/* How It Works */}
      <div className="row mt-5 text-center">
        <h3 className="mb-4 fw-bold section-header-garden">{t('gardensList.howItWorks')}</h3>
        <div className="col-md-3">
          <div className="p-3">
            <i className="bi bi-search fs-1" style={{ color: 'var(--brand-secondary)' }}></i>
            <h5 className="mt-2">{t('gardensList.stepFind')}</h5>
            <p className="text-muted">{t('gardensList.stepFindBody')}</p>
          </div>
        </div>
        <div className="col-md-3">
          <div className="p-3">
            <i className="bi bi-grid-3x3-gap fs-1" style={{ color: 'var(--brand-secondary)' }}></i>
            <h5 className="mt-2">{t('gardensList.stepClaim')}</h5>
            <p className="text-muted">{t('gardensList.stepClaimBody')}</p>
          </div>
        </div>
        <div className="col-md-3">
          <div className="p-3">
            <i className="bi bi-people fs-1" style={{ color: 'var(--brand-gold)' }}></i>
            <h5 className="mt-2">{t('gardensList.stepGrow')}</h5>
            <p className="text-muted">{t('gardensList.stepGrowBody')}</p>
          </div>
        </div>
        <div className="col-md-3">
          <div className="p-3">
            <i className="bi bi-bar-chart fs-1" style={{ color: 'var(--brand-primary)' }}></i>
            <h5 className="mt-2">{t('gardensList.stepImpact')}</h5>
            <p className="text-muted">{t('gardensList.stepImpactBody')}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
