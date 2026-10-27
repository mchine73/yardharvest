// The navbar renders above every page, which makes it the component most
// worth asserting on and — until this test — the one nothing checked.
//
// It catches both failure modes this rollout has actually shipped:
//   * a label that renders as nothing, the way the garden admin sidebar did
//     when its array was renamed to labelKey and a render site kept reading
//     .label. `{undefined}` is not an error in JSX, so only a render test
//     sees it.
//   * a label that stays English on a Spanish page, which is what the whole
//     navbar did until now.
import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import Navbar from './Navbar';
import i18n from '../i18n';

vi.mock('../AuthContext', () => ({
  useAuth: () => ({
    user: null, logout: vi.fn(), cartCount: 0, unreadCount: 0,
    notifCount: 0, setNotifCount: vi.fn(),
  }),
}));
vi.mock('../SiteConfigContext', () => ({
  useSiteConfig: () => ({ marketplaceEnabled: true, languages: ['en', 'es'] }),
}));
vi.mock('../api', () => ({
  notificationsAPI: { list: vi.fn().mockResolvedValue({ data: { notifications: [] } }) },
}));

const draw = () => render(<MemoryRouter><Navbar /></MemoryRouter>);

afterEach(async () => { await i18n.changeLanguage('en'); });

describe('navbar', () => {
  it('renders its English labels', async () => {
    await i18n.changeLanguage('en');
    draw();
    for (const label of ['Gardens', 'About', 'Pricing', 'Login', 'Register']) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }
  });

  it('renders its Spanish labels, not the English ones', async () => {
    await i18n.changeLanguage('es');
    draw();
    for (const label of ['Huertos', 'Acerca de', 'Precios', 'Iniciar sesión', 'Registrarse']) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }
  });

  it('leaves no English nav label anywhere on a Spanish page', async () => {
    // Checking a handful of English strings is not enough: most labels render
    // TWICE, once in the desktop bar and once in the mobile sheet, so
    // hardcoding one of a pair still leaves the Spanish one findable. The
    // first version of this test passed with `</i>About` hardcoded back in.
    // So: take every English nav label from the catalog and assert none of
    // them survives.
    const en = i18n.getResourceBundle('en', 'common').nav;
    const es = i18n.getResourceBundle('es', 'common').nav;
    await i18n.changeLanguage('es');
    const { container } = draw();
    const survivors = Object.keys(en).filter(
      (k) => en[k] !== es[k] && container.textContent.includes(en[k]));
    expect(survivors).toEqual([]);
  });

  it('leaves no nav link with an empty label', async () => {
    await i18n.changeLanguage('es');
    const { container } = draw();
    // The sidebar shipped as bare icons. A link whose only content is an <i>
    // is unreadable and unannounceable, so treat it as a failure.
    const empty = [...container.querySelectorAll('a.nav-link, a.nav-dropdown-item')]
      .filter((a) => !a.getAttribute('title') && !a.getAttribute('aria-label')
        && !a.textContent.trim());
    expect(empty.map((a) => a.getAttribute('href'))).toEqual([]);
  });

  it('never renders a raw translation key', async () => {
    await i18n.changeLanguage('es');
    const { container } = draw();
    expect(container.textContent).not.toMatch(/\bnav\.[a-zA-Z]/);
  });
});
