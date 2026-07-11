# Production Data Visibility (EC5)

Production-only staff must not automatically see:
- `unit_price_cents` on Work Order Item snapshots — omitted from `/api/work-orders/{id}/summary` unless the caller has `invoice:read`.
- Invoice / Payment records — separate permission gate (`invoice:read`, `payment:read`).
- Private customer notes — the Work Order snapshot only carries production-visible fields captured from the Order Item.
- Margin / pricing calculations.

The router source for the pricing gate is `routers/work_orders.get_summary`:
```
include_pricing = "invoice:read" in (user.get("permissions") or [])
```
Backend enforcement is authoritative. Frontend surfaces the same by reading `permissions` from `/api/auth/me`.
