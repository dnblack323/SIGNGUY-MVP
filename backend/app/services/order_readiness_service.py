"""Shop Operations Order readiness and workspace aggregation.

This layer reads the existing Order, Approval, Decision Room, Proof, Document,
Invoice, Payment, and Work Order authorities. It does not own a second
commercial, approval, finance, or production system.
"""
from __future__ import annotations

from typing import Any, Optional

from ..core.db import db
from ..core.permissions import Perm, permissions_for_role
from ..core.time_utils import serialize_doc, utc_now
from ..services.audit import record_audit
from ..services.commerce_totals import compute_pricing_summary
from ..services.order_pricing import compute_document_totals_with_pricing_adjustments
from ..services import work_order_service


ACTIVE_WORK_ORDER_STATUSES = {"draft", "released", "queued", "in_progress", "blocked", "ready"}
ACTIVE_APPROVAL_STATUSES = {"current", "pending", "pending_review", "sent", "in_review"}
APPROVED_PROOF_STATUSES = {"approved"}
BLOCKING_PROOF_STATUSES = {"draft", "sent", "viewed", "changes_requested"}
INACTIVE_PROOF_STATUSES = {"cancelled", "superseded", "archived"}


def user_permissions(user: dict[str, Any]) -> set[str]:
    if "permissions" in user:
        return {str(p) for p in (user.get("permissions") or [])}
    return set(permissions_for_role(user.get("role", "staff")))


def can_read_financials(user: dict[str, Any]) -> bool:
    perms = user_permissions(user)
    return Perm.INVOICE_READ.value in perms or Perm.PAYMENT_READ.value in perms


async def _order_or_raise(tenant_id: str, order_id: str) -> dict[str, Any]:
    order = await db.orders.find_one({"tenant_id": tenant_id, "id": order_id}, {"_id": 0})
    if not order:
        raise ValueError("order_not_found")
    return order


async def list_order_items(tenant_id: str, order_id: str) -> list[dict[str, Any]]:
    cursor = db.order_items.find(
        {"tenant_id": tenant_id, "order_id": order_id}, {"_id": 0},
    ).sort("position", 1)
    return [serialize_doc(item) async for item in cursor]


async def order_financial_summary(tenant_id: str, order_id: str, *, include_details: bool) -> dict[str, Any]:
    if not include_details:
        return {"available": False, "restricted": True}
    invoices = [
        serialize_doc(invoice) async for invoice in db.invoices.find(
            {"tenant_id": tenant_id, "order_id": order_id}, {"_id": 0},
        ).sort("created_at", -1)
    ]
    invoice_ids = [invoice["id"] for invoice in invoices]
    payments = [
        serialize_doc(payment) async for payment in db.payments.find(
            {"tenant_id": tenant_id, "invoice_id": {"$in": invoice_ids}}, {"_id": 0},
        ).sort("created_at", -1)
    ] if invoice_ids else []
    total_invoiced = sum(int(invoice.get("total_cents") or 0) for invoice in invoices if invoice.get("status") != "void")
    total_paid = sum(int(invoice.get("amount_paid_cents") or invoice.get("paid_cents") or 0) for invoice in invoices if invoice.get("status") != "void")
    total_refunded = sum(int(invoice.get("amount_refunded_cents") or 0) for invoice in invoices if invoice.get("status") != "void")
    balance_due = sum(int(invoice.get("balance_due_cents") or max(int(invoice.get("total_cents") or 0) - int(invoice.get("amount_paid_cents") or 0), 0)) for invoice in invoices if invoice.get("status") != "void")
    return {
        "available": True,
        "restricted": False,
        "invoices": invoices,
        "payments": payments,
        "invoice_count": len(invoices),
        "payment_count": len(payments),
        "total_invoiced_cents": total_invoiced,
        "amount_paid_cents": total_paid,
        "amount_refunded_cents": total_refunded,
        "balance_due_cents": balance_due,
    }


