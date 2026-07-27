"""Tenant-scoped record numbering contracts."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import Field

from .base import BaseDoc


RecordNumberResetPolicy = Literal["never", "calendar_year"]
RecordNumberDateComponent = Literal["none", "year"]
RecordNumberAllocationStatus = Literal["issued"]


class RecordNumberConfig(BaseDoc):
    tenant_id: str
    record_type: str
    prefix: str = ""
    starting_number: int = Field(default=1, ge=1)
    min_digits: int = Field(default=0, ge=0, le=12)
    suffix: str = ""
    date_component: RecordNumberDateComponent = "none"
    reset_policy: RecordNumberResetPolicy = "never"
    max_number: Optional[int] = Field(default=None, ge=1)
    active: bool = True


class RecordNumberAllocation(BaseDoc):
    tenant_id: str
    record_type: str
    sequence_name: str
    number: int
    formatted_number: str
    status: RecordNumberAllocationStatus = "issued"
    idempotency_key: Optional[str] = None
    issued_to_entity_type: Optional[str] = None
    issued_to_entity_id: Optional[str] = None
    actor_user_id: Optional[str] = None
    actor_email: Optional[str] = None
    reason: Optional[str] = None
    context: dict[str, Any] = Field(default_factory=dict)
    config_snapshot: dict[str, Any] = Field(default_factory=dict)
