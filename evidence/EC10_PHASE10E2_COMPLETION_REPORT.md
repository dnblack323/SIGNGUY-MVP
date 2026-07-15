# EC10 Phase 10E-2 — Customer Option Selection, Rejection, and Change Requests — COMPLETION REPORT

**Date:** 2026-02
**Scope authorized:** Phase 10E-2 ONLY (per owner's adjusted instruction — `save_for_later` explicitly EXCLUDED, deferred to Phase 10E-3).
**Testing constraints honored:** No `testing_agent`, no full regression suite, no browser automation, no screenshots. One targeted pytest file + `yarn craco build` only, per standing owner instruction.

---

## 1. What was built

### 1.1 Backend model — `CustomerDecision` (`models/decision_room.py`)
Append-only event, NEVER mutated after insert (mirrors the `Approval` precedent). Fields:
- `tenant_id`, `decision_room_id`, `published_version_id` (authoritative — the exact frozen `DecisionRoomVersion._id` the customer was shown), `published_version_number` (display-only convenience).
- `action_type`: `option_selected` | `option_rejected` | `all_options_rejected` | `change_requested` (owner's exact literal names — no abbreviated `select`/`reject`/`request_change` values used anywhere).
- `option_id` (required for `option_selected`/`option_rejected`; forbidden for `all_options_rejected`; optional for `change_requested`).
- `comment` (required, non-empty, for `change_requested`).
- `source_access_mode`: `portal` | `public_token`; `customer_id` (portal) XOR `public_token_id` (public token).
- `actor_display`, `supersedes_decision_id`, `internal_review_status` (`pending_review` | `acknowledged` — server-derived only, never customer-settable), `idempotency_key`, `submitted_at`, `ip`, `user_agent`.

`save_for_later` is NOT in the `action_type` literal and no code path references it anywhere in this phase.

### 1.2 New room-level flag — `allow_reject_all`
Added to `DecisionRoom`, `DecisionRoomVersion` (frozen at publish time, same pattern as `allow_change_requests`), the customer-safe response, and the `DecisionRoomCreateIn`/`UpdateIn`/New-page checkbox. `all_options_rejected` is rejected with `400 reject_all_not_allowed` unless this flag is `true` on the frozen version — never assumed enabled.

### 1.3 Service (`decision_room_service.py`)
- `submit_customer_decision()` — validates: room must be `status="published"` (closed/expired stay readable but reject new writes with `400 room_not_open_for_decisions`; unpublished/archived rooms 404 via the existing `_get_accessible_room_and_version()`, never leaking existence); option must exist AND be active on the exact frozen `options_snapshot`; `change_requested` requires the `allow_change_requests` flag + non-empty comment; `all_options_rejected` requires `allow_reject_all` + no `option_id`.
- **Idempotency**: unique sparse index `(tenant_id, decision_room_id, idempotency_key)` — a duplicate submission (same client-generated key) returns the already-saved row (checked both pre-insert and on a DB duplicate-key race).
- **Selection superseding**: selecting a *different* option supersedes that same actor's most recent unresolved `option_selected` for the same room + exact `published_version_id` — expressed as `supersedes_decision_id` on the NEW row; the old row is never mutated or deleted. A dedicated `decision_room.customer_decision_superseded` audit event is recorded alongside the primary `decision_room.customer_<action_type>` audit event.
- **Notifications**: reuses the existing `notify_tenant_owners()` helper as-is (no new notification/retry system). Wrapped in `try/except` — a notification failure is logged and swallowed; it can never roll back or lose the already-durably-saved `CustomerDecision`.
- `list_customer_decisions()` — staff, all rows (pending + superseded, history never hidden).
- `list_my_customer_decisions()` — portal/public, the caller's own decision history on the room (drives "already decided" UI state).
- `acknowledge_customer_decision()` — staff-only, flips `internal_review_status` to `acknowledged` only. Never touches `action_type`/`option_id`/any Quote/Order/Order Item/pricing field.

### 1.4 Routes
- `POST /portal/decision-rooms/{id}/decisions` (new `portal:respond_decision_rooms` permission — deliberately separate from `portal:view_decision_rooms`, added to `owner_full`/`approver_only` presets), `GET /portal/decision-rooms/{id}/decisions`.
- `POST /public/decision-rooms/{id}/decisions?t=...`, `GET /public/decision-rooms/{id}/decisions?t=...` (reuses the existing multi-use `decision_room_view` token — never consumed, since a customer may change their mind before the room closes).
- `GET /decision-rooms/{id}/decisions` (staff, `decision_room:read`), `POST /decision-rooms/{id}/decisions/{decision_id}/acknowledge` (staff, `decision_room:write`).

### 1.5 Frontend
- `DecisionRoomCustomerView.jsx`: Select/Reject buttons per option (disabled once already selected/rejected respectively), a room-level "None of these work for me" (reject-all) action gated by `room.allow_reject_all`, and a Request-Change comment box gated by `room.allow_change_requests` — all hidden once the room leaves `published` status (shows a read-only historical-record note instead). Derives "already decided" badges purely from the caller-supplied `myDecisions` history — stays a pure presentational component.
- `PortalDecisionRoomPage.jsx` / `PublicApp.jsx`'s `PublicDecisionRoom` — wire the submit callback (fresh `crypto.randomUUID()` idempotency key per click, immediate reload of both room + decision history on success).
- `DecisionRoomCustomerDecisionsPanel.jsx` (new) — staff, read-only, mounted on `DecisionRoomEditorPage.jsx`: shows every decision (pending + superseded, badge-coded by `action_type`/`internal_review_status`), with an **Acknowledge** button only (no accept/apply/reject-internally/pricing-change action anywhere in this panel).
- `DecisionRoomNewPage.jsx` — added the "Allow customer to reject all options" checkbox.
- `StatusPill.jsx` — added `customer_decision_action`/`decision_review_status` color maps.

## 2. What was explicitly NOT built (per owner instruction)
- `save_for_later` action type, its service validation, routes, and buttons — remains Phase 10E-3.
- Anchored comments/pins, questions — Phase 10E-3.
- Staff acceptance/rejection of the commercial decision, or any write to a Quote/Order/Order Item/pricing field — Phase 10F.
- Any new notification/retry infrastructure — the existing `notify_tenant_owners()` contract was reused verbatim.

## 3. Testing performed
- **Backend**: new targeted file `tests/test_ec10_phase10e2_decision_room_customer_decisions.py` — **12/12 passed**. Covers: portal select → `pending_review` row; viewer-only identity rejected (403); idempotent duplicate submission (single row); selection superseding (old row untouched, new row points back); option-id-must-belong-to-frozen-version (404 for a live-only or nonexistent option); `all_options_rejected` gated by `allow_reject_all` (+ `option_id` forbidden alongside it); `change_requested` gated by `allow_change_requests` + non-empty comment; closed/draft rooms reject new writes (closed stays readable, draft 404s); public-token submit/list parity; tenant isolation; staff list + acknowledge with a **before/after `db.orders` document equality assertion proving zero commercial mutation**; customer-submitted `internal_review_status`/`customer_id` fields are silently ignored (always server-derived).
- Re-ran `tests/test_ec10_phase10d_decision_room.py` + `tests/test_ec10_phase10e1_decision_room_customer_access.py` + `tests/test_ec10_phase10e1b_decision_room_customer_media.py` — all decision-room-logic tests green; one media test failed on an **external object-storage 500/502** (transient, unrelated to any file touched in this phase — confirmed by re-running, a different sub-test failed the second time, and zero storage/upload code was modified in Phase 10E-2).
- **Frontend**: `yarn craco build` — compiles cleanly, zero errors/warnings.
- No `testing_agent`, no full regression suite, no browser automation, no screenshots — per standing owner instruction.

## 4. Files changed
- `backend/app/models/decision_room.py`, `backend/app/models/portal_identity.py`, `backend/app/core/db.py`, `backend/app/services/decision_room_service.py`, `backend/app/routers/decision_room.py`, `backend/app/routers/decision_room_portal.py`, `backend/app/routers/public_actions.py`
- `frontend/src/components/decisionRoom/DecisionRoomCustomerView.jsx`, `DecisionRoomCustomerDecisionsPanel.jsx` (new), `frontend/src/portal/PortalDecisionRoomPage.jsx`, `frontend/src/public/PublicApp.jsx`, `frontend/src/pages/DecisionRoomEditorPage.jsx`, `frontend/src/pages/DecisionRoomNewPage.jsx`, `frontend/src/components/common/StatusPill.jsx`
- New: `backend/tests/test_ec10_phase10e2_decision_room_customer_decisions.py`

## 5. Stopping point
Per owner instruction: **stopping after this completion report. Phase 10E-3 (Questions, anchored comments/pins, and save-for-later) is NOT started and requires explicit owner authorization.**
