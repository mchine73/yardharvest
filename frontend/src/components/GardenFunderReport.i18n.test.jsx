// The printable funder report, in both languages. It is the page with the
// most numbers per sentence, so the test pins the sentences rather than the
// labels: each counted phrase must agree with its own number ("1 volunteer
// worked 12.5 logged hours across 1 organized shift"), and the hours phrase is
// a nested <Trans> that must keep its bold number.
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import GardenFunderReport from './GardenFunderReport';
import i18n from '../i18n';

vi.mock('../api', () => ({
  gardenAdminAPI: {
    funderReport: vi.fn().mockResolvedValue({
      data: {
        garden: { name: 'Test Garden', city: 'Omaha', state: 'NE' },
        period: { start: '2026-01-01', end: '2026-10-31' },
        harvest: {
          total_lbs: 1500.5,
          by_category: [{ category: 'tomatoes', lbs: 900 }, { category: 'Uncategorized', lbs: 10 }],
          by_destination: {}, food_bank_lbs: 300, shared_lbs: 150, gardeners: 1,
        },
        participation: { members_total: 24, members_new: 1, plots_total: 30, plots_assigned: 21, occupancy_pct: 70 },
        volunteering: { shifts_held: 1, volunteers: 1, hours: 12.5, value_usd: 418.63 },
        events: { held: 5, by_type: { workday: 3, harvest_day: 1, other: 1 }, rsvps_going: 1 },
        finance: {
          dues_expected: 1200, dues_collected: 1000, expenses_total: 250.5,
          expenses_by_category: { supplies: 200.5, water: 50 }, net: 749.5,
        },
        equivalents: { meals: 1, produce_value_usd: 4501.5, co2_saved_lbs: 900 },
        rates: { produce_rate: 3, volunteer_rate: 33.49, lbs_per_meal: 1.2, co2_per_lb: 2 },
      },
    }),
  },
}));

async function draw(lang) {
  await i18n.changeLanguage(lang);
  const utils = render(
    <MemoryRouter>
      <GardenFunderReport gardenId={7} garden={{ name: 'Test Garden' }} />
    </MemoryRouter>,
  );
  await screen.findByText(lang === 'es' ? 'Reporte de impacto y actividad' : 'Impact & Activity Report');
  return utils;
}

function survivors(section, text) {
  const en = i18n.getResourceBundle('en', 'common')[section];
  const es = i18n.getResourceBundle('es', 'common')[section];
  return Object.keys(en).filter((k) => {
    const v = en[k];
    if (/\{\{|</.test(v) || es[k].includes(v)) return false;
    const esc = v.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return new RegExp(`(^|[^\\p{L}])${esc}([^\\p{L}]|$)`, 'u').test(text);
  });
}

const squash = (s) => s.replace(/\s+/g, ' ');

describe('GardenFunderReport i18n', () => {
  it('renders English sentences that agree with their numbers', async () => {
    const { container } = await draw('en');
    const text = squash(container.textContent);
    expect(text).toContain('1 volunteer worked 12.5 logged hours across 1 organized shift');
    expect(text).toContain('(3 workdays, 1 harvest day, 1 other event)');
    expect(text).toContain('with 1 RSVP');
    expect(text).toContain('roughly 1 meal.');
    expect(text).toContain('1 gardener logged harvests');
    expect(text).toContain('24 members (1 joined during this period)');
    expect(text).toContain('Volunteer labor value: $418.63 at $33.49/hour');
    for (const s of ['Tomatoes', 'Uncategorized', 'Supplies', 'Water', 'Data recorded in YardHarvest by Test Garden.']) {
      expect(text).toContain(s);
    }
  });

  it('renders Spanish, with no English label left over', async () => {
    const { container } = await draw('es');
    const text = squash(container.textContent);
    expect(text).toContain('1 voluntario trabajó 12.5 horas registradas en 1 turno organizado');
    expect(text).toContain('(3 jornadas de trabajo, 1 día de cosecha, 1 evento de otro tipo)');
    expect(text).toContain('con 1 confirmación de asistencia');
    expect(text).toContain('aproximadamente 1 comida.');
    expect(text).toContain('1 hortelano registró cosechas');
    expect(text).toContain('Valor del trabajo voluntario: $418.63 a $33.49/hora');
    for (const s of ['Jitomates', 'Sin categoría', 'Insumos', 'Agua', 'Metodología', 'Total cosechado',
      'Generado el', 'de octubre de 2026']) {
      expect(text).toContain(s);
    }
    expect(survivors('funderReport', text)).toEqual([]);
    expect(text).not.toMatch(/\b(funderReport|impact|garden|dash)\.[a-zA-Z]/);
    expect(text).not.toContain('{{');
  });

  it('keeps the hours number bold inside the nested phrase', async () => {
    const { container } = await draw('es');
    const bold = [...container.querySelectorAll('li strong')].map((b) => b.textContent);
    expect(bold).toContain('12.5');
    expect(bold).toContain('1');
  });
});
