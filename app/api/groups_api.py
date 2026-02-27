"""Neighborhood Garden Groups REST API endpoints."""
import math
import re

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.api.token_auth import token_or_session, get_current_user
from app import db
from app.models import (
    NeighborhoodGroup, GroupMembership, GroupPost, GroupPostComment,
    Listing, User
)
from app.helpers import geocode_address, haversine_miles

groups_api = Blueprint('groups_api', __name__, url_prefix='/api/groups')

OMAHA_NEIGHBORHOODS = [
    'Dundee', 'Benson', 'Blackstone', 'Aksarben', 'Midtown',
    'Elkhorn', 'Papillion', 'Ralston', 'Florence', 'Little Italy',
]


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    return re.sub(r'-+', '-', text)


def group_to_dict(group, include_preview=False):
    d = {
        'id': group.id,
        'name': group.name,
        'slug': group.slug,
        'description': group.description,
        'neighborhood': group.neighborhood,
        'city': group.city,
        'state': group.state,
        'zip_code': group.zip_code,
        'cover_photo_url': group.cover_photo_url,
        'is_public': group.is_public,
        'created_by_id': group.created_by_id,
        'created_by_name': group.created_by.display_name or group.created_by.username,
        'member_count': group.members.count(),
        'post_count': group.posts.count(),
        'created_at': group.created_at.isoformat() if group.created_at else None,
    }
    if include_preview:
        recent = group.posts.limit(3).all()
        d['recent_posts'] = [post_to_dict(p) for p in recent]
    return d


def membership_to_dict(membership):
    return {
        'id': membership.id,
        'user_id': membership.user_id,
        'username': membership.user.username,
        'display_name': membership.user.display_name or membership.user.username,
        'profile_image': membership.user.profile_image,
        'role': membership.role,
        'joined_at': membership.joined_at.isoformat() if membership.joined_at else None,
    }


def post_to_dict(post):
    return {
        'id': post.id,
        'group_id': post.group_id,
        'author_id': post.author_id,
        'author_name': post.author.display_name or post.author.username,
        'author_image': post.author.profile_image,
        'post_type': post.post_type,
        'title': post.title,
        'content': post.content,
        'photo_url': post.photo_url,
        'event_date': post.event_date.isoformat() if post.event_date else None,
        'event_location': post.event_location,
        'pinned': post.pinned,
        'comment_count': post.comments.count(),
        'created_at': post.created_at.isoformat() if post.created_at else None,
    }


def comment_to_dict(comment):
    return {
        'id': comment.id,
        'post_id': comment.post_id,
        'author_id': comment.author_id,
        'author_name': comment.author.display_name or comment.author.username,
        'author_image': comment.author.profile_image,
        'content': comment.content,
        'created_at': comment.created_at.isoformat() if comment.created_at else None,
    }


def get_membership(group_id, user_id):
    return GroupMembership.query.filter_by(group_id=group_id, user_id=user_id).first()


# ---------- Neighborhoods list ----------
@groups_api.route('/neighborhoods', methods=['GET'])
def neighborhoods():
    return jsonify(OMAHA_NEIGHBORHOODS)


# ---------- My groups ----------
@groups_api.route('/my-groups', methods=['GET'])
@token_or_session
def my_groups():
    memberships = GroupMembership.query.filter_by(user_id=get_current_user().id).all()
    group_ids = [m.group_id for m in memberships]
    groups = NeighborhoodGroup.query.filter(NeighborhoodGroup.id.in_(group_ids)).all()
    return jsonify([group_to_dict(g) for g in groups])


