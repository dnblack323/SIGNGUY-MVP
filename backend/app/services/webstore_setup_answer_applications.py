"""Safe preview, application, and reversal of owner questionnaire answers."""
from __future__ import annotations

from .webstore_setup_common import *
from .webstore_setup_progress import _refresh_setup_state


def _get_path(data: dict, path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _set_path(updates: dict, path: str, value: Any) -> None:
    current = updates
    parts = path.split(".")
    for part in parts[:-1]:
        current = current.setdefault(part, {})
    current[parts[-1]] = value


def _field_updates_from_changes(changes: list[dict[str, Any]]) -> dict:
    updates: dict[str, Any] = {}
    for change in changes:
        updates[change["target"]] = change["to"]
    return updates


async def answer_application_preview(user: dict, webstore_id: str, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    store = await _get_store(user["tenant_id"], webstore_id)
    submission_id = fields.get("submission_id")
    submission = await db.webstore_questionnaire_submissions.find_one({"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "id": submission_id}, {"_id": 0})
    if not submission or submission.get("status") not in {"submitted", "reviewed"}:
        raise WebstoreSetupError("submitted_questionnaire_required", "A submitted questionnaire is required", 409)
    answers = submission.get("submitted_snapshot", {}).get("answers") or submission.get("answers") or {}
    selected = fields.get("selected_answer_keys") or []
    if not selected:
        raise WebstoreSetupError("selected_answers_required", "Select at least one questionnaire answer to apply", 400)
    proposed: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    proposed_values = fields.get("proposed_values") or {}
    for key in selected:
        if key not in answers:
            rejected.append({"answer_key": key, "reason": "answer_not_found"})
            continue
        if key in LOCKED_ANSWER_FIELDS:
            rejected.append({"answer_key": key, "reason": "locked_field"})
            continue
        mapping = SAFE_ANSWER_MAPPING.get(key)
        if not mapping:
            rejected.append({"answer_key": key, "reason": "no_safe_mapping"})
            continue
        value = proposed_values.get(key, answers.get(key))
        if value is None or value == "":
            continue
        target = mapping["target"]
        proposed.append(
            {
                "answer_key": key,
                "target": target,
                "label": mapping["label"],
                "from": _get_path(store, target),
                "to": value,
            }
        )
    return {"webstore_id": webstore_id, "submission_id": submission_id, "proposed_changes": proposed, "rejected_changes": rejected, "dry_run": True}


async def apply_questionnaire_answers(user: dict, webstore_id: str, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_MANAGE)
    reason = _clean_text(fields.get("reason"), "reason", limit=1000)
    key = _clean_text(fields.get("idempotency_key"), "idempotency_key", limit=200)
    existing = await db.webstore_answer_applications.find_one({"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "idempotency_key": key}, {"_id": 0})
    if existing:
        return {"application": serialize_doc(existing), "idempotent_replay": True}
    preview = await answer_application_preview(user, webstore_id, fields)
    updates = _field_updates_from_changes(preview["proposed_changes"])
    if not updates:
        raise WebstoreSetupError("no_safe_answers_to_apply", "No safe questionnaire answers were selected for application", 409)
    updates["updated_at"] = _now_iso()
    await db.webstores.update_one({"tenant_id": user["tenant_id"], "id": webstore_id}, {"$set": updates})
    await db.webstore_questionnaire_submissions.update_one(
        {"tenant_id": user["tenant_id"], "id": fields.get("submission_id")},
        {"$set": {"status": "reviewed", "reviewed_at": _now_iso(), "updated_at": _now_iso()}},
    )
    app_doc = WebstoreAnswerApplication(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        submission_id=fields.get("submission_id"),
        idempotency_key=key,
        actor_user_id=user.get("id"),
        actor_email=user.get("email"),
        reason=reason,
        proposed_changes=preview["proposed_changes"],
        applied_changes=preview["proposed_changes"],
        rejected_changes=preview["rejected_changes"],
    ).model_dump()
    await db.webstore_answer_applications.insert_one(prepare_for_mongo(app_doc))
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user.get("id"),
        actor_email=user.get("email"),
        action="webstore.questionnaire_answers_applied",
        entity_type="webstore_answer_application",
        entity_id=app_doc["id"],
        summary="Safe Webstore questionnaire answers applied",
        metadata={"idempotency_key": key},
    )
    await _refresh_setup_state(user["tenant_id"], webstore_id)
    return {"application": serialize_doc(app_doc), "idempotent_replay": False}


async def reverse_answer_application(user: dict, webstore_id: str, application_id: str, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_MANAGE)
    reason = _clean_text(fields.get("reason"), "reason", limit=1000)
    original = await db.webstore_answer_applications.find_one(
        {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "id": application_id, "status": "applied"},
        {"_id": 0},
    )
    if not original:
        raise WebstoreSetupError("answer_application_not_found", "Applied answer application not found", 404)
    reversal_changes = [{**change, "from": change.get("to"), "to": change.get("from")} for change in original.get("applied_changes", [])]
    current_store = await _get_store(user["tenant_id"], webstore_id)
    conflicts = [
        change
        for change in original.get("applied_changes", [])
        if _get_path(current_store, change["target"]) != change.get("to")
    ]
    if conflicts:
        raise WebstoreSetupError("answer_reversal_conflict", "Answer application cannot be reversed because newer changes touched the same fields", 409)
    updates = _field_updates_from_changes(reversal_changes)
    updates["updated_at"] = _now_iso()
    await db.webstores.update_one({"tenant_id": user["tenant_id"], "id": webstore_id}, {"$set": updates})
    await db.webstore_answer_applications.update_one(
        {"tenant_id": user["tenant_id"], "id": application_id},
        {"$set": {"status": "reversed", "reversed_at": _now_iso(), "updated_at": _now_iso()}},
    )
    key = fields.get("idempotency_key") or f"reverse:{application_id}"
    reversal = WebstoreAnswerApplication(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        submission_id=original["submission_id"],
        idempotency_key=key,
        actor_user_id=user.get("id"),
        actor_email=user.get("email"),
        reason=reason,
        proposed_changes=reversal_changes,
        applied_changes=reversal_changes,
        rejected_changes=[],
        reversal_of_application_id=application_id,
    ).model_dump()
    await db.webstore_answer_applications.insert_one(prepare_for_mongo(reversal))
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor_type="staff",
        actor_id=user.get("id"),
        actor_email=user.get("email"),
        action="webstore.questionnaire_answers_reversed",
        entity_type="webstore_answer_application",
        entity_id=reversal["id"],
        summary="Webstore questionnaire answer application reversed",
        metadata={"reversal_of_application_id": application_id},
    )
    return {"application": serialize_doc(reversal)}

__all__ = ['_get_path', '_set_path', '_field_updates_from_changes', 'answer_application_preview', 'apply_questionnaire_answers', 'reverse_answer_application']
