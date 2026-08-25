# SIGNGUY MVP — Business & Finance Feature Audit

**Repository:** `dnblack323/SIGNGUY-MVP`  
**Audited branch:** `main`  
**Code baseline:** `66c0c49fb6450268ad784c7a5e291257442b3c20`  
**Audit date:** August 16, 2026  
**Scope:** Business & Finance, including directly connected invoice, payment, expense, tax, reporting, pricing, inventory, purchasing, and vendor capabilities.

This is a code-level audit of the current repository, not a product-roadmap interpretation. A feature is credited only when the repository contains working UI, backend behavior, or a clearly wired integration. Backend-only and unreachable UI features are called out separately so they are not mistaken for usable app features.

## Rating and AI legend

| Score | Classification | Meaning |
|---:|---|---|
| 5 | Standout / advanced | Deep, production-shaped workflow with safeguards, history, edge-case handling, and polished access through the app. |
| 4 | Advanced | Substantial end-to-end capability; valuable and differentiated, but with identifiable completeness or polish gaps. |
| 3 | Solid | Real, useful workflow with meaningful backend and UI support; not yet deep or complete. |
| 2 | Basic | Narrow or incomplete workflow; significant manual steps, missing surfaces, or weak integration. |
| 1 | Foundation only | Models/services or isolated UI exist, but the feature is not practically usable from the normal app. |
| 0 | Placeholder / absent | Named, planned, mocked, or implied, but not implemented as a usable feature. |

**AI labels**

- **No:** deterministic business logic; no AI service is necessary.
- **Optional:** the core feature works without AI, with an optional AI-assisted action.
- **Required:** the workflow depends on an AI model or provider.
- **Planned / inactive:** an AI-shaped contract or UI concept exists, but no live AI provider is connected.

## Executive scorecard

| Category | Usable app score | Backend depth | AI | Current state |
|---|---:|---:|---|---|
| Finance Overview | **4/5 — Advanced** | 4/5 | No | Strong multi-basis dashboard with profit-coverage warnings and explicit limitations. |
| Invoices | **4/5 — Advanced** | 4/5 | Optional | Mature issue/edit/void/reconcile flow; invoice creation is order-driven and document output is limited. |
| Payments | **3/5 — Solid, mixed** | 5/5 | No | Excellent payment/refund domain logic, but no central Payments area and Stripe UI is still test-oriented. |
| Expenses | **3/5 — Solid** | 4/5 | No | Useful operational expense register; receipt, category, linkage, recurring, and AP workflows are incomplete in UI. |
| Taxes | **3/5 — Solid** | 4/5 | No | Good tax snapshot reporting and exemption model; mostly read-only and not a filing/remittance system. |
| Reports & Analytics | **4/5 — Advanced foundation** | 4/5 | No | Broad report catalog, safe custom builder, saved reports, exports, and manual scheduling; several promised advanced functions remain blocked or manual. |
| Pricing Defaults & Calculator | **4/5 — Advanced foundation** | 4/5 | No; advisory planned/inactive | Deep pricing setup and calculation engine, but category/method readiness is uneven and this section is misplaced in current navigation. |
| Supply Center | **2/5 — Basic** | 3/5 | No | Searchable synthetic supplier catalog only; no real connector, comparison/cart/PO workflow in the visible page. |
| Inventory | **1/5 — Foundation in the app** | 4/5 | No | Substantial backend and a page component exist, but the page is not routed from the application. |
| Purchase Orders & Vendors | **1/5 — Foundation in the app** | 4/5 | No | Strong domain services and detail components exist, but the pages are not routed and no real supplier connector is present. |
| Standalone Business Analytics | **0/5 — Absent** | — | No | There is no separate Business Analytics route or page; some intended value is covered by Finance and Reports. |

### Overall assessment

The strongest Business & Finance capabilities are the **financial dashboard, invoice/payment domain model, report catalog, safe custom report execution, and pricing foundation**. The repository shows careful work around tenant isolation, integer-money storage, immutable financial history, reconciliation, idempotency, and limitations disclosure.

The largest issue is not lack of backend code; it is **product integration**. Several advanced finance-adjacent modules are hidden, unreachable, or placed in the wrong section. Payments has no dedicated ledger page. Supply Center is hidden from navigation. Inventory, purchase-order, and vendor pages exist in source but are not routed. Pricing Defaults is currently under Business & Finance even though the previously finalized information architecture placed it in Control Center.

No core Business & Finance workflow currently requires AI. The one invoice AI action is optional, and the pricing advisory endpoint is an inactive contract that always reports unavailable rather than calling a live model.

## Current Business & Finance navigation

The current navigation declares:

