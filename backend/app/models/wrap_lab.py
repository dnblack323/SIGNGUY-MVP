"""EC15 - Wrap Lab canonical data contracts."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import Field, StrictInt

from .base import BaseDoc

WrapProjectStatus = Literal[
    "lead_intake",
    "vehicle_recorded",
    "measurement_planning",
    "estimate_ready",
    "quote_linked",
    "contract_deposit_pending",
    "pre_install_ready",
    "pre_install_signed",
    "design_in_progress",
    "proof_ready",
    "proof_approved",
    "panel_plan_ready",
    "production_ready",
    "install_scheduled",
    "installing",
    "completion_packet_ready",
    "completed",
    "warranty_active",
    "archived",
]
WrapVehicleType = Literal["sedan", "suv", "pickup", "van", "box_truck", "sprinter_van", "trailer", "semi_truck", "race_car", "other"]
CoverageLevel = Literal["spot_graphics", "partial_wrap", "half_wrap", "full_wrap", "custom"]
CoveragePanelStatus = Literal["not_started", "measured", "designed", "printed", "prepped", "wrapped", "quality_checked", "skipped"]
InspectionType = Literal["pre_install", "completion"]
InspectionStatus = Literal["draft", "ready_for_signature", "signed", "completed", "superseded"]
DamageType = Literal["scratch", "dent", "paint_chip", "rust", "failing_clear_coat", "other"]
DesignStatus = Literal["draft", "in_progress", "proof_ready", "approved", "superseded"]
LayerType = Literal["vehicle_template", "logo_asset", "text", "shape", "background", "panel_guide", "measurement", "note"]
PanelPlanStatus = Literal["draft", "ready_for_production", "exported", "superseded"]
PacketType = Literal["pre_install", "work_order", "completion", "warranty_aftercare"]
PacketStatus = Literal["generated", "sent", "signed", "superseded"]
ScheduleType = Literal["production", "install", "pickup"]
ScheduleStatus = Literal["scheduled", "in_progress", "completed", "canceled"]
WarrantyStatus = Literal["draft", "active", "expired", "voided"]


class WrapVehicle(BaseDoc):
    tenant_id: str
    customer_id: Optional[str] = None
    year: Optional[str] = None
    make: str
    model: str
    trim: Optional[str] = None
    vin: Optional[str] = None
    license_plate: Optional[str] = None
    color: Optional[str] = None
    vehicle_type: WrapVehicleType = "other"
    template_key: Optional[str] = None
    dimensions: dict[str, Any] = Field(default_factory=dict)
    photo_file_ids: list[str] = Field(default_factory=list)
    notes: Optional[str] = None


class WrapProject(BaseDoc):
    tenant_id: str
    customer_id: str
    vehicle_id: Optional[str] = None
    intake_id: Optional[str] = None
    quote_id: Optional[str] = None
    order_id: Optional[str] = None
    work_order_id: Optional[str] = None
    commercial_feature_key: str = "wrap_lab"
    project_name: str
    project_type: CoverageLevel = "custom"
    status: WrapProjectStatus = "lead_intake"
    coverage_summary: Optional[str] = None
    estimate_total_cents: StrictInt = Field(default=0, ge=0)
    deposit_required_cents: StrictInt = Field(default=0, ge=0)
    material_estimate_cents: StrictInt = Field(default=0, ge=0)
    labor_estimate_cents: StrictInt = Field(default=0, ge=0)
    assigned_user_ids: list[str] = Field(default_factory=list)
    due_at: Optional[str] = None
    completed_at: Optional[str] = None
    archived_at: Optional[str] = None
    notes: Optional[str] = None


class WrapCoveragePlan(BaseDoc):
    tenant_id: str
    project_id: str
    coverage_level: CoverageLevel = "custom"
    panels: list[dict[str, Any]] = Field(default_factory=list)
    total_square_feet: StrictInt = Field(default=0, ge=0)
    waste_percent: StrictInt = Field(default=15, ge=0, le=100)
    status: str = "draft"
    notes: Optional[str] = None


class WrapInspection(BaseDoc):
    tenant_id: str
    project_id: str
    inspection_type: InspectionType
    status: InspectionStatus = "draft"
    inspector_user_id: Optional[str] = None
    damage_items: list[dict[str, Any]] = Field(default_factory=list)
    acknowledgements: list[dict[str, Any]] = Field(default_factory=list)
    diagram_marks: list[dict[str, Any]] = Field(default_factory=list)
    before_photo_file_ids: list[str] = Field(default_factory=list)
    after_photo_file_ids: list[str] = Field(default_factory=list)
    signature_request_id: Optional[str] = None
    signature_id: Optional[str] = None
    signed_at: Optional[str] = None
    notes: Optional[str] = None


class WrapDesignScene(BaseDoc):
    tenant_id: str
    project_id: str
    revision: StrictInt = Field(default=1, ge=1)
    status: DesignStatus = "draft"
    vehicle_template_key: Optional[str] = None
    artboard: dict[str, Any] = Field(default_factory=dict)
    scale: dict[str, Any] = Field(default_factory=dict)
    layers: list[dict[str, Any]] = Field(default_factory=list)
    groups: list[dict[str, Any]] = Field(default_factory=list)
    original_asset_file_ids: list[str] = Field(default_factory=list)
    preflight_results: dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None


class WrapPanelPlan(BaseDoc):
    tenant_id: str
    project_id: str
    revision: StrictInt = Field(default=1, ge=1)
    status: PanelPlanStatus = "draft"
    printer_max_width_inches: StrictInt = Field(default=54, gt=0)
    overlap_inches: float = Field(default=0.5, ge=0)
    bleed_inches: float = Field(default=0.5, ge=0)
    panels: list[dict[str, Any]] = Field(default_factory=list)
    export_manifest: dict[str, Any] = Field(default_factory=dict)
    material_usage_square_feet: StrictInt = Field(default=0, ge=0)
    material_cost_cents: StrictInt = Field(default=0, ge=0)
    labor_cost_cents: StrictInt = Field(default=0, ge=0)
    notes: Optional[str] = None


class WrapPacket(BaseDoc):
    tenant_id: str
    project_id: str
    packet_type: PacketType
    revision: StrictInt = Field(default=1, ge=1)
    status: PacketStatus = "generated"
    snapshot: dict[str, Any] = Field(default_factory=dict)
    layout_contract: dict[str, Any] = Field(default_factory=dict)
    generated_by_user_id: Optional[str] = None
    sent_at: Optional[str] = None
    signed_at: Optional[str] = None


class WrapSchedule(BaseDoc):
    tenant_id: str
    project_id: str
    schedule_type: ScheduleType
    status: ScheduleStatus = "scheduled"
    title: str
    start_at: str
    end_at: str
    assigned_user_ids: list[str] = Field(default_factory=list)
    location: Optional[str] = None
    calendar_event_id: Optional[str] = None
    notes: Optional[str] = None


class WrapWarranty(BaseDoc):
    tenant_id: str
    project_id: str
    status: WarrantyStatus = "draft"
    starts_at: Optional[str] = None
    expires_at: Optional[str] = None
    coverage_terms: list[str] = Field(default_factory=list)
    care_instructions: list[str] = Field(default_factory=list)
    issue_refs: list[dict[str, Any]] = Field(default_factory=list)
    warranty_value_cents: StrictInt = Field(default=0, ge=0)
    notes: Optional[str] = None


class WrapActivity(BaseDoc):
    tenant_id: str
    project_id: str
    actor_type: str = "staff"
    actor_id: Optional[str] = None
    actor_email: Optional[str] = None
    action: str
    entity_type: str
    entity_id: str
    summary: str
    metadata: dict[str, Any] = Field(default_factory=dict)
