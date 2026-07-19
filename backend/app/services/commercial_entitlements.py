"""EC13 commercial entitlement projection into EC2 `feature_entitlements`."""
from __future__ import annotations

from typing import Any

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.feature_entitlement import FeatureEntitlement
from .activity import record_activity_with_audit

COMMERCIAL_GRANTED_BY = "commercial_billing"


async def project_entitlements_for_tenant(*, tenant_id: str, actor_user_id: str = "system", actor_email: str = "system") -> dict:
    """Recompute commercial-derived EC2 entitlements for one tenant.

    This is the only EC13 write path into `feature_entitlements`. It updates
    rows previously granted by EC13 and does not modify manually reviewed or
    test-seeded entitlements with a different `granted_by` source.
    """
    active_product_ids: set[str] = set()
    async for sub in db.tenant_subscriptions.find(
        {"tenant_id": tenant_id, "status": {"$in": ["trialing", "active", "past_due", "cancellation_scheduled"]}},
        {"_id": 0},
    ):
        if sub.get("dunning_state") in {"suspended"}:
            continue
        active_product_ids.add(sub["plan_product_id"])
        active_product_ids.update(sub.get("add_on_product_ids") or [])

    active_trial = await db.trial_records.find_one(
        {"tenant_id": tenant_id, "status": {"$in": ["free_active", "extended_active"]}},
        {"_id": 0},
    )

    rule_filter: dict[str, Any] = {"enabled": True, "$or": []}
    if active_product_ids:
        rule_filter["$or"].append({"product_id": {"$in": sorted(active_product_ids)}})
    if active_trial:
        rule_filter["$or"].append({"entitlement_scope": "trial"})
    if not rule_filter["$or"]:
        rule_filter = {"id": "__none__"}

    desired: dict[str, dict] = {}
    async for rule in db.commercial_entitlement_rules.find(rule_filter, {"_id": 0}):
        feature_key = rule["feature_key"]
        existing = desired.get(feature_key)
        if existing and existing.get("source_priority", 100) <= rule.get("source_priority", 100):
            continue
        desired[feature_key] = rule

    now = utc_now().isoformat()
    changed: list[str] = []
    for feature_key, rule in desired.items():
        existing = await db.feature_entitlements.find_one({"tenant_id": tenant_id, "feature_key": feature_key}, {"_id": 0})
        if existing and existing.get("granted_by") not in {None, COMMERCIAL_GRANTED_BY}:
            continue
        patch = {
            "enabled": True,
            "quota": rule.get("quota"),
            "quota_used": 0 if existing is None else existing.get("quota_used", 0),
            "expires_at": None,
            "granted_by": COMMERCIAL_GRANTED_BY,
            "notes": f"Derived from EC13 commercial rule {rule['id']}",
            "updated_at": now,
        }
        if existing:
            await db.feature_entitlements.update_one({"tenant_id": tenant_id, "feature_key": feature_key}, {"$set": patch})
        else:
            ent = FeatureEntitlement(tenant_id=tenant_id, feature_key=feature_key, **{k: v for k, v in patch.items() if k != "updated_at"})
            doc = ent.model_dump()
            doc["updated_at"] = now
            await db.feature_entitlements.insert_one(prepare_for_mongo(doc))
        changed.append(feature_key)

    async for ent in db.feature_entitlements.find({"tenant_id": tenant_id, "granted_by": COMMERCIAL_GRANTED_BY}, {"_id": 0}):
        if ent["feature_key"] not in desired:
            await db.feature_entitlements.update_one(
                {"tenant_id": tenant_id, "feature_key": ent["feature_key"]},
                {"$set": {"enabled": False, "updated_at": now, "notes": "Disabled by EC13 commercial entitlement recompute"}},
            )
            changed.append(ent["feature_key"])

    if changed:
        await record_activity_with_audit(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            actor_email=actor_email,
            module="commercial_billing",
            action="commercial.entitlements_projected",
            entity_type="feature_entitlement",
            entity_id=tenant_id,
            summary="Commercial entitlements projected",
            metadata={"feature_keys": sorted(set(changed))},
        )
    cursor = db.feature_entitlements.find({"tenant_id": tenant_id, "granted_by": COMMERCIAL_GRANTED_BY}, {"_id": 0}).sort("feature_key", 1)
    items = [serialize_doc(doc) async for doc in cursor]
    return {"items": items, "total": len(items)}