1. Overview — `/finance`
2. Invoices — `/invoices`
3. Expenses — `/expenses`
4. Taxes — `/tax`
5. Reports — `/reports`
6. Pricing Defaults — `/pricing-foundation`

Important structural findings:

- There is **no Payments navigation item or global Payments page**. Payments are handled inside an invoice.
- `/supply-center` is routed but **not listed in the navigation**.
- Inventory, purchase-order list/detail, and vendor-detail components exist, but their routes are **not registered in the main app**.
- There is **no standalone Business Analytics page**.
- Pricing Defaults is usable but **misclassified here** relative to the finalized product structure; it belongs in Control Center.

## 1. Finance Overview

**Rating: 4/5 — Advanced**  
**AI: No**

### Implemented features

#### Date and basis controls

- Custom **Date From** and **Date To** filtering.
- Explicit basis descriptions so users can see that different cards use different accounting events.
- Labels distinguish invoice-issued revenue, cash received, stored tax snapshots, and operational expenses.
- Tenant-aware and timezone-aware service logic.

#### Financial KPI cards

- **Invoice revenue:** issued invoice totals in the selected window; accrual-style operational measure.
- **Payments received:** confirmed payment amounts in the selected window; cash-basis measure.
- **Refunds:** shown separately instead of silently netting them away.
- **Outstanding accounts receivable:** unpaid and partially paid invoice balances.
- **Expenses:** active operational expenses in the period.
- **Tax collected:** based on tax amounts stored on invoices.
- **Estimated gross profit:** combines recognized revenue with available cost snapshots.
- **Estimated net operating result:** invoice revenue minus active expenses and refunds, clearly identified as a mixed-basis operational estimate rather than formal accounting income.
- Supporting backend metrics include average order value / average invoice value and aging-style receivable calculations used by reporting services.

#### Charts and breakdowns

- Monthly **revenue trend**.
- Monthly **payments trend**.
- Monthly **expense trend**.
- **Top customers by revenue**.
- **Payment method breakdown**.

#### Cost and profit integrity

- Uses order cost snapshots, linked operational expenses, and receiving/material costs where available.
- Counts missing cost records and exposes incomplete coverage.
- Does not silently treat absent costs as reliable zero-cost jobs.
- Displays limitations and basis notes directly in the dashboard experience.

### Why it is advanced

The dashboard is stronger than a typical MVP total-card screen because it treats revenue, cash, refunds, tax, expenses, and profit as different concepts. Its most important advanced behavior is **coverage-aware profitability**: it warns when cost data is incomplete instead of presenting false precision.

### Limitations and missing features

- Not a formal profit-and-loss statement.
- No balance sheet.
- No cash-flow statement.
- No general ledger or chart of accounts.
- No bank feeds or bank reconciliation.
- No budgeting, forecasting, budget-versus-actual, or scenario planning.
- No period close, journal entries, accrual adjustments, or accounting lock dates.
- Mixed-basis estimated net operating value is useful operationally but must not be represented as GAAP accounting income.

## 2. Invoices

**Rating: 4/5 — Advanced**  
**AI: Optional** — only the Payment Email shortcut can hand context to Studio; invoice operations themselves are deterministic.

### Implemented features

#### Invoice lifecycle

- One invoice per order, enforced by tenant/order uniqueness.
- Order-driven invoice creation.
- Separate **document status** and **financial status**:
  - Document: draft, issued, void.
  - Financial: unpaid, partial, paid, refunded, or voided, derived from payment state.
- Draft invoice editing for title, total, due date, description, and notes.
- Invoice issuance.
- Invoice voiding with required reason.
- Void prevention when net payment activity makes voiding unsafe.
- Issued, due, and activity metadata.

#### Invoice list

- Invoice register with status filtering.
- Customer/order context and monetary totals.
- Legacy-style list filters include draft, sent, viewed, partially paid, paid, overdue, and void.
- Direct navigation to invoice detail.

#### Invoice detail

- Detail, payments, and activity views.
- Paired document and financial status badges.
- Total paid, total refunded, and remaining balance.
- Payment history and reconciliation.
- Internal audit/activity trail.
- Compose-email action.
- Optional **Payment Email** action that opens Studio with invoice/payment context.

#### Financial safeguards

- Integer-cent money representation.
- Backend-derived payment state rather than trusting editable status fields.
- Tenant isolation.
- Reconciliation based on confirmed payment and refund records.

### Why it is advanced

The dual-status model avoids a common invoice design error: conflating whether a document is issued with whether money was received. The void protection, immutable payment history, and reconciliation model make this substantially more than a CRUD invoice screen.

### Limitations and risks

