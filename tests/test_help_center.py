"""The Help Center is described in two files, so make them prove they agree.

`frontend/src/data/helpCenter.js` holds the content the browser renders;
`app/seo.py` holds the titles and descriptions crawlers and the sitemap see.
Every previous instance of one rule living in two files in this codebase has
drifted — org types, the Garden Pro price, the Pro gate, scout vocabulary, the
dues fee. This is the same shape, so it gets the same guard.
"""
import io
import os
import re

import pytest

_DIST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     'frontend', 'dist')
# Meta injection happens while serving the built SPA's index.html, so these
# tests are meaningless on a backend-only CI job. Same marker as test_seo.py.
needs_spa = pytest.mark.skipif(not os.path.isdir(_DIST),
                               reason='frontend/dist not built')


HELP_JS = 'frontend/src/data/helpCenter.js'


def js_slugs():
    src = io.open(HELP_JS, encoding='utf-8').read()
    return [m.group(1) for m in re.finditer(r"^    slug: '([a-z0-9-]+)'", src, re.M)]


def js_categories():
    src = io.open(HELP_JS, encoding='utf-8').read()
    block = src[src.index('export const CATEGORIES'):src.index('export const ARTICLES')]
    return [m.group(1) for m in re.finditer(r"key: '([a-z]+)'", block)]


# ---------------------------------------------------------------------------
# Drift
# ---------------------------------------------------------------------------
def test_every_article_has_crawler_meta():
    from app.seo import HELP_META
    missing = [s for s in js_slugs() if s not in HELP_META]
    assert not missing, (
        'articles with no entry in seo.HELP_META (crawlers and the sitemap '
        'will not see them): %s' % missing)


def test_no_orphan_meta_entries():
    """A slug in HELP_META with no article 404s in the SPA and is a dead
    sitemap entry — worse than missing, because it looks intentional."""
    from app.seo import HELP_META
    orphans = [s for s in HELP_META if s not in js_slugs()]
    assert not orphans, 'HELP_META names articles that do not exist: %s' % orphans


def test_every_article_belongs_to_a_real_category():
    src = io.open(HELP_JS, encoding='utf-8').read()
    used = set(re.findall(r"^    category: '([a-z]+)'", src, re.M))
    known = set(js_categories())
    assert used <= known, 'articles in unknown categories: %s' % (used - known)
    # An empty category renders as a heading with nothing under it.
    assert known <= used, 'categories with no articles: %s' % (known - used)


def test_prices_are_never_hardcoded_in_help_content():
    """The column defaults are not the real prices. A page that hardcoded them
    told Google the wrong number for months — this file must use the tokens
    Help.jsx substitutes from the live pricing API."""
    src = io.open(HELP_JS, encoding='utf-8').read()
    body = src[src.index('export const ARTICLES'):]
    hardcoded = re.findall(r'\$\d+(?:\.\d\d)?\s*(?:a month|/mo|a year|/yr|per month|per year)',
                           body)
    assert not hardcoded, (
        'hardcoded prices in help content: %s — use {{PRO_MONTHLY}} / '
        '{{PRO_YEARLY}} instead' % hardcoded)


# ---------------------------------------------------------------------------
# What crawlers get
# ---------------------------------------------------------------------------
def test_the_resolver_answers_for_the_hub_and_every_article(app):
    """The unit the SPA-serving path calls, tested without needing a build so
    it still runs on a backend-only CI job."""
    from app.seo import HELP_META, _meta_for_path

    with app.test_request_context():
        title, desc, noindex, jsonld, canonical = _meta_for_path('/help')
        assert 'Help' in title and desc and not noindex

        for slug, (art_title, art_desc) in HELP_META.items():
            title, desc, noindex, jsonld, canonical = _meta_for_path('/help/%s' % slug)
            assert art_title in title, slug
            assert desc == art_desc, slug
            assert not noindex, slug
            # One Article node so the page can stand alone in search results.
            assert any(j.get('@type') == 'Article' for j in jsonld), slug


def test_the_resolver_sends_unknown_articles_to_the_hub(app):
    from app.seo import _meta_for_path
    with app.test_request_context():
        title, _desc, _noindex, _jsonld, canonical = _meta_for_path('/help/nope')
        assert canonical == '/help'
        assert 'Help' in title


@needs_spa
def test_the_hub_has_its_own_title_and_description(client):
    resp = client.get('/help', headers={'User-Agent': 'Googlebot'})
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'YardHarvest Help' in html
    assert 'name="description"' in html


@needs_spa
@pytest.mark.parametrize('slug', ['stripe-setup', 'dues', 'free-and-pro'])
def test_each_article_gets_its_own_meta(client, slug):
    from app.seo import HELP_META
    resp = client.get('/help/%s' % slug, headers={'User-Agent': 'Googlebot'})
    html = resp.get_data(as_text=True)
    title = HELP_META[slug][0]
    assert title in html, 'article title missing from server-rendered meta'
    # Articles must not all share the hub's description (duplicate-content).
    assert HELP_META[slug][1][:40] in html


@needs_spa
def test_an_unknown_article_points_crawlers_at_the_hub(client):
    """The SPA redirects unknown slugs to /help, so the meta has to agree or
    Search Console reports a soft 404 with a canonical pointing nowhere."""
    resp = client.get('/help/does-not-exist', headers={'User-Agent': 'Googlebot'})
    assert resp.status_code == 200
    assert 'YardHarvest Help' in resp.get_data(as_text=True)


def test_the_sitemap_lists_every_article(client):
    xml = client.get('/sitemap.xml').get_data(as_text=True)
    for slug in js_slugs():
        assert '/help/%s<' % slug in xml, 'not in sitemap: %s' % slug
    assert '/help<' in xml, 'the hub itself is missing from the sitemap'


def test_help_is_not_disallowed_in_robots(client):
    """It exists to be found — by search engines and by anyone pasting an
    error message into a search box."""
    body = client.get('/robots.txt').get_data(as_text=True)
    assert 'Disallow: /help' not in body
