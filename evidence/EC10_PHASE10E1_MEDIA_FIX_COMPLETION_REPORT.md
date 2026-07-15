# EC10 Phase 10E-1 — Completion Gap Fix: Customer-Safe Derivative Media Access
## COMPLETION REPORT

**Date:** 2026-02. **Scope:** This is a required-completion fix for Phase 10E-1 only (media access for the published Decision Room view). Phase 10E-2 and later were NOT started.

---

### 1. Files changed

**Backend:**
- `app/services/decision_room_service.py` — added `_get_accessible_room_and_version()` (extracted shared room/version lookup, used by both `get_customer_view()` and the new media resolver), `_freeze_options_with_proof_previews()` (called from `publish_room()` — resolves and freezes each option's Proof preview file AT PUBLISH TIME), `_collect_customer_media_refs()`, and `resolve_customer_safe_media()`. `_option_preview()` extended with a new `proof_preview_file_id` output field (sourced only from the frozen `_frozen_proof_preview_file_id`, never a live lookup).
- `app/routers/decision_room_portal.py` — added `GET /{room_id}/media/{file_id}` (streams bytes via the existing `storage.get_bytes()`).
- `app/routers/public_actions.py` — added `GET /decision-rooms/{room_id}/media/{file_id}` (same streaming pattern, gated by `resolve_public_token()` first).
- `tests/test_ec10_phase10e1b_decision_room_customer_media.py` (new, 5 targeted tests).

**Frontend:**
- `components/decisionRoom/DecisionRoomMedia.jsx` (new) — one shared media renderer (see §2).
- `components/decisionRoom/DecisionRoomCustomerView.jsx` — replaced the "N attachment(s) referenced" text with actual `<DecisionRoomMedia>` renders for `rendered_preview_file_id`, `proof_preview_file_id`, and each `file_ids` entry; added `buildMediaUrl`/`authToken` props.
- `portal/PortalDecisionRoomPage.jsx` — passes `buildMediaUrl` (portal media endpoint) + `authToken` (the portal JWT from `localStorage`).
- `public/PublicApp.jsx` (`PublicDecisionRoom`) — passes `buildMediaUrl` (public media endpoint, `t` embedded in the URL) and no `authToken`.

No repository classes; router → service → direct DB/storage access, matching every other EC10 module.

### 2. Customer-safe media delivery approach

**Reused the existing object-storage proxy pattern exactly** (the same one `routers/documents.py`'s staff-only `view_file`/`download_file` already use): `storage.get_bytes(file_doc["storage_key"])` fetches the bytes from the (private-by-default) Emergent Object Storage adapter, and the endpoint returns them as a plain `Response(content=data, media_type=...)`. There is no signed-URL capability in this codebase's storage adapter, so the streaming/proxy option was the only one available — and it is also the more auditable/revocable choice per the task's own instruction to "choose whichever existing pattern the repository already uses." No raw storage path, no signed URL, no presigned token, and no inline base64 are ever returned in any JSON response — only an opaque `file_id`, which the frontend turns into a same-origin API call.

On the frontend, `DecisionRoomMedia.jsx` always fetches the media endpoint as a `blob` (via `axios`, with an `Authorization` header for portal mode, none for public-token mode since the token already lives in the URL's `t` param), then renders an `<img>` from a local `URL.createObjectURL(...)` if the blob's content-type starts with `image/`, or a "View file" link (opening the same blob URL) otherwise — this is how PDF previews are supported without needing to know the mime type ahead of time. A fetch failure (401/403/404/410, or a genuinely missing storage object) renders a "Media unavailable" placeholder — never a broken-image icon or a thrown error.

### 3. Portal authorization behavior

`GET /portal/decision-rooms/{room_id}/media/{file_id}` requires the same `portal:view_decision_rooms` JWT-authenticated identity as the room-detail endpoint, and re-derives room+version access from scratch on every single media request (no caching of "already-authorized") — so a portal identity whose access is later revoked (identity `status` flipped, JWT expired) is blocked on the very next media request, not just the next room-detail request.

### 4. Token authorization behavior

`GET /public/decision-rooms/{room_id}/media/{file_id}?t=...` re-runs the full, unmodified `resolve_public_token()` dependency on every single media request — an invalid token → `401`, an expired token → `410`, a revoked token → `410`, a wrong-purpose token (e.g. a `quote_view` token) → `403`, all verified by test. A valid Decision Room token can NEVER be used to fetch a file that isn't referenced in that exact room's frozen published version (see §5) — it never becomes a general file-browser token, per the explicit constraint.

### 5. Frozen-version reference enforcement

`resolve_customer_safe_media()` computes its allow-list EXCLUSIVELY from the room's frozen `DecisionRoomVersion.options_snapshot` (via the shared `_get_accessible_room_and_version()` — the exact same lookup `get_customer_view()` uses), never from the live `room["options"]`. Verified by test (`test_draft_only_and_post_publish_media_rejected`): a brand-new, valid, `customer_visible`-flagged file attached to a live option AFTER the room was published is rejected (`404`) — it simply isn't part of the version that was actually frozen. Re-publishing (creating version 2) is the only way a newly-attached file becomes retrievable, and only under version 2's own allow-list. `Proof.current_file_id` is the one media reference that is NOT a plain File pointer sitting statically on the option — since a Proof can be re-versioned later, its resolved preview file id is eagerly resolved and frozen into the snapshot's `_frozen_proof_preview_file_id` field at the exact moment of `publish_room()`, so a later Proof re-version cannot silently change what a customer already saw.

### 6. Image, proof, markup-preview, and PDF behavior

- **Customer-safe image `file_ids`:** require the referenced `FileRecord.visibility == "customer_visible"` (an internal-only-flagged file in the same `file_ids` list is rejected `404` — verified by test).
- **`rendered_preview_file_id` / `thumbnail_file_id` (rendered VisualMarkup preview):** structurally customer-safe by their role on the option (staff explicitly attaches these AS the customer-facing preview) — servable regardless of the underlying `FileRecord.visibility` flag, with no separate opt-in needed.
- **Proof preview:** resolved from the FROZEN `_frozen_proof_preview_file_id` (see §5) — servable the same way as the structurally-safe fields above.
- **PDF previews:** handled generically — any of the above categories may point at a PDF; the frontend's blob-fetch-then-branch approach (§2) renders a "View file" link instead of an `<img>` when the fetched content-type isn't `image/*`, with no separate PDF-specific backend code path needed.

### 7. Missing/unavailable-media behavior

A `FileRecord` that exists in the DB but is `archived: true` → `404` (treated identically to "not referenced"). A `FileRecord` whose `storage_key` no longer resolves in the object-storage service (genuinely deleted/missing bytes) → the `storage.get_bytes()` call raises, caught and converted to a safe `404 "Media not available"` (never a 500, never the underlying storage error text) — verified by test with a `FileRecord` pointing at a deliberately bogus `storage_key`. The frontend never distinguishes "never existed," "not customer-safe," or "storage object gone" — all three render the identical, safe "Media unavailable" placeholder.

### 8. Targeted test count and result

**5/5 passed** — `tests/test_ec10_phase10e1b_decision_room_customer_media.py`: `test_portal_and_public_can_retrieve_referenced_customer_safe_media`, `test_unrelated_and_internal_only_file_rejected`, `test_draft_only_and_post_publish_media_rejected`, `test_public_token_state_boundaries_for_media`, `test_cross_tenant_media_and_unavailable_object_and_no_storage_path_leak`.

**28/28 directly-affected shared-function tests re-verified green** (unchanged behavior confirmed, since `publish_room()` and `_option_preview()` were both directly touched): `tests/test_ec10_phase10d_decision_room.py` (19/19) + `tests/test_ec10_phase10e1_decision_room_customer_access.py` (9/9). No other prerequisite suites were re-run.

### 9. Production build result

`cd /app/frontend && CI=true yarn craco build` → **Compiled successfully.** `main.7a0271a7.js` (408.74 kB gzip, +719 B), `795.c1f8920e.chunk.js` unchanged, `main.3bcb1e7f.css` (12.87 kB gzip, +35 B). No errors, no new warnings.

### 10. Confirmation — no broad tests, testing_agent, browser automation, or screenshots ran

Only `python -m pytest` (the new targeted media-access file + the two directly-affected Phase 10D/10E-1 files) and `yarn craco build` were run this session. No `testing_agent`, no full backend or frontend regression suite, no Playwright/browser automation, and no screenshots were used.

### 11. Confirmation Phase 10E-2 and later phases were NOT started

No option-selection, rejection, change-request, question, comment, pin, or save-for-later code exists anywhere in this session's changes — this fix is strictly a read-only media-retrieval completion for the already-approved Phase 10E-1 display. `DecisionRoomCustomerView.jsx`'s existing "This is a read-only comparison. Selecting an option is not available yet." disclaimer is unchanged. No Quote/Order/Order Item write path exists.
