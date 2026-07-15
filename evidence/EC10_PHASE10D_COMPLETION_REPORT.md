# EC10 Phase 10D — Customer Decision Room Models and Internal Authoring
## COMPLETION REPORT

**Date:** 2026-02. **Scope:** Phase 10D only (per owner authorization). This is internal authoring only — no customer/public access, no decision-to-order integration, no templates, and Phase 10E/10F/10G were NOT started.

---

### 1. Existing systems reused (never duplicated)

- **Customer** (`db.customers`) — `customer_id` cross-tenant existence check only.
- **Quote / QuoteLineItem** (`db.quotes` / `db.quote_line_items`) — referenced by id; never mutated, never re-read for pricing.
- **Order / OrderItem** (`db.orders` / `db.order_items`) — referenced by id, including an `order_item_id ↔ order_id` consistency check; never mutated.
- **IntakeSubmission** (`db.intake_submissions`) — `intake_id` reference only (the model already reserved a `decision_room_id` field back in Phase 10A/10B — Phase 10D does not populate it yet; that linkage belongs to the not-yet-built decision-to-order phase).
- **File / object storage** (`db.files`, existing `/files/upload`) — every `file_ids`/`thumbnail_file_id`/`rendered_preview_file_id` value is a reference to an existing, immutable record; nothing is re-uploaded or copied here.
- **Proof** (`db.proofs`) — `proof_id` reference only; Proof approval state remains fully owned by the existing Proof/Approval system.
- **VisualMarkup** (Phase 10C, `db.visual_markups`) — `visual_markup_id` reference only.
- **PricingSnapshotRecord** (EC9, `db.pricing_snapshot_records`) — `pricing_snapshot_id` reference; only its frozen `selected_final_price_cents` value is copied (once, at attach time) into `DecisionOption.suggested_price_cents`. The snapshot record itself is never mutated, never recalculated, and never deleted by anything in this file (verified by test).
- **`record_audit()`** (existing audit service) — reused verbatim for every mutation.
- **Tenant/permission system** (`Perm`, `require_permission`, `permissions_for_role`) — extended with 4 new permission strings; no new role system was created.

No repository classes were introduced — the router → service → direct-DB-access architecture matches every other EC10 module.

### 2. Files changed

**Backend (new):**
- `app/models/decision_room.py` — `DecisionOption` (embedded), `DecisionRoom`, `DecisionRoomVersion`.
- `app/services/decision_room_service.py` — full authoring surface (create/list/get/update room; add/update/duplicate/reorder/archive/restore option; attach/detach media; attach/detach pricing snapshot; readiness validation; lifecycle `transition()` + dedicated `publish_room()`; list/get version; internal `preview()`).
- `app/routers/decision_room.py` — `/api/decision-rooms*` (staff-only).
- `tests/test_ec10_phase10d_decision_room.py` (new, 19 targeted tests).
- Additive: `app/core/permissions.py` (4 new `Perm` values; `DECISION_ROOM_READ`/`WRITE` added to `STAFF_PERMS`), `app/core/db.py` (6 new indexes), `server.py` (router registration).

**Frontend (new):**
- `lib/decisionRoom.js` — statuses, allowed-transition map (mirrors the backend map exactly), badge/price-display constants, blank-option factory.
- `components/decisionRoom/DecisionOptionCard.jsx` — one comparison card's full editor (label/badge/headline/description/features/timing + composes the two sections below + notes + reorder/duplicate/archive controls).
- `components/decisionRoom/DecisionOptionPricingSection.jsx` — price-display mode, manual price ($), pricing-snapshot attach/detach (by id), selected-price-source toggle, backend-computed displayed price (read-only).
- `components/decisionRoom/DecisionOptionMediaSection.jsx` — file attachment (reuses the existing `FileAttachmentPicker`), proof/markup/thumbnail/rendered-preview id attach/detach.
- `components/decisionRoom/DecisionRoomVersionHistory.jsx` — read-only frozen-version list dialog.
- `components/decisionRoom/DecisionRoomPreviewDialog.jsx` — internal customer-safe preview dialog.
- `pages/DecisionRoomsPage.jsx`, `pages/DecisionRoomNewPage.jsx`, `pages/DecisionRoomEditorPage.jsx` — list / create / editor routes.
- Modified (additive): `components/common/StatusPill.jsx` (`decision_room`, `decision_badge` color maps), `lib/navigation.js` (Decision Rooms flyout entry under Shop Operations, gated on `decision_room:read`), `App.js` (3 new routes).

