// The YardHarvest Help Center — content for /help.
//
// Product documentation, as distinct from /about/guide, which is advice about
// starting a community garden in the real world. This file answers "how do I
// do X in YardHarvest", and says plainly where the software will bite.
//
// Plain strings, no JSX — rendered by pages/Help.jsx.
//
// PRICING IS NEVER HARDCODED. Write {{PRO_MONTHLY}}, {{PRO_YEARLY}} or
// {{TRIAL_DAYS}} and Help.jsx substitutes the live values from
// /api/admin/public-pricing. The column defaults in models.py are NOT the real
// prices, and a page that hardcodes them has been wrong here before.
//
// KEEP IN SYNC: slugs/titles/descriptions are mirrored in app/seo.py
// (HELP_META) for server-side crawler meta and the sitemap.

export const HELP_TITLE = 'YardHarvest Help';
export const HELP_INTRO =
  'How to run your garden on YardHarvest — setting up, collecting money, and ' +
  'what to do when something looks wrong. Written for the organizer doing ' +
  'this in the evenings, not for a support queue.';

export const CATEGORIES = [
  {
    key: 'start',
    title: 'Getting started',
    icon: 'bi-flag',
    blurb: 'Create a garden, add plots, and get your first members in.',
  },
  {
    key: 'running',
    title: 'Running your garden',
    icon: 'bi-sun',
    blurb: 'Events, shifts, tools, photos and keeping everyone in the loop.',
  },
  {
    key: 'money',
    title: 'Money & Stripe',
    icon: 'bi-cash-stack',
    blurb: 'Payout setup, dues, Tap to Pay, and where the money actually goes.',
  },
  {
    key: 'plans',
    title: 'Plans & billing',
    icon: 'bi-star',
    blurb: 'What is free, what Garden Pro adds, and how billing works.',
  },
  {
    key: 'gardeners',
    title: 'For gardeners',
    icon: 'bi-person',
    blurb: 'Claiming a plot, paying dues, and logging what you grew.',
  },
  {
    key: 'trouble',
    title: 'When something is wrong',
    icon: 'bi-life-preserver',
    blurb: 'The failures people actually hit, and how to clear them.',
  },
];

