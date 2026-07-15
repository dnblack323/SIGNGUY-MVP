"""EC10 Phase 10A — Intake service.

Canonical, backend-authoritative lifecycle for `IntakeSubmission` records.
Every write here reuses the existing audit/activity/sequence services — no
parallel audit system. Cross-tenant references (customer/quote/order/file/
questionnaire) are always validated before being stored.

Conversion into a live Quote/Order is explicitly OUT of scope for Phase 10A
(deferred to Phase 10F). The two `preview_*` functions below are pure,
non-persisting contract-validation helpers only — they compute what a later
conversion WOULD write, without writing anything, so the shape of the
contract can be tested now.
"""
from __future__ import annotations

from typing import Any, Optional

from pymongo.errors import DuplicateKeyError

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.intake_submission import IntakeItem, IntakeSubmission
from ..services.audit import record_audit
from ..services.sequence import next_number

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"submitted", "cancelled"},
    "submitted": {"under_review", "needs_information", "cancelled"},
    "under_review": {"needs_information", "accepted", "rejected", "cancelled"},
    "needs_information": {"submitted", "cancelled"},
    "accepted": {"converted_to_quote", "converted_to_order", "cancelled"},
    "converted_to_quote": set(),
    "converted_to_order": set(),
    "rejected": set(),
    "cancelled": set(),
}

# Fields that must never be included in a customer-safe / portal-safe view.
# Not wired to any customer-facing route yet (none exists in Phase 10A) —
# provided now so later phases (10E) have one shared place to enforce this.
_INTERNAL_ONLY_FIELDS = (
    "internal_notes", "assigned_user_id", "assigned_team_id",
    "created_by_user_id", "updated_by_user_id", "submitted_by_user_id",
)


class IntakeError(ValueError):
    """Raised for any intake-service validation failure. `code` maps to an HTTP status in the router."""

    def __init__(self, code: str, message: Optional[str] = None, details: Optional[list[str]] = None):
        super().__init__(message or code)
        self.code = code
        self.details = details or []


async def _validate_customer(tenant_id: str, customer_id: Optional[str]) -> None:
    if not customer_id:
        return
    doc = await db.customers.find_one({"id": customer_id, "tenant_id": tenant_id}, {"_id": 0, "id": 1})
    if not doc:
        raise IntakeError("customer_not_found", "Customer not found for this tenant")


async def _validate_quote(tenant_id: str, quote_id: Optional[str]) -> None:
    if not quote_id:
        return
    doc = await db.quotes.find_one({"id": quote_id, "tenant_id": tenant_id}, {"_id": 0, "id": 1})
    if not doc:
        raise IntakeError("quote_not_found", "Quote not found for this tenant")


async def _validate_order(tenant_id: str, order_id: Optional[str]) -> None:
    if not order_id:
        return
    doc = await db.orders.find_one({"id": order_id, "tenant_id": tenant_id}, {"_id": 0, "id": 1})
    if not doc:
        raise IntakeError("order_not_found", "Order not found for this tenant")


async def _validate_user(tenant_id: str, user_id: Optional[str]) -> None:
    if not user_id:
        return
    doc = await db.users.find_one({"id": user_id, "tenant_id": tenant_id}, {"_id": 0, "id": 1})
    if not doc:
        raise IntakeError("assigned_user_not_found", "Assigned user not found for this tenant")


async def _validate_file_ids(tenant_id: str, file_ids: list[str]) -> None:
    if not file_ids:
        return
    found = {
        d["id"]
        async for d in db.files.find(
            {"id": {"$in": file_ids}, "tenant_id": tenant_id, "archived": {"$ne": True}}, {"_id": 0, "id": 1}
        )
    }
    missing = [f for f in file_ids if f not in found]
    if missing:
        raise IntakeError("file_not_found", f"File(s) not found for this tenant: {missing}")