- There is no visible **New Invoice** form in the invoice register; the intended path is through an order.
- Invoice editing is total-oriented rather than a full standalone invoice line-item editor.
- No polished invoice PDF preview/download workflow was found in the invoice detail surface.
- No centralized hosted payment-link management experience was found.
- List filters still use legacy labels such as sent/viewed/partially_paid while detail uses the newer paired status model; this can create inconsistent mental models.
- The AI Payment Email action is an optional handoff, not an autonomous collections workflow.

## 3. Payments

**Overall rating: 3/5 — Solid but uneven**  
**Backend rating: 5/5 — Standout**  
**Staff/customer UI rating: 2/5 — Basic / test-oriented**  
**AI: No**

### Implemented backend features

#### Unified payment records

- Manual and Stripe payments use one canonical Payment collection.
- Supports multiple and partial payments on the same invoice.
- Maintains status, method, reference, notes, dates, external IDs, and reconciliation metadata.

#### Manual payments

- Methods include cash, check, external card, external bank transfer, and other.
- Full or partial payment entry.
- Reference number and notes.
- Paid-on date.
- Idempotency-key handling.
- Race-safe overpayment prevention.
- Manual-payment void with required reason.
- Voiding preserves the original record rather than deleting history.

#### Stripe payment intents and confirmation

- Creates pending Stripe payment intent records.
- Confirms through signed webhook processing.
- Preserves failed records when Stripe is unavailable.
- Webhook signature verification.
- Feature-flagged Stripe behavior.
- Payment secrets are held in memory and are not intentionally rendered into persistent UI state.

#### Refunds

- Stripe refund workflow.
- Full and partial refunds.
- Refund reason.
- Idempotency protection.
- Webhook confirmation.
- Pending and confirmed refund accounting.
- Parent payment status updates to partial-refund or refunded.

#### Reconciliation

- Paid, refunded, and balance calculations.
- Pending, failed, and voided payments are excluded from confirmed-cash totals.
- Payment history is append-oriented and auditable.
- Invoice financial status is recalculated from payment state.

### Implemented UI features

- Record manual payments from invoice detail.
- Select manual payment method.
- Enter reference, notes, amount, and payment date.
- View payment history on an invoice.
- Void eligible manual payments.
- Start Stripe payment flow from staff invoice context.
- Customer portal payment page with customer-scoped invoice protection.
- Portal prevents payment of void, paid, or overpaid invoices.
- Customers can see manual payment history read-only.

### Major limitations

- No global **Payments** page, payment ledger, deposit register, or reconciliation workspace.
- Staff must begin from an individual invoice.
- The staff Stripe dialog displays a placeholder for secure payment fields and includes a **test-only simulated confirmation** action.
- The customer portal also uses a development confirmation simulation instead of a mounted production Stripe Payment Element.
- No payout/deposit matching against bank activity.
- No chargeback/dispute-management workspace.
- No terminal, card-present, or integrated POS workflow found.
- No payment plans, automatic installments, autopay, or dunning automation.

### Assessment

This is the section with the largest backend/UI score gap. The underlying payment state machine, refund handling, idempotency, and audit preservation are among the most advanced finance capabilities in the repository. However, a normal user does not yet receive a production-grade card-payment experience or a finance-wide payment operations page.

## 4. Expenses

**Rating: 3/5 — Solid**  
**Backend depth: 4/5**  
**AI: No**

### Implemented features

#### Expense records

- Sequential expense number.
- Expense date.
- Category.
- Vendor ID and vendor-name snapshot.
- Description.
- Amount, tax, and calculated total in integer cents.
- Payment method:
  - Cash
  - Check
  - Card
  - ACH
  - Bank transfer
  - Wire
  - Other
- External/reference number.
- Internal notes.

#### Tax and deductibility metadata

- Deductibility classifications:
  - Unknown
  - Fully deductible
  - Partially deductible
  - Non-deductible
  - Personal
  - Capitalized
  - Not applicable
- Category label snapshots preserve historical meaning even if a category is renamed later.

#### Linkage fields

- Purchase order reference.
- Customer reference.
- Order reference.
- Project reference.
- Recurring flag/reference foundation.

#### Lifecycle and audit behavior

- Active, archived, and voided states.
- Non-destructive archive, restore, and void behavior.
- Tenant scoping.
- Filters for state, category, vendor, purchase order, customer, order, and date.

#### Expense categories

- Seeded system categories.
- Custom category creation.
- Renameable display label backed by stable key.
- Archive and unarchive.

#### Receipts and supporting files

- File-record attachment support.
- Attachment roles include receipt, vendor invoice, statement, and other supporting document.
- Attachment archival support.

