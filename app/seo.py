"""Server-side SEO/GEO meta injection for the React SPA.

The SPA sets per-route title/description/canonical client-side
(react-helmet-async in frontend/src/components/Seo.jsx) — which works for
Googlebot (it renders JS) but NOT for most AI/answer-engine crawlers (GPTBot,
ClaudeBot, PerplexityBot) or social scrapers, which read raw HTML. This module
injects the same per-route meta — plus JSON-LD structured data — into
index.html at serve time, so a no-JS crawler sees real page identity.

Contract with the client: values here MIRROR the client Seo component's
values (same title pattern `<Title> — YardHarvest`, same descriptions), and
every injected tag carries ``data-ssr="1"`` so main.jsx removes them at
hydration, leaving Helmet the sole owner of the live DOM.
"""
import json
import os
import re
from markupsafe import escape

SITE_NAME = 'YardHarvest'
DEFAULT_TITLE = 'YardHarvest — Community Garden Management Platform'
DEFAULT_DESC = (
    'YardHarvest is the all-in-one platform for community gardens — manage '
    'plots, members, dues, events and volunteers, and grow a thriving local '
    'garden network.')

# Static route → (title, description). MIRRORS the client <Seo> props — keep
# in sync when a page's Seo copy changes.
HELP_TITLE = 'YardHarvest Help'

PAGE_META = {
    '/': (None, DEFAULT_DESC),
    '/about': ('About',
               "YardHarvest's story and mission: making community gardens "
               'easier to run and helping local garden networks thrive.'),
    '/pricing': ('Pricing',
                 'Simple, transparent pricing for community gardens. Start '
                 'free, upgrade to Garden Pro for messaging, finance, photos '
                 'and more.'),
    '/gardens': ('Community Gardens',
                 'Browse community gardens near you on YardHarvest. Find a '
                 'plot, join a garden, and grow alongside your neighbors.'),
    '/planting-calendar': ('Planting Calendar',
                           'A location-aware planting calendar: when to sow, '
                           'transplant and harvest each crop based on your '
                           'local frost dates and growing zone.'),
    '/harvest-forecast': ('Harvest Forecast',
                          'See what local gardens are growing and when crops '
                          'will be ready to harvest in your area.'),
    '/book': ('Book time with James',
              'Schedule a 30-minute intro call about YardHarvest — pick any '
              'open time that works for you, no back-and-forth.'),
    '/terms': ('Terms of Service', 'YardHarvest terms of service.'),
    '/privacy': ('Privacy Policy', 'How YardHarvest handles your data.'),
    '/groups': ('Neighborhood Groups',
                'Join neighborhood gardening groups on YardHarvest.'),
    '/help': (HELP_TITLE,
              'How to run a community garden on YardHarvest: setup, plots, '
              'members, dues, Stripe payouts, Tap to Pay and troubleshooting.'),
    '/about/guide': ('The Community Garden Guide',
                     'A friendly, practical guide to starting and running a '
                     'community garden — land, funding, building, organizing '
                     'neighbors, and keeping it thriving.'),
}

