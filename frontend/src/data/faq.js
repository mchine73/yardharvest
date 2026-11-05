// Frequently asked questions — content for /faq and the home page's
// "Questions, answered" section.
//
// Short answers to what people ask before and just after they sign up. The
// help center (/help) is where the step-by-step lives; an answer here links
// there rather than growing into a second copy of it.
//
// Every answer states something the product actually does. Before adding one,
// find where the code, the help center or the pricing page says it — this is
// public copy that people decide on.
//
// PRICES AND FEES ARE NEVER HARDCODED. Write {{PRO_MONTHLY}}, {{PRO_YEARLY}},
// {{TRIAL_DAYS}} or {{DUES_FEE}} and the page fills them from
// /api/admin/public-pricing. An answer that needs a value carries `aNoPrice`
// (said when pricing could not load), or `needsPricing: true` to be left out
// instead. The platform-fee answer has two forms: `a` when the fee is 0 and
// `aFee` when it is not, so the page can never say "no cut" while one is set.
//
// KEEP IN SYNC: faq.es.js mirrors this file (faq.parity.test.js holds the
// structure), and app/seo.py mirrors both for the FAQPage structured data
// (tests/test_seo_es.py reads them through Node).

export const FAQ_TITLE = 'Frequently asked questions';
export const FAQ_DESCRIPTION =
  'Answers about YardHarvest: what it costs, what Garden Pro adds, where ' +
  'dues money goes, how gardeners get a plot, and what happens to your data.';
export const FAQ_INTRO =
  'The questions organizers and gardeners ask most, answered briefly. For ' +
  'step-by-step instructions, the help center has the detail.';

export const CATEGORIES = [
  { key: 'start', title: 'Getting started', icon: 'bi-flag' },
  { key: 'cost', title: 'Cost and Garden Pro', icon: 'bi-tag' },
  { key: 'money', title: 'Dues and payments', icon: 'bi-cash-stack' },
  { key: 'gardeners', title: 'For gardeners', icon: 'bi-flower1' },
  { key: 'data', title: 'Privacy and your data', icon: 'bi-shield-lock' },
];

