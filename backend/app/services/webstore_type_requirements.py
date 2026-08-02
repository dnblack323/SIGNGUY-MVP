"""Shared Webstore type settings and requirement rules."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

WEBSTORE_TYPE_REQUIREMENTS: dict[str, dict[str, Any]] = {
    "b2b": {
        "label": "B2B",
        "settings": {"access_policy": "restricted", "donation_enabled": False, "fulfillment_method": "pickup_or_shipping"},
        "requirements": [
            {"key": "access_policy", "label": "Access policy", "path": "store_settings.access_policy.mode", "owner_wording": "Store access rules are set."},
            {"key": "billing_po", "label": "Billing or PO requirements", "path": "setup_profile.billing_po_requirements", "owner_wording": "Billing or PO details are captured."},
            {"key": "catalog_updates", "label": "Catalog change frequency", "path": "setup_profile.catalog_change_frequency", "owner_wording": "Catalog update expectations are captured."},
            {"key": "fulfillment", "label": "Pickup/shipping setup", "path": "store_settings.fulfillment.method", "owner_wording": "Pickup or shipping details are set."},
        ],
    },
    "fundraiser": {
        "label": "Fundraiser",
        "settings": {"access_policy": "open", "donation_enabled": True, "fulfillment_method": "pickup"},
        "requirements": [
            {"key": "fundraiser_goal", "label": "Fundraiser goal", "path": "setup_profile.fundraiser_goal_amount", "owner_wording": "Fundraiser goal is captured."},
            {"key": "profit_allocation", "label": "Profit allocation", "path": "setup_profile.profit_allocation_type", "owner_wording": "Profit allocation is set."},
            {"key": "donations", "label": "Donation settings", "path": "store_settings.donation.enabled", "owner_wording": "Donation settings are set."},
            {"key": "deadline", "label": "Order deadline", "path": "store_settings.deadlines.order_deadline_at", "fallback_path": "deadline_at", "owner_wording": "Order deadline is set."},
        ],
    },
    "event": {
        "label": "Event",
        "settings": {"access_policy": "open", "donation_enabled": False, "fulfillment_method": "event_pickup"},
        "requirements": [
            {"key": "event_date", "label": "Event date", "path": "event_start_at", "owner_wording": "Event date is captured."},
            {"key": "event_location", "label": "Event location", "path": "event_location", "owner_wording": "Event location is captured."},
            {"key": "pickup", "label": "Event pickup instructions", "path": "setup_profile.pickup_instructions", "owner_wording": "Pickup instructions are captured."},
            {"key": "deadline", "label": "Order deadline", "path": "store_settings.deadlines.order_deadline_at", "fallback_path": "deadline_at", "owner_wording": "Order deadline is set."},
        ],
    },
    "promotional": {
        "label": "Promotional",
        "settings": {"access_policy": "open", "donation_enabled": False, "fulfillment_method": "pickup_or_shipping"},
        "requirements": [
            {"key": "brand_identity", "label": "Brand identity", "path": "setup_profile.brand_identity_name", "owner_wording": "Brand identity is captured."},
            {"key": "promotion_goal", "label": "Promotion goal", "path": "setup_profile.promotion_goal", "owner_wording": "Promotion goal is captured."},
            {"key": "promo_channels", "label": "Promotion channels", "path": "setup_profile.promo_channels", "owner_wording": "Promotion channels are captured."},
            {"key": "promo_copy", "label": "Promo copy notes", "path": "store_settings.promo.copy_notes", "fallback_path": "setup_profile.promo_copy_notes", "owner_wording": "Promo copy notes are captured."},
        ],
    },
    "employee": {
        "label": "Employee",
        "settings": {"access_policy": "restricted", "donation_enabled": False, "fulfillment_method": "pickup"},
        "requirements": [
            {"key": "employee_audience", "label": "Employee audience", "path": "setup_profile.employee_audience", "owner_wording": "Employee audience is captured."},
            {"key": "departments", "label": "Department categories", "path": "setup_profile.department_categories", "owner_wording": "Department categories are captured."},
            {"key": "access_policy", "label": "Employee access policy", "path": "store_settings.access_policy.mode", "owner_wording": "Employee access rules are set."},
            {"key": "allowance", "label": "Allowance notes", "path": "setup_profile.allowance_notes", "owner_wording": "Allowance notes are captured."},
        ],
    },
    "general": {
        "label": "General",
        "settings": {"access_policy": "open", "donation_enabled": False, "fulfillment_method": "pickup"},
        "requirements": [
            {"key": "purpose", "label": "Store purpose", "path": "setup_profile.store_purpose", "fallback_path": "setup_profile.goals", "owner_wording": "Store purpose is captured."},
            {"key": "audience", "label": "Audience", "path": "setup_profile.audience", "owner_wording": "Audience is captured."},
            {"key": "fulfillment", "label": "Pickup/shipping setup", "path": "store_settings.fulfillment.method", "owner_wording": "Pickup or shipping details are set."},
            {"key": "promo_copy", "label": "Promo copy notes", "path": "store_settings.promo.copy_notes", "fallback_path": "setup_profile.promo_copy_notes", "owner_wording": "Promo copy notes are captured."},
        ],
    },
}


def _get_path(data: dict[str, Any], path: str | None) -> Any:
    current: Any = data
    for part in (path or "").split("."):
      if not part:
          continue
      if not isinstance(current, dict):
          return None
      current = current.get(part)
    return current


def _complete(value: Any) -> bool:
    if isinstance(value, bool):
        return True
    if isinstance(value, (list, tuple, set)):
        return len(value) > 0
    if isinstance(value, dict):
        return any(_complete(item) for item in value.values())
    return value is not None and str(value).strip() != ""


def type_rule_for(store_type: str | None) -> dict[str, Any]:
    return WEBSTORE_TYPE_REQUIREMENTS.get(store_type or "general") or WEBSTORE_TYPE_REQUIREMENTS["general"]


def default_store_settings(store_type: str | None, existing: dict[str, Any] | None = None) -> dict[str, Any]:
    rule = type_rule_for(store_type)
    defaults = rule["settings"]
    result = {
        "access_policy": {"mode": defaults["access_policy"], "owner_wording": ""},
        "donation": {"enabled": defaults["donation_enabled"], "goal_amount_cents": None, "public_progress": False},
        "fulfillment": {"method": defaults["fulfillment_method"], "pickup_copy": "", "shipping_copy": ""},
        "deadlines": {"order_deadline_at": None, "late_orders_allowed": False, "late_order_copy": ""},
        "promo": {"copy_notes": "", "channels": []},
        "tax_shipping_copy": {"tax_copy": "", "shipping_copy": ""},
    }
    if existing:
        result = _deep_merge(result, existing)
    return result


def _deep_merge(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in (incoming or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def evaluate_type_requirements(store: dict[str, Any]) -> dict[str, Any]:
    store_type = store.get("store_type") or "general"
    rule = type_rule_for(store_type)
    normalized = {**store, "store_settings": default_store_settings(store_type, store.get("store_settings") or {})}
    items = []
    for raw in rule["requirements"]:
        value = _get_path(normalized, raw.get("path"))
        if not _complete(value) and raw.get("fallback_path"):
            value = _get_path(normalized, raw.get("fallback_path"))
        complete = _complete(value)
        items.append({
            "key": raw["key"],
            "label": raw["label"],
            "status": "complete" if complete else "missing",
            "complete": complete,
            "path": raw.get("path"),
            "owner_wording": raw.get("owner_wording") or raw["label"],
            "blocking": True,
        })
    return {
        "store_type": store_type,
        "label": rule["label"],
        "store_settings": normalized["store_settings"],
        "settings_schema": default_store_settings(store_type),
        "items": items,
        "complete": all(item["complete"] for item in items),
        "missing": [item for item in items if not item["complete"]],
    }
