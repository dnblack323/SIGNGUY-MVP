"""Focused Webstore shared helpers."""
from __future__ import annotations

from .webstore_context import *
from .webstore_shared_repository import _get_store

def _require_staff_perm(user: dict, perm: Perm) -> None:
    if perm.value not in set(permissions_for_role(user.get("role", "staff"))):
        raise WebstoreError("permission_denied", f"Missing permission: {perm.value}", 403)


async def _require_webstore_assignment_scope(user: dict, webstore_id: str) -> None:
    """Enforce explicit active Webstore assignments when they exist for a user.

    Tenant owners/admins without an assignment remain tenant-wide. A user with
    an active assignment is restricted to the stores assigned to that account;
    this keeps staff routes consistent with the portal assignment authority.
    """
    assigned_store_id = user.get("webstore_id")
    assigned_store_ids = {str(value) for value in (user.get("webstore_ids") or [])}
    if assigned_store_id and str(assigned_store_id) != webstore_id:
        raise WebstoreError(
            "webstore_assignment_scope_forbidden",
            "Webstore access is limited to the assigned Webstore",
            403,
        )
    if assigned_store_ids and webstore_id not in assigned_store_ids:
        raise WebstoreError(
            "webstore_assignment_scope_forbidden",
            "Webstore access is limited to assigned Webstores",
            403,
        )

    identity_filters = [{"portal_identity_id": str(user.get("id"))}]
    email = str(user.get("email") or "").strip().lower()
    if email:
        identity_filters.append({"email": email})
    assignments = [
        doc
        async for doc in db.webstore_access_assignments.find(
            {
                "tenant_id": user["tenant_id"],
                "status": "active",
                "$or": identity_filters,
            },
            {"_id": 0, "webstore_id": 1},
        )
    ]
    if assignments:
        allowed_store_ids = {str(doc["webstore_id"]) for doc in assignments if doc.get("webstore_id")}
        if webstore_id not in allowed_store_ids:
            raise WebstoreError(
                "webstore_assignment_scope_forbidden",
                "Webstore access is limited to assigned Webstores",
                403,
            )


def _require_platform_creator(user: dict) -> None:
    if not has_platform_admin_access(user, extra_permissions={PlatformPerm.PLATFORM_CREATOR.value}):
        raise WebstoreError("platform_creator_required", "Platform Creator access is required for platform starter templates", 403)

async def _owner_portal_store(identity: dict, webstore_id: str) -> dict:
    if identity.get("portal_type") not in {"webstore_owner", "webstore_manager"}:
        raise WebstoreError("webstore_portal_required", "Webstore portal access required", 403)
    store = await _get_store(identity["tenant_id"], webstore_id)
    assignment = await db.webstore_access_assignments.find_one(
        {
            "tenant_id": identity["tenant_id"],
            "webstore_id": webstore_id,
            "portal_identity_id": identity.get("id"),
            "status": "active",
        },
        {"_id": 0},
    )
    if assignment:
        return store
    assignment_count = await db.webstore_access_assignments.count_documents(
        {"tenant_id": identity["tenant_id"], "portal_identity_id": identity.get("id")}
    )
    if assignment_count:
        raise WebstoreError("webstore_assignment_scope_forbidden", "Webstore portal access is limited to assigned Webstores", 403)
    owner_id = identity.get("webstore_owner_id")
    if owner_id and store.get("owner_id") != owner_id:
        raise WebstoreError("webstore_scope_forbidden", "Webstore portal access is owner-scoped", 403)
    if not owner_id:
        raise WebstoreError("webstore_owner_scope_required", "Webstore owner scope is required", 403)
    assigned_webstore_id = identity.get("webstore_id")
    if identity.get("portal_type") == "webstore_manager":
        if not assigned_webstore_id:
            raise WebstoreError("webstore_manager_assignment_required", "Webstore manager scope is required", 403)
        if assigned_webstore_id != webstore_id:
            raise WebstoreError("webstore_manager_scope_forbidden", "Webstore manager access is limited to the assigned Webstore", 403)
    return store

__all__ = [name for name in globals() if not name.startswith("__")]
