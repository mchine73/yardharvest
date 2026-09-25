import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';

const CONSENT_KEY = 'yh_consent';
const CHANGED_EVENT = 'yh:consent-changed';

/**
 * Reopen the banner so a choice can be changed.
 *
 * GDPR Art. 7(3): withdrawing consent must be as easy as giving it. Before
 * this there was no way to withdraw at all short of clearing site data, while
 * the banner told people they could "change this anytime in your settings" —
 * a setting that did not exist. The footer link is that setting.
 */
export function openCookieSettings() {
  window.dispatchEvent(new CustomEvent(CHANGED_EVENT, { detail: { reopen: true } }));
}

export function hasConsent() {
  try {
    return localStorage.getItem(CONSENT_KEY) === 'accepted';
  } catch {
    // Private browsing, or storage blocked. No stored consent means no
    // consent — analytics stays off rather than defaulting on.
    return false;
  }
}

/** The stored answer, or null if they have not been asked yet. */
export function consentChoice() {
  try {
    const v = localStorage.getItem(CONSENT_KEY);
    return v === 'accepted' || v === 'declined' ? v : null;
  } catch {
    return null;
  }
}

export default function CookieConsent() {
  const [visible, setVisible] = useState(false);
  const [choice, setChoice] = useState(consentChoice());

  useEffect(() => {
    // Reopened from the footer: always show, even if already answered.
    const onReopen = () => { setChoice(consentChoice()); setVisible(true); };
    window.addEventListener(CHANGED_EVENT, onReopen);
    return () => window.removeEventListener(CHANGED_EVENT, onReopen);
  }, []);

  useEffect(() => {
    if (consentChoice()) return;   // already answered

    fetch('/api/analytics/config')
      .then(r => r.json())
      .then(data => {
        if (!data.cookie_consent_required) {
          try { localStorage.setItem(CONSENT_KEY, 'accepted'); } catch { /* ignore */ }
          return;
        }
        setVisible(true);
      })
      // If we cannot tell whether consent is required, ask. Failing to the
      // question is the only safe direction.
      .catch(() => setVisible(true));
  }, []);

  const save = useCallback((value) => {
    try {
      localStorage.setItem(CONSENT_KEY, value);
      if (value === 'accepted') {
        if (!localStorage.getItem('yh_session_id')) {
          localStorage.setItem('yh_session_id', crypto.randomUUID());
        }
      } else {
        // Withdrawal has to actually remove the identifier, not just stop
        // sending it — otherwise the same visitor is re-identified the
        // moment they change their mind back.
        localStorage.removeItem('yh_session_id');
      }
    } catch { /* storage blocked — nothing is stored, so nothing is tracked */ }
    setChoice(value);
    setVisible(false);
  }, []);

  if (!visible) return null;

  const btn = {
    padding: '10px 24px', borderRadius: '8px', cursor: 'pointer',
    fontSize: '0.9rem', fontWeight: 700, border: '2px solid transparent',
  };

  return (
    <div
      role="dialog"
      aria-modal="false"
      aria-label="Cookie choices"
      style={{
        position: 'fixed', bottom: 0, left: 0, right: 0, zIndex: 9999,
        background: '#22242a', color: 'white', padding: '16px 24px',
        boxShadow: '0 -4px 20px rgba(0,0,0,0.15)',
        display: 'flex', justifyContent: 'center', alignItems: 'center',
        gap: '16px', flexWrap: 'wrap',
      }}
    >
      <div style={{ flex: 1, minWidth: '260px', maxWidth: '600px' }}>
        <div style={{ fontWeight: 600, marginBottom: '4px', fontSize: '0.95rem' }}>
          <i className="bi bi-shield-check me-2"></i>Your privacy
        </div>
        <div style={{ fontSize: '0.85rem', opacity: 0.9, lineHeight: 1.4 }}>
          We use first-party analytics to understand how YardHarvest is used.
          No data is shared with advertisers. Declining changes nothing about
          how the site works. You can change your mind from{' '}
          <strong>Cookie settings</strong> at the bottom of any page, or read
          our <Link to="/privacy" style={{ color: '#e3ff8f' }}>Privacy Policy</Link>.
          {choice && (
            <div style={{ marginTop: '6px', opacity: 0.75 }}>
              Currently: <strong>{choice === 'accepted' ? 'accepted' : 'declined'}</strong>.
            </div>
          )}
        </div>
      </div>
      {/* Both choices are one click, the same size, in the same place. A
          "decline" hidden behind an extra step is not freely given consent. */}
      <div style={{ display: 'flex', gap: '8px', flexShrink: 0 }}>
        <button onClick={() => save('accepted')}
                style={{ ...btn, background: '#e3ff8f', color: '#22242a' }}>
          Accept
        </button>
        <button onClick={() => save('declined')}
                style={{ ...btn, background: 'transparent', color: 'white',
                         borderColor: 'rgba(255,255,255,0.5)' }}>
          Decline
        </button>
      </div>
    </div>
  );
}
