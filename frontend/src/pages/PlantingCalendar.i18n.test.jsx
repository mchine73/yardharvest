// PlantingCalendar in both languages: the Spanish render must carry no English
// from the `plantingCalendar` or `crops` sections and no raw key, the <Seo>
// props must stay word-for-word what app/seo.py serves for /planting-calendar,
// and the English the API sends (activity labels, "%b %d" frost dates) must
// not reach a Spanish reader — the page translates by activity type and
// formats dates from the day-of-year numbers instead.
import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import PlantingCalendar from './PlantingCalendar';
import i18n from '../i18n';

// Keys of `section` whose English value is still visible in `container` —
// text, plus the attributes that render as text. Placeholders ({{count}}) match
// anything, and the match is on whole words. Server prose (the guide's notes
// and companion lists) is removed first: it is not translated.
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

const NOTES = 'Start indoors 6-8 weeks before last frost.';
const COMPANIONS = 'Basil, Carrots, Parsley';
const AVOID = 'Fennel, Corn';

// Shaped like /api/planting/calendar and /guide, English labels and all.
let estimated = true;
const location = () => ({
  lat: estimated ? 44.9 : null, estimated, zone: estimated ? '4' : '5b',
  region: estimated ? 'Your location' : 'Omaha area (default)',
  last_frost: { month: 5, day: 9, label: 'May 09' },
  first_frost: { month: 9, day: 28, label: 'Sep 28' },
  last_frost_doy: 129, first_frost_doy: 271,
});
const day = (doy, label) => ({ label, start_doy: doy });

vi.mock('../components/Seo', () => ({
  default: ({ title, description }) => (
    <div data-testid="seo" data-title={title} data-description={description} />
  ),
}));
vi.mock('../api', () => ({
  plantingAPI: {
    calendar: vi.fn(() => Promise.resolve({
      data: {
        location: location(),
        categories: [
          {
            category: 'Tomatoes', frost_sensitive: true,
            activities: [
              { type: 'indoor_seed', label: 'Start Indoors', start: day(74, 'Mar 15'), end: day(88, 'Mar 29'), start_doy: 74, end_doy: 88 },
              { type: 'transplant', label: 'Transplant', start: day(134, 'May 14'), end: day(164, 'Jun 13'), start_doy: 134, end_doy: 164 },
              { type: 'harvest', label: 'Harvest', start: day(194, 'Jul 13'), end: day(249, 'Sep 06'), start_doy: 194, end_doy: 249 },
            ],
          },
          {
            // Spans the whole year so "what to do this month" always renders.
            category: 'Leafy Greens', frost_sensitive: false,
            activities: [
              { type: 'direct_sow', label: 'Direct Sow', start: day(1, 'Jan 01'), end: day(365, 'Dec 31'), start_doy: 1, end_doy: 365 },
            ],
          },
        ],
      },
    })),
    guide: vi.fn(() => Promise.resolve({
      data: {
        location: location(),
        guides: [
          {
            id: 1, category: 'Tomatoes', zone: '5b',
            seed_indoor_start_doy: 74, direct_sow_start_doy: null, direct_sow_end_doy: null,
            transplant_start_doy: 134, transplant_end_doy: 164,
            days_to_harvest_min: 60, days_to_harvest_max: 85, succession_interval_days: 14,
            frost_sensitive: true, notes: NOTES, companion_plants: COMPANIONS, avoid_near: AVOID,
          },
          {
            id: 2, category: 'Leafy Greens', zone: '5b',
            seed_indoor_start_doy: null, direct_sow_start_doy: 104, direct_sow_end_doy: 274,
            transplant_start_doy: null, transplant_end_doy: null,
            days_to_harvest_min: 30, days_to_harvest_max: 60, succession_interval_days: null,
            frost_sensitive: false, notes: null, companion_plants: null, avoid_near: null,
          },
        ],
      },
    })),
  },
}));

const draw = () => render(<MemoryRouter><PlantingCalendar /></MemoryRouter>);
// The crop's row header (the name also appears in "what to do this month").
const row = (container, name) => [...container.querySelectorAll('tbody td[title]')]
  .find((td) => td.textContent.startsWith(name));

afterEach(async () => {
  estimated = true;
  await i18n.changeLanguage('en');
});

describe('PlantingCalendar', () => {
  it('renders English, with the Seo copy app/seo.py serves', async () => {
    await i18n.changeLanguage('en');
    const { container } = draw();
    expect(await screen.findByText('Your Planting Calendar')).toBeInTheDocument();
    expect(screen.getByText(/Last frost ~May 9/)).toBeInTheDocument();
    expect(screen.getByText('Jan')).toBeInTheDocument();
    expect(row(container, 'Leafy Greens')).toBeTruthy();
    fireEvent.click(row(container, 'Tomatoes'));
    expect(screen.getByText('Tomatoes Growing Guide')).toBeInTheDocument();
    expect(screen.getByText('Every 14 days')).toBeInTheDocument();
    expect(screen.getByText('60 - 85 days')).toBeInTheDocument();
    const seo = screen.getByTestId('seo');
    expect(seo.dataset.title).toBe('Planting Calendar');
    expect(seo.dataset.description).toBe(
      'A location-aware planting calendar: when to sow, transplant and harvest each '
      + 'crop based on your local frost dates and growing zone.');
  });

  it('leaves no English on a Spanish page, detail panel open', async () => {
    await i18n.changeLanguage('es');
    const { container } = draw();
    expect(await screen.findByText('Tu calendario de siembra')).toBeInTheDocument();
    fireEvent.click(row(container, 'Jitomates'));
    expect(screen.getByText('Guía de cultivo: Jitomates')).toBeInTheDocument();
    expect(screen.getByText('Cada 14 días')).toBeInTheDocument();
    const server = [NOTES, COMPANIONS, AVOID];
    expect(englishSurvivors(container, 'plantingCalendar', server)).toEqual([]);
    expect(englishSurvivors(container, 'crops', server)).toEqual([]);
    // What the API sends in English must not leak through either.
    const text = container.textContent;
    for (const english of ['May 09', 'Sep 28', 'Jan', 'Harvest Forecast', 'My Planting Log', 'Update']) {
      expect(text).not.toContain(english);
    }
    const titles = [...container.querySelectorAll('[title]')].map((el) => el.getAttribute('title'));
    expect(titles.filter((t) => /Start Indoors|Transplant|Harvest|Mar 15/.test(t))).toEqual([]);
    expect(screen.getByTestId('seo').dataset.title).toBe('Calendario de siembra');
  });

  it('says Omaha in Spanish when no location is known', async () => {
    estimated = false;
    await i18n.changeLanguage('es');
    const { container } = draw();
    expect(await screen.findByText('Calendario de siembra de Omaha, zona 5b')).toBeInTheDocument();
    expect(englishSurvivors(container, 'plantingCalendar')).toEqual([]);
  });

  it('never renders a raw translation key', async () => {
    await i18n.changeLanguage('es');
    const { container } = draw();
    await screen.findByText('Tu calendario de siembra');
    fireEvent.click(row(container, 'Hojas verdes'));
    expect(container.textContent).not.toMatch(/\b(plantingCalendar|crops|garden|dash)\.[a-zA-Z]/);
  });
});
