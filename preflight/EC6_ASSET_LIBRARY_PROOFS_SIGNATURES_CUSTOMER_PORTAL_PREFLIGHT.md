# EC6 — Asset Library, Proofs, Signatures, and Customer Portal — PREFLIGHT

**Authority:** `/app/SIGNGUY_AI_FINAL_CONSOLIDATED_MASTER_BUILD_PLAN.md` (Parts 3, 7A.14–7A.16, 7A.27, 8.8, 11).
**Prereq:** EC0–EC5 COMPLETE.
**Repository:** `dnblack323/SIGNGUY-MVP` (permanent). No donor repo modified. No wholesale donor file copied.
**Owner decisions applied:** D1 (money cents), D2 (permissions catalog), D4 (fail-closed prod), D5 (donor archive), D8 (portal auth mode), D21 (impersonation — n/a for EC6), D22 (portal payments = Stripe card + manual internal recording; ACH deferred), D27 (SMS out of scope).

---

## 1. MVP files inspected (read-only for preflight)

Existing MVP surface that EC6 extends without duplicating:

**Backend**
- `backend/app/models/file.py` — `FileRecord` (storage_key + visibility) + `Attachment` (parent_type/parent_id polymorphic, EC1). Kept as authoritative for the staff attach flow.
- `backend/app/models/file_link.py` (EC2) — polymorphic cross-entity `FileLink`. EC6 will layer proofs/portal links on top.
- `backend/app/models/document_link.py` (EC2) — many-to-many entity ↔ document association.
- `backend/app/models/document_share.py` (EC2) — external share record shape (`channel`, `recipient_key`, `revoked`, `last_accessed_at`). EC6 completes the flow by minting scoped tokens against these.
- `backend/app/services/storage.py` — Emergent object storage adapter, private-by-default, tenant-path-prefixed. Kept.
- `backend/app/routers/documents.py` — current file upload / list / download / attach / visibility endpoints. Kept. Extended.
- `backend/app/services/upload_validation.py` (EC2) — MIME + magic-byte + size + sanitized filename. Kept.
- `backend/app/services/audit.py` + `services/activity.py` + `services/notifications.py` (EC1+EC2) — the write path all EC6 write endpoints will use.
- `backend/app/services/email.py` (EC1 + EC2 send tracking) — outbound send + `email_activity` mirror.
- `backend/app/services/sequence.py` — atomic per-tenant sequence generator. Used for `proof_number`, `signature_number`.
- `backend/app/core/permissions.py` — `Perm.DOCUMENT_*`, `Perm.PORTAL_CUSTOMER_*` already enumerated by EC1. No new permissions required for the staff catalog; portal permissions are the disjoint `PortalPerm` scope.
- `backend/app/core/security.py` — JWT + password hashing. EC6 adds a portal-scoped JWT variant (`sub_scope="portal"`) via a new helper — MVP staff JWT untouched.
- `backend/app/deps.py` — `require_permission` (staff), `require_entitlement` (EC2). EC6 adds `get_current_portal_identity`, `require_portal_permission`, `resolve_public_token` — all in a new `deps_portal.py` file to keep staff auth path free of any portal branching.

**Frontend**
- `frontend/src/pages/DocumentsPage.jsx` — staff document library. Will get "shares" tab + per-file share-token minting UI.
- `frontend/src/pages/QuoteDetailPage.jsx`, `OrderDetailPage.jsx`, `InvoiceDetailPage.jsx`, `WorkOrderDetailPage.jsx` — will get a "Share to customer" action and a proofs panel (order + work-order surfaces).
- `frontend/src/lib/api.js` — staff Axios client. **Not** reused for the customer portal — the portal gets its own `frontend/src/portal/portalApi.js` with a distinct auth header + interceptor so a portal token can never accidentally reach a staff route or vice versa.
- `frontend/src/App.js` — mounts routes. Portal routes will mount **outside** the `AppShell` (no staff chrome for customer users) at `/portal/*`. Public single-action pages mount at `/p/*`.

## 2. Legacy job-ticket / bad-terminology behavior found

**None** in the surfaces EC6 touches. Existing MVP `documents`/`attachments`/`file_links` are already terminology-clean. The terminology guard (`app/core/terminology_guard.py`) will be re-run at close-out.

## 3. Donor evidence used (behavioral extraction only — no wholesale copy)

Per Master Plan §7A the following donors are behavioral references only. **Nothing is copied wholesale.** Every donor path is treated as "TO CONFIRM DURING PREFLIGHT" per the exact-source rule.

