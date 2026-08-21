"""Staff and portal branding draft editing."""
from __future__ import annotations

from typing import Any

from ..core.db import db
from ..core.permissions import Perm
from .webstore_branding_contracts import LIVE_BLOCKING_STATUSES, WHOLE_SECTION_PATHS, WebstoreBrandingError
from .webstore_branding_defaults import default_branding
from .webstore_branding_records import (
    _active_assignment,
    _actor_from_identity,
    _actor_from_user,
    _activity,
    _audit,
    _get_store,
    _history,
    _now_iso,
    _record_for_store,
    _response,
    _require_staff_perm,
)
from .webstore_branding_validation import _content_hash, normalize_branding

async def get_staff_branding(user: dict, webstore_id: str) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    store = await _get_store(user["tenant_id"], webstore_id)
    record = await _record_for_store(store)
    data = _response(store, record, role="staff")
    data["history"] = await _history(user["tenant_id"], webstore_id)
    data["activity"] = await _activity(user["tenant_id"], webstore_id)
    return data


def _portal_visibility_denied(content: dict[str, Any], current: dict[str, Any]) -> bool:
    for section, field in WHOLE_SECTION_PATHS:
        current_value = (current.get(section) or {}).get(field)
        if section in content and isinstance(content[section], dict) and content[section].get(field) is False and current_value is not False:
            return True
    return False


async def save_staff_draft(user: dict, webstore_id: str, content: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    store = await _get_store(user["tenant_id"], webstore_id)
    record = await _record_for_store(store)
    draft = normalize_branding(store, content)
    draft_hash = _content_hash(draft)
    updates: dict[str, Any] = {"draft": draft, "draft_hash": draft_hash, "updated_at": _now_iso()}
    if record.get("submitted_hash") != draft_hash:
        updates.update({"status": "draft", "submitted_snapshot": None, "submitted_hash": None, "owner_decision": {}})
    await db.webstore_branding_records.update_one({"tenant_id": user["tenant_id"], "webstore_id": webstore_id}, {"$set": updates})
    saved = await _record_for_store(store)
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor=_actor_from_user(user),
        action="webstore.branding_draft_saved",
        summary="Branding draft saved",
        entity_id=saved["id"],
    )
    return await get_staff_branding(user, webstore_id)


async def get_portal_branding(identity: dict, webstore_id: str) -> dict:
    scoped = await _active_assignment(identity, webstore_id)
    record = await _record_for_store(scoped["store"])
    data = _response(scoped["store"], record, role=scoped["role"])
    data["history"] = await _history(identity["tenant_id"], webstore_id)
    data["activity"] = await _activity(identity["tenant_id"], webstore_id)
    return data


async def save_portal_draft(identity: dict, webstore_id: str, content: dict[str, Any]) -> dict:
    scoped = await _active_assignment(identity, webstore_id)
    store = scoped["store"]
    record = await _record_for_store(store)
    if _portal_visibility_denied(content, record.get("draft") or default_branding(store)):
        raise WebstoreBrandingError("whole_section_visibility_staff_only", "Only shop staff can hide the entire Header, Hero, or Catalog area.", 403)
    draft = normalize_branding(store, content)
    draft_hash = _content_hash(draft)
    updates: dict[str, Any] = {"draft": draft, "draft_hash": draft_hash, "updated_at": _now_iso()}
    if record.get("submitted_hash") != draft_hash:
        updates.update({"status": "draft", "submitted_snapshot": None, "submitted_hash": None, "owner_decision": {}})
    await db.webstore_branding_records.update_one({"tenant_id": identity["tenant_id"], "webstore_id": webstore_id}, {"$set": updates})
    saved = await _record_for_store(store)
    await _audit(
        tenant_id=identity["tenant_id"],
        webstore_id=webstore_id,
        actor=_actor_from_identity(identity),
        action="webstore.branding_draft_saved",
        summary="Branding draft saved",
        entity_id=saved["id"],
    )
    return await get_portal_branding(identity, webstore_id)
