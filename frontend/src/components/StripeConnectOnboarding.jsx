import { useState, useEffect, useRef } from 'react';
import { loadConnectAndInitialize } from '@stripe/connect-js';
import { ConnectComponentsProvider, ConnectAccountOnboarding } from '@stripe/react-connect-js';

/**
 * In-app Stripe Connect onboarding (embedded components).
 *
 * Renders Stripe's account onboarding flow inside the page instead of
 * redirecting to a Stripe-hosted URL, so users never leave the app.
 *
 * Props:
 *  - fetchAccountSession: () => Promise<axios res> hitting an account-session
 *    endpoint that returns { client_secret, publishable_key }
 *  - onComplete: called when the user finishes/exits the onboarding flow
 *  - onError: called with an Error if the embedded flow cannot initialize
 *    (callers should fall back to the hosted onboarding link)
 */
export default function StripeConnectOnboarding({ fetchAccountSession, onComplete, onError }) {
  const [connectInstance, setConnectInstance] = useState(null);
  const [failed, setFailed] = useState(false);
  // The init call already returns a client secret; serve it to connect-js on
  // the first request, then mint fresh sessions on refresh.
  const firstSecret = useRef(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetchAccountSession();
        const { client_secret: clientSecret, publishable_key: publishableKey } = res.data;
        if (!clientSecret || !publishableKey) throw new Error('Account session unavailable');
        firstSecret.current = clientSecret;
        const instance = loadConnectAndInitialize({
          publishableKey,
          fetchClientSecret: async () => {
            if (firstSecret.current) {
              const secret = firstSecret.current;
              firstSecret.current = null;
              return secret;
            }
            const r = await fetchAccountSession();
            return r.data.client_secret;
          },
          appearance: {
            variables: {
              colorPrimary: '#166f4c',
              fontFamily: 'Inter, sans-serif',
              borderRadius: '8px',
            },
          },
        });
        if (!cancelled) setConnectInstance(instance);
      } catch (err) {
        if (!cancelled) {
          setFailed(true);
          onError?.(err);
        }
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (failed) return null;
  if (!connectInstance) {
    return (
      <div className="text-center py-4">
        <div className="spinner-border text-success spinner-border-sm me-2"></div>
        <span className="text-muted">Loading payout setup…</span>
      </div>
    );
  }

  return (
    <ConnectComponentsProvider connectInstance={connectInstance}>
      <ConnectAccountOnboarding onExit={() => onComplete?.()} />
    </ConnectComponentsProvider>
  );
}
