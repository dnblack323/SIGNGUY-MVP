"""EC15 - Wrap Lab shared-core service layer."""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from math import ceil
from typing import Any, Optional

from ..core.db import db
from ..core.permissions import Perm, permissions_for_role
from ..core.portal_security import hash_token
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.wrap_lab import (
    WrapActivity,
    WrapCoveragePlan,
    WrapDesignScene,
    WrapInspection,
    WrapInstallationRecord,
    WrapPacket,
    WrapPanelPlan,
    WrapProject,
    WrapSchedule,
    WrapVehicle,
    WrapWarranty,
)
from ..repositories.wrap_lab import WrapLabRepository
from .activity import record_activity_with_audit
from . import order_readiness_service
from .approvals_signatures_service import create_signature_request, record_signature
from .portal_tokens import mint_public_action_token

PROJECT_STATUS_ORDER = [
    "lead_intake",
    "vehicle_recorded",
    "measurement_planning",
    "estimate_ready",
    "quote_linked",
    "contract_deposit_pending",
    "pre_install_ready",
    "pre_install_signed",
    "design_in_progress",
    "proof_ready",
    "proof_approved",
    "panel_plan_ready",
    "production_ready",
    "install_scheduled",
    "installing",
    "completion_packet_ready",
    "completed",
    "warranty_active",
    "archived",
]

vehicles_repo = WrapLabRepository("wrap_vehicles")
projects_repo = WrapLabRepository("wrap_projects")
coverage_repo = WrapLabRepository("wrap_coverage_plans")
inspections_repo = WrapLabRepository("wrap_inspections")
designs_repo = WrapLabRepository("wrap_design_scenes")
panel_plans_repo = WrapLabRepository("wrap_panel_plans")
packets_repo = WrapLabRepository("wrap_packets")
schedules_repo = WrapLabRepository("wrap_schedules")
warranties_repo = WrapLabRepository("wrap_warranties")
installations_repo = WrapLabRepository("wrap_installation_records")

READINESS_REQUIREMENTS = {
    "inspection": "pre-install inspection is completed or ready for customer signature",
    "signature": "customer pre-install acknowledgment is signed",
    "proof": "current proof or design approval is present",
    "panel_plan": "production panel plan is ready",
}

APPROVAL_SENSITIVE_PROJECT_FIELDS = {"project_type", "coverage_summary", "specifications", "vehicle_id"}
APPROVAL_SENSITIVE_VEHICLE_FIELDS = {
    "year",
    "make",
    "model",
    "trim",
    "body_style",
    "vin",
    "license_plate",
    "color",
    "unit_number",
    "vehicle_type",
    "template_key",
    "dimensions",
    "measured_wrap_areas",
}


class WrapLabError(Exception):
    def __init__(self, code: str, detail: str, status_code: int = 400):
        self.code = code
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def _now_iso() -> str:
    return utc_now().isoformat()


def _parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _require_staff_perm(user: dict, perm: Perm) -> None:
    if perm.value not in set(permissions_for_role(user.get("role", "staff"))):
        raise WrapLabError("permission_denied", f"Missing permission: {perm.value}", 403)


def _clean_text(value: Any, field: str, *, limit: int = 200) -> str:
    text = str(value or "").strip()
    if not text:
        raise WrapLabError(f"{field}_required", f"{field} is required", 400)
    if len(text) > limit:
        raise WrapLabError(f"{field}_too_long", f"{field} must be {limit} characters or fewer", 400)
    return text


def _optional_text(value: Any, *, limit: int = 2000) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text[:limit] if text else None


def _non_negative_cents(value: Any, field: str) -> int:
    cents = int(value or 0)
    if cents < 0:
        raise WrapLabError("invalid_cents", f"{field} must be non-negative integer cents", 400)
    return cents


