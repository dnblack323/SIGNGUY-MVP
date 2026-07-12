"""EC7 phase 7c — Expense service.

Owns the operational Expense lifecycle: create, update, archive, void.
Reuses EC2 FileRecord + Attachment for receipts (via ExpenseAttachment).
"""
from __future__ import annotations
from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import serialize_doc, utc_now
from ..models.expense import Expense, ExpenseAttachment
from ..services import expense_categories as _cats
from ..services.audit import record_audit
from ..services.sequence import next_number


async def _resolve_category(*, tenant_id: str, key: str) -> tuple[str, str]:
    """Return (key, label_snapshot) for a valid category. Raises ValueError."""
    cat = await _cats.get_category(tenant_id=tenant_id, key=key)
    if not cat:
        raise ValueError("category_not_found")
    return cat["key"], cat["label"]


async def create_expense(*, tenant_id: str, actor_user_id: str, actor_email: str,
                         payload: dict[str, Any]) -> dict:
    if not payload.get("description") or not str(payload["description"]).strip():
        raise ValueError("description_required")
    amount_cents = int(payload.get("amount_cents", 0))
    if amount_cents < 0:
        raise ValueError("amount_cents_must_be_non_negative")
    tax_cents = int(payload.get("tax_cents", 0))
    if tax_cents < 0:
        raise ValueError("tax_cents_must_be_non_negative")
    if not payload.get("expense_date"):
        raise ValueError("expense_date_required")
    category_key = payload.get("category_key") or ""
    key, label = await _resolve_category(tenant_id=tenant_id, key=category_key)
    # Optional vendor snapshot
    vendor_id = payload.get("vendor_id")
    vendor_name_snapshot = None
    if vendor_id:
        v = await db.vendors.find_one({"tenant_id": tenant_id, "id": vendor_id}, {"_id": 0})
        if not v:
            raise ValueError("vendor_not_found")
        vendor_name_snapshot = v["name"]
    # Optional linked-Order-etc. sanity checks (tenant scope only)
    for link_field, coll in [("purchase_order_id", "purchase_orders"),
                              ("customer_id", "customers"),
                              ("order_id", "orders")]:
        val = payload.get(link_field)
        if val:
            hit = await db[coll].find_one({"tenant_id": tenant_id, "id": val}, {"_id": 0, "id": 1})
            if not hit:
                raise ValueError(f"{link_field}_not_found")
    number = await next_number(tenant_id=tenant_id, name="expense")
    exp = Expense(
        tenant_id=tenant_id, number=number,
        expense_date=str(payload["expense_date"]),
        category_key=key, category_label_snapshot=label,
        vendor_id=vendor_id, vendor_name_snapshot=vendor_name_snapshot,
        description=str(payload["description"]).strip(),
        amount_cents=amount_cents, tax_cents=tax_cents,
        total_cents=amount_cents + tax_cents,
        payment_method=payload.get("payment_method", "other"),
        reference=payload.get("reference"),
        deductible_class=payload.get("deductible_class", "unknown"),
        recurring=bool(payload.get("recurring", False)),
        recurring_reference=payload.get("recurring_reference"),
        purchase_order_id=payload.get("purchase_order_id"),
        customer_id=payload.get("customer_id"),
        order_id=payload.get("order_id"),
        project_reference=payload.get("project_reference"),
        internal_notes=payload.get("internal_notes"),
        created_by=actor_user_id,
    ).model_dump()
    await db.expenses.insert_one(exp)
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="expense.create", entity_type="expense", entity_id=exp["id"],
        summary=f"Created Expense #{number} ({label}, ${exp['total_cents']/100:.2f})",
        diff={"category_key": key, "amount_cents": amount_cents, "tax_cents": tax_cents},
    )
    exp.pop("_id", None)
    return serialize_doc(exp)


