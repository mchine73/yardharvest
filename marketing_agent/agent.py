#!/usr/bin/env python3
"""
YardHarvest autonomous marketing agent.

Pulls audience/segment data from the YardHarvest CRM marketing API, asks Claude
to draft a personalized email campaign (subject + body with merge tokens) in the
YardHarvest brand voice, and POSTs it back to the CRM as a DRAFT for human review.
It never sends email — a person reviews and sends from the CRM.

Run as a CLI:
    python -m marketing_agent.agent "spring pilot push to WI independent gardens" \
        --state WI --type Independent

Run as a scheduled job (cron / Render cron). With no goal argument it falls back
to the MARKETING_GOAL env var:
    MARKETING_GOAL="re-engage stalled MN gardens" python -m marketing_agent.agent

Config (environment variables):
    ANTHROPIC_API_KEY   required — Claude API key
    CRM_BASE_URL        default http://127.0.0.1:5000 (CRM endpoints live under /crm)
    MARKETING_API_KEY   required — token for the /crm/api/marketing/* endpoints
    CLAUDE_MODEL        optional — defaults to claude-opus-4-7
"""
import argparse
import json
import os
import sys

import anthropic
import requests

# The CRM was consolidated into yardharvest; its endpoints now live under /crm.
# CRM_BASE_URL should be the *yardharvest* origin (e.g. https://yardharvest.com);
# this script prepends /crm/api/marketing/... when making calls.
CRM_BASE_URL = os.environ.get("CRM_BASE_URL", "http://127.0.0.1:5000").rstrip("/")
MARKETING_API_KEY = os.environ.get("MARKETING_API_KEY", "")
MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-4-7")
HTTP_TIMEOUT = 30

# ---------------------------------------------------------------------------
# Brand voice — sent as a cached system prompt. Keep this text STABLE: any byte
# change invalidates the prompt cache. (Caching kicks in once the prefix exceeds
# the model's minimum cacheable size — ~4096 tokens on Opus; below that it is a
# silent no-op, which is harmless here.)
# ---------------------------------------------------------------------------
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

# JSON schema for the structured campaign output.
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


# ---------------------------------------------------------------------------
# CRM marketing API client
# ---------------------------------------------------------------------------
def _crm_headers():
    return {"X-API-Key": MARKETING_API_KEY, "Content-Type": "application/json"}


def crm_get(path, params=None):
    r = requests.get(f"{CRM_BASE_URL}{path}", headers=_crm_headers(),
                     params=params, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    return r.json()


def crm_post(path, payload):
    r = requests.post(f"{CRM_BASE_URL}{path}", headers=_crm_headers(),
                      data=json.dumps(payload), timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    return r.json()


def get_segments():
    return crm_get("/crm/api/marketing/segments")


def get_audience(state="", org_type="", tag="", limit=200):
    params = {"limit": limit}
    if state:
        params["state"] = state
    if org_type:
        params["type"] = org_type
    if tag:
        params["tag"] = tag
    return crm_get("/crm/api/marketing/audience", params=params)


def create_draft(name, subject, body, state="", org_type="", tag=""):
    payload = {"name": name, "subject": subject, "body": body}
    if state:
        payload["state"] = state
    if org_type:
        payload["type"] = org_type
    if tag:
        payload["tag"] = tag
    return crm_post("/crm/api/marketing/campaigns", payload)


# ---------------------------------------------------------------------------
# Claude — draft the campaign
# ---------------------------------------------------------------------------
def draft_campaign(client, goal, segments, audience):
    """Ask Claude to write a campaign. Returns dict(name, subject, body)."""
    sample = audience.get("contacts", [])[:8]
    sample_lines = "\n".join(
        f"- {c.get('first_name') or c.get('name')} at "
        f"{c.get('company') or 'an organization'} "
        f"({c.get('city') or '?'}, {c.get('state') or '?'}; "
        f"{c.get('org_type') or 'unknown type'})"
        for c in sample
    ) or "(no sample available)"

    user_prompt = f"""Write ONE outreach email campaign for this goal:

GOAL: {goal}

AUDIENCE SIZE: {audience.get('count', 0)} recipients (opted-out contacts are
already excluded by the CRM).

AUDIENCE FILTERS: {json.dumps(audience.get('filters', {}))}

SAMPLE RECIPIENTS:
{sample_lines}

CRM SEGMENT TOTALS (for context):
{json.dumps(segments, indent=2)}

Write the campaign now. Personalize with merge tokens so each recipient sees
their own name/org/location. Return JSON only: name, subject, body."""

    resp = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=[{
            "type": "text",
            "text": BRAND_VOICE,
            "cache_control": {"type": "ephemeral"},  # cache the stable brand voice
        }],
        messages=[{"role": "user", "content": user_prompt}],
        output_config={"format": {"type": "json_schema", "schema": CAMPAIGN_SCHEMA}},
    )

    # Cache visibility (0 read on first call / when under the cache minimum)
    u = resp.usage
    print(f"[claude] input={u.input_tokens} "
          f"cache_write={getattr(u, 'cache_creation_input_tokens', 0)} "
          f"cache_read={getattr(u, 'cache_read_input_tokens', 0)} "
          f"output={u.output_tokens}", file=sys.stderr)

    text = next(b.text for b in resp.content if b.type == "text")
    return json.loads(text)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def run(goal, state="", org_type="", tag="", name=None, dry_run=False):
    if not MARKETING_API_KEY:
        sys.exit("MARKETING_API_KEY is not set.")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set.")

    client = anthropic.Anthropic()

    segments = get_segments()
    audience = get_audience(state, org_type, tag)
    print(f"[crm] audience: {audience.get('count', 0)} recipient(s) "
          f"(filters: state={state or '-'} type={org_type or '-'} tag={tag or '-'})")

    if audience.get("count", 0) == 0:
        sys.exit("No recipients match these filters — nothing to draft.")

    campaign = draft_campaign(client, goal, segments, audience)
    if name:
        campaign["name"] = name

    print("\n=== DRAFT CAMPAIGN ===")
    print(f"Name:    {campaign['name']}")
    print(f"Subject: {campaign['subject']}")
    print(f"Body:\n{campaign['body']}\n")

    if dry_run:
        print("[dry-run] Not creating a draft in the CRM.")
        return campaign

    result = create_draft(campaign["name"], campaign["subject"],
                          campaign["body"], state, org_type, tag)
    print(f"[crm] Draft created (id={result.get('id')}), "
          f"~{result.get('estimated_recipients')} recipients, "
          f"{result.get('opted_out_excluded')} opted-out excluded.")
    print(f"[crm] Review & send: {result.get('review_url')}")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="YardHarvest marketing agent")
    parser.add_argument("goal", nargs="?", default=os.environ.get("MARKETING_GOAL"),
                        help="Campaign goal (or set MARKETING_GOAL)")
    parser.add_argument("--state", default="", help="2-letter state filter (e.g. WI)")
    parser.add_argument("--type", dest="org_type", default="",
                        help="Independent | City-Sponsored")
    parser.add_argument("--tag", default="", help="Organization tag substring")
    parser.add_argument("--name", default=None, help="Override the campaign name")
    parser.add_argument("--dry-run", action="store_true",
                        help="Draft and print, but do not write to the CRM")
    args = parser.parse_args(argv)

    if not args.goal:
        parser.error("a goal is required (positional arg or MARKETING_GOAL env var)")

    run(args.goal, state=args.state, org_type=args.org_type, tag=args.tag,
        name=args.name, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
