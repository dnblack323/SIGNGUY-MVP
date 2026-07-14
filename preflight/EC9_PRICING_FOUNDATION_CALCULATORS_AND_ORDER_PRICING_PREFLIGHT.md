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

---

## 17. Phase 9B — Global Pricing Foundation (COMPLETE, 2026-02)

**Scope delivered:** shop-level (tenant-wide) Pricing Foundation settings only — Shop Rate/labor rates, labor burden, overhead, target margin, markup, design/install rates, minimum charges, setup/rush/waste defaults (fallback slots), source labels, manual-override coexistence, effective-date/versioning. Category-specific calculator formulas remain Phase 9E (not started). The grouped onboarding quiz remains Phase 9C (not started — no quiz code was written; only the shop-level data fields it will eventually suggest values for now exist).

**Settings/models changed:** `app/services/starter_defaults.py` (`SHOP_DEFAULTS`, `STARTER_DEFAULT_VERSION` bumped to `1.1.0`), `app/routers/pricing.py` (`ShopDefaultsIn` extended with 12 new optional fields), `app/services/pricing.py` (`calculate_pricing()` now returns `shop_defaults_used`), `app/services/pricing_snapshot.py` (`build_calculated_snapshot` now returns `defaults_snapshot` + `foundation_effective_at`; source taxonomy formally documented), `app/routers/quotes.py` / `app/routers/orders.py` (manual line-item creation now tags `source="user_entered"`), `app/routers/inventory.py` (added a `POST /materials/{id}/restore` endpoint — a small, necessary EC7 gap-fill required to make Phase 9A invariant 5 enforceable/testable; mirrors the existing `archive` endpoint exactly), `app/services/pricing_materials.py` / `app/services/pricing_saved_items.py` (reject archived materials for new profile/saved-item-ref creation), `app/frontend/src/pages/PricingFoundationPage.jsx` (`SHOP_FIELDS` extended to 18 fields).

**Defaults added (EC09-exact, per the controlling document):** `design_hourly_rate` 97→**85**, `install_hourly_rate` 75→**95**, `default_overhead_percent` 19→**15**; new `removal_hourly_rate` **65**, `travel_hourly_rate` **45**, `admin_hourly_rate` **35**, `consultation_hourly_rate` **110**, `site_survey_hourly_rate` **95**, `finishing_hourly_rate` **28**. `production_hourly_rate` (28), `target_profit_margin_percent` (40), `default_markup_multiplier` (2.5) were already correct and unchanged. Fields with no explicit global number in the EC09 document (`install_minimum_charge`, `setup_fee_default`, `labor_burden_percent`) were added as tenant-editable fallback slots seeded at 0 — not invented values, explicitly flagged, editable.

**Formulas added:** none new (Phase 9E territory) — `calculate_pricing()`'s pipeline is unchanged in shape, only its shop-level rate inputs changed value and it now echoes back the exact values it used (`shop_defaults_used`) for downstream snapshotting.

**Versioning/effective-date behavior:** `defaults_snapshot` captures the actual shop-level rate/percentage values in effect at calculation time (not just a version string), and `foundation_effective_at` records the tenant's `pricing_settings.updated_at` timestamp at that moment. This guarantees a historical snapshot's math remains fully explainable and immutable even after a shop later edits its Pricing Foundation — proven by `test_defaults_snapshot_immutable_after_shop_defaults_change`.

**Frontend behavior:** `PricingFoundationPage.jsx` Shop Defaults grid now exposes all 18 fields for direct edit/save (verified end-to-end by the testing agent: edit → save → reload → persisted). The 9 category cards are unaffected.

**Backend-authoritative calculation behavior:** unchanged and reconfirmed — `calculate_pricing()` remains the single, backend-only source of truth; frontend never computes a price itself.

**Phase 9A invariant verification (all 10, per owner request):**
1. Unique `(tenant_id, material_id)` — enforced by service check + Mongo unique index. ✅ (re-verified at DB layer in `test_invariant_1_and_3_...`)
2. Cross-tenant Material reference rejected — ✅ (`test_tenant_isolation_on_material_profile`, Phase 9A)
3. Duplicate create cannot produce >1 active profile — ✅ (service 400 + DB-level `DuplicateKeyError` + count==1 assertion)
4. Archiving a Material preserves historical snapshots — ✅ (`test_invariant_4_...`, new)
5. Archived Materials rejected for new selection, restorable — ✅ (`test_invariant_5_...`, new — required adding a small `POST /materials/{id}/restore` endpoint, noted above)
6. Deactivating a SavedItem/Component doesn't touch other collections — ✅ (`test_invariant_6_...`, new)
7. `material_refs` validated as canonical tenant-owned — ✅ (`test_foreign_material_ref_rejected`, Phase 9A)
8. `save_as_variation()` never mutates source — ✅ (`test_save_as_variation_does_not_mutate_source`, Phase 9A)
9. Tenant scope/timestamps/status on all new records — ✅ (`test_invariant_9_...`, new)
10. No pricing profile is a second inventory record — ✅ (`test_invariant_10_...`, new)

