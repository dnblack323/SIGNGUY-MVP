"""EC7 phase 7b — Supplier normalized catalog + warehouses + order log.

The `supplier_products` collection stores the normalized rows loaded by any
supplier connector (test adapter, catalog feed, direct API, manual). One row
per (supplier_id, supplier_sku). Variant attributes are category-aware in the
`variant` dict — do NOT try to force apparel and non-apparel into one variant
structure.

`supplier_order_log` records EVERY submission attempt for a supplier-side PO
with idempotency, request/response, and audit metadata.
"""
from __future__ import annotations
from typing import Any, Literal, Optional
from pydantic import Field
from .base import BaseDoc


SupplierProductCategory = Literal[
    "apparel", "vinyl", "laminate", "application_tape", "printable_media",
    "substrate", "banner", "ink", "hardware", "supplies", "heat_transfer",
    "packaging", "equipment", "other",
]


class SupplierWarehouse(BaseDoc):
    """A vendor warehouse capable of shipping stock to the shop."""
    tenant_id: str
    vendor_id: str
    code: str                                  # e.g., "NW-PDX"
    name: str
    region: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    base_ship_cost_cents: int = 0             # per-shipment base
    per_item_ship_cost_cents: int = 0         # additional per line item
    freight_multiplier: float = 1.0           # heavy/bulky material multiplier
    handling_fee_cents: int = 0
    active: bool = True


class SupplierProduct(BaseDoc):
    """Normalized supplier catalog row.

    Category-aware variant attributes live inside `variant`. Never force
    apparel + non-apparel into the same variant shape (per master plan Appendix A.3).
    """
    tenant_id: str
    vendor_id: str

    # Identity
    supplier_sku: str
    upc: Optional[str] = None
    manufacturer: Optional[str] = None
    brand: Optional[str] = None
    series: Optional[str] = None
    family: Optional[str] = None
    description: str
    category: SupplierProductCategory = "other"

    # Variant attributes (category-aware, freeform dict)
    variant: dict[str, Any] = Field(default_factory=dict)

    # Purchase / packaging
    purchase_unit: str = "each"
    package_qty: int = 1                       # must order in multiples of this
    minimum_order_qty: int = 0
    quantity_breaks: list[dict[str, int]] = Field(default_factory=list)  # [{"min_qty":n, "unit_price_cents":c}]

    # Pricing (all integer cents; account price is tenant-scoped)
    list_price_cents: int = 0
    account_price_cents: int = 0
    price_effective_at: Optional[str] = None

    # Compatibility / substitution guard
    compatible_group: Optional[str] = None    # only compare within same group
    incompatible_with: list[str] = Field(default_factory=list)

    # Delivery attributes
    freight_class: Optional[str] = None       # "standard" | "ltl" | "parcel_only" | "oversize"
    default_lead_time_days: Optional[int] = None

    # Lifecycle
    active: bool = True
    discontinued: bool = False
    seed_source: Optional[str] = None         # "test_adapter" | "manual" | "feed_csv" | "api" | ...
    seed_ref: Optional[str] = None
    last_synced_at: Optional[str] = None


class SupplierProductStock(BaseDoc):
    """Per (supplier_product, warehouse) available quantity + lead time."""
    tenant_id: str
    vendor_id: str
    supplier_product_id: str
    warehouse_id: str
    available_qty: int = 0
    lead_time_days: int = 0
    last_synced_at: Optional[str] = None


class SupplierOrderLog(BaseDoc):
    """Every supplier-side submission attempt. Idempotency-Key is unique."""
    tenant_id: str
    vendor_id: str
    purchase_order_id: str
    idempotency_key: str
    request_id: str
    submitted_at: str
    submitted_by_user_id: Optional[str] = None
    request_payload: dict[str, Any] = Field(default_factory=dict)
    response_status: str = "pending"          # pending | accepted | rejected | error
    response_payload: dict[str, Any] = Field(default_factory=dict)
    supplier_order_id: Optional[str] = None
    tracking_number: Optional[str] = None
    tracking_status: Optional[str] = None
    last_polled_at: Optional[str] = None
