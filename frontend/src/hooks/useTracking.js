import { useCallback, useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { hasConsent } from '../components/CookieConsent';

const SESSION_KEY = 'yh_session_id';

function getSessionId() {
  let id = localStorage.getItem(SESSION_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(SESSION_KEY, id);
  }
  return id;
}

function getDeviceType() {
  const ua = navigator.userAgent;
  if (/Mobi|Android/i.test(ua)) return 'mobile';
  if (/Tablet|iPad/i.test(ua)) return 'tablet';
  return 'desktop';
}

async function sendEvent(eventType, metadata = null, pageUrl = null) {
  if (!hasConsent()) return;
  try {
    await fetch('/api/analytics/event', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        event_type: eventType,
        session_id: getSessionId(),
        page_url: pageUrl || window.location.pathname,
        referrer: document.referrer || '',
        metadata,
        device_type: getDeviceType(),
      }),
    });
  } catch {
    // Silently fail — analytics should never break the app
  }
}

export function trackEvent(eventType, metadata = null) {
  sendEvent(eventType, metadata);
}

export function usePageTracking() {
  const location = useLocation();
  const prevPath = useRef(null);

  useEffect(() => {
    if (location.pathname !== prevPath.current) {
      prevPath.current = location.pathname;
      sendEvent('page_view', null, location.pathname + location.search);
    }
  }, [location]);
}

export default function useTracking() {
  const track = useCallback((eventType, metadata = null) => {
    sendEvent(eventType, metadata);
  }, []);

  return { trackEvent: track };
}
