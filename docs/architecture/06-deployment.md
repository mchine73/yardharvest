# 06 - Deployment Topology

YardHarvest is deployed on **Render** via `render.yaml` (Blueprint/IaC). One
GitHub repo drives a web service, a cron job, and a managed Postgres database.

```mermaid
flowchart TB
    Dev["Developer"] -->|git push| GH["GitHub repo<br/>yardharvest"]

    subgraph Actions["GitHub Actions"]
        Tests[".github/workflows/tests.yml<br/>push + PR<br/>pytest on SQLite + Postgres"]
        APICheck[".github/workflows/api-keys-check.yml<br/>workflow_dispatch (manual)<br/>scripts/check_api_keys.py"]
    end
    GH -->|push / PR| Tests
    GH -.->|manual run| APICheck

    GH -->|auto deploy| Render

    subgraph Render["Render (render.yaml)"]
        Web["Web Service: yardharvest<br/>build: bash build.sh<br/>start: gunicorn wsgi:app<br/>(schema + seed run in build.sh)"]
        Cron["Cron: yardharvest-trial-lifecycle<br/>schedule '0 8 * * *'<br/>start: flask garden-trial-lifecycle"]
        CronFB["Cron: yardharvest-facebook-scheduler<br/>schedule '*/15 * * * *'<br/>start: flask publish-due-facebook-posts"]
        PG[("Postgres: yardharvest-db<br/>(free plan)")]
    end

    Web --> PG
    Cron --> PG
    CronFB --> PG

    subgraph BuildSteps["build.sh"]
        B1["pip install -r requirements.txt"]
        B2["cd frontend && npm install && npm run build<br/>(Vite -> frontend/dist)"]
        B3["python db_upgrade.py<br/>(Alembic: upgrade / stamp)"]
        B4["python seed_if_empty.py"]
        B1 --> B2 --> B3 --> B4
    end
    Web -. build phase .-> BuildSteps

    subgraph Ext["External APIs (via secrets)"]
        Stripe["Stripe"]
        Twilio["Twilio"]
        Email["Zoho ZeptoMail"]
        DoorDash["DoorDash Drive"]
        OpenWeather["OpenWeather"]
    end
    Web --> Stripe
    Web --> Twilio
    Web --> Email
    Web --> DoorDash
    Web --> OpenWeather
    Stripe -->|webhooks| Web
    Cron --> Email
    Cron --> Twilio
```

## Runtime topology

```mermaid
flowchart LR
    Browser["Browser SPA"] -->|HTTPS| Web
    MobileApp["Mobile app (JWT)"] -->|HTTPS| Web
    subgraph Web["Render Web Service"]
        GU["gunicorn -> wsgi:app"]
        SPA["Flask serves frontend/dist<br/>(SPA fallback to index.html)"]
        API["Flask REST API /api/*"]
        GU --> SPA
        GU --> API
    end
    API --> PG[("Render Postgres")]
```

## Environment & secrets

