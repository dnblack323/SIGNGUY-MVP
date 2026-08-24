"""Shop Operations completion, aftercare, customer communication, and analytics.

This service extends the existing Order workspace. It reads canonical Order,
Work Order, Approval, Signature, Public Token, Communication, and audit records
instead of creating another fulfillment or messaging authority.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import serialize_doc, utc_now
from ..services import order_readiness_service
from ..services.approvals_signatures_service import create_signature_request, record_signature
from ..services.audit import record_audit
from ..services.portal_tokens import mint_public_action_token, revoke_public_action_token


ACTIVE_WORK_ORDER_STATUSES = {"draft", "released", "queued", "in_progress", "blocked", "ready"}
OPEN_ISSUE_STATUSES = {"open", "rework_required", "in_review"}
TERMINAL_ORDER_FINANCIAL_STATUSES = {"completed", "cancelled", "archived"}
ACTIVE_PRODUCTION_STAGE_STATUSES = {"ready", "in_progress", "blocked", "waiting"}
COMPLETION_OVERRIDE_ROLES = {"owner", "admin", "manager"}


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


def _now_iso() -> str:
    return utc_now().isoformat()


def _clean(value: Any, *, default: Optional[str] = None, limit: int = 2000) -> Optional[str]:
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    return text[:limit]


def _parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _minutes_between(start: Any, end: Any) -> Optional[int]:
    start_dt = _parse_dt(start)
    end_dt = _parse_dt(end)
    if not start_dt or not end_dt or end_dt < start_dt:
        return None
    return int((end_dt - start_dt).total_seconds() // 60)


def _average(values: list[int]) -> int:
    if not values:
        return 0
    return int(round(sum(values) / len(values)))


def _has_completion_override_authority(user: dict[str, Any]) -> bool:
    return str(user.get("role") or "").lower() in COMPLETION_OVERRIDE_ROLES


def _rework_order_status(order: dict[str, Any]) -> str:
    current = order.get("status") or "draft"
    if current in TERMINAL_ORDER_FINANCIAL_STATUSES:
        return current
    return "in_production"


async def _order_or_raise(tenant_id: str, order_id: str) -> dict[str, Any]:
    order = await db.orders.find_one({"tenant_id": tenant_id, "id": order_id}, {"_id": 0})
    if not order:
        raise ValueError("order_not_found")
    return order


async def _customer_for_order(tenant_id: str, order: dict[str, Any]) -> Optional[dict[str, Any]]:
    customer_id = order.get("customer_id")
    if not customer_id:
        return None
    return await db.customers.find_one({"tenant_id": tenant_id, "id": customer_id}, {"_id": 0})


async def _completion_records(tenant_id: str, order_id: str) -> list[dict[str, Any]]:
    cursor = db.order_completion_records.find({"tenant_id": tenant_id, "order_id": order_id}, {"_id": 0}).sort("created_at", -1)
    return [serialize_doc(doc) async for doc in cursor]


async def _completion_packets(tenant_id: str, order_id: str) -> list[dict[str, Any]]:
    cursor = db.order_completion_packets.find({"tenant_id": tenant_id, "order_id": order_id}, {"_id": 0}).sort("version", -1)
    return [serialize_doc(doc) async for doc in cursor]


async def _completion_issues(tenant_id: str, order_id: str) -> list[dict[str, Any]]:
    cursor = db.order_completion_issues.find({"tenant_id": tenant_id, "order_id": order_id}, {"_id": 0}).sort("created_at", -1)
    return [serialize_doc(doc) async for doc in cursor]


async def _completion_tokens(tenant_id: str, order_id: str) -> list[dict[str, Any]]:
    cursor = db.public_action_tokens.find(
        {"tenant_id": tenant_id, "action": "order_completion_review", "parent_type": "order", "parent_id": order_id},
        {"_id": 0, "token_hash": 0},
    ).sort("created_at", -1)
    return [serialize_doc(doc) async for doc in cursor]


def _token_status(token: dict[str, Any]) -> str:
    if token.get("revoked") or token.get("status") == "revoked":
        return "revoked"
    if token.get("consumed_at"):
        return "completed"
    exp = token.get("expires_at")
    try:
        parsed = datetime.fromisoformat(str(exp).replace("Z", "+00:00")) if exp else None
    except Exception:
        parsed = None
    if parsed and parsed < datetime.now(timezone.utc):
        return "expired"
    return token.get("status") or "active"


async def completion_readiness(tenant_id: str, order_id: str, *, user: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    order = await _order_or_raise(tenant_id, order_id)
    production = await order_readiness_service.evaluate_readiness(
        tenant_id=tenant_id,
        order_id=order_id,
        user=user,
        include_financial_details=False,
    )
    items = await order_readiness_service.list_order_items(tenant_id, order_id)
    work_orders_cursor = db.work_orders.find({"tenant_id": tenant_id, "order_id": order_id}, {"_id": 0})
    work_orders = [serialize_doc(wo) async for wo in work_orders_cursor]
    active_work_orders = [
        wo for wo in work_orders
        if wo.get("current_version", True) and wo.get("production_status") in ACTIVE_WORK_ORDER_STATUSES
    ]
    issues = await _completion_issues(tenant_id, order_id)
    open_issues = [issue for issue in issues if issue.get("status") in OPEN_ISSUE_STATUSES]
    latest_packet = (await _completion_packets(tenant_id, order_id) or [None])[0]
    customer = await _customer_for_order(tenant_id, order)

    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if production.get("blockers"):
        blockers.append({
            "code": "production_readiness_blocked",
            "label": "Production readiness still has unresolved blockers.",
            "required_action": "Resolve production readiness blockers before customer handoff.",
            "source": "readiness",
            "source_id": order_id,
        })
    if active_work_orders:
        blockers.append({
            "code": "active_work_order",
            "label": "A current Work Order is still active.",
            "required_action": "Complete, cancel, or supersede the active Work Order before closeout.",
            "source": "work_order",
            "source_id": active_work_orders[0].get("id"),
        })
    if open_issues:
        blockers.append({
            "code": "open_completion_issue",
            "label": "Customer issue or rework is still open.",
            "required_action": "Resolve open completion/rework issues before final closeout.",
            "source": "order_completion_issue",
            "source_id": open_issues[0].get("id"),
        })
    if not latest_packet:
        warnings.append({
            "code": "aftercare_packet_missing",
            "label": "Aftercare packet has not been generated.",
            "required_action": "Generate an aftercare packet before customer handoff.",
            "source": "order_completion_packet",
            "source_id": None,
        })
    if not customer:
        blockers.append({
            "code": "missing_customer",
            "label": "Customer record is missing.",
            "required_action": "Restore or relink the customer before closeout.",
            "source": "customer",
            "source_id": order.get("customer_id"),
        })

    ready = not blockers and order.get("status") not in {"cancelled", "archived"}
    return {
        "ready": ready,
        "status": "ready" if ready else "not_ready",
        "blockers": blockers,
        "warnings": warnings,
        "summary": {
            "item_count": len(items),
            "work_order_count": len(work_orders),
            "active_work_order_count": len(active_work_orders),
            "open_issue_count": len(open_issues),
            "packet_count": len(await _completion_packets(tenant_id, order_id)),
        },
        "evaluated_at": _now_iso(),
    }


async def completion_payload(tenant_id: str, order_id: str, *, user: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    await _order_or_raise(tenant_id, order_id)
    readiness = await completion_readiness(tenant_id, order_id, user=user)
    tokens = await _completion_tokens(tenant_id, order_id)
    return {
        "readiness": readiness,
        "records": await _completion_records(tenant_id, order_id),
        "packets": await _completion_packets(tenant_id, order_id),
        "issues": await _completion_issues(tenant_id, order_id),
        "review_links": [{**token, "status": _token_status(token)} for token in tokens],
    }


async def transition_completion(tenant_id: str, order_id: str, payload: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    order = await _order_or_raise(tenant_id, order_id)
    target = _clean(payload.get("target_status"), limit=80)
    if target not in {
        "production_complete",
        "customer_handoff_pending",
        "ready_for_pickup",
        "ready_for_delivery",
        "installed",
        "completed",
        "rework_required",
        "reopened",
        "cancelled",
    }:
        raise ValueError("invalid_completion_status")
    reason = _clean(payload.get("reason"), limit=1000)
    outcome_notes = _clean(payload.get("outcome_notes"), limit=4000)
    completion_type = _clean(payload.get("completion_type"), default="pickup", limit=80)
    readiness = await completion_readiness(tenant_id, order_id, user=user)
    if target in {"completed", "cancelled", "rework_required", "reopened"} and not reason:
        raise ValueError("reason_required")
    manager_override_required = (
        (target == "completed" and not readiness["ready"])
        or (target == "reopened" and order.get("status") in TERMINAL_ORDER_FINANCIAL_STATUSES)
        or (target in {"cancelled", "rework_required"} and order.get("status") in TERMINAL_ORDER_FINANCIAL_STATUSES)
    )
    if manager_override_required and not _has_completion_override_authority(user):
        raise PermissionError("completion_override_forbidden")

    now = _now_iso()
    record = {
        "id": _new_id("completion"),
        "tenant_id": tenant_id,
        "order_id": order_id,
        "customer_id": order.get("customer_id"),
        "from_order_status": order.get("status"),
        "target_status": target,
        "completion_type": completion_type,
        "reason": reason,
        "outcome_notes": outcome_notes,
        "evidence_file_ids": payload.get("evidence_file_ids") or [],
        "aftercare_packet_id": payload.get("aftercare_packet_id"),
        "override_applied": manager_override_required,
        "created_by_user_id": user.get("id"),
        "created_by_email": user.get("email"),
        "created_at": now,
        "readiness_snapshot": readiness,
    }
    await db.order_completion_records.insert_one(record)
    order_status = {
        "production_complete": "ready",
        "customer_handoff_pending": "ready",
        "ready_for_pickup": "ready",
        "ready_for_delivery": "ready",
        "installed": "ready",
        "completed": "completed",
        "rework_required": _rework_order_status(order),
        "reopened": _rework_order_status(order),
        "cancelled": "cancelled",
    }[target]
    updates = {
        "status": order_status,
        "completion_status": target,
        "updated_at": now,
        "completed_at": now if target == "completed" else order.get("completed_at"),
    }
    await db.orders.update_one({"tenant_id": tenant_id, "id": order_id}, {"$set": updates})
    await record_audit(
        tenant_id=tenant_id,
        actor_user_id=user["id"],
        actor_email=user["email"],
        action=f"order.completion.{target}",
        entity_type="order",
        entity_id=order_id,
        summary=f"Order completion transitioned to {target.replace('_', ' ')}",
        diff={
            "previous_status": order.get("status"),
            "new_status": order_status,
            "reason": reason,
            "completion_type": completion_type,
            "override_applied": manager_override_required,
            "readiness_ready": readiness["ready"],
            "readiness_blockers": readiness.get("blockers") or [],
            "transitioned_at": now,
        },
    )
    return serialize_doc(record)


def _aftercare_for_items(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    instructions: list[dict[str, str]] = []
    for item in items:
        label = item.get("item_name") or item.get("description") or "Order item"
        text = "Inspect at pickup/delivery and contact the shop before cleaning or altering the product."
        haystack = " ".join(str(item.get(key) or "") for key in ["category", "product_type", "description", "material_key"]).lower()
        if "wrap" in haystack or "vehicle" in haystack:
            text = "Avoid pressure washing, abrasive cleaners, and wax for the initial cure period. Report lifting or damage promptly."
        elif "decal" in haystack or "vinyl" in haystack:
            text = "Clean gently with mild soap and avoid scraping edges. Allow adhesive to cure before aggressive cleaning."
        elif "banner" in haystack:
            text = "Store rolled with printed side out and dry fully before storage."
        instructions.append({"item_id": item.get("id"), "label": label, "instruction": text})
    return instructions


def _packet_snapshot(order: dict[str, Any], customer: Optional[dict[str, Any]], items: list[dict[str, Any]], payload: dict[str, Any], version: int) -> dict[str, Any]:
    aftercare = payload.get("aftercare_instructions") or _aftercare_for_items(items)
    return {
        "schema": "order_completion_packet_v1",
        "order": {
            "id": order["id"],
            "number": order.get("number"),
            "job_name": order.get("job_name"),
            "status": order.get("status"),
            "completed_at": order.get("completed_at"),
        },
        "customer": {
            "id": customer.get("id") if customer else order.get("customer_id"),
            "name": customer.get("name") if customer else "Customer",
            "email": (customer.get("email") or customer.get("primary_email")) if customer else None,
        },
        "items": [
            {
                "id": item.get("id"),
                "description": item.get("description"),
                "quantity": item.get("quantity"),
                "category": item.get("category"),
                "production_required": item.get("production_required", True),
            }
            for item in items
        ],
        "aftercare_instructions": aftercare,
        "outcome": {
            "delivery_method": payload.get("delivery_method") or "manual",
            "installation_outcome": payload.get("installation_outcome"),
            "customer_acceptance_required": bool(payload.get("customer_acceptance_required", True)),
            "notes": _clean(payload.get("notes"), limit=4000),
        },
        "version": version,
        "generated_at": _now_iso(),
    }


async def generate_aftercare_packet(tenant_id: str, order_id: str, payload: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    order = await _order_or_raise(tenant_id, order_id)
    customer = await _customer_for_order(tenant_id, order)
    items = await order_readiness_service.list_order_items(tenant_id, order_id)
    version = await db.order_completion_packets.count_documents({"tenant_id": tenant_id, "order_id": order_id}) + 1
    snapshot = _packet_snapshot(order, customer, items, payload, version)
    packet = {
        "id": _new_id("packet"),
        "tenant_id": tenant_id,
        "order_id": order_id,
        "customer_id": order.get("customer_id"),
        "version": version,
        "status": "generated",
        "packet_type": payload.get("packet_type") or "completion_aftercare",
        "snapshot": snapshot,
        "artifact_type": "completion_packet_pdf_snapshot",
        "artifact_filename": f"order-{order.get('number') or order_id}-completion-v{version}.pdf",
        "created_by_user_id": user.get("id"),
        "created_by_email": user.get("email"),
        "created_at": _now_iso(),
    }
    await db.order_completion_packets.update_many(
        {"tenant_id": tenant_id, "order_id": order_id, "status": "generated"},
        {"$set": {"status": "superseded", "superseded_at": _now_iso()}},
    )
    await db.order_completion_packets.insert_one(packet)
    await record_audit(
        tenant_id=tenant_id,
        actor_user_id=user["id"],
        actor_email=user["email"],
        action="order.completion_packet.generated",
        entity_type="order_completion_packet",
        entity_id=packet["id"],
        summary=f"Order completion packet v{version} generated",
        diff={"order_id": order_id, "packet_type": packet["packet_type"]},
    )
    return serialize_doc(packet)


def _pdf_escape(value: Any) -> str:
    return str(value or "").replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")[:160]


def render_completion_packet_pdf(packet: dict[str, Any]) -> bytes:
    snapshot = packet.get("snapshot") or {}
    order = snapshot.get("order") or {}
    customer = snapshot.get("customer") or {}
    lines = [
        f"Order Completion Packet v{snapshot.get('version') or packet.get('version')}",
        f"Order O-{order.get('number')}: {order.get('job_name')}",
        f"Customer: {customer.get('name')}",
        f"Generated: {snapshot.get('generated_at')}",
        "Aftercare:",
    ]
    for item in snapshot.get("aftercare_instructions") or []:
        lines.append(f"- {item.get('label')}: {item.get('instruction')}")
    lines.append("Acceptance and signer evidence are recorded in the linked signature/audit records.")
    text_commands = []
    y = 760
    for line in lines[:34]:
        text_commands.append(f"BT /F1 10 Tf 50 {y} Td ({_pdf_escape(line)}) Tj ET")
        y -= 18
    stream = "\n".join(text_commands).encode("latin-1", "ignore")
    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj",
        b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj",
        b"5 0 obj << /Length " + str(len(stream)).encode() + b" >> stream\n" + stream + b"\nendstream endobj",
    ]
    pdf = [b"%PDF-1.4\n"]
    offsets = [0]
    for obj in objects:
        offsets.append(sum(len(part) for part in pdf))
        pdf.append(obj + b"\n")
    xref = sum(len(part) for part in pdf)
    pdf.append(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        pdf.append(f"{offset:010d} 00000 n \n".encode())
    pdf.append(f"trailer << /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return b"".join(pdf)


async def get_packet(tenant_id: str, order_id: str, packet_id: str) -> dict[str, Any]:
    packet = await db.order_completion_packets.find_one({"tenant_id": tenant_id, "order_id": order_id, "id": packet_id}, {"_id": 0})
    if not packet:
        raise ValueError("packet_not_found")
    return serialize_doc(packet)


async def create_review_link(tenant_id: str, order_id: str, payload: dict[str, Any], user: dict[str, Any], *, request: Any = None) -> dict[str, Any]:
    order = await _order_or_raise(tenant_id, order_id)
    packet_id = payload.get("packet_id")
    packet = await db.order_completion_packets.find_one({"tenant_id": tenant_id, "order_id": order_id, "id": packet_id}, {"_id": 0}) if packet_id else None
    if not packet:
        packet = await generate_aftercare_packet(tenant_id, order_id, payload, user)
    ttl_hours = int(payload.get("ttl_hours") or 168)
    audience_email = payload.get("recipient_email") or (await _customer_for_order(tenant_id, order) or {}).get("email")
    raw, token = await mint_public_action_token(
        tenant_id=tenant_id,
        action="order_completion_review",
        parent_type="order",
        parent_id=order_id,
        parent_version=int(packet.get("version") or 1),
        audience_email=audience_email,
        ttl_hours=ttl_hours,
        single_use=False,
        issued_by=user.get("id"),
        ip_issued=(request.client.host if request and request.client else None),
    )
    delivery = {
        "channel": payload.get("delivery_channel") or "manual_copy_link",
        "status": "manual_link_ready",
        "recipient_email": audience_email,
        "message": "No email or SMS delivery worker is claimed here; staff can copy this secure link manually.",
        "created_at": _now_iso(),
    }
    await db.public_action_tokens.update_one(
        {"tenant_id": tenant_id, "id": token["id"]},
        {"$set": {"packet_id": packet["id"], "status": "active", "delivery_history": [delivery], "updated_at": _now_iso()}},
    )
    safe_token = await db.public_action_tokens.find_one({"tenant_id": tenant_id, "id": token["id"]}, {"_id": 0, "token_hash": 0})
    await record_audit(
        tenant_id=tenant_id,
        actor_user_id=user["id"],
        actor_email=user["email"],
        action="order.completion_link.created",
        entity_type="public_action_token",
        entity_id=token["id"],
        summary="Order completion review link created",
        diff={"order_id": order_id, "packet_id": packet["id"], "delivery_status": delivery["status"]},
    )
    return {"token": serialize_doc(safe_token), "raw_token": raw, "review_url": f"/public/order-completions/{order_id}?t={raw}", "packet": packet}


async def update_review_link(tenant_id: str, token_id: str, mode: str, user: dict[str, Any]) -> bool:
    token = await db.public_action_tokens.find_one({"tenant_id": tenant_id, "id": token_id, "action": "order_completion_review"})
    if not token:
        raise ValueError("token_not_found")
    if mode == "revoke":
        ok = await revoke_public_action_token(token_id, tenant_id)
        action = "order.completion_link.revoked"
    elif mode == "expire":
        res = await db.public_action_tokens.update_one(
            {"tenant_id": tenant_id, "id": token_id},
            {"$set": {"expires_at": (utc_now() - timedelta(minutes=1)).isoformat(), "status": "expired", "updated_at": _now_iso()}},
        )
        ok = res.modified_count > 0
        action = "order.completion_link.expired"
    else:
        raise ValueError("invalid_token_action")
    if ok:
        await record_audit(
            tenant_id=tenant_id,
            actor_user_id=user["id"],
            actor_email=user["email"],
            action=action,
            entity_type="public_action_token",
            entity_id=token_id,
            summary=f"Order completion review link {mode}d",
            diff={"order_id": token.get("parent_id")},
        )
    return ok


async def communication_timeline(tenant_id: str, order_id: str) -> dict[str, Any]:
    order = await _order_or_raise(tenant_id, order_id)
    items: list[dict[str, Any]] = []

    async def add(kind: str, at: Any, title: str, *, source_type: str, source_id: Optional[str] = None, status: Optional[str] = None, summary: Optional[str] = None, customer_visible: bool = True) -> None:
        if not at:
            at = _now_iso()
        items.append({
            "kind": kind,
            "at": at,
            "title": title,
            "source_type": source_type,
            "source_id": source_id,
            "status": status,
            "summary": summary,
            "customer_visible": customer_visible,
        })

    async for thread in db.message_threads.find({"tenant_id": tenant_id, "order_id": order_id}, {"_id": 0}).sort("updated_at", -1):
        await add("message_thread", thread.get("updated_at") or thread.get("created_at"), thread.get("subject") or "Message thread", source_type="message_thread", source_id=thread.get("id"), status=thread.get("visibility"), customer_visible=thread.get("visibility") != "internal")
    async for event in db.order_customer_communications.find({"tenant_id": tenant_id, "order_id": order_id}, {"_id": 0}).sort("created_at", -1):
        await add("manual_customer_message", event.get("created_at"), event.get("subject") or "Customer message", source_type="order_customer_communication", source_id=event.get("id"), status=event.get("delivery_status"), summary=event.get("body"))
    async for token in db.public_action_tokens.find({"tenant_id": tenant_id, "parent_id": order_id}, {"_id": 0, "token_hash": 0}).sort("created_at", -1):
        await add("share_link", token.get("updated_at") or token.get("created_at"), f"{str(token.get('action') or 'Share link').replace('_', ' ').title()} link", source_type="public_action_token", source_id=token.get("id"), status=_token_status(token), summary=(token.get("delivery_history") or [{}])[-1].get("message"))
    async for room in db.decision_rooms.find({"tenant_id": tenant_id, "order_id": order_id}, {"_id": 0}).sort("updated_at", -1):
        await add("decision_room", room.get("updated_at") or room.get("created_at"), room.get("title") or "Decision Room", source_type="decision_room", source_id=room.get("id"), status=room.get("status"))
    async for record in db.order_completion_records.find({"tenant_id": tenant_id, "order_id": order_id}, {"_id": 0}).sort("created_at", -1):
        await add("completion", record.get("created_at"), f"Completion {str(record.get('target_status')).replace('_', ' ')}", source_type="order_completion_record", source_id=record.get("id"), status=record.get("target_status"), summary=record.get("outcome_notes"))
    async for issue in db.order_completion_issues.find({"tenant_id": tenant_id, "order_id": order_id}, {"_id": 0}).sort("created_at", -1):
        await add("issue", issue.get("created_at"), issue.get("title") or "Customer issue", source_type="order_completion_issue", source_id=issue.get("id"), status=issue.get("status"), summary=issue.get("description"))

    items.sort(key=lambda item: str(item.get("at") or ""), reverse=True)
    return {"order_id": order_id, "customer_id": order.get("customer_id"), "items": items}


async def create_manual_customer_message(tenant_id: str, order_id: str, payload: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    order = await _order_or_raise(tenant_id, order_id)
    subject = _clean(payload.get("subject"), default="Order update", limit=200)
    body = _clean(payload.get("body"), limit=5000)
    if not body:
        raise ValueError("message_body_required")
    doc = {
        "id": _new_id("order-msg"),
        "tenant_id": tenant_id,
        "order_id": order_id,
        "customer_id": order.get("customer_id"),
        "subject": subject,
        "body": body,
        "delivery_channel": payload.get("delivery_channel") or "manual",
        "delivery_status": "manual_delivery_ready",
        "delivery_note": "No email or SMS delivery worker is claimed here; staff must copy or send through an approved channel.",
        "created_by_user_id": user.get("id"),
        "created_by_email": user.get("email"),
        "created_at": _now_iso(),
    }
    await db.order_customer_communications.insert_one(doc)
    await record_audit(
        tenant_id=tenant_id,
        actor_user_id=user["id"],
        actor_email=user["email"],
        action="order.customer_message.prepared",
        entity_type="order_customer_communication",
        entity_id=doc["id"],
        summary=f"Customer-facing Order message prepared for O-{order.get('number')}",
        diff={"order_id": order_id, "delivery_status": doc["delivery_status"]},
    )
    return serialize_doc(doc)


async def create_completion_issue(tenant_id: str, order_id: str, payload: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    order = await _order_or_raise(tenant_id, order_id)
    title = _clean(payload.get("title"), default="Customer issue", limit=200)
    description = _clean(payload.get("description"), limit=5000)
    if not description:
        raise ValueError("issue_description_required")
    status = payload.get("status") or "open"
    if status not in {"open", "rework_required", "in_review", "resolved", "closed"}:
        raise ValueError("invalid_issue_status")
    doc = {
        "id": _new_id("issue"),
        "tenant_id": tenant_id,
        "order_id": order_id,
        "customer_id": order.get("customer_id"),
        "title": title,
        "description": description,
        "status": status,
        "reported_by": payload.get("reported_by") or "staff",
        "source": payload.get("source") or "staff",
        "evidence_file_ids": payload.get("evidence_file_ids") or [],
        "created_by_user_id": user.get("id"),
        "created_by_email": user.get("email"),
        "created_at": _now_iso(),
    }
    await db.order_completion_issues.insert_one(doc)
    if status in OPEN_ISSUE_STATUSES:
        await db.orders.update_one(
            {"tenant_id": tenant_id, "id": order_id},
            {"$set": {"completion_status": "rework_required", "status": _rework_order_status(order), "updated_at": _now_iso()}},
        )
    await record_audit(
        tenant_id=tenant_id,
        actor_user_id=user["id"],
        actor_email=user["email"],
        action="order.completion_issue.created",
        entity_type="order_completion_issue",
        entity_id=doc["id"],
        summary=f"Order completion issue opened: {title}",
        diff={"order_id": order_id, "status": status},
    )
    return serialize_doc(doc)


async def public_completion_view(raw_token: str, order_id: str, *, ip: Optional[str] = None, user_agent: Optional[str] = None) -> dict[str, Any]:
    from ..deps_portal import resolve_public_token  # imported lazily to avoid FastAPI dependency coupling
    class _Req:
        headers = {"user-agent": user_agent or ""}
        client = type("Client", (), {"host": ip})() if ip else None
    token = await resolve_public_token(_Req(), raw_token=raw_token, expected_action="order_completion_review", expected_parent_type="order", expected_parent_id=order_id)
    packet_id = token.get("packet_id")
    packet = await db.order_completion_packets.find_one({"tenant_id": token["tenant_id"], "order_id": order_id, "id": packet_id}, {"_id": 0}) if packet_id else None
    if not packet:
        packet = await db.order_completion_packets.find_one({"tenant_id": token["tenant_id"], "order_id": order_id, "version": token.get("parent_version")}, {"_id": 0})
    if not packet:
        raise ValueError("packet_not_found")
    await db.public_action_tokens.update_one(
        {"tenant_id": token["tenant_id"], "id": token["id"]},
        {"$set": {"status": "viewed", "viewed_at": _now_iso(), "updated_at": _now_iso(), "last_view_ip": ip, "last_user_agent": user_agent}},
    )
    safe = packet.get("snapshot") or {}
    return {
        "order_id": order_id,
        "packet": {
            "id": packet["id"],
            "version": packet.get("version"),
            "snapshot": safe,
            "download_url": f"/public/order-completions/{order_id}/packet?t={raw_token}",
        },
        "token": {"id": token["id"], "status": _token_status(token), "expires_at": token.get("expires_at")},
    }


async def public_completion_acknowledge(raw_token: str, order_id: str, payload: dict[str, Any], *, ip: Optional[str] = None, user_agent: Optional[str] = None) -> dict[str, Any]:
    from ..deps_portal import resolve_public_token
    class _Req:
        headers = {"user-agent": user_agent or ""}
        client = type("Client", (), {"host": ip})() if ip else None
    token = await resolve_public_token(_Req(), raw_token=raw_token, expected_action="order_completion_review", expected_parent_type="order", expected_parent_id=order_id)
    if token.get("status") == "completed" or token.get("consumed_at"):
        raise ValueError("completion_already_recorded")
    packet_id = token.get("packet_id")
    packet = await db.order_completion_packets.find_one({"tenant_id": token["tenant_id"], "order_id": order_id, "id": packet_id}, {"_id": 0}) if packet_id else None
    if not packet:
        raise ValueError("packet_not_found")
    signer_name = _clean(payload.get("signer_name"), default="Customer", limit=160)
    signer_email = _clean(payload.get("signer_email"), default=token.get("audience_email") or "customer@example.invalid", limit=254)
    parent_id = f"order-completion:{order_id}:{packet['id']}"
    request = await create_signature_request(
        tenant_id=token["tenant_id"],
        parent_type="document",
        parent_id=parent_id,
        parent_version=int(packet.get("version") or 1),
        title=f"Order completion acceptance - O-{(packet.get('snapshot') or {}).get('order', {}).get('number')}",
        description="Customer acceptance of the immutable Order completion and aftercare packet.",
        required_signers=[{"name": signer_name, "email": signer_email, "role": "customer"}],
        created_by=f"token:{token['id']}",
        actor_email=signer_email,
    )
    signature = await record_signature(
        tenant_id=token["tenant_id"],
        request_id=request["id"],
        signer_email=signer_email,
        signer_name=signer_name,
        signature_type=payload.get("signature_type") or "typed",
        typed_text=payload.get("signature_data") or signer_name,
        token_id=token["id"],
        ip=ip,
        user_agent=user_agent,
    )
    record = {
        "id": _new_id("completion"),
        "tenant_id": token["tenant_id"],
        "order_id": order_id,
        "customer_id": (packet.get("snapshot") or {}).get("customer", {}).get("id"),
        "target_status": "customer_accepted",
        "completion_type": "customer_acceptance",
        "reason": payload.get("comment"),
        "aftercare_packet_id": packet["id"],
        "signature_request_id": request["id"],
        "signature_id": signature["id"],
        "created_by_user_id": f"token:{token['id']}",
        "created_by_email": signer_email,
        "created_at": _now_iso(),
    }
    await db.order_completion_records.insert_one(record)
    await db.public_action_tokens.update_one(
        {"tenant_id": token["tenant_id"], "id": token["id"]},
        {"$set": {"status": "completed", "consumed_at": _now_iso(), "updated_at": _now_iso()}},
    )
    await db.orders.update_one(
        {"tenant_id": token["tenant_id"], "id": order_id},
        {"$set": {"completion_status": "customer_accepted", "status": "completed", "completed_at": _now_iso(), "updated_at": _now_iso()}},
    )
    return {"record": serialize_doc(record), "signature": signature}


async def public_completion_issue(raw_token: str, order_id: str, payload: dict[str, Any], *, ip: Optional[str] = None, user_agent: Optional[str] = None) -> dict[str, Any]:
    from ..deps_portal import resolve_public_token
    class _Req:
        headers = {"user-agent": user_agent or ""}
        client = type("Client", (), {"host": ip})() if ip else None
    token = await resolve_public_token(_Req(), raw_token=raw_token, expected_action="order_completion_review", expected_parent_type="order", expected_parent_id=order_id)
    order = await _order_or_raise(token["tenant_id"], order_id)
    doc = {
        "id": _new_id("issue"),
        "tenant_id": token["tenant_id"],
        "order_id": order_id,
        "title": _clean(payload.get("title"), default="Customer reported issue", limit=200),
        "description": _clean(payload.get("description"), default="", limit=5000),
        "status": "open",
        "reported_by": "customer",
        "source": "public_completion_review",
        "public_token_id": token["id"],
        "ip": ip,
        "user_agent": user_agent,
        "created_at": _now_iso(),
    }
    if not doc["description"]:
        raise ValueError("issue_description_required")
    await db.order_completion_issues.insert_one(doc)
    await db.orders.update_one(
        {"tenant_id": token["tenant_id"], "id": order_id},
        {"$set": {"completion_status": "rework_required", "status": _rework_order_status(order), "updated_at": _now_iso()}},
    )
    return {"issue": serialize_doc(doc)}


async def shop_operations_analytics(tenant_id: str) -> dict[str, Any]:
    orders_active = await db.orders.count_documents({"tenant_id": tenant_id, "status": {"$in": ["confirmed", "in_production", "ready"]}})
    open_issues = await db.order_completion_issues.count_documents({"tenant_id": tenant_id, "status": {"$in": list(OPEN_ISSUE_STATUSES)}})
    completion_count = await db.order_completion_records.count_documents({"tenant_id": tenant_id, "target_status": {"$in": ["completed", "customer_accepted"]}})
    active_stage_counts: dict[str, int] = {}
    queue_minutes: list[int] = []
    cycle_minutes: list[int] = []
    blocked_labels: dict[str, int] = {}
    waiting_labels: dict[str, int] = {}
    async for stage in db.production_stage_instances.find(
        {"tenant_id": tenant_id, "status": {"$in": list(ACTIVE_PRODUCTION_STAGE_STATUSES | {"completed"})}},
        {
            "_id": 0,
            "stage_name": 1,
            "status": 1,
            "work_area_id": 1,
            "created_at": 1,
            "started_at": 1,
            "completed_at": 1,
            "actual_duration_seconds": 1,
        },
    ):
        key = stage.get("stage_name") or stage.get("work_area_id") or "Unassigned"
        status = stage.get("status")
        if status in ACTIVE_PRODUCTION_STAGE_STATUSES:
            active_stage_counts[key] = active_stage_counts.get(key, 0) + 1
        if status == "blocked":
            blocked_labels[key] = blocked_labels.get(key, 0) + 1
        if status == "waiting":
            waiting_labels[key] = waiting_labels.get(key, 0) + 1
        queued_for = _minutes_between(stage.get("created_at"), stage.get("started_at"))
        if queued_for is not None:
            queue_minutes.append(queued_for)
        cycled_for = _minutes_between(stage.get("created_at"), stage.get("completed_at"))
        if cycled_for is not None:
            cycle_minutes.append(cycled_for)
    blocked = await db.production_stage_instances.count_documents({"tenant_id": tenant_id, "status": "blocked"})
    waiting = await db.production_stage_instances.count_documents({"tenant_id": tenant_id, "status": "waiting"})
    effective_seconds = 0
    async for session in db.production_time_entries.find({"tenant_id": tenant_id, "status": {"$ne": "voided"}}, {"_id": 0, "effective_elapsed_seconds": 1, "corrected_elapsed_seconds": 1}):
        value = session.get("corrected_elapsed_seconds")
        if value is None:
            value = session.get("effective_elapsed_seconds")
        try:
            effective_seconds += max(0, int(value or 0))
        except (TypeError, ValueError):
            continue
    recent_completion_cursor = db.order_completion_records.find({"tenant_id": tenant_id}, {"_id": 0}).sort("created_at", -1).limit(10)
    recent_completion = [serialize_doc(row) async for row in recent_completion_cursor]
    bottlenecks = [
        {"label": label, "active_count": count, "signal": "stage_capacity"}
        for label, count in sorted(active_stage_counts.items(), key=lambda item: item[1], reverse=True)
    ][:8]
    delay_labels = dict(blocked_labels)
    for label, count in waiting_labels.items():
        delay_labels[label] = delay_labels.get(label, 0) + count
    repeated_delays = [
        {"label": label, "active_count": count, "signal": "repeated_delay"}
        for label, count in sorted(delay_labels.items(), key=lambda item: item[1], reverse=True)
        if count > 1
    ]
    bottlenecks.extend(repeated_delays[:4])
    if open_issues:
        bottlenecks.insert(0, {"label": "Customer issues / rework", "active_count": open_issues, "signal": "completion_rework"})
    return {
        "counts": {
            "active_orders": orders_active,
            "open_completion_issues": open_issues,
            "completed_orders": completion_count,
            "blocked_stages": blocked,
            "waiting_stages": waiting,
        },
        "time_summary": {
            "average_queue_minutes": _average(queue_minutes),
            "average_active_minutes": int(round(effective_seconds / 60)) if effective_seconds else 0,
            "average_cycle_minutes": _average(cycle_minutes),
            "blocked_stage_count": blocked,
            "waiting_stage_count": waiting,
            "repeated_delay_count": len(repeated_delays),
        },
        "bottlenecks": bottlenecks,
        "recent_completion": recent_completion,
        "restricted_financial_data": False,
        "generated_at": _now_iso(),
    }
