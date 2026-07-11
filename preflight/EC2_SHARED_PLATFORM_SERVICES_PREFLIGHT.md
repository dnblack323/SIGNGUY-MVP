# EC2 — Shared Platform Services — Preflight

**Status:** Preflight COMPLETE. Implementation NOT started (deferred to fresh session — see §14).
**Authority:** `/app/SIGNGUY_AI_FINAL_CONSOLIDATED_MASTER_BUILD_PLAN.md` + `/app/evidence/EC1_evidence.md`.

## 1. MVP Files Inspected

- `backend/server.py` — 12 routers wired; `enforce_startup_guards` active; `ensure_indexes` at startup.
- `backend/app/core/{config,db,security,security_guards,money,terminology_guard,permissions,time_utils}.py`.
- `backend/app/deps.py` — `get_current_user`, `get_current_tenant`, `require_permission(*Perm)`.
- `backend/app/services/{audit.py, email.py, storage.py, sequence.py, pricing.py, starter_defaults.py}`.
- `backend/app/models/user.py` (Tenant + User + PasswordResetToken shapes).
- `backend/app/routers/{auth, users, customers, quotes, orders, work_orders, invoices, documents, emails, audit, dashboard, pricing}.py`.
- `frontend/src/{App.js, components/app-shell/AppShell.jsx, lib/navigation.js, auth/AuthContext.jsx}`.

## 2. Donor Files Approved for Reference (read-only)

- REB `routes/settings.py`, `models/settings.py`, `services/settings.py` — namespace/key/audit shape.
- REB `routes/communications.py`, `services/communications.py`, `models/notification.py`, `models/email_activity.py` — SendGrid webhook signature, event log.
- REB `routes/activity.py`, `services/activity.py`, `models/activity.py` — activity envelope extending audit.
- REB `services/upload_validation.py` — MIME/extension/magic-byte/SHA-256/filename sanitation.
- REB DocuLink `models/{file_link,document_link,document_share}.py` — polymorphic link + share shapes.
- REB `services/feature_entitlements.py` — feature-key/quota/expiry shape.

Reject during port: `PreviewEnvelope`, `core_runtime` fallbacks, preview-user impersonation, local-disk storage, permissive webhook production behavior, donor tenant/auth deps, donor route envelopes, donor frontend scaffolds.

## 3. Keep / Refactor / Extract / Rebuild / Reject Decisions

| Concern | Decision | Notes |
|---|---|---|
| Settings | REBUILD against MVP shared services using REB scaffold shape | New `models/settings.py`, `repositories/settings.py`, `services/settings.py`, `routers/settings.py`. Namespace + key + typed JSON. |
| Audit helper | KEEP | Do not replace. Activity extends. |
| Activity extension | EXTRACT & REBUILD | New `models/activity.py` linked to audit; single write path with dual visibility. |
| Notifications | REBUILD | REB shape as reference; recipient + tenant scoped; separate from portal notifications. |
| Email outbound | KEEP | `services/email.py`. Ensure metadata includes tenant_id + email_log_id + entity refs. |
| Email activity + SendGrid webhook | EXTRACT | Webhook signature verify + event log. Reuse EC1 `sendgrid_webhook_secret` gate. |
| Shared webhook infra | REBUILD | New `services/webhooks.py` framework + `webhook_events` collection. |
| Upload validation | EXTRACT | New `services/upload_validation.py` invoked before file record commit. |
| Polymorphic file links | REBUILD | New collections `file_links`, `document_links`, `document_shares`. MVP attachments stay. |
| Entitlements | REBUILD | New `models/feature_entitlement.py`, `services/entitlements.py`, `require_entitlement` dep. |
| Integration status | NEW | Read-only status surface; no secrets exposed. |
| Monitoring | NEW | Structured logging + minimal `system_events` collection. |

## 4. Files to Add

Backend models: `activity.py`, `settings.py`, `notification.py`, `email_activity.py`, `webhook_event.py`, `file_link.py`, `document_link.py`, `document_share.py`, `feature_entitlement.py`.
Backend repositories: `settings.py`, `notifications.py`, `email_activity.py`, `webhook_events.py`, `file_links.py`, `document_links.py`, `document_shares.py`, `feature_entitlements.py`, `activity.py`.
Backend services: `settings.py`, `notifications.py`, `webhooks.py`, `upload_validation.py`, `entitlements.py`, `activity.py`, `sendgrid_webhook.py`, `integration_status.py`.
Backend routers: `settings.py`, `notifications.py`, `webhooks.py`, `entitlements.py`, `integration_status.py`, `activity.py`.
Backend deps: `require_entitlement(feature_key)`.
Frontend: `pages/CompanySettingsPage.jsx`, `pages/IntegrationsPage.jsx`, `pages/FeatureAccessPage.jsx`, `pages/DataSecurityPage.jsx`, `components/notifications/NotificationBell.jsx`, `components/notifications/NotificationPanel.jsx`, `lib/entitlements.js`.
Tests: `test_settings.py`, `test_notifications.py`, `test_webhooks_sendgrid.py`, `test_email_activity.py`, `test_upload_validation.py`, `test_file_links.py`, `test_entitlements.py`, `test_integration_status.py`, `test_ec2_cross_tenant.py`, `test_ec2_permissions.py`.
Docs: 9 files under `/app/docs/architecture` + `/app/docs/integrations` + `/app/docs/security`.