# The Community Garden Guide chapters — MIRRORS frontend/src/data/gardenGuide.js
# (slugs, titles, descriptions). Update both together.
# Help Centre articles - MIRRORS frontend/src/data/helpCenter.js
# (slugs, titles, descriptions). Update both together; the
# generator lives in the commit that added the Help Centre.
HELP_META = {
    'create-a-garden': (
        "Create your garden",
        "How to create a community garden on YardHarvest: the details "
        "that matter, what members see, and what you can change "
        "later."),
    'plots-and-layout': (
        "Plots and the layout designer",
        "Add garden plots, assign them to members, and draw your "
        "garden layout on a grid so members can see which bed is "
        "theirs."),
    'members-and-roles': (
        "Members and roles",
        "Approve members, export your roster, and understand exactly "
        "which garden roles grant permissions in YardHarvest."),
    'events-and-shifts': (
        "Events and volunteer shifts",
        "Create garden events with RSVPs, and schedule volunteer "
        "shifts with signups, reminders and attendance tracking."),
    'resources-and-tools': (
        "Shared tools and resources",
        "Track shared garden tools, print QR labels, and check "
        "equipment in and out so you know who has what."),
    'communication': (
        "Announcements, messages and the community wall",
        "When to use announcements, direct messages, the community "
        "wall, and announcement emails to reach your garden members."),
    'photos-and-impact': (
        "Photos, harvest logs and impact",
        "Post garden photos, log harvest weights, and turn a season "
        "of records into a funder-ready impact report."),
    'money-overview': (
        "How money moves through YardHarvest",
        "Where garden dues and sales actually go, who holds the "
        "money, and why YardHarvest never sits between you and your "
        "funds."),
    'stripe-setup': (
        "Set up payouts with Stripe",
        "Step-by-step Stripe Connect onboarding for a community "
        "garden: what Stripe asks for, how long it takes, and how to "
        "know it worked."),
    'dues': (
        "Generating and collecting dues",
        "Generate seasonal dues for plot holders, take payment online "
        "or in person, record cash, and chase what is outstanding."),
    'tap-to-pay': (
        "Tap to Pay at the gate",
        "Use Tap to Pay on iPhone in the YardHarvest app to collect "
        "dues and run plant sales in person, with no card reader."),
    'money-feed': (
        "Reading your Stripe activity",
        "Understand the Finance Stripe tab: card money in, platform "
        "and Stripe fees, refunds, chargebacks, and bank deposits."),
    'stripe-pitfalls': (
        "Stripe pitfalls worth knowing",
        "Common Stripe problems for community gardens: payout not "
        "ready, card-present inactive, restricted accounts, and "
        "missing payouts."),
    'free-and-pro': (
        "What is free and what Garden Pro adds",
        "A precise breakdown of which YardHarvest features are free "
        "for every community garden and which require Garden Pro."),
    'trial-and-billing': (
        "Trials, upgrading and cancelling",
        "Start a Garden Pro trial, upgrade, change plan, or cancel \u2014 "
        "and what happens to your data either way."),
    'for-gardeners': (
        "For gardeners",
        "How to join a community garden on YardHarvest, claim a plot, "
        "pay your dues and log your harvest."),
    'common-problems': (
        "Common problems",
        "Troubleshooting YardHarvest: missing emails, members who "
        "cannot see features, locked Pro tabs and things that look "
        "wrong."),
}


GUIDE_TITLE = 'The Community Garden Guide'
GUIDE_META = {
    'getting-started': (
        'Getting Started',
        'How to start a community garden: gauge neighborhood interest, build '
        'a founding team, and set a shared vision before you touch a shovel.'),
    'finding-land': (
        'Finding Land & Site Planning',
        'How to find land for a community garden, evaluate sun, water and '
        'soil, and secure a lease or agreement that protects the garden.'),
    'funding-and-budget': (
        'Funding & Your First Budget',
        'Community garden startup costs, realistic budgets, plot dues, '
        'grants, fundraising ideas, and fiscal sponsorship explained simply.'),
    'building-the-garden': (
        'Building the Garden',
        'Designing a community garden layout, building raised beds, setting '
        'up water, and organizing a volunteer build day that people enjoy.'),
    'organizing-people': (
        'Organizing People',
        'How to organize community garden members: plot agreements, '
        'waitlists, volunteer hours, leadership structure, and avoiding '
        'coordinator burnout.'),
    'running-the-season': (
        'Running the Season',
        'A season-by-season rhythm for running a community garden: renewals, '
        'spring kickoff, summer maintenance, events, and winterizing.'),
    'harvest-and-impact': (
        'Harvest & Impact',
        'Tracking community garden harvests and impact: donation programs, '
        'simple record-keeping, and reporting that wins over funders and '
        'cities.'),
    'troubleshooting': (
        'Troubleshooting',
        'Common community garden problems and fixes: theft and vandalism, '
        'abandoned plots, member conflicts, pests, and leadership turnover.'),
}

# Mirrors the visible FAQ copy in frontend/src/pages/Pricing.jsx — structured
# data must match on-page content, so update BOTH together.
PRICING_FAQS = [
    ('Is there a contract?',
     'No. Garden Pro is month-to-month or annual with no long-term '
     'commitment. Cancel anytime from your garden settings.'),
    ('What happens when my trial ends?',
     'Pro features lock, but your garden profile, plots, members, and all '
     'your data remain intact. You can subscribe anytime to unlock '
     'everything again.'),
    ('How do online dues payments work?',
     "Connect your garden's Stripe account from the billing page (the setup "
     'happens right in the app) and members can pay dues online. Payments go '
     'directly to your garden, and collection status is tracked automatically.'),
    ('We run multiple gardens — how does pricing work?',
     "Networks and city programs get volume pricing per garden with "
     'centralized billing and network-wide impact reporting. Contact us and '
     "we'll put together a plan for your organization."),
]

# Both public URL shapes for a garden: the opaque public_id the app links to
# everywhere (grd_...), plus legacy numeric ids still present in old sitemaps
# and inbound links. Reserved sub-paths (create, my-gardens) never match.
_GARDEN_PATH_RE = re.compile(r'^/gardens/(grd_\w+|\d+)$')

