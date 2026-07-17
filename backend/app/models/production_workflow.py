from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import Field

from .base import BaseDoc

ProductionWorkflowScope = Literal[
    "tenant_default",
    "category",
    "reusable_custom",
    "system_starter",
    "order_item_override",
]

ProductionStageStatus = Literal["not_started", "in_progress", "waiting", "blocked", "completed", "skipped"]
ProductionWorkflowInstanceStatus = Literal["active", "manual_no_workflow", "completed", "cancelled"]
ProductionWorkflowInstanceSource = Literal["order_item_override", "category", "tenant_default", "explicit_workflow", "manual_no_workflow"]


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


class OrderItemWorkflowOverride(BaseDoc):
    tenant_id: str
    order_id: str
    order_item_id: str
    source_workflow_id: Optional[str] = None
    source_workflow_version: Optional[int] = None
    source_type: ProductionWorkflowInstanceSource = "order_item_override"
    workflow_name: str
    workflow_key: str
    stages: list[ProductionWorkflowStageDefinition] = Field(default_factory=list)
    created_by_user_id: str
    updated_by_user_id: Optional[str] = None
    locked_at: Optional[str] = None
    locked_workflow_instance_id: Optional[str] = None


class ProductionWorkflowInstance(BaseDoc):
    tenant_id: str
    order_id: str
    order_item_id: str
    work_order_id: str
    source_workflow_id: Optional[str] = None
    source_workflow_version: Optional[int] = None
    source_type: ProductionWorkflowInstanceSource
    source_name: Optional[str] = None
    created_by_user_id: str
    status: ProductionWorkflowInstanceStatus = "active"
    resolution_source: str
    stage_definitions: list[dict[str, Any]] = Field(default_factory=list)


class ProductionStageInstance(BaseDoc):
    tenant_id: str
    workflow_instance_id: str
    order_id: str
    order_item_id: str
    work_order_id: str
    stage_key: str
    stage_name: str
    description: Optional[str] = None
    sequence: int
    required: bool = True
    may_skip: bool = True
    requires_reason_to_skip: bool = False
    status: ProductionStageStatus = "not_started"
    assigned_employee_id: Optional[str] = None
    assigned_user_id: Optional[str] = None
    assigned_role: Optional[str] = None
    due_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    skipped_at: Optional[str] = None
    blocked_at: Optional[str] = None
    waiting_since: Optional[str] = None
    blocker_reason: Optional[str] = None
    completion_note: Optional[str] = None
    skip_reason: Optional[str] = None
    reopened_at: Optional[str] = None
    reopened_by_user_id: Optional[str] = None
    reopen_reason: Optional[str] = None
    proof_gate_type: Optional[str] = None
    proof_gate_snapshot: Optional[dict[str, Any]] = None
    equipment_requirement_ids: list[str] = Field(default_factory=list)
    certification_requirement_ids: list[str] = Field(default_factory=list)
    customer_visible: bool = False
    employee_visible: bool = True
    requires_previous_stage_complete: bool = True
    production_notes: list[dict[str, Any]] = Field(default_factory=list)
    history: list[dict[str, Any]] = Field(default_factory=list)
