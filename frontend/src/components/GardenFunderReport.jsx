import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { gardenAdminAPI } from '../api';

// Funder-facing impact report: date-ranged aggregates (harvest,
// participation, volunteering, events, finance) with valuation equivalents,
// printable to PDF via the browser and exportable as CSV. The numbers come
// from GET /garden-admin/:id/funder-report (Pro).

const fmtUSD = (v) => `$${Number(v || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const fmtN = (v) => Number(v || 0).toLocaleString();
const fmtLong = (iso) => new Date(`${iso}T12:00:00`).toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' });
const fmtLabel = (s) => String(s || '').replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase());
const iso = (d) => d.toISOString().slice(0, 10);

function presetRange(key, garden) {
  const now = new Date();
  const y = now.getFullYear();
  switch (key) {
    case 'last_year':
      return [`${y - 1}-01-01`, `${y - 1}-12-31`];
    case 'season': {
      if (garden?.season_start && garden?.season_end) {
        return [garden.season_start, garden.season_end];
      }
      return [`${y}-01-01`, iso(now)];
    }
    case 'twelve_months': {
      const back = new Date(now);
      back.setFullYear(back.getFullYear() - 1);
      return [iso(back), iso(now)];
    }
    case 'this_year':
    default:
      return [`${y}-01-01`, iso(now)];
  }
}

const TILE = { textAlign: 'center', padding: '14px 8px', backgroundColor: '#f7f8f8', borderRadius: 12, height: '100%' };
const TILE_VALUE = { fontSize: '1.5rem', fontWeight: 700, color: '#22242a' };
const TILE_LABEL = { fontSize: '.75rem', color: '#6b6e76' };
const SECTION_H = { fontWeight: 700, borderBottom: '2px solid #edf7cf', paddingBottom: 6, marginTop: 28, marginBottom: 12 };

export default function GardenFunderReport({ gardenId, garden }) {
  const [preset, setPreset] = useState('this_year');
  const [range, setRange] = useState(() => presetRange('this_year', garden));
  const [produceRate, setProduceRate] = useState('3.00');
  const [volunteerRate, setVolunteerRate] = useState('33.49');
  const [preparedFor, setPreparedFor] = useState('');
  const [notes, setNotes] = useState('');
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [needsPro, setNeedsPro] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    gardenAdminAPI.funderReport(gardenId, {
      start: range[0], end: range[1],
      produce_rate: produceRate, volunteer_rate: volunteerRate,
    }).then((res) => {
      setReport(res.data);
      setNeedsPro(false);
    }).catch((e) => {
      if (e.response?.status === 403 && e.response.data?.upgrade_url) {
        setNeedsPro(true);
      } else {
        setError('Could not load the report — please try again.');
      }
    }).finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gardenId, range[0], range[1], produceRate, volunteerRate]);

  useEffect(() => { load(); }, [load]);

  const pickPreset = (key) => {
    setPreset(key);
    if (key !== 'custom') setRange(presetRange(key, garden));
  };

  const printReport = () => {
    // Print isolation: the CSS in App.css hides everything except
    // .funder-report while this body class is present.
    document.body.classList.add('printing-funder-report');
    const cleanup = () => document.body.classList.remove('printing-funder-report');
    window.addEventListener('afterprint', cleanup, { once: true });
    window.print();
    setTimeout(cleanup, 2000);   // safety net if afterprint never fires
  };

  const downloadCsv = () => {
    if (!report) return;
    const r = report;
    const rows = [
      ['Section', 'Metric', 'Value'],
      ['Period', 'Start', r.period.start], ['Period', 'End', r.period.end],
      ['Harvest', 'Total produce (lbs)', r.harvest.total_lbs],
      ['Harvest', 'Food bank donations (lbs)', r.harvest.food_bank_lbs],
      ['Harvest', 'Shared with neighbors (lbs)', r.harvest.shared_lbs],
      ['Harvest', 'Gardeners who logged harvests', r.harvest.gardeners],
      ...r.harvest.by_category.map((c) => ['Harvest by crop', fmtLabel(c.category), c.lbs]),
      ['Participation', 'Members', r.participation.members_total],
      ['Participation', 'New members this period', r.participation.members_new],
      ['Participation', 'Plots', r.participation.plots_total],
      ['Participation', 'Plots assigned', r.participation.plots_assigned],
      ['Participation', 'Plot occupancy (%)', r.participation.occupancy_pct],
      ['Volunteering', 'Shifts held', r.volunteering.shifts_held],
      ['Volunteering', 'Volunteers', r.volunteering.volunteers],
      ['Volunteering', 'Hours logged', r.volunteering.hours],
      ['Volunteering', 'Value (USD)', r.volunteering.value_usd],
      ['Events', 'Events held', r.events.held],
      ['Events', 'RSVPs (going)', r.events.rsvps_going],
      ...Object.entries(r.events.by_type).map(([t, n]) => ['Events by type', t, n]),
      ['Finance', 'Dues collected (USD)', r.finance.dues_collected],
      ['Finance', 'Dues expected (USD)', r.finance.dues_expected],
      ['Finance', 'Expenses (USD)', r.finance.expenses_total],
      ...Object.entries(r.finance.expenses_by_category).map(([c, a]) => ['Expenses by category', c, a]),
      ['Finance', 'Net (USD)', r.finance.net],
      ['Impact', 'Meals shared (est.)', r.equivalents.meals],
      ['Impact', 'Produce value (USD, est.)', r.equivalents.produce_value_usd],
      ['Impact', 'CO2 avoided (lbs, est.)', r.equivalents.co2_saved_lbs],
      ['Methodology', 'Produce rate (USD/lb)', r.rates.produce_rate],
      ['Methodology', 'Volunteer rate (USD/hr)', r.rates.volunteer_rate],
      ['Methodology', 'Lbs per meal', r.rates.lbs_per_meal],
    ];
    const csv = rows.map((row) =>
      row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `${(garden?.name || 'garden').replace(/\W+/g, '-')}-impact-${report.period.start}-to-${report.period.end}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  if (needsPro) {
    return (
      <div className="text-center py-5">
        <i className="bi bi-file-earmark-bar-graph" style={{ fontSize: '3rem', color: '#ccc' }}></i>
        <h5 className="mt-3 fw-bold">Funder reports are a Garden Pro feature</h5>
        <p className="text-muted" style={{ maxWidth: 420, margin: '0 auto 16px' }}>
          Generate grant-ready impact reports — harvest, participation,
          volunteer hours and their dollar value — for any date range, ready
          to print or export.
        </p>
        <Link to={`/gardens/${gardenId}/billing`} className="btn" style={{ backgroundColor: 'var(--yh-lime)', color: '#22242a', fontWeight: 600 }}>
          Upgrade to Garden Pro
        </Link>
      </div>
    );
  }

  const r = report;

  return (
    <div>
      <h4 className="fw-bold mb-3"><i className="bi bi-file-earmark-bar-graph me-2"></i>Funder Reports</h4>

      {/* Controls (never printed) */}
      <div className="card mb-4 d-print-none" style={{ border: '1px solid var(--yh-border)' }}>
        <div className="card-body">
          <div className="d-flex flex-wrap gap-1 mb-3">
            {[['this_year', 'This year'], ['last_year', 'Last year'],
              ['season', 'Garden season'], ['twelve_months', 'Last 12 months'],
              ['custom', 'Custom']].map(([key, label]) => (
              <button key={key}
                      className={`btn btn-sm ${preset === key ? 'btn-dark' : 'btn-outline-secondary'} rounded-pill`}
                      onClick={() => pickPreset(key)}>{label}</button>
            ))}
          </div>
          <div className="row g-2 align-items-end">
            <div className="col-6 col-md-2">
              <label className="form-label small mb-1">From</label>
              <input type="date" className="form-control form-control-sm" value={range[0]}
                     onChange={(e) => { setPreset('custom'); setRange([e.target.value, range[1]]); }} />
            </div>
            <div className="col-6 col-md-2">
              <label className="form-label small mb-1">To</label>
              <input type="date" className="form-control form-control-sm" value={range[1]}
                     onChange={(e) => { setPreset('custom'); setRange([range[0], e.target.value]); }} />
            </div>
            <div className="col-6 col-md-2">
              <label className="form-label small mb-1" title="Used to value harvested produce">Produce $/lb</label>
              <input type="number" step="0.25" min="0" className="form-control form-control-sm"
                     value={produceRate} onChange={(e) => setProduceRate(e.target.value)} />
            </div>
            <div className="col-6 col-md-2">
              <label className="form-label small mb-1" title="Independent Sector 2024 national value: $33.49">Volunteer $/hr</label>
              <input type="number" step="0.5" min="0" className="form-control form-control-sm"
                     value={volunteerRate} onChange={(e) => setVolunteerRate(e.target.value)} />
            </div>
            <div className="col-12 col-md-4">
              <label className="form-label small mb-1">Prepared for (funder / grant name — optional)</label>
              <input className="form-control form-control-sm" value={preparedFor}
                     placeholder="e.g. City of Omaha Community Grants"
                     onChange={(e) => setPreparedFor(e.target.value)} />
            </div>
          </div>
          <div className="mt-2">
            <label className="form-label small mb-1">Narrative notes (printed under the headline numbers — optional)</label>
            <textarea className="form-control form-control-sm" rows={2} value={notes}
                      placeholder="One or two sentences of context for the reader…"
                      onChange={(e) => setNotes(e.target.value)} />
          </div>
          <div className="d-flex gap-2 mt-3">
            <button className="btn btn-sm" style={{ backgroundColor: '#22242a', color: '#fff' }}
                    onClick={printReport} disabled={!r}>
              <i className="bi bi-printer me-1"></i>Print / Save as PDF
            </button>
            <button className="btn btn-sm btn-outline-secondary" onClick={downloadCsv} disabled={!r}>
              <i className="bi bi-download me-1"></i>Download CSV
            </button>
          </div>
        </div>
      </div>

      {loading && <div className="text-center py-4"><div className="spinner-border text-success"></div></div>}
      {error && (
        <div className="alert alert-warning d-flex align-items-center justify-content-between d-print-none">
          <span>{error}</span>
          <button className="btn btn-sm btn-outline-secondary" onClick={load}>Try again</button>
        </div>
      )}

      {/* ---- The printable report ---- */}
      {r && !loading && (
        <div className="funder-report card" style={{ border: '1px solid var(--yh-border)' }}>
          <div className="card-body p-4">
            <div style={{ borderBottom: '3px solid #e3ff8f', paddingBottom: 12, marginBottom: 18 }}>
              <div className="d-flex justify-content-between flex-wrap align-items-baseline">
                <h3 className="fw-bold mb-0">{r.garden.name}</h3>
                <span className="text-muted">{[r.garden.city, r.garden.state].filter(Boolean).join(', ')}</span>
              </div>
              <div className="mt-1" style={{ fontSize: '1.05rem' }}>Impact &amp; Activity Report</div>
              <div className="text-muted" style={{ fontSize: '.9rem' }}>
                {fmtLong(r.period.start)} — {fmtLong(r.period.end)}
                {preparedFor && <> · Prepared for {preparedFor}</>}
                {' '}· Generated {new Date().toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' })}
              </div>
            </div>

            {/* Headline tiles */}
            <div className="row g-2">
              {[
                [`${fmtN(r.harvest.total_lbs)} lbs`, 'Produce harvested'],
                [fmtN(r.equivalents.meals), 'Meals shared (est.)'],
                [fmtN(r.volunteering.hours), 'Volunteer hours'],
                [fmtUSD(r.volunteering.value_usd), 'Volunteer value'],
                [fmtN(r.participation.members_total), 'Members'],
                [`+${fmtN(r.participation.members_new)}`, 'New members'],
                [fmtN(r.events.held), 'Events held'],
                [`${r.participation.occupancy_pct}%`, 'Plot occupancy'],
              ].map(([value, label]) => (
                <div key={label} className="col-6 col-md-3">
                  <div style={TILE}>
                    <div style={TILE_VALUE}>{value}</div>
                    <div style={TILE_LABEL}>{label}</div>
                  </div>
                </div>
              ))}
            </div>

            {notes.trim() && (
              <p className="mt-3 mb-0" style={{ fontSize: '.95rem' }}>{notes}</p>
            )}

            {/* Harvest */}
            <div style={SECTION_H}>Harvest &amp; Food Access</div>
            <div className="row">
              <div className="col-md-7">
                <table className="table table-sm mb-2">
                  <thead><tr><th>Crop</th><th className="text-end">Pounds</th></tr></thead>
                  <tbody>
                    {r.harvest.by_category.map((c) => (
                      <tr key={c.category}><td>{fmtLabel(c.category)}</td><td className="text-end">{fmtN(c.lbs)}</td></tr>
                    ))}
                    {r.harvest.by_category.length === 0 && (
                      <tr><td colSpan={2} className="text-muted">No harvests logged in this period.</td></tr>
                    )}
                  </tbody>
                  {r.harvest.by_category.length > 0 && (
                    <tfoot><tr className="fw-bold"><td>Total</td><td className="text-end">{fmtN(r.harvest.total_lbs)}</td></tr></tfoot>
                  )}
                </table>
              </div>
              <div className="col-md-5">
                <p style={{ fontSize: '.92rem' }} className="mb-1">
                  <strong>{fmtN(r.harvest.food_bank_lbs)} lbs</strong> donated to food banks
                  and <strong>{fmtN(r.harvest.shared_lbs)} lbs</strong> shared with neighbors —
                  roughly <strong>{fmtN(r.equivalents.meals)} meals</strong>.
                </p>
                <p style={{ fontSize: '.92rem' }} className="mb-1">
                  Estimated market value of all produce grown:{' '}
                  <strong>{fmtUSD(r.equivalents.produce_value_usd)}</strong>.
                </p>
                <p style={{ fontSize: '.92rem' }} className="mb-0">
                  {fmtN(r.harvest.gardeners)} gardener{r.harvest.gardeners === 1 ? '' : 's'} logged harvests;
                  an estimated <strong>{fmtN(r.equivalents.co2_saved_lbs)} lbs</strong> of CO₂ avoided
                  through locally shared food.
                </p>
              </div>
            </div>

            {/* Participation + Volunteering */}
            <div style={SECTION_H}>Community &amp; Volunteering</div>
            <div className="row" style={{ fontSize: '.92rem' }}>
              <div className="col-md-6">
                <ul className="mb-2">
                  <li><strong>{fmtN(r.participation.members_total)}</strong> members ({fmtN(r.participation.members_new)} joined during this period)</li>
                  <li><strong>{fmtN(r.participation.plots_assigned)}</strong> of {fmtN(r.participation.plots_total)} plots in active use ({r.participation.occupancy_pct}% occupancy)</li>
                  <li><strong>{fmtN(r.events.held)}</strong> community events held, with {fmtN(r.events.rsvps_going)} RSVPs
                    {Object.keys(r.events.by_type).length > 0 && (
                      <> ({Object.entries(r.events.by_type).map(([t, n]) => `${n} ${t.replace('_', ' ')}`).join(', ')})</>
                    )}
                  </li>
                </ul>
              </div>
              <div className="col-md-6">
                <ul className="mb-2">
                  <li><strong>{fmtN(r.volunteering.volunteers)}</strong> volunteers worked <strong>{fmtN(r.volunteering.hours)}</strong> logged hours across {fmtN(r.volunteering.shifts_held)} organized shifts</li>
                  <li>Volunteer labor value: <strong>{fmtUSD(r.volunteering.value_usd)}</strong> at ${r.rates.volunteer_rate}/hour</li>
                </ul>
              </div>
            </div>

            {/* Finance */}
            <div style={SECTION_H}>Financial Summary</div>
            <div className="row" style={{ fontSize: '.92rem' }}>
              <div className="col-md-6">
                <table className="table table-sm mb-0">
                  <tbody>
                    <tr><td>Member dues collected</td><td className="text-end">{fmtUSD(r.finance.dues_collected)}</td></tr>
                    <tr><td className="text-muted">of dues billed</td><td className="text-end text-muted">{fmtUSD(r.finance.dues_expected)}</td></tr>
                    <tr><td>Expenses</td><td className="text-end">({fmtUSD(r.finance.expenses_total)})</td></tr>
                    <tr className="fw-bold"><td>Net</td><td className="text-end">{fmtUSD(r.finance.net)}</td></tr>
                  </tbody>
                </table>
              </div>
              <div className="col-md-6">
                {Object.keys(r.finance.expenses_by_category).length > 0 && (
                  <table className="table table-sm mb-0">
                    <thead><tr><th>Expenses by category</th><th className="text-end"></th></tr></thead>
                    <tbody>
                      {Object.entries(r.finance.expenses_by_category).map(([c, a]) => (
                        <tr key={c}><td style={{ textTransform: 'capitalize' }}>{c}</td><td className="text-end">{fmtUSD(a)}</td></tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>

            {/* Methodology */}
            <div className="text-muted mt-4" style={{ fontSize: '.72rem', borderTop: '1px solid var(--yh-border)', paddingTop: 8 }}>
              Methodology: produce valued at ${r.rates.produce_rate}/lb; volunteer time valued at
              ${r.rates.volunteer_rate}/hour (Independent Sector 2024 national average);
              meals estimated at {r.rates.lbs_per_meal} lbs per meal (Feeding America);
              CO₂ estimate of {r.rates.co2_per_lb} lbs per lb of donated/shared produce.
              Volunteer hours are logged, attended shift hours — event participation is reported separately.
              Data recorded in YardHarvest by {r.garden.name}.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
