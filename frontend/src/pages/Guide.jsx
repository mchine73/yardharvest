import { useEffect } from 'react';
import { useParams, Link, Navigate } from 'react-router-dom';
import Seo from '../components/Seo';
import { CHAPTERS, GUIDE_TITLE, GUIDE_INTRO } from '../data/gardenGuide';

/** The Community Garden Guide — a small sub-site under /about/guide.
 *  No slug = hub page (chapter cards); /about/guide/<slug> = chapter view. */
export default function Guide() {
  const { slug } = useParams();
  const idx = slug ? CHAPTERS.findIndex((c) => c.slug === slug) : -1;
  const chapter = idx >= 0 ? CHAPTERS[idx] : null;

  useEffect(() => { window.scrollTo(0, 0); }, [slug]);

  if (slug && !chapter) return <Navigate to="/about/guide" replace />;

  return chapter ? <ChapterView chapter={chapter} idx={idx} /> : <GuideHub />;
}

function GuideHub() {
  return (
    <div className="mx-auto" style={{ maxWidth: 860 }}>
      <Seo
        title={GUIDE_TITLE}
        path="/about/guide"
        description="A friendly, practical guide to starting and running a community garden — land, funding, building, organizing neighbors, and keeping it thriving."
      />
      <nav aria-label="breadcrumb" className="mb-2" style={{ fontSize: '.85rem' }}>
        <Link to="/about" className="text-decoration-none">About</Link>
        <span className="text-muted"> / Guide</span>
      </nav>
      <h1 className="h2 mb-2">{GUIDE_TITLE}</h1>
      <p className="text-muted mb-4" style={{ maxWidth: 640 }}>{GUIDE_INTRO}</p>

      <div className="row g-3 mb-5">
        {CHAPTERS.map((c, i) => (
          <div className="col-md-6" key={c.slug}>
            <Link to={`/about/guide/${c.slug}`}
                  className="card h-100 shadow-sm text-decoration-none text-reset guide-card">
              <div className="card-body">
                <div className="d-flex align-items-center mb-1" style={{ gap: '.6rem' }}>
                  <i className={`bi ${c.icon} text-success fs-4`} />
                  <h2 className="h5 mb-0">
                    <span className="text-muted me-1">{i + 1}.</span>{c.title}
                  </h2>
                </div>
                <p className="text-muted small mb-0">{c.tagline}</p>
              </div>
            </Link>
          </div>
        ))}
      </div>

      <GuideCta />
    </div>
  );
}

function ChapterView({ chapter, idx }) {
  const prev = idx > 0 ? CHAPTERS[idx - 1] : null;
  const next = idx < CHAPTERS.length - 1 ? CHAPTERS[idx + 1] : null;

  return (
    <div className="mx-auto" style={{ maxWidth: 720 }}>
      <Seo
        title={`${chapter.title} — ${GUIDE_TITLE}`}
        path={`/about/guide/${chapter.slug}`}
        description={chapter.description}
        type="article"
      />
      <nav aria-label="breadcrumb" className="mb-2" style={{ fontSize: '.85rem' }}>
        <Link to="/about" className="text-decoration-none">About</Link>
        <span className="text-muted"> / </span>
        <Link to="/about/guide" className="text-decoration-none">Guide</Link>
        <span className="text-muted"> / {chapter.title}</span>
      </nav>

      <p className="text-success fw-semibold mb-1" style={{ fontSize: '.85rem' }}>
        <i className={`bi ${chapter.icon} me-1`} />
        Chapter {idx + 1} of {CHAPTERS.length}
      </p>
      <h1 className="h2 mb-1">{chapter.title}</h1>
      <p className="text-muted mb-4">{chapter.tagline}</p>

      {chapter.sections.map((s) => (
        <section key={s.h} className="mb-4">
          <h2 className="h4 mb-3">{s.h}</h2>
          {s.p.map((para, i) => (
            <p key={i} style={{ lineHeight: 1.7 }}>{para}</p>
          ))}
          {s.list && (
            <ul style={{ lineHeight: 1.7 }}>
              {s.list.map((item, i) => <li key={i} className="mb-1">{item}</li>)}
            </ul>
          )}
        </section>
      ))}

      <GuideCta />

      <div className="d-flex justify-content-between border-top pt-3 mt-4 mb-5" style={{ gap: '1rem' }}>
        {prev ? (
          <Link to={`/about/guide/${prev.slug}`} className="text-decoration-none">
            <i className="bi bi-arrow-left me-1" />{prev.title}
          </Link>
        ) : <span />}
        {next ? (
          <Link to={`/about/guide/${next.slug}`} className="text-decoration-none text-end">
            {next.title}<i className="bi bi-arrow-right ms-1" />
          </Link>
        ) : (
          <Link to="/about/guide" className="text-decoration-none text-end">
            Back to the guide<i className="bi bi-arrow-up ms-1" />
          </Link>
        )}
      </div>
    </div>
  );
}

function GuideCta() {
  return (
    <div className="card border-0 shadow-sm mb-4" style={{ background: 'var(--brand-soft, #f4f9ec)' }}>
      <div className="card-body">
        <p className="mb-2 fw-semibold">Running the garden shouldn’t be a second job.</p>
        <p className="text-muted small mb-3">
          YardHarvest handles the boring parts of this guide for you — plots and
          waitlists, dues collection, events, volunteer hours, and the harvest
          numbers your annual report wants. Less admin, more garden.
        </p>
        <Link to="/pricing" className="btn btn-success btn-sm me-2">See pricing</Link>
        <Link to="/book" className="btn btn-outline-success btn-sm">Book a 30-min chat</Link>
      </div>
    </div>
  );
}
