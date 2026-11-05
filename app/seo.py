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
from urllib.parse import unquote

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
    '/faq': ('Frequently asked questions',
             'Answers about YardHarvest: what it costs, what Garden Pro '
             'adds, where dues money goes, how gardeners get a plot, and '
             'what happens to your data.'),
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
# Help Center articles - MIRRORS frontend/src/data/helpCenter.js
# (slugs, titles, descriptions). Update both together; the
# generator lives in the commit that added the Help Center.
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
        "Trials, upgrading and canceling",
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
     'Pro features lock, but your garden profile, plots, members, and '
     'all your data remain intact. You can subscribe anytime to unlock'
     ' everything again.'),
    ('How do online dues payments work?',
     'Connect your garden\u2019s Stripe account from the billing page (the '
     'setup happens right in the app) and members can pay dues online.'
     ' Payments go directly to your garden, and collection status is '
     'tracked automatically.'),
    ('We run multiple gardens \u2014 how does pricing work?',
     'Networks and city programs get volume pricing per garden with '
     'centralized billing and network-wide impact reporting. Contact '
     'us below and we\u2019ll put together a plan for your organization.'),
]

# The same questions on /es/pricing. MIRRORS pricing.faq*Q / faq*A in the
# Spanish catalog.
ES_PRICING_FAQS = [
    ('\u00bfHay contrato?',
     'No. Garden Pro es mensual o anual, sin compromiso a largo '
     'plazo. Cancela cuando quieras desde los ajustes de tu huerto.'),
    ('\u00bfQu\u00e9 pasa cuando termina mi prueba?',
     'Las funciones Pro se bloquean, pero el perfil de tu huerto, '
     'las parcelas, los integrantes y todos tus datos siguen '
     'intactos. Puedes suscribirte cuando quieras para volver a '
     'desbloquearlo todo.'),
    ('\u00bfC\u00f3mo funcionan los pagos de cuotas en l\u00ednea?',
     'Conecta la cuenta de Stripe de tu huerto desde la p\u00e1gina de '
     'facturaci\u00f3n (la configuraci\u00f3n se hace dentro de la app) y los '
     'integrantes podr\u00e1n pagar sus cuotas en l\u00ednea. Los pagos llegan'
     ' directamente a tu huerto y el estado de cobro se registra '
     'solo.'),
    ('Gestionamos varios huertos: \u00bfc\u00f3mo funcionan los precios?',
     'Las redes y los programas municipales obtienen precios por '
     'volumen por huerto, con facturaci\u00f3n centralizada e informes de'
     ' impacto de toda la red. Escr\u00edbenos m\u00e1s abajo y te preparamos '
     'un plan para tu organizaci\u00f3n.'),
]

