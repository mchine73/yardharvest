"""Spanish metadata for the crawler view, and the gate that holds it back.

The rule these tests exist to enforce: **meta follows the language of the
content it describes.** A Spanish <title> on an English page is worse than an
English one — it tells Google to serve that URL to a Spanish searcher who then
cannot read it. So the Spanish copy, the hreflang alternates and the Spanish
sitemap entries are all gated on one question per path, and a page that is
still English (Terms, Privacy, /book) must keep serving English meta under /es/.

Two of these tests are parity checks against the client. They are the only
thing standing between "MIRRORS the client" as a comment and as a fact — a
disagreement is otherwise invisible, because the server would emit an hreflang
the client removes at hydration and nothing would look broken from either end.
"""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

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

def test_english_pages_are_not_marked_translated():
    """The whole point of the gate. If one of these ever reads True without
    its page having been translated, /es/ starts advertising English pages to
    Spanish searchers. Legal copy stays authoritative in English, and /book's
    heading, intro and meeting types are the host's own English words."""
    for path in ('/terms', '/privacy', '/book', '/book/manage/abc',
                 '/browse', '/search', '/admin'):
        assert not seo.path_is_translated(path), path


def test_translated_paths_include_the_screens_that_are_translated():
    for path in ('/', '/about', '/pricing', '/gardens', '/login', '/register',
                 '/forgot-password', '/reset-password', '/verify-email-change',
                 '/planting-calendar', '/harvest-forecast', '/groups', '/help',
                 '/about/guide'):
        assert seo.path_is_translated(path), path
    # A garden's own page, either URL shape.
    assert seo.path_is_translated('/gardens/grd_abc123')
    assert seo.path_is_translated('/gardens/42')
    for path in ('/groups/7', '/help/dues', '/about/guide/finding-land',
                 '/planting-guide/Tomatoes'):
        assert seo.path_is_translated(path), path


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
    """/es/terms is a real URL and it renders an English page. Describing it
    in Spanish is the failure this whole module guards against."""
    with app.app_context():
        title, desc, _, _, _ = seo._meta_for_path('/terms', 'es')
        assert (title, desc) == seo.PAGE_META['/terms']


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
        head = seo._build_head('/es/terms')
        assert '<title>Terms of Service' in head
        # Still the Spanish canonical: the URL exists and is not a duplicate.
        assert re.search(r'rel="canonical" href="[^"]+/es/terms"', head)
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
            # Terms is English; advertising a Spanish alternate for it is
            # precisely how a Spanish searcher lands on a page they cannot
            # read.
            assert 'hreflang' not in seo._build_head('/terms')
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
        # The gate holds here too: terms is English-only.
        assert '/es/terms' not in body
        # And the translated marketing site is listed in Spanish, root included.
        assert '/es/pricing</loc>' in body and '/es</loc>' in body
        assert '/es/help/dues</loc>' in body
    finally:
        app.config['SPANISH_ENABLED'] = False


@needs_spa
def test_served_html_declares_spanish(client):
    body = client.get('/es/gardens').get_data(as_text=True)
    assert '<html lang="es"' in body
    assert 'Huertos comunitarios' in body


# --- the mirrors ----------------------------------------------------------
#
# Each Spanish string here exists twice: once where the reader sees it (the
# catalog, or the help/guide data modules) and once here for the crawler. A
# reworded page that forgets this file leaves Google reading the old sentence,
# and nothing on either page would look wrong.

# path -> (title key, description key) in the client catalog.
_CATALOG_META = {
    '/gardens': ('gardensList.title', 'gardensList.seoDescription'),
    '/planting-calendar': ('plantingCalendar.seoTitle',
                           'plantingCalendar.seoDescription'),
    '/harvest-forecast': ('harvestForecast.seoTitle',
                          'harvestForecast.seoDescription'),
    '/groups': ('groups.seoTitle', 'groups.seoDescription'),
}


def _get(doc, dotted):
    for part in dotted.split('.'):
        doc = doc[part]
    return doc


@pytest.mark.parametrize('path', sorted(_CATALOG_META))
def test_page_meta_mirrors_the_catalog_in_both_languages(path):
    title_key, desc_key = _CATALOG_META[path]
    for lang, table in (('en', seo.PAGE_META), ('es', seo.ES_PAGE_META)):
        cat = _catalog(lang)
        assert table[path] == (_get(cat, title_key), _get(cat, desc_key)), (lang, path)


