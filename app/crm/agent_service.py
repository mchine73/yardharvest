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

YardHarvest sells a community-garden management platform (plot/plot-rental
management, member dues billing, event scheduling, volunteer coordination, and
harvest/impact tracking) to community gardens, urban-agriculture nonprofits, and
municipal/city parks programs. Tagline: "Less admin, more garden."

VOICE
- Warm, practical, community-first. Sound like a knowledgeable neighbor who
  gardens, not a SaaS sales rep.
- Plain, human language. No hype words ("revolutionary", "game-changing",
  "synergy"), no ALL CAPS, no exclamation-point spam, no false urgency.
- Confident and helpful, never pushy or fear-based.

AUDIENCE PERSONAS
1. Garden Coordinator (volunteer/part-time): time-poor; juggles plots,
   waitlists, dues, and volunteers on spreadsheets. Wants their Saturday back.
2. Nonprofit Program Manager: runs a network of gardens; must show impact to
   funders and boards; budgets are grant- and fiscal-year-driven.
3. City Parks / Municipal Staff: runs community gardens as a public program;
   cares about equitable access, reporting, and the fiscal year (many end June 30)
   and procurement timelines.

MESSAGING PILLARS
1. Less admin, more garden — automate dues, plots, waitlists, events.
2. Show your impact — participation & harvest data for funders and councils.
3. Built for community — volunteers, events, and members in one place.
4. Grows with you — one garden or a citywide network.

WRITING RULES
- Lead with the reader's problem, not the product.
- Exactly ONE clear, low-friction call to action (e.g. book a 15-min call, start
  a free pilot, or reply).
- Cold outreach body: ~120-180 words, short skimmable paragraphs.
- Personalize with merge tokens that the CRM fills per recipient. Available
  tokens: {{first_name}}, {{contact_name}}, {{company}}, {{city}}, {{state}},
  {{org_type}}, {{sender_name}}, {{today}}. Write so the copy still reads
  naturally if a token renders blank. Do NOT invent other tokens.
- Never fabricate statistics, customer names, or testimonials.
- Honor consent / CAN-SPAM: honest subject line, no deceptive phrasing. The CRM
  adds the unsubscribe + physical-address footer, so do not invent one.
- Describe only capabilities the product actually has (see pillars above).

OUTPUT
Return a single campaign as JSON with: name (short internal label), subject
(<= 60 chars), and body (plain text with merge tokens). No markdown, no preamble.
"""

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

DEFAULT_MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-4-8")

# Email drafting (follow-ups, campaigns, templates) runs SYNCHRONOUSLY inside a
# web request, so it uses a faster model to stay well under the gunicorn worker
# timeout — Sonnet 4.6 (no extended thinking) is quick and plenty capable for
# routine email copy. Override with CRM_EMAIL_MODEL. Scouting, the AI-Studio
# campaign designer, and Facebook posts keep DEFAULT_MODEL (Opus).
EMAIL_MODEL = os.environ.get("CRM_EMAIL_MODEL", "claude-sonnet-4-6")

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
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=model or EMAIL_MODEL,
            max_tokens=2000,
            system=[{
                "type": "text",
                "text": BRAND_VOICE,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": user_prompt}],
            output_config={"format": {"type": "json_schema",
                                      "schema": CAMPAIGN_SCHEMA}},
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
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=model or EMAIL_MODEL,
            max_tokens=2000,
            system=[{
                "type": "text",
                "text": BRAND_VOICE,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": user_prompt}],
            output_config={"format": {"type": "json_schema",
                                      "schema": CAMPAIGN_SCHEMA}},
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
    return template


def _lead_block(lead):
    """One compact, fact-only context line per lead for the follow-up prompt."""
    recent = lead.get('recent') or []
    recent_txt = '; '.join(recent[:4]) if recent else 'no prior activity logged'
    dsc = lead.get('days_since_contact')
    contacted = (f'{dsc} days since last contact' if dsc is not None
                 else 'never contacted')
    return (
        f"lead_id={lead.get('lead_id')} | {lead.get('name') or 'A contact'}"
        f" at {lead.get('company') or 'an organization'}"
        f" ({lead.get('city') or '?'}, {lead.get('state') or '?'};"
        f" {lead.get('org_type') or 'unknown type'})"
        f" | status={lead.get('lead_status') or 'New'} | {contacted}"
        f" | recent: {recent_txt}"
    )


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
    user_prompt = f"""You are doing outbound BDR follow-ups for {sender_name or 'the YardHarvest team'}.

