import math
import os
import uuid
from functools import wraps
from PIL import Image
from werkzeug.utils import secure_filename
from flask import current_app, abort
from flask_login import current_user

try:
    from geopy.geocoders import Nominatim
    from geopy.extra.rate_limiter import RateLimiter
    geolocator = Nominatim(user_agent="yardharvest-prototype/1.0")
    geocode_fn = RateLimiter(geolocator.geocode, min_delay_seconds=1)
except Exception:
    geocode_fn = None


VEGETABLE_CATEGORIES = [
    ('tomatoes', 'Tomatoes'),
    ('peppers', 'Peppers'),
    ('cucumbers', 'Cucumbers'),
    ('squash', 'Squash & Zucchini'),
    ('herbs', 'Herbs'),
    ('greens', 'Leafy Greens'),
    ('beans', 'Beans & Peas'),
    ('corn', 'Corn'),
    ('berries', 'Berries'),
    ('root_vegetables', 'Root Vegetables'),
    ('onions', 'Onions & Garlic'),
    ('melons', 'Melons'),
    ('flowers', 'Edible Flowers'),
    ('eggs', 'Eggs'),
    ('honey', 'Honey'),
    ('preserves', 'Jams & Preserves'),
    ('other', 'Other'),
]

UNIT_CHOICES = [
    ('per lb', 'Per Pound'),
    ('each', 'Each'),
    ('per bunch', 'Per Bunch'),
    ('per basket', 'Per Basket'),
    ('per dozen', 'Per Dozen'),
    ('per bag', 'Per Bag'),
]


def geocode_address(address, city, state, zip_code):
    if not geocode_fn:
        return None, None
    try:
        full = f"{address}, {city}, {state} {zip_code}" if address else f"{city}, {state} {zip_code}"
        location = geocode_fn(full)
        if location:
            return location.latitude, location.longitude
    except Exception:
        pass
    return None, None


def haversine_miles(lat1, lon1, lat2, lon2):
    R = 3959
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    c = 2 * math.asin(math.sqrt(a))
    return R * c


def get_nearby_listings(lat, lon, radius_miles=10, query=None):
    from app.models import Listing
    lat_delta = radius_miles / 69.0
    lon_delta = radius_miles / (69.0 * max(math.cos(math.radians(lat)), 0.01))

    q = Listing.query.filter(
        Listing.is_active == True,
        Listing.quantity_available > 0,
        Listing.pickup_latitude.isnot(None),
        Listing.pickup_latitude.between(lat - lat_delta, lat + lat_delta),
        Listing.pickup_longitude.between(lon - lon_delta, lon + lon_delta)
    )

    if query:
        q = q.filter(
            db.or_(
                Listing.title.ilike(f'%{query}%'),
                Listing.description.ilike(f'%{query}%'),
                Listing.vegetable_type.ilike(f'%{query}%')
            )
        )

    candidates = q.all()
    results = []
    for listing in candidates:
        dist = haversine_miles(lat, lon, listing.pickup_latitude, listing.pickup_longitude)
        if dist <= radius_miles:
            listing.distance = round(dist, 1)
            results.append(listing)

    return sorted(results, key=lambda x: x.distance)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


def save_listing_image(file):
    if not file or not file.filename or not allowed_file(file.filename):
        return None
    ext = file.filename.rsplit('.', 1)[1].lower()

    # M10: Validate actual image content via PIL (not just extension)
    try:
        img = Image.open(file)
        img.verify()  # Verify it's a real image
        file.seek(0)  # Reset after verify
        img = Image.open(file)  # Re-open after verify (verify closes data)
    except Exception:
        return None  # Not a valid image file

    # Verify PIL-detected format matches claimed extension
    pil_format = (img.format or '').lower()
    allowed_formats = {'png': 'png', 'jpg': 'jpeg', 'jpeg': 'jpeg', 'gif': 'gif', 'webp': 'webp'}
    if ext not in allowed_formats or pil_format != allowed_formats[ext]:
        return None

    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    img.thumbnail((800, 800))
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')
    img.save(filepath, quality=85)
    return filename


def save_photo(file_storage, max_dimension=2000, max_file_size=4*1024*1024):
    """
    Save an uploaded photo with auto-downscaling.
    - Accepts up to 20MB uploads
    - Resizes to max 2000px on longest side
    - Progressively reduces JPEG quality until <= 4MB
    Returns (filename, file_size, width, height)
    """
    import io

    # Read the uploaded file
    img_data = file_storage.read()
    if len(img_data) > 20 * 1024 * 1024:
        raise ValueError('File too large (max 20MB)')

    # Open with Pillow
    img = Image.open(io.BytesIO(img_data))

    # Convert RGBA to RGB if needed
    if img.mode in ('RGBA', 'LA', 'P'):
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
        img = background
    elif img.mode != 'RGB':
        img = img.convert('RGB')

    # Resize if larger than max_dimension
    w, h = img.size
    if max(w, h) > max_dimension:
        if w > h:
            new_w = max_dimension
            new_h = int(h * max_dimension / w)
        else:
            new_h = max_dimension
            new_w = int(w * max_dimension / h)
        img = img.resize((new_w, new_h), Image.LANCZOS)

    w, h = img.size

    # Progressive quality reduction until <= max_file_size
    quality = 92
    while quality >= 20:
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=quality, optimize=True)
        file_size = buffer.tell()
        if file_size <= max_file_size:
            break
        quality -= 8

    # Generate unique filename
    ext = '.jpg'
    filename = f"photo_{uuid.uuid4().hex[:12]}{ext}"

    # Save to uploads directory
    upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, filename)

    buffer.seek(0)
    with open(filepath, 'wb') as f:
        f.write(buffer.read())

    return filename, file_size, w, h


def format_display_name(name):
    """Format name as 'FirstName L.' for privacy."""
    if not name:
        return 'Anonymous'
    parts = name.strip().split()
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]} {parts[-1][0]}."


def admin_required(f):
    """Require the current user to be an admin (supports both session and JWT auth)."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from app.api.token_auth import get_current_user
        user = get_current_user()
        if not user.is_authenticated or not user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def seller_required(f):
    """Require the current user to be a seller."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.can_sell():
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def buyer_required(f):
    """Require the current user to be a buyer."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.can_buy():
            abort(403)
        return f(*args, **kwargs)
    return decorated_function
