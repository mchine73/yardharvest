import { Helmet } from 'react-helmet-async';

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
  const fullTitle = title ? `${title} — ${SITE_NAME}` : DEFAULT_TITLE;
  const desc = (description || DEFAULT_DESC).slice(0, 300);
  const canonicalPath =
    path != null
      ? path
      : typeof window !== 'undefined'
        ? window.location.pathname
        : '/';
  const url = `${SITE_URL}${canonicalPath}`;

  return (
    <Helmet prioritizeSeoTags>
      <title>{fullTitle}</title>
      <meta name="description" content={desc} />
      <link rel="canonical" href={url} />
      {noindex && <meta name="robots" content="noindex, follow" />}

      <meta property="og:type" content={type} />
      <meta property="og:site_name" content={SITE_NAME} />
      <meta property="og:title" content={fullTitle} />
      <meta property="og:description" content={desc} />
      <meta property="og:url" content={url} />
      {image && <meta property="og:image" content={image} />}

      <meta name="twitter:title" content={fullTitle} />
      <meta name="twitter:description" content={desc} />
      {image && <meta name="twitter:image" content={image} />}

      {jsonLd && (
        <script type="application/ld+json">{JSON.stringify(jsonLd)}</script>
      )}
    </Helmet>
  );
}
