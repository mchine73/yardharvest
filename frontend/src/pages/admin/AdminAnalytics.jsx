import { useState, useEffect } from 'react';
import { adminAPI } from '../../api';
import AdminHeader from '../../components/AdminHeader';

const PERIODS = [
  { key: 'day', label: 'Today' },
  { key: 'week', label: 'This Week' },
  { key: 'month', label: 'This Month' },
  { key: 'quarter', label: 'Quarter' },
  { key: 'year', label: 'Year' },
  { key: 'all', label: 'All Time' },
];

const CARD = { border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' };
const dot = (color) => ({
  display: 'inline-block', width: 9, height: 9, borderRadius: '50%',
  background: color, marginRight: 5,
});

// Resolve brand CSS variables to concrete hex once — SVG presentation
// attributes (stroke/fill) don't accept var(...), and the redesign repoints
// some brand vars, so reading the computed value is the reliable path.
function useBrandColors() {
  const [c, setC] = useState({ pv: '#2aa873', sess: '#d99a2b', grid: '#eef0f2' });
  useEffect(() => {
    const cs = getComputedStyle(document.documentElement);
    const get = (n, fb) => cs.getPropertyValue(n).trim() || fb;
    setC({ pv: get('--brand-accent', '#2aa873'), sess: get('--brand-gold', '#d99a2b'), grid: '#eef0f2' });
  }, []);
  return c;
}

function fmtTick(t, granularity) {
  if (granularity === 'hour') return t.slice(11, 16);       // HH:00
  const parts = t.split('-');                                // YYYY-MM-DD
  return parts.length === 3 ? `${parts[1]}/${parts[2]}` : t;
}

function TrendChart({ series, granularity }) {
  const colors = useBrandColors();
  const [hi, setHi] = useState(null);

  if (!series || series.length === 0) {
    return (
      <div className="card mb-4" style={CARD}>
        <div className="card-body">
          <h6 className="fw-bold mb-0"><i className="bi bi-graph-up-arrow me-2"></i>Traffic over time</h6>
          <p className="text-muted text-center py-4 mb-0">No activity in this period yet</p>
        </div>
      </div>
    );
  }

  const W = 760, H = 240, padL = 36, padR = 12, padT = 14, padB = 26;
  const innerW = W - padL - padR, innerH = H - padT - padB;
  const n = series.length;
  const maxV = Math.max(1, ...series.flatMap(d => [d.page_views, d.sessions]));
  const xAt = i => padL + (n <= 1 ? innerW / 2 : (i / (n - 1)) * innerW);
  const yAt = v => padT + innerH - (v / maxV) * innerH;
  const line = key => series.map((d, i) => `${i ? 'L' : 'M'}${xAt(i).toFixed(1)},${yAt(d[key]).toFixed(1)}`).join(' ');
  const area = `${line('page_views')} L${xAt(n - 1).toFixed(1)},${(padT + innerH).toFixed(1)} L${xAt(0).toFixed(1)},${(padT + innerH).toFixed(1)} Z`;

  const tickN = Math.min(6, n);
  const ticks = Array.from({ length: tickN }, (_, k) => Math.round(k * (n - 1) / Math.max(tickN - 1, 1)));
  const totalPV = series.reduce((a, d) => a + d.page_views, 0);
  const totalS = series.reduce((a, d) => a + d.sessions, 0);

  const onMove = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const px = (e.clientX - rect.left) / rect.width * W;
    let idx = Math.round((px - padL) / (innerW || 1) * (n - 1));
    setHi(Math.max(0, Math.min(n - 1, idx)));
  };

  return (
    <div className="card mb-4" style={CARD}>
      <div className="card-body">
        <div className="d-flex justify-content-between align-items-center flex-wrap mb-2">
          <h6 className="fw-bold mb-0"><i className="bi bi-graph-up-arrow me-2"></i>Traffic over time</h6>
          <div className="small">
            <span className="me-3"><span style={dot(colors.pv)}></span>Page views <strong>{totalPV}</strong></span>
            <span><span style={dot(colors.sess)}></span>Sessions <strong>{totalS}</strong></span>
          </div>
        </div>
        <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 'auto' }}
          onMouseMove={onMove} onMouseLeave={() => setHi(null)}>
          <defs>
            <linearGradient id="yh-pvgrad" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor={colors.pv} stopOpacity="0.25" />
              <stop offset="100%" stopColor={colors.pv} stopOpacity="0" />
            </linearGradient>
          </defs>
          {[0, 0.5, 1].map((f, i) => {
            const yy = padT + innerH - f * innerH;
            return (
              <g key={i}>
                <line x1={padL} x2={W - padR} y1={yy} y2={yy} stroke={colors.grid} />
                <text x={padL - 6} y={yy + 3} textAnchor="end" fontSize="10" fill="#9aa0a6">{Math.round(maxV * f)}</text>
              </g>
            );
          })}
          <path d={area} fill="url(#yh-pvgrad)" />
          <path d={line('page_views')} fill="none" stroke={colors.pv} strokeWidth="2" />
          <path d={line('sessions')} fill="none" stroke={colors.sess} strokeWidth="1.5" strokeDasharray="4 3" />
          {ticks.map(i => (
            <text key={i} x={xAt(i)} y={H - 8} textAnchor="middle" fontSize="10" fill="#9aa0a6">
              {fmtTick(series[i].t, granularity)}
            </text>
          ))}
          {hi != null && (
            <g>
              <line x1={xAt(hi)} x2={xAt(hi)} y1={padT} y2={padT + innerH} stroke="#c9ccd1" strokeDasharray="3 3" />
              <circle cx={xAt(hi)} cy={yAt(series[hi].page_views)} r="3.5" fill={colors.pv} />
              <circle cx={xAt(hi)} cy={yAt(series[hi].sessions)} r="3" fill={colors.sess} />
            </g>
          )}
        </svg>
        <div className="small text-muted text-center" style={{ minHeight: '1.2em' }}>
          {hi != null && (
            <span><strong>{series[hi].t}</strong> — {series[hi].page_views} views, {series[hi].sessions} sessions</span>
          )}
        </div>
      </div>
    </div>
  );
}

