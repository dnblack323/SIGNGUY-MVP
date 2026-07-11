"""EC5 — Work Orders router (extended for lifecycle + versioning + summary + board)."""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..core.db import db
from ..core.permissions import Perm
from ..core.time_utils import serialize_doc, utc_now
from ..deps import require_permission
from ..models.work_order import effective_status
from ..services.work_order_service import (
    ALLOWED_TRANSITIONS, assign, build_summary, generate, regenerate, transition,
)
from ..services.audit import record_audit

router = APIRouter(prefix="/work-orders", tags=["work_orders"])
prod_router = APIRouter(prefix="/production", tags=["production"])

_ERR = {
    "order_not_found": (404, "Order not found"),
    "work_order_not_found": (404, "Work order not found"),
    "no_production_required_items": (400, "No production-required items on this order"),
    "reason_required": (400, "Reason is required"),
    "work_order_not_regeneratable": (400, "Work order cannot be regenerated"),
}


def _raise(ex: Exception) -> None:
    msg = str(ex)
    if msg.startswith("invalid_transition:"):
        raise HTTPException(status_code=400, detail=f"Invalid transition ({msg.split(':', 1)[1]})")
    if msg.startswith("assignee_not_found:"):
        raise HTTPException(status_code=400, detail=f"Assignee not found in tenant")
    st, det = _ERR.get(msg, (400, msg))
    raise HTTPException(status_code=st, detail=det)


# ---- Payloads ----


class GenerateIn(BaseModel):
    order_id: str
    priority: Literal["low", "normal", "high", "rush"] = "normal"
    due_date: Optional[str] = None
    production_instructions: Optional[str] = None
    internal_notes: Optional[str] = None
    assigned_user_ids: list[str] = Field(default_factory=list)


class LegacyCreateIn(BaseModel):
    order_id: str
    production_instructions: Optional[str] = None
    internal_notes: Optional[str] = None
    assigned_to: Optional[str] = None


class TransitionIn(BaseModel):
    target: Literal["draft", "released", "queued", "in_progress", "blocked", "ready", "completed", "cancelled"]
    reason: Optional[str] = None


class LegacyStatusIn(BaseModel):
    production_status: str


