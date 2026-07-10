"""SEO endpoints: robots.txt, the dynamic sitemap.xml, llms.txt, and the
server-side per-route meta injection for no-JS crawlers.

The sitemap must enumerate static public pages plus every *active* garden so
search engines can discover individual content a client-rendered SPA hides.
Inactive gardens must be excluded.

Meta-injection tests need the built SPA (frontend/dist); they skip when it's
absent (e.g. a backend-only CI job).
"""
import os

import pytest
from werkzeug.security import generate_password_hash

from app import db as _db

_DIST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     'frontend', 'dist')
needs_spa = pytest.mark.skipif(not os.path.isdir(_DIST),
                               reason='frontend/dist not built')


def test_robots_txt(client):
    r = client.get('/robots.txt')
    assert r.status_code == 200
    assert 'text/plain' in r.content_type
    body = r.get_data(as_text=True)
    assert 'User-agent:' in body
    assert 'Disallow: /admin' in body
    assert 'Sitemap:' in body and 'sitemap.xml' in body


def test_sitemap_lists_static_pages_and_active_gardens(client, app):
    from app.models import User, CommunityGarden
    with app.app_context():
        base = (app.config.get('SITE_URL') or 'https://www.yardharvest.app').rstrip('/')
        u = User(username='seo_org', email='seo_org@example.com',
                 password_hash=generate_password_hash('password123'))
        _db.session.add(u)
        _db.session.flush()
        active = CommunityGarden(name='SEO Test Garden', slug='seo-test-garden',
                                 organizer_id=u.id, is_active=True)
        hidden = CommunityGarden(name='Hidden Garden', slug='hidden-seo-garden',
                                 organizer_id=u.id, is_active=False)
        _db.session.add_all([active, hidden])
        _db.session.commit()
        active_pid, hidden_pid = active.public_id, hidden.public_id

    r = client.get('/sitemap.xml')
    assert r.status_code == 200
    assert 'xml' in r.content_type
    body = r.get_data(as_text=True)
    assert '<urlset' in body
    # static pages (URLs use the app's configured SITE_URL)
    assert f'<loc>{base}/</loc>' in body
    assert f'<loc>{base}/gardens</loc>' in body
    # active garden included under its canonical public_id URL (the legacy
    # numeric shape made crawlers see every garden twice), inactive excluded
    assert f'{base}/gardens/{active_pid}</loc>' in body
    assert f'{base}/gardens/{hidden_pid}</loc>' not in body


def test_sitemap_includes_book(client, app):
    with app.app_context():
        base = (app.config.get('SITE_URL') or 'https://www.yardharvest.app').rstrip('/')
    body = client.get('/sitemap.xml').get_data(as_text=True)
    assert f'<loc>{base}/book</loc>' in body


def test_robots_disallows_manage_links(client):
    body = client.get('/robots.txt').get_data(as_text=True)
    assert 'Disallow: /book/manage/' in body


def test_llms_txt_is_real_text(client):
    """Regression: the SPA catch-all used to swallow /llms.txt and return HTML."""
    r = client.get('/llms.txt')
    assert r.status_code == 200
    assert 'text/plain' in r.content_type
    body = r.get_data(as_text=True)
    assert body.startswith('# YardHarvest')
    assert '/book' in body and 'Pricing' in body
    assert '<!doctype' not in body.lower()


# ---------------------------------------------------------------------------
# Server-side meta injection (the no-JS crawler view)
# ---------------------------------------------------------------------------

@needs_spa
def test_home_injects_default_meta_and_jsonld(client):
    html = client.get('/').get_data(as_text=True)
    assert '<title>YardHarvest — Community Garden Management Platform</title>' in html
    assert 'meta name="description"' in html
    assert 'SoftwareApplication' in html
    assert 'rel="canonical"' in html


@needs_spa
def test_pricing_injects_route_meta_and_faq(client):
    html = client.get('/pricing').get_data(as_text=True)
    assert '<title>Pricing — YardHarvest</title>' in html
    assert 'Simple, transparent pricing' in html
    assert 'FAQPage' in html
    assert 'Is there a contract?' in html


@needs_spa
def test_book_route_meta(client):
    html = client.get('/book').get_data(as_text=True)
    assert '<title>Book time with James — YardHarvest</title>' in html
    assert '30-minute intro call' in html


@needs_spa
def test_book_manage_is_noindex(client):
    html = client.get('/book/manage/bkg_whatever').get_data(as_text=True)
    assert 'noindex' in html
    assert 'rel="canonical"' not in html   # private URLs get no canonical


@needs_spa
def test_garden_detail_injects_db_meta(client, app):
    from app.models import User, CommunityGarden
    with app.app_context():
        u = User(username='seo_meta', email='seo_meta@example.com',
                 password_hash=generate_password_hash('password123'))
        _db.session.add(u)
        _db.session.flush()
        g = CommunityGarden(name='Sunny Acres Garden', slug='sunny-acres-seo',
                            city='Lincoln', state='NE',
                            description='A neighborhood garden with 40 plots.',
                            organizer_id=u.id, is_active=True)
        _db.session.add(g)
        _db.session.commit()
        gid = g.id
    html = client.get(f'/gardens/{gid}').get_data(as_text=True)
    assert 'Sunny Acres Garden' in html
    assert 'Lincoln' in html
    assert 'A neighborhood garden with 40 plots.' in html


