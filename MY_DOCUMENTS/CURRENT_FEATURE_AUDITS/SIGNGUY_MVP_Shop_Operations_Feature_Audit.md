# SIGNGUY MVP — Shop Operations Feature Audit

**Repository:** `dnblack323/SIGNGUY-MVP`  
**Audited branch/commit:** `main` at `82361811b80000392fa318e771bb9ff443ab62c4`  
**Audit focus:** the current Shop Operations product surface, including supporting approvals, signatures, customer portal behavior, invoices/payments, and the separate voice assistant boundary.

This is a code-based implementation audit, not a summary of plans or specification files. A feature is rated from the combination of its current frontend, backend model/service/router, permission and tenant rules, and focused tests. Where the model or API exists but the user-facing workflow is incomplete, the lower rating wins.

## Rating and AI legend

| Score | Label | Meaning |
|---|---|---|
| 5 | Standout / advanced | Deep, integrated, guarded, and meaningfully end-to-end. One of the app's strongest differentiators. |
| 4 | Advanced | Substantial end-to-end workflow with good controls; a few polish or coverage gaps remain. |
| 3 | Solid | Useful operational feature that works, but is narrower, rougher, or has a material missing handoff. |
| 2 | Basic | A usable slice exists, but the workflow is manual, thin, or clearly unfinished. |
| 1 | Foundation only | Models/APIs or fragments exist, but this should not be sold as a complete user feature. |
| 0 | Placeholder | Visible copy or disabled controls only. |

AI labels used below:

- **No** — works without AI and does not call an AI feature.
- **Optional** — core workflow works without AI; a user can deliberately launch an AI helper.
- **Required for this feature** — the named feature is itself an AI capability and requires configured provider access/entitlement/credits.
- **Planned/inactive** — the UI advertises an AI idea but its controls are disabled or explicitly deferred.

## Current Shop Operations structure in the repo

The current navigation code exposes:

1. Overview
2. Customers
3. Sales
   - Intake Requests
   - Quotes
   - Orders
4. Approval Center
5. Production
6. Schedule
7. Webstores
8. Wrap Lab

Production Kiosk is a separate kiosk route. Invoices and Payments live canonically in Business & Finance even though Orders can create and link to them. The Business Assistant and voice experience live under Studio/Tools, not inside Shop Operations.

## Executive scorecard

| Area | Score | AI requirement | Bottom line |
|---|---:|---|---|
| Shop Operations Overview | 3 | No | Useful operational summary; some “approval” metrics are derived attention counts rather than a true Approval Center aggregate. |
| Customers | 4 | No | Strong customer master record, dedupe/merge, contacts, addresses, and related-record hub; some related-record links are not routed. |
| Intake Requests | 3 | No | Strong structured intake and state history; actual creation of a Quote or Order from the intake is incomplete. |
| Quotes | 5 | Optional | One of the strongest modules: pricing, revisions, approvals, Decision Rooms, email, scheduling, and idempotent conversion. |
| Orders | 5 | Optional | Strong commercial-to-production bridge with exact item snapshots, approvals, proofs, scheduling, invoicing, and work-order generation. |
| Approval Center | 5 | No | Unified authority queue with real actions across approvals, Decision Rooms, proofs, and signature requests. |
| Decision Rooms | 5 | No | The clearest standout feature: versioned customer decisions, comparison options, comments, overlays, secure links, and controlled commercial application. |
| Proofs | 3 | No | Real version/status/approval foundation and public action flow, but staff file selection and token delivery are rough. |
| Signature Requests | 1 | No | Backend foundation only. No staff request screen, no public signing screen, and signed-PDF regeneration is not implemented. |
| Production | 5 | No | Advanced work orders, stage workflows, board, timeline, gates, bulk actions, eligibility, and kiosk. |
| Shop Schedule | 4 | No | Strong operational calendar with resource conflicts, linked records, several views, and overrides. |
| Webstores | 4 | Optional | Very broad setup-to-commerce-to-production system; several stale/disabled UI elements and provider configuration still affect polish. |
| Wrap Lab | 2 | Optional | Rich backend data contract, but the current staff UI is mostly a hard-coded demonstration workflow rather than a production editor. |
| Customer Portal support | 3 | No | Decision Rooms and invoice payment have deeper pages; most other portal areas are list-first and thin. |
| Invoice/payment handoff | 3 | Optional | Strong reconciliation backend and staff controls; portal card entry is still a development simulation rather than mounted Stripe Elements. |
| Voice assistant (outside Shop Ops) | 3 | Required for this feature | Real OpenAI Realtime boundary and safety design, but it is separately entitled/configured and not a Shop Ops workflow requirement. |

## 1. Shop Operations Overview — 3/5 Solid

**AI:** No.

| Feature | Maturity | What exists now |
|---|---:|---|
| Operational KPI cards | 3 | Active Orders, Quotes needing follow-up, Production attention, and approval/readiness indicators. |
| Sales Follow-up Queue | 3 | Quote number, project, relative age, status, total, and click-through to the Quote. |
| Production Attention Queue | 3 | Work Order number/status and click-through for records needing attention. |
| Approval & Customer Signals | 3 | Combines quote follow-up and order-readiness signals. Useful, but not the same as querying every unresolved Approval Center authority item. |
| Recent operational activity | 3 | Displays recent operational events with record links. |
| Operational Snapshot | 2 | Compact counts and small visual bars; informative rather than interactive analytics. |

## 2. Customers — 4/5 Advanced

**AI:** No.

### Customer record and lifecycle

| Feature | Maturity | What exists now |
|---|---:|---|
| Create and edit customers | 4 | Name, company, customer type, lifecycle, email, phone, address, and notes. Types include business, individual, and organization. |
| Lifecycle controls | 4 | Active, lead, inactive, archive, restore, and merged-record preservation. |
| Search and filtering | 4 | Search plus status/lifecycle views for active, archived, and merged records. |
| Multiple contacts | 4 | Contact roles include primary, billing, production, approval, and other. One contact can be marked primary. |
| Multiple addresses | 4 | Purpose-aware addresses for billing, shipping, production, installation, mailing, and other; supports a default address. |
| Permission and tenant isolation | 4 | Reads, writes, archive/restore, and merge behavior are permission- and tenant-scoped. |

### Duplicate detection and merge

| Feature | Maturity | What exists now |
|---|---:|---|
| Duplicate-candidate detection | 4 | Compares normalized name, company, email, phone, and address and explains match reasons. |
| Merge into a survivor record | 4 | Source becomes a preserved merged/archived record; related records are relinked. |
| Merge safety | 4 | Cross-tenant merges are blocked and repeat merges are prevented. |

