"""Reusable template service for EC10 and EC12 systems."""
from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Optional

from pymongo.errors import DuplicateKeyError

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.template_definition import TemplateDefinition, TemplatePack
from ..services import decision_room_service, intake_service
from ..services.audit import record_audit

PLATFORM_TENANT_ID = "__platform__"

EC10_TEMPLATE_TYPES = {"intake", "questionnaire", "decision_options"}
EC12_TEMPLATE_TYPES = {
    "task", "task_checklist", "appointment", "appointment_confirmation", "appointment_reminder",
    "message", "announcement", "note", "daily_digest", "email", "sms",
    "support_response", "bug_response", "feature_request_response", "time_off_response",
}
VALID_TEMPLATE_TYPES = EC10_TEMPLATE_TYPES | EC12_TEMPLATE_TYPES

VALID_CHANNELS = {
    "in_app", "email_subject", "email_body", "sms_body", "announcement_body", "note_body",
    "task_title", "task_description", "digest_section",
}
CHANNEL_LIMITS = {
    "email_subject": 200,
    "sms_body": 320,
    "task_title": 180,
    "announcement_body": 4000,
    "note_body": 5000,
    "digest_section": 3000,
}
VALID_PLACEHOLDERS = {
    "customer_name", "employee_name", "order_number", "work_order_number",
    "appointment_date", "appointment_time", "appointment_location", "task_title",
    "due_date", "support_request_number", "feature_request_title", "bug_report_title",
    "shop_name", "contact_name",
}
PLACEHOLDER_RE = re.compile(r"{{\s*([a-zA-Z0-9_.-]+)\s*}}")

STARTER_PACK_ID = "starter_ec12_productivity"
STARTER_PACK_VERSION = 1
STARTER_TEMPLATES = [
    ("follow_up_quote", "Follow up on quote", "task", {"task_title": "Follow up with {{customer_name}} about quote {{order_number}}", "task_description": "Confirm next steps and answer any open questions.", "in_app": "Follow up on quote {{order_number}}."}),
    ("request_artwork", "Request artwork", "task", {"task_title": "Request artwork from {{customer_name}}", "task_description": "Ask for logo/art files and production requirements.", "in_app": "Artwork is needed for {{customer_name}}."}),
    ("schedule_installation", "Schedule installation", "task", {"task_title": "Schedule installation for {{customer_name}}", "task_description": "Coordinate installer, date, and location.", "in_app": "Schedule installation at {{appointment_location}}."}),
    ("consultation", "Consultation appointment", "appointment", {"in_app": "Consultation with {{customer_name}} on {{appointment_date}} at {{appointment_time}}.", "email_subject": "Consultation scheduled", "email_body": "Hi {{customer_name}}, your consultation is scheduled for {{appointment_date}} at {{appointment_time}}."}),
    ("appointment_tomorrow", "Appointment tomorrow", "appointment_reminder", {"in_app": "Reminder: appointment with {{customer_name}} tomorrow.", "sms_body": "Reminder: your appointment is tomorrow at {{appointment_time}}.", "email_subject": "Appointment reminder", "email_body": "Your appointment is tomorrow at {{appointment_time}}."}),
    ("schedule_change", "Schedule change message", "message", {"in_app": "Schedule changed for {{customer_name}}. New date: {{appointment_date}}.", "email_subject": "Schedule update", "email_body": "The schedule has changed. New date: {{appointment_date}}."}),
    ("production_delay", "Production delay announcement", "announcement", {"announcement_body": "Production delay for {{order_number}}. Please review updated due date {{due_date}}."}),
    ("urgent_shop_notice", "Urgent shop notice", "announcement", {"announcement_body": "Urgent notice from {{shop_name}}: please check current assignments."}),
    ("daily_digest_basic", "Daily digest basic section", "daily_digest", {"digest_section": "{{shop_name}} daily digest: tasks due {{due_date}} and upcoming appointments."}),
    ("support_received", "Support request received", "support_response", {"in_app": "We received support request {{support_request_number}} and will review it.", "email_subject": "Support request received", "email_body": "We received your support request and will follow up soon."}),
    ("need_more_info", "Need more information", "support_response", {"in_app": "We need more information for support request {{support_request_number}}.", "email_body": "Please send more detail so we can continue reviewing this request."}),
    ("bug_acknowledged", "Bug report acknowledged", "bug_response", {"in_app": "Bug report {{bug_report_title}} has been acknowledged.", "email_body": "Thanks for the report. We have logged {{bug_report_title}}."}),
    ("feature_acknowledged", "Feature request acknowledged", "feature_request_response", {"in_app": "Feature request {{feature_request_title}} has been acknowledged.", "email_body": "Thanks for suggesting {{feature_request_title}}."}),
    ("time_off_more_info", "Time-off need more information", "time_off_response", {"in_app": "Please add more detail to your time-off request for {{due_date}}."}),
]


