# EC2 — Shared Platform Services — Evidence

**Status:** COMPLETE.
**Authority:** `/app/SIGNGUY_AI_FINAL_CONSOLIDATED_MASTER_BUILD_PLAN.md`,
`/app/preflight/EC2_SHARED_PLATFORM_SERVICES_PREFLIGHT.md`,
`/app/evidence/EC1_evidence.md`.
**Owner decisions incorporated:**
- SendGrid webhook: Option A. Route stays disabled until a real production
  secret is configured. Signature-verification / replay-protection /
  failure-path / tenant-attribution behavior tested with a test-only secret.
  **No development-placeholder secret is written to `.env`.**
- Feature Entitlements: Option A. Tenant-readable endpoint and reusable
  `require_entitlement(feature_key)` dep landed. Platform-scoped write API
  deferred to the commercial checkpoint. Tests seed entitlement records
  directly via a helper.

## 1. Modules delivered

| Area | Backend | Frontend |
|---|---|---|
| Tenant Settings | `models/settings.py`, `services/settings.py`, `routers/settings.py` (`/api/settings`, `/api/settings/{ns}`, `/api/settings/{ns}/{key}`) | `pages/CompanySettingsPage.jsx` |
| Activity Feed | `models/activity.py`, `services/activity.py`, `routers/activity.py` (`/api/activity`) | Rendered on Data & Security page |
| In-App Notifications | `models/notification.py`, `services/notifications.py`, `routers/notifications.py` (`/api/notifications*`) | `components/notifications/NotificationBell.jsx`, `NotificationPanel.jsx` |
| Email Activity | `models/email_activity.py`, extended `services/email.py` (writes `internal` rows), `services/sendgrid_webhook.py`, `routers/webhooks.py` | — |
| Webhook Framework | `models/webhook_event.py`, `services/webhooks.py`, `routers/webhooks.py` (SendGrid only in EC2) | — |
| Upload Validation | `services/upload_validation.py` | — |
| Polymorphic Links | `models/file_link.py`, `models/document_link.py`, `models/document_share.py` | — |
| Feature Entitlements | `models/feature_entitlement.py`, `services/entitlements.py`, `routers/entitlements.py`, `deps.require_entitlement` | `pages/FeatureAccessPage.jsx`, `lib/entitlements.js` |
| Integration Status | `services/integration_status.py`, `routers/integration_status.py` (`/api/integrations/status`) | `pages/IntegrationsPage.jsx` |
| Data & Security surface | — | `pages/DataSecurityPage.jsx` |

## 2. Wiring changes

- `server.py` — 6 new routers registered.
- `app/core/db.py` — 22 new indexes across 9 collections (see below).
- `app/deps.py` — added `require_entitlement(feature_key)`.
- `app/services/email.py` — added `record_processed_activity` and wired it
  into the send flow.
- `app/routers/emails.py` — writes `email_activity` on outbound send.
- `frontend/src/App.js` — 4 new routes (company / integrations / features / data-security).
- `frontend/src/components/app-shell/AppShell.jsx` — mounted `NotificationBell` in topbar.
- `frontend/src/lib/navigation.js` — un-disabled EC2 Control Center entries
  (Company Settings, Integrations, Feature Access, Data & Security) and
  re-pointed Company Settings from `/settings` to `/settings/company`.

## 3. Collections + Indexes (idempotent in `ensure_indexes`)

| Collection | Indexes |
|---|---|
| `settings` | unique `(tenant_id, namespace, key)`; `(tenant_id, namespace)` |
| `activity_events` | unique `id`; `(tenant_id, module, created_at)`; `(tenant_id, entity_type, entity_id)`; `(tenant_id, severity, created_at)` |
| `notifications` | unique `id`; `(tenant_id, recipient_user_id, status, created_at)`; `(tenant_id, recipient_user_id, read_at)` |
| `email_activity` | unique `id`; unique `(provider, provider_event_id)`; `(tenant_id, email_log_id, event_timestamp)`; `(tenant_id, related_entity_type, related_entity_id)` |
| `webhook_events` | unique `id`; unique `(provider, provider_event_id)`; `(provider, processing_status, received_at)` |
| `file_links` | unique `id`; `(tenant_id, parent_type, parent_id)`; `(tenant_id, file_id)` |
| `document_links` | unique `id`; `(tenant_id, document_id, entity_type, entity_id)` |
| `document_shares` | unique `id`; `(tenant_id, document_id)`; `(tenant_id, recipient_key, revoked)` |
| `feature_entitlements` | unique `id`; unique `(tenant_id, feature_key)` |

