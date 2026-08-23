# Stripe webhooks — setup and what each event is for

YardHarvest has **one** webhook route, `POST /api/webhooks/stripe`, but Stripe
needs **two endpoints** pointed at it. That is the single most important thing
on this page, and the reason garden managers could not see their own money for
so long.

- A **platform** endpoint delivers events about charges the platform creates:
  dues payments, Tap-to-Pay sales, refunds, chargebacks, Garden Pro
  subscriptions.
- A **Connect** endpoint delivers events emitted by *connected accounts* —
  managers' Express accounts. Payouts to their bank and `account.updated` only
  ever arrive this way.

Stripe issues a **separate signing secret per endpoint**, so a deployment that
knows only one secret rejects every event from the other with a signature
failure. In the logs that is indistinguishable from an attack. Both secrets are
therefore configuration:

| Env var | Endpoint | Required |
|---|---|---|
| `STRIPE_WEBHOOK_SECRET` | platform | yes — unsigned events are refused whenever `STRIPE_SECRET_KEY` is set |
| `STRIPE_CONNECT_WEBHOOK_SECRET` | Connect | only if you want payouts and account health |

`stripe_service.construct_webhook_event` tries each configured secret in turn.

## Setting it up (Stripe Dashboard → **Workbench → Webhooks**)

Not "Developers → Webhooks" — webhook management moved into **Workbench**:
<https://dashboard.stripe.com/workbench/webhooks>

**Check the mode toggle first.** Production runs on live keys (`/api/health/stripe`
reports `mode: live`), so the dashboard must be in **live** mode, not a sandbox.
Endpoints configured in a sandbox are invisible to production and vice versa —
this is the single most common way this ends up "configured" and still not
working.

Both endpoints use the same URL: `https://www.yardharvest.app/api/webhooks/stripe`

The scope is set by the **Events from** control when you create the webhook:
**Your account** (the platform endpoint) or **Connected accounts** (the Connect
endpoint). Via the API the same thing is the `connect` parameter, `false` or
`true`.

### 1. Platform endpoint — "Events from: Your account"

Select:

| Event | What it does here |
|---|---|
| `payment_intent.succeeded` | Settles dues (online **and** in-person) and writes every garden payment to the finance ledger. The guarantee path — collection no longer depends on a browser or a phone calling back. |
| `payment_intent.payment_failed` | Marks marketplace orders failed; records a declined garden charge so a manager can check whether money ever arrived. |
| `charge.refunded` | Syncs marketplace refunds, ledgers garden refunds, and puts a fully-refunded member back on the dues roster. |
| `charge.dispute.created` / `.updated` / `.closed` | Chargebacks on garden money. Notifies the organizer while there is still time to respond. |
| `customer.subscription.created` / `.updated` / `.deleted` | Garden Pro status and billing periods. Also the activation-of-last-resort for a paid subscription. |
| `invoice.payment_failed` | Garden Pro dunning → `past_due`. |
| `transfer.created` | Records a marketplace `SellerPayout`. |

### 2. Connect endpoint — "Events from: Connected accounts"

Add a **second** endpoint at the same URL, this time with **Events from** set to
**Connected accounts**, and select:

| Event | What it does here |
|---|---|
| `account.updated` | Mirrors the manager's account health (charges/payouts enabled, outstanding requirements, disabled reason) and notifies them when it slips. Without this, a restriction first surfaces as a failed tap in front of a member. |
| `payout.created` / `payout.paid` / `payout.failed` | "When does the money reach my bank." Payouts belong to the connected account, so they arrive **only** here. |

Open the new endpoint, reveal its **Signing secret** (`whsec_…`), and put it in
`STRIPE_CONNECT_WEBHOOK_SECRET` on the Render **web service** → Environment.
Dashboard-set env vars survive blueprint syncs; `render.yaml` is not to be
edited. Saving triggers a redeploy.

### Doing it via the API instead

If the dashboard is fighting you, both endpoints can be created from the Render
shell, where `STRIPE_SECRET_KEY` already exists:

```python
import os, stripe
stripe.api_key = os.environ['STRIPE_SECRET_KEY']
ep = stripe.WebhookEndpoint.create(
    url='https://www.yardharvest.app/api/webhooks/stripe',
    enabled_events=['account.updated', 'payout.created',
                    'payout.paid', 'payout.failed'],
    connect=True,                      # <- this is the whole point
    description='YardHarvest Connect events',
)
print(ep.secret)                       # whsec_... -> STRIPE_CONNECT_WEBHOOK_SECRET
```

> **`WebhookEndpoint.modify` REPLACES `enabled_events` wholesale.** Updating the
> platform endpoint means passing the *entire* list, not just the additions.
> Passing only the dispute events would silently drop
> `payment_intent.succeeded` and stop dues collection.

## Verifying

```bash
curl -s https://www.yardharvest.app/api/health/stripe/webhooks
```

Returns booleans, counts and event names — never URLs or secrets:

