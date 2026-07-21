# Security Correction Checkpoint 2 Evidence

## Starting-Point Verification

- VERIFIED_REPOSITORY_FACT: Branch: `CODEX-ux1-branch`.
- VERIFIED_REPOSITORY_FACT: Checkpoint 1 commit: `8c3acdb7a8454113674f11074576f10a4ba42011`.
- VERIFIED_REPOSITORY_FACT: Checkpoint 1 commit message: `Security: enforce tenant isolation and add platform creator role`.
- VERIFIED_REPOSITORY_FACT: Checkpoint 1 was pushed to `origin/CODEX-ux1-branch`.
- VERIFIED_REPOSITORY_FACT: `origin/main`: `b06589e4ba71d4296a7986c7ca918af84e3607d8`.
- VERIFIED_REPOSITORY_FACT: Ahead/behind versus `origin/CODEX-ux1-branch` before Checkpoint 2 changes: `0	0`.
- VERIFIED_REPOSITORY_FACT: Most recently completed checkpoint: Security Correction Checkpoint 1.
- VERIFIED_REPOSITORY_FACT: Platform creator bootstrap script was not executed.
- VERIFIED_REPOSITORY_FACT: UX1 and later checkpoint implementation were not started as part of this checkpoint.

## Authoritative Requirements Used

- DOCUMENTED_REQUIREMENT: `docs/security/EC2_SECURITY_POSTURE.md` requires tenant isolation, fail-closed defaults, and secret minimization.
- DOCUMENTED_REQUIREMENT: `docs/security/production_startup_guards.md` documents production-only safety gates and dev-only surface expectations.
- DOCUMENTED_REQUIREMENT: `docs/architecture/EC6_ASSET_LIBRARY_AND_PORTAL.md` requires separate staff and portal auth graphs, hashed magic/public tokens, single-purpose public tokens, scoped portal reads, and public-token writes through owning services.
- DOCUMENTED_REQUIREMENT: `docs/architecture/permission_catalog.md` requires staff, platform, and portal permission scopes to remain disjoint.
- DOCUMENTED_REQUIREMENT: `docs/modules/ec14_webstores.md` requires public storefront lookup to serialize only public product data.
- DOCUMENTED_REQUIREMENT: `docs/modules/ec18_business_assistant.md` requires Business Assistant tenant isolation, entitlement and permission enforcement, source-linked deterministic answers, confirmation before mutations, and no direct EC4 payment/invoice mutations.
- DOCUMENTED_REQUIREMENT: `evidence/EC18_REQUIREMENTS_TRACEABILITY_AUDIT.md` records EC18 traceability and remaining intentionally partial live/provider acceptance items.

## Portal and Public-Token Inventory