- **REB DocuLink** (`routes/doculink.py`, `services/doculink_storage.py`, `services/doculink_bridge.py`, `models/doculink.py`) — evidence level FSV. Reuse method **REBUILD against MVP shared services** (§7A.14). We take: (a) `Document` record shape (title, category, source_type, requires_review, current_version), (b) `document_link` cross-entity association pattern (already implemented in EC2), (c) `document_share` recipient/revocation pattern (already implemented in EC2). We reject: local-disk storage, donor auth, giant router, donor tenant helpers, `PreviewEnvelope`.
- **ORIG signatures** (`routes/signatures.py` + `services/signature_service.py`) — PSI head-only per §7A.15. Full trace happens inside this preflight. We take: single-action-token issuance shape, dual-parent (Proof/Contract/WOS) targeting, signed-PDF regeneration hook (stubbed → completed in EC6). We reject: monolithic router, dev/backup routes, preview impersonation.
- **ORIG approvals** (`routes/approvals.py`) — PSI head-only per §7A.16. Dual-parent already in donor. We take: approval action record + parent linkage. We reject: donor auth deps.
- **ORIG portal** (`routes/portal.py` — 2195 lines) — PSI head-only per §7A.27. Reuse method **REBUILD**. We take: route shape for Portal Quotes/Orders/Invoices/Payments/Documents/Proofs listings; portal-identity scoping filter idea. We reject: preview-user impersonation, permissive public routes, parallel Customer/Invoice/Payment collections.

## 4. Classification

| Element | Class | Note |
|---|---|---|
| `Attachment` (MVP) | KEEP | Authoritative for existing staff attachments |
| `FileRecord` (MVP) | KEEP + EXTEND | Add optional `document_id` FK, portal-visibility flag |
| `FileLink`, `DocumentLink`, `DocumentShare` (EC2) | KEEP + EXTEND | EC6 fills in the mint-token / revoke-token flow |
| Staff JWT (`core/security.py`) | KEEP | Untouched. Portal JWT is separate. |
| `documents` collection | **NEW (REBUILD)** | Asset-library metadata layer over stored files |
| `proofs` + `proof_versions` collections | **NEW (REBUILD)** | Parent = OrderItem or Order or WorkOrder |
| `approvals` collection | **NEW (REBUILD)** | Dual-parent (Proof / Contract / Work Order Summary) |
| `signature_requests` + `signatures` collections | **NEW (REBUILD)** | Portal + public-action-token surfaces |
| `portal_identities` collection | **NEW (REBUILD)** | Separate from `users`; `sub_scope="portal"` JWT |
| `magic_link_tokens` collection | **NEW (REBUILD)** | Signed, expiring, single-use |
| `public_action_tokens` collection | **NEW (REBUILD)** | Bound to ONE terminal action |
| `portal_sessions` (optional) | **NEW** | If we want portal-JWT revocation; deferred if not required by exit conditions |
| Employee Portal | OUT OF EC6 | Explicitly EC8 per master plan §7A.28 |
| Webstore Portals + Public Storefront | OUT OF EC6 | Explicitly CP7/EC9 per §7A.29+ |
| Full Forms + Questionnaires builder | OUT OF EC6 | Only minimum required by approved customer workflows lands here |
| SMS/MMS | OUT OF EC6 | Per D27 → EC14 |
| ACH portal payments | OUT OF EC6 | Per D22 |

## 5. Schema additions (additive; nothing destructive)

### 5.1 `documents` collection

```
id, tenant_id, title, category, source_type=("upload"|"generated"|"external"),
requires_review: bool, current_file_id: str, version: int=1,
description?: str, tags: list[str]=[], visibility=("internal"|"customer_visible"),
created_by, created_at, updated_at, archived: bool=False
```
Indexes: unique `id`; `(tenant_id, category, created_at)`; `(tenant_id, current_file_id)`.
`Attachment` and `FileLink` continue to point at underlying `file_id`s; documents are the metadata layer.

### 5.2 `proofs` + `proof_versions`

```
proofs: id, tenant_id, number, parent_type=("order"|"order_item"|"work_order"),
        parent_id, title, current_version: int=1, current_file_id?: str,
        status=("draft"|"sent"|"viewed"|"approved"|"changes_requested"|"cancelled"|"superseded"),
        due_at?, created_by, created_at, updated_at
proof_versions: id, tenant_id, proof_id, version, file_id, notes,
                sent_at?, viewed_at?, approved_at?, changes_requested_reason?,
                created_by, created_at
```
Indexes: unique `(tenant_id, number)` on `proofs`; `(tenant_id, parent_type, parent_id)`; unique `(tenant_id, proof_id, version)` on `proof_versions`.

