"""EC8 phase 8c — Employee Portal onboarding (staff-side admin actions).

Additive on top of the EC6 Portal Identity system — no second identity table,
no second token system. `portal_type="employee"` distinguishes these rows
from Customer Portal identities in the very same `portal_identities`
collection. Reuses `services/portal_tokens.py::mint_magic_link_token` (the
same magic-link mechanism the Customer Portal uses) and `services/email.py`
for delivery.
"""
from __future__ import annotations

from typing import Optional

from ..core.db import db
from ..core.time_utils import serialize_doc, utc_now
from .audit import record_audit
from .email import send_email
from .portal_identity import create_portal_identity, EMPLOYEE_PORTAL_PERMS
from .portal_tokens import mint_magic_link_token

INVITE_TTL_MINUTES = 60 * 24 * 3  # 3 days — an invitation, not a quick re-login link


class EmployeePortalError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


async def _get_identity(tenant_id: str, employee_id: str) -> Optional[dict]:
    doc = await db.portal_identities.find_one(
        {"tenant_id": tenant_id, "employee_id": employee_id, "portal_type": "employee"}, {"_id": 0, "password_hash": 0},
    )
    return doc


async def get_portal_status(*, tenant_id: str, employee_id: str) -> dict:
    identity = await _get_identity(tenant_id, employee_id)
    if not identity:
        return {"invited": False, "identity": None}
    return {"invited": True, "identity": identity}


async def list_employee_portal_identities(*, tenant_id: str) -> list[dict]:
    cur = db.portal_identities.find(
        {"tenant_id": tenant_id, "portal_type": "employee"}, {"_id": 0, "password_hash": 0},
    ).sort("created_at", -1)
    return [serialize_doc(d) async for d in cur]


async def invite_employee(*, tenant_id: str, employee_id: str, request_ip: Optional[str],
                           actor_user_id: str, actor_email: str) -> dict:
    emp = await db.employees.find_one({"id": employee_id, "tenant_id": tenant_id}, {"_id": 0})
    if not emp:
        raise EmployeePortalError(404, "Employee not found")
    if emp.get("status") != "active":
        raise EmployeePortalError(400, "Only active employees can be invited to the Employee Portal")
    if not emp.get("email"):
        raise EmployeePortalError(400, "Employee has no email on file — add one before inviting")

    identity = await _get_identity(tenant_id, employee_id)
    if identity:
        # Re-inviting always re-syncs permissions to the current Employee
        # Portal grant set — protects against identities created before a
        # permission (e.g. Training/Certification self-service) was added.
        updates: dict = {"updated_at": utc_now().isoformat()}
        if identity["status"] == "disabled":
            updates["status"] = "active"
        if set(identity.get("permissions") or []) != set(EMPLOYEE_PORTAL_PERMS):
            updates["permissions"] = list(EMPLOYEE_PORTAL_PERMS)
        await db.portal_identities.update_one({"id": identity["id"], "tenant_id": tenant_id}, {"$set": updates})
        identity.update(updates)
    else:
        try:
            identity = await create_portal_identity(
                tenant_id=tenant_id, portal_type="employee", employee_id=employee_id,
                email=emp["email"], full_name=emp.get("name"), role_label=emp.get("role_label"),
                magic_link_only=True,
            )
        except ValueError as ex:
            raise EmployeePortalError(400, str(ex))

    raw, _tok = await mint_magic_link_token(
        tenant_id=tenant_id, portal_identity_id=identity["id"], email=identity["email"],
        ttl_minutes=INVITE_TTL_MINUTES, ip_issued=request_ip,
    )
    send_email(
        to_email=identity["email"],
        subject="You've been invited to the SignGuy AI Employee Portal",
        body_text=(f"You can now view your schedule, clock in/out, and check your timesheet online.\n\n"
                   f"Open your Employee Portal: /portal/employee/verify?t={raw}\n"
                   f"This single-use link expires in 3 days."),
        body_html=(f"<p>You can now view your schedule, clock in/out, and check your timesheet online.</p>"
                   f"<p><a href='/portal/employee/verify?t={raw}'>Open your Employee Portal</a></p>"
                   f"<p>This single-use link expires in 3 days.</p>"),
    )
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="employee_portal_invited", entity_type="portal_identity", entity_id=identity["id"],
        summary=f"Employee Portal invitation sent to {emp['name']} ({identity['email']})",
    )
    return identity


async def suspend_employee_portal(*, tenant_id: str, employee_id: str, actor_user_id: str, actor_email: str) -> dict:
    identity = await _get_identity(tenant_id, employee_id)
    if not identity:
        raise EmployeePortalError(404, "No Employee Portal identity exists for this employee")
    await db.portal_identities.update_one(
        {"id": identity["id"], "tenant_id": tenant_id},
        {"$set": {"status": "disabled", "updated_at": utc_now().isoformat()}},
    )
    await record_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        action="employee_portal_suspended", entity_type="portal_identity", entity_id=identity["id"],
        summary=f"Employee Portal access suspended for employee {employee_id}",
    )
    doc = await db.portal_identities.find_one({"id": identity["id"]}, {"_id": 0, "password_hash": 0})
    return serialize_doc(doc or {})
