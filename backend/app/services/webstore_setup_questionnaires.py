"""Questionnaire templates, owner responses, staff review returns, and notifications."""
from __future__ import annotations

from .webstore_setup_common import *
from .webstore_setup_portal_scope import _owner_safe_store, _owner_store
from .webstore_setup_progress import _refresh_setup_state


async def ensure_default_questionnaire_templates(tenant_id: str) -> None:
    for store_type in ("base", *WEBSTORE_TYPES, *LEGACY_WEBSTORE_TYPES):
        exists = await db.webstore_questionnaire_templates.find_one(
            {"tenant_id": tenant_id, "scope": "tenant_default", "store_type": store_type},
            {"_id": 0, "id": 1, "source_template_id": 1},
            sort=[("version", -1)],
        )
        if exists:
            if exists.get("source_template_id") != QUESTIONNAIRE_TEMPLATE_SOURCE_ID:
                await db.webstore_questionnaire_templates.update_one(
                    {"tenant_id": tenant_id, "id": exists["id"]},
                    {
                        "$set": {
                            "version": 2,
                            "title": "Base Webstore Intake" if store_type == "base" else f"{store_type.replace('_', ' ').title()} Webstore Intake",
                            "sections": DEFAULT_TEMPLATE_SECTIONS[store_type],
                            "status": "active",
                            "source_template_id": QUESTIONNAIRE_TEMPLATE_SOURCE_ID,
                            "updated_at": _now_iso(),
                        }
                    },
                )
            continue
        doc = WebstoreQuestionnaireTemplate(
            tenant_id=tenant_id,
            scope="tenant_default",
            store_type=store_type,
            version=2,
            title="Base Webstore Intake" if store_type == "base" else f"{store_type.replace('_', ' ').title()} Webstore Intake",
            sections=DEFAULT_TEMPLATE_SECTIONS[store_type],
            status="active",
            source_template_id=QUESTIONNAIRE_TEMPLATE_SOURCE_ID,
        ).model_dump()
        await db.webstore_questionnaire_templates.insert_one(prepare_for_mongo(doc))
    await _seed_shared_webstore_form_templates(tenant_id)


async def _seed_shared_webstore_form_templates(tenant_id: str) -> None:
    async for template in db.webstore_questionnaire_templates.find(
        {"tenant_id": tenant_id, "source_template_id": QUESTIONNAIRE_TEMPLATE_SOURCE_ID},
        {"_id": 0},
    ):
        await _upsert_shared_form_template_for_webstore_template(tenant_id, serialize_doc(template))


async def _webstore_templates_for_store_types(tenant_id: str, template_types: list[str]) -> list[dict[str, Any]]:
    legacy_templates = [
        serialize_doc(d)
        async for d in db.webstore_questionnaire_templates.find(
            {"tenant_id": tenant_id, "store_type": {"$in": template_types}, "status": "active"},
            {"_id": 0},
        ).sort([("store_type", 1), ("version", -1)])
    ]
    shared_forms = [
        serialize_doc(d)
        async for d in db.form_templates.find(
            {
                "tenant_id": tenant_id,
                "module": "webstores",
                "context_type": "webstore",
                "status": "published",
                "$or": [
                    {"private_config.store_type": {"$in": template_types}},
                    {"private_config.store_type": {"$exists": False}},
                ],
            },
            {"_id": 0},
        ).sort([("updated_at", -1)])
    ]
    shared_by_source = {form.get("source_template_id"): form for form in shared_forms if form.get("source_template_id")}
    resolved = [
        _webstore_template_from_shared_form(shared_by_source[template["id"]], template)
        if template["id"] in shared_by_source
        else template
        for template in legacy_templates
    ]
    legacy_ids = {template["id"] for template in legacy_templates}
    for form in shared_forms:
        if form.get("source_template_id") in legacy_ids:
            continue
        private_config = form.get("private_config") or {}
        if private_config.get("adapter") and private_config.get("adapter") != WEBSTORE_FORM_ADAPTER:
            continue
        resolved.append(_webstore_template_from_shared_form(form))
    return resolved


async def _webstore_templates_for_store(store: dict) -> list[dict[str, Any]]:
    return await _webstore_templates_for_store_types(store["tenant_id"], ["base", store.get("store_type") or "general"])


async def list_questionnaire_templates(user: dict, *, store_type: Optional[str] = None, active_only: bool = False) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    await ensure_default_questionnaire_templates(user["tenant_id"])
    template_types = [store_type] if store_type else ["base", *WEBSTORE_TYPES, *LEGACY_WEBSTORE_TYPES]
    items = await _webstore_templates_for_store_types(user["tenant_id"], template_types)
    if active_only:
        items = [item for item in items if item.get("status") == "active"]
    return {"items": items}


async def save_questionnaire_template(user: dict, fields: dict[str, Any], template_id: Optional[str] = None) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_MANAGE)
    raise WebstoreSetupError(
        "form_maker_is_questionnaire_authority",
        "Webstore questionnaires are edited in Library/DocuLink Form Maker. Legacy Webstore questionnaire templates are migration-only.",
        409,
    )


