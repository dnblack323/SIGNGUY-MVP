# SignGuy AI — Documentation Authority Register

**Purpose:** Single register naming every planning document in the repository and its exact authority ranking, so no two documents wear the same crown. Created 2026-02 during the SignGuy AI Checkpoint Specification Pack intake.

## Authority order (highest wins on conflict)

1. **Explicit current owner decisions** — this Prompt + subsequent owner ratifications (verbal/chat instructions), always wins.
2. **`/app/specs_pack/extracted/*.docx`** — the SignGuy AI Checkpoint Specification Pack (Master Index + EC09–EC22). **Authoritative for all remaining work from EC9 onward.** Supersedes the old master plan's EC9–EC14 sections.
   - `00_Master_Index_and_Owner_Decision_Register.docx`
   - `EC09_Pricing_Foundation_Calculators_and_Order_Pricing.docx`
   - `EC10_Order_Intake_Visual_Markup_Decision_Room_and_Templates.docx`
   - `EC11_Production_Timeline_Workflows_Kiosk_and_Advanced_Tracking.docx`
   - `EC12_Productivity_Messaging_Calendar_Appointments_and_Community.docx`
   - `EC13_Commercial_Billing_Fees_Trials_Setup_and_Entitlements.docx`
   - `EC14_Webstores_Master_Specification.docx`
   - `EC15_Wrap_Lab_Master_Specification.docx`
   - `EC16_Shared_AI_Gateway_Cost_Credits_and_Governance.docx`
   - `EC17_Studio_AI_Tools_OWNER_REVIEW_REQUIRED.docx`
   - `EC18_Paid_Business_Assistant_Actions_Intelligence_and_Voice.docx`
   - `EC19_Onboarding_Help_and_App_Documentation.docx`
   - `EC20_Platform_Admin_Analytics_Dunning_and_Support.docx`
   - `EC21_Marketing_Public_Pricing_Founder_and_Signup.docx`
   - `EC22_Final_Integration_and_Commercial_Release_Hardening.docx`
3. **`/app/memory/checkpoint_reference_table.md`**, **`/app/memory/owner_specification_hold_register.md`**, **`/app/memory/permanent_backlog_register.md`** — working registers derived from #2, kept in sync with it.
4. **`/app/memory/PRD.md`** and **`/app/memory/progress_register.md`** — live status trackers, reconciled against #2 and #3.
5. **`/app/SIGNGUY_AI_FINAL_CONSOLIDATED_MASTER_BUILD_PLAN.md`** — **authoritative for EC0–EC8 (all COMPLETE/CLOSED).** For EC9 onward, this document is SUPERSEDED / HISTORICAL REFERENCE ONLY where it conflicts with #2 (superseded sections are marked inline: Part 30A.10–30A.15, Appendix A.4).
6. **`/app/docs/commercial/REVISED_COMMERCIAL_SOURCE_OF_TRUTH_2026-07.md`** — SUPERSEDED / HISTORICAL REFERENCE ONLY where it conflicts with the new pack's EC13/EC19/EC21 (one open contradiction on standalone pricing — see hold register).
7. **`/app/SIGNGUY_AI_FINAL_SCOPE_AND_DECISION_REGISTER.md`**, **`/app/SIGNGUY_AI_FEATURE_READINESS_MATRIX.md`**, **`/app/SIGNGUY_AI_REPOSITORY_AND_ARCHITECTURE_SOURCE_MAP.md`** — historical EC0–EC8 evidence/reference only. Not authoritative for EC9 onward.
8. **`/app/memory/AGENT_INSTRUCTIONS.md`** — permanent LOCKED implementation rules (terminology, money policy, navigation, security, permissions, module standard). These rules are unaffected by the new pack and remain binding.
9. **`/app/memory/product_ideas_register.md`** — unscheduled product ideas backlog (distinct from the permanent, committed backlog in `permanent_backlog_register.md`).
10. **`/app/memory/completion_register.md`** — historical completion log for EC0–EC2 (superseded in practice by the fuller `progress_register.md`, kept for provenance).
11. Existing MVP code behavior (`/app/backend/app/**`, `/app/frontend/src/**`) — evidence of current working system, not a planning authority.
12. Legacy donor repositories — behavior references only, never authoritative.

## What overrides what (worked examples)

- The new pack's EC14 saying "Webstores" **overrides** every older document's "Order Portal" phrasing (master plan, REVISED_COMMERCIAL doc, code comments/file names may lag — cosmetic rename is not authorized yet, see hold register).
- The new pack's EC15 saying "Wrap Lab" **overrides** every older document's "Wrap Command Center" phrasing.
- The new pack's EC13 pricing numbers **override** the old master plan Decision 10/11 and Appendix A.4 wherever they conflict — including standalone pricing, now resolved by explicit owner decision 2026-02 (Webstores standalone $109/mo, Wrap Lab standalone $139/mo, annual not yet approved for either) — see `owner_specification_hold_register.md`.
- `/app/memory/AGENT_INSTRUCTIONS.md` LOCKED technical rules (money policy, terminology, tenant isolation, permission model) are unaffected by the new pack and remain binding on all future checkpoints.

## Naming corrections registered (2026-02 intake)

| Old term | New canonical term | Source |
|---|---|---|
| Order Portal / Order Portal Manager | **Webstores** / **Webstores Manager** | EC14 |
| Wrap Command Center | **Wrap Lab** | EC15 |
| Portal Owner (Webstores context) | **Webstore Owner** | EC14 |

**Implementation note:** these are naming corrections registered for future implementation. No file, route, model, or UI label has been renamed as part of this documentation-only intake (no code was touched). Renaming existing code is deferred to the checkpoint that owns each surface (EC14 for Webstores, EC15 for Wrap Lab), per EC14's own "temporary compatibility naming" allowance.

**Register last updated:** 2026-02 — SignGuy AI Checkpoint Specification Pack intake; contradictions C1/C2/C3 resolved by explicit owner decision (see `owner_specification_hold_register.md`).
