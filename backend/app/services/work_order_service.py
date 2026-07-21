"""EC5 — Work Order service: generation, transitions, versioning, summary."""
from __future__ import annotations

from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.work_order import WorkOrder, effective_status
from ..services.audit import record_audit
from ..services.sequence import next_number


ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "draft":       {"released", "cancelled"},
    "released":    {"queued", "in_progress", "blocked", "cancelled"},
    "queued":      {"in_progress", "blocked", "cancelled"},
    "in_progress": {"blocked", "ready", "cancelled"},
    "blocked":     {"released", "queued", "in_progress", "cancelled"},
    "ready":       {"completed", "cancelled"},
    "completed":   set(),
    "cancelled":   set(),
    "superseded":  set(),
}


async def _snapshot_items(tenant_id: str, order_id: str) -> list[dict]:
    items = []
    async for it in db.order_items.find(
        {"tenant_id": tenant_id, "order_id": order_id}, {"_id": 0}
    ).sort("position", 1):
        if not it.get("production_required", True):
            continue
        items.append({
            "order_item_id": it["id"],
            "description": it["description"],
            "quantity": int(it.get("quantity", 1)),
            "unit_price_cents": int(it.get("unit_price_cents", 0)),
            "category": it.get("category"),
            "product_type": it.get("product_type"),
            "width_inches": it.get("width_inches"),
            "height_inches": it.get("height_inches"),
            "unit_of_measure": it.get("unit_of_measure"),
            "material_key": it.get("material_key"),
            "notes": it.get("notes"),
            "production_required": True,
        })
    return items


async def generate(
    *, tenant_id: str, order_id: str, actor_user_id: str, actor_email: str,
    priority: str = "normal", due_date: Optional[str] = None,
    production_instructions: Optional[str] = None, internal_notes: Optional[str] = None,
    assigned_user_ids: Optional[list[str]] = None, allow_duplicate: bool = False,
) -> tuple[dict, bool]:
    order = await db.orders.find_one({"id": order_id, "tenant_id": tenant_id})
    if not order:
        raise ValueError("order_not_found")

    if not allow_duplicate:
        existing = await db.work_orders.find_one(
            {"tenant_id": tenant_id, "order_id": order_id, "current_version": True}
        )
        if existing:
            return serialize_doc({k: v for k, v in existing.items() if k != "_id"}), True

    items = await _snapshot_items(tenant_id, order_id)
    if not items:
        raise ValueError("no_production_required_items")

    number = await next_number(tenant_id=tenant_id, name="work_order")
    wo = WorkOrder(
        tenant_id=tenant_id, number=number,
        order_id=order_id, customer_id=order["customer_id"],
        production_status="draft", priority=priority,  # type: ignore[arg-type]
        due_date=due_date, production_instructions=production_instructions,
        internal_notes=internal_notes,
        assigned_user_ids=assigned_user_ids or [],
        assigned_to=(assigned_user_ids or [None])[0],
        items_snapshot=items, created_by=actor_user_id,
    )
    await db.work_orders.insert_one(prepare_for_mongo(wo.model_dump()))
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="work_order.create", entity_type="work_order", entity_id=wo.id,
        summary=f"Work Order W-{number} created from O-{order['number']}",
        diff={"order_id": order_id, "items_count": len(items), "priority": priority},
    )
    return serialize_doc(wo.model_dump()), False


