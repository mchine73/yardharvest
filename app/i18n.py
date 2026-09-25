"""Language selection for the server: which language do we answer in?

Two audiences, two different questions, and conflating them is the bug this
module exists to prevent:

  * A **request** is answered in the language of whoever is reading the
    response — the signed-in user, or failing that what their browser asked
    for. ``resolve_locale`` decides that, and Flask-Babel calls it per request.

  * An **email or SMS** is written in the language of its *recipient*, who is
    usually not the person whose request triggered it. An organizer clicking
    "send dues reminders" is one request in English producing forty messages
    in whatever language each member chose. Anything that composes a message
    for somebody else must wrap it in ``force_locale(user)`` — see the
    docstring there.

Precedence for a request, highest first:

  1. ``/es/…`` in the path. The URL is the most explicit statement of intent
     there is, it is what a shared link carries, and it is what the crawler
     sees. If the URL says Spanish, the answer is Spanish.
  2. The signed-in user's saved preference.
  3. The ``yh_lang`` cookie, which is how a signed-out reader's choice
     survives a page load.
  4. ``Accept-Language``, for a first visit that has stated nothing.
  5. English.
"""
import logging
import os
import re

from flask import g, has_request_context, request

log = logging.getLogger(__name__)

#: Languages the product is actually translated into. Adding one here is not
#: enough to ship it — see SPANISH_ENABLED in config for the release switch.
SUPPORTED = ('en', 'es')
DEFAULT = 'en'

#: Cookie a signed-out reader's choice lives in.
COOKIE = 'yh_lang'

#: A leading language segment: /es, /es/, /es/gardens/4.
_PREFIX = re.compile(r'^/(%s)(?:/|$)' % '|'.join(SUPPORTED))


def normalize(value):
    """A supported language code, or None.

    Accepts the shapes that actually arrive: 'es', 'ES', 'es-MX', 'es_419'.
    A regional Spanish is answered in Spanish rather than dropped to English —
    a Mexican Spanish speaker reading es-419 is not better served by English.
    """
    if not value:
        return None
    code = str(value).strip().lower().replace('_', '-').split('-')[0]
    return code if code in SUPPORTED else None


def locale_from_path(path=None):
    """The language named by the URL, or None."""
    if path is None:
        path = request.path if has_request_context() else ''
    m = _PREFIX.match(path or '')
    return m.group(1) if m else None


def strip_prefix(path):
    """'/es/gardens' -> '/gardens'. Used wherever a path is matched against a
    route table that only knows the English URLs (seo.py's meta map, say)."""
    if not path:
        return path
    m = _PREFIX.match(path)
    if not m:
        return path
    rest = path[m.end():]
    return rest if rest.startswith('/') else '/' + rest


def resolve_locale():
    """The language for the current request. Flask-Babel's locale selector."""
    # An explicit forced locale (a message being composed for someone else)
    # wins over everything — the request context is not the audience.
    forced = getattr(g, '_forced_locale', None) if has_request_context() else None
    if forced:
        return forced

    if not has_request_context():
        return DEFAULT

    from_path = locale_from_path()
    if from_path:
        return from_path

    # Flask-Login hands back an anonymous proxy rather than None, so ask
    # whether it is a real session before trusting an attribute off it. The
    # lookup is cached per request by Flask-Login, not a query per string.
    try:
        from flask_login import current_user
        if getattr(current_user, 'is_authenticated', False):
            chosen = normalize(getattr(current_user, 'language', None))
            if chosen:
                return chosen
    except Exception:
        # Never let a language lookup break a response. English is a worse
        # answer than Spanish here, never a broken one.
        log.debug('Could not read the signed-in language preference', exc_info=True)

    chosen = normalize(request.cookies.get(COOKIE))
    if chosen:
        return chosen

    # Ask Werkzeug rather than parsing the header ourselves: it handles the
    # q-values and the ordering, which is exactly the part people get wrong.
    try:
        best = request.accept_languages.best_match(SUPPORTED)
    except Exception:
        best = None
    return normalize(best) or DEFAULT