### Customer 360° related-record hub

| Area | Maturity | What is shown |
|---|---:|---|
| Overview | 4 | Core profile, lifecycle, contacts, addresses, and quick actions. |
| Communications | 3 | Email records associated with the customer. This is not yet a full omnichannel communication timeline. |
| Requests | 4 | Intake/quote requests, schedule events, Decision Rooms, and approvals. |
| Quotes and Orders | 4 | Related Quotes, Orders, Work Orders, Invoices, and Payments. |
| Files and forms | 3 | Documents, Proofs, Files, and related form artifacts. |
| Portal | 3 | Portal identities, Webstores, and portal-related tasks are visible. Direct invitation/identity management is not fully centered here. |
| Activity | 4 | Audit-oriented timeline of customer-related operations. |
| Schedule customer action | 4 | Opens Shop Schedule with customer context prefilled. |

### Known customer gaps

- Some customer-detail links point to individual document, proof, file, or portal-identity URLs that do not have matching frontend routes.
- The communication view is email-centric, not a complete unified inbox.
- Portal identity visibility is better than portal identity management from the Customer page.

## 3. Sales — Intake Requests — 3/5 Solid

**AI:** No.

### Intake capture

| Feature | Maturity | What exists now |
|---|---:|---|
| Intake list | 3 | Search and filters for status, priority, and operational review. |
| Quick and Detailed creation modes | 4 | A lightweight start plus a richer intake editor. |
| Linked or unlinked customer | 4 | Use an existing Customer or capture contact name, email, and phone before a customer record exists. |
| Source tracking | 4 | Internal user, customer portal, public link, questionnaire, email import, Quote, Order, template, API, and other. |
| Priority and ownership | 4 | Low, normal, high, urgent; assigned user and requested due date. |
| Customer-safe vs internal notes | 4 | Separate note fields prevent accidental disclosure. |
| Installation intake | 4 | Installation-required flag, location, and installation notes. |
| Intake-level files/forms | 3 | File references and questionnaire-submission references can be associated. |

### Intake items

| Feature | Maturity | What exists now |
|---|---:|---|
| Multiple items | 4 | Add, duplicate, remove, and reorder intake items. |
| Item details | 4 | Name, category, description, quantity, saved/common item, dimensions, material, requested completion, notes, and files. |
| Requirement flags | 4 | Proof required, Approval required, and Installation required at item level. |
| Missing-information validation | 4 | Banners and validation rules identify incomplete records, including missing installation detail. |
| Conversion preview | 4 | Read-only preview shows how an intake item maps to a Quote Line Item or Order Item without inventing a selling price. |
| Pricing-workflow metadata | 2 | Backend stores pricing readiness/state, manual-cent values, snapshots, and warnings; the intake UI is not a full pricing workbench. |

### Workflow and history

| Feature | Maturity | What exists now |
|---|---:|---|
| Status lifecycle | 4 | Draft, submitted, under review, needs information, accepted, converted to Quote, converted to Order, rejected, cancelled. |
| Guarded transitions | 4 | Editing is limited to appropriate states; rejection/cancellation reasons are required. |
| Status history | 4 | Actor, timestamp, previous/new status, and reason are preserved. |
| Idempotency and validation | 4 | Tenant, permission, related-record, and repeat-submission safeguards. |

### Critical intake gap

The backend can preview a conversion and mark an intake as converted when a `quote_id` or `order_id` is supplied, but the audited code does not contain an end-to-end command that creates the Quote or Order from the accepted Intake. Public quote requests also create a separate Quote Request record and are not automatically promoted into the canonical Intake Submission workflow.

## 4. Sales — Quotes — 5/5 Standout

**AI:** Optional. Every core Quote function works without AI.

### Quote management

| Feature | Maturity | What exists now |
|---|---:|---|
| Quote list and create | 4 | Create from customer/project context and filter by draft, sent, approved, declined, and converted views. |
| Rich status model | 5 | Draft, sent, viewed, approved, declined, expired, converted, and void on the backend. |
| Customer and internal notes | 4 | Separate disclosure boundaries. |
| Expiration | 4 | Expiry dates and expired-conversion override safeguards. |
| Email Quote | 4 | Staff compose an editable email using Quote context. |
| Schedule from Quote | 4 | Opens operational scheduling with commercial context. |

### Quote Line Items and pricing

| Feature | Maturity | What exists now |
|---|---:|---|
| Quote Line Item CRUD | 5 | Add, edit, and remove items using Quick or Detailed modes. |
| Product categories | 5 | Banners, rigid signs, cut vinyl, digital print, vehicle graphics, apparel, services, promotional, and custom. |
| Units and dimensions | 5 | Quantity, each/square-foot/linear-foot/hour units, width/height in inches or feet, and material profile. |
| Category-specific inputs | 5 | Design, installation, material, and production inputs vary by category. |
| Server pricing calculator | 5 | Debounced recalculation, method comparison, suggested vs manual price, cost breakdown, unavailable-method explanations, and saved-calculation reuse. |
| Manual overrides | 5 | Manual pricing is allowed with an override reason and preserved snapshot. |
| Discounts and tax | 5 | Line-level pricing plus backend-derived Quote totals. |
| Pricing integrity | 5 | Integer cents; backend ignores spoofed client totals and derives subtotal, discount, tax, digital-print minimum, and total. |
| Profitability | 5 | Estimated production cost, estimated profit, margin, and warnings. |
| Recalculation review | 5 | Preview changes, accept/reject, and preserve the previous snapshot. |
| Production requirement | 5 | Quote Line Items can carry a production requirement into later Order/Work Order flow. |

### Revisions, approval, and conversion

| Feature | Maturity | What exists now |
|---|---:|---|
| Immutable revisions | 5 | Editing a sent Quote snapshots the prior revision and increments the revision number. |
| Quote Approval | 5 | Approve, decline, or request a change with reason; writes canonical immutable Approval history. |
| Quote-to-Order conversion | 5 | Copies the exact current Quote revision and line-item pricing snapshots; repeat calls are idempotent. |
| Conversion safeguards | 5 | Declined Quotes are blocked; expired Quotes require an override reason and audit entry. |
| Decision Room | 5 | Create/open an approval workspace, inspect history, and create secure share links. |
| Audit trail | 5 | Commercial and approval actions are visible in the record timeline. |

### Optional Quote AI

