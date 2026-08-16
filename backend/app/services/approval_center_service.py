"""Shop Operations Approval Center authority layer.

This service aggregates existing approval-capable records and creates
Decision Room work through the canonical Decision Room service. It does not
own a second approval workflow.
"""
from __future__ import annotations

import re
from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import serialize_doc
from ..services import decision_room_service
from ..services.decision_room_service import DecisionRoomError


ACTIVE_SIGNATURE_STATUSES = {"draft", "sent", "partially_signed"}
ACTIVE_PROOF_STATUSES = {"draft", "in_review", "sent", "changes_requested"}


def _regex(term: str) -> dict[str, str]:
    return {"$regex": re.escape(term.strip()), "$options": "i"}


def _text(*values: Any) -> str:
    return " ".join(str(v) for v in values if v is not None and str(v).strip()).strip()


def _dt(value: Any) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value or "")


def _source_url(item: dict[str, Any]) -> str:
    if item.get("parent_type") == "work_order_summary":
        return f"/work-orders/{item.get('parent_id')}"
    if item.get("quote_id"):
        return f"/quotes/{item['quote_id']}"
    if item.get("order_id"):
        return f"/orders/{item['order_id']}"
    if item.get("parent_type") == "quote":
        return f"/quotes/{item.get('parent_id')}"
    if item.get("parent_type") == "quote_revision":
        return f"/quotes/{item.get('parent_id')}"
    if item.get("parent_type") == "order_item" and item.get("order_id"):
        return f"/orders/{item['order_id']}"
    return "/approval-center"


def _approval_parent_label(parent_type: Optional[str]) -> str:
    labels = {
        "quote_revision": "Quote approval",
        "proof_version": "Proof approval",
        "contract": "Contract approval",
        "order_item": "Order item approval",
        "work_order_summary": "Work Order Summary approval",
        "signature_request": "Signature request",
    }
    return labels.get(parent_type or "", parent_type or "Approval")


async def _customer_names(tenant_id: str, customer_ids: set[str]) -> dict[str, str]:
    if not customer_ids:
        return {}
    cursor = db.customers.find(
        {"tenant_id": tenant_id, "id": {"$in": list(customer_ids)}},
        {"_id": 0, "id": 1, "name": 1, "company": 1},
    )
    return {c["id"]: c.get("name") or c.get("company") or c["id"] async for c in cursor}