### 3. DecisionRoom model

`DecisionRoom` is tenant-scoped and holds: `title`/`internal_name`/`customer_safe_intro`, `status`, optional `customer_id`/`intake_id`/`quote_id`/`order_id`/`order_item_id` (every non-null reference is validated cross-tenant at write time — a bad or foreign-tenant id is rejected `404`, verified by test), a reserved (unused) `public_token_id`, `current_version`/`published_version` integers, `expiration_at`, four customer-behavior flags (`allow_save_for_later`/`allow_customer_comments`/`allow_customer_questions`/`allow_change_requests`, all default `False`), `require_internal_acceptance` (default `True`, matching the EC10 owner decision #1 recommended default), and audit fields (`created_by_user_id`/`updated_by_user_id`/`published_by_user_id`/timestamps). `options` is an embedded `list[DecisionOption]` on the room document itself — see §4 for why.

### 4. DecisionOption architecture

**Embedded on the parent `DecisionRoom`**, not a separate collection — mirroring the `IntakeSubmission.items`/`IntakeItem` precedent from Phase 10A/10B (the current database convention for "always authored/reordered/duplicated as a unit with the parent, never queried independently"). This also makes freezing a version trivial and atomic: a `DecisionRoomVersion` snapshot is just a deep copy of the room's `options` array at that instant, with no risk of a separate collection's rows drifting out of sync with the room during a publish.

Every field from the spec is implemented: `id`, `display_order`, `internal_name`, `customer_label`, `badge_type`, `custom_badge_text` (sanitized — non-printable characters stripped, trimmed, capped at 60 chars), `headline`, `customer_safe_description`, `included_features`/`excluded_features` (lists), `expected_timing`, `price_display_mode`, `pricing_snapshot_id`, `suggested_price_cents`, `manual_price_cents`, `selected_price_source`, `selected_display_price_cents` (backend-derived, never client-writable), `quote_line_item_id`, `order_item_id`, `proof_id`, `file_ids`, `visual_markup_id`, `rendered_preview_file_id`, `thumbnail_file_id`, `internal_notes`, `customer_safe_notes`, `active`, and audit fields. All money is integer cents.

### 5. Status lifecycle

`draft → ready → published → {closed | expired} → archived`, plus `archived → draft` (restore) and `ready → draft` (back to edit). Implemented as an explicit `ALLOWED_TRANSITIONS` map in the service, enforced by `transition()`; **`published` is deliberately absent from every entry's allowed-target set** — it is reachable ONLY through the dedicated `publish_room()` action (which also performs readiness validation and freezes a version — see §9). Every transition (including the dedicated publish/archive/restore actions) emits an audit event named `decision_room.<target>` or `decision_room.published_version_created`. Attempting any transition not in the map returns `400 invalid_transition` (verified by test: draft/ready cannot jump straight to `published` via the generic transition endpoint). `expired`/`closed`/`archived` rooms are locked against further edits (`400 room_locked` on any option/room mutation) but remain fully readable/viewable internally — nothing is ever deleted.

### 6. Option labels and badges

`badge_type` is one of `recommended`/`best_value`/`premium`/`budget`/`fastest`/`custom`/`none`. **At most one option per room may be `recommended`** — enforced server-side on every add/update/duplicate: setting a new option to `recommended` automatically demotes any other option's `recommended` badge to `none` (not rejected — auto-corrected, which is friendlier for staff and still satisfies "at most one" as a live invariant), verified by test. `custom_badge_text` only applies to `custom` and is sanitized (non-printable stripped, trimmed, 60-char cap) — badges never touch or influence any price field.

### 7. Media, Proof, and markup integration

`file_ids`/`proof_id`/`visual_markup_id`/`rendered_preview_file_id`/`thumbnail_file_id` are pure references — validated cross-tenant on every write (a foreign-tenant or nonexistent id is rejected `404`, verified by test for files, proofs, and visual markups). No inline base64 and no file bytes are ever copied into a `DecisionOption` or a frozen `DecisionRoomVersion` — only ids. Proof approval state is untouched; a Decision Option can *point at* a Proof but never replaces or duplicates one. The internal preview (§11) exposes `file_ids`/`rendered_preview_file_id`/`thumbnail_file_id` (intended customer-visible media) but never `proof_id`/`visual_markup_id`/`internal_notes` (internal linkage, stripped).

### 8. Pricing snapshot integration

Attaching a `pricing_snapshot_id` copies that snapshot's frozen `selected_final_price_cents` value into `DecisionOption.suggested_price_cents` **once, at attach time** — the snapshot record itself is never written to again (verified by test: the snapshot document is byte-identical before/after an attach+detach cycle). `selected_display_price_cents` is always backend-computed from `selected_price_source` (`manual` → `manual_price_cents`, `snapshot` → `suggested_price_cents`) and is recomputed on every relevant write; it is never invented — detaching a snapshot while `selected_price_source` is still `"snapshot"` correctly leaves the displayed price `None` rather than falling back to a guessed value (verified by test). Nothing in this phase recalculates a price from scratch — `manual_price_cents` only ever contains a value a human typed.

### 9. Versioning behavior

`current_version` and `published_version` are both integers starting at `0`. **`publish_room()`** is the only function that inserts a `DecisionRoomVersion` row — it requires status `ready` or already-`published`, re-runs readiness validation, computes `new_version_number = published_version + 1` (monotonic, regardless of how many draft edits happened since the last publish), freezes a full deep copy of the room's current `options` plus title/intro/behavior-flags/expiration into the new version row, and sets both `current_version` and `published_version` to that number. **Any edit made while `status == "published"`** bumps `current_version` by 1 (a cheap, DB-only signal — no new frozen row) so `current_version != published_version` tells staff "there are unpublished changes" (surfaced in the editor UI as an amber "Unpublished changes" badge). The next `publish_room()` call folds that drift back into alignment, producing the correctly-monotonic next version number. A previously published `DecisionRoomVersion` is **never** re-read from live Quote/Order/File/Proof state — it is self-contained. Verified end-to-end by test: publish → edit (current_version diverges from published_version, no new version row) → publish again (new version row, both counters realign) → re-fetch the FIRST version and confirm it is still byte-identical to what was frozen before the edit.

### 10. Internal authoring UI

`/decision-rooms` (list with status filter chips), `/decision-rooms/new` (title/intro/customer/quote/order/intake selectors + behavior-flag checkboxes, all optional except title), `/decision-rooms/:id` (the editor). The editor: room-details edit-toggle (title/intro/expiration/order id), status pill + readiness banner (shown whenever not-ready and the room is still editable), transition buttons (filtered by `ALLOWED_ROOM_TRANSITIONS[status]`, with `archived` additionally gated on `hasPerm("decision_room:archive")` client-side — the backend re-enforces this regardless), a separate "Publish"/"Publish new version" button gated on `decision_room:publish`, per-option cards with reorder (up/down)/duplicate/archive-restore controls, an "Add option" button, a "Versions" button (opens the read-only history dialog), and a "Preview" button (opens the internal customer-safe preview dialog). No page-builder/drag-and-drop canvas was built — every input is a plain, structured form field, matching the spec's "keep the editor compact and structured" instruction.

### 11. Internal customer-safe preview

`GET /decision-rooms/{id}/preview` (and the `DecisionRoomPreviewDialog` frontend component that renders it) returns ONLY: room title/intro/status/expiration/behavior-flags, and per active option (sorted by `display_order`): `customer_label`, `badge_type`/`custom_badge_text`, `headline`, `customer_safe_description`, `included_features`/`excluded_features`, `expected_timing`, `price_display_mode`, `displayed_price_cents` (null unless `price_display_mode == "show_price"`), `file_ids`/`rendered_preview_file_id`/`thumbnail_file_id`, `customer_safe_notes`. It never includes `internal_notes`, `internal_name`, `created_by_user_id`/`updated_by_user_id`, `pricing_snapshot_id`, `suggested_price_cents`, `manual_price_cents`, `selected_price_source`, `proof_id`, `quote_line_item_id`, or `order_item_id` — verified by test asserting all of those keys are absent from the response. The frontend dialog additionally prints an explicit italic disclaimer that this is a staff-only, read-only view with no operational customer-action buttons — there is no fake "Select"/"Reject" affordance anywhere.

### 12. Readiness validation

`validate_readiness()` is a pure, structural check run before `ready`/`publish` (and exposed standalone via `GET /decision-rooms/{id}/readiness`): requires a non-empty title, a `customer_id`, at least one of `intake_id`/`quote_id`/`order_id`/`order_item_id`, **at least two active options** (chosen over "at least one" since a Decision Room's entire purpose is comparison), every active option having a `customer_label` or `internal_name`, every `show_price` option having a non-null `selected_display_price_cents`, at most one `recommended` option (defensive — already enforced at write time), and a non-past `expiration_at` if set. It never invents a missing price or media reference — it only reports what's missing, returning `{ready: bool, errors: [...]}`. Verified by test for every individual rule.

### 13. Permissions

4 new permissions: `decision_room:read`, `decision_room:write` (granted to ALL staff, matching the Intake/Markup self-service convention), `decision_room:publish`, `decision_room:archive` (owner/admin only — freezing a published version is customer-exposure-adjacent even though 10E's actual customer access isn't built, and archiving a room out of normal internal views is reserved for the same reason). The generic `/transition` endpoint is gated on `decision_room:write` but has an extra in-handler check requiring `decision_room:archive` specifically when `target == "archived"`, so a plain staff login cannot bypass the dedicated `/archive` route's stricter permission by going through `/transition` instead — verified by test. A `role: "customer"` user (no entry in `ROLE_PERMISSIONS`) is rejected `403` on every endpoint, confirming no non-staff role can ever satisfy a Decision Room permission check.

### 14. Audit events

`decision_room.created`, `decision_room.updated`, `decision_room.option_added`, `decision_room.option_updated`, `decision_room.option_duplicated`, `decision_room.options_reordered`, `decision_room.option_archived`/`option_restored`, `decision_room.option_media_attached`/`option_media_detached`, `decision_room.option_pricing_snapshot_attached`/`option_pricing_snapshot_detached`, `decision_room.ready`/`draft`/`closed`/`expired`/`archived` (from `transition()`), `decision_room.published_version_created`. Every `diff` payload carries only ids/field-name-lists/counts — verified by test that a 500-character `customer_safe_description` and the full `options_snapshot` never appear in any recorded audit event.

### 15. Targeted backend test count and result

**19/19 passed** — `tests/test_ec10_phase10d_decision_room.py`: `test_create_draft_room_and_attach_context`, `test_cross_tenant_context_references_rejected`, `test_add_multiple_options_badges_and_recommended_exclusivity`, `test_duplicate_option_new_id_and_does_not_inherit_recommended`, `test_reorder_options`, `test_archive_and_restore_option`, `test_attach_file_proof_markup_and_cross_tenant_rejection`, `test_pricing_snapshot_attach_detach_and_display_price_computation`, `test_readiness_report_and_minimum_active_options`, `test_option_label_and_price_required_for_readiness`, `test_ready_transition_accepted_and_invalid_transition_rejected`, `test_publish_creates_immutable_version_and_edit_bumps_current_version`, `test_internal_preview_excludes_internal_fields`, `test_tenant_isolation`, `test_permission_enforcement`, `test_audit_events_emitted_without_bulky_content`, `test_no_quote_order_orderitem_mutation_and_no_pricing_recalculation`, `test_room_locked_when_archived_and_restorable`, `test_no_public_or_unauthenticated_customer_access`.

**68/68 directly-affected prerequisite tests re-verified green** (unchanged, no regressions): `test_ec10_phase10a_intake_contracts.py`, `test_ec10_phase10b_intake_workflows.py`, `test_ec10_phase10c_visual_markup.py` (Decision Rooms reference Visual Markup and Files), `test_ec9_phase9g_snapshots_and_advisory.py` (Decision Options reference Pricing Snapshots), `test_permissions_scope.py` (permission catalog was extended). Command: `python -m pytest tests/test_ec10_phase10a_intake_contracts.py tests/test_ec10_phase10b_intake_workflows.py tests/test_ec10_phase10c_visual_markup.py tests/test_ec9_phase9g_snapshots_and_advisory.py tests/test_permissions_scope.py -q` → `68 passed`. No `testing_agent`, no full backend regression suite was run.

### 16. Frontend test/build result

`cd /app/frontend && CI=true yarn craco build` → **Compiled successfully.** `main.79014a82.js` (407.18 kB gzip, +6.66 kB over the Phase 10C baseline for the new Decision Room pages/components), `795.c1f8920e.chunk.js` unchanged (135.91 kB — the Fabric/pdfjs chunk, untouched by this phase), `main.e0c77cb5.css` (12.81 kB gzip, +23 B). No errors, no new warnings. A live smoke check confirmed the new `/api/decision-rooms` route is registered and enforcing auth end-to-end (`GET` with no bearer token → `401`, matching the real, non-overridden `get_current_user` dependency). No browser automation, screenshots, or `testing_agent` were used — the build/compile check revealed no defect that would have warranted one.

### 17. Known gaps (all intentional, deferred to their named phase or documented as a pragmatic MVP simplification)

- **No dedicated Proof/Visual-Markup/Pricing-Snapshot picker UI** — staff paste an existing record's id into a plain text field (backend still validates tenant + existence on every attach). A searchable picker is a reasonable follow-up enhancement, not required by the Phase 10D spec.
- **No `quote_line_item_id`/`order_item_id` editor field on the option card** — these are accepted and validated by the backend (and covered by tests), but the current UI doesn't expose an input for them yet, since Phase 10D's spec did not require surfacing every reference field in the compact editor.
- Readiness's "at least two active options" threshold was implemented as a **hard minimum of 2** (the spec allowed either "two" or "one, if the specification permits" — no such permission was found in the controlling preflight, so the stricter, comparison-appropriate default was used).
- `IntakeSubmission.decision_room_id` (reserved since Phase 10A/10B) is still unpopulated — wiring a Decision Room back onto its originating Intake is deferred to whichever later phase formally defines that linkage's write path.
- No frontend Jest unit tests were added for the new Decision Room components — per the owner's explicit "targeted backend tests + build check only" instruction inherited from Phase 10C, and re-confirmed by this phase's "no browser automation/screenshots unless a defect is found" instruction.
- Public-access stub fields (`public_token_id`) exist on the model but are entirely unused — no code path reads, writes meaningfully, or resolves them; that is intentionally Phase 10E's job.

### 18. Three owner decisions from the EC10 preflight §10 — reproduced verbatim

| # | Issue | Why it matters | Recommended option | Alternative | Can implementation proceed around it? |
|---|---|---|---|---|---|
| 1 | Does a customer "Select" in the Decision Room require internal staff acceptance before the live Quote/Order Item changes, or can it apply immediately? | Directly determines whether Phase 10F needs a staff review queue or can be a straight-through pipe. The EC10 spec text says "only through an explicit controlled action" — read most naturally as **staff acceptance required**, but the owner should confirm this is not meant to allow direct customer-driven auto-apply for low-risk selections (e.g. size-only changes). | **Require an explicit staff/controlled acceptance step for every decision, no auto-apply exceptions** (matches spec text literally, matches `CustomerIntake` precedent, safest default). | Allow tenant-configurable auto-apply for specific low-risk option types later (P2, not EC10). | Yes — Phase 10A–10E can be built without this being decided; Phase 10F (the actual Quote/Order Item write) is genuinely blocked without it. Phase 10D's `require_internal_acceptance` field defaults to `True` (the recommended answer) but is not yet enforced by any code path, since nothing in 10D writes to a Quote/Order. |
| 2 | Can customers annotate/draw directly on markup, or is markup staff-only with customer view/comment-only? | Changes Phase 10C/10E scope materially (customer-facing Fabric.js editor vs. read-only viewer + comment pins). Spec §3 lists "Customer and staff comments anchored to markup points" (implying customers comment, not necessarily draw) but §2/§3 elsewhere is ambiguous about customer-authored shapes. | **Staff draws/authors markup; customers can only add anchored comments/pins (not freeform shapes) and approve/acknowledge a version** — safer, matches "Approval or acknowledgement per version" language, avoids customers accidentally corrupting a proof-quality asset. | Allow customers full drawing parity with staff. | Yes for 10C/10D (staff-side editor/authoring is needed regardless); blocks the exact scope of 10E's customer-facing markup UI. |
| 3 | Should the "Wrap Command Center"/"Wrap Lab" naming correction register item interact with EC10 at all (e.g. vehicle-graphics intake)? | Just a scope-boundary confirmation — Wrap Lab is EC15 (held, unauthorized). | **No — EC10 intake/markup/decision-room applies generically to all categories including vehicle graphics pricing (EC9 already supports it), but any Wrap-Lab-*specific* workflow (e.g. vehicle diagrams) stays out of EC10 and waits for EC15.** | — | Yes, does not block any EC10 phase; stated here only for completeness per the spec's request to flag scope boundaries. |

None of these three were resolved or acted on in Phase 10D, as instructed — reproduced here unresolved, for the owner's future decision before Phase 10E (#2) and Phase 10F (#1) begin. Phase 10D's staff-only authoring implementation, and its `require_internal_acceptance` default, are consistent with (and do not preempt) either answer to #1 or #2.

### 19. Confirmation — no testing_agent, broad suites, browser automation, or screenshots ran

Only `python -m pytest` (targeted Phase 10D test file + 5 directly-affected prerequisite test files, 87 tests total) and `yarn craco build` were run this session. No `testing_agent`, no full backend or frontend regression suite, no Playwright/browser automation, and no screenshots were used — the build compiled cleanly and every targeted test passed on the first corrected attempt (one bug was found and fixed by the targeted tests themselves: a duplicate-option `display_order` kwarg collision, and a version-numbering arithmetic correction — both caught by `pytest`, not a screenshot).

### 20. Confirmation Phase 10E and later phases were NOT started

No customer-facing Decision Room route, no public-token resolution endpoint, no customer option-selection/rejection/comment/question/change-request capture, no email/SMS delivery, no Quote/Order/Order Item mutation from a decision (verified by test — the referenced Quote/Order/OrderItem/PricingSnapshotRecord documents are byte-identical before and after every Decision Room operation in this phase), and no template system exist anywhere in this session's changes. `public_token_id` remains an unused, unresolved reserved field. Phase 10D is internal-authoring-only, exactly as scoped.