| AI helper | Status | Behavior |
|---|---|---|
| AI Quote Email | Optional | Opens Studio with Quote context to draft copy; does not replace core email composition. |
| AI Proposal | Optional | Opens Studio with Quote context. |
| Pricing Advisor | Optional | Opens Studio with Quote/pricing context. |

These buttons are contextual navigation into Studio, not automatic inline mutations of the Quote.

## 5. Sales — Orders — 5/5 Standout

**AI:** Optional.

### Order creation and item management

| Feature | Maturity | What exists now |
|---|---:|---|
| Direct Order creation | 4 | Create an Order without a Quote. |
| Quote-converted Order | 5 | Preserves source Quote and exact source revision. |
| Status ribbon/views | 4 | All, Draft, Confirmed, Ready, In Production, Completed, and Cancelled. |
| Order Item Quick Add and Detailed editor | 5 | Reuses the rich line-item pricing engine. |
| Production-required defaults | 5 | Physical categories default to production; services/promotional default to no production; unknown categories default safely to production. |
| Production override reason | 5 | Staff can override production requirement only with a reason. |
| Backend totals and profitability | 5 | Integer-cent totals, digital-print minimum, estimated cost/profit/margin, suggested/manual totals, and warnings. |
| Mutation guards | 5 | Completed, cancelled, and archived Orders cannot have their items changed. |
| Due date and note boundaries | 4 | Customer-facing and internal notes remain separate. |

### Production and fulfillment handoff

| Feature | Maturity | What exists now |
|---|---:|---|
| Generate Work Order | 5 | Uses only production-required Order Items. |
| Current Work Order detection | 5 | Avoids accidental duplicate current Work Orders. |
| Regenerate/supersede Work Order | 5 | Creates a new immutable version and supersedes the old one. |
| Production timeline | 5 | Order-level history spanning production events. |
| Schedule appointment/installation | 4 | Carries Customer, Order, and Work Order context into Shop Schedule. |
| Task handoff | 4 | Creates/open a staff task handoff from the Order. |

### Approval, proof, finance, and files

| Feature | Maturity | What exists now |
|---|---:|---|
| Proofs panel | 3 | Create Proofs, add versions, and transition approval states. The file picker/token-delivery experience is rough. |
| Decision Room | 5 | Create/open the customer decision workspace and inspect approval history. |
| Secure share | 5 | Mint/revoke Decision Room links and keep immutable published versions. |
| Create Invoice | 4 | Idempotently creates or opens the Order's Invoice and hands off to Business & Finance. |
| Source Quote link | 5 | Shows Quote and exact revision used. |
| Files & Artwork tab | 0 | Explanatory placeholder only; there is no real attached-file manager in this Order tab. |
| Financial tab | 4 | Surfaces Invoice/financial handoff rather than duplicating finance authority inside Shop Ops. |
| Activity tab | 3 | Reuses the Production Timeline instead of a distinct, fully generalized Order audit view. |

### Optional Order AI

- **Status Email** — optional contextual Studio action.
- **Marketing Post** — optional contextual Studio action.

Both are user-triggered helpers and are not needed to create, produce, or invoice an Order.

## 6. Approval Center — 5/5 Standout

**AI:** No.

| Feature | Maturity | What exists now |
|---|---:|---|
| Unified Authority Queue | 5 | Normalizes canonical Approvals, Decision Room activity, Signature Requests, and Proofs into one operational queue. |
| Search and filtering | 4 | Search across approvals/rooms/customer/messages, filter by type, and show unresolved-only. |
| Actionable queue rows | 5 | Activity, target, Customer, status, submission time, source, and direct open action. |
| Apply selected option | 5 | Staff can apply a selected Decision Room option to the linked Quote Line Item or Order Item. |
| Review acknowledgements | 4 | Staff can acknowledge customer decisions and visual overlays. |
| Customer-question response | 5 | Respond to and resolve room-level or option-level questions. |
| Proof actions | 4 | Approve or request changes with reason. |
| Create approval work | 5 | Search for a Quote, Order, Quote Line Item, Order Item, or other supported target, preserve customer/commercial context, and create a Decision Room. |
| Reusable history | 5 | Quote/Order views reuse the canonical Approval history. |
| Immutable Approval records | 5 | Approval, request-changes, and decline decisions preserve actor, source, snapshot, and audit metadata. |
| Broad parent support | 5 | Quote revisions, proof versions, contracts, Order Items, Work Order Summaries, and Webstore product/mockup/launch/terms approvals. |

## 7. Decision Rooms — 5/5 Standout

**AI:** No. This entire decision workflow is deterministic and human-controlled.

### Staff authoring

| Feature | Maturity | What exists now |
|---|---:|---|
| Linked commercial context | 5 | Link to Customer, Intake, Quote, Order, Quote Line Item, or Order Item. |
| Room identity and lifecycle | 5 | Internal name, customer title/introduction, draft/ready/published/expired/closed/archived, and optional expiration. |
| Customer permission controls | 5 | Allow/disallow save later, comments, questions, change requests, reject-all, and require internal acceptance. |
| Option cards | 5 | Customer label, internal name, headline, description, included/excluded features, timing, and price. |
| Merchandising badges | 5 | Recommended, best value, premium, budget, fastest, custom, or none; recommended exclusivity is enforced. |
| Price presentation | 5 | Show, hide, or contact-for-price; attach an immutable pricing snapshot or a human-entered manual price. |
| Media | 5 | Attach files, Proofs, visual markup, rendered previews, and thumbnails with safe/internal note separation. |
| Commercial apply target | 5 | Explicitly targets a Quote Line Item or Order Item. |
| Option management | 5 | Add, duplicate, reorder, archive, and restore. |
| Readiness validation | 5 | Requires publishable option count, customer labels, and valid price presentation. |
| Preview and immutable versions | 5 | Publishing creates a frozen version; later edits remain unpublished until a new version is released. |

### Secure sharing

| Feature | Maturity | What exists now |
|---|---:|---|
| Secure token links | 5 | Optional audience email, expiration (default seven days), multi-use support, and tenant/record scope. |
| Token handling | 5 | Link shown once, copy action, token history/status, new-token “resend,” and revocation. |
| Delivery boundary | 3 | The app creates the link but does not send email or SMS. Staff must copy and deliver it manually. |

### Customer decision experience

