// Dates in the page's language, not the browser's.
//
// `new Date(x).toLocaleDateString()` with no locale uses the BROWSER's locale.
// A Spanish page opened in a US-English browser therefore renders "Sep 30,
// 2026" under Spanish prose — which is what shipped, and what nobody notices
// in review because the developer's browser agrees with the page.
//
// Passing an explicit 'en-US' is the same bug stated out loud; several call
// sites did that to force a short month name and got a permanently English
// date as the side effect.
//
// These helpers take the language from i18next, so the date follows the URL
// like every other string on the page. They return '' for a null or
// unparseable value rather than "Invalid Date".
import i18n from './index';

const BCP47 = { en: 'en-US', es: 'es-ES' };

/** The BCP-47 tag for the active language, for Intl. */
export function currentLocale() {
  const lang = (i18n.language || 'en').split('-')[0];
  return BCP47[lang] || BCP47.en;
}

function parse(value) {
  if (value === null || value === undefined || value === '') return null;
  const d = value instanceof Date ? value : new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** A date, in the page's language. Pass Intl options for a shorter form. */
export function formatDate(value, options) {
  const d = parse(value);
  return d ? d.toLocaleDateString(currentLocale(), options) : '';
}

/** Date and time together. */
export function formatDateTime(value, options) {
  const d = parse(value);
  return d ? d.toLocaleString(currentLocale(), options) : '';
}

/** Just the time. */
export function formatTime(value, options) {
  const d = parse(value);
  return d ? d.toLocaleTimeString(currentLocale(), options) : '';
}

/** "Sep 30" / "30 sept" — the short form used in activity feeds. */
export const DAY_MONTH = { month: 'short', day: 'numeric' };
/** "Sep 30, 2026" / "30 sept 2026". */
export const DAY_MONTH_YEAR = { month: 'short', day: 'numeric', year: 'numeric' };
/** "Sep 30, 2:05 PM" / "30 sept, 14:05" — note es-ES picks a 24-hour clock. */
export const DAY_MONTH_TIME = {
  month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
};
/** "2:05 PM" / "14:05". */
export const HOUR_MINUTE = { hour: 'numeric', minute: '2-digit' };
