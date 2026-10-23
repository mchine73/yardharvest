import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import i18n from '../../i18n';
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

// The dialog's BUTTONS are as much a part of the page as its message. The
// admin portal shipped 21 confirms whose question was Spanish and whose
// Cancel button was English, because the messages were translated at the call
// sites and the defaults live in this module. Dialogs also mount in a portal
// outside <main>, so a check scoped to the page body never saw them.
describe('dialog chrome follows the language', () => {
  afterEach(async () => {
    resolveDialog(undefined);
    await i18n.changeLanguage('en');
  });

  it('uses English defaults in English', () => {
    confirmDialog('Delete this?');
    const dlg = getState().dialog;
    expect([dlg.confirmText, dlg.cancelText]).toEqual(['Confirm', 'Cancel']);
    expect(dlg.title).toBe('Please confirm');
  });

  it('uses Spanish defaults in Spanish', async () => {
    await i18n.changeLanguage('es');
    confirmDialog('¿Eliminar esto?');
    const dlg = getState().dialog;
    expect(dlg.cancelText).toBe('Cancelar');
    expect(dlg.confirmText).toBe('Confirmar');
    expect(dlg.title).toBe('Confirma, por favor');
  });

  it('translates the prompt defaults too', async () => {
    await i18n.changeLanguage('es');
    promptDialog('¿Cuántos días?');
    const dlg = getState().dialog;
    expect(dlg.confirmText).toBe('Aceptar');
    expect(dlg.cancelText).toBe('Cancelar');
    expect(dlg.title).toBe('Escribe un valor');
  });

  it('still honours an explicit override', async () => {
    await i18n.changeLanguage('es');
    confirmDialog('x', { confirmText: 'Liberar', cancelText: 'No' });
    expect(getState().dialog.confirmText).toBe('Liberar');
    expect(getState().dialog.cancelText).toBe('No');
  });
});
