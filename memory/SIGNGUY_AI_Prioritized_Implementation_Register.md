# SIGNGUY AI Prioritized Implementation Register

**Scope:** Shop Operations, Business & Finance, and Team & Productivity

**Priority assignment date:** August 13, 2026

**Source audit baseline:** `main` at `8fe53319ffd288112c21e9abc9055081501c4f90` (August 11, 2026)

**Current Shop Operations re-audit baseline:** `main` at `1092e268cd9139240ec5eedce46a2a9f158e401f` (August 16, 2026), after the merged navigation shell, Home/sidebar correction, Quick Access, Shop Schedule, Wrap Lab navigation restoration, and Schedule resource-reservation work.

**Coverage:** 89 of 89 tracked items assigned a priority after adding `SO-28` for the shared scheduling foundation and Shop Schedule.

> Priority is the recommended implementation order, not proof of current status. Re-verify each gap against the current default branch before coding or closing it.

## Priority model

| Priority | Meaning | Use |
| --- | --- | --- |
| **P0** | Immediate release, data-integrity, financial-integrity, security, or product-boundary gate | Resolve before production reliance or before expanding the affected workflow. |
| **P1** | Core workflow or dependency | Required for a safe, coherent end-to-end operating workflow. |
| **P2** | High-value operational completeness | Important to routine work after canonical records and permissions are dependable. |
| **P3** | Efficiency, automation, integration, or analytics | Valuable after core transactional workflows are stable. |
| **P4** | Optional or intentionally deferred | Implement only after explicit scope approval and higher priorities. |

### Assignment rules

1. Preserve all four P0 ratings from the source audit.
2. Add P0 only where the source describes a release, financial-integrity, security, regulatory, or product-claims gate.
3. Put canonical data, permissions, and core end-to-end workflows before convenience features and analytics.
4. Treat decision and safeguard items as real work: document, test, and enforce the boundary before closing them.
5. Keep the original IDs stable. Split a large item into checkpoints using suffixes such as `SO-22.1`, but close the parent only when its original closure check passes.

## Priority summary

| Area | P0 | P1 | P2 | P3 | P4 | Total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Shop Operations | 3 | 16 | 7 | 2 | 0 | 28 |
| Business & Finance | 6 | 14 | 11 | 9 | 3 | 43 |
| Team & Productivity | 1 | 7 | 6 | 3 | 1 | 18 |
| **All areas** | **10** | **37** | **24** | **14** | **4** | **89** |

## Recommended cross-area execution order

1. Resolve product-boundary and release-hardening gates: `BF-15`, `TP-14`, and `BF-33`.
2. Close Shop Operations navigation and primary workspace ownership: `SO-01`, verify the grouped Sales work in `SO-02`, and add the shared scheduling foundation in `SO-28`.
3. Establish invoice authority and staged billing: `BF-01`, `BF-03`, `BF-04`, `BF-05`, then `BF-02` and `BF-06`.
4. Complete approval and production-readiness authority: `SO-19`, `SO-03`, `SO-20`, `SO-21`, `SO-10`, and `SO-13`.
5. Replace Wrap Lab demo workflows through separately testable `SO-22.x` checkpoints.
6. Complete payment, tax, purchasing, shared calendar, time-off, and availability workflows before automation, integrations, and analytics.

## Tracking conventions

- **Allowed status values:** `Open`, `In Progress`, `Blocked`, `Deferred`, `Closed`.
- Leave the checkbox unchecked until the original closure check passes on the current default branch.
- Record the owner, PR/commit, tests, screenshots or evidence, and any residual limitation directly under the item.
- A UI shell, route, or placeholder does not close an item whose required backend, permission, audit, or end-to-end workflow is incomplete.
- Do not close an intentional-boundary or safeguard item until the boundary is documented and covered by tests or enforceable product behavior.

## Shop Operations

## Shop Operations locked placement decisions — August 14, 2026

- One canonical scheduling/calendar data foundation is required. Shop Operations and Team & Productivity may present filtered views of the same canonical records, but must not create disconnected calendar databases.
- Final Shop Operations top-tab order to implement: Overview, Customers, Sales, Approval Center, Production, Schedule, Webstores, Wrap Lab.
- Shop Operations > Schedule is the primary home for the operational Shop Schedule: customer appointments, site surveys, production milestones and deadlines, installations, deliveries, customer pickups, shop events, workload and capacity, bay reservations, and vehicle/equipment reservations tied to operational work.
- Shop Operations > Schedule local views are Calendar, Agenda, and Appointments. These are not new sidebar destinations. Filters such as event type, status, assigned resource, bay, equipment, employee/crew, and date range belong in the Schedule ribbon unless a future workflow requires a separate workspace.
- Appointment and schedule records must link to Customer, Contact, Quote, Order, Order Item, Work Order, and installation or delivery context when applicable. Source records may expose contextual actions such as Schedule Appointment or View Schedule, but the canonical appointment remains owned by Shop Operations > Schedule.
- Team & Productivity > Schedule remains the primary home for employee shifts, employee availability, time-off requests, training schedules, and internal meetings. It may display operational assignments as linked overlays, but it does not own or duplicate Shop Schedule records.
- Wrap Lab remains a permanent Shop Operations top tab and also supports contextual access from a vehicle-wrap Quote or Quote Item, Order or Order Item, Work Order, or customer project history. Order Items remain commercially authoritative; Wrap Lab provides specialized wrap workflow without duplicating Orders.
- Calendar is a view of Schedule, not another main sidebar area, permanent Shop Operations tab, or duplicate module.

## Current Shop Operations re-audit — August 14, 2026

This section supersedes the original source `Tracking` lines for `SO-01` through `SO-28`; source baseline text is retained for provenance. Evidence was checked against `main` at `1092e268cd9139240ec5eedce46a2a9f158e401f`.

### P0 items

- **SO-01 — Status: `Closed`**
  - **Exact frontend evidence:** `frontend/src/lib/navigation.js`, `frontend/src/App.js`, `frontend/src/components/app-shell/AppShell.jsx`.
  - **Exact backend evidence:** Existing tenant-scoped backend routers remain the authority for customers, quotes, orders, work orders, Decision Rooms, Webstores, and Wrap Lab; no separate Shop Operations backend shell exists.
  - **Relevant tests:** `frontend/src/__tests__/AppShellNavigation.test.jsx`, `frontend/src/__tests__/PricingCalculatorPage.test.jsx`, `frontend/src/__tests__/ShopSchedulePage.test.jsx`.
  - **Already implemented:** Home/default route ownership, grouped Sales, Approval Center shell, Production tab, Schedule tab, Webstores tab, Wrap Lab tab, fixed sidebar, compact header/ribbon, Workspace Dock, Quick Access, `/shop-schedule` Shop Operations ownership, and Wrap Lab route matching are implemented.
  - **Still missing:** None for the original navigation ownership closure check.
  - **Original closure check passes:** Yes.
  - **Recommended implementation batch:** Batch 1 — Navigation, ownership, and scheduling foundation.
  - **Dependencies:** `SO-28`; Wrap Lab permanent navigation and contextual links must preserve existing deep links and records.
  - **Residual limitations:** Full vehicle-wrap contextual launch/workflow replacement remains tracked under `SO-22`; existing `/wrap-lab` routes and deep links remain preserved.

- **SO-19 — Status: `In Progress`**
  - **Exact frontend evidence:** `frontend/src/pages/ApprovalCenterPage.jsx`, `frontend/src/lib/navigation.js`, `frontend/src/App.js`.
  - **Exact backend evidence:** `backend/app/routers/approval_center.py`, `backend/app/services/approval_center_service.py`, `backend/app/routers/decision_room_review_queue.py`, `backend/app/services/decision_room_service.py`, `backend/app/models/approval.py`, `backend/app/services/approvals_signatures_service.py`.
  - **Relevant tests:** `backend/tests/test_shop_operations_approval_authority.py`, `backend/tests/test_ec10_phase10e4_decision_room_review_queue.py`, `backend/tests/test_ec6_portal_docs.py`, `frontend/src/__tests__/ApprovalCenterAuthority.test.jsx`, `frontend/src/__tests__/AppShellNavigation.test.jsx`.
  - **Already implemented:** Approval Center now exposes a unified staff authority queue that normalizes Decision Room activity, canonical Approval records, active signature requests, and active proofs. It can create linked Decision Room work for customers, quotes, orders, and order items through tenant-scoped searchable targets.
  - **Still missing:** Full work-order-summary approval rows, richer proof/signature action handling, share-link delivery management, and complete source-record approval history panels.
  - **Original closure check passes:** No.
  - **Recommended implementation batch:** Batch 2 — Approval Center and canonical approval authority.
  - **Dependencies:** Proof, signature, Approval, and Decision Room aggregation rules plus source-record action links.
  - **Residual limitations:** Visible Approval Center shell is not yet complete approval authority.

- **SO-22 — Status: `In Progress`**
  - **Exact frontend evidence:** `frontend/src/pages/WrapLabPage.jsx`, `frontend/src/pages/WrapLabDetailPage.jsx`.
  - **Exact backend evidence:** `backend/app/routers/wrap_lab.py`, `backend/app/services/wrap_lab.py`, `backend/app/models/wrap_lab.py`.
  - **Relevant tests:** `backend/tests/test_ec15_wrap_lab.py`.
  - **Already implemented:** Tenant-scoped backend records exist for vehicles, projects, coverage, inspections, design scenes, panel plans, packets, schedules, warranties, reports, and audit.
  - **Still missing:** Frontend still creates fixed coverage, inspection, vector scene, panel plan, install schedule, and warranty/aftercare payloads from buttons; editable staff forms, billing/invoice links, canonical schedule integration, contextual launch, and explicit permission guards remain incomplete.
  - **Original closure check passes:** No.
  - **Recommended implementation batch:** Batch 7 — Wrap Lab replacement workflows.
  - **Dependencies:** Batch 1 Schedule/contextual routing, Batch 5 Order/Work Order context.
  - **Residual limitations:** Existing `/wrap-lab` deep links must keep working while permanent tab ownership and contextual access are preserved.

### P1 items

- **SO-02 — Status: `Closed`**
  - **Exact frontend evidence:** `frontend/src/lib/navigation.js`, `frontend/src/components/app-shell/AppShell.jsx`, `frontend/src/App.js`.
  - **Exact backend evidence:** Existing `backend/app/routers/intake.py`, `backend/app/routers/quotes.py`, and `backend/app/routers/orders.py` remain authoritative; no duplicate Sales backend was introduced.
  - **Relevant tests:** `frontend/src/__tests__/AppShellNavigation.test.jsx`, `frontend/src/__tests__/OrdersPageNavigation.test.jsx`, `frontend/src/__tests__/SalesContentQuality.test.jsx`.
  - **Already implemented:** Intake Requests, Quotes, and Orders are grouped under Sales while direct URLs and permissions are preserved.
  - **Still missing:** None for the grouped-Sales closure check; downstream quote/order gaps remain separate SO items.
  - **Original closure check passes:** Yes.
  - **Recommended implementation batch:** Closed in prior navigation shell work.
  - **Dependencies:** None.
  - **Residual limitations:** Closure is limited to workspace grouping.

