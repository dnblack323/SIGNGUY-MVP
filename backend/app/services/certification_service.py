"""EC8 phase 8e — Certification service.

Owns Certification issue/renew/revoke/expire-check AND the Work Order
assignment-eligibility check (`check_work_order_assignment`) — kept together
because the enforcement decision is fundamentally "does this Employee hold a
valid Certification for this Equipment", which is exactly what this module
already knows how to answer. `services/work_order_service.py` calls into
`check_work_order_assignment` rather than re-implementing any of this.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.certification import Certification
from .activity import record_activity_with_audit
from .notifications import notify

DEFAULT_CERTIFICATION_SETTINGS: dict[str, Any] = {
    "expiring_alert_windows_days": [30, 14, 7],
}

ACTIVE_STATUSES = ("not_started", "in_progress", "pending_signoff", "certified")


class CertificationError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


async def get_certification_settings(*, tenant_id: str) -> dict[str, Any]:
    from . import settings as settings_service
    stored = await settings_service.list_namespace(tenant_id=tenant_id, namespace="certification")
    return {**DEFAULT_CERTIFICATION_SETTINGS, **stored}


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def effective_status(cert: dict, today: Optional[str] = None) -> str:
    """Backend-derived status — `expired` is computed from `expiration_date`
    regardless of what's stored, so callers never have to trust a stale
    field (the stored value is also actively transitioned — see
    `_refresh_expired_status`)."""
    today = today or _today()
    if cert["status"] in ("revoked", "failed", "not_started", "in_progress", "pending_signoff"):
        return cert["status"]
    if cert.get("expiration_date") and cert["expiration_date"] < today:
        return "expired"
    return cert["status"]


def _expires_soon(cert: dict, windows_days: list[int], today: Optional[str] = None) -> bool:
    today = today or _today()
    if effective_status(cert, today) != "certified" or not cert.get("expiration_date"):
        return False
    days_left = (date.fromisoformat(cert["expiration_date"]) - date.fromisoformat(today)).days
    return 0 <= days_left <= max(windows_days or [30])


async def _refresh_expired_status(tenant_id: str, cert: dict) -> dict:
    today = _today()
    if cert["status"] == "certified" and cert.get("expiration_date") and cert["expiration_date"] < today:
        await db.certifications.update_one(
            {"id": cert["id"], "tenant_id": tenant_id},
            {"$set": {"status": "expired", "updated_at": utc_now().isoformat()}},
        )
        cert["status"] = "expired"
        await record_activity_with_audit(
            tenant_id=tenant_id, actor_user_id="system", actor_email="system@signguy.internal",
            module="team", action="certification_expired", entity_type="certification", entity_id=cert["id"],
            summary=f"Certification expired for employee {cert['employee_id']}",
        )
    return cert


async def get_certification(*, tenant_id: str, certification_id: str) -> dict:
    doc = await db.certifications.find_one({"id": certification_id, "tenant_id": tenant_id}, {"_id": 0})
    if not doc:
        raise CertificationError(404, "Certification not found")
    return serialize_doc(await _refresh_expired_status(tenant_id, doc))


async def list_certifications(
    *, tenant_id: str, employee_id: Optional[str] = None, equipment_id: Optional[str] = None,
    status: Optional[str] = None,
) -> list[dict]:
    q: dict[str, Any] = {"tenant_id": tenant_id}
    if employee_id:
        q["employee_id"] = employee_id
    if equipment_id:
        q["equipment_id"] = equipment_id
    settings = await get_certification_settings(tenant_id=tenant_id)
    windows = settings["expiring_alert_windows_days"]
    today = _today()
    out = []
    async for d in db.certifications.find(q, {"_id": 0}):
        d = serialize_doc(await _refresh_expired_status(tenant_id, d))
        if status and effective_status(d, today) != status:
            continue
        d["expires_soon"] = _expires_soon(d, windows, today)
        out.append(d)
    return out


def _active_cert_query(tenant_id: str, employee_id: str, equipment_id: Optional[str], certification_type: Optional[str]) -> dict:
    q: dict[str, Any] = {"tenant_id": tenant_id, "employee_id": employee_id, "status": {"$in": list(ACTIVE_STATUSES)}}
    if equipment_id:
        q["equipment_id"] = equipment_id
    else:
        q["certification_type"] = certification_type
    return q


async def issue_certification(
    *, tenant_id: str, employee_id: str, actor_user_id: str, actor_email: str,
    equipment_id: Optional[str] = None, certification_type: Optional[str] = None,
    source_training_assignment_id: Optional[str] = None, issued_date: Optional[str] = None,
    expiration_date: Optional[str] = None, trainer_user_id: Optional[str] = None,
    required_score: Optional[int] = None, actual_score: Optional[int] = None,
    practical_signoff_result: Optional[str] = None, restrictions: Optional[str] = None,
    renewal_of: Optional[str] = None,
) -> dict:
    if not equipment_id and not certification_type:
        raise CertificationError(400, "Either equipment_id or certification_type is required")
    emp = await db.employees.find_one({"id": employee_id, "tenant_id": tenant_id}, {"_id": 0, "id": 1})
    if not emp:
        raise CertificationError(404, "Employee not found")
    # Duplicate active certification prevention — renew (revoke+reissue with renewal_of) instead.
    dup = await db.certifications.find_one(_active_cert_query(tenant_id, employee_id, equipment_id, certification_type), {"_id": 0})
    if dup and dup["id"] != renewal_of:
        raise CertificationError(409, "An active Certification already exists for this Employee and Equipment/type — renew it instead of issuing a new one")
    doc = Certification(
        tenant_id=tenant_id, employee_id=employee_id, equipment_id=equipment_id, certification_type=certification_type,
        source_training_assignment_id=source_training_assignment_id, status="certified",
        issued_date=issued_date or _today(), expiration_date=expiration_date, trainer_user_id=trainer_user_id,
        required_score=required_score, actual_score=actual_score, practical_signoff_result=practical_signoff_result,
        restrictions=restrictions, renewal_of=renewal_of, created_by=actor_user_id, updated_by=actor_user_id,
    ).model_dump()
    await db.certifications.insert_one(prepare_for_mongo(dict(doc)))
    if renewal_of:
        await db.certifications.update_one({"id": renewal_of, "tenant_id": tenant_id}, {"$set": {"updated_at": utc_now().isoformat()}})
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="team", action="certification_issued" if not renewal_of else "certification_renewed",
        entity_type="certification", entity_id=doc["id"],
        summary=f"Certification {'renewed' if renewal_of else 'issued'} for employee {employee_id}",
    )
    await notify_employee_event(tenant_id, employee_id, "certification_issued" if not renewal_of else "certification_renewed", f"Your certification has been issued (expires {expiration_date or 'never'}).")
    doc.pop("_id", None)
    return serialize_doc(doc)


async def renew_certification(
    *, tenant_id: str, certification_id: str, actor_user_id: str, actor_email: str,
    expiration_date: Optional[str] = None, source_training_assignment_id: Optional[str] = None,
    trainer_user_id: Optional[str] = None, actual_score: Optional[int] = None,
) -> dict:
    prior = await get_certification(tenant_id=tenant_id, certification_id=certification_id)
    return await issue_certification(
        tenant_id=tenant_id, employee_id=prior["employee_id"], actor_user_id=actor_user_id, actor_email=actor_email,
        equipment_id=prior.get("equipment_id"), certification_type=prior.get("certification_type"),
        source_training_assignment_id=source_training_assignment_id, expiration_date=expiration_date,
        trainer_user_id=trainer_user_id or prior.get("trainer_user_id"), required_score=prior.get("required_score"),
        actual_score=actual_score, restrictions=prior.get("restrictions"), renewal_of=certification_id,
    )


async def revoke_certification(*, tenant_id: str, certification_id: str, actor_user_id: str, actor_email: str, reason: str) -> dict:
    if not reason or not reason.strip():
        raise CertificationError(400, "A reason is required to revoke a Certification")
    cert = await get_certification(tenant_id=tenant_id, certification_id=certification_id)
    if cert["status"] == "revoked":
        raise CertificationError(400, "Certification is already revoked")
    now_iso = utc_now().isoformat()
    await db.certifications.update_one(
        {"id": certification_id, "tenant_id": tenant_id},
        {"$set": {"status": "revoked", "revoked_at": now_iso, "revoked_by": actor_user_id,
                   "revocation_reason": reason, "updated_at": now_iso, "updated_by": actor_user_id}},
    )
    await record_activity_with_audit(
        tenant_id=tenant_id, actor_user_id=actor_user_id, actor_email=actor_email,
        module="team", action="certification_revoked", entity_type="certification", entity_id=certification_id,
        summary=f"Certification revoked for employee {cert['employee_id']}: {reason}", severity="warning",
    )
    await notify_employee_event(tenant_id, cert["employee_id"], "certification_revoked", f"Your certification was revoked: {reason}")
    return await get_certification(tenant_id=tenant_id, certification_id=certification_id)


async def notify_employee_event(tenant_id: str, employee_id: str, kind: str, title: str, body: Optional[str] = None) -> None:
    emp = await db.employees.find_one({"id": employee_id, "tenant_id": tenant_id}, {"_id": 0, "linked_user_id": 1})
    if not emp or not emp.get("linked_user_id"):
        return
    try:
        await notify(
            tenant_id=tenant_id, recipient_user_id=emp["linked_user_id"], module="team", kind=kind,
            title=title, body=body or title, entity_type="certification",
        )
    except Exception:
        pass  # notifications are best-effort — never block a certification/training action


# ---------------------------------------------------------------------------
# Work Order assignment enforcement (called by both the standalone precheck
# endpoint and `work_order_service.assign()` — SAME function, so the backend
# always revalidates on commit; nothing trusts only the pre-check).
# ---------------------------------------------------------------------------

class AssignmentBlockedError(Exception):
    def __init__(self, check: dict):
        self.check = check
        super().__init__("assignment_blocked")


class AssignmentWarningError(Exception):
    def __init__(self, check: dict):
        self.check = check
        super().__init__("assignment_warning_override_required")


async def _employee_active_certification(tenant_id: str, employee_id: str, equipment_id: str) -> Optional[dict]:
    cur = db.certifications.find({"tenant_id": tenant_id, "employee_id": employee_id, "equipment_id": equipment_id}, {"_id": 0}).sort("created_at", -1)
    docs = [serialize_doc(await _refresh_expired_status(tenant_id, d)) async for d in cur]
    for d in docs:
        if d["status"] not in ("revoked", "failed"):
            return d
    return docs[0] if docs else None


async def check_work_order_assignment(*, tenant_id: str, work_order: dict, user_ids: list[str]) -> dict:
    results = []
    any_blocked = False
    any_warning = False
    required_equipment_ids = work_order.get("required_equipment_ids") or []
    required_role = work_order.get("required_role")
    required_skill = work_order.get("required_skill")

    for uid in user_ids:
        blocked: list[dict] = []
        warnings: list[dict] = []
        user = await db.users.find_one({"id": uid, "tenant_id": tenant_id}, {"_id": 0, "id": 1, "is_active": 1})
        if not user:
            blocked.append({"code": "cross_tenant_or_missing_user", "message": "User not found in this tenant", "equipment_id": None})
            results.append({"user_id": uid, "employee_id": None, "eligible": False, "blocked": blocked, "warnings": warnings})
            any_blocked = True
            continue

        employee = await db.employees.find_one({"tenant_id": tenant_id, "linked_user_id": uid}, {"_id": 0})
        has_requirements = bool(required_equipment_ids) or bool(required_role) or bool(required_skill)

        if has_requirements:
            if not employee:
                blocked.append({"code": "no_employee_record", "message": "No Employee record is linked to this user — cannot verify Equipment/Certification requirements", "equipment_id": None})
            elif employee.get("status") != "active":
                blocked.append({"code": "employee_inactive", "message": f"Employee is {employee.get('status')}, not active", "equipment_id": None})

        for eq_id in required_equipment_ids:
            equipment = await db.equipment.find_one({"id": eq_id, "tenant_id": tenant_id}, {"_id": 0})
            if not equipment:
                blocked.append({"code": "equipment_not_found", "message": f"Required Equipment {eq_id} not found", "equipment_id": eq_id})
                continue
            policy = equipment["access_policy"]
            if policy == "no_required" or not employee:
                if policy != "no_required" and not employee:
                    pass  # already blocked above via no_employee_record
                continue
            cert = await _employee_active_certification(tenant_id, employee["id"], eq_id)
            state = effective_status(cert) if cert else "missing"
            valid = cert is not None and state == "certified"
            if valid:
                continue
            reason_map = {"missing": "no valid Certification", "expired": "Certification expired",
                          "revoked": "Certification revoked", "not_started": "Certification not started",
                          "in_progress": "Certification in progress", "pending_signoff": "Certification pending signoff",
                          "failed": "Certification failed"}
            reason = reason_map.get(state, "no valid Certification")
            if policy == "recommended":
                warnings.append({"code": "certification_recommended", "message": f"{equipment['name']}: {reason} (recommended, not required)", "equipment_id": eq_id})
            elif policy == "required_no_override":
                blocked.append({"code": f"certification_{state}", "message": f"{equipment['name']}: {reason} — this Equipment does not allow manager override", "equipment_id": eq_id})
            elif policy == "required_override_allowed":
                warnings.append({"code": f"certification_{state}", "message": f"{equipment['name']}: {reason} — manager override available with a reason", "equipment_id": eq_id})

        if required_role and employee and employee.get("role_label") and employee["role_label"] != required_role:
            warnings.append({"code": "role_mismatch", "message": f"Employee role '{employee['role_label']}' does not match required role '{required_role}'", "equipment_id": None})
        if required_skill:
            warnings.append({"code": "skill_requirement", "message": f"Advisory: verify '{required_skill}' skill before assigning — not tracked automatically", "equipment_id": None})

        eligible = len(blocked) == 0
        results.append({
            "user_id": uid, "employee_id": employee["id"] if employee else None, "employee_name": employee.get("name") if employee else None,
            "eligible": eligible, "blocked": blocked, "warnings": warnings,
        })
        if blocked:
            any_blocked = True
        if warnings:
            any_warning = True

    return {"results": results, "any_blocked": any_blocked, "any_warning": any_warning}
