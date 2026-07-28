# EC9 Phase 9I Calculator Extraction And Money Normalization Implementation Plan

**Status:** PHASE 9I-K VERSIONED PARITY FIXTURE FRAMEWORK IMPLEMENTED AND VERIFIED - PHASE 9I REMAINS OPEN; PHASE 9I-L NOT STARTED
**Date:** 2026-07-27
**Repository gate verified:** `main` at `7334cb24867102013350bde3ea4c8b84a59c4ff1`
**Planning document with implementation records:** Phase 9I-J and Phase 9I-K implementation results are recorded below. Phase 9I remains open.

## 1. Accepted Audit Conclusion

The separate read-only EC9 Phase 9I Calculator Extraction, Money Normalization, and Standalone Licensing Readiness Audit is accepted as the controlling input for this plan.

Accepted findings:

- Existing SaaS calculator behavior is currently functional.
- Quote and Order commerce totals are authoritative integer cents.
- Phase 9I cannot close because the calculator is not yet a pure portable engine.
- Calculator configuration, results, saved calculations, and snapshots still mix dollar floats, cents, Decimal values, percentages, basis points, and frontend numbers.
- Snapshot evidence is historically stable but not yet a clean portable contract.
- No shared versioned parity fixture pack currently proves identical SaaS and standalone results.
- Licensing must be added only after the reusable engine boundary passes.
- Phase 9I remains open.

## 2. Final Owner Decisions Recorded

### Human-readable admin configuration

The admin UI may continue displaying and accepting dollar values for usability. The UI is not an authoritative money boundary.

At the backend/configuration boundary:

- Fixed currency amounts use integer cents.
- High-precision rates use validated fixed-precision Decimal values serialized as strings with explicit units.
- Percentages that do not require greater precision use basis points.
- Quantities, dimensions, areas, time, multipliers, and waste factors remain non-currency values with explicit types and units.
- Numeric configuration values are not all converted to cents.

### Historical snapshots

Existing embedded dollar-float snapshot fields are immutable legacy evidence. They must never be recalculated or rewritten merely to match the new contract.

The migration is additive:

- Add a snapshot schema version.
- Add cents-first authoritative amount fields.
- Add explicit Decimal-string rate evidence where required.
- Preserve engine version, formula version, settings version, category configuration version, rounding policy, and source references.
- Continue reading legacy snapshots.
- Do not require destructive historical migration.
- Clearly distinguish legacy evidence from new authoritative fields.

Future implementation may stop writing new legacy dollar fields after an owner-approved compatibility gate, but existing historical fields and records remain readable permanently.

### Engine location

The extracted calculator first lives inside the existing `SIGNGUY-MVP` repository as a clearly isolated importable package.

Recommended package boundary:

- New pure package: `backend/pricing_engine/`
- SaaS adapter layer: `backend/app/services/pricing_engine_adapter.py` and existing router/service call sites
- Contract/parity fixtures: `backend/tests/fixtures/pricing_engine/`

The core package must not import FastAPI routers/request objects, authenticated users, tenant models, MongoDB clients, SaaS persistence models, React/frontend code, Stripe, SaaS entitlements, license validation, network services, or environment-specific application configuration.

No separate repository or published package is created during these phases.

### Licensing direction

Future standalone calculator licensing uses a hybrid model:

- Online initial activation.
- Signed locally stored license or activation lease.
- Offline grace period.
- Periodic online revalidation when connectivity is available.
- No live internet connection required for each calculation.
- No license checks inside formulas.
- No change to calculated results based on license type.
- License enforcement remains in the standalone application shell.

Licensing is not implemented during calculator extraction. Desktop framework selection is also deferred unless a separate authoritative owner decision requires it.

### Phase 9I closure gate

Phase 9I requires shared parity fixtures for all nine categories:

- `banners`
- `rigid_signs`
- `cut_vinyl`
- `digital_print`
- `vehicle_graphics`
- `apparel`
- `promotional`
- `services`
- `custom`

Every category must produce the same authoritative cents-first results through:

1. The shared engine.
2. The SignGuy AI SaaS adapter.
3. The future standalone adapter or a contract-faithful standalone adapter test harness.

Phase 9I cannot close after converting only selected or common calculators.

## 3. Current Architecture Summary

Current authoritative calculator entrypoint:

- `backend/app/services/pricing.py::calculate_pricing`

Current category formula services:

- `backend/app/services/pricing_flat_sqft.py`
- `backend/app/services/pricing_apparel.py`
- `backend/app/services/pricing_promotional.py`
- `backend/app/services/pricing_vehicle_graphics.py`
- `backend/app/services/pricing_services.py`
- `backend/app/services/pricing_custom.py`

Current SaaS orchestration:

- `backend/app/services/order_pricing.py`
- `backend/app/routers/pricing.py`
- `backend/app/routers/quotes.py`
- `backend/app/routers/orders.py`
- `backend/app/services/quote_conversion.py`
- `backend/app/services/quote_revisions.py`

Current snapshot and saved-calculation records:

- `backend/app/services/pricing_snapshot.py`
- `backend/app/services/pricing_snapshot_records.py`
- `backend/app/models/pricing_snapshot_record.py`
- `backend/app/models/pricing_saved_calculation.py`
- `backend/app/services/pricing_saved_calculations.py`

Current UI consumers:

- `frontend/src/pages/PricingCalculatorPage.jsx`
- `frontend/src/components/commerce/LineItemDialog.jsx`
- `frontend/src/components/pricing/CategorySpecificFields.jsx`
- `frontend/src/components/pricing/SavedCalculationLibrary.jsx`

Current money helpers:

- Backend: `backend/app/core/money.py`
- Frontend display/input: `frontend/src/lib/format.js`, `frontend/src/components/forms/MoneyInput.jsx`

## 4. Target Engine Boundary

The pure engine accepts normalized inputs and configuration, performs deterministic Decimal math, and returns cents-first result/evidence objects.

The pure engine owns:

- Category validation that does not require tenant/user/database state.
- Formula dispatch.
- Decimal-safe calculation math.
- Line-level calculation output.
- Document-level calculation output.
- Method rows and explanation evidence.
- Rounding policy version stamping.
- Snapshot evidence shape creation for new normalized snapshots.

The SaaS adapter owns:

- Tenant lookup.
- Permission checks.
- Entitlement checks, if any later phase applies them.
- MongoDB persistence.
- Reference resolution for materials, material profiles, pricing components, saved items, saved calculations, quotes, orders, revisions, and work orders.
- Audit events.
- API request/response envelopes.
- Legacy snapshot readers and migration compatibility.

The standalone adapter owns:

- Local configuration loading.
- Local save/export/import, if authorized later.
- License-shell checks after extraction passes.
- Local UI-specific data entry and formatting.
- No formula changes and no license-conditioned calculation differences.

## 5. Target Contracts

All authoritative Decimal API and serialized values use strings. Authoritative Decimal values must not be serialized as JSON binary floats.

| Contract | Meaning | Authoritative unit | Runtime type | JSON representation | Validation | Rounding behavior | Precision | Example | Legacy mapping | Owner |
|---|---|---|---|---|---|---|---|---|---|---|
| `MoneyCents` | Fixed currency amount | cents | `int` | number integer | finite integer, normally >= 0 unless signed adjustment | no rounding after construction | whole cent | `12500` | `selling_price` dollars -> `selling_price_cents` | engine/shared |
| `CurrencyRateDecimal` | High-precision money rate | explicit unit, e.g. USD/sqft | `Decimal` | string plus unit | finite, non-negative, allowed scale | quantized only at final amount boundary | category-defined scale, default 6 dp | `{"value":"1.234567","unit":"USD_per_sqft"}` | `cost_per_sqft`, `sell_per_sqft`, hourly rates | engine/shared |
| `PercentDecimal` | Precise percentage when basis points are insufficient | percent | `Decimal` | string | finite, bounded by field | applied as Decimal ratio | default 6 dp | `"12.500000"` | `waste_percent`, precise tax rates | engine/shared |
| `BasisPoints` | Standard percentage/rate | 1/100 percent | `int` | number integer | bounded integer, e.g. 0-10000 unless field-specific | no rounding | integer bps | `2500` = 25% | fee/tax/discount rates where precision fits | engine/shared |
| `Quantity` | Count of items | category-specific count | `int` or Decimal string where fractional is allowed | integer or string plus unit | positive, field-specific max | never currency-rounded | count precision | `3` | current `quantity` | engine/shared |
| `Dimension` | One dimension | inches, feet, etc. | `Decimal` | `{"value":"96","unit":"in"}` | positive unless optional | converted with Decimal | default 4 dp | width 96 in | `width_inches`/`height_inches` floats | engine/shared |
| `Area` | Derived or entered area | sqft, sqin | `Decimal` | `{"value":"24.0000","unit":"sqft"}` | non-negative | not currency-rounded | default 4 dp | 24 sqft | `area_sqft_total` float | engine/shared |
| `TimeAmount` | Labor/time basis | minutes or hours | `Decimal` | `{"value":"1.50","unit":"hour"}` | non-negative | not currency-rounded | default 4 dp | 1.5 hours | hourly labor assumptions | engine/shared |
| `WasteFactor` | Waste or yield adjustment | ratio or percent | `Decimal` | string plus unit | non-negative, field bounded | not currency-rounded | default 6 dp | `"0.125000"` | `waste_percent` float | engine/shared |
| `Markup` | Cost multiplier | multiplier | `Decimal` | string | >= 0 | applied before final cents rounding | default 6 dp | `"2.500000"` | `default_markup_multiplier` | engine/shared |
| `Margin` | Profit margin target | bps or Decimal percent | `int` bps or Decimal | integer bps preferred | 0 <= margin < 100% | applied before final cents rounding | bps or 6 dp | `4000` | `target_margin_percent` | engine/shared |
| `CalculationInput` | Normalized line request | mixed explicit units | dataclass/Pydantic-like DTO | object | category-specific schema validation | no money rounding | versioned | category + dimensions + options | current `/pricing/calculate` payload | engine |
| `CategoryConfiguration` | Formula config | cents/rates/bps/units | DTO | object | schema version, required fields by category | no final rounding | versioned | digital print item/order minimums | `pricing_settings.category_defaults` | engine + SaaS adapter |
| `LineCalculationResult` | Authoritative line result | cents plus evidence | DTO | object | selected method amount required on success | final currency converts once to cents | whole cents output | `selling_price_cents` | calculator `selling_price` float | engine |
| `DocumentCalculationInput` | Priced lines plus document rules | cents/rates/bps/units | DTO | object | line results already normalized | document rounding once per documented component | whole cents output | quote/order priced lines | `compute_document_totals_with_pricing_adjustments` input | engine |
| `DocumentCalculationResult` | Document subtotal/adjustments/tax/total | cents | DTO | object | all totals derive from lines/adjustments | no adapter variance | whole cents | Digital Print min adjustment | Quote/Order total fields | engine |
| `CalculationEvidence` | Explanation and formula trace | explicit units | DTO | object | no secrets, no live DB objects | records rounding policy | versioned | breakdown lines and source labels | current `breakdown`, `detail_sections` | engine |
| `SnapshotEvidence` | Historical immutable result evidence | cents-first with legacy fields | DTO | object | schema version required for new snapshots | records rounding version | versioned | `snapshot_schema_version` | embedded legacy snapshot dict | engine + SaaS adapter |
| `SavedCalculation` | Explicit saved historical calculation | cents-first immutable result | DTO/model | object | successful line result only | no recalc unless explicit reuse | versioned | saved calc record | current float+cents saved calculation | SaaS adapter |
| `PortableConfigExport` | Export/importable pricing config | cents/rates/bps/units | DTO | JSON file | schema, category coverage, version | none during import except validation | versioned | exported shop defaults | `pricing_settings` document | SaaS + standalone adapter |