| Feature | Maturity | What exists now |
|---|---:|---|
| Public or authenticated access | 5 | Customer Portal or secure token opens the frozen published version. |
| Safe serialization | 5 | Only customer-safe fields/media are returned; storage paths and internal notes are excluded. |
| Compare options | 5 | Compare cards, media, features, price, and timing. |
| Select/reject/request change | 5 | Customer can select, reject an option, reject all when allowed, or request a change with comment. |
| Append-only decision history | 5 | A new selection supersedes the prior one instead of editing history; submission is idempotent. |
| Questions and replies | 5 | Room- or option-level questions; staff response and resolution; customer sees the answer. |
| Visual overlay pins | 5 | Add anchored comments with normalized coordinates; withdraw is exposed. Backend also supports edit, but the audited customer UI does not expose editing an existing pin. |
| Save for later | 4 | Explicit non-decision state. |
| Review queue | 5 | Assignment, acknowledgement/review, internal notes, and Approval Center integration. |
| Controlled commercial mutation | 5 | A customer choice never changes Quote/Order pricing by itself. Only staff Apply can mutate the linked item, and superseded selections cannot be applied. |
| Public rate limiting | 5 | Customer/public interactions are rate-limited. |

## 8. Proofs — 3/5 Solid but rough

**AI:** No.

| Feature | Maturity | What exists now |
|---|---:|---|
| Proof parent links | 4 | Order, Order Item, or Work Order. |
| Immutable versions | 4 | Current version plus preserved prior versions. |
| Status lifecycle | 4 | Draft, sent, viewed, approved, changes requested, cancelled, and superseded. |
| Staff Proofs panel | 3 | Create Proof, add version, and change state with reasons from the Order. |
| Public approval page | 4 | Single-purpose, single-use token supports approve or request changes with name/reason. |
| Approval Center actions | 4 | Proof decisions are actionable from the authority queue. |
| Customer Portal API | 3 | Backend supports portal Proof approval. |
| Customer Portal UI | 2 | Portal currently lists Proofs but does not expose the full backend approval workflow. |
| File selection | 2 | Staff enter/attach file identifiers rather than using a polished file picker. |
| Token creation/delivery | 2 | The audited Proofs panel does not provide a polished “create and send approval link” workflow. |

## 9. Signature Requests — 1/5 Foundation only

**AI:** No.

### What the backend genuinely supports

- Signature Request parent types: Proof, Contract, Work Order Summary, Quote, and Document.
- Multiple required signers with name, email, role, signed status, timestamp, and linked Signature record.
- Typed or drawn signature record types.
- Draft, sent, partially signed, completed, and cancelled statuses.
- Signer email matching, token reference, IP address, user agent, actor/timestamp audit data.
- Staff list/create/detail endpoints and a public token-backed signature endpoint.
- Signature Requests are normalized into the Approval Center queue.

### What is not finished

- There is no staff Signature Request page/component for creating, sending, or monitoring requests.
- There is no public frontend route/page where a signer can type or draw a signature.
- The model describes composite signed-PDF regeneration, but the current `record_signature` implementation only stores the Signature and updates signer/request status. It does not generate a signed PDF or new Document version.
- There is no polished cancellation, resend, reminder, or signer-replacement UI.

**Conclusion:** sell this only as a signature backend foundation, not as an e-signature feature.

## 10. Production — 5/5 Standout

**AI:** No.

### Work Orders and Work Order Summaries

| Feature | Maturity | What exists now |
|---|---:|---|
| Order-to-Work Order generation | 5 | Uses production-required Order Items only and blocks empty production handoffs. |
| Immutable item snapshot | 5 | Work Order preserves the commercial/production item snapshot. |
| Role-aware Work Order Summary | 5 | Selling/pricing information is hidden for users without the required permission. |
| Work Order lifecycle | 5 | Draft, released, queued, in progress, blocked, ready, completed, cancelled, and superseded. |
| Guarded transitions | 5 | State rules plus required reasons for blocked/cancelled paths. |
| Priority and due context | 4 | Low, normal, high, rush; requested/due dates, production instructions, and internal notes. |
| Assignment model | 5 | Multiple assignees, department, required role/skill/certification/equipment, and eligibility checks. |
| Versioning | 5 | Regenerate to a new version, supersede the prior one, preserve reason and history. |
| Detail workspace | 5 | Items, Stages, Details, and Activity tabs; print summary; schedule; task handoff. |

### Reusable production workflows

| Feature | Maturity | What exists now |
|---|---:|---|
| Starter workflows | 4 | Seeded reusable workflows. |
| Custom workflows | 4 | Create, duplicate, archive, restore, mark default, and assign product categories. |
| Workflow resolution preview | 4 | Preview which workflow applies; manual no-workflow fallback exists. |
| Stage definitions | 5 backend / 3 UI | Backend supports required/optional, skip reason, role, duration, due offsets, customer/employee visibility, prior-stage gate, Proof gate, equipment, certification, checklist, color, and icon. UI exposes a smaller subset such as name, role, ordering, add/archive. |
| Per-Order-Item override | 4 | Preview and save a workflow override before generating Work Order stages. |

### Stage execution

| Feature | Maturity | What exists now |
|---|---:|---|
| Stage actions | 5 | Assign, unassign, start, wait, block, resume, complete, skip, reopen, change due date, and add notes. |
| Dependency gates | 5 | Prior-stage gates, Proof gates, assignment/eligibility, required skip reasons. |
| History and audit | 5 | Append-only stage event history and unified production timeline. |

### Production Board

| Feature | Maturity | What exists now |
|---|---:|---|
| Live summary | 5 | Active, Ready, In Progress, Blocked, Waiting, Overdue, Unassigned, and Recently Done. |
| Queue views | 5 | Active, Blocked/Waiting, Ready, Unassigned, Overdue, and Completed Recently. |
| Grouping | 5 | Status, Stage, Assignee, or Due Date. |
| Sorting | 5 | Due Date, Priority, Oldest Waiting, Oldest Started, Customer, Work Order, and Last Updated. |
| Filters/search | 5 | Priority, stage status, Work Order, Order, Customer, item, and employee. |
| Rich board rows | 5 | Work Order, Order, Customer, item, current stage, Proof/Approval gate, blockers, eligibility, assignee/role, due time, waiting time, and progress. |
| Bulk actions | 5 | Assign, due date, wait, and note with partial-success/partial-failure reporting. |
| Docked Work Order workspace | 5 | Opens the record without abandoning the board. |

### Production Timeline

- Projects activity across Order, Order Item, and Work Order scope.
- Includes audit events, Approvals, Proofs, files, and production events.
- Filtering, pagination, and deduplication are implemented.

### Production Kiosk