async def _approvals_for_order(tenant_id: str, order_id: str, item_ids: list[str], work_order_ids: list[str]) -> list[dict[str, Any]]:
    filters: list[dict[str, Any]] = [{"snapshot.order_id": order_id}]
    if item_ids:
        filters.append({"parent_type": "order_item", "parent_id": {"$in": item_ids}})
    if work_order_ids:
        filters.append({"parent_type": "work_order_summary", "parent_id": {"$in": work_order_ids}})
    cursor = db.approvals.find({"tenant_id": tenant_id, "$or": filters}, {"_id": 0}).sort("created_at", -1)
    return [serialize_doc(approval) async for approval in cursor]


async def _decision_rooms_for_order(tenant_id: str, order_id: str) -> list[dict[str, Any]]:
    cursor = db.decision_rooms.find(
        {"tenant_id": tenant_id, "order_id": order_id}, {"_id": 0},
    ).sort("updated_at", -1)
    return [serialize_doc(room) async for room in cursor]


async def _proofs_for_order(tenant_id: str, order_id: str, item_ids: list[str]) -> list[dict[str, Any]]:
    filters: list[dict[str, Any]] = [
        {"order_id": order_id},
        {"parent_type": "order", "parent_id": order_id},
    ]
    if item_ids:
        filters.append({"parent_type": "order_item", "parent_id": {"$in": item_ids}})
    cursor = db.proofs.find({"tenant_id": tenant_id, "$or": filters, "archived": {"$ne": True}}, {"_id": 0}).sort("created_at", -1)
    return [serialize_doc(proof) async for proof in cursor]


async def _linked_assets(tenant_id: str, order_id: str, item_ids: list[str]) -> dict[str, Any]:
    attachment_filters: list[dict[str, Any]] = [{"parent_type": "order", "parent_id": order_id}]
    document_filters: list[dict[str, Any]] = [{"entity_type": "order", "entity_id": order_id}]
    if item_ids:
        attachment_filters.append({"parent_type": "order_item", "parent_id": {"$in": item_ids}})
        document_filters.append({"entity_type": "order_item", "entity_id": {"$in": item_ids}})
    attachments = [
        serialize_doc(att) async for att in db.attachments.find(
            {"tenant_id": tenant_id, "$or": attachment_filters}, {"_id": 0},
        )
    ]
    file_ids = [att.get("file_id") for att in attachments if att.get("file_id")]
    files = [
        serialize_doc(file) async for file in db.files.find(
            {"tenant_id": tenant_id, "id": {"$in": file_ids}, "archived": {"$ne": True}}, {"_id": 0},
        )
    ] if file_ids else []
    doc_links = [
        serialize_doc(link) async for link in db.document_links.find(
            {"tenant_id": tenant_id, "$or": document_filters}, {"_id": 0},
        )
    ]
    document_ids = [link.get("document_id") for link in doc_links if link.get("document_id")]
    documents = [
        serialize_doc(doc) async for doc in db.documents.find(
            {"tenant_id": tenant_id, "id": {"$in": document_ids}, "archived": {"$ne": True}}, {"_id": 0},
        )
    ] if document_ids else []
    return {"attachments": attachments, "files": files, "document_links": doc_links, "documents": documents}


async def _work_orders(tenant_id: str, order_id: str) -> list[dict[str, Any]]:
    cursor = db.work_orders.find({"tenant_id": tenant_id, "order_id": order_id}, {"_id": 0}).sort("number", -1)
    return [serialize_doc(work_order) async for work_order in cursor]


def _production_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in items if item.get("production_required", True)]


def _current_approval_approves_current(approvals: list[dict[str, Any]], *, parent_type: str, parent_id: str, parent_version: Optional[int] = None) -> bool:
    for approval in approvals:
        if approval.get("parent_type") != parent_type or approval.get("parent_id") != parent_id:
            continue
        if parent_version is not None and approval.get("parent_version") not in {None, parent_version}:
            continue
        if approval.get("action") == "approve" and approval.get("status", "current") == "current":
            return True
    return False


