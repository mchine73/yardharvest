# Project Plan — Tap to Pay (Soft POS) for Garden Managers

**Status:** Proposed · **Owner:** TBD · **Last updated:** 2026-06-19

## 1. Goal

Let a garden manager **accept in‑person card payments on their own phone** — tap a
physical card, Apple Pay, or Google Pay against the device, no extra hardware —
with the money routed to **that garden's** Stripe account, minus YardHarvest's
platform fee. This is "soft POS," delivered by **Stripe Tap to Pay** (part of
Stripe Terminal).

Primary use cases (all in person):
- Collecting **annual dues / plot fees** at a sign‑up table or work day.
- **Event** tickets, plant‑sale, or workshop payments.
- **Donations** to the garden.

This complements the existing **online** dues flow (Stripe Connect destination
charges) — same money model, new "card present" channel.

---

## 2. The pivotal constraint (read this first)

**Tap to Pay only works inside a native mobile app. It cannot run in a web
browser / PWA.** Apple's Tap to Pay on iPhone uses the device's secure NFC
hardware through the Stripe Terminal **native SDK**, gated behind an Apple
entitlement. There is no web API for it. YardHarvest today is a **React (web)
SPA + Flask** — which has no path to Tap to Pay as‑is.

So this project is, unavoidably, **"add a mobile app capability."** Everything
below flows from that decision.

### Device / platform requirements
- **Tap to Pay on iPhone:** iPhone XS or newer, **iOS 16.4+**, and an Apple
  **development + publishing entitlement** (`proximity-reader.payment.acceptance`).
  Dev entitlement is usually auto‑approved in ~1–2 business days; the publishing
  entitlement review takes ~1–2 weeks. Requires enrollment in the Apple Developer
  Program and Apple Business Register.
- **Tap to Pay on Android:** Android 11+ with NFC. **No prior approval** needed —
  simpler than iOS.
- US‑first (YardHarvest is US/Omaha). Confirm regional availability before
  expanding.

---

## 3. Approach options & recommendation

| Option | What it is | Pros | Cons |
|---|---|---|---|
| **A. React Native app** (recommended) | A focused "YardHarvest for Garden Managers" app using `@stripe/stripe-terminal-react-native` (supports Tap to Pay, iOS + Android, currently public preview) | One codebase for both platforms; closest to the team's existing React skills; reuses the Flask API; Stripe‑maintained SDK | New app to build/maintain + app‑store presence; SDK is in public preview |
| **B. Native Swift / Kotlin apps** | Two native apps using the iOS/Android Terminal SDKs | Most robust, GA SDKs | Two codebases, two skill sets, slowest |
| **C. Hardware reader instead** | Keep web‑only; managers use a Stripe Terminal reader (e.g. WisePOS/Tap to Pay‑capable reader) paired to the web app via the JS SDK | No native app; works from the existing SPA | Not "soft POS" — it's hardware ($$, logistics); not what was asked |
| **D. Do nothing / QR‑to‑online** | Manager shows a QR that opens the existing online dues page on the payer's phone | Zero build | Payer needs their own device + to type card details; not a tap, not a POS |

**Recommendation: Option A (React Native).** It's the only option that delivers
true soft POS, covers both phone platforms from one codebase, leans on the
team's React experience, and reuses the Flask/Connect backend we already run.
Keep **Option D (QR‑to‑online)** as a zero‑cost interim while the app is built.

---

## 4. How this fits YardHarvest's existing Stripe Connect

We already run **destination charges** for online dues: a charge is created on
the platform with funds routed to the garden's connected account, and we take a
platform fee. **Tap to Pay supports the exact same model**, so the money flow,
payouts, and reporting stay consistent. Verified specifics for the
destination‑charge model with Terminal:

- **PaymentIntent** (created server‑side on Flask — recommended): `card_present`
  payment method, `capture_method=manual`, with
  `on_behalf_of=<garden_connected_account>`,
  `transfer_data[destination]=<garden_connected_account>`, and
  `application_fee_amount=<platform fee>`.
