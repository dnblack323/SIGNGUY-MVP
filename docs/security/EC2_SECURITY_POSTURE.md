# EC2 — Security posture

## Fail-closed defaults

| Surface | Default | Notes |
|---|---|---|
| SendGrid webhook route | **404** when disabled or unsecret | `SENDGRID_WEBHOOK_ENABLED=false` hides the surface entirely. |
| Feature entitlement guard | **402** when not entitled | `require_entitlement(feature)` returns 402 before permission checks run. |
| Settings mutation | **403** when caller lacks `settings:write` | Read guarded by `settings:read`. |
| Integration status | **403** when caller lacks `integration:read` | Never returns secret values, only presence + missing env var names. |
| Notifications | **403** for cross-user | Every op is scoped by `(tenant_id, recipient_user_id)`. |
| Upload validation | **400/413** on invalid content | MIME + magic-byte + size + filename sanitation before any storage IO. |

## No secret leakage

- `settings` collection is **prohibited** from storing secrets. All secrets
  live only in environment variables.
- `integration_status` reports only `enabled` / `configured` / `missing_secrets`
  (env-var *names*, never values). See `test_integration_status.py`.

## Tenant isolation guarantees

Every EC2 collection includes `tenant_id`. Cross-tenant queries are
impossible without a code bug. The dedicated sweep test
`tests/test_ec2_cross_tenant.py` verifies isolation for every new collection
including `file_links`, `document_links`, `document_shares`, `settings`,
`activity_events`, `notifications`, `email_activity`, and `feature_entitlements`.

## Webhook payload minimization

Raw provider payloads are not stored verbatim. `webhook_events.metadata`
and `email_activity.payload_snapshot` keep a curated subset. Signature
secrets never appear in Mongo.
