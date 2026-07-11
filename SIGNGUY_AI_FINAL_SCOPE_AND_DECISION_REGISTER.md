# SignGuy AI — Final Scope and Decision Register

**Document date:** 2026-02 (Prompt 3 authoritative scope pass)
**Author:** E2 agent — read-only for this document (no application code changes)
**Companion documents:**
- `/app/SIGNGUY_AI_FEATURE_READINESS_MATRIX.md` (per-feature evidence source)
- `/app/SIGNGUY_AI_REPOSITORY_AND_ARCHITECTURE_SOURCE_MAP.md` (per-repo evidence source)
- `/app/memory/AGENT_INSTRUCTIONS.md` (migration policy)
- `/app/PRICING_DEFAULTS_AUDIT.md`, `/app/design_guidelines.md`, `/app/plan.md`

**Purpose:** Establish the final authoritative product scope, decision register, terminology lock, module inventory, add-on boundaries, integration register, money and commercial policy, portal-auth direction, permission catalog, code-organization decisions, reuse policy, never-again register, open-decision register, internal build-checkpoint recommendation, and commercial-release gate for the permanent commercial SignGuy AI application.

**Deliberate limits of this document:**
- No application code is created, modified, or migrated.
- No routes, models, pages, services, integrations, or database collections are added.
- No final master build plan is created (Prompt 4).
- Any stage numbering below is a **proposed dependency reference**, not a locked plan.

**Evidence-level legend** (carried forward from prior audit):

| Symbol | Meaning |
|---|---|
| **RV** | Runtime Verified against SIGNGUY-MVP |
| **STHV** | Source Tree Hash Verified |
| **FSV** | Full Source Verified (file read line-by-line) |
| **PSI** | Partially Source Inspected (module preflight required before implementation) |
| **SS** | Spec + Scaffold present |
| **SO** | Spec Only |
| **RS** | Reference Only (donor code, unsafe or incompatible for direct port) |

**Decision-status legend** (used throughout Parts 4–15):

| Label | Meaning |
|---|---|
| **LOCKED** | Non-negotiable finding or already ratified by owner; no reopening. |
| **OWNER APPROVED IN THIS REGISTER** | Resolved in this document by referencing a prior explicit owner statement. |
| **RECOMMENDED** | Recommendation made based on inspected evidence; enters implementation only after owner approves in Prompt 4 preflight. |
| **REQUIRES MODULE PREFLIGHT** | Cannot be finalised until the affected donor module is fully traced. Does NOT block scope. |
| **REQUIRES FUTURE IMPLEMENTATION DETAIL** | Direction is locked; concrete values (numbers, thresholds, model versions) come during module implementation. |
| **REMOVE / DEPRECATE** | Explicitly excluded from the permanent product. |

---

# PART 1 — FINAL PRODUCT DEFINITION

## 1.1 What SignGuy AI Is

**SignGuy AI** is the permanent commercial business-management platform for sign, graphics, wrap, print, and apparel shops. It replaces the fragmented mixture of paper job tickets, spreadsheets, generic CRMs, disconnected estimating tools, ad-hoc email quoting, and manual production tracking that these shops use today. It unifies the entire flow from **customer** → **quote** → **order** (with line items) → **work order** (for items requiring production) → **production** → **invoice** → **payment**, and layers document workflow, customer/employee/webstore portals, industry-specific pricing calculators, AI design and productivity tools, Wrap Lab workflow, inventory, payroll, reports, and commercial billing on top of that spine.

**SIGNGUY-MVP is the permanent commercial product**, not a disposable MVP. Every feature currently missing is a build-out gap in the permanent product, not a "deferred by MVP scope" concession. The application will not be sold until all approved final-product features are implemented, integrated, tested, secure, tenant-safe, permission-safe, stable, documented, and working together.

## 1.2 Who It Is For

- **Sign shops** — rigid signs, cut vinyl, banners, ADA/wayfinding, permit-required signage.
- **Graphics shops** — vehicle graphics, wraps, fleet, decal, digital print.
- **Wrap shops** — vehicle wraps, boat wraps, architectural wraps, wrap installers and inspectors.
- **Print shops** — digital print, wide-format, apparel print.
- **Apparel shops** — screen print, DTG, embroidery, promotional merch resellers.
- **Related businesses** — small design studios or mixed businesses that combine any of the above.

Users inside a shop:
- Shop owners, admins, and managers (financial + configuration).
- Sales staff (leads, quotes, customer service).
- Designers (artwork, proofs).
- Production staff and installers (work orders, install scheduling).
- Employees (time clock, tasks, timesheets, employee portal).

External users:
- Customers (customer portal, proof approval, signatures, quote acceptance, payment).
- Webstore owners and managers (webstore administration, product management, orders).
- Public visitors (marketing site, public forms, public quote requests, storefronts).

## 1.3 What Business Problems It Solves

1. **Loss of revenue from disorganised quoting.** Industry-specific calculators produce consistent pricing with real materials + labor + overhead + margin.
2. **Missed jobs and pricing errors from paper job tickets.** Digital orders with items, work orders, and pricing snapshots eliminate transcription loss.
3. **Slow customer approval cycles.** Proof review, signatures, and payment happen through the customer portal without email chains.
4. **Cash-flow errors from bad invoice reconciliation.** Independent document + financial status on invoices, unified Payment collection with idempotency, void-with-reason, and Stripe two-step reconciliation.
5. **Production chaos.** Work orders are generated only for items that require production, so the production board is not polluted by service or promo line items.
6. **Repeat design work.** DocuLink templates, signature-ready documents, and AI-assisted design generation reduce time-per-quote.
7. **Fragmented sales channels.** Webstores let shops sell to schools, teams, and enterprise buyers without a separate e-commerce provider.
8. **Time and payroll leakage.** Time clock, timesheets, and payroll are linked to orders and work orders so labor cost feeds pricing intelligence.
9. **No unified analytics.** Reports and analytics span quoting, production, payroll, inventory, and AI credit consumption.
10. **Manual customer communication.** SendGrid email, in-app notifications, SMS/MMS (roadmap), and customer/employee portals replace scattered email threads.

## 1.4 What Makes It Different From Generic Software

- **Industry-specific calculators, not generic invoicing.** Nine category calculators (rigid signs, banners, cut vinyl, digital print, vehicle wrap, apparel, services, promo/misc, custom) with `sell_rate_per_sqft`, `cost_plus`, `max_of_both`, `package_benchmark`, and `price_table` methods.
- **Order Items with per-item pricing snapshots.** Every line item captures its own labor / material / total cents at commit time, so historical quotes remain accurate.
- **`production_required` gate.** Work Orders snapshot only physical-production items — a distinction generic ERPs lack.
- **Wrap Lab / Wrap Command Center.** A dedicated 11-stage workflow engine with stage gates for high-value wrap jobs.
- **Webstores add-on.** Shops sell branded storefronts to schools/teams/enterprise clients without a separate e-commerce provider.
- **AI Tools tailored to the sign & graphics industry.** A 24-tool catalog covering AI Sign Designer, Vehicle Wrap Mockup, Font Identifier, Image Vectorizer, Wrap Cost Calculator, Permit Research, Business Copywriter, Pricing Intelligence, and more.
- **Portal + Public systems by design.** Customer portal, employee portal, webstore owner portal, webstore manager portal, public forms, public questionnaires, public quote request, public proof approval, public signatures, marketing website — first-class citizens, not afterthoughts.
- **Single tenant-safe backend.** All add-ons and standalone products share the same core (Customers, Orders, Documents, Payments, Files, Email, Users, Audit) with feature-entitlement gating.
- **Cents-safe money everywhere in commerce.** Integer cents on Quote/Order/Invoice/Payment/WorkOrder; float dollars only in pricing configuration. Single, documented pricing→commerce conversion boundary.

## 1.5 How AI Supports the Business

AI supports the business through the Creative Studio and the AI Tools grid. AI does not replace professional design or production judgment. Every AI generation is:
- Metered against a **tenant AI credit ledger**.
- Persisted to a **DocuLink-linked `ai_responses` collection** where AI-generated documents are marked `source_type=ai_generated` and `requires_review=True` before customer-facing publication.
- Provider-abstracted (Emergent LLM key with model-selection rules per tool intensity).
- Subject to per-tool credit cost, failure/refund behavior, cost caps, abuse prevention, and provider-outage fallbacks.

**Prohibited AI behaviors** in the permanent product:
- No AI system autonomously sends emails, sends SMS, alters invoices, records payments, changes pricing, or triggers Stripe events.
- No AI-generated document is published customer-facing without review markers.
- No AI system runs without credit metering and tenant cost caps.

## 1.6 How the Product Connects

```
Customers ─┬── Quotes ── Quote Line Items ─────────────┐
           │                                            │
           ├── Orders ── Order Items ─┬── Work Orders ──┼── Production
           │                          │                  │
           ├── Invoices ── Payments ──┴── (production_required = True items only)
           │
           ├── Documents ── DocuLink ── Templates ── Forms ── Questionnaires ── Signatures ── Proofs ── Approvals
           │
           ├── Customer Portal ── (proof review, signatures, invoice view, payment, messaging)
           │
           ├── Webstores ── Webstore Products ── Webstore Orders ── Stripe Connect ── Payouts
           │
           ├── Wrap Lab ── 11-stage workflow ── Approvals ── Signatures ── Portal projection (public_project())
           │
           ├── Pricing (config) ── Materials ── Labor ── Overhead ── Calculators ── Snapshot into Order Items
           │
           ├── Inventory & Purchasing ── Inventory ── Vendors ── Purchasing ── Receiving ── Locations ── Low-stock Alerts
           │
           ├── Team & Workflow ── Tasks ── Kanban ── Team Schedule ── Appointments ── Time Clock ── Timesheets ── Payroll
           │
           ├── Reports ── Analytics ── Custom Report Builder
           │
           └── Creative Studio ── AI Tools ── AI Assistant ── AI Credits ── Prompt Library ── AI-Generated Files
```

## 1.7 What Must Be True Before the Product Can Be Commercially Sold

The permanent product may be sold only when every gate in **Part 15 (Commercial-Release Gate)** passes. In summary:
- All approved required modules implemented.
- All approved portals implemented.
- All approved add-ons implemented (Webstores, Wrap Lab).
- AI systems implemented with credit metering and provider abstraction.
- Production secrets rotated; dev bypass disabled; tenant/permission/portal isolation tested end-to-end.
- Payment safety verified: idempotency, overpayment reject, controlled void, Stripe webhook reconciliation, refund path.
- All commercial pricing values approved (Part 7B).
- Documentation, support process, terms/policies, marketing site, public pricing published.
- No release blocker open at commercial launch.

## 1.8 What the Permanent Product Is Not

- Not a rebuild-in-progress. `SIGNGUY-MVP` is the destination.
- Not a job-ticket system. Terminology `Job / Job Item / Job Ticket / Production Ticket / Job Ticket Summary` is prohibited as canonical.
- Not a generic CRM.
- Not a "reduced launch edition" or "trial version" sold at a discount.
- Not a single-tenant product. It is multi-tenant with strict tenant isolation.
- Not dependent on any donor repository at runtime.
- Not free of feature entitlements. Add-ons and standalone products are entitlement-gated but never duplicated in code.

## 1.9 Repository Roles (locked)

| Repository | Role | Status |
|---|---|---|
| `dnblack323/SIGNGUY-MVP` | **PERMANENT PRODUCT** | Active development. Only repo that receives new commits. |
| `dnblack323/SIGNGUY-AI-OS` | Read-only mirror of MVP under `backend/app/**/*.py` (STHV, scoped) | No new development. Complete-tree comparison + archive timing deferred until final commercial completion. No deletion. |
| `dnblack323/signguyai_rebuild_version` (REB) | Architecture reference + working-scaffold code donor | Read-only reference throughout the build. Sanitise preview code + `core_runtime` imports on port. |
| `dnblack323/signguy-ai-feb22` (FEB) | Financial-logic donor (Invoice + Payment) | Read-only reference. Rename `job_id`→`order_id` on port. |
| `dnblack323/signguyai` (ORIG) | Feature discovery map + targeted donor (object_storage, signatures, approvals, portal, stripe patterns) | Read-only reference. Module preflight required before any port. Never copy monolithic `App.js`, giant pricing files, dev/backup routes, or Job-domain routes. |

**Locked rule.** No donor repository is deleted before final commercial completion.

---

# PART 2 — LOCKED TERMINOLOGY REGISTER

## 2.1 Canonical Product Terms (LOCKED)

| Canonical term | Meaning | Prohibited synonyms |
|---|---|---|
| **Customer** | An external buyer entity linked to a tenant. Has contacts, addresses, notes, quotes, orders, invoices, portal access. | Client (in canonical UI), Account (in canonical UI). |
| **Lead** | A pre-customer inquiry captured via public forms or manual intake. Converts to Customer + Quote on qualification. | Prospect (in canonical UI). |
| **Quote** | A priced proposal, versioned, expiring, sendable, approvable, declinable, convertible to Order. Contains Quote Line Items. | Estimate (as canonical model name — allowed as customer-facing label option). |
| **Order** | An accepted or in-progress commitment to fulfill work. Contains Order Items. | **Job**, **Job Ticket**, **Job Item**. |
| **Order Item** | A single line on an Order with category, quantity, unit price cents, pricing snapshot, `production_required` flag, artwork status, proof status. | **Job Item**, **Job Ticket Item**. |
| **Work Order** | The production-side snapshot generated from an Order for items requiring production. May be delivered as a printable Work Order Summary. | **Production Ticket**, **Job Ticket Summary**, **Job Ticket**. |
| **Work Order Summary** | The printable, PDF/print view of a Work Order for shop-floor and installer use. | Job Ticket Summary. |
| **Invoice** | A billable document referencing an Order and its line items with tax/discount/fee snapshots, independent `document_status` and `financial_status`. | — |
| **Payment** | A single money movement (manual or Stripe) attached to an Invoice; unified collection; idempotent; void-with-reason. | — |
| **Proof** | A visual artwork proof attached to an Order Item; versioned; watermarked; portal-visible. | Mock-up (allowed as UI synonym; not canonical model). |
| **Approval** | A customer or internal decision event on a Proof, Contract, or Work Order Summary. | Sign-off. |
| **Document** | Any file in DocuLink (contract, quote PDF, invoice PDF, proof, permit, form response, questionnaire, template, AI-generated file). | File (allowed as low-level storage term). |
| **Template** | A reusable Document, Email, or Form definition scoped to a tenant. | Blueprint. |
| **Questionnaire** | A structured multi-step customer intake tied to an Order/Wrap/Webstore. | — |
| **Form** | A single-step public or private data-capture form. | — |
| **Signature Request** | A request to sign a Contract, Proof, Pre-Install Packet, or Final Packet. | E-sign, DocuSign (allowed only as vendor comparison label). |
| **Webstore** | A branded storefront owned by a Webstore Owner (may be the shop itself or a third party such as a school/team). | Storefront (allowed as customer-facing UI label). |
| **Webstore Owner** | The identity that owns a Webstore. Can manage products, orders, and Managers. May or may not be a SignGuy shop. | Store Owner. |
| **Webstore Manager** | An identity assigned to help operate a Webstore's orders/products without owning it. | Store Manager. |
| **Wrap Project** | A single Wrap Lab record advancing through 11 stages. | Wrap Job. |
| **Tenant** | The isolated data boundary owned by a shop. All business collections carry `tenant_id`. | Workspace (UI synonym allowed for portal invitations only). |
| **Organization** | UI-facing synonym for Tenant, used on onboarding and settings screens. | — |
| **User** | A staff identity inside a Tenant with a Role. | Staff (allowed as UI category label). |
| **Employee** | A User with employment fields (start date, department, employment type, payroll rate) — a superset of User for payroll modules. | — |
| **Platform Admin** | A cross-tenant identity operating the SignGuy AI platform itself. | — |
| **AI Credit** | The unit consumed when running an AI Tool. Metered per tenant. | Token (avoid; overloaded with LLM token). |
| **Subscription** | A tenant's active plan (Core, Webstores, Wrap, Complete Bundle). | Plan (allowed as UI label). |
| **Add-on** | An optional feature bundle purchased on top of a Subscription (e.g., Webstores add-on, Wrap Lab add-on). | Extension. |
| **Entitlement** | A single boolean/quota controlling whether a Tenant may access a feature or how much of it. | Feature flag (allowed as low-level term for per-shop toggles). |

## 2.2 Prohibited Canonical Terms → Permanent Replacement

| Prohibited term | Reason | Permanent replacement |
|---|---|---|
| **Job** | Donor-era terminology from ORIG/FEB; causes model conflicts. | **Order**. |
| **Job Item** | Same. | **Order Item**. |
| **Job Ticket** | Legacy paper concept; conflicts with Work Order. | **Work Order** (for the production snapshot) or **Order Item** (for the source line). |
| **Production Ticket** | Ambiguous; conflicts with Work Order. | **Work Order**. |
| **Job Ticket Summary** | Legacy paper concept. | **Work Order Summary**. |

For every prohibited term, backend fields (`job_id`, `job_ticket_id`), collections (`db.jobs`), route paths (`/jobs`, `/job-tickets`), nav labels ("Jobs"), UI copy ("Job #"), and audit-event names (`job.created`) must use the permanent replacement.

## 2.3 Locked Process Terminology (workflow contracts)

- **Quote → Order.** A Quote converts to an Order via an idempotent `find_one_and_update` guard. The conversion is a first-class event with an audit trail. A Quote may have multiple revisions but only one converted Order.
- **Order → Order Items.** An Order contains one or more Order Items. Order Items carry `production_required: bool | None`. When `None`, the default is derived from `services/order_item_rules.py::default_production_required(item_category)` (from REB, `PHYSICAL_PRODUCTION_CATEGORIES = {rigid_signs, banners, cut_vinyl, digital_print, vehicle_wrap, apparel, promo_misc, custom}`).
- **Order → Work Orders.** Work Orders are generated **only** for Order Items with `production_required=True`. Work Orders never snapshot Order Items with `production_required=False` (e.g., services, promo/misc line items).
- **Order → Invoice.** An Order generates or converts into exactly one Invoice via a unique compound index `(tenant_id, order_id)`.
- **Invoice ← Payments.** Payments belong to Invoices via `invoice_id`. Payment status and Invoice document status remain **separate**. An Invoice has `document_status` (draft/sent/void) and `financial_status` (unpaid/partially_paid/paid/refunded/overpaid) as **independent** dimensions.
- **Production → Work Order.** Production staff receive a Work Order or Work Order Summary as their input. Production never sees an Order Item directly.
- **Customer proof approval ≠ internal production completion.** Customer approvals live in the Approval collection. Internal production completion is a separate state transition on the Work Order.

## 2.4 Naming Rules (LOCKED)

| Surface | Rule |
|---|---|
| **API routes** | Plural, kebab-case, no `/jobs`. Examples: `/api/orders`, `/api/order-items`, `/api/work-orders`, `/api/quote-line-items`, `/api/invoices`, `/api/payments`, `/api/wrap-projects`. |
| **Model class names** | `Order`, `OrderItem`, `WorkOrder`, `WorkOrderItemSnapshot`, `Quote`, `QuoteLineItem`, `Invoice`, `InvoiceLineItem`, `Payment`, `WrapProject`. |
| **MongoDB collections** | `orders`, `order_items`, `work_orders`, `quotes`, `quote_line_items`, `invoices`, `invoice_line_items`, `payments`, `wrap_projects`, `attachments`, `documents`, `document_shares`, `file_links`, `document_links`. Never `jobs`. |
| **Field names** | Money commerce fields: `<x>_cents` (integer). Pricing configuration fields: unsuffixed dollar `Decimal`/`float` (rare — only in `pricing_settings`). Foreign keys: `<entity>_id`. Timestamps: `<verb>_at` in UTC. |
| **Navigation labels** | Match Part 3.1 exactly. Never mix "Job" and "Order" in any nav. |
| **Page titles** | Match nav labels. No `Job Details` — use `Order Details`. |
| **Portal labels** | External-facing labels may be softened for customers (e.g., "Your Order", "Your Proof") but never revert to "Job". |
| **Audit-event names** | `<domain>.<verb>` — `order.created`, `order.item_added`, `work_order.generated`, `invoice.sent`, `payment.recorded`, `payment.voided`, `wrap_project.stage_advanced`. Never `job.*`. |
| **Documentation** | All internal docs, comments, and error messages use canonical terms. |

