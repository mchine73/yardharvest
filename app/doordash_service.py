"""DoorDash Drive API integration for delivery.

Uses JWT auth with DoorDash Drive API.
Gracefully degrades to mock/dev mode when credentials are not configured.

Env vars required for production:
  DOORDASH_DEVELOPER_ID, DOORDASH_KEY_ID, DOORDASH_SIGNING_SECRET
"""
import os
import time
import uuid
import json

DOORDASH_DEVELOPER_ID = os.environ.get('DOORDASH_DEVELOPER_ID', '')
DOORDASH_KEY_ID = os.environ.get('DOORDASH_KEY_ID', '')
DOORDASH_SIGNING_SECRET = os.environ.get('DOORDASH_SIGNING_SECRET', '')
DOORDASH_API_BASE = 'https://openapi.doordash.com/drive/v2'

# Try to import JWT for signing; graceful fallback
try:
    import jwt
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False

# Try to import requests
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


def _is_configured():
    """Check if DoorDash credentials are available."""
    return bool(DOORDASH_DEVELOPER_ID and DOORDASH_KEY_ID and DOORDASH_SIGNING_SECRET
                and JWT_AVAILABLE and REQUESTS_AVAILABLE)


def _create_jwt():
    """Create a signed JWT for DoorDash API authentication."""
    if not _is_configured():
        return None
    payload = {
        'aud': 'doordash',
        'iss': DOORDASH_DEVELOPER_ID,
        'kid': DOORDASH_KEY_ID,
        'exp': int(time.time()) + 300,  # 5 min expiry
        'iat': int(time.time()),
    }
    token = jwt.encode(
        payload,
        DOORDASH_SIGNING_SECRET,
        algorithm='HS256',
        headers={'dd-ver': 'DD-JWT-V1'},
    )
    return token


def _headers():
    """Build request headers with JWT auth."""
    token = _create_jwt()
    if not token:
        return None
    return {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }


def get_delivery_quote(pickup_address, dropoff_address):
    """Get a delivery fee quote from DoorDash.

    Returns dict: {fee, estimated_pickup_time, estimated_delivery_time}
    In dev mode, returns mock data.
    """
    if not _is_configured():
        # Dev mode: return mock quote
        print(f"[DOORDASH DEV] Quote: {pickup_address} -> {dropoff_address}")
        return {
            'fee': 5.99,
            'estimated_pickup_time': '15-25 min',
            'estimated_delivery_time': '30-45 min',
            'currency': 'USD',
            'mock': True,
        }

    headers = _headers()
    try:
        resp = requests.post(
            f'{DOORDASH_API_BASE}/quotes',
            headers=headers,
            json={
                'external_delivery_id': str(uuid.uuid4()),
                'pickup_address': pickup_address,
                'dropoff_address': dropoff_address,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            'fee': data.get('fee', 0) / 100,  # DoorDash returns cents
            'estimated_pickup_time': data.get('pickup_time_estimated', ''),
            'estimated_delivery_time': data.get('dropoff_time_estimated', ''),
            'currency': data.get('currency', 'USD'),
            'mock': False,
        }
    except Exception as e:
        print(f"[DOORDASH ERROR] Quote failed: {e}")
        return {
            'fee': 5.99,
            'estimated_pickup_time': 'Unknown',
            'estimated_delivery_time': 'Unknown',
            'error': str(e),
            'mock': True,
        }


def create_delivery(order, pickup_address, dropoff_address, pickup_phone='', dropoff_phone=''):
    """Create a DoorDash Drive delivery.

    Returns dict: {delivery_id, tracking_url, status}
    In dev mode, returns mock delivery.
    """
    external_id = f'yh-order-{order.id}-{uuid.uuid4().hex[:8]}'

    if not _is_configured():
        print(f"[DOORDASH DEV] Create delivery for order #{order.id}")
        return {
            'delivery_id': f'mock-{external_id}',
            'tracking_url': f'https://track.doordash.com/mock/{external_id}',
            'status': 'created',
            'mock': True,
        }

    headers = _headers()
    try:
        resp = requests.post(
            f'{DOORDASH_API_BASE}/deliveries',
            headers=headers,
            json={
                'external_delivery_id': external_id,
                'pickup_address': pickup_address,
                'pickup_phone_number': pickup_phone,
                'dropoff_address': dropoff_address,
                'dropoff_phone_number': dropoff_phone,
                'order_value': int((order.subtotal or order.total_price) * 100),  # cents
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            'delivery_id': data.get('external_delivery_id', external_id),
            'tracking_url': data.get('tracking_url', ''),
            'status': data.get('delivery_status', 'created'),
            'mock': False,
        }
    except Exception as e:
        print(f"[DOORDASH ERROR] Create delivery failed: {e}")
        return {
            'delivery_id': f'failed-{external_id}',
            'tracking_url': '',
            'status': 'failed',
            'error': str(e),
            'mock': True,
        }


def get_delivery_status(delivery_id):
    """Check delivery status.

    Returns string status: created, confirmed, enroute_to_pickup, picked_up,
    enroute_to_dropoff, delivered, cancelled
    """
    if not _is_configured() or delivery_id.startswith('mock-'):
        return 'mock-delivered'

    headers = _headers()
    try:
        resp = requests.get(
            f'{DOORDASH_API_BASE}/deliveries/{delivery_id}',
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get('delivery_status', 'unknown')
    except Exception as e:
        print(f"[DOORDASH ERROR] Status check failed: {e}")
        return 'unknown'
