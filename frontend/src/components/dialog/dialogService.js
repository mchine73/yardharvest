/**
 * Bespoke in-app dialog service — replaces the native window.alert/confirm/
 * prompt (which render ugly, unstyled, blocking browser chrome) with animated
 * toasts and modals rendered inside the React tree.
 *
 * Imperative API so it can be called from anywhere (event handlers, .catch()
 * chains, plain functions) without threading a hook through every component:
 *
 *   import { toast, confirmDialog, promptDialog } from '.../dialogService';
 *
 *   toast('Saved!', { type: 'success' });            // fire-and-forget
 *   if (!(await confirmDialog('Delete this?'))) return;
 *   const name = await promptDialog('New name:', { defaultValue: 'x' });
 *
 * A single <DialogHost /> mounted at the app root subscribes to this store and
 * renders the UI.
 */

let listeners = [];
let state = { toasts: [], dialog: null };

function emit() {
  state = { toasts: state.toasts, dialog: state.dialog };
  listeners.forEach((l) => l(state));
}

export function subscribe(fn) {
  listeners.push(fn);
  return () => {
    listeners = listeners.filter((l) => l !== fn);
  };
}

export function getState() {
  return state;
}

// ---- Toasts (replaces alert) ----------------------------------------------
let toastId = 0;

export function toast(message, { type = 'info', duration = 4500 } = {}) {
  if (message == null || message === '') return null;
  const id = ++toastId;
  state.toasts = [...state.toasts, { id, message: String(message), type }];
  emit();
  if (duration) setTimeout(() => dismissToast(id), duration);
  return id;
}

export function dismissToast(id) {
  state.toasts = state.toasts.filter((t) => t.id !== id);
  emit();
}

// ---- Confirm / Prompt modal (replaces confirm/prompt) ---------------------
export function confirmDialog(message, opts = {}) {
  return new Promise((resolve) => {
    state.dialog = {
      kind: 'confirm',
      message: String(message),
      title: opts.title || 'Please confirm',
      confirmText: opts.confirmText || 'Confirm',
      cancelText: opts.cancelText || 'Cancel',
      danger: !!opts.danger,
      icon: opts.icon || (opts.danger ? 'bi-exclamation-triangle' : 'bi-question-circle'),
      resolve,
    };
    emit();
  });
}

export function promptDialog(message, opts = {}) {
  return new Promise((resolve) => {
    state.dialog = {
      kind: 'prompt',
      message: String(message),
      title: opts.title || 'Enter a value',
      defaultValue: opts.defaultValue != null ? String(opts.defaultValue) : '',
      placeholder: opts.placeholder || '',
      inputType: opts.inputType || 'text',
      confirmText: opts.confirmText || 'OK',
      cancelText: opts.cancelText || 'Cancel',
      icon: opts.icon || 'bi-pencil-square',
      resolve,
    };
    emit();
  });
}

/** Zoom an image into the animated modal (same backdrop/scale-in as dialogs). */
export function lightbox(src, opts = {}) {
  if (!src) return;
  state.dialog = {
    kind: 'lightbox',
    src,
    alt: opts.alt || '',
    caption: opts.caption || '',
  };
  emit();
}

/** Close the active modal, resolving its promise with `result`.
 * Lightboxes have no awaiting promise, so `resolve` is optional. */
export function resolveDialog(result) {
  const d = state.dialog;
  state.dialog = null;
  emit();
  if (d && typeof d.resolve === 'function') d.resolve(result);
}
