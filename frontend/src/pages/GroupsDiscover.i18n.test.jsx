// GroupsDiscover in both languages: the Spanish render must carry no English
// from the `groups` catalog section and no raw key, and the <Seo> props must
// stay word-for-word what app/seo.py serves for /groups in English.
import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import GroupsDiscover from './GroupsDiscover';
import i18n from '../i18n';

// Keys of `section` whose English value is still visible in `container` —
// text, plus the attributes that render as text. Placeholders ({{count}}) match
// anything, and the match is on whole words, so "Event" is not found inside
// "Evento". User content is removed first: it is never translated.
function englishSurvivors(container, section, userContent = []) {
  const en = i18n.getResourceBundle('en', 'common')[section];
  const es = i18n.getResourceBundle('es', 'common')[section];
  const ATTRS = ['placeholder', 'alt', 'title', 'aria-label'];
  const attrs = [...container.querySelectorAll(ATTRS.map((a) => `[${a}]`).join(','))]
    .flatMap((el) => ATTRS.map((a) => el.getAttribute(a)).filter(Boolean));
  // Text node by text node: textContent glues neighbours together ("mi awayBenson"),
  // which would defeat the whole-word match.
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

vi.mock('../AuthContext', () => ({
  useAuth: () => ({ user: { id: 7, zip_code: '68132' } }),
}));
// Seo needs Helmet + SiteConfig providers; all this test wants is its props.
vi.mock('../components/Seo', () => ({
  default: ({ title, description }) => (
    <div data-testid="seo" data-title={title} data-description={description} />
  ),
}));
vi.mock('../api', () => ({
  groupsAPI: {
    browse: vi.fn().mockResolvedValue({
      data: {
        groups: [
          { id: 1, name: 'Huerteros de Dundee', neighborhood: 'Dundee', city: 'Omaha',
            description: 'Tomates y chiles', member_count: 1, post_count: 1, distance: 3.2 },
          { id: 2, name: 'Benson Growers', neighborhood: 'Benson', city: 'Omaha',
            description: 'Raised beds', member_count: 12, post_count: 0 },
        ],
        total: 2, pages: 2, has_prev: false, has_next: true,
      },
    }),
  },
}));

const draw = () => render(<MemoryRouter><GroupsDiscover /></MemoryRouter>);

afterEach(async () => { await i18n.changeLanguage('en'); });

describe('GroupsDiscover', () => {
  it('renders English, with the Seo copy app/seo.py serves', async () => {
    await i18n.changeLanguage('en');
    draw();
    expect(await screen.findByText('2 groups found')).toBeInTheDocument();
    expect(screen.getByText('Neighborhood Garden Groups')).toBeInTheDocument();
    expect(screen.getByText('1 member')).toBeInTheDocument();
    expect(screen.getByText('12 members')).toBeInTheDocument();
    expect(screen.getByText('1 post')).toBeInTheDocument();
    expect(screen.getByText('0 posts')).toBeInTheDocument();
    expect(screen.getByText('3.2 mi away')).toBeInTheDocument();
    expect(screen.getByRole('option', { name: '25 miles' })).toBeInTheDocument();
    const seo = screen.getByTestId('seo');
    expect(seo.dataset.title).toBe('Neighborhood Groups');
    expect(seo.dataset.description).toBe('Join neighborhood gardening groups on YardHarvest.');
  });

  it('renders Spanish', async () => {
    await i18n.changeLanguage('es');
    draw();
    expect(await screen.findByText('2 grupos encontrados')).toBeInTheDocument();
    expect(screen.getByText('Grupos de huertos del vecindario')).toBeInTheDocument();
    expect(screen.getByText('1 integrante')).toBeInTheDocument();
    expect(screen.getByText('12 integrantes')).toBeInTheDocument();
    expect(screen.getByText('1 publicación')).toBeInTheDocument();
    expect(screen.getByText('a 3.2 mi')).toBeInTheDocument();
    expect(screen.getByRole('option', { name: '25 millas' })).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Buscar grupos...')).toBeInTheDocument();
    expect(screen.getByText('Siguiente')).toBeInTheDocument();
    expect(screen.getByTestId('seo').dataset.title).toBe('Grupos del vecindario');
    // User content is left exactly as written.
    expect(screen.getByText('Benson Growers')).toBeInTheDocument();
  });

  it('has a detector that finds English when English is there', async () => {
    // Without this, an englishSurvivors() that matched nothing would pass below.
    await i18n.changeLanguage('en');
    const { container } = draw();
    await screen.findByText('2 groups found');
    const found = englishSurvivors(container, 'groups');
    expect(found).toEqual(expect.arrayContaining(['heroTitle', 'search', 'groupsFound_other', 'memberCount_one', 'milesAway', 'next']));
  });

  it('leaves no English from the groups section on the Spanish page', async () => {
    await i18n.changeLanguage('es');
    const { container } = draw();
    await screen.findByText('2 grupos encontrados');
    expect(englishSurvivors(container, 'groups', ['Benson Growers', 'Raised beds'])).toEqual([]);
  });

  it('never renders a raw translation key', async () => {
    await i18n.changeLanguage('es');
    const { container } = draw();
    await screen.findByText('2 grupos encontrados');
    expect(container.textContent).not.toMatch(/\bgroups\.[a-zA-Z]/);
  });
});