async def _validate_questionnaire_ids(tenant_id: str, ids: list[str]) -> None:
    if not ids:
        return
    found = {
        d["id"]
        async for d in db.customer_intakes.find({"id": {"$in": ids}, "tenant_id": tenant_id}, {"_id": 0, "id": 1})
    }
    missing = [i for i in ids if i not in found]
    if missing:
        raise IntakeError("questionnaire_submission_not_found", f"Questionnaire submission(s) not found: {missing}")


async def _validate_pricing_snapshot(tenant_id: str, snapshot_id: Optional[str]) -> None:
    if not snapshot_id:
        return
    doc = await db.pricing_snapshot_records.find_one({"id": snapshot_id, "tenant_id": tenant_id}, {"_id": 0, "id": 1})
    if not doc:
        raise IntakeError("pricing_snapshot_not_found", "Pricing snapshot not found for this tenant")


async def _validate_references(tenant_id: str, *, customer_id, quote_id, order_id, assigned_user_id,
                                file_ids, questionnaire_submission_ids) -> None:
    await _validate_customer(tenant_id, customer_id)
    await _validate_quote(tenant_id, quote_id)
    await _validate_order(tenant_id, order_id)
    await _validate_user(tenant_id, assigned_user_id)
    await _validate_file_ids(tenant_id, file_ids or [])
    await _validate_questionnaire_ids(tenant_id, questionnaire_submission_ids or [])


def missing_information_for_submission(doc: dict[str, Any]) -> list[str]:
    """Pure, structural (no DB calls) completeness check — every cross-tenant
    reference on `doc` was already validated at write-time, so this never
    needs to re-check the database. Used both for the compact
    missing-information summary (§12) and as the Phase 10B submit-validation
    gate (a `submitted` transition is refused while this returns any codes)."""
    codes: list[str] = []
    if not (doc.get("project_name") or doc.get("project_description")):
        codes.append("project_name_or_description_required")
    if not (doc.get("customer_id") or doc.get("contact_name")):
        codes.append("customer_or_contact_required")
    items = doc.get("items") or []
    if not items:
        codes.append("at_least_one_item_required")
    for item in items:
        iid = item.get("id", "?")
        if not (item.get("item_name") or item.get("description")):
            codes.append(f"item:{iid}:name_or_description_required")
        if not item.get("category"):
            codes.append(f"item:{iid}:category_required")
        qty = item.get("quantity")
        if not isinstance(qty, int) or qty < 1:
            codes.append(f"item:{iid}:valid_quantity_required")
    if doc.get("installation_required") and not (doc.get("installation_location") or doc.get("installation_notes")):
        codes.append("installation_details_required")
    return codes


async def create_intake(
    *, tenant_id: str, payload: dict[str, Any], created_by_user_id: Optional[str], actor_email: str,
) -> dict:
    idempotency_key = payload.get("idempotency_key")
    if idempotency_key:
        existing = await db.intake_submissions.find_one(
            {"tenant_id": tenant_id, "idempotency_key": idempotency_key}, {"_id": 0},
        )
        if existing:
            return serialize_doc(existing)

    await _validate_references(
        tenant_id,
        customer_id=payload.get("customer_id"), quote_id=payload.get("quote_id"),
        order_id=payload.get("order_id"), assigned_user_id=payload.get("assigned_user_id"),
        file_ids=payload.get("file_ids"), questionnaire_submission_ids=payload.get("questionnaire_submission_ids"),
    )

    items_in = payload.get("items") or []
    items: list[IntakeItem] = []
    for item in items_in:
        await _validate_file_ids(tenant_id, item.get("file_ids") or [])
        items.append(IntakeItem(**item))

    # Reserved/server-controlled fields — a client-supplied value is always
    # discarded here, never trusted (mirrors `_resolve_item_pricing` pattern
    # in EC9: the server, not the client, owns these).
    _reserved = {
        "items", "idempotency_key", "id", "tenant_id", "intake_number", "status",
        "created_at", "updated_at", "created_by_user_id", "updated_by_user_id",
        "submitted_at", "reviewed_at", "converted_at",
        "rejected_at", "rejected_reason", "cancelled_at", "cancelled_reason",
    }
    num = await next_number(tenant_id=tenant_id, name="intake_submission")
    doc = IntakeSubmission(
        tenant_id=tenant_id, intake_number=num,
        created_by_user_id=created_by_user_id, updated_by_user_id=created_by_user_id,
        items=items,
        **{k: v for k, v in payload.items() if k not in _reserved},
        idempotency_key=idempotency_key,
    ).model_dump()

    try:
        await db.intake_submissions.insert_one(prepare_for_mongo(dict(doc)))
    except DuplicateKeyError:
        # Idempotency race — another concurrent request already inserted this key.
        existing = await db.intake_submissions.find_one(
            {"tenant_id": tenant_id, "idempotency_key": idempotency_key}, {"_id": 0},
        )
        if existing:
            return serialize_doc(existing)
        raise

    await record_audit(
        tenant_id=tenant_id, actor_user_id=(created_by_user_id or "system"), actor_email=actor_email,
        action="intake.create", entity_type="intake_submission", entity_id=doc["id"],
        summary=f"Intake IN-{num} created", diff={"source_type": doc.get("source_type"), "status": doc.get("status")},
    )
    doc.pop("_id", None)
    return serialize_doc(doc)


