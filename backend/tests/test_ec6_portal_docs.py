"""EC6 — end-to-end backend tests: portal auth separation, tokens, docs, proofs, approvals, cross-tenant."""
from __future__ import annotations

import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from server import app
from app.core.db import db
from app.deps import get_current_user
from app.core.security import create_access_token
from app.core.portal_security import create_portal_token
from app.services.portal_identity import create_portal_identity


def _override(u):
    async def _get():
        return {**u}
    return _get


async def _client_staff(u):
    app.dependency_overrides[get_current_user] = _override(u)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear_deps():
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
async def seeded_users_ec6():
    ta = f"t-a-{uuid.uuid4().hex[:6]}"
    tb = f"t-b-{uuid.uuid4().hex[:6]}"
    ua = {"id": f"u-a-{uuid.uuid4().hex[:6]}", "tenant_id": ta, "email": f"owner-a-{uuid.uuid4().hex[:4]}@example.com", "role": "owner", "is_active": True}
    ub = {"id": f"u-b-{uuid.uuid4().hex[:6]}", "tenant_id": tb, "email": f"owner-b-{uuid.uuid4().hex[:4]}@example.com", "role": "owner", "is_active": True}
    # Insert users into DB so /auth/me-like flows work if needed
    await db.tenants.insert_one({"id": ta, "slug": ta, "name": "TA"})
    await db.tenants.insert_one({"id": tb, "slug": tb, "name": "TB"})
    await db.users.insert_one({**ua})
    await db.users.insert_one({**ub})
    ca = {"id": f"c-a-{uuid.uuid4().hex[:6]}", "tenant_id": ta, "name": "Cust A", "email": "custa@example.com"}
    cb = {"id": f"c-b-{uuid.uuid4().hex[:6]}", "tenant_id": tb, "name": "Cust B", "email": "custb@example.com"}
    await db.customers.insert_one({**ca})
    await db.customers.insert_one({**cb})
    yield {"user_a": ua, "user_b": ub, "customer_a": ca, "customer_b": cb, "tenant_a": ta, "tenant_b": tb}


@pytest.mark.asyncio
async def test_portal_identity_create_and_permission_preset(seeded_users_ec6):
    u = seeded_users_ec6["user_a"]
    ca = seeded_users_ec6["customer_a"]
    async with await _client_staff(u) as c:
        r = await c.post("/api/portal-identities", json={
            "customer_id": ca["id"], "email": f"portal-{uuid.uuid4().hex[:5]}@example.com",
            "full_name": "Owner", "permissions_preset": "owner_full",
            "send_invite_email": False,
        })
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["customer_id"] == ca["id"]
        assert "portal:approve_proofs" in body["permissions"]
        assert body["magic_link_only"] is True
    _clear_deps()


@pytest.mark.asyncio
async def test_staff_route_rejects_portal_token(seeded_users_ec6):
    tid = seeded_users_ec6["tenant_a"]
    cid = seeded_users_ec6["customer_a"]["id"]
    portal_tok = create_portal_token(portal_identity_id="pi-fake", tenant_id=tid, customer_id=cid)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/customers", headers={"Authorization": f"Bearer {portal_tok}"})
        assert r.status_code == 401
        assert "Portal token not allowed" in r.json()["detail"]


