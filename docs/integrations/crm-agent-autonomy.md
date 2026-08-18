# Autonomous BDR agent — setup & operations

The CRM's BDR agent can run the core outbound loop by itself: each weekday
morning it picks who to contact, writes the email, sends it, follows the
4d → 8d → stop cadence, starts cold leads that are already in the CRM, reads
replies out of your mailbox, and emails you a digest of what it did.

**What it never does on its own** (these stay in the approval queue):
find brand-new organizations on the web, enrich company records, send mass
campaigns, post to Facebook, and *answer a reply* — a human answers a human.
Each of those is a checkbox in the console if you change your mind.

---

## 1. One-time setup

### a. Zoho Mail — let the CRM read replies

Reply capture is the safety net: it's what stops a sequence the moment
someone answers. Without it the agent refuses to send (by default).

1. Zoho Mail → **Settings → Mail Accounts → IMAP Access** → enable.
2. Note the **IMAP server** Zoho shows there — `imap.zoho.com` for personal
   accounts, `imappro.zoho.com` for paid organization accounts.
3. With two-factor on (it should be), create an **application-specific
   password**: accounts.zoho.com → Security → App Passwords → name it
   "YardHarvest CRM". Copy it once — Zoho won't show it again.

The CRM only ever *reads* (`EXAMINE` + `BODY.PEEK`), so your unread flags and
message state are untouched.

### b. Render environment variables

Add these in the **Render Dashboard** (Environment tab) — never in
`render.yaml`. Dashboard values survive a blueprint sync, and editing
`render.yaml` would re-apply the blueprint and revert the database to the
free plan.

**Web service `yardharvest`:**

| Key | Value |
|---|---|
| `CRM_IMAP_PASSWORD` | the app-specific password |
| `CRM_IMAP_HOST` | only if not `imap.zoho.com` (e.g. `imappro.zoho.com`) |
| `CRM_MAILING_ADDRESS` | your CAN-SPAM postal address (should already be set) |

**Cron service `yardharvest-facebook-scheduler`** — this is what actually
runs the agent every 15 minutes, so it needs the same keys:

| Key | Value |
|---|---|
| `ANTHROPIC_API_KEY` | same as the web service |
| `ZEPTOMAIL_TOKEN` | same as the web service |
| `CRM_MAILING_ADDRESS` | same |
| `CRM_IMAP_PASSWORD` | same |
| `CRM_IMAP_HOST` | if you needed it above |
| `CLAUDE_MODEL` / `CRM_EMAIL_MODEL` | optional, only to override models |

Why that cron: Render's free tier spins the web service down when idle, and
a new cron service would mean re-applying the blueprint. The Facebook
scheduler already runs `*/15 * * * *`, never overlaps itself, and the agent
tick is idempotent — so it rides along. Publishing Facebook posts happens
first and is unaffected if the agent errors.

### c. Turn it on

1. Deploy (the build applies migration `b5d7f9a1c3e5`).
2. Open **/crm/agent** → the **Autonomy** panel.
3. Click **Test connection** — you should get "Connected to imap.zoho.com…".
4. Click **Check replies** once. The first poll *baselines* your mailbox: it
   records where the mailbox is now and processes nothing, so years of old
   mail are never replayed into the CRM.
5. In **Settings**, set **Acts as** (the CRM user the agent records as owner)
   and the digest address if it differs from the CRM sender.
6. Click **Turn on**.

If anything is missing the panel says exactly what ("Autonomy is on but won't
send yet: …") instead of silently doing nothing.

---

## 2. What a day looks like

Every 15 minutes the cron ticks. The tick polls for replies if it's been
more than ~14 minutes, then runs the daily cycle if it's a weekday at/after
your send hour and today's cycle hasn't run.

The cycle:

1. **Reads replies first.** Anyone who wrote back is marked Engaged (or
   Disqualified / unsubscribed / snoozed), their queued follow-ups are
   withdrawn, and for interested replies a response is drafted and left in
   your queue. You also get an immediate "💬 X replied" email.
2. **Checks the brakes** — hard bounces in the last 24h, reply capture
   health, the daily cap.
3. **Sends follow-ups** to due leads: New/Working only, with an address, not
   opted out or suppressed, under three touches, nothing already queued, no
   reply from them this week. Touch 1 is a value-first intro, touch 2 a short
   bump with a new angle, touch 3 a polite break-up — then the lead moves to
   Nurture for ~90 days.
4. **Starts cold leads** with any leftover budget: ranks the cold leads
   already in your CRM, promotes the best to Working, and sends their intro.
5. **Emails you the digest**: what went out, who replied, what was skipped or
   failed, meetings booked, AI cost, and how many more days of pipeline you
   have at the current pace.

---

## 3. Controls

| Control | Where | Effect |
|---|---|---|
| **Turn off** | Autonomy panel | Stops all automatic sending. The queue still works. |
| **Resume** | Autonomy panel (when paused) | Clears a tripped breaker. |
| **Run cycle now** | Autonomy panel | Runs immediately, ignoring the time window. Still respects the cap and the switch. |
| **Check replies** | Autonomy panel | Polls the mailbox now. |
| `CRM_AGENT_AUTONOMY=off` | Render env | Emergency stop without a code change — overrides the in-app switch. |
| Per-action checkboxes | Autonomy → Settings | Which action types run unattended. |

**The agent pauses itself** (and emails you) when: 3 consecutive sends fail,
3+ hard bounces/complaints land in 24 hours, or reply capture hasn't
succeeded in 24 hours. It stays paused until you press Resume.

### CLI (ops / debugging)

```bash
flask crm-agent-tick             # one heartbeat: poll + cycle-if-due
flask crm-agent-cycle --force    # run a cycle now, ignore the window
flask crm-agent-poll             # poll the mailbox once
```

---

## 4. Things worth knowing

- **Pace.** Default 15 emails/weekday from one address. That's deliberately
  slow: a young sending domain that suddenly blasts hundreds of cold emails
  gets spam-foldered, which is very hard to undo. Raise it gradually.
- **Cost.** Roughly $0.10–0.30 a day at the default cap (drafting is Sonnet;
  cold-lead ranking is Opus). The console's AI usage panel shows a rolling
  30-day estimate.
- **The agent never invents anything.** It writes only from what's in the
  CRM. Web-scouted leads still require a real source URL.
- **Leads it won't touch.** Engaged and Qualified leads are yours — the
  digest lists them as "needs your touch". Same for anyone opted out,
  suppressed, or bounced.
- **Running dry.** Each cold lead is worth ~3 touches; the digest tells you
  how many weekday cycles of pipeline remain and nudges you to click
  **Find new leads** (still a manual, web-searching step) before it starves.
- **Every automated email** carries the founder signature, the CAN-SPAM
  postal footer, and a List-Unsubscribe header, and is BCC'd to you.

## 5. If something looks wrong

| Symptom | Look at |
|---|---|
| Nothing sends | The Autonomy panel's blocker list — it names the exact gate. |
| "Paused itself" | The reason on the panel; fix, then Resume. |
| Reply capture red | Test connection. A rotated app password is the usual cause. |
| Someone got a follow-up after replying | Check the reply landed: Recent replies on the console, or `flask crm-agent-poll`. Replies that never reached the mailbox (or arrived from a different address than the CRM has) can't be seen. |
| Duplicate sends | Shouldn't be possible — sends are claimed atomically and the cycle is claimed per local date. Check `crm_agent_run` for two runs the same day. |
