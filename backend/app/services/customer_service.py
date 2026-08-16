from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Optional

from fastapi import HTTPException

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..services.audit import record_audit


RELATED_CUSTOMER_COLLECTIONS = [
    "quotes",
    "orders",
    "work_orders",
    "invoices",
    "payments",
    "documents",
    "proofs",
    "email_logs",
    "message_threads",
    "internal_notes",
    "calendar_events",
    "portal_identities",
    "quote_requests",
    "customer_intakes",
    "decision_rooms",
    "customer_decisions",
    "decision_room_questions",
    "decision_room_overlays",
    "saved_for_later",
    "webstores",
    "tax_exemptions",
    "tasks",
    "expenses",
    "wrap_vehicles",
    "wrap_projects",
]

ATTACHMENT_PARENT_COLLECTIONS = ["attachments", "file_links"]
DOCUMENT_LINK_COLLECTIONS = ["document_links"]


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def normalize_phone(value: Any) -> str:
    return re.sub(r"\D+", "", str(value or ""))


def normalize_email(value: Any) -> str:
    return str(value or "").strip().lower()


def normalize_address_parts(parts: list[Any]) -> str:
    return normalize_text(" ".join(str(p) for p in parts if p))


def _compact_dict(data: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in data.items() if v not in (None, "", [], {})}


def _legacy_contact(doc: dict[str, Any]) -> Optional[dict[str, Any]]:
    if not any(doc.get(k) for k in ("email", "phone", "name")):
        return None
    return _compact_dict({
        "name": doc.get("name") or doc.get("company") or "Primary contact",
        "email": doc.get("email"),
        "phone": doc.get("phone"),
        "role": "primary",
        "is_primary": True,
    })


def _legacy_address(doc: dict[str, Any]) -> Optional[dict[str, Any]]:
    if not any(doc.get(k) for k in ("address_line1", "address_line2", "city", "state", "postal_code", "country")):
        return None
    return _compact_dict({
        "label": "Primary address",
        "line1": doc.get("address_line1"),
        "line2": doc.get("address_line2"),
        "city": doc.get("city"),
        "state": doc.get("state"),
        "postal_code": doc.get("postal_code"),
        "country": doc.get("country"),
        "purposes": ["billing", "shipping"],
        "is_default": True,
    })


def normalize_contacts(raw_contacts: Optional[list[dict[str, Any]]], legacy_doc: dict[str, Any]) -> list[dict[str, Any]]:
    contacts = [_compact_dict(dict(item)) for item in (raw_contacts or []) if isinstance(item, dict)]
    contacts = [item for item in contacts if item.get("name") or item.get("email") or item.get("phone")]
    if not contacts:
        legacy = _legacy_contact(legacy_doc)
        contacts = [legacy] if legacy else []
    if contacts and not any(item.get("is_primary") for item in contacts):
        contacts[0]["is_primary"] = True
    primary_seen = False
    for item in contacts:
        item.setdefault("role", "primary" if item.get("is_primary") else "other")
        if item.get("is_primary"):
            if primary_seen:
                item["is_primary"] = False
            else:
                primary_seen = True
                item["role"] = "primary"
    return contacts


def normalize_addresses(raw_addresses: Optional[list[dict[str, Any]]], legacy_doc: dict[str, Any]) -> list[dict[str, Any]]:
    addresses = [_compact_dict(dict(item)) for item in (raw_addresses or []) if isinstance(item, dict)]
    addresses = [item for item in addresses if any(item.get(k) for k in ("line1", "line2", "city", "state", "postal_code", "country"))]
    if not addresses:
        legacy = _legacy_address(legacy_doc)
        addresses = [legacy] if legacy else []
    if addresses and not any(item.get("is_default") for item in addresses):
        addresses[0]["is_default"] = True
    default_seen = False
    for item in addresses:
        item.setdefault("purposes", ["billing"] if item.get("is_default") else ["other"])
        if item.get("is_default"):
            if default_seen:
                item["is_default"] = False
            else:
                default_seen = True
    return addresses


