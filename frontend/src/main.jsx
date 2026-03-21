import React from 'react';
import ReactDOM from 'react-dom/client';

const IS_PROD = import.meta.env.PROD;

// Global error handler — show generic message in production, details in dev
window.addEventListener('error', (e) => {
  const root = document.getElementById('root');
  if (root) {
    const detail = IS_PROD
      ? 'An unexpected error occurred. Please refresh the page.'
      : `${e.message}\n\n${e.filename}:${e.lineno}:${e.colno}`;
    root.innerHTML = `<div style="padding:2rem;font-family:monospace;background:#fee;color:#c00;border:2px solid #c00;margin:1rem;border-radius:8px">
      <h2>Something went wrong</h2>
      <pre style="white-space:pre-wrap">${detail}</pre>
    </div>`;
  }
});

window.addEventListener('unhandledrejection', (e) => {
  const root = document.getElementById('root');
  if (root && !root.innerHTML.includes('went wrong')) {
    const detail = IS_PROD
      ? 'An unexpected error occurred. Please refresh the page.'
      : String(e.reason);
    root.innerHTML = `<div style="padding:2rem;font-family:monospace;background:#fee;color:#c00;border:2px solid #c00;margin:1rem;border-radius:8px">
      <h2>Something went wrong</h2>
      <pre style="white-space:pre-wrap">${detail}</pre>
    </div>`;
  }
});

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '2rem', fontFamily: 'monospace', background: '#fee', color: '#c00', border: '2px solid #c00', margin: '1rem', borderRadius: '8px' }}>
          <h2>Something went wrong</h2>
          {IS_PROD ? (
            <p>An unexpected error occurred. Please refresh the page.</p>
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
