from flask import Blueprint, request, jsonify
from sqlalchemy import func
from app import db
from app.models import Photo, PhotoLike, PhotoComment
from app.helpers import save_photo
from app.api.token_auth import token_or_session, get_current_user

photos_api = Blueprint('photos_api', __name__, url_prefix='/api/photos')


def _comment_counts(photo_ids):
    """Return {photo_id: comment_count} for a page of photos in one query."""
    if not photo_ids:
        return {}
    rows = (db.session.query(PhotoComment.photo_id, func.count(PhotoComment.id))
            .filter(PhotoComment.photo_id.in_(photo_ids))
            .group_by(PhotoComment.photo_id).all())
    return {pid: cnt for pid, cnt in rows}


def _liked_photo_ids(user, photo_ids):
    """Return the subset of photo_ids the user has already upvoted."""
    if not user or not getattr(user, 'is_authenticated', False) or not photo_ids:
        return set()
    rows = (db.session.query(PhotoLike.photo_id)
            .filter(PhotoLike.user_id == user.id,
                    PhotoLike.photo_id.in_(photo_ids)).all())
    return {pid for (pid,) in rows}


def _garden_organizer_id(garden_id):
    if not garden_id:
        return None
    from app.models import CommunityGarden
    return (db.session.query(CommunityGarden.organizer_id)
            .filter_by(id=garden_id).scalar())


def _is_garden_admin(user, garden_id):
    """True if the user is the garden's organizer or a site admin — the same
    notion of "admin" used by the comment wall and the admin portal."""
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if user.is_admin:
        return True
    return _garden_organizer_id(garden_id) == user.id


def _garden_is_pro(garden_id):
    """True if the garden has a trialing/active Garden Pro subscription. The
    photo gallery is a Pro feature, so garden-scoped photo actions require it."""
    if not garden_id:
        return True  # personal (non-garden) photos aren't gated
    from app.models import CommunityGarden
    status = (db.session.query(CommunityGarden.subscription_status)
              .filter_by(id=garden_id).scalar())
    return status in ('trialing', 'active')


def _pro_required_response():
    return jsonify({
        'error': 'Garden Pro subscription required',
        'pro_required': True,
    }), 403


def _photo_comment_to_dict(c):
    return {
        'id': c.id,
        'photo_id': c.photo_id,
        'user_id': c.user_id,
        'user_name': (c.user.display_name or c.user.username) if c.user else 'Member',
        'content': c.content,
        'created_at': c.created_at.isoformat() if c.created_at else None,
    }


