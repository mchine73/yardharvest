import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useTranslation, Trans } from 'react-i18next';
import { gardensAPI } from '../../api';
import { formatDate, currentLocale } from '../../i18n/dates';

const CATEGORY_COLORS = [
  'var(--brand-secondary)', 'var(--brand-accent)', '#52b788', 'var(--brand-light-green)', 'var(--brand-light-green)',
  '#3f7ddb', '#8b5cf6', 'var(--brand-gold)', '#ef4444', '#06b6d4',
];

// Module scope cannot call t(): labelKey is translated at the render site.
const DEST_STYLES = {
  personal: { bg: '#f3f4f6', color: '#374151', icon: 'bi-house', labelKey: 'impact.destPersonal' },
  shared: { bg: '#dbeafe', color: '#1e40af', icon: 'bi-people', labelKey: 'impact.destShared' },
  food_bank: { bg: '#fef3c7', color: '#92400e', icon: 'bi-heart', labelKey: 'impact.foodBankDonations' },
  marketplace: { bg: 'var(--brand-pale)', color: '#166534', icon: 'bi-shop', labelKey: 'impact.destMarketplace' },
};

// Harvest category slugs, labelled as the harvest form labels them. The
// server sends 'Uncategorized' for a harvest logged without one.
const HARVEST_CATEGORY_KEYS = {
  tomatoes: 'garden.catTomatoes', peppers: 'garden.catPeppers',
  greens: 'garden.catGreens', herbs: 'garden.catHerbs',
  squash: 'garden.catSquash', beans: 'garden.catBeans',
  root_vegetables: 'garden.catRootVegetables', corn: 'garden.catCorn',
  berries: 'garden.catBerries', other: 'garden.catOther',
  Uncategorized: 'impact.uncategorized',
};