export const ARTICLES = [
  // ---------------------------------------------------------------- start ---
  {
    slug: 'create-a-garden',
    category: 'start',
    title: 'Create your garden',
    tagline: 'The five minutes that decide how everything else reads.',
    description:
      'How to create a community garden on YardHarvest: the details that '
      + 'matter, what members see, and what you can change later.',
    keywords: 'create new garden setup start signup register',
    sections: [
      {
        h: 'Make the garden',
        p: [
          'Sign up, then go to Create a Garden. You need a name and a location; everything else can wait. The garden goes live immediately with its own public page, which is the link you will share with neighbors.',
        ],
        steps: [
          'Register an account, choosing the organizer role.',
          'Open Create a Garden from the main menu.',
          'Fill in the name, address, and a short description.',
          'Save. You land in the admin portal for the new garden.',
        ],
      },
      {
        h: 'What members see',
        p: [
          'Your public page shows the description, address, rules, season dates, plot availability, and any photos you have posted. It is indexed by search engines, so it doubles as the garden\'s website. Write the description for a stranger who found you on a map, not for people who already know you.',
          'The address is used for the map pin and for weather alerts. If your garden is behind a building or has no street number, put the nearest usable address in and explain the approach in the description.',
        ],
      },
      {
        h: 'Set the rules early',
        p: [
          'Rules live in Settings and appear on the public page. Write them before the first plot is claimed. Once someone has a bed, a new rule feels like a rule aimed at them.',
        ],
        tip: 'Everything here is editable later — name, description, rules, season dates, plot count, layout. Nothing you choose today locks you in.',
      },
    ],
  },
  {
    slug: 'plots-and-layout',
    category: 'start',
    title: 'Plots and the layout designer',
    tagline: 'Beds on a grid, and who is in which one.',
    description:
      'Add garden plots, assign them to members, and draw your garden layout '
      + 'on a grid so members can see which bed is theirs.',
    keywords: 'plots beds layout grid assign reserve designer',
    sections: [
      {
        h: 'Add your plots',
        p: [
          'Go to the Plots tab and add beds. A plot needs a number or name; size and notes are optional but help people choose. Plots start as available, and every available plot shows on the public page as claimable.',
        ],
        steps: [
          'Admin portal, Plots tab.',
          'Add each bed, or add them in bulk if they are numbered simply.',
          'Mark any bed you are keeping back as unavailable so nobody claims it.',
        ],
      },
      {
        h: 'How a plot gets claimed',
        p: [
          'A member reserves a plot from the public page. That does not assign it — it creates a request you review. Reservations waiting on you appear in the Plots tab, and in the iOS app as the Reviews tile on your dashboard.',
          'Approve and the plot is theirs. Decline and it goes back to available; the member is notified either way.',
        ],
      },
      {
        h: 'The waitlist',
        p: [
          'When nothing is available, people join the waitlist instead. Approving someone from the waitlist takes them off it and lets them claim a bed. The waitlist is the number worth watching: it is the honest measure of demand, and it is what a funder or a city parks department will ask you for.',
        ],
      },
      {
        h: 'The layout designer',
        p: [
          'The layout designer draws your garden on a grid so members can see where their bed physically is, alongside paths, sheds, water and compost. You edit a draft and publish it when it looks right, so a half-finished layout is never visible to members.',
        ],
        pro: true,
      },
    ],
  },
  {
    slug: 'members-and-roles',
    category: 'start',
    title: 'Members and roles',
    tagline: 'Who is in your garden, and what a role actually does.',
    description:
      'Approve members, export your roster, and understand exactly which '
      + 'garden roles grant permissions in YardHarvest.',
    keywords: 'members roster roles organizer treasurer permissions remove export',
    sections: [
      {
        h: 'Your roster',
        p: [
          'The Members tab lists everyone attached to the garden, with their plot and role. You can export the roster as CSV — useful for a mailing list, an insurance form, or a grant application.',
        ],
      },
      {
        h: 'What each role can do',
        p: [
          'Roles grant real access to the admin portal. Someone you make treasurer can log in and do the books without you; a volunteer lead can run the shift rota without being able to see the money.',
        ],
        list: [
          'Organizer - the owner. Full control, including roles, billing and payout setup. One per garden.',
          'Co-organizer - runs the garden: plots, members, events, shifts, resources, dues and reports.',
          'Treasurer - dues, expenses and reports. No access to plots, members or settings.',
          'Volunteer lead - events and volunteer shifts. No access to money or members.',
          'Member - no administrative access.',
        ],
      },
      {
        h: 'Two things only the owner can do',
        p: [
          'Changing roles, and anything to do with billing or payouts. Both stay with the organizer no matter who else you appoint.',
          'That is deliberate. Whoever can change roles can grant every other permission, and whoever controls payout setup decides which bank account the money lands in. A co-organizer can collect and spend; they cannot redirect.',
        ],
        tip: 'Handing the garden over entirely - a founder stepping down - is an ownership transfer rather than a role change. Get in touch and we will move it.',
      },
      {
        h: 'Removing someone',
        p: [
          'Removing a member releases their plot back to available and takes them off the roster. It does not delete their account, their harvest log, or anything they posted. If they owed dues, the dues record stays so your books still balance.',
        ],
      },
    ],
  },

  // -------------------------------------------------------------- running ---
  {
    slug: 'events-and-shifts',
    category: 'running',
    title: 'Events and volunteer shifts',
    tagline: 'Workdays people actually turn up to.',
    description:
      'Create garden events with RSVPs, and schedule volunteer shifts with '
      + 'signups, reminders and attendance tracking.',
    keywords: 'events workday rsvp volunteer shifts attendance reminders calendar',
    sections: [
      {
        h: 'Events',
        p: [
          'Events cover workdays, potlucks, plant sales and meetings. Members RSVP from the garden page or the app, and you can see who said yes. Events can repeat, so a standing Saturday workday is one entry rather than twenty.',
          'Every event appears on your public page, which means it also works as outreach — a neighbor who has never met you can find your next workday.',
        ],
      },
      {
        h: 'Volunteer shifts',
        p: [
          'Shifts are for work that needs specific people at a specific time: watering weeks, compost turning, the Saturday gate. Members sign up for a slot, you cap how many are needed, and you can send a reminder before it comes round.',
          'After the fact you mark who actually attended. That builds the volunteer-hours record that funder reports draw on, so marking attendance is worth the thirty seconds — it is the difference between "we think about forty people help out" and a number you can put in a grant application.',
        ],
        pro: true,
      },
    ],
  },
  {
    slug: 'resources-and-tools',
    category: 'running',
    title: 'Shared tools and resources',
    tagline: 'Where the good spade went.',
    description:
      'Track shared garden tools, print QR labels, and check equipment in and '
      + 'out so you know who has what.',
    keywords: 'tools resources checkout qr label borrow return maintenance printer',
    sections: [
      {
        h: 'Build the inventory',
        p: [
          'Add every shared item worth tracking: tools, wheelbarrows, hoses, the mower. Listing inventory is free, and even without checkout it answers "what do we own" — which is most of the value the first time you do a stocktake.',
        ],
      },
      {
        h: 'Checking things out',
        p: [
          'Checkout is how you know where a tool is. A member scans the item\'s QR code, or you check it out on their behalf from the admin portal. Each item has a due date, and you can extend it or force a return if something goes quiet.',
          'You can print QR labels straight from the iOS app to a Bluetooth label printer, which is the fastest way to get a shed tagged in an afternoon.',
        ],
        pro: true,
      },
      {
        h: 'Maintenance',
        p: [
          'Mark an item as out of service while it is broken and it stops being checkoutable, rather than someone walking to the shed to find a mower that has not run since June.',
        ],
        pro: true,
      },
    ],
  },
  {
    slug: 'communication',
    category: 'running',
    title: 'Announcements, messages and the community wall',
    tagline: 'Three channels, three different jobs.',
    description:
      'When to use announcements, direct messages, the community wall, and '
      + 'announcement emails to reach your garden members.',
    keywords: 'announcements messages email community wall moderation broadcast notify',
    sections: [
      {
        h: 'Announcements — one to everyone',
        p: [
          'Announcements are the garden noticeboard: water is off Tuesday, the gate code changed, the plant sale is Saturday. They appear on the garden page and in the app, and you can pin the important ones. Free on every garden.',
        ],
      },
      {
        h: 'Messages — one to one',
        p: [
          'Direct messages are for conversations with a single member: a dues reminder, a question about a neglected bed, a welcome to someone new. You can also broadcast to the whole garden when something needs to land in an inbox rather than on a noticeboard.',
        ],
        pro: true,
      },
      {
        h: 'The community wall — everyone to everyone',
        p: [
          'The wall is the members\' space: seedling swaps, questions, photos of the first tomato. Public comments are screened automatically for spam and abuse before they appear, and anything questionable waits for you to approve or remove it.',
        ],
      },
      {
        h: 'Announcement emails',
        p: [
          'Announcement emails send a formatted note to your members\' inboxes, with your garden\'s name and reply-to address. Configure the sender details once in the Setup section, and preview before you send — an email is the one channel you cannot edit after the fact.',
        ],
        pro: true,
      },
    ],
  },
  {
    slug: 'photos-and-impact',
    category: 'running',
    title: 'Photos, harvest logs and impact',
    tagline: 'Proof that the season happened.',
    description:
      'Post garden photos, log harvest weights, and turn a season of records '
      + 'into a funder-ready impact report.',
    keywords: 'photos gallery harvest log pounds impact funder report grant weight',
    sections: [
      {
        h: 'The photo wall',
        p: [
          'Photos are the thing that makes a garden page feel alive to someone who has never visited. Members can post to the gallery, and photos appear on the public page and the app dashboard.',
        ],
        pro: true,
      },
      {
        h: 'Harvest logging',
        p: [
          'Members log what they picked and how much it weighed. It takes seconds in the app and it accumulates into the single most useful number a community garden has: pounds of food grown this season.',
          'The habit is the hard part. Logging in the garden, at the moment of picking, works. Asking people to remember in the evening does not.',
        ],
      },
      {
        h: 'Funder reports',
        p: [
          'Funder Reports assembles your harvest weight, volunteer hours, member counts and plot occupancy over a date range into a document written in the language grant officers use. You can override the valuation rates if your funder prefers their own, print it, or export the underlying numbers.',
          'This is the tab that pays for itself. The numbers are already in the system; the report just stops you rebuilding them in a spreadsheet the night before a deadline.',
        ],
        pro: true,
      },
    ],
  },

  // ---------------------------------------------------------------- money ---
  {
    slug: 'money-overview',
    category: 'money',
    title: 'How money moves through YardHarvest',
    tagline: 'Read this before setting anything up.',
    description:
      'Where garden dues and sales actually go, who holds the money, and why '
      + 'YardHarvest never sits between you and your funds.',
    keywords: 'money flow stripe connect destination charge dues payout platform fee',
    sections: [
      {
        h: 'Your money is yours',
        p: [
          'YardHarvest does not hold your garden\'s money. When a member pays dues, or you take a card at the gate, the payment goes to a Stripe account in your garden\'s name and Stripe pays it out to your bank. We are not a middleman with a balance.',
          'This is why payout setup is a real step and not a checkbox. Stripe has to know who you are before it can send money to your bank, and that is a legal requirement, not a YardHarvest one.',
        ],
      },
      {
        h: 'The three ways money comes in',
        list: [
          'Online dues — a member pays from the garden page or the app with a card or bank transfer.',
          'In-person dues — you collect at the gate with Tap to Pay on an iPhone, against a member\'s dues record.',
          'Ad-hoc sales — plant starts, day passes, anything. Tap to Pay for any amount, with a memo.',
        ],
        p: [
          'All three land in the same place and appear in the same Finance activity feed. Cash and checks you record by hand on the dues record, and those never touch Stripe.',
        ],
      },
      {
        h: "What it costs to take a payment",
        p: [
          "Stripe charges a processing fee on every card payment, and on your garden it is charged to your Stripe account. A $50 dues payment does not arrive as $50 - it arrives as roughly $48. That is Stripe, the same fee any business pays to take a card.",
          "YardHarvest takes nothing from your dues. There is no platform cut on garden collections, so the only difference between what a member pays and what reaches your bank is Stripe.",
          "Your Finance screen shows all three numbers: what was charged, what Stripe took, and what you received. Garden Pro is billed separately as a subscription and is unrelated.",
        ],
        tip: "Set your dues to the amount you want members to pay, not the amount you want to receive. Members are charged exactly what you set; the processing fee comes off your side.",
      },
    ],
  },
  {
    slug: 'stripe-setup',
    category: 'money',
    title: 'Set up payouts with Stripe',
    tagline: 'The one setup step worth doing carefully.',
    description:
      'Step-by-step Stripe Connect onboarding for a community garden: what '
      + 'Stripe asks for, how long it takes, and how to know it worked.',
    keywords: 'stripe connect onboarding payout bank account setup verification ein',
    sections: [
      {
        h: 'Before you start',
        p: [
          'Stripe will ask who is legally receiving the money. Have these to hand and the whole thing takes about ten minutes; go looking for them halfway through and it takes a week.',
        ],
        list: [
          'The legal name of whoever receives the money — the garden\'s nonprofit, a fiscal sponsor, or a person.',
          'A tax ID (EIN) if you are set up as an organization, or an SSN if you are receiving it personally.',
          'A business address. A PO box is often rejected; use a physical address.',
          'Bank account and routing numbers for the account the money should land in.',
          'A phone number that can receive a verification code right now.',
        ],
        warn: 'Whoever completes this is legally the recipient. If your garden has a nonprofit or a fiscal sponsor, onboard as that organization — not as yourself. Moving it later means starting over with a new account.',
      },
      {
        h: 'Do the onboarding',
        steps: [
          'Admin portal, then Billing & Payouts.',
          'Choose to set up payouts. Stripe\'s form opens inside YardHarvest.',
          'Work through the questions. Save as you go — it will let you come back.',
          'Add the bank account at the end, and confirm the phone verification.',
          'Return to Billing & Payouts. It should now say your account is ready.',
        ],
      },
      {
        h: 'How to know it actually worked',
        p: [
          'Two things have to be true, and they are separate. Charges enabled means you can take money. Payouts enabled means Stripe can send it to your bank. It is entirely possible to have the first without the second — you take a payment happily and the funds then sit in Stripe waiting on a document.',
          'Your Finance tab reports both, in plain words, on the Stripe sub-tab. If it says payments and payouts are both enabled, you are done.',
        ],
      },
      {
        h: 'The first payout is slower',
        p: [
          'Stripe typically holds a new account\'s first payout for several days before releasing it, then settles into a regular schedule. This is normal anti-fraud behavior, not a problem with your setup. Do not collect a season of dues the day before you need the money.',
        ],
      },
    ],
  },
  {
    slug: 'dues',
    category: 'money',
    title: 'Generating and collecting dues',
    tagline: 'From "everyone owes $50" to a paid roster.',
    description:
      'Generate seasonal dues for plot holders, take payment online or in '
      + 'person, record cash, and chase what is outstanding.',
    keywords: 'dues fees season generate collect waive comp unpaid remind cash check',
    sections: [
      {
        h: 'Generate the season',
        p: [
          'Finance, then the Dues sub-tab, then Generate Dues. Enter the amount and it creates one record per current plot holder for that season. Anyone who claims a plot afterwards needs a record adding, so generate once the roster has settled.',
        ],
        pro: true,
      },
      {
        h: "What the garden actually receives",
        p: [
          "Members are charged exactly the amount you set. What reaches your bank is a little less, because Stripe takes its processing fee from your side of the transaction - on a card, roughly 3%. Set dues at $50 and expect about $48.",
          "Cash and checks have no fee at all, which is worth remembering if your garden is fine with either. Bank transfer is usually cheaper than card too.",
        ],
        tip: "Do not set dues at $52 to cover the fee. Members see the number you set, and an odd amount invites questions you will spend the season answering.",
      },
      {
        h: 'How members pay',
        p: [
          'A member with an outstanding dues record sees it on the garden page and in the app, and can pay by card or bank transfer. The record marks itself paid — you do not have to reconcile anything.',
          'Payment is refused with a clear message if your payout account is not ready. That is deliberate: it stops dues being collected into an account that cannot pay them out to you.',
        ],
      },
      {
        h: 'Cash, checks and waivers',
        list: [
          'Cash or check — record the payment by hand on the member\'s dues row, with a note. It never touches Stripe.',
          'Waived — dues forgiven for this season. Use it for hardship, and it is reversible.',
          'Comp — no dues owed at all. Use it for a plot you have given to a school or a partner.',
        ],
      },
      {
        h: 'Chasing what is outstanding',
        p: [
          'The Dues sub-tab shows who has paid and who has not, and you can send a reminder from the same row. The Summary sub-tab gives you the collection rate, which is the number to watch mid-season — chasing at 60% collected is a conversation, chasing in November is a problem.',
        ],
        pro: true,
      },
    ],
  },
  {
    slug: 'tap-to-pay',
    category: 'money',
    title: 'Tap to Pay at the gate',
    tagline: 'Take a card on your iPhone, with no reader.',
    description:
      'Use Tap to Pay on iPhone in the YardHarvest app to collect dues and '
      + 'run plant sales in person, with no card reader.',
    keywords: 'tap to pay iphone terminal card present in person sale reader nfc',
    sections: [
      {
        h: 'What you need',
        list: [
          'An iPhone XS or newer running iOS 17 or later. iPads cannot do Tap to Pay.',
          'The YardHarvest app, signed in as the garden\'s organizer.',
          'Payout setup finished, including in-person card payments being active on your Stripe account.',
        ],
        p: [
          'If your device cannot do it, the Payments screen says so rather than failing at the moment you hold a card to it.',
        ],
      },
      {
        h: 'Collecting dues in person',
        steps: [
          'Open the app, go to your garden, then Payments.',
          'Choose Collect Dues and pick the member.',
          'Hold their card or phone to the back of yours.',
          'The dues record marks itself paid.',
        ],
      },
      {
        h: 'Selling anything else',
        p: [
          'New Sale takes any amount with a memo — plant starts, a bag of compost, a day pass at an open day. It is not tied to a dues record. Write a memo every time: it is the only thing that tells you later what the £12 on the fourteenth was for.',
        ],
      },
      {
        h: 'If the network drops mid-tap',
        p: [
          'The payment still counts. Stripe tells YardHarvest directly what happened, so a dues record settles even if your phone lost signal immediately after the tap. You do not need to re-take the payment — check the Finance activity feed before you charge anyone twice.',
        ],
      },
    ],
  },
  {
    slug: 'money-feed',
    category: 'money',
    title: 'Reading your Stripe activity',
    tagline: 'What came in, what went back out, and when it hit the bank.',
    description:
      'Understand the Finance Stripe tab: card money in, platform and Stripe '
      + 'fees, refunds, chargebacks, and bank deposits.',
    keywords: 'finance activity feed stripe fees kept deposits refund dispute chargeback',
    sections: [
      {
        h: 'Where to find it',
        p: [
          'Finance, then the Stripe sub-tab on the web. In the iOS app it is Payments, then Money. Both show the same thing, straight from Stripe, and neither requires Garden Pro — it is a record of money you have already taken.',
        ],
      },
      {
        h: "What the totals mean",
        list: [
          "Charged - everything billed to members in the window, before anything is deducted.",
          "Stripe fees - card processing, charged by Stripe and taken from your side.",
          "Net received - what actually reached you. Read from Stripe rather than worked out, so it accounts for anything unusual about a payment.",
          "Deposited to bank - money Stripe has actually sent you.",
        ],
        p: [
          "Refunds, chargebacks and a platform fee each get their own figure, but only when there is something on them. YardHarvest charges no platform fee on garden collections, so most gardens will never see that line.",
        ],
      },
      {
        h: 'Deposits cover your whole Stripe account',
        p: [
          'A deposit is not per-garden. If you run two gardens on one Stripe account, a single deposit covers both, which is why deposits are shown in the feed but never added into one garden\'s totals. Reconciling one garden\'s collections against a deposit will not balance, and that is expected.',
        ],
      },
      {
        h: 'Refunds and chargebacks',
        p: [
          'Refund a dues payment from your Stripe dashboard and the member goes back to unpaid on your roster automatically, so the roster never claims someone paid when they were refunded.',
          'A chargeback is a cardholder disputing a payment with their bank. Stripe pulls the money back immediately and gives you a short window to respond with evidence. You will be notified when one opens — that notification is time-sensitive in a way almost nothing else in YardHarvest is.',
        ],
      },
    ],
  },
  {
    slug: 'stripe-pitfalls',
    category: 'money',
    title: 'Stripe pitfalls worth knowing',
    tagline: 'The things that go wrong, and what they actually mean.',
    description:
      'Common Stripe problems for community gardens: payout not ready, '
      + 'card-present inactive, restricted accounts, and missing payouts.',
    keywords: 'stripe problems errors payout not ready card present restricted troubleshoot',
    sections: [
      {
        h: '"Finish payout onboarding before collecting"',
        p: [
          'Your Stripe account is not ready to receive money, so collection is refused rather than charged somewhere it cannot reach you. Finish onboarding in Billing & Payouts. If you thought you had finished, you have probably hit the charges-versus-payouts distinction below.',
        ],
      },
      {
        h: 'Charges enabled but payouts disabled',
        p: [
          'These are two separate switches. You can be perfectly able to take money and still unable to receive it — usually because Stripe wants an identity document, a tax ID, or a bank account it has not been given yet. Money keeps arriving into Stripe and stops there.',
          'Your Finance Stripe tab names what is outstanding. Nothing you have already collected is at risk; it is waiting.',
        ],
      },
      {
        h: 'Tap to Pay says in-person payments are not enabled',
        p: [
          'Card-present is a separate Stripe capability from ordinary online payments, and accounts created before you started using Tap to Pay never asked for it. YardHarvest requests it automatically the first time you try, and it usually goes active within a few minutes. If it stays inactive, there is normally an unfinished step in your Stripe dashboard.',
        ],
      },
      {
        h: 'Could not set up a payment location',
        p: [
          'Tap to Pay registers your phone as a card reader against a location on your Stripe account, and a location needs a real business address. Add one in your Stripe dashboard and try again.',
        ],
      },
      {
        h: 'Your account has been restricted',
        p: [
          'Stripe has paused the account, normally because a verification deadline passed or a document went stale. You will be told as soon as we hear it, rather than finding out when a card fails in front of a member. Open your Stripe dashboard and clear what it asks for.',
        ],
      },
      {
        h: 'Test mode and live mode are different worlds',
        p: [
          'If you have been experimenting in a Stripe sandbox, none of it exists in live mode — not the account, not the payments, not the settings. Check which mode your Stripe dashboard is in before concluding something did not save.',
        ],
      },
      {
        h: 'No deposits showing at all',
        p: [
          'Deposits reach YardHarvest through a separate Stripe connection to the one that carries payments. If your payments appear but your deposits never do, that connection is not set up on the platform side — tell us rather than assuming Stripe has not paid you, and check your Stripe dashboard for the truth in the meantime.',
        ],
      },
    ],
  },

  // ---------------------------------------------------------------- plans ---
  {
    slug: 'free-and-pro',
    category: 'plans',
    title: 'What is free and what Garden Pro adds',
    tagline: 'The actual list, not a marketing table.',
    description:
      'A precise breakdown of which YardHarvest features are free for every '
      + 'community garden and which require Garden Pro.',
    keywords: 'free pro pricing features comparison upgrade what do i get',
    sections: [
      {
        h: 'Free, always',
        p: [
          'Running a garden costs nothing. You can open a garden, fill it, organize it and take money in, without ever paying us.',
        ],
        list: [
          'Your garden, its public page, and unlimited plots and members.',
          'The waitlist, plot reservations and approvals.',
          'Events and RSVPs.',
          'Announcements and the community wall, with automatic moderation.',
          'Tool and resource inventory.',
          'Harvest logging.',
          'Weather alerts.',
          'Payout setup, and collecting money in person with Tap to Pay.',
          'Your Stripe activity feed — every payment, refund and deposit.',
          'Member roster export.',
        ],
      },
      {
        h: 'Garden Pro',
        p: [
          'Pro is {{PRO_MONTHLY}} a month or {{PRO_YEARLY}} a year, with a {{TRIAL_DAYS}}-day free trial that needs no card.',
        ],
        list: [
          'Dues — generating, tracking, reminders, waivers and CSV export.',
          'Expenses and the finance summary.',
          'Funder reports.',
          'Direct messages and broadcasts.',
          'Announcement emails to members\' inboxes.',
          'The photo wall.',
          'Volunteer shifts, signups, reminders and attendance.',
          'Tool checkout, QR labels and maintenance tracking.',
          'The layout designer.',
        ],
      },
      {
        h: 'The line we drew',
        p: [
          'Anything that records money you have already taken stays free, including the whole Stripe activity feed. Putting a paywall between an organizer and the record of their own collections is not a trade we were willing to make. What Pro charges for is the administrative work around it — generating dues, chasing them, and reporting on the result.',
        ],
      },
    ],
  },
  {
    slug: 'trial-and-billing',
    category: 'plans',
    title: 'Trials, upgrading and canceling',
    tagline: 'How Garden Pro billing works.',
    description:
      'Start a Garden Pro trial, upgrade, change plan, or cancel — and what '
      + 'happens to your data either way.',
    keywords: 'trial upgrade cancel subscription billing invoice downgrade refund',
    sections: [
      {
        h: 'The trial',
        p: [
          'Garden Pro trials for {{TRIAL_DAYS}} days and needs no card to start. Everything unlocks immediately. We will remind you before it ends.',
        ],
      },
      {
        h: 'Upgrading',
        p: [
          'Billing & Payouts, then start a subscription. Monthly is {{PRO_MONTHLY}}, yearly is {{PRO_YEARLY}} and works out cheaper. This is a separate payment from your garden\'s dues collection — it goes to YardHarvest, not through your garden\'s Stripe account.',
        ],
      },
      {
        h: 'If a payment fails',
        p: [
          'Stripe retries automatically over several days and we email you. Pro features stay on through a short grace period rather than switching off the moment a card expires, because losing your dues roster mid-season over an expired card would be a ridiculous way to treat a garden.',
        ],
      },
      {
        h: 'Cancelling',
        p: [
          'Cancel any time and Pro runs to the end of the period you have paid for. Nothing is deleted. Your dues records, photos, shifts and reports all remain — they simply stop being editable until you come back, and everything free keeps working exactly as before.',
        ],
      },
    ],
  },

  // ------------------------------------------------------------ gardeners ---
  {
    slug: 'for-gardeners',
    category: 'gardeners',
    title: 'For gardeners',
    tagline: 'Claiming a bed, paying, and logging what you grew.',
    description:
      'How to join a community garden on YardHarvest, claim a plot, pay your '
      + 'dues and log your harvest.',
    keywords: 'gardener member join plot claim pay dues harvest log app rsvp',
    sections: [
      {
        h: 'Finding and joining a garden',
        p: [
          'Browse gardens, open the one near you, and either claim an available plot or join the waitlist. Your request goes to the organizer, who approves it — you will hear back either way.',
        ],
      },
      {
        h: 'Paying your dues',
        p: [
          'If your garden charges dues, you will see what you owe on the garden page and in the app, and you can pay by card or bank transfer. Your organizer may also take payment in person, or record a cash payment on your behalf.',
          'The money goes to your garden, not to YardHarvest.',
        ],
      },
      {
        h: 'Logging your harvest',
        p: [
          'Log what you pick and roughly what it weighed. It takes a few seconds and it adds up: your garden\'s total harvest is what its organizers show funders and the city to keep the garden going. A kitchen scale by the door is the whole trick.',
        ],
      },
      {
        h: 'Everything else',
        list: [
          'RSVP to workdays and events.',
          'Borrow shared tools by scanning the QR label, where your garden has that switched on.',
          'Post to the community wall and the photo gallery.',
          'Message your organizer directly.',
        ],
      },
    ],
  },

  // -------------------------------------------------------------- trouble ---
  {
    slug: 'common-problems',
    category: 'trouble',
    title: 'Common problems',
    tagline: 'Quick answers to the things that come up most.',
    description:
      'Troubleshooting YardHarvest: missing emails, members who cannot see '
      + 'features, locked Pro tabs and things that look wrong.',
    keywords: 'troubleshoot problem broken missing email not working locked help',
    sections: [
      {
        h: 'A member cannot see something you can',
        p: [
          'Most likely it is a Pro feature and the garden is on the free plan, or the member is not approved yet. Check the roster first — an unapproved reservation looks a lot like a broken account from the member\'s side.',
        ],
      },
      {
        h: 'Emails are not arriving',
        p: [
          'Check spam first, then check the address on the member\'s profile. If an address has hard-bounced or been marked as spam once, it is suppressed automatically to protect delivery for everyone else in your garden, and it will not receive anything until that is cleared.',
        ],
      },
      {
        h: 'Pro tabs went dark',
        p: [
          'Either the trial ended, the subscription was canceled, or a payment failed and the grace period ran out. Billing & Payouts tells you which. Nothing has been deleted — the data is waiting.',
        ],
      },
      {
        h: 'A number looks wrong on the Finance screen',
        p: [
          'Check whether the figure is labelled as a ceiling — while a payment\'s Stripe fee has not been confirmed, "You keep" is shown as an upper bound rather than a precise figure, and it will say so. Deposits also cover your whole Stripe account rather than one garden.',
          'If something still does not reconcile, your Stripe dashboard is the system of record for money, and we would rather hear about a mismatch than have you quietly distrust the screen.',
        ],
      },
      {
        h: 'Still stuck',
        p: [
          'Get in touch. Tell us the garden name and what you expected to happen — that is almost always enough for us to find it.',
        ],
      },
    ],
  },
];

/** Article by slug, or null. */
export function findArticle(slug) {
  return ARTICLES.find((a) => a.slug === slug) || null;
}

/** Articles in a category, in file order. */
export function articlesIn(categoryKey) {
  return ARTICLES.filter((a) => a.category === categoryKey);
}

/** Loose text match over title, tagline and keywords. */
export function searchArticles(query) {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  const terms = q.split(/\s+/);
  return ARTICLES.filter((a) => {
    const hay = `${a.title} ${a.tagline} ${a.keywords} ${a.category}`.toLowerCase();
    return terms.every((t) => hay.includes(t));
  });
}
