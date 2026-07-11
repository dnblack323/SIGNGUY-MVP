"""EC3 — Quote Line Item model.

First-class stored records (per EC3 preflight) so that quote revisions and
audit trails can reference stable IDs.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import Field

from .base import BaseDoc


class QuoteLineItem(BaseDoc):
    tenant_id: str
    quote_id: str
    revision_number: int = 1  # revision this line belongs to (default 1)
    position: int = 0

    # Identity + classification
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
    manual_override_reason: Optional[str] = None
    manual_override_actor_user_id: Optional[str] = None
    manual_override_actor_email: Optional[str] = None
    manual_override_at: Optional[str] = None

    # Workflow
    production_required: Optional[bool] = None
    notes: Optional[str] = None
