# EC9 Phase 9I - Shared Pricing Calculator Preflight and Implementation Plan

**Status:** PHASE 9I-D RE-REVIEW PASSED  
**Date:** 2026-07-26  
**Repository state audited:** `main` at `08fbe1fd1e4265df8b4047a5ca138b056cd0a82e`  
**Implementation status:** Phase 9I-A passed owner review. Phase 9I-B backend tenant pricing-method configuration foundation is implemented. Phase 9I-C backend Banner comparison contract was corrected after read-only review findings and received an independent read-only re-review with final status `PHASE 9I-C RE-REVIEW PASSED`. Phase 9I-D normalizes every currently implemented non-Banner category output through the shared method-output contract. Its read-only review found one manual-override normalization defect; that defect was corrected and received final read-only re-review status `PHASE 9I-D RE-REVIEW PASSED`. Live pricing math remains unchanged. Phase 9I-E and later remain pending and must not begin without separate owner authorization.  
**Controlling authority:** `specs_pack/extracted/EC09_Pricing_Foundation_Calculators_and_Order_Pricing.docx`

## 0. Approved Owner Decisions Recorded For 9I-A

1. The checkpoint name and number is approved as **EC9 Phase 9I - Shared Pricing Calculator Completion / Recovery**.
2. Cut Vinyl uses `$25` as the recommended starter item minimum. It remains tenant-configurable in later setup work. Phase 9I-A records this in contract metadata and does not change live pricing math.
3. Digital Print has separate future configuration concepts: `item_minimum` recommended at `$20` and `order_minimum` recommended at `$40`. Phase 9I-A records the distinction in contract metadata and does not apply the split to live pricing.
4. Saved Calculations Library is approved for a later Phase 9I implementation phase. Phase 9I-A does not build the library.
5. Saved calculation transfer into Quote/Order will create an independent line-item pricing snapshot and preserve source ID/revision traceability in a later phase. Phase 9I-A does not implement transfer behavior.
6. The future navigation label is **Pricing Calculators** under **Shop Operations**. **Pricing Defaults** remains under **Control Center**. Phase 9I-A does not modify navigation.
7. Apparel metadata correction is approved: Apparel is table-based and cost-plus, not `per_sqft`. Phase 9I-A corrects this in the new registry contract and keeps the legacy starter-default `pricing_method` value untouched for backward compatibility with existing setup consumers and the protected-file boundary.

## 1. Repository And Merge Preflight

| Check | Result |
|---|---|
| Active branch before writing this preflight | `main` |
| `main` / `origin/main` | Both at `08fbe1fd1e4265df8b4047a5ca138b056cd0a82e` |
| PR #13 merge present | Yes: `08fbe1f Merge pull request #13 from dnblack323/CODEX-security-recovery-branch` |
| Security commit present in main | Yes: `1b3452b0c5e54de9a4aeb09e4f58c0637d331b6f` |
| Security commit checks | GitHub check-runs inspected: six completed/success check-runs across two CI runs, including backend-tests, frontend-build, and frontend-tests |
| Calculator PR #12 present before PR #13 | Yes: `1de2de7 Merge pull request #12 from dnblack323/CODEX-calculator-branch` |
| Security branch introduced calculator changes | No pricing/calculator file matches in `git show --name-only 1b3452b...`; diff from calculator merge to current main changes security/platform files only |
| Protected Banner files changed after calculator merge | No changes found for the seven protected Banner files between `1de2de7` and `08fbe1f` |
| Fast-forward main | `git pull --ff-only origin main` reported already up to date |
| Working tree before documentation | Clean |

Protected Banner files checked:

- `backend/app/services/pricing_flat_sqft.py`
- `backend/app/services/pricing_snapshot.py`
- `backend/app/services/starter_defaults.py`
- `backend/tests/test_banner_pricing_owner_decisions.py`
- `frontend/src/components/commerce/LineItemDialog.jsx`
- `frontend/src/components/pricing/CategorySpecificFields.jsx`
- `frontend/src/pages/PricingCalculatorPage.jsx`

## 2. Checkpoint Number Selection

The next pricing-calculator checkpoint should be recorded as **EC9 Phase 9I - Shared Pricing Calculator Completion / Recovery**.

Rationale:

- EC09 is the active authoritative pricing calculator specification.
- Tracking says EC9 Phases 9A-9H are closed, but the owner has reopened calculator completion work after the verified Banner repair.
- EC20-EC22 are unrelated later checkpoints and should not be used for pricing calculator recovery.
- Phase 9I can preserve the historical 9H closure record while creating a controlled, auditable follow-on scope.

## 3. Authoritative Sources Inspected

| Source | Use |
|---|---|
| `specs_pack/extracted/EC09_Pricing_Foundation_Calculators_and_Order_Pricing.docx` | Category list, formulas, outputs, snapshots, Quote/Order integration, exact Business Card tiers |
| `preflight/EC9_PRICING_FOUNDATION_CALCULATORS_AND_ORDER_PRICING_PREFLIGHT.md` | Original EC9 phase and hold context |
| `PRICING_DEFAULTS_AUDIT.md` | Pricing-default inventory reference |
| `docs/architecture/pricing_snapshots.md` | Snapshot contract |
| `docs/architecture/order_item_rules.md` | Order Item behavior |
| `docs/architecture/quote_to_order_conversion.md` | Quote to Order price preservation |
| `docs/architecture/quote_revisions.md` | Quote revision constraints |
| `docs/modules/quotes.md`, `docs/modules/orders.md`, `docs/modules/order_items.md` | Existing commerce integration docs |
| `docs/modules/ec14_webstores.md`, `docs/modules/ec15_wrap_lab.md` | Deferred adjacent module boundaries |
| `backend/app/services/pricing.py` | Canonical calculator dispatcher |
| `backend/app/services/pricing_flat_sqft.py` | Banner/Rigid/Digital/Cut Vinyl implementation |
| `backend/app/services/pricing_apparel.py` | Apparel implementation |
| `backend/app/services/pricing_promotional.py` | Promotional/Business Cards implementation |
| `backend/app/services/pricing_vehicle_graphics.py` | Vehicle Graphics implementation |
| `backend/app/services/pricing_services.py` | Services implementation |
| `backend/app/services/pricing_custom.py` | Custom/Misc implementation |
| `backend/app/services/order_pricing.py` | Shared Quote/Order/reference resolver |
| `backend/app/services/pricing_snapshot.py` | Embedded item snapshot builder |
| `backend/app/services/pricing_snapshot_records.py` | Durable append-only snapshot records |
| `backend/app/services/starter_defaults.py` | Tenant starter settings/category defaults |
| `backend/app/routers/pricing*.py`, `quotes.py`, `orders.py` | API boundaries |
| `backend/app/models/material*.py`, `pricing_component.py`, `pricing_saved_item.py`, `pricing_snapshot_record.py` | Data contracts |
| `backend/app/core/db.py`, `backend/app/core/permissions.py` | Indexes and permissions |
| `frontend/src/pages/PricingCalculatorPage.jsx` | Dedicated calculator workspace |
| `frontend/src/components/commerce/LineItemDialog.jsx` | Quote/Order dialog calculator integration |
| `frontend/src/components/pricing/*.jsx`, `wizardConfigs.js` | Category setup and calculator inputs |
| `frontend/src/lib/navigation.js`, `frontend/src/App.js` | Route/navigation exposure |
| `backend/tests/test_ec9*.py`, `test_banner_pricing_owner_decisions.py`, `test_pricing_snapshot.py` | Existing backend coverage |

## 4. Complete Current-State Calculator Audit