### 5.3 `approvals`

```
id, tenant_id, parent_type=("proof"|"contract"|"work_order_summary"|"quote"),
parent_id, parent_version?, action=("approve"|"request_changes"|"decline"),
reason?, actor_type=("portal_customer"|"public_token"|"staff"),
actor_ref, ip?, user_agent?, created_at
```
Indexes: unique `id`; `(tenant_id, parent_type, parent_id, created_at)`.

### 5.4 `signature_requests` + `signatures`

```
signature_requests: id, tenant_id, number, parent_type=("proof"|"contract"|"work_order_summary"|"quote"|"document"),
                    parent_id, parent_version?, required_signers: list[{name,email,role}],
                    status=("draft"|"sent"|"partially_signed"|"completed"|"cancelled"),
                    created_by, created_at, sent_at?, completed_at?,
                    signed_pdf_file_id?  # regenerated composite
signatures: id, tenant_id, request_id, signer_name, signer_email,
            signature_type=("drawn"|"typed"),
            signature_data_ref,  # file_id of signature raster/SVG
            ip?, user_agent?, token_used?, signed_at
```
Indexes: unique `(tenant_id, number)` on `signature_requests`; `(tenant_id, parent_type, parent_id)`; `(tenant_id, request_id)` on `signatures`.

### 5.5 `portal_identities`

```
id, tenant_id, customer_id, email (lowercased), password_hash?,
full_name?, phone?, status=("active"|"disabled"),
last_login_at?, magic_link_only: bool=False,
created_at, updated_at
```
Indexes: unique `id`; unique `(tenant_id, email)`; `(tenant_id, customer_id)`; `(tenant_id, status)`.

### 5.6 `magic_link_tokens`

```
id, tenant_id, portal_identity_id, token_hash (sha256), purpose="login",
expires_at, single_use: bool=True, consumed_at?, ip_issued?, created_at
```
Indexes: unique `id`; unique `token_hash`; `(tenant_id, portal_identity_id, expires_at)`.
Raw token never stored — only sha256(hash).

### 5.7 `public_action_tokens`

```
id, tenant_id, token_hash (sha256),
action=("proof_approve"|"proof_request_changes"|"sign"|"quote_view"|"invoice_view"|"invoice_pay"),
parent_type, parent_id, parent_version?,
audience_email?,   # optional binding
expires_at, single_use: bool=True, consumed_at?, ip_issued?,
issued_by,  # staff user_id
created_at
```
Indexes: unique `id`; unique `token_hash`; `(tenant_id, action, parent_type, parent_id)`; `(tenant_id, expires_at)`.

### 5.8 Existing collections extended (additive fields only)

- `file_records`: add optional `document_id: str | None` (backref to `documents.id`).
- `document_shares` (EC2): add `token_id: str | None` referring to the `public_action_tokens` row that was minted for the share. Existing rows continue to work; token minting is new.

## 6. Files to add / modify

**Add — backend**
- `backend/app/models/{document,proof,proof_version,approval,signature_request,signature,portal_identity,magic_link_token,public_action_token}.py`
- `backend/app/services/{documents_service,proofs_service,approvals_service,signatures_service,portal_identity_service,portal_auth_service,public_tokens_service}.py`
- `backend/app/routers/{documents_meta,proofs,approvals,signatures,portal_auth,portal_customer,public_actions}.py`
  - `documents_meta` mounts at `/api/documents` (metadata layer over existing `/api/files`).
  - `portal_auth` mounts at `/api/portal/auth/*` (login, magic-link request, magic-link verify, logout, me).
  - `portal_customer` mounts at `/api/portal/*` (quotes, orders, invoices, payments, proofs, documents, messages).
  - `public_actions` mounts at `/api/public/*` (token-verify, proof_approve, proof_request_changes, sign, quote_view, invoice_view, invoice_pay-intent).
- `backend/app/deps_portal.py` — portal auth deps (`get_current_portal_identity`, `require_portal_permission`, `resolve_public_token`) fully separate from staff `deps.py`.
- `backend/tests/test_documents_ec6.py`, `test_proofs_ec6.py`, `test_signatures_ec6.py`, `test_approvals_ec6.py`, `test_portal_auth_ec6.py`, `test_portal_customer_ec6.py`, `test_public_actions_ec6.py`, `test_ec6_cross_tenant.py`, `test_ec6_permission_matrix.py`.