def _blocker(code: str, label: str, *, source: str, source_id: Optional[str], action: str, owner: str = "staff", severity: str = "blocker") -> dict[str, Any]:
    return {
        "code": code,
        "label": label,
        "source": source,
        "source_id": source_id,
        "required_action": action,
        "owner": owner,
        "severity": severity,
        "resolved": False,
    }


async def evaluate_readiness(
    *,
    tenant_id: str,
    order_id: str,
    user: Optional[dict[str, Any]] = None,
    include_financial_details: bool = False,
) -> dict[str, Any]:
    order = await _order_or_raise(tenant_id, order_id)
    items = await list_order_items(tenant_id, order_id)
    item_ids = [item["id"] for item in items]
    production_items = _production_items(items)
    work_orders = await _work_orders(tenant_id, order_id)
    active_work_order = next((wo for wo in work_orders if wo.get("current_version", True) and wo.get("production_status") in ACTIVE_WORK_ORDER_STATUSES), None)
    approvals = await _approvals_for_order(tenant_id, order_id, item_ids, [wo["id"] for wo in work_orders])
    rooms = await _decision_rooms_for_order(tenant_id, order_id)
    proofs = await _proofs_for_order(tenant_id, order_id, item_ids)
    assets = await _linked_assets(tenant_id, order_id, item_ids)
    financial = await order_financial_summary(tenant_id, order_id, include_details=include_financial_details)
    customer = await db.customers.find_one({"tenant_id": tenant_id, "id": order.get("customer_id")}, {"_id": 0})

    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if not customer:
        blockers.append(_blocker("missing_customer", "Customer record is missing.", source="customer", source_id=order.get("customer_id"), action="Select a valid customer."))
    elif customer.get("archived") or customer.get("lifecycle_status") in {"archived", "merged"} or customer.get("merged_into"):
        blockers.append(_blocker("inactive_customer", "Customer is archived or merged.", source="customer", source_id=customer.get("id"), action="Restore the customer or move the order to the surviving customer."))

    if not items:
        blockers.append(_blocker("missing_items", "Order has no line items.", source="order", source_id=order_id, action="Add at least one valid Order Item."))
    elif not production_items:
        blockers.append(_blocker("no_production_items", "Order has no production-required items.", source="order_item", source_id=None, action="Mark at least one fulfillment item as production-required before handoff."))
    if production_items and not any(item.get("description") and int(item.get("quantity") or 0) > 0 for item in production_items):
        blockers.append(_blocker("invalid_production_items", "Production-required items are incomplete.", source="order_item", source_id=None, action="Review production-required Order Items."))
    for item in items:
        if int(item.get("quantity") or 0) < 1 or int(item.get("unit_price_cents") or 0) < 0 or int(item.get("line_total_cents") or 0) < 0:
            blockers.append(_blocker("invalid_pricing", f"{item.get('description') or 'Order item'} has invalid pricing.", source="order_item", source_id=item.get("id"), action="Correct item pricing."))
        if item.get("selected_price_source") == "manual" and int(item.get("manual_price_cents") or 0) > 0 and not item.get("manual_override_reason"):
            warnings.append(_blocker("manual_price_review", f"{item.get('description') or 'Order item'} uses manual pricing without a visible reason.", source="order_item", source_id=item.get("id"), action="Record or review the manual price reason.", severity="warning"))
        if item.get("calculation_warnings"):
            warnings.append(_blocker("pricing_warning", f"{item.get('description') or 'Order item'} has pricing warnings.", source="order_item", source_id=item.get("id"), action="Review pricing warnings.", severity="warning"))

    requires_proof = any(item.get("design_required") or item.get("customer_supplied_artwork") or item.get("proof_status") for item in production_items)
    if requires_proof:
        active_proofs = [proof for proof in proofs if proof.get("status") not in INACTIVE_PROOF_STATUSES]
        if not active_proofs:
            blockers.append(_blocker("missing_proof", "Proof approval is required but no active proof exists.", source="proof", source_id=None, action="Create and send a proof for approval."))
        elif not any(proof.get("status") in APPROVED_PROOF_STATUSES for proof in active_proofs):
            blockers.append(_blocker("proof_not_approved", "Proof approval is still pending.", source="proof", source_id=active_proofs[0].get("id"), action="Obtain customer proof approval."))
    elif any(proof.get("status") in BLOCKING_PROOF_STATUSES for proof in proofs):
        blocking_proof = next((proof for proof in proofs if proof.get("status") in BLOCKING_PROOF_STATUSES), None)
        blockers.append(_blocker("active_proof_pending", "An active proof is still awaiting approval or changes.", source="proof", source_id=blocking_proof.get("id") if blocking_proof else None, action="Resolve the active proof before production."))

    active_room = next((room for room in rooms if room.get("status") not in {"archived", "closed", "expired"}), None)
    current_approval_blockers = [
        approval for approval in approvals
        if approval.get("status", "current") in ACTIVE_APPROVAL_STATUSES and approval.get("action") in {"request_changes", "decline"}
    ]
    if current_approval_blockers:
        approval = current_approval_blockers[0]
        blockers.append(_blocker("approval_change_requested", "Customer approval has requested changes or declined.", source="approval", source_id=approval.get("id"), action="Resolve customer decision before production.", owner="customer"))
    if active_room and not any(approval.get("action") == "approve" and approval.get("status", "current") == "current" for approval in approvals):
        blockers.append(_blocker("decision_room_pending", "Decision Room work is active and has no current approval.", source="decision_room", source_id=active_room.get("id"), action="Apply or close the customer decision.", owner="customer"))

    required_deposit_cents = int(order.get("deposit_required_cents") or order.get("required_deposit_cents") or 0)
    if not required_deposit_cents and order.get("deposit_required_percent"):
        required_deposit_cents = round(int(order.get("total_cents") or 0) * float(order.get("deposit_required_percent")) / 100)
    if order.get("payment_required_before_production") or required_deposit_cents > 0:
        amount_paid = int(financial.get("amount_paid_cents") or order.get("amount_paid_cents") or 0)
        required = required_deposit_cents or int(order.get("total_cents") or 0)
        if amount_paid < required:
            blockers.append(_blocker("deposit_required", "Required deposit or payment has not been received.", source="invoice", source_id=None, action="Create/open the invoice and record payment."))

    if order.get("status") in {"cancelled", "archived"}:
        blockers.append(_blocker("order_inactive", "Order is cancelled or archived.", source="order", source_id=order_id, action="Restore or recreate the order before production."))

    ready = len(blockers) == 0 and bool(production_items)
    return {
        "ready": ready,
        "status": "ready" if ready else "not_ready",
        "blockers": blockers,
        "warnings": warnings,
        "summary": {
            "item_count": len(items),
            "production_required_count": len(production_items),
            "approval_count": len(approvals),
            "decision_room_count": len(rooms),
            "proof_count": len(proofs),
            "file_count": len(assets["files"]),
            "document_count": len(assets["documents"]),
            "active_work_order_id": active_work_order.get("id") if active_work_order else None,
        },
        "evaluated_at": utc_now().isoformat(),
    }


