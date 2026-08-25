# Business & Finance — Work Outline

This section should go through the same complete process used for Shop Operations. The existing Business & Finance feature audit is the starting record of what the code currently has.

## 1. Confirm what belongs in Business & Finance

- Keep financial ownership here: Invoices, Payments, Expenses, Taxes, Reports, financial dashboards, reconciliation, and financial analysis.
- Decide where vendors, purchasing, inventory value, accounts payable, and Supply Center functions belong.
- Keep employee timekeeping and operational payroll in Team & Productivity. Business & Finance should receive payroll cost totals and reports without owning employee pay workflows.
- Move Pricing Defaults and Pricing Foundation to Control Center. Business & Finance may show pricing and profit results, but it should not own the shop's configuration.
- Keep Order production work in Shop Operations while allowing authorized staff to see linked invoice and payment status.

## 2. Correct the sidebar module row

- Review the current Overview, Invoices, Expenses, Taxes, Reports, and Pricing Defaults tabs.
- Add or expose Payments as a real central workspace if the code supports it.
- Remove Pricing Defaults from this area after its Control Center destination is ready.
- Decide whether purchasing, vendors, inventory, and Supply Center need permanent modules, internal tabs, or links from another module.
- Keep the module row short enough to understand without hiding important financial work.

## 3. Decide the internal tabs and ribbons

- Define internal tabs for Invoices, Payments, Expenses, Taxes, Reports, purchasing, and other approved modules.
- Separate record navigation from actions such as New Invoice, Record Payment, Refund, Reconcile, Export, and Run Report.
- Keep financial actions permission-aware.
- Make sure Order shortcuts open the authoritative finance record instead of creating a second copy.

## 4. Update the complete feature audit

- Recheck the existing Business & Finance feature audit against the newest `main` branch.
- List every visible feature, backend-only feature, integration, report, export, financial safeguard, and unfinished control.
- Rate each feature by actual usable depth.
- Mark optional or planned AI separately from normal financial calculations.

## 5. Create and correct the Business & Finance gap list

- Turn incomplete workflows into numbered Business & Finance gaps.
- Separate missing implementation, incorrect placement, confusing presentation, security problems, and future additions.
- Remove gaps that are no longer real after code inspection.
- Arrange the remaining work into safe implementation batches with clear dependencies.

## 6. Verify every gap against the code

- Check frontend pages, backend routes, models, services, permissions, tenant filters, audit history, and tests.
- Confirm whether a feature works from the normal interface instead of crediting backend code that employees cannot use.
- Confirm that displayed totals come from authoritative records.
- Require evidence before closing a financial issue.

## 7. Complete the financial workflows

- Finance Overview and dashboard totals
- Invoice creation, editing, issuing, voiding, documents, status history, and Order links
- Payment recording, Stripe status, refunds, reconciliation, failed payments, and central payment history
- Expenses, categories, receipts, recurring expenses, vendor links, approvals, and accounts-payable needs
- Taxes, exemptions, taxable sales, reports, adjustments, and remittance tracking boundaries
- Reports, saved reports, exports, scheduling, drilldowns, and report permissions
- Purchasing, inventory valuation, vendors, purchase orders, and Supply Center workflows if they remain in this section

## 8. Fix connections with other sections

- Show invoice, deposit, payment, balance, refund, and financial-block status inside authorized Order views.
- Send payroll cost summaries from Team & Productivity without duplicating payroll records.
- Pull pricing results from Pricing Foundation without allowing finance pages to silently change pricing rules.
- Use the same Customers, Orders, Webstore orders, vendors, products, and payment records throughout the app.

## 9. Strengthen money and record safeguards

- Store and calculate money consistently.
- Protect against duplicate charges, duplicate webhooks, double refunds, and repeated submissions.
- Preserve invoice, payment, refund, tax, and pricing snapshots after later settings change.
- Require reasons and audit history for sensitive overrides, voids, write-offs, reconciliations, and manual adjustments.
- Confirm Stripe Connect direct-charge behavior wherever Webstore payments are involved.

## 10. Fix financial permissions and privacy

- Decide what owners, admins, managers, sales staff, production staff, and employees can see.
- Hide profit, costs, payroll details, sensitive payment information, and tax information from unauthorized roles.
- Test tenant separation on every financial endpoint and report.
- Separate platform billing permissions from a shop's customer-payment permissions.

## 11. Clean up the interface

- Make totals, balances, statuses, dates, and warnings easy to understand.
- Replace dead buttons and misleading placeholders with working actions or clear boundaries.
- Use drill-through views so users can understand where a number came from.
- Keep finance pages visually consistent with the approved app shell.

## 12. Clean up the code

- Identify oversized finance, report, Stripe, tax, and purchasing files.
- Separate calculation logic from page formatting and provider integrations.
- Remove duplicate total calculations and repeated record-mapping code.
- Keep one authoritative service for each financial rule.

## 13. Test and verify

- Test invoice and payment lifecycles, refunds, failed transactions, tax behavior, expenses, reports, exports, and permissions.
- Add regression tests for money rounding, duplicate submissions, tenant isolation, locked historical records, and status transitions.
- Run backend tests, frontend tests, and the frontend build.
- Verify the most important workflows through the actual interface.

## 14. Update the registers and perform the final review

- Record every fixed and remaining Business & Finance issue.
- Add branch, commit, test, and limitation evidence.
- Perform a final category-specific code review.
- Then update the main code issue register so remaining finance risks are visible in the overall MVP plan.
