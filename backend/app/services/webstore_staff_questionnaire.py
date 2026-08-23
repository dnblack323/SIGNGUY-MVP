"""Webstore Owner questionnaire submission compatibility operation."""
from __future__ import annotations

from .webstore_shared import *


async def submit_questionnaire(identity: dict, webstore_id: str, fields: dict[str, Any]) -> dict:
    store = await _owner_portal_store(identity, webstore_id)
    owner = await _get_owner(identity["tenant_id"], store["owner_id"])
    existing = await submissions_repo.find_one({"tenant_id": identity["tenant_id"], "webstore_id": webstore_id})
    payload = {
        "answers": fields.get("answers") or {},
        "known_products": fields.get("known_products") or [],
        "open_to_suggestions": bool(fields.get("open_to_suggestions", True)),
        "missing_info_flags": fields.get("missing_info_flags") or [],
        "status": "submitted",
        "submitted_at": _now_iso(),
    }
    if existing:
        submission = await submissions_repo.update(tenant_id=identity["tenant_id"], entity_id=existing["id"], updates=payload)
    else:
        doc = WebstoreQuestionnaireSubmission(
            tenant_id=identity["tenant_id"],
            webstore_id=webstore_id,
            owner_id=owner["id"],
            **payload,
        ).model_dump()
        await db.webstore_questionnaire_submissions.insert_one(prepare_for_mongo(doc))
        submission = serialize_doc(doc)
    await stores_repo.update(tenant_id=identity["tenant_id"], entity_id=webstore_id, updates={"status": "questionnaire_submitted"})
    await _audit(
        tenant_id=identity["tenant_id"],
        webstore_id=webstore_id,
        actor_type="portal",
        actor_id=identity["id"],
        actor_email=identity.get("email"),
        action="webstore.questionnaire_submitted",
        entity_type="webstore_questionnaire_submission",
        entity_id=submission["id"],
        summary="Webstore owner submitted questionnaire",
    )
    return submission or {}

__all__ = ['submit_questionnaire']
