"""Language selection, and the one rule that matters: a message is written in
its RECIPIENT's language, not in the language of whoever triggered it.

Nothing is translated yet - P0 only builds the pipeline - so these assert the
machinery, plus the seeded 'Not found' string that proves gettext is wired all
the way from the catalog on disk to the response body.
"""
import pytest

from app import db as _db, i18n
from app.models import User


def test_normalize_accepts_the_shapes_that_actually_arrive():
    assert [i18n.normalize(v) for v in ('es', 'ES', 'es-MX', 'es_419')] == ['es'] * 4
    # A regional Spanish is answered in Spanish. Dropping es-419 to English
    # serves nobody: the reader asked for Spanish and we have Spanish.
    assert i18n.normalize('en-GB') == 'en'
    assert i18n.normalize('fr') is None
    assert i18n.normalize(None) is None
    assert i18n.normalize('') is None


@pytest.mark.parametrize('path,expected', [
    ('/es/gardens', '/gardens'),
    ('/es', '/'),
    ('/es/', '/'),
    ('/gardens', '/gardens'),
    # Not a prefix - a word that merely starts with the code.
    ('/estuary', '/estuary'),
    ('/english-garden', '/english-garden'),
])
def test_strip_prefix(path, expected):
    assert i18n.strip_prefix(path) == expected


def test_language_from_path_needs_a_segment_boundary():
    assert i18n.locale_from_path('/es/help') == 'es'
    assert i18n.locale_from_path('/es') == 'es'
    assert i18n.locale_from_path('/estuary') is None


# ---------------------------------------------------------------------------
# Precedence
# ---------------------------------------------------------------------------
def test_the_url_wins_over_the_header(app):
    """A shared link means what it says regardless of the browser opening it."""
    with app.test_request_context('/es/pricing', headers={'Accept-Language': 'en'}):
        assert i18n.resolve_locale() == 'es'


def test_the_header_is_used_when_nothing_else_is_stated(app):
    with app.test_request_context('/pricing',
                                  headers={'Accept-Language': 'es-MX,es;q=0.9,en;q=0.5'}):
        assert i18n.resolve_locale() == 'es'


def test_the_cookie_beats_the_header(app):
    """A choice someone made beats one their browser made for them."""
    with app.test_request_context(
            '/pricing',
            headers={'Accept-Language': 'en', 'Cookie': '%s=es' % i18n.COOKIE}):
        assert i18n.resolve_locale() == 'es'


def test_english_when_nothing_is_stated(app):
    with app.test_request_context('/pricing'):
        assert i18n.resolve_locale() == 'en'


def test_an_unsupported_language_falls_back(app):
    with app.test_request_context('/', headers={'Accept-Language': 'fr-CA,fr'}):
        assert i18n.resolve_locale() == 'en'


# ---------------------------------------------------------------------------
# The gettext chain
# ---------------------------------------------------------------------------
def test_a_translated_string_comes_back_translated(client):
    """Proves the whole path: catalog on disk -> compiled .mo -> response."""
    assert client.get('/api/nope').get_json()['error'] == 'Not found'
    es = client.get('/api/nope', headers={'Accept-Language': 'es'})
    assert es.get_json()['error'] == 'No encontrado'

def test_one_readers_language_does_not_leak_into_the_next_request(client):
    """Flask-Babel caches the resolved locale on `g`, which belongs to the
    APPLICATION context and so can outlive a single request. Without a
    per-request refresh the first request to touch a translated string pinned
    the language for every request after it — one visitor's Spanish served to
    everybody, and invisible in development where requests arrive one at a
    time in the same language."""
    first = client.get('/api/nope', headers={'Accept-Language': 'es'})
    second = client.get('/api/nope', headers={'Accept-Language': 'en'})
    third = client.get('/api/nope', headers={'Accept-Language': 'es'})
    assert [r.get_json()['error'] for r in (first, second, third)] == [
        'No encontrado', 'Not found', 'No encontrado']


