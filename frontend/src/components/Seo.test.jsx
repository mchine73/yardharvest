// Seo owns the live <head> after hydration, which is what Googlebot reads.
//
// The bug these tests pin: main.jsx removes every data-ssr tag at hydration,
// so the server's correct canonical and hreflang are thrown away and whatever
// this component emits is final. It used to emit `SITE_URL + path` with no
// language prefix, so on /es/gardens the canonical claimed to be the ENGLISH
// url — telling Google the Spanish page is a duplicate and to drop it, which
// is the exact opposite of why the page exists.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { HelmetProvider } from 'react-helmet-async';

import Seo from './Seo';
import i18n from '../i18n';

// The real provider fetches /api/admin/site-config; the language list is the
// only field these tests care about.
vi.mock('../SiteConfigContext', () => ({
  useSiteConfig: () => ({ languages: globalThis.__langs ?? ['en'] }),
}));

const head = () => document.head.innerHTML;

let view;
const draw = (props) => {
  view = render(
    <HelmetProvider>
      <Seo {...props} />
    </HelmetProvider>,
  );
  return view;
};

beforeEach(() => { globalThis.__langs = ['en']; });
afterEach(async () => {
  // Unmount BEFORE clearing the head. Helmet removes the tags it owns on
  // unmount, and pulling them out from under it throws on removeChild.
  view?.unmount();
  view = undefined;
  document.head.querySelectorAll('link,meta,title').forEach((el) => el.remove());
  await i18n.changeLanguage('en');
});

describe('Seo canonical', () => {
  it('points at the English url in English', async () => {
    draw({ title: 'Community Gardens', path: '/gardens' });
    await waitFor(() => expect(head()).toContain('rel="canonical"'));
    expect(head()).toContain('href="https://www.yardharvest.app/gardens"');
  });

  it('points at the Spanish url in Spanish, not the English one', async () => {
    await i18n.changeLanguage('es');
    draw({ title: 'Huertos comunitarios', path: '/gardens' });
    await waitFor(() => expect(head()).toContain('rel="canonical"'));
    expect(head()).toContain('href="https://www.yardharvest.app/es/gardens"');
  });

  it('keeps the root a bare /es rather than /es/', async () => {
    await i18n.changeLanguage('es');
    draw({ path: '/' });
    await waitFor(() => expect(head()).toContain('rel="canonical"'));
    expect(head()).toContain('href="https://www.yardharvest.app/es"');
  });
});

describe('Seo hreflang', () => {
  it('emits none while only English is offered', async () => {
    draw({ title: 'Community Gardens', path: '/gardens' });
    await waitFor(() => expect(head()).toContain('rel="canonical"'));
    expect(head()).not.toContain('hreflang');
  });

  it('emits both languages plus x-default once Spanish is offered', async () => {
    globalThis.__langs = ['en', 'es'];
    draw({ title: 'Community Gardens', path: '/gardens' });
    await waitFor(() => expect(head()).toContain('hreflang'));
    const h = head();
    expect(h).toContain('hreflang="en"');
    expect(h).toContain('hreflang="es"');
    expect(h).toContain('hreflang="x-default"');
    expect(h).toContain('https://www.yardharvest.app/es/gardens');
  });

  it('emits none for a page whose content is still English', async () => {
    // Pricing is not in seoReady.js. Advertising a Spanish alternate for it
    // sends a Spanish searcher to a page they cannot read.
    globalThis.__langs = ['en', 'es'];
    draw({ title: 'Pricing', path: '/pricing' });
    await waitFor(() => expect(head()).toContain('rel="canonical"'));
    expect(head()).not.toContain('hreflang');
  });

  it('emits none on a noindex page', async () => {
    globalThis.__langs = ['en', 'es'];
    draw({ title: 'Log in', path: '/login', noindex: true });
    await waitFor(() => expect(head()).toContain('noindex'));
    expect(head()).not.toContain('hreflang');
  });
});

describe('Seo og:locale', () => {
  it('uses a full locale, not a bare language code', async () => {
    await i18n.changeLanguage('es');
    draw({ path: '/gardens' });
    await waitFor(() => expect(head()).toContain('og:locale'));
    expect(head()).toContain('content="es_ES"');
  });
});
