# Browser test target safety (fail closed)

Real-browser checks must never reach the development backend (port 8001) or the
developer database (`signguy_local`). The Webstores browser harness is the one
isolation path; these checks extend it rather than replace it.

## Layers

1. **Backend environment** — `backend/tests/browser_target_guard.py::assert_backend_test_env`
   (called by `tests/webstores_browser_harness.py` on import). Refuses unless:
   `WEBSTORES_BROWSER_HARNESS=1`, `ENV` is not production, `AUTH_DEV_BYPASS=false`,
   `DB_NAME` starts with `webstores_browser_harness_` and is not `signguy_local`
   or the `DB_NAME` in `backend/.env`, `JWT_SECRET` is random, and no
   `SENDGRID_API_KEY` / Stripe secret is set.
2. **Frontend dev server** — `frontend/craco.config.js`. With
   `SIGNGUY_BROWSER_TEST=1` it refuses to start unless `SIGNGUY_DEV_API_TARGET`
   is set and is not the development backend.
3. **Preflight before any browser step** —
   `python -m tests.browser_target_guard --fixture <harness fixture json> --frontend http://127.0.0.1:3102`
   (run from `backend/`). Exits non-zero unless the harness backend accepts the
   harness's random credentials, the same login succeeds **through the frontend
   proxy**, and the dev auto-login is refused through the proxy. Credentials
   exist only in the isolated database, so a proxy pointed anywhere else fails.

## Run order

```
# backend (from backend/), random secrets, no provider keys
WEBSTORES_BROWSER_HARNESS=1 ENV=test AUTH_DEV_BYPASS=false \
DB_NAME=webstores_browser_harness_<run> JWT_SECRET=<random> \
WEBSTORES_BROWSER_BACKEND_PORT=8102 WEBSTORES_BROWSER_FIXTURE_PATH=<path> \
PUBLIC_APP_URL=http://localhost:3102 CORS_ORIGINS=http://localhost:3102 \
python tests/webstores_browser_harness.py

# frontend (from frontend/)
PORT=3102 SIGNGUY_BROWSER_TEST=1 SIGNGUY_DEV_API_TARGET=http://127.0.0.1:8102 npx craco start

# then, before opening the browser
python -m tests.browser_target_guard --fixture <path> --frontend http://127.0.0.1:3102
```

If any step refuses, stop. Do not work around it.
