"""EC3 — Quote line items, revisions, conversion, tenant isolation.

Uses direct FastAPI dependency overrides to exercise the router in-process
against the real MongoDB used by other tests, seeded via `seeded_users`.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from server import app
from app.core.db import db as _db
from app.deps import get_current_user


def _override_as(user: dict):
    async def _dep():
        return user
    return _dep


async def _seed_customer(tenant_id: str) -> str:
    cust_id = f"cust-{uuid.uuid4().hex[:8]}"
    await _db.customers.insert_one({
        "id": cust_id,
        "tenant_id": tenant_id,
        "name": f"Test {cust_id}",
        "email": "c@example.com",
    })
    return cust_id


async def _client_as(user: dict) -> AsyncClient:
    app.dependency_overrides[get_current_user] = _override_as(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear_overrides():
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_quote_line_items_backend_derived_totals(seeded_users):
    user = seeded_users["user_a"]
    cust_id = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        r = await c.post("/api/quotes", json={
            "customer_id": cust_id,
            "job_name": "Sign package",
        })
        assert r.status_code == 201, r.text
        quote = r.json()
        qid = quote["id"]

        # Add two line items
        r = await c.post(f"/api/quotes/{qid}/line-items", json={
            "description": "Banner 3x6",
            "quantity": 2,
            "unit_price_cents": 5000,
            "category": "banners",
        })
        assert r.status_code == 201
        r = await c.post(f"/api/quotes/{qid}/line-items", json={
            "description": "Design fee",
            "quantity": 1,
            "unit_price_cents": 7500,
            "discount_cents": 500,
            "category": "services",
        })
        assert r.status_code == 201

        r = await c.get(f"/api/quotes/{qid}")
        assert r.status_code == 200
        body = r.json()
        assert body["totals"]["subtotal_cents"] == 2 * 5000 + 7500
        assert body["totals"]["discount_cents"] == 500
        assert body["totals"]["total_cents"] == 2 * 5000 + 7500 - 500
        assert body["quote"]["total_cents"] == body["totals"]["total_cents"]
    _clear_overrides()


@pytest.mark.asyncio
async def test_quote_create_and_update_ignore_client_supplied_document_totals(seeded_users):
    user = seeded_users["user_a"]
    cust_id = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        r = await c.post("/api/quotes", json={
            "customer_id": cust_id,
            "job_name": "Totals ignored",
            "total_cents": 999999,
        })
        assert r.status_code == 201, r.text
        quote = r.json()
        assert quote["total_cents"] == 0
        assert quote["subtotal_cents"] == 0

        r = await c.patch(f"/api/quotes/{quote['id']}", json={
            "notes": "Only notes should change",
            "total_cents": 123456,
        })
        assert r.status_code == 200, r.text
        assert r.json()["notes"] == "Only notes should change"
        assert r.json()["total_cents"] == 0

        r = await c.patch(f"/api/quotes/{quote['id']}", json={"total_cents": 111})
        assert r.status_code == 400
        assert r.json()["detail"] == "No updates"
    _clear_overrides()


@pytest.mark.asyncio
async def test_sent_quote_edit_creates_revision(seeded_users):
    user = seeded_users["user_a"]
    cust_id = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        r = await c.post("/api/quotes", json={"customer_id": cust_id, "job_name": "Wrap"})
        qid = r.json()["id"]
        r = await c.post(f"/api/quotes/{qid}/line-items", json={
            "description": "Banner", "quantity": 1, "unit_price_cents": 10000,
            "category": "banners",
        })
        # send it
        r = await c.post(f"/api/quotes/{qid}/status", json={"status": "sent"})
        assert r.status_code == 200
        assert r.json()["status"] == "sent"

        # Edit the price → should force a revision
        r = await c.post(f"/api/quotes/{qid}/line-items", json={
            "description": "Extra banner", "quantity": 1, "unit_price_cents": 12000,
            "category": "banners",
        })
        assert r.status_code == 201

        # New quote revision should be 2
        r = await c.get(f"/api/quotes/{qid}")
        assert r.json()["quote"]["revision_number"] == 2

        r = await c.get(f"/api/quotes/{qid}/revisions")
        assert r.status_code == 200
        revs = r.json()["items"]
        assert len(revs) == 1
        assert revs[0]["revision_number"] == 1
        assert revs[0]["job_name"] == "Wrap"
    _clear_overrides()


@pytest.mark.asyncio
async def test_expired_quote_conversion_blocked_and_overridable(seeded_users):
    user = seeded_users["user_a"]
    cust_id = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        r = await c.post("/api/quotes", json={
            "customer_id": cust_id,
            "job_name": "Wrap",
            "expires_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        })
        qid = r.json()["id"]
        r = await c.post(f"/api/quotes/{qid}/status", json={"status": "sent"})
        assert r.status_code == 200

        # Without override → rejected
        r = await c.post(f"/api/quotes/{qid}/convert-to-order", json={})
        assert r.status_code == 400
        assert "expired" in r.json()["detail"].lower()

        # With override but no reason → 400
        r = await c.post(f"/api/quotes/{qid}/convert-to-order", json={"allow_expired": True})
        assert r.status_code == 400

        # With override + reason → success
        r = await c.post(f"/api/quotes/{qid}/convert-to-order", json={
            "allow_expired": True, "override_reason": "customer approved verbally",
        })
        assert r.status_code == 200
        assert r.json()["order"]["id"]
    _clear_overrides()


@pytest.mark.asyncio
async def test_convert_idempotent_and_copies_items(seeded_users):
    user = seeded_users["user_a"]
    cust_id = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        r = await c.post("/api/quotes", json={"customer_id": cust_id, "job_name": "Sign"})
        qid = r.json()["id"]
        for _ in range(2):
            await c.post(f"/api/quotes/{qid}/line-items", json={
                "description": "Item", "quantity": 1, "unit_price_cents": 2500, "category": "banners",
            })

        r1 = await c.post(f"/api/quotes/{qid}/convert-to-order", json={})
        assert r1.status_code == 200
        order_id = r1.json()["order"]["id"]
        assert r1.json()["already_converted"] is False

        r2 = await c.post(f"/api/quotes/{qid}/convert-to-order", json={})
        assert r2.status_code == 200
        assert r2.json()["already_converted"] is True
        assert r2.json()["order"]["id"] == order_id

        # Order items copied
        r = await c.get(f"/api/orders/{order_id}")
        body = r.json()
        assert len(body["items"]) == 2
        assert body["order"]["source_quote_id"] == qid
        assert body["order"]["source_quote_revision"] == 1
        assert body["totals"]["subtotal_cents"] == 5000
    _clear_overrides()


@pytest.mark.asyncio
async def test_conversion_failure_leaves_quote_retryable_and_cleans_candidate(seeded_users, monkeypatch):
    user = seeded_users["user_a"]
    cust_id = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        r = await c.post("/api/quotes", json={"customer_id": cust_id, "job_name": "Retryable"})
        qid = r.json()["id"]
        await c.post(f"/api/quotes/{qid}/line-items", json={
            "description": "Item", "quantity": 1, "unit_price_cents": 2500, "category": "banners",
        })

        from app.services import quote_conversion

        async def fail_snapshot(*args, **kwargs):
            raise RuntimeError("forced snapshot failure")

        monkeypatch.setattr(quote_conversion, "create_snapshot_record", fail_snapshot)

        with pytest.raises(RuntimeError, match="forced snapshot failure"):
            await quote_conversion.convert_quote_to_order(
                tenant_id=user["tenant_id"],
                quote_id=qid,
                actor_user_id=user["id"],
                actor_email=user["email"],
            )

        quote = await _db.quotes.find_one({"tenant_id": user["tenant_id"], "id": qid}, {"_id": 0})
        assert quote["status"] == "draft"
        assert quote.get("converted_order_id") is None
        assert await _db.orders.count_documents({"tenant_id": user["tenant_id"], "source_quote_id": qid}) == 0
    _clear_overrides()


@pytest.mark.asyncio
async def test_declined_quote_cannot_convert(seeded_users):
    user = seeded_users["user_a"]
    cust_id = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        r = await c.post("/api/quotes", json={"customer_id": cust_id, "job_name": "X"})
        qid = r.json()["id"]
        await c.post(f"/api/quotes/{qid}/status", json={"status": "sent"})
        await c.post(f"/api/quotes/{qid}/status", json={"status": "declined", "reason": "no budget"})
        r = await c.post(f"/api/quotes/{qid}/convert-to-order", json={})
        assert r.status_code == 400
        assert "declined" in r.json()["detail"].lower()
    _clear_overrides()


@pytest.mark.asyncio
async def test_tenant_isolation_on_quotes(seeded_users):
    user_a = seeded_users["user_a"]
    user_b = seeded_users["user_b"]
    cust_id = await _seed_customer(user_a["tenant_id"])
    async with await _client_as(user_a) as ca:
        r = await ca.post("/api/quotes", json={"customer_id": cust_id, "job_name": "T"})
        qid = r.json()["id"]
    _clear_overrides()

    async with await _client_as(user_b) as cb:
        r = await cb.get(f"/api/quotes/{qid}")
        assert r.status_code == 404
        r = await cb.post(f"/api/quotes/{qid}/convert-to-order", json={})
        assert r.status_code == 404
    _clear_overrides()


@pytest.mark.asyncio
async def test_quote_share_public_preview_and_customer_approval_use_canonical_approval(seeded_users):
    user = seeded_users["user_a"]
    cust_id = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        created = await c.post("/api/quotes", json={
            "customer_id": cust_id,
            "job_name": "Customer approval",
            "notes_internal": "staff only",
            "notes_customer": "Please review this quote.",
        })
        assert created.status_code == 201, created.text
        qid = created.json()["id"]
        line = await c.post(f"/api/quotes/{qid}/line-items", json={
            "description": "Window decal",
            "quantity": 2,
            "unit_price_cents": 12500,
            "category": "decals",
            "manual_override_reason": "Internal pricing note",
        })
        assert line.status_code == 201, line.text

        shared = await c.post(f"/api/quotes/{qid}/share", json={"audience_email": "customer@example.com"})
        assert shared.status_code == 201, shared.text
        share_body = shared.json()
        assert share_body["token"]
        assert share_body["delivery_status"] == "manual_link_ready"
        assert "token_hash" not in share_body["record"]
        assert share_body["record"]["parent_version"] == 1

    _clear_overrides()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as public:
        preview = await public.get(f"/api/public/quotes/{qid}", params={"t": share_body["token"]})
        assert preview.status_code == 200, preview.text
        body = preview.json()
        assert body["quote"]["status"] == "viewed"
        assert body["quote"]["revision_number"] == 1
        assert "notes_internal" not in body["quote"]
        assert "manual_override_reason" not in body["line_items"][0]
        assert body["line_items"][0]["line_total_cents"] == 25000

        approved = await public.post(f"/api/public/quotes/{qid}/approval", params={"t": share_body["token"]}, json={
            "action": "approve",
            "signer_name": "Customer Person",
            "comment": "Looks good.",
        })
        assert approved.status_code == 201, approved.text
        assert approved.json()["quote"]["status"] == "approved"

    approval = await _db.approvals.find_one({
        "tenant_id": user["tenant_id"],
        "parent_type": "quote_revision",
        "parent_id": qid,
        "action": "approve",
    }, {"_id": 0})
    assert approval
    assert approval["actor_type"] == "public_token"
    assert approval["snapshot"]["customer_comment"] == "Looks good."
    quote = await _db.quotes.find_one({"tenant_id": user["tenant_id"], "id": qid}, {"_id": 0})
    assert quote["approved_approval_id"] == approval["id"]
    assert quote["approved_source"] == "public_token"


@pytest.mark.asyncio
async def test_public_quote_approval_rejects_stale_published_revision(seeded_users):
    user = seeded_users["user_a"]
    cust_id = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        created = await c.post("/api/quotes", json={"customer_id": cust_id, "job_name": "Revision lock"})
        qid = created.json()["id"]
        await c.post(f"/api/quotes/{qid}/line-items", json={
            "description": "Banner", "quantity": 1, "unit_price_cents": 10000, "category": "banners",
        })
        shared = await c.post(f"/api/quotes/{qid}/share", json={})
        token = shared.json()["token"]
        edited = await c.patch(f"/api/quotes/{qid}", json={"job_name": "Revision lock updated"})
        assert edited.status_code == 200, edited.text
        assert edited.json()["revision_number"] == 2
    _clear_overrides()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as public:
        approved = await public.post(f"/api/public/quotes/{qid}/approval", params={"t": token}, json={"action": "approve"})
        assert approved.status_code == 409
        assert approved.json()["detail"] == "Quote revision is no longer current"


@pytest.mark.asyncio
async def test_staff_quote_override_requires_reason_and_records_audit(seeded_users):
    user = seeded_users["user_a"]
    cust_id = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        created = await c.post("/api/quotes", json={"customer_id": cust_id, "job_name": "Override"})
        qid = created.json()["id"]
        await c.post(f"/api/quotes/{qid}/status", json={"status": "sent"})

        missing_reason = await c.post(f"/api/quotes/{qid}/staff-approval", json={"action": "approve"})
        assert missing_reason.status_code == 422

        approved = await c.post(f"/api/quotes/{qid}/staff-approval", json={
            "action": "approve",
            "reason": "Customer approved by phone",
            "comment": "Called at 2 PM",
        })
        assert approved.status_code == 200, approved.text
        assert approved.json()["quote"]["status"] == "approved"
    _clear_overrides()

    approval = await _db.approvals.find_one({
        "tenant_id": user["tenant_id"],
        "parent_type": "quote_revision",
        "parent_id": qid,
        "action": "approve",
    }, {"_id": 0})
    assert approval["reason"] == "Customer approved by phone"
    assert approval["snapshot"]["source"] == "staff_override"
    audit = await _db.audit_events.find_one({
        "tenant_id": user["tenant_id"],
        "entity_type": "quote",
        "entity_id": qid,
        "action": "quote.approved",
    }, {"_id": 0})
    assert audit


@pytest.mark.asyncio
async def test_quote_assets_artifact_and_timeline_are_source_backed(seeded_users):
    user = seeded_users["user_a"]
    cust_id = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as c:
        created = await c.post("/api/quotes", json={"customer_id": cust_id, "job_name": "Source backed"})
        qid = created.json()["id"]
        await c.post(f"/api/quotes/{qid}/line-items", json={
            "description": "Panel", "quantity": 1, "unit_price_cents": 5500, "category": "signs",
        })
        await _db.files.insert_one({
            "id": f"file-{uuid.uuid4().hex}",
            "tenant_id": user["tenant_id"],
            "storage_key": f"/tenants/{user['tenant_id']}/quote-art.png",
            "original_filename": "quote-art.png",
            "mime_type": "image/png",
            "size_bytes": 128,
            "visibility": "customer_visible",
            "archived": False,
        })
        file_doc = await _db.files.find_one({"tenant_id": user["tenant_id"], "original_filename": "quote-art.png"}, {"_id": 0})
        await _db.attachments.insert_one({
            "id": f"att-{uuid.uuid4().hex}",
            "tenant_id": user["tenant_id"],
            "file_id": file_doc["id"],
            "parent_type": "quote",
            "parent_id": qid,
        })
        await _db.documents.insert_one({
            "id": f"doc-{uuid.uuid4().hex}",
            "tenant_id": user["tenant_id"],
            "title": "Signed layout",
            "category": "quote",
            "source_type": "upload",
            "visibility": "customer_visible",
            "version": 1,
            "archived": False,
        })
        doc = await _db.documents.find_one({"tenant_id": user["tenant_id"], "title": "Signed layout"}, {"_id": 0})
        await _db.document_links.insert_one({
            "id": f"doc-link-{uuid.uuid4().hex}",
            "tenant_id": user["tenant_id"],
            "document_id": doc["id"],
            "entity_type": "quote",
            "entity_id": qid,
            "portal_visible": True,
        })
        await _db.proofs.insert_one({
            "id": f"proof-{uuid.uuid4().hex}",
            "tenant_id": user["tenant_id"],
            "number": 1,
            "parent_type": "quote",
            "parent_id": qid,
            "quote_id": qid,
            "customer_id": cust_id,
            "title": "Quote proof",
            "status": "sent",
        })

        assets = await c.get(f"/api/quotes/{qid}/linked-assets")
        assert assets.status_code == 200, assets.text
        assert [f["original_filename"] for f in assets.json()["files"]] == ["quote-art.png"]
        assert [d["title"] for d in assets.json()["documents"]] == ["Signed layout"]
        assert [p["title"] for p in assets.json()["proofs"]] == ["Quote proof"]

        artifact = await c.get(f"/api/quotes/{qid}/artifact")
        assert artifact.status_code == 200, artifact.text
        assert artifact.json()["artifact_type"] == "quote_printable_snapshot"
        assert artifact.json()["snapshot"]["revision_number"] == 1
        assert "Panel" in artifact.json()["content"]

        shared = await c.post(f"/api/quotes/{qid}/share", json={})
        assert shared.status_code == 201, shared.text
        timeline = await c.get(f"/api/quotes/{qid}/timeline")
        assert timeline.status_code == 200, timeline.text
        kinds = {item["kind"] for item in timeline.json()["items"]}
        assert {"created", "sent"}.issubset(kinds)
    _clear_overrides()