def _data_modules():
    """The help and guide modules, both languages, read through Node.

    They are ES modules with prose spread over concatenated literals; Node
    reads them exactly as the browser does, where a regex would not.
    """
    node = shutil.which('node')
    if not node:
        pytest.skip('node is not installed')
    data = os.path.join(_ROOT, 'frontend', 'src', 'data')
    url = lambda name: Path(os.path.join(data, name)).as_uri()
    script = (
        "const [he, hs, ge, gs] = await Promise.all(["
        f"import('{url('helpCenter.js')}'), import('{url('helpCenter.es.js')}'),"
        f"import('{url('gardenGuide.js')}'), import('{url('gardenGuide.es.js')}')]);"
        "const rows = (list) => list.map((x) => [x.slug, x.title, x.description]);"
        "console.log(JSON.stringify({"
        "help: {en: [he.HELP_TITLE, he.HELP_DESCRIPTION, rows(he.ARTICLES)],"
        "       es: [hs.HELP_TITLE, hs.HELP_DESCRIPTION, rows(hs.ARTICLES)]},"
        "guide: {en: [ge.GUIDE_TITLE, ge.GUIDE_DESCRIPTION, rows(ge.CHAPTERS)],"
        "        es: [gs.GUIDE_TITLE, gs.GUIDE_DESCRIPTION, rows(gs.CHAPTERS)]}}));")
    out = subprocess.run([node, '--input-type=module', '-e', script],
                         capture_output=True, text=True, encoding='utf-8',
                         timeout=60, check=True)
    return json.loads(out.stdout)


def test_help_meta_mirrors_the_data_modules():
    mods = _data_modules()['help']
    for lang, title, meta, hub in (
            ('en', seo.HELP_TITLE, seo.HELP_META, seo.PAGE_META['/help']),
            ('es', seo.ES_HELP_TITLE, seo.ES_HELP_META, seo.ES_PAGE_META['/help'])):
        m_title, m_desc, rows = mods[lang]
        assert (title, hub) == (m_title, (m_title, m_desc)), lang
        assert meta == {slug: (t, d) for slug, t, d in rows}, lang


def test_guide_meta_mirrors_the_data_modules():
    mods = _data_modules()['guide']
    for lang, title, meta, hub in (
            ('en', seo.GUIDE_TITLE, seo.GUIDE_META, seo.PAGE_META['/about/guide']),
            ('es', seo.ES_GUIDE_TITLE, seo.ES_GUIDE_META,
             seo.ES_PAGE_META['/about/guide'])):
        m_title, m_desc, rows = mods[lang]
        assert (title, hub) == (m_title, (m_title, m_desc)), lang
        assert meta == {slug: (t, d) for slug, t, d in rows}, lang


def test_crop_names_mirror_the_catalog():
    src = Path(_ROOT, 'frontend', 'src', 'data', 'plantingCrops.js').read_text(
        encoding='utf-8')
    keys = dict(re.findall(r"'([^']+)': 'crops\.(\w+)'", src))
    assert len(keys) >= 17, 'could not read CROP_KEYS from plantingCrops.js'
    crops = _catalog('es')['crops']
    assert seo.ES_CROP_NAMES == {cat: crops[k] for cat, k in keys.items()}


def test_crop_guide_templates_mirror_the_catalog():
    guide = _catalog('es')['cropGuide']
    as_py = lambda s: s.replace('{{crop}}', '{crop}')
    assert seo.ES_CROP_GUIDE_TITLE == as_py(guide['seoTitle'])
    assert seo.ES_CROP_GUIDE_DESC == as_py(guide['seoDescription'])


# --- the per-path branches ------------------------------------------------

def test_a_help_article_is_described_in_spanish(app):
    with app.app_context():
        title, desc, _, ld, _ = seo._meta_for_path('/help/dues', 'es')
        assert title == seo.ES_HELP_META['dues'][0] + ' — Ayuda de YardHarvest'
        assert desc == seo.ES_HELP_META['dues'][1]
        # The structured data names the page the reader is on.
        assert ld[0]['url'].endswith('/es/help/dues')
        assert ld[0]['isPartOf']['url'].endswith('/es/help')
        assert ld[0]['inLanguage'] == 'es'
        en_title, _, _, en_ld, _ = seo._meta_for_path('/help/dues', 'en')
        assert en_title.startswith(seo.HELP_META['dues'][0])
        assert en_ld[0]['url'].endswith('/help/dues')
        assert '/es/' not in en_ld[0]['url']


def test_a_guide_chapter_is_described_in_spanish(app):
    with app.app_context():
        title, desc, _, ld, _ = seo._meta_for_path('/about/guide/finding-land', 'es')
        assert title.startswith(seo.ES_GUIDE_META['finding-land'][0])
        assert ld[0]['url'].endswith('/es/about/guide/finding-land')


