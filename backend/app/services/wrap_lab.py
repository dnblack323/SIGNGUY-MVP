"""EC15 - Wrap Lab shared-core service layer."""
from __future__ import annotations

from math import ceil
from typing import Any, Optional

from ..core.db import db
from ..core.permissions import Perm, permissions_for_role
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.wrap_lab import (
    WrapActivity,
    WrapCoveragePlan,
    WrapDesignScene,
    WrapInspection,
    WrapPacket,
    WrapPanelPlan,
    WrapProject,
    WrapSchedule,
    WrapVehicle,
    WrapWarranty,
)
from ..repositories.wrap_lab import WrapLabRepository
from .activity import record_activity_with_audit

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


class WrapLabError(Exception):
    def __init__(self, code: str, detail: str, status_code: int = 400):
        self.code = code
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def _now_iso() -> str:
    return utc_now().isoformat()


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
        vin=_optional_text(fields.get("vin"), limit=40),
        license_plate=_optional_text(fields.get("license_plate"), limit=40),
        color=_optional_text(fields.get("color"), limit=60),
        vehicle_type=fields.get("vehicle_type", "other"),
        template_key=_optional_text(fields.get("template_key"), limit=120),
        dimensions=fields.get("dimensions") or {},
        photo_file_ids=fields.get("photo_file_ids") or [],
        notes=_optional_text(fields.get("notes")),
    ).model_dump()
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


async def list_vehicles(user: dict, *, customer_id: Optional[str] = None) -> dict:
    _require_staff_perm(user, Perm.WRAP_LAB_READ)
    filters = {"customer_id": customer_id} if customer_id else {}
    return await vehicles_repo.list(tenant_id=user["tenant_id"], filters=filters, sort=[("updated_at", -1)])


async def create_project(user: dict, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WRAP_LAB_WRITE)
    await _assert_customer(user["tenant_id"], fields.get("customer_id"))
    await _assert_ref("wrap_vehicles", user["tenant_id"], fields.get("vehicle_id"), "vehicle_not_found")
    for collection, key, code in [
        ("intake_submissions", "intake_id", "intake_not_found"),
        ("quotes", "quote_id", "quote_not_found"),
        ("orders", "order_id", "order_not_found"),
        ("work_orders", "work_order_id", "work_order_not_found"),
    ]:
        await _assert_ref(collection, user["tenant_id"], fields.get(key), code)
    status = fields.get("status") or ("vehicle_recorded" if fields.get("vehicle_id") else "lead_intake")
    project = WrapProject(
        tenant_id=user["tenant_id"],
        customer_id=fields["customer_id"],
        vehicle_id=fields.get("vehicle_id"),
        intake_id=fields.get("intake_id"),
        quote_id=fields.get("quote_id"),
        order_id=fields.get("order_id"),
        work_order_id=fields.get("work_order_id"),
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
        notes=_optional_text(fields.get("notes")),
    ).model_dump()
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


async def list_projects(user: dict, *, status: Optional[str] = None, customer_id: Optional[str] = None) -> dict:
    _require_staff_perm(user, Perm.WRAP_LAB_READ)
    filters: dict[str, Any] = {}
    if status:
        filters["status"] = status
    if customer_id:
        filters["customer_id"] = customer_id
    return await projects_repo.list(tenant_id=user["tenant_id"], filters=filters, sort=[("updated_at", -1)])


async def get_project(user: dict, project_id: str) -> dict:
    _require_staff_perm(user, Perm.WRAP_LAB_READ)
    project = await _get_project(user["tenant_id"], project_id)
    return {
        "project": project,
        "vehicle": await vehicles_repo.get(tenant_id=user["tenant_id"], entity_id=project["vehicle_id"]) if project.get("vehicle_id") else None,
        "coverage_plans": (await coverage_repo.list(tenant_id=user["tenant_id"], filters={"project_id": project_id}))["items"],
        "inspections": (await inspections_repo.list(tenant_id=user["tenant_id"], filters={"project_id": project_id}))["items"],
        "design_scenes": (await designs_repo.list(tenant_id=user["tenant_id"], filters={"project_id": project_id}))["items"],
        "panel_plans": (await panel_plans_repo.list(tenant_id=user["tenant_id"], filters={"project_id": project_id}))["items"],
        "packets": (await packets_repo.list(tenant_id=user["tenant_id"], filters={"project_id": project_id}))["items"],
        "schedules": (await schedules_repo.list(tenant_id=user["tenant_id"], filters={"project_id": project_id}))["items"],
        "warranties": (await warranties_repo.list(tenant_id=user["tenant_id"], filters={"project_id": project_id}))["items"],
    }


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
    await _audit(tenant_id=user["tenant_id"], project_id=project_id, user=user, action="wrap_lab.coverage_plan_created", entity_type="wrap_coverage_plan", entity_id=plan["id"], summary="Wrap Lab coverage plan created")
    return serialize_doc(plan)  # type: ignore[return-value]


async def create_inspection(user: dict, project_id: str, fields: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WRAP_LAB_WRITE)
    project = await _get_project(user["tenant_id"], project_id)
    await _ensure_open_project(project)
    inspection = WrapInspection(
        tenant_id=user["tenant_id"],
        project_id=project_id,
        inspection_type=fields["inspection_type"],
        status=fields.get("status", "draft"),
        inspector_user_id=fields.get("inspector_user_id") or user.get("id"),
        damage_items=fields.get("damage_items") or [],
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