def test_sitemap_includes_guide_chapters(client, app):
    with app.app_context():
        base = (app.config.get('SITE_URL') or 'https://www.yardharvest.app').rstrip('/')
    body = client.get('/sitemap.xml').get_data(as_text=True)
    assert f'<loc>{base}/about/guide</loc>' in body
    assert f'<loc>{base}/about/guide/getting-started</loc>' in body
    assert f'<loc>{base}/about/guide/troubleshooting</loc>' in body


@needs_spa
def test_guide_hub_and_chapter_meta(client):
    hub = client.get('/about/guide').get_data(as_text=True)
    assert '<title>The Community Garden Guide — YardHarvest</title>' in hub
    ch = client.get('/about/guide/finding-land').get_data(as_text=True)
    assert ('<title>Finding Land &amp; Site Planning — The Community Garden '
            'Guide — YardHarvest</title>' in ch)
    assert '"@type": "Article"' in ch or 'Article' in ch
    # Unknown chapter falls back to hub meta (SPA redirects there).
    unknown = client.get('/about/guide/nonsense').get_data(as_text=True)
    assert '<title>The Community Garden Guide — YardHarvest</title>' in unknown


@needs_spa
def test_unknown_route_falls_back_to_defaults(client):
    html = client.get('/some/unknown/path').get_data(as_text=True)
    assert '<title>YardHarvest — Community Garden Management Platform</title>' in html


@needs_spa
def test_hashed_assets_get_immutable_cache(client):
    assets_dir = os.path.join(_DIST, 'assets')
    target = next(a for a in os.listdir(assets_dir) if a.endswith(('.js', '.css')))
    r = client.get(f'/assets/{target}')
    assert r.status_code == 200
    assert 'immutable' in r.headers.get('Cache-Control', '')


def test_bing_site_auth_served_only_when_configured(client, app):
    """/BingSiteAuth.xml serves Bing's verification XML from BING_SITE_AUTH;
    unset -> 404 so an empty/wrong file is never served."""
    app.config.pop('BING_SITE_AUTH', None)
    assert client.get('/BingSiteAuth.xml').status_code == 404
    app.config['BING_SITE_AUTH'] = 'ABC123DEF456'
    try:
        r = client.get('/BingSiteAuth.xml')
        assert r.status_code == 200
        assert 'xml' in r.content_type
        assert b'<user>ABC123DEF456</user>' in r.data
    finally:
        app.config.pop('BING_SITE_AUTH', None)


def _make_seo_garden(app, name='Canon Garden', slug='canon-garden-seo'):
    from app.models import User, CommunityGarden
    with app.app_context():
        u = User(username=f'u_{slug}'[:60], email=f'{slug}@example.com',
                 password_hash=generate_password_hash('password123'))
        _db.session.add(u)
        _db.session.flush()
        g = CommunityGarden(name=name, slug=slug, city='Omaha', state='NE',
                            organizer_id=u.id, is_active=True)
        _db.session.add(g)
        _db.session.commit()
        return g.id, g.public_id


def test_garden_public_id_url_gets_real_meta(client, app):
    """/gardens/grd_… (the shape the app links to everywhere) must inject the
    garden's real title — it used to fall through to the identical default
    title, which crawlers reported as mass duplicate titles."""
    gid, pid = _make_seo_garden(app, name='Opaque Meta Garden',
                                slug='opaque-meta-garden')
    html = client.get(f'/gardens/{pid}').get_data(as_text=True)
    assert 'Opaque Meta Garden' in html
    assert f'/gardens/{pid}"' in html          # canonical to itself


def test_numeric_garden_url_canonicalizes_to_public_id(client, app):
    """Legacy numeric garden URLs canonicalize to the public_id URL so both
    shapes collapse into ONE page for crawlers."""
    gid, pid = _make_seo_garden(app, name='Legacy Canon Garden',
                                slug='legacy-canon-garden')
    html = client.get(f'/gardens/{gid}').get_data(as_text=True)
    assert 'Legacy Canon Garden' in html
    assert f'rel="canonical" href="' in html
    assert f'/gardens/{pid}"' in html          # canonical points at public_id


def test_auth_pages_have_unique_noindex_meta(client):
    login = client.get('/login').get_data(as_text=True)
    assert '<title>Log in — YardHarvest</title>' in login
    assert 'noindex' in login
    register = client.get('/register').get_data(as_text=True)
    assert '<title>Create your account — YardHarvest</title>' in register
    assert 'noindex' in register
    forgot = client.get('/forgot-password').get_data(as_text=True)
    assert 'Reset your password' in forgot and 'noindex' in forgot


def test_planting_guide_crop_meta(client):
    html = client.get('/planting-guide/Tomatoes').get_data(as_text=True)
    assert '<title>Tomatoes Growing Guide — YardHarvest</title>' in html
    assert 'When and how to plant tomatoes' in html


def test_indexnow_key_file(client, app):
    # Unset -> plain 404, never the SPA shell.
    r = client.get('/whatever-key.txt')
    assert r.status_code == 404 and 'html' not in r.content_type
    app.config['INDEXNOW_KEY'] = 'abc123def456abc123def456abc123de'
    try:
        ok = client.get('/abc123def456abc123def456abc123de.txt')
        assert ok.status_code == 200
        assert ok.get_data(as_text=True) == 'abc123def456abc123def456abc123de'
        # A wrong key still 404s, and the explicit .txt routes still win.
        assert client.get('/wrong-key.txt').status_code == 404
        assert b'User-agent' in client.get('/robots.txt').data
        assert client.get('/llms.txt').status_code == 200
    finally:
        app.config.pop('INDEXNOW_KEY', None)
