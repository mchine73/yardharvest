import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { gardensAPI } from '../../api';

const CATEGORY_COLORS = [
  '#1d8a5f', '#2aa873', '#52b788', '#7fd4ab', '#7fd4ab',
  '#3f7ddb', '#8b5cf6', '#d99a2b', '#ef4444', '#06b6d4',
];

const DEST_STYLES = {
  personal: { bg: '#f3f4f6', color: '#374151', icon: 'bi-house', label: 'Personal Use' },
  shared: { bg: '#dbeafe', color: '#1e40af', icon: 'bi-people', label: 'Shared with Neighbors' },
  food_bank: { bg: '#fef3c7', color: '#92400e', icon: 'bi-heart', label: 'Food Bank Donations' },
  marketplace: { bg: '#ecf7f1', color: '#166534', icon: 'bi-shop', label: 'YardHarvest Marketplace' },
};

export default function GardenImpact() {
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

  if (loading) return <div className="text-center py-5"><div className="spinner-border" style={{ color: '#1d8a5f' }}></div></div>;
  if (!garden || !impact) return <div className="text-center py-5"><p>Garden not found</p></div>;

  const maxCategoryLbs = impact.category_breakdown.length > 0
    ? Math.max(...impact.category_breakdown.map(c => c.lbs))
    : 0;

  const maxMonthlyLbs = impact.monthly_trend.length > 0
    ? Math.max(...impact.monthly_trend.map(m => m.lbs))
    : 0;

  return (
    <div>
      <Link to={`/gardens/${id}`} style={{ color: '#1d8a5f', textDecoration: 'none', fontSize: '0.9rem' }}>
        <i className="bi bi-arrow-left me-1"></i> Back to {garden.name}
      </Link>

      <h2 className="fw-bold mt-3 mb-2" style={{ color: '#1d8a5f' }}>
        <i className="bi bi-bar-chart me-2"></i>Impact Dashboard
      </h2>
      <p className="text-muted mb-4">{garden.name} - Community Impact at a Glance</p>

      {/* Hero Stats */}
      <div className="row g-3 mb-4">
        {[
          { label: 'Total Produce Harvested', value: `${Math.round(impact.total_harvest_lbs)}`, unit: 'lbs', icon: 'bi-basket2', color: '#1d8a5f', bgColor: '#ecf7f1' },
          { label: 'Food Bank Donations', value: `${Math.round(impact.food_bank_lbs)}`, unit: 'lbs', icon: 'bi-heart-fill', color: '#e0564f', bgColor: '#fee2e2' },
          { label: 'CO2 Emissions Saved', value: `${Math.round(impact.co2_saved_lbs)}`, unit: 'lbs', icon: 'bi-cloud-sun', color: '#3f7ddb', bgColor: '#dbeafe' },
          { label: 'Active Gardeners', value: impact.active_gardeners, unit: '', icon: 'bi-people-fill', color: '#8b5cf6', bgColor: '#ede9fe' },
          { label: 'Community Events', value: impact.total_events, unit: '', icon: 'bi-calendar-check-fill', color: '#d99a2b', bgColor: '#fef3c7' },
          { label: 'Volunteer Hours', value: impact.volunteer_hours, unit: 'hrs', icon: 'bi-clock-fill', color: '#2aa873', bgColor: '#ecf7f1' },
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
                <i className="bi bi-bar-chart-fill me-2" style={{ color: '#1d8a5f' }}></i>
                Harvest by Category
              </h5>
              {impact.category_breakdown.length === 0 ? (
                <p className="text-muted text-center py-4">No harvest data yet</p>
              ) : (
                impact.category_breakdown
                  .sort((a, b) => b.lbs - a.lbs)
                  .map((cat, i) => {
                    const pct = maxCategoryLbs > 0 ? (cat.lbs / maxCategoryLbs) * 100 : 0;
                    return (
                      <div key={i} className="mb-3">
                        <div className="d-flex justify-content-between mb-1">
                          <span className="fw-semibold" style={{ textTransform: 'capitalize', fontSize: '0.9rem' }}>
                            {cat.category?.replace('_', ' ')}
                          </span>
                          <span className="fw-bold" style={{ color: CATEGORY_COLORS[i % CATEGORY_COLORS.length] }}>
                            {cat.lbs.toFixed(1)} lbs
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
                            {pct > 20 && <span style={{ color: 'white', fontSize: '0.75rem', fontWeight: 600 }}>{cat.lbs.toFixed(1)}</span>}
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
                <i className="bi bi-pie-chart-fill me-2" style={{ color: '#1d8a5f' }}></i>
                Where Produce Goes
              </h5>
              {impact.destination_breakdown.length === 0 ? (
                <p className="text-muted text-center py-4">No distribution data yet</p>
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
                            {Math.round(dest.lbs)}
                          </div>
                          <div style={{ fontSize: '0.85rem', color: style.color }}>pounds ({pct}%)</div>
                          <div style={{ fontSize: '0.8rem', color: '#6b7280', marginTop: '4px' }}>{style.label}</div>
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
                <i className="bi bi-graph-up me-2" style={{ color: '#1d8a5f' }}></i>
                Monthly Harvest Trend
              </h5>
              {impact.monthly_trend.length === 0 ? (
                <p className="text-muted text-center py-4">No monthly data yet</p>
              ) : (
                <div style={{ display: 'flex', alignItems: 'flex-end', gap: '8px', height: '200px', padding: '0 8px' }}>
                  {impact.monthly_trend.map((month, i) => {
                    const pct = maxMonthlyLbs > 0 ? (month.lbs / maxMonthlyLbs) * 100 : 0;
                    const [year, mon] = month.month.split('-');
                    const monthLabel = new Date(parseInt(year), parseInt(mon) - 1).toLocaleString('en-US', { month: 'short' });
                    return (
                      <div key={i} style={{ flex: 1, textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'flex-end', height: '100%' }}>
                        <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#1d8a5f', marginBottom: '4px' }}>
                          {month.lbs.toFixed(1)}
                        </div>
                        <div style={{
                          width: '100%',
                          maxWidth: '48px',
                          height: `${Math.max(pct, 5)}%`,
                          backgroundColor: '#2aa873',
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
        border: '2px solid #7fd4ab',
        borderRadius: '16px',
        backgroundColor: '#ecf7f1',
      }}>
        <div className="card-body p-4 text-center">
          <h5 className="fw-bold mb-3" style={{ color: '#1d8a5f' }}>
            <i className="bi bi-trophy me-2"></i>Community Impact Summary
          </h5>
          <p style={{ fontSize: '1.1rem', maxWidth: '600px', margin: '0 auto' }}>
            <strong>{garden.name}</strong> has produced <strong>{Math.round(impact.total_harvest_lbs)} lbs</strong> of fresh produce,
            donated <strong>{Math.round(impact.food_bank_lbs)} lbs</strong> to food banks,
            saved an estimated <strong>{Math.round(impact.co2_saved_lbs)} lbs of CO2</strong>,
            and brought together <strong>{impact.active_gardeners} gardeners</strong> through{' '}
            <strong>{impact.total_events} community events</strong> totaling{' '}
            <strong>{impact.volunteer_hours} volunteer hours</strong>.
          </p>
        </div>
      </div>
    </div>
  );
}
