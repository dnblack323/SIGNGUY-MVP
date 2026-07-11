# Work Order Snapshots + Versioning + Transitions + Summary (EC5)

## Snapshots
Each Work Order embeds `items_snapshot: list[dict]` — a denormalized copy of only the Order Items where `production_required=true` at snapshot time. Fields captured: source `order_item_id`, description, quantity, category, product_type, dimensions, unit_of_measure, material_key, notes. Once a Work Order is released, the snapshot content is immutable via router policy (`PATCH` accepts only production_instructions/internal_notes/priority/due_date/department).

## Versioning
`WorkOrder.version` starts at 1, `current_version=True`. `POST /api/work-orders/{id}/regenerate` (reason required) creates a NEW row with `version += 1, superseded_from = <old_id>` and marks the old row `production_status="superseded", current_version=False, superseded_by=<new_id>`. Prior versions remain readable.

## Duplicate active guard
`POST /api/work-orders` for an Order that already has a `current_version=True` Work Order returns the existing row with `already_exists=true` — no duplicate active work orders per Order.

## Transitions
Central `ALLOWED_TRANSITIONS` map in `services/work_order_service.py`. `blocked` and `cancelled` require a reason. Order coordination is a safe subset — `released→order.confirmed, in_progress→order.in_production, ready→order.ready, completed→order.completed`. Financial state is never touched by production transitions.

## Summary
`GET /api/work-orders/{id}/summary` returns a printable JSON with production-only fields. `unit_price_cents` is included ONLY when the caller carries `invoice:read`. Otherwise the summary is safe for the production floor.

## Print / PDF
EC5 ships the tenant-safe JSON summary. The full PDF renderer belongs to EC6 Asset Library. The frontend Work Order Detail can print the browser page.

## Data compatibility
`effective_status(raw)` translates legacy `not_started→released` / `on_hold→blocked` on read. No destructive migration.