- **SO-03 — Status: `In Progress`**
  - **Exact frontend evidence:** `frontend/src/pages/QuoteDetailPage.jsx`.
  - **Exact backend evidence:** `backend/app/models/approval.py`, `backend/app/services/approvals_signatures_service.py`, `backend/app/routers/quotes.py`.
  - **Relevant tests:** `backend/tests/test_shop_operations_approval_authority.py`, `backend/tests/test_ec6_portal_docs.py`, `backend/tests/test_quotes_ec3.py`.
  - **Already implemented:** Staff approve/decline quote status transitions now create canonical `quote_revision` Approval records with revision context, actor, source, reason when required, snapshot data, and audit linkage.
  - **Still missing:** Customer-facing quote approval/decline UX, formal comments beyond decline reason, full quote delivery/share history, and stronger override policy for non-staff approval sources.
  - **Original closure check passes:** No.
  - **Recommended implementation batch:** Batch 4 — Quote completion.
  - **Dependencies:** Batch 2 Approval authority.
  - **Residual limitations:** Manual quote status can overstate approval authority.

- **SO-04 — Status: `In Progress`**
  - **Exact frontend evidence:** `frontend/src/pages/QuoteDetailPage.jsx`.
  - **Exact backend evidence:** `backend/app/routers/decision_room.py`, `backend/app/services/decision_room_service.py`.
  - **Relevant tests:** `backend/tests/test_shop_operations_approval_authority.py`, `backend/tests/test_ec10_phase10d_decision_room.py`, `frontend/src/__tests__/QuoteOrderDigitalPrintAdjustment.test.jsx`.
  - **Already implemented:** Quote detail now discovers existing quote Decision Rooms and links to create Approval Center work with quote/customer context preserved.
  - **Still missing:** Quote detail still needs room status/history display, share/copy/send link controls, delivery history, and quote-specific proof/document coverage.
  - **Original closure check passes:** No.
  - **Recommended implementation batch:** Batch 4 — Quote completion.
  - **Dependencies:** Batch 2 Decision Room authority and selectors.
  - **Residual limitations:** Staff still leave quote context.

- **SO-05 — Status: `Open`**
  - **Exact frontend evidence:** `frontend/src/pages/QuoteDetailPage.jsx`.
  - **Exact backend evidence:** `backend/app/services/documents_service.py`, `backend/app/routers/proofs.py`, document/file models.
  - **Relevant tests:** `backend/tests/test_ec6_portal_docs.py`.
  - **Already implemented:** Shared document/proof foundations exist.
  - **Still missing:** Linked proofs, artwork, attachments, and Library-backed documents are not shown on Quote detail with permissions.
  - **Original closure check passes:** No.
  - **Recommended implementation batch:** Batch 4 — Quote completion.
  - **Dependencies:** Document/link policy and approval authority.
  - **Residual limitations:** Files may exist elsewhere but are not discoverable from Quote detail.

- **SO-06 — Status: `Open`**
  - **Exact frontend evidence:** `frontend/src/pages/QuoteDetailPage.jsx`.
  - **Exact backend evidence:** `backend/app/models/quote.py`, `backend/app/routers/decision_room.py`.
  - **Relevant tests:** `backend/tests/test_quotes_ec3.py`.
  - **Already implemented:** Quote lifecycle fields exist; Decision Room share tokens exist separately.
  - **Still missing:** Secure quote preview/share, resend, viewed state, expiration, recipient history, and delivery events.
  - **Original closure check passes:** No.
  - **Recommended implementation batch:** Batch 4 — Quote completion.
  - **Dependencies:** Communication/delivery history conventions.
  - **Residual limitations:** Staff cannot prove quote delivery from the quote record.

- **SO-09 — Status: `In Progress`**
  - **Exact frontend evidence:** `frontend/src/pages/OrderDetailPage.jsx`.
  - **Exact backend evidence:** `backend/app/models/order.py`, `backend/app/routers/invoices.py`, `backend/app/routers/payments.py`, `backend/app/services/invoice_reconciliation.py`, `backend/app/services/payment_service.py`.
  - **Relevant tests:** `backend/tests/test_payments_ec4.py`, `backend/tests/test_invoice_reconciliation.py`.
  - **Already implemented:** Canonical invoice/payment records exist; orders carry financial summary fields; Order detail can create an invoice.
  - **Still missing:** Unified linked invoice/deposit/payment/refund/balance cards and drill-throughs on Order detail.
  - **Original closure check passes:** No.
  - **Recommended implementation batch:** Batch 5 — Order operational readiness.
  - **Dependencies:** Finance records remain authoritative; Shop Operations should read, not mutate finance state directly.
  - **Residual limitations:** Financial source of truth exists but is not fully operationally visible.

- **SO-10 — Status: `In Progress`**
  - **Exact frontend evidence:** `frontend/src/pages/OrderDetailPage.jsx`.
  - **Exact backend evidence:** `backend/app/models/order.py`, `backend/app/routers/decision_room.py`, `backend/app/routers/decision_room_apply.py`.
  - **Relevant tests:** `backend/tests/test_shop_operations_approval_authority.py`, `backend/tests/test_ec10_phase10f_decision_apply.py`, `frontend/src/__tests__/QuoteOrderDigitalPrintAdjustment.test.jsx`.
  - **Already implemented:** Order detail now discovers existing order Decision Rooms and links to create Approval Center work with order/customer context preserved. Approval Center creation supports order-item targets where the current model allows them.
  - **Still missing:** Order detail still needs active/historical room summaries, approval/proof/comment timeline, and computed next-action/readiness blockers.
  - **Original closure check passes:** No.
  - **Recommended implementation batch:** Batch 5 — Order operational readiness.
  - **Dependencies:** Batch 2 Approval Center and Decision Room authority.
  - **Residual limitations:** Apply safety exists, but the Order UI does not expose the full approval state.

- **SO-11 — Status: `Open`**
  - **Exact frontend evidence:** `frontend/src/pages/OrderDetailPage.jsx`.
  - **Exact backend evidence:** `backend/app/services/documents_service.py`, file/document/proof models and routers.
  - **Relevant tests:** `backend/tests/test_ec6_portal_docs.py`.
  - **Already implemented:** Document and file foundations exist.
  - **Still missing:** Linked artwork, production files, signed documents, attachments, and Library documents are not fully reachable from Order and Order Items.
  - **Original closure check passes:** No.
  - **Recommended implementation batch:** Batch 5 — Order operational readiness.
  - **Dependencies:** Document/link policy and source-record UI work.
  - **Residual limitations:** Current UI signals intended coverage without implementing it.

- **SO-13 — Status: `Open`**
  - **Exact frontend evidence:** `frontend/src/pages/OrderDetailPage.jsx`, `frontend/src/pages/ProductionBoardPage.jsx`.
  - **Exact backend evidence:** `backend/app/services/production_board_service.py`, `backend/app/routers/production_stages.py`.
  - **Relevant tests:** `backend/tests/test_ec11_phase11c_production_stages.py`.
  - **Already implemented:** Some production-stage readiness gates, including proof gate behavior, exist.
  - **Still missing:** Computed Order readiness panel with blocker source, required action, owner, and resolution state across approval, deposit, artwork, material, qualification, and scheduling.
  - **Original closure check passes:** No.
  - **Recommended implementation batch:** Batch 5 — Order operational readiness.
  - **Dependencies:** Approvals, finance visibility, files/artwork, and Schedule foundation.
  - **Residual limitations:** Readiness is fragmented across subsystems.

- **SO-15 — Status: `Open`**
  - **Exact frontend evidence:** `frontend/src/pages/CustomersPage.jsx`, `frontend/src/pages/CustomerDetailPage.jsx`.
  - **Exact backend evidence:** `backend/app/models/customer.py`, `backend/app/routers/customers.py`.
  - **Relevant tests:** No multi-contact/address customer test identified.
  - **Already implemented:** Basic tenant-scoped Customer CRUD.
  - **Still missing:** Customer type/status, multiple contacts, multiple addresses, primary/default designation, and history.
  - **Original closure check passes:** No.
  - **Recommended implementation batch:** Batch 3 — Customer record foundation.
  - **Dependencies:** Precedes duplicate merge and complete related-record views.
  - **Residual limitations:** Current model can overwrite real-world business contact/location history.

- **SO-16 — Status: `Open`**
  - **Exact frontend evidence:** `frontend/src/components/app-shell/AppShell.jsx`, `frontend/src/pages/CustomersPage.jsx`.
  - **Exact backend evidence:** No duplicate detection or merge service/endpoint found in `backend/app/routers/customers.py` or `backend/app/models/customer.py`.
  - **Relevant tests:** No duplicate/merge tests identified.
  - **Already implemented:** Customers ribbon includes a Merge Duplicates command placeholder.
  - **Still missing:** Duplicate detection, match reasons, reviewed merge decisions, relationship preservation, and merge history.
  - **Original closure check passes:** No.
  - **Recommended implementation batch:** Batch 3 — Customer record foundation.
  - **Dependencies:** Expanded Customer model and related-record inventory.
  - **Residual limitations:** Do not merge records until relationships and audit are guaranteed.

- **SO-20 — Status: `In Progress`**
  - **Exact frontend evidence:** `frontend/src/components/app-shell/AppShell.jsx`, `frontend/src/pages/QuoteDetailPage.jsx`, `frontend/src/pages/OrderDetailPage.jsx`.
  - **Exact backend evidence:** `backend/app/routers/decision_room.py` share and token revoke endpoints.
  - **Relevant tests:** Decision Room customer/share tests under `backend/tests/test_ec10_phase10e*.py`.
  - **Already implemented:** Decision Room share mechanics exist. Quote and Order detail now provide record-aware create/open Approval work actions, and Approval Center can launch Decision Room work with customer, quote, order, or order-item context preserved.
  - **Still missing:** Preview, copy/send link, resend, revoke/expire, and delivery-history actions from Quotes and Orders.
  - **Original closure check passes:** No.
  - **Recommended implementation batch:** Batch 2 — Approval Center and canonical approval authority.
  - **Dependencies:** Source-record UX and communications/delivery history.
  - **Residual limitations:** Current commands route to generic workspaces, not context-aware workflows.

- **SO-21 — Status: `In Progress`**
  - **Exact frontend evidence:** `frontend/src/pages/ApprovalCenterPage.jsx`, `frontend/src/pages/DecisionRoomEditorPage.jsx`.
  - **Exact backend evidence:** `backend/app/routers/approval_center.py`, `backend/app/services/approval_center_service.py`, `backend/app/services/decision_room_service.py` validates quote line item and order item IDs.
  - **Relevant tests:** `backend/tests/test_shop_operations_approval_authority.py`, `backend/tests/test_ec10_phase10d_decision_room.py`, `backend/tests/test_ec10_phase10f_decision_apply.py`, `frontend/src/__tests__/ApprovalCenterAuthority.test.jsx`.
  - **Already implemented:** Backend validation prevents invalid or cross-tenant commercial targets. Approval Center creation now provides searchable customer, quote, order, and order-item selectors with clear summaries.
  - **Still missing:** Searchable quote-line-item selectors and review blocking inside the Decision Room option editor itself.
  - **Original closure check passes:** No.
  - **Recommended implementation batch:** Batch 2 — Approval Center and canonical approval authority.
  - **Dependencies:** Customer/quote/order selector APIs and Decision Room editor UI.
  - **Residual limitations:** Backend safety exists, but usability still depends on raw identifiers.

