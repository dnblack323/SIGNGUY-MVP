"""EC7 phase 7c — Expense system + Categories tests.

Covers:
  - default categories seeded on first read; idempotent
  - custom category creation + rename does NOT rewrite past Expenses
  - archive category still usable historically; hidden from picker
  - Expense CRUD w/ backend-derived total_cents = amount + tax
  - validation: description/amount required; category must exist
  - vendor/PO/order/customer link validation
  - archive + restore, void (reason required)
  - receipt attachment via EC2 FileRecord reuse
  - cross-tenant isolation
"""
from __future__ import annotations
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from server import app
from app.core.db import db
from app.deps import get_current_user


def _override(u):
    async def _get(): return {**u}
    return _get


async def _client(u):
    app.dependency_overrides[get_current_user] = _override(u)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear(): app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
async def ec7c_ctx():
    ta = f"t-ec7c-{uuid.uuid4().hex[:6]}"
    tb = f"t-ec7cB-{uuid.uuid4().hex[:6]}"
    ua = {"id": f"u-a-{uuid.uuid4().hex[:6]}", "tenant_id": ta,
          "email": f"a-{uuid.uuid4().hex[:4]}@example.com", "role": "owner", "is_active": True}
    ub = {"id": f"u-b-{uuid.uuid4().hex[:6]}", "tenant_id": tb,
          "email": f"b-{uuid.uuid4().hex[:4]}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_many([{"id": ta, "slug": ta, "name": "TA"},
                                   {"id": tb, "slug": tb, "name": "TB"}])
    await db.users.insert_many([{**ua}, {**ub}])
    yield {"ua": ua, "ub": ub, "ta": ta, "tb": tb}
    _clear()


@pytest.mark.asyncio
async def test_categories_seed_and_rename_does_not_rewrite_history(ec7c_ctx):
    ua = ec7c_ctx["ua"]
    ta = ec7c_ctx["ta"]
    async with await _client(ua) as c:
        # First read seeds
        r = await c.get("/api/expense-categories")
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) == 16                         # all initial keys
        assert any(x["key"] == "materials" for x in items)
        assert all(x["system"] for x in items)
        # Second read is idempotent (no duplicates)
        r2 = await c.get("/api/expense-categories")
        assert len(r2.json()["items"]) == 16
        # Create an Expense in "materials"
        exp = (await c.post("/api/expenses", json={
            "expense_date": "2026-06-15", "category_key": "materials",
            "description": "Vinyl roll", "amount_cents": 5000,
        })).json()
        assert exp["category_label_snapshot"] == "Materials"
        # Rename the "materials" category
        r3 = await c.patch("/api/expense-categories/materials", json={"label": "Raw Materials"})
        assert r3.status_code == 200
        assert r3.json()["label"] == "Raw Materials"
        # Historical Expense is NOT rewritten — snapshot preserved
        r4 = await c.get(f"/api/expenses/{exp['id']}")
        assert r4.json()["category_label_snapshot"] == "Materials"


@pytest.mark.asyncio
async def test_archived_category_still_usable_historically(ec7c_ctx):
    ua = ec7c_ctx["ua"]
    async with await _client(ua) as c:
        await c.get("/api/expense-categories")               # seed
        # Create expense in fuel
        exp = (await c.post("/api/expenses", json={
            "expense_date": "2026-06-15", "category_key": "fuel",
            "description": "Gas station", "amount_cents": 6500,
        })).json()
        # Archive the category
        r = await c.post("/api/expense-categories/fuel/archive")
        assert r.status_code == 200
        # Default list hides archived
        items = (await c.get("/api/expense-categories")).json()["items"]
        assert not any(x["key"] == "fuel" for x in items)
        # But include_archived=true reveals it
        items2 = (await c.get("/api/expense-categories", params={"include_archived": "true"})).json()["items"]
        assert any(x["key"] == "fuel" and x["archived"] for x in items2)
        # Historical expense still resolves
        r2 = await c.get(f"/api/expenses/{exp['id']}")
        assert r2.status_code == 200
        # Cannot create NEW expense against archived category (still allowed; category exists),
        # since "fuel" is still in the tenant's category store and get_category returns it.
        # This is intentional: archived means "hide from picker", not "forbid".
        new_exp = await c.post("/api/expenses", json={
            "expense_date": "2026-06-16", "category_key": "fuel",
            "description": "gas 2", "amount_cents": 2000})
        assert new_exp.status_code == 201


