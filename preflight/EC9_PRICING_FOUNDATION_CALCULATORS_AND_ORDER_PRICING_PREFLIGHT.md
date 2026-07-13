# EC9 Preflight — Pricing Foundation, Calculators, and Order Pricing

**Status:** PREFLIGHT ONLY — NO CODE WRITTEN. Controlling spec: `/app/specs_pack/extracted/EC09_Pricing_Foundation_Calculators_and_Order_Pricing.docx`.
**Date:** 2026-02. **Authorization:** preflight only, per explicit owner instruction. EC9 coding requires a further explicit approval.

---

## 1. Existing baseline inventory (files inspected)

**Backend**
- `app/services/pricing.py` — `pricing_settings` CRUD (shop defaults, category defaults), `calculate_pricing()` (the one and only calculation pipeline), `wizard_suggestions()` (banners has bespoke logic; all other 8 categories use a generic passthrough).
- `app/routers/pricing.py` — `/pricing/settings`, `/pricing/settings/shop-defaults`, `/pricing/settings/categories/{id}` (+reset, +wizard/suggestions, +wizard/apply), `/pricing/calculate`. Permissions: `pricing:read`, `pricing:write`, `pricing:calculate` (`app/core/permissions.py` lines 84-86).
- `app/services/starter_defaults.py` — single source of truth for the starter pack: `SHOP_DEFAULTS` (8 fields), `MATERIALS` (20 materials, embedded dict, cost/sell per sqft only), `CATEGORY_DEFAULTS` (9 categories: banners, rigid_signs, cut_vinyl, digital_print, vehicle_graphics, apparel, services, promotional, custom).
- `app/services/pricing_snapshot.py` — `build_manual_snapshot`, `build_calculated_snapshot`, `apply_override`. Snapshot stored on the line item's `pricing_snapshot` dict field. `source` field exists but only has two values today: `"manual"` / `"calculator"`.
- `app/models/quote_line_item.py`, `app/models/order.py` — both carry `pricing_snapshot: dict[str, Any]`, wired in `routers/quotes.py` and `routers/orders.py` via `build_manual_snapshot`.
- `app/models/material.py` — the **EC7 physical-inventory** `Material` model (distinct system; already has a dormant `pricing_material_id: Optional[str]` field reserved for future pricing integration, never wired up).
- `backend/tests/test_pricing_snapshot.py` — 3 unit tests, snapshot builders only. **No test file exercises `calculate_pricing()` itself, no per-category expected-value tests exist today.**

**Frontend**
- `pages/PricingFoundationPage.jsx` — shop-defaults form + one card per category (status badge, setup/reset buttons) + `CategorySetupWizard` modal.
- `pages/PricingCalculatorPage.jsx` — single-item calculator form + result/breakdown card. Material dropdown reads `settings.materials` filtered by category.
- `components/pricing/CategorySetupWizard.jsx` + `wizardConfigs.js` — one wizard config entry exists per category (9/9), but only banners has category-specific questions; the rest are effectively generic.

## 2. What is already COMPLETE

- One canonical, backend-authoritative calculation pipeline (no parallel pricing engine exists) — `calculate_pricing()`.
- Tenant-scoped, auto-cloned starter pack; editing the starter template never retroactively touches an existing tenant (`get_or_init_pricing_settings` clones once, per-tenant `pricing_settings` doc thereafter).
- Manual override coexists with the calculator (`manual_selling_price` param, `method_used="manual_override"`).
- Immutable historical pricing snapshots on Quote line items and Orders, captured at commit time, never re-priced when shop defaults later change (verified by reading the write paths — nothing touches an existing `pricing_snapshot` after creation except the explicit, audited `apply_override`).
- Integer-cents boundary is correctly placed: calculator internals + settings are float/Decimal dollars; `pricing_snapshot.py` converts to cents exactly once (`dollars_to_cents`) when freezing the snapshot.
- Quote + Order Item integration exists end-to-end (routers already call the snapshot builders).
- 9/9 categories have a starter default entry and a `pricing_settings` UI card; all 9 route through the same `calculate_pricing()` function (no category has its own bespoke code path).

## 3. What is PARTIAL

