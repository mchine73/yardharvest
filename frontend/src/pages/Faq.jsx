import { useEffect, useMemo, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import Seo from '../components/Seo';
import FaqList, { answerable, useFaqContent, useFaqPricing } from '../components/FaqList';

/** /faq — short answers to what people ask before and just after signing up.
 *  Step-by-step instructions live in the help center; answers link there. */
export default function Faq() {
  const { t } = useTranslation();
  const { hash } = useLocation();
  const {
    CATEGORIES, FAQ_DESCRIPTION, FAQ_INTRO, FAQ_TITLE, QUESTIONS, searchQuestions,
  } = useFaqContent();
  const pricing = useFaqPricing();
  const [query, setQuery] = useState('');
  const [openId, setOpenId] = useState(null);

  const searching = query.trim().length > 0;
  const results = useMemo(
    () => answerable(searching ? searchQuestions(query) : QUESTIONS, pricing),
    [searching, searchQuestions, query, QUESTIONS, pricing]);

  // A link to /faq#<id> opens that question and scrolls to it.
  useEffect(() => {
    const id = decodeURIComponent((hash || '').slice(1));
    if (!id || !QUESTIONS.some((q) => q.id === id)) return;
    setOpenId(id);
    requestAnimationFrame(() => document.getElementById(id)?.scrollIntoView({ block: 'start' }));
  }, [hash, QUESTIONS]);

  const toggle = (id) => {
    setOpenId(id);
    // Keep the address shareable without adding a history entry per click.
    window.history.replaceState(null, '', id ? `#${id}` : window.location.pathname);
  };

  // FAQPage structured data in the page's language, built from exactly what
  // is shown. app/seo.py serves the same questions to crawlers without JS.
  const jsonLd = useMemo(() => ({
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: answerable(QUESTIONS, pricing).map(({ item, answer }) => ({
      '@type': 'Question',
      name: item.q,
      acceptedAnswer: { '@type': 'Answer', text: answer },
    })),
  }), [QUESTIONS, pricing]);

  return (
    <div className="mx-auto" style={{ maxWidth: 820 }}>
      <Seo title={FAQ_TITLE} path="/faq" description={FAQ_DESCRIPTION} jsonLd={jsonLd} />

      <div className="text-center py-4 yh-hero-glow mb-4">
        <h1 className="yh-hero-title mb-2">{FAQ_TITLE}</h1>
        <p className="text-muted mx-auto mb-4" style={{ maxWidth: 600 }}>{FAQ_INTRO}</p>
        <div className="mx-auto" style={{ maxWidth: 560 }}>
          <div className="input-group input-group-lg">
            <span className="input-group-text bg-white"><i className="bi bi-search" aria-hidden="true" /></span>
            <input
              type="search"
              className="form-control"
              placeholder={t('faq.searchPlaceholder')}
              aria-label={t('faq.searchLabel')}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
        </div>
      </div>

      {searching ? (
        <section aria-live="polite" className="mb-5">
          <p className="text-muted small">
            {results.length === 0 ? t('faq.noResults') : t('faq.resultCount', { count: results.length })}
          </p>
          <FaqList rows={results} openId={openId} onToggle={toggle} headingLevel={2} />
        </section>
      ) : (
        <>
          <nav aria-label={t('faq.jumpTo')} className="d-flex flex-wrap gap-2 justify-content-center mb-5">
            {CATEGORIES.map((c) => (
              <a key={c.key} href={`#topic-${c.key}`} className="btn btn-sm btn-outline-secondary rounded-pill"
                 onClick={(e) => {
                   e.preventDefault();
                   document.getElementById(`topic-${c.key}`)?.scrollIntoView({ behavior: 'smooth' });
                 }}>
                <i className={`bi ${c.icon} me-1`} aria-hidden="true" />{c.title}
              </a>
            ))}
          </nav>
          {CATEGORIES.map((c) => {
            const rows = results.filter(({ item }) => item.category === c.key);
            if (!rows.length) return null;
            return (
              <section key={c.key} id={`topic-${c.key}`} className="mb-5" style={{ scrollMarginTop: 90 }}>
                <h2 className="h5 mb-3">
                  <i className={`bi ${c.icon} text-success me-2`} aria-hidden="true" />{c.title}
                </h2>
                <FaqList rows={rows} openId={openId} onToggle={toggle} />
              </section>
            );
          })}
        </>
      )}

      <div className="yh-band-lime text-center p-4 p-md-5 mb-4" style={{ borderRadius: 12 }}>
        <h2 className="h4 mb-2">{t('faq.stillQuestions')}</h2>
        <p className="mb-3" style={{ color: '#2e3a1a' }}>{t('faq.stillQuestionsBody')}</p>
        <div className="d-flex flex-wrap gap-2 justify-content-center">
          <Link to="/help" className="yh-btn-dark"><i className="bi bi-life-preserver" aria-hidden="true" />{t('faq.visitHelp')}</Link>
          <Link to="/book" className="btn btn-outline-dark rounded-pill px-4">{t('faq.bookCall')}</Link>
        </div>
      </div>
    </div>
  );
}
