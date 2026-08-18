"""Shared setup error type, validation, audit, and data helpers."""
from __future__ import annotations

from .webstore_setup_contracts import *


class WebstoreSetupError(Exception):
    def __init__(self, code: str, detail: str, status_code: int = 400):
        self.code = code
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def _now_iso() -> str:
    return utc_now().isoformat()


def _require_staff_perm(user: dict, perm: Perm) -> None:
    if perm.value not in set(permissions_for_role(user.get("role", "staff"))):
        raise WebstoreSetupError("permission_denied", f"Missing permission: {perm.value}", 403)


def _email(value: Any) -> str:
    email = str(value or "").strip().lower()
    if not email or "@" not in email:
        raise WebstoreSetupError("email_required", "A valid email is required", 400)
    return email


def _clean_text(value: Any, field: str, *, limit: int = 200) -> str:
    text = str(value or "").strip()
    if not text:
        raise WebstoreSetupError(f"{field}_required", f"{field} is required", 400)
    if len(text) > limit:
        raise WebstoreSetupError(f"{field}_too_long", f"{field} must be {limit} characters or fewer", 400)
    return text


def _portal_type_for_role(role: str) -> str:
    if role == "manager":
        return "webstore_manager"
    return "webstore_owner"


def _portal_perms_for_role(role: str) -> list[str]:
    return list(WEBSTORE_MANAGER_PORTAL_PERMS if role == "manager" else WEBSTORE_OWNER_PORTAL_PERMS)


def _shared_form_status(webstore_template_status: str) -> str:
    if webstore_template_status == "active":
        return "published"
    if webstore_template_status == "retired":
        return "archived"
    return "draft"


def _shared_form_template_name(template: dict[str, Any]) -> str:
    return str(template.get("title") or template.get("name") or "Webstore Questionnaire").strip()


async def _upsert_shared_form_template_for_webstore_template(
    tenant_id: str,
    template: dict[str, Any],
    actor_user_id: Optional[str] = None,
    *,
    force: bool = False,
) -> dict:
    existing = await db.form_templates.find_one(
        {"tenant_id": tenant_id, "module": "webstores", "source_template_id": template["id"]},
        {"_id": 0},
    )
    payload = {
        "name": _shared_form_template_name(template),
        "module": "webstores",
        "context_type": "webstore",
        "description": template.get("description"),
        "status": _shared_form_status(template.get("status") or "active"),
        "version": int(template.get("version") or 1),
        "sections": template.get("sections") or [],
        "mapping_config": {"safe_answer_mapping": SAFE_ANSWER_MAPPING},
        "private_config": {
            "adapter": WEBSTORE_FORM_ADAPTER,
            "store_type": template.get("store_type") or "general",
            "legacy_template_id": template["id"],
        },
        "source_template_id": template["id"],
        "updated_by_user_id": actor_user_id,
        "updated_at": _now_iso(),
    }
    if existing:
        if not force:
            return serialize_doc(existing)
        await db.form_templates.update_one(
            {"tenant_id": tenant_id, "id": existing["id"]},
            {"$set": prepare_for_mongo(payload)},
        )
        current = await db.form_templates.find_one({"tenant_id": tenant_id, "id": existing["id"]}, {"_id": 0})
        return serialize_doc(current or existing)
    doc = FormTemplate(
        tenant_id=tenant_id,
        created_by_user_id=actor_user_id,
        **payload,
    ).model_dump()
    await db.form_templates.insert_one(prepare_for_mongo(doc))
    return serialize_doc(doc)


def _webstore_template_from_shared_form(form: dict[str, Any], fallback: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    private_config = form.get("private_config") or {}
    fallback = fallback or {}
    return {
        **fallback,
        "id": fallback.get("id") or private_config.get("legacy_template_id") or form["id"],
        "title": form.get("name") or fallback.get("title") or "Webstore Questionnaire",
        "sections": form.get("sections") or fallback.get("sections") or [],
        "version": form.get("version") or fallback.get("version") or 1,
        "status": "active" if form.get("status") == "published" else "inactive",
        "store_type": private_config.get("store_type") or fallback.get("store_type") or "general",
        "source_template_id": fallback.get("source_template_id") or form.get("source_template_id"),
        "shared_form_template_id": form["id"],
        "shared_form_adapter": "forms_v1",
    }


def _token_response(invitation: dict, raw_token: str) -> dict:
    response = serialize_doc(invitation)
    response.pop("token_hash", None)
    response["invitation_url"] = f"/portal/webstores/invitations/accept?t={raw_token}"
    return response


async def _audit(
    *,
    tenant_id: str,
    webstore_id: str,
    actor_type: str,
    action: str,
    entity_type: str,
    entity_id: str,
    summary: str,
    actor_id: Optional[str] = None,
    actor_email: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    await db.webstore_activity_events.insert_one(
        prepare_for_mongo(
            {
                "id": secrets.token_hex(16),
                "created_at": utc_now(),
                "updated_at": utc_now(),
                "tenant_id": tenant_id,
                "webstore_id": webstore_id,
                "actor_type": actor_type,
                "actor_id": actor_id,
                "actor_email": actor_email,
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "summary": summary,
                "metadata": metadata or {},
            }
        )
    )
    await record_activity_with_audit(
        tenant_id=tenant_id,
        actor_user_id=actor_id or actor_type,
        actor_email=actor_email or actor_type,
        module="webstores",
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        metadata={"webstore_id": webstore_id, **(metadata or {})},
    )


async def _get_store(tenant_id: str, webstore_id: str) -> dict:
    store = await db.webstores.find_one({"tenant_id": tenant_id, "id": webstore_id}, {"_id": 0})
    if not store:
        raise WebstoreSetupError("webstore_not_found", "Webstore not found", 404)
    return serialize_doc(store)


async def _get_owner(tenant_id: str, owner_id: str) -> dict:
    owner = await db.webstore_owners.find_one({"tenant_id": tenant_id, "id": owner_id}, {"_id": 0})
    if not owner:
        raise WebstoreSetupError("webstore_owner_not_found", "Webstore owner not found", 404)
    return serialize_doc(owner)

__all__ = [name for name in globals() if not name.startswith("__")]
