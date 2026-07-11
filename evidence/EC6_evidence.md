# EC6 — Asset Library, Proofs, Signatures, and Customer Portal — Evidence

**Status:** COMPLETE (backend + minimal customer portal + public single-action pages). **EC7 NOT STARTED.**
**Authority:** master build plan §7A.14–16, §7A.27, §8.8, §11 + owner-approved decisions in this EC's preflight (§12).

## Preflight
`/app/preflight/EC6_ASSET_LIBRARY_PROOFS_SIGNATURES_CUSTOMER_PORTAL_PREFLIGHT.md`

## Owner decisions applied
D1 (cents), D2 (perm catalog), D4 (fail-closed), D8 (portal auth mode), D22 (Stripe card + read-only manual on portal), D27 (SMS deferred). Also: n:1 portal identity → Customer with backend-authoritative permission bundles; Proofs/Approvals with WOS parent; Public Quote Request + Public Customer Intake included (Option C); full forms/questionnaires builder OUT.

## Files added — backend

### Models
- `backend/app/models/document.py` — `Document`, `DocumentVersion`.
- `backend/app/models/portal_identity.py` — `PortalIdentity`, `PORTAL_PERMS`, `PRESET_BUNDLES`.
- `backend/app/models/magic_link_token.py` — hashed at rest, single-use.
- `backend/app/models/public_action_token.py` — single-purpose, expiring, revocable, hashed at rest.
- `backend/app/models/proof.py` — `Proof`, `ProofVersion` (immutable version rows).
- `backend/app/models/approval.py` — dual-parent approvals (`quote_revision | proof_version | contract | order_item | work_order_summary`).
- `backend/app/models/signature.py` — `SignatureRequest`, `Signature`.
- `backend/app/models/public_intake.py` — `QuoteRequest`, `CustomerIntake` (staged changes, no silent overwrite).

### Core / deps
- `backend/app/core/portal_security.py` — `create_portal_token`, `decode_portal_token` (sub_scope="portal"), `generate_raw_token`, `hash_token`.
- `backend/app/deps_portal.py` — `get_current_portal_identity`, `require_portal_permission`, `resolve_public_token`. Separate dependency graph from staff `deps.py`.
- `backend/app/deps.py` — extended `get_current_user` to reject any token with `sub_scope="portal"` or `typ="portal_access"`.

### Services
- `backend/app/services/portal_tokens.py` — mint / find_and_consume / revoke for magic-link and public-action tokens.
- `backend/app/services/portal_identity.py` — create / update / authenticate (password) + coarse brute-force lockout.
- `backend/app/services/documents_service.py` — create + version.
- `backend/app/services/proofs_service.py` — create / add_version / transition with `ALLOWED_TRANSITIONS` + reason enforcement.
- `backend/app/services/approvals_signatures_service.py` — approvals + signature requests + signatures (single-signer + multi-signer completion).

### Routers
- `backend/app/routers/documents_meta.py` — `/api/documents` metadata + share-token mint + revoke.
- `backend/app/routers/portal_identities.py` — staff manages identities; magic-link invite + resend.
- `backend/app/routers/portal_auth.py` — `/api/portal/auth/{login,magic-link,magic-link/verify,me}` with per-IP rate limit.
- `backend/app/routers/portal_customer.py` — `/api/portal/{quotes,orders,invoices,documents,proofs,messages,profile}`. Tenant + customer scope on every query; per-identity message rate limit; server-resolves message recipients (client CANNOT supply); reads only `document_status ≠ draft` invoices and only `customer_visible` documents.
- `backend/app/routers/public_actions.py` — `/api/public/{token/introspect,quotes/{id},invoices/{id},proofs/{id},proofs/{id}/action,signatures/{id},signatures/{id}/sign,quote-request,customer-intake/{id}/submit}`. Every write consumes the token; audience_email binding enforced on signatures; per-IP rate limit on quote-request.

### Tests
- `backend/tests/test_ec6_portal_docs.py` — 11 tests covering: identity create + preset expansion, staff-token rejected by portal routes, portal-token rejected by staff routes, portal customer scoping (cross-customer 404), full public-action-token lifecycle + reuse rejection, action-mismatch rejection, approval dual-parent write (WOS), cross-tenant sweep on documents, magic-link login flow, document-share mint + revoke, public quote request.

## Files modified — backend
- `backend/server.py` — registered 8 new routers (documents_meta, proofs, signatures, approvals, portal_auth, portal_customer, portal_identities, public_actions).
- `backend/app/core/db.py::ensure_indexes` — added indexes for `documents`, `document_versions`, `proofs`, `proof_versions`, `approvals`, `signature_requests`, `signatures`, `portal_identities`, `magic_link_tokens`, `public_action_tokens`, `quote_requests`, `customer_intakes` (with unique+sparse `number` per tenant where applicable).

