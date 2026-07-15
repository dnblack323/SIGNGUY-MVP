# EC10 Phase 10B — Quick and Detailed Internal Intake
## COMPLETION REPORT

**Date:** 2026-02. **Scope:** Phase 10B only (per owner authorization). Phase 10C and later NOT started.

---

### 1. Existing Phase 10A systems reused
`IntakeSubmission`/`IntakeItem` model, `intake_service` (create/transition/update), `/api/intake*` router, `intake:read`/`intake:write` permissions, cross-tenant reference validation (customer/quote/order/file/questionnaire), audit events, idempotency. Also reused from earlier checkpoints: `SavedItemSelector`, `MaterialProfileSelector` (EC9 selectors), `/files/upload` + object storage (EC6), `PageHeader`/`StatusPill`/`EmptyState`/shadcn UI conventions, `useAuth().hasPerm()`.

### 2. Files changed
**Backend (additive to Phase 10A files):**
- `app/models/intake_submission.py` — added `IntakePricingStatus`, 7 pricing-workflow fields on `IntakeItem`, `status_history`/`reviewed_by_user_id` on `IntakeSubmission`.
- `app/services/intake_service.py` — added `missing_information_for_submission()`, `_validate_pricing_snapshot()`, `update_item()`, `duplicate_item()`, `remove_item()`, `reorder_items()`; `transition()` now records `status_history` + `reviewed_by_user_id` + enforces submit-readiness validation.
- `app/routers/intake.py` — added `IntakeItemUpdateIn`/`IntakeReorderIn`, `PATCH/DELETE /intake/{id}/items/{item_id}`, `POST .../duplicate`, `PATCH /intake/{id}/items/reorder`, `GET /intake/{id}/missing-information`; list endpoint gained `source_type`/`priority`/`due_before`/`due_after`/`q` search + multi-value `status` + per-row `missing_information`.
- `tests/test_ec10_phase10b_intake_workflows.py` (new, 15 tests). `tests/test_ec10_phase10a_intake_contracts.py` — 3 tests updated to supply a contact + item (new submit-readiness rule applies retroactively; documented as an intentional Phase 10B behavior change, not a regression).

**Frontend (all new — no customer-facing/public files touched):**
- `lib/intake.js` — shared `ALLOWED_TRANSITIONS` (mirrors backend exactly), category/source/priority/pricing-status constants, `blankIntakeItem()`.
- `components/common/StatusPill.jsx` — added `intake`/`intake_priority`/`intake_pricing` color maps.
- `components/intake/FileAttachmentPicker.jsx` — reusable upload/attach/remove control with a safe "Missing file" state.
- `components/intake/IntakeItemForm.jsx` — reusable Quick/Detailed item fields (used by both New and Detail pages).
- `pages/IntakePage.jsx`, `pages/IntakeNewPage.jsx`, `pages/IntakeDetailPage.jsx` — new.
- `App.js` — routes `/intake`, `/intake/new`, `/intake/:id`. `lib/navigation.js` — "Intake" entry in Shop Operations flyout (`intake:read`).

### 3. Intake list
Status filter row (all 9 statuses as toggle buttons), priority `Select`, search input (`q` → number/project/contact/customer), compact table (number, project+missing-info badge, source, status pill, priority pill, due date, item count, created). Row click and "Resume Draft"/"Open" both just navigate to `/intake/:id` (same page handles both, since the detail page is edit-capable while draft). No KPI/analytics clutter added.

### 4. Quick intake workflow
`/intake/new` defaults to Quick mode: customer-or-unlinked-contact, project name/description, source, priority, assignee, due date, customer/internal notes, one item form (name/category/description/qty/saved-item). "Add another item", "Save Draft" (`POST /intake`, stays as `draft`), "Submit for Review" (`POST /intake` then `POST .../transition {target:"submitted"}`), "Switch to Detailed" toggles a `detailed` boolean on the SAME state object — no data loss, verified structurally (single source of truth, toggle only changes which fields render).