@photos_api.route('/upload', methods=['POST'])
@token_or_session
def upload_photo():
    """Upload a photo with auto-downscaling."""
    user = get_current_user()

    # Photo gallery is a Garden Pro feature — block uploads to non-Pro gardens.
    garden_id = request.form.get('garden_id', type=int)
    if garden_id and not _garden_is_pro(garden_id):
        return _pro_required_response()

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
        'url': f'/media/{photo.filename}',
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

    ids = [p.id for p in pagination.items]
    counts = _comment_counts(ids)
    liked = _liked_photo_ids(user, ids)

    return jsonify({
        'photos': [{
            'id': p.id,
            'filename': p.filename,
            'url': f'/media/{p.filename}',
            'original_filename': p.original_filename,
            'file_size': p.file_size,
            'width': p.width,
            'height': p.height,
            'category': p.category,
            'caption': p.caption,
            'user_id': p.user_id,
            'likes_count': p.likes_count or 0,
            'liked_by_me': p.id in liked,
            'comments_count': counts.get(p.id, 0),
            'can_delete': True,  # list_photos is always the caller's own photos
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
    photo = db.get_or_404(Photo, photo_id)

    # Only the original poster or a garden admin (organizer / site admin).
    if photo.user_id != user.id and not _is_garden_admin(user, photo.garden_id):
        return jsonify({'error': 'Not authorized'}), 403

    # Delete the asset: local file if present (dev), else the Cloudinary asset
    # (photo.filename is the public_id when stored on the CDN).
    import os
    from flask import current_app
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], photo.filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    else:
        from app import cloudinary_service
        if cloudinary_service.is_configured():
            cloudinary_service.destroy_image(photo.filename)

    # Remove upvotes + comments first (explicit; the relationship cascade also
    # covers this, but a bulk delete avoids loading every child row).
    PhotoLike.query.filter_by(photo_id=photo.id).delete(synchronize_session=False)
    PhotoComment.query.filter_by(photo_id=photo.id).delete(synchronize_session=False)
    db.session.delete(photo)
    db.session.commit()

    return jsonify({'success': True})


@photos_api.route('/garden/<garden_id>', methods=['GET'])
def garden_photos(garden_id):
    """List photos for a specific garden (public).

    Includes the poster's id so the frontend can show a delete control only to
    the poster or an admin (delete itself is re-checked server-side).
    """
    from sqlalchemy.orm import joinedload
    from app.helpers import resolve_garden_pk
    # photos_api has no garden-id url_value_preprocessor, so the ref arrives raw.
    # Public garden URLs carry the opaque grd_… public_id; resolve to the integer
    # PK or filter_by(garden_id=…) errors against the integer column in Postgres.
    garden_id = resolve_garden_pk(garden_id)

    # Photo gallery is a Garden Pro feature. Non-Pro gardens get an empty wall
    # plus a pro_required flag so the UI can show an upgrade prompt / hide it.
    if not _garden_is_pro(garden_id):
        return jsonify({'photos': [], 'total': 0, 'pages': 0, 'page': 1,
                        'pro_required': True})

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    category = (request.args.get('category') or '').strip()

    query = (Photo.query.filter_by(garden_id=garden_id)
             .options(joinedload(Photo.user)))
    if category and category != 'all':
        query = query.filter_by(category=category)
    query = query.order_by(Photo.uploaded_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    # Optional user context (works for both session + Bearer); anonymous viewers
    # simply get liked=False everywhere. Comment counts + my-likes resolved in
    # one grouped query each to avoid N+1 across the page.
    user = get_current_user()
    is_authed = getattr(user, 'is_authenticated', False)
    is_admin = is_authed and getattr(user, 'is_admin', False)
    # A photo is removable by three groups: its creator, the garden admin
    # (organizer), or a site admin.
    org_id = _garden_organizer_id(garden_id)
    is_garden_admin = is_authed and (is_admin or (org_id is not None and org_id == user.id))
    ids = [p.id for p in pagination.items]
    counts = _comment_counts(ids)
    liked = _liked_photo_ids(user, ids)

    return jsonify({
        'photos': [{
            'id': p.id,
            'filename': p.filename,
            'url': f'/media/{p.filename}',
            'caption': p.caption,
            'category': p.category,
            'width': p.width,
            'height': p.height,
            'user_id': p.user_id,
            'user_name': (p.user.display_name or p.user.username) if p.user else 'Member',
            'likes_count': p.likes_count or 0,
            'liked_by_me': p.id in liked,
            'comments_count': counts.get(p.id, 0),
            'can_delete': is_authed and (p.user_id == user.id or is_garden_admin),
            'uploaded_at': p.uploaded_at.isoformat() if p.uploaded_at else None,
        } for p in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'page': page,
    })


@photos_api.route('/<int:photo_id>/like', methods=['POST'])
@token_or_session
def toggle_photo_like(photo_id):
    """Toggle the current user's upvote on a photo."""
    user = get_current_user()
    photo = db.get_or_404(Photo, photo_id)
    if not _garden_is_pro(photo.garden_id):
        return _pro_required_response()

    existing = PhotoLike.query.filter_by(photo_id=photo_id, user_id=user.id).first()
    if existing:
        db.session.delete(existing)
        photo.likes_count = max(0, (photo.likes_count or 0) - 1)
        liked = False
    else:
        db.session.add(PhotoLike(photo_id=photo_id, user_id=user.id))
        photo.likes_count = (photo.likes_count or 0) + 1
        liked = True
    db.session.commit()

    return jsonify({'photo_id': photo_id, 'liked': liked, 'likes_count': photo.likes_count})


@photos_api.route('/<int:photo_id>/comments', methods=['GET'])
def list_photo_comments(photo_id):
    """List comments on a photo (public)."""
    photo = db.get_or_404(Photo, photo_id)
    from sqlalchemy.orm import joinedload
    comments = (photo.comments.options(joinedload(PhotoComment.user)).all())
    return jsonify({'comments': [_photo_comment_to_dict(c) for c in comments]})


@photos_api.route('/<int:photo_id>/comments', methods=['POST'])
@token_or_session
def add_photo_comment(photo_id):
    """Add a comment to a photo."""
    user = get_current_user()
    photo = db.get_or_404(Photo, photo_id)
    if not _garden_is_pro(photo.garden_id):
        return _pro_required_response()

    data = request.get_json(silent=True) or {}
    content = (data.get('content') or '').strip()
    if not content:
        return jsonify({'error': 'Comment text is required'}), 400
    if len(content) > 1000:
        return jsonify({'error': 'Comment is too long (max 1000 characters)'}), 400

    comment = PhotoComment(photo_id=photo.id, user_id=user.id, content=content)
    db.session.add(comment)
    db.session.commit()

    return jsonify(_photo_comment_to_dict(comment)), 201


@photos_api.route('/<int:photo_id>/comments/<int:comment_id>', methods=['DELETE'])
@token_or_session
def delete_photo_comment(photo_id, comment_id):
    """Delete a photo comment. Allowed for three groups only: the comment's
    creator, the garden admin (organizer), or a site admin."""
    user = get_current_user()
    comment = db.get_or_404(PhotoComment, comment_id)
    if comment.photo_id != photo_id:
        return jsonify({'error': 'Comment not found'}), 404

    photo = db.session.get(Photo, photo_id)
    can_delete = (comment.user_id == user.id
                  or _is_garden_admin(user, photo.garden_id if photo else None))
    if not can_delete:
        return jsonify({'error': 'Not authorized'}), 403

    db.session.delete(comment)
    db.session.commit()
    return jsonify({'success': True})
