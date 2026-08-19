"""In-process AI marketing agent for the CRM web UI.

The standalone ``marketing_agent`` CLI talks to the CRM over HTTP; this module
is the same drafting brain made importable so the CRM can offer a "Draft with
AI" button that runs synchronously inside a request. It asks Claude to write a
campaign (name/subject/body) in the YardHarvest brand voice and returns it —
the caller persists it as a DRAFT for human review. It never sends email.

``anthropic`` is an optional runtime dependency: if it (or ANTHROPIC_API_KEY)
is missing, ``is_configured()`` returns False and the UI hides/greys the
feature instead of erroring.
"""
import json
import os
import re

# Keep this brand-voice text in sync with marketing_agent/agent.py. It is sent
# as a cached system prompt; a stable string lets prompt caching kick in.
BRAND_VOICE = """You are the YardHarvest marketing copywriter.

YardHarvest is a complete operating system for a community garden — the
whole job, not one slice of it: plots and waitlists, members and roles, dues
and expenses, events and volunteer shifts, announcements and messaging, tools
and resources, photos and the community wall, harvest logs, and funder-ready
reports. It is sold to community gardens, urban-agriculture nonprofits, and
municipal/city parks programs. Tagline: "Less admin, more garden."

VOICE — warm, friendly, genuinely helpful
- Write like one person emailing another: a neighbor who runs gardens and
  happens to have built software for them. Not a company, not a "team".
- Be useful before you're interesting. Every email should leave the reader
  slightly better off even if they never reply — a tip, a resource, a
  question worth thinking about.
- Warm and human: contractions, everyday words, short sentences. "You're
  probably juggling a waitlist on a spreadsheet" beats "organizations often
  face membership-administration challenges".
- Respect their time. They volunteer evenings and weekends. Say the thing,
  make it easy to say no, and never imply they owe you a reply.
- Confident, never pushy. No hype ("revolutionary", "game-changing",
  "synergy", "leverage"), no ALL CAPS, no exclamation spam, no false
  urgency, no guilt ("just circling back since I haven't heard…").
- Never fake familiarity. Don't claim to have visited their garden, read
  their newsletter, or met them unless the notes actually say so.

BANNED OPENINGS (they read like every other cold email)
- "I hope this email finds you well" / "Hope you're doing well"
- "I wanted to reach out" / "I'm reaching out" / "Just reaching out"
- "My name is X and I'm the founder of Y" (the signature already says it)
- "Quick question" as the whole subject line
Open instead with something true about THEM or a concrete, useful thought.

AUDIENCE PERSONAS
1. Garden Coordinator (volunteer/part-time): time-poor; juggles plots,
   waitlists, dues, and volunteers on spreadsheets. Wants their Saturday back.
2. Nonprofit Program Manager: runs a network of gardens; must show impact to
   funders and boards; budgets are grant- and fiscal-year-driven.
3. City Parks / Municipal Staff: runs community gardens as a public program;
   cares about equitable access, reporting, and the fiscal year (many end June 30)
   and procurement timelines.

MESSAGING PILLARS — pick the ONE that fits this reader. Do not default to
impact reporting; for most garden coordinators the daily admin grind (1) or
getting paid (2) lands far harder than reporting (5).
1. Less admin, more garden — plots, waitlists, and renewals stop living in a
   spreadsheet; members apply and reserve from your own garden page.
2. Get paid without chasing — dues generated per season, payment status at a
   glance, reminders that send themselves, money in your bank via Stripe.
3. Keep people showing up — events with RSVPs, volunteer shifts with capacity
   and logged hours, announcements that reach everyone by email and text.
4. One place for the whole garden — members, tools, photos, the community
   wall, harvest logs; nothing scattered across inboxes and group chats.
5. Prove it when it counts — participation and harvest data turned into a
   funder- or council-ready report in a couple of clicks.
6. Grows with you — one garden or a citywide network of them.

WHAT THE PRODUCT ACTUALLY DOES — the full surface. Pull the ONE or TWO
details that match what this reader is likely fighting with; never list
features, and never mention anything outside this list.
- Plots: bulk-add, assign, sizes/soil/sun notes, renewal dates, maintenance
  status, and a drag-and-drop garden map with paths, sheds, and water points.
- Waitlist and self-serve plot reservations from a public garden page, with
  applications you approve or decline (and an invite link to share).
- Members and roles (co-organizer, treasurer, volunteer lead), member
  directory, CSV export.
- Dues: generate for a season, track paid / partial / waived, record cash or
  check payments, send reminders, and take card payments with payouts landing
  in the garden's own bank account. Expenses logged by category, with a
  running financial summary.
- Events with RSVPs and attendee lists, including recurring workdays.
- Volunteer shifts with capacity, signups, attendance and logged hours.
- Announcements to every plot holder in-app, by email, and by SMS; direct and
  broadcast messaging; your own branding on the emails that go out.
- Tools and resources: an inventory with QR-code checkout, due dates, and
  condition/maintenance tracking.
- Community wall with automatic spam/abuse screening, and a photo gallery.
- Harvest logging by crop and destination (kept, shared, donated), which
  becomes the impact numbers.
- Impact and activity reports over any date range — pounds grown, meals
  shared, volunteer hours and their dollar value — printable or CSV.
- Frost, heat, and storm alerts for the garden's own location.
- A free tier that covers the public page, plots, waitlist, events,
  announcements, the community wall, resources, and bank payouts; Garden Pro
  (free trial) adds dues, messaging, photos, tool checkout, the map editor,
  and the funder reports.

WRITING RULES
- Lead with the reader's problem, not the product.
- Exactly ONE clear, low-friction call to action. The PREFERRED CTA when
  proposing a call or meeting is James's scheduling page —
  https://www.yardharvest.app/book — where the reader picks any open time for a
  30-minute intro call (no back-and-forth over availability). Link it naturally,
  e.g. "grab a time that works for you" with the URL as the link. Softer
  touches may instead invite a simple reply; never use both in one email.
- Cold outreach body: ~90-150 words, short skimmable paragraphs. Shorter is
  almost always better — a 70-word email that's easy to answer beats a
  polished 200-word one that isn't.
- Subject lines: 4-8 words, specific, like something a person would actually
  type. Use SENTENCE CASE — capitalize the first word and any proper noun
  (a person's name, a city, an organization, YardHarvest); everything else
  stays lowercase. "Waitlist for Maple Garden" — not "waitlist for maple
  garden" (sloppy) and not "Waitlist For Maple Garden" (newsletter). No
  "Re:" fakery, no clickbait, no emoji, no trailing period, never the
  company name alone.
- Personalize with merge tokens that the CRM fills per recipient. Available
  tokens: {{first_name}}, {{contact_name}}, {{company}}, {{city}}, {{state}},
  {{org_type}}, {{today}}. Write so the copy still reads naturally if a token
  renders blank. Do NOT invent other tokens.
- GREETING — this matters. Use "Hi {{first_name}}," ONLY when the lead
  context says the contact is a real person. When it says the contact is a
  shared inbox or a role (info@, "Garden Coordinator", the org's own name),
  write a neutral greeting — "Hi there," or "Hello," — and never guess a
  name. A misfired "Hi Info," or "Hi Community Garden," is the single most
  amateurish thing an email can do.
- Never use {{sender_name}} in the body. The CRM appends the signature.
- Never fabricate statistics, customer names, or testimonials.
- Honor consent / CAN-SPAM: honest subject line, no deceptive phrasing. The CRM
  adds the unsubscribe + physical-address footer, so do not invent one.
- The CRM also auto-appends the sender's signature block (James Goodman /
  Founder / YardHarvest.app) after the body. End with a short warm sign-off
  only (e.g. "Best," or "Talk soon,") — do NOT write out a name, title, or
  signature block yourself.
- Describe only capabilities the product actually has (see pillars above).
- No placeholders, ever: no [brackets], no "X", no TODO, no "insert…". If you
  don't know something, leave it out and write around it.
- Don't stack sign-offs, don't add a P.S. unless it carries real information,
  and never write "Sent from my iPhone" or similar.

WHAT "HELPFUL" LOOKS LIKE HERE (use these, they're true)
- The free 8-chapter Community Garden Guide (below) — share the ONE chapter
  that matches where they are right now.
- Practical, seasonal timing: plot renewals and waitlists spike late winter;
  city/parks budgets turn over around June 30; grant reports come due in the
  fall. Mentioning the right one at the right time reads as understanding,
  not selling.
- Naming the specific chore they're probably doing by hand this week (dues
  chasing, waitlist spreadsheet, volunteer sign-ups, harvest logs for a
  funder) is worth more than any feature list.

OUTPUT
Return a single campaign as JSON with: name (short internal label), subject
(<= 60 chars), and body (plain text with merge tokens). No markdown, no preamble.
"""


def _guide_library():
    """Content-library block for the system prompt, generated from the SEO
    layer's chapter registry (app.seo.GUIDE_META) — single source of truth,
    so a new guide chapter automatically reaches every agent skill."""
    try:
        from app.seo import GUIDE_META
    except Exception:
        return ''
    lines = '\n'.join(
        f'- {title}: https://www.yardharvest.app/about/guide/{slug}'
        for slug, (title, _desc) in GUIDE_META.items())
    return f"""

CONTENT LIBRARY — The Community Garden Guide
We publish a free, practical 8-chapter guide to starting and running a
community garden (hub: https://www.yardharvest.app/about/guide). Chapters:
{lines}

Sharing the ONE most relevant chapter is an excellent value-first CTA for cold
or early-stage outreach — it gives before it asks. Match the chapter to the
reader's situation (garden just forming → Getting Started; money worries →
Funding & Your First Budget; a city program or nonprofit → Harvest & Impact;
tired volunteer coordinator → Organizing People). Together with the signup,
pricing and booking pages named in VERIFIED FACTS below, these are the ONLY
URLs you may include. The one-CTA rule still applies: guide link OR signup
link OR booking link OR a reply invitation — never two."""


