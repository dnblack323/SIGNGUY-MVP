# Report Builder Complete Reporting System - Preflight And Implementation Plan

**Branch:** `CODEX-reports-complete-reporting-system`
**Starting main:** `1e9df59dfb844401d4fd74fd343dc39401b75d0c`
**Controlling source:** `specs_pack/source/SIGNGUY_AI_REPORT_CATALOG_AND_CUSTOM_REPORT_BUILDER_SPEC.pdf`
**Extracted text companion:** `specs_pack/extracted/SIGNGUY_AI_REPORT_CATALOG_AND_CUSTOM_REPORT_BUILDER_SPEC.txt`
**Source title:** `SIGNGUY AI | REPORT CATALOG & CUSTOM REPORT BUILDER SPEC`
**Source length:** 11 pages

## Owner Decisions Applied

- App location is `Business & Finance -> Reports`. The PDF's older `Business Management -> Reports` label is superseded.
- Official Webstore types are `B2B`, `Fundraiser`, `Event`, `Promotional`, and `General`. The PDF's `Employee` store type is recorded as a discrepancy and not added as a sixth official type.
- Report Builder is tenant/shop-level reporting, not EC20 platform analytics.
- Phase labels in the PDF establish implementation sequence only. They do not remove later requirements.

## Architecture Contract

One shared reporting system owns:

- Standard report catalog and category navigation.
- Source registry and field registry.
- Metric definitions and safe query validation.
- Tenant-scoped query execution.
- Saved and shared report definitions.
- Export generation and export history.
- Scheduled report definitions and run history.
- Drill-down links to authorized source records.
- Dashboard-compatible report-widget definitions where the current dashboard contract permits.

No module may create a second report builder, separate export engine, or independent scheduled-report engine.

## Source-Contract Readiness

| Source area | Current evidence | Status |
|---|---|---|
| Customers | `backend/app/models/customer.py`, `routers/customers.py` | READY |
| Quotes | `quote.py`, `quote_line_item.py`, quote statuses and totals | READY |
| Orders and Order Items | `order.py`, pricing snapshots, totals, statuses, due dates | READY |
| Invoices | `invoice.py`, dual document/financial statuses, totals, balances | READY |
| Payments and refunds | `payment.py`, manual/Stripe boundary, confirmed/refund status | READY |
| Expenses | `expense.py`, active/archived/voided states, category snapshots | READY |
| Taxes | `tax_service.py`, `tax_reports.py`, invoice tax snapshots | READY |
| Work Orders | `work_order.py`, statuses, due dates, assigned users | READY |
| Production stages | `production_workflow.py`, stage instances and histories | READY WITH ADAPTATION |
| Artwork/proofs | Order Item `proof_status` and Decision Room docs exist, full approval timing is partial | PARTIALLY DEPENDENT |
| Documents/compliance | Document and file records exist, required-doc policy is not defined | BLOCKED BY SOURCE CONTRACT |
| Materials/inventory | `material.py`, `inventory.py`, immutable movement ledger | READY |
| Purchasing/vendors | `purchase_order.py`, `vendor.py`, receiving records | READY |
| Employees/time | `employee.py`, `time_entry.py`, `timesheet.py` | READY |
| Payroll | `payroll_snapshot.py`, `payroll_transaction.py` | READY |
| Scheduling/capacity | employee schedules and Wrap schedules exist; operational shop capacity is partial | PARTIALLY DEPENDENT |
| Webstores | EC14 models, buyer orders, products, ledger, store types | READY WITH DISCREPANCY |
| Wrap Lab | EC15 project, vehicle, schedules, panel plans, packets, warranties | READY WITH ADAPTATION |
| Dashboard customizer | no stable Dashboard Customizer registration contract found | BLOCKED BY SOURCE CONTRACT |
| Background delivery | no general background-job runner; scheduled reports can persist and run manually/test mode | PARTIALLY DEPENDENT |
| Platform analytics | belongs to EC20, outside tenant Report Builder | BLOCKED - OUTSIDE REPORT BUILDER |

## Standard Report Requirement Inventory

Rows marked `IMPLEMENTED AND VERIFIED` are backed by a concrete report contract and focused verification. Rows marked `BLOCKED — NOT COMPLETE` are not presented as completed functionality; the blocking source contract or missing implementation remains documented in the row's source/evidence context and in the blocker notes below.

