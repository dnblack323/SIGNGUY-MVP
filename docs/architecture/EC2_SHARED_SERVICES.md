# EC2 — Shared Platform Services (Architecture)

**Status:** Complete. See `/app/evidence/EC2_evidence.md`.

Shared foundations every subsequent EC (EC3+) depends on. All services are
tenant-scoped in code AND enforced by MongoDB indexes.

## Modules delivered

| Module | Purpose | Files |
|---|---|---|
| Tenant Settings | Namespaced key/value store; per-tenant configuration | `models/settings.py`, `services/settings.py`, `routers/settings.py` |
| Activity Feed | Human-visible event feed that extends (not replaces) audit | `models/activity.py`, `services/activity.py`, `routers/activity.py` |
| In-App Notifications | Per-user staff notifications (portal notifications are separate) | `models/notification.py`, `services/notifications.py`, `routers/notifications.py` |
| Email Activity | SendGrid + internal outbound event log | `models/email_activity.py`, extension in `services/email.py`, `services/sendgrid_webhook.py` |
| Webhook Framework | Provider-agnostic dedupe + verify + audit | `models/webhook_event.py`, `services/webhooks.py`, `routers/webhooks.py` |
| Upload Validation | MIME + magic-byte + size + filename sanitation | `services/upload_validation.py` |
| Polymorphic File Links | Cross-entity file/document references without duplication | `models/file_link.py`, `models/document_link.py`, `models/document_share.py` |
| Feature Entitlements | Tenant read + `require_entitlement(feature)` guard | `models/feature_entitlement.py`, `services/entitlements.py`, `routers/entitlements.py`, extension in `deps.py` |
| Integration Status | Read-only surface of enabled/configured integrations | `services/integration_status.py`, `routers/integration_status.py` |

## Boundary rules (LOCKED)

- MVP `Attachment` remains authoritative for the existing quote/order/invoice
  attachment flow. `FileLink` handles new cross-entity references (portal,
  webstore, wrap lab) starting in EC4+.
- MVP `audit.record_audit` remains authoritative. `activity.record_activity`
  is the *feed* surface — it links to `audit_event_id` when both are needed.
  `record_activity_with_audit` is the single-call convenience for write routes.
- MVP `EmailLog` remains the outbound record. `email_activity` is the
  observability stream (delivery, open, click, bounce). Internal outbound
  writes an `internal` row so the feed shows sends before webhook events.

## Tenant isolation

Every collection has a `tenant_id` field. Reads and writes always filter by
`tenant_id`. `require_entitlement` is called AFTER `get_current_user` so an
un-entitled tenant is rejected before permission introspection.

Notifications additionally scope by `recipient_user_id` — a user cannot see
or mutate another staff user's notifications even inside the same tenant.

## Value type contract

`settings.value` is typed JSON. `settings.value_type` is an informational
hint (`string`, `int`, `float`, `bool`, `json`). Callers validate shape at
the service layer per namespace.

Secrets are **prohibited** in `settings`. All secrets live only in the
environment; `integration_status` reports availability without ever
exposing values.
