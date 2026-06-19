import React from 'react';
import ReactDOM from 'react-dom/client';

const IS_PROD = import.meta.env.PROD;

// Last-resort handler for global errors / promise rejections. IMPORTANT: only
// take over the page when the app never mounted (empty #root) — e.g. a boot
// failure or a chunk that failed to load. Once React is running, a stray async
// error (commonly from third-party SDKs like the Stripe embedded Connect
// iframe) must NOT blank the whole app; just log it and let React's
// ErrorBoundary handle anything that's actually a render error.
function showFatalBootError(detail) {
  const root = document.getElementById('root');
  if (!root || root.childElementCount > 0) return; // app mounted → don't clobber
  root.innerHTML = `<div style="padding:2rem;font-family:monospace;background:#fee;color:#c00;border:2px solid #c00;margin:1rem;border-radius:8px">
    <h2>Something went wrong</h2>
    <pre style="white-space:pre-wrap">${detail}</pre>
  </div>`;
}

window.addEventListener('error', (e) => {
  console.error('Global error:', e.error || e.message, e.filename, e.lineno);
  showFatalBootError(IS_PROD
    ? 'An unexpected error occurred. Please refresh the page.'
    : `${e.message}\n\n${e.filename}:${e.lineno}:${e.colno}`);
});

window.addEventListener('unhandledrejection', (e) => {
  console.error('Unhandled promise rejection:', e.reason);
  // A failed lazy import that escaped the ErrorBoundary — recover via reload.
  if (isChunkLoadError(e.reason) && reloadForStaleChunk()) return;
  showFatalBootError(IS_PROD
    ? 'An unexpected error occurred. Please refresh the page.'
    : String(e.reason));
});

// --- Stale-chunk recovery after a deploy ---------------------------------
// Each deploy gives lazy-loaded route chunks new hashed filenames. A tab still
// running the previous build will 404 when it imports a route ("Failed to fetch
// dynamically imported module"). Reload once to pull the fresh index.html +
// chunk names. Loop-guarded (10s) so a genuinely-missing chunk surfaces in the
// ErrorBoundary instead of reloading forever.
function isChunkLoadError(error) {
  const msg = (error && (error.message || String(error))) || '';
  return /dynamically imported module|Importing a module script failed|'?ChunkLoadError'?|Loading chunk \d|Failed to fetch dynamically/i
    .test(msg);
}

function reloadForStaleChunk() {
  const KEY = 'vh:chunkReloadAt';
  const last = Number(sessionStorage.getItem(KEY) || 0);
  if (Date.now() - last > 10000) {
    sessionStorage.setItem(KEY, String(Date.now()));
    window.location.reload();
    return true;
  }
  return false;  // already tried recently — let the error surface
}

// Vite's official hook for a failed dynamic import (fires before the throw).
window.addEventListener('vite:preloadError', (e) => {
  e.preventDefault();
  reloadForStaleChunk();
});

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  componentDidCatch(error, info) {
    console.error('React ErrorBoundary caught:', error, info?.componentStack);
    // A lazy route failed to load — almost always a deploy rotated the chunk
    // hashes. Reload once to fetch the current build (loop-guarded).
    if (isChunkLoadError(error)) reloadForStaleChunk();
  }
  render() {
    if (this.state.hasError) {
      // While the stale-chunk reload kicks in, show a calm "updating" note
      // rather than the red error panel.
      if (isChunkLoadError(this.state.error)) {
        return (
          <div style={{ padding: '2rem', fontFamily: 'monospace', color: '#555', margin: '1rem' }}>
            <h2>Updating to the latest version…</h2>
            <p>One moment — reloading. If this doesn’t clear, refresh the page.</p>
          </div>
        );
      }
      return (
        <div style={{ padding: '2rem', fontFamily: 'monospace', background: '#fee', color: '#c00', border: '2px solid #c00', margin: '1rem', borderRadius: '8px' }}>
          <h2>Something went wrong</h2>
          {IS_PROD ? (
            <>
              <p>An unexpected error occurred. Please refresh the page.</p>
              {this.state.error?.message && (
                <pre style={{ whiteSpace: 'pre-wrap', fontSize: '0.8rem', color: '#900' }}>{this.state.error.message}</pre>
              )}
            </>
          ) : (
            <>
              <pre style={{ whiteSpace: 'pre-wrap' }}>{this.state.error?.message}</pre>
              <pre style={{ whiteSpace: 'pre-wrap', fontSize: '0.8rem', color: '#666' }}>{this.state.error?.stack}</pre>
            </>
          )}
        </div>
      );
    }
    return this.props.children;
  }
}

import App from './App';
import { HelmetProvider } from 'react-helmet-async';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary>
      <HelmetProvider>
        <App />
      </HelmetProvider>
    </ErrorBoundary>
  </React.StrictMode>
);
