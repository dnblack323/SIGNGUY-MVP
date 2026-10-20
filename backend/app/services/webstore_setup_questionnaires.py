"""Questionnaire templates, owner responses, staff review returns, and notifications."""
from __future__ import annotations

from .forms_service import invalid_answer_keys
from .webstore_questionnaire_pack import QUESTIONNAIRE_STORE_TYPES, questionnaires_by_ids, questionnaires_for_store_type
from .webstore_setup_common import *
from .webstore_setup_portal_scope import _owner_safe_store, _owner_store
from .webstore_setup_progress import _refresh_setup_state


async def list_questionnaire_templates(user: dict, *, store_type: Optional[str] = None, active_only: bool = False) -> dict:
    """Webstore questionnaires as Form Maker holds them (all are published, so active_only is moot)."""
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    store_types = [store_type] if store_type else list(QUESTIONNAIRE_STORE_TYPES)
    items: dict[str, dict] = {}
    for st in store_types:
        for template in await questionnaires_for_store_type(user["tenant_id"], st):
            items.setdefault(template["id"], template)
    return {"items": list(items.values())}


async def bind_questionnaire_templates(user: dict, webstore_id: str) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    store = await _get_store(user["tenant_id"], webstore_id)
    templates = await _bind(store)
    return {"webstore_id": webstore_id, "templates": templates}


async def _bind(store: dict) -> list[dict]:
    templates = await questionnaires_for_store_type(store["tenant_id"], store.get("store_type") or "general")
    await db.webstores.update_one(
        {"tenant_id": store["tenant_id"], "id": store["id"]},
        {"$set": {"setup_requirements.questionnaire_template_ids": [t["id"] for t in templates], "updated_at": _now_iso()}},
    )
    return templates


async def owner_questionnaire(identity: dict, webstore_id: str) -> dict:
    store = await _owner_store(identity, webstore_id)
    templates = await _bound_templates(store)
    submission = await db.webstore_questionnaire_submissions.find_one(
        {"tenant_id": identity["tenant_id"], "webstore_id": webstore_id, "portal_identity_id": identity["id"], "status": {"$in": ["draft", "returned_for_changes"]}},
        {"_id": 0},
        sort=[("updated_at", -1)],
    )
    return {"webstore": _owner_safe_store(store), "templates": templates, "submission": serialize_doc(submission) if submission else None}


async def _bound_templates(store: dict) -> list[dict]:
    """The questionnaires bound to this store; rebinds if none of them are still published
    (for example a store bound before the Webstore Starter pack existed)."""
    ids = ((store.get("setup_requirements") or {}).get("questionnaire_template_ids") or [])
    templates = await questionnaires_by_ids(store["tenant_id"], ids) if ids else []
    return templates or await _bind(store)


async def save_questionnaire_draft(identity: dict, webstore_id: str, fields: dict[str, Any]) -> dict:
    store = await _owner_store(identity, webstore_id)
    owner_id = identity.get("webstore_owner_id") or store["owner_id"]
    templates = await _bound_templates(store)
    payload = {
        "answers": fields.get("answers") or {},
        "known_products": fields.get("known_products") or [],
        "open_to_suggestions": bool(fields.get("open_to_suggestions", True)),
        "missing_info_flags": fields.get("missing_info_flags") or [],
        "status": "draft",
        "portal_identity_id": identity["id"],
        "template_ids": [t["id"] for t in templates],
        "template_version_ids": [f"{t['id']}:v{t.get('version', 1)}" for t in templates],
        "template_snapshot": {"templates": templates},
        "updated_at": _now_iso(),
    }
    existing = await db.webstore_questionnaire_submissions.find_one(
        {"tenant_id": identity["tenant_id"], "webstore_id": webstore_id, "portal_identity_id": identity["id"], "status": "draft"},
        {"_id": 0},
    )
    if existing:
        await db.webstore_questionnaire_submissions.update_one({"tenant_id": identity["tenant_id"], "id": existing["id"]}, {"$set": payload})
        doc = await db.webstore_questionnaire_submissions.find_one({"tenant_id": identity["tenant_id"], "id": existing["id"]}, {"_id": 0})
    else:
        doc = WebstoreQuestionnaireSubmission(
            tenant_id=identity["tenant_id"],
            webstore_id=webstore_id,
            owner_id=owner_id,
            **payload,
        ).model_dump()
        await db.webstore_questionnaire_submissions.insert_one(prepare_for_mongo(doc))
    await _refresh_setup_state(identity["tenant_id"], webstore_id)
    return serialize_doc(doc or {})


