"""EC10 Phase 10G - reusable template service."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.template_definition import TemplateDefinition
from ..services import decision_room_service, intake_service
from ..services.audit import record_audit

VALID_TEMPLATE_TYPES = {"intake", "questionnaire", "decision_options"}


class TemplateError(ValueError):
    def __init__(self, code: str, message: Optional[str] = None):
        super().__init__(message or code)
        self.code = code


def _now_iso() -> str:
    return utc_now().isoformat()


def _sanitize_name(name: Optional[str]) -> str:
    cleaned = (name or "").strip()
    if not cleaned:
        raise TemplateError("name_required", "Template name is required")
    return cleaned[:160]


def _validate_body(template_type: str, body: dict[str, Any]) -> dict[str, Any]:
    if template_type not in VALID_TEMPLATE_TYPES:
        raise TemplateError("invalid_template_type", f"Unsupported template_type: {template_type}")
    body = deepcopy(body or {})
    if template_type == "intake":
        if "items" in body and not isinstance(body["items"], list):
            raise TemplateError("invalid_template_body", "Intake template items must be a list")
    elif template_type == "questionnaire":
        if "prompt_config" in body and not isinstance(body["prompt_config"], dict):
            raise TemplateError("invalid_template_body", "Questionnaire template prompt_config must be an object")
    elif template_type == "decision_options":
        if not isinstance(body.get("options"), list):
            raise TemplateError("invalid_template_body", "Decision option templates require an options list")
    return body


async def create_template(
    *, tenant_id: str, payload: dict[str, Any], actor_user_id: str, actor_email: str,
) -> dict[str, Any]:
    template_type = payload.get("template_type")
    doc = TemplateDefinition(
        tenant_id=tenant_id,
        name=_sanitize_name(payload.get("name")),
        template_type=template_type,
        description=(payload.get("description") or None),
        body=_validate_body(template_type, payload.get("body") or {}),
        created_by_user_id=actor_user_id,
        updated_by_user_id=actor_user_id,
    ).model_dump()
    await db.template_definitions.insert_one(prepare_for_mongo(dict(doc)))
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="template.created", entity_type="template_definition", entity_id=doc["id"],
        summary=f"Template '{doc['name']}' created", diff={"template_type": template_type},
    )
    return serialize_doc(doc)


async def list_templates(*, tenant_id: str, template_type: Optional[str] = None, active: Optional[bool] = None) -> list[dict[str, Any]]:
    q: dict[str, Any] = {"tenant_id": tenant_id}
    if template_type:
        q["template_type"] = template_type
    if active is not None:
        q["active"] = active
    cur = db.template_definitions.find(q, {"_id": 0}).sort("updated_at", -1)
    return [serialize_doc(d) async for d in cur]


async def get_template(*, tenant_id: str, template_id: str) -> dict[str, Any]:
    doc = await db.template_definitions.find_one({"id": template_id, "tenant_id": tenant_id}, {"_id": 0})
    if not doc:
        raise TemplateError("template_not_found", "Template not found")
    return serialize_doc(doc)


async def update_template(
    *, tenant_id: str, template_id: str, changes: dict[str, Any], actor_user_id: str, actor_email: str,
) -> dict[str, Any]:
    current = await get_template(tenant_id=tenant_id, template_id=template_id)
    updates: dict[str, Any] = {}
    if "name" in changes:
        updates["name"] = _sanitize_name(changes.get("name"))
    if "description" in changes:
        updates["description"] = changes.get("description")
    if "body" in changes:
        updates["body"] = _validate_body(current["template_type"], changes.get("body") or {})
    if not updates:
        return current
    updates["version"] = int(current.get("version") or 1) + 1
    updates["updated_by_user_id"] = actor_user_id
    updates["updated_at"] = _now_iso()
    await db.template_definitions.update_one({"id": template_id, "tenant_id": tenant_id}, {"$set": updates})
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="template.updated", entity_type="template_definition", entity_id=template_id,
        summary="Template updated", diff={"fields": list(updates.keys())},
    )
    return await get_template(tenant_id=tenant_id, template_id=template_id)


async def archive_template(*, tenant_id: str, template_id: str, actor_user_id: str, actor_email: str) -> dict[str, Any]:
    await get_template(tenant_id=tenant_id, template_id=template_id)
    now = _now_iso()
    await db.template_definitions.update_one(
        {"id": template_id, "tenant_id": tenant_id},
        {"$set": {"active": False, "archived_at": now, "updated_at": now, "updated_by_user_id": actor_user_id}},
    )
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="template.archived", entity_type="template_definition", entity_id=template_id,
        summary="Template archived",
    )
    return await get_template(tenant_id=tenant_id, template_id=template_id)


async def restore_template(*, tenant_id: str, template_id: str, actor_user_id: str, actor_email: str) -> dict[str, Any]:
    await get_template(tenant_id=tenant_id, template_id=template_id)
    now = _now_iso()
    await db.template_definitions.update_one(
        {"id": template_id, "tenant_id": tenant_id},
        {"$set": {"active": True, "archived_at": None, "updated_at": now, "updated_by_user_id": actor_user_id}},
    )
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="template.restored", entity_type="template_definition", entity_id=template_id,
        summary="Template restored",
    )
    return await get_template(tenant_id=tenant_id, template_id=template_id)


async def apply_template(
    *, tenant_id: str, template_id: str, target_type: str, target_id: Optional[str],
    actor_user_id: str, actor_email: str,
) -> dict[str, Any]:
    template = await get_template(tenant_id=tenant_id, template_id=template_id)
    if not template.get("active", True):
        raise TemplateError("template_archived", "Archived templates cannot be applied")
    body = deepcopy(template.get("body") or {})
    template_type = template["template_type"]

    if template_type == "intake":
        if target_type != "new_intake":
            raise TemplateError("invalid_template_target", "Intake templates can only create a new intake")
        payload = {
            **body,
            "source_type": "saved_template",
            "source_reference": f"template:{template_id}:v{template.get('version')}",
        }
        intake = await intake_service.create_intake(
            tenant_id=tenant_id, payload=payload, created_by_user_id=actor_user_id, actor_email=actor_email,
        )
        return {"target_type": "intake", "target_id": intake["id"], "record": intake}

    if template_type == "questionnaire":
        if target_type != "customer_intake" or not target_id:
            raise TemplateError("invalid_template_target", "Questionnaire templates require a customer_intake target_id")
        existing = await db.customer_intakes.find_one({"id": target_id, "tenant_id": tenant_id})
        if not existing:
            raise TemplateError("customer_intake_not_found", "Customer intake not found")
        prompt_config = deepcopy(body.get("prompt_config", body))
        now = _now_iso()
        await db.customer_intakes.update_one(
            {"id": target_id, "tenant_id": tenant_id},
            {"$set": {"prompt_config": prompt_config, "updated_at": now}},
        )
        updated = await db.customer_intakes.find_one({"id": target_id, "tenant_id": tenant_id}, {"_id": 0})
        return {"target_type": "customer_intake", "target_id": target_id, "record": serialize_doc(updated)}

    if template_type == "decision_options":
        if target_type != "decision_room" or not target_id:
            raise TemplateError("invalid_template_target", "Decision option templates require a decision_room target_id")
        room = None
        for option in body.get("options") or []:
            copied = deepcopy(option)
            copied.pop("id", None)
            room = await decision_room_service.add_option(
                tenant_id=tenant_id, room_id=target_id, option_in=copied,
                actor_user_id=actor_user_id, actor_email=actor_email,
            )
        if room is None:
            raise TemplateError("invalid_template_body", "Decision option template has no options to apply")
        return {"target_type": "decision_room", "target_id": target_id, "record": room}

    raise TemplateError("invalid_template_type", f"Unsupported template_type: {template_type}")