| Feature | Maturity | What exists now |
|---|---:|---|
| Device activation/session | 5 | Persistent device session, expiry, revoke, and employee switching. |
| Employee PIN access | 5 | Employee ID plus PIN, rate limiting, and safe session handling. |
| Work queues | 5 | Current Task, Assigned, Ready for Me, Shop Queue, Blocked/Waiting, and Recently Completed by Me. |
| Stage execution | 5 | Reuses the canonical stage service instead of maintaining a separate kiosk state machine. |
| Supervisor Start override | 5 | One-time, action-specific override with reason and audit. |
| Time Clock | 4 | Separate kiosk panel for clock in/out. |
| Offline behavior | 3 | Detects offline state and disables actions. There is no offline action queue. |

## 11. Shop Schedule — 4/5 Advanced

**AI:** No.

| Feature | Maturity | What exists now |
|---|---:|---|
| Operational calendar feed | 4 | Combines canonical calendar events, tasks, and production-stage schedule items. |
| Views | 4 | Calendar, Agenda, and Appointments. |
| Appointment types | 4 | Consultation, site survey, vehicle drop-off, vehicle pickup, installation, customer meeting, production milestone, and custom. |
| Create/edit appointment | 4 | Title, type, assigned employee, date/time/timezone, location, notes, and linked record identifiers. |
| Record linking | 4 | Customer, Order, and Work Order context; deep links can prefill the create flow. |
| People and resources | 4 | Employees plus equipment, vehicles, and custom schedulable resources. |
| Availability/conflict engine | 5 | Identifies the blocked resource, prevents ordinary save, and records an authorized override reason/history. |
| Filters | 4 | Employee, equipment, vehicle, custom resource, attention state, appointment type, and linked-record state. |
| Search | 4 | Search across the operational schedule. |
| Navigation/summary | 4 | Today/date movement, visible-period summary, and responsive calendar/list layouts. |
| Operational boundary | 4 | Shop Schedule excludes employee shift/absence administration; that lives in Team Schedule. |

**Navigation note:** Schedule is present in the current Shop Operations navigation. That should be treated as the current repo behavior even if a later product-information architecture decides to move it.

## 12. Webstores — 4/5 Advanced, broad, and still uneven

**AI:** Optional for per-product drafts. Planned/inactive for the large “AI Product Suggestions” panel.

### Guided creation and owner setup

| Feature | Maturity | What exists now |
|---|---:|---|
| Store types | 4 | B2B, fundraiser, event, promotional, and general; legacy employee-store data remains readable but new employee type creation is blocked. |
| Four-step creation | 4 | Type, Owner, Basics, and Branding & products. |
| Owner modes | 4 | New owner, existing Customer, or the current business/account. |
| Basic configuration | 4 | Store name, purpose/welcome, open/close dates, public/restricted access, initial colors, greeting, starting products, logo, and banner. |
| Guided checklist | 4 | Questionnaire, answers review, product building, launch packet, and launch gates. |

### Assignments, invitations, and questionnaire

| Feature | Maturity | What exists now |
|---|---:|---|
| Owner/manager assignments | 5 | Primary owner plus manager roles, assignment-scoped portal access, tenant isolation, and role rules. |
| Invitation lifecycle | 5 | Hashed one-time invitations, resend, revoke, acceptance, conflict checks, and audit. |
| Type-specific questionnaire | 5 | Templates for store type, draft/save, required-answer validation, submit, repeat-safe submission, and frozen answer snapshot. |
| Answer review | 5 | Staff previews proposed non-pricing changes, selects which answers to apply, applies idempotently, and can reverse the application. |
| Type-change safety | 4 | Controls when a store type may change and records inactive answer paths/history. |
| Setup files | 5 backend / 3 UI | Validated/allowlisted formats, version replacement, safe SVG handling, and download. UI supports uploading categorized setup files. |
| Missing-information request | 0 | The visible button is disabled. |
| View full questionnaire | 1 | A disabled button remains in the current product-plan area even though response data is available elsewhere. |

### Branding and storefront design

| Feature | Maturity | What exists now |
|---|---:|---|
| Branding sections | 5 | Brand basics, colors/fonts, header/announcement, hero, store information, type-specific content, catalog introduction, and footer. |
| Image slots and accessibility | 5 | Logo/alternate/social/hero/supporting images, format validation, SVG limited to logo use, and alternate-text checks. |
| Section visibility | 5 | Header, hero, catalog, and other areas can be hidden intentionally. |
| Desktop/mobile preview | 5 | Live draft preview in both form factors. |
| Review workflow | 5 | Save draft, request owner review, owner approve or request changes, and staff publish. |
| Published-version safety | 5 | Public storefront never receives an unpublished draft; an existing published version stays live while a replacement is reviewed. |
| History/activity | 5 | Published version history, feedback, validation warnings/errors, and branding activity. |

### Product catalog

| Feature | Maturity | What exists now |
|---|---:|---|
| Product templates | 4 | Platform starter templates and tenant templates; create a product from a template. |
| Product categories | 4 | Assign, edit, archive/restore, preserve legacy free-text categories, and show active-product counts. New-category creation is still described as belonging to a later/shared resource flow. |
| Catalog management | 5 | Create blank product, duplicate, reorder, archive, restore, search, filter by status/category, and select a focused editor. |
| Basic product data | 5 | Name, type, category, SKU, short/full description, catalog status, and packet eligibility. |
| Images and mockups | 5 | Primary/secondary customer images with file or safe URL and alt text; attach private artwork and mockup associations. |
| Variants/SKUs | 5 | Size, color, style/name, variant SKU, and variant price. |
| Inventory | 4 | Inventory policy and quantity with server-side availability enforcement. |
| Personalization | 5 | Configurable fields, labels, required state, placeholders/limits, and public validation. |
| Pricing and shares | 5 | Selling price, production cost, owner share, fundraiser share, and platform-fee basis points in integer cents. |
| Production mapping | 5 | Production method, internal production notes, private supplier/source, private fulfillment notes, and preserved Webstore snapshot into production. |
| Bundles | 4 | Associate bundle items/products. |
| Approval | 5 | Product and Mockup submission/approval with revisions, owner decisions, comments, history, and canonical Approval rows. |

### Launch packet, terms, and lifecycle

