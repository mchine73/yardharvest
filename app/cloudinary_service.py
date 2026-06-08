"""Cloudinary object storage for user-uploaded images.

When ``CLOUDINARY_URL`` is set, image uploads go to Cloudinary (CDN-backed,
survives Render deploys/restarts) and we store the returned ``public_id`` in the
existing image columns. The ``/media/<ref>`` route serves local files in dev and
301-redirects to the Cloudinary CDN in production. When the env var is unset,
everything falls back to local disk under ``UPLOAD_FOLDER``.

All functions degrade gracefully (return None / False, log) so an upload never
crashes the calling endpoint.
"""
import logging
import os

from flask import current_app

log = logging.getLogger(__name__)

UPLOAD_FOLDER_NAME = 'yardharvest'  # Cloudinary asset folder


def _cloudinary_url():
    return os.environ.get('CLOUDINARY_URL') or current_app.config.get('CLOUDINARY_URL', '')


def is_configured():
    return bool(_cloudinary_url())


def _configure():
    import cloudinary
    cloudinary.config(cloudinary_url=_cloudinary_url(), secure=True)


def upload_image(file_or_bytes, folder=UPLOAD_FOLDER_NAME):
    """Upload an image to Cloudinary. Returns the public_id, or None on failure.

    ``file_or_bytes`` may be a file path, file-like object, or raw bytes.
    """
    try:
        _configure()
        import cloudinary.uploader
        result = cloudinary.uploader.upload(
            file_or_bytes, folder=folder, resource_type='image')
        return result.get('public_id')
    except Exception:
        log.exception('Cloudinary upload failed')
        return None


def delivery_url(public_id):
    """Build the secure CDN delivery URL for a stored public_id."""
    try:
        _configure()
        import cloudinary.utils
        url, _opts = cloudinary.utils.cloudinary_url(public_id, secure=True)
        return url
    except Exception:
        log.exception('Cloudinary URL build failed for %s', public_id)
        return None


def destroy_image(public_id):
    """Delete an asset from Cloudinary. Returns True on success."""
    try:
        _configure()
        import cloudinary.uploader
        cloudinary.uploader.destroy(public_id, resource_type='image')
        return True
    except Exception:
        log.exception('Cloudinary destroy failed for %s', public_id)
        return False
