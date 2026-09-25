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
 */
export default function LanguageSwitcher({ className = '' }) {
  const { languages } = useSiteConfig();
  const offered = languages || ['en'];
  if (offered.length < 2) return null;

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
