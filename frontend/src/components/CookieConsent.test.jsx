// Consent is a legal obligation, not a UI nicety, so the parts that carry the
// obligation are pinned here: withdrawal must be possible and as easy as
// consent (GDPR Art. 7(3)), declining must actually drop the identifier, and
// nothing may be treated as consent until someone says yes.
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import CookieConsent, { hasConsent, consentChoice, openCookieSettings } from './CookieConsent';

const show = () => render(<MemoryRouter><CookieConsent /></MemoryRouter>);

beforeEach(() => {
  localStorage.clear();
  global.fetch = vi.fn(() =>
    Promise.resolve({ json: () => Promise.resolve({ cookie_consent_required: true }) }));
});
afterEach(() => vi.restoreAllMocks());

describe('asking', () => {
  it('asks when no choice has been made', async () => {
    show();
    expect(await screen.findByText(/Accept/)).toBeTruthy();
  });

  it('treats silence as refusal', async () => {
    // An unanswered banner is not consent. Closing the tab without choosing
    // must leave analytics off.
    show();
    await screen.findByText(/Accept/);
    expect(hasConsent()).toBe(false);
  });

  it('asks when it cannot tell whether consent is required', async () => {
    global.fetch = vi.fn(() => Promise.reject(new Error('offline')));
    show();
    expect(await screen.findByText(/Accept/)).toBeTruthy();
  });

  it('offers accept and decline as equal, one-click choices', async () => {
    show();
    const accept = await screen.findByText('Accept');
    const decline = screen.getByText('Decline');
    // Both are buttons in the same row — a decline buried behind an extra
    // step is not freely given consent.
    expect(accept.tagName).toBe('BUTTON');
    expect(decline.tagName).toBe('BUTTON');
    expect(accept.parentElement).toBe(decline.parentElement);
  });

  it('links to the privacy policy', async () => {
    show();
    await screen.findByText('Accept');
    expect(document.querySelector('a[href="/privacy"]')).toBeTruthy();
  });
});

describe('choosing', () => {
  it('accepting stores consent and mints a session id', async () => {
    show();
    fireEvent.click(await screen.findByText('Accept'));
    await waitFor(() => expect(hasConsent()).toBe(true));
    expect(localStorage.getItem('yh_session_id')).toBeTruthy();
  });

  it('declining stores the refusal and mints nothing', async () => {
    show();
    fireEvent.click(await screen.findByText('Decline'));
    await waitFor(() => expect(consentChoice()).toBe('declined'));
    expect(localStorage.getItem('yh_session_id')).toBeNull();
  });

  it('does not ask again once answered', async () => {
    localStorage.setItem('yh_consent', 'declined');
    show();
    await new Promise((r) => setTimeout(r, 20));
    expect(screen.queryByText('Accept')).toBeNull();
  });
});

describe('withdrawing', () => {
  it('can be reopened after a choice was already made', async () => {
    // Art. 7(3): withdrawal must be as easy as giving consent. Before this
    // there was no way to withdraw short of clearing site data — while the
    // banner claimed you could change it "in your settings".
    localStorage.setItem('yh_consent', 'accepted');
    show();
    await new Promise((r) => setTimeout(r, 20));
    expect(screen.queryByText('Accept')).toBeNull();

    openCookieSettings();
    expect(await screen.findByText('Accept')).toBeTruthy();
  });

  it('shows what the current choice is', async () => {
    localStorage.setItem('yh_consent', 'accepted');
    show();
    openCookieSettings();
    await screen.findByText('Accept');
    expect(screen.getByText(/accepted/)).toBeTruthy();
  });

  it('withdrawing removes the identifier, not just future sends', async () => {
    // Otherwise the same visitor is re-identified the moment they change
    // their mind back, and the withdrawal was cosmetic.
    localStorage.setItem('yh_consent', 'accepted');
    localStorage.setItem('yh_session_id', 'existing-id');
    show();
    openCookieSettings();
    fireEvent.click(await screen.findByText('Decline'));
    await waitFor(() => expect(hasConsent()).toBe(false));
    expect(localStorage.getItem('yh_session_id')).toBeNull();
  });
});

describe('when storage is unavailable', () => {
  it('reports no consent rather than defaulting to yes', () => {
    const spy = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    expect(hasConsent()).toBe(false);
    expect(consentChoice()).toBeNull();
    spy.mockRestore();
  });
});