## 6. Rounding Policy

One documented rounding boundary is required.

Target policy:

- Internal formulas use `Decimal`.
- Intermediate results retain required precision.
- Final currency components convert to integer cents once.
- Rounding mode: `ROUND_HALF_UP`.
- Line and document rounding behavior cannot vary by adapter.
- Frontend formatting does not perform authoritative rounding.
- Repeated dollars-to-cents or cents-to-dollars conversions are prohibited.
- Snapshot evidence records `rounding_policy_version`.
- Decimal-string API values record unit and scale.

Recommended rounding policy identifier:

```text
pricing_rounding_v1_round_half_up_final_cents
```

## 7. Phased Migration Plan

Use an additive strangler migration. Each phase can be reviewed and committed independently.

### Phase 9I-J - Contract and type foundation

- Status: implemented and verified on 2026-07-28.
- Scope: Add pure contract primitives and validation helpers without changing existing calculators.
- Likely files: new `backend/pricing_engine/__init__.py`, `backend/pricing_engine/contracts.py`, `backend/pricing_engine/money.py`, `backend/pricing_engine/validation.py`, `backend/tests/test_ec9_phase9ij_engine_contracts.py`.
- Dependencies: Accepted owner decisions in this plan.
- Unchanged: All formulas, routers, UI, snapshots, persistence.
- Data migration: none.
- Legacy compatibility: existing dollar-float responses untouched.
- Feature strategy: contracts unused or adapter-only behind tests.
- Unit tests: money cents, Decimal string validation, unit validation, rounding policy.
- Integration tests: importability from backend app without circular imports.
- Parity fixtures: schema validation only.
- Security/tenant tests: assert engine package has no SaaS imports.
- Snapshot tests: schema-version shape only.
- Exit criteria: contracts import cleanly and reject invalid money/rate/unit shapes.
- Review gate: read-only review of contracts and no behavior changes.
- Commit safety: yes.
- Rollback: remove unused package/files.

Implemented files:

- `backend/pricing_engine/__init__.py`
- `backend/pricing_engine/contracts.py`
- `backend/pricing_engine/money.py`
- `backend/pricing_engine/validation.py`
- `backend/tests/test_ec9_phase9ij_engine_contracts.py`

Implemented contracts and validation foundation:

- Integer-cent `MoneyCents` with nonnegative and signed-adjustment construction paths.
- Decimal-string `CurrencyRateDecimal`, `PercentDecimal`, `Quantity`, `Dimension`, `Area`, `TimeAmount`, `WasteFactor`, and `Markup` contracts.
- Integer `BasisPoints` and `Margin` contracts.
- Explicit dimension, area, time, quantity, currency-rate, and waste-factor unit identifiers.
- Exact nine-category `CategoryId` contract.
- Contract/schema, engine, formula, category-configuration, and rounding-policy metadata.
- Base calculation, category-configuration, line-result, document, snapshot, saved-calculation, portable-config, and calculation-evidence envelopes.
- Pure validation helpers that reject booleans as cents, binary floats at authoritative Decimal boundaries, non-finite values, malformed Decimal strings, unsupported units/categories/versions, excess scale/precision, and negative values where not allowed.
- Named rounding policy `pricing_rounding_v1_round_half_up_final_cents` using `ROUND_HALF_UP` at the final-cents boundary.

Verification:

- Phase 9I-J focused tests: `23 passed`.
- Focused money-policy and existing Phase 9I contract regressions: `32 passed`.
- Backend compile/import validation: passed.
- No calculator formula, production service, route, frontend, persistence model, migration, snapshot record, Quote, Order, Webstore, Wrap Lab, Record Numbering, Control Center, Platform Administration, or licensing behavior changed.

### Phase 9I-K - Versioned parity fixture framework

