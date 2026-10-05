"""Spanish metadata for the crawler view, and the gate that holds it back.

The rule these tests exist to enforce: **meta follows the language of the
content it describes.** A Spanish <title> on an English page is worse than an
English one — it tells Google to serve that URL to a Spanish searcher who then
cannot read it. So the Spanish copy, the hreflang alternates and the Spanish
sitemap entries are all gated on one question per path, and the marketing site
(still English) must keep serving English meta under /es/.

Two of these tests are parity checks against the client. They are the only
thing standing between "MIRRORS the client" as a comment and as a fact — a
disagreement is otherwise invisible, because the server would emit an hreflang
the client removes at hydration and nothing would look broken from either end.
"""
import json
import os
import re

import pytest

from app import seo

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DIST = os.path.join(_ROOT, 'frontend', 'dist')
needs_spa = pytest.mark.skipif(not os.path.isdir(_DIST),
                               reason='frontend/dist not built')


def _catalog(lang):
    path = os.path.join(_ROOT, 'frontend', 'src', 'i18n', 'locales', lang,
                        'common.json')
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


def _client_ready_lists():
    """The two lists out of frontend/src/i18n/seoReady.js.

    Parsed rather than imported: this is a Python test and the alternative is
    a Node round-trip in CI for two array literals.
    """
    path = os.path.join(_ROOT, 'frontend', 'src', 'i18n', 'seoReady.js')
    with open(path, encoding='utf-8') as fh:
        src = fh.read()

    def arr(name):
        m = re.search(r'export const %s = \[(.*?)\];' % name, src, re.S)
        assert m, 'could not find %s in seoReady.js' % name
        return set(re.findall(r"'([^']+)'", m.group(1)))

    return arr('TRANSLATED_PATHS'), arr('TRANSLATED_PREFIXES')


# --- the gate -------------------------------------------------------------

def test_marketing_pages_are_not_marked_translated():
    """The whole point of the gate. If one of these ever reads True without
    its page having been translated, /es/ starts advertising English pages to
    Spanish searchers."""
    for path in ('/', '/about', '/pricing', '/terms', '/privacy',
                 '/planting-calendar', '/harvest-forecast', '/book',
                 '/help', '/about/guide', '/groups'):
        assert not seo.path_is_translated(path), path


def test_translated_paths_include_the_screens_that_are_translated():
    for path in ('/gardens', '/login', '/register', '/forgot-password',
                 '/reset-password'):
        assert seo.path_is_translated(path), path
    # A garden's own page, either URL shape.
    assert seo.path_is_translated('/gardens/grd_abc123')
    assert seo.path_is_translated('/gardens/42')


def test_server_and_client_agree_on_which_paths_are_ready():
    paths, prefixes = _client_ready_lists()
    assert paths == set(seo.TRANSLATED_PATHS)
    assert prefixes == set(seo.TRANSLATED_PREFIXES)


# --- the copy -------------------------------------------------------------

def test_spanish_meta_mirrors_the_client_catalog():
    """The gardens directory is the one indexable page with Spanish copy on
    both sides, so it is where a drift would actually cost an impression."""
    es, en = _catalog('es'), _catalog('en')
    title, desc = seo.ES_PAGE_META['/gardens']
    assert title == es['gardensList']['title']
    assert desc == es['gardensList']['seoDescription']
    # And the English side still mirrors too, which is the older contract.
    en_title, en_desc = seo.PAGE_META['/gardens']
    assert en_title == en['gardensList']['title']
    assert en_desc == en['gardensList']['seoDescription']


def test_every_spanish_entry_has_an_english_source():
    for path in seo.ES_PAGE_META:
        assert path in seo.PAGE_META, path
    for path in seo.ES_NOINDEX_META:
        assert path in seo.NOINDEX_META, path


def test_no_spanish_entry_for_an_untranslated_page():
    for path in list(seo.ES_PAGE_META) + list(seo.ES_NOINDEX_META):
        assert seo.path_is_translated(path), path


