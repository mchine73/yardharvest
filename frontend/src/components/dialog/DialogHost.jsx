import { useEffect, useRef, useState } from 'react';
import { subscribe, getState, dismissToast, resolveDialog } from './dialogService';
import './dialog.css';

const TOAST_ICON = {
  success: 'bi-check-circle-fill',
  error: 'bi-x-circle-fill',
  warning: 'bi-exclamation-triangle-fill',
  info: 'bi-info-circle-fill',
};

/**
 * Single host mounted at the app root. Subscribes to the dialog service and
 * renders animated toasts + a confirm/prompt modal. No props.
 */
export default function DialogHost() {
  const [, force] = useState(0);
  const stateRef = useRef(getState());

  useEffect(() => subscribe((s) => {
    stateRef.current = s;
    force((n) => n + 1);
  }), []);

  const { toasts, dialog } = stateRef.current;

  return (
    <>
      <ToastStack toasts={toasts} />
      {dialog && dialog.kind === 'lightbox' && <Lightbox dialog={dialog} />}
      {dialog && dialog.kind !== 'lightbox' && <Modal dialog={dialog} />}
    </>
  );
}

function Lightbox({ dialog }) {
  const [leaving, setLeaving] = useState(false);

  const close = () => {
    setLeaving(true);
    setTimeout(() => resolveDialog(null), 170);
  };

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') close(); };
    window.addEventListener('keydown', onKey, true);
    return () => window.removeEventListener('keydown', onKey, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div
      className={`yh-modal-backdrop yh-lightbox-backdrop ${leaving ? 'leaving' : ''}`}
      onMouseDown={(e) => { if (e.target === e.currentTarget) close(); }}
      role="dialog"
      aria-modal="true"
      aria-label={dialog.alt || 'Photo'}
    >
      <div className="yh-lightbox">
        <button className="yh-lightbox-close" aria-label="Close" onClick={close}>
          <i className="bi bi-x-lg"></i>
        </button>
        <img className="yh-lightbox-img" src={dialog.src} alt={dialog.alt} />
        {dialog.caption && <div className="yh-lightbox-caption">{dialog.caption}</div>}
      </div>
    </div>
  );
}

function ToastStack({ toasts }) {
  if (!toasts.length) return null;
  return (
    <div className="yh-toast-stack" role="region" aria-label="Notifications">
      {toasts.map((t) => (
        <div key={t.id} className={`yh-toast ${t.type}`} role="alert">
          <i className={`bi ${TOAST_ICON[t.type] || TOAST_ICON.info} yh-toast-icon`}></i>
          <span className="yh-toast-msg">{t.message}</span>
          <button
            className="yh-toast-close"
            aria-label="Dismiss"
            onClick={() => dismissToast(t.id)}
          >
            <i className="bi bi-x-lg"></i>
          </button>
        </div>
      ))}
    </div>
  );
}

function Modal({ dialog }) {
  const isPrompt = dialog.kind === 'prompt';
  const [value, setValue] = useState(dialog.defaultValue || '');
  const [leaving, setLeaving] = useState(false);
  const inputRef = useRef(null);

  useEffect(() => {
    if (isPrompt && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isPrompt]);

  // Close with an exit animation, then resolve the promise.
  const close = (result) => {
    setLeaving(true);
    setTimeout(() => resolveDialog(result), 170);
  };

  const onConfirm = () => close(isPrompt ? value : true);
  const onCancel = () => close(isPrompt ? null : false);

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') onCancel();
      else if (e.key === 'Enter' && (isPrompt || dialog.kind === 'confirm')) {
        if (!(isPrompt && e.target.tagName === 'TEXTAREA')) onConfirm();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, leaving]);

  return (
    <div
      className={`yh-modal-backdrop ${leaving ? 'leaving' : ''}`}
      onMouseDown={(e) => { if (e.target === e.currentTarget) onCancel(); }}
    >
      <div
        className={`yh-modal ${dialog.danger ? 'danger' : ''}`}
        role="dialog"
        aria-modal="true"
        aria-label={dialog.title}
      >
        <div className="yh-modal-body">
          <div className="yh-modal-icon">
            <i className={`bi ${dialog.icon}`}></i>
          </div>
          <div className="yh-modal-title">{dialog.title}</div>
          {dialog.message && <div className="yh-modal-message">{dialog.message}</div>}
          {isPrompt && (
            <input
              ref={inputRef}
              type={dialog.inputType}
              className="yh-modal-input"
              value={value}
              placeholder={dialog.placeholder}
              onChange={(e) => setValue(e.target.value)}
            />
          )}
        </div>
        <div className="yh-modal-actions">
          <button className="yh-btn yh-btn-cancel" onClick={onCancel}>
            {dialog.cancelText}
          </button>
          <button className="yh-btn yh-btn-confirm" onClick={onConfirm}>
            {dialog.confirmText}
          </button>
        </div>
      </div>
    </div>
  );
}