### Current Backend Shape

- `calculate_pricing()` in `backend/app/services/pricing.py` is the single calculator entry point.
- Category services are split by formula family:
  - `pricing_flat_sqft.py`: Banners, Rigid Signs, Digital Print, Cut Vinyl.
  - `pricing_vehicle_graphics.py`: Vehicle Graphics/Wraps pricing only.
  - `pricing_apparel.py`: Apparel.
  - `pricing_promotional.py`: Promotional Items, including Business Card saved tiers.
  - `pricing_services.py`: Services.
  - `pricing_custom.py`: Custom/Miscellaneous strict manual fallback.
- `order_pricing.py` resolves Material Pricing Profiles, Pricing Components, Saved Items, and current tenant settings before calling the calculator.
- `/api/pricing/calculate` uses `pricing:calculate`; settings/write endpoints use `pricing:read` and `pricing:write`.
- Quote and Order routers call the same resolver for detailed line items and order items.

### Current Frontend Shape

- `/pricing-calculator` exists and renders `PricingCalculatorPage.jsx`.
- `/pricing-foundation` exists and renders `PricingFoundationPage.jsx`.
- `Pricing Calculator` is not currently exposed in `frontend/src/lib/navigation.js`; `Pricing Defaults` appears under Control Center.
- `PricingCalculatorPage.jsx` supports category selection, dimensions, category-specific inputs, saved/common item selection, material profile selection, pricing component selection, manual override, method comparison when present, and Add to Quote/Add to Order.
- `LineItemDialog.jsx` embeds the same category input components for Quote Line Items and Order Items.

### Current Snapshot Shape

- Embedded item snapshots are built by `pricing_snapshot.py`.
- Durable records are stored in `pricing_snapshot_records`.
- Durable snapshot source types are currently limited to `quote_line_item` and `order_item`.
- Snapshot money fields use integer cents; configuration records intentionally still use dollar-based fields today.
- Snapshot records are append-only except status lineage metadata.

### Current Setup Shape

- Pricing Foundation and grouped quiz configure shop defaults, category defaults, material pricing profiles, pricing components, and saved items.
- Exact Business Card tiers are stored as tenant-scoped starter `PricingSavedItem` records under `promotional`.
- There is not yet one Simple Setup flow that asks owner-friendly questions and writes all required settings with explicit review.

## 5. Category Traceability Matrix

| Category / product family | EC09 requirement | Current implementation | Current status | Gaps for 9I |
|---|---|---|---|---|
| Banners | Sqft pricing, waste, finishing, design/install, overhead, markup, minimum, comparison methods, snapshots | `pricing_flat_sqft.py` advanced Banner path, detailed method results, frontend comparison UI, protected Banner tests | Strongest implemented category | Preserve exactly; use as reference contract for shared method output |
| Rigid Signs | Sqft pricing, material/graphic method, waste, overhead, markup, minimum, quantity tiers | Generic flat sqft path with category defaults and fields | Partial compared with Banner | Add shared method result contract and visible formula source details |
| Cut Vinyl | Sqft pricing, waste, tape, overhead, markup, minimum | Generic flat sqft path | Partial; possible default conflict | EC09 text says minimum $20 while current starter default is $25; needs owner decision before changing |
| Digital Print | Sqft pricing, ink/laminate/substrate, overhead, markup, minimum item/order handling | Generic flat sqft path | Partial; minimum semantics incomplete | EC09 describes $20 per item / $40 per order; current single `$40` minimum does not express both |
| Vehicle Graphics / Wraps | Vehicle type, coverage, material/laminate/window-perf, install/design/prep labor, package/benchmark vs cost-plus | `pricing_vehicle_graphics.py` with benchmarks and provisional warnings | Implemented but not normalized to shared comparison UI | Add shared method output rows for benchmark/package and cost-plus; keep Wrap Lab workflow deferred |
| Apparel | Blank garments, decoration methods, setup, plus-size, name/number, rush, minimum | `pricing_apparel.py`, exact/provisional source labels, warnings | Implemented but config label is inconsistent | Starter category still says `pricing_method="per_sqft"` although dispatcher uses apparel formula |
| Services | Labor/travel/trip/equipment/subcontract/permit/rush/minimum | `pricing_services.py` wired into dispatcher | Implemented formula path | Needs shared method/result display and clearer Simple Setup fields |
| Promotional Items | Saved-item library, exact Business Card tiers, no guessed non-matching tier price | `pricing_promotional.py`, `BUSINESS_CARD_STARTER_ITEMS`, exact tier endpoint | Implemented for Business Cards and generic promo modes | Needs clear workspace UX for exact tier, per-piece, flat-fee, and manual-required states |
| Standard Paper Business Cards | Exact EC09 tier table | Tenant starter saved item | Implemented | Keep as saved/common item, not separate category |
| Magnetic Business Cards | Exact EC09 tier table | Tenant starter saved item | Implemented | Keep as saved/common item, not separate category |
| Custom / Miscellaneous | Manual fallback, optional manual cost/profit | `pricing_custom.py` strict manual | Implemented by design | Do not add invented formula engine |

## 6. Pricing-Method Support Matrix

| Pricing method | Current support | Categories currently using it | 9I target |
|---|---|---|---|
| `square_foot_plus_addons` | Banner only, full method row | Banners | Preserve and make part of shared method registry |
| `cost_plus` | Banner comparison row; other services have category-specific cost-plus names | Banners, Vehicle, Apparel, Services, Promotional variants | Normalize output naming and comparison rows without changing formulas |
| `target_margin` | Banner comparison row only | Banners | Add shared optional method row where formula has enough cost data |
| `materials_labor_overhead` | Banner comparison row only | Banners | Add shared optional method row where category formula has explicit cost components |
| `minimum_charge` | Banner comparison row; other categories apply minimum internally | Banners plus implicit others | Expose minimum handling consistently in result detail sections |
| `per_sqft` / sell-rate | Generic flat sqft selected method | Rigid, Cut Vinyl, Digital Print | Keep, but express through shared result rows |
| `cost_plus_labor` | Category default for Vehicle, Services, Promo, Custom; dispatcher-specific | Vehicle, Services, Promotional, Custom | Preserve as formula family but separate from selectable comparison methods |
| `vehicle_benchmark` / package | Vehicle only | Vehicle Graphics | Expose as method row with source label and no invented benchmarks |
| `apparel_table` / `apparel_cost_plus` | Apparel only | Apparel | Expose table vs estimate with authority labels |
| `tier_pricing` | Promotional saved items; exact match only | Business Cards | Keep exact tier behavior; no interpolation |
| `per_piece` | Promotional | Promotional | Keep as configurable mode |
| `flat_fee` | Promotional and Services | Promotional, Services | Keep as configurable mode |
| `hourly`, `per_crew_hour`, `per_unit`, `pass_through`, `hybrid`, `manual` | Services | Services | Keep in Services setup, but do not promote every small variant as a top-level calculator category |
| `manual_override` | All paths | All | Preserve; requires reason in Quote/Order when replacing calculated suggested price |

## 7. Simple Setup Recommendation Matrix

