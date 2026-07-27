# Complete Code Review and Rebuild Safeguard Audit

Review date: 2026-07-27
Repository: `C:\Users\thesi\Documents\GitHub\SIGNGUY-MVP`
Branch reviewed: `main`
Commit reviewed: `0ff8c323807b4cd568f0c3c9c7f87e6e3beefdde`
Workspace Dock commit included: `2aa4e0fe0082a487b69e82335b46490e1a213c6f`
Established integration branch: `main` (`origin/HEAD -> main`)

## 1. Executive Verdict

Verdict after correction checkpoint: **P1/P2 CORRECTIONS IMPLEMENTED - AWAITING REVIEW**

Correction checkpoint note (2026-07-27): this audit originally recorded `CORRECTIONS REQUIRED - BUILD MAY CONTINUE WITH RESTRICTIONS`. The dedicated correction checkpoint has now addressed the recorded P1/P2 findings in code and tracking:

- F-001: runtime dependencies on retired provider URLs/assets were removed from backend storage, Google auth configuration, frontend HTML/scripts, dependency manifests, and integration-status reporting. `.env.example` now lists placeholder variable names only, and `.env` remains ignored by Git.
- F-002: AI gateway request payloads now reject caller-supplied credit-charge fields; billable charges are derived only from the active capability contract, with atomic credit reserve/commit behavior.
- F-003: Workspace Dock state now has revision-based database compare-and-set writes with retry, protecting the max-open rule beyond a single process lock.
- F-004: existing Phase 9I tracking documents now record `PHASE 9I-H REVIEW PASSED` without closing deferred later Phase 9I scope.
- F-005: document upload routes now use the shared validator for MIME, extension, magic-byte, size, safe filename, and safe download headers.
- F-006: the identified post-write rereads were made tenant-scoped, including customer update, file visibility update, and assistant voice-session usage update.
- F-007: router/service decomposition remains a documented architecture discipline for future modules; no broad refactor was attempted during this correction checkpoint.
- F-008: production startup guards now reject unsafe hosted/deployment context, wildcard CORS, missing production object-storage path, unsupported storage backend, and missing configured Google auth endpoint.
- F-009: Stripe refunds now net pending and confirmed prior refunds and support idempotent replay by `Idempotency-Key`.
- F-010: giant route registries remain deferred because refactoring stable routing was outside the safe correction scope.
- F-011: frontend API base now has a local development fallback and explicit production misconfiguration logging.
- F-012: public HTML branding/assets were corrected.

Correction verification evidence:

- Focused correction suite: `69 passed, 6 warnings`.
- Full backend suite: `841 passed, 3 skipped, 6 warnings`.
- Full frontend suite: `16 test suites passed, 70 tests passed`.
- Frontend production build: passed.
- Backend compile/import validation: passed.
- `git diff --check`: passed with CRLF conversion warnings only.
- Active runtime dependency scan over backend/frontend/package/runtime paths: no Emergent URL, package, environment-key, or fallback references found.
- `.env`, `backend/.env`, and `frontend/.env` remain ignored by Git; generated local object-storage data under `backend/.data/` is ignored.

The application is materially better structured than the original donor-style app: it is a modular FastAPI/React app, most business records are tenant-scoped, the pricing calculator recovery reuses backend authority, the shell correction removed the rejected desktop flyout, and the Workspace Dock is persisted per tenant/user.

Before this correction checkpoint, the repository still recreated several original-rebuild hazards:

- It still depends on Emergent-specific runtime services and branding in Google auth, object storage, frontend HTML, and dependency manifests.
- The AI gateway allows caller-supplied credit charges, which lets a normal AI user request a billable capability at `0` credits.
- Workspace Dock's eight-open-workspace limit is enforced only by process-local locking and full-document replacement, so it is not safe across multiple backend instances.
- File upload validation is MIME-prefix based and accepts `application/octet-stream`; extension and safe response-header handling are incomplete.
- Several stable modules still use router-level direct database logic and unscoped rereads after scoped writes, which violates the locked tenant-filter discipline even where globally unique IDs reduce immediate exposure.

Record Numbering may continue if it is isolated to sequence/document numbering and includes atomic tenant-scoped tests. Control Center may continue as a bounded configuration/administration checkpoint using the new startup/configuration guard contracts. Platform Administration may now proceed to a dedicated implementation/review checkpoint because the P1 deployment, AI-credit, Workspace Dock atomicity, and Phase 9I-H status blockers have been corrected; it must still include focused platform-role and tenant-boundary tests for any new platform-admin surface.