```json
{
  "configured": true,
  "platform_secret_set": true,
  "connect_secret_set": true,
  "endpoints": 2,
  "enabled_endpoints": 2,
  "handled_events": ["account.updated", "charge.dispute.closed", "..."],
  "connect_events": ["account.updated", "payout.created", "payout.failed", "payout.paid"],
  "missing_events": [],
  "error": null
}
```

`missing_events` lists event types the app handles that no enabled endpoint is
subscribed to. Anything in that list is a feature that will silently do
nothing. Note the probe cannot tell a platform endpoint from a Connect one
(Stripe does not return the flag), so an event can appear covered while still
being subscribed on the wrong endpoint — `connect_secret_set: false` alongside
payout events in `handled_events` is the tell.

Also useful:

```bash
curl -s https://www.yardharvest.app/api/health/stripe
```

`{mode, configured, auth_ok, connect_ok, error}` — key authentication and
whether Connect is enabled on the platform account.

In the app, a garden's **Finance → Stripe** tab shows `synced_at: null` as
"Stripe hasn't sent an account update yet", which is the same diagnosis from
the manager's side: the Connect endpoint isn't wired up.

## Backfill: making it correct on day one

Webhooks only report what happens *next*. A manager whose Stripe account has
been healthy for months emits no `account.updated`, so straight after wiring
the Connect endpoint the finance screens would report "Stripe hasn't sent an
account update yet" indefinitely — and payouts Stripe already made would never
appear. Run once, from the Render shell:

```bash
flask stripe-sync-accounts --dry-run    # read and report, write nothing
flask stripe-sync-accounts              # then for real
```

It reads every user with a `stripe_connect_account_id` via `Account.retrieve`,
mirrors the health columns, and pulls the last 10 payouts per account
(`--payout-limit N`, or `--no-payouts` to skip). It writes through the *same*
`garden_finance.sync_account` / `record_payout` helpers the webhook handlers
use, so a backfilled account and a webhook-updated one are indistinguishable —
`tests/test_stripe_backfill.py` asserts exactly that.

Safe to re-run: ledger rows are upserted on the Stripe object id. A dead
account (a test-mode id under live keys, a closed account) is reported and
skipped rather than aborting the run.

It stays **silent** by default — messaging every manager at once about a state
they have been in for weeks is noise, not news. `--notify` opts in, and even
then only for managers whose state actually changed and who organize a garden
to link to. `--account acct_...` limits the run to one manager.

## Fees: what Stripe charged, not what we assumed

`garden_finance_event` records two separate cuts:

* `fee_cents` — YardHarvest's application fee, set by `pricing.dues_fee_cents()`.
* `stripe_fee_cents` — what **Stripe** charged the connected account, read from
  that account's balance transaction on `payment_intent.succeeded`.

The second is read rather than modelled, because who bears Stripe's processing
fee is a Stripe configuration, not something the app decides. Reading it keeps
"You keep" correct whichever way that is set, and survives it being changed.

`stripe_fee_cents` is **NULL when unknown, which is not zero.** Zero is a fact
(the platform absorbed it); NULL means the lookup hasn't run or failed. While
any payment in the window is NULL, the API reports `fees_complete: false` and
the screens present the kept figure as a ceiling — a total quietly short by
Stripe's cut is the exact failure this column exists to prevent.

To fill in rows recorded before the lookup existed, or ones whose lookup
failed:

```bash
flask stripe-backfill-fees --dry-run
flask stripe-backfill-fees
```

Only touches payment rows still NULL, so it is safe to re-run.

## What gets written

Every money event lands in `garden_finance_event` (see `app/garden_finance.py`),
which is the only thing the finance screens read. Two scopes share the table:

- **Garden-scoped** (`garden_id`) — payments, refunds, disputes. These sum into
  a garden's totals.
- **Account-scoped** (`user_id`, `garden_id` NULL) — payouts and account status.
  A payout covers the whole Stripe account, which may span several gardens, so
  attributing it to one would make that garden's books wrong. It appears in the
  garden's activity feed and is excluded from its totals.

Rows are **upserted** on `(kind, stripe_object_id)`. This is not an
optimisation: Stripe reports `amount_refunded` cumulatively, so appending a row
per delivery would claim more money was returned than was ever charged.

Idempotency is belt-and-braces: `ProcessedStripeEvent` short-circuits a
redelivered event id, and the upsert key means the same object arriving under a
*new* event id still can't double-count.

## Testing locally

The route accepts unsigned JSON only when `STRIPE_SECRET_KEY` is absent (dev
and the test suite). With real keys present, an unsigned event is refused with
503 rather than trusted — otherwise anyone who found the URL could forge
`payment_intent.succeeded` and mark dues paid.

```bash
curl -X POST http://localhost:5000/api/webhooks/stripe \
  -H 'Content-Type: application/json' \
  -d '{"id":"evt_1","type":"payout.paid","account":"acct_x",
       "data":{"object":{"id":"po_1","amount":4850,"currency":"usd",
                         "status":"paid","created":1756000000}}}'
```

`tests/test_garden_finance.py` drives every handler this way.
