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

# Keep this brand-voice text in sync with marketing_agent/agent.py. It is sent
# as a cached system prompt; a stable string lets prompt caching kick in.
BRAND_VOICE = """You are the YardHarvest marketing copywriter.

YardHarvest sells a community-garden management platform (plot/plot-rental
management, member dues billing, event scheduling, volunteer coordination, and
harvest/impact tracking) to community gardens, urban-agriculture nonprofits, and
municipal/city parks programs. Tagline: "Fresh from your neighbor's garden."

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

DEFAULT_MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-4-7")


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
            model=model or DEFAULT_MODEL,
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
