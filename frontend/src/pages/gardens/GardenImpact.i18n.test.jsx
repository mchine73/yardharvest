// The public impact page, in both languages. Besides the usual "no English
// left on the Spanish page" sweep, it pins the two things a reviewer cannot
// see in the catalog:
//   * the summary sentence is one <Trans> whose garden name is a component,
//     so a name containing markup characters renders literally;
//   * the counted phrases pluralise ("1 gardener", "1 hortelano").
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

import GardenImpact from './GardenImpact';
import i18n from '../../i18n';

const NAME = 'Huerto <Sur> & Co';

vi.mock('../../api', () => ({
  gardensAPI: {
    detail: vi.fn().mockResolvedValue({ data: { id: 7, name: 'Huerto <Sur> & Co' } }),
    impact: vi.fn().mockResolvedValue({
      data: {
        total_harvest_lbs: 1234.4, food_bank_lbs: 200, shared_lbs: 100, co2_saved_lbs: 600,
        active_gardeners: 1, total_events: 3, volunteer_hours: 12.5,
        category_breakdown: [
          { category: 'tomatoes', lbs: 500.25 },
          { category: 'root_vegetables', lbs: 100 },
          { category: 'Uncategorized', lbs: 5 },
        ],
        monthly_trend: [{ month: '2026-09', lbs: 300.5 }],
        destination_breakdown: [
          { destination: 'food_bank', lbs: 200 },
          { destination: 'personal', lbs: 1 },
        ],
      },
    }),
  },
}));

async function draw(lang) {
  await i18n.changeLanguage(lang);
  const utils = render(
    <MemoryRouter initialEntries={['/gardens/7/impact']}>
      <Routes><Route path="/gardens/:id/impact" element={<GardenImpact />} /></Routes>
    </MemoryRouter>,
  );
  await screen.findByText(lang === 'es' ? 'Panel de impacto' : 'Impact Dashboard', { exact: false });
  return utils;
}

// English catalog values that still appear, as whole words, on a page.
// Values with placeholders or markup cannot appear verbatim and are skipped,
// as are values the Spanish legitimately contains.
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

describe('GardenImpact i18n', () => {
  it('renders English', async () => {
    const { container } = await draw('en');
    const text = container.textContent;
    for (const s of ['Harvest by Category', 'Root Vegetables', 'Uncategorized',
      'Food Bank Donations', 'pound (0%)', 'Sep']) {
      expect(text).toContain(s);
    }
    expect(text).toContain(`${NAME} has produced 1,234 lbs of fresh produce`);
    expect(text).toContain('brought together 1 gardener through 3 community events totaling 12.5 volunteer hours.');
  });

  it('renders Spanish, with no English label left over', async () => {
    const { container } = await draw('es');
    const text = container.textContent;
    for (const s of ['Cosecha por categoría', 'Jitomates', 'Raíces y tubérculos', 'Sin categoría',
      'Donaciones a bancos de alimentos', 'libra (0%)', 'Volver a', 'sept']) {
      expect(text).toContain(s);
    }
    expect(text).toContain(`${NAME} ha producido`);
    expect(text).toContain('1 hortelano');
    expect(text).toContain('3 eventos comunitarios');
    expect(text).toContain('12.5 horas de voluntariado');
    expect(survivors('impact', text)).toEqual([]);
    expect(text).not.toMatch(/\b(impact|garden)\.[a-zA-Z]/);
    expect(text).not.toContain('{{');
  });

  it('renders the garden name literally and in bold', async () => {
    const { container } = await draw('es');
    const bold = [...container.querySelectorAll('strong')].map((b) => b.textContent);
    expect(bold).toContain(NAME);
  });
});
