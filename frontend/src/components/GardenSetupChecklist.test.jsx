import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import GardenSetupChecklist from './GardenSetupChecklist';

const renderChecklist = (garden, payouts, extra = {}) =>
  render(
    <MemoryRouter>
      <GardenSetupChecklist garden={garden} payouts={payouts}
                            onGoToTab={vi.fn()} {...extra} />
    </MemoryRouter>
  );

const OPEN_GARDEN = {
  public_id: 'grd_x', description: 'd', city: 'c',
  total_plots: 4, member_count: 2, waitlist_count: 0, subscription_status: 'trialing',
};

describe('GardenSetupChecklist', () => {
  beforeEach(() => {
    try { localStorage.clear(); } catch { /* jsdom */ }
  });

  it('shows incomplete steps with CTAs and a progress count', () => {
    // Only "basics" is done (has description + location); everything else open.
    renderChecklist(
      {
        public_id: 'grd_partial', description: 'A lovely plot', city: 'Omaha',
        total_plots: 0, member_count: 0, waitlist_count: 0, subscription_status: 'none',
      },
      { configured: true, ready: false }
    );

    expect(screen.getByText('Get your garden ready')).toBeInTheDocument();
    expect(screen.getByText(/1 of 5 steps complete/)).toBeInTheDocument();

    // Open steps render their action controls...
    expect(screen.getByRole('button', { name: /Manage plots/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Copy invite link/ })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Set up payouts/ })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Start free trial/ })).toBeInTheDocument();

    // ...but the completed "basics" step shows no action button.
    expect(screen.queryByRole('button', { name: 'Edit profile' })).not.toBeInTheDocument();
  });

  it('counts a trialing subscription as the plan step being done', () => {
    renderChecklist(
      {
        public_id: 'grd_trial', description: 'd', city: 'c',
        total_plots: 4, member_count: 2, waitlist_count: 0, subscription_status: 'trialing',
      },
      { configured: false, ready: false }
    );
    // basics + plots + members + plan done = 4/5 (only payouts remains).
    expect(screen.getByText(/4 of 5 steps complete/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Set up payouts/ })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /Start free trial/ })).not.toBeInTheDocument();
  });

  it('renders nothing once every step is complete', () => {
    renderChecklist(
      {
        public_id: 'grd_done', description: 'd', address: '1 Main St',
        total_plots: 10, member_count: 5, waitlist_count: 0, subscription_status: 'active',
      },
      { configured: true, ready: true }
    );
    expect(screen.queryByText('Get your garden ready')).not.toBeInTheDocument();
  });

  it('collapses to a resumable pill after being dismissed with steps remaining', () => {
    localStorage.setItem('yh-setup-dismissed-grd_hidden', '1');
    renderChecklist(
      {
        public_id: 'grd_hidden', description: 'd', city: 'c',
        total_plots: 0, member_count: 0, waitlist_count: 0, subscription_status: 'none',
      },
      { configured: true, ready: false }
    );
    expect(screen.queryByText('Get your garden ready')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Setup: 1 of 5 done/ })).toBeInTheDocument();
    expect(screen.getByText('Resume')).toBeInTheDocument();
  });
  // ---- Stripe Connect state -------------------------------------------------
  // "Set up payouts" is one step with four quite different meanings. Telling a
  // restricted account it simply hasn't done setup sends someone to redo
  // onboarding they already finished.

  it('distinguishes an unfinished account from one never started', () => {
    renderChecklist(OPEN_GARDEN, null, {
      connectStatus: {
        state: 'action_needed', charges_enabled: true, payouts_enabled: false,
        requirements_due: ['individual.verification.document'],
      },
    });
    expect(screen.getByText('Finish your payout setup')).toBeInTheDocument();
    expect(screen.getByText(/take payments, but Stripe still needs/)).toBeInTheDocument();
    // Name what is outstanding rather than making them go and find out.
    expect(screen.getByText(/individual verification document/)).toBeInTheDocument();
  });

  it('says so when Stripe has restricted the account', () => {
    renderChecklist(OPEN_GARDEN, null, {
      connectStatus: { state: 'restricted', requirements_due: [] },
    });
    expect(screen.getByText('Stripe has paused your payouts')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Open payout settings/ })).toBeInTheDocument();
  });

  it('sends an unfinished setup straight into the Connect flow', () => {
    renderChecklist(OPEN_GARDEN, null, { connectStatus: { state: 'not_started' } });
    // ?onboard=1 opens onboarding on arrival instead of dropping them on a page.
    expect(screen.getByRole('link', { name: /Set up payouts/ }))
      .toHaveAttribute('href', '/gardens/grd_x/billing?onboard=1');
  });

  it('counts the step done when the webhook says the account is ready', () => {
    renderChecklist(OPEN_GARDEN, null, { connectStatus: { state: 'ok' } });
    expect(screen.queryByText('Get your garden ready')).not.toBeInTheDocument();
  });

  it('shows a delegate the status without a link they cannot use', () => {
    // Payout setup is organizer-only, so a co-organizer gets the truth rather
    // than a button that 403s on arrival.
    renderChecklist(OPEN_GARDEN, null, {
      connectStatus: { state: 'not_started' }, canSetUpPayouts: false,
    });
    expect(screen.getByText(/Only the garden owner can set this up/)).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /Set up payouts/ })).not.toBeInTheDocument();
  });
});
