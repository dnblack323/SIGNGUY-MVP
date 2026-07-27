"""EC9 Phase 9I-G - tenant-scoped saved pricing calculations.

Saved calculations are historical snapshots of successful calculator results.
Metadata can change, but the stored inputs and result payload are never
rewritten after creation.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import Field

from .base import BaseDoc

SavedCalculationSource = Literal["pricing_calculator", "quote_item", "order_item"]


class PricingSavedCalculation(BaseDoc):
    tenant_id: str
    name: str
    notes: Optional[str] = None
    category: str

    calculation_inputs: dict[str, Any] = Field(default_factory=dict)
    selling_price: float
    selling_price_cents: int
    canonical_method_id: Optional[str] = None
    selected_method_id: Optional[str] = None
    pricing_method_results: list[dict[str, Any]] = Field(default_factory=list)
    method_availability: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[Any] = Field(default_factory=list)
    errors: list[Any] = Field(default_factory=list)
    breakdown: list[dict[str, Any]] = Field(default_factory=list)
    detail_sections: list[dict[str, Any]] = Field(default_factory=list)
    calculation_result: dict[str, Any] = Field(default_factory=dict)
    comparison_result: Optional[dict[str, Any]] = None
    pricing_reproducibility_ref: dict[str, Any] = Field(default_factory=dict)

    source_context: SavedCalculationSource = "pricing_calculator"
    created_by_user_id: str
    created_by_email: Optional[str] = None
    updated_by_user_id: Optional[str] = None

    archived: bool = False
    archived_at: Optional[str] = None
    restored_at: Optional[str] = None
    duplicated_from_id: Optional[str] = None
