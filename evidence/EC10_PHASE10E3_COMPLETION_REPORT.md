# EC10 Phase 10E-3 — Customer Questions, Anchored Comments/Pins, and Save for Later — COMPLETION REPORT

**Date:** 2026-02
**Scope authorized:** Phase 10E-3 ONLY. Phase 10E-4 (broad internal review queue) and Phase 10F (commercial apply) explicitly NOT started.

## 1. Existing systems reused
- **Phase 10E-1** portal/public access validation: every new function funnels through `_get_accessible_room_and_version()` (unchanged) — same `published`/`closed`/`expired` read-window, same 404-on-unpublished, same tenant/customer ownership check.
- **Frozen published Decision Room versions**: every question/overlay/save is tied to the exact `published_version_id` in effect at submission time; option/media/markup validation is checked against that frozen `options_snapshot`, never the live draft.
- **Phase 10E-2 `CustomerDecision` architecture**: reused its exact idempotency pattern (find-before-insert + duplicate-key-race fallback), its `source_access_mode`/`customer_id`/`public_token_id` identity shape, its audit-then-notify sequencing, and its portal/public/staff three-router split. Deliberately kept as SEPARATE collections (`decision_room_questions`, `decision_room_overlays`, `decision_room_saved_for_later`) rather than folding into `CustomerDecision`, per your explicit instruction not to distort its selection/rejection history.
- **Phase 10C markup coordinate contract**: `VisualMarkup.source_file_type`/`source_page_number` reused verbatim for PDF-page validation. Customer overlays use their OWN normalized (0.0-1.0) coordinate space, stored in a separate collection — never touching `MarkupVersion.structured_markup_json`.
- **Existing audit (`record_audit`) and notification (`notify_tenant_owners`) contracts** — reused as-is, zero new infrastructure.

## 2. Files changed
- `backend/app/models/decision_room.py` — added `DecisionRoomQuestion`, `DecisionRoomOverlay`, `SavedForLater`.
- `backend/app/core/db.py` — new indexes for the 3 collections; **fixed a latent idempotency-index bug** (see §9).
- `backend/app/services/decision_room_service.py` — ~450 new lines: question/overlay/save-for-later submit+list+staff-respond+staff-resolve+edit+withdraw functions, shared anchor validator, sanitizer.
- `backend/app/routers/decision_room.py` (staff), `decision_room_portal.py` (portal), `public_actions.py` (public token) — new endpoints, listed in §3-§5.
- Frontend: `DecisionRoomCustomerView.jsx` (extended), `DecisionRoomAnchorableMedia.jsx` (new), `DecisionRoomQuestionsPanel.jsx` (new, staff), `PortalDecisionRoomPage.jsx`, `PublicApp.jsx`, `DecisionRoomEditorPage.jsx`, `DecisionRoomNewPage.jsx`.
- New test file: `backend/tests/test_ec10_phase10e3_questions_overlays_save_for_later.py`.

## 3. Question model and lifecycle
`DecisionRoomQuestion`: `open → answered → resolved`. Gated behind the room's own `allow_customer_questions` flag (declared in Phase 10D, inert until now). Fields preserved exactly as specified: `tenant_id`, `decision_room_id`, `published_version_id`, `option_id`, `source_file_id`, `visual_markup_id`, `markup_version_id`, `customer_id`/`public_token_id`, `source_access_mode`, `customer_message`, `status`, `submitted_at`, `idempotency_key`. Message is required, HTML-stripped, plain text, max 2000 chars. Anchor fields are all OPTIONAL (a room-level question needs none). Closed/expired rooms reject new questions (still readable). Routes: `POST/GET /portal|public/decision-rooms/{id}/questions`; staff `GET /decision-rooms/{id}/questions`.

## 4. Staff-response behavior
`POST /decision-rooms/{id}/questions/{qid}/respond` (staff, `decision_room:write`) sets `staff_response`, `responded_by_user_id`, `responded_at`, flips status to `answered`. A separate `POST .../resolve` moves status to `resolved` independently (staff may resolve without writing a response). One response per question — deliberately NOT a threaded messaging system. `_question_customer_safe()` strips `responded_by_user_id`/`customer_id`/`public_token_id`/`tenant_id` before returning to the customer — verified by test. Never touches a commercial record. Minimal staff UI: `DecisionRoomQuestionsPanel.jsx` (view/respond/resolve only, mounted on the room editor).