For EACH lead below, write one short, warm follow-up email that moves the
conversation toward a 15-minute intro call. These are real prospects pulled
from the CRM — use ONLY the context given. Do not invent facts, statistics,
prior conversations, names, or commitments that aren't shown here.

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
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=model or EMAIL_MODEL,
            max_tokens=4000,
            system=[{
                "type": "text",
                "text": BRAND_VOICE,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": user_prompt}],
            output_config={"format": {"type": "json_schema",
                                      "schema": FOLLOWUPS_SCHEMA}},
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

    u = getattr(resp, "usage", None)
    usage = {
        "input_tokens": getattr(u, "input_tokens", 0),
        "output_tokens": getattr(u, "output_tokens", 0),
        "cache_read": getattr(u, "cache_read_input_tokens", 0),
    } if u else {}
    return clean, usage


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
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=model or DEFAULT_MODEL,
            max_tokens=2500,
            system=[{
                "type": "text",
                "text": BRAND_VOICE,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": user_prompt}],
            output_config={"format": {"type": "json_schema",
                                      "schema": SCOUT_SCHEMA}},
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
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=model or DEFAULT_MODEL,
            max_tokens=2000,
            system=[{
                "type": "text",
                "text": BRAND_VOICE,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": user_prompt}],
            output_config={"format": {"type": "json_schema",
                                      "schema": FB_POST_SCHEMA}},
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
invitation, a behind-the-scenes/community moment, a feature highlight). These
are public posts — finished copy, NO merge tokens or placeholders. Do NOT invent
statistics, customer names, testimonials, dates, or URLs.

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
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=model or DEFAULT_MODEL,
            max_tokens=3000,
            system=[{
                "type": "text",
                "text": BRAND_VOICE,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": user_prompt}],
            output_config={"format": {"type": "json_schema",
                                      "schema": FB_PROPOSALS_SCHEMA}},
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
- Include contact_name / contact_email / contact_title ONLY if publicly listed on
  the org's own site. If not found, leave them "". NEVER guess or invent an
  email, name, phone, or organization.
- city/state must be the org's real location. org_type must be exactly one of
  "Independent", "Nonprofit", or "City-Sponsored".
- fit: ONE sentence on why this org fits YardHarvest, grounded in what you found.
{avoid}

Return ONLY a JSON array (no prose, no markdown fences) of objects with keys:
name, city, state, org_type, website, contact_name, contact_email,
contact_title, fit, source_url."""

    try:
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=model or DEFAULT_MODEL,
            max_tokens=8000,
            thinking={"type": "adaptive"},
            system=[{
                "type": "text",
                "text": BRAND_VOICE,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": user_prompt}],
            tools=[{"type": "web_search_20260209", "name": "web_search",
                    "max_uses": max(3, min(12, count + 2))}],
        )
    except Exception as e:
        raise AgentError(f"The AI request failed: {e}") from e

    if getattr(resp, "stop_reason", None) == "refusal":
        raise AgentError("Claude declined this scouting run — try again.")

    text = "".join(getattr(b, "text", "") for b in resp.content
                   if getattr(b, "type", None) == "text")
    leads = _parse_lead_array(text)

    u = getattr(resp, "usage", None)
    usage = {
        "input_tokens": getattr(u, "input_tokens", 0),
        "output_tokens": getattr(u, "output_tokens", 0),
    } if u else {}
    return leads, usage


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
                "text": BRAND_VOICE + DESIGN_EXTENSION,
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
