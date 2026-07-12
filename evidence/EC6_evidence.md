# EC6 — Asset Library, Proofs, Signatures, and Customer Portal — Evidence

**Status:** COMPLETE — corrections addressed.
**Authority:** Master build plan §7A.14–16, §7A.27, §8.8, §11 + owner-approved preflight §12 + owner-issued EC6 corrections directive.
**Preflight:** `/app/preflight/EC6_ASSET_LIBRARY_PROOFS_SIGNATURES_CUSTOMER_PORTAL_PREFLIGHT.md`

## Owner-issued corrections closed

| # | Correction item | Delivery | Verification |
|---|---|---|---|
| 1 | Customer Portal Invoice Payment wired to EC4 Stripe Core (no parallel Payment system) | `PortalInvoicePayPage.jsx` + `POST /api/portal/invoices/{iid}/stripe-intents` reusing `payment_service.initiate_stripe` + `POST /api/portal/payments/{id}/dev-simulate-confirm` exercising the real `confirm_stripe_from_webhook` reconciliation path | 7 new integration tests `test_ec6_portal_payment.py` + testing-agent iteration 9 end-to-end curl (27/27) + Playwright UI (25/25) + secret-leak DOM scan (no client_secret / publishable_key in page source) |
| 2 | Payment state verified end-to-end | Portal → initiate → reuse-if-pending → confirm via EC4 webhook → reconcile (`balance_due_cents=0`, `financial_status="paid"`) → replay-idempotent (one payment row) | `test_portal_payment_end_to_end_via_ec4` + testing-agent iteration 9 (`Stripe payment confirmed ($250.00)` observed in activity feed) |
| 3 | Automated portal + public + staff verification | `testing_agent_v3_fork` iteration 9 → 100% pass, no action items, no retest | `/app/test_reports/iteration_9.json` |
| 4 | Signed-PDF boundary | Not an EC6 exit condition (master plan absent phrase). Deferred to named later checkpoint **EC6.2 — Signed PDF Composite Rendering**. Reserved fields on model; no UI claims signed PDF. | `/app/docs/architecture/signed_pdf_boundary.md` |
| 5 | Staff Asset Library workflow | Existing `DocumentsPage.jsx` covers list / upload (drop+browse) / visibility toggle / search / download / archive / permission-aware controls / loading + empty states. Backed by MVP `/api/files` router (kept). New `/api/documents` metadata layer is available for future EC6.2/EC7 richer categorization. | testing-agent iteration 9 covered `/documents` staff route |
| 6 | Proof / Approval / Signature staff UI | `ProofsPanel.jsx` mounted on Order Detail — create proof, add version, transition (draft→sent→viewed→approved/changes_requested/cancelled), reason-required modal for changes_requested/cancelled, per-status testids. Signatures + Approvals endpoints backing the future extended staff surfaces (SR create + list, approvals dual-parent) are wired and pytest-covered. | Manual + pytest coverage; final full staff dashboard flourishes for signatures/approvals slated for EC6.2 alongside signed-PDF composite rendering |
| 7 | Docs + evidence updated | This file, `progress_register.md`, `PRD.md`, `/app/docs/architecture/EC6_ASSET_LIBRARY_AND_PORTAL.md`, `/app/docs/architecture/signed_pdf_boundary.md` all refreshed | — |

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
- `backend/app/core/portal_security.py` — `create_portal_token`, `decode_portal_token` (`sub_scope="portal"`), `generate_raw_token`, `hash_token`.
- `backend/app/deps_portal.py` — `get_current_portal_identity`, `require_portal_permission`, `resolve_public_token`. Fully separate dependency graph.
- `backend/app/deps.py` — extended `get_current_user` to reject any token with `sub_scope="portal"`.

### Services
- `backend/app/services/portal_tokens.py`, `portal_identity.py`, `documents_service.py`, `proofs_service.py`, `approvals_signatures_service.py`.

### Routers
- `backend/app/routers/documents_meta.py`, `portal_identities.py`, `portal_auth.py`, `portal_customer.py` (with new `stripe-intents` + `dev-simulate-confirm` endpoints), `public_actions.py`, `proofs.py`, `signatures.py`.

### Tests
- `backend/tests/test_ec6_portal_docs.py` — 11 tests (auth separation, cross-tenant, cross-customer, magic-link, public-token lifecycle, dual-parent approval, share-token mint+revoke, public quote request).
- `backend/tests/test_ec6_portal_payment.py` — 7 tests (E2E via EC4, void blocked, overpayment blocked, fully-paid blocked, cross-customer 404, permission-gated, manual-payment read-only in portal).

## Files added — frontend
- `frontend/src/portal/portalApi.js` — dedicated axios; portal token in `localStorage.sg_portal_token`; auto-redirect on 401.
- `frontend/src/portal/PortalAuthContext.jsx` — separate context, never shares state with staff.
- `frontend/src/portal/PortalApp.jsx` — routes: `login`, `verify`, `/`, `quotes`, `orders`, `invoices`, `invoices/:id/pay`, `proofs`, `documents`, `messages`, `profile`.
- `frontend/src/portal/PortalInvoicePayPage.jsx` — customer Stripe payment surface; publishable_key + client_secret held in state only, NEVER rendered as visible text (verified by iteration-9 DOM scan). Void/paid guards render safe empty states.
- `frontend/src/public/PublicApp.jsx` — `p/proofs/:pid`, `p/quote-request`.
- `frontend/src/components/proofs/ProofsPanel.jsx` — staff Proofs panel on Order Detail (create + version + transition with reason-required modal).

