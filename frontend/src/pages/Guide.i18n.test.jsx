// The guide's prose comes from a data module chosen by page language, and its
// chrome from the catalog. Either half can silently stay English: the module
// switch only shows up on a Spanish render, and a hardcoded "Back to the
// guide" looks finished in an English browser.
import { describe, it, expect, afterEach, vi } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

import Guide from './Guide';
import i18n from '../i18n';
import * as en from '../data/gardenGuide';
import * as es from '../data/gardenGuide.es';

const seoCalls = [];
vi.mock('../components/Seo', () => ({
  default: (props) => { seoCalls.push(props); return null; },
}));

const draw = (path) => render(
  <MemoryRouter initialEntries={[path]}>
    <Routes>
      <Route path="/about/guide" element={<Guide />} />
      <Route path="/about/guide/:slug" element={<Guide />} />
    </Routes>
  </MemoryRouter>,
);

afterEach(async () => {
  seoCalls.length = 0;
  await i18n.changeLanguage('en');
});

const lastSeo = () => seoCalls[seoCalls.length - 1];
const catalog = (lng) => i18n.getResourceBundle(lng, 'common').guide;

describe('garden guide hub', () => {
  it('renders the English content in English', async () => {
    await i18n.changeLanguage('en');
    const { container } = draw('/about/guide');
    expect(container.textContent).toContain(en.GUIDE_TITLE);
    for (const c of en.CHAPTERS) expect(container.textContent).toContain(c.title);
    expect(lastSeo()).toMatchObject({ title: en.GUIDE_TITLE, description: en.GUIDE_DESCRIPTION });
  });

  it('renders the Spanish content, chrome and meta on a Spanish page', async () => {
    await i18n.changeLanguage('es');
    const { container } = draw('/about/guide');
    const text = container.textContent;
    expect(text).toContain(es.GUIDE_TITLE);
    expect(text).toContain(es.GUIDE_INTRO);
    for (const c of es.CHAPTERS) {
      expect(text).toContain(c.title);
      expect(text).toContain(c.tagline);
    }
    expect(text).not.toContain(en.GUIDE_INTRO);
    expect(lastSeo()).toMatchObject({
      title: es.GUIDE_TITLE, description: es.GUIDE_DESCRIPTION, path: '/about/guide',
    });
  });
});

describe('garden guide chapter', () => {
  it('renders every Spanish chapter with no English prose or chrome left', async () => {
    await i18n.changeLanguage('es');
    const enChrome = catalog('en');
    const esChrome = catalog('es');
    for (const [i, c] of es.CHAPTERS.entries()) {
      const { container, unmount } = draw(`/about/guide/${c.slug}`);
      const text = container.textContent;
      const enC = en.CHAPTERS[i];
      expect(text).toContain(c.title);
      expect(text).toContain(c.sections[0].p[0]);
      expect(text).not.toContain(enC.title);
      expect(text).not.toContain(enC.sections[0].h);
      // The breadcrumb label is an attribute, not text; the rest is visible.
      const survivors = Object.keys(enChrome).filter(
        (k) => k !== 'breadcrumbLabel' && enChrome[k] !== esChrome[k]
          && text.includes(enChrome[k]));
      expect(survivors, c.slug).toEqual([]);
      expect(text).toContain(`Capítulo ${i + 1} de ${es.CHAPTERS.length}`);
      expect(container.querySelector('nav').getAttribute('aria-label')).toBe(esChrome.breadcrumbLabel);
      expect(lastSeo()).toMatchObject({
        title: `${c.title} — ${es.GUIDE_TITLE}`,
        description: c.description,
        path: `/about/guide/${c.slug}`,
      });
      unmount();
    }
  });

  it('ends the last chapter with a Spanish link back to the hub', async () => {
    await i18n.changeLanguage('es');
    const last = es.CHAPTERS[es.CHAPTERS.length - 1];
    const { container } = draw(`/about/guide/${last.slug}`);
    expect(container.textContent).toContain(catalog('es').backToGuide);
  });

  it('never renders a raw translation key', async () => {
    await i18n.changeLanguage('es');
    const { container } = draw(`/about/guide/${es.CHAPTERS[0].slug}`);
    expect(container.textContent).not.toMatch(/\b(guide|app)\.[a-zA-Z]/);
  });
});