async def _normalize_approvals(tenant_id: str, unresolved_only: bool) -> list[dict[str, Any]]:
    q: dict[str, Any] = {"tenant_id": tenant_id}
    if unresolved_only:
        q["status"] = "current"
    approvals = [a async for a in db.approvals.find(q, {"_id": 0}).sort("created_at", -1).limit(100)]
    customer_ids = {((a.get("snapshot") or {}).get("customer_id")) for a in approvals if (a.get("snapshot") or {}).get("customer_id")}
    customer_names = await _customer_names(tenant_id, set(customer_ids))
    items: list[dict[str, Any]] = []
    for approval in approvals:
        snapshot = approval.get("snapshot") or {}
        customer_id = snapshot.get("customer_id")
        parent_type = approval.get("parent_type")
        title = snapshot.get("title") or snapshot.get("job_name") or parent_type
        order_id = snapshot.get("order_id")
        work_order = None
        if parent_type == "order_item" and not order_id:
            order_item = await db.order_items.find_one(
                {"tenant_id": tenant_id, "id": approval.get("parent_id")},
                {"_id": 0, "order_id": 1, "description": 1},
            )
            order_id = order_item.get("order_id") if order_item else None
            if order_item and not title:
                title = order_item.get("description")
        if parent_type == "work_order_summary":
            work_order = await db.work_orders.find_one(
                {"tenant_id": tenant_id, "id": approval.get("parent_id")},
                {"_id": 0, "id": 1, "number": 1, "order_id": 1, "customer_id": 1, "title": 1, "job_name": 1},
            )
            if work_order:
                order_id = order_id or work_order.get("order_id")
                customer_id = customer_id or work_order.get("customer_id")
                title = title or work_order.get("title") or work_order.get("job_name") or f"W-{work_order.get('number')}"
        item = {
            "id": f"approval:{approval.get('id')}",
            "queue_type": "approval_record",
            "record_type": "approval",
            "record_id": approval.get("id"),
            "activity_type": approval.get("action"),
            "status": approval.get("status") or "current",
            "title": title,
            "target_type": parent_type,
            "target_id": approval.get("parent_id"),
            "customer_id": customer_id,
            "customer_name": customer_names.get(customer_id) or snapshot.get("customer_name"),
            "quote_id": snapshot.get("quote_id") or (approval.get("parent_id") if parent_type == "quote_revision" else None),
            "order_id": order_id,
            "work_order_id": approval.get("parent_id") if parent_type == "work_order_summary" else None,
            "order_item_id": snapshot.get("order_item_id") or (approval.get("parent_id") if parent_type == "order_item" else None),
            "submitted_at": _dt(approval.get("created_at")),
            "reason": approval.get("reason"),
            "source_url": _source_url({**approval, **snapshot, "order_id": order_id}),
            "source_summary": _text(
                _approval_parent_label(parent_type),
                f"Q-{snapshot.get('quote_number')}" if snapshot.get("quote_number") else None,
                f"O-{snapshot.get('order_number')}" if snapshot.get("order_number") else None,
                f"W-{work_order.get('number')}" if work_order and work_order.get("number") else None,
                snapshot.get("job_name"),
            ),
            "unresolved": (approval.get("status") or "current") == "current",
        }
        if customer_id and not item["customer_name"]:
            customer = await db.customers.find_one(
                {"tenant_id": tenant_id, "id": customer_id},
                {"_id": 0, "id": 1, "name": 1, "company": 1},
            )
            item["customer_name"] = (customer or {}).get("name") or (customer or {}).get("company")
        items.append(item)
    return items


async def _normalize_signatures(tenant_id: str, unresolved_only: bool) -> list[dict[str, Any]]:
    q: dict[str, Any] = {"tenant_id": tenant_id}
    if unresolved_only:
        q["status"] = {"$in": list(ACTIVE_SIGNATURE_STATUSES)}
    requests = [r async for r in db.signature_requests.find(q, {"_id": 0}).sort("created_at", -1).limit(100)]
    return [
        {
            "id": f"signature_request:{req.get('id')}",
            "queue_type": "signature_request",
            "record_type": "signature_request",
            "record_id": req.get("id"),
            "activity_type": "signature",
            "status": req.get("status"),
            "title": req.get("title"),
            "target_type": req.get("parent_type"),
            "target_id": req.get("parent_id"),
            "submitted_at": _dt(req.get("created_at")),
            "source_url": _source_url({"parent_type": req.get("parent_type"), "parent_id": req.get("parent_id")}),
            "source_summary": _text("Signature request", _approval_parent_label(req.get("parent_type")), req.get("parent_id")),
            "unresolved": req.get("status") in ACTIVE_SIGNATURE_STATUSES,
        }
        for req in requests
    ]


async def _normalize_proofs(tenant_id: str, unresolved_only: bool) -> list[dict[str, Any]]:
    q: dict[str, Any] = {"tenant_id": tenant_id, "archived": {"$ne": True}}
    if unresolved_only:
        q["status"] = {"$in": list(ACTIVE_PROOF_STATUSES)}
    proofs = [p async for p in db.proofs.find(q, {"_id": 0}).sort("created_at", -1).limit(100)]
    return [
        {
            "id": f"proof:{proof.get('id')}",
            "queue_type": "proof",
            "record_type": "proof",
            "record_id": proof.get("id"),
            "activity_type": "proof",
            "status": proof.get("status"),
            "title": proof.get("title") or proof.get("name") or "Proof review",
            "target_type": "proof_version",
            "target_id": proof.get("id"),
            "customer_id": proof.get("customer_id"),
            "quote_id": proof.get("quote_id"),
            "order_id": proof.get("order_id"),
            "submitted_at": _dt(proof.get("created_at")),
            "source_url": _source_url(proof),
            "source_summary": _text("Proof", proof.get("parent_type"), proof.get("parent_id")),
            "unresolved": proof.get("status") in ACTIVE_PROOF_STATUSES,
        }
        for proof in proofs
    ]