| Feature | Maturity | What exists now |
|---|---:|---|
| Launch Packet | 5 | Immutable, versioned snapshot with promotion copy, owner preview, included products, QR destination reference, generator, timestamp, and hash. |
| Packet delivery/decision | 5 | Send to owner portal, approve, reject with reason, or request changes. |
| Change Requests | 5 | Open, respond, resolve, and block launch readiness until resolved. |
| Terms acceptance | 5 | Versioned terms/fee acknowledgement; a new required terms version invalidates readiness. |
| Launch gates | 5 | Questionnaire, products, branding, packet, terms, public positive-price catalog, open change requests, and payment-provider readiness. |
| Material-change invalidation | 5 | Changing meaningful product/launch data invalidates prior packet approval. |
| Lifecycle | 5 | Draft/setup states, approved, launch ready, live, paused, closed, archived, and relaunch-ready with reasons and audit. |
| Pause/close/archive | 5 | Disables checkout while preserving historical Orders and confirmation receipts. |
| Relaunch | 5 | Rechecks deadlines and every readiness gate before creating an audited relaunch-ready transition. |

### Public storefront and cart

| Feature | Maturity | What exists now |
|---|---:|---|
| Public store by global slug | 5 | Only live/customer-safe data is serialized; internal costs, notes, tenant data, and storage details are redacted. |
| Product list/detail | 4 | Public cards plus an inline detail view. |
| Variant/personalization selection | 5 | Required options and personalization are enforced server-side. |
| Fulfillment choice | 4 | Pickup/shipping selection when configured. |
| Cart | 5 | Add/remove, quantity changes, server-repriced quote, expiration, and zero order side effects before checkout. |
| Server-authoritative totals | 5 | Product subtotal, shipping, donation, discount, and total; rejects public money fields and tampering. |
| Fundraiser functions | 5 | Optional donation, promo codes, and progress based only on verified paid sales. |
| Secure checkout | 4 | Creates a provider checkout session only when Webstore Stripe readiness is verified; displays a Stripe-hosted checkout URL. |
| Verified payment boundary | 5 | Webhooks normalize pending, failed, paid, refund, transfer, and payout signals with idempotency and authority checks. |
| Confirmation receipt | 5 | Token-protected, customer-safe confirmation remains available even after close/archive. |

### Canonical Orders, Production, reporting, and Stripe Connect

| Feature | Maturity | What exists now |
|---|---:|---|
| Paid Order bridge | 5 | Verified payment creates/reuses Customer, canonical confirmed Order, Order Items, and Payment; exact checkout snapshot is preserved and retries recover safely. |
| Orders projection | 5 | Staff and owner views read canonical Orders and redact internal/provider fields. |
| Production handoff | 5 | Idempotently creates one current Work Order and preserves product, variant, and production mapping snapshots. |
| Staff reporting | 5 backend / 3 UI | Orders, gross sales, refunds, payouts, product quantities, production load, platform fee, and owner share. Current staff UI shows only a compact subset. |
| Owner reporting | 4 | Customer-safe summary excludes internal platform fee and production load. |
| Stripe Connect controls | 4 | Connect, resume onboarding, refresh status, and view requirements. Real capability depends on provider configuration and verified account readiness. |
| Refund/ledger integrity | 5 backend | Provider refunds and immutable proportional ledger reversals; original fee rows are preserved. Staff refund management is not a rich Webstore UI. |

### Webstore AI

| AI feature | Maturity | Behavior |
|---|---:|---|
| Product description draft | 4 | Preview credit cost, require explicit confirmation, create an editable review draft, charge through the AI credit ledger, and never overwrite product copy automatically. |
| Product mockup concept | 4 | Preview/confirm cost and create a non-production-ready generated concept asset; does not create/approve a canonical Webstore Mockup automatically. |
| Manual alternative | 5 | Manual product setup remains available even when AI entitlement/credits/provider are unavailable. |
| AI Product Suggestions panel | 0 | Explicitly says recommendations, pricing/share estimates, selectable suggestions, and regeneration are planned; all controls are disabled. |

### Webstore polish defects to fix before calling it fully product-complete

- One Review & Launch button still says public commerce waits for “Stage 6/7” and is disabled, although the guided setup module can launch a ready store and later commerce stages exist.
- The large AI Product Suggestions area is a placeholder even though per-product AI drafts are live.
- “View Full Questionnaire,” “Request Missing Information,” and some shared category-resource controls are disabled.
- Stripe commerce is real only when the runtime is configured with a verified provider account; automated tests use mocked provider calls.
- The setup page contains very many advanced controls and two layers of setup navigation, making it functionally broad but cognitively heavy.

## 13. Wrap Lab — 2/5 Basic UI over an advanced backend foundation

**AI:** Optional contextual links only. Core Wrap Lab does not require AI.

### Advanced backend/data capabilities

| Feature | Backend maturity | What exists |
|---|---:|---|
| Vehicle records | 4 | Customer, year, make, model, type, template key, VIN/reference fields. |
| Wrap Project lifecycle | 5 | Lead intake → vehicle recorded → measurement planning → estimate ready → Quote linked → contract/deposit pending → pre-install ready/signed → design → Proof ready/approved → panel plan → production → installation → completion → warranty → archive. Only one-step normal advancement is allowed. |
| Financial estimates | 4 | Estimate, deposit, material estimate, labor estimate, material cost, labor cost, and warranty value in integer cents. |
| Coverage plans | 5 | Coverage level, measured vehicle panels, dimensions, statuses, and derived square footage. |
| Pre-install inspections | 5 | Damage items, panel/type/notes/coordinates, acknowledgements, signature-request link, and status. |
| Vector design-scene contract | 5 | Vehicle template, artboard, scale, groups/layers, locked layers, original logo asset identity, and production preflight results. |
| Original-asset safety | 5 | Locked layers reject edits; AI logo replacement, silent redrawing, and font substitution are outside the allowed contract. |
| Panel planning/export manifest | 5 | Printer-width-aware panel splitting/labels, material/labor cost snapshots, and ready-for-production state. |
| Schedule references | 4 | Wrap schedule records can reference calendar events. The EC15 service itself does not create the canonical calendar event. |
| Packets | 4 | Immutable revisioned pre-install, Work Order, completion, and warranty/aftercare snapshots with a layout contract. This is a snapshot contract, not a verified exported PDF workflow in the audited UI. |
| Warranty/aftercare | 4 | Active warranty, terms, care instructions, dates, and value. |
| Reports | 3 | Project counts, estimate/deposit totals, and status counts. |
| Security | 5 | Staff-only permission/entitlement boundary, tenant isolation, archive read-only behavior, and portal-token rejection. |

### Current frontend limitations

