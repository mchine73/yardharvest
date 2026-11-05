import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { plantingAPI } from '../api';
import Seo from '../components/Seo';
import { formatDate, DAY_MONTH } from '../i18n/dates';
import { cropLabel } from '../data/plantingCrops';
import { cropProse } from '../data/plantingCropNotes.es';

const ACTIVITY_COLORS = {
  indoor_seed: '#3f7ddb',
  direct_sow:  '#22c55e',
  transplant:  'var(--brand-gold)',
  harvest:     '#ef4444',
};

// Keys, not text: module scope runs before any t() exists.
const ACTIVITY_LABEL_KEYS = {
  indoor_seed: 'plantingCalendar.actIndoorSeed',
  direct_sow:  'plantingCalendar.actDirectSow',
  transplant:  'plantingCalendar.actTransplant',
  harvest:     'cropGuide.harvestWindow',
};

// The bar itself repeats the activity's short name (what the API sends as an
// English `label`), so harvest reads "Harvest" there, not "Harvest Window".
const ACTIVITY_SHORT_KEYS = {
  ...ACTIVITY_LABEL_KEYS,
  harvest: 'plantingCalendar.actHarvest',
};

const styles = {
  page: {
    maxWidth: 800,
    margin: '0 auto',
    padding: '0 16px',
  },
  backLink: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    color: 'var(--brand-secondary)',
    textDecoration: 'none',
    fontWeight: 600,
    fontSize: 14,
    marginBottom: 20,
  },
  header: {
    marginBottom: 28,
  },
  title: {
    fontSize: 30,
    fontWeight: 700,
    color: 'var(--brand-secondary)',
    marginBottom: 4,
  },
  zoneBadge: {
    display: 'inline-block',
    padding: '3px 10px',
    background: 'var(--brand-pale)',
    color: 'var(--brand-secondary)',
    borderRadius: 12,
    fontSize: 12,
    fontWeight: 600,
    marginLeft: 10,
  },
  frostBadge: (sensitive) => ({
    display: 'inline-block',
    padding: '3px 10px',
    background: sensitive ? '#fef2f2' : 'var(--brand-pale)',
    color: sensitive ? '#dc2626' : '#16a34a',
    borderRadius: 12,
    fontSize: 12,
    fontWeight: 600,
    marginLeft: 8,
  }),
  subtitle: {
    color: '#666',
    fontSize: 15,
    marginTop: 6,
  },
  section: {
    marginBottom: 28,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: 700,
    color: 'var(--brand-secondary)',
    marginBottom: 14,
    paddingBottom: 6,
    borderBottom: '2px solid var(--brand-pale)',
  },
  timelineContainer: {
    background: '#f8f9fa',
    borderRadius: 12,
    padding: 20,
    marginBottom: 20,
  },
  timelineBar: {
    position: 'relative',
    height: 40,
    background: '#e5e7eb',
    borderRadius: 8,
    marginBottom: 12,
    overflow: 'hidden',
  },
  timelineFill: (color, leftPct, widthPct) => ({
    position: 'absolute',
    top: 0,
    bottom: 0,
    left: `${leftPct}%`,
    width: `${widthPct}%`,
    background: color,
    borderRadius: 8,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: '#fff',
    fontSize: 11,
    fontWeight: 600,
    overflow: 'hidden',
    whiteSpace: 'nowrap',
    minWidth: 20,
  }),
  timelineMonths: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: 11,
    color: '#999',
    paddingTop: 4,
  },
  timelineLegend: {
    display: 'flex',
    gap: 16,
    flexWrap: 'wrap',
    marginTop: 12,
    fontSize: 13,
  },
  legendItem: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
  },
  legendDot: (color) => ({
    width: 12,
    height: 12,
    borderRadius: 3,
    background: color,
  }),
  infoGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
    gap: 14,
  },
  infoCard: {
    background: '#fff',
    border: '1px solid #e5e7eb',
    borderRadius: 10,
    padding: 16,
  },
  infoLabel: {
    fontSize: 11,
    fontWeight: 600,
    color: '#999',
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
    marginBottom: 4,
  },
  infoValue: {
    fontSize: 15,
    color: '#333',
    fontWeight: 500,
  },
  notesCard: {
    background: 'var(--brand-pale)',
    borderRadius: 10,
    padding: 18,
    border: '1px solid var(--brand-light-green)',
    lineHeight: 1.7,
    fontSize: 14,
    color: '#22242a',
  },
  companionGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: 14,
  },
  companionCard: (good) => ({
    background: good ? 'var(--brand-pale)' : '#fef2f2',
    borderRadius: 10,
    padding: 16,
    border: `1px solid ${good ? '#86efac' : '#fca5a5'}`,
  }),
  companionTitle: (good) => ({
    fontWeight: 700,
    fontSize: 14,
    color: good ? '#16a34a' : '#dc2626',
    marginBottom: 6,
  }),
  companionList: {
    fontSize: 14,
    color: '#333',
    lineHeight: 1.6,
  },
  tipsList: {
    paddingLeft: 20,
    lineHeight: 1.8,
    fontSize: 14,
    color: '#333',
  },
  linkRow: {
    display: 'flex',
    gap: 12,
    flexWrap: 'wrap',
    marginTop: 20,
  },
  actionLink: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    padding: '10px 20px',
    background: '#22242a',
    color: '#fff',
    borderRadius: 8,
    textDecoration: 'none',
    fontWeight: 600,
    fontSize: 14,
  },
  secondaryLink: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    padding: '10px 20px',
    background: '#fff',
    color: 'var(--brand-secondary)',
    border: '2px solid var(--brand-secondary)',
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
  notFound: {
    textAlign: 'center',
    padding: 60,
    color: '#999',
  },
};

