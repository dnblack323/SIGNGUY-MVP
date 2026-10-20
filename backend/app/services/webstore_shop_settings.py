"""Shop-level Webstore settings: which fulfillment methods the shop supports (P2-12).

Stored in the tenant settings store (namespace ``webstores``, key ``fulfillment``)
behind this validated service; the generic settings API does not expose it.
Times are wall-clock in the shop's existing timezone (``get_tenant_timezone``).
"""
from __future__ import annotations

import re
from typing import Any

from ..core.permissions import Perm, permissions_for_role
from . import settings as settings_svc
from .time_period_utils import get_tenant_timezone

SETTINGS_NAMESPACE = "webstores"
FULFILLMENT_KEY = "fulfillment"

FULFILLMENT_METHODS: dict[str, str] = {
    "individual_shipping": "Individual shipping to each buyer",
    "bulk_shipping": "Bulk shipping to the organizer",
    "shop_pickup": "Pickup at our shop",
    "organizer_pickup": "Bulk pickup by the organizer",
    "event_distribution": "Distribution at the event",
    "local_delivery": "Local delivery",
}
PICKUP_METHODS = {"shop_pickup", "organizer_pickup", "event_distribution"}
SHIPPING_METHODS = {"individual_shipping", "bulk_shipping"}
MAX_PICKUP_WINDOWS = 3
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

DEFAULT_FULFILLMENT_SETTINGS: dict[str, Any] = {
    "supported_methods": ["individual_shipping", "bulk_shipping", "shop_pickup", "organizer_pickup", "event_distribution"],
    "default_pickup_location": "",
    "pickup_instructions": "",
    "pickup_windows_enabled": True,
    "default_window_start": "15:00",
    "default_window_end": "18:00",
}


class ShopSettingsError(Exception):
    def __init__(self, code: str, detail: str, status_code: int = 400):
        self.code, self.detail, self.status_code = code, detail, status_code
        super().__init__(detail)


async def get_fulfillment_settings(tenant_id: str) -> dict[str, Any]:
    doc = await settings_svc.get_setting(tenant_id=tenant_id, namespace=SETTINGS_NAMESPACE, key=FULFILLMENT_KEY)
    stored = (doc or {}).get("value") if isinstance((doc or {}).get("value"), dict) else {}
    result = {**DEFAULT_FULFILLMENT_SETTINGS, **stored}
    result["timezone"] = await get_tenant_timezone(tenant_id)
    result["method_labels"] = {k: FULFILLMENT_METHODS[k] for k in result["supported_methods"] if k in FULFILLMENT_METHODS}
    return result


async def update_fulfillment_settings(user: dict, fields: dict[str, Any]) -> dict[str, Any]:
    if Perm.WEBSTORE_MANAGE.value not in set(permissions_for_role(user.get("role", "staff"))):
        raise ShopSettingsError("permission_denied", f"Missing permission: {Perm.WEBSTORE_MANAGE.value}", 403)
    current = await get_fulfillment_settings(user["tenant_id"])
    methods = fields.get("supported_methods", current["supported_methods"])
    if not isinstance(methods, list) or not methods:
        raise ShopSettingsError("fulfillment_methods_required", "Choose at least one fulfillment method the shop supports")
    unknown = sorted(set(methods) - set(FULFILLMENT_METHODS))
    if unknown:
        raise ShopSettingsError("unknown_fulfillment_method", f"Unknown fulfillment methods: {', '.join(unknown)}")
    value = {
        "supported_methods": [m for m in FULFILLMENT_METHODS if m in methods],
        "default_pickup_location": str(fields.get("default_pickup_location", current["default_pickup_location"]) or "").strip()[:300],
        "pickup_instructions": str(fields.get("pickup_instructions", current["pickup_instructions"]) or "").strip()[:1000],
        "pickup_windows_enabled": bool(fields.get("pickup_windows_enabled", current["pickup_windows_enabled"])),
        "default_window_start": _time(fields.get("default_window_start", current["default_window_start"]), "default_window_start"),
        "default_window_end": _time(fields.get("default_window_end", current["default_window_end"]), "default_window_end"),
    }
    if value["default_window_end"] <= value["default_window_start"]:
        raise ShopSettingsError("pickup_window_invalid", "The default pickup window must end after it starts")
    await settings_svc.set_setting(
        tenant_id=user["tenant_id"], namespace=SETTINGS_NAMESPACE, key=FULFILLMENT_KEY, value=value, updated_by=user.get("id"),
    )
    return await get_fulfillment_settings(user["tenant_id"])


def _time(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not _TIME_RE.match(text):
        raise ShopSettingsError("invalid_time", f"{field} must be HH:MM (24-hour)")
    return text


def filter_questionnaire_to_shop(templates: list[dict[str, Any]], shop: dict[str, Any]) -> list[dict[str, Any]]:
    """Owners only see the fulfillment methods this shop supports; pickup windows only if enabled."""
    supported = set(shop.get("supported_methods") or [])
    result = []
    for template in templates:
        sections = []
        for section in template.get("sections") or []:
            questions = []
            for question in section.get("questions") or []:
                if question.get("key") == "fulfillment_methods":
                    question = {**question, "options": [o for o in question.get("options") or [] if o.get("value") in supported]}
                if question.get("key", "").startswith("pickup_window_") and not shop.get("pickup_windows_enabled", True):
                    continue
                questions.append(question)
            sections.append({**section, "questions": questions})
        result.append({**template, "sections": sections})
    return result
