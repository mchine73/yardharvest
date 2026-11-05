// The <Trans> links on the group pages, in both languages.
//
// These first shipped with the tag name <link> in the catalog ("<link>Log
// in</link> to leave a comment."). <link> is an HTML VOID element, so the
// parser behind <Trans> closes it at once: the page rendered an EMPTY <a> and
// the words after it as plain text — in every language, so comparing English
// with Spanish could not see it. The tags are <a> now; this asserts the text
// lands INSIDE the link.
import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

import GroupPostDetail from './GroupPostDetail';
import CreateGroup from './CreateGroup';
import i18n from '../i18n';

let mockUser = null;
vi.mock('../AuthContext', () => ({ useAuth: () => ({ user: mockUser }) }));
vi.mock('../components/dialog/dialogService', () => ({ toast: vi.fn() }));
vi.mock('../api', () => ({
  IMAGE_BASE: '/img/',
  groupsAPI: {
    getPost: vi.fn().mockResolvedValue({
      data: { id: 5, post_type: 'event', title: 'Siembra', content: 'Traigan palas', author_name: 'Ana',
        author_public_id: 'a1', created_at: '2026-09-30T14:05:00Z', event_date: '2026-10-05T17:00:00Z',
        event_location: 'Parque', pinned: true },
    }),
    getComments: vi.fn().mockResolvedValue({
      data: [{ id: 1, author_name: 'Luis', author_public_id: 'l2', created_at: '2026-09-30T15:00:00Z', content: 'Voy' }],
    }),
    detail: vi.fn().mockResolvedValue({ data: { id: 1, name: 'Huerteros', my_membership: null } }),
  },
}));

const drawPost = () => render(
  <MemoryRouter initialEntries={['/groups/1/posts/5']}>
    <Routes><Route path="/groups/:id/posts/:postId" element={<GroupPostDetail />} /></Routes>
  </MemoryRouter>,
);

afterEach(async () => { mockUser = null; await i18n.changeLanguage('en'); });

describe('GroupPostDetail', () => {
  it.each([
    ['en', 'Join this group', 'Log in', 'Event Details', 'Pinned Post'],
    ['es', 'Únete a este grupo', 'Inicia sesión', 'Detalles del evento', 'Publicación fijada'],
  ])('%s: the comment prompt link carries its words', async (lang, joinText, loginText, details, pinned) => {
    await i18n.changeLanguage(lang);
    mockUser = { id: 9 };          // signed in, not a member
    const first = drawPost();
    await screen.findByText('Voy');
    expect(screen.getByText(details)).toBeInTheDocument();
    expect(screen.getByText(pinned)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: joinText })).toHaveAttribute('href', '/groups/1');
    first.unmount();

    mockUser = null;               // signed out
    drawPost();
    await screen.findByText('Voy');
    expect(screen.getByRole('link', { name: loginText })).toHaveAttribute('href', '/login');
  });

  it('shows Spanish dates and no raw key on the Spanish page', async () => {
    await i18n.changeLanguage('es');
    mockUser = { id: 9 };
    const { container } = drawPost();
    await screen.findByText('Voy');
    expect(container.textContent).toContain('septiembre');
    expect(container.textContent).not.toMatch(/September|Wednesday|Sep 30/);
    expect(container.textContent).not.toMatch(/\bgroups\.[a-zA-Z]/);
  });
});

describe('CreateGroup', () => {
  it.each([['en', 'log in'], ['es', 'Inicia sesión']])(
    '%s: the signed-out prompt link carries its words', async (lang, text) => {
      await i18n.changeLanguage(lang);
      render(<MemoryRouter><CreateGroup /></MemoryRouter>);
      expect(screen.getByRole('link', { name: text })).toHaveAttribute('href', '/login');
    },
  );
});