- **Category-specific formulas:** only a generic per-sqft / cost-plus-labor / common-job-prices split exists. EC09's richer per-category rules (perimeter-based banner finishing + event multipliers, cut-vinyl color-count/surface complexity, rigid-sign substrate/finish multipliers, vehicle-wrap coverage-tier + benchmark packages + prep/removal + multi-installer, services rate-cards, apparel multi-method hooks) are **not** implemented — today apparel and vehicle_graphics get light bespoke branches inside `calculate_pricing()`, everything else is the generic per-sqft/cost-plus fallback.
- **Wizard suggestions:** banners has real suggestion logic; the other 8 categories fall back to a generic passthrough (`_generic_wizard_suggestions`) that just echoes answers back — not a derived-defaults quiz.
- **Quantity/rush multipliers:** `quantity_tiers` field exists in the schema (used for apparel discount display) but is not applied inside `calculate_pricing()`'s selling-price math; `rush_fee_percent` exists in `SHOP_DEFAULTS` but is never read by `calculate_pricing()`.
- **Source labeling:** the `pricing_snapshot.source` field only distinguishes `manual` vs `calculator` — the 6-value taxonomy required by EC09/Part 4 item 24 (shop default / saved item / AI estimate / historical data / market data / user entered) does not exist.

## 4. What is MISSING entirely

