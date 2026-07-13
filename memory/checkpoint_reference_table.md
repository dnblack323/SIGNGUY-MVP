# SignGuy AI — Checkpoint Reference Table

**Purpose:** One table naming every checkpoint (old and new numbering), its controlling document, its status, and its holds. Created 2026-02 during the SignGuy AI Checkpoint Specification Pack intake. Supersedes the checkpoint-status tables in `/app/memory/PRD.md` and `/app/memory/progress_register.md` only insofar as EC9 onward is concerned — both files are kept in sync with this table rather than duplicating it.

## EC0–EC8 (original numbering — unaffected by the new pack)

| EC | Name | Status | Controlling document |
|---|---|---|---|
| EC0 | Owner Decisions and Governance Lock | COMPLETE | Old master plan Part 4 |
| EC1 | Security and Permanent App Guardrails | COMPLETE | Old master plan (EC1–EC8 sections remain authoritative) |
| EC2 | Shared Platform Services | COMPLETE | ″ |
| EC3 | Quotes, Orders, Order Items, Pricing Snapshots | COMPLETE | ″ |
| EC4 | Invoices, Payments, and Stripe Core | COMPLETE | ″ |
| EC5 | Production and Work Orders | COMPLETE | ″ |
| EC6 | Asset Library, Proofs, Signatures, Customer Portal | COMPLETE | ″ |
| EC7 | Inventory, Purchasing, Finance, Reporting (incl. A.3 Supplier Catalog) | COMPLETE | ″ |
| EC8 | Team, Scheduling, Time, Payroll, Employee Portal, Equipment/Training/Certification (incl. A.5) | DELIVERED / CLOSED | ″ |

## EC9–EC22 (new numbering — SignGuy AI Checkpoint Specification Pack, authoritative from here on)

| EC | Name | Status | Controlling document | Absorbs/carries forward | Holds |
|---|---|---|---|---|---|
| **EC9** | Pricing Foundation, Detailed Calculators, and Exact Order Workflow | **IN PROGRESS — Phase 9A + 9B COMPLETE (9C–9H remaining)** | `EC09_Pricing_Foundation_Calculators_and_Order_Pricing.docx` | Old master plan Appendix A.2 (EC3.1 Pricing Foundation Verification). Preflight + Phase 9A/9B decision record & evidence: `/app/preflight/EC9_PRICING_FOUNDATION_CALCULATORS_AND_ORDER_PRICING_PREFLIGHT.md` | H1 |
| **EC10** | Order Intake, Visual Markup, Customer Decision Room, and Templates | NOT STARTED | `EC10_Order_Intake_Visual_Markup_Decision_Room_and_Templates.docx` | Old master plan Appendix A.1 (EC6.3 Order Intake/Visual Markup); adds the new Customer Decision Room + reusable Templates | H1 |
| **EC11** | Production Timeline, Workflow Configuration, Stage Tracking, and Kiosk | NOT STARTED | `EC11_Production_Timeline_Workflows_Kiosk_and_Advanced_Tracking.docx` | Advanced Production Tracking & Bottleneck Analytics Add-On (registered permanent future scope from EC8 Phase 8c) | H1 |
| **EC12** | Tasks, Kanban, Messages, Notes, Calendar, Appointments, Shop Schedule, and Community | NOT STARTED | `EC12_Productivity_Messaging_Calendar_Appointments_and_Community.docx` | — | H1 |
| **EC13** | Commercial Billing, Entitlements, Fees, Trials, and Setup Packages | NOT STARTED | `EC13_Commercial_Billing_Fees_Trials_Setup_and_Entitlements.docx` | Old master plan Appendix A.4 / `REVISED_COMMERCIAL_SOURCE_OF_TRUTH_2026-07.md` (confirmed; C1/C2 contradictions RESOLVED 2026-02 — see hold register) | H1 |
| **EC14** | Webstores | NOT STARTED | `EC14_Webstores_Master_Specification.docx` | Old master plan EC9 (Webstores and Stripe Connect) / 7A.30 / Part 14 | H1, **H2**, C1 (RESOLVED) |
| **EC15** | Wrap Lab | NOT STARTED | `EC15_Wrap_Lab_Master_Specification.docx` | Old master plan EC10 (Wrap Lab / Wrap Command Center) / 7A.29 / Part 15 | H1, **H3**, **H6**, C1 (RESOLVED) |
| **EC16** | Shared AI Gateway, Usage, Cost, Credits, and Governance | NOT STARTED | `EC16_Shared_AI_Gateway_Cost_Credits_and_Governance.docx` | Old master plan EC11 (Creative Studio and AI Credits) — gateway/ledger half | H1, **H4**, H7 |
| **EC17** | Studio AI Tools, Prompt Library, Generated Assets, and AI Activity | NOT STARTED | `EC17_Studio_AI_Tools_OWNER_REVIEW_REQUIRED.docx` | Old master plan EC11 — tool-catalog half | H1, **H4**, **H5/H8 (blocking)**, H7, C3 (RESOLVED — no separate AI tiers; see hold register) |
| **EC18** | Paid Business Assistant, Actions, Intelligence, and Realtime Voice | NOT STARTED | `EC18_Paid_Business_Assistant_Actions_Intelligence_and_Voice.docx` | New scope (not in old master plan) | H1, **H4** |
| **EC19** | Onboarding, Help Center, Contextual Help, and App Documentation | NOT STARTED | `EC19_Onboarding_Help_and_App_Documentation.docx` | Old master plan EC12 — onboarding/help half | H1 |
| **EC20** | Platform Admin, Analytics, Dunning, and Support | NOT STARTED | `EC20_Platform_Admin_Analytics_Dunning_and_Support.docx` | Old master plan EC12 — platform admin/community half | H1, C2 (RESOLVED — day-based model authoritative, 3-strikes superseded; see hold register) |
| **EC21** | Marketing Website, Public Pricing, Founder Offer, and Signup | NOT STARTED | `EC21_Marketing_Public_Pricing_Founder_and_Signup.docx` | Old master plan EC13 — marketing/public-pricing half | H1 |
| **EC22** | Final Integration and Commercial Release Hardening | NOT STARTED | `EC22_Final_Integration_and_Commercial_Release_Hardening.docx` | Old master plan EC14 (Commercial Release Hardening) | H1 (closes only after EC9–EC21 all COMPLETE) |

## Source precedence (per Master Index §4)

1. This checkpoint pack and later written owner corrections.
2. The final uploaded topic specifications (the 15 docx files themselves).
3. Current MVP architecture and completed checkpoint evidence (EC0–EC8).
4. Older consolidated plans (old master plan, scope register, readiness matrix, source map).
5. Legacy donor repositories as behavior references only.

**Table last updated:** 2026-02 — SignGuy AI Checkpoint Specification Pack intake. No checkpoint above has started.
