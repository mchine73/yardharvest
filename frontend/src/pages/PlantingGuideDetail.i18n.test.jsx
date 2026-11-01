// PlantingGuideDetail in both languages. Besides the usual no-English /
// no-raw-key checks, this pins the timeline: /planting/calendar answers
// { location, categories }, and the page used to call .find on that object,
// throw, and render the "Growing Timeline" section with no activities at all.
import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

import PlantingGuideDetail from './PlantingGuideDetail';
import i18n from '../i18n';

function englishSurvivors(container, section, serverContent = []) {
  const en = i18n.getResourceBundle('en', 'common')[section];
  const es = i18n.getResourceBundle('es', 'common')[section];
  const ATTRS = ['placeholder', 'alt', 'title', 'aria-label'];
  const attrs = [...container.querySelectorAll(ATTRS.map((a) => `[${a}]`).join(','))]
    .flatMap((el) => ATTRS.map((a) => el.getAttribute(a)).filter(Boolean));
  const texts = [];
  const walk = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
  while (walk.nextNode()) texts.push(walk.currentNode.nodeValue);
  let seen = [...texts, ...attrs].join('\n');
  for (const u of serverContent) seen = seen.split(u).join(' ');
  const escape = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return Object.keys(en).filter((k) => en[k] !== es[k]).filter((k) => {
    const body = en[k].replace(/<\/?\w+>/g, '').split(/\{\{\w+\}\}/).map(escape).join('.*?');
    return new RegExp(`(^|[^\\p{L}])${body}($|[^\\p{L}])`, 'u').test(seen);
  });
}

const NOTES = 'Direct sow when soil is 60F+. Plant in blocks for good pollination.';
const COMPANIONS = 'Beans, Squash, Peas, Cucumbers';
const AVOID = 'Tomatoes (corn earworm)';

vi.mock('../components/Seo', () => ({
  default: ({ title, description }) => (
    <div data-testid="seo" data-title={title} data-description={description} />
  ),
}));
vi.mock('../api', () => ({
  plantingAPI: {
    guideCategory: vi.fn(() => Promise.resolve({
      data: {
        id: 11, category: 'Corn', zone: '5b',
        seed_indoor_start_doy: null, direct_sow_start_doy: 130, direct_sow_end_doy: 160,
        transplant_start_doy: null, transplant_end_doy: null,
        days_to_harvest_min: 65, days_to_harvest_max: 90, succession_interval_days: 14,
        frost_sensitive: true, notes: NOTES, companion_plants: COMPANIONS, avoid_near: AVOID,
      },
    })),
    calendar: vi.fn(() => Promise.resolve({
      data: {
        location: { estimated: false, zone: '5b' },
        categories: [{
          category: 'Corn', frost_sensitive: true,
          activities: [
            { type: 'direct_sow', label: 'Direct Sow', start: { label: 'May 10' }, end: { label: 'Jun 09' }, start_doy: 130, end_doy: 160 },
            { type: 'harvest', label: 'Harvest', start: { label: 'Jul 14' }, end: { label: 'Sep 07' }, start_doy: 195, end_doy: 250 },
          ],
        }],
      },
    })),
  },
}));

const draw = () => render(
  <MemoryRouter initialEntries={['/planting-guide/Corn']}>
    <Routes><Route path="/planting-guide/:category" element={<PlantingGuideDetail />} /></Routes>
  </MemoryRouter>,
);

afterEach(async () => { await i18n.changeLanguage('en'); });

describe('PlantingGuideDetail', () => {
  it('renders English, a populated timeline, and the Seo copy app/seo.py serves', async () => {
    await i18n.changeLanguage('en');
    draw();
    expect(await screen.findByText('Corn')).toBeInTheDocument();
    // One heading per calendar activity: the timeline is no longer empty.
    expect((await screen.findAllByText('May 10 - Jun 9')).length).toBeGreaterThan(0);
    expect(screen.getByText('Jul 14 - Sep 7')).toBeInTheDocument();
    expect(screen.getByText('Every 14 days for continuous harvest')).toBeInTheDocument();
    expect(screen.getByText('~April 25')).toBeInTheDocument();
    const seo = screen.getByTestId('seo');
    expect(seo.dataset.title).toBe('Corn Growing Guide');
    expect(seo.dataset.description).toBe(
      'When and how to plant corn: sowing and transplant windows, frost sensitivity, '
      + 'companions, and harvest timing for your zone.');
  });

  it('leaves no English on a Spanish page', async () => {
    await i18n.changeLanguage('es');
    const { container } = draw();
    expect(await screen.findByText('Maíz')).toBeInTheDocument();
    expect(await screen.findByText('14 jul - 7 sept')).toBeInTheDocument();
    expect(screen.getByText('~25 de abril')).toBeInTheDocument();
    const server = [NOTES, COMPANIONS, AVOID];
    for (const section of ['cropGuide', 'plantingCalendar', 'crops']) {
      expect(englishSurvivors(container, section, server)).toEqual([]);
    }
    let text = container.textContent;
    for (const u of server) text = text.split(u).join(' ');
    for (const english of ['Direct Sow', 'Harvest', 'May 10', 'Jan', 'Harvest Forecast']) {
      expect(text).not.toContain(english);
    }
    expect(text).not.toMatch(/\b(cropGuide|plantingCalendar|crops|garden)\.[a-zA-Z]/);
    const seo = screen.getByTestId('seo');
    expect(seo.dataset.title).toBe('Guía de cultivo: Maíz');
    expect(seo.dataset.description).toMatch(/^Cuándo y cómo sembrar maíz: /);
  });
});