async def workspace_payload(*, tenant_id: str, order_id: str, user: dict[str, Any]) -> dict[str, Any]:
    order = await _order_or_raise(tenant_id, order_id)
    items = await list_order_items(tenant_id, order_id)
    item_ids = [item["id"] for item in items]
    work_orders = await _work_orders(tenant_id, order_id)
    approvals = await _approvals_for_order(tenant_id, order_id, item_ids, [wo["id"] for wo in work_orders])
    rooms = await _decision_rooms_for_order(tenant_id, order_id)
    proofs = await _proofs_for_order(tenant_id, order_id, item_ids)
    assets = await _linked_assets(tenant_id, order_id, item_ids)
    include_financials = can_read_financials(user)
    financial = await order_financial_summary(tenant_id, order_id, include_details=include_financials)
    readiness = await evaluate_readiness(
        tenant_id=tenant_id,
        order_id=order_id,
        user=user,
        include_financial_details=include_financials,
    )
    customer = await db.customers.find_one({"tenant_id": tenant_id, "id": order.get("customer_id")}, {"_id": 0})
    quote_id = order.get("source_quote_id") or order.get("quote_id")
    quote = await db.quotes.find_one({"tenant_id": tenant_id, "id": quote_id}, {"_id": 0}) if quote_id else None
    totals = compute_document_totals_with_pricing_adjustments(items)
    return {
        "order": serialize_doc(order),
        "items": items,
        "totals": totals,
        "pricing_summary": compute_pricing_summary(items),
        "customer_summary": serialize_doc(customer) if customer else None,
        "source_quote_summary": serialize_doc(quote) if quote else None,
        "work_orders": work_orders,
        "approvals": approvals,
        "decision_rooms": rooms,
        "proofs": proofs,
        "linked_assets": assets,
        "financial_summary": financial,
        "readiness": readiness,
        "permissions": {"financials_visible": include_financials},
    }


