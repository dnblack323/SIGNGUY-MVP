# Pricing Snapshots (EC3)

## Purpose

Every committed line item (Quote or Order) stores a `pricing_snapshot` object containing the calculation basis for its price at commit time. Historical Quotes and Orders MUST NOT silently reprice when shop pricing defaults change.

## Shape

Manual entry (`services/pricing_snapshot.build_manual_snapshot`):
- `source: "manual"`, `pricing_method: "manual"`, `unit_price_cents`, `quantity`, override reason/actor/email, `captured_at`.

Calculator entry (`services/pricing_snapshot.build_calculated_snapshot`):
- `source: "calculator"`, `pricing_method` (from calc result), `calculator_version` (from `starter_defaults.STARTER_DEFAULT_VERSION`), `category`, `quantity`, `width_inches`, `height_inches`, `area_sqft_total`, `material_key`, `material_cost_dollars`, `labor_cost_dollars`, `design_cost_dollars`, `install_cost_dollars`, `overhead_cost_dollars`, `true_cost_dollars`, `calculated_unit_price_cents`, `override_unit_price_cents`, override metadata, `captured_at`.

Override (`services/pricing_snapshot.apply_override`):
- Preserves the original calculated cents, adds `override_unit_price_cents`, `override_reason`, actor, `override_applied_at`.

## Rules

- Snapshots are stored on the line item document, not in a separate collection (kept close to the record; can move later if reporting needs demand).
- Snapshots never include secrets or full pricing_settings dumps — only relevant inputs.
- A change to shop pricing defaults never mutates historical snapshots.

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