- **Materials Library as a first-class, tenant-editable library.** Today `materials` is a fixed embedded dict inside `pricing_settings`, seeded once from `starter_defaults.MATERIALS`, with no create/update/delete endpoint — tenants cannot add their own material today.
- **Hardware & Accessories catalog** — no model, no collection, no UI.
- **Labor & Service Rates beyond the 3 shop-level roles** (design/production/install) — no role-based rate table for e.g. weeding, lamination, mounting, embroidery digitizing.
- **Saved / Common Item Pricing** — no dedicated reusable-product library; only an unstructured `common_job_prices` dict per category (freeform, not query-able, not reusable across categories).
- **Promotional Items "commonly sold" list** — `promotional` category exists as a generic cost-plus-labor category only; no starter tier-pricing (business cards/magnets) as described in EC09 §4.
- **AI Estimation Rules / AI Price Analysis / Historical Invoice Analysis / Market Research comparison** — none exist. (See Risk R1 below — this is a deliberate boundary, not an oversight.)
- **Review/Testing Panel** — no dedicated admin sandbox UI; `/pricing/calculate` is already side-effect-free (no persistence) so the underlying capability exists, just not framed as a panel.
- **Grouped, simplified onboarding pricing quiz** (one practical-scenario question deriving several defaults at once, per the Master Index's locked decision and EC09/EC19) — does not exist. The existing `CategorySetupWizard` is a *different, more detailed* per-category wizard, not this.
- **Order-level vs. Order-Item-level pricing *view*** with explicit source labels — Order/Quote detail pages render the line item price but do not surface `pricing_snapshot.source`, cost breakdown, or a labeled provenance to staff today (needs confirming at implementation time; not deep-inventoried here to conserve credits).
- **No calculator/category pytest coverage** with known expected values (per Part 4 item 30 requirement).

## 5. Proposed EC9 architecture (extends existing, no second engine)

- **Keep `calculate_pricing()` as the single pipeline** (Area → Material → Labor/Design/Install → Overhead → Sell = max(cost-plus, sell-rate, minimum) → qty-discount/rush). Extend it with category-specific branches (mirrors the existing apparel/vehicle_graphics special-case pattern already in the file) rather than a new function per category.
- **Promote `materials` from an embedded dict to a real tenant-scoped collection** (`pricing_materials`), following Decision 3 (repository class for new modules): `PricingMaterial` model with `tenant_id`, `key`, `name`, `category`, `cost_per_sqft`, `sell_per_sqft`, `is_starter` (seeded vs. user-created), `linked_inventory_material_id: Optional[str]` (optional forward-looking link to EC7's `Material.pricing_material_id` — no EC7 changes, no reopening EC7). `pricing_settings.materials` becomes a read-through cache or is deprecated in favor of the new collection — exact migration approach decided at implementation time, but starter-pack cloning behavior (never retroactive) is preserved.
- **New `pricing_hardware_accessories` collection**, same shape/pattern as materials.
- **New `pricing_saved_items` collection** — reusable Saved/Common Items (covers both "Saved/Common Item Pricing" and the Promotional "commonly sold" list): `tenant_id`, `name`, `category`, `frozen_price_cents` or `recalculate_on_apply: bool`, `source_calculator_snapshot`. Applying a saved item to a Quote/Order Item reuses the existing `build_manual_snapshot`/`build_calculated_snapshot` path — no new snapshot mechanism.
- **Formalize the `source` taxonomy** in `pricing_snapshot.py` as an enum: `shop_default | saved_item | ai_estimate | historical_data | market_data | user_entered | manual | calculator` (additive to the existing 2 values — old snapshots remain valid, no backfill).
- **New simplified onboarding quiz service** (`pricing_quiz.py`) — one grouped practical-scenario question (job type, size, material, design/production/install time, what-you-charge) → derives labor rate, minimum charge, overhead recovery, sell rate as a single review-and-approve screen. Explicitly additive to, not a replacement for, the existing per-category `CategorySetupWizard`, per the Master Index's locked instruction that "advanced or specialist pricing tools remain available in a dedicated pricing area."
- **AI/market-research/historical-invoice pieces are built as scaffolding only in EC9**: data-model fields (`ai_estimate_status`, `source="ai_estimate"`/`"market_data"`/`"historical_data"`, review-card shape) and a manual-entry-only "advisory" UI, with **no live LLM/provider call** — that is EC16's job (Shared AI Gateway, currently held on H4) and is explicitly forbidden earlier by the locked Never-Again rule "No AI before credit metering + cost controls." See Risk R1.
- **Review/Testing Panel** = a frontend-only sandbox framing of the existing stateless `/pricing/calculate` endpoint (optionally tag sandbox calls with a `is_sandbox: true` flag so they're excluded from any future usage analytics — minor, non-breaking).

## 6. Exact implementation phases (proposed — for approval, not started)

1. **Materials Library + Hardware/Accessories** — new collections/models/repositories/routers, migrate calculator to read from them, tenant-CRUD UI panel, backfill starter pack into the new collection on first tenant access (same clone-once pattern as today).
2. **Category-specific formula depth** — implement the EC09 §4 formulas category-by-category (Promotional commonly-sold list + starter tiers; Digital Print sqft+multipliers+1.0 sqft minimum; Cut Vinyl tier/color-count/complexity; Rigid Signs substrate/finish multipliers; Banners perimeter finishing + event multipliers; Vehicle Wraps coverage tiers + benchmark packages + prep/removal + multi-installer; Services billing-unit rate-cards; Apparel generic multi-method hook), plus quantity-discount and rush-multiplier application inside `calculate_pricing()`.
3. **Saved/Common Item Pricing** — new collection, CRUD UI, "apply to Quote/Order Item" action reusing existing snapshot builders.
4. **Source-label taxonomy + snapshot formalization** — enum, `build_calculated_snapshot`/`build_manual_snapshot` updates (additive only), Order/Quote-detail-page provenance badges (Order-level + Order-Item-level views).
5. **Simplified grouped onboarding pricing quiz** — new service + endpoint + UI, additive to the existing detailed wizard.
6. **Review/Testing Panel UI** — sandbox framing of the existing calculate endpoint.
7. **AI/market-research/historical-invoice scaffolding** — data model + advisory review-card UI only, no live call (pending EC16).
8. **Test suite** — per-category expected-value tests, materials/saved-items CRUD + tenant-isolation tests, quiz tests, snapshot-taxonomy regression, manual-never-overwritten guard test.

## 7. Exact files expected to be created or modified

**Backend — modify:** `app/services/starter_defaults.py`, `app/services/pricing.py`, `app/services/pricing_snapshot.py`, `app/routers/pricing.py`.
**Backend — new:** `app/models/pricing_material.py`, `app/models/pricing_hardware_accessory.py`, `app/models/pricing_saved_item.py`, `app/repositories/pricing_material_repo.py` (+ hardware/saved-item repos, per Decision 3), `app/services/pricing_quiz.py`, `app/services/pricing_ai_boundary.py` (scaffolding only), `app/routers/pricing_materials.py`, `app/routers/pricing_saved_items.py`, `app/routers/pricing_quiz.py`.
**Backend — new tests:** `tests/test_ec9_pricing_categories.py`, `tests/test_ec9_pricing_materials.py`, `tests/test_ec9_pricing_saved_items.py`, `tests/test_ec9_pricing_quiz.py`.
**Frontend — modify:** `pages/PricingFoundationPage.jsx`, `pages/PricingCalculatorPage.jsx`, `components/pricing/CategorySetupWizard.jsx`, `components/pricing/wizardConfigs.js`.
**Frontend — new:** `components/pricing/MaterialsLibraryPanel.jsx`, `HardwareAccessoriesPanel.jsx`, `SavedItemsPanel.jsx`, `PricingReviewTestPanel.jsx`, `GroupedPricingQuiz.jsx`.
**Order/Quote detail pages:** exact component touch-points for the pricing-source badge are not fully inventoried in this preflight (credit conservation) — to be confirmed at implementation start.

## 8. Database / settings changes

- New collections: `pricing_materials`, `pricing_hardware_accessories`, `pricing_saved_items` — each `(tenant_id, key/id)` unique-indexed, following the existing `pricing_settings` single-doc-per-tenant pattern where applicable.
- `pricing_settings` gains: `hardware_accessories` (transitional, if not fully split out), extended `setup_quiz_metadata` for the new grouped quiz.
- No new permission enum values proposed — reuse `pricing:read` / `pricing:write` / `pricing:calculate` for all new endpoints (extends existing architecture, avoids permission-catalog sprawl).
- No changes to `Quote`, `Order`, `OrderItem`, `Invoice`, or `WorkOrder` schemas beyond the additive `pricing_snapshot.source` enum values (backward compatible; old records simply lack the new labels and must render "—"/"legacy").

## 9. Order / Order Item / Quote integration

- No change to how a line item *becomes* priced — `build_manual_snapshot`/`build_calculated_snapshot` remain the only two snapshot constructors, called from the existing `routers/quotes.py` and `routers/orders.py` call sites.
- Order-level and Order-Item-level pricing *views* are additive UI surfaces reading the existing `pricing_snapshot` (plus the new `source` taxonomy) — no new Order/Quote backend fields.

## 10. Historical snapshot rules

- Confirmed already correct and must be preserved exactly: a `pricing_snapshot` is written once at commit time and never mutated except through the existing, audited `apply_override` path (adds an override on top, never deletes the original calculated value). Changing `pricing_settings` (shop defaults, category defaults, starter pack version) must never alter any existing `pricing_snapshot`. All EC9 additions to the snapshot shape are additive-only with safe defaults for pre-EC9 records.

## 11. AI and market-research boundaries

- AI may only **fill missing fields**, never overwrite a user-entered or manually-overridden value (enforced today already for manual overrides via `manual_selling_price`/`override_unit_price_cents`; EC9 extends the same rule to any future AI-suggested field).
- Market research and historical-invoice analysis are advisory only, must be source-labeled (`market_data`/`historical_data`), and require explicit human review/approval before becoming a default (mirrors the existing wizard `apply=True`/`confidence` pattern already used for suggestions).
- **No live AI/LLM/provider call is made inside EC9.** This is a hard boundary driven by the locked Never-Again rule ("no AI before credit metering + cost controls") and hold H4 (EC16 Shared AI Gateway not yet authorized). EC9 ships the data model + advisory UI shape only.

## 12. Targeted test plan

- Per-category `calculate_pricing()` tests with known expected values for all 9 categories (~25-35 cases), covering the new category-specific formulas from Phase 2.
- Materials/Hardware/Saved-Items CRUD + tenant-isolation sweep (cross-tenant read/write must 404/403).
- Grouped-quiz derivation test (one scenario in → correct multi-field suggestion out, matching the EC19 example: job type/size/material/times/charge → labor rate/minimum/overhead/sell rate).
- Manual-override-never-overwritten-by-suggestion guard test.
- Snapshot-taxonomy regression: confirm a pre-EC9 (`source="calculator"`) snapshot fixture still round-trips and renders without the new fields.
- Existing `test_pricing_snapshot.py` (3 tests) re-run as regression — **not** the full 312-test suite (per credit-conservation instruction; full regression happens at EC9 close-out, not preflight).

## 13. Risks and blockers

- **R1 (boundary, not a blocker):** EC09's AI Estimation Rules / AI Price Analysis / Historical Invoice Analysis / Market Research sections cannot be fully "implemented" inside EC9 without EC16 (Shared AI Gateway, hold H4, not authorized) and without violating the locked "no AI before credit metering" rule. Resolution proposed above (scaffold-only, no live call) — flagged as an owner decision to confirm (see §17), not a hard blocker to starting EC9.
- **R2 (design decision, not a blocker):** relationship between the new `pricing_materials` collection and EC7's existing (dormant) `Material.pricing_material_id` field. Recommendation: keep them separate now with an optional forward link; do not reopen EC7. Flagged for confirmation.
- **R3 (scope-size risk):** EC09 §4's full category-by-category formula depth (especially Vehicle Wraps benchmark packages and Apparel multi-method hooks) is substantial; may warrant splitting Phase 2 into two implementation passes if the owner wants faster incremental review. Not a blocker, just a heads-up.
- **No blocker requires owner input before EC9 preflight approval** — R1/R2 are recommendations ready for a quick yes/no, not open-ended questions.

## 14. Owner decisions still needed

1. Confirm R1: EC9 ships AI/market-research/historical-invoice features as data-model + advisory-UI scaffolding only, with zero live LLM calls, until EC16 is separately authorized. (Recommended: yes.)
2. Confirm R2: new `pricing_materials`/`pricing_hardware_accessories`/`pricing_saved_items` collections stay pricing-owned and separate from EC7's Inventory `Material`, linked only by an optional field, not deeply merged. (Recommended: yes.)
3. Optional: confirm whether Phase 2 (category-formula depth) should be delivered as one pass or split into two for incremental review. (Recommended: one pass, mirrors this preflight's phase list — but splittable on request.)

## 15. Confirmations

- **No EC9 code was written.** This document is planning/preflight only.
- **No later checkpoint (EC10–EC22) was started or touched.**
- **No `.docx` specification file was modified.**
- **No full regression suite or `testing_agent` run was performed** (not applicable at preflight stage).
- **No navigation changes were made.**

---

## 16. Phase 9A — Decision Record & Completion Evidence (2026-02)

**Owner decisions received and applied (superseding this preflight's §14 recommendations where they differ):**

1. **Canonical Materials — REJECTED the independent `pricing_materials` collection recommendation.** EC7's `Material` (`app/models/material.py`) is the single canonical physical-material/inventory record for ALL physical items, including hardware/accessories (grommets, stakes, brackets, frames, mounting hardware, packaging, fasteners) that are stocked/purchased/reordered/supplier-linked/quantity-tracked. **Decision: linked one-to-one pricing profile** (not additive fields on `Material`) — implemented as `app/models/material_pricing_profile.py` (`MaterialPricingProfile`), one profile per `(tenant_id, material_id)`, referencing the canonical `Material` by id and reusing `Material`'s pre-existing (previously dormant) `pricing_material_id` field to point back at the profile. The profile never duplicates name/SKU/supplier/unit-of-measure/purchase method/quantity/inventory cost/tenant ownership/archive status — those stay exclusively on `Material`.
2. **Hardware/Accessories — REJECTED the separate `pricing_hardware_accessories` catalog.** Physical hardware/accessories use the same EC7 `Material`/Inventory/Supplier/Purchasing system as any other material (via `MaterialPricingProfile` if pricing-relevant). A **separate, non-inventory `PricingComponent` model** (`app/models/pricing_component.py`) was created strictly for commercial charges/fees that are never stocked or supplier-linked: setup fee, design fee, file cleanup, permit fee, outsourced service, pass-through/shipping, install minimum, rush charge, personalization fee, decoration fee, relaunch fee.
3. **Saved Items — APPROVED as planned**, revised to reference canonical `Material.id` via `material_refs` (never copies material/inventory data). Implemented as `app/models/pricing_saved_item.py` (`PricingSavedItem`), with `save_as_variation()` cloning without mutating the source.
4. **AI/market-research/historical-analysis boundaries — deferred to Phase 9G** per the owner's phase plan (contracts/data structures, zero live calls, hidden-until-entitled UI) — not built in Phase 9A.

**Phase 9A implementation (COMPLETE):**
- New models: `app/models/material_pricing_profile.py`, `app/models/pricing_component.py`, `app/models/pricing_saved_item.py`.
- New services: `app/services/pricing_materials.py`, `app/services/pricing_components.py`, `app/services/pricing_saved_items.py` — all tenant-scoped, all validate references against the canonical `db.materials` collection (no duplication), dollar-based fields (no `_cents` suffix — this is pricing configuration, not a transactional snapshot, per the Money Policy in `app/core/money.py`).
- New routers: `app/routers/pricing_materials.py` (`/pricing/material-profiles`), `app/routers/pricing_components.py` (`/pricing/components`), `app/routers/pricing_saved_items.py` (`/pricing/saved-items`) — registered in `server.py`, reusing the existing `pricing:read`/`pricing:write` permissions (no new permission enum values).
- New indexes in `app/core/db.py`: unique `(tenant_id, material_id)` on `material_pricing_profiles`, unique `(tenant_id, key)` on `pricing_components`, `(tenant_id, category)` + `(tenant_id, quick_select)` on `pricing_saved_items`.
- New tests: `tests/test_ec9_material_pricing_profiles.py` (4 tests), `tests/test_ec9_pricing_components.py` (3 tests), `tests/test_ec9_pricing_saved_items.py` (3 tests) — **10/10 passing.**
- Regression check (targeted, not full suite): `tests/test_pricing_snapshot.py` (3/3 passing, untouched), `tests/test_terminology_guard.py`, `tests/test_money_policy.py`, `tests/test_permissions_scope.py` (23/23 passing) — confirms tenant isolation, integer-cents boundary, and snapshot immutability behavior are all preserved.
- `Material.pricing_material_id` is now actively wired (was previously a dormant reserved field) — set automatically when a `MaterialPricingProfile` is created.

**Phase 9A status: COMPLETE.** Proceeding to Phase 9B (Global Pricing Foundation) next, per owner authorization.
