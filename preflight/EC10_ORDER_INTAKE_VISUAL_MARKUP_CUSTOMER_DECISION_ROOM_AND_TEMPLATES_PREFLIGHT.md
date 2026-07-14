# EC10 — Order Intake, Visual Markup, Customer Decision Room, and Templates
## PREFLIGHT ONLY — NO IMPLEMENTATION AUTHORIZED

**Date:** 2026-02
**Controlling document:** `/app/specs_pack/extracted/EC10_Order_Intake_Visual_Markup_Decision_Room_and_Templates.docx`
**Authority chain:** EC10 spec (planning authority, no implementation authorization) → `/app/memory/PRD.md` → `/app/memory/progress_register.md` → `/app/memory/checkpoint_reference_table.md` → EC9 closure record → current repository.
**Status:** EC9 formally accepted/closed by owner (2026-02). This document is the EC10 preflight only. **No production code was changed. No tests were run. No testing_agent was invoked.**

---

## 1. Existing systems found (inventory)

| System | Files | Current behavior |
|---|---|---|
| Customers | `models/customer.py`, `routers/customers.py` | Canonical customer record. No intake/decision fields. |
| Quotes / Quote Line Items | `models/quote.py`, `models/quote_line_item.py`, `routers/quotes.py`, `services/quote_revisions.py`, `services/quote_conversion.py` | Revisioned, backend-totaled, EC9 pricing fields present. No markup/decision/intake linkage fields. |
| Orders / Order Items | `models/order.py`, `routers/orders.py` | Same pricing integration as Quotes. `artwork_status`/`proof_status`/`customer_supplied_artwork`/`design_required` fields exist on `OrderItem` but nothing currently writes/reads them from a UI — dead/unused fields today. |
| Files / Attachments | `models/file.py` (`FileRecord`, `Attachment`), `routers/documents.py` (`/files/*`) | One upload endpoint, SHA-256 de-dupe, tenant-scoped storage key, polymorphic `Attachment` (customer/quote/order/order_item/work_order/invoice/email/generic), `visibility` (internal/customer_visible), archive (soft), authenticated view/download proxy. **No UI anywhere currently calls `/files/upload` from Order/Quote/Customer detail pages** — the endpoint exists, wired attachment lists do not. |
| Documents (Asset Library layer) | `models/document.py`, `document_link.py`, `document_share.py`, `routers/documents_meta.py`, `services/documents_service.py` | Metadata/versioning layer over `FileRecord` (title, category incl. `customer_intake`, `visibility`, version history). `DocumentLink` = polymorphic many-to-many link with a `portal_visible` boolean gate. Reused as-is in EC8 for Equipment/Training. |
| Object storage | `services/storage.py`, `services/upload_validation.py` | Emergent Object Storage, private-by-default, backend-proxied get/put, tenant-path-scoped. MIME allowlist + magic-byte check + 25MB cap + filename sanitize + sha256. Images + PDF already allowed. **No inline base64 storage anywhere in the codebase — confirmed.** |
| Proofs | `models/proof.py` (`Proof`, `ProofVersion`), `routers/proofs.py`, `services/proofs_service.py`, `components/proofs/ProofsPanel.jsx` | Immutable version history (1 file per version), 7-state transition graph (`ALLOWED_TRANSITIONS`), reason-required on `changes_requested`/`cancelled`, mounted on Order Detail. Parent types today: `order`/`order_item`/`work_order` only (no `quote` parent type yet). |
| Approvals | `models/approval.py`, `routers/signatures.py` (`approvals_router`) | Immutable, dual-parent (`quote_revision`/`proof_version`/`contract`/`order_item`/`work_order_summary`), 3 actions (approve/request_changes/decline), `actor_type` distinguishes `staff`/`portal_customer`/`public_token`. Never silently changes pricing/status — the calling router decides the operational transition. **This is the exact pattern the Decision Room's "Select/Reject/Request Change" must reuse, extended with 2 new parent types (`decision_option`, `decision_room`) and 2 new actions (`select`, `save_for_later` — "ask a question" is better modeled as a comment, not an Approval).** |
| Signatures | `models/signature.py`, `routers/signatures.py`, `services/approvals_signatures_service.py` | `SignatureRequest` (required signers list, 5-state) + `Signature` (drawn/typed, IP/UA, optional public-token binding). Parent types: `proof`/`contract`/`work_order_summary`/`quote`/`document`. Reusable as-is for EC10's "in-person signature capture" requirement — no new signature model needed. |
| Customer Portal (staff-facing shell) | `portal/PortalApp.jsx`, `routers/portal_customer.py`, `routers/portal_auth.py`, `services/portal_identity.py` | Read-only list pages (Quotes/Orders/Invoices/Proofs/Documents/Messages) + Profile + Invoice Pay. Magic-link + password login, JWT with `sub_scope="portal"`, 5 permission-bundle presets. **No customer-facing upload, markup, or decision UI exists today — this is 100% new frontend surface for EC10.** |
| Public token pages | `public/PublicApp.jsx`, `routers/public_actions.py`, `models/public_action_token.py` | `PublicActionToken` (single-purpose, hashed, expiring, `single_use`, optional `audience_email` binding). Existing actions: `proof_approve`, `proof_request_changes`, `sign`, `quote_view`, `invoice_view`, `invoice_pay`, `customer_intake`. **Adding `decision_room_view`/`decision_room_respond` as 2 new enum values is additive and fits the existing model exactly — no new token system needed.** |
| Public/staged intake | `models/public_intake.py` (`QuoteRequest`, `CustomerIntake`), `routers/public_actions.py` | `QuoteRequest` = anonymous lead capture (rate-limited, spam-protected). `CustomerIntake` = staff-issued token-scoped questionnaire to a known Customer; response stored raw, a server-computed `staged_changes` diff is produced, **nothing is ever silently applied to the authoritative Customer** — staff must explicitly apply named fields. **This staged-diff pattern is the direct precedent for how Decision Room customer selections must reach the Quote/Order (never a direct write).** |
| Templates | `models/pricing_saved_item.py` (`PricingSavedItem`), `services/starter_defaults.py`, `models/email.py` (`EmailTemplate` Literal, 5 fixed values, no editable template *records*) | **No general-purpose, tenant-editable template system exists.** `PricingSavedItem` is the closest analog (reusable "item" with save-as-new/update/save-as-variation lifecycle) but is pricing-specific. `EmailTemplate` is a hardcoded enum, not stored/editable content. |
| Notifications / Email | `services/notifications.py`, `services/email.py`, `models/notification.py` | In-app notify + fan-out-to-owners helper; SendGrid-backed email with fail-closed webhook. Reusable for EC10 (e.g. "customer responded in Decision Room" → `notify_tenant_owners`). |
| Audit / Activity | `services/audit.py`, `services/activity.py` | `record_audit` mandatory on every write (non-optional actor). `record_activity_with_audit` is the standard combined helper. EC10 must use these exactly as-is — no parallel audit system. |
| Permissions | `core/permissions.py` (`Perm` enum) | Explicitly documents (line 12-14) that "new module namespaces are declared here so future checkpoints can introduce routes without a scattered enum" — confirms adding `intake:*`, `markup:*`, `decision_room:*`, `template:*` namespaces in EC10 is expected practice, not a deviation. |
| Canvas / annotation / drawing library | — | **None installed.** `package.json` has no `fabric`, `konva`, `react-konva`, `react-signature-canvas`, or PDF-annotation package. `react-day-picker`, `react-hook-form`, `react-resizable-panels` are the only non-Radix/non-Shadcn UI-adjacent libs. A library decision is genuinely required (see §4). |