async def add_item(
    *, tenant_id: str, intake_id: str, item: dict[str, Any],
    actor_user_id: str, actor_email: str,
) -> dict:
    submission = await db.intake_submissions.find_one({"id": intake_id, "tenant_id": tenant_id})
    if not submission:
        raise IntakeError("intake_not_found", "Intake submission not found")
    if submission.get("status") not in {"draft", "needs_information"}:
        raise IntakeError("intake_locked", "Items can only be added while draft or needs_information")
    await _validate_file_ids(tenant_id, item.get("file_ids") or [])
    new_item = IntakeItem(**item).model_dump()
    now = utc_now().isoformat()
    await db.intake_submissions.update_one(
        {"id": intake_id, "tenant_id": tenant_id},
        {"$push": {"items": new_item}, "$set": {"updated_at": now, "updated_by_user_id": actor_user_id}},
    )
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="intake.add_item", entity_type="intake_submission", entity_id=intake_id,
        summary="Intake item added", diff={"item_id": new_item["id"], "category": new_item.get("category")},
    )
    doc = await db.intake_submissions.find_one({"id": intake_id, "tenant_id": tenant_id}, {"_id": 0})
    return serialize_doc(doc or {})


async def update_item(
    *, tenant_id: str, intake_id: str, item_id: str, updates: dict[str, Any],
    actor_user_id: str, actor_email: str,
) -> dict:
    submission = await db.intake_submissions.find_one({"id": intake_id, "tenant_id": tenant_id})
    if not submission:
        raise IntakeError("intake_not_found", "Intake submission not found")
    items = submission.get("items") or []
    item = next((i for i in items if i.get("id") == item_id), None)
    if not item:
        raise IntakeError("item_not_found", "Intake item not found")
    if submission.get("status") not in {"draft", "needs_information"}:
        raise IntakeError("intake_locked", "Items can only be edited while draft or needs_information")

    _reserved = {"id", "conversion_status", "quote_line_item_id", "order_item_id"}
    changes = {k: v for k, v in updates.items() if k not in _reserved and v is not None}
    if "file_ids" in changes:
        await _validate_file_ids(tenant_id, changes["file_ids"])
    if "pricing_snapshot_id" in changes:
        await _validate_pricing_snapshot(tenant_id, changes["pricing_snapshot_id"])
    if changes.get("pricing_status") == "manual_price_entered" and not (
        changes.get("manual_price_cents", item.get("manual_price_cents"))
    ):
        raise IntakeError("manual_price_required", "manual_price_cents is required when pricing_status is manual_price_entered")

    merged = {**item, **changes}
    IntakeItem(**merged)  # validate the merged shape before writing

    now = utc_now().isoformat()
    new_items = [merged if i.get("id") == item_id else i for i in items]
    await db.intake_submissions.update_one(
        {"id": intake_id, "tenant_id": tenant_id},
        {"$set": {"items": new_items, "updated_at": now, "updated_by_user_id": actor_user_id}},
    )
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="intake.update_item", entity_type="intake_submission", entity_id=intake_id,
        summary="Intake item updated", diff={"item_id": item_id, "fields": list(changes.keys())},
    )
    doc = await db.intake_submissions.find_one({"id": intake_id, "tenant_id": tenant_id}, {"_id": 0})
    return serialize_doc(doc or {})


