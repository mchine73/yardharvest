import { useState } from 'react';
import { useTranslation, Trans } from 'react-i18next';
import { Link } from 'react-router-dom';
import { useAuth } from '../AuthContext';
import { useSiteConfig } from '../SiteConfigContext';
import Seo from '../components/Seo';
import useScrollReveal from '../hooks/useScrollReveal';

export default function About() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const { marketplaceEnabled } = useSiteConfig();
  const [openFaq, setOpenFaq] = useState(null);
  useScrollReveal([marketplaceEnabled]);

  const toggleFaq = (index) => {
    setOpenFaq(openFaq === index ? null : index);
  };

  // Inside the component, so t() is in scope: the text follows the language.
  const buyerSteps = [
    { icon: 'bi-search', title: t('about.buyerStep1Title'), desc: t('about.buyerStep1Desc') },
    { icon: 'bi-cart-plus', title: t('about.buyerStep2Title'), desc: t('about.buyerStep2Desc') },
    { icon: 'bi-emoji-smile', title: t('about.buyerStep3Title'), desc: t('about.buyerStep3Desc') },
  ];

  const sellerSteps = [
    { icon: 'bi-camera', title: t('about.sellerStep1Title'), desc: t('about.sellerStep1Desc') },
    { icon: 'bi-bell', title: t('about.sellerStep2Title'), desc: t('about.sellerStep2Desc') },
    { icon: 'bi-wallet2', title: t('about.sellerStep3Title'), desc: t('about.sellerStep3Desc') },
  ];

  const marketplaceFeatures = [
    { icon: 'bi-pin-map-fill', title: t('about.mktFeat1Title'), desc: t('about.mktFeat1Desc') },
    { icon: 'bi-people', title: t('about.mktFeat2Title'), desc: t('about.mktFeat2Desc') },
    { icon: 'bi-flower2', title: t('about.mktFeat3Title'), desc: t('about.mktFeat3Desc') },
    { icon: 'bi-graph-up-arrow', title: t('about.mktFeat4Title'), desc: t('about.mktFeat4Desc') },
    { icon: 'bi-recycle', title: t('about.mktFeat5Title'), desc: t('about.mktFeat5Desc') },
    { icon: 'bi-heart-fill', title: t('about.mktFeat6Title'), desc: t('about.mktFeat6Desc') },
  ];

  const gardenFeatures = [
    { icon: 'bi-clipboard-check', title: t('about.gardenFeat1Title'), desc: t('about.gardenFeat1Desc') },
    { icon: 'bi-cash-coin', title: t('about.gardenFeat2Title'), desc: t('about.gardenFeat2Desc') },
    { icon: 'bi-people', title: t('about.gardenFeat3Title'), desc: t('about.gardenFeat3Desc') },
    { icon: 'bi-graph-up-arrow', title: t('about.gardenFeat4Title'), desc: t('about.gardenFeat4Desc') },
    { icon: 'bi-flower2', title: t('about.gardenFeat5Title'), desc: t('about.gardenFeat5Desc') },
    { icon: 'bi-building', title: t('about.gardenFeat6Title'), desc: t('about.gardenFeat6Desc') },
  ];

  const features = marketplaceEnabled ? marketplaceFeatures : gardenFeatures;

  const currentMonth = new Date().getMonth();
  const seasonalGuides = {
    winter: {
      months: t('about.winterMonths'),
      title: t('about.winterTitle'),
      items: [t('about.winterItem1'), t('about.winterItem2'), t('about.winterItem3'), t('about.winterItem4'), t('about.winterItem5')],
      tip: t('about.winterTip'),
    },
    spring: {
      months: t('about.springMonths'),
      title: t('about.springTitle'),
      items: [t('about.springItem1'), t('about.springItem2'), t('about.springItem3'), t('about.springItem4'), t('about.springItem5'), t('about.springItem6')],
      tip: t('about.springTip'),
    },
    summer: {
      months: t('about.summerMonths'),
      title: t('about.summerTitle'),
      items: [t('about.summerItem1'), t('about.summerItem2'), t('about.summerItem3'), t('about.summerItem4'), t('about.summerItem5'), t('about.summerItem6'), t('about.summerItem7')],
      tip: t('about.summerTip'),
    },
    fall: {
      months: t('about.fallMonths'),
      title: t('about.fallTitle'),
      items: [t('about.fallItem1'), t('about.fallItem2'), t('about.fallItem3'), t('about.fallItem4'), t('about.fallItem5'), t('about.fallItem6')],
      tip: t('about.fallTip'),
    },
  };

  const getSeason = () => {
    if (currentMonth >= 2 && currentMonth <= 4) return 'spring';
    if (currentMonth >= 5 && currentMonth <= 7) return 'summer';
    if (currentMonth >= 8 && currentMonth <= 10) return 'fall';
    return 'winter';
  };
  const season = seasonalGuides[getSeason()];

  // Literal keys rather than a template, so the key checker can see them.
  const gardenFaqs = [
    { q: t('about.gardenFaq1Q'), a: t('about.gardenFaq1A') },
    { q: t('about.gardenFaq2Q'), a: t('about.gardenFaq2A') },
    { q: t('about.gardenFaq3Q'), a: t('about.gardenFaq3A') },
    { q: t('about.gardenFaq4Q'), a: t('about.gardenFaq4A') },
    { q: t('about.gardenFaq5Q'), a: t('about.gardenFaq5A') },
    { q: t('about.gardenFaq6Q'), a: t('about.gardenFaq6A') },
  ];

  const faqs = [
    { q: t('about.mktFaq1Q'), a: t('about.mktFaq1A') },
    { q: t('about.mktFaq2Q'), a: t('about.mktFaq2A') },
    { q: t('about.mktFaq3Q'), a: t('about.mktFaq3A') },
    { q: t('about.mktFaq4Q'), a: t('about.mktFaq4A') },
    { q: t('about.mktFaq5Q'), a: t('about.mktFaq5A') },
    { q: t('about.mktFaq6Q'), a: t('about.mktFaq6A') },
    { q: t('about.mktFaq7Q'), a: t('about.mktFaq7A') },
    { q: t('about.mktFaq8Q'), a: t('about.mktFaq8A') },
  ];

  return (
    <div>
      <Seo
        title={t('about.about')}
        path="/about"
        description={t('about.seoDescription')}
      />
      {/* Hero Section — matches the home page: lime glow + hero typography */}
      <div className="text-center py-5 yh-hero-glow" style={{ marginBottom: '2rem' }}>
        <div className="yh-reveal" style={{ marginBottom: '0.8rem' }}>
          <img src="/sunflower.svg" alt="" style={{ width: '3.4rem', height: '3.4rem', borderRadius: '0.7rem' }} />
        </div>
        <h1 className="yh-hero-title yh-reveal" style={{ '--rd': '0.06s' }}>{t('about.yardharvest')}</h1>
        {marketplaceEnabled ? (
          <>
            <p className="yh-hero-sub yh-reveal" style={{ '--rd': '0.12s', color: 'var(--yh-ink)', fontSize: '1.2rem', maxWidth: 620, marginBottom: '0.5rem' }}>{t('about.connectingNeighborsThroughTheFreshest')}</p>
            <p className="yh-hero-sub yh-reveal" style={{ '--rd': '0.18s' }}>{t('about.fromYourNeighborsGardenTo')}</p>
          </>
        ) : (
          <>
            <p className="yh-hero-sub yh-reveal" style={{ '--rd': '0.12s', color: 'var(--yh-ink)', fontSize: '1.2rem', maxWidth: 620, marginBottom: '0.5rem' }}>{t('about.lessAdminMoreGarden')}</p>
            <p className="yh-hero-sub yh-reveal" style={{ '--rd': '0.18s' }}>{t('about.theManagementPlatformForCommunity')}</p>
          </>
        )}
        <div className="yh-reveal mt-2" style={{ '--rd': '0.22s' }}>
          <Link to="/about/guide" className="btn btn-outline-success">
            <i className="bi bi-book me-2"></i>{t('about.readTheCommunityGardenGuide')}</Link>
          <div className="text-muted mt-1" style={{ fontSize: '.85rem' }}>{t('about.ourFreePracticalGuideTo')}</div>
        </div>
        {!user && (
          <div className="d-flex justify-content-center gap-3 flex-wrap yh-reveal" style={{ '--rd': '0.24s' }}>
            <Link to="/register" className="yh-btn-dark">
              <i className="bi bi-person-plus"></i>{t('about.joinYardharvest')}</Link>
            {marketplaceEnabled ? (
              <Link to="/search" className="yh-btn-ghost">
                <i className="bi bi-search"></i>{t('about.browseProduce')}</Link>
            ) : (
              <Link to="/gardens" className="yh-btn-ghost">
                <i className="bi bi-tree"></i>{t('about.exploreGardens')}</Link>
            )}
          </div>
        )}
      </div>

      {/* Our Story Section */}
      <div className="row justify-content-center mb-5">
        <div className="col-lg-8 text-center yh-reveal">
          <h2 className="fw-bold mb-4">
            <i className="bi bi-book text-success me-2"></i>{t('about.ourStory')}</h2>
          <div className="text-start" style={{ fontSize: '1.1rem', lineHeight: '1.8' }}>
            <p>{t('about.yardharvestStartedWithASimple')}</p>
            <p>{t('about.atTheSameTimeJust')}</p>
            {/* One key: the three fragments rendered with no spaces between them. */}
            <p><Trans i18nKey="about.weThoughtFull" components={{ em: <em /> }} /></p>
            {marketplaceEnabled ? (
              <p className="mb-0">{t('about.thatIsHowYardharvestWas')}</p>
            ) : (
              <>
                <p>{t('about.thatObservationGrewIntoYardharvest')}</p>
                <p className="mb-0">{t('about.soThatIsWhatYardharvest')}</p>
              </>
            )}
          </div>
        </div>
      </div>

      <hr className="my-5" />

      {/* How It Works Section */}
      <div className="mb-5">
        <h2 className="fw-bold text-center mb-2 yh-reveal">
          <i className="bi bi-signpost-split text-success me-2"></i>{t('about.howItWorks')}</h2>
        <p className="text-center text-muted mb-5">{t('about.simpleForEveryoneWhetherYou')}</p>

        {marketplaceEnabled ? (
          <>
            {/* Buyers */}
            <h4 className="text-center mb-4">
              <span className="badge bg-success px-3 py-2 fs-6">
                <i className="bi bi-cart3 me-2"></i>{t('about.forBuyers')}</span>
            </h4>
            <div className="row g-4 mb-5 justify-content-center">
              {buyerSteps.map((step, i) => (
                <div className="col-md-4 yh-reveal" key={i} style={{ '--rd': `${i * 0.1}s` }}>
                  <div className="card h-100 border-0 shadow-sm text-center" style={{ borderTop: '3px solid var(--yh-lime)' }}>
                    <div className="card-body p-4">
                      <div
                        className="rounded-circle d-inline-flex align-items-center justify-content-center mb-3"
                        style={{ width: '70px', height: '70px', background: 'var(--yh-lime-soft)', color: 'var(--yh-ink)', fontSize: '1.8rem' }}
                      >
                        <i className={`bi ${step.icon}`}></i>
                      </div>
                      <div className="text-muted small mb-2">{t('about.stepNumber', { n: i + 1 })}</div>
                      <h5 className="fw-bold">{step.title}</h5>
                      <p className="text-muted mb-0">{step.desc}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Sellers */}
            <h4 className="text-center mb-4">
              <span className="badge bg-warning text-dark px-3 py-2 fs-6">
                <i className="bi bi-flower1 me-2"></i>{t('about.forSellers')}</span>
            </h4>
            <div className="row g-4 justify-content-center">
              {sellerSteps.map((step, i) => (
                <div className="col-md-4 yh-reveal" key={i} style={{ '--rd': `${i * 0.1}s` }}>
                  <div className="card h-100 border-0 shadow-sm text-center" style={{ borderTop: '3px solid var(--yh-lime)' }}>
                    <div className="card-body p-4">
                      <div
                        className="rounded-circle d-inline-flex align-items-center justify-content-center mb-3"
                        style={{ width: '70px', height: '70px', background: 'var(--yh-surface)', color: 'var(--yh-ink)', fontSize: '1.8rem' }}
                      >
                        <i className={`bi ${step.icon}`}></i>
                      </div>
                      <div className="text-muted small mb-2">{t('about.stepNumber', { n: i + 1 })}</div>
                      <h5 className="fw-bold">{step.title}</h5>
                      <p className="text-muted mb-0">{step.desc}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </>
        ) : (
          <>
            {/* For Gardeners */}
            <h4 className="text-center mb-4">
              <span className="badge bg-success px-3 py-2 fs-6">
                <i className="bi bi-tree me-2"></i>{t('about.forGardeners')}</span>
            </h4>
            <div className="row g-4 justify-content-center">
              {[
                { icon: 'bi-search', title: t('about.gardenerStep1Title'), desc: t('about.gardenerStep1Desc') },
                { icon: 'bi-flag', title: t('about.gardenerStep2Title'), desc: t('about.gardenerStep2Desc') },
                { icon: 'bi-flower2', title: t('about.gardenerStep3Title'), desc: t('about.gardenerStep3Desc') },
              ].map((step, i) => (
                <div className="col-md-4 yh-reveal" key={i} style={{ '--rd': `${i * 0.1}s` }}>
                  <div className="card h-100 border-0 shadow-sm text-center" style={{ borderTop: '3px solid var(--yh-lime)' }}>
                    <div className="card-body p-4">
                      <div
                        className="rounded-circle d-inline-flex align-items-center justify-content-center mb-3"
                        style={{ width: '70px', height: '70px', background: 'var(--yh-lime-soft)', color: 'var(--yh-ink)', fontSize: '1.8rem' }}
                      >
                        <i className={`bi ${step.icon}`}></i>
                      </div>
                      <div className="text-muted small mb-2">{t('about.stepNumber', { n: i + 1 })}</div>
                      <h5 className="fw-bold">{step.title}</h5>
                      <p className="text-muted mb-0">{step.desc}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}

        <div className="text-center mt-5">
          <a
            href="/static/garden-admin-guide.html"
            target="_blank"
            rel="noopener noreferrer"
            className="yh-btn-dark"
          >
            <i className="bi bi-journal-richtext"></i>{t('about.learnMoreAboutTheGarden')}</a>
        </div>
      </div>

      <hr className="my-5" />

      {/* Why YardHarvest */}
      <div className="mb-5">
        <h2 className="fw-bold text-center mb-2 yh-reveal">
          <i className="bi bi-stars text-success me-2"></i>{t('about.whyYardharvest')}</h2>
        <p className="text-center text-muted mb-5">
          {marketplaceEnabled
            ? t('about.whySubMarketplace')
            : t('about.whySubGardens')}
        </p>
        <div className="row g-4">
          {features.map((feature, i) => (
            <div className="col-md-6 col-lg-4 yh-reveal" key={i} style={{ '--rd': `${(i % 3) * 0.1}s` }}>
              <div className="card h-100 border-0 shadow-sm" style={{ transition: 'transform 0.2s' }}
                onMouseEnter={e => e.currentTarget.style.transform = 'translateY(-4px)'}
                onMouseLeave={e => e.currentTarget.style.transform = 'translateY(0)'}>
                <div className="card-body p-4">
                  <div className="d-flex align-items-center mb-3">
                    <div
                      className="rounded-3 d-inline-flex align-items-center justify-content-center me-3"
                      style={{ width: '48px', height: '48px', background: 'var(--brand-pale)', color: 'var(--brand-secondary)', fontSize: '1.4rem', flexShrink: 0 }}
                    >
                      <i className={`bi ${feature.icon}`}></i>
                    </div>
                    <h5 className="fw-bold mb-0">{feature.title}</h5>
                  </div>
                  <p className="text-muted mb-0">{feature.desc}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <hr className="my-5" />

      {/* Seasonal Guide */}
      <div className="mb-5">
        <h2 className="fw-bold text-center mb-2 yh-reveal">
          <i className="bi bi-calendar3 text-success me-2"></i>{t('about.whatsGrowingNow')}</h2>
        <p className="text-center text-muted mb-4">{t('about.aSeasonalGuideForNebraska')}</p>
        <div className="row justify-content-center">
          <div className="col-lg-8 yh-reveal">
            <div className="card border-0 shadow-sm" style={{ borderLeft: '5px solid var(--brand-accent)' }}>
              <div className="card-body p-4">
                <div className="d-flex align-items-center mb-3">
                  <span className="badge bg-success me-3 px-3 py-2 fs-6">{season.months}</span>
                  <h4 className="fw-bold mb-0">{season.title}</h4>
                </div>
                <div className="row">
                  <div className="col-md-7">
                    <h6 className="fw-semibold mb-2">{marketplaceEnabled ? t('about.lookForThese') : t('about.inSeasonNebraska')}</h6>
                    <ul className="list-unstyled">
                      {season.items.map((item, i) => (
                        <li key={i} className="mb-1">
                          <i className="bi bi-check-circle-fill text-success me-2"></i>{item}
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div className="col-md-5">
                    <div className="p-3 rounded-3" style={{ background: 'var(--brand-pale)' }}>
                      <h6 className="fw-semibold">
                        <i className="bi bi-lightbulb text-warning me-2"></i>{t('about.seasonalTip')}</h6>
                      <p className="text-muted small mb-0">{season.tip}</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <hr className="my-5" />

      {/* Call to Action */}
      <div className="mb-5">
        <div
          className="text-center p-5 rounded-4 yh-reveal"
          style={{
            background: '#f3f7e6',
            border: '1px solid #e9efd8',
          }}
        >
          <h2 className="fw-bold mb-3" style={{ color: 'var(--brand-primary)' }}>{t('about.readyToJoinTheMovement')}</h2>
          <p className="fs-5 mb-4" style={{ color: 'var(--brand-secondary)', maxWidth: '600px', margin: '0 auto' }}>
            {marketplaceEnabled
              ? t('about.ctaMarketplace')
              : t('about.ctaGardens')}
          </p>
          <div className="d-flex justify-content-center gap-3 flex-wrap">
            {marketplaceEnabled ? (
              user ? (
                <>
                  <Link to="/listings/create" className="btn btn-success btn-lg px-4">
                    <i className="bi bi-plus-circle me-2"></i>{t('about.listYourProduce')}</Link>
                  <Link to="/search" className="btn btn-outline-success btn-lg px-4">
                    <i className="bi bi-search me-2"></i>{t('about.findFreshFood')}</Link>
                </>
              ) : (
                <>
                  <Link to="/register" className="btn btn-success btn-lg px-4">
                    <i className="bi bi-flower1 me-2"></i>{t('about.signUpAsAGrower')}</Link>
                  <Link to="/register" className="btn btn-outline-success btn-lg px-4">
                    <i className="bi bi-cart3 me-2"></i>{t('about.signUpAsABuyer')}</Link>
                </>
              )
            ) : (
              <>
                <Link to="/gardens" className="btn btn-success btn-lg px-4">
                  <i className="bi bi-tree me-2"></i>{t('about.exploreGardens')}</Link>
                <Link to="/gardens" className="btn btn-outline-success btn-lg px-4">
                  <i className="bi bi-people me-2"></i>{t('about.joinAGarden')}</Link>
              </>
            )}
          </div>
        </div>
      </div>

      <hr className="my-5" />

      {/* FAQ Section */}
      <div className="mb-5">
        <h2 className="fw-bold text-center mb-2 yh-reveal">
          <i className="bi bi-question-circle text-success me-2"></i>{t('about.frequentlyAskedQuestions')}</h2>
        <p className="text-center text-muted mb-5">{t('about.everythingYouNeedToKnow')}</p>
        <div className="row justify-content-center">
          <div className="col-lg-8">
            <div className="accordion" id="faqAccordion">
              {(marketplaceEnabled ? faqs : gardenFaqs).map((faq, i) => (
                <div className="accordion-item border-0 mb-2 shadow-sm rounded-3 overflow-hidden yh-reveal" key={i} style={{ '--rd': `${Math.min(i, 6) * 0.05}s` }}>
                  <h2 className="accordion-header">
                    <button
                      className={`accordion-button fw-semibold ${openFaq === i ? '' : 'collapsed'}`}
                      type="button"
                      onClick={() => toggleFaq(i)}
                      style={{
                        background: openFaq === i ? 'var(--brand-pale)' : 'white',
                        color: '#333',
                        boxShadow: 'none',
                      }}
                    >
                      <i className={`bi bi-${openFaq === i ? 'dash' : 'plus'}-circle text-success me-2`}></i>
                      {faq.q}
                    </button>
                  </h2>
                  <div className={`accordion-collapse collapse ${openFaq === i ? 'show' : ''}`}>
                    <div className="accordion-body text-muted" style={{ lineHeight: '1.7' }}>
                      {faq.a}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Footer tagline */}
      <div className="text-center py-4 mb-3">
        <img src="/sunflower.svg" alt="" style={{ width: '2rem', height: '2rem', borderRadius: '0.4rem' }} />
        <p className="text-muted mt-2 mb-0">
          {marketplaceEnabled
            ? t('about.taglineMarketplace')
            : t('about.taglineGardens')}
        </p>
      </div>
    </div>
  );
}