| ID | Exact report / requirement | Category | Primary source | Filters / grouping | Drill-down | Exports | Permission | Status |
|---|---|---|---|---|---|---|---|---|
| RB-OV-001 | Revenue collected | Overview | payments, invoices | date range, comparison | payments/invoices | CSV/XLSX/PDF/print | finance:read | IMPLEMENTED AND VERIFIED |
| RB-OV-002 | Sales booked | Overview | orders | date range, status | orders | CSV/XLSX/PDF/print | order:read | IMPLEMENTED AND VERIFIED |
| RB-OV-003 | Open quote value | Overview | quotes | date range, status | quotes | CSV/XLSX/PDF/print | quote:read | IMPLEMENTED AND VERIFIED |
| RB-OV-004 | Open order value | Overview | orders | due date, status | orders | CSV/XLSX/PDF/print | order:read | IMPLEMENTED AND VERIFIED |
| RB-OV-005 | Outstanding invoice balance | Overview | invoices | due date, financial status | invoices/customers | CSV/XLSX/PDF/print | invoice:read | IMPLEMENTED AND VERIFIED |
| RB-OV-006 | Estimated gross profit | Overview | order_items pricing snapshots | date range, category | orders/order items | CSV/XLSX/PDF/print | finance:read | IMPLEMENTED AND VERIFIED |
| RB-OV-007 | Orders due soon | Overview | orders, work_orders | due date window | orders/work orders | CSV/XLSX/PDF/print | order:read | BLOCKED — NOT COMPLETE |
| RB-OV-008 | Production workload | Overview | work_orders, production stages | status, stage | work orders | CSV/XLSX/PDF/print | work_order:read | BLOCKED — NOT COMPLETE |
| RB-OV-009 | Low-stock alerts | Overview | inventory_items, materials | location, category | materials/inventory | CSV/XLSX/PDF/print | inventory:read | IMPLEMENTED AND VERIFIED |
| RB-OV-010 | Revenue trend by week/month | Overview | payments/invoices | date bucket | payments/invoices | CSV/XLSX/PDF/print | finance:read | IMPLEMENTED AND VERIFIED |
| RB-OV-011 | Order count trend | Overview | orders | date bucket | orders | CSV/XLSX/PDF/print | order:read | IMPLEMENTED AND VERIFIED |
| RB-OV-012 | Average order value trend | Overview | orders | date bucket | orders | CSV/XLSX/PDF/print | order:read | IMPLEMENTED AND VERIFIED |
| RB-OV-013 | Quote conversion trend | Overview | quotes | date bucket | quotes/orders | CSV/XLSX/PDF/print | quote:read | IMPLEMENTED AND VERIFIED |
| RB-OV-014 | Labor and material cost trend | Overview | order_items, payroll/material snapshots | date bucket | orders/items | CSV/XLSX/PDF/print | finance:read | IMPLEMENTED AND VERIFIED |
| RB-OV-015 | Overdue invoices | Overview action | invoices | due date, status | invoices | CSV/XLSX/PDF/print | invoice:read | BLOCKED — NOT COMPLETE |
| RB-OV-016 | Quotes needing follow-up | Overview action | quotes | status, age | quotes | CSV/XLSX/PDF/print | quote:read | BLOCKED — NOT COMPLETE |
| RB-OV-017 | Orders at risk of being late | Overview action | orders/work_orders | due date, status | orders/work orders | CSV/XLSX/PDF/print | order:read | BLOCKED — NOT COMPLETE |
| RB-OV-018 | Proofs waiting for approval | Overview action | order_items proof_status | status | order items | CSV/XLSX/PDF/print | order:read | BLOCKED — NOT COMPLETE |
| RB-OV-019 | Purchases or stock issues that could delay work | Overview action | inventory, purchase_orders | low stock, open PO | materials/POs | CSV/XLSX/PDF/print | inventory:read | BLOCKED — NOT COMPLETE |
| RB-FIN-001 | Sales by day, week, month, quarter, and year | Financial | orders/invoices | period bucket | orders/invoices | CSV/XLSX/PDF/print/accounting | finance:read | BLOCKED — NOT COMPLETE |
| RB-FIN-002 | Sales by product/service category | Financial | order_items | category | orders/items | CSV/XLSX/PDF/print/accounting | finance:read | BLOCKED — NOT COMPLETE |
| RB-FIN-003 | Sales by customer | Financial | orders/customers | customer | customers/orders | CSV/XLSX/PDF/print/accounting | finance:read | BLOCKED — NOT COMPLETE |
| RB-FIN-004 | Sales by employee or salesperson | Financial | quotes/orders created_by | user | users/orders | CSV/XLSX/PDF/print | finance:read | BLOCKED — NOT COMPLETE |
| RB-FIN-005 | Average order value | Financial | orders | date range | orders | CSV/XLSX/PDF/print | finance:read | BLOCKED — NOT COMPLETE |
| RB-FIN-006 | Deposit versus final payment mix | Financial | payments | method/status/source | payments/invoices | CSV/XLSX/PDF/print | payment:read | BLOCKED — NOT COMPLETE |
| RB-FIN-007 | Revenue by source | Financial | orders/webstores/wrap projects | source | records | CSV/XLSX/PDF/print | finance:read | BLOCKED — NOT COMPLETE |
| RB-FIN-008 | Open invoices | Financial | invoices | financial status | invoices | CSV/XLSX/PDF/print/accounting | invoice:read | BLOCKED — NOT COMPLETE |
| RB-FIN-009 | Overdue invoices | Financial | invoices | due date, financial status | invoices | CSV/XLSX/PDF/print/accounting | invoice:read | BLOCKED — NOT COMPLETE |
| RB-FIN-010 | Invoice aging | Financial | invoices | aging bucket | invoices/customers | CSV/XLSX/PDF/print/accounting | invoice:read | BLOCKED — NOT COMPLETE |
| RB-FIN-011 | Payments collected | Financial | payments | date, method | payments/invoices | CSV/XLSX/PDF/print/accounting | payment:read | BLOCKED — NOT COMPLETE |
| RB-FIN-012 | Payment method mix | Financial | payments | method | payments | CSV/XLSX/PDF/print/accounting | payment:read | BLOCKED — NOT COMPLETE |
| RB-FIN-013 | Deposits due and deposits received | Financial | quotes/payments | quote/order status | quotes/payments | CSV/XLSX/PDF/print | finance:read | BLOCKED — NOT COMPLETE |
| RB-FIN-014 | Refunds, credits, write-offs, and failed payments | Financial | payments/refunds | status/type | payments | CSV/XLSX/PDF/print/accounting | payment:read | BLOCKED — NOT COMPLETE |
| RB-FIN-015 | Customer balance detail | Financial | invoices/customers | customer, aging | customers/invoices | CSV/XLSX/PDF/print/accounting | invoice:read | BLOCKED — NOT COMPLETE |
| RB-FIN-016 | Estimated versus actual revenue | Financial | quotes/orders/invoices | record link | quote/order/invoice | CSV/XLSX/PDF/print | finance:read | BLOCKED — NOT COMPLETE |
| RB-FIN-017 | Estimated versus actual labor cost | Financial | pricing snapshots, payroll/time | order/category | order/work order | CSV/XLSX/PDF/print | finance:read | BLOCKED — NOT COMPLETE |
| RB-FIN-018 | Estimated versus actual material cost | Financial | pricing snapshots, inventory/materials | order/category | order/items | CSV/XLSX/PDF/print | finance:read | BLOCKED — NOT COMPLETE |
| RB-FIN-019 | Gross profit and gross margin by order | Financial | orders/order_items | order/category/customer | orders | CSV/XLSX/PDF/print | finance:read | BLOCKED — NOT COMPLETE |
| RB-FIN-020 | Profitability by service category | Financial | order_items | category | order items | CSV/XLSX/PDF/print | finance:read | BLOCKED — NOT COMPLETE |
| RB-FIN-021 | Profitability by customer | Financial | orders/order_items/customers | customer | customers/orders | CSV/XLSX/PDF/print | finance:read | BLOCKED — NOT COMPLETE |
| RB-FIN-022 | Most and least profitable products or job types | Financial | order_items | category/product type | order items | CSV/XLSX/PDF/print | finance:read | BLOCKED — NOT COMPLETE |
| RB-FIN-023 | Rework and warranty cost impact | Financial | production stages/wrap warranties | rework/warranty markers | work/wrap records | CSV/XLSX/PDF/print | finance:read | BLOCKED — NOT COMPLETE |
| RB-FIN-024 | Taxable sales | Financial taxes | invoices/orders | date, jurisdiction | invoices/orders | CSV/XLSX/PDF/print/tax | tax_report:read | BLOCKED — NOT COMPLETE |
| RB-FIN-025 | Tax collected | Financial taxes | invoices | date, jurisdiction | invoices | CSV/XLSX/PDF/print/tax | tax_report:read | BLOCKED — NOT COMPLETE |
| RB-FIN-026 | Tax owed by jurisdiction when supported | Financial taxes | invoices/tax snapshots | jurisdiction | invoices | CSV/XLSX/PDF/print/tax | tax_report:read | BLOCKED — NOT COMPLETE |
| RB-FIN-027 | Sales tax exception items | Financial taxes | tax exemptions/invoices | exception type | invoices/customers | CSV/XLSX/PDF/print/tax | tax_report:read | BLOCKED — NOT COMPLETE |
| RB-FIN-028 | Export-ready transaction detail | Financial taxes/accounting | invoices/payments/expenses | date, type | source records | CSV/XLSX/PDF/print/accounting/tax | finance:read | BLOCKED — NOT COMPLETE |
| RB-FIN-029 | Monthly income/expense category summaries | Financial accounting | invoices/payments/expenses | month/category | source records | CSV/XLSX/PDF/print/accounting | finance:read | BLOCKED — NOT COMPLETE |
| RB-FIN-030 | Accounting integration reconciliation status | Financial accounting | integration records | provider/status | integrations | CSV/XLSX/PDF/print/accounting | integration:read | BLOCKED — NOT COMPLETE |
| RB-FIN-031 | Expected payments from open invoices | Financial cash | invoices | due date | invoices | CSV/XLSX/PDF/print | finance:read | BLOCKED — NOT COMPLETE |
| RB-FIN-032 | Expected deposits from approved quotes | Financial cash | quotes | approved/converted | quotes | CSV/XLSX/PDF/print | finance:read | BLOCKED — NOT COMPLETE |
| RB-FIN-033 | Upcoming webstore payouts or fees | Financial cash | webstore ledger | store/date/status | webstores/ledger | CSV/XLSX/PDF/print | webstore:read | BLOCKED — NOT COMPLETE |
| RB-FIN-034 | Projected revenue from scheduled work | Financial cash | orders/work_orders/wrap schedules | due/schedule date | orders/work orders | CSV/XLSX/PDF/print | finance:read | BLOCKED — NOT COMPLETE |
| RB-FIN-035 | Short-term cash collection forecast | Financial cash | invoices/quotes/webstores | date bucket | source records | CSV/XLSX/PDF/print | finance:read | BLOCKED — NOT COMPLETE |
| RB-OPS-001 | Orders by status | Operations | orders | status | orders | CSV/XLSX/PDF/print | order:read | IMPLEMENTED AND VERIFIED |
| RB-OPS-002 | Open order value | Operations | orders | status/date | orders | CSV/XLSX/PDF/print | order:read | BLOCKED — NOT COMPLETE |
| RB-OPS-003 | Orders due today/this week | Operations | orders | due date | orders | CSV/XLSX/PDF/print | order:read | BLOCKED — NOT COMPLETE |
| RB-OPS-004 | Late orders | Operations | orders | due date/status | orders | CSV/XLSX/PDF/print | order:read | BLOCKED — NOT COMPLETE |
| RB-OPS-005 | Orders by type, customer, source, or owner | Operations | orders/customers | type/customer/source/owner | orders/customers | CSV/XLSX/PDF/print | order:read | BLOCKED — NOT COMPLETE |
| RB-OPS-006 | Order aging | Operations | orders | age bucket/status | orders | CSV/XLSX/PDF/print | order:read | BLOCKED — NOT COMPLETE |
| RB-OPS-007 | Canceled and reopened orders | Operations | orders | status/history | orders | CSV/XLSX/PDF/print | order:read | BLOCKED — NOT COMPLETE |
| RB-OPS-008 | Production board workload by stage | Operations production | production stages/work_orders | stage/status | work orders | CSV/XLSX/PDF/print | work_order:read | BLOCKED — NOT COMPLETE |
| RB-OPS-009 | Time in each production stage | Operations production | production_stage_instances | stage/date | work orders/stages | CSV/XLSX/PDF/print | work_order:read | BLOCKED — NOT COMPLETE |
| RB-OPS-010 | Bottlenecks by stage or department | Operations production | production_stage_instances | stage/department | work orders/stages | CSV/XLSX/PDF/print | work_order:read | BLOCKED — NOT COMPLETE |
| RB-OPS-011 | Scheduled versus completed production | Operations production | work_orders | schedule/due/status | work orders | CSV/XLSX/PDF/print | work_order:read | BLOCKED — NOT COMPLETE |
| RB-OPS-012 | Rework counts and reasons | Operations production | production stages/order items/wrap warranty | reason | work/wrap records | CSV/XLSX/PDF/print | work_order:read | BLOCKED — NOT COMPLETE |
| RB-OPS-013 | Jobs waiting on materials, artwork, approval, customer response, or install scheduling | Operations production | work_orders/order_items | blocker reason/status | work/orders | CSV/XLSX/PDF/print | work_order:read | BLOCKED — NOT COMPLETE |
| RB-OPS-014 | Proofs sent | Artwork approvals | order_items proof_status | status/date | order items | CSV/XLSX/PDF/print | order:read | BLOCKED — NOT COMPLETE |
| RB-OPS-015 | Proofs awaiting approval | Artwork approvals | order_items proof_status | status/date | order items | CSV/XLSX/PDF/print | order:read | BLOCKED — NOT COMPLETE |
| RB-OPS-016 | Approval turnaround time | Artwork approvals | proof/decision room events | date | approvals | CSV/XLSX/PDF/print | order:read | BLOCKED — NOT COMPLETE |
| RB-OPS-017 | Revision cycles per order | Artwork approvals | quote revisions/order item history | order | quotes/orders | CSV/XLSX/PDF/print | quote:read | BLOCKED — NOT COMPLETE |
| RB-OPS-018 | Approval delays by customer or job type | Artwork approvals | proof/approval events | customer/type | approvals | CSV/XLSX/PDF/print | order:read | BLOCKED — NOT COMPLETE |
| RB-OPS-019 | Rejected proof reasons | Artwork approvals | proof events | reason | order items | CSV/XLSX/PDF/print | order:read | BLOCKED — NOT COMPLETE |
| RB-OPS-020 | Signed document completion rates | Artwork approvals | signature/document records | document type | documents | CSV/XLSX/PDF/print | document:read | BLOCKED — NOT COMPLETE |
| RB-OPS-021 | Scheduled installs | Scheduling installs | wrap_schedules/work_orders | date/type | schedules/work orders | CSV/XLSX/PDF/print | schedule:read | BLOCKED — NOT COMPLETE |
| RB-OPS-022 | Install completion rate | Scheduling installs | wrap_schedules/work_orders | date/type | schedules/work orders | CSV/XLSX/PDF/print | schedule:read | BLOCKED — NOT COMPLETE |
| RB-OPS-023 | Install duration estimates versus actuals | Scheduling installs | schedules/time entries | install | schedules/time | CSV/XLSX/PDF/print | schedule:read | BLOCKED — NOT COMPLETE |
| RB-OPS-024 | No-show, reschedule, and cancellation tracking | Scheduling installs | schedule history | status/reason | schedules | CSV/XLSX/PDF/print | schedule:read | BLOCKED — NOT COMPLETE |
| RB-OPS-025 | Crew workload | Scheduling installs | schedules/work_orders | crew/date | schedules/work orders | CSV/XLSX/PDF/print | schedule:read | BLOCKED — NOT COMPLETE |
| RB-OPS-026 | Upcoming delivery, pickup, and install commitments | Scheduling installs | orders/work_orders/wrap_schedules | date/type | source records | CSV/XLSX/PDF/print | schedule:read | BLOCKED — NOT COMPLETE |
| RB-OPS-027 | Missing required documents | Documents | document policy | required document | documents/orders | CSV/XLSX/PDF/print | document:read | BLOCKED — NOT COMPLETE |
| RB-OPS-028 | Unsigned contracts or acknowledgments | Documents | document/signature records | document status | documents | CSV/XLSX/PDF/print | document:read | BLOCKED — NOT COMPLETE |
| RB-OPS-029 | Documents expiring or due for renewal | Documents | document records | expiration date | documents | CSV/XLSX/PDF/print | document:read | BLOCKED — NOT COMPLETE |
| RB-OPS-030 | Document completion by order type | Documents | document policy/order type | order type | documents/orders | CSV/XLSX/PDF/print | document:read | BLOCKED — NOT COMPLETE |
| RB-OPS-031 | Customer packet delivery status | Documents | packets/decision rooms | status | packets/rooms | CSV/XLSX/PDF/print | document:read | BLOCKED — NOT COMPLETE |
| RB-CS-001 | New versus returning customers | Customer & Sales | customers/orders | date | customers/orders | CSV/XLSX/PDF/print | customer:read | BLOCKED — NOT COMPLETE |
| RB-CS-002 | Customer lifetime value | Customer & Sales | customers/orders/invoices | customer/date | customers/orders | CSV/XLSX/PDF/print | finance:read | BLOCKED — NOT COMPLETE |
| RB-CS-003 | Top customers by revenue, profit, and order count | Customer & Sales | customers/orders/order_items | metric | customers/orders | CSV/XLSX/PDF/print | finance:read | BLOCKED — NOT COMPLETE |
| RB-CS-004 | Customer purchase frequency | Customer & Sales | orders/customers | customer/date | customers/orders | CSV/XLSX/PDF/print | customer:read | BLOCKED — NOT COMPLETE |
| RB-CS-005 | Inactive customers | Customer & Sales | customers/orders | inactivity window | customers | CSV/XLSX/PDF/print | customer:read | BLOCKED — NOT COMPLETE |
| RB-CS-006 | Customer segmentation by industry, type, or tag | Customer & Sales | customers | segment fields | customers | CSV/XLSX/PDF/print | customer:read | BLOCKED — NOT COMPLETE |
| RB-CS-007 | Quotes created, sent, viewed, approved, declined, expired | Customer & Sales | quotes | status/date | quotes | CSV/XLSX/PDF/print | quote:read | BLOCKED — NOT COMPLETE |
| RB-CS-008 | Quote-to-order conversion rate | Customer & Sales | quotes/orders | date/source | quotes/orders | CSV/XLSX/PDF/print | quote:read | BLOCKED — NOT COMPLETE |
| RB-CS-009 | Conversion by salesperson, source, category, and customer type | Customer & Sales | quotes/customers | grouping | quotes/customers | CSV/XLSX/PDF/print | quote:read | BLOCKED — NOT COMPLETE |
| RB-CS-010 | Average quote value | Customer & Sales | quotes | date/status | quotes | CSV/XLSX/PDF/print | quote:read | BLOCKED — NOT COMPLETE |
| RB-CS-011 | Lost quote reasons | Customer & Sales | quotes | declined reason | quotes | CSV/XLSX/PDF/print | quote:read | BLOCKED — NOT COMPLETE |
| RB-CS-012 | Quotes needing follow-up | Customer & Sales | quotes | age/status | quotes | CSV/XLSX/PDF/print | quote:read | BLOCKED — NOT COMPLETE |
| RB-CS-013 | Pipeline by stage | Customer & Sales | quotes | status/stage | quotes | CSV/XLSX/PDF/print | quote:read | BLOCKED — NOT COMPLETE |
| RB-CS-014 | Forecast value by close date | Customer & Sales | quotes | close/expiration date | quotes | CSV/XLSX/PDF/print | quote:read | BLOCKED — NOT COMPLETE |
| RB-CS-015 | Follow-up activity | Customer & Sales | tasks/activities | activity date | tasks | CSV/XLSX/PDF/print | task:read | BLOCKED — NOT COMPLETE |
| RB-CS-016 | Lead source performance | Customer & Sales | leads/quotes | lead source | leads/quotes | CSV/XLSX/PDF/print | lead:read | BLOCKED — NOT COMPLETE |
| RB-CS-017 | Sales cycle length | Customer & Sales | quotes/orders | dates | quotes/orders | CSV/XLSX/PDF/print | quote:read | BLOCKED — NOT COMPLETE |
| RB-CS-018 | Opportunities with no recent activity | Customer & Sales | leads/tasks/quotes | activity age | leads/tasks | CSV/XLSX/PDF/print | task:read | BLOCKED — NOT COMPLETE |
| RB-CS-019 | Repeat order rate | Customer & Sales | orders/customers | date | customers/orders | CSV/XLSX/PDF/print | customer:read | BLOCKED — NOT COMPLETE |
| RB-CS-020 | Post-install or post-purchase follow-up status | Customer & Sales | tasks/work_orders | follow-up status | tasks/orders | CSV/XLSX/PDF/print | task:read | BLOCKED — NOT COMPLETE |
| RB-CS-021 | Customers due for reactivation | Customer & Sales | customers/orders | inactivity | customers | CSV/XLSX/PDF/print | customer:read | BLOCKED — NOT COMPLETE |
| RB-CS-022 | Upsell/cross-sell opportunities | Customer & Sales | AI/marketing rules | opportunity rules | customers | CSV/XLSX/PDF/print | customer:read | BLOCKED — NOT COMPLETE |
| RB-CS-023 | Review request status | Customer & Sales | marketing/review requests | status | customers/orders | CSV/XLSX/PDF/print | customer:read | BLOCKED — NOT COMPLETE |
| RB-WS-001 | Sales by store | Webstores | webstore_buyer_orders | store/date | webstores/orders | CSV/XLSX/PDF/print | webstore:read | IMPLEMENTED AND VERIFIED |
| RB-WS-002 | Orders by store | Webstores | webstore_buyer_orders | store/date | webstores/orders | CSV/XLSX/PDF/print | webstore:read | BLOCKED — NOT COMPLETE |
| RB-WS-003 | Average order value | Webstores | webstore_buyer_orders | store/date | webstore orders | CSV/XLSX/PDF/print | webstore:read | BLOCKED — NOT COMPLETE |
| RB-WS-004 | Store conversion when traffic data exists | Webstores | traffic analytics | store/date | webstores | CSV/XLSX/PDF/print | webstore:read | BLOCKED — NOT COMPLETE |
| RB-WS-005 | Open and closing-soon stores | Webstores | webstores | status/type | webstores | CSV/XLSX/PDF/print | webstore:read | BLOCKED — NOT COMPLETE |
| RB-WS-006 | Store goal progress for fundraisers | Webstores | webstores/buyer orders | store type | webstores | CSV/XLSX/PDF/print | webstore:read | BLOCKED — NOT COMPLETE |
| RB-WS-007 | Store performance by type | Webstores | webstores/buyer orders | official type | webstores | CSV/XLSX/PDF/print | webstore:read | BLOCKED — NOT COMPLETE |
| RB-WS-008 | Best-selling products | Webstores | buyer order line_items/products | product/date | products/orders | CSV/XLSX/PDF/print | webstore:read | BLOCKED — NOT COMPLETE |
| RB-WS-009 | Variant performance | Webstores | buyer order line_items | variant | products/orders | CSV/XLSX/PDF/print | webstore:read | BLOCKED — NOT COMPLETE |
| RB-WS-010 | Low-performing products | Webstores | products/orders | product | products/orders | CSV/XLSX/PDF/print | webstore:read | BLOCKED — NOT COMPLETE |
| RB-WS-011 | Revenue and margin by product | Webstores | products/ledger/orders | product | products/orders | CSV/XLSX/PDF/print | webstore:read | BLOCKED — NOT COMPLETE |
| RB-WS-012 | Product demand by size/color/style | Webstores | line_items variants | variant | products/orders | CSV/XLSX/PDF/print | webstore:read | BLOCKED — NOT COMPLETE |
| RB-WS-013 | Out-of-stock or unavailable option impact | Webstores | products/inventory | stock status | products | CSV/XLSX/PDF/print | webstore:read | BLOCKED — NOT COMPLETE |
| RB-WS-014 | Owner share totals | Webstores | webstore_ledger_entries | store/date | ledger/webstores | CSV/XLSX/PDF/print/accounting | webstore:read | BLOCKED — NOT COMPLETE |
| RB-WS-015 | Platform fee totals | Webstores | webstore_ledger_entries | store/date | ledger/webstores | CSV/XLSX/PDF/print/accounting | webstore:read | BLOCKED — NOT COMPLETE |
| RB-WS-016 | Stripe/payment processing fee totals when available | Webstores | webstore_ledger_entries | store/date | ledger/webstores | CSV/XLSX/PDF/print/accounting | webstore:read | BLOCKED — NOT COMPLETE |
| RB-WS-017 | Payout status | Webstores | ledger/status | store/status | ledger/webstores | CSV/XLSX/PDF/print/accounting | webstore:read | BLOCKED — NOT COMPLETE |
| RB-WS-018 | Unpaid or failed payout issues | Webstores | ledger/status | status | ledger/webstores | CSV/XLSX/PDF/print/accounting | webstore:read | BLOCKED — NOT COMPLETE |
| RB-WS-019 | Store-level margin summary | Webstores | ledger/products/orders | store | webstores/orders | CSV/XLSX/PDF/print | webstore:read | BLOCKED — NOT COMPLETE |
| RB-WS-020 | Fundraiser goal progress | Webstores | stores/orders | fundraiser stores | webstores | CSV/XLSX/PDF/print | webstore:read | BLOCKED — NOT COMPLETE |
| RB-WS-021 | Donation totals | Webstores | buyer orders | store/date | orders | CSV/XLSX/PDF/print | webstore:read | BLOCKED — NOT COMPLETE |
| RB-WS-022 | Event deadline status | Webstores | stores | deadline/status | webstores | CSV/XLSX/PDF/print | webstore:read | BLOCKED — NOT COMPLETE |
| RB-WS-023 | Pickup/delivery status | Webstores | buyer orders | fulfillment status | orders | CSV/XLSX/PDF/print | webstore:read | BLOCKED — NOT COMPLETE |
| RB-WS-024 | Late order volume | Webstores | buyer orders/stores | deadline/status | orders | CSV/XLSX/PDF/print | webstore:read | BLOCKED — NOT COMPLETE |
| RB-WS-025 | Participant/team/group sales ranking when enabled | Webstores | buyer/order metadata | participant/team | orders | CSV/XLSX/PDF/print | webstore:read | BLOCKED — NOT COMPLETE |
| RB-MP-001 | On-hand quantity | Materials & Purchasing | inventory_items | location/category | inventory/materials | CSV/XLSX/PDF/print | inventory:read | IMPLEMENTED AND VERIFIED |
| RB-MP-002 | Low stock and out-of-stock items | Materials & Purchasing | inventory_items/materials | threshold/location | inventory/materials | CSV/XLSX/PDF/print | inventory:read | IMPLEMENTED AND VERIFIED |
| RB-MP-003 | Inventory value | Materials & Purchasing | inventory_items/materials | location/category | inventory/materials | CSV/XLSX/PDF/print | inventory:read | BLOCKED — NOT COMPLETE |
| RB-MP-004 | Usage trends | Materials & Purchasing | inventory_movements | date/material | movements | CSV/XLSX/PDF/print | inventory:read | IMPLEMENTED AND VERIFIED |
| RB-MP-005 | Material movement history | Materials & Purchasing | inventory_movements | date/material | movements | CSV/XLSX/PDF/print | inventory:read | IMPLEMENTED AND VERIFIED |
| RB-MP-006 | Reorder suggestions | Materials & Purchasing | inventory_items/materials | threshold | materials | CSV/XLSX/PDF/print | inventory:read | BLOCKED — NOT COMPLETE |
| RB-MP-007 | Expired, damaged, discontinued, or obsolete stock | Materials & Purchasing | inventory movements/material status | status | materials | CSV/XLSX/PDF/print | inventory:read | BLOCKED — NOT COMPLETE |
| RB-MP-008 | Purchase orders by status | Materials & Purchasing | purchase_orders | status/vendor | purchase orders | CSV/XLSX/PDF/print | purchasing:read | IMPLEMENTED AND VERIFIED |
| RB-MP-009 | Open purchases | Materials & Purchasing | purchase_orders | open status/vendor | purchase orders | CSV/XLSX/PDF/print | purchasing:read | BLOCKED — NOT COMPLETE |
| RB-MP-010 | Vendor lead time | Materials & Purchasing | purchase_orders/receiving | vendor | purchase orders | CSV/XLSX/PDF/print | purchasing:read | BLOCKED — NOT COMPLETE |
| RB-MP-011 | Expected delivery dates | Materials & Purchasing | purchase_orders | date/vendor | purchase orders | CSV/XLSX/PDF/print | purchasing:read | BLOCKED — NOT COMPLETE |
| RB-MP-012 | Received versus ordered quantities | Materials & Purchasing | purchase_order_lines | PO/material | purchase orders | CSV/XLSX/PDF/print | purchasing:read | BLOCKED — NOT COMPLETE |
| RB-MP-013 | Purchase price variance | Materials & Purchasing | PO lines/material cost history | material/vendor | materials/POs | CSV/XLSX/PDF/print | purchasing:read | BLOCKED — NOT COMPLETE |
| RB-MP-014 | Purchases by vendor and material category | Materials & Purchasing | PO lines/materials | vendor/category | vendors/POs | CSV/XLSX/PDF/print | purchasing:read | BLOCKED — NOT COMPLETE |
| RB-MP-015 | Material usage by order | Materials & Purchasing | inventory movements/order links | order | orders/movements | CSV/XLSX/PDF/print | inventory:read | BLOCKED — NOT COMPLETE |
| RB-MP-016 | Usage by product/service category | Materials & Purchasing | inventory/order item links | category | order items | CSV/XLSX/PDF/print | inventory:read | BLOCKED — NOT COMPLETE |
| RB-MP-017 | Waste by material, employee, machine, or job type | Materials & Purchasing | inventory_movements | movement_type/reason | movements | CSV/XLSX/PDF/print | inventory:read | BLOCKED — NOT COMPLETE |
| RB-MP-018 | Waste cost | Materials & Purchasing | inventory_movements/material costs | material | movements/materials | CSV/XLSX/PDF/print | inventory:read | BLOCKED — NOT COMPLETE |
| RB-MP-019 | Roll/sheet utilization | Materials & Purchasing | material dimensions/movements | material | materials | CSV/XLSX/PDF/print | inventory:read | BLOCKED — NOT COMPLETE |
| RB-MP-020 | Material cost versus quoted material allowance | Materials & Purchasing | pricing snapshots/material costs | order/category | order items/materials | CSV/XLSX/PDF/print | finance:read | BLOCKED — NOT COMPLETE |
| RB-MP-021 | Vendor spend | Materials & Purchasing | purchase_orders | vendor/date | vendors/POs | CSV/XLSX/PDF/print | purchasing:read | IMPLEMENTED AND VERIFIED |
| RB-MP-022 | Price changes | Materials & Purchasing | material_cost_history | material/vendor | materials | CSV/XLSX/PDF/print | inventory:read | IMPLEMENTED AND VERIFIED |
| RB-MP-023 | On-time delivery rate | Materials & Purchasing | purchase_orders/receiving | vendor/date | POs | CSV/XLSX/PDF/print | purchasing:read | BLOCKED — NOT COMPLETE |
| RB-MP-024 | Order issue rate | Materials & Purchasing | PO issues | vendor/date | POs | CSV/XLSX/PDF/print | purchasing:read | BLOCKED — NOT COMPLETE |
| RB-MP-025 | Most-used vendors | Materials & Purchasing | purchase_orders | vendor/date | vendors/POs | CSV/XLSX/PDF/print | purchasing:read | BLOCKED — NOT COMPLETE |
| RB-MP-026 | Alternative vendor comparison | Materials & Purchasing | supplier connectors | vendor/material | vendors/materials | CSV/XLSX/PDF/print | purchasing:read | BLOCKED — NOT COMPLETE |
| RB-TL-001 | Hours by employee | Team & Labor | time_entries/timesheets | employee/date | employees/time | CSV/XLSX/PDF/print/payroll | timesheet:read | IMPLEMENTED AND VERIFIED |
| RB-TL-002 | Hours by department or production stage | Team & Labor | time_entries/work_orders | department/stage | time/work | CSV/XLSX/PDF/print/payroll | timesheet:read | BLOCKED — NOT COMPLETE |
| RB-TL-003 | Payroll totals by pay period | Team & Labor | payroll_snapshots | pay period | payroll | CSV/XLSX/PDF/print/payroll | payroll:read | IMPLEMENTED AND VERIFIED |
| RB-TL-004 | Advances, payments, carryover, and adjustments | Team & Labor | payroll_transactions | type/period | payroll | CSV/XLSX/PDF/print/payroll | payroll:read | IMPLEMENTED AND VERIFIED |
| RB-TL-005 | Clock-in/out exceptions | Team & Labor | time_entries/timesheets | exception/status | time entries | CSV/XLSX/PDF/print/payroll | timesheet:read | BLOCKED — NOT COMPLETE |
| RB-TL-006 | Missing time entries | Team & Labor | timesheets | missing count | timesheets | CSV/XLSX/PDF/print/payroll | timesheet:read | BLOCKED — NOT COMPLETE |
| RB-TL-007 | Export-ready timesheets | Team & Labor | timesheets/time_entries | period/employee | timesheets | CSV/XLSX/PDF/print/payroll | payroll:export | BLOCKED — NOT COMPLETE |
| RB-TL-008 | Estimated versus actual labor hours by order | Team & Labor | order item estimates/time entries | order | orders/time | CSV/XLSX/PDF/print | finance:read | BLOCKED — NOT COMPLETE |
| RB-TL-009 | Labor cost versus quoted allowance | Team & Labor | pricing snapshots/payroll | order/category | orders | CSV/XLSX/PDF/print | finance:read | BLOCKED — NOT COMPLETE |
| RB-TL-010 | Hours by order type | Team & Labor | time_entries/work_orders/orders | order type | orders/time | CSV/XLSX/PDF/print | timesheet:read | BLOCKED — NOT COMPLETE |
| RB-TL-011 | Hours by production stage | Team & Labor | time_entries/stages | stage | time/stages | CSV/XLSX/PDF/print | timesheet:read | BLOCKED — NOT COMPLETE |
| RB-TL-012 | Labor utilization | Team & Labor | time entries/availability | date/employee | time/employees | CSV/XLSX/PDF/print | timesheet:read | BLOCKED — NOT COMPLETE |
| RB-TL-013 | Overtime trends | Team & Labor | payroll/time | date bucket | payroll/time | CSV/XLSX/PDF/print/payroll | payroll:read | IMPLEMENTED AND VERIFIED |
| RB-TL-014 | Rework labor impact | Team & Labor | rework/time entries | reason/order | work/time | CSV/XLSX/PDF/print | finance:read | BLOCKED — NOT COMPLETE |
| RB-TL-015 | Scheduled hours versus available hours | Team & Labor | schedules/availability | employee/date | schedules/employees | CSV/XLSX/PDF/print | schedule:read | BLOCKED — NOT COMPLETE |
| RB-TL-016 | Employee workload | Team & Labor | work_orders/shifts/tasks | employee/date | employees/work | CSV/XLSX/PDF/print | employee:read | BLOCKED — NOT COMPLETE |
| RB-TL-017 | Install crew capacity | Team & Labor | wrap_schedules/shifts | crew/date | schedules | CSV/XLSX/PDF/print | schedule:read | BLOCKED — NOT COMPLETE |
| RB-TL-018 | Upcoming staffing gaps | Team & Labor | schedules/availability | date/role | schedules | CSV/XLSX/PDF/print | schedule:read | BLOCKED — NOT COMPLETE |
| RB-TL-019 | Time-off impact | Team & Labor | time_off_requests | date/employee | time off | CSV/XLSX/PDF/print | schedule:read | IMPLEMENTED AND VERIFIED |
| RB-TL-020 | Schedule adherence | Team & Labor | shifts/time entries | date/employee | shifts/time | CSV/XLSX/PDF/print | schedule:read | BLOCKED — NOT COMPLETE |
| RB-TL-021 | Late/missed clock-in patterns | Team & Labor | timesheets/time_entries | date/employee | time entries | CSV/XLSX/PDF/print | timesheet:read | IMPLEMENTED AND VERIFIED |
| RB-TL-022 | Absence or time-off tracking | Team & Labor | time_off_requests | type/status | time off | CSV/XLSX/PDF/print | schedule:read | IMPLEMENTED AND VERIFIED |
| RB-TL-023 | Task completion | Team & Labor | tasks | date/status | tasks | CSV/XLSX/PDF/print | task:read | BLOCKED — NOT COMPLETE |
| RB-TL-024 | Training/checklist completion when enabled | Team & Labor | training_assignments | status | training | CSV/XLSX/PDF/print | training:manage | IMPLEMENTED AND VERIFIED |
| RB-TL-025 | Employee announcements acknowledgement when enabled | Team & Labor | announcements | acknowledgment | announcements | CSV/XLSX/PDF/print | announcement:read | BLOCKED — NOT COMPLETE |
| RB-WL-001 | Wrap projects by status | Wrap Lab | wrap_projects | status/date | wrap projects | CSV/XLSX/PDF/print | wrap_lab:read | IMPLEMENTED AND VERIFIED |
| RB-WL-002 | Revenue and profit by vehicle type | Wrap Lab | wrap_projects/wrap_vehicles | vehicle type | wrap projects | CSV/XLSX/PDF/print | wrap_lab:read | BLOCKED — NOT COMPLETE |
| RB-WL-003 | Design-to-install turnaround time | Wrap Lab | wrap_projects/design scenes/schedules | date/status | wrap projects | CSV/XLSX/PDF/print | wrap_lab:read | BLOCKED — NOT COMPLETE |
| RB-WL-004 | Install scheduling status | Wrap Lab | wrap_schedules | status/type | schedules/projects | CSV/XLSX/PDF/print | wrap_lab:read | BLOCKED — NOT COMPLETE |
| RB-WL-005 | Project completion rate | Wrap Lab | wrap_projects | status/date | wrap projects | CSV/XLSX/PDF/print | wrap_lab:read | IMPLEMENTED AND VERIFIED |
| RB-WL-006 | Deposit and final payment status | Wrap Lab | wrap_projects/orders/invoices | status | source records | CSV/XLSX/PDF/print | wrap_lab:read | BLOCKED — NOT COMPLETE |
| RB-WL-007 | Estimated versus actual install hours | Wrap Lab | wrap_projects/time_entries | project | wrap/time | CSV/XLSX/PDF/print | wrap_lab:read | BLOCKED — NOT COMPLETE |
| RB-WL-008 | Material use by wrap project | Wrap Lab | wrap_panel_plans | project | wrap projects | CSV/XLSX/PDF/print | wrap_lab:read | IMPLEMENTED AND VERIFIED |
| RB-WL-009 | Waste by vehicle size/type | Wrap Lab | wrap_panel_plans/vehicles | vehicle type | wrap projects | CSV/XLSX/PDF/print | wrap_lab:read | BLOCKED — NOT COMPLETE |
| RB-WL-010 | Laminate/print/vinyl usage | Wrap Lab | wrap_panel_plans | material usage | wrap panel plans | CSV/XLSX/PDF/print | wrap_lab:read | IMPLEMENTED AND VERIFIED |
| RB-WL-011 | Install crew time | Wrap Lab | wrap_schedules/time_entries | crew/date | schedules/time | CSV/XLSX/PDF/print | wrap_lab:read | BLOCKED — NOT COMPLETE |
| RB-WL-012 | Material cost versus estimate | Wrap Lab | wrap_panel_plans/projects | project | wrap projects | CSV/XLSX/PDF/print | wrap_lab:read | IMPLEMENTED AND VERIFIED |
| RB-WL-013 | Mockup/proof turnaround time | Wrap Lab | wrap_design_scenes/activities | project/date | wrap projects | CSV/XLSX/PDF/print | wrap_lab:read | BLOCKED — NOT COMPLETE |
| RB-WL-014 | Revision cycles | Wrap Lab | wrap_design_scenes | project | scenes/projects | CSV/XLSX/PDF/print | wrap_lab:read | BLOCKED — NOT COMPLETE |
| RB-WL-015 | Customer approval delays | Wrap Lab | wrap packets/signatures | date/status | packets/projects | CSV/XLSX/PDF/print | wrap_lab:read | BLOCKED — NOT COMPLETE |
| RB-WL-016 | Brand asset completeness | Wrap Lab | artwork/design scenes | asset flags | projects/assets | CSV/XLSX/PDF/print | wrap_lab:read | BLOCKED — NOT COMPLETE |
| RB-WL-017 | Pre-install document/signoff status | Wrap Lab | wrap_inspections/packets | status/type | inspections/packets | CSV/XLSX/PDF/print | wrap_lab:read | BLOCKED — NOT COMPLETE |
| RB-WL-018 | Post-install follow-up completion | Wrap Lab | warranties/activities | status | warranty/projects | CSV/XLSX/PDF/print | wrap_lab:read | BLOCKED — NOT COMPLETE |
| RB-WL-019 | Warranty claims | Wrap Lab | wrap_warranties | status/type | warranty/projects | CSV/XLSX/PDF/print | wrap_lab:read | BLOCKED — NOT COMPLETE |
| RB-WL-020 | Issue type and root cause | Wrap Lab | warranty issue_refs | issue type | warranty/projects | CSV/XLSX/PDF/print | wrap_lab:read | BLOCKED — NOT COMPLETE |
| RB-WL-021 | Rework cost | Wrap Lab | warranty issue_refs/panel plans | issue | warranty/projects | CSV/XLSX/PDF/print | wrap_lab:read | BLOCKED — NOT COMPLETE |
| RB-WL-022 | Customer care packet delivery | Wrap Lab | wrap_packets | packet status | packets/projects | CSV/XLSX/PDF/print | wrap_lab:read | BLOCKED — NOT COMPLETE |
| RB-WL-023 | Recurring issue patterns by material, vehicle, or install type | Wrap Lab | warranty issue_refs/vehicles | issue/material/type | warranty/projects | CSV/XLSX/PDF/print | wrap_lab:read | BLOCKED — NOT COMPLETE |

