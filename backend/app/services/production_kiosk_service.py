"""EC11 Phase 11F - shop-floor production kiosk mode.

Kiosk mode is a restricted shared-device layer. It owns device/employee kiosk
sessions and delegates stage and time-clock mutations to the existing EC11/EC8
services.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from ..core.db import db
from ..core.permissions import permissions_for_role
from ..core.security import hash_password, hash_reset_token, verify_password
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.production_kiosk import ProductionKioskDeviceSession, ProductionKioskSupervisorOverride
from . import production_board_service, production_stage_service, settings as settings_service, time_clock_service, timesheet_service
from .audit import record_audit
from .production_stage_service import ProductionStageError
from .time_clock_service import TimeEntryError

SETTINGS_NS = "production_kiosk"
DEFAULT_CONFIG: dict[str, Any] = {
    "kiosk_enabled": True,
    "device_session_ttl_minutes": 720,
    "employee_idle_timeout_minutes": 10,
    "pin_enabled": True,
    "shop_queue_visibility": "assigned_only",
    "customer_name_visible": True,
    "artwork_document_visible": False,
    "time_clock_panel_enabled": True,
    "supervisor_override_enabled": True,
    "allowed_basic_employee_actions": ["start", "resume", "wait", "block", "complete", "notes"],
    "device_labels": [],
}
ALLOWED_QUEUE_VISIBILITY = {"assigned_only", "assigned_plus_ready_for_role", "full_safe_production_queue"}
ALLOWED_BASIC_ACTIONS = {"start", "resume", "wait", "block", "complete", "notes"}
EMPLOYEE_SESSION_HEADER = "X-Kiosk-Employee-Token"
DEVICE_SESSION_HEADER = "X-Kiosk-Device-Token"
FAILED_PIN_LIMIT = 5
FAILED_PIN_WINDOW_MINUTES = 10
FAILED_PIN_LOCK_MINUTES = 5
SUPERVISOR_OVERRIDE_TTL_SECONDS = 120


class ProductionKioskError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.status_code = status_code
        super().__init__(message)


def _now_iso() -> str:
    return utc_now().isoformat()


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _token() -> str:
    return secrets.token_urlsafe(32)


def _token_hash(raw: str) -> str:
    return hash_reset_token(raw)


def _is_expired(value: Optional[str]) -> bool:
    dt = _parse_dt(value)
    return bool(dt and dt <= utc_now())


def _is_kiosk_manager(user: dict) -> bool:
    if user.get("role") in {"owner", "admin", "production_manager"}:
        return True
    perms = set(user.get("permissions") or permissions_for_role(user.get("role", "staff")))
    return "kiosk:manage" in perms


def _assert_manager(user: dict) -> None:
    if not _is_kiosk_manager(user):
        raise ProductionKioskError("kiosk_manager_required", "Only owner/admin/production manager may manage production kiosks", 403)


def _public_employee(emp: dict) -> dict:
    hidden = {
        "hourly_rate_cents",
        "notes",
        "status_history",
        "overtime_policy",
        "overtime_override",
        "kiosk_pin_hash",
        "kiosk_pin_updated_at",
        "kiosk_pin_updated_by",
    }
    return {k: v for k, v in serialize_doc(emp).items() if k not in hidden}


def _session_public(session: dict, *, include_employee: bool = True) -> dict:
    data = serialize_doc(session)
    for key in ("device_token_hash", "employee_session_token_hash"):
        data.pop(key, None)
    if not include_employee:
        for key in ("employee_id", "employee_identity_id", "employee_session_started_at", "employee_session_expires_at", "employee_last_activity_at"):
            data.pop(key, None)
    return data


def _clean_config(values: dict[str, Any]) -> dict[str, Any]:
    config = {**DEFAULT_CONFIG, **(values or {})}
    config["kiosk_enabled"] = bool(config.get("kiosk_enabled"))
    config["pin_enabled"] = bool(config.get("pin_enabled"))
    config["customer_name_visible"] = bool(config.get("customer_name_visible"))
    config["artwork_document_visible"] = bool(config.get("artwork_document_visible"))
    config["time_clock_panel_enabled"] = bool(config.get("time_clock_panel_enabled"))
    config["supervisor_override_enabled"] = bool(config.get("supervisor_override_enabled"))
    config["device_session_ttl_minutes"] = max(15, min(int(config.get("device_session_ttl_minutes") or 720), 43200))
    config["employee_idle_timeout_minutes"] = max(2, min(int(config.get("employee_idle_timeout_minutes") or 10), 120))
    if config.get("shop_queue_visibility") not in ALLOWED_QUEUE_VISIBILITY:
        config["shop_queue_visibility"] = DEFAULT_CONFIG["shop_queue_visibility"]
    actions = [a for a in list(config.get("allowed_basic_employee_actions") or []) if a in ALLOWED_BASIC_ACTIONS]
    config["allowed_basic_employee_actions"] = actions or DEFAULT_CONFIG["allowed_basic_employee_actions"]
    labels = config.get("device_labels")
    config["device_labels"] = labels if isinstance(labels, list) else []
    return config


async def get_config(tenant_id: str) -> dict[str, Any]:
    return _clean_config(await settings_service.list_namespace(tenant_id=tenant_id, namespace=SETTINGS_NS))


async def update_config(*, tenant_id: str, values: dict[str, Any], user: dict) -> dict[str, Any]:
    _assert_manager(user)
    allowed = {k: v for k, v in values.items() if k in DEFAULT_CONFIG}
    config = _clean_config({**await get_config(tenant_id), **allowed})
    await settings_service.set_many(tenant_id=tenant_id, namespace=SETTINGS_NS, values=config, updated_by=user["id"])
    await record_audit(
        tenant_id=tenant_id, actor_user_id=user["id"], actor_email=user.get("email", ""),
        action="production_kiosk.config_updated", entity_type="production_kiosk_config", entity_id=tenant_id,
        summary="Production kiosk configuration updated",
        diff={k: config.get(k) for k in sorted(allowed.keys())},
    )
    return config


async def set_employee_credential(*, tenant_id: str, employee_id: str, pin: str, user: dict) -> dict:
    _assert_manager(user)
    if not pin or len(pin.strip()) < 4:
        raise ProductionKioskError("pin_too_short", "Kiosk PIN must be at least 4 characters", 400)
    emp = await db.employees.find_one({"tenant_id": tenant_id, "id": employee_id}, {"_id": 0})
    if not emp:
        raise ProductionKioskError("employee_not_found", "Employee not found", 404)
    if emp.get("status") != "active":
        raise ProductionKioskError("employee_inactive", "Employee is not active", 400)
    identity = await db.portal_identities.find_one(
        {"tenant_id": tenant_id, "portal_type": "employee", "employee_id": employee_id, "status": "active"},
        {"_id": 0, "id": 1},
    )
    if not identity:
        raise ProductionKioskError("employee_portal_identity_required", "An active Employee Portal identity is required before kiosk PIN setup", 409)
    await db.employees.update_one(
        {"tenant_id": tenant_id, "id": employee_id},
        {"$set": {
            "kiosk_pin_hash": hash_password(pin.strip()),
            "kiosk_pin_updated_at": _now_iso(),
            "kiosk_pin_updated_by": user["id"],
            "updated_at": _now_iso(),
        }},
    )
    await record_audit(
        tenant_id=tenant_id, actor_user_id=user["id"], actor_email=user.get("email", ""),
        action="production_kiosk.employee_credential_set", entity_type="employee", entity_id=employee_id,
        summary="Production kiosk credential set for employee",
    )
    updated = await db.employees.find_one({"tenant_id": tenant_id, "id": employee_id}, {"_id": 0})
    return {"employee": _public_employee(updated or emp), "credential_configured": True}


async def activate_device(*, tenant_id: str, device_label: Optional[str], user: dict) -> dict:
    _assert_manager(user)
    config = await get_config(tenant_id)
    if not config["kiosk_enabled"]:
        raise ProductionKioskError("kiosk_disabled", "Production kiosk mode is disabled", 403)
    raw = _token()
    now = utc_now()
    expires_at = now + timedelta(minutes=int(config["device_session_ttl_minutes"]))
    doc = ProductionKioskDeviceSession(
        tenant_id=tenant_id,
        device_token_hash=_token_hash(raw),
        device_label=(device_label or "").strip() or None,
        activated_by_user_id=user["id"],
        activated_by_email=user.get("email", ""),
        activated_at=now.isoformat(),
        expires_at=expires_at.isoformat(),
        last_activity_at=now.isoformat(),
    ).model_dump()
    await db.production_kiosk_sessions.insert_one(prepare_for_mongo(doc))
    await record_audit(
        tenant_id=tenant_id, actor_user_id=user["id"], actor_email=user.get("email", ""),
        action="production_kiosk.device_activated", entity_type="production_kiosk_session", entity_id=doc["id"],
        summary=f"Production kiosk device activated: {doc.get('device_label') or doc['id']}",
        diff={"expires_at": expires_at.isoformat()},
    )
    return {"device_token": raw, "session": _session_public(doc), "config": config}


async def list_sessions(*, tenant_id: str, user: dict) -> list[dict]:
    _assert_manager(user)
    cursor = db.production_kiosk_sessions.find({"tenant_id": tenant_id}, {"_id": 0}).sort("activated_at", -1).limit(200)
    return [_session_public(s) async for s in cursor]


async def revoke_session(*, tenant_id: str, session_id: str, reason: Optional[str], user: dict) -> dict:
    _assert_manager(user)
    session = await db.production_kiosk_sessions.find_one({"tenant_id": tenant_id, "id": session_id}, {"_id": 0})
    if not session:
        raise ProductionKioskError("session_not_found", "Kiosk session not found", 404)
    now = _now_iso()
    await db.production_kiosk_sessions.update_one(
        {"tenant_id": tenant_id, "id": session_id},
        {"$set": {
            "status": "revoked",
            "revoked_at": now,
            "revoked_by_user_id": user["id"],
            "revoke_reason": (reason or "").strip() or None,
            "employee_id": None,
            "employee_identity_id": None,
            "employee_session_token_hash": None,
            "employee_session_started_at": None,
            "employee_session_expires_at": None,
            "employee_last_activity_at": None,
            "updated_at": now,
        }},
    )
    await record_audit(
        tenant_id=tenant_id, actor_user_id=user["id"], actor_email=user.get("email", ""),
        action="production_kiosk.device_revoked", entity_type="production_kiosk_session", entity_id=session_id,
        summary="Production kiosk device revoked", diff={"reason": reason},
    )
    updated = await db.production_kiosk_sessions.find_one({"tenant_id": tenant_id, "id": session_id}, {"_id": 0})
    return _session_public(updated or session)


async def require_device_session(device_token: Optional[str]) -> dict:
    if not device_token:
        raise ProductionKioskError("device_token_required", "Kiosk device token is required", 401)
    session = await db.production_kiosk_sessions.find_one({"device_token_hash": _token_hash(device_token)}, {"_id": 0})
    if not session:
        raise ProductionKioskError("invalid_device_session", "Kiosk session is invalid or expired", 401)
    if session.get("status") != "active" or _is_expired(session.get("expires_at")):
        raise ProductionKioskError("invalid_device_session", "Kiosk session is invalid or expired", 401)
    now = _now_iso()
    await db.production_kiosk_sessions.update_one(
        {"id": session["id"], "tenant_id": session["tenant_id"]},
        {"$set": {"last_activity_at": now, "updated_at": now}},
    )
    session["last_activity_at"] = now
    return serialize_doc(session)


async def inspect_device_session(device_token: Optional[str]) -> dict:
    session = await require_device_session(device_token)
    return {"session": _session_public(session, include_employee=False), "config": await get_config(session["tenant_id"])}


async def _employee_identity(tenant_id: str, employee_id: str) -> dict:
    identity = await db.portal_identities.find_one(
        {"tenant_id": tenant_id, "portal_type": "employee", "employee_id": employee_id, "status": "active"},
        {"_id": 0},
    )
    if not identity:
        raise ProductionKioskError("invalid_employee_credentials", "Invalid employee credentials", 401)
    return serialize_doc(identity)


async def _record_failed_identification(session: dict) -> None:
    now = utc_now()
    window_start = _parse_dt(session.get("failed_identification_window_started_at"))
    if not window_start or window_start <= now - timedelta(minutes=FAILED_PIN_WINDOW_MINUTES):
        count = 1
        window = now.isoformat()
    else:
        count = int(session.get("failed_identification_count") or 0) + 1
        window = session.get("failed_identification_window_started_at")
    updates: dict[str, Any] = {
        "failed_identification_count": count,
        "failed_identification_window_started_at": window,
        "updated_at": now.isoformat(),
    }
    if count >= FAILED_PIN_LIMIT:
        updates["identification_locked_until"] = (now + timedelta(minutes=FAILED_PIN_LOCK_MINUTES)).isoformat()
    await db.production_kiosk_sessions.update_one({"tenant_id": session["tenant_id"], "id": session["id"]}, {"$set": updates})


async def identify_employee(*, device_token: Optional[str], employee_id: str, pin: str) -> dict:
    session = await require_device_session(device_token)
    if _is_expired(session.get("identification_locked_until")):
        await db.production_kiosk_sessions.update_one(
            {"tenant_id": session["tenant_id"], "id": session["id"]},
            {"$set": {"identification_locked_until": None}},
        )
        session["identification_locked_until"] = None
    if session.get("identification_locked_until"):
        raise ProductionKioskError("identification_rate_limited", "Too many failed attempts. Try again shortly.", 429)
    config = await get_config(session["tenant_id"])
    if not config["pin_enabled"]:
        raise ProductionKioskError("pin_disabled", "Employee kiosk PIN identification is disabled", 403)
    emp = await db.employees.find_one({"tenant_id": session["tenant_id"], "id": employee_id}, {"_id": 0})
    if not emp or emp.get("status") != "active" or not emp.get("kiosk_pin_hash") or not verify_password(pin or "", emp["kiosk_pin_hash"]):
        await _record_failed_identification(session)
        raise ProductionKioskError("invalid_employee_credentials", "Invalid employee credentials", 401)
    identity = await _employee_identity(session["tenant_id"], employee_id)
    raw_employee_token = _token()
    now = utc_now()
    expires_at = now + timedelta(minutes=int(config["employee_idle_timeout_minutes"]))
    await db.production_kiosk_sessions.update_one(
        {"tenant_id": session["tenant_id"], "id": session["id"]},
        {"$set": {
            "employee_id": employee_id,
            "employee_identity_id": identity["id"],
            "employee_session_token_hash": _token_hash(raw_employee_token),
            "employee_session_started_at": now.isoformat(),
            "employee_session_expires_at": expires_at.isoformat(),
            "employee_last_activity_at": now.isoformat(),
            "failed_identification_count": 0,
            "failed_identification_window_started_at": None,
            "identification_locked_until": None,
            "updated_at": now.isoformat(),
        }},
    )
    await record_audit(
        tenant_id=session["tenant_id"], actor_user_id=f"kiosk:{session['id']}:{employee_id}", actor_email=identity.get("email", ""),
        action="production_kiosk.employee_identified", entity_type="production_kiosk_session", entity_id=session["id"],
        summary="Employee identified on production kiosk",
        diff={"employee_id": employee_id, "employee_identity_id": identity["id"]},
    )
    return {
        "employee_token": raw_employee_token,
        "employee": _public_employee(emp),
        "session": _session_public(await db.production_kiosk_sessions.find_one({"tenant_id": session["tenant_id"], "id": session["id"]}, {"_id": 0}) or session),
        "config": config,
    }


async def end_employee_session(*, device_token: Optional[str]) -> dict:
    session = await require_device_session(device_token)
    now = _now_iso()
    previous_employee_id = session.get("employee_id")
    await db.production_kiosk_sessions.update_one(
        {"tenant_id": session["tenant_id"], "id": session["id"]},
        {"$set": {
            "employee_id": None,
            "employee_identity_id": None,
            "employee_session_token_hash": None,
            "employee_session_started_at": None,
            "employee_session_expires_at": None,
            "employee_last_activity_at": None,
            "updated_at": now,
        }},
    )
    await record_audit(
        tenant_id=session["tenant_id"], actor_user_id=f"kiosk:{session['id']}", actor_email="production-kiosk",
        action="production_kiosk.employee_session_cleared", entity_type="production_kiosk_session", entity_id=session["id"],
        summary="Employee kiosk session cleared", diff={"employee_id": previous_employee_id},
    )
    updated = await db.production_kiosk_sessions.find_one({"tenant_id": session["tenant_id"], "id": session["id"]}, {"_id": 0})
    return {"session": _session_public(updated or session, include_employee=False)}


async def require_employee_session(device_token: Optional[str], employee_token: Optional[str]) -> dict:
    session = await require_device_session(device_token)
    if not employee_token or not session.get("employee_id") or not session.get("employee_session_token_hash"):
        raise ProductionKioskError("employee_session_required", "Employee kiosk session is required", 401)
    if _token_hash(employee_token) != session["employee_session_token_hash"] or _is_expired(session.get("employee_session_expires_at")):
        raise ProductionKioskError("employee_session_expired", "Employee kiosk session is invalid or expired", 401)
    emp = await db.employees.find_one({"tenant_id": session["tenant_id"], "id": session["employee_id"], "status": "active"}, {"_id": 0})
    if not emp:
        raise ProductionKioskError("employee_session_expired", "Employee kiosk session is invalid or expired", 401)
    config = await get_config(session["tenant_id"])
    now = utc_now()
    expires_at = now + timedelta(minutes=int(config["employee_idle_timeout_minutes"]))
    await db.production_kiosk_sessions.update_one(
        {"tenant_id": session["tenant_id"], "id": session["id"]},
        {"$set": {
            "employee_last_activity_at": now.isoformat(),
            "employee_session_expires_at": expires_at.isoformat(),
            "last_activity_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }},
    )
    session["employee_last_activity_at"] = now.isoformat()
    session["employee_session_expires_at"] = expires_at.isoformat()
    session["employee"] = serialize_doc(emp)
    session["config"] = config
    return session


def _kiosk_actor(session: dict) -> dict:
    return {
        "id": f"kiosk:{session['id']}:{session['employee_id']}",
        "tenant_id": session["tenant_id"],
        "email": "production-kiosk",
        "role": "employee_kiosk",
        "permissions": [],
    }


async def get_work_view(*, session: dict, search: Optional[str] = None) -> dict:
    config = session.get("config") or await get_config(session["tenant_id"])
    try:
        data = await production_board_service.get_employee_kiosk_view(
            tenant_id=session["tenant_id"],
            employee_id=session["employee_id"],
            search=search,
            shop_queue_visibility=config["shop_queue_visibility"],
            customer_name_visible=config["customer_name_visible"],
            allowed_basic_actions=config["allowed_basic_employee_actions"],
        )
    except production_board_service.ProductionBoardError as e:
        raise ProductionKioskError(e.code, str(e), 404)
    return {"employee": _public_employee(session["employee"]), "config": config, **data}


def _stage_error(e: ProductionStageError) -> ProductionKioskError:
    status = {
        "stage_not_found": 404,
        "work_order_not_found": 404,
        "invalid_transition": 400,
        "previous_stage_incomplete": 409,
        "proof_gate_blocked": 409,
        "reason_required": 400,
        "note_required": 400,
        "manager_required": 403,
        "employee_not_found": 404,
        "employee_inactive": 400,
        "assignment_blocked": 409,
        "assignment_warning_override_required": 409,
    }.get(e.code, 400)
    return ProductionKioskError(e.code, str(e), status)


async def _consume_override(*, tenant_id: str, session: dict, action: str, stage_id: str, token: Optional[str]) -> Optional[dict]:
    if not token:
        return None
    override = await db.production_kiosk_supervisor_overrides.find_one(
        {"tenant_id": tenant_id, "override_token_hash": _token_hash(token), "kiosk_session_id": session["id"]},
        {"_id": 0},
    )
    if not override or override.get("consumed_at") or _is_expired(override.get("expires_at")):
        raise ProductionKioskError("invalid_supervisor_override", "Supervisor override is invalid or expired", 403)
    if override.get("employee_id") != session.get("employee_id") or override.get("action") != action or override.get("stage_id") != stage_id:
        raise ProductionKioskError("invalid_supervisor_override", "Supervisor override does not match this action", 403)
    now = _now_iso()
    await db.production_kiosk_supervisor_overrides.update_one(
        {"tenant_id": tenant_id, "id": override["id"]},
        {"$set": {"consumed_at": now, "consumed_by_employee_id": session["employee_id"], "updated_at": now}},
    )
    await record_audit(
        tenant_id=tenant_id, actor_user_id=override["supervisor_user_id"], actor_email=override["supervisor_email"],
        action="production_kiosk.supervisor_override_consumed", entity_type="production_stage", entity_id=stage_id,
        summary=f"Supervisor override consumed for kiosk action: {action}",
        diff={"employee_id": session["employee_id"], "reason": override["reason"], "kiosk_session_id": session["id"]},
    )
    return serialize_doc(override)


async def perform_stage_action(*, session: dict, stage_id: str, action: str, payload: dict[str, Any]) -> dict:
    config = session.get("config") or await get_config(session["tenant_id"])
    if action not in {"start", "resume", "wait", "block", "complete", "notes"}:
        raise ProductionKioskError("action_not_allowed", "This kiosk action is not allowed", 403)
    if action not in set(config["allowed_basic_employee_actions"]):
        raise ProductionKioskError("action_not_allowed", "This kiosk action is disabled", 403)
    try:
        stage = await production_stage_service.get_stage(tenant_id=session["tenant_id"], stage_id=stage_id)
    except ProductionStageError as e:
        raise _stage_error(e)
    if not bool(stage.get("employee_visible", True)):
        raise ProductionKioskError("stage_not_found", "Production task not found", 404)
    override = await _consume_override(
        tenant_id=session["tenant_id"],
        session=session,
        action=action,
        stage_id=stage_id,
        token=payload.get("supervisor_override_token"),
    )
    assigned_to_self = stage.get("assigned_employee_id") == session["employee_id"]
    if not assigned_to_self:
        if not override or action not in {"start"}:
            raise ProductionKioskError("stage_not_assigned", "Production task is not assigned to this employee", 403)
        try:
            supervisor = {
                "id": override["supervisor_user_id"],
                "tenant_id": session["tenant_id"],
                "email": override["supervisor_email"],
                "role": override["supervisor_role"],
                "permissions": permissions_for_role(override["supervisor_role"]),
            }
            stage = await production_stage_service.assign_stage(
                tenant_id=session["tenant_id"], stage_id=stage_id, employee_id=session["employee_id"],
                override_reason=override["reason"], user=supervisor,
            )
        except ProductionStageError as e:
            raise _stage_error(e)
    actor = _kiosk_actor(session)
    try:
        if action == "notes":
            return await production_stage_service.add_stage_note(
                tenant_id=session["tenant_id"], stage_id=stage_id, note=payload.get("note") or "", user=actor,
            )
        target = {
            "start": "in_progress",
            "resume": "in_progress",
            "wait": "waiting",
            "block": "blocked",
            "complete": "completed",
        }[action]
        return await production_stage_service.transition_stage(
            tenant_id=session["tenant_id"], stage_id=stage["id"], target=target, user=actor,
            reason=payload.get("reason"), completion_note=payload.get("completion_note"),
        )
    except ProductionStageError as e:
        raise _stage_error(e)


async def create_supervisor_override(*, tenant_id: str, device_token: Optional[str], employee_id: str, stage_id: str, action: str, reason: str, user: dict) -> dict:
    _assert_manager(user)
    session = await require_device_session(device_token)
    if session["tenant_id"] != tenant_id:
        raise ProductionKioskError("session_not_found", "Kiosk session not found", 404)
    config = await get_config(tenant_id)
    if not config["supervisor_override_enabled"]:
        raise ProductionKioskError("supervisor_override_disabled", "Supervisor overrides are disabled", 403)
    if not reason or not reason.strip():
        raise ProductionKioskError("reason_required", "Supervisor override reason is required", 400)
    if session.get("employee_id") != employee_id:
        raise ProductionKioskError("employee_session_required", "Override employee must match the active kiosk employee", 409)
    raw = _token()
    expires_at = utc_now() + timedelta(seconds=SUPERVISOR_OVERRIDE_TTL_SECONDS)
    doc = ProductionKioskSupervisorOverride(
        tenant_id=tenant_id,
        kiosk_session_id=session["id"],
        employee_id=employee_id,
        supervisor_user_id=user["id"],
        supervisor_email=user.get("email", ""),
        supervisor_role=user.get("role", "staff"),
        action=action,
        stage_id=stage_id,
        reason=reason.strip(),
        override_token_hash=_token_hash(raw),
        expires_at=expires_at.isoformat(),
    ).model_dump()
    await db.production_kiosk_supervisor_overrides.insert_one(prepare_for_mongo(doc))
    await record_audit(
        tenant_id=tenant_id, actor_user_id=user["id"], actor_email=user.get("email", ""),
        action="production_kiosk.supervisor_override_created", entity_type="production_stage", entity_id=stage_id,
        summary=f"Supervisor override created for kiosk action: {action}",
        diff={"employee_id": employee_id, "reason": reason, "kiosk_session_id": session["id"]},
    )
    public = serialize_doc(doc)
    public.pop("override_token_hash", None)
    return {"override_token": raw, "override": public}


async def get_time_clock_status(session: dict) -> dict:
    config = session.get("config") or await get_config(session["tenant_id"])
    if not config["time_clock_panel_enabled"]:
        raise ProductionKioskError("time_clock_disabled", "Time Clock panel is disabled", 403)
    active = await time_clock_service.get_active_entry(tenant_id=session["tenant_id"], employee_id=session["employee_id"])
    return {"active_entry": active, "label": "Work Shift Time"}


async def clock_in(*, session: dict, work_order_id: Optional[str] = None, notes: Optional[str] = None) -> dict:
    try:
        return await time_clock_service.clock_in(
            tenant_id=session["tenant_id"], employee_id=session["employee_id"],
            actor_user_id=_kiosk_actor(session)["id"], actor_email="production-kiosk",
            source="self", work_order_id=work_order_id, notes=notes,
        )
    except TimeEntryError as e:
        raise ProductionKioskError("time_clock_error", e.detail, e.status_code)


async def clock_out(session: dict) -> dict:
    try:
        entry = await time_clock_service.clock_out(
            tenant_id=session["tenant_id"], employee_id=session["employee_id"],
            actor_user_id=_kiosk_actor(session)["id"], actor_email="production-kiosk",
        )
        await timesheet_service.refresh_after_time_entry_change(
            tenant_id=session["tenant_id"], employee_id=session["employee_id"], work_date=entry["work_date"],
        )
        return entry
    except TimeEntryError as e:
        raise ProductionKioskError("time_clock_error", e.detail, e.status_code)