- Scope: Add shared fixture schema and runner harness for all adapters.
- Likely files: `backend/tests/fixtures/pricing_engine/schema.json`, `backend/tests/fixtures/pricing_engine/*.json`, `backend/tests/pricing_engine_fixture_runner.py`, `backend/tests/test_ec9_phase9ik_parity_fixture_schema.py`.
- Dependencies: Phase 9I-J contracts.
- Unchanged: Calculators, production routes.
- Data migration: none.
- Legacy compatibility: fixture runner maps current legacy output into expected normalized assertions.
- Feature strategy: test-only.
- Unit tests: fixture validation, duplicate fixture ID rejection, expected-result completeness.
- Integration tests: current SaaS calculator adapter reads fixtures.
- Parity fixtures: at least one starter fixture per category before exit; full coverage grows in later phases.
- Security/tenant tests: fixture runner must not require live tenant DB for pure validation.
- Snapshot tests: fixture shape includes expected snapshot evidence.
- Exit criteria: shared fixture files run without copied expectations per adapter.
- Review gate: fixture coverage review.
- Commit safety: yes.
- Rollback: remove fixture harness.

Implemented files:

- `backend/tests/fixtures/pricing_engine/schema.json`
- `backend/tests/fixtures/pricing_engine/banners/banners_normal.json`
- `backend/tests/fixtures/pricing_engine/rigid_signs/rigid_signs_normal.json`
- `backend/tests/fixtures/pricing_engine/cut_vinyl/cut_vinyl_normal.json`
- `backend/tests/fixtures/pricing_engine/digital_print/digital_print_normal.json`
- `backend/tests/fixtures/pricing_engine/vehicle_graphics/vehicle_graphics_normal.json`
- `backend/tests/fixtures/pricing_engine/apparel/apparel_normal.json`
- `backend/tests/fixtures/pricing_engine/promotional/promotional_normal.json`
- `backend/tests/fixtures/pricing_engine/services/services_normal.json`
- `backend/tests/fixtures/pricing_engine/custom/custom_normal.json`
- `backend/tests/pricing_engine_fixture_runner.py`
- `backend/tests/test_ec9_phase9ik_parity_fixture_schema.py`

Verification:

- Fixture schema version: `pricing_fixture_v1`.
- Fixture engine version: `pricing_engine_v1`.
- Formula version: `ec9_current`.
- Rounding policy: `pricing_rounding_v1_round_half_up_final_cents`.
- Starter fixtures: 9 total; all nine categories represented.
- Executed adapter/path: `legacy_saas_calculator_v1` through `app.services.pricing.calculate_pricing`.
- Phase 9I-K focused tests: `29 passed`.
- Phase 9I-J focused tests: `23 passed`.
- Focused money-policy and existing Phase 9I contract regressions: `32 passed`.
- Focused category-output and Banner regressions: `33 passed`.
- Backend compile/import validation: passed.
- No calculator formula, production service, route, frontend, persistence model, migration, snapshot record, Quote, Order, Webstore, Wrap Lab, Record Numbering, Control Center, Platform Administration, standalone adapter, pure engine implementation, data migration, or licensing behavior changed.
- Full all-adapter parity coverage is not complete; only the current legacy/SaaS calculator path executes in Phase 9I-K.

### Phase 9I-L - Cents-first compatibility DTOs around existing calculators

- Scope: Wrap existing calculator outputs into cents-first line-result DTOs while preserving legacy response fields.
- Likely files: `backend/pricing_engine/adapters/legacy_result_adapter.py`, `backend/app/services/pricing_engine_adapter.py`, `backend/tests/test_ec9_phase9il_cents_first_adapter.py`.
- Dependencies: 9I-J/K.
- Unchanged: Formula services and frontend-visible legacy fields.
- Data migration: none.
- Legacy compatibility: legacy `selling_price`, `true_cost`, `breakdown.amount` remain readable.
- Feature strategy: additive response fields, possibly behind a compatibility flag.
- Unit tests: every category maps selling price/true cost/method rows to cents without changing totals.
- Integration tests: `/pricing/calculate` includes normalized result envelope without breaking existing consumers.
- Parity fixtures: all nine categories normal path.
- Security/tenant tests: SaaS adapter continues tenant-scoped settings/reference resolution.
- Snapshot tests: no historical snapshot rewrite.
- Exit criteria: normalized cents fields exist for all successful calculator results.
- Review gate: compare legacy and cents outputs exactly.
- Commit safety: yes.
- Rollback: remove additive fields/adapter calls.

### Phase 9I-M - Saved-calculation normalization

- Scope: Add cents-first saved-calculation contract fields and legacy readers.
- Likely files: `backend/app/models/pricing_saved_calculation.py`, `backend/app/services/pricing_saved_calculations.py`, `backend/app/routers/pricing_saved_calculations.py`, `backend/tests/test_ec9_phase9im_saved_calculation_money_contract.py`, frontend display files only if API field use is required.
- Dependencies: 9I-L.
- Unchanged: saved calculation lifecycle, archive/restore/duplicate/reuse semantics.
- Data migration: additive fields on new saves only; no destructive migration.
- Legacy compatibility: read `selling_price` float and `selling_price_cents` for old records.
- Feature strategy: write both new normalized fields and legacy display fields until compatibility gate.
- Unit tests: successful save requires normalized cents result; failed/unavailable cannot save.
- Integration tests: save/reuse performs fresh backend calculation and transfers only fresh cents result.
- Parity fixtures: saved calculation fixture for every category.
- Security/tenant tests: tenant-scoped CRUD and permission checks unchanged.
- Snapshot tests: saved calculation remains historical, not current transferable price.
- Exit criteria: saved calculations no longer depend on float amount for authority.
- Review gate: saved-calculation immutable snapshot review.
- Commit safety: yes.
- Rollback: keep legacy fields, ignore new normalized fields.