#### Current Expenses page

- Create expense with date, category, description, amount, tax, payment method, deductible status, reference, and internal notes.
- Table with number, date, category, vendor, description, amount, tax, total, payment method, and state.
- State-oriented viewing.
- Archive, restore, and void actions.

### Limitations

- No full expense-detail or edit workflow in the visible page.
- Receipt upload and attachment management are not exposed in the current Expenses UI.
- Category administration is not exposed even though backend CRUD exists.
- Vendor, purchase-order, order, customer, and project linkages are not offered in the create form.
- Recurring metadata exists, but there is no recurrence generator, schedule, or automated posting flow.
- No expense approval chain, manager review, spending policy, card feed, OCR, or duplicate-receipt detection.
- No mileage or per-diem workflow.
- This is explicitly operational expense tracking, **not full accounts payable**.
- No vendor bill lifecycle, payment terms, bills due, aging, vendor credits, three-way match, or bill-payment execution.

## 5. Taxes

**Rating: 3/5 — Solid reporting foundation**  
**Backend depth: 4/5**  
**AI: No**

### Implemented features

#### Tax collection reporting

- Date-range tax report.
- Total tax collected from tax snapshots stored on invoices.
- Tax collected by jurisdiction.
- Jurisdiction grouping prefers the invoice jurisdiction snapshot and otherwise uses customer state information.
- Invoice count, subtotal, and tax totals per jurisdiction.

#### Manual tax override monitoring

- Reports invoices using manual tax overrides.
- Shows override reason.
- Counts override activity.

#### Customer exemption model

- Customer-linked tax-exemption records.
- Jurisdiction.
- Reference/certificate identifier.
- Reason.
- Effective start and end dates.
- Notes.
- Archive state.
- Tenant isolation.
- Backend list, upsert, archive, and exemption-check operations.

#### Exemption auditing

- Exempt-customer report.
- Flags cases where an exempt customer was still charged tax.
- Shows invoice count, subtotal, and tax charged.

#### Current Taxes page

- Date From and Date To.
- KPI cards for tax collected, manual overrides, and exempt-customer count.
- Tabs:
  - By Jurisdiction
  - Exempt Customers
  - Exemption Records
  - Manual Overrides
- Detailed tables for jurisdictions, customers, exemption records, and invoice override reasons.

### Why it is solid

The use of invoice snapshots is important: historical tax reports do not silently change when a customer or tax configuration changes later. Exemption discrepancy reporting also provides a useful audit control.

### Limitations

- The Taxes page is predominantly read-only.
- No create/edit/archive exemption form is exposed in the current UI.
- No tax-rate table or jurisdiction-rule administration was found in this section.
- No tax nexus management.
- No filing calendar, due-date reminders, return preparation, remittance, payment, or electronic filing.
- No automated connection to a tax provider.
- No tax liability reconciliation to a general ledger.
- No dedicated tax-package export on the Taxes page.
- Stored invoice tax reporting is not the same as a complete sales-tax compliance system.

## 6. Reports & Analytics

**Rating: 4/5 — Advanced reporting foundation**  
**AI: No**

### A. Report center organization

Current report tabs:

- Overview
- Financial
- Operations
- Customers & Sales
- Webstores
- Materials & Purchasing
- Team & Labor
- Wrap Lab
- Custom Builder
- Saved
- Scheduled
- Exports

The breadth is notable: Business & Finance acts as a reporting hub for data owned by several other product sections.

### B. Standard report catalog

#### Executive and trend reports

- Executive summary.
- Overview trends.

#### Finance reports

- Finance summary.
- Top customers.
- Invoice aging.
- Payments collected.
- Payment-method mix.

#### Tax reports

- Tax by jurisdiction.
- Manual tax overrides.
- Exempt customers.

#### Expense reports

- All expenses.
- Expenses by category.
- Expenses by vendor.

#### Order and quote reports

- Orders by status.
- Order detail.
- Order profitability.
- Quotes by status.
- Quote follow-up.
- Customer performance.

#### Inventory and purchasing reports

- Inventory on hand.
- Low stock.
- Inventory movements.
- Material cost history.
- Inventory value.
- Purchase orders by status.
- Vendor spend.

#### Webstore reports

- Sales by store.
- Product performance.
- Ledger summary.

#### Team, labor, and compliance reports

- Hours by employee.
- Time off.
- Certification matrix.
- Expiring certifications.
- Incomplete training.
- Overdue training.
- Equipment access.

Payroll/labor reporting can appear here, while payroll execution belongs in Team & Productivity.

#### Wrap Lab reports

- Project performance.
- Material use.

### C. Standard report execution

