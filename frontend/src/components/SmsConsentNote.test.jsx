import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import SmsConsentNote from './SmsConsentNote';

describe('SmsConsentNote', () => {
  const renderNote = () =>
    render(
      <MemoryRouter>
        <SmsConsentNote />
      </MemoryRouter>
    );

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
