// HarvestForecast in both languages: crop names through the label map,
// plurals, the server's English "%b %d - %b %d" week label replaced by dates
// formatted from week_start/week_end, and the Seo copy app/seo.py serves.
import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import HarvestForecast from './HarvestForecast';
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

let empty = false;
vi.mock('../AuthContext', () => ({ useAuth: () => ({ user: null }) }));
vi.mock('../SiteConfigContext', () => ({ useSiteConfig: () => ({ marketplaceEnabled: true }) }));
vi.mock('../components/Seo', () => ({
  default: ({ title, description }) => (
    <div data-testid="seo" data-title={title} data-description={description} />
  ),
}));
vi.mock('../api', () => ({
  plantingAPI: {
    forecast: vi.fn(() => Promise.resolve({
      data: empty ? [] : [
        {
          week_start: '2026-11-02', week_end: '2026-11-08', week_label: 'Nov 02 - Nov 08',
          categories: [
            { category: 'Peppers (Hot)', seller_count: 1, quantities: ['20 lbs'], has_preorder: true },
            { category: 'Leafy Greens', seller_count: 3, quantities: [], has_preorder: false },
          ],
        },
        { week_start: '2026-11-09', week_end: '2026-11-15', week_label: 'Nov 09 - Nov 15', categories: [] },
      ],
    })),
    preorders: vi.fn(() => Promise.resolve({
      data: empty ? [] : [{
        id: 5, seller_id: 9, seller_name: 'Dana', category: 'Peppers (Hot)', variety: 'Jalapeño',
        quantity_estimate: '20 lbs', estimated_harvest_start: '2026-11-03', estimated_harvest_end: '2026-11-20',
      }],
    })),
  },
}));

const draw = () => render(<MemoryRouter><HarvestForecast /></MemoryRouter>);

afterEach(async () => {
  empty = false;
  await i18n.changeLanguage('en');
});

describe('HarvestForecast', () => {
  it('renders English, with the Seo copy app/seo.py serves', async () => {
    await i18n.changeLanguage('en');
    draw();
    expect(await screen.findByText('Nov 2 - Nov 8')).toBeInTheDocument();
    expect(screen.getByText('2 crops')).toBeInTheDocument();
    expect(screen.getByText('1 grower')).toBeInTheDocument();
    expect(screen.getByText('3 growers')).toBeInTheDocument();
    expect(screen.getByText('Expected Nov 3 - Nov 20')).toBeInTheDocument();
    const seo = screen.getByTestId('seo');
    expect(seo.dataset.title).toBe('Harvest Forecast');
    expect(seo.dataset.description).toBe(
      'See what local gardens are growing and when crops will be ready to harvest in your area.');
  });

  it('leaves no English on a Spanish page', async () => {
    await i18n.changeLanguage('es');
    const { container } = draw();
    expect(await screen.findByText('2 cultivos')).toBeInTheDocument();
    expect(screen.getByText('1 productor')).toBeInTheDocument();
    expect(screen.getAllByText('Chiles (picantes)').length).toBe(2);
    const user = ['Dana', 'Jalapeño', '20 lbs'];
    expect(englishSurvivors(container, 'harvestForecast', user)).toEqual([]);
    expect(englishSurvivors(container, 'crops', user)).toEqual([]);
    expect(container.textContent).not.toContain('Nov 02');
    expect(container.textContent).not.toMatch(/\b(harvestForecast|plantingCalendar|crops|garden)\.[a-zA-Z]/);
    expect(screen.getByTestId('seo').dataset.title).toBe('Pronóstico de cosecha');
  });

  // <Trans> parses catalog markup as HTML; a tag named after a void element
  // (<link>) renders an EMPTY anchor with the words beside it. Check the words
  // are inside the anchor, in both languages.
  it.each([
    ['en', 'No Harvest Data Yet', 'Planting Log'],
    ['es', 'Todavía no hay datos de cosecha', 'registro de siembra'],
  ])('keeps the planting-log link text inside the anchor (%s)', async (lang, title, label) => {
    empty = true;
    await i18n.changeLanguage(lang);
    const { container } = draw();
    expect(await screen.findByText(title)).toBeInTheDocument();
    const link = container.querySelector('p a[href="/my-planting-log"]');
    expect(link).toBeTruthy();
    expect(link.textContent).toBe(label);
    if (lang === 'es') expect(englishSurvivors(container, 'harvestForecast')).toEqual([]);
  });
});