function Delta({ current, previous }) {
  if (previous == null || typeof current !== 'number') return null;
  if (previous === 0) {
    return current > 0
      ? <span className="badge ms-2 text-bg-success" style={{ fontSize: '0.62rem' }}>NEW</span>
      : null;
  }
  const pct = Math.round((current - previous) / previous * 100);
  if (pct === 0) return <span className="text-muted ms-2" style={{ fontSize: '0.72rem' }}>0%</span>;
  const up = pct > 0;
  // Cap the display: tiny prior periods make raw % explode (e.g. 1 → 262 = 26100%).
  const label = Math.abs(pct) > 999 ? '>999%' : `${Math.abs(pct)}%`;
  return (
    <span className={`ms-2 ${up ? 'text-success' : 'text-danger'}`} style={{ fontSize: '0.72rem', fontWeight: 600 }}>
      <i className={`bi ${up ? 'bi-arrow-up-short' : 'bi-arrow-down-short'}`}></i>{label}
    </span>
  );
}

function SplitBar({ a, b, aLabel, bLabel, aColor, bColor }) {
  const total = a + b || 1;
  return (
    <div className="mb-3">
      <div className="d-flex justify-content-between small mb-1">
        <span><span style={dot(aColor)}></span>{aLabel} <strong>{a}</strong></span>
        <span>{bLabel} <strong>{b}</strong> <span style={dot(bColor)}></span></span>
      </div>
      <div style={{ display: 'flex', height: 14, borderRadius: 7, overflow: 'hidden', background: '#eef0f2' }}>
        <div style={{ width: `${a / total * 100}%`, background: aColor }}></div>
        <div style={{ width: `${b / total * 100}%`, background: bColor }}></div>
      </div>
    </div>
  );
}

