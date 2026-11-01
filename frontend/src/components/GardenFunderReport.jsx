import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation, Trans } from 'react-i18next';
import { gardenAdminAPI } from '../api';
import { formatDate, currentLocale } from '../i18n/dates';

// Funder-facing impact report: date-ranged aggregates (harvest,
// participation, volunteering, events, finance) with valuation equivalents,
// printable to PDF via the browser and exportable as CSV. The numbers come
// from GET /garden-admin/:id/funder-report (Pro).

// Numbers and dates follow the page's language, not the browser's.
const fmtUSD = (v) => `$${Number(v || 0).toLocaleString(currentLocale(), { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const fmtN = (v) => Number(v || 0).toLocaleString(currentLocale());
const LONG_DATE = { year: 'numeric', month: 'long', day: 'numeric' };
const fmtLong = (iso) => formatDate(`${iso}T12:00:00`, LONG_DATE);
const fmtLabel = (s) => String(s || '').replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase());

// Slugs the server sends, labelled the way the rest of the app labels them.
// Module scope cannot call t(), so these hold catalog keys; an unknown slug
// falls back to fmtLabel.
const HARVEST_CATEGORY_KEYS = {
  tomatoes: 'garden.catTomatoes', peppers: 'garden.catPeppers',
  greens: 'garden.catGreens', herbs: 'garden.catHerbs',
  squash: 'garden.catSquash', beans: 'garden.catBeans',
  root_vegetables: 'garden.catRootVegetables', corn: 'garden.catCorn',
  berries: 'garden.catBerries', other: 'garden.catOther',
  Uncategorized: 'impact.uncategorized',
};
const EVENT_TYPE_KEYS = {
  workday: 'garden.eventTypeWorkday', workshop: 'garden.eventTypeWorkshop',
  social: 'garden.eventTypeSocial', meeting: 'garden.eventTypeMeeting',
  harvest_day: 'garden.eventTypeHarvestDay', other: 'garden.typeOther',
};
// The same event types counted inside a sentence: "3 workdays".
const EVENT_COUNT_KEYS = {
  workday: 'funderReport.evWorkday', workshop: 'funderReport.evWorkshop',
  social: 'funderReport.evSocial', meeting: 'funderReport.evMeeting',
  harvest_day: 'funderReport.evHarvestDay', other: 'funderReport.evOther',
};
const EXPENSE_CATEGORY_KEYS = {
  supplies: 'dash.expSupplies', infrastructure: 'dash.expInfrastructure',
  water: 'dash.expWater', seeds: 'dash.expSeeds', tools: 'dash.expTools',
  other: 'dash.expOther',
};
const labelFrom = (keys, slug, t) => (keys[slug] ? t(keys[slug]) : fmtLabel(slug));
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
  const { t } = useTranslation();
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
        setError(t('funderReport.errLoad'));
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
    // Labels follow the page's language; the values stay raw numbers so the
    // file still opens as data in a spreadsheet.
    const sec = {
      period: t('funderReport.csvPeriod'), harvest: t('funderReport.csvHarvest'),
      participation: t('funderReport.csvParticipation'),
      volunteering: t('funderReport.csvVolunteering'), events: t('funderReport.csvEvents'),
      finance: t('funderReport.csvFinance'), impact: t('funderReport.csvImpact'),
      methodology: t('funderReport.csvMethodology'),
    };
    const rows = [
      [t('funderReport.csvSection'), t('funderReport.csvMetric'), t('funderReport.csvValue')],
      [sec.period, t('funderReport.csvStart'), r.period.start], [sec.period, t('funderReport.csvEnd'), r.period.end],
      [sec.harvest, t('funderReport.csvTotalProduce'), r.harvest.total_lbs],
      [sec.harvest, t('funderReport.csvFoodBank'), r.harvest.food_bank_lbs],
      [sec.harvest, t('funderReport.csvShared'), r.harvest.shared_lbs],
      [sec.harvest, t('funderReport.csvGardeners'), r.harvest.gardeners],
      ...r.harvest.by_category.map((c) => [t('funderReport.csvHarvestByCrop'), labelFrom(HARVEST_CATEGORY_KEYS, c.category, t), c.lbs]),
      [sec.participation, t('garden.members'), r.participation.members_total],
      [sec.participation, t('funderReport.csvNewMembers'), r.participation.members_new],
      [sec.participation, t('funderReport.csvPlots'), r.participation.plots_total],
      [sec.participation, t('funderReport.csvPlotsAssigned'), r.participation.plots_assigned],
      [sec.participation, t('funderReport.csvOccupancy'), r.participation.occupancy_pct],
      [sec.volunteering, t('funderReport.csvShiftsHeld'), r.volunteering.shifts_held],
      [sec.volunteering, t('funderReport.csvVolunteers'), r.volunteering.volunteers],
      [sec.volunteering, t('funderReport.csvHoursLogged'), r.volunteering.hours],
      [sec.volunteering, t('funderReport.csvValueUsd'), r.volunteering.value_usd],
      [sec.events, t('funderReport.tileEventsHeld'), r.events.held],
      [sec.events, t('funderReport.csvRsvps'), r.events.rsvps_going],
      ...Object.entries(r.events.by_type).map(([type, n]) => [t('funderReport.csvEventsByType'), labelFrom(EVENT_TYPE_KEYS, type, t), n]),
      [sec.finance, t('funderReport.csvDuesCollected'), r.finance.dues_collected],
      [sec.finance, t('funderReport.csvDuesExpected'), r.finance.dues_expected],
      [sec.finance, t('funderReport.csvExpenses'), r.finance.expenses_total],
      ...Object.entries(r.finance.expenses_by_category).map(([c, a]) => [t('funderReport.expensesByCategory'), labelFrom(EXPENSE_CATEGORY_KEYS, c, t), a]),
      [sec.finance, t('funderReport.csvNet'), r.finance.net],
      [sec.impact, t('funderReport.tileMeals'), r.equivalents.meals],
      [sec.impact, t('funderReport.csvProduceValue'), r.equivalents.produce_value_usd],
      [sec.impact, t('funderReport.csvCo2'), r.equivalents.co2_saved_lbs],
      [sec.methodology, t('funderReport.csvProduceRate'), r.rates.produce_rate],
      [sec.methodology, t('funderReport.csvVolunteerRate'), r.rates.volunteer_rate],
      [sec.methodology, t('funderReport.csvLbsPerMeal'), r.rates.lbs_per_meal],
    ];
    const csv = rows.map((row) =>
      row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = t('funderReport.csvFilename', {
      name: (garden?.name || t('funderReport.csvDefaultName')).replace(/\W+/g, '-'),
      start: report.period.start, end: report.period.end,
    });
    a.click();
    URL.revokeObjectURL(a.href);
  };

  if (needsPro) {
    return (
      <div className="text-center py-5">
        <i className="bi bi-file-earmark-bar-graph" style={{ fontSize: '3rem', color: '#ccc' }}></i>
        <h5 className="mt-3 fw-bold">{t('funderReport.proTitle')}</h5>
        <p className="text-muted" style={{ maxWidth: 420, margin: '0 auto 16px' }}>
          {t('funderReport.proBody')}
        </p>
        <Link to={`/gardens/${gardenId}/billing`} className="btn" style={{ backgroundColor: 'var(--yh-lime)', color: '#22242a', fontWeight: 600 }}>
          {t('funderReport.upgrade')}
        </Link>
      </div>
    );
  }

  const r = report;

  return (
    <div>
      <h4 className="fw-bold mb-3"><i className="bi bi-file-earmark-bar-graph me-2"></i>{t('dash.tabReports')}</h4>

      {/* Controls (never printed) */}
      <div className="card mb-4 d-print-none" style={{ border: '1px solid var(--yh-border)' }}>
        <div className="card-body">
          <div className="d-flex flex-wrap gap-1 mb-3">
            {[['this_year', t('funderReport.presetThisYear')], ['last_year', t('funderReport.presetLastYear')],
              ['season', t('funderReport.presetSeason')], ['twelve_months', t('funderReport.presetTwelveMonths')],
              ['custom', t('funderReport.presetCustom')]].map(([key, label]) => (
              <button key={key}
                      className={`btn btn-sm ${preset === key ? 'btn-dark' : 'btn-outline-secondary'} rounded-pill`}
                      onClick={() => pickPreset(key)}>{label}</button>
            ))}
          </div>
          <div className="row g-2 align-items-end">
            <div className="col-6 col-md-2">
              <label className="form-label small mb-1">{t('funderReport.from')}</label>
              <input type="date" className="form-control form-control-sm" value={range[0]}
                     onChange={(e) => { setPreset('custom'); setRange([e.target.value, range[1]]); }} />
            </div>
            <div className="col-6 col-md-2">
              <label className="form-label small mb-1">{t('funderReport.to')}</label>
              <input type="date" className="form-control form-control-sm" value={range[1]}
                     onChange={(e) => { setPreset('custom'); setRange([range[0], e.target.value]); }} />
            </div>
            <div className="col-6 col-md-2">
              <label className="form-label small mb-1" title={t('funderReport.produceRateHelp')}>{t('funderReport.produceRate')}</label>
              <input type="number" step="0.25" min="0" className="form-control form-control-sm"
                     value={produceRate} onChange={(e) => setProduceRate(e.target.value)} />
            </div>
            <div className="col-6 col-md-2">
              <label className="form-label small mb-1" title={t('funderReport.volunteerRateHelp', { rate: fmtN(33.49) })}>{t('funderReport.volunteerRate')}</label>
              <input type="number" step="0.5" min="0" className="form-control form-control-sm"
                     value={volunteerRate} onChange={(e) => setVolunteerRate(e.target.value)} />
            </div>
            <div className="col-12 col-md-4">
              <label className="form-label small mb-1">{t('funderReport.preparedFor')}</label>
              <input className="form-control form-control-sm" value={preparedFor}
                     placeholder={t('funderReport.preparedForPlaceholder')}
                     onChange={(e) => setPreparedFor(e.target.value)} />
            </div>
          </div>
          <div className="mt-2">
            <label className="form-label small mb-1">{t('funderReport.notes')}</label>
            <textarea className="form-control form-control-sm" rows={2} value={notes}
                      placeholder={t('funderReport.notesPlaceholder')}
                      onChange={(e) => setNotes(e.target.value)} />
          </div>
          <div className="d-flex gap-2 mt-3">
            <button className="btn btn-sm" style={{ backgroundColor: '#22242a', color: '#fff' }}
                    onClick={printReport} disabled={!r}>
              <i className="bi bi-printer me-1"></i>{t('funderReport.print')}
            </button>
            <button className="btn btn-sm btn-outline-secondary" onClick={downloadCsv} disabled={!r}>
              <i className="bi bi-download me-1"></i>{t('funderReport.downloadCsv')}
            </button>
          </div>
        </div>
      </div>

      {loading && <div className="text-center py-4"><div className="spinner-border text-success"></div></div>}
      {error && (
        <div className="alert alert-warning d-flex align-items-center justify-content-between d-print-none">
          <span>{error}</span>
          <button className="btn btn-sm btn-outline-secondary" onClick={load}>{t('gardensList.tryAgain')}</button>
        </div>
      )}

      {/* ---- The printable report ---- */}
      {r && !loading && (
        <div className="funder-report card" style={{ border: '1px solid var(--yh-border)' }}>
          <div className="card-body p-4">
            <div className="fr-header" style={{ borderBottom: '3px solid #e3ff8f', paddingBottom: 12, marginBottom: 18 }}>
              <div className="d-flex justify-content-between flex-wrap align-items-baseline">
                <h3 className="fw-bold mb-0">{r.garden.name}</h3>
                <span className="text-muted">{[r.garden.city, r.garden.state].filter(Boolean).join(', ')}</span>
              </div>
              <div className="mt-1" style={{ fontSize: '1.05rem' }}>{t('funderReport.reportTitle')}</div>
              <div className="text-muted" style={{ fontSize: '.9rem' }}>
                {fmtLong(r.period.start)} — {fmtLong(r.period.end)}
                {preparedFor && <> · {t('funderReport.preparedForLine', { name: preparedFor })}</>}
                {' '}· {t('funderReport.generatedOn', { date: formatDate(new Date(), LONG_DATE) })}
              </div>
            </div>

            {/* Headline tiles */}
            <div className="row g-2">
              {[
                [t('impact.lbsValue', { value: fmtN(r.harvest.total_lbs) }), t('funderReport.tileProduce')],
                [fmtN(r.equivalents.meals), t('funderReport.tileMeals')],
                [fmtN(r.volunteering.hours), t('funderReport.tileVolunteerHours')],
                [fmtUSD(r.volunteering.value_usd), t('funderReport.tileVolunteerValue')],
                [fmtN(r.participation.members_total), t('garden.members')],
                [`+${fmtN(r.participation.members_new)}`, t('funderReport.tileNewMembers')],
                [fmtN(r.events.held), t('funderReport.tileEventsHeld')],
                [`${r.participation.occupancy_pct}%`, t('funderReport.tileOccupancy')],
              ].map(([value, label]) => (
                <div key={label} className="col-6 col-md-3 fr-tile-col">
                  <div className="fr-tile" style={TILE}>
                    <div className="fr-tile-value" style={TILE_VALUE}>{value}</div>
                    <div className="fr-tile-label" style={TILE_LABEL}>{label}</div>
                  </div>
                </div>
              ))}
            </div>

            {notes.trim() && (
              <p className="mt-3 mb-0" style={{ fontSize: '.95rem' }}>{notes}</p>
            )}

            {/* Harvest */}
            <div className="fr-section" style={SECTION_H}>{t('funderReport.harvestHeading')}</div>
            <div className="row">
              <div className="col-md-7">
                <table className="table table-sm mb-2">
                  <thead><tr><th>{t('funderReport.crop')}</th><th className="text-end">{t('garden.pounds')}</th></tr></thead>
                  <tbody>
                    {r.harvest.by_category.map((c) => (
                      <tr key={c.category}><td>{labelFrom(HARVEST_CATEGORY_KEYS, c.category, t)}</td><td className="text-end">{fmtN(c.lbs)}</td></tr>
                    ))}
                    {r.harvest.by_category.length === 0 && (
                      <tr><td colSpan={2} className="text-muted">{t('funderReport.noHarvests')}</td></tr>
                    )}
                  </tbody>
                  {r.harvest.by_category.length > 0 && (
                    <tfoot><tr className="fw-bold"><td>{t('funderReport.total')}</td><td className="text-end">{fmtN(r.harvest.total_lbs)}</td></tr></tfoot>
                  )}
                </table>
              </div>
              <div className="col-md-5">
                <p style={{ fontSize: '.92rem' }} className="mb-1">
                  <Trans i18nKey="funderReport.harvestLine" count={r.equivalents.meals}
                         values={{ foodBank: fmtN(r.harvest.food_bank_lbs), shared: fmtN(r.harvest.shared_lbs), meals: fmtN(r.equivalents.meals) }}
                         components={{ b: <strong /> }} />
                </p>
                <p style={{ fontSize: '.92rem' }} className="mb-1">
                  <Trans i18nKey="funderReport.marketValue"
                         values={{ value: fmtUSD(r.equivalents.produce_value_usd) }}
                         components={{ b: <strong /> }} />
                </p>
                <p style={{ fontSize: '.92rem' }} className="mb-0">
                  <Trans i18nKey="funderReport.gardenersLine" count={r.harvest.gardeners}
                         values={{ gardeners: fmtN(r.harvest.gardeners), co2: fmtN(r.equivalents.co2_saved_lbs) }}
                         components={{ b: <strong /> }} />
                </p>
              </div>
            </div>

            {/* Participation + Volunteering */}
            <div className="fr-section" style={SECTION_H}>{t('funderReport.communityHeading')}</div>
            <div className="row" style={{ fontSize: '.92rem' }}>
              <div className="col-md-6">
                <ul className="mb-2">
                  <li><Trans i18nKey="funderReport.membersLine" count={r.participation.members_total}
                             values={{ total: fmtN(r.participation.members_total), newCount: fmtN(r.participation.members_new) }}
                             components={{ b: <strong /> }} /></li>
                  <li><Trans i18nKey="funderReport.plotsLine" count={r.participation.plots_total}
                             values={{ assigned: fmtN(r.participation.plots_assigned), total: fmtN(r.participation.plots_total), pct: r.participation.occupancy_pct }}
                             components={{ b: <strong /> }} /></li>
                  <li><Trans i18nKey="funderReport.eventsLine" count={r.events.held}
                             values={{ held: fmtN(r.events.held), rsvps: t('funderReport.rsvpCount', { count: r.events.rsvps_going, value: fmtN(r.events.rsvps_going) }) }}
                             components={{ b: <strong /> }} />
                    {Object.keys(r.events.by_type).length > 0 && (
                      <> ({Object.entries(r.events.by_type).map(([type, n]) => (EVENT_COUNT_KEYS[type]
                        ? t(EVENT_COUNT_KEYS[type], { count: n, value: fmtN(n) })
                        : `${n} ${type.replace('_', ' ')}`)).join(', ')})</>
                    )}
                  </li>
                </ul>
              </div>
              <div className="col-md-6">
                <ul className="mb-2">
                  {/* Three counts in one sentence: the hours phrase is its own
                      pluralised <Trans> (keeping its bold number), the shifts
                      phrase a plain pluralised string. */}
                  <li><Trans i18nKey="funderReport.volunteerLine" count={r.volunteering.volunteers}
                             values={{
                               volunteers: fmtN(r.volunteering.volunteers),
                               shifts: t('funderReport.shiftsCount', { count: r.volunteering.shifts_held, value: fmtN(r.volunteering.shifts_held) }),
                             }}
                             components={{
                               b: <strong />,
                               hours: <Trans i18nKey="funderReport.hoursLogged" count={r.volunteering.hours}
                                             values={{ hours: fmtN(r.volunteering.hours) }}
                                             components={{ b: <strong /> }} />,
                             }} /></li>
                  <li><Trans i18nKey="funderReport.volunteerValueLine"
                             values={{ value: fmtUSD(r.volunteering.value_usd), rate: fmtN(r.rates.volunteer_rate) }}
                             components={{ b: <strong /> }} /></li>
                </ul>
              </div>
            </div>

            {/* Finance */}
            <div className="fr-section" style={SECTION_H}>{t('funderReport.financeHeading')}</div>
            <div className="row" style={{ fontSize: '.92rem' }}>
              <div className="col-md-6">
                <table className="table table-sm mb-0">
                  <tbody>
                    <tr><td>{t('funderReport.duesCollected')}</td><td className="text-end">{fmtUSD(r.finance.dues_collected)}</td></tr>
                    <tr><td className="text-muted">{t('funderReport.duesBilled')}</td><td className="text-end text-muted">{fmtUSD(r.finance.dues_expected)}</td></tr>
                    <tr><td>{t('dash.financeExpenses')}</td><td className="text-end">({fmtUSD(r.finance.expenses_total)})</td></tr>
                    <tr className="fw-bold"><td>{t('funderReport.net')}</td><td className="text-end">{fmtUSD(r.finance.net)}</td></tr>
                  </tbody>
                </table>
              </div>
              <div className="col-md-6">
                {Object.keys(r.finance.expenses_by_category).length > 0 && (
                  <table className="table table-sm mb-0">
                    <thead><tr><th>{t('funderReport.expensesByCategory')}</th><th className="text-end"></th></tr></thead>
                    <tbody>
                      {Object.entries(r.finance.expenses_by_category).map(([c, a]) => (
                        <tr key={c}><td>{labelFrom(EXPENSE_CATEGORY_KEYS, c, t)}</td><td className="text-end">{fmtUSD(a)}</td></tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>

            {/* Methodology */}
            <div className="text-muted mt-4 fr-method" style={{ fontSize: '.72rem', borderTop: '1px solid var(--yh-border)', paddingTop: 8 }}>
              {t('funderReport.methodology', {
                produceRate: fmtN(r.rates.produce_rate),
                volunteerRate: fmtN(r.rates.volunteer_rate),
                lbsPerMeal: fmtN(r.rates.lbs_per_meal),
                co2PerLb: fmtN(r.rates.co2_per_lb),
                name: r.garden.name,
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