| Setup area | Current state | Recommendation |
|---|---|---|
| Shop labor/rates | Stored as `production_hourly_rate`, `design_hourly_rate`, `install_hourly_rate`, etc. | Keep current field keys; label them in UI as shop labor rates. Do not rename without migration. |
| Markup and target margin | Stored globally and per category | Simple Setup should ask target margin and markup in business language, then map to existing fields. |
| Minimums | Stored per category and globally | Simple Setup should ask minimum order/item charges and warn when EC09 has per-item/per-order semantics not represented. |
| Waste | Stored globally and per category | Simple Setup should show category-specific waste defaults and allow review before applying. |
| Materials | Canonical Material plus Material Pricing Profile | Simple Setup should create/update pricing profiles, not inventory materials, unless the material already exists or the owner intentionally creates it. |
| Add-ons/components | Pricing Components exist | Simple Setup should seed/edit tenant components such as design, finishing, hardware, install, rush; inactive components must be unavailable to calculators. |
| Saved/common items | Pricing Saved Items exist | Simple Setup should support common presets and variations but avoid treating saved config as a committed price. |
| Business Cards | Exact saved item tiers exist | Simple Setup should expose the exact tier table and state that non-matching quantities require manual price. |
| Category methods | Mixed and partly category-specific today | Create a shared method registry and simple owner labels before expanding UI. |
| Formula assumptions | Some provisional assumptions already warning-labeled | Keep warnings; owner must approve any new values before defaults change. |
| Webstores/Wrap Lab | Existing modules consume/own adjacent workflows | Keep 9I focused on calculator contracts; no Webstore payout or Wrap Lab workflow changes. |

### Recommended Simple Setup Methods By Category

Simple Setup should enable two comparison methods only when the category genuinely supports two useful methods from current code or EC09 source evidence. If fewer than two are supported, the UI should state that the category has one recommended method and should not fabricate a second comparison.

| Category / preset | Primary recommended method | Second recommended comparison method | Supports fewer than two? | Notes |
|---|---|---|---|---|
| `banners` | `square_foot_plus_addons` | `cost_plus` | No | Banner already proves selectable comparison behavior; `target_margin` can remain an optional advanced third method. |
| `rigid_signs` | `per_sqft` / sell-rate | `cost_plus` | No | Needs shared method rows; formula already has rate, material/labor cost, markup, and minimum data. |
| `cut_vinyl` | `per_sqft` / sell-rate | `cost_plus` | No | Owner must decide the default minimum conflict before changing expected values. |
| `digital_print` | `per_sqft` / sell-rate | `cost_plus` | No | Owner must decide item-vs-order minimum semantics before changing expected values. |
| `vehicle_graphics` | `vehicle_benchmark` / package where documented | `vehicle_cost_plus` | Sometimes | Vehicle types without an approved benchmark should compare only cost-plus and warn; do not invent benchmark prices. |
| `apparel` | `apparel_table` where an exact table applies | `apparel_cost_plus` / foundation estimate | Sometimes | Exact-table authority and foundation-estimate authority must be visually distinct. |
| `services` | selected service preset method, such as `hourly` or `flat_fee` | detailed labor/cost-plus comparison where enough cost inputs exist | No for common services; yes for pass-through/manual-only cases | Do not expose every service method as a top-level category choice. |
| `promotional` | `tier_pricing` when a saved tier table exists | `per_piece` or `flat_fee` when tenant setup supports it | Sometimes | Non-matching exact tier quantities require manual price; no interpolation. |
| Standard Paper Business Cards preset | `tier_pricing` exact table | none by default | Yes | Exact EC09 tier saved item; non-matching quantities require manual price. |
| Magnetic Business Cards preset | `tier_pricing` exact table | none by default | Yes | Exact EC09 tier saved item; non-matching quantities require manual price. |
| `custom` | `manual_override` / `unit_price_x_quantity` | none | Yes | Strict manual fallback is the intended behavior. |

## 8. Field, Formula, And Conditional Gap Register

| ID | Gap | Impact | Recommendation | Owner hold |
|---|---|---|---|---|
| G1 | No shared category-method registry; method names are spread across defaults, formula files, and frontend wizard config | UI and snapshots can drift by category | Add backend contract/service that lists category methods, labels, source authority, and required inputs | No |
| G2 | Banner has full `pricing_method_results`; most categories return only one method | Quote/Order/dialog users get inconsistent breakdowns | Normalize all calculation results to return method rows where meaningful | No formula changes without expected-value tests |
| G3 | `/pricing-calculator` route exists but is not in main navigation | Users cannot easily find the dedicated calculator workspace | Add a Shop Operations navigation destination after owner approves implementation | No |
| G4 | `PricingFoundationPage` and `PricingCalculatorPage` boundaries are visually/functionally close | Users may confuse setup defaults with live calculators | Keep setup under Control Center; expose calculators under Shop Operations | No |
| G5 | Frontend `wizardConfigs.js` method options do not match backend Banner method names | Setup UI can write values that do not map cleanly to actual formulas | Drive setup choices from backend method registry or align static config | No |
| G6 | Category defaults mix formula-family labels with selectable price methods | Reporting/snapshots can be hard to explain | Separate `formula_family` from `default_pricing_method` in contracts, with compatibility migration | Needs migration care |
| G7 | Cut Vinyl default minimum differs from EC09 text | Potential incorrect starter price | Owner must decide whether to preserve current $25 or revert to EC09 $20 | Yes |
| G8 | Digital Print has one minimum default but EC09 describes item/order minimum behavior | Potential over/under minimum handling | Add explicit per-item and per-order minimum fields only after owner approval | Yes |
| G9 | Apparel category default says `per_sqft` although apparel formula is table/cost-plus based | Misleading setup/config | Correct metadata without changing pricing math | No |
| G10 | Standalone calculator result is not saved as its own immutable calculation record | One-time estimates can be lost unless added to Quote/Order or saved as reusable config | Add `pricing_calculation_records` or extend snapshot source types for standalone calculator saves | Needs owner decision on library UX |
| G11 | Saved Item stores input config, not priced result | Correct design, but easy to misunderstand | UI copy and docs should distinguish reusable item presets from saved calculations | No |
| G12 | Configuration money fields are dollar floats while persisted Quote/Order/snapshot money is cents | EC1 cents policy is satisfied at committed price boundary, but setup config precision can vary | Do not silently migrate all config in 9I unless scoped; add tests to preserve cents on committed outputs | Possible later hardening |
| G13 | Inactive/unavailable behavior is spread across selectors/services | Risk of using inactive material/profile/component/saved item | Add tests and shared guards for inactive references in calculate + Quote/Order paths | No |
| G14 | Formula explanation shape differs by category | Users cannot compare categories consistently | Standardize `detail_sections`, `source_labels`, `warnings`, and `assumptions` keys | No |
| G15 | No frontend tests specifically cover the dedicated calculator full workflow | Browser regressions possible | Add focused React tests and Playwright/manual QA plan | No |

## 9. Shared Architecture And Data-Contract Plan

Phase 9I implementation should preserve the existing single calculator authority and add a shared result contract around it.

### Backend Contracts

Create a small backend contract layer, likely:

- `backend/app/services/pricing_contracts.py`
- `backend/app/services/pricing_method_registry.py`

Shared calculation output should include, for every category:

- `category`
- `formula_family`
- `quantity`
- `measurement`
- `category_inputs_used`
- `pricing_method_used`
- `selected_pricing_method`
- `pricing_method_results`
- `selling_price`
- `calculated_unit_price_cents`
- `true_cost`
- `profit_amount`
- `profit_margin_percent`
- `breakdown`
- `detail_sections`
- `source_labels`
- `calculation_warnings`
- `requires_manual_price`
- `manual_override`
- frozen references for material profile, components, saved item, and category defaults where used

Rules:

- Do not add a second pricing engine.
- Do not move formula math into the frontend.
- Do not change Banner results except where tests prove compatibility.
- Do not invent category prices or assumptions.
- Do not treat Custom/Misc as an automatic estimator.
- Keep committed Quote/Order/snapshot money in integer cents.