## 2. Repository and Commit Reviewed

- `git status --short --branch`: `## main...origin/main`
- `git rev-parse --abbrev-ref HEAD`: `main`
- `git rev-parse HEAD`: `0ff8c323807b4cd568f0c3c9c7f87e6e3beefdde`
- `git merge-base --is-ancestor 2aa4e0fe0082a487b69e82335b46490e1a213c6f HEAD`: included
- `git remote show origin`: `HEAD branch: main`; local `main` pushes to remote `main` and is up to date
- Starting working tree: clean

## 3. Authoritative Documents Used

- `memory/AGENT_INSTRUCTIONS.md`
- `SIGNGUY_AI_FINAL_MASTER_BUILD_PLAN.md`
- `SIGNGUY_AI_FINAL_SCOPE_AND_DECISION_REGISTER.md`
- `SIGNGUY_AI_FEATURE_READINESS_MATRIX.md`
- `SIGNGUY_AI_REPOSITORY_AND_ARCHITECTURE_SOURCE_MAP.md`
- `memory/documentation_authority_register.md`
- `memory/MASTER_CHECKPOINT_CHECKLIST.md`
- `memory/PRD.md`
- `memory/checkpoint_reference_table.md`
- `memory/progress_register.md`
- `memory/owner_specification_hold_register.md`
- Current code under `backend/app/**` and `frontend/src/**`

Key locked rules traced:

- `SIGNGUY-MVP` is the permanent product; donor repos are read-only references (`memory/AGENT_INSTRUCTIONS.md:15-17`, `SIGNGUY_AI_FINAL_MASTER_BUILD_PLAN.md:79-85`).
- Money storage uses integer `_cents`; Decimal is used inside pricing; single conversion boundary (`memory/AGENT_INSTRUCTIONS.md:24-28`, `SIGNGUY_AI_FINAL_MASTER_BUILD_PLAN.md:108-114`).
- Backend permissions are authoritative and staff/platform/portal scopes are disjoint (`memory/AGENT_INSTRUCTIONS.md:34-42`).
- New modules use model/repository/router/service boundaries; routers stay thin (`memory/AGENT_INSTRUCTIONS.md:44-47`).
- No missing tenant filters, no base64-in-Mongo, no production dev bypass, no giant app/router files, no AI before credit metering and cost controls (`memory/AGENT_INSTRUCTIONS.md:79-94`).
- Production startup guards, private object storage, webhook signature/idempotency requirements, and tenant-scoped indexes are locked (`SIGNGUY_AI_FINAL_MASTER_BUILD_PLAN.md:116-130`).

## 4. System Inventory

Backend inventory:

- FastAPI root: `backend/server.py`
- Core: configuration, database/index creation, money, permissions, security, startup guards, user serialization
- Models: 80 Python model files
- Routers: 85 Python router files
- Services: 105 Python service files
- Registered endpoint decorators found: 894
- Major domains: auth/users/tenants, customers, quotes, orders, work orders, invoices/payments, documents/files, email, audit/activity, pricing, saved calculations, inventory/purchasing, expenses/finance/tax/reports, team/schedule/payroll/training, portals/public actions, decision rooms/templates/markup, commercial billing, webstores, wrap lab, AI gateway/studio/business assistant, onboarding/help/community, workspace dock

Frontend inventory:

- React entry/routes: `frontend/src/App.js`
- Authenticated shell: `frontend/src/components/app-shell/AppShell.jsx`
- Navigation source: `frontend/src/lib/navigation.js`
- Frontend route definitions found in `App.js`: 93
- Pages: 79
- Major components: app shell, commerce dialogs, pricing, workspace dock, notifications, assistant, portal/employee portal, decision room, production, UI primitives

Environment/dependencies:

- Backend env is read by `backend/app/core/config.py`.
- Frontend API base comes from `REACT_APP_BACKEND_URL` in `frontend/src/lib/api.js`.
- Object storage uses the Emergent storage endpoint and `EMERGENT_LLM_KEY`.
- Google sign-in uses Emergent-managed OAuth session exchange.
- Frontend package manifest still pulls an Emergent visual-edit dependency.

## 5. Original Rebuild Safeguards Checked

Passed or mostly satisfied:

- Permanent repo and donor-read-only principle are documented and this review was performed on `SIGNGUY-MVP`.
- Most core record reads and writes include tenant scope.
- Staff routes reject portal tokens through the auth dependency.
- Commerce totals use backend derivation in representative Quote/Order paths.
- Pricing calculator recovery generally preserves backend authority and historical snapshot boundaries.
- File bytes are stored through object storage, not inline base64 records.
- The authenticated shell now uses `frontend/src/lib/navigation.js` and no desktop long module flyout was observed in the current shell code.

Not satisfied:

- Runtime independence from Emergent.
- AI-credit charge authority.
- Multi-instance atomicity for Workspace Dock limit enforcement.
- Complete upload validation.
- Thin-router/repository discipline across older stable modules.
- Strict tenant-scoped reread discipline in several legacy routes/services.
- Phase status hygiene: current `main` contains Phase 9I-H work while tracking still marks it as implemented/ready for review, not closed.

## 6. Confirmed Findings by Priority

### Compact Summary Table

| ID | Priority | Area | Finding | Evidence | Blocks |
| -- | -------- | ---- | ------- | -------- | ------ |
| F-001 | P1 | Deployment | Runtime still depends on Emergent services/assets | `backend/app/services/storage.py:34-38`; `backend/app/routers/auth.py:34-36`; `frontend/public/index.html:24-26`; `frontend/package.json:85`; `backend/requirements.txt:56` | Control Center, Platform Admin, launch |
| F-002 | P1 | AI credits | Caller can override billable gateway credit charge to zero | `backend/app/routers/ai_gateway.py:128-144`; `backend/app/services/ai_gateway.py:639-643`; `backend/app/services/ai_gateway.py:385-399` | Platform Admin, launch |
| F-003 | P1 | Data integrity | Workspace Dock max-open rule is process-local/non-atomic | `backend/app/services/workspace_dock.py:21-23`; `backend/app/services/workspace_dock.py:281-330`; `backend/app/services/workspace_dock.py:252-262` | Platform Admin, launch |
| F-004 | P1 | Checkpoint governance | Main contains Phase 9I-H work while tracking says ready for review | `memory/checkpoint_reference_table.md:23`; `memory/progress_register.md:13`; `git log --graph` shows Phase 9I-H ancestry merged into `main` | Platform Admin, launch |
| F-005 | P2 | File security | Upload validation lacks extension/content validation and accepts octet-stream | `backend/app/routers/documents.py:32-34`; `backend/app/routers/documents.py:52-73`; `backend/app/routers/documents.py:208-212` | Launch |
| F-006 | P2 | Tenant discipline | Scoped mutations followed by unscoped rereads | `backend/app/routers/customers.py:76-91`; `backend/app/routers/documents.py:180-177` | Launch hardening |
| F-007 | P2 | Architecture | Stable routers still hold direct database/business logic | `backend/app/routers/customers.py:36-91`; `backend/app/routers/quotes.py:19-35`; `backend/app/routers/orders.py:11-25` | Control Center if copied into new modules |
| F-008 | P2 | Startup/config | Production safety depends on `ENV=production`; defaults are permissive | `backend/app/core/config.py:18-20`; `backend/app/core/config.py:36-42`; `backend/app/core/security_guards.py:55-68`; `backend/server.py:302-307` | Platform Admin, launch |
| F-009 | P2 | Refund integrity | Stripe refund path has an explicit TODO for prior-refund netting | `backend/app/services/payment_service.py:342-367` | Launch/payment hardening |
| F-010 | P3 | Maintainability | Root route and backend app files are growing into giant registries | `frontend/src/App.js:1-199`; `backend/server.py:9-29`; `backend/server.py:52-68`; route inventory count 894 | Does not block Record Numbering |
| F-011 | P3 | Frontend runtime | API base lacks a local/dev fallback or explicit startup error | `frontend/src/lib/api.js:3-6` | Preview reliability |
| F-012 | P4 | Visual/product finish | Public HTML still displays Emergent title/badge | `frontend/public/index.html:7`; `frontend/public/index.html:24`; `frontend/public/index.html:41-44` | Final visual pass |

### F-001 - Runtime Still Depends on Emergent Services and Assets

Priority: P1
Evidence:

- `backend/app/services/storage.py:34-38` refuses object storage without `EMERGENT_LLM_KEY` and posts to `_settings.storage_url`.
- `backend/app/core/config.py:26-27` defines `emergent_llm_key` and hardcodes `https://integrations.emergentagent.com/objstore/api/v1/storage`.
- `backend/app/routers/auth.py:34-36` hardcodes the Emergent Google auth session endpoint.
- `frontend/src/pages/LoginPage.jsx:12-15` redirects browser login to `https://auth.emergentagent.com`.
- `frontend/public/index.html:24-26` uses the Emergent title and external script.
- `frontend/package.json:85` depends on `@emergentbase/visual-edits` from `https://assets.emergent.sh`.
- `backend/requirements.txt:56` installs `litellm` from an Emergent customer-assets URL.

Violated rule: Permanent product must run independently; no hidden Emergent runtime dependency.
Why it matters: Google login and storage are production-facing capabilities. They cannot rely on a donor/development host and should be configurable provider integrations.
Impact: A normal developer or production deploy can fail to authenticate, upload files, or build/install without Emergent access.
Correction: Replace hardcoded provider URLs with explicit configuration, add non-Emergent storage provider abstraction, remove production Emergent HTML/scripts/badge, and move visual-edits dependency behind a dev-only optional path or remove it.
Best stage: Before Control Center / Platform Administration; definitely before launch.
Blocks: Control Center partially, Platform Administration yes, launch yes.
Size: Large.
Tests cover this: No; current tests largely encode the Emergent bridge rather than proving independent operation.

### F-002 - AI Gateway Lets Caller Override Billable Credit Charge

Priority: P1
Evidence:

- `backend/app/routers/ai_gateway.py:128-144` exposes `credit_charge_credits` on the public gateway request payload.
- `backend/app/routers/ai_gateway.py:321-324` passes that payload directly to `create_gateway_request`.
- `backend/app/services/ai_gateway.py:639-643` uses `fields.get("credit_charge_credits", capability.get("default_credit_charge", 0))`.
- `backend/app/services/ai_gateway.py:385-399` returns without reservation and without insufficient-credit enforcement when `amount <= 0`.

Violated rule: AI-credit-consuming features cannot operate without the credit ledger and entitlement rules. Backend metering must be authoritative.
Why it matters: A user with `ai_tool:use` or `ai_assistant:use` can request an active billable capability with `credit_charge_credits: 0`; the gateway records the action without reserving/debiting credits.
Impact: AI usage, governance limits, and paid entitlements can be bypassed for gateway requests.
Correction: Remove `credit_charge_credits` from tenant/user request inputs or ignore it except for platform-admin simulation/test endpoints; derive charges solely from the active capability/governance contract.
Best stage: Before any further AI or Platform Administration work.
Blocks: Platform Administration, launch.
Size: Medium.
Tests cover this: Not directly; existing references assert explicit positive values, not that user-provided zero is rejected/ignored.

### F-003 - Workspace Dock Eight-Open Rule Is Not Multi-Instance Atomic

Priority: P1
Evidence:

- `backend/app/services/workspace_dock.py:21-23` stores `_STATE_LOCKS` in process memory.
- `backend/app/services/workspace_dock.py:281-284` protects open operations only with that process-local lock.
- `backend/app/services/workspace_dock.py:301-330` loads current state, checks `len(open_items) >= MAX_OPEN_WORKSPACES`, then appends in memory.
- `backend/app/services/workspace_dock.py:252-262` writes the full state back with `$set` and `upsert=True`, not a conditional update based on the previously read state.

Violated rule: Critical limits and repeatable operations must be race-safe.
Why it matters: Two backend instances can both read seven open workspaces, both pass the eight-item check, and each overwrite or exceed the intended state.
Impact: Lost workspace updates, incorrect active workspace state, and broken max-open enforcement in production scaling.
Correction: Enforce the max-open rule with a database conditional update, version field/compare-and-swap, transaction, or array update that fails closed when the limit changed.
Best stage: Before launch and before treating Workspace Dock as platform infrastructure.
Blocks: Platform Administration, launch.
Size: Medium.
Tests cover this: Current tests can prove single-process behavior but cannot prove multi-process atomicity.

### F-004 - Phase 9I-H Work Is on Main but Tracking Still Marks It Ready for Review

Priority: P1
Evidence:

- `memory/checkpoint_reference_table.md:23` marks EC9 Phase 9I as `PHASE 9I-H IMPLEMENTED - READY FOR REVIEW`.
- `memory/progress_register.md:13` repeats `Phase 9I-H ... status is PHASE 9I-H IMPLEMENTED - READY FOR REVIEW`.
- Git history shows `main` merged `CODEX-ux1-workspace-dock`, whose ancestry includes Phase 9I commits through `0603611 fix: commit pricing consumer contracts and google auth callback`.