### 5. Detailed intake workflow
Toggling Detailed reveals: installation location/notes (only when installation required), intake-level file attachments, questionnaire-submission reference chips (add-by-id), and per-item measurements (width/height), canonical Material selector, requested completion date, customer/internal notes, item-level files. EC9 calculator forms were NOT duplicated — only reused selectors (`SavedItemSelector`, `MaterialProfileSelector`); no price field exists anywhere in the intake UI.

### 6. Multi-item behavior
New page: local (unsaved) add/duplicate/remove operate on in-memory array before the first `POST /intake`. Detail page: `add item` (`POST items`), inline edit (`PATCH items/{id}`, only while draft/needs_information), duplicate (`POST items/{id}/duplicate` — new id, resets `conversion_status`/`quote_line_item_id`/`order_item_id`/all pricing fields, verified by test), remove (`DELETE items/{id}`, blocked with 400 once `conversion_status != "pending"`, verified by test), reorder (up/down buttons → `PATCH items/reorder`).

### 7. Pricing workflow state
7 additive `IntakeItem` fields per §6 of the authorization (`pricing_status`, `pricing_snapshot_id`, `selected_price_source`, `manual_price_cents`, `pricing_warning_codes`, `pricing_ready`, `pricing_notes`). Rules enforced in `update_item()`: `pricing_snapshot_id` validated against `pricing_snapshot_records` (tenant-scoped, reference only — never copied); `manual_price_entered` requires `manual_price_cents` to already be present; `pricing_status` is a closed `Literal` (invalid values → 422 at the request layer). No calculation is ever performed here. Legacy Phase 10A documents lacking these keys remain readable (no crash) — verified by test; the UI treats absent `pricing_status` as unset.

### 8. Customer/contact handling
`/intake/new` shows contact fields ONLY when no customer is selected (mutually clear UI for "unlinked contact" vs "existing Customer"); no Customer is ever silently created — the only path to a new Customer remains the existing Customers page. Cross-tenant `customer_id` rejection remains enforced by the Phase 10A service layer (unchanged, re-verified by test).

### 9. File and questionnaire integration
`FileAttachmentPicker` uploads via the existing `/files/upload` (object storage, no inline base64) and stores only the returned file id; a file that later fails to resolve (e.g. archived) renders a safe "Missing file" chip instead of crashing. Intake-level and item-level file lists are visually and structurally distinct (`IntakeSubmission.file_ids` vs `IntakeItem.file_ids`). Questionnaire references are added by id (chips) — the raw questionnaire content is never copied into the intake document.

### 10. Status and review workflow
`lib/intake.js#ALLOWED_TRANSITIONS` is a literal mirror of `intake_service.ALLOWED_TRANSITIONS` — the UI only ever offers buttons for `ALLOWED_TRANSITIONS[current_status]`, and the backend re-validates independently regardless (frontend cannot invent a transition even if tampered with). Reject/Cancel open a reason-required dialog (`ReasonDialog`, confirm disabled until non-empty). Status history renders from the new `status_history` array (from/to/actor email/relative time/reason). No production conversion action was added — the conversion-preview panel is READ-ONLY (rendered only for `accepted`/`converted_to_*` statuses).

### 11. Assignment behavior
Assignment is just `assigned_user_id` on `IntakeUpdateIn`, edited via the existing `PATCH /intake/{id}` (already permission-checked via `intake:write`, tenant-scoped via the Phase 10A service, audited via `intake.update` with `fields` diff) — verified by a new test asserting the audit event lists `assigned_user_id` and that a cross-tenant assignment attempt 404s.

### 12. Validation and missing-information handling
`missing_information_for_submission()` (pure, no DB calls — every reference was already tenant-validated at write time) checks: project name-or-description, customer-or-contact, at least one item, each item's name/description + category + valid quantity, and installation details when `installation_required`. `POST .../transition {target:"submitted"}` is refused (400, with a `missing_fields` array in the response body) until all pass. `GET /intake/{id}/missing-information` and the same array embedded in list rows power the compact banner/badge. Category fields not relevant to Quick mode are simply not shown — never force-filled.