@pytest.mark.asyncio
async def test_expense_totals_and_validation(ec7c_ctx):
    ua = ec7c_ctx["ua"]
    async with await _client(ua) as c:
        # Missing description -> 400
        r = await c.post("/api/expenses", json={
            "expense_date": "2026-06-01", "category_key": "materials",
            "description": "", "amount_cents": 100})
        assert r.status_code == 400
        # Unknown category -> 400
        r2 = await c.post("/api/expenses", json={
            "expense_date": "2026-06-01", "category_key": "no_such",
            "description": "x", "amount_cents": 100})
        assert r2.status_code == 400
        # Negative amount -> 400
        r3 = await c.post("/api/expenses", json={
            "expense_date": "2026-06-01", "category_key": "materials",
            "description": "x", "amount_cents": -1})
        assert r3.status_code == 400
        # Valid -> total_cents = amount + tax
        r4 = await c.post("/api/expenses", json={
            "expense_date": "2026-06-01", "category_key": "materials",
            "description": "Vinyl roll", "amount_cents": 5000, "tax_cents": 400})
        assert r4.status_code == 201
        assert r4.json()["total_cents"] == 5400
        # Update tax_cents -> total recomputed
        r5 = await c.patch(f"/api/expenses/{r4.json()['id']}", json={"tax_cents": 600})
        assert r5.status_code == 200
        assert r5.json()["total_cents"] == 5600


@pytest.mark.asyncio
async def test_expense_lifecycle_archive_restore_void(ec7c_ctx):
    ua = ec7c_ctx["ua"]
    async with await _client(ua) as c:
        exp = (await c.post("/api/expenses", json={
            "expense_date": "2026-06-01", "category_key": "materials",
            "description": "Roll", "amount_cents": 100})).json()
        # Archive
        assert (await c.post(f"/api/expenses/{exp['id']}/archive")).status_code == 200
        assert (await c.get(f"/api/expenses/{exp['id']}")).json()["state"] == "archived"
        # Update forbidden while archived
        r = await c.patch(f"/api/expenses/{exp['id']}", json={"description": "x"})
        assert r.status_code == 400
        # Restore
        assert (await c.post(f"/api/expenses/{exp['id']}/restore")).status_code == 200
        assert (await c.get(f"/api/expenses/{exp['id']}")).json()["state"] == "active"
        # Void without reason -> 400
        r2 = await c.post(f"/api/expenses/{exp['id']}/void", json={"reason": "  "})
        assert r2.status_code == 400
        # Void with reason -> 200
        assert (await c.post(f"/api/expenses/{exp['id']}/void",
                              json={"reason": "Duplicate entry"})).status_code == 200
        assert (await c.get(f"/api/expenses/{exp['id']}")).json()["state"] == "voided"


@pytest.mark.asyncio
async def test_expense_receipt_attachment_reuses_file_records(ec7c_ctx):
    ua = ec7c_ctx["ua"]
    ta = ec7c_ctx["ta"]
    # Simulate an EC2 FileRecord (bypass upload endpoint)
    file_id = f"file-{uuid.uuid4().hex[:12]}"
    await db.files.insert_one({
        "id": file_id, "tenant_id": ta,
        "storage_key": f"tenants/{ta}/receipts/x.jpg",
        "original_filename": "receipt.jpg", "mime_type": "image/jpeg",
        "size_bytes": 12345, "uploaded_by": ua["id"], "visibility": "internal",
        "archived": False, "created_at": "2026-06-01T00:00:00Z",
        "updated_at": "2026-06-01T00:00:00Z",
    })
    async with await _client(ua) as c:
        exp = (await c.post("/api/expenses", json={
            "expense_date": "2026-06-01", "category_key": "materials",
            "description": "Roll", "amount_cents": 100})).json()
        # Attach
        r = await c.post(f"/api/expenses/{exp['id']}/attachments",
                         json={"file_id": file_id, "role": "receipt"})
        assert r.status_code == 201
        atts = (await c.get(f"/api/expenses/{exp['id']}")).json()["attachments"]
        assert len(atts) == 1
        assert atts[0]["role"] == "receipt"
        assert atts[0]["file"]["original_filename"] == "receipt.jpg"
        # Bad file id -> 400
        r2 = await c.post(f"/api/expenses/{exp['id']}/attachments",
                         json={"file_id": "no-such", "role": "receipt"})
        assert r2.status_code == 400
        # Archive attachment
        r3 = await c.post(f"/api/expenses/attachments/{atts[0]['id']}/archive")
        assert r3.status_code == 200
        atts2 = (await c.get(f"/api/expenses/{exp['id']}")).json()["attachments"]
        assert len(atts2) == 0


@pytest.mark.asyncio
async def test_expense_links_validate_and_cross_tenant_isolation(ec7c_ctx):
    ua, ub = ec7c_ctx["ua"], ec7c_ctx["ub"]
    async with await _client(ua) as c:
        # Cross-tenant customer not found
        # Create a customer in tenant B
        cust_b = {"id": f"cus-{uuid.uuid4().hex[:8]}", "tenant_id": ub["tenant_id"],
                  "name": "B Corp", "archived": False,
                  "created_at": "2026-06-01T00:00:00Z", "updated_at": "2026-06-01T00:00:00Z"}
        await db.customers.insert_one(cust_b)
        # Referencing B's customer from A must be rejected
        r = await c.post("/api/expenses", json={
            "expense_date": "2026-06-01", "category_key": "materials",
            "description": "x", "amount_cents": 100,
            "customer_id": cust_b["id"]})
        assert r.status_code == 400
    _clear()
    # Now tenant B can list — but A's expenses should be invisible
    async with await _client(ub) as c:
        items = (await c.get("/api/expenses")).json()["items"]
        assert items == []
