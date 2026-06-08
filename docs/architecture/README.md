# YardHarvest — Architecture Diagrams

This folder contains the architecture documentation for the **YardHarvest**
platform as a set of Mermaid diagrams. GitHub renders the fenced `mermaid`
blocks inline, so each `.md` file is viewable directly in the repo.

## Platform overview

YardHarvest is a hyperlocal gardening platform with two product surfaces gated by
an admin `marketplace_enabled` flag (`SiteEmailConfig`). The **marketplace** lets
neighbors buy and sell home-grown produce (listings, cart, orders, CSA
subscription boxes, reviews, smart pricing) with Stripe-powered checkout and
seller payouts. The **community gardens** surface manages physical gardens (plots
and assignments, waitlists, events, volunteer shifts, shared-resource lending via
QR, dues and expenses, announcements, photos) and is monetized through a
**Garden Pro** subscription (free trial → Stripe Subscription) plus optional
routing of member **dues** straight to a garden manager's Stripe Connect account.
The backend is a Flask REST API consumed by a React (Vite) SPA over session
cookies and by a mobile app over JWT; it is deployed on Render as a web service,
a daily cron, and managed Postgres.

The same Flask app also serves an **internal CRM** at `/crm/*` — a server-rendered
Jinja module (`app/crm/`) used by the YardHarvest team to track sales pipelines
to community gardens and city/parks departments. It has its own session-based
auth, its own user table (`crm_user`), and tables prefixed `crm_*` in the same
Postgres database. A token-authenticated marketing API at
`/crm/api/marketing/*` is consumed by the `marketing_agent/` CLI (Claude-powered
campaign drafter). This module was previously a separate Render service +
database (`yardharvest-crm`) and was consolidated to eliminate the second
deploy footprint.

## Tech stack

- **Backend:** Python 3.11, Flask, Flask-SQLAlchemy, Flask-Login, Flask-Mail,
  Flask-WTF (CSRF), Flask-CORS, Flask-Limiter; gunicorn (prod) on `wsgi:app`.
- **Frontend:** React + Vite SPA, React Router, Axios (`baseURL: /api`,
  `withCredentials`), Stripe.js; `AuthContext` + `SiteConfigContext`.
- **Database:** PostgreSQL (Render) in prod, SQLite in dev.
- **Auth:** Flask-Login session cookies (web) + JWT access/refresh (mobile).
- **Integrations:** Stripe (Connect, destination charges, Subscriptions,
  webhooks), Twilio (SMS), Zoho ZeptoMail (transactional email API), DoorDash Drive
  (delivery), OpenWeather (forecasts), geopy/Nominatim (geocoding).
- **Hosting / CI:** Render (web + cron + Postgres via `render.yaml`, `build.sh`);
  a manual GitHub Actions workflow validates third-party API keys.

## Diagram index

| File | Description |
|---|---|
| [01-system-context.md](01-system-context.md) | C4-style context: actors ↔ YardHarvest (SPA, API, Postgres) ↔ external services. |
| [02-backend-components.md](02-backend-components.md) | Flask blueprint/component map grouped by domain, plus the service modules each calls, with a url_prefix reference table. |
| [03-data-model.md](03-data-model.md) | ER diagrams of the main entities (marketplace, community gardens, and platform/billing), split for readability. |
| [04-auth-flow.md](04-auth-flow.md) | Sequence diagrams: web session login, mobile JWT login/refresh/revoke, and marketplace-hidden role-gated registration. |
| [05-payments.md](05-payments.md) | Sequence diagrams for the three money flows (marketplace checkout + payout, Garden Pro trial→subscription, dues destination charge) and the Stripe webhook dispatch. |
| [06-deployment.md](06-deployment.md) | Render deployment topology, build pipeline, runtime topology, env/secrets, and the API-key-check GitHub Actions workflow. |
| [07-crm-module.md](07-crm-module.md) | Internal CRM module at `/crm/*` — schema (crm_* tables), session auth, marketing API, marketing-agent CLI integration. |

## Source of truth

These diagrams were derived from the code under `app/` (blueprints in
`app/api/*.py`, models in `app/models.py`, integrations in `app/*_service.py`,
`app/cli.py`, `config.py`), the deploy config (`render.yaml`, `build.sh`), the
`.github/workflows/` workflow, and the frontend (`frontend/src/App.jsx`,
`frontend/src/api.js`). If the code changes, update the corresponding diagram.