def _normalize_decision_room_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"decision_room_activity:{item.get('record_type')}:{item.get('record_id')}",
        "queue_type": "decision_room_activity",
        "record_type": item.get("record_type"),
        "record_id": item.get("record_id"),
        "activity_type": item.get("activity_type"),
        "status": item.get("status"),
        "title": item.get("decision_room_title") or "Decision Room activity",
        "target_type": "decision_room",
        "target_id": item.get("decision_room_id"),
        "decision_room_id": item.get("decision_room_id"),
        "customer_id": item.get("customer_id"),
        "customer_name": item.get("customer_name"),
        "submitted_at": item.get("submitted_at"),
        "assigned_user_id": item.get("assigned_user_id"),
        "customer_message": item.get("customer_message"),
        "option_label": item.get("option_label"),
        "source_url": f"/decision-rooms/{item.get('decision_room_id')}",
        "source_summary": _text(
            "Decision Room",
            item.get("activity_type"),
            item.get("option_label"),
            item.get("customer_message"),
        ),
        "unresolved": item.get("unresolved"),
    }


def _matches(item: dict[str, Any], search: Optional[str], kind: Optional[str], status: Optional[str]) -> bool:
    if kind and item.get("queue_type") != kind and item.get("record_type") != kind and item.get("activity_type") != kind:
        return False
    if status and item.get("status") != status:
        return False
    if not search:
        return True
    needle = search.strip().lower()
    haystack = _text(
        item.get("title"),
        item.get("customer_name"),
        item.get("option_label"),
        item.get("customer_message"),
        item.get("target_id"),
        item.get("record_id"),
    ).lower()
    return needle in haystack


