import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { publicAPI } from '../api';
import { useSiteConfig } from '../SiteConfigContext';
import { useAuth } from '../AuthContext';
import Seo from '../components/Seo';
import useScrollReveal from '../hooks/useScrollReveal';

const CHECK = <i className="bi bi-check-circle-fill text-success"></i>;
const CROSS = <i className="bi bi-x-circle text-muted"></i>;

export default function Pricing() {
  const { t } = useTranslation();
  const { marketplaceEnabled } = useSiteConfig();
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [faqOpen, setFaqOpen] = useState(null);

  useEffect(() => {
    publicAPI.pricing().then(r => setData(r.data)).catch(() => {});
  }, []);

  // Re-scan once the async pricing data renders the cards/sections.
  useScrollReveal([data, marketplaceEnabled]);

  if (!data) return <div className="text-center py-5"><div className="spinner-border text-success"></div></div>;

  const gp = data.garden_pro;
  const mkt = data.marketplace;
  const savings = (gp.monthly * 12 - gp.yearly).toFixed(0);
  // Derived, not hardcoded: this read "over 3 months free" while the amount
  // beside it was computed, so at $12/mo it advertised 3 months when the
  // saving is actually seven.
  const monthsFree = gp.monthly > 0 ? Math.floor((gp.monthly * 12 - gp.yearly) / gp.monthly) : 0;
  const ctaLink = user ? '/gardens/create' : '/register';

  const faqs = [
    { q: t('pricing.faqContractQ'), a: t('pricing.faqContractA') },
    { q: t('pricing.faqTrialEndsQ'), a: t('pricing.faqTrialEndsA') },
    { q: t('pricing.faqDuesQ'), a: t('pricing.faqDuesA') },
    { q: t('pricing.faqMultiQ'), a: t('pricing.faqMultiA') },
    ...(marketplaceEnabled ? [
      { q: t('pricing.faqMktNeedProQ'), a: t('pricing.faqMktNeedProA') },
      { q: t('pricing.faqSmartPricingQ'), a: t('pricing.faqSmartPricingA') },
    ] : []),
  ];

  return (
    <div>
      <Seo
        title={t('pricing.pricing')}
        path="/pricing"
        description="Simple, transparent pricing for community gardens. Start free, upgrade to Garden Pro for messaging, finance, photos and more."
      />
      {/* ── Hero — matches the home page: lime glow + hero typography ── */}
      <div className="text-center py-5 yh-hero-glow">
        <h1 className="yh-hero-title yh-reveal">{t('pricing.simpleTransparent')}<span className="yh-highlight">pricing</span></h1>
        <p className="yh-hero-sub yh-reveal" style={{ '--rd': '0.12s', maxWidth: 600 }}>
          {marketplaceEnabled
            ? 'Free for growers and buyers. Subscription plans for community garden organizers.'
            : 'Free for gardeners. Simple plans for organizers. Volume pricing for networks and city programs.'}
        </p>
      </div>

      <div className="container py-5">

        {/* ── Garden Pro Cards ── */}
        {gp.enabled && (
          <>
            <div className="text-center mb-4 yh-reveal">
              <h2 className="fw-bold" style={{ color: 'var(--brand-primary)' }}>{t('pricing.gardenPro')}</h2>
              <p className="text-muted">{t('pricing.everythingYouNeedToRun')}</p>
              <a
                href="/static/garden-admin-guide.html"
                target="_blank"
                rel="noopener noreferrer"
                className="yh-btn-dark mt-2"
              >
                <i className="bi bi-journal-richtext"></i>Learn more about the Garden Pro Platform
              </a>
            </div>

            <div className="row g-4 mb-5 justify-content-center">
              {/* Free Trial */}
              <div className="col-md-4 yh-reveal">
                <div className="card h-100 shadow-sm" style={{ borderRadius: 12, borderTop: '4px solid var(--brand-light-green)' }}>
                  <div className="card-body p-4 text-center">
                    <span className="badge bg-success mb-2">{t('pricing.tryItFree')}</span>
                    <h4 className="fw-bold">{t('pricing.freeTrial')}</h4>
                    <div className="display-4 fw-bold my-3" style={{ color: 'var(--brand-secondary)' }}>$0</div>
                    <p className="text-muted">{t('pricing.trialDaysAllFeatures', { count: gp.trial_days })}</p>
                    <ul className="list-unstyled text-start mb-4">
                      <li className="mb-2"><i className="bi bi-check text-success me-2"></i>{t('pricing.allProFeaturesIncluded')}</li>
                      <li className="mb-2"><i className="bi bi-check text-success me-2"></i>{t('pricing.noPaymentRequired')}</li>
                      <li className="mb-2"><i className="bi bi-check text-success me-2"></i>{t('pricing.setUpAtYourOwn')}</li>
                    </ul>
                    <Link to={ctaLink} className="btn btn-outline-success w-100 py-2">{t('pricing.startFreeTrial')}</Link>
                  </div>
                </div>
              </div>

              {/* Monthly */}
              <div className="col-md-4 yh-reveal">
                <div className="card h-100 shadow-sm" style={{ borderRadius: 12, borderTop: '4px solid var(--brand-accent)' }}>
                  <div className="card-body p-4 text-center">
                    <h4 className="fw-bold mt-3">{t('pricing.monthly')}</h4>
                    <div className="display-4 fw-bold my-3" style={{ color: 'var(--brand-secondary)' }}>${gp.monthly}<span className="fs-5 fw-normal text-muted">/mo</span></div>
                    <p className="text-muted">{t('pricing.flexibleCancelAnytime')}</p>
                    <ul className="list-unstyled text-start mb-4">
                      <li className="mb-2"><i className="bi bi-check text-success me-2"></i>{t('pricing.everythingInTrial')}</li>
                      <li className="mb-2"><i className="bi bi-check text-success me-2"></i>{t('pricing.monthlyBilling')}</li>
                      <li className="mb-2"><i className="bi bi-check text-success me-2"></i>{t('pricing.noCommitment')}</li>
                    </ul>
                    <Link to={ctaLink} className="btn btn-outline-success w-100 py-2">{t('pricing.getStarted')}</Link>
                  </div>
                </div>
              </div>

              {/* Annual */}
              <div className="col-md-4 yh-reveal">
                <div className="card h-100 shadow" style={{ borderRadius: 12, border: '2px solid var(--brand-secondary)' }}>
                  <div className="card-body p-4 text-center">
                    <span className="badge mb-2" style={{ backgroundColor: 'var(--brand-secondary)' }}>{t('pricing.bestValue')}</span>
                    <h4 className="fw-bold">{t('pricing.annual')}</h4>
                    <div className="display-4 fw-bold my-3" style={{ color: 'var(--brand-secondary)' }}>${gp.yearly}<span className="fs-5 fw-normal text-muted">/yr</span></div>
                    <p className="fw-bold" style={{ color: 'var(--brand-secondary)' }}>{t('pricing.saveMonthsFree', { amount: savings, count: monthsFree })}</p>
                    <ul className="list-unstyled text-start mb-4">
                      <li className="mb-2"><i className="bi bi-check text-success me-2"></i>{t('pricing.everythingInMonthly')}</li>
                      <li className="mb-2"><i className="bi bi-check text-success me-2"></i>{t('pricing.billedAnnually')}</li>
                      <li className="mb-2"><i className="bi bi-star-fill text-warning me-2"></i>{t('pricing.bestPricePerMonth')}</li>
                    </ul>
                    <Link to={ctaLink} className="btn btn-success w-100 py-2 fw-bold">{t('pricing.getStarted')}</Link>
                  </div>
                </div>
              </div>
            </div>

            {/* ── Feature Comparison ── */}
            <div className="card shadow-sm mb-5 yh-reveal" style={{ borderRadius: 12 }}>
              <div className="card-body p-4">
                <h4 className="fw-bold mb-4 text-center" style={{ color: 'var(--brand-primary)' }}>{t('pricing.featureComparison')}</h4>
                <div className="table-responsive">
                  <table className="table align-middle mb-0">
                    <thead style={{ backgroundColor: 'var(--brand-cream)' }}>
                      <tr><th>{t('pricing.feature')}</th><th className="text-center" style={{ width: 100 }}>{t('pricing.free')}</th><th className="text-center" style={{ width: 100 }}>{t('pricing.pro')}</th></tr>
                    </thead>
                    <tbody>
                      {[
                        [t('pricing.featProfile'), true, true],
                        [t('pricing.featPlots'), true, true],
                        [t('pricing.featWaitlist'), true, true],
                        [t('pricing.featEvents'), true, true],
                        [t('pricing.featAnnouncements'), true, true],
                        [t('pricing.featWall'), true, true],
                        [t('pricing.featHarvest'), true, true],
                        [t('pricing.featResources'), true, true],
                        [t('pricing.featPayouts'), true, true],
                        [t('pricing.featFinance'), false, true],
                        [t('pricing.featShifts'), false, true],
                        [t('pricing.featCheckout'), false, true],
                        [t('pricing.featPhotos'), false, true],
                        [t('pricing.featMessaging'), false, true],
                        [t('pricing.featBranding'), false, true],
                        [t('pricing.featGrid'), false, true],
                        [t('pricing.featExport'), false, true],
                      ].map(([feature, free, pro], i) => (
                        <tr key={i}>
                          <td>{feature}</td>
                          <td className="text-center">{free ? CHECK : CROSS}</td>
                          <td className="text-center">{pro ? CHECK : CROSS}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </>
        )}

        {/* ── Networks & City Programs ── */}
        <div className="card mb-5 yh-reveal" style={{ borderRadius: 12, background: '#f3f7e6', border: '1px solid #e9efd8', color: 'var(--yh-ink)' }}>
          <div className="card-body p-5 text-center">
            <i className="bi bi-building fs-1 mb-3 d-block" style={{ opacity: 0.8 }}></i>
            <h3 className="fw-bold mb-3">{t('pricing.gardenNetworksCityPrograms')}</h3>
            <p className="mb-2" style={{ opacity: 0.9, maxWidth: 640, margin: '0 auto' }}>
              {t('pricing.networkBody')}
            </p>
            <p className="mb-4" style={{ opacity: 0.75, maxWidth: 640, margin: '0 auto' }}>
              {t('pricing.networkBody2')}
            </p>
            <a href="mailto:james@yardharvest.app?subject=Network Pricing Inquiry" className="btn btn-success btn-lg px-5 fw-bold">
              <i className="bi bi-envelope me-2"></i>Talk to Us About Network Pricing
            </a>
          </div>
        </div>

        {/* ── Marketplace Economics (conditional) ── */}
        {marketplaceEnabled && (
          <div className="mb-5">
            <div className="text-center mb-4 yh-reveal">
              <h2 className="fw-bold" style={{ color: 'var(--brand-primary)' }}>
                <i className="bi bi-shop me-2"></i>Marketplace Pricing
              </h2>
              <p className="text-muted">{t('pricing.forGrowersAndBuyersCompletely')}</p>
            </div>

            <div className="row g-4">
              {/* Smart Pricing */}
              {mkt.smart_pricing_enabled && (
                <div className="col-md-4">
                  <div className="card h-100 shadow-sm" style={{ borderRadius: 12, borderTop: '4px solid var(--brand-accent)' }}>
                    <div className="card-body p-4">
                      <div className="rounded-circle d-inline-flex align-items-center justify-content-center mb-3"
                        style={{ width: 48, height: 48, backgroundColor: 'var(--brand-pale)' }}>
                        <i className="bi bi-graph-up fs-4" style={{ color: 'var(--brand-secondary)' }}></i>
                      </div>
                      <h5 className="fw-bold">{t('pricing.smartPricing')}</h5>
                      <p className="text-muted">{t('pricing.ourAlgorithmAdjustsPricesBased')}</p>
                      <div className="alert alert-light py-2 mb-0 small">
                        <strong>{t('pricing.priceRange')}</strong> {Math.round(mkt.price_floor_pct * 100)}% – {Math.round(mkt.price_ceiling_pct * 100)}% of your base price
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Commission */}
              {mkt.commission_enabled && (
                <div className="col-md-4">
                  <div className="card h-100 shadow-sm" style={{ borderRadius: 12, borderTop: '4px solid var(--brand-accent)' }}>
                    <div className="card-body p-4">
                      <div className="rounded-circle d-inline-flex align-items-center justify-content-center mb-3"
                        style={{ width: 48, height: 48, backgroundColor: 'var(--brand-pale)' }}>
                        <i className="bi bi-bank fs-4" style={{ color: 'var(--brand-secondary)' }}></i>
                      </div>
                      <h5 className="fw-bold">{t('pricing.platformCommission')}</h5>
                      <p className="text-muted">{t('pricing.aSmallPlatformFeeSupports')}</p>
                      <div className="alert alert-light py-2 mb-0">
                        <div className="d-flex justify-content-between">
                          <span><strong>{Math.round(mkt.commission_rate * 100)}%</strong> per transaction</span>
                        </div>
                        <div className="text-muted small mt-1">{t('pricing.freeToListYouOnly')}</div>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Delivery */}
              {mkt.delivery_fees_enabled && (
                <div className="col-md-4">
                  <div className="card h-100 shadow-sm" style={{ borderRadius: 12, borderTop: '4px solid var(--brand-accent)' }}>
                    <div className="card-body p-4">
                      <div className="rounded-circle d-inline-flex align-items-center justify-content-center mb-3"
                        style={{ width: 48, height: 48, backgroundColor: 'var(--brand-pale)' }}>
                        <i className="bi bi-truck fs-4" style={{ color: 'var(--brand-secondary)' }}></i>
                      </div>
                      <h5 className="fw-bold">{t('pricing.delivery')}</h5>
                      <p className="text-muted">{t('pricing.buyersCanChoosePickupFree')}</p>
                      <div className="alert alert-light py-2 mb-0 small">
                        <div><strong>${mkt.delivery_fee_flat.toFixed(2)}</strong> flat delivery fee</div>
                        {mkt.free_delivery_enabled && mkt.free_delivery_threshold > 0 && (
                          <div className="text-success mt-1">{t('pricing.freeDeliveryOver', { amount: mkt.free_delivery_threshold.toFixed(2) })}</div>
                        )}
                        {mkt.doordash_enabled && (
                          <div className="mt-1"><i className="bi bi-lightning-fill text-danger"></i> DoorDash Drive available</div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── FAQ ── */}
        <div className="mb-5">
          <h3 className="fw-bold text-center mb-4" style={{ color: 'var(--brand-primary)' }}>{t('pricing.frequentlyAskedQuestions')}</h3>
          <div className="mx-auto" style={{ maxWidth: 700 }}>
            {faqs.map((faq, i) => (
              <div key={i} className="card mb-2 shadow-sm yh-reveal" style={{ borderRadius: 8, cursor: 'pointer', '--rd': `${Math.min(i, 6) * 0.05}s` }} onClick={() => setFaqOpen(faqOpen === i ? null : i)}>
                <div className="card-body py-3 px-4">
                  <div className="d-flex justify-content-between align-items-center">
                    <h6 className="mb-0 fw-bold">{faq.q}</h6>
                    <i className={`bi bi-chevron-${faqOpen === i ? 'up' : 'down'} text-muted`}></i>
                  </div>
                  {faqOpen === i && <p className="text-muted mt-2 mb-0">{faq.a}</p>}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* ── Final CTA ── */}
        <div className="text-center py-4 yh-reveal">
          <h3 className="fw-bold mb-3" style={{ color: 'var(--brand-primary)' }}>{t('pricing.readyToGrowYourCommunity')}</h3>
          <Link to={ctaLink} className="btn btn-success btn-lg px-5 fw-bold">
            <i className="bi bi-rocket-takeoff me-2"></i>Get Started Free
          </Link>
        </div>
      </div>
    </div>
  );
}