# /faq, both languages: (id, question, answer, answer-when-a-dues-fee-is-set).
# MIRRORS frontend/src/data/faq.js and faq.es.js; tests/test_seo_es.py reads
# those modules through Node and asserts every entry. {{TOKENS}} are filled
# from the live pricing at request time, exactly as the page fills them.
FAQ_ITEMS = [
    ('what-is-yardharvest',
     'What is YardHarvest?',
     'Software for running a community garden. Organizers manage '
     'plots and the waitlist, members, dues, events, volunteer '
     'shifts, announcements, shared tools and harvest records in one'
     ' place. Gardeners use it to find a garden, claim a plot, pay '
     'their dues and log what they grow.',
     None),
    ('who-is-it-for',
     'Who is it for?',
     'The people who organize community gardens and the volunteers '
     'who help them, the gardeners who rent plots, and organizations'
     ' that run several gardens, such as nonprofits, extension '
     'programs and parks departments.',
     None),
    ('start-a-garden',
     'How do I start a garden on YardHarvest?',
     'Create a free account, then choose Create a Garden. All you '
     'need is a name and a location; everything else can wait. Your '
     'garden goes live straight away with its own public page, which'
     ' is the link you share with neighbors.',
     None),
    ('is-the-garden-page-public',
     'Is my garden\'s page public?',
     'Yes. It shows your garden\'s description, address, rules, '
     'season dates, plot availability and any photos you post, and '
     'search engines index it, so it doubles as the garden\'s '
     'website.',
     None),
    ('is-it-free',
     'Is YardHarvest free?',
     'For gardeners, always. For organizers, running a garden is '
     'free too: unlimited plots and members, the waitlist, events, '
     'announcements, the community wall, tool inventory, harvest '
     'logging, payout setup and collecting money in person with Tap '
     'to Pay. Garden Pro adds the administrative tools on top.',
     None),
    ('garden-pro',
     'What does Garden Pro cost, and what does it add?',
     '{{PRO_MONTHLY}} a month or {{PRO_YEARLY}} a year, with a free '
     'trial of {{TRIAL_DAYS}} days that needs no card. Pro adds dues'
     ' (generating, tracking, reminders and exports), expenses and '
     'the finance summary, funder reports, direct messages and '
     'broadcasts, announcement emails, the photo wall, volunteer '
     'shifts, tool checkout with QR labels, and the layout designer.',
     None),
    ('do-gardeners-pay',
     'Do gardeners pay anything to use YardHarvest?',
     'No. Gardeners never pay YardHarvest. If your garden charges '
     'plot dues, that money goes to your garden.',
     None),
    ('contract-and-canceling',
     'Is there a contract? What happens if we cancel Pro?',
     'No contract: Pro is monthly or yearly, and you can cancel any '
     'time. It keeps running to the end of the period you\'ve paid '
     'for, and nothing is deleted. Dues records, photos, shifts and '
     'reports stay, read-only until you come back, and everything '
     'free keeps working as before.',
     None),
    ('several-gardens',
     'We run several gardens. Is there a plan for us?',
     'Yes. Garden networks and city programs get volume pricing per '
     'garden, centralized billing and network-wide impact reporting.'
     ' Book a call and we\'ll put a plan together.',
     None),
    ('where-does-the-money-go',
     'Where does dues money go?',
     'Straight to your garden. Payments go to a Stripe account in '
     'your garden\'s name, and Stripe pays them out to your bank. '
     'YardHarvest never holds your garden\'s money.',
     None),
    ('platform-fee',
     'Does YardHarvest take a cut of what we collect?',
     'No. YardHarvest takes nothing from dues, in-person payments or'
     ' sales. Card payments do carry Stripe processing fees, and '
     'your Finance tab shows, for every payment, what was charged, '
     'the fees, and what reached your bank.',
     'YardHarvest keeps {{DUES_FEE}}% of each payment your garden '
     'collects. Card payments also carry Stripe processing fees. '
     'Your Finance tab shows, for every payment, what was charged, '
     'the fees, and what reached your bank.'),
    ('how-members-pay',
     'How can members pay their dues?',
     'Online by card or bank transfer, from the garden\'s page; in '
     'person with Tap to Pay on iPhone; or in cash or by check, '
     'which the organizer records by hand.',
     None),
    ('collect-online',
     'What do we need to collect dues online?',
     'A payout account. You connect your garden to Stripe from its '
     'billing page, without leaving YardHarvest. Stripe asks who you'
     ' are and where to send the money, which the law requires of '
     'anyone paying out funds. Until that\'s done, members can\'t pay '
     'online.',
     None),
    ('get-a-plot',
     'How do I find a garden and get a plot?',
     'Browse the gardens, open the one near you, and either reserve '
     'an available plot or join its waitlist. The organizer approves'
     ' requests, and you\'ll hear back either way.',
     None),
    ('pay-my-dues',
     'How do I pay my dues?',
     'If your garden charges dues, you\'ll see what you owe on the '
     'garden\'s page and can pay by card or bank transfer. Your '
     'organizer can also take payment in person or record a cash '
     'payment for you.',
     None),
    ('log-my-harvest',
     'Why log my harvest?',
     'Your garden\'s total harvest is what its organizers show '
     'funders and the city to keep the garden going. It takes a few '
     'seconds: what you picked, and roughly what it weighed.',
     None),
    ('do-you-sell-my-data',
     'Do you sell my data?',
     'No. We don\'t sell personal information, and we share it only '
     'with the services that run YardHarvest, such as hosting, '
     'payments and email, under contract. Your display name, profile'
     ' photo and anything you post can be seen on your garden\'s '
     'public page.',
     None),
    ('export-our-data',
     'Can we export our garden\'s data?',
     'Yes. Exporting the member roster is free. With Garden Pro you '
     'can also export dues, finance records and funder reports as '
     'CSV.',
     None),
    ('more-help',
     'Where can I get more help?',
     'The help center walks through setup, money and troubleshooting'
     ' step by step. If you\'d rather talk it through, book a call.',
     None),
]

