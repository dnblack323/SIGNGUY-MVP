"""Controlled PLATFORM_CREATOR assignment and authorization helpers."""
from __future__ import annotations

import re
from typing import Optional

from ..core.db import db
from ..core.permissions import (
    PLATFORM_CREATOR_ROLE,
    PlatformPerm,
    has_platform_admin_access,
    is_platform_creator_user,
)
from ..core.time_utils import serialize_doc, utc_now
from .activity import record_activity_with_audit

PLATFORM_CREATOR_EMAIL = "thesigntistslab@gmail.com"


class PlatformCreatorError(Exception):
    def __init__(self, code: str, detail: str, status_code: int = 400):
        self.code = code
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def normalize_email(email: str) -> str:
    return str(email or "").strip().lower()


async def _find_user_by_normalized_email(email: str) -> dict:
    normalized = normalize_email(email)
    if not normalized:
        raise PlatformCreatorError("email_required", "Email is required", 400)
    exact = await db.users.find({"email": normalized, "is_active": True}).to_list(length=2)
    if not exact:
        pattern = f"^{re.escape(normalized)}$"
        exact = await db.users.find({"email": {"$regex": pattern, "$options": "i"}, "is_active": True}).to_list(length=2)
    if not exact:
        raise PlatformCreatorError("platform_creator_user_not_found", "Platform creator user not found", 404)
    if len(exact) > 1:
        raise PlatformCreatorError(
            "platform_creator_email_ambiguous",
            "Platform creator email exists on more than one active user",
            409,
        )
    return exact[0]


def require_platform_creator(user: dict) -> None:
    if not is_platform_creator_user(user):
        raise PlatformCreatorError("platform_creator_required", "Platform creator access is required", 403)


async def assign_platform_creator_by_email(
    *,
    actor_user: Optional[dict],
    email: str = PLATFORM_CREATOR_EMAIL,
    allow_system_bootstrap: bool = False,
    reason: str,
) -> dict:
    """Assign PLATFORM_CREATOR by stored user identity.

    The only email comparison here is for controlled assignment/bootstrap. All
    runtime authorization uses stored role/permission fields.
    """
    if actor_user:
        if not has_platform_admin_access(actor_user):
            raise PlatformCreatorError("platform_admin_required", "Platform admin access is required", 403)
        actor_user_id = actor_user["id"]
        actor_email = actor_user.get("email", "platform")
    elif allow_system_bootstrap:
        actor_user_id = "system:platform_creator_bootstrap"
        actor_email = "system@signguy.internal"
    else:
        raise PlatformCreatorError("platform_admin_required", "Platform admin access is required", 403)

    clean_reason = (reason or "").strip()
    if not clean_reason:
        raise PlatformCreatorError("reason_required", "Role assignment reason is required", 400)

    target = await _find_user_by_normalized_email(email)
    perms = set(target.get("permissions") or [])
    perms.update({PlatformPerm.PLATFORM_CREATOR.value, PlatformPerm.PLATFORM_ADMIN.value})
    updates = {
        "platform_role": PLATFORM_CREATOR_ROLE,
        "platform_admin": True,
        "permissions": sorted(perms),
        "platform_creator_assigned_at": utc_now().isoformat(),
        "platform_creator_assigned_by_user_id": actor_user_id,
        "platform_creator_assignment_reason": clean_reason,
        "updated_at": utc_now().isoformat(),
    }
    await db.users.update_one(
        {"id": target["id"], "tenant_id": target["tenant_id"]},
        {"$set": updates},
    )
    await record_activity_with_audit(
        tenant_id=target["tenant_id"],
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        module="platform_admin",
        action="platform_creator.assigned",
        entity_type="user",
        entity_id=target["id"],
        summary=f"PLATFORM_CREATOR assigned to {target.get('email')}",
        diff={"email": normalize_email(email), "reason": clean_reason},
        metadata={"platform_role": PLATFORM_CREATOR_ROLE},
    )
    updated = await db.users.find_one({"id": target["id"], "tenant_id": target["tenant_id"]}, {"_id": 0, "password_hash": 0})
    return serialize_doc(updated)