// Timeline month labels, in the page's language ("Jan" / "ene").
const MONTH_INDEXES = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11];
const monthName = (i) => formatDate(new Date(2025, i, 1), { month: 'short' });
// The fixed Omaha reference dates below, e.g. "April 25" / "25 de abril".
const longDay = (month, day) => formatDate(new Date(2025, month, day), { month: 'long', day: 'numeric' });

export default function PlantingGuideDetail() {
  const { t, i18n } = useTranslation();
  const { category } = useParams();
  const [guide, setGuide] = useState(null);
  const [calendarEntry, setCalendarEntry] = useState(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  const decodedCategory = decodeURIComponent(category);

  useEffect(() => {
    Promise.all([
      plantingAPI.guideCategory(decodedCategory),
      plantingAPI.calendar(),
    ])
      .then(([guideRes, calRes]) => {
        setGuide(guideRes.data);
        // /planting/calendar answers { location, categories }, not a bare
        // array; calling .find on the object threw, and the timeline was empty.
        const cats = calRes.data?.categories || (Array.isArray(calRes.data) ? calRes.data : []);
        const entry = cats.find(c => c.category === decodedCategory);
        setCalendarEntry(entry || null);
      })
      .catch(err => {
        if (err.response?.status === 404) {
          setNotFound(true);
        } else {
          console.error('Failed to load guide:', err);
        }
      })
      .finally(() => setLoading(false));
  }, [decodedCategory]);

  if (loading) return <div style={styles.loading}>{t('cropGuide.loading')}</div>;
  if (notFound || !guide) {
    return (
      <div style={styles.page}>
        <div style={styles.notFound}>
          <h2>{t('cropGuide.notFoundTitle')}</h2>
          <p>{t('cropGuide.notFoundBody', { crop: cropLabel(t, decodedCategory) })}</p>
          <Link to="/planting-calendar" style={styles.actionLink}>
            {t('cropGuide.backToCalendarShort')}
          </Link>
        </div>
      </div>
    );
  }

  // Build timeline activities
  const activities = calendarEntry?.activities || [];
  const crop = cropLabel(t, guide.category);

  return (
    <div style={styles.page}>
      {/* Mirrors app/seo.py's /planting-guide/<crop> branch — keep in sync. */}
      <Seo
        title={t('cropGuide.seoTitle', { crop })}
        path={`/planting-guide/${encodeURIComponent(category)}`}
        description={t('cropGuide.seoDescription', { crop: crop.toLowerCase() })}
      />
      <Link to="/planting-calendar" style={styles.backLink}>
        <i className="bi bi-arrow-left"></i> {t('plantingCalendar.backToCalendar')}
      </Link>

      <div style={styles.header}>
        <h1 style={styles.title}>
          {crop}
          <span style={styles.zoneBadge}>{t('cropGuide.zone', { zone: guide.zone })}</span>
          <span style={styles.frostBadge(guide.frost_sensitive)}>
            {guide.frost_sensitive ? t('cropGuide.frostSensitive') : t('cropGuide.frostTolerant')}
          </span>
        </h1>
        <p style={styles.subtitle}>
          {t('cropGuide.subtitle')}
        </p>
      </div>

      {/* Visual Timeline */}
      <div style={styles.section}>
        <div style={styles.sectionTitle}>
          <i className="bi bi-calendar-range me-2"></i>
          {t('cropGuide.timeline')}
        </div>
        <div style={styles.timelineContainer}>
          {activities.map((act, i) => {
            const leftPct = ((act.start_doy - 1) / 365) * 100;
            const widthPct = ((act.end_doy - act.start_doy + 1) / 365) * 100;
            const color = ACTIVITY_COLORS[act.type] || '#999';
            return (
              <div key={i}>
                <div style={{ fontSize: 12, fontWeight: 600, color, marginBottom: 4 }}>
                  {ACTIVITY_LABEL_KEYS[act.type] ? t(ACTIVITY_LABEL_KEYS[act.type]) : act.label}
                  <span style={{ fontWeight: 400, color: '#888', marginLeft: 8 }}>
                    {doyToLabel(act.start_doy)} - {doyToLabel(act.end_doy)}
                  </span>
                </div>
                <div style={styles.timelineBar}>
                  <div style={styles.timelineFill(color, leftPct, widthPct)}>
                    {widthPct > 8 ? (ACTIVITY_SHORT_KEYS[act.type] ? t(ACTIVITY_SHORT_KEYS[act.type]) : (act.label || '')) : ''}
                  </div>
                </div>
              </div>
            );
          })}
          <div style={styles.timelineMonths}>
            {MONTH_INDEXES.map(i => <span key={i}>{monthName(i)}</span>)}
          </div>
          <div style={styles.timelineLegend}>
            {Object.entries(ACTIVITY_COLORS).map(([key, color]) => (
              <div key={key} style={styles.legendItem}>
                <div style={styles.legendDot(color)}></div>
                <span>{t(ACTIVITY_LABEL_KEYS[key])}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Key Dates */}
      <div style={styles.section}>
        <div style={styles.sectionTitle}>
          <i className="bi bi-calendar-event me-2"></i>
          {t('cropGuide.keyDates')}
        </div>
        <div style={styles.infoGrid}>
          {guide.seed_indoor_start_doy && (
            <div style={styles.infoCard}>
              <div style={styles.infoLabel}>{t('cropGuide.startSeedsIndoors')}</div>
              <div style={styles.infoValue}>
                {doyToLabel(guide.seed_indoor_start_doy)}
              </div>
            </div>
          )}
          {guide.direct_sow_start_doy && (
            <div style={styles.infoCard}>
              <div style={styles.infoLabel}>{t('plantingCalendar.directSowWindow')}</div>
              <div style={styles.infoValue}>
                {doyToLabel(guide.direct_sow_start_doy)} - {doyToLabel(guide.direct_sow_end_doy)}
              </div>
            </div>
          )}
          {guide.transplant_start_doy && (
            <div style={styles.infoCard}>
              <div style={styles.infoLabel}>{t('plantingCalendar.transplantWindow')}</div>
              <div style={styles.infoValue}>
                {doyToLabel(guide.transplant_start_doy)} - {doyToLabel(guide.transplant_end_doy)}
              </div>
            </div>
          )}
          <div style={styles.infoCard}>
            <div style={styles.infoLabel}>{t('plantingCalendar.daysToHarvest')}</div>
            <div style={styles.infoValue}>
              {t('plantingCalendar.daysRange', { min: guide.days_to_harvest_min, max: guide.days_to_harvest_max })}
            </div>
          </div>
          {guide.succession_interval_days && (
            <div style={styles.infoCard}>
              <div style={styles.infoLabel}>{t('plantingCalendar.successionPlanting')}</div>
              <div style={styles.infoValue}>
                {t('cropGuide.successionEvery', { count: guide.succession_interval_days })}
              </div>
            </div>
          )}
          <div style={styles.infoCard}>
            <div style={styles.infoLabel}>{t('cropGuide.frostSensitivity')}</div>
            <div style={styles.infoValue}>
              {guide.frost_sensitive
                ? t('cropGuide.frostSensitiveDetail')
                : t('cropGuide.coldTolerantDetail')}
            </div>
          </div>
        </div>
      </div>

      {/* Omaha Growing Tips */}
      {guide.notes && (
        <div style={styles.section}>
          <div style={styles.sectionTitle}>
            <i className="bi bi-lightbulb me-2"></i>
            {t('plantingCalendar.omahaTips')}
          </div>
          <div style={styles.notesCard}>
            {cropProse(i18n.language, guide, 'notes')}
          </div>
        </div>
      )}

      {/* Companion Planting */}
      <div style={styles.section}>
        <div style={styles.sectionTitle}>
          <i className="bi bi-flower2 me-2"></i>
          {t('cropGuide.companionPlanting')}
        </div>
        <div style={styles.companionGrid}>
          <div style={styles.companionCard(true)}>
            <div style={styles.companionTitle(true)}>
              <i className="bi bi-check-circle me-1"></i>
              {t('cropGuide.goodCompanions')}
            </div>
            <div style={styles.companionList}>
              {cropProse(i18n.language, guide, 'companion_plants') || t('cropGuide.noCompanions')}
            </div>
          </div>
          <div style={styles.companionCard(false)}>
            <div style={styles.companionTitle(false)}>
              <i className="bi bi-x-circle me-1"></i>
              {t('plantingCalendar.avoidNear')}
            </div>
            <div style={styles.companionList}>
              {cropProse(i18n.language, guide, 'avoid_near') || t('cropGuide.noConflicts')}
            </div>
          </div>
        </div>
      </div>

      {/* Quick Reference for Omaha */}
      <div style={styles.section}>
        <div style={styles.sectionTitle}>
          <i className="bi bi-geo-alt me-2"></i>
          {t('cropGuide.quickReference')}
        </div>
        <div style={styles.infoGrid}>
          <div style={styles.infoCard}>
            <div style={styles.infoLabel}>{t('cropGuide.lastSpringFrost')}</div>
            <div style={styles.infoValue}>~{longDay(3, 25)}</div>
          </div>
          <div style={styles.infoCard}>
            <div style={styles.infoLabel}>{t('cropGuide.firstFallFrost')}</div>
            <div style={styles.infoValue}>~{longDay(9, 10)}</div>
          </div>
          <div style={styles.infoCard}>
            <div style={styles.infoLabel}>{t('cropGuide.growingSeason')}</div>
            <div style={styles.infoValue}>{t('cropGuide.approxDays', { count: 168 })}</div>
          </div>
          <div style={styles.infoCard}>
            <div style={styles.infoLabel}>{t('cropGuide.usdaZone')}</div>
            <div style={styles.infoValue}>{t('cropGuide.usdaZoneValue')}</div>
          </div>
        </div>
      </div>

      {/* Action Links */}
      <div style={styles.linkRow}>
        <Link
          to="/gardens"
          style={styles.actionLink}
        >
          <i className="bi bi-tree"></i>
          {t('cropGuide.findGarden')}
        </Link>
        <Link to="/my-planting-log" style={styles.secondaryLink}>
          <i className="bi bi-journal-plus"></i>
          {t('cropGuide.logPlanting')}
        </Link>
        <Link to="/harvest-forecast" style={styles.secondaryLink}>
          <i className="bi bi-graph-up-arrow"></i>
          {t('garden.harvestForecast')}
        </Link>
      </div>

      <div style={{ height: 40 }}></div>
    </div>
  );
}

function doyToLabel(doy) {
  if (!doy) return '';
  const d = new Date(2025, 0, 1);
  d.setDate(d.getDate() + doy - 1);
  return formatDate(d, DAY_MONTH);
}