// Numbers in the page's language ("1,234.5" / "1234,5").
const fmtInt = (v) => Math.round(Number(v) || 0).toLocaleString(currentLocale());
const fmtOne = (v) => (Number(v) || 0).toLocaleString(currentLocale(),
  { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const fmtNum = (v) => (Number(v) || 0).toLocaleString(currentLocale(), { maximumFractionDigits: 1 });

export default function GardenImpact() {
  const { t } = useTranslation();
  const { id } = useParams();
  const [garden, setGarden] = useState(null);
  const [impact, setImpact] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      gardensAPI.detail(id),
      gardensAPI.impact(id),
    ]).then(([gardenRes, impactRes]) => {
      setGarden(gardenRes.data);
      setImpact(impactRes.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [id]);

  if (loading) return <div className="text-center py-5"><div className="spinner-border" style={{ color: 'var(--brand-secondary)' }}></div></div>;
  if (!garden || !impact) return <div className="text-center py-5"><p>{t('garden.notFound')}</p></div>;

  const maxCategoryLbs = impact.category_breakdown.length > 0
    ? Math.max(...impact.category_breakdown.map(c => c.lbs))
    : 0;

  const maxMonthlyLbs = impact.monthly_trend.length > 0
    ? Math.max(...impact.monthly_trend.map(m => m.lbs))
    : 0;

  const categoryLabel = (slug) => (HARVEST_CATEGORY_KEYS[slug]
    ? t(HARVEST_CATEGORY_KEYS[slug])
    : String(slug || '').replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase()));

  return (
    <div>
      <Link to={`/gardens/${id}`} style={{ color: 'var(--brand-secondary)', textDecoration: 'none', fontSize: '0.9rem' }}>
        <i className="bi bi-arrow-left me-1"></i> {t('garden.backToGarden', { name: garden.name })}
      </Link>

      <h2 className="fw-bold mt-3 mb-2" style={{ color: 'var(--brand-secondary)' }}>
        <i className="bi bi-bar-chart me-2"></i>{t('impact.title')}
      </h2>
      <p className="text-muted mb-4">{t('impact.subtitle', { name: garden.name })}</p>

      {/* Hero Stats */}
      <div className="row g-3 mb-4">
        {[
          { label: t('impact.statTotalProduce'), value: fmtInt(impact.total_harvest_lbs), unit: t('impact.unitLbs'), icon: 'bi-basket2', color: 'var(--brand-secondary)', bgColor: 'var(--brand-pale)' },
          { label: t('impact.foodBankDonations'), value: fmtInt(impact.food_bank_lbs), unit: t('impact.unitLbs'), icon: 'bi-heart-fill', color: '#e0564f', bgColor: '#fee2e2' },
          { label: t('impact.statCo2'), value: fmtInt(impact.co2_saved_lbs), unit: t('impact.unitLbs'), icon: 'bi-cloud-sun', color: '#3f7ddb', bgColor: '#dbeafe' },
          { label: t('impact.statGardeners'), value: fmtInt(impact.active_gardeners), unit: '', icon: 'bi-people-fill', color: '#8b5cf6', bgColor: '#ede9fe' },
          { label: t('impact.statEvents'), value: fmtInt(impact.total_events), unit: '', icon: 'bi-calendar-check-fill', color: 'var(--brand-gold)', bgColor: '#fef3c7' },
          { label: t('impact.statVolunteerHours'), value: fmtNum(impact.volunteer_hours), unit: t('impact.unitHrs'), icon: 'bi-clock-fill', color: 'var(--brand-accent)', bgColor: 'var(--brand-pale)' },
        ].map((stat, i) => (
          <div key={i} className="col-6 col-md-4 col-lg-2">
            <div style={{
              textAlign: 'center',
              padding: '24px 12px',
              backgroundColor: stat.bgColor,
              borderRadius: '16px',
              height: '100%',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
            }}>
              <i className={`bi ${stat.icon}`} style={{ fontSize: '2rem', color: stat.color }}></i>
              <div style={{ fontSize: '2rem', fontWeight: 'bold', color: stat.color, lineHeight: 1.2, marginTop: '8px' }}>
                {stat.value}
              </div>
              {stat.unit && <div style={{ fontSize: '0.85rem', color: stat.color, opacity: 0.8 }}>{stat.unit}</div>}
              <div style={{ fontSize: '0.75rem', color: '#6b7280', marginTop: '4px' }}>{stat.label}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="row g-4">
        {/* Harvest by Category */}
        <div className="col-md-6">
          <div className="card h-100" style={{ border: 'none', boxShadow: '0 2px 12px rgba(0,0,0,0.06)', borderRadius: '16px' }}>
            <div className="card-body p-4">
              <h5 className="fw-bold mb-4">
                <i className="bi bi-bar-chart-fill me-2" style={{ color: 'var(--brand-secondary)' }}></i>
                {t('impact.byCategory')}
              </h5>
              {impact.category_breakdown.length === 0 ? (
                <p className="text-muted text-center py-4">{t('impact.noHarvestData')}</p>
              ) : (
                impact.category_breakdown
                  .sort((a, b) => b.lbs - a.lbs)
                  .map((cat, i) => {
                    const pct = maxCategoryLbs > 0 ? (cat.lbs / maxCategoryLbs) * 100 : 0;
                    return (
                      <div key={i} className="mb-3">
                        <div className="d-flex justify-content-between mb-1">
                          <span className="fw-semibold" style={{ fontSize: '0.9rem' }}>
                            {categoryLabel(cat.category)}
                          </span>
                          <span className="fw-bold" style={{ color: CATEGORY_COLORS[i % CATEGORY_COLORS.length] }}>
                            {t('impact.lbsValue', { value: fmtOne(cat.lbs) })}
                          </span>
                        </div>
                        <div style={{ backgroundColor: '#e5e7eb', borderRadius: '6px', height: '24px', overflow: 'hidden' }}>
                          <div style={{
                            width: `${pct}%`,
                            backgroundColor: CATEGORY_COLORS[i % CATEGORY_COLORS.length],
                            borderRadius: '6px',
                            height: '100%',
                            transition: 'width 0.8s ease',
                            display: 'flex',
                            alignItems: 'center',
                            paddingLeft: '8px',
                          }}>
                            {pct > 20 && <span style={{ color: 'white', fontSize: '0.75rem', fontWeight: 600 }}>{fmtOne(cat.lbs)}</span>}
                          </div>
                        </div>
                      </div>
                    );
                  })
              )}
            </div>
          </div>
        </div>

        {/* Where Produce Goes */}
        <div className="col-md-6">
          <div className="card h-100" style={{ border: 'none', boxShadow: '0 2px 12px rgba(0,0,0,0.06)', borderRadius: '16px' }}>
            <div className="card-body p-4">
              <h5 className="fw-bold mb-4">
                <i className="bi bi-pie-chart-fill me-2" style={{ color: 'var(--brand-secondary)' }}></i>
                {t('impact.whereProduceGoes')}
              </h5>
              {impact.destination_breakdown.length === 0 ? (
                <p className="text-muted text-center py-4">{t('impact.noDistributionData')}</p>
              ) : (
                <div className="row g-3">
                  {impact.destination_breakdown.map((dest, i) => {
                    const style = DEST_STYLES[dest.destination] || DEST_STYLES.personal;
                    const totalLbs = impact.total_harvest_lbs || 1;
                    const pct = ((dest.lbs / totalLbs) * 100).toFixed(0);
                    return (
                      <div key={i} className="col-6">
                        <div style={{
                          backgroundColor: style.bg,
                          borderRadius: '12px',
                          padding: '20px',
                          textAlign: 'center',
                          height: '100%',
                        }}>
                          <i className={`bi ${style.icon}`} style={{ fontSize: '2rem', color: style.color }}></i>
                          <div style={{ fontSize: '1.8rem', fontWeight: 'bold', color: style.color, marginTop: '8px' }}>
                            {fmtInt(dest.lbs)}
                          </div>
                          <div style={{ fontSize: '0.85rem', color: style.color }}>{t('impact.poundsPct', { count: Math.round(dest.lbs), pct })}</div>
                          <div style={{ fontSize: '0.8rem', color: '#6b7280', marginTop: '4px' }}>{t(style.labelKey)}</div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Monthly Harvest Trend */}
        <div className="col-12">
          <div className="card" style={{ border: 'none', boxShadow: '0 2px 12px rgba(0,0,0,0.06)', borderRadius: '16px' }}>
            <div className="card-body p-4">
              <h5 className="fw-bold mb-4">
                <i className="bi bi-graph-up me-2" style={{ color: 'var(--brand-secondary)' }}></i>
                {t('impact.monthlyTrend')}
              </h5>
              {impact.monthly_trend.length === 0 ? (
                <p className="text-muted text-center py-4">{t('impact.noMonthlyData')}</p>
              ) : (
                <div style={{ display: 'flex', alignItems: 'flex-end', gap: '8px', height: '200px', padding: '0 8px' }}>
                  {impact.monthly_trend.map((month, i) => {
                    const pct = maxMonthlyLbs > 0 ? (month.lbs / maxMonthlyLbs) * 100 : 0;
                    const [year, mon] = month.month.split('-');
                    const monthLabel = formatDate(new Date(parseInt(year), parseInt(mon) - 1), { month: 'short' });
                    return (
                      <div key={i} style={{ flex: 1, textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'flex-end', height: '100%' }}>
                        <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--brand-secondary)', marginBottom: '4px' }}>
                          {fmtOne(month.lbs)}
                        </div>
                        <div style={{
                          width: '100%',
                          maxWidth: '48px',
                          height: `${Math.max(pct, 5)}%`,
                          backgroundColor: 'var(--brand-accent)',
                          borderRadius: '6px 6px 0 0',
                          transition: 'height 0.8s ease',
                          minHeight: '8px',
                        }}></div>
                        <div style={{ fontSize: '0.7rem', color: '#6b7280', marginTop: '4px' }}>
                          {monthLabel}
                        </div>
                        <div style={{ fontSize: '0.65rem', color: '#9ca3af' }}>{year}</div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Summary Box */}
      <div className="card mt-4" style={{
        border: '2px solid var(--brand-light-green)',
        borderRadius: '16px',
        backgroundColor: 'var(--brand-pale)',
      }}>
        <div className="card-body p-4 text-center">
          <h5 className="fw-bold mb-3" style={{ color: 'var(--brand-secondary)' }}>
            <i className="bi bi-trophy me-2"></i>{t('impact.summaryTitle')}
          </h5>
          <p style={{ fontSize: '1.1rem', maxWidth: '600px', margin: '0 auto' }}>
            {/* The garden name is a component, not a value, so user text never
                goes through the <tag> parser. Each counted phrase is
                pluralised on its own so Spanish can reorder the sentence. */}
            <Trans
              i18nKey="impact.summary"
              values={{
                total: fmtInt(impact.total_harvest_lbs),
                foodBank: fmtInt(impact.food_bank_lbs),
                co2: fmtInt(impact.co2_saved_lbs),
                gardeners: t('impact.summaryGardeners', { count: impact.active_gardeners, value: fmtInt(impact.active_gardeners) }),
                events: t('impact.summaryEvents', { count: impact.total_events, value: fmtInt(impact.total_events) }),
                hours: t('impact.summaryHours', { count: impact.volunteer_hours, value: fmtNum(impact.volunteer_hours) }),
              }}
              components={{ name: <strong>{garden.name}</strong>, b: <strong /> }}
            />
          </p>
        </div>
      </div>
    </div>
  );
}