## 4. Owner-decision compliance

**SendGrid webhook.**
- Route is fail-closed: returns **404** when disabled or secret missing.
- `test_sendgrid_route_disabled_returns_404` covers the disabled path.
- `test_sendgrid_route_rejects_invalid_signature` covers 401 on bad signature.
- `test_sendgrid_route_accepts_valid_signature` covers full HMAC verification
  against a **test-only** secret; **no placeholder secret exists in `.env`**.
- Replay protection verified in `test_process_events_dedupes_by_event_id`.
- Tenant-attribution failure path verified in
  `test_process_events_marks_unresolved_tenant`.
- Signature-verification is HMAC-SHA256 only. ECDSA mode not implemented.
- EC1 startup guard still refuses production start when
  `SENDGRID_WEBHOOK_ENABLED=true` without a valid secret.

**Feature Entitlements.**
- `GET /api/entitlements` and `GET /api/entitlements/{feature_key}` (tenant-readable).
- `require_entitlement(feature_key)` dep returns **402** when denied.
- **No** platform-scoped write endpoint is exposed. `_upsert_entitlement_for_tests`
  is a test-only helper, not routed.
- Expiry + quota checks live in `has_entitlement`, covered by
  `test_expired_entitlement_is_denied` and `test_quota_exhausted_denies`.

## 5. Tenant + user isolation proof

`tests/test_ec2_cross_tenant.py` sweeps every new collection:
`settings`, `activity_events`, `notifications`, `feature_entitlements`,
`file_links`. Additionally:
- `test_notifications_isolated_per_user_and_tenant` verifies staff
  cross-user isolation.
- `test_mark_read_cannot_touch_other_users_row` verifies mutation cross-user
  isolation.

## 6. Secret non-leakage proof

`tests/test_integration_status.py::test_status_shape_and_no_secret_values`
asserts:
- Every integration report has exactly `{name, enabled, configured, missing_secrets, ok}`.
- `missing_secrets` contains ONLY uppercase env-var names, never values.

## 7. Existing MVP systems extended (not duplicated)

- MVP `Attachment` remains authoritative for order/quote/invoice attachments.
  `FileLink` is a NEW polymorphic layer for cross-entity references that
  future portal/webstore/wrap-lab work will use.
- MVP `audit.record_audit` remains authoritative. `activity.record_activity`
  is a NEW feed layer that links to `audit_event_id`.
  `activity.record_activity_with_audit` writes both.
- MVP `EmailLog` remains the outbound record. `email_activity` is a NEW
  observability stream. Outbound writes now mirror an `internal` row so the
  feed reflects sends before webhook events arrive.
- MVP `settings` collection is NEW (there was no prior key/value settings
  system). Pricing config lives in the existing `pricing_settings` collection
  and is untouched.

## 8. Test results

```
92 passed, 6 warnings in 1.66s
```

New tests: 58 across 9 files:
- `tests/test_settings.py` (6)
- `tests/test_notifications.py` (6)
- `tests/test_webhooks_sendgrid.py` (9)
- `tests/test_upload_validation.py` (7)
- `tests/test_entitlements.py` (8)
- `tests/test_integration_status.py` (3)
- `tests/test_email_activity.py` (3)
- `tests/test_ec2_cross_tenant.py` (5)
- `tests/test_activity.py` (2)
- `tests/test_ec2_permissions.py` (8)

Existing 34 EC1 tests still pass.

## 9. Frontend surfaces verified

Screenshots taken during smoke testing:
- Home dashboard renders with notification bell in topbar (`data-testid="notification-bell"`) — bell count polling live.
- `/settings/company` renders `Company Settings` with editable Company Profile,
  Invoicing Defaults, and Branding namespaces backed by `/api/settings/*`.

## 10. Docs written

- `/app/docs/architecture/EC2_SHARED_SERVICES.md`
- `/app/docs/integrations/sendgrid_webhook.md`
- `/app/docs/security/EC2_SECURITY_POSTURE.md`

## 11. Rollback

`git diff HEAD` scoped to files listed in §1-§2. Drop new collections via a
one-shot mongo shell command if needed. Set `SENDGRID_WEBHOOK_ENABLED=false`
(already default) to disable the webhook route.

## 12. Deferred to later checkpoints

- Stripe webhook — EC3.
- Platform-scoped entitlement write API — commercial checkpoint.
- Portal-specific notification delivery — EC4.
- SMS/MMS webhook — conditional inside EC14.
- Additional settings namespaces (portal, sales_tax, notifications) — populated
  by the module that owns them.
