import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { plantingAPI } from '../api';

const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

const ACTIVITY_COLORS = {
  indoor_seed: { bg: '#3b82f6', label: 'Start Indoors' },
  direct_sow:  { bg: '#22c55e', label: 'Direct Sow' },
  transplant:  { bg: '#f59e0b', label: 'Transplant' },
  harvest:     { bg: '#ef4444', label: 'Harvest' },
};

const styles = {
  page: {
    maxWidth: 1100,
    margin: '0 auto',
    padding: '0 16px',
  },
  header: {
    textAlign: 'center',
    marginBottom: 32,
  },
  title: {
    fontSize: 32,
    fontWeight: 700,
    color: '#2d6a4f',
    marginBottom: 4,
  },
  subtitle: {
    color: '#666',
    fontSize: 15,
    marginBottom: 0,
  },
  summaryCard: {
    background: '#D8EDDF',
    borderRadius: 12,
    padding: '20px 28px',
    marginBottom: 28,
    border: '1px solid #74C69D',
  },
  summaryTitle: {
    fontWeight: 700,
    fontSize: 18,
    color: '#2d6a4f',
    marginBottom: 10,
  },
  summaryList: {
    margin: 0,
    paddingLeft: 20,
    color: '#1b4332',
    lineHeight: 1.7,
  },
  legend: {
    display: 'flex',
    gap: 20,
    justifyContent: 'center',
    flexWrap: 'wrap',
    marginBottom: 20,
  },
  legendItem: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    fontSize: 13,
  },
  legendDot: (color) => ({
    width: 14,
    height: 14,
    borderRadius: 3,
    backgroundColor: color,
  }),
  frostLine: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    fontSize: 13,
  },
  frostDot: {
    width: 14,
    height: 2,
    backgroundColor: '#9333ea',
  },
  calendarContainer: {
    overflowX: 'auto',
    marginBottom: 28,
  },
  calendarTable: {
    width: '100%',
    minWidth: 800,
    borderCollapse: 'collapse',
  },
  monthHeader: {
    padding: '8px 2px',
    fontSize: 12,
    fontWeight: 600,
    textAlign: 'center',
    color: '#555',
    borderBottom: '2px solid #e5e7eb',
    width: `${100 / 13}%`,
  },
  currentMonthHeader: {
    backgroundColor: '#D8EDDF',
    color: '#2d6a4f',
    fontWeight: 700,
    borderRadius: '6px 6px 0 0',
  },
  categoryCell: {
    padding: '10px 8px',
    fontWeight: 600,
    fontSize: 13,
    color: '#2d6a4f',
    borderBottom: '1px solid #f0f0f0',
    whiteSpace: 'nowrap',
    cursor: 'pointer',
    verticalAlign: 'middle',
    width: `${100 / 13}%`,
  },
  monthCell: {
    padding: '6px 2px',
    borderBottom: '1px solid #f0f0f0',
    position: 'relative',
    height: 32,
    verticalAlign: 'middle',
  },
  currentMonthCell: {
    backgroundColor: '#D8EDDF',
  },
  bar: (color, leftPct, widthPct) => ({
    position: 'absolute',
    top: '50%',
    transform: 'translateY(-50%)',
    left: `${leftPct}%`,
    width: `${widthPct}%`,
    height: 10,
    backgroundColor: color,
    borderRadius: 5,
    minWidth: 4,
  }),
  frostMarker: (leftPct) => ({
    position: 'absolute',
    top: 0,
    bottom: 0,
    left: `${leftPct}%`,
    width: 2,
    backgroundColor: '#9333ea',
    opacity: 0.5,
  }),
  selectedRow: {
    backgroundColor: '#D8EDDF',
  },
  detailPanel: {
    background: '#fff',
    border: '2px solid #74C69D',
    borderRadius: 12,
    padding: 24,
    marginBottom: 28,
  },
  detailTitle: {
    fontSize: 22,
    fontWeight: 700,
    color: '#2d6a4f',
    marginBottom: 16,
  },
  detailGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
    gap: 16,
    marginBottom: 16,
  },
  detailCard: {
    backgroundColor: '#f8f9fa',
    borderRadius: 8,
    padding: 14,
  },
  detailLabel: {
    fontWeight: 600,
    fontSize: 12,
    color: '#888',
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
    marginBottom: 4,
  },
  detailValue: {
    fontSize: 14,
    color: '#333',
    lineHeight: 1.5,
  },
  linkRow: {
    display: 'flex',
    gap: 12,
    flexWrap: 'wrap',
    marginTop: 12,
  },
  link: {
    color: '#2d6a4f',
    fontWeight: 600,
    textDecoration: 'none',
    fontSize: 14,
  },
  navLinks: {
    display: 'flex',
    gap: 16,
    justifyContent: 'center',
    flexWrap: 'wrap',
    marginBottom: 24,
  },
  navLink: {
    display: 'inline-block',
    padding: '8px 20px',
    backgroundColor: '#40916c',
    color: '#fff',
    borderRadius: 8,
    textDecoration: 'none',
    fontWeight: 600,
    fontSize: 14,
  },
  loading: {
    textAlign: 'center',
    padding: 60,
    color: '#888',
  },
};