### Phase 9I-N - Snapshot schema normalization and legacy readers

- Scope: Add snapshot schema version, cents-first authoritative fields, Decimal-string rate evidence, and legacy reader helpers.
- Likely files: `backend/pricing_engine/snapshots.py`, `backend/app/services/pricing_snapshot.py`, `backend/app/services/pricing_snapshot_records.py`, `backend/app/models/pricing_snapshot_record.py`, `backend/tests/test_ec9_phase9in_snapshot_normalization.py`, `docs/architecture/pricing_snapshots.md`.
- Dependencies: 9I-L/M.
- Unchanged: existing embedded snapshot fields and historical rows.
- Data migration: none required; future optional additive backfill only by owner decision.
- Legacy compatibility: old snapshots remain readable permanently.
- Feature strategy: dual-write new normalized fields and legacy fields during compatibility window.
- Unit tests: old snapshot reader, new snapshot writer, no rewrite on read.
- Integration tests: Quote/Order create/update/conversion preserves normalized and legacy evidence.
- Parity fixtures: snapshot evidence expectations for all categories.
- Security/tenant tests: snapshot reads remain tenant-scoped.
- Snapshot tests: legacy dollar fields distinguished from authoritative cents fields.
- Exit criteria: new snapshots contain schema version and cents-first evidence.
- Review gate: historical stability review.
- Commit safety: yes.
- Rollback: readers ignore new fields.

### Phase 9I-O - Pure line-level calculator extraction

- Scope: Move or wrap formula dispatch into `backend/pricing_engine/line_engine.py` with no SaaS imports.
- Likely files: `backend/pricing_engine/line_engine.py`, `backend/pricing_engine/categories/*.py`, `backend/pricing_engine/config.py`, `backend/app/services/pricing.py`, `backend/tests/test_ec9_phase9io_line_engine_parity.py`.
- Dependencies: 9I-J through 9I-N.
- Unchanged: formulas, owner-approved defaults, minimums, markups, rounding results.
- Data migration: none.
- Legacy compatibility: SaaS adapter still emits old response envelope where needed.
- Feature strategy: route through adapter while comparing old and new engines.
- Unit tests: all category formulas from fixture suite.
- Integration tests: `/pricing/calculate`, Quote Item, Order Item parity.
- Parity fixtures: complete line-level cases for all nine categories.
- Security/tenant tests: engine package import scan proves no auth/Mongo/FastAPI imports.
- Snapshot tests: new line results build normalized snapshot evidence.
- Exit criteria: current SaaS line calculations are produced by pure engine.
- Review gate: protected formula parity review.
- Commit safety: yes, if adapter fallback remains possible.
- Rollback: switch SaaS adapter back to legacy dispatcher.

### Phase 9I-P - Pure document-level pricing pipeline extraction

- Scope: Extract document totals and adjustments into `backend/pricing_engine/document_engine.py`.
- Likely files: `backend/pricing_engine/document_engine.py`, `backend/app/services/order_pricing.py`, `backend/app/services/commerce_totals.py`, `backend/tests/test_ec9_phase9ip_document_engine_parity.py`.
- Dependencies: 9I-O.
- Unchanged: Quote/Order mutation orchestration, revisions, conversion, stored historical records.
- Data migration: none.
- Legacy compatibility: existing Quote/Order fields remain.
- Feature strategy: adapter calls document engine; legacy helper stays as wrapper until removed.
- Unit tests: line subtotals, Digital Print document minimum, discounts, tax, multi-line and mixed-category docs.
- Integration tests: Quote and Order create/update/delete/reprice recompute totals identically.
- Parity fixtures: document-level fixtures including Digital Print below/at/above minimum.
- Security/tenant tests: document engine cannot access tenant persistence; SaaS adapter enforces tenant before mutation.
- Snapshot tests: document evidence stored without line snapshot rewrites.
- Exit criteria: Quote and Order services orchestrate shared document engine rather than owning formulas.
- Review gate: document minimum and totals review.
- Commit safety: yes.
- Rollback: revert wrapper to legacy helpers.

### Phase 9I-Q - SaaS configuration, tenant, persistence, and permission adapters

- Scope: Formalize SaaS adapter mapping from Mongo settings/references to pure engine config/contracts.
- Likely files: `backend/app/services/pricing_engine_config_adapter.py`, `backend/app/services/pricing_engine_result_adapter.py`, `backend/app/routers/pricing.py`, `backend/app/routers/quotes.py`, `backend/app/routers/orders.py`, targeted tests.
- Dependencies: 9I-O/P.
- Unchanged: permission names, tenant boundaries, record mutation semantics.
- Data migration: none.
- Legacy compatibility: old setting documents mapped to new normalized config in memory.
- Feature strategy: adapter-level compatibility path for legacy settings.
- Unit tests: mapping for all config fields, missing defaults, inactive references.
- Integration tests: tenant-specific settings produce tenant-specific results.
- Parity fixtures: SaaS adapter runs the same engine fixture files.
- Security/tenant tests: cross-tenant material/profile/component/saved item IDs rejected.
- Snapshot tests: settings version and source refs included.
- Exit criteria: app no longer passes raw `pricing_settings` dicts into formulas.
- Review gate: adapter isolation and tenant-boundary review.
- Commit safety: yes.
- Rollback: adapter can map back to legacy dispatcher until 9I-O removal gate.

### Phase 9I-R - Frontend/API boundary conversion

