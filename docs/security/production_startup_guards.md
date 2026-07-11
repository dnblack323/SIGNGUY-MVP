# Production Startup Guards (LOCKED — EC1)

## Contract

The application refuses to start in production when:

1. `AUTH_DEV_BYPASS=true`.
2. `JWT_SECRET` is missing or matches a known placeholder (see `JWT_PLACEHOLDER_SECRETS` in `security_guards.py`).
3. `SENDGRID_WEBHOOK_ENABLED=true` and `SENDGRID_WEBHOOK_SECRET` is missing.
4. `STRIPE_WRITES_ENABLED=true` and `STRIPE_API_KEY` is missing.
5. `STRIPE_WEBHOOK_ENABLED=true` and `STRIPE_WEBHOOK_SECRET` is missing.
6. `AI_ENABLED=true` and `EMERGENT_LLM_KEY` is missing.
7. `SMS_ENABLED=true` and both `SMS_PROVIDER_KEY` + `SMS_PROVIDER_SECRET` are missing.

Development and test environments (`ENV=development` / `ENV=test`) pass through and are permitted to run with the documented test settings. The dev bypass remains visibly identified via `GET /api/auth/dev-config` and the amber banner in `AppShell`.

## Dev route protection (defense in depth)

The following endpoints refuse to run outside `ENV=development` (return 404):

- `POST /api/auth/dev-login`
- `GET /api/auth/_dev/last-reset-token`
- `GET /api/auth/dev-config`

## Implementation

- `backend/app/core/config.py` reads all environment flags and secrets.
- `backend/app/core/security_guards.py::enforce_startup_guards(settings)` computes violations and raises `StartupGuardError` when any exist.
- `backend/server.py` calls `enforce_startup_guards(_settings)` at import time.
- `backend/app/routers/auth.py` gates each dev route on `settings.env == "development"`.

## Testing

`backend/tests/test_startup_guards.py` verifies all seven conditions plus the disabled-integration passthrough.

## Deployment checklist

Before setting `ENV=production`:

- [ ] Rotate `JWT_SECRET` to a strong non-placeholder value.
- [ ] Set `AUTH_DEV_BYPASS=false` (or unset).
- [ ] Set `SENDGRID_WEBHOOK_SECRET` if enabling the delivery-event webhook.
- [ ] Set `STRIPE_API_KEY` (live) and `STRIPE_WEBHOOK_SECRET` when enabling Stripe writes/webhook.
- [ ] Set `EMERGENT_LLM_KEY` when enabling AI generation.
- [ ] Set `SMS_PROVIDER_KEY` + `SMS_PROVIDER_SECRET` when enabling SMS.
- [ ] Confirm `/api/auth/dev-*` returns 404 in the deployed environment.
