"""F2 — Customizable Home dashboard: registry, per-user layout, permissions, data."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.core.security import create_access_token
from app.deps import get_current_user
from app.services import home_dashboard
from server import app


def _iso(delta: timedelta = timedelta()) -> str:
    return (datetime.now(timezone.utc) + delta).isoformat()


def _as(user: dict) -> AsyncClient:
    async def _get():
        return {**user}

    app.dependency_overrides[get_current_user] = _get
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _shop(label: str) -> dict:
    s = uuid.uuid4().hex[:8]
    tid = f"t-f2-{label}-{s}"
    owner = {"id": f"owner-{s}", "tenant_id": tid, "email": f"o-{s}@example.com", "role": "owner", "is_active": True}
    owner2 = {"id": f"owner2-{s}", "tenant_id": tid, "email": f"o2-{s}@example.com", "role": "owner", "is_active": True}
    staff = {"id": f"staff-{s}", "tenant_id": tid, "email": f"s-{s}@example.com", "role": "staff", "is_active": True}
    await db.tenants.insert_one({"id": tid, "slug": tid, "name": f"F2 {label}", "is_active": True})
    await db.users.insert_many([dict(owner), dict(owner2), dict(staff)])
    return {"tenant_id": tid, "owner": owner, "owner2": owner2, "staff": staff, "s": s}


@pytest_asyncio.fixture(autouse=True)
async def _cleanup_overrides():
    yield
    app.dependency_overrides.pop(get_current_user, None)


async def _seed_records(shop: dict) -> None:
    tid, s = shop["tenant_id"], shop["s"]
    await db.orders.insert_many([
        {"id": f"o1-{s}", "tenant_id": tid, "number": 1, "job_name": "Storefront", "status": "confirmed", "total_cents": 10000},
        {"id": f"o2-{s}", "tenant_id": tid, "number": 2, "job_name": "Banner", "status": "ready", "total_cents": 5000},
        {"id": f"o3-{s}", "tenant_id": tid, "number": 3, "job_name": "Draft", "status": "draft", "total_cents": 1},
        {"id": f"o4-{s}", "tenant_id": tid, "number": 4, "job_name": "Done", "status": "completed", "total_cents": 1},
    ])
    await db.quotes.insert_many([
        {"id": f"q1-{s}", "tenant_id": tid, "number": 11, "job_name": "Truck", "status": "sent", "total_cents": 20000},
        {"id": f"q2-{s}", "tenant_id": tid, "number": 12, "job_name": "Sign", "status": "viewed", "total_cents": 3000},
        {"id": f"q3-{s}", "tenant_id": tid, "number": 13, "job_name": "Draft", "status": "draft", "total_cents": 1},
    ])
    await db.invoices.insert_many([
        {"id": f"i1-{s}", "tenant_id": tid, "order_id": f"inv-order-i1-{s}", "number": 21, "title": "Late", "status": "sent", "due_date": _iso(-timedelta(days=3)), "balance_due_cents": 4000},
        {"id": f"i2-{s}", "tenant_id": tid, "order_id": f"inv-order-i2-{s}", "number": 22, "title": "Soon", "status": "partially_paid", "due_date": _iso(timedelta(days=2)), "balance_due_cents": 1500},
        {"id": f"i3-{s}", "tenant_id": tid, "order_id": f"inv-order-i3-{s}", "number": 23, "title": "Paid", "status": "paid", "balance_due_cents": 0},
    ])
    await db.work_orders.insert_many([
        {"id": f"w1-{s}", "tenant_id": tid, "number": 31, "production_status": "in_progress"},
        {"id": f"w2-{s}", "tenant_id": tid, "number": 32, "production_status": "on_hold"},  # legacy -> blocked
        {"id": f"w3-{s}", "tenant_id": tid, "number": 33, "production_status": "completed"},
    ])


@pytest.mark.asyncio
async def test_default_layout_shows_one_widget_per_family_with_real_values():
    shop = await _shop("values")
    await _seed_records(shop)
    async with _as(shop["owner"]) as c:
        body = (await c.get("/api/dashboard/home")).json()
    data, hidden = body["data"], set(body["layout"]["hidden"])
    assert data["active_orders_kpi"]["value"] == 2  # confirmed + ready (Shop Operations definition)
    assert data["unpaid_invoices_kpi"] == {"state": "ready", "value": 2, "amount_cents": 5500}
    assert data["production_status"]["total"] == 2
    assert {r["status"]: r["value"] for r in data["production_status"]["rows"]}["blocked"] == 1
    assert data["quotes_awaiting_list"]["total"] == 2
    assert {i["to"] for i in data["quotes_awaiting_list"]["items"]} == {f"/quotes/q1-{shop['s']}", f"/quotes/q2-{shop['s']}"}
    visible = [k for k in body["layout"]["order"] if k not in hidden]
    families = [home_dashboard.WIDGET_BY_KEY[k]["family"] for k in visible]
    assert len(families) == len(set(families))
    assert "quotes_awaiting_kpi" not in data  # hidden widgets are not computed


@pytest.mark.asyncio
async def test_invoice_aging_buckets_use_balances():
    shop = await _shop("aging")
    await _seed_records(shop)
    async with _as(shop["owner"]) as c:
        await c.put("/api/dashboard/home/layout", json={"order": ["invoice_aging"], "hidden": ["unpaid_invoices_kpi"]})
        aging = (await c.get("/api/dashboard/home")).json()["data"]["invoice_aging"]
    rows = {r["label"]: (r["value"], r["amount_cents"]) for r in aging["rows"]}
    assert rows["Overdue"] == (1, 4000) and rows["Due in 7 days"] == (1, 1500) and aging["amount_cents"] == 5500


@pytest.mark.asyncio
async def test_layout_is_per_user_and_per_tenant_and_resettable():
    shop = await _shop("prefs")
    other = await _shop("prefs-other")
    async with _as(shop["owner"]) as c:
        saved = (await c.put("/api/dashboard/home/layout", json={
            "order": ["recent_customers", "active_orders_kpi"], "hidden": ["active_team_kpi", "bogus_widget"], "collapsed": ["recent_customers", "active_orders_kpi"],
        })).json()["layout"]
    assert saved["order"][:2] == ["recent_customers", "active_orders_kpi"]
    assert "active_team_kpi" in saved["hidden"] and "bogus_widget" not in saved["hidden"]
    assert saved["collapsed"] == ["recent_customers"]  # only list widgets collapse
    async with _as(shop["owner"]) as c:
        assert (await c.get("/api/dashboard/home")).json()["layout"]["order"][0] == "recent_customers"
    default = home_dashboard.default_layout()
    async with _as(shop["owner2"]) as c:
        assert (await c.get("/api/dashboard/home")).json()["layout"] == default
    async with _as(other["owner"]) as c:
        assert (await c.get("/api/dashboard/home")).json()["layout"] == default
    async with _as(shop["owner"]) as c:
        assert (await c.delete("/api/dashboard/home/layout")).json()["layout"] == default
        assert (await c.get("/api/dashboard/home")).json()["layout"] == default
    assert await db.dashboard_preferences.count_documents({"tenant_id": shop["tenant_id"]}) == 0


@pytest.mark.asyncio
async def test_two_presentations_of_one_metric_cannot_both_show():
    shop = await _shop("dedupe")
    async with _as(shop["owner"]) as c:
        layout = (await c.put("/api/dashboard/home/layout", json={
            "order": ["quotes_awaiting_kpi", "quotes_awaiting_list"], "hidden": [],
        })).json()["layout"]
    assert "quotes_awaiting_kpi" not in layout["hidden"] and "quotes_awaiting_list" in layout["hidden"]


@pytest.mark.asyncio
async def test_permission_restricted_widgets_return_no_data():
    shop = await _shop("perms")
    await db.calendar_events.insert_one({"id": f"ev-{shop['s']}", "tenant_id": shop["tenant_id"], "title": "Install",
                                         "start_at": _iso(timedelta(minutes=5)), "end_at": _iso(timedelta(hours=1)), "status": "scheduled", "archived_at": None})
    async with _as(shop["staff"]) as c:
        body = (await c.get("/api/dashboard/home")).json()
    restricted = {w["key"] for w in body["restricted"]}
    assert {"todays_schedule", "timesheets_pending_kpi", "active_team_kpi"} <= restricted
    assert not restricted & set(body["data"])
    assert not restricted & {w["key"] for w in body["widgets"]}


@pytest.mark.asyncio
async def test_todays_schedule_is_tenant_isolated_and_links_records():
    shop = await _shop("sched")
    other = await _shop("sched-other")
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    for t, title in ((shop, "Our install"), (other, "Their install")):
        await db.calendar_events.insert_one({"id": f"ev-{t['s']}", "tenant_id": t["tenant_id"], "title": title, "order_id": f"o1-{t['s']}",
                                             "start_at": (start + timedelta(hours=10)).isoformat(), "end_at": (start + timedelta(hours=11)).isoformat(),
                                             "status": "scheduled", "archived_at": None})
    params = {"day_start": start.isoformat(), "day_end": (start + timedelta(days=1)).isoformat()}
    async with _as(shop["owner"]) as c:
        items = (await c.get("/api/dashboard/home", params=params)).json()["data"]["todays_schedule"]["items"]
    assert [i["title"] for i in items] == ["Our install"]
    assert items[0]["to"] == f"/orders/o1-{shop['s']}"


@pytest.mark.asyncio
async def test_failing_source_is_unavailable_not_fatal(monkeypatch):
    shop = await _shop("fail")

    async def _boom(*_a):
        raise RuntimeError("source down")

    monkeypatch.setitem(home_dashboard.SOURCES, "recent_customers", _boom)
    async with _as(shop["owner"]) as c:
        resp = await c.get("/api/dashboard/home")
    assert resp.status_code == 200
    assert resp.json()["data"]["recent_customers"]["state"] == "unavailable"
    assert resp.json()["data"]["active_orders_kpi"]["state"] == "ready"


@pytest.mark.asyncio
async def test_read_only_shop_can_still_save_its_layout():
    shop = await _shop("readonly")
    await db.trial_records.insert_one({"id": f"tr-{shop['s']}", "tenant_id": shop["tenant_id"], "billing_account_id": "ba",
                                       "trial_kind": "free", "status": "free_active", "starts_at": _iso(-timedelta(days=3)), "ends_at": _iso(-timedelta(hours=1))})
    token = create_access_token(subject=shop["owner"]["id"], tenant_id=shop["tenant_id"])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"Authorization": f"Bearer {token}"}) as c:
        assert (await c.put("/api/dashboard/home/layout", json={"hidden": ["recent_activity"]})).status_code == 200
        assert (await c.post("/api/customers", json={"name": "Blocked"})).status_code == 402


# --- PR #43 review findings ------------------------------------------------------


@pytest.mark.asyncio
async def test_todays_schedule_is_not_starved_by_older_history():
    shop = await _shop("history")
    tid, s = shop["tenant_id"], shop["s"]
    day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    older = [{"id": f"old{i}-{s}", "tenant_id": tid, "title": f"Old job {i}", "status": "scheduled", "archived_at": None,
              "start_at": (day - timedelta(days=40 - i, hours=-9)).isoformat(), "end_at": (day - timedelta(days=40 - i, hours=-10)).isoformat()}
             for i in range(30)]
    today = [{"id": f"today{h}-{s}", "tenant_id": tid, "title": f"Today {h}", "status": status, "archived_at": None,
              "start_at": (day + timedelta(hours=h)).isoformat(), "end_at": (day + timedelta(hours=h + 1)).isoformat()}
             for h, status in ((9, "scheduled"), (11, "in_progress"), (13, "scheduled"), (15, "completed"))]
    await db.calendar_events.insert_many(older + today)
    params = {"day_start": day.isoformat(), "day_end": (day + timedelta(days=1)).isoformat()}
    async with _as(shop["owner"]) as c:
        widget = (await c.get("/api/dashboard/home", params=params)).json()["data"]["todays_schedule"]
    assert [i["title"] for i in widget["items"]] == ["Today 9", "Today 11", "Today 13"]
    assert widget["total"] == 3


@pytest.mark.asyncio
async def test_unpaid_invoices_use_canonical_status_and_positive_balance():
    shop = await _shop("canon")
    tid, s = shop["tenant_id"], shop["s"]

    def inv(n, **fields):
        return {"id": f"inv{n}-{s}", "tenant_id": tid, "order_id": f"ord{n}-{s}", "number": n, "title": f"Invoice {n}", **fields}

    await db.invoices.insert_many([
        inv(1, status="sent", document_status="issued", financial_status="paid", balance_due_cents=0, due_date=_iso(-timedelta(days=9))),  # fully paid
        inv(2, status="sent", document_status="issued", financial_status="partial", balance_due_cents=2000, due_date=_iso(timedelta(days=3))),
        inv(3, status="sent", document_status="issued", financial_status="unpaid", balance_due_cents=5000, due_date=_iso(-timedelta(days=2))),  # overdue
        inv(4, status="sent", document_status="issued", financial_status="unpaid", balance_due_cents=0),  # nothing actually due
        inv(5, status="draft", document_status="draft", financial_status="unpaid", balance_due_cents=900),  # not issued
        inv(6, status="void", document_status="void", financial_status="voided", balance_due_cents=700),
        inv(7, status="sent", balance_due_cents=1000, due_date=_iso(timedelta(days=30))),  # legacy row, still open
        inv(8, status="paid", balance_due_cents=0),  # legacy paid
    ])
    async with _as(shop["owner"]) as c:
        await c.put("/api/dashboard/home/layout", json={"order": ["unpaid_invoices_list", "invoice_aging"],
                                                         "hidden": ["unpaid_invoices_kpi", "invoice_aging"]})
        listed = (await c.get("/api/dashboard/home")).json()["data"]["unpaid_invoices_list"]
        await c.put("/api/dashboard/home/layout", json={"order": ["unpaid_invoices_kpi"], "hidden": []})
        kpi = (await c.get("/api/dashboard/home")).json()["data"]["unpaid_invoices_kpi"]
        await c.put("/api/dashboard/home/layout", json={"order": ["invoice_aging"], "hidden": ["unpaid_invoices_kpi"]})
        aging = (await c.get("/api/dashboard/home")).json()["data"]["invoice_aging"]
    assert {i["ref"] for i in listed["items"]} == {"I-2", "I-3", "I-7"}
    assert kpi["value"] == 3 and kpi["amount_cents"] == 8000
    buckets = {r["label"]: (r["value"], r["amount_cents"]) for r in aging["rows"]}
    assert buckets == {"Overdue": (1, 5000), "Due in 7 days": (1, 2000), "Due later or no due date": (1, 1000)}


@pytest.mark.asyncio
async def test_work_order_status_filter_includes_legacy_values():
    shop = await _shop("wofilter")
    tid, s = shop["tenant_id"], shop["s"]
    await db.work_orders.insert_many([
        {"id": f"wb-{s}", "tenant_id": tid, "number": 1, "production_status": "blocked", "is_current": True},
        {"id": f"wh-{s}", "tenant_id": tid, "number": 2, "production_status": "on_hold", "is_current": True},
        {"id": f"wq-{s}", "tenant_id": tid, "number": 3, "production_status": "queued", "is_current": True},
    ])
    async with _as(shop["owner"]) as c:
        blocked = (await c.get("/api/work-orders", params={"production_status": "blocked"})).json()["items"]
        queued = (await c.get("/api/work-orders", params={"production_status": "queued"})).json()["items"]
    assert {w["id"] for w in blocked} == {f"wb-{s}", f"wh-{s}"}
    assert [w["id"] for w in queued] == [f"wq-{s}"]
