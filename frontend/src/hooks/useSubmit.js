import { useState, useCallback, useRef } from 'react';
import { toast } from '../components/dialog/dialogService';

/**
 * Minimal submit primitive for mutations.
 *
 * Scope is deliberately small (the codebase favors explicit inline handlers):
 * it owns exactly three things — a `pending` flag, a double-submit guard, and
 * success/error toasts. The caller keeps its own side-effects (refetch, close
 * modal, reset form) so this never becomes a leaky god-hook.
 *
 *   const { pending, run } = useSubmit();
 *   const onClick = () => run(() => api.doThing(), {
 *     success: 'Saved',
 *     error: 'Could not save — please try again.',
 *   }).then(({ ok }) => { if (ok) refetch(); });
 *
 * `run` never throws: it resolves to { ok: true, data } on success or
 * { ok: false, error } after showing the error toast.
 */
export function useSubmit() {
  const [pending, setPending] = useState(false);
  const inFlight = useRef(false);

  const run = useCallback(async (fn, { success, error } = {}) => {
    if (inFlight.current) return { ok: false, error: null }; // guard double-submit
    inFlight.current = true;
    setPending(true);
    try {
      const data = await fn();
      if (success) toast(success, { type: 'success' });
      return { ok: true, data };
    } catch (err) {
      const msg = error || err?.response?.data?.error ||
        'Something went wrong. Please check your connection and try again.';
      toast(msg, { type: 'error' });
      return { ok: false, error: err };
    } finally {
      inFlight.current = false;
      setPending(false);
    }
  }, []);

  return { pending, run };
}
