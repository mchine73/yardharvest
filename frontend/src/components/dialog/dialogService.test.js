import { describe, it, expect, beforeEach } from 'vitest';
import {
  getState, toast, dismissToast, confirmDialog, promptDialog,
  lightbox, resolveDialog,
} from './dialogService';

// Reset the singleton store between tests.
beforeEach(() => {
  getState().toasts.length = 0;
  resolveDialog(undefined);
});

describe('toasts', () => {
  it('adds a toast and dismisses it by id', () => {
    const id = toast('Saved!', { type: 'success', duration: 0 });
    expect(getState().toasts.some((t) => t.id === id && t.message === 'Saved!')).toBe(true);
    dismissToast(id);
    expect(getState().toasts.some((t) => t.id === id)).toBe(false);
  });

  it('ignores empty messages', () => {
    expect(toast('')).toBeNull();
    expect(toast(null)).toBeNull();
  });
});

describe('confirm/prompt dialogs', () => {
  it('confirmDialog resolves true when confirmed', async () => {
    const p = confirmDialog('Delete this?', { title: 'Delete' });
    expect(getState().dialog.kind).toBe('confirm');
    resolveDialog(true);
    await expect(p).resolves.toBe(true);
    expect(getState().dialog).toBeNull();
  });

  it('promptDialog resolves with the entered value', async () => {
    const p = promptDialog('Name:', { defaultValue: 'x' });
    expect(getState().dialog.kind).toBe('prompt');
    resolveDialog('Sunrise Garden');
    await expect(p).resolves.toBe('Sunrise Garden');
  });
});

describe('lightbox', () => {
  it('opens a lightbox dialog with the given src', () => {
    lightbox('/media/photo.jpg', { caption: 'Tomatoes' });
    expect(getState().dialog.kind).toBe('lightbox');
    expect(getState().dialog.src).toBe('/media/photo.jpg');
    expect(getState().dialog.caption).toBe('Tomatoes');
  });

  it('REGRESSION: closing a lightbox does not throw (it has no resolve fn)', () => {
    lightbox('/media/photo.jpg');
    // The bug: resolveDialog unconditionally called dialog.resolve(), but a
    // lightbox is fire-and-forget and carries no resolve callback.
    expect(() => resolveDialog(null)).not.toThrow();
    expect(getState().dialog).toBeNull();
  });

  it('ignores a falsy src', () => {
    resolveDialog(undefined); // clear
    lightbox('');
    expect(getState().dialog).toBeNull();
  });
});