async def duplicate_item(
    *, tenant_id: str, intake_id: str, item_id: str, actor_user_id: str, actor_email: str,
) -> dict:
    submission = await db.intake_submissions.find_one({"id": intake_id, "tenant_id": tenant_id})
    if not submission:
        raise IntakeError("intake_not_found", "Intake submission not found")
    items = submission.get("items") or []
    item = next((i for i in items if i.get("id") == item_id), None)
    if not item:
        raise IntakeError("item_not_found", "Intake item not found")
    if submission.get("status") not in {"draft", "needs_information"}:
        raise IntakeError("intake_locked", "Items can only be duplicated while draft or needs_information")

    # Never inherit conversion lineage or accepted pricing snapshot lineage —
    # a duplicate is a NEW item, not a continuation of the original's history.
    dup_payload = {**item}
    for k in ("id",):
        dup_payload.pop(k, None)
    dup = IntakeItem(
        **{**dup_payload,
           "conversion_status": "pending", "quote_line_item_id": None, "order_item_id": None,
           "pricing_status": "not_started", "pricing_snapshot_id": None,
           "selected_price_source": None, "manual_price_cents": None,
           "pricing_warning_codes": [], "pricing_ready": False},
    ).model_dump()

    now = utc_now().isoformat()
    await db.intake_submissions.update_one(
        {"id": intake_id, "tenant_id": tenant_id},
        {"$push": {"items": dup}, "$set": {"updated_at": now, "updated_by_user_id": actor_user_id}},
    )
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="intake.duplicate_item", entity_type="intake_submission", entity_id=intake_id,
        summary="Intake item duplicated", diff={"source_item_id": item_id, "new_item_id": dup["id"]},
    )
    doc = await db.intake_submissions.find_one({"id": intake_id, "tenant_id": tenant_id}, {"_id": 0})
    return serialize_doc(doc or {})


async def remove_item(
    *, tenant_id: str, intake_id: str, item_id: str, actor_user_id: str, actor_email: str,
) -> dict:
    submission = await db.intake_submissions.find_one({"id": intake_id, "tenant_id": tenant_id})
    if not submission:
        raise IntakeError("intake_not_found", "Intake submission not found")
    items = submission.get("items") or []
    item = next((i for i in items if i.get("id") == item_id), None)
    if not item:
        raise IntakeError("item_not_found", "Intake item not found")
    if submission.get("status") not in {"draft", "needs_information"}:
        raise IntakeError("intake_locked", "Items can only be removed while draft or needs_information")
    if item.get("conversion_status") != "pending":
        raise IntakeError("item_converted_cannot_remove", "This item has already been converted and cannot be removed")

    now = utc_now().isoformat()
    remaining = [i for i in items if i.get("id") != item_id]
    await db.intake_submissions.update_one(
        {"id": intake_id, "tenant_id": tenant_id},
        {"$set": {"items": remaining, "updated_at": now, "updated_by_user_id": actor_user_id}},
    )
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="intake.remove_item", entity_type="intake_submission", entity_id=intake_id,
        summary="Intake item removed", diff={"item_id": item_id},
    )
    doc = await db.intake_submissions.find_one({"id": intake_id, "tenant_id": tenant_id}, {"_id": 0})
    return serialize_doc(doc or {})


