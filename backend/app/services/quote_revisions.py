"""EC3 — Quote revision service.

A revision captures the full commercial state of a Quote at a moment in time.
Editing a Quote that has already been sent to a customer creates a new
revision before the customer-visible commercial terms are replaced.

Revisions are stored in the `quote_revisions` collection with a unique
`(tenant_id, quote_id, revision_number)` index.
"""
from __future__ import annotations

from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc
from ..models.quote_revision import QuoteRevision


async def _load_line_items(tenant_id: str, quote_id: str, revision_number: int) -> list[dict[str, Any]]:
    """Load current line items for a quote scoped to a given revision number."""
    cursor = db.quote_line_items.find(
        {"tenant_id": tenant_id, "quote_id": quote_id, "revision_number": revision_number},
        {"_id": 0},
    ).sort("position", 1)
    return [serialize_doc(d) async for d in cursor]


async def snapshot_current(
    *,
    tenant_id: str,
    quote_doc: dict[str, Any],
    actor_user_id: str,
    actor_email: str,
    reason: Optional[str] = None,
) -> QuoteRevision:
    """Persist an immutable snapshot of the quote at its CURRENT revision number.

    The caller must set the quote's new revision_number afterwards.
    """
    revision_number = int(quote_doc.get("revision_number") or 1)
    items = await _load_line_items(tenant_id, quote_doc["id"], revision_number)
    rev = QuoteRevision(
        tenant_id=tenant_id,
        quote_id=quote_doc["id"],
        revision_number=revision_number,
        job_name=quote_doc.get("job_name", ""),
        notes_internal=quote_doc.get("notes_internal") or quote_doc.get("notes"),
        notes_customer=quote_doc.get("notes_customer"),
        expires_at=quote_doc.get("expires_at"),
        line_items=items,
        subtotal_cents=int(quote_doc.get("subtotal_cents") or 0),
        discount_cents=int(quote_doc.get("discount_cents") or 0),
        tax_cents=int(quote_doc.get("tax_cents") or 0),
        total_cents=int(quote_doc.get("total_cents") or 0),
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        reason=reason,
    )
    await db.quote_revisions.insert_one(prepare_for_mongo(rev.model_dump()))
    return rev


async def list_revisions(tenant_id: str, quote_id: str) -> list[dict[str, Any]]:
    cursor = db.quote_revisions.find(
        {"tenant_id": tenant_id, "quote_id": quote_id}, {"_id": 0}
    ).sort("revision_number", -1)
    return [serialize_doc(d) async for d in cursor]


async def get_revision(tenant_id: str, quote_id: str, revision_number: int) -> Optional[dict[str, Any]]:
    doc = await db.quote_revisions.find_one(
        {"tenant_id": tenant_id, "quote_id": quote_id, "revision_number": int(revision_number)},
        {"_id": 0},
    )
    return serialize_doc(doc) if doc else None
