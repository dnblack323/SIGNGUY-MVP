"""Canonical tenant-scoped record number allocation.

The existing `counters` collection remains the atomic source of truth. This
module adds stable record-type contracts, idempotent allocation records, and
future-ready format snapshots without changing existing numeric sequences.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc
from ..models.record_numbering import RecordNumberAllocation


class RecordNumberingError(ValueError):
    pass


@dataclass(frozen=True)
class RecordNumberDefinition:
    record_type: str
    collection: Optional[str]
    number_field: str
    prefix: str
    sequence_name: Optional[str] = None
    min_digits: int = 0


RECORD_NUMBER_DEFINITIONS: dict[str, RecordNumberDefinition] = {
    "quote": RecordNumberDefinition("quote", "quotes", "number", "Q"),
    "order": RecordNumberDefinition("order", "orders", "number", "O"),
    "invoice": RecordNumberDefinition("invoice", "invoices", "number", "I"),
    "payment": RecordNumberDefinition("payment", "payments", "number", "PAY"),
    "refund": RecordNumberDefinition("refund", "payments", "number", "REF"),
    "customer": RecordNumberDefinition("customer", "customers", "number", "CUST"),
    "work_order": RecordNumberDefinition("work_order", "work_orders", "number", "W"),
    "purchase_order": RecordNumberDefinition("purchase_order", "purchase_orders", "number", "PO"),
    "expense": RecordNumberDefinition("expense", "expenses", "number", "EXP"),
    "webstore_order": RecordNumberDefinition("webstore_order", "webstore_buyer_orders", "number", "WSO"),
    "proof": RecordNumberDefinition("proof", "proofs", "number", "P"),
    "signature_request": RecordNumberDefinition("signature_request", "signature_requests", "number", "SIG"),
    "quote_request": RecordNumberDefinition("quote_request", "quote_requests", "number", "QR"),
    "intake_submission": RecordNumberDefinition("intake_submission", "intake_submissions", "intake_number", "IN"),
}

RECORD_NUMBER_ALIASES = {
    "customer_intake": "intake_submission",
}


def normalize_record_type(record_type: str) -> str:
    key = str(record_type or "").strip().lower()
    key = RECORD_NUMBER_ALIASES.get(key, key)
    if key not in RECORD_NUMBER_DEFINITIONS:
        raise RecordNumberingError(f"unsupported_record_type:{record_type}")
    return key


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _sequence_name(record_type: str, config: dict[str, Any]) -> str:
    reset_policy = config.get("reset_policy") or "never"
    date_component = config.get("date_component") or "none"
    if reset_policy == "calendar_year" or date_component == "year":
        return f"{record_type}:{_now().year}"
    return record_type


def _validate_config(record_type: str, config: dict[str, Any]) -> dict[str, Any]:
    definition = RECORD_NUMBER_DEFINITIONS[record_type]
    prefix = str(config.get("prefix", definition.prefix))
    suffix = str(config.get("suffix", ""))
    starting_number = int(config.get("starting_number") or 1)
    min_digits = int(config.get("min_digits") or definition.min_digits)
    reset_policy = str(config.get("reset_policy") or "never")
    date_component = str(config.get("date_component") or "none")
    max_number = config.get("max_number")
    if starting_number < 1:
        raise RecordNumberingError("invalid_starting_number")
    if min_digits < 0 or min_digits > 12:
        raise RecordNumberingError("invalid_min_digits")
    if reset_policy not in {"never", "calendar_year"}:
        raise RecordNumberingError("invalid_reset_policy")
    if date_component not in {"none", "year"}:
        raise RecordNumberingError("invalid_date_component")
    if max_number is not None:
        max_number = int(max_number)
        if max_number < starting_number:
            raise RecordNumberingError("invalid_max_number")
    return {
        "record_type": record_type,
        "prefix": prefix,
        "starting_number": starting_number,
        "min_digits": min_digits,
        "suffix": suffix,
        "date_component": date_component,
        "reset_policy": reset_policy,
        "max_number": max_number,
    }


async def _effective_config(*, tenant_id: str, record_type: str) -> dict[str, Any]:
    doc = await db.record_number_configs.find_one(
        {"tenant_id": tenant_id, "record_type": record_type, "active": True},
        {"_id": 0},
    )
    return _validate_config(record_type, doc or {})


def format_record_number(number: int, config: dict[str, Any]) -> str:
    digits = str(int(number)).zfill(int(config.get("min_digits") or 0))
    parts: list[str] = []
    prefix = str(config.get("prefix") or "")
    suffix = str(config.get("suffix") or "")
    if prefix:
        parts.append(prefix)
    if config.get("date_component") == "year":
        parts.append(str(_now().year))
    parts.append(digits)
    body = "-".join(parts) if len(parts) > 1 else parts[0]
    return f"{body}{suffix}"


async def preview_next_record_number(*, tenant_id: str, record_type: str) -> dict[str, Any]:
    normalized = normalize_record_type(record_type)
    config = await _effective_config(tenant_id=tenant_id, record_type=normalized)
    sequence_name = _sequence_name(normalized, config)
    counter = await db.counters.find_one({"tenant_id": tenant_id, "name": sequence_name}, {"_id": 0})
    current = int(counter.get("value") or 0) if counter else int(config["starting_number"]) - 1
    next_value = current + 1
    return {
        "tenant_id": tenant_id,
        "record_type": normalized,
        "sequence_name": sequence_name,
        "next_number": next_value,
        "formatted_number": format_record_number(next_value, config),
        "config_snapshot": config,
    }


async def _ensure_counter_initialized(*, tenant_id: str, sequence_name: str, start_at: int) -> None:
    try:
        await db.counters.update_one(
            {"tenant_id": tenant_id, "name": sequence_name},
            {"$setOnInsert": {"tenant_id": tenant_id, "name": sequence_name, "value": start_at - 1}},
            upsert=True,
        )
    except DuplicateKeyError:
        return


async def _next_counter_value(*, tenant_id: str, sequence_name: str, config: dict[str, Any]) -> int:
    await _ensure_counter_initialized(
        tenant_id=tenant_id,
        sequence_name=sequence_name,
        start_at=int(config["starting_number"]),
    )
    max_number = config.get("max_number")
    query: dict[str, Any] = {"tenant_id": tenant_id, "name": sequence_name}
    if max_number is not None:
        query["value"] = {"$lt": int(max_number)}
    doc = await db.counters.find_one_and_update(
        query,
        {"$inc": {"value": 1}},
        return_document=ReturnDocument.AFTER,
    )
    if not doc:
        raise RecordNumberingError("sequence_exhausted")
    return int(doc["value"])


async def _advance_counter_at_least(*, tenant_id: str, sequence_name: str, value: int) -> None:
    await db.counters.update_one(
        {"tenant_id": tenant_id, "name": sequence_name},
        {"$setOnInsert": {"tenant_id": tenant_id, "name": sequence_name}, "$max": {"value": int(value)}},
        upsert=True,
    )


async def advance_record_number_counter_at_least(*, tenant_id: str, record_type: str, value: int) -> None:
    normalized = normalize_record_type(record_type)
    config = await _effective_config(tenant_id=tenant_id, record_type=normalized)
    await _advance_counter_at_least(
        tenant_id=tenant_id,
        sequence_name=_sequence_name(normalized, config),
        value=int(value),
    )


async def next_record_number(
    *,
    tenant_id: str,
    record_type: str,
    idempotency_key: Optional[str] = None,
    issued_to_entity_type: Optional[str] = None,
    issued_to_entity_id: Optional[str] = None,
    actor_user_id: Optional[str] = None,
    actor_email: Optional[str] = None,
    reason: Optional[str] = None,
    context: Optional[dict[str, Any]] = None,
) -> RecordNumberAllocation:
    normalized = normalize_record_type(record_type)
    if idempotency_key:
        existing = await db.record_number_allocations.find_one(
            {"tenant_id": tenant_id, "record_type": normalized, "idempotency_key": idempotency_key},
            {"_id": 0},
        )
        if existing:
            return RecordNumberAllocation(**serialize_doc(existing))

    config = await _effective_config(tenant_id=tenant_id, record_type=normalized)
    sequence_name = _sequence_name(normalized, config)
    number = await _next_counter_value(tenant_id=tenant_id, sequence_name=sequence_name, config=config)
    allocation = RecordNumberAllocation(
        tenant_id=tenant_id,
        record_type=normalized,
        sequence_name=sequence_name,
        number=number,
        formatted_number=format_record_number(number, config),
        idempotency_key=idempotency_key,
        issued_to_entity_type=issued_to_entity_type,
        issued_to_entity_id=issued_to_entity_id,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        reason=reason,
        context=context or {},
        config_snapshot=config,
    )
    try:
        await db.record_number_allocations.insert_one(prepare_for_mongo(allocation.model_dump()))
    except DuplicateKeyError:
        if idempotency_key:
            existing = await db.record_number_allocations.find_one(
                {"tenant_id": tenant_id, "record_type": normalized, "idempotency_key": idempotency_key},
                {"_id": 0},
            )
            if existing:
                return RecordNumberAllocation(**serialize_doc(existing))
        raise
    return allocation


async def next_number(*, tenant_id: str, name: str) -> int:
    """Backward-compatible numeric allocator for existing create paths."""
    allocation = await next_record_number(tenant_id=tenant_id, record_type=name)
    return int(allocation.number)


async def backfill_missing_record_numbers(
    *,
    tenant_id: str,
    record_type: str,
    actor_user_id: Optional[str] = None,
    actor_email: Optional[str] = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    normalized = normalize_record_type(record_type)
    definition = RECORD_NUMBER_DEFINITIONS[normalized]
    if not definition.collection:
        raise RecordNumberingError("record_type_has_no_collection")
    field = definition.number_field
    collection = db[definition.collection]
    existing_numbers: set[int] = set()
    async for doc in collection.find({"tenant_id": tenant_id, field: {"$exists": True}}, {"_id": 0, field: 1}):
        try:
            number = int(doc[field])
        except (TypeError, ValueError):
            raise RecordNumberingError("invalid_existing_number")
        if number in existing_numbers:
            raise RecordNumberingError("duplicate_existing_number")
        existing_numbers.add(number)

    config = await _effective_config(tenant_id=tenant_id, record_type=normalized)
    sequence_name = _sequence_name(normalized, config)
    if existing_numbers and not dry_run:
        await _advance_counter_at_least(tenant_id=tenant_id, sequence_name=sequence_name, value=max(existing_numbers))

    missing = [
        doc async for doc in collection.find(
            {"tenant_id": tenant_id, "$or": [{field: {"$exists": False}}, {field: None}]},
            {"_id": 0, "id": 1, "created_at": 1},
        ).sort([("created_at", 1), ("id", 1)])
    ]
    assigned: list[dict[str, Any]] = []
    for doc in missing:
        if dry_run:
            preview = await preview_next_record_number(tenant_id=tenant_id, record_type=normalized)
            assigned.append({"id": doc["id"], "would_assign": preview["next_number"]})
            continue
        allocation = await next_record_number(
            tenant_id=tenant_id,
            record_type=normalized,
            issued_to_entity_type=normalized,
            issued_to_entity_id=doc["id"],
            actor_user_id=actor_user_id,
            actor_email=actor_email,
            reason="record_number_backfill",
        )
        await collection.update_one(
            {"tenant_id": tenant_id, "id": doc["id"], "$or": [{field: {"$exists": False}}, {field: None}]},
            {"$set": {field: allocation.number}},
        )
        assigned.append({"id": doc["id"], "number": allocation.number})
    return {
        "tenant_id": tenant_id,
        "record_type": normalized,
        "collection": definition.collection,
        "number_field": field,
        "preserved_existing_count": len(existing_numbers),
        "assigned_count": len(assigned),
        "assigned": assigned,
        "dry_run": dry_run,
    }
