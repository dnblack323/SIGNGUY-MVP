"""EC3 — Quotes router.

Backward compatible with EC2 shape: `POST /quotes` accepts a plain quote with
optional `total_cents` and no line items. EC3 adds:

- Quote Line Items sub-resource (`/quotes/{id}/line-items`).
- Backend-derived totals on every line-item write.
- Revisions (`/quotes/{id}/revisions`): editing a `sent` (or later) quote's
  commercial fields creates a new revision BEFORE mutating the row.
- Expiration (`expires_at`) — derived at read time; expired conversion blocked
  unless `allow_expired=true` + `override_reason` provided.
- Approval-state foundation: `send`, internal `approve`, internal `decline`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field

from ..core.db import db
from ..core.permissions import Perm
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..deps import require_permission
from ..models.quote import Quote
from ..models.quote_line_item import QuoteLineItem
from ..services.audit import record_audit
from ..services.commerce_totals import compute_document_totals, compute_line_totals
from ..services.pricing_snapshot import build_manual_snapshot
from ..services.quote_conversion import convert_quote_to_order
from ..services.quote_revisions import get_revision, list_revisions, snapshot_current
from ..services.sequence import next_number

router = APIRouter(prefix="/quotes", tags=["quotes"])

# ---- Payloads ----


class QuoteIn(BaseModel):
    customer_id: str
    job_name: str = Field(min_length=1, max_length=200)
    notes: Optional[str] = None
    notes_internal: Optional[str] = None
    notes_customer: Optional[str] = None
    expires_at: Optional[str] = None
    total_cents: int = Field(0, ge=0)  # backward-compat single-total quotes


class QuoteUpdateIn(BaseModel):
    job_name: Optional[str] = None
    notes: Optional[str] = None
    notes_internal: Optional[str] = None
    notes_customer: Optional[str] = None
    expires_at: Optional[str] = None
    total_cents: Optional[int] = Field(None, ge=0)


class QuoteStatusIn(BaseModel):
    status: Literal["draft", "sent", "viewed", "approved", "declined", "void"]
    reason: Optional[str] = None
    source: Optional[str] = None  # e.g. staff / portal


class LineItemIn(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    quantity: int = Field(1, ge=1)
    unit_price_cents: int = Field(0, ge=0)
    discount_cents: int = Field(0, ge=0)
    tax_cents: int = Field(0, ge=0)
    category: Optional[str] = None
    product_type: Optional[str] = None
    sku: Optional[str] = None
    unit_of_measure: str = "each"
    width_inches: Optional[float] = None
    height_inches: Optional[float] = None
    depth_inches: Optional[float] = None
    material_key: Optional[str] = None
    notes: Optional[str] = None
    production_required: Optional[bool] = None
    manual_override_reason: Optional[str] = None


class LineItemPatchIn(BaseModel):
    description: Optional[str] = Field(None, min_length=1, max_length=500)
    quantity: Optional[int] = Field(None, ge=1)
    unit_price_cents: Optional[int] = Field(None, ge=0)
    discount_cents: Optional[int] = Field(None, ge=0)
    tax_cents: Optional[int] = Field(None, ge=0)
    category: Optional[str] = None
    product_type: Optional[str] = None
    sku: Optional[str] = None
    unit_of_measure: Optional[str] = None
    width_inches: Optional[float] = None
    height_inches: Optional[float] = None
    depth_inches: Optional[float] = None
    material_key: Optional[str] = None
    notes: Optional[str] = None
    production_required: Optional[bool] = None
    position: Optional[int] = None
    manual_override_reason: Optional[str] = None


class ConvertIn(BaseModel):
    allow_expired: bool = False
    override_reason: Optional[str] = None


# ---- Helpers ----


async def _recompute_quote_totals(tenant_id: str, quote_id: str) -> dict[str, int]:
    cursor = db.quote_line_items.find(
        {"tenant_id": tenant_id, "quote_id": quote_id},
        {"_id": 0},
    )
    items = [d async for d in cursor]
    doc = await db.quotes.find_one({"id": quote_id, "tenant_id": tenant_id})
    if doc:
        items = [
            i for i in items
            if int(i.get("revision_number") or 1) == int(doc.get("revision_number") or 1)
        ]
    totals = compute_document_totals(items)
    return totals


def _is_expired_doc(quote: dict[str, Any]) -> bool:
    exp = quote.get("expires_at")
    if not exp:
        return False
    try:
        dt = datetime.fromisoformat(str(exp).replace("Z", "+00:00"))
    except ValueError:
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt < utc_now()


def _derived_status(quote: dict[str, Any]) -> str:
    """Return the effective status accounting for derived expiration."""
    st = quote.get("status") or "draft"
    if st in {"sent", "viewed"} and _is_expired_doc(quote):
        return "expired"
    return st


def _serialize_quote(doc: dict[str, Any]) -> dict[str, Any]:
    out = serialize_doc(doc)
    out["effective_status"] = _derived_status(out)
    out["expired"] = _is_expired_doc(out)
    return out


async def _create_revision_before_edit(quote_doc: dict[str, Any], user: dict, reason: Optional[str] = None) -> int:
    """If a sent (or later) quote is being edited, snapshot then bump the number."""
    current_status = quote_doc.get("status") or "draft"
    if current_status in {"draft"}:
        return int(quote_doc.get("revision_number") or 1)
    # snapshot the current state
    await snapshot_current(
        tenant_id=user["tenant_id"],
        quote_doc=quote_doc,
        actor_user_id=user["id"],
        actor_email=user["email"],
        reason=reason,
    )
    new_number = int(quote_doc.get("revision_number") or 1) + 1
    # Roll all existing line items forward to the new revision
    await db.quote_line_items.update_many(
        {"tenant_id": user["tenant_id"], "quote_id": quote_doc["id"],
         "revision_number": int(quote_doc.get("revision_number") or 1)},
        {"$set": {"revision_number": new_number, "updated_at": utc_now().isoformat()}},
    )
    return new_number


# ---- Quote CRUD ----


@router.get("")
async def list_quotes(
    status: Optional[str] = Query(None),
    customer_id: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    skip: int = Query(0, ge=0),
    user: dict = Depends(require_permission(Perm.QUOTE_READ)),
) -> dict:
    q: dict = {"tenant_id": user["tenant_id"]}
    if status:
        q["status"] = status
    if customer_id:
        q["customer_id"] = customer_id
    total = await db.quotes.count_documents(q)
    cursor = db.quotes.find(q, {"_id": 0}).sort("number", -1).skip(skip).limit(limit)
    return {"items": [_serialize_quote(d) async for d in cursor], "total": total, "limit": limit, "skip": skip}


@router.post("", status_code=201)
async def create_quote(payload: QuoteIn, user: dict = Depends(require_permission(Perm.QUOTE_WRITE))) -> dict:
    cust = await db.customers.find_one({"id": payload.customer_id, "tenant_id": user["tenant_id"]})
    if not cust:
        raise HTTPException(status_code=404, detail="Customer not found")
    number = await next_number(tenant_id=user["tenant_id"], name="quote")
    q = Quote(
        tenant_id=user["tenant_id"],
        number=number,
        created_by=user["id"],
        customer_id=payload.customer_id,
        job_name=payload.job_name,
        notes=payload.notes,
        notes_internal=payload.notes_internal,
        notes_customer=payload.notes_customer,
        expires_at=payload.expires_at,
        total_cents=payload.total_cents,
        subtotal_cents=payload.total_cents,
    )
    await db.quotes.insert_one(prepare_for_mongo(q.model_dump()))
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="quote.created", entity_type="quote", entity_id=q.id,
        summary=f"Quote Q-{number} created for {cust['name']}",
    )
    return _serialize_quote(q.model_dump())


@router.get("/{quote_id}")
async def get_quote(quote_id: str, user: dict = Depends(require_permission(Perm.QUOTE_READ))) -> dict:
    doc = await db.quotes.find_one({"id": quote_id, "tenant_id": user["tenant_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Quote not found")
    line_items = await _list_line_items(user["tenant_id"], quote_id, int(doc.get("revision_number") or 1))
    return {"quote": _serialize_quote(doc), "line_items": line_items, "totals": compute_document_totals(line_items)}


@router.patch("/{quote_id}")
async def update_quote(quote_id: str, payload: QuoteUpdateIn, user: dict = Depends(require_permission(Perm.QUOTE_WRITE))) -> dict:
    doc = await db.quotes.find_one({"id": quote_id, "tenant_id": user["tenant_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Quote not found")
    if doc.get("status") == "converted":
        raise HTTPException(status_code=400, detail="Cannot edit a converted quote")
    if doc.get("status") == "void":
        raise HTTPException(status_code=400, detail="Cannot edit a voided quote")
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No updates")

    # Commercial fields → require revision on sent+ quotes
    commercial_fields = {"job_name", "expires_at", "notes_customer", "total_cents"}
    if any(k in updates for k in commercial_fields) and doc.get("status") not in {"draft"}:
        new_rev = await _create_revision_before_edit(doc, user, reason="edit_after_send")
        updates["revision_number"] = new_rev

    updates["updated_at"] = utc_now().isoformat()
    await db.quotes.update_one({"id": quote_id}, {"$set": updates})
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="quote.updated", entity_type="quote", entity_id=quote_id,
        summary=f"Quote Q-{doc['number']} updated", diff={"changes": updates},
    )
    doc = await db.quotes.find_one({"id": quote_id}, {"_id": 0})
    return _serialize_quote(doc)


@router.post("/{quote_id}/status")
async def set_status(quote_id: str, payload: QuoteStatusIn, user: dict = Depends(require_permission(Perm.QUOTE_WRITE))) -> dict:
    doc = await db.quotes.find_one({"id": quote_id, "tenant_id": user["tenant_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Quote not found")
    current = doc.get("status") or "draft"
    target = payload.status

    if current == "converted":
        raise HTTPException(status_code=400, detail="Quote already converted")
    if current == "void" and target != "void":
        raise HTTPException(status_code=400, detail="Quote is void")

    # Allowed transitions map (EC3 approval foundation)
    allowed = {
        "draft": {"sent", "void"},
        "sent": {"viewed", "approved", "declined", "void"},
        "viewed": {"approved", "declined", "void"},
        "approved": {"void"},
        "declined": {"void"},
        "expired": {"void"},
        "void": set(),
    }
    if target not in allowed.get(current, set()) and target != current:
        raise HTTPException(status_code=400, detail=f"Invalid transition {current} → {target}")
    if target == current:
        return _serialize_quote(doc)

    now = utc_now()
    updates: dict[str, Any] = {"status": target, "updated_at": now.isoformat()}
    if target == "sent":
        updates["sent_at"] = now
    elif target == "viewed":
        updates["viewed_at"] = now
    elif target == "approved":
        updates["approved_at"] = now
        updates["approved_revision"] = int(doc.get("revision_number") or 1)
        updates["approved_actor_user_id"] = user["id"]
        updates["approved_source"] = payload.source or "staff"
    elif target == "declined":
        updates["declined_at"] = now
        updates["declined_reason"] = payload.reason

    await db.quotes.update_one({"id": quote_id}, {"$set": prepare_for_mongo(updates)})
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action=f"quote.{target}", entity_type="quote", entity_id=quote_id,
        summary=f"Quote Q-{doc['number']} → {target}",
        diff={"from": current, "to": target, "reason": payload.reason},
    )
    doc = await db.quotes.find_one({"id": quote_id}, {"_id": 0})
    return _serialize_quote(doc)


@router.post("/{quote_id}/archive")
async def archive_quote(quote_id: str, user: dict = Depends(require_permission(Perm.QUOTE_WRITE))) -> dict:
    doc = await db.quotes.find_one({"id": quote_id, "tenant_id": user["tenant_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Quote not found")
    if doc.get("archived_at"):
        return _serialize_quote(doc)
    await db.quotes.update_one(
        {"id": quote_id},
        {"$set": {"archived_at": utc_now(), "updated_at": utc_now().isoformat()}},
    )
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="quote.archived", entity_type="quote", entity_id=quote_id,
        summary=f"Quote Q-{doc['number']} archived",
    )
    doc = await db.quotes.find_one({"id": quote_id}, {"_id": 0})
    return _serialize_quote(doc)


# ---- Line Items ----


async def _list_line_items(tenant_id: str, quote_id: str, revision_number: int) -> list[dict[str, Any]]:
    cursor = db.quote_line_items.find(
        {"tenant_id": tenant_id, "quote_id": quote_id, "revision_number": int(revision_number)},
        {"_id": 0},
    ).sort("position", 1)
    return [serialize_doc(d) async for d in cursor]


@router.get("/{quote_id}/line-items")
async def list_line_items(quote_id: str, user: dict = Depends(require_permission(Perm.QUOTE_READ))) -> dict:
    quote = await db.quotes.find_one({"id": quote_id, "tenant_id": user["tenant_id"]})
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    items = await _list_line_items(user["tenant_id"], quote_id, int(quote.get("revision_number") or 1))
    return {"items": items, "totals": compute_document_totals(items)}


@router.post("/{quote_id}/line-items", status_code=201)
async def add_line_item(
    quote_id: str,
    payload: LineItemIn,
    user: dict = Depends(require_permission(Perm.QUOTE_WRITE)),
) -> dict:
    quote = await db.quotes.find_one({"id": quote_id, "tenant_id": user["tenant_id"]})
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    if quote.get("status") == "converted":
        raise HTTPException(status_code=400, detail="Cannot edit a converted quote")

    # sent+ quote: bump revision first
    if quote.get("status") not in {"draft"}:
        new_rev = await _create_revision_before_edit(quote, user, reason="line_item_add")
        await db.quotes.update_one({"id": quote_id}, {"$set": {"revision_number": new_rev, "updated_at": utc_now().isoformat()}})
        quote["revision_number"] = new_rev

    revision_number = int(quote.get("revision_number") or 1)
    totals = compute_line_totals(
        quantity=payload.quantity,
        unit_price_cents=payload.unit_price_cents,
        discount_cents=payload.discount_cents,
        tax_cents=payload.tax_cents,
    )
    position = await db.quote_line_items.count_documents(
        {"tenant_id": user["tenant_id"], "quote_id": quote_id, "revision_number": revision_number}
    )
    snapshot = build_manual_snapshot(
        unit_price_cents=payload.unit_price_cents,
        quantity=payload.quantity,
        reason=payload.manual_override_reason,
        actor_user_id=user["id"],
        actor_email=user["email"],
    )
    li = QuoteLineItem(
        tenant_id=user["tenant_id"],
        quote_id=quote_id,
        revision_number=revision_number,
        position=position,
        category=payload.category,
        product_type=payload.product_type,
        description=payload.description,
        sku=payload.sku,
        quantity=payload.quantity,
        unit_of_measure=payload.unit_of_measure,
        width_inches=payload.width_inches,
        height_inches=payload.height_inches,
        depth_inches=payload.depth_inches,
        material_key=payload.material_key,
        unit_price_cents=payload.unit_price_cents,
        discount_cents=totals["discount_cents"],
        tax_cents=totals["tax_cents"],
        line_subtotal_cents=totals["line_subtotal_cents"],
        line_total_cents=totals["line_total_cents"],
        pricing_snapshot=snapshot,
        manual_override_reason=payload.manual_override_reason,
        production_required=payload.production_required,
        notes=payload.notes,
    )
    await db.quote_line_items.insert_one(prepare_for_mongo(li.model_dump()))

    # Recompute + persist quote totals
    quote_totals = await _recompute_quote_totals(user["tenant_id"], quote_id)
    await db.quotes.update_one(
        {"id": quote_id},
        {"$set": {**quote_totals, "updated_at": utc_now().isoformat()}},
    )
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="quote.line_item.added", entity_type="quote", entity_id=quote_id,
        summary=f"Line item added to Q-{quote['number']}",
        diff={"line_item_id": li.id, "unit_price_cents": payload.unit_price_cents,
              "quantity": payload.quantity, "revision": revision_number},
    )
    return serialize_doc(li.model_dump())


@router.patch("/{quote_id}/line-items/{item_id}")
async def update_line_item(
    quote_id: str,
    item_id: str,
    payload: LineItemPatchIn,
    user: dict = Depends(require_permission(Perm.QUOTE_WRITE)),
) -> dict:
    quote = await db.quotes.find_one({"id": quote_id, "tenant_id": user["tenant_id"]})
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    if quote.get("status") == "converted":
        raise HTTPException(status_code=400, detail="Cannot edit a converted quote")

    line = await db.quote_line_items.find_one(
        {"id": item_id, "quote_id": quote_id, "tenant_id": user["tenant_id"]}
    )
    if not line:
        raise HTTPException(status_code=404, detail="Line item not found")

    # sent+ quote: bump revision + roll items forward
    if quote.get("status") not in {"draft"}:
        new_rev = await _create_revision_before_edit(quote, user, reason="line_item_update")
        await db.quotes.update_one({"id": quote_id}, {"$set": {"revision_number": new_rev, "updated_at": utc_now().isoformat()}})
        line = await db.quote_line_items.find_one({"id": item_id})

    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No updates")

    # If the unit price is overridden without a reason, reject.
    if "unit_price_cents" in updates and int(updates["unit_price_cents"]) != int(line.get("unit_price_cents") or 0):
        if not updates.get("manual_override_reason") and not line.get("manual_override_reason"):
            raise HTTPException(status_code=400, detail="Override reason required for manual price change")
        updates["manual_override_actor_user_id"] = user["id"]
        updates["manual_override_actor_email"] = user["email"]
        updates["manual_override_at"] = utc_now().isoformat()

    merged = {**line, **updates}
    totals = compute_line_totals(
        quantity=int(merged.get("quantity") or 1),
        unit_price_cents=int(merged.get("unit_price_cents") or 0),
        discount_cents=int(merged.get("discount_cents") or 0),
        tax_cents=int(merged.get("tax_cents") or 0),
    )
    updates.update(totals)
    updates["updated_at"] = utc_now().isoformat()
    await db.quote_line_items.update_one({"id": item_id}, {"$set": updates})

    quote_totals = await _recompute_quote_totals(user["tenant_id"], quote_id)
    await db.quotes.update_one(
        {"id": quote_id},
        {"$set": {**quote_totals, "updated_at": utc_now().isoformat()}},
    )
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="quote.line_item.updated", entity_type="quote", entity_id=quote_id,
        summary=f"Line item updated on Q-{quote['number']}",
        diff={"line_item_id": item_id, "changes": updates},
    )
    doc = await db.quote_line_items.find_one({"id": item_id}, {"_id": 0})
    return serialize_doc(doc)


@router.delete("/{quote_id}/line-items/{item_id}", status_code=204, response_class=Response)
async def delete_line_item(
    quote_id: str,
    item_id: str,
    user: dict = Depends(require_permission(Perm.QUOTE_WRITE)),
) -> Response:
    quote = await db.quotes.find_one({"id": quote_id, "tenant_id": user["tenant_id"]})
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    if quote.get("status") == "converted":
        raise HTTPException(status_code=400, detail="Cannot edit a converted quote")
    line = await db.quote_line_items.find_one({"id": item_id, "quote_id": quote_id, "tenant_id": user["tenant_id"]})
    if not line:
        raise HTTPException(status_code=404, detail="Line item not found")

    if quote.get("status") not in {"draft"}:
        new_rev = await _create_revision_before_edit(quote, user, reason="line_item_delete")
        await db.quotes.update_one({"id": quote_id}, {"$set": {"revision_number": new_rev, "updated_at": utc_now().isoformat()}})
        line = await db.quote_line_items.find_one({"id": item_id})

    await db.quote_line_items.delete_one({"id": item_id})
    quote_totals = await _recompute_quote_totals(user["tenant_id"], quote_id)
    await db.quotes.update_one({"id": quote_id}, {"$set": {**quote_totals, "updated_at": utc_now().isoformat()}})
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="quote.line_item.removed", entity_type="quote", entity_id=quote_id,
        summary=f"Line item removed from Q-{quote['number']}",
        diff={"line_item_id": item_id},
    )
    return Response(status_code=204)


# ---- Revisions ----


@router.get("/{quote_id}/revisions")
async def get_revisions(quote_id: str, user: dict = Depends(require_permission(Perm.QUOTE_READ))) -> dict:
    quote = await db.quotes.find_one({"id": quote_id, "tenant_id": user["tenant_id"]})
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    revs = await list_revisions(user["tenant_id"], quote_id)
    return {"items": revs, "current_revision": int(quote.get("revision_number") or 1)}


@router.get("/{quote_id}/revisions/{revision_number}")
async def get_one_revision(quote_id: str, revision_number: int, user: dict = Depends(require_permission(Perm.QUOTE_READ))) -> dict:
    quote = await db.quotes.find_one({"id": quote_id, "tenant_id": user["tenant_id"]})
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    rev = await get_revision(user["tenant_id"], quote_id, revision_number)
    if not rev:
        raise HTTPException(status_code=404, detail="Revision not found")
    return rev


# ---- Conversion ----


@router.post("/{quote_id}/convert-to-order")
async def convert(
    quote_id: str,
    payload: ConvertIn = Body(default_factory=ConvertIn),
    user: dict = Depends(require_permission(Perm.QUOTE_CONVERT)),
) -> dict:
    try:
        order, already = await convert_quote_to_order(
            tenant_id=user["tenant_id"],
            quote_id=quote_id,
            actor_user_id=user["id"],
            actor_email=user["email"],
            allow_expired=payload.allow_expired,
            override_reason=payload.override_reason,
        )
    except ValueError as ex:
        code_map = {
            "quote_not_found": (404, "Quote not found"),
            "quote_declined": (400, "Cannot convert a declined quote"),
            "quote_void": (400, "Cannot convert a voided quote"),
            "quote_expired": (400, "Quote has expired"),
            "override_reason_required": (400, "Override reason required for expired conversion"),
            "conversion_race_lost": (409, "Conversion race lost"),
        }
        status, msg = code_map.get(str(ex), (400, str(ex)))
        raise HTTPException(status_code=status, detail=msg)

    if not already:
        await record_audit(
            tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
            action="quote.converted", entity_type="quote", entity_id=quote_id,
            summary=f"Quote converted to Order O-{order.get('number')}",
            diff={"order_id": order.get("id"), "expired_override": payload.allow_expired,
                  "override_reason": payload.override_reason},
        )
    return {"order": order, "already_converted": already}
