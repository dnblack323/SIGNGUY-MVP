# Order Items Module (EC3)

**Owner checkpoint:** EC3.

`backend/app/models/order.py::OrderItem` is the permanent rich order-line schema.

## Field groups delivered in EC3

- **Identity:** id, tenant_id, order_id, position, category, product_type, description, sku
- **Quantity/Dimensions:** quantity, unit_of_measure, width_inches, height_inches, depth_inches
- **Materials:** material_key
- **Pricing (integer cents):** unit_price_cents, discount_cents, tax_cents, line_subtotal_cents (derived), line_total_cents (derived)
- **Pricing snapshot:** pricing_snapshot (dict)
- **Manual override:** manual_override_reason, manual_override_actor_user_id, manual_override_actor_email, manual_override_at
- **Artwork/Proof foundation:** artwork_status, proof_status, customer_supplied_artwork, design_required
- **Workflow:** production_required, production_required_override_reason, production_required_override_actor_user_id, production_required_override_at, notes

## Guardrails

- `unit_price_cents` change → requires `manual_override_reason`.
- `production_required` override → requires `production_required_override_reason`.
- Line totals always backend-derived via `services/commerce_totals.compute_line_totals`.
- Category defaults `production_required` via `services/order_item_rules.default_production_required`.

## Deferred to owning checkpoints

- Assigned team/user, department_route → Team & Workflow (EC6).
- Install / packaging notes surfaces → Wrap Lab / production board (EC5/EC8).
- Proof / artwork approvals → EC4 shared Approvals system.