async def bind_questionnaire_templates(user: dict, webstore_id: str) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    store = await _get_store(user["tenant_id"], webstore_id)
    await ensure_default_questionnaire_templates(user["tenant_id"])
    templates = await _webstore_templates_for_store(store)
    await db.webstores.update_one(
        {"tenant_id": user["tenant_id"], "id": webstore_id},
        {"$set": {"setup_requirements.questionnaire_template_ids": [t["id"] for t in templates], "updated_at": _now_iso()}},
    )
    return {"webstore_id": webstore_id, "templates": templates}


async def owner_questionnaire(identity: dict, webstore_id: str) -> dict:
    store = await _owner_store(identity, webstore_id)
    templates = await _bound_templates(store)
    submission = await db.webstore_questionnaire_submissions.find_one(
        {"tenant_id": identity["tenant_id"], "webstore_id": webstore_id, "portal_identity_id": identity["id"], "status": {"$in": ["draft", "returned_for_changes"]}},
        {"_id": 0},
    )
    return {"webstore": _owner_safe_store(store), "templates": templates, "submission": serialize_doc(submission) if submission else None}


async def _bound_templates(store: dict) -> list[dict]:
    tenant_id = store["tenant_id"]
    ids = ((store.get("setup_requirements") or {}).get("questionnaire_template_ids") or [])
    if ids:
        legacy = [serialize_doc(d) async for d in db.webstore_questionnaire_templates.find({"tenant_id": tenant_id, "id": {"$in": ids}, "status": "active"}, {"_id": 0})]
        forms = [
            serialize_doc(d)
            async for d in db.form_templates.find(
                {"tenant_id": tenant_id, "module": "webstores", "context_type": "webstore", "status": "published", "$or": [{"source_template_id": {"$in": ids}}, {"id": {"$in": ids}}]},
                {"_id": 0},
            )
        ]
        forms_by_source = {form.get("source_template_id"): form for form in forms if form.get("source_template_id")}
        resolved = [
            _webstore_template_from_shared_form(forms_by_source[item["id"]], item)
            if item["id"] in forms_by_source
            else item
            for item in legacy
        ]
        legacy_ids = {item["id"] for item in legacy}
        resolved.extend(_webstore_template_from_shared_form(form) for form in forms if form["id"] in ids and form.get("source_template_id") not in legacy_ids)
        return resolved
    await ensure_default_questionnaire_templates(tenant_id)
    return await _webstore_templates_for_store(store)


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
    missing_required = _missing_required_answers(draft.get("template_snapshot", {}).get("templates") or [], draft.get("answers") or {})
    if missing_required:
        raise WebstoreSetupError("questionnaire_required_answers_missing", f"Missing required answers: {', '.join(missing_required)}", 400)
    missing_info_flags = _missing_required_answer_flags(draft.get("template_snapshot", {}).get("templates") or [], draft.get("answers") or {})
    now = _now_iso()
    snapshot = {
        "answers": draft.get("answers") or {},
        "known_products": draft.get("known_products") or [],
        "missing_info_flags": missing_info_flags,
        "template_snapshot": draft.get("template_snapshot") or {},
        "submitted_at": now,
    }
    await db.webstore_questionnaire_submissions.update_one(
        {"tenant_id": identity["tenant_id"], "id": draft["id"]},
        {
            "$set": {
                "status": "submitted",
                "submitted_at": now,
                "submitted_snapshot": snapshot,
                "missing_info_flags": missing_info_flags,
                "updated_at": now,
            }
        },
    )
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
        summary="Webstore setup questionnaire submitted",
    )
    submitted = await db.webstore_questionnaire_submissions.find_one({"tenant_id": identity["tenant_id"], "id": draft["id"]}, {"_id": 0})
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
        metadata={"submission_id": draft["id"], "webstore_id": webstore_id},
    )
    return serialize_doc(submitted or {})


def _missing_required_answers(templates: list[dict], answers: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for template in templates:
        for section in template.get("sections") or []:
            for question in section.get("questions") or []:
                key = question.get("key")
                if (
                    question.get("required")
                    and (question.get("blocking_required") or key in BLOCKING_QUESTIONNAIRE_REQUIRED_KEYS)
                    and (answers.get(key) in (None, "", []))
                ):
                    missing.append(key)
    return missing


def _missing_required_answer_flags(templates: list[dict], answers: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for template in templates:
        for section in template.get("sections") or []:
            for question in section.get("questions") or []:
                key = question.get("key")
                if question.get("required") and (answers.get(key) in (None, "", [])):
                    missing.append(key)
    return missing


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

__all__ = ['ensure_default_questionnaire_templates', '_seed_shared_webstore_form_templates', '_webstore_templates_for_store_types', '_webstore_templates_for_store', 'list_questionnaire_templates', 'save_questionnaire_template', 'bind_questionnaire_templates', 'owner_questionnaire', '_bound_templates', 'save_questionnaire_draft', 'submit_questionnaire', '_missing_required_answers', '_missing_required_answer_flags', 'return_questionnaire', 'latest_questionnaire_response']
