"""EC9 Phase 9G — Provider-neutral advisory contracts (§8-§12).

These models define STORAGE and CONTRACT SHAPE ONLY for future AI/historical/
market pricing advisory features (EC16 Shared AI Gateway, EC17 Studio AI
Tools). No live AI, web, or market-data provider is called anywhere in this
phase — every `AdvisoryResponseItem` created by `services/pricing_advisory.py`
has `status="unavailable"` until a future checkpoint wires in a real
provider. No provider-specific model/API names appear here by design.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from .base import BaseDoc

AdvisoryType = Literal[
    "ai_pricing_analysis", "historical_pricing_comparison", "local_market_comparison",
    "regional_market_comparison", "target_margin_analysis", "cost_risk_analysis",
    "underpricing_warning", "overpricing_warning", "price_confidence_analysis",
]
AdvisoryResponseStatus = Literal[
    "unavailable", "not_requested", "pending", "completed", "partial", "failed", "stale",
    "accepted", "rejected",
]


class AdvisoryResponseItem(BaseModel):
    advisory_type: str
    status: AdvisoryResponseStatus = "unavailable"
    source_type: str = "none"  # provider-neutral; "none" until EC16/EC17 wires a real source
    recommended_price_range_cents: Optional[list[int]] = None
    confidence: Optional[str] = None  # "low" | "medium" | "high"
    explanation: Optional[str] = None
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    comparable_price_range_cents: Optional[list[int]] = None
    historical_range_cents: Optional[list[int]] = None
    local_market_range_cents: Optional[list[int]] = None
    regional_market_range_cents: Optional[list[int]] = None
    target_margin_result: Optional[dict[str, Any]] = None
    cost_risk_flags: list[str] = Field(default_factory=list)
    evidence_references: list[str] = Field(default_factory=list)
    generated_at: Optional[str] = None
    stale_after: Optional[str] = None
    user_decision: Optional[str] = None  # "accepted" | "rejected" | None
    user_notes: Optional[str] = None
    decided_at: Optional[str] = None


class AdvisoryRequest(BaseDoc):
    tenant_id: str
    user_id: str
    category: Optional[str] = None
    item_description: Optional[str] = None
    quantity: Optional[int] = None
    calculator_inputs: dict[str, Any] = Field(default_factory=dict)
    material_summary: dict[str, Any] = Field(default_factory=dict)
    component_summary: list[dict[str, Any]] = Field(default_factory=list)
    current_suggested_price_cents: Optional[int] = None
    manual_price_cents: Optional[int] = None
    selected_final_price_cents: Optional[int] = None
    estimated_cost_cents: Optional[int] = None
    target_margin_percent: Optional[float] = None
    historical_snapshot_id: Optional[str] = None
    geographic_market_scope: Optional[str] = None
    owner_notes: Optional[str] = None
    requested_advisory_types: list[str] = Field(default_factory=list)
    data_consent: bool = False
    request_timestamp: Optional[str] = None
    responses: list[AdvisoryResponseItem] = Field(default_factory=list)
    overall_status: str = "not_requested"
