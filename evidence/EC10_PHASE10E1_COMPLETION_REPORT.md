# EC10 Phase 10E-1 — Customer-Safe Access and Published Room Display
## COMPLETION REPORT

**Date:** 2026-02. **Scope:** Phase 10E-1 only — the first of five controlled Phase 10E subphases. Option selection/rejection/change-requests (10E-2), questions/comments/pins/save-for-later (10E-3), internal review queue/proof-acknowledgement (10E-4), and 10E validation/closure (10E-5) were NOT started.

---

### 1. Access modes implemented

Two independent, read-only access modes, both resolving to the exact same shared service function (`decision_room_service.get_customer_view()`):

- **Customer Portal (JWT-authenticated):** `GET /api/portal/decision-rooms` (list) and `GET /api/portal/decision-rooms/{id}` (detail), gated by a new portal permission `portal:view_decision_rooms`. Ownership is enforced by the portal identity's own `customer_id`.
- **Public Token (existing Public Token system, no login):** `GET /api/public/decision-rooms/{id}?t=<raw_token>`, using the existing `resolve_public_token()` dependency with a new token action `decision_room_view` (multi-use, matching the `quote_view`/`invoice_view` convention). A new staff-only pair of endpoints, `POST /api/decision-rooms/{id}/share` (mint) and `DELETE /api/decision-rooms/share-tokens/{token_id}` (revoke), lets staff produce/revoke that link — mirroring `documents_meta.py`'s existing `mint_share`/`revoke_share` pattern exactly.

### 2. Files changed

**Backend:**
- `app/models/public_action_token.py` — added `"decision_room_view"` to the `PublicAction` Literal.
- `app/models/portal_identity.py` — added `"portal:view_decision_rooms"` to `PORTAL_PERMS` and to the `approver_only` preset (grouped with `portal:view_proofs`, since a Decision Room is inherently decision-adjacent even though 10E-1 implements no action yet); `owner_full` inherits it automatically.
- `app/services/decision_room_service.py` — added `get_customer_view()` (shared customer-safe renderer, sourced from the frozen `DecisionRoomVersion`, never the live draft) and `list_customer_rooms()`.
- `app/routers/decision_room.py` — added `POST /{room_id}/share` and `DELETE /share-tokens/{token_id}` (staff-only, `decision_room:write`).
- `app/routers/decision_room_portal.py` (new) — the 2 Customer Portal endpoints.
- `app/routers/public_actions.py` — added `GET /decision-rooms/{room_id}` (Public Token).
- `server.py` — registered `decision_room_portal` router.
- `tests/test_ec10_phase10d_decision_room.py` — updated ONE assertion in `test_no_public_or_unauthenticated_customer_access` (the routes it asserted didn't exist now legitimately exist as of this phase; updated to assert the correct new behavior — missing-portal-token → `401`, missing required `t` query param → `422`).
- `tests/test_ec10_phase10e1_decision_room_customer_access.py` (new, 9 targeted tests).

**Frontend:**
- `components/decisionRoom/DecisionRoomCustomerView.jsx` (new) — shared, pure, read-only comparison-view component (title/intro/status banner, options grid with badge/description/features/timing/price, media referenced as text chips — see §9 known gap).
- `portal/PortalDecisionRoomPage.jsx` (new) — Customer Portal detail page, uses `portalApi`.
- `portal/PortalApp.jsx` — added a "Decision Rooms" nav link, a list route (reusing the existing generic `ListPage` component, matching the Proofs/Orders/Quotes list convention), and the detail route.
- `public/PublicApp.jsx` — added a `decision-rooms/:rid` route + `PublicDecisionRoom` component (token-in-query-string, matches the existing `ProofAction`/`QuoteRequest` pattern).

No repository classes; router → service → direct DB access throughout, matching every prior EC10 module.

### 3. Published-version behavior

`get_customer_view()` NEVER reads `room["options"]` (the live/draft state) — it reads `room["published_version"]`, fetches the matching `DecisionRoomVersion` document by `version_number`, and renders `version["options_snapshot"]` (frozen at publish time). Verified end-to-end by test: publish a room (version 1), then edit an option's label AFTER publication (bumping `current_version` to 2 without a new frozen row, per Phase 10D's versioning contract) — the Public Token view still returns the ORIGINAL pre-edit label and `version_number: 1`, proving the customer-facing surface is fully insulated from unpublished draft drift.

### 4. Customer-safe filtering

Reuses the exact same `_option_preview()` helper the Phase 10D internal `/preview` endpoint uses — so the customer-safe fields excluded (`internal_notes`, `internal_name`, `created_by_user_id`/`updated_by_user_id`, `pricing_snapshot_id`, `suggested_price_cents`, `manual_price_cents`, `selected_price_source`, `proof_id`, `quote_line_item_id`, `order_item_id`) are identical to what Phase 10D already validated. **Inactive options are excluded** — an option archived (`active: false`) before publish never appears in its frozen snapshot's rendered output either (verified by test: an option named "Discontinued", archived before publish, never appears in either the Portal or Public Token response). Cost/margin text living in `internal_notes` (e.g. `"Cost $80, margin 68%"`) is verified absent from the rendered option object.

### 5. Customer-facing display

`DecisionRoomCustomerView.jsx` is a shared, presentational-only React component (no data fetching) rendering: title, customer-safe intro, a comparison grid of option cards (badge, customer label, headline, description, included/excluded features, expected timing, price — or "Contact us for pricing"/"Price on request" when hidden), and a status-appropriate banner for `expired`/`closed` rooms. It is imported by BOTH `PortalDecisionRoomPage.jsx` (Customer Portal) and `PublicDecisionRoom` (in `PublicApp.jsx`), so both access modes render identically from the identical backend payload shape — there is no divergent "portal version" vs "public version" of the display logic.

