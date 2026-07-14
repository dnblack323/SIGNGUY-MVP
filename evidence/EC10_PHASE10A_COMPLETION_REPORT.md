# EC10 Phase 10A — Intake Architecture and Canonical Data Contracts
## COMPLETION REPORT

**Date:** 2026-02. **Scope:** Phase 10A only (per owner authorization). Phase 10B and later NOT started.

---

### 1. Existing systems reused
Customer, Quote, Order, File/`Attachment`/object-storage (`/files/upload`), `CustomerIntake` (reused as the questionnaire-submission reference target), `audit.record_audit`, `sequence.next_number`, `core/permissions.py` namespace pattern. No system was duplicated; `IntakeSubmission` stores references (ids) only, never copies of any live record.

### 2. Files changed
- New: `app/models/intake_submission.py` (`IntakeSubmission`, `IntakeItem`)
- New: `app/services/intake_service.py` (create/update/add_item/transition, reference validation, conversion-preview contract, customer-safe-serialization helper)
- New: `app/routers/intake.py` (`/api/intake*`, staff-only)
- New: `tests/test_ec10_phase10a_intake_contracts.py` (18 targeted tests)
- Modified (additive only): `app/core/permissions.py` (`Perm.INTAKE_READ`/`INTAKE_WRITE`, added to `STAFF_PERMS`), `app/models/quote.py` / `app/models/order.py` (`decision_room_id: Optional[str] = None` on `Quote`, `Order`, `OrderItem` — Phase 10D reference stub, unenforced), `app/core/db.py` (7 new indexes), `server.py` (router registration).

### 3. IntakeSubmission model
Implemented per §3 of the authorization prompt in full — all listed fields present (`intake_number`, `source_type`/`source_reference`, contact fields, `status`, `priority`, due date/installation fields, `assigned_user_id`, `quote_id`/`order_id`, `questionnaire_submission_ids`, `file_ids`, `proof_required`/`approval_required`, `internal_notes`/`customer_notes`, `metadata`, `idempotency_key`, all timestamps, actor ids). All cross-record fields are string id references — no live record is ever copied. No file bytes/base64 field exists anywhere on the model.

### 4. Multi-item intake structure
`IntakeItem` embedded list on the submission (mirrors the existing `SignatureRequest.required_signers` embedded-list precedent — no extra collection needed for something that never needs independent revisioning). Each item carries its own stable `id`, category/measurements/`category_inputs`, canonical EC9 references (`saved_item_id`/`material_profile_id`/`pricing_component_ids`), `file_ids`, proof/approval flags, and conversion-tracking fields (`conversion_status`, `quote_line_item_id`, `order_item_id`). **No pricing field exists anywhere on `IntakeItem`** — confirmed by test (`test_multi_item_intake_and_source_tracking` asserts `unit_price_cents` absent).

### 5. Source types
`internal_user | customer_portal | public_intake_link | questionnaire | email_import | quote | order | saved_template | api | other` — normalized `Literal`, stored as-is. `email_import` behavior explicitly NOT implemented (value only). `saved_template` accepted with a free-form, unvalidated `source_reference` string — satisfies "templates beyond contracts required by 10A" boundary without a `TemplateDefinition` model.

### 6. Status lifecycle
`draft → submitted → under_review → {needs_information | accepted | rejected} → {converted_to_quote | converted_to_order}`, plus `cancelled` reachable from every non-terminal state. Implemented exactly as the smallest practical set from the preflight/authorization, mirroring `proofs_service.ALLOWED_TRANSITIONS`. Every transition is backend-validated (`IntakeError("invalid_transition")` → HTTP 400), reason-required on `rejected`/`cancelled`, every transition writes `record_audit`. Rejected/cancelled records are never deleted (verified by test).

### 7. Conversion contracts
`transition(target="converted_to_quote"|"converted_to_order")` validates the referenced Quote/Order exists in-tenant before accepting the status change — it does **not** create a Quote/Order (that write remains Phase 10F scope). `preview_quote_line_item`/`preview_order_item`/`build_conversion_preview` are pure, non-persisting functions exposed via `GET /intake/{id}/conversion-preview` — they compute the exact shape Phase 10F's real create-line-item call will need (category, description, quantity, `category_inputs`, canonical refs) with **no price field**, proving the contract without building the workflow.

### 8. File and questionnaire integration
Every `file_ids` entry (submission- and item-level) is validated against `db.files` with `tenant_id` match and `archived != True` — reuses the existing `/files/upload` endpoint and `FileRecord`, zero new storage code, zero inline/base64 storage anywhere. `questionnaire_submission_ids` validated against `db.customer_intakes` (the existing EC6 questionnaire-answer store) with the same tenant-scoped-existence check.

### 9. Future markup references (Phase 10C contract only)
`IntakeItem.visual_markup_id` / `.rendered_preview_file_id` and `IntakeSubmission.visual_markup_ids` — plain optional string/id fields, unenforced, no model/service/UI for `VisualMarkup` exists. Fabric.js/`pdfjs-dist` were **not** installed (per explicit instruction).

### 10. Future Decision Room references (Phase 10D+ contract only)
`IntakeSubmission.decision_room_id` and — per the authorization prompt's explicit "an intake, Quote, Order, or Order Item should be able to reference a future DecisionRoom ID" — `decision_room_id: Optional[str] = None` added additively to `Quote`, `Order`, and `OrderItem`. No `DecisionRoom`/`DecisionOption`/`CustomerDecision` model, service, router, or endpoint exists. No fake/stub endpoint was created.