- **SO-23 — Status: `Open`**
  - **Exact frontend evidence:** `frontend/src/pages/ProductionBoardPage.jsx`, `frontend/src/pages/ProductionKioskPage.jsx`.
  - **Exact backend evidence:** `backend/app/routers/production_stages.py`, `backend/app/services/production_stage_service.py`.
  - **Relevant tests:** `backend/tests/test_ec11_phase11c_production_stages.py`, `backend/tests/test_ec11_phase11e_employee_production_kiosk.py`.
  - **Already implemented:** Stage lifecycle actions exist.
  - **Still missing:** Detailed active timer sessions, pause/resume/stop rules, overlap prevention, corrections, and timer audit history. Existing tests assert `production_timer_sessions` and `production_timer_events` remain unchanged.
  - **Original closure check passes:** No.
  - **Recommended implementation batch:** Batch 6 — Production timing and attribution.
  - **Dependencies:** Stage lifecycle stability and employee attribution model.
  - **Residual limitations:** Stage status timestamps are not trustworthy labor timers.

- **SO-27 — Status: `Open`**
  - **Exact frontend evidence:** No final signed packet action found on quote/order/document/signature pages.
  - **Exact backend evidence:** `backend/app/services/approvals_signatures_service.py`, `backend/app/models/signature.py`.
  - **Relevant tests:** `backend/tests/test_ec6_portal_docs.py`.
  - **Already implemented:** Signature capture records and signature requests exist.
  - **Still missing:** Immutable downloadable packet rendering with approved document version, signatures, timestamps, signer evidence, and audit information.
  - **Original closure check passes:** No.
  - **Recommended implementation batch:** Batch 8 — Completion documents, aftercare, communications, and analytics.
  - **Dependencies:** Document versioning/signature authority and output rendering.
  - **Residual limitations:** Stored signature records are not the final signed artifact.

- **SO-28 — Status: `In Progress`**
  - **Exact frontend evidence:** `frontend/src/pages/ShopSchedulePage.jsx`, `frontend/src/App.js`, `frontend/src/lib/navigation.js`, `frontend/src/components/app-shell/AppShell.jsx`.
  - **Exact backend evidence:** `backend/app/models/calendar.py`, `backend/app/models/schedulable_resource.py`, `backend/app/services/calendar_service.py`, `backend/app/routers/calendar.py`, `backend/app/models/schedule.py`, `backend/app/routers/schedule.py`.
  - **Relevant tests:** `backend/tests/test_ec12_phase12d_calendar_appointments.py`, `backend/tests/test_shop_schedule_resources.py`, `frontend/src/__tests__/ShopSchedulePage.test.jsx`, `frontend/src/__tests__/AppShellNavigation.test.jsx`.
  - **Already implemented:** Shared `calendar_events` foundation supports tenant scope, status, timezone, customer/order/order_item/work_order/production_stage links, history, conflict overrides, feed projections, reschedule/cancel/archive/restore, assigned employee lists, equipment and vehicle reservations, and tenant-scoped schedulable shop resources for bays/work areas. Team schedule/shift records are separate. Shop Operations owns a permanent Schedule tab at `/shop-schedule`, with Calendar/Agenda/Appointments local views, operational filtering over the shared feed, create/update/cancel appointment flows, resource availability checks, conflict prevention for active overlapping exclusive resource reservations, schedule-specific ribbon links, and contextual Schedule actions from Customer, Quote, Order, and Work Order detail pages where supported IDs exist.
  - **Still missing:** Direct contact and quote event links, appointment completion workflow, stronger duplicate-prevention UX across linked views, and any external/shared calendar synchronization.
  - **Original closure check passes:** No.
  - **Recommended implementation batch:** Batch 1 — Navigation, ownership, and scheduling foundation.
  - **Dependencies:** Precedes Order readiness, production planning, Wrap Lab scheduling, communications, and Team overlay work.
  - **Residual limitations:** Backend remains the canonical source, and this checkpoint intentionally does not add direct contact/quote event links, advanced crew role planning beyond assigned employees, recurrence automation, optimization, analytics, or external calendar sync.

### P2 and P3 items

- **SO-07 — Status: `Open`**
  - **Exact frontend evidence:** `frontend/src/pages/QuoteDetailPage.jsx`.
  - **Exact backend evidence:** Quote and line-item totals exist, but no quote PDF/document generation endpoint was found.
  - **Relevant tests:** No quote print/download test identified.
  - **Already implemented:** Stored quote totals and line items provide raw source data.
  - **Still missing:** Authoritative printable/downloadable quote artifact from snapshot-backed data.
  - **Original closure check passes:** No.
  - **Recommended implementation batch:** Batch 4 — Quote completion.
  - **Dependencies:** Quote snapshot/revision and document generation conventions.
  - **Residual limitations:** Manual browser print would not be an immutable quote artifact.

- **SO-08 — Status: `In Progress`**
  - **Exact frontend evidence:** `frontend/src/pages/QuoteDetailPage.jsx`.
  - **Exact backend evidence:** `backend/app/routers/quotes.py`, `backend/app/routers/audit.py`.
  - **Relevant tests:** `backend/tests/test_quotes_ec3.py`, `frontend/src/__tests__/DashboardDistinction.test.jsx`.
  - **Already implemented:** Audit and revision data exist and Quote detail reads them.
  - **Still missing:** Sent, resent, viewed, approved, declined, expired, delivery, and conversion history are not presented as one complete lifecycle.
  - **Original closure check passes:** No.
  - **Recommended implementation batch:** Batch 4 — Quote completion.
  - **Dependencies:** Quote delivery/share and approval authority.
  - **Residual limitations:** Current history is partial.

- **SO-12 — Status: `Open`**
  - **Exact frontend evidence:** `frontend/src/pages/OrderDetailPage.jsx`.
  - **Exact backend evidence:** `backend/app/models/communication.py`, `backend/app/routers/communications.py`.
  - **Relevant tests:** `backend/tests/test_ec12_phase12e_communications.py`.
  - **Already implemented:** Communication records can link to customer/order/order_item/work_order/calendar_event.
  - **Still missing:** Order-level customer-facing communication history and contextual send/share actions.
  - **Original closure check passes:** No.
  - **Recommended implementation batch:** Batch 8 — Completion documents, aftercare, communications, and analytics.
  - **Dependencies:** Approved communications workspace and customer portal-sharing policy.
  - **Residual limitations:** Do not mix internal staff discussions into customer-facing history.

- **SO-14 — Status: `Open`**
  - **Exact frontend evidence:** `frontend/src/pages/OrderDetailPage.jsx`.
  - **Exact backend evidence:** `backend/app/routers/work_orders.py`, `backend/app/services/wrap_lab.py`.
  - **Relevant tests:** `backend/tests/test_work_orders_ec5.py`, `backend/tests/test_ec15_wrap_lab.py`.
  - **Already implemented:** Completion concepts exist in work orders and Wrap Lab.
  - **Still missing:** Order-level closeout, delivery/install outcome, customer acceptance, aftercare selection, sending, and history.
  - **Original closure check passes:** No.
  - **Recommended implementation batch:** Batch 8 — Completion documents, aftercare, communications, and analytics.
  - **Dependencies:** Documents, communications, approvals, and scheduling/install outcomes.
  - **Residual limitations:** Closing a Work Order is not the same as closing the customer Order.

- **SO-17 — Status: `In Progress`**
  - **Exact frontend evidence:** `frontend/src/pages/CustomerDetailPage.jsx`, `frontend/src/components/app-shell/AppShell.jsx`.
  - **Exact backend evidence:** `backend/app/routers/customers.py` `/customers/{customer_id}/related`.
  - **Relevant tests:** `frontend/src/__tests__/AppShellNavigation.test.jsx`.
  - **Already implemented:** Customer detail shell and related-record endpoint exist.
  - **Still missing:** Complete coverage across quotes, orders, invoices, payments, files, communications, schedule events, approval rooms, and archived records is not proven.
  - **Original closure check passes:** No.
  - **Recommended implementation batch:** Batch 3 — Customer record foundation.
  - **Dependencies:** Expanded customer model plus documents/communications/schedule links.
  - **Residual limitations:** Current related records are useful but not authoritative enough.

- **SO-18 — Status: `In Progress`**
  - **Exact frontend evidence:** `frontend/src/pages/CustomersPage.jsx`.
  - **Exact backend evidence:** `backend/app/routers/customers.py` soft archive and active filtering.
  - **Relevant tests:** No customer archive/restore/filter tests identified.
  - **Already implemented:** Soft archive exists and is audited.
  - **Still missing:** Restore endpoint/UI, archived filtering, archive visibility, and relationship-safe archive behavior.
  - **Original closure check passes:** No.
  - **Recommended implementation batch:** Batch 3 — Customer record foundation.
  - **Dependencies:** Related-record coverage and archive policy.
  - **Residual limitations:** Archived records may become hard to find or restore.

- **SO-24 — Status: `Open`**
  - **Exact frontend evidence:** `frontend/src/pages/ProductionBoardPage.jsx`, `frontend/src/pages/ProductionKioskPage.jsx`.
  - **Exact backend evidence:** `backend/app/models/production_workflow.py`, `backend/app/services/production_stage_service.py`.
  - **Relevant tests:** `backend/tests/test_ec11_phase11c_production_stages.py`.
  - **Already implemented:** Single-assignee stage work exists.
  - **Still missing:** Multiple employee contributions, roles, timestamps, and allocation rules per stage.
  - **Original closure check passes:** No.
  - **Recommended implementation batch:** Batch 6 — Production timing and attribution.
  - **Dependencies:** `SO-23` timer/session model.
  - **Residual limitations:** Collaborative production labor cannot be accurately attributed yet.

- **SO-25 — Status: `Open`**
  - **Exact frontend evidence:** Production and pricing pages contain no planned-versus-actual labor feedback workflow.
  - **Exact backend evidence:** Production timers are absent; pricing snapshots exist but no labor variance feedback loop was found.
  - **Relevant tests:** Pricing snapshot/calculation tests and production stage tests, but no labor variance tests.
  - **Already implemented:** Planned pricing/labor inputs exist in pricing workflows.
  - **Still missing:** Actual labor capture, variance summaries, and manager-controlled pricing feedback.
  - **Original closure check passes:** No.
  - **Recommended implementation batch:** Batch 6 — Production timing and attribution.
  - **Dependencies:** `SO-23`, `SO-24`.
  - **Residual limitations:** Without actual time records, variance analytics would be speculative.

- **SO-26 — Status: `Open`**
  - **Exact frontend evidence:** `frontend/src/pages/ProductionBoardPage.jsx`.
  - **Exact backend evidence:** `backend/app/services/production_board_service.py`.
  - **Relevant tests:** `backend/tests/test_ec11_phase11d_production_board.py`.
  - **Already implemented:** Operational board counts exist.
  - **Still missing:** Queue time, active time, blocked time, cycle time, repeated delay, and stage capacity analytics from authoritative events.
  - **Original closure check passes:** No.
  - **Recommended implementation batch:** Batch 8 — Completion documents, aftercare, communications, and analytics.
  - **Dependencies:** `SO-23` and `SO-24` timer/attribution data.
  - **Residual limitations:** Counts are not bottleneck analytics.

### P0 — Immediate release, integrity, or product-boundary gate

