"""Shop Operations quote completion helpers.

This module keeps quote customer-facing approval on the existing approval,
public-token, revision, document, and audit foundations.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import serialize_doc, utc_now
from ..services.approvals_signatures_service import record_approval
from ..services.audit import record_audit
from ..services.commerce_totals import compute_pricing_summary
from ..services.order_pricing import compute_document_totals_with_pricing_adjustments
from ..services.portal_tokens import mint_public_action_token


QUOTE_PUBLIC_FIELDS = {
    "id", "number", "customer_id", "job_name", "notes_customer", "expires_at",
    "revision_number", "status", "sent_at", "viewed_at", "approved_at",
    "approved_revision", "approved_source", "declined_at", "declined_reason",
    "converted_order_id", "converted_revision", "converted_at", "created_at",
    "updated_at", "subtotal_cents", "discount_cents", "tax_cents", "total_cents",
}

LINE_PUBLIC_FIELDS = {
    "id", "description", "item_name", "quantity", "unit_of_measure",
    "width_inches", "height_inches", "depth_inches", "material_key",
    "product_type", "sku", "category", "unit_price_cents", "discount_cents",
    "tax_cents", "line_subtotal_cents", "line_total_cents", "notes",
}

INACTIVE_QUOTE_STATUSES = {"converted", "void"}
APPROVABLE_STATUSES = {"sent", "viewed"}


def _now_iso() -> str:
    return utc_now().isoformat()


def _is_expired(quote: dict[str, Any]) -> bool:
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


def _effective_status(quote: dict[str, Any]) -> str:
    status = quote.get("status") or "draft"
    if status in {"sent", "viewed"} and _is_expired(quote):
        return "expired"
    return status


def _customer_safe_quote(quote: dict[str, Any], *, revision_number: Optional[int] = None) -> dict[str, Any]:
    safe = {key: quote.get(key) for key in QUOTE_PUBLIC_FIELDS if key in quote}
    if revision_number is not None:
        safe["revision_number"] = int(revision_number)
    safe["effective_status"] = _effective_status(safe)
    safe["expired"] = _is_expired(safe)
    return serialize_doc(safe)


def _customer_safe_line_item(item: dict[str, Any]) -> dict[str, Any]:
    return serialize_doc({key: item.get(key) for key in LINE_PUBLIC_FIELDS if key in item})


async def get_quote_or_raise(tenant_id: str, quote_id: str) -> dict[str, Any]:
    quote = await db.quotes.find_one({"tenant_id": tenant_id, "id": quote_id}, {"_id": 0})
    if not quote:
        raise ValueError("quote_not_found")
    return quote


async def quote_snapshot(
    *,
    tenant_id: str,
    quote_id: str,
    revision_number: Optional[int] = None,
    customer_safe: bool = False,
    mark_viewed: bool = False,
    actor_user_id: Optional[str] = None,
    actor_email: Optional[str] = None,
    public_token_id: Optional[str] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> dict[str, Any]:
    quote = await get_quote_or_raise(tenant_id, quote_id)
    requested_revision = int(revision_number or quote.get("revision_number") or 1)
    current_revision = int(quote.get("revision_number") or 1)

    if requested_revision == current_revision:
        line_items = [
            serialize_doc(item) async for item in db.quote_line_items.find(
                {"tenant_id": tenant_id, "quote_id": quote_id, "revision_number": current_revision},
                {"_id": 0},
            ).sort("position", 1)
        ]
        quote_doc = quote
    else:
        revision = await db.quote_revisions.find_one(
            {"tenant_id": tenant_id, "quote_id": quote_id, "revision_number": requested_revision},
            {"_id": 0},
        )
        if not revision:
            raise ValueError("quote_revision_not_found")
        line_items = revision.get("line_items") or []
        quote_doc = {
            **quote,
            "job_name": revision.get("job_name", quote.get("job_name")),
            "notes_customer": revision.get("notes_customer", quote.get("notes_customer")),
            "expires_at": revision.get("expires_at", quote.get("expires_at")),
            "revision_number": requested_revision,
            "subtotal_cents": int(revision.get("subtotal_cents") or 0),
            "discount_cents": int(revision.get("discount_cents") or 0),
            "tax_cents": int(revision.get("tax_cents") or 0),
            "total_cents": int(revision.get("total_cents") or 0),
        }

    if mark_viewed and quote.get("status") == "sent" and requested_revision == current_revision:
        now = utc_now()
        await db.quotes.update_one(
            {"tenant_id": tenant_id, "id": quote_id, "status": "sent"},
            {"$set": {"status": "viewed", "viewed_at": now, "updated_at": now.isoformat()}},
        )
        await record_audit(
            tenant_id=tenant_id,
            actor_user_id=(actor_user_id or f"token:{public_token_id}" if public_token_id else "public"),
            actor_email=(actor_email or "public@quote"),
            action="quote.viewed",
            entity_type="quote",
            entity_id=quote_id,
            summary=f"Quote Q-{quote.get('number')} viewed",
            diff={"revision_number": requested_revision, "public_token_id": public_token_id, "ip": ip, "user_agent": user_agent},
        )
        quote_doc = await get_quote_or_raise(tenant_id, quote_id)

    visible_items = [_customer_safe_line_item(item) for item in line_items] if customer_safe else [serialize_doc(item) for item in line_items]
    totals = compute_document_totals_with_pricing_adjustments(line_items)
    return {
        "quote": _customer_safe_quote(quote_doc, revision_number=requested_revision) if customer_safe else serialize_doc(quote_doc),
        "line_items": visible_items,
        "totals": totals,
        "pricing_summary": {} if customer_safe else compute_pricing_summary(line_items),
        "snapshot": {
            "quote_id": quote_id,
            "revision_number": requested_revision,
            "published_revision": requested_revision,
            "customer_safe": customer_safe,
        },
    }


async def create_quote_share_token(
    *,
    tenant_id: str,
    quote_id: str,
    audience_email: Optional[str],
    ttl_hours: int,
    actor_user_id: str,
    actor_email: str,
    ip_issued: Optional[str] = None,
    note: Optional[str] = None,
) -> dict[str, Any]:
    quote = await get_quote_or_raise(tenant_id, quote_id)
    current_revision = int(quote.get("revision_number") or 1)
    raw, token_doc = await mint_public_action_token(
        tenant_id=tenant_id,
        action="quote_view",
        parent_type="quote",
        parent_id=quote_id,
        parent_version=current_revision,
        audience_email=audience_email,
        ttl_hours=ttl_hours,
        single_use=False,
        issued_by=actor_user_id,
        ip_issued=ip_issued,
    )
    now = utc_now()
    updates: dict[str, Any] = {"updated_at": now.isoformat(), "last_quote_share_token_id": token_doc["id"]}
    if quote.get("status") == "draft":
        updates.update({"status": "sent", "sent_at": now})
    await db.quotes.update_one({"tenant_id": tenant_id, "id": quote_id}, {"$set": updates})
    await record_audit(
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        action="quote.share_token_mint",
        entity_type="quote",
        entity_id=quote_id,
        summary=f"Quote Q-{quote.get('number')} share link created",
        diff={
            "token_id": token_doc["id"],
            "audience_email": audience_email,
            "revision_number": current_revision,
            "delivery_status": "manual_link_ready",
            "delivery_error": "Email/SMS delivery is not configured for quote share links; copy the link manually.",
            "note": note,
        },
    )
    record = dict(token_doc)
    record.pop("token_hash", None)
    return {
        "token": raw,
        "record": serialize_doc(record),
        "public_url_path": f"/p/quotes/{quote_id}?t={raw}",
        "delivery_status": "manual_link_ready",
        "delivery_error": "Email/SMS delivery is not configured for quote share links; copy the link manually.",
    }


async def list_quote_share_tokens(*, tenant_id: str, quote_id: str) -> dict[str, Any]:
    await get_quote_or_raise(tenant_id, quote_id)
    cursor = db.public_action_tokens.find(
        {"tenant_id": tenant_id, "action": "quote_view", "parent_type": "quote", "parent_id": quote_id},
        {"_id": 0, "token_hash": 0},
    ).sort("created_at", -1)
    return {"items": [serialize_doc(token) async for token in cursor]}


async def revoke_or_expire_quote_token(
    *,
    tenant_id: str,
    token_id: str,
    mode: str,
    actor_user_id: str,
    actor_email: str,
) -> bool:
    token = await db.public_action_tokens.find_one(
        {"tenant_id": tenant_id, "id": token_id, "action": "quote_view", "parent_type": "quote"},
        {"_id": 0},
    )
    if not token:
        return False
    now = _now_iso()
    updates = {"updated_at": now}
    action = "quote.share_token_revoke"
    if mode == "expire":
        updates["expires_at"] = now
        action = "quote.share_token_expire"
    else:
        updates["revoked"] = True
    await db.public_action_tokens.update_one({"tenant_id": tenant_id, "id": token_id}, {"$set": updates})
    await record_audit(
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        action=action,
        entity_type="quote",
        entity_id=token.get("parent_id"),
        summary="Quote share link revoked" if mode == "revoke" else "Quote share link expired",
        diff={"token_id": token_id},
    )
    return True


async def decide_quote(
    *,
    tenant_id: str,
    quote_id: str,
    action: str,
    actor_type: str,
    actor_ref: str,
    actor_display: Optional[str],
    source: str,
    reason: Optional[str] = None,
    comment: Optional[str] = None,
    parent_version: Optional[int] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> dict[str, Any]:
    quote = await get_quote_or_raise(tenant_id, quote_id)
    current_revision = int(quote.get("revision_number") or 1)
    target_revision = int(parent_version or current_revision)
    if target_revision != current_revision:
        raise ValueError("stale_quote_revision")
    effective_status = _effective_status(quote)
    if effective_status == "expired":
        raise ValueError("quote_expired")
    if quote.get("status") in INACTIVE_QUOTE_STATUSES:
        raise ValueError("quote_inactive")
    if action not in {"approve", "decline"}:
        raise ValueError("invalid_action")
    if action == "decline" and not (reason or "").strip():
        raise ValueError("reason_required")
    if quote.get("status") not in APPROVABLE_STATUSES and quote.get("status") != action + "d":
        raise ValueError(f"invalid_transition:{quote.get('status')}")

    await db.approvals.update_many(
        {
            "tenant_id": tenant_id,
            "parent_type": "quote_revision",
            "parent_id": quote_id,
            "parent_version": current_revision,
            "status": "current",
        },
        {"$set": {"status": "superseded", "superseded_at": _now_iso(), "superseded_reason": "New quote decision recorded"}},
    )
    approval = await record_approval(
        tenant_id=tenant_id,
        parent_type="quote_revision",
        parent_id=quote_id,
        parent_version=current_revision,
        action=action,
        actor_type=actor_type,
        actor_ref=actor_ref,
        actor_display=actor_display,
        reason=reason,
        ip=ip,
        user_agent=user_agent,
        snapshot={
            "quote_id": quote_id,
            "customer_id": quote.get("customer_id"),
            "job_name": quote.get("job_name"),
            "quote_number": quote.get("number"),
            "revision_number": current_revision,
            "status_before": quote.get("status"),
            "total_cents": quote.get("total_cents"),
            "source": source,
            "customer_comment": comment,
        },
    )
    now = utc_now()
    updates: dict[str, Any] = {"status": "approved" if action == "approve" else "declined", "updated_at": now.isoformat()}
    if action == "approve":
        updates.update({
            "approved_at": now,
            "approved_revision": current_revision,
            "approved_actor_user_id": actor_ref,
            "approved_source": source,
            "approved_approval_id": approval.get("id"),
            "customer_approval_comment": comment,
        })
    else:
        updates.update({
            "declined_at": now,
            "declined_reason": reason,
            "declined_approval_id": approval.get("id"),
            "customer_decline_comment": comment,
        })
    await db.quotes.update_one({"tenant_id": tenant_id, "id": quote_id}, {"$set": updates})
    await record_audit(
        tenant_id=tenant_id,
        actor_user_id=actor_ref,
        actor_email=actor_display or actor_ref,
        action=f"quote.{updates['status']}",
        entity_type="quote",
        entity_id=quote_id,
        summary=f"Quote Q-{quote.get('number')} {updates['status']}",
        diff={"approval_id": approval.get("id"), "reason": reason, "comment": comment, "source": source},
    )
    refreshed = await get_quote_or_raise(tenant_id, quote_id)
    return {"quote": serialize_doc(refreshed), "approval": approval}


async def linked_quote_assets(*, tenant_id: str, quote_id: str) -> dict[str, Any]:
    quote = await get_quote_or_raise(tenant_id, quote_id)
    files = [
        serialize_doc(file) async for file in db.files.find(
            {
                "tenant_id": tenant_id,
                "id": {
                    "$in": [
                        attachment["file_id"] async for attachment in db.attachments.find(
                            {"tenant_id": tenant_id, "parent_type": "quote", "parent_id": quote_id},
                            {"_id": 0, "file_id": 1},
                        )
                    ]
                },
                "archived": {"$ne": True},
            },
            {"_id": 0},
        )
    ]
    documents = [
        serialize_doc(doc) async for doc in db.documents.find(
            {
                "tenant_id": tenant_id,
                "id": {
                    "$in": [
                        link["document_id"] async for link in db.document_links.find(
                            {"tenant_id": tenant_id, "entity_type": "quote", "entity_id": quote_id},
                            {"_id": 0, "document_id": 1},
                        )
                    ]
                },
                "archived": {"$ne": True},
            },
            {"_id": 0},
        )
    ]
    proofs = [
        serialize_doc(proof) async for proof in db.proofs.find(
            {
                "tenant_id": tenant_id,
                "$or": [
                    {"quote_id": quote_id},
                    {"parent_type": "quote", "parent_id": quote_id},
                ],
                "archived": {"$ne": True},
            },
            {"_id": 0},
        ).sort("created_at", -1)
    ]
    return {
        "quote_id": quote_id,
        "customer_id": quote.get("customer_id"),
        "files": files,
        "documents": documents,
        "proofs": proofs,
    }


async def quote_timeline(*, tenant_id: str, quote_id: str) -> dict[str, Any]:
    quote = await get_quote_or_raise(tenant_id, quote_id)
    events: list[dict[str, Any]] = []

    def add(kind: str, label: str, at: Any, source: str, metadata: Optional[dict[str, Any]] = None) -> None:
        if at:
            events.append({"kind": kind, "label": label, "at": serialize_doc({"v": at})["v"], "source": source, "metadata": metadata or {}})

    add("created", "Quote created", quote.get("created_at"), "quote", {"number": quote.get("number")})
    add("sent", "Quote sent", quote.get("sent_at"), "quote")
    add("viewed", "Quote viewed", quote.get("viewed_at"), "quote")
    add("approved", "Quote approved", quote.get("approved_at"), "quote", {"approval_id": quote.get("approved_approval_id")})
    add("declined", "Quote declined", quote.get("declined_at"), "quote", {"reason": quote.get("declined_reason")})
    if _effective_status(quote) == "expired":
        add("expired", "Quote expired", quote.get("expires_at"), "quote")
    add("converted", "Quote converted to order", quote.get("converted_at"), "quote", {"order_id": quote.get("converted_order_id")})

    async for rev in db.quote_revisions.find({"tenant_id": tenant_id, "quote_id": quote_id}, {"_id": 0}).sort("revision_number", 1):
        add("revised", f"Revision #{rev.get('revision_number')} captured", rev.get("created_at"), "quote_revision", {"reason": rev.get("reason")})
    async for approval in db.approvals.find({"tenant_id": tenant_id, "parent_type": "quote_revision", "parent_id": quote_id}, {"_id": 0}).sort("created_at", 1):
        add(approval.get("action") or "approval", f"Approval {approval.get('action')}", approval.get("created_at"), "approval", {
            "approval_id": approval.get("id"),
            "actor": approval.get("actor_display") or approval.get("actor_ref"),
            "reason": approval.get("reason"),
            "status": approval.get("status"),
        })
    async for token in db.public_action_tokens.find({"tenant_id": tenant_id, "action": "quote_view", "parent_type": "quote", "parent_id": quote_id}, {"_id": 0, "token_hash": 0}).sort("created_at", 1):
        add("sent", "Quote share link created", token.get("created_at"), "public_action_token", {
            "token_id": token.get("id"),
            "audience_email": token.get("audience_email"),
            "revoked": token.get("revoked"),
            "expires_at": serialize_doc({"v": token.get("expires_at")}).get("v"),
        })
        if token.get("revoked"):
            add("revoked", "Quote share link revoked", token.get("updated_at"), "public_action_token", {"token_id": token.get("id")})
    async for audit in db.audit_logs.find({"tenant_id": tenant_id, "entity_type": "quote", "entity_id": quote_id}, {"_id": 0}).sort("created_at", 1):
        add("audit", audit.get("summary") or audit.get("action"), audit.get("created_at"), "audit", {
            "action": audit.get("action"),
            "actor": audit.get("actor_email"),
        })

    deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for event in events:
        deduped[(event["kind"], event["label"], event["at"])] = event
    ordered = sorted(deduped.values(), key=lambda item: item.get("at") or "")
    return {"items": ordered}
