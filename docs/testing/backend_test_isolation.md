# Backend test isolation

Automated backend tests **never** use the development database, the developer's `.env`, or
live integrations. `python -m pytest tests/` is safe to run as-is.

## How a run is isolated

`backend/tests/_test_env.py` is the single bootstrap. `tests/conftest.py` calls it from
`pytest_configure`, before any `app` module is imported (config/db read settings at import time).

1. Starts a **private `mongod`** on a random loopback port with a temp data directory
   (found via `SIGNGUY_TEST_MONGOD`, `PATH`, or the standard install path). It is not the
   developer's MongoDB service, so no test can reach `signguy_local`.
2. Creates one database per xdist worker: `signguy_test_<run_id>_gw0`, `..._gw1` (`..._main` for `-n 0`),
   each holding an ownership marker (run id + hash of a random owner token).
3. Exports a complete test environment: `ENV=test`, random `JWT_SECRET`, run-scoped
   `OBJECT_STORAGE_PATH`, and every live integration key blanked/disabled
   (SendGrid, Stripe, OpenAI/AI, SMS, Google). `backend/.env` is not read.
4. On finish (pass, fail or Ctrl+C) each worker drops its own database, then the controller
   stops the private mongod and deletes the run directory.

If no test MongoDB can be provided the run **refuses to start** (exit 4) before any write; it never
falls back to the development database.

## What is rejected (fail closed)

* Preset `DB_NAME` or `MONGO_URL` (e.g. `DB_NAME=signguy_local pytest` is refused).
* `SIGNGUY_TEST_MONGO_URL` that is non-loopback, `mongodb+srv`, on port 27017 outside CI, or whose
  server already holds any database this run did not create.
* A database name that does not embed this run's id, or any protected name (`signguy_local`, `signguy_mvp`, ...).
* Importing `app` under pytest (or with a run id) without a validated target (`app/core/config.py`).
* Cleanup only drops a database whose **name and ownership marker** both match the current run;
  a name containing "test" is never enough.

## HTTP tests and scripts

HTTP tests start their own disposable server (`tests/live_server.py`) on a random loopback port, bound
to the run's database. `SIGNGUY_API_BASE_URL` (the old way to point tests at a running app) is refused.
Standalone scripts (`tests/_seed_ui_ctx.py`, `tests/e2e_portal_pay_curl.py`, `scripts/smoke_backend.py`,
`scripts/poc_core.py`) exit with code 2 unless run inside an isolated environment:

```bash
cd backend
python -m tests._test_env run -- python scripts/smoke_backend.py
```

## Abandoned runs

A force-killed run leaves only a private mongod on a random port and a folder in
`%TEMP%/signguy-test-runs/<run_id>/`; the dev database is unaffected.

```bash
python -m tests._test_env list    # shows runs and whether their runner process is gone
python -m tests._test_env reap     # stops/deletes abandoned runs recorded in a manifest (nothing else)
```

## CI

CI sets only `SIGNGUY_TEST_MONGO_URL` (the disposable service container). The bootstrap verifies the
server is empty before creating its per-worker databases and drops them afterwards.
