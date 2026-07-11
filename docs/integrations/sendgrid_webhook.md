# SendGrid Event Webhook — Integration

## Runtime posture

- **Off by default.** The route `/api/webhooks/sendgrid` returns **404** when
  `SENDGRID_WEBHOOK_ENABLED=false` OR `SENDGRID_WEBHOOK_SECRET` is unset.
  This hides the surface entirely and matches the EC1 fail-closed guard.
- **Signature-first.** Verify HMAC-SHA256 signature *before* touching the
  event log. Invalid signatures return 401 without persistence.
- **Replay-safe.** Duplicate `(provider, provider_event_id)` returns 200 as a
  no-op. Enforced in two places: (1) explicit check in
  `services/webhooks.record_received`; (2) MongoDB unique index.
- **Tenant-attributed.** Each event resolves `tenant_id` via the internal
  `email_logs.sendgrid_message_id` mapping — never from a client-supplied
  payload field. Unresolved events are logged with `error_code=tenant_unresolved`
  and never leak to another tenant.

## Signature spec

- `X-Twilio-Email-Event-Webhook-Signature` — base64(HMAC-SHA256(secret, timestamp || raw_body))
- `X-Twilio-Email-Event-Webhook-Timestamp` — unix seconds

We use HMAC-SHA256 shared-secret mode only. ECDSA verification mode is
intentionally not implemented.

## Payload persistence

- We do **not** store the full SendGrid payload verbatim.
- `webhook_events.metadata` and `email_activity.payload_snapshot` keep only
  safe scalar fields useful for support triage.
- `email_activity` rows are unique on `(provider, provider_event_id)`.

## Environment configuration

```
SENDGRID_WEBHOOK_ENABLED=false    # true only when the real secret is set
SENDGRID_WEBHOOK_SECRET=          # HMAC shared secret from SendGrid Mail Settings
```

EC1 startup guards refuse to start in production when
`SENDGRID_WEBHOOK_ENABLED=true` without a valid secret.

## Enablement checklist (production)

1. Generate the SendGrid Event Webhook signed secret in SendGrid's Mail
   Settings → Event Webhook screen.
2. Set both `SENDGRID_WEBHOOK_ENABLED=true` and `SENDGRID_WEBHOOK_SECRET` in
   the production environment.
3. Restart the backend so the EC1 guard picks up the new configuration.
4. Point SendGrid's webhook URL to `POST {backend}/api/webhooks/sendgrid`.
5. Send a test event from SendGrid and verify a row lands in
   `email_activity` and the corresponding `webhook_events` row has
   `processing_status="processed"`.