def apply_customer_compatibility(data: dict[str, Any], existing: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    merged = {**(existing or {}), **data}
    contacts = normalize_contacts(merged.get("contacts"), merged)
    addresses = normalize_addresses(merged.get("addresses"), merged)
    merged["contacts"] = contacts
    merged["addresses"] = addresses

    primary = next((item for item in contacts if item.get("is_primary")), contacts[0] if contacts else {})
    default_address = next((item for item in addresses if item.get("is_default")), addresses[0] if addresses else {})

    if primary:
        merged["email"] = primary.get("email") or merged.get("email")
        merged["phone"] = primary.get("phone") or merged.get("phone")
    if default_address:
        merged["address_line1"] = default_address.get("line1") or merged.get("address_line1")
        merged["address_line2"] = default_address.get("line2") or merged.get("address_line2")
        merged["city"] = default_address.get("city") or merged.get("city")
        merged["state"] = default_address.get("state") or merged.get("state")
        merged["postal_code"] = default_address.get("postal_code") or merged.get("postal_code")
        merged["country"] = default_address.get("country") or merged.get("country")

    merged.setdefault("customer_type", "business")
    merged.setdefault("lifecycle_status", "archived" if merged.get("archived") else "active")
    if merged.get("archived"):
        merged["lifecycle_status"] = "merged" if merged.get("merged_into") else "archived"
    return merged


def serialize_customer(doc: dict[str, Any]) -> dict[str, Any]:
    return serialize_doc(apply_customer_compatibility(deepcopy(doc)))


def customer_match_fingerprint(doc: dict[str, Any]) -> dict[str, set[str]]:
    normalized = apply_customer_compatibility(deepcopy(doc))
    names = {normalize_text(normalized.get("name")), normalize_text(normalized.get("company"))} - {""}
    emails = {normalize_email(normalized.get("email"))} - {""}
    phones = {normalize_phone(normalized.get("phone"))} - {""}
    addresses = {normalize_address_parts([
        normalized.get("address_line1"), normalized.get("city"), normalized.get("state"), normalized.get("postal_code")
    ])} - {""}
    for contact in normalized.get("contacts", []):
        if contact.get("email"):
            emails.add(normalize_email(contact.get("email")))
        if contact.get("phone"):
            phone = normalize_phone(contact.get("phone"))
            if phone:
                phones.add(phone)
    for address in normalized.get("addresses", []):
        addr = normalize_address_parts([address.get("line1"), address.get("city"), address.get("state"), address.get("postal_code")])
        if addr:
            addresses.add(addr)
    return {"names": names, "emails": emails, "phones": phones, "addresses": addresses}


def match_reasons(a: dict[str, Any], b: dict[str, Any]) -> list[str]:
    fa = customer_match_fingerprint(a)
    fb = customer_match_fingerprint(b)
    reasons: list[str] = []
    if fa["emails"] & fb["emails"]:
        reasons.append("Matching email")
    if fa["phones"] & fb["phones"]:
        reasons.append("Matching phone")
    if fa["names"] & fb["names"]:
        reasons.append("Matching customer or company name")
    if fa["addresses"] & fb["addresses"]:
        reasons.append("Matching address")
    return reasons


async def duplicate_candidates(*, tenant_id: str, customer_id: Optional[str] = None, search: Optional[str] = None) -> list[dict[str, Any]]:
    base_filter: dict[str, Any] = {"tenant_id": tenant_id, "merged_into": {"$exists": False}}
    target: Optional[dict[str, Any]] = None
    if customer_id:
        target = await db.customers.find_one({"tenant_id": tenant_id, "id": customer_id}, {"_id": 0})
        if not target:
            raise HTTPException(status_code=404, detail="Customer not found")
        base_filter["id"] = {"$ne": customer_id}
    docs = [doc async for doc in db.customers.find(base_filter, {"_id": 0}).limit(500)]
    if search and not target:
        needle = normalize_text(search)
        docs = [doc for doc in docs if needle in normalize_text(" ".join([
            str(doc.get("name") or ""), str(doc.get("company") or ""), str(doc.get("email") or ""), str(doc.get("phone") or "")
        ]))]
    candidates = []
    compare_docs = [target] if target else docs
    for doc in docs:
        reasons: list[str] = []
        for compare in compare_docs:
            if not compare or compare.get("id") == doc.get("id"):
                continue
            reasons = sorted(set(reasons + match_reasons(compare, doc)))
        if reasons:
            candidates.append({"customer": serialize_customer(doc), "match_reasons": reasons})
    return candidates


async def related_records(*, tenant_id: str, customer_id: str) -> dict[str, list[dict[str, Any]]]:
    customer = await db.customers.find_one({"id": customer_id, "tenant_id": tenant_id}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    async def _all(coll: str, q: dict[str, Any], url_prefix: Optional[str] = None):
        rows = [serialize_doc(d) async for d in db[coll].find(q, {"_id": 0}).sort("created_at", -1).limit(200)]
        if url_prefix:
            for row in rows:
                row["source_url"] = f"{url_prefix}/{row['id']}"
        return rows

    attachments = await _all("attachments", {"tenant_id": tenant_id, "parent_type": "customer", "parent_id": customer_id})
    files = []
    if attachments:
        file_ids = [item["file_id"] for item in attachments if item.get("file_id")]
        files = await _all("files", {"tenant_id": tenant_id, "id": {"$in": file_ids}}, "/files")
    documents = await _all("documents", {"tenant_id": tenant_id, "customer_id": customer_id}, "/documents")
    approvals = []
    for approval in await _all("approvals", {"tenant_id": tenant_id, "snapshot.customer_id": customer_id}):
        approval["source_url"] = "/approval-center"
        approvals.append(approval)

    return {
        "quotes": await _all("quotes", {"tenant_id": tenant_id, "customer_id": customer_id}, "/quotes"),
        "orders": await _all("orders", {"tenant_id": tenant_id, "customer_id": customer_id}, "/orders"),
        "work_orders": await _all("work_orders", {"tenant_id": tenant_id, "customer_id": customer_id}, "/work-orders"),
        "invoices": await _all("invoices", {"tenant_id": tenant_id, "customer_id": customer_id}, "/invoices"),
        "payments": await _all("payments", {"tenant_id": tenant_id, "customer_id": customer_id}, "/payments"),
        "files": files,
        "attachments": attachments,
        "documents": documents,
        "proofs": await _all("proofs", {"tenant_id": tenant_id, "customer_id": customer_id}, "/proofs"),
        "emails": await _all("email_logs", {"tenant_id": tenant_id, "customer_id": customer_id}),
        "communication_threads": await _all("message_threads", {"tenant_id": tenant_id, "customer_id": customer_id}, "/communications"),
        "internal_notes": await _all("internal_notes", {"tenant_id": tenant_id, "customer_id": customer_id}, "/communications"),
        "schedule_events": await _all("calendar_events", {"tenant_id": tenant_id, "customer_id": customer_id}, "/shop-schedule"),
        "portal_identities": await _all("portal_identities", {"tenant_id": tenant_id, "customer_id": customer_id}, "/portal-identities"),
        "quote_requests": await _all("quote_requests", {"tenant_id": tenant_id, "customer_id": customer_id}, "/intake"),
        "customer_intakes": await _all("customer_intakes", {"tenant_id": tenant_id, "customer_id": customer_id}, "/intake"),
        "approvals": approvals,
        "decision_rooms": await _all("decision_rooms", {"tenant_id": tenant_id, "customer_id": customer_id}, "/decision-rooms"),
        "webstores": await _all("webstores", {"tenant_id": tenant_id, "customer_id": customer_id}, "/webstores"),
        "tax_exemptions": await _all("tax_exemptions", {"tenant_id": tenant_id, "customer_id": customer_id}, "/taxes"),
        "tasks": await _all("tasks", {"tenant_id": tenant_id, "customer_id": customer_id}, "/team/tasks"),
    }


async def merge_customers(
    *,
    tenant_id: str,
    actor_user_id: str,
    actor_email: str,
    source_customer_id: str,
    surviving_customer_id: str,
    confirmation: str,
) -> dict[str, Any]:
    if source_customer_id == surviving_customer_id:
        raise HTTPException(status_code=400, detail="Choose two different customers to merge")
    if confirmation != "MERGE":
        raise HTTPException(status_code=400, detail="Type MERGE to confirm customer merge")

    source = await db.customers.find_one({"tenant_id": tenant_id, "id": source_customer_id}, {"_id": 0})
    survivor = await db.customers.find_one({"tenant_id": tenant_id, "id": surviving_customer_id}, {"_id": 0})
    if not source or not survivor:
        raise HTTPException(status_code=404, detail="Customer not found")
    if source.get("merged_into"):
        raise HTTPException(status_code=400, detail="Source customer has already been merged")
    if survivor.get("merged_into"):
        raise HTTPException(status_code=400, detail="Surviving customer cannot already be merged")

    counts: dict[str, int] = {}
    for coll in RELATED_CUSTOMER_COLLECTIONS:
        res = await db[coll].update_many({"tenant_id": tenant_id, "customer_id": source_customer_id}, {"$set": {"customer_id": surviving_customer_id, "updated_at": utc_now().isoformat()}})
        if res.modified_count:
            counts[coll] = res.modified_count

    for coll in ATTACHMENT_PARENT_COLLECTIONS:
        res = await db[coll].update_many(
            {"tenant_id": tenant_id, "parent_type": "customer", "parent_id": source_customer_id},
            {"$set": {"parent_id": surviving_customer_id, "updated_at": utc_now().isoformat()}},
        )
        if res.modified_count:
            counts[coll] = res.modified_count

    for coll in DOCUMENT_LINK_COLLECTIONS:
        res = await db[coll].update_many(
            {"tenant_id": tenant_id, "entity_type": "customer", "entity_id": source_customer_id},
            {"$set": {"entity_id": surviving_customer_id, "updated_at": utc_now().isoformat()}},
        )
        if res.modified_count:
            counts[coll] = res.modified_count

    for coll in ("webstore_orders", "webstore_quote_requests"):
        res = await db[coll].update_many(
            {"tenant_id": tenant_id, "canonical_customer_id": source_customer_id},
            {"$set": {"canonical_customer_id": surviving_customer_id, "updated_at": utc_now().isoformat()}},
        )
        if res.modified_count:
            counts[coll] = res.modified_count

    now = utc_now().isoformat()
    merge_entry = {
        "source_customer_id": source_customer_id,
        "surviving_customer_id": surviving_customer_id,
        "merged_at": now,
        "actor_user_id": actor_user_id,
        "affected_record_counts": counts,
        "match_reasons": match_reasons(source, survivor),
    }
    await db.customers.update_one(
        {"tenant_id": tenant_id, "id": source_customer_id},
        {"$set": {
            "archived": True,
            "archived_at": now,
            "lifecycle_status": "merged",
            "merged_into": surviving_customer_id,
            "merged_at": now,
            "updated_at": now,
        }, "$push": {"merge_history": merge_entry}},
    )
    await db.customers.update_one(
        {"tenant_id": tenant_id, "id": surviving_customer_id},
        {"$push": {"merge_history": merge_entry}, "$set": {"updated_at": now}},
    )
    await record_audit(
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        action="customer.merge",
        entity_type="customer",
        entity_id=surviving_customer_id,
        summary=f"Merged customer {source_customer_id} into {surviving_customer_id}",
        diff=merge_entry,
    )
    await record_audit(
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        action="customer.merged_into",
        entity_type="customer",
        entity_id=source_customer_id,
        summary=f"Customer merged into {surviving_customer_id}",
        diff=merge_entry,
    )
    source_after = await db.customers.find_one({"tenant_id": tenant_id, "id": source_customer_id}, {"_id": 0})
    survivor_after = await db.customers.find_one({"tenant_id": tenant_id, "id": surviving_customer_id}, {"_id": 0})
    return {
        "source": serialize_customer(source_after),
        "survivor": serialize_customer(survivor_after),
        "affected_record_counts": counts,
        "match_reasons": merge_entry["match_reasons"],
    }


def mongo_customer_payload(data: dict[str, Any], existing: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    normalized = apply_customer_compatibility(data, existing)
    return prepare_for_mongo(normalized)