Violated rule: Checkpoint work should not be treated as integrated/closed until review and tracking are synchronized.
Why it matters: Current `main` appears to contain direct consumer pricing contracts that the live tracking documents still say require review.
Impact: Future work may build on an unclosed checkpoint and confuse owner acceptance, regression scope, and rollback decisions.
Correction: Either perform and record the missing Phase 9I-H review/approval on `main`, or explicitly document that the merge introduced reviewed work and update the status.
Best stage: Immediate process correction before the next major checkpoint.
Blocks: Platform Administration and launch; does not inherently block isolated Record Numbering.
Size: Small to medium.
Tests cover this: No; this is repository/process evidence.

### F-005 - File Upload Validation Is MIME-Prefix Based and Accepts Octet-Stream

Priority: P2
Evidence:

- `backend/app/routers/documents.py:32-34` allows broad MIME prefixes including `text/`, zip, and `application/octet-stream`.
- `backend/app/routers/documents.py:52-54` validates only the client-provided MIME type.
- `backend/app/routers/documents.py:65-73` reads the full file into memory and does no extension allowlist or content sniffing before storage.
- `backend/app/routers/documents.py:208-212` places `original_filename` directly in `Content-Disposition`.

Violated rule: Upload validation must cover type, extension, size, naming, authorization, and tenant ownership.
Why it matters: Client-provided MIME is not authoritative, octet-stream admits arbitrary content, and a raw filename in a response header is avoidable risk.
Impact: Unsafe or unexpected files can enter private storage and be served back through authenticated endpoints; large files are read fully into memory before rejection.
Correction: Centralize upload validation with extension allowlist, MIME/content sniffing, safe filename normalization, streaming size checks where practical, and RFC-safe response header construction.
Best stage: EC22/security hardening, or earlier if documents are used heavily.
Blocks: Launch.
Size: Medium.
Tests cover this: Prior docs mention upload validation, but current router code does not enforce the full contract.

### F-006 - Scoped Mutations Are Followed by Unscoped Rereads

Priority: P2
Evidence:

- `backend/app/routers/customers.py:82` updates by `{"id": customer_id, "tenant_id": user["tenant_id"]}`, then `backend/app/routers/customers.py:90` rereads by `{"id": customer_id}` only.
- `backend/app/routers/documents.py:182-184` archives by `id + tenant_id`, while the visibility path rereads at `backend/app/routers/documents.py:176` by `{"id": file_id}` only after a scoped update.

Violated rule: No missing tenant filters; tenant ownership must be enforced in the actual database operation and reread.
Why it matters: Global unique `id` indexes currently reduce exploitability, but the pattern is fragile and contradicts the tenant-isolation standard established during security recovery.
Impact: Future ID/index changes or copied code could reintroduce cross-tenant leaks.
Correction: Require `tenant_id` on every tenant-scoped reread/update/delete, including post-mutation reads, and add pattern tests.
Best stage: Security hardening sweep before launch.
Blocks: Launch hardening; not Record Numbering if not copied.
Size: Small.
Tests cover this: Some security-recovery tests cover modified auth/user scope, not this full-app pattern.

### F-007 - Older Routers Still Own Business Logic and Direct Database Access

Priority: P2
Evidence:

- `backend/app/routers/customers.py:36-91` contains query construction, inserts, updates, and audit calls directly in the router.
- `backend/app/routers/quotes.py:19-35` imports `db`, pricing, totals, snapshot, revision, conversion, and sequence services directly into a large route module.
- `backend/app/routers/orders.py:11-25` similarly couples routing, `db`, pricing, totals, snapshots, sequence, and production rules.

Violated rule: New modules use `models/ + repositories/ + routers/ + services`; routers stay thin; repositories own tenant filters; services own algorithms.
Why it matters: This is explicitly allowed not to be mass-refactored for stable MVP modules, but it is risky if used as the pattern for Record Numbering, Control Center, or Platform Administration.
Impact: Future checkpoints may duplicate tenant filters and business logic in route files instead of centralizing them.
Correction: Do not rewrite stable modules opportunistically; for new/changed modules, move new behavior into services/repositories and leave routers as validation/orchestration only.
Best stage: Ongoing checkpoint discipline; enforce before Control Center and Platform Admin.
Blocks: Does not block Record Numbering if its implementation follows service/repository contracts.
Size: Medium if corrected globally; small per touched module.
Tests cover this: No architecture tests enforce router thinness.

