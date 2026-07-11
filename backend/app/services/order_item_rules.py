"""EC3 — production_required rule.

Derives whether an Order Item requires physical production work (and therefore
belongs on a Work Order). Categories not requiring production include pass-through
services, promotional pass-throughs, and other non-fabricated line items.

Rule reference: SIGNGUY_AI_FINAL_CONSOLIDATED_MASTER_BUILD_PLAN.md §7A.19.
"""
from __future__ import annotations

from typing import Optional

# Categories that produce a physical fabricated item and require production work.
PHYSICAL_PRODUCTION_CATEGORIES: set[str] = {
    "rigid_signs",
    "banners",
    "cut_vinyl",
    "digital_print",
    "vehicle_graphics",
    "apparel",
    "custom",
}

# Categories explicitly excluded from production (pass-through, services).
NON_PRODUCTION_CATEGORIES: set[str] = {
    "services",
    "promotional",
}


def default_production_required(category: Optional[str]) -> bool:
    """Return the default `production_required` value for an item category.

    - Physical production categories → True.
    - Explicit non-production categories → False.
    - Unknown / None → True (safe default: keep item on the work order until
      the operator explicitly overrides).
    """
    if category is None:
        return True
    if category in NON_PRODUCTION_CATEGORIES:
        return False
    if category in PHYSICAL_PRODUCTION_CATEGORIES:
        return True
    return True