@pytest.mark.asyncio
async def test_portal_route_rejects_staff_token(seeded_users_ec6):
    u = seeded_users_ec6["user_a"]
    staff_tok = create_access_token(subject=u["id"], tenant_id=u["tenant_id"])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/portal/auth/me", headers={"Authorization": f"Bearer {staff_tok}"})
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_portal_customer_scope(seeded_users_ec6):
    # Create a portal identity for Customer A, then confirm it cannot access Customer B data.
    ca = seeded_users_ec6["customer_a"]
    cb = seeded_users_ec6["customer_b"]
    tid = seeded_users_ec6["tenant_a"]
    identity = await create_portal_identity(
        tenant_id=tid, customer_id=ca["id"],
        email=f"pi-{uuid.uuid4().hex[:6]}@example.com",
        permissions_preset="owner_full", magic_link_only=True,
    )
    token = create_portal_token(portal_identity_id=identity["id"], tenant_id=tid, customer_id=ca["id"])
    # Seed a customer-B quote in tenant A (unusual but tests scoping)
    other_customer_quote = {"id": f"q-{uuid.uuid4().hex[:6]}", "tenant_id": tid, "customer_id": cb["id"],
                            "status": "sent", "number": 1, "total_cents": 1000, "created_at": "2026-02-01T00:00:00+00:00"}
    my_customer_quote = {"id": f"q-{uuid.uuid4().hex[:6]}", "tenant_id": tid, "customer_id": ca["id"],
                         "status": "sent", "number": 2, "total_cents": 2000, "created_at": "2026-02-01T00:00:00+00:00"}
    await db.quotes.insert_many([other_customer_quote, my_customer_quote])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/portal/quotes", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        ids = [q["id"] for q in r.json()["items"]]
        assert my_customer_quote["id"] in ids
        assert other_customer_quote["id"] not in ids
        # Detail lookup on other-customer quote → 404
        r2 = await c.get(f"/api/portal/quotes/{other_customer_quote['id']}",
                         headers={"Authorization": f"Bearer {token}"})
        assert r2.status_code == 404


