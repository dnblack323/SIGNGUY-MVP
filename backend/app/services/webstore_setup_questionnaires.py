"""Questionnaire templates, owner responses, staff review returns, and notifications."""
from __future__ import annotations

from .forms_service import invalid_answer_keys
from .webstore_questionnaire_pack import QUESTIONNAIRE_STORE_TYPES, questionnaires_by_ids, questionnaires_for_store_type
from .webstore_setup_common import *
from .webstore_questionnaire_content import ACKNOWLEDGEMENT_TEXT, ACKNOWLEDGEMENT_VERSION
from .webstore_shop_settings import filter_questionnaire_to_shop, get_fulfillment_settings
from .webstore_questionnaire_review import consistency_checks
from .webstore_setup_portal_scope import _owner_safe_store, _owner_store
from .webstore_next_action import with_derived_state
from .webstore_stage import apply_store_status


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
    templates = await _owner_templates(store)
    from .webstore_information_packet import owner_welcome

    latest = await db.webstore_questionnaire_submissions.find_one(
        {"tenant_id": identity["tenant_id"], "webstore_id": webstore_id, "revision": {"$ne": None}},
        {"_id": 0, "id": 1, "status": 1, "revision": 1, "returned_reason": 1, "submitted_at": 1}, sort=[("revision", -1)],
    )
    # The form is open while the owner has a draft, or while the newest revision was returned for changes.
    submission = await db.webstore_questionnaire_submissions.find_one(
        {"tenant_id": identity["tenant_id"], "webstore_id": webstore_id, "portal_identity_id": identity["id"], "status": "draft"},
        {"_id": 0},
        sort=[("updated_at", -1)],
    )
    if not submission and latest and latest.get("status") == "returned_for_changes":
        submission = await db.webstore_questionnaire_submissions.find_one({"tenant_id": identity["tenant_id"], "id": latest["id"]}, {"_id": 0})
    owner = await db.webstore_owners.find_one({"tenant_id": store["tenant_id"], "id": store.get("owner_id")}, {"_id": 0})
    return {
        "webstore": _owner_safe_store(await with_derived_state(store)),
        "templates": templates,
        "submission": serialize_doc(submission) if submission else None,
        "latest_revision": serialize_doc(latest) if latest else None,
        "welcome": await owner_welcome(store, owner),
    }


async def _bound_templates(store: dict) -> list[dict]:
    """The questionnaires bound to this store; rebinds if none of them are still published
    (for example a store bound before the Webstore Starter pack existed)."""
    ids = ((store.get("setup_requirements") or {}).get("questionnaire_template_ids") or [])
    templates = await questionnaires_by_ids(store["tenant_id"], ids) if ids else []
    return templates or await _bind(store)


async def _owner_templates(store: dict) -> list[dict]:
    """Bound questionnaires as the owner sees them: only fulfillment methods this shop supports."""
    return filter_questionnaire_to_shop(await _bound_templates(store), await get_fulfillment_settings(store["tenant_id"]))


