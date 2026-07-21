from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.core.portal_security import create_portal_token
from app.services.portal_tokens import mint_public_action_token
from server import app


async def _token_client(token: str) -> AsyncClient:
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    client.headers["Authorization"] = f"Bearer {token}"
    return client


def _forbidden_present(payload: object, forbidden: set[str]) -> set[str]:
    found: set[str] = set()
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in forbidden:
                found.add(key)
            found.update(_forbidden_present(value, forbidden))
    elif isinstance(payload, list):
        for item in payload:
            found.update(_forbidden_present(item, forbidden))
    return found


@pytest.mark.asyncio
async def test_decision_room_customer_public_payloads_are_minimized():
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"t-sec3-dr-{suffix}"
    customer_id = f"cust-sec3-{suffix}"
    room_id = f"dr-sec3-{suffix}"
    version_id = f"drv-sec3-{suffix}"
    public_file_id = f"file-public-{suffix}"
    private_file_id = f"file-private-{suffix}"

    await db.tenants.insert_one({"id": tenant_id, "slug": tenant_id, "name": "Security 3"})
    await db.customers.insert_one({"id": customer_id, "tenant_id": tenant_id, "name": "Safe Customer", "archived": False})
    await db.files.insert_many([
        {"id": public_file_id, "tenant_id": tenant_id, "filename": "public.png", "visibility": "customer_visible", "archived": False},
        {"id": private_file_id, "tenant_id": tenant_id, "filename": "costs.png", "visibility": "internal", "archived": False},
    ])
    await db.decision_rooms.insert_one({
        "id": room_id,
        "tenant_id": tenant_id,
        "customer_id": customer_id,
        "title": "Published options",
        "internal_name": "Margin Review",
        "status": "published",
        "published_version": 1,
    })
    await db.decision_room_versions.insert_one({
        "id": version_id,
        "tenant_id": tenant_id,
        "decision_room_id": room_id,
        "version_number": 1,
        "title": "Published options",
        "customer_safe_intro": "Choose one.",
        "allow_save_for_later": True,
        "allow_customer_comments": True,
        "allow_customer_questions": True,
        "allow_change_requests": True,
        "allow_reject_all": True,
        "options_snapshot": [{
            "id": f"opt-sec3-{suffix}",
            "active": True,
            "display_order": 1,
            "customer_label": "Good",
            "internal_name": "High margin",
            "internal_notes": "Cost $80, margin 68%",
            "pricing_snapshot_id": f"price-{suffix}",
            "manual_price_cents": 25000,
            "proof_id": f"proof-{suffix}",
            "file_ids": [public_file_id, private_file_id],
        }],
    })
    portal_identity = {
        "id": f"pi-sec3-{suffix}",
        "tenant_id": tenant_id,
        "portal_type": "customer",
        "customer_id": customer_id,
        "email": f"customer-{suffix}@example.com",
        "status": "active",
        "permissions": ["portal:view_decision_rooms", "portal:respond_decision_rooms"],
    }
    await db.portal_identities.insert_one(portal_identity)
    portal_token = create_portal_token(
        portal_identity_id=portal_identity["id"], tenant_id=tenant_id,
        portal_type="customer", customer_id=customer_id,
    )
    public_token, _ = await mint_public_action_token(
        tenant_id=tenant_id, action="decision_room_view",
        parent_type="decision_room", parent_id=room_id, single_use=False,
    )
    other_room_id = f"dr-sec3-other-{suffix}"
    await db.decision_rooms.insert_one({
        "id": other_room_id, "tenant_id": tenant_id, "customer_id": customer_id,
        "title": "Other room", "status": "published", "published_version": 1,
    })

    async with await _token_client(portal_token) as client:
        detail = await client.get(f"/api/portal/decision-rooms/{room_id}")
        assert detail.status_code == 200, detail.text
        body = detail.json()
        forbidden = {
            "tenant_id", "customer_id", "public_token_id", "internal_name", "internal_notes",
            "pricing_snapshot_id", "manual_price_cents", "proof_id",
        }
        assert _forbidden_present(body, forbidden) == set()
        assert body["options"][0]["file_ids"] == [public_file_id]

        decision = await client.post(
            f"/api/portal/decision-rooms/{room_id}/decisions",
            json={
                "action_type": "option_selected",
                "option_id": body["options"][0]["id"],
                "internal_review_status": "acknowledged",
                "customer_id": "spoofed",
                "idempotency_key": f"decision-{suffix}",
            },
        )
        assert decision.status_code == 201, decision.text
        assert _forbidden_present(decision.json(), {"tenant_id", "customer_id", "public_token_id", "internal_review_status", "idempotency_key"}) == set()
        stored = await db.customer_decisions.find_one({"id": decision.json()["id"], "tenant_id": tenant_id}, {"_id": 0})
        assert stored["customer_id"] == customer_id
        assert stored["internal_review_status"] == "pending_review"

        saved = await client.post(
            f"/api/portal/decision-rooms/{room_id}/save-for-later",
            json={"note": "Later", "idempotency_key": f"saved-{suffix}"},
        )
        assert saved.status_code == 201, saved.text
        assert _forbidden_present(saved.json(), {"tenant_id", "customer_id", "public_token_id", "idempotency_key"}) == set()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as anon:
        wrong_room = await anon.get(f"/api/public/decision-rooms/{other_room_id}", params={"t": public_token})
        assert wrong_room.status_code == 403


