# Pricing Snapshots (EC3)

## Purpose

Every committed line item (Quote or Order) stores a `pricing_snapshot` object containing the calculation basis for its price at commit time. Historical Quotes and Orders MUST NOT silently reprice when shop pricing defaults change.

## Shape

Manual entry (`services/pricing_snapshot.build_manual_snapshot`):
- `source: "manual"`, `pricing_method: "manual"`, `unit_price_cents`, `quantity`, override reason/actor/email, `captured_at`.

Calculator entry (`services/pricing_snapshot.build_calculated_snapshot`):
- `source: "calculator"`, `pricing_method` (from calc result), `calculator_version` (from `starter_defaults.STARTER_DEFAULT_VERSION`), `category`, `quantity`, `width_inches`, `height_inches`, `area_sqft_total`, `material_key`, `material_cost_dollars`, `labor_cost_dollars`, `design_cost_dollars`, `install_cost_dollars`, `overhead_cost_dollars`, `true_cost_dollars`, `calculated_unit_price_cents`, `override_unit_price_cents`, override metadata, `captured_at`.
- Digital Print calculator snapshots also preserve line-level item-minimum evidence and document-order-minimum context when present: `minimum_policy`, `minimum_scope`, `pre_minimum_selling_price`, `item_minimum`, `order_minimum`, `item_minimum_total`, `order_minimum_total`, `minimum_charge_applied`, `minimum_adjustment`, and `minimum_applied_reason`. The standalone calculator does not apply the document order-minimum floor.

Override (`services/pricing_snapshot.apply_override`):
- Preserves the original calculated cents, adds `override_unit_price_cents`, `override_reason`, actor, `override_applied_at`.

## Rules

- Snapshots are stored on the line item document, not in a separate collection (kept close to the record; can move later if reporting needs demand).
- Snapshots never include secrets or full pricing_settings dumps — only relevant inputs.
- A change to shop pricing defaults never mutates historical snapshots.
- Digital Print line snapshots are historical evidence only. The once-per-document Digital Print order-minimum adjustment is stored on Quote/Order totals as `digital_print_minimum` / `digital_print_order_minimum_adjustment_cents`, using stored line snapshots and line subtotals rather than live defaults. It is not a hidden trigger to recalculate older line items.

## Direct Consumer Contracts (EC9 Phase 9I-H)

Downstream consumers may display or summarize stored pricing evidence, but they
must not recalculate or rewrite historical pricing during read-only consumption.

- Work Order Summary reads `work_orders.items_snapshot` and may show snapshot
  unit prices only when the current user has pricing visibility.
- Reporting reads issued invoices, stored Order cost evidence, payments,
  refunds, expenses, and report datasets. It must not call calculator methods
  or create pricing settings while producing read-only reports.
- Webstore reports read `webstore_buyer_orders` and
  `webstore_ledger_entries`; Webstore storefront, payout, and operational
  pricing changes remain outside this phase.
- Wrap Lab reports and packets read stored Wrap Lab project and packet values;
  Wrap Lab pricing consumers remain outside this phase.

Any future Webstore, Wrap Lab, customer-portal, or reporting consumer that needs
fresh pricing must enter through an explicitly authorized pricing workflow and
must not treat historical snapshots as current transferable prices.

## Cents-First Snapshot Contract (EC9 Phase 9I-N)

New calculated embedded snapshots and immutable `pricing_snapshot_records` now
dual-write the additive schema version
`pricing_snapshot_money_contract_9in_v1` in `pricing_snapshot_schema_version`.
The one canonical normalized calculator field is `pricing_engine_result`.

New calculated snapshot writes must use the Phase 9I-L compatibility envelope:
`pricing_engine_result.status` must be `success`, and
`pricing_engine_result.selling_price_cents` must be a non-boolean integer. The
snapshot writers copy cents from that normalized result instead of deriving
authoritative cents from legacy dollar floats. Legacy display fields remain
present during the compatibility window.

Manual snapshots do not fabricate calculator evidence. They store
`pricing_snapshot_schema_version`, preserve existing manual source/reason/actor
fields, set `pricing_engine_result` to `None`, and treat validated integer
`unit_price_cents` as the manual authority.

Legacy readers are deterministic and non-mutating:
- normalized stored `pricing_engine_result`;
- then valid stored integer cents;
- then read-only legacy dollar adaptation using `Decimal(str(value))` and the
  `pricing_rounding_v1_round_half_up_final_cents` policy.

Reading old embedded snapshots or old immutable records never updates MongoDB,
changes `updated_at`, writes audit events, re-reads current pricing settings,
or backfills normalized fields. Contradictory legacy dollar evidence produces a
compatibility warning while preserving trustworthy integer cents.

Quote and Order create/update/reprice, quote revisions, Quote-to-Order
conversion, active/superseded snapshot lineage, and Digital Print item/document
minimum evidence continue to preserve historical pricing evidence without
recalculation. Phase 9I-N does not implement frontend cents-first consumption,
the visible Digital Print adjustment row, formula extraction, data migration,
or historical backfill.
