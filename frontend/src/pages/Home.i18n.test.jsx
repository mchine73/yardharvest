// The home page is one of the three pages advertised to Google as Spanish, so
// it must render no English on /es/ — including the hero, whose highlighted
// word used to be hardcoded English glued onto a translated fragment.
import { describe, it, expect, afterEach, vi } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import Home from './Home';
import i18n from '../i18n';

// jsdom has no matchMedia; "reduced motion" makes the reveal effect a no-op.
window.matchMedia = window.matchMedia || (() => ({ matches: true }));

globalThis.__mkt = false;
vi.mock('../SiteConfigContext', () => ({
  useSiteConfig: () => ({ marketplaceEnabled: globalThis.__mkt, languages: ['en', 'es'] }),
}));
vi.mock('../AuthContext', () => ({ useAuth: () => ({ user: null }) }));
vi.mock('../api', () => ({
  listingsAPI: { featured: vi.fn().mockResolvedValue({ data: [] }) },
}));
// Seo needs a HelmetProvider; the description it receives is what matters.
// A span, not a <meta>: React 19 hoists <meta> out of the container.
vi.mock('../components/Seo', () => ({
  default: ({ description }) => <span data-testid="seo" data-content={description} />,
}));

const draw = () => render(<MemoryRouter><Home /></MemoryRouter>);

afterEach(async () => { globalThis.__mkt = false; await i18n.changeLanguage('en'); });

const englishOf = (section) => i18n.getResourceBundle('en', 'common')[section];
const spanishOf = (section) => i18n.getResourceBundle('es', 'common')[section];

describe.each([['garden mode', false], ['marketplace mode', true]])('home page, %s', (_label, mkt) => {
  it('renders the hero as one sentence with the highlight inside it', async () => {
    globalThis.__mkt = mkt;
    await i18n.changeLanguage('es');
    const { container } = draw();
    const h1 = container.querySelector('h1');
    expect(h1.querySelector('.yh-highlight').textContent).toBe('huerto');
    expect(h1.querySelector('br')).toBeTruthy();
    expect(h1.textContent).not.toMatch(/garden|neighbor|admin/i);
  });

  it('leaves no English home string on the Spanish page', async () => {
    globalThis.__mkt = mkt;
    await i18n.changeLanguage('es');
    const { container } = draw();
    const en = englishOf('home');
    const es = spanishOf('home');
    // Strip markup tags from the catalog value, and match whole words only:
    // "List" must not be found inside "¿Listo para empezar?".
    const plain = (s) => s.replace(/<[^>]+>/g, '');
    const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const survivors = Object.keys(en).filter(
      (k) => en[k] !== es[k] && plain(en[k]).length > 3
        && new RegExp(`(^|[^\\p{L}])${esc(plain(en[k]))}($|[^\\p{L}])`, 'u').test(container.textContent));
    expect(survivors).toEqual([]);
    expect(container.textContent).not.toMatch(/\bhome\.[a-zA-Z]/);
  });

  it('passes a Spanish description to Seo', async () => {
    globalThis.__mkt = mkt;
    await i18n.changeLanguage('es');
    const { getByTestId } = draw();
    expect(getByTestId('seo').getAttribute('data-content')).toBe(spanishOf('home').seoDescription);
  });
});

describe('home page in English', () => {
  it('keeps the English hero and the exact English description', async () => {
    await i18n.changeLanguage('en');
    const { container, getByTestId } = draw();
    expect(container.querySelector('h1').textContent).toBe('Less admin,more garden.');
    expect(getByTestId('seo').getAttribute('data-content')).toBe(
      'YardHarvest is the all-in-one platform for community gardens — manage plots, members, '
      + 'dues, events and volunteers, and grow a thriving local garden network.');
  });
});
