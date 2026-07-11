# Order Item Rules — production_required (EC3)

`backend/app/services/order_item_rules.py`.

## Rule

Every Order Item carries an explicit boolean `production_required`. Work Orders snapshot ONLY items where `production_required=True`.

## Category defaults

Physical production categories (default True): `rigid_signs, banners, cut_vinyl, digital_print, vehicle_graphics, apparel, custom`.
Non-production categories (default False): `services, promotional`.
Unknown / null categories → default True (safe: keep item on work orders until an operator overrides).

## Override

Setting `production_required` to a different value on an existing item requires `production_required_override_reason`. Actor + timestamp are recorded server-side and audited.

## Location of the rule

Backend authority via `services/order_item_rules.default_production_required(category)`. Frontend labels do NOT drive the rule.