async def regenerate(
    *, tenant_id: str, work_order_id: str, reason: str, actor_user_id: str, actor_email: str,
) -> dict:
    src = await db.work_orders.find_one({"id": work_order_id, "tenant_id": tenant_id})
    if not src:
        raise ValueError("work_order_not_found")
    if not reason.strip():
        raise ValueError("reason_required")
    if src.get("production_status") in {"completed", "cancelled", "superseded"}:
        raise ValueError("work_order_not_regeneratable")

    items = await _snapshot_items(tenant_id, src["order_id"])
    if not items:
        raise ValueError("no_production_required_items")

    number = await next_number(tenant_id=tenant_id, name="work_order")
    new_wo = WorkOrder(
        tenant_id=tenant_id, number=number, order_id=src["order_id"], customer_id=src["customer_id"],
        production_status="draft", priority=src.get("priority", "normal"),
        due_date=src.get("due_date"), production_instructions=src.get("production_instructions"),
        internal_notes=src.get("internal_notes"),
        assigned_user_ids=src.get("assigned_user_ids") or [],
        assigned_to=src.get("assigned_to"),
        items_snapshot=items, created_by=actor_user_id,
        version=int(src.get("version") or 1) + 1, current_version=True,
        superseded_from=src["id"], supersede_reason=reason,
        snapshot_version=int(src.get("snapshot_version") or 1) + 1,
    )
    await db.work_orders.insert_one(prepare_for_mongo(new_wo.model_dump()))
    # Supersede the old one.
    await db.work_orders.update_one(
        {"id": src["id"], "tenant_id": tenant_id},
        {"$set": {
            "production_status": "superseded", "current_version": False,
            "superseded_by": new_wo.id, "updated_at": utc_now().isoformat(),
        }},
    )
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="work_order.regenerate", entity_type="work_order", entity_id=new_wo.id,
        summary=f"W-{src['number']} superseded by W-{number}",
        diff={"from": src["id"], "to": new_wo.id, "reason": reason},
    )
    return serialize_doc(new_wo.model_dump())


async def transition(
    *, tenant_id: str, work_order_id: str, target: str, reason: Optional[str],
    actor_user_id: str, actor_email: str,
) -> dict:
    doc = await db.work_orders.find_one({"id": work_order_id, "tenant_id": tenant_id})
    if not doc:
        raise ValueError("work_order_not_found")
    current = effective_status(doc.get("production_status"))
    if target == current:
        return serialize_doc({k: v for k, v in doc.items() if k != "_id"})
    if target not in ALLOWED_TRANSITIONS.get(current, set()):
        raise ValueError(f"invalid_transition:{current}->{target}")
    if target in {"blocked", "cancelled"} and (not reason or not reason.strip()):
        raise ValueError("reason_required")

    now = utc_now()
    updates: dict[str, Any] = {"production_status": target, "updated_at": now.isoformat()}
    if target == "released" and not doc.get("released_at"):
        updates["released_at"] = now
    if target == "in_progress" and not doc.get("started_at"):
        updates["started_at"] = now
    if target == "ready" and not doc.get("ready_at"):
        updates["ready_at"] = now
    if target == "completed":
        updates["completed_at"] = now
    if target == "cancelled":
        updates["cancelled_at"] = now
        updates["cancel_reason"] = (reason or "").strip()
    if target == "blocked":
        updates["block_reason"] = (reason or "").strip()

    await db.work_orders.update_one(
        {"id": work_order_id, "tenant_id": tenant_id},
        {"$set": prepare_for_mongo(updates)},
    )

    # Coordinate Order operational status (safe subset)
    order_status_map = {
        "released": "confirmed", "in_progress": "in_production",
        "ready": "ready", "completed": "completed",
    }
    if target in order_status_map:
        await db.orders.update_one(
            {"id": doc["order_id"], "tenant_id": tenant_id},
            {"$set": {"status": order_status_map[target], "updated_at": now.isoformat()}},
        )

    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action=f"work_order.{target}", entity_type="work_order", entity_id=work_order_id,
        summary=f"W-{doc['number']} → {target}",
        diff={"from": current, "to": target, "reason": reason},
    )
    updated = await db.work_orders.find_one({"id": work_order_id, "tenant_id": tenant_id})
    return serialize_doc({k: v for k, v in updated.items() if k != "_id"})


