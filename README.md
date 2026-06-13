# YardHarvest

The management platform for community gardens — and the nonprofits and city
programs that run them. Organizers handle plots, dues, volunteers, events, and
funder-ready impact reporting from one place. A produce **marketplace** (Omaha
heritage) ships behind a feature flag and is off by default.

- **Backend:** Flask 3 + SQLAlchemy 2, served by gunicorn. REST API under
  `/api/*`; an internal CRM (sales pipeline + AI marketing drafts) under `/crm/*`.
- **Frontend:** React 19 + Vite SPA (`frontend/`), served from `frontend/dist`
  in production with a server-side SPA fallback.
- **Database:** PostgreSQL in production, SQLite for local dev.
- **Integrations:** Stripe (payments, Connect payouts, subscriptions),
  Zoho ZeptoMail (email), Twilio (SMS), Cloudinary (image CDN), Anthropic
  (CRM AI drafting), Sentry (error tracking). Each degrades gracefully when
  unconfigured.

## Local development

### Backend (Python 3.11)

```bash
python -m venv .venv
.venv/Scripts/activate            # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
python run.py                     # http://127.0.0.1:5000
```

With no `DATABASE_URL` set, the app uses a local SQLite DB and auto-creates the
schema (`db.create_all()`), so no migration step is needed for local work.

### Frontend (Node 20)

```bash
cd frontend
npm install
npm run dev                       # http://localhost:5173 (proxies /api to :5000)
```

For a production-style run, `npm run build` writes `frontend/dist`, which Flask
then serves directly.

## Testing

```bash
# Backend (pytest) — SQLite by default; set TEST_DATABASE_URL for Postgres
pytest -q

# Frontend (Vitest + Testing Library)
cd frontend && npm run test
```

CI (`.github/workflows/tests.yml`) runs the backend suite on **both SQLite and
PostgreSQL** and the frontend unit tests + build on every push and PR.

## Database migrations

Schema is owned by **Alembic** (via Flask-Migrate) under `migrations/`.

```bash
# After changing a model:
flask db migrate -m "describe the change"   # FLASK_APP=wsgi:app
# review the generated file, then commit it
```

On deploy, `db_upgrade.py` applies migrations safely: fresh DBs are built from
the baseline (`upgrade`), an existing pre-Alembic database is adopted without
DDL (`stamp`), and migrated databases are upgraded. See
[docs/architecture/06-deployment.md](docs/architecture/06-deployment.md).

## Deployment

Deployed on **Render** via `render.yaml` (web service + daily cron + managed
Postgres). `build.sh` installs deps, builds the SPA, runs `db_upgrade.py`, and
seeds. Secrets are set in the Render dashboard (`sync: false`), never committed —
see `.env.example` for the full list. Health probes live at `/api/health/*`
(`config`, `stripe`, `email`, `ai`).

## Architecture docs

[`docs/architecture/`](docs/architecture/) covers the system context, backend
components, data model, auth flow, payments, deployment, and the CRM module.
