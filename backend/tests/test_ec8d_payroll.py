"""EC8 phase 8d — Payroll service + router tests (targeted, per credit-conservation).

Covers the Phase 8d completion gate: Saturday-Friday period boundaries +
Friday payday, idempotent period creation (no overlaps), regular/overtime
calculation + blocking-warning gate on approve (with authorized override),
rate-snapshot historical stability, no-duplicate-earning-rows on repeated
recalculation, frozen-after-approval + authorized reopen, append-only ledger
(void = reversal, never in-place mutation), idempotent advances/payments,
ledger-derived partially_paid/paid status, carryover (both when the next
Pay Period already exists and when it doesn't yet), cross-tenant + RBAC
enforcement, the two payroll report registry entries + CSV export reuse,
and self-scoped Employee Portal My Pay.

NOTE: `app.dependency_overrides` is global on the shared `app` object, so
tests never hold two `_client(...)` context managers open at once — every
helper below opens its own short-lived client per actor, sequentially
(matching the existing EC8b/EC8c test convention).
"""
from __future__ import annotations
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from server import app
from app.core.db import db
from app.deps import get_current_user
from app.core.portal_security import create_portal_token
from app.services.portal_identity import create_portal_identity


def _override(u):
    async def _get(): return {**u}
    return _get


async def _client(u):
    app.dependency_overrides[get_current_user] = _override(u)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear(): app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
