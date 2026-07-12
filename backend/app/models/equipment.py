"""EC8 phase 8e — Equipment (tenant-scoped asset register gating Training/
Certification and Work Order assignment).

Distinct from EC7 inventory/material SKU tracking — this is workforce
safety/certification equipment, not stock. Equipment is never hard-deleted;
`status="archived"` instead, so historical Training/Certification/Work Order
references stay resolvable.

`access_policy` is the SOLE authoritative source for assignment-enforcement
decisions (see `services/certification_service.check_work_order_assignment`).
`certification_required` is a derived display convenience kept in sync by
`services/equipment_service.py` — never read directly by the enforcement
engine.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import Field

from .base import BaseDoc

EquipmentCategory = Literal[
    "printer", "laminator", "plotter", "cutter", "heat_press",
    "embroidery_machine", "lift", "vehicle", "specialty_tool", "other",
]
EquipmentStatus = Literal["active", "inactive", "maintenance", "retired", "archived"]
# no_required            — no certification needed to be assigned
# recommended            — certification encouraged; gap is always a warning, never blocks
# required_override_allowed — certification required; a manager may override a gap with a reason
# required_no_override      — certification required; NO override is possible (hard block)
EquipmentAccessPolicy = Literal[
    "no_required", "recommended", "required_override_allowed", "required_no_override",
]


class Equipment(BaseDoc):
    tenant_id: str
    name: str
    category: EquipmentCategory = "other"
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    location: Optional[str] = None
    status: EquipmentStatus = "active"
    safety_sensitive: bool = False
    certification_required: bool = False   # derived from access_policy — see module docstring
    access_policy: EquipmentAccessPolicy = "no_required"
    description: Optional[str] = None
    operating_notes: Optional[str] = None
    safety_notes: Optional[str] = None
    training_requirements: Optional[str] = None  # free-text summary
    maintenance_reference: Optional[str] = None
    created_by: str
    updated_by: str
