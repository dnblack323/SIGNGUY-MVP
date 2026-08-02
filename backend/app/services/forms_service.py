"""Shared form maker service.

This is the single foundation for Webstore questionnaires, client/design forms,
and training quizzes. Module-specific adapters attach context and mapping rules.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import re
from typing import Any, Optional

from pymongo.errors import DuplicateKeyError

from ..core.db import db
from ..core.portal_security import generate_raw_token, hash_token
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.forms import (
    FORM_CONTEXT_TYPES,
    FORM_FIELD_TYPES,
    FORM_REQUEST_STATUSES,
    FORM_TEMPLATE_STATUSES,
    FormRequest,
    FormResponse,
    FormTemplate,
)
from .activity import record_activity_with_audit


class FormsError(Exception):
    def __init__(self, code: str, detail: str, status_code: int = 400):
        self.code = code
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def _now_iso() -> str:
    return utc_now().isoformat()


def _clean_text(value: Any, field: str, *, limit: int = 160) -> str:
    text = str(value or "").strip()
    if not text:
        raise FormsError(f"{field}_required", f"{field.replace('_', ' ').title()} is required", 400)
    return text[:limit]


def _clean_optional_text(value: Any, *, limit: int = 500) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text[:limit] if text else None


def _validate_context_type(value: Any) -> str:
    context_type = str(value or "general").strip().lower()
    if context_type not in FORM_CONTEXT_TYPES:
        raise FormsError("invalid_form_context_type", "Unsupported form context type", 400)
    return context_type


def _validate_sections(sections: Any, *, questions: Any = None, allow_private_config: bool = True) -> list[dict[str, Any]]:
    if (not sections) and isinstance(questions, list):
        sections = [{"id": "main", "title": "Questions", "questions": questions}]
    if not isinstance(sections, list):
        raise FormsError("invalid_form_sections", "Form sections must be a list", 400)
    cleaned: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for section_index, section in enumerate(sections):
        if not isinstance(section, dict):
            raise FormsError("invalid_form_section", "Each form section must be an object", 400)
        section_id = str(section.get("id") or f"section_{section_index + 1}").strip()
        title = str(section.get("title") or f"Section {section_index + 1}").strip()
        questions = section.get("questions") or []
        if not isinstance(questions, list):
            raise FormsError("invalid_form_questions", "Section questions must be a list", 400)
        cleaned_questions: list[dict[str, Any]] = []
        for question_index, question in enumerate(questions):
            if not isinstance(question, dict):
                raise FormsError("invalid_form_question", "Each form question must be an object", 400)
            key = str(question.get("key") or f"q_{section_index + 1}_{question_index + 1}").strip()
            if key in seen_keys:
                raise FormsError("duplicate_form_question_key", f"Duplicate form question key: {key}", 400)
            seen_keys.add(key)
            field_type = str(question.get("type") or "text").strip()
            if field_type not in FORM_FIELD_TYPES:
                raise FormsError("invalid_form_question_type", f"Unsupported form question type: {field_type}", 400)
            item = {
                "id": str(question.get("id") or key),
                "key": key,
                "label": str(question.get("label") or question.get("prompt") or key.replace("_", " ")).strip(),
                "type": field_type,
                "required": bool(question.get("required", False)),
                "description": _clean_optional_text(question.get("description")),
                "placeholder": _clean_optional_text(question.get("placeholder"), limit=180),
                "options": _clean_options(question.get("options") or question.get("choices") or []),
                "validation": question.get("validation") if isinstance(question.get("validation"), dict) else {},
                "conditional": question.get("conditional") if isinstance(question.get("conditional"), dict) else {},
                "conditional_visibility": question.get("conditional_visibility") if isinstance(question.get("conditional_visibility"), dict) else {},
                "file_settings": question.get("file_settings") if isinstance(question.get("file_settings"), dict) else {},
                "accept_file_types": question.get("accept_file_types") or ((question.get("file_settings") or {}).get("accept") if isinstance(question.get("file_settings"), dict) else None) or [],
                "max_file_size_mb": question.get("max_file_size_mb") or ((question.get("file_settings") or {}).get("max_file_size_mb") if isinstance(question.get("file_settings"), dict) else None) or 10,
                "mapping": question.get("mapping") if isinstance(question.get("mapping"), dict) else {},
                "order": int(question.get("order") or question_index),
            }
            if allow_private_config and isinstance(question.get("private_config"), dict):
                item["private_config"] = deepcopy(question["private_config"])
            cleaned_questions.append(item)
        cleaned.append({"id": section_id, "title": title, "description": _clean_optional_text(section.get("description")), "questions": cleaned_questions})
    return cleaned


def _clean_options(options: Any) -> list[dict[str, str]]:
    if not isinstance(options, list):
        return []
    cleaned = []
    for index, option in enumerate(options):
        if isinstance(option, dict):
            value = str(option.get("value") if option.get("value") is not None else option.get("label") or index).strip()
            label = str(option.get("label") if option.get("label") is not None else value).strip()
        else:
            value = str(option).strip()
            label = value
        if value or label:
            cleaned.append({"value": value, "label": label or value})
    return cleaned


def public_template_view(template: dict[str, Any]) -> dict[str, Any]:
    safe = serialize_doc(template)
    safe.pop("private_config", None)
    for section in safe.get("sections") or []:
        for question in section.get("questions") or []:
            question.pop("private_config", None)
    return safe


async def create_template(*, tenant_id: str, user: dict, payload: dict[str, Any]) -> dict:
    module = str(payload.get("module") or "general").strip().lower()
    status = str(payload.get("status") or "draft").strip().lower()
    if status not in FORM_TEMPLATE_STATUSES:
        raise FormsError("invalid_form_template_status", "Unsupported form template status", 400)
    template = FormTemplate(
        tenant_id=tenant_id,
        name=_clean_text(payload.get("name"), "name"),
        module=module,
        context_type=_validate_context_type(payload.get("context_type")),
        description=_clean_optional_text(payload.get("description")),
        status=status,
        sections=_validate_sections(payload.get("sections") or [], questions=payload.get("questions")),
        mapping_config=payload.get("mapping_config") if isinstance(payload.get("mapping_config"), dict) else {},
        private_config=payload.get("private_config") if isinstance(payload.get("private_config"), dict) else {},
        source_template_id=payload.get("source_template_id"),
        created_by_user_id=user.get("id"),
        updated_by_user_id=user.get("id"),
    ).model_dump()
    await db.form_templates.insert_one(prepare_for_mongo(template))
    await record_activity_with_audit(
        tenant_id=tenant_id,
        actor_user_id=user.get("id"),
        actor_email=user.get("email"),
        module="forms",
        action="form_template_created",
        entity_type="form_template",
        entity_id=template["id"],
        summary=f"Form template created: {template['name']}",
        metadata={"module": module, "context_type": template["context_type"]},
    )
    return serialize_doc(template)


async def list_templates(*, tenant_id: str, module: Optional[str] = None, context_type: Optional[str] = None, include_archived: bool = False) -> dict:
    q: dict[str, Any] = {"tenant_id": tenant_id}
    if module:
        q["module"] = module
    if context_type:
        q["context_type"] = _validate_context_type(context_type)
    if not include_archived:
        q["status"] = {"$ne": "archived"}
    items = [serialize_doc(doc) async for doc in db.form_templates.find(q, {"_id": 0}).sort([("updated_at", -1)])]
    return {"items": items}


async def get_template(*, tenant_id: str, template_id: str) -> dict:
    doc = await db.form_templates.find_one({"tenant_id": tenant_id, "id": template_id}, {"_id": 0})
    if not doc:
        raise FormsError("form_template_not_found", "Form template not found", 404)
    return serialize_doc(doc)


async def update_template(*, tenant_id: str, template_id: str, user: dict, payload: dict[str, Any]) -> dict:
    existing = await get_template(tenant_id=tenant_id, template_id=template_id)
    updates: dict[str, Any] = {"updated_by_user_id": user.get("id")}
    if "name" in payload:
        updates["name"] = _clean_text(payload.get("name"), "name")
    if "description" in payload:
        updates["description"] = _clean_optional_text(payload.get("description"))
    if "module" in payload:
        updates["module"] = str(payload.get("module") or "general").strip().lower()
    if "context_type" in payload:
        updates["context_type"] = _validate_context_type(payload.get("context_type"))
    if "sections" in payload or "questions" in payload:
        updates["sections"] = _validate_sections(payload.get("sections") or [], questions=payload.get("questions"))
        updates["version"] = int(existing.get("version") or 1) + 1
        if existing.get("status") == "published":
            updates["status"] = "draft"
    if "mapping_config" in payload and isinstance(payload.get("mapping_config"), dict):
        updates["mapping_config"] = payload["mapping_config"]
    if "private_config" in payload and isinstance(payload.get("private_config"), dict):
        updates["private_config"] = payload["private_config"]
    if "status" in payload:
        status = str(payload.get("status") or existing.get("status")).strip().lower()
        if status not in FORM_TEMPLATE_STATUSES:
            raise FormsError("invalid_form_template_status", "Unsupported form template status", 400)
        updates["status"] = status
    updates["updated_at"] = _now_iso()
    await db.form_templates.update_one({"tenant_id": tenant_id, "id": template_id}, {"$set": prepare_for_mongo(updates)})
    return await get_template(tenant_id=tenant_id, template_id=template_id)


async def duplicate_template(*, tenant_id: str, template_id: str, user: dict) -> dict:
    existing = await get_template(tenant_id=tenant_id, template_id=template_id)
    payload = {
        "name": f"{existing['name']} Copy",
        "module": existing.get("module"),
        "context_type": existing.get("context_type"),
        "description": existing.get("description"),
        "sections": existing.get("sections") or [],
        "mapping_config": existing.get("mapping_config") or {},
        "private_config": existing.get("private_config") or {},
        "source_template_id": existing.get("source_template_id") or existing["id"],
    }
    return await create_template(tenant_id=tenant_id, user=user, payload=payload)


async def create_request(*, tenant_id: str, user: dict, payload: dict[str, Any]) -> dict:
    template = await get_template(tenant_id=tenant_id, template_id=payload.get("template_id"))
    if template.get("status") != "published":
        raise FormsError("published_form_template_required", "Publish the form template before creating a public request", 409)
    status = str(payload.get("status") or "pending").strip().lower()
    if status not in FORM_REQUEST_STATUSES:
        raise FormsError("invalid_form_request_status", "Unsupported form request status", 400)
    raw_token = generate_raw_token()
    expires_at = _clean_optional_text(payload.get("expires_at"), limit=80)
    if not expires_at:
        expires_at = (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()
    request = FormRequest(
        tenant_id=tenant_id,
        template_id=template["id"],
        template_version=template.get("version") or 1,
        template_snapshot=public_template_view(template),
        context_type=_validate_context_type(payload.get("context_type") or template.get("context_type")),
        context_id=_clean_optional_text(payload.get("context_id"), limit=120),
        recipient_email=_clean_optional_text(payload.get("recipient_email"), limit=200),
        recipient_name=_clean_optional_text(payload.get("recipient_name"), limit=160),
        token_hash=hash_token(raw_token),
        status=status,
        expires_at=expires_at,
        consent_metadata=payload.get("consent_metadata") if isinstance(payload.get("consent_metadata"), dict) else {},
        created_by_user_id=user.get("id"),
    ).model_dump()
    try:
        await db.form_requests.insert_one(prepare_for_mongo(request))
    except DuplicateKeyError:
        raise FormsError("form_request_token_collision", "Unable to create unique form request token", 409)
    response = serialize_doc(request)
    response["request_token"] = raw_token
    response["public_path"] = f"/forms/request/{raw_token}"
    return response


async def list_requests(*, tenant_id: str, context_type: Optional[str] = None, context_id: Optional[str] = None) -> dict:
    q: dict[str, Any] = {"tenant_id": tenant_id}
    if context_type:
        q["context_type"] = _validate_context_type(context_type)
    if context_id:
        q["context_id"] = context_id
    items = [serialize_doc(doc) async for doc in db.form_requests.find(q, {"_id": 0, "token_hash": 0}).sort([("created_at", -1)])]
    return {"items": items}


async def get_request_by_token(*, raw_token: str, mark_opened: bool = True) -> dict:
    doc = await db.form_requests.find_one({"token_hash": hash_token(raw_token)}, {"_id": 0})
    if not doc or doc.get("status") in {"revoked", "expired"}:
        raise FormsError("form_request_not_found", "Form request not found", 404)
    if doc.get("status") == "submitted":
        raise FormsError("form_request_already_submitted", "This form request has already been submitted", 409)
    if doc.get("expires_at"):
        try:
            expires_at = datetime.fromisoformat(str(doc["expires_at"]).replace("Z", "+00:00"))
            if expires_at < datetime.now(timezone.utc):
                await db.form_requests.update_one({"id": doc["id"]}, {"$set": {"status": "expired", "updated_at": _now_iso()}})
                raise FormsError("form_request_expired", "Form request expired", 410)
        except ValueError:
            pass
    if mark_opened and not doc.get("opened_at"):
        now = _now_iso()
        await db.form_requests.update_one({"id": doc["id"]}, {"$set": {"status": "opened", "opened_at": now, "updated_at": now}})
        doc["status"] = "opened"
        doc["opened_at"] = now
    template = doc.get("template_snapshot")
    if not template:
        template = public_template_view(await get_template(tenant_id=doc["tenant_id"], template_id=doc["template_id"]))
    safe_request = serialize_doc({k: v for k, v in doc.items() if k != "token_hash"})
    return {"request": safe_request, "template": template}


async def submit_response_by_token(*, raw_token: str, payload: dict[str, Any]) -> dict:
    bundle = await get_request_by_token(raw_token=raw_token, mark_opened=False)
    request = bundle["request"]
    template = bundle["template"]
    answers = payload.get("answers") if isinstance(payload.get("answers"), dict) else {}
    attachments = payload.get("attachments") if isinstance(payload.get("attachments"), list) else []
    _validate_response_answers(template, answers)
    response = FormResponse(
        tenant_id=request["tenant_id"],
        request_id=request["id"],
        template_id=template["id"],
        template_version=request.get("template_version") or template.get("version") or 1,
        context_type=request.get("context_type") or template.get("context_type") or "general",
        context_id=request.get("context_id"),
        respondent_email=_clean_optional_text(payload.get("respondent_email") or request.get("recipient_email"), limit=200),
        respondent_name=_clean_optional_text(payload.get("respondent_name") or request.get("recipient_name"), limit=160),
        answers=deepcopy(answers),
        attachments=await _safe_attachment_refs(attachments, tenant_id=request["tenant_id"]),
        submitted_snapshot={"answers": deepcopy(answers), "template": deepcopy(template), "consent": payload.get("consent_metadata") or {}},
    ).model_dump()
    await db.form_responses.insert_one(prepare_for_mongo(response))
    now = _now_iso()
    await db.form_requests.update_one(
        {"id": request["id"], "tenant_id": request["tenant_id"]},
        {"$set": {"status": "submitted", "submitted_at": now, "updated_at": now}},
    )
    return serialize_doc(response)


def _answer_is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def _question_is_visible(question: dict[str, Any], answers: dict[str, Any]) -> bool:
    rule = question.get("conditional") or question.get("conditional_visibility") or {}
    if not isinstance(rule, dict):
        return True
    depends_on = rule.get("depends_on") or rule.get("question_key")
    if not depends_on:
        return True
    operator = str(rule.get("operator") or "equals").lower()
    expected = rule.get("value")
    actual = answers.get(depends_on)
    if operator == "not_equals":
        return str(actual) != str(expected)
    if operator in {"contains", "includes"}:
        if isinstance(actual, (list, tuple, set)):
            return expected in actual or str(expected) in [str(item) for item in actual]
        return str(expected) in str(actual or "")
    if operator in {"greater_than", "less_than"}:
        try:
            actual_number = float(actual)
            expected_number = float(expected)
        except (TypeError, ValueError):
            return False
        return actual_number > expected_number if operator == "greater_than" else actual_number < expected_number
    return str(actual) == str(expected)


def _validate_response_answers(template: dict[str, Any], answers: dict[str, Any]) -> None:
    errors: list[str] = []
    for section in template.get("sections") or []:
        for question in section.get("questions") or []:
            if question.get("type") in {"heading", "paragraph"} or not _question_is_visible(question, answers):
                continue
            key = question.get("key")
            value = answers.get(key)
            if question.get("required") and _answer_is_empty(value):
                errors.append(str(key))
                continue
            if _answer_is_empty(value):
                continue
            validation = question.get("validation") if isinstance(question.get("validation"), dict) else {}
            if question.get("type") == "email" and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", str(value)):
                errors.append(str(key))
            if question.get("type") == "number":
                try:
                    number_value = float(value)
                except (TypeError, ValueError):
                    errors.append(str(key))
                    continue
                if validation.get("min") is not None and number_value < float(validation["min"]):
                    errors.append(str(key))
                if validation.get("max") is not None and number_value > float(validation["max"]):
                    errors.append(str(key))
            text_value = str(value)
            if validation.get("min_length") is not None and len(text_value) < int(validation["min_length"]):
                errors.append(str(key))
            if validation.get("max_length") is not None and len(text_value) > int(validation["max_length"]):
                errors.append(str(key))
            if validation.get("pattern") and not re.match(str(validation["pattern"]), text_value):
                errors.append(str(key))
    if errors:
        raise FormsError("form_response_validation_failed", f"Invalid or missing answers: {', '.join(sorted(set(errors)))}", 400)


async def _safe_attachment_refs(attachments: list[Any], *, tenant_id: str) -> list[dict[str, Any]]:
    safe = []
    for item in attachments:
        if not isinstance(item, dict):
            continue
        ref = {k: item.get(k) for k in ("file_id", "file_name", "content_type", "size_bytes", "field_key") if item.get(k) is not None}
        if ref.get("file_id"):
            existing = await db.files.find_one({"tenant_id": tenant_id, "id": ref["file_id"], "archived": {"$ne": True}}, {"_id": 0, "id": 1})
            if not existing:
                raise FormsError("form_attachment_file_not_found", "Attachment file was not found for this tenant", 404)
        if ref:
            safe.append(ref)
    return safe


async def list_responses(*, tenant_id: str, template_id: Optional[str] = None, context_type: Optional[str] = None, context_id: Optional[str] = None) -> dict:
    q: dict[str, Any] = {"tenant_id": tenant_id}
    if template_id:
        q["template_id"] = template_id
    if context_type:
        q["context_type"] = _validate_context_type(context_type)
    if context_id:
        q["context_id"] = context_id
    items = [serialize_doc(doc) async for doc in db.form_responses.find(q, {"_id": 0}).sort([("created_at", -1)])]
    return {"items": items}


async def review_response(*, tenant_id: str, response_id: str, user: dict, mapping_results: Optional[list[dict[str, Any]]] = None) -> dict:
    doc = await db.form_responses.find_one({"tenant_id": tenant_id, "id": response_id}, {"_id": 0})
    if not doc:
        raise FormsError("form_response_not_found", "Form response not found", 404)
    updates = {
        "status": "reviewed",
        "reviewed_at": _now_iso(),
        "reviewed_by_user_id": user.get("id"),
        "mapping_results": mapping_results or doc.get("mapping_results") or [],
        "updated_at": _now_iso(),
    }
    await db.form_responses.update_one({"tenant_id": tenant_id, "id": response_id}, {"$set": updates})
    return serialize_doc(await db.form_responses.find_one({"tenant_id": tenant_id, "id": response_id}, {"_id": 0}))
