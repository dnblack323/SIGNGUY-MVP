"""Shared Webstore type settings and requirement rules."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

WEBSTORE_TYPE_REQUIREMENTS: dict[str, dict[str, Any]] = {
    "fundraiser": {
        "label": "Fundraiser",
        "settings": {"access_policy": "open", "donation_enabled": True, "fulfillment_method": "organizer_pickup"},
        "requirements": [
            {"key": "fundraiser_purpose", "label": "Fundraiser purpose", "path": "store_settings.fundraiser.purpose", "owner_wording": "What the money is raised for is captured."},
            {"key": "profit_allocation", "label": "Proceeds arrangement", "path": "store_settings.fundraiser.allocation_type", "owner_wording": "How proceeds are shared is set."},
            {"key": "donations", "label": "Donation settings", "path": "store_settings.donation.enabled", "owner_wording": "Donation settings are set."},
            {"key": "deadline", "label": "Order deadline", "path": "store_settings.deadlines.order_deadline_at", "fallback_path": "deadline_at", "owner_wording": "Order deadline is set."},
        ],
    },
    "event": {
        "label": "Event",
        "settings": {"access_policy": "open", "donation_enabled": False, "fulfillment_method": "event_distribution"},
        "requirements": [
            {"key": "event_date", "label": "Event date", "path": "event_start_at", "owner_wording": "Event date is captured."},
            {"key": "event_location", "label": "Event location", "path": "event_location", "owner_wording": "Event location is captured."},
            {"key": "fulfillment", "label": "Fulfillment method", "path": "store_settings.fulfillment.methods", "owner_wording": "How buyers receive orders is set."},
            {"key": "deadline", "label": "Order deadline", "path": "store_settings.deadlines.order_deadline_at", "fallback_path": "deadline_at", "owner_wording": "Order deadline is set."},
        ],
    },
    "team_school": {
        "label": "Team / School",
        "settings": {"access_policy": "open", "donation_enabled": False, "fulfillment_method": "organizer_pickup"},
        "requirements": [
            {"key": "group_name", "label": "Team, school or club", "path": "setup_profile.group_name", "owner_wording": "The team or school is identified."},
            {"key": "fulfillment", "label": "Fulfillment method", "path": "store_settings.fulfillment.methods", "owner_wording": "How buyers receive orders is set."},
            {"key": "deadline", "label": "Order deadline", "path": "store_settings.deadlines.order_deadline_at", "fallback_path": "deadline_at", "owner_wording": "Order deadline is set."},
        ],
    },
    "b2b": {
        "label": "Business / B2B",
        "settings": {"access_policy": "restricted", "donation_enabled": False, "fulfillment_method": "bulk_shipping"},
        "requirements": [
            {"key": "access_policy", "label": "Access policy", "path": "store_settings.access_policy.mode", "owner_wording": "Store access rules are set."},
            {"key": "billing_po", "label": "Billing or PO requirements", "path": "setup_profile.billing_po_requirements", "owner_wording": "Billing or PO details are captured."},
            {"key": "fulfillment", "label": "Fulfillment method", "path": "store_settings.fulfillment.methods", "owner_wording": "Pickup or shipping details are set."},
        ],
    },
    "promotional": {
        "label": "Promotional",
        "settings": {"access_policy": "open", "donation_enabled": False, "fulfillment_method": "individual_shipping"},
        "requirements": [
            {"key": "brand_identity", "label": "Brand identity", "path": "setup_profile.brand_identity_name", "owner_wording": "Brand identity is captured."},
            {"key": "promotion_goal", "label": "Promotion goal", "path": "setup_profile.promotion_goal", "owner_wording": "Promotion goal is captured."},
            {"key": "promo_channels", "label": "Promotion channels", "path": "store_settings.promo.channels", "owner_wording": "Promotion channels are captured."},
        ],
    },
    "general": {
        "label": "General",
        "settings": {"access_policy": "open", "donation_enabled": False, "fulfillment_method": "shop_pickup"},
        "requirements": [
            {"key": "purpose", "label": "Store purpose", "path": "setup_profile.store_purpose", "fallback_path": "description", "owner_wording": "Store purpose is captured."},
            {"key": "fulfillment", "label": "Fulfillment method", "path": "store_settings.fulfillment.methods", "owner_wording": "Pickup or shipping details are set."},
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
        "fundraiser": {"name": "", "purpose": "", "goal_amount_cents": None, "allocation_type": None, "allocation_percentage": None, "allocation_fixed_cents": None},
        "fulfillment": {
            "method": defaults["fulfillment_method"],
            "methods": [],
            "pickup_copy": "",
            "shipping_copy": "",
            "pickup_location": "",
            "pickup_instructions": "",
            "pickup_windows": [],
            "bag_and_label": False,
            "delivery_address": "",
        },
        "deadlines": {"order_deadline_at": None, "late_orders_allowed": False, "late_order_copy": ""},
        "production": {"personalization_enabled": False, "personalization_details": "", "artwork_status": None},
        "promo": {"copy_notes": "", "channels": []},
        "campaign": {"repeat": None},
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
