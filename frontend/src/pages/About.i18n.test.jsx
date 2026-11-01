// /about is advertised to Google as Spanish, so the Spanish render must carry
// no English: the step cards, feature cards, seasonal guide and FAQ all used
// to be English literals in arrays the earlier pass could not see.
import { describe, it, expect, afterEach, vi } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import About from './About';
import i18n from '../i18n';

// jsdom has no matchMedia; "reduced motion" makes the reveal effect a no-op.
window.matchMedia = window.matchMedia || (() => ({ matches: true }));

globalThis.__mkt = false;
vi.mock('../SiteConfigContext', () => ({
  useSiteConfig: () => ({ marketplaceEnabled: globalThis.__mkt, languages: ['en', 'es'] }),
}));
vi.mock('../AuthContext', () => ({ useAuth: () => ({ user: null }) }));
// A span, not a <meta>: React 19 hoists <meta> out of the container.
vi.mock('../components/Seo', () => ({
  default: ({ description }) => <span data-testid="seo" data-content={description} />,
}));

const draw = () => render(<MemoryRouter><About /></MemoryRouter>);
const bundle = (lang) => i18n.getResourceBundle(lang, 'common').about;
const plain = (s) => s.replace(/<[^>]+>/g, '');
const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
// Whole words only, so a short English value is not "found" inside Spanish.
const appears = (text, needle) => new RegExp(`(^|[^\\p{L}])${esc(needle)}($|[^\\p{L}])`, 'u').test(text);

afterEach(async () => { globalThis.__mkt = false; await i18n.changeLanguage('en'); });

describe.each([['garden mode', false], ['marketplace mode', true]])('about page, %s', (_label, mkt) => {
  it('leaves no English about string on the Spanish page', async () => {
    globalThis.__mkt = mkt;
    await i18n.changeLanguage('es');
    const { container } = draw();
    const en = bundle('en');
    const es = bundle('es');
    const survivors = Object.keys(en).filter(
      (k) => en[k] !== es[k] && plain(en[k]).length > 3 && appears(container.textContent, plain(en[k])));
    expect(survivors).toEqual([]);
    expect(container.textContent).not.toMatch(/\babout\.[a-zA-Z]/);
    expect(container.textContent).not.toMatch(/\bStep \d/);
  });

  it('passes a Spanish description to Seo', async () => {
    globalThis.__mkt = mkt;
    await i18n.changeLanguage('es');
    const { getByTestId } = draw();
    expect(getByTestId('seo').getAttribute('data-content')).toBe(bundle('es').seoDescription);
  });
});

describe('about page story', () => {
  it('renders "We thought" as one sentence with the question emphasised', async () => {
    await i18n.changeLanguage('en');
    const { container } = draw();
    const em = container.querySelector('p em');
    expect(em.textContent).toBe('what if we could connect these two groups?');
    // The three fragments used to run together with no spaces.
    expect(em.parentElement.textContent).toMatch(/^We thought: what if .*groups\? What if the gardener/);
  });

  it('keeps the exact English description', async () => {
    await i18n.changeLanguage('en');
    const { getByTestId } = draw();
    expect(getByTestId('seo').getAttribute('data-content')).toBe(
      "YardHarvest's story and mission: making community gardens easier to run and helping local garden networks thrive.");
  });
});