- Scope: Make API responses and frontend transfers consume cents-first authoritative fields.
- Likely files: `frontend/src/pages/PricingCalculatorPage.jsx`, `frontend/src/components/commerce/LineItemDialog.jsx`, `frontend/src/components/pricing/SavedCalculationLibrary.jsx`, `frontend/src/lib/format.js`, `backend/app/routers/pricing.py`, frontend tests.
- Dependencies: 9I-L through 9I-Q.
- Unchanged: UI workflows and formula outputs.
- Data migration: none.
- Legacy compatibility: frontend can display legacy responses during transition but transfers only cents-first fields when present.
- Feature strategy: additive API fields, fallback only for legacy endpoints/tests.
- Unit tests: frontend no longer authoritatively rounds backend selling price floats for transfer.
- Integration tests: calculator, Quote Item, Order Item, saved calculation reuse.
- Parity fixtures: API snapshots from fixture cases.
- Security/tenant tests: permission-blocked calculate/transfer paths unchanged.
- Snapshot tests: transfer snapshots use new normalized evidence.
- Exit criteria: frontend formatting is display-only; backend remains sole authority.
- Review gate: browser/API contract review.
- Commit safety: yes.
- Rollback: keep legacy field fallback.

### Phase 9I-S - Portable configuration export/import

- Scope: Add versioned export/import contracts for pricing configuration without standalone licensing.
- Likely files: `backend/pricing_engine/config_export.py`, `backend/app/services/pricing_config_export.py`, `backend/app/routers/pricing_config_export.py`, tests.
- Dependencies: 9I-Q.
- Unchanged: live settings mutation unless explicit import endpoint is authorized.
- Data migration: none.
- Legacy compatibility: export maps current settings to normalized portable config; import validates before any save.
- Feature strategy: read-only export first; import can be preview-only unless owner authorizes save.
- Unit tests: round-trip validation, invalid config, version mismatch.
- Integration tests: tenant export does not leak other tenant references.
- Parity fixtures: exported config runs same fixtures.
- Security/tenant tests: permission checks for export/import preview.
- Snapshot tests: config version refs in result evidence.
- Exit criteria: portable config can reproduce fixture results without Mongo.
- Review gate: export/import security review.
- Commit safety: yes.
- Rollback: remove endpoints; engine remains unaffected.

### Phase 9I-T - Standalone adapter contract harness

- Scope: Add contract-faithful standalone adapter test harness with local config input and no licensing implementation.
- Likely files: `backend/tests/standalone_pricing_adapter_harness.py`, `backend/tests/test_ec9_phase9it_standalone_adapter_contract.py`, fixture updates.
- Dependencies: 9I-S.
- Unchanged: no desktop app, no license shell, no packaging publish.
- Data migration: none.
- Legacy compatibility: not applicable to runtime data.
- Feature strategy: test harness only.
- Unit tests: standalone harness loads portable config and calls pure engine.
- Integration tests: compare SaaS adapter and standalone harness outputs.
- Parity fixtures: all nine categories must run in both adapters.
- Security/tenant tests: harness has no tenant persistence or network access.
- Snapshot tests: snapshot evidence is equivalent where applicable.
- Exit criteria: standalone-style adapter can run fixtures without SaaS imports.
- Review gate: isolation review.
- Commit safety: yes.
- Rollback: remove harness/tests.

### Phase 9I-U - Final all-category parity and extraction verification

- Scope: Complete all fixture coverage and prove engine/SaaS/standalone harness parity.
- Likely files: fixture files, parity tests, `evidence/EC9_PHASE9I_EXTRACTION_PARITY_REPORT.md`, tracking docs.
- Dependencies: all prior extraction phases.
- Unchanged: no formula changes unless a separate defect is found and reviewed.
- Data migration: none.
- Legacy compatibility: legacy snapshot/read paths remain.
- Feature strategy: freeze compatibility gate.
- Unit tests: all contract and category fixtures.
- Integration tests: SaaS routes, Quote/Order, saved calculations, document pipeline.
- Parity fixtures: all required fixture classes listed below.
- Security/tenant tests: no cross-tenant reference leakage; no engine SaaS imports.
- Snapshot tests: old and new snapshots readable; historical records stable after settings change.
- Exit criteria: all nine categories match across shared engine, SaaS adapter, and standalone harness.
- Review gate: final extraction audit.
- Commit safety: yes.
- Rollback: keep adapter fallback if still present.

### Phase 9I-V - Licensing readiness gate after extraction passes

- Scope: Document readiness for future standalone licensing; do not implement licensing.
- Likely files: `docs/architecture/pricing_engine_extraction.md`, `preflight/EC9_PHASE9I...` tracking update, optional evidence report.
- Dependencies: 9I-U review passed.
- Unchanged: no license checks, no desktop framework, no package publish.
- Data migration: none.
- Legacy compatibility: unchanged.
- Feature strategy: readiness documentation only.
- Unit tests: none beyond extraction verification.
- Integration tests: none beyond extraction verification.
- Parity fixtures: final gate references completed fixture suite.
- Security/tenant tests: confirm licensing remains outside formulas.
- Snapshot tests: confirm no license-conditioned result differences.
- Exit criteria: owner can authorize a later standalone/licensing checkpoint.
- Review gate: owner review.
- Commit safety: yes.
- Rollback: documentation-only.

## 8. Category Migration Matrix