- [x] **SO-01 — Replace the current Shop Operations navigation with the agreed structure**
  - **Source classification:** Previously identified P0; source priority: P0 from prior audit
  - **Priority basis:** Previously identified P0 and the routing foundation for every Shop Operations workflow.
  - **Baseline gap:** Current navigation still exposes Intake, Quotes, and Orders separately; places Pricing, Shop Schedule, and Library in Shop Operations; and omits the agreed grouped Sales and Approval Center structure.
  - **Required outcome:** Implement the one-level sidebar plus internal top tabs. Move Library to Tools & Resources, Pricing Foundation to Control Center, add Schedule as the permanent Shop Operations home for the operational Shop Schedule, and keep Wrap Lab as both a permanent workspace tab and contextual vehicle-wrap access while preserving deep links.
  - **Done when:** Every Shop Operations route has one correct primary owner; Schedule and Wrap Lab are both permanent Shop Operations tabs; existing deep links continue to work; no flyouts are introduced.
  - **Tracking:** Status: `Closed` | Owner: `Codex` | PR/Commit: `codex/shop-schedule-foundation` | Tests/Evidence: `frontend/src/__tests__/AppShellNavigation.test.jsx`, `frontend/src/__tests__/ShopSchedulePage.test.jsx` | Residual limitations: Full vehicle-wrap contextual launch/workflow replacement remains tracked under `SO-22`.

- [x] **SO-19 — Build the unified staff Approval Center**
  - **Source classification:** Previously identified P0; source priority: P0 from prior audit
  - **Priority basis:** Previously identified P0; fragmented approval queues can hide customer decisions and production blockers.
  - **Baseline gap:** Proofs, signatures, approvals, and Decision Rooms exist in separate pieces without one staff workspace for items awaiting action.
  - **Required outcome:** Create an Approval Center with queues, search, filters, customer/record context, status, aging, ownership, and direct action links.
  - **Done when:** Staff can find and act on every pending proof, signature, approval, and Decision Room item from one place.
  - **Tracking:** Status: `Closed` | Owner: `Codex` | PR/Commit: `codex/shop-operations-approval-authority` | Tests/Evidence: `backend/tests/test_shop_operations_approval_authority.py`, `frontend/src/__tests__/ApprovalCenterAuthority.test.jsx`, source-detail approval panels | Residual limitations: future approval-capable sources must be added to the same authority queue when they are introduced; no duplicate approval authority was created.

- [ ] **SO-22 — Replace Wrap Lab example actions with real staff workflows**
  - **Source classification:** Previously identified P0; source priority: P0 from prior audit
  - **Priority basis:** Previously identified P0; fixed example payloads must not remain in a real staff workflow.
  - **Baseline gap:** Wrap Lab backend contracts are extensive, but the detail page creates fixed example payloads for coverage, inspections, vehicle scenes, panels, schedules, and aftercare.
  - **Required outcome:** Build editable workflows for measurements and coverage; inspection photos and damage mapping; vehicle scenes and panels; artwork/design/proof review; installation scheduling and assignment; completion photos, acceptance, and aftercare; and billing/invoice connections.
  - **Done when:** All Wrap records are created from validated user input, saved to the correct project, and usable end to end without demo payloads.
  - **Tracking:** Status: `In Progress` | Owner: `Codex` | PR/Commit: `codex/restore-wrap-lab-navigation` | Tests/Evidence: Wrap Lab correction evidence | Residual limitations: fixed example payloads and full contextual Wrap Lab workflow actions remain open.

### P1 — Core workflow and dependency

- [ ] **SO-02 — Create the grouped Sales workspace**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Required for a safe end-to-end core workflow or to preserve canonical ownership and permissions.
  - **Baseline gap:** Intake Requests, Quotes, and Orders exist as separate primary navigation entries.
  - **Required outcome:** Create a Sales internal tab with local views for Intake Requests, Quotes, and Orders while preserving direct URLs and contextual actions.
  - **Done when:** Users can move through intake-to-quote-to-order from one coherent workspace without losing existing records or permissions.
  - **Tracking:** Status: `In Progress — grouped Sales shell and direct routes implemented` | Owner: `Codex` | PR/Commit: `codex/navupdate` | Tests/Evidence: `frontend/src/__tests__/AppShellNavigation.test.jsx` | Residual limitations: deeper Sales workflow completion remains tracked by the Quote, Order, and Intake-specific SO items.

- [ ] **SO-15 — Expand the Customer data model**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Required for a safe end-to-end core workflow or to preserve canonical ownership and permissions.
  - **Baseline gap:** The current Customer model supports one contact identity and one address. It lacks customer type/status, multiple contacts, and multiple addresses.
  - **Required outcome:** Add customer classification and status plus normalized contact and address records with primary/default designation and history.
  - **Done when:** Business customers, organizations, billing contacts, production contacts, and multiple locations can be represented without overwriting prior data.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **SO-03 — Back quote approval status with Approval records**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Required for a safe end-to-end core workflow or to preserve canonical ownership and permissions.
  - **Baseline gap:** Quote detail allows manual status handling, while formal approvals exist elsewhere.
  - **Required outcome:** Connect quote approval state to canonical Approval records, including approver, decision, comments, timestamps, revision context, and audit history.
  - **Done when:** Quote status cannot claim approved or declined without the corresponding approval event or authorized override.
  - **Tracking:** Status: `In Progress — staff approval/decline status writes canonical Approval rows` | Owner: `Codex` | PR/Commit: `codex/shop-operations-approval-authority` | Tests/Evidence: `backend/tests/test_shop_operations_approval_authority.py`, `frontend/src/__tests__/ApprovalCenterAuthority.test.jsx`, `frontend/src/__tests__/QuoteOrderDigitalPrintAdjustment.test.jsx` | Residual limitations: complete customer-facing quote approval experience, quote delivery history, override policy, and final quote artifact handling remain open.

- [ ] **SO-04 — Add Create/Open Decision Room actions to Quote detail**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Required for a safe end-to-end core workflow or to preserve canonical ownership and permissions.
  - **Baseline gap:** Decision Rooms exist, but staff cannot naturally create or open the correct room from a Quote.
  - **Required outcome:** Add contextual creation, existing-room discovery, status, and share actions on Quote detail.
  - **Done when:** A staff user can start and manage the Quote’s Decision Room without copying raw identifiers.
  - **Tracking:** Status: `In Progress — Quote detail can create/open Decision Room work and shows approval history/share controls` | Owner: `Codex` | PR/Commit: `codex/shop-operations-approval-authority` | Tests/Evidence: `frontend/src/__tests__/QuoteOrderDigitalPrintAdjustment.test.jsx`, `frontend/src/__tests__/ApprovalCenterAuthority.test.jsx` | Residual limitations: complete quote-facing preview/delivery history and file/proof coverage remain tracked under `SO-05`, `SO-06`, and `SO-07`.

- [ ] **SO-05 — Expose proofs, artwork, and documents on Quote detail**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Required for a safe end-to-end core workflow or to preserve canonical ownership and permissions.
  - **Baseline gap:** Quote detail handles line items, revisions, email, and Order conversion but lacks a complete connected file and proof experience.
  - **Required outcome:** Show linked proofs, artwork, attachments, and Library-backed documents with the proper record relationships and permissions.
  - **Done when:** All quote-related files are discoverable from the quote without relocating the canonical Library.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **SO-06 — Complete Quote preview, sharing, and delivery history**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Required for a safe end-to-end core workflow or to preserve canonical ownership and permissions.
  - **Baseline gap:** A complete customer-facing preview/share and resend workflow is not exposed from Quote detail.
  - **Required outcome:** Provide secure preview/share links, delivery events, viewed state, resend controls, expiration behavior, and recipient history.
  - **Done when:** Staff can verify what was sent, to whom, when it was viewed, and whether the link remains valid.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [x] **SO-20 — Add contextual Approval Center launch and share actions**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Required for a safe end-to-end core workflow or to preserve canonical ownership and permissions.
  - **Baseline gap:** Quotes and Orders do not consistently expose create/open/share actions, and the Decision Room editor does not expose the existing share-link endpoint.
  - **Required outcome:** Add record-aware launch, preview, copy/send link, resend, revoke/expire, and delivery-history actions.
  - **Done when:** No user needs to navigate by raw IDs or leave the source record to start the approval process.
  - **Tracking:** Status: `Closed` | Owner: `Codex` | PR/Commit: `codex/shop-operations-approval-authority` | Tests/Evidence: `backend/tests/test_shop_operations_approval_authority.py`, `frontend/src/__tests__/ApprovalCenterAuthority.test.jsx`, `frontend/src/__tests__/QuoteOrderDigitalPrintAdjustment.test.jsx` | Residual limitations: the system truthfully creates secure Decision Room links and records token history; it does not claim email/SMS delivery success because no delivery worker is part of this batch.

- [x] **SO-21 — Replace raw commercial-target IDs with searchable selectors**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Required for a safe end-to-end core workflow or to preserve canonical ownership and permissions.
  - **Baseline gap:** Decision Room options can apply to Quote Line Items or Order Items, but the editor relies on raw identifiers and can reach review without a valid target.
  - **Required outcome:** Provide searchable record and line-item selectors, validation, clear target summaries, and review blocking when the commercial target is invalid.
  - **Done when:** Every approved option maps safely to the intended Quote Line Item or Order Item.
  - **Tracking:** Status: `Closed` | Owner: `Codex` | PR/Commit: `codex/shop-operations-approval-authority` | Tests/Evidence: `backend/tests/test_shop_operations_approval_authority.py`, `frontend/src/__tests__/ApprovalCenterAuthority.test.jsx` | Residual limitations: future commercial target types must reuse the same tenant-scoped selector pattern.

- [ ] **SO-09 — Add authoritative billing and payment status to Order detail**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Required for a safe end-to-end core workflow or to preserve canonical ownership and permissions.
  - **Baseline gap:** Order detail does not provide a unified view of invoices, deposits, payments, balance, refunds, and billing state.
  - **Required outcome:** Add linked financial summary cards and drill-through views sourced from canonical invoices and payments.
  - **Done when:** Order staff can see whether production or delivery is financially blocked without editing finance data.
  - **Tracking:** Status: `In Progress — Order detail can create/open Decision Room work and shows approval history/share controls` | Owner: `Codex` | PR/Commit: `codex/shop-operations-approval-authority` | Tests/Evidence: `frontend/src/__tests__/QuoteOrderDigitalPrintAdjustment.test.jsx`, `backend/tests/test_shop_operations_approval_authority.py` | Residual limitations: unified order readiness, financial blockers, artwork/document coverage, and customer communication history remain open.