BRAND_VOICE = BRAND_VOICE + _guide_library()

CAMPAIGN_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "subject": {"type": "string"},
        "body": {"type": "string"},
    },
    "required": ["name", "subject", "body"],
    "additionalProperties": False,
}

FB_POST_SCHEMA = {
    "type": "object",
    "properties": {
        "message": {"type": "string"},
        "link": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
        "image_idea": {"type": "string"},
        "alternates": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["message"],
    "additionalProperties": False,
}

# One post idea per item for the agent's "propose a few posts" skill (the
# man-in-the-middle Facebook queue). Each is a finished, ready-to-edit draft.
FB_PROPOSALS_SCHEMA = {
    "type": "object",
    "properties": {
        "posts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "rationale": {"type": "string"},
                    "message": {"type": "string"},
                    "link": {"type": "string"},
                    "hashtags": {"type": "array", "items": {"type": "string"}},
                    "image_idea": {"type": "string"},
                },
                "required": ["title", "message"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["posts"],
    "additionalProperties": False,
}


def _clean_hashtags(raw, *, limit=5):
    """Normalize model-supplied hashtags: ensure a single leading '#', strip
    spaces, dedupe (case-insensitively), and cap the count."""
    out, seen = [], set()
    for h in (raw or []):
        h = str(h).strip().replace(' ', '')
        if not h:
            continue
        h = '#' + h.lstrip('#')
        if h == '#':
            continue
        key = h.lower()
        if key not in seen:
            seen.add(key)
            out.append(h)
        if len(out) >= limit:
            break
    return out

# One personalized follow-up email per due lead. ``lead_id`` is echoed back so
# the caller can map each draft to its contact.
FOLLOWUPS_SCHEMA = {
    "type": "object",
    "properties": {
        "drafts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "lead_id": {"type": "integer"},
                    "title": {"type": "string"},
                    "rationale": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["lead_id", "title", "rationale", "subject", "body"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["drafts"],
    "additionalProperties": False,
}

# Model tiers — match the model to how much judgment the job actually needs.
# Writing a cold email stopped being formulaic once BRAND_VOICE grew to carry
# the whole product: the writer now has to pick ONE of six pillars and one or
# two of a dozen capabilities that fit this particular reader. That is
# selection and synthesis, not template-filling, so it belongs on Sonnet.
#   DEFAULT_MODEL (Sonnet) — judgment work: ranking which leads to prospect,
#     web-sourced scouting, company enrichment, full campaign design.
#   EMAIL_MODEL (Sonnet)   — writing work: intros, follow-ups, campaign and
#     template copy, Facebook posts. First impression; worth the tier.
#   REPLY_MODEL (Sonnet)   — answering someone who actually replied. The
#     highest-stakes single email the agent sends.
#   QA_MODEL (Sonnet)      — the pre-send critic. A reviewer weaker than the
#     writer is a rubber stamp, so it matches the writer's tier.
#   TRIAGE_MODEL (Haiku)   — five-way reply classification. Genuinely simple,
#     runs on every poll; Haiku is the right tool and stays.
# Cost at the daily cap is a few dollars a month either way. Note BRAND_VOICE
# (~2.2k tokens) sits under Haiku 4.5's 4096-token cache floor but over
# Sonnet's 1024, so the system-prompt cache only actually engages on Sonnet.
# Every skill still accepts model= to override per call.
DEFAULT_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5")
EMAIL_MODEL = os.environ.get("CRM_EMAIL_MODEL", "claude-sonnet-5")

# Estimated API rates (USD) for spend visibility — token prices per 1M tokens,
# web search per 1K searches. Defaults from Anthropic pricing (mid-2026); update
# here if rates change. Powers the CRM's "AI usage" estimate only.
_MODEL_RATES = {
    'claude-fable-5': (10.0, 50.0),
    'claude-opus-5': (5.0, 25.0),
    'claude-opus-4-8': (5.0, 25.0),
    'claude-opus-4-7': (5.0, 25.0),
    # Sonnet 5 list price. Introductory pricing (2.00/10.00) runs through
    # 2026-08-31, so this over-estimates slightly until then — deliberate:
    # the usage panel should never under-report what the agent is spending.
    'claude-sonnet-5': (3.0, 15.0),
    'claude-sonnet-4-6': (3.0, 15.0),
    'claude-haiku-4-5': (1.0, 5.0),
}
_WEB_SEARCH_USD_PER_1K = 10.0


def _effort(model, level="medium"):
    """Extra `output_config` keys for models that accept an effort level.

    On the Claude 5 family, omitting `thinking` means adaptive thinking runs by
    default and `max_tokens` caps thinking *plus* the answer — so every call
    below carries headroom and an explicit effort. Haiku 4.5 and Sonnet 4.5
    reject `effort` outright, so they get nothing; this matters because every
    model here is env-overridable. Merge the result into output_config."""
    m = (model or '').strip()
    if 'haiku' in m or 'sonnet-4-5' in m or 'opus-4-5' in m:
        return {}
    return {"effort": level}


def estimate_cost(model, input_tokens=0, output_tokens=0, web_searches=0):
    """Rough USD estimate for one agent run (tokens + web searches). Unknown
    models fall back to Opus rates. Estimate only — see _MODEL_RATES."""
    in_rate, out_rate = _MODEL_RATES.get((model or '').strip(), (5.0, 25.0))
    return round((int(input_tokens or 0) / 1_000_000) * in_rate
                 + (int(output_tokens or 0) / 1_000_000) * out_rate
                 + (int(web_searches or 0) / 1000) * _WEB_SEARCH_USD_PER_1K, 4)

# ---------------------------------------------------------------------------
# AI Studio — full campaign design (targeting + email + content plan)
# ---------------------------------------------------------------------------
CONTENT_CHANNELS = ["Email", "Social", "Blog", "Event", "Ad"]

DESIGN_EXTENSION = """

You are also the marketing director: when asked for a FULL CAMPAIGN DESIGN,
go beyond the email and produce targeting plus a supporting content plan.

CONTENT PLAN RULES
- 3 to 6 supporting items across channels (Email, Social, Blog, Event, Ad)
  that reinforce the campaign over the following weeks.
- Each item gets a concrete working title, a channel, a short note on the
  angle/outline, and a day offset from today for scheduling.
- Sequence sensibly: tease -> send -> follow up -> amplify.

TARGETING RULES
- Choose audience filters (US state code, org type, tag) that best fit the
  goal. Leave a filter empty ("") to include everyone on that dimension.
- org_type must be "" or "Independent" or "City-Sponsored".
"""

DESIGN_SCHEMA = {
    "type": "object",
    "properties": {
        "strategy_summary": {
            "type": "string",
            "description": "2-3 sentence rationale for the design",
        },
        "campaign": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
                "audience": {
                    "type": "object",
                    "properties": {
                        "state": {"type": "string"},
                        "org_type": {
                            "type": "string",
                            "enum": ["", "Independent", "City-Sponsored"],
                        },
                        "tag": {"type": "string"},
                    },
                    "required": ["state", "org_type", "tag"],
                    "additionalProperties": False,
                },
            },
            "required": ["name", "subject", "body", "audience"],
            "additionalProperties": False,
        },
        "content_plan": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "channel": {"type": "string", "enum": CONTENT_CHANNELS},
                    "days_from_now": {"type": "integer"},
                    "notes": {"type": "string"},
                },
                "required": ["title", "channel", "days_from_now", "notes"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["strategy_summary", "campaign", "content_plan"],
    "additionalProperties": False,
}


class AgentError(RuntimeError):
    """Raised when the AI draft can't be produced (config or API failure)."""


def is_configured():
    """True when the agent can run: the SDK is importable and a key is set."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
        return True
    except ImportError:
        return False


def auth_ok():
    """Real credential check: does the key authenticate with Anthropic?

    Uses a free ``models.list()`` call (no token/generation cost) so it's safe
    to expose as an ops health probe. Returns False on any failure (bad key,
    missing SDK, network error).
    """
    if not is_configured():
        return False
    try:
        import anthropic
        anthropic.Anthropic().models.list(limit=1)
        return True
    except Exception:
        return False


def _sample_lines(sample_recipients):
    lines = "\n".join(
        f"- {c.get('first_name') or c.get('name') or 'A contact'} at "
        f"{c.get('company') or 'an organization'} "
        f"({c.get('city') or '?'}, {c.get('state') or '?'}; "
        f"{c.get('org_type') or 'unknown type'})"
        for c in (sample_recipients or [])
    )
    return lines or "(no sample available)"


def draft_campaign(goal, *, segments=None, sample_recipients=None,
                   audience_count=0, model=None):
    """Ask Claude to draft a campaign. Returns (campaign_dict, usage_dict).

    campaign_dict has keys name/subject/body. Raises AgentError on any failure
    so the caller can flash a friendly message.
    """
    if not is_configured():
        raise AgentError(
            "AI drafting isn't configured. Set ANTHROPIC_API_KEY (and install "
            "the anthropic package) to enable it.")

    import anthropic

    user_prompt = f"""Write ONE outreach email campaign for this goal:

GOAL: {goal}

AUDIENCE SIZE: {audience_count} recipients (opted-out contacts are already
excluded by the CRM).

SAMPLE RECIPIENTS:
{_sample_lines(sample_recipients)}

CRM SEGMENT TOTALS (for context):
{json.dumps(segments or {}, indent=2)}

Write the campaign now. Personalize with merge tokens so each recipient sees
their own name/org/location. Return JSON only: name, subject, body."""

    try:
        mdl = model or EMAIL_MODEL
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=mdl,
            max_tokens=6000,
            system=[{
                "type": "text",
                "text": brand_voice(),
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": user_prompt}],
            output_config={"format": {"type": "json_schema",
                                      "schema": CAMPAIGN_SCHEMA}, **_effort(mdl)},
        )
    except Exception as e:  # network / auth / SDK errors
        raise AgentError(f"The AI request failed: {e}") from e

    try:
        text = next(b.text for b in resp.content if b.type == "text")
        campaign = json.loads(text)
        # Minimal shape guard
        for key in ("name", "subject", "body"):
            if not campaign.get(key):
                raise KeyError(key)
        campaign["subject"] = normalize_subject(campaign["subject"])
    except (StopIteration, ValueError, KeyError) as e:
        raise AgentError("The AI returned an unexpected response. Try again "
                         "or adjust the goal.") from e

    u = getattr(resp, "usage", None)
    usage = {
        "input_tokens": getattr(u, "input_tokens", 0),
        "output_tokens": getattr(u, "output_tokens", 0),
        "cache_read": getattr(u, "cache_read_input_tokens", 0),
    } if u else {}
    return campaign, usage


def draft_template(purpose, *, model=None):
    """Ask Claude to draft a reusable email template (name/subject/body) for a
    described purpose. Returns the validated dict. Raises AgentError on failure.

    Unlike a campaign, a template is reused across many recipients/contexts, so
    it should lean on merge tokens and stay broadly applicable.
    """
    if not is_configured():
        raise AgentError(
            "AI drafting isn't configured. Set ANTHROPIC_API_KEY (and install "
            "the anthropic package) to enable it.")

    import anthropic

    user_prompt = f"""Write ONE reusable email TEMPLATE for this purpose:

PURPOSE: {purpose}

This template is saved once and reused for many recipients across the CRM, so:
- Personalize with merge tokens ({{{{first_name}}}}, {{{{company}}}}, {{{{city}}}},
  {{{{state}}}}, {{{{org_type}}}}, {{{{sender_name}}}}, {{{{today}}}}) so each send
  reads personally; write so it still reads naturally if a token is blank.
- Keep it broadly applicable to the purpose (not tied to one specific recipient
  or a one-time event date) so it stays reusable.

Write the body as simple, email-safe HTML — use <p>, <h2>, <strong>, <em>,
<a href>, and <ul>/<li> only (NO <html>/<head>/<style>/<script>, no full
document; just the inner content). Keep merge tokens inside the HTML. Where a
photo would strengthen the email, add a short placeholder paragraph like
<p>[Add a photo here: a garden in season]</p> (do NOT invent <img> URLs) so the
sender can drop in a real image.

Return JSON only: name (short internal label for this template), subject
(<= 60 chars), body (the email-safe HTML described above with merge tokens)."""

    try:
        mdl = model or EMAIL_MODEL
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=mdl,
            max_tokens=6000,
            system=[{
                "type": "text",
                "text": brand_voice(),
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": user_prompt}],
            output_config={"format": {"type": "json_schema",
                                      "schema": CAMPAIGN_SCHEMA}, **_effort(mdl)},
        )
    except Exception as e:  # network / auth / SDK errors
        raise AgentError(f"The AI request failed: {e}") from e

    if getattr(resp, "stop_reason", None) == "refusal":
        raise AgentError("Claude declined to write this template — try "
                         "rephrasing the purpose.")
    try:
        text = next(b.text for b in resp.content if b.type == "text")
        template = json.loads(text)
        for key in ("name", "subject", "body"):
            if not template.get(key):
                raise KeyError(key)
    except (StopIteration, ValueError, KeyError) as e:
        raise AgentError("The AI returned an unexpected response. Try again "
                         "or adjust the purpose.") from e
    template["subject"] = normalize_subject(template.get("subject"))
    return template


def _book_url():
    """The founder's scheduling page — from SITE_URL so non-prod hosts don't
    advertise the production URL; falls back to prod when no app context."""
    try:
        from flask import current_app
        base = (current_app.config.get('SITE_URL') or '').rstrip('/')
        if base:
            return f'{base}/book'
    except Exception:
        pass
    return 'https://www.yardharvest.app/book'


def _site_url(path=''):
    """A URL on the public site, from SITE_URL so a non-prod host never
    advertises production. Falls back to prod outside an app context."""
    base = 'https://www.yardharvest.app'
    try:
        from flask import current_app
        base = (current_app.config.get('SITE_URL') or base).rstrip('/')
    except Exception:
        pass
    return f'{base}{path}'


def _facts_block():
    """The commercial facts the writer is otherwise forbidden to state.

    BRAND_VOICE tells the model never to invent a price, and nothing told it
    the real one — so "how much is it?" cost a manual round-trip and every
    cold email asked a volunteer for a 30-minute call instead of pointing at
    a free signup. Resolved per call from the admin console's pricing
    (app.pricing.garden_pro_pricing) and SITE_URL, so a price change reaches
    the next email without a deploy and nothing here can drift.
    """
    from app.pricing import garden_pro_pricing
    pro = garden_pro_pricing()
    monthly, yearly, trial = pro['monthly'], pro['yearly'], pro['trial_days']
    money = lambda v: (f'${v:,.0f}' if float(v) == int(v) else f'${v:,.2f}')  # noqa: E731
    annual_saving = monthly * 12 - yearly
    saving_txt = (f' (saves {money(annual_saving)} against paying monthly)'
                  if annual_saving > 0 else '')
    return f"""

VERIFIED FACTS — you may state these exactly; never guess a number or a URL.
- Free plan, no card, no time limit: the public garden page, plots and the
  map, the waitlist and self-serve reservations, members and roles, events
  and RSVPs, announcements, the community wall, shared resources, and bank
  payouts. A garden can run on this forever.
- Garden Pro adds dues (generate, track, remind, collect, pay out), member
  messaging and SMS, the photo gallery, tool checkout, the map editor, and
  the funder-ready impact reports.
- Garden Pro costs {money(monthly)}/month or {money(yearly)}/year{saving_txt},
  after a {trial}-day free trial that does not ask for a card.
- Signing up is free and takes about ten minutes: {_site_url('/register')}
  creates the account and the garden's page.
- Full pricing: {_site_url('/pricing')}. Book a 30-minute call: {_site_url('/book')}.

CHOOSING THE CALL TO ACTION — one per email, matched to who is reading.
- A volunteer-run independent garden has no budget line and no procurement
  process. Do NOT open by asking for a 30-minute call; the ask is too big for
  a stranger's inbox. Point at the free plan — "set your garden's page up in
  about ten minutes, free" — or share the ONE guide chapter that fits.
- A nonprofit, a multi-garden operator, a city or parks program has staff,
  budget and a decision process. A call is proportionate: use the booking
  page.
- Anyone who has already replied: answer what they asked, then offer the one
  next step that follows from it — a call, the free signup, or nothing.
- Never state a price the reader did not ask about. If they ask, give the
  real one from the facts above."""


def brand_voice():
    """The system prompt: the stable voice plus the facts that can change.

    Resolved per call rather than frozen at import, so the price the agent
    quotes is the price the admin console holds today."""
    return BRAND_VOICE + _facts_block()


def _lead_block(lead):
    """One compact, fact-only context line per lead for the follow-up prompt.

    When the caller supplies touch context (``touch_number``/``max_touches``/
    ``prior_emails``/``angle`` — the autonomous cycle does), it is appended so
    the model can write touch 2 differently from touch 1 and make the final
    touch a polite break-up instead of another cold intro."""
    recent = lead.get('recent') or []
    recent_txt = '; '.join(recent[:4]) if recent else 'no prior activity logged'
    dsc = lead.get('days_since_contact')
    contacted = (f'{dsc} days since last contact' if dsc is not None
                 else 'never contacted')
    line = (
        f"lead_id={lead.get('lead_id')} | {lead.get('name') or 'A contact'}"
        f" at {lead.get('company') or 'an organization'}"
        f" ({lead.get('city') or '?'}, {lead.get('state') or '?'};"
        f" {lead.get('org_type') or 'unknown type'})"
        f" | status={lead.get('lead_status') or 'New'} | {contacted}"
        f" | recent: {recent_txt}"
    )
    # What we already know about them. The CRM was holding researched notes,
    # a website and tags and handing the writer none of it, so every email
    # opened on a generality.
    if lead.get('website'):
        line += f" | website: {lead['website']}"
    if lead.get('tags'):
        line += f" | tags: {lead['tags']}"
    facts = [f for f in (lead.get('facts_on_file') or []) if f]
    if facts:
        joined = ' // '.join(' '.join(str(f).split())[:180] for f in facts[:3])
        line += f" | facts on file: {joined}"
    tn = lead.get('touch_number')
    if tn:
        mx = lead.get('max_touches') or 3
        line += f" | touch {tn} of {mx}" + (" (FINAL touch)" if lead.get('is_final') else "")
    if lead.get('angle'):
        line += f" | suggested angle: {str(lead['angle'])[:160]}"
    prior = lead.get('prior_emails') or []
    if prior:
        parts = []
        for i, pe in enumerate(prior[:3], 1):
            when = pe.get('date') or ''
            parts.append(f'[{i}{" " + when if when else ""}] "{(pe.get("subject") or "")[:80]}"'
                         f' — {(pe.get("snippet") or "")[:140]}')
        line += " | prior emails sent: " + " ; ".join(parts)
    return line


def draft_followups(leads, *, sender_name='', model=None):
    """Draft a personalized follow-up email for each due lead.

    ``leads`` is a list of fact-only context dicts (lead_id, name, company,
    city, state, org_type, lead_status, days_since_contact, recent[]). Returns
    (drafts, usage) where each draft is {lead_id, title, rationale, subject,
    body}. ``body`` is email-safe HTML (rendered in the rich editor and sent via
    render_sales_email) — same format the composer/template generator uses. The
    agent proposes; a human approves before anything sends. Raises AgentError on
    any failure so the caller can flash a friendly message.
    """
    if not is_configured():
        raise AgentError(
            "AI drafting isn't configured. Set ANTHROPIC_API_KEY (and install "
            "the anthropic package) to enable it.")
    if not leads:
        return [], {}

    import anthropic

    blocks = "\n".join(_lead_block(ld) for ld in leads)
    book = _book_url()
    user_prompt = f"""You are doing outbound BDR follow-ups for {sender_name or 'the YardHarvest team'}.

For EACH lead below, write one short, warm follow-up email that moves the
conversation toward a 30-minute intro call. The call-to-action for a call is
the scheduling page: link <a href="{book}">{book}</a> (the reader picks any
open time — no back-and-forth). For a COLD lead (never contacted, or no
engagement across prior touches), a value-first CTA often works better: share
the single most relevant Community Garden Guide chapter from the content
library instead of asking for a call — give before you ask. One CTA either
way. These are real prospects pulled from the CRM — use ONLY the context
given. Do not invent facts, statistics, prior conversations, names, or
commitments that aren't shown here.

TOUCH RULES (when a lead line shows "touch N of M"):
- Touch 1 = the cold intro: value-first, lead with their situation, one guide
  chapter or the booking link.
- Touch 2 = a short bump (60-100 words) that adds ONE new angle not used
  before; you may reference the earlier note lightly ("I sent a note last
  week about…") but never re-paste it.
- The FINAL touch = a polite break-up: acknowledge the timing may be off,
  leave exactly one link, and make it easy to say "not now" — no guilt, no
  pressure, no fake urgency.
- The lead line lists the subjects/openings of emails ALREADY SENT. Never
  reuse a prior subject line or opening sentence; vary the angle each time.

For each lead also give:
- title: a 5-8 word summary of the step (e.g. "Follow up with Maria re: dues")
- rationale: ONE sentence on why now, grounded in the lead's real status /
  days-since-contact / recent activity shown below.

Personalize with merge tokens ({{{{first_name}}}}, {{{{company}}}}, {{{{city}}}},
{{{{state}}}}, {{{{org_type}}}}, {{{{sender_name}}}}) so each email renders per
recipient; write so it still reads naturally if a token is blank.

Write each `body` as simple, email-safe HTML — use <p>, <strong>, <em>, <a href>,
and <ul>/<li> only (NO <html>/<head>/<style>/<script>, no full document; just the
inner content), keeping the merge tokens inside the HTML. Keep it short and warm
(~90-150 words) with ONE clear low-friction call to action. Do NOT invent <img>
URLs. The CRM appends the unsubscribe/address footer — don't add one.

LEADS:
{blocks}

Return JSON only: {{ "drafts": [ {{lead_id, title, rationale, subject, body}} ] }}
with exactly one draft per lead_id above."""

    try:
        mdl = model or EMAIL_MODEL
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=mdl,
            max_tokens=12000,
            system=[{
                "type": "text",
                "text": brand_voice(),
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": user_prompt}],
            output_config={"format": {"type": "json_schema",
                                      "schema": FOLLOWUPS_SCHEMA}, **_effort(mdl)},
        )
    except Exception as e:
        raise AgentError(f"The AI request failed: {e}") from e

    try:
        text = next(b.text for b in resp.content if b.type == "text")
        drafts = json.loads(text).get("drafts", [])
    except (StopIteration, ValueError) as e:
        raise AgentError("The AI returned an unexpected response. Try again.") from e

    # Keep only well-formed drafts that map to a lead we asked about.
    valid_ids = {ld.get('lead_id') for ld in leads}
    clean = [d for d in drafts
             if d.get('lead_id') in valid_ids and d.get('subject') and d.get('body')]
    for d in clean:
        d['subject'] = normalize_subject(d.get('subject'))

    u = getattr(resp, "usage", None)
    usage = {
        "input_tokens": getattr(u, "input_tokens", 0),
        "output_tokens": getattr(u, "output_tokens", 0),
        "cache_read": getattr(u, "cache_read_input_tokens", 0),
    } if u else {}
    return clean, usage


# ---------------------------------------------------------------------------
# Inbound replies — triage + response drafting (autonomous loop feedback)
# ---------------------------------------------------------------------------
# Sorting a reply into one of five buckets is simple, runs on every 15-minute
# poll, and is latency-sensitive — Haiku's job. Override with CRM_TRIAGE_MODEL.
TRIAGE_MODEL = os.environ.get("CRM_TRIAGE_MODEL", "claude-haiku-4-5")
# Writing the answer is not simple: someone real replied and this is the email
# that decides whether the conversation continues. Override with CRM_REPLY_MODEL.
REPLY_MODEL = os.environ.get("CRM_REPLY_MODEL", EMAIL_MODEL)
# The pre-send quality gate (see review_email). A second model re-reading the
# draft as a critic catches more than asking the writer to check its own work —
# but only if the critic is at least as sharp as the writer. Matches EMAIL_MODEL
# by default. Override with CRM_QA_MODEL.
QA_MODEL = os.environ.get("CRM_QA_MODEL", EMAIL_MODEL)

REPLY_CLASSES = ('interested', 'no_budget', 'not_interested', 'unsubscribe',
                 'out_of_office', 'other')

CLASSIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "classification": {"type": "string", "enum": list(REPLY_CLASSES)},
        "summary": {"type": "string"},
        "suggested_next_step": {"type": "string"},
    },
    "required": ["classification", "summary", "suggested_next_step"],
    "additionalProperties": False,
}

CLASSIFY_SYSTEM = """You triage replies to one-to-one sales outreach from YardHarvest
(software for community gardens and city garden programs). Classify the INBOUND
message into exactly one class:
- interested: wants to talk, asks a question, requests info/pricing/a demo, or is
  otherwise warm — even briefly ("sure, tell me more").
- no_budget: the ONLY reason they say no is money — "no budget", "we can't
  afford it", "we're all volunteers", "maybe next fiscal year". This is not a
  rejection: the product has a free plan that covers most of what a garden
  does, so it is the moment to say so. Use it whenever cost is the stated
  obstacle, even alongside mild interest.
- not_interested: declines for any other reason — "not a fit", "we already
  use X", "too small" — any soft or hard no that is NOT about money and NOT
  a request to stop all email.
- unsubscribe: asks to stop emails / remove them / do not contact (any phrasing).
- out_of_office: an automatic away/leave notice. A human who names a
  colleague to talk to instead is 'other', not this — that is a referral and
  a person needs to read it.
- other: unclear, wrong person, needs a human to read it.
Return JSON only: {"classification": ..., "summary": "<=160 chars, plain, factual",
"suggested_next_step": "<=120 chars"}. Never invent facts not in the message."""

_UNSUB_RE = re.compile(
    r"\b(unsubscribe|remove me|take me off|stop (emailing|sending|contacting)|"
    r"do not (contact|email)|no more emails|opt[ -]?out)\b", re.I)


def classify_reply(text, *, subject='', model=None):
    """Triage an inbound reply. Returns (dict{classification, summary,
    suggested_next_step}, usage). Deterministic pre-check: an explicit
    unsubscribe request never needs the model. Raises AgentError on failure."""
    body = (text or '').strip()
    if _UNSUB_RE.search(f"{subject}\n{body}"):
        return ({"classification": "unsubscribe",
                 "summary": "Asked to stop receiving email.",
                 "suggested_next_step": "Suppress the address; no further outreach."}, {})
    if not is_configured():
        raise AgentError("AI isn't configured (ANTHROPIC_API_KEY).")
    import anthropic
    prompt = (f"Subject: {subject or '(none)'}\n\nMessage:\n{body[:4000] or '(empty)'}\n\n"
              "Classify this reply.")
    try:
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=model or TRIAGE_MODEL, max_tokens=400,
            system=[{"type": "text", "text": CLASSIFY_SYSTEM,
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": prompt}],
            output_config={"format": {"type": "json_schema", "schema": CLASSIFY_SCHEMA}},
        )
    except Exception as e:
        raise AgentError(f"The AI request failed: {e}") from e
    try:
        out = json.loads(next(b.text for b in resp.content if b.type == "text"))
    except (StopIteration, ValueError) as e:
        raise AgentError("The AI returned an unexpected response.") from e
    if out.get("classification") not in REPLY_CLASSES:
        out["classification"] = "other"
    u = getattr(resp, "usage", None)
    usage = {"input_tokens": getattr(u, "input_tokens", 0),
             "output_tokens": getattr(u, "output_tokens", 0)} if u else {}
    return out, usage


REPLY_SCHEMA = {
    "type": "object",
    "properties": {"subject": {"type": "string"}, "body": {"type": "string"}},
    "required": ["subject", "body"],
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------
# Pre-send quality check — the last thing between a draft and a real person
# ---------------------------------------------------------------------------
# Names that are NOT a person: shared inboxes, roles, and org-ish words. When a
# contact's "name" looks like one of these, greeting them by it ("Hi Info,")
# instantly marks the email as machine-generated.
_NON_PERSON_TOKENS = {
    'info', 'admin', 'administrator', 'office', 'contact', 'team', 'staff',
    'hello', 'hi', 'mail', 'email', 'inbox', 'general', 'main', 'support',
    'help', 'volunteer', 'volunteers', 'coordinator', 'director', 'manager',
    'president', 'secretary', 'treasurer', 'board', 'committee', 'chair',
    'garden', 'gardens', 'community', 'city', 'parks', 'recreation', 'dept',
    'department', 'nonprofit', 'foundation', 'association', 'society',
    'network', 'alliance', 'coalition', 'project', 'program', 'center',
    'centre', 'farm', 'farms', 'org', 'organization', 'us', 'we', 'noreply',
    'no-reply', 'webmaster', 'postmaster', 'events', 'membership',
}
# Titles that mean the "name" is a role, even when combined with other words.
_ROLE_PHRASES = ('coordinator', 'director', 'manager', 'president', 'chair',
                 'secretary', 'treasurer', 'volunteer', 'office', 'department',
                 'board', 'committee', 'program', 'garden', 'parks')


def is_placeholder_name(name):
    """True when *name* is a shared inbox / role / organization rather than a
    person — i.e. it must never be used as a first name in a greeting."""
    raw = (name or '').strip()
    if not raw:
        return True
    # Our own scout/enrichment placeholder, e.g. "Info — Maple Garden"
    if raw.lower().startswith(('info —', 'info -', 'info@', 'contact —', 'contact -')):
        return True
    cleaned = re.sub(r'[^\w\s\'-]', ' ', raw).strip()
    words = [w for w in cleaned.split() if w]
    if not words:
        return True
    low = [w.lower() for w in words]
    if low[0] in _NON_PERSON_TOKENS:
        return True
    if any(p in ' '.join(low) for p in _ROLE_PHRASES):
        return True
    # "MAPLE GARDEN ASSOCIATION" / single word that's clearly not a given name
    if len(words) == 1 and (len(words[0]) < 2 or words[0].isupper()):
        return True
    return False


_HONORIFICS = {'mr', 'mrs', 'ms', 'miss', 'mx', 'dr', 'prof', 'rev', 'fr', 'sr',
               'hon', 'councilmember', 'councilman', 'councilwoman'}


def first_name_of(name):
    """The greeting name, or '' when the contact isn't a person. Skips
    honorifics so "Dr. Jane Smith" greets Jane, not "Dr."."""
    if is_placeholder_name(name):
        return ''
    parts = [p for p in (name or '').strip().split() if p]
    for p in parts:
        if p.strip('.').lower() in _HONORIFICS:
            continue
        return p
    return ''


_LINT_BANNED = (
    ('i hope this email finds you well', 'opens with "I hope this email finds you well"'),
    ('hope this email finds you well', 'opens with "hope this email finds you well"'),
    ('hope you are doing well', 'opens with "hope you are doing well"'),
    ('hope you’re doing well', 'opens with "hope you’re doing well"'),
    ('i wanted to reach out', 'uses "I wanted to reach out"'),
    ('i am reaching out', 'uses "I am reaching out"'),
    ('i’m reaching out', 'uses "I’m reaching out"'),
    ('just circling back', 'uses "just circling back"'),
    ('per my last email', 'uses "per my last email"'),
    ('dear sir', 'uses "Dear Sir/Madam"'),
    ('to whom it may concern', 'uses "To whom it may concern"'),
    ('sent from my iphone', 'contains a phone signature'),
    ('lorem ipsum', 'contains placeholder text'),
    ('game-changing', 'uses hype language'),
    ('revolutionary', 'uses hype language'),
)

_SIGNOFF_RE = re.compile(
    r'(best|thanks|cheers|regards|warmly|talk soon|sincerely)[,\s]*(<[^>]+>\s*)*'
    r'(james|j\.?\s*goodman)', re.I)
_TITLE_RE = re.compile(r'\b(founder|yardharvest\.app)\b', re.I)
_TOKEN_RE = re.compile(r'\{\{\s*(\w+)\s*\}\}')
_BRACKET_RE = re.compile(r'\[(?!/?\w+\])[^\]]{1,40}\]')     # [First Name], [X] — not [1]
_ALLOWED_TOKENS = {'first_name', 'contact_name', 'company', 'city', 'state',
                   'org_type', 'today', 'tracking_token'}


_SUBJECT_FIXUPS = ((re.compile(r'\byardharvest\b'), 'YardHarvest'),)


def normalize_subject(subject):
    """Sentence-case a drafted subject line deterministically.

    BRAND_VOICE asks for sentence case, and the model mostly complies — but it
    drifts to all-lowercase often enough to look sloppy, and occasionally
    leaves a trailing period. Bouncing a draft through the review loop for
    something this mechanical is a waste, so fix it at the source: every
    drafted subject passes through here before it reaches the queue, which
    also keeps the preview and the sent mail identical. Merge tokens and
    deliberate capitalisation elsewhere in the line are left alone."""
    subj = re.sub(r'\s+', ' ', (subject or '')).strip()
    if not subj:
        return ''
    for pattern, replacement in _SUBJECT_FIXUPS:
        subj = pattern.sub(replacement, subj)
    trimmed = subj.rstrip('. ').strip()   # a trailing "?" is fine; "." is not
    subj = trimmed or subj
    if subj[:1].islower():                # never touch a leading {{token}}
        subj = subj[0].upper() + subj[1:]
    return subj


def lint_email(subject, body, *, contact_name=None, personal=None, allow_greeting_name=None):
    """Deterministic pre-send checks. Returns a list of plain-English issues
    (empty = looks fine). Cheap, runs on every autonomous send before the
    model-based review; catches the failures that embarrass us most."""
    issues = []
    subj = (subject or '').strip()
    raw_body = (body or '')
    text = re.sub(r'<[^>]+>', ' ', raw_body)
    text = re.sub(r'\s+', ' ', text).strip()
    low_all = f'{subj}\n{text}'.lower()

    if not subj:
        issues.append('the subject line is empty')
    elif len(subj) > 78:
        issues.append('the subject line is too long (over 78 characters)')
    if subj.endswith(('.', '!')):
        issues.append('the subject line ends with punctuation')
    if subj[:1].islower():
        issues.append('the subject line starts with a lowercase letter')
    words = [w for w in re.findall(r'[A-Za-z][\w\'-]*', subj)]
    if len(words) >= 4 and all(w[0].isupper() for w in words):
        issues.append('the subject line is in Title Case (reads like a newsletter)')
    if not text:
        issues.append('the body is empty')
    elif len(text.split()) > 220:
        issues.append('the body is too long for cold outreach (over 220 words)')

    # Greeting / name sanity — the big one.
    personal = (not is_placeholder_name(contact_name)) if personal is None else personal
    if allow_greeting_name is None:
        allow_greeting_name = personal
    greeting = re.match(r'^\s*(hi|hello|hey|dear|greetings)[ ,]+([^,<\n!.]{0,40})', text, re.I)
    if greeting:
        who = (greeting.group(2) or '').strip()
        if not who or who in (',', '-'):
            issues.append('the greeting has no name after it ("Hi ,")')
        elif not allow_greeting_name and who.lower() not in ('there', 'all', 'everyone', 'folks', 'team'):
            issues.append(f'greets a non-person by name ("{greeting.group(1)} {who}") — '
                          f'this contact is a shared inbox or a role')
        elif contact_name and personal and who.lower() not in (contact_name or '').lower() \
                and '{{' not in greeting.group(0):
            issues.append(f'greets "{who}" but the contact is "{contact_name}"')
    if re.search(r'\b(hi|hello|hey|dear)\s*,', text[:60], re.I):
        issues.append('the greeting has no name after it ("Hi ,")')

    # Signature / sender-name duplication (the CRM appends the real one).
    if _SIGNOFF_RE.search(raw_body) or _TITLE_RE.search(text):
        issues.append('writes out a name/title/signature — the CRM appends it automatically')
    if '{{sender_name}}' in raw_body:
        issues.append('uses {{sender_name}} in the body (the signature is appended)')

    # Merge tokens.
    for t in set(_TOKEN_RE.findall(raw_body)) | set(_TOKEN_RE.findall(subj)):
        if t not in _ALLOWED_TOKENS:
            issues.append(f'uses an unknown merge token {{{{{t}}}}}')
    if _BRACKET_RE.search(text):
        issues.append('contains an unfilled placeholder in [brackets]')

    for needle, msg in _LINT_BANNED:
        if needle in low_all:
            issues.append(msg)
    if text.count('!') > 1:
        issues.append('uses more than one exclamation mark')
    if re.search(r'\b[A-Z]{4,}\b', text):
        issues.append('shouts in ALL CAPS')
    if len(re.findall(r'https?://', raw_body)) > 2:
        issues.append('includes more than two links')
    # One CTA: a booking link AND a guide link AND "reply" is three asks.
    asks = sum([bool(re.search(r'/book\b', raw_body)),
                bool(re.search(r'/about/guide', raw_body)),
                bool(re.search(r'/register\b', raw_body)),
                bool(re.search(r'\b(just )?(reply|let me know|hit reply)\b', text, re.I))])
    if asks > 1:
        issues.append('has more than one call to action')
    return issues


REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["send", "fixed", "hold"]},
        "issues": {"type": "array", "items": {"type": "string"}},
        "subject": {"type": "string"},
        "body": {"type": "string"},
    },
    "required": ["verdict", "issues", "subject", "body"],
    "additionalProperties": False,
}

REVIEW_SYSTEM = """You are the last set of eyes on a cold email before it is sent
to a real person by a one-person company. Your job is to catch anything that
would make the sender look careless, automated, or amateurish — and to fix it.

Check, in this order:
1. GREETING AND NAME. If the recipient is a shared inbox or a role (info@,
   "Garden Coordinator", the organization's own name), the email must NOT
   greet them by that name — "Hi Info," or "Hi Community Garden," is fatal.
   Use "Hi there," instead. If the recipient IS a person, the greeting must
   use their actual first name (or the {{first_name}} token), spelled right.
2. NO SIGNATURE IN THE BODY. The system appends "James Goodman / Founder /
   YardHarvest.app" after the body. The body must end with a short sign-off
   only ("Best," / "Thanks,") and must never write out a name, title,
   company, or contact block — that would print it twice.
3. PLACEHOLDERS AND TOKENS. No [brackets], no "X", no TODO, no unknown
   {{tokens}}. Allowed tokens: {{first_name}}, {{contact_name}}, {{company}},
   {{city}}, {{state}}, {{org_type}}, {{today}}. Copy must read naturally if
   a token is blank.
4. TONE. Warm, plain, human, useful. No "I hope this email finds you well",
   no "just circling back", no hype, no ALL CAPS, at most one exclamation
   mark, no guilt or false urgency, no invented facts about their garden.
5. ONE ask. A booking link OR a guide link OR an invitation to reply — not
   two, not three. At most two links total.
6. Claims. Nothing invented: no statistics, customers, testimonials, or
   references to conversations/visits that aren't in the context given.

Then decide:
- "send" — it's good as-is (issues: []).
- "fixed" — you corrected it; return the corrected subject and body.
- "hold" — it needs a human (fabricated claims, or you cannot fix it without
  inventing facts). Explain why in issues.

Preserve the writer's voice and any true personalization. Keep the body as
email-safe HTML (<p>, <strong>, <em>, <a href>, <ul>/<li> only). Never make
an email longer. Return JSON only."""


def review_email(subject, body, *, contact_name=None, personal=None, company=None,
                 touch_number=None, known_issues=None, model=None):
    """Second-pass quality gate: a cheap model re-reads the draft as a critic
    and either approves it, returns a corrected version, or holds it for a
    human. Returns ({verdict, issues, subject, body}, usage).

    Falls back to ('send' with the deterministic issues) if AI isn't
    configured, so lint alone still governs."""
    if not is_configured():
        return ({'verdict': 'send', 'issues': list(known_issues or []),
                 'subject': subject, 'body': body}, {})
    import anthropic
    personal = (not is_placeholder_name(contact_name)) if personal is None else personal
    who = (f'{contact_name} at {company}' if company else (contact_name or 'the recipient'))
    prompt = f"""RECIPIENT: {who}
This recipient IS {'a real person — greet them by first name' if personal else
                  'NOT a person (shared inbox or role) — use a neutral greeting, never a name'}.
{f'This is touch {touch_number} in a sequence.' if touch_number else ''}
{('Automated checks already flagged: ' + '; '.join(known_issues)) if known_issues else ''}

SUBJECT: {subject}

BODY:
{body}

Review and return JSON."""
    try:
        mdl = model or QA_MODEL
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=mdl, max_tokens=5000,
            system=[{"type": "text", "text": REVIEW_SYSTEM,
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": prompt}],
            output_config={"format": {"type": "json_schema",
                                      "schema": REVIEW_SCHEMA}, **_effort(mdl)},
        )
    except Exception as e:
        raise AgentError(f"The AI request failed: {e}") from e
    try:
        out = json.loads(next(b.text for b in resp.content if b.type == "text"))
    except (StopIteration, ValueError) as e:
        raise AgentError("The reviewer returned an unexpected response.") from e
    if out.get('verdict') not in ('send', 'fixed', 'hold'):
        out['verdict'] = 'hold'
    out['subject'] = normalize_subject(out.get('subject') or subject)
    out['body'] = (out.get('body') or body or '').strip()
    if not out['subject'] or not out['body']:
        out['verdict'] = 'hold'
        out.setdefault('issues', []).append('the reviewer returned an empty draft')
    u = getattr(resp, "usage", None)
    usage = {"input_tokens": getattr(u, "input_tokens", 0),
             "output_tokens": getattr(u, "output_tokens", 0)} if u else {}
    return out, usage


def draft_reply(ctx, *, sender_name='', model=None):
    """Draft a response to a lead who wrote back. ``ctx`` = {name, company,
    city, state, org_type, inbound_subject, inbound_text, classification,
    last_sent_subject, last_sent_snippet}. Returns ({subject, body(HTML)},
    usage). Queued for human approval by default (AgentSettings.auto_replies)."""
    if not is_configured():
        raise AgentError("AI isn't configured (ANTHROPIC_API_KEY).")
    import anthropic
    book = _book_url()
    prompt = f"""A lead replied to {sender_name or 'our'} outreach. Draft the response.

LEAD: {ctx.get('name') or 'the contact'} at {ctx.get('company') or 'their organization'}
({ctx.get('city') or '?'}, {ctx.get('state') or '?'}; {ctx.get('org_type') or 'unknown type'})
OUR LAST EMAIL: subject "{ctx.get('last_sent_subject') or '(unknown)'}" —
{(ctx.get('last_sent_snippet') or '')[:400]}
THEIR REPLY (classified as {ctx.get('classification') or 'other'}):
Subject: {ctx.get('inbound_subject') or '(none)'}
{(ctx.get('inbound_text') or '')[:2500]}

Write a short, warm, human reply (60-120 words) that answers what they actually
asked using ONLY known product facts (see pillars) — if you don't know, say
you'll find out. Prices and URLs are in VERIFIED FACTS — if they asked what it
costs, tell them plainly; do not deflect a pricing question into a call.

Then ONE next step, matched to the reply:
- Cost is the obstacle (classified no_budget): lead with the free plan. Say
  what it covers, that it stays free, and that setting the garden up takes
  about ten minutes — link the signup page. Do NOT pitch Garden Pro or ask
  for a call. Never sound like you are talking them out of the free plan.
- They want to talk or asked something a conversation answers: the scheduling
  page <a href="{book}">{book}</a>.
- A no for any other reason: thank them, leave the door open, ask nothing.

Subject: "Re: <their subject>" (or a natural one if none). Body as email-safe
HTML (<p>, <strong>, <a href> only). End with a short sign-off only — the CRM
appends the signature. Do not invent names, customers, or commitments.

Return JSON only: {{"subject": ..., "body": ...}}"""
    try:
        mdl = model or REPLY_MODEL
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=mdl, max_tokens=4000,
            system=[{"type": "text", "text": brand_voice(),
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": prompt}],
            output_config={"format": {"type": "json_schema",
                                      "schema": REPLY_SCHEMA}, **_effort(mdl)},
        )
    except Exception as e:
        raise AgentError(f"The AI request failed: {e}") from e
    try:
        out = json.loads(next(b.text for b in resp.content if b.type == "text"))
    except (StopIteration, ValueError) as e:
        raise AgentError("The AI returned an unexpected response.") from e
    if not out.get("subject") or not out.get("body"):
        raise AgentError("The AI returned an incomplete reply draft.")
    out["subject"] = normalize_subject(out["subject"])
    u = getattr(resp, "usage", None)
    usage = {"input_tokens": getattr(u, "input_tokens", 0),
             "output_tokens": getattr(u, "output_tokens", 0)} if u else {}
    return out, usage


SCOUT_SCHEMA = {
    "type": "object",
    "properties": {
        "picks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "lead_id": {"type": "integer"},
                    "title": {"type": "string"},
                    "rationale": {"type": "string"},
                    "angle": {"type": "string"},
                },
                "required": ["lead_id", "title", "rationale", "angle"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["picks"],
    "additionalProperties": False,
}


def scout_leads(leads, *, limit=8, model=None):
    """Prioritize which REAL cold leads to start prospecting, with a fit brief.

    ``leads`` is a list of fact-only context dicts (lead_id, name, company,
    city, state, org_type, website). The agent ranks the best-fit prospects for
    YardHarvest's ICP and returns up to ``limit`` picks, each with a fact-based
    rationale and a suggested first-touch angle. It does NOT invent organizations
    or facts — it only chooses among the leads provided. Returns (picks, usage).
    """
    if not is_configured():
        raise AgentError(
            "AI drafting isn't configured. Set ANTHROPIC_API_KEY (and install "
            "the anthropic package) to enable it.")
    if not leads:
        return [], {}

    import anthropic

    blocks = "\n".join(
        f"lead_id={ld.get('lead_id')} | {ld.get('company') or 'an organization'}"
        f" ({ld.get('city') or '?'}, {ld.get('state') or '?'};"
        f" {ld.get('org_type') or 'unknown type'})"
        f" | contact: {ld.get('name') or 'unknown'}"
        f" | site: {ld.get('website') or 'none'}"
        for ld in leads)
    user_prompt = f"""From the cold, never-contacted leads below, pick the up to
{limit} BEST fits to start prospecting now and explain why. These are real
organizations already in the CRM — choose only from this list and use only the
facts shown. Do NOT invent organizations, people, contact details, or claims.

Rank by fit with YardHarvest's ideal customer (community gardens, urban-ag
nonprofits, and municipal/city parks programs that manage plots, dues,
volunteers, and need to show impact to funders/councils).

For each pick give:
- title: a short label (e.g. "Prioritize Lincoln Parks & Rec")
- rationale: ONE sentence on why this org is a strong fit, grounded only in the
  shown org_type / location / name.
- angle: a one-line suggested first-touch hook tailored to that org type.

LEADS:
{blocks}

Return JSON only: {{ "picks": [ {{lead_id, title, rationale, angle}} ] }}."""

    try:
        mdl = model or DEFAULT_MODEL
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=mdl,
            max_tokens=6000,
            system=[{
                "type": "text",
                "text": brand_voice(),
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": user_prompt}],
            output_config={"format": {"type": "json_schema",
                                      "schema": SCOUT_SCHEMA}, **_effort(mdl)},
        )
    except Exception as e:
        raise AgentError(f"The AI request failed: {e}") from e

    try:
        text = next(b.text for b in resp.content if b.type == "text")
        picks = json.loads(text).get("picks", [])
    except (StopIteration, ValueError) as e:
        raise AgentError("The AI returned an unexpected response. Try again.") from e

    valid_ids = {ld.get('lead_id') for ld in leads}
    clean = [p for p in picks
             if p.get('lead_id') in valid_ids and p.get('rationale')]

    u = getattr(resp, "usage", None)
    usage = {
        "input_tokens": getattr(u, "input_tokens", 0),
        "output_tokens": getattr(u, "output_tokens", 0),
        "cache_read": getattr(u, "cache_read_input_tokens", 0),
    } if u else {}
    return clean, usage


def draft_facebook_post(purpose, *, model=None):
    """Ask Claude to draft a rich Facebook Page post for a described purpose.

    Returns a dict with:
      message     — finished post copy (NO merge tokens; a Page post is public).
      link        — a URL the purpose clearly implies, else '' (never invented).
      hashtags    — a normalized list of 1–5 '#tags' (kept OUT of message so the
                    UI can show them as chips and let the user add them).
      image_idea  — a one-line concept for a photo to pair with the post.
      alternates  — up to 2 alternate full versions of the post (different angle
                    or length) the user can swap in with one click.
    Raises AgentError on failure.
    """
    if not is_configured():
        raise AgentError(
            "AI drafting isn't configured. Set ANTHROPIC_API_KEY (and install "
            "the anthropic package) to enable it.")

    import anthropic

    user_prompt = f"""Write ONE Facebook Page post for this purpose, with options:

PURPOSE: {purpose}

Produce:
- message: the primary post copy — finished, public, NO merge tokens or
  placeholders. Hook in the first line, a warm middle, ONE clear call to action.
  Concise (ideally under ~120 words / 600 characters). Do NOT put the hashtags
  inside the message — return them separately.
- hashtags: 1–5 relevant hashtags (without spaces). These are returned
  separately from the message.
- image_idea: ONE short line describing a photo that would pair well with this
  post (e.g. "Close-up of volunteers planting seedlings in raised beds"). This
  is guidance for the human to attach a real photo — do NOT invent an image URL.
- alternates: up to 2 alternate full versions of the post (e.g. a shorter punchy
  one and a warmer storytelling one) so the reviewer can pick.
- link: a URL only if the purpose clearly implies one; otherwise "" (never
  invent a URL).

Return JSON only with keys: message, link, hashtags, image_idea, alternates."""

    try:
        mdl = model or DEFAULT_MODEL
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=mdl,
            max_tokens=5000,
            system=[{
                "type": "text",
                "text": brand_voice(),
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": user_prompt}],
            output_config={"format": {"type": "json_schema",
                                      "schema": FB_POST_SCHEMA}, **_effort(mdl)},
        )
    except Exception as e:
        raise AgentError(f"The AI request failed: {e}") from e

    if getattr(resp, "stop_reason", None) == "refusal":
        raise AgentError("Claude declined to write this post — try rephrasing "
                         "the purpose.")
    try:
        text = next(b.text for b in resp.content if b.type == "text")
        post = json.loads(text)
        if not post.get("message"):
            raise KeyError("message")
    except (StopIteration, ValueError, KeyError) as e:
        raise AgentError("The AI returned an unexpected response. Try again "
                         "or adjust the purpose.") from e
    return _normalize_post_fields(post)


def _normalize_post_fields(post):
    """Coerce a drafted-post dict into the shape the UI/persistence expect."""
    post.setdefault("link", "")
    post["link"] = (post.get("link") or "").strip()
    post["hashtags"] = _clean_hashtags(post.get("hashtags"))
    post["image_idea"] = (post.get("image_idea") or "").strip()
    post["alternates"] = [str(a).strip() for a in (post.get("alternates") or [])
                          if str(a).strip()][:2]
    return post


def propose_facebook_posts(*, count=3, season_hint='', recent_titles=None,
                           model=None):
    """Agent skill: propose a short calendar of Facebook Page posts for review.

    The agent never publishes — it returns finished drafts that land in the
    approval queue as ``facebook_post`` proposals; a human edits the copy,
    attaches a real photo, then approves to publish. Each proposal has:
    title, rationale, message, hashtags[], image_idea, link. Spans the brand
    pillars, invents no statistics/URLs. Returns (posts, usage).
    """
    if not is_configured():
        raise AgentError(
            "AI drafting isn't configured. Set ANTHROPIC_API_KEY (and install "
            "the anthropic package) to enable it.")

    import anthropic

    avoid = ''
    if recent_titles:
        avoid = ("\n\nRecently posted (do NOT repeat these themes):\n"
                 + "\n".join(f"- {t}" for t in recent_titles[:8]))
    season_line = (f"\nSeason / timing context: {season_hint}."
                   if season_hint else '')

    user_prompt = f"""Propose {count} Facebook Page posts for YardHarvest's Page
to publish over the coming weeks.{season_line}

Vary them across the brand messaging pillars (less admin/more garden; show your
impact; built for community; grows with you) and across post types (a tip, an
invitation, a behind-the-scenes/community moment, a feature highlight, or a
share of one Community Garden Guide chapter from the content library — chapter
shares make great posts: pull one genuinely useful idea from the chapter's
theme as the hook, then link it). These are public posts — finished copy, NO
merge tokens or placeholders. Do NOT invent statistics, customer names,
testimonials, or dates. The ONLY URLs allowed are the guide chapters and
booking page listed in the content library.

For EACH post give:
- title: a short internal label (e.g. "Spring plot-signup reminder").
- rationale: ONE sentence on why this post is worth publishing now.
- message: the finished post copy (hook, warm middle, one clear call to action;
  concise). Keep hashtags OUT of the message.
- hashtags: 1–5 relevant hashtags (no spaces).
- image_idea: ONE short line describing a photo to pair with it (guidance for
  the human to attach a real photo — do NOT invent an image URL).
- link: a URL only if clearly implied; otherwise "".{avoid}

Return JSON only: {{ "posts": [ {{title, rationale, message, hashtags, image_idea, link}} ] }}."""

    try:
        mdl = model or DEFAULT_MODEL
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=mdl,
            max_tokens=8000,
            system=[{
                "type": "text",
                "text": brand_voice(),
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": user_prompt}],
            output_config={"format": {"type": "json_schema",
                                      "schema": FB_PROPOSALS_SCHEMA}, **_effort(mdl)},
        )
    except Exception as e:
        raise AgentError(f"The AI request failed: {e}") from e

    if getattr(resp, "stop_reason", None) == "refusal":
        raise AgentError("Claude declined to draft posts — try again.")
    try:
        text = next(b.text for b in resp.content if b.type == "text")
        posts = json.loads(text).get("posts", [])
    except (StopIteration, ValueError) as e:
        raise AgentError("The AI returned an unexpected response. Try again.") from e

    clean = []
    for pst in posts:
        if not pst.get("message") or not pst.get("title"):
            continue
        pst["hashtags"] = _clean_hashtags(pst.get("hashtags"))
        pst["image_idea"] = (pst.get("image_idea") or "").strip()
        pst["link"] = (pst.get("link") or "").strip()
        pst.setdefault("rationale", "")
        clean.append(pst)

    u = getattr(resp, "usage", None)
    usage = {
        "input_tokens": getattr(u, "input_tokens", 0),
        "output_tokens": getattr(u, "output_tokens", 0),
        "cache_read": getattr(u, "cache_read_input_tokens", 0),
    } if u else {}
    return clean, usage


_URL_RE = re.compile(r'^https?://', re.I)
_NEW_LEAD_ORG_TYPES = ('Independent', 'Nonprofit', 'City-Sponsored')


def _parse_lead_array(text):
    """Extract + normalize the JSON lead array from the model's final text.
    Drops any lead missing a name or a real source_url — the no-fabrication
    guard: a lead with no citeable source doesn't enter the funnel."""
    if not text:
        return []
    m = re.search(r'\[.*\]', text, re.DOTALL)
    if not m:
        return []
    try:
        raw = json.loads(m.group(0))
    except ValueError:
        return []
    out = []
    for it in (raw if isinstance(raw, list) else []):
        if not isinstance(it, dict):
            continue
        name = (it.get('name') or '').strip()
        src = (it.get('source_url') or '').strip()
        if not name or not _URL_RE.match(src):
            continue
        ot = (it.get('org_type') or '').strip().title()
        out.append({
            'name': name[:160],
            'city': (it.get('city') or '').strip()[:80],
            'state': (it.get('state') or '').strip()[:20],
            'org_type': ot if ot in _NEW_LEAD_ORG_TYPES else '',
            'website': (it.get('website') or '').strip()[:255],
            'contact_name': (it.get('contact_name') or '').strip()[:120],
            'contact_email': (it.get('contact_email') or '').strip()[:120],
            'contact_title': (it.get('contact_title') or '').strip()[:120],
            'contact_phone': (it.get('contact_phone') or '').strip()[:30],
            'fit': (it.get('fit') or '').strip()[:300],
            'source_url': src[:500],
        })
    return out


def scout_new_leads(*, focus='', exclude=None, count=8, model=None):
    """Find NET-NEW community-garden leads on the web that fit YardHarvest's ICP,
    for human review before they enter the CRM.

    Uses Claude (Opus 4.8) with the ``web_search`` server tool so every lead is
    grounded in a real, citeable source — never invented from memory. Returns
    (leads, usage); each lead is a dict: name, city, state, org_type, website,
    contact_name, contact_email, contact_title, fit, source_url. ``exclude`` is
    a list of org names already in the CRM to skip. Raises AgentError on failure.
    """
    if not is_configured():
        raise AgentError(
            "AI scouting isn't configured. Set ANTHROPIC_API_KEY (and install "
            "the anthropic package) to enable it.")

    import anthropic

    avoid = ''
    if exclude:
        avoid = ("\n\nAlready in our CRM — do NOT return these (find different "
                 "organizations):\n" + "\n".join(f"- {n}" for n in list(exclude)[:80]))
    focus_line = f"\nExtra focus for this run: {focus}." if focus else ''

    user_prompt = f"""Use web search to find up to {count} REAL, currently-operating
community gardens or urban-agriculture organizations in the US that are a strong
fit for YardHarvest and are NOT already our customers.{focus_line}

Ideal fit (priority order):
1. Independent / volunteer-run community gardens managing plots, dues, waitlists,
   and volunteers (our wedge — we cut their admin).
2. Urban-agriculture nonprofits and multi-garden operators (run several gardens;
   need funder-ready impact reporting).
3. Municipal / city parks community-garden programs.

Hard rules — this data goes straight into a sales CRM, so accuracy matters:
- ONLY include organizations you actually found via web search this session.
- For EACH lead, include source_url = the page where you found it (their own site
  or a directory listing). If you have no source_url, DO NOT include the lead.
- POPULATE EVERY FIELD YOU CAN: for each promising org, also check its website's
  contact/about page — most orgs publicly list a general email, a coordinator's
  name/title, and a phone number, and a lead with an email is worth far more to
  us than one without. Spend searches on contact pages, not just discovery.
- Include contact_name / contact_email / contact_title / contact_phone ONLY if
  publicly listed (their own site or official directory page). If not found,
  leave them "". NEVER guess or invent an email, name, phone, or organization.
- city/state must be the org's real location. org_type must be exactly one of
  "Independent", "Nonprofit", or "City-Sponsored".
- fit: ONE sentence on why this org fits YardHarvest, grounded in what you found.
{avoid}

Return ONLY a JSON array (no prose, no markdown fences) of objects with keys:
name, city, state, org_type, website, contact_name, contact_email,
contact_title, contact_phone, fit, source_url."""

    try:
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=model or DEFAULT_MODEL,
            max_tokens=8000,
            thinking={"type": "adaptive"},
            system=[{
                "type": "text",
                "text": brand_voice(),
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": user_prompt}],
            # count*2: discovery searches PLUS contact-page digs per lead.
            tools=[{"type": "web_search_20260209", "name": "web_search",
                    "max_uses": max(3, min(20, count * 2 + 2))}],
        )
    except Exception as e:
        raise AgentError(f"The AI request failed: {e}") from e

    if getattr(resp, "stop_reason", None) == "refusal":
        raise AgentError("Claude declined this scouting run — try again.")

    text = "".join(getattr(b, "text", "") for b in resp.content
                   if getattr(b, "type", None) == "text")
    leads = _parse_lead_array(text)

    usage = _web_usage(resp, model)
    return leads, usage


def _web_usage(resp, model=None):
    """Normalize usage (incl. server-side web-search count) from a response."""
    u = getattr(resp, "usage", None)
    stu = getattr(u, "server_tool_use", None) if u else None
    return {
        "model": getattr(resp, "model", model or DEFAULT_MODEL),
        "input_tokens": getattr(u, "input_tokens", 0) if u else 0,
        "output_tokens": getattr(u, "output_tokens", 0) if u else 0,
        "web_searches": (getattr(stu, "web_search_requests", 0) or 0) if stu else 0,
    }


def enrich_company(ctx, model=None):
    """Find publicly listed contact info for ONE existing CRM company.

    ``ctx``: {name, city, state, org_type, website, known_emails}. Uses web
    search (the org's own site first) to fill what the CRM is missing —
    general/coordinator email, phone, a named contact + title, website.
    Same no-fabrication contract as scouting: every value must literally
    appear on a page found this session, with source_url; '' when not found.
    Returns (data_dict_or_None, usage)."""
    if not is_configured():
        raise AgentError(
            "AI enrichment isn't configured. Set ANTHROPIC_API_KEY (and "
            "install the anthropic package) to enable it.")

    import anthropic

    known = ', '.join(ctx.get('known_emails') or []) or 'none'
    site = ctx.get('website') or 'unknown — find it'
    user_prompt = f"""Find publicly listed contact information for this
community-garden organization (it's already in our CRM but missing fields):

ORGANIZATION: {ctx.get('name')}
LOCATION: {ctx.get('city') or '?'}, {ctx.get('state') or '?'}
TYPE: {ctx.get('org_type') or 'unknown'}
WEBSITE: {site}
EMAILS WE ALREADY HAVE: {known}

Use web search — their own website's contact/about/join page first, then an
official directory listing. Fill ONLY what you actually see on a page you
found this session:
- email: a general or coordinator email address (not one we already have)
- phone: a listed phone number
- contact_name / contact_title: a named coordinator/manager/president if listed
- website: their real site URL (only if the one above is unknown/wrong)
- source_url: the exact page where you found the info (REQUIRED if any field
  is filled — no source, no data)
- found_note: ONE short sentence on what you found/where

NEVER guess, derive, or pattern-construct an email (no "probably
info@domain"). If a field isn't publicly listed, return "" for it. If you can
find nothing at all, return all fields as "".

Return ONLY a JSON object (no prose, no markdown fences) with keys:
email, phone, contact_name, contact_title, website, source_url, found_note."""

    try:
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=model or DEFAULT_MODEL,
            max_tokens=2500,
            thinking={"type": "adaptive"},
            system=[{
                "type": "text",
                "text": brand_voice(),
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": user_prompt}],
            tools=[{"type": "web_search_20260209", "name": "web_search",
                    "max_uses": 4}],
        )
    except Exception as e:
        raise AgentError(f"The AI request failed: {e}") from e

    text = "".join(getattr(b, "text", "") for b in resp.content
                   if getattr(b, "type", None) == "text")
    m = re.search(r'\{.*\}', text, re.DOTALL)
    data = None
    if m:
        try:
            raw = json.loads(m.group(0))
            if isinstance(raw, dict):
                data = {k: (str(raw.get(k) or '').strip())
                        for k in ('email', 'phone', 'contact_name',
                                  'contact_title', 'website', 'source_url',
                                  'found_note')}
                # No-fabrication gate: filled fields require a real source.
                has_data = any(data[k] for k in
                               ('email', 'phone', 'contact_name', 'website'))
                if has_data and not data['source_url'].startswith(('http://', 'https://')):
                    data = None
        except (ValueError, TypeError):
            data = None
    return data, _web_usage(resp, model)


def design_campaign(goal, context, model=None):
    """AI Studio: design a FULL campaign (targeting + email + content plan).

    ``context`` is a dict of live CRM facts (counts, breakdowns, segments,
    recent campaigns, constraints, today). Returns the validated design dict.
    Raises AgentError on any failure so the caller can flash it.
    """
    if not is_configured():
        raise AgentError(
            "AI Studio isn't configured. Set ANTHROPIC_API_KEY (and install "
            "the anthropic package) to enable it.")

    import anthropic

    user_prompt = f"""Design ONE complete marketing campaign for this goal:

GOAL: {goal}

REQUESTED AUDIENCE CONSTRAINTS (honor these if set; refine the rest):
{json.dumps(context.get('constraints', {}))}

LIVE CRM CONTEXT:
- Contacts (emailable): {context.get('emailable', 0)} of {context.get('contacts', 0)}
- Organizations by state: {json.dumps(context.get('by_state', {}))}
- Organizations by type: {json.dumps(context.get('by_type', {}))}
- Existing saved segments: {json.dumps(context.get('segments', []))}
- Recent campaigns (avoid repeating): {json.dumps(context.get('recent_campaigns', []))}
- Today's date: {context.get('today', '')}

Design the full campaign now: targeting, email copy with merge tokens, and a
supporting content plan."""

    try:
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=model or DEFAULT_MODEL,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            system=[{
                "type": "text",
                "text": brand_voice() + DESIGN_EXTENSION,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": user_prompt}],
            output_config={"format": {"type": "json_schema",
                                      "schema": DESIGN_SCHEMA}},
        )
    except Exception as e:  # network / auth / SDK errors
        raise AgentError(f"The AI request failed: {e}") from e

    if getattr(resp, "stop_reason", None) == "refusal":
        raise AgentError("Claude declined to write this campaign — try "
                         "rephrasing the goal.")

    try:
        text = next(b.text for b in resp.content if b.type == "text")
        design = json.loads(text)
        if not design.get("campaign", {}).get("subject"):
            raise KeyError("campaign.subject")
    except (StopIteration, ValueError, KeyError) as e:
        raise AgentError("The AI returned an unexpected response. Try again "
                         "or adjust the goal.") from e

    design["model"] = getattr(resp, "model", model or DEFAULT_MODEL)
    return design
