"""Tenant-scoped reservable shop spaces for the shared calendar.

This model is intentionally limited to places/work areas such as installation
bays, wrap bays, production areas, and meeting areas. Employees remain owned by
Employee records and equipment/vehicles remain owned by Equipment records.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import Field

from .base import BaseDoc

SchedulableResourceType = Literal[
    "installation_bay",
    "wrap_bay",
    "production_area",
    "meeting_area",
    "work_area",
    "other",
]
SchedulableResourceStatus = Literal["active", "inactive", "archived"]


class SchedulableResource(BaseDoc):
    tenant_id: str
    name: str
    resource_type: SchedulableResourceType = "work_area"
    status: SchedulableResourceStatus = "active"
    capacity: Optional[int] = None
    location: Optional[str] = None
    description: Optional[str] = None
    availability_windows: list[dict[str, Any]] = Field(default_factory=list)
    unavailable_periods: list[dict[str, Any]] = Field(default_factory=list)
    created_by: str
    updated_by: str