**Add — frontend**
- Portal shell (no staff sidebar, no dev banner):
  - `frontend/src/portal/PortalApp.jsx` (independent router mounted from `App.js` at `/portal/*`).
  - `frontend/src/portal/PortalAuthContext.jsx`, `frontend/src/portal/portalApi.js`, `frontend/src/portal/PortalShell.jsx`.
  - `frontend/src/portal/pages/{PortalLoginPage,PortalMagicLinkPage,PortalDashboardPage,PortalQuotesPage,PortalQuoteDetailPage,PortalOrdersPage,PortalOrderDetailPage,PortalInvoicesPage,PortalInvoiceDetailPage,PortalPaymentPage,PortalDocumentsPage,PortalProofPage,PortalSignPage,PortalProfilePage}.jsx`.
- Public single-action pages (unauthenticated, token-scoped) mount at `/p/*`:
  - `frontend/src/public/PublicApp.jsx` + `{PublicProofApprovePage,PublicSignPage,PublicQuoteViewPage,PublicInvoiceViewPage,PublicInvoicePayPage}.jsx`.
- Staff-side additions inside existing shell:
  - `frontend/src/components/documents/DocumentsMetaPanel.jsx`, `ShareToCustomerDialog.jsx`, `MintTokenDialog.jsx` (used from Documents + Quote/Order/Invoice detail pages).
  - `frontend/src/components/proofs/ProofsPanel.jsx`, `ProofUploadDialog.jsx`, `ProofSendDialog.jsx` (mounted on Order & Work Order detail pages).
  - `frontend/src/components/signatures/SignatureRequestPanel.jsx`, `SignatureRequestDialog.jsx`.
  - `frontend/src/components/portal/PortalAccessPanel.jsx` on the Customer detail page (issue portal identity, resend magic link, disable/re-enable).

**Modify — backend**
- `backend/server.py` — register new routers.
- `backend/app/core/db.py::ensure_indexes` — add the indexes listed in §5.
- `backend/app/core/security.py` — add `create_portal_token(portal_identity_id, tenant_id)` + `decode_portal_token(token) -> claims with sub_scope="portal"`. Staff `create_access_token` untouched.
- `backend/app/core/permissions.py` — no new staff perms (already covered by EC1). Add helper `PORTAL_CUSTOMER_DEFAULT_SET` (view + approve + sign + pay + message) so a portal identity gets a permission bundle by default; owner can toggle bundle bits via a new staff endpoint if scope allows (may defer to EC12).

**Modify — frontend**
- `frontend/src/App.js` — mount `<PortalApp>` on `/portal/*` and `<PublicApp>` on `/p/*` **outside** the staff `<AppShell>`.
- `frontend/src/pages/{QuoteDetailPage,OrderDetailPage,InvoiceDetailPage,WorkOrderDetailPage,CustomerDetailPage}.jsx` — surface EC6 panels/dialogs where documented above.
- `frontend/src/lib/navigation.js` — mark previously disabled Asset Library entry as enabled (points at existing `/documents` staff page).

## 7. Rules (LOCKED)

- **Private-by-default.** Every file remains inaccessible without either (a) staff JWT + `document:read` for that tenant, (b) a live portal session with matching customer scope, or (c) a valid unconsumed `public_action_token`.
- **Portal JWT ≠ Staff JWT.** Staff `Depends(get_current_user)` must reject any token with `sub_scope="portal"` (status 401). Portal deps reject any staff token likewise. Two dependency graphs, zero crossover — this is the LOCKED separation.
- **Magic links** are signed, expiring, and single-use. Token raw value is delivered by email only; database stores SHA-256 hash only.
- **Public single-action tokens** are single-use for terminal actions (approve, request-changes, sign, pay-intent-init). Multi-view tokens (quote_view, invoice_view) may permit multiple GETs before expiry but never authorize writes beyond the bound action.
- **Portal customer scope** filters every list/detail query by `portal_identity.customer_id`. Cross-customer requests inside the same tenant → 404.
- **Every EC6 write endpoint** writes an audit event (via EC1 `record_audit`) and an activity event (via EC2 `record_activity_with_audit` where staff-visible). Portal writes carry `actor_type=portal_customer` and `actor_ref=portal_identity.id`.
- **Notifications** — approvals, signatures, revision requests, portal payments notify assigned staff via EC2 notifications helper. Emails via EC2 `email.send` helper (SendGrid).
- **Portal payments** initiate via EC4 `services/stripe_core.py` — no new Stripe surface, no ACH.
- **Feature entitlement** — EC6 features are all in Core, so no `require_entitlement` guard is applied for basic asset library / proofs / signatures / customer portal. (Wrap-lab-only proofs will layer entitlement in EC10.)
- **Money policy** unchanged (`_cents` on the wire and stored). Portal payment endpoints only pass through EC4 amounts.
- **Terminology** — "customer" / "portal" / "proof" / "signature" / "approval" / "document" / "share" / "revision request". No `job_*` anywhere.

