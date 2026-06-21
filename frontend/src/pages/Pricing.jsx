import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { publicAPI } from '../api';
import { useSiteConfig } from '../SiteConfigContext';
import { useAuth } from '../AuthContext';
import Seo from '../components/Seo';
import useScrollReveal from '../hooks/useScrollReveal';

const CHECK = <i className="bi bi-check-circle-fill text-success"></i>;
const CROSS = <i className="bi bi-x-circle text-muted"></i>;

export default function Pricing() {
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
  const ctaLink = user ? '/gardens/create' : '/register';

  const faqs = [
    { q: 'Is there a contract?', a: 'No. Garden Pro is month-to-month or annual with no long-term commitment. Cancel anytime from your garden settings.' },
    { q: 'What happens when my trial ends?', a: 'Pro features lock, but your garden profile, plots, members, and all your data remain intact. You can subscribe anytime to unlock everything again.' },
    { q: 'How do online dues payments work?', a: 'Connect your garden’s Stripe account from the billing page (the setup happens right in the app) and members can pay dues online. Payments go directly to your garden, and collection status is tracked automatically.' },
    { q: 'We run multiple gardens — how does pricing work?', a: 'Networks and city programs get volume pricing per garden with centralized billing and network-wide impact reporting. Contact us below and we’ll put together a plan for your organization.' },
    ...(marketplaceEnabled ? [
      { q: 'Do I need Garden Pro to use the marketplace?', a: 'No. The marketplace is completely free for growers and buyers. Garden Pro is only for community garden organizers who need advanced management tools.' },
      { q: 'How does smart pricing work?', a: 'Our algorithm considers local supply levels, sales velocity, and listing freshness to suggest fair market prices. Your price stays within a floor and ceiling you control — it never changes without your input.' },
    ] : []),
  ];

  return (
    <div>
      <Seo
        title="Pricing"
        path="/pricing"
        description="Simple, transparent pricing for community gardens. Start free, upgrade to Garden Pro for messaging, finance, photos and more."
      />
      {/* ── Hero — matches the home page: lime glow + hero typography ── */}
      <div className="text-center py-5 yh-hero-glow">
        <h1 className="yh-hero-title yh-reveal">Simple, transparent <span className="yh-highlight">pricing</span></h1>
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
              <h2 className="fw-bold" style={{ color: 'var(--brand-primary)' }}>Garden Pro</h2>
              <p className="text-muted">Everything you need to run a community garden</p>
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
                    <span className="badge bg-success mb-2">Try it free</span>
                    <h4 className="fw-bold">Free Trial</h4>
                    <div className="display-4 fw-bold my-3" style={{ color: 'var(--brand-secondary)' }}>$0</div>
                    <p className="text-muted">{gp.trial_days} days, all features</p>
                    <ul className="list-unstyled text-start mb-4">
                      <li className="mb-2"><i className="bi bi-check text-success me-2"></i>All Pro features included</li>
                      <li className="mb-2"><i className="bi bi-check text-success me-2"></i>No payment required</li>
                      <li className="mb-2"><i className="bi bi-check text-success me-2"></i>Set up at your own pace</li>
                    </ul>
                    <Link to={ctaLink} className="btn btn-outline-success w-100 py-2">Start Free Trial</Link>
                  </div>
                </div>
              </div>

              {/* Monthly */}
              <div className="col-md-4 yh-reveal">
                <div className="card h-100 shadow-sm" style={{ borderRadius: 12, borderTop: '4px solid var(--brand-accent)' }}>
                  <div className="card-body p-4 text-center">
                    <h4 className="fw-bold mt-3">Monthly</h4>
                    <div className="display-4 fw-bold my-3" style={{ color: 'var(--brand-secondary)' }}>${gp.monthly}<span className="fs-5 fw-normal text-muted">/mo</span></div>
                    <p className="text-muted">Flexible, cancel anytime</p>
                    <ul className="list-unstyled text-start mb-4">
                      <li className="mb-2"><i className="bi bi-check text-success me-2"></i>Everything in trial</li>
                      <li className="mb-2"><i className="bi bi-check text-success me-2"></i>Monthly billing</li>
                      <li className="mb-2"><i className="bi bi-check text-success me-2"></i>No commitment</li>
                    </ul>
                    <Link to={ctaLink} className="btn btn-outline-success w-100 py-2">Get Started</Link>
                  </div>
                </div>
              </div>

              {/* Annual */}
              <div className="col-md-4 yh-reveal">
                <div className="card h-100 shadow" style={{ borderRadius: 12, border: '2px solid var(--brand-secondary)' }}>
                  <div className="card-body p-4 text-center">
                    <span className="badge mb-2" style={{ backgroundColor: 'var(--brand-secondary)' }}>Best Value</span>
                    <h4 className="fw-bold">Annual</h4>
                    <div className="display-4 fw-bold my-3" style={{ color: 'var(--brand-secondary)' }}>${gp.yearly}<span className="fs-5 fw-normal text-muted">/yr</span></div>
                    <p className="fw-bold" style={{ color: 'var(--brand-secondary)' }}>Save ${savings} — over 3 months free</p>
                    <ul className="list-unstyled text-start mb-4">
                      <li className="mb-2"><i className="bi bi-check text-success me-2"></i>Everything in monthly</li>
                      <li className="mb-2"><i className="bi bi-check text-success me-2"></i>Billed annually</li>
                      <li className="mb-2"><i className="bi bi-star-fill text-warning me-2"></i>Best price per month</li>
                    </ul>
                    <Link to={ctaLink} className="btn btn-success w-100 py-2 fw-bold">Get Started</Link>
                  </div>
                </div>
              </div>
            </div>

            {/* ── Feature Comparison ── */}
            <div className="card shadow-sm mb-5 yh-reveal" style={{ borderRadius: 12 }}>
              <div className="card-body p-4">
                <h4 className="fw-bold mb-4 text-center" style={{ color: 'var(--brand-primary)' }}>Feature Comparison</h4>
                <div className="table-responsive">
                  <table className="table align-middle mb-0">
                    <thead style={{ backgroundColor: 'var(--brand-cream)' }}>
                      <tr><th>Feature</th><th className="text-center" style={{ width: 100 }}>Free</th><th className="text-center" style={{ width: 100 }}>Pro</th></tr>
                    </thead>
                    <tbody>
                      {[
                        ['Garden profile & member directory', true, true],
                        ['Plot creation, assignment & statuses', true, true],
                        ['Waitlist & reservations', true, true],
                        ['Events with RSVPs', true, true],
                        ['Announcements (in-app, email, SMS)', true, true],
                        ['Community wall with AI moderation', true, true],
                        ['Harvest logging', true, true],
                        ['Resource inventory', true, true],
                        ['Direct bank payouts via Stripe', true, true],
                        ['Financial management (dues & expenses)', false, true],
                        ['Volunteer shift scheduling & reports', false, true],
                        ['Tool checkout & maintenance (QR)', false, true],
                        ['Photo wall with likes & comments', false, true],
                        ['Broadcast & direct messaging', false, true],
                        ['Custom email branding & preview', false, true],
                        ['Plot grid designer', false, true],
                        ['Data export (CSV)', false, true],
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
            <h3 className="fw-bold mb-3">Garden networks &amp; city programs</h3>
            <p className="mb-2" style={{ opacity: 0.9, maxWidth: 640, margin: '0 auto' }}>
              Running 5, 50, or 200 gardens? Get volume pricing per garden, centralized billing and
              administration, online dues collection across every site, and network-wide impact
              reporting for boards, funders, and councils.
            </p>
            <p className="mb-4" style={{ opacity: 0.75, maxWidth: 640, margin: '0 auto' }}>
              Custom branding and dedicated onboarding included. Built for nonprofits, extension
              programs, and parks departments.
            </p>
            <a href="mailto:support@yardharvest.com?subject=Network Pricing Inquiry" className="btn btn-success btn-lg px-5 fw-bold">
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
              <p className="text-muted">For growers and buyers — completely free to join</p>
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
                      <h5 className="fw-bold">Smart Pricing</h5>
                      <p className="text-muted">Our algorithm adjusts prices based on local supply, demand, and freshness to help your produce sell faster at fair market value.</p>
                      <div className="alert alert-light py-2 mb-0 small">
                        <strong>Price range:</strong> {Math.round(mkt.price_floor_pct * 100)}% – {Math.round(mkt.price_ceiling_pct * 100)}% of your base price
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
                      <h5 className="fw-bold">Platform Commission</h5>
                      <p className="text-muted">A small platform fee supports the marketplace infrastructure and keeps the community running.</p>
                      <div className="alert alert-light py-2 mb-0">
                        <div className="d-flex justify-content-between">
                          <span><strong>{Math.round(mkt.commission_rate * 100)}%</strong> per transaction</span>
                        </div>
                        <div className="text-muted small mt-1">Free to list. You only pay when you sell.</div>
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
                      <h5 className="fw-bold">Delivery</h5>
                      <p className="text-muted">Buyers can choose pickup (free) or delivery for a small fee. Sellers set their own delivery radius.</p>
                      <div className="alert alert-light py-2 mb-0 small">
                        <div><strong>${mkt.delivery_fee_flat.toFixed(2)}</strong> flat delivery fee</div>
                        {mkt.free_delivery_enabled && mkt.free_delivery_threshold > 0 && (
                          <div className="text-success mt-1">Free delivery on orders over ${mkt.free_delivery_threshold.toFixed(2)}</div>
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
          <h3 className="fw-bold text-center mb-4" style={{ color: 'var(--brand-primary)' }}>Frequently Asked Questions</h3>
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
          <h3 className="fw-bold mb-3" style={{ color: 'var(--brand-primary)' }}>Ready to grow your community?</h3>
          <Link to={ctaLink} className="btn btn-success btn-lg px-5 fw-bold">
            <i className="bi bi-rocket-takeoff me-2"></i>Get Started Free
          </Link>
        </div>
      </div>
    </div>
  );
}
