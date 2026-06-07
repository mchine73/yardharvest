# YardHarvest Marketing Agent (autonomous runner)

A standalone Python agent that drafts personalized email campaigns for the
YardHarvest CRM and stages them as **drafts** for human review. It never sends
email — a person reviews and sends from the CRM UI.

## What it does
1. Pulls segment totals + the target audience from the CRM marketing API
   (`/api/marketing/segments`, `/api/marketing/audience`) using `X-API-Key`.
2. Asks Claude (`claude-opus-4-7`) to write a campaign (name, subject, body) in
   the YardHarvest brand voice, personalized with merge tokens
   (`{{first_name}}`, `{{company}}`, `{{state}}`, …). The brand-voice system
   prompt is sent with prompt caching.
3. POSTs the result back as a **draft** campaign
   (`POST /api/marketing/campaigns`) and prints the review URL.

## Install
```bash
pip install -r marketing_agent/requirements.txt
```

## Configure (environment)
| Var | Required | Default | Notes |
|-----|----------|---------|-------|
| `ANTHROPIC_API_KEY` | yes | — | Claude API key |
| `MARKETING_API_KEY` | yes | — | Token for the CRM `/api/marketing/*` endpoints |
| `CRM_BASE_URL` | no | `http://127.0.0.1:5000` | e.g. `https://crm.yardharvest.app` |
| `CLAUDE_MODEL` | no | `claude-opus-4-7` | Override the model |
| `MARKETING_GOAL` | no | — | Fallback goal for unattended/scheduled runs |

## Run as a CLI
```bash
python -m marketing_agent.agent "spring pilot push to WI independent gardens" \
    --state WI --type Independent

# Preview without writing to the CRM:
python -m marketing_agent.agent "re-engage stalled MN gardens" --state MN --dry-run
```
Flags: `--state`, `--type` (`Independent`|`City-Sponsored`), `--tag`, `--name`,
`--dry-run`.

## Run as a scheduled job
With no positional goal it reads `MARKETING_GOAL`. Example cron (weekly):
```cron
0 9 * * 1  cd /app && MARKETING_GOAL="weekly outreach to new gardens" \
           python -m marketing_agent.agent --type Independent >> /var/log/mktg.log 2>&1
```
On Render, add a **Cron Job** service with the same start command and the env
vars above.

## Design notes
- **Human-in-the-loop by design.** The agent only ever creates *draft*
  campaigns; sending is a deliberate human action in the CRM (which also enforces
  opt-out/CAN-SPAM). The CRM API has no "send" endpoint for the agent.
- **Prompt caching.** The stable `BRAND_VOICE` system prompt is sent with
  `cache_control: ephemeral`. Caching activates once the prefix exceeds the
  model's minimum cacheable size (~4096 tokens on Opus); below that it's a
  harmless no-op. Cache stats are printed to stderr each run.
- **Structured output.** The campaign is returned via a JSON schema
  (`output_config.format`) so parsing is reliable.
- **Consent.** The audience endpoint already excludes opted-out contacts.

## Relationship to the in-IDE agent
This runner is the *productionized / autonomous* layer. For interactive,
human-in-the-loop campaign building inside Claude Code, use the subagents and
skills under `.claude/` (the `marketing-strategist` agent and the `/market`
command), which call the same CRM marketing API.
