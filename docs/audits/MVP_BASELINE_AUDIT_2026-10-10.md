# SIGNGUY-MVP baseline audit — 2026-10-10

## Audit scope and evidence standard

This is an evidence-first audit of the code checked out at 1ad34d7 in C:\Users\thesi\Documents\GitHub\SIGNGUY-MVP. It does not assert the state of a deployment, database, external provider, or the commits already present in the local origin/main tracking ref but not in this checkout. The checkout is main, four commits behind that ref, and had one pre-existing untracked file (docs/MVP_CODE_HEALTH_AND_CLEANUP_AUDIT.md); it was neither changed nor treated as source-of-truth evidence.

The inventory cross-checks 149 registered client route declarations, including aliases, wildcards, and fallbacks, in frontend/src/App.js:121-259, frontend/src/portal/PortalApp.jsx:198-213, frontend/src/portal/employee/EmployeePortalApp.jsx:1081-1096, and frontend/src/public/PublicApp.jsx:535-541, FastAPI registrations in backend/server.py:1-320, page/API dependencies, and focused test files. No broad test suite, build, dev-server session, provider call, database mutation, or production-data access was run. No business feature is labelled VERIFIED WORKING merely from source inspection.

IMPLEMENTED — NOT RUNTIME VERIFIED means the client, API, authorization, and persistence path appear connected in the checked-out source, often with focused test coverage, but were not exercised in this audit. PARTIALLY IMPLEMENTED includes a deliberate, visible provider or workflow boundary; it is not automatically a coding defect.

## 1. Executive summary

SIGNGUY-MVP is a large multi-tenant React/FastAPI/MongoDB application with real domain models and persistence for most sign-shop records: customers, intake, quotes, orders, invoices, payments, documents, work orders, production stages, inventory, purchasing, employee time, schedules, portals, and pricing. This is not a collection of disconnected mock screens. The frontend makes authenticated API calls, FastAPI mounts the corresponding routers, and services store tenant-scoped MongoDB documents.

It is nevertheless not production-ready as a full operational sign-shop system. The strongest boundaries are external commerce/provider activation, webstore-to-canonical-order/production completion, live AI execution, supplier connectivity, and payroll compliance. Several workflows have strong internal records and state transitions but stop before the real-world external handoff. The current checked-out baseline also lags its recorded remote branch, so it must be refreshed and re-audited before a release claim.

The inventory contains 124 significant application features/pages, grouped where an alias points to the same page or a route family is one user-facing surface. Its machine-readable companion is docs/audits/MVP_FEATURE_INVENTORY_2026-10-10.csv. Status counts are derived from that CSV: 0 verified working; 95 implemented-not-runtime-verified; 19 partially implemented; 1 UI only; 1 broken; 1 unreachable/disconnected; 2 legacy/unused; 3 planned only; 2 unknown.

## 2. Complete application map

### Application shells and access

