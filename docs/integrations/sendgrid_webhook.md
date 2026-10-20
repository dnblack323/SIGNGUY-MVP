# SendGrid Event Webhook — Integration

## Runtime posture

- **Off by default.** The route `/api/webhooks/sendgrid` returns **404** when
  `SENDGRID_WEBHOOK_ENABLED=false` OR `SENDGRID_WEBHOOK_PUBLIC_KEY` is unset.
  This hides the surface entirely and matches the EC1 fail-closed guard.
- **Signature-first.** Verify SendGrid's ECDSA signature over the raw body
  *before* touching the event log. Invalid signatures return 401 without persistence.
- **Replay-safe.** Duplicate `(provider, provider_event_id)` returns 200 as a
  no-op. Enforced in two places: (1) explicit check in
  `services/webhooks.record_received`; (2) MongoDB unique index.
- **Tenant-attributed.** Each event resolves `tenant_id` only via the internal
  `email_logs.sendgrid_message_id` mapping (the prefix of the event's
  `sg_message_id`) — never from the recipient address or any other payload
  field. Unresolved events are logged with `error_code=tenant_unresolved`
  and never leak to another tenant. Every system email is sent through
  `services/email.send_logged_email`, which writes that EmailLog.

## Signature spec

SendGrid's Signed Event Webhook uses ECDSA (P-256):

- `X-Twilio-Email-Event-Webhook-Signature` — base64 ECDSA signature of `timestamp + raw_body`
- `X-Twilio-Email-Event-Webhook-Timestamp` — unix seconds

Verification uses the verifier bundled in the official `sendgrid` Python
library (`sendgrid.helpers.eventwebhook.EventWebhook`) with the account's
verification public key. Shared-secret HMAC is not a SendGrid mode and is not used.

## Payload persistence

- We do **not** store the full SendGrid payload verbatim.
- `webhook_events.metadata` and `email_activity.payload_snapshot` keep only
  safe scalar fields useful for support triage.
- `email_activity` rows are unique on `(provider, provider_event_id)`.

## Environment configuration

```
SENDGRID_WEBHOOK_ENABLED=false    # true only when the public key is set
SENDGRID_WEBHOOK_PUBLIC_KEY=      # Event Webhook "Verification Key" (base64, no PEM header)
PUBLIC_APP_URL=                   # frontend origin used for links in emails
```

EC1 startup guards refuse to start in production when
`SENDGRID_WEBHOOK_ENABLED=true` without a public key, or when
`SENDGRID_API_KEY` is set without `PUBLIC_APP_URL`.

## Enablement checklist (production)

1. In SendGrid → Settings → Mail Settings → Event Webhooks, add a webhook for
   MVP and turn on **Signed Event Webhook**; copy its verification key.
2. Set `SENDGRID_WEBHOOK_ENABLED=true` and `SENDGRID_WEBHOOK_PUBLIC_KEY` in
   the environment (use a restricted Mail Send API key for `SENDGRID_API_KEY`).
3. Restart the backend so the EC1 guard picks up the new configuration.
4. Point SendGrid's webhook URL to `POST {backend}/api/webhooks/sendgrid`.
5. Send a test event from SendGrid and verify a row lands in
   `email_activity` and the corresponding `webhook_events` row has
   `processing_status="processed"`.