async def assign(
    *, tenant_id: str, work_order_id: str, user_ids: list[str],
    actor_user_id: str, actor_email: str, override_reason: Optional[str] = None,
) -> dict:
    doc = await db.work_orders.find_one({"id": work_order_id, "tenant_id": tenant_id})
    if not doc:
        raise ValueError("work_order_not_found")
    # Cross-tenant safety
    for uid in user_ids:
        u = await db.users.find_one({"id": uid, "tenant_id": tenant_id})
        if not u:
            raise ValueError(f"assignee_not_found:{uid}")
    # EC8 phase 8e — Equipment/Certification assignment-eligibility gate.
    # SAME check function used by the standalone precheck endpoint, so the
    # backend always revalidates on commit (nothing trusts only a pre-check).
    from ..services.certification_service import AssignmentBlockedError, AssignmentWarningError, check_work_order_assignment
    wo_doc = {k: v for k, v in doc.items() if k != "_id"}
    check = await check_work_order_assignment(tenant_id=tenant_id, work_order=wo_doc, user_ids=user_ids)
    if check["any_blocked"]:
        await record_audit(
            tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
            action="work_order_assignment_blocked", entity_type="work_order", entity_id=work_order_id,
            summary=f"Assignment blocked for W-{doc['number']}", diff={"check": check},
        )
        raise AssignmentBlockedError(check)
    if check["any_warning"] and not (override_reason and override_reason.strip()):
        raise AssignmentWarningError(check)
    await db.work_orders.update_one(
        {"id": work_order_id, "tenant_id": tenant_id},
        {"$set": {
            "assigned_user_ids": user_ids,
            "assigned_to": user_ids[0] if user_ids else None,
            "updated_at": utc_now().isoformat(),
        }},
    )
    # Notifications for newly assigned users
    prev = set(doc.get("assigned_user_ids") or ([doc.get("assigned_to")] if doc.get("assigned_to") else []))
    new = [u for u in user_ids if u not in prev]
    if new:
        from ..services.notifications import notify
        for uid in new:
            await notify(
                tenant_id=tenant_id, recipient_user_id=uid,
                module="work_order", kind="assigned",
                title=f"Assigned to W-{doc['number']}",
                body="Open production board",
                link=f"/work-orders/{work_order_id}",
                entity_type="work_order", entity_id=work_order_id,
            )
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="work_order.assign", entity_type="work_order", entity_id=work_order_id,
        summary=f"W-{doc['number']} assigned to {len(user_ids)} user(s)",
        diff={"user_ids": user_ids},
    )
    if check["any_warning"] and override_reason:
        await record_audit(
            tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
            action="work_order_certification_override", entity_type="work_order", entity_id=work_order_id,
            summary=f"Assignment override for W-{doc['number']}: {override_reason}",
            diff={"check": check, "override_reason": override_reason},
        )
    doc = await db.work_orders.find_one({"id": work_order_id, "tenant_id": tenant_id})
    return serialize_doc({k: v for k, v in doc.items() if k != "_id"})


def build_summary(wo: dict, order: dict, customer: dict, include_pricing: bool = False) -> dict:
    """Tenant-safe printable Work Order Summary. Excludes financial fields unless explicit perm."""
    items = []
    for it in wo.get("items_snapshot") or []:
        row = {
            "description": it.get("description"),
            "quantity": it.get("quantity"),
            "category": it.get("category"),
            "product_type": it.get("product_type"),
            "width_inches": it.get("width_inches"),
            "height_inches": it.get("height_inches"),
            "unit_of_measure": it.get("unit_of_measure"),
            "material_key": it.get("material_key"),
            "notes": it.get("notes"),
        }
        if include_pricing:
            row["unit_price_cents"] = it.get("unit_price_cents")
        items.append(row)
    return {
        "work_order_number": wo.get("number"),
        "order_number": order.get("number"),
        "customer": {"id": customer.get("id"), "name": customer.get("name")},
        "production_title": wo.get("production_instructions") or "",
        "priority": wo.get("priority"),
        "due_date": wo.get("due_date"),
        "assigned_user_ids": wo.get("assigned_user_ids") or [],
        "version": wo.get("version") or 1,
        "current_version": bool(wo.get("current_version", True)),
        "items": items,
        "production_notes": wo.get("production_instructions"),
        "generated_at": utc_now().isoformat(),
        "status": effective_status(wo.get("production_status")),
    }