async def save_questionnaire_draft(identity: dict, webstore_id: str, fields: dict[str, Any]) -> dict:
    store = await _owner_store(identity, webstore_id)
    owner_id = identity.get("webstore_owner_id") or store["owner_id"]
    templates = await _owner_templates(store)
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
    sections = [s for t in templates for s in t.get("sections") or []]
    invalid = invalid_answer_keys({"sections": sections}, answers)
    if invalid:
        labels = {q.get("key"): q.get("label") for s in sections for q in s.get("questions") or []}
        listed = "; ".join(f"{labels.get(k) or k} ({k})" for k in invalid)
        raise WebstoreSetupError("questionnaire_required_answers_missing", f"Please complete these answers: {listed}", 400)
    previous = await db.webstore_questionnaire_submissions.find_one(
        {"tenant_id": identity["tenant_id"], "webstore_id": webstore_id, "revision": {"$ne": None}},
        {"_id": 0, "id": 1, "revision": 1},
        sort=[("revision", -1)],
    )
    revision = int(previous["revision"]) + 1 if previous else 1
    now = _now_iso()
    acknowledgement = (
        {"version": ACKNOWLEDGEMENT_VERSION, "text": ACKNOWLEDGEMENT_TEXT, "accepted_at": now,
         "portal_identity_id": identity["id"], "revision": revision}
        if "confirmed" in (answers.get("intake_acknowledgement") or []) else None
    )
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
                "acknowledgement": acknowledgement,
                "updated_at": now,
            }
        },
    )
    submitted = await db.webstore_questionnaire_submissions.find_one({"tenant_id": identity["tenant_id"], "id": draft["id"]}, {"_id": 0})
    if not result.modified_count:
        return serialize_doc(submitted or {})
    await apply_store_status(
        tenant_id=identity["tenant_id"], webstore_id=webstore_id, status="questionnaire_submitted", source="questionnaire_submitted",
        actor_id=identity["id"], actor_email=identity.get("email"), validate=False,
        only_from={"draft", "questionnaire_sent", "waiting_on_store_owner", "changes_requested"},
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
        title=f"{store.get('name')} questionnaire ready for review",
        body=f"Revision {revision} was submitted. Open the review to check the summary and Approve & Apply.",
        severity="info",
        entity_type="webstore",
        entity_id=webstore_id,
        link=f"/webstores/{webstore_id}",
        metadata={"submission_id": draft["id"], "webstore_id": webstore_id, "revision": revision},
        dedupe_key=f"webstore.questionnaire_submitted:{draft['id']}",
    )
    warnings = consistency_checks(store, submitted or {}, await get_fulfillment_settings(identity["tenant_id"]))
    if warnings:
        await notify_tenant_owners(
            tenant_id=identity["tenant_id"],
            module="webstores",
            kind="webstore.questionnaire_correction_needed",
            title=f"{store.get('name')} questionnaire needs a correction",
            body="; ".join(w["message"] for w in warnings)[:500],
            severity="warning",
            entity_type="webstore",
            entity_id=webstore_id,
            link=f"/webstores/{webstore_id}",
            metadata={"submission_id": draft["id"], "codes": [w["code"] for w in warnings]},
            dedupe_key=f"webstore.questionnaire_correction_needed:{draft['id']}",
        )
    return serialize_doc(submitted or {})


async def return_questionnaire(user: dict, webstore_id: str, submission_id: str, reason: str) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    reason = _clean_text(reason, "reason", limit=1000)
    submission = await db.webstore_questionnaire_submissions.find_one({"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "id": submission_id}, {"_id": 0})
    if not submission:
        raise WebstoreSetupError("questionnaire_submission_not_found", "Questionnaire submission not found", 404)
    if submission.get("status") == "returned_for_changes":
        return {"submission_id": submission_id, "status": "returned_for_changes", "reason": submission.get("returned_reason")}
    if submission.get("status") != "submitted":
        raise WebstoreSetupError("questionnaire_not_returnable", "Only a submitted questionnaire that has not been applied can be returned", 409)
    await db.webstore_questionnaire_submissions.update_one(
        {"tenant_id": user["tenant_id"], "id": submission_id},
        {"$set": {"status": "returned_for_changes", "returned_reason": reason, "returned_at": _now_iso(), "updated_at": _now_iso()}},
    )
    store = await _get_store(user["tenant_id"], webstore_id)
    await notify_tenant_owners(
        tenant_id=user["tenant_id"],
        module="webstores",
        kind="webstore.questionnaire_returned",
        title=f"{store.get('name')} questionnaire returned for changes",
        body=reason,
        severity="info",
        entity_type="webstore",
        entity_id=webstore_id,
        link=f"/webstores/{webstore_id}",
        metadata={"submission_id": submission_id, "returned_by": user.get("email")},
        dedupe_key=f"webstore.questionnaire_returned:{submission_id}",
    )
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
