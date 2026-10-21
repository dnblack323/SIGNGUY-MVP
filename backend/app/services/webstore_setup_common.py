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


def _token_response(invitation: dict, raw_token: str) -> dict:
    response = serialize_doc(invitation)
    response.pop("token_hash", None)
    response["invitation_url"] = public_url(f"/portal/webstores/invitations/accept?t={raw_token}")
    return response


async def _audit(**fields: Any) -> None:
    """Same single history writer as the rest of Webstores (webstore_shared_audit._audit)."""
    from .webstore_shared_audit import _audit as shared_audit

    await shared_audit(**fields)


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