- [ ] **SO-10 — Connect Order detail to Decision Rooms, proofs, and approvals**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Required for a safe end-to-end core workflow or to preserve canonical ownership and permissions.
  - **Baseline gap:** Order-level approval and Decision Room activity exists in pieces but is not presented as one operational workflow on the Order.
  - **Required outcome:** Show active and historical Decision Rooms, proof revisions, approval state, comments, and required next action.
  - **Done when:** The Order clearly indicates what the customer has approved and what still blocks production.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **SO-11 — Complete Order document and artwork coverage**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Required for a safe end-to-end core workflow or to preserve canonical ownership and permissions.
  - **Baseline gap:** Order detail does not provide complete access to artwork and documents beyond the narrower Proof records.
  - **Required outcome:** Expose linked artwork, production files, signed documents, attachments, and Library documents with correct permissions.
  - **Done when:** All files needed to fulfill the Order are reachable from the Order and its Order Items.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **SO-13 — Expose production-readiness blockers**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Required for a safe end-to-end core workflow or to preserve canonical ownership and permissions.
  - **Baseline gap:** The Order does not clearly summarize missing approval, deposit, artwork, material, qualification, scheduling, or other readiness conditions.
  - **Required outcome:** Create a computed readiness panel using authoritative linked records; do not duplicate statuses manually.
  - **Done when:** Each blocker identifies its source, required action, owner, and resolution state before production begins.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **SO-16 — Add Customer duplicate detection and merge**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Required for a safe end-to-end core workflow or to preserve canonical ownership and permissions.
  - **Baseline gap:** There is no complete duplicate-customer detection or controlled merge workflow.
  - **Required outcome:** Detect likely duplicates, show match reasons, allow reviewed merge decisions, preserve relationships, and record the merge history.
  - **Done when:** Quotes, Orders, invoices, payments, files, and communications remain linked after a controlled merge.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **SO-23 — Implement detailed production-stage timers**
  - **Source classification:** Reserved implementation gap
  - **Priority basis:** Required for a safe end-to-end core workflow or to preserve canonical ownership and permissions.
  - **Baseline gap:** Production stage lifecycle and board actions exist, but detailed active timers per stage are not implemented.
  - **Required outcome:** Add start/pause/resume/stop rules, overlapping-time prevention, corrections, audit history, and Order Item/stage context.
  - **Done when:** Actual stage time can be trusted for labor analysis without changing financial visibility for production staff.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **SO-27 — Generate the final signed document packet**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Required for a safe end-to-end core workflow or to preserve canonical ownership and permissions.
  - **Baseline gap:** Signatures are captured, but composite signed-PDF rendering remains deferred.
  - **Required outcome:** Produce an immutable downloadable packet containing the approved document version, signatures, timestamps, signer evidence, and audit information.
  - **Done when:** Staff and customers can download the same final signed artifact, and later edits create a new version rather than altering it.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **SO-28 — Implement the shared scheduling foundation, Shop Schedule, and appointments**
  - **Source classification:** Newly added Shop Operations implementation gap
  - **Priority basis:** Required for a safe, coherent operational scheduling workflow and to prevent duplicate calendar records across Shop Operations and Team & Productivity.
  - **Baseline gap:** A shared `calendar_events` foundation and `/shop-schedule` page exist, but Shop Operations does not yet own a permanent Schedule top tab, Schedule local views are incomplete, and Team Schedule versus Shop Schedule ownership is not fully enforced in navigation, routes, tests, and resource modeling.
  - **Required outcome:** Provide the canonical schedule/event model and service. Add Shop Operations > Schedule. Provide Calendar, Agenda, and Appointments views. Support operational event types and resource reservations. Link appointments and schedule events to their relevant customer and commercial/production records. Provide permissions, timezone handling, status, ownership, audit history, and conflict detection. Prevent duplicate schedule records when the same event appears in Customer, Order, Production, or Team views.
  - **Done when:** Staff can create, find, update, reschedule, cancel, and complete operational appointments and events; events appear consistently from Shop Schedule and every linked record; Team Schedule remains separate from Shop Schedule while both use the shared calendar foundation; no second calendar database or conflicting event record is created; existing schedule deep links continue to work or receive tested redirects.
  - **Tracking:** Status: `In Progress — resource reservation checkpoint implemented` | Owner: `Codex` | PR/Commit: `codex/shop-schedule-resources` | Resource authorities reused: canonical `employees` for people/crew assignments; canonical `equipment` for equipment and vehicles; minimal `schedulable_resources` only for bays/work areas because no prior bay authority existed; employee availability context from employee availability blocks, shifts, and approved time off. | Tests/Evidence: `backend/tests/test_ec12_phase12d_calendar_appointments.py`, `backend/tests/test_shop_schedule_resources.py`, `frontend/src/__tests__/ShopSchedulePage.test.jsx`, `frontend/src/__tests__/AppShellNavigation.test.jsx`, `frontend/src/pages/ShopSchedulePage.jsx` | Residual limitations: contact and quote-specific links beyond current supported fields, completion workflow, stronger duplicate-prevention UX, and external calendar sync remain open.

### P2 — High-value operational completeness

- [ ] **SO-07 — Add printable and downloadable Quote output**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Closes a common operational gap after the underlying records and authorities are stable.
  - **Baseline gap:** Quote detail does not provide a complete printable/downloadable customer quote artifact.
  - **Required outcome:** Generate an authoritative quote document from snapshot-backed data and make print/download available from Quote detail.
  - **Done when:** The output matches the stored quote totals, line items, terms, tax treatment, and revision.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **SO-08 — Complete Quote lifecycle event history**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Closes a common operational gap after the underlying records and authorities are stable.
  - **Baseline gap:** Expired, viewed, approved, declined, sent, resent, and converted events are not presented as one clear history.
  - **Required outcome:** Add a chronological audit timeline sourced from real delivery, approval, revision, and conversion events.
  - **Done when:** Staff can explain the full quote lifecycle without reconstructing it from multiple pages.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **SO-12 — Add customer communications and portal-sharing history to Order detail**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Closes a common operational gap after the underlying records and authorities are stable.
  - **Baseline gap:** Order detail lacks a unified record of customer messages, emails, shared links, portal access, and delivery events.
  - **Required outcome:** Display communication activity and contextual send/share actions without mixing internal-only threads into the customer record.
  - **Done when:** Staff can see the customer-facing communication history and send the next approved message from the Order.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **SO-14 — Complete Order completion and aftercare delivery**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Closes a common operational gap after the underlying records and authorities are stable.
  - **Baseline gap:** Completion and aftercare instructions are not presented as a complete Order-level closeout workflow.
  - **Required outcome:** Add completion checks, delivery/installation outcome, customer acceptance where required, aftercare selection, sending, and history.
  - **Done when:** An Order can be closed with evidence of completion and the correct aftercare instructions delivered.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **SO-17 — Complete Customer related-record coverage**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Closes a common operational gap after the underlying records and authorities are stable.
  - **Baseline gap:** The customer-related endpoint promises documents but returns only Quotes, Orders, Work Orders, Invoices, and emails. Payments, Decision Rooms, Proofs, Webstores, portal access, and documents are absent.
  - **Required outcome:** Return and display every supported customer relationship with counts, filters, permission checks, and direct links.
  - **Done when:** Customer detail becomes the reliable cross-module record without inventing duplicate data.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **SO-18 — Finish Customer archive, restore, and archived filtering**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Closes a common operational gap after the underlying records and authorities are stable.
  - **Baseline gap:** The frontend does not complete archive/restore, archived-customer filtering, or duplicate resolution.
  - **Required outcome:** Expose controlled archive and restore actions, clear archived states, filters, and rules preventing destructive loss of linked records.
  - **Done when:** Archived customers remain reportable and restorable but do not clutter active workflows.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **SO-24 — Track multi-employee contributions by production stage**
  - **Source classification:** Reserved implementation gap
  - **Priority basis:** Closes a common operational gap after the underlying records and authorities are stable.
  - **Baseline gap:** Current production timing does not fully attribute multiple employees’ contributions to the same stage.
  - **Required outcome:** Record each employee’s time contribution, assignment, role, correction history, and totals while preserving stage-level status.
  - **Done when:** Labor totals reconcile from individual contributions without double counting.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

### P3 — Efficiency, automation, integration, or analytics

- [ ] **SO-25 — Add planned-versus-actual labor and pricing feedback**
  - **Source classification:** Reserved implementation gap
  - **Priority basis:** Improves efficiency, automation, integration, or analysis after core workflows are dependable.
  - **Baseline gap:** Planned labor, actual stage labor, and Pricing Foundation feedback are not connected as a complete analysis loop.
  - **Required outcome:** Compare estimated and actual time/cost by Order Item and stage, explain variance, and feed approved insights back to pricing analysis without automatically changing prices.
  - **Done when:** Managers can see variance and choose whether to update pricing defaults.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **SO-26 — Add production bottleneck analytics**
  - **Source classification:** Reserved implementation gap
  - **Priority basis:** Improves efficiency, automation, integration, or analysis after core workflows are dependable.
  - **Baseline gap:** The production board exists, but bottleneck and throughput analytics remain unfinished.
  - **Required outcome:** Calculate queue time, active time, blocked time, cycle time, repeated delays, and stage capacity from authoritative events.
  - **Done when:** Analytics identifies the source and period of bottlenecks without exposing restricted financial data to production employees.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

## Recommended Shop Operations-only implementation batches

Do not combine all Shop Operations gaps into one implementation PR. Use these dependency-based batches and keep each branch focused.

1. **Navigation, ownership, and scheduling foundation**
   - **Included SO IDs:** `SO-01`, `SO-28`
   - **Why they belong together:** Schedule placement, route ownership, and Wrap Lab contextual access control later appointments, production scheduling, and source-record links.
   - **Required predecessor batches:** None.
   - **Suggested branch name:** `codex/shop-operations-schedule-foundation`
   - **Closure tests and evidence required:** AppShell route ownership tests for the final tab order; `/shop-operations/schedule` refresh tests; `/shop-schedule` redirect/deep-link tests; calendar feed CRUD/conflict backend tests; screenshots at 1440x900 and 1280x800.

2. **Approval Center and canonical approval authority**
   - **Included SO IDs:** `SO-19`, `SO-20`, `SO-21`, prerequisite slices of `SO-03`, `SO-04`, and `SO-10`
   - **Why they belong together:** Approval queues, Decision Room launch/share, selectors, and staff apply actions need one canonical authority before Quote and Order pages claim approval state.
   - **Required predecessor batches:** Batch 1 only for approval due dates or schedule-linked actions.
   - **Suggested branch name:** `codex/shop-operations-approval-authority`
   - **Closure tests and evidence required:** Backend aggregation tests covering proofs, signatures, Approval records, Decision Room decisions/questions/overlays; permission tests; source-record action tests; Approval Center screenshots.

3. **Customer record foundation**
   - **Included SO IDs:** `SO-15`, `SO-16`, `SO-17`, `SO-18`
   - **Why they belong together:** Multi-contact/address structure, related-record coverage, duplicate merge, and archive/restore all mutate or depend on the same customer authority.
   - **Required predecessor batches:** None; coordinate linked schedule records from Batch 1 if implemented first.
   - **Suggested branch name:** `codex/shop-operations-customer-foundation`
   - **Closure tests and evidence required:** Model/endpoint tests for contacts, addresses, archive/restore, duplicate candidates, merge relationship preservation, audit events, and Customer detail screenshots.

4. **Quote completion**
   - **Included SO IDs:** `SO-03`, `SO-04`, `SO-05`, `SO-06`, `SO-07`, `SO-08`
   - **Why they belong together:** Quote approval authority, Decision Rooms, files/proofs, preview/share, printable output, and lifecycle history all depend on versioned quote state.
   - **Required predecessor batches:** Batch 2 for approval authority; Batch 3 if customer contact/address selection is required.
   - **Suggested branch name:** `codex/shop-operations-quote-completion`
   - **Closure tests and evidence required:** Quote approval-record enforcement tests, document/proof link tests, preview/share/delivery history tests, print/download artifact tests, Quote detail screenshots.

5. **Order operational readiness**
   - **Included SO IDs:** `SO-09`, `SO-10`, `SO-11`, `SO-13`
   - **Why they belong together:** Billing status, approvals/proofs, documents/artwork, and readiness blockers determine whether an Order can safely move into production.
   - **Required predecessor batches:** Batches 2 and 4; Batch 1 for schedule blockers.
   - **Suggested branch name:** `codex/shop-operations-order-readiness`
   - **Closure tests and evidence required:** Order financial summary tests, approval/proof aggregation tests, document/artwork permissions tests, computed readiness blocker tests, Order detail screenshots.

