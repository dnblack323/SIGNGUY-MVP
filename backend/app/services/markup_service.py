"""EC10 Phase 10C — Visual Markup service.

Structured markup JSON is a Fabric.js `canvas.toJSON()`-shaped payload
containing ONLY annotation objects (never the source image/PDF, never a
`backgroundImage`, never a data-URI). Every write validates: allowlisted
object types only, no embedded binary/image data, a maximum object count,
and a maximum serialized size — see `validate_structured_markup()`.

Version numbering uses the same atomic `find_one_and_update($inc=...)`
pattern already proven race-safe by `services/sequence.py`, scoped to the
`VisualMarkup` document itself (not a separate counters collection) since
version numbers only need to be unique per-markup, not per-tenant.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from pymongo import ReturnDocument

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.visual_markup import MarkupVersion, VisualMarkup
from ..services.audit import record_audit

_ALLOWED_OBJECT_TYPES = {
    "rect", "circle", "ellipse", "line", "path", "triangle",
    "textbox", "i-text", "text", "group", "polygon", "polyline",
}
_MAX_OBJECTS = 300
_MAX_PAYLOAD_BYTES = 300_000
_FORBIDDEN_VALUE_PREFIXES = ("data:image", "data:application/pdf", "data:application/octet-stream")
_IMAGE_CONTENT_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
_PDF_CONTENT_TYPE = "application/pdf"


class MarkupError(ValueError):
    def __init__(self, code: str, message: Optional[str] = None):
        super().__init__(message or code)
        self.code = code


def _scan_for_forbidden_values(node: Any) -> bool:
    if isinstance(node, str):
        low = node.strip().lower()
        return any(low.startswith(p) for p in _FORBIDDEN_VALUE_PREFIXES)
    if isinstance(node, dict):
        return any(_scan_for_forbidden_values(v) for v in node.values())
    if isinstance(node, list):
        return any(_scan_for_forbidden_values(v) for v in node)
    return False


def _count_and_validate_objects(objects: list, depth: int = 0) -> int:
    if depth > 1:
        raise MarkupError("malformed_markup", "Groups may not be nested more than one level deep")
    count = 0
    for obj in objects:
        if not isinstance(obj, dict):
            raise MarkupError("malformed_markup", "Each markup object must be a JSON object")
        obj_type = obj.get("type")
        if obj_type not in _ALLOWED_OBJECT_TYPES:
            raise MarkupError("unsupported_object_type", f"Unsupported markup object type: {obj_type!r}")
        count += 1
        if obj_type == "group":
            nested = obj.get("objects") or []
            if not isinstance(nested, list):
                raise MarkupError("malformed_markup", "Group 'objects' must be a list")
            count += _count_and_validate_objects(nested, depth + 1)
    return count


def validate_structured_markup(payload: dict[str, Any]) -> int:
    """Raises `MarkupError` on any violation; returns the total object count."""
    if not isinstance(payload, dict):
        raise MarkupError("malformed_markup", "structured_markup_json must be a JSON object")
    objects = payload.get("objects", [])
    if not isinstance(objects, list):
        raise MarkupError("malformed_markup", "structured_markup_json.objects must be a list")
    if "backgroundImage" in payload or "background" in payload:
        raise MarkupError("embedded_binary_forbidden", "structured_markup_json must not include a background image")
    serialized_size = len(json.dumps(payload).encode("utf-8"))
    if serialized_size > _MAX_PAYLOAD_BYTES:
        raise MarkupError("payload_too_large", f"Markup payload exceeds the {_MAX_PAYLOAD_BYTES}-byte limit")
    if _scan_for_forbidden_values(payload):
        raise MarkupError("embedded_binary_forbidden", "Markup payload must not embed image/binary data")
    total = _count_and_validate_objects(objects)
    if total > _MAX_OBJECTS:
        raise MarkupError("too_many_objects", f"Markup exceeds the maximum of {_MAX_OBJECTS} objects")
    return total


async def _get_source_file(tenant_id: str, file_id: str) -> dict:
    doc = await db.files.find_one({"id": file_id, "tenant_id": tenant_id, "archived": {"$ne": True}}, {"_id": 0})
    if not doc:
        raise MarkupError("source_file_not_found", "Source file not found for this tenant")
    return doc


def _file_type_for_content_type(content_type: str) -> str:
    ct = (content_type or "").lower()
    if ct in _IMAGE_CONTENT_TYPES:
        return "image"
    if ct == _PDF_CONTENT_TYPE:
        return "pdf"
    raise MarkupError("unsupported_source_file_type", f"Unsupported markup source type: {content_type!r}")


async def _validate_intake(tenant_id: str, intake_id: Optional[str]) -> Optional[dict]:
    if not intake_id:
        return None
    doc = await db.intake_submissions.find_one({"id": intake_id, "tenant_id": tenant_id})
    if not doc:
        raise MarkupError("intake_not_found", "Intake submission not found for this tenant")
    return doc


def _find_intake_item(intake_doc: dict, intake_item_id: str) -> dict:
    item = next((i for i in (intake_doc.get("items") or []) if i.get("id") == intake_item_id), None)
    if not item:
        raise MarkupError("intake_item_not_found", "Intake item not found on this intake")
    return item


async def _validate_preview_file(tenant_id: str, file_id: Optional[str]) -> None:
    if not file_id:
        return
    doc = await db.files.find_one({"id": file_id, "tenant_id": tenant_id}, {"_id": 0, "id": 1})
    if not doc:
        raise MarkupError("preview_file_not_found", "Rendered preview file not found for this tenant")


async def create_markup(
    *, tenant_id: str, source_file_id: str, source_page_number: Optional[int],
    intake_id: Optional[str], intake_item_id: Optional[str], title: Optional[str],
    description: Optional[str], actor_user_id: str, actor_email: str,
) -> dict:
    file_doc = await _get_source_file(tenant_id, source_file_id)
    source_file_type = _file_type_for_content_type(file_doc.get("mime_type", ""))
    if source_file_type == "pdf":
        if not source_page_number or source_page_number < 1:
            raise MarkupError("invalid_pdf_page", "A valid (>=1) source_page_number is required for PDF markup")
    else:
        source_page_number = None

    intake_doc = await _validate_intake(tenant_id, intake_id)
    if intake_item_id:
        if not intake_doc:
            raise MarkupError("intake_not_found", "intake_id is required when intake_item_id is provided")
        _find_intake_item(intake_doc, intake_item_id)

    markup = VisualMarkup(
        tenant_id=tenant_id, source_file_id=source_file_id, source_file_type=source_file_type,
        source_page_number=source_page_number, intake_id=intake_id, intake_item_id=intake_item_id,
        title=title, description=description,
        created_by_user_id=actor_user_id, updated_by_user_id=actor_user_id,
    ).model_dump()
    await db.visual_markups.insert_one(prepare_for_mongo(dict(markup)))
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="markup.created", entity_type="visual_markup", entity_id=markup["id"],
        summary="Visual markup workspace created",
        diff={"source_file_id": source_file_id, "intake_id": intake_id, "intake_item_id": intake_item_id},
    )
    return serialize_doc(markup)


async def get_markup(*, tenant_id: str, markup_id: str) -> dict:
    doc = await db.visual_markups.find_one({"id": markup_id, "tenant_id": tenant_id}, {"_id": 0})
    if not doc:
        raise MarkupError("markup_not_found", "Visual markup not found")
    return serialize_doc(doc)


async def list_markup(
    *, tenant_id: str, intake_id: Optional[str] = None, intake_item_id: Optional[str] = None,
    status: Optional[str] = None,
) -> list[dict]:
    q: dict = {"tenant_id": tenant_id}
    if intake_id: q["intake_id"] = intake_id
    if intake_item_id: q["intake_item_id"] = intake_item_id
    if status: q["status"] = status
    cur = db.visual_markups.find(q, {"_id": 0}).sort("created_at", -1)
    return [serialize_doc(d) async for d in cur]


async def save_version(
    *, tenant_id: str, markup_id: str, structured_markup_json: dict[str, Any],
    canvas_width: int, canvas_height: int, source_display_width: int, source_display_height: int,
    rendered_preview_file_id: Optional[str], change_summary: Optional[str],
    actor_user_id: str, actor_email: str,
) -> dict:
    markup = await db.visual_markups.find_one({"id": markup_id, "tenant_id": tenant_id})
    if not markup:
        raise MarkupError("markup_not_found", "Visual markup not found")
    if markup.get("status") != "active":
        raise MarkupError("markup_archived", "Cannot save a new version on an archived markup")

    object_count = validate_structured_markup(structured_markup_json)
    await _validate_preview_file(tenant_id, rendered_preview_file_id)

    # Atomic, race-safe version numbering — mirrors `services/sequence.py`.
    updated_markup = await db.visual_markups.find_one_and_update(
        {"id": markup_id, "tenant_id": tenant_id},
        {"$inc": {"current_version_number": 1}},
        return_document=ReturnDocument.AFTER,
    )
    version_number = int(updated_markup["current_version_number"])
    parent_version_id = markup.get("current_version_id")

    version = MarkupVersion(
        tenant_id=tenant_id, visual_markup_id=markup_id, version_number=version_number,
        canvas_width=canvas_width, canvas_height=canvas_height,
        source_display_width=source_display_width, source_display_height=source_display_height,
        structured_markup_json=structured_markup_json, rendered_preview_file_id=rendered_preview_file_id,
        change_summary=change_summary, created_by_user_id=actor_user_id, parent_version_id=parent_version_id,
    ).model_dump()
    await db.markup_versions.insert_one(prepare_for_mongo(dict(version)))

    now = utc_now().isoformat()
    update_fields: dict[str, Any] = {
        "current_version_id": version["id"], "updated_at": now, "updated_by_user_id": actor_user_id,
    }
    await db.visual_markups.update_one({"id": markup_id, "tenant_id": tenant_id}, {"$set": update_fields})

    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="markup.version_saved", entity_type="visual_markup", entity_id=markup_id,
        summary=f"Markup version {version_number} saved ({object_count} object(s))",
        diff={"source_file_id": markup.get("source_file_id"), "intake_id": markup.get("intake_id"),
              "intake_item_id": markup.get("intake_item_id"), "version_number": version_number},
    )
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="markup.current_version_changed", entity_type="visual_markup", entity_id=markup_id,
        summary=f"Current version advanced to {version_number}",
        diff={"version_number": version_number, "previous_version_id": parent_version_id},
    )

    # Propagate to an attached Intake Item so its preview always reflects
    # the current version — reference only, never a copy of the markup JSON.
    if markup.get("intake_item_id") and rendered_preview_file_id:
        await db.intake_submissions.update_one(
            {"id": markup["intake_id"], "tenant_id": tenant_id, "items.id": markup["intake_item_id"]},
            {"$set": {
                "items.$.visual_markup_id": markup_id,
                "items.$.rendered_preview_file_id": rendered_preview_file_id,
                "updated_at": now,
            }},
        )

    doc = await db.visual_markups.find_one({"id": markup_id, "tenant_id": tenant_id}, {"_id": 0})
    return {"markup": serialize_doc(doc), "version": serialize_doc(version)}


async def list_versions(*, tenant_id: str, markup_id: str) -> list[dict]:
    markup = await db.visual_markups.find_one({"id": markup_id, "tenant_id": tenant_id}, {"_id": 0, "id": 1})
    if not markup:
        raise MarkupError("markup_not_found", "Visual markup not found")
    cur = db.markup_versions.find(
        {"visual_markup_id": markup_id, "tenant_id": tenant_id}, {"_id": 0},
    ).sort("version_number", -1)
    return [serialize_doc(d) async for d in cur]


async def get_version(*, tenant_id: str, markup_id: str, version_id: str) -> dict:
    doc = await db.markup_versions.find_one(
        {"id": version_id, "visual_markup_id": markup_id, "tenant_id": tenant_id}, {"_id": 0},
    )
    if not doc:
        raise MarkupError("version_not_found", "Markup version not found")
    return serialize_doc(doc)


async def get_preview_reference(*, tenant_id: str, markup_id: str) -> dict:
    markup = await db.visual_markups.find_one({"id": markup_id, "tenant_id": tenant_id}, {"_id": 0})
    if not markup:
        raise MarkupError("markup_not_found", "Visual markup not found")
    if not markup.get("current_version_id"):
        return {"rendered_preview_file_id": None, "version_number": 0}
    version = await db.markup_versions.find_one(
        {"id": markup["current_version_id"], "tenant_id": tenant_id}, {"_id": 0, "rendered_preview_file_id": 1, "version_number": 1},
    )
    return {
        "rendered_preview_file_id": (version or {}).get("rendered_preview_file_id"),
        "version_number": (version or {}).get("version_number", 0),
    }


async def _set_status(*, tenant_id: str, markup_id: str, status: str, action: str,
                       actor_user_id: str, actor_email: str) -> dict:
    markup = await db.visual_markups.find_one({"id": markup_id, "tenant_id": tenant_id})
    if not markup:
        raise MarkupError("markup_not_found", "Visual markup not found")
    now = utc_now().isoformat()
    updates: dict[str, Any] = {"status": status, "updated_at": now, "updated_by_user_id": actor_user_id}
    updates["archived_at"] = now if status == "archived" else None
    await db.visual_markups.update_one({"id": markup_id, "tenant_id": tenant_id}, {"$set": updates})
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action=action, entity_type="visual_markup", entity_id=markup_id,
        summary=f"Visual markup {status}", diff={"status": status},
    )
    doc = await db.visual_markups.find_one({"id": markup_id, "tenant_id": tenant_id}, {"_id": 0})
    return serialize_doc(doc or {})


async def archive_markup(*, tenant_id: str, markup_id: str, actor_user_id: str, actor_email: str) -> dict:
    return await _set_status(tenant_id=tenant_id, markup_id=markup_id, status="archived",
                              action="markup.archived", actor_user_id=actor_user_id, actor_email=actor_email)


async def restore_markup(*, tenant_id: str, markup_id: str, actor_user_id: str, actor_email: str) -> dict:
    return await _set_status(tenant_id=tenant_id, markup_id=markup_id, status="active",
                              action="markup.restored", actor_user_id=actor_user_id, actor_email=actor_email)


async def attach_to_intake(*, tenant_id: str, markup_id: str, intake_id: str,
                            actor_user_id: str, actor_email: str) -> dict:
    markup = await db.visual_markups.find_one({"id": markup_id, "tenant_id": tenant_id}, {"_id": 0, "id": 1})
    if not markup:
        raise MarkupError("markup_not_found", "Visual markup not found")
    intake_doc = await _validate_intake(tenant_id, intake_id)
    if not intake_doc:
        raise MarkupError("intake_not_found", "Intake submission not found")
    await db.intake_submissions.update_one(
        {"id": intake_id, "tenant_id": tenant_id},
        {"$addToSet": {"visual_markup_ids": markup_id}, "$set": {"updated_at": utc_now().isoformat()}},
    )
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="markup.attached_to_intake", entity_type="intake_submission", entity_id=intake_id,
        summary="Visual markup attached to intake", diff={"markup_id": markup_id},
    )
    doc = await db.intake_submissions.find_one({"id": intake_id, "tenant_id": tenant_id}, {"_id": 0})
    return serialize_doc(doc or {})


async def attach_to_intake_item(*, tenant_id: str, markup_id: str, intake_id: str, intake_item_id: str,
                                 actor_user_id: str, actor_email: str) -> dict:
    markup = await db.visual_markups.find_one({"id": markup_id, "tenant_id": tenant_id})
    if not markup:
        raise MarkupError("markup_not_found", "Visual markup not found")
    intake_doc = await _validate_intake(tenant_id, intake_id)
    if not intake_doc:
        raise MarkupError("intake_not_found", "Intake submission not found")
    _find_intake_item(intake_doc, intake_item_id)

    preview = await get_preview_reference(tenant_id=tenant_id, markup_id=markup_id)
    now = utc_now().isoformat()
    await db.intake_submissions.update_one(
        {"id": intake_id, "tenant_id": tenant_id, "items.id": intake_item_id},
        {"$set": {
            "items.$.visual_markup_id": markup_id,
            "items.$.rendered_preview_file_id": preview.get("rendered_preview_file_id"),
            "updated_at": now,
        }},
    )
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="markup.attached_to_intake_item", entity_type="intake_submission", entity_id=intake_id,
        summary="Visual markup attached to intake item", diff={"markup_id": markup_id, "intake_item_id": intake_item_id},
    )
    doc = await db.intake_submissions.find_one({"id": intake_id, "tenant_id": tenant_id}, {"_id": 0})
    return serialize_doc(doc or {})
