// The admin API Usage page and the garden-manager messaging tab.
//
// Rendered rather than string-checked: this session's worst bug (the garden
// admin sidebar shipping as bare icons) passed every text-level check and was
// only visible on a rendered page.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const api = vi.hoisted(() => ({
  apiUsage: vi.fn(),
  managerAudienceOptions: vi.fn(),
  managerBroadcastPreview: vi.fn(),
  managerBroadcast: vi.fn(),
  managerBroadcasts: vi.fn(),
}));
vi.mock('../../api', () => ({ adminAPI: api }));
vi.mock('../../SiteConfigContext', () => ({
  useSiteConfig: () => ({ marketplaceEnabled: false, languages: ['en'] }),
}));
const dialogs = vi.hoisted(() => ({ toast: vi.fn(), confirmDialog: vi.fn() }));
vi.mock('../../components/dialog/dialogService', () => dialogs);

import AdminApiUsage from './AdminApiUsage';
import ManagerMessaging from './ManagerMessaging';

const wrap = (el) => render(<MemoryRouter>{el}</MemoryRouter>);

const usage = (over = {}) => ({
  days: 30,
  providers: [
    { provider: 'zeptomail', label: 'ZeptoMail (email)', calls: 40, units: 120,
      failed: 4, failure_rate: 0.1, cost_usd: 0.03 },
    { provider: 'anthropic', label: 'Anthropic (AI)', calls: 12, units: 12,
      failed: 0, failure_rate: 0, cost_usd: 1.84 },
  ],
  operations: [
    { provider: 'anthropic', operation: 'agent.follow_up', model: 'claude-sonnet-5',
      calls: 10, units: 10, failed: 0, cost_usd: 1.5, input_tokens: 90000, output_tokens: 4000 },
    { provider: 'zeptomail', operation: 'email.send', calls: 40, units: 120,
      failed: 4, cost_usd: 0.03, input_tokens: 0, output_tokens: 0 },
  ],
  daily: [{ day: new Date().toISOString().slice(0, 10), provider: 'zeptomail', calls: 40, cost_usd: 0.03, failed: 4 }],
  recent_failures: [{ at: new Date().toISOString(), provider: 'zeptomail', operation: 'email.send', error: 'HTTP 402' }],
  total_cost_usd: 1.87,
  monthly_run_rate_usd: 1.87,
  tracking_since: '2026-10-31T00:00:00+00:00',
  rates: { zeptomail_per_recipient: 0.00025, twilio_per_segment: 0.0123 },
  ...over,
});

beforeEach(() => { Object.values(api).forEach((f) => f.mockReset()); dialogs.toast.mockReset(); });

describe('API Usage page', () => {
  it('shows spend, run rate, and each provider', async () => {
    api.apiUsage.mockResolvedValue({ data: usage() });
    wrap(<AdminApiUsage />);
    expect(await screen.findByText('ZeptoMail (email)')).toBeInTheDocument();
    expect(screen.getByText('Anthropic (AI)')).toBeInTheDocument();
    expect(screen.getAllByText('$1.87').length).toBeGreaterThan(0);
    expect(screen.getByText('BDR agent — follow up')).toBeInTheDocument();
  });

  it('makes a failure rate visible, not just the spend', async () => {
    api.apiUsage.mockResolvedValue({ data: usage() });
    wrap(<AdminApiUsage />);
    expect(await screen.findByText(/4 failed \(10\.0%\)/)).toBeInTheDocument();
  });

  it('explains what HTTP 402 from ZeptoMail means', async () => {
    // The July outage: credits gone, every send failing, health probe green.
    api.apiUsage.mockResolvedValue({ data: usage() });
    wrap(<AdminApiUsage />);
    expect(await screen.findByText(/prepaid credits are exhausted/)).toBeInTheDocument();
  });

  it('says when nothing has been counted yet, instead of reading as zero', async () => {
    api.apiUsage.mockResolvedValue({ data: usage({
      providers: [], operations: [], daily: [], recent_failures: [],
      total_cost_usd: 0, monthly_run_rate_usd: 0, tracking_since: null,
    }) });
    wrap(<AdminApiUsage />);
    expect(await screen.findByText(/counting starts with the first one/)).toBeInTheDocument();
  });

  it('reloads for a different window', async () => {
    api.apiUsage.mockResolvedValue({ data: usage() });
    wrap(<AdminApiUsage />);
    await screen.findByText('ZeptoMail (email)');
    fireEvent.click(screen.getByRole('button', { name: '7 days' }));
    await waitFor(() => expect(api.apiUsage).toHaveBeenLastCalledWith({ days: 7 }));
  });
});

