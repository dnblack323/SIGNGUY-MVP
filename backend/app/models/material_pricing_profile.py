"""EC9 phase 9A — Material Pricing Profile.

Owner decision (2026-02): EC7's `Material` (app/models/material.py) remains the
single canonical physical-material/inventory record. This profile is a
one-to-one, tenant-scoped PRICING extension linked to a canonical Material by
`material_id` — it never duplicates name/SKU/supplier/unit-of-measure/purchase
method/quantity/inventory cost/tenant ownership/archive status, all of which
stay on `Material`. A profile must never become a second inventory record.

Money policy: this is pricing CONFIGURATION (like `starter_defaults.MATERIALS`
and `pricing_settings.category_defaults`), so amounts here are dollar-based
(no `_cents` suffix). The dollars-to-cents boundary is crossed only once,
inside `services/pricing_snapshot.py`, when a profile is used to price a
Quote/Order line item.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import Field

from .base import BaseDoc

PricingUnit = Literal["per_sqft", "per_unit", "per_linear_ft", "per_garment", "other"]
PricingSource = Literal["manual", "starter_default", "imported"]


class MaterialPricingProfile(BaseDoc):
    tenant_id: str
    material_id: str  # canonical FK -> Material.id (EC7). Exactly one profile per (tenant_id, material_id).
    pricing_unit: PricingUnit = "per_sqft"
    normalized_cost_basis: Optional[float] = None   # dollars, normalized to `pricing_unit`
    waste_percent: float = 0.0
    default_markup_multiplier: Optional[float] = None
    default_margin_percent: Optional[float] = None
    suggested_sell_rate: Optional[float] = None      # dollars per `pricing_unit`
    minimum_sell_amount: Optional[float] = None      # dollars
    category_applicability: list[str] = Field(default_factory=list)  # subset of starter_defaults.CATEGORY_IDS
    quantity_tiers: list[dict[str, Any]] = Field(default_factory=list)
    pricing_source: PricingSource = "manual"
    effective_at: Optional[str] = None
    pricing_notes: Optional[str] = None
    last_reviewed_at: Optional[str] = None
    active: bool = True
