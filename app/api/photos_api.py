from flask import Blueprint, request, jsonify
from app import db
from app.models import Photo
from app.helpers import save_photo
from app.api.token_auth import token_or_session, get_current_user

photos_api = Blueprint('photos_api', __name__, url_prefix='/api/photos')


@photos_api.route('/upload', methods=['POST'])
@token_or_session
def upload_photo():
    """Upload a photo with auto-downscaling."""
    user = get_current_user()

    if 'photo' not in request.files:
        return jsonify({'error': 'No photo file provided'}), 400

    file = request.files['photo']
    if not file.filename:
        return jsonify({'error': 'No file selected'}), 400

    # Validate file type
    allowed = {'jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp'}
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in allowed:
        return jsonify({'error': f'Invalid file type. Allowed: {", ".join(allowed)}'}), 400

    try:
        filename, file_size, width, height = save_photo(file)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'Failed to process image'}), 500

    photo = Photo(
        user_id=user.id,
        garden_id=request.form.get('garden_id', type=int),
        filename=filename,
        original_filename=file.filename,
        file_size=file_size,
        width=width,
        height=height,
        category=request.form.get('category', 'general'),
        caption=request.form.get('caption', ''),
    )
    db.session.add(photo)
    db.session.commit()

    return jsonify({
        'id': photo.id,
        'filename': photo.filename,
        'url': f'/static/uploads/{photo.filename}',
        'file_size': photo.file_size,
        'width': photo.width,
        'height': photo.height,
        'category': photo.category,
        'caption': photo.caption,
        'uploaded_at': photo.uploaded_at.isoformat() if photo.uploaded_at else None,
    }), 201


@photos_api.route('', methods=['GET'])
@token_or_session
def list_photos():
    """List photos with optional filtering."""
    user = get_current_user()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    category = request.args.get('category')
    garden_id = request.args.get('garden_id', type=int)

    query = Photo.query.filter_by(user_id=user.id)
    if category:
        query = query.filter_by(category=category)
    if garden_id:
        query = query.filter_by(garden_id=garden_id)

    query = query.order_by(Photo.uploaded_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'photos': [{
            'id': p.id,
            'filename': p.filename,
            'url': f'/static/uploads/{p.filename}',
            'original_filename': p.original_filename,
            'file_size': p.file_size,
            'width': p.width,
            'height': p.height,
            'category': p.category,
            'caption': p.caption,
            'uploaded_at': p.uploaded_at.isoformat() if p.uploaded_at else None,
        } for p in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'page': page,
    })


@photos_api.route('/<int:photo_id>', methods=['DELETE'])
@token_or_session
def delete_photo(photo_id):
    """Delete a photo."""
    user = get_current_user()
    photo = Photo.query.get_or_404(photo_id)

    if photo.user_id != user.id and not user.is_admin:
        return jsonify({'error': 'Not authorized'}), 403

    # Delete file from disk
    import os
    filepath = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'static', 'uploads', photo.filename)
    if os.path.exists(filepath):
        os.remove(filepath)

    db.session.delete(photo)
    db.session.commit()

    return jsonify({'success': True})


@photos_api.route('/garden/<int:garden_id>', methods=['GET'])
def garden_photos(garden_id):
    """List photos for a specific garden (public)."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    query = Photo.query.filter_by(garden_id=garden_id).order_by(Photo.uploaded_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'photos': [{
            'id': p.id,
            'filename': p.filename,
            'url': f'/static/uploads/{p.filename}',
            'caption': p.caption,
            'category': p.category,
            'width': p.width,
            'height': p.height,
            'uploaded_at': p.uploaded_at.isoformat() if p.uploaded_at else None,
        } for p in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'page': page,
    })