ES_FAQ_ITEMS = [
    ('what-is-yardharvest',
     '\u00bfQu\u00e9 es YardHarvest?',
     'Un programa para llevar un huerto comunitario. Quienes lo '
     'organizan gestionan en un solo lugar las parcelas y la lista '
     'de espera, los integrantes, las cuotas, los eventos, los '
     'turnos de voluntariado, los anuncios, las herramientas '
     'compartidas y los registros de cosecha. Los hortelanos lo usan'
     ' para encontrar un huerto, conseguir una parcela, pagar sus '
     'cuotas y registrar lo que cultivan.',
     None),
    ('who-is-it-for',
     '\u00bfPara qui\u00e9n es?',
     'Para quienes organizan huertos comunitarios y los voluntarios '
     'que les ayudan, para los hortelanos que alquilan una parcela y'
     ' para las organizaciones que llevan varios huertos, como '
     'organizaciones sin \u00e1nimo de lucro, programas de extensi\u00f3n y '
     'departamentos de parques.',
     None),
    ('start-a-garden',
     '\u00bfC\u00f3mo creo un huerto en YardHarvest?',
     'Crea una cuenta gratis y luego elige \u00abCrear un huerto\u00bb. Solo '
     'necesitas un nombre y una ubicaci\u00f3n; todo lo dem\u00e1s puede '
     'esperar. Tu huerto queda publicado de inmediato con su propia '
     'p\u00e1gina p\u00fablica, que es el enlace que compartes con tus '
     'vecinos.',
     None),
    ('is-the-garden-page-public',
     '\u00bfLa p\u00e1gina de mi huerto es p\u00fablica?',
     'S\u00ed. Muestra la descripci\u00f3n del huerto, la direcci\u00f3n, las '
     'normas, las fechas de la temporada, las parcelas disponibles y'
     ' las fotos que publiques, y los buscadores la indexan, as\u00ed que'
     ' tambi\u00e9n sirve como sitio web del huerto.',
     None),
    ('is-it-free',
     '\u00bfYardHarvest es gratis?',
     'Para los hortelanos, siempre. Para quienes organizan, llevar '
     'un huerto tambi\u00e9n es gratis: parcelas e integrantes '
     'ilimitados, la lista de espera, los eventos, los anuncios, el '
     'muro de la comunidad, el inventario de herramientas, el '
     'registro de cosechas, la configuraci\u00f3n de las transferencias y'
     ' el cobro en persona con Tap to Pay. Garden Pro a\u00f1ade encima '
     'las herramientas de gesti\u00f3n.',
     None),
    ('garden-pro',
     '\u00bfCu\u00e1nto cuesta Garden Pro y qu\u00e9 a\u00f1ade?',
     '{{PRO_MONTHLY}} al mes o {{PRO_YEARLY}} al a\u00f1o, con una prueba'
     ' gratis de {{TRIAL_DAYS}} d\u00edas que no pide tarjeta. Pro a\u00f1ade '
     'las cuotas (generarlas, hacer su seguimiento, recordatorios y '
     'exportaciones), los gastos y el resumen financiero, los '
     'informes para financiadores, los mensajes directos y masivos, '
     'los correos de anuncios, el muro de fotos, los turnos de '
     'voluntariado, el pr\u00e9stamo de herramientas con etiquetas QR y '
     'el dise\u00f1ador del plano.',
     None),
    ('do-gardeners-pay',
     '\u00bfLos hortelanos pagan algo por usar YardHarvest?',
     'No. Los hortelanos nunca pagan nada a YardHarvest. Si tu '
     'huerto cobra cuotas por las parcelas, ese dinero es para tu '
     'huerto.',
     None),
    ('contract-and-canceling',
     '\u00bfHay contrato? \u00bfQu\u00e9 pasa si cancelamos Pro?',
     'No hay contrato: Pro es mensual o anual y puedes cancelar '
     'cuando quieras. Sigue activo hasta el final del periodo que ya'
     ' has pagado y no se borra nada. Los registros de cuotas, las '
     'fotos, los turnos y los informes se conservan, en modo de solo'
     ' lectura hasta que vuelvas, y todo lo gratuito sigue '
     'funcionando igual.',
     None),
    ('several-gardens',
     'Llevamos varios huertos. \u00bfHay un plan para nosotros?',
     'S\u00ed. Las redes de huertos y los programas municipales tienen '
     'precios por volumen por huerto, facturaci\u00f3n centralizada e '
     'informes de impacto de toda la red. Reserva una llamada y '
     'preparamos un plan.',
     None),
    ('where-does-the-money-go',
     '\u00bfA d\u00f3nde va el dinero de las cuotas?',
     'Directamente a tu huerto. Los pagos llegan a una cuenta de '
     'Stripe a nombre de tu huerto, y Stripe los transfiere a tu '
     'banco. YardHarvest nunca guarda el dinero de tu huerto.',
     None),
    ('platform-fee',
     '\u00bfYardHarvest se queda con una parte de lo que cobramos?',
     'No. YardHarvest no se queda con nada de las cuotas, los cobros'
     ' en persona ni las ventas. Los pagos con tarjeta s\u00ed tienen '
     'comisiones de procesamiento de Stripe, y la pesta\u00f1a \u00abFinanzas\u00bb'
     ' muestra, para cada pago, cu\u00e1nto se cobr\u00f3, las comisiones y '
     'cu\u00e1nto lleg\u00f3 a tu banco.',
     'YardHarvest se queda con el {{DUES_FEE}} % de cada pago que '
     'cobra tu huerto. Los pagos con tarjeta tambi\u00e9n tienen '
     'comisiones de procesamiento de Stripe. La pesta\u00f1a \u00abFinanzas\u00bb '
     'muestra, para cada pago, cu\u00e1nto se cobr\u00f3, las comisiones y '
     'cu\u00e1nto lleg\u00f3 a tu banco.'),
    ('how-members-pay',
     '\u00bfC\u00f3mo pueden pagar sus cuotas los integrantes?',
     'En l\u00ednea con tarjeta o transferencia bancaria, desde la p\u00e1gina'
     ' del huerto; en persona con Tap to Pay en iPhone; o en '
     'efectivo o con cheque, que quien organiza registra a mano.',
     None),
    ('collect-online',
     '\u00bfQu\u00e9 necesitamos para cobrar cuotas en l\u00ednea?',
     'Una cuenta para recibir transferencias. Conectas tu huerto a '
     'Stripe desde \u00abFacturaci\u00f3n y transferencias\u00bb, sin salir de '
     'YardHarvest. Stripe te pregunta qui\u00e9n eres y a d\u00f3nde enviar el'
     ' dinero, algo que la ley exige a cualquiera que reciba pagos. '
     'Mientras no est\u00e9 lista, los integrantes no pueden pagar en '
     'l\u00ednea.',
     None),
    ('get-a-plot',
     '\u00bfC\u00f3mo encuentro un huerto y consigo una parcela?',
     'Explora los huertos, abre el que te quede cerca y reserva una '
     'parcela disponible o ap\u00fantate a su lista de espera. Quien '
     'organiza aprueba las solicitudes y te avisa en cualquier caso.',
     None),
    ('pay-my-dues',
     '\u00bfC\u00f3mo pago mis cuotas?',
     'Si tu huerto cobra cuotas, ver\u00e1s lo que debes en la p\u00e1gina del'
     ' huerto y podr\u00e1s pagar con tarjeta o transferencia bancaria. '
     'Quien organiza tambi\u00e9n puede cobrarte en persona o registrar '
     'un pago en efectivo por ti.',
     None),
    ('log-my-harvest',
     '\u00bfPara qu\u00e9 registrar mi cosecha?',
     'La cosecha total de tu huerto es lo que sus organizadores '
     'muestran a los financiadores y al ayuntamiento para que el '
     'huerto siga adelante. Lleva unos segundos: qu\u00e9 has cosechado y'
     ' m\u00e1s o menos cu\u00e1nto pesa.',
     None),
    ('do-you-sell-my-data',
     '\u00bfVenden mis datos?',
     'No. No vendemos informaci\u00f3n personal y solo la compartimos, '
     'por contrato, con los servicios que hacen funcionar '
     'YardHarvest, como el alojamiento, los pagos y el correo. Tu '
     'nombre visible, tu foto de perfil y lo que publiques se pueden'
     ' ver en la p\u00e1gina p\u00fablica de tu huerto.',
     None),
    ('export-our-data',
     '\u00bfPodemos exportar los datos de nuestro huerto?',
     'S\u00ed. Exportar la lista de integrantes es gratis. Con Garden Pro'
     ' tambi\u00e9n puedes exportar las cuotas, los registros financieros'
     ' y los informes para financiadores en CSV.',
     None),
    ('more-help',
     '\u00bfD\u00f3nde consigo m\u00e1s ayuda?',
     'El centro de ayuda explica paso a paso la configuraci\u00f3n, el '
     'dinero y la soluci\u00f3n de problemas. Si prefieres hablarlo, '
     'reserva una llamada.',
     None),
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

# --- Spanish --------------------------------------------------------------
#
# A Spanish title on an English page is worse than an English one: it invites
# Google to serve that URL to a Spanish searcher who then cannot read it. So
# copy lives here only for paths whose CONTENT is Spanish, and the gate below
# is what decides. Everything else keeps serving English meta under /es/,
# which is honest about what the reader will find.
# og:locale wants a full locale. The language code alone is ignored.
OG_LOCALES = {'en': 'en_US', 'es': 'es_ES'}

# MIRRORS app.seoDefaultTitle / app.seoDefaultDescription in the Spanish
# catalog, which is what the client renders on a Spanish page.
ES_DEFAULT_TITLE = 'YardHarvest \u2014 Plataforma de gesti\u00f3n de huertos comunitarios'
ES_DEFAULT_DESC = (
    'YardHarvest es la plataforma integral para huertos '
    'comunitarios: gestiona parcelas, integrantes, cuotas, eventos '
    'y voluntariado, y haz crecer una red local de huertos llena de'
    ' vida.')

# MIRRORS the client catalog - frontend/src/i18n/locales/es/common.json.
# tests/test_seo_es.py asserts the two agree, so a reworded page cannot leave
# the crawler reading the old sentence.
ES_PAGE_META = {
    '/': (None, ES_DEFAULT_DESC),
    '/faq': ('Preguntas frecuentes',
             'Respuestas sobre YardHarvest: cu\u00e1nto cuesta, qu\u00e9 a\u00f1ade Garden '
             'Pro, a d\u00f3nde va el dinero de las cuotas, c\u00f3mo conseguir una '
             'parcela y qu\u00e9 pasa con tus datos.'),
    '/about': ('Acerca de',
               'La historia y la misi\u00f3n de YardHarvest: hacer que los huertos '
               'comunitarios sean m\u00e1s f\u00e1ciles de llevar y ayudar a que las '
               'redes locales de huertos prosperen.'),
    '/pricing': ('Precios',
                 'Precios simples y transparentes para huertos comunitarios. '
                 'Empieza gratis y p\u00e1sate a Garden Pro para tener mensajes, '
                 'finanzas, fotos y m\u00e1s.'),
    '/gardens': ('Huertos comunitarios',
                 'Explora los huertos comunitarios cerca de ti en YardHarvest. '
                 'Encuentra una parcela, \u00fanete a un huerto y cultiva junto a tus'
                 ' vecinos.'),
    '/planting-calendar': ('Calendario de siembra',
                           'Un calendario de siembra adaptado a tu ubicaci\u00f3n: cu\u00e1ndo '
                           'sembrar, trasplantar y cosechar cada cultivo seg\u00fan las fechas '
                           'de helada y la zona de cultivo de tu localidad.'),
    '/harvest-forecast': ('Previsi\u00f3n de cosecha',
                          'Mira qu\u00e9 est\u00e1n cultivando los huertos locales y cu\u00e1ndo estar\u00e1n'
                          ' listos para cosechar los cultivos de tu zona.'),
    '/groups': ('Grupos de barrio',
                '\u00danete a grupos de hortelanos de tu barrio en YardHarvest.'),
    '/help': ('Ayuda de YardHarvest',
              'C\u00f3mo llevar un huerto comunitario en YardHarvest: '
              'configuraci\u00f3n, parcelas, integrantes, cuotas, transferencias '
              'de Stripe, Tap to Pay y soluci\u00f3n de problemas.'),
    '/about/guide': ('La Gu\u00eda del Huerto Comunitario',
                     'Una gu\u00eda cercana y pr\u00e1ctica para crear y llevar adelante un '
                     'huerto comunitario: el terreno, la financiaci\u00f3n, la '
                     'construcci\u00f3n, la organizaci\u00f3n de los vecinos y c\u00f3mo mantenerlo'
                     ' floreciente.'),
}

# The help centre and the garden guide in Spanish. MIRRORS the Spanish data
# modules (frontend/src/data/helpCenter.es.js, gardenGuide.es.js) the way
# HELP_META / GUIDE_META mirror the English ones; tests/test_seo_es.py reads
# those modules through Node and asserts every entry.
ES_HELP_TITLE = 'Ayuda de YardHarvest'
ES_HELP_META = {
    'create-a-garden': (
        'Crea tu huerto',
        'C\u00f3mo crear un huerto comunitario en YardHarvest: los datos que'
        ' importan, lo que ven los integrantes y lo que puedes cambiar '
        'despu\u00e9s.'),
    'plots-and-layout': (
        'Las parcelas y el dise\u00f1ador del huerto',
        'A\u00f1ade las parcelas del huerto, as\u00edgnalas a los integrantes y '
        'dibuja el plano del huerto en una cuadr\u00edcula para que cada uno'
        ' vea cu\u00e1l es la suya.'),
    'members-and-roles': (
        'Integrantes y funciones',
        'Aprueba integrantes, exporta tu lista y entiende exactamente '
        'qu\u00e9 permisos da cada funci\u00f3n del huerto en YardHarvest.'),
    'events-and-shifts': (
        'Eventos y turnos de voluntariado',
        'Crea eventos del huerto con confirmaci\u00f3n de asistencia y '
        'organiza turnos de voluntariado con inscripciones, '
        'recordatorios y registro de asistencia.'),
    'resources-and-tools': (
        'Herramientas y recursos compartidos',
        'Lleva el control de las herramientas compartidas del huerto, '
        'imprime etiquetas QR y registra pr\u00e9stamos y devoluciones para '
        'saber qui\u00e9n tiene qu\u00e9.'),
    'communication': (
        'Anuncios, mensajes y el muro de la comunidad',
        'Cu\u00e1ndo usar anuncios, mensajes directos, el muro de la '
        'comunidad y los correos de anuncios para llegar a los '
        'integrantes de tu huerto.'),
    'photos-and-impact': (
        'Fotos, registro de cosecha e impacto',
        'Publica fotos del huerto, registra el peso de la cosecha y '
        'convierte los datos de una temporada en un informe de impacto '
        'listo para financiadores.'),
    'money-overview': (
        'C\u00f3mo se mueve el dinero en YardHarvest',
        'A d\u00f3nde van de verdad las cuotas y las ventas del huerto, '
        'qui\u00e9n tiene el dinero y por qu\u00e9 YardHarvest nunca se interpone'
        ' entre t\u00fa y tus fondos.'),
    'stripe-setup': (
        'Configura las transferencias con Stripe',
        'El registro en Stripe Connect paso a paso para un huerto '
        'comunitario: qu\u00e9 te pide Stripe, cu\u00e1nto tarda y c\u00f3mo saber que'
        ' ha funcionado.'),
    'dues': (
        'Generar y cobrar las cuotas',
        'Genera las cuotas de la temporada para quienes tienen parcela,'
        ' cobra en l\u00ednea o en persona, registra el efectivo y controla '
        'lo que queda pendiente.'),
    'tap-to-pay': (
        'Tap to Pay en la entrada',
        'Usa Tap to Pay en iPhone desde la app de YardHarvest para '
        'cobrar cuotas y hacer ventas de plantas en persona, sin lector'
        ' de tarjetas.'),
    'money-feed': (
        'C\u00f3mo leer tu actividad de Stripe',
        'Entiende la subpesta\u00f1a Stripe de Finanzas: el dinero cobrado '
        'con tarjeta, las comisiones de la plataforma y de Stripe, los '
        'reembolsos, los contracargos y las transferencias a tu banco.'),
    'stripe-pitfalls': (
        'Problemas con Stripe que conviene conocer',
        'Problemas comunes de Stripe en huertos comunitarios: '
        'transferencias sin configurar, pagos en persona inactivos, '
        'cuentas restringidas y transferencias que no aparecen.'),
    'free-and-pro': (
        'Qu\u00e9 es gratis y qu\u00e9 a\u00f1ade Garden Pro',
        'Un desglose preciso de qu\u00e9 funciones de YardHarvest son gratis'
        ' para todos los huertos comunitarios y cu\u00e1les requieren Garden'
        ' Pro.'),
    'trial-and-billing': (
        'Prueba, suscripci\u00f3n y cancelaci\u00f3n',
        'Empieza una prueba de Garden Pro, suscr\u00edbete, cambia de plan o'
        ' cancela, y qu\u00e9 pasa con tus datos en cada caso.'),
    'for-gardeners': (
        'Para hortelanos',
        'C\u00f3mo unirte a un huerto comunitario en YardHarvest, pedir una '
        'parcela, pagar tus cuotas y registrar tu cosecha.'),
    'common-problems': (
        'Problemas comunes',
        'Soluci\u00f3n de problemas en YardHarvest: correos que no llegan, '
        'integrantes que no ven funciones, pesta\u00f1as Pro bloqueadas y '
        'cosas que parecen estar mal.'),
}

ES_GUIDE_TITLE = 'La Gu\u00eda del Huerto Comunitario'
ES_GUIDE_META = {
    'getting-started': (
        'Primeros pasos',
        'C\u00f3mo crear un huerto comunitario: mide el inter\u00e9s del barrio, '
        'forma un equipo fundador y define una visi\u00f3n compartida antes '
        'de tocar una pala.'),
    'finding-land': (
        'Buscar terreno y planificar el espacio',
        'C\u00f3mo encontrar terreno para un huerto comunitario, evaluar el '
        'sol, el agua y el suelo, y conseguir un arrendamiento o '
        'acuerdo que proteja el huerto.'),
    'funding-and-budget': (
        'Financiaci\u00f3n y tu primer presupuesto',
        'Costes iniciales de un huerto comunitario, presupuestos '
        'realistas, cuotas de parcela, subvenciones, ideas para '
        'recaudar fondos y el patrocinio fiscal, explicados de forma '
        'sencilla.'),
    'building-the-garden': (
        'Construir el huerto',
        'C\u00f3mo dise\u00f1ar la distribuci\u00f3n de un huerto comunitario, '
        'construir bancales elevados, instalar el agua y organizar una '
        'jornada de construcci\u00f3n con voluntarios que la gente disfrute.'),
    'organizing-people': (
        'Organizar a las personas',
        'C\u00f3mo organizar a los integrantes de un huerto comunitario: '
        'acuerdos de parcela, listas de espera, horas de voluntariado, '
        'estructura de liderazgo y c\u00f3mo evitar que se agote quien '
        'coordina.'),
    'running-the-season': (
        'Gestionar la temporada',
        'Un ritmo, estaci\u00f3n por estaci\u00f3n, para llevar un huerto '
        'comunitario: renovaciones, arranque de primavera, '
        'mantenimiento de verano, eventos y preparaci\u00f3n para el '
        'invierno.'),
    'harvest-and-impact': (
        'Cosecha e impacto',
        'C\u00f3mo registrar la cosecha y el impacto de un huerto '
        'comunitario: programas de donaci\u00f3n, registros sencillos e '
        'informes que convencen a financiadores y ayuntamientos.'),
    'troubleshooting': (
        'Resolver problemas',
        'Problemas comunes de los huertos comunitarios y c\u00f3mo '
        'resolverlos: robos y vandalismo, parcelas abandonadas, '
        'conflictos entre integrantes, plagas y cambios de liderazgo.'),
}

# A crop guide's title names the crop, and the crop's name is the planting
# category (the URL segment). MIRRORS the crops.* catalog keys through the map
# in frontend/src/data/plantingCrops.js, and the cropGuide.seoTitle /
# seoDescription templates.
ES_CROP_NAMES = {
    'Tomatoes': 'Tomates',
    'Peppers (Hot)': 'Pimientos picantes',
    'Peppers (Sweet)': 'Pimientos dulces',
    'Cucumbers': 'Pepinos',
    'Squash (Summer)': 'Calabac\u00edn',
    'Squash (Winter)': 'Calabaza (de invierno)',
    'Herbs': 'Hierbas',
    'Leafy Greens': 'Hortalizas de hoja',
    'Root Vegetables': 'Ra\u00edces y tub\u00e9rculos',
    'Beans': 'Jud\u00edas',
    'Corn': 'Ma\u00edz',
    'Berries': 'Frutos rojos',
    'Melons': 'Melones',
    'Peas': 'Guisantes',
    'Onions/Garlic': 'Cebollas y ajos',
    'Brassicas': 'Cruc\u00edferas',
    'Other': 'Otros',
}
ES_CROP_GUIDE_TITLE = 'Gu\u00eda de cultivo: {crop}'
ES_CROP_GUIDE_DESC = ('Cu\u00e1ndo y c\u00f3mo sembrar {crop}: periodos de siembra y '
                      'trasplante, sensibilidad a las heladas, plantas compa\u00f1eras y '
                      'momento de cosecha para tu zona.')

ES_NOINDEX_META = {
    '/login': ('Iniciar sesi\u00f3n', 'Inicia sesi\u00f3n en tu cuenta de YardHarvest.'),
    '/register': ('Crea tu cuenta',
                  'Crea una cuenta gratuita de YardHarvest para unirte a un '
                  'huerto comunitario o administrar el tuyo.'),
    '/forgot-password': ('Restablece tu contrase\u00f1a',
                         'Pide un enlace para restablecer tu contrase\u00f1a de '
                         'YardHarvest.'),
    '/reset-password': ('Elige una contrase\u00f1a nueva',
                        'Elige una contrase\u00f1a nueva para YardHarvest.'),
    '/verify-email-change': ('Verifica tu correo',
                             'Confirma el cambio de correo de tu cuenta de '
                             'YardHarvest.'),
}

# Paths whose CONTENT is translated. Spanish meta, hreflang and the Spanish
# sitemap entry are emitted only for these.
#
# Still NOT here: Terms and Privacy (the authoritative version of legal copy
# should not be a translation), and /book, whose heading, intro and meeting
# types are the host's own English and whose call is held in English. Add a
# path here in the same commit that translates its page - not before.
TRANSLATED_PATHS = frozenset((
    '/', '/about', '/pricing', '/faq', '/gardens', '/login', '/register', '/forgot-password', '/reset-password',
    '/verify-email-change', '/planting-calendar', '/harvest-forecast',
    '/groups', '/help', '/about/guide',
))
# Pages under these share their parent's translated chrome. A garden's and a
# group's own words are the organizer's, which no catalog can translate; the
# help articles, guide chapters and crop guides are translated in full.
TRANSLATED_PREFIXES = ('/gardens/', '/groups/', '/help/', '/about/guide/',
                       '/planting-guide/')


def path_is_translated(path):
    """Is the CONTENT at *path* available in every offered language?"""
    path = (path or '/').rstrip('/') or '/'
    if path in TRANSLATED_PATHS:
        return True
    return any(path.startswith(p) for p in TRANSLATED_PREFIXES)


_index_cache = {}


def _spanish(path, lang):
    """Should this path's copy be Spanish? Only if the content is."""
    return lang == 'es' and path_is_translated(path)


def _localized(en_map, es_map, path, lang):
    """The Spanish entry when there is one and the page is translated."""
    if _spanish(path, lang) and path in es_map:
        return es_map[path]
    return en_map[path]


def _site_base():
    from flask import current_app
    return (current_app.config.get('SITE_URL') or 'https://www.yardharvest.app').rstrip('/')


def _org_jsonld(base, es=False):
    return {
        '@context': 'https://schema.org', '@type': 'Organization',
        'name': SITE_NAME, 'url': base, 'logo': f'{base}/sunflower.svg',
        'email': 'james@yardharvest.app',
        'description': ES_DEFAULT_DESC if es else DEFAULT_DESC,
    }


def _software_jsonld(base, es=False):
    # Search engines and AI crawlers read these offers. They must be the prices
    # the admin console actually charges — this used to read config.py and so
    # advertised a price the checkout did not honor.
    from app.pricing import garden_pro_pricing
    pro = garden_pro_pricing()
    monthly, yearly, trial = pro['monthly'], pro['yearly'], pro['trial_days']
    return {
        '@context': 'https://schema.org', '@type': 'SoftwareApplication',
        'name': SITE_NAME, 'applicationCategory': 'BusinessApplication',
        'operatingSystem': 'Web',
        'url': base, 'description': ES_DEFAULT_DESC if es else DEFAULT_DESC,
        'offers': [
            {'@type': 'Offer',
             'name': (f'Garden Pro (mensual, prueba gratis de {trial} días)' if es
                      else f'Garden Pro (monthly, {trial}-day free trial)'),
             'price': f'{monthly:.2f}', 'priceCurrency': 'USD'},
            {'@type': 'Offer',
             'name': 'Garden Pro (anual)' if es else 'Garden Pro (annual)',
             'price': f'{yearly:.2f}', 'priceCurrency': 'USD'},
        ],
    }


def _money(value):
    """$12 / $12.50 - the same shape the FAQ page prints."""
    value = float(value)
    return f'${int(value)}' if value == int(value) else f'${value:.2f}'


def _faq_page_jsonld(es=False):
    """FAQPage data for /faq, filled exactly as the page fills it: live Garden
    Pro prices, and the platform-fee answer that matches the fee actually set,
    so a crawler is never told "no cut" while one is being taken."""
    from app.pricing import dues_fee_percent, garden_pro_pricing
    pro = garden_pro_pricing()
    fee = dues_fee_percent()
    fee_text = ('%.2f' % fee).rstrip('0').rstrip('.')

    def fill(text):
        return (text.replace('{{PRO_MONTHLY}}', _money(pro['monthly']))
                .replace('{{PRO_YEARLY}}', _money(pro['yearly']))
                .replace('{{TRIAL_DAYS}}', str(pro['trial_days']))
                .replace('{{DUES_FEE}}', fee_text))

    return {
        '@context': 'https://schema.org', '@type': 'FAQPage',
        'mainEntity': [{
            '@type': 'Question', 'name': q,
            'acceptedAnswer': {'@type': 'Answer',
                               'text': fill(a_fee if (fee > 0 and a_fee) else a)},
        } for _id, q, a, a_fee in (ES_FAQ_ITEMS if es else FAQ_ITEMS)],
    }


def _faq_jsonld(es=False):
    # Structured data must match the visible FAQ, which is in the page's
    # language.
    return {
        '@context': 'https://schema.org', '@type': 'FAQPage',
        'mainEntity': [{
            '@type': 'Question', 'name': q,
            'acceptedAnswer': {'@type': 'Answer', 'text': a},
        } for q, a in (ES_PRICING_FAQS if es else PRICING_FAQS)],
    }


def _article(base, path, lang, title, desc, series, hub):
    """Meta + Article JSON-LD for a help article or guide chapter.

    The structured data names the page the reader is actually on, so a
    Spanish chapter's url and series point at the /es/ pages and say so.
    """
    pre = '/' + lang if _spanish(path, lang) else ''
    article = {
        '@context': 'https://schema.org', '@type': 'Article',
        'headline': f'{title} — {series}',
        'description': desc,
        'url': f'{base}{pre}{path}',
        'inLanguage': lang if pre else 'en',
        'author': {'@type': 'Organization', 'name': SITE_NAME},
        'publisher': {'@type': 'Organization', 'name': SITE_NAME,
                      'url': base},
        'isPartOf': {'@type': 'CreativeWorkSeries', 'name': series,
                     'url': f'{base}{pre}{hub}'},
    }
    return f'{title} — {series}', desc, False, [article], None


def _meta_for_path(path, lang=None):
    """Resolve (title, description, noindex, jsonld_list, canonical_path) for
    a request path.

    *lang* selects the copy, but only where the page's content is actually in
    that language - see path_is_translated. Anywhere else the English copy is
    returned deliberately, because it describes what the reader will find. ``canonical_path`` overrides the request path in the
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
        title, desc = _localized(NOINDEX_META, ES_NOINDEX_META, path, lang)
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
                # The organizer's own description wins in both languages -
                # it is their words about their garden, not our copy.
                fallback = (
                    f'{g.name} es un huerto comunitario'
                    + (f' en {loc}' if loc else '') + ' en YardHarvest.'
                    if _spanish(path, lang) else
                    f'{g.name} is a community garden'
                    + (f' in {loc}' if loc else '') + ' on YardHarvest.')
                desc = (g.description or '').strip()[:280] or fallback
                canonical = (f'/gardens/{g.public_id}' if g.public_id else None)
                return (f'{g.name}' + (f' ({loc})' if loc else ''),
                        desc, False, [], canonical)
        except Exception:  # DB hiccup — fall through to defaults, never 500
            pass

    if path.startswith('/planting-guide/'):
        # Everything after the prefix, not the last segment: the category
        # "Onions/Garlic" arrives with its slash decoded, and rsplit used to
        # title that guide "Garlic".
        crop = unquote(path[len('/planting-guide/'):]).replace('-', ' ')
        crop_t = crop.strip().title()[:60]
        if crop_t and _spanish(path, lang):
            es_name = next((v for k, v in ES_CROP_NAMES.items()
                            if k.lower() == crop.strip().lower()), None)
            if es_name:
                return (ES_CROP_GUIDE_TITLE.format(crop=es_name),
                        ES_CROP_GUIDE_DESC.format(crop=es_name.lower()),
                        False, [], None)
        if crop_t:
            return (f'{crop_t} Growing Guide',
                    f'When and how to plant {crop_t.lower()}: sowing and '
                    'transplant windows, frost sensitivity, companions, and '
                    'harvest timing for your zone.', False, [], None)

    if path.startswith('/help/'):
        slug = path[len('/help/'):].strip('/')
        es = _spanish(path, lang)
        meta, series = ((ES_HELP_META, ES_HELP_TITLE) if es
                        else (HELP_META, HELP_TITLE))
        if slug in meta:
            return _article(base, path, lang, *meta[slug], series, '/help')
        # Unknown article: the SPA redirects to the hub, so point crawlers there.
        title, desc = _localized(PAGE_META, ES_PAGE_META, '/help', lang)
        return title, desc, False, [], '/help'

    if path.startswith('/about/guide/'):
        slug = path.rsplit('/', 1)[-1]
        es = _spanish(path, lang)
        meta, series = ((ES_GUIDE_META, ES_GUIDE_TITLE) if es
                        else (GUIDE_META, GUIDE_TITLE))
        if slug in meta:
            return _article(base, path, lang, *meta[slug], series, '/about/guide')
        # Unknown chapter — the SPA redirects to the hub; meta mirrors that.
        title, desc = _localized(PAGE_META, ES_PAGE_META, '/about/guide', lang)
        return title, desc, False, [], '/about/guide'

    if path in PAGE_META:
        title, desc = _localized(PAGE_META, ES_PAGE_META, path, lang)
        es = _spanish(path, lang)
        jsonld = []
        if path == '/':
            jsonld = [_org_jsonld(base, es), _software_jsonld(base, es)]
        elif path == '/pricing':
            jsonld = [_software_jsonld(base, es), _faq_jsonld(es)]
        elif path == '/faq':
            jsonld = [_faq_page_jsonld(es)]
        elif path == '/book':
            jsonld = [_org_jsonld(base, es)]
        return title, desc, False, jsonld, None

    return (None, ES_DEFAULT_DESC if _spanish(path, lang) else DEFAULT_DESC,
            False, [], None)


def _build_head(path):
    """Compose the injected head block for *path* (all tags data-ssr tagged)."""
    from app import i18n

    base = _site_base()
    # The meta map is keyed by the English URLs. A Spanish page is the same
    # page — /es/pricing is pricing — so look it up by the unprefixed path
    # rather than falling through to the generic site description.
    lang = i18n.locale_from_path(path) or i18n.DEFAULT
    lookup = i18n.strip_prefix(path)
    title, desc, noindex, jsonld, canonical_path = _meta_for_path(lookup, lang)
    default_title = ES_DEFAULT_TITLE if _spanish(lookup, lang) else DEFAULT_TITLE
    full_title = f'{title} — {SITE_NAME}' if title else default_title
    # Each language canonicalizes to its OWN URL. Pointing /es/pricing at the
    # English canonical would tell Google the Spanish page is a duplicate and
    # drop it from the index — the exact opposite of why it exists.
    canonical_path = canonical_path or (lookup or '/').rstrip('/') or '/'

    def _url(code):
        """Absolute URL for this page in *code*. The root is the awkward case:
        English keeps its trailing slash (it always had one) and Spanish is
        /es rather than /es/."""
        pre = '' if code == i18n.DEFAULT else '/' + code
        if canonical_path == '/':
            return base + (pre or '/')
        return base + pre + canonical_path

    canonical = _url(lang)
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
        # Facebook and the rest want a full locale, not a bare language code.
        f'<meta property="og:locale" content="{OG_LOCALES.get(lang, OG_LOCALES[i18n.DEFAULT])}" data-ssr="1" />',
    ]
    # hreflang, but only once Spanish is actually offered. Advertising an
    # alternate that is still half-English is worse than advertising nothing:
    # it invites Google to serve the Spanish URL to Spanish searchers before
    # there is Spanish on it.
    from app import i18n as _i18n
    from flask import current_app
    try:
        offered = _i18n.enabled_languages()
    except Exception:
        offered = [_i18n.DEFAULT]
    # Per path, not site-wide. Half the site is still English, and an
    # alternate that points at an English page is how a Spanish searcher gets
    # served something they cannot read.
    if len(offered) > 1 and not noindex and path_is_translated(canonical_path):
        for code in offered:
            parts.append(f'<link rel="alternate" hreflang="{code}" '
                         f'href="{escape(_url(code))}" data-ssr="1" />')
        parts.append(f'<link rel="alternate" hreflang="x-default" '
                     f'href="{escape(_url(_i18n.DEFAULT))}" data-ssr="1" />')

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

        # No word-boundary escapes in this pattern on purpose: it is bounded
        # by the tag's own '>' already, and an escape here once survived an
        # edit as a literal control byte, which silently matched nothing. The
        # client also sets documentElement.lang, so the browser looked right
        # while the SERVED html — all a no-JS crawler sees, and the whole
        # reason this module exists — still said English.
        # Declare the document's language. A Spanish page still claiming
        # lang="en" tells a screen reader to pronounce it with English
        # phonetics and tells Chrome to offer to translate it into the
        # language it is already in.
        from app import i18n
        lang = i18n.locale_from_path(path) or i18n.DEFAULT
        if lang != i18n.DEFAULT:
            out = re.sub(r'<html[^>]*lang="[^"]*"', '<html lang="%s"' % lang,
                         out, count=1)
        return Response(out, mimetype='text/html')
    except Exception:
        return send_from_directory(spa_dir, 'index.html')