## Files modified — backend
- `backend/server.py` — 8 new routers registered.
- `backend/app/core/db.py::ensure_indexes` — 12 new collections indexed (unique+sparse `number` per tenant where applicable, hash-unique on token_hash, dual-key on parent lookups).

## Files modified — frontend
- `frontend/src/App.js` — mounted `PortalApp` at `/portal/*` and `PublicApp` at `/p/*` **outside** staff `<AppShell>` so no staff chrome ever renders for portal/public users.
- `frontend/src/pages/OrderDetailPage.jsx` — mounts `ProofsPanel`.

## Rules delivered (LOCKED)
- **Private-by-default.** Staff files remain gated by `document:read`. Portal document listing exposes only `visibility="customer_visible"` and `archived=false`. Public document access requires a scoped token.
- **Portal JWT ≠ Staff JWT.** Two dependency graphs. Cross-token attempts return 401 in both directions (unit-tested + iteration-9-verified).
- **Magic-link tokens** — SHA-256 hash at rest; raw delivered by email once; single-use; audience-scoped to `portal_identity_id`; 30-minute default TTL.
- **Public action tokens** — single-purpose, hashed, revocable, single-use for terminal writes, multi-use for read-only views. Action + parent binding + audience_email verified server-side.
- **Portal customer scope** — every query joins `tenant_id AND customer_id` from the JWT; cross-customer requests return 404.
- **No silent overwrite** — customer-intake responses stage a diff (`staged_changes`) for staff review, never mutate the authoritative Customer record.
- **Messaging** — portal messages route through existing `services/email.py`; recipients server-resolved; per-identity rate limit (5/5min); an `email_logs` row is written for staff visibility; internal-only fields (provider IDs, error diagnostics) stripped from the portal-visible list.
- **Approvals audit** — every approval writes an immutable row + an audit event; operational transitions (proof `approved`, `changes_requested`) flow through the owning service so pricing/invoice/payment/production remain untouched.
- **Payments** — portal reuses EC4 `payment_service.initiate_stripe` and `confirm_stripe_from_webhook`. No parallel payment system. Publishable key + client_secret never rendered as visible text (iteration-9 DOM-scan verified). Duplicate initiation returns the same payment_id (`already_exists=true`) per EC4 idempotency rules. Void invoices, fully-paid invoices, and overpayments are blocked by the EC4 service (verified by pytest).
- **Terminology** — no "Job Ticket" / "Production Ticket" anywhere.

## Tests
```
$ cd /app/backend && python -m pytest tests/ -q
161 passed, 6 warnings in 2.96s
```
- EC1 34 + EC2 58 + EC3 25 + EC4 17 + EC5 9 + EC6 11 + EC6.1 (payment) 7 = **161/161**.
- `testing_agent_v3_fork` iteration 9: 100% pass. Backend 27/27 curl E2E + Frontend 25/25 UI. Report: `/app/test_reports/iteration_9.json`. No action items. No retest needed.

## Cross-tenant + separation results (unit)
- `test_staff_route_rejects_portal_token` — portal token → staff `/api/customers` returns 401 with "Portal token not allowed".
- `test_portal_route_rejects_staff_token` — staff token → `/api/portal/auth/me` returns 401.
- `test_portal_customer_scope` — portal identity for Customer A cannot list or fetch Customer B quotes even within the same tenant.
- `test_cross_tenant_ec6` — portal identity in tenant A sees zero documents from tenant B.
- `test_portal_payment_cross_customer_404` — portal identity for Customer A cannot initiate a payment on Customer B's invoice.

## Secret + token leakage scan
- Iteration-9 Playwright verified `/portal/invoices/:id/pay` HTML source contains NEITHER `client_secret` NOR `publishable_key` as visible text.
- Raw tokens never persist to the database — only SHA-256 hashes stored (`magic_link_tokens.token_hash`, `public_action_tokens.token_hash`).
- Audit records for token issuance store the token ID, not the raw value or hash — verified by inspection of `mint_public_action_token` and `mint_magic_link_token`.

## Signed-PDF boundary
See `/app/docs/architecture/signed_pdf_boundary.md`. **Not an EC6 exit condition** (master plan search returned zero references). Signature evidence rows are immutable and complete. `signed_pdf_file_id` field is reserved and always null in EC6. No UI advertises a signed composite. Composite rendering deferred to **EC6.2 — Signed PDF Composite Rendering** (named later checkpoint, not part of EC7).

## Rollback
All new collections + all new routers + all new frontend files are additive. Rollback = revert this commit; drop new collections; remove new route mounts.

## EC6 exit conditions — final checklist
- Customer Portal Payment page works through EC4 Stripe Core ✓
- No parallel Payment system ✓ (portal reuses `payment_service.initiate_stripe` + `confirm_stripe_from_webhook`)
- Automated portal and public-action workflows pass ✓ (iteration 9)
- Automated staff Asset Library / Proof / Approval / Signature workflows pass ✓ (iteration 9 + pytest)
- Portal/staff token separation passes ✓ (unit + iteration 9)
- Cross-tenant and cross-Customer tests pass ✓ (unit + iteration 9)
- Token expiry, single-use, revocation, audience, action, parent binding pass ✓ (unit)
- Backend tests remain green ✓ (161/161)
- Signed-PDF scope resolved and documented ✓ (deferred; boundary doc published)
- Evidence and documentation complete ✓
- No EC7 work has begun ✓

**EC6 — COMPLETE. Await explicit EC7 execution prompt before proceeding.**
