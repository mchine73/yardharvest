import { useEffect, useMemo, useState } from 'react';
import { useParams, Link, Navigate } from 'react-router-dom';
import Seo from '../components/Seo';
import { publicAPI } from '../api';
import {
  ARTICLES, CATEGORIES, HELP_INTRO, HELP_TITLE,
  articlesIn, findArticle, searchArticles,
} from '../data/helpCenter';

/** The Help Centre — product documentation at /help.
 *
 *  Distinct from /about/guide, which is advice about starting a community
 *  garden in the real world. This answers "how do I do X in YardHarvest".
 *  No slug = hub; /help/<slug> = one article.
 */
export default function Help() {
  const { slug } = useParams();
  const [pricing, setPricing] = useState(null);

  // Pricing is fetched, never hardcoded: the column defaults in the model are
  // not the real prices, and a page that hardcoded them told Google the wrong
  // number for months.
  useEffect(() => {
    publicAPI.pricing()
      .then((r) => setPricing(r.data?.garden_pro || null))
      .catch(() => { /* articles render with the tokens stripped */ });
  }, []);

  useEffect(() => { window.scrollTo(0, 0); }, [slug]);

  const article = slug ? findArticle(slug) : null;
  if (slug && !article) return <Navigate to="/help" replace />;

  return article
    ? <ArticleView article={article} pricing={pricing} />
    : <HelpHub pricing={pricing} />;
}

/** Replace {{PRO_MONTHLY}} / {{PRO_YEARLY}} / {{TRIAL_DAYS}} with live values.
 *  Falls back to neutral wording rather than a stale number. */
function fillPricing(text, pricing) {
  if (!text) return text;
  return text
    .replace(/\{\{PRO_MONTHLY\}\}/g,
      pricing ? `$${pricing.monthly}` : 'a monthly fee')
    .replace(/\{\{PRO_YEARLY\}\}/g,
      pricing ? `$${pricing.yearly}` : 'a yearly fee')
    .replace(/\{\{TRIAL_DAYS\}\}/g,
      pricing ? String(pricing.trial_days) : 'a free');
}

// ---------------------------------------------------------------- the hub ---

function HelpHub({ pricing }) {
  const [query, setQuery] = useState('');
  const results = useMemo(() => searchArticles(query), [query]);
  const searching = query.trim().length > 0;

  return (
    <div className="mx-auto" style={{ maxWidth: 900 }}>
      <Seo
        title={HELP_TITLE}
        path="/help"
        description="How to run a community garden on YardHarvest: setup, plots, members, dues, Stripe payouts, Tap to Pay and troubleshooting."
      />
      <h1 className="h2 mb-2">{HELP_TITLE}</h1>
      <p className="text-muted mb-4" style={{ maxWidth: 640 }}>{HELP_INTRO}</p>

      <div className="mb-4">
        <div className="input-group input-group-lg">
          <span className="input-group-text bg-white"><i className="bi bi-search" /></span>
          <input
            type="search"
            className="form-control"
            placeholder="Search help — try “payout”, “dues”, “tap to pay”"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Search help articles"
          />
        </div>
      </div>

      {searching ? (
        <section aria-live="polite">
          <p className="text-muted small">
            {results.length === 0
              ? 'Nothing matched. Try a single word, or browse the sections below.'
              : `${results.length} article${results.length === 1 ? '' : 's'}`}
          </p>
          <div className="row g-3 mb-4">
            {results.map((a) => <ArticleCard key={a.slug} article={a} half />)}
          </div>
          {results.length === 0 && <CategoryGrid />}
        </section>
      ) : (
        <>
          <CategoryGrid />
          {CATEGORIES.map((cat) => (
            <section key={cat.key} id={`cat-${cat.key}`} className="mb-5">
              <h2 className="h5 mb-3">
                <i className={`bi ${cat.icon} text-success me-2`} />{cat.title}
              </h2>
              <div className="row g-3">
                {articlesIn(cat.key).map((a) => (
                  <ArticleCard key={a.slug} article={a} half />
                ))}
              </div>
            </section>
          ))}
        </>
      )}

      <HelpFooter pricing={pricing} />
    </div>
  );
}