**No duplicate pricing engines, no disconnected forms, no unregistered routers were found in the areas inspected.** The only "dead" fields found are `OrderItem.artwork_status`/`proof_status`/`customer_supplied_artwork`/`design_required` (declared in EC3, never wired to any UI) — EC10 is the natural checkpoint to finally wire them, not a conflict.

---

## 2. Reusable components and services (confirmed safe to extend, not replace)

- File upload + storage + validation pipeline (`documents.py` + `storage.py` + `upload_validation.py`) — reused as-is for intake camera/image/PDF/document capture.
- `Document`/`DocumentVersion`/`DocumentLink` — reused for markup export/share and portal-visibility gating.
- `Proof`/`ProofVersion` + `ALLOWED_TRANSITIONS` pattern — reused/extended (new parent type `quote`; markup versions can be a `ProofVersion`-shaped concept OR a dedicated model, see §8).
- `Approval` dual-parent immutable pattern — reused/extended for Decision Room Select/Reject/Request-Change.
- `SignatureRequest`/`Signature` — reused as-is for in-person signature capture bound to intake content.
- `PublicActionToken` — extended with 2 new `PublicAction` enum values for Decision Room public access.
- `CustomerIntake` staged-diff-never-silent-overwrite pattern — the architectural template for how ANY customer-originated data (intake answers, decision selections) must reach authoritative Quote/Order/Order Item records.
- `record_audit` / `record_activity_with_audit` / `notifications.notify_tenant_owners` — reused as-is, no parallel audit/notify system.
- `next_number` sequence service — reused for any new numbered entity (e.g. `DecisionRoom`, `IntakeSubmission`).

