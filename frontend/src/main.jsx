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
  showFatalBootError(IS_PROD
    ? 'An unexpected error occurred. Please refresh the page.'
    : String(e.reason));
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
  }
  render() {
    if (this.state.hasError) {
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

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>
);