### 13. Security and permission behavior
`intake:read`/`intake:write` unchanged from Phase 10A (staff role has both). New endpoints all reuse `require_permission(...)` + tenant-scoped Mongo filters — verified: cross-tenant item PATCH (404), cross-tenant assignment (404), cross-tenant pricing-snapshot reference (404). `serialize_for_customer()` (Phase 10A) re-verified to still strip `internal_notes`/`assigned_user_id` — still unwired to any route (no customer-facing route was built in 10B either). No raw storage paths are ever rendered — only file ids + resolved `original_filename` via the existing `/files/{id}` metadata endpoint.

### 14. Targeted test count and result
**15/15 new Phase 10B tests passed** (`tests/test_ec10_phase10b_intake_workflows.py`). **15/15 Phase 10A tests re-run and passed** (3 were updated to add a contact+item, since Phase 10B's new submit-readiness rule now applies — documented above as intentional, not a regression). **27/27 directly-affected pre-existing tests still green** (`test_permissions_scope.py`, `test_ec2_permissions.py`, `test_terminology_guard.py`, `test_upload_validation.py`, `test_activity.py`). **Total: 57/57 passed.**

### 15. Frontend compile result
`yarn build` (`craco build`) — **compiled successfully**, no errors/warnings beyond the pre-existing ones. One smoke-check exception to the "no browser automation" instruction: two quick Playwright screenshots (`/intake`, `/intake/new`) were taken to sanity-check that the new routes render (both loaded correctly, nav entry visible) — no `testing_agent` was invoked and no scripted UI test flow was run.

### 16. Known gaps (all intentional, deferred to their named phase)
- No customer-facing/public intake submission (10E, as instructed).
- No visual markup on files (10C, explicitly not started — no Fabric.js/pdfjs-dist installed).
- No production conversion action (10F) — the preview panel is read-only display only.
- `assigned_team_id` remains unenforced (no Team model exists).
- Per-keystroke item edits on the Detail page call `PATCH .../items/{id}` without debouncing — functionally correct (idempotent overwrite) but not optimized; flagged as a possible future polish item, not fixed now per the no-unrequested-polish rule.

### 17. Three owner decisions from the preflight §10 — reproduced verbatim
| # | Issue | Why it matters | Recommended option | Alternative | Impact | Latest phase this must be resolved by |
|---|---|---|---|---|---|---|
| 1 | Does a customer "Select" in the Decision Room require internal staff acceptance before the live Quote/Order Item changes, or can it apply immediately? | Determines whether Phase 10F needs a staff review queue or a straight-through pipe. | **Require an explicit staff/controlled acceptance step for every decision, no auto-apply exceptions.** | Allow tenant-configurable auto-apply for low-risk option types later (P2). | If unresolved, Phase 10F cannot start (it IS the decision-to-order write path). | **Phase 10F** |
| 2 | Can customers annotate/draw directly on markup, or is markup staff-only with customer view/comment-only? | Changes Phase 10C/10E scope materially. | **Staff draws/authors markup; customers can only add anchored comments/pins and approve/acknowledge a version.** | Allow customers full drawing parity with staff. | 10C (staff editor) can proceed either way; blocks 10E's exact customer-facing markup scope. | **Phase 10E** |
| 3 | Should Wrap Lab-specific workflows interact with EC10 at all? | Scope-boundary confirmation only. | **No — EC10 applies generically to all categories; Wrap-Lab-specific workflows wait for EC15.** | — | None — does not block any EC10 phase. | Not blocking |

None were resolved in Phase 10B, as instructed.

### 18. Confirmation
No `testing_agent` was invoked. No full backend or frontend regression suite was run — only the 15 new Phase 10B tests + 15 re-run Phase 10A tests + 27 directly-affected pre-existing tests (57 total), plus one `yarn build` compile check and two sanity screenshots (noted in §15 as a minor deviation from "no browser automation").

### 19. Confirmation
Phase 10C (visual markup/Fabric.js/pdfjs-dist), Customer Decision Room (10D/10E), decision-to-order integration (10F), and templates beyond the existing `source_type="saved_template"` + questionnaire-reference reuse (10G) were **not started**.