class TemplateError(ValueError):
    def __init__(self, code: str, message: Optional[str] = None):
        super().__init__(message or code)
        self.code = code


def _now_iso() -> str:
    return utc_now().isoformat()


def _is_platform_admin(user: Optional[dict]) -> bool:
    user = user or {}
    return bool(
        user.get("platform_admin")
        or user.get("founder_access_admin")
        or user.get("platform_role") in {"admin", "owner"}
        or "platform:admin" in set(user.get("permissions") or [])
    )


def _actor_email(actor_email: Optional[str]) -> str:
    return actor_email or "staff"


async def _audit(
    *, tenant_id: str, actor_user_id: str, actor_email: str, action: str,
    template_id: str, summary: str, diff: Optional[dict[str, Any]] = None,
) -> None:
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=_actor_email(actor_email),
        action=action, entity_type="template_definition", entity_id=template_id,
        summary=summary, diff=diff or {},
    )


def _sanitize_name(name: Optional[str]) -> str:
    cleaned = (name or "").strip()
    if not cleaned:
        raise TemplateError("name_required", "Template name is required")
    return cleaned[:160]


def _extract_placeholders(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, str):
        found.update(PLACEHOLDER_RE.findall(value))
    elif isinstance(value, dict):
        for v in value.values():
            found.update(_extract_placeholders(v))
    elif isinstance(value, list):
        for item in value:
            found.update(_extract_placeholders(item))
    return found


def _reject_unsafe_text(value: Any) -> None:
    if isinstance(value, str):
        lowered = value.lower()
        for marker in ("<script", "javascript:", "onerror=", "authorization:", "bearer ", "cookie:", "password=", "secret"):
            if marker in lowered:
                raise TemplateError("invalid_template_body", "Template body contains unsafe or secret-like content")
    elif isinstance(value, dict):
        for v in value.values():
            _reject_unsafe_text(v)
    elif isinstance(value, list):
        for item in value:
            _reject_unsafe_text(item)


