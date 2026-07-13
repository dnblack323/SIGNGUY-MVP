# SignGuy AI — Permanent Backlog Register

**Purpose:** The committed, permanent-scope backlog — work that IS on the roadmap (unlike `/app/memory/product_ideas_register.md`, which is explicitly NOT-yet-committed ideas). Created 2026-02 during the SignGuy AI Checkpoint Specification Pack intake. Reconciles the old master plan's Appendix A permanent-scope addenda and the P1/P2 backlog previously tracked ad hoc in `PRD.md` into the new EC9–EC22 sequence.

**Rule (carried forward from old master plan):** nothing below may be silently absorbed into another checkpoint, silently dropped, or treated as an "implied capability." Each item is owned by exactly one checkpoint in `/app/memory/checkpoint_reference_table.md`.

## P0 — Immediate (blocked on owner authorization, hold H1)

- Nothing is "next" until the owner names a specific checkpoint to start. Per explicit owner instruction, this documentation intake does not auto-start EC9.

## P1 — Next in sequence once authorized (per new EC9–EC22 order)

| Item | Owning checkpoint | Carries forward from |
|---|---|---|
| Pricing Foundation full calculator category coverage, canonical formula pipeline, manual/saved/AI pricing-mode coexistence, review/testing panel | EC9 | Old Appendix A.2 (EC3.1) |
| Order Intake capture (camera/image/PDF/measurements/voice notes/questionnaires), Visual Markup tools, Customer Decision Room, reusable Templates (Quote/Order/Intake/Questionnaire/Proof/Email/SMS/Document/Production/Appointment) | EC10 | Old Appendix A.1 (EC6.3) + new Customer Decision Room (first-time authority, previously missing) |
| Order Timeline panel, configurable Production Stages (Simple/Detailed/Custom), Employee Production Experience, Shop-Floor Kiosk | EC11 | New scope; Advanced stage-timer/bottleneck-analytics half remains the pre-existing owner-locked paid add-on (`/app/docs/production_stage_timer_boundary.md`) |
| Shared Task system, Employee Scheduling/Time-Off, Messages/Announcements/Daily Digest, Calendar/Appointments/Shop Schedule, Employee Account Experience, Community + Founders Area, Templates | EC12 | New scope (Community/Founders area is new; Team messaging/scheduling extends EC8) |
| Commercial billing engine: Founder + GA plans, platform fees, credit packs, setup packages, trials, entitlements, dunning | EC13 | Old Appendix A.4 / `REVISED_COMMERCIAL_SOURCE_OF_TRUTH_2026-07.md` — contradictions C1 (standalone pricing) and C2 (dunning model) now **RESOLVED 2026-02** by owner decision; see `/app/memory/owner_specification_hold_register.md` |

## P2 — Add-ons requiring separate owner authorization (holds H2/H3)

| Item | Owning checkpoint | Hold |
|---|---|---|
| Webstores Manager (9 release gates: Foundation Lock → Setup MVP → Questionnaire/Owner Portal → AI-Assisted Product Builder → Artwork/Mockups/Launch Packet → Public Storefront/Buyer Orders → Stripe Connect/Fees/Payouts/Ledger → Reporting/Launch Hardening → Main-App Integration) | EC14 | H2 — separate owner authorization required |
| Wrap Lab (full workflow: lead/intake → vehicle/customer → coverage/measurement → estimate/quote → contract/deposit → pre-install inspection → design/proof → panel planning → production/install scheduling → installation → completion packet → warranty/aftercare → history/reporting; vector design engine; packet-layout preservation) | EC15 | H3 — separate owner authorization required; H6 — standalone activation additionally requires its own preflight |

## P2 — AI systems requiring separate owner authorization (hold H4) and the EC17 tool-review block (holds H5/H8)

| Item | Owning checkpoint | Hold |
|---|---|---|
| Shared AI Gateway: provider/model router, capability registry, prompt/version registry, context/action services, usage + provider-cost + credit ledgers, generation history, rate limits/budget alerts, entitlement checks | EC16 | H4 |
| Studio AI Tools consolidation (28+ legacy tools → families), Prompt Library, Generated Assets, AI Activity | EC17 | H4 + **H5/H8 blocking** — owner must complete the Keep/Combine/Change/Rename/Defer/Remove worksheet (with Final Name + Family per tool) before any implementation prompt is issued. AI-tier-pricing question (C3) is **RESOLVED 2026-02** — no separate AI subscription tiers; plan-included credits + existing top-up packs only. |
| Paid Business Assistant: conversational business intelligence, structured actions with preview/confirm, Realtime Voice (WebRTC, VAD, push-to-talk) | EC18 | H4 |

## P2 — Platform/commercial-surround (no product-specific hold beyond H1)

| Item | Owning checkpoint |
|---|---|
| Onboarding checklist/dashboard, Help Center, contextual help, app documentation, pricing-quiz onboarding flow | EC19 |
| Platform Admin cockpit: tenant oversight, impersonation (read-only "View As"), suspension, maintenance mode, dunning execution, broadcast email, analytics (AI cost/feature usage) | EC20 |
| Marketing website, public pricing page (single-source-of-truth manifest, no duplicated pricing constants), Founder-offer slot counter, 8-step signup flow | EC21 |

## P3 — Final gate (closes only after all of the above are COMPLETE)

| Item | Owning checkpoint |
|---|---|
| Cross-module journey verification (Sales/Revenue, Webstore, Wrap Lab, AI Integration, Workforce/Management), security/data/infra/experience/ops/financial hardening, release-blocker sweep | EC22 |

## Pre-existing permanent backlog items unaffected by this intake

- **EC6.2 — Signed PDF Composite Rendering** (deferred per `/app/memory/product_ideas_register.md`) — still deferred to EC22 Final Hardening or an earlier verified need; unaffected by the new pack.
- **Reusable Quote/Order Templates** and **Production Board Live Refresh** ideas in `product_ideas_register.md` remain unscheduled ideas, not part of this committed backlog, unless the owner promotes them.

**Register last updated:** 2026-02 — SignGuy AI Checkpoint Specification Pack intake; contradictions C1/C2/C3 resolved by owner decision (see `owner_specification_hold_register.md`). No item above has started implementation.
