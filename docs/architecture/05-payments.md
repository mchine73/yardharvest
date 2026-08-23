# 05 - Payment Flows

All Stripe calls flow through `app/stripe_service.py`. There are three distinct
money flows, plus a shared webhook path. In dev (no `STRIPE_SECRET_KEY`) each
endpoint returns a `dev_mode` response and skips Stripe — so **production must
set `STRIPE_SECRET_KEY` / `STRIPE_PUBLISHABLE_KEY` / `STRIPE_WEBHOOK_SECRET`
(+ `APP_URL`)** or the UI shows the dev "Test Payment" placeholder and no money
moves.

Seller and garden-manager payouts use **Stripe Connect Express** accounts
(`ensure_connect_account` → `Account.create(type='express', capabilities=
{card_payments, transfers, us_bank_account_ach_payments})` — the ACH capability
lets members pay dues by bank, since the connected account is merchant-of-record
on dues). Onboarding is **embedded in-app** by default via
`create_account_session()` (Stripe Connect embedded components, rendered by
`StripeConnectOnboarding.jsx`), with Stripe-**hosted** `AccountLink`
(`create_connect_account_link`) as the automatic fallback when the embedded
component can't load. An Express dashboard `login_link` is offered once
`charges_enabled && payouts_enabled`.

> The embedded components load `Connect.js` from `connect-js.stripe.com`, so the
> CSP in `app/__init__.py` must allow that host in `script-src`/`frame-src` plus
> `connect-src` (also `merchant-ui-api.stripe.com`) — see `06-deployment.md`.

**Self-healing ids (test→live cutover):** `ensure_connect_account` and
`get_or_create_customer` recreate a stored Connect/customer id when Stripe
rejects it with `InvalidRequestError` *or* `PermissionError` (e.g. a leftover
test-mode id under live keys); `create_connect_account_link` /
`create_account_session` additionally reset + retry once if the account link
itself is rejected. This makes the test→live key switch seamless.

## (a) Marketplace checkout + seller payout

`payment_api` (`/api/payments`). The platform takes a commission; the seller's
share is sent as a Stripe **Transfer** to their connected account (separate
charges-and-transfers model).

```mermaid
sequenceDiagram
    actor B as Buyer
    participant FE as React SPA
    participant PAY as payment_api
    participant SS as stripe_service
    participant ST as Stripe
    participant DB as Postgres

    B->>FE: Checkout
    FE->>PAY: POST /api/payments/create-session
    PAY->>PAY: sum cart effective prices + per-seller delivery fees + promo
    PAY->>SS: get_or_create_customer(buyer)
    SS->>ST: Customer.create / reuse
    PAY->>SS: create_payment_intent(total, customer)
    SS->>ST: PaymentIntent.create (metadata type=marketplace_order)
    PAY->>DB: PendingCheckout snapshot (basket + fulfillment + promo) keyed by PI id
    ST-->>PAY: client_secret
    PAY-->>FE: client_secret + publishable_key
    FE->>ST: confirmCardPayment(client_secret) (Stripe.js)
    ST-->>FE: succeeded

    Note over PAY,DB: fulfill_payment_intent(pi) — shared + idempotent.<br/>Runs from the SNAPSHOT, triggered by whichever arrives first:
    par instant path
        FE->>PAY: POST /api/payments/confirm (payment_intent_id)
        PAY->>SS: retrieve_payment_intent(), assert succeeded
        PAY->>PAY: fulfill_payment_intent(pi, buyer)
    and guarantee path
        ST->>PAY: webhook payment_intent.succeeded
        PAY->>PAY: fulfill_payment_intent(pi, snapshot.buyer)
    end
    PAY->>DB: create Order(+OrderItems) per seller, decrement stock, clear cart
    loop each seller (payout-ready -> transfer, else held 'pending')
        PAY->>SS: create_transfer(seller_earnings, dest=connect_acct, group=pi)
        PAY->>DB: SellerPayout(completed | pending)
    end
    PAY->>DB: apply promo usage, mark snapshot fulfilled
    PAY->>PAY: send order confirmation + new-order emails
```

## (b) Garden Pro trial -> subscription (Stripe Subscriptions)

