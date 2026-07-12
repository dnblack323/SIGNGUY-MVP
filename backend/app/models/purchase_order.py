"""EC7 phase 7b — Purchase Orders + Lines + ReceivingRecords.

All money values are integer cents. Totals are backend-derived — never trust
client-supplied totals. `receiving_records` are keyed uniquely on
`idempotency_key` per master plan (replay never doubles receipt).
"""
from __future__ import annotations
from typing import Any, Literal, Optional
from pydantic import Field
from .base import BaseDoc


PurchaseOrderStatus = Literal[
    "draft", "submitted", "acknowledged", "partially_received",
    "received", "cancelled",
]


class PurchaseOrderLine(BaseDoc):
    tenant_id: str
    purchase_order_id: str
    position: int = 0

    # Source references (all optional so manual POs still work)
    material_id: Optional[str] = None
    supplier_product_id: Optional[str] = None
    supplier_warehouse_id: Optional[str] = None
    order_id: Optional[str] = None                # linked customer Order
    order_item_id: Optional[str] = None           # linked Order Item

    # Snapshot of supplier product at time of PO
    supplier_sku: Optional[str] = None
    description: str
    manufacturer: Optional[str] = None
    brand: Optional[str] = None
    variant: dict[str, Any] = Field(default_factory=dict)

    # Quantities
    quantity_ordered: float
    quantity_received: float = 0.0
    unit_of_measure: str = "each"
    package_qty: int = 1

    # Cost snapshot (integer cents)
    unit_price_cents: int = 0
    line_extended_cents: int = 0                  # unit_price * quantity_ordered
    line_notes: Optional[str] = None


class PurchaseOrder(BaseDoc):
    tenant_id: str
    number: int                                   # sequential per-tenant PO number
    vendor_id: str
    vendor_snapshot: dict[str, Any] = Field(default_factory=dict)

    status: PurchaseOrderStatus = "draft"
    created_by_user_id: str
    submitted_at: Optional[str] = None
    acknowledged_at: Optional[str] = None
    cancelled_at: Optional[str] = None
    cancelled_reason: Optional[str] = None

    # Delivery target (default main shop, but can be overridden per PO)
    ship_to_location_id: Optional[str] = None
    expected_arrival_at: Optional[str] = None

    # Backend-derived totals (integer cents)
    subtotal_cents: int = 0
    shipping_cents: int = 0
    handling_cents: int = 0
    tax_cents: int = 0
    total_cents: int = 0

    # Warehouse split summary
    warehouse_splits: list[dict[str, Any]] = Field(default_factory=list)

    # Supplier submission linkage
    supplier_order_log_ids: list[str] = Field(default_factory=list)
    supplier_order_id: Optional[str] = None
    tracking_number: Optional[str] = None
    tracking_status: Optional[str] = None

    # Provenance for the recommendation / cart flow
    source_recommendation_key: Optional[str] = None
    source_priority: Optional[str] = None
    notes: Optional[str] = None


class ReceivingRecord(BaseDoc):
    """Immutable record of a single receiving action on a PO.

    `idempotency_key` is REQUIRED and UNIQUE per master plan §7 — replaying the
    same key is a no-op and returns the existing record.
    """
    tenant_id: str
    purchase_order_id: str
    idempotency_key: str
    received_by_user_id: str
    received_at: str
    lines: list[dict[str, Any]] = Field(default_factory=list)
    # Each entry: {po_line_id, quantity, location_id, inventory_movement_id, material_cost_history_id}
    notes: Optional[str] = None