---

## 3. Current intake paths (mapped)

| Path | Exists today? | Flows into canonical Quote/Order/Order Item? |
|---|---|---|
| Staff creates Quote/Order manually (Quick or Detailed via `LineItemDialog.jsx`) | ✅ Yes | ✅ Yes — this is the only fully-wired intake path today. |
| Calculator-created item (`PricingCalculatorPage.jsx` → "Add to Quote/Order") | ✅ Yes | ✅ Yes (EC9 Phase 9F). |
| Saved-item-created item | ✅ Yes | ✅ Yes (EC9). |
| Anonymous public Quote Request (`QuoteRequest` model) | ✅ Yes | ⚠️ Partial — creates a standalone `quote_requests` row; a human must manually review and create a real Quote. No auto-conversion, no file/photo capture beyond a raw `file_ids` list with **no upload endpoint wired to populate it** (the public form has no file input at all). |
| Staff-issued Customer Intake questionnaire (`CustomerIntake` model) | ✅ Yes (backend only) | ⚠️ Partial — targets the **Customer** record only (staged-changes diff), not a Quote/Order/Order Item. No frontend page exists to author `prompt_config` or view `staged_changes` for staff review/apply — the apply step itself (`applied_fields`) has no router endpoint either. |
| Customer-originated Order Item request / measurement / photo capture | ❌ Does not exist | — |
| Portal-originated Order Item change/decision request | ❌ Does not exist | — |
| Camera/photo/PDF capture bound to a specific Order Item (vs generic Attachment) | ❌ Does not exist (generic `Attachment.parent_type="order_item"` exists but no UI surface uses it) | — |
| Measurements-with-units-and-source, voice-to-note | ❌ Does not exist | — |

**Duplication/disconnection found:** `QuoteRequest.file_ids` and `CustomerIntake.file_ids` both assume uploads happen through the *existing* `/files/upload` endpoint (correct — no parallel upload path was invented), but neither the public quote-request form nor any staff Customer Intake authoring page currently calls it. This is a genuine gap to close in Phase 10A/10B, not a duplicate system to remove.

---

## 4. Visual markup findings

**Nothing exists today:** no image/PDF annotation, canvas, drawing, arrows, pins, callouts, coordinate-anchored comments, before/after, or markup export anywhere in the repository (confirmed via `package.json` + component search).

**Storage/versioning implication:** the existing `Document`/`DocumentVersion` non-destructive-versioning pattern (never overwrite `current_file_id` in place — always insert a new version row) is exactly the right shape for "original preserved separately, non-destructive versions." A markup version should store BOTH:
1. A structured JSON description of the annotation (shapes/arrows/text/pins with coordinates, author, timestamp) — enables re-editing and `/explain`-style deterministic reconstruction, consistent with EC9's snapshot philosophy.
2. A flattened rendered image (PNG) of that version — enables fast display, proof generation, and DocuLink-style export without needing the canvas library client-side.

Both should reference the **original** untouched `FileRecord` via a stable `source_file_id` that is never itself replaced.

**Library decision (genuinely required — 2 viable choices):**

| Option | Pros | Cons |
|---|---|---|
| **A — Fabric.js (recommended)** | MIT/open-source, mature object model (arrows/text/shapes/images out of the box), stable object IDs for layers/authorship, wide React integration precedent, works on images directly; for PDFs, render each page to an image via `pdfjs-dist` (already MIT, no license) first, then markup that image like any other image. | No native PDF annotation — PDFs are handled as "render page → image → markup," which is acceptable per spec (§3 says "images and PDFs," not "PDF-native annotation objects"). |
| **B — react-konva** | Also MIT, React-idiomatic component API, good performance for many shapes. | Materially the same capability as Fabric for this use case; no PDF-native support either; less precedent for "arrow/pin" annotation-specific helpers out of the box (more manual shape math). |