export default function PlantingCalendar() {
  const [calendarData, setCalendarData] = useState([]);
  const [guideData, setGuideData] = useState([]);
  const [selectedCategory, setSelectedCategory] = useState(null);
  const [loading, setLoading] = useState(true);

  const currentMonth = new Date().getMonth(); // 0-indexed
  const currentDoy = Math.floor((new Date() - new Date(new Date().getFullYear(), 0, 0)) / 86400000);
  const LAST_FROST_DOY = 115; // ~April 25
  const FIRST_FROST_DOY = 283; // ~Oct 10

  useEffect(() => {
    Promise.all([plantingAPI.calendar(), plantingAPI.guide()])
      .then(([calRes, guideRes]) => {
        setCalendarData(calRes.data);
        setGuideData(guideRes.data);
      })
      .catch(err => console.error('Failed to load planting data:', err))
      .finally(() => setLoading(false));
  }, []);

  const selectedGuide = guideData.find(g => g.category === selectedCategory);

  // What to do this month
  const getThisMonthActivities = () => {
    const activities = [];
    const monthStart = currentMonth * 30.44 + 1; // rough doy
    const monthEnd = (currentMonth + 1) * 30.44;

    calendarData.forEach(cat => {
      cat.activities.forEach(act => {
        if (act.start_doy <= monthEnd && act.end_doy >= monthStart) {
          activities.push({
            category: cat.category,
            type: act.type,
            label: act.label,
          });
        }
      });
    });
    return activities;
  };

  // Convert doy to percentage position within a month cell (0-100%)
  const doyToMonthPosition = (doy, monthIndex) => {
    // Day ranges for each month (non-leap year approximation)
    const monthStartDoys = [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335];
    const monthEndDoys = [31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334, 365];

    const mStart = monthStartDoys[monthIndex];
    const mEnd = monthEndDoys[monthIndex];
    const mLength = mEnd - mStart + 1;

    if (doy < mStart) return 0;
    if (doy > mEnd) return 100;
    return ((doy - mStart) / mLength) * 100;
  };

  // Get bar segments for a given activity within a specific month
  const getBarForMonth = (activity, monthIndex) => {
    const monthStartDoys = [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335];
    const monthEndDoys = [31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334, 365];

    const mStart = monthStartDoys[monthIndex];
    const mEnd = monthEndDoys[monthIndex];

    // Check if activity overlaps this month
    if (activity.start_doy > mEnd || activity.end_doy < mStart) return null;

    const barStart = Math.max(activity.start_doy, mStart);
    const barEnd = Math.min(activity.end_doy, mEnd);
    const mLength = mEnd - mStart + 1;

    const leftPct = ((barStart - mStart) / mLength) * 100;
    const widthPct = ((barEnd - barStart + 1) / mLength) * 100;

    return { leftPct, widthPct };
  };

  // Frost line position within a month
  const getFrostLineForMonth = (frostDoy, monthIndex) => {
    const monthStartDoys = [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335];
    const monthEndDoys = [31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334, 365];

    const mStart = monthStartDoys[monthIndex];
    const mEnd = monthEndDoys[monthIndex];

    if (frostDoy < mStart || frostDoy > mEnd) return null;
    const mLength = mEnd - mStart + 1;
    return ((frostDoy - mStart) / mLength) * 100;
  };

  if (loading) return <div style={styles.loading}>Loading planting calendar...</div>;

  const thisMonthActivities = getThisMonthActivities();
  // Group by type for summary
  const grouped = {};
  thisMonthActivities.forEach(a => {
    if (!grouped[a.label]) grouped[a.label] = [];
    if (!grouped[a.label].includes(a.category)) grouped[a.label].push(a.category);
  });

  return (
    <div style={styles.page}>
      <div style={styles.header}>
        <h1 style={styles.title}>Omaha Zone 5b Planting Calendar</h1>
        <p style={styles.subtitle}>
          Last frost ~April 25 | First frost ~October 10 | Interactive growing guide for the Omaha area
        </p>
      </div>

      <div style={styles.navLinks}>
        <Link to="/harvest-forecast" style={styles.navLink}>
          <i className="bi bi-graph-up-arrow me-1"></i> Harvest Forecast
        </Link>
        <Link to="/my-planting-log" style={styles.navLink}>
          <i className="bi bi-journal-plus me-1"></i> My Planting Log
        </Link>
      </div>

      {/* What to do this month */}
      {Object.keys(grouped).length > 0 && (
        <div style={styles.summaryCard}>
          <div style={styles.summaryTitle}>
            <i className="bi bi-calendar-check me-2"></i>
            What to Do in {MONTHS[currentMonth]}
          </div>
          <ul style={styles.summaryList}>
            {Object.entries(grouped).map(([label, cats]) => (
              <li key={label}>
                <strong>{label}:</strong> {cats.join(', ')}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Legend */}
      <div style={styles.legend}>
        {Object.entries(ACTIVITY_COLORS).map(([key, val]) => (
          <div key={key} style={styles.legendItem}>
            <div style={styles.legendDot(val.bg)}></div>
            <span>{val.label}</span>
          </div>
        ))}
        <div style={styles.frostLine}>
          <div style={styles.frostDot}></div>
          <span>Frost Dates</span>
        </div>
      </div>

      {/* Calendar Grid */}
      <div style={styles.calendarContainer}>
        <table style={styles.calendarTable}>
          <thead>
            <tr>
              <th style={styles.monthHeader}>Crop</th>
              {MONTHS.map((m, i) => (
                <th
                  key={m}
                  style={{
                    ...styles.monthHeader,
                    ...(i === currentMonth ? styles.currentMonthHeader : {}),
                  }}
                >
                  {m}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {calendarData.map(cat => (
              <tr
                key={cat.category}
                style={selectedCategory === cat.category ? styles.selectedRow : {}}
              >
                <td
                  style={styles.categoryCell}
                  onClick={() =>
                    setSelectedCategory(
                      selectedCategory === cat.category ? null : cat.category
                    )
                  }
                  title="Click for details"
                >
                  {cat.category}
                  {cat.frost_sensitive && (
                    <span style={{ color: '#ef4444', marginLeft: 4, fontSize: 11 }} title="Frost sensitive">*</span>
                  )}
                </td>
                {MONTHS.map((m, mi) => {
                  const lastFrostPct = getFrostLineForMonth(LAST_FROST_DOY, mi);
                  const firstFrostPct = getFrostLineForMonth(FIRST_FROST_DOY, mi);
                  return (
                    <td
                      key={m}
                      style={{
                        ...styles.monthCell,
                        ...(mi === currentMonth ? styles.currentMonthCell : {}),
                      }}
                    >
                      {lastFrostPct !== null && <div style={styles.frostMarker(lastFrostPct)}></div>}
                      {firstFrostPct !== null && <div style={styles.frostMarker(firstFrostPct)}></div>}
                      {cat.activities.map((act, ai) => {
                        const bar = getBarForMonth(act, mi);
                        if (!bar) return null;
                        return (
                          <div
                            key={ai}
                            style={styles.bar(
                              ACTIVITY_COLORS[act.type]?.bg || '#999',
                              bar.leftPct,
                              bar.widthPct
                            )}
                            title={`${act.label}: ${act.start?.label || ''} - ${act.end?.label || ''}`}
                          ></div>
                        );
                      })}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p style={{ textAlign: 'center', fontSize: 12, color: '#999', marginBottom: 24 }}>
        * = Frost sensitive. Click any crop row for detailed growing information.
      </p>

      {/* Detail Panel */}
      {selectedGuide && (
        <div style={styles.detailPanel}>
          <div style={styles.detailTitle}>
            <i className="bi bi-flower1 me-2"></i>
            {selectedGuide.category} Growing Guide
          </div>
          <div style={styles.detailGrid}>
            {selectedGuide.seed_indoor_start_doy && (
              <div style={styles.detailCard}>
                <div style={styles.detailLabel}>Start Indoors</div>
                <div style={styles.detailValue}>
                  Day {selectedGuide.seed_indoor_start_doy} (~{doyToLabel(selectedGuide.seed_indoor_start_doy)})
                </div>
              </div>
            )}
            {selectedGuide.direct_sow_start_doy && (
              <div style={styles.detailCard}>
                <div style={styles.detailLabel}>Direct Sow Window</div>
                <div style={styles.detailValue}>
                  {doyToLabel(selectedGuide.direct_sow_start_doy)} - {doyToLabel(selectedGuide.direct_sow_end_doy)}
                </div>
              </div>
            )}
            {selectedGuide.transplant_start_doy && (
              <div style={styles.detailCard}>
                <div style={styles.detailLabel}>Transplant Window</div>
                <div style={styles.detailValue}>
                  {doyToLabel(selectedGuide.transplant_start_doy)} - {doyToLabel(selectedGuide.transplant_end_doy)}
                </div>
              </div>
            )}
            <div style={styles.detailCard}>
              <div style={styles.detailLabel}>Days to Harvest</div>
              <div style={styles.detailValue}>
                {selectedGuide.days_to_harvest_min} - {selectedGuide.days_to_harvest_max} days
              </div>
            </div>
            {selectedGuide.succession_interval_days && (
              <div style={styles.detailCard}>
                <div style={styles.detailLabel}>Succession Planting</div>
                <div style={styles.detailValue}>
                  Every {selectedGuide.succession_interval_days} days
                </div>
              </div>
            )}
            <div style={styles.detailCard}>
              <div style={styles.detailLabel}>Frost Sensitive</div>
              <div style={styles.detailValue}>
                {selectedGuide.frost_sensitive ? 'Yes - protect from frost' : 'No - tolerates light frost'}
              </div>
            </div>
            <div style={styles.detailCard}>
              <div style={styles.detailLabel}>Companion Plants</div>
              <div style={styles.detailValue}>{selectedGuide.companion_plants || 'N/A'}</div>
            </div>
            <div style={styles.detailCard}>
              <div style={styles.detailLabel}>Avoid Planting Near</div>
              <div style={styles.detailValue}>{selectedGuide.avoid_near || 'N/A'}</div>
            </div>
          </div>
          {selectedGuide.notes && (
            <div style={{ ...styles.detailCard, marginBottom: 12 }}>
              <div style={styles.detailLabel}>Omaha Growing Tips</div>
              <div style={styles.detailValue}>{selectedGuide.notes}</div>
            </div>
          )}
          <div style={styles.linkRow}>
            <Link
              to={`/planting-guide/${encodeURIComponent(selectedGuide.category)}`}
              style={styles.link}
            >
              <i className="bi bi-book me-1"></i> Full Guide
            </Link>
            <Link
              to={`/browse?category=${encodeURIComponent(selectedGuide.category)}`}
              style={styles.link}
            >
              <i className="bi bi-shop me-1"></i> Browse Marketplace
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}

function doyToLabel(doy) {
  if (!doy) return '';
  const d = new Date(2025, 0, 1);
  d.setDate(d.getDate() + doy - 1);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}
