# SignGuy AI — Revised Commercial Source of Truth (REVISED-2026-07)

**Revision:** REVISED-2026-07 (July 2026 owner-approved revision).
**Authority:** master plan Appendix A.4 (`/app/SIGNGUY_AI_FINAL_CONSOLIDATED_MASTER_BUILD_PLAN.md`).
**Origin document:** `SignGuy_AI_Final_Recommended_Pricing_Fees_Onboarding_Annual_Trials_REVISED.docx` (owner-uploaded artifact, 47.8 KB, 2026-07 revision).
**Scope:** commercial pricing, transaction fees, onboarding, annual billing, trials, AI credits — the durable commercial source of truth for Stripe product setup, sales pages, onboarding offers, internal fee logic, and future pricing decisions.

**Delivery ownership (LOCKED):**
- **EC11 — AI Credits and Usage Ledger** owns the ledger, cost tracking, monthly resets, purchased-credit retention, configurable plan-aware launch guardrails, low-credit warnings, zero-balance blocking, provisional credit packs, cost-audit gate.
- **EC12 — Onboarding, Documentation, Help, and Governance UX** owns the guided onboarding wizard product experience, documentation registry, Help Center, documentation-grounded AI Help, support escalation, failed-subscription warning + restriction UX. May display subscription state but does NOT own billing truth.
- **EC13 — Commercial Billing and Marketing** owns Founder eligibility, subscription pricing, trials + paid extended trial + $20 conversion credit, setup products + add-ons + waivers, checkout, receipts, annual billing, platform fees, Stripe products / prices / coupons, entitlements, grace periods, continuous-active Founder enforcement, public pricing page, marketing website, signup + conversion flows.

**Implementation rule (LOCKED):** none of this document is built inside EC7. It is scheduled to EC11 / EC12 / EC13.

---

## 1. Founder Edition (active)

| Field | Value |
|---|---|
| Availability | First 25 signed shops. Closes when the 25 slots fill. |
| Monthly path | $119/month for months 1–3, then $189/month while continuously active |
| Annual path | $1,890/year upfront (replaces the 3-month monthly promotion) |
| Included software | Core SignGuy AI OS + Webstores + Wrap Command Center + Customer Portal + documents + approvals + production + pricing + invoicing + payments + platform improvements |
| Included AI credits | 1,000/month (provisional; subject to provider-cost audit) |
| Platform-fee holiday | 0% regular Payment + 0% Webstore platform fee — first 3 paid months (Stripe processing still applies) |
| Locked fee schedule (month 4+) | 0.5% regular Payment / 1.5% Webstore while continuously active |
| Founder Kickstart Setup | $299 one-time required unless a specifically approved waiver |
| Founder lock | Founder pricing remains locked only while the account stays continuously active |
| Implementation | Stripe promotion / coupon for the $119 intro period. Never create a permanent Founder product SKU. EC13 owns backend enforcement. |

## 2. General Availability (active)

| Product | Monthly | Annual | Included monthly AI credits |
|---|---|---|---|
| SignGuy AI OS — Core | $149 | $1,490 | 300 |
| Webstores Add-On | $89 | $890 | 300 |
| Wrap Command Center Add-On | $119 | $1,190 | 500 |
| **Complete Bundle** | **$279** | **$2,790** | **1,100** |
| Webstores Standalone | $89 | $890 | 300 |
| Wrap Command Center Standalone | $119 | $1,190 | 500 — **only after standalone readiness is verified** |

Standalone-readiness verification is a prerequisite before Wrap Command Center Standalone may be sold publicly. If later analysis shows standalone products need higher pricing than add-ons, that requires a **separate owner decision** — not a documentation-cleanup change.

## 3. Platform Transaction Fees (active)

Fees are backend-calculated, snapshotted per transaction, plan-aware, tenant-scoped, and auditable. Fee display must be clear before checkout / payout where legally appropriate. Frontend must never set or alter fee rates.

| Account status | Regular Payment platform fee | Webstore platform fee |
|---|---|---|
| Founder months 1–3 | 0% | 0% |
| Founder month 4+ | 0.5% | 1.5% |
| General Availability | 1.0% | 2.0% |
| Custom / enterprise | negotiated after real volume | negotiated after real volume |

Refunds and partial refunds require a documented proportional-fee policy. Fees stay separate from Stripe processing, tax, supplier charges, shipping, and customer-facing line items.

## 4. AI Credits & Credit Packs (active)

Provisional launch prices — subject to provider-cost audit before final lock.

| Pack | Credits | Launch price | Expiration |
|---|---|---|---|
| Quick Fix | 100 | $19 | No expiration while subscription remains active |
| Growth Boost | 300 | $45 | No expiration while subscription remains active |
| Power Pack | 800 | $99 | No expiration while subscription remains active |

- Included monthly credits reset each billing cycle (no rollover).
- Top-up (purchased) credits are consumed only after included credits and remain available while the paid account remains active.

### 4.1 Launch guardrails — PROVISIONAL CONFIGURABLE LAUNCH GUARDRAILS — SUBJECT TO PROVIDER-COST AND USAGE REVIEW

- 20 image generations / tenant / day (starting value)
- 50 AI assistant messages / tenant / day (starting value)
- 3 historical invoice analyses / tenant / day (starting value)
- Low-credit warning at 20% remaining
- Block paid AI actions at 0 credits

