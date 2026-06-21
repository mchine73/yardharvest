import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import GardenSetupChecklist from './GardenSetupChecklist';

const renderChecklist = (garden, payouts) =>
  render(
    <MemoryRouter>
      <GardenSetupChecklist garden={garden} payouts={payouts} onGoToTab={vi.fn()} />
    </MemoryRouter>
  );

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
    expect(screen.getByRole('link', { name: /Finish payout setup/ })).toBeInTheDocument();
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
    expect(screen.getByRole('link', { name: /Finish payout setup/ })).toBeInTheDocument();
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

  it('stays hidden after being dismissed for that garden', () => {
    localStorage.setItem('yh-setup-dismissed-grd_hidden', '1');
    renderChecklist(
      {
        public_id: 'grd_hidden', description: 'd', city: 'c',
        total_plots: 0, member_count: 0, waitlist_count: 0, subscription_status: 'none',
      },
      { configured: true, ready: false }
    );
    expect(screen.queryByText('Get your garden ready')).not.toBeInTheDocument();
  });
});