async def order_item_mutation_blocker(tenant_id: str, order_id: str) -> Optional[str]:
    invoice = await db.invoices.find_one(
        {"tenant_id": tenant_id, "order_id": order_id, "status": {"$ne": "void"}},
        {"_id": 0, "id": 1, "number": 1},
    )
    if invoice:
        return f"Order Items are locked because invoice I-{invoice.get('number')} exists. Void or revise through Finance before changing items."
    work_order = await db.work_orders.find_one(
        {"tenant_id": tenant_id, "order_id": order_id, "current_version": True, "production_status": {"$nin": ["cancelled", "superseded"]}},
        {"_id": 0, "id": 1, "number": 1},
    )
    if work_order:
        return f"Order Items are locked because Work Order W-{work_order.get('number')} exists. Regenerate or supersede production work instead of changing source items."
    return None


async def production_handoff(
    *,
    tenant_id: str,
    order_id: str,
    payload: dict[str, Any],
    user: dict[str, Any],
) -> dict[str, Any]:
    readiness = await evaluate_readiness(
        tenant_id=tenant_id,
        order_id=order_id,
        user=user,
        include_financial_details=can_read_financials(user),
    )
    override_reason = (payload.get("override_reason") or "").strip()
    if not readiness["ready"] and not override_reason:
        raise ValueError("readiness_override_reason_required")
    if not readiness["ready"]:
        await record_audit(
            tenant_id=tenant_id,
            actor_user_id=user["id"],
            actor_email=user["email"],
            action="order.readiness_override",
            entity_type="order",
            entity_id=order_id,
            summary="Production handoff override applied",
            diff={"reason": override_reason, "blockers": readiness.get("blockers", [])},
        )
    work_order, already = await work_order_service.generate(
        tenant_id=tenant_id,
        order_id=order_id,
        actor_user_id=user["id"],
        actor_email=user["email"],
        priority=payload.get("priority") or "normal",
        due_date=payload.get("due_date"),
        production_instructions=payload.get("production_instructions"),
        internal_notes=payload.get("internal_notes"),
        assigned_user_ids=payload.get("assigned_user_ids") or [],
    )
    await record_audit(
        tenant_id=tenant_id,
        actor_user_id=user["id"],
        actor_email=user["email"],
        action="order.production_handoff",
        entity_type="order",
        entity_id=order_id,
        summary=f"Order handed off to Work Order W-{work_order.get('number')}",
        diff={"work_order_id": work_order.get("id"), "already_exists": already, "readiness_ready": readiness["ready"]},
    )
    return {"work_order": work_order, "already_exists": already, "readiness": readiness, "override_applied": not readiness["ready"]}
