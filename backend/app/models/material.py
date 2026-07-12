"""EC7 phase 7a — Material record (physical inventory material, distinct from
`pricing_material` which owns EC3 pricing formulas)."""
from __future__ import annotations
from typing import Literal, Optional
from pydantic import Field
from .base import BaseDoc

MaterialCategory = Literal[
    "vinyl", "laminate", "application_tape", "printable_media", "substrate",
    "banner", "ink", "hardware", "apparel", "heat_transfer", "packaging",
    "equipment", "supplies", "other",
]
UnitOfMeasure = Literal[
    "each", "package", "roll", "sheet", "linear_foot", "square_foot",
    "linear_inch", "square_inch", "gallon", "ounce", "pound",
]


class Material(BaseDoc):
    tenant_id: str
    name: str
    sku: Optional[str] = None
    category: MaterialCategory = "other"
    manufacturer: Optional[str] = None
    brand: Optional[str] = None
    series: Optional[str] = None
    description: Optional[str] = None
    # Purchase configuration
    purchase_unit: UnitOfMeasure = "each"
    package_size: Optional[float] = None
    roll_width_inches: Optional[float] = None
    roll_length_feet: Optional[float] = None
    sheet_width_inches: Optional[float] = None
    sheet_height_inches: Optional[float] = None
    quantity_per_package: Optional[float] = None
    vendor_item_number: Optional[str] = None
    # Cost
    current_cost_cents: int = 0
    cost_unit: UnitOfMeasure = "each"
    effective_at: Optional[str] = None
    # Inventory behavior
    stock_tracked: bool = True
    reorder_point: Optional[float] = None
    reorder_quantity: Optional[float] = None
    default_location_id: Optional[str] = None
    unit_of_measure: UnitOfMeasure = "each"
    active: bool = True
    # Pricing integration
    pricing_material_id: Optional[str] = None
    tax_classification: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


class MaterialCostHistory(BaseDoc):
    tenant_id: str
    material_id: str
    cost_cents: int
    cost_unit: UnitOfMeasure = "each"
    vendor_id: Optional[str] = None
    source: str = "manual"   # manual | receiving | vendor_import
    source_ref: Optional[str] = None
    effective_at: str
    actor_user_id: Optional[str] = None
