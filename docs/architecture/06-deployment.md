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
        Web["Web Service: yardharvest<br/>build: bash build.sh<br/>start: seed_if_empty.py && gunicorn wsgi:app"]
        Cron["Cron: yardharvest-trial-lifecycle<br/>schedule '0 8 * * *'<br/>start: flask garden-trial-lifecycle"]
        PG[("Postgres: yardharvest-db<br/>(free plan)")]
    end

    Web --> PG
    Cron --> PG

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
| `CORS_ORIGINS`, `RENDER_EXTERNAL_URL`, `APP_URL` | env | CORS/Origin allowlist, Stripe return URLs |
| `GARDEN_TRIAL_DAYS`, `GARDEN_PRO_PRICE_MONTHLY/YEARLY` | env | Garden Pro defaults (also admin-editable in `PricingConfig`) |
| `GARDEN_DUES_FEE_PERCENT` | env (fallback) | Dues platform fee — now admin-editable via Admin → Pricing (`PricingConfig.garden_dues_fee_percent`); env used only if unset |
| `MARKETING_API_KEY` | secret | Token gate for `/crm/api/marketing/*` (used by `marketing_agent` CLI). Unset → API returns 503. |
| `SENTRY_DSN` | secret | Error tracking (backend). Set on both web + cron. Unset = disabled. `SENTRY_ENVIRONMENT`/`SENTRY_TRACES_SAMPLE_RATE` optional. |

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

- The cron job and web service are **separate Render services sharing the same
  Postgres**. The cron runs daily at 08:00 UTC and handles trial expiry,
  cancelled-subscription expiry, and day 3/7/12/14/21 onboarding emails/SMS.
- The internal CRM previously ran as its own Render web service
  (`yardharvest-crm`) on its own Postgres (`yardharvest-crm-db`). It was
  consolidated into the main yardharvest web service at `/crm/*` (see
  [07-crm-module.md](07-crm-module.md)). After migrating data with
  `scripts/migrate_crm_data.py`, the standalone CRM service and database can
  be deleted from the Render dashboard. The `crm.yardharvest.app` subdomain
  is kept as an alias-domain on the consolidated service so existing URLs
  stay valid.
- A second CLI command, `analytics-cleanup`, exists for retention-based purging
  of `AnalyticsEvent` rows but is **not wired into render.yaml** as a cron (would
  need its own scheduled service).
- `api-keys-check.yml` is manual (`workflow_dispatch`) and only validates that
  third-party credentials in repo secrets are usable; it is not part of CI/CD.