def _normalize_ec12_body(body: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(body or {})
    channels = normalized.get("channels")
    if channels is None:
        channels = {k: normalized[k] for k in list(normalized.keys()) if k in VALID_CHANNELS}
        normalized["channels"] = channels
    if not isinstance(channels, dict):
        raise TemplateError("invalid_template_body", "Template channels must be an object")
    unknown_channels = sorted(set(channels) - VALID_CHANNELS)
    if unknown_channels:
        raise TemplateError("invalid_template_body", f"Unsupported template channels: {', '.join(unknown_channels)}")
    for channel, value in channels.items():
        if not isinstance(value, str):
            raise TemplateError("invalid_template_body", f"{channel} must be text")
        limit = CHANNEL_LIMITS.get(channel, 5000)
        if len(value) > limit:
            raise TemplateError("invalid_template_body", f"{channel} must be {limit} characters or fewer")
    _reject_unsafe_text(normalized)
    placeholders = _extract_placeholders(normalized)
    unknown = sorted(p for p in placeholders if p not in VALID_PLACEHOLDERS)
    if unknown:
        raise TemplateError("unknown_placeholder", f"Unsupported placeholders: {', '.join(unknown)}")
    normalized["placeholders"] = sorted(placeholders)
    return normalized


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
    elif template_type in EC12_TEMPLATE_TYPES:
        body = _normalize_ec12_body(body)
    return body


def _template_channels(body: dict[str, Any]) -> list[str]:
    channels = body.get("channels") if isinstance(body, dict) else {}
    if isinstance(channels, dict):
        return sorted(k for k, v in channels.items() if v)
    return sorted(k for k in body if k in VALID_CHANNELS)


def _template_placeholders(body: dict[str, Any]) -> list[str]:
    if isinstance(body, dict) and isinstance(body.get("placeholders"), list):
        return sorted(set(str(p) for p in body["placeholders"]))
    return sorted(_extract_placeholders(body))


def _sample_context(overrides: Optional[dict[str, Any]] = None) -> dict[str, str]:
    base = {
        "customer_name": "Acme Signs",
        "employee_name": "Alex Maker",
        "order_number": "1001",
        "work_order_number": "WO-2001",
        "appointment_date": "2026-08-01",
        "appointment_time": "10:00 AM",
        "appointment_location": "123 Main St",
        "task_title": "Follow up on quote",
        "due_date": "2026-08-02",
        "support_request_number": "SUP-1001",
        "feature_request_title": "Batch reminders",
        "bug_report_title": "Board filter resets",
        "shop_name": "SignGuy Shop",
        "contact_name": "Jordan Customer",
    }
    for k, v in (overrides or {}).items():
        if k in VALID_PLACEHOLDERS and v is not None:
            base[k] = str(v)
    return base


def _render_text(value: str, context: dict[str, str]) -> str:
    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in VALID_PLACEHOLDERS:
            raise TemplateError("unknown_placeholder", f"Unsupported placeholder: {key}")
        return context.get(key, "")
    return PLACEHOLDER_RE.sub(repl, value)


def render_channels(body: dict[str, Any], context: Optional[dict[str, Any]] = None) -> dict[str, str]:
    channels = body.get("channels") if isinstance(body, dict) else {}
    if not isinstance(channels, dict):
        raise TemplateError("invalid_template_body", "Template channels must be an object")
    safe_context = _sample_context(context)
    rendered = {k: _render_text(v, safe_context) for k, v in channels.items() if k in VALID_CHANNELS and isinstance(v, str)}
    for channel, value in rendered.items():
        limit = CHANNEL_LIMITS.get(channel, 5000)
        if len(value) > limit:
            raise TemplateError("invalid_template_body", f"Rendered {channel} exceeds {limit} characters")
    return rendered


def _public_filter_for_tenant(tenant_id: str, *, include_archived: bool = False) -> dict[str, Any]:
    active_clause = {} if include_archived else {"archived_at": None, "active": True}
    return {
        "$and": [
            active_clause,
            {"$or": [
                {"tenant_id": tenant_id, "owner_scope": {"$in": [None, "tenant"]}},
                {"tenant_id": PLATFORM_TENANT_ID, "owner_scope": "platform", "platform_managed": True, "active": True, "source_status": {"$in": ["active", "deprecated", "replaced"]}},
            ]},
        ]
    }


async def _find_visible_template(*, tenant_id: str, template_id: str, user: Optional[dict] = None) -> dict[str, Any]:
    query = {"id": template_id, "$or": [
        {"tenant_id": tenant_id, "owner_scope": {"$in": [None, "tenant"]}},
        {"tenant_id": PLATFORM_TENANT_ID, "owner_scope": "platform", "platform_managed": True},
    ]}
    doc = await db.template_definitions.find_one(query, {"_id": 0})
    if not doc:
        raise TemplateError("template_not_found", "Template not found")
    if doc.get("owner_scope") == "platform" and not doc.get("active", True) and not _is_platform_admin(user):
        raise TemplateError("template_not_found", "Template not found")
    return serialize_doc(doc)


async def _get_tenant_template(*, tenant_id: str, template_id: str) -> dict[str, Any]:
    doc = await db.template_definitions.find_one({"id": template_id, "tenant_id": tenant_id, "owner_scope": {"$in": [None, "tenant"]}}, {"_id": 0})
    if not doc:
        raise TemplateError("template_not_found", "Template not found")
    return serialize_doc(doc)


async def create_template(
    *, tenant_id: str, payload: dict[str, Any], actor_user_id: str, actor_email: str,
) -> dict[str, Any]:
    template_type = payload.get("template_type")
    body = _validate_body(template_type, payload.get("body") or {})
    doc = TemplateDefinition(
        tenant_id=tenant_id,
        owner_scope="tenant",
        name=_sanitize_name(payload.get("name")),
        template_type=template_type,
        description=(payload.get("description") or None),
        body=body,
        channels=_template_channels(body),
        placeholders=_template_placeholders(body),
        created_by_user_id=actor_user_id,
        updated_by_user_id=actor_user_id,
    ).model_dump()
    await db.template_definitions.insert_one(prepare_for_mongo(dict(doc)))
    await _audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="template.created", template_id=doc["id"],
        summary=f"Template '{doc['name']}' created", diff={"template_type": template_type, "owner_scope": "tenant"},
    )
    return serialize_doc(doc)