- Tenant-scoped, live data reads.
- Date filtering.
- Report-mode controls where supported.
- Metadata describing data source, date basis, calculation basis, and limitations.
- Drill-down links where a valid route exists.
- No source-record mutation during report runs.

### D. Custom Report Builder

#### Supported capabilities

- Allowlisted datasets.
- Allowlisted fields.
- Date ranges.
- Allowlisted filters.
- Grouping.
- Sorting.
- Grouped money sums.
- Dataset-aware column definitions.

#### Available data families

The allowlisted dataset registry covers expenses, purchase orders, invoices, customers, quotes, orders, order items, payments, work orders, webstores, buyer orders, webstore products, ledgers, inventory items, materials, purchase-order lines, employees, time entries, timesheets, payroll snapshots, wrap projects, and panel plans.

#### Security controls

- Rejects tenant ID as a user-selectable field.
- Rejects unapproved fields.
- Rejects Mongo-shaped or injection-like filter objects.
- Rejects invalid group-by requests.
- Uses server-side allowlists instead of accepting arbitrary collection queries.

### E. Saved reports

- Save standard or custom report definitions.
- Private, shared-user, and shared-role visibility concepts in the data model/backend.
- Run a saved report against fresh authorized data.
- Duplicate a shared or owned report.
- Archive and restore in backend.
- Shared users can run and duplicate without mutating the original.

#### Saved-report UI gaps

- Uses basic/default naming flows.
- No complete visibility and sharing-control editor in the frontend.
- No polished rename/update-definition workflow.
- Archived records do not have a visible restore action in the current Saved interface.

### F. Exports

- CSV export.
- XLSX export.
- PDF export.
- Print-format export.
- Export history.
- CSV spreadsheet-formula injection protection.

#### Export quality limitations

- XLSX generation is functional but minimal.
- PDF output is a basic text/table document rather than a polished branded financial report.
- Print output is a downloaded plain-text artifact rather than a true browser print layout.
- Specialized accounting, payroll, and tax CSV formats are explicitly blocked.

### G. Scheduled reports

#### Implemented foundation

- Schedule model supports daily, weekly, monthly, pay-period, and event-triggered cadence concepts.
- Delivery format and recipient user/email fields.
- Frontend can create a schedule from a saved report.
- Manual **Run Now**.
- Durable run/export history.
- Permission revalidation at run time.
- Prevention of duplicate concurrent execution.

#### What is not production-complete

- No background scheduler continuously executes due schedules.
- No production email delivery; current evidence records test/no-email delivery.
- No automatic retry and delivery recovery.
- No full timezone-window execution behavior.
- The visible scheduler is closer to a durable manual-run foundation than true scheduled distribution.

### H. Missing and blocked report-builder functions

- The visible **Search reports** input is not connected to filtering state and is therefore nonfunctional.
- Calculated fields are not implemented.
- Period-over-period comparisons are not implemented.
- Dashboard-widget publishing is blocked.
- Specialized accounting/payroll/tax exports are blocked.
- Definition versioning is not complete.
- Complete report-definition audit history is not present.
- Automated retry/delivery is not implemented.
- Detailed webstore payout reports are blocked.
- Deep Wrap Lab workflow reports are blocked.
- Payroll tax-filing exports are blocked.

### Assessment

This is an advanced MVP reporting architecture because it combines a large standard catalog with a server-safe custom builder and persistent saved/export/schedule models. It should not yet be described as a fully finished BI or report-distribution platform. Search, calculations, comparisons, widgets, polished outputs, and real scheduled delivery remain important gaps.

## 7. Pricing Defaults & Pricing Calculator

**Feature-depth rating: 4/5 — Advanced foundation**  
**Operational readiness rating: 3/5 — Needs real-shop validation**  
**AI: No for core pricing; Planned / inactive for pricing advisory**

### Information-architecture finding

Pricing Defaults is currently listed under Business & Finance. The finalized product organization previously placed pricing configuration in **Control Center**. It is a real and substantial capability, but it should not occupy a primary Business & Finance slot.

### A. Shop-wide pricing defaults

- Design labor rate.
- Production labor rate.
- Installation labor rate.
- Overhead percentage.
- Target margin.
- Minimum order.
- Deposit percentage.
- Default markup.
- Default waste percentage.
- Rush percentage.
- Editable starter values.

### B. Category setup

Supported category families include:

- Banners
- Rigid signs
- Cut vinyl
- Digital print
- Vehicle graphics
- Apparel
- Services
- Promotional products
- Custom

Features:

- Per-category setup status.
- Category setup wizard.
- Reset to starter defaults.
- Method availability.
- Primary-method selection.
- Simple and Advanced setup modes.
- Preview and selectively apply configuration suggestions.