| UI feature | Maturity | Limitation |
|---|---:|---|
| Project list/report cards | 3 | Useful list, status filters, totals, and click-through. |
| New Wrap Project | 2 | Requires raw Customer ID; hard-codes vehicle type to van and project type to partial wrap. |
| Vehicle layout | 1 | Static generic SVG “flat production profile,” not an interactive vehicle template/editor. |
| Advance workflow | 2 | One button advances to the next status; no stage-specific forms, prerequisites, or exception handling in the UI. |
| Create Coverage | 1 | Button submits three hard-coded sample panels and measurements. |
| Create Inspection | 1 | Button submits a hard-coded scratch and acknowledgement. |
| Create Vector Scene | 1 | Button creates hard-coded template/logo/background layers, including a placeholder source file ID. |
| Create Panel Plan | 1 | Button submits hard-coded panel sizes and costs. |
| Schedule Install | 1 | Button schedules “now plus four hours,” not a real date/resource selector. |
| Create Warranty | 1 | Button submits fixed sample terms/instructions. |
| Packet builder | 2 | User can choose packet type and create revisions, but not deeply edit/review/export a polished packet. |
| Production summary | 2 | Displays up to five panel/damage/export entries; no real editor. |

### Optional Wrap AI

- **Wrap Concept** — contextual link to the Vehicle Graphics Studio.
- **Cost Guidance** — contextual link to Pricing & Profitability.

These are navigation helpers; they do not automatically populate or mutate the Wrap Project.

**Conclusion:** the domain model is ambitious and technically thoughtful, but the current UI should be described as a prototype/demo shell. It is not yet a production Wrap Lab editor.

## 14. Cross-linked Invoices and Payments — 3/5 Solid backend, mixed UI

**Canonical section:** Business & Finance, not Shop Operations. Included here because Orders create/open Invoices.

**AI:** Optional Payment Email helper only. Money and reconciliation never require AI.

### Invoices

| Feature | Maturity | What exists now |
|---|---:|---|
| One Invoice per Order | 5 | Unique tenant/order constraint and idempotent Order handoff. |
| Dual status | 5 | Independent document status (draft/issued/void) and backend-derived financial status (unpaid/partial/paid/refunded/voided). |
| Backend-derived money | 5 | Subtotal, discount, tax, fee, total, paid, refunded, and balance in integer cents. |
| Invoice list | 4 | Filters and table with total, balance, and paired document/financial status. |
| Draft editing | 4 | Title, total, due date, description, and notes while draft. |
| Issue and void | 5 | Issue action; void requires a reason and is blocked while confirmed net payments remain. |
| Email Invoice | 4 | Editable composed email; optional AI Payment Email button opens Studio. |

### Payments

| Feature | Maturity | What exists now |
|---|---:|---|
| Manual payments | 5 | Cash, check, external card, external bank transfer, or other; positive amount and idempotency required. |
| Overpayment prevention | 5 | Rechecked race-safely at write time. |
| Manual void | 5 | Confirmed manual payment can be voided with reason. Stripe payments cannot be manually voided. |
| Stripe payment intent | 4 backend | Server-initiated Payment Intent boundary and provider identifiers. |
| Refund | 5 backend | Stripe confirmed payments can be refunded with reason; reconciliation updates totals and history. |
| Payment history | 4 | Staff view shows status, source/method, amount, provider/reference masking, void, and refund actions. |
| Reconciliation | 5 | Runs on every write/provider event and derives financial status and balance. |

### Customer Portal invoice payment limitation

The portal page shows Invoice status, total, paid, balance, amount selection, and Payment history. However, the code explicitly says production should mount Stripe.js Payment Element; the current page instead exposes a development-only “Simulate secure card confirmation” button. Therefore the portal payment screen is not a production-ready card-entry experience even though the backend Payment Intent/reconciliation contracts are strong.

## 15. Customer Portal support — 3/5 Mixed

**AI:** No.

| Portal area | Maturity | Current state |
|---|---:|---|
| Authentication/identity | 4 | Magic-link/password boundary, portal identity presets, create/update/resend, and strict staff-token vs portal-token separation. |
| Decision Rooms | 5 | Full customer decision experience. |
| Invoice payment | 2 UI / 4 backend | Full invoice/payment data and intent endpoints, but frontend confirmation is a development simulation. |
| Quotes | 2 UI / 4 backend | Portal lists Quotes; backend has detail/approval endpoints, but the frontend does not provide the full detailed approval route. |
| Orders | 2 UI / 4 backend | Portal list is present; backend detail exists, but frontend interaction is thin. |
| Proofs | 2 UI / 4 backend | Portal list exists; backend can approve/request changes, but frontend does not expose the complete action flow. |
| Documents | 2 | List-focused. |
| Messages | 2 | List-focused/basic. |
| Profile | 4 | Customer can edit permitted profile fields. |
| Webstore owner portal | 5 | Separate, deep owner/manager portal for questionnaire, branding, product/mockup approvals, launch packet, terms, change requests, and reporting. |

## 16. Voice capability — outside Shop Operations

The user-facing “voice” feature is the Business Assistant at `/studio/assistant`; it is not embedded in Quotes, Orders, Production, or Decision Rooms.

**Score:** 3/5 Solid provider-gated AI capability.  
**AI/provider:** Required for this feature. Requires the Business Assistant entitlement/permission, AI credits, `OPENAI_API_KEY`, and Realtime enabled.

### What exists

- Text assistant with Owner, Operations, Finance, Production, and Workforce modes.
- Context indicator for the current record/query-string context.
- Source/citation display for supported operational/BI answers.
- Quick actions, action-proposal cards, memory controls, routines, proactive insights, and Studio delegation.
- Safe action lifecycle: propose, edit, confirm, execute, cancel, stale/unsupported handling, idempotency, and target revalidation.
- Email/report actions create editable drafts only; they never auto-send.
- OpenAI Realtime browser voice using backend-issued short-lived credentials and WebRTC.
- Push-to-talk default, optional voice-activity detection, interrupt/end controls, transcript, and text fallback.
- Voice states for connecting, listening, thinking, speaking, interrupted, reconnecting, unavailable, microphone denied, and error.
- Provider usage metering from explicit events; raw voice audio is not stored by default.
- If no OpenAI key or Realtime setting is present, the UI/API reports Voice is not configured and does not fake a session.

### What voice does not mean

- It is not required for any Shop Operations workflow.
- It does not silently modify Quotes, Orders, payments, production records, or customer communications.
- Tool calls initiated by voice still create a proposal and require explicit confirmation before a state-changing action executes.

## Strongest differentiators in the current app