## Capability Matrix

| Capability | Required behavior | Source / planned collection | Status |
|---|---|---|---|
| Saved reports | Persist validated report definitions; metadata edits do not version immutable definitions yet | `report_definitions` | IMPLEMENTED AND VERIFIED |
| Shared reports | Private, selected-user, role-based sharing without broadening source access or allowing shared users to mutate originals | `report_definitions.shared_*` | IMPLEMENTED AND VERIFIED |
| Scheduling | Daily, weekly, monthly, pay-period, event-triggered records; manual/test delivery and run history only until background worker exists | `report_schedules`, `report_schedule_runs` | IMPLEMENTED AND VERIFIED |
| Export history | Persist export metadata, status, format, actor, row count, filters | `report_exports` | IMPLEMENTED AND VERIFIED |
| Dashboard placement | Register dashboard-compatible report widgets when stable contract exists | report-side widget contract | BLOCKED — NOT COMPLETE |
| Drill-down | Runnable report rows return allowlisted source links where source routes currently exist | `drill_down` metadata | IMPLEMENTED AND VERIFIED |
| Calculated fields | Safe allowlisted operations only; no eval/exec/raw DB expressions | builder validation | BLOCKED — NOT COMPLETE |
| Comparison periods | Previous period and previous year where date basis exists | report execution metadata | BLOCKED — NOT COMPLETE |
| Definition versioning | Edits create a new definition version without corrupting schedules | versioned definition contract | BLOCKED — NOT COMPLETE |
| Permissions | Revalidate report-level and source-level permissions on list, run, save, share, export, schedule, drill-down | backend service | IMPLEMENTED AND VERIFIED |
| Audit history | Writes, exports, schedules, sharing, archive/restore audited | `audit_events` | BLOCKED — NOT COMPLETE |
| Large-result handling | Preview limits, export limits, status history | service limits | IMPLEMENTED AND VERIFIED |
| Schedule retries | Run history supports retries/failures and duplicate-running protection; automated retry worker absent | `report_schedule_runs` | BLOCKED — NOT COMPLETE |
| Timezone handling | Tenant timezone basis recorded and applied to schedule execution windows | scheduler contract | BLOCKED — NOT COMPLETE |
| Money rounding | Integer cents only, collected tax separated from revenue in implemented rows | result/export formatters | IMPLEMENTED AND VERIFIED |
| Safe formulas | Restricted expression tree over selected numeric fields | builder formula validator | BLOCKED — NOT COMPLETE |

