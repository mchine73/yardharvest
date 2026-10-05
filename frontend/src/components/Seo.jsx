import { Helmet } from 'react-helmet-async';
import i18n, { SUPPORTED, DEFAULT_LANGUAGE } from '../i18n';
import { pathIsTranslated } from '../i18n/seoReady';
import { useSiteConfig } from '../SiteConfigContext';

// Per-route SEO. To avoid duplicate tags, each tag is owned by exactly ONE
// source: this component owns all PER-PAGE tags (title, description, canonical,
// og:title/description/url, twitter:title/description). index.html owns only the
// CONSTANT social defaults Helmet doesn't emit by default — og:image,
// twitter:card, twitter:image — so non-JS social scrapers still get a brand
// preview. og:image/twitter:image are emitted here only when a page supplies a
// custom image (e.g. a garden photo). Works for JS-executing crawlers
// (Googlebot); per-page social previews on a SPA would need SSR/prerender.
const SITE_URL = 'https://www.yardharvest.app';
const SITE_NAME = 'YardHarvest';
const OG_LOCALES = { en: 'en_US', es: 'es_ES' };

/** Absolute URL for `path` in `lang`. The root is the awkward case: English
 *  keeps its trailing slash and Spanish is /es, not /es/. */
function urlFor(lang, path) {
  const prefix = lang === DEFAULT_LANGUAGE ? '' : `/${lang}`;
  if (path === '/') return SITE_URL + (prefix || '/');
  return SITE_URL + prefix + path;
}
const DEFAULT_TITLE = 'YardHarvest — Community Garden Management Platform';
const DEFAULT_DESC =
  'YardHarvest is the all-in-one platform for community gardens — manage plots, ' +
  'members, dues, events and volunteers, and grow a thriving local garden network.';

export default function Seo({
  title,
  description,
  path,
  image,
  type = 'website',
  noindex = false,
  jsonLd,
}) {
  const { languages } = useSiteConfig();
  const fullTitle = title ? `${title} — ${SITE_NAME}` : DEFAULT_TITLE;
  const desc = (description || DEFAULT_DESC).slice(0, 300);
  // `path` is the UNPREFIXED route, the same key the server's meta map uses.
  // The language comes from i18next, which took it from the URL.
  const canonicalPath =
    path != null
      ? path
      : typeof window !== 'undefined'
        ? window.location.pathname
        : '/';
  const lang = (i18n.language || DEFAULT_LANGUAGE).split('-')[0];
  const url = urlFor(SUPPORTED.includes(lang) ? lang : DEFAULT_LANGUAGE, canonicalPath);
  // Only where the content exists in every language, and only once more than
  // one is offered. An alternate pointing at an English page is how a Spanish
  // searcher gets served something they cannot read.
  const offered = (languages && languages.length > 1 ? languages : []).filter(
    (c) => SUPPORTED.includes(c));
  const alternates = (!noindex && offered.length > 1 && pathIsTranslated(canonicalPath))
    ? offered : [];

  return (
    <Helmet prioritizeSeoTags>
      <title>{fullTitle}</title>
      <meta name="description" content={desc} />
      <link rel="canonical" href={url} />
      {noindex && <meta name="robots" content="noindex, follow" />}

      <meta property="og:type" content={type} />
      <meta property="og:site_name" content={SITE_NAME} />
      <meta property="og:locale" content={OG_LOCALES[lang] || OG_LOCALES.en} />
      <meta property="og:title" content={fullTitle} />
      <meta property="og:description" content={desc} />
      <meta property="og:url" content={url} />
      {image && <meta property="og:image" content={image} />}

      <meta name="twitter:title" content={fullTitle} />
      <meta name="twitter:description" content={desc} />
      {image && <meta name="twitter:image" content={image} />}

      {alternates.map((code) => (
        <link key={code} rel="alternate" hrefLang={code} href={urlFor(code, canonicalPath)} />
      ))}
      {alternates.length > 0 && (
        <link rel="alternate" hrefLang="x-default" href={urlFor(DEFAULT_LANGUAGE, canonicalPath)} />
      )}

      {jsonLd && (
        <script type="application/ld+json">{JSON.stringify(jsonLd)}</script>
      )}
    </Helmet>
  );
}