---

# PART 3 — FINAL NAVIGATION AND PRODUCT-AREA INVENTORY

## 3.1 Top-Level Navigation Structure (LOCKED direction)

The application uses a **collapsible left sidebar** as the primary navigation surface. The major areas appear in the left sidebar. Each major area opens a **side flyout submenu** containing its modules. The main second-level module navigation is **NOT** placed permanently across the top of every page.

**Selected module pages may still use:**
- compact Office-style ribbons
- page-specific tabs
- filters
- view selectors
- actions
- breadcrumbs

These page controls must not duplicate the main sidebar or flyout navigation. **Home** remains a simple icon returning to the overall application dashboard.

**Final top-level sidebar labels (LOCKED):**

```
[HOME]
Shop Operations
Business & Finance
Team & Workflow
Creative Studio
─── (divider) ───
Control Center
Help & Community
```

All product-level modules live under exactly one of these six flyout areas. Individual reports, settings screens, and utility pages **do not become separate top-level modules**.

## 3.2 Area Flyouts

### 3.2.1 Shop Operations (flyout)

- **Purpose:** Day-to-day sales and production workflow.
- **Overview/Dashboard:** Cross-module summary (open quotes, active orders, work orders in production, unpaid invoices, recent proofs pending approval, recent portal activity).
- **Flyout entries (LOCKED):**
  - Overview
  - Customers
  - Quotes
  - Orders
  - Production
  - Shop Schedule
  - Asset Library
  - Inventory & Purchasing
  - Webstores
  - Wrap Lab
- **Rules:**
  - **Asset Library** is the user-facing navigation label for the broader DocuLink-backed document/library system. **DocuLink** remains the backend/system name where technically appropriate.
  - **Inventory & Purchasing** combines Inventory, Vendors, Purchasing, Receiving, material quantities, Locations, and low-stock alerts under a single flyout destination.
  - **Proofs and Approvals** are NOT a permanent sidebar flyout destination. They are connected workflows available within Orders, Production, Customer records, and Asset Library.
  - **Customer invoices and payments** are operationally connected to Orders — surfaced from Order Detail. Financial analysis of invoices and payments lives in Business & Finance.
  - **Shop Schedule** covers production, installations, appointments, pickups, and deliveries (shop-facing scheduling).
- **Portal connections:** Customer Portal, Webstore Owner/Manager Portals.
- **Shared systems used:** Auth, Tenants, Permissions, Object Storage, Sequences, Audit, SendGrid, Pricing (calculator surface), Documents, Approvals, Signatures, Notifications, Feature Entitlements.
- **Recommended ribbon purpose (page-level, non-nav):** row-level and page-level actions (New Customer, Convert to Order, Generate Invoice, Print Work Order Summary, Send Proof, Approve Proof), plus quick filters (Status, Owner, Recency).
- **Items that must NOT be separate flyout entries:** individual per-order screens, per-customer detail screens, per-work-order detail, per-invoice detail, portal-view previews, Proofs and Approvals.
- **Legacy routes to consolidate or remove:** All ORIG `/jobs`, `/job-tickets`, `/production-tickets`, `LegacyJobRedirect.js` — removed.

### 3.2.2 Business & Finance (flyout)

- **Purpose:** Financial reporting, analysis, and business-wide financial management.
- **Overview/Dashboard:** Financial KPIs (MTD revenue, unpaid balance, expenses, profit), cash-flow snapshot, tax snapshot, payment-method breakdown.
- **Flyout entries (LOCKED):**
  - Overview
  - Financials
  - Sales
  - Expenses
  - Taxes
  - Reports
  - Business Analytics
- **Rules:**
  - **Payroll does NOT belong here** — Payroll lives under Team & Workflow.
  - **Employee scheduling does NOT belong here** — lives under Team & Workflow.
  - **Materials, inventory, vendors, and purchasing do NOT belong here** — live under Shop Operations → Inventory & Purchasing.
  - **The shop's own SignGuy AI subscription and AI-credit purchasing do NOT belong here** — live under Control Center → Subscriptions & AI Credits.
  - **Financials** includes: revenue; accounts receivable; payments received; unpaid and overdue invoice balances; refunds and voids; gross profit; net-profit estimates; margins; cash-flow snapshots; Webstore revenue; Wrap Lab revenue; tax collected; payment-method breakdown.
  - **Financials reports on invoices and payments but does not duplicate operational Invoice Detail or Payment History screens** — those remain accessible from Orders / Shop Operations.
  - **Reports** may contain payroll reports, employee reports, inventory reports, and production reports, **but the management of those systems remains in their proper product areas** (Payroll in Team & Workflow; Inventory in Shop Operations; Employees in Team & Workflow).
- **Shared systems used:** Auth, Permissions, Audit, Feature Entitlements, Reports, Analytics.
- **Recommended ribbon purpose (page-level):** report generation, filter by period, export.
- **Items that must NOT be separate flyout entries:** individual saved reports (live under Reports); individual invoices/payments (live under Shop Operations → Orders/Invoices).
- **Legacy routes to consolidate or remove:** ORIG `Financials.js`, `PricingPlansV2.js`, `Pricing.js` — reused as reference only; do not persist as separate top-level nav.

### 3.2.3 Team & Workflow (flyout)

- **Purpose:** Internal team collaboration, employee management, scheduling, time, payroll, and productivity.
- **Overview/Dashboard:** Team activity, open tasks by owner, calendar heat, time-clock summary, unread internal messages, published schedule.
- **Flyout entries (LOCKED):**
  - Overview
  - Employees
  - Tasks & Kanban
  - Team Schedule
  - Time Clock
  - Timesheets
  - Payroll
  - Messages & Notes
  - Announcements
  - Employee Portal
- **Rules:**
  - **Payroll permanently belongs under Team & Workflow.** Includes pay periods, pay calculations, advances, adjustments, carryover, payments, history, and exports.
  - **Employee scheduling permanently belongs under Team & Workflow.**
  - **Team Schedule** covers employee shifts, availability, time off, and published schedules.
  - **Time Clock and Timesheets** remain separate flyout entries because they are frequently used operational surfaces.
- **Shared systems used:** Users, Permissions, Notifications, Audit.
- **Recommended ribbon purpose (page-level):** assign task, add appointment, punch clock, send announcement.
- **Items that must NOT be separate flyout entries:** per-employee screens (drill-in only).

### 3.2.4 Creative Studio (flyout)

- **Purpose:** AI-assisted image, design, writing, prompt, artwork, and generated-content workflows. Creative Studio contains more than graphic design.
- **Overview/Dashboard:** AI credits remaining, recent AI generations, prompt library entries, generated assets awaiting review.
- **Flyout entries (LOCKED):**
  - Studio Overview
  - AI Assistant
  - Image Tools
  - Design Tools
  - Writing Tools
  - Prompt Library
  - Artwork Workspace
  - Generated Assets
  - AI History
- **Rules:**
  - **Renamed** from "Design Studio" to **Creative Studio**.
  - Creative Studio contains AI image, design, writing, prompt, artwork, and generated-content workflows.
  - **AI-credit purchasing and plan administration remain in Control Center**, not Creative Studio.
- **Shared systems used:** AI credit ledger, DocuLink (`source_type=ai_generated → requires_review`), Feature Entitlements, Object Storage.
- **Recommended ribbon purpose (page-level):** Launch tool, insert generated asset into current Order Item, mark reviewed.
- **Items that must NOT be separate flyout entries:** individual AI response records.

### 3.2.5 Control Center (flyout, below divider)

- **Purpose:** Company-wide configuration, users/permissions, integrations, pricing defaults, portals, tenant subscription + AI credits, feature access, platform governance (visible only to platform-authorized roles), data & security.
- **Overview/Dashboard:** Health checks — production readiness, tenant configuration completeness, integration connection status.
- **Flyout entries (LOCKED):**
  - Overview
  - Company Settings
  - Users & Permissions
  - Integrations
  - Pricing Defaults
  - Portals
  - Subscriptions & AI Credits
  - Feature Access
  - Platform Governance
  - Data & Security
- **Rules:**
  - **Pricing Defaults** contains shop rate, labor rates, materials defaults, markups, minimum charges, category defaults, complexity settings, and formula configuration. Operational Pricing Calculator access may appear as a shortcut elsewhere (e.g., inside Quotes/Orders), but permanent configuration lives here.
  - **Subscriptions & AI Credits** manages the tenant's own SignGuy AI account: plan, add-ons, credit balance, top-ups, billing history, and payment method. **It does not manage the shop's customer invoices.**
  - **Platform Governance** is visible ONLY to platform-authorized roles (Platform Creator, Platform Admin). Use "Platform Governance" — never "Platform Governments."
  - **Data & Security** covers audit log surface, retention, export/deletion tools, key rotation, and security posture.
- **Shared systems used:** Auth, Permissions, Settings framework, Feature Entitlements, Audit.
- **Recommended ribbon purpose (page-level):** invite user, edit role, connect integration, rotate secret, view audit trail.
- **Items that must NOT be separate flyout entries:** individual integration screens (subpages of Integrations).

### 3.2.6 Help & Community (flyout, below divider)

- **Purpose:** In-app documentation, onboarding, community, bug reports, feature requests, contact support, and release notes.
- **Overview/Dashboard:** Getting started tiles, contextual help links, community stats.
- **Flyout entries (LOCKED):**
  - Help Center
  - Documentation
  - Onboarding
  - Community
  - Bug Reports
  - Feature Requests
  - Contact Support
  - What's New
- **Rules:**
  - **Bug Reports and Feature Requests may share the Community backend** (categorised posts), but they remain **directly accessible flyout destinations**, not buried inside Community.
  - **Contact Support** is a first-class flyout entry (ticket submission + email path).
  - **What's New** is the release notes / changelog surface.
- **Shared systems used:** Community Hub, Audit, SendGrid (for support ticket routing).
- **Recommended ribbon purpose (page-level):** search help, submit bug, submit feature request.

## 3.3 Portals and Public Systems

Portals are not sidebar destinations in the internal app. They are separately-routed, separately-authenticated surfaces sharing the same backend and tenant architecture (see Part 5).

- **Customer Portal** — proof review, signatures, invoice view, payment, messaging.
- **Employee Portal** — time clock, task view, timesheet review, payroll visibility (payslip view scoped by owner decision, see Part 13).
- **Webstore Owner Portal** — webstore products, orders, managers, payouts.
- **Webstore Manager Portal** — webstore orders + operational actions granted by the Owner.
- **Public Storefront** — customer-facing webstore product browsing + checkout.
- **Public Forms / Questionnaires** — lead capture, quote intake, wrap intake, permit intake.
- **Public Quote Request** — standalone quote request form.
- **Public Proof Approval** — one-time-token public link for proof approval.
- **Public Signatures** — one-time-token public signature link for contracts, packets.
- **Marketing Website** — LandingPage, About, Features, Contact, Pricing — separate static site (or public routes) with its own SEO.
- **Public Pricing** — plan comparison page.

## 3.4 Rules That Prevent Nav Bloat

- **No separate top-level modules** for individual reports, individual settings screens, individual utility pages. They live inside a larger bounded area's flyout.
- **No permanent second-level top navigation** across every page. Second-level navigation lives in the sidebar flyout; page-level tabs/ribbons/filters are page-specific and do not duplicate the flyout.
- **No duplicate menus** (e.g., no separate "Job Ticket" nav alongside "Work Order").
- **No duplicate dashboards** (single Shop Ops dashboard, single Business & Finance dashboard, single Team & Workflow dashboard, single Creative Studio dashboard).
- **No legacy redirect** treated as a permanent nav entry.
- **No overflow "More" menu** where a ribbon can fit the items compactly.
- **Pricing configuration lives in Control Center → Pricing Defaults.** The Pricing Calculator may appear as an operational shortcut inside Quotes/Orders when useful, but permanent configuration does not scatter across product areas.
- **Tenant subscription and AI-credit purchasing live in Control Center → Subscriptions & AI Credits.** They do not sit next to shop-side financial reporting.

---

# PART 4 — FINAL MODULE INVENTORY

Every approved module must be included before commercial release unless explicitly removed in this register. Each module is grouped by product area.

**Column keys:**
- **Sc.** = Scope: `I`=Internal (staff), `P`=Portal (external identity), `Pu`=Public (no auth or scoped token), `Pl`=Platform (cross-tenant).
- **Src.** = Best source repository (MVP / REB / FEB / ORIG / New).
- **Ev.** = Evidence level (FSV / PSI / SS / SO / RS / RV / New).
- **Preflight** = Y if requires module preflight before implementation.
- **CR** = Commercial-release requirement: `REQ`=required, `REQ-DEP`=required after dependencies, `ADD`=advanced/add-on module, `OWNER`=owner decision, `REMOVE`=explicitly excluded.
- **Standalone** = Y if module can be sold as a standalone product.
- **AI/Msg/OS/Stripe/Audit/Sensitive/Owner** = Uses AI credits / Uses messaging / Uses object storage / Uses Stripe / Requires audit history / Contains sensitive info / Requires owner decisions.

## 4.1 Foundation and Shared Systems

| Module | Sc. | Src. | Ev. | Preflight | CR | Standalone | AI | Msg | OS | Stripe | Audit | Sensitive | Owner |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Authentication and Account Access | I,P | MVP | RV+FSV | N | REQ | N | N | N | N | N | Y | Y | N |
| Tenants and Organizations | I,Pl | MVP | RV | N | REQ | N | N | N | N | N | Y | Y | N |
| Users | I | MVP | RV | N | REQ | N | N | N | N | N | Y | Y | N |
| Roles | I | REB+MVP | FSV+RV | N | REQ | N | N | N | N | N | Y | N | Y |
| Permissions | I | REB+MVP | FSV | N | REQ | N | N | N | N | N | Y | N | Y |
| Application Shell | I | MVP | RV | N | REQ | N | N | N | N | N | N | N | N |
| Navigation | I,P | MVP | RV | N | REQ | N | N | N | N | N | N | N | N |
| Shared UI Components | I,P | MVP | RV | N | REQ | N | N | N | N | N | N | N | N |
| Settings Framework | I | REB | FSV | N | REQ | N | N | N | N | N | Y | N | N |
| Audit Log / Activity History | I,Pl | MVP+REB | RV+FSV | N | REQ | N | N | N | N | N | Y | Y | N |
| Notifications (in-app) | I,P | REB | FSV | N | REQ | N | N | Y | N | N | Y | N | N |
| Email (SendGrid outbound) | I,P | MVP | RV | N | REQ | N | N | Y | N | N | Y | Y | N |
| Email Activity Log + Webhook | I,Pl | REB | FSV | N | REQ | N | N | Y | N | N | Y | Y | Y |
| SMS/MMS | I,P | ORIG | RS | Y | OWNER DECISION — COMMERCIAL RELEASE TIMING (permanent-product scope; timing per Decision 27) | N | N | Y | N | N | Y | Y | Y |
| Internal Messaging (staff↔staff) | I | ORIG+REB | RS+FSV | N | REQ-DEP | N | N | Y | Y | N | Y | N | N |
| Object Storage | I,P | MVP | RV | N | REQ | N | N | N | Y | N | Y | Y | N |
| File Uploads | I,P | MVP | RV | N | REQ | N | N | N | Y | N | Y | Y | N |
| Upload Validation | I,P | REB | FSV | N | REQ | N | N | N | Y | N | Y | Y | N |
| Attachments (polymorphic) | I,P | MVP+REB | RV+FSV | N | REQ | N | N | N | Y | N | Y | N | N |
| Forms | I,Pu | ORIG | RS | Y | REQ | N | N | N | Y | N | Y | Y | N |
| Questionnaires | I,Pu | ORIG+REB | RS+SO | Y | REQ | N | N | N | Y | N | Y | Y | N |
| Templates (doc + email) | I | REB+ORIG | FSV+RS | N | REQ | N | N | Y | Y | N | Y | N | N |
| Signatures | I,P,Pu | ORIG | PSI | Y | REQ | N | N | N | Y | N | Y | Y | N |
| Global Search | I | New | New | N | REQ-DEP | N | N | N | N | N | N | N | N |
| Background Jobs / Scheduler | I,Pl | ORIG+New | RS+New | N | REQ-DEP | N | N | N | N | N | Y | N | N |
| Webhook Infrastructure | I,Pl | REB+FEB | FSV | N | REQ | N | N | Y | N | Y | Y | Y | Y |
| Error Logging | I | MVP | RV | N | REQ | N | N | N | N | N | N | N | N |
| Monitoring | I,Pl | New | New | N | REQ | N | N | N | N | N | N | N | N |
| Feature Flags / Entitlements | I,Pl | REB+SS | FSV+SS | N | REQ | N | N | N | N | N | Y | N | Y |
| Subscription Access | I,Pl | REB | FSV | Y | REQ | N | N | N | N | Y | Y | Y | Y |
| AI Credit Ledger | I,Pl | REB+ORIG | FSV+RS | Y | REQ-DEP | N | Y | N | N | Y | Y | N | Y |

## 4.2 Shop Operations

| Module | Sc. | Src. | Ev. | Preflight | CR | Standalone | AI | Msg | OS | Stripe | Audit | Sensitive | Owner |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Customer CRM | I,P | MVP | RV | N | REQ | N | N | Y | Y | N | Y | Y | N |
| Customer Detail | I,P | MVP | RV | N | REQ | N | N | Y | Y | N | Y | Y | N |
| Communication History | I | REB+MVP | FSV+RV | N | REQ | N | N | Y | N | N | Y | Y | N |
| Quotes | I,P | REB | FSV | N | REQ | N | N | Y | Y | N | Y | Y | N |
| Quote Line Items | I | REB | FSV | N | REQ | N | N | N | N | N | Y | N | N |
| Quote Approval | I,P | REB | FSV | N | REQ | N | N | Y | N | N | Y | N | N |
| Quote-to-Order Conversion | I | MVP+REB | RV+FSV | N | REQ | N | N | N | N | N | Y | N | N |
| Orders | I,P | REB | FSV | N | REQ | N | N | Y | Y | N | Y | Y | N |
| Order Items (rich, 40+ fields) | I | REB | FSV | N | REQ | N | N | N | N | N | Y | N | N |
| Order Pricing Snapshots | I | REB | FSV | N | REQ | N | N | N | N | N | Y | N | N |
| `production_required` gate | I | REB | FSV | N | REQ | N | N | N | N | N | Y | N | N |
| Invoices (dual status) | I,P | FEB | FSV | N | REQ | N | N | Y | Y | N | Y | Y | Y |
| Payments (unified) | I,P | FEB | FSV | N | REQ | N | N | Y | N | Y | Y | Y | Y |
| Payment History | I,P | FEB | FSV | N | REQ | N | N | N | N | Y | Y | Y | N |
| Production | I | MVP+REB | RV+FSV | N | REQ | N | N | Y | Y | N | Y | N | N |
| Work Orders | I | MVP+REB | RV+FSV | N | REQ | N | N | N | Y | N | Y | N | N |
| Work Order Summaries | I | MVP+ORIG | RV+RS | N | REQ | N | N | N | Y | N | Y | N | N |
| Production Board | I | REB+ORIG | SS+RS | Y | REQ | N | N | Y | N | N | Y | N | N |
| Proofs | I,P | ORIG | PSI | Y | REQ | N | N | Y | Y | N | Y | N | N |
| Artwork Approvals | I,P | ORIG | PSI | Y | REQ | N | N | Y | Y | N | Y | N | N |
| DocuLink | I,P | REB | FSV | N | REQ | N | Y | Y | Y | N | Y | Y | N |
| Document Templates | I | REB+ORIG | FSV+RS | N | REQ | N | N | N | Y | N | Y | N | N |
| Inventory | I | ORIG+REB | RS+SO | Y | REQ | N | N | N | N | N | Y | N | N |
| Vendors | I | ORIG | RS | Y | REQ | N | N | N | N | N | Y | Y | N |
| Purchasing | I | ORIG | RS | Y | REQ | N | N | N | N | N | Y | Y | N |
| Webstores | I,P,Pu | REB+ORIG | FSV+SO+RS | Y | ADD | Y | N | Y | Y | Y | Y | Y | Y |
| Webstore Setup Wizard | I,P | REB | SO | Y | ADD | Y | N | Y | Y | N | Y | N | N |
| Webstore Products | I,P,Pu | ORIG | RS | Y | ADD | Y | N | N | Y | N | Y | N | N |
| Product Variants | I,P,Pu | ORIG | RS | Y | ADD | Y | N | N | Y | N | Y | N | N |
| Webstore Orders | I,P,Pu | ORIG | RS | Y | ADD | Y | N | Y | Y | Y | Y | Y | N |
| Stripe Connect | I,Pl | FEB+ORIG | FSV+RS | Y | ADD | N | N | Y | N | Y | Y | Y | Y |
| Payouts | I,Pl | FEB+ORIG | FSV+RS | Y | ADD | N | N | Y | N | Y | Y | Y | Y |
| Wrap Lab / Wrap Command Center | I,P | REB+ORIG | FSV+RS | Y | ADD | Y* | N | Y | Y | N | Y | Y | Y |

