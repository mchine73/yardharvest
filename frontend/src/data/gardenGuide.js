// The Community Garden Guide — content for /about/guide.
// Plain-string content (no JSX) rendered by pages/Guide.jsx.
// Tone: light, practical, neighborly — informative without being preachy.
// No invented statistics; ranges are hedged as "many"/"typically".
//
// KEEP IN SYNC: chapter slugs/titles/descriptions are mirrored in app/seo.py
// (GUIDE_META) for server-side crawler meta + the sitemap.

export const GUIDE_TITLE = 'The Community Garden Guide';
export const GUIDE_INTRO =
  'Everything we know about starting and running a community garden, from ' +
  '"is anyone else into this?" to a thriving plot of neighbors. Written for ' +
  'real volunteers with real day jobs — practical, honest, and occasionally ' +
  'muddy.';

export const CHAPTERS = [
  {
    slug: 'getting-started',
    title: 'Getting Started',
    icon: 'bi-flag',
    tagline: 'From “wouldn’t it be nice” to an actual plan.',
    description:
      'How to start a community garden: gauge neighborhood interest, build a ' +
      'founding team, and set a shared vision before you touch a shovel.',
    sections: [
      {
        h: 'Start with people, not plants',
        p: [
          'Every community garden begins the same way: somebody looks at an empty lot and thinks “that could be tomatoes.” The trick is finding out who else is thinking it. Before you research soil or seeds, research neighbors. A garden with great soil and two volunteers fails; a garden with mediocre soil and fifteen committed people finds a way.',
          'Put out feelers where your neighborhood already talks — a flyer at the coffee shop, a post in the neighborhood group, a sign on the fence of the lot itself with a phone number. You’re looking for two things: a rough headcount of people who’d want a plot, and two or three people willing to help organize. Those organizers matter more than the headcount.',
        ],
      },
      {
        h: 'Hold one honest meeting',
        p: [
          'Get interested folks in a room (or a park, or a group chat that graduates to a room). Keep the first meeting short and concrete. You want answers to three questions: What do we want — individual plots, a shared communal garden, or a mix? Who can commit time, not just enthusiasm? And what does “success” look like a year from now?',
          'Write the answers down. This becomes your one-page vision, and it will save you arguments later. When someone proposes chickens in year two, you’ll be glad you wrote down what the group actually signed up for.',
        ],
        list: [
          'Individual plots: households tend their own beds — the most common model, and the easiest to organize.',
          'Communal style: everyone works shared beds and splits the harvest — great for food-pantry gardens, needs stronger coordination.',
          'Hybrid: individual plots plus a few shared beds (herbs, flowers, donation rows) — the best of both, and what many gardens settle into.',
        ],
      },
      {
        h: 'Give the group a tiny bit of structure',
        p: [
          'You don’t need bylaws to plant lettuce, but you do need three named roles: someone who talks to the landowner and city, someone who handles money, and someone who keeps the member list. In many gardens that’s two people wearing three hats, and that’s fine.',
          'Decide early how decisions get made — majority vote at meetings is plenty. The goal isn’t bureaucracy; it’s making sure the garden isn’t one burned-out hero away from collapse. (More on avoiding that fate in the chapter on organizing people.)',
        ],
      },
    ],
  },
  {
    slug: 'finding-land',
    title: 'Finding Land & Site Planning',
    icon: 'bi-geo-alt',
    tagline: 'Sun, water, soil, and a handshake that’s actually in writing.',
    description:
      'How to find land for a community garden, evaluate sun, water and ' +
      'soil, and secure a lease or agreement that protects the garden.',
    sections: [
      {
        h: 'What makes a good site',
        p: [
          'Vegetables are simple creatures with three demands: sun, water, and soil that isn’t actively hostile. Look for at least six hours of direct sun (watch the site at different times of day — that friendly morning lot may sit in building shade all afternoon), a water source you can legally and practically use, and reasonably flat ground.',
          'Convenience beats perfection. A decent site people walk past daily will outperform a perfect site a ten-minute drive away. Gardens live on casual visits — the “I’ll just pop in and water” trips — and distance quietly kills those.',
        ],
      },
      {
        h: 'Test the soil before you fall in love',
        p: [
          'Urban soil has history, and not all of it is charming. Before committing, get a soil test — university extension offices in most states run them affordably and will screen for lead and other contaminants along with nutrients. If contamination turns up, don’t panic: raised beds with imported soil and a barrier layer are the standard, well-trodden fix. But you want to know before you build, not after.',
        ],
      },
      {
        h: 'Who owns the lot?',
        p: [
          'Your county assessor’s website will tell you who owns a parcel. Owners fall into three buckets: the city or county (often the easiest — many cities have vacant-lot or adopt-a-lot programs and a person whose actual job is saying yes to you), churches, schools and nonprofits (frequently thrilled to host), and private owners (a mixed bag, but a well-kept garden raises the value of everything around it, and plenty of owners know it).',
        ],
      },
      {
        h: 'Get it in writing',
        p: [
          'A handshake is how gardens start; a written agreement is how they survive. Ask for a lease or use agreement of at least three years — you’re about to invest real money in soil and beds, and one season isn’t enough to earn it back. The agreement should cover: who pays for water, what happens if the owner sells, liability and insurance expectations, and what “leaving the site clean” means if it ends.',
          'Many gardens operate under a nominal lease — a dollar a year is a time-honored tradition. What matters isn’t the rent; it’s that everyone knows the rules before the first bed is built.',
        ],
      },
    ],
  },
  {
    slug: 'funding-and-budget',
    title: 'Funding & Your First Budget',
    icon: 'bi-piggy-bank',
    tagline: 'Where the money comes from, and where it quietly goes.',
    description:
      'Community garden startup costs, realistic budgets, plot dues, grants, ' +
      'fundraising ideas, and fiscal sponsorship explained simply.',
    sections: [
      {
        h: 'What a garden actually costs',
        p: [
          'Startup is the expensive part: soil and compost, lumber for beds, a water connection or tank, basic tools, a shed or storage box, and fencing if your neighborhood requires honesty enforcement. Depending on size and how much you scrounge, first-year costs commonly land anywhere from a few hundred dollars for a scrappy volunteer build to several thousand for a larger fenced site with a new water line — the water line is usually the single biggest number.',
          'After year one, it gets much cheaper. Ongoing costs are water bills, compost top-ups, tool replacement, insurance if you carry it, and the occasional lock after someone loses the key. Again. (Buy a combination lock.)',
        ],
      },
      {
        h: 'Plot dues: the steady engine',
        p: [
          'Most plot-based gardens charge seasonal or annual dues, and many run entirely on them. Set dues to cover your real recurring costs divided by your plots, with a cushion — and always offer a reduced or waived rate for anyone who needs it, traded for volunteer hours if you like. A garden nobody can afford isn’t a community garden.',
          'Collect dues once, at a clear deadline, with a clear consequence (no renewal, plot goes to the waitlist). Chasing eleven people for twenty dollars each in July is the specific chore that makes treasurers quit.',
        ],
      },
      {
        h: 'Grants, sponsors, and the fiscal sponsor trick',
        p: [
          'Small grants for community gardens are surprisingly plentiful: city neighborhood programs, community foundations, hardware-store and grocery chains, master-gardener associations, and health-focused nonprofits all run them. Most are modest — think hundreds to a few thousand dollars — which happens to be exactly what a garden needs.',
          'Many funders require a nonprofit to receive money. You don’t need to become a 501(c)(3) — find a fiscal sponsor: an existing nonprofit (church, neighborhood association, food bank) that receives the grant on your behalf, usually for a small admin percentage. It’s a normal, boring, wonderful arrangement.',
          'And never underestimate in-kind: lumber yards with warped-but-fine boards, tree services with free wood chips, restaurants with buckets. The best garden budgets are half cash, half charm.',
        ],
      },
    ],
  },
  {
    slug: 'building-the-garden',
    title: 'Building the Garden',
    icon: 'bi-hammer',
    tagline: 'Layout, beds, water, and the legendary build day.',
    description:
      'Designing a community garden layout, building raised beds, setting up ' +
      'water, and organizing a volunteer build day that people enjoy.',
    sections: [
      {
        h: 'Sketch before you shovel',
        p: [
          'Draw the site to rough scale and place the big things first: beds, paths, water points, compost, storage, and a gathering spot. Paths between beds should fit a wheelbarrow (three feet is comfortable; four is generous), and at least the main paths should be wide and firm enough for wheelchairs and strollers — accessibility is much cheaper to design in than retrofit.',
          'Put the compost bins downwind, the shed where it won’t shade beds, and a bench somewhere with a view of it all. The bench is not optional. The bench is where the community part happens.',
        ],
      },
      {
        h: 'Beds: raised vs. in-ground',
        p: [
          'Raised beds cost more up front but solve several problems at once: questionable soil, drainage, defined boundaries between plots, and backs that don’t bend like they used to. In-ground rows are nearly free and fine where soil tested clean. Many gardens mix both.',
          'A standard raised bed is four feet wide (reachable from both sides without stepping in) and eight to twelve feet long. Untreated cedar lasts longest; untreated pine is cheaper and still gives years of service. Skip old railroad ties and anything treated before you were born.',
        ],
      },
      {
        h: 'Water: solve it properly, once',
        p: [
          'Nothing determines a garden’s success as quietly as water convenience. If members fill jugs from a distant spigot, beds go dry by August. Aim for a hose reach to every plot — a few well-placed spigots or a simple manifold with timers. If you’re on a meter, mulch heavily and water deeply-but-rarely; your bill and your tomatoes will both thank you.',
        ],
      },
      {
        h: 'The build day',
        p: [
          'Batch the heavy work into one or two organized volunteer days. The formula: pre-cut and pre-stage everything beforehand, give every arriving human an immediate job, put one confident person on each station (bed assembly, soil hauling, path laying), feed people, and finish with something visible — the first bed planted, the sign going up. People forget sore arms; they remember the photo.',
        ],
      },
    ],
  },
  {
    slug: 'organizing-people',
    title: 'Organizing People',
    icon: 'bi-people',
    tagline: 'Plot agreements, waitlists, and not burning out your founder.',
    description:
      'How to organize community garden members: plot agreements, waitlists, ' +
      'volunteer hours, leadership structure, and avoiding coordinator burnout.',
    sections: [
      {
        h: 'The plot agreement: one page, no lawyer voice',
        p: [
          'Every member signs a short agreement when they take a plot. It should fit on one page and read like a neighbor wrote it. Cover: what dues cost and when they’re due, what “keeping up your plot” means (planted by a date, weeded to a reasonable standard, cleared by season’s end), shared-chore expectations, what happens to abandoned plots, and the small stuff that becomes big stuff — pets, kids, guests, pesticides or organic-only, and whether the zucchini on the fence table is community property. (It is. It always is.)',
        ],
      },
      {
        h: 'Run the waitlist like you mean it',
        p: [
          'A good garden develops a waitlist, and a waitlist is a promise. Keep it honest: first-come order (with any priority rules you’ve agreed, like neighborhood residents first), written down where the organizers can see it, and actually used when a plot opens. The fastest way to lose community trust is a plot that goes to somebody’s cousin.',
          'Turn over abandoned plots promptly but kindly — a friendly check-in, a stated deadline, then reassignment. Life happens to gardeners; the agreement you wrote makes the conversation easy instead of awkward.',
        ],
      },
      {
        h: 'Spread the load before it crushes someone',
        p: [
          'The most common way community gardens die isn’t drought or vandals — it’s founder burnout. One heroic person does everything for three years, moves away, and the garden composts itself. Design against it from day one: rotate a couple of named roles annually, keep a shared document of how things actually work (where the water key lives, when dues go out, who to call at the city), and split chores into small owned pieces rather than “everyone helps,” which reliably means nobody does.',
          'Volunteer hour requirements — a few hours per season per plot, logged simply — keep shared spaces tended without nagging. Pair them with scheduled workdays that end in food. Attendance doubles when there’s a grill.',
        ],
      },
    ],
  },
  {
    slug: 'running-the-season',
    title: 'Running the Season',
    icon: 'bi-calendar3',
    tagline: 'A year in the life: dues, events, weeds, and repeat.',
    description:
      'A season-by-season rhythm for running a community garden: renewals, ' +
      'spring kickoff, summer maintenance, events, and winterizing.',
    sections: [
      {
        h: 'Late winter: paperwork season',
        p: [
          'The season starts before the soil thaws. Send renewal notices with a real deadline, collect dues, offer open plots to the waitlist, and order the year’s compost and seeds while everything is cheap and in stock. One planning meeting now — dates for the kickoff, workdays, and the fall cleanup — gives the whole year a spine.',
        ],
      },
      {
        h: 'Spring: the kickoff',
        p: [
          'Open the season with an event, not an email. A spring kickoff workday — beds refreshed, water turned on, new members introduced and shown where everything lives — sets the tone and catches problems (a cracked spigot, a rotted bed corner) while they’re cheap. Hand every new member their plot assignment, the one-page agreement, and one experienced neighbor to ask questions of.',
        ],
      },
      {
        h: 'Summer: maintain the machine',
        p: [
          'Summer is mostly wonderful and partly weeds. The garden’s shared spaces need a light, steady rhythm: a monthly workday, a simple chore rotation for mowing and compost turning, and someone glancing at the water system weekly. Communication is the real chore — a monthly note (what’s happening, what needs doing, what’s ready to harvest) keeps casual members connected and quietly reminds everyone the garden is alive and led.',
          'Do at least one purely social event. Tomato tasting, harvest potluck, kids’ scavenger hunt — anything where nobody is asked to weed. Gardens that only ever meet to work eventually stop meeting.',
        ],
      },
      {
        h: 'Fall: land the plane',
        p: [
          'End the season on purpose: a cleanup day with clear expectations (plots cleared by a date, tools inventoried, water drained before first freeze), garlic and cover crops in for those who want them, and a short wrap-up note — what grew well, what broke, what to change. Then let everyone rest. Including you.',
        ],
      },
    ],
  },
  {
    slug: 'harvest-and-impact',
    title: 'Harvest & Impact',
    icon: 'bi-basket',
    tagline: 'Counting carrots, sharing surplus, and proving it matters.',
    description:
      'Tracking community garden harvests and impact: donation programs, ' +
      'simple record-keeping, and reporting that wins over funders and cities.',
    sections: [
      {
        h: 'Why bother counting?',
        p: [
          'You don’t need data to enjoy a tomato. You do need it the day the city asks whether the garden “really gets used,” or a grant application wants outcomes, or a skeptical neighbor calls it “just a hobby lot.” A garden that can say how many households it feeds, how many pounds it grew, and how many volunteer hours it logged is a garden that’s very hard to argue with — and very easy to fund.',
        ],
      },
      {
        h: 'Keep tracking almost effortless',
        p: [
          'The best tracking system is the one people actually use. A scale by the shed and a simple log — paper on a clipboard or a shared form — gets you shockingly far. Track three things: harvest weight (even rough estimates), volunteer hours, and participation (plots filled, waitlist length, event turnout). Five seconds per harvest basket is the entire ask.',
        ],
      },
      {
        h: 'Share the surplus',
        p: [
          'Every garden eventually produces more than its members can eat — usually all at once, usually zucchini. Put surplus to work: a designated donation bed or “grow a row” program, a standing weekly drop-off with a local food pantry (call first — they’ll tell you what they can take and when), or the humble sharing table by the gate. Weigh what you give; donated pounds are the single most persuasive number in any garden’s annual report.',
        ],
      },
      {
        h: 'Tell the story once a year',
        p: [
          'Roll your numbers into one page each fall: pounds grown, pounds donated, households, volunteer hours, events held, plus three photos and one quote from a member. Send it to the landowner, the city, your funders, and the neighborhood group. This single page renews leases, wins grants, and recruits next spring’s waitlist — it’s the highest-leverage hour of the whole year.',
        ],
      },
    ],
  },
  {
    slug: 'troubleshooting',
    title: 'Troubleshooting',
    icon: 'bi-bandaid',
    tagline: 'Vandals, vacancies, conflicts, and other solvable problems.',
    description:
      'Common community garden problems and fixes: theft and vandalism, ' +
      'abandoned plots, member conflicts, pests, and leadership turnover.',
    sections: [
      {
        h: 'Theft and vandalism',
        p: [
          'It happens, it stings, and it’s survivable. The best defenses are social, not architectural: a garden that looks loved and busy gets bothered less, neighbors who know the garden watch out for it, and a sharing table by the gate converts a surprising amount of “theft” into “taking the free vegetables, as invited.” Fences help; signs naming the garden and its people help more. If something is taken, replant loudly and cheerfully — resilience is a great look.',
        ],
      },
      {
        h: 'The abandoned plot',
        p: [
          'Someone’s plot has gone to thistle and they’ve stopped answering messages. Your plot agreement already solved this: friendly check-in, stated deadline, reassignment to the waitlist. The kind version matters — the number-one reason plots get abandoned is that life got hard, not that people stopped caring. Offer a graceful exit and a spot back on the list, and enforce the timeline anyway. Both halves are the job.',
        ],
      },
      {
        h: 'People conflict',
        p: [
          'Two members are feuding about a shade tree, an aggressive squash, or a decade-old grievance that predates the garden. Don’t adjudicate at the fence. Have a standing, boring process: concerns go to the organizers, get talked through calmly with both people, and get resolved by the written rules — which is why you wrote them. Most garden conflict is really about unclear expectations; every fight you have is a sentence to add to next year’s agreement.',
        ],
      },
      {
        h: 'When a leader leaves',
        p: [
          'Coordinators move, burn out, or simply finish their chapter. If you rotated roles and kept the how-things-work document from the organizing chapter, this is a handoff, not a crisis. If you didn’t — do it now, while they’re still around and fond of you. A garden’s knowledge should live in a shared drive, not one person’s head.',
        ],
      },
      {
        h: 'And when it’s going great',
        p: [
          'The final problem nobody warns you about: success. A thriving garden attracts a waitlist, event requests, a second-site conversation with the city, and more admin than any volunteer signed up for. That’s the moment to get organized on purpose — clear records, steady communication, dues that collect themselves — so the garden’s growth runs on systems instead of siphoning one person’s evenings. However you manage it, protect the thing that made it work: neighbors, in the dirt, together.',
        ],
      },
    ],
  },
];