async def reorder_items(
    *, tenant_id: str, intake_id: str, ordered_item_ids: list[str], actor_user_id: str, actor_email: str,
) -> dict:
    submission = await db.intake_submissions.find_one({"id": intake_id, "tenant_id": tenant_id})
    if not submission:
        raise IntakeError("intake_not_found", "Intake submission not found")
    items = submission.get("items") or []
    by_id = {i.get("id"): i for i in items}
    if set(ordered_item_ids) != set(by_id.keys()):
        raise IntakeError("reorder_mismatch", "ordered_item_ids must contain exactly the current item ids")

    now = utc_now().isoformat()
    reordered = [by_id[i] for i in ordered_item_ids]
    await db.intake_submissions.update_one(
        {"id": intake_id, "tenant_id": tenant_id},
        {"$set": {"items": reordered, "updated_at": now, "updated_by_user_id": actor_user_id}},
    )
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="intake.reorder_items", entity_type="intake_submission", entity_id=intake_id,
        summary="Intake items reordered", diff={"order": ordered_item_ids},
    )
    doc = await db.intake_submissions.find_one({"id": intake_id, "tenant_id": tenant_id}, {"_id": 0})
    return serialize_doc(doc or {})


async def transition(
    *, tenant_id: str, intake_id: str, target: str, reason: Optional[str] = None,
    quote_id: Optional[str] = None, order_id: Optional[str] = None,
    actor_user_id: str, actor_email: str,
) -> dict:
    submission = await db.intake_submissions.find_one({"id": intake_id, "tenant_id": tenant_id})
    if not submission:
        raise IntakeError("intake_not_found", "Intake submission not found")
    current = submission.get("status", "draft")
    if target not in ALLOWED_TRANSITIONS.get(current, set()):
        raise IntakeError("invalid_transition", f"Cannot move intake from {current} to {target}")
    if target in {"rejected", "cancelled"} and not reason:
        raise IntakeError("reason_required", "A reason is required to reject or cancel an intake")
    if target == "submitted":
        missing = missing_information_for_submission(submission)
        if missing:
            raise IntakeError(
                "missing_information", f"Intake is missing required information: {missing}", details=missing,
            )

    now = utc_now().isoformat()
    updates: dict[str, Any] = {"status": target, "updated_at": now, "updated_by_user_id": actor_user_id}
    if target == "submitted":
        updates["submitted_at"] = now
    elif target == "under_review":
        updates["reviewed_at"] = now
        updates["reviewed_by_user_id"] = actor_user_id
    elif target == "rejected":
        updates["rejected_at"] = now
        updates["rejected_reason"] = reason
    elif target == "cancelled":
        updates["cancelled_at"] = now
        updates["cancelled_reason"] = reason
    elif target == "converted_to_quote":
        effective_quote_id = quote_id or submission.get("quote_id")
        if not effective_quote_id:
            raise IntakeError("quote_id_required", "quote_id is required to mark an intake converted_to_quote")
        await _validate_quote(tenant_id, effective_quote_id)
        updates["quote_id"] = effective_quote_id
        updates["converted_at"] = now
    elif target == "converted_to_order":
        effective_order_id = order_id or submission.get("order_id")
        if not effective_order_id:
            raise IntakeError("order_id_required", "order_id is required to mark an intake converted_to_order")
        await _validate_order(tenant_id, effective_order_id)
        updates["order_id"] = effective_order_id
        updates["converted_at"] = now

    history_entry = {
        "from": current, "to": target, "reason": reason,
        "actor_user_id": actor_user_id, "actor_email": actor_email, "at": now,
    }
    await db.intake_submissions.update_one(
        {"id": intake_id, "tenant_id": tenant_id},
        {"$set": updates, "$push": {"status_history": history_entry}},
    )
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action=f"intake.{target}", entity_type="intake_submission", entity_id=intake_id,
        summary=f"Intake IN-{submission.get('intake_number')} → {target}",
        diff={"from": current, "to": target, "reason": reason},
    )
    doc = await db.intake_submissions.find_one({"id": intake_id, "tenant_id": tenant_id}, {"_id": 0})
    return serialize_doc(doc or {})


