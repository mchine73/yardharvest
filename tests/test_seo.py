"""SEO endpoints: robots.txt and the dynamic sitemap.xml.

The sitemap must enumerate static public pages plus every *active* garden so
search engines can discover individual content a client-rendered SPA hides.
Inactive gardens must be excluded.
"""
from werkzeug.security import generate_password_hash

from app import db as _db


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
        active_id, hidden_id = active.id, hidden.id

    r = client.get('/sitemap.xml')
    assert r.status_code == 200
    assert 'xml' in r.content_type
    body = r.get_data(as_text=True)
    assert '<urlset' in body
    # static pages (URLs use the app's configured SITE_URL)
    assert f'<loc>{base}/</loc>' in body
    assert f'<loc>{base}/gardens</loc>' in body
    # active garden included, inactive excluded
    assert f'{base}/gardens/{active_id}</loc>' in body
    assert f'{base}/gardens/{hidden_id}</loc>' not in body