function FunnelBar({ steps, title, icon, color }) {
  const max = Math.max(...steps.map(s => s.value), 1);
  const first = steps[0]?.value || 0;
  const last = steps[steps.length - 1]?.value || 0;
  const overall = first > 0 ? Math.round(last / first * 100) : 0;
  return (
    <div className="card mb-3" style={CARD}>
      <div className="card-body">
        <div className="d-flex justify-content-between align-items-center mb-3">
          <h6 className="fw-bold mb-0" style={{ color: 'var(--brand-primary)' }}>
            <i className={`bi ${icon} me-2`}></i>{title}
          </h6>
          {first > 0 && (
            <span className="badge text-bg-light border" title="End-to-end conversion">
              {overall}% overall
            </span>
          )}
        </div>
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
                    <span className="text-muted ms-2" style={{ fontSize: '0.75rem' }}>({convRate}% from prev)</span>
                  )}
                </span>
              </div>
              <div style={{ height: 20, backgroundColor: '#e5e7eb', borderRadius: 4, overflow: 'hidden' }}>
                <div style={{
                  width: `${pct}%`, height: '100%', backgroundColor: color,
                  borderRadius: 4, transition: 'width 0.5s ease', minWidth: step.value > 0 ? 4 : 0,
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
  const colors = useBrandColors();
  const [period, setPeriod] = useState('month');
  const [overview, setOverview] = useState(null);
  const [series, setSeries] = useState(null);
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
      adminAPI.analyticsTimeseries({ period }),
      adminAPI.analyticsFunnel({ period }),
      adminAPI.analyticsSearch({ period }),
    ]).then(([o, t, f, s]) => {
      setOverview(o.data);
      setSeries(t.data);
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
      <AdminHeader title="Analytics" icon="bi-bar-chart-line"
                   right={
                     <>
                       <div className="btn-group">
                         {PERIODS.map(p => (
                           <button key={p.key} className={`btn btn-sm ${period === p.key ? 'btn-success' : 'btn-outline-success'}`}
                             onClick={() => setPeriod(p.key)}>{p.label}</button>
                         ))}
                       </div>
                       <a className="btn btn-sm btn-outline-secondary" href={`/api/admin/analytics/export.csv?period=${period}`}
                         title="Download raw events for this period">
                         <i className="bi bi-download me-1"></i>Export CSV
                       </a>
                     </>
                   } />

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
                  { label: 'Page Views', value: overview.kpis.page_views, prev: overview.previous?.page_views, icon: 'bi-eye', color: 'primary' },
                  { label: 'Unique Sessions', value: overview.kpis.unique_sessions, prev: overview.previous?.unique_sessions, icon: 'bi-window', color: 'info' },
                  { label: 'Unique Users', value: overview.kpis.unique_users, prev: overview.previous?.unique_users, icon: 'bi-people', color: 'success' },
                  { label: 'Bounce Rate', value: `${overview.kpis.bounce_rate}%`, icon: 'bi-arrow-return-left', color: 'warning' },
                ].map(s => (
                  <div key={s.label} className="col-6 col-md-3">
                    <div className="card text-center h-100" style={CARD}>
                      <div className="card-body py-3">
                        <i className={`bi ${s.icon} fs-3 text-${s.color}`}></i>
                        <h3 className="mb-0 d-flex align-items-center justify-content-center">
                          {s.value}
                          {s.prev != null && <Delta current={s.value} previous={s.prev} />}
                        </h3>
                        <small className="text-muted">{s.label}</small>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {series && <TrendChart series={series.series} granularity={series.granularity} />}

              <div className="row g-4">
                <div className="col-md-7">
                  <div className="card" style={CARD}>
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
                  <div className="card mb-3" style={CARD}>
                    <div className="card-body">
                      <h6 className="fw-bold mb-3"><i className="bi bi-diagram-3 me-2"></i>Acquisition Channels</h6>
                      {(!overview.channels || overview.channels.length === 0) ? (
                        <p className="text-muted text-center py-3">No referrer data yet</p>
                      ) : (() => {
                        const cmax = Math.max(...overview.channels.map(c => c.visits), 1);
                        return overview.channels.map((c, i) => (
                          <div key={i} className="mb-2">
                            <div className="d-flex justify-content-between mb-1" style={{ fontSize: '0.85rem' }}>
                              <span className="text-truncate" style={{ maxWidth: 200 }}>{c.channel}</span>
                              <strong>{c.visits}</strong>
                            </div>
                            <div style={{ height: 8, backgroundColor: '#e5e7eb', borderRadius: 4 }}>
                              <div style={{ width: `${c.visits / cmax * 100}%`, height: '100%', backgroundColor: colors.pv, borderRadius: 4 }}></div>
                            </div>
                          </div>
                        ));
                      })()}
                    </div>
                  </div>

                  <div className="card" style={CARD}>
                    <div className="card-body">
                      <h6 className="fw-bold mb-3"><i className="bi bi-phone me-2"></i>Devices</h6>
                      {Object.keys(overview.devices).length === 0 ? (
                        <p className="text-muted text-center py-3">No device data yet</p>
                      ) : (() => {
                        const total = Object.values(overview.devices).reduce((a, b) => a + b, 0);
                        const dc = { desktop: 'var(--brand-secondary)', mobile: 'var(--brand-accent)', tablet: 'var(--brand-light-green)' };
                        return Object.entries(overview.devices).map(([device, count]) => (
                          <div key={device} className="mb-2">
                            <div className="d-flex justify-content-between mb-1" style={{ fontSize: '0.85rem' }}>
                              <span style={{ textTransform: 'capitalize' }}><i className={`bi bi-${device === 'mobile' ? 'phone' : device === 'tablet' ? 'tablet' : 'display'} me-1`}></i>{device}</span>
                              <span><strong>{count}</strong> ({total > 0 ? Math.round(count / total * 100) : 0}%)</span>
                            </div>
                            <div style={{ height: 8, backgroundColor: '#e5e7eb', borderRadius: 4 }}>
                              <div style={{ width: `${total > 0 ? count / total * 100 : 0}%`, height: '100%', backgroundColor: dc[device] || '#6b7280', borderRadius: 4 }}></div>
                            </div>
                          </div>
                        ));
                      })()}
                    </div>
                  </div>
                </div>
              </div>

              <div className="row g-4 mt-1">
                <div className="col-md-6">
                  <div className="card" style={CARD}>
                    <div className="card-body">
                      <h6 className="fw-bold mb-3"><i className="bi bi-people me-2"></i>Visitors</h6>
                      {overview.segments ? (
                        <>
                          <SplitBar
                            a={overview.segments.new_sessions} b={overview.segments.returning_sessions}
                            aLabel="New" bLabel="Returning" aColor={colors.pv} bColor={colors.sess}
                          />
                          <SplitBar
                            a={overview.segments.logged_in_sessions} b={overview.segments.anon_sessions}
                            aLabel="Logged in" bLabel="Anonymous" aColor="var(--brand-primary)" bColor="#c9ccd1"
                          />
                        </>
                      ) : <p className="text-muted text-center py-3">No visitor data yet</p>}
                    </div>
                  </div>
                </div>
                <div className="col-md-6">
                  <div className="card" style={CARD}>
                    <div className="card-body">
                      <h6 className="fw-bold mb-3"><i className="bi bi-link-45deg me-2"></i>Top Referrers</h6>
                      {overview.top_referrers.length === 0 ? (
                        <p className="text-muted text-center py-3">No referrer data yet</p>
                      ) : overview.top_referrers.map((r, i) => (
                        <div key={i} className="d-flex justify-content-between mb-2">
                          <span className="small text-truncate" style={{ maxWidth: 240 }}>{r.referrer}</span>
                          <strong>{r.visits}</strong>
                        </div>
                      ))}
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
                  color="var(--brand-secondary)"
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
                  color="var(--brand-accent)"
                  steps={[
                    { label: 'Viewed Garden', value: funnel.garden.garden_view },
                    { label: 'Reserved Plot', value: funnel.garden.plot_reserve },
                    { label: 'Plot Confirmed', value: funnel.garden.plot_confirmed },
                  ]}
                />
                <FunnelBar
                  title="Registration"
                  icon="bi-person-plus"
                  color="var(--brand-gold)"
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
                <div className="card" style={CARD}>
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
                <div className="card" style={CARD}>
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
                <select className="form-select form-select-sm" style={{ maxWidth: 200 }} value={eventFilter}
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
