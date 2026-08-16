from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.deps import get_current_user
from server import app


def _override(user):
    async def _get():
        return {**user}
    return _get


async def _client(user):
    app.dependency_overrides[get_current_user] = _override(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear_override():
    app.dependency_overrides.pop(get_current_user, None)


@pytest_asyncio.fixture
async def customer_ctx():
    suffix = uuid.uuid4().hex[:8]
    tenant_a = f"t-customer-a-{suffix}"
    tenant_b = f"t-customer-b-{suffix}"
    owner_a = {"id": f"owner-a-{suffix}", "tenant_id": tenant_a, "email": f"owner-a-{suffix}@example.com", "role": "owner", "is_active": True}
    owner_b = {"id": f"owner-b-{suffix}", "tenant_id": tenant_b, "email": f"owner-b-{suffix}@example.com", "role": "owner", "is_active": True}
    survivor = {"id": f"cust-survivor-{suffix}", "tenant_id": tenant_a, "name": "Rusty Lemon Boutique", "company": "Rusty Lemon", "phone": "(724) 555-0191", "archived": False}
    duplicate = {"id": f"cust-duplicate-{suffix}", "tenant_id": tenant_a, "name": "Rusty Lemon", "company": "Rusty Lemon Boutique", "phone": "7245550191", "address_line1": "10 Main St", "city": "Connellsville", "state": "PA", "postal_code": "15425", "archived": False}
    other_tenant = {"id": f"cust-other-{suffix}", "tenant_id": tenant_b, "name": "Rusty Lemon", "archived": False}
    quote = {"id": f"quote-{suffix}", "tenant_id": tenant_a, "number": 1001, "customer_id": duplicate["id"], "job_name": "Window decals", "status": "sent", "created_by": owner_a["id"]}
    order = {"id": f"order-{suffix}", "tenant_id": tenant_a, "number": 9001, "customer_id": duplicate["id"], "job_name": "Trailer graphics", "status": "confirmed", "created_by": owner_a["id"]}
    work_order = {"id": f"wo-{suffix}", "tenant_id": tenant_a, "number": 1042, "order_id": order["id"], "customer_id": duplicate["id"], "production_status": "queued", "created_by": owner_a["id"]}
    invoice = {"id": f"invoice-{suffix}", "tenant_id": tenant_a, "number": 5001, "order_id": order["id"], "customer_id": duplicate["id"], "title": "Invoice", "status": "sent"}
    document = {"id": f"doc-{suffix}", "tenant_id": tenant_a, "title": "Logo file", "customer_id": duplicate["id"], "category": "artwork"}
    proof = {"id": f"proof-{suffix}", "tenant_id": tenant_a, "number": 7, "title": "Window proof", "customer_id": duplicate["id"], "status": "sent"}
    thread = {"id": f"thread-{suffix}", "tenant_id": tenant_a, "thread_type": "order_discussion", "title": "Order notes", "customer_id": duplicate["id"]}
    note = {"id": f"note-{suffix}", "tenant_id": tenant_a, "body": "Install gate code", "customer_id": duplicate["id"]}
    event = {"id": f"event-{suffix}", "tenant_id": tenant_a, "title": "Install", "start_at": "2026-08-20T13:00:00+00:00", "end_at": "2026-08-20T15:00:00+00:00", "customer_id": duplicate["id"], "status": "scheduled"}
    room = {"id": f"room-{suffix}", "tenant_id": tenant_a, "title": "Approval room", "customer_id": duplicate["id"], "status": "published"}
    portal_identity = {"id": f"portal-{suffix}", "tenant_id": tenant_a, "email": "customer@example.com", "customer_id": duplicate["id"], "portal_type": "customer", "status": "active"}
    webstore = {"id": f"webstore-{suffix}", "tenant_id": tenant_a, "name": "Rusty Lemon Store", "customer_id": duplicate["id"], "status": "active"}
    await db.tenants.insert_many([
        {"id": tenant_a, "slug": tenant_a, "name": "Tenant A"},
        {"id": tenant_b, "slug": tenant_b, "name": "Tenant B"},
    ])
    await db.users.insert_many([owner_a, owner_b])
    await db.customers.insert_many([survivor, duplicate, other_tenant])
    await db.quotes.insert_one(quote)
    await db.orders.insert_one(order)
    await db.work_orders.insert_one(work_order)
    await db.invoices.insert_one(invoice)
    await db.documents.insert_one(document)
    await db.proofs.insert_one(proof)
    await db.message_threads.insert_one(thread)
    await db.internal_notes.insert_one(note)
    await db.calendar_events.insert_one(event)
    await db.decision_rooms.insert_one(room)
    await db.portal_identities.insert_one(portal_identity)
    await db.webstores.insert_one(webstore)
    yield {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "owner_a": owner_a,
        "owner_b": owner_b,
        "survivor": survivor,
        "duplicate": duplicate,
        "other_tenant": other_tenant,
        "quote": quote,
        "order": order,
        "work_order": work_order,
        "invoice": invoice,
        "document": document,
        "proof": proof,
        "thread": thread,
        "note": note,
        "event": event,
        "room": room,
        "portal_identity": portal_identity,
        "webstore": webstore,
    }
    _clear_override()


@pytest.mark.asyncio
async def test_customer_create_preserves_legacy_contact_and_address_compatibility(customer_ctx):
    async with await _client(customer_ctx["owner_a"]) as client:
        created = await client.post("/api/customers", json={
            "name": "Party Squad Rentals",
            "company": "Party Squad",
            "customer_type": "business",
            "lifecycle_status": "lead",
            "contacts": [
                {"name": "Nicole Harris", "email": "nicole@example.com", "phone": "724-555-0101", "role": "primary", "is_primary": True},
                {"name": "Accounts Payable", "email": "ap@example.com", "role": "billing"},
            ],
            "addresses": [
                {"label": "Shop", "line1": "20 River Rd", "city": "Connellsville", "state": "PA", "postal_code": "15425", "purposes": ["billing"], "is_default": True}
            ],
        })
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["customer_type"] == "business"
    assert body["lifecycle_status"] == "lead"
    assert body["email"] == "nicole@example.com"
    assert body["address_line1"] == "20 River Rd"
    assert len(body["contacts"]) == 2
    assert body["contacts"][0]["is_primary"] is True


@pytest.mark.asyncio
async def test_customer_duplicates_merge_relinks_records_and_blocks_repeated_or_cross_tenant_merge(customer_ctx):
    async with await _client(customer_ctx["owner_a"]) as client:
        candidates = await client.get("/api/customers/duplicates", params={"customer_id": customer_ctx["survivor"]["id"]})
        assert candidates.status_code == 200, candidates.text
        assert candidates.json()["items"][0]["customer"]["id"] == customer_ctx["duplicate"]["id"]
        assert "Matching phone" in candidates.json()["items"][0]["match_reasons"]

        merged = await client.post("/api/customers/merge", json={
            "source_customer_id": customer_ctx["duplicate"]["id"],
            "surviving_customer_id": customer_ctx["survivor"]["id"],
            "confirmation": "MERGE",
        })
        assert merged.status_code == 200, merged.text
        counts = merged.json()["affected_record_counts"]
        assert counts["quotes"] == 1
        assert counts["orders"] == 1
        assert counts["documents"] == 1
        assert counts["proofs"] == 1
        repeated = await client.post("/api/customers/merge", json={
            "source_customer_id": customer_ctx["duplicate"]["id"],
            "surviving_customer_id": customer_ctx["survivor"]["id"],
            "confirmation": "MERGE",
        })
        assert repeated.status_code == 400

    quote = await db.quotes.find_one({"id": customer_ctx["quote"]["id"]}, {"_id": 0})
    source = await db.customers.find_one({"id": customer_ctx["duplicate"]["id"]}, {"_id": 0})
    audit = await db.audit_events.find_one({"entity_id": customer_ctx["survivor"]["id"], "action": "customer.merge"}, {"_id": 0})
    assert quote["customer_id"] == customer_ctx["survivor"]["id"]
    assert source["archived"] is True
    assert source["merged_into"] == customer_ctx["survivor"]["id"]
    assert audit["diff"]["affected_record_counts"]["calendar_events"] == 1

    async with await _client(customer_ctx["owner_b"]) as client:
        denied = await client.post("/api/customers/merge", json={
            "source_customer_id": customer_ctx["survivor"]["id"],
            "surviving_customer_id": customer_ctx["other_tenant"]["id"],
            "confirmation": "MERGE",
        })
    assert denied.status_code == 404


@pytest.mark.asyncio
async def test_customer_archive_restore_filters_and_related_coverage(customer_ctx):
    async with await _client(customer_ctx["owner_a"]) as client:
        archived = await client.post(f"/api/customers/{customer_ctx['survivor']['id']}/archive", json={"reason": "Closed account"})
        assert archived.status_code == 200, archived.text
        active = await client.get("/api/customers", params={"status": "active"})
        assert customer_ctx["survivor"]["id"] not in [item["id"] for item in active.json()["items"]]
        archived_list = await client.get("/api/customers", params={"status": "archived"})
        assert customer_ctx["survivor"]["id"] in [item["id"] for item in archived_list.json()["items"]]
        restored = await client.post(f"/api/customers/{customer_ctx['survivor']['id']}/restore", json={})
        assert restored.status_code == 200, restored.text
        assert restored.json()["archived"] is False

        related = await client.get(f"/api/customers/{customer_ctx['duplicate']['id']}/related")
        assert related.status_code == 200, related.text
        body = related.json()
        assert body["quotes"][0]["source_url"] == f"/quotes/{customer_ctx['quote']['id']}"
        assert body["documents"][0]["source_url"] == f"/documents/{customer_ctx['document']['id']}"
        assert body["proofs"][0]["source_url"] == f"/proofs/{customer_ctx['proof']['id']}"
        assert body["communication_threads"][0]["source_url"] == f"/communications/{customer_ctx['thread']['id']}"
        assert body["schedule_events"][0]["source_url"] == f"/shop-schedule/{customer_ctx['event']['id']}"
        assert body["decision_rooms"][0]["source_url"] == f"/decision-rooms/{customer_ctx['room']['id']}"
        assert body["portal_identities"][0]["source_url"] == f"/portal-identities/{customer_ctx['portal_identity']['id']}"
        assert body["webstores"][0]["source_url"] == f"/webstores/{customer_ctx['webstore']['id']}"
