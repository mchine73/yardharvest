# 05 - Payment Flows

All Stripe calls flow through `app/stripe_service.py`. There are three distinct
money flows, plus a shared webhook path. In dev (no `STRIPE_SECRET_KEY`) each
endpoint returns a `dev_mode` response and skips Stripe — so **production must
set `STRIPE_SECRET_KEY` / `STRIPE_PUBLISHABLE_KEY` / `STRIPE_WEBHOOK_SECRET`
(+ `APP_URL`)** or the UI shows the dev "Test Payment" placeholder and no money
moves.

Seller and garden-manager payouts use **Stripe Connect Express** accounts
(`create_connect_account_link` → `Account.create(type='express', capabilities=
{card_payments, transfers})`): Stripe-hosted onboarding via `AccountLink`, and
an Express dashboard `login_link` once `charges_enabled && payouts_enabled`.

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
    ST-->>PAY: client_secret
    PAY-->>FE: client_secret + publishable_key
    FE->>ST: confirmCardPayment(client_secret) (Stripe.js)
    ST-->>FE: succeeded

    FE->>PAY: POST /api/payments/confirm (payment_intent_id)
    PAY->>SS: retrieve_payment_intent(), assert status == succeeded
    PAY->>DB: create Order(+OrderItems) per seller, decrement stock, clear cart
    loop each seller with Connect account
        PAY->>SS: create_transfer(seller_earnings, dest=connect_acct, group=pi)
        SS->>ST: Transfer.create
        PAY->>DB: SellerPayout(status=completed, stripe_transfer_id)
    end
    PAY->>DB: apply promo usage
    PAY-->>FE: order_ids
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
(`GARDEN_DUES_FEE_PERCENT`). If the manager has no payout-ready Connect account,
it falls back to a plain platform charge so collection still works.

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
        GA->>GA: application_fee = amount * GARDEN_DUES_FEE_PERCENT/100 (optional)
        GA->>SS: create_payment_intent(amount, customer,<br/>destination=mgr, on_behalf_of=mgr, application_fee)
        Note right of SS: Destination charge -> funds to manager,<br/>platform keeps app fee
    else manager not payout-ready (fallback)
        GA->>SS: create_payment_intent(amount, customer)
        Note right of SS: Plain platform charge
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

`POST /api/webhooks/stripe` (`webhook_api`). Signature is verified via
`STRIPE_WEBHOOK_SECRET`; events are dispatched through an `EVENT_HANDLERS` map.

```mermaid
flowchart TB
    ST["Stripe"] -->|"POST /api/webhooks/stripe<br/>+ Stripe-Signature"| WH["webhook_api.stripe_webhook"]
    WH -->|"construct_webhook_event (verify sig)"| IDEM{"event.id seen?<br/>(ProcessedStripeEvent)"}
    IDEM -->|yes| SKIP["200 duplicate (skip)"]
    IDEM -->|no| DISP{"event.type"}
    DISP -->|"payment_intent.succeeded<br/>(type=garden_dues)"| H0["settle GardenDuesRecord (idempotent)"]
    DISP -->|payment_intent.succeeded| H1["mark Order payment succeeded"]
    DISP -->|payment_intent.payment_failed| H2["mark Order payment failed"]
    DISP -->|charge.refunded| H3["sync Order refund_status/amount"]
    DISP -->|transfer.created| H4["record SellerPayout"]
    DISP -->|account.updated| H5["set User.stripe_onboarding_complete"]
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
```

## Notes

- Marketplace uses **separate charges & transfers** (platform charge + later
  `Transfer`), while garden dues use a **destination charge**
  (`transfer_data.destination` + `on_behalf_of`) — two different Connect models
  in the same codebase.
- Refunds (`refund_api`, admin) issue `Refund.create` for marketplace orders and
  may `reverse_transfer` the seller payout; Garden Pro refunds cancel/refund the
  subscription. The `charge.refunded` webhook also back-syncs dashboard refunds.
- **Idempotency:** every webhook event id is recorded in `ProcessedStripeEvent`
  (UNIQUE); redeliveries short-circuit with `200 duplicate`. An event is only
  recorded after its handler succeeds, so a failing handler returns 500 and
  Stripe retries. Handlers are also individually idempotent (guard on current
  state) as defense-in-depth.
- **Payout holds:** marketplace transfers only fire when the seller's Connect
  account is fully payout-ready; otherwise a `SellerPayout(status='pending')`
  records the amount owed (surfaced in Grower Earnings) instead of the platform
  silently keeping it. Managers reach Connect onboarding via the admin portal
  "Billing & Payouts" link.
- **Known follow-up:** marketplace *order creation* still happens in the client
  `/confirm` call (idempotent, but if the buyer's browser dies between payment
  and confirm, no order is created despite the charge). The dues flow is already
  webhook-guaranteed; the marketplace should get the same treatment via a
  checkout snapshot fulfilled from `payment_intent.succeeded`.