async def update_intake(
    *, tenant_id: str, intake_id: str, updates: dict[str, Any],
    actor_user_id: str, actor_email: str,
) -> dict:
    submission = await db.intake_submissions.find_one({"id": intake_id, "tenant_id": tenant_id})
    if not submission:
        raise IntakeError("intake_not_found", "Intake submission not found")
    if submission.get("status") not in {"draft", "needs_information"}:
        raise IntakeError("intake_locked", "Intake can only be edited while draft or needs_information")

    _reserved = {
        "items", "idempotency_key", "id", "tenant_id", "intake_number", "status",
        "created_at", "updated_at", "created_by_user_id", "updated_by_user_id",
        "submitted_at", "reviewed_at", "converted_at",
        "rejected_at", "rejected_reason", "cancelled_at", "cancelled_reason",
    }
    changes = {k: v for k, v in updates.items() if k not in _reserved and v is not None}
    if not changes:
        return serialize_doc({k: v for k, v in submission.items() if k != "_id"})

    await _validate_references(
        tenant_id,
        customer_id=changes.get("customer_id"), quote_id=changes.get("quote_id"),
        order_id=changes.get("order_id"), assigned_user_id=changes.get("assigned_user_id"),
        file_ids=changes.get("file_ids"), questionnaire_submission_ids=changes.get("questionnaire_submission_ids"),
    )

    now = utc_now().isoformat()
    changes["updated_at"] = now
    changes["updated_by_user_id"] = actor_user_id
    await db.intake_submissions.update_one({"id": intake_id, "tenant_id": tenant_id}, {"$set": changes})
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="intake.update", entity_type="intake_submission", entity_id=intake_id,
        summary=f"Intake IN-{submission.get('intake_number')} updated", diff={"fields": list(changes.keys())},
    )
    doc = await db.intake_submissions.find_one({"id": intake_id, "tenant_id": tenant_id}, {"_id": 0})
    return serialize_doc(doc or {})


# ---- Conversion contracts (Phase 10A: validation + preview only — no writes) ----

def preview_quote_line_item(item: dict[str, Any]) -> dict[str, Any]:
    """Pure mapping of an IntakeItem into the shape the existing EC9-integrated
    Quote Line Item create endpoint accepts. Never invents a price — no
    `unit_price_cents` is set; that remains owned by `calculate_pricing()`
    when Phase 10F actually calls the real create endpoint."""
    return {
        "category": item.get("category"),
        "item_name": item.get("item_name"),
        "description": item.get("description") or item.get("item_name") or "Untitled item",
        "quantity": item.get("quantity", 1),
        "category_inputs": item.get("category_inputs") or {},
        "material_profile_id": item.get("material_profile_id"),
        "pricing_component_ids": item.get("pricing_component_ids") or [],
        "saved_item_id": item.get("saved_item_id"),
        "notes": item.get("customer_notes"),
    }


def preview_order_item(item: dict[str, Any]) -> dict[str, Any]:
    """Same contract as `preview_quote_line_item`, for the Order Item shape."""
    return preview_quote_line_item(item)


def build_conversion_preview(submission: dict[str, Any]) -> dict[str, Any]:
    items = submission.get("items") or []
    return {
        "quote_line_item_previews": [preview_quote_line_item(i) for i in items],
        "order_item_previews": [preview_order_item(i) for i in items],
    }


def serialize_for_customer(doc: dict[str, Any]) -> dict[str, Any]:
    """Strip internal-only fields. Not wired to any route in Phase 10A (no
    customer-facing intake route exists yet) — provided as the one shared
    place later phases (10E) must call, per the security review in the
    EC10 preflight §9/§11."""
    return {k: v for k, v in doc.items() if k not in _INTERNAL_ONLY_FIELDS}