# ---------- Browse / search groups ----------
@groups_api.route('', methods=['GET'])
def browse():
    page = request.args.get('page', 1, type=int)
    per_page = 12
    search = request.args.get('search', '')
    neighborhood = request.args.get('neighborhood', '')
    zip_code = request.args.get('zip_code', '').strip()
    radius = request.args.get('radius', 25, type=float)

    q = NeighborhoodGroup.query.filter_by(is_public=True)
    if search:
        kw = f'%{search}%'
        q = q.filter(
            (NeighborhoodGroup.name.ilike(kw)) |
            (NeighborhoodGroup.description.ilike(kw))
        )
    if neighborhood:
        q = q.filter_by(neighborhood=neighborhood)

    # --- Distance-based filtering ---
    if zip_code:
        search_lat, search_lon = geocode_address(None, '', '', zip_code)
        if search_lat is not None and search_lon is not None:
            # Bounding-box pre-filter for performance
            lat_delta = radius / 69.0
            lon_delta = radius / (69.0 * max(math.cos(math.radians(search_lat)), 0.01))
            q = q.filter(
                NeighborhoodGroup.latitude.isnot(None),
                NeighborhoodGroup.latitude.between(search_lat - lat_delta, search_lat + lat_delta),
                NeighborhoodGroup.longitude.between(search_lon - lon_delta, search_lon + lon_delta),
            )
            candidates = q.all()
            # Precise haversine filter and sort by distance
            results = []
            for g in candidates:
                dist = haversine_miles(search_lat, search_lon, g.latitude, g.longitude)
                if dist <= radius:
                    d = group_to_dict(g)
                    d['distance'] = round(dist, 1)
                    results.append(d)
            results.sort(key=lambda x: x['distance'])
            # Manual pagination
            total = len(results)
            pages = max(1, math.ceil(total / per_page))
            start = (page - 1) * per_page
            end = start + per_page
            page_results = results[start:end]
            return jsonify({
                'groups': page_results,
                'total': total,
                'pages': pages,
                'page': page,
                'has_next': page < pages,
                'has_prev': page > 1,
            })
        # Geocoding failed -- fall through to normal query with no results for zip
        # (don't error, just return empty since we can't locate the zip)

    pagination = q.order_by(NeighborhoodGroup.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return jsonify({
        'groups': [group_to_dict(g) for g in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'page': pagination.page,
        'has_next': pagination.has_next,
        'has_prev': pagination.has_prev,
    })


# ---------- Group detail ----------
@groups_api.route('/<int:group_id>', methods=['GET'])
def detail(group_id):
    group = NeighborhoodGroup.query.get_or_404(group_id)
    data = group_to_dict(group, include_preview=True)
    if get_current_user().is_authenticated:
        membership = get_membership(group_id, get_current_user().id)
        data['my_membership'] = membership_to_dict(membership) if membership else None
    else:
        data['my_membership'] = None
    return jsonify(data)


# ---------- Create group ----------
@groups_api.route('', methods=['POST'])
@token_or_session
def create():
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'error': 'Group name is required'}), 400

    slug = slugify(data['name'])
    # Ensure unique slug
    base_slug = slug
    counter = 1
    while NeighborhoodGroup.query.filter_by(slug=slug).first():
        slug = f'{base_slug}-{counter}'
        counter += 1

    group = NeighborhoodGroup(
        name=data['name'],
        slug=slug,
        description=data.get('description', ''),
        neighborhood=data.get('neighborhood', ''),
        city=data.get('city', 'Omaha'),
        state=data.get('state', 'NE'),
        zip_code=data.get('zip_code', ''),
        cover_photo_url=data.get('cover_photo_url', ''),
        is_public=data.get('is_public', True),
        created_by_id=get_current_user().id,
    )

    # Auto-geocode if location info is available
    g_zip = data.get('zip_code', '')
    g_city = data.get('city', 'Omaha')
    g_state = data.get('state', 'NE')
    if g_zip or g_city:
        lat, lon = geocode_address(None, g_city, g_state, g_zip)
        if lat is not None:
            group.latitude = lat
            group.longitude = lon

    db.session.add(group)
    db.session.flush()

    # Creator becomes admin member
    membership = GroupMembership(
        group_id=group.id,
        user_id=get_current_user().id,
        role='admin',
    )
    db.session.add(membership)
    db.session.commit()
    return jsonify(group_to_dict(group)), 201


# ---------- Update group ----------
@groups_api.route('/<int:group_id>', methods=['PUT'])
@token_or_session
def update(group_id):
    group = NeighborhoodGroup.query.get_or_404(group_id)
    membership = get_membership(group_id, get_current_user().id)
    if not membership or membership.role != 'admin':
        return jsonify({'error': 'Not authorized'}), 403

    data = request.get_json()
    if data.get('name'):
        group.name = data['name']
    if 'description' in data:
        group.description = data['description']
    if 'neighborhood' in data:
        group.neighborhood = data['neighborhood']
    if 'zip_code' in data:
        group.zip_code = data['zip_code']
    if 'cover_photo_url' in data:
        group.cover_photo_url = data['cover_photo_url']
    if 'is_public' in data:
        group.is_public = data['is_public']

    db.session.commit()
    return jsonify(group_to_dict(group))


