from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import Field

from .base import BaseDoc

ProductionWorkflowScope = Literal["tenant_default", "category", "reusable_custom", "system_starter"]

ProductionStageStatus = Literal["not_started", "in_progress", "waiting", "blocked", "completed", "skipped"]


class ProductionWorkflowStageDefinition(BaseDoc):
    stage_key: str
    display_name: str
    description: Optional[str] = None
    sequence: int
    active: bool = True
    required: bool = True
    may_skip: bool = True
    requires_reason_to_skip: bool = False
    default_role: Optional[str] = None
    default_estimated_duration_minutes: Optional[int] = None
    due_date_offset_days: Optional[int] = None
    customer_visible: bool = False
    employee_visible: bool = True
    requires_previous_stage_complete: bool = True
    proof_gate_type: Optional[str] = None
    equipment_requirement_ids: list[str] = Field(default_factory=list)
    certification_requirement_ids: list[str] = Field(default_factory=list)
    checklist_template_ids: list[str] = Field(default_factory=list)
    color: Optional[str] = None
    icon: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProductionWorkflowDefinition(BaseDoc):
    tenant_id: str
    name: str
    description: Optional[str] = None
    workflow_key: str
    scope_type: ProductionWorkflowScope = "reusable_custom"
    category_ids: list[str] = Field(default_factory=list)
    active: bool = True
    archived_at: Optional[str] = None
    version: int = 1
    source_template_id: Optional[str] = None
    is_tenant_default: bool = False
    system_starter_key: Optional[str] = None
    stages: list[ProductionWorkflowStageDefinition] = Field(default_factory=list)
    created_by_user_id: Optional[str] = None
    updated_by_user_id: Optional[str] = None
