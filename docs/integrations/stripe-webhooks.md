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

## Setting it up (Stripe dashboard → Developers → Webhooks)

Both endpoints use the same URL: `https://www.yardharvest.app/api/webhooks/stripe`

### 1. Platform endpoint

Add an endpoint, leave "Listen to events on Connected accounts" **unchecked**,
and select:

| Event | What it does here |
|---|---|
| `payment_intent.succeeded` | Settles dues (online **and** in-person) and writes every garden payment to the finance ledger. The guarantee path — collection no longer depends on a browser or a phone calling back. |
| `payment_intent.payment_failed` | Marks marketplace orders failed; records a declined garden charge so a manager can check whether money ever arrived. |
| `charge.refunded` | Syncs marketplace refunds, ledgers garden refunds, and puts a fully-refunded member back on the dues roster. |
| `charge.dispute.created` / `.updated` / `.closed` | Chargebacks on garden money. Notifies the organizer while there is still time to respond. |
| `customer.subscription.created` / `.updated` / `.deleted` | Garden Pro status and billing periods. Also the activation-of-last-resort for a paid subscription. |
| `invoice.payment_failed` | Garden Pro dunning → `past_due`. |
| `transfer.created` | Records a marketplace `SellerPayout`. |

### 2. Connect endpoint

Add a **second** endpoint at the same URL with "Listen to events on Connected
accounts" **checked**, and select:

| Event | What it does here |
|---|---|
| `account.updated` | Mirrors the manager's account health (charges/payouts enabled, outstanding requirements, disabled reason) and notifies them when it slips. Without this, a restriction first surfaces as a failed tap in front of a member. |
| `payout.created` / `payout.paid` / `payout.failed` | "When does the money reach my bank." Payouts belong to the connected account, so they arrive **only** here. |

Copy that endpoint's signing secret into `STRIPE_CONNECT_WEBHOOK_SECRET` in the
Render dashboard (web service). Dashboard-set env vars survive blueprint syncs;
`render.yaml` is not to be edited.

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
