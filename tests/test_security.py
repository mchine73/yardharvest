"""Tests for security middleware: Origin validation and security headers.

Covers set_security_headers + validate_origin in app/__init__.py, including
the path-aware CSP: /api/* (and the marketplace SPA) keep a strict script-src,
while the server-rendered CRM at /crm/* relaxes script-src to 'unsafe-inline'
(its lifted templates use inline event handlers).
"""


def test_security_headers_present(client):
    resp = client.get('/api/listings/categories')
    assert resp.headers['X-Content-Type-Options'] == 'nosniff'
    assert resp.headers['X-Frame-Options'] == 'SAMEORIGIN'
    assert resp.headers['Referrer-Policy'] == 'strict-origin-when-cross-origin'
    assert 'Content-Security-Policy' in resp.headers


def test_csp_script_src_locks_down_self_and_cdns(client):
    """The app's CSP allows self + specific CDNs but NOT 'unsafe-inline' in script-src."""
    resp = client.get('/api/listings/categories')
    csp = resp.headers['Content-Security-Policy']
    # Pull out the script-src directive.
    directives = {
        d.strip().split(' ', 1)[0]: d.strip()
        for d in csp.split(';') if d.strip()
    }
    script_src = directives['script-src']
    assert "'self'" in script_src
    assert 'https://js.stripe.com' in script_src
    # Inline scripts are not permitted -- this is the hardened behavior.
    assert "'unsafe-inline'" not in script_src


def test_csp_object_src_none(client):
    csp = client.get('/api/listings/categories').headers['Content-Security-Policy']
    assert "object-src 'none'" in csp


def test_csp_allows_stripe_connect_embedded_domains(client):
    """Embedded Connect onboarding loads Connect.js + iframes from
    connect-js.stripe.com; the CSP must allow it in script-src, frame-src and
    connect-src or in-app payout onboarding fails with 'Failed to load Connect.js'."""
    csp = client.get('/api/listings/categories').headers['Content-Security-Policy']
    directives = {d.strip().split(' ', 1)[0]: d.strip()
                  for d in csp.split(';') if d.strip()}
    assert 'https://connect-js.stripe.com' in directives['script-src']
    assert 'https://connect-js.stripe.com' in directives['frame-src']
    assert 'https://js.stripe.com' in directives['frame-src']
    assert 'https://connect-js.stripe.com' in directives['connect-src']


def test_csp_allows_https_images(client):
    """Garden/user photos may be Cloudinary CDN, OSM tiles, or external/seed
    URLs — img-src must allow any https host (else banners render blank)."""
    csp = client.get('/api/listings/categories').headers['Content-Security-Policy']
    img_src = [d.strip() for d in csp.split(';') if d.strip().startswith('img-src')][0]
    assert 'https:' in img_src.split()


def _script_src(csp):
    for d in csp.split(';'):
        d = d.strip()
        if d.startswith('script-src'):
            return d
    return ''


def test_csp_relaxes_unsafe_inline_for_crm(client):
    """/crm/* gets 'unsafe-inline' in script-src (inline handlers in templates)."""
    resp = client.get('/crm/login', follow_redirects=False)
    script_src = _script_src(resp.headers['Content-Security-Policy'])
    assert "'unsafe-inline'" in script_src


def test_csp_strict_for_non_crm_paths(client):
    """Non-CRM paths must NOT carry 'unsafe-inline' in script-src."""
    resp = client.get('/api/listings/categories')
    script_src = _script_src(resp.headers['Content-Security-Policy'])
    assert "'unsafe-inline'" not in script_src


def test_origin_check_rejects_foreign_origin_on_api_post(client):
    """State-changing /api/* requests with a disallowed Origin get a 403."""
    resp = client.post(
        '/api/auth/login',
        json={'email': 'x@example.com', 'password': 'whatever'},
        headers={'Origin': 'https://evil.example.com'},
    )
    assert resp.status_code == 403
    assert resp.get_json()['error'] == 'Invalid origin'


def test_origin_check_allows_no_origin_header(client, make_user):
    """Same-origin requests omit Origin -> should pass the check (here: reach auth logic)."""
    make_user(username='originok', email='originok@example.com', password='GoodPass1')
    resp = client.post('/api/auth/login', json={
        'email': 'originok@example.com', 'password': 'GoodPass1',
    })
    # Reaches the login handler (200), not blocked by origin check.
    assert resp.status_code == 200


def test_origin_check_skipped_for_get(client):
    """Safe methods are never blocked even with a foreign Origin."""
    resp = client.get('/api/listings/categories',
                      headers={'Origin': 'https://evil.example.com'})
    assert resp.status_code == 200


def test_origin_check_skipped_for_non_api(client):
    """Only /api/* paths are origin-protected; other POSTs pass through.

    The exact status depends on run mode (404 in dev, 200 SPA-fallback when a
    frontend/dist build is present), but the key invariant is that the Origin
    middleware does NOT block it with a 403.
    """
    resp = client.post('/not-an-api-path',
                       headers={'Origin': 'https://evil.example.com'})
    assert resp.status_code != 403


def test_api_404_returns_json(client):
    resp = client.get('/api/does/not/exist')
    assert resp.status_code == 404
    assert resp.get_json() == {'error': 'Not found'}