**EC11 MUST implement these as configurable, plan-aware controls — not hardcoded permanent limits.**

Log provider + model + tokens/units + estimated cost + feature + tenant + outcome for every billable AI action. Cost allotments (Founder + GA) reviewed after 10–20 active paying shops; never retroactively reduce an active Founder promise.

## 5. Onboarding & Setup (active)

**Split ownership (LOCKED):**
- **EC12 owns the guided onboarding product experience** — Quick Setup, Advanced Setup, mini quizzes, setup checklist, progress tracking, setup readiness, contextual explanations, help articles, Settings mapping, save-and-continue-later, staff-assisted setup workflow, onboarding support checklist, documentation + AI Help Center integration.
- **EC13 owns the paid setup purchase + billing** — setup-package products, discounts/waivers, checkout, payment status, receipts, service entitlement / purchase records, billing + refund behavior.
- Onboarding wizard MUST work for DIY customers without requiring a paid package. Paid setup purchases MUST NOT create a parallel onboarding system.

| Package | Price | Availability |
|---|---|---|
| DIY Guided Setup | $0 | all plans |
| Founder Kickstart Setup | $299 one-time | first 25 Founder shops (rare waiver for case-study shops) |
| Standard Shop Setup | $499 one-time | General Availability bundle |
| Full Optimization Setup | $999 one-time | deeper configuration |
| White-Glove Implementation | $1,999+ (quoted) | larger shops / messy data / multiple locations |

Setup add-ons (locked): Additional Webstore Setup Basic $199; Advanced $399; Large Catalog Build $699+; Wrap Command Center Setup $299; Historical Invoice/Pricing Import Review $399 / $799 extended; Data Import Cleanup $150/hr; Extra Training $150/hr or $249/2hr; Custom Template Build $75 each or $299/5.

Boundaries: setup fees are **separate** from subscription + AI credits + Stripe processing + platform fees. Every package requires a written checklist and a documented completion point. Setup fees collected at signup or before first assisted session.

## 6. Annual Billing (active)

- "Pay 10, get 12" annual discount.
- AI credits still reset **monthly** even on annual plans — do not grant a full year upfront.
- Annual plans keep the same platform-fee schedule as the matching monthly plan.
- Auto-renew at the same approved annual rate unless cancelled before renewal.
- Founder annual pricing remains available only while the account stays continuously active.

## 7. Free & Paid Extended Trial (active)

| Trial | Price | Length | Credits | Rule |
|---|---|---|---|---|
| Free Trial | $0 | 48h — begins on verified activation / explicit trial start | 25 AI credits | Limited access, sample data, checklist. No custom setup work. |
| Extended Trial | $20 | 7 days | 75 total credits | Apply the $20 credit toward first paid subscription if purchased within 14 days after trial expiration. |

Controls: one trial per business / owner / verified domain unless manually approved; live card / SMS / regulated integrations may stay disabled until verification; countdown + expiration + export + conversion behavior explicit.

## 8. Failed Subscription & Access State (active)

| Period since last-good payment | Access |
|---|---|
| Days 1–7 | Normal access with prominent billing warnings and retry notices. |
| Days 8–14 | Soft restrictions on add-ons and new AI usage. Core data remains accessible. |
| After day 14 | Paid modules blocked. Customer data preserved. Billing + export + support + account-recovery remain available. Never auto-delete tenant data because a subscription failed. Never block billing / export / support / privacy / data-deletion tools. Reactivation restores entitlements idempotently. Founder pricing is not guaranteed after cancellation or unresolved lapse beyond the approved grace period. |

Owned by EC13 (billing truth). EC12 owns the **warning + restriction UX**; it does not own the underlying enforcement.

## 9. Continuously Active Founder Enforcement — architecture reservation

Permanent tenant / subscription commercial-state fields owned by EC13. Documented here so their names and semantics remain stable across checkpoints. **Do NOT add these to the production database in EC7:**

- `founder_status`
- `founder_slot_number`
- `founder_activated_at`
- `founder_intro_started_at`
- `founder_intro_ends_at`
- `founder_locked_monthly_price_cents`
- `founder_locked_annual_price_cents`
- `founder_continuously_active`
- `founder_lost_at`
- `founder_loss_reason`
- `subscription_current_period_end`
- `subscription_grace_period_ends_at`
- `commercial_terms_version`

EC13 must implement: backend enforcement, Founder slot allocation, continuous-active evaluation, grace-period handling, Founder loss rules, audit history, historical terms snapshotting, Stripe subscription mapping. This is **not** an EC1 startup guard — it is commercial state and belongs to EC13.

## 10. Rollout Discipline

- **Phase 1 (Founder):** sell only the complete Founder Edition to the first 25 shops.
- **Phase 2 (Review):** after 10–20 active paying shops, review adoption + AI cost + support burden + payment volume + churn + Webstore demand.
- **Phase 3 (GA):** open GA using the $279 bundle + approved Core / add-on / verified standalone prices.
- Never change active Founder pricing. Updated pricing applies only to new customers after Founder availability closes.

## 11. Source-of-Truth Rule

Any subsequent commercial-numbers document must supersede this one **explicitly** with a new revision date. Older conflicting commercial numbers are superseded by REVISED-2026-07 until a new owner-approved revision replaces it. Marketing copy, Stripe product map, entitlement rules, onboarding packages, and billing tests must always match this document.