| Surface | File/symbol | Route | Auth/token | Boundary | Status | Correction/test |
|---|---|---|---|---|---|---|
| Customer portal auth login | `backend/app/routers/portal_auth.py::login` | `POST /api/portal/auth/login` | email/password plus tenant slug | tenant + active portal identity | SAFE_AFTER_CORRECTION | response identity allowlist; tenant-scoped login state updates |
| Customer portal magic-link request | `portal_auth.py::request_magic_link` | `POST /api/portal/auth/magic-link` | open request, rate-limited | tenant slug + email, non-enumerating response | SAFE | raw token generated once and emailed; hash stored |
| Customer portal magic-link verify | `portal_auth.py::verify_magic_link` | `POST /api/portal/auth/magic-link/verify` | raw magic link token | token hash + tenant + portal identity | SAFE_AFTER_CORRECTION | response identity allowlist; tenant-scoped last-login update |
| Customer portal current identity | `portal_auth.py::me` | `GET /api/portal/auth/me` | portal JWT | active identity + token type | SAFE_AFTER_CORRECTION | response identity allowlist |
| Customer portal quote/order/invoice lists/details | `backend/app/routers/portal_customer.py` | `/api/portal/quotes`, `/orders`, `/invoices` | portal JWT permissions | tenant + customer from identity | SAFE_AFTER_CORRECTION | explicit allowlists for documents and child line/payment rows |
| Customer portal Stripe intent | `portal_customer.py::portal_initiate_stripe` | `POST /api/portal/invoices/{id}/stripe-intents` | portal JWT pay permission | tenant + customer invoice, shared EC4 service | SAFE_AFTER_CORRECTION | response allowlist preserves only client-needed Stripe.js fields |
| Customer portal documents/proofs/messages/profile | `portal_customer.py` | `/api/portal/documents`, `/proofs`, `/messages`, `/profile` | portal JWT permissions | tenant + customer from identity | SAFE_AFTER_CORRECTION | explicit allowlists; profile reread tenant-scoped |
| Employee portal | `backend/app/routers/portal_employee.py` | `/api/portal/employee/*` | employee portal JWT | tenant + employee from identity | SAFE_WITH_REMAINING_REVIEW | existing self-scope helpers and field strips; broad service response review remains medium follow-up |
| Webstore owner portal | `backend/app/routers/webstore_owner_portal.py`, `backend/app/services/webstores.py` | `/api/portal/webstores/*` | webstore owner/manager portal JWT | tenant + webstore owner from identity | SAFE_AFTER_CORRECTION | owner list/detail now returns public-safe store/product/packet views |
| Public token introspection | `backend/app/routers/public_actions.py::introspect` | `GET /api/public/token/introspect` | raw public token | hash + expiry + revoke + consumption state | SAFE_AFTER_CORRECTION | no longer echoes bound parent id |
| Public quote/invoice/proof/signature reads | `public_actions.py` | `/api/public/quotes/{id}`, `/invoices/{id}`, `/proofs/{id}`, `/signatures/{id}` | raw public token | action + parent type + parent id + tenant | SAFE_AFTER_CORRECTION | explicit allowlists; signature signer list filtered by audience email |
| Public proof/signature/customer-intake writes | `public_actions.py` | proof action, signature sign, customer intake submit | single-purpose raw public token | action + parent record + tenant | SAFE | writes call owning services or staged intake; tokens consumed on successful writes |
| Public Decision Room | `public_actions.py`, `decision_room_portal.py`, `decision_room_service.py` | `/api/public/decision-rooms/*`, `/api/portal/decision-rooms/*` | public token or portal JWT | tenant + room + customer/token | SAFE_WITH_REMAINING_REVIEW | shared customer-safe service is already used; full response allowlist remains follow-up because service output is larger and specialized |
| Public storefront and buyer order | `backend/app/routers/public_webstores.py`, `backend/app/services/webstores.py` | `/api/public/webstores/*` | public slug, no JWT | live store + active public products | SAFE_AFTER_CORRECTION | public product/order/ledger views are allowlisted; internal ledger rows stay in DB only |
| Password reset token | `backend/app/core/security.py`, `backend/app/routers/auth.py` | auth reset routes | reset token hash | token hash + expiry | SAFE | hash storage is existing EC2/production-guard contract |
| Invitation tokens | `portal_identities.py`, `employee_portal_admin.py` | staff invitation routes | staff auth mints magic link | tenant + identity | SAFE_WITH_REMAINING_REVIEW | raw token emailed once; staff response may include raw token only at mint-time by design |

## Field-Level Exposure Findings

