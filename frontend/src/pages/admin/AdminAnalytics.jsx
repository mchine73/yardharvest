import { useState, useEffect } from 'react';
import { adminAPI } from '../../api';

const PERIODS = [
  { key: 'day', label: 'Today' },
  { key: 'week', label: 'This Week' },
  { key: 'month', label: 'This Month' },
  { key: 'quarter', label: 'Quarter' },
  { key: 'year', label: 'Year' },
  { key: 'all', label: 'All Time' },
];

function FunnelBar({ steps, title, icon, color }) {
  const max = Math.max(...steps.map(s => s.value), 1);
  return (
    <div className="card mb-3" style={{ border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
      <div className="card-body">
        <h6 className="fw-bold mb-3" style={{ color: '#1B4D3E' }}>
          <i className={`bi ${icon} me-2`}></i>{title}
        </h6>
        {steps.map((step, i) => {
          const pct = max > 0 ? (step.value / max * 100) : 0;
          const convRate = i > 0 && steps[i - 1].value > 0
            ? Math.round(step.value / steps[i - 1].value * 100) : null;
          return (
            <div key={step.label} className="mb-2">
              <div className="d-flex justify-content-between mb-1" style={{ fontSize: '0.85rem' }}>
                <span>{step.label}</span>
                <span>
                  <strong>{step.value}</strong>
                  {convRate !== null && (
                    <span className="text-muted ms-2" style={{ fontSize: '0.75rem' }}>
                      ({convRate}% from prev)
                    </span>
                  )}
                </span>
              </div>
              <div style={{ height: '20px', backgroundColor: '#e5e7eb', borderRadius: '4px', overflow: 'hidden' }}>
                <div style={{
                  width: `${pct}%`, height: '100%', backgroundColor: color,
                  borderRadius: '4px', transition: 'width 0.5s ease', minWidth: step.value > 0 ? '4px' : 0,
                }}></div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function AdminAnalytics() {
  const [period, setPeriod] = useState('month');
  const [overview, setOverview] = useState(null);
  const [funnel, setFunnel] = useState(null);
  const [search, setSearch] = useState(null);
  const [events, setEvents] = useState(null);
  const [eventsPage, setEventsPage] = useState(1);
  const [eventFilter, setEventFilter] = useState('');
  const [tab, setTab] = useState('overview');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      adminAPI.analyticsOverview({ period }),
      adminAPI.analyticsFunnel({ period }),
      adminAPI.analyticsSearch({ period }),
    ]).then(([o, f, s]) => {
      setOverview(o.data);
      setFunnel(f.data);
      setSearch(s.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [period]);

  useEffect(() => {
    if (tab === 'events') {
      adminAPI.analyticsEvents({ page: eventsPage, event_type: eventFilter })
        .then(r => setEvents(r.data)).catch(() => {});
    }
  }, [tab, eventsPage, eventFilter]);

  return (
    <>
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h1><i className="bi bi-bar-chart-line me-2"></i>Analytics</h1>
        <div className="btn-group">
          {PERIODS.map(p => (
            <button key={p.key} className={`btn btn-sm ${period === p.key ? 'btn-success' : 'btn-outline-success'}`}
              onClick={() => setPeriod(p.key)}>{p.label}</button>
          ))}
        </div>
      </div>

      <ul className="nav nav-tabs mb-4">
        {['overview', 'funnels', 'search', 'events'].map(t => (
          <li key={t} className="nav-item">
            <button className={`nav-link ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)}>
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </button>
          </li>
        ))}
      </ul>

      {loading && tab !== 'events' ? (
        <div className="text-center py-5"><div className="spinner-border text-success"></div></div>
      ) : (
        <>
          {/* OVERVIEW TAB */}
          {tab === 'overview' && overview && (
            <>
              <div className="row g-3 mb-4">
                {[
                  { label: 'Page Views', value: overview.kpis.page_views, icon: 'bi-eye', color: 'primary' },
                  { label: 'Unique Sessions', value: overview.kpis.unique_sessions, icon: 'bi-window', color: 'info' },
                  { label: 'Unique Users', value: overview.kpis.unique_users, icon: 'bi-people', color: 'success' },
                  { label: 'Bounce Rate', value: `${overview.kpis.bounce_rate}%`, icon: 'bi-arrow-return-left', color: 'warning' },
                ].map(s => (
                  <div key={s.label} className="col-6 col-md-3">
                    <div className="card text-center h-100" style={{ border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
                      <div className="card-body py-3">
                        <i className={`bi ${s.icon} fs-3 text-${s.color}`}></i>
                        <h3 className="mb-0">{s.value}</h3>
                        <small className="text-muted">{s.label}</small>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              <div className="row g-4">
                <div className="col-md-7">
                  <div className="card" style={{ border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
                    <div className="card-body">
                      <h6 className="fw-bold mb-3"><i className="bi bi-file-earmark me-2"></i>Top Pages</h6>
                      {overview.top_pages.length === 0 ? (
                        <p className="text-muted text-center py-3">No page view data yet</p>
                      ) : (
                        <table className="table table-sm">
                          <thead><tr><th>Page</th><th>Views</th><th>Visitors</th></tr></thead>
                          <tbody>
                            {overview.top_pages.map((p, i) => (
                              <tr key={i}>
                                <td><code style={{ fontSize: '0.8rem' }}>{p.url}</code></td>
                                <td><strong>{p.views}</strong></td>
                                <td>{p.unique_visitors}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      )}
                    </div>
                  </div>
                </div>

                <div className="col-md-5">
                  <div className="card mb-3" style={{ border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
                    <div className="card-body">
                      <h6 className="fw-bold mb-3"><i className="bi bi-link-45deg me-2"></i>Top Referrers</h6>
                      {overview.top_referrers.length === 0 ? (
                        <p className="text-muted text-center py-3">No referrer data yet</p>
                      ) : overview.top_referrers.map((r, i) => (
                        <div key={i} className="d-flex justify-content-between mb-2">
                          <span className="small text-truncate" style={{ maxWidth: '200px' }}>{r.referrer}</span>
                          <strong>{r.visits}</strong>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="card" style={{ border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
                    <div className="card-body">
                      <h6 className="fw-bold mb-3"><i className="bi bi-phone me-2"></i>Devices</h6>
                      {Object.keys(overview.devices).length === 0 ? (
                        <p className="text-muted text-center py-3">No device data yet</p>
                      ) : (() => {
                        const total = Object.values(overview.devices).reduce((a, b) => a + b, 0);
                        const colors = { desktop: '#2D6A4F', mobile: '#40916C', tablet: '#74C69D' };
                        return Object.entries(overview.devices).map(([device, count]) => (
                          <div key={device} className="mb-2">
                            <div className="d-flex justify-content-between mb-1" style={{ fontSize: '0.85rem' }}>
                              <span style={{ textTransform: 'capitalize' }}><i className={`bi bi-${device === 'mobile' ? 'phone' : device === 'tablet' ? 'tablet' : 'display'} me-1`}></i>{device}</span>
                              <span><strong>{count}</strong> ({total > 0 ? Math.round(count / total * 100) : 0}%)</span>
                            </div>
                            <div style={{ height: '8px', backgroundColor: '#e5e7eb', borderRadius: '4px' }}>
                              <div style={{ width: `${total > 0 ? count / total * 100 : 0}%`, height: '100%', backgroundColor: colors[device] || '#6b7280', borderRadius: '4px' }}></div>
                            </div>
                          </div>
                        ));
                      })()}
                    </div>
                  </div>
                </div>
              </div>
            </>
          )}

          {/* FUNNELS TAB */}
          {tab === 'funnels' && funnel && (
            <div className="row g-4">
              <div className="col-md-6">
                <FunnelBar
                  title="Marketplace Conversion"
                  icon="bi-cart3"
                  color="#2D6A4F"
                  steps={[
                    { label: 'Viewed Listing', value: funnel.marketplace.listing_view },
                    { label: 'Added to Cart', value: funnel.marketplace.add_to_cart },
                    { label: 'Started Checkout', value: funnel.marketplace.checkout_start },
                    { label: 'Completed Purchase', value: funnel.marketplace.checkout_complete },
                  ]}
                />
              </div>
              <div className="col-md-6">
                <FunnelBar
                  title="Garden Conversion"
                  icon="bi-tree"
                  color="#40916C"
                  steps={[
                    { label: 'Viewed Garden', value: funnel.garden.garden_view },
                    { label: 'Reserved Plot', value: funnel.garden.plot_reserve },
                    { label: 'Plot Confirmed', value: funnel.garden.plot_confirmed },
                  ]}
                />
                <FunnelBar
                  title="Registration"
                  icon="bi-person-plus"
                  color="#D4A843"
                  steps={[
                    { label: 'Started Registration', value: funnel.registration.register_start },
                    { label: 'Completed Registration', value: funnel.registration.register_complete },
                  ]}
                />
              </div>
            </div>
          )}

          {/* SEARCH TAB */}
          {tab === 'search' && search && (
            <div className="row g-4">
              <div className="col-md-6">
                <div className="card" style={{ border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
                  <div className="card-body">
                    <h6 className="fw-bold mb-3"><i className="bi bi-search me-2"></i>Top Search Queries</h6>
                    <p className="text-muted small mb-3">{search.total_searches} total searches this period</p>
                    {search.top_queries.length === 0 ? (
                      <p className="text-muted text-center py-3">No search data yet</p>
                    ) : (
                      <table className="table table-sm">
                        <thead><tr><th>Query</th><th>Count</th></tr></thead>
                        <tbody>
                          {search.top_queries.map((q, i) => (
                            <tr key={i}><td>{q.query}</td><td><strong>{q.count}</strong></td></tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
                </div>
              </div>
              <div className="col-md-6">
                <div className="card" style={{ border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
                  <div className="card-body">
                    <h6 className="fw-bold mb-3"><i className="bi bi-exclamation-triangle me-2 text-warning"></i>Zero-Result Searches</h6>
                    <p className="text-muted small mb-3">Users searched for these but found nothing — potential stock gaps</p>
                    {search.zero_result_queries.length === 0 ? (
                      <p className="text-muted text-center py-3">No zero-result searches — great coverage!</p>
                    ) : (
                      <table className="table table-sm">
                        <thead><tr><th>Query</th><th>Count</th></tr></thead>
                        <tbody>
                          {search.zero_result_queries.map((q, i) => (
                            <tr key={i}><td><span className="text-danger">{q.query}</span></td><td><strong>{q.count}</strong></td></tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* EVENTS TAB */}
          {tab === 'events' && (
            <div>
              <div className="d-flex gap-2 mb-3 align-items-center">
                <select className="form-select form-select-sm" style={{ maxWidth: '200px' }} value={eventFilter}
                  onChange={e => { setEventFilter(e.target.value); setEventsPage(1); }}>
                  <option value="">All Events</option>
                  {['page_view', 'listing_view', 'garden_view', 'search', 'add_to_cart', 'checkout_start',
                    'checkout_complete', 'register_start', 'register_complete', 'plot_reserve', 'login'].map(t => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
                {events && <span className="text-muted small">{events.total} events total</span>}
              </div>

              {!events ? (
                <div className="text-center py-4"><div className="spinner-border text-success spinner-border-sm"></div></div>
              ) : (
                <>
                  <div className="table-responsive">
                    <table className="table table-sm table-hover">
                      <thead className="table-light">
                        <tr>
                          <th>Time</th><th>Event</th><th>Page</th><th>Device</th><th>User</th><th>Session</th>
                        </tr>
                      </thead>
                      <tbody>
                        {events.events.map(ev => (
                          <tr key={ev.id}>
                            <td><small>{ev.created_at ? new Date(ev.created_at).toLocaleString() : '—'}</small></td>
                            <td><span className="badge bg-secondary">{ev.event_type}</span></td>
                            <td><code style={{ fontSize: '0.75rem' }}>{ev.page_url || '—'}</code></td>
                            <td><small>{ev.device_type || '—'}</small></td>
                            <td><small>{ev.user_id || 'anon'}</small></td>
                            <td><small className="text-muted">{ev.session_id}</small></td>
                          </tr>
                        ))}
                        {events.events.length === 0 && (
                          <tr><td colSpan="6" className="text-center text-muted py-4">No events recorded yet</td></tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                  {events.pages > 1 && (
                    <nav>
                      <ul className="pagination justify-content-center">
                        {Array.from({ length: Math.min(events.pages, 10) }, (_, i) => (
                          <li key={i} className={`page-item ${eventsPage === i + 1 ? 'active' : ''}`}>
                            <button className="page-link" onClick={() => setEventsPage(i + 1)}>{i + 1}</button>
                          </li>
                        ))}
                      </ul>
                    </nav>
                  )}
                </>
              )}
            </div>
          )}
        </>
      )}
    </>
  );
}
