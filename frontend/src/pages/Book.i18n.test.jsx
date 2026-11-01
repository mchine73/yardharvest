// The public /book scheduler and its manage link, in both languages.
//
// The operator's heading, intro and meeting-type names come from the booking
// settings and stay as written; everything around them is ours. A Spanish
// page also says, once, that the call itself is in English.
import { describe, it, expect, vi, beforeAll, afterAll } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

import Book from './Book';
import BookManage from './BookManage';
import i18n from '../i18n';

vi.mock('../components/Seo', () => ({
  default: ({ title, description }) => (
    <div data-testid="seo" data-title={title} data-description={description || ''} />
  ),
}));

vi.mock('../api', () => {
  const type = { slug: 'intro', name: 'Intro call', duration_min: 30, color: '#3a3', location: 'Zoom', description: 'A quick chat.' };
  return {
    bookingAPI: {
      config: vi.fn().mockResolvedValue({
        data: {
          settings: { heading: 'Book time with me', owner_name: 'James Goodman', intro: 'Pick a meeting type and a time that works for you.' },
          types: [type],
        },
      }),
      slots: vi.fn().mockResolvedValue({
        data: { type, owner_timezone: 'America/Chicago', slots: ['2026-11-10T15:00:00Z', '2026-11-10T16:00:00Z'] },
      }),
      getManage: vi.fn().mockResolvedValue({
        data: {
          booking: {
            public_id: 'abc', type_name: 'Intro call', start_at: '2026-11-10T15:00:00Z', duration_min: 30,
            invitee_timezone: 'America/Chicago', invitee_name: 'Ana', invitee_email: 'ana@example.com',
            location: 'Zoom', status: 'confirmed',
          },
        },
      }),
    },
  };
});

function survivors(text) {
  const en = i18n.getResourceBundle('en', 'common').book;
  const es = i18n.getResourceBundle('es', 'common').book;
  return Object.keys(en).filter((k) => {
    const v = en[k];
    if (/\{\{|</.test(v) || es[k].includes(v)) return false;
    const esc = v.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return new RegExp(`(^|[^\\p{L}])${esc}([^\\p{L}]|$)`, 'u').test(text);
  });
}

async function drawBook(lang) {
  await i18n.changeLanguage(lang);
  const utils = render(
    <MemoryRouter initialEntries={['/book']}>
      <Routes><Route path="/book" element={<Book />} /></Routes>
    </MemoryRouter>,
  );
  // One meeting type, so the page goes straight to the calendar (the month
  // navigation appears once the slots have loaded).
  await screen.findByLabelText(lang === 'es' ? 'Mes anterior' : 'Previous month');
  return utils;
}

describe('Book i18n', () => {
  // The mocked slots are on 10 Nov 2026. Pin the clock (only Date, so the
  // async waits keep real timers) or the page treats them as past once the
  // calendar catches up with them.
  beforeAll(() => {
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date('2026-11-01T18:00:00Z'));
  });
  afterAll(() => vi.useRealTimers());

  it('renders English, without the language note', async () => {
    const { container } = await drawBook('en');
    const seo = screen.getByTestId('seo');
    expect(seo.dataset.title).toBe('Book time with James');
    expect(seo.dataset.description).toBe(
      'Schedule a 30-minute intro call about YardHarvest — pick any open time that works for you, no back-and-forth.');
    const text = container.textContent;
    expect(text).toContain('with James Goodman');
    expect(text).toContain('Times shown in');
    expect(text).toContain('30 min');
    expect(text).not.toContain('The call is held in English.');
  });

  it('renders Spanish through the calendar and the details form', async () => {
    const { container } = await drawBook('es');
    expect(screen.getByTestId('seo').dataset.title).toBe('Reserva una llamada con James');
    let text = container.textContent;
    for (const s of ['con James Goodman', 'La llamada es en inglés.', 'Horarios en', '30 minutos',
      'Lu', 'Sá', 'noviembre de 2026']) {
      expect(text).toContain(s);
    }
    expect(screen.getByLabelText('Mes anterior')).toBeInTheDocument();
    expect(survivors(text)).toEqual([]);

    // Pick the first time: the details form.
    // The time buttons render a beat after the month navigation does.
    const slot = await waitFor(() => {
      const b = [...container.querySelectorAll('.btn-outline-success:not([disabled])')]
        .find((el) => /\d:\d\d/.test(el.textContent));
      expect(b).toBeTruthy();
      return b;
    });
    fireEvent.click(slot);
    await screen.findByText('Elegir otro horario');
    text = container.textContent;
    for (const s of ['Nombre *', 'Correo electrónico *', 'Teléfono', '(opcional)',
      '¿Hay algo que quieras compartir?', 'Confirmar la reserva', 'martes, 10 de noviembre']) {
      expect(text).toContain(s);
    }
    expect(survivors(text)).toEqual([]);
    expect(text).not.toMatch(/\bbook\.[a-zA-Z]/);
  });
});

describe('BookManage i18n', () => {
  async function drawManage(lang) {
    await i18n.changeLanguage(lang);
    const utils = render(
      <MemoryRouter initialEntries={['/book/manage/abc']}>
        <Routes><Route path="/book/manage/:publicId" element={<BookManage />} /></Routes>
      </MemoryRouter>,
    );
    await screen.findByText('Intro call');
    return utils;
  }

  it('renders English', async () => {
    const { container } = await drawManage('en');
    expect(container.textContent).toContain('Booked by Ana (ana@example.com)');
    expect(container.textContent).toContain('Cancel this booking');
  });

  it('renders Spanish', async () => {
    const { container } = await drawManage('es');
    const text = container.textContent;
    for (const s of ['Administra tu reserva', 'Reservada por Ana (ana@example.com)', '30 minutos',
      'Reservar otro horario', 'Cancelar esta reserva', 'de noviembre de 2026']) {
      expect(text).toContain(s);
    }
    fireEvent.click(screen.getByText('Cancelar esta reserva'));
    const after = container.textContent;
    expect(after).toContain('¿Cancelar esta reserva? No se puede deshacer.');
    expect(after).toContain('Sí, cancelar');
    expect(after).toContain('Mantenerla');
    expect(survivors(after)).toEqual([]);
  });
});
