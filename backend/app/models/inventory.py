"""EC7 phase 7a — Inventory location, item, movement, reservation."""
from __future__ import annotations
from typing import Literal, Optional
from pydantic import Field
from .base import BaseDoc

MovementType = Literal[
    "receiving", "manual_increase", "manual_decrease", "correction",
    "transfer_out", "transfer_in", "reservation", "reservation_release",
    "consumption", "return_to_stock", "waste", "damage", "count_adjustment",
]
Direction = Literal["in", "out", "neutral"]


class InventoryLocation(BaseDoc):
    tenant_id: str
    name: str
    kind: Literal["shop", "production", "vehicle", "warehouse", "overflow", "other"] = "shop"
    address: Optional[str] = None
    notes: Optional[str] = None
    active: bool = True


class InventoryItem(BaseDoc):
    """A single material's balance at a specific location. Unique per
    (tenant_id, material_id, location_id)."""
    tenant_id: str
    material_id: str
    location_id: str
    quantity_on_hand: float = 0.0
    quantity_reserved: float = 0.0
    # quantity_available is derived = on_hand - reserved (server-only computed)
    minimum_quantity: Optional[float] = None
    reorder_quantity: Optional[float] = None
    last_counted_at: Optional[str] = None
    last_received_at: Optional[str] = None
    last_movement_at: Optional[str] = None


class InventoryMovement(BaseDoc):
    """Immutable stock-change ledger row."""
    tenant_id: str
    material_id: str
    location_id: str
    quantity: float          # always positive; direction encodes sign
    unit_of_measure: str = "each"
    direction: Direction = "neutral"
    movement_type: MovementType
    source_entity_type: Optional[str] = None     # "purchase_order" | "order" | "work_order" | "adjustment" | ...
    source_entity_id: Optional[str] = None
    reason: Optional[str] = None
    actor_user_id: Optional[str] = None
    before_quantity: float = 0.0
    after_quantity: float = 0.0
    idempotency_key: Optional[str] = None
    observed_quantity: Optional[float] = None    # for physical count (records expected vs observed)
    expected_quantity: Optional[float] = None


class InventoryReservation(BaseDoc):
    tenant_id: str
    material_id: str
    location_id: str
    quantity: float
    unit_of_measure: str = "each"
    source_entity_type: str      # "order" | "order_item" | "work_order"
    source_entity_id: str
    active: bool = True
    released_at: Optional[str] = None
    released_reason: Optional[str] = None
    actor_user_id: Optional[str] = None