6. **Production timing and attribution**
   - **Included SO IDs:** `SO-23`, `SO-24`, `SO-25`
   - **Why they belong together:** Detailed timers, multi-employee contributions, and labor/pricing variance rely on the same stage-time data model.
   - **Required predecessor batches:** Batch 5 for readiness signals.
   - **Suggested branch name:** `codex/shop-operations-production-timing`
   - **Closure tests and evidence required:** Timer lifecycle tests, overlap/correction tests, multi-contributor tests, pricing feedback tests, kiosk and Production Board screenshots.

7. **Wrap Lab replacement workflows**
   - **Included SO IDs:** `SO-22`, plus contextual access dependencies from `SO-01` and schedule integration from `SO-28`
   - **Why they belong together:** Removing fixed example payloads requires editable staff workflows, permanent workspace access, and contextual launch points while preserving existing Wrap Lab records and deep links.
   - **Required predecessor batches:** Batch 1; Batch 5 for order/work-order context; Batch 6 if install labor is tied to wrap stages.
   - **Suggested branch name:** `codex/shop-operations-wrap-lab-workflows`
   - **Closure tests and evidence required:** Frontend form tests replacing fixed payload buttons, backend validation and permission tests, deep-link/redirect tests, Wrap Lab contextual screenshots.

8. **Completion documents, aftercare, communications, and analytics**
   - **Included SO IDs:** `SO-12`, `SO-14`, `SO-26`, `SO-27`
   - **Why they belong together:** Completion packets, customer communication history, signed artifacts, aftercare delivery, and analytics rely on stable records from the earlier batches.
   - **Required predecessor batches:** Batches 1, 2, 5, and 6.
   - **Suggested branch name:** `codex/shop-operations-completion-communications-analytics`
   - **Closure tests and evidence required:** Communication history tests, aftercare send/history tests, signed packet renderer tests, bottleneck analytics tests, Order closeout and analytics screenshots.

## Business & Finance

### P0 — Immediate release, integrity, or product-boundary gate

- [ ] **BF-15 — Decide the accounting boundary**
  - **Source classification:** Decision required
  - **Priority basis:** Product and reporting gate: operational metrics must not be represented as a full accounting system.
  - **Baseline gap:** Finance metrics are operational and unaudited. They mix issued-invoice revenue, cash-basis refunds, operational expenses, and incomplete Order cost snapshots. There is no general ledger, chart of accounts, accounts payable, bank reconciliation, or accounting periods.
  - **Required outcome:** Choose either a dependable operational-finance system with QuickBooks/Xero-style exports/integration or a full accounting scope. Do not let estimated dashboard values appear to be bookkeeping statements.
  - **Done when:** The chosen boundary is documented in product copy, reports, exports, and data contracts.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **BF-33 — Remove or restrict synthetic-data seeding in production UI**
  - **Source classification:** Release hardening gap
  - **Priority basis:** Release-hardening gate: normal production users must never be able to seed synthetic purchasing data.
  - **Baseline gap:** The Supply Center page exposes synthetic-data seeding alongside its limited catalog interface.
  - **Required outcome:** Restrict seeding to development/test environments or protected administrative tooling, and prevent it from appearing in normal tenant workflows.
  - **Done when:** Production users cannot create demo purchasing data accidentally.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **BF-01 — Support multiple invoices per Order**
  - **Source classification:** Previously identified P0; source priority: P0 from prior audit
  - **Priority basis:** Previously identified P0; the one-invoice limit blocks deposits, progress billing, changes, and final billing.
  - **Baseline gap:** The current API permits only one invoice per Order, preventing proper staged billing.
  - **Required outcome:** Allow multiple independently numbered invoices linked to the same Order with controlled status, totals, balance, and void/refund behavior.
  - **Done when:** An Order can have deposit, progress, change, and final invoices without overwriting prior billing.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **BF-03 — Populate authoritative Invoice Line Items**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Financial-integrity gate: authoritative stored line items are required to reproduce every invoice total.
  - **Baseline gap:** An InvoiceLineItem model exists, but invoice creation does not populate it from the selected commercial source.
  - **Required outcome:** Create immutable invoice line items from the approved Quote/Order/Order Item data, including descriptions, quantities, prices, discounts, and tax treatment.
  - **Done when:** Every invoice total can be reproduced from its stored line items.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **BF-04 — Derive invoice totals on the server**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Financial-integrity and security gate: client-supplied totals cannot remain authoritative.
  - **Baseline gap:** Invoice creation accepts a client-supplied total.
  - **Required outcome:** Calculate subtotal, discounts, taxable amount, tax, credits, fees, total, paid amount, and balance from server-authoritative records.
  - **Done when:** Changing a client request cannot alter the invoice total outside validated line-item and adjustment rules.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **BF-05 — Store immutable pricing and tax snapshots on finalized invoices**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Financial-integrity gate: finalized invoices must not change when pricing, tax, or source records change later.
  - **Baseline gap:** Invoices do not yet provide the required complete, immutable pricing/tax snapshot behavior.
  - **Required outcome:** Snapshot line-item pricing, discounts, tax jurisdiction/rate/exemption, terms, and source revision when the invoice is finalized.
  - **Done when:** Later changes to pricing defaults, customer exemptions, or Orders do not rewrite a finalized invoice.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

### P1 — Core workflow and dependency

- [ ] **BF-02 — Implement deposit, progress, and final invoicing**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Required for a safe end-to-end core workflow or to preserve canonical ownership and permissions.
  - **Baseline gap:** The billing workflow does not provide a complete deposit/progress/final lifecycle.
  - **Required outcome:** Add invoice type or purpose, eligible amount selection, prior-billed tracking, remaining-to-bill controls, and conversion from Order when collecting a down payment.
  - **Done when:** The same Order amount cannot be billed twice unless an authorized adjustment explains it.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **BF-06 — Complete payment terms, credits, and controlled adjustments**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Required for a safe end-to-end core workflow or to preserve canonical ownership and permissions.
  - **Baseline gap:** Payment terms and credit-adjustment handling are incomplete.
  - **Required outcome:** Add due-date terms, approved credits, credit memos or equivalent controlled adjustments, reasons, authorization, and audit history.
  - **Done when:** Balance changes are explainable and traceable without directly editing a finalized total.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **BF-12 — Implement deposit allocation and unapplied credits**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Required for a safe end-to-end core workflow or to preserve canonical ownership and permissions.
  - **Baseline gap:** There is no complete workflow for customer money received before or outside a specific finalized invoice.
  - **Required outcome:** Track deposits and unapplied credits, apply them to eligible invoices, prevent over-allocation, support reversal, and preserve the original payment connection.
  - **Done when:** Customer balance, invoice balance, and unapplied credit totals reconcile after every allocation or reversal.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **BF-07 — Create a global payment and refund ledger**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Required for a safe end-to-end core workflow or to preserve canonical ownership and permissions.
  - **Baseline gap:** Payments are visible primarily inside individual invoices even though manual and Stripe payments, refunds, voiding, and safeguards exist.
  - **Required outcome:** Create a cross-invoice ledger for payments, refunds, voids, methods, references, customer, invoice, Order, dates, and reconciliation state.
  - **Done when:** Finance staff can find any payment or refund without opening invoices one at a time.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **BF-10 — Expose reconciliation exceptions**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Required for a safe end-to-end core workflow or to preserve canonical ownership and permissions.
  - **Baseline gap:** Payment safeguards exist, but there is no complete staff workspace for unreconciled activity and discrepancies.
  - **Required outcome:** Show unmatched references, amount conflicts, duplicate attempts, failed/refunded/voided sequences, and required resolution actions.
  - **Done when:** Every exception has a status, owner, explanation, and audit trail.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **BF-09 — Implement detailed accounts-receivable aging and customer balances**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Required for a safe end-to-end core workflow or to preserve canonical ownership and permissions.
  - **Baseline gap:** Dashboard totals do not replace a complete aging and customer-balance workspace.
  - **Required outcome:** Add all outstanding, current/not due, 1-30, 31-60, 61-90, 90+ days, partially paid, and customer-balance views with invoice drill-through.
  - **Done when:** Aging buckets reconcile to open invoice balances for the same as-of date.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **BF-22 — Build Tax Exemption management UI**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Required for a safe end-to-end core workflow or to preserve canonical ownership and permissions.
  - **Baseline gap:** Tax exemption APIs can create/archive records, but the Taxes page is read-only.
  - **Required outcome:** Add customer search, exemption status/reason, jurisdiction, certificate/reference details, effective/expiration dates, create, edit where allowed, archive, and restore.
  - **Done when:** Authorized staff can manage exemptions without direct API calls, and invoices use the correct active record.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **BF-23 — Complete exemption documents and audit history**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Required for a safe end-to-end core workflow or to preserve canonical ownership and permissions.
  - **Baseline gap:** The agreed Taxes structure expects certificates, supporting documents, validity status, and history that are not fully exposed.
  - **Required outcome:** Attach certificate files, show missing/active/expired state, preserve prior versions, and record who changed or applied the exemption.
  - **Done when:** Every exempt invoice can be traced to the exemption record and evidence used at finalization.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **BF-27 — Build Supplier and Vendor configuration**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Required for a safe end-to-end core workflow or to preserve canonical ownership and permissions.
  - **Baseline gap:** There is no complete vendor creation/configuration workflow for the Supply Center.
  - **Required outcome:** Manage company and representative information, account number, ordering instructions, materials/SKUs, preferred status, catalog/API connection, notes, and history.
  - **Done when:** Materials and Purchase Orders can select maintained suppliers without manual IDs.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **BF-24 — Expose Supply Center shortage and reorder workflows**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Required for a safe end-to-end core workflow or to preserve canonical ownership and permissions.
  - **Baseline gap:** Backend endpoints support shortages and recommendations, but the page mainly renders catalog search.
  - **Required outcome:** Build Reorder Needs, Out of Stock, Production Shortages, upcoming Order Item requirements, urgency, required-by date, already-on-order quantities, and multi-select actions.
  - **Done when:** Production shortages can be converted into a reviewed purchasing action without re-entering material needs.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **BF-32 — Replace raw material IDs with searchable selectors**
  - **Source classification:** Open usability gap
  - **Priority basis:** Required for a safe end-to-end core workflow or to preserve canonical ownership and permissions.
  - **Baseline gap:** Current inventory actions can require pasted identifiers.
  - **Required outcome:** Use searchable material/SKU/location selectors with stock context, validation, recent choices, and permission-aware actions.
  - **Done when:** Routine inventory and purchasing work can be completed without copying internal IDs.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **BF-26 — Build Supply Center cart and draft-PO checkout UI**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Required for a safe end-to-end core workflow or to preserve canonical ownership and permissions.
  - **Baseline gap:** Cart-to-draft-Purchase-Order checkout endpoints exist, but no complete staff interface exposes them.
  - **Required outcome:** Add cart review, supplier grouping, quantities, substitutions, shipping/tax estimates, validation, and draft-PO creation.
  - **Done when:** Selected needs produce editable draft Purchase Orders with source shortages retained.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **BF-31 — Build draft Purchase Order creation and editing UI**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Required for a safe end-to-end core workflow or to preserve canonical ownership and permissions.
  - **Baseline gap:** Purchase Order submission, receiving, and cost history are materially implemented, but draft creation/editing is not complete from the staff interface.
  - **Required outcome:** Add supplier selection, line editing, prices, freight, taxes, expected delivery, related shortages/Orders, approval state, PDF/email/API submission, and audit history.
  - **Done when:** A buyer can create, revise, approve, and submit a PO without direct API use.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **BF-18 — Add Vendor, Order, and Purchase Order selectors to Expenses**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Required for a safe end-to-end core workflow or to preserve canonical ownership and permissions.
  - **Baseline gap:** Expense linkage exists but the page lacks complete user-friendly selectors.
  - **Required outcome:** Provide searchable selectors, context summaries, validation, and clear unlink/relink rules.
  - **Done when:** An expense can be linked without pasting raw IDs and cannot silently duplicate a received Purchase Order cost.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