def test_spanish_copy_is_not_just_the_english_copy():
    for path, (title, desc) in seo.ES_PAGE_META.items():
        assert (title, desc) != seo.PAGE_META[path], path
    for path, (title, desc) in seo.ES_NOINDEX_META.items():
        assert (title, desc) != seo.NOINDEX_META[path], path


def test_meta_for_path_picks_the_language(app):
    with app.app_context():
        es_title, es_desc, _, _, _ = seo._meta_for_path('/gardens', 'es')
        en_title, en_desc, _, _, _ = seo._meta_for_path('/gardens', 'en')
        assert es_title == 'Huertos comunitarios'
        assert es_title != en_title and es_desc != en_desc


def test_untranslated_page_keeps_english_copy_under_es(app):
    """/es/pricing is a real URL and it renders an English page. Describing it
    in Spanish is the failure this whole module guards against."""
    with app.app_context():
        title, desc, _, _, _ = seo._meta_for_path('/pricing', 'es')
        assert (title, desc) == seo.PAGE_META['/pricing']


# --- the injected head ----------------------------------------------------

def test_head_is_spanish_for_a_translated_path(app):
    with app.test_request_context():
        head = seo._build_head('/es/gardens')
        assert 'Huertos comunitarios' in head
        assert 'og:locale" content="es_ES"' in head
        # Each language canonicalizes to its own URL.
        assert re.search(r'rel="canonical" href="[^"]+/es/gardens"', head)


def test_head_is_english_for_an_untranslated_path_under_es(app):
    with app.test_request_context():
        head = seo._build_head('/es/pricing')
        assert '<title>Pricing' in head
        # Still the Spanish canonical: the URL exists and is not a duplicate.
        assert re.search(r'rel="canonical" href="[^"]+/es/pricing"', head)
        assert 'og:locale" content="es_ES"' in head


def test_no_hreflang_until_spanish_is_enabled(app):
    with app.test_request_context():
        app.config['SPANISH_ENABLED'] = False
        assert 'hreflang' not in seo._build_head('/gardens')


def test_hreflang_only_for_paths_whose_content_is_translated(app):
    with app.test_request_context():
        app.config['SPANISH_ENABLED'] = True
        try:
            ready = seo._build_head('/gardens')
            assert 'hreflang="es"' in ready and 'hreflang="en"' in ready
            assert 'hreflang="x-default"' in ready
            # Pricing is English; advertising a Spanish alternate for it is
            # precisely how a Spanish searcher lands on a page they cannot
            # read.
            assert 'hreflang' not in seo._build_head('/pricing')
        finally:
            app.config['SPANISH_ENABLED'] = False


# --- the sitemap ----------------------------------------------------------

def test_sitemap_has_no_spanish_urls_until_spanish_is_enabled(client, app):
    app.config['SPANISH_ENABLED'] = False
    body = client.get('/sitemap.xml').get_data(as_text=True)
    assert '/es/' not in body
    assert 'xhtml:link' not in body


def test_sitemap_lists_both_languages_with_reciprocal_alternates(client, app):
    app.config['SPANISH_ENABLED'] = True
    try:
        body = client.get('/sitemap.xml').get_data(as_text=True)
        assert '<loc>' in body and '/es/gardens</loc>' in body
        # Reciprocal: the English entry names the Spanish alternate and the
        # Spanish entry names the English one. A one-way pair is ignored.
        blocks = [b for b in body.split('<url>') if '/gardens</loc>' in b
                  or '/es/gardens</loc>' in b]
        assert len(blocks) >= 2
        for b in blocks:
            assert 'hreflang="en"' in b and 'hreflang="es"' in b
        # The gate holds here too: pricing is English-only.
        assert '/es/pricing' not in body
    finally:
        app.config['SPANISH_ENABLED'] = False


@needs_spa
def test_served_html_declares_spanish(client):
    body = client.get('/es/gardens').get_data(as_text=True)
    assert '<html lang="es"' in body
    assert 'Huertos comunitarios' in body
