import { describe, it, expect } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import DialogHost from './DialogHost';
import { lightbox, confirmDialog, resolveDialog, getState } from './dialogService';

describe('DialogHost', () => {
  it('renders an opened lightbox and closes via the X without crashing', async () => {
    const user = userEvent.setup();
    render(<DialogHost />);

    lightbox('/media/photo.jpg', { alt: 'A photo', caption: 'Tomatoes' });

    // Image + close button appear
    const img = await screen.findByRole('img', { name: 'A photo' });
    expect(img).toHaveAttribute('src', '/media/photo.jpg');
    const close = screen.getByRole('button', { name: /close/i });

    // REGRESSION: clicking close used to throw (lightbox has no resolve fn),
    // tripping the error boundary. It must close cleanly instead.
    await user.click(close);
    await waitFor(() => expect(getState().dialog).toBeNull());
    expect(screen.queryByRole('img', { name: 'A photo' })).not.toBeInTheDocument();
  });

  it('renders a confirm dialog and resolves on confirm', async () => {
    const user = userEvent.setup();
    render(<DialogHost />);

    const p = confirmDialog('Delete this?', { title: 'Delete', confirmText: 'Delete' });
    expect(await screen.findByText('Delete this?')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Delete' }));
    await expect(p).resolves.toBe(true);
  });

  // Keep the store clean for other test files sharing the singleton.
  it('cleanup', () => { resolveDialog(undefined); expect(true).toBe(true); });
});