@pytest.mark.asyncio
async def test_public_action_token_full_lifecycle(seeded_users_ec6):
    u = seeded_users_ec6["user_a"]
    ca = seeded_users_ec6["customer_a"]
    tid = u["tenant_id"]
    # Create a proof to approve
    proof_id = f"pf-{uuid.uuid4().hex[:6]}"
    await db.proofs.insert_one({
        "id": proof_id, "tenant_id": tid, "number": 1,
        "parent_type": "order", "parent_id": "o-x", "customer_id": ca["id"],
        "title": "Proof", "status": "sent", "current_version": 1,
    })
    # Staff mints a proof_approve token
    async with await _client_staff(u) as c:
        # We first need a document to hang share on; skip and mint via portal_tokens direct
        pass
    _clear_deps()
    from app.services.portal_tokens import mint_public_action_token
    raw, _tok = await mint_public_action_token(
        tenant_id=tid, action="proof_approve", parent_type="proof",
        parent_id=proof_id, parent_version=1, ttl_hours=1, single_use=True,
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # Introspect works
        r = await c.get("/api/public/token/introspect", params={"t": raw})
        assert r.status_code == 200
        assert r.json()["action"] == "proof_approve"
        # Approve
        r2 = await c.post(f"/api/public/proofs/{proof_id}/action",
                          params={"t": raw}, json={"action": "approve", "signer_name": "Test"})
        assert r2.status_code == 201, r2.text
        # Reuse rejected
        r3 = await c.post(f"/api/public/proofs/{proof_id}/action",
                          params={"t": raw}, json={"action": "approve"})
        assert r3.status_code == 410


@pytest.mark.asyncio
async def test_public_action_token_action_mismatch(seeded_users_ec6):
    u = seeded_users_ec6["user_a"]
    tid = u["tenant_id"]
    inv_id = f"inv-{uuid.uuid4().hex[:6]}"
    await db.invoices.insert_one({
        "id": inv_id, "tenant_id": tid, "customer_id": seeded_users_ec6["customer_a"]["id"],
        "number": 1, "document_status": "issued", "financial_status": "unpaid", "total_cents": 1000,
    })
    from app.services.portal_tokens import mint_public_action_token
    raw, _ = await mint_public_action_token(
        tenant_id=tid, action="invoice_view", parent_type="invoice",
        parent_id=inv_id, ttl_hours=1, single_use=False,
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # Correct action → OK
        r = await c.get(f"/api/public/invoices/{inv_id}", params={"t": raw})
        assert r.status_code == 200
        # Wrong parent → 403
        r2 = await c.get("/api/public/quotes/notaquote", params={"t": raw})
        assert r2.status_code == 403


@pytest.mark.asyncio
async def test_approval_writes_and_dual_parent(seeded_users_ec6):
    from app.services.approvals_signatures_service import record_approval
    u = seeded_users_ec6["user_a"]
    r = await record_approval(
        tenant_id=u["tenant_id"], parent_type="work_order_summary",
        parent_id=f"wo-{uuid.uuid4().hex[:5]}", action="approve",
        actor_type="staff", actor_ref=u["id"], actor_display=u["email"],
    )
    assert r["parent_type"] == "work_order_summary"
    assert r["action"] == "approve"


@pytest.mark.asyncio
async def test_cross_tenant_ec6(seeded_users_ec6):
    """Portal identity in tenant A must not read tenant B data."""
    ca = seeded_users_ec6["customer_a"]
    ta = seeded_users_ec6["tenant_a"]
    tb = seeded_users_ec6["tenant_b"]
    identity_a = await create_portal_identity(
        tenant_id=ta, customer_id=ca["id"],
        email=f"pi-{uuid.uuid4().hex[:6]}@example.com",
        permissions_preset="owner_full",
    )
    token_a = create_portal_token(portal_identity_id=identity_a["id"], tenant_id=ta, customer_id=ca["id"])
    # Seed a Doc in tenant B
    await db.documents.insert_one({
        "id": f"d-{uuid.uuid4().hex[:6]}", "tenant_id": tb, "title": "B doc",
        "visibility": "customer_visible", "archived": False, "category": "general",
        "source_type": "upload", "customer_id": "any",
    })
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/portal/documents", headers={"Authorization": f"Bearer {token_a}"})
        assert r.status_code == 200
        assert r.json()["items"] == []


@pytest.mark.asyncio
async def test_magic_link_login_flow(seeded_users_ec6):
    ca = seeded_users_ec6["customer_a"]
    ta = seeded_users_ec6["tenant_a"]
    identity = await create_portal_identity(
        tenant_id=ta, customer_id=ca["id"],
        email=f"mlk-{uuid.uuid4().hex[:6]}@example.com",
        permissions_preset="viewer_only",
    )
    from app.services.portal_tokens import mint_magic_link_token
    raw, _ = await mint_magic_link_token(
        tenant_id=ta, portal_identity_id=identity["id"], email=identity["email"], ttl_minutes=5,
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/portal/auth/magic-link/verify", json={"token": raw})
        assert r.status_code == 200
        assert r.json()["token"]
        # Consumed → second use fails
        r2 = await c.post("/api/portal/auth/magic-link/verify", json={"token": raw})
        assert r2.status_code == 401


@pytest.mark.asyncio
async def test_document_share_token_mint_and_revoke(seeded_users_ec6):
    u = seeded_users_ec6["user_a"]
    ca = seeded_users_ec6["customer_a"]
    async with await _client_staff(u) as c:
        # Create a doc
        r = await c.post("/api/documents", json={
            "title": "Sample", "customer_id": ca["id"], "visibility": "customer_visible",
        })
        assert r.status_code == 201, r.text
        doc_id = r.json()["id"]
        # Mint a share token
        r2 = await c.post(f"/api/documents/{doc_id}/share", json={
            "action": "invoice_view", "parent_type": "invoice", "parent_id": "i-x",
            "audience_email": "test@example.com", "ttl_hours": 1,
        })
        assert r2.status_code == 201, r2.text
        assert "token" in r2.json()
        token_id = r2.json()["record"]["id"]
        # Revoke
        r3 = await c.delete(f"/api/documents/share-tokens/{token_id}")
        assert r3.status_code == 204
    _clear_deps()


@pytest.mark.asyncio
async def test_public_quote_request(seeded_users_ec6):
    ta = seeded_users_ec6["tenant_a"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/public/quote-request", json={
            "tenant_slug": ta, "contact_name": "Alice", "contact_email": "alice@example.com",
            "project_title": "3x6 Banner",
        })
        assert r.status_code == 201, r.text
        assert r.json()["status"] == "received"
        assert r.json()["reference"].startswith("QR-")