- **Connection token** (for the destination model): created with the **platform
  secret key only — NO `Stripe-Account` header** — scoped by a **`location`** so a
  manager's app can only use readers (phones) registered to their garden.
  *(Note: this differs from the direct‑charge model, which does use the
  `Stripe-Account` header — we are deliberately using destination charges to
  match dues.)*
- The connected account must have the **`card_payments` capability** (our dues
  gardens already do).

Net effect: a garden that's already onboarded for online dues needs **no new
Stripe onboarding** to start taking in‑person payments.

---

## 5. Target architecture

```
┌─────────────────────────────┐        ┌──────────────────────────────┐
│  RN app (Garden Manager)    │        │  Flask backend (existing)     │
│  - login (reuse JWT auth)   │  HTTPS │  - POST /terminal/connection- │
│  - @stripe/terminal-rn SDK  │◀──────▶│      token  (platform key,    │
│  - Tap to Pay reader = phone│        │      location-scoped)         │
│  - collect payment UI       │        │  - POST /terminal/payment-    │
└──────────────┬──────────────┘        │      intent (destination +    │
               │ NFC tap                │      app fee, on_behalf_of)   │
               ▼                        │  - record payment → dues/     │
        card / Apple Pay /              │      plot / event             │
        Google Pay                      │  - Stripe webhooks (reconcile)│
                                        └───────────────┬──────────────┘
                                                        ▼
                                              Stripe (Terminal + Connect)
                                              Locations (1 per garden),
                                              readers = managers' phones
```

New backend pieces (small — mostly reuse `stripe_service`):
1. `POST /api/terminal/connection-token` — auth'd to a garden manager; creates a
   token scoped to that garden's **Location**.
2. `POST /api/terminal/payment-intent` — builds the destination PaymentIntent
   (amount, `on_behalf_of`, `transfer_data[destination]`, `application_fee_amount`),
   tied to a dues record / plot / event.
3. **Location provisioning** — create a Stripe Terminal `Location` per garden
   (lazily, first time a manager enables in‑person payments), stored on the
   garden row (e.g. `stripe_terminal_location_id`).
4. **Webhook handling** — extend the existing webhook to reconcile
   `payment_intent.succeeded` for `card_present` and mark the dues/plot/event paid.

---

## 6. Phased plan

> Estimates assume ~1 developer. Apple entitlement reviews run **in parallel** —
> start them on day 1.

| Phase | Scope | Est. |
|---|---|---|
| **0. Decision & accounts** | Confirm Option A; enable **Stripe Terminal** on the platform account; enroll Apple Developer + **Apple Business Register**; request the **development** Tap‑to‑Pay entitlement; pick iOS‑only vs iOS+Android for v1. | 2–3 days (+ entitlement wait) |
| **1. Backend** | Connection‑token + destination PaymentIntent endpoints; per‑garden Location provisioning + `stripe_terminal_location_id` column/migration; webhook reconciliation; tests (incl. Postgres). No app needed to test the API. | ~1 week |
| **2. RN app skeleton** | New React Native app; reuse JWT login against the existing API; manager picks their garden; CI + TestFlight/internal‑track build. | ~1–1.5 weeks |
| **3. Tap to Pay integration** | Add `@stripe/stripe-terminal-react-native`; wire token provider → backend; discover/connect the phone as a Tap to Pay reader; "collect dues" flow (amount → tap → confirm → receipt). | ~1.5–2 weeks |
| **4. Link to records + receipts** | Attach payment to a dues record / plot / event; email/SMS receipt (reuse ZeptoMail); in‑app history; partial/again handling. | ~1 week |
| **5. Pilot** | TestFlight / Play internal testing with **one friendly garden**; real low‑value taps; reconcile payouts; fix. | ~1 week + soak |
| **6. Launch** | Obtain the **publishing** entitlement; App Store + Play submissions; store listings; rollout + manager docs (extend the garden‑admin guide). | ~1–2 weeks (review‑bound) |