1. **Decision Rooms** — unusually deep, versioned, customer-safe decision authority tied to commercial line items.
2. **Quote and Order pricing integrity** — server-derived totals, pricing snapshots, revisions, profitability, and safe conversion.
3. **Approval Center** — normalized cross-feature authority queue with real action controls.
4. **Production Board + stage engine + kiosk** — mature execution system with gates, bulk operations, and a safe shared core.
5. **Webstore setup-to-paid-order-to-production bridge** — broad ownership, branding, approval, commerce, canonical Order, reporting, and Work Order flow.
6. **Customer merge and related-record hub** — strong operational data foundation.

## Most important incomplete or risky claims

1. **Do not call Signature Requests a complete e-signature system.** Backend records exist; the staff/public UI and signed PDF output do not.
2. **Do not claim Intake converts to Quotes/Orders end-to-end.** Preview/status linking exists; record creation is missing.
3. **Do not call Wrap Lab production-ready.** Its UI posts hard-coded sample data and lacks real editors/resource selection.
4. **Do not call Order Files & Artwork finished.** The tab is informational only.
5. **Do not claim the customer portal is equally deep in every module.** Decision Rooms are deep; Quotes/Orders/Proofs/Documents/Messages are mostly list-first.
6. **Do not call portal card payment production-ready.** The frontend still uses a development confirmation simulator instead of mounted Stripe Elements.
7. **Do not claim AI Product Suggestions are live.** Per-product AI description/mockup drafts are live; the broader suggestion/planning panel is explicitly disabled.
8. **Do not say Decision Room links are emailed automatically.** The app mints and revokes secure links; staff deliver them manually.
9. **Do not describe core Shop Operations as AI-dependent.** Quotes, Orders, Customers, approvals, Production, Schedule, Webstores manual setup, and Decision Rooms all work without AI.

## Recommended product-language summary

The current MVP is strongest as an integrated shop operating system for **Customers → Intake → Quotes → Orders → approvals/Decision Rooms → Work Orders → staged Production**, with advanced Webstores layered into the same Order and production core. AI is an optional helper around content, pricing guidance, and assistant interactions; it is not the authority for commercial totals, approvals, customer decisions, or production state.

The features that need the clearest “beta/foundation” wording are **Signature Requests, Wrap Lab, portal card payment, Intake conversion, and Order Files & Artwork**.

## Principal code evidence

- Current navigation: [`frontend/src/lib/navigation.js`](https://github.com/dnblack323/SIGNGUY-MVP/blob/82361811b80000392fa318e771bb9ff443ab62c4/frontend/src/lib/navigation.js)
- Quotes and Orders UI: [`frontend/src/pages/QuoteDetailPage.jsx`](https://github.com/dnblack323/SIGNGUY-MVP/blob/82361811b80000392fa318e771bb9ff443ab62c4/frontend/src/pages/QuoteDetailPage.jsx), [`frontend/src/pages/OrderDetailPage.jsx`](https://github.com/dnblack323/SIGNGUY-MVP/blob/82361811b80000392fa318e771bb9ff443ab62c4/frontend/src/pages/OrderDetailPage.jsx)
- Approval Center: [`frontend/src/pages/ApprovalCenterPage.jsx`](https://github.com/dnblack323/SIGNGUY-MVP/blob/82361811b80000392fa318e771bb9ff443ab62c4/frontend/src/pages/ApprovalCenterPage.jsx)
- Decision Rooms: [`frontend/src/pages/DecisionRoomEditorPage.jsx`](https://github.com/dnblack323/SIGNGUY-MVP/blob/82361811b80000392fa318e771bb9ff443ab62c4/frontend/src/pages/DecisionRoomEditorPage.jsx), [`backend/app/services/decision_rooms.py`](https://github.com/dnblack323/SIGNGUY-MVP/blob/82361811b80000392fa318e771bb9ff443ab62c4/backend/app/services/decision_rooms.py)
- Production: [`frontend/src/pages/ProductionPage.jsx`](https://github.com/dnblack323/SIGNGUY-MVP/blob/82361811b80000392fa318e771bb9ff443ab62c4/frontend/src/pages/ProductionPage.jsx), [`frontend/src/pages/ProductionKioskPage.jsx`](https://github.com/dnblack323/SIGNGUY-MVP/blob/82361811b80000392fa318e771bb9ff443ab62c4/frontend/src/pages/ProductionKioskPage.jsx)
- Shop Schedule: [`frontend/src/pages/ShopSchedulePage.jsx`](https://github.com/dnblack323/SIGNGUY-MVP/blob/82361811b80000392fa318e771bb9ff443ab62c4/frontend/src/pages/ShopSchedulePage.jsx)
- Webstores: [`frontend/src/pages/WebstoreDetailPage.jsx`](https://github.com/dnblack323/SIGNGUY-MVP/blob/82361811b80000392fa318e771bb9ff443ab62c4/frontend/src/pages/WebstoreDetailPage.jsx), [`backend/app/services/webstores.py`](https://github.com/dnblack323/SIGNGUY-MVP/blob/82361811b80000392fa318e771bb9ff443ab62c4/backend/app/services/webstores.py)
- Wrap Lab: [`frontend/src/pages/WrapLabDetailPage.jsx`](https://github.com/dnblack323/SIGNGUY-MVP/blob/82361811b80000392fa318e771bb9ff443ab62c4/frontend/src/pages/WrapLabDetailPage.jsx), [`docs/modules/ec15_wrap_lab.md`](https://github.com/dnblack323/SIGNGUY-MVP/blob/82361811b80000392fa318e771bb9ff443ab62c4/docs/modules/ec15_wrap_lab.md)
- Signatures: [`backend/app/models/signature.py`](https://github.com/dnblack323/SIGNGUY-MVP/blob/82361811b80000392fa318e771bb9ff443ab62c4/backend/app/models/signature.py), [`backend/app/services/approvals_signatures_service.py`](https://github.com/dnblack323/SIGNGUY-MVP/blob/82361811b80000392fa318e771bb9ff443ab62c4/backend/app/services/approvals_signatures_service.py)
- Invoices and payments: [`docs/modules/invoices.md`](https://github.com/dnblack323/SIGNGUY-MVP/blob/82361811b80000392fa318e771bb9ff443ab62c4/docs/modules/invoices.md), [`docs/modules/payments.md`](https://github.com/dnblack323/SIGNGUY-MVP/blob/82361811b80000392fa318e771bb9ff443ab62c4/docs/modules/payments.md)
- Voice assistant: [`docs/modules/ec18_business_assistant.md`](https://github.com/dnblack323/SIGNGUY-MVP/blob/82361811b80000392fa318e771bb9ff443ab62c4/docs/modules/ec18_business_assistant.md)
