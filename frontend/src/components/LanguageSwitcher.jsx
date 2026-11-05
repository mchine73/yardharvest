import { useSiteConfig } from '../SiteConfigContext';
import { buildLanguageHref, currentLanguage } from '../i18n';

const LABELS = { en: 'English', es: 'Español' };

/**
 * Language picker. Renders nothing unless the server says more than one
 * language is actually on offer — a picker that switches to a half-translated
 * site is worse than no picker, and the server flag (SPANISH_ENABLED) is what
 * decides when that stops being true.
 *
 * Deliberately real links, not buttons: switching language changes the URL,
 * so it should middle-click, open in a new tab and be copyable like any other
 * navigation. It also means the server renders the target language on the
 * first paint rather than the client repainting after boot.
 *
 * `compact` (the desktop navbar, where width is short) shows only the
 * languages you are not reading, behind a globe: "Español" on an English page,
 * "English" on a Spanish one. Names are endonyms, each language in itself, so
 * a reader finds their own whichever page they landed on.
 */
export default function LanguageSwitcher({ className = '', compact = false }) {
  const { languages } = useSiteConfig();
  const offered = languages || ['en'];
  if (offered.length < 2) return null;

  if (compact) {
    return (
      <div className={`d-flex align-items-center ${className}`}>
        {offered.filter((code) => code !== currentLanguage).map((code) => (
          // Below 1200px the full name crowded a signed-in Spanish navbar
          // (zero gap at 992px), so it shortens to the code there; the label
          // and tooltip keep the name for screen readers and hover.
          <a key={code} href={buildLanguageHref(code)} className="nav-link small px-2"
             hrefLang={code} lang={code}
             aria-label={LABELS[code] || code} title={LABELS[code] || code}>
            <i className="bi bi-globe2 me-1" aria-hidden="true" />
            <span className="d-none d-xl-inline">{LABELS[code] || code}</span>
            <span className="d-xl-none">{code.toUpperCase()}</span>
          </a>
        ))}
      </div>
    );
  }

  return (
    <div className={`d-flex align-items-center gap-1 ${className}`}>
      {offered.map((code) => (
        code === currentLanguage ? (
          <span key={code} className="small fw-semibold px-1" aria-current="true">
            {LABELS[code] || code}
          </span>
        ) : (
          <a key={code} href={buildLanguageHref(code)} className="small px-1"
             hrefLang={code} lang={code}>
            {LABELS[code] || code}
          </a>
        )
      ))}
    </div>
  );
}
