import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { publicAPI } from '../api';
import { useSiteConfig } from '../SiteConfigContext';
import { useAuth } from '../AuthContext';

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

  if (!data) return <div className="text-center py-5"><div className="spinner-border text-success"></div></div>;

  const gp = data.garden_pro;
  const mkt = data.marketplace;
  const savings = (gp.monthly * 12 - gp.yearly).toFixed(0);
  const ctaLink = user ? '/gardens/create' : '/register';

  const faqs = [
    { q: 'Is there a contract?', a: 'No. Garden Pro is month-to-month or annual with no long-term commitment. Cancel anytime from your garden settings.' },
    { q: 'What happens when my trial ends?', a: 'Pro features lock, but your garden profile, plots, members, and all your data remain intact. You can subscribe anytime to unlock everything again.' },
    { q: 'Do I need Garden Pro to use the marketplace?', a: 'No. The marketplace is completely free for growers and buyers. Garden Pro is only for community garden organizers who need advanced management tools.' },
    { q: 'How does smart pricing work?', a: 'Our algorithm considers local supply levels, sales velocity, and listing freshness to suggest fair market prices. Your price stays within a floor and ceiling you control — it never changes without your input.' },
  ];

  return (
    <div>
      {/* ── Hero ── */}
      <div className="text-center text-white py-5" style={{
        background: 'linear-gradient(135deg, #166f4c 0%, #1d8a5f 30%, #2aa873 60%, #7fd4ab 100%)',
      }}>
        <div className="container py-4">
          <h1 className="display-4 fw-bold mb-3">Simple, transparent pricing</h1>
          <p className="lead mb-0" style={{ opacity: 0.9, maxWidth: 600, margin: '0 auto' }}>
            Free for growers and buyers. Subscription plans for community garden organizers.
          </p>
        </div>
      </div>

      <div className="container py-5">

        {/* ── Garden Pro Cards ── */}
        {gp.enabled && (
          <>
            <div className="text-center mb-4">
              <h2 className="fw-bold" style={{ color: '#166f4c' }}>Garden Pro</h2>
              <p className="text-muted">Everything you need to run a community garden</p>
            </div>

            <div className="row g-4 mb-5 justify-content-center">
              {/* Free Trial */}
              <div className="col-md-4">
                <div className="card h-100 shadow-sm" style={{ borderRadius: 12, borderTop: '4px solid #7fd4ab' }}>
                  <div className="card-body p-4 text-center">
                    <span className="badge bg-success mb-2">Try it free</span>
                    <h4 className="fw-bold">Free Trial</h4>
                    <div className="display-4 fw-bold my-3" style={{ color: '#1d8a5f' }}>$0</div>
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
              <div className="col-md-4">
                <div className="card h-100 shadow-sm" style={{ borderRadius: 12, borderTop: '4px solid #2aa873' }}>
                  <div className="card-body p-4 text-center">
                    <h4 className="fw-bold mt-3">Monthly</h4>
                    <div className="display-4 fw-bold my-3" style={{ color: '#1d8a5f' }}>${gp.monthly}<span className="fs-5 fw-normal text-muted">/mo</span></div>
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
              <div className="col-md-4">
                <div className="card h-100 shadow" style={{ borderRadius: 12, border: '2px solid #1d8a5f' }}>
                  <div className="card-body p-4 text-center">
                    <span className="badge mb-2" style={{ backgroundColor: '#1d8a5f' }}>Best Value</span>
                    <h4 className="fw-bold">Annual</h4>
                    <div className="display-4 fw-bold my-3" style={{ color: '#1d8a5f' }}>${gp.yearly}<span className="fs-5 fw-normal text-muted">/yr</span></div>
                    <p className="fw-bold" style={{ color: '#1d8a5f' }}>Save ${savings} — over 3 months free</p>
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
            <div className="card shadow-sm mb-5" style={{ borderRadius: 12 }}>
              <div className="card-body p-4">
                <h4 className="fw-bold mb-4 text-center" style={{ color: '#166f4c' }}>Feature Comparison</h4>
                <div className="table-responsive">
                  <table className="table align-middle mb-0">
                    <thead style={{ backgroundColor: '#f7f8f9' }}>
                      <tr><th>Feature</th><th className="text-center" style={{ width: 100 }}>Free</th><th className="text-center" style={{ width: 100 }}>Pro</th></tr>
                    </thead>
                    <tbody>
                      {[
                        ['Garden profile & member directory', true, true],
                        ['Plot assignments', true, true],
                        ['Announcements', true, true],
                        ['Harvest logging', true, true],
                        ['Basic dashboard', true, true],
                        ['Events', true, true],
                        ['Financial management (dues, expenses)', false, true],
                        ['Volunteer shift scheduling & reports', false, true],
                        ['Photo wall with comments', false, true],
                        ['Broadcast messaging', false, true],
                        ['Custom email branding', false, true],
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

        {/* ── White Label ── */}
        <div className="card mb-5" style={{ borderRadius: 12, background: 'linear-gradient(135deg, #166f4c, #1d8a5f)', color: 'white' }}>
          <div className="card-body p-5 text-center">
            <i className="bi bi-building fs-1 mb-3 d-block" style={{ opacity: 0.8 }}></i>
            <h3 className="fw-bold mb-3">Managing multiple community gardens?</h3>
            <p className="mb-4" style={{ opacity: 0.9, maxWidth: 600, margin: '0 auto' }}>
              Our White Label program gives large organizations custom branding, multi-garden management, and dedicated support.
              Perfect for city parks departments, nonprofits, and garden networks.
            </p>
            <a href="mailto:support@yardharvest.com?subject=White Label Inquiry" className="btn btn-light btn-lg px-5 fw-bold" style={{ color: '#166f4c' }}>
              <i className="bi bi-envelope me-2"></i>Contact Us
            </a>
          </div>
        </div>

        {/* ── Marketplace Economics (conditional) ── */}
        {marketplaceEnabled && (
          <div className="mb-5">
            <div className="text-center mb-4">
              <h2 className="fw-bold" style={{ color: '#166f4c' }}>
                <i className="bi bi-shop me-2"></i>Marketplace Pricing
              </h2>
              <p className="text-muted">For growers and buyers — completely free to join</p>
            </div>

            <div className="row g-4">
              {/* Smart Pricing */}
              {mkt.smart_pricing_enabled && (
                <div className="col-md-4">
                  <div className="card h-100 shadow-sm" style={{ borderRadius: 12, borderTop: '4px solid #2aa873' }}>
                    <div className="card-body p-4">
                      <div className="rounded-circle d-inline-flex align-items-center justify-content-center mb-3"
                        style={{ width: 48, height: 48, backgroundColor: '#ecf7f1' }}>
                        <i className="bi bi-graph-up fs-4" style={{ color: '#1d8a5f' }}></i>
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
                  <div className="card h-100 shadow-sm" style={{ borderRadius: 12, borderTop: '4px solid #2aa873' }}>
                    <div className="card-body p-4">
                      <div className="rounded-circle d-inline-flex align-items-center justify-content-center mb-3"
                        style={{ width: 48, height: 48, backgroundColor: '#ecf7f1' }}>
                        <i className="bi bi-bank fs-4" style={{ color: '#1d8a5f' }}></i>
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
                  <div className="card h-100 shadow-sm" style={{ borderRadius: 12, borderTop: '4px solid #2aa873' }}>
                    <div className="card-body p-4">
                      <div className="rounded-circle d-inline-flex align-items-center justify-content-center mb-3"
                        style={{ width: 48, height: 48, backgroundColor: '#ecf7f1' }}>
                        <i className="bi bi-truck fs-4" style={{ color: '#1d8a5f' }}></i>
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
          <h3 className="fw-bold text-center mb-4" style={{ color: '#166f4c' }}>Frequently Asked Questions</h3>
          <div className="mx-auto" style={{ maxWidth: 700 }}>
            {faqs.map((faq, i) => (
              <div key={i} className="card mb-2 shadow-sm" style={{ borderRadius: 8, cursor: 'pointer' }} onClick={() => setFaqOpen(faqOpen === i ? null : i)}>
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
        <div className="text-center py-4">
          <h3 className="fw-bold mb-3" style={{ color: '#166f4c' }}>Ready to grow your community?</h3>
          <Link to={ctaLink} className="btn btn-success btn-lg px-5 fw-bold">
            <i className="bi bi-rocket-takeoff me-2"></i>Get Started Free
          </Link>
        </div>
      </div>
    </div>
  );
}