async def list_templates(
    *, tenant_id: str, template_type: Optional[str] = None, active: Optional[bool] = None,
    channel: Optional[str] = None, include_platform: bool = True, include_archived: bool = False,
) -> list[dict[str, Any]]:
    q: dict[str, Any]
    if include_platform:
        q = _public_filter_for_tenant(tenant_id, include_archived=include_archived)
    else:
        q = {"tenant_id": tenant_id, "owner_scope": {"$in": [None, "tenant"]}}
        if not include_archived:
            q.update({"archived_at": None, "active": True})
    if template_type:
        q["template_type"] = template_type
    if active is not None:
        q["active"] = active
    if channel:
        if channel not in VALID_CHANNELS:
            raise TemplateError("invalid_channel", f"Unsupported channel: {channel}")
        q["channels"] = channel
    cur = db.template_definitions.find(q, {"_id": 0}).sort("updated_at", -1)
    return [serialize_doc(d) async for d in cur]


async def get_template(*, tenant_id: str, template_id: str, user: Optional[dict] = None) -> dict[str, Any]:
    return await _find_visible_template(tenant_id=tenant_id, template_id=template_id, user=user)


async def update_template(
    *, tenant_id: str, template_id: str, changes: dict[str, Any], actor_user_id: str, actor_email: str,
) -> dict[str, Any]:
    current = await _get_tenant_template(tenant_id=tenant_id, template_id=template_id)
    if current.get("owner_scope") == "platform":
        raise TemplateError("platform_template_immutable", "Platform master templates cannot be edited by tenants")
    updates: dict[str, Any] = {}
    if "name" in changes:
        updates["name"] = _sanitize_name(changes.get("name"))
    if "template_type" in changes and changes.get("template_type") != current["template_type"]:
        if changes["template_type"] not in VALID_TEMPLATE_TYPES:
            raise TemplateError("invalid_template_type", f"Unsupported template_type: {changes['template_type']}")
        updates["template_type"] = changes["template_type"]
    if "description" in changes:
        updates["description"] = changes.get("description")
    if "body" in changes:
        effective_type = updates.get("template_type") or current["template_type"]
        body = _validate_body(effective_type, changes.get("body") or {})
        updates["body"] = body
        updates["channels"] = _template_channels(body)
        updates["placeholders"] = _template_placeholders(body)
    if not updates:
        return current
    updates["version"] = int(current.get("version") or 1) + 1
    if current.get("source_template_id"):
        updates["tenant_modified"] = True
        source = await db.template_definitions.find_one({"id": current["source_template_id"], "tenant_id": PLATFORM_TENANT_ID}, {"_id": 0, "version": 1})
        updates["source_update_available"] = bool(source and int(source.get("version") or 1) > int(current.get("source_template_version") or 0))
    updates["updated_by_user_id"] = actor_user_id
    updates["updated_at"] = _now_iso()
    await db.template_definitions.update_one({"id": template_id, "tenant_id": tenant_id}, {"$set": updates})
    await _audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="template.updated", template_id=template_id,
        summary="Template updated", diff={"fields": list(updates.keys())},
    )
    return await _get_tenant_template(tenant_id=tenant_id, template_id=template_id)