### F-008 - Production Safety Depends on a Permissive Environment Default

Priority: P2
Evidence:

- `backend/app/core/config.py:18-20` defaults CORS to `*` and JWT to `dev-secret-do-not-use-in-prod`.
- `backend/app/core/config.py:36-42` defaults `ENV` to `development`.
- `backend/app/core/security_guards.py:55-68` returns no violations unless the environment is production.
- `backend/server.py:302-307` enables credentialed CORS using configured origins.

Violated rule: Production startup guards must prevent dev bypass/placeholder secrets and config must be separated across environments.
Why it matters: The guard is useful only if deployment sets `ENV=production`; a misconfigured production deploy can start as development with permissive defaults.
Impact: Incorrect deployment can expose dev behaviors or break browser auth through wildcard credentialed CORS behavior.
Correction: Add explicit deployment mode requirements for non-local hosts, require `CORS_ORIGINS` and strong JWT outside local dev/test, and fail closed when a deploy target is not explicitly classified.
Best stage: Before Platform Administration and launch.
Blocks: Platform Administration and launch.
Size: Medium.
Tests cover this: Startup guard tests cover production settings, not misclassified deployment.

### F-009 - Refund Path Still Has Prior-Refund Netting TODO

Priority: P2
Evidence:

- `backend/app/services/payment_service.py:361` sets `refundable = int(src["amount_cents"])` with comment `net after prior refunds -> future TODO`.
- `backend/app/services/payment_service.py:362-365` validates the requested refund against the original amount, not accumulated prior refunds.

Violated rule: Money, refunds, and repeatable payment operations must be idempotent and not corrupt balances.
Why it matters: If multiple refunds are allowed for a confirmed Stripe payment, the code path does not subtract prior refund records before approving the next amount.
Impact: Over-refund attempts may reach Stripe or create inconsistent local expectations depending on provider response.
Correction: Calculate refundable balance from confirmed refund records and provider state, and add idempotency keys not based on random suffix for repeatable refund requests.
Best stage: Payment hardening before launch.
Blocks: Launch/payment hardening; not Record Numbering.
Size: Medium.
Tests cover this: Not confirmed by this review.

### F-010 - Route Registries Are Becoming Giant Files

Priority: P3
Evidence:

- `frontend/src/App.js:1-199` imports and declares the app's full route table inline.
- `backend/server.py:9-29` and `backend/server.py:52-68` begin a long router import/include sequence; current endpoint decorator inventory found 894 router endpoint decorators across 85 router files.

Violated rule: Avoid giant `App.js` / router files and obsolete monolithic patterns.
Why it matters: The app is growing quickly and merge conflicts around route registration and app-shell behavior are already recurring.
Impact: More accidental routing regressions and harder checkpoint isolation.
Correction: Move frontend route metadata into feature route modules or route registry objects and group backend router includes by domain registration functions.
Best stage: Controlled architecture cleanup, not inside a business checkpoint.
Blocks: Does not block Record Numbering; should be considered before broad Control Center nav work.
Size: Medium.
Tests cover this: Current tests catch some route rendering, not maintainability risk.

### F-011 - Frontend API Base Has No Explicit Fallback or Startup Error

Priority: P3
Evidence:

- `frontend/src/lib/api.js:3-6` builds `${REACT_APP_BACKEND_URL}/api` directly.

Violated rule: Normal developers should be able to run the app with documented configuration and avoid blank-screen/runtime surprises.
Why it matters: If `REACT_APP_BACKEND_URL` is absent, API calls go to `undefined/api` rather than showing an actionable configuration error.
Impact: Local preview confusion, especially after login/auth callback issues.
Correction: Fail visibly with a configuration message or use a documented local default only in development.
Best stage: Developer-experience hardening.
Blocks: No.
Size: Small.
Tests cover this: Not found.

### F-012 - Public HTML Still Carries Emergent Branding

Priority: P4
Evidence:

- `frontend/public/index.html:7` describes the app as `A product of emergent.sh`.
- `frontend/public/index.html:24` sets title `Emergent | Fullstack App`.
- `frontend/public/index.html:41-44` renders the Emergent badge link.

Violated rule: `SIGNGUY-MVP` is the permanent SignGuy AI commercial product.
Why it matters: This is not a core architecture failure, but it is visible product/launch polish and reinforces the runtime-dependency problem in F-001.
Impact: Users see incorrect product identity.
Correction: Replace with SignGuy AI product metadata and remove the badge during final visual/product pass unless it is explicitly required for the development environment only.
Best stage: Final visual pass, or with F-001 if removing external assets.
Blocks: Final launch polish.
Size: Small.
Tests cover this: No.

