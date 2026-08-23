"""Owner review workflow for Webstore branding."""
from __future__ import annotations

from typing import Any, Optional

from ..core.db import db
from ..core.permissions import Perm
from .webstore_branding_contracts import WebstoreBrandingError
from .webstore_branding_defaults import default_branding
from .webstore_branding_drafts import get_portal_branding, get_staff_branding
from .webstore_branding_records import (
    _active_assignment,
    _actor_from_identity,
    _actor_from_user,
    _activity,
    _audit,
    _get_store,
    _now_iso,
    _record_for_store,
    _response,
    _require_staff_perm,
)
from .webstore_branding_validation import _clean_text, _content_hash, validation_for_branding

async def request_review(actor: dict, webstore_id: str, *, portal: bool = False, note: Optional[str] = None) -> dict:
    if portal:
        scoped = await _active_assignment(actor, webstore_id)
        if scoped["role"] != "manager":
            raise WebstoreBrandingError("manager_review_request_required", "Only shop staff or the assigned Store Manager can request owner review.", 403)
        tenant_id = actor["tenant_id"]
        store = scoped["store"]
        audit_actor = _actor_from_identity(actor)
    else:
        _require_staff_perm(actor, Perm.WEBSTORE_WRITE)
        tenant_id = actor["tenant_id"]
        store = await _get_store(tenant_id, webstore_id)
        audit_actor = _actor_from_user(actor)
    record = await _record_for_store(store)
    draft = record.get("draft") or default_branding(store)
    validation = validation_for_branding(store, draft)
    if validation["errors"]:
        raise WebstoreBrandingError("branding_validation_failed", " ".join(validation["errors"]), 409)
    now = _now_iso()
    draft_hash = _content_hash(draft)
    await db.webstore_branding_records.update_one(
        {"tenant_id": tenant_id, "webstore_id": webstore_id},
        {
            "$set": {
                "status": "waiting_owner_approval",
                "submitted_snapshot": draft,
                "submitted_hash": draft_hash,
                "submitted_at": now,
                "submitted_by_actor_type": audit_actor["type"],
                "submitted_by_id": audit_actor.get("id"),
                "submitted_by_email": audit_actor.get("email"),
                "owner_decision": {},
                "feedback_note": None,
                "updated_at": now,
            }
        },
    )
    await _audit(
        tenant_id=tenant_id,
        webstore_id=webstore_id,
        actor=audit_actor,
        action="webstore.branding_review_requested",
        summary="Owner review requested",
        entity_id=record["id"],
        note=note,
    )
    return await (get_portal_branding(actor, webstore_id) if portal else get_staff_branding(actor, webstore_id))


async def owner_approve(identity: dict, webstore_id: str, note: Optional[str] = None) -> dict:
    scoped = await _active_assignment(identity, webstore_id)
    if scoped["role"] != "owner":
        raise WebstoreBrandingError("owner_approval_required", "Only the assigned Store Owner can approve branding.", 403)
    record = await _record_for_store(scoped["store"])
    if record.get("status") != "waiting_owner_approval" or not record.get("submitted_snapshot"):
        raise WebstoreBrandingError("branding_review_required", "Send branding for owner review before approval.", 409)
    submitted_hash = _content_hash(record["submitted_snapshot"])
    if submitted_hash != record.get("submitted_hash"):
        raise WebstoreBrandingError("branding_review_changed", "The submitted branding changed and must be sent for review again.", 409)
    now = _now_iso()
    decision = {
        "status": "approved",
        "actor_id": identity.get("id"),
        "actor_email": identity.get("email"),
        "decided_at": now,
        "note": _clean_text(note, limit=1000),
        "approved_hash": submitted_hash,
    }
    await db.webstore_branding_records.update_one(
        {"tenant_id": identity["tenant_id"], "webstore_id": webstore_id},
        {"$set": {"status": "owner_approved", "owner_decision": decision, "feedback_note": None, "updated_at": now}},
    )
    await _audit(
        tenant_id=identity["tenant_id"],
        webstore_id=webstore_id,
        actor=_actor_from_identity(identity),
        action="webstore.branding_owner_approved",
        summary="Store Owner approved branding",
        entity_id=record["id"],
        note=note,
    )
    return await get_portal_branding(identity, webstore_id)


async def owner_request_changes(identity: dict, webstore_id: str, note: str) -> dict:
    scoped = await _active_assignment(identity, webstore_id)
    if scoped["role"] != "owner":
        raise WebstoreBrandingError("owner_change_request_required", "Only the assigned Store Owner can request branding changes.", 403)
    clean_note = _clean_text(note, limit=1000)
    if not clean_note:
        raise WebstoreBrandingError("feedback_note_required", "Add a change-request note for the shop team.", 400)
    record = await _record_for_store(scoped["store"])
    if record.get("status") != "waiting_owner_approval":
        raise WebstoreBrandingError("branding_review_required", "A submitted branding review is required before requesting changes.", 409)
    now = _now_iso()
    decision = {
        "status": "changes_requested",
        "actor_id": identity.get("id"),
        "actor_email": identity.get("email"),
        "decided_at": now,
        "note": clean_note,
    }
    await db.webstore_branding_records.update_one(
        {"tenant_id": identity["tenant_id"], "webstore_id": webstore_id},
        {"$set": {"status": "changes_requested", "owner_decision": decision, "feedback_note": clean_note, "updated_at": now}},
    )
    await _audit(
        tenant_id=identity["tenant_id"],
        webstore_id=webstore_id,
        actor=_actor_from_identity(identity),
        action="webstore.branding_changes_requested",
        summary="Store Owner requested branding changes",
        entity_id=record["id"],
        note=clean_note,
    )
    return await get_portal_branding(identity, webstore_id)
