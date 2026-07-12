"""EC7 phase 7c — Expenses + ExpenseCategories router."""
from __future__ import annotations
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..core.db import db
from ..core.permissions import Perm
from ..core.time_utils import serialize_doc
from ..deps import require_permission
from ..services import expense_service, expense_categories

router = APIRouter(tags=["expenses"])


# --------- Category endpoints ---------
categories_router = APIRouter(prefix="/expense-categories", tags=["expenses"])


class CategoryIn(BaseModel):
    key: str
    label: str
    description: Optional[str] = None
    position: int = 999


class CategoryRenameIn(BaseModel):
    label: str
    description: Optional[str] = None


@categories_router.get("")
async def list_categories(include_archived: bool = False,
                          user: dict = Depends(require_permission(Perm.EXPENSE_READ))) -> dict:
    # Idempotent seed on first read.
    await expense_categories.seed_defaults(tenant_id=user["tenant_id"])
    items = await expense_categories.list_categories(
        tenant_id=user["tenant_id"], include_archived=include_archived,
    )
    return {"items": items}


@categories_router.post("", status_code=201)
async def create_category(payload: CategoryIn,
                          user: dict = Depends(require_permission(Perm.EXPENSE_WRITE))) -> dict:
    try:
        return await expense_categories.create_category(
            tenant_id=user["tenant_id"], key=payload.key, label=payload.label,
            description=payload.description, position=payload.position,
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))


@categories_router.patch("/{key}")
async def rename_category(key: str, payload: CategoryRenameIn,
                          user: dict = Depends(require_permission(Perm.EXPENSE_WRITE))) -> dict:
    try:
        return await expense_categories.rename_category(
            tenant_id=user["tenant_id"], key=key,
            label=payload.label, description=payload.description,
        )
    except ValueError as ex:
        raise HTTPException(status_code=404 if "not_found" in str(ex) else 400, detail=str(ex))


@categories_router.post("/{key}/archive")
async def archive_category(key: str,
                            user: dict = Depends(require_permission(Perm.EXPENSE_WRITE))) -> dict:
    try:
        return await expense_categories.archive_category(
            tenant_id=user["tenant_id"], key=key
        )
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex))


@categories_router.post("/{key}/unarchive")
async def unarchive_category(key: str,
                              user: dict = Depends(require_permission(Perm.EXPENSE_WRITE))) -> dict:
    try:
        return await expense_categories.unarchive_category(
            tenant_id=user["tenant_id"], key=key
        )
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex))


# --------- Expense endpoints ---------
expenses_router = APIRouter(prefix="/expenses", tags=["expenses"])


class ExpenseIn(BaseModel):
    expense_date: str
    category_key: str
    description: str
    amount_cents: int
    tax_cents: int = 0
    payment_method: str = "other"
    reference: Optional[str] = None
    deductible_class: str = "unknown"
    recurring: bool = False
    recurring_reference: Optional[str] = None
    vendor_id: Optional[str] = None
    purchase_order_id: Optional[str] = None
    customer_id: Optional[str] = None
    order_id: Optional[str] = None
    project_reference: Optional[str] = None
    internal_notes: Optional[str] = None


class ExpenseUpdateIn(BaseModel):
    expense_date: Optional[str] = None
    category_key: Optional[str] = None
    description: Optional[str] = None
    amount_cents: Optional[int] = None
    tax_cents: Optional[int] = None
    payment_method: Optional[str] = None
    reference: Optional[str] = None
    deductible_class: Optional[str] = None
    recurring: Optional[bool] = None
    recurring_reference: Optional[str] = None
    vendor_id: Optional[str] = None
    purchase_order_id: Optional[str] = None
    customer_id: Optional[str] = None
    order_id: Optional[str] = None
    project_reference: Optional[str] = None
    internal_notes: Optional[str] = None


class VoidIn(BaseModel):
    reason: str


class AttachmentIn(BaseModel):
    file_id: str
    role: str = "receipt"
    note: Optional[str] = None