| Category | Current entry point | Formula services | Current config | Current output | Dollar-float fields | Required cents fields | Precise rate fields | Minimum behavior | Options/add-ons | Snapshot behavior | Existing coverage | Required parity cases | Extraction order | Risks |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `banners` | `calculate_pricing` | `pricing_flat_sqft.calc_banners` | shop defaults, category defaults, materials, components | advanced method rows | `selling_price`, `true_cost`, costs, rates | selling, true cost, components, adjustments | sqft cost/sell rates, hourly rates, waste | category/global minimum | hems, grommets, pole pockets, hardware, design, install, rush | embedded + durable snapshot | strong owner tests | 8x3, ft/in, quantity, finishing, comparison, manual | first reference category | protected formula; do not alter selection behavior |
| `rigid_signs` | `calculate_pricing` | `pricing_flat_sqft.calc_rigid_signs` | material/profile, graphic method, category defaults | normalized rows | selling/cost/rate floats | selling/true cost/finishing/hardware/install | sqft rates, waste, markup/margin | category/global minimum | substrate, shape, finish, drill, hardware, design/install | embedded + durable snapshot | category method output tests | min area, double-sided, hardware, manual override | after Banner adapter | generic finalize path aliases |
| `cut_vinyl` | `calculate_pricing` | `pricing_flat_sqft.calc_cut_vinyl` | material/profile, category defaults | normalized rows | selling/cost floats | selling/true cost/finishing/install | sqft rates, waste, complexity factors | `$25` starter item minimum owner decision | colors, weeding, masking, surface, design/install | embedded + durable snapshot | method output tests | below/at/above minimum, masking, manual | after rigid | preserve owner-approved `$25` |
| `digital_print` | `calculate_pricing`; document helper | `pricing_flat_sqft.calc_digital_print`; `order_pricing` | item/order minimum, material/profile, category defaults | normalized rows + document evidence | line selling/cost/minimum context floats | line selling, item minimum, document adjustment, totals | sqft rates, ink/lamination/mounting rates, waste | item minimum in line; order minimum once per document | lamination, mounting, contour cut, piece separation, design/install | line snapshot + Quote/Order document evidence | strong 9I-I tests | item below/at/above, multi-line doc minimum, mixed category | before document engine | avoid reintroducing per-line `$40` floor |
| `vehicle_graphics` | `calculate_pricing` | `pricing_vehicle_graphics.py` | vehicle benchmark/cost-plus defaults | normalized rows | benchmark/cost-plus/selling floats | selected selling, true cost, add-ons | sqft rates, hourly rates, travel/removal rates | method-specific minimums | coverage, laminate, prep, removal, travel, helper | embedded + durable snapshot | method output tests | benchmark available/unavailable, cost-plus, manual | after flat sqft | conditional methods cannot fabricate price |
| `apparel` | `calculate_pricing` | `pricing_apparel.py` | garment tables, decoration methods, setup/add-ons | normalized rows | table/cost-plus/selling floats | selling, setup, decoration, add-ons | per-garment rates, labor/setup rates, markup/margin | apparel minimum | plus size, name/number, specialty finish, rush | embedded + durable snapshot | method output tests | exact table, cost-plus fallback, manual | after vehicle | table vs provisional estimate labeling |
| `promotional` | `calculate_pricing` | `pricing_promotional.py` | saved item tiers, unit cost, flat fee | normalized rows | tier/per-piece/flat selling floats | selling, setup, shipping, add-ons | unit cost if sub-cent, markup/margin | no guessed tier price | exact tier, per-piece, flat fee, setup, decoration | embedded + durable snapshot | method output tests | exact tier, missing tier error, manual, flat fee | after apparel | missing tiers must remain unavailable |
| `services` | `calculate_pricing` | `pricing_services.py` | service rates and presets | normalized rows | hourly/flat/pass-through floats | service total, travel/vendor/permit add-ons | hourly rates, per-unit rates, markup/margin | service minimum | travel, equipment, subcontract, permit, rush | embedded + durable snapshot | method output tests | hourly, flat, pass-through, cost-plus, manual | after promotional | service aliases map to stable IDs |
| `custom` | `calculate_pricing` | `pricing_custom.py` | custom unit price/manual config | unit price x quantity | unit price/selling floats | unit price, total, optional manual cost | markup informational only | configured custom minimum | notes, manual cost, optional markup info | embedded + durable snapshot | method output tests | unit x qty, minimum, manual notes | last line category | must not become auto estimator |

## 9. Parity Fixture Requirements

Fixture files should live under:

```text
backend/tests/fixtures/pricing_engine/
```

Recommended filename pattern:

```text
<category>/<case_id>.json
```

Required fixture shape:

```json
{
  "fixture_schema_version": "pricing_fixture_v1",
  "engine_version": "pricing_engine_v1",
  "formula_version": "ec9_current",
  "category": "digital_print",
  "case_id": "digital_print_document_minimum_below",
  "normalized_inputs": {},
  "normalized_configuration": {},
  "expected_line_results": {},
  "expected_document_results": {},
  "decimal_rate_evidence": [],
  "rounding_evidence": {},
  "minimum_adjustment_evidence": {},
  "expected_validation_errors": [],
  "snapshot_evidence": {},
  "legacy_compatibility": {}
}
```

Required fixture families:

- Normal calculation.
- Below, exactly at, and above minimums.
- Quantity boundaries.
- Decimal rounding boundaries.
- Optional charges and finishing.
- Manual price overrides.
- Multiple lines.
- Mixed categories.
- Document-level Digital Print minimum.
- Discounts and tax.
- Invalid configuration.
- Legacy snapshots.
- Changed defaults with stable historical records.

The same fixture files must run against the pure engine, SaaS adapter, and standalone adapter harness without copying expected values into separate test files.

## 10. Document-Level Engine Plan

The document engine accepts normalized priced lines plus document configuration and returns:

- Line subtotals.
- Category-eligible subtotals.
- Digital Print minimum adjustment.
- Other documented adjustments.
- Discount breakdown.
- Tax breakdown.
- Final total in cents.
- Explanation evidence.
- Calculation and rounding versions.

Quote and Order services must orchestrate this engine rather than own separate formulas.

Tenant lookups, authorization, record mutation, persistence, revision creation, and conversion remain in the SaaS adapter.

## 11. Security, Tenant, And Authority Boundaries

Pure engine:

- No tenant identity.
- No user identity.
- No permissions.
- No persistence.
- No entitlement or license decisions.
- No network calls.

SaaS adapter:

- Requires existing pricing permissions.
- Resolves all references with `tenant_id`.
- Rejects cross-tenant material/profile/component/saved item/saved calculation IDs.
- Persists only through existing Quote/Order/saved-calculation/snapshot paths.
- Records audit events for mutations.
- Keeps manual override reason rules.

Standalone adapter harness:

- Uses local normalized config and fixtures.
- Does not call SaaS APIs.
- Does not perform license checks during formula tests.

## 12. Data Migration Strategy

No destructive migration is planned.

Data strategy:

- Keep current records readable.
- Add normalized fields to new writes.
- Add reader helpers that can interpret legacy embedded snapshots.
- Do not rewrite old snapshots, saved calculations, Quotes, Orders, Quote revisions, Work Orders, invoices, Webstore records, or Wrap Lab records.
- Optional future backfill may create additive normalized evidence only after owner approval and dry-run evidence.

## 13. Scope Control

This plan must not become a rewrite of every commerce module.

Invoices, payments, Webstores, Wrap Lab, Commercial Billing, and AI provider-cost ledgers change only if the calculator contract directly crosses their boundary or an active authoritative-money defect is found in a separately reviewed correction.

Out-of-scope work:

- New pricing formulas.
- Owner-approved price changes.
- Webstore payout or storefront changes.
- Wrap Lab workflow changes.
- Control Center UI.
- Platform Administration.
- Record Numbering.
- AI credits or AI provider metering.
- Stripe.
- Standalone desktop application.
- Licensing implementation.

## 14. Preserved Follow-Ups

Preserve these from Phase 9I-I:

1. Add a visible `Digital Print order minimum adjustment` row to applicable Quote and Order detail surfaces. Place this in Phase 9I-R because it is frontend/API evidence presentation, not formula work.
2. Audit identifier-only Quote and Order item update/delete operations after tenant-scoped authorization lookups. Keep this as security hardening unless extraction work touches those paths directly.
3. Preserve the one-off `tests/test_ec7_inventory.py` duplicate-key setup failure as informational test-reliability evidence.

## 15. Phase 9I Closure Conditions

Phase 9I can close only after:

- All nine categories run through cents-first contracts.
- The pure line engine is isolated from SaaS imports.
- The pure document engine is isolated from SaaS imports.
- SaaS adapter output matches current behavior.
- Standalone harness output matches current behavior.
- Shared fixtures cover every required category and case family.
- Legacy snapshots remain readable.
- New snapshots are schema-versioned and cents-first.
- Saved calculations are normalized without rewriting history.
- Frontend transfers only backend-authoritative cents-first values.
- Security tests prove tenant isolation at every SaaS adapter boundary.
- Licensing remains outside formulas and has not affected results.
- Independent review passes.

## 16. Documentation Verification For This Plan

Read-only sources used while preparing this plan:

- `preflight/EC9_PHASE9I_SHARED_PRICING_CALCULATOR_PREFLIGHT_AND_IMPLEMENTATION_PLAN.md`
- `evidence/EC9_PHASE9I_CLOSURE_REPORT.md`
- `docs/architecture/money_policy.md`
- `docs/architecture/pricing_snapshots.md`
- `backend/app/core/money.py`
- `backend/app/services/pricing.py`
- `backend/app/services/pricing_flat_sqft.py`
- `backend/app/services/order_pricing.py`
- `backend/app/services/pricing_snapshot.py`
- `backend/app/services/pricing_method_registry.py`
- `backend/app/services/pricing_method_outputs.py`
- `backend/app/models/pricing_saved_calculation.py`
- `backend/app/models/pricing_snapshot_record.py`
- `backend/app/models/material_pricing_profile.py`
- `backend/app/models/pricing_component.py`
- `frontend/src/lib/format.js`
- `frontend/src/components/forms/MoneyInput.jsx`

Documentation-only verification required before review:

- `git diff --check`
- `git status --short --branch`
- Confirm dirty tree contains only this plan and tracking documents.

## 17. Implementation Boundary

Phase 9I-J is implemented and verified.

Phase 9I-K is implemented and verified.

No calculator formula changes, production integration, data migration, schema/model migration, frontend changes, licensing work, pure engine implementation, standalone adapter implementation, or production SaaS adapter implementation are included in Phase 9I-K.

Phase 9I remains open.

Phase 9I-L is the next implementation slice under this plan and has not started.