async def _audit(
    *,
    tenant_id: str,
    project_id: str,
    user: dict,
    action: str,
    entity_type: str,
    entity_id: str,
    summary: str,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    activity = WrapActivity(
        tenant_id=tenant_id,
        project_id=project_id,
        actor_id=user.get("id"),
        actor_email=user.get("email"),
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        metadata=metadata or {},
    ).model_dump()
    await db.wrap_activity_events.insert_one(prepare_for_mongo(activity))
    await record_activity_with_audit(
        tenant_id=tenant_id,
        actor_user_id=user.get("id", "unknown"),
        actor_email=user.get("email", "unknown"),
        module="wrap_lab",
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        metadata={"project_id": project_id, **(metadata or {})},
    )


async def _audit_public(
    *,
    tenant_id: str,
    project_id: str,
    action: str,
    entity_type: str,
    entity_id: str,
    summary: str,
    metadata: Optional[dict[str, Any]] = None,
    actor_email: str = "public@wrap-inspection",
) -> None:
    activity = WrapActivity(
        tenant_id=tenant_id,
        project_id=project_id,
        actor_type="public_token",
        actor_id=(metadata or {}).get("token_id"),
        actor_email=actor_email,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        metadata=metadata or {},
    ).model_dump()
    await db.wrap_activity_events.insert_one(prepare_for_mongo(activity))
    await record_activity_with_audit(
        tenant_id=tenant_id,
        actor_user_id=f"public_token:{(metadata or {}).get('token_id', 'unknown')}",
        actor_email=actor_email,
        module="wrap_lab",
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        metadata={"project_id": project_id, **(metadata or {})},
    )


async def _get_project(tenant_id: str, project_id: str) -> dict:
    project = await projects_repo.get(tenant_id=tenant_id, entity_id=project_id)
    if not project:
        raise WrapLabError("wrap_project_not_found", "Wrap Lab project not found", 404)
    return project


async def _ensure_open_project(project: dict) -> None:
    if project.get("status") == "archived":
        raise WrapLabError("project_archived", "Archived Wrap Lab projects are read-only", 409)


async def _assert_customer(tenant_id: str, customer_id: Optional[str]) -> None:
    if not customer_id:
        return
    customer = await db.customers.find_one({"tenant_id": tenant_id, "id": customer_id}, {"_id": 0})
    if not customer:
        raise WrapLabError("customer_not_found", "Customer not found", 404)


async def _assert_ref(collection: str, tenant_id: str, entity_id: Optional[str], code: str) -> None:
    if not entity_id:
        return
    doc = await db[collection].find_one({"tenant_id": tenant_id, "id": entity_id}, {"_id": 0})
    if not doc:
        raise WrapLabError(code, f"Referenced {collection} record not found", 404)


async def _get_ref(collection: str, tenant_id: str, entity_id: Optional[str], code: str) -> Optional[dict[str, Any]]:
    if not entity_id:
        return None
    doc = await db[collection].find_one({"tenant_id": tenant_id, "id": entity_id}, {"_id": 0})
    if not doc:
        raise WrapLabError(code, f"Referenced {collection} record not found", 404)
    return serialize_doc(doc)


async def _validate_file_ids(tenant_id: str, file_ids: list[str]) -> None:
    ids = [fid for fid in file_ids if fid]
    if not ids:
        return
    count = await db.files.count_documents({"tenant_id": tenant_id, "id": {"$in": ids}})
    if count != len(set(ids)):
        raise WrapLabError("file_not_found", "One or more referenced files were not found for this tenant", 404)


def _is_wrap_order_item(item: Optional[dict[str, Any]]) -> bool:
    if not item:
        return False
    text = " ".join(
        str(item.get(key) or "")
        for key in ["category", "product_type", "description", "item_name", "material_key"]
    ).lower()
    snapshot = item.get("pricing_snapshot") if isinstance(item.get("pricing_snapshot"), dict) else {}
    text += " " + str(snapshot.get("category") or "").lower()
    return "wrap" in text or "vehicle_graphics" in text or item.get("source_type") == "wrap_project"


async def _validate_project_links(tenant_id: str, fields: dict[str, Any]) -> dict[str, Optional[dict[str, Any]]]:
    customer_id = fields.get("customer_id")
    if not customer_id:
        raise WrapLabError("customer_required", "A customer is required for a Wrap Project", 400)
    customer = await _get_ref("customers", tenant_id, customer_id, "customer_not_found")
    vehicle = await _get_ref("wrap_vehicles", tenant_id, fields.get("vehicle_id"), "vehicle_not_found")
    intake = await _get_ref("intake_submissions", tenant_id, fields.get("intake_id"), "intake_not_found")
    quote = await _get_ref("quotes", tenant_id, fields.get("quote_id"), "quote_not_found")
    order = await _get_ref("orders", tenant_id, fields.get("order_id"), "order_not_found")
    order_item = await _get_ref("order_items", tenant_id, fields.get("order_item_id"), "order_item_not_found")
    work_order_id = fields.get("work_order_id") or fields.get("work_order_summary_id")
    work_order = await _get_ref("work_orders", tenant_id, work_order_id, "work_order_not_found")
    if vehicle and vehicle.get("customer_id") and vehicle.get("customer_id") != customer_id:
        raise WrapLabError("vehicle_customer_mismatch", "Vehicle belongs to a different customer", 409)
    for name, doc in [("quote", quote), ("order", order), ("work_order", work_order)]:
        if doc and doc.get("customer_id") and doc.get("customer_id") != customer_id:
            raise WrapLabError(f"{name}_customer_mismatch", f"Referenced {name.replace('_', ' ')} belongs to a different customer", 409)
    if order_item:
        if order and order_item.get("order_id") != order.get("id"):
            raise WrapLabError("order_item_order_mismatch", "Order Item does not belong to the selected Order", 409)
        if not _is_wrap_order_item(order_item):
            raise WrapLabError("order_item_not_wrap", "Selected Order Item is not classified as vehicle-wrap work", 409)
    if work_order and order and work_order.get("order_id") != order.get("id"):
        raise WrapLabError("work_order_order_mismatch", "Work Order does not belong to the selected Order", 409)
    return {
        "customer": customer,
        "vehicle": vehicle,
        "intake": intake,
        "quote": quote,
        "order": order,
        "order_item": order_item,
        "work_order": work_order,
    }


async def _prevent_duplicate_project(tenant_id: str, fields: dict[str, Any], *, exclude_project_id: Optional[str] = None) -> None:
    checks: list[dict[str, Any]] = []
    if fields.get("order_item_id"):
        checks.append({"order_item_id": fields["order_item_id"]})
    if fields.get("work_order_id") or fields.get("work_order_summary_id"):
        work_order_checks = []
        if fields.get("work_order_id"):
            work_order_checks.append({"work_order_id": fields.get("work_order_id")})
        if fields.get("work_order_summary_id") or fields.get("work_order_id"):
            work_order_checks.append({"work_order_summary_id": fields.get("work_order_summary_id") or fields.get("work_order_id")})
        checks.append({"$or": work_order_checks})
    if fields.get("quote_id") and fields.get("vehicle_id"):
        checks.append({"quote_id": fields["quote_id"], "vehicle_id": fields["vehicle_id"]})
    if fields.get("order_id") and fields.get("vehicle_id"):
        checks.append({"order_id": fields["order_id"], "vehicle_id": fields["vehicle_id"]})
    if not checks:
        return
    query: dict[str, Any] = {"tenant_id": tenant_id, "status": {"$ne": "archived"}, "$or": checks}
    if exclude_project_id:
        query["id"] = {"$ne": exclude_project_id}
    existing = await db.wrap_projects.find_one(query, {"_id": 0, "id": 1, "project_name": 1})
    if existing:
        raise WrapLabError("duplicate_wrap_project", f"A Wrap Project already exists for this commercial item: {existing.get('project_name') or existing.get('id')}", 409)


def _financially_safe_project(project: dict[str, Any]) -> dict[str, Any]:
    safe = dict(project)
    for key in ["estimate_total_cents", "deposit_required_cents", "material_estimate_cents", "labor_estimate_cents"]:
        safe.pop(key, None)
    return safe


def _completion_status(inspection: dict[str, Any]) -> str:
    if inspection.get("status") in {"signed", "completed"}:
        return "complete"
    required = inspection.get("required_views") or []
    photos = set(inspection.get("before_photo_file_ids") or []) | set(inspection.get("after_photo_file_ids") or [])
    if required and len(photos) < len(required):
        return "missing_photos"
    return "in_progress"


def _latest(items: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not items:
        return None
    return sorted(items, key=lambda d: str(d.get("updated_at") or d.get("created_at") or ""), reverse=True)[0]


def _signature_parent_id(project_id: str, inspection_id: str) -> str:
    return f"wrap-inspection:{project_id}:{inspection_id}"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _approval_fingerprint(project: dict[str, Any], vehicle: Optional[dict[str, Any]] = None) -> str:
    vehicle = vehicle or {}
    sensitive = {
        "project_type": project.get("project_type"),
        "coverage_summary": project.get("coverage_summary"),
        "specifications": project.get("specifications") or {},
        "vehicle": {key: vehicle.get(key) for key in sorted(APPROVAL_SENSITIVE_VEHICLE_FIELDS)},
    }
    return hashlib.sha256(_canonical_json(sensitive).encode("utf-8")).hexdigest()


def _approval_filters_for_project(project: dict[str, Any]) -> list[dict[str, Any]]:
    filters = [{"parent_type": "wrap_project", "parent_id": project["id"]}]
    for parent_type, key in [("quote", "quote_id"), ("order", "order_id"), ("order_item", "order_item_id"), ("work_order_summary", "work_order_summary_id")]:
        if project.get(key):
            filters.append({"parent_type": parent_type, "parent_id": project[key]})
    return filters


def _evidence_revision(item: dict[str, Any]) -> Optional[int]:
    sources = [
        item,
        item.get("snapshot") if isinstance(item.get("snapshot"), dict) else {},
        item.get("metadata") if isinstance(item.get("metadata"), dict) else {},
    ]
    for source in sources:
        value = source.get("wrap_project_revision")
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                return None
    return None


def _matches_current_wrap_revision(item: dict[str, Any], project_revision: int) -> bool:
    revision = _evidence_revision(item)
    return revision == project_revision or (revision is None and project_revision == 1)


async def _bump_approval_revision(
    user: dict,
    project: dict[str, Any],
    *,
    reason: str,
    changed_fields: list[str],
    vehicle: Optional[dict[str, Any]] = None,
    force: bool = False,
) -> dict[str, Any]:
    current_revision = int(project.get("approval_revision") or 1)
    fingerprint = _approval_fingerprint(project, vehicle)
    if not force and project.get("approval_fingerprint") == fingerprint:
        return project
    new_revision = current_revision + 1 if project.get("approval_fingerprint") else current_revision
    now = _now_iso()
    log_entry = {
        "revision": new_revision,
        "previous_revision": current_revision,
        "changed_at": now,
        "changed_by": user.get("id"),
        "reason": reason,
        "fields": sorted(set(changed_fields)),
    }
    updates = {
        "approval_revision": new_revision,
        "approval_fingerprint": fingerprint,
        "approval_revision_changed_at": now,
        "approval_revision_changed_reason": reason,
        "approval_sensitive_change_log": [*(project.get("approval_sensitive_change_log") or []), log_entry],
    }
    revision_query: dict[str, Any] = {"tenant_id": project["tenant_id"], "id": project["id"], "approval_revision": current_revision}
    if current_revision == 1 and "approval_revision" not in project:
        revision_query = {"tenant_id": project["tenant_id"], "id": project["id"], "$or": [{"approval_revision": 1}, {"approval_revision": {"$exists": False}}]}
    result = await db.wrap_projects.update_one(
        revision_query,
        {"$set": prepare_for_mongo({**updates, "updated_at": now})},
    )
    if result.matched_count == 0:
        raise WrapLabError("stale_wrap_project_revision", "Wrap Project approval revision changed. Reload before saving approval-sensitive changes.", 409)
    approval_filters = _approval_filters_for_project(project)
    await db.approvals.update_many(
        {"tenant_id": project["tenant_id"], "$or": approval_filters, "status": "current"},
        {"$set": {"status": "superseded", "superseded_at": now, "superseded_reason": reason}},
    )
    proof_filters = [{"parent_type": f["parent_type"], "parent_id": f["parent_id"]} for f in approval_filters]
    if proof_filters:
        await db.proofs.update_many(
            {"tenant_id": project["tenant_id"], "$or": proof_filters, "status": {"$nin": ["cancelled", "superseded", "archived"]}},
            {"$set": {"wrap_project_stale": True, "stale_at": now, "stale_reason": reason, "updated_at": now}},
        )
    await _audit(
        tenant_id=project["tenant_id"],
        project_id=project["id"],
        user=user,
        action="wrap_lab.approval_revision_changed",
        entity_type="wrap_project",
        entity_id=project["id"],
        summary="Wrap Project approval-sensitive information changed",
        metadata={"previous_revision": current_revision, "approval_revision": new_revision, "reason": reason, "fields": sorted(set(changed_fields))},
    )
    return await _get_project(project["tenant_id"], project["id"])


async def search_targets(user: dict, *, search: str = "", target_type: Optional[str] = None) -> dict:
    _require_staff_perm(user, Perm.WRAP_LAB_READ)
    tenant_id = user["tenant_id"]
    term = (search or "").strip()
    pattern = {"$regex": term, "$options": "i"} if term else {"$exists": True}
    allowed = {target_type} if target_type else {"customer", "quote", "order", "order_item", "work_order"}
    results: list[dict[str, Any]] = []
    if "customer" in allowed:
        cursor = db.customers.find({"tenant_id": tenant_id, "$or": [{"name": pattern}, {"email": pattern}, {"phone": pattern}]}, {"_id": 0}).limit(10)
        async for customer in cursor:
            results.append({"type": "customer", "id": customer["id"], "label": customer.get("name") or customer.get("email") or customer["id"], "description": customer.get("email") or customer.get("phone") or "Customer"})
    if "quote" in allowed:
        cursor = db.quotes.find({"tenant_id": tenant_id, "$or": [{"title": pattern}, {"job_name": pattern}, {"description": pattern}]}, {"_id": 0}).limit(10)
        async for quote in cursor:
            customer = await db.customers.find_one({"tenant_id": tenant_id, "id": quote.get("customer_id")}, {"_id": 0, "name": 1})
            results.append({"type": "quote", "id": quote["id"], "label": quote.get("title") or quote.get("job_name") or f"Quote {quote.get('number', quote['id'])}", "description": f"{customer.get('name') if customer else 'Customer'} · {quote.get('status', 'quote')}", "customer_id": quote.get("customer_id")})
    if "order" in allowed:
        cursor = db.orders.find({"tenant_id": tenant_id, "$or": [{"job_name": pattern}, {"title": pattern}, {"description": pattern}]}, {"_id": 0}).limit(10)
        async for order in cursor:
            customer = await db.customers.find_one({"tenant_id": tenant_id, "id": order.get("customer_id")}, {"_id": 0, "name": 1})
            results.append({"type": "order", "id": order["id"], "label": order.get("title") or order.get("job_name") or f"Order O-{order.get('number')}", "description": f"{customer.get('name') if customer else 'Customer'} · {order.get('status', 'order')}", "customer_id": order.get("customer_id")})
    if "order_item" in allowed:
        cursor = db.order_items.find({"tenant_id": tenant_id, "$or": [{"description": pattern}, {"item_name": pattern}, {"category": pattern}, {"product_type": pattern}]}, {"_id": 0}).limit(20)
        async for item in cursor:
            if not _is_wrap_order_item(item):
                continue
            order = await db.orders.find_one({"tenant_id": tenant_id, "id": item.get("order_id")}, {"_id": 0, "number": 1, "customer_id": 1, "job_name": 1})
            results.append({"type": "order_item", "id": item["id"], "label": item.get("item_name") or item.get("description") or item["id"], "description": f"O-{order.get('number') if order else '?'} · {order.get('job_name') if order else 'Order'}", "order_id": item.get("order_id"), "customer_id": order.get("customer_id") if order else None})
    if "work_order" in allowed:
        cursor = db.work_orders.find({"tenant_id": tenant_id, "$or": [{"production_instructions": pattern}, {"internal_notes": pattern}]}, {"_id": 0}).limit(10)
        async for work_order in cursor:
            results.append({"type": "work_order", "id": work_order["id"], "label": f"W-{work_order.get('number')}", "description": work_order.get("production_status") or "Work Order", "order_id": work_order.get("order_id"), "customer_id": work_order.get("customer_id")})
    return {"items": results[:25], "total": len(results[:25])}


def _calculate_square_feet(panels: list[dict[str, Any]]) -> int:
    total_inches = 0.0
    for panel in panels:
        if panel.get("selected") is False:
            continue
        width = float(panel.get("width_inches") or 0)
        height = float(panel.get("height_inches") or 0)
        if width < 0 or height < 0:
            raise WrapLabError("invalid_panel_dimensions", "Panel dimensions must be non-negative", 400)
        total_inches += width * height
    return int(ceil(total_inches / 144.0)) if total_inches else 0


def _layer_preflight(layers: list[dict[str, Any]]) -> dict[str, Any]:
    warnings: list[str] = []
    original_assets: list[str] = []
    for layer in layers:
        layer_type = layer.get("type")
        source_file_id = layer.get("source_file_id")
        if layer_type == "logo_asset":
            if not source_file_id:
                warnings.append(f"logo layer {layer.get('id', 'unknown')} is missing source_file_id")
            else:
                original_assets.append(source_file_id)
            if layer.get("generated_by_ai"):
                warnings.append("logo assets cannot be regenerated by AI")
            if layer.get("font_substituted"):
                warnings.append("logo text/font substitution is not allowed")
        if layer.get("locked") is True and layer.get("editable") is True:
            warnings.append(f"locked layer {layer.get('id', 'unknown')} cannot be marked editable")
    return {"warnings": warnings, "passed": not warnings, "original_asset_file_ids": sorted(set(original_assets))}


def _layout_contract(packet_type: str) -> dict[str, Any]:
    return {
        "style": "clean_white_card_packet",
        "required_sections": [
            "strong_section_headers",
            "two_column_summary_blocks",
            "coverage_and_damage_tables",
            "vehicle_diagram_area",
            "checklist_hierarchy",
            "financial_summary",
            "proof_and_timeline_blocks",
            "completion_warranty_aftercare",
        ],
        "packet_type": packet_type,
    }


async def create_vehicle(user: dict, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WRAP_LAB_WRITE)
    await _assert_customer(user["tenant_id"], fields.get("customer_id"))
    vehicle = WrapVehicle(
        tenant_id=user["tenant_id"],
        customer_id=fields.get("customer_id"),
        year=_optional_text(fields.get("year"), limit=20),
        make=_clean_text(fields.get("make"), "make"),
        model=_clean_text(fields.get("model"), "model"),
        trim=_optional_text(fields.get("trim"), limit=80),
        body_style=_optional_text(fields.get("body_style"), limit=80),
        vin=_optional_text(fields.get("vin"), limit=40),
        license_plate=_optional_text(fields.get("license_plate"), limit=40),
        color=_optional_text(fields.get("color"), limit=60),
        unit_number=_optional_text(fields.get("unit_number"), limit=60),
        odometer=fields.get("odometer"),
        vehicle_type=fields.get("vehicle_type", "other"),
        template_key=_optional_text(fields.get("template_key"), limit=120),
        dimensions=fields.get("dimensions") or {},
        measured_wrap_areas=fields.get("measured_wrap_areas") or [],
        requested_coverage=_optional_text(fields.get("requested_coverage"), limit=500),
        existing_graphics=_optional_text(fields.get("existing_graphics"), limit=1000),
        removal_requirements=_optional_text(fields.get("removal_requirements"), limit=1000),
        installation_location=_optional_text(fields.get("installation_location"), limit=200),
        target_install_at=fields.get("target_install_at"),
        target_delivery_at=fields.get("target_delivery_at"),
        customer_instructions=_optional_text(fields.get("customer_instructions"), limit=2000),
        internal_notes=_optional_text(fields.get("internal_notes"), limit=2000),
        photo_file_ids=fields.get("photo_file_ids") or [],
        notes=_optional_text(fields.get("notes")),
    ).model_dump()
    await _validate_file_ids(user["tenant_id"], vehicle["photo_file_ids"])
    await db.wrap_vehicles.insert_one(prepare_for_mongo(vehicle))
    await record_activity_with_audit(
        tenant_id=user["tenant_id"],
        actor_user_id=user.get("id", "unknown"),
        actor_email=user.get("email", "unknown"),
        module="wrap_lab",
        action="wrap_lab.vehicle_created",
        entity_type="wrap_vehicle",
        entity_id=vehicle["id"],
        summary="Wrap Lab vehicle created",
        metadata={"customer_id": vehicle.get("customer_id")},
    )
    return serialize_doc(vehicle)  # type: ignore[return-value]


async def update_vehicle(user: dict, vehicle_id: str, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WRAP_LAB_WRITE)
    vehicle = await vehicles_repo.get(tenant_id=user["tenant_id"], entity_id=vehicle_id)
    if not vehicle:
        raise WrapLabError("vehicle_not_found", "Wrap Lab vehicle not found", 404)
    if fields.get("customer_id"):
        await _assert_customer(user["tenant_id"], fields.get("customer_id"))
    if "photo_file_ids" in fields:
        await _validate_file_ids(user["tenant_id"], fields.get("photo_file_ids") or [])
    updates: dict[str, Any] = {}
    text_fields = {
        "year": 20,
        "make": 80,
        "model": 80,
        "trim": 80,
        "body_style": 80,
        "vin": 40,
        "license_plate": 40,
        "color": 60,
        "unit_number": 60,
        "template_key": 120,
        "requested_coverage": 500,
        "existing_graphics": 1000,
        "removal_requirements": 1000,
        "installation_location": 200,
        "customer_instructions": 2000,
        "internal_notes": 2000,
        "notes": 2000,
    }
    required = {"make", "model"}
    for key, limit in text_fields.items():
        if key in fields:
            updates[key] = _clean_text(fields.get(key), key, limit=limit) if key in required else _optional_text(fields.get(key), limit=limit)
    for key in ["customer_id", "odometer", "vehicle_type", "dimensions", "measured_wrap_areas", "target_install_at", "target_delivery_at", "photo_file_ids"]:
        if key in fields:
            updates[key] = fields.get(key)
    updated = await vehicles_repo.update(tenant_id=user["tenant_id"], entity_id=vehicle_id, updates=updates)
    sensitive_fields = sorted(set(updates) & APPROVAL_SENSITIVE_VEHICLE_FIELDS)
    if sensitive_fields and updated:
        cursor = db.wrap_projects.find({"tenant_id": user["tenant_id"], "vehicle_id": vehicle_id, "status": {"$ne": "archived"}}, {"_id": 0})
        async for linked_project in cursor:
            merged_project = {**linked_project}
            await _bump_approval_revision(
                user,
                merged_project,
                reason="Vehicle identity changed after approval evidence",
                changed_fields=[f"vehicle.{field}" for field in sensitive_fields],
                vehicle=updated,
            )
    await record_activity_with_audit(
        tenant_id=user["tenant_id"],
        actor_user_id=user.get("id", "unknown"),
        actor_email=user.get("email", "unknown"),
        module="wrap_lab",
        action="wrap_lab.vehicle_updated",
        entity_type="wrap_vehicle",
        entity_id=vehicle_id,
        summary="Wrap Lab vehicle intake updated",
        metadata={"fields": sorted(updates)},
    )
    return updated or {}


async def list_vehicles(user: dict, *, customer_id: Optional[str] = None) -> dict:
    _require_staff_perm(user, Perm.WRAP_LAB_READ)
    filters = {"customer_id": customer_id} if customer_id else {}
    return await vehicles_repo.list(tenant_id=user["tenant_id"], filters=filters, sort=[("updated_at", -1)])


async def create_project(user: dict, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WRAP_LAB_WRITE)
    refs = await _validate_project_links(user["tenant_id"], fields)
    await _prevent_duplicate_project(user["tenant_id"], fields)
    status = fields.get("status") or ("vehicle_recorded" if fields.get("vehicle_id") else "lead_intake")
    project_model = WrapProject(
        tenant_id=user["tenant_id"],
        customer_id=fields["customer_id"],
        vehicle_id=fields.get("vehicle_id"),
        intake_id=fields.get("intake_id"),
        quote_id=fields.get("quote_id"),
        order_id=fields.get("order_id"),
        order_item_id=fields.get("order_item_id"),
        work_order_id=fields.get("work_order_id"),
        work_order_summary_id=fields.get("work_order_summary_id") or fields.get("work_order_id"),
        commercial_feature_key=fields.get("commercial_feature_key", "wrap_lab"),
        project_name=_clean_text(fields.get("project_name"), "project_name"),
        project_type=fields.get("project_type", "custom"),
        status=status,
        coverage_summary=_optional_text(fields.get("coverage_summary")),
        estimate_total_cents=_non_negative_cents(fields.get("estimate_total_cents"), "estimate_total_cents"),
        deposit_required_cents=_non_negative_cents(fields.get("deposit_required_cents"), "deposit_required_cents"),
        material_estimate_cents=_non_negative_cents(fields.get("material_estimate_cents"), "material_estimate_cents"),
        labor_estimate_cents=_non_negative_cents(fields.get("labor_estimate_cents"), "labor_estimate_cents"),
        assigned_user_ids=fields.get("assigned_user_ids") or [],
        due_at=fields.get("due_at"),
        specifications=fields.get("specifications") or {},
        notes=_optional_text(fields.get("notes")),
    )
    project = project_model.model_dump()
    project["approval_fingerprint"] = _approval_fingerprint(project, refs.get("vehicle"))
    await db.wrap_projects.insert_one(prepare_for_mongo(project))
    await _audit(
        tenant_id=user["tenant_id"],
        project_id=project["id"],
        user=user,
        action="wrap_lab.project_created",
        entity_type="wrap_project",
        entity_id=project["id"],
        summary="Wrap Lab project created",
    )
    return serialize_doc(project)  # type: ignore[return-value]


async def update_project(user: dict, project_id: str, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WRAP_LAB_WRITE)
    project = await _get_project(user["tenant_id"], project_id)
    await _ensure_open_project(project)
    merged = {**project, **fields}
    await _validate_project_links(user["tenant_id"], merged)
    await _prevent_duplicate_project(user["tenant_id"], merged, exclude_project_id=project_id)
    updates: dict[str, Any] = {}
    text_fields = {
        "project_name": 200,
        "coverage_summary": 2000,
        "notes": 2000,
    }
    for key, limit in text_fields.items():
        if key in fields:
            updates[key] = _clean_text(fields.get(key), key, limit=limit) if key == "project_name" else _optional_text(fields.get(key), limit=limit)
    for key in [
        "customer_id",
        "vehicle_id",
        "intake_id",
        "quote_id",
        "order_id",
        "order_item_id",
        "work_order_id",
        "work_order_summary_id",
        "project_type",
        "assigned_user_ids",
        "due_at",
        "specifications",
    ]:
        if key in fields:
            updates[key] = fields.get(key)
    if updates.get("work_order_id") and "work_order_summary_id" not in updates:
        updates["work_order_summary_id"] = updates["work_order_id"]
    updated = await projects_repo.update(tenant_id=user["tenant_id"], entity_id=project_id, updates=updates)
    if updated and (set(updates) & APPROVAL_SENSITIVE_PROJECT_FIELDS):
        updated = await _bump_approval_revision(
            user,
            updated,
            reason="Wrap specifications changed after approval evidence",
            changed_fields=sorted(set(updates) & APPROVAL_SENSITIVE_PROJECT_FIELDS),
            vehicle=await vehicles_repo.get(tenant_id=user["tenant_id"], entity_id=updated["vehicle_id"]) if updated.get("vehicle_id") else None,
        )
    await _audit(
        tenant_id=user["tenant_id"],
        project_id=project_id,
        user=user,
        action="wrap_lab.project_updated",
        entity_type="wrap_project",
        entity_id=project_id,
        summary="Wrap Lab project relationships/specifications updated",
        metadata={"fields": sorted(updates)},
    )
    return updated or {}


async def list_projects(user: dict, *, status: Optional[str] = None, customer_id: Optional[str] = None) -> dict:
    _require_staff_perm(user, Perm.WRAP_LAB_READ)
    filters: dict[str, Any] = {}
    if status:
        filters["status"] = status
    if customer_id:
        filters["customer_id"] = customer_id
    return await projects_repo.list(tenant_id=user["tenant_id"], filters=filters, sort=[("updated_at", -1)])


async def _linked_assets(tenant_id: str, project: dict[str, Any]) -> dict[str, Any]:
    filters = [{"parent_type": "wrap_project", "parent_id": project["id"]}, {"entity_type": "wrap_project", "entity_id": project["id"]}]
    for parent_type, key in [("customer", "customer_id"), ("quote", "quote_id"), ("order", "order_id"), ("order_item", "order_item_id"), ("work_order", "work_order_id")]:
        if project.get(key):
            filters.append({"parent_type": parent_type, "parent_id": project[key]})
            filters.append({"entity_type": parent_type, "entity_id": project[key]})
    attachments = [
        serialize_doc(att) async for att in db.attachments.find(
            {"tenant_id": tenant_id, "$or": [{"parent_type": f["parent_type"], "parent_id": f["parent_id"]} for f in filters if f.get("parent_type")]},
            {"_id": 0},
        )
    ] if any(f.get("parent_type") for f in filters) else []
    file_ids = [att.get("file_id") for att in attachments if att.get("file_id")]
    explicit_file_ids: list[str] = []
    for collection in ["wrap_vehicles", "wrap_inspections", "wrap_installation_records"]:
        cursor = db[collection].find({"tenant_id": tenant_id, "$or": [{"id": project.get("vehicle_id")}, {"project_id": project["id"]}]}, {"_id": 0})
        async for doc in cursor:
            for key in ["photo_file_ids", "before_photo_file_ids", "after_photo_file_ids", "completion_photo_file_ids"]:
                explicit_file_ids.extend(doc.get(key) or [])
    all_file_ids = sorted(set(file_ids + explicit_file_ids))
    files = [
        serialize_doc(file) async for file in db.files.find(
            {"tenant_id": tenant_id, "id": {"$in": all_file_ids}, "archived": {"$ne": True}},
            {"_id": 0},
        )
    ] if all_file_ids else []
    doc_links = [
        serialize_doc(link) async for link in db.document_links.find(
            {"tenant_id": tenant_id, "$or": [{"entity_type": f["entity_type"], "entity_id": f["entity_id"]} for f in filters if f.get("entity_type")]},
            {"_id": 0},
        )
    ] if any(f.get("entity_type") for f in filters) else []
    document_ids = [link.get("document_id") for link in doc_links if link.get("document_id")]
    documents = [
        serialize_doc(doc) async for doc in db.documents.find(
            {"tenant_id": tenant_id, "id": {"$in": document_ids}, "archived": {"$ne": True}},
            {"_id": 0},
        )
    ] if document_ids else []
    return {"attachments": attachments, "files": files, "document_links": doc_links, "documents": documents}


async def _approval_context(tenant_id: str, project: dict[str, Any]) -> dict[str, Any]:
    approval_filters = [{"parent_type": "wrap_project", "parent_id": project["id"]}]
    room_filters = [{"wrap_project_id": project["id"]}]
    proof_filters = [{"parent_type": "wrap_project", "parent_id": project["id"]}]
    for parent_type, key in [("quote", "quote_id"), ("order", "order_id"), ("order_item", "order_item_id"), ("work_order_summary", "work_order_summary_id")]:
        if project.get(key):
            approval_filters.append({"parent_type": parent_type, "parent_id": project[key]})
            proof_filters.append({"parent_type": parent_type, "parent_id": project[key]})
            if key in {"quote_id", "order_id"}:
                room_filters.append({key: project[key]})
    approvals = [
        serialize_doc(doc) async for doc in db.approvals.find({"tenant_id": tenant_id, "$or": approval_filters}, {"_id": 0}).sort("created_at", -1)
    ]
    project_revision = int(project.get("approval_revision") or 1)
    for approval in approvals:
        approval["wrap_project_current"] = _matches_current_wrap_revision(approval, project_revision)
    rooms = [
        serialize_doc(doc) async for doc in db.decision_rooms.find({"tenant_id": tenant_id, "$or": room_filters}, {"_id": 0}).sort("updated_at", -1)
    ]
    proofs = [
        serialize_doc(doc) async for doc in db.proofs.find({"tenant_id": tenant_id, "$or": proof_filters, "archived": {"$ne": True}}, {"_id": 0}).sort("created_at", -1)
    ]
    for proof in proofs:
        proof["wrap_project_current"] = _matches_current_wrap_revision(proof, project_revision) and not proof.get("wrap_project_stale")
    signature_requests = [
        serialize_doc(doc) async for doc in db.signature_requests.find({"tenant_id": tenant_id, "parent_type": "document", "parent_id": {"$regex": f"^wrap-inspection:{project['id']}:"}}, {"_id": 0}).sort("created_at", -1)
    ]
    return {"approvals": approvals, "decision_rooms": rooms, "proofs": proofs, "signature_requests": signature_requests}


def _wrap_readiness(
    project: dict[str, Any],
    inspections: list[dict[str, Any]],
    panel_plans: list[dict[str, Any]],
    approval_context: dict[str, Any],
) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if not project.get("vehicle_id"):
        blockers.append({"code": "missing_vehicle", "label": "Vehicle intake is not linked.", "required_action": "Link or create a vehicle record."})
    if not project.get("order_item_id"):
        warnings.append({"code": "missing_order_item", "label": "No wrap Order Item is linked.", "required_action": "Link the commercial wrap item before production handoff."})
    pre = _latest([i for i in inspections if i.get("inspection_type") == "pre_install" and i.get("status") != "superseded"])
    if not pre:
        blockers.append({"code": "missing_pre_install_inspection", "label": READINESS_REQUIREMENTS["inspection"], "required_action": "Complete pre-install inspection."})
    elif _completion_status(pre) == "missing_photos":
        blockers.append({"code": "inspection_photos_missing", "label": "Required inspection photos are missing.", "required_action": "Attach required exterior/detail photos."})
    if pre and pre.get("status") not in {"signed", "completed"}:
        blockers.append({"code": "inspection_not_acknowledged", "label": READINESS_REQUIREMENTS["signature"], "required_action": "Capture customer acknowledgment or in-person staff acknowledgment."})
    project_revision = int(project.get("approval_revision") or 1)
    active_proofs = [p for p in approval_context.get("proofs", []) if p.get("status") not in {"cancelled", "superseded", "archived"}]
    current_proofs = [p for p in active_proofs if p.get("wrap_project_current", _matches_current_wrap_revision(p, project_revision))]
    current_approvals = [
        a for a in approval_context.get("approvals", [])
        if a.get("action") == "approve"
        and a.get("status", "current") == "current"
        and a.get("wrap_project_current", _matches_current_wrap_revision(a, project_revision))
    ]
    stale_approvals = [
        a for a in approval_context.get("approvals", [])
        if a.get("action") == "approve" and not a.get("wrap_project_current", _matches_current_wrap_revision(a, project_revision))
    ]
    stale_proofs = [p for p in active_proofs if not p.get("wrap_project_current", _matches_current_wrap_revision(p, project_revision)) or p.get("wrap_project_stale")]
    approved = any(p.get("status") == "approved" for p in current_proofs) or bool(current_approvals)
    if not approved:
        blockers.append({"code": "proof_not_approved", "label": READINESS_REQUIREMENTS["proof"], "required_action": "Resolve current proof or Decision Room approval."})
    if (stale_approvals or stale_proofs) and not approved:
        blockers.append({
            "code": "approval_evidence_stale",
            "label": project.get("approval_revision_changed_reason") or "Approved artwork or specifications changed after approval.",
            "required_action": f"Create/open current approval work for Wrap Project revision {project_revision}.",
            "approval_revision": project_revision,
            "stale_approval_ids": [a.get("id") for a in stale_approvals if a.get("id")],
            "stale_proof_ids": [p.get("id") for p in stale_proofs if p.get("id")],
        })
    latest_plan = _latest(panel_plans)
    if not latest_plan or latest_plan.get("status") != "ready_for_production":
        blockers.append({"code": "panel_plan_not_ready", "label": READINESS_REQUIREMENTS["panel_plan"], "required_action": "Create a ready production panel plan."})
    return {"ready": not blockers, "blockers": blockers, "warnings": warnings, "evaluated_at": _now_iso()}


def _timeline(project: dict[str, Any], detail: dict[str, Any], approval_context: dict[str, Any]) -> list[dict[str, Any]]:
    events = [{"at": project.get("created_at"), "kind": "project", "label": "Wrap Project created", "entity_id": project.get("id")}]
    for key, label in [
        ("coverage_plans", "Coverage/specification updated"),
        ("inspections", "Inspection activity"),
        ("design_scenes", "Artwork/design scene updated"),
        ("panel_plans", "Panel plan updated"),
        ("schedules", "Installation schedule updated"),
        ("installation_records", "Installation/QC updated"),
        ("packets", "Packet generated"),
        ("warranties", "Warranty/aftercare updated"),
    ]:
        for item in detail.get(key) or []:
            events.append({"at": item.get("updated_at") or item.get("created_at"), "kind": key, "label": label, "entity_id": item.get("id"), "status": item.get("status")})
    for key, label in [("approvals", "Approval activity"), ("decision_rooms", "Decision Room activity"), ("proofs", "Proof activity"), ("signature_requests", "Signature activity")]:
        for item in approval_context.get(key) or []:
            events.append({"at": item.get("updated_at") or item.get("created_at"), "kind": key, "label": label, "entity_id": item.get("id"), "status": item.get("status") or item.get("action")})
    return sorted([event for event in events if event.get("at")], key=lambda e: str(e.get("at")), reverse=True)


async def get_project(user: dict, project_id: str) -> dict:
    _require_staff_perm(user, Perm.WRAP_LAB_READ)
    project = await _get_project(user["tenant_id"], project_id)
    tenant_id = user["tenant_id"]
    detail = {
        "project": project,
        "vehicle": await vehicles_repo.get(tenant_id=tenant_id, entity_id=project["vehicle_id"]) if project.get("vehicle_id") else None,
        "customer": await db.customers.find_one({"tenant_id": tenant_id, "id": project.get("customer_id")}, {"_id": 0}) if project.get("customer_id") else None,
        "quote": await db.quotes.find_one({"tenant_id": tenant_id, "id": project.get("quote_id")}, {"_id": 0}) if project.get("quote_id") else None,
        "order": await db.orders.find_one({"tenant_id": tenant_id, "id": project.get("order_id")}, {"_id": 0}) if project.get("order_id") else None,
        "order_item": await db.order_items.find_one({"tenant_id": tenant_id, "id": project.get("order_item_id")}, {"_id": 0}) if project.get("order_item_id") else None,
        "work_order": await db.work_orders.find_one({"tenant_id": tenant_id, "id": project.get("work_order_id") or project.get("work_order_summary_id")}, {"_id": 0}) if project.get("work_order_id") or project.get("work_order_summary_id") else None,
        "coverage_plans": (await coverage_repo.list(tenant_id=tenant_id, filters={"project_id": project_id}))["items"],
        "inspections": (await inspections_repo.list(tenant_id=tenant_id, filters={"project_id": project_id}))["items"],
        "design_scenes": (await designs_repo.list(tenant_id=tenant_id, filters={"project_id": project_id}))["items"],
        "panel_plans": (await panel_plans_repo.list(tenant_id=tenant_id, filters={"project_id": project_id}))["items"],
        "packets": (await packets_repo.list(tenant_id=tenant_id, filters={"project_id": project_id}))["items"],
        "schedules": (await schedules_repo.list(tenant_id=tenant_id, filters={"project_id": project_id}))["items"],
        "warranties": (await warranties_repo.list(tenant_id=tenant_id, filters={"project_id": project_id}))["items"],
        "installation_records": (await installations_repo.list(tenant_id=tenant_id, filters={"project_id": project_id}))["items"],
    }
    approval_context = await _approval_context(tenant_id, project)
    detail["linked_assets"] = await _linked_assets(tenant_id, project)
    detail.update(approval_context)
    detail["readiness"] = _wrap_readiness(project, detail["inspections"], detail["panel_plans"], approval_context)
    detail["timeline"] = _timeline(project, detail, approval_context)
    return detail


async def advance_project(user: dict, project_id: str, status: str, reason: Optional[str] = None) -> dict:
    _require_staff_perm(user, Perm.WRAP_LAB_ADVANCE)
    project = await _get_project(user["tenant_id"], project_id)
    if status not in PROJECT_STATUS_ORDER:
        raise WrapLabError("invalid_status", "Unsupported Wrap Lab project status", 400)
    if project.get("status") == "archived":
        raise WrapLabError("project_archived", "Archived Wrap Lab projects cannot advance", 409)
    current = PROJECT_STATUS_ORDER.index(project["status"])
    target = PROJECT_STATUS_ORDER.index(status)
    if target < current:
        raise WrapLabError("invalid_transition", "Wrap Lab projects cannot move backward", 409)
    if target > current + 1 and status != "archived":
        raise WrapLabError("invalid_transition", "Wrap Lab projects advance one status at a time", 409)
    updates: dict[str, Any] = {"status": status}
    if status == "completed":
        updates["completed_at"] = _now_iso()
    if status == "archived":
        updates["archived_at"] = _now_iso()
    updated = await projects_repo.update(tenant_id=user["tenant_id"], entity_id=project_id, updates=updates)
    await _audit(
        tenant_id=user["tenant_id"],
        project_id=project_id,
        user=user,
        action="wrap_lab.project_status_changed",
        entity_type="wrap_project",
        entity_id=project_id,
        summary=f"Wrap Lab project status changed from {project['status']} to {status}",
        metadata={"from": project["status"], "to": status, "reason": reason},
    )
    return updated or {}


async def create_coverage_plan(user: dict, project_id: str, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WRAP_LAB_WRITE)
    project = await _get_project(user["tenant_id"], project_id)
    await _ensure_open_project(project)
    panels = fields.get("panels") or []
    plan = WrapCoveragePlan(
        tenant_id=user["tenant_id"],
        project_id=project_id,
        coverage_level=fields.get("coverage_level", project.get("project_type", "custom")),
        panels=panels,
        total_square_feet=int(fields.get("total_square_feet") or _calculate_square_feet(panels)),
        waste_percent=int(fields.get("waste_percent", 15)),
        status=fields.get("status", "draft"),
        notes=_optional_text(fields.get("notes")),
    ).model_dump()
    await db.wrap_coverage_plans.insert_one(prepare_for_mongo(plan))
    await _bump_approval_revision(
        user,
        project,
        reason="Wrap coverage or included panels changed after approval evidence",
        changed_fields=["coverage_plan", "coverage_plan.panels", "coverage_plan.coverage_level"],
        vehicle=await vehicles_repo.get(tenant_id=user["tenant_id"], entity_id=project["vehicle_id"]) if project.get("vehicle_id") else None,
        force=True,
    )
    await _audit(tenant_id=user["tenant_id"], project_id=project_id, user=user, action="wrap_lab.coverage_plan_created", entity_type="wrap_coverage_plan", entity_id=plan["id"], summary="Wrap Lab coverage plan created")
    return serialize_doc(plan)  # type: ignore[return-value]


async def create_inspection(user: dict, project_id: str, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WRAP_LAB_WRITE)
    project = await _get_project(user["tenant_id"], project_id)
    await _ensure_open_project(project)
    await _validate_file_ids(user["tenant_id"], (fields.get("before_photo_file_ids") or []) + (fields.get("after_photo_file_ids") or []))
    existing_count = await db.wrap_inspections.count_documents({"tenant_id": user["tenant_id"], "project_id": project_id, "inspection_type": fields["inspection_type"]})
    inspection = WrapInspection(
        tenant_id=user["tenant_id"],
        project_id=project_id,
        inspection_type=fields["inspection_type"],
        version=existing_count + 1,
        status=fields.get("status", "draft"),
        inspector_user_id=fields.get("inspector_user_id") or user.get("id"),
        required_views=fields.get("required_views") or [],
        damage_items=fields.get("damage_items") or [],
        surface_conditions=fields.get("surface_conditions") or [],
        acknowledgements=fields.get("acknowledgements") or [],
        diagram_marks=fields.get("diagram_marks") or [],
        before_photo_file_ids=fields.get("before_photo_file_ids") or [],
        after_photo_file_ids=fields.get("after_photo_file_ids") or [],
        signature_request_id=fields.get("signature_request_id"),
        signature_id=fields.get("signature_id"),
        signed_at=fields.get("signed_at"),
        notes=_optional_text(fields.get("notes")),
    ).model_dump()
    await db.wrap_inspections.insert_one(prepare_for_mongo(inspection))
    await _audit(tenant_id=user["tenant_id"], project_id=project_id, user=user, action="wrap_lab.inspection_created", entity_type="wrap_inspection", entity_id=inspection["id"], summary="Wrap Lab inspection created")
    return serialize_doc(inspection)  # type: ignore[return-value]


async def update_inspection(user: dict, inspection_id: str, fields: dict[str, Any], *, create_addendum: bool = False) -> dict:
    _require_staff_perm(user, Perm.WRAP_LAB_WRITE)
    inspection = await inspections_repo.get(tenant_id=user["tenant_id"], entity_id=inspection_id)
    if not inspection:
        raise WrapLabError("inspection_not_found", "Wrap Lab inspection not found", 404)
    project = await _get_project(user["tenant_id"], inspection["project_id"])
    await _ensure_open_project(project)
    locked = inspection.get("status") in {"signed", "completed"} or inspection.get("locked_at")
    if locked and not create_addendum:
        raise WrapLabError("inspection_locked", "Signed inspections are immutable; create an addendum instead.", 409)
    file_ids: list[str] = []
    for key in ["before_photo_file_ids", "after_photo_file_ids"]:
        if key in fields:
            file_ids.extend(fields.get(key) or [])
    await _validate_file_ids(user["tenant_id"], file_ids)
    allowed = {
        "status",
        "inspector_user_id",
        "required_views",
        "damage_items",
        "surface_conditions",
        "acknowledgements",
        "diagram_marks",
        "before_photo_file_ids",
        "after_photo_file_ids",
        "signature_request_id",
        "signature_id",
        "signed_at",
        "notes",
    }
    updates = {key: fields[key] for key in allowed if key in fields}
    if "notes" in updates:
        updates["notes"] = _optional_text(updates["notes"])
    if updates.get("status") in {"completed", "signed"}:
        updates["completed_at"] = updates.get("completed_at") or _now_iso()
        updates["locked_at"] = updates.get("locked_at") or _now_iso()
    if create_addendum:
        await _supersede_inspection_review_links(user, inspection, reason="Signed inspection addendum created")
        await inspections_repo.update(tenant_id=user["tenant_id"], entity_id=inspection_id, updates={"status": "superseded"})
        addendum = WrapInspection(
            tenant_id=user["tenant_id"],
            project_id=inspection["project_id"],
            inspection_type=inspection["inspection_type"],
            version=int(inspection.get("version") or 1) + 1,
            previous_inspection_id=inspection_id,
            status=updates.get("status", "draft"),
            inspector_user_id=updates.get("inspector_user_id") or user.get("id"),
            required_views=updates.get("required_views", inspection.get("required_views") or []),
            damage_items=updates.get("damage_items", inspection.get("damage_items") or []),
            surface_conditions=updates.get("surface_conditions", inspection.get("surface_conditions") or []),
            acknowledgements=updates.get("acknowledgements", inspection.get("acknowledgements") or []),
            diagram_marks=updates.get("diagram_marks", inspection.get("diagram_marks") or []),
            before_photo_file_ids=updates.get("before_photo_file_ids", inspection.get("before_photo_file_ids") or []),
            after_photo_file_ids=updates.get("after_photo_file_ids", inspection.get("after_photo_file_ids") or []),
            notes=_optional_text(updates.get("notes")),
        ).model_dump()
        await db.wrap_inspections.insert_one(prepare_for_mongo(addendum))
        await _audit(tenant_id=user["tenant_id"], project_id=inspection["project_id"], user=user, action="wrap_lab.inspection_addendum_created", entity_type="wrap_inspection", entity_id=addendum["id"], summary="Wrap Lab inspection addendum created", metadata={"previous_inspection_id": inspection_id})
        return serialize_doc(addendum)  # type: ignore[return-value]
    customer_visible_fields = {"status", "required_views", "damage_items", "surface_conditions", "diagram_marks", "before_photo_file_ids", "after_photo_file_ids"}
    if set(updates) & customer_visible_fields:
        await _supersede_inspection_review_links(user, inspection, reason="Inspection review content changed after link issue")
    updated = await inspections_repo.update(tenant_id=user["tenant_id"], entity_id=inspection_id, updates=updates)
    await _audit(tenant_id=user["tenant_id"], project_id=inspection["project_id"], user=user, action="wrap_lab.inspection_updated", entity_type="wrap_inspection", entity_id=inspection_id, summary="Wrap Lab inspection updated", metadata={"fields": sorted(updates)})
    return updated or {}


async def acknowledge_inspection(user: dict, inspection_id: str, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WRAP_LAB_WRITE)
    inspection = await inspections_repo.get(tenant_id=user["tenant_id"], entity_id=inspection_id)
    if not inspection:
        raise WrapLabError("inspection_not_found", "Wrap Lab inspection not found", 404)
    if inspection.get("status") in {"signed", "completed"} or inspection.get("locked_at"):
        raise WrapLabError("inspection_locked", "Inspection is already signed and immutable", 409)
    project = await _get_project(user["tenant_id"], inspection["project_id"])
    signer_email = (fields.get("signer_email") or user.get("email") or "in-person@example.invalid").lower()
    signer_name = _clean_text(fields.get("signer_name"), "signer_name", limit=160)
    parent_id = f"wrap-inspection:{project['id']}:{inspection_id}"
    request = await create_signature_request(
        tenant_id=user["tenant_id"],
        parent_type="document",
        parent_id=parent_id,
        parent_version=int(inspection.get("version") or 1),
        title=f"Wrap inspection acknowledgment - {project.get('project_name')}",
        description="Customer-safe Wrap Lab inspection condition acknowledgment.",
        required_signers=[{"name": signer_name, "email": signer_email, "role": "customer"}],
        created_by=user.get("id"),
        actor_email=user.get("email"),
    )
    signature = await record_signature(
        tenant_id=user["tenant_id"],
        request_id=request["id"],
        signer_email=signer_email,
        signer_name=signer_name,
        signature_type=fields.get("signature_type") or "typed",
        typed_text=fields.get("signature_data") if fields.get("signature_type", "typed") == "typed" else None,
        signature_data_ref=fields.get("signature_data") if fields.get("signature_type") == "drawn" else None,
    )
    updates = {
        "status": "signed",
        "signature_request_id": request["id"],
        "signature_id": signature["id"],
        "signed_at": _now_iso(),
        "locked_at": _now_iso(),
        "acknowledgements": [
            *(inspection.get("acknowledgements") or []),
            {"signer_name": signer_name, "signer_email": signer_email, "signature_id": signature["id"], "signed_at": _now_iso(), "version": inspection.get("version") or 1},
        ],
    }
    await _supersede_inspection_review_links(user, inspection, reason="Inspection was acknowledged in person")
    updated = await inspections_repo.update(tenant_id=user["tenant_id"], entity_id=inspection_id, updates=updates)
    await _audit(tenant_id=user["tenant_id"], project_id=inspection["project_id"], user=user, action="wrap_lab.inspection_acknowledged", entity_type="wrap_inspection", entity_id=inspection_id, summary="Wrap Lab inspection acknowledged and signed", metadata={"signature_request_id": request["id"], "signature_id": signature["id"]})
    return {"inspection": updated, "signature_request": request, "signature": signature}


def _public_token_status(token: dict[str, Any]) -> str:
    if token.get("revoked") or token.get("status") == "revoked":
        return "revoked"
    if token.get("status") == "superseded":
        return "superseded"
    if token.get("status") == "completed" or token.get("completed_at"):
        return "completed"
    expires = _parse_dt(token.get("expires_at"))
    if expires and expires <= utc_now():
        return "expired"
    if token.get("first_viewed_at"):
        return "viewed"
    return token.get("status") or "active"


def _safe_inspection_payload(project: dict[str, Any], vehicle: Optional[dict[str, Any]], inspection: dict[str, Any], token: dict[str, Any]) -> dict[str, Any]:
    snapshot = token.get("review_snapshot") if isinstance(token.get("review_snapshot"), dict) else None
    if snapshot:
        base = {
            "project": snapshot.get("project") or {},
            "vehicle": snapshot.get("vehicle") or {},
            "inspection": snapshot.get("inspection") or {},
        }
    else:
        safe_vehicle = {}
        if vehicle:
            for key in ["year", "make", "model", "trim", "body_style", "color", "unit_number", "vehicle_type", "requested_coverage"]:
                if vehicle.get(key) is not None:
                    safe_vehicle[key] = vehicle.get(key)
        base = {
            "project": {
                "id": project["id"],
                "project_name": project.get("project_name"),
                "project_type": project.get("project_type"),
                "coverage_summary": project.get("coverage_summary"),
            },
            "vehicle": safe_vehicle,
            "inspection": {
                "id": inspection["id"],
                "inspection_type": inspection.get("inspection_type"),
                "version": int(inspection.get("version") or 1),
                "status": inspection.get("status"),
                "required_views": inspection.get("required_views") or [],
                "damage_items": inspection.get("damage_items") or [],
                "surface_conditions": inspection.get("surface_conditions") or [],
                "diagram_marks": inspection.get("diagram_marks") or [],
                "before_photo_file_ids": inspection.get("before_photo_file_ids") or [],
                "after_photo_file_ids": inspection.get("after_photo_file_ids") or [],
                "signed_at": inspection.get("signed_at"),
                "acknowledgements": inspection.get("acknowledgements") or [],
            },
        }
    base["token"] = {
        "id": token["id"],
        "status": _public_token_status(token),
        "parent_version": token.get("parent_version"),
        "expires_at": serialize_doc({"v": token.get("expires_at")}).get("v"),
        "first_viewed_at": token.get("first_viewed_at"),
        "last_viewed_at": token.get("last_viewed_at"),
        "completed_at": token.get("completed_at"),
        "revoked_at": token.get("revoked_at"),
        "superseded_at": token.get("superseded_at"),
        "delivery_history": token.get("delivery_history") or [],
    }
    return base


async def create_inspection_review_link(
    user: dict,
    inspection_id: str,
    fields: dict[str, Any],
    *,
    ip_issued: Optional[str] = None,
) -> dict[str, Any]:
    _require_staff_perm(user, Perm.WRAP_LAB_WRITE)
    inspection = await inspections_repo.get(tenant_id=user["tenant_id"], entity_id=inspection_id)
    if not inspection:
        raise WrapLabError("inspection_not_found", "Wrap Lab inspection not found", 404)
    if inspection.get("status") == "superseded":
        raise WrapLabError("inspection_superseded", "Create a link for the current inspection version.", 409)
    project = await _get_project(user["tenant_id"], inspection["project_id"])
    ttl_hours = int(fields.get("ttl_hours") or 168)
    if ttl_hours <= 0 or ttl_hours > 24 * 90:
        raise WrapLabError("invalid_token_ttl", "Inspection review links must expire within 90 days.", 400)
    audience_email = (fields.get("audience_email") or "").strip().lower() or None
    raw, token_doc = await mint_public_action_token(
        tenant_id=user["tenant_id"],
        action="wrap_inspection_review",
        parent_type="wrap_inspection",
        parent_id=inspection_id,
        parent_version=int(inspection.get("version") or 1),
        audience_email=audience_email,
        ttl_hours=ttl_hours,
        single_use=False,
        issued_by=user.get("id"),
        ip_issued=ip_issued,
    )
    now = _now_iso()
    delivery_entry = {
        "status": "manual_link_ready",
        "channel": fields.get("delivery_channel") or "manual",
        "message": "Email/SMS delivery is not configured for Wrap inspection links; copy the link manually.",
        "created_at": now,
        "created_by": user.get("id"),
        "note": _optional_text(fields.get("note"), limit=500),
    }
    vehicle = await vehicles_repo.get(tenant_id=user["tenant_id"], entity_id=project["vehicle_id"]) if project.get("vehicle_id") else None
    review_snapshot = {
        key: value for key, value in _safe_inspection_payload(
            project,
            vehicle,
            inspection,
            {**token_doc, "id": token_doc["id"], "status": "active", "delivery_history": [delivery_entry]},
        ).items()
        if key in {"project", "vehicle", "inspection"}
    }
    await db.public_action_tokens.update_one(
        {"tenant_id": user["tenant_id"], "id": token_doc["id"]},
        {"$set": {
            "status": "active",
            "project_id": project["id"],
            "inspection_id": inspection_id,
            "inspection_version": int(inspection.get("version") or 1),
            "review_snapshot": review_snapshot,
            "delivery_history": [delivery_entry],
            "updated_at": now,
        }},
    )
    await _audit(
        tenant_id=user["tenant_id"],
        project_id=project["id"],
        user=user,
        action="wrap_lab.inspection_link_created",
        entity_type="public_action_token",
        entity_id=token_doc["id"],
        summary="Wrap inspection review link created",
        metadata={"inspection_id": inspection_id, "inspection_version": int(inspection.get("version") or 1), "delivery_status": "manual_link_ready"},
    )
    record = await db.public_action_tokens.find_one({"tenant_id": user["tenant_id"], "id": token_doc["id"]}, {"_id": 0, "token_hash": 0})
    return {
        "token": raw,
        "record": serialize_doc(record),
        "public_url_path": f"/p/wrap-inspections/{inspection_id}?t={raw}",
        "delivery_status": "manual_link_ready",
        "delivery_error": "Email/SMS delivery is not configured for Wrap inspection links; copy the link manually.",
    }


async def list_inspection_review_links(user: dict, inspection_id: str) -> dict[str, Any]:
    _require_staff_perm(user, Perm.WRAP_LAB_READ)
    inspection = await inspections_repo.get(tenant_id=user["tenant_id"], entity_id=inspection_id)
    if not inspection:
        raise WrapLabError("inspection_not_found", "Wrap Lab inspection not found", 404)
    cursor = db.public_action_tokens.find(
        {"tenant_id": user["tenant_id"], "action": "wrap_inspection_review", "parent_type": "wrap_inspection", "parent_id": inspection_id},
        {"_id": 0, "token_hash": 0},
    ).sort("created_at", -1)
    items = []
    async for token in cursor:
        item = serialize_doc(token)
        item["computed_status"] = _public_token_status(token)
        items.append(item)
    return {"items": items}


async def update_inspection_review_link(user: dict, token_id: str, *, mode: str) -> bool:
    _require_staff_perm(user, Perm.WRAP_LAB_WRITE)
    token = await db.public_action_tokens.find_one(
        {"tenant_id": user["tenant_id"], "id": token_id, "action": "wrap_inspection_review", "parent_type": "wrap_inspection"},
        {"_id": 0},
    )
    if not token:
        raise WrapLabError("inspection_link_not_found", "Wrap inspection link not found", 404)
    inspection = await inspections_repo.get(tenant_id=user["tenant_id"], entity_id=token["parent_id"])
    project_id = token.get("project_id") or (inspection or {}).get("project_id")
    now = _now_iso()
    if mode == "expire":
        updates = {"expires_at": now, "expired_at": now, "status": "expired", "updated_at": now}
        action = "wrap_lab.inspection_link_expired"
        summary = "Wrap inspection review link expired"
    elif mode == "revoke":
        updates = {"revoked": True, "revoked_at": now, "status": "revoked", "updated_at": now}
        action = "wrap_lab.inspection_link_revoked"
        summary = "Wrap inspection review link revoked"
    else:
        raise WrapLabError("invalid_link_action", "Unsupported inspection link action", 400)
    await db.public_action_tokens.update_one({"tenant_id": user["tenant_id"], "id": token_id}, {"$set": updates})
    if project_id:
        await _audit(tenant_id=user["tenant_id"], project_id=project_id, user=user, action=action, entity_type="public_action_token", entity_id=token_id, summary=summary, metadata={"inspection_id": token.get("parent_id")})
    return True


async def _supersede_inspection_review_links(user: dict, inspection: dict[str, Any], *, reason: str) -> None:
    now = _now_iso()
    result = await db.public_action_tokens.update_many(
        {
            "tenant_id": user["tenant_id"],
            "action": "wrap_inspection_review",
            "parent_type": "wrap_inspection",
            "parent_id": inspection["id"],
            "parent_version": int(inspection.get("version") or 1),
            "status": {"$nin": ["completed", "revoked", "expired", "superseded"]},
        },
        {"$set": {"status": "superseded", "superseded_at": now, "superseded_reason": reason, "updated_at": now}},
    )
    if result.modified_count:
        await _audit(
            tenant_id=user["tenant_id"],
            project_id=inspection["project_id"],
            user=user,
            action="wrap_lab.inspection_links_superseded",
            entity_type="wrap_inspection",
            entity_id=inspection["id"],
            summary="Open Wrap inspection review links superseded by a new inspection version",
            metadata={"inspection_version": int(inspection.get("version") or 1), "count": result.modified_count},
        )


async def _resolve_public_inspection_review_token(raw_token: str, inspection_id: str, *, for_signature: bool = False) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    token = await db.public_action_tokens.find_one({"token_hash": hash_token(raw_token), "action": "wrap_inspection_review", "parent_type": "wrap_inspection"}, {"_id": 0})
    if not token or token.get("parent_id") != inspection_id:
        raise WrapLabError("inspection_link_not_found", "Wrap inspection link is invalid.", 404)
    status = _public_token_status(token)
    if status in {"revoked", "expired", "superseded"}:
        if status == "expired" and token.get("status") != "expired":
            await db.public_action_tokens.update_one({"id": token["id"]}, {"$set": {"status": "expired", "expired_at": _now_iso(), "updated_at": _now_iso()}})
        code = "inspection_link_" + status
        raise WrapLabError(code, f"Wrap inspection link is {status}.", 410)
    inspection = await inspections_repo.get(tenant_id=token["tenant_id"], entity_id=inspection_id)
    if not inspection:
        raise WrapLabError("inspection_not_found", "Wrap inspection not found", 404)
    if status != "completed" and (int(token.get("parent_version") or 0) != int(inspection.get("version") or 1) or inspection.get("status") == "superseded"):
        await db.public_action_tokens.update_one({"id": token["id"]}, {"$set": {"status": "superseded", "superseded_at": _now_iso(), "updated_at": _now_iso()}})
        raise WrapLabError("inspection_link_superseded", "This inspection link was superseded by a newer inspection version.", 410)
    if for_signature and status == "completed":
        raise WrapLabError("inspection_link_completed", "This inspection link has already been completed.", 409)
    project = await _get_project(token["tenant_id"], inspection["project_id"])
    return token, inspection, project


async def public_view_inspection_review(raw_token: str, inspection_id: str, *, ip: Optional[str] = None, user_agent: Optional[str] = None) -> dict[str, Any]:
    token, inspection, project = await _resolve_public_inspection_review_token(raw_token, inspection_id)
    now = _now_iso()
    updates: dict[str, Any] = {"last_viewed_at": now, "updated_at": now}
    if not token.get("first_viewed_at"):
        updates["first_viewed_at"] = now
    if token.get("status") == "active" or not token.get("status"):
        updates["status"] = "viewed"
    await db.public_action_tokens.update_one({"id": token["id"]}, {"$set": updates})
    token = {**token, **updates}
    await _audit_public(
        tenant_id=token["tenant_id"],
        project_id=project["id"],
        action="wrap_lab.inspection_link_viewed",
        entity_type="wrap_inspection",
        entity_id=inspection_id,
        summary="Customer viewed Wrap inspection review",
        metadata={"token_id": token["id"], "ip": ip, "user_agent": user_agent, "inspection_version": inspection.get("version")},
        actor_email=token.get("audience_email") or "public@wrap-inspection",
    )
    vehicle = await vehicles_repo.get(tenant_id=token["tenant_id"], entity_id=project["vehicle_id"]) if project.get("vehicle_id") else None
    return _safe_inspection_payload(project, vehicle, inspection, token)


async def public_sign_inspection_review(raw_token: str, inspection_id: str, fields: dict[str, Any], *, ip: Optional[str] = None, user_agent: Optional[str] = None) -> dict[str, Any]:
    token, inspection, project = await _resolve_public_inspection_review_token(raw_token, inspection_id, for_signature=True)
    if inspection.get("status") in {"signed", "completed"} or inspection.get("locked_at"):
        raise WrapLabError("inspection_locked", "This inspection version has already been signed.", 409)
    signer_name = _clean_text(fields.get("signer_name"), "signer_name", limit=160)
    signer_email = (fields.get("signer_email") or token.get("audience_email") or "").strip().lower()
    if not signer_email:
        raise WrapLabError("signer_email_required", "signer_email is required", 400)
    signature_text = _clean_text(fields.get("signature_data") or fields.get("typed_text"), "signature_data", limit=500)
    request = await create_signature_request(
        tenant_id=token["tenant_id"],
        parent_type="document",
        parent_id=_signature_parent_id(project["id"], inspection_id),
        parent_version=int(inspection.get("version") or 1),
        title=f"Wrap inspection acknowledgment - {project.get('project_name')}",
        description="Customer-safe Wrap Lab inspection condition acknowledgment.",
        required_signers=[{"name": signer_name, "email": signer_email, "role": "customer"}],
        created_by=f"public_token:{token['id']}",
        actor_email=signer_email,
    )
    signature = await record_signature(
        tenant_id=token["tenant_id"],
        request_id=request["id"],
        signer_email=signer_email,
        signer_name=signer_name,
        signature_type=fields.get("signature_type") or "typed",
        typed_text=signature_text if fields.get("signature_type", "typed") == "typed" else None,
        signature_data_ref=signature_text if fields.get("signature_type") == "drawn" else None,
        token_id=token["id"],
        ip=ip,
        user_agent=user_agent,
    )
    now = _now_iso()
    acknowledgement = {
        "signer_name": signer_name,
        "signer_email": signer_email,
        "signature_id": signature["id"],
        "signed_at": now,
        "version": int(inspection.get("version") or 1),
        "public_token_id": token["id"],
    }
    updated = await inspections_repo.update(
        tenant_id=token["tenant_id"],
        entity_id=inspection_id,
        updates={
            "status": "signed",
            "signature_request_id": request["id"],
            "signature_id": signature["id"],
            "signed_at": now,
            "locked_at": now,
            "acknowledgements": [*(inspection.get("acknowledgements") or []), acknowledgement],
        },
    )
    review_snapshot = deepcopy(token.get("review_snapshot") or {})
    if isinstance(review_snapshot.get("inspection"), dict):
        review_snapshot["inspection"] = {
            **review_snapshot["inspection"],
            "status": "signed",
            "signed_at": now,
            "acknowledgements": [*(review_snapshot["inspection"].get("acknowledgements") or []), acknowledgement],
        }
    await db.public_action_tokens.update_one(
        {"id": token["id"]},
        {"$set": {"status": "completed", "completed_at": now, "customer_acknowledgement": acknowledgement, "signature_id": signature["id"], "signature_request_id": request["id"], "review_snapshot": review_snapshot, "updated_at": now}},
    )
    await _audit_public(
        tenant_id=token["tenant_id"],
        project_id=project["id"],
        action="wrap_lab.inspection_link_signed",
        entity_type="wrap_inspection",
        entity_id=inspection_id,
        summary="Customer signed Wrap inspection review",
        metadata={"token_id": token["id"], "signature_id": signature["id"], "signature_request_id": request["id"], "inspection_version": inspection.get("version"), "ip": ip, "user_agent": user_agent},
        actor_email=signer_email,
    )
    vehicle = await vehicles_repo.get(tenant_id=token["tenant_id"], entity_id=project["vehicle_id"]) if project.get("vehicle_id") else None
    latest_token = await db.public_action_tokens.find_one({"id": token["id"]}, {"_id": 0, "token_hash": 0})
    return {**_safe_inspection_payload(project, vehicle, updated or inspection, latest_token or token), "signature": signature, "signature_request": request}


async def create_design_scene(user: dict, project_id: str, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WRAP_LAB_WRITE)
    project = await _get_project(user["tenant_id"], project_id)
    await _ensure_open_project(project)
    existing_count = await db.wrap_design_scenes.count_documents({"tenant_id": user["tenant_id"], "project_id": project_id})
    layers = fields.get("layers") or []
    preflight = _layer_preflight(layers)
    scene = WrapDesignScene(
        tenant_id=user["tenant_id"],
        project_id=project_id,
        revision=existing_count + 1,
        status=fields.get("status", "draft"),
        vehicle_template_key=fields.get("vehicle_template_key"),
        artboard=fields.get("artboard") or {},
        scale=fields.get("scale") or {},
        layers=layers,
        groups=fields.get("groups") or [],
        original_asset_file_ids=preflight["original_asset_file_ids"],
        preflight_results=preflight,
        notes=_optional_text(fields.get("notes")),
    ).model_dump()
    await db.wrap_design_scenes.insert_one(prepare_for_mongo(scene))
    await _bump_approval_revision(
        user,
        project,
        reason="Approved artwork or design scene changed after approval evidence",
        changed_fields=["design_scene", "artwork"],
        vehicle=await vehicles_repo.get(tenant_id=user["tenant_id"], entity_id=project["vehicle_id"]) if project.get("vehicle_id") else None,
        force=True,
    )
    await _audit(tenant_id=user["tenant_id"], project_id=project_id, user=user, action="wrap_lab.design_scene_created", entity_type="wrap_design_scene", entity_id=scene["id"], summary="Wrap Lab vector design scene created", metadata={"revision": scene["revision"]})
    return serialize_doc(scene)  # type: ignore[return-value]


async def update_design_layer(user: dict, scene_id: str, layer_id: str, updates: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WRAP_LAB_WRITE)
    scene = await designs_repo.get(tenant_id=user["tenant_id"], entity_id=scene_id)
    if not scene:
        raise WrapLabError("design_scene_not_found", "Wrap Lab design scene not found", 404)
    project = await _get_project(user["tenant_id"], scene["project_id"])
    await _ensure_open_project(project)
    layers = list(scene.get("layers") or [])
    changed = False
    for layer in layers:
        if layer.get("id") == layer_id:
            if layer.get("locked") and not updates.get("locked") is False:
                raise WrapLabError("layer_locked", "Locked Wrap Lab layers cannot be edited until unlocked", 409)
            if layer.get("type") == "logo_asset":
                forbidden = {"source_file_id", "asset_url", "original_format", "text", "font_family"} & set(updates)
                if forbidden:
                    raise WrapLabError("logo_asset_immutable", "Original logo asset identity cannot be redrawn or substituted", 409)
            layer.update(updates)
            changed = True
            break
    if not changed:
        raise WrapLabError("layer_not_found", "Wrap Lab design layer not found", 404)
    preflight = _layer_preflight(layers)
    updated = await designs_repo.update(
        tenant_id=user["tenant_id"],
        entity_id=scene_id,
        updates={"layers": layers, "preflight_results": preflight, "original_asset_file_ids": preflight["original_asset_file_ids"]},
    )
    await _bump_approval_revision(
        user,
        project,
        reason="Approved artwork layer changed after approval evidence",
        changed_fields=["design_layer", layer_id],
        vehicle=await vehicles_repo.get(tenant_id=user["tenant_id"], entity_id=project["vehicle_id"]) if project.get("vehicle_id") else None,
        force=True,
    )
    await _audit(tenant_id=user["tenant_id"], project_id=scene["project_id"], user=user, action="wrap_lab.design_layer_updated", entity_type="wrap_design_scene", entity_id=scene_id, summary="Wrap Lab vector design layer updated", metadata={"layer_id": layer_id})
    return updated or {}


async def create_panel_plan(user: dict, project_id: str, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WRAP_LAB_WRITE)
    project = await _get_project(user["tenant_id"], project_id)
    await _ensure_open_project(project)
    existing_count = await db.wrap_panel_plans.count_documents({"tenant_id": user["tenant_id"], "project_id": project_id})
    panels = fields.get("panels") or []
    usage_sqft = int(fields.get("material_usage_square_feet") or _calculate_square_feet(panels))
    printer_width = int(fields.get("printer_max_width_inches", 54))
    export_panels = []
    for idx, panel in enumerate(panels, start=1):
        width = float(panel.get("width_inches") or 0)
        splits = max(1, ceil(width / printer_width)) if printer_width > 0 else 1
        for split in range(1, splits + 1):
            export_panels.append({"label": f"Panel {idx}{chr(64 + split)}", "source_panel": panel.get("name", f"Panel {idx}"), "split": split, "scale": "true_size"})
    plan = WrapPanelPlan(
        tenant_id=user["tenant_id"],
        project_id=project_id,
        revision=existing_count + 1,
        status=fields.get("status", "draft"),
        printer_max_width_inches=printer_width,
        overlap_inches=float(fields.get("overlap_inches", 0.5)),
        bleed_inches=float(fields.get("bleed_inches", 0.5)),
        panels=panels,
        export_manifest={"formats": fields.get("export_formats") or ["layered_pdf", "paneled_pdf"], "panels": export_panels, "scale": "true_size"},
        material_usage_square_feet=usage_sqft,
        material_cost_cents=_non_negative_cents(fields.get("material_cost_cents"), "material_cost_cents"),
        labor_cost_cents=_non_negative_cents(fields.get("labor_cost_cents"), "labor_cost_cents"),
        notes=_optional_text(fields.get("notes")),
    ).model_dump()
    await db.wrap_panel_plans.insert_one(prepare_for_mongo(plan))
    await _bump_approval_revision(
        user,
        project,
        reason="Production panel plan changed after approval evidence",
        changed_fields=["panel_plan", "panel_plan.panels", "panel_plan.material_usage"],
        vehicle=await vehicles_repo.get(tenant_id=user["tenant_id"], entity_id=project["vehicle_id"]) if project.get("vehicle_id") else None,
        force=True,
    )
    await _audit(tenant_id=user["tenant_id"], project_id=project_id, user=user, action="wrap_lab.panel_plan_created", entity_type="wrap_panel_plan", entity_id=plan["id"], summary="Wrap Lab panel plan created", metadata={"revision": plan["revision"]})
    return serialize_doc(plan)  # type: ignore[return-value]


async def generate_packet(user: dict, project_id: str, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WRAP_LAB_WRITE)
    project_detail = await get_project(user, project_id)
    packet_type = fields["packet_type"]
    existing_count = await db.wrap_packets.count_documents({"tenant_id": user["tenant_id"], "project_id": project_id, "packet_type": packet_type})
    snapshot = {
        "project": project_detail["project"],
        "vehicle": project_detail["vehicle"],
        "coverage_plans": project_detail["coverage_plans"],
        "inspections": project_detail["inspections"],
        "design_scenes": project_detail["design_scenes"],
        "panel_plans": project_detail["panel_plans"],
        "warranties": project_detail["warranties"],
        "financial_summary": {
            "estimate_total_cents": int(project_detail["project"].get("estimate_total_cents") or 0),
            "deposit_required_cents": int(project_detail["project"].get("deposit_required_cents") or 0),
            "material_estimate_cents": int(project_detail["project"].get("material_estimate_cents") or 0),
            "labor_estimate_cents": int(project_detail["project"].get("labor_estimate_cents") or 0),
        },
        "notes": fields.get("notes"),
    }
    packet = WrapPacket(
        tenant_id=user["tenant_id"],
        project_id=project_id,
        packet_type=packet_type,
        revision=existing_count + 1,
        status="generated",
        snapshot=snapshot,
        layout_contract=_layout_contract(packet_type),
        generated_by_user_id=user.get("id"),
    ).model_dump()
    await db.wrap_packets.insert_one(prepare_for_mongo(packet))
    await _audit(tenant_id=user["tenant_id"], project_id=project_id, user=user, action="wrap_lab.packet_generated", entity_type="wrap_packet", entity_id=packet["id"], summary="Wrap Lab packet snapshot generated", metadata={"packet_type": packet_type, "revision": packet["revision"]})
    return serialize_doc(packet)  # type: ignore[return-value]


async def create_schedule(user: dict, project_id: str, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WRAP_LAB_WRITE)
    project = await _get_project(user["tenant_id"], project_id)
    await _ensure_open_project(project)
    schedule = WrapSchedule(
        tenant_id=user["tenant_id"],
        project_id=project_id,
        schedule_type=fields["schedule_type"],
        status=fields.get("status", "scheduled"),
        title=_clean_text(fields.get("title"), "title"),
        start_at=_clean_text(fields.get("start_at"), "start_at", limit=80),
        end_at=_clean_text(fields.get("end_at"), "end_at", limit=80),
        assigned_user_ids=fields.get("assigned_user_ids") or [],
        location=_optional_text(fields.get("location"), limit=200),
        calendar_event_id=fields.get("calendar_event_id"),
        notes=_optional_text(fields.get("notes")),
    ).model_dump()
    await db.wrap_schedules.insert_one(prepare_for_mongo(schedule))
    await _audit(tenant_id=user["tenant_id"], project_id=project_id, user=user, action="wrap_lab.schedule_created", entity_type="wrap_schedule", entity_id=schedule["id"], summary="Wrap Lab schedule record created", metadata={"schedule_type": schedule["schedule_type"], "calendar_event_id": schedule.get("calendar_event_id")})
    return serialize_doc(schedule)  # type: ignore[return-value]


async def create_warranty(user: dict, project_id: str, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WRAP_LAB_WRITE)
    project = await _get_project(user["tenant_id"], project_id)
    await _ensure_open_project(project)
    warranty = WrapWarranty(
        tenant_id=user["tenant_id"],
        project_id=project_id,
        status=fields.get("status", "draft"),
        starts_at=fields.get("starts_at"),
        expires_at=fields.get("expires_at"),
        coverage_terms=fields.get("coverage_terms") or [],
        care_instructions=fields.get("care_instructions") or [],
        issue_refs=fields.get("issue_refs") or [],
        warranty_value_cents=_non_negative_cents(fields.get("warranty_value_cents"), "warranty_value_cents"),
        notes=_optional_text(fields.get("notes")),
    ).model_dump()
    await db.wrap_warranties.insert_one(prepare_for_mongo(warranty))
    await _audit(tenant_id=user["tenant_id"], project_id=project_id, user=user, action="wrap_lab.warranty_created", entity_type="wrap_warranty", entity_id=warranty["id"], summary="Wrap Lab warranty/aftercare record created")
    return serialize_doc(warranty)  # type: ignore[return-value]


async def create_installation_record(user: dict, project_id: str, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WRAP_LAB_WRITE)
    project = await _get_project(user["tenant_id"], project_id)
    await _ensure_open_project(project)
    await _validate_file_ids(user["tenant_id"], fields.get("completion_photo_file_ids") or [])
    for uid in fields.get("installer_user_ids") or []:
        if not await db.users.find_one({"tenant_id": user["tenant_id"], "id": uid}, {"_id": 0, "id": 1}):
            raise WrapLabError("installer_not_found", f"Installer {uid} was not found for this tenant", 404)
    record = WrapInstallationRecord(
        tenant_id=user["tenant_id"],
        project_id=project_id,
        status=fields.get("status", "planned"),
        installer_user_ids=fields.get("installer_user_ids") or [],
        crew_names=fields.get("crew_names") or [],
        actual_start_at=fields.get("actual_start_at"),
        actual_end_at=fields.get("actual_end_at"),
        location=_optional_text(fields.get("location"), limit=200),
        preparation_checklist=fields.get("preparation_checklist") or [],
        installation_checklist=fields.get("installation_checklist") or [],
        issues=fields.get("issues") or [],
        completion_photo_file_ids=fields.get("completion_photo_file_ids") or [],
        quality_notes=_optional_text(fields.get("quality_notes"), limit=2000),
        customer_acknowledgement=fields.get("customer_acknowledgement") or {},
        notes=_optional_text(fields.get("notes")),
    ).model_dump()
    await db.wrap_installation_records.insert_one(prepare_for_mongo(record))
    await _audit(tenant_id=user["tenant_id"], project_id=project_id, user=user, action="wrap_lab.installation_record_created", entity_type="wrap_installation_record", entity_id=record["id"], summary="Wrap Lab installation/QC record created", metadata={"status": record["status"]})
    return serialize_doc(record)  # type: ignore[return-value]


async def production_handoff(user: dict, project_id: str, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WRAP_LAB_WRITE)
    _require_staff_perm(user, Perm.WORK_ORDER_WRITE)
    project_detail = await get_project(user, project_id)
    project = project_detail["project"]
    if not project.get("order_id"):
        raise WrapLabError("order_required", "A linked Order is required before production handoff", 400)
    if not project.get("order_item_id"):
        raise WrapLabError("order_item_required", "A linked wrap Order Item is required before production handoff", 400)
    readiness = project_detail["readiness"]
    override_reason = _optional_text(fields.get("override_reason"), limit=500)
    if any(blocker.get("code") == "approval_evidence_stale" for blocker in readiness.get("blockers") or []):
        raise WrapLabError("current_wrap_approval_required", "Wrap approval evidence is stale; create a current approval before production handoff.", 409)
    if not readiness["ready"] and not override_reason:
        raise WrapLabError("wrap_readiness_override_reason_required", "Wrap Project is not production-ready; provide an override reason.", 400)
    latest_plan = _latest(project_detail.get("panel_plans") or [])
    latest_inspection = _latest([i for i in project_detail.get("inspections", []) if i.get("status") != "superseded"])
    instructions_parts = [
        fields.get("production_instructions"),
        f"Wrap Project: {project.get('project_name')}",
        f"Coverage: {project.get('coverage_summary') or project.get('project_type')}",
        f"Specifications: {project.get('specifications') or {}}",
        f"Panel plan: {latest_plan.get('id') if latest_plan else 'missing'}",
        f"Inspection: {latest_inspection.get('id') if latest_inspection else 'missing'}",
    ]
    try:
        handoff = await order_readiness_service.production_handoff(
            tenant_id=user["tenant_id"],
            order_id=project["order_id"],
            payload={
                "override_reason": override_reason,
                "priority": fields.get("priority") or "normal",
                "due_date": fields.get("due_date") or project.get("due_at"),
                "production_instructions": "\n".join(str(part) for part in instructions_parts if part),
                "internal_notes": fields.get("internal_notes") or project.get("notes"),
                "assigned_user_ids": fields.get("assigned_user_ids") or project.get("assigned_user_ids") or [],
            },
            user=user,
        )
    except ValueError as exc:
        detail_map = {
            "order_not_found": ("order_not_found", "Linked Order was not found", 404),
            "no_production_required_items": ("no_production_required_items", "No production-required Order Items exist for this Order", 400),
            "readiness_override_reason_required": ("order_readiness_override_reason_required", "Order readiness requires an override reason", 400),
        }
        code, detail, status = detail_map.get(str(exc), ("production_handoff_failed", str(exc), 400))
        raise WrapLabError(code, detail, status)
    updates = {
        "status": "production_ready" if project.get("status") in PROJECT_STATUS_ORDER and PROJECT_STATUS_ORDER.index(project.get("status")) < PROJECT_STATUS_ORDER.index("production_ready") else project.get("status"),
        "work_order_id": handoff["work_order"].get("id"),
        "work_order_summary_id": handoff["work_order"].get("id"),
        "production_handoff": {
            "work_order_id": handoff["work_order"].get("id"),
            "already_exists": handoff.get("already_exists"),
            "override_applied": bool(override_reason),
            "override_reason": override_reason,
            "readiness": readiness,
            "handed_off_at": _now_iso(),
            "actor_user_id": user.get("id"),
        },
    }
    updated = await projects_repo.update(tenant_id=user["tenant_id"], entity_id=project_id, updates=updates)
    await _audit(tenant_id=user["tenant_id"], project_id=project_id, user=user, action="wrap_lab.production_handoff", entity_type="wrap_project", entity_id=project_id, summary="Wrap Project handed off to canonical Work Order", metadata={"work_order_id": handoff["work_order"].get("id"), "override_applied": bool(override_reason), "blockers": readiness.get("blockers")})
    return {"project": updated, **handoff, "wrap_readiness": readiness}


async def reports(user: dict) -> dict:
    _require_staff_perm(user, Perm.WRAP_LAB_READ)
    tenant_id = user["tenant_id"]
    projects = [doc async for doc in db.wrap_projects.find({"tenant_id": tenant_id}, {"_id": 0})]
    by_status: dict[str, int] = {}
    for project in projects:
        by_status[project["status"]] = by_status.get(project["status"], 0) + 1
    return {
        "project_count": len(projects),
        "status_counts": by_status,
        "estimate_total_cents": sum(int(p.get("estimate_total_cents") or 0) for p in projects),
        "deposit_required_cents": sum(int(p.get("deposit_required_cents") or 0) for p in projects),
        "material_estimate_cents": sum(int(p.get("material_estimate_cents") or 0) for p in projects),
        "labor_estimate_cents": sum(int(p.get("labor_estimate_cents") or 0) for p in projects),
    }