@expenses_router.get("")
async def list_expenses(state: Optional[str] = None,
                        category_key: Optional[str] = None,
                        vendor_id: Optional[str] = None,
                        purchase_order_id: Optional[str] = None,
                        customer_id: Optional[str] = None,
                        order_id: Optional[str] = None,
                        date_from: Optional[str] = None,
                        date_to: Optional[str] = None,
                        limit: int = Query(100, le=500),
                        skip: int = 0,
                        user: dict = Depends(require_permission(Perm.EXPENSE_READ))) -> dict:
    return await expense_service.list_expenses(
        tenant_id=user["tenant_id"],
        filters={"state": state, "category_key": category_key, "vendor_id": vendor_id,
                 "purchase_order_id": purchase_order_id, "customer_id": customer_id,
                 "order_id": order_id, "date_from": date_from, "date_to": date_to},
        limit=limit, skip=skip,
    )


@expenses_router.post("", status_code=201)
async def create_expense(payload: ExpenseIn,
                          user: dict = Depends(require_permission(Perm.EXPENSE_WRITE))) -> dict:
    # Ensure defaults seeded.
    await expense_categories.seed_defaults(tenant_id=user["tenant_id"])
    try:
        return await expense_service.create_expense(
            tenant_id=user["tenant_id"], actor_user_id=user["id"],
            actor_email=user["email"], payload=payload.model_dump(),
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))


@expenses_router.get("/{expense_id}")
async def get_expense(expense_id: str,
                       user: dict = Depends(require_permission(Perm.EXPENSE_READ))) -> dict:
    doc = await expense_service.get_expense(
        tenant_id=user["tenant_id"], expense_id=expense_id
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Expense not found")
    doc["attachments"] = await expense_service.list_attachments(
        tenant_id=user["tenant_id"], expense_id=expense_id
    )
    return doc


@expenses_router.patch("/{expense_id}")
async def update_expense(expense_id: str, payload: ExpenseUpdateIn,
                          user: dict = Depends(require_permission(Perm.EXPENSE_WRITE))) -> dict:
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    try:
        return await expense_service.update_expense(
            tenant_id=user["tenant_id"], expense_id=expense_id,
            actor_user_id=user["id"], actor_email=user["email"], payload=updates,
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))


@expenses_router.post("/{expense_id}/archive")
async def archive_expense(expense_id: str,
                          user: dict = Depends(require_permission(Perm.EXPENSE_ARCHIVE))) -> dict:
    try:
        return await expense_service.archive_expense(
            tenant_id=user["tenant_id"], expense_id=expense_id,
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))


@expenses_router.post("/{expense_id}/restore")
async def restore_expense(expense_id: str,
                          user: dict = Depends(require_permission(Perm.EXPENSE_ARCHIVE))) -> dict:
    try:
        return await expense_service.restore_expense(
            tenant_id=user["tenant_id"], expense_id=expense_id,
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))


@expenses_router.post("/{expense_id}/void")
async def void_expense(expense_id: str, payload: VoidIn,
                        user: dict = Depends(require_permission(Perm.EXPENSE_ARCHIVE))) -> dict:
    try:
        return await expense_service.void_expense(
            tenant_id=user["tenant_id"], expense_id=expense_id,
            actor_user_id=user["id"], actor_email=user["email"], reason=payload.reason,
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))


@expenses_router.post("/{expense_id}/attachments", status_code=201)
async def attach_receipt(expense_id: str, payload: AttachmentIn,
                          user: dict = Depends(require_permission(Perm.EXPENSE_WRITE))) -> dict:
    try:
        return await expense_service.attach_receipt(
            tenant_id=user["tenant_id"], expense_id=expense_id,
            file_id=payload.file_id, role=payload.role,
            actor_user_id=user["id"], actor_email=user["email"], note=payload.note,
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))


@expenses_router.post("/attachments/{attachment_id}/archive")
async def archive_attachment(attachment_id: str,
                              user: dict = Depends(require_permission(Perm.EXPENSE_WRITE))) -> dict:
    try:
        return await expense_service.archive_attachment(
            tenant_id=user["tenant_id"], attachment_id=attachment_id,
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except ValueError as ex:
        raise HTTPException(status_code=404, detail=str(ex))