| Variable | Set by | Used for |
|---|---|---|
| `DATABASE_URL` | Render (fromDatabase) | Postgres connection (`postgres://` rewritten to `postgresql://`); also the prod flag (enables Secure cookies, HSTS) |
| `SECRET_KEY` | Render (`generateValue` web; `sync:false` cron) | Flask session signing; **fatal if missing in prod** |
| `JWT_SECRET_KEY` | env (defaults to `SECRET_KEY + '-jwt'`) | JWT signing |
| `PYTHON_VERSION` / `NODE_VERSION` | render.yaml | 3.11.6 / 20 build toolchain |
| `FLASK_APP=wsgi:app` | render.yaml (cron) | CLI entrypoint for `flask garden-trial-lifecycle` |
| `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET` | secrets | Stripe payments + webhook verification |
| `TWILIO_ACCOUNT_SID/AUTH_TOKEN/PHONE_NUMBER` | secrets | SMS |
| `ZEPTOMAIL_TOKEN`, `ZEPTOMAIL_API_URL`, `MAIL_DEFAULT_SENDER` | secrets/env | Email via Zoho ZeptoMail (sole provider, pay-as-you-go transactional API; send-only token, no SMTP). Unset = email logged-only. |
| `CLOUDINARY_URL` | secret | Object storage for user-uploaded images (`cloudinary://key:secret@cloud`). Set = uploads go to the Cloudinary CDN (survive deploys); unset = ephemeral local disk. Images resolve via the `/media/<ref>` route (serves local file, else 301-redirects to the CDN). |
| `DOORDASH_DEVELOPER_ID/KEY_ID/SIGNING_SECRET` | secrets | DoorDash Drive JWT |
| `OPENWEATHER_API_KEY` | secret | Weather forecasts |
| `CORS_ORIGINS`, `RENDER_EXTERNAL_URL`, `SITE_URL`, `APP_URL` | env | CORS/Origin allowlist + public base URL for emails/Stripe return links. Resolution order is `SITE_URL` → `APP_URL` → `https://www.yardharvest.app`, and a bare apex is normalized to `www.` (so an `APP_URL` of `yardharvest.app` is overridden) |
| _(Garden Pro price / trial length)_ | — | Not env-configurable. Set in the admin console (`PricingConfig`) and read everywhere through `app.pricing.garden_pro_pricing()` — billing, emails, the pricing page and the structured data all quote that one value. |
| `GARDEN_DUES_FEE_PERCENT` | env (fallback) | Dues platform fee — now admin-editable via Admin → Pricing (`PricingConfig.garden_dues_fee_percent`); env used only if unset |
| `MARKETING_API_KEY` | secret | Token gate for `/crm/api/marketing/*` (used by `marketing_agent` CLI). Unset → API returns 503. |
| `ANTHROPIC_API_KEY` | secret | Powers the in-CRM "Draft with AI" marketing agent **and** the garden comment-wall moderator. Unset = AI drafting disabled + comments default to `allow`. `CLAUDE_MODEL` / `CRM_EMAIL_MODEL` / `CRM_REPLY_MODEL` / `CRM_QA_MODEL` (all default `claude-sonnet-5`), `CRM_TRIAGE_MODEL` (reply classification, default `claude-haiku-4-5`), and `MODERATION_MODEL` (default `claude-sonnet-5`) optionally override the model. |
| `FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET`, `FACEBOOK_WEBHOOK_VERIFY_TOKEN` | secrets | Meta CRM integration (publish-to-Page + Page inbox + webhook). App id/secret are set on both the web service and the facebook-scheduler cron. Unset = the CRM Facebook page shows setup instructions, disabled. `FACEBOOK_GRAPH_VERSION` optional (default `v21.0`). See [docs/integrations/facebook-setup.md](../integrations/facebook-setup.md). |
| `SENTRY_DSN` | secret | Error tracking (backend). Set on the web service and **both** crons. Unset = disabled. `SENTRY_ENVIRONMENT`/`SENTRY_TRACES_SAMPLE_RATE` optional. |

### Stripe go-live

To move from test to live: set `STRIPE_SECRET_KEY` / `STRIPE_PUBLISHABLE_KEY`
to `sk_live_…` / `pk_live_…`, create a **live** webhook → `/api/webhooks/stripe`
(events: `payment_intent.succeeded`, `payment_intent.payment_failed`,
`customer.subscription.updated`, `customer.subscription.deleted`,
`invoice.payment_failed`, `account.updated`, `transfer.created`,
`charge.refunded`) and set its signing secret as `STRIPE_WEBHOOK_SECRET`, then
complete the **Connect platform profile** in the live dashboard (required before
Express accounts can be created). The publishable key is served to the SPA at
runtime, so a key swap needs only a restart — **no frontend rebuild**. Verify
with `GET /api/health/stripe` (`mode: live, auth_ok: true, connect_ok: true`).
Stored Connect/customer ids self-heal across the test→live switch.

> **CSP for embedded Connect onboarding:** `set_security_headers` must allow
> `connect-js.stripe.com` (script-src + frame-src), `js.stripe.com` (frame-src)
> and `merchant-ui-api.stripe.com` (connect-src) — without these the in-app
> onboarding fails with *"Failed to load Connect.js"* and falls back to hosted.

## Database migrations (Alembic via Flask-Migrate)

Schema is owned by **Alembic** migrations under `migrations/`. The deploy runs
`python db_upgrade.py` (in `build.sh`), which is safe in every DB state:

| DB state | Action | Effect |
|---|---|---|
| Fresh (no tables) | `upgrade head` | Baseline migration builds the whole schema |
| Pre-Alembic prod (tables exist, no `alembic_version`) | `stamp head` | Records the baseline revision **without running DDL** — the live schema is never touched. The first post-Alembic deploy hits this path |
| Already on Alembic | `upgrade head` | Applies any new migrations |

