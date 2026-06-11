import { useState, useEffect } from 'react';
import api from '../api';

const CONSENT_KEY = 'yh_consent';

export default function CookieConsent() {
  const [visible, setVisible] = useState(false);
  const [consentRequired, setConsentRequired] = useState(true);

  useEffect(() => {
    const stored = localStorage.getItem(CONSENT_KEY);
    if (stored === 'accepted' || stored === 'declined') return;

    // Check if consent is required from server config
    fetch('/api/analytics/config')
      .then(r => r.json())
      .then(data => {
        if (!data.cookie_consent_required) {
          localStorage.setItem(CONSENT_KEY, 'accepted');
          return;
        }
        setConsentRequired(true);
        setVisible(true);
      })
      .catch(() => setVisible(true));
  }, []);

  const accept = () => {
    localStorage.setItem(CONSENT_KEY, 'accepted');
    if (!localStorage.getItem('yh_session_id')) {
      localStorage.setItem('yh_session_id', crypto.randomUUID());
    }
    setVisible(false);
  };

  const decline = () => {
    localStorage.setItem(CONSENT_KEY, 'declined');
    localStorage.removeItem('yh_session_id');
    setVisible(false);
  };

  if (!visible) return null;

  return (
    <div style={{
      position: 'fixed', bottom: 0, left: 0, right: 0, zIndex: 9999,
      background: 'linear-gradient(135deg, #166f4c, #1d8a5f)',
      color: 'white', padding: '16px 24px',
      boxShadow: '0 -4px 20px rgba(0,0,0,0.15)',
      display: 'flex', justifyContent: 'center', alignItems: 'center',
      gap: '16px', flexWrap: 'wrap',
    }}>
      <div style={{ flex: 1, minWidth: '260px', maxWidth: '600px' }}>
        <div style={{ fontWeight: 600, marginBottom: '4px', fontSize: '0.95rem' }}>
          <i className="bi bi-shield-check me-2"></i>Your Privacy Matters
        </div>
        <div style={{ fontSize: '0.85rem', opacity: 0.9, lineHeight: 1.4 }}>
          We use first-party analytics cookies to understand how you use YardHarvest and improve your experience.
          No data is shared with third parties. You can change this anytime in your settings.
        </div>
      </div>
      <div style={{ display: 'flex', gap: '8px', flexShrink: 0 }}>
        <button onClick={accept} style={{
          padding: '10px 24px', borderRadius: '8px', border: 'none',
          background: '#d99a2b', color: '#16181d', fontWeight: 700,
          cursor: 'pointer', fontSize: '0.9rem',
        }}>
          <i className="bi bi-check-lg me-1"></i>Accept
        </button>
        <button onClick={decline} style={{
          padding: '10px 24px', borderRadius: '8px',
          border: '2px solid rgba(255,255,255,0.5)', background: 'transparent',
          color: 'white', fontWeight: 600, cursor: 'pointer', fontSize: '0.9rem',
        }}>
          Decline
        </button>
      </div>
    </div>
  );
}

export function hasConsent() {
  return localStorage.getItem(CONSENT_KEY) === 'accepted';
}
