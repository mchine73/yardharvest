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
from urllib.parse import urlparse

from flask import current_app

log = logging.getLogger(__name__)

UPLOAD_FOLDER_NAME = 'yardharvest'  # Cloudinary asset folder


def _cloudinary_url():
    raw = os.environ.get('CLOUDINARY_URL') or current_app.config.get('CLOUDINARY_URL', '') or ''
    # Defensive sanitize: dashboard pastes often carry leading/trailing
    # whitespace or newlines, surrounding quotes, or an accidental
    # "CLOUDINARY_URL=" prefix (from copying the whole assignment line).
    raw = raw.strip().strip('"').strip("'").strip()
    if raw.upper().startswith('CLOUDINARY_URL='):
        raw = raw.split('=', 1)[1].strip().strip('"').strip("'").strip()
    return raw


def is_configured():
    return bool(_cloudinary_url())


def cloud_name():
    """Parsed cloud name (public, non-secret) — None if the URL is malformed."""
    return urlparse(_cloudinary_url()).hostname


def _configure():
    import cloudinary
    # Parse cloudinary://<api_key>:<api_secret>@<cloud_name> explicitly. Passing
    # cloudinary_url= to config() does NOT populate cloud_name/api_key/api_secret
    # (it just stores a stray attribute), which makes uploads + URL building fail.
    parsed = urlparse(_cloudinary_url())
    cloudinary.config(
        cloud_name=parsed.hostname,
        api_key=parsed.username,
        api_secret=parsed.password,
        secure=True,
    )


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
