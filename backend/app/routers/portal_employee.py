"""EC8 phase 8c — Employee Portal (employee-facing self-service routes).

Every route resolves the acting Employee from `identity["employee_id"]`
(set at token-mint time from the PortalIdentity doc) — never from a
client-supplied employee_id. Time Clock and Timesheet actions call straight
into the Phase 8b services (`time_clock_service`, `timesheet_service`) with
no duplicated business logic. Schedule/Announcements reuse the Phase 8a/8c
data directly with an explicit self/published-only filter.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from ..core.db import db
from ..core.time_utils import utc_now
from ..deps_portal import require_employee_portal_permission
from ..services import announcement_service, calendar_service, certification_service, communication_service, payroll_service, production_board_service, production_stage_service, schedule_service, task_service, time_clock_service, time_off_service, timesheet_service, training_service
from ..services.activity import record_activity_with_audit
from ..services.calendar_service import CalendarError
from ..services.communication_service import CommunicationError
from ..services.production_stage_service import ProductionStageError
from ..services.task_service import TaskError
from ..services.time_off_service import TimeOffError
from ..services.portal_identity import update_portal_identity
from ..services.time_clock_service import TimeEntryError
from ..services.timesheet_service import TimesheetError
from ..services.training_service import TrainingError, public_definition_view

router = APIRouter(prefix="/portal/employee", tags=["portal_employee"])

VIEW = require_employee_portal_permission("portal:employee_view")
CLOCK = require_employee_portal_permission("portal:employee_time_clock")
TIMESHEET = require_employee_portal_permission("portal:employee_timesheet_view")
SCHEDULE = require_employee_portal_permission("portal:employee_schedule_view")
PAY = require_employee_portal_permission("portal:employee_pay_view")
TRAINING = require_employee_portal_permission("portal:employee_training_view")
CERTIFICATION = require_employee_portal_permission("portal:employee_certification_view")
TASKS = require_employee_portal_permission("portal:employee_tasks")
MESSAGES = require_employee_portal_permission("portal:employee_messages")
PROFILE = require_employee_portal_permission("portal:employee_profile")


def _raise(e):
    raise HTTPException(status_code=e.status_code, detail=e.detail)


def _raise_stage(e: ProductionStageError) -> None:
    status = {
        "stage_not_found": 404,
        "work_order_not_found": 404,
        "invalid_transition": 400,
        "previous_stage_incomplete": 409,
        "proof_gate_blocked": 409,
        "reason_required": 400,
        "note_required": 400,
    }.get(e.code, 400)
    raise HTTPException(status_code=status, detail=str(e))


def _pick(doc: Optional[dict], fields: tuple[str, ...]) -> Optional[dict]:
    if doc is None:
        return None
    return {k: doc.get(k) for k in fields if k in doc}


_EMPLOYEE_PORTAL_FIELDS = (
    "id", "name", "preferred_name", "email", "phone", "profile_image_file_id",
    "hire_date", "availability", "availability_blocks", "timezone",
    "emergency_contact_name", "emergency_contact_phone", "created_at", "updated_at",
)
_PORTAL_IDENTITY_FIELDS = ("id", "portal_type", "employee_id", "email", "phone", "full_name")
_TIME_ENTRY_FIELDS = (
    "id", "employee_id", "work_date", "clock_in_at", "clock_out_at", "breaks",
    "total_break_minutes", "worked_minutes", "regular_minutes", "overtime_minutes",
    "status", "source", "work_order_id", "task_id", "notes", "created_at", "updated_at",
)
_SHIFT_FIELDS = (
    "id", "employee_id", "shift_date", "start_at", "end_at", "break_minutes_expected",
    "location", "title", "notes", "work_order_id", "order_id", "status", "created_at", "updated_at",
)
_TIMESHEET_FIELDS = (
    "id", "employee_id", "week_start", "week_end", "status", "worked_minutes",
    "break_minutes", "regular_minutes", "overtime_minutes", "incomplete_entry_count",
    "missed_clock_count", "created_at", "updated_at",
)
_ANNOUNCEMENT_FIELDS = (
    "id", "title", "body", "audience", "acknowledgement_required", "status",
    "published_at", "expires_at", "created_at", "updated_at",
)
_TASK_FIELDS = (
    "id", "title", "description", "status", "priority", "due_at", "assigned_employee_id",
    "employee_visible", "linked_record_label", "available_actions", "created_at", "updated_at",
)
_TASK_COMMENT_FIELDS = (
    "id", "task_id", "author_employee_id", "body", "visibility", "edited_at", "created_at", "updated_at",
)
_TIME_OFF_FIELDS = (
    "id", "employee_id", "requested_by_employee_id", "request_type", "start_at", "end_at",
    "all_day", "reason", "private_reason", "manager_note", "status", "clarification_requested_at",
    "approved_at", "denied_at", "canceled_at", "conflicts", "created_at", "updated_at",
)
_THREAD_FIELDS = (
    "id", "thread_type", "title", "participant_employee_ids", "customer_id", "order_id",
    "order_item_id", "work_order_id", "production_stage_id", "task_id", "calendar_event_id",
    "announcement_id", "visibility", "last_message_at", "unread_count", "created_at", "updated_at",
)
_MESSAGE_FIELDS = (
    "id", "thread_id", "sender_employee_id", "body", "message_type", "visibility",
    "edited_at", "created_at", "updated_at",
)
_PREFERENCE_FIELDS = (
    "id", "identity_type", "identity_id", "in_app_messages", "task_notifications",
    "schedule_changes", "time_off_decisions", "appointment_reminders", "announcements",
    "daily_digest", "email_delivery", "digest_time", "digest_frequency", "quiet_hours",
    "created_at", "updated_at",
)
_DIGEST_FIELDS = ("id", "digest_date", "status", "sections", "delivered_at", "delivery_channel", "created_at", "updated_at")
_PRODUCTION_STAGE_FIELDS = (
    "id", "workflow_instance_id", "order_id", "order_item_id", "work_order_id",
    "stage_key", "stage_name", "description", "sequence", "required", "may_skip",
    "requires_reason_to_skip", "status", "assigned_employee_id", "assigned_role",
    "due_at", "started_at", "completed_at", "blocked_at", "waiting_since",
    "blocker_reason", "completion_note", "proof_gate_type", "employee_visible",
    "requires_previous_stage_complete", "created_at", "updated_at",
)


def _public_employee_view(emp: dict) -> dict:
    return _pick(emp, _EMPLOYEE_PORTAL_FIELDS) or {}


def _public_portal_identity_view(identity: dict) -> dict:
    return _pick(identity, _PORTAL_IDENTITY_FIELDS) or {}


def _public_time_entry_view(entry: Optional[dict]) -> Optional[dict]:
    return _pick(entry, _TIME_ENTRY_FIELDS)


def _public_shift_view(shift: dict) -> dict:
    return _pick(shift, _SHIFT_FIELDS) or {}


def _public_timesheet_view(doc: dict) -> dict:
    return _pick(doc, _TIMESHEET_FIELDS) or {}


def _public_announcement_view(doc: dict) -> dict:
    return _pick(doc, _ANNOUNCEMENT_FIELDS) or {}


def _public_task_view(doc: dict) -> dict:
    return _pick(doc, _TASK_FIELDS) or {}


def _public_task_comment_view(doc: dict) -> dict:
    return _pick(doc, _TASK_COMMENT_FIELDS) or {}


def _public_time_off_view(doc: dict) -> dict:
    return _pick(doc, _TIME_OFF_FIELDS) or {}


def _public_thread_view(doc: dict) -> dict:
    return _pick(doc, _THREAD_FIELDS) or {}


def _public_message_view(doc: dict) -> dict:
    return _pick(doc, _MESSAGE_FIELDS) or {}


def _public_preferences_view(doc: dict) -> dict:
    return _pick(doc, _PREFERENCE_FIELDS) or {}


def _public_digest_view(doc: dict) -> dict:
    return _pick(doc, _DIGEST_FIELDS) or {}


def _public_production_stage_view(doc: dict) -> dict:
    out = _pick(doc, _PRODUCTION_STAGE_FIELDS) or {}
    out["production_notes"] = [
        {k: note.get(k) for k in ("note", "created_at") if k in note}
        for note in doc.get("production_notes") or []
    ]
    return out


def _public_task_collection(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "available": payload.get("available", True),
        "items": [_public_task_view(t) for t in payload.get("items") or []],
        "total": payload.get("total", 0),
        "summary": payload.get("summary"),
    }


def _public_thread_collection(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "items": [_public_thread_view(t) for t in payload.get("items") or []],
        "total": payload.get("total", 0),
        "unread_total": payload.get("unread_total", 0),
    }


async def _get_self_employee(identity: dict) -> dict:
    emp = await db.employees.find_one({"id": identity["employee_id"], "tenant_id": identity["tenant_id"]}, {"_id": 0})
    if not emp:
        raise HTTPException(status_code=404, detail="Employee record not found")
    return emp


async def _refresh_timesheet(tenant_id: str, employee_id: str, entry: dict) -> None:
    await timesheet_service.refresh_after_time_entry_change(
        tenant_id=tenant_id, employee_id=employee_id, work_date=entry["work_date"],
    )


def _portal_actor(identity: dict) -> dict:
    return {
        "id": f"portal:{identity['id']}",
        "tenant_id": identity["tenant_id"],
        "email": identity.get("email") or "employee-portal",
        "role": "employee_portal",
        "permissions": [],
    }


async def _get_own_stage(identity: dict, stage_id: str) -> dict:
    try:
        stage = await production_stage_service.get_stage(tenant_id=identity["tenant_id"], stage_id=stage_id)
    except ProductionStageError as e:
        _raise_stage(e)
    if not bool(stage.get("employee_visible", True)):
        raise HTTPException(status_code=404, detail="Production task not found")
    if stage.get("assigned_employee_id") != identity["employee_id"]:
        raise HTTPException(status_code=403, detail="Production task is not assigned to this employee")
    return stage


# ---- Dashboard ----

@router.get("/dashboard")
async def dashboard(identity: dict = Depends(VIEW)) -> dict:
    tenant_id, employee_id = identity["tenant_id"], identity["employee_id"]
    emp = await _get_self_employee(identity)
    active_entry = await time_clock_service.get_active_entry(tenant_id=tenant_id, employee_id=employee_id)
    from ..services.time_period_utils import business_date, get_tenant_timezone
    tz = await get_tenant_timezone(tenant_id)
    today = business_date(utc_now(), tz)
    today_shifts = await schedule_service.list_shifts(
        tenant_id=tenant_id, employee_id=employee_id, date_from=today, date_to=today, published_only=True,
    )
    next_shifts = await schedule_service.list_shifts(
        tenant_id=tenant_id, employee_id=employee_id, date_from=today, published_only=True,
    )
    next_shift = next((s for s in next_shifts if s["status"] == "scheduled"), None)
    week_summary = await timesheet_service.get_or_create_weekly_timesheet(
        tenant_id=tenant_id, employee_id=employee_id, week_start=today,
    )
    announcements = await announcement_service.active_announcements(tenant_id=tenant_id, limit=3)
    visible_announcements = [
        a for a in announcements if a.get("audience") == "all" or employee_id in (a.get("employee_ids") or [])
    ]
    latest_pay = await _latest_pay_summary(tenant_id, employee_id)
    task_summary = await task_service.list_employee_tasks(tenant_id=tenant_id, employee_id=employee_id)
    return {
        "employee": _public_employee_view(emp),
        "active_entry": _public_time_entry_view(active_entry),
        "today_shifts": [_public_shift_view(s) for s in today_shifts if s["status"] != "cancelled"],
        "next_shift": _public_shift_view(next_shift) if next_shift else None,
        "week_hours": {"worked_minutes": week_summary["worked_minutes"], "week_start": week_summary["week_start"],
                       "week_end": week_summary["week_end"]},
        "timesheet_status": week_summary["status"],
        "announcements": [_public_announcement_view(a) for a in visible_announcements],
        "tasks": {"available": True, "items": [_public_task_view(t) for t in task_summary["items"][:3]], "total": task_summary["total"]},
        "pay": latest_pay,
    }


# ---- Production / Kiosk (EC11 Phase 11E) ----

class ProductionActionIn(BaseModel):
    reason: Optional[str] = None
    completion_note: Optional[str] = None
    note: Optional[str] = None


@router.get("/production")
async def production_home(search: Optional[str] = None, identity: dict = Depends(VIEW)) -> dict:
    await _get_self_employee(identity)
    return await production_board_service.get_employee_production_view(
        tenant_id=identity["tenant_id"],
        employee_id=identity["employee_id"],
        search=search,
    )


@router.post("/production/stages/{stage_id}/start")
async def production_start(stage_id: str, identity: dict = Depends(VIEW)) -> dict:
    await _get_own_stage(identity, stage_id)
    try:
        stage = await production_stage_service.transition_stage(
            tenant_id=identity["tenant_id"], stage_id=stage_id, target="in_progress", user=_portal_actor(identity),
        )
        return _public_production_stage_view(stage)
    except ProductionStageError as e:
        _raise_stage(e)


@router.post("/production/stages/{stage_id}/resume")
async def production_resume(stage_id: str, identity: dict = Depends(VIEW)) -> dict:
    await _get_own_stage(identity, stage_id)
    try:
        stage = await production_stage_service.transition_stage(
            tenant_id=identity["tenant_id"], stage_id=stage_id, target="in_progress", user=_portal_actor(identity),
        )
        return _public_production_stage_view(stage)
    except ProductionStageError as e:
        _raise_stage(e)


@router.post("/production/stages/{stage_id}/wait")
async def production_wait(stage_id: str, payload: ProductionActionIn, identity: dict = Depends(VIEW)) -> dict:
    await _get_own_stage(identity, stage_id)
    try:
        stage = await production_stage_service.transition_stage(
            tenant_id=identity["tenant_id"], stage_id=stage_id, target="waiting",
            user=_portal_actor(identity), reason=payload.reason,
        )
        return _public_production_stage_view(stage)
    except ProductionStageError as e:
        _raise_stage(e)


@router.post("/production/stages/{stage_id}/block")
async def production_block(stage_id: str, payload: ProductionActionIn, identity: dict = Depends(VIEW)) -> dict:
    await _get_own_stage(identity, stage_id)
    try:
        stage = await production_stage_service.transition_stage(
            tenant_id=identity["tenant_id"], stage_id=stage_id, target="blocked",
            user=_portal_actor(identity), reason=payload.reason,
        )
        return _public_production_stage_view(stage)
    except ProductionStageError as e:
        _raise_stage(e)


@router.post("/production/stages/{stage_id}/complete")
async def production_complete(stage_id: str, payload: ProductionActionIn, identity: dict = Depends(VIEW)) -> dict:
    await _get_own_stage(identity, stage_id)
    try:
        stage = await production_stage_service.transition_stage(
            tenant_id=identity["tenant_id"], stage_id=stage_id, target="completed",
            user=_portal_actor(identity), completion_note=payload.completion_note,
        )
        return _public_production_stage_view(stage)
    except ProductionStageError as e:
        _raise_stage(e)


@router.post("/production/stages/{stage_id}/notes")
async def production_note(stage_id: str, payload: ProductionActionIn, identity: dict = Depends(VIEW)) -> dict:
    await _get_own_stage(identity, stage_id)
    try:
        stage = await production_stage_service.add_stage_note(
            tenant_id=identity["tenant_id"], stage_id=stage_id, note=payload.note or "", user=_portal_actor(identity),
        )
        return _public_production_stage_view(stage)
    except ProductionStageError as e:
        _raise_stage(e)


# ---- Time Clock (thin wrappers over the Phase 8b service — no duplicate logic) ----

class ClockInIn(BaseModel):
    work_order_id: Optional[str] = None
    notes: Optional[str] = None


@router.get("/time-clock/me")
async def time_clock_me(identity: dict = Depends(CLOCK)) -> dict:
    active = await time_clock_service.get_active_entry(tenant_id=identity["tenant_id"], employee_id=identity["employee_id"])
    return {"active_entry": _public_time_entry_view(active)}


@router.post("/time-clock/clock-in")
async def clock_in(payload: ClockInIn, identity: dict = Depends(CLOCK)) -> dict:
    try:
        entry = await time_clock_service.clock_in(
            tenant_id=identity["tenant_id"], employee_id=identity["employee_id"],
            actor_user_id=f"portal:{identity['id']}", actor_email=identity["email"],
            source="self", work_order_id=payload.work_order_id, notes=payload.notes,
        )
        return _public_time_entry_view(entry) or {}
    except TimeEntryError as e:
        _raise(e)


@router.post("/time-clock/clock-out")
async def clock_out(identity: dict = Depends(CLOCK)) -> dict:
    try:
        entry = await time_clock_service.clock_out(
            tenant_id=identity["tenant_id"], employee_id=identity["employee_id"],
            actor_user_id=f"portal:{identity['id']}", actor_email=identity["email"],
        )
        await _refresh_timesheet(identity["tenant_id"], identity["employee_id"], entry)
        return _public_time_entry_view(entry) or {}
    except TimeEntryError as e:
        _raise(e)


@router.post("/time-clock/break-start")
async def break_start(identity: dict = Depends(CLOCK)) -> dict:
    try:
        entry = await time_clock_service.start_break(
            tenant_id=identity["tenant_id"], employee_id=identity["employee_id"],
            actor_user_id=f"portal:{identity['id']}", actor_email=identity["email"],
        )
        return _public_time_entry_view(entry) or {}
    except TimeEntryError as e:
        _raise(e)


@router.post("/time-clock/break-end")
async def break_end(identity: dict = Depends(CLOCK)) -> dict:
    try:
        entry = await time_clock_service.end_break(
            tenant_id=identity["tenant_id"], employee_id=identity["employee_id"],
            actor_user_id=f"portal:{identity['id']}", actor_email=identity["email"],
        )
        return _public_time_entry_view(entry) or {}
    except TimeEntryError as e:
        _raise(e)


# ---- My Schedule (published-only, self-scoped) ----

@router.get("/schedule/today")
async def schedule_today(identity: dict = Depends(SCHEDULE)) -> dict:
    from ..services.time_period_utils import business_date, get_tenant_timezone
    tz = await get_tenant_timezone(identity["tenant_id"])
    today = business_date(utc_now(), tz)
    items = await schedule_service.list_shifts(
        tenant_id=identity["tenant_id"], employee_id=identity["employee_id"],
        date_from=today, date_to=today, published_only=True,
    )
    return {"date": today, "items": [_public_shift_view(s) for s in items]}


@router.get("/schedule/week")
async def schedule_week(week_start: Optional[str] = None, identity: dict = Depends(SCHEDULE)) -> dict:
    from ..services.time_period_utils import business_date, get_tenant_timezone, week_bounds_for_date_str
    tz = await get_tenant_timezone(identity["tenant_id"])
    anchor = week_start or business_date(utc_now(), tz)
    start, end = week_bounds_for_date_str(anchor)
    items = await schedule_service.list_shifts(
        tenant_id=identity["tenant_id"], employee_id=identity["employee_id"],
        date_from=start, date_to=end, published_only=True,
    )
    return {"week_start": start, "week_end": end, "items": [_public_shift_view(s) for s in items]}


# ---- My Timesheet (self-scoped, read-only — no approval action here) ----

# EC8 phase 8c — Timesheet fields that must stay in the (future) Phase 8d "My
# Pay" surface, not here. `estimated_gross_cents` is derived from the payroll
# rate; even though it isn't the rate itself, it lets an employee reverse
# it out of their known hours, so it is stripped from every portal response.
_TIMESHEET_HIDDEN_FIELDS = {"estimated_gross_cents"}


@router.get("/timesheet/summary")
async def timesheet_summary(period: str, date: str, identity: dict = Depends(TIMESHEET)) -> dict:
    try:
        result = await timesheet_service.period_summary(
            tenant_id=identity["tenant_id"], employee_id=identity["employee_id"], period=period, date_str=date,
        )
        return _public_timesheet_view(result)
    except TimesheetError as e:
        _raise(e)


@router.get("/timesheet/weekly")
async def timesheet_weekly(week_start: str, identity: dict = Depends(TIMESHEET)) -> dict:
    result = await timesheet_service.get_or_create_weekly_timesheet(
        tenant_id=identity["tenant_id"], employee_id=identity["employee_id"], week_start=week_start,
    )
    return _public_timesheet_view(result)


# ---- My Pay (self-scoped, EC8 phase 8d — reuses the Phase 8d payroll ledger,
# no parallel pay system). Strict allow-list of fields: never manager notes,
# other employees, audit internals, bank info, or tax data.) ----

_PAY_SNAPSHOT_FIELDS = (
    "pay_period_id", "period_start", "period_end", "payday", "period_status",
    "regular_minutes", "overtime_minutes", "hourly_rate_cents",
    "gross_regular_cents", "gross_overtime_cents", "adjustment_total_cents",
    "advance_total_cents", "repayment_total_cents", "payment_total_cents",
    "carryover_in_cents", "carryover_out_cents", "total_earned_cents",
    "total_paid_cents", "remaining_balance_cents",
)
_PAY_TXN_FIELDS = ("pay_period_id", "type", "amount_cents", "effective_date", "reference", "payment_method", "payment_date")


def _public_pay_view(snapshot: dict) -> dict:
    return {k: snapshot.get(k) for k in _PAY_SNAPSHOT_FIELDS}


def _public_txn_view(txn: dict) -> dict:
    return {k: txn.get(k) for k in _PAY_TXN_FIELDS}


async def _latest_pay_summary(tenant_id: str, employee_id: str) -> Optional[dict]:
    snaps = await payroll_service.list_employee_snapshots(tenant_id=tenant_id, employee_id=employee_id, limit=1)
    if not snaps:
        return None
    return _public_pay_view(snaps[0])


@router.get("/pay/summary")
async def pay_summary(identity: dict = Depends(PAY)) -> dict:
    latest = await _latest_pay_summary(identity["tenant_id"], identity["employee_id"])
    return {"latest_period": latest}


@router.get("/pay/periods")
async def pay_periods(identity: dict = Depends(PAY)) -> dict:
    snaps = await payroll_service.list_employee_snapshots(tenant_id=identity["tenant_id"], employee_id=identity["employee_id"])
    return {"items": [_public_pay_view(s) for s in snaps]}


@router.get("/pay/transactions")
async def pay_transactions(pay_period_id: Optional[str] = None, identity: dict = Depends(PAY)) -> dict:
    txns = await payroll_service.list_transactions(
        tenant_id=identity["tenant_id"], employee_id=identity["employee_id"], pay_period_id=pay_period_id,
    )
    return {"items": [_public_txn_view(t) for t in txns]}


# ---- My Training (self-scoped, EC8 phase 8e — reuses the Phase 8e training
# service, no parallel training system). Answer keys are always stripped via
# `training_service.public_definition_view`; a client-supplied employee_id is
# never trusted — everything resolves from `identity["employee_id"]`.) ----

_ASSIGNMENT_HIDDEN_FIELDS = {"manager_notes", "created_by", "updated_by", "renewal_of"}


def _public_assignment_view(a: dict) -> dict:
    return {k: v for k, v in a.items() if k not in _ASSIGNMENT_HIDDEN_FIELDS}


@router.get("/training/assignments")
async def my_training_assignments(status: Optional[str] = None, identity: dict = Depends(TRAINING)) -> dict:
    status_in = [status] if status else None
    items = await training_service.list_assignments(tenant_id=identity["tenant_id"], employee_id=identity["employee_id"], status_in=status_in)
    return {"items": [_public_assignment_view(a) for a in items]}


@router.get("/training/assignments/{assignment_id}")
async def my_training_assignment_detail(assignment_id: str, identity: dict = Depends(TRAINING)) -> dict:
    try:
        a = await training_service.get_assignment(tenant_id=identity["tenant_id"], assignment_id=assignment_id)
        if a["employee_id"] != identity["employee_id"]:
            raise HTTPException(status_code=403, detail="This Training Assignment belongs to a different Employee")
        defn = await training_service.get_training_definition(tenant_id=identity["tenant_id"], training_definition_id=a["training_definition_id"])
        docs = await training_service.list_documents(tenant_id=identity["tenant_id"], training_definition_id=a["training_definition_id"], portal_visible_only=True)
        attempts = await training_service.list_quiz_attempts(tenant_id=identity["tenant_id"], assignment_id=assignment_id)
        return {
            **_public_assignment_view(a), "definition": public_definition_view(defn), "documents": docs,
            "quiz_attempts": [{"attempt_number": at["attempt_number"], "score": at["score"], "passed": at["passed"], "completed_at": at["completed_at"]} for at in attempts],
        }
    except TrainingError as e:
        _raise(e)


@router.post("/training/assignments/{assignment_id}/start")
async def start_my_training(assignment_id: str, identity: dict = Depends(TRAINING)) -> dict:
    try:
        return _public_assignment_view(await training_service.start_assignment(tenant_id=identity["tenant_id"], assignment_id=assignment_id, employee_id=identity["employee_id"]))
    except TrainingError as e:
        _raise(e)


@router.post("/training/assignments/{assignment_id}/complete")
async def complete_my_training(assignment_id: str, identity: dict = Depends(TRAINING)) -> dict:
    try:
        return _public_assignment_view(await training_service.complete_assignment(
            tenant_id=identity["tenant_id"], assignment_id=assignment_id, employee_id=identity["employee_id"],
            actor_user_id=f"portal:{identity['id']}", actor_email=identity.get("email", "employee-portal"),
        ))
    except TrainingError as e:
        _raise(e)


class QuizSubmitIn(BaseModel):
    answers: list[dict]
    started_at: str


@router.post("/training/assignments/{assignment_id}/quiz")
async def submit_my_quiz(assignment_id: str, payload: QuizSubmitIn, identity: dict = Depends(TRAINING)) -> dict:
    try:
        attempt = await training_service.submit_quiz_attempt(
            tenant_id=identity["tenant_id"], assignment_id=assignment_id, employee_id=identity["employee_id"],
            answers=payload.answers, started_at=payload.started_at,
            actor_user_id=f"portal:{identity['id']}", actor_email=identity.get("email", "employee-portal"),
        )
        return {"score": attempt["score"], "passed": attempt["passed"], "attempt_number": attempt["attempt_number"]}
    except TrainingError as e:
        _raise(e)


# ---- My Certifications (self-scoped, EC8 phase 8e) ----

_CERT_HIDDEN_FIELDS = {"trainer_user_id", "revoked_by", "created_by", "updated_by"}


def _public_certification_view(c: dict) -> dict:
    return {k: v for k, v in c.items() if k not in _CERT_HIDDEN_FIELDS}


@router.get("/certifications")
async def my_certifications(identity: dict = Depends(CERTIFICATION)) -> dict:
    items = await certification_service.list_certifications(tenant_id=identity["tenant_id"], employee_id=identity["employee_id"])
    return {"items": [_public_certification_view(c) for c in items]}


# ---- Announcements (reuses Phase 8a Announcement — no second messaging system) ----

@router.get("/announcements")
async def announcements(identity: dict = Depends(VIEW)) -> dict:
    all_active = await announcement_service.active_announcements(tenant_id=identity["tenant_id"], limit=20)
    visible = [
        a for a in all_active
        if a.get("audience") == "all" or identity["employee_id"] in (a.get("employee_ids") or [])
    ]
    return {"items": [_public_announcement_view(a) for a in visible]}


class PortalTaskActionIn(BaseModel):
    reason: Optional[str] = None


class PortalTaskCommentIn(BaseModel):
    body: str


class PortalMessageIn(BaseModel):
    body: str
    idempotency_key: Optional[str] = None


class PortalPreferenceIn(BaseModel):
    in_app_messages: Optional[bool] = None
    task_notifications: Optional[bool] = None
    schedule_changes: Optional[bool] = None
    time_off_decisions: Optional[bool] = None
    appointment_reminders: Optional[bool] = None
    announcements: Optional[bool] = None
    daily_digest: Optional[bool] = None
    email_delivery: Optional[bool] = None
    digest_time: Optional[str] = None
    digest_frequency: Optional[str] = None
    quiet_hours: Optional[dict] = None


@router.get("/tasks")
async def my_tasks(status: Optional[str] = None, view: Optional[str] = None, identity: dict = Depends(TASKS)) -> dict:
    payload = await task_service.list_employee_tasks(
        tenant_id=identity["tenant_id"], employee_id=identity["employee_id"], status=status, view=view,
    )
    return _public_task_collection(payload)


@router.get("/tasks/{task_id}")
async def task_detail(task_id: str, identity: dict = Depends(TASKS)) -> dict:
    try:
        task = await task_service.get_employee_task(
            tenant_id=identity["tenant_id"], employee_id=identity["employee_id"], task_id=task_id,
        )
        comments = await task_service.list_comments(
            tenant_id=identity["tenant_id"], task_id=task_id, employee_visible_only=True,
        )
        return {
            "task": _public_task_view(task),
            "comments": [_public_task_comment_view(c) for c in comments],
        }
    except TaskError as e:
        _raise(e)


class TimeOffCreateIn(BaseModel):
    request_type: str = "other"
    start_at: str
    end_at: str
    all_day: bool = False
    reason: Optional[str] = None
    private_reason: Optional[str] = None


class TimeOffClarificationIn(BaseModel):
    response: str
    private_reason: Optional[str] = None


class TimeOffCancelIn(BaseModel):
    reason: Optional[str] = None


@router.get("/time-off")
async def my_time_off(status: Optional[str] = None, identity: dict = Depends(SCHEDULE)) -> dict:
    payload = await time_off_service.list_requests(
        tenant_id=identity["tenant_id"], employee_id=identity["employee_id"], status=status, include_private=True,
    )
    return {
        "items": [_public_time_off_view(t) for t in payload.get("items") or []],
        "total": payload.get("total", 0),
        "limit": payload.get("limit"),
        "skip": payload.get("skip"),
    }


@router.post("/time-off", status_code=201)
async def submit_time_off(payload: TimeOffCreateIn, identity: dict = Depends(SCHEDULE)) -> dict:
    try:
        request = await time_off_service.create_request(
            tenant_id=identity["tenant_id"], employee_id=identity["employee_id"],
            actor_employee_id=identity["employee_id"], actor_email=identity.get("email", "employee-portal"),
            payload=payload.model_dump(exclude_none=True),
        )
        return _public_time_off_view(request)
    except TimeOffError as e:
        _raise(e)


@router.get("/time-off/{request_id}")
async def my_time_off_detail(request_id: str, identity: dict = Depends(SCHEDULE)) -> dict:
    try:
        request = await time_off_service.employee_get_request(
            tenant_id=identity["tenant_id"], employee_id=identity["employee_id"], request_id=request_id,
        )
        return _public_time_off_view(request)
    except TimeOffError as e:
        _raise(e)


@router.post("/time-off/{request_id}/clarification")
async def respond_time_off(request_id: str, payload: TimeOffClarificationIn, identity: dict = Depends(SCHEDULE)) -> dict:
    try:
        request = await time_off_service.respond_to_clarification(
            tenant_id=identity["tenant_id"], request_id=request_id, employee_id=identity["employee_id"],
            actor_email=identity.get("email", "employee-portal"), response=payload.response,
            private_reason=payload.private_reason,
        )
        return _public_time_off_view(request)
    except TimeOffError as e:
        _raise(e)


@router.post("/time-off/{request_id}/cancel")
async def cancel_time_off(request_id: str, payload: TimeOffCancelIn, identity: dict = Depends(SCHEDULE)) -> dict:
    try:
        request = await time_off_service.cancel_request(
            tenant_id=identity["tenant_id"], request_id=request_id, employee_id=identity["employee_id"],
            actor_email=identity.get("email", "employee-portal"), reason=payload.reason,
        )
        return _public_time_off_view(request)
    except TimeOffError as e:
        _raise(e)


@router.get("/calendar")
async def my_calendar(start_at: str, end_at: str, identity: dict = Depends(SCHEDULE)) -> dict:
    try:
        feed = await calendar_service.employee_feed(
            tenant_id=identity["tenant_id"], employee_id=identity["employee_id"], start_at=start_at, end_at=end_at,
        )
        return {
            "items": [
                {k: event.get(k) for k in (
                    "id", "title", "description", "start_at", "end_at", "all_day",
                    "event_type", "status", "employee_id", "work_order_id", "order_id",
                    "time_off_request_id", "created_at", "updated_at",
                ) if k in event}
                for event in feed.get("items", [])
            ],
            "total": feed.get("total", len(feed.get("items", []))),
        }
    except CalendarError as e:
        _raise(e)


async def _task_transition(identity: dict, task_id: str, target: str, payload: PortalTaskActionIn) -> dict:
    try:
        task = await task_service.transition_task(
            tenant_id=identity["tenant_id"], task_id=task_id, target=target,
            actor_user_id=f"portal:{identity['id']}", actor_email=identity.get("email", "employee-portal"),
            actor_employee_id=identity["employee_id"], reason=payload.reason, allow_employee=True,
        )
        return _public_task_view(task)
    except TaskError as e:
        _raise(e)


@router.post("/tasks/{task_id}/start")
async def task_start(task_id: str, payload: PortalTaskActionIn, identity: dict = Depends(TASKS)) -> dict:
    return await _task_transition(identity, task_id, "in_progress", payload)


@router.post("/tasks/{task_id}/resume")
async def task_resume(task_id: str, payload: PortalTaskActionIn, identity: dict = Depends(TASKS)) -> dict:
    return await _task_transition(identity, task_id, "in_progress", payload)


@router.post("/tasks/{task_id}/wait")
async def task_wait(task_id: str, payload: PortalTaskActionIn, identity: dict = Depends(TASKS)) -> dict:
    return await _task_transition(identity, task_id, "waiting", payload)


@router.post("/tasks/{task_id}/block")
async def task_block(task_id: str, payload: PortalTaskActionIn, identity: dict = Depends(TASKS)) -> dict:
    return await _task_transition(identity, task_id, "blocked", payload)


@router.post("/tasks/{task_id}/complete")
async def task_complete(task_id: str, payload: PortalTaskActionIn, identity: dict = Depends(TASKS)) -> dict:
    return await _task_transition(identity, task_id, "completed", payload)


@router.get("/tasks/{task_id}/comments")
async def task_comments(task_id: str, identity: dict = Depends(TASKS)) -> dict:
    try:
        await task_service.get_employee_task(
            tenant_id=identity["tenant_id"], employee_id=identity["employee_id"], task_id=task_id,
        )
        comments = await task_service.list_comments(
            tenant_id=identity["tenant_id"], task_id=task_id, employee_visible_only=True,
        )
        return {"items": [_public_task_comment_view(c) for c in comments]}
    except TaskError as e:
        _raise(e)


@router.post("/tasks/{task_id}/comments", status_code=201)
async def task_add_comment(task_id: str, payload: PortalTaskCommentIn, identity: dict = Depends(TASKS)) -> dict:
    try:
        comment = await task_service.add_comment(
            tenant_id=identity["tenant_id"], task_id=task_id,
            actor_user_id=f"portal:{identity['id']}", actor_email=identity.get("email", "employee-portal"),
            author_employee_id=identity["employee_id"], body=payload.body, employee_scope=True,
        )
        return _public_task_comment_view(comment)
    except TaskError as e:
        _raise(e)


# ---- Messages, preferences, and digest (self-scoped EC12 Phase 12E/12F) ----

@router.get("/messages")
async def my_message_threads(q: Optional[str] = None, identity: dict = Depends(MESSAGES)) -> dict:
    try:
        payload = await communication_service.list_threads(
            tenant_id=identity["tenant_id"], identity_type="employee", identity_id=identity["employee_id"], q=q,
        )
        return _public_thread_collection(payload)
    except CommunicationError as e:
        _raise(e)


@router.get("/messages/{thread_id}")
async def my_message_thread(thread_id: str, identity: dict = Depends(MESSAGES)) -> dict:
    try:
        thread = await communication_service.get_thread(
            tenant_id=identity["tenant_id"], thread_id=thread_id,
            identity_type="employee", identity_id=identity["employee_id"],
        )
        messages = await communication_service.list_messages(
            tenant_id=identity["tenant_id"], thread_id=thread_id,
            identity_type="employee", identity_id=identity["employee_id"],
        )
        return {
            "thread": _public_thread_view(thread),
            "messages": [_public_message_view(m) for m in messages["items"]],
        }
    except CommunicationError as e:
        _raise(e)


@router.post("/messages/{thread_id}/messages", status_code=201)
async def my_send_message(thread_id: str, payload: PortalMessageIn, identity: dict = Depends(MESSAGES)) -> dict:
    try:
        message = await communication_service.send_message(
            tenant_id=identity["tenant_id"], thread_id=thread_id, body=payload.body,
            actor_employee_id=identity["employee_id"], actor_email=identity.get("email", "employee-portal"),
            idempotency_key=payload.idempotency_key,
        )
        return _public_message_view(message)
    except CommunicationError as e:
        _raise(e)


@router.post("/messages/{thread_id}/read")
async def my_mark_message_read(thread_id: str, identity: dict = Depends(MESSAGES)) -> dict:
    try:
        return await communication_service.mark_thread_read(
            tenant_id=identity["tenant_id"], thread_id=thread_id,
            identity_type="employee", identity_id=identity["employee_id"],
        )
    except CommunicationError as e:
        _raise(e)


@router.get("/preferences")
async def my_preferences(identity: dict = Depends(PROFILE)) -> dict:
    prefs = await communication_service.get_preferences(
        tenant_id=identity["tenant_id"], identity_type="employee", identity_id=identity["employee_id"],
    )
    return _public_preferences_view(prefs)


@router.patch("/preferences")
async def update_my_preferences(payload: PortalPreferenceIn, identity: dict = Depends(PROFILE)) -> dict:
    prefs = await communication_service.update_preferences(
        tenant_id=identity["tenant_id"], identity_type="employee", identity_id=identity["employee_id"],
        actor_employee_id=identity["employee_id"], actor_email=identity.get("email", "employee-portal"),
        updates=payload.model_dump(exclude_none=True),
    )
    return _public_preferences_view(prefs)


@router.get("/digest/preview")
async def my_digest_preview(digest_date: Optional[str] = None, identity: dict = Depends(MESSAGES)) -> dict:
    digest = await communication_service.preview_digest(
        tenant_id=identity["tenant_id"], recipient_type="employee",
        recipient_id=identity["employee_id"], digest_date=digest_date,
    )
    return _public_digest_view(digest)


@router.post("/digest/generate")
async def my_digest_generate(digest_date: Optional[str] = None, identity: dict = Depends(MESSAGES)) -> dict:
    digest = await communication_service.generate_digest(
        tenant_id=identity["tenant_id"], recipient_type="employee",
        recipient_id=identity["employee_id"], digest_date=digest_date,
    )
    return _public_digest_view(digest)


# ---- Profile ----

@router.get("/profile")
async def profile(identity: dict = Depends(PROFILE)) -> dict:
    emp = await _get_self_employee(identity)
    prefs = await communication_service.get_preferences(
        tenant_id=identity["tenant_id"], identity_type="employee", identity_id=identity["employee_id"],
    )
    return {
        "employee": _public_employee_view(emp),
        "portal_email": identity["email"],
        "portal_phone": identity.get("phone"),
        "portal_full_name": identity.get("full_name"),
        "preferences": _public_preferences_view(prefs),
    }


class ProfileUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phone: Optional[str] = None
    full_name: Optional[str] = None
    preferred_name: Optional[str] = None
    contact_email: Optional[str] = None
    profile_image_file_id: Optional[str] = None
    availability: Optional[str] = None
    timezone: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    availability_blocks: Optional[list[dict]] = None


@router.patch("/profile")
async def update_profile(payload: ProfileUpdateIn, identity: dict = Depends(PROFILE)) -> dict:
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No updates")
    forbidden = {"hourly_rate_cents", "role_label", "status", "linked_user_id", "overtime_policy", "portal_access"}
    if forbidden.intersection(updates):
        raise HTTPException(status_code=400, detail="Protected employment fields cannot be changed from the Employee Portal")
    tenant_id, employee_id = identity["tenant_id"], identity["employee_id"]
    portal_updates = {k: updates[k] for k in ("phone", "full_name") if k in updates}
    employee_updates: dict = {}
    if "preferred_name" in updates:
        employee_updates["preferred_name"] = updates["preferred_name"]
    if "contact_email" in updates:
        employee_updates["email"] = updates["contact_email"]
    if "phone" in updates:
        employee_updates["phone"] = updates["phone"]
    if "availability" in updates:
        employee_updates["availability"] = updates["availability"]
    if "timezone" in updates:
        employee_updates["timezone"] = updates["timezone"]
    if "emergency_contact_name" in updates:
        employee_updates["emergency_contact_name"] = updates["emergency_contact_name"]
    if "emergency_contact_phone" in updates:
        employee_updates["emergency_contact_phone"] = updates["emergency_contact_phone"]
    if "availability_blocks" in updates:
        blocks = []
        for block in updates["availability_blocks"] or []:
            blocks.append({
                "id": str(block.get("id") or f"avail-{len(blocks) + 1}"),
                "kind": block.get("kind") if block.get("kind") in {"unavailable", "preferred"} else "unavailable",
                "day_of_week": block.get("day_of_week"),
                "date_from": block.get("date_from"),
                "date_to": block.get("date_to"),
                "start_time": block.get("start_time"),
                "end_time": block.get("end_time"),
                "note": block.get("note"),
                "created_at": utc_now().isoformat(),
                "created_by": f"portal:{identity['id']}",
            })
        employee_updates["availability_blocks"] = blocks
    if "profile_image_file_id" in updates:
        file_id = updates["profile_image_file_id"]
        if file_id and str(file_id).startswith("data:"):
            raise HTTPException(status_code=400, detail="Profile image must reference an uploaded file")
        if file_id:
            file_doc = await db.files.find_one({"tenant_id": tenant_id, "id": file_id}, {"_id": 0, "id": 1})
            if not file_doc:
                raise HTTPException(status_code=404, detail="Profile image file not found")
        employee_updates["profile_image_file_id"] = file_id
    now = utc_now().isoformat()
    if employee_updates:
        employee_updates["updated_at"] = now
        await db.employees.update_one({"tenant_id": tenant_id, "id": employee_id}, {"$set": employee_updates})
        await record_activity_with_audit(
            tenant_id=tenant_id, actor_user_id=f"portal:{identity['id']}", actor_email=identity.get("email", "employee-portal"),
            module="team", action="employee.profile_updated", entity_type="employee", entity_id=employee_id,
            summary="Employee Portal profile updated",
            metadata={"fields": sorted(k for k in employee_updates.keys() if k != "updated_at")},
        )
    updated_identity = None
    if portal_updates:
        updated_identity = await update_portal_identity(identity_id=identity["id"], tenant_id=tenant_id, updates=portal_updates)
        updated_identity.pop("password_hash", None)
    emp = await _get_self_employee(identity)
    return {
        "employee": _public_employee_view(emp),
        "portal": _public_portal_identity_view(
            updated_identity or {"id": identity["id"], "portal_type": identity.get("portal_type"), "employee_id": identity.get("employee_id"), "email": identity["email"], "phone": identity.get("phone"), "full_name": identity.get("full_name")}
        ),
    }
