"""EC9 phase 9A — Pricing Component (non-inventory commercial charge/fee).

Owner decision (2026-02): physical, stocked, purchased, reordered, supplier-
linked, quantity-tracked items (materials AND hardware/accessories such as
grommets, stakes, brackets, frames, mounting hardware, packaging, fasteners)
are owned exclusively by EC7's `Material`/Inventory/Supplier/Purchasing
system. A `PricingComponent` is the opposite: a reusable, tenant-scoped,
NON-inventory commercial charge or fee definition (setup fee, design fee,
file cleanup, permit fee, outsourced service, shipping/pass-through,
installation minimum, rush charge, personalization fee, decoration fee,
relaunch fee, etc.). Pricing components are never stock-tracked and never
create/reference an inventory or supplier record.

Money policy: dollar-based configuration (no `_cents` suffix) — mirrors
`starter_defaults.CATEGORY_DEFAULTS` fee fields (e.g. `basic_setup_fee`,
`file_prep_fee`). This model formalizes those ad hoc per-category fee fields
into a reusable, named catalog usable across categories (wired into the
calculator in later EC9 phases — this phase only establishes the model).
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import Field

from .base import BaseDoc

ChargeType = Literal[
    "setup_fee", "design_fee", "file_cleanup", "permit_fee", "outsourced_service",
    "pass_through", "install_minimum", "rush_charge", "personalization_fee",
    "decoration_fee", "relaunch_fee", "other",
]


class PricingComponent(BaseDoc):
    tenant_id: str
    key: str
    name: str
    charge_type: ChargeType = "other"
    amount: Optional[float] = None    # flat dollar amount, if applicable
    percent: Optional[float] = None   # percentage-of-base amount, if applicable
    category_applicability: list[str] = Field(default_factory=list)  # subset of starter_defaults.CATEGORY_IDS; empty = all
    notes: Optional[str] = None
    active: bool = True
