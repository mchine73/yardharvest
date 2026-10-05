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
// before. The marketing site — home, about, pricing, terms, privacy, the
// planting calendar, the harvest forecast, the help centre, the garden guide —
// is deliberately absent.
export const TRANSLATED_PATHS = ['/gardens', '/login', '/register',
  '/forgot-password', '/reset-password'];

// A garden's own page: its chrome is translated, and the description is the
// organizer's own words, which no catalog can translate anyway.
export const TRANSLATED_PREFIXES = ['/gardens/'];

/** Is the content at `path` available in every offered language? */
export function pathIsTranslated(path) {
  const p = (path || '/').replace(/\/+$/, '') || '/';
  return TRANSLATED_PATHS.includes(p)
    || TRANSLATED_PREFIXES.some((pre) => p.startsWith(pre));
}
