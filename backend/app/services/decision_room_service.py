"""EC10 Phase 10D — Customer Decision Room service (internal authoring only).

STAFF-ONLY. No function in this file resolves a public token, accepts a
customer selection, records a customer comment/question/change-request, or
writes to any Quote/Order/Order Item. All of that is explicitly deferred to
Phase 10E (customer access) / 10F (decision-to-order integration).

Reuses (never duplicates): Customer/Quote/Order/OrderItem/IntakeSubmission
existence checks, the existing `/files` object-storage records, `Proof`,
`VisualMarkup`, `PricingSnapshotRecord` (EC9, immutable — never recalculated
or mutated here), `record_audit`, and `next_number`-free UUID ids (a
DecisionRoom has no sequential "number" requirement in this phase).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.decision_room import DecisionOption, DecisionRoom, DecisionRoomVersion
from ..services.audit import record_audit

# ---- Status lifecycle -------------------------------------------------
# "published" is reachable only via `publish_room()` (a dedicated action
# that also freezes a `DecisionRoomVersion`), never via this generic map —
# see `publish_room()` below.
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"ready", "archived"},
    "ready": {"draft", "archived"},
    "published": {"closed", "expired", "archived"},
    "expired": {"archived"},
    "closed": {"archived"},
    "archived": {"draft"},
}

_LOCKED_STATUSES = {"expired", "closed", "archived"}
_VALID_BADGES = {"recommended", "best_value", "premium", "budget", "fastest", "custom", "none"}
_VALID_PRICE_MODES = {"show_price", "hide_price", "contact_for_price"}

# Fields that must never reach a customer-facing response.
_INTERNAL_ROOM_FIELDS = (
    "internal_name", "created_by_user_id", "updated_by_user_id",
    "published_by_user_id", "metadata", "public_token_id",
)
_INTERNAL_OPTION_FIELDS = (
    "internal_name", "internal_notes", "created_by_user_id", "updated_by_user_id",
    "pricing_snapshot_id", "suggested_price_cents", "manual_price_cents",
    "selected_price_source", "quote_line_item_id", "order_item_id", "proof_id",
)


class DecisionRoomError(ValueError):
    def __init__(self, code: str, message: Optional[str] = None, details: Optional[list[str]] = None):
        super().__init__(message or code)
        self.code = code
        self.details = details or []


def _now_iso() -> str:
    return utc_now().isoformat()


# ---- Cross-tenant reference validation ---------------------------------

async def _validate_customer(tenant_id: str, customer_id: Optional[str]) -> None:
    if not customer_id:
        return
    doc = await db.customers.find_one({"id": customer_id, "tenant_id": tenant_id}, {"_id": 0, "id": 1})
    if not doc:
        raise DecisionRoomError("customer_not_found", "Customer not found for this tenant")


async def _validate_intake(tenant_id: str, intake_id: Optional[str]) -> None:
    if not intake_id:
        return
    doc = await db.intake_submissions.find_one({"id": intake_id, "tenant_id": tenant_id}, {"_id": 0, "id": 1})
    if not doc:
        raise DecisionRoomError("intake_not_found", "Intake submission not found for this tenant")


async def _validate_quote(tenant_id: str, quote_id: Optional[str]) -> None:
    if not quote_id:
        return
    doc = await db.quotes.find_one({"id": quote_id, "tenant_id": tenant_id}, {"_id": 0, "id": 1})
    if not doc:
        raise DecisionRoomError("quote_not_found", "Quote not found for this tenant")


async def _validate_order(tenant_id: str, order_id: Optional[str]) -> None:
    if not order_id:
        return
    doc = await db.orders.find_one({"id": order_id, "tenant_id": tenant_id}, {"_id": 0, "id": 1})
    if not doc:
        raise DecisionRoomError("order_not_found", "Order not found for this tenant")


async def _validate_order_item(tenant_id: str, order_item_id: Optional[str], order_id: Optional[str]) -> None:
    if not order_item_id:
        return
    doc = await db.order_items.find_one({"id": order_item_id, "tenant_id": tenant_id}, {"_id": 0, "id": 1, "order_id": 1})
    if not doc:
        raise DecisionRoomError("order_item_not_found", "Order Item not found for this tenant")
    if order_id and doc.get("order_id") != order_id:
        raise DecisionRoomError("order_item_order_mismatch", "order_item_id does not belong to order_id")


async def _validate_quote_line_item(tenant_id: str, quote_line_item_id: Optional[str]) -> None:
    if not quote_line_item_id:
        return
    doc = await db.quote_line_items.find_one({"id": quote_line_item_id, "tenant_id": tenant_id}, {"_id": 0, "id": 1})
    if not doc:
        raise DecisionRoomError("quote_line_item_not_found", "Quote line item not found for this tenant")


async def _validate_file_ids(tenant_id: str, file_ids: list[str]) -> None:
    if not file_ids:
        return
    found = {
        d["id"] async for d in db.files.find(
            {"id": {"$in": file_ids}, "tenant_id": tenant_id, "archived": {"$ne": True}}, {"_id": 0, "id": 1},
        )
    }
    missing = [f for f in file_ids if f not in found]
    if missing:
        raise DecisionRoomError("file_not_found", f"File(s) not found for this tenant: {missing}")


async def _validate_proof(tenant_id: str, proof_id: Optional[str]) -> None:
    if not proof_id:
        return
    doc = await db.proofs.find_one({"id": proof_id, "tenant_id": tenant_id}, {"_id": 0, "id": 1})
    if not doc:
        raise DecisionRoomError("proof_not_found", "Proof not found for this tenant")


async def _validate_visual_markup(tenant_id: str, visual_markup_id: Optional[str]) -> None:
    if not visual_markup_id:
        return
    doc = await db.visual_markups.find_one({"id": visual_markup_id, "tenant_id": tenant_id}, {"_id": 0, "id": 1})
    if not doc:
        raise DecisionRoomError("visual_markup_not_found", "Visual markup not found for this tenant")


async def _get_pricing_snapshot(tenant_id: str, pricing_snapshot_id: Optional[str]) -> Optional[dict]:
    if not pricing_snapshot_id:
        return None
    doc = await db.pricing_snapshot_records.find_one({"id": pricing_snapshot_id, "tenant_id": tenant_id}, {"_id": 0})
    if not doc:
        raise DecisionRoomError("pricing_snapshot_not_found", "Pricing snapshot not found for this tenant")
    return doc


async def _validate_option_references(tenant_id: str, option: dict[str, Any]) -> None:
    await _validate_file_ids(tenant_id, option.get("file_ids") or [])
    for key in ("rendered_preview_file_id", "thumbnail_file_id"):
        fid = option.get(key)
        if fid:
            await _validate_file_ids(tenant_id, [fid])
    await _validate_proof(tenant_id, option.get("proof_id"))
    await _validate_visual_markup(tenant_id, option.get("visual_markup_id"))
    await _validate_quote_line_item(tenant_id, option.get("quote_line_item_id"))
    await _validate_order_item(tenant_id, option.get("order_item_id"), None)
    if option.get("pricing_snapshot_id"):
        await _get_pricing_snapshot(tenant_id, option["pricing_snapshot_id"])
    if option.get("badge_type") and option["badge_type"] not in _VALID_BADGES:
        raise DecisionRoomError("invalid_badge_type", f"Unsupported badge_type: {option['badge_type']!r}")
    if option.get("price_display_mode") and option["price_display_mode"] not in _VALID_PRICE_MODES:
        raise DecisionRoomError("invalid_price_display_mode", f"Unsupported price_display_mode: {option['price_display_mode']!r}")


def _compute_display_price(option: dict[str, Any]) -> Optional[int]:
    source = option.get("selected_price_source", "manual")
    if source == "snapshot":
        return option.get("suggested_price_cents")
    return option.get("manual_price_cents")


def _sanitize_custom_badge_text(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    cleaned = "".join(ch for ch in text if ch.isprintable()).strip()
    return cleaned[:60] or None


async def _get_room(tenant_id: str, room_id: str) -> dict:
    doc = await db.decision_rooms.find_one({"id": room_id, "tenant_id": tenant_id})
    if not doc:
        raise DecisionRoomError("room_not_found", "Decision Room not found")
    return doc


def _assert_editable(room: dict) -> None:
    if room.get("status") in _LOCKED_STATUSES:
        raise DecisionRoomError("room_locked", f"Decision Room cannot be edited while '{room.get('status')}'")


def _find_option(room: dict, option_id: str) -> dict:
    option = next((o for o in (room.get("options") or []) if o.get("id") == option_id), None)
    if not option:
        raise DecisionRoomError("option_not_found", "Decision option not found")
    return option


async def _persist_room_mutation(
    tenant_id: str, room: dict, *, options: Optional[list[dict]] = None,
    extra_fields: Optional[dict[str, Any]] = None, actor_user_id: str,
) -> None:
    """Shared write path for every option-level mutation: bumps
    `current_version` (without creating a frozen version row) if the room is
    already published, per §9's "changes after publication create a new
    version" — here interpreted as: the draft's version counter advances so
    `current_version != published_version` signals unpublished changes."""
    now = _now_iso()
    updates: dict[str, Any] = {"updated_at": now, "updated_by_user_id": actor_user_id}
    if options is not None:
        updates["options"] = options
    if extra_fields:
        updates.update(extra_fields)
    if room.get("status") == "published":
        updates["current_version"] = int(room.get("current_version", 0)) + 1
    await db.decision_rooms.update_one({"id": room["id"], "tenant_id": tenant_id}, {"$set": updates})


# ---- Room CRUD -----------------------------------------------------------

async def create_room(*, tenant_id: str, payload: dict[str, Any], actor_user_id: str, actor_email: str) -> dict:
    title = (payload.get("title") or "").strip()
    if not title:
        raise DecisionRoomError("title_required", "A Decision Room title is required")

    await _validate_customer(tenant_id, payload.get("customer_id"))
    await _validate_intake(tenant_id, payload.get("intake_id"))
    await _validate_quote(tenant_id, payload.get("quote_id"))
    await _validate_order(tenant_id, payload.get("order_id"))
    await _validate_order_item(tenant_id, payload.get("order_item_id"), payload.get("order_id"))

    _reserved = {
        "id", "tenant_id", "status", "options", "current_version", "published_version",
        "created_at", "updated_at", "created_by_user_id", "updated_by_user_id",
        "published_by_user_id", "published_at", "archived_at",
    }
    doc = DecisionRoom(
        tenant_id=tenant_id,
        created_by_user_id=actor_user_id, updated_by_user_id=actor_user_id,
        **{k: v for k, v in payload.items() if k not in _reserved and v is not None},
    ).model_dump()
    await db.decision_rooms.insert_one(prepare_for_mongo(dict(doc)))
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="decision_room.created", entity_type="decision_room", entity_id=doc["id"],
        summary=f"Decision Room '{title}' created",
        diff={"customer_id": doc.get("customer_id"), "quote_id": doc.get("quote_id"),
              "order_id": doc.get("order_id"), "intake_id": doc.get("intake_id")},
    )
    doc.pop("_id", None)
    return serialize_doc(doc)


async def list_rooms(
    *, tenant_id: str, status: Optional[list[str]] = None, customer_id: Optional[str] = None,
    quote_id: Optional[str] = None, order_id: Optional[str] = None, intake_id: Optional[str] = None,
) -> list[dict]:
    q: dict[str, Any] = {"tenant_id": tenant_id}
    if status: q["status"] = {"$in": status}
    if customer_id: q["customer_id"] = customer_id
    if quote_id: q["quote_id"] = quote_id
    if order_id: q["order_id"] = order_id
    if intake_id: q["intake_id"] = intake_id
    cur = db.decision_rooms.find(q, {"_id": 0}).sort("created_at", -1)
    return [serialize_doc(d) async for d in cur]


async def get_room(*, tenant_id: str, room_id: str) -> dict:
    doc = await _get_room(tenant_id, room_id)
    doc.pop("_id", None)
    return serialize_doc(doc)


async def update_room(*, tenant_id: str, room_id: str, changes: dict[str, Any], actor_user_id: str, actor_email: str) -> dict:
    room = await _get_room(tenant_id, room_id)
    _assert_editable(room)

    _reserved = {
        "id", "tenant_id", "status", "options", "current_version", "published_version",
        "created_at", "updated_at", "created_by_user_id", "updated_by_user_id",
        "published_by_user_id", "published_at", "archived_at",
    }
    changes = {k: v for k, v in changes.items() if k not in _reserved and v is not None}
    if "title" in changes and not changes["title"].strip():
        raise DecisionRoomError("title_required", "Decision Room title cannot be empty")
    if not changes:
        room.pop("_id", None)
        return serialize_doc(room)

    await _validate_customer(tenant_id, changes.get("customer_id"))
    await _validate_intake(tenant_id, changes.get("intake_id"))
    await _validate_quote(tenant_id, changes.get("quote_id"))
    await _validate_order(tenant_id, changes.get("order_id"))
    await _validate_order_item(tenant_id, changes.get("order_item_id"), changes.get("order_id") or room.get("order_id"))

    await _persist_room_mutation(tenant_id, room, extra_fields=changes, actor_user_id=actor_user_id)
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="decision_room.updated", entity_type="decision_room", entity_id=room_id,
        summary="Decision Room updated", diff={"fields": list(changes.keys())},
    )
    return await get_room(tenant_id=tenant_id, room_id=room_id)


# ---- Option authoring -----------------------------------------------------

async def _clear_recommended_on_others(options: list[dict], keep_option_id: str) -> list[dict]:
    """Enforces §6: at most one Recommended option per room."""
    out = []
    for o in options:
        if o.get("id") != keep_option_id and o.get("badge_type") == "recommended":
            o = {**o, "badge_type": "none"}
        out.append(o)
    return out


async def add_option(*, tenant_id: str, room_id: str, option_in: dict[str, Any], actor_user_id: str, actor_email: str) -> dict:
    room = await _get_room(tenant_id, room_id)
    _assert_editable(room)
    await _validate_option_references(tenant_id, option_in)

    option_in = {**option_in, "custom_badge_text": _sanitize_custom_badge_text(option_in.get("custom_badge_text"))}
    now = _now_iso()
    option = DecisionOption(
        **option_in, display_order=len(room.get("options") or []),
        created_by_user_id=actor_user_id, updated_by_user_id=actor_user_id,
        created_at=now, updated_at=now,
    ).model_dump()
    option["selected_display_price_cents"] = _compute_display_price(option)

    options = list(room.get("options") or [])
    if option.get("badge_type") == "recommended":
        options = await _clear_recommended_on_others(options, option["id"])
    options.append(option)

    await _persist_room_mutation(tenant_id, room, options=options, actor_user_id=actor_user_id)
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="decision_room.option_added", entity_type="decision_room", entity_id=room_id,
        summary="Decision option added", diff={"option_id": option["id"], "badge_type": option.get("badge_type")},
    )
    return await get_room(tenant_id=tenant_id, room_id=room_id)


async def update_option(
    *, tenant_id: str, room_id: str, option_id: str, changes: dict[str, Any], actor_user_id: str, actor_email: str,
) -> dict:
    room = await _get_room(tenant_id, room_id)
    _assert_editable(room)
    options = list(room.get("options") or [])
    existing = _find_option(room, option_id)

    _reserved = {"id", "created_by_user_id", "created_at", "selected_display_price_cents", "display_order"}
    changes = {k: v for k, v in changes.items() if k not in _reserved and v is not None}
    if "custom_badge_text" in changes:
        changes["custom_badge_text"] = _sanitize_custom_badge_text(changes["custom_badge_text"])
    merged = {**existing, **changes}
    await _validate_option_references(tenant_id, merged)
    merged["selected_display_price_cents"] = _compute_display_price(merged)
    merged["updated_by_user_id"] = actor_user_id
    merged["updated_at"] = _now_iso()
    DecisionOption(**merged)  # validate merged shape before writing

    if merged.get("badge_type") == "recommended":
        options = await _clear_recommended_on_others(options, option_id)
    new_options = [merged if o.get("id") == option_id else o for o in options]

    await _persist_room_mutation(tenant_id, room, options=new_options, actor_user_id=actor_user_id)
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="decision_room.option_updated", entity_type="decision_room", entity_id=room_id,
        summary="Decision option updated", diff={"option_id": option_id, "fields": list(changes.keys())},
    )
    return await get_room(tenant_id=tenant_id, room_id=room_id)


async def duplicate_option(*, tenant_id: str, room_id: str, option_id: str, actor_user_id: str, actor_email: str) -> dict:
    room = await _get_room(tenant_id, room_id)
    _assert_editable(room)
    options = list(room.get("options") or [])
    source = _find_option(room, option_id)

    now = _now_iso()
    _dup_excluded = {"id", "display_order", "created_at", "updated_at", "created_by_user_id", "updated_by_user_id"}
    dup_payload = {k: v for k, v in source.items() if k not in _dup_excluded}
    # Never inherit exclusivity-sensitive or lineage-sensitive state (§11).
    dup_payload["badge_type"] = "none" if source.get("badge_type") == "recommended" else source.get("badge_type", "none")
    dup = DecisionOption(
        **dup_payload, display_order=len(options),
        created_by_user_id=actor_user_id, updated_by_user_id=actor_user_id, created_at=now, updated_at=now,
    ).model_dump()
    dup["selected_display_price_cents"] = _compute_display_price(dup)
    options.append(dup)

    await _persist_room_mutation(tenant_id, room, options=options, actor_user_id=actor_user_id)
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="decision_room.option_duplicated", entity_type="decision_room", entity_id=room_id,
        summary="Decision option duplicated", diff={"source_option_id": option_id, "new_option_id": dup["id"]},
    )
    return await get_room(tenant_id=tenant_id, room_id=room_id)


async def reorder_options(
    *, tenant_id: str, room_id: str, ordered_option_ids: list[str], actor_user_id: str, actor_email: str,
) -> dict:
    room = await _get_room(tenant_id, room_id)
    _assert_editable(room)
    options = room.get("options") or []
    by_id = {o.get("id"): o for o in options}
    if set(ordered_option_ids) != set(by_id.keys()):
        raise DecisionRoomError("reorder_mismatch", "ordered_option_ids must contain exactly the current option ids")

    now = _now_iso()
    reordered = []
    for idx, oid in enumerate(ordered_option_ids):
        o = {**by_id[oid], "display_order": idx, "updated_at": now, "updated_by_user_id": actor_user_id}
        reordered.append(o)

    await _persist_room_mutation(tenant_id, room, options=reordered, actor_user_id=actor_user_id)
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="decision_room.options_reordered", entity_type="decision_room", entity_id=room_id,
        summary="Decision options reordered", diff={"order": ordered_option_ids},
    )
    return await get_room(tenant_id=tenant_id, room_id=room_id)


async def _set_option_active(
    *, tenant_id: str, room_id: str, option_id: str, active: bool, actor_user_id: str, actor_email: str,
) -> dict:
    room = await _get_room(tenant_id, room_id)
    _assert_editable(room)
    options = room.get("options") or []
    _find_option(room, option_id)
    now = _now_iso()
    new_options = [
        {**o, "active": active, "updated_at": now, "updated_by_user_id": actor_user_id} if o.get("id") == option_id else o
        for o in options
    ]
    await _persist_room_mutation(tenant_id, room, options=new_options, actor_user_id=actor_user_id)
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="decision_room.option_archived" if not active else "decision_room.option_restored",
        entity_type="decision_room", entity_id=room_id,
        summary=f"Decision option {'archived' if not active else 'restored'}", diff={"option_id": option_id},
    )
    return await get_room(tenant_id=tenant_id, room_id=room_id)


async def archive_option(*, tenant_id: str, room_id: str, option_id: str, actor_user_id: str, actor_email: str) -> dict:
    return await _set_option_active(tenant_id=tenant_id, room_id=room_id, option_id=option_id, active=False,
                                     actor_user_id=actor_user_id, actor_email=actor_email)


async def restore_option(*, tenant_id: str, room_id: str, option_id: str, actor_user_id: str, actor_email: str) -> dict:
    return await _set_option_active(tenant_id=tenant_id, room_id=room_id, option_id=option_id, active=True,
                                     actor_user_id=actor_user_id, actor_email=actor_email)


# ---- Media + pricing snapshot attach/detach ------------------------------

async def attach_media(
    *, tenant_id: str, room_id: str, option_id: str, fields: dict[str, Any], actor_user_id: str, actor_email: str,
) -> dict:
    """`fields` may contain any of: file_ids, proof_id, visual_markup_id,
    rendered_preview_file_id, thumbnail_file_id."""
    room = await _get_room(tenant_id, room_id)
    _assert_editable(room)
    option = _find_option(room, option_id)
    merged = {**option, **fields}
    await _validate_option_references(tenant_id, merged)
    merged["updated_by_user_id"] = actor_user_id
    merged["updated_at"] = _now_iso()

    new_options = [merged if o.get("id") == option_id else o for o in (room.get("options") or [])]
    await _persist_room_mutation(tenant_id, room, options=new_options, actor_user_id=actor_user_id)
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="decision_room.option_media_attached", entity_type="decision_room", entity_id=room_id,
        summary="Media attached to decision option", diff={"option_id": option_id, "fields": list(fields.keys())},
    )
    return await get_room(tenant_id=tenant_id, room_id=room_id)


async def detach_media(
    *, tenant_id: str, room_id: str, option_id: str, field_names: list[str], actor_user_id: str, actor_email: str,
) -> dict:
    room = await _get_room(tenant_id, room_id)
    _assert_editable(room)
    option = _find_option(room, option_id)
    allowed = {"file_ids", "proof_id", "visual_markup_id", "rendered_preview_file_id", "thumbnail_file_id"}
    clears: dict[str, Any] = {}
    for name in field_names:
        if name not in allowed:
            continue
        clears[name] = [] if name == "file_ids" else None
    merged = {**option, **clears, "updated_by_user_id": actor_user_id, "updated_at": _now_iso()}

    new_options = [merged if o.get("id") == option_id else o for o in (room.get("options") or [])]
    await _persist_room_mutation(tenant_id, room, options=new_options, actor_user_id=actor_user_id)
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="decision_room.option_media_detached", entity_type="decision_room", entity_id=room_id,
        summary="Media detached from decision option", diff={"option_id": option_id, "fields": field_names},
    )
    return await get_room(tenant_id=tenant_id, room_id=room_id)


async def attach_pricing_snapshot(
    *, tenant_id: str, room_id: str, option_id: str, pricing_snapshot_id: str, actor_user_id: str, actor_email: str,
) -> dict:
    room = await _get_room(tenant_id, room_id)
    _assert_editable(room)
    option = _find_option(room, option_id)
    snapshot = await _get_pricing_snapshot(tenant_id, pricing_snapshot_id)

    merged = {
        **option,
        "pricing_snapshot_id": pricing_snapshot_id,
        # Copy the frozen numeric value only — the snapshot record itself is
        # never mutated and remains the sole source of truth for "why".
        "suggested_price_cents": snapshot.get("selected_final_price_cents"),
        "updated_by_user_id": actor_user_id, "updated_at": _now_iso(),
    }
    merged["selected_display_price_cents"] = _compute_display_price(merged)

    new_options = [merged if o.get("id") == option_id else o for o in (room.get("options") or [])]
    await _persist_room_mutation(tenant_id, room, options=new_options, actor_user_id=actor_user_id)
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="decision_room.option_pricing_snapshot_attached", entity_type="decision_room", entity_id=room_id,
        summary="Pricing snapshot attached to decision option",
        diff={"option_id": option_id, "pricing_snapshot_id": pricing_snapshot_id},
    )
    return await get_room(tenant_id=tenant_id, room_id=room_id)


async def detach_pricing_snapshot(
    *, tenant_id: str, room_id: str, option_id: str, actor_user_id: str, actor_email: str,
) -> dict:
    room = await _get_room(tenant_id, room_id)
    _assert_editable(room)
    option = _find_option(room, option_id)
    merged = {
        **option, "pricing_snapshot_id": None, "suggested_price_cents": None,
        "updated_by_user_id": actor_user_id, "updated_at": _now_iso(),
    }
    merged["selected_display_price_cents"] = _compute_display_price(merged)

    new_options = [merged if o.get("id") == option_id else o for o in (room.get("options") or [])]
    await _persist_room_mutation(tenant_id, room, options=new_options, actor_user_id=actor_user_id)
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="decision_room.option_pricing_snapshot_detached", entity_type="decision_room", entity_id=room_id,
        summary="Pricing snapshot detached from decision option", diff={"option_id": option_id},
    )
    return await get_room(tenant_id=tenant_id, room_id=room_id)


# ---- Readiness validation -------------------------------------------------

def validate_readiness(room: dict[str, Any]) -> dict[str, Any]:
    """Pure, structural readiness check (§15). Every cross-tenant reference
    on `room`/its options was already validated at write time, so this never
    re-queries the database. Never invents a missing price or media
    reference — it only reports what is missing."""
    errors: list[str] = []
    if not (room.get("title") or "").strip():
        errors.append("title_required")
    if not room.get("customer_id"):
        errors.append("customer_required")
    if not any(room.get(k) for k in ("intake_id", "quote_id", "order_id", "order_item_id")):
        errors.append("commercial_or_intake_context_required")

    options = room.get("options") or []
    active_options = [o for o in options if o.get("active", True)]
    if len(active_options) < 2:
        errors.append("at_least_two_active_options_required")

    recommended_count = 0
    for o in active_options:
        oid = o.get("id", "?")
        if not (o.get("customer_label") or o.get("internal_name")):
            errors.append(f"option:{oid}:label_required")
        if o.get("price_display_mode") == "show_price" and o.get("selected_display_price_cents") is None:
            errors.append(f"option:{oid}:price_required")
        if o.get("badge_type") == "recommended":
            recommended_count += 1
    if recommended_count > 1:
        errors.append("multiple_recommended_options")

    expiration_at = room.get("expiration_at")
    if expiration_at:
        try:
            exp = datetime.fromisoformat(str(expiration_at).replace("Z", "+00:00"))
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp <= datetime.now(timezone.utc):
                errors.append("expiration_in_past")
        except ValueError:
            errors.append("expiration_invalid")

    return {"ready": len(errors) == 0, "errors": errors}


async def readiness_report(*, tenant_id: str, room_id: str) -> dict:
    room = await _get_room(tenant_id, room_id)
    return validate_readiness(room)


# ---- Lifecycle transitions + publish -------------------------------------

async def transition(*, tenant_id: str, room_id: str, target: str, actor_user_id: str, actor_email: str) -> dict:
    room = await _get_room(tenant_id, room_id)
    current = room.get("status", "draft")
    if target not in ALLOWED_TRANSITIONS.get(current, set()):
        raise DecisionRoomError("invalid_transition", f"Cannot move Decision Room from {current} to {target}")
    if target == "ready":
        report = validate_readiness(room)
        if not report["ready"]:
            raise DecisionRoomError("readiness_failed", f"Decision Room is not ready: {report['errors']}", details=report["errors"])

    now = _now_iso()
    updates: dict[str, Any] = {"status": target, "updated_at": now, "updated_by_user_id": actor_user_id}
    if target == "archived":
        updates["archived_at"] = now
    elif current == "archived" and target == "draft":
        updates["archived_at"] = None

    await db.decision_rooms.update_one({"id": room_id, "tenant_id": tenant_id}, {"$set": updates})
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action=f"decision_room.{target}", entity_type="decision_room", entity_id=room_id,
        summary=f"Decision Room {current} -> {target}", diff={"from": current, "to": target},
    )
    return await get_room(tenant_id=tenant_id, room_id=room_id)


async def publish_room(*, tenant_id: str, room_id: str, actor_user_id: str, actor_email: str) -> dict:
    room = await _get_room(tenant_id, room_id)
    current = room.get("status", "draft")
    if current not in {"ready", "published"}:
        raise DecisionRoomError(
            "invalid_transition", "Decision Room must be 'ready' (or already 'published') to create a published version",
        )
    report = validate_readiness(room)
    if not report["ready"]:
        raise DecisionRoomError("readiness_failed", f"Decision Room is not ready to publish: {report['errors']}", details=report["errors"])

    # Monotonic per §9: always the next number after the last FROZEN publish,
    # regardless of how many draft edits (each bumping `current_version` as a
    # divergence signal) happened in between — those extra bumps are folded
    # back into alignment with `published_version` here.
    new_version_number = int(room.get("published_version", 0)) + 1
    now = _now_iso()
    version = DecisionRoomVersion(
        tenant_id=tenant_id, decision_room_id=room_id, version_number=new_version_number,
        title=room["title"], customer_safe_intro=room.get("customer_safe_intro"),
        options_snapshot=[dict(o) for o in (room.get("options") or [])],
        allow_save_for_later=room.get("allow_save_for_later", False),
        allow_customer_comments=room.get("allow_customer_comments", False),
        allow_customer_questions=room.get("allow_customer_questions", False),
        allow_change_requests=room.get("allow_change_requests", False),
        require_internal_acceptance=room.get("require_internal_acceptance", True),
        expiration_at=room.get("expiration_at"), published_by_user_id=actor_user_id,
    ).model_dump()
    await db.decision_room_versions.insert_one(prepare_for_mongo(dict(version)))

    await db.decision_rooms.update_one(
        {"id": room_id, "tenant_id": tenant_id},
        {"$set": {
            "status": "published", "current_version": new_version_number, "published_version": new_version_number,
            "published_at": now, "published_by_user_id": actor_user_id,
            "updated_at": now, "updated_by_user_id": actor_user_id,
        }},
    )
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="decision_room.published_version_created", entity_type="decision_room", entity_id=room_id,
        summary=f"Decision Room published version {new_version_number} created",
        diff={"version_number": new_version_number},
    )
    return await get_room(tenant_id=tenant_id, room_id=room_id)


async def list_versions(*, tenant_id: str, room_id: str) -> list[dict]:
    await _get_room(tenant_id, room_id)
    cur = db.decision_room_versions.find(
        {"decision_room_id": room_id, "tenant_id": tenant_id}, {"_id": 0},
    ).sort("version_number", -1)
    return [serialize_doc(d) async for d in cur]


async def get_version(*, tenant_id: str, room_id: str, version_id: str) -> dict:
    doc = await db.decision_room_versions.find_one(
        {"id": version_id, "decision_room_id": room_id, "tenant_id": tenant_id}, {"_id": 0},
    )
    if not doc:
        raise DecisionRoomError("version_not_found", "Decision Room version not found")
    return serialize_doc(doc)


async def archive_room(*, tenant_id: str, room_id: str, actor_user_id: str, actor_email: str) -> dict:
    return await transition(tenant_id=tenant_id, room_id=room_id, target="archived",
                             actor_user_id=actor_user_id, actor_email=actor_email)


async def restore_room(*, tenant_id: str, room_id: str, actor_user_id: str, actor_email: str) -> dict:
    return await transition(tenant_id=tenant_id, room_id=room_id, target="draft",
                             actor_user_id=actor_user_id, actor_email=actor_email)


# ---- Internal customer-safe preview --------------------------------------

def _option_preview(option: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": option.get("id"),
        "display_order": option.get("display_order"),
        "customer_label": option.get("customer_label") or option.get("internal_name"),
        "badge_type": option.get("badge_type", "none"),
        "custom_badge_text": option.get("custom_badge_text"),
        "headline": option.get("headline"),
        "customer_safe_description": option.get("customer_safe_description"),
        "included_features": option.get("included_features", []),
        "excluded_features": option.get("excluded_features", []),
        "expected_timing": option.get("expected_timing"),
        "price_display_mode": option.get("price_display_mode", "show_price"),
        "displayed_price_cents": (
            option.get("selected_display_price_cents") if option.get("price_display_mode") == "show_price" else None
        ),
        "file_ids": option.get("file_ids", []),
        "rendered_preview_file_id": option.get("rendered_preview_file_id"),
        "thumbnail_file_id": option.get("thumbnail_file_id"),
        "customer_safe_notes": option.get("customer_safe_notes"),
    }


async def internal_preview(*, tenant_id: str, room_id: str) -> dict:
    """Deterministic customer-safe preview for STAFF use only (§12). Never
    includes internal notes, cost/profit/margin, employee ids, raw storage
    paths, or private audit data. No operational customer-action affordance
    is represented here — this is a read model, not an endpoint a customer
    can ever reach in Phase 10D."""
    room = await _get_room(tenant_id, room_id)
    active_options = sorted(
        [o for o in (room.get("options") or []) if o.get("active", True)],
        key=lambda o: o.get("display_order", 0),
    )
    return {
        "id": room.get("id"),
        "title": room.get("title"),
        "customer_safe_intro": room.get("customer_safe_intro"),
        "status": room.get("status"),
        "expiration_at": room.get("expiration_at"),
        "allow_save_for_later": room.get("allow_save_for_later", False),
        "allow_customer_comments": room.get("allow_customer_comments", False),
        "allow_customer_questions": room.get("allow_customer_questions", False),
        "allow_change_requests": room.get("allow_change_requests", False),
        "options": [_option_preview(o) for o in active_options],
    }