async def archive_template(*, tenant_id: str, template_id: str, actor_user_id: str, actor_email: str) -> dict[str, Any]:
    current = await _get_tenant_template(tenant_id=tenant_id, template_id=template_id)
    if current.get("owner_scope") == "platform":
        raise TemplateError("platform_template_immutable", "Platform master templates cannot be archived by tenants")
    now = _now_iso()
    await db.template_definitions.update_one(
        {"id": template_id, "tenant_id": tenant_id},
        {"$set": {"active": False, "archived_at": now, "updated_at": now, "updated_by_user_id": actor_user_id}},
    )
    await _audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="template.archived", template_id=template_id,
        summary="Template archived",
    )
    return await _get_tenant_template(tenant_id=tenant_id, template_id=template_id)


async def restore_template(*, tenant_id: str, template_id: str, actor_user_id: str, actor_email: str) -> dict[str, Any]:
    current = await _get_tenant_template(tenant_id=tenant_id, template_id=template_id)
    if current.get("owner_scope") == "platform":
        raise TemplateError("platform_template_immutable", "Platform master templates cannot be restored by tenants")
    now = _now_iso()
    await db.template_definitions.update_one(
        {"id": template_id, "tenant_id": tenant_id},
        {"$set": {"active": True, "archived_at": None, "updated_at": now, "updated_by_user_id": actor_user_id}},
    )
    await _audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="template.restored", template_id=template_id,
        summary="Template restored",
    )
    return await _get_tenant_template(tenant_id=tenant_id, template_id=template_id)