`garden_billing_api` (`/api/gardens/<id>/billing`). Trial requires no payment.
Conversion uses a `default_incomplete` Subscription whose latest invoice's
PaymentIntent the client confirms, then the backend activates the record.

```mermaid
sequenceDiagram
    actor M as Garden Manager
    participant FE as React SPA
    participant GB as garden_billing_api
    participant SS as stripe_service
    participant ST as Stripe
    participant DB as Postgres

    Note over M,DB: 1) Start free trial
    M->>FE: Start trial
    FE->>GB: POST /<id>/billing/start-trial
    GB->>DB: GardenSubscription(status=trialing, trial_end=+14d)
    GB->>SS: get_or_create_customer(organizer) (pre-create)
    GB-->>FE: trialing

    Note over M,DB: 2) Convert to paid
    M->>FE: Subscribe (monthly/yearly)
    FE->>GB: POST /<id>/billing/create-checkout
    GB->>SS: ensure_garden_pro_products() -> price_id
    GB->>SS: create_subscription(customer, price, payment_behavior=default_incomplete)
    SS->>ST: Subscription.create (expand latest_invoice.payment_intent)
    ST-->>GB: subscription + invoice.payment_intent.client_secret
    GB-->>FE: client_secret + subscription_id
    FE->>ST: confirmCardPayment(client_secret)
    ST-->>FE: succeeded

    FE->>GB: POST /<id>/billing/subscribe (subscription_id, billing_cycle)
    GB->>SS: retrieve_subscription(), read current_period_end
    GB->>DB: GardenSubscription status=active, garden.subscription_status=active
    GB-->>FE: activated

    Note over ST,DB: Async: invoice.payment_failed -> past_due,<br/>customer.subscription.updated/deleted sync via webhook
```

## (c) Garden dues -> manager Connect destination charge

`gardens_api` (`/api/gardens/<id>/dues/<id>/pay`). Dues are charged **on behalf
of** and routed **directly to the garden manager's** connected account
(destination charge), with an optional platform `application_fee`
(admin-editable `PricingConfig.garden_dues_fee_percent`, with the legacy
`GARDEN_DUES_FEE_PERCENT` env var as fallback). Behavior when the manager **isn't** payout-ready is controlled by the admin
switch **`PricingConfig.dues_require_payout_ready`** (Admin → Pricing →
"Require payout setup before collecting dues", default **ON**):
- **ON** — collection is **refused with `409` (`reason: manager_payout_not_ready`)**
  so dues are never charged to the platform; every successful charge routes to
  the manager. The garden admin dashboard's "Finish account payout set-up"
  banner prompts the manager to onboard.
- **OFF** — dues fall back to a plain platform charge so collection always works
  (those funds land with the platform until reconciled to the manager manually).

```mermaid
sequenceDiagram
    actor G as Gardener (member)
    participant FE as React SPA
    participant GA as gardens_api
    participant SS as stripe_service
    participant ST as Stripe
    participant DB as Postgres

    G->>FE: Pay dues
    FE->>GA: POST /<gid>/dues/<did>/pay
    GA->>DB: load GardenDuesRecord, compute remaining balance
    GA->>SS: get_or_create_customer(gardener)
    alt manager Connect account ready
        GA->>GA: destination = organizer.stripe_connect_account_id
        GA->>GA: application_fee = amount * PricingConfig.garden_dues_fee_percent/100 (optional)
        GA->>SS: create_payment_intent(amount, customer,<br/>destination=mgr, on_behalf_of=mgr, application_fee)
        Note right of SS: Destination charge -> funds to manager,<br/>platform keeps app fee
    else manager not payout-ready
        GA-->>FE: 409 manager_payout_not_ready (no charge)
        Note right of GA: Collection refused — dues never go to the platform
    end
    SS->>ST: PaymentIntent.create (metadata type=garden_dues)
    ST-->>GA: client_secret + routed_to_manager flag
    GA-->>FE: client_secret + publishable_key
    FE->>ST: confirmCardPayment(client_secret)
    ST-->>FE: succeeded
    FE->>GA: POST /<gid>/dues/<did>/confirm-payment (payment_intent_id)
    GA->>SS: retrieve_payment_intent(), assert succeeded
    GA->>DB: update GardenDuesRecord (amount_paid, status=paid, stripe_payment_intent_id)
    GA-->>FE: confirmed
    Note over ST,DB: GUARANTEE: payment_intent.succeeded (type=garden_dues) also<br/>settles the dues record server-side — collection no longer<br/>depends on the browser calling confirm. Idempotent on PI id.
```

