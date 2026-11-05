// GroupDetail in both languages, every tab. The page shows slugs from the
// database (post_type, role) and dates, which is where English hides once the
// JSX text is done: a badge reading "Moderator" or "Sep 30" under Spanish.
import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

import GroupDetail from './GroupDetail';
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

vi.mock('../AuthContext', () => ({ useAuth: () => ({ user: { id: 99 } }) }));
vi.mock('../components/dialog/dialogService', () => ({ confirmDialog: vi.fn() }));
vi.mock('../api', () => ({
  IMAGE_BASE: '/img/',
  groupsAPI: {
    detail: vi.fn().mockResolvedValue({
      data: {
        id: 1, name: 'Huerteros de Dundee', neighborhood: 'Dundee', city: 'Omaha', state: 'NE',
        description: 'Tomates y chiles', member_count: 1, post_count: 2,
        created_by_name: 'Ana', my_membership: { role: 'moderator' },
      },
    }),
    feed: vi.fn().mockResolvedValue({
      data: {
        posts: [
          { id: 11, post_type: 'event', title: '', content: 'Siembra el sábado', author_name: 'Ana',
            author_id: 2, created_at: '2026-09-30T14:05:00Z', event_date: '2026-10-05T17:00:00Z',
            event_location: 'Parque', comment_count: 1, pinned: true },
          { id: 12, post_type: 'question', title: 'Semillas', content: '¿Alguien tiene?',
            author_name: 'Luis', author_id: 3, created_at: '2026-09-29T10:00:00Z', comment_count: 0,
            pinned: false },
        ],
        pages: 1,
      },
    }),
    members: vi.fn().mockResolvedValue({
      data: [
        { id: 1, display_name: 'Ana', user_public_id: 'a1', role: 'admin', joined_at: '2026-01-02T12:00:00Z' },
        { id: 2, display_name: 'Luis', user_public_id: 'l2', role: 'moderator', joined_at: '2026-02-03T12:00:00Z' },
        { id: 3, display_name: 'Eva', user_public_id: 'e3', role: 'member', joined_at: '2026-03-04T12:00:00Z' },
      ],
    }),
    listings: vi.fn().mockResolvedValue({ data: [] }),
  },
}));

const USER_CONTENT = ['Huerteros de Dundee', 'Tomates y chiles', 'Siembra el sábado', 'Semillas', '¿Alguien tiene?', 'Parque'];

const draw = () => render(
  <MemoryRouter initialEntries={['/groups/1']}>
    <Routes><Route path="/groups/:id" element={<GroupDetail />} /></Routes>
  </MemoryRouter>,
);

// Visit every tab, collecting the survivors on each.
async function survivorsOnEveryTab(tabLabels, waitFor) {
  const { container } = draw();
  await screen.findByText(waitFor.feed);
  const found = new Set(englishSurvivors(container, 'groups', USER_CONTENT));
  fireEvent.click(screen.getByText(waitFor.shareButton));   // open the composer
  englishSurvivors(container, 'groups', USER_CONTENT).forEach((k) => found.add(k));
  for (const [label, marker] of tabLabels) {
    fireEvent.click(screen.getByRole('button', { name: label }));
    await screen.findByText(marker);
    englishSurvivors(container, 'groups', USER_CONTENT).forEach((k) => found.add(k));
  }
  return [...found].sort();
}

afterEach(async () => { await i18n.changeLanguage('en'); });

describe('GroupDetail', () => {
  it('renders English', async () => {
    await i18n.changeLanguage('en');
    draw();
    expect(await screen.findByText('Question')).toBeInTheDocument();
    expect(screen.getByText('1 member')).toBeInTheDocument();
    expect(screen.getByText('Created by Ana')).toBeInTheDocument();
    expect(screen.getAllByText('Moderator').length).toBeGreaterThan(0);
    expect(screen.getByText('1 comment')).toBeInTheDocument();
    expect(screen.getByText('0 comments')).toBeInTheDocument();
    expect(screen.getByText('Sep 30, 2026')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Feed' })).toBeInTheDocument();
  });

  it('renders Spanish', async () => {
    await i18n.changeLanguage('es');
    draw();
    expect(await screen.findByText('Pregunta')).toBeInTheDocument();
    expect(screen.getByText('Evento')).toBeInTheDocument();
    expect(screen.getByText('1 integrante')).toBeInTheDocument();
    expect(screen.getByText('Creado por Ana')).toBeInTheDocument();
    expect(screen.getAllByText('Moderador').length).toBeGreaterThan(0);
    expect(screen.getByText('Salir del grupo')).toBeInTheDocument();
    expect(screen.getByText('1 comentario')).toBeInTheDocument();
    expect(screen.getByText('0 comentarios')).toBeInTheDocument();
    expect(screen.queryByText('Sep 30, 2026')).toBeNull();
    expect(screen.getByRole('button', { name: 'Publicaciones' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Integrantes' }));
    expect(await screen.findByText('Administrador')).toBeInTheDocument();
    expect(screen.getByText('Integrante')).toBeInTheDocument();
    expect(screen.getAllByText(/^Se unió el /)).toHaveLength(3);

    fireEvent.click(screen.getByRole('button', { name: 'En venta' }));
    expect(await screen.findByText('Los integrantes del grupo todavía no tienen productos en venta.')).toBeInTheDocument();
  });

  it('has a detector that finds English when English is there', async () => {
    await i18n.changeLanguage('en');
    const found = await survivorsOnEveryTab(
      [['Members', 'Eva'], ['Listings', 'No active listings from group members yet.'], ['Events', 'Posted by Ana']],
      { feed: 'Question', shareButton: 'Share something with the group...' },
    );
    expect(found).toEqual(expect.arrayContaining([
      'createdBy', 'roleModerator', 'typeQuestion', 'commentCount_one', 'whatsOnYourMind',
      'roleAdmin', 'joinedOn', 'noListings', 'postedBy',
    ]));
  });

  it('leaves no English from the groups section on any Spanish tab', async () => {
    await i18n.changeLanguage('es');
    const found = await survivorsOnEveryTab(
      [['Integrantes', 'Eva'], ['En venta', 'Los integrantes del grupo todavía no tienen productos en venta.'], ['Eventos', 'Publicado por Ana']],
      { feed: 'Pregunta', shareButton: 'Comparte algo con el grupo...' },
    );
    expect(found).toEqual([]);
  });

  it('never renders a raw translation key', async () => {
    await i18n.changeLanguage('es');
    const { container } = draw();
    await screen.findByText('Pregunta');
    expect(container.textContent).not.toMatch(/\bgroups\.[a-zA-Z]/);
  });
});
