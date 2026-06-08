"""Cloudinary object storage for user-uploaded images.

When ``CLOUDINARY_URL`` is set, image uploads go to Cloudinary (CDN-backed,
survives Render deploys/restarts) and we store the returned ``public_id`` in the
existing image columns. The ``/media/<ref>`` route serves local files in dev and
301-redirects to the Cloudinary CDN in production. When the env var is unset,
everything falls back to local disk under ``UPLOAD_FOLDER``.

The cloudinary SDK auto-parses ``os.environ['CLOUDINARY_URL']`` *at import time*
and raises on any malformation (leading whitespace, surrounding quotes, a
scheme typo, etc.). We instead parse the URL ourselves and configure the SDK
explicitly, importing it with the env var temporarily removed so that fragile
import-time validation can never take the whole integration down.

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


def is_working():
    """True if the SDK imports and a delivery URL can be built from the config
    (i.e. CLOUDINARY_URL is present and well-formed). Cheap, no network."""
    return bool(is_configured() and delivery_url('healthcheck/probe'))


def _import_cloudinary():
    """Import the SDK without its import-time CLOUDINARY_URL auto-validation.

    The cloudinary package reads os.environ['CLOUDINARY_URL'] when first
    imported and raises ValueError on any malformation. Since we parse the URL
    ourselves and configure manually, we drop the env var across the import so
    a stray space / quote / scheme typo in the raw value can't break the import.
    """
    saved = os.environ.pop('CLOUDINARY_URL', None)
    try:
        import cloudinary
        import cloudinary.utils   # noqa: F401
        import cloudinary.uploader  # noqa: F401
        return cloudinary
    finally:
        if saved is not None:
            os.environ['CLOUDINARY_URL'] = saved


def _configure():
    """Import + configure the SDK from our own parse of CLOUDINARY_URL.

    Returns the configured ``cloudinary`` module. Configuring explicitly with
    cloud_name/api_key/api_secret avoids both the import-time validation and the
    fact that config(cloudinary_url=...) does NOT populate those fields.
    """
    cl = _import_cloudinary()
    parsed = urlparse(_cloudinary_url())
    cl.config(
        cloud_name=parsed.hostname,
        api_key=parsed.username,
        api_secret=parsed.password,
        secure=True,
    )
    return cl


def upload_image(file_or_bytes, folder=UPLOAD_FOLDER_NAME):
    """Upload an image to Cloudinary. Returns the public_id, or None on failure.

    ``file_or_bytes`` may be a file path, file-like object, or raw bytes.
    """
    try:
        cl = _configure()
        result = cl.uploader.upload(
            file_or_bytes, folder=folder, resource_type='image')
        return result.get('public_id')
    except Exception:
        log.exception('Cloudinary upload failed')
        return None


def delivery_url(public_id):
    """Build the secure CDN delivery URL for a stored public_id."""
    try:
        cl = _configure()
        url, _opts = cl.utils.cloudinary_url(public_id, secure=True)
        return url
    except Exception:
        log.exception('Cloudinary URL build failed for %s', public_id)
        return None


def destroy_image(public_id):
    """Delete an asset from Cloudinary. Returns True on success."""
    try:
        cl = _configure()
        cl.uploader.destroy(public_id, resource_type='image')
        return True
    except Exception:
        log.exception('Cloudinary destroy failed for %s', public_id)
        return False
