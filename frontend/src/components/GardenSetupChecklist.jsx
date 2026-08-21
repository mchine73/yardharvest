import { useState } from 'react';
import { Link } from 'react-router-dom';
import { toast } from './dialog/dialogService';
import { gardenHasPro } from '../pro';

// First-run operator setup guide shown atop the admin dashboard. It computes
// completion from data the dashboard already loads (garden detail + payout
// status) — no extra fetch — and auto-hides once every step is done. An
// operator who'd rather not finish yet can dismiss it (remembered per garden
// in localStorage); it reappears on another device or after clearing storage,
// which is fine for a best-effort nudge.

const DISMISS_PREFIX = 'yh-setup-dismissed-';

const cardStyle = {
  border: '1px solid var(--yh-border)',
  borderRadius: '16px',
  boxShadow: 'none',
  background: 'var(--yh-surface-2)',
  borderLeft: '4px solid var(--yh-lime)',
};
const limeBtn = { backgroundColor: 'var(--yh-lime)', color: 'var(--yh-ink)', border: '1px solid var(--yh-lime)', fontWeight: 500 };
const outlineBtn = { border: '1px solid var(--yh-border)', color: 'var(--yh-ink)', backgroundColor: '#fff', fontWeight: 500 };

export default function GardenSetupChecklist({ garden, payouts, onGoToTab }) {
  const pubId = garden?.public_id;
  const dismissKey = DISMISS_PREFIX + pubId;
  const [dismissed, setDismissed] = useState(() => {
    try { return localStorage.getItem(dismissKey) === '1'; } catch { return false; }
  });

  if (!garden) return null;

  // ---- Step completion, derived from already-loaded data ----
  const hasBasics = !!(garden.description && (garden.address || garden.city));
  const plotCount = (garden.total_plots || 0)
    || ((garden.available_plots || 0) + (garden.assigned_plots || 0));
  const hasPlots = plotCount > 0;
  const hasMembers = (garden.member_count || 0) > 0 || (garden.waitlist_count || 0) > 0;
  const payoutsReady = !!(payouts && payouts.ready);
  const planActive = gardenHasPro(garden);

  const inviteUrl = pubId ? `${window.location.origin}/gardens/${pubId}` : '';
  const copyInvite = async () => {
    try {
      await navigator.clipboard.writeText(inviteUrl);
      toast('Invite link copied — share it with your gardeners.', { type: 'success' });
    } catch {
      toast(inviteUrl, { type: 'info' });
    }
  };

  const steps = [
    {
      key: 'basics', done: hasBasics,
      title: 'Complete your garden profile',
      desc: 'Add a description and location so gardeners know what to expect.',
      action: (
        <button className="btn btn-sm" style={outlineBtn} onClick={() => onGoToTab('settings')}>
          Edit profile
        </button>
      ),
    },
    {
      key: 'plots', done: hasPlots,
      title: 'Add your plots',
      desc: 'Lay out the plots members can claim — bulk-add and arrange them on a grid.',
      action: (
        <button className="btn btn-sm" style={outlineBtn} onClick={() => onGoToTab('plots')}>
          Manage plots
        </button>
      ),
    },
    {
      key: 'members', done: hasMembers,
      title: 'Invite your members',
      desc: 'Share your garden link so gardeners can claim a plot or join the waitlist.',
      action: (
        <div className="d-flex gap-2 flex-wrap">
          <button className="btn btn-sm" style={limeBtn} onClick={copyInvite}>
            <i className="bi bi-link-45deg me-1"></i>Copy invite link
          </button>
          <button className="btn btn-sm" style={outlineBtn} onClick={() => onGoToTab('members')}>
            View members
          </button>
        </div>
      ),
    },
    {
      key: 'payouts', done: payoutsReady,
      title: 'Set up payouts',
      desc: 'Connect a Stripe account so collected member dues are paid out to you.',
      action: (
        <Link className="btn btn-sm" style={outlineBtn} to={`/gardens/${pubId}/billing`}>
          Finish payout setup
        </Link>
      ),
    },
    {
      key: 'plan', done: planActive,
      title: 'Start your Garden Pro trial',
      desc: 'Unlock dues collection, the photo wall, and tool checkout with a 14-day free trial.',
      action: (
        <Link className="btn btn-sm" style={limeBtn} to={`/gardens/${pubId}/billing`}>
          Start free trial
        </Link>
      ),
    },
  ];

  const doneCount = steps.filter(s => s.done).length;
  const allDone = doneCount === steps.length;
  if (allDone) return null;

  const pct = Math.round((doneCount / steps.length) * 100);
  const dismiss = () => {
    try { localStorage.setItem(dismissKey, '1'); } catch { /* ignore */ }
    setDismissed(true);
  };

  // Dismissed with steps remaining: collapse to a one-line pill instead of
  // vanishing — the invite link and payout setup used to become unreachable.
  if (dismissed) {
    return (
      <button
        type="button"
        className="btn btn-sm mb-4 d-inline-flex align-items-center gap-2"
        style={{ ...outlineBtn, borderRadius: 999 }}
        onClick={() => { try { localStorage.removeItem(dismissKey); } catch { /* ignore */ } setDismissed(false); }}
      >
        <i className="bi bi-rocket-takeoff" style={{ color: 'var(--brand-secondary)' }}></i>
        Setup: {doneCount} of {steps.length} done
        <span className="fw-semibold text-decoration-underline">Resume</span>
      </button>
    );
  }

  return (
    <div className="card mb-4" style={cardStyle}>
      <div className="card-body p-3 p-md-4">
        <div className="d-flex justify-content-between align-items-start mb-2">
          <div>
            <h5 className="fw-bold mb-1" style={{ color: 'var(--text-dark)' }}>
              <i className="bi bi-rocket-takeoff me-2" style={{ color: 'var(--brand-secondary)' }}></i>
              Get your garden ready
            </h5>
            <div style={{ fontSize: '0.85rem', color: '#6b7280' }}>
              {doneCount} of {steps.length} steps complete — finish setup to start welcoming members.
            </div>
          </div>
          <button
            type="button"
            className="btn-close"
            aria-label="Dismiss setup guide"
            title="Dismiss"
            onClick={dismiss}
          ></button>
        </div>

        <div className="progress mb-4" style={{ height: '8px', borderRadius: '999px', background: 'var(--yh-border)' }}>
          <div
            className="progress-bar"
            role="progressbar"
            aria-valuenow={pct}
            aria-valuemin={0}
            aria-valuemax={100}
            style={{ width: `${pct}%`, background: 'var(--yh-lime)', borderRadius: '999px' }}
          ></div>
        </div>

        <div className="d-flex flex-column gap-3">
          {steps.map((s, i) => (
            <div key={s.key} className="d-flex align-items-start gap-3">
              <div
                className="d-flex align-items-center justify-content-center flex-shrink-0"
                style={{
                  width: '30px', height: '30px', borderRadius: '50%',
                  background: s.done ? 'var(--yh-lime)' : '#fff',
                  border: `1px solid ${s.done ? 'var(--yh-lime)' : 'var(--yh-border)'}`,
                  color: 'var(--yh-ink)', fontWeight: 600, fontSize: '0.85rem',
                }}
              >
                {s.done ? <i className="bi bi-check-lg"></i> : i + 1}
              </div>
              <div className="flex-grow-1">
                <div
                  className="fw-semibold"
                  style={{ color: 'var(--text-dark)', textDecoration: s.done ? 'line-through' : 'none', opacity: s.done ? 0.6 : 1 }}
                >
                  {s.title}
                </div>
                {!s.done && (
                  <>
                    <div style={{ fontSize: '0.82rem', color: '#6b7280', marginBottom: '0.4rem' }}>{s.desc}</div>
                    {s.action}
                  </>
                )}
              </div>
              {s.done && (
                <span className="badge align-self-center" style={{ background: 'var(--yh-lime)', color: 'var(--yh-ink)' }}>Done</span>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