Rules of the road:

- **Production** (`DATABASE_URL` set): `create_app()` does **not** call
  `db.create_all()` — Alembic is the single source of truth, so a forgotten
  migration can't be silently masked by auto-create.
- **Dev / tests** (no `DATABASE_URL`): `create_app()` still calls `create_all()`
  so local work and the test suite need no migration step. CI's Postgres leg
  also uses `create_all` (via `TEST_DATABASE_URL`), so migrations and tests both
  exercise Postgres.
- **Adding a column/table:** change the model, then
  `flask db migrate -m "describe change"`, **review the generated file**, commit
  it. The next deploy applies it via `db_upgrade.py`. Never hand-edit the schema
  in two places again.
- `seed_if_empty.py` still runs its idempotent `create_all` + defensive
  column-adds as a transitional safety net; these all no-op once Alembic owns the
  schema. Retiring that ad-hoc logic (leaving Alembic fully in charge) is a
  follow-up once a deploy or two has validated the new flow on staging.

## Staging environment (recommended, opt-in)

There is currently **no staging environment** — `main` deploys straight to
production. Now that migrations are real (and reversible-by-review), a staging
service is the right place to validate the first Alembic deploy and future
schema changes before they touch production data. To add one, append to
`render.yaml` (or create via the dashboard) — kept out of the committed blueprint
so it isn't auto-provisioned without an explicit decision:

```yaml
  # --- Staging (opt-in) -------------------------------------------------
  - type: web
    name: yardharvest-staging
    runtime: python
    plan: free
    branch: staging              # deploy from a 'staging' branch
    buildCommand: bash build.sh
    startCommand: python seed_if_empty.py && gunicorn wsgi:app
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: yardharvest-staging-db
          property: connectionString
      - key: SECRET_KEY
        generateValue: true
      # Point integrations at TEST credentials (Stripe test keys, a ZeptoMail
      # sandbox, a separate Sentry environment), never production secrets.
      - key: SENTRY_ENVIRONMENT
        value: staging
      # ...mirror the other sync:false secrets with test values...

databases:
  - name: yardharvest-staging-db
    plan: free
```

Workflow once staging exists: merge to `staging` → verify the deploy (especially
`db_upgrade.py` output and the migrated feature) → fast-forward `main`.

## Notes

- The crons and the web service are **separate Render services sharing the same
  Postgres**. Two crons are defined in `render.yaml`:
  - **`yardharvest-trial-lifecycle`** — daily at 08:00 UTC
    (`flask garden-trial-lifecycle`): trial expiry, cancelled-subscription
    expiry, and day 3/7/12/14/21 onboarding emails/SMS. As a daily fallback it
    also publishes any due scheduled Facebook posts.
  - **`yardharvest-facebook-scheduler`** — every 15 minutes
    (`flask publish-due-facebook-posts`): publishes CRM Facebook posts at their
    scheduled time with minute-level precision.
- The internal CRM previously ran as its own Render web service
  (`yardharvest-crm`) on its own Postgres (`yardharvest-crm-db`). It was
  consolidated into the main yardharvest web service at `/crm/*` (see
  [07-crm-module.md](07-crm-module.md)). After migrating data with
  `scripts/migrate_crm_data.py`, the standalone CRM service and database can
  be deleted from the Render dashboard. The `crm.yardharvest.app` subdomain
  is kept as an alias-domain on the consolidated service so existing URLs
  stay valid.
- `app/cli.py` registers **four** CLI commands: `garden-trial-lifecycle` and
  `publish-due-facebook-posts` (both wired as crons above), plus two that are
  **not** scheduled in `render.yaml`:
  - `analytics-cleanup` — retention-based purge of `AnalyticsEvent` rows older
    than `SiteEmailConfig.analytics_retention_days` (default 90). Would need its
    own scheduled service to run automatically.
  - `crm-set-password <username>` — sets/creates a CRM user's password from the
    `CRM_NEW_PASSWORD` env var (creates as `role=admin` if absent); run manually
    via the Render shell for CRM account recovery.
- `api-keys-check.yml` is manual (`workflow_dispatch`) and only validates that
  third-party credentials in repo secrets are usable; it is not part of CI/CD.
