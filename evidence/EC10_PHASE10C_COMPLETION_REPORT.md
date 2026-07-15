# EC10 Phase 10C — Asset Upload and Visual Markup
## COMPLETION REPORT

**Date:** 2026-02. **Scope:** Phase 10C only (per owner authorization). Phase 10D and later NOT started.

---

### 1. Dependencies and exact versions

Frontend (`/app/frontend/package.json`):
- `fabric`: `6.9.1` (MIT) — canvas annotation object model (shapes/arrows/text/pins/groups).
- `pdfjs-dist`: `5.6.205` (Apache-2.0) — client-side PDF page rendering. PDF worker loaded via `new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url)` (no CDN dependency).

No new backend Python packages were required for Phase 10C — reuses the existing FastAPI/Pydantic/PyMongo stack unchanged.

### 2. Files changed

**Backend (new):**
- `app/models/visual_markup.py` — `VisualMarkup`, `MarkupVersion`.
- `app/services/markup_service.py` — create/get/list markup, `save_version`, `list_versions`/`get_version`, `get_preview_reference`, `archive_markup`/`restore_markup`, `attach_to_intake`/`attach_to_intake_item`, `validate_structured_markup`.
- `app/routers/visual_markup.py` — `/api/markup*` (staff-only).
- `tests/test_ec10_phase10c_visual_markup.py` (new, 12 targeted tests).
- Additive: `app/core/permissions.py` (`Perm.MARKUP_READ`/`MARKUP_WRITE`, added to `STAFF_PERMS`), `server.py` (router registration).

**Frontend (new):**
- `components/intake/markup/MarkupWorkspace.jsx` — dialog orchestrator: resolves image (blob URL) or PDF-page (client-rendered to a `<canvas>` → data URL) background, loads the current version's objects, wires toolbar/canvas/save/version-history.
- `components/intake/markup/MarkupCanvas.jsx` — the Fabric.js annotation surface (fixed logical resolution, undo/redo history stack, tool dispatch, `getStructuredJson()`/`toPreviewDataUrl()`).
- `components/intake/markup/MarkupToolbar.jsx` — select/freehand/line/arrow/rect/ellipse/text/callout/pin/highlight + delete/undo/redo/zoom/fit/clear/save.
- `components/intake/markup/MarkupVersionHistory.jsx` — read-only version list.
- `lib/markupCoordinates.js` — display-scale helper (`computeDisplayScale`), unit-tested (`__tests__/markupCoordinates.test.js`).
- `lib/markupObjects.js` — allowlisted-primitive builders for arrow/pin/numbered-callout (composed from `line`/`triangle`/`circle`/`textbox`/`group` — no custom Fabric subclass, so every object serializes to a backend-allowlisted type).
- Modified (additive): `components/intake/FileAttachmentPicker.jsx` — markup entry point (pencil icon) rendered per-chip when `markupContext` is supplied and the file's `mime_type` is image/PDF; PDF chips additionally expose a page-number input.

### 3. VisualMarkup and MarkupVersion behavior

`VisualMarkup` is a workspace bound to exactly one existing `FileRecord` (`source_file_id`, never copied/re-uploaded). It tracks `current_version_id`/`current_version_number` and a `status` (`active`/`archived`). `MarkupVersion` is **append-only**: every save creates a brand-new version row; no version is ever mutated or deleted (verified by test — a version fetched after two subsequent saves is byte-identical to what was originally stored, including its `change_summary`). Each version carries its own `parent_version_id`, forming a linear lineage chain. Archiving a `VisualMarkup` blocks new version writes (400) but never deletes existing versions; restoring re-enables writes — history is always intact.

### 4. Supported tools

Select/move, freehand draw (Fabric `PencilBrush`), straight line, arrow (composed line + triangle head), rectangle, ellipse, text label (`Textbox`), numbered callout (circle + number, auto-incrementing), pin (filled circle marker), highlight box (semi-transparent fill, no stroke), plus delete-selected, undo/redo (client-side history stack, not persisted until "Save new version" is clicked), zoom in/out, fit-to-screen, and "clear unsaved changes" (reverts to the last saved version). No filters, cropping, masking, or design tools — annotation only, per the EC10 preflight §6 recommendation.

### 5. Image and PDF support

