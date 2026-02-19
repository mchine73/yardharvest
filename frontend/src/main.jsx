import React from 'react';
import ReactDOM from 'react-dom/client';

// Global error handler to show crashes visually
window.addEventListener('error', (e) => {
  const root = document.getElementById('root');
  if (root) {
    root.innerHTML = `<div style="padding:2rem;font-family:monospace;background:#fee;color:#c00;border:2px solid #c00;margin:1rem;border-radius:8px">
      <h2>⚠️ JavaScript Error</h2>
      <pre style="white-space:pre-wrap">${e.message}\n\n${e.filename}:${e.lineno}:${e.colno}</pre>
    </div>`;
  }
});

window.addEventListener('unhandledrejection', (e) => {
  const root = document.getElementById('root');
  if (root && !root.innerHTML.includes('JavaScript Error')) {
    root.innerHTML = `<div style="padding:2rem;font-family:monospace;background:#fee;color:#c00;border:2px solid #c00;margin:1rem;border-radius:8px">
      <h2>⚠️ Unhandled Promise Rejection</h2>
      <pre style="white-space:pre-wrap">${e.reason}</pre>
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
          <h2>⚠️ React Rendering Error</h2>
          <pre style={{ whiteSpace: 'pre-wrap' }}>{this.state.error?.message}</pre>
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: '0.8rem', color: '#666' }}>{this.state.error?.stack}</pre>
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
