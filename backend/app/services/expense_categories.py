"""EC7 phase 7c — ExpenseCategory service.

Seeds a stable initial catalog per tenant and enforces the "stable key,
customizable label" contract.
"""
from __future__ import annotations
from typing import Optional

from ..core.db import db
from ..core.time_utils import serialize_doc, utc_now
from ..models.expense import ExpenseCategory


# Ordered list of the initial seeded categories. Keys are STABLE and MUST NOT
# change once seeded — reports rely on them. Labels are the default display
# string; tenants may rename them (updating `label` only).
INITIAL_CATEGORIES: list[tuple[str, str]] = [
    ("materials",      "Materials"),
    ("equipment",      "Equipment"),
    ("vehicle",        "Vehicle"),
    ("fuel",           "Fuel"),
    ("rent",           "Rent"),
    ("utilities",      "Utilities"),
    ("software",       "Software"),
    ("advertising",    "Advertising"),
    ("subcontractor",  "Subcontractor"),
    ("office",         "Office"),
    ("insurance",      "Insurance"),
    ("taxes",          "Taxes"),
    ("fees",           "Fees"),
    ("shipping",       "Shipping"),
    ("maintenance",    "Maintenance"),
    ("miscellaneous",  "Miscellaneous"),
]


async def seed_defaults(*, tenant_id: str) -> int:
    """Idempotent seed of the initial expense-category catalog for a tenant.

    Existing rows are left untouched — label changes are preserved. Missing
    system categories are inserted. Returns count of newly inserted rows.
    """
    now = utc_now().isoformat()
    inserted = 0
    for pos, (key, label) in enumerate(INITIAL_CATEGORIES):
        existing = await db.expense_categories.find_one(
            {"tenant_id": tenant_id, "key": key}, {"_id": 0, "id": 1}
        )
        if existing:
            continue
        doc = ExpenseCategory(
            tenant_id=tenant_id, key=key, label=label, position=pos,
            system=True, archived=False,
        ).model_dump()
        await db.expense_categories.insert_one(doc)
        inserted += 1
    return inserted


async def list_categories(*, tenant_id: str, include_archived: bool = False) -> list[dict]:
    filt = {"tenant_id": tenant_id}
    if not include_archived:
        filt["archived"] = False
    cur = db.expense_categories.find(filt, {"_id": 0}).sort([("position", 1), ("label", 1)])
    return [serialize_doc(d) async for d in cur]


async def create_category(*, tenant_id: str, key: str, label: str,
                          description: Optional[str] = None,
                          position: int = 999) -> dict:
    """Custom (non-system) category. `key` must be lowercase_snake_case and unique."""
    if not key or not key.strip():
        raise ValueError("key_required")
    normalized = key.strip().lower()
    if any(c for c in normalized if not (c.isalnum() or c == "_")):
        raise ValueError("key_invalid_chars")
    existing = await db.expense_categories.find_one(
        {"tenant_id": tenant_id, "key": normalized}, {"_id": 0, "id": 1}
    )
    if existing:
        raise ValueError("key_already_exists")
    doc = ExpenseCategory(
        tenant_id=tenant_id, key=normalized, label=label.strip() or normalized,
        description=description, position=position, system=False, archived=False,
    ).model_dump()
    await db.expense_categories.insert_one(doc)
    return serialize_doc(doc)


async def rename_category(*, tenant_id: str, key: str, label: str,
                          description: Optional[str] = None) -> dict:
    """Update the display label (or description). The key never changes.
    Historical Expense rows are NOT rewritten — they keep their snapshot label."""
    upd = {"label": label.strip() or key, "updated_at": utc_now().isoformat()}
    if description is not None:
        upd["description"] = description
    res = await db.expense_categories.update_one(
        {"tenant_id": tenant_id, "key": key}, {"$set": upd}
    )
    if res.matched_count == 0:
        raise ValueError("category_not_found")
    doc = await db.expense_categories.find_one({"tenant_id": tenant_id, "key": key}, {"_id": 0})
    return serialize_doc(doc or {})


async def archive_category(*, tenant_id: str, key: str) -> dict:
    """Archive a category. Historical Expense rows remain usable and reportable.
    Archived categories are hidden from the "create Expense" picker."""
    res = await db.expense_categories.update_one(
        {"tenant_id": tenant_id, "key": key},
        {"$set": {"archived": True, "updated_at": utc_now().isoformat()}}
    )
    if res.matched_count == 0:
        raise ValueError("category_not_found")
    return {"archived": True, "key": key}


async def unarchive_category(*, tenant_id: str, key: str) -> dict:
    res = await db.expense_categories.update_one(
        {"tenant_id": tenant_id, "key": key},
        {"$set": {"archived": False, "updated_at": utc_now().isoformat()}}
    )
    if res.matched_count == 0:
        raise ValueError("category_not_found")
    return {"archived": False, "key": key}


async def get_category(*, tenant_id: str, key: str) -> Optional[dict]:
    doc = await db.expense_categories.find_one(
        {"tenant_id": tenant_id, "key": key}, {"_id": 0}
    )
    return serialize_doc(doc) if doc else None
