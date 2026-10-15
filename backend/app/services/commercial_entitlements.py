"""EC13 commercial entitlement projection into EC2 `feature_entitlements`.

F1 (Commercial V1): this module is also the single owner of a tenant's
commercial access state, derived only from the existing `tenant_subscriptions`
and `trial_records` contracts. Time-based loss of access (trial end, day-15
dunning) is carried by `expires_at` on projected rows, so it takes effect
without a scheduler or a manual admin call.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.feature_entitlement import FeatureEntitlement
from .activity import record_activity_with_audit

COMMERCIAL_GRANTED_BY = "commercial_billing"

# Subscription statuses that can still grant access (EC13 contract).
USABLE_SUBSCRIPTION_STATUSES = ("trialing", "active", "past_due", "cancellation_scheduled")
ACTIVE_TRIAL_STATUSES = ("free_active", "extended_active")
# Owner decision C2: day 15+ after the first failed payment is past the grace period.
PAID_FEATURE_GRACE_DAYS = 15

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


def _subscription_paid_access_until(sub: dict, now: datetime) -> tuple[bool, Optional[datetime]]:
    """Whether a subscription still grants paid features, and until when (None = open-ended)."""
    if sub.get("status") not in USABLE_SUBSCRIPTION_STATUSES or sub.get("dunning_state") == "suspended":
        return False, None
    failed_at = _parse_iso(sub.get("first_payment_failed_at"))
    if sub.get("status") != "past_due" or not failed_at:
        return True, None
    until = failed_at + timedelta(days=PAID_FEATURE_GRACE_DAYS)
    grace_until = _parse_iso(sub.get("manual_grace_until"))
    if grace_until and grace_until > until:
        until = grace_until
    return until > now, until


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
        if sub.get("status") in USABLE_SUBSCRIPTION_STATUSES and sub.get("dunning_state") != "suspended":
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

    Each projected row carries the latest time its granting sources remain
    valid (trial end, or day-15 dunning cut-off extended by manual grace);
    `expires_at=None` means open-ended.
    """
    now = utc_now()
    # product_id -> latest access time across subscriptions (None = open-ended)
    product_until: dict[str, Optional[datetime]] = {}
    async for sub in db.tenant_subscriptions.find(
        {"tenant_id": tenant_id, "status": {"$in": list(USABLE_SUBSCRIPTION_STATUSES)}},
        {"_id": 0},
    ):
        usable, until = _subscription_paid_access_until(sub, now)
        if not usable:
            continue
        for product_id in [sub["plan_product_id"], *(sub.get("add_on_product_ids") or [])]:
            if product_id in product_until and product_until[product_id] is None:
                continue
            previous = product_until.get(product_id)
            product_until[product_id] = None if until is None else max(until, previous) if previous else until

    trial_until: Optional[datetime] = None
    async for trial in db.trial_records.find(
        {"tenant_id": tenant_id, "status": {"$in": list(ACTIVE_TRIAL_STATUSES)}},
        {"_id": 0},
    ):
        until = _trial_until(trial, now)
        if until and (trial_until is None or until > trial_until):
            trial_until = until

    rule_filter: dict[str, Any] = {"enabled": True, "$or": []}
    if product_until:
        rule_filter["$or"].append({"product_id": {"$in": sorted(product_until)}})
    if trial_until:
        rule_filter["$or"].append({"entitlement_scope": "trial"})
    if not rule_filter["$or"]:
        rule_filter = {"id": "__none__"}

    desired: dict[str, dict] = {}
    expiry: dict[str, Optional[datetime]] = {}
    async for rule in db.commercial_entitlement_rules.find(rule_filter, {"_id": 0}):
        feature_key = rule["feature_key"]
        candidates: list[Optional[datetime]] = []
        if rule.get("product_id") in product_until:
            candidates.append(product_until[rule["product_id"]])
        if trial_until and rule.get("entitlement_scope") == "trial":
            candidates.append(trial_until)
        rule_until = None if any(c is None for c in candidates) else max(candidates)
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