## Shared webhook path

`POST /api/webhooks/stripe` (`webhook_api`). Events are dispatched through an
`EVENT_HANDLERS` map; each handler receives both the event object and the whole
event, because Connect events identify the garden manager only through the
top-level `account` field.

**Two Stripe endpoints point at this one route.** A *platform* endpoint carries
charges, refunds, disputes and subscriptions; a *Connect* endpoint (created with
"listen to events on connected accounts") carries `payout.*` and
`account.updated`, which connected accounts emit and the platform never sees.
Stripe issues a separate signing secret per endpoint, so
`construct_webhook_event` tries `STRIPE_WEBHOOK_SECRET` and then
`STRIPE_CONNECT_WEBHOOK_SECRET` — with only one configured, every event from the
other endpoint fails signature verification and looks exactly like an attack in
the logs. Setup and verification: `docs/integrations/stripe-webhooks.md`;
coverage probe: `GET /api/health/stripe/webhooks`.

```mermaid
flowchart TB
    ST["Stripe"] -->|"POST /api/webhooks/stripe<br/>+ Stripe-Signature"| WH["webhook_api.stripe_webhook"]
    WH -->|"construct_webhook_event (verify sig)"| IDEM{"event.id seen?<br/>(ProcessedStripeEvent)"}
    IDEM -->|yes| SKIP["200 duplicate (skip)"]
    IDEM -->|no| DISP{"event.type"}
    DISP -->|"payment_intent.succeeded<br/>(garden dues / in-person dues / sale)"| H0["settle GardenDuesRecord (idempotent)<br/>+ GardenFinanceEvent(payment)"]
    DISP -->|"payment_intent.succeeded<br/>(marketplace)"| H1["fulfill_payment_intent from PendingCheckout snapshot (idempotent)"]
    DISP -->|payment_intent.payment_failed| H2["mark Order payment failed<br/>or GardenFinanceEvent(payment_failed)"]
    DISP -->|charge.refunded| H3["sync Order refund_status/amount<br/>+ GardenFinanceEvent(refund), un-settle dues"]
    DISP -->|charge.dispute.*| H9["GardenFinanceEvent(dispute) + notify organizer"]
    DISP -->|transfer.created| H4["record SellerPayout"]
    DISP -->|"account.updated (Connect)"| H5["mirror charges/payouts/requirements<br/>onto User + notify on a state change"]
    DISP -->|"payout.* (Connect)"| H10["GardenFinanceEvent(payout, account-scoped)<br/>+ notify organizer"]
    DISP -->|customer.subscription.updated| H6["sync GardenSubscription status + periods"]
    DISP -->|customer.subscription.deleted| H7["GardenSubscription -> expired + email"]
    DISP -->|invoice.payment_failed| H8["GardenSubscription -> past_due + dunning email"]
    H0 --> DB[("Postgres")]
    H1 --> DB
    H2 --> DB
    H3 --> DB
    H4 --> DB
    H5 --> DB
    H6 --> DB
    H7 --> DB
    H8 --> DB
    H9 --> DB
    H10 --> DB
```

## (d) The garden money ledger

`garden_finance_event` (`app/garden_finance.py`) is a manager-facing record of
what Stripe did, written **only** by the webhook path. It exists because a
manager's money lived entirely in the Stripe dashboard: a Tap-to-Pay sale wrote
nothing to YardHarvest at all, an in-person dues tap depended on the iOS app
completing its finalize call, a refund issued from the dashboard never reached
the roster, and payouts and chargebacks had no representation.

Two scopes share the table. **Garden-scoped** rows (`garden_id`) — payments,
refunds, disputes — sum into a garden's totals. **Account-scoped** rows
(`user_id`, `garden_id` NULL) — payouts and connected-account status — do not:
a payout covers the whole Stripe account, which may span several gardens, so
folding it into one would make that garden's books wrong. Both appear in the
garden's activity feed; only the first kind is summed.