**Phase 9B targeted test results:** `tests/test_ec9_phase9b_global_foundation.py` (5 tests) + `tests/test_ec9_phase9a_invariants.py` (6 tests) — **11/11 passing.**

**Regression checked (targeted, not full suite):** `test_ec9_material_pricing_profiles.py`, `test_ec9_pricing_components.py`, `test_ec9_pricing_saved_items.py`, `test_pricing_snapshot.py`, `test_quotes_ec3.py`, `test_orders_ec3.py`, `test_money_policy.py`, `test_terminology_guard.py`, `test_ec7_inventory.py` — **64/64 passing, zero regressions.**

**Frontend verification:** delegated to `testing_agent_v4` (main agent's own Playwright screenshot attempts were disrupted by a transient dev-server recompile loop this session). Result: **100% pass** — Shop Defaults render/edit/save/persist correctly with all 18 fields, 9 category cards unaffected, Pricing Calculator smoke calculation still works, general app navigation stable, zero console errors, zero bugs found. See `/app/test_reports/iteration_17.json`.

**Phase 9B status: COMPLETE.**

**Remaining Phase 9C work (NOT started):** the simplified, grouped onboarding pricing quiz — one practical-scenario question deriving labor rate/minimum/overhead/sell-rate suggestions, shown-math + owner-review-before-apply, additive to (not replacing) the existing detailed `CategorySetupWizard`. No quiz code, service, or endpoint exists yet.


---

## EC9 CLOSURE RECORD — Phase 9H (2026-07)

**EC9 status: COMPLETE / CLOSED.** All phases delivered: 9A (invariants) → 9B (global foundation) → 9C (grouped quiz) → 9D (Materials/Saved Items) → 9E-1..9E-4 (all 9 category calculators) → 9F (Quote/Order/Order Item integration) → 9G (immutable snapshots + advisory contracts) → 9H (this closure pass).

**Phase 9H findings:** `testing_agent_v4` (first and only run for the whole EC9 checkpoint) found **1 critical defect**: Quote Line Item / Order Item pricing resolution (`routers/quotes.py`, `routers/orders.py` — `_resolve_item_pricing`) never forwarded `width_inches`/`height_inches` into `order_pricing.calculate_for_references()`, causing flat/square-foot categories (banners, rigid_signs, cut_vinyl, digital_print) to silently price off the category's minimum billable area rather than the actual entered dimensions whenever an item was created/edited/recalculated through a Quote or Order (the standalone `/pricing/calculate` endpoint used by the Calculator page was unaffected — it always forwarded dimensions correctly). **Fixed** in both routers (dimensions now flow through create/update/recalculate-preview; `pricing_trigger_fields` now includes `width_inches`/`height_inches` so a dimensions-only edit also triggers recalculation) and locked in with 5 new regression tests (`tests/test_ec9_phase9h_closure_regressions.py`).

**Dead-code finding:** `components/pricing/selectors/MaterialSelector.jsx` (a raw canonical-Material selector prepared in Phase 9D, zero usages anywhere in the frontend — superseded by the profile-based `MaterialProfileSelector.jsx` built in Phase 9F/9G) — **removed**.

**Final test totals:** 196 EC9-targeted pytest (all phases together) + 5 Phase 9H closure regression tests + 511 full backend regression (2 pre-existing unrelated collection-only issues in `test_ec8_api_spotcheck.py`/`test_live_foundation_hardening.py` confirmed to pass fully when `REACT_APP_BACKEND_URL` is exported — a test-harness quirk, not an EC9 or application defect) + 25/25 frontend Jest + frontend production build (`yarn build`, clean) + terminology guard (`OK`) — all green. `testing_agent_v4` closure workflow pass: 1 defect found and fixed as above, zero other defects.

**Full closure report + category coverage matrix + provisional assumption register:** see the "EC9 Phase 9H — Closure" section of `/app/memory/PRD.md` (this preflight doc is kept as historical evidence only and is not re-authored).

**EC10 and all later checkpoints: NOT STARTED.**