export const QUESTIONS = [
  // ---------------------------------------------------------------- start --
  {
    id: 'what-is-yardharvest',
    category: 'start',
    featured: true,
    q: 'What is YardHarvest?',
    a: 'Software for running a community garden. Organizers manage plots and the waitlist, members, dues, events, volunteer shifts, announcements, shared tools and harvest records in one place. Gardeners use it to find a garden, claim a plot, pay their dues and log what they grow.',
    link: { to: '/about', label: 'Our story' },
  },
  {
    id: 'who-is-it-for',
    category: 'start',
    q: 'Who is it for?',
    a: 'The people who organize community gardens and the volunteers who help them, the gardeners who rent plots, and organizations that run several gardens, such as nonprofits, extension programs and parks departments.',
  },
  {
    id: 'start-a-garden',
    category: 'start',
    featured: true,
    q: 'How do I start a garden on YardHarvest?',
    a: 'Create a free account, then choose Create a Garden. All you need is a name and a location; everything else can wait. Your garden goes live straight away with its own public page, which is the link you share with neighbors.',
    link: { to: '/help/create-a-garden', label: 'Create your garden' },
  },
  {
    id: 'is-the-garden-page-public',
    category: 'start',
    q: "Is my garden's page public?",
    a: "Yes. It shows your garden's description, address, rules, season dates, plot availability and any photos you post, and search engines index it, so it doubles as the garden's website.",
  },

  // ----------------------------------------------------------------- cost --
  {
    id: 'is-it-free',
    category: 'cost',
    featured: true,
    q: 'Is YardHarvest free?',
    a: 'For gardeners, always. For organizers, running a garden is free too: unlimited plots and members, the waitlist, events, announcements, the community wall, tool inventory, harvest logging, payout setup and collecting money in person with Tap to Pay. Garden Pro adds the administrative tools on top.',
    link: { to: '/help/free-and-pro', label: 'What is free and what Pro adds' },
  },
  {
    id: 'garden-pro',
    category: 'cost',
    q: 'What does Garden Pro cost, and what does it add?',
    a: '{{PRO_MONTHLY}} a month or {{PRO_YEARLY}} a year, with a free trial of {{TRIAL_DAYS}} days that needs no card. Pro adds dues (generating, tracking, reminders and exports), expenses and the finance summary, funder reports, direct messages and broadcasts, announcement emails, the photo wall, volunteer shifts, tool checkout with QR labels, and the layout designer.',
    aNoPrice: 'Garden Pro is a monthly or yearly subscription with a free trial that needs no card; the pricing page has the current prices. Pro adds dues (generating, tracking, reminders and exports), expenses and the finance summary, funder reports, direct messages and broadcasts, announcement emails, the photo wall, volunteer shifts, tool checkout with QR labels, and the layout designer.',
    link: { to: '/pricing', label: 'See pricing' },
  },
  {
    id: 'do-gardeners-pay',
    category: 'cost',
    q: 'Do gardeners pay anything to use YardHarvest?',
    a: 'No. Gardeners never pay YardHarvest. If your garden charges plot dues, that money goes to your garden.',
  },
  {
    id: 'contract-and-canceling',
    category: 'cost',
    q: 'Is there a contract? What happens if we cancel Pro?',
    a: "No contract: Pro is monthly or yearly, and you can cancel any time. It keeps running to the end of the period you've paid for, and nothing is deleted. Dues records, photos, shifts and reports stay, read-only until you come back, and everything free keeps working as before.",
  },
  {
    id: 'several-gardens',
    category: 'cost',
    q: 'We run several gardens. Is there a plan for us?',
    a: "Yes. Garden networks and city programs get volume pricing per garden, centralized billing and network-wide impact reporting. Book a call and we'll put a plan together.",
    link: { to: '/book', label: 'Book a call' },
  },

  // ---------------------------------------------------------------- money --
  {
    id: 'where-does-the-money-go',
    category: 'money',
    featured: true,
    q: 'Where does dues money go?',
    a: "Straight to your garden. Payments go to a Stripe account in your garden's name, and Stripe pays them out to your bank. YardHarvest never holds your garden's money.",
    link: { to: '/help/money-overview', label: 'How money moves' },
  },
  {
    id: 'platform-fee',
    category: 'money',
    needsPricing: true,
    q: 'Does YardHarvest take a cut of what we collect?',
    a: 'No. YardHarvest takes nothing from dues, in-person payments or sales. Card payments do carry Stripe processing fees, and your Finance tab shows, for every payment, what was charged, the fees, and what reached your bank.',
    aFee: 'YardHarvest keeps {{DUES_FEE}}% of each payment your garden collects. Card payments also carry Stripe processing fees. Your Finance tab shows, for every payment, what was charged, the fees, and what reached your bank.',
  },
  {
    id: 'how-members-pay',
    category: 'money',
    q: 'How can members pay their dues?',
    a: "Online by card or bank transfer, from the garden's page; in person with Tap to Pay on iPhone; or in cash or by check, which the organizer records by hand.",
    link: { to: '/help/dues', label: 'Generating and collecting dues' },
  },
  {
    id: 'collect-online',
    category: 'money',
    q: 'What do we need to collect dues online?',
    a: "A payout account. You connect your garden to Stripe from its billing page, without leaving YardHarvest. Stripe asks who you are and where to send the money, which the law requires of anyone paying out funds. Until that's done, members can't pay online.",
    link: { to: '/help/stripe-setup', label: 'Set up payouts with Stripe' },
  },

  // ------------------------------------------------------------ gardeners --
  {
    id: 'get-a-plot',
    category: 'gardeners',
    featured: true,
    q: 'How do I find a garden and get a plot?',
    a: "Browse the gardens, open the one near you, and either reserve an available plot or join its waitlist. The organizer approves requests, and you'll hear back either way.",
    link: { to: '/gardens', label: 'Browse gardens' },
  },
  {
    id: 'pay-my-dues',
    category: 'gardeners',
    q: 'How do I pay my dues?',
    a: "If your garden charges dues, you'll see what you owe on the garden's page and can pay by card or bank transfer. Your organizer can also take payment in person or record a cash payment for you.",
  },
  {
    id: 'log-my-harvest',
    category: 'gardeners',
    q: 'Why log my harvest?',
    a: "Your garden's total harvest is what its organizers show funders and the city to keep the garden going. It takes a few seconds: what you picked, and roughly what it weighed.",
  },

  // ----------------------------------------------------------------- data --
  {
    id: 'do-you-sell-my-data',
    category: 'data',
    q: 'Do you sell my data?',
    a: "No. We don't sell personal information, and we share it only with the services that run YardHarvest, such as hosting, payments and email, under contract. Your display name, profile photo and anything you post can be seen on your garden's public page.",
    link: { to: '/privacy', label: 'Privacy policy' },
  },
  {
    id: 'export-our-data',
    category: 'data',
    q: "Can we export our garden's data?",
    a: 'Yes. Exporting the member roster is free. With Garden Pro you can also export dues, finance records and funder reports as CSV.',
  },
  {
    id: 'more-help',
    category: 'data',
    q: 'Where can I get more help?',
    a: "The help center walks through setup, money and troubleshooting step by step. If you'd rather talk it through, book a call.",
    link: { to: '/help', label: 'Visit the help center' },
  },
];

/** Accent-insensitive, so "credito" finds "crédito" in the Spanish copy. */
function fold(s) {
  return String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
}

/** Questions matching every word of `query`, in their usual order. */
export function searchQuestions(query) {
  const terms = fold(query).trim().split(/\s+/).filter(Boolean);
  if (!terms.length) return QUESTIONS;
  return QUESTIONS.filter((item) => {
    const hay = fold(`${item.q} ${item.a} ${item.aFee || ''} ${item.aNoPrice || ''}`);
    return terms.every((term) => hay.includes(term));
  });
}
