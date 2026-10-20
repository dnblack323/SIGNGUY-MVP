"""Staff review of a submitted Webstore questionnaire, without AI.

One read model for the review overlay: a structured brief built from the frozen
template snapshot, the proposed draft-setting changes (same mapping the apply
step uses), deterministic consistency checks, and a comparison with the
previous revision.
"""
from __future__ import annotations

from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import serialize_doc
from .forms_service import invalid_answer_keys, visible_question_keys
from .webstore_setup_answer_applications import proposed_changes_for
from .webstore_setup_common import Perm, WebstoreSetupError, _get_store, _require_staff_perm
from .webstore_setup_contracts import SAFE_ANSWER_MAPPING
from .webstore_shop_settings import FULFILLMENT_METHODS, get_fulfillment_settings


def _sections(submission: dict) -> list[dict[str, Any]]:
    snapshot = submission.get("submitted_snapshot") or {}
    templates = (snapshot.get("template_snapshot") or {}).get("templates") or []
    return [s for t in templates for s in t.get("sections") or []]


def _answers(submission: dict) -> dict[str, Any]:
    return (submission.get("submitted_snapshot") or {}).get("answers") or submission.get("answers") or {}


def _display(question: dict[str, Any], value: Any) -> str:
    labels = {o.get("value"): o.get("label") for o in question.get("options") or []}
    if isinstance(value, dict):
        return str(value.get("file_name") or value.get("name") or "")
    if isinstance(value, (list, tuple)):
        return ", ".join(str(labels.get(v, v)) for v in value)
    return str(labels.get(value, value))


def build_brief(submission: dict) -> list[dict[str, Any]]:
    sections = _sections(submission)
    answers = _answers(submission)
    visible = visible_question_keys({"sections": sections}, answers)
    brief = []
    for section in sections:
        items = [
            {"key": q["key"], "label": q.get("label") or q["key"], "value": _display(q, answers[q["key"]]),
             "affects_settings": q["key"] in SAFE_ANSWER_MAPPING or q["key"].startswith("pickup_window_")}
            for q in section.get("questions") or []
            if q.get("type") not in {"heading", "paragraph"} and q.get("key") in visible and answers.get(q["key"]) not in (None, "", [])
        ]
        if items:
            brief.append({"id": section.get("id"), "title": section.get("title"), "items": items})
    return brief


def consistency_checks(store: dict, submission: dict, shop: dict) -> list[dict[str, str]]:
    """The approved core checks. Dates compare as ISO strings (YYYY-MM-DD)."""
    answers = _answers(submission)
    sections = _sections(submission)
    visible = visible_question_keys({"sections": sections}, answers)
    shown = {k: v for k, v in answers.items() if k in visible}
    warnings: list[dict[str, str]] = []

    def warn(code: str, message: str) -> None:
        warnings.append({"code": code, "message": message})

    opens, closes = str(shown.get("target_launch_at") or ""), str(shown.get("deadline_at") or "")
    if opens and closes and closes < opens:
        warn("closing_before_opening", f"Ordering closes ({closes}) before the store opens ({opens}).")
    event_date = str(shown.get("event_start_at") or "")
    for n in range(1, 4):
        date = str(shown.get(f"pickup_window_{n}_date") or "")
        start, end = str(shown.get(f"pickup_window_{n}_start") or ""), str(shown.get(f"pickup_window_{n}_end") or "")
        if not date:
            continue
        if opens and date < opens:
            warn("pickup_before_store_opens", f"Pickup window {n} ({date}) is before the store opens ({opens}).")
        if event_date and date > event_date:
            warn("pickup_after_event", f"Pickup window {n} ({date}) is after the event ({event_date}).")
        if start and end and end <= start:
            warn("pickup_window_times_invalid", f"Pickup window {n} ends before it starts.")
    methods = list(shown.get("fulfillment_methods") or [])
    unsupported = [m for m in methods if m not in set(shop.get("supported_methods") or [])]
    if unsupported:
        names = ", ".join(FULFILLMENT_METHODS.get(m, m) for m in unsupported)
        warn("unsupported_fulfillment_method", f"The shop does not offer: {names}.")
    donations = any(str(shown.get(k)) == "yes" for k in ("allow_checkout_donations", "event_checkout_donations"))
    purpose = any(shown.get(k) for k in ("fundraiser_purpose", "event_fundraiser_purpose", "team_fundraiser_purpose"))
    if donations and not purpose:
        warn("donations_without_purpose", "Checkout donations are on, but the fundraiser purpose is missing.")
    if str(shown.get("bag_label_orders")) == "yes" and methods and set(methods) <= {"individual_shipping"}:
        warn("bagging_with_individual_shipping", "Bagging and labeling was chosen, but every order ships individually.")
    missing = invalid_answer_keys({"sections": sections}, answers)
    if missing:
        warn("required_answers_missing", f"Required answers are missing or invalid: {', '.join(missing)}.")
    return warnings


def compare_revisions(previous: Optional[dict], current: dict) -> list[dict[str, Any]]:
    """Answer-level differences between two revisions; material changes are flagged."""
    if not previous:
        return []
    def shown(sub: dict) -> dict[str, Any]:
        answers = _answers(sub)
        visible = visible_question_keys({"sections": _sections(sub)}, answers) if _sections(sub) else set(answers)
        return {k: v for k, v in answers.items() if k in visible and v not in (None, "", [])}
    before, after = shown(previous), shown(current)
    labels = {q["key"]: q.get("label") or q["key"] for s in _sections(current) + _sections(previous) for q in s.get("questions") or []}
    rows = []
    for key in sorted(set(before) | set(after), key=lambda k: list(labels).index(k) if k in labels else 999):
        if before.get(key) == after.get(key):
            continue
        change = "added" if key not in before else "removed" if key not in after else "changed"
        mapping = SAFE_ANSWER_MAPPING.get(key) or {}
        is_window = key.startswith("pickup_window_")
        rows.append({
            "key": key, "label": labels.get(key, key), "change": change,
            "previous": before.get(key), "current": after.get(key),
            "affects_settings": bool(mapping) or is_window,
            "material": bool(mapping.get("material")) or is_window,
        })
    return rows


async def questionnaire_review(user: dict, webstore_id: str) -> dict[str, Any]:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    store = await _get_store(user["tenant_id"], webstore_id)
    submission = await db.webstore_questionnaire_submissions.find_one(
        {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "revision": {"$ne": None}},
        {"_id": 0}, sort=[("revision", -1)],
    )
    if not submission:
        raise WebstoreSetupError("questionnaire_submission_not_found", "No submitted questionnaire yet", 404)
    previous = None
    if submission.get("supersedes_submission_id"):
        previous = await db.webstore_questionnaire_submissions.find_one(
            {"tenant_id": user["tenant_id"], "id": submission["supersedes_submission_id"]}, {"_id": 0}
        )
    shop = await get_fulfillment_settings(user["tenant_id"])
    answers = _answers(submission)
    visible = visible_question_keys({"sections": _sections(submission)}, answers)
    keys = [k for k in answers if k in visible and (k in SAFE_ANSWER_MAPPING or k.startswith("pickup_window_"))]
    proposed, rejected = proposed_changes_for(store, answers, visible, keys, {})
    return {
        "webstore_id": webstore_id,
        "submission": serialize_doc(submission),
        "previous_revision": previous.get("revision") if previous else None,
        "brief": build_brief(submission),
        "proposed_changes": proposed,
        "rejected_changes": rejected,
        "warnings": consistency_checks(store, submission, shop),
        "comparison": compare_revisions(previous, submission),
        "can_apply": submission.get("status") == "submitted",
    }

