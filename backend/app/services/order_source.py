"""Canonical Order source classification.

This service keeps Order provenance server-controlled while supporting legacy
rows that predate the canonical `order_source` field.
"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from ..core.db import db
from ..core.time_utils import serialize_doc

ORDER_SOURCE_MANUAL = "manual"
ORDER_SOURCE_QUOTE = "quote"
ORDER_SOURCE_WEBSTORE = "webstore"
ORDER_SOURCE_WRAP_LAB = "wrap_lab"
ORDER_SOURCE_EMAIL = "email"
ORDER_SOURCE_FACEBOOK = "facebook"
ORDER_SOURCE_LEGACY_UNKNOWN = "legacy_unknown"

VISIBLE_ORDER_SOURCES = (
    ORDER_SOURCE_MANUAL,
    ORDER_SOURCE_QUOTE,
    ORDER_SOURCE_WEBSTORE,
    ORDER_SOURCE_WRAP_LAB,
    ORDER_SOURCE_LEGACY_UNKNOWN,
)

RESERVED_ORDER_SOURCES = (
    ORDER_SOURCE_EMAIL,
    ORDER_SOURCE_FACEBOOK,
)

ALL_ORDER_SOURCES = VISIBLE_ORDER_SOURCES + RESERVED_ORDER_SOURCES

ORDER_SOURCE_RECORD_TYPES = {
    ORDER_SOURCE_QUOTE: "quote",
    ORDER_SOURCE_WEBSTORE: "webstore_buyer_order",
    ORDER_SOURCE_WRAP_LAB: "wrap_project",
    ORDER_SOURCE_EMAIL: "email_message",
    ORDER_SOURCE_FACEBOOK: "facebook_message",
}

ORDER_SOURCE_FILTER_OPTIONS = [
    {"value": ORDER_SOURCE_MANUAL, "label": "Manual"},
    {"value": ORDER_SOURCE_QUOTE, "label": "Quote"},
    {"value": ORDER_SOURCE_WEBSTORE, "label": "Webstore"},
    {"value": ORDER_SOURCE_WRAP_LAB, "label": "Wrap Lab"},
    {"value": ORDER_SOURCE_LEGACY_UNKNOWN, "label": "Legacy / Unknown"},
]


def parse_order_source_filter(raw: str | None) -> set[str] | None:
    if not raw:
        return None
    values = {part.strip() for part in raw.split(",") if part.strip()}
    if not values or values == {"all"}:
        return None
    unsupported = sorted(value for value in values if value not in ALL_ORDER_SOURCES)
    if unsupported:
        raise HTTPException(status_code=400, detail=f"Unsupported order_source: {', '.join(unsupported)}")
    return values


def apply_created_order_source(
    order: dict[str, Any],
    *,
    source: str,
    record_type: str | None = None,
    record_id: str | None = None,
) -> dict[str, Any]:
    if source not in ALL_ORDER_SOURCES or source == ORDER_SOURCE_LEGACY_UNKNOWN:
        raise ValueError("invalid_order_source")
    order["order_source"] = source
    if record_type:
        order["order_source_record_type"] = record_type
    if record_id:
        order["order_source_record_id"] = record_id
    return order


def visible_filter_contract() -> dict[str, Any]:
    return {
        "query_param": "order_source",
        "multiple_values": "comma_separated",
        "all_orders_value": "all",
        "visible_sources": ORDER_SOURCE_FILTER_OPTIONS,
        "reserved_hidden_sources": [
            {"value": ORDER_SOURCE_EMAIL, "label": "Email"},
            {"value": ORDER_SOURCE_FACEBOOK, "label": "Facebook"},
        ],
    }


def _normalize_from_explicit(order: dict[str, Any]) -> dict[str, Any] | None:
    source = order.get("order_source")
    if source in ALL_ORDER_SOURCES:
        normalized = dict(order)
        normalized["order_source"] = source
        return normalized
    return None


def _normalize_from_quote(order: dict[str, Any]) -> dict[str, Any] | None:
    quote_id = order.get("source_quote_id") or order.get("quote_id")
    if not quote_id:
        return None
    normalized = dict(order)
    normalized["order_source"] = ORDER_SOURCE_QUOTE
    normalized.setdefault("order_source_record_type", ORDER_SOURCE_RECORD_TYPES[ORDER_SOURCE_QUOTE])
    normalized.setdefault("order_source_record_id", quote_id)
    return normalized


def _normalize_from_webstore(order: dict[str, Any], buyer_order: dict[str, Any] | None) -> dict[str, Any] | None:
    if not buyer_order:
        return None
    normalized = dict(order)
    normalized["order_source"] = ORDER_SOURCE_WEBSTORE
    normalized.setdefault("order_source_record_type", ORDER_SOURCE_RECORD_TYPES[ORDER_SOURCE_WEBSTORE])
    normalized.setdefault("order_source_record_id", buyer_order.get("id"))
    return normalized


def _normalize_from_wrap_lab(order: dict[str, Any], project: dict[str, Any] | None) -> dict[str, Any] | None:
    if not project:
        return None
    normalized = dict(order)
    normalized["order_source"] = ORDER_SOURCE_WRAP_LAB
    normalized.setdefault("order_source_record_type", ORDER_SOURCE_RECORD_TYPES[ORDER_SOURCE_WRAP_LAB])
    normalized.setdefault("order_source_record_id", project.get("id"))
    return normalized


def _normalize_unknown(order: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(order)
    normalized["order_source"] = ORDER_SOURCE_LEGACY_UNKNOWN
    normalized.setdefault("order_source_record_type", None)
    normalized.setdefault("order_source_record_id", None)
    return normalized


async def normalize_order_source(order: dict[str, Any] | None) -> dict[str, Any] | None:
    if not order:
        return order
    serialized = serialize_doc(order)
    explicit = _normalize_from_explicit(serialized)
    if explicit:
        return explicit
    quote = _normalize_from_quote(serialized)
    if quote:
        return quote
    tenant_id = serialized.get("tenant_id")
    order_id = serialized.get("id")
    buyer = await db.webstore_buyer_orders.find_one(
        {"tenant_id": tenant_id, "bridged_order_id": order_id},
        {"_id": 0, "id": 1},
    )
    webstore = _normalize_from_webstore(serialized, buyer)
    if webstore:
        return webstore
    project = await db.wrap_projects.find_one(
        {"tenant_id": tenant_id, "order_id": order_id},
        {"_id": 0, "id": 1},
    )
    wrap_lab = _normalize_from_wrap_lab(serialized, project)
    if wrap_lab:
        return wrap_lab
    return _normalize_unknown(serialized)


async def normalize_order_sources(orders: list[dict[str, Any]]) -> list[dict[str, Any]]:
    serialized = [serialize_doc(order) for order in orders]
    unresolved = [
        order for order in serialized
        if not _normalize_from_explicit(order) and not _normalize_from_quote(order)
    ]
    by_tenant: dict[str, set[str]] = {}
    for order in unresolved:
        tenant_id = order.get("tenant_id")
        order_id = order.get("id")
        if tenant_id and order_id:
            by_tenant.setdefault(tenant_id, set()).add(order_id)

    buyer_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    project_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for tenant_id, order_ids in by_tenant.items():
        cursor = db.webstore_buyer_orders.find(
            {"tenant_id": tenant_id, "bridged_order_id": {"$in": list(order_ids)}},
            {"_id": 0, "id": 1, "bridged_order_id": 1},
        )
        async for buyer in cursor:
            buyer_by_key[(tenant_id, buyer["bridged_order_id"])] = buyer
        cursor = db.wrap_projects.find(
            {"tenant_id": tenant_id, "order_id": {"$in": list(order_ids)}},
            {"_id": 0, "id": 1, "order_id": 1},
        )
        async for project in cursor:
            project_by_key[(tenant_id, project["order_id"])] = project

    normalized: list[dict[str, Any]] = []
    for order in serialized:
        explicit = _normalize_from_explicit(order)
        if explicit:
            normalized.append(explicit)
            continue
        quote = _normalize_from_quote(order)
        if quote:
            normalized.append(quote)
            continue
        key = (order.get("tenant_id"), order.get("id"))
        webstore = _normalize_from_webstore(order, buyer_by_key.get(key))
        if webstore:
            normalized.append(webstore)
            continue
        wrap_lab = _normalize_from_wrap_lab(order, project_by_key.get(key))
        if wrap_lab:
            normalized.append(wrap_lab)
            continue
        normalized.append(_normalize_unknown(order))
    return normalized