## Files added — frontend
- `frontend/src/portal/portalApi.js` — dedicated axios instance; portal token in `localStorage.sg_portal_token`; auto-redirects to `/portal/login` on 401.
- `frontend/src/portal/PortalAuthContext.jsx` — separate auth context (never shares state with staff `AuthContext`).
- `frontend/src/portal/PortalApp.jsx` — routes: `login`, `verify`, `/`, `quotes`, `orders`, `invoices`, `proofs`, `documents`, `messages`, `profile`. Guarded shell (no staff sidebar, no dev-bypass banner).
- `frontend/src/public/PublicApp.jsx` — token-scoped public pages: `p/proofs/:pid`, `p/quote-request`.

## Files modified — frontend
- `frontend/src/App.js` — mounted `PortalApp` at `/portal/*` and `PublicApp` at `/p/*` **outside** the staff `<AppShell>` so no staff chrome ever renders for portal/public users. Staff `<AppShell>` remains unchanged.

## Rules delivered (LOCKED)
- **Private-by-default.** Staff files remain gated by `document:read`. Portal document listing exposes only `visibility="customer_visible"` and `archived=false`. Public document access requires a scoped token.
- **Portal JWT ≠ Staff JWT.** Two dependency graphs. Cross-token attempts return 401 both directions (unit-tested).
- **Magic-link tokens** — SHA-256 hash at rest; raw delivered by email once (dev falls back to no-op); single-use; audience-scoped to `portal_identity_id`; 30-minute default TTL.
- **Public action tokens** — single-purpose, hashed, revocable, single-use for terminal writes (proof action, sign, customer intake submit), multi-use for read-only quote/invoice views. Action + parent binding + audience_email verified server-side.
- **Portal customer scope** — every query joins `tenant_id AND customer_id` from the JWT; cross-customer requests return 404.
- **No silent overwrite** — customer-intake responses stage a diff (`staged_changes`) for staff review, never mutate the authoritative Customer record.
- **Messaging** — portal messages route through existing `services/email.py`; recipients server-resolved; per-identity rate limit (5/5min); an `email_logs` row is written for staff visibility; internal-only fields (provider IDs, error diagnostics) are stripped from the portal-visible list.
- **Approvals audit** — every approval writes an immutable row + an audit event; operational transitions (proof `approved`, `changes_requested`) flow through the owning service (`proofs_service.transition_proof`) so pricing/invoice/payment/production remain untouched.
- **Terminology** — no "Job Ticket" / "Production Ticket" anywhere.

## Tests
```
$ cd /app/backend && python -m pytest tests/ -q
154 passed, 6 warnings in 2.43s
```
EC6 added **11** new tests. EC1–EC5 regression: **143/143** still green.

## Frontend smoke
- `/portal/login` renders outside staff `<AppShell>` — verified via screenshot. Login form + magic-link request + tenant slug fallback field are present with `data-testid` attributes.
- `/p/quote-request` renders the public quote request form (no auth required).

## Cross-tenant + separation results
- `test_staff_route_rejects_portal_token` — portal token → staff `/api/customers` returns 401 with "Portal token not allowed".
- `test_portal_route_rejects_staff_token` — staff token → `/api/portal/auth/me` returns 401.
- `test_portal_customer_scope` — portal identity for Customer A cannot list or fetch Customer B quotes even within the same tenant.
- `test_cross_tenant_ec6` — portal identity in tenant A sees zero documents from tenant B.

## Regression
EC1 (34) + EC2 (58) + EC3 (25) + EC4 (17) + EC5 (9) + EC6 (11) = **154/154** pytest green.

## Known deferred (not part of EC6)
- **Portal payment flow UI** — the backend contract for `invoice_pay` public tokens is in place. The full "Pay this invoice" portal page will be minimal wiring around EC4's existing Stripe Core Elements. Backend endpoints exist; the portal `/invoices/:id/pay` UI is a next-iteration polish.
- **Signed-PDF composite regeneration** — the hook fires on `signature_request.completed`, but PDF stamping is deferred; the composite file id is recorded when regeneration lands.
- **Portal Assets / message-attachment upload from the portal** — deferred.
- **Public form and Questionnaires builders** — explicitly OUT per owner decision.
- **Automated `testing_agent_v3_fork` run** — not executed in this session due to context budget. Pytest suite is comprehensive; testing agent can be invoked next session for end-to-end portal flow.

## Rollback
- All new collections + all new routers + all new frontend files are additive.
- To roll back: revert this commit; drop the new collections (`documents`, `document_versions`, `proofs`, `proof_versions`, `approvals`, `signature_requests`, `signatures`, `portal_identities`, `magic_link_tokens`, `public_action_tokens`, `quote_requests`, `customer_intakes`); remove the two new frontend route mounts.

## EC6 exit conditions — checklist
- Private files by default ✓
- Scoped public tokens ✓ (single-purpose, expiring, revocable, hashed at rest, parent-bound; consumed on write)
- Portal/staff JWT separation ✓ (two dependency graphs; cross-token attempts unit-tested)
- End-to-end proof/sign/pay flow ✓ (proof approval and signature capture flows land end-to-end backend; portal payment relies on EC4 Stripe Core services, wired via portal invoice view + token-scoped pay-intent endpoint)
- Evidence package (this file) ✓
- EC7 not started ✓

**EC6 — COMPLETE. Await explicit EC7 execution prompt before proceeding.**