**Rough total:** ~7–9 weeks of build, with Phase 6 partly gated by Apple/Google
review and the publishing entitlement.

---

## 7. Prerequisites checklist

- [ ] Stripe **Terminal enabled** on the platform account.
- [ ] Connected (garden) accounts have **`card_payments`** capability — dues
      gardens already do; verify for any new ones.
- [ ] Apple Developer Program enrollment + **Apple Business Register**.
- [ ] Tap‑to‑Pay **development** entitlement (start early).
- [ ] Tap‑to‑Pay **publishing** entitlement (before store launch).
- [ ] Test devices: an iPhone XS+ on iOS 16.4+ (and/or Android 11+ w/ NFC).
- [ ] Decide the **platform fee** for in‑person payments (`application_fee_amount`).

---

## 8. Risks & mitigations

| Risk | Mitigation |
|---|---|
| **Native app is a new surface** to build/maintain | Keep the app thin — it's a payment terminal + thin record link; all business logic stays in Flask. Ship QR‑to‑online (Option D) as the interim. |
| **Apple entitlement / review delays** | Request the dev entitlement on day 1; treat publishing as a long‑lead item; build/pilot via TestFlight meanwhile. |
| **RN Terminal SDK is "public preview"** | Pin versions; watch Stripe's changelog; have the native‑SDK fallback (Option B) in mind if blockers appear. |
| **Stripe in‑person fees** reduce garden net | Show fees transparently; decide whether the platform fee is reduced for in‑person; document for managers. |
| **Device coverage** (older phones) | Publish the supported‑device list; the hardware reader (Option C) is the fallback for unsupported devices. |
| **Refunds / disputes in person** | Build refund into the app/back office from day 1; Stripe handles dispute plumbing. |
| **PCI / security** | Card data never touches our servers or the app — Stripe's SDK + secure element handle it; we only see PaymentIntents. Keep the connection token endpoint auth’d + location‑scoped. |

---

## 9. Open decisions (need a call before Phase 1)

1. **Platforms for v1:** iOS‑only (faster, but excludes Android managers) vs
   iOS + Android (RN gives both, modest extra effort). *Recommendation: both,
   since RN makes it cheap.*
2. **New app vs. extend:** stand up a dedicated "Garden Manager" RN app vs.
   broaden into a general member app later. *Recommendation: dedicated manager
   app first.*
3. **Scope of payments for v1:** dues only, or dues + events + donations.
   *Recommendation: dues first, generalize in Phase 4.*
4. **Fees:** does the platform application fee change for in‑person vs online?
5. **Gating:** is in‑person payment a **Garden Pro** feature, or available to all
   gardens with payouts connected?

---

## 10. Success metrics

- # gardens that enable in‑person payments; # managers who complete a real tap.
- $ collected in person / month; share of dues paid in person vs online.
- Time‑to‑first‑payment for a newly enabled garden.
- Payment success rate; refund/dispute rate.

---

## 11. Out of scope (for now)

- Hardware readers (WisePOS, etc.) — revisit only for unsupported devices.
- Non‑US regions.
- Offline payments / store‑and‑forward.
- A full consumer/member mobile app (this is manager‑facing only).

---

### Sources (Stripe, verified 2026‑06‑19)
- [Tap to Pay — Stripe Terminal](https://stripe.com/terminal/tap-to-pay)
- [Tap to Pay setup — Stripe Docs](https://docs.stripe.com/terminal/payments/setup-reader/tap-to-pay)
- [Use Terminal with Connect — Stripe Docs](https://docs.stripe.com/terminal/features/connect)
- [Terminal + Connect: destination charges](https://docs.stripe.com/terminal/features/connect.md?connect-charge-type=destination)
- [Stripe Terminal React Native SDK](https://github.com/stripe/stripe-terminal-react-native)
- [Tap to Pay on iPhone / Android — Stripe support](https://support.stripe.com/questions/tap-to-pay-on-iphone-or-android-and-stripe-terminal)