async def apply_template(
    *, tenant_id: str, template_id: str, target_type: str, target_id: Optional[str],
    actor_user_id: str, actor_email: str, context: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    template = await _find_visible_template(tenant_id=tenant_id, template_id=template_id)
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

    if template_type in EC12_TEMPLATE_TYPES:
        rendered = render_channels(body, context)
        await _audit(
            tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
            action="template.rendered", template_id=template_id,
            summary="Template rendered", diff={"template_type": template_type, "target_type": target_type},
        )
        return {
            "target_type": target_type,
            "target_id": target_id,
            "template_type": template_type,
            "template_id": template_id,
            "rendered": rendered,
            "mutated": False,
            "sent": False,
        }

    raise TemplateError("invalid_template_type", f"Unsupported template_type: {template_type}")


async def create_platform_master(*, payload: dict[str, Any], actor: dict) -> dict[str, Any]:
    if not _is_platform_admin(actor):
        raise TemplateError("platform_admin_required", "Platform admin access is required")
    template_type = payload.get("template_type")
    body = _validate_body(template_type, payload.get("body") or {})
    doc = TemplateDefinition(
        tenant_id=PLATFORM_TENANT_ID,
        owner_scope="platform",
        name=_sanitize_name(payload.get("name")),
        template_type=template_type,
        description=payload.get("description") or None,
        body=body,
        channels=_template_channels(body),
        placeholders=_template_placeholders(body),
        source_status=payload.get("source_status") or "active",
        starter_template=bool(payload.get("starter_template", False)),
        pack_id=payload.get("pack_id"),
        pack_type=payload.get("pack_type") or ("starter" if payload.get("starter_template") else None),
        platform_managed=True,
        premium_reserved=bool(payload.get("premium_reserved", False)),
        created_by_user_id=actor["id"],
        updated_by_user_id=actor["id"],
    ).model_dump()
    await db.template_definitions.insert_one(prepare_for_mongo(dict(doc)))
    await _audit(
        tenant_id=actor["tenant_id"], actor_user_id=actor["id"], actor_email=actor.get("email", "platform"),
        action="template.platform_master_created", template_id=doc["id"],
        summary="Platform master template created", diff={"template_type": template_type, "premium_reserved": doc["premium_reserved"]},
    )
    return serialize_doc(doc)


async def update_platform_master(*, template_id: str, changes: dict[str, Any], actor: dict) -> dict[str, Any]:
    if not _is_platform_admin(actor):
        raise TemplateError("platform_admin_required", "Platform admin access is required")
    current = await db.template_definitions.find_one({"id": template_id, "tenant_id": PLATFORM_TENANT_ID, "owner_scope": "platform"}, {"_id": 0})
    if not current:
        raise TemplateError("template_not_found", "Template not found")
    updates: dict[str, Any] = {}
    if "name" in changes:
        updates["name"] = _sanitize_name(changes.get("name"))
    if "description" in changes:
        updates["description"] = changes.get("description")
    if "source_status" in changes:
        if changes["source_status"] not in {"active", "deprecated", "replaced"}:
            raise TemplateError("invalid_source_status", "Unsupported source status")
        updates["source_status"] = changes["source_status"]
    if "active" in changes:
        updates["active"] = bool(changes["active"])
        updates["archived_at"] = None if updates["active"] else _now_iso()
    if "body" in changes:
        body = _validate_body(current["template_type"], changes.get("body") or {})
        updates["body"] = body
        updates["channels"] = _template_channels(body)
        updates["placeholders"] = _template_placeholders(body)
    if not updates:
        return serialize_doc(current)
    if any(k in updates for k in {"body", "name", "description"}):
        updates["version"] = int(current.get("version") or 1) + 1
    updates["updated_by_user_id"] = actor["id"]
    updates["updated_at"] = _now_iso()
    await db.template_definitions.update_one({"id": template_id, "tenant_id": PLATFORM_TENANT_ID}, {"$set": updates})
    await _mark_source_updates(template_id)
    await _audit(
        tenant_id=actor["tenant_id"], actor_user_id=actor["id"], actor_email=actor.get("email", "platform"),
        action="template.platform_master_updated", template_id=template_id,
        summary="Platform master template updated", diff={"fields": list(updates.keys())},
    )
    return serialize_doc(await db.template_definitions.find_one({"id": template_id, "tenant_id": PLATFORM_TENANT_ID}, {"_id": 0}))


async def _mark_source_updates(source_template_id: str) -> None:
    source = await db.template_definitions.find_one({"id": source_template_id, "tenant_id": PLATFORM_TENANT_ID}, {"_id": 0, "version": 1})
    if not source:
        return
    await db.template_definitions.update_many(
        {"source_template_id": source_template_id, "owner_scope": {"$in": [None, "tenant"]}, "source_template_version": {"$lt": int(source.get("version") or 1)}},
        {"$set": {"source_update_available": True, "updated_at": _now_iso()}},
    )


async def install_template_copy(
    *, tenant_id: str, source_template_id: str, actor_user_id: str, actor_email: str,
    replacement_for_template_id: Optional[str] = None,
) -> dict[str, Any]:
    source = await db.template_definitions.find_one({"id": source_template_id, "tenant_id": PLATFORM_TENANT_ID, "owner_scope": "platform"}, {"_id": 0})
    if not source or not source.get("active", True):
        raise TemplateError("template_not_found", "Template not found")
    existing = await db.template_definitions.find_one(
        {"tenant_id": tenant_id, "source_template_id": source_template_id, "source_template_version": source.get("version"), "archived_at": None},
        {"_id": 0},
    )
    if existing and not replacement_for_template_id:
        return serialize_doc(existing)
    doc = TemplateDefinition(
        tenant_id=tenant_id,
        owner_scope="tenant",
        name=source["name"] if not replacement_for_template_id else f"{source['name']} v{source.get('version')}",
        template_type=source["template_type"],
        description=source.get("description"),
        body=deepcopy(source.get("body") or {}),
        version=1,
        source_template_id=source["id"],
        source_template_version=int(source.get("version") or 1),
        source_template_name=source["name"],
        installed_at=_now_iso(),
        tenant_modified=False,
        source_update_available=False,
        starter_template=bool(source.get("starter_template")),
        pack_id=source.get("pack_id"),
        pack_type=source.get("pack_type"),
        platform_managed=False,
        premium_reserved=bool(source.get("premium_reserved", False)),
        channels=list(source.get("channels") or []),
        placeholders=list(source.get("placeholders") or []),
        created_by_user_id=actor_user_id,
        updated_by_user_id=actor_user_id,
    ).model_dump()
    await db.template_definitions.insert_one(prepare_for_mongo(dict(doc)))
    if replacement_for_template_id:
        await db.template_definitions.update_one(
            {"tenant_id": tenant_id, "id": replacement_for_template_id},
            {"$set": {"source_update_available": False, "updated_at": _now_iso()}},
        )
    await _audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="template.starter_installed", template_id=doc["id"],
        summary="Starter template installed", diff={"source_template_id": source_template_id, "source_version": source.get("version")},
    )
    return serialize_doc(doc)


