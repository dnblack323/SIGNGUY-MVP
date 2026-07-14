"""EC9 Phase 9G — Advisory request/response persistence (§8-§12).

NO live AI/web/market-data provider is ever called here. Every response is
created with `status="unavailable"` — this module only builds and stores the
CONTRACT so EC16 (Shared AI Gateway) / EC17 (Studio AI Tools) have a
provider-neutral, tenant-scoped place to plug a real analysis in later.

Rules enforced here (§11):
- Advisory failures/unavailability never block normal pricing — nothing in
  this module writes to a Quote/Order/Order Item.
- Advisory results never silently replace selected pricing — the only path
  that can create a new pricing snapshot is `decide_advisory_response` with
  an explicit `decision="accepted"` AND a populated recommended price (never
  true for the "unavailable" placeholders this phase creates).
- Advisory records are always tenant-scoped.
"""
from __future__ import annotations

from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, utc_now
from ..models.pricing_advisory import AdvisoryRequest, AdvisoryResponseItem
from .pricing_snapshot_records import create_snapshot_record

VALID_ADVISORY_TYPES = {
    "ai_pricing_analysis", "historical_pricing_comparison", "local_market_comparison",
    "regional_market_comparison", "target_margin_analysis", "cost_risk_analysis",
    "underpricing_warning", "overpricing_warning", "price_confidence_analysis",
}


def _now_iso() -> str:
    return utc_now().isoformat()


async def create_advisory_request(tenant_id: str, user_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    """Persist the request contract + one placeholder response per requested
    type. Every placeholder is `status="unavailable"` — no provider is called."""
    requested_types = [t for t in (fields.get("requested_advisory_types") or []) if t in VALID_ADVISORY_TYPES]
    responses = [
        AdvisoryResponseItem(advisory_type=t, status="unavailable", source_type="none").model_dump()
        for t in requested_types
    ]
    req = AdvisoryRequest(
        tenant_id=tenant_id, user_id=user_id,
        category=fields.get("category"), item_description=fields.get("item_description"),
        quantity=fields.get("quantity"), calculator_inputs=fields.get("calculator_inputs") or {},
        material_summary=fields.get("material_summary") or {}, component_summary=fields.get("component_summary") or [],
        current_suggested_price_cents=fields.get("current_suggested_price_cents"),
        manual_price_cents=fields.get("manual_price_cents"),
        selected_final_price_cents=fields.get("selected_final_price_cents"),
        estimated_cost_cents=fields.get("estimated_cost_cents"),
        target_margin_percent=fields.get("target_margin_percent"),
        historical_snapshot_id=fields.get("historical_snapshot_id"),
        geographic_market_scope=fields.get("geographic_market_scope"),
        owner_notes=fields.get("owner_notes"), requested_advisory_types=requested_types,
        data_consent=bool(fields.get("data_consent", False)), request_timestamp=_now_iso(),
        responses=responses,
        overall_status="unavailable" if requested_types else "not_requested",
    ).model_dump()
    await db.pricing_advisory_requests.insert_one(prepare_for_mongo(dict(req)))
    req.pop("_id", None)
    return req


async def get_advisory_request(tenant_id: str, request_id: str) -> Optional[dict[str, Any]]:
    return await db.pricing_advisory_requests.find_one({"tenant_id": tenant_id, "id": request_id}, {"_id": 0})


async def list_advisory_requests(
    tenant_id: str, *, historical_snapshot_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    filt: dict[str, Any] = {"tenant_id": tenant_id}
    if historical_snapshot_id:
        filt["historical_snapshot_id"] = historical_snapshot_id
    return [d async for d in db.pricing_advisory_requests.find(filt, {"_id": 0}).sort("created_at", -1)]


async def decide_advisory_response(
    tenant_id: str, request_id: str, advisory_type: str, decision: str, *,
    user_id: str, notes: Optional[str] = None,
    apply_to: Optional[dict[str, Any]] = None,  # {"source_type","source_id","item_doc",...}
) -> dict[str, Any]:
    """§11 — recording a decision NEVER touches pricing by itself. Only when
    decision == "accepted" AND the response actually carries a recommended
    price AND the caller supplies `apply_to` does this create a NEW pricing
    snapshot (never edits an existing one) — exercised directly by tests with
    a synthetic populated response, never by any live provider call."""
    if decision not in {"accepted", "rejected"}:
        raise ValueError("invalid_decision")
    req = await get_advisory_request(tenant_id, request_id)
    if not req:
        raise ValueError("advisory_request_not_found")
    responses = req.get("responses") or []
    idx = next((i for i, r in enumerate(responses) if r.get("advisory_type") == advisory_type), None)
    if idx is None:
        raise ValueError("advisory_response_not_found")
    now = _now_iso()
    responses[idx] = {**responses[idx], "user_decision": decision, "user_notes": notes, "decided_at": now}
    await db.pricing_advisory_requests.update_one(
        {"id": request_id, "tenant_id": tenant_id}, {"$set": {"responses": responses, "updated_at": now}},
    )

    if decision == "accepted" and apply_to and responses[idx].get("recommended_price_range_cents"):
        await create_snapshot_record(
            tenant_id=tenant_id, source_type=apply_to["source_type"], source_id=apply_to["source_id"],
            quote_id=apply_to.get("quote_id"), order_id=apply_to.get("order_id"),
            item_doc=apply_to["item_doc"], calculated_by_user_id=user_id, status="accepted",
        )

    return await get_advisory_request(tenant_id, request_id)