describe('Message garden managers', () => {
  const preview = (count = 2, suppressed = 1) => ({
    data: {
      count, suppressed, emailable: count - suppressed, est_email_cost_usd: 0.00025,
      truncated: false,
      recipients: [
        { id: 1, name: 'Mia Multi', email: 'mia@x.com', gardens: ['Apple', 'Bean'], suppressed: false },
        { id: 2, name: 'Sol Solo', email: 'sol@x.com', gardens: ['Corn'], suppressed: true },
      ].slice(0, count),
    },
  });

  beforeEach(() => {
    api.managerAudienceOptions.mockResolvedValue({ data: {
      states: ['IA', 'NE'], plan_counts: { active: 1, trialing: 1 },
      gardens: [{ id: 1, name: 'Apple', state: 'NE', plan: 'active' }],
    } });
    api.managerBroadcasts.mockResolvedValue({ data: { broadcasts: [] } });
  });

  const fill = () => {
    fireEvent.change(screen.getByLabelText('Subject'), { target: { value: 'Season update' } });
    fireEvent.change(screen.getByLabelText('Message'), { target: { value: 'Hello managers.' } });
  };

  it('will not send before the audience has been previewed', async () => {
    wrap(<ManagerMessaging />);
    await screen.findByText('NE');
    fill();
    expect(screen.getByRole('button', { name: /^Send/ })).toBeDisabled();
  });

  it('previews who it reaches, including who will not be emailed', async () => {
    api.managerBroadcastPreview.mockResolvedValue(preview());
    wrap(<ManagerMessaging />);
    await screen.findByText('NE');
    fireEvent.click(screen.getByRole('button', { name: /Preview recipients/ }));
    expect(await screen.findByText('2 people')).toBeInTheDocument();
    expect(screen.getByText(/1 unsubscribed or bounced/)).toBeInTheDocument();
    expect(screen.getByText('Mia Multi')).toBeInTheDocument();
  });

  it('sends the count it previewed, so the server can refuse a changed audience', async () => {
    api.managerBroadcastPreview.mockResolvedValue(preview());
    api.managerBroadcast.mockResolvedValue({ data: { broadcast: {
      recipient_count: 2, emailed: 1, notified: 2, email_failed: 0 } } });
    dialogs.confirmDialog.mockResolvedValue(true);
    wrap(<ManagerMessaging />);
    await screen.findByText('NE');
    fill();
    fireEvent.click(screen.getByRole('button', { name: /Preview recipients/ }));
    await screen.findByText('2 people');
    fireEvent.click(screen.getByRole('button', { name: 'Send to 2' }));
    await waitFor(() => expect(api.managerBroadcast).toHaveBeenCalled());
    const sent = api.managerBroadcast.mock.calls[0][0];
    expect(sent.expected_count).toBe(2);
    expect(sent.subject).toBe('Season update');
    expect(sent.channels).toEqual(['email', 'inapp']);
  });

  it('throws the preview away when the audience filters change', async () => {
    api.managerBroadcastPreview.mockResolvedValue(preview());
    wrap(<ManagerMessaging />);
    await screen.findByText('NE');
    fireEvent.click(screen.getByRole('button', { name: /Preview recipients/ }));
    await screen.findByText('2 people');
    fireEvent.click(screen.getByRole('button', { name: 'NE' }));   // narrow to Nebraska
    await waitFor(() => expect(screen.queryByText('2 people')).toBeNull());
  });

  it('does nothing if the confirmation is declined', async () => {
    api.managerBroadcastPreview.mockResolvedValue(preview());
    dialogs.confirmDialog.mockResolvedValue(false);
    wrap(<ManagerMessaging />);
    await screen.findByText('NE');
    fill();
    fireEvent.click(screen.getByRole('button', { name: /Preview recipients/ }));
    await screen.findByText('2 people');
    fireEvent.click(screen.getByRole('button', { name: 'Send to 2' }));
    await waitFor(() => expect(dialogs.confirmDialog).toHaveBeenCalled());
    expect(api.managerBroadcast).not.toHaveBeenCalled();
  });
});
