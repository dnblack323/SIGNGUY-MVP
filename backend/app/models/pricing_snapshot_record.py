"""EC9 Phase 9G — Immutable Pricing Snapshot records.

A `PricingSnapshotRecord` is an APPEND-ONLY historical record explaining
exactly how a Quote Line Item / Order Item price was derived at a specific
moment in time — independent of the live Material / MaterialPricingProfile /
PricingSavedItem / PricingComponent / Pricing Foundation defaults records,
which may all change later without affecting this record's stored values.

This is a SEPARATE collection from the pre-existing embedded `pricing_snapshot`
dict already stored inline on QuoteLineItem/OrderItem (Phase 9B/9F,
`services/pricing_snapshot.py`) — that embedded dict is unchanged and is the
SOURCE this record is built from (see `services/pricing_snapshot_records.py`).
This collection adds durable, queryable lineage (active/superseded/etc.) that
survives independent of the line item, plus a stable id for the explain/
compare endpoints and future EC16/EC17 advisory linkage.

Only `status` / `status_changed_at` / `superseded_by_snapshot_id` are ever
updated after insert (lineage metadata). Every other field is written once at
creation and never mutated.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import Field

from .base import BaseDoc

SnapshotStatus = Literal["active", "superseded", "historical", "candidate", "accepted", "rejected"]
SnapshotSourceType = Literal["quote_line_item", "order_item"]


class PricingSnapshotRecord(BaseDoc):
    tenant_id: str

    # What this snapshot explains
    source_type: SnapshotSourceType
    source_id: str  # quote_line_item.id or order_item.id
    quote_id: Optional[str] = None
    order_id: Optional[str] = None
    order_item_id: Optional[str] = None  # explicit even when == source_id (spec §3)

    category: Optional[str] = None
    item_name: Optional[str] = None
    description: Optional[str] = None
    quantity: int = 1
    category_inputs: dict[str, Any] = Field(default_factory=dict)

    # Canonical references + frozen values at calculation time (EC7 Material /
    # Phase 9A profiles/components/saved items — never re-read from live docs)
    material_ids: list[str] = Field(default_factory=list)
    material_profile_ids: list[str] = Field(default_factory=list)
    material_values_used: dict[str, Any] = Field(default_factory=dict)
    saved_item_id: Optional[str] = None
    saved_item_values_used: dict[str, Any] = Field(default_factory=dict)
    pricing_component_ids: list[str] = Field(default_factory=list)
    pricing_component_values_used: list[dict[str, Any]] = Field(default_factory=list)

    # Pricing Foundation basis in effect at calculation time
    shop_defaults_used: dict[str, Any] = Field(default_factory=dict)
    category_defaults_used: dict[str, Any] = Field(default_factory=dict)
    formula_version: Optional[str] = None
    starter_default_version: Optional[str] = None
    pricing_foundation_effective_at: Optional[str] = None

    # Price + cost breakdown — integer cents (EC1 Money Policy)
    suggested_price_cents: Optional[int] = None
    manual_price_cents: Optional[int] = None
    selected_final_price_cents: int = 0
    selected_price_source: str = "manual"  # "suggested" | "manual"
    cost_breakdown: list[dict[str, Any]] = Field(default_factory=list)
    labor_breakdown_cents: dict[str, Any] = Field(default_factory=dict)
    overhead_cost_cents: Optional[int] = None
    minimum_applied: bool = False
    discount_cents: int = 0
    rush_adjustment_applied: bool = False
    estimated_profit_cents: Optional[int] = None
    estimated_margin_percent: Optional[float] = None

    # Explainability
    source_labels: dict[str, Any] = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list)
    calculation_warnings: list[str] = Field(default_factory=list)

    # Accountability
    calculated_by_user_id: Optional[str] = None
    price_selected_by_user_id: Optional[str] = None
    recalculated_at: Optional[str] = None

    # Lineage + status (the ONLY fields ever updated after insert)
    previous_snapshot_id: Optional[str] = None
    superseded_by_snapshot_id: Optional[str] = None
    status: SnapshotStatus = "active"
    status_changed_at: Optional[str] = None