# ---------- Join group ----------
@groups_api.route('/<int:group_id>/join', methods=['POST'])
@token_or_session
def join(group_id):
    group = NeighborhoodGroup.query.get_or_404(group_id)
    existing = get_membership(group_id, get_current_user().id)
    if existing:
        return jsonify({'error': 'Already a member'}), 400

    membership = GroupMembership(
        group_id=group_id,
        user_id=get_current_user().id,
        role='member',
    )
    db.session.add(membership)
    db.session.commit()
    return jsonify(membership_to_dict(membership)), 201


# ---------- Leave group ----------
@groups_api.route('/<int:group_id>/leave', methods=['POST'])
@token_or_session
def leave(group_id):
    membership = get_membership(group_id, get_current_user().id)
    if not membership:
        return jsonify({'error': 'Not a member'}), 400
    db.session.delete(membership)
    db.session.commit()
    return jsonify({'message': 'Left group'})


# ---------- List members ----------
@groups_api.route('/<int:group_id>/members', methods=['GET'])
def members(group_id):
    group = NeighborhoodGroup.query.get_or_404(group_id)
    memberships = group.members.order_by(GroupMembership.joined_at).all()
    return jsonify([membership_to_dict(m) for m in memberships])


# ---------- Change member role ----------
@groups_api.route('/<int:group_id>/members/<int:user_id>/role', methods=['POST'])
@token_or_session
def change_role(group_id, user_id):
    my_membership = get_membership(group_id, get_current_user().id)
    if not my_membership or my_membership.role != 'admin':
        return jsonify({'error': 'Not authorized'}), 403

    target = get_membership(group_id, user_id)
    if not target:
        return jsonify({'error': 'User is not a member'}), 404

    data = request.get_json()
    new_role = data.get('role', 'member')
    if new_role not in ('member', 'moderator', 'admin'):
        return jsonify({'error': 'Invalid role'}), 400

    target.role = new_role
    db.session.commit()
    return jsonify(membership_to_dict(target))


# ---------- Feed (paginated posts) ----------
@groups_api.route('/<int:group_id>/feed', methods=['GET'])
def feed(group_id):
    group = NeighborhoodGroup.query.get_or_404(group_id)

    # Private groups require membership
    if not group.is_public:
        if not get_current_user().is_authenticated:
            return jsonify({'error': 'Authentication required'}), 401
        if not get_membership(group_id, get_current_user().id):
            return jsonify({'error': 'Members only'}), 403

    page = request.args.get('page', 1, type=int)
    per_page = 10
    post_type = request.args.get('type', '')

    q = GroupPost.query.filter_by(group_id=group_id)
    if post_type:
        q = q.filter_by(post_type=post_type)

    # Pinned first, then by date
    pagination = q.order_by(
        GroupPost.pinned.desc(), GroupPost.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'posts': [post_to_dict(p) for p in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'page': pagination.page,
        'has_next': pagination.has_next,
        'has_prev': pagination.has_prev,
    })


# ---------- Create post ----------
@groups_api.route('/<int:group_id>/posts', methods=['POST'])
@token_or_session
def create_post(group_id):
    group = NeighborhoodGroup.query.get_or_404(group_id)
    membership = get_membership(group_id, get_current_user().id)
    if not membership:
        return jsonify({'error': 'Must be a member to post'}), 403

    data = request.get_json()
    if not data or not data.get('content'):
        return jsonify({'error': 'Content is required'}), 400

    post = GroupPost(
        group_id=group_id,
        author_id=get_current_user().id,
        post_type=data.get('post_type', 'update'),
        title=data.get('title', ''),
        content=data['content'],
        photo_url=data.get('photo_url', ''),
        event_date=data.get('event_date'),
        event_location=data.get('event_location', ''),
    )
    db.session.add(post)
    db.session.commit()
    return jsonify(post_to_dict(post)), 201


