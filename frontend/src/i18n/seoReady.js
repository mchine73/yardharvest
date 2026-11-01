// Which paths may advertise themselves as available in every language.
//
// MIRRORS app/seo.py (TRANSLATED_PATHS / TRANSLATED_PREFIXES); tests/test_seo_es.py
// asserts the two agree, because a disagreement is invisible — the server
// would emit an hreflang the client then removes at hydration, or the other
// way round, and nothing would look broken from either side.
//
// A Spanish <title> on an English page is worse than an English one: it tells
// Google to serve that URL to a Spanish searcher who then cannot read it. So
// a path joins this list in the same commit that translates its page, never
// before. Terms and Privacy are deliberately absent (legal copy stays
// authoritative in English), and so is /book, whose heading, intro and
// meeting types are the host's own English.
export const TRANSLATED_PATHS = ['/', '/about', '/pricing', '/gardens',
  '/login', '/register', '/forgot-password', '/reset-password',
  '/verify-email-change', '/planting-calendar', '/harvest-forecast', '/groups',
  '/help', '/about/guide'];

// Pages under these share their parent's translated chrome. A garden's and a
// group's own words are the organizer's; help articles, guide chapters and
// crop guides are translated in full.
export const TRANSLATED_PREFIXES = ['/gardens/', '/groups/', '/help/',
  '/about/guide/', '/planting-guide/'];

/** Is the content at `path` available in every offered language? */
export function pathIsTranslated(path) {
  const p = (path || '/').replace(/\/+$/, '') || '/';
  return TRANSLATED_PATHS.includes(p)
    || TRANSLATED_PREFIXES.some((pre) => p.startsWith(pre));
}
