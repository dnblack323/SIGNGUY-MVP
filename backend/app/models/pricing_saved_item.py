"""EC9 phase 9A — Pricing Saved Item (reusable saved product / configuration).

Owner decision (2026-02): a tenant-scoped, reusable saved-item / product-
template system for commonly sold products and configurations (Promotional
Items, common products, saved calculator configurations). Saved items MUST
reference canonical materials by `material_id` (EC7 `Material.id`) — they
never copy inventory quantities and never create a duplicate material
ownership record. `saved_config` stores the calculator INPUT configuration
(category, dimensions, quantity, options) — not a priced/committed result;
applying a saved item to a Quote/Order Item still goes through
`services.pricing.calculate_pricing()` and the existing snapshot builders.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import Field

from .base import BaseDoc

CreatedFrom = Literal["new", "variation"]


class PricingSavedItem(BaseDoc):
    tenant_id: str
    name: str
    category: str  # one of starter_defaults.CATEGORY_IDS
    material_refs: list[str] = Field(default_factory=list)       # EC7 Material.id references (no copied data)
    pricing_component_refs: list[str] = Field(default_factory=list)  # PricingComponent.id references
    quantity_tiers: list[dict[str, Any]] = Field(default_factory=list)
    default_production_assumptions: dict[str, Any] = Field(default_factory=dict)
    default_pricing_method: Optional[str] = None
    default_notes: Optional[str] = None
    saved_config: dict[str, Any] = Field(default_factory=dict)  # calculator input snapshot (not a priced result)
    active: bool = True
    quick_select: bool = False
    variation_of_id: Optional[str] = None  # set when created_from == "variation"
    created_from: CreatedFrom = "new"