`*` Wrap Lab standalone is conditional — see Part 5. Sold standalone only if shared-core access can be provided without duplicating systems.

**Sidebar flyout note (Shop Operations):** Inventory, Vendors, and Purchasing are grouped under a single sidebar flyout entry **Inventory & Purchasing** (which also surfaces Receiving, Locations, and low-stock alerts). This is a navigation grouping; the three modules remain individually bounded and remain distinct rows in this inventory. Proofs and Artwork Approvals are connected workflows accessible from Orders, Production, Customer records, and Asset Library — they are NOT a permanent sidebar flyout destination.

## 4.3 Business & Finance

**Renamed from "Business Management" — LOCKED navigation change.** Financial reporting, analysis, and business-wide financial management only. Pricing configuration has moved to **Control Center → Pricing Defaults** (section 4.6). Tenant Subscriptions and AI Credit purchasing have moved to **Control Center → Subscriptions & AI Credits** (section 4.6). Payroll, Time Clock, Timesheets, and Employee Scheduling have moved to **Team & Workflow** (section 4.4).

| Module | Sc. | Src. | Ev. | Preflight | CR | Standalone | AI | Msg | OS | Stripe | Audit | Sensitive | Owner |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Finance Dashboard | I | ORIG+New | RS+New | Y | REQ | N | N | N | N | N | Y | Y | N |
| Financials (revenue, A/R, payments received, unpaid/overdue, refunds/voids, gross/net profit, margins, cash-flow snapshot, Webstore revenue, Wrap Lab revenue, tax collected, payment-method breakdown) | I | ORIG+New | RS+New | Y | REQ | N | N | N | N | N | Y | Y | N |
| Sales | I | ORIG+New | RS+New | Y | REQ | N | N | N | N | N | Y | Y | N |
| Expenses | I | ORIG+New | RS+New | Y | REQ | N | N | N | N | N | Y | Y | N |
| Taxes | I | New | New | Y | REQ | N | N | N | N | N | Y | Y | Y |
| Reports (may include payroll / employee / inventory / production reports — management of those systems stays in their product areas) | I | ORIG+New | RS+New | Y | REQ | N | N | N | N | N | Y | Y | Y |
| Custom Report Builder | I | ORIG+New | RS+New | Y | REQ-DEP | N | N | N | N | N | Y | Y | Y |
| Business Analytics | I,Pl | ORIG+New | RS+New | Y | REQ | N | N | N | N | N | Y | Y | N |

**Flyout rules:**
- Financials reports on invoices and payments but **does not duplicate operational Invoice Detail or Payment History screens** (those remain under Shop Operations → Orders).
- Reports may **surface** payroll/employee/inventory/production reports, but **manage** those systems in their proper product areas.
- Payroll, employee scheduling, materials/inventory/vendors/purchasing, and the tenant's own subscription do NOT belong here.

## 4.4 Team & Workflow

**Renamed from "Team and Workflow" — LOCKED navigation change.** Team collaboration, employee management, scheduling, time, payroll, and productivity. Payroll, Time Clock, Timesheets, and Employee Scheduling permanently live here (moved from Business & Finance).

| Module | Sc. | Src. | Ev. | Preflight | CR | Standalone | AI | Msg | OS | Stripe | Audit | Sensitive | Owner |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Team Dashboard | I | ORIG+New | RS+New | Y | REQ | N | N | Y | N | N | Y | N | N |
| Employees | I,P | ORIG+FEB | RS | Y | REQ | N | N | N | N | N | Y | Y | N |
| Tasks | I | ORIG+FEB | RS | Y | REQ | N | N | Y | N | N | Y | N | N |
| Kanban | I | ORIG | RS | Y | REQ | N | N | Y | N | N | Y | N | N |
| Team Schedule (shifts, availability, time off, published schedules) | I | ORIG+New | RS+New | Y | REQ | N | N | Y | N | N | Y | N | N |
| Calendar | I | ORIG | RS | Y | REQ | N | N | Y | N | N | Y | N | N |
| Appointments | I,P | ORIG | RS | Y | REQ | N | N | Y | N | N | Y | N | N |
| Install Scheduling | I | ORIG | RS | Y | REQ | N | N | Y | N | N | Y | N | N |
| Production Scheduling | I | ORIG | RS | Y | REQ | N | N | Y | N | N | Y | N | N |
| Time Clock | I,P | ORIG+FEB | RS | Y | REQ | N | N | N | N | N | Y | N | N |
| Timesheets | I,P | ORIG+FEB | RS | Y | REQ | N | N | N | N | N | Y | N | N |
| Payroll (pay periods, calculations, advances, adjustments, carryover, payments, history, exports) | I,P | ORIG+FEB | RS | Y | REQ | N | N | N | N | N | Y | Y | Y |
| Employee Scheduling | I | ORIG | RS | Y | REQ | N | N | Y | N | N | Y | N | N |
| Messages & Notes (internal notes + team communication) | I | REB+ORIG | FSV+RS | N | REQ | N | N | Y | N | N | Y | N | N |
| Announcements | I | ORIG | RS | Y | REQ | N | N | Y | N | N | Y | N | N |
| Reminders | I | New | New | N | REQ-DEP | N | N | Y | N | N | Y | N | N |
| Employee Portal | P | ORIG+FEB+New | RS+New | Y | REQ | N | N | Y | Y | N | Y | Y | Y |

**Flyout rules:**
- Payroll and Employee Scheduling permanently belong under Team & Workflow.
- Team Schedule covers employee shifts, availability, time off, and published schedules.
- Time Clock and Timesheets remain separate flyout entries (frequently used operational surfaces).

## 4.5 Creative Studio and AI

**Renamed from "Design Studio and AI" — LOCKED navigation change.** Creative Studio contains more than graphic design: AI-assisted image, design, writing, prompt, artwork, and generated-content workflows. AI-credit purchasing and plan administration live in Control Center — not here.

| Module | Sc. | Src. | Ev. | Preflight | CR | Standalone | AI | Msg | OS | Stripe | Audit | Sensitive | Owner |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| AI Tools Grid (24 tools) | I | REB | FSV | Y | REQ | N | Y | N | Y | N | Y | N | Y |
| AI Assistant | I | ORIG+REB | RS+FSV | Y | REQ | N | Y | Y | Y | N | Y | Y | Y |
| Image Tools (subset of AI Tools Grid) | I | REB+ORIG | FSV+RS | Y | REQ | N | Y | N | Y | N | Y | N | N |
| Design Tools (subset of AI Tools Grid) | I | REB+ORIG | FSV+RS | Y | REQ | N | Y | N | Y | N | Y | N | N |
| Writing Tools (subset of AI Tools Grid) | I | REB+ORIG | FSV+RS | Y | REQ | N | Y | N | Y | N | Y | N | N |
| Prompt Library | I | ORIG | RS | Y | REQ | N | Y | N | N | N | Y | N | N |
| Artwork Workspace | I | ORIG+New | RS+New | Y | REQ | N | Y | N | Y | N | Y | N | N |
| Generated Assets (with `requires_review` markers) | I,P | REB | FSV | N | REQ | N | Y | N | Y | N | Y | Y | N |
| AI History (usage history) | I,Pl | REB | FSV | N | REQ | N | Y | N | N | Y | Y | N | N |
| AI Generated Files | I,P | REB | FSV | N | REQ | N | Y | N | Y | N | Y | Y | N |
| AI Generated Documents | I,P | REB | FSV | N | REQ | N | Y | N | Y | N | Y | Y | N |
| AI Context Retrieval | I | ORIG | RS | Y | REQ-DEP | N | Y | N | N | N | Y | N | Y |
| AI Result Storage | I,P | REB | FSV | N | REQ | N | Y | N | Y | N | Y | Y | N |
| Creative Studio Workspace | I | ORIG | RS | Y | REQ | N | Y | N | Y | N | Y | N | N |
| Artwork Assets | I | New | New | N | REQ | N | N | N | Y | N | Y | N | N |

**Flyout rules:**
- Image Tools / Design Tools / Writing Tools are curated slices of the 24-tool AI Tools Grid, presented as flyout destinations for common navigation. The underlying tool catalog remains single-source.

## 4.6 Control Center (tenant configuration)

**New product-area section — reflects the sidebar flyout for tenant-level configuration surfaces.** Modules previously listed under other areas that concern tenant configuration (Pricing Defaults, Subscriptions & AI Credits, Portals, Feature Access, Data & Security) live here.

| Module | Sc. | Src. | Ev. | Preflight | CR | Standalone | AI | Msg | OS | Stripe | Audit | Sensitive | Owner |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Company Settings | I | New | New | N | REQ | N | N | N | N | N | Y | N | N |
| Users & Permissions (surface) | I | MVP+New | RV+New | N | REQ | N | N | N | N | N | Y | Y | N |
| Integrations (surface: Email, SMS/MMS, File storage, AI provider, Tax provider [future], Stripe) | I | MVP+New | RV+New | N | REQ | N | N | Y | Y | Y | Y | Y | Y |
| Portals (portal settings + Webstore settings + Wrap Lab settings) | I | New | New | N | REQ | N | N | N | N | N | Y | Y | Y |
| Feature Access (per-tenant feature entitlement view + toggles per plan) | I | REB+New | FSV+New | N | REQ | N | N | N | N | N | Y | N | Y |
| Data & Security (audit surface, retention, export/deletion, key rotation, security posture) | I | MVP+New | RV+New | N | REQ | N | N | N | N | N | Y | Y | Y |
| Pricing Defaults — Pricing Foundation | I | MVP | RV | N | REQ | N | N | N | N | N | Y | N | N |
| Pricing Defaults — Pricing Setup | I | MVP | RV | N | REQ | N | N | N | N | N | Y | N | N |
| Pricing Defaults — Shop Rate | I | MVP | RV | N | REQ | N | N | N | N | N | Y | N | N |
| Pricing Defaults — Labor Rates | I | MVP | RV | N | REQ | N | N | N | N | N | Y | N | N |
| Pricing Defaults — Material Pricing (tenant catalog editor) | I | ORIG+REB | RS+FSV | N | REQ | N | N | N | N | N | Y | N | N |
| Pricing Defaults — Pricing Calculators (9 categories) | I | MVP | RV | N | REQ | N | N | N | N | N | Y | N | N |
| Pricing Defaults — Pricing Administration | I | MVP | RV | N | REQ | N | N | N | N | N | Y | N | N |
| Subscriptions & AI Credits — Tenant Subscription (plan, add-ons, billing history, payment method) | I,Pl | REB | FSV | Y | REQ | N | N | Y | N | Y | Y | Y | Y |
| Subscriptions & AI Credits — Tenant AI Credits (balance, top-ups, usage summary) | I,Pl | REB | FSV | Y | REQ-DEP | N | Y | N | N | Y | Y | N | Y |
| Platform Governance (visible only to platform-authorized roles) | Pl | REB | FSV | Y | REQ | N | N | N | N | N | Y | Y | Y |

**Flyout rules:**
- Pricing Defaults contains shop rate, labor rates, materials defaults, markups, minimum charges, category defaults, complexity settings, and formula configuration. Operational Pricing Calculator access may appear as a shortcut inside Quotes/Orders, but permanent configuration lives here.
- Subscriptions & AI Credits manages the tenant's OWN SignGuy AI account (plan, add-ons, credit balance, top-ups, billing history, payment method). It does NOT manage the shop's customer invoices.
- Platform Governance is visible ONLY to platform-authorized roles. Use "Platform Governance" — never "Platform Governments."

## 4.7 Platform and Support

| Module | Sc. | Src. | Ev. | Preflight | CR | Standalone | AI | Msg | OS | Stripe | Audit | Sensitive | Owner |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Onboarding | I | ORIG | RS | N | REQ | N | N | Y | N | N | Y | N | N |
| Help Center / Documentation | I,Pu | FEB+ORIG | RS | N | REQ | N | N | N | N | N | N | N | N |
| Community Hub | I | REB | FSV | N | REQ | N | N | Y | N | N | Y | N | N |
| Bug Reports (via community) | I,Pl | REB | FSV | N | REQ | N | N | Y | N | N | Y | N | N |
| Feature Requests (via community) | I,Pl | REB | FSV | N | REQ | N | N | Y | N | N | Y | N | N |
| Support | I,Pu | New | New | N | REQ | N | N | Y | N | N | Y | Y | N |
| Platform Admin Dashboard | Pl | REB+ORIG | FSV+RS | Y | REQ | N | N | N | N | N | Y | Y | Y |
| Platform Tenant Management | Pl | REB | FSV | Y | REQ | N | N | N | N | N | Y | Y | Y |
| Platform Analytics | Pl | ORIG+New | RS+New | Y | REQ | N | N | N | N | N | Y | Y | N |
| Platform Audit Logs | Pl | MVP+REB | RV+FSV | N | REQ | N | N | N | N | N | Y | Y | N |
| Platform Email & Broadcasts | Pl | ORIG | RS | Y | REQ | N | N | Y | N | N | Y | Y | Y |
| Platform Settings | Pl | New | New | N | REQ | N | N | N | N | N | Y | Y | N |
| Subscription Administration | Pl | REB | FSV | Y | REQ | N | N | Y | N | Y | Y | Y | Y |
| AI Credit Administration | Pl | REB | FSV | Y | REQ | N | Y | N | N | Y | Y | N | Y |

## 4.8 Portals and Public Systems

| Module | Sc. | Src. | Ev. | Preflight | CR | Standalone | AI | Msg | OS | Stripe | Audit | Sensitive | Owner |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Customer Portal | P | ORIG+New | PSI+New | Y | REQ | N | N | Y | Y | Y | Y | Y | Y |
| Employee Portal | P | ORIG+FEB+New | RS+New | Y | REQ | N | N | Y | Y | N | Y | Y | Y |
| Webstore Owner Portal | P | ORIG+REB | RS+SO | Y | ADD | N | N | Y | Y | Y | Y | Y | Y |
| Webstore Manager Portal | P | REB | SO | Y | ADD | N | N | Y | Y | N | Y | N | N |
| Public Storefront | Pu | ORIG+REB | RS+SO | Y | ADD | Y | N | N | Y | Y | Y | N | N |
| Public Forms | Pu | ORIG | RS | Y | REQ | N | N | N | Y | N | Y | Y | N |
| Public Questionnaires | Pu | ORIG+REB | RS+SO | Y | REQ | N | N | N | Y | N | Y | Y | N |
| Public Quote Requests | Pu | ORIG | RS | Y | REQ | N | N | N | Y | N | Y | Y | N |
| Public Customer Intake | Pu | ORIG | RS | Y | REQ | N | N | N | Y | N | Y | Y | N |
| Public Proof Approval | Pu | ORIG | PSI | Y | REQ | N | N | N | N | N | Y | Y | N |
| Public Signature Pages | Pu | ORIG | PSI | Y | REQ | N | N | N | Y | N | Y | Y | N |
| Marketing Website | Pu | ORIG+FEB | RS | N | REQ | N | N | N | N | N | N | N | N |
| Public Pricing and Plan Selection | Pu | ORIG+FEB | RS | N | REQ | N | N | N | N | Y | N | N | Y |

## 4.9 Commercial and Billing Systems

| Module | Sc. | Src. | Ev. | Preflight | CR | Standalone | AI | Msg | OS | Stripe | Audit | Sensitive | Owner |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Subscription Billing | I,Pl | REB | FSV | Y | REQ | N | N | Y | N | Y | Y | Y | Y |
| Add-on Purchases | I,Pl | REB | FSV | Y | REQ | N | N | Y | N | Y | Y | Y | Y |
| AI Credit Purchases | I,Pl | REB | FSV | Y | REQ-DEP | N | Y | Y | N | Y | Y | N | Y |
| Transaction Fees | I,Pl | REB | FSV | Y | ADD | N | N | Y | N | Y | Y | Y | Y |
| Founders Promo | I,Pl | REB | FSV | Y | REQ | N | N | Y | N | Y | Y | Y | Y |

**Modules explicitly REMOVED / DEPRECATED from the permanent product:**
- Any `Job`, `Job Ticket`, `Job Item`, `Production Ticket`, `Job Ticket Summary` module or route.
- ORIG `PortalPreview.js`, `LegacyJobRedirect.js`, `routes/backup.py`, `routes/dev.py`.
- ORIG monolithic `App.js` structure.
- ORIG giant `routes/pricing.py` and `routes/pricing_setup.py` (replaced by MVP pricing service).
- ORIG `services/multi_product_billing.py` whole-file copy (extract micro-formulas only, see Part 11).
- FEB `models/jobs.py` and Job-domain routes.
- REB `PreviewEnvelope` base model and preview-user impersonation defaults.

---

# PART 5 — FINAL ADD-ON AND STANDALONE BOUNDARIES

## 5.1 Owner Directions (LOCKED — carried forward from prior owner statements)

- **SignGuy AI Core** is the primary platform.
- **Webstores** is available as **paid add-on** AND **standalone**.
- **Wrap Lab / Wrap Command Center** is available as **paid add-on**. Standalone is permitted **only if shared-core access can be provided safely without duplicating systems**.
- **Founders** receive the full platform + Webstores + Wrap Lab bundled with a defined AI credit amount and a limited-usage one-week free trial.
- **AI credits** are charged separately or included in defined amounts per plan.
- **No feature tiers** cripple normal shop operations (customer count, order count, or similar business-limiting quotas are prohibited).
- **Advanced AI usage** is controlled through credits, not by removing basic business functionality.

## 5.2 Shared Backend Rule (LOCKED)

**One shared multi-tenant backend + one set of shared domain systems** power every product boundary. Every product mode (Core, Webstores, Wrap Lab, Complete Bundle, standalone Webstores, standalone Wrap Lab) uses the same:
- Auth / Users / Tenants / Permissions.
- Customer / Order / Order Item / Work Order / Invoice / Payment collections.
- Object Storage / Attachments / DocuLink / Document Shares / Templates.
- Email / SendGrid / Email Activity / Notifications.
- Audit / Activity Events.
- Files / Upload Validation / File Links.
- Settings framework.
- Feature Entitlements service (controls module access per tenant).

**Never duplicated** in code or database (LOCKED):
- Customers.
- Orders.
- Documents.
- Payments.
- Email.
- SMS.
- Users.
- Authentication.
- Files.
- Audit Logs.
- Settings.

Standalone products **do not** get their own parallel domain models. They get an isolated UI surface and entitlement-controlled module access.

## 5.3 Product Mode Definitions