# Auth/utility pages: real titles (so crawlers that reach them don't report
# duplicate/missing metadata) but noindex — they have no search value.
NOINDEX_META = {
    '/login': ('Log in', 'Log in to your YardHarvest account.'),
    '/register': ('Create your account',
                  'Create a free YardHarvest account to join or run a '
                  'community garden.'),
    '/forgot-password': ('Reset your password',
                         'Request a YardHarvest password reset link.'),
    '/reset-password': ('Choose a new password',
                        'Choose a new YardHarvest password.'),
    '/verify-email-change': ('Verify your email',
                             'Confirm your YardHarvest email change.'),
}

_index_cache = {}


def _site_base():
    from flask import current_app
    return (current_app.config.get('SITE_URL') or 'https://www.yardharvest.app').rstrip('/')


def _org_jsonld(base):
    return {
        '@context': 'https://schema.org', '@type': 'Organization',
        'name': SITE_NAME, 'url': base, 'logo': f'{base}/sunflower.svg',
        'email': 'james@yardharvest.app',
        'description': DEFAULT_DESC,
    }


def _software_jsonld(base):
    # Search engines and AI crawlers read these offers. They must be the prices
    # the admin console actually charges — this used to read config.py and so
    # advertised a price the checkout did not honour.
    from app.pricing import garden_pro_pricing
    pro = garden_pro_pricing()
    monthly, yearly, trial = pro['monthly'], pro['yearly'], pro['trial_days']
    return {
        '@context': 'https://schema.org', '@type': 'SoftwareApplication',
        'name': SITE_NAME, 'applicationCategory': 'BusinessApplication',
        'operatingSystem': 'Web',
        'url': base, 'description': DEFAULT_DESC,
        'offers': [
            {'@type': 'Offer', 'name': f'Garden Pro (monthly, {trial}-day free trial)',
             'price': f'{monthly:.2f}', 'priceCurrency': 'USD'},
            {'@type': 'Offer', 'name': 'Garden Pro (annual)',
             'price': f'{yearly:.2f}', 'priceCurrency': 'USD'},
        ],
    }


def _faq_jsonld():
    return {
        '@context': 'https://schema.org', '@type': 'FAQPage',
        'mainEntity': [{
            '@type': 'Question', 'name': q,
            'acceptedAnswer': {'@type': 'Answer', 'text': a},
        } for q, a in PRICING_FAQS],
    }


def _meta_for_path(path):
    """Resolve (title, description, noindex, jsonld_list, canonical_path) for
    a request path. ``canonical_path`` overrides the request path in the
    canonical/og:url tags — used to collapse a garden's legacy numeric URL and
    its opaque public_id URL into ONE canonical, so crawlers stop reporting
    the two shapes as duplicate pages."""
    base = _site_base()
    path = (path or '/').rstrip('/') or '/'

    if path.startswith('/book/manage'):
        # Private per-booking manage links — never index.
        return ('Manage your booking', 'Manage your YardHarvest booking.',
                True, [], None)

    if path in NOINDEX_META:
        title, desc = NOINDEX_META[path]
        return title, desc, True, [], None

    m = _GARDEN_PATH_RE.match(path)
    if m:
        try:
            from app import db
            from app.models import CommunityGarden
            ref = m.group(1)
            if ref.startswith('grd_'):
                g = CommunityGarden.query.filter_by(public_id=ref).first()
            else:
                g = db.session.get(CommunityGarden, int(ref))
            if g and g.is_active:
                loc = ', '.join(p for p in (g.city, g.state) if p)
                desc = (g.description or '').strip()[:280] or (
                    f'{g.name} is a community garden'
                    + (f' in {loc}' if loc else '') + ' on YardHarvest.')
                canonical = (f'/gardens/{g.public_id}' if g.public_id else None)
                return (f'{g.name}' + (f' ({loc})' if loc else ''),
                        desc, False, [], canonical)
        except Exception:  # DB hiccup — fall through to defaults, never 500
            pass

    if path.startswith('/planting-guide/'):
        crop = path.rsplit('/', 1)[-1].replace('-', ' ').replace('%20', ' ')
        crop_t = crop.strip().title()[:60]
        if crop_t:
            return (f'{crop_t} Growing Guide',
                    f'When and how to plant {crop_t.lower()}: sowing and '
                    'transplant windows, frost sensitivity, companions, and '
                    'harvest timing for your zone.', False, [], None)

    if path.startswith('/help/'):
        slug = path[len('/help/'):].strip('/')
        if slug in HELP_META:
            art_title, desc = HELP_META[slug]
            article = {
                '@context': 'https://schema.org', '@type': 'Article',
                'headline': f'{art_title} — {HELP_TITLE}',
                'description': desc,
                'url': f'{base}{path}',
                'author': {'@type': 'Organization', 'name': SITE_NAME},
                'publisher': {'@type': 'Organization', 'name': SITE_NAME,
                              'url': base},
                'isPartOf': {'@type': 'CreativeWorkSeries', 'name': HELP_TITLE,
                             'url': f'{base}/help'},
            }
            return f'{art_title} — {HELP_TITLE}', desc, False, [article], None
        # Unknown article: the SPA redirects to the hub, so point crawlers there.
        title, desc = PAGE_META['/help']
        return title, desc, False, [], '/help'

    if path.startswith('/about/guide/'):
        slug = path.rsplit('/', 1)[-1]
        if slug in GUIDE_META:
            ch_title, desc = GUIDE_META[slug]
            article = {
                '@context': 'https://schema.org', '@type': 'Article',
                'headline': f'{ch_title} — {GUIDE_TITLE}',
                'description': desc,
                'url': f'{base}{path}',
                'author': {'@type': 'Organization', 'name': SITE_NAME},
                'publisher': {'@type': 'Organization', 'name': SITE_NAME,
                              'url': base},
                'isPartOf': {'@type': 'CreativeWorkSeries', 'name': GUIDE_TITLE,
                             'url': f'{base}/about/guide'},
            }
            return f'{ch_title} — {GUIDE_TITLE}', desc, False, [article], None
        # Unknown chapter — the SPA redirects to the hub; meta mirrors that.
        title, desc = PAGE_META['/about/guide']
        return title, desc, False, [], '/about/guide'

    if path in PAGE_META:
        title, desc = PAGE_META[path]
        jsonld = []
        if path == '/':
            jsonld = [_org_jsonld(base), _software_jsonld(base)]
        elif path == '/pricing':
            jsonld = [_software_jsonld(base), _faq_jsonld()]
        elif path == '/book':
            jsonld = [_org_jsonld(base)]
        return title, desc, False, jsonld, None

    return None, DEFAULT_DESC, False, [], None