function CategoryGrid() {
  return (
    <div className="row g-3 mb-5">
      {CATEGORIES.map((c) => (
        <div className="col-6 col-lg-4" key={c.key}>
          <a href={`#${c.key}`}
             onClick={(e) => {
               e.preventDefault();
               document.getElementById(`cat-${c.key}`)?.scrollIntoView({ behavior: 'smooth' });
             }}
             className="card h-100 shadow-sm text-decoration-none text-reset">
            <div className="card-body">
              <i className={`bi ${c.icon} text-success fs-4 d-block mb-1`} />
              <div className="fw-semibold">{c.title}</div>
              <div className="text-muted small">{c.blurb}</div>
            </div>
          </a>
        </div>
      ))}
    </div>
  );
}

function ArticleCard({ article, half }) {
  return (
    <div className={half ? 'col-md-6' : 'col-12'}>
      <Link to={`/help/${article.slug}`}
            className="card h-100 shadow-sm text-decoration-none text-reset guide-card">
        <div className="card-body">
          <h3 className="h6 mb-1">{article.title}</h3>
          <p className="text-muted small mb-0">{article.tagline}</p>
        </div>
      </Link>
    </div>
  );
}

// ------------------------------------------------------------ the article ---

function ArticleView({ article, pricing }) {
  const category = CATEGORIES.find((c) => c.key === article.category);
  const siblings = articlesIn(article.category);
  const idx = siblings.findIndex((a) => a.slug === article.slug);
  const prev = idx > 0 ? siblings[idx - 1] : null;
  const next = idx >= 0 && idx < siblings.length - 1 ? siblings[idx + 1] : null;
  const fill = (t) => fillPricing(t, pricing);

  return (
    <div className="mx-auto" style={{ maxWidth: 780 }}>
      <Seo
        title={`${article.title} — ${HELP_TITLE}`}
        path={`/help/${article.slug}`}
        description={article.description}
      />
      <nav aria-label="breadcrumb" className="mb-2" style={{ fontSize: '.85rem' }}>
        <Link to="/help" className="text-decoration-none">Help</Link>
        <span className="text-muted"> / {category?.title}</span>
      </nav>

      <h1 className="h2 mb-2">{article.title}</h1>
      <p className="text-muted mb-4">{article.tagline}</p>

      {article.sections.map((s, i) => (
        <section key={i} className="mb-4">
          <h2 className="h5 mb-2">
            {s.h}
            {s.pro && (
              <span className="badge bg-warning text-dark ms-2 align-middle"
                    style={{ fontSize: '.7rem' }}>Garden Pro</span>
            )}
          </h2>

          {(s.p || []).map((para, j) => (
            <p key={j} className="mb-2">{fill(para)}</p>
          ))}

          {s.steps && (
            <ol className="mb-2">
              {s.steps.map((step, j) => <li key={j} className="mb-1">{fill(step)}</li>)}
            </ol>
          )}

          {s.list && (
            <ul className="mb-2">
              {s.list.map((item, j) => <li key={j} className="mb-1">{fill(item)}</li>)}
            </ul>
          )}

          {s.warn && (
            <div className="alert alert-warning d-flex gap-2 py-2 small">
              <i className="bi bi-exclamation-triangle-fill mt-1" />
              <div>{fill(s.warn)}</div>
            </div>
          )}

          {s.tip && (
            <div className="alert alert-light border d-flex gap-2 py-2 small">
              <i className="bi bi-lightbulb mt-1 text-success" />
              <div>{fill(s.tip)}</div>
            </div>
          )}
        </section>
      ))}

      <hr className="my-4" />
      <div className="d-flex justify-content-between gap-2 flex-wrap mb-4">
        {prev
          ? <Link to={`/help/${prev.slug}`} className="btn btn-outline-secondary btn-sm">
              <i className="bi bi-arrow-left me-1" />{prev.title}
            </Link>
          : <span />}
        {next && (
          <Link to={`/help/${next.slug}`} className="btn btn-outline-secondary btn-sm ms-auto">
            {next.title}<i className="bi bi-arrow-right ms-1" />
          </Link>
        )}
      </div>

      <HelpFooter pricing={pricing} />
    </div>
  );
}

function HelpFooter() {
  return (
    <div className="card bg-light border-0 mb-5">
      <div className="card-body">
        <h2 className="h6 mb-2">Didn’t find it?</h2>
        <p className="small text-muted mb-3">
          Tell us the garden name and what you expected to happen — that is
          almost always enough for us to find it.
        </p>
        <div className="d-flex gap-2 flex-wrap">
          <Link to="/about#contact" className="btn btn-sm btn-success">Get in touch</Link>
          <Link to="/about/guide" className="btn btn-sm btn-outline-secondary">
            Starting a garden? Read the guide
          </Link>
        </div>
      </div>
    </div>
  );
}

export { ARTICLES };