## 8. Test plan (green before EC6 close-out)

Backend suites the EC6 exit must pass:

- `test_documents_ec6.py` — document create + link + share; visibility gates; document ↔ file version bump.
- `test_proofs_ec6.py` — proof lifecycle (draft → sent → viewed → approved / changes_requested → superseded); version bump; parent linkage; tenant isolation.
- `test_signatures_ec6.py` — signature request lifecycle; single-signer & multi-signer completion; signed-pdf regeneration hook fires.
- `test_approvals_ec6.py` — dual-parent approvals; reasons required for `request_changes`/`decline`; audit + activity written; notifications enqueued.
- `test_portal_auth_ec6.py` — password login + magic-link issue + magic-link verify + logout; portal JWT NEVER accepted on staff routes; staff JWT NEVER accepted on portal routes; brute-force lockout (5 fails → 15 min lock, coarse-grained).
- `test_portal_customer_ec6.py` — portal identity sees only its `customer_id`; cross-customer 404; portal invoice pay creates a Payment via EC4 core (dev-simulated confirm); portal message routes to email + notification.
- `test_public_actions_ec6.py` — mint token → verify → consume; consumed token → 410 gone; expired → 410; single-use enforcement; audience_email binding rejected on mismatch.
- `test_ec6_cross_tenant.py` — sweeps every new collection for cross-tenant leakage (both staff and portal routes).
- `test_ec6_permission_matrix.py` — staff `document:*`, `document:share`, `portal:customer_*` bundle coverage.

Regression: existing 143 EC1–EC5 tests remain green.

## 9. Compatibility

- Additive schema. No destructive changes to `file_records`, `attachments`, `file_links`, `document_links`, `document_shares`.
- Existing MVP `/api/files/*` router untouched; the new `/api/documents/*` router owns metadata + share-token minting.
- Staff `AuthContext.jsx` untouched. Portal `PortalAuthContext.jsx` is a **separate** context, not a subclass.
- Feature gates — no changes required to EC2 entitlements.

## 10. Rollback

- All new collections + all new routers are additive. Rollback = drop new collections, remove new routers/models/services, drop new frontend `/portal` and `/p` routes.
- No index-only migrations that mutate existing docs.
- New portal JWT secret uses the existing `JWT_SECRET_KEY` env var with a scoped claim; no new env vars introduced (EC6 does not require a new production secret).

## 11. Proposed EC6 execution phases (all inside a single execution checkpoint — this is scope structuring, not sub-checkpointing)

To keep risk local and testing tight, EC6 will land in 4 tight batches with pytest green after each. **No batch is a separate EC.** Nothing publishes to a customer until batch 4.

1. **6a — Asset Library metadata + share-token infra.** `documents` model + service + router; `mint_public_action_token` helper (used later); staff-side share dialog; tests. No portal yet.
2. **6b — Proofs + Approvals + Signatures backend + staff UI.** Full lifecycle + notifications + email + audit + activity. Public-token issuance available but not yet consumable by public pages.
3. **6c — Portal identity + Portal Auth + Portal Customer routes + public-action-token endpoints.** Portal JWT separation enforced; magic-link + password login; portal listings.
4. **6d — Portal frontend + public single-action pages + docs + evidence + `testing_agent_v3_fork`.** Portal pages, public token pages, cross-tenant + permission-matrix regression, evidence package, docs.

Each phase writes to `progress_register.md`; the checkpoint is only marked COMPLETE after phase 6d green and evidence package produced.

## 12. Owner decisions (LOCKED for EC6)

