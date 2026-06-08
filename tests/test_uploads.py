"""Regression tests for photo upload storage.

The bug: save_photo() wrote to <repo>/static/uploads while Flask serves
/static/uploads from app/static/uploads (UPLOAD_FOLDER) — so garden/general
photos 404'd and thumbnails broke. These tests pin that uploads land in the
served directory, and that the photos API serves them at /static/uploads/.
"""
import io
import os

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