# ---------- Edit post ----------
@groups_api.route('/<int:group_id>/posts/<int:post_id>', methods=['PUT'])
@token_or_session
def edit_post(group_id, post_id):
    post = GroupPost.query.filter_by(id=post_id, group_id=group_id).first_or_404()
    if post.author_id != get_current_user().id:
        return jsonify({'error': 'Not authorized'}), 403

    data = request.get_json()
    if data.get('title') is not None:
        post.title = data['title']
    if data.get('content'):
        post.content = data['content']
    if data.get('post_type'):
        post.post_type = data['post_type']
    if 'photo_url' in data:
        post.photo_url = data['photo_url']
    if 'event_date' in data:
        post.event_date = data['event_date']
    if 'event_location' in data:
        post.event_location = data['event_location']

    db.session.commit()
    return jsonify(post_to_dict(post))


# ---------- Delete post ----------
@groups_api.route('/<int:group_id>/posts/<int:post_id>', methods=['DELETE'])
@token_or_session
def delete_post(group_id, post_id):
    post = GroupPost.query.filter_by(id=post_id, group_id=group_id).first_or_404()
    membership = get_membership(group_id, get_current_user().id)

    # Author, moderator, or admin can delete
    can_delete = (
        post.author_id == get_current_user().id or
        (membership and membership.role in ('moderator', 'admin'))
    )
    if not can_delete:
        return jsonify({'error': 'Not authorized'}), 403

    # Delete comments first
    GroupPostComment.query.filter_by(post_id=post_id).delete()
    db.session.delete(post)
    db.session.commit()
    return jsonify({'message': 'Post deleted'})


# ---------- Pin / unpin post ----------
@groups_api.route('/<int:group_id>/posts/<int:post_id>/pin', methods=['POST'])
@token_or_session
def pin_post(group_id, post_id):
    post = GroupPost.query.filter_by(id=post_id, group_id=group_id).first_or_404()
    membership = get_membership(group_id, get_current_user().id)
    if not membership or membership.role not in ('moderator', 'admin'):
        return jsonify({'error': 'Not authorized'}), 403

    post.pinned = not post.pinned
    db.session.commit()
    return jsonify({'pinned': post.pinned})


# ---------- Get comments ----------
@groups_api.route('/<int:group_id>/posts/<int:post_id>/comments', methods=['GET'])
def get_comments(group_id, post_id):
    post = GroupPost.query.filter_by(id=post_id, group_id=group_id).first_or_404()
    comments = post.comments.all()
    return jsonify([comment_to_dict(c) for c in comments])


# ---------- Add comment ----------
@groups_api.route('/<int:group_id>/posts/<int:post_id>/comments', methods=['POST'])
@token_or_session
def add_comment(group_id, post_id):
    post = GroupPost.query.filter_by(id=post_id, group_id=group_id).first_or_404()
    membership = get_membership(group_id, get_current_user().id)
    if not membership:
        return jsonify({'error': 'Must be a member to comment'}), 403

    data = request.get_json()
    if not data or not data.get('content'):
        return jsonify({'error': 'Content is required'}), 400

    comment = GroupPostComment(
        post_id=post_id,
        author_id=get_current_user().id,
        content=data['content'],
    )
    db.session.add(comment)
    db.session.commit()
    return jsonify(comment_to_dict(comment)), 201


# ---------- Get single post ----------
@groups_api.route('/<int:group_id>/posts/<int:post_id>', methods=['GET'])
def get_post(group_id, post_id):
    post = GroupPost.query.filter_by(id=post_id, group_id=group_id).first_or_404()
    return jsonify(post_to_dict(post))


# ---------- Aggregate member listings ----------
@groups_api.route('/<int:group_id>/listings', methods=['GET'])
def group_listings(group_id):
    group = NeighborhoodGroup.query.get_or_404(group_id)
    member_ids = [m.user_id for m in group.members.all()]
    if not member_ids:
        return jsonify([])

    listings = Listing.query.filter(
        Listing.seller_id.in_(member_ids),
        Listing.is_active == True,
        Listing.quantity_available > 0,
    ).order_by(Listing.created_at.desc()).all()

    result = []
    for listing in listings:
        result.append({
            'id': listing.id,
            'seller_id': listing.seller_id,
            'seller_name': listing.seller.display_name or listing.seller.username,
            'seller_image': listing.seller.profile_image,
            'title': listing.title,
            'description': listing.description,
            'vegetable_type': listing.vegetable_type,
            'price': listing.price,
            'unit': listing.unit,
            'quantity_available': listing.quantity_available,
            'image_filename': listing.image_filename,
            'image_url': listing.image_url,
            'created_at': listing.created_at.isoformat() if listing.created_at else None,
        })
    return jsonify(result)