### P2 — High-value operational completeness

- [ ] **BF-08 — Add payment-ledger search and filters**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Closes a common operational gap after the underlying records and authorities are stable.
  - **Baseline gap:** There is no complete global search/filter experience by customer, method, date, status, reference, or reconciliation state.
  - **Required outcome:** Provide fast filters, saved criteria where appropriate, totals for the filtered set, and drill-through to source records.
  - **Done when:** Ledger results are reproducible and exportable for a selected period.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **BF-11 — Generate receipts and payment confirmations**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Closes a common operational gap after the underlying records and authorities are stable.
  - **Baseline gap:** The global finance experience lacks complete receipt and payment-confirmation output.
  - **Required outcome:** Generate authoritative receipts for manual and processor payments, including allocation, method/reference, refund history, customer, invoice, and remaining balance.
  - **Done when:** Staff can print, download, or send the correct receipt and see its delivery history.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **BF-14 — Build the Other Income Ledger**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Closes a common operational gap after the underlying records and authorities are stable.
  - **Baseline gap:** The agreed Other Income Ledger inside Overview does not exist in application code.
  - **Required outcome:** Implement date, source/payer, amount, category, payment method, description, related Customer/Order, attachment, notes, edit, controlled void, and activity history.
  - **Done when:** Other income appears in reports exactly once and remains separate from invoice payments.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **BF-16 — Complete Expense detail and editing**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Closes a common operational gap after the underlying records and authorities are stable.
  - **Baseline gap:** The backend supports richer expense behavior, while the page focuses on creation, listing, archive/restore, and void.
  - **Required outcome:** Add expense detail, controlled edits, history, recurring state, linked records, and clear restrictions after financial use.
  - **Done when:** Staff can review and correct an expense without bypassing audit controls.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **BF-17 — Complete receipt attachment management**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Closes a common operational gap after the underlying records and authorities are stable.
  - **Baseline gap:** Receipt attachment support exists in the model/API but is not fully operable from the page.
  - **Required outcome:** Add upload, preview/download, replace/remove rules, attachment metadata, and preservation of the original receipt.
  - **Done when:** Each expense can retain its supporting receipt with an auditable attachment history.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **BF-19 — Build Expense Category management UI**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Closes a common operational gap after the underlying records and authorities are stable.
  - **Baseline gap:** Category management capabilities are not exposed as a complete staff workflow.
  - **Required outcome:** Add create, rename, merge, archive, restore, deductible classification, usage visibility, and reporting connection.
  - **Done when:** Category changes preserve historical reporting and prevent orphaned expenses.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **BF-25 — Build purchasing-recommendation comparison**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Closes a common operational gap after the underlying records and authorities are stable.
  - **Baseline gap:** Recommendations exist in the backend but lack a complete comparison interface.
  - **Required outcome:** Compare quantity, supplier, pack size, live/imported/manual price, availability, freight, last price, urgency, and estimated landed cost.
  - **Done when:** A buyer can choose a recommendation with its source and assumptions visible.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **BF-28 — Add CSV and manual supplier-catalog imports**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Closes a common operational gap after the underlying records and authorities are stable.
  - **Baseline gap:** Non-API alternatives are required, but the interface does not provide complete imported-price-list or CSV update workflows.
  - **Required outcome:** Add mapping, validation, preview, error reporting, version/date/source, update rules, and rollback or supersession behavior.
  - **Done when:** Imported catalogs update supplier offers without corrupting canonical material records.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **BF-30 — Complete warehouse/location-level availability UI**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Closes a common operational gap after the underlying records and authorities are stable.
  - **Baseline gap:** Inventory services are broader than the Supply Center page and warehouse-level availability is not fully presented.
  - **Required outcome:** Show on-hand, reserved, available, on-order, location, transfers, counts, damaged/waste, and receiving effects by location.
  - **Done when:** Buyers and production staff see accurate availability at permitted detail levels.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **BF-39 — Complete specialized accounting, payroll, and tax exports**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Closes a common operational gap after the underlying records and authorities are stable.
  - **Baseline gap:** Specialized exports remain incomplete even though general CSV/XLSX/PDF/print output exists.
  - **Required outcome:** Define export schemas, periods, mapping, validation, version, and reconciliation totals for the selected external workflows.
  - **Done when:** Each export can be reconciled to an in-app report and identifies its accounting basis.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **BF-40 — Add report-definition versioning, audit history, and delivery retries**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Closes a common operational gap after the underlying records and authorities are stable.
  - **Baseline gap:** Definition versioning, full audit history, and robust delivery retries are incomplete.
  - **Required outcome:** Version report definitions and schedules, record material edits/runs/deliveries, and expose retry state without duplicating successful deliveries.
  - **Done when:** Historical outputs can be tied to the exact report definition and parameters used.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

### P3 — Efficiency, automation, integration, or analytics

- [ ] **BF-13 — Add Finance Overview quick-entry actions**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Improves efficiency, automation, integration, or analysis after core workflows are dependable.
  - **Baseline gap:** The dashboard is informative but lacks complete quick-entry flows for Add Expense, Record Customer Payment, Add Other Income, and Create Invoice.
  - **Required outcome:** Add permission-aware entry actions with validation and links to the resulting records.
  - **Done when:** Each quick action completes a real backend workflow rather than opening a placeholder.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **BF-20 — Implement recurring-expense generation**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Improves efficiency, automation, integration, or analysis after core workflows are dependable.
  - **Baseline gap:** Recurrence flags are modeled as foundation, but no recurring generator completes the workflow.
  - **Required outcome:** Add frequency, next date, end/pause rules, background generation, duplicate protection, review state, and history.
  - **Done when:** Recurring expenses are generated once per period and remain distinguishable from the template rule.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **BF-29 — Implement real supplier connectors and credential management**
  - **Source classification:** Open integration gap
  - **Priority basis:** Improves efficiency, automation, integration, or analysis after core workflows are dependable.
  - **Baseline gap:** Supplier catalog search exists, but complete production supplier connectors and credential management are absent.
  - **Required outcome:** Add supported connector contracts, secure tenant credentials, refresh/error states, rate-limit handling, price/availability timestamps, and non-API fallback.
  - **Done when:** Live supplier results clearly identify source and freshness and never expose credentials.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **BF-34 — Implement scheduled report execution and delivery**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Improves efficiency, automation, integration, or analysis after core workflows are dependable.
  - **Baseline gap:** Reporting evidence identifies scheduled background execution and email delivery as incomplete.
  - **Required outcome:** Add a scheduler/worker, output generation, recipients, permissions, retry handling, delivery history, and failure alerts.
  - **Done when:** Reports run at the configured time and every attempt has a visible result.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **BF-35 — Complete report schedule controls**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Improves efficiency, automation, integration, or analysis after core workflows are dependable.
  - **Baseline gap:** Schedule editing, pausing, delivery configuration, and related lifecycle controls are incomplete.
  - **Required outcome:** Provide frequency, next run, timezone, format, recipients, active/paused state, edit, cancel, and schedule history.
  - **Done when:** Users can manage a schedule without recreating it and can see the next effective run.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **BF-42 — Make report scheduling timezone-aware**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Improves efficiency, automation, integration, or analysis after core workflows are dependable.
  - **Baseline gap:** Timezone-aware schedule execution remains incomplete.
  - **Required outcome:** Store the intended timezone, handle daylight-saving transitions, display next run in the user’s context, and record the actual execution time.
  - **Done when:** Scheduled reports run at the expected local time across timezone and daylight-saving changes.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **BF-36 — Complete Saved Report management**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Improves efficiency, automation, integration, or analysis after core workflows are dependable.
  - **Baseline gap:** Saved-report editing, sharing, and restoration are incomplete in the UI.
  - **Required outcome:** Add edit, duplicate, share/permission, archive/delete where allowed, restore, creator, last run, and saved definition details.
  - **Done when:** A saved report is reusable and recoverable without losing its filters, columns, sorting, or grouping.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **BF-43 — Make the visible report search functional**
  - **Source classification:** Open usability gap
  - **Priority basis:** Improves efficiency, automation, integration, or analysis after core workflows are dependable.
  - **Baseline gap:** The Reports page displays a ‘Search reports’ input without filtering state.
  - **Required outcome:** Connect the input to report catalog filtering with clear no-results and reset behavior.
  - **Done when:** Typing a query immediately narrows the visible report catalog predictably.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **BF-41 — Complete Wrap Lab reporting**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Improves efficiency, automation, integration, or analysis after core workflows are dependable.
  - **Baseline gap:** Deep Wrap Lab reporting is not covered by the current reporting implementation.
  - **Required outcome:** Add approved datasets and reports for project status, measurements/coverage, damage documentation, design/proof cycle, production, installation, labor, materials, and profitability where financial permissions allow.
  - **Done when:** Wrap reports reconcile to canonical Wrap Projects, Orders, production records, and invoices.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

### P4 — Optional or intentionally deferred

- [ ] **BF-21 — Implement user-triggered receipt scanning if retained**
  - **Source classification:** Planned enhancement
  - **Priority basis:** Optional or deferred capability; confirm scope and stable foundations before implementation.
  - **Baseline gap:** Receipt scanning is planned but not implemented as a complete reviewed workflow.
  - **Required outcome:** Support image upload/capture, extraction suggestions, duplicate checks, Order/PO matching, permanent-category selection, and mandatory human review before save.
  - **Done when:** No extracted receipt becomes an expense automatically; the original image stays attached.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **BF-37 — Add comparison periods and calculated fields**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Optional or deferred capability; confirm scope and stable foundations before implementation.
  - **Baseline gap:** Advanced period comparisons and calculated fields are not complete.
  - **Required outcome:** Support validated comparison periods and allowlisted calculated fields with clear formulas and consistent export behavior.
  - **Done when:** Displayed and exported results use the same definitions and explain their calculations.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **BF-38 — Implement dashboard-widget publishing only after report definitions are stable**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Optional or deferred capability; confirm scope and stable foundations before implementation.
  - **Baseline gap:** Publishing report results as dashboard widgets remains incomplete.
  - **Required outcome:** Define eligible reports, refresh rules, permissions, date context, empty/error states, and removal behavior.
  - **Done when:** A published widget matches its source report and does not display stale or unauthorized data.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

## Team & Productivity

### P0 — Immediate release, integrity, or product-boundary gate

- [ ] **TP-14 — Define the payroll-processing boundary**
  - **Source classification:** Decision required
  - **Priority basis:** Regulatory and product-claims gate: gross-pay tracking must be clearly separated from regulated payroll processing.
  - **Baseline gap:** Current Payroll is an employee gross-pay ledger using approved time, rates, overtime settings, advances, payments, adjustments, repayments, and carryover. It does not provide ACH, direct deposit, withholding, tax filing, W-2s, or 1099s.
  - **Required outcome:** Choose whether SignGuy AI remains an operational payroll ledger with exports/integrations or becomes a regulated payroll-processing system. Keep Payroll operationally under Team & Productivity; expose payroll costs in Business & Finance reporting.
  - **Done when:** The UI, onboarding, and marketing distinguish gross-pay tracking from full payroll processing.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