## Donor Investigation Summary

| Repository | Evidence | Decision |
|---|---|---|
| `signguyai` | `memory/BUSINESS_FINANCE_REPORTING_ANALYTICS_REBUILD_DOC.md`; donor identifies reporting gaps and legacy `jobs` data bug | Supporting evidence only; do not treat as controlling spec |
| `signguyai` | Profit Analytics export pattern (CSV/XLSX/PDF) and issue reports | Adapt export format ideas, not legacy data source |
| `signguy-ai-feb22` | financial/payment model references and roadmap mentions | Supporting evidence for payment/invoice reconciliation only |
| `signguyai_rebuild_version` | duplicate copy of Business Finance rebuild investigation | Supporting evidence only |
| Current MVP | EC7 `reports_service.py`, `reports.py`, `ReportsPage.jsx` | Extend in-place to the PDF-governed shared engine |

## Implementation Units

1. Preserve source PDF and extracted text.
2. Expand backend reporting models, indexes, route contracts, export services, schedule services, saved/shared report service, and standard report catalog.
3. Expand frontend Reports workspace under `Business & Finance -> Reports` without changing UX1 shell navigation.
4. Add focused backend tests for report catalog, tenant isolation, permission revalidation, saved/shared reports, exports, scheduling, no fake blocked reports, and source reconciliation.
5. Add focused frontend tests for category navigation, builder validation, saved/shared/scheduled/export views, loading/empty/error states, and no horizontal document scroll.
6. Update tracking docs and evidence after verification.