## 10. Dedicated Pricing Calculators Workspace Plan

Location:

- Route: existing `/pricing-calculator`.
- Navigation: add under **Shop Operations** as `Pricing Calculators` or `Pricing Calculator`.
- Keep `Pricing Defaults` under **Control Center**.

Workspace sections:

- Category selector.
- Saved/common item selector.
- Required inputs.
- Optional finishing/components.
- Material profile selector.
- Pricing method selector/comparison.
- Result cards.
- Detailed breakdown.
- Warnings/assumptions.
- Save as reusable item.
- Save calculation snapshot/library entry, if owner approves.
- Add to Quote / Add to Order.

Do not add:

- Webstore publish flow.
- Wrap Lab project workflow.
- Checkout/payment/subscription behavior.
- AI pricing advice or live market calls.

## 11. Quote And Order Integration Plan

Current Quote/Order integration should remain authoritative:

- `LineItemDialog.jsx` stays shared between Quote Line Items and Order Items.
- `quotes.py` and `orders.py` continue to recompute server-side for `selected_price_source="suggested"`.
- Client-provided `unit_price_cents` must not override suggested pricing.
- Manual price override remains explicit and reasoned.
- Recalculate Preview remains pure compute; accept is still a separate save/update operation.
- Quote to Order conversion must copy snapshots and pricing fields without recalculating.
- Existing non-detailed/manual line item behavior must remain backward compatible.

Phase 9I should add tests that the same category input produces identical result rows and snapshots across:

- Dedicated Pricing Calculator.
- Quote Item detailed dialog.
- Order Item detailed dialog.

## 12. Snapshot And Saved-Calculation Plan

Current records:

- `PricingSavedItem`: reusable input preset, not a committed price.
- `PricingSnapshotRecord`: append-only committed pricing evidence for Quote Line Items and Order Items.

Recommended 9I addition, pending owner approval:

- Add a standalone saved calculation record or extend snapshot source types with `standalone_calculation`.
- Store the exact calculator request, normalized inputs, method results, selected method, final price, warnings, source labels, formula version, and frozen defaults.
- Keep it tenant-scoped.
- Keep it immutable after save, except archival/status metadata.
- Do not let saved standalone calculations mutate live Quote/Order prices automatically.
- Adding a saved calculation to a Quote/Order should either copy the frozen result as a manual/snapshot import with clear source, or recompute from current settings by explicit user choice. The safer MVP default is recompute unless the user chooses "use saved price snapshot."

## 13. Indexes

Existing relevant indexes:

- `pricing_settings`: unique `tenant_id`.
- `material_pricing_profiles`: unique `id`, unique `(tenant_id, material_id)`.
- `pricing_components`: unique `id`, unique `(tenant_id, key)`.
- `pricing_saved_items`: unique `id`, `(tenant_id, category)`, `(tenant_id, quick_select)`.
- `pricing_quiz_submissions`: unique `id`, `(tenant_id, status)`, `(tenant_id, created_at)`.
- `pricing_snapshot_records`: unique `id`, `(tenant_id, source_type, source_id, status)`, `(tenant_id, created_at)`.
- Quote/Order item indexes already include tenant and parent IDs.

Required 9I indexes if saved standalone calculations are implemented:

- `pricing_calculation_records`: unique `id`.
- `pricing_calculation_records`: `(tenant_id, category, created_at)`.
- `pricing_calculation_records`: `(tenant_id, saved_item_id, created_at)`.
- `pricing_calculation_records`: `(tenant_id, status, created_at)`.
- Optional idempotency index if a save action accepts `idempotency_key`: unique `(tenant_id, created_by_user_id, idempotency_key)` with partial filter on string key.

Potential index hardening:

- `pricing_saved_items`: `(tenant_id, category, active, quick_select)` for selectors.
- `pricing_components`: `(tenant_id, category, active)` if category-specific component filtering becomes common.

Phase 9I-B index decision:

- No new collection was created.
- Tenant method configuration is stored in `pricing_settings.category_method_configurations`.
- The existing unique `pricing_settings.tenant_id` index is the required write/read index because every 9I-B operation resolves tenant ID from auth context and updates one tenant settings document.
- Existing audit indexes support `pricing_method_configuration` audit lookups by `(tenant_id, entity_type, entity_id, created_at)`.
- No dynamic per-category subdocument index was added because 9I-B never queries across tenant documents by category method configuration.

## 14. Required Tests

### Backend Unit/Service

- Each category returns the shared calculation contract.
- Banner protected owner-decision tests still pass unchanged.
- Rigid Signs, Cut Vinyl, Digital Print include method rows and detail sections.
- Vehicle Graphics exposes benchmark/package and cost-plus results correctly.
- Apparel exposes exact-table vs foundation-estimate authority labels.
- Services exposes selected service method and source formulas.
- Promotional exact Business Card tiers return exact tier; non-matching quantity returns manual-required without guessed price.
- Custom/Misc remains strict manual.
- Inactive Material Profile, Pricing Component, and Saved Item cannot be used by calculate/Quote/Order.
- Cross-tenant references are rejected.
- Suggested price is server authoritative.
- Manual override requires reason where it replaces a calculated result.

### Backend API

- `/api/pricing/calculate` returns identical result shape across categories.
- `/api/pricing/settings` or a new contract endpoint exposes category/method registry safely.
- Quote line item create/update/recalculate uses same result as dedicated calculator.
- Order item create/update/recalculate uses same result as dedicated calculator.
- Quote to Order conversion preserves pricing snapshots.
- Saved standalone calculation behavior, if approved, is immutable and tenant-scoped.
- Audit events are written for settings/saved item/component/profile mutations and standalone saved-calculation create/archive actions, if implemented.

### Frontend

- Pricing Calculator page renders every category with required inputs.
- Method selector changes selected method intentionally and does not auto-pick highest result.
- Incomplete/invalid dimensions do not show misleading stale price.
- Auto-debounce marks previous result as updating.
- Same Banner result appears in dedicated calculator, Quote Item, and Order Item.
- Saved/common item selector works for Business Cards.
- Non-matching Business Card quantity displays manual-required warning.
- Quote Item and Order Item dialogs reopen snapshots with original entered units, normalized dimensions, method rows, selected method, and detailed breakdown.
- Navigation exposes calculators under Shop Operations and setup under Control Center.

### Commands

Targeted backend:

```powershell
cd backend
python -m pytest tests/test_banner_pricing_owner_decisions.py tests/test_ec9_phase9e1_flat_sqft_categories.py tests/test_ec9_phase9e2_apparel_promo.py tests/test_ec9_phase9e2_corrections_and_9e3_vehicle.py tests/test_ec9_phase9e4_services_and_custom.py tests/test_ec9_phase9f_quote_order_integration.py tests/test_ec9_phase9g_snapshots_and_advisory.py tests/test_ec9_phase9h_closure_regressions.py -q
```

Full directly affected backend:

```powershell
cd backend
python -m pytest tests/test_ec9*.py tests/test_banner_pricing_owner_decisions.py tests/test_pricing_snapshot.py tests/test_foundation_hardening.py -q
```

Frontend:

```powershell
cd frontend
yarn test --runInBand
yarn build
```

Repository checks:

```powershell
git diff --check
git status --short --branch
```

## 15. Phased Implementation Plan

### Dependency Order Summary

1. Shared contracts and category-method configuration.
2. Simple Setup and Advanced Setup contracts.
3. Method comparison engine.
4. First complete category vertical slice: Banner, preserving the verified behavior.
5. Dedicated Pricing Calculators workspace.
6. Quote/Order shared integration parity.
7. Remaining category families: area-based products, Vehicle Graphics, Apparel, Promotional/Business Cards, Services, Custom.
8. Wrap Lab and Webstore consumer contracts only; operational module changes remain deferred unless separately authorized.
9. Snapshot/integration hardening.
10. Final cross-category verification and evidence.