- HIGH VERIFIED_REPOSITORY_FACT: `portal_customer.py` returned broad internal Quote, Order, Invoice, Document, Proof, EmailLog, and child rows. Corrected with explicit allowlists.
- HIGH VERIFIED_REPOSITORY_FACT: `public_actions.py` returned broad public Quote, Invoice, Proof, and SignatureRequest documents. Corrected with explicit allowlists.
- HIGH VERIFIED_REPOSITORY_FACT: `webstores.py::create_buyer_order` returned internal Webstore ledger rows, including platform fee, owner share, production cost, and shop gross estimates. Corrected by returning only buyer-visible ledger entries.
- MEDIUM VERIFIED_REPOSITORY_FACT: Webstore owner portal list/detail previously returned broad store rows and full launch packet rows. Corrected with public-safe owner portal serializers.
- MEDIUM REASONABLE_INFERENCE: Decision Room service responses are intended customer-safe and token-scoped, but the response shape is specialized and should receive a dedicated follow-up allowlist pass if the owner wants deeper review.

## Token-Security Findings

- VERIFIED_REPOSITORY_FACT: Portal JWTs carry `sub_scope="portal"` and `typ="portal_access"` and are rejected by staff auth dependencies.
- VERIFIED_REPOSITORY_FACT: Public action tokens and magic-link tokens are generated with `secrets.token_urlsafe`, stored by SHA-256 hash, and raw values are returned only at mint-time.
- VERIFIED_REPOSITORY_FACT: Public token resolution enforces revoked, consumed, expired, expected action, expected parent type, and expected parent id.
- VERIFIED_REPOSITORY_FACT: Magic links are single-use and consumed by hash lookup.
- LOW RECOMMENDATION: Consider a future TTL cleanup/index expiration policy for consumed/expired public and magic-link tokens if not already handled operationally.

## Portal/Public Mutation Findings

- VERIFIED_REPOSITORY_FACT: Portal payment initiation is tenant/customer scoped before calling the shared EC4 payment service.
- VERIFIED_REPOSITORY_FACT: Portal and public proof actions call `record_approval` and `transition_proof`.
- VERIFIED_REPOSITORY_FACT: Public signature writes enforce token audience email when present and consume the token after successful signature.
- VERIFIED_REPOSITORY_FACT: Public customer intake stores staged changes for staff review and does not overwrite Customer records.
- VERIFIED_REPOSITORY_FACT: Webstore buyer order totals are calculated server-side from current active public products.
- MEDIUM RECOMMENDATION: Customer intake response keys beyond `tenant_id` and `id` are still accepted as raw questionnaire payload. This is acceptable for staged intake, but a future questionnaire schema should constrain allowed fields per template.

## EC18 Business Assistant Inventory

- VERIFIED_REPOSITORY_FACT: Routes are staff-authenticated through `backend/app/routers/business_assistant.py`.
- VERIFIED_REPOSITORY_FACT: `assert_assistant_access` requires `ai_assistant:use` and the `business_assistant` entitlement.
- VERIFIED_REPOSITORY_FACT: Context lookup uses server-derived tenant id and target-specific read permissions.
- VERIFIED_REPOSITORY_FACT: Structured actions require proposal and confirmation before execution.
- VERIFIED_REPOSITORY_FACT: EC18 does not call EC4 invoice/payment mutation services.
- HIGH VERIFIED_REPOSITORY_FACT: Follow-up operations after earlier tenant checks used bare-id filters in source-citation message linking, stale proposal marking, memory upsert/reread/delete, insight dismiss/reread, and voice usage update/reread. Corrected to include tenant/user/conversation scope as appropriate.

## Corrections Implemented

- `backend/app/services/business_assistant.py`: tenant/user/conversation-scoped follow-up update/reread operations.
- `backend/app/services/portal_identity.py`: tenant-scoped portal identity reread and login lockout/reset updates.
- `backend/app/routers/portal_auth.py`: tenant-scoped magic-link login update and allowlisted identity responses.
- `backend/app/routers/portal_customer.py`: allowlisted customer-portal response payloads and scoped profile reread.
- `backend/app/routers/public_actions.py`: allowlisted public token reads, no parent id in introspection, audience-filtered signature signer list.
- `backend/app/services/webstores.py`: allowlisted public product/store/order/ledger output and owner-portal list/detail output.
- `backend/tests/test_ec14_webstores.py`: updated internal ledger assertions to read internal rows directly instead of relying on public response leakage.
- `backend/tests/test_security_correction_checkpoint2.py`: added focused regressions.