| Boundary | Shared core | Independent UI | Auth model | Tenant ownership | Permissions | Entitlements | Shared Customers | Shared Orders | Shared Documents | Shared Email/SMS | Shared Stripe refs | Data portability | Upgrade path | Downgrade behavior | No-duplication requirement | Commercial-release dependency |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **SignGuy AI Core** | Yes | Full app (all six areas) | Standard staff auth | Single tenant | Full permission catalog | Entitles Core features | Yes | Yes | Yes | Yes | Yes | N/A | N/A | N/A | Enforced | Foundation gates all |
| **Webstores add-on** | Yes | Adds Webstore UI to existing tenant | Standard staff auth + Webstore Owner/Manager portal auth | Same tenant | Adds webstore permissions | Turns on `webstores` + `stripe_connect` | Yes | Yes (Webstore Orders are Orders) | Yes | Yes | Yes | N/A | N/A | On downgrade: turn off entitlement; existing storefronts flagged read-only until re-enabled or exported. Data preserved. | Enforced | Requires Feature Entitlements, Stripe Connect foundation |
| **Webstores standalone** | Yes | **Only Webstores UI + minimal Customer/Order surface** for storefront operators. Non-webstore internal areas hidden by entitlement, not deleted. | Standard staff auth (limited role) + Webstore Owner/Manager portal auth | Own tenant | Reduced permission set (webstore + minimal customer + minimal order + payments-view) | Turns on `webstores` + `stripe_connect` ONLY | Yes (own tenant scope) | Yes | Yes | Yes | Yes | Yes — can upgrade in place | Upgrade to Core = flip entitlements on; no data migration | Downgrade = flip entitlements off; hidden UI; data preserved | Enforced | Requires shared backend + entitlement gating |
| **Wrap Lab add-on** | Yes | Adds Wrap Lab UI + Wrap-Project portal | Standard staff auth + Customer portal (per Wrap Project) | Same tenant | Adds wrap permissions | Turns on `wrap_lab` | Yes | Wrap Projects link to Orders | Yes | Yes | Yes | N/A | N/A | On downgrade: entitlement off; existing wrap projects flagged read-only until re-enabled. Data preserved. | Enforced | Requires Approvals, Signatures, Customer Portal, DocuLink |
| **Wrap Lab standalone** | Yes (owner-decision conditional) | Only Wrap Lab UI + minimal Customer/Order surface | Standard staff auth (limited role) + Customer Portal | Own tenant | Reduced permission set (wrap + minimal customer + minimal order + payments-view) | Turns on `wrap_lab` ONLY | Yes | Yes | Yes | Yes | Yes | Yes — can upgrade to Core | Upgrade = flip entitlements on | Downgrade = flip entitlements off | Enforced | Requires standalone conditions verified during module preflight |
| **Complete Bundle (Founders)** | Yes | Full app + Webstores + Wrap Lab | Standard staff auth + portals | Single tenant | Full permission catalog | Turns on all three feature keys | Yes | Yes | Yes | Yes | Yes | N/A | N/A | On plan change: entitlements adjust; data preserved | Enforced | Requires all foundations |
| **AI Tools / Assistant** (metered) | Yes | Creative Studio area | Standard staff auth | Same tenant | Adds AI permissions | Turns on `ai_tools` + per-tool caps | Yes | Yes | Yes | Yes | Yes | N/A | N/A | On credit exhaustion: soft-block AI Tools; core untouched | Enforced | Requires AI credit ledger, provider abstraction |
| **SMS/MMS** (permanent-product scope; commercial-release timing = Decision 27) | Yes | Notification prefs + Portal messaging | Same | Same tenant | Adds sms permissions | Turns on `sms_mms` | Yes | Yes | Yes | Yes | Yes | N/A | N/A | On downgrade: turn off entitlement | Enforced | Requires SMS provider integration |

## 5.4 Entitlement Rules (LOCKED)

- Every module protected by an add-on or subscription tier reads a **feature entitlement** at request time.
- Entitlements never bypass permissions. An entitlement grants a tenant *access to a module*; permissions still control *which user in the tenant may do what*.
- Standalone products never expose modules for which the tenant has no entitlement.
- Founder tenants receive all three feature keys (`core`, `webstores`, `wrap_lab`).
- No entitlement enables a completely-parallel data store.

## 5.5 Standalone Constraints

- Standalone products share the same auth database, but users see a reduced UI. Non-entitled routes return 402/403 with a specific `entitlement_missing` error code.
- Shared users may exist across portals but never receive internal staff permissions from a portal identity.
- Customers upgrade from standalone to full platform by adding entitlements — **no data migration required**.
- Data portability: every standalone tenant may export their Customers, Orders, Invoices, Payments, Files via a scheduled export mechanism (build-out for permanent product roadmap).

## 5.6 Standalone Wrap Lab — RECOMMENDED conditional decision

- **Recommendation:** Enable Wrap Lab standalone **only after** module preflight of the shared portal, DocuLink, Approvals, Signatures confirms zero code duplication. If preflight identifies any duplicated system, revert to add-on-only.
- **Status:** RECOMMENDED — owner ratifies in Prompt 4 after preflight completes.

## 5.7 Do NOT Create

- No duplicated Customer collection per product boundary.
- No duplicated Order collection per product boundary.
- No duplicated Payment collection per product boundary.
- No duplicated Email/SMS pipelines per product boundary.
- No duplicated Users/Auth per product boundary.
- No duplicated Files/Attachments per product boundary.
- No duplicated Audit Logs per product boundary.
- No duplicated Settings schema per product boundary.

---

# PART 6 — FINAL INTEGRATION REGISTER

Every third-party integration in the permanent product is listed below. Every integration MUST route through `integration_playbook_expert_v2` before implementation.

## 6.1 Integration Rules (LOCKED)

- **No inline Base64 file storage.** All files flow through the object storage adapter.
- **Object storage is private by default.** All downloads require auth or a scoped, expiring public link.
- **SendGrid webhook must fail closed in production if the secret is unset.**
- **Stripe webhooks must be signature-verified and replay-safe.**
- **Payment writes require idempotency.**
- **No production integration uses placeholder secrets.**
- **No live integration key is hardcoded.**
- **Provider-specific logic lives behind services or adapters** so a provider swap is a single-file change.
- **Failed integrations must not silently mark workflows complete.** Errors surface through activity events, notifications, and audit.

## 6.2 Integration Register

| Integration | Purpose | Modules | Required/Optional | Current status | Existing donor source | Auth/Secrets | Webhooks | Retry | Idempotency | Audit | Tenant ownership | Data stored locally | Production safety | Preflight | CR blocker | Failure behavior | Monitoring | Owner decisions | Recommendation |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **SendGrid outbound email** | Transactional email | Emails, Quotes, Invoices, Portal, Documents, Wrap Lab | Required | Live (RV) | MVP `services/email.py` | `SENDGRID_API_KEY`, `SENDGRID_FROM_EMAIL` | N | Provider-managed | Per-send Idempotency-Key + email_logs dedup | Yes | Per-tenant filter on logs | `email_logs` collection | Rotate keys before commercial release | N | Y | Log failure as `email.send_failed` activity + retry queue | Delivery metrics per tenant | N | KEEP as-is |
| **SendGrid delivery/event webhook** | Inbound bounces, opens, clicks | Communication history, Portal notifications | Required | Not integrated | REB `POST /communications/webhooks/sendgrid` (FSV) | `SIGNGUYAI_SENDGRID_WEBHOOK_SECRET` (HMAC-SHA256) | Y | Provider-managed | Event ID + replay-safe write | Y | Per-tenant via SendGrid metadata | `email_activity` collection | Force-fail startup if secret unset AND ENV=production | Y | Y | 401 unverified events; alert on repeated failures | Webhook success rate | Y (fail-closed policy) | Adopt REB webhook + activity log |
| **SMS/MMS provider** | Transactional SMS + inbound reply | Portal, Notifications, Order events, Marketing | Permanent-product scope; **commercial-release timing = OWNER DECISION 27** (before-first-sale vs later commercial release) | Not integrated | ORIG `routes/sms.py` + `services/sms_service.py` (RS) | Provider API key + webhook secret | Y | Provider-managed | Per-send Idempotency-Key + sms_logs dedup | Y | Per-tenant | `sms_logs` collection | Rotate before enabling; carrier registration required for US 10DLC | Y | Timing per Decision 27 | Log failure as `sms.send_failed`; retry queue | Deliverability + carrier lookups | Y (provider choice — see Part 13 Decision 19; release timing — see Part 13 Decision 27) | Twilio recommended (matches donor); confirm in Prompt 4 alongside Decision 27 timing |
| **Stripe (Core payments)** | Manual payments (recorded), tenant subscription billing | Payments, Subscriptions, AI credit top-ups | Required | Not integrated | FEB `services/payment_service.py` + FEB/ORIG `routes/stripe_connect.py` (FSV+RS) | `STRIPE_API_KEY` (test key already provisioned in pod env), `STRIPE_WEBHOOK_SECRET` | Y | Provider-managed | Idempotency-Key on every write + DuplicateKeyError race handling on webhook confirm | Y | Per-tenant Stripe customer ID | `payments` collection, `subscriptions` collection | Signature verification + replay protection MANDATORY | Y | Y | Never mark payment success without webhook confirmation; refund path tested | Payment success rate + reconciliation deltas | Y (transaction fee bps — see Part 7B) | Adopt FEB pattern verbatim |
| **Stripe Connect** | Webstore payouts to shop-owned Stripe accounts | Webstores, Payouts | Required for Webstores | Not integrated | FEB + ORIG (FSV+RS) | Same as Stripe Core + Connect onboarding | Y | Provider-managed | Same + payout idempotency | Y | Per-tenant Stripe Connect account | `payouts` collection | Financial-safety review before any port | Y | Y (for Webstores) | Never trust client-computed payout amounts | Payout success + reconciliation deltas | Y (transaction fee bps + payout schedule) | Formal security review + adopt FEB confirm-on-webhook pattern |
| **Emergent Object Storage** | Private file storage for attachments, DocuLink, AI-generated files, portal-visible assets | Files, DocuLink, Portal, Wrap Lab, AI, Templates | Required | Live (RV) | MVP `services/storage.py` + ORIG `services/object_storage.py` (FSV, 35 lines, clean) | `EMERGENT_LLM_KEY` (used for storage init in MVP) | N | N/A | Per-file UUID | Y | Per-tenant path prefix | File metadata + polymorphic attachment links | Tenant path check on every read/write | N | Y | Fail closed on missing key | Storage error rate | N | KEEP + adopt REB `upload_validation.py` |
| **AI provider (LLM)** | AI generation for all AI Tools + Assistant | AI Tools, Assistant, Prompt Library, AI generated files/docs | Required | Available (Emergent LLM key) | Emergent LLM key + emergentintegrations | `EMERGENT_LLM_KEY` | N | Retry per provider adapter | Per-generation `ai_credit_ledger` idempotency | Y | Per-tenant credit metering + result storage | `ai_responses` collection + credit ledger | Provider abstraction MANDATORY; cost cap per tenant | Y | Y | Refund credits on provider failure; queue retry; user notified | Provider latency + cost per tool | Y (model choice + per-tool cost cap) | Route through integration playbook expert; adopt Emergent-managed key |
| **Tax provider** (Avalara / TaxJar or shop-configured) | Sales tax computation on Invoices | Invoices, Reports | Optional at launch | Not integrated | New (or `New` + spec) | Provider API key (if used) | N | Provider-managed | Per-invoice tax snapshot idempotency | Y | Per-tenant | `invoice_line_items.tax_cents` snapshot | Store invoice tax snapshot; never recalc historical | Y | N at launch (shop-configured rates OK) | Log failure; allow manual override | Tax API errors | Y (strategy — see Part 7C) | Start with shop-configured rates + tax integration boundary in service |
| **Meta/Facebook lead integration** | Lead capture from Facebook lead ads | Leads, Public Forms | Optional | Not integrated | ORIG (RS) | Meta API keys | Y | Provider-managed | Per-lead source_id dedup | Y | Per-tenant | `leads` collection | Same as public forms | Y | N | Log failure; do not lose lead data | Ingestion success rate | Y (Prompt 4 decision) | Defer to backlog; not required for commercial launch |
| **Google Calendar / other calendar integrations** | Sync appointments + install schedule | Calendar, Scheduling | Optional | Not integrated | New | OAuth tokens | Y | Provider-managed | Per-event provider ID | Y | Per-user (external calendar) | `calendar_syncs` collection | OAuth scopes minimum required | Y | N | Log sync failures | Sync success rate | Y | Defer to backlog |
| **Accounting integrations (QuickBooks, Xero)** | Bookkeeping sync | Finance, Reports | Optional | Not integrated | New | OAuth tokens | Y | Provider-managed | Per-invoice + per-payment external ID | Y | Per-tenant | `accounting_syncs` collection | OAuth scopes minimum required | Y | N | Log sync failures | Sync success rate | Y | Defer to backlog |
| **Webhook Infrastructure (inbound)** | Shared webhook receiver framework for SendGrid + Stripe + future providers | Notifications, Payments | Required | Partial (REB SendGrid shape FSV) | REB `routes/communications.py::ingest_sendgrid_webhook` + FEB Stripe patterns | Per-integration secret | N/A | Retry with dedup by event ID | Idempotency-Key + event ID unique index | Y | Per-tenant metadata | `webhook_events` collection | Signature verify + replay-safe + fail-closed | Y | Y | Reject unverified; alert on error rate | Verification success rate | N | Build shared webhook framework before Stripe port |
| **Background Jobs / Scheduler** | Scheduled digest emails, dunning, report generation, reconciliation sweeps | Emails, Notifications, Reports, Payments | Required (post initial launch) | Not integrated | ORIG `services/digest_scheduler.py` + `services/workflow_engine.py` (RS) | N/A (internal) | N/A | Retry with dead-letter | Job ID dedup | Y | Per-tenant scope | `job_runs` collection | Fail-safe scheduler; alerts on missed jobs | Y | Y (once dependent modules exist) | Alert on run failure | Job success rate | N | Build against MVP shared services after core modules stable |
| **Public forms / questionnaires** | Public data capture | Forms, Questionnaires, Leads | Required | Not integrated | ORIG + REB (RS+SO) | N/A (public) | N/A | N/A | Per-submission dedup by IP + timestamp | Y | Per-tenant slug ownership | `form_submissions` collection | Rate-limit + spam protection + captcha | Y | Y | Reject spam; allow retry | Submission volume + spam rate | N | Rate-limit + captcha before enabling public forms |
| **Portal authentication** | Magic-link + password auth for external portal identities | Customer Portal, Employee Portal, Webstore Owner/Manager Portals, Public Approval/Signature links | Required | Not integrated | ORIG `routes/portal.py` + `routes/magic_links.py` (PSI+RS) | Per-tenant JWT signing scope | N/A | N/A | Token single-use where applicable | Y | Per-tenant | `portal_identities` collection + `magic_link_tokens` collection | Portal tokens are NEVER interchangeable with staff JWTs (LOCKED) | Y | Y | Alert on brute-force / rate-limit trigger | Portal auth success + failed attempts | Y (auth mode — see Part 8) | Separate portal identity + magic link + password combo |

## 6.3 Integration Preflight Checklist (LOCKED for every integration)

Before any integration port lands, the following must be verified:
- Playbook obtained from `integration_playbook_expert_v2`.
- Latest SDK version confirmed.
- API keys / secrets provisioned via `.env` (never hardcoded).
- Webhook secret set and fail-closed rule enforced (where applicable).
- Idempotency keys defined on all mutating writes.
- Replay-safety confirmed for webhook receivers.
- Audit events defined on all state transitions.
- Tenant scoping verified (no cross-tenant leak).
- Failure behavior defined (retry queue, activity event, notification).
- Monitoring wired.

---

# PART 7 — FINAL MONEY, BILLING, AND COMMERCIAL DECISIONS

## 7A. Money Representation

### 7A.1 Verified Current State (LOCKED — FSV)

- **Commerce values (`Quote.total_cents`, `Order Item.unit_price_cents` and `line_total_cents`, `WorkOrderItemSnapshot.unit_price_cents`, `Invoice.total_cents`, `InvoiceLineItem.unit_price_cents`, `Payment.amount_cents`)** use **integer cents** in Pydantic models and MongoDB. Frontend receives cents and displays via `centsToDollarsString`; `MoneyInput.jsx` calls `parseDollarsToCents` on input.
- **Pricing configuration + calculator input/output** (`services/starter_defaults.py::SHOP_DEFAULTS`, `MATERIALS`, `CATEGORY_DEFAULTS`, `services/pricing.py::calculate_pricing` args and return payload) use **float dollars with `Decimal` internal math**. Rounded to 2 dp at the boundary (`ROUND_HALF_UP`).
- **No unsuffixed money field** exists in commerce models. Configuration fields are dollar-based and unsuffixed by convention.
- **No tax, discount, or fee fields** currently modeled on any commerce entity.

### 7A.2 Recommended Permanent Policy (RECOMMENDED — OWNER RATIFY)

1. **Stored transactional money uses integer cents.**
2. **Transactional fields carry the `_cents` suffix** on every commerce model (Quote, QuoteLineItem, Order, OrderItem, WorkOrder, WorkOrderItemSnapshot, Invoice, InvoiceLineItem, Payment, and future additions such as `tax_cents`, `discount_cents`, `fee_cents`, `amount_paid_cents`, `balance_due_cents`, Stripe amounts).
3. **Pricing configuration may use dollar-based decimal/float values.** Fields in `pricing_settings` remain dollar-based. The calculator continues to compute in `Decimal` and cast to float at the response boundary.
4. **Single pricing→commerce conversion boundary** at the point where calculator output is written onto a Quote Line Item, Order Item, Invoice Line Item, Payment, tax, fee, or discount. Conversion helper: `round(dollars * 100)` returns an integer alongside the float payload for callers that want to snapshot.
5. **Stripe amounts remain integer cents on the wire and integer cents on our Payment row.** No conversion.
6. **API field names reflect their unit.** Money JSON responses use the same suffix as the model. No display-formatted currency strings on API responses.
7. **No unsuffixed ambiguous money fields on any commerce model or API response.**
8. **Reports sum integer cents.** Display formatting happens in the report renderer.
9. **Frontend continues using `centsToDollarsString` / `parseDollarsToCents` / `MoneyInput.jsx`.** No refactor needed.
10. **No data migration required.** Every existing commerce field is already integer cents. New fields are additive.

**Owner decision required in Prompt 4:** ratify or overrule the "commerce in integer cents / configuration in float dollars" split, the `_cents` naming rule, the conversion boundary location, and the no-unsuffixed-money rule.

## 7B. Commercial Product Model

### 7B.1 Product Model Direction (OWNER APPROVED IN THIS REGISTER)

Carried forward from prior explicit owner statements:

- **Founders program:** First 50 founder customers; complete platform + Webstores + Wrap Lab + a defined AI credit amount; one-week free trial with limited AI usage; **no artificial customer or order limits**; founder pricing must be simple and attractive; **founder access must not become a maze of feature gates**.
- **After founders:** Main SignGuy AI platform subscription; Webstores as add-on **and** standalone; Wrap Lab as add-on with standalone capability evaluated; AI credits separately metered; add-on bundle discount **may** be offered; **no feature tiers cripple normal shop operations**; advanced AI is controlled via credits, not by removing basic functionality.

### 7B.2 REB `billing_rules.py` Values — CANDIDATE ONLY

REB `services/billing_rules.py` is the most complete existing commercial-pricing implementation candidate. **None of its prices, fees, plans, credits, promotions, or transaction rates are final until Prompt 4 owner approval.** Values below are the candidate as inspected (FSV) — every row requires explicit ratification.

### 7B.3 Commercial Decision Table