def _build_head(path):
    """Compose the injected head block for *path* (all tags data-ssr tagged)."""
    base = _site_base()
    title, desc, noindex, jsonld, canonical_path = _meta_for_path(path)
    full_title = f'{title} — {SITE_NAME}' if title else DEFAULT_TITLE
    canonical = base + (canonical_path or (path or '/').rstrip('/') or '/')
    e_title, e_desc = escape(full_title), escape(desc[:300])

    parts = [
        f'<title>{e_title}</title>',
        f'<meta name="description" content="{e_desc}" data-ssr="1" />',
    ]
    if noindex:
        parts.append('<meta name="robots" content="noindex, follow" data-ssr="1" />')
    else:
        parts.append(f'<link rel="canonical" href="{escape(canonical)}" data-ssr="1" />')
    parts += [
        f'<meta property="og:title" content="{e_title}" data-ssr="1" />',
        f'<meta property="og:description" content="{e_desc}" data-ssr="1" />',
        f'<meta property="og:url" content="{escape(canonical)}" data-ssr="1" />',
        f'<meta property="og:site_name" content="{SITE_NAME}" data-ssr="1" />',
    ]
    for obj in jsonld:
        # JSON-LD scripts keep working after hydration removal isn't needed —
        # but tag them anyway so the client sweep leaves Helmet in sole control.
        payload = json.dumps(obj).replace('</', '<\\/')
        parts.append(f'<script type="application/ld+json" data-ssr="1">{payload}</script>')
    return '\n    '.join(parts)


def serve_spa_index(spa_dir, path):
    """Serve index.html with per-route meta injected (the no-JS crawler view).

    Falls back to the raw file on any surprise — serving the SPA must never
    break because of SEO decoration."""
    from flask import Response, send_from_directory
    try:
        index_path = os.path.join(spa_dir, 'index.html')
        mtime = os.path.getmtime(index_path)
        cached = _index_cache.get(spa_dir)
        if cached is not None and cached[0] == mtime:
            html = cached[1]
        else:
            with open(index_path, encoding='utf-8') as f:
                html = f.read()
            _index_cache[spa_dir] = (mtime, html)
        start = html.find('<title>')
        end = html.find('</title>')
        if start == -1 or end == -1:
            return send_from_directory(spa_dir, 'index.html')
        out = html[:start] + _build_head(path) + html[end + len('</title>'):]
        return Response(out, mimetype='text/html')
    except Exception:
        return send_from_directory(spa_dir, 'index.html')