### Phase 9I-A - Contracts And Registry

- Add shared calculation output helpers.
- Add category/method registry with labels, formula families, required input metadata, source authority, and unavailable/deferred flags.
- Align frontend method labels with backend registry.
- Tests: backend contract shape, registry permissions, no math changes.

### Phase 9I-B - Simple And Advanced Setup Contracts

- Add backend-readable method configuration contract per tenant/category.
- Keep Simple Setup as recommended defaults with two methods only where supported.
- Keep Advanced Setup as authorized configuration of one to three supported methods.
- Prevent rerun of Simple Setup from silently overwriting deliberate Advanced configuration.
- Tests: supported method limits, primary method required, max three comparisons, restore recommended configuration.

### Phase 9I-C - Method Comparison Engine And Banner Vertical Slice

- Extract the Banner method-result shape into reusable helpers without changing Banner math.
- Prove Banner still returns the verified values and selected-method behavior.
- Separate universal add-ons from method-specific formula math so they are not omitted or double-counted.
- Tests: protected Banner tests plus new shared-contract tests.

### Phase 9I-D - Normalize Category Outputs

- Update non-Banner category services to return shared method rows/detail sections.
- Preserve existing formulas and expected numbers unless owner-approved gaps are fixed.
- Tests: exact category expected examples.

### Phase 9I-E - Dedicated Calculator Workspace

- Expose `/pricing-calculator` in Shop Operations navigation.
- Keep `/pricing-foundation` under Control Center.
- Improve workspace display for methods, warnings, saved items, and breakdowns.
- Tests: route/nav render and category workflow.

### Phase 9I-F - Quote/Order Dialog Parity

- Ensure Quote Item and Order Item dialogs consume the same contract.
- Preserve snapshots on reopen.
- Validate server-authoritative suggested pricing and manual override reason paths.
- Tests: dedicated/quote/order parity.

### Phase 9I-G - Saved Calculation Library

- Implement only if owner approves the saved-calculation record.
- Add backend model/service/router/indexes and frontend affordance.
- Preserve immutability and tenant isolation.
- Tests: save, list, read, archive, cross-tenant denial, no automatic Quote/Order mutation.

### Phase 9I-H - Direct Consumer Contracts

- Document and test read-only consumer boundaries for Work Order Summary, reporting, Webstores, and Wrap Lab.
- Do not change Webstore payout, storefront, Wrap Lab project, or production workflow behavior in this phase unless separately authorized.
- Tests: existing consumers still read snapshots without recalculation.

### Phase 9I-I - Verification, Evidence, Closure

- Run targeted backend tests, frontend tests/build, `git diff --check`.
- Perform browser QA for calculator, Quote Item, and Order Item workflows.
- Update evidence and tracking docs.
- Stop for owner review before any later checkpoint.

### Current Implementation Boundary

Phase 9I-A and Phase 9I-C have passed owner/review gates recorded in this document. Phase 9I-B backend tenant method-configuration work remains implemented as part of the uncommitted Phase 9I package. Phase 9I-D is implemented, its manual-override normalization defect is corrected, and final re-review status is `PHASE 9I-D RE-REVIEW PASSED`. All of Phase 9I is not closed. Phase 9I-E and later remain deferred. Do not start frontend workspace, Quote/Order parity, saved calculations, consumer contracts, or closure until the owner separately authorizes the next phase.

## 16. Exact Files Expected To Change In Implementation

Expected backend files for the overall Phase 9I plan:

- `backend/app/services/pricing_contracts.py` (new)
- `backend/app/services/pricing_method_registry.py` (new)
- `backend/app/services/pricing_method_configurations.py` (new in Phase 9I-B)
- `backend/app/services/pricing.py`
- `backend/app/services/pricing_flat_sqft.py`
- `backend/app/services/pricing_vehicle_graphics.py`
- `backend/app/services/pricing_apparel.py`
- `backend/app/services/pricing_promotional.py`
- `backend/app/services/pricing_services.py`
- `backend/app/services/pricing_custom.py`
- `backend/app/services/order_pricing.py`
- `backend/app/services/pricing_snapshot.py`
- `backend/app/services/pricing_snapshot_records.py`
- `backend/app/services/starter_defaults.py`
- `backend/app/routers/pricing.py`
- `backend/app/routers/quotes.py`
- `backend/app/routers/orders.py`
- `backend/app/core/db.py`
- `backend/app/models/pricing_calculation_record.py` (new, only if saved calculations approved)
- `backend/app/services/pricing_calculation_records.py` (new, only if saved calculations approved)
- `backend/app/routers/pricing_calculation_records.py` (new, only if saved calculations approved)

Expected frontend files:

- `frontend/src/lib/navigation.js`
- `frontend/src/App.js` only if a new saved-calculation route is approved
- `frontend/src/pages/PricingCalculatorPage.jsx`
- `frontend/src/pages/PricingFoundationPage.jsx` only for registry/method display alignment
- `frontend/src/components/commerce/LineItemDialog.jsx`
- `frontend/src/components/pricing/CategorySpecificFields.jsx`
- `frontend/src/components/pricing/wizardConfigs.js`
- `frontend/src/components/pricing/selectors/MaterialProfileSelector.jsx`
- `frontend/src/components/pricing/selectors/PricingComponentSelector.jsx`
- `frontend/src/components/pricing/selectors/SavedItemSelector.jsx`
- `frontend/src/components/pricing/SavedCalculationsPanel.jsx` (new, only if saved calculations approved)

Expected tests:

- `backend/tests/test_ec9_phase9i_pricing_contracts.py` (new)
- `backend/tests/test_ec9_phase9ib_pricing_method_configurations.py` (new in Phase 9I-B)
- `backend/tests/test_ec9_phase9i_category_method_outputs.py` (new)
- `backend/tests/test_ec9_phase9i_quote_order_parity.py` (new)
- `backend/tests/test_ec9_phase9i_saved_calculations.py` (new, only if saved calculations approved)
- `frontend/src/__tests__/PricingCalculatorPage.test.jsx` (new or update if existing)
- `frontend/src/__tests__/LineItemDialogPricing.test.jsx` (new or update if existing)
- Existing EC9 and Banner tests must remain passing.

Expected documentation/evidence:

- `docs/modules/pricing_calculators.md` (new or update)
- `evidence/EC9_PHASE9I_SHARED_PRICING_CALCULATOR_COMPLETION_REPORT.md` (new at implementation closure)
- `preflight/EC9_PHASE9I_SHARED_PRICING_CALCULATOR_PREFLIGHT_AND_IMPLEMENTATION_PLAN.md` (this file)
- `memory/MASTER_CHECKPOINT_CHECKLIST.md`
- `memory/checkpoint_reference_table.md`
- `memory/progress_register.md`
- `memory/PRD.md`

## 17. Owner Holds And Decisions Required

All seven owner holds listed in the original preflight are resolved for Phase 9I-A by the approved decisions recorded at the top of this document.

Remaining later-phase holds:

1. Implementing Simple Setup and Advanced Setup frontend controls remains deferred to a later Phase 9I phase.
2. Implementing the Saved Calculations Library remains deferred to a later Phase 9I phase.
3. Implementing saved-calculation transfer into Quote/Order remains deferred to a later Phase 9I phase.
4. Implementing the **Pricing Calculators** navigation destination remains deferred until the dedicated workspace phase.
5. Enforcing Digital Print item/order minimum behavior remains deferred because order-level minimums must be handled at document-total level, not as a single line-item formula.

