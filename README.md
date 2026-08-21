# SignGuy AI

A multi-tenant shop-management platform for sign shops: quotes, orders, production
scheduling, inventory/materials, vendors, payroll, invoicing/payments, customer &
employee portals, and a Pricing Foundation with per-category pricing calculators.

## Stack

- **Backend**: FastAPI (Python 3.11), MongoDB (Motor async driver)
- **Frontend**: React 18 (Create React App + CRACO), Tailwind CSS, shadcn/ui, TanStack Query
- **Container runtime**: repository-owned Docker Compose with nginx routing

## Prerequisites

- Node.js **20.x** and Yarn **1.22.x** (Yarn Classic — this repo is NOT set up for Yarn Berry/npm)
- Python **3.11**
- A running MongoDB instance, or Docker Compose

## Local setup

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/install_pricing_engine.py
# create backend/.env with the variables below, then:
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

Required backend environment variables (`backend/.env`, never committed):

| Variable | Purpose |
| --- | --- |
| `MONGO_URL` | MongoDB connection string |
| `DB_NAME` | MongoDB database name |
| `CORS_ORIGINS` | Comma-separated allowed origins |
| `JWT_SECRET` | Secret for signing access tokens |
| `ENV` | `development` or `production` — gates all `/api/*/dev-*` routes and dev-only response fields |
| `AUTH_DEV_BYPASS` | `true` only in development — enables `/api/auth/dev-login` |
| `AI_PROVIDER_API_KEY` | Optional AI provider key when `AI_ENABLED=true` |
| `GOOGLE_AUTH_ENABLED` | Enables direct app-owned Google OAuth |
| `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` | Backend-only Google OAuth credentials |
| `SENDGRID_API_KEY`, `SENDGRID_FROM_EMAIL`, `SENDGRID_FROM_NAME` | Transactional email |
| `STRIPE_API_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WRITES_ENABLED` | Payments |
| `PRICING_ENGINE_READ_TOKEN` | Optional local fallback for installing the private pinned `signguy-pricing-engine` wheel; authorized developers can alternatively use an authenticated `gh` session |

All backend routes are served under the `/api` prefix.

### Frontend

```bash
cd frontend
yarn install --frozen-lockfile   # reproducible install from the committed yarn.lock
yarn start                       # dev server on :3000
```

Optional frontend environment variable (`frontend/.env`, never committed):

| Variable | Purpose |
| --- | --- |
| `REACT_APP_API_BASE_URL` | API base path. Defaults to same-origin `/api`. |
| `SIGNGUY_DEV_API_TARGET` | Optional CRA dev-server proxy target for same-origin `/api`; defaults to `http://localhost:8001`. |

### Docker Compose

The repository includes an independent local stack:

```bash
docker compose up --build
```

The web app is served at `http://localhost:3000`. nginx serves the React build
and proxies `/api/*` to the backend service. MongoDB data and object storage are
kept in Docker volumes.

### Production build

```bash
cd frontend
yarn install --frozen-lockfile
yarn build
```

This must succeed from a clean `node_modules` (no cached state) — it is verified in CI
(`.github/workflows/ci.yml`) on every push/PR.

## Running tests

### Backend (targeted or full suite)

```bash
cd backend
python -m pytest tests/ -q
```

### Frontend

```bash
cd frontend
CI=true yarn test --watchAll=false
```

## Multi-tenant login

Email is unique **per shop** (`(tenant_id, email)`), not globally — the same person can
exist as a user in more than one shop. Login, password-reset, and Google sign-in all
require identifying the shop explicitly:

- `POST /api/auth/login` — body: `{ "tenant_slug", "email", "password" }`
- `POST /api/auth/request-password-reset` — body: `{ "tenant_slug", "email" }`
- Google sign-in uses app-owned direct OAuth. The backend creates a short-lived,
  one-time state value, validates replay/expiration on callback, exchanges the
  authorization code directly with Google, and issues the normal app JWT.
- Google sign-in links to an existing account only when the email is unambiguous
  across shops; if it exists in more than one shop, the user is asked to sign in with
  their shop slug + email + password instead.

## Repository layout

```
backend/
  app/
    models/      # Pydantic document models
    services/    # business logic, one module per domain
    routers/     # FastAPI routers (thin — delegate to services)
    core/        # db, security, permissions, config, time utils
  tests/         # pytest suite (async, httpx ASGITransport)
frontend/
  src/
    pages/       # route-level pages
    components/  # reusable UI (shadcn/ui in components/ui/)
    auth/        # AuthContext, Google OAuth callback
```
