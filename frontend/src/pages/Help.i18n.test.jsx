// The Help Center renders from one of two content modules, picked by page
// language. This checks the page actually does the picking — chrome from the
// catalog, prose and <Seo> from the right module — and that a Spanish reader
// meets no English chrome, no raw key and no unfilled price token.
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

import Help from './Help';
import i18n from '../i18n';
import * as en from '../data/helpCenter';
import * as es from '../data/helpCenter.es';

let pricing;
vi.mock('../api', () => ({
  publicAPI: { pricing: vi.fn(() => pricing) },
}));
// Seo needs Helmet + site config; all that matters here is what it is given.
vi.mock('../components/Seo', () => ({
  default: ({ title, description }) => (
    <div data-testid="seo" data-title={title} data-description={description} />
  ),
}));

const draw = (path) => render(
  <MemoryRouter initialEntries={[path]}>
    <Routes>
      <Route path="/help" element={<Help />} />
      <Route path="/help/:slug" element={<Help />} />
    </Routes>
  </MemoryRouter>,
);

beforeEach(() => {
  window.scrollTo = vi.fn();
  pricing = Promise.resolve({ data: { garden_pro: { monthly: 12, yearly: 60, trial_days: 14 } } });
});
afterEach(async () => { await i18n.changeLanguage('en'); });

/** English help.* catalog values that must not survive on a Spanish page. */
function englishChrome() {
  const enHelp = i18n.getResourceBundle('en', 'common').help;
  const esHelp = i18n.getResourceBundle('es', 'common').help;
  return Object.keys(enHelp).filter((k) => enHelp[k] !== esHelp[k]).map((k) => enHelp[k])
    .filter((v) => !v.includes('{{'));
}

describe('help center hub', () => {
  it('renders English content and meta in English', async () => {
    await i18n.changeLanguage('en');
    draw('/help');
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(en.HELP_TITLE);
    const seo = screen.getByTestId('seo');
    expect(seo.dataset.title).toBe(en.HELP_TITLE);
    expect(seo.dataset.description).toBe(en.HELP_DESCRIPTION);
    expect(screen.getByText('Didn’t find it?')).toBeInTheDocument();
  });

  it('renders Spanish content, chrome and meta in Spanish', async () => {
    await i18n.changeLanguage('es');
    const { container } = draw('/help');
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(es.HELP_TITLE);
    const seo = screen.getByTestId('seo');
    expect(seo.dataset.title).toBe(es.HELP_TITLE);
    expect(seo.dataset.description).toBe(es.HELP_DESCRIPTION);
    for (const c of es.CATEGORIES) expect(screen.getAllByText(c.title).length).toBeGreaterThan(0);
    // getAll: "Para hortelanos" is both a category and its one article.
    for (const a of es.ARTICLES) expect(screen.getAllByText(a.title).length).toBeGreaterThan(0);

    const text = container.textContent;
    const html = container.innerHTML;
    expect(englishChrome().filter((v) => text.includes(v) || html.includes(v))).toEqual([]);
    expect(en.CATEGORIES.filter((c) => text.includes(c.blurb))).toEqual([]);
    expect(text).not.toContain(en.HELP_INTRO);
    expect(text).not.toMatch(/\bhelp\.[a-zA-Z]/);
    expect(screen.getByRole('searchbox')).toHaveAttribute('placeholder', i18n.t('help.searchPlaceholder'));
  });
});

describe('help center article', () => {
  it('renders the Spanish article, its meta and filled prices', async () => {
    await i18n.changeLanguage('es');
    const article = es.findArticle('free-and-pro');
    const { container } = draw('/help/free-and-pro');
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(article.title);
    const seo = screen.getByTestId('seo');
    expect(seo.dataset.title).toBe(`${article.title} — ${es.HELP_TITLE}`);
    expect(seo.dataset.description).toBe(article.description);
    expect(await screen.findByText(/Pro cuesta \$12 al mes o \$60 al año/)).toBeInTheDocument();
    expect(container.textContent).toMatch(/prueba gratis de 14 días/);
    expect(container.textContent).not.toMatch(/\{\{/);
    expect(container.textContent).not.toMatch(/\bhelp\.[a-zA-Z]/);
    expect(screen.getByRole('link', { name: 'Ayuda' })).toHaveAttribute('href', '/help');
    expect(screen.getByRole('navigation')).toHaveAttribute('aria-label', 'Ruta de navegación');
  });

  it('falls back to wording that fits Spanish when pricing cannot load', async () => {
    pricing = Promise.reject(new Error('offline'));
    await i18n.changeLanguage('es');
    const { container } = draw('/help/trial-and-billing');
    expect(container.textContent).toContain('La prueba de Garden Pro dura varios días');
    expect(container.textContent).not.toMatch(/\{\{|a monthly fee|a yearly fee/);
  });

  it('still renders the English article in English', async () => {
    await i18n.changeLanguage('en');
    draw('/help/tap-to-pay');
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Tap to Pay at the gate');
    expect(screen.getByRole('link', { name: 'Help' })).toHaveAttribute('href', '/help');
  });
});