## Completion Rule

The branch may be ready for review with blocked rows, but the complete Report Builder cannot be called complete until every PDF row is either `IMPLEMENTED AND VERIFIED` or explicitly `BLOCKED — NOT COMPLETE` with its exact source dependency documented.

## Implementation Status Update - 2026-07-29

Status: `REPORT BUILDER REVIEW CORRECTIONS APPLIED - READY FOR VERIFICATION`.

Implemented:

- Preserved the 11-page controlling PDF under `specs_pack/source/`.
- Created searchable extracted text under `specs_pack/extracted/`.
- Expanded backend reporting models, indexes, report catalog, custom datasets, exports, saved/shared definitions, schedule contracts, and run/export history.
- Rebuilt the `/reports` frontend workspace under `Business & Finance -> Reports`.
- Added focused backend and frontend tests.
- Review correction: replaced every standard inventory row status with either `IMPLEMENTED AND VERIFIED` or `BLOCKED — NOT COMPLETE`; blocked rows are not represented by fake totals, fake export buttons, or disconnected placeholders.
- Review correction: blocked unsupported calculated fields, comparison periods, dashboard-widget publishing, specialized accounting/payroll/tax exports, and duplicate schedule runs instead of silently accepting them.

Known blocked requirements remain not complete and are not presented as finished:

- Dashboard widget publishing waits for Dashboard Customizer contracts.
- Detailed Webstore payout analytics waits for Webstore payout/source-contract completion.
- Deep Wrap Lab workflow analytics waits for Wrap Lab workflow/source-contract completion.
- Specialized accounting/payroll/tax exports wait for explicit downstream export schemas and are blocked at the API until those schemas exist.
- Payroll tax filing exports wait for payroll withholding/statutory deduction contracts.
- Automated production report delivery waits for a background scheduler/delivery contract; manual schedule runs and run history are implemented.

Verification recorded in `/app/evidence/REPORT_BUILDER_COMPLETE_REPORTING_SYSTEM_EVIDENCE.md`.

## Review Correction Verification - 2026-07-29

- Requirement inventory rows: 207 total; 34 `IMPLEMENTED AND VERIFIED`; 173 `BLOCKED — NOT COMPLETE`; 0 other status values.
- Focused backend reports suite: `12 passed, 6 warnings`.
- Report-adjacent backend regressions: `26 passed, 6 warnings`.
- Full backend suite: `1034 passed, 12 failed, 3 skipped, 6 warnings`; the same 12 failures reproduce on clean `main` and are pre-existing pricing/snapshot/direct-consumer/portable-config failures.
- Focused frontend Reports suite: `4 passed`.
- Full frontend suite: `18 suites passed, 91 tests passed`.
- Frontend production build: compiled successfully.
- Backend compile/import validation: passed.
- `git diff --check`: passed with CRLF conversion warnings only.
- Live browser verification at `/reports`: authenticated Reports workspace loaded, standard report ran, drill-down links rendered, generic exports were visible, specialized export labels were hidden, custom builder ran against approved datasets, saved report creation worked, schedule creation/manual run worked, export history updated, console errors were `0`, and no horizontal document overflow was observed at desktop width.