## 7. Probable Risks Requiring Confirmation

- Community/platform support service uses several `find_one({"id": ...})` and update patterns without obvious tenant scope in the grep output. Some may be intentionally platform-global, but founder/community/support boundaries need a focused tenant-role review before Platform Administration.
- AI Studio local mock behavior is intentional under H7. It is not a defect by itself, but production enablement must not silently convert local mock outputs into real provider claims without owner-approved credit pricing and provider contracts.
- Public portal and employee portal token storage uses browser `localStorage`. Staff/portal JWT scope separation is enforced backend-side, but token storage should be revisited in EC22 hardening.
- Search endpoints rely on regex search patterns in several list pages. This is acceptable for MVP-size data but needs indexing/search strategy before large tenants.
- `main` contains many checkpoint histories merged through long-lived branches. A release-candidate audit should verify every committed checkpoint's tracking status matches code on `main`.

## 8. Missing or Partially Connected Implementations

- Phase 9I-H is implemented on `main` but not recorded as reviewed/closed in tracking.
- Digital Print item/order-minimum enforcement remains explicitly deferred; this is not a defect unless UI claims it is active.
- EC20 Platform Admin is not started.
- EC21 marketing/public pricing/founder/signup is not started.
- EC22 final integration/commercial release hardening is not started.
- Final independent, non-Emergent deployment configuration is incomplete.
- Final AI provider/credit commercial activation remains deferred by H7.

## 9. Duplicate Sources of Truth

- Navigation: current code centralizes navigation in `frontend/src/lib/navigation.js`; current shell uses it. Older docs still mention side flyouts while current owner decisions require persistent top module tabs. Current owner decisions should remain controlling.
- Pricing: current Phase 9I work appears to preserve backend authority and shared contracts. No frontend formula duplication was identified in sampled files.
- AI: gateway capabilities and Studio/Assistant bootstrap services both seed platform AI records; this is acceptable only if bootstrap remains idempotent and platform-admin controlled.
- Documents/files: upload rules are partly duplicated between current code and older docs that claim stronger validation than the current router performs.

## 10. Security and Tenant-Isolation Assessment

Strengths:

- Staff routes use `get_current_user`/`require_permission`.
- Portal tokens are rejected from staff auth dependencies.
- User create/update models forbid unexpected payload fields and do not expose platform creator assignment through tenant user endpoints.
- Many domain reads/writes include `tenant_id`.

Concerns:

- AI gateway credit amount is user-controllable.
- Some post-update rereads omit tenant scope.
- Upload validation is too broad.
- Production guard defaults are permissive unless deployment is correctly marked as production.
- Emergent-managed Google auth is hardcoded and must be replaced or explicitly made an approved provider dependency.

## 11. Data and Money-Integrity Assessment

Strengths:

- Commerce fields sampled in Quote/Order/Payment paths use `_cents`.
- Quote-to-Order and pricing snapshot protections are documented and appear represented in service imports and recent checkpoint history.
- Saved calculations are designed as immutable historical snapshots and fresh recalculation is required for transfer.

Concerns:

- Workspace Dock max-open enforcement has been moved to revision-checked database writes with retry.
- Payment refund prior-refund netting and request idempotency are implemented for the Stripe refund path.
- The identified update/reread paths in this correction scope now include tenant scope.
- Broad metadata fields exist in AI and pricing-adjacent models; authoritative business values should continue to stay in typed fields.

## 12. Architecture and Maintainability Assessment

The app remains a shared modular monolith, which matches the approved architecture. Newer modules generally follow the models/services/routers pattern, but older stable modules still keep business logic and direct DB calls inside routers. This is acceptable as legacy stability debt only if future work avoids copying that pattern.

The largest maintainability risk is accumulation in central route registration files and checkpoint merges that bring in adjacent work before tracking status is closed.

## 13. Frontend/Backend Integration Assessment

Strengths:

- `RequireAuth` wraps authenticated app routes.
- `AppShell` uses the shared navigation source and renders module tabs, contextual ribbon, one Quick Access Toolbar, and Workspace Dock.
- Pricing workspace and Quote/Order calculator parity are routed through backend results.

Concerns:

