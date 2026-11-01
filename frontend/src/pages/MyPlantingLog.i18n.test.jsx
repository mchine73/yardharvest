// MyPlantingLog in Spanish: status slugs, price-unit slugs and crop
// categories render as labels (the <option> VALUES stay the English ids the
// API stores), and the two <Trans> lines with values keep their numbers.
import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import MyPlantingLog from './MyPlantingLog';
import i18n from '../i18n';

function englishSurvivors(container, section, userContent = []) {
  const en = i18n.getResourceBundle('en', 'common')[section];
  const es = i18n.getResourceBundle('es', 'common')[section];
  const ATTRS = ['placeholder', 'alt', 'title', 'aria-label'];
  const attrs = [...container.querySelectorAll(ATTRS.map((a) => `[${a}]`).join(','))]
    .flatMap((el) => ATTRS.map((a) => el.getAttribute(a)).filter(Boolean));
  const texts = [];
  const walk = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
  while (walk.nextNode()) texts.push(walk.currentNode.nodeValue);
  let seen = [...texts, ...attrs].join('\n');
  for (const u of userContent) seen = seen.split(u).join(' ');
  const escape = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return Object.keys(en).filter((k) => en[k] !== es[k]).filter((k) => {
    const body = en[k].replace(/<\/?\w+>/g, '').split(/\{\{\w+\}\}/).map(escape).join('.*?');
    return new RegExp(`(^|[^\\p{L}])${body}($|[^\\p{L}])`, 'u').test(seen);
  });
}

vi.mock('../AuthContext', () => ({ useAuth: () => ({ user: { id: 3 } }) }));
vi.mock('../SiteConfigContext', () => ({ useSiteConfig: () => ({ marketplaceEnabled: true }) }));
vi.mock('../components/dialog/dialogService', () => ({ toast: vi.fn(), confirmDialog: vi.fn() }));
vi.mock('../api', () => ({
  plantingAPI: {
    myPlantings: vi.fn(() => Promise.resolve({
      data: [{
        id: 1, category: 'Squash (Winter)', variety: 'Butternut', status: 'harvesting',
        planted_date: '2026-05-20', estimated_harvest_start: '2026-08-13', estimated_harvest_end: '2026-09-07',
        quantity_estimate: '12 squash', weight_lbs: 30, sale_price: 2.5, price_unit: 'each',
        allow_preorder: true, auto_list_on_harvest: false, linked_listing_id: null, notes: 'North bed',
      }],
    })),
    guideCategory: vi.fn(() => Promise.resolve({ data: { days_to_harvest_min: 65, days_to_harvest_max: 90 } })),
    priceGuide: vi.fn(() => Promise.resolve({
      data: { avg_price: 3.25, low_price: 2.5, high_price: 4, unit: 'bunch', sample_size: 0, source: 'default' },
    })),
  },
}));

const draw = () => render(<MemoryRouter><MyPlantingLog /></MemoryRouter>);

afterEach(async () => { await i18n.changeLanguage('en'); });

describe('MyPlantingLog', () => {
  it('renders English labels for slugs', async () => {
    await i18n.changeLanguage('en');
    draw();
    expect(await screen.findByText('Squash (Winter)')).toBeInTheDocument();
    expect(screen.getByText('$2.50/each')).toBeInTheDocument();
  });

  it('leaves no English on a Spanish page', async () => {
    await i18n.changeLanguage('es');
    const { container } = draw();
    expect(await screen.findByText('Calabaza (de invierno)')).toBeInTheDocument();
    expect(screen.getByText('$2.50/pieza')).toBeInTheDocument();
    expect(screen.getByText('~30 lb (12 squash)')).toBeInTheDocument();
    // The option the API receives is still the English id.
    const option = screen.getByRole('option', { name: 'Hojas verdes' });
    expect(option.getAttribute('value')).toBe('Leafy Greens');
    fireEvent.change(container.querySelector('select'), { target: { value: 'Leafy Greens' } });
    expect(await screen.findByText(/\$2\.50 – \$4\.00 \/ manojo/)).toBeInTheDocument();
    expect(await screen.findByText(/días después de la siembra/)).toBeInTheDocument();
    expect(screen.getByText('Sugerido:').tagName).toBe('STRONG');
    const user = ['Butternut', '12 squash', 'North bed'];
    for (const section of ['plantingLog', 'crops']) {
      expect(englishSurvivors(container, section, user)).toEqual([]);
    }
    expect(container.textContent).not.toMatch(/\b(plantingLog|crops|garden|dash|common)\.[a-zA-Z]/);
  });
});