Rows are upserted on `(kind, stripe_object_id)` because Stripe reports
`amount_refunded` cumulatively — appending per delivery would claim more was
refunded than was ever charged.

Read by `GET /api/garden-admin/<id>/finance/{activity,payouts,stripe-status}`
and folded into `finance-summary` as a `stripe` block *beside* the dues figures,
not merged into them: the roster's "collected" includes cash and says nothing
about fees. These three endpoints use `require_garden_admin`, **not** the Pro
gate the rest of the Finance tab uses — the endpoints that take this money
aren't Pro-gated either, and a paywall between a manager and the record of
their own collections is the wrong trade. Surfaced as Finance → **Stripe** on
the web and the **Money** screen in the iOS Payments hub.

## Notes

- Marketplace uses **separate charges & transfers** (platform charge + later
  `Transfer`), while garden dues use a **destination charge**
  (`transfer_data.destination` + `on_behalf_of`) — two different Connect models
  in the same codebase.
- Refunds (`refund_api`, admin) issue `Refund.create` for marketplace orders and
  may `reverse_transfer` the seller payout; Garden Pro refunds cancel/refund the
  subscription. The `charge.refunded` webhook also back-syncs dashboard refunds.
- **Connected-account health** is mirrored onto `User.stripe_charges_enabled` /
  `stripe_payouts_enabled` / `stripe_requirements_due` / `stripe_disabled_reason`
  by `account.updated`, so the finance screens answer "can this garden take
  money, and can it be paid" with no Stripe round-trip — and a restriction
  reaches the manager before it reaches a member at the plot gate.
  `stripe_account_synced_at` being NULL means no such event has ever arrived,
  which is itself the diagnosis (no Connect endpoint), and the UI says so.
- **Idempotency:** every webhook event id is recorded in `ProcessedStripeEvent`
  (UNIQUE); redeliveries short-circuit with `200 duplicate`. An event is only
  recorded after its handler succeeds, so a failing handler returns 500 and
  Stripe retries. Handlers are also individually idempotent (guard on current
  state) as defense-in-depth.
- **Payout holds:** marketplace transfers only fire when the seller's Connect
  account is fully payout-ready; otherwise a `SellerPayout(status='pending')`
  records the amount owed (surfaced in Grower Earnings) instead of the platform
  silently keeping it. Managers reach Connect onboarding via the admin portal
  "Billing & Payouts" link, and the garden admin dashboard shows a "Finish
  account payout set-up" banner while `payoutStatus` is `configured && !ready`.
- **Payment methods are restricted to card + `us_bank_account` (ACH) only** via
  explicit `payment_method_types` (no Amazon Pay / Cash App Pay / Klarna). ACH on
  a destination charge is gated on the connected account actually having the
  capability active (`connect_payment_method_types`), so dues collection never
  breaks if ACH isn't enabled.
- **Go-live health probe:** `GET /api/health/stripe` reports `{mode, configured,
  auth_ok, connect_ok, error}` — `mode` is `live`/`test` from the key prefix,
  `auth_ok` proves the secret key authenticates (`Balance.retrieve`), and
  `connect_ok` proves Connect is enabled (`Account.list`). This is the canonical
  way to verify a key swap landed. (Note: `connect_ok` only proves listing works,
  not that Express account *creation* is enabled — an incomplete Connect platform
  profile surfaces only when onboarding actually runs.)
- **Webhook-guaranteed marketplace fulfillment:** at `create-session` a
  `PendingCheckout` snapshot (basket + per-seller fulfillment + promo) is stored
  keyed by the PaymentIntent. Orders are created by the shared
  `payment_api.fulfill_payment_intent`, called by **both** the client `/confirm`
  (instant) and the `payment_intent.succeeded` webhook (guarantee), reading the
  snapshot so the order matches exactly what was charged. Idempotent (per-PI
  order guard), so a browser death between pay and confirm can no longer leave a
  charge without orders. Dev mode (no snapshot) falls back to the live cart.
