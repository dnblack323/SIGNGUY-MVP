"""EC13 commercial entitlement projection into EC2 `feature_entitlements`.

F1 (Commercial V1): this module is also the single owner of a tenant's
commercial access state, derived only from the existing `tenant_subscriptions`
and `trial_records` contracts. A trial's end is carried by `expires_at` on
projected rows, so trial access lapses without a scheduler or an admin call.
Subscriptions follow owner decision C2: past-due (including day 15+, which is
only *eligible* for suspension) keeps access until an admin formally suspends.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.feature_entitlement import FeatureEntitlement
from .activity import record_activity_with_audit

COMMERCIAL_GRANTED_BY = "commercial_billing"

# Subscription statuses that can still grant access (EC13 contract).
USABLE_SUBSCRIPTION_STATUSES = ("trialing", "active", "past_due", "cancellation_scheduled")
ACTIVE_TRIAL_STATUSES = ("free_active", "extended_active")

ACCESS_FULL = "full"
ACCESS_READ_ONLY = "read_only"
ACCESS_UNBILLED = "unbilled"


def _parse_iso(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        when = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def _subscription_grants_access(sub: dict) -> bool:
    """EC13 contract: usable statuses grant access unless formally suspended."""
    return sub.get("status") in USABLE_SUBSCRIPTION_STATUSES and sub.get("dunning_state") != "suspended"


def _trial_until(trial: dict, now: datetime) -> Optional[datetime]:
    """End of a still-running trial, or None when the trial is not running."""
    if trial.get("status") not in ACTIVE_TRIAL_STATUSES:
        return None
    ends_at = _parse_iso(trial.get("ends_at"))
    return ends_at if ends_at and ends_at > now else None


async def resolve_commercial_access(*, tenant_id: str, as_of: Optional[datetime] = None) -> dict:
    """Read-only commercial access state for one tenant (no writes).

    - `unbilled`: no trial or subscription has ever existed (pre-commercial or
      legacy tenant); no restriction is applied.
    - `full`: a running trial or a subscription that is not suspended or ended.
      Past-due subscriptions keep core access: per owner decision C2, day 15+
      only makes a shop *eligible* for suspension.
    - `read_only`: commercial history exists but nothing currently grants
      access (trial expired without purchase, subscription suspended, unpaid
      or canceled). Core records stay readable and exportable.
    """
    now = as_of or utc_now()
    has_history = False
    trial_ends_at: Optional[datetime] = None
    async for trial in db.trial_records.find({"tenant_id": tenant_id}, {"_id": 0}):
        has_history = True
        until = _trial_until(trial, now)
        if until and (trial_ends_at is None or until > trial_ends_at):
            trial_ends_at = until
    usable_subscription = False
    async for sub in db.tenant_subscriptions.find({"tenant_id": tenant_id}, {"_id": 0}):
        has_history = True
        if _subscription_grants_access(sub):
            usable_subscription = True
    if not has_history:
        return {"state": ACCESS_UNBILLED, "read_only": False, "reason": None, "trial_ends_at": None}
    if usable_subscription or trial_ends_at:
        return {
            "state": ACCESS_FULL,
            "read_only": False,
            "reason": None,
            "trial_ends_at": trial_ends_at.isoformat() if trial_ends_at and not usable_subscription else None,
        }
    return {"state": ACCESS_READ_ONLY, "read_only": True, "reason": "subscription_inactive", "trial_ends_at": None}


async def project_entitlements_for_tenant(*, tenant_id: str, actor_user_id: str = "system", actor_email: str = "system") -> dict:
    """Recompute commercial-derived EC2 entitlements for one tenant.

    This is the only EC13 write path into `feature_entitlements`. It updates
    rows previously granted by EC13 and does not modify manually reviewed or
    test-seeded entitlements with a different `granted_by` source.

    Rows granted only by a running trial carry the trial's end as
    `expires_at`; rows granted by a subscription are open-ended
    (`expires_at=None`) until the subscription is suspended or ends.
    """
    now = utc_now()
    active_product_ids: set[str] = set()
    async for sub in db.tenant_subscriptions.find(
        {"tenant_id": tenant_id, "status": {"$in": list(USABLE_SUBSCRIPTION_STATUSES)}},
        {"_id": 0},
    ):
        if not _subscription_grants_access(sub):
            continue
        active_product_ids.add(sub["plan_product_id"])
        active_product_ids.update(sub.get("add_on_product_ids") or [])

    trial_until: Optional[datetime] = None
    async for trial in db.trial_records.find(
        {"tenant_id": tenant_id, "status": {"$in": list(ACTIVE_TRIAL_STATUSES)}},
        {"_id": 0},
    ):
        until = _trial_until(trial, now)
        if until and (trial_until is None or until > trial_until):
            trial_until = until

    rule_filter: dict[str, Any] = {"enabled": True, "$or": []}
    if active_product_ids:
        rule_filter["$or"].append({"product_id": {"$in": sorted(active_product_ids)}})
    if trial_until:
        rule_filter["$or"].append({"entitlement_scope": "trial"})
    if not rule_filter["$or"]:
        rule_filter = {"id": "__none__"}

    desired: dict[str, dict] = {}
    expiry: dict[str, Optional[datetime]] = {}
    async for rule in db.commercial_entitlement_rules.find(rule_filter, {"_id": 0}):
        feature_key = rule["feature_key"]
        # Subscription grants are open-ended; trial-only grants end with the trial.
        rule_until = None if rule.get("product_id") in active_product_ids else trial_until
        if feature_key in expiry:
            previous = expiry[feature_key]
            expiry[feature_key] = None if previous is None or rule_until is None else max(previous, rule_until)
        else:
            expiry[feature_key] = rule_until
        existing = desired.get(feature_key)
        if existing and existing.get("source_priority", 100) <= rule.get("source_priority", 100):
            continue
        desired[feature_key] = rule

    now = now.isoformat()
    changed: list[str] = []
    for feature_key, rule in desired.items():
        existing = await db.feature_entitlements.find_one({"tenant_id": tenant_id, "feature_key": feature_key}, {"_id": 0})
        if existing and existing.get("granted_by") not in {None, COMMERCIAL_GRANTED_BY}:
            continue
        expires_at = expiry.get(feature_key)
        patch = {
            "enabled": True,
            "quota": rule.get("quota"),
            "quota_used": 0 if existing is None else existing.get("quota_used", 0),
            "expires_at": expires_at.isoformat() if expires_at else None,
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