1. **Portal payments** — Stripe card via EC4 Stripe Core only. ACH deferred. Manual Payment is a staff-only action; portal users may only view manual Payments after staff reconciliation as read-only history. **No customer-created manual payments.** No portal-specific payment collection.
2. **Portal messages** — customer-scoped read-only communication history + "Send message" that routes through the existing `services/email.py`. **No new `portal_messages` collection.** Only communications explicitly flagged customer-visible are shown; internal notes, provider IDs, webhook metadata, bounce diagnostics, staff-only recipients, and internal delivery details are excluded. Portal message recipients + Customer + tenant + related-record resolution happen entirely on the backend — the client provides only `subject/body/related_entity_ref?`. Rate limit + audit every portal-originated message.
3. **Portal identity → Customer** — **n:1**. Multiple portal identities per Customer (owner, billing, purchasing, project, proof approver, etc.), each with a **backend-enforced permission bundle**. Presets: `owner_full`, `billing_only`, `approver_only`, `viewer_only`, `custom`. One portal identity belongs to exactly one tenant and one Customer.
4. **Approval parent types** — `quote_revision`, `proof_version`, `contract` (a document flagged as contract), `order_item` (where genuinely required), `work_order_summary`. Approval NEVER silently changes pricing / invoice status / payment status / production completion / unrelated Order Items. Any resulting operational transition goes through the owning module's service (EC3 order status, EC5 work-order transition) and is audited.
5. **Forms scope** — build **Public Quote Request** and **Public Customer Intake** only. **No** full Forms Builder, **no** general Questionnaires Builder. Public Quote Request creates/matches a tenant-scoped Lead or Customer via approved duplicate-detection and creates a `draft_quote_request` (NOT an approved `sent` Quote). Public Customer Intake is sent to a known Customer via an expiring scoped token; original response stored; changes staged for staff review — no silent overwrite of authoritative Customer data. Approved attachments only. Spam + captcha + rate limit on the public quote request; token binding on customer intake. Both write audit + activity. Public users may NOT supply `tenant_id`, prices, quote status, assigned staff, approval state, or internal notes.
6. **ORIG behavioral discovery scope** — customer proof delivery, customer approval & revision requests, signature-request behavior, customer document visibility, customer Quote/Order visibility, customer Invoice/Payment presentation, public intake & quote-request behavior, portal communication history, customer profile behavior. **Reject** ORIG authentication, tenant handling, Customer models, file storage, Payment systems, portal authorization, and route structure.

### Locked EC6 constraints (all authoritative)

- Portal Identity records are separate from staff User records.
- Portal JWTs use `sub_scope="portal"` and a fully separate dependency graph. Staff JWTs never authorize portal routes; portal JWTs never authorize staff routes.
- Magic-link tokens are single-use, hashed at rest (SHA-256), expiring, and audience-scoped (bound to `portal_identity_id`).
- Public action tokens are single-purpose (one action), expiring, revocable, hashed at rest, and bound to the exact `parent_type + parent_id + parent_version`. Proof-approval tokens do NOT grant general portal access. Invoice-payment tokens do NOT grant access to unrelated customer records.
- Raw tokens NEVER stored in DB records, logs, analytics, or activity metadata. Tokens are delivered by email once; only hashes persist.
- No unrestricted public document URLs. Customer-visible documents require either an intentional share record OR a scoped token.
- Every portal query resolves tenant + Customer ownership on the backend. `tenant_id`, `customer_id`, permissions, approval state, price, balance, and record ownership are never trusted from the client.
- Reuse: EC2 (files, links, shares, notifications, email, activity, audit, webhooks); EC3 (Quote/Order services); EC4 (Invoice/reconciliation/Payment/Stripe Core); EC5 (Work Order + Summary).
- No parallel file, document, approval, signature, Customer, Invoice, Payment, or authentication systems.
- Immutable: proof versions, approval records, signature evidence, customer-action history.
- Idempotency: every portal write endpoint that could cause duplicates (approvals, signatures, portal messages, portal payment intent) uses request-scoped idempotency.
- Rate-limit portal + public auth routes and the portal-message-send route.
- Never expose internal pricing, profit, margin, private notes, staff-only attachments, audit metadata, or platform information on the portal or public surfaces.
- Stop after EC6. Do not begin EC7.

### Execution protocol (approved)

Phases 6a → 6b → 6c → 6d run as internal implementation phases. **No pause between phases** unless: inspected code conflicts with this preflight, a security decision is not covered above, a destructive data migration becomes necessary, or a scope conflict with the master plan is discovered. Otherwise: complete EC6, run backend + frontend test suites, produce the evidence package, stop before EC7.
