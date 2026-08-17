"""EC12 Phase 12D - shared calendar and appointment routes."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..core.permissions import Perm
from ..deps import require_permission
from ..services import calendar_service
from ..services.calendar_service import CalendarError

router = APIRouter(prefix="/calendar", tags=["calendar"])


def _raise(e: CalendarError) -> None:
    raise HTTPException(status_code=e.status_code, detail={"code": e.code, "message": e.detail, **e.metadata})


class CalendarEventIn(BaseModel):
    event_type: str = "custom"
    title: str
    description: Optional[str] = None
    start_at: str
    end_at: str
    all_day: bool = False
    timezone: Optional[str] = None
    location: Optional[str] = None
    customer_id: Optional[str] = None
    contact_id: Optional[str] = None
    quote_id: Optional[str] = None
    order_id: Optional[str] = None
    order_item_id: Optional[str] = None
    work_order_id: Optional[str] = None
    production_stage_id: Optional[str] = None
    wrap_project_id: Optional[str] = None
    vehicle_inspection_id: Optional[str] = None
    installation_id: Optional[str] = None
    task_id: Optional[str] = None
    employee_id: Optional[str] = None
    assigned_employee_ids: list[str] = Field(default_factory=list)
    reserved_equipment_ids: list[str] = Field(default_factory=list)
    reserved_vehicle_ids: list[str] = Field(default_factory=list)
    reserved_resource_ids: list[str] = Field(default_factory=list)
    assigned_user_id: Optional[str] = None
    visibility: str = "staff"
    reminder_policy: dict = {}
    recurrence_rule: Optional[dict] = None
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    conflict_override_reason: Optional[str] = None


class CalendarEventUpdateIn(BaseModel):
    event_type: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    start_at: Optional[str] = None
    end_at: Optional[str] = None
    all_day: Optional[bool] = None
    timezone: Optional[str] = None
    location: Optional[str] = None
    customer_id: Optional[str] = None
    contact_id: Optional[str] = None
    quote_id: Optional[str] = None
    order_id: Optional[str] = None
    order_item_id: Optional[str] = None
    work_order_id: Optional[str] = None
    production_stage_id: Optional[str] = None
    wrap_project_id: Optional[str] = None
    vehicle_inspection_id: Optional[str] = None
    installation_id: Optional[str] = None
    task_id: Optional[str] = None
    employee_id: Optional[str] = None
    assigned_employee_ids: Optional[list[str]] = None
    reserved_equipment_ids: Optional[list[str]] = None
    reserved_vehicle_ids: Optional[list[str]] = None
    reserved_resource_ids: Optional[list[str]] = None
    assigned_user_id: Optional[str] = None
    visibility: Optional[str] = None
    reminder_policy: Optional[dict] = None
    recurrence_rule: Optional[dict] = None
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    conflict_override_reason: Optional[str] = None


class CancelIn(BaseModel):
    reason: Optional[str] = None


class CompleteIn(BaseModel):
    outcome_note: Optional[str] = None


class ReopenIn(BaseModel):
    reason: str


class AvailabilityIn(BaseModel):
    start_at: str
    end_at: str
    event_id: Optional[str] = None
    employee_id: Optional[str] = None
    assigned_employee_ids: list[str] = Field(default_factory=list)
    reserved_equipment_ids: list[str] = Field(default_factory=list)
    reserved_vehicle_ids: list[str] = Field(default_factory=list)
    reserved_resource_ids: list[str] = Field(default_factory=list)
    location: Optional[str] = None
    customer_id: Optional[str] = None


class SchedulableResourceIn(BaseModel):
    name: str
    resource_type: str = "work_area"
    status: str = "active"
    capacity: Optional[int] = None
    location: Optional[str] = None
    description: Optional[str] = None
    availability_windows: list[dict] = Field(default_factory=list)
    unavailable_periods: list[dict] = Field(default_factory=list)


class SchedulableResourceUpdateIn(BaseModel):
    name: Optional[str] = None
    resource_type: Optional[str] = None
    status: Optional[str] = None
    capacity: Optional[int] = None
    location: Optional[str] = None
    description: Optional[str] = None
    availability_windows: Optional[list[dict]] = None
    unavailable_periods: Optional[list[dict]] = None


@router.get("/feed")
async def feed(
    start_at: str,
    end_at: str,
    event_type: Optional[str] = None,
    employee_id: Optional[str] = None,
    equipment_id: Optional[str] = None,
    vehicle_id: Optional[str] = None,
    resource_id: Optional[str] = None,
    attention: Optional[str] = None,
    customer_id: Optional[str] = None,
    quote_id: Optional[str] = None,
    order_id: Optional[str] = None,
    order_item_id: Optional[str] = None,
    work_order_id: Optional[str] = None,
    production_stage_id: Optional[str] = None,
    wrap_project_id: Optional[str] = None,
    status: Optional[str] = None,
    source_type: Optional[str] = None,
    visibility: Optional[str] = None,
    limit: int = Query(200, ge=1, le=500),
    skip: int = Query(0, ge=0),
    user: dict = Depends(require_permission(Perm.SCHEDULE_READ)),
) -> dict:
    try:
        return await calendar_service.list_events(
            tenant_id=user["tenant_id"], start_at=start_at, end_at=end_at,
            event_type=event_type, employee_id=employee_id, equipment_id=equipment_id,
            vehicle_id=vehicle_id, resource_id=resource_id, attention=attention, customer_id=customer_id,
            quote_id=quote_id, order_id=order_id, order_item_id=order_item_id,
            work_order_id=work_order_id, production_stage_id=production_stage_id,
            wrap_project_id=wrap_project_id, status=status, source_type=source_type,
            visibility=visibility, limit=limit, skip=skip,
        )
    except CalendarError as e:
        _raise(e)


@router.get("/conflicts")
async def conflicts(start_at: str, end_at: str, employee_id: Optional[str] = None,
                    assigned_employee_ids: list[str] = Query(default=[]),
                    reserved_equipment_ids: list[str] = Query(default=[]),
                    reserved_vehicle_ids: list[str] = Query(default=[]),
                    reserved_resource_ids: list[str] = Query(default=[]),
                    location: Optional[str] = None, customer_id: Optional[str] = None,
                    event_id: Optional[str] = None,
                    user: dict = Depends(require_permission(Perm.SCHEDULE_READ))) -> dict:
    try:
        return {"items": await calendar_service.check_conflicts(
            tenant_id=user["tenant_id"], start_at=start_at, end_at=end_at, employee_id=employee_id,
            assigned_employee_ids=assigned_employee_ids,
            reserved_equipment_ids=reserved_equipment_ids,
            reserved_vehicle_ids=reserved_vehicle_ids,
            reserved_resource_ids=reserved_resource_ids,
            location=location, customer_id=customer_id, event_id=event_id,
        )}
    except CalendarError as e:
        _raise(e)


@router.post("/availability")
async def availability(payload: AvailabilityIn, user: dict = Depends(require_permission(Perm.SCHEDULE_READ))) -> dict:
    try:
        return await calendar_service.availability(tenant_id=user["tenant_id"], payload=payload.model_dump(exclude_none=True))
    except CalendarError as e:
        _raise(e)


@router.get("/resources")
async def list_resources(status: Optional[str] = None, resource_type: Optional[str] = None,
                         user: dict = Depends(require_permission(Perm.SCHEDULE_READ))) -> dict:
    try:
        return await calendar_service.list_schedulable_resources(
            tenant_id=user["tenant_id"], status=status, resource_type=resource_type,
        )
    except CalendarError as e:
        _raise(e)


@router.post("/resources", status_code=201)
async def create_resource(payload: SchedulableResourceIn,
                          user: dict = Depends(require_permission(Perm.SCHEDULE_MANAGE))) -> dict:
    try:
        return await calendar_service.create_schedulable_resource(
            tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
            payload=payload.model_dump(exclude_none=True),
        )
    except CalendarError as e:
        _raise(e)


@router.patch("/resources/{resource_id}")
async def update_resource(resource_id: str, payload: SchedulableResourceUpdateIn,
                          user: dict = Depends(require_permission(Perm.SCHEDULE_MANAGE))) -> dict:
    try:
        return await calendar_service.update_schedulable_resource(
            tenant_id=user["tenant_id"], resource_id=resource_id,
            actor_user_id=user["id"], actor_email=user["email"],
            payload=payload.model_dump(exclude_none=True),
        )
    except CalendarError as e:
        _raise(e)


@router.post("/resources/{resource_id}/archive")
async def archive_resource(resource_id: str, user: dict = Depends(require_permission(Perm.SCHEDULE_MANAGE))) -> dict:
    try:
        return await calendar_service.archive_schedulable_resource(
            tenant_id=user["tenant_id"], resource_id=resource_id,
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except CalendarError as e:
        _raise(e)


@router.post("/events", status_code=201)
async def create_event(payload: CalendarEventIn,
                       user: dict = Depends(require_permission(Perm.SCHEDULE_MANAGE))) -> dict:
    try:
        return await calendar_service.create_event(
            tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
            actor_role=user.get("role"),
            payload=payload.model_dump(exclude_none=True),
        )
    except CalendarError as e:
        _raise(e)


@router.get("/events/{event_id}")
async def get_event(event_id: str, user: dict = Depends(require_permission(Perm.SCHEDULE_READ))) -> dict:
    try:
        return await calendar_service.get_event(tenant_id=user["tenant_id"], event_id=event_id)
    except CalendarError as e:
        _raise(e)


@router.patch("/events/{event_id}")
async def update_event(event_id: str, payload: CalendarEventUpdateIn,
                       user: dict = Depends(require_permission(Perm.SCHEDULE_MANAGE))) -> dict:
    try:
        return await calendar_service.update_event(
            tenant_id=user["tenant_id"], event_id=event_id, actor_user_id=user["id"], actor_email=user["email"],
            actor_role=user.get("role"),
            payload=payload.model_dump(exclude_none=True),
        )
    except CalendarError as e:
        _raise(e)


@router.post("/events/{event_id}/reschedule")
async def reschedule_event(event_id: str, payload: CalendarEventUpdateIn,
                           user: dict = Depends(require_permission(Perm.SCHEDULE_MANAGE))) -> dict:
    try:
        return await calendar_service.reschedule_event(
            tenant_id=user["tenant_id"], event_id=event_id, actor_user_id=user["id"], actor_email=user["email"],
            actor_role=user.get("role"),
            payload=payload.model_dump(exclude_none=True),
        )
    except CalendarError as e:
        _raise(e)


@router.post("/events/{event_id}/cancel")
async def cancel_event(event_id: str, payload: CancelIn,
                       user: dict = Depends(require_permission(Perm.SCHEDULE_MANAGE))) -> dict:
    try:
        return await calendar_service.cancel_event(
            tenant_id=user["tenant_id"], event_id=event_id, actor_user_id=user["id"],
            actor_email=user["email"], reason=payload.reason,
        )
    except CalendarError as e:
        _raise(e)


@router.post("/events/{event_id}/complete")
async def complete_event(event_id: str, payload: CompleteIn = Body(default_factory=CompleteIn),
                         user: dict = Depends(require_permission(Perm.SCHEDULE_MANAGE))) -> dict:
    try:
        return await calendar_service.complete_event(
            tenant_id=user["tenant_id"], event_id=event_id, actor_user_id=user["id"],
            actor_email=user["email"], outcome_note=payload.outcome_note,
        )
    except CalendarError as e:
        _raise(e)


@router.post("/events/{event_id}/reopen")
async def reopen_event(event_id: str, payload: ReopenIn,
                       user: dict = Depends(require_permission(Perm.SCHEDULE_MANAGE))) -> dict:
    try:
        return await calendar_service.reopen_event(
            tenant_id=user["tenant_id"], event_id=event_id, actor_user_id=user["id"],
            actor_email=user["email"], reason=payload.reason,
        )
    except CalendarError as e:
        _raise(e)


@router.post("/events/{event_id}/archive")
async def archive_event(event_id: str, user: dict = Depends(require_permission(Perm.SCHEDULE_MANAGE))) -> dict:
    try:
        return await calendar_service.archive_event(
            tenant_id=user["tenant_id"], event_id=event_id, actor_user_id=user["id"], actor_email=user["email"],
        )
    except CalendarError as e:
        _raise(e)


@router.post("/events/{event_id}/restore")
async def restore_event(event_id: str, user: dict = Depends(require_permission(Perm.SCHEDULE_MANAGE))) -> dict:
    try:
        return await calendar_service.restore_event(
            tenant_id=user["tenant_id"], event_id=event_id, actor_user_id=user["id"], actor_email=user["email"],
        )
    except CalendarError as e:
        _raise(e)