class RegenerateIn(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class AssignIn(BaseModel):
    user_ids: list[str] = Field(default_factory=list)


class PatchIn(BaseModel):
    production_instructions: Optional[str] = None
    internal_notes: Optional[str] = None
    priority: Optional[Literal["low", "normal", "high", "rush"]] = None
    due_date: Optional[str] = None
    department: Optional[str] = None


# ---- List / Detail ----


@router.get("")
async def list_wos(
    production_status: Optional[str] = Query(None),
    order_id: Optional[str] = Query(None),
    customer_id: Optional[str] = Query(None),
    current_only: bool = Query(False),
    limit: int = Query(50, le=200), skip: int = Query(0, ge=0),
    user: dict = Depends(require_permission(Perm.WORK_ORDER_READ)),
) -> dict:
    q: dict = {"tenant_id": user["tenant_id"]}
    if production_status:
        q["production_status"] = production_status
    if order_id:
        q["order_id"] = order_id
    if customer_id:
        q["customer_id"] = customer_id
    if current_only:
        q["current_version"] = True
    total = await db.work_orders.count_documents(q)
    cursor = db.work_orders.find(q, {"_id": 0}).sort("number", -1).skip(skip).limit(limit)
    return {"items": [serialize_doc(d) async for d in cursor], "total": total, "limit": limit, "skip": skip}


@router.get("/{wo_id}")
async def get_wo(wo_id: str, user: dict = Depends(require_permission(Perm.WORK_ORDER_READ))) -> dict:
    doc = await db.work_orders.find_one({"id": wo_id, "tenant_id": user["tenant_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Work order not found")
    return serialize_doc(doc)


# ---- Generation ----


@router.post("", status_code=201)
async def generate_wo(
    payload: GenerateIn | LegacyCreateIn,
    user: dict = Depends(require_permission(Perm.WORK_ORDER_WRITE)),
) -> dict:
    """Preserves the legacy `{order_id, production_instructions, internal_notes, assigned_to}` shape."""
    order_id = getattr(payload, "order_id", None)
    priority = getattr(payload, "priority", "normal")
    due_date = getattr(payload, "due_date", None)
    prod_notes = getattr(payload, "production_instructions", None)
    int_notes = getattr(payload, "internal_notes", None)
    assignees = getattr(payload, "assigned_user_ids", None) or (
        [payload.assigned_to] if getattr(payload, "assigned_to", None) else []
    )
    try:
        wo, already = await generate(
            tenant_id=user["tenant_id"], order_id=order_id,
            actor_user_id=user["id"], actor_email=user["email"],
            priority=priority, due_date=due_date,
            production_instructions=prod_notes, internal_notes=int_notes,
            assigned_user_ids=assignees,
        )
        if already:
            return {**wo, "already_exists": True}
        return wo
    except ValueError as ex:
        _raise(ex)


@router.post("/{wo_id}/regenerate", status_code=201)
async def regenerate_wo(
    wo_id: str, payload: RegenerateIn,
    user: dict = Depends(require_permission(Perm.WORK_ORDER_WRITE)),
) -> dict:
    try:
        return await regenerate(
            tenant_id=user["tenant_id"], work_order_id=wo_id, reason=payload.reason,
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except ValueError as ex:
        _raise(ex)


# ---- Mutations ----


@router.patch("/{wo_id}")
async def patch_wo(wo_id: str, payload: PatchIn, user: dict = Depends(require_permission(Perm.WORK_ORDER_WRITE))) -> dict:
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No updates")
    updates["updated_at"] = utc_now().isoformat()
    res = await db.work_orders.update_one({"id": wo_id, "tenant_id": user["tenant_id"]}, {"$set": updates})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Work order not found")
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="work_order.update", entity_type="work_order", entity_id=wo_id,
        summary="Work order updated", diff={"changes": updates},
    )
    doc = await db.work_orders.find_one({"id": wo_id}, {"_id": 0})
    return serialize_doc(doc)


@router.post("/{wo_id}/transition")
async def transition_wo(wo_id: str, payload: TransitionIn, user: dict = Depends(require_permission(Perm.WORK_ORDER_WRITE))) -> dict:
    try:
        return await transition(
            tenant_id=user["tenant_id"], work_order_id=wo_id,
            target=payload.target, reason=payload.reason,
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except ValueError as ex:
        _raise(ex)


@router.post("/{wo_id}/production-status")
async def legacy_status(
    wo_id: str, payload: LegacyStatusIn,
    user: dict = Depends(require_permission(Perm.WORK_ORDER_WRITE)),
) -> dict:
    """Legacy MVP endpoint — maps old enum values to new via effective_status."""
    m = {"not_started": "released", "on_hold": "blocked"}
    tgt = m.get(payload.production_status, payload.production_status)
    if tgt not in {"draft", "released", "queued", "in_progress", "blocked", "ready", "completed", "cancelled"}:
        raise HTTPException(status_code=400, detail=f"Unknown status {payload.production_status}")
    try:
        return await transition(
            tenant_id=user["tenant_id"], work_order_id=wo_id, target=tgt, reason=None,
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except ValueError as ex:
        _raise(ex)


@router.post("/{wo_id}/assign")
async def assign_wo(wo_id: str, payload: AssignIn, user: dict = Depends(require_permission(Perm.WORK_ORDER_WRITE))) -> dict:
    try:
        return await assign(
            tenant_id=user["tenant_id"], work_order_id=wo_id, user_ids=payload.user_ids,
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except ValueError as ex:
        _raise(ex)


# ---- Summary ----


@router.get("/{wo_id}/summary")
async def get_summary(wo_id: str, user: dict = Depends(require_permission(Perm.WORK_ORDER_READ))) -> dict:
    wo = await db.work_orders.find_one({"id": wo_id, "tenant_id": user["tenant_id"]}, {"_id": 0})
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found")
    order = await db.orders.find_one({"id": wo["order_id"]}, {"_id": 0}) or {}
    customer = await db.customers.find_one({"id": wo["customer_id"]}, {"_id": 0}) or {}
    include_pricing = "invoice:read" in (user.get("permissions") or [])
    return build_summary(wo, order, customer, include_pricing=include_pricing)


# ---- Production Board ----


@prod_router.get("/board")
async def board(
    customer_id: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    assigned_user_id: Optional[str] = Query(None),
    user: dict = Depends(require_permission(Perm.WORK_ORDER_READ)),
) -> dict:
    q: dict = {"tenant_id": user["tenant_id"], "current_version": True}
    if customer_id:
        q["customer_id"] = customer_id
    if priority:
        q["priority"] = priority
    if assigned_user_id:
        q["assigned_user_ids"] = assigned_user_id
    cursor = db.work_orders.find(q, {"_id": 0}).sort([("priority", -1), ("due_date", 1)]).limit(500)
    columns: dict[str, list] = {s: [] for s in ["draft", "released", "queued", "in_progress", "blocked", "ready", "completed"]}
    async for wo in cursor:
        st = effective_status(wo.get("production_status"))
        wo["effective_status"] = st
        wo["overdue"] = bool(wo.get("due_date") and wo["due_date"] < utc_now().date().isoformat() and st not in {"completed", "cancelled"})
        columns.setdefault(st, []).append(serialize_doc(wo))
    return {"columns": columns, "counts": {k: len(v) for k, v in columns.items()}}
