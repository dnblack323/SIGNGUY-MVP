"""EC8 Phase 8b — Dev-only fixture helper.

Bridges the `dev-login` auto-provisioned Owner `User` to an `Employee`
record so Time Clock / Timesheet manual verification has real linked data
in development/preview environments (which may reset).

Scope discipline:
- Does NOT modify `dev-login` or any production identity-provisioning path.
- Does NOT make normal login create Employee records (payroll-domain
  creation stays separate from auth).
- Reuses the existing `employee_service` (same create path as the Phase 8a
  Employees API) — no parallel Employee-creation logic.
- Idempotent: looks up by `linked_user_id` first; never creates a duplicate.
- Refuses outside development (same guard pattern as `auth.py`'s
  `/auth/_dev/last-reset-token` and `/auth/dev-config`) — disabled in
  production even if `AUTH_DEV_BYPASS` were somehow set.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..core.config import get_settings
from ..core.db import db
from ..services import employee_service
from .auth import DEV_OWNER_EMAIL, DEV_TENANT_SLUG

router = APIRouter(prefix="/dev-tools", tags=["dev-tools"])
_settings = get_settings()


@router.post("/ensure-dev-employee")
async def ensure_dev_employee() -> dict:
    """DEV-ONLY: ensure the dev-login Owner has a linked, active Employee.

    Call `/api/auth/dev-login` at least once first so the Dev Shop tenant
    and Owner user exist. Safe to call repeatedly — reuses the existing
    Employee if one is already linked instead of creating another.
    """
    if _settings.env != "development" or not _settings.auth_dev_bypass:
        raise HTTPException(status_code=404, detail="Not found")

    tenant = await db.tenants.find_one({"slug": DEV_TENANT_SLUG})
    if not tenant:
        raise HTTPException(status_code=404, detail="Dev tenant not provisioned yet — call /api/auth/dev-login first")
    user = await db.users.find_one({"tenant_id": tenant["id"], "email": DEV_OWNER_EMAIL})
    if not user:
        raise HTTPException(status_code=404, detail="Dev owner not provisioned yet — call /api/auth/dev-login first")

    existing = await employee_service.get_employee_by_linked_user(tenant_id=tenant["id"], user_id=user["id"])
    if existing:
        return {"created": False, "employee": existing}

    employee = await employee_service.create_employee(
        tenant_id=tenant["id"], actor_user_id=user["id"], actor_email=user["email"],
        payload={
            "name": user.get("full_name") or "Dev Owner",
            "email": user.get("email"),
            "linked_user_id": user["id"],
            "role_label": "Owner/Admin",
        },
    )
    return {"created": True, "employee": employee}


@router.post("/mint-employee-portal-login")
async def mint_employee_portal_login(employee_id: str) -> dict:
    """DEV-ONLY (EC8 phase 8c): mint a fresh, unconsumed Employee Portal
    magic-link token for a given employee_id and return the RAW token
    directly in the response — bypassing email delivery entirely.

    Reuses the exact same invite/identity path as the real
    `/api/employee-portal/{id}/invite` flow (`employee_portal_service`); it
    just skips SendGrid so E2E verification doesn't depend on a real inbox.
    Refuses outside development, same guard as `ensure-dev-employee`.
    """
    if _settings.env != "development" or not _settings.auth_dev_bypass:
        raise HTTPException(status_code=404, detail="Not found")

    from ..services.employee_portal_service import _get_identity
    from ..services.portal_tokens import mint_magic_link_token

    tenant = await db.tenants.find_one({"slug": DEV_TENANT_SLUG})
    if not tenant:
        raise HTTPException(status_code=404, detail="Dev tenant not provisioned yet")
    identity = await _get_identity(tenant["id"], employee_id)
    if not identity:
        raise HTTPException(status_code=404, detail="No Employee Portal identity for this employee — invite first")
    raw, _ = await mint_magic_link_token(
        tenant_id=tenant["id"], portal_identity_id=identity["id"], email=identity["email"],
    )
    return {"token": raw, "identity_id": identity["id"], "verify_path": "/api/portal/auth/magic-link/verify"}
