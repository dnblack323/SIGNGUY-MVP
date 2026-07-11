# Repository Roles (LOCKED)

**Permanent product:** `dnblack323/SIGNGUY-MVP`. Only repository that receives new development.

**Frozen mirror:** `SIGNGUY-AI-OS`. No new development. Archive only after final commercial completion. No deletion.

**Architecture + scaffold donor:** `signguyai_rebuild_version` (REB). Read-only reference. Sanitize `PreviewEnvelope` and resolve `core_runtime` imports on any port. Never copy a whole donor module wholesale.

**Financial-logic donor:** `signguy-ai-feb22` (FEB). Read-only reference. Rename Job→Order on every ported line. Preserve invoice reconciliation logic, payment idempotency, and controlled void behavior.

**Feature-discovery + targeted donor:** `signguyai` (ORIG). Read-only reference. Module preflight required before any port. Never copy monolithic `App.js`, giant pricing files, dev/backup routes, or Job-domain routes.

**Rules (LOCKED — EC1):**
- No new rebuild repository.
- No merging donors into MVP.
- No deletion or archival of donors before final commercial completion.
- No preview architecture, `core_runtime` fallback, `PreviewEnvelope`, or preview-user impersonation defaults may be introduced into MVP.
- Donor files may be inspected only to understand approved architecture patterns.