### P1 — Core workflow and dependency

- [ ] **TP-01 — Implement the final Team & Productivity internal-tab structure**
  - **Source classification:** Placement correction
  - **Priority basis:** Required for a safe end-to-end core workflow or to preserve canonical ownership and permissions.
  - **Baseline gap:** The repository contains Employees, schedules, time tracking, payroll, tasks, communications, and a substantial Equipment/Training/Certification subsystem, but the previously proposed seven-tab structure did not account for all of it.
  - **Required outcome:** Use these internal top tabs: Overview; Team; Schedule; Time & Attendance; Payroll; Tasks; Communications; Training & Equipment. Keep the sidebar one level only. Do not name the Tasks tab ‘Tasks & Projects.’
  - **Done when:** Every existing Team capability has one primary internal-tab owner; Training & Equipment is visible; no sidebar flyouts or nested sidebar groups are introduced.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **TP-02 — Keep employee scheduling in Team Schedule and link operational Shop Schedule overlays**
  - **Source classification:** Placement correction
  - **Priority basis:** Required for a safe end-to-end core workflow or to preserve canonical ownership and permissions.
  - **Baseline gap:** Team Schedule and Shop Schedule are related views over shared scheduling foundations, but they have different product ownership. Employee shifts, availability, time-off requests, training schedules, and internal meetings belong in Team & Productivity > Schedule. Operational appointments, site surveys, installs, deliveries, pickups, production milestones, resource reservations, and customer-facing shop events belong in Shop Operations > Schedule.
  - **Required outcome:** Make Team & Productivity > Schedule the primary home for employee scheduling and time-off administration. Shop Operations > Schedule remains the primary home for Shop Calendar operational records while using the same canonical scheduling foundation instead of a second database.
  - **Done when:** There is one canonical calendar foundation; employee schedule administration and operational Shop Schedule records are presented in their correct workspaces without duplicate event records.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **TP-18 — Keep Production owned by Shop Operations**
  - **Source classification:** Safeguard
  - **Priority basis:** Required for a safe end-to-end core workflow or to preserve canonical ownership and permissions.
  - **Baseline gap:** The Employee Portal has a Production view so employees can work assigned stages, but the production board, Work Orders, stages, kiosk, and workflow management are operational systems.
  - **Required outcome:** Keep Production in Shop Operations. Team & Productivity supplies employees, qualifications, schedules, and time connections only.
  - **Done when:** Employee production access works without relocating or duplicating the Production module.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **TP-16 — Preserve the shared linked-notes architecture**
  - **Source classification:** Safeguard
  - **Priority basis:** Required for a safe end-to-end core workflow or to preserve canonical ownership and permissions.
  - **Baseline gap:** Communication notes are shared linked notes. Creating separate databases for task notes, order notes, employee notes, and work-order notes would duplicate the same concept and fragment history.
  - **Required outcome:** Continue using the canonical notes collection with record links, permissions, and context-specific presentation.
  - **Done when:** Every supported record can show its notes without duplicating note records or losing cross-record history.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **TP-09 — Resolve the customer-participation boundary for messaging**
  - **Source classification:** Decision required
  - **Priority basis:** Required for a safe end-to-end core workflow or to preserve canonical ownership and permissions.
  - **Baseline gap:** The shared messaging service supports staff and employee participants; customer participation was explicitly excluded.
  - **Required outcome:** Decide whether customer messages remain owned by customer/order communication features or whether a secure customer conversation type will be added. Do not silently add customers to internal threads.
  - **Done when:** The selected boundary is documented, permission-tested, and reflected consistently in Communications and Shop Operations.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **TP-03 — Build the manager-facing Time-Off workspace**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Required for a safe end-to-end core workflow or to preserve canonical ownership and permissions.
  - **Baseline gap:** Employees can request time off and backend services support list, review, approve, deny, request clarification, and conflict checking. There is no complete staff-facing Time-Off page or route.
  - **Required outcome:** Create the manager queue and request-detail workflow with status filters, conflicts, review actions, reasons, history, and schedule overlays.
  - **Done when:** A manager can complete the full request lifecycle without calling the API directly.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **TP-04 — Complete staff availability management**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Required for a safe end-to-end core workflow or to preserve canonical ownership and permissions.
  - **Baseline gap:** Manager availability endpoints exist and availability affects shift conflict warnings, but there is no complete dedicated staff availability workspace.
  - **Required outcome:** Provide employee selection, recurring availability blocks, exceptions, edit/archive behavior, conflict visibility, and activity history.
  - **Done when:** Managers can maintain availability and see its effect before publishing shifts.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

### P2 — High-value operational completeness

- [ ] **TP-05 — Correct Employee Portal access messaging**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Closes a common operational gap after the underlying records and authorities are stable.
  - **Baseline gap:** The admin Portal Access page describes only schedule, time clock, and timesheets even though the portal also includes Production, Time Off, My Pay, Training, Certifications, Tasks, Messages, Announcements, and Profile.
  - **Required outcome:** Update page copy and invitation/access descriptions to match the portal’s actual capabilities and permission boundaries.
  - **Done when:** Portal access messaging accurately lists the available employee experiences and does not overpromise restricted features.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **TP-06 — Keep Projects out of current navigation unless a real Projects system is built**
  - **Source classification:** Intentional boundary
  - **Priority basis:** Closes a common operational gap after the underlying records and authorities are stable.
  - **Baseline gap:** There is no Project model, router, page, workspace, or task-to-project structure in the repository.
  - **Required outcome:** Use the tab name ‘Tasks.’ If Projects becomes a future requirement, treat it as a separately planned subsystem rather than a label change.
  - **Done when:** No screen or marketing copy implies Project management exists today.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **TP-07 — Do not claim a generic workflow builder**
  - **Source classification:** Intentional boundary
  - **Priority basis:** Closes a common operational gap after the underlying records and authorities are stable.
  - **Baseline gap:** Production workflows exist and Tasks have lifecycle rules, but there is no general Team workflow-automation builder.
  - **Required outcome:** Keep production workflow configuration with Production. Only add a generic workflow builder after its triggers, actions, permissions, audit history, and ownership are specified.
  - **Done when:** Current UI does not present production workflow rules as a general automation product.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **TP-15 — Consolidate announcement access without creating a second announcement system**
  - **Source classification:** Model and navigation cleanup
  - **Priority basis:** Closes a common operational gap after the underlying records and authorities are stable.
  - **Baseline gap:** Announcements use an older separate model, while Communications already exposes an Announcements view and includes announcements in digest and preference behavior.
  - **Required outcome:** Keep Announcements inside Communications and route existing announcement data through the shared experience. Avoid a separate top tab or replacement model unless migration is planned.
  - **Done when:** Users have one announcement entry point, and existing announcements remain accessible.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **TP-17 — Keep templates centralized while adding contextual use actions**
  - **Source classification:** Placement correction
  - **Priority basis:** Closes a common operational gap after the underlying records and authorities are stable.
  - **Baseline gap:** Task, appointment, announcement, message, digest, support, and time-off response templates use a shared template engine. The template library belongs under Tools & Resources.
  - **Required outcome:** Add contextual ‘Use Template’ actions in Team pages that open or apply the shared template source; do not duplicate template management inside Team & Productivity.
  - **Done when:** Team workflows can use templates while one centralized template library remains authoritative.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **TP-10 — Implement recurring-task generation**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Closes a common operational gap after the underlying records and authorities are stable.
  - **Baseline gap:** Recurrence-related fields are reserved, but no scheduler creates future task instances.
  - **Required outcome:** Add recurrence rules, next-run calculation, background generation, duplicate protection, pause/end controls, and activity history.
  - **Done when:** Recurring tasks are generated exactly once at the expected times and can be paused, edited, and ended.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

### P3 — Efficiency, automation, integration, or analytics

- [ ] **TP-08 — Add unified communications oversight if it remains in scope**
  - **Source classification:** Open product and implementation gap
  - **Priority basis:** Improves efficiency, automation, integration, or analysis after core workflows are dependable.
  - **Baseline gap:** Current internal message threads, linked notes, announcements, digests, and preferences do not provide the requested management view across internal and customer communications.
  - **Required outcome:** Define and implement a management workspace that can show internal communications and linked customer-facing activity without merging incompatible permission models.
  - **Done when:** Managers can review communication activity across supported channels with clear source, participant, privacy, and record links.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **TP-11 — Implement saved task views and configurable Kanban boards**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Improves efficiency, automation, integration, or analysis after core workflows are dependable.
  - **Baseline gap:** Task List, Kanban, My Tasks, and system views share the canonical Task model, but user-created saved views and customizable boards are not implemented.
  - **Required outcome:** Add saved filters, column/group settings, ownership/sharing rules, ordering, default views, and restore behavior without creating another task engine.
  - **Done when:** Users can create, reuse, edit, and remove saved views; Kanban configuration remains a view over canonical Tasks.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

- [ ] **TP-12 — Finish Daily Digest delivery**
  - **Source classification:** Open implementation gap
  - **Priority basis:** Improves efficiency, automation, integration, or analysis after core workflows are dependable.
  - **Baseline gap:** Daily Digest currently previews or generates data. There is no completed email delivery worker, automatic AI digest, or SMS delivery.
  - **Required outcome:** Implement only the approved delivery channels, scheduling, quiet-hours behavior, retry/failure history, and user-triggered AI rules. Keep SMS and automatic AI out unless explicitly added to scope.
  - **Done when:** A configured digest is delivered reliably, failures are visible, and AI never runs automatically unless the product decision changes.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

### P4 — Optional or intentionally deferred

- [ ] **TP-13 — Implement external calendar synchronization only if approved**
  - **Source classification:** Open optional integration gap
  - **Priority basis:** Optional or deferred capability; confirm scope and stable foundations before implementation.
  - **Baseline gap:** There is no Google Calendar or Outlook calendar synchronization.
  - **Required outcome:** If retained, specify directionality, conflict rules, ownership, deleted-event behavior, authentication, and sync history before implementation.
  - **Done when:** Calendar sync is not advertised until a tested end-to-end integration exists.
  - **Tracking:** Status: `Open — re-verify` | Owner: `—` | PR/Commit: `—` | Tests/Evidence: `—` | Residual limitations: `—`

## Current-context note

The source register was audited against an older `main` baseline. This repository copy establishes the canonical committed register at `memory/SIGNGUY_AI_Prioritized_Implementation_Register.md` because no prior prioritized implementation register existed in the repository and the established planning/tracking registers live under `memory/`.

Shop Operations items `SO-01` through `SO-28` were re-audited on August 16, 2026 against `main` at `1092e268cd9139240ec5eedce46a2a9f158e401f` after the merged navigation shell, Home/sidebar correction, Quick Access, Shop Schedule, Wrap Lab navigation restoration, and Schedule resource-reservation work. Business & Finance content remains source-copy content and was not re-audited or edited in this task. Team & Productivity content remains source-copy content except the minimum `TP-02` wording correction needed to remove contradictory Shop Schedule ownership.

## Per-item closure record template

Copy this under an item when work begins:

```text
Status: In Progress | Blocked | Deferred | Closed
Owner:
Branch / PR:
Fixing commit:
Tests run:
Evidence path or link:
Residual limitations:
Verified against default-branch commit:
```

---

This tracker preserves every item from `SIGNGUY_AI_Master_Implementation_Gap_Register(1).docx` in the three requested areas. The priority assignment is new; the baseline gap, required outcome, and closure language are retained from the source register.
