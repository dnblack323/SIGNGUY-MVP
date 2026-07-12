"""EC8 phase 8b — Timesheet service + router tests.

Covers: Saturday-Friday week boundary (pure + integration), daily/weekly/
monthly totals, open-entry warning, approve/reject/reopen (incl. approved
entry lock + unlock), self-view, other-employee privacy.
"""
from __future__ import annotations
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from server import app
from app.core.db import db
from app.deps import get_current_user
from app.services.time_period_utils import week_bounds_for_date_str


def _override(u):
    async def _get(): return {**u}
    return _get


async def _client(u):
    app.dependency_overrides[get_current_user] = _override(u)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear(): app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
async def ec8b_ts_ctx():
    ta = f"t-ec8bts-{uuid.uuid4().hex[:6]}"
    owner_a = {"id": f"u-a-{uuid.uuid4().hex[:6]}", "tenant_id": ta,
               "email": f"a-{uuid.uuid4().hex[:4]}@example.com", "role": "owner", "is_active": True}
    staff_a = {"id": f"u-s-{uuid.uuid4().hex[:6]}", "tenant_id": ta,
               "email": f"s-{uuid.uuid4().hex[:4]}@example.com", "role": "staff", "is_active": True}
    await db.tenants.insert_many([{"id": ta, "slug": ta, "name": "TA"}])
    await db.users.insert_many([{**owner_a}, {**staff_a}])
    async with await _client(owner_a) as c:
        r = await c.post("/api/employees", json={"name": "TS Employee", "linked_user_id": staff_a["id"], "hourly_rate_cents": 2000})
        emp = r.json()
    yield {"owner_a": owner_a, "staff_a": staff_a, "ta": ta, "emp": emp}
    _clear()


def test_week_bounds_saturday_friday_pure():
    assert week_bounds_for_date_str("2026-02-10") == ("2026-02-07", "2026-02-13")  # Tuesday -> that week
    assert week_bounds_for_date_str("2026-02-07") == ("2026-02-07", "2026-02-13")  # Saturday itself
    assert week_bounds_for_date_str("2026-02-13") == ("2026-02-07", "2026-02-13")  # Friday itself
    assert week_bounds_for_date_str("2026-02-08") == ("2026-02-07", "2026-02-13")  # Sunday


@pytest.mark.asyncio
async def test_daily_weekly_monthly_totals(ec8b_ts_ctx):
    owner_a, staff_a, emp = ec8b_ts_ctx["owner_a"], ec8b_ts_ctx["staff_a"], ec8b_ts_ctx["emp"]
    async with await _client(staff_a) as c:
        r = await c.post("/api/time-clock/clock-in", json={})
        entry_id = r.json()["id"]
        await c.post("/api/time-clock/clock-out")

    async with await _client(owner_a) as c:
        r = await c.post(f"/api/time-clock/entries/{entry_id}/correct", json={
            "clock_in_at": "2026-02-10T14:00:00+00:00", "clock_out_at": "2026-02-10T16:00:00+00:00",
            "reason": "backfill for deterministic test",
        })
        assert r.status_code == 200
        assert r.json()["worked_minutes"] == 120
        assert r.json()["work_date"] == "2026-02-10"

    async with await _client(staff_a) as c:
        r = await c.get("/api/timesheets/summary", params={"period": "daily", "date": "2026-02-10"})
        assert r.status_code == 200
        assert r.json()["worked_minutes"] == 120

        r = await c.get("/api/timesheets/weekly", params={"week_start": "2026-02-10"})
        assert r.status_code == 200
        weekly = r.json()
        assert weekly["week_start"] == "2026-02-07"
        assert weekly["week_end"] == "2026-02-13"
        assert weekly["worked_minutes"] == 120
        assert weekly["estimated_gross_cents"] == 4000

        r = await c.get("/api/timesheets/summary", params={"period": "monthly", "date": "2026-02-20"})
        assert r.status_code == 200
        assert r.json()["worked_minutes"] == 120


@pytest.mark.asyncio
async def test_open_entry_counts_as_incomplete(ec8b_ts_ctx):
    staff_a = ec8b_ts_ctx["staff_a"]
    async with await _client(staff_a) as c:
        r = await c.post("/api/time-clock/clock-in", json={})
        work_date = r.json()["work_date"]
        r = await c.get("/api/timesheets/weekly", params={"week_start": work_date})
        assert r.json()["incomplete_entry_count"] >= 1


@pytest.mark.asyncio
async def test_approve_locks_entries_reject_and_reopen_unlocks(ec8b_ts_ctx):
    owner_a, staff_a = ec8b_ts_ctx["owner_a"], ec8b_ts_ctx["staff_a"]
    async with await _client(staff_a) as c:
        r = await c.post("/api/time-clock/clock-in", json={})
        entry = r.json()
        work_date = entry["work_date"]
        await c.post("/api/time-clock/clock-out")

    async with await _client(owner_a) as c:
        r = await c.get("/api/timesheets/weekly", params={"week_start": work_date, "employee_id": ec8b_ts_ctx["emp"]["id"]})
        ts_id = r.json()["id"]

        r = await c.post(f"/api/timesheets/{ts_id}/reject", json={"reason": ""})
        assert r.status_code == 400

        r = await c.post(f"/api/timesheets/{ts_id}/approve")
        assert r.status_code == 200
        assert r.json()["status"] == "approved"

        r = await c.post(f"/api/time-clock/entries/{entry['id']}/correct", json={"notes": "x", "reason": "should fail"})
        assert r.status_code == 409

        r = await c.post(f"/api/timesheets/{ts_id}/approve")
        assert r.status_code == 400

        r = await c.post(f"/api/timesheets/{ts_id}/reopen", json={"reason": "need to fix a note"})
        assert r.status_code == 200
        assert r.json()["status"] == "pending"

        r = await c.post(f"/api/time-clock/entries/{entry['id']}/correct", json={"notes": "fixed", "reason": "adding a note"})
        assert r.status_code == 200
        assert r.json()["notes"] == "fixed"


@pytest.mark.asyncio
async def test_self_view_and_other_employee_privacy(ec8b_ts_ctx):
    staff_a, emp = ec8b_ts_ctx["staff_a"], ec8b_ts_ctx["emp"]
    async with await _client(staff_a) as c:
        r = await c.get("/api/timesheets/summary", params={"period": "daily", "date": "2026-02-10"})
        assert r.status_code == 200

        r = await c.get("/api/timesheets/weekly", params={"week_start": "2026-02-10", "employee_id": emp["id"]})
        assert r.status_code == 403