## 20. Phase 9I-A Implementation Record

Contracts implemented in Phase 9I-A:

- Shared pricing contract primitives: `PricingMethodDefinition`, `PricingCategoryDefinition`, `PricingPresetDefinition`, and `TenantCategoryMethodConfiguration`.
- Stable global method registry with metadata only; no tenant rates, minimums, material costs, or formulas are stored in global method definitions.
- Stable category registry for all nine existing category IDs.
- Category-to-method support mapping and Simple Setup recommendation metadata.
- Conditional method availability helpers for Vehicle benchmark and Promotional methods.
- Tenant method configuration validation rules: tenant ID required, category match required, no duplicates, primary required when methods are enabled, primary must be enabled, every enabled method must be supported, stable order required, and no more than three enabled comparison methods.
- Business Card preset metadata preserving the existing saved-item starter behavior without registering presets as categories.
- Apparel registry metadata corrected to the real `apparel_table` and `apparel_cost_plus` support. The legacy starter-default `pricing_method` remains unchanged during 9I-A as a backward-compatible mapping; no Apparel formula or existing setup consumer changed.

Behavior intentionally deferred:

- Simple Setup behavior.
- Advanced Setup behavior.
- Tenant method configuration persistence.
- Method comparison calculation normalization.
- Dedicated Pricing Calculators workspace and navigation.
- Saved Calculations Library.
- Saved calculation transfer into Quote/Order.
- Digital Print order-minimum enforcement.
- Webstore and Wrap Lab consumer changes.

Pricing math unchanged:

- `calculate_pricing()` remains the live dispatch entry point.
- Existing category formula modules remain the live calculators.
- The new registry is descriptive metadata and validation only.

## 21. Phase 9I-B Read-Only Investigation Findings

Existing storage that can safely hold later tenant category-method configuration:

- `pricing_settings` is already tenant-scoped and unique by `tenant_id`.
- `category_defaults` already stores per-category tenant configuration and is updated by existing pricing settings services.
- A later phase can likely extend `category_defaults.{category_id}` with method configuration fields without a new collection, but this must include compatibility guards so Simple Setup does not overwrite Advanced configuration.

Existing schema/API extension points:

- `backend/app/services/pricing.py::update_category()` already updates tenant category defaults and records field sources.
- `backend/app/routers/pricing.py` already exposes read/write settings routes under pricing permissions.
- `PATCH /pricing/settings/categories/{category_id}` can accept category fields through the current update path, but Phase 9I-B should add explicit validation before method configuration is persisted.

Existing permissions and audit:

- Pricing setup reads use `pricing:read`.
- Pricing calculations use `pricing:calculate`.
- Pricing setup mutations use `pricing:write`.
- Existing pricing settings mutations call `record_audit` with actor, tenant, action, entity, and diff context.

Existing setup UI boundaries:

- `PricingFoundationPage.jsx` owns configuration under **Control Center -> Pricing Defaults**.
- `CategorySetupWizard.jsx` and `wizardConfigs.js` currently provide category setup scaffolds.
- `PricingCalculatorPage.jsx` is a working calculator route and should remain separate from setup.

Simple Setup overwrite control required in 9I-B:

- Store `configuration_mode`, `recommended_configuration_version`, `enabled_method_ids`, `primary_method_id`, and comparison order together.
- If a category is in Advanced mode or has deliberate method configuration, Simple Setup rerun should produce a review/diff and require explicit confirmation before changing method configuration.
- Restore-recommended behavior should be an explicit action with audit.

Compatibility work required:

- Preserve existing `pricing_method` values as formula-family/backward-compatible metadata while adding method-specific configuration fields.
- Map legacy `cost_plus_labor`, `per_sqft`, and `common_job_prices` setup terminology to the new stable method IDs for display/validation.
- Keep the live dispatcher unchanged until category formula outputs are normalized and tested in a later phase.

## 22. Phase 9I-B Implementation Record

Phase 9I-B selected the existing `pricing_settings` tenant document as the persistence destination. Evidence:

- `pricing_settings` is already unique by `tenant_id`.
- It already owns tenant Pricing Defaults and `category_defaults`.
- Existing pricing settings endpoints already use `pricing:read`, `pricing:write`, tenant context from `get_current_user`, and audit events.
- A separate collection would duplicate the established tenant settings boundary without improving isolation for one configuration per tenant/category.

Persisted shape:

- Top-level path: `pricing_settings.category_method_configurations.{category_id}`.
- Fields: `tenant_id`, `category_id`, `configuration_mode`, `enabled_method_ids`, `primary_method_id`, `comparison_order`, `compare_automatically`, `recommended_configuration_version`, `method_configuration_refs`, `validation_warnings`, `configuration_version`, `config_version`, created/updated timestamps, and created/updated actor fields.
- The record stores method-selection configuration only. It does not store calculated prices, calculator inputs, material/labor/rate copies, pricing snapshots, Quote/Order data, Webstore commerce data, or Wrap Lab data.

Service and API operations added:

- `GET /api/pricing/settings/category-method-configurations`
- `GET /api/pricing/settings/categories/{category_id}/method-configuration`
- `POST /api/pricing/settings/categories/{category_id}/method-availability`
- `POST /api/pricing/settings/categories/{category_id}/simple-setup/preview`
- `POST /api/pricing/settings/categories/{category_id}/simple-setup/apply`
- `PUT /api/pricing/settings/categories/{category_id}/advanced-setup`
- `POST /api/pricing/settings/categories/{category_id}/restore-recommendations`
- `GET /api/pricing/settings/categories/{category_id}/method-configuration/audit`

Simple Setup behavior:

- Preview is non-mutating and returns deterministic current recommendations, availability details, warnings, and the recommendation version.
- Preview selects up to two available recommended methods and never fabricates a second method.
- Apply is an explicit write.
- Repeated identical apply is idempotent and does not create duplicate audit events.
- Applying over Advanced configuration requires explicit `replace_advanced=true`.

Advanced Setup behavior:

- Saves one, two, or three supported and currently available methods.
- Persists primary method, display/comparison order, compare-automatically preference, and method-specific configuration references.
- Rejects unsupported, duplicate, unavailable, over-limit, missing-primary, invalid-primary, invalid-order, and invalid-reference configurations with structured field errors.
- Existing configurations require an expected version for meaningful updates, preventing stale overwrites.

Restore-recommendations behavior:

- Uses the current Simple Setup preview.
- Writes only after an explicit request.
- Does not write unavailable methods.
- Requires confirmation before replacing Advanced configuration.
- Preserves unrelated pricing defaults, materials, labor rates, minimums, markups, and other pricing settings.

Context-sensitive availability:

- Globally supported methods and currently available methods are separate.
- Vehicle benchmark is unavailable when the tenant has no approved benchmark configuration, or when a requested vehicle/coverage pair has no benchmark.
- Promotional tier, per-piece, and flat-fee methods are available only when tenant configuration or provided context supports them.
- Availability checks do not mutate configuration and do not run pricing formulas.

Permissions and tenant isolation:

- Reads require `pricing:read`.
- Writes require `pricing:write`.
- Audit readout requires existing audit access.
- Tenant ID is resolved from the authenticated user context; no endpoint accepts a client-controlled tenant ID.
- Portal tokens remain rejected by staff-route auth.

Audit and concurrency:

- Meaningful creation, Advanced save, Simple apply, confirmed Advanced replacement, restore, enabled-method changes, primary changes, order changes, and compare-automatically changes write audit records under entity type `pricing_method_configuration`.
- Non-mutating previews and identical idempotent writes do not create audit records.
- Updates use a per-category `configuration_version` and conditional write filter to prevent stale overwrites.

Legacy compatibility mappings added:

- `per_sqft` -> `per_sqft`
- `cost_plus_labor` -> `cost_plus`
- `cost_plus` -> `cost_plus`
- `square_foot_plus_addons` -> `square_foot_plus_addons`
- `tier_pricing` -> `tier_pricing`
- `flat_fee` -> `flat_fee`
- `unit_price_x_quantity` -> `unit_price_x_quantity`
- `common_job_prices` is intentionally not mapped because repository evidence shows it is reference/common-price data, not a stable formula method.

Tests added:

- `backend/tests/test_ec9_phase9ib_pricing_method_configurations.py`
- Focused coverage includes persistence, validation, Simple Setup preview/apply, Advanced Setup, restore recommendations, context-sensitive availability, read/write permissions, portal denial, tenant isolation, audit/no-op audit behavior, stale writes, legacy mappings, registry immutability, and unchanged Banner pricing.

Verification results:

- Phase 9I-A focused tests plus Phase 9I-B focused tests: `36 passed, 6 warnings`.
- Targeted EC9/pricing suite including Banner, snapshots, Phase 9I-A, Phase 9I-B, and foundation hardening tests: `201 passed, 6 warnings`.
- Quote, Order, and Work Order regression tests: `22 passed, 6 warnings`.
- Backend compile/import validation: passed.
- `git diff --check`: passed; only CRLF conversion warnings were reported for existing working-copy line endings.
- Full backend suite: `723 passed, 26 failed, 3 skipped, 6 warnings`.
- The full-suite failure count did not increase from the Phase 9I-A baseline. The 18 additional passes correspond to the new Phase 9I-B focused tests.
- Full-suite failures remained outside EC9 Phase 9I-B: EC10/EC10E media upload tests fail because `EMERGENT_LLM_KEY` is missing for object storage; EC18 voice fails with `OpenAI Realtime session creation failed`; EC13 billing tests fail with `stripe_not_configured`; EC13 founder contract preservation still fails with the existing founder contract conflict; EC6 portal payment still fails on its dev confirm route with `404 Not found`.

Deferred after Phase 9I-B:

- Pricing Defaults frontend pages and setup controls.
- Simple Setup frontend wizard.
- Advanced Setup frontend controls.
- Method-comparison calculation engine.
- Calculator comparison UI.
- Live pricing dispatcher changes.
- Pricing formula changes.
- Dedicated Pricing Calculators navigation/workspace.
- Saved Calculations Library.
- Quote/Order calculator UI changes.
- Webstore or Wrap Lab integration.
- Minimum-charge enforcement changes.
- Banner vertical-slice work, which is now completed by Phase 9I-C for the backend comparison contract only.

## 23. Phase 9I-C Implementation Record

Phase 9I-C implements a backend-only shared comparison contract for the existing Banner vertical slice.

Read-only review findings corrected:

- The original 9I-C adapter let saved or explicit comparison primary method selection change `pricing_result.selling_price`. Correction: `pricing_result` now comes from the ordinary canonical Banner calculation before comparison filtering/selection is applied.
- The original 9I-C adapter called settings/configuration helpers that could initialize first-run tenant pricing settings. Correction: the comparison adapter now uses a read-only settings lookup and in-memory starter-default fallback; first-run comparison does not create `pricing_settings`.

Implemented:

- Added `backend/app/services/pricing_method_comparisons.py` as a contract adapter over the existing `calculate_pricing()` Banner path.
- Added `POST /api/pricing/method-comparison` behind `pricing:calculate`.
- The 9I-C endpoint supports only `category: "banners"` in this phase and returns `comparison_not_available` for other categories.
- The endpoint can use an existing saved tenant Banner method configuration, or an explicit request-scoped method list, only to control comparison rows/order/primary.
- Saved tenant method configuration controls comparison order and selected primary method when present.
- Explicit request-scoped comparison supports one to three Banner-supported methods and remains non-persistent.
- Response includes `contract_version`, tenant/category, settings source, configuration source/version, comparison order, primary and selected comparison method IDs, `canonical_method_id`, normalized comparison rows, availability details, `mutated: false`, `persistent_entities_created: []`, and the existing canonical pricing result.
- Normalized rows are derived from the existing Banner `pricing_method_results` entries and preserve method amount, pre-adjustment amount, status, selected state, display label, and existing handler identity.
- Existing formula output is reused directly; no Banner formula, add-on, minimum, snapshot, frontend, or Quote/Order behavior changed.
- Existing default Banner behavior remains explicit: Square-foot plus add-ons is selected by default even when Cost-plus is higher.
- Missing resolved material profile or saved-item references fail with structured 404 errors.

Corrected field definitions:

- `pricing_result`: the unchanged ordinary canonical Banner calculation for the submitted pricing inputs, before saved or explicit comparison selection is applied. It retains ordinary Banner default method behavior and is the only canonical price result in this response.
- `primary_method_id`: the effective saved or explicit comparison primary method used for comparison presentation. It does not determine `pricing_result.selling_price`.
- `selected_method_id`: the comparison selection identifier. When saved or explicit comparison methods are supplied, this follows the comparison primary; otherwise it matches the canonical method.
- `canonical_method_id`: the method used by the ordinary canonical Banner calculation.
- `comparison_results[].amount`: the amount already present on the existing Banner method-result row for that method. Missing rows are not synthesized, failed rows keep failure status and null amount, and no comparison row amount is copied into the canonical price.
- `settings_source`: `persisted_settings` when an existing tenant settings document was read; `starter_defaults_fallback` when no persisted settings existed and starter defaults were used in memory only.
- `configuration_source`: `saved_tenant_configuration`, `explicit_request`, `existing_calculator_defaults`, or `starter_defaults_fallback`.

9I-B review gaps closed during 9I-C:

- Added a route-level audit-history denial test proving `pricing:read` alone is insufficient for method-configuration audit history.
- Added a cross-tenant saved-item availability test proving saved-item references are tenant-scoped before availability is resolved.
- Added a platform-role behavior test proving `platform:creator` / platform-admin fields do not grant tenant `pricing:write` on pricing-method configuration routes.

Correction tests added after read-only review:

- Saved `cost_plus` comparison primary does not change canonical `pricing_result.selling_price`.
- Explicit request-scoped comparison primary does not change canonical `pricing_result.selling_price`.
- Complete canonical result fields match the direct ordinary Banner calculation for identical inputs.
- First-run tenants use in-memory starter fallback and do not create `pricing_settings`, method configuration, audit events, saved calculation records, pricing snapshots, Quotes, Orders, Order Items, or Work Orders.
- Unsupported non-Banner categories return structured `404 comparison_not_available` before calculator dispatch and without persistence.
- Failed existing method rows keep failure status/null amount, missing method rows are not synthesized, and failed configured primary remains the comparison primary without replacing canonical price.

Behavior intentionally deferred after Phase 9I-C:

- Frontend setup controls.
- Calculator comparison UI changes.
- Automatic comparison in Quote/Order dialogs.
- Saved Calculations Library.
- Saved calculation transfer into Quote/Order.
- Category output normalization beyond Banners.
- Pricing Calculators navigation/workspace exposure.
- Digital Print order-minimum enforcement.
- Webstore and Wrap Lab consumer integration.

Verification results:

- Pre-edit Phase 9I-A and 9I-B focused suite: `36 passed, 6 warnings`.
- Phase 9I-C focused tests: `8 passed, 6 warnings`.
- Combined Phase 9I-A/B/C focused suite: `44 passed, 6 warnings`.
- Direct pricing/Banner/snapshot suite: `64 passed, 6 warnings`.
- Quote/Order/Work Order regression suite: `45 passed, 6 warnings`.
- Explicit full EC9 pricing set plus Banner and snapshot tests: `244 passed, 1 skipped, 6 warnings`.
- Backend compile check for `backend/app` and the new 9I-C test file: passed.
- `git diff --check`: passed; only existing CRLF conversion warnings were reported.

Correction verification after read-only review findings:

- Phase 9I-A focused tests: `18 passed`.
- Phase 9I-B focused tests: `18 passed, 6 warnings`.
- Corrected Phase 9I-C focused tests: `11 passed, 6 warnings`.
- Final combined Phase 9I-A/B/C focused tests after correction: `47 passed, 6 warnings`.
- Existing Banner owner-decision tests plus pricing snapshot tests: `10 passed`.
- Available Quote, Order, and Work Order pricing regressions after manual-override correction: `64 passed, 3 warnings`.
- Backend compile/import validation: `283 files`.
- `git diff --check`: passed; only existing CRLF conversion warnings were reported.

Independent read-only re-review result:

- Final review status: `PHASE 9I-C RE-REVIEW PASSED`.
- The initial Phase 9I-C review found canonical-result conflation and a first-run settings write. Both defects were corrected before re-review.
- `pricing_result` remains the unchanged ordinary Banner calculation.
- `primary_method_id` and `selected_method_id` are comparison metadata only.
- Comparison amounts come from existing Banner `pricing_method_results`.
- First-run tenants use in-memory starter defaults without creating `pricing_settings`.
- Unsupported categories are rejected before calculator dispatch.
- Failed and missing rows are handled without fabricated prices.
- The comparison remains tenant-scoped, authorized through `pricing:calculate`, and non-mutating.
- No frontend, protected pricing formula, Quote, Order, Order Item, Work Order, or snapshot behavior changed.
- Final verification recorded by re-review: Phase 9I-A/B/C `47 passed, 6 warnings`; Banner/snapshot `10 passed`; available Quote/Order/Work Order regressions `64 passed, 6 warnings`; backend compile/import validation `283 files`; `git diff --check` passed with CRLF conversion warnings only; no test failures.

## 24. Phase 9I-D Implementation Record

Phase 9I-D normalizes currently implemented non-Banner pricing category outputs into the shared Phase 9I method-output contract without changing any category formula or authoritative total.

Categories completed:

- `rigid_signs`
- `cut_vinyl`
- `digital_print`
- `vehicle_graphics`
- `apparel`
- `promotional`
- `services`
- `custom`

Categories blocked:

- None.

Implemented:

- Added `backend/app/services/pricing_method_outputs.py` as a pure adapter over existing calculator results.
- Wired `calculate_pricing()` to normalize non-Banner category outputs after the existing category calculator returns.
- Preserved existing formula modules as the sole source of price authority; no formulas, defaults, minimums, markups, rounding, labor, materials, add-ons, owner-approved prices, or Digital Print item/order minimum behavior changed.
- Added shared fields for non-Banner results: `pricing_output_contract_version`, `pricing_method_results`, `method_availability`, `detail_sections`, `canonical_method_id`, `method_output_source`, `mutated: false`, and `persistent_entities_created: []`.
- `pricing_method_results` uses stable method IDs from the Phase 9I registry. Selected method rows carry the existing authoritative selling total. Alternate method rows expose only candidate amounts already present in existing calculator output, such as vehicle benchmark/cost-plus and service cost-plus. Missing or unavailable methods keep null amounts and explicit unavailable status.
- Phase 9I-D read-only review found that existing `manual_override` calculator results for `rigid_signs`, `cut_vinyl`, `digital_print`, `vehicle_graphics`, and `apparel` preserved `selling_price` but did not produce a selected normalized method row. The correction adds the shared stable method ID `manual_override` to the method registry and appends one selected manual row only when the authoritative calculator result actually reports `pricing_method_used = "manual_override"`. Existing `custom` manual behavior remains mapped to `unit_price_x_quantity`. Formula-derived rows are not selected as authoritative and no new prices are fabricated.
- Category-specific detail survives through `detail_sections` and the existing category-specific top-level fields. The adapter does not force every calculator into a misleading identical breakdown.
- Unsupported methods are represented as unavailable in `method_availability`, not as fabricated comparison rows.
- Promotional exact-tier failure remains honest: a missing tier returns no selling price and a null tier row with `manual_price_required` / `no_exact_tier_match`; no replacement price is invented.
- Banner remains protected and unchanged; its existing `pricing_method_results` and detailed Banner contract are not normalized by the 9I-D adapter.

Behavior intentionally deferred after Phase 9I-D:

- Frontend setup controls.
- Calculator comparison UI changes.
- Dedicated Pricing Calculators navigation/workspace.
- Automatic comparison in Quote/Order dialogs.
- Quote/Order dialog parity work.
- Saved Calculations Library.
- Saved calculation transfer into Quote/Order.
- Webstore and Wrap Lab consumer integration.
- Digital Print order-minimum enforcement.
- Final Phase 9I evidence/closure.

Phase 9I-D verification:

- Final read-only re-review status: `PHASE 9I-D RE-REVIEW PASSED`.
- Phase 9I-D focused tests after manual-override correction: `26 passed`.
- Combined Phase 9I-A/B/C/D focused suite after manual-override correction: `73 passed, 3 warnings`.
- Existing category formula regressions for flat/sqft, apparel, promotional, vehicle, services, and custom calculators after manual-override correction: `100 passed, 3 warnings`.
- Existing Banner owner-decision tests plus pricing snapshot tests: `10 passed`.
- Available Quote, Order, and Work Order pricing regressions: `64 passed, 6 warnings`.
- Backend compile/import validation: passed.
- `git diff --check`: passed; only existing CRLF conversion warnings were reported.
- No test failures.

## 25. Risks And Controls

| Risk | Control |
|---|---|
| Breaking verified Banner behavior | Keep existing Banner tests; add parity tests before touching shared helpers |
| Mixing setup defaults with live calculator UX | Keep Pricing Defaults in Control Center and Calculators in Shop Operations |
| Introducing a duplicate engine | All workflows must continue through `calculate_pricing()` |
| Silent price changes from live defaults | Preserve snapshot immutability and explicit recalculation behavior |
| Cross-tenant reference misuse | Continue tenant-scoped lookups in `order_pricing.py`; add denial tests |
| Inactive references used accidentally | Add shared active guards and tests |
| Inventing unapproved prices | Owner holds for Cut Vinyl, Digital Print, and any missing category-specific constants |
| Expanding into Webstores/Wrap Lab | Keep 9I calculator-only; no payouts/storefront/wrap project changes |
| Frontend stale totals | Preserve debounce/updating behavior from Banner repair |

## 26. Stop Boundary

Phase 9I-A, 9I-B, 9I-C, and 9I-D are implemented as the current uncommitted Phase 9I package. Phase 9I-C has final review status `PHASE 9I-C RE-REVIEW PASSED`; Phase 9I-D is implemented with the manual-override normalization defect corrected and final re-review status `PHASE 9I-D RE-REVIEW PASSED`. Phase 9I-E and later should not begin until separately authorized.

No EC20, EC21, EC22, AI, attachments, markup, navigation redesign, Webstore payout, Wrap Lab workflow, EC4 payment/invoice, Stripe, provider, or unrelated work is included.
