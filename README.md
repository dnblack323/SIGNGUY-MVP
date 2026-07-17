# SignGuy AI

A multi-tenant shop-management platform for sign shops: quotes, orders, production
scheduling, inventory/materials, vendors, payroll, invoicing/payments, customer &
employee portals, and a Pricing Foundation with per-category pricing calculators.

## Stack

- **Backend**: FastAPI (Python 3.11), MongoDB (Motor async driver)
- **Frontend**: React 18 (Create React App + CRACO), Tailwind CSS, shadcn/ui, TanStack Query
- **Process management**: supervisor (dev/preview environment)

## Prerequisites

- Node.js **20.x** and Yarn **1.22.x** (Yarn Classic — this repo is NOT set up for Yarn Berry/npm)
- Python **3.11**
- A running MongoDB instance

## Local setup

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
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
| `EMERGENT_LLM_KEY` | Universal key used by AI and object-storage integrations when those optional features are enabled |
| `SENDGRID_API_KEY`, `SENDGRID_FROM_EMAIL`, `SENDGRID_FROM_NAME` | Transactional email |
| `STRIPE_API_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WRITES_ENABLED` | Payments |

All backend routes are served under the `/api` prefix.

### Frontend

```bash
cd frontend
yarn install --frozen-lockfile   # reproducible install from the committed yarn.lock
yarn start                       # dev server on :3000
```

Required frontend environment variable (`frontend/.env`, never committed):

| Variable | Purpose |
| --- | --- |
| `REACT_APP_BACKEND_URL` | Base URL the frontend uses to reach the backend's `/api/*` routes |

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