## 5. Anchored comment/pin behavior
`DecisionRoomOverlay`: `overlay_type` = `comment` | `pin`, `status` = `active` | `withdrawn`. Gated behind `allow_customer_comments` (also a dormant Phase 10D flag, now live). Stored ENTIRELY separately from `MarkupVersion.structured_markup_json` — confirmed by test (`markup_version_before == markup_version_after` after a full create/edit/withdraw cycle). `marker_number` auto-assigned server-side, sequential per `(room, published_version, source_file_id/visual_markup_id, overlay_type="pin")` — customers never supply it. Customers may `PATCH` (edit message) or `POST .../withdraw` only their OWN `active` overlay — ownership checked by exact `customer_id`/`public_token_id` match, a non-owner request 404s identically to a truly-missing overlay. A withdrawn overlay is locked from further edits (400 `overlay_locked`) but never deleted (history preserved). Routes: `POST/GET/PATCH /portal|public/decision-rooms/{id}/overlays[/{overlay_id}[/withdraw]]`; staff read-only `GET /decision-rooms/{id}/overlays` (no staff mutation — staff can view but never edit/withdraw a customer's overlay).

## 6. Coordinate and frozen-media validation
`normalized_x`/`normalized_y` must both be in `[0.0, 1.0]` (400 `invalid_coordinates` otherwise). Every anchor is resolved through `_resolve_and_validate_anchor()`: `source_file_id` reuses the EXACT Phase 10E-1 `resolve_customer_safe_media()` allowlist (file not referenced in the frozen version → 404); `visual_markup_id` must belong to an active option in the frozen snapshot (or match the given `option_id`'s own markup) → 404 `visual_markup_not_in_version` otherwise; `markup_version_id` (if given) must belong to that exact `visual_markup_id` → 404 `markup_version_not_found`; `page_number` must equal the markup's frozen `source_page_number` when the markup is a PDF (400 `invalid_pdf_page` on mismatch) and must be omitted for non-PDF markup. An overlay with neither `source_file_id` nor `visual_markup_id` is rejected (400 `anchor_required`). **Fabric.js JSON is never accepted**: both `PortalOverlaySubmitIn`/`PublicOverlaySubmitIn` use `ConfigDict(extra="forbid")` — any extra field (e.g. `structured_markup_json`) causes a hard `422`, verified by test.

## 7. Save-for-later behavior
`SavedForLater` — a deliberately SEPARATE, minimal model from `CustomerDecision` (per your explicit instruction not to distort selection/rejection history for this). Gated behind `allow_save_for_later` (400 `save_for_later_not_allowed` when off). Never selects/rejects an option, never touches pricing, never extends `expiration_at`. Stores the exact `published_version_id` (verified by test). Closed/expired rooms reject new saves (400). Idempotent (duplicate key returns the same row, note NOT overwritten). Routes: `POST/GET /portal|public/decision-rooms/{id}/save-for-later`. Frontend shows "Saving does not select or reject any option" in the save form and a persistent "Saved on … — no selection was submitted" confirmation banner.

## 8. Customer-safe history
`_question_customer_safe()`/`_overlay_customer_safe()` strip `tenant_id`, `customer_id`/`public_token_id`, `responded_by_user_id`, `idempotency_key`, `source_access_mode` before returning to a customer — only IDs/labels/timestamps/status/message/response are ever exposed (verified by test). A customer only ever sees their OWN identity-scoped history (`customer_id` XOR `public_token_id` filter, mirroring the Phase 10E-2 precedent).

## 9. Security and idempotency
Tenant isolation, ownership, and frozen-version-only references all verified by test. **Bug found and fixed during this phase**: a compound Mongo index with `sparse=True` does NOT exclude documents missing only SOME of its fields (it only excludes documents missing ALL of them) — since `tenant_id`/`decision_room_id` are always present, two idempotency-key-less submissions to the same room would have collided with a spurious `E11000` duplicate-key error (a real latent bug, also present in the Phase 10E-2 `customer_decisions` index, now fixed for both). Replaced with `partialFilterExpression={"idempotency_key": {"$type": "string"}}` on all 4 idempotency indexes, plus a `_for_insert()` helper that drops the field entirely when falsy before every insert. Stale indexes on the live dev DB were dropped and cleanly recreated. Public-token endpoints (question/overlay/save-for-later `POST` only) are rate-limited at 20 requests/60s per IP (`_dr_rate()`, mirroring the existing `_qr_rate()` quote-request limiter) — verified by test (`429` after the 20th request).

## 10. Audit events
`decision_room.customer_question_submitted`, `decision_room.staff_response_submitted`, `decision_room.question_resolved`, `decision_room.customer_overlay_{comment|pin}_added`, `decision_room.customer_overlay_edited`, `decision_room.customer_overlay_withdrawn`, `decision_room.customer_saved_for_later` — every `diff` payload carries IDs/lengths only (e.g. `message_length`), never the full message body (verified by test).

## 11. Notification-hook behavior
Reuses `notify_tenant_owners()` exactly as-is for `customer_question_submitted` and `customer_overlay_submitted` (staff-facing). **Intentionally NOT implemented**: a "staff response posted" push to the customer, and any save-for-later notification — no reusable customer-facing notification channel exists without building new infrastructure, which is explicitly forbidden; customers see both live via the portal/public pull-based history endpoints instead. Every notification call is wrapped in `try/except` — verified by test that a simulated notification outage still returns `201` with the row durably saved.

## 12. Targeted test count and result
**13/13 new tests pass** (`tests/test_ec10_phase10e3_questions_overlays_save_for_later.py`): room/option-level questions, flag+message validation, HTML stripping, markup/page/version/media anchor validation, staff respond/resolve + customer-safe stripping, pin/comment with marker numbering, flag/anchor/coordinate validation, Fabric.js-payload 422 rejection, edit/withdraw ownership + staff-markup-untouched, save-for-later gating+lifecycle+idempotency+no-CustomerDecision-created, public-token parity, tenant isolation, rate limiting, audit+notification-failure-safety. Re-ran Phase 10D + 10E-1 + 10E-2 decision-room test files together — **53/53 total pass**, confirming zero regression from the shared-index fix.

## 13. Frontend production-build result
`yarn craco build` — compiles cleanly, zero errors/warnings.

## 14. Known gaps
- Anchored-pin click UI only works on `image`-type media in the customer view; PDF-page-anchored overlays are fully validated end-to-end on the backend but have no click-to-place UI yet.
- No dedicated staff UI for viewing anchored overlays (the read-only `GET /decision-rooms/{id}/overlays` endpoint exists and is tested; only the questions panel got a staff UI this phase).
- "Staff response posted" and "save for later" produce no customer-facing push notification (no infra to reuse without building new, which is forbidden).

## 15. Confirmation: no commercial mutation
Zero code path in this phase writes to `quotes`, `quote_line_items`, `orders`, `order_items`, any pricing/pricing-snapshot field, `proofs`, or `MarkupVersion.structured_markup_json`. Verified by test: `markup_version_before == markup_version_after` after a full overlay lifecycle, and `decisions_before == decisions_after` (customer_decisions count) after save-for-later use.

## 16. Confirmation: testing constraints honored
No `testing_agent`, no full backend/frontend regression suite, no browser automation, no screenshots were run. Only the one new targeted pytest file + the 3 directly-related pre-existing decision-room test files (10D/10E-1/10E-2, re-run because the shared idempotency-index fix touched code they depend on) + `yarn craco build`.

## 17. Confirmation: scope boundary honored
Phase 10E-4 (broad internal review queue) was NOT started — only a minimal, per-room, view+respond/resolve/acknowledge panel (continuing the exact pattern already established in Phase 10E-2, not a new queue). Phase 10F (applying a decision to a Quote/Order Item, commercial acceptance) was NOT started. Stopping here per instruction — awaiting explicit authorization before Phase 10E-4.