### C. Grouped Pricing Quiz

- Job type.
- Typical duration.
- Crew size.
- Material estimate.
- Customer charge.
- Floor/minimum.
- Included items.
- Difficulty.
- Shows its math.
- Lets the user choose which suggestions to apply.
- Save draft and resume later.
- Review later.
- Skip optional steps.

This is deterministic assisted setup, not AI-dependent analysis.

### D. Materials & Pricing Profiles

- Canonical material creation.
- Material search.
- Archive and restore.
- Material categories.
- Current cost.
- Pricing-profile unit bases:
  - Per square foot
  - Per unit
  - Per linear foot
  - Per garment
  - Other
- Normalized cost basis.
- Waste percentage.
- Markup.
- Margin.
- Sell rate.
- Minimum sell price.
- Applicable product categories.
- Notes.

### E. Pricing Components

- Reusable fees and charges.
- Examples include setup fee, design fee, file cleanup, permit fee, and outsourced service.
- Flat-amount or percentage charge.
- Notes.
- Archive and restore.

### F. Saved / Common Items

- Category assignment.
- Pricing methods:
  - Tier pricing
  - Per piece
  - Flat fee
  - Manual
- Exact quantity tiers.
- Material association.
- Reusable components.
- Notes.
- Quick select.
- Save variation.
- Edit, archive, and restore.

### G. Pricing Calculator

- Category, quantity, dimensions, unit, material, design, installation, reusable components, and manual-price inputs.
- Multiple possible calculation methods.
- Banner methods include square-foot plus add-ons, cost-plus, target-margin, materials/labor/overhead, and minimum-charge behavior.
- Displays method results.
- Displays unavailable methods with reasons.
- Warnings and errors.
- Tier preview.
- Category detail.
- Simple setup preview/apply.
- Advanced allowed-method toggle and primary-method selection.

### H. Saved calculations and shared engine

- Save calculation name and notes.
- Search saved calculations.
- Category and archive-state filtering.
- Edit metadata.
- Duplicate.
- Archive and restore.
- Recalculate.
- Use saved result.
- Warn when current calculated price differs from saved price.
- Shared pricing engine is reused in Quote and Order line items.
- Immutable pricing snapshots preserve the price basis used at the time of a transaction.

### Limitations and risk areas

- Pricing-method availability is uneven by category.
- Several non-banner categories can report unavailable methods until configuration is complete.
- Unit handling, category defaults, and method readiness remain high-risk areas and require real sign-shop test cases.
- The repository’s starter setup intentionally defers laminates, apparel catalog depth, hardware, equipment, advanced labor rules, detailed digital-print multipliers, and external market benchmarks.
- The calculator should be rated on both engine depth and configured output correctness; a sophisticated engine can still produce poor results if defaults or unit mappings are incomplete.

### AI pricing advisory status

- A pricing-advisory backend contract exists.
- It does **not call a live AI model or external provider**.
- Requests currently return an unavailable status.
- Local/regional pricing comparison, confidence scoring, and AI market guidance should therefore be classified as **planned / inactive**, not implemented.
- Optional Studio pricing/profitability assistance elsewhere does not make the core calculator AI-dependent.

## 8. Supply Center

**Usable app rating: 2/5 — Basic**  
**AI: No**

### Implemented visible features

- Routed page at `/supply-center`.
- Supplier catalog table.
- Search by description, SKU, brand, or family.
- Category, vendor, account price, and status display.
- Synthetic demonstration catalog with roughly 80 SKUs across four test vendors in development/test data.
- Clear demo/synthetic-data messaging.

### Limitations

- The route is not present in normal navigation.
- No real supplier account or production connector is configured.
- No visible shortage-recommendation workflow.
- No complete side-by-side supplier price comparison experience.
- No cart or purchase-order builder in the visible page.
- No ordering/checkout flow.
- The current supplier adapter is synthetic/test-only.

## 9. Inventory

**Usable app rating: 1/5 — Foundation only because it is unreachable**  
**Backend depth: 4/5 — Advanced**  
**Component depth: 3/5 — Solid**  
**AI: No**

### Implemented backend features

- Tenant-scoped material records.
- Inventory locations.
- Inventory items.
- Immutable inventory movements.
- Increase and decrease adjustments.
- Prevention of negative stock.
- Idempotent receiving.
- Reservations and release of reservations.
- Physical counts with expected and observed quantities.
- Transfers represented as paired movements.
- Low-stock detection.
- Unit-conversion support, including roll-to-square-foot scenarios.
- Material cost history tied to receiving.

### Existing Inventory page component