### 11. Security and permissions
New `intake:read`/`intake:write` permissions (both granted to `staff` role, all of `Perm` already granted to `owner`/`admin`). Verified by test: cross-tenant customer/quote/order/file/questionnaire references all rejected with 404; guessed intake ids on GET/list rejected (tenant-scoped query, 404); duplicate submissions prevented via a unique partial index on `(tenant_id, idempotency_key)` plus a service-level pre-check (race-safe — `DuplicateKeyError` falls back to a re-fetch, mirroring the `payments` idempotency pattern); `serialize_for_customer()` strips `internal_notes`/`assigned_user_id`/`assigned_team_id`/`created_by_user_id`/`updated_by_user_id`/`submitted_by_user_id` (unit-tested directly — not yet wired to a route, since no customer-facing route exists in 10A). No public-token or customer-facing submission route was created (both explicitly deferred).

### 12. Database indexes
`intake_submissions`: `id` (unique), `(tenant_id, intake_number)` (unique), `(tenant_id, status)`, `(tenant_id, customer_id)`, `(tenant_id, quote_id)`, `(tenant_id, order_id)`, `(tenant_id, assigned_user_id)`, `(tenant_id, created_at desc)`, `(tenant_id, idempotency_key)` (unique, partial on string type) — exactly the indexes named in the authorization prompt, no speculative additions.

### 13. Targeted test count and result
**18/18 passed** (`tests/test_ec10_phase10a_intake_contracts.py`) covering every bullet in §14 of the authorization prompt. **Directly-affected existing tests re-run and green (40/40 unaffected):** `test_permissions_scope.py`, `test_ec2_permissions.py`, `test_orders_ec3.py`, `test_quotes_ec3.py`, `test_terminology_guard.py`, `test_upload_validation.py`, `test_activity.py`.

### 14. Frontend compile result
Not applicable — **no frontend files were changed** in Phase 10A (backend contracts only; the authorization prompt's Phase 10A frontend allowance was optional ("only if required by the preflight") and was not required to validate this architecture).

### 15. Known gaps (all intentional, deferred to their named phase)
- No customer-facing or public-token intake submission route (Phase 10B/10E).
- No email-import behavior (explicitly out of scope for 10A).
- `assigned_team_id` field exists but is unenforced — no Team/Task grouping concept exists yet.
- Conversion contracts validate/preview only — no live Quote/Order write path yet (Phase 10F).
- `serialize_for_customer()` exists but is unwired (no route calls it yet — correct, since no customer route exists).

### 16. The three owner decisions from the EC10 preflight §10 — reproduced verbatim
| # | Issue | Why it matters | Recommended option | Alternative | Can implementation proceed around it? |
|---|---|---|---|---|---|
| 1 | Does a customer "Select" in the Decision Room require internal staff acceptance before the live Quote/Order Item changes, or can it apply immediately? | Directly determines whether Phase 10F needs a staff review queue or can be a straight-through pipe. The EC10 spec text says "only through an explicit controlled action" — read most naturally as **staff acceptance required**, but the owner should confirm this is not meant to allow direct customer-driven auto-apply for low-risk selections (e.g. size-only changes). | **Require an explicit staff/controlled acceptance step for every decision, no auto-apply exceptions** (matches spec text literally, matches `CustomerIntake` precedent, safest default). | Allow tenant-configurable auto-apply for specific low-risk option types later (P2, not EC10). | Yes — Phase 10A-10E can be built without this being decided (options/comparison/selection capture doesn't need the answer); Phase 10F (the actual Quote/Order Item write) is genuinely blocked without it. |
| 2 | Can customers annotate/draw directly on markup, or is markup staff-only with customer view/comment-only? | Changes Phase 10C/10E scope materially (customer-facing Fabric.js editor vs. read-only viewer + comment pins). Spec §3 lists "Customer and staff comments anchored to markup points" (implying customers comment, not necessarily draw) but §2/§3 elsewhere is ambiguous about customer-authored shapes. | **Staff draws/authors markup; customers can only add anchored comments/pins (not freeform shapes) and approve/acknowledge a version** — safer, matches "Approval or acknowledgement per version" language, avoids customers accidentally corrupting a proof-quality asset. | Allow customers full drawing parity with staff. | Yes for 10C (staff-side editor is needed regardless); blocks the exact scope of 10E's customer-facing markup UI. |
| 3 | Should the "Wrap Command Center"/"Wrap Lab" naming correction register item interact with EC10 at all (e.g. vehicle-graphics intake)? | Just a scope-boundary confirmation — Wrap Lab is EC15 (held, unauthorized). | **No — EC10 intake/markup/decision-room applies generically to all categories including vehicle graphics pricing (EC9 already supports it), but any Wrap-Lab-*specific* workflow (e.g. vehicle diagrams) stays out of EC10 and waits for EC15.** | — | Yes, does not block any EC10 phase; stated here only for completeness per the spec's request to flag scope boundaries. |

None of these three were resolved or blocked on in Phase 10A, as instructed — reproduced here unresolved, for the owner's future decision before Phase 10E (#2) and Phase 10F (#1) begin.

### 17. Confirmation
No `testing_agent` was invoked. No full backend or frontend regression suite was run. Only the 18 new Phase 10A tests + 40 directly-affected pre-existing tests (permissions/EC3 orders+quotes/terminology guard/upload validation/activity) were executed — all green.

### 18. Confirmation
Phase 10B (Quick/Detailed internal intake UI), visual markup (10C), Customer Decision Room (10D/10E), decision-to-order integration (10F), and templates beyond the minimal `source_type="saved_template"` contract (10G) were **not started**. No frontend UI was built.