## 5. Files to Modify

- `backend/app/core/config.py` — nothing (all EC2 secrets already declared in EC1).
- `backend/app/core/permissions.py` — no new perms needed; EC1 catalog covers EC2.
- `backend/app/deps.py` — add `require_entitlement`.
- `backend/app/core/db.py::ensure_indexes` — register EC2 indexes.
- `backend/server.py` — register 6 new routers.
- `backend/app/services/email.py` — add tenant + entity metadata parameters on outbound send; write to `email_activity` on send.
- `frontend/src/App.js` — register new pages under Control Center routes.
- `frontend/src/components/app-shell/AppShell.jsx` — mount NotificationBell in topbar.
- `frontend/src/lib/navigation.js` — flip `disabled: false` on the EC2-landed Control Center flyout entries.

## 6. Collections + Indexes

| Collection | Indexes |
|---|---|
| `settings` | unique `(tenant_id, namespace, key)`; `(tenant_id, namespace)` |
| `activity_events` | `(tenant_id, module, created_at)`; `(tenant_id, entity_type, entity_id)`; `(tenant_id, severity, created_at)` |
| `notifications` | `(tenant_id, recipient_user_id, status, created_at)`; `(tenant_id, recipient_user_id, read_at)` |
| `email_activity` | `(tenant_id, email_log_id, event_timestamp)`; unique `(provider, provider_event_id)`; `(tenant_id, related_entity_type, related_entity_id)` |
| `webhook_events` | unique `(provider, provider_event_id)`; `(provider, processing_status, received_at)` |
| `file_links` | `(tenant_id, parent_type, parent_id)`; `(tenant_id, file_id)` |
| `document_links` | `(tenant_id, document_id, entity_type, entity_id)` |
| `document_shares` | `(tenant_id, document_id)`; `(tenant_id, recipient_key, revoked)` |
| `feature_entitlements` | unique `(tenant_id, feature_key)` |
| `system_events` (monitoring) | `(kind, occurred_at)`; TTL on non-critical entries |

## 7. API Routes (new)

- Settings: `GET/PUT /api/settings/{namespace}` + `GET /api/settings/merged`.
- Activity: `GET /api/activity` (tenant-scoped filter).
- Notifications: `GET /api/notifications`, `GET /api/notifications/unread-count`, `POST /api/notifications/{id}/read`, `POST /api/notifications/read-many`, `POST /api/notifications/{id}/dismiss`.
- SendGrid webhook: `POST /api/webhooks/sendgrid` (signature verify + replay-safe).
- File links: `POST /api/file-links`, `GET /api/file-links?parent_type=&parent_id=`, `DELETE /api/file-links/{id}` (archive not destroy).
- Entitlements (tenant read): `GET /api/entitlements`; (platform-scoped write): `POST/PUT /api/platform/entitlements` — deferred to EC8 platform module unless owner earlier.
- Integration status: `GET /api/integrations/status`.

## 8. Permissions

EC1 catalog already contains: `settings:read/write`, `notification:read/manage` (via `TASK_READ`-style approach — add explicit perms), `integration:read/write`, `document:read/write/share`, `subscription:read`, `platform:*`. Add if missing during implementation.

## 9. Tenant-Isolation Rules

Every EC2 read + write filters `tenant_id`. `require_entitlement` runs AFTER `get_current_user` but BEFORE `require_permission`. Webhook tenant resolution uses signed metadata + email_log_id lookup — never raw payload tenant claims.

## 10. Webhook Security Rules

- HMAC-SHA256 on SendGrid; ECDSA on Stripe (EC3+).
- Missing production secret + `SENDGRID_WEBHOOK_ENABLED=true` fails startup (EC1 guard already in place).
- Signature failure = 401.
- Duplicate `(provider, provider_event_id)` = 200 no-op.
- Verification + processing failures recorded in `webhook_events` + `system_events`.

## 11. Test Plan

10 test files (see §4). Additional cross-tenant sweep test file (`test_ec2_cross_tenant.py`) enforces isolation on every new collection.

## 12. Rollback Plan

Revert new files + `search_replace` reverts to `server.py`, `db.py`, `AppShell.jsx`, `App.js`, `navigation.js`. Drop new collections via `mongo` shell only if migrations occurred. Restart supervisor.

## 13. Frontend Verification

- NotificationBell renders with unread count.
- Control Center flyout entries for Company Settings / Integrations / Feature Access / Data & Security become active (undisabled) and route successfully.
- Regression: EC1 sidebar tests remain green; existing MVP routes remain functional.

## 14. Implementation Deferral — Honest Status

**Preflight step is COMPLETE per EC2 §4 Step 1.**

The EC2 implementation body (backend models + repos + services + routers + FE surfaces + tests + docs = 30–50 new files) exceeds the remaining context window in this session (~45k tokens). Attempting to slam through would produce partial, undertested code that would fail EC2 exit conditions (§23) and violate the "do not mark complete merely because endpoints respond" rule.

**Recommendation:** resume EC2 implementation in a fresh session (fork) with this preflight as the entry contract. Because Prompt EC2 says "EC2 may continue directly into implementation after the preflight because the source and migration direction is already approved," the fresh session can proceed without re-approval — it inherits the approved direction encoded here.