- Items tab.
- Materials tab.
- Movements tab.
- Locations tab.
- Physical-count dialog.
- Transfer dialog.
- Material search.
- Material cost and low-stock information.
- Reserved-quantity information.

### Availability and UX gaps

- The Inventory page is not imported/routed in the main application.
- It is not in Business & Finance navigation.
- Some component links point to routes that do not exist in the main router.
- No complete create/edit material or location administration workflow was confirmed in the page.
- Some dialogs rely on raw material IDs, which is not production-grade selection UX.

### Assessment

Inventory should not be marketed as a usable main-section feature yet. The backend is materially advanced, but the application shell does not expose it. This is a wiring and workflow-completion problem more than a missing-domain problem.

## 10. Purchase Orders & Vendors

**Usable app rating: 1/5 — Foundation only because it is unreachable**  
**Backend depth: 4/5 — Advanced**  
**Component depth: 3/5 — Solid**  
**AI: No**

### Vendor and supplier data

- Vendor records.
- Vendor warehouses.
- Supplier products.
- Vendor-to-material mappings.
- Preferred/active vendor status.
- Connector/account metadata.
- Synthetic test-adapter seeding.

### Supply and sourcing services

- Supplier catalog search.
- Shortage recommendations.
- Compatibility grouping.
- Vendor-grouped cart concepts.
- Cart-to-purchase-order creation in backend services.

### Purchase-order lifecycle

- Draft purchase orders.
- Purchase-order lines.
- Backend totals.
- Freight.
- Submit with confirmation and idempotency.
- Supplier activity log.
- Cancel with reason.
- Tracking refresh.
- Partial and full receiving.
- Over-receive prevention.
- Idempotent receiving.
- Receiving creates inventory movements.
- Receiving updates material cost history and current material cost.
- PO-linked receiving history.

### Existing page components

#### Purchase-order list

- Purchase-order listing.
- Status information.
- Submit action.
- Cancel action.

#### Purchase-order detail

- Vendor summary.
- Cost totals.
- Line items.
- Receive per line and location.
- Fill remaining quantity.
- Receiving notes.
- Receiving history.
- Supplier history.
- Inventory-movement history.

#### Vendor detail

- Vendor identity.
- Preferred and active state.
- Connector/account information.
- Warehouses.
- Material mappings.
- Purchase-order history.

### Availability and completeness gaps

- Purchase-order list/detail routes are not registered in the main app.
- Vendor detail route is not registered.
- Existing component links point to unavailable routes.
- No polished visible UI to create a vendor or build a new purchase order was confirmed.
- Supply Center does not expose its backend cart-to-PO workflow.
- No real supplier connector is implemented; the available adapter is synthetic/test-only.
- No vendor bill, AP, payment, or three-way-match workflow.

## 11. Standalone Business Analytics

**Rating: 0/5 — Not separately implemented**  
**AI: No**

There is no Business Analytics route, navigation item, or dedicated page. Finance Overview and Reports cover many analytics use cases, including trends, profitability, customer performance, invoice aging, payments, inventory value, labor, and webstore activity. That overlap may make a separate page unnecessary, but the repository should not claim a distinct Business Analytics feature today.

## 12. AI dependency map

| Feature | AI status | What AI does today |
|---|---|---|
| Finance Overview | No | All calculations are deterministic. |
| Invoices | Optional | A Payment Email action can hand invoice context to Studio; core invoice flow does not depend on it. |
| Payments | No | Payment and refund logic uses deterministic backend and Stripe APIs. |
| Expenses | No | No AI/OCR/receipt classification is wired. |
| Taxes | No | Snapshot reporting and exemption checks are deterministic. |
| Reports & Custom Builder | No | Report definitions and aggregations use allowlisted server logic. |
| Pricing Defaults & Calculator | No | Quiz suggestions and price calculations are deterministic rules/math. |
| Pricing advisory | Planned / inactive | Contract exists, but no provider call is made; responses are unavailable. |
| Supply, Inventory, Purchasing, Vendors | No | Catalog, stock, PO, and receiving logic are deterministic. |
| Business Analytics | Absent | No standalone feature exists. |

**Bottom line:** AI is not required for any implemented core Business & Finance capability. The app should not market AI pricing intelligence as live based on the current repository.

## 13. Capabilities that are not implemented as complete Business & Finance features

The following should be treated as roadmap items or gaps, not current features:

- General ledger and chart of accounts.
- Double-entry bookkeeping.
- Journal entries and period close.
- Formal profit-and-loss, balance-sheet, and cash-flow statements.
- Bank feeds and reconciliation.
- Budgeting and forecasting.
- Full accounts payable and vendor bill payment.
- Expense approvals and corporate-card feeds.
- Automated recurring expenses.
- Dedicated global payment ledger and deposit reconciliation.
- Production Stripe Payment Element in the staff and portal flows.
- Chargeback/dispute operations.
- Tax-rate administration, nexus, filing, remittance, and provider integration.
- Production scheduled-report delivery.
- Calculated report fields and period comparisons.
- Dashboard widget publishing.
- Specialized accounting, payroll, and tax exports.
- Standalone Business Analytics.
- Real supplier connectors.
- Routed inventory, vendor, and purchase-order workspaces.
- Live AI pricing advisory or market benchmarking.

## 14. Recommended product-structure corrections

These are information-architecture and exposure corrections, not claims that the underlying modules must all remain in Business & Finance.

### Business & Finance should expose

1. Overview
2. Invoices & Payments
3. Expenses
4. Taxes
5. Reports & Analytics

A dedicated Payments view or combined **Invoices & Payments** workspace would close the largest visible finance-operations gap.

### Move or restore elsewhere

- Move **Pricing Defaults** to Control Center.
- Keep payroll execution in Team & Productivity; surface labor/payroll financial reporting in Reports.
- Put inventory, vendors, purchasing, receiving, and Supply Center in the product section chosen for shop/supply operations, but actually route and expose them.

### Highest-value implementation priorities

1. Replace simulated Stripe confirmation with production Payment Element integration in staff and portal flows.
2. Add a global Payments register with refunds, voids, method filters, deposit/reconciliation context, and invoice drill-down.
3. Route and navigation-enable inventory, purchase orders, and vendor detail—or remove/defer the orphaned UI until ready.
4. Expose expense receipts, category management, and entity linkages.
5. Add tax-exemption management UI.
6. Finish report search, calculated fields, comparisons, branded exports, and actual scheduled delivery.
7. Validate pricing methods, units, and starter defaults against real sign-shop scenarios before treating calculator output as production-ready.

## 15. Strongest features, by advancement

### Standout backend capabilities

- Payment/refund state, idempotency, webhook confirmation, and audit-preserving void/refund behavior.
- Tenant-safe custom report allowlists and filter-injection rejection.
- Inventory receiving and immutable movement/cost-history mechanics.

### Advanced end-to-end capabilities

- Finance Overview with explicit financial bases and profit-coverage warnings.
- Invoice lifecycle and reconciliation.
- Broad standard report catalog plus saved/custom/export foundations.
- Pricing Foundation, reusable components, saved/common items, and shared quote/order calculator engine.

### Solid but incomplete capabilities

- Operational expenses.
- Tax snapshot and exemption reporting.
- Saved-report and scheduling UI.
- Pricing configuration for categories beyond the best-supported methods.

### Foundations currently blocked by product wiring

- Supply Center.
- Inventory workspace.
- Purchase-order list/detail.
- Vendor detail.
- Real supplier integration.

## 16. Principal code evidence

The audit was based primarily on the current navigation/router, feature pages, routers, services, models, tests, and implementation evidence in these areas:

- `frontend/src/lib/navigation.js`
- `frontend/src/App.jsx`
- `frontend/src/pages/FinanceDashboardPage.jsx`
- `frontend/src/pages/InvoicesPage.jsx`
- `frontend/src/pages/InvoiceDetailPage.jsx`
- `frontend/src/pages/ExpensesPage.jsx`
- `frontend/src/pages/TaxReportsPage.jsx`
- `frontend/src/pages/ReportsPage.jsx`
- `frontend/src/pages/PricingFoundationPage.jsx`
- `frontend/src/pages/PricingCalculatorPage.jsx`
- `frontend/src/pages/SupplyCenterPage.jsx`
- `frontend/src/pages/InventoryPage.jsx`
- `frontend/src/pages/PurchaseOrdersPage.jsx`
- `frontend/src/pages/PurchaseOrderDetailPage.jsx`
- `frontend/src/pages/VendorDetailPage.jsx`
- Finance, invoice, payment, expense, tax, report, pricing, inventory, purchasing, and supplier backend routers/services/models and their focused tests.

## Final verdict

Business & Finance is an **advanced MVP foundation with uneven product exposure**. Finance Overview, invoices, payment-domain logic, reporting, and pricing contain real depth. Expenses and taxes are credible operational tools. The product is not yet a full accounting system, and it should not be positioned as one.

The most important distinction is between **implemented domain capability** and **usable product capability**. The repository contains advanced payment, inventory, purchasing, and vendor logic, but several of those workflows are hidden, unrouted, or test-only. Fixing navigation, route wiring, production Stripe UI, and report delivery would unlock more value than adding another large backend subsystem.
