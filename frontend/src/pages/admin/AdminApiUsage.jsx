import { useEffect, useMemo, useState } from 'react';
import { adminAPI } from '../../api';
import AdminHeader from '../../components/AdminHeader';

// What the platform spends on metered APIs, and how often those calls fail.
//
// The page exists because the expensive failures here have all been silent.
// ZeptoMail is prepaid: when the credits ran out in July 2026 every send failed
// while /api/health/email still reported auth_ok, and nothing counted sends.
// A failure rate is therefore shown as prominently as the spend.

const WINDOWS = [7, 30, 90];
const CARD = { border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' };
const COLORS = { zeptomail: '#3f7ddb', twilio: '#d99a2b', anthropic: '#2aa873' };
const OP_LABELS = {
  'email.send': 'Email (one-to-one)',
  'email.batch': 'Email (batch)',
  'sms.send': 'SMS',
  moderation: 'Wall moderation',
};

const usd = (n) => {
  const v = Number(n || 0);
  if (v === 0) return '$0.00';
  if (v < 0.01) return `$${v.toFixed(4)}`;
  return `$${v.toFixed(2)}`;
};
const pct = (n) => `${(Number(n || 0) * 100).toFixed(1)}%`;
const num = (n) => Number(n || 0).toLocaleString();
const opLabel = (op) => OP_LABELS[op]
  || (op.startsWith('agent.') ? `BDR agent — ${op.slice(6).replace(/_/g, ' ')}` : op);
const unitLabel = (provider) => (
  { zeptomail: 'recipients', twilio: 'segments', anthropic: 'calls' }[provider] || 'units');

function DailyChart({ daily, days }) {
  // Stacked daily cost by provider. Plain divs: no chart library for one chart.
  const series = useMemo(() => {
    const byDay = {};
    daily.forEach((d) => {
      byDay[d.day] = byDay[d.day] || {};
      byDay[d.day][d.provider] = (byDay[d.day][d.provider] || 0) + d.cost_usd;
    });
    const out = [];
    const end = new Date();
    for (let i = days - 1; i >= 0; i -= 1) {
      const dt = new Date(end);
      dt.setUTCDate(end.getUTCDate() - i);
      const key = dt.toISOString().slice(0, 10);
      out.push({ day: key, parts: byDay[key] || {} });
    }
    return out;
  }, [daily, days]);
  const max = Math.max(0.0001, ...series.map((s) => Object.values(s.parts).reduce((a, b) => a + b, 0)));

  return (
    <div>
      <div className="d-flex align-items-end gap-1" style={{ height: 140 }}
           role="img" aria-label={`Daily API spend over the last ${days} days`}>
        {series.map((s) => {
          const total = Object.values(s.parts).reduce((a, b) => a + b, 0);
          return (
            <div key={s.day} title={`${s.day}: ${usd(total)}`}
                 className="d-flex flex-column-reverse flex-grow-1"
                 style={{ height: '100%', minWidth: 2 }}>
              {Object.entries(s.parts).map(([p, v]) => (
                <div key={p} style={{
                  height: `${(v / max) * 100}%`, background: COLORS[p] || '#9aa0a6',
                  borderRadius: 2, minHeight: v > 0 ? 2 : 0,
                }} />
              ))}
            </div>
          );
        })}
      </div>
      <div className="d-flex justify-content-between small text-muted mt-1">
        <span>{series[0]?.day}</span><span>{series[series.length - 1]?.day}</span>
      </div>
    </div>
  );
}

export default function AdminApiUsage() {
  const [days, setDays] = useState(30);
  const [data, setData] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    setData(null);
    setError('');
    adminAPI.apiUsage({ days })
      .then((r) => setData(r.data))
      .catch((e) => setError(e.response?.data?.error || 'Could not load API usage.'));
  }, [days]);

  const right = (
    <div className="btn-group btn-group-sm" role="group" aria-label="Time window">
      {WINDOWS.map((w) => (
        <button key={w} type="button"
                className={`btn ${days === w ? 'btn-dark' : 'btn-outline-secondary'}`}
                onClick={() => setDays(w)}>
          {w} days
        </button>
      ))}
    </div>
  );

  return (
    <div>
      <AdminHeader title="API Usage" icon="bi-cpu" right={right} />

      {error && <div className="alert alert-danger">{error}</div>}
      {!data && !error && (
        <div className="text-center py-5"><div className="spinner-border" /></div>
      )}

      {data && (
        <>
          {data.tracking_since && (
            <div className="alert alert-light small border">
              <i className="bi bi-info-circle me-1" />
              Email, SMS and moderation calls are counted from{' '}
              <strong>{new Date(data.tracking_since).toLocaleDateString()}</strong>, when tracking
              began. The BDR agent's history goes back further. Costs are estimates from list
              prices — ZeptoMail at {usd(data.rates.zeptomail_per_recipient * 10000)} per 10,000
              recipients, Twilio at {usd(data.rates.twilio_per_segment)} per segment including
              carrier fees.
            </div>
          )}
          {!data.tracking_since && (
            <div className="alert alert-light small border">
              <i className="bi bi-info-circle me-1" />
              No email, SMS or moderation calls recorded yet — counting starts with the first one.
            </div>
          )}

          <div className="row g-3 mb-4">
            <div className="col-6 col-lg-3">
              <div className="card h-100" style={CARD}><div className="card-body">
                <div className="text-muted small">Estimated spend ({days}d)</div>
                <div className="fs-3 fw-bold">{usd(data.total_cost_usd)}</div>
              </div></div>
            </div>
            <div className="col-6 col-lg-3">
              <div className="card h-100" style={CARD}><div className="card-body">
                <div className="text-muted small">Monthly run rate</div>
                <div className="fs-3 fw-bold">{usd(data.monthly_run_rate_usd)}</div>
                <div className="small text-muted">projected from this window</div>
              </div></div>
            </div>
            {data.providers.map((p) => (
              <div className="col-6 col-lg-3" key={p.provider}>
                <div className="card h-100" style={{ ...CARD, borderTop: `3px solid ${COLORS[p.provider] || '#9aa0a6'}` }}>
                  <div className="card-body">
                    <div className="text-muted small">{p.label}</div>
                    <div className="fs-4 fw-bold">{usd(p.cost_usd)}</div>
                    <div className="small">
                      {num(p.units)} {unitLabel(p.provider)} · {num(p.calls)} calls
                    </div>
                    {p.failed > 0 && (
                      <div className={`small fw-semibold ${p.failure_rate >= 0.05 ? 'text-danger' : 'text-warning'}`}>
                        <i className="bi bi-exclamation-triangle me-1" />
                        {num(p.failed)} failed ({pct(p.failure_rate)})
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="card mb-4" style={CARD}>
            <div className="card-body">
              <div className="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
                <h6 className="fw-bold mb-0"><i className="bi bi-bar-chart me-2" />Daily spend</h6>
                <div className="small">
                  {Object.entries(COLORS).map(([p, c]) => (
                    <span key={p} className="me-3">
                      <span style={{ display: 'inline-block', width: 9, height: 9, borderRadius: '50%', background: c, marginRight: 5 }} />
                      {p}
                    </span>
                  ))}
                </div>
              </div>
              <DailyChart daily={data.daily} days={days} />
              <div className="small text-muted mt-2">
                Daily bars cover email, SMS and moderation. The BDR agent appears in the totals above
                and the table below.
              </div>
            </div>
          </div>

          <div className="card mb-4" style={CARD}>
            <div className="card-body">
              <h6 className="fw-bold mb-3"><i className="bi bi-list-ul me-2" />By operation</h6>
              {data.operations.length === 0 ? (
                <p className="text-muted mb-0">No metered API calls in this window.</p>
              ) : (
                <div className="table-responsive">
                  <table className="table table-sm align-middle mb-0">
                    <thead>
                      <tr>
                        <th>Operation</th><th>Provider</th>
                        <th className="text-end">Calls</th><th className="text-end">Units</th>
                        <th className="text-end">Tokens in / out</th>
                        <th className="text-end">Failed</th><th className="text-end">Est. cost</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.operations.map((o) => (
                        <tr key={`${o.provider}-${o.operation}-${o.model || ''}`}>
                          <td>
                            {opLabel(o.operation)}
                            {o.model && <div className="small text-muted">{o.model}</div>}
                          </td>
                          <td>{o.provider}</td>
                          <td className="text-end">{num(o.calls)}</td>
                          <td className="text-end">{num(o.units)}</td>
                          <td className="text-end small">
                            {o.input_tokens || o.output_tokens
                              ? `${num(o.input_tokens)} / ${num(o.output_tokens)}` : '—'}
                          </td>
                          <td className={`text-end ${o.failed ? 'text-danger fw-semibold' : ''}`}>
                            {num(o.failed)}
                          </td>
                          <td className="text-end fw-semibold">{usd(o.cost_usd)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>

          <div className="card mb-4" style={CARD}>
            <div className="card-body">
              <h6 className="fw-bold mb-3"><i className="bi bi-exclamation-octagon me-2" />Recent failures</h6>
              {data.recent_failures.length === 0 ? (
                <p className="text-muted mb-0">None in this window.</p>
              ) : (
                <>
                  <ul className="list-unstyled mb-2 small">
                    {data.recent_failures.map((f, i) => (
                      <li key={i} className="py-1 border-bottom">
                        <span className="text-muted me-2">{f.at ? new Date(f.at).toLocaleString() : ''}</span>
                        <strong className="me-2">{f.provider}</strong>
                        {opLabel(f.operation)}
                        {f.error && <span className="ms-2 text-danger">{f.error}</span>}
                      </li>
                    ))}
                  </ul>
                  {data.recent_failures.some((f) => f.provider === 'zeptomail' && /402/.test(f.error || '')) && (
                    <div className="alert alert-danger small mb-0">
                      <strong>HTTP 402 from ZeptoMail means the prepaid credits are exhausted.</strong>{' '}
                      Every email fails until they are topped up — check the ZeptoMail console. Sends
                      attempted in the meantime were recorded as handled, so campaign recipients and
                      BDR follow-ups during the outage may need re-sending.
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