async def ec8d_ctx():
    ta = f"t-ec8d-{uuid.uuid4().hex[:6]}"
    tb = f"t-ec8dB-{uuid.uuid4().hex[:6]}"
    owner_a = {"id": f"u-a-{uuid.uuid4().hex[:6]}", "tenant_id": ta,
               "email": f"a-{uuid.uuid4().hex[:4]}@example.com", "role": "owner", "is_active": True}
    staff_a = {"id": f"u-s-{uuid.uuid4().hex[:6]}", "tenant_id": ta,
               "email": f"s-{uuid.uuid4().hex[:4]}@example.com", "role": "staff", "is_active": True}
    owner_b = {"id": f"u-b-{uuid.uuid4().hex[:6]}", "tenant_id": tb,
               "email": f"b-{uuid.uuid4().hex[:4]}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_many([{"id": ta, "slug": ta, "name": "TA"}, {"id": tb, "slug": tb, "name": "TB"}])
    await db.users.insert_many([{**owner_a}, {**staff_a}, {**owner_b}])
    async with await _client(owner_a) as c:
        r1 = await c.post("/api/employees", json={"name": "Pay Pete", "linked_user_id": staff_a["id"], "hourly_rate_cents": 3000})
        emp1 = r1.json()
        r2 = await c.post("/api/employees", json={"name": "Pay Priya", "hourly_rate_cents": 2000})
        emp2 = r2.json()
    yield {"owner_a": owner_a, "staff_a": staff_a, "owner_b": owner_b, "ta": ta, "tb": tb, "emp1": emp1, "emp2": emp2}
    _clear()


async def _log_hours(staff_user: dict, owner_user: dict, work_date: str, hours: float) -> dict:
    async with await _client(staff_user) as cs:
        r = await cs.post("/api/time-clock/clock-in", json={})
        entry = r.json()
    from datetime import datetime, timedelta
    clock_in = f"{work_date}T06:00:00+00:00"
    end_dt = datetime.fromisoformat(clock_in) + timedelta(minutes=int(hours * 60))
    async with await _client(owner_user) as co:
        r2 = await co.post(f"/api/time-clock/entries/{entry['id']}/correct", json={
            "clock_in_at": clock_in, "clock_out_at": end_dt.isoformat(), "reason": "backfill for deterministic test",
        })
        assert r2.status_code == 200, r2.text
        return r2.json()


async def _approve_weekly_timesheet(owner_user: dict, employee_id: str, week_start: str) -> dict:
    async with await _client(owner_user) as co:
        r = await co.get("/api/timesheets/weekly", params={"week_start": week_start, "employee_id": employee_id})
        ts = r.json()
        r2 = await co.post(f"/api/timesheets/{ts['id']}/approve")
        assert r2.status_code == 200, r2.text
        return r2.json()


async def _get_or_create_period(owner_user: dict, period_start: str) -> dict:
    async with await _client(owner_user) as co:
        r = await co.get("/api/payroll/periods/current", params={"period_start": period_start})
        assert r.status_code == 200, r.text
        return r.json()["period"]


async def _recalculate(owner_user: dict, period_id: str) -> dict:
    async with await _client(owner_user) as co:
        r = await co.post(f"/api/payroll/periods/{period_id}/recalculate")
        assert r.status_code == 200, r.text
        return r.json()


async def _approve_period(owner_user: dict, period_id: str, override_reason=None):
    async with await _client(owner_user) as co:
        return await co.post(f"/api/payroll/periods/{period_id}/approve", json={"override_reason": override_reason})


async def _get_period(owner_user: dict, period_id: str) -> dict:
    async with await _client(owner_user) as co:
        r = await co.get(f"/api/payroll/periods/{period_id}")
        assert r.status_code == 200, r.text
        return r.json()


@pytest.mark.asyncio
async def test_period_saturday_friday_boundary_friday_payday_and_no_overlap(ec8d_ctx):
    owner_a = ec8d_ctx["owner_a"]
    period = await _get_or_create_period(owner_a, "2026-02-10")  # Tuesday
    assert period["start_date"] == "2026-02-07"  # Saturday
    assert period["end_date"] == "2026-02-13"    # Friday
    assert period["payday"] == "2026-02-13"       # Friday payday enforced
    # Requesting any other date in the same week returns the SAME period (no overlap/duplicate)
    period2 = await _get_or_create_period(owner_a, "2026-02-08")
    assert period2["id"] == period["id"]
    count = await db.pay_periods.count_documents({"tenant_id": ec8d_ctx["ta"], "start_date": "2026-02-07"})
    assert count == 1


@pytest.mark.asyncio
async def test_recalculate_computes_regular_and_overtime_and_is_idempotent(ec8d_ctx):
    owner_a, staff_a, emp1, ta = ec8d_ctx["owner_a"], ec8d_ctx["staff_a"], ec8d_ctx["emp1"], ec8d_ctx["ta"]
    await _log_hours(staff_a, owner_a, "2026-02-10", 45)  # 40 regular + 5 OT
    await _approve_weekly_timesheet(owner_a, emp1["id"], "2026-02-10")
    period = await _get_or_create_period(owner_a, "2026-02-10")
    detail = await _recalculate(owner_a, period["id"])
    snap = next(s for s in detail["snapshots"] if s["employee_id"] == emp1["id"])
    assert snap["regular_minutes"] == 2400
    assert snap["overtime_minutes"] == 300
    assert snap["gross_regular_cents"] == 120000
    assert snap["gross_overtime_cents"] == 22500
    assert snap["warnings"] == []

    # Recalculating again with unchanged hours must NOT duplicate the earning rows
    await _recalculate(owner_a, period["id"])
    earning_count = await db.payroll_transactions.count_documents(
        {"tenant_id": ta, "employee_id": emp1["id"], "pay_period_id": period["id"], "type": "earning", "voided": False}
    )
    assert earning_count == 1
    ot_count = await db.payroll_transactions.count_documents(
        {"tenant_id": ta, "employee_id": emp1["id"], "pay_period_id": period["id"], "type": "overtime_earning", "voided": False}
    )
    assert ot_count == 1


@pytest.mark.asyncio
async def test_approve_blocked_by_unresolved_warnings_then_authorized_override(ec8d_ctx):
    owner_a, staff_a, emp1 = ec8d_ctx["owner_a"], ec8d_ctx["staff_a"], ec8d_ctx["emp1"]
    await _log_hours(staff_a, owner_a, "2026-03-03", 8)
    period = await _get_or_create_period(owner_a, "2026-03-03")
    await _recalculate(owner_a, period["id"])  # timesheet NOT approved yet -> warning
    r = await _approve_period(owner_a, period["id"])
    assert r.status_code == 409
    assert "blocking_warnings" in r.json()["detail"]
    r2 = await _approve_period(owner_a, period["id"], override_reason="Manager confirmed with employee")
    assert r2.status_code == 200
    assert r2.json()["period"]["status"] == "approved"


@pytest.mark.asyncio
async def test_rate_snapshot_stable_after_approval_despite_later_rate_change(ec8d_ctx):
    owner_a, staff_a, emp1 = ec8d_ctx["owner_a"], ec8d_ctx["staff_a"], ec8d_ctx["emp1"]
    await _log_hours(staff_a, owner_a, "2026-03-10", 8)
    await _approve_weekly_timesheet(owner_a, emp1["id"], "2026-03-10")
    period = await _get_or_create_period(owner_a, "2026-03-10")
    detail = await _recalculate(owner_a, period["id"])
    snap = next(s for s in detail["snapshots"] if s["employee_id"] == emp1["id"])
    assert snap["hourly_rate_cents"] == 3000
    await _approve_period(owner_a, period["id"])
    async with await _client(owner_a) as co:
        await co.patch(f"/api/employees/{emp1['id']}", json={"hourly_rate_cents": 9999})
    detail2 = await _get_period(owner_a, period["id"])
    snap2 = next(s for s in detail2["snapshots"] if s["employee_id"] == emp1["id"])
    assert snap2["hourly_rate_cents"] == 3000  # frozen — historical rate never mutates
    assert snap2["locked"] is True


@pytest.mark.asyncio
async def test_recalculate_frozen_once_approved_reopen_requires_reason(ec8d_ctx):
    owner_a, staff_a, emp1 = ec8d_ctx["owner_a"], ec8d_ctx["staff_a"], ec8d_ctx["emp1"]
    await _log_hours(staff_a, owner_a, "2026-03-17", 8)
    await _approve_weekly_timesheet(owner_a, emp1["id"], "2026-03-17")
    period = await _get_or_create_period(owner_a, "2026-03-17")
    await _recalculate(owner_a, period["id"])
    await _approve_period(owner_a, period["id"])
    async with await _client(owner_a) as co:
        r = await co.post(f"/api/payroll/periods/{period['id']}/recalculate")
        assert r.status_code == 409
        r2 = await co.post(f"/api/payroll/periods/{period['id']}/reopen", json={"reason": ""})
        assert r2.status_code == 400
        r3 = await co.post(f"/api/payroll/periods/{period['id']}/reopen", json={"reason": "Need to add a missed shift"})
        assert r3.status_code == 200
        assert r3.json()["period"]["status"] == "open"
        r4 = await co.post(f"/api/payroll/periods/{period['id']}/recalculate")
        assert r4.status_code == 200


@pytest.mark.asyncio
async def test_manual_transactions_idempotent_and_ledger_append_only_on_void(ec8d_ctx):
    owner_a, staff_a, emp1, ta = ec8d_ctx["owner_a"], ec8d_ctx["staff_a"], ec8d_ctx["emp1"], ec8d_ctx["ta"]
    await _log_hours(staff_a, owner_a, "2026-03-24", 8)
    await _approve_weekly_timesheet(owner_a, emp1["id"], "2026-03-24")
    period = await _get_or_create_period(owner_a, "2026-03-24")
    await _recalculate(owner_a, period["id"])
    await _approve_period(owner_a, period["id"])

    payload = {"employee_id": emp1["id"], "pay_period_id": period["id"], "type": "advance",
               "amount_cents": 5000, "effective_date": "2026-03-25", "idempotency_key": "adv-1"}
    async with await _client(owner_a) as co:
        r1 = await co.post("/api/payroll/transactions", json=payload)
        assert r1.status_code == 200, r1.text
        txn1 = r1.json()
        r2 = await co.post("/api/payroll/transactions", json=payload)
        assert r2.json()["id"] == txn1["id"]  # idempotent — same row, not duplicated
        count = await db.payroll_transactions.count_documents(
            {"tenant_id": ta, "employee_id": emp1["id"], "pay_period_id": period["id"], "type": "advance"}
        )
        assert count == 1

        r3 = await co.post(f"/api/payroll/transactions/{txn1['id']}/void", json={"reason": "entered twice by mistake"})
        assert r3.status_code == 200
    original = await db.payroll_transactions.find_one({"id": txn1["id"], "tenant_id": ta}, {"_id": 0})
    assert original["voided"] is True
    assert original["amount_cents"] == 5000  # amount never mutated in place
    reversal = await db.payroll_transactions.find_one(
        {"tenant_id": ta, "type": "void", "source_record_id": txn1["id"]}, {"_id": 0}
    )
    assert reversal is not None
    assert reversal["amount_cents"] == -5000


@pytest.mark.asyncio
async def test_status_derives_from_ledger_partially_paid_then_paid(ec8d_ctx):
    owner_a, staff_a, emp1 = ec8d_ctx["owner_a"], ec8d_ctx["staff_a"], ec8d_ctx["emp1"]
    await _log_hours(staff_a, owner_a, "2026-03-31", 8)  # 8h * $30 = 24000 cents gross
    await _approve_weekly_timesheet(owner_a, emp1["id"], "2026-03-31")
    period = await _get_or_create_period(owner_a, "2026-03-31")
    await _recalculate(owner_a, period["id"])
    r = await _approve_period(owner_a, period["id"])
    assert r.json()["period"]["status"] == "approved"

    async with await _client(owner_a) as co:
        await co.post("/api/payroll/transactions", json={
            "employee_id": emp1["id"], "pay_period_id": period["id"], "type": "payment",
            "amount_cents": 10000, "effective_date": "2026-04-03",
        })
    detail = await _get_period(owner_a, period["id"])
    assert detail["period"]["status"] == "partially_paid"

    async with await _client(owner_a) as co:
        await co.post("/api/payroll/transactions", json={
            "employee_id": emp1["id"], "pay_period_id": period["id"], "type": "payment",
            "amount_cents": 14000, "effective_date": "2026-04-03",
        })
    detail2 = await _get_period(owner_a, period["id"])
    assert detail2["period"]["status"] == "paid"


@pytest.mark.asyncio
async def test_close_blocked_by_unpaid_balance_then_override_creates_pending_carryover(ec8d_ctx):
    owner_a, staff_a, emp1, ta = ec8d_ctx["owner_a"], ec8d_ctx["staff_a"], ec8d_ctx["emp1"], ec8d_ctx["ta"]
    await _log_hours(staff_a, owner_a, "2026-04-07", 8)
    await _approve_weekly_timesheet(owner_a, emp1["id"], "2026-04-07")
    period = await _get_or_create_period(owner_a, "2026-04-07")
    await _recalculate(owner_a, period["id"])
    await _approve_period(owner_a, period["id"])

    async with await _client(owner_a) as co:
        r = await co.post(f"/api/payroll/periods/{period['id']}/close", json={})
        assert r.status_code == 409  # unpaid balance blocks close without override

        r2 = await co.post(f"/api/payroll/periods/{period['id']}/close", json={"override_reason": "Paying employee next week off-cycle"})
        assert r2.status_code == 200
        assert r2.json()["period"]["status"] == "closed"

    carryover_out = await db.payroll_transactions.find_one(
        {"tenant_id": ta, "employee_id": emp1["id"], "pay_period_id": period["id"], "type": "carryover_out"}, {"_id": 0},
    )
    assert carryover_out is not None
    assert carryover_out["amount_cents"] == 24000
    pending = await db.payroll_carryovers.find_one({"tenant_id": ta, "employee_id": emp1["id"], "source_period_id": period["id"]}, {"_id": 0})
    assert pending is not None
    assert pending["linked"] is False

    # Idempotency: closing again (already closed) must not duplicate the carryover_out row
    async with await _client(owner_a) as co:
        r3 = await co.post(f"/api/payroll/periods/{period['id']}/close", json={"override_reason": "retry"})
        assert r3.status_code == 400

    # Now create next week's Pay Period — pending carryover must auto-link
    next_period = await _get_or_create_period(owner_a, "2026-04-14")
    detail = await _get_period(owner_a, next_period["id"])
    snap = next((s for s in detail["snapshots"] if s["employee_id"] == emp1["id"]), None)
    assert snap is not None
    assert snap["carryover_in_cents"] == 24000
    pending2 = await db.payroll_carryovers.find_one({"id": pending["id"], "tenant_id": ta}, {"_id": 0})
    assert pending2["linked"] is True
    assert pending2["target_period_id"] == next_period["id"]


@pytest.mark.asyncio
async def test_carryover_links_immediately_when_next_period_already_exists(ec8d_ctx):
    owner_a, staff_a, emp1, ta = ec8d_ctx["owner_a"], ec8d_ctx["staff_a"], ec8d_ctx["emp1"], ec8d_ctx["ta"]
    await _log_hours(staff_a, owner_a, "2026-04-21", 8)
    await _approve_weekly_timesheet(owner_a, emp1["id"], "2026-04-21")
    period = await _get_or_create_period(owner_a, "2026-04-21")
    next_period = await _get_or_create_period(owner_a, "2026-04-28")  # already exists before close
    await _recalculate(owner_a, period["id"])
    await _approve_period(owner_a, period["id"])
    async with await _client(owner_a) as co:
        await co.post(f"/api/payroll/periods/{period['id']}/close", json={"override_reason": "off-cycle"})
    detail = await _get_period(owner_a, next_period["id"])
    snap = next(s for s in detail["snapshots"] if s["employee_id"] == emp1["id"])
    assert snap["carryover_in_cents"] == 24000
    pending_count = await db.payroll_carryovers.count_documents({"tenant_id": ta, "employee_id": emp1["id"], "linked": False})
    assert pending_count == 0  # no dangling pending record when the next period already existed


@pytest.mark.asyncio
async def test_cross_tenant_and_rbac_enforcement(ec8d_ctx):
    owner_a, owner_b, staff_a = ec8d_ctx["owner_a"], ec8d_ctx["owner_b"], ec8d_ctx["staff_a"]
    period = await _get_or_create_period(owner_a, "2026-05-05")
    async with await _client(owner_b) as cb:
        r = await cb.get(f"/api/payroll/periods/{period['id']}")
        assert r.status_code == 404
    async with await _client(staff_a) as cs:
        r2 = await cs.get("/api/payroll/periods")
        assert r2.status_code == 403


@pytest.mark.asyncio
async def test_reports_registry_includes_payroll_and_export_reuses_ec7_infra(ec8d_ctx):
    owner_a, staff_a, emp1 = ec8d_ctx["owner_a"], ec8d_ctx["staff_a"], ec8d_ctx["emp1"]
    await _log_hours(staff_a, owner_a, "2026-05-12", 8)
    await _approve_weekly_timesheet(owner_a, emp1["id"], "2026-05-12")
    period = await _get_or_create_period(owner_a, "2026-05-12")
    await _recalculate(owner_a, period["id"])

    async with await _client(owner_a) as co:
        r = await co.get("/api/reports")
        keys = {rep["key"] for rep in r.json()["reports"]}
        assert "payroll.by_period" in keys
        assert "payroll.by_employee" in keys

        r2 = await co.post("/api/reports/payroll.by_period/run", json={"filters": {"date_from": "2026-05-01", "date_to": "2026-05-31"}})
        assert r2.status_code == 200
        assert any(row["employee_name"] == "Pay Pete" for row in r2.json()["rows"])

        r3 = await co.post("/api/reports/payroll.by_period/export.csv", json={"filters": {"date_from": "2026-05-01", "date_to": "2026-05-31"}})
        assert r3.status_code == 200
        assert r3.headers["content-type"].startswith("text/csv")
        assert "Pay Pete" in r3.text


@pytest.mark.asyncio
async def test_zero_gross_period_does_not_derive_to_paid(ec8d_ctx):
    """Business-rule fix (found by testing agent): an approved Pay Period with
    zero earned/zero paid must stay 'approved', never auto-derive to 'paid' —
    there is no balance to consider 'satisfied'."""
    owner_a, staff_a, emp2 = ec8d_ctx["owner_a"], ec8d_ctx["staff_a"], ec8d_ctx["emp2"]
    # emp2 has no logged hours and no approved timesheet this week — recalculating
    # still creates a snapshot with 0 gross (candidate via payroll_transactions
    # lookup is empty, so we add a manual $0-neutralizing adjustment isn't needed;
    # instead directly recompute a zero snapshot then approve with override).
    period = await _get_or_create_period(owner_a, "2026-06-02")
    async with await _client(owner_a) as co:
        # Force a snapshot to exist for emp2 with zero activity by recording and
        # then voiding a $1 adjustment (net zero ledger, snapshot row created).
        r = await co.post("/api/payroll/transactions", json={
            "employee_id": emp2["id"], "pay_period_id": period["id"], "type": "adjustment",
            "amount_cents": 100, "effective_date": "2026-06-02",
        })
        txn = r.json()
        await co.post(f"/api/payroll/transactions/{txn['id']}/void", json={"reason": "test cleanup"})
        r2 = await co.post(f"/api/payroll/periods/{period['id']}/approve", json={"override_reason": "no hours this week"})
        assert r2.status_code == 200
        assert r2.json()["period"]["status"] == "approved"
    detail = await _get_period(owner_a, period["id"])
    assert detail["period"]["status"] == "approved"  # NOT "paid"


@pytest.mark.asyncio
async def test_my_pay_self_scoped_and_field_allowlist(ec8d_ctx):
    owner_a, staff_a, emp1, emp2, ta = ec8d_ctx["owner_a"], ec8d_ctx["staff_a"], ec8d_ctx["emp1"], ec8d_ctx["emp2"], ec8d_ctx["ta"]
    await _log_hours(staff_a, owner_a, "2026-05-19", 8)
    await _approve_weekly_timesheet(owner_a, emp1["id"], "2026-05-19")
    period = await _get_or_create_period(owner_a, "2026-05-19")
    await _recalculate(owner_a, period["id"])
    await _approve_period(owner_a, period["id"])

    identity1 = await create_portal_identity(tenant_id=ta, portal_type="employee", employee_id=emp1["id"],
                                              email=f"pay1-{uuid.uuid4().hex[:5]}@example.com")
    token1 = create_portal_token(portal_identity_id=identity1["id"], tenant_id=ta, portal_type="employee", employee_id=emp1["id"])
    identity2 = await create_portal_identity(tenant_id=ta, portal_type="employee", employee_id=emp2["id"],
                                              email=f"pay2-{uuid.uuid4().hex[:5]}@example.com")
    token2 = create_portal_token(portal_identity_id=identity2["id"], tenant_id=ta, portal_type="employee", employee_id=emp2["id"])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/portal/employee/pay/periods", headers={"Authorization": f"Bearer {token1}"})
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) == 1
        item = items[0]
        assert item["gross_regular_cents"] == 24000
        assert item["hourly_rate_cents"] == 3000
        assert item["period_status"] == "approved"
        for forbidden in ("employee_id", "employee_name", "notes", "created_by", "warnings", "linked_user_id"):
            assert forbidden not in item

        r2 = await c.get("/api/portal/employee/pay/periods", headers={"Authorization": f"Bearer {token2}"})
        assert r2.json()["items"] == []  # a different employee sees nothing of emp1's pay

        r3 = await c.get("/api/portal/employee/dashboard", headers={"Authorization": f"Bearer {token1}"})
        assert r3.json()["pay"]["gross_regular_cents"] == 24000
