import { describe, it, expect, beforeEach, afterAll } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import i18n from '../i18n';
import SmsConsentNote from './SmsConsentNote';

const renderNote = () =>
  render(
    <MemoryRouter>
      <SmsConsentNote />
    </MemoryRouter>
  );

// The disclosure is now translated, so anything asserting the English wording
// has to say which language it is asserting.
beforeEach(async () => { await i18n.changeLanguage('en'); });
afterAll(async () => { await i18n.changeLanguage('en'); });

describe('SmsConsentNote', () => {
  it('discloses the required SMS consent terms (rates, frequency, STOP/HELP)', () => {
    renderNote();
    expect(screen.getByText(/Message & data rates may apply/i)).toBeInTheDocument();
    expect(screen.getByText(/Message frequency varies/i)).toBeInTheDocument();
    expect(screen.getByText(/Reply STOP to opt out, HELP for help/i)).toBeInTheDocument();
    expect(screen.getByText(/not a condition of any purchase/i)).toBeInTheDocument();
  });

  it('links to the Privacy Policy and Terms', () => {
    renderNote();
    expect(screen.getByRole('link', { name: /privacy policy/i })).toHaveAttribute('href', '/privacy');
    expect(screen.getByRole('link', { name: /terms of service/i })).toHaveAttribute('href', '/terms');
  });
});

// ---------------------------------------------------------------------------
// The <Trans> index trap
// ---------------------------------------------------------------------------
// <Trans> maps <1>, <3> in the catalog onto the *children* of the JSX element,
// and a `{' '}` expression container counts as a child. Writing
//
//     ... and{' '}
//     <Link to="/terms">Terms of Service</Link>
//
// makes the Terms link child 4, so a catalog string saying <3> renders the
// whitespace instead and the link silently disappears — in every language at
// once. The catalog tests cannot see it: they compare en against es, and both
// were equally wrong.
//
// It matters most here of anywhere it could happen: this disclosure is what
// TCPA / 10DLC opt-in rests on, and a consent notice missing its link to the
// Terms no longer discloses what it says it does.
describe.each(['en', 'es'])('rendered in %s', (lang) => {
  beforeEach(async () => { await i18n.changeLanguage(lang); });

  it('renders both links with text inside them', () => {
    renderNote();
    const privacy = document.querySelector('a[href="/privacy"]');
    const terms = document.querySelector('a[href="/terms"]');
    expect(privacy).toBeTruthy();
    expect(terms).toBeTruthy();
    // The bug produced an EMPTY link, not a missing one.
    expect(privacy.textContent.trim().length).toBeGreaterThan(3);
    expect(terms.textContent.trim().length).toBeGreaterThan(3);
  });

  it('never leaks a Trans placeholder to the reader', () => {
    renderNote();
    expect(document.body.textContent).not.toMatch(/<\/?\d+>/);
  });

  it('keeps the carrier keywords literal', () => {
    // STOP and HELP are matched by the carrier, not read as words. A
    // translated "STOP" unsubscribes nobody.
    renderNote();
    const text = document.body.textContent;
    expect(text).toContain('STOP');
    expect(text).toContain('HELP');
    expect(text).toContain('YardHarvest');
  });
});

describe('the Spanish is a translation, not a copy', () => {
  it('differs from the English', async () => {
    await i18n.changeLanguage('en');
    const { unmount } = renderNote();
    const en = document.body.textContent;
    unmount();
    await i18n.changeLanguage('es');
    renderNote();
    expect(document.body.textContent).not.toBe(en);
  });
});