**Recommendation: Fabric.js + `pdfjs-dist`** for Phase 10C. This is a technical implementation detail Emergent can decide safely (per EC10 spec's own instruction not to raise routine technical choices as owner decisions) — flagged here for visibility only, not as a blocking question.

---

## 5. Customer Decision Room findings

**Confirmed:** this is genuinely new — no options/comparison/selection model exists anywhere. It must be additive alongside Proofs/Approvals/Pricing, never a fork of any of them.

- **Reusable:** `Approval` model's dual-parent/immutable/actor-typed pattern (extend, don't replace) for the Select/Reject decision record itself; `Proof`/`ProofVersion` versioning pattern for "Decision Room remains readable after the Order changes; prior versions are historical" (a `DecisionRoom` should be an immutable-history, current-pointer entity exactly like `Proof`); `PublicActionToken` + portal-JWT dual access (both are already supported patterns in this codebase — token for one-off customer links, portal login for returning/logged-in customers) satisfies "how Decision Room access should be tokenized or authenticated" without inventing a third auth mechanism.
- **New model required:** Yes — a `DecisionRoom` (parent = quote or order or order_item) + `DecisionOption` (side-by-side cards: label, price snapshot ref, included/excluded scope, lead time, warranty notes, proof/mockup ref) + `CustomerDecision` (append-only: select/reject/ask_question/request_change/save_for_later, per-option, with customer/user/date/pricing-snapshot-at-decision-time). `Approval` is the right model for the *authorization* half (staff acknowledging/acting on a decision) but not for the *options themselves* — options are structured comparison data the existing model has no field for.
- **Pricing snapshot integrity:** each `DecisionOption` must carry its own frozen price (reusing EC9's `PricingSnapshotRecord`/embedded-snapshot pattern — "options may have different pricing snapshots" is already architecturally supported by EC9, nothing new needed there).
- **Selection → Quote/Order update:** must follow the `CustomerIntake.staged_changes` precedent exactly — a customer "Select" NEVER auto-writes the Quote Line Item/Order Item. It creates an audited `CustomerDecision` row; a **separate, explicit staff/controlled action** (mirroring `CustomerIntake.applied_fields`) performs the actual Quote/Order Item update. This satisfies the spec's "Final selection can update a Quote or Order Item only through an explicit controlled action" verbatim.
- **Expired links:** reuse `PublicActionToken.expires_at`/`revoked` exactly as Proofs/Signatures already do — no new expiry mechanism.
- **Internal visibility of unresolved actions:** reuse `notifications.notify_tenant_owners` (e.g. "Customer requested a change on Decision Room #12") — no new notification system.

---

## 6. Template-system findings

**Recommended EC10 scope (smallest that satisfies the spec without one giant universal model):**

| Template type | EC10 scope? | Reasoning |
|---|---|---|
| Intake / checklist templates | ✅ In scope | Directly needed by Phase 10A/10B intake forms. |
| Questionnaire templates | ✅ In scope | Directly needed — this is `CustomerIntake.prompt_config` formalized into a reusable, named, tenant-owned definition instead of an ad-hoc dict authored fresh every time. |
| Decision-option templates | ✅ In scope | Directly needed by Decision Room authoring (reusable "Recommended/Best Value/Premium" card shapes per category). |
| Quote / Order / Order Item templates | ⚠️ Deferred candidate, but low-risk to include if time allows — conceptually adjacent to `PricingSavedItem` (Phase 9D), which already covers the "reusable item" need at the line-item level. A full Quote/Order **template** (multiple items + structure) is new. Recommend Phase 10G scope, not earlier. |
| Proof/approval templates | ⚠️ Defer to Phase 10G or later — not required for the completion gate. |
| Production workflow templates | ❌ Defer to EC11 (Production Timeline/Workflow Configuration is EC11's explicit scope — building it here would duplicate that checkpoint). |
| Installation / appointment templates | ❌ Defer to EC12 (Appointments is EC12's explicit scope). |
| Email / SMS templates | ❌ Defer — `EmailTemplate` today is a hardcoded enum; making it an editable record is a Settings/Communications concern better owned alongside EC12/EC19, not EC10's Decision Room focus. |
| Announcement templates | ❌ Not in EC10 scope — Announcements already exist (EC8) as one-off authored content, not templated. |

**Recommended architecture:** one `TemplateDefinition` model with a closed `template_type` enum (`intake`, `questionnaire`, `decision_options`, and later `quote`/`order`/`order_item` when 10G lands) rather than N separate collections — this matches the "smallest architecture" instruction and mirrors how `Document.category` is a single closed enum rather than N document tables. Each `template_type`'s `body` is a `dict[str, Any]` (schema validated per-type in the service layer, exactly like `PricingSavedItem.category_inputs`/`GroupedPricingQuiz` already do). Applying a template to a live record ALWAYS copies values at apply-time (never a live reference) — editing a template later must never alter historical Quotes/Orders/intake submissions already created from it. Tenant-scoped, `active`/archived (soft-restore), versioned via a simple `version: int` bump on edit (no need for a separate version-history collection unless the owner later requires audit-grade template history — flag as a possible P2 refinement, not a blocker).

---

## 7. Canonical proposed data flow

```
Customer or internal user
  → IntakeSubmission (Order/Order Item/Quote association, files via existing /files/upload,
     measurements, notes, questionnaire answers — from a TemplateDefinition or ad-hoc)
  → staff review (missing-information queue) → creates/updates a draft Quote or Order + Order Item(s)
     [owned by: quotes.py / orders.py routers — unchanged from EC3/EC9]
  → uploaded assets get non-destructive VisualMarkup versions
     [owned by: new markup service, reusing Document/DocumentVersion storage pattern]
  → staff authors a DecisionRoom with 1..N DecisionOptions (each with its own frozen pricing snapshot,
     reusing EC9 PricingSnapshotRecord)
     [owned by: new decision_room service]
  → Customer Decision Room (portal login OR public token)
     → customer: select / reject / ask_question / request_change / save_for_later
        → CustomerDecision row (append-only, audited)
           [owned by: new decision_room service, reusing Approval-style actor typing]
  → internal acceptance (explicit controlled action — staff reviews CustomerDecision,
     applies it to the live Quote Line Item / Order Item)
     [owned by: quotes.py / orders.py — an ADDITIVE endpoint, not a new pricing path]
  → updated Quote or Order Item (existing EC9 pricing machinery recalculates/snapshots as normal)
  → preserved decision + pricing history (DecisionRoom/CustomerDecision rows are append-only;
     PricingSnapshotRecord already append-only from EC9)
```

Every arrow above already has an audit-event/activity-event precedent to reuse (`record_audit`/`record_activity_with_audit`) — **no frontend-only state transition is proposed anywhere in this flow.**

---

## 8. Proposed models and statuses (smallest viable set)

Recommend **5** new models (not 9 — several spec-suggested concepts collapse into existing or shared models):

| Model | Collapses into existing model? | Notes |
|---|---|---|
| `IntakeSubmission` | New | `{tenant_id, source (staff|portal|public_token), customer_id, quote_id?, order_id?, order_item_id?, measurements[], notes, questionnaire_answers, file_ids[], visibility (internal|portal_visible), status, missing_info_flags[]}` |
| `VisualMarkup` + `MarkupVersion` | New (2 models, mirroring `Proof`/`ProofVersion` 1:1) | `VisualMarkup{source_file_id, parent_type, parent_id, current_version}`; `MarkupVersion{markup_id, version, annotations_json, rendered_file_id, author, created_at}` |
| `DecisionRoom` | New | Mirrors `Proof` shape: `{parent_type (quote|order|order_item), parent_id, status, options: [DecisionOption ids]}` |
| `DecisionOption` | New | `{decision_room_id, label, recommended_tag?, pricing_snapshot_id, included_scope, excluded_scope, lead_time, warranty_notes, proof_ref?}` |
| `CustomerDecision` | New (NOT collapsed into `Approval` — see §5) | `{decision_room_id, option_id?, action (select|reject|ask_question|request_change|save_for_later), actor_type, actor_ref, comment, pricing_snapshot_id_at_decision, created_at}` |
| `ChangeRequest` | Collapses into `CustomerDecision.action="request_change"` + `.comment` | No separate model needed — a request-change IS a `CustomerDecision` row with a comment; avoids a 6th model. |
| `TemplateDefinition` | New | Single model, closed `template_type` enum (§6). |
| `IntakeTemplate` | Collapses into `TemplateDefinition(template_type="intake")` | — |

**Proposed statuses:**
- `IntakeSubmission.status`: `new → reviewed → applied` (+ `rejected`) — mirrors `CustomerIntake` lifecycle.
- `VisualMarkup`: no status; append-only versions (mirrors `Proof`'s version mechanics without needing the full send/view/approve state machine — markup approval is expressed via `CustomerDecision`/`Approval` on top, not duplicated inside markup itself).
- `DecisionRoom.status`: `draft → published → in_review → resolved` (+ `archived`) — mirrors `Proof`'s `draft/sent/...` shape.
- `CustomerDecision`: no status — append-only event log (mirrors `Approval`, which also has none).
- `TemplateDefinition.status`: `active ↔ archived` (soft, restorable — mirrors `PricingSavedItem.active`).

**Terminology requiring owner confirmation before Phase 10A code:** none of the above introduce a "Job Ticket"-style banned term. `DecisionRoom`/`DecisionOption`/`CustomerDecision`/`IntakeSubmission`/`TemplateDefinition`/`VisualMarkup` are all descriptive, spec-aligned names — flagged in §10 only for the owner to confirm naming, not because any conflict was found.

---

## 9. Security and storage findings

- **Object storage confirmed** for all EC10 file paths (reuses `services/storage.py` — no inline base64 anywhere).
- **Cross-tenant asset access:** existing `/files/download`/`/files/view` already enforce `tenant_id` match + storage-path defense-in-depth — EC10 markup/intake endpoints must query through the same tenant-scoped pattern (no new risk if reused correctly; a real risk if a new ad-hoc file-serving path were invented instead — must not happen).
- **Expired public links / guessed tokens:** `PublicActionToken` already hashes at rest (SHA-256), is single-use where appropriate, and expires — extending its enum is safe; inventing a second token scheme for Decision Room would be the actual risk.
- **Markup tampering / customer editing internal notes:** must enforce at the service layer that `internal`-visibility fields (e.g. staff notes, cost data referenced by a `DecisionOption`) are never serialized into any portal/public-token response — follow the exact precedent in `public_view_quote` (`{"_id": 0, "notes_internal": 0}` field-exclusion projection).
- **Untrusted/oversized/unsupported uploads:** already handled by `upload_validation.py` (MIME allowlist, magic bytes, 25MB cap, filename sanitize) — reuse as-is, no new validation system.
- **Deleted source assets / proof replacement / decision replay / duplicate submissions:** the append-only + soft-archive (never hard-delete) pattern already used by `Document`/`FileRecord`/`Proof` must be followed for `IntakeSubmission`/`VisualMarkup`/`CustomerDecision` — a markup's `source_file_id` must never be archived while any `MarkupVersion` still references it (service-layer guard, mirrors nothing new architecturally, just applied to a new model).
- **Unauthorized price changes / customer selection after Quote expiration or after Order approval:** must reuse the exact guard pattern EC9 already enforces on `recalculate-preview` (400 on non-draft/locked documents) — a `DecisionRoom` tied to an expired Quote or a non-draft Order Item must reject new `CustomerDecision` writes (read remains available per spec's "Decision Room remains readable after the Order changes").

**No new object-storage risk identified.** The only genuinely new attack surface is the Decision Room's dual access path (portal JWT OR public token) needing a single shared tenant+parent-scoping check — both mechanisms already exist independently (EC6) and are proven safe; EC10 combines them for one feature for the first time, which is a wiring task, not a new security primitive.

---

## 10. Owner decisions required (genuine blockers only)

| # | Issue | Why it matters | Recommended option | Alternative | Can implementation proceed around it? |
|---|---|---|---|---|---|
| 1 | Does a customer "Select" in the Decision Room require internal staff acceptance before the live Quote/Order Item changes, or can it apply immediately? | Directly determines whether Phase 10F needs a staff review queue or can be a straight-through pipe. The EC10 spec text says "only through an explicit controlled action" — read most naturally as **staff acceptance required**, but the owner should confirm this is not meant to allow direct customer-driven auto-apply for low-risk selections (e.g. size-only changes). | **Require an explicit staff/controlled acceptance step for every decision, no auto-apply exceptions** (matches spec text literally, matches `CustomerIntake` precedent, safest default). | Allow tenant-configurable auto-apply for specific low-risk option types later (P2, not EC10). | Yes — Phase 10A-10E can be built without this being decided (options/comparison/selection capture doesn't need the answer); Phase 10F (the actual Quote/Order Item write) is genuinely blocked without it. |
| 2 | Can customers annotate/draw directly on markup, or is markup staff-only with customer view/comment-only? | Changes Phase 10C/10E scope materially (customer-facing Fabric.js editor vs. read-only viewer + comment pins). Spec §3 lists "Customer and staff comments anchored to markup points" (implying customers comment, not necessarily draw) but §2/§3 elsewhere is ambiguous about customer-authored shapes. | **Staff draws/authors markup; customers can only add anchored comments/pins (not freeform shapes) and approve/acknowledge a version** — safer, matches "Approval or acknowledgement per version" language, avoids customers accidentally corrupting a proof-quality asset. | Allow customers full drawing parity with staff. | Yes for 10C (staff-side editor is needed regardless); blocks the exact scope of 10E's customer-facing markup UI. |
| 3 | Should the "Wrap Command Center"/"Wrap Lab" naming correction register item interact with EC10 at all (e.g. vehicle-graphics intake)? | Just a scope-boundary confirmation — Wrap Lab is EC15 (held, unauthorized). | **No — EC10 intake/markup/decision-room applies generically to all categories including vehicle graphics pricing (EC9 already supports it), but any Wrap-Lab-*specific* workflow (e.g. vehicle diagrams) stays out of EC10 and waits for EC15.** | — | Yes, does not block any EC10 phase; stated here only for completeness per the spec's request to flag scope boundaries. |

**Not escalated as owner decisions (Emergent will decide safely, per the spec's own instruction not to raise routine technical detail):** Fabric.js vs react-konva (§4); single `TemplateDefinition` model vs many (§6); 5-model vs 9-model set (§8); exact permission-string names (`intake:read`, `markup:write`, `decision_room:read/write/respond`, `template:read/write`).

**Rejected-options-remain-visible** and **"save for later" expiry** (both listed as possible decisions in the task) are **not genuine blockers**: the spec's own §4 text ("Decision Room remains readable after the Order changes; prior versions are historical records") already answers "rejected options remain visible = yes, permanently, as history." "Save for later" needs no expiry beyond the parent Quote's own `expires_at` — no separate timer required. Both resolved by re-reading the spec, not escalated.

---

## 11. Test strategy (future — not run in this preflight)

Planned targeted pytest files (one per phase, mirroring the EC9 `test_ec9_phaseXX_*.py` convention):

- `test_ec10_phase10a_intake_contracts.py` — tenant isolation, permission checks on new `intake:*`/`markup:*`/`decision_room:*`/`template:*` perms, `IntakeSubmission` CRUD, Order/Order Item/Quote association validity.
- `test_ec10_phase10b_intake_workflows.py` — Quick vs Detailed intake, multi-item intake, missing-information queue, upload references reuse `/files/upload` correctly (no duplicate upload path), portal-visible vs internal intake fields.
- `test_ec10_phase10c_visual_markup.py` — markup version creation/versioning, original `source_file_id` immutability (edit live markup, re-fetch old version byte-identical — same style of proof EC9 used for pricing snapshots), layer author/timestamp, DocuLink-style export/share visibility allowlist.
- `test_ec10_phase10d_decision_room_authoring.py` — `DecisionRoom`/`DecisionOption` CRUD, per-option pricing snapshot capture, Recommended/Best-Value/etc. tag without hiding price differences (assert raw price always present even when tagged).
- `test_ec10_phase10e_decision_room_portal.py` — side-by-side option retrieval via portal JWT AND via public token (both paths), Select/Reject/Ask/Request-Change/Save-for-later all create `CustomerDecision` rows, expired-token/expired-quote access rejected (read-only history still available), duplicate-submission protection.
- `test_ec10_phase10f_decision_to_order_integration.py` — staff-acceptance step is the ONLY path that mutates a live Quote Line Item/Order Item; a raw `CustomerDecision` never silently changes pricing; pricing snapshot survives later Material/default changes (reuse EC9's exact verification pattern: edit live source after decision, re-fetch, byte-identical).
- `test_ec10_phase10g_templates.py` — `TemplateDefinition` CRUD/archive-restore, apply-to-live-record copies values (never a live reference), editing a template after use never alters historical records already created from it.
- `test_ec10_phase10h_closure_regressions.py` — full backend regression re-run (537+ pre-existing tests) to confirm zero EC0–EC9 regressions, mirroring the EC9 Phase 9H closure methodology exactly.

Frontend: Jest coverage for new components + one `testing_agent_v4_fork` end-to-end pass at Phase 10H closure only (not per-phase, per the owner's own EC9-established cadence and this preflight's minimal-credit instruction).

---

## 12. Recommended Phase 10A–10H breakdown

| Phase | Goal | Files likely affected | Dependencies | Targeted tests | Owner decisions needed | Explicit exclusions |
|---|---|---|---|---|---|---|
| **10A** | Intake architecture + canonical data contracts | New: `models/intake_submission.py`, `models/template_definition.py`. Extend: `core/permissions.py` (new namespaces). | None | `test_ec10_phase10a_*` | None | No UI yet; no markup; no decision room. |
| **10B** | Quick/Detailed internal intake | New: `routers/intake.py`, `services/intake_service.py`. Frontend: intake form on Order/Order Item detail (reusing `/files/upload`). Wire the dead `OrderItem.artwork_status`/`design_required` fields for the first time. | 10A | `test_ec10_phase10b_*` | None | No customer-facing portal intake yet (staff-only in 10B; portal-originated intake deferred to 10E where Decision-Room-adjacent portal work already lands, avoiding two separate portal-UI phases). |
| **10C** | Asset upload + visual markup | New: `models/visual_markup.py`, `services/markup_service.py`, `routers/markup.py`. Frontend: Fabric.js + `pdfjs-dist` markup editor (staff-side). `yarn add fabric pdfjs-dist`. | 10A/10B | `test_ec10_phase10c_*` | **#2 (customer draw rights)** — needed before 10E, not 10C. | No customer-facing markup UI yet (staff-only editor). |
| **10D** | Decision Room models + internal authoring | New: `models/decision_room.py` (`DecisionRoom`, `DecisionOption`, `CustomerDecision`), `services/decision_room_service.py`, `routers/decision_room.py`. Frontend: staff authoring UI on Quote/Order Item detail. | 10A, EC9 pricing snapshots | `test_ec10_phase10d_*` | None | No customer/portal access yet. |
| **10E** | Customer Portal Decision Room experience | Frontend: `portal/DecisionRoomPage.jsx` (side-by-side cards, Select/Reject/Ask/Request-Change/Save-for-later), `public/DecisionRoomAction.jsx` (token path). Extend `PublicActionToken` enum + `routers/public_actions.py`. | 10D | `test_ec10_phase10e_*` | **#1 (auto-apply vs staff acceptance)** must be answered before 10F, informs 10E's UI copy ("pending review" messaging). | No pricing/Order write yet — 10E only records `CustomerDecision`. |
| **10F** | Decision-to-Quote/Order integration | Extend `routers/quotes.py`/`orders.py` with an additive "apply decision" endpoint (mirrors `CustomerIntake.applied_fields` pattern). | 10D, 10E, EC9 `order_pricing.py`/pricing snapshot services | `test_ec10_phase10f_*` | **#1 must be resolved before this phase starts.** | Does not touch EC9's `calculate_pricing()` internals — only feeds it the selected option's inputs, same as any other line-item edit today. |
| **10G** | EC10-scoped templates | `TemplateDefinition` service/router + authoring UI for `intake`/`questionnaire`/`decision_options` types only (per §6 scope table). "Open in Document Creator / Create Custom Template" fallback action. | 10A | `test_ec10_phase10g_*` | None | Quote/Order/Order Item templates, Proof/approval templates, production/appointment/email/SMS templates — all explicitly deferred (§6). |
| **10H** | Validation, testing, closure | Implementation inventory, terminology guard, full backend regression, frontend Jest, `testing_agent_v4_fork`, documentation updates (mirrors EC9 Phase 9H exactly). | All prior phases | `test_ec10_phase10h_*` + full suite | None | No EC11 work started. |

---

## 13. Confirmations

1. **No production code was changed during this preflight.** Only this report file was created under `/app/preflight/`.
2. **No `testing_agent` and no broad backend/frontend test suites were run.** No `pytest`, no `yarn test`/`yarn build`, no screenshot/browser automation was invoked.
3. **EC11 and all later checkpoints were not started, inspected for implementation, or scoped in any binding way** — EC11/EC12 are referenced above only to justify *excluding* work from EC10 (production-workflow and appointment templates), not to plan their content.
4. **No donor repository was inspected** — every finding above came from the current MVP repository (`/app/backend`, `/app/frontend`) and the EC10 spec docx itself; nothing in the EC10 spec identified a donor-only feature that couldn't be understood from the current repo.
5. Minimal-credit instruction followed: targeted `grep`/`glob`/file-view calls only, no wide directory dumps beyond what was needed to build the inventory in §1.

---

## Summary for owner

- EC10 is genuinely new scope (Decision Room, Visual Markup, Templates) layered additively on 6 existing EC6/EC9 systems (Files, Documents, Proofs, Approvals, Signatures, Public Tokens) — no conflicts, no duplicate systems proposed.
- 5 new models recommended (not 9): `IntakeSubmission`, `VisualMarkup`+`MarkupVersion`, `DecisionRoom`+`DecisionOption`, `CustomerDecision`, `TemplateDefinition`. `ChangeRequest` and `IntakeTemplate` collapse into existing/new models rather than becoming separate collections.
- One technical library decision (Fabric.js + pdfjs-dist for markup) is recommended, not escalated, per the spec's own "don't ask about routine technical details" instruction.
- **3 genuine owner decisions block specific later phases only** (§10): #1 blocks Phase 10F, #2 blocks Phase 10E's customer-drawing scope, #3 is a scope-boundary confirmation that blocks nothing.
- Recommended sequencing: **10A → 10B → 10C → 10D → 10E → 10F → 10G → 10H**, matching the task's suggested order exactly — no reordering needed based on repository evidence.

**Awaiting explicit owner authorization to begin Phase 10A.**