## Tests Added

- `test_customer_portal_quote_invoice_and_message_responses_are_allowlisted`
- `test_public_token_reads_are_record_bound_and_field_allowlisted`
- `test_public_webstore_buyer_response_excludes_internal_commerce_rows`
- `test_ec18_followup_database_operations_remain_tenant_scoped`

## Verification Commands and Results

- PASS: `C:\Users\thesi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_security_correction_checkpoint2.py tests/test_ec6_portal_docs.py tests/test_ec6_portal_payment.py tests/test_ec14_webstores.py tests/test_ec18_assistant_foundation.py tests/test_ec18_assistant_voice.py -q -n 0`
  - Result: `32 passed, 2 warnings`.
- FAIL_THEN_FIXED: `C:\Users\thesi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/ -q -n 0`
  - First result: `1 failed, 687 passed, 3 skipped, 3 warnings`.
  - Failure: employee portal activation expected `employee_id` in the portal identity response.
  - Fix: preserved portal identity scoped record IDs in `_public_identity` while still excluding tenant/password/counter/lockout internals.
- PASS: `C:\Users\thesi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/ -q -n 0`
  - Result: `688 passed, 3 skipped, 3 warnings`.
- PASS: `C:\Users\thesi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/ -q`
  - Result: `688 passed, 3 skipped, 6 warnings`.
- PASS: `C:\Users\thesi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m compileall app tests`
- PASS: `git diff --check`
  - Result: no whitespace errors; Git emitted CRLF conversion warnings only.
- PASS: EC18 unscoped follow-up search found no targeted bare-id follow-up operations in `backend/app/services/business_assistant.py`.
- PASS: Portal/public protected-field search reviewed after final edits. Remaining matches are internal calculations, dev-only payment simulation internals, token-hash removal, or test fixtures/assertions, not public/portal serialized response paths.
- NOT_RUN: frontend tests/build. Reason: no frontend files changed in Checkpoint 2.

## Remaining Security Risks

- MEDIUM RECOMMENDATION: Decision Room customer-safe service output should receive a dedicated allowlist pass in a later security batch because it is specialized and larger than the core portal/public read serializers corrected here.
- MEDIUM RECOMMENDATION: Employee Portal service-returned payloads should receive a dedicated field minimization review by subdomain, especially tasks, communications, time-off, calendar, and production views.
- LOW RECOMMENDATION: Add operational cleanup for expired/consumed public and magic-link token rows if not already covered outside code.
- INFORMATIONAL VERIFIED_REPOSITORY_FACT: Portal/public response minimization preserves the portal identity's own scoped record IDs (`customer_id`, `employee_id`, `webstore_owner_id`, `webstore_id`) where the existing portal UI/tests require them, while excluding `tenant_id`, password fields, counters, and lockout state.

## Files Modified

- `backend/app/routers/portal_auth.py`
- `backend/app/routers/portal_customer.py`
- `backend/app/routers/public_actions.py`
- `backend/app/services/business_assistant.py`
- `backend/app/services/portal_identity.py`
- `backend/app/services/webstores.py`
- `backend/tests/test_ec14_webstores.py`
- `backend/tests/test_security_correction_checkpoint2.py`
- `evidence/SECURITY_CORRECTION_CHECKPOINT_2.md`

## No-Unrelated-Work Confirmation

- VERIFIED_REPOSITORY_FACT: No UX1, EC20, EC21, EC22, Stripe catalog creation, Checkout Session, subscription, billing portal, webhook, order-source field, Workspace Dock, Dashboard Customizer, Advanced Onboarding, or Admin Communication Center work was started.
- VERIFIED_REPOSITORY_FACT: Checkpoint 2 remains uncommitted and unpushed for owner review.
