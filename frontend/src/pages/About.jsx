import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../AuthContext';
import { useSiteConfig } from '../SiteConfigContext';
import Seo from '../components/Seo';

export default function About() {
  const { user } = useAuth();
  const { marketplaceEnabled } = useSiteConfig();
  const [openFaq, setOpenFaq] = useState(null);

  const toggleFaq = (index) => {
    setOpenFaq(openFaq === index ? null : index);
  };

  const buyerSteps = [
    { icon: 'bi-search', title: 'Browse & Search', desc: 'Find fresh produce listed by gardeners near you. Filter by type, distance, price, and more.' },
    { icon: 'bi-cart-plus', title: 'Add to Cart & Order', desc: 'Build your order from one or multiple growers. Choose pickup or delivery at checkout.' },
    { icon: 'bi-emoji-smile', title: 'Enjoy & Review', desc: 'Pick up your haul, enjoy the freshest produce around, and leave a review for your neighbor.' },
  ];

  const sellerSteps = [
    { icon: 'bi-camera', title: 'List Your Harvest', desc: 'Snap a photo, set your price and quantity. Our dynamic pricing helps you stay competitive.' },
    { icon: 'bi-bell', title: 'Get Orders', desc: 'Receive notifications when neighbors order. Accept and arrange pickup or delivery.' },
    { icon: 'bi-wallet2', title: 'Earn & Grow', desc: 'Turn your surplus into income. Build a reputation and a loyal customer base in your area.' },
  ];

  const marketplaceFeatures = [
    { icon: 'bi-pin-map-fill', title: 'Hyper-Local', desc: 'Everything is within miles of your home. No long supply chains, no cross-country shipping.' },
    { icon: 'bi-people', title: 'Support Your Neighbors', desc: 'Every purchase goes directly to a gardener in your community. Keep dollars local.' },
    { icon: 'bi-flower2', title: 'Fresher Than Any Store', desc: 'Picked this morning, on your table tonight. You simply cannot get produce this fresh from a grocery store.' },
    { icon: 'bi-graph-up-arrow', title: 'Dynamic Fair Pricing', desc: 'Our smart pricing reflects real-time supply and demand, keeping things fair for everyone.' },
    { icon: 'bi-recycle', title: 'Reduce Food Waste', desc: 'Surplus zucchini? Extra herbs? Instead of composting the excess, share it with someone who wants it.' },
    { icon: 'bi-heart-fill', title: 'Build Community', desc: 'Meet the people behind your food. YardHarvest turns anonymous neighbors into friends.' },
  ];

  const gardenFeatures = [
    { icon: 'bi-clipboard-check', title: 'Less Admin, More Garden', desc: 'Plot assignments, waitlists, member records, and renewals — automated, so organizers spend their time in the garden, not in spreadsheets.' },
    { icon: 'bi-cash-coin', title: 'Dues & Payments', desc: 'Set seasonal dues, send branded reminders, and collect online. Money goes straight to your garden — no more chasing checks.' },
    { icon: 'bi-people', title: 'Volunteer Coordination', desc: 'Schedule workdays and shifts, track signups, attendance, and hours — the records grant applications ask for.' },
    { icon: 'bi-graph-up-arrow', title: 'Show Your Impact', desc: 'Harvest pounds, food-bank donations, participation, and volunteer hours — funder-ready data for boards, grantors, and city councils.' },
    { icon: 'bi-flower2', title: 'Planting Intelligence', desc: 'Zone-aware planting calendars, guides, and harvest tracking that keep members growing all season.' },
    { icon: 'bi-building', title: 'Grows With You', desc: 'One neighborhood garden or a citywide network — manage every site from one place with volume pricing.' },
  ];

  const features = marketplaceEnabled ? marketplaceFeatures : gardenFeatures;

  const currentMonth = new Date().getMonth();
  const seasonalGuides = {
    winter: {
      months: 'December - February',
      title: 'Winter in Nebraska',
      items: ['Indoor microgreens & sprouts', 'Stored root vegetables (carrots, beets, turnips)', 'Winter squash varieties', 'Preserved goods (jams, pickles, dried herbs)', 'Fresh eggs from backyard flocks'],
      tip: 'Many growers have cold frames and hoop houses extending their seasons. Check listings for greenhouse-grown greens!',
    },
    spring: {
      months: 'March - May',
      title: 'Spring in Nebraska',
      items: ['Lettuce, spinach & arugula', 'Radishes & green onions', 'Asparagus', 'Rhubarb', 'Peas & sugar snaps', 'Fresh herb starts'],
      tip: 'Spring is transplant season! Look for tomato, pepper, and herb seedlings from experienced local growers.',
    },
    summer: {
      months: 'June - August',
      title: 'Summer in Nebraska',
      items: ['Tomatoes (heirloom, cherry, beefsteak)', 'Sweet corn', 'Cucumbers & zucchini', 'Peppers (sweet & hot)', 'Green beans', 'Melons & berries', 'Fresh herbs galore'],
      tip: 'Peak season! Expect an abundance of listings. This is the best time to stock up and preserve.',
    },
    fall: {
      months: 'September - November',
      title: 'Fall in Nebraska',
      items: ['Pumpkins & winter squash', 'Apples & pears', 'Late-season tomatoes', 'Kale, chard & collards', 'Sweet potatoes', 'Brussels sprouts'],
      tip: 'Fall harvest is spectacular in Nebraska. Look for bulk deals perfect for canning and freezing.',
    },
  };

  const getSeason = () => {
    if (currentMonth >= 2 && currentMonth <= 4) return 'spring';
    if (currentMonth >= 5 && currentMonth <= 7) return 'summer';
    if (currentMonth >= 8 && currentMonth <= 10) return 'fall';
    return 'winter';
  };
  const season = seasonalGuides[getSeason()];

  const gardenFaqs = [
    {
      q: 'What does YardHarvest cost?',
      a: 'It is free for gardeners and members. Garden organizers get a 14-day free trial of Garden Pro, then choose a monthly or annual plan. Networks and city programs running multiple gardens get volume pricing — see the Pricing page.',
    },
    {
      q: 'What is included for free vs. Garden Pro?',
      a: 'Free covers your garden profile, member directory, plot assignments, announcements, events, and harvest logging. Garden Pro adds dues and expense management, volunteer shift scheduling, broadcast messaging, photo wall, custom email branding, the plot grid designer, and data export.',
    },
    {
      q: 'How do online dues payments work?',
      a: 'Connect your garden’s Stripe account in a few minutes (it never leaves the app) and members can pay dues online by card. Payments go directly to your garden, and the platform tracks who has paid, who is partial, and who needs a reminder.',
    },
    {
      q: 'We run multiple gardens — can we manage them together?',
      a: 'Yes. Nonprofits and city programs can run any number of gardens under one organization with volume pricing, centralized administration, and network-wide impact reporting. Contact us from the Pricing page.',
    },
    {
      q: 'Can we produce reports for funders and councils?',
      a: 'Yes — harvest pounds, food-bank donations, volunteer hours, participation, and dues collection are tracked automatically and exportable, so seasonal impact reports take minutes instead of days.',
    },
    {
      q: 'What happens to our data if we cancel?',
      a: 'Nothing is deleted. Pro features lock, but your garden profile, members, plots, and history remain intact, and you can export your data at any time.',
    },
  ];

  const faqs = [
    {
      q: 'How do I sign up as a seller?',
      a: 'Just create a free YardHarvest account and navigate to "Sell" to create your first listing. Add a photo, set your price and quantity, and you are live! There are no upfront fees.',
    },
    {
      q: 'Is there a fee for using YardHarvest?',
      a: 'YardHarvest is free to browse and buy. We keep the platform running through a small service fee on completed transactions. Sellers keep the vast majority of every sale.',
    },
    {
      q: 'How does pickup and delivery work?',
      a: 'When a buyer places an order, the seller can offer porch pickup, a meeting point, or local delivery. Details are arranged through our built-in messaging system after the order is placed.',
    },
    {
      q: 'What if something is wrong with my order?',
      a: 'We encourage buyers and sellers to communicate directly through our messaging feature. If you receive produce that does not match the listing, you can leave an honest review and reach out to support.',
    },
    {
      q: 'How does dynamic pricing work?',
      a: 'Our system adjusts effective prices based on local supply and demand. When a vegetable is in high demand and low supply, prices may increase slightly. When supply is abundant, prices stay low. This keeps the marketplace fair and responsive.',
    },
    {
      q: 'Do I need a license to sell my garden produce?',
      a: 'Nebraska has a Cottage Food Law that allows you to sell certain homegrown produce without a special license. YardHarvest is designed for backyard gardeners sharing surplus. Always check local regulations for your specific situation.',
    },
    {
      q: 'How far away can buyers be?',
      a: 'You can set a delivery/pickup radius on your listings. Most transactions happen within a 10-mile radius, but our search lets buyers look up to 50 miles away for specialty items.',
    },
    {
      q: 'Can I sell preserved goods like jams or pickles?',
      a: 'Potentially! Nebraska cottage food laws cover certain preserved items. Check your local guidelines. If allowed, you can list them on YardHarvest with the appropriate category.',
    },
  ];

  return (
    <div>
      <Seo
        title="About"
        path="/about"
        description="YardHarvest's story and mission: making community gardens easier to run and helping local garden networks thrive."
      />
      {/* Hero Section */}
      <div
        className="hero-section text-center position-relative overflow-hidden"
        style={{
          padding: '5rem 2rem',
          borderRadius: '16px',
          marginBottom: '3rem',
        }}
      >
        <div style={{
          position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
          background: 'url("data:image/svg+xml,%3Csvg width=\'60\' height=\'60\' viewBox=\'0 0 60 60\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cg fill=\'none\' fill-rule=\'evenodd\'%3E%3Cg fill=\'%23ffffff\' fill-opacity=\'0.05\'%3E%3Cpath d=\'M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z\'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")',
          opacity: 0.5,
        }} />
        <div className="position-relative">
          <div style={{ marginBottom: '1rem' }}>
            <img src="/sunflower.svg" alt="" style={{ width: '4rem', height: '4rem', borderRadius: '0.7rem' }} />
          </div>
          <h1 className="display-3 fw-bold mb-3" style={{ letterSpacing: '-1px' }}>
            YardHarvest
          </h1>
          {marketplaceEnabled ? (
            <>
              <p className="lead fs-4 mb-2" style={{ maxWidth: '700px', margin: '0 auto', opacity: 0.95 }}>
                Connecting neighbors through the freshest produce in Omaha
              </p>
              <p className="fs-6 mb-4" style={{ maxWidth: '550px', margin: '0 auto', opacity: 0.8 }}>
                From your neighbor's garden to your kitchen table &mdash; no trucks, no warehouses, no middlemen.
              </p>
            </>
          ) : (
            <>
              <p className="lead fs-4 mb-2" style={{ maxWidth: '700px', margin: '0 auto', opacity: 0.95 }}>
                Less admin, more garden
              </p>
              <p className="fs-6 mb-4" style={{ maxWidth: '550px', margin: '0 auto', opacity: 0.8 }}>
                The management platform for community gardens &mdash; and the nonprofits and city programs behind them.
              </p>
            </>
          )}
          {!user && (
            <div className="d-flex justify-content-center gap-3 flex-wrap">
              <Link to="/register" className="yh-btn-dark">
                <i className="bi bi-person-plus"></i>Join YardHarvest
              </Link>
              {marketplaceEnabled ? (
                <Link to="/search" className="yh-btn-ghost">
                  <i className="bi bi-search"></i>Browse Produce
                </Link>
              ) : (
                <Link to="/gardens" className="yh-btn-ghost">
                  <i className="bi bi-tree"></i>Explore Gardens
                </Link>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Our Story Section */}
      <div className="row justify-content-center mb-5">
        <div className="col-lg-8 text-center">
          <h2 className="fw-bold mb-4">
            <i className="bi bi-book text-success me-2"></i>Our Story
          </h2>
          <div className="text-start" style={{ fontSize: '1.1rem', lineHeight: '1.8' }}>
            <p>
              YardHarvest started with a simple observation on a summer evening in 2024. In neighborhoods
              across Omaha &mdash; from Dundee to Elkhorn, Benson to Bellevue &mdash; backyard gardens were
              overflowing. Tomatoes ripened faster than families could eat them. Zucchini multiplied like
              magic. Herb gardens grew lush and fragrant while most of the harvest went unused.
            </p>
            <p>
              At the same time, just a few blocks away, neighbors were buying plastic-wrapped produce
              trucked in from hundreds of miles away &mdash; produce that was days or even weeks old before
              it hit the shelf.
            </p>
            <p>
              We thought: <em>what if we could connect these two groups?</em> What if the gardener with
              fifty pounds of tomatoes could easily find the neighbor who would love to buy a few pounds of
              vine-ripened heirlooms? What if we could turn surplus into income and reduce food waste at
              the same time?
            </p>
            {marketplaceEnabled ? (
              <p className="mb-0">
                That is how YardHarvest was born &mdash; a marketplace built specifically for Omaha&apos;s
                backyard gardeners and the neighbors who love truly fresh, local food. No commercial farms.
                No industrial agriculture. Just people growing food and sharing it with the folks next door.
              </p>
            ) : (
              <>
                <p>
                  That observation grew into YardHarvest. As we worked with growers, we kept meeting the
                  people who make local food possible at scale: community garden organizers &mdash;
                  volunteers, nonprofit program managers, and city parks staff &mdash; running plots,
                  dues, waitlists, and workdays out of spreadsheets, paper folders, and group texts.
                </p>
                <p className="mb-0">
                  So that is what YardHarvest became: a management platform built specifically for
                  community gardens and the organizations behind them. Less time on admin and chasing
                  payments, more time growing food, building community, and proving impact to the
                  funders and councils who keep gardens alive.
                </p>
              </>
            )}
          </div>
        </div>
      </div>

      <hr className="my-5" />

      {/* How It Works Section */}
      <div className="mb-5">
        <h2 className="fw-bold text-center mb-2">
          <i className="bi bi-signpost-split text-success me-2"></i>How It Works
        </h2>
        <p className="text-center text-muted mb-5">Simple for everyone &mdash; whether you grow it or eat it.</p>

        {marketplaceEnabled ? (
          <>
            {/* Buyers */}
            <h4 className="text-center mb-4">
              <span className="badge bg-success px-3 py-2 fs-6">
                <i className="bi bi-cart3 me-2"></i>For Buyers
              </span>
            </h4>
            <div className="row g-4 mb-5 justify-content-center">
              {buyerSteps.map((step, i) => (
                <div className="col-md-4" key={i}>
                  <div className="card h-100 border-0 shadow-sm text-center" style={{ borderTop: '3px solid var(--yh-lime)' }}>
                    <div className="card-body p-4">
                      <div
                        className="rounded-circle d-inline-flex align-items-center justify-content-center mb-3"
                        style={{ width: '70px', height: '70px', background: 'var(--yh-lime-soft)', color: 'var(--yh-ink)', fontSize: '1.8rem' }}
                      >
                        <i className={`bi ${step.icon}`}></i>
                      </div>
                      <div className="text-muted small mb-2">Step {i + 1}</div>
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
                <i className="bi bi-flower1 me-2"></i>For Sellers
              </span>
            </h4>
            <div className="row g-4 justify-content-center">
              {sellerSteps.map((step, i) => (
                <div className="col-md-4" key={i}>
                  <div className="card h-100 border-0 shadow-sm text-center" style={{ borderTop: '3px solid var(--yh-lime)' }}>
                    <div className="card-body p-4">
                      <div
                        className="rounded-circle d-inline-flex align-items-center justify-content-center mb-3"
                        style={{ width: '70px', height: '70px', background: 'var(--yh-surface)', color: 'var(--yh-ink)', fontSize: '1.8rem' }}
                      >
                        <i className={`bi ${step.icon}`}></i>
                      </div>
                      <div className="text-muted small mb-2">Step {i + 1}</div>
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
                <i className="bi bi-tree me-2"></i>For Gardeners
              </span>
            </h4>
            <div className="row g-4 justify-content-center">
              {[
                { icon: 'bi-search', title: 'Find a Garden', desc: 'Browse community gardens in your area and find one that fits.' },
                { icon: 'bi-flag', title: 'Reserve a Plot', desc: 'Sign up, reserve a plot, and connect with your garden organizer.' },
                { icon: 'bi-flower2', title: 'Grow Together', desc: 'Plant, harvest, track your progress, and volunteer alongside neighbors.' },
              ].map((step, i) => (
                <div className="col-md-4" key={i}>
                  <div className="card h-100 border-0 shadow-sm text-center" style={{ borderTop: '3px solid var(--yh-lime)' }}>
                    <div className="card-body p-4">
                      <div
                        className="rounded-circle d-inline-flex align-items-center justify-content-center mb-3"
                        style={{ width: '70px', height: '70px', background: 'var(--yh-lime-soft)', color: 'var(--yh-ink)', fontSize: '1.8rem' }}
                      >
                        <i className={`bi ${step.icon}`}></i>
                      </div>
                      <div className="text-muted small mb-2">Step {i + 1}</div>
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
            <i className="bi bi-journal-richtext"></i>Learn more about the Garden Pro Platform
          </a>
        </div>
      </div>

      <hr className="my-5" />

      {/* Why YardHarvest */}
      <div className="mb-5">
        <h2 className="fw-bold text-center mb-2">
          <i className="bi bi-stars text-success me-2"></i>Why YardHarvest?
        </h2>
        <p className="text-center text-muted mb-5">
          {marketplaceEnabled
            ? 'Six reasons to love your local food marketplace.'
            : 'Six reasons garden organizers and networks choose YardHarvest.'}
        </p>
        <div className="row g-4">
          {features.map((feature, i) => (
            <div className="col-md-6 col-lg-4" key={i}>
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
        <h2 className="fw-bold text-center mb-2">
          <i className="bi bi-calendar3 text-success me-2"></i>What&apos;s Growing Now?
        </h2>
        <p className="text-center text-muted mb-4">A seasonal guide for Nebraska produce.</p>
        <div className="row justify-content-center">
          <div className="col-lg-8">
            <div className="card border-0 shadow-sm" style={{ borderLeft: '5px solid var(--brand-accent)' }}>
              <div className="card-body p-4">
                <div className="d-flex align-items-center mb-3">
                  <span className="badge bg-success me-3 px-3 py-2 fs-6">{season.months}</span>
                  <h4 className="fw-bold mb-0">{season.title}</h4>
                </div>
                <div className="row">
                  <div className="col-md-7">
                    <h6 className="fw-semibold mb-2">{marketplaceEnabled ? 'Look for these on YardHarvest:' : 'In season in Nebraska gardens:'}</h6>
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
                        <i className="bi bi-lightbulb text-warning me-2"></i>Seasonal Tip
                      </h6>
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
          className="text-center p-5 rounded-4"
          style={{
            background: '#f3f7e6',
            border: '1px solid #e9efd8',
          }}
        >
          <h2 className="fw-bold mb-3" style={{ color: 'var(--brand-primary)' }}>
            Ready to Join the Movement?
          </h2>
          <p className="fs-5 mb-4" style={{ color: 'var(--brand-secondary)', maxWidth: '600px', margin: '0 auto' }}>
            {marketplaceEnabled
              ? 'Whether you have extra tomatoes to share or you want the freshest food in town, YardHarvest has a place for you.'
              : 'Whether you run one neighborhood garden or a citywide network, YardHarvest takes the admin off your plate.'}
          </p>
          <div className="d-flex justify-content-center gap-3 flex-wrap">
            {marketplaceEnabled ? (
              user ? (
                <>
                  <Link to="/listings/create" className="btn btn-success btn-lg px-4">
                    <i className="bi bi-plus-circle me-2"></i>List Your Produce
                  </Link>
                  <Link to="/search" className="btn btn-outline-success btn-lg px-4">
                    <i className="bi bi-search me-2"></i>Find Fresh Food
                  </Link>
                </>
              ) : (
                <>
                  <Link to="/register" className="btn btn-success btn-lg px-4">
                    <i className="bi bi-flower1 me-2"></i>Sign Up as a Grower
                  </Link>
                  <Link to="/register" className="btn btn-outline-success btn-lg px-4">
                    <i className="bi bi-cart3 me-2"></i>Sign Up as a Buyer
                  </Link>
                </>
              )
            ) : (
              <>
                <Link to="/gardens" className="btn btn-success btn-lg px-4">
                  <i className="bi bi-tree me-2"></i>Explore Gardens
                </Link>
                <Link to="/gardens" className="btn btn-outline-success btn-lg px-4">
                  <i className="bi bi-people me-2"></i>Join a Garden
                </Link>
              </>
            )}
          </div>
        </div>
      </div>

      <hr className="my-5" />

      {/* FAQ Section */}
      <div className="mb-5">
        <h2 className="fw-bold text-center mb-2">
          <i className="bi bi-question-circle text-success me-2"></i>Frequently Asked Questions
        </h2>
        <p className="text-center text-muted mb-5">Everything you need to know about YardHarvest.</p>
        <div className="row justify-content-center">
          <div className="col-lg-8">
            <div className="accordion" id="faqAccordion">
              {(marketplaceEnabled ? faqs : gardenFaqs).map((faq, i) => (
                <div className="accordion-item border-0 mb-2 shadow-sm rounded-3 overflow-hidden" key={i}>
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
            ? 'YardHarvest — Homegrown in Omaha, shared with love.'
            : 'YardHarvest — Less admin, more garden.'}
        </p>
      </div>
    </div>
  );
}