@pytest.mark.asyncio
async def test_employee_portal_payloads_are_minimized_and_self_scoped():
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"t-sec3-emp-{suffix}"
    employee_id = f"emp-sec3-{suffix}"
    other_employee_id = f"emp-other-{suffix}"

    await db.tenants.insert_one({"id": tenant_id, "slug": tenant_id, "name": "Security 3"})
    await db.employees.insert_many([
        {
            "id": employee_id, "tenant_id": tenant_id, "name": "Portal Employee",
            "email": f"employee-{suffix}@example.com", "status": "active",
            "hourly_rate_cents": 5000, "linked_user_id": f"user-{suffix}",
            "role_label": "Installer", "portal_access": True, "overtime_policy": "weekly",
            "notes": "Manager note", "status_history": [{"from": "inactive", "to": "active"}],
        },
        {"id": other_employee_id, "tenant_id": tenant_id, "name": "Other Employee", "status": "active", "hourly_rate_cents": 9000},
    ])
    portal_identity = {
        "id": f"pi-emp-sec3-{suffix}",
        "tenant_id": tenant_id,
        "portal_type": "employee",
        "employee_id": employee_id,
        "email": f"portal-{suffix}@example.com",
        "status": "active",
        "permissions": [
            "portal:employee_view", "portal:employee_time_clock", "portal:employee_schedule_view",
            "portal:employee_timesheet_view", "portal:employee_pay_view", "portal:employee_profile",
        ],
    }
    await db.portal_identities.insert_one(portal_identity)
    token = create_portal_token(
        portal_identity_id=portal_identity["id"], tenant_id=tenant_id,
        portal_type="employee", employee_id=employee_id,
    )
    await db.time_entries.insert_one({
        "id": f"time-sec3-{suffix}", "tenant_id": tenant_id, "employee_id": employee_id,
        "linked_user_id": f"user-{suffix}", "work_date": "2026-07-20",
        "clock_in_at": "2026-07-20T13:00:00+00:00", "status": "open", "source": "self",
        "created_by": "manager", "updated_by": "manager", "corrections": [{"reason": "internal"}],
        "approved_by": "manager", "void_reason": "internal",
    })
    await db.schedules.insert_one({"id": f"sched-sec3-{suffix}", "tenant_id": tenant_id, "period_start": "2026-07-18", "status": "published"})
    await db.shifts.insert_one({
        "id": f"shift-sec3-{suffix}", "tenant_id": tenant_id, "schedule_id": f"sched-sec3-{suffix}",
        "employee_id": employee_id, "shift_date": "2026-07-20",
        "start_at": "2026-07-20T13:00:00+00:00", "end_at": "2026-07-20T21:00:00+00:00",
        "status": "scheduled", "created_by": "manager", "updated_by": "manager",
        "conflict_override_reason": "manager-only",
    })
    await db.announcements.insert_one({
        "id": f"ann-sec3-{suffix}", "tenant_id": tenant_id, "title": "Shift reminder",
        "body": "Bring tools.", "audience": "selected", "employee_ids": [employee_id],
        "status": "published", "published_at": "2026-07-20T12:00:00+00:00",
        "created_by": "manager", "acknowledged_by": [other_employee_id],
    })
    await db.payroll_snapshots.insert_many([
        {
            "id": f"pay-sec3-{suffix}", "tenant_id": tenant_id, "employee_id": employee_id,
            "pay_period_id": f"period-sec3-{suffix}", "period_start": "2026-07-01",
            "period_end": "2026-07-15", "payday": "2026-07-20", "period_status": "closed",
            "regular_minutes": 480, "overtime_minutes": 0, "hourly_rate_cents": 5000,
            "gross_regular_cents": 40000, "gross_overtime_cents": 0, "adjustment_total_cents": 0,
            "advance_total_cents": 0, "repayment_total_cents": 0, "payment_total_cents": 40000,
            "carryover_in_cents": 0, "carryover_out_cents": 0, "total_earned_cents": 40000,
            "total_paid_cents": 40000, "remaining_balance_cents": 0, "manager_note": "hidden",
        },
        {
            "id": f"pay-other-{suffix}", "tenant_id": tenant_id, "employee_id": other_employee_id,
            "pay_period_id": f"period-sec3-{suffix}", "period_start": "2026-07-01",
            "period_end": "2026-07-15", "payday": "2026-07-20", "period_status": "closed",
            "regular_minutes": 480, "overtime_minutes": 0, "hourly_rate_cents": 9000,
        },
    ])

    forbidden = {
        "tenant_id", "linked_user_id", "role_label", "portal_access", "overtime_policy",
        "notes", "status_history", "created_by", "updated_by", "corrections",
        "approved_by", "void_reason", "schedule_id", "conflict_override_reason",
        "employee_ids", "acknowledged_by", "manager_note",
    }
    async with await _token_client(token) as client:
        profile = await client.get("/api/portal/employee/profile")
        assert profile.status_code == 200, profile.text
        assert profile.json()["employee"]["id"] == employee_id
        assert _forbidden_present(profile.json(), forbidden | {"hourly_rate_cents"}) == set()

        active = await client.get("/api/portal/employee/time-clock/me")
        assert active.status_code == 200, active.text
        assert active.json()["active_entry"]["employee_id"] == employee_id
        assert _forbidden_present(active.json(), forbidden) == set()

        schedule = await client.get("/api/portal/employee/schedule/week?week_start=2026-07-18")
        assert schedule.status_code == 200, schedule.text
        assert len(schedule.json()["items"]) == 1
        assert _forbidden_present(schedule.json(), forbidden) == set()

        announcements = await client.get("/api/portal/employee/announcements")
        assert announcements.status_code == 200, announcements.text
        assert len(announcements.json()["items"]) == 1
        assert _forbidden_present(announcements.json(), forbidden) == set()

        pay = await client.get("/api/portal/employee/pay/periods")
        assert pay.status_code == 200, pay.text
        assert len(pay.json()["items"]) == 1
        assert pay.json()["items"][0]["hourly_rate_cents"] == 5000
        assert other_employee_id not in pay.text
        assert _forbidden_present(pay.json(), {"tenant_id", "employee_id", "manager_note"}) == set()
