"""Workspace Dock state service.

The dock stores only navigation/view metadata. It never mutates the underlying
business record represented by a workspace.
"""
from __future__ import annotations

import asyncio
import uuid
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from ..core.db import db
from ..core.permissions import Perm, permissions_for_role
from ..core.time_utils import prepare_for_mongo, serialize_doc
from ..models.workspace_dock import WorkspaceDockState

MAX_OPEN_WORKSPACES = 8
MAX_RECENT_WORKSPACES = 20
_STATE_LOCKS: defaultdict[tuple[str, str], asyncio.Lock] = defaultdict(asyncio.Lock)


class WorkspaceDockError(Exception):
    def __init__(self, message: str, *, status_code: int = 400, extra: dict[str, Any] | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.extra = extra or {}


class WorkspaceDockConflict(WorkspaceDockError):
    """Raised internally when the stored dock revision changed during a write."""


@dataclass(frozen=True)
class WorkspaceTarget:
    collection: Optional[str]
    permission: Perm
    default_path: str
    number_fields: tuple[str, ...] = ("number",)
    label_fields: tuple[str, ...] = ("job_name", "name", "title", "company_name", "customer_name", "description")
    prefix: str = ""
    allow_archived: bool = False
    record_required: bool = True


WORKSPACE_TARGETS: dict[str, WorkspaceTarget] = {
    "order": WorkspaceTarget("orders", Perm.ORDER_READ, "/orders", prefix="O"),
    "quote": WorkspaceTarget("quotes", Perm.QUOTE_READ, "/quotes", prefix="Q"),
    "customer": WorkspaceTarget("customers", Perm.CUSTOMER_READ, "/customers", prefix="Customer", number_fields=()),
    "work_order": WorkspaceTarget("work_orders", Perm.WORK_ORDER_READ, "/work-orders", prefix="WO"),
    "invoice": WorkspaceTarget("invoices", Perm.INVOICE_READ, "/invoices", prefix="INV"),
    "pricing_calculator": WorkspaceTarget(None, Perm.PRICING_READ, "/pricing-calculator", prefix="Pricing Calculator", record_required=False),
    "saved_calculation": WorkspaceTarget("pricing_saved_calculations", Perm.PRICING_READ, "/pricing-calculator", prefix="Saved Calc", label_fields=("name", "category")),
    "decision_room": WorkspaceTarget("decision_rooms", Perm.DECISION_ROOM_READ, "/decision-rooms", prefix="Decision Room", label_fields=("title", "name")),
    "proof": WorkspaceTarget("proofs", Perm.DOCUMENT_READ, "/documents", prefix="Proof"),
    "visual_markup": WorkspaceTarget("markups", Perm.MARKUP_READ, "/markup", prefix="Markup"),
    "webstore": WorkspaceTarget("webstores", Perm.WEBSTORE_READ, "/webstores", prefix="Webstore", label_fields=("name", "title")),
    "wrap_lab": WorkspaceTarget("wrap_projects", Perm.WRAP_LAB_READ, "/wrap-lab", prefix="Wrap Lab", label_fields=("project_name", "name", "customer_name")),
    "material": WorkspaceTarget("materials", Perm.INVENTORY_READ, "/materials", prefix="Material", label_fields=("name", "sku")),
    "purchase_order": WorkspaceTarget("purchase_orders", Perm.PURCHASING_READ, "/purchase-orders", prefix="PO"),
    "vendor": WorkspaceTarget("vendors", Perm.VENDOR_READ, "/vendors", prefix="Vendor", label_fields=("name",)),
    "employee": WorkspaceTarget("employees", Perm.EMPLOYEE_READ, "/team/employees", prefix="Employee", label_fields=("full_name", "name", "email")),
    "equipment": WorkspaceTarget("equipment", Perm.EQUIPMENT_READ, "/team/equipment", prefix="Equipment", label_fields=("name", "asset_tag")),
}

ALLOWED_VIEW_STATE_KEYS = {
    "selected_tab",
    "active_tab",
    "filter",
    "filters",
    "sort",
    "scroll_y",
    "view",
    "category",
    "mode",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _permissions(user: dict[str, Any]) -> set[str]:
    role = user.get("role", "staff")
    return set(permissions_for_role(role))


def _require_permission(user: dict[str, Any], permission: Perm) -> None:
    if permission.value not in _permissions(user):
        raise WorkspaceDockError("Workspace target not found or not accessible", status_code=404)


def _workspace_id() -> str:
    return str(uuid.uuid4())


def _sanitize_query_params(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    cleaned: dict[str, str] = {}
    for key, raw in value.items():
        if len(cleaned) >= 20:
            break
        key_text = str(key)[:80]
        if not key_text:
            continue
        if isinstance(raw, (str, int, float, bool)):
            cleaned[key_text] = str(raw)[:300]
    return cleaned


def _sanitize_view_state(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    cleaned: dict[str, Any] = {}
    for key, raw in value.items():
        if key not in ALLOWED_VIEW_STATE_KEYS:
            continue
        if isinstance(raw, (str, int, float, bool)) or raw is None:
            cleaned[key] = raw
        elif isinstance(raw, list):
            cleaned[key] = [item for item in raw[:20] if isinstance(item, (str, int, float, bool)) or item is None]
        elif isinstance(raw, dict):
            cleaned[key] = {
                str(sub_key)[:80]: sub_value
                for sub_key, sub_value in list(raw.items())[:20]
                if isinstance(sub_value, (str, int, float, bool)) or sub_value is None
            }
    return cleaned


def _status_filter_for_record(target: WorkspaceTarget) -> dict[str, Any]:
    if target.allow_archived:
        return {}
    return {
        "$and": [
            {"archived": {"$ne": True}},
            {"deleted": {"$ne": True}},
            {"is_deleted": {"$ne": True}},
        ]
    }


async def _load_record(tenant_id: str, target: WorkspaceTarget, record_id: Optional[str]) -> dict[str, Any] | None:
    if not target.collection:
        return None
    if not record_id:
        raise WorkspaceDockError("Workspace record ID is required", status_code=400)
    query: dict[str, Any] = {"tenant_id": tenant_id, "id": record_id}
    query.update(_status_filter_for_record(target))
    return await db[target.collection].find_one(query, {"_id": 0})


def _record_number(record: dict[str, Any] | None, target: WorkspaceTarget) -> Optional[str]:
    if not record:
        return None
    for field in target.number_fields:
        value = record.get(field)
        if value:
            return str(value)
    return None


def _recognizable_label(record: dict[str, Any] | None, target: WorkspaceTarget) -> str:
    if not record:
        return target.prefix
    for field in target.label_fields:
        value = record.get(field)
        if value:
            return str(value)
    customer = record.get("customer")
    if isinstance(customer, dict):
        for field in ("name", "company_name", "full_name"):
            if customer.get(field):
                return str(customer[field])
    return record.get("id", target.prefix)


def _build_label(target: WorkspaceTarget, record: dict[str, Any] | None, payload_label: Optional[str] = None) -> str:
    number = _record_number(record, target)
    name = _recognizable_label(record, target)
    if target.collection is None and payload_label:
        return str(payload_label)[:120]
    if target.prefix in {"Customer", "Webstore", "Wrap Lab", "Saved Calc", "Decision Room", "Material", "Vendor", "Employee", "Equipment", "Pricing Calculator"}:
        suffix = payload_label or name
        return f"{target.prefix} - {suffix}"[:120] if suffix and suffix != target.prefix else target.prefix
    if number and name:
        return f"{target.prefix}-{number} - {name}"[:120]
    if number:
        return f"{target.prefix}-{number}"[:120]
    return (payload_label or name or target.prefix)[:120]


def _workspace_key(workspace_type: str, record_id: Optional[str], pathname: str, query_params: dict[str, str]) -> str:
    if record_id:
        return f"{workspace_type}:{record_id}"
    if workspace_type == "pricing_calculator":
        return "pricing_calculator:default"
    return f"{workspace_type}:{pathname}:{query_params.get('id', '')}"


async def _validate_target(tenant_id: str, user: dict[str, Any], payload: dict[str, Any]) -> tuple[WorkspaceTarget, dict[str, Any] | None]:
    workspace_type = str(payload.get("workspace_type") or "")
    target = WORKSPACE_TARGETS.get(workspace_type)
    if not target:
        raise WorkspaceDockError("Workspace target not supported", status_code=400)
    _require_permission(user, target.permission)
    record_id = payload.get("record_id")
    if target.record_required and not record_id:
        raise WorkspaceDockError("Workspace record ID is required", status_code=400)
    record = await _load_record(tenant_id, target, record_id)
    if target.record_required and not record:
        raise WorkspaceDockError("Workspace target not found or not accessible", status_code=404)
    return target, record


async def _get_or_create_state(tenant_id: str, user_id: str) -> dict[str, Any]:
    existing = await db.workspace_docks.find_one({"tenant_id": tenant_id, "user_id": user_id}, {"_id": 0})
    if existing:
        doc = serialize_doc(existing) or existing
        doc.setdefault("revision", 0)
        return doc
    state = WorkspaceDockState(tenant_id=tenant_id, user_id=user_id)
    doc = prepare_for_mongo(state.model_dump())
    await db.workspace_docks.update_one(
        {"tenant_id": tenant_id, "user_id": user_id},
        {"$setOnInsert": doc},
        upsert=True,
    )
    return serialize_doc(await db.workspace_docks.find_one({"tenant_id": tenant_id, "user_id": user_id}, {"_id": 0})) or doc


def _normalize_positions(open_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(open_items, key=lambda item: item.get("position") if item.get("position") is not None else 9999)
    for index, item in enumerate(ordered):
        item["position"] = index
        item["status"] = "open"
    return ordered


def _trim_recent(recent_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    for item in recent_items:
        key = item.get("workspace_key") or item.get("id")
        if key and key not in unique:
            unique[key] = item
    ordered = sorted(unique.values(), key=lambda item: str(item.get("last_opened_at") or ""), reverse=True)
    for item in ordered[:MAX_RECENT_WORKSPACES]:
        item["status"] = "recent"
        item["active"] = False
        item["position"] = None
        item["dirty"] = False
    return ordered[:MAX_RECENT_WORKSPACES]


async def _save_state(state: dict[str, Any]) -> dict[str, Any]:
    tenant_id = state["tenant_id"]
    user_id = state["user_id"]
    expected_revision = int(state.get("revision") or 0)
    state["updated_at"] = _now()
    state["open_workspaces"] = _normalize_positions(state.get("open_workspaces", []))
    state["recent_workspaces"] = _trim_recent(state.get("recent_workspaces", []))
    state["revision"] = expected_revision + 1
    revision_filter: dict[str, Any] = {"revision": expected_revision}
    if expected_revision == 0:
        revision_filter = {"$or": [{"revision": 0}, {"revision": {"$exists": False}}]}
    result = await db.workspace_docks.update_one(
        {"tenant_id": tenant_id, "user_id": user_id, **revision_filter},
        {"$set": prepare_for_mongo(state)},
    )
    if result.matched_count == 0:
        raise WorkspaceDockConflict("Workspace state changed; retry the operation", status_code=409)
    return await list_workspace_state(tenant_id, user_id)


def _state_lock(tenant_id: str, user_id: str) -> asyncio.Lock:
    return _STATE_LOCKS[(tenant_id, user_id)]


async def _retry_state_conflicts(operation):
    for _ in range(20):
        try:
            return await operation()
        except WorkspaceDockConflict:
            continue
    raise WorkspaceDockError("Workspace state changed; try again", status_code=409)


async def list_workspace_state(tenant_id: str, user_id: str) -> dict[str, Any]:
    state = await _get_or_create_state(tenant_id, user_id)
    open_items = _normalize_positions(deepcopy(state.get("open_workspaces", [])))
    recent_items = _trim_recent(deepcopy(state.get("recent_workspaces", [])))
    return {
        "open_workspaces": open_items,
        "recent_workspaces": recent_items,
        "limits": {"max_open": MAX_OPEN_WORKSPACES, "max_recent": MAX_RECENT_WORKSPACES},
    }


async def open_workspace(tenant_id: str, user: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    target, record = await _validate_target(tenant_id, user, payload)
    async with _state_lock(tenant_id, user["id"]):
        return await _retry_state_conflicts(lambda: _open_workspace_after_validation(tenant_id, user, payload, target, record))


async def _open_workspace_after_validation(
    tenant_id: str,
    user: dict[str, Any],
    payload: dict[str, Any],
    target: WorkspaceTarget,
    record: dict[str, Any] | None,
) -> dict[str, Any]:
    now = _now()
    record_id = payload.get("record_id")
    pathname = str(payload.get("pathname") or target.default_path)
    query_params = _sanitize_query_params(payload.get("query_params"))
    workspace_key = _workspace_key(str(payload["workspace_type"]), record_id, pathname, query_params)
    label = _build_label(target, record, payload.get("label"))
    record_number = _record_number(record, target)
    state = await _get_or_create_state(tenant_id, user["id"])
    open_items = deepcopy(state.get("open_workspaces", []))
    recent_items = deepcopy(state.get("recent_workspaces", []))

    existing = next((item for item in open_items if item.get("workspace_key") == workspace_key), None)
    if existing:
        for item in open_items:
            item["active"] = item.get("workspace_key") == workspace_key
        existing.update(
            {
                "label": label,
                "record_number": record_number,
                "pathname": pathname,
                "query_params": query_params,
                "view_state": _sanitize_view_state(payload.get("view_state")),
                "scroll_position": int(payload.get("scroll_position") or existing.get("scroll_position") or 0),
                "last_opened_at": now,
                "updated_at": now,
            }
        )
        state["open_workspaces"] = open_items
        state["recent_workspaces"] = recent_items
        return await _save_state(state)

    if len(open_items) >= MAX_OPEN_WORKSPACES:
        raise WorkspaceDockError(
            "Workspace limit reached",
            status_code=409,
            extra={"limit": MAX_OPEN_WORKSPACES, "open_workspaces": open_items},
        )

    recent_existing = next((item for item in recent_items if item.get("workspace_key") == workspace_key), None)
    if recent_existing:
        item = recent_existing
        recent_items = [recent for recent in recent_items if recent.get("workspace_key") != workspace_key]
        item.update(
            {
                "status": "open",
                "active": True,
                "position": len(open_items),
                "label": label,
                "record_number": record_number,
                "pathname": pathname,
                "query_params": query_params,
                "view_state": _sanitize_view_state(payload.get("view_state")),
                "last_opened_at": now,
                "updated_at": now,
                "closed_at": None,
            }
        )
    else:
        item = {
            "id": _workspace_id(),
            "workspace_type": payload["workspace_type"],
            "workspace_key": workspace_key,
            "record_id": record_id,
            "record_number": record_number,
            "label": label,
            "pathname": pathname,
            "query_params": query_params,
            "view_state": _sanitize_view_state(payload.get("view_state")),
            "active": True,
            "pinned": bool(payload.get("pinned") or False),
            "position": len(open_items),
            "scroll_position": int(payload.get("scroll_position") or 0),
            "dirty": False,
            "status": "open",
            "last_opened_at": now,
            "closed_at": None,
            "created_at": now,
            "updated_at": now,
        }
    for existing_item in open_items:
        existing_item["active"] = False
    open_items.append(item)
    state["open_workspaces"] = open_items
    state["recent_workspaces"] = recent_items
    return await _save_state(state)


async def activate_workspace(tenant_id: str, user: dict[str, Any], workspace_id: str) -> dict[str, Any]:
    async with _state_lock(tenant_id, user["id"]):
        return await _retry_state_conflicts(lambda: _activate_workspace_locked(tenant_id, user, workspace_id))


async def _activate_workspace_locked(tenant_id: str, user: dict[str, Any], workspace_id: str) -> dict[str, Any]:
    state = await _get_or_create_state(tenant_id, user["id"])
    open_items = deepcopy(state.get("open_workspaces", []))
    item = next((workspace for workspace in open_items if workspace.get("id") == workspace_id), None)
    if not item:
        raise WorkspaceDockError("Workspace not found", status_code=404)
    await _validate_target(tenant_id, user, item)
    now = _now()
    for workspace in open_items:
        workspace["active"] = workspace.get("id") == workspace_id
        if workspace.get("id") == workspace_id:
            workspace["last_opened_at"] = now
            workspace["updated_at"] = now
    state["open_workspaces"] = open_items
    return await _save_state(state)


async def update_workspace(tenant_id: str, user_id: str, workspace_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    async with _state_lock(tenant_id, user_id):
        return await _retry_state_conflicts(lambda: _update_workspace_locked(tenant_id, user_id, workspace_id, updates))


async def _update_workspace_locked(tenant_id: str, user_id: str, workspace_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    state = await _get_or_create_state(tenant_id, user_id)
    open_items = deepcopy(state.get("open_workspaces", []))
    item = next((workspace for workspace in open_items if workspace.get("id") == workspace_id), None)
    if not item:
        raise WorkspaceDockError("Workspace not found", status_code=404)
    allowed: dict[str, Any] = {}
    if "pathname" in updates:
        allowed["pathname"] = str(updates["pathname"])
    if "query_params" in updates:
        allowed["query_params"] = _sanitize_query_params(updates["query_params"])
    if "view_state" in updates:
        allowed["view_state"] = _sanitize_view_state(updates["view_state"])
    if "scroll_position" in updates:
        allowed["scroll_position"] = max(0, int(updates["scroll_position"] or 0))
    if "dirty" in updates:
        allowed["dirty"] = bool(updates["dirty"])
    if "label" in updates and updates["label"]:
        allowed["label"] = str(updates["label"])[:120]
    allowed["updated_at"] = _now()
    item.update(allowed)
    state["open_workspaces"] = open_items
    return await _save_state(state)


async def set_pinned(tenant_id: str, user_id: str, workspace_id: str, pinned: bool) -> dict[str, Any]:
    async with _state_lock(tenant_id, user_id):
        return await _retry_state_conflicts(lambda: _set_pinned_locked(tenant_id, user_id, workspace_id, pinned))


async def _set_pinned_locked(tenant_id: str, user_id: str, workspace_id: str, pinned: bool) -> dict[str, Any]:
    state = await _get_or_create_state(tenant_id, user_id)
    open_items = deepcopy(state.get("open_workspaces", []))
    item = next((workspace for workspace in open_items if workspace.get("id") == workspace_id), None)
    if not item:
        raise WorkspaceDockError("Workspace not found", status_code=404)
    item["pinned"] = pinned
    item["updated_at"] = _now()
    state["open_workspaces"] = open_items
    return await _save_state(state)


async def reorder_workspaces(tenant_id: str, user_id: str, workspace_ids: list[str]) -> dict[str, Any]:
    async with _state_lock(tenant_id, user_id):
        return await _retry_state_conflicts(lambda: _reorder_workspaces_locked(tenant_id, user_id, workspace_ids))


async def _reorder_workspaces_locked(tenant_id: str, user_id: str, workspace_ids: list[str]) -> dict[str, Any]:
    state = await _get_or_create_state(tenant_id, user_id)
    open_items = deepcopy(state.get("open_workspaces", []))
    by_id = {item["id"]: item for item in open_items}
    if set(workspace_ids) != set(by_id):
        raise WorkspaceDockError("Reorder payload must include every open workspace", status_code=400)
    state["open_workspaces"] = [by_id[workspace_id] for workspace_id in workspace_ids]
    for index, item in enumerate(state["open_workspaces"]):
        item["position"] = index
        item["updated_at"] = _now()
    return await _save_state(state)


async def close_workspace(tenant_id: str, user_id: str, workspace_id: str) -> dict[str, Any]:
    async with _state_lock(tenant_id, user_id):
        return await _retry_state_conflicts(lambda: _close_workspace_locked(tenant_id, user_id, workspace_id))


async def _close_workspace_locked(tenant_id: str, user_id: str, workspace_id: str) -> dict[str, Any]:
    state = await _get_or_create_state(tenant_id, user_id)
    open_items = deepcopy(state.get("open_workspaces", []))
    item = next((workspace for workspace in open_items if workspace.get("id") == workspace_id), None)
    if not item:
        raise WorkspaceDockError("Workspace not found", status_code=404)
    was_active = bool(item.get("active"))
    open_items = [workspace for workspace in open_items if workspace.get("id") != workspace_id]
    now = _now()
    item.update({"status": "recent", "active": False, "position": None, "dirty": False, "closed_at": now, "updated_at": now, "last_opened_at": now})
    if was_active and open_items:
        open_items[-1]["active"] = True
    state["open_workspaces"] = open_items
    state["recent_workspaces"] = [item] + deepcopy(state.get("recent_workspaces", []))
    return await _save_state(state)


async def reopen_recent_workspace(tenant_id: str, user: dict[str, Any], workspace_id: str) -> dict[str, Any]:
    async with _state_lock(tenant_id, user["id"]):
        return await _retry_state_conflicts(lambda: _reopen_recent_workspace_locked(tenant_id, user, workspace_id))


async def _reopen_recent_workspace_locked(tenant_id: str, user: dict[str, Any], workspace_id: str) -> dict[str, Any]:
    state = await _get_or_create_state(tenant_id, user["id"])
    recent_items = deepcopy(state.get("recent_workspaces", []))
    item = next((workspace for workspace in recent_items if workspace.get("id") == workspace_id), None)
    if not item:
        raise WorkspaceDockError("Recent workspace not found", status_code=404)
    target, record = await _validate_target(tenant_id, user, item)
    return await _open_workspace_after_validation(tenant_id, user, item, target, record)


async def remove_recent_workspace(tenant_id: str, user_id: str, workspace_id: str) -> dict[str, Any]:
    async with _state_lock(tenant_id, user_id):
        return await _retry_state_conflicts(lambda: _remove_recent_workspace_locked(tenant_id, user_id, workspace_id))


async def _remove_recent_workspace_locked(tenant_id: str, user_id: str, workspace_id: str) -> dict[str, Any]:
    state = await _get_or_create_state(tenant_id, user_id)
    state["recent_workspaces"] = [workspace for workspace in deepcopy(state.get("recent_workspaces", [])) if workspace.get("id") != workspace_id]
    return await _save_state(state)
