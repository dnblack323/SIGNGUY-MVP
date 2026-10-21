"""Safe preview, application, and reversal of owner questionnaire answers."""
from __future__ import annotations

from ..core.money import dollars_to_cents
from .forms_service import visible_question_keys
from .webstore_setup_common import *


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


def _transform(value: Any, transform: Optional[str]) -> Any:
    """Convert an owner answer into the stored setting value. Money uses the single cents boundary."""
    if transform == "yes_bool":
        return str(value).strip().lower() in {"yes", "true", "1"}
    if transform == "list":
        return list(value) if isinstance(value, (list, tuple)) else [value]
    if transform == "number":
        return float(value)
    if transform == "dollars_to_cents":
        return dollars_to_cents(value)
    if transform == "access_mode":
        return "restricted" if str(value) == "private" else "open"
    return value


def _pickup_windows(answers: dict[str, Any], visible: set[str]) -> list[dict[str, Any]]:
    windows = []
    for n in range(1, 4):
        window = {f: answers.get(f"pickup_window_{n}_{f}") for f in PICKUP_WINDOW_FIELDS if f"pickup_window_{n}_{f}" in visible}
        if window.get("date"):
            windows.append({f: (window.get(f) or "") for f in PICKUP_WINDOW_FIELDS})
    return windows


def _visible_answer_keys(submission: dict) -> set[str]:
    snapshot = submission.get("submitted_snapshot") or {}
    templates = (snapshot.get("template_snapshot") or submission.get("template_snapshot") or {}).get("templates") or []
    answers = snapshot.get("answers") or submission.get("answers") or {}
    if not templates:
        return set(answers)
    return visible_question_keys({"sections": [s for t in templates for s in t.get("sections") or []]}, answers)


def proposed_changes_for(store: dict, answers: dict[str, Any], visible: set[str], keys: list[str], proposed_values: dict[str, Any]) -> tuple[list[dict], list[dict]]:
    """Map answers onto draft Webstore fields. Hidden (stale) answers are never applied."""
    proposed: dict[str, dict[str, Any]] = {}
    rejected: list[dict[str, Any]] = []
    for key in keys:
        if key not in answers or key not in visible:
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
        if value is None or value == "" or value == []:
            continue
        try:
            value = _transform(value, mapping.get("transform"))
        except (TypeError, ValueError, ArithmeticError):
            rejected.append({"answer_key": key, "reason": "invalid_value"})
            continue
        target = mapping["target"]
        proposed[target] = {"answer_key": key, "target": target, "label": mapping["label"], "from": _get_path(store, target), "to": value}
        if key == "fulfillment_methods" and value:
            primary = "store_settings.fulfillment.method"
            proposed[primary] = {"answer_key": key, "target": primary, "label": "Primary fulfillment method", "from": _get_path(store, primary), "to": value[0]}
    if any(k.startswith("pickup_window_") for k in keys):
        windows = _pickup_windows(answers, visible)
        if windows:
            proposed[PICKUP_WINDOWS_TARGET] = {"answer_key": "pickup_windows", "target": PICKUP_WINDOWS_TARGET, "label": "Pickup windows", "from": _get_path(store, PICKUP_WINDOWS_TARGET), "to": windows}
    return list(proposed.values()), rejected


async def answer_application_preview(user: dict, webstore_id: str, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    store = await _get_store(user["tenant_id"], webstore_id)
    submission_id = fields.get("submission_id")
    submission = await db.webstore_questionnaire_submissions.find_one({"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "id": submission_id}, {"_id": 0})
    if not submission or submission.get("status") not in {"submitted", "reviewed"}:
        raise WebstoreSetupError("submitted_questionnaire_required", "A submitted questionnaire is required", 409)
    answers = submission.get("submitted_snapshot", {}).get("answers") or submission.get("answers") or {}
    visible = _visible_answer_keys(submission)
    if fields.get("apply_all"):
        selected = [k for k in answers if k in visible and (k in SAFE_ANSWER_MAPPING or k.startswith("pickup_window_"))]
    else:
        selected = fields.get("selected_answer_keys") or []
    if not selected:
        raise WebstoreSetupError("selected_answers_required", "Select at least one questionnaire answer to apply", 400)
    proposed, rejected = proposed_changes_for(store, answers, visible, selected, fields.get("proposed_values") or {})
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
    return {"application": serialize_doc(app_doc), "idempotent_replay": False}


async def approve_and_apply(user: dict, webstore_id: str, submission_id: str) -> dict:
    """Review overlay "Approve & Apply": apply every mapped, visible answer in one step (idempotent)."""
    submission = await db.webstore_questionnaire_submissions.find_one(
        {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "id": submission_id}, {"_id": 0, "status": 1}
    )
    if not submission:
        raise WebstoreSetupError("questionnaire_submission_not_found", "Questionnaire submission not found", 404)
    key = f"approve:{submission_id}"
    if submission.get("status") != "submitted":
        existing = await db.webstore_answer_applications.find_one({"tenant_id": user["tenant_id"], "idempotency_key": key}, {"_id": 0})
        if existing:
            return {"application": serialize_doc(existing), "idempotent_replay": True}
        raise WebstoreSetupError("questionnaire_not_approvable", "Only a submitted questionnaire can be approved", 409)
    # Applying marks the revision reviewed, which moves setup_state on to setup_in_progress.
    return await apply_questionnaire_answers(user, webstore_id, {
        "submission_id": submission_id, "apply_all": True, "idempotency_key": key, "reason": "Approved & applied from questionnaire review",
    })


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

__all__ = ['_get_path', '_set_path', '_field_updates_from_changes', 'proposed_changes_for', 'answer_application_preview', 'apply_questionnaire_answers', 'approve_and_apply', 'reverse_answer_application']
