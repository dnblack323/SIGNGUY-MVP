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
