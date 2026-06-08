"""Regression tests for photo upload storage.

The bug: save_photo() wrote to <repo>/static/uploads while Flask serves
/static/uploads from app/static/uploads (UPLOAD_FOLDER) — so garden/general
photos 404'd and thumbnails broke. These tests pin that uploads land in the
served directory, and that the photos API serves them at /static/uploads/.
"""
import io
import os
from unittest.mock import patch

from PIL import Image
from werkzeug.datastructures import FileStorage


def _png_filestorage(name='test.png', color='red', size=(12, 12)):
    buf = io.BytesIO()
    Image.new('RGB', size, color).save(buf, 'PNG')
    buf.seek(0)
    return FileStorage(stream=buf, filename=name, content_type='image/png')


def test_save_photo_writes_to_served_upload_folder(app):
    """save_photo() must write into UPLOAD_FOLDER (the dir Flask serves at
    /static/uploads), not a hand-built <repo>/static/uploads path."""
    from app.helpers import save_photo
    with app.app_context():
        filename, file_size, w, h = save_photo(_png_filestorage())
        served_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        try:
            assert os.path.isfile(served_path), (
                f'{filename} not found in served UPLOAD_FOLDER '
                f'{app.config["UPLOAD_FOLDER"]}')
            assert file_size > 0 and w > 0 and h > 0
        finally:
            if os.path.exists(served_path):
                os.remove(served_path)


def test_save_listing_image_writes_to_served_upload_folder(app):
    """Marketplace listing images use the same served folder."""
    from app.helpers import save_listing_image
    with app.app_context():
        filename = save_listing_image(_png_filestorage('listing.png', 'green'))
        assert filename, 'save_listing_image returned no filename'
        served_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        try:
            assert os.path.isfile(served_path)
        finally:
            if os.path.exists(served_path):
                os.remove(served_path)


# ---------------------------------------------------------------------------
# Cloudinary object storage (mocked) + /media resolution route
# ---------------------------------------------------------------------------
def test_store_image_uses_cloudinary_when_configured(app):
    """When Cloudinary is configured, save_photo stores the public_id and does
    NOT write a local file."""
    from app.helpers import save_photo
    with app.app_context():
        with patch('app.cloudinary_service.is_configured', return_value=True), \
                patch('app.cloudinary_service.upload_image',
                      return_value='yardharvest/abc123') as up:
            ref, size, w, h = save_photo(_png_filestorage())
        assert ref == 'yardharvest/abc123'  # public_id, not a local filename
        up.assert_called_once()
        assert not os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], ref))


def test_media_route_serves_local_file(app, client):
    updir = app.config['UPLOAD_FOLDER']
    os.makedirs(updir, exist_ok=True)
    name = 'media_local_test.bin'
    path = os.path.join(updir, name)
    with open(path, 'wb') as f:
        f.write(b'hello-bytes')
    try:
        r = client.get(f'/media/{name}')
        assert r.status_code == 200
        assert r.data == b'hello-bytes'
        r.close()  # release the file handle (Windows can't delete an open file)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def test_media_route_redirects_to_cloudinary_when_missing(app, client):
    with patch('app.cloudinary_service.is_configured', return_value=True), \
            patch('app.cloudinary_service.delivery_url',
                  return_value='https://res.cloudinary.com/x/image/upload/yardharvest/abc'):
        r = client.get('/media/yardharvest/abc', follow_redirects=False)
    assert r.status_code == 301
    assert r.headers['Location'] == 'https://res.cloudinary.com/x/image/upload/yardharvest/abc'


def test_media_route_404_when_missing_and_no_cloudinary(app, client):
    with patch('app.cloudinary_service.is_configured', return_value=False):
        r = client.get('/media/definitely-not-here.jpg')
    assert r.status_code == 404


def test_cloudinary_delivery_url_builds_real_cdn_url(app, monkeypatch):
    """Exercise the REAL _configure() + delivery_url() (no mocks) — guards the
    bug where config(cloudinary_url=...) failed to set cloud_name, so URL
    building (and uploads) silently failed."""
    monkeypatch.setenv('CLOUDINARY_URL', 'cloudinary://key123:secret456@democloud')
    from app import cloudinary_service
    with app.app_context():
        assert cloudinary_service.is_configured() is True
        url = cloudinary_service.delivery_url('yardharvest/abc')
        assert url, 'delivery_url returned None — Cloudinary config is broken'
        assert 'res.cloudinary.com/democloud' in url
        assert 'yardharvest/abc' in url


def test_cloudinary_url_sanitized(app, monkeypatch):
    """Tolerate whitespace / quotes / a stray CLOUDINARY_URL= prefix in the env
    value (common dashboard paste errors) — all must still parse the cloud."""
    from app import cloudinary_service
    for raw in [
        '  cloudinary://k:s@mycloud  ',
        '"cloudinary://k:s@mycloud"',
        'CLOUDINARY_URL=cloudinary://k:s@mycloud',
        'cloudinary://k:s@mycloud\n',
    ]:
        monkeypatch.setenv('CLOUDINARY_URL', raw)
        with app.app_context():
            assert cloudinary_service.cloud_name() == 'mycloud', f'failed for {raw!r}'
            assert cloudinary_service.delivery_url('a/b')


def test_media_route_redirects_using_real_cloudinary_config(app, client, monkeypatch):
    """End-to-end: with a real CLOUDINARY_URL, an unknown /media ref 301s to the
    Cloudinary CDN (this is exactly the live production behavior we probe)."""
    monkeypatch.setenv('CLOUDINARY_URL', 'cloudinary://key123:secret456@democloud')
    r = client.get('/media/yardharvest/abc', follow_redirects=False)
    assert r.status_code == 301
    assert 'res.cloudinary.com/democloud' in r.headers['Location']
