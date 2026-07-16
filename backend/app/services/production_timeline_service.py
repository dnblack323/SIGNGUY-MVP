"""EC11 Phase 11B - normalized production timeline projection.

This service does not own event storage. It projects existing authoritative
records (orders, order items, work orders, proofs, approvals, attachments,
invoices, payments, audit, and activity) into one read-only timeline shape.

Deduplication/source priority:
1. Direct domain records are preferred for lifecycle facts.
2. Audit records fill transition/update facts and actor context.
3. Activity records are lowest priority display feed facts.
Singleton lifecycle events are keyed by source_type + source_id + event_type;
transition/update events additionally include timestamp/status sequence.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from ..core.db import db
from ..core.time_utils import serialize_doc

TimelineScope = str

SINGLETON_EVENT_TYPES = {
    "order_created",
    "order_item_created",
    "work_order_created",
    "proof_created",
    "invoice_created",
    "payment_recorded",
    "document_uploaded",
    "artwork_uploaded",
    "artwork_version_uploaded",
}

CUSTOMER_VISIBLE_TYPES = {
    "artwork_uploaded",
    "artwork_version_uploaded",
    "proof_created",
    "proof_sent",
    "proof_approved",
    "proof_revision_requested",
    "document_uploaded",
    "invoice_created",
    "payment_recorded",
}

SAFE_METADATA_KEYS = {
    "action",
    "amount_cents",
    "attachment_id",
    "document_status",
    "filename",
    "financial_status",
    "invoice_number",
    "mime_type",
    "number",
    "parent_id",
    "parent_type",
    "payment_status",
    "proof_number",
    "size_bytes",
    "status",
    "version",
    "visibility",
}


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    return str(value)


def _dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            cleaned = value.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(cleaned)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _event_id(*parts: Any) -> str:
    raw = "|".join("" if p is None else str(p) for p in parts)
    return "tl_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]


def _dedupe_key(event: dict[str, Any]) -> str:
    base = f"{event.get('source_type')}:{event.get('source_id')}:{event.get('event_type')}"
    if event.get("event_type") in SINGLETON_EVENT_TYPES:
        return base
    seq = event.get("status_to") or event.get("occurred_at") or event.get("id")
    return f"{base}:{seq}"


def _safe_metadata(meta: Optional[dict[str, Any]]) -> dict[str, Any]:
    if not meta:
        return {}
    return {k: v for k, v in meta.items() if k in SAFE_METADATA_KEYS and v is not None}


def _actor_from_user(user_id: Optional[str], label: Optional[str] = None) -> dict[str, Any]:
    return {
        "actor_type": "staff" if user_id else "system",
        "actor_user_id": user_id,
        "actor_employee_id": None,
        "actor_customer_id": None,
        "actor_label": label or user_id or "System",
    }


def _actor_from_approval(approval: dict[str, Any]) -> dict[str, Any]:
    actor_type = approval.get("actor_type") or "staff"
    actor_ref = approval.get("actor_ref")
    return {
        "actor_type": actor_type,
        "actor_user_id": actor_ref if actor_type == "staff" else None,
        "actor_employee_id": None,
        "actor_customer_id": actor_ref if actor_type in {"portal_customer", "public_token"} else None,
        "actor_label": approval.get("actor_display") or actor_ref or actor_type,
    }


def _make_event(
    *,
    tenant_id: str,
    event_type: str,
    event_category: str,
    source_type: str,
    source_id: str,
    order_id: Optional[str],
    occurred_at: Any,
    title: str,
    internal_summary: str,
    customer_safe_summary: Optional[str] = None,
    order_item_id: Optional[str] = None,
    work_order_id: Optional[str] = None,
    visibility: Optional[str] = None,
    actor: Optional[dict[str, Any]] = None,
    status_from: Optional[str] = None,
    status_to: Optional[str] = None,
    duration_seconds: Optional[int] = None,
    related_file_id: Optional[str] = None,
    related_proof_id: Optional[str] = None,
    related_invoice_id: Optional[str] = None,
    related_payment_id: Optional[str] = None,
    related_workflow_id: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
    links: Optional[list[dict[str, str]]] = None,
) -> dict[str, Any]:
    occurred = _iso(occurred_at)
    actor = actor or _actor_from_user(None)
    visibility = visibility or ("customer_visible" if event_type in CUSTOMER_VISIBLE_TYPES else "internal_only")
    event_id = _event_id(source_type, source_id, event_type, occurred, status_to or "")
    return {
        "id": event_id,
        "tenant_id": tenant_id,
        "event_type": event_type,
        "event_category": event_category,
        "source_type": source_type,
        "source_id": source_id,
        "order_id": order_id,
        "order_item_id": order_item_id,
        "work_order_id": work_order_id,
        **actor,
        "title": title,
        "customer_safe_summary": customer_safe_summary or title,
        "internal_summary": internal_summary,
        "occurred_at": occurred,
        "duration_seconds": duration_seconds,
        "status_from": status_from,
        "status_to": status_to,
        "related_file_id": related_file_id,
        "related_proof_id": related_proof_id,
        "related_invoice_id": related_invoice_id,
        "related_payment_id": related_payment_id,
        "related_workflow_id": related_workflow_id,
        "visibility": visibility,
        "metadata": _safe_metadata(metadata),
        "links": links or [],
    }


def _add_event(events: dict[str, dict[str, Any]], event: Optional[dict[str, Any]]) -> None:
    if not event or not event.get("occurred_at"):
        return
    key = _dedupe_key(event)
    if key not in events:
        events[key] = event


async def _docs(collection: str, query: dict[str, Any], sort: Optional[list[tuple[str, int]]] = None) -> list[dict[str, Any]]:
    cur = db[collection].find(query, {"_id": 0})
    if sort:
        cur = cur.sort(sort)
    return [serialize_doc(doc) async for doc in cur]


def _id_list(values: Iterable[Optional[str]]) -> list[str]:
    return sorted({v for v in values if v})


async def _scope_data(tenant_id: str, scope: TimelineScope, source_id: str) -> dict[str, Any]:
    if scope == "order":
        order = await db.orders.find_one({"tenant_id": tenant_id, "id": source_id}, {"_id": 0})
        if not order:
            raise ValueError("order_not_found")
        items = await _docs("order_items", {"tenant_id": tenant_id, "order_id": source_id})
        work_orders = await _docs("work_orders", {"tenant_id": tenant_id, "order_id": source_id})
        return {"order": serialize_doc(order), "items": items, "work_orders": work_orders}

    if scope == "order_item":
        item = await db.order_items.find_one({"tenant_id": tenant_id, "id": source_id}, {"_id": 0})
        if not item:
            raise ValueError("order_item_not_found")
        order = await db.orders.find_one({"tenant_id": tenant_id, "id": item["order_id"]}, {"_id": 0})
        if not order:
            raise ValueError("order_not_found")
        work_orders = await _docs(
            "work_orders",
            {"tenant_id": tenant_id, "order_id": item["order_id"], "items_snapshot.order_item_id": source_id},
        )
        return {"order": serialize_doc(order), "items": [serialize_doc(item)], "work_orders": work_orders}

    if scope == "work_order":
        wo = await db.work_orders.find_one({"tenant_id": tenant_id, "id": source_id}, {"_id": 0})
        if not wo:
            raise ValueError("work_order_not_found")
        order = await db.orders.find_one({"tenant_id": tenant_id, "id": wo["order_id"]}, {"_id": 0})
        item_ids = _id_list((row or {}).get("order_item_id") for row in (wo.get("items_snapshot") or []))
        items = await _docs("order_items", {"tenant_id": tenant_id, "id": {"$in": item_ids}}) if item_ids else []
        return {"order": serialize_doc(order), "items": items, "work_orders": [serialize_doc(wo)]}

    raise ValueError("invalid_scope")


async def _collect_related(tenant_id: str, data: dict[str, Any]) -> dict[str, Any]:
    order = data.get("order") or {}
    order_id = order.get("id")
    item_ids = _id_list(item.get("id") for item in data.get("items") or [])
    work_order_ids = _id_list(wo.get("id") for wo in data.get("work_orders") or [])

    proof_parent_filters: list[dict[str, Any]] = []
    if order_id:
        proof_parent_filters.append({"parent_type": "order", "parent_id": order_id})
    if item_ids:
        proof_parent_filters.append({"parent_type": "order_item", "parent_id": {"$in": item_ids}})
    if work_order_ids:
        proof_parent_filters.append({"parent_type": "work_order", "parent_id": {"$in": work_order_ids}})
    proof_query = {"tenant_id": tenant_id, "$or": proof_parent_filters} if proof_parent_filters else {"tenant_id": tenant_id, "id": "__none__"}
    proofs = await _docs("proofs", proof_query)
    proof_ids = _id_list(p.get("id") for p in proofs)
    proof_versions = await _docs("proof_versions", {"tenant_id": tenant_id, "proof_id": {"$in": proof_ids}}) if proof_ids else []
    approvals = await _docs("approvals", {"tenant_id": tenant_id, "parent_type": "proof_version", "parent_id": {"$in": _id_list(v.get("id") for v in proof_versions)}}) if proof_versions else []

    attachment_filters: list[dict[str, Any]] = []
    if order_id:
        attachment_filters.append({"parent_type": "order", "parent_id": order_id})
    if item_ids:
        attachment_filters.append({"parent_type": "order_item", "parent_id": {"$in": item_ids}})
    if work_order_ids:
        attachment_filters.append({"parent_type": "work_order", "parent_id": {"$in": work_order_ids}})
    attachments = await _docs("attachments", {"tenant_id": tenant_id, "$or": attachment_filters}) if attachment_filters else []
    file_ids = _id_list([a.get("file_id") for a in attachments] + [v.get("file_id") for v in proof_versions])
    files = await _docs("files", {"tenant_id": tenant_id, "id": {"$in": file_ids}}) if file_ids else []
    files_by_id = {f["id"]: f for f in files}

    invoices = await _docs("invoices", {"tenant_id": tenant_id, "order_id": order_id}) if order_id else []
    invoice_ids = _id_list(i.get("id") for i in invoices)
    payments = await _docs("payments", {"tenant_id": tenant_id, "$or": [{"invoice_id": {"$in": invoice_ids}}, {"order_id": order_id}]}) if invoice_ids or order_id else []

    return {
        "proofs": proofs,
        "proof_versions": proof_versions,
        "approvals": approvals,
        "attachments": attachments,
        "files_by_id": files_by_id,
        "invoices": invoices,
        "payments": payments,
    }


def _parent_ids_for_proof(proof: dict[str, Any], data: dict[str, Any]) -> tuple[Optional[str], Optional[str], Optional[str]]:
    order_id = (data.get("order") or {}).get("id")
    if proof.get("parent_type") == "order_item":
        return order_id, proof.get("parent_id"), None
    if proof.get("parent_type") == "work_order":
        wo = next((w for w in data.get("work_orders") or [] if w.get("id") == proof.get("parent_id")), {})
        return wo.get("order_id") or order_id, None, proof.get("parent_id")
    return proof.get("parent_id") or order_id, None, None


def _attachment_context(att: dict[str, Any], data: dict[str, Any]) -> tuple[Optional[str], Optional[str], Optional[str]]:
    order_id = (data.get("order") or {}).get("id")
    if att.get("parent_type") == "order_item":
        return order_id, att.get("parent_id"), None
    if att.get("parent_type") == "work_order":
        wo = next((w for w in data.get("work_orders") or [] if w.get("id") == att.get("parent_id")), {})
        return wo.get("order_id") or order_id, None, att.get("parent_id")
    return att.get("parent_id") or order_id, None, None


def _project_direct_events(tenant_id: str, data: dict[str, Any], related: dict[str, Any]) -> dict[str, dict[str, Any]]:
    events: dict[str, dict[str, Any]] = {}
    order = data.get("order") or {}
    if order:
        _add_event(events, _make_event(
            tenant_id=tenant_id, event_type="order_created", event_category="order",
            source_type="order", source_id=order["id"], order_id=order["id"],
            occurred_at=order.get("created_at"), title=f"Order O-{order.get('number')} created",
            internal_summary=f"Order O-{order.get('number')} was created.",
            actor=_actor_from_user(order.get("created_by")), status_to=order.get("status"),
            metadata={"number": order.get("number"), "status": order.get("status")},
            links=[{"label": f"O-{order.get('number')}", "to": f"/orders/{order['id']}"}],
        ))

    for item in data.get("items") or []:
        _add_event(events, _make_event(
            tenant_id=tenant_id, event_type="order_item_created", event_category="order_item",
            source_type="order_item", source_id=item["id"], order_id=item.get("order_id"),
            order_item_id=item["id"], occurred_at=item.get("created_at"),
            title="Order item created", internal_summary=f"Order item created: {item.get('description')}",
            customer_safe_summary=f"Order item added: {item.get('description')}",
            metadata={"status": item.get("proof_status")},
            links=[{"label": "Order", "to": f"/orders/{item.get('order_id')}"}],
        ))
        if item.get("updated_at") and item.get("updated_at") != item.get("created_at"):
            _add_event(events, _make_event(
                tenant_id=tenant_id, event_type="order_item_updated", event_category="order_item",
                source_type="order_item", source_id=item["id"], order_id=item.get("order_id"),
                order_item_id=item["id"], occurred_at=item.get("updated_at"),
                title="Order item updated", internal_summary=f"Order item updated: {item.get('description')}",
                visibility="internal_only",
            ))

    for wo in data.get("work_orders") or []:
        _add_event(events, _make_event(
            tenant_id=tenant_id, event_type="work_order_created", event_category="work_order",
            source_type="work_order", source_id=wo["id"], order_id=wo.get("order_id"),
            work_order_id=wo["id"], occurred_at=wo.get("created_at"),
            title=f"Work order W-{wo.get('number')} created",
            internal_summary=f"Work order W-{wo.get('number')} was created.",
            actor=_actor_from_user(wo.get("created_by")), status_to=wo.get("production_status"),
            metadata={"number": wo.get("number"), "status": wo.get("production_status")},
            links=[{"label": f"W-{wo.get('number')}", "to": f"/work-orders/{wo['id']}"}],
        ))
        if wo.get("assigned_user_ids") or wo.get("assigned_to"):
            _add_event(events, _make_event(
                tenant_id=tenant_id, event_type="work_order_assigned", event_category="work_order",
                source_type="work_order", source_id=wo["id"], order_id=wo.get("order_id"),
                work_order_id=wo["id"], occurred_at=wo.get("updated_at") or wo.get("created_at"),
                title=f"Work order W-{wo.get('number')} assigned",
                internal_summary=f"Work order assigned to {len(wo.get('assigned_user_ids') or [])} user(s).",
                visibility="employee_visible", metadata={"number": wo.get("number")},
            ))

    proofs_by_id = {p["id"]: p for p in related["proofs"]}
    for proof in related["proofs"]:
        order_id, item_id, wo_id = _parent_ids_for_proof(proof, data)
        _add_event(events, _make_event(
            tenant_id=tenant_id, event_type="proof_created", event_category="proof",
            source_type="proof", source_id=proof["id"], order_id=order_id,
            order_item_id=item_id, work_order_id=wo_id, occurred_at=proof.get("created_at"),
            title=f"Proof P-{proof.get('number')} created",
            internal_summary=f"Proof created: {proof.get('title')}",
            customer_safe_summary=f"Proof created: {proof.get('title')}",
            actor=_actor_from_user(proof.get("created_by")), related_proof_id=proof["id"],
            metadata={"proof_number": proof.get("number"), "status": proof.get("status")},
            links=[{"label": f"P-{proof.get('number')}", "to": f"/proofs/{proof['id']}"}],
        ))
        if proof.get("last_sent_at"):
            _add_event(events, _make_event(
                tenant_id=tenant_id, event_type="proof_sent", event_category="proof",
                source_type="proof", source_id=proof["id"], order_id=order_id,
                order_item_id=item_id, work_order_id=wo_id, occurred_at=proof.get("last_sent_at"),
                title=f"Proof P-{proof.get('number')} sent",
                internal_summary=f"Proof sent: {proof.get('title')}", related_proof_id=proof["id"],
                status_to="sent", metadata={"proof_number": proof.get("number")},
            ))
        if proof.get("approved_at"):
            _add_event(events, _make_event(
                tenant_id=tenant_id, event_type="proof_approved", event_category="proof",
                source_type="proof", source_id=proof["id"], order_id=order_id,
                order_item_id=item_id, work_order_id=wo_id, occurred_at=proof.get("approved_at"),
                title=f"Proof P-{proof.get('number')} approved",
                internal_summary=f"Proof approved: {proof.get('title')}", related_proof_id=proof["id"],
                status_to="approved", metadata={"proof_number": proof.get("number")},
            ))
        if proof.get("changes_requested_at"):
            _add_event(events, _make_event(
                tenant_id=tenant_id, event_type="proof_revision_requested", event_category="proof",
                source_type="proof", source_id=proof["id"], order_id=order_id,
                order_item_id=item_id, work_order_id=wo_id, occurred_at=proof.get("changes_requested_at"),
                title=f"Revision requested for P-{proof.get('number')}",
                internal_summary=proof.get("changes_requested_reason") or "Proof revision requested.",
                customer_safe_summary="Proof revision requested.", related_proof_id=proof["id"],
                status_to="changes_requested", metadata={"proof_number": proof.get("number")},
            ))

    for version in related["proof_versions"]:
        proof = proofs_by_id.get(version.get("proof_id"), {})
        order_id, item_id, wo_id = _parent_ids_for_proof(proof, data)
        _add_event(events, _make_event(
            tenant_id=tenant_id, event_type="artwork_version_uploaded", event_category="document",
            source_type="proof_version", source_id=version["id"], order_id=order_id,
            order_item_id=item_id, work_order_id=wo_id, occurred_at=version.get("created_at"),
            title=f"Proof version v{version.get('version')} uploaded",
            internal_summary=f"Proof version v{version.get('version')} uploaded.",
            related_file_id=version.get("file_id"), related_proof_id=version.get("proof_id"),
            actor=_actor_from_user(version.get("created_by")),
            metadata={"version": version.get("version")},
        ))

    versions_by_id = {v["id"]: v for v in related["proof_versions"]}
    for approval in related["approvals"]:
        version = versions_by_id.get(approval.get("parent_id"), {})
        proof = proofs_by_id.get(version.get("proof_id"), {})
        order_id, item_id, wo_id = _parent_ids_for_proof(proof, data)
        event_type = "proof_approved" if approval.get("action") == "approve" else "proof_revision_requested"
        title = "Proof approved" if event_type == "proof_approved" else "Proof revision requested"
        _add_event(events, _make_event(
            tenant_id=tenant_id, event_type=event_type, event_category="proof",
            source_type="approval", source_id=approval["id"], order_id=order_id,
            order_item_id=item_id, work_order_id=wo_id, occurred_at=approval.get("created_at"),
            title=title, internal_summary=approval.get("reason") or title,
            customer_safe_summary=title, actor=_actor_from_approval(approval),
            status_to="approved" if event_type == "proof_approved" else "changes_requested",
            related_proof_id=version.get("proof_id"),
            metadata={"version": version.get("version")},
        ))

    for att in related["attachments"]:
        file_doc = related["files_by_id"].get(att.get("file_id"), {})
        order_id, item_id, wo_id = _attachment_context(att, data)
        event_type = "artwork_uploaded" if att.get("parent_type") in {"order_item", "work_order"} else "document_uploaded"
        _add_event(events, _make_event(
            tenant_id=tenant_id, event_type=event_type, event_category="document",
            source_type="attachment", source_id=att["id"], order_id=order_id,
            order_item_id=item_id, work_order_id=wo_id, occurred_at=att.get("created_at"),
            title=file_doc.get("original_filename") or "Document uploaded",
            internal_summary=f"Attached {file_doc.get('original_filename') or 'file'} to {att.get('parent_type')}.",
            customer_safe_summary=file_doc.get("original_filename") or "Document uploaded",
            actor=_actor_from_user(att.get("attached_by")), related_file_id=att.get("file_id"),
            visibility="customer_visible" if file_doc.get("visibility") == "customer_visible" else "internal_only",
            metadata={
                "attachment_id": att.get("id"),
                "filename": file_doc.get("original_filename"),
                "mime_type": file_doc.get("mime_type"),
                "size_bytes": file_doc.get("size_bytes"),
                "visibility": file_doc.get("visibility"),
                "parent_type": att.get("parent_type"),
                "parent_id": att.get("parent_id"),
            },
        ))

    for inv in related["invoices"]:
        _add_event(events, _make_event(
            tenant_id=tenant_id, event_type="invoice_created", event_category="invoice",
            source_type="invoice", source_id=inv["id"], order_id=inv.get("order_id"),
            occurred_at=inv.get("created_at"), title=f"Invoice I-{inv.get('number')} created",
            internal_summary=f"Invoice I-{inv.get('number')} created.",
            actor=_actor_from_user(inv.get("created_by")), related_invoice_id=inv["id"],
            metadata={"invoice_number": inv.get("number"), "document_status": inv.get("document_status"), "financial_status": inv.get("financial_status")},
            links=[{"label": f"I-{inv.get('number')}", "to": f"/invoices/{inv['id']}"}],
        ))

    for pay in related["payments"]:
        _add_event(events, _make_event(
            tenant_id=tenant_id, event_type="payment_recorded", event_category="payment",
            source_type="payment", source_id=pay["id"], order_id=pay.get("order_id") or order.get("id"),
            occurred_at=pay.get("confirmed_at") or pay.get("created_at"), title="Payment recorded",
            internal_summary=f"Payment recorded for {pay.get('amount_cents') or 0} cents.",
            customer_safe_summary="Payment recorded.", actor=_actor_from_user(pay.get("created_by")),
            related_invoice_id=pay.get("invoice_id"), related_payment_id=pay["id"],
            metadata={"amount_cents": pay.get("amount_cents"), "payment_status": pay.get("status")},
        ))

    return events


def _map_audit_event(audit: dict[str, Any], data: dict[str, Any], related: dict[str, Any]) -> Optional[dict[str, Any]]:
    tenant_id = audit["tenant_id"]
    action = audit.get("action") or ""
    entity_type = audit.get("entity_type")
    entity_id = audit.get("entity_id")
    diff = audit.get("diff") or {}
    order = data.get("order") or {}
    order_id = order.get("id")
    actor = {
        "actor_type": "staff" if not str(audit.get("actor_user_id", "")).startswith("portal:") else "portal_customer",
        "actor_user_id": audit.get("actor_user_id") if not str(audit.get("actor_user_id", "")).startswith("portal:") else None,
        "actor_employee_id": None,
        "actor_customer_id": audit.get("actor_user_id") if str(audit.get("actor_user_id", "")).startswith("portal:") else None,
        "actor_label": audit.get("actor_email") or audit.get("actor_user_id") or "System",
    }

    event_type: Optional[str] = None
    category = entity_type or "activity"
    source_id = entity_id
    item_id = diff.get("item_id")
    wo_id = entity_id if entity_type == "work_order" else None
    proof_id = entity_id if entity_type == "proof" else None
    invoice_id = entity_id if entity_type == "invoice" else None
    payment_id = diff.get("payment_id")
    file_id = diff.get("file_id")
    visibility = "internal_only"
    source_type = entity_type or "audit"
    title = audit.get("summary") or action
    status_from = diff.get("from")
    status_to = diff.get("to")

    if action == "order.created":
        event_type = "order_created"
        category = "order"
    elif action == "order.updated":
        changes = diff.get("changes") or {}
        event_type = "due_date_changed" if "due_date" in changes else "order_updated"
        category = "order"
    elif action.startswith("order.status."):
        event_type = "order_status_changed"
        category = "order"
    elif action == "order.item_added":
        event_type = "order_item_created"
        category = "order_item"
        source_id = item_id or entity_id
        source_type = "order_item"
    elif action == "order.item_updated":
        event_type = "order_item_updated"
        category = "order_item"
        source_id = item_id or entity_id
        source_type = "order_item"
    elif action == "work_order.create":
        event_type = "work_order_created"
        category = "work_order"
    elif action == "work_order.assign":
        event_type = "work_order_assigned"
        category = "work_order"
        visibility = "employee_visible"
    elif action == "work_order.update":
        changes = diff.get("changes") or {}
        if "due_date" in changes:
            event_type = "due_date_changed"
        elif "internal_notes" in changes or "production_instructions" in changes:
            event_type = "production_note_added"
        else:
            event_type = "order_updated"
        category = "work_order"
    elif action.startswith("work_order.") and action not in {"work_order.create", "work_order.assign", "work_order.update"}:
        event_type = "work_order_status_changed"
        category = "work_order"
    elif action == "proof.create":
        event_type = "proof_created"
        category = "proof"
        proof_id = entity_id
    elif action == "proof.add_version":
        event_type = "artwork_version_uploaded"
        category = "document"
        proof_id = entity_id
    elif action == "proof.sent":
        event_type = "proof_sent"
        category = "proof"
        proof_id = entity_id
        visibility = "customer_visible"
    elif action == "proof.approved":
        event_type = "proof_approved"
        category = "proof"
        proof_id = entity_id
        visibility = "customer_visible"
    elif action == "proof.changes_requested":
        event_type = "proof_revision_requested"
        category = "proof"
        proof_id = entity_id
        visibility = "customer_visible"
    elif action == "attachment.create":
        event_type = "artwork_uploaded" if entity_type in {"order_item", "work_order"} else "document_uploaded"
        category = "document"
        source_id = diff.get("attachment_id") or entity_id
        source_type = "attachment"
    elif action == "invoice.create":
        event_type = "invoice_created"
        category = "invoice"
    elif action in {"invoice.payment_added", "payment_recorded_manual", "payment_confirmed_stripe"}:
        event_type = "payment_recorded"
        category = "payment"
        if payment_id:
            source_id = payment_id
            source_type = "payment"

    if not event_type:
        return None

    if proof_id:
        proof = next((p for p in related["proofs"] if p.get("id") == proof_id), {})
        order_id, item_id, wo_id = _parent_ids_for_proof(proof, data)
    elif wo_id:
        wo = next((w for w in data.get("work_orders") or [] if w.get("id") == wo_id), {})
        order_id = wo.get("order_id") or order_id

    return _make_event(
        tenant_id=tenant_id, event_type=event_type, event_category=category,
        source_type=source_type, source_id=source_id or audit["id"], order_id=order_id,
        order_item_id=item_id, work_order_id=wo_id, occurred_at=audit.get("created_at"),
        title=title, internal_summary=audit.get("summary") or title,
        customer_safe_summary=title, actor=actor, status_from=status_from, status_to=status_to,
        related_file_id=file_id, related_proof_id=proof_id, related_invoice_id=invoice_id,
        related_payment_id=payment_id, visibility=visibility,
        metadata={"action": action},
    )


async def _project_audit_events(tenant_id: str, data: dict[str, Any], related: dict[str, Any], events: dict[str, dict[str, Any]]) -> None:
    ids_by_type: dict[str, list[str]] = {
        "order": _id_list([(data.get("order") or {}).get("id")]),
        "order_item": _id_list(item.get("id") for item in data.get("items") or []),
        "work_order": _id_list(wo.get("id") for wo in data.get("work_orders") or []),
        "proof": _id_list(p.get("id") for p in related["proofs"]),
        "invoice": _id_list(i.get("id") for i in related["invoices"]),
    }
    filters = [{"entity_type": typ, "entity_id": {"$in": ids}} for typ, ids in ids_by_type.items() if ids]
    if not filters:
        return
    audits = await _docs("audit_events", {"tenant_id": tenant_id, "$or": filters}, [("created_at", -1)])
    for audit in audits:
        _add_event(events, _map_audit_event(audit, data, related))


def _matches_filters(event: dict[str, Any], filters: dict[str, Any]) -> bool:
    if filters.get("event_category") and event.get("event_category") != filters["event_category"]:
        return False
    if filters.get("event_type") and event.get("event_type") != filters["event_type"]:
        return False
    if filters.get("visibility") and event.get("visibility") != filters["visibility"]:
        return False
    actor = filters.get("actor")
    if actor and actor not in {
        event.get("actor_user_id"),
        event.get("actor_employee_id"),
        event.get("actor_customer_id"),
        event.get("actor_label"),
    }:
        return False
    occurred = _dt(event.get("occurred_at"))
    if filters.get("date_from") and occurred and occurred < filters["date_from"]:
        return False
    if filters.get("date_to") and occurred and occurred > filters["date_to"]:
        return False
    return True


async def list_timeline(
    *,
    tenant_id: str,
    scope: TimelineScope,
    source_id: str,
    event_category: Optional[str] = None,
    event_type: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    actor: Optional[str] = None,
    visibility: Optional[str] = None,
    sort: str = "desc",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    data = await _scope_data(tenant_id, scope, source_id)
    related = await _collect_related(tenant_id, data)
    events = _project_direct_events(tenant_id, data, related)
    await _project_audit_events(tenant_id, data, related, events)

    filters = {
        "event_category": event_category,
        "event_type": event_type,
        "date_from": date_from,
        "date_to": date_to,
        "actor": actor,
        "visibility": visibility,
    }
    items = [event for event in events.values() if _matches_filters(event, filters)]
    reverse = sort != "asc"
    items.sort(key=lambda e: (_dt(e.get("occurred_at")) or datetime.min.replace(tzinfo=timezone.utc), e.get("id") or ""), reverse=reverse)
    total = len(items)
    page = items[offset:offset + limit]
    next_offset = offset + limit if offset + limit < total else None
    return {"items": page, "total": total, "limit": limit, "offset": offset, "next_offset": next_offset, "sort": sort}