- **Staff shell.** Authenticated routes are nested beneath RequireAuth and AppShell (frontend/src/App.js:133-259). The shell’s canonical navigation is frontend/src/lib/navigation.js, rather than an inferred route list. It includes Home, Shop Operations, Customers, Sales, Approval Center, Production, Schedule, Webstores, Wrap Lab, Business & Finance, Team, Studio, Help, and Settings.
- **Authentication and tenant creation.** Login, registration, password reset, Google callback, suspension, and a development login exist. Auth routes and dev-login are registered in backend/app/routers/auth.py:86-525; README.md:28-49 describes tenant-scoped identity and required provider configuration.
- **Separate non-staff shells.** Customer portal (/portal/*), employee portal (/portal/employee/*), restricted production kiosk (/kiosk/production), token/public actions (/p/*), and public form/webstore routes are distinct route trees, not sidebar panels.
- **Platform administration.** A separate platform-admin route family exposes tenants, billing/support operations, broadcasts, site settings, email/audit/impersonation logs, analytics, AI governance, and commercial catalog APIs. It must be evaluated under platform permissions, not ordinary shop roles.

### Business domains discovered

| Area | Active surfaces and substantive overlays | Connected backend/persistence evidence |
| --- | --- | --- |
| Home and Shop Operations | Overview dashboard, KPI/work queues, Shop Operations, workspace dock, global search/quick actions | Dashboard and workspace routers are registered in backend/server.py:76-142; the dashboard client calls summary/team/timesheet endpoints in frontend/src/pages/DashboardPage.jsx:100-112. |
| Sales and customers | Customers/detail/duplicate merge; staff intake; quote/detail; order/detail; line-item/pricing dialog; invoices/detail; manual/Stripe/refund dialogs; documents and email history | Customer CRUD/merge/archive (backend/app/routers/customers.py:62-229), quote conversion (backend/app/services/quote_conversion.py:42-118), order pricing and completion, invoice/payment routers. |
| Approvals and design | Decision Rooms, review queue, Approval Center, proof state, visual markup, templates, forms and public form request | Decision-room, approval, proof, signature, visual-markup, templates, and form routers are mounted in backend/server.py:179-226; editor mutations are visible in DecisionRoomEditorPage.jsx:34-67. |
| Production | Work-order list/detail, board, workflow configuration, timeline, stage actions, kiosk, readiness/completion | Work-order, production workflow/timeline/stage/kiosk routers are mounted in backend/server.py:216-244; order terminal edit protection is in backend/app/routers/orders.py:198-203. |
| Pricing | Pricing Foundation, setup quiz/wizard, calculator, saved items/calculations, snapshot history, advisory | Pricing routers and private-engine adapter infrastructure are mounted in backend/server.py:115-160; calculator source displays authoritative method output and unavailable-method states in PricingCalculatorPage.jsx:752-889. |
| Inventory and finance | Materials, stock, supply center, vendors, purchase orders/receiving, expenses, finance dashboard, tax reports, curated/custom reports | Inventory records/reorder (inventory_service.py:106-238), PO receiving (purchase_orders.py:178-186), and finance/report routers are registered in server.py:94-114. |
| Team | Team dashboard, employees, equipment, training, certifications, tasks, communications, announcements, time clock, timesheets, payroll, team/shop schedules, employee access | Time-clock refreshes timesheets (time_clock.py:54-85); task endpoints support assignment and Kanban (tasks.py:103-180); payroll explicitly covers stored gross-pay, not statutory payroll. |
| Webstores | Staff list/detail/setup, owner portal/invitations, catalog/products/branding/questionnaire, launch packet/readiness, public storefront/cart/checkout, orders/production/report surfaces | Router/service families are mounted in server.py:271-280; public checkout is conditional on verified provider authority (webstore_public_checkout.py:24-60,158-174). |
| Vehicle graphics | Wrap Lab list/detail, vehicle/specification records, inspections, proofs/signatures, panel plans, installation schedules/records, customer acknowledgement | Wrap Lab links quote/order/work-order references and enforces workflow readiness (wrap_lab.py:30-71,282-294); UI writes inspection/panel/schedule/installation records (WrapLabDetailPage.jsx:126-153). |
| AI, help, administration | AI Studio, generated assets, prompts, activity, credits, governance, Business Assistant/voice, onboarding, Help Center, community, billing/settings/data security/platform admin | AI gateway and Studio routes are mounted in server.py:282-304; AI gateway deliberately makes no external provider calls (ai_gateway.py:3-4) and Studio uses deterministic local mocks (ai_studio.py:362-417,664-721). |

The CSV is the complete row-level map, including redirect/alias routes and portal-only features that do not appear in the staff sidebar.

## 3. Feature status by application area

### Strongly implemented but not runtime verified

The following have connected page/API/persistence paths and targeted test evidence, but no fresh live verification in this audit: customer CRUD and merge; staff intake CRUD and conversion contracts; quote/order/invoice CRUD; manual payment and recorded Stripe intent/refund paths; documents and email history; decision-room authoring/portal/review/apply; form/template authoring; work-order and production stage records; core pricing configuration and calculator; material/stock/PO/receiving; expenses and stored-data finance reports; employees/equipment/training/certifications/tasks/time clock/timesheets; schedules; Wrap Lab records; customer and employee portal flows; onboarding/help/community; and platform administration.

There is substantial focused test infrastructure: 152 backend test_*.py files and 35 frontend test files, including workflow-specific suites for customers, pricing, production, portals, webstores, Wrap Lab, reports, AI, and platform admin. These are evidence of intended/automated coverage, not a claim that they passed today.

### Partially implemented or intentionally gated

- **External AI execution.** AI gateway metering/governance and Studio records persist, but the gateway never calls a real provider and Studio records local/mock provenance (backend/app/services/ai_gateway.py:3-4; backend/app/services/ai_studio.py:381-417). Business Assistant text/actions are local contracts; voice is conditional on OpenAI Realtime configuration and reports unavailable otherwise (business_assistant.py:1183-1271).
- **Webstore payment and canonical fulfillment.** Catalog, readiness, cart, purchase-intent, provider-event and report code exists, but a non-configured provider explicitly performs no operation (webstore_payment_provider_not_configured.py:13-28). The public UI tells users order creation/payment are unavailable until verified setup (PublicWebstorePage.jsx:146-192), and launch documentation says canonical Order/Production handoff remains deferred (webstore_launch_packet.py:141).
- **Payments and billing.** Manual payments are connected. Stripe code can use a deterministic local path for placeholder/empty keys and only invokes real Stripe when proper configuration permits it (stripe_core.py:36-64; stripe_billing.py:28-93). No configured-provider session was exercised.
- **Purchasing/supplier data.** Material, vendor, PO, receiving, stock, and shortage calculations are implemented. Supplier connectors are an adapter contract with a manual/feed/test path; a live supplier integration is not demonstrated. supplier_connectors/base.py:38-88 correctly raises NotImplementedError for a base adapter and is not dead code.
- **Payroll.** Pay periods, stored transactions, approvals/close/reopen, and snapshots exist, but the router explicitly excludes statutory filings and the reports service says withholding/deductions are not implemented (payroll.py:4-169; reports_service.py:1599).
- **Reporting.** Stored data reports/CSV/export and a custom-report surface exist, but dashboard customization, webstore payout rebuild, Wrap Lab rebuild, and statutory-payroll reports are explicitly deferred (reports_service.py:1581-1599).
- **Intake/public inquiry distinction.** Staff intake is implemented. The intake module expressly defers customer/public intake submission and its preview helpers are non-persisting contracts (intake_service.py:5-12,492-513). Public form requests are forms, not an implemented public-intake conversion workflow.

### UI-only, unreachable, legacy, and unknown items

- **UI only:** Pricing advisory responses are persisted but always unavailable without a provider (pricing_advisory.py:4-60); the public webstore donation/promo presentation explicitly says the actions are not available (PublicWebstorePage.jsx:146).
- **Unreachable/disconnected:** Several /help/* locations map to the same Help Center or Community page rather than dedicated pages (frontend/src/App.js:210-217); the route exists but the promised topical destination is not distinct. The legacy /home and /sales/* routes are intentional redirects, not dead pages.
- **Legacy/unused:** inputValue is declared in frontend/src/pages/PricingCalculatorPage.jsx:62 with no in-repository use; it is a low-risk confirmed dead declaration. isDevServer is similarly declared but unused in frontend/craco.config.js:7.
- **Unknown:** Production production-data behavior, outbound email delivery, Google OAuth, live Stripe/Stripe Connect, object storage, OpenAI Realtime, live suppliers, and external deployment configuration were deliberately not invoked. Their live status cannot be inferred from code.

## 4. Workflow readiness

| Workflow | Connected path found | Readiness | Principal blocker or gap |
| --- | --- | --- | --- |
| Customer to sale | Customer → staff intake or quote → quote line items/pricing → approval/send → idempotent quote-to-order → invoice → manual/conditional Stripe payment | **PARTIALLY IMPLEMENTED** | Fresh end-to-end execution absent; public inquiry is not a staff-intake conversion, and live payment requires real configuration. |
| Sales to production | Order → readiness → work orders → production stages/board/kiosk → completion packet/signature | **PARTIALLY IMPLEMENTED** | Internal services are connected, but no full sequence was run against a safe data set; real pickup/install operating evidence is absent. |
| Financial | Quote/order → one invoice per order → payment history/manual payment → paid/balance status → stored-data finance/reports | **PARTIALLY IMPLEMENTED** | Live Stripe and refund/webhook delivery were not verified; no statutory payroll/reporting. |
| Vehicle Wrap | Wrap project → vehicle/specs → inspection → proof/signature → panel plan → calendar schedule → installation record → completion/acknowledgment | **IMPLEMENTED — NOT RUNTIME VERIFIED** | Strong linked data-flow in source, but no isolated project was exercised. AI/design-provider work is not a dependency this source proves. |
| Inventory and purchasing | Material/location stock → reorder/shortage → purchase order → receive → inventory update | **IMPLEMENTED — NOT RUNTIME VERIFIED** | Live supplier ordering/feed remains adapter-specific and unverified. |
| Team | Employee → task/shift → self/admin clock actions → timesheet → pay period/snapshot | **PARTIALLY IMPLEMENTED** | Actual clock/approval flows not run; payroll is operational ledger support, not tax/payroll filing. |
| Customer portal | Token/login → quotes/orders/invoices → invoice pay → proofs/decision rooms/documents/messages/webstores | **PARTIALLY IMPLEMENTED** | Provider payments and token/email delivery not live-tested; rights and data isolation require runtime security verification. |
| Employee portal | Identity/login → clock/production/schedule/time off/timesheet/pay/training/certifications/tasks/messages/profile | **IMPLEMENTED — NOT RUNTIME VERIFIED** | Requires real identity provisioning and permission/tenant acceptance tests in a safe environment. |
| Pricing | Pricing setup/material profiles/components/saved items → calculator → snapshot → quote/order item price records | **IMPLEMENTED — NOT RUNTIME VERIFIED** | Private pricing engine/package and full pricing parity were not invoked in this audit. Advisory provider answers are unavailable by design. |
| Online store | Owner/setup/branding/catalog → readiness/launch → public storefront/cart → purchase intent → verified provider event → canonical order/production | **PARTIALLY IMPLEMENTED** | Verified Stripe Connect authority plus canonical fulfillment handoff are explicitly incomplete/deferred. |
| AI | Governance/credits/catalog → Studio run or Assistant proposal → audit/activity/assets | **PARTIALLY IMPLEMENTED** | Core runs are deterministic/local contracts; external AI is intentionally absent. Voice requires separate configuration. |

## 5. Technical code review

### Architecture and persistence

The architecture is coherent at a high level: React 19/CRACO/TanStack Query is the client stack (frontend/package.json), FastAPI routers delegate to domain services, and Motor persists tenant-scoped MongoDB documents. Startup validates configuration and ensures indexes (backend/server.py:1-20 and backend/app/core/db.py:1514). Docker Compose supplies an isolated MongoDB, backend filesystem object store, and web reverse proxy (docker-compose.yml:1-55).

The main architecture risks are localized rather than a repository-wide emergency:

1. **Duplicated pricing orchestration (P2).** Quote and order routers each implement _resolve_item_pricing (quotes.py:222 and orders.py:206) and invoke it in line-item mutation paths. Contract drift can change quoted versus ordered economics.
2. **Provider boundaries can be mistaken for live features (P1 product-risk).** AI, Stripe/Connect, SendGrid, OAuth, storage, and supplier adapters have safe gates, but the UI exposes sophisticated surfaces. Keep activation state prominent and do not represent them as verified without environment evidence.
3. **Route/content mismatch (P2).** Help topic routes collapse to generic surfaces (App.js:210-217); therefore named help destinations do not have their own information architecture.
4. **Documentation drift (P2).** README.md:9 says React 18 while frontend/package.json pins React 19. This does not prove a runtime bug but can derail reproducible environment work.
5. **Deferred-report labels must remain product-visible (P2).** Report APIs deliberately return limitations (reports_service.py:1581-1599). Avoid letting exports be interpreted as complete accounting, payroll, or payout systems.

### Security and integrity observations

Positive static evidence includes route-level permission dependencies, tenant filters in customer/quote/order examples, production terminal-state safeguards, development-only authentication controls, and a substantial set of tenant, permissions, document-security, Stripe, and concurrent-payment tests. Examples include customers.py:62-229, orders.py:198-203, time_clock.py:3-6, and test files such as test_ec2_cross_tenant.py, test_document_upload_security.py, and test_cir_001_concurrent_invoice_overpayment.py.

This audit cannot certify tenant isolation, authorization, webhook signatures, token expiration, or object-storage access in a deployed environment. Those remain runtime acceptance/security exercises, not source-only conclusions.

## 6. Dead code and cleanup candidates

| Candidate | Evidence | Confidence / cleanup risk | Audit action |
| --- | --- | --- | --- |
| inputValue | Declared only at frontend/src/pages/PricingCalculatorPage.jsx:62; repository search found no use. | Confirmed unused / low. | Remove only in a separately authorized cleanup change with a focused calculator test. |
| isDevServer | Declared only at frontend/craco.config.js:7; repository search found no use. | Confirmed unused / low. | Same narrow cleanup treatment. |
| Quote/order pricing resolver duplication | Parallel private functions at backend/app/routers/quotes.py:222 and backend/app/routers/orders.py:206. | Confirmed duplication / medium-high behavioral risk. | First extract contracts and parity tests; do not refactor during feature work. |
| Quote expiration helpers | Multiple quote status/expiration decisions around backend/app/routers/quotes.py:184-201 plus legacy behavior candidates. | Potential duplication / medium. | Trace all state transitions before consolidating. |
| Webstore façade/compatibility modules | Large dynamically connected webstore_* service/router family; public/staff/owner paths use shared contracts. | Not dead; compatibility risk high. | Do not delete based on filename or size. Consolidate only one externally tested seam at a time. |
| AI and supplier mock/test adapters | Registry/configuration-based or provider-boundary code. | Not dead; high false-positive risk. | Preserve until a documented provider cutover removes the consumer. |

No unused dependency was declared confirmed: manifest-only inspection cannot prove runtime/bundler use. No generated, dependency, vendored, or local-data directory was included as a cleanup candidate.

## 7. Incomplete and abandoned development

There is no evidence that most incomplete work is abandoned; much is a deliberate staged boundary. The concrete incomplete items are: external AI provider execution; AI advisory answers; Webstore verified payment authority and canonical fulfillment handoff; public intake conversion; supplier adapter implementations beyond manual/feed/test mechanisms; payroll tax/withholding/filings; dashboard customization; webstore payout rebuild; Wrap Lab reporting rebuild; public-store donation/promo actions; and topic-specific help pages.

The backend/app/models/time_entry.py:39 comment that calls task_id a placeholder is stale or ambiguous because a Tasks system now exists; it is documentation debt, not proof the field is unused. Do not remove the field without a model/database consumer trace.

## 8. Critical problems

1. **Baseline is not release-current.** The audit checkout is four commits behind origin/main; source conclusions cannot be promoted to a current remote-main release assertion.
2. **Online-webstore completion is blocked.** Public catalog/cart paths exist, but verified payment authority and canonical Order/Production handoff are not a complete, demonstrated workflow.
3. **External providers are configuration-dependent and unverified.** Payments, email, Google OAuth, storage, external AI/voice, and supplier integrations cannot be considered operational from this checkout alone.
4. **Payroll/reporting could be misused as a full financial system.** The code explicitly omits statutory deductions/filings and certain rebuilds.
5. **The public-inquiry-to-sales handoff is incomplete.** Staff intake is solid, but public forms are not a public intake submission and conversion workflow.

## 9. Recommended development priorities

1. **Reconcile the baseline before coding or release claims.** Fetch/review the newer remote commits, preserve the existing untracked audit, and repeat the small set of affected evidence checks. Do not blindly merge or reset.
2. **Choose and complete the Webstore commerce authority.** Define verified Stripe/Connect setup, webhook handling, idempotency, canonical Order and Production creation, and acceptance tests as one dependency chain.
3. **Complete a safe customer-to-cash acceptance path.** Use a disposable tenant/data set to exercise customer → quote → approval → order → invoice → manual/real configured payment → completion, including tenant isolation.
4. **Make public inquiry explicit.** Either build a governed public-intake submission/conversion workflow or clearly route users to the existing form capability without implying automatic sales conversion.
5. **Set provider/finance boundaries in the product and plan their next slice.** Prioritize real provider activation only with secrets/webhook/permission acceptance coverage; separately decide whether statutory payroll and report limitations are in MVP scope. Do not refactor general code first.

## 10. Current MVP readiness

- **Internal testing: conditionally ready.** The local Docker/development architecture, focused test suites, development login, and broad persisted workflow surface make internal testing reasonable after the checkout is reconciled and a disposable MongoDB/database is selected.
- **Limited beta: not yet evidenced.** A narrow, manually operated beta might be possible after real-provider choices are deliberately disabled or acceptance-tested. This audit has not verified access control, email, payments, external storage, support operations, backups, monitoring, or critical workflows in a beta-like environment.
- **Production use: not ready to certify.** The remote-baseline mismatch and explicit commerce/provider/payroll/public-intake limits prevent a responsible production-readiness claim. This is a readiness conclusion, not a claim the application cannot run.

## 11. Verification gaps

Not run: frontend build; backend/frontend complete suites; any live browser route; local Docker stack; MongoDB migration/index behavior; document upload; email; OAuth; Stripe/Stripe Connect/webhooks/refunds; Webstore payment/order handoff; OpenAI/Realtime; AI provider calls; external supplier feeds; object storage; permissions/tenant isolation against a live data set; production kiosk device behavior; backup/restore; performance/load; accessibility; and deployed observability. The baseline also excludes the commits visible only in origin/main at audit time.

The only files created by this audit are this report and its companion CSV.
