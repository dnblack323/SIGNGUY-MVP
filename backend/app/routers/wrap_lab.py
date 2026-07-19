"""EC15 - staff Wrap Lab routes."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, StrictInt

from ..deps import get_current_user
from ..services import wrap_lab as svc
from ..services.wrap_lab import WrapLabError

router = APIRouter(prefix="/wrap-lab", tags=["wrap-lab"])


def _raise(e: WrapLabError) -> None:
    raise HTTPException(status_code=e.status_code, detail=e.detail)


class VehicleIn(BaseModel):
    customer_id: Optional[str] = None
    year: Optional[str] = None
    make: str
    model: str
    trim: Optional[str] = None
    vin: Optional[str] = None
    license_plate: Optional[str] = None
    color: Optional[str] = None
    vehicle_type: str = "other"
    template_key: Optional[str] = None
    dimensions: dict[str, Any] = Field(default_factory=dict)
    photo_file_ids: list[str] = Field(default_factory=list)
    notes: Optional[str] = None


class ProjectIn(BaseModel):
    customer_id: str
    vehicle_id: Optional[str] = None
    intake_id: Optional[str] = None
    quote_id: Optional[str] = None
    order_id: Optional[str] = None
    work_order_id: Optional[str] = None
    commercial_feature_key: str = "wrap_lab"
    project_name: str
    project_type: str = "custom"
    status: Optional[str] = None
    coverage_summary: Optional[str] = None
    estimate_total_cents: StrictInt = Field(default=0, ge=0)
    deposit_required_cents: StrictInt = Field(default=0, ge=0)
    material_estimate_cents: StrictInt = Field(default=0, ge=0)
    labor_estimate_cents: StrictInt = Field(default=0, ge=0)
    assigned_user_ids: list[str] = Field(default_factory=list)
    due_at: Optional[str] = None
    notes: Optional[str] = None


class StatusIn(BaseModel):
    status: str
    reason: Optional[str] = None


class CoveragePlanIn(BaseModel):
    coverage_level: str = "custom"
    panels: list[dict[str, Any]] = Field(default_factory=list)
    total_square_feet: Optional[StrictInt] = Field(default=None, ge=0)
    waste_percent: StrictInt = Field(default=15, ge=0, le=100)
    status: str = "draft"
    notes: Optional[str] = None


class InspectionIn(BaseModel):
    inspection_type: str
    status: str = "draft"
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


class DesignSceneIn(BaseModel):
    status: str = "draft"
    vehicle_template_key: Optional[str] = None
    artboard: dict[str, Any] = Field(default_factory=dict)
    scale: dict[str, Any] = Field(default_factory=dict)
    layers: list[dict[str, Any]] = Field(default_factory=list)
    groups: list[dict[str, Any]] = Field(default_factory=list)
    notes: Optional[str] = None


class DesignLayerPatchIn(BaseModel):
    updates: dict[str, Any] = Field(default_factory=dict)


class PanelPlanIn(BaseModel):
    status: str = "draft"
    printer_max_width_inches: StrictInt = Field(default=54, gt=0)
    overlap_inches: float = Field(default=0.5, ge=0)
    bleed_inches: float = Field(default=0.5, ge=0)
    panels: list[dict[str, Any]] = Field(default_factory=list)
    export_formats: list[str] = Field(default_factory=list)
    material_usage_square_feet: Optional[StrictInt] = Field(default=None, ge=0)
    material_cost_cents: StrictInt = Field(default=0, ge=0)
    labor_cost_cents: StrictInt = Field(default=0, ge=0)
    notes: Optional[str] = None


class PacketIn(BaseModel):
    packet_type: str
    notes: Optional[str] = None


class ScheduleIn(BaseModel):
    schedule_type: str
    status: str = "scheduled"
    title: str
    start_at: str
    end_at: str
    assigned_user_ids: list[str] = Field(default_factory=list)
    location: Optional[str] = None
    calendar_event_id: Optional[str] = None
    notes: Optional[str] = None


class WarrantyIn(BaseModel):
    status: str = "draft"
    starts_at: Optional[str] = None
    expires_at: Optional[str] = None
    coverage_terms: list[str] = Field(default_factory=list)
    care_instructions: list[str] = Field(default_factory=list)
    issue_refs: list[dict[str, Any]] = Field(default_factory=list)
    warranty_value_cents: StrictInt = Field(default=0, ge=0)
    notes: Optional[str] = None


@router.get("/vehicles")
async def list_vehicles(customer_id: Optional[str] = Query(None), user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.list_vehicles(user, customer_id=customer_id)
    except WrapLabError as e:
        _raise(e)


@router.post("/vehicles", status_code=201)
async def create_vehicle(payload: VehicleIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_vehicle(user, payload.model_dump(exclude_none=True))
    except WrapLabError as e:
        _raise(e)


@router.get("/projects")
async def list_projects(status: Optional[str] = Query(None), customer_id: Optional[str] = Query(None), user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.list_projects(user, status=status, customer_id=customer_id)
    except WrapLabError as e:
        _raise(e)


@router.post("/projects", status_code=201)
async def create_project(payload: ProjectIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_project(user, payload.model_dump(exclude_none=True))
    except WrapLabError as e:
        _raise(e)


@router.get("/reports")
async def reports(user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.reports(user)
    except WrapLabError as e:
        _raise(e)


@router.get("/projects/{project_id}")
async def get_project(project_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.get_project(user, project_id)
    except WrapLabError as e:
        _raise(e)


@router.post("/projects/{project_id}/status")
async def advance_project(project_id: str, payload: StatusIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.advance_project(user, project_id, payload.status, reason=payload.reason)
    except WrapLabError as e:
        _raise(e)


@router.post("/projects/{project_id}/coverage-plans", status_code=201)
async def create_coverage_plan(project_id: str, payload: CoveragePlanIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_coverage_plan(user, project_id, payload.model_dump(exclude_none=True))
    except WrapLabError as e:
        _raise(e)


@router.post("/projects/{project_id}/inspections", status_code=201)
async def create_inspection(project_id: str, payload: InspectionIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_inspection(user, project_id, payload.model_dump(exclude_none=True))
    except WrapLabError as e:
        _raise(e)


@router.post("/projects/{project_id}/design-scenes", status_code=201)
async def create_design_scene(project_id: str, payload: DesignSceneIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_design_scene(user, project_id, payload.model_dump(exclude_none=True))
    except WrapLabError as e:
        _raise(e)


@router.patch("/design-scenes/{scene_id}/layers/{layer_id}")
async def update_design_layer(scene_id: str, layer_id: str, payload: DesignLayerPatchIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.update_design_layer(user, scene_id, layer_id, payload.updates)
    except WrapLabError as e:
        _raise(e)


@router.post("/projects/{project_id}/panel-plans", status_code=201)
async def create_panel_plan(project_id: str, payload: PanelPlanIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_panel_plan(user, project_id, payload.model_dump(exclude_none=True))
    except WrapLabError as e:
        _raise(e)


@router.post("/projects/{project_id}/packets", status_code=201)
async def generate_packet(project_id: str, payload: PacketIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.generate_packet(user, project_id, payload.model_dump(exclude_none=True))
    except WrapLabError as e:
        _raise(e)


@router.post("/projects/{project_id}/schedules", status_code=201)
async def create_schedule(project_id: str, payload: ScheduleIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_schedule(user, project_id, payload.model_dump(exclude_none=True))
    except WrapLabError as e:
        _raise(e)


@router.post("/projects/{project_id}/warranties", status_code=201)
async def create_warranty(project_id: str, payload: WarrantyIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_warranty(user, project_id, payload.model_dump(exclude_none=True))
    except WrapLabError as e:
        _raise(e)