async def submit_questionnaire(identity: dict, webstore_id: str, fields: dict[str, Any]) -> dict:
    existing_submitted = await db.webstore_questionnaire_submissions.find_one(
        {"tenant_id": identity["tenant_id"], "webstore_id": webstore_id, "portal_identity_id": identity["id"], "status": {"$in": ["submitted", "reviewed"]}},
        {"_id": 0},
        sort=[("submitted_at", -1), ("updated_at", -1)],
    )
    if existing_submitted:
        return serialize_doc(existing_submitted)
    draft = await save_questionnaire_draft(identity, webstore_id, fields)
    templates = draft.get("template_snapshot", {}).get("templates") or []
    answers = draft.get("answers") or {}
    invalid = invalid_answer_keys({"sections": [s for t in templates for s in t.get("sections") or []]}, answers)
    if invalid:
        raise WebstoreSetupError("questionnaire_required_answers_missing", f"Missing or invalid answers: {', '.join(invalid)}", 400)
    previous = await db.webstore_questionnaire_submissions.find_one(
        {"tenant_id": identity["tenant_id"], "webstore_id": webstore_id, "revision": {"$ne": None}},
        {"_id": 0, "id": 1, "revision": 1},
        sort=[("revision", -1)],
    )
    revision = int(previous["revision"]) + 1 if previous else 1
    now = _now_iso()
    snapshot = {
        "answers": answers,
        "known_products": draft.get("known_products") or [],
        "missing_info_flags": [],
        "template_snapshot": draft.get("template_snapshot") or {},
        "submitted_at": now,
        "revision": revision,
    }
    # Only a draft can become a revision; the filter also stops a double submit.
    result = await db.webstore_questionnaire_submissions.update_one(
        {"tenant_id": identity["tenant_id"], "id": draft["id"], "status": "draft"},
        {
            "$set": {
                "status": "submitted",
                "submitted_at": now,
                "submitted_snapshot": snapshot,
                "missing_info_flags": [],
                "revision": revision,
                "supersedes_submission_id": previous["id"] if previous else None,
                "updated_at": now,
            }
        },
    )
    submitted = await db.webstore_questionnaire_submissions.find_one({"tenant_id": identity["tenant_id"], "id": draft["id"]}, {"_id": 0})
    if not result.modified_count:
        return serialize_doc(submitted or {})
    await db.webstores.update_one(
        {"tenant_id": identity["tenant_id"], "id": webstore_id},
        {"$set": {"setup_state": "questionnaire_submitted", "updated_at": now}},
    )
    await _audit(
        tenant_id=identity["tenant_id"],
        webstore_id=webstore_id,
        actor_type="portal",
        actor_id=identity["id"],
        actor_email=identity.get("email"),
        action="webstore.questionnaire_submitted",
        entity_type="webstore_questionnaire_submission",
        entity_id=draft["id"],
        summary=f"Webstore setup questionnaire submitted (revision {revision})",
        metadata={"revision": revision},
    )
    store = await _get_store(identity["tenant_id"], webstore_id)
    await notify_tenant_owners(
        tenant_id=identity["tenant_id"],
        module="webstores",
        kind="webstore.questionnaire_submitted",
        title=f"{store.get('name')} questionnaire submitted",
        body="The store owner submitted setup answers. Review and apply safe answers in the Webstore workspace.",
        severity="info",
        entity_type="webstore",
        entity_id=webstore_id,
        link=f"/webstores/{webstore_id}",
        metadata={"submission_id": draft["id"], "webstore_id": webstore_id, "revision": revision},
    )
    return serialize_doc(submitted or {})


async def return_questionnaire(user: dict, webstore_id: str, submission_id: str, reason: str) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    reason = _clean_text(reason, "reason", limit=1000)
    submission = await db.webstore_questionnaire_submissions.find_one({"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "id": submission_id}, {"_id": 0})
    if not submission:
        raise WebstoreSetupError("questionnaire_submission_not_found", "Questionnaire submission not found", 404)
    await db.webstore_questionnaire_submissions.update_one(
        {"tenant_id": user["tenant_id"], "id": submission_id},
        {"$set": {"status": "returned_for_changes", "returned_reason": reason, "updated_at": _now_iso()}},
    )
    await _refresh_setup_state(user["tenant_id"], webstore_id)
    return {"submission_id": submission_id, "status": "returned_for_changes", "reason": reason}


async def latest_questionnaire_response(user: dict, webstore_id: str) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    await _get_store(user["tenant_id"], webstore_id)
    doc = await db.webstore_questionnaire_submissions.find_one(
        {"tenant_id": user["tenant_id"], "webstore_id": webstore_id},
        {"_id": 0},
        sort=[("updated_at", -1)],
    )
    return {"submission": serialize_doc(doc) if doc else None}

__all__ = ['list_questionnaire_templates', 'bind_questionnaire_templates', 'owner_questionnaire', '_bound_templates', 'save_questionnaire_draft', 'submit_questionnaire', 'return_questionnaire', 'latest_questionnaire_response']