def _starter_body(channels: dict[str, str]) -> dict[str, Any]:
    return _normalize_ec12_body({"channels": channels})


async def ensure_platform_starter_pack(*, actor: Optional[dict] = None) -> dict[str, Any]:
    ids: list[str] = []
    for key, name, template_type, channels in STARTER_TEMPLATES:
        template_id = f"starter_ec12_{key}"
        body = _starter_body(channels)
        doc = TemplateDefinition(
            id=template_id,
            tenant_id=PLATFORM_TENANT_ID,
            owner_scope="platform",
            name=name,
            template_type=template_type,
            description="Base app EC12 starter template.",
            body=body,
            version=STARTER_PACK_VERSION,
            active=True,
            source_status="active",
            starter_template=True,
            pack_id=STARTER_PACK_ID,
            pack_type="starter",
            platform_managed=True,
            premium_reserved=False,
            channels=_template_channels(body),
            placeholders=_template_placeholders(body),
            created_by_user_id=(actor or {}).get("id", "system"),
            updated_by_user_id=(actor or {}).get("id", "system"),
        ).model_dump()
        try:
            await db.template_definitions.insert_one(prepare_for_mongo(dict(doc)))
        except DuplicateKeyError:
            pass
        ids.append(template_id)
    pack_doc = TemplatePack(
        id=STARTER_PACK_ID,
        name="EC12 Productivity Starter Templates",
        description="Small base-app starter templates for tasks, appointments, messages, announcements, reminders, support, bugs, features, and time-off responses.",
        pack_type="starter",
        version=STARTER_PACK_VERSION,
        included_template_ids=ids,
        active=True,
        platform_managed=True,
        starter_pack=True,
        premium_reserved=False,
    ).model_dump()
    created_at = pack_doc.pop("created_at", utc_now())
    await db.template_packs.update_one(
        {"id": STARTER_PACK_ID},
        {"$set": prepare_for_mongo({**pack_doc, "updated_at": utc_now()}), "$setOnInsert": {"created_at": created_at}},
        upsert=True,
    )
    return serialize_doc(await db.template_packs.find_one({"id": STARTER_PACK_ID}, {"_id": 0}))


async def list_template_packs() -> list[dict[str, Any]]:
    await ensure_platform_starter_pack()
    cur = db.template_packs.find({"active": True}, {"_id": 0}).sort("name", 1)
    return [serialize_doc(d) async for d in cur]


async def install_starter_pack(*, tenant_id: str, actor_user_id: str, actor_email: str) -> dict[str, Any]:
    pack = await ensure_platform_starter_pack()
    installed = []
    for source_id in pack.get("included_template_ids") or []:
        installed.append(await install_template_copy(
            tenant_id=tenant_id, source_template_id=source_id,
            actor_user_id=actor_user_id, actor_email=actor_email,
        ))
    await _audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="template.pack_installed", template_id=STARTER_PACK_ID,
        summary="Starter template pack installed", diff={"pack_id": STARTER_PACK_ID, "count": len(installed)},
    )
    return {"pack": pack, "items": installed, "installed_count": len(installed)}