class force_locale:
    """Render this block in ``target``'s language, whoever made the request.

    Every email and SMS composed for another person belongs inside one of
    these::

        with force_locale(member):
            subject, html = build_dues_reminder(...)

    Without it a Spanish-speaking member gets an English dues reminder any
    time an English-speaking organizer is the one who pressed the button, and
    nothing in the product says why. The failure is silent and it is only
    visible to the person least able to report it.

    Takes a user, a language code, or None (which means: change nothing).
    Restores the previous value on exit, including when the body raises.
    """

    def __init__(self, target):
        if target is None:
            self.locale = None
        elif isinstance(target, str):
            self.locale = normalize(target)
        else:
            self.locale = normalize(getattr(target, 'language', None))
        self._previous = None
        self._had_context = False

    def __enter__(self):
        if not self.locale or not has_request_context():
            return self
        self._had_context = True
        self._previous = getattr(g, '_forced_locale', None)
        g._forced_locale = self.locale
        try:
            from flask_babel import refresh
            refresh()
        except Exception:      # pragma: no cover - babel optional at import
            pass
        return self

    def __exit__(self, *exc):
        if not self._had_context:
            return False
        if self._previous:
            g._forced_locale = self._previous
        else:
            g.pop('_forced_locale', None)
        try:
            from flask_babel import refresh
            refresh()
        except Exception:      # pragma: no cover
            pass
        return False


def init_app(app):
    """Wire Flask-Babel up, and expose the language to templates."""
    from flask_babel import Babel

    app.config.setdefault('BABEL_DEFAULT_LOCALE', DEFAULT)
    # Absolute, because Flask-Babel resolves a relative path against the app
    # PACKAGE (app/translations), while the catalogs live at the repo root
    # where babel.cfg and the compile step put them. A mismatch here fails
    # silently — gettext just returns the English msgid — so it is spelled out
    # rather than left to a default.
    app.config.setdefault(
        'BABEL_TRANSLATION_DIRECTORIES',
        os.path.join(os.path.dirname(os.path.abspath(app.root_path)), 'translations'))
    Babel(app, locale_selector=resolve_locale)

    @app.before_request
    def _reset_language_cache():
        """Re-resolve the language for every request.

        Flask-Babel caches the resolved locale on ``g``, and ``g`` belongs to
        the application context — which outlives a single request whenever one
        is pushed around several (the test client does exactly this, and so
        does any long-lived worker that pushes its own). Without this, the
        FIRST request to touch a translated string pins the language for every
        request that follows it, which is the sort of bug that looks fine in
        development and serves one visitor's Spanish to everybody else.

        Cheap: the compiled catalog is cached on Babel's Domain object, so
        this clears a namespace and re-runs the selector, not a file read.
        """
        from flask_babel import refresh
        refresh()

    @app.after_request
    def _remember_language(response):
        """Persist a language chosen by navigating to /es/….

        The switcher is a plain link, so there is no JavaScript to POST a
        preference — the navigation IS the statement of intent, and this is
        where it gets recorded. Two places, for two reasons:

          * the cookie, so a signed-out reader's choice survives the next
            page load and the links they follow back to '/';
          * the user row, because that is what force_locale reads when their
            dues reminder is composed days later by somebody else's click.

        Only on document requests that actually name a language, and only
        when something would change — this must not be a database write on
        every page view.
        """
        try:
            lang = locale_from_path()
            if not lang or request.path.startswith(('/api/', '/static/', '/media/')):
                return response
            if request.cookies.get(COOKIE) != lang:
                response.set_cookie(COOKIE, lang, max_age=60 * 60 * 24 * 365,
                                    samesite='Lax', secure=request.is_secure,
                                    httponly=False)
            from flask_login import current_user
            if (getattr(current_user, 'is_authenticated', False)
                    and getattr(current_user, 'language', None) != lang):
                from app import db
                current_user.language = lang
                db.session.commit()
        except Exception:
            # A preference that failed to save is not worth failing a page for.
            try:
                from app import db
                db.session.rollback()
            except Exception:
                pass
            log.debug('Could not persist the language preference', exc_info=True)
        return response

    @app.context_processor
    def _inject_language():
        return {'current_language': resolve_locale(),
                'languages_enabled': enabled_languages()}


def enabled_languages():
    """Languages a reader may actually choose right now.

    Translation lands over several releases, so the catalogs existing is not
    the same as the product being ready to offer them. Spanish appears here
    only once SPANISH_ENABLED is set, which keeps a half-translated release
    from advertising itself as bilingual.
    """
    from flask import current_app
    langs = [DEFAULT]
    try:
        if current_app.config.get('SPANISH_ENABLED'):
            langs.append('es')
    except Exception:
        pass
    return langs
