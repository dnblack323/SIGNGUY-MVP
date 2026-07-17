"""EC11 Phase 11D - production board projection and safe bulk actions.

The board is a read model over Phase 11C workflow/stage instances. Mutations
delegate to `production_stage_service` so lifecycle, audit, timeline, and
notification behavior remains single-sourced.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import serialize_doc, utc_now
from ..models.work_order import effective_status
from . import production_stage_service as stage_service
from .production_stage_service import ProductionStageError

ACTIVE_STAGE_STATUSES = {"in_progress", "blocked", "waiting"}
TERMINAL_STAGE_STATUSES = {"completed", "skipped"}
PRIORITY_WEIGHT = {"rush": 0, "high": 1, "normal": 2, "low": 3}
RECENT_DAYS = 7


class ProductionBoardError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _is_manager(user: dict) -> bool:
    return user.get("role") in {"owner", "admin", "production_manager"}


def _has_write(user: dict) -> bool:
    return "work_order:write" in set(user.get("permissions") or [])


def _date_part(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return str(value)[:10]


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        raw = str(value)
        if len(raw) == 10:
            return datetime.fromisoformat(raw).replace(tzinfo=timezone.utc)
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _row_updated_at(*docs: dict) -> Optional[str]:
    values = [d.get("updated_at") or d.get("created_at") for d in docs if d]
    return max([str(v) for v in values if v], default=None)


def _current_stage(stages: list[dict]) -> tuple[Optional[dict], str]:
    if not stages:
        return None, "manual_no_workflow"
    ordered = sorted(stages, key=lambda s: int(s.get("sequence") or 0))
    active = [s for s in ordered if s.get("status") in ACTIVE_STAGE_STATUSES]
    if active:
        rank = {"in_progress": 0, "blocked": 1, "waiting": 2}
        active.sort(key=lambda s: (rank.get(s.get("status"), 9), int(s.get("sequence") or 0)))
        return active[0], "active"
    for stage in ordered:
        if (stage.get("status") or "not_started") == "not_started":
            return stage, "ready"
    return ordered[-1], "finished"


async def _proof_gate_state(stage: Optional[dict]) -> Optional[str]:
    if not stage or not stage.get("proof_gate_type") or stage.get("proof_gate_type") in {"none", "not_required"}:
        return None
    filters = [
        {"parent_type": "order_item", "parent_id": stage["order_item_id"]},
        {"parent_type": "work_order", "parent_id": stage["work_order_id"]},
        {"parent_type": "order", "parent_id": stage["order_id"]},
    ]
    proof = await db.proofs.find_one({"tenant_id": stage["tenant_id"], "$or": filters, "status": "approved"}, {"_id": 0, "id": 1})
    if proof:
        return "approved"
    proof_ids = [p["id"] async for p in db.proofs.find({"tenant_id": stage["tenant_id"], "$or": filters}, {"_id": 0, "id": 1})]
    versions = [v["id"] async for v in db.proof_versions.find({"tenant_id": stage["tenant_id"], "proof_id": {"$in": proof_ids}}, {"_id": 0, "id": 1})] if proof_ids else []
    approval = await db.approvals.find_one(
        {"tenant_id": stage["tenant_id"], "parent_type": "proof_version", "parent_id": {"$in": versions}, "action": "approve"},
        {"_id": 0, "id": 1},
    ) if versions else None
    return "approved" if approval else "approval_required"


def _eligibility_summary(stage: Optional[dict]) -> Optional[str]:
    if not stage:
        return None
    pieces = []
    if stage.get("assigned_role"):
        pieces.append(f"role: {stage['assigned_role']}")
    if stage.get("equipment_requirement_ids"):
        pieces.append(f"{len(stage['equipment_requirement_ids'])} equipment requirement(s)")
    if stage.get("certification_requirement_ids"):
        pieces.append(f"{len(stage['certification_requirement_ids'])} certification requirement(s)")
    if not pieces:
        return None
    return "Eligibility check required: " + ", ".join(pieces)


def _allowed_actions(row: dict, user: dict) -> list[str]:
    actions = ["open_work_order", "open_order"]
    if row.get("customer_id"):
        actions.append("open_customer")
    if not _has_write(user) or not row.get("current_stage_id"):
        return actions
    status = row.get("current_stage_status") or "not_started"
    if status == "not_started":
        actions.append("start")
    elif status == "in_progress":
        actions.extend(["wait", "block", "complete"])
    elif status == "waiting":
        actions.extend(["resume", "block"])
    elif status == "blocked":
        actions.extend(["resume", "wait"])
    actions.append("add_note")
    if _is_manager(user):
        actions.extend(["assign", "update_due_date"])
        if row.get("assigned_employee_id"):
            actions.append("unassign")
        if status == "not_started" and row.get("may_skip", True):
            actions.append("skip")
        if status in TERMINAL_STAGE_STATUSES:
            actions.append("reopen")
    return actions


def _column_key(row: dict, group_by: str) -> str:
    status = row.get("current_stage_status") or "manual_no_workflow"
    if row.get("legacy_work_order_queue") and group_by == "status":
        return row.get("work_order_status") or "released"
    if group_by == "stage":
        return row.get("current_stage_key") or "manual_no_workflow"
    if group_by == "assignee":
        return row.get("assigned_employee_name") or "Unassigned"
    if group_by == "due_date":
        if row.get("workflow_complete"):
            return "completed"
        if row.get("overdue"):
            return "overdue"
        due = _date_part(row.get("due_at"))
        today = utc_now().date().isoformat()
        tomorrow = (utc_now().date() + timedelta(days=1)).isoformat()
        if not due:
            return "no_due"
        if due <= today:
            return "today"
        if due == tomorrow:
            return "tomorrow"
        return "upcoming"
    if status == "manual_no_workflow":
        return "manual_no_workflow"
    if row.get("workflow_complete"):
        return "completed"
    if status in {"blocked", "waiting", "in_progress"}:
        return status
    if row.get("overdue"):
        return "overdue"
    if not row.get("assigned_employee_id"):
        return "unassigned"
    return "ready_to_start"


def _filter_match(row: dict, filters: dict[str, Any]) -> bool:
    def _bool_filter(name: str, predicate: bool) -> bool:
        value = filters.get(name)
        return True if value is None else bool(value) == predicate

    if filters.get("stage") and row.get("current_stage_key") != filters["stage"]:
        return False
    if filters.get("stage_status") and row.get("current_stage_status") != filters["stage_status"]:
        return False
    if filters.get("employee") and row.get("assigned_employee_id") != filters["employee"]:
        return False
    if filters.get("workflow") and row.get("workflow_instance_id") != filters["workflow"] and row.get("workflow_name") != filters["workflow"]:
        return False
    if filters.get("priority") and row.get("priority") != filters["priority"]:
        return False
    if filters.get("customer") and row.get("customer_id") != filters["customer"]:
        return False
    if filters.get("work_order_status") and row.get("work_order_status") != filters["work_order_status"]:
        return False
    if filters.get("order_status") and row.get("order_status") != filters["order_status"]:
        return False
    if filters.get("production_category") and row.get("production_category") != filters["production_category"]:
        return False
    if not _bool_filter("overdue", bool(row.get("overdue"))):
        return False
    if not _bool_filter("blocked", row.get("current_stage_status") == "blocked"):
        return False
    if not _bool_filter("waiting", row.get("current_stage_status") == "waiting"):
        return False
    if not _bool_filter("unassigned", not row.get("assigned_employee_id") and bool(row.get("current_stage_id"))):
        return False
    due = _date_part(row.get("due_at"))
    if filters.get("due_from") and (not due or due < filters["due_from"]):
        return False
    if filters.get("due_to") and (not due or due > filters["due_to"]):
        return False
    search = (filters.get("search") or "").strip().lower()
    if search:
        haystack = " ".join(str(row.get(k) or "") for k in [
            "work_order_number", "order_number", "customer_name", "order_item_name", "assigned_employee_name",
        ]).lower()
        if search not in haystack:
            return False
    view = filters.get("view")
    if view == "blocked_waiting" and row.get("current_stage_status") not in {"blocked", "waiting"}:
        return False
    if view == "unassigned" and row.get("assigned_employee_id"):
        return False
    if view == "ready" and (row.get("current_stage_status") != "not_started" or row.get("workflow_complete")):
        return False
    if view == "overdue" and not row.get("overdue"):
        return False
    if view == "completed_recently" and not row.get("completed_recently"):
        return False
    return True


def _sort_rows(rows: list[dict], sort: str) -> list[dict]:
    if sort == "priority":
        return sorted(rows, key=lambda r: (PRIORITY_WEIGHT.get(r.get("priority") or "normal", 2), r.get("due_at") or "9999-99-99"))
    if sort == "oldest_waiting":
        return sorted(rows, key=lambda r: (r.get("waiting_since") or "9999-99-99", r.get("work_order_number") or ""))
    if sort == "oldest_started":
        return sorted(rows, key=lambda r: (r.get("started_at") or "9999-99-99", r.get("work_order_number") or ""))
    if sort == "customer":
        return sorted(rows, key=lambda r: ((r.get("customer_name") or "").lower(), r.get("work_order_number") or ""))
    if sort == "work_order_number":
        return sorted(rows, key=lambda r: str(r.get("work_order_number") or ""))
    if sort == "last_updated":
        return sorted(rows, key=lambda r: r.get("updated_at") or "", reverse=True)
    return sorted(rows, key=lambda r: (r.get("due_at") or "9999-99-99", PRIORITY_WEIGHT.get(r.get("priority") or "normal", 2), r.get("work_order_number") or ""))


def _summary_counts(rows: list[dict]) -> dict[str, int]:
    return {
        "active_production": sum(1 for r in rows if not r.get("workflow_complete") and r.get("current_stage_status") != "manual_no_workflow"),
        "ready_to_start": sum(1 for r in rows if r.get("current_stage_status") == "not_started" and not r.get("workflow_complete")),
        "in_progress": sum(1 for r in rows if r.get("current_stage_status") == "in_progress"),
        "blocked": sum(1 for r in rows if r.get("current_stage_status") == "blocked"),
        "waiting": sum(1 for r in rows if r.get("current_stage_status") == "waiting"),
        "overdue": sum(1 for r in rows if r.get("overdue")),
        "unassigned": sum(1 for r in rows if not r.get("assigned_employee_id") and r.get("current_stage_id")),
        "completed_recently": sum(1 for r in rows if r.get("completed_recently")),
        "manual_no_workflow": sum(1 for r in rows if r.get("current_stage_status") == "manual_no_workflow"),
    }


async def _build_rows(tenant_id: str, work_orders: list[dict], user: dict) -> list[dict]:
    order_ids = list({w.get("order_id") for w in work_orders if w.get("order_id")})
    customer_ids = list({w.get("customer_id") for w in work_orders if w.get("customer_id")})
    work_order_ids = [w["id"] for w in work_orders]
    orders = {
        o["id"]: serialize_doc(o) async for o in db.orders.find({"tenant_id": tenant_id, "id": {"$in": order_ids}}, {"_id": 0})
    } if order_ids else {}
    customers = {
        c["id"]: serialize_doc(c) async for c in db.customers.find({"tenant_id": tenant_id, "id": {"$in": customer_ids}}, {"_id": 0})
    } if customer_ids else {}
    instances = [
        serialize_doc(i) async for i in db.production_workflow_instances.find({"tenant_id": tenant_id, "work_order_id": {"$in": work_order_ids}}, {"_id": 0})
    ] if work_order_ids else []
    stages = [
        serialize_doc(s) async for s in db.production_stage_instances.find({"tenant_id": tenant_id, "work_order_id": {"$in": work_order_ids}}, {"_id": 0})
    ] if work_order_ids else []
    item_ids = list({i.get("order_item_id") for i in instances if i.get("order_item_id")})
    items = {
        item["id"]: serialize_doc(item) async for item in db.order_items.find({"tenant_id": tenant_id, "id": {"$in": item_ids}}, {"_id": 0})
    } if item_ids else {}
    employee_ids = list({s.get("assigned_employee_id") for s in stages if s.get("assigned_employee_id")})
    employees = {
        e["id"]: serialize_doc(e) async for e in db.employees.find({"tenant_id": tenant_id, "id": {"$in": employee_ids}}, {"_id": 0, "id": 1, "name": 1, "role_label": 1})
    } if employee_ids else {}

    stages_by_instance: dict[str, list[dict]] = {}
    for stage in stages:
        stages_by_instance.setdefault(stage["workflow_instance_id"], []).append(stage)
    instances_by_wo: dict[str, list[dict]] = {}
    for instance in instances:
        instances_by_wo.setdefault(instance["work_order_id"], []).append(instance)

    rows: list[dict] = []
    today = utc_now().date().isoformat()
    recent_cutoff = (utc_now().date() - timedelta(days=RECENT_DAYS)).isoformat()
    for wo in work_orders:
        wo_instances = sorted(instances_by_wo.get(wo["id"], []), key=lambda i: (i.get("created_at") or "", i.get("order_item_id") or ""))
        if not wo_instances:
            rows.append(_safe_row(
                work_order=wo, order=orders.get(wo.get("order_id"), {}), customer=customers.get(wo.get("customer_id"), {}),
                item={}, instance={}, stage=None, all_stages=[], employee={}, user=user,
                resolution_state="manual_no_workflow", proof_gate_state=None,
            ))
            continue
        for instance in wo_instances:
            instance_stages = sorted(stages_by_instance.get(instance["id"], []), key=lambda s: int(s.get("sequence") or 0))
            stage, state = _current_stage(instance_stages)
            employee = employees.get((stage or {}).get("assigned_employee_id"), {})
            proof_state = await _proof_gate_state(stage)
            row = _safe_row(
                work_order=wo, order=orders.get(wo.get("order_id"), {}), customer=customers.get(wo.get("customer_id"), {}),
                item=items.get(instance.get("order_item_id"), {}), instance=instance, stage=stage, all_stages=instance_stages,
                employee=employee, user=user, resolution_state=state, proof_gate_state=proof_state,
            )
            due = _date_part(row.get("due_at"))
            row["overdue"] = bool(due and due < today and not row.get("workflow_complete"))
            row["completed_recently"] = bool(row.get("workflow_complete") and _date_part((stage or {}).get("completed_at") or (stage or {}).get("skipped_at")) >= recent_cutoff)
            rows.append(row)
    return rows


def _safe_row(
    *,
    work_order: dict,
    order: dict,
    customer: dict,
    item: dict,
    instance: dict,
    stage: Optional[dict],
    all_stages: list[dict],
    employee: dict,
    user: dict,
    resolution_state: str,
    proof_gate_state: Optional[str],
) -> dict:
    completed_count = sum(1 for s in all_stages if s.get("status") in TERMINAL_STAGE_STATUSES)
    total_count = len(all_stages)
    progress = round((completed_count / total_count) * 100) if total_count else 0
    status = (stage or {}).get("status") or ("manual_no_workflow" if not stage else "not_started")
    workflow_complete = bool(total_count and completed_count == total_count)
    row = {
        "id": f"{work_order['id']}:{instance.get('id')}" if instance.get("id") else work_order["id"],
        "work_order_id": work_order["id"],
        "work_order_number": work_order.get("number"),
        "order_id": work_order.get("order_id"),
        "order_number": order.get("number"),
        "order_item_id": item.get("id") or instance.get("order_item_id"),
        "order_item_name": item.get("description") or item.get("name") or "Manual production",
        "production_category": item.get("category") or item.get("product_type"),
        "customer_id": work_order.get("customer_id") or order.get("customer_id"),
        "customer_name": customer.get("name"),
        "workflow_instance_id": instance.get("id"),
        "workflow_name": instance.get("source_name"),
        "workflow_resolution_source": instance.get("resolution_source"),
        "current_stage_id": (stage or {}).get("id"),
        "current_stage_key": (stage or {}).get("stage_key"),
        "current_stage_name": (stage or {}).get("stage_name") or ("Manual / no workflow" if not stage else None),
        "current_stage_sequence": (stage or {}).get("sequence"),
        "current_stage_status": status,
        "assigned_employee_id": (stage or {}).get("assigned_employee_id"),
        "assigned_employee_name": employee.get("name"),
        "assigned_role": (stage or {}).get("assigned_role"),
        "due_at": (stage or {}).get("due_at") or work_order.get("due_date"),
        "overdue": False,
        "blocker_reason": (stage or {}).get("blocker_reason"),
        "waiting_since": (stage or {}).get("waiting_since"),
        "started_at": (stage or {}).get("started_at"),
        "completed_stage_count": completed_count,
        "total_stage_count": total_count,
        "progress_percent": progress,
        "priority": work_order.get("priority") or "normal",
        "work_order_status": effective_status(work_order.get("production_status")),
        "order_status": order.get("status"),
        "proof_or_approval_gate_state": proof_gate_state,
        "eligibility_warning": _eligibility_summary(stage),
        "updated_at": _row_updated_at(stage or {}, instance, work_order, order),
        "workflow_complete": workflow_complete,
        "resolution_state": resolution_state,
        "legacy_work_order_queue": not bool(instance.get("id")),
        "may_skip": (stage or {}).get("may_skip", True),
        "requires_reason_to_skip": (stage or {}).get("requires_reason_to_skip", False),
        "employee_visible": bool((stage or {}).get("employee_visible", True)),
    }
    row["allowed_actions"] = _allowed_actions(row, user)
    return row


async def get_board(
    *,
    tenant_id: str,
    user: dict,
    filters: dict[str, Any],
    group_by: str = "status",
    sort: str = "due_date",
    limit: int = 100,
    skip: int = 0,
) -> dict:
    wo_query: dict[str, Any] = {"tenant_id": tenant_id, "current_version": {"$ne": False}}
    if filters.get("customer"):
        wo_query["customer_id"] = filters["customer"]
    if filters.get("priority"):
        wo_query["priority"] = filters["priority"]
    if filters.get("work_order_status"):
        wo_query["production_status"] = filters["work_order_status"]
    if filters.get("order_status"):
        matching_orders = [o["id"] async for o in db.orders.find({"tenant_id": tenant_id, "status": filters["order_status"]}, {"_id": 0, "id": 1})]
        wo_query["order_id"] = {"$in": matching_orders}
    work_orders = [serialize_doc(w) async for w in db.work_orders.find(wo_query, {"_id": 0}).limit(1000)]
    rows = await _build_rows(tenant_id, work_orders, user)
    filtered = [r for r in rows if _filter_match(r, filters)]
    sorted_rows = _sort_rows(filtered, sort)
    total = len(sorted_rows)
    paged = sorted_rows[skip: skip + limit]
    columns: dict[str, list[dict]] = {}
    for row in paged:
        columns.setdefault(_column_key(row, group_by), []).append(row)
    return {
        "items": paged,
        "columns": columns,
        "counts": {k: len(v) for k, v in columns.items()},
        "summary_counts": _summary_counts(filtered),
        "total": total,
        "limit": limit,
        "skip": skip,
        "group_by": group_by,
        "sort": sort,
        "views": ["active", "blocked_waiting", "unassigned", "ready", "overdue", "completed_recently"],
    }


def _portal_stage_actions(row: dict, *, assigned_to_self: bool) -> list[str]:
    if not assigned_to_self or not row.get("current_stage_id"):
        return []
    status = row.get("current_stage_status") or "not_started"
    if status == "not_started":
        return ["start", "add_note"]
    if status == "in_progress":
        return ["wait", "block", "complete", "add_note"]
    if status == "waiting":
        return ["resume", "block", "add_note"]
    if status == "blocked":
        return ["resume", "wait", "add_note"]
    return ["add_note"]


def _portal_row(row: dict, *, employee_id: str) -> dict:
    assigned_to_self = row.get("assigned_employee_id") == employee_id
    return {
        "id": row.get("id"),
        "stage_id": row.get("current_stage_id"),
        "work_order_id": row.get("work_order_id"),
        "work_order_number": row.get("work_order_number"),
        "order_id": row.get("order_id"),
        "order_number": row.get("order_number"),
        "order_item_id": row.get("order_item_id"),
        "order_item_name": row.get("order_item_name"),
        "customer_name": row.get("customer_name"),
        "workflow_name": row.get("workflow_name"),
        "stage_key": row.get("current_stage_key"),
        "stage_name": row.get("current_stage_name"),
        "stage_sequence": row.get("current_stage_sequence"),
        "stage_status": row.get("current_stage_status"),
        "assigned_employee_id": row.get("assigned_employee_id"),
        "assigned_employee_name": row.get("assigned_employee_name"),
        "assigned_to_self": assigned_to_self,
        "due_at": row.get("due_at"),
        "overdue": row.get("overdue"),
        "priority": row.get("priority"),
        "blocker_reason": row.get("blocker_reason"),
        "waiting_since": row.get("waiting_since"),
        "started_at": row.get("started_at"),
        "completed_stage_count": row.get("completed_stage_count"),
        "total_stage_count": row.get("total_stage_count"),
        "progress_percent": row.get("progress_percent"),
        "proof_or_approval_gate_state": row.get("proof_or_approval_gate_state"),
        "eligibility_warning": row.get("eligibility_warning"),
        "allowed_actions": _portal_stage_actions(row, assigned_to_self=assigned_to_self),
    }


def _active_portal_row(row: dict) -> bool:
    return bool(row.get("current_stage_id")) and bool(row.get("employee_visible", True)) and row.get("current_stage_status") not in TERMINAL_STAGE_STATUSES


async def get_employee_production_view(
    *,
    tenant_id: str,
    employee_id: str,
    search: Optional[str] = None,
    limit: int = 80,
) -> dict:
    work_orders = [serialize_doc(w) async for w in db.work_orders.find(
        {"tenant_id": tenant_id, "current_version": {"$ne": False}}, {"_id": 0},
    ).limit(1000)]
    synthetic_user = {"id": f"employee:{employee_id}", "tenant_id": tenant_id, "email": "", "role": "employee_portal", "permissions": []}
    rows = await _build_rows(tenant_id, work_orders, synthetic_user)
    q = (search or "").strip().lower()

    portal_rows: list[dict] = []
    for row in rows:
        if not _active_portal_row(row):
            continue
        if q:
            haystack = " ".join(str(row.get(k) or "") for k in [
                "work_order_number", "order_number", "customer_name", "order_item_name",
                "current_stage_name", "assigned_employee_name",
            ]).lower()
            if q not in haystack:
                continue
        portal_rows.append(_portal_row(row, employee_id=employee_id))

    assigned = [r for r in portal_rows if r["assigned_to_self"]]
    assigned = _sort_portal_rows(assigned)
    current = [r for r in assigned if r["stage_status"] in ACTIVE_STAGE_STATUSES]
    queue = _sort_portal_rows([r for r in portal_rows if not r["assigned_to_self"]])
    return {
        "current_task": current[0] if current else None,
        "assigned_tasks": assigned[:limit],
        "shop_queue": queue[:limit],
        "counts": {
            "current": len(current),
            "assigned": len(assigned),
            "shop_queue": len(queue),
            "blocked": sum(1 for r in assigned if r["stage_status"] == "blocked"),
            "waiting": sum(1 for r in assigned if r["stage_status"] == "waiting"),
            "overdue": sum(1 for r in assigned if r["overdue"]),
        },
        "search": search or None,
        "limit": limit,
    }


def _sort_portal_rows(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda r: (
        0 if r.get("stage_status") == "in_progress" else 1,
        PRIORITY_WEIGHT.get(r.get("priority") or "normal", 2),
        r.get("due_at") or "9999-99-99",
        str(r.get("work_order_number") or ""),
    ))


async def bulk_assign(*, tenant_id: str, stage_ids: list[str], employee_id: str, override_reason: Optional[str], user: dict) -> dict:
    return await _bulk_stage_action(
        tenant_id=tenant_id, stage_ids=stage_ids, user=user,
        call=lambda stage_id: stage_service.assign_stage(
            tenant_id=tenant_id, stage_id=stage_id, employee_id=employee_id, override_reason=override_reason, user=user,
        ),
    )


async def bulk_due_date(*, tenant_id: str, stage_ids: list[str], due_at: Optional[str], user: dict) -> dict:
    return await _bulk_stage_action(
        tenant_id=tenant_id, stage_ids=stage_ids, user=user,
        call=lambda stage_id: stage_service.update_stage_due_date(tenant_id=tenant_id, stage_id=stage_id, due_at=due_at, user=user),
    )


async def bulk_wait(*, tenant_id: str, stage_ids: list[str], reason: Optional[str], user: dict) -> dict:
    return await _bulk_stage_action(
        tenant_id=tenant_id, stage_ids=stage_ids, user=user,
        call=lambda stage_id: stage_service.transition_stage(tenant_id=tenant_id, stage_id=stage_id, target="waiting", user=user, reason=reason),
    )


async def bulk_note(*, tenant_id: str, stage_ids: list[str], note: str, user: dict) -> dict:
    return await _bulk_stage_action(
        tenant_id=tenant_id, stage_ids=stage_ids, user=user,
        call=lambda stage_id: stage_service.add_stage_note(tenant_id=tenant_id, stage_id=stage_id, note=note, user=user),
    )


async def reject_unsupported_bulk(action: str) -> None:
    raise ProductionBoardError("bulk_action_not_allowed", f"Bulk {action} is not allowed from the production board")


async def _bulk_stage_action(*, tenant_id: str, stage_ids: list[str], user: dict, call) -> dict:
    if not _is_manager(user):
        raise ProductionBoardError("manager_required", "Only owner/admin/production manager may perform bulk board actions")
    results = []
    for stage_id in list(dict.fromkeys(stage_ids)):
        try:
            updated = await call(stage_id)
            results.append({"stage_id": stage_id, "ok": True, "stage": updated})
        except ProductionStageError as ex:
            results.append({"stage_id": stage_id, "ok": False, "code": ex.code, "error": str(ex)})
    return {
        "results": results,
        "success_count": sum(1 for r in results if r["ok"]),
        "failure_count": sum(1 for r in results if not r["ok"]),
    }