async def list_authority_queue(
    *,
    tenant_id: str,
    search: Optional[str] = None,
    status: Optional[str] = None,
    kind: Optional[str] = None,
    unresolved_only: bool = True,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    decision_room_queue = await decision_room_service.list_review_queue(
        tenant_id=tenant_id,
        unresolved_only=unresolved_only,
        search=search,
        limit=100,
        offset=0,
    )
    items = [_normalize_decision_room_item(item) for item in decision_room_queue.get("items", [])]
    items += await _normalize_approvals(tenant_id, unresolved_only)
    items += await _normalize_signatures(tenant_id, unresolved_only)
    items += await _normalize_proofs(tenant_id, unresolved_only)
    items = [item for item in items if _matches(item, search, kind, status)]
    items.sort(key=lambda item: item.get("submitted_at") or "", reverse=True)
    total = len(items)
    return {"items": items[offset: offset + limit], "total": total, "limit": limit, "offset": offset}


async def search_targets(*, tenant_id: str, target_type: str, search: Optional[str], limit: int = 20) -> dict[str, Any]:
    term = (search or "").strip()
    if target_type == "customer":
        q: dict[str, Any] = {"tenant_id": tenant_id}
        if term:
            rx = _regex(term)
            q["$or"] = [{"name": rx}, {"company": rx}, {"email": rx}, {"phone": rx}]
        cursor = db.customers.find(q, {"_id": 0}).sort("name", 1).limit(limit)
        return {"items": [
            {"id": c["id"], "target_type": "customer", "label": c.get("name") or c.get("company") or c["id"], "subtitle": c.get("email"), "customer_id": c["id"]}
            async for c in cursor
        ]}
    if target_type == "quote":
        q = {"tenant_id": tenant_id}
        if term:
            rx = _regex(term)
            clauses: list[dict[str, Any]] = [{"job_name": rx}, {"id": rx}]
            if term.isdigit():
                clauses.append({"number": int(term)})
            q["$or"] = clauses
        quotes = [quote async for quote in db.quotes.find(q, {"_id": 0}).sort("number", -1).limit(limit)]
        customers = await _customer_names(tenant_id, {q["customer_id"] for q in quotes if q.get("customer_id")})
        return {"items": [
            {
                "id": quote["id"],
                "target_type": "quote",
                "label": f"Q-{quote.get('number')} {quote.get('job_name')}",
                "subtitle": customers.get(quote.get("customer_id")),
                "customer_id": quote.get("customer_id"),
            }
            for quote in quotes
        ]}
    if target_type == "order":
        q = {"tenant_id": tenant_id}
        if term:
            rx = _regex(term)
            clauses = [{"job_name": rx}, {"id": rx}]
            if term.isdigit():
                clauses.append({"number": int(term)})
            q["$or"] = clauses
        orders = [order async for order in db.orders.find(q, {"_id": 0}).sort("number", -1).limit(limit)]
        customers = await _customer_names(tenant_id, {o["customer_id"] for o in orders if o.get("customer_id")})
        return {"items": [
            {
                "id": order["id"],
                "target_type": "order",
                "label": f"O-{order.get('number')} {order.get('job_name')}",
                "subtitle": customers.get(order.get("customer_id")),
                "customer_id": order.get("customer_id"),
            }
            for order in orders
        ]}
    if target_type == "order_item":
        q = {"tenant_id": tenant_id}
        if term:
            rx = _regex(term)
            q["$or"] = [{"description": rx}, {"category": rx}, {"id": rx}, {"order_id": rx}]
        order_items = [item async for item in db.order_items.find(q, {"_id": 0}).sort("created_at", -1).limit(limit)]
        order_ids = {item["order_id"] for item in order_items if item.get("order_id")}
        orders = {
            o["id"]: o async for o in db.orders.find(
                {"tenant_id": tenant_id, "id": {"$in": list(order_ids)}},
                {"_id": 0, "id": 1, "number": 1, "job_name": 1, "customer_id": 1},
            )
        } if order_ids else {}
        customers = await _customer_names(tenant_id, {o["customer_id"] for o in orders.values() if o.get("customer_id")})
        return {"items": [
            {
                "id": item["id"],
                "target_type": "order_item",
                "label": item.get("description") or item["id"],
                "subtitle": _text(
                    f"O-{orders.get(item.get('order_id'), {}).get('number')}" if orders.get(item.get("order_id")) else None,
                    orders.get(item.get("order_id"), {}).get("job_name"),
                ),
                "customer_id": orders.get(item.get("order_id"), {}).get("customer_id"),
                "customer_name": customers.get(orders.get(item.get("order_id"), {}).get("customer_id")),
                "order_id": item.get("order_id"),
            }
            for item in order_items
        ]}
    if target_type == "quote_line_item":
        q = {"tenant_id": tenant_id}
        if term:
            rx = _regex(term)
            q["$or"] = [{"description": rx}, {"category": rx}, {"id": rx}, {"quote_id": rx}]
        line_items = [item async for item in db.quote_line_items.find(q, {"_id": 0}).sort("created_at", -1).limit(limit)]
        quote_ids = {item["quote_id"] for item in line_items if item.get("quote_id")}
        quotes = {
            quote["id"]: quote async for quote in db.quotes.find(
                {"tenant_id": tenant_id, "id": {"$in": list(quote_ids)}},
                {"_id": 0, "id": 1, "number": 1, "job_name": 1, "customer_id": 1},
            )
        } if quote_ids else {}
        customers = await _customer_names(tenant_id, {quote["customer_id"] for quote in quotes.values() if quote.get("customer_id")})
        return {"items": [
            {
                "id": item["id"],
                "target_type": "quote_line_item",
                "label": item.get("description") or item["id"],
                "subtitle": _text(
                    f"Q-{quotes.get(item.get('quote_id'), {}).get('number')}" if quotes.get(item.get("quote_id")) else None,
                    quotes.get(item.get("quote_id"), {}).get("job_name"),
                    customers.get(quotes.get(item.get("quote_id"), {}).get("customer_id")),
                ),
                "customer_id": quotes.get(item.get("quote_id"), {}).get("customer_id"),
                "customer_name": customers.get(quotes.get(item.get("quote_id"), {}).get("customer_id")),
                "quote_id": item.get("quote_id"),
            }
            for item in line_items
        ]}
    raise ValueError("unsupported_target_type")


async def _resolve_target(tenant_id: str, target_type: str, target_id: str) -> dict[str, Any]:
    if target_type == "customer":
        doc = await db.customers.find_one({"tenant_id": tenant_id, "id": target_id}, {"_id": 0})
        if not doc:
            raise DecisionRoomError("customer_not_found")
        return {"customer_id": doc["id"], "label": doc.get("name") or doc.get("company") or doc["id"]}
    if target_type == "quote":
        quote = await db.quotes.find_one({"tenant_id": tenant_id, "id": target_id}, {"_id": 0})
        if not quote:
            raise DecisionRoomError("quote_not_found")
        return {
            "customer_id": quote.get("customer_id"),
            "quote_id": quote["id"],
            "label": f"Q-{quote.get('number')} {quote.get('job_name')}",
        }
    if target_type == "order":
        order = await db.orders.find_one({"tenant_id": tenant_id, "id": target_id}, {"_id": 0})
        if not order:
            raise DecisionRoomError("order_not_found")
        return {
            "customer_id": order.get("customer_id"),
            "order_id": order["id"],
            "label": f"O-{order.get('number')} {order.get('job_name')}",
        }
    if target_type == "order_item":
        item = await db.order_items.find_one({"tenant_id": tenant_id, "id": target_id}, {"_id": 0})
        if not item:
            raise DecisionRoomError("order_item_not_found")
        order = await db.orders.find_one({"tenant_id": tenant_id, "id": item.get("order_id")}, {"_id": 0})
        if not order:
            raise DecisionRoomError("order_not_found")
        return {
            "customer_id": order.get("customer_id"),
            "order_id": order["id"],
            "order_item_id": item["id"],
            "label": item.get("description") or item["id"],
        }
    if target_type == "quote_line_item":
        item = await db.quote_line_items.find_one({"tenant_id": tenant_id, "id": target_id}, {"_id": 0})
        if not item:
            raise DecisionRoomError("quote_line_item_not_found")
        quote = await db.quotes.find_one({"tenant_id": tenant_id, "id": item.get("quote_id")}, {"_id": 0})
        if not quote:
            raise DecisionRoomError("quote_not_found")
        return {
            "customer_id": quote.get("customer_id"),
            "quote_id": quote["id"],
            "quote_line_item_id": item["id"],
            "label": item.get("description") or item["id"],
        }
    raise ValueError("unsupported_target_type")


async def create_approval_work(
    *,
    tenant_id: str,
    target_type: str,
    target_id: str,
    title: Optional[str],
    customer_safe_intro: Optional[str],
    allow_customer_comments: bool,
    allow_customer_questions: bool,
    allow_change_requests: bool,
    allow_reject_all: bool,
    actor_user_id: str,
    actor_email: str,
) -> dict[str, Any]:
    target = await _resolve_target(tenant_id, target_type, target_id)
    payload = {
        "title": title or target["label"],
        "customer_safe_intro": customer_safe_intro,
        "customer_id": target.get("customer_id"),
        "quote_id": target.get("quote_id"),
        "order_id": target.get("order_id"),
        "order_item_id": target.get("order_item_id"),
        "allow_customer_comments": allow_customer_comments,
        "allow_customer_questions": allow_customer_questions,
        "allow_change_requests": allow_change_requests,
        "allow_reject_all": allow_reject_all,
        "metadata": {
            "created_from": "approval_center",
            "target_type": target_type,
            "target_id": target_id,
            "quote_line_item_id": target.get("quote_line_item_id"),
        },
    }
    room = await decision_room_service.create_room(
        tenant_id=tenant_id,
        payload=payload,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
    )
    return serialize_doc(room)


async def list_approval_history(*, tenant_id: str, source_type: str, source_id: str) -> dict[str, Any]:
    filters: list[dict[str, Any]] = []
    if source_type == "quote":
        quote = await db.quotes.find_one({"tenant_id": tenant_id, "id": source_id}, {"_id": 0, "id": 1})
        if not quote:
            raise DecisionRoomError("quote_not_found")
        quote_line_ids = [
            item["id"] async for item in db.quote_line_items.find(
                {"tenant_id": tenant_id, "quote_id": source_id}, {"_id": 0, "id": 1},
            )
        ]
        filters.append({"parent_type": "quote_revision", "parent_id": source_id})
        if quote_line_ids:
            filters.append({"parent_type": "quote_line_item", "parent_id": {"$in": quote_line_ids}})
    elif source_type == "order":
        order = await db.orders.find_one({"tenant_id": tenant_id, "id": source_id}, {"_id": 0, "id": 1})
        if not order:
            raise DecisionRoomError("order_not_found")
        order_item_ids = [
            item["id"] async for item in db.order_items.find(
                {"tenant_id": tenant_id, "order_id": source_id}, {"_id": 0, "id": 1},
            )
        ]
        work_order_ids = [
            work_order["id"] async for work_order in db.work_orders.find(
                {"tenant_id": tenant_id, "order_id": source_id}, {"_id": 0, "id": 1},
            )
        ]
        filters.append({"snapshot.order_id": source_id})
        if order_item_ids:
            filters.append({"parent_type": "order_item", "parent_id": {"$in": order_item_ids}})
        if work_order_ids:
            filters.append({"parent_type": "work_order_summary", "parent_id": {"$in": work_order_ids}})
    elif source_type == "order_item":
        item = await db.order_items.find_one({"tenant_id": tenant_id, "id": source_id}, {"_id": 0, "id": 1})
        if not item:
            raise DecisionRoomError("order_item_not_found")
        filters.append({"parent_type": "order_item", "parent_id": source_id})
    elif source_type == "work_order_summary":
        work_order = await db.work_orders.find_one({"tenant_id": tenant_id, "id": source_id}, {"_id": 0, "id": 1})
        if not work_order:
            raise DecisionRoomError("work_order_not_found")
        filters.append({"parent_type": "work_order_summary", "parent_id": source_id})
    elif source_type in {"proof_version", "contract"}:
        filters.append({"parent_type": source_type, "parent_id": source_id})
    else:
        raise ValueError("unsupported_source_type")

    query: dict[str, Any] = {"tenant_id": tenant_id}
    if len(filters) == 1:
        query.update(filters[0])
    else:
        query["$or"] = filters
    cursor = db.approvals.find(query, {"_id": 0}).sort("created_at", -1).limit(50)
    items = []
    async for approval in cursor:
        snapshot = approval.get("snapshot") or {}
        items.append({
            **serialize_doc(approval),
            "label": _approval_parent_label(approval.get("parent_type")),
            "source_url": _source_url({**approval, **snapshot}),
            "source_summary": _text(_approval_parent_label(approval.get("parent_type")), snapshot.get("job_name"), approval.get("reason")),
        })
    return {"items": items}