| Item | Candidate value (from REB) | Status | Notes |
|---|---|---|---|
| **Founder plan** | Complete Bundle at founders price | OWNER APPROVED IN THIS REGISTER (direction) | Exact price REQUIRES OWNER DECISION (Part 13) |
| **Founder platform coverage** | Core + Webstores + Wrap Lab + AI credits | OWNER APPROVED | LOCKED per owner statement |
| **Founder customer limit** | First 50 | OWNER APPROVED | LOCKED per owner statement |
| **Founder free-trial duration** | 1 week | OWNER APPROVED | LOCKED per owner statement |
| **Founder free-trial AI usage** | Limited | OWNER APPROVED (direction) | Specific limit REQUIRES OWNER DECISION |
| **Founder artificial customer/order limits** | None | OWNER APPROVED | LOCKED — no limits |
| **Core platform (GA) subscription** | `prod_core_os` `$149.00/mo` GA / `$99.00/mo` founders | REQUIRES OWNER DECISION | Candidate only |
| **Core platform included credits** | 300 GA / 300 founders | REQUIRES OWNER DECISION | Candidate only |
| **Webstores add-on price** | Bundled with Core in Complete Bundle OR sold separately at Standalone price | REQUIRES OWNER DECISION | Add-on standalone pricing distinct from bundle |
| **Webstores standalone price** | `prod_webstore_standalone` `$89.00/mo` GA / `$59.00/mo` founders, 300 GA / 200 founders credits | REQUIRES OWNER DECISION | Candidate only |
| **Wrap Lab add-on price** | Bundled with Core OR sold separately at Standalone price | REQUIRES OWNER DECISION | See standalone conditional (Part 5.6) |
| **Wrap Lab standalone price** | `prod_wrap_standalone` `$119.00/mo` GA / `$79.00/mo` founders, 500 GA / 350 founders credits | REQUIRES OWNER DECISION | Candidate only + conditional on preflight |
| **Complete Bundle** | `prod_complete_bundle` `$279.00/mo` GA / `$189.00/mo` founders, 1000 credits both phases | REQUIRES OWNER DECISION | Candidate only |
| **AI credits included in each plan** | Per plan as above | REQUIRES OWNER DECISION | Direction locked; amounts pending |
| **AI credit top-up: 100 credits** | `prod_topup_100` `$19.00` | REQUIRES OWNER DECISION | Candidate only |
| **AI credit top-up: 300 credits** | `prod_topup_300` `$45.00` | REQUIRES OWNER DECISION | Candidate only |
| **AI credit top-up: 800 credits** | `prod_topup_800` `$99.00` | REQUIRES OWNER DECISION | Candidate only |
| **Founders promo code** | `FOUNDERS3MO`, max 25 redemptions, 3-month duration, 3-month fee holiday, discounts $40 Core / $20 Webstores / $30 Wrap / $70 Bundle | REQUIRES OWNER DECISION | Redemption cap conflicts with "first 50 founders" direction — reconcile in Prompt 4 |
| **Transaction fee (promo-active phase)** | 0 bp standard / 0 bp webstore | REQUIRES OWNER DECISION | Candidate only |
| **Transaction fee (founders phase)** | 50 bp standard / 150 bp webstore | REQUIRES OWNER DECISION | Candidate only |
| **Transaction fee (GA)** | 100 bp standard / 200 bp webstore | REQUIRES OWNER DECISION | Candidate only |
| **Transaction fee cutover rule** | `shop_onboarded_index > 50` OR `phase == general_availability` → GA rates | REQUIRES OWNER DECISION | Candidate only |
| **Setup / onboarding fees** | None in candidate | REQUIRES OWNER DECISION | Prompt 4 |
| **DIY onboarding** | Available (default) | OWNER APPROVED (direction) | Founders receive DIY onboarding |
| **Free-trial for non-founder tenants** | Not defined | REQUIRES OWNER DECISION | Prompt 4 |
| **Price-lock rules for founders** | Not defined | REQUIRES OWNER DECISION | Prompt 4 (e.g., founders keep founder price forever vs 12 months) |
| **Promo behavior on upgrade** | Not defined | REQUIRES OWNER DECISION | Prompt 4 (does promo carry across plan change?) |
| **Upgrade behavior** | Flip entitlements on; prorated Stripe billing | RECOMMENDED | Standard Stripe pattern |
| **Cancellation behavior** | Entitlements off at period end; data preserved | RECOMMENDED | Standard subscription pattern |
| **Entitlement behavior on payment failure** | Grace period 7 days → soft block → full block | REQUIRES OWNER DECISION | Prompt 4 |

**Do not let old code silently decide current prices.** Every value in REB `billing_rules.py` remains CANDIDATE until Prompt 4 owner approval.

## 7C. Sales Tax Strategy

### 7C.1 Options Compared

| Option | Pros | Cons | Preflight |
|---|---|---|---|
| Shop-configured tax rates | Simple; per-tenant control; no integration cost | Manual; error-prone for multi-jurisdiction | None |
| Shop-configured multiple tax jurisdictions | Slightly better than single rate | Still manual | None |
| Tax exemption records | Necessary regardless of rate source | Requires exemption certificate storage + audit | None |
| Third-party integration (Avalara / TaxJar) | Accurate multi-jurisdiction; nexus tracking | Integration cost per transaction; monthly subscription; adds a vendor dependency | Y |
| Manual tax entry | Escape hatch for edge cases | Not scalable | None |
| Future automated tax expansion | Best long-term | Requires historical data + audit | Y |

### 7C.2 Recommended Initial Strategy (RECOMMENDED)

- **Launch with shop-configured tax rates** with support for multiple jurisdictions.
- **Support tax exemption records** with certificate storage and audit trail.
- **Store invoice tax snapshot at commit time.** Never silently recalculate historical invoices.
- **Provide manual tax override** per invoice with actor + reason audit fields.
- **Establish a tax provider integration boundary** (an interface in `services/tax.py`) so Avalara/TaxJar can be added later without refactoring invoice modules.
- **Publish clear responsibility disclaimer** in Terms of Service: SignGuy AI does not warrant tax accuracy; shop is responsible for correct rates and exemption records.
- **Add tax auditability** — every rate change, exemption change, and manual override produces an audit event.

**Owner decision required in Prompt 4:** ratify the shop-configured start + provider-integration boundary approach, or select a different initial strategy.

## 7D. AI Provider and Credit Model

### 7D.1 Provider Abstraction (LOCKED)

- **All AI calls route through a `services/ai_provider.py` adapter** that hides provider-specific SDKs.
- **Provider strategy:** Emergent LLM key is the confirmed source of LLM access. Emergent LLM key supports Claude Sonnet text, Gemini text + Nano Banana image, OpenAI text + GPT Image 1, Sora 2 video, OpenAI Whisper.
- **Model selection rules** — every tool defines an intensity level (low / medium / high / vision / image) and the adapter selects a model per intensity.
- **Tool intensity levels** — used to derive per-tool credit cost.
- **Per-tool credit cost** — declared in a `AI_TOOL_CREDIT_COSTS` catalog (RECOMMENDED; not final values without measured cost audit).
- **Failure/refund behavior** — on provider failure, credits are refunded to the tenant ledger; user is notified via activity event; retry attempted per adapter policy.
- **Tenant credit ledger** — every generation debits credits; every refund/adjustment writes an event; monthly bank replenishes on subscription cycle.
- **Included monthly credits** — per plan (see Part 7B candidate values).
- **Purchased credits** — top-up packs.
- **Expiration policy** — RECOMMENDED: purchased top-up credits do not expire; monthly included credits reset on cycle (RECOMMENDED — owner ratify).
- **Admin adjustments** — Platform Admin can credit or debit a tenant with a required reason + audit event.
- **Usage history** — every AI generation persisted in `ai_responses` with metadata + credit cost.
- **Cost caps** — per-tenant monthly cap (soft warning + hard cap). RECOMMENDED default: soft warning at 200% of plan credits, hard cap at 400% (owner ratifies specific values).
- **Abuse prevention** — rate limiting per tenant + per user + per tool; anomaly detection for sudden usage spikes.
- **Provider outage behavior** — mark tool as `provider_down`; do not debit credits; queue for retry; notify tenant if outage exceeds 15 min.
- **Output storage** — every AI generation stored in `ai_responses` + linked to DocuLink for AI-generated files/documents.
- **AI-generated document review** — files carry `source_type=ai_generated` + `requires_review=True`; not portal-visible until reviewed by a staff user with `document:write` permission.
- **Customer-facing AI restrictions** — no AI system autonomously emails/SMS/records payments/alters invoices/changes pricing (LOCKED).

### 7D.2 Per-Tool Cost Locking

**Prompt 4 must not lock exact per-tool credit costs without evidence of real provider cost.** The master build plan may require a later measured cost audit before final AI-credit pricing is locked. Until then, `AI_TOOL_CREDIT_COSTS` holds provisional values with an explicit `provisional=True` flag.

**Owner decision required in Prompt 4:** ratify the provider abstraction direction; ratify or overrule the RECOMMENDED expiration and cap defaults; approve the measured-cost audit requirement.

---

# PART 8 — PORTAL AUTHENTICATION DECISION

## 8.1 Recommended Direction (RECOMMENDED)

Carried forward from prior standing decisions + evidence review:

1. **Internal users use normal staff authentication** (bcrypt + JWT, single-use email reset token, `AUTH_DEV_BYPASS` only on preview).
2. **Customers and external portal users use a separate portal identity/security scope.** Portal identities live in a `portal_identities` collection distinct from `users`, with their own password hashes (where applicable) and roles that are scoped to `portal:*` permissions only.
3. **Portal users NEVER receive internal staff permissions** (LOCKED). Portal JWTs are signed with a different subject-scope claim; the staff `require_permission()` dep rejects them.
4. **Magic links** may be used for secure low-friction access. Magic-link tokens are single-use, expiring (recommended 15 min for approval/signature, 60 min for login), and revocable.
5. **Password login** available for recurring portal users (Webstore Owner, Webstore Manager, Employee Portal). Password reset uses the same single-use token pattern as staff.
6. **Sensitive actions may require reauthentication or one-time tokens** — payment method changes, subscription cancellations, invoice PDFs older than 30 days.
7. **Public approval/signature links** are scoped to ONE action + expire (recommended 7 days) + are single-use for the terminal action.
8. **Portal tokens are NOT interchangeable with admin JWTs** (LOCKED).

## 8.2 Portal Identity Model