- **Image** source files (`image/png`, `image/jpeg`, `image/jpg`, `image/webp`): downloaded once via the existing authenticated `/files/{id}/download` proxy, displayed as a Fabric `backgroundImage` (never part of the persisted object array), capped at 1400px on the long edge for canvas performance (capped dimensions become the version's `canvas_width`/`canvas_height` — the original file on disk is untouched).
- **PDF** source files: the original PDF is never modified or re-uploaded. `pdfjs-dist` renders the requested `source_page_number` client-side into an offscreen `<canvas>`, which is converted to a PNG data URL and used ONLY as the Fabric background for that markup session — the rendered pixels are never persisted as a new source file; only the annotation objects are ever saved. A PDF markup workspace requires a valid (`>= 1`) `source_page_number` at creation — omitting it or passing `0` is rejected with `400 invalid_pdf_page` (verified by test).

### 6. Coordinate/version handling

Each `MarkupVersion` freezes the exact `canvas_width`/`canvas_height` (the logical Fabric resolution at save time) and `source_display_width`/`source_display_height`, plus a `coordinate_space` tag (`"canvas_pixels_v1"`) for future-proofing. Stored object coordinates (`left`/`top`/etc.) are never rewritten when the workspace is reopened at a different screen width — `lib/markupCoordinates.js#computeDisplayScale` computes one uniform scale factor and applies it via Fabric's `canvas.setZoom()`, which only affects on-screen rendering/hit-testing. Verified by test (`test_coordinate_round_trip`): a version saved with `left: 123.5, top: 456.25` at `canvas_width=1024` is re-read with the identical floating-point coordinates and dimensions.

### 7. Preview generation

On save, the frontend renders the flattened canvas (`canvas.toDataURL()`) and uploads it through the existing `/files/upload` endpoint as an ordinary new `FileRecord` — a derivative, never authoritative, always a **separate** file id from the source (verified by test: `rendered_preview_file_id != source_file_id`, and the original source file record is confirmed unchanged/still resolvable after the save). If the preview upload fails, the structured version is still saved (toast-warned, not blocked) — a preview-generation failure can never corrupt or block the append-only annotation history. `rendered_preview_file_id` is validated tenant-scoped on write; an unresolvable reference is rejected (`404 preview_file_not_found`).

### 8. Intake and Intake Item integration

A markup can optionally reference an `intake_id`/`intake_item_id` at creation (both tenant/existence-validated; a bad `intake_item_id` is rejected `404`). `POST /markup/{id}/attach` links a markup to an intake (`$addToSet` on `IntakeSubmission.visual_markup_ids`) or to a specific item (`items.$.visual_markup_id` + `items.$.rendered_preview_file_id`, keeping the item's preview reference in sync with whatever the current version is). Saving a new version on an item-linked markup also auto-propagates the new preview reference onto that intake item — by reference only, never a copy of the markup JSON. The `FileAttachmentPicker` markup entry point is wired into intake file chips (both intake-level and item-level) via the existing Phase 10B component — no new attachment UI surface was invented.

### 9. Payload validation and tenant isolation

`validate_structured_markup()` enforces, on every version write: only allowlisted Fabric object types (`rect/circle/ellipse/line/path/triangle/textbox/i-text/text/group/polygon/polyline`) — an unsupported type (e.g. `"image"`) is rejected `400`; no `backgroundImage`/`background` key; no embedded `data:image`/`data:application/pdf`/`data:application/octet-stream` value anywhere in the payload (recursive scan) — rejected `400 embedded_binary_forbidden`; a 300-object cap (nested groups limited to 1 level deep) — rejected `400 too_many_objects`; a 300,000-byte serialized-size cap. All confirmed by test. Every markup/version/preview/attach endpoint is tenant-scoped (`{"id": ..., "tenant_id": user["tenant_id"]}` on every query) — cross-tenant GET/version-save/guessed-id all return `404` (never leaking existence), verified by `test_source_file_validation_cross_tenant_and_unavailable` and `test_tenant_isolation_and_permissions`. Both `markup:read`/`markup:write` are staff-role permissions (no customer-facing or public route exists in this phase).

### 10. Audit events

Every markup mutation is audited via the existing `record_audit()` helper — `markup.created`, `markup.version_saved`, `markup.current_version_changed`, `markup.archived`, `markup.restored`, `markup.attached_to_intake`, `markup.attached_to_intake_item`. Audit `diff` payloads never contain the full `structured_markup_json` or a raw `objects` array (verified by test `test_audit_events_emitted` — asserts both keys/substrings are absent from every recorded event) — only lightweight metadata (source file id, intake/item ids, version number) is logged.

### 11. Targeted test count and result

**12/12 passed** — `tests/test_ec10_phase10c_visual_markup.py`:
`test_create_image_markup`, `test_create_pdf_page_markup_requires_valid_page`, `test_source_file_validation_cross_tenant_and_unavailable`, `test_intake_and_intake_item_attachment`, `test_structured_json_persistence_and_object_validation`, `test_versioning_monotonic_and_prior_version_immutable`, `test_concurrent_version_saves_get_distinct_monotonic_numbers`, `test_rendered_preview_stored_separately_and_original_untouched`, `test_archive_and_restore`, `test_tenant_isolation_and_permissions`, `test_audit_events_emitted`, `test_coordinate_round_trip`.

Command run: `cd /app/backend && python -m pytest tests/test_ec10_phase10c_visual_markup.py -q` → `12 passed`. Per the owner's explicit constraint, no other test files, no full backend regression, and no `testing_agent` were run in this session.

### 12. Production build result

`cd /app/frontend && CI=true yarn craco build` → **Compiled successfully.** `main.d37f8c6d.js` (400.52 kB gzip) + `795.c1f8920e.chunk.js` (135.91 kB gzip, contains the `fabric`/`pdfjs-dist` async-loaded code) + `main.7011e776.css` (12.79 kB gzip). No errors. No new warnings introduced by the `fabric`/`pdfjs-dist` integration.

### 13. Known gaps (all intentional, deferred to their named phase)

- No customer-facing markup UI or route — Phase 10C is staff-only, per the preflight's Owner Decision #2 default (customers may only comment/acknowledge, not draw) and per explicit scope (10E).
- No Proof/Work-Order-Summary attachment surface yet — `VisualMarkup.proof_id` is a reserved, unenforced field; Proofs integration is not built in 10C.
- No in-person signature capture bound to a markup version — reserved for a later phase per the EC6.3 legacy scope; not required for 10C's asset-upload/markup contract itself.
- Preview generation runs client-side (Fabric `toDataURL`) — no server-side rendering fallback; a failed preview upload degrades gracefully (version still saves) rather than retrying automatically.
- Per-keystroke change-summary input is not debounced (not needed — it is only read at save time, not on every keystroke write).
- No frontend Jest unit tests were run this session beyond what already exists (`markupCoordinates.test.js`) — per the owner's explicit "targeted backend tests + build check only" instruction, `yarn test`/Jest was not invoked in this session.

### 14. The three owner decisions from the EC10 preflight §10 — reproduced verbatim

| # | Issue | Why it matters | Recommended option | Alternative | Can implementation proceed around it? |
|---|---|---|---|---|---|
| 1 | Does a customer "Select" in the Decision Room require internal staff acceptance before the live Quote/Order Item changes, or can it apply immediately? | Directly determines whether Phase 10F needs a staff review queue or can be a straight-through pipe. The EC10 spec text says "only through an explicit controlled action" — read most naturally as **staff acceptance required**, but the owner should confirm this is not meant to allow direct customer-driven auto-apply for low-risk selections (e.g. size-only changes). | **Require an explicit staff/controlled acceptance step for every decision, no auto-apply exceptions** (matches spec text literally, matches `CustomerIntake` precedent, safest default). | Allow tenant-configurable auto-apply for specific low-risk option types later (P2, not EC10). | Yes — Phase 10A-10E can be built without this being decided (options/comparison/selection capture doesn't need the answer); Phase 10F (the actual Quote/Order Item write) is genuinely blocked without it. |
| 2 | Can customers annotate/draw directly on markup, or is markup staff-only with customer view/comment-only? | Changes Phase 10C/10E scope materially (customer-facing Fabric.js editor vs. read-only viewer + comment pins). Spec §3 lists "Customer and staff comments anchored to markup points" (implying customers comment, not necessarily draw) but §2/§3 elsewhere is ambiguous about customer-authored shapes. | **Staff draws/authors markup; customers can only add anchored comments/pins (not freeform shapes) and approve/acknowledge a version** — safer, matches "Approval or acknowledgement per version" language, avoids customers accidentally corrupting a proof-quality asset. | Allow customers full drawing parity with staff. | Yes for 10C (staff-side editor is needed regardless); blocks the exact scope of 10E's customer-facing markup UI. |
| 3 | Should the "Wrap Command Center"/"Wrap Lab" naming correction register item interact with EC10 at all (e.g. vehicle-graphics intake)? | Just a scope-boundary confirmation — Wrap Lab is EC15 (held, unauthorized). | **No — EC10 intake/markup/decision-room applies generically to all categories including vehicle graphics pricing (EC9 already supports it), but any Wrap-Lab-*specific* workflow (e.g. vehicle diagrams) stays out of EC10 and waits for EC15.** | — | Yes, does not block any EC10 phase; stated here only for completeness per the spec's request to flag scope boundaries. |

None of these three were resolved or acted on in Phase 10C, as instructed — reproduced here unresolved, for the owner's future decision before Phase 10E (#2) and Phase 10F (#1) begin. Phase 10C's staff-only implementation is consistent with (and does not preempt) either answer to #2.

### 15. Confirmation — Phase 10D NOT started

No `DecisionRoom`/`DecisionOption`/`CustomerDecision` model, service, router, or UI exists. No Phase 10D code, routes, or frontend authoring surface was created or modified in this session. No `testing_agent` was invoked and no full backend/frontend regression suite was run this session — only the 12 targeted Phase 10C tests and one `yarn craco build` compile check, per explicit owner instruction.
