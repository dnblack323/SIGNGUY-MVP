from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import Field

from .base import BaseDoc

OrderStatus = Literal[
    "draft", "confirmed", "in_production", "ready", "completed", "cancelled", "archived"
]

OrderSource = Literal[
    "manual", "quote", "webstore", "wrap_lab", "email", "facebook", "legacy_unknown"
]


class OrderItem(BaseDoc):
    tenant_id: str
    order_id: str
    position: int = 0

    # Identity / classification
    category: Optional[str] = None
    product_type: Optional[str] = None
    description: str
    sku: Optional[str] = None

    # Dimensions / quantity
    quantity: int = 1
    unit_of_measure: str = "each"
    width_inches: Optional[float] = None
    height_inches: Optional[float] = None
    depth_inches: Optional[float] = None

    # Materials / production hints (kept minimal in EC3; extended later)
    material_key: Optional[str] = None

    # Pricing (backend-derived commerce cents)
    unit_price_cents: int = 0
    discount_cents: int = 0
    tax_cents: int = 0
    line_subtotal_cents: int = 0
    line_total_cents: int = 0

    # Pricing snapshot + manual override metadata
    pricing_snapshot: dict[str, Any] = Field(default_factory=dict)
    previous_pricing_snapshot: Optional[dict[str, Any]] = None  # preserved on accepted recalculation
    manual_override_reason: Optional[str] = None
    manual_override_actor_user_id: Optional[str] = None
    manual_override_actor_email: Optional[str] = None
    manual_override_at: Optional[str] = None

    # EC9 Phase 9F — Quote/Order/Order Item pricing integration (additive).
    item_name: Optional[str] = None
    category_inputs: dict[str, Any] = Field(default_factory=dict)
    material_profile_id: Optional[str] = None
    pricing_component_ids: list[str] = Field(default_factory=list)
    saved_item_id: Optional[str] = None
    suggested_price_cents: Optional[int] = None
    manual_price_cents: Optional[int] = None
    selected_price_source: str = "manual"          # "suggested" | "manual"
    pricing_status: str = "manual"                 # "manual" | "calculated"
    estimated_cost_cents: Optional[int] = None
    estimated_profit_cents: Optional[int] = None
    estimated_margin_percent: Optional[float] = None
    calculation_warnings: list[str] = Field(default_factory=list)
    source_labels: dict[str, Any] = Field(default_factory=dict)
    last_recalculated_at: Optional[str] = None
    price_selected_by_user_id: Optional[str] = None

    # Artwork / proof workflow (foundation only in EC3)
    artwork_status: Optional[str] = None
    proof_status: Optional[str] = None
    customer_supplied_artwork: bool = False
    design_required: bool = False

    # Workflow
    production_required: Optional[bool] = None
    production_required_override_reason: Optional[str] = None
    production_required_override_actor_user_id: Optional[str] = None
    production_required_override_at: Optional[str] = None
    notes: Optional[str] = None

    # EC10 Phase 10A — reserved reference to a future Decision Room (EC10
    # Phase 10D). Not implemented/enforced yet; reference only.
    decision_room_id: Optional[str] = None


class Order(BaseDoc):
    tenant_id: str
    number: int  # sequential per tenant
    customer_id: str

    # Canonical source classification is assigned only by trusted backend flows.
    order_source: OrderSource = "manual"
    order_source_record_type: Optional[str] = None
    order_source_record_id: Optional[str] = None

    # Source linkage (EC3 keeps backward-compatible `quote_id`)
    quote_id: Optional[str] = None
    source_quote_id: Optional[str] = None
    source_quote_revision: Optional[int] = None

    job_name: str
    title: Optional[str] = None                 # explicit title (EC3)
    description: Optional[str] = None
    notes: Optional[str] = None                 # legacy MVP note
    notes_internal: Optional[str] = None
    notes_customer: Optional[str] = None

    # Backend-derived totals (integer cents) — recomputed on every item write
    subtotal_cents: int = 0
    discount_cents: int = 0
    tax_cents: int = 0
    total_cents: int = 0

    # EC4 will own these fields — kept as zero in EC3 for shape stability
    amount_invoiced_cents: int = 0
    amount_paid_cents: int = 0
    balance_cents: int = 0

    due_date: Optional[str] = None
    status: OrderStatus = "draft"
    archived_at: Optional[str] = None
    created_by: str

    # EC10 Phase 10A — reserved reference to a future Decision Room (EC10
    # Phase 10D). Not implemented/enforced yet; reference only.
    decision_room_id: Optional[str] = None
