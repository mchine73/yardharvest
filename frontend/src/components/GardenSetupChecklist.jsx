import { useState } from 'react';
import { Link } from 'react-router-dom';
import { toast } from './dialog/dialogService';
import { gardenHasPro } from '../pro';
import { useTranslation } from 'react-i18next';

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

export default function GardenSetupChecklist({ garden, payouts, connectStatus,
                                              canSetUpPayouts = true, onGoToTab }) {
  const { t } = useTranslation();
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
  // Connect state, preferring what the account.updated webhook mirrored
  // (no Stripe round-trip, says *why*, readable by delegates) and falling back
  // to the live payout check for gardens whose webhook hasn't landed yet.
  const connectState = connectStatus?.state
    || (payouts?.ready ? 'ok'
      : payouts?.onboarded ? 'action_needed'
        : payouts?.configured === false ? 'unknown' : 'not_started');
  const payoutsReady = connectState === 'ok';
  const planActive = gardenHasPro(garden);

  // "Set up payouts" is one step with four quite different meanings, and a
  // checklist that says only "not done" for a *restricted* account sends
  // someone to redo onboarding they already finished.
  const payoutCopy = {
    not_started: {
      title: t('setup.payoutsTitle'),
      desc: t('setup.payoutsDesc'),
      cta: t('setup.payoutsTitle'),
    },
    action_needed: {
      title: t('setup.payoutsFinishTitle'),
      desc: connectStatus?.payouts_enabled === false && connectStatus?.charges_enabled
        ? t('setup.payoutsFinishChargesDesc')
        : t('setup.payoutsFinishDesc'),
      cta: t('setup.payoutsFinishCta'),
    },
    restricted: {
      title: t('setup.payoutsPausedTitle'),
      desc: t('setup.payoutsPausedDesc'),
      cta: t('setup.payoutsPausedCta'),
    },
    ok: {
      title: t('setup.payoutsTitle'),
      desc: t('setup.payoutsOkDesc'),
      cta: t('setup.payoutsOkCta'),
    },
    unknown: {
      title: t('setup.payoutsTitle'),
      desc: t('setup.payoutsDesc'),
      cta: t('setup.payoutsTitle'),
    },
  }[connectState] || {};

  const outstanding = (connectStatus?.requirements_due || []).slice(0, 2)
    .map((r) => r.replace(/[._]/g, ' '));

  const inviteUrl = pubId ? `${window.location.origin}/gardens/${pubId}` : '';
  const copyInvite = async () => {
    try {
      await navigator.clipboard.writeText(inviteUrl);
      toast(t('setup.inviteCopied'), { type: 'success' });
    } catch {
      toast(inviteUrl, { type: 'info' });
    }
  };

  const steps = [
    {
      key: 'basics', done: hasBasics,
      title: t('setup.stepProfile'),
      desc: t('setup.stepProfileDesc'),
      action: (
        <button className="btn btn-sm" style={outlineBtn} onClick={() => onGoToTab('settings')}>
          {t('setup.stepProfileCta')}
        </button>
      ),
    },
    {
      key: 'plots', done: hasPlots,
      title: t('setup.stepPlots'),
      desc: t('setup.stepPlotsDesc'),
      action: (
        <button className="btn btn-sm" style={outlineBtn} onClick={() => onGoToTab('plots')}>
          {t('setup.stepPlotsCta')}
        </button>
      ),
    },
    {
      key: 'members', done: hasMembers,
      title: t('setup.stepInvite'),
      desc: t('setup.stepInviteDesc'),
      action: (
        <div className="d-flex gap-2 flex-wrap">
          <button className="btn btn-sm" style={limeBtn} onClick={copyInvite}>
            <i className="bi bi-link-45deg me-1"></i>{t('setup.copyInvite')}
          </button>
          <button className="btn btn-sm" style={outlineBtn} onClick={() => onGoToTab('members')}>
            {t('setup.viewMembers')}
          </button>
        </div>
      ),
    },
    {
      key: 'payouts', done: payoutsReady,
      title: payoutCopy.title,
      desc: payoutCopy.desc,
      note: outstanding.length ? `Stripe still needs: ${outstanding.join(', ')}` : null,
      action: canSetUpPayouts ? (
        // Straight into the Connect flow rather than onto a page they then
        // have to navigate; the billing page opens onboarding on ?onboard=1.
        <Link className="btn btn-sm"
              style={connectState === 'ok' ? outlineBtn : limeBtn}
              to={`/gardens/${pubId}/billing${connectState === 'ok' ? '' : '?onboard=1'}`}>
          {connectState !== 'ok' && <i className="bi bi-bank me-1"></i>}
          {payoutCopy.cta}
        </Link>
      ) : (
        // Payout setup is organizer-only, so a delegate gets the status
        // without a link that would 403 on arrival.
        <span className="text-muted small">
          <i className="bi bi-lock me-1"></i>{t('setup.ownerOnly')}
        </span>
      ),
    },
    {
      key: 'plan', done: planActive,
      title: t('setup.stepTrial'),
      desc: t('setup.stepTrialDesc'),
      action: (
        <Link className="btn btn-sm" style={limeBtn} to={`/gardens/${pubId}/billing`}>
          {t('setup.startTrial')}
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
        {t('setup.setupShort', { done: doneCount, total: steps.length })}
        <span className="fw-semibold text-decoration-underline">{t('setup.resume')}</span>
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
              {t('setup.ready')}
            </h5>
            <div style={{ fontSize: '0.85rem', color: '#6b7280' }}>
              {t('setup.progress', { done: doneCount, total: steps.length })}
            </div>
          </div>
          <button
            type="button"
            className="btn-close"
            aria-label={t('setup.dismissGuide')}
            title={t('dash.dismiss')}
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
                    {s.note && (
                      <div style={{ fontSize: '0.78rem', color: '#9ca3af', marginBottom: '0.4rem' }}>
                        {s.note}
                      </div>
                    )}
                    {s.action}
                  </>
                )}
              </div>
              {s.done && (
                <span className="badge align-self-center" style={{ background: 'var(--yh-lime)', color: 'var(--yh-ink)' }}>{t('setup.done')}</span>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