def test_a_crop_guide_is_described_in_spanish(app):
    with app.app_context():
        title, desc, *_ = seo._meta_for_path('/planting-guide/Tomatoes', 'es')
        assert title == 'Guía de cultivo: Jitomates'
        assert 'jitomates' in desc
        en_title, *_ = seo._meta_for_path('/planting-guide/Tomatoes', 'en')
        assert en_title == 'Tomatoes Growing Guide'


def test_a_category_with_a_slash_keeps_its_whole_name(app):
    """'Onions/Garlic' arrives with its slash decoded; taking the last
    segment titled the page 'Garlic'."""
    with app.app_context():
        en_title, *_ = seo._meta_for_path('/planting-guide/Onions/Garlic', 'en')
        es_title, *_ = seo._meta_for_path('/planting-guide/Onions%2FGarlic', 'es')
    assert en_title == 'Onions/Garlic Growing Guide'
    assert es_title == 'Guía de cultivo: Cebollas y ajos'


def test_an_unknown_help_article_points_at_the_hub_in_its_language(app):
    with app.app_context():
        title, desc, _, _, canonical = seo._meta_for_path('/help/nope', 'es')
    assert (title, desc) == seo.ES_PAGE_META['/help']
    assert canonical == '/help'


def test_book_stays_english_under_es(app):
    """The host's own heading and intro are English, and so is the call."""
    with app.app_context():
        assert not seo.path_is_translated('/book')
        assert seo._meta_for_path('/book', 'es')[:2] == seo.PAGE_META['/book']


# --- home, about, pricing -------------------------------------------------

def test_defaults_mirror_the_catalog():
    """The site-wide default title and description are what the client shows
    on a page with no title of its own - the home page among them."""
    for lang, title, desc in (('en', seo.DEFAULT_TITLE, seo.DEFAULT_DESC),
                              ('es', seo.ES_DEFAULT_TITLE, seo.ES_DEFAULT_DESC)):
        app_cat = _catalog(lang)['app']
        assert (title, desc) == (app_cat['seoDefaultTitle'],
                                 app_cat['seoDefaultDescription']), lang
        assert desc == _catalog(lang)['home']['seoDescription'], lang


@pytest.mark.parametrize('path,title_key,desc_key', [
    ('/about', 'about.about', 'about.seoDescription'),
    ('/pricing', 'pricing.pricing', 'pricing.seoDescription'),
])
def test_marketing_meta_mirrors_the_catalog(path, title_key, desc_key):
    for lang, table in (('en', seo.PAGE_META), ('es', seo.ES_PAGE_META)):
        cat = _catalog(lang)
        assert table[path] == (_get(cat, title_key), _get(cat, desc_key)), lang


def test_pricing_faq_mirrors_the_visible_faq():
    """FAQ structured data must match the questions on the page, word for
    word - in the language the page is in."""
    names = ['faqContract', 'faqTrialEnds', 'faqDues', 'faqMulti']
    for lang, faqs in (('en', seo.PRICING_FAQS), ('es', seo.ES_PRICING_FAQS)):
        pricing = _catalog(lang)['pricing']
        assert faqs == [(pricing[n + 'Q'], pricing[n + 'A']) for n in names], lang


def test_structured_data_follows_the_page_language(app):
    with app.app_context():
        *_, es_ld, _ = seo._meta_for_path('/pricing', 'es')
        *_, en_ld, _ = seo._meta_for_path('/pricing', 'en')
    es_faq = next(o for o in es_ld if o['@type'] == 'FAQPage')
    en_faq = next(o for o in en_ld if o['@type'] == 'FAQPage')
    assert es_faq['mainEntity'][0]['name'] == seo.ES_PRICING_FAQS[0][0]
    assert en_faq['mainEntity'][0]['name'] == seo.PRICING_FAQS[0][0]
    es_soft = next(o for o in es_ld if o['@type'] == 'SoftwareApplication')
    assert es_soft['description'] == seo.ES_DEFAULT_DESC
    assert 'mensual' in es_soft['offers'][0]['name']
    # Prices are numbers, the same in every language.
    en_soft = next(o for o in en_ld if o['@type'] == 'SoftwareApplication')
    assert [o['price'] for o in es_soft['offers']] == [o['price'] for o in en_soft['offers']]


def test_the_spanish_home_page_is_described_in_spanish(app):
    with app.test_request_context():
        head = seo._build_head('/es')
    assert '<title>%s</title>' % seo.ES_DEFAULT_TITLE in head
    assert 'Plataforma' in head
    assert re.search(r'rel="canonical" href="[^"]+/es"', head)