async def update_expense(*, tenant_id: str, expense_id: str, actor_user_id: str,
                         actor_email: str, payload: dict[str, Any]) -> dict:
    exp = await db.expenses.find_one({"tenant_id": tenant_id, "id": expense_id}, {"_id": 0})
    if not exp:
        raise ValueError("expense_not_found")
    if exp["state"] != "active":
        raise ValueError(f"expense_not_editable:{exp['state']}")
    updates: dict[str, Any] = {}
    if "category_key" in payload:
        key, label = await _resolve_category(tenant_id=tenant_id, key=payload["category_key"])
        updates["category_key"] = key
        updates["category_label_snapshot"] = label
    for f in ("expense_date", "description", "reference", "internal_notes",
              "project_reference", "payment_method", "deductible_class",
              "recurring", "recurring_reference"):
        if f in payload:
            updates[f] = payload[f]
    if "amount_cents" in payload:
        amt = int(payload["amount_cents"])
        if amt < 0:
            raise ValueError("amount_cents_must_be_non_negative")
        updates["amount_cents"] = amt
    if "tax_cents" in payload:
        tx = int(payload["tax_cents"])
        if tx < 0:
            raise ValueError("tax_cents_must_be_non_negative")
        updates["tax_cents"] = tx
    if "amount_cents" in updates or "tax_cents" in updates:
        updates["total_cents"] = int(updates.get("amount_cents", exp["amount_cents"])) + \
                                  int(updates.get("tax_cents", exp["tax_cents"]))
    # Link changes
    if "vendor_id" in payload:
        vid = payload["vendor_id"]
        if vid:
            v = await db.vendors.find_one({"tenant_id": tenant_id, "id": vid}, {"_id": 0})
            if not v:
                raise ValueError("vendor_not_found")
            updates["vendor_id"] = vid
            updates["vendor_name_snapshot"] = v["name"]
        else:
            updates["vendor_id"] = None
            updates["vendor_name_snapshot"] = None
    for link_field, coll in [("purchase_order_id", "purchase_orders"),
                              ("customer_id", "customers"),
                              ("order_id", "orders")]:
        if link_field in payload:
            val = payload[link_field]
            if val:
                hit = await db[coll].find_one({"tenant_id": tenant_id, "id": val}, {"_id": 0, "id": 1})
                if not hit:
                    raise ValueError(f"{link_field}_not_found")
            updates[link_field] = val
    updates["updated_at"] = utc_now().isoformat()
    await db.expenses.update_one({"tenant_id": tenant_id, "id": expense_id}, {"$set": updates})
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="expense.update", entity_type="expense", entity_id=expense_id,
        summary=f"Updated Expense #{exp['number']}", diff=updates,
    )
    fresh = await db.expenses.find_one({"tenant_id": tenant_id, "id": expense_id}, {"_id": 0})
    return serialize_doc(fresh or {})


async def archive_expense(*, tenant_id: str, expense_id: str, actor_user_id: str,
                          actor_email: str) -> dict:
    exp = await db.expenses.find_one({"tenant_id": tenant_id, "id": expense_id}, {"_id": 0})
    if not exp:
        raise ValueError("expense_not_found")
    if exp["state"] == "voided":
        raise ValueError("expense_voided_cannot_archive")
    await db.expenses.update_one(
        {"tenant_id": tenant_id, "id": expense_id},
        {"$set": {"state": "archived", "archived_at": utc_now().isoformat(),
                  "updated_at": utc_now().isoformat()}}
    )
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="expense.archive", entity_type="expense", entity_id=expense_id,
        summary=f"Archived Expense #{exp['number']}",
    )
    return {"archived": True, "id": expense_id}


async def restore_expense(*, tenant_id: str, expense_id: str, actor_user_id: str,
                          actor_email: str) -> dict:
    exp = await db.expenses.find_one({"tenant_id": tenant_id, "id": expense_id}, {"_id": 0})
    if not exp:
        raise ValueError("expense_not_found")
    if exp["state"] != "archived":
        raise ValueError("expense_not_archived")
    await db.expenses.update_one(
        {"tenant_id": tenant_id, "id": expense_id},
        {"$set": {"state": "active", "archived_at": None,
                  "updated_at": utc_now().isoformat()}}
    )
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="expense.restore", entity_type="expense", entity_id=expense_id,
        summary=f"Restored Expense #{exp['number']}",
    )
    return {"restored": True, "id": expense_id}