| Concept | Rule |
|---|---|
| Identity model | Separate `portal_identities` collection distinct from `users`. Fields: `id`, `tenant_id`, `portal_type` (customer/employee/webstore_owner/webstore_manager), `email` (nullable for anonymous portal links), `password_hash` (nullable — magic-link-only identities), `linked_customer_id`/`linked_employee_id`/`linked_webstore_owner_id`, `is_active`, `created_at`. |
| Token model | Separate JWT signing scope: `sub_scope="portal"`. Staff `require_permission` rejects tokens with `sub_scope="portal"`. |
| Expiration | Portal login tokens: 24 hours. Magic-link tokens for login: 60 min. Magic-link tokens for approval/signature: 15 min (proof/signature actions), 7 days for public-link view + terminal action. |
| Revocation | Password reset invalidates active JWTs (via `password_version` claim). Magic links are single-use; consumption stored in `magic_link_tokens.used_at`. Manual admin revocation via `portal_identities.is_active=False`. |
| Password reset | Same single-use pattern as staff. 60-min token. |
| Invitation flow | Owner or authorized staff sends portal invite email with magic-link setup token. Portal identity created on setup completion. |
| Tenant ownership | Every portal identity carries `tenant_id`. Cross-tenant portal-identity leakage is a Priority-1 test case. |
| Portal roles | `customer` (portal only), `webstore_owner` (portal only), `webstore_manager` (portal only + limited to Webstores of the Owner they're linked to), `employee` (portal only + linked to Employee record). |
| Session behavior | Portal sessions are stateless JWT. Optional refresh-token pattern for long-lived Webstore Owner sessions (Prompt 4 refinement). |
| Audit events | `portal.login_success`, `portal.login_failed`, `portal.magic_link_sent`, `portal.magic_link_consumed`, `portal.password_reset_sent`, `portal.password_reset_completed`, `portal.session_revoked`. |
| Visibility rules | Portal identities cannot enumerate other portal identities. Customer portal identities cannot see other customers' orders. |
| Brute-force protection | Rate-limit failed login attempts per email + per IP. Progressive lockout: 5 attempts → 5 min, 10 attempts → 60 min, 20 attempts → 24 hours + notification to tenant owner. |
| Rate limiting | Global rate limit per IP on `/portal/login`, `/portal/magic-link/request`, `/portal/password-reset/request`. |
| Link sharing risk | Magic-link tokens are single-use → sharing consumes the token. Approval/signature links are scoped to ONE action so sharing does not grant additional access. |
| Multi-portal identity reuse | An external email may hold multiple portal identities across different tenants (e.g., same customer at two shops). Each identity is scoped to its own tenant. |
| Account merging | Not supported in launch. Deferred to backlog. |

## 8.3 Public Approval/Signature Links (LOCKED)

- Public links use signed, expiring, single-action tokens (`public_action_tokens` collection).
- Each token is bound to ONE specific action (approve proof #X, sign contract #Y, view invoice #Z).
- Tokens are not JWTs; they are opaque signed strings validated server-side.
- Consumption stored + IP + user agent logged.
- Approval/signature tokens are always single-use for terminal actions; view-only tokens may be reused within their 7-day expiration.

## 8.4 Status

- **Direction:** RECOMMENDED (multi-mode: password + magic link + public single-action tokens).
- **Owner decision required in Prompt 4:** ratify the multi-mode direction OR select a single mode (magic-link-only). Approve or refine the expiration + lockout defaults.

---

# PART 9 — PERMISSION AND ROLE DECISION REGISTER

## 9.1 Approach

- **Do not automatically copy all 57 REB permissions.**
- The permanent catalog will merge MVP's minimalist enum with REB's richer surface, keeping only permissions that map to modules in Part 4.
- Portal permissions remain in a **separate scope** (`portal:*`) and are never granted to staff roles.
- Every module in Part 4 that shows `Y` in the Audit column requires at least one permission for its writes and one for reads.

## 9.2 Permanent Role List (RECOMMENDED)

| Role | Purpose | Scope | Default permissions | Restricted areas | Portal? | User mgmt? | View financials? | Record payments? | Manage pricing? | View payroll? | Manage Webstores? | Manage Wrap Lab? | Use AI? | Platform admin? |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Platform Creator** | The account that created the platform tenant (SignGuy Labs). One identity per platform. | Platform | All (including platform admin bypass) | None | N | Y | Y | N (never records for tenants) | N | N | N | N | N | Y (superuser) |
| **Platform Admin** | Operate the SignGuy AI platform | Platform | Platform admin bypass + tenant read/write on platform mgmt | Cannot record payments on tenants | N | Y (across tenants) | Y (aggregated) | N | N | N | N | N | N | Y |
| **Tenant Owner** | The signup owner of a tenant | Tenant | All tenant permissions | None | N | Y | Y | Y | Y | Y | Y | Y | Y | N |
| **Tenant Admin** | Deputy owner | Tenant | All tenant permissions except tenant delete | None | N | Y | Y | Y | Y | Y | Y | Y | Y | N |
| **Manager** | Operational manager | Tenant | Most tenant permissions; no user delete; no billing changes | Cannot delete users; cannot manage subscription | N | Y (invite only) | Y | Y | Y | Optional | Y | Y | Y | N |
| **Staff** | General staff | Tenant | Read/write on Customers/Quotes/Orders/Work Orders/Documents; read on Invoices/Payments | Cannot manage users, pricing, payroll, subscriptions | N | N | N | N | N | N | N | N | Y (metered) | N |
| **Designer** | Design + Proof focus | Tenant | Staff + write on Proofs + AI tool access | Cannot record payments | N | N | N | N | N | N | N | N | Y | N |
| **Production Staff** | Shop-floor | Tenant | Read on Orders/Work Orders/Documents; write on Work Order status; write on Time Clock | Cannot see financials | N | N | N | N | N | N | N | N | N | N |
| **Sales Staff** | Sales-focused | Tenant | Staff + write on Quotes/Convert; read on Invoices | Cannot manage pricing config | N | N | Read | N | N | N | N | N | Y | N |
| **Installer** | Field installer | Tenant | Read on Orders (assigned); write on Install schedule + Time Clock + Install/Final packet signatures | Cannot see financials | N | N | N | N | N | N | N | N | N | N |
| **Employee** | Any employee identity linked to portal | Tenant | Time Clock write, own Timesheet read | Portal-only | Y (Employee Portal) | N | N | N | N | Own only | N | N | N | N |
| **Customer** | External buyer identity | Tenant | Portal read on their own orders, quotes, invoices, proofs; portal write on approvals + signatures + payments (via Stripe) | Portal-only | Y (Customer Portal) | N | Own only | Own only (via Stripe) | N | N | N | N | N | N |
| **Webstore Owner** | Owner of a Webstore | Tenant | Webstore products/orders/managers/payouts write | Portal-only | Y (Webstore Owner Portal) | Y (Managers only) | Own Webstore | Own Webstore | N | N | Y (own) | N | N | N |
| **Webstore Manager** | Delegated Webstore ops | Tenant | Webstore orders/products write as granted by Owner | Portal-only | Y (Webstore Manager Portal) | N | Read | N | N | N | Y (limited) | N | N | N |
| **Read-only / Accountant** | External accountant | Tenant | Read-only on financial modules | Cannot mutate anything | N | N | Y | N | N | Read | N | N | N | N |

## 9.3 Permanent Permission Catalog (RECOMMENDED)

Grouped by module. Every module in Part 4 has at least one permission below. Format: `<module>:<action>` where action is one of `read`, `write`, `delete`, `admin`, plus module-specific verbs.

### 9.3.1 Foundation and Shared
- `user:read`, `user:write`, `user:delete`
- `role:read`, `role:write`
- `settings:read`, `settings:write`
- `audit:read`
- `notification:read`, `notification:write`
- `email:read`, `email:send`
- `sms:read`, `sms:send`
- `file:read`, `file:write`, `file:delete`
- `attachment:write`, `attachment:delete`
- `template:read`, `template:write`
- `entitlement:read`, `entitlement:write`

### 9.3.2 Shop Operations
- `customer:read`, `customer:write`, `customer:delete`
- `lead:read`, `lead:write`
- `quote:read`, `quote:write`, `quote:convert`, `quote:approve`, `quote:decline`
- `order:read`, `order:write`, `order:cancel`
- `order_item:write`
- `work_order:read`, `work_order:write`, `work_order:status`
- `invoice:read`, `invoice:write`, `invoice:send`, `invoice:void`
- `payment:read`, `payment:write` (record manual), `payment:void`, `payment:refund`
- `document:read`, `document:write`, `document:delete`, `document:share`
- `proof:read`, `proof:write`, `proof:send`
- `approval:read`, `approval:write`
- `signature:read`, `signature:write`, `signature:request`
- `inventory:read`, `inventory:write`
- `vendor:read`, `vendor:write`
- `purchasing:read`, `purchasing:write`
- `webstore:read`, `webstore:write`, `webstore:manage`, `webstore:launch`
- `wrap_lab:read`, `wrap_lab:write`, `wrap_lab:advance_stage`, `wrap_lab:admin`

### 9.3.3 Business & Finance (permissions surfaced under this product area)
- `finance:read`, `finance:write`
- `sales:read`
- `expense:read`, `expense:write`
- `tax:read`, `tax:write`
- `report:read`, `report:write`
- `analytics:read`

Note: `payroll:*`, `time_clock:*`, `timesheet:*`, `schedule:*` are enforced but their management surfaces live under **Team & Workflow** (section 9.3.4). `pricing:*` and `subscription:*` and `ai_credit:*` are enforced but their management surfaces live under **Control Center** (section 9.3.6).

### 9.3.4 Team & Workflow (permissions surfaced under this product area)
- `team:read`
- `employee:read`, `employee:write`, `employee:admin`
- `task:read`, `task:write`
- `kanban:read`, `kanban:write`
- `calendar:read`, `calendar:write`
- `appointment:read`, `appointment:write`
- `internal_message:read`, `internal_message:write`
- `announcement:read`, `announcement:write`
- `payroll:read`, `payroll:write`, `payroll:admin`
- `time_clock:read`, `time_clock:write`
- `timesheet:read`, `timesheet:approve`
- `schedule:read`, `schedule:write`

### 9.3.5 Creative Studio and AI
- `ai_tool:use`
- `ai_assistant:use`
- `ai_prompt:read`, `ai_prompt:write`
- `ai_history:read`
- `ai_context:admin`

### 9.3.6 Control Center / Platform / Help & Community
- `pricing:read`, `pricing:write`, `pricing:calculate`
- `subscription:read`, `subscription:manage`
- `ai_credit:read`, `ai_credit:admin`
- `integration:read`, `integration:write`
- `branding:read`, `branding:write`
- `platform:admin` (superuser bypass)
- `platform:tenant_read`, `platform:tenant_write`, `platform:tenant_status`
- `platform:audit_read`
- `platform:broadcast_write`
- `platform:subscription_admin`
- `platform:ai_credit_admin`
- `community:read`, `community:post`, `community:moderate`
- `support:read`, `support:write`

### 9.3.7 Portal permissions (SEPARATE scope — never granted to staff roles)
- `portal:customer_view`, `portal:customer_approve`, `portal:customer_sign`, `portal:customer_pay`, `portal:customer_message`
- `portal:employee_view`, `portal:employee_time_clock`, `portal:employee_timesheet_view`, `portal:employee_payslip_view` (owner-decision gated per Part 13)
- `portal:webstore_owner_admin`, `portal:webstore_manager_ops`

## 9.4 Which Existing MVP Permissions Remain / Rename / Retire

| MVP `Perm` value | Action |
|---|---|
| `customer:read`, `customer:write` | KEEP |
| `quote:read`, `quote:write`, `quote:convert` | KEEP + add `quote:approve`, `quote:decline` |
| `order:read`, `order:write` | KEEP + add `order:cancel` + `order_item:write` |
| `work_order:read`, `work_order:write` | KEEP + add `work_order:status` |
| `invoice:read`, `invoice:write` | KEEP + add `invoice:send`, `invoice:void` |
| `payment:write` | KEEP + add `payment:read`, `payment:void`, `payment:refund` |
| `document:read`, `document:write` | KEEP + add `document:delete`, `document:share` |
| `email:read`, `email:send` | KEEP |
| `audit:read` | KEEP |
| `user:read`, `user:write` | KEEP + add `user:delete` |
| `dashboard:read` | RETIRE (redundant — dashboards inherit read from modules) |
| `pricing:read`, `pricing:write`, `pricing:calculate` | KEEP |

## 9.5 Owner Approval Required Before Final Permission Catalog Locks

- Ratify the role list (Part 9.2).
- Ratify the permission catalog (Part 9.3).
- Ratify the retirement of `dashboard:read`.
- Ratify portal-permission separation (LOCKED direction; owner ratifies).

---

# PART 10 — PERMANENT CODE-ORGANIZATION DECISIONS

## 10.1 Repository-Class Pattern (RECOMMENDED)

Adopt REB's repository-class pattern for **new or substantially rebuilt modules only**. Do **not** refactor working MVP code merely for consistency.

**Rules (LOCKED once ratified in Prompt 4):**
- New module folder standard: `models/` + `repositories/` + `routers/` + `services/`.
- One **repository class per collection**. All tenant filtering lives in the repository. `ensure_indexes()` lives on the repository.
- **Routers stay thin.** They inject permissions, call repositories or services, record activity, and return.
- **Services** own cross-repository orchestration, algorithms (pricing, reconciliation), and workflow engines.
- **Domain services** own cross-module orchestration (e.g., quote-to-order conversion).
- **Business logic never lives in UI components.**
- **Permissions enforced through backend dependencies** — never through frontend gates alone.
- **Audit logging mandatory on writes.**
- **No cross-module imports except through services or a stable `core_runtime`-equivalent.**
- **Every collection registered** in `core/db.py::ensure_indexes()`.

## 10.2 Final Decisions per Concern

| Concern | Decision |
|---|---|
| **repositories folder** | Introduced at `backend/app/repositories/<module>.py` — new modules only |
| **router responsibilities** | Thin: permission dep → repository/service → activity event → typed response |
| **service responsibilities** | Non-CRUD logic, cross-repository orchestration, algorithms, workflow engines |
| **model organization** | One Pydantic file per module: `<X>Payload`, `<X>Document`, `<X>Patch`, `<X>Response`, `<X>ListResponse` |
| **validation** | Pydantic validators at the model layer; boundary validation at the router layer |
| **response models** | Every endpoint has a typed response model; no raw dicts in OpenAPI schema |
| **shared modules** | `core/` (config, db, security, permissions, time_utils), `deps.py`, `services/audit.py`, `services/sequence.py`, `services/storage.py`, `services/email.py` |
| **module-to-module imports** | Prohibited — go through services |
| **database indexes** | Each repository defines its own indexes; `ensure_indexes()` invoked at startup |
| **audit events** | Every write path records an event with actor, entity, event_type, severity, changes, metadata |
| **frontend feature folders** | `src/components/<module>/` for feature-specific; `src/components/common/` + `forms/` + `layout/` for shared |
| **page-size limits** | Any page > 400 lines split into sub-components |
| **test organization** | `/app/backend/tests/` — one file per module + smoke script + cross-tenant sweep |

## 10.3 Legacy MVP Compatibility

MVP's existing `models/`, `routers/`, `services/` layout is compatible with the new standard. Only the **new `repositories/` folder** needs to be introduced when Settings, Notifications, DocuLink, and subsequent new modules land. **No refactor of existing MVP code is required.**

---

# PART 11 — EXISTING-CODE REUSE POLICY

## 11.1 Reuse Classifications (LOCKED)

| Classification | Meaning |
|---|---|
| **KEEP** | MVP working code; do not touch |
| **COPY AND INTEGRATE** | Donor code copies as-is + import path fix |
| **COPY AND TARGETED REFACTOR** | Rename `job_id`→`order_id`, adjust imports, adjust permissions; behavior preserved |
| **EXTRACT BUSINESS LOGIC AND REHOUSE** | Take the algorithm; discard the surrounding donor scaffolding |
| **MERGE DUPLICATE IMPLEMENTATIONS** | Consolidate duplicated behavior across donors into one MVP implementation |
| **REBUILD AGAINST MVP SHARED SERVICES** | Donor code is reference only; write fresh on MVP shared services |
| **REMOVE** | Donor file never lands |
| **DEPRECATE** | Existing MVP code retired in favour of a new replacement |
| **MODULE PREFLIGHT REQUIRED** | Full donor file trace before any port |
| **OWNER DECISION REQUIRED** | Reuse path pending owner decision |

## 11.2 Priority Order (LOCKED)

1. **Preserve working MVP code.**
2. **Reuse verified donor code** where architecture is compatible.
3. **Apply targeted refactoring** where terminology, imports, permissions, or tenant handling differ.
4. **Extract business behavior** when donor architecture is unsafe.
5. **Rebuild** only when reuse would be less safe or more expensive than fresh implementation.
6. **Never copy an entire donor repository into MVP.**
7. **Never create parallel domain models.**

## 11.3 Donor Rules

### 11.3.1 `SIGNGUY-MVP`
- Permanent destination.
- Preserve working systems.
- Targeted extensions only.
- No wholesale rebuild.

### 11.3.2 `SIGNGUY-AI-OS`
- No new development.
- Complete-tree comparison before any archive.
- Read-only reference.
- **No deletion before final commercial completion.**

### 11.3.3 `signguyai_rebuild_version` (REB)
- Architecture reference.
- Specification source (`memory/MODULE SPECS MDS/*` + `ORDER_PORTAL_*_SPEC.md`).
- Working-scaffold donor for: Settings, Communications (notifications + email activity + SendGrid webhook), DocuLink, Wrap Lab, Platform Admin, Shared Systems (community + AI tool catalog), Webstores capabilities scaffold, Billing Rules (candidate), Pricing Engine (reference), Upload Validation, Order Item Rules, Quotes (line items + expiration + revisions + snapshots), Orders (rich item schema + `production_required` gate).
- **Sanitize preview code** (`PreviewEnvelope`, preview-user impersonation defaults) before landing.
- **Resolve `core_runtime` imports** — collapse to a single import path when porting into MVP.
- **Do not copy thin frontend wholesale** — REB frontend has only 5 pages and is behind the backend.

### 11.3.4 `signguy-ai-feb22` (FEB)
- Financial-logic donor.
- **Rename Job terminology** on every ported line.
- Preserve invoice reconciliation logic (`InvoiceService.compute_line_items_and_totals` + `reconcile_invoice_financials`).
- Preserve payment idempotency (`record_manual_payment` 409-on-replay).
- Preserve controlled void behavior (`void_manual_payment` — required reason, never applies to Stripe).
- **Do not copy Job-domain routes wholesale** — `routes/jobs.py`, `routes/tiers.py`, `routes/portal.py` (Job-domain), `routes/employee_portal.py` are REMOVE.

### 11.3.5 Original SIGNGUYAI (ORIG)
- Feature-discovery map.
- Targeted donor only.
- **Module preflight required for large files** (portal 2195 lines, webstores 3775 lines, signatures 658 lines, approvals 355 lines).
- **Do not copy monolithic App.js.**
- **Do not copy giant pricing modules** (`routes/pricing.py`, `routes/pricing_setup.py`).
- **Do not copy dev or backup routes** (`routes/dev.py`, `routes/backup.py`).
- **Do not copy Job Ticket domain** (`routes/job_tickets.py`, `LegacyJobRedirect.js`).

## 11.4 Reuse Assignment (summary — cross-reference Part 2 of Source Map for full table)

| System | Path |
|---|---|
| Auth / JWT / password reset | KEEP (MVP) |
| Tenants / permissions catalog | REF (MVP → adopt REB's Permission StrEnum shape) |
| Object storage | KEEP (MVP + ORIG object_storage.py FSV compatible) |
| Upload validation | EXTRACT (REB `services/upload_validation.py`) |
| Attachments / polymorphic links / shares | REF (MVP + adopt REB's `file_links`, `document_links`, `document_shares`) |
| Settings framework | REBUILD against MVP shared services using REB scaffold (REF path) |
| Notifications | REBUILD against MVP shared services using REB scaffold |
| Email — outbound | KEEP (MVP) |
| Email — inbound webhook + activity log | REF (REB SendGrid webhook + email_activity) |
| Documents / DocuLink | REBUILD against MVP shared services using REB scaffold (rewire storage to Emergent) |
| Signatures | REF ORIG (rename job→order); MODULE PREFLIGHT REQUIRED |
| Approvals | REF ORIG (dual-parent already); MODULE PREFLIGHT REQUIRED |
| Customers | KEEP (MVP) |
| Quotes | REF (REB shape) |
| Orders / Order Items | REF (REB shape) |
| `production_required` gate | REF (REB `services/order_item_rules.py`) |
| Pricing snapshots | REF (REB pricing-calculate/save/override endpoints) |
| Pricing Foundation & Calculator | KEEP (MVP) |
| Work Orders | REF (MVP + REB `generate_work_order_placeholder` snapshot rule) |
| Invoices dual status | EXTRACT (FEB `invoice_service.py`) |
| Payments unified | EXTRACT (FEB `payment_service.py` + `models/payments.py`) |
| Stripe Connect | REF (FEB confirm + ORIG onboarding); FINANCIAL-SAFETY REVIEW REQUIRED |
| Money representation policy | Ratify MVP split (RECOMMENDED — owner ratify) |
| Customer portal | REBUILD using ORIG as blueprint; MODULE PREFLIGHT REQUIRED |
| Employee portal | REBUILD using ORIG + FEB as blueprints |
| Wrap Lab | REF (REB workflow engine + models + routes) |
| Webstores | REBUILD using REB `ORDER_PORTAL_*_SPEC.md` + ORIG feature map |
| Public storefront | REBUILD |
| Community Hub | REF (REB scaffold) |
| AI tool catalog | EXTRACT (REB 24-tool catalog) |
| AI generation | REBUILD (Emergent LLM key + credit metering) |
| Subscription plans & fees | EXTRACT (REB `billing_rules.py` candidate + owner approval) |
| AI credits & top-ups | EXTRACT + REBUILD (REB + new credit ledger) |
| Feature flags / entitlements | REF (REB `FeatureEntitlementRepository` spec) |
| Platform administration | REF (REB `routes/platform_admin.py`) |
| Global search | REBUILD |
| Background job runner | REBUILD |
| SMS / MMS | REBUILD |
| Global reports & analytics | REBUILD |
| Inventory / Vendors / Purchasing | REBUILD (using ORIG + REB references) |
| Payroll / Time Clock / Employees | REBUILD |
| Frontend page / component library | KEEP + EXTEND (MVP shadcn/ui) |

---

# PART 12 — NEVER-AGAIN REGISTER

Permanent list of architectural and workflow mistakes that must not return. Every rule below is enforced by code review and by the Commercial-Release Gate (Part 15).

| # | Prohibited pattern | Why it caused problems | Prevention rule | Required test/review | Recorded in |
|---|---|---|---|---|---|
| 1 | Multiple active rebuild repositories | Fragmented development; drift; silent divergence | One live repo (`SIGNGUY-MVP`); donors are read-only references | Freeze donors against commits | `AGENT_INSTRUCTIONS.md`, Part 1.9 above |
| 2 | Parallel customer systems | Data model split; broken linked records | One `customers` collection; one Pydantic `Customer` model | Cross-repo grep on port | Part 4 |
| 3 | Parallel order systems | Same as above | One `orders` + `order_items` collection | Cross-repo grep on port | Part 4 |
| 4 | `Job` and `Order` models coexisting | Terminology contamination; data model split | Terminology lock (Part 2); rename on every port | Grep for `job_id`, `job_ticket_id`, `db.jobs`, `Job`, `JobTicket` at review | Part 2 |
| 5 | Duplicate invoice/payment systems | Reconciliation drift; double writes | One `invoices` + one `payments` collection | Cross-repo grep on port | Part 4 |
| 6 | Duplicate settings systems | Config drift | One settings framework (REB shape) | New-module review | Part 4, Part 10 |
| 7 | Duplicate file-storage systems | Base64 anti-pattern regression risk | One object-storage adapter (Emergent) | Grep for base64 inline blobs | Part 6 |
| 8 | Base64 files stored in Mongo | Storage bloat; unindexable; costly | Object storage MANDATORY | Startup guard + code review | Part 6 |
| 9 | Frontend-only permissions | Client-bypass security holes | Backend `require_permission()` MANDATORY | Cross-tenant + cross-role sweep in testing | Part 10 |
| 10 | Missing tenant filters | Cross-tenant data leak | Repository pattern enforces tenant filter | Cross-tenant sweep test | Part 10 |
| 11 | Hardcoded tenant IDs | Bypasses tenant filter | Never hardcode; all tenant_id comes from `get_current_tenant` dep | Code review | Part 10 |
| 12 | Direct payment-status mutation | Reconciliation drift | Payments flow through `PaymentService.record_manual_payment` or webhook confirm | Code review | Part 6, Part 7A |
| 13 | Invoice document status mixed with financial status | Reports incorrect | Independent `document_status` + `financial_status` fields | Part 4 review | Part 7A |
| 14 | Unverified payment webhooks | Money loss / injection | Signature verify + replay-safe (LOCKED) | Webhook infra tests | Part 6 |
| 15 | No idempotency on payment writes | Double charge risk | Idempotency-Key MANDATORY | Payment tests | Part 6 |
| 16 | Portal users sharing internal JWT permissions | Privilege escalation | Portal identity + `sub_scope="portal"` (LOCKED) | Portal auth tests | Part 8 |
| 17 | Preview-user impersonation in production | Tenant takeover | Sanitize `PreviewEnvelope` on port | Startup guard on ENV=production | Part 11.3.3 |
| 18 | Dev-login routes in production | Tenant takeover | Startup guard fails if `AUTH_DEV_BYPASS==true` + `ENV=production` | Startup guard test | Part 15 |
| 19 | Placeholder secrets in production | Credential compromise | Startup guard on placeholder JWT/keys | Startup guard test | Part 15 |
| 20 | Giant App.js | Unmaintainable | Page-size limit + feature folders | Frontend review | Part 10 |
| 21 | Giant route files controlling unrelated modules | Coupling | One router per top-level API prefix | Backend review | Part 10 |
| 22 | Giant pricing modules | Unmaintainable + banned | MVP pricing service is the target | Code review | Part 11 |
| 23 | Duplicate menus | UI confusion | One nav per top-level area | UX review | Part 3 |
| 24 | Duplicate dashboards | Confusion | One dashboard per area | UX review | Part 3 |
| 25 | Duplicate pages | Bit rot | One page per top-level route | UX review | Part 3 |
| 26 | Legacy redirects treated as permanent features | Cruft | Remove legacy redirects at port | Migration checklist | Part 4 |
| 27 | Hardcoded categories or status values | Rigidity | Enum/StrEnum with a single source | Code review | Part 4 |
| 28 | Scattered business formulas | Duplication + drift | Services own algorithms | Code review | Part 10 |
| 29 | Client-calculated authoritative totals | Manipulation risk | Server recomputes on every read/write | Payment tests | Part 6, Part 11 |
| 30 | Silent status changes | Audit gaps | Every state transition writes an audit event | Backend review | Part 10 |
| 31 | Missing audit events | Compliance gaps | Every write requires `record_audit(...)` | Backend review | Part 10 |
| 32 | Destructive deletion where archive is required | Data loss | Soft-delete/archive for records with financial or customer impact | Backend review | Part 10 |
| 33 | Modules marked complete because a page renders | False progress | CP1–CP15 gate before feature complete | Feature preflight | Part 15 |
| 34 | Placeholder data presented as production behavior | Fake demos | No production launch until CR gate passes | Commercial release gate | Part 15 |
| 35 | Copying donor code without reading dependencies | Silent breakage | Module preflight required for PSI files | Feature preflight | Part 4 |
| 36 | Rewriting working code because agent prefers another style | Regression | Priority-order enforced (Part 11.2) | Code review | Part 11 |
| 37 | Beginning a module before its dependencies exist | Blocked builds | Build order enforced via checkpoint groups | Part 14 | Part 14 |
| 38 | Building Webstores before entitlements/portals/payments | Foundational holes | Webstore checkpoint blocked until F9 + F11 + F14 land | Part 14 gates | Part 14 |
| 39 | Building Wrap Lab before approvals/signatures/files/portal | Foundational holes | Wrap Lab checkpoint blocked until dependencies land | Part 14 gates | Part 14 |
| 40 | Enabling AI before credit metering and cost controls | Cost blowup | AI blocked until credit ledger + entitlements + cost caps land | Part 14 gates | Part 14 |
| 41 | Archiving donor repositories before migration completion | Loss of reference | No deletion until final commercial completion (LOCKED) | Repository policy | Part 1.9, Part 5 |
| 42 | Allowing scope documents and implementation to drift | Documentation rot | Re-run audit at each checkpoint completion | Checkpoint review | Part 14 |

---

# PART 13 — OPEN DECISION REGISTER

One consolidated register of every decision still requiring owner approval. Prompt 4 (final master build plan) resolves them.

| # | Decision | Existing options | Evidence | Risks | Recommendation | Owner decision | Status | Modules affected | Blocks master plan? | Blocks implementation? | Blocks commercial release? |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Permanent money policy ratification | (a) Ratify MVP split (cents commerce / dollars config); (b) Move commerce to Decimal dollars; (c) Move config to cents | FSV MVP + FEB | Wrong choice = data migration | Ratify MVP split (7A) | Pending | RECOMMENDED | Invoices, Payments, Quotes, Orders, Reports | Y | Y (Stage 6) | Y |
| 2 | Permission catalog | (a) Adopt 9.3 recommended catalog; (b) Adopt REB 57-permission StrEnum verbatim; (c) Custom subset | FSV REB + RV MVP | Missing permissions = holes; over-broad = privilege | Adopt 9.3 recommended | Pending | RECOMMENDED | All modules | N | Y (new modules) | Y |
| 3 | Repository-class pattern | (a) Adopt for new modules only; (b) Refactor MVP too; (c) Skip and continue MVP style | RV MVP + FSV REB | Refactor = risk without value; skip = inconsistency | Adopt for new modules only (10.1) | Pending | RECOMMENDED | New modules | N | Y (new modules) | N |
| 4 | SendGrid fail-closed production behavior | (a) Force-fail startup if secret unset in prod; (b) Log warning; (c) Silent | FSV REB | Fake bounce injection if silent | Force-fail (6.2 row 2) | Pending | RECOMMENDED | Email activity, Portal notifications | N | Y (webhook enable) | Y |
| 5 | `SIGNGUY-AI-OS` archive timing | (a) Freeze now + archive after commercial completion; (b) Archive now; (c) Merge into MVP; (d) Delete | STHV comparison | Delete = lose recovery; merge = drift | Freeze now + archive after commercial completion; no delete | Pending | RECOMMENDED | Repo policy | N | N | N |
| 6 | Webstores standalone AND add-on policy | (a) Both (owner direction); (b) Add-on only; (c) Standalone only | Owner statement | Duplication if not shared backend | Both with shared backend (Part 5) | OWNER APPROVED IN THIS REGISTER (direction); specific pricing pending Prompt 4 | OWNER APPROVED | Webstores | N | N | Y (before Webstore launch) |
| 7 | Wrap Lab standalone policy | (a) Add-on + conditional standalone; (b) Add-on only; (c) Standalone always | Owner statement | Standalone duplication risk | Add-on + conditional standalone (5.6) | Pending confirmation after Wrap preflight | RECOMMENDED | Wrap Lab | N | Y (Wrap Lab release) | Y (Wrap Lab release) |
| 8 | Portal authentication mode | (a) Multi-mode (password + magic link + public tokens); (b) Magic-link-only; (c) Password-only | ORIG PSI + industry practice | Magic-link-only = bad for recurring portal users; password-only = friction on approvals | Multi-mode (Part 8) | Pending | RECOMMENDED | Portals | N | Y (portal launch) | Y |
| 9 | Sales-tax strategy | (a) Shop-configured + integration boundary; (b) Full Avalara/TaxJar at launch; (c) Manual only | Comparison | Full integration = cost + vendor lock; manual only = errors | Shop-configured + integration boundary (7C.2) | Pending | RECOMMENDED | Invoices, Reports | N | Y (Invoice tax) | Y |
| 10 | Commercial pricing | See 7B.3 candidate table | REB candidate | Wrong pricing = revenue impact | Ratify each row in Prompt 4 | Pending | REQUIRES OWNER DECISION | Subscriptions | Y | Y (billing enable) | Y |
| 11 | Founders pricing (specific amounts) | Candidate: $189/mo Complete Bundle | REB candidate | Wrong founder pricing = acquisition impact | Ratify in Prompt 4 | Pending | REQUIRES OWNER DECISION | Subscriptions | Y | Y (Founder launch) | Y |
| 12 | AI-credit pricing per top-up pack | Candidate: $19/100, $45/300, $99/800 | REB candidate | Wrong pricing = margin risk | Ratify + measured-cost audit before lock | Pending | REQUIRES OWNER DECISION | AI credits | Y | Y (AI billing) | Y |
| 13 | Included AI credit amounts per plan | Candidate per REB | REB candidate | Wrong amount = margin or churn | Ratify + measured-cost audit | Pending | REQUIRES OWNER DECISION | AI credits, Subscriptions | Y | Y (AI billing) | Y |
| 14 | AI credit expiration | (a) Included credits reset monthly, top-ups never expire; (b) All expire in 12 months; (c) Custom | Industry | Expiration = churn if aggressive | Included reset monthly, top-ups never expire (7D.1) | Pending | RECOMMENDED | AI credits | N | Y (AI billing) | Y |
| 15 | Transaction fees | Candidate: 0/50/100 bp standard, 0/150/200 bp webstore | REB candidate | Wrong fee = margin/adoption impact | Ratify + reconcile founders-promo redemption cap with "first 50" | Pending | REQUIRES OWNER DECISION | Payments, Webstores | Y | Y (Stripe launch) | Y |
| 16 | Setup / onboarding fees | (a) None; (b) One-time; (c) Waived for founders | Candidate | Fees = friction | None (DIY onboarding) | RECOMMENDED | Pending | Subscriptions | N | N | Y |
| 17 | Free-trial limits (non-founder) | (a) 7 days limited AI; (b) 14 days; (c) None | Founder = 7 days | Long trial = revenue delay | Ratify in Prompt 4 (RECOMMENDED: match founders 7 days with limited AI) | Pending | REQUIRES OWNER DECISION | Subscriptions, Marketing | N | Y (Trial enable) | Y |
| 18 | AI provider / model choices | (a) Emergent LLM key with model rules per intensity; (b) Direct provider integration | Emergent confirmed | Model choice affects cost + quality | Emergent LLM key + model rules per tool intensity (7D.1) | RECOMMENDED (owner ratify specific model rules) | RECOMMENDED | AI Tools, AI Assistant | Y | Y (AI enable) | Y |
| 19 | SMS provider | (a) Twilio (donor pattern); (b) Alternative | ORIG uses Twilio | Provider = integration cost + carrier compliance | Twilio (donor-compatible) | Pending | RECOMMENDED | SMS module | N | Y (SMS enable) | N (post-launch OK) |
| 20 | Report-builder scope | (a) Curated report library + custom builder; (b) Curated only; (c) Full BI | ORIG has reports | Full BI = late; curated only = churn | Curated + custom builder (Part 4.3) | Pending | REQUIRES OWNER DECISION | Reports | N | Y (Reports GA) | N (post-launch OK) |
| 21 | Platform-admin impersonation | (a) No impersonation ever; (b) Read-only view-as; (c) Full impersonation with audit | Standard SaaS | Impersonation = support power but abuse risk | Read-only view-as with audit + tenant notification | Pending | REQUIRES OWNER DECISION | Platform Admin | N | Y (Impersonation feature) | N |
| 22 | Customer portal payment methods | (a) Stripe only; (b) Stripe + ACH; (c) Multiple | Stripe covers most | ACH = lower fees, slower | Stripe (card) at launch; ACH later | Pending | REQUIRES OWNER DECISION | Customer Portal, Payments | N | Y (Portal payment) | Y |
| 23 | Employee portal payroll visibility | (a) Full payslip; (b) YTD summary only; (c) None | Legal varies by state | Wrong = legal exposure | Full payslip view with tenant-owner override | Pending | REQUIRES OWNER DECISION | Employee Portal, Payroll | N | Y (Payroll GA) | N (post-launch OK) |
| 24 | Final navigation labels + structure | (a) Left collapsible sidebar with side flyouts per Part 3.1 (LOCKED); (b) Permanent second-level top nav (rejected); (c) Alternative labels (rejected) | Owner directive + Part 3.1 | Wording drift risk | Match Part 3.1 (LOCKED): Home / Shop Operations / Business & Finance / Team & Workflow / Creative Studio / (divider) / Control Center / Help & Community. Flyouts LOCKED per Part 3.2. | LOCKED | LOCKED | Navigation | N | N | N |
| 25 | Final internal checkpoint order | (a) Part 14 recommended groups; (b) Old 0–17; (c) Custom | Part 14 evidence | Order affects delivery | Adopt Part 14 groups (A–H) | Pending | RECOMMENDED | Master build plan | Y | N | N |
| 26 | Grace period on subscription payment failure | (a) 7 days; (b) 3 days; (c) 14 days | Industry | Too short = churn, too long = revenue delay | 7 days soft grace → 14 days soft block → hard block | Pending | RECOMMENDED | Subscriptions, Entitlements | N | Y (Billing enable) | Y |
| 27 | SMS/MMS commercial-release timing | (a) Required before the first commercial sale; (b) Approved permanent-product feature scheduled for a later commercial release | Owner has not resolved this in prior statements; ORIG donor `routes/sms.py` + `services/sms_service.py` exist as reference; carrier registration (US 10DLC) requires lead time | (a) delays initial launch by SMS provider integration + carrier registration; (b) launches without SMS which affects portal messaging + order events + marketing | No automatic choice — owner must select | Pending | **OWNER DECISION — COMMERCIAL RELEASE TIMING** (SMS/MMS remains in permanent product scope regardless of choice) | SMS/MMS, Portal, Notifications, Order events, Marketing | N | N | Y if (a); N if (b) |

**Reconciled decisions (already resolved from prior explicit owner statements):**
- Repository roles (Part 1.9) — LOCKED.
- Terminology (Part 2) — LOCKED.
- Founder direction (Part 7B.1) — OWNER APPROVED (specific values pending in Prompt 4).
- Webstores add-on + standalone direction (Part 5) — OWNER APPROVED.
- Wrap Lab add-on direction (Part 5) — OWNER APPROVED (standalone conditional).
- No customer/order limits (Part 5.1) — OWNER APPROVED.
- AI via credits, not tiers (Part 5.1) — OWNER APPROVED.
- Donor repos remain read-only references, no deletion (Part 1.9) — OWNER APPROVED.
- Money split direction (cents commerce / dollars config) — RECOMMENDED; awaiting explicit ratification.

---

# PART 14 — FINAL INTERNAL BUILD-CHECKPOINT RECOMMENDATION

This is a **proposed dependency reference**. The final master build plan (Prompt 4) may rename, combine, divide, or reorder these checkpoints. The old 0–17 numbering is not preserved.

## 14.1 Checkpoint Groups (RECOMMENDED)

### Group A — Product Rules and Security

- **Purpose:** Land every non-negotiable rule the rest of the build depends on.
- **Included modules:** Permanent terminology; money policy; repository roles; production secret policy; dev-bypass restrictions; tenant rules; permission model; audit requirements; file-storage rules; reuse rules; startup guards.
- **Dependencies:** None (foundational).
- **Source repositories:** Existing docs + this register.
- **Required module preflights:** None.
- **Required owner decisions:** Decisions 1, 2, 3, 4, 5 from Part 13.
- **Entry conditions:** Prompt 4 begun.
- **Exit conditions:** All rules recorded in `AGENT_INSTRUCTIONS.md`, startup guards in place (dev-bypass, JWT placeholder, SendGrid webhook secret).
- **Required tests:** Startup guard test on ENV=production.
- **Required documentation:** `AGENT_INSTRUCTIONS.md` updated.
- **Commercial-release relevance:** Blocker (must land before any subsequent group).
- **Parallel-safe with:** None.
- **Risk if out of order:** Silent security regressions.

### Group B — Shared Platform Foundations

- **Purpose:** Land shared services every module depends on.
- **Included modules:** Settings framework (F7); Notifications (F8); Email activity log + inbound webhook (F5 addendum); Upload validation (F2 addendum); Webhooks infra (F11); Feature entitlements (F9); Background jobs (F10) — may split later; Portal authentication (F12); Monitoring; Error logging (already partial in MVP).
- **Dependencies:** Group A.
- **Source repositories:** REB (Settings, Notifications, SendGrid webhook, Upload validation, Feature entitlements spec); FEB (Stripe webhook pattern shared with F11); ORIG (Background jobs reference, Portal auth reference).
- **Required module preflights:** None for scaffolds; portal auth requires ORIG portal preflight (deferred to Group F when portal launches).
- **Required owner decisions:** Decision 4 (SendGrid), Decision 8 (portal auth mode).
- **Entry conditions:** Group A exit conditions met.
- **Exit conditions:** All shared services expose endpoints + repositories, F7–F13 stubbed and covered by smoke tests.
- **Required tests:** Cross-tenant sweep on each new module; webhook signature verify; entitlement flip test.
- **Required documentation:** Per-service README under `backend/app/services/` or module docs.
- **Commercial-release relevance:** Blocker for Groups C–H.
- **Parallel-safe with:** None (Group B modules interlock).
- **Risk if out of order:** Modules built on missing foundations; rework.

### Group C — Core Money and Order Pipeline

- **Purpose:** Complete the Customer → Quote → Order → Invoice → Payment spine.
- **Included modules:** Customers (extend for portal); Quotes (REB shape — line items, expiration, revisions); Quote Line Items; Orders (REB rich shape); Order Items (40+ fields including `production_required`); Pricing snapshots on Quote/Order line items; Invoices (dual status — FEB EXT); Payments (FEB EXT); Production-required gate; Work Orders (rework to snapshot only production items).
- **Dependencies:** Groups A, B.
- **Source repositories:** MVP (Customers, Quotes basic, Orders basic, Work Orders basic); REB (Quotes shape, Orders shape, Order Item Rules, pricing snapshots endpoints); FEB (Invoice service + Payment service + Payment model).
- **Required module preflights:** None (all files FSV).
- **Required owner decisions:** Decision 1 (money policy), Decision 15 (transaction fees).
- **Entry conditions:** Group B exit.
- **Exit conditions:** All spine modules pass cross-tenant + permission + payment idempotency tests.
- **Required tests:** Cross-tenant sweep, payment idempotency, overpayment reject, void-with-reason, work-order gate, quote-to-order idempotency, pricing snapshot equality.
- **Required documentation:** Per-module changelog.
- **Commercial-release relevance:** Blocker for all higher groups.
- **Parallel-safe with:** None internal; Group D DocuLink work may begin in parallel once Files infra is stable.
- **Risk if out of order:** Financial data model split.

### Group D — Document and Customer Workflow

- **Purpose:** Documents, templates, forms, questionnaires, signatures, proofs, approvals, customer portal, public forms.
- **Included modules:** DocuLink; Forms; Questionnaires; Templates; Signatures; Proofs; Approvals; Customer Portal; Public Forms; Public Proof Approval; Public Signature Pages.
- **Dependencies:** Groups A, B, C.
- **Source repositories:** REB (DocuLink FSV); ORIG (Signatures PSI, Approvals PSI, Portal PSI, Forms/Questionnaires RS); MVP (Files/Attachments RV).
- **Required module preflights:** Y — Signatures, Approvals, Customer Portal, Forms, Questionnaires.
- **Required owner decisions:** Decision 8 (portal auth), Decision 22 (portal payment methods).
- **Entry conditions:** Group C exit.
- **Exit conditions:** Customer portal end-to-end flow works (approve proof, sign contract, pay invoice via Stripe).
- **Required tests:** Portal identity isolation, magic-link single-use, public-token single-action + expiration, cross-tenant portal sweep.
- **Required documentation:** Portal onboarding docs + terms/policies.
- **Commercial-release relevance:** Blocker (customer portal is required for commercial release).
- **Parallel-safe with:** Group E Inventory, Purchasing, Finance, and Reporting (some parallelism OK).
- **Risk if out of order:** Portal identity leaks, silent proof approvals.

### Group E — Inventory, Purchasing, Finance, and Reporting

- **Purpose:** Land Inventory + Vendors + Purchasing operational modules AND Finance + Expenses + Taxes + Reports + Business Analytics in a single implementation checkpoint. These systems share this checkpoint because purchasing costs, inventory valuation, expenses, financial reporting, and analytics all depend on the completed Order, Invoice, and Payment pipeline delivered in Group C. **Checkpoint grouping does NOT change permanent navigation placement.**
- **Navigation placement (LOCKED — unchanged by this checkpoint grouping):**
  - Inventory, Vendors, and Purchasing are navigated through **Shop Operations → Inventory & Purchasing** (per Part 3.2.1 / Part 4.2).
  - Finance, Expenses, Taxes, Reports, and Business Analytics are navigated through **Business & Finance** (per Part 3.2.2 / Part 4.3).
- **Included modules:** Inventory; Vendors; Purchasing; Finance Dashboard; Financials; Sales; Expenses; Taxes; Reports; Custom Report Builder; Business Analytics.
- **Dependencies:** Groups A, B, C.
- **Source repositories:** ORIG (Inventory RS, Vendors RS, Purchasing RS, Finance RS, Reports RS); New (Custom Report Builder, Business Analytics).
- **Required module preflights:** Y — Inventory, Vendors, Purchasing, Reports.
- **Required owner decisions:** Decision 9 (tax strategy), Decision 20 (report scope).
- **Entry conditions:** Group C exit.
- **Exit conditions:** Financial dashboards render; inventory valuation feeds finance; tax snapshots stored on invoices; reports pass tenant scoping; purchasing costs flow into finance.
- **Required tests:** Tax snapshot invariance on historical invoices, report tenant scoping, purchasing→expense flow, inventory valuation consistency.
- **Required documentation:** Reports catalog; inventory setup guide.
- **Commercial-release relevance:** Blocker (financial reporting + inventory + purchasing are required).
- **Parallel-safe with:** Group D (some), Group F.
- **Risk if out of order:** Reports read incomplete data; inventory valuation misaligned with orders/payments.

### Group F — Team & Workflow

- **Purpose:** Employees, tasks, calendar, scheduling, time clock, timesheets, payroll, employee portal, internal messaging.
- **Included modules:** Employees; Tasks; Kanban; Calendar; Appointments; Install + Production Scheduling; Time Clock; Timesheets; Payroll; Employee Portal; Internal Notes/Messages/Announcements.
- **Dependencies:** Groups A, B; Group D for Employee Portal.
- **Source repositories:** ORIG (Employees, Tasks, Kanban, Calendar, Scheduling, Time Clock, Timesheets, Employee Portal RS); FEB (Employee Portal RS).
- **Required module preflights:** Y — Employees, Payroll, Time Clock, Employee Portal.
- **Required owner decisions:** Decision 23 (payroll visibility in Employee Portal).
- **Entry conditions:** Group D Employee Portal foundations exist.
- **Exit conditions:** Employee end-to-end flow works (clock in, view tasks, view timesheet, view payslip if enabled).
- **Required tests:** Portal isolation between employees, cross-tenant sweep, payroll data integrity.
- **Required documentation:** Payroll setup docs + labor compliance disclaimer.
- **Commercial-release relevance:** Blocker (payroll + time clock are required).
- **Parallel-safe with:** Groups D, E.
- **Risk if out of order:** Employee portal built on missing shared services.

### Group G — Add-ons (Webstores + Wrap Lab)

- **Purpose:** Sellable add-on modules.
- **Included modules:** Webstores; Webstore Products; Webstore Variants; Public Storefront; Webstore Owner Portal; Webstore Manager Portal; Stripe Connect; Payouts; Wrap Lab; Wrap Portal behavior.
- **Dependencies:** Groups A, B, C, D. Requires F9 (Entitlements), F11 (Webhooks), F14 (Payments reconciliation), portal auth (F12), Approvals, Signatures, DocuLink.
- **Source repositories:** REB (Webstore capabilities scaffold, Wrap Lab workflow engine — both FSV); ORIG (Webstore feature discovery RS, Wrap fragments RS); FEB (Stripe Connect confirm FSV).
- **Required module preflights:** Y — Webstores (full donor analysis: 3775 lines), Stripe Connect (financial safety review), Wrap Lab portal projection.
- **Required owner decisions:** Decisions 6, 7 (product boundaries), 10, 15 (pricing + fees).
- **Entry conditions:** Groups C, D exit; Stripe Core + Stripe Connect webhooks verified.
- **Exit conditions:** End-to-end webstore order → payment → payout works; wrap project 11-stage flow works.
- **Required tests:** Stripe Connect payout reconciliation, webstore tenant isolation, wrap-project portal allowlist enforcement.
- **Required documentation:** Webstore setup guide, wrap onboarding.
- **Commercial-release relevance:** Blocker for founder launch (founders include both).
- **Parallel-safe with:** Group H (parts).
- **Risk if out of order:** Money movement errors.

### Group H — AI, Platform, and Commercial Systems

- **Purpose:** AI Tools + Assistant + credits, platform admin, community, help, onboarding, marketing site, public pricing, subscription billing.
- **Included modules:** AI Tools; AI Assistant; Prompt Library; AI Credits; Subscription Billing; Platform Admin; Community; Help; Onboarding; Marketing Website; Public Pricing.
- **Dependencies:** Groups A, B, C, F9 (Entitlements), Stripe Core.
- **Source repositories:** REB (AI catalog FSV, Community FSV, Platform Admin FSV, Billing Rules candidate FSV); ORIG (AI Assistant RS, Onboarding RS, Marketing site RS).
- **Required module preflights:** Y — AI Assistant, AI Tools per-tool, Platform Admin, Marketing site.
- **Required owner decisions:** Decisions 10, 11, 12, 13, 14, 15, 17, 18 (all commercial + AI decisions).
- **Entry conditions:** Group B + Stripe Core live.
- **Exit conditions:** Founder can sign up, receive credits, use AI tools, be metered; Platform Admin can suspend/reactivate tenants.
- **Required tests:** Credit ledger integrity, cost-cap enforcement, provider outage refund, subscription proration.
- **Required documentation:** AI tool docs, pricing page, onboarding guide.
- **Commercial-release relevance:** Blocker.
- **Parallel-safe with:** Group G (parts).
- **Risk if out of order:** Uncapped AI cost.

## 14.2 Global Rules Across All Checkpoints

- **CP1–CP15** (from Source Map Part 10) apply to every stage.
- **Startup guards** MUST be in place before Group C completes: `AUTH_DEV_BYPASS==true` on `ENV=production` = fail; placeholder JWT secret = fail; SendGrid webhook secret unset on production = fail; Stripe webhook secret unset on production = fail.
- **Cross-tenant sweep** runs after every module.
- **Testing agent iteration** runs after every group.
- **Documentation sync** to `AGENT_INSTRUCTIONS.md` and this register at every group exit.

---

# PART 15 — COMMERCIAL-RELEASE GATE

The application MUST NOT be sold until every gate below passes. Every gate is a **blocker** unless explicitly listed as accepted-limitation.

## 15.1 Product Completeness

- [ ] All approved required modules implemented (Part 4).
- [ ] All approved portals implemented (Customer, Employee, Webstore Owner, Webstore Manager, public approval + signature).
- [ ] All approved add-ons implemented (Webstores, Wrap Lab).
- [ ] All approved AI systems implemented (24-tool catalog + Assistant + credit ledger + provider abstraction).
- [ ] No placeholder pages served.
- [ ] No mock production behavior remains (no `AUTH_DEV_BYPASS=true` in prod; no `_dev/*` endpoints).
- [ ] No disconnected frontend/backend modules.
- [ ] No unfinished workflows presented as complete.

## 15.2 Security

- [ ] Production secrets rotated (JWT, SendGrid, Stripe test → live, storage keys).
- [ ] Dev bypass disabled on `ENV=production`.
- [ ] Dev routes blocked (`/api/auth/dev-*`, `/api/auth/_dev/*`).
- [ ] Tenant isolation tested (cross-tenant sweep on every module).
- [ ] Permissions tested (every role × every endpoint).
- [ ] Portal isolation tested (portal identities cannot access staff endpoints).
- [ ] Public endpoints rate-limited (portal login, magic-link request, public forms, public storefront).
- [ ] Uploads validated (MIME + magic-byte + size + SHA-256).
- [ ] Files private by default.
- [ ] Webhook signatures verified (SendGrid, Stripe, future integrations).
- [ ] Replay protection active (event ID unique index).
- [ ] Audit logging active (every write records an event).

## 15.3 Financial Safety

- [ ] Integer-cent commerce policy enforced (`_cents` on every commerce field; conversion boundary documented).
- [ ] Invoice states correct (document_status + financial_status independent).
- [ ] Payment states correct (unified Payment collection; source distinguished).
- [ ] Payment idempotency verified (Idempotency-Key + DuplicateKeyError race handling).
- [ ] Overpayment blocked.
- [ ] Controlled void behavior verified (manual only, void reason required, Stripe never voided).
- [ ] Stripe webhook reconciliation verified.
- [ ] Refunds tested (if included in scope).
- [ ] Tax snapshots preserved on invoice.
- [ ] Subscription entitlements tested (flip on/off; grace-period behavior).
- [ ] AI-credit ledger tested (debit + refund + admin adjust; cost cap enforcement).
- [ ] Transaction fees approved and applied at Payment/Payout time.

## 15.4 Data Integrity

- [ ] Indexes present on all documented collections.
- [ ] Uniqueness constraints present ((tenant_id, number), (tenant_id, order_id) on invoices).
- [ ] Conversions idempotent (quote → order, order → invoice, work order draft).
- [ ] Archives preserve records (no destructive delete on customers/orders/invoices).
- [ ] No orphaned attachments.
- [ ] No duplicate active systems (no `db.jobs`, no parallel customer/order/payment collections).
- [ ] No Job-domain collections in production database.
- [ ] Backups and recovery tested.
- [ ] Data migration reports complete.

## 15.5 Quality

- [ ] Unit tests present for each module.
- [ ] Integration tests present (quote-to-order-to-invoice-to-payment; wrap-project stage flow; webstore order flow).
- [ ] End-to-end tests present (Customer portal proof approval + payment; founder signup + AI generation + credit debit).
- [ ] Cross-tenant tests pass.
- [ ] Permission matrix tests pass.
- [ ] Portal tests pass.
- [ ] Payment tests pass.
- [ ] Integration-failure tests pass (SendGrid down, Stripe down, provider timeout).
- [ ] Responsive UI tests pass (mobile + tablet + desktop).
- [ ] Accessibility review done.
- [ ] Loading/error/empty-state review done.
- [ ] Performance review done (P95 request latency, page-load).
- [ ] Monitoring and logging verified.

## 15.6 Operations

- [ ] Production deployment procedure documented.
- [ ] Rollback plan documented.
- [ ] Incident response procedure documented.
- [ ] Error alerts wired.
- [ ] Billing support process documented.
- [ ] Customer-support process documented (support ticket + email).
- [ ] Onboarding process documented.
- [ ] Documentation complete (in-app Help Center + external docs).
- [ ] Privacy and data-deletion process documented.
- [ ] Terms of Service + Privacy Policy published.
- [ ] Status monitoring live.
- [ ] Provider outage procedures documented.

## 15.7 Commercial Readiness

- [ ] Final prices approved (Part 7B decisions ratified).
- [ ] Plans approved.
- [ ] Trial approved (founders 1-week; non-founder trial per Decision 17).
- [ ] Founder offer approved (Decision 11).
- [ ] AI-credit costs approved (Decisions 12–13, with measured-cost audit if applicable).
- [ ] Setup fees approved (Decision 16).
- [ ] Public pricing page accurate.
- [ ] Subscription checkout tested.
- [ ] Cancellation behavior tested.
- [ ] Entitlement changes tested (upgrade, downgrade, add-on toggle).
- [ ] Taxes and disclaimers approved.
- [ ] Marketing pages accurate.
- [ ] Support contact active.

## 15.8 Definitions

- **Release blocker:** Any gate above unchecked at launch.
- **Major issue:** Regression in a working module post-launch.
- **Minor issue:** Non-blocking UX/copy issue.
- **Accepted limitation:** A pre-launch limitation formally documented and approved by the owner (e.g., "Google Calendar synchronization is not included at launch; the internal SignGuy AI calendar remains fully functional.").

**No release blocker may remain open at commercial launch.**

---

# PART 16 — FINAL EVIDENCE PACKAGE SUMMARY

## 16.1 Final Product Definition

SignGuy AI is the permanent multi-tenant commercial business-management platform for sign, graphics, wrap, print, and apparel shops. It unifies customer → quote → order → work order → production → invoice → payment plus documents, portals, industry-specific pricing, AI tools, Wrap Lab, Webstores, inventory, payroll, and reports on a single shared backend.

## 16.2 Final Permanent Repository

- **Permanent destination:** `dnblack323/SIGNGUY-MVP`.

## 16.3 Final Repository Roles

- `SIGNGUY-MVP` = permanent product.
- `SIGNGUY-AI-OS` = frozen mirror (no new development, archive timing deferred, no delete).
- `signguyai_rebuild_version` = read-only architecture + scaffold donor.
- `signguy-ai-feb22` = read-only financial-logic donor.
- `signguyai` = read-only feature-discovery + targeted donor.

## 16.4 Final Terminology

- Customer / Lead / Quote / Quote Line Item / Order / Order Item / Work Order / Work Order Summary / Invoice / Payment / Proof / Approval / Document / Template / Questionnaire / Form / Signature Request / Webstore / Webstore Owner / Webstore Manager / Wrap Project / Tenant / Organization / User / Employee / Platform Admin / AI Credit / Subscription / Add-on / Entitlement.
- Prohibited: Job / Job Item / Job Ticket / Production Ticket / Job Ticket Summary.

## 16.5 Final Top-Level Navigation

**Collapsible left sidebar** with side flyouts per major area (no permanent second-level top navigation). Home icon + six flyout areas + divider:

```
[HOME]
Shop Operations
Business & Finance
Team & Workflow
Creative Studio
─── (divider) ───
Control Center
Help & Community
```

Portals + Public systems live outside the internal sidebar (separately-routed).

## 16.6 Final Module Count

Updated to reflect the LOCKED sidebar-flyout navigation. Module rows re-grouped without deletion; new rows added for Control Center flyout entries (Company Settings, Users & Permissions surface, Integrations surface, Portals, Feature Access, Data & Security, Platform Governance), Team & Workflow (Team Schedule), Business & Finance (Financials), and Creative Studio flyout subsets (Image Tools / Design Tools / Writing Tools / Artwork Workspace / Generated Assets). No underlying bounded modules removed.

- **Foundation and Shared Systems (4.1):** 31 modules (all REQ; SMS/MMS commercial-release timing is Owner Decision 27 — permanent-product scope regardless of timing choice).
- **Shop Operations (4.2):** 33 modules (10 ADD or ADD-dep; rest REQ). Inventory & Purchasing is a single flyout entry combining Inventory + Vendors + Purchasing.
- **Business & Finance (4.3):** 8 modules (Finance Dashboard, Financials, Sales, Expenses, Taxes, Reports, Custom Report Builder, Business Analytics).
- **Team & Workflow (4.4):** 17 modules (adds Payroll, Time Clock, Timesheets, Employee Scheduling, Team Schedule).
- **Creative Studio and AI (4.5):** 15 modules (renamed from Design Studio; adds Image/Design/Writing Tools flyout subsets + Artwork Workspace + Generated Assets + AI History).
- **Control Center (4.6):** 16 modules (Company Settings, Users & Permissions, Integrations, Portals, Feature Access, Data & Security, seven Pricing Defaults surfaces, two Subscriptions & AI Credits surfaces, Platform Governance).
- **Platform and Support (4.7):** 14 modules.
- **Portals and Public Systems (4.8):** 13 modules (Webstore Owner/Manager/Storefront = ADD).
- **Commercial and Billing Systems (4.9):** 5 modules.
- **Total scoped module rows:** ~152 (grew from the prior 139 baseline solely because the new sidebar-flyout structure surfaces additional first-class configuration and Creative Studio destinations; no underlying bounded module was removed).

## 16.7 Required Modules

Every module in Part 4 marked **REQ** or **REQ-DEP**.

## 16.8 Add-On Modules

Webstores + Wrap Lab + Stripe Connect + Payouts + AI systems (metered add-on).

## 16.9 Standalone-Capable Modules

Webstores (Y) + Wrap Lab (Y, conditional on preflight).

## 16.10 Portal Systems

Customer Portal, Employee Portal, Webstore Owner Portal, Webstore Manager Portal.

## 16.11 Public Systems

Public Storefront, Public Forms, Public Questionnaires, Public Quote Requests, Public Customer Intake, Public Proof Approval, Public Signature Pages, Marketing Website, Public Pricing.

## 16.12 Shared Foundations

F1 Auth+Tenants+Permissions, F2 Object Storage+Attachments+Upload Validation, F3 Sequences, F4 Audit+Activity, F5 SendGrid+Webhook+Activity Log, F6 Money Policy, F7 Settings, F8 Notifications, F9 Feature Entitlements, F10 Background Jobs, F11 Webhook Infrastructure, F12 Portal Auth, F13 DocuLink, F14 Money-Safe Reconciliation, F15 Frontend Shared Components.

## 16.13 Approved Reuse Sources

- MVP (KEEP): Auth, Tenants, Users, Permissions, Object Storage, Sequences, Audit, Pricing Foundation + Calculator, SendGrid outbound, Attachments, Frontend shared components, Convert-to-Order idempotency.
- REB (REF/EXT): Settings, Communications (notifications + webhook + email activity), DocuLink, Wrap Lab, Platform Admin, Community/AI catalog, Webstores scaffold, Billing Rules candidate, Pricing Engine reference, Upload Validation, Order Item Rules, Quotes/Orders/Items rich shapes.
- FEB (EXT): InvoiceService, PaymentService, Payment model.
- ORIG (REF/PSI): object_storage.py (FSV), signatures.py (PSI), approvals.py (PSI), portal.py (PSI), Stripe patterns, forms/questionnaires patterns, employees/time-clock references.

## 16.14 Required Module Preflights

Customer portal, Employee portal, Signatures, Approvals, Public Forms/Questionnaires, Webstores (full donor analysis), Stripe Connect (financial-safety review), Wrap Lab portal projection, Inventory, Vendors, Purchasing, Payroll, Reports, Analytics, AI Assistant, AI Tools per-tool, Marketing site, Platform Admin.

## 16.15 Locked Decisions

- Repository roles.
- Terminology.
- Money representation factual finding (cents commerce / dollars config — observed).
- Repo policy (no deletion of donors before final commercial completion).
- Portal tokens NEVER interchangeable with staff JWTs.
- No parallel domain systems.
- No base64-in-Mongo.
- No AI system autonomously alters money/messages/documents.
- Sendgrid + Stripe webhook signature verification mandatory.
- Tenant isolation mandatory.

## 16.16 Owner-Approved Decisions in This Register

- Founder direction (Part 7B.1).
- Webstores add-on + standalone mode (Part 5).
- Wrap Lab add-on mode (Part 5); standalone conditional pending preflight.
- No customer/order limits.
- AI via credits, not by removing basic functionality.
- Navigation direction (Part 3.1 LOCKED as final direction).
- Marketing site + Public pricing as public routes.

## 16.17 Remaining Owner Decisions

See Part 13 open register. 27 decisions enumerated; ~15 marked REQUIRES OWNER DECISION.

## 16.18 Commercial-Release Blockers

Every unchecked item in Part 15 is a blocker. Highest-impact blockers: Stripe integration, Portal auth, Webstores end-to-end, AI credit ledger, tax snapshot, JWT+bypass rotation, permission matrix completeness.

## 16.19 Highest Risks

(Cross-reference Source Map Part 9 top-30 register.) Highest 5:
1. `AUTH_DEV_BYPASS=true` shipping to production.
2. JWT dev secret shipping to production.
3. Job/JobTicket terminology contamination during donor ports.
4. Stripe integration without webhook signature verification + replay handling.
5. AI cost blowup without per-tenant credit metering.

## 16.20 Systems That Must Not Be Rebuilt

Pricing Foundation & Calculator; Idempotent Convert-to-Order; SendGrid Email; Object Storage + Attachments; Audit helper; Sequence generator; Customer/Order/Invoice basic CRUD; Design system (shadcn/ui + Tailwind); Cross-tenant isolation; AppShell + permission-gated nav.

## 16.21 Systems Requiring Targeted Replacement

Invoice status → dual status (FEB EXT). Payment history + reconciliation (FEB EXT). Work Orders → `production_required` gate (REB REF). Quotes → line items + expiration + revisions (REB REF). Order Items → 40+ fields + pricing snapshots (REB REF). Settings framework (REB REF). Notifications framework (REB REF). Permissions catalog (REB REF).

## 16.22 Systems Requiring New Implementation

Portal Auth (F12). Background Jobs (F10). Feature Entitlements (F9 — REB spec + new build). Global Search. Custom Report Builder. Tax provider integration boundary. SMS/MMS module. AI credit ledger (new atop REB catalog).

## 16.23 Systems to Remove or Deprecate

`db.jobs` and every Job-domain model/route/collection. ORIG monolithic App.js. ORIG giant pricing files. ORIG `routes/backup.py`, `routes/dev.py`. ORIG `PortalPreview.js`, `LegacyJobRedirect.js`. REB `PreviewEnvelope` + preview-user impersonation defaults. FEB `models/jobs.py` + Job-domain routes. MVP `dashboard:read` permission.

## 16.24 Final Recommended Checkpoint Groups

Group A (Product Rules & Security) → Group B (Shared Platform Foundations) → Group C (Core Money & Order Pipeline) → Group D (Document & Customer Workflow) → Group E (Inventory, Purchasing, Finance, and Reporting) → Group F (Team & Workflow) → Group G (Add-ons: Webstores + Wrap Lab) → Group H (AI + Platform + Commercial Systems).

## 16.25 Enough Scope Evidence for Master Build Plan?

**YES for scope, evidence, terminology, module inventory, add-on boundaries, reuse policy, never-again register, portal auth direction, permission catalog, code-organization, checkpoint groups, and commercial-release gate.**

**PARTIAL for exact commercial values** — specific pricing, credit amounts, transaction fees, expiration policies, cost caps, and provider-model choices remain REQUIRES OWNER DECISION and must be resolved during Prompt 4 (final master build plan).

---

# FINAL REQUIRED CONCLUSION

## **SCOPE COMPLETE — OWNER DECISIONS REQUIRED BEFORE MASTER BUILD PLAN**

### Decisions resolved automatically from existing owner instructions

- SIGNGUY-MVP is the permanent commercial product (not disposable MVP).
- Canonical terminology (Order / Order Item / Work Order / Work Order Summary / etc.); Job-domain terms prohibited.
- Donor repositories remain read-only references throughout the build; no deletion until final commercial completion.
- Webstores available as add-on AND standalone.
- Wrap Lab available as add-on; standalone conditional on preflight.
- Founders receive complete platform + Webstores + Wrap Lab + defined AI credits + 1-week limited-AI free trial.
- No artificial customer or order limits.
- No feature tiers cripple normal shop operations.
- Advanced AI is controlled via credits, not by removing basic functionality.
- One shared multi-tenant backend for all product boundaries.
- No parallel domain systems, no duplicated Customer/Order/Payment/File/User/Audit.
- Portal tokens NEVER interchangeable with staff JWTs.
- Object storage private by default; no Base64-in-Mongo.
- Webhook signature verification mandatory (SendGrid + Stripe).
- Payment idempotency mandatory; overpayment reject; controlled void with reason.
- Audit logging mandatory on every write.
- Collapsible left sidebar with side flyouts (LOCKED): Home / Shop Operations / Business & Finance / Team & Workflow / Creative Studio / (divider) / Control Center / Help & Community. Portals + Public systems separately-routed.

### Decisions requiring explicit owner approval (Prompt 4)

Refer Part 13 Open Decision Register — 27 numbered decisions. Highest-priority for master build plan:
1. Money policy ratification.
2. Permission catalog approval.
3. Repository-class pattern for new modules.
4. SendGrid fail-closed production behavior.
5. `SIGNGUY-AI-OS` archive timing.
6. Portal authentication mode.
7. Sales-tax strategy.
8. Commercial pricing values (subscriptions, credit packs, transaction fees, founders promo, free-trial, setup fees, grace period).
9. AI provider/model choices + cost caps + expiration.
10. SMS provider selection.
11. Report-builder scope.
12. Platform-admin impersonation policy.
13. Customer portal payment methods.
14. Employee portal payroll visibility.
15. Final internal checkpoint order (Groups A–H recommended).

### Scope conflicts corrected

- Money representation contradiction — resolved: MVP already stores commerce in cents / config in dollars (FSV). Ratification is a separate owner decision.
- REB `billing_rules.py` reclassified from canonical to candidate.
- REB role upgraded from "spec only" to "architecture reference + working-scaffold donor".
- ORIG role refined from "reference only" to "feature discovery + targeted donor for specific FSV files".
- Founders promo redemption cap (25 in REB candidate) conflicts with "first 50 founders" direction — surfaced for reconciliation in Prompt 4.
- "Deferred by MVP scope" language removed everywhere — all gaps are permanent-product build-outs.

### Features confirmed as required before commercial release

Every module in Part 4 marked REQ or REQ-DEP. Every portal in Part 4.7. Every Foundation in Part 4.1. Every Add-on module in Part 4.2, Part 4.7, Part 4.8 that is required for founder launch. Every gate in Part 15.

### Features removed or deprecated

- `db.jobs`, `Job`, `JobItem`, `JobTicket` domain: REMOVED.
- ORIG monolithic App.js, giant pricing files, dev/backup routes, `PortalPreview.js`, `LegacyJobRedirect.js`: REMOVED.
- REB `PreviewEnvelope` + preview-user impersonation defaults: REMOVED (sanitize on port).
- MVP `dashboard:read` permission: DEPRECATED.
- Base64-in-Mongo file storage: PROHIBITED.

### Final recommended checkpoint groups

Group A → B → C → D → E → F → G → H (see Part 14). Master build plan may rename, combine, divide, or reorder.

### Exact inputs the final master build plan must use

- This document (`/app/SIGNGUY_AI_FINAL_SCOPE_AND_DECISION_REGISTER.md`).
- `/app/SIGNGUY_AI_FEATURE_READINESS_MATRIX.md`.
- `/app/SIGNGUY_AI_REPOSITORY_AND_ARCHITECTURE_SOURCE_MAP.md`.
- `/app/memory/AGENT_INSTRUCTIONS.md`.
- Owner decisions resolved during Prompt 4 (from Part 13).
- Module preflight outputs (during Groups C–H).

### Whether Prompt 4 may proceed

**YES — Prompt 4 may proceed to draft the final master build plan** on the LOCKED and OWNER-APPROVED items above. Prompt 4 MUST also collect owner ratification on each REQUIRES-OWNER-DECISION item in Part 13 before that item's downstream module is scheduled into a checkpoint that depends on it. No code, no migration, no route or model creation may occur inside Prompt 4 itself.

---