def test_the_spa_renders_the_error_verbatim_so_nothing_else_changed(client):
    """The frontend prints `error` as-is in ~24 places. That is why the whole
    backend change is wrapping the string, not introducing error codes."""
    body = client.get('/api/nope', headers={'Accept-Language': 'es'}).get_json()
    assert set(body) == {'error'}


# ---------------------------------------------------------------------------
# force_locale - the rule this module exists for
# ---------------------------------------------------------------------------
def test_mail_is_written_in_the_recipients_language(app):
    """An English-speaking organizer pressing send must not turn a Spanish
    member's dues reminder into English. This is the failure that is invisible
    to everyone except the person least able to report it."""
    from flask_babel import gettext as _
    member = User(username='m', email='m@example.com', language='es')
    with app.test_request_context('/', headers={'Accept-Language': 'en'}):
        assert _('Not found') == 'Not found'
        with i18n.force_locale(member):
            assert _('Not found') == 'No encontrado'
        assert _('Not found') == 'Not found'


def test_force_locale_nests_and_restores(app):
    from flask_babel import gettext as _
    with app.test_request_context('/'):
        with i18n.force_locale('es'):
            with i18n.force_locale('en'):
                assert _('Not found') == 'Not found'
            assert _('Not found') == 'No encontrado'
        assert _('Not found') == 'Not found'


def test_force_locale_restores_after_an_exception(app):
    """A send that raises must not leave every later message in Spanish."""
    from flask_babel import gettext as _
    with app.test_request_context('/'):
        with pytest.raises(RuntimeError):
            with i18n.force_locale('es'):
                raise RuntimeError('send failed')
        assert _('Not found') == 'Not found'


def test_a_recipient_with_no_preference_changes_nothing(app):
    from flask_babel import gettext as _
    with app.test_request_context('/', headers={'Accept-Language': 'es'}):
        with i18n.force_locale(User(username='x', email='x@example.com',
                                    language=None)):
            assert _('Not found') == 'No encontrado'


# ---------------------------------------------------------------------------
# The release switch
# ---------------------------------------------------------------------------
def test_spanish_is_not_offered_until_the_flag_is_set(app):
    """Catalogs existing is not the same as the product being ready to say it
    is bilingual."""
    with app.app_context():
        app.config['SPANISH_ENABLED'] = False
        assert i18n.enabled_languages() == ['en']
        app.config['SPANISH_ENABLED'] = True
        assert i18n.enabled_languages() == ['en', 'es']


def test_site_config_reports_the_offered_languages(client, app):
    app.config['SPANISH_ENABLED'] = False
    assert client.get('/api/admin/site-config').get_json()['languages'] == ['en']
    app.config['SPANISH_ENABLED'] = True
    assert client.get('/api/admin/site-config').get_json()['languages'] == ['en', 'es']


# ---------------------------------------------------------------------------
# SEO: the crawler's view of a Spanish page
# ---------------------------------------------------------------------------
def test_a_spanish_page_keeps_its_own_identity(app):
    """/es/pricing is the pricing page, so it must get the pricing meta and
    canonicalize to ITSELF - pointing it at the English URL would tell Google
    it is a duplicate and drop it from the index."""
    from app import seo
    with app.app_context():
        app.config['SITE_URL'] = 'https://www.yardharvest.app'
        head = seo._build_head('/es/pricing')
        assert 'Pricing' in head
        assert 'href="https://www.yardharvest.app/es/pricing"' in head


def test_hreflang_waits_for_the_flag(app):
    """Advertising an alternate that is still half-English invites Google to
    serve it to Spanish searchers before there is Spanish on it."""
    from app import seo
    with app.app_context():
        app.config['SITE_URL'] = 'https://www.yardharvest.app'
        app.config['SPANISH_ENABLED'] = False
        assert 'hreflang' not in seo._build_head('/pricing')
        app.config['SPANISH_ENABLED'] = True
        head = seo._build_head('/pricing')
        assert 'hreflang="es"' in head and 'hreflang="x-default"' in head