async def duplicate_template(*, tenant_id: str, template_id: str, actor_user_id: str, actor_email: str) -> dict[str, Any]:
    source = await _find_visible_template(tenant_id=tenant_id, template_id=template_id)
    doc = TemplateDefinition(
        tenant_id=tenant_id,
        owner_scope="tenant",
        name=f"{source['name']} copy"[:160],
        template_type=source["template_type"],
        description=source.get("description"),
        body=deepcopy(source.get("body") or {}),
        channels=list(source.get("channels") or []),
        placeholders=list(source.get("placeholders") or []),
        source_template_id=source.get("source_template_id") or (source["id"] if source.get("owner_scope") == "platform" else None),
        source_template_version=source.get("source_template_version") or (source.get("version") if source.get("owner_scope") == "platform" else None),
        source_template_name=source.get("source_template_name") or (source["name"] if source.get("owner_scope") == "platform" else None),
        installed_at=_now_iso() if source.get("owner_scope") == "platform" else None,
        tenant_modified=True,
        created_by_user_id=actor_user_id,
        updated_by_user_id=actor_user_id,
    ).model_dump()
    await db.template_definitions.insert_one(prepare_for_mongo(dict(doc)))
    await _audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="template.duplicated", template_id=doc["id"],
        summary="Template duplicated", diff={"source_template_id": template_id},
    )
    return serialize_doc(doc)


async def preview_template(*, tenant_id: str, template_id: str, context: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    template = await _find_visible_template(tenant_id=tenant_id, template_id=template_id)
    return {
        "template_id": template_id,
        "template_type": template["template_type"],
        "placeholders": _template_placeholders(template.get("body") or {}),
        "rendered": render_channels(template.get("body") or {}, context),
        "sample": context is None,
    }


async def validate_template_payload(*, template_type: str, body: dict[str, Any]) -> dict[str, Any]:
    try:
        validated = _validate_body(template_type, body)
        return {"valid": True, "placeholders": _template_placeholders(validated), "channels": _template_channels(validated), "warnings": []}
    except TemplateError as ex:
        if ex.code == "unknown_placeholder":
            return {"valid": False, "code": ex.code, "detail": str(ex), "warnings": [str(ex)]}
        raise


async def compare_source_version(*, tenant_id: str, template_id: str) -> dict[str, Any]:
    template = await _get_tenant_template(tenant_id=tenant_id, template_id=template_id)
    source_id = template.get("source_template_id")
    if not source_id:
        return {"has_source": False, "update_available": False}
    source = await db.template_definitions.find_one({"id": source_id, "tenant_id": PLATFORM_TENANT_ID}, {"_id": 0})
    if not source:
        return {"has_source": True, "source_available": False, "update_available": False}
    update_available = int(source.get("version") or 1) > int(template.get("source_template_version") or 0)
    if update_available != bool(template.get("source_update_available")):
        await db.template_definitions.update_one({"id": template_id, "tenant_id": tenant_id}, {"$set": {"source_update_available": update_available, "updated_at": _now_iso()}})
    return {
        "has_source": True,
        "source_available": True,
        "source_template_id": source_id,
        "source_template_version": int(source.get("version") or 1),
        "tenant_source_version": int(template.get("source_template_version") or 0),
        "source_status": source.get("source_status"),
        "update_available": update_available,
    }


async def install_newer_source_copy(*, tenant_id: str, template_id: str, actor_user_id: str, actor_email: str) -> dict[str, Any]:
    template = await _get_tenant_template(tenant_id=tenant_id, template_id=template_id)
    source_id = template.get("source_template_id")
    if not source_id:
        raise TemplateError("source_template_missing", "Template has no platform source")
    comparison = await compare_source_version(tenant_id=tenant_id, template_id=template_id)
    if not comparison.get("update_available"):
        raise TemplateError("source_update_not_available", "No newer source version is available")
    copied = await install_template_copy(
        tenant_id=tenant_id, source_template_id=source_id,
        actor_user_id=actor_user_id, actor_email=actor_email,
        replacement_for_template_id=template_id,
    )
    await _audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="template.newer_source_copy_installed", template_id=copied["id"],
        summary="Newer source template copy installed", diff={"previous_template_id": template_id, "source_template_id": source_id},
    )
    return copied