async def void_expense(*, tenant_id: str, expense_id: str, actor_user_id: str,
                       actor_email: str, reason: str) -> dict:
    if not reason or not reason.strip():
        raise ValueError("void_reason_required")
    exp = await db.expenses.find_one({"tenant_id": tenant_id, "id": expense_id}, {"_id": 0})
    if not exp:
        raise ValueError("expense_not_found")
    if exp["state"] == "voided":
        raise ValueError("expense_already_voided")
    await db.expenses.update_one(
        {"tenant_id": tenant_id, "id": expense_id},
        {"$set": {"state": "voided", "voided_at": utc_now().isoformat(),
                  "void_reason": reason.strip(), "updated_at": utc_now().isoformat()}}
    )
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="expense.void", entity_type="expense", entity_id=expense_id,
        summary=f"Voided Expense #{exp['number']}", diff={"reason": reason},
    )
    return {"voided": True, "id": expense_id}


async def attach_receipt(*, tenant_id: str, expense_id: str, file_id: str,
                         role: str, actor_user_id: str, actor_email: str,
                         note: Optional[str] = None) -> dict:
    exp = await db.expenses.find_one({"tenant_id": tenant_id, "id": expense_id}, {"_id": 0, "id": 1})
    if not exp:
        raise ValueError("expense_not_found")
    file_doc = await db.files.find_one({"tenant_id": tenant_id, "id": file_id}, {"_id": 0, "id": 1})
    if not file_doc:
        raise ValueError("file_not_found")
    doc = ExpenseAttachment(
        tenant_id=tenant_id, expense_id=expense_id, file_id=file_id,
        role=role or "receipt", attached_by=actor_user_id, note=note,
    ).model_dump()
    await db.expense_attachments.insert_one(doc)
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="expense.attach", entity_type="expense", entity_id=expense_id,
        summary=f"Attached {role} to Expense", diff={"file_id": file_id, "role": role},
    )
    return serialize_doc(doc)


async def list_attachments(*, tenant_id: str, expense_id: str) -> list[dict]:
    cur = db.expense_attachments.find(
        {"tenant_id": tenant_id, "expense_id": expense_id, "archived": False}, {"_id": 0}
    )
    out: list[dict] = []
    async for a in cur:
        file_doc = await db.files.find_one({"tenant_id": tenant_id, "id": a["file_id"]}, {"_id": 0})
        a["file"] = serialize_doc(file_doc) if file_doc else None
        out.append(serialize_doc(a))
    return out


async def archive_attachment(*, tenant_id: str, attachment_id: str,
                             actor_user_id: str, actor_email: str) -> dict:
    res = await db.expense_attachments.update_one(
        {"tenant_id": tenant_id, "id": attachment_id},
        {"$set": {"archived": True, "updated_at": utc_now().isoformat()}}
    )
    if res.matched_count == 0:
        raise ValueError("attachment_not_found")
    return {"archived": True, "id": attachment_id}


# ------- Queries -------
async def list_expenses(*, tenant_id: str, filters: dict[str, Any],
                       limit: int = 100, skip: int = 0) -> dict:
    filt: dict[str, Any] = {"tenant_id": tenant_id}
    if filters.get("state"):
        filt["state"] = filters["state"]
    else:
        filt["state"] = "active"
    if filters.get("category_key"):
        filt["category_key"] = filters["category_key"]
    if filters.get("vendor_id"):
        filt["vendor_id"] = filters["vendor_id"]
    if filters.get("purchase_order_id"):
        filt["purchase_order_id"] = filters["purchase_order_id"]
    if filters.get("customer_id"):
        filt["customer_id"] = filters["customer_id"]
    if filters.get("order_id"):
        filt["order_id"] = filters["order_id"]
    date_filter: dict[str, Any] = {}
    if filters.get("date_from"):
        date_filter["$gte"] = filters["date_from"]
    if filters.get("date_to"):
        date_filter["$lte"] = filters["date_to"]
    if date_filter:
        filt["expense_date"] = date_filter
    total = await db.expenses.count_documents(filt)
    cur = db.expenses.find(filt, {"_id": 0}).sort([("expense_date", -1), ("number", -1)]).skip(skip).limit(limit)
    return {"items": [serialize_doc(d) async for d in cur], "total": total}


async def get_expense(*, tenant_id: str, expense_id: str) -> Optional[dict]:
    doc = await db.expenses.find_one(
        {"tenant_id": tenant_id, "id": expense_id}, {"_id": 0}
    )
    return serialize_doc(doc) if doc else None