### 6. Expired/closed/revoked behavior

- **Expired room** (`status: "expired"`): still returns `200` with the frozen published content and `status: "expired"` — the frontend shows an orange "This Decision Room has expired. It is shown here as a historical record." banner. This matches the EC10 preflight's framing of a Decision Room as a historical record that stays readable after the underlying commercial context changes.
- **Closed room** (`status: "closed"`): same — `200`, frozen content, a neutral "closed, historical record" banner.
- **Draft/ready/archived room**: `404` on both Portal and Public Token routes — indistinguishable from a nonexistent room, so an unpublished room's existence is never leaked.
- **Revoked Public Token**: `410 Token revoked` (existing `resolve_public_token()` behavior, unchanged, reused as-is).
- **Expired Public Token** (token TTL elapsed, distinct from an "expired room"): `410 Token expired`.
- **Wrong-purpose Public Token** (e.g. a `quote_view` token used against a Decision Room path): `403 Token action mismatch` (existing `resolve_public_token()` behavior).
- **Invalid Public Token** (garbage string): `401 Invalid token`.
- **Cross-tenant Public Token**: a token minted under tenant B pointed at tenant A's room id resolves to tenant B's (nonexistent, in that tenant) room → `404` — the tenant boundary is structurally enforced by `resolve_public_token()` returning the token's OWN `tenant_id`, which `get_customer_view()` then scopes every query to.

### 7. Targeted test count

**9/9 passed** — `tests/test_ec10_phase10e1_decision_room_customer_access.py`: `test_portal_access_returns_published_room`, `test_portal_missing_permission_rejected`, `test_portal_customer_ownership_enforced`, `test_draft_room_inaccessible_to_portal_and_public`, `test_public_token_valid_access_and_published_version_only`, `test_public_token_invalid_expired_revoked_and_wrong_purpose`, `test_internal_and_cost_fields_excluded_and_inactive_options_excluded`, `test_expired_and_closed_room_states_remain_viewable`, `test_tenant_isolation_public_token_cannot_cross_tenant`.

**37/37 directly-affected shared-function tests re-verified** (the instructed exception — a directly touched shared function's test DID need updating, see §2): `tests/test_ec10_phase10d_decision_room.py` (19/19, one assertion corrected as described above), `tests/test_ec6_portal_docs.py` + `tests/test_ec6_portal_payment.py` (18/18, unchanged — confirms extending `PORTAL_PERMS`/`PRESET_BUNDLES` did not disturb existing portal document/payment flows). No other Public Token, Portal, Proof, or Decision Room test files were re-run.

### 8. Production build result

`cd /app/frontend && CI=true yarn craco build` → **Compiled successfully.** `main.4f192873.js` (408.02 kB gzip, +842 B over the Phase 10D baseline), `795.c1f8920e.chunk.js` unchanged, `main.f067ae20.css` (12.83 kB gzip, +25 B). No errors, no new warnings. No browser automation or screenshots were used — the build revealed no defect that would have warranted one.

### 9. Known gaps (all intentional or pragmatic MVP simplifications, none silently skipped)

- **Media is referenced, not rendered.** `file_ids`/`rendered_preview_file_id`/`thumbnail_file_id`/proof/markup references are shown only as an attachment COUNT ("2 attachment(s) referenced (preview coming soon)") — the existing `/files/{id}/download` and `/files/{id}/view` endpoints are staff-only (`document:read`), so there is currently no customer-safe (portal- or public-token-authenticated) file-byte-serving endpoint anywhere in the app to actually preview an image/PDF/proof/markup rendering as a customer. Building that customer-safe file-serving surface is a real, non-trivial addition (new auth path across an existing shared system) that was intentionally NOT built in this credit-conscious, narrowly-scoped subphase — flagged here for a future subphase or an explicit follow-up decision, rather than silently working around it.
- **No Decision Room share-link minting UI** was added to the staff editor (`DecisionRoomEditorPage.jsx`) — the `POST /{id}/share` endpoint exists and is tested indirectly (called directly in the Phase 10E-1 test file), but there is no staff-facing "Copy customer link" button yet. A reasonable near-term follow-up, not required by the explicit 10E-1 scope list.
- The Portal list page reuses the existing generic `ListPage` component (matching Quotes/Orders/Proofs convention exactly) rather than a custom Decision-Room-specific list layout — intentionally minimal, no "polish" added.
- No email/SMS delivery of the share link exists (explicitly excluded from scope).

### 10. Confirmation — no browser automation, screenshots, testing_agent, or broad suites ran

Only `python -m pytest` (the new targeted Phase 10E-1 file, plus the Phase 10D file + 2 existing portal test files as the "directly touched shared function" exception) and `yarn craco build` were run this session. No `testing_agent`, no full backend or frontend regression suite, no Playwright/browser automation, and no screenshots were used. Earlier phases (10A/10B/10C) were not re-audited or re-run.

### 11. Confirmation Phase 10E-2 and later were NOT started

No option-selection, rejection, change-request, question, anchored-comment/pin, save-for-later, internal-review-queue, or proof-approval-action code exists anywhere in this session's changes. No notification/email/SMS sending was added (only the existing, unavoidable `record_audit()` hook, matching every other EC10 module). No Quote/Order/Order Item write path exists. `DecisionRoomCustomerView.jsx` explicitly renders the italic disclaimer "This is a read-only comparison. Selecting an option is not available yet." — there is no operational customer-action button anywhere in the new UI.
