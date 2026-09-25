// Client-side language setup.
//
// The language is taken from the URL — /es/… — and nothing else, because the
// URL is what a shared link carries, what the crawler indexes, and what the
// server already used to decide the <html lang> and meta it injected. If the
// client inferred the language from a cookie while the server rendered from
// the path, the two would disagree on exactly the pages people share.
//
// Changing language is therefore a real navigation, not a state update: see
// buildLanguageHref. That costs one page load and buys a URL that means the
// same thing to the next person who opens it.
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

import enCommon from './locales/en/common.json';
import esCommon from './locales/es/common.json';

export const SUPPORTED = ['en', 'es'];
export const DEFAULT_LANGUAGE = 'en';

const PREFIX = new RegExp(`^/(${SUPPORTED.join('|')})(?:/|$)`);

/** The language named by a path, or null. */
export function languageFromPath(pathname) {
  const m = PREFIX.exec(pathname || '');
  return m ? m[1] : null;
}

/**
 * The router basename for a path: '/es' for Spanish, '' for English.
 *
 * This is the whole reason 74 routes and every <Link> needed no edits — React
 * Router prepends the basename to each, so `<Link to="/pricing">` resolves to
 * /es/pricing inside a Spanish session on its own.
 */
export function basenameFor(pathname) {
  const lang = languageFromPath(pathname);
  return lang && lang !== DEFAULT_LANGUAGE ? `/${lang}` : '';
}

/** The current path expressed in `lang` — what the language switcher links to. */
export function buildLanguageHref(lang, { pathname, search, hash } = window.location) {
  const current = languageFromPath(pathname);
  let rest = current ? pathname.slice(current.length + 1) : pathname;
  if (!rest.startsWith('/')) rest = `/${rest}`;
  if (rest === '/' ) rest = '';
  const prefix = lang === DEFAULT_LANGUAGE ? '' : `/${lang}`;
  return `${prefix}${rest}${search || ''}${hash || ''}` || '/';
}

export const currentLanguage = languageFromPath(window.location.pathname) || DEFAULT_LANGUAGE;

i18n.use(initReactI18next).init({
  resources: {
    en: { common: enCommon },
    es: { common: esCommon },
  },
  lng: currentLanguage,
  fallbackLng: DEFAULT_LANGUAGE,
  defaultNS: 'common',
  // A missing Spanish string renders the English one rather than the key.
  // Translation lands page by page, so half-translated is the normal state
  // for a while and "plots.title" on screen is the wrong way to show it.
  returnEmptyString: false,
  interpolation: { escapeValue: false },   // React escapes already
});

// Keep the served <html lang> honest after client-side navigation.
if (typeof document !== 'undefined') {
  document.documentElement.lang = currentLanguage;
}

export default i18n;
