"""QR Code generation for shared resource checkout/return."""
import io
import secrets

try:
    import qrcode
    HAS_QR = True
except ImportError:
    HAS_QR = False


def generate_token():
    """Generate a unique token for a resource QR code."""
    return secrets.token_urlsafe(32)


def generate_resource_qr(garden_ref, resource_id, base_url):
    """Generate a QR code PNG for a shared resource.

    ``garden_ref`` is the garden's opaque public_id (it goes straight into the
    scannable URL). Returns PNG bytes or None if qrcode lib is not installed.
    """
    if not HAS_QR:
        return None

    url = f"{base_url}/gardens/{garden_ref}/resources/{resource_id}/scan"

    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color='#2d6a4f', back_color='white')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf.getvalue()