- `REACT_APP_BACKEND_URL` now has a documented local development fallback and production misconfiguration logging.
- Google login now requires explicit provider URL/session exchange configuration and fails closed when missing.
- Large `App.js` route table increases risk of future shell/navigation regressions.

## 14. Deployment Independence Assessment

Deployment independence is satisfied for the audited runtime dependencies. Object storage is application-owned/configurable, Google sign-in no longer hardcodes a provider URL or session-data endpoint, frontend HTML no longer loads external donor assets, dependency manifests no longer pull donor packages or wheels, and startup guards fail closed for unsafe hosted/deployment configuration.

## 15. Existing-Test Coverage Assessment

Existing tests are extensive for checkpoint-level behavior, pricing, permissions, and many workflows. The cross-cutting gaps identified by the original audit were addressed during this correction checkpoint:

- Workspace Dock now has a simulated multi-instance atomicity test for the max-open rule.
- AI gateway metering tests reject caller-supplied charge overrides and cover server-authorized free operations.
- Upload-validation tests cover extension/content mismatch, MIME allowlisting, magic-byte checks, safe filenames, valid files, and tenant separation.
- The identified unscoped rereads were corrected directly and covered by focused tests where applicable.
- Runtime-independence and startup-guard tests now fail on provider-specific URLs/assets/package/env dependencies and unsafe deployment configuration.

Commands run during this correction checkpoint:

- Focused correction backend tests: `69 passed, 6 warnings`.
- Full backend tests: `841 passed, 3 skipped, 6 warnings`.
- Full frontend tests: `16 passed, 70 tests passed`.
- Frontend production build: passed.
- Backend compile/import validation: passed.
- `git diff --check`: passed with CRLF conversion warnings only.

## 16. Items Safe for the Final Emergent Pass

- Minor colors, spacing, typography, icons, and non-blocking responsive polish.
- Replacing the visible HTML title/badge can be included in a final product polish pass, but the external script/dependency/runtime aspects should be treated with F-001.
- Minor wording around local mock AI labels, as long as they remain honest and H7-compliant.

## 17. Prioritized Correction Order

Post-correction status: items 1 through 8 below have been corrected in this checkpoint. Item 9 remains intentionally deferred as architecture-maintenance work and does not block Record Numbering, Control Center, or Platform Administration if those checkpoints keep new work inside the service/repository contracts.

1. Fix AI gateway credit-charge authority so tenant users cannot reduce billable charges.
2. Reconcile Phase 9I-H status on `main`: review/record/close or explicitly document the merge state.
3. Replace or isolate Emergent runtime dependencies for auth, storage, frontend HTML/scripts, and package sources.
4. Make Workspace Dock open/limit updates database-atomic across backend instances.
5. Complete upload validation and safe download headers.
6. Tighten deployment guardrails for non-local environments and CORS/JWT defaults.
7. Sweep scoped-mutation/unscoped-reread patterns.
8. Close payment refund netting/idempotency TODO.
9. Refactor route registration and keep future modules on service/repository boundaries.

## 18. Features That May Safely Continue After Corrections

- Record Numbering may proceed if it is tightly scoped, uses tenant-scoped atomic counters, includes idempotency/concurrency tests, and does not touch auth, payments, AI credits, storage, shell, or platform admin.
- Final visual polish may proceed for P4-only items if it avoids hiding the P1/P2 defects.
- Documentation-only reconciliation may proceed.
- Control Center may proceed as a bounded configuration/administration checkpoint using the corrected startup guard and integration-status contracts.
- Platform Administration may proceed as its own focused checkpoint with explicit platform-role, audit, and tenant-boundary tests.

## 19. Features That Must Wait

- Launch/commercial release still requires its own final readiness review; it is not automatically approved by this correction checkpoint.
- Any live AI provider expansion should wait for H7 owner decisions and provider-specific launch approval.
- Any storage-heavy customer portal, Webstore, Wrap Lab, or public upload expansion should reuse the corrected upload/storage validator and still receive focused endpoint tests.
- Broad router/App.js decomposition remains deferred to a controlled architecture cleanup, not a business checkpoint.

## 20. Final Recommendation

The correction checkpoint is ready for owner review. The codebase is not recreating the original app wholesale, and the previously blocking cross-cutting hazards are corrected in code, tests, and tracking: provider/runtime independence, AI-credit authority, Workspace Dock atomicity, upload validation, production guardrails, refund idempotency/netting, and Phase 9I-H status hygiene.

Final status:

P1/P2 CORRECTIONS IMPLEMENTED - AWAITING REVIEW
