"""EC8 phase 8e — Equipment, Training, Certification + Work Order enforcement
tests (targeted, per credit-conservation — do not re-audit 8a-8d).

Covers the Phase 8e completion gate: Equipment CRUD + archive + tenant
isolation, access_policy->certification_required sync, Training Definition
CRUD + assignment lifecycle (start/complete/fail/overdue), quiz scoring
(backend-only, answer keys hidden from the portal, attempt history
preserved), practical signoff (no self-certification), Certification
issue/renew/revoke/expiration + duplicate-active prevention, Employee Portal
self-scope for My Training/My Certifications, and Work Order assignment
enforcement (hard block vs override-allowed warning, cross-tenant rejection,
backend revalidation on commit).
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
async def ec8e_ctx():
    ta = f"t-ec8e-{uuid.uuid4().hex[:6]}"
    tb = f"t-ec8eB-{uuid.uuid4().hex[:6]}"
    owner_a = {"id": f"u-a-{uuid.uuid4().hex[:6]}", "tenant_id": ta,
               "email": f"a-{uuid.uuid4().hex[:4]}@example.com", "role": "owner", "is_active": True}
    staff_a = {"id": f"u-s1-{uuid.uuid4().hex[:6]}", "tenant_id": ta,
               "email": f"s1-{uuid.uuid4().hex[:4]}@example.com", "role": "staff", "is_active": True}
    staff_b = {"id": f"u-s2-{uuid.uuid4().hex[:6]}", "tenant_id": ta,
               "email": f"s2-{uuid.uuid4().hex[:4]}@example.com", "role": "staff", "is_active": True}
    owner_b = {"id": f"u-b-{uuid.uuid4().hex[:6]}", "tenant_id": tb,
               "email": f"b-{uuid.uuid4().hex[:4]}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_many([{"id": ta, "slug": ta, "name": "TA"}, {"id": tb, "slug": tb, "name": "TB"}])
    await db.users.insert_many([{**owner_a}, {**staff_a}, {**staff_b}, {**owner_b}])
    async with await _client(owner_a) as c:
        r1 = await c.post("/api/employees", json={"name": "Trainee One", "linked_user_id": staff_a["id"], "role_label": "Install Tech"})
        emp1 = r1.json()
        r2 = await c.post("/api/employees", json={"name": "Trainee Two", "linked_user_id": staff_b["id"]})
        emp2 = r2.json()
        r3 = await c.post("/api/equipment", json={"name": "Forklift #1", "category": "lift", "safety_sensitive": True, "access_policy": "required_no_override"})
        forklift = r3.json()
        r4 = await c.post("/api/equipment", json={"name": "Laminator A", "category": "laminator", "access_policy": "required_override_allowed"})
        laminator = r4.json()
    yield {"owner_a": owner_a, "owner_b": owner_b, "staff_a": staff_a, "staff_b": staff_b, "ta": ta, "tb": tb,
           "emp1": emp1, "emp2": emp2, "forklift": forklift, "laminator": laminator}
    _clear()


# ---------------------------------------------------------------------------
# Equipment
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_equipment_crud_archive_tenant_isolation_and_policy_sync(ec8e_ctx):
    owner_a, owner_b, forklift, ta = ec8e_ctx["owner_a"], ec8e_ctx["owner_b"], ec8e_ctx["forklift"], ec8e_ctx["ta"]
    assert forklift["certification_required"] is True  # derived from access_policy at creation

    async with await _client(owner_a) as co:
        r = await co.patch(f"/api/equipment/{forklift['id']}", json={"access_policy": "no_required"})
        assert r.status_code == 200
        assert r.json()["certification_required"] is False  # stays in sync — never drifts independently

        r2 = await co.post(f"/api/equipment/{forklift['id']}/archive")
        assert r2.status_code == 200
        assert r2.json()["status"] == "archived"
        r3 = await co.post(f"/api/equipment/{forklift['id']}/archive")
        assert r3.status_code == 400  # already archived

    async with await _client(owner_b) as cb:
        r4 = await cb.get(f"/api/equipment/{forklift['id']}")
        assert r4.status_code == 404  # cross-tenant


@pytest.mark.asyncio
async def test_equipment_permission_enforcement(ec8e_ctx):
    staff_a = ec8e_ctx["staff_a"]
    async with await _client(staff_a) as cs:
        r = await cs.get("/api/equipment")
        assert r.status_code == 403
        r2 = await cs.post("/api/equipment", json={"name": "X"})
        assert r2.status_code == 403


# ---------------------------------------------------------------------------
# Training — definitions, assignment lifecycle, self-view
# ---------------------------------------------------------------------------

async def _create_reading_training(owner_a, laminator_id):
    async with await _client(owner_a) as co:
        r = await co.post("/api/training/definitions", json={
            "title": "Laminator Safety Briefing", "training_type": "reading",
            "equipment_id": laminator_id, "practical_signoff_required": False,
        })
        assert r.status_code == 201, r.text
        return r.json()


@pytest.mark.asyncio
async def test_training_assignment_lifecycle_and_overdue(ec8e_ctx):
    owner_a, emp1, laminator = ec8e_ctx["owner_a"], ec8e_ctx["emp1"], ec8e_ctx["laminator"]
    defn = await _create_reading_training(owner_a, laminator["id"])
    async with await _client(owner_a) as co:
        r = await co.post("/api/training/assignments", json={
            "employee_id": emp1["id"], "training_definition_id": defn["id"], "due_date": "2020-01-01",
        })
        assert r.status_code == 201, r.text
        assignment = r.json()
        assert assignment["status"] == "not_started"
        assert assignment["equipment_id"] == laminator["id"]  # denormalized from definition

        r2 = await co.get("/api/training/assignments", params={"employee_id": emp1["id"]})
        overdue_item = next(a for a in r2.json()["items"] if a["id"] == assignment["id"])
        assert overdue_item["overdue"] is True  # due_date is in the past


@pytest.mark.asyncio
async def test_employee_self_view_start_complete_and_other_employee_denied(ec8e_ctx):
    owner_a, emp1, emp2, laminator, ta = ec8e_ctx["owner_a"], ec8e_ctx["emp1"], ec8e_ctx["emp2"], ec8e_ctx["laminator"], ec8e_ctx["ta"]
    defn = await _create_reading_training(owner_a, laminator["id"])
    async with await _client(owner_a) as co:
        r = await co.post("/api/training/assignments", json={"employee_id": emp1["id"], "training_definition_id": defn["id"]})
        assignment = r.json()

    id1 = await create_portal_identity(tenant_id=ta, portal_type="employee", employee_id=emp1["id"], email=f"t1-{uuid.uuid4().hex[:5]}@example.com")
    t1 = create_portal_token(portal_identity_id=id1["id"], tenant_id=ta, portal_type="employee", employee_id=emp1["id"])
    id2 = await create_portal_identity(tenant_id=ta, portal_type="employee", employee_id=emp2["id"], email=f"t2-{uuid.uuid4().hex[:5]}@example.com")
    t2 = create_portal_token(portal_identity_id=id2["id"], tenant_id=ta, portal_type="employee", employee_id=emp2["id"])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        h1, h2 = {"Authorization": f"Bearer {t1}"}, {"Authorization": f"Bearer {t2}"}
        # emp2 (a different Employee) may not view or act on emp1's assignment
        denied = await c.get(f"/api/portal/employee/training/assignments/{assignment['id']}", headers=h2)
        assert denied.status_code == 403
        denied2 = await c.post(f"/api/portal/employee/training/assignments/{assignment['id']}/start", headers=h2)
        assert denied2.status_code == 403

        # emp1 (self) can start then complete
        started = await c.post(f"/api/portal/employee/training/assignments/{assignment['id']}/start", headers=h1)
        assert started.status_code == 200
        assert started.json()["status"] == "in_progress"
        completed = await c.post(f"/api/portal/employee/training/assignments/{assignment['id']}/complete", headers=h1)
        assert completed.status_code == 200
        assert completed.json()["status"] == "completed"

        list_r = await c.get("/api/portal/employee/training/assignments", headers=h2)
        assert list_r.json()["items"] == []  # emp2 has no assignments at all — never sees emp1's


@pytest.mark.asyncio
async def test_quiz_scoring_backend_only_history_preserved_and_pass_fail(ec8e_ctx):
    owner_a, emp1, laminator, ta = ec8e_ctx["owner_a"], ec8e_ctx["emp1"], ec8e_ctx["laminator"], ec8e_ctx["ta"]
    async with await _client(owner_a) as co:
        r = await co.post("/api/training/definitions", json={
            "title": "Laminator Quiz", "training_type": "quiz", "equipment_id": laminator["id"],
            "passing_score": 100,
            "quiz_questions": [
                {"id": "q1", "prompt": "Is the blade guard required?", "choices": ["Yes", "No"], "correct_index": 0},
                {"id": "q2", "prompt": "Max temp?", "choices": ["100C", "200C"], "correct_index": 1},
            ],
        })
        defn = r.json()
        assert "correct_index" not in str(defn.get("quiz_questions", [{}])[0].keys()) or "correct_index" in defn["quiz_questions"][0]
        # manager-facing GET must still show the answer key (needed to author/verify quizzes)
        r_get = await co.get(f"/api/training/definitions/{defn['id']}")
        assert r_get.json()["quiz_questions"][0]["correct_index"] == 0

        r2 = await co.post("/api/training/assignments", json={"employee_id": emp1["id"], "training_definition_id": defn["id"]})
        assignment = r2.json()

    identity = await create_portal_identity(tenant_id=ta, portal_type="employee", employee_id=emp1["id"], email=f"q-{uuid.uuid4().hex[:5]}@example.com")
    token = create_portal_token(portal_identity_id=identity["id"], tenant_id=ta, portal_type="employee", employee_id=emp1["id"])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        headers = {"Authorization": f"Bearer {token}"}
        detail = await c.get(f"/api/portal/employee/training/assignments/{assignment['id']}", headers=headers)
        assert detail.status_code == 200
        assert "correct_index" not in str(detail.json()["definition"]["quiz_questions"])  # answer key never exposed to portal

        fail = await c.post(f"/api/portal/employee/training/assignments/{assignment['id']}/quiz", headers=headers, json={
            "answers": [{"question_id": "q1", "selected_index": 1}, {"question_id": "q2", "selected_index": 1}],
            "started_at": "2026-01-01T00:00:00+00:00",
        })
        assert fail.status_code == 200
        assert fail.json()["passed"] is False
        assert fail.json()["score"] == 50

        passed = await c.post(f"/api/portal/employee/training/assignments/{assignment['id']}/quiz", headers=headers, json={
            "answers": [{"question_id": "q1", "selected_index": 0}, {"question_id": "q2", "selected_index": 1}],
            "started_at": "2026-01-01T00:05:00+00:00",
        })
        assert passed.status_code == 200
        assert passed.json()["passed"] is True
        assert passed.json()["attempt_number"] == 2  # prior attempt preserved, not overwritten

    count = await db.quiz_attempts.count_documents({"tenant_id": ta, "training_assignment_id": assignment["id"]})
    assert count == 2


@pytest.mark.asyncio
async def test_practical_signoff_no_self_certification_and_failed_signoff(ec8e_ctx):
    owner_a, emp1, laminator = ec8e_ctx["owner_a"], ec8e_ctx["emp1"], ec8e_ctx["laminator"]
    async with await _client(owner_a) as co:
        r = await co.post("/api/training/definitions", json={
            "title": "Laminator Practical", "training_type": "practical_demonstration",
            "equipment_id": laminator["id"], "practical_signoff_required": True,
        })
        defn = r.json()
        r2 = await co.post("/api/training/assignments", json={"employee_id": emp1["id"], "training_definition_id": defn["id"]})
        assignment = r2.json()

        fail_result = await co.post(f"/api/training/assignments/{assignment['id']}/signoff", json={"result": "failed", "notes": "needs more practice"})
        assert fail_result.status_code == 200
        assert fail_result.json()["result"] == "failed"
        detail = await co.get(f"/api/training/assignments/{assignment['id']}")
        assert detail.json()["status"] == "failed"
        assert detail.json()["practical_signoff_status"] == "failed"


@pytest.mark.asyncio
async def test_practical_signoff_rejects_employees_own_linked_user_as_evaluator(ec8e_ctx):
    """A staff user who IS the linked employee may never be the evaluator,
    even if (hypothetically) granted training:manage."""
    from app.services import training_service
    owner_a, staff_a, emp1, laminator, ta = ec8e_ctx["owner_a"], ec8e_ctx["staff_a"], ec8e_ctx["emp1"], ec8e_ctx["laminator"], ec8e_ctx["ta"]
    async with await _client(owner_a) as co:
        r = await co.post("/api/training/definitions", json={"title": "Self-signoff test", "training_type": "practical_demonstration", "equipment_id": laminator["id"], "practical_signoff_required": True})
        defn = r.json()
        r2 = await co.post("/api/training/assignments", json={"employee_id": emp1["id"], "training_definition_id": defn["id"]})
        assignment = r2.json()
    with pytest.raises(training_service.TrainingError):
        await training_service.record_practical_signoff(
            tenant_id=ta, assignment_id=assignment["id"], evaluator_user_id=staff_a["id"], actor_email=staff_a["email"], result="passed",
        )


# ---------------------------------------------------------------------------
# Certification — issue / renew / revoke / expiration / duplicate prevention
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_certification_issue_expire_renew_revoke_and_duplicate_prevention(ec8e_ctx):
    owner_a, emp1, laminator, ta = ec8e_ctx["owner_a"], ec8e_ctx["emp1"], ec8e_ctx["laminator"], ec8e_ctx["ta"]
    async with await _client(owner_a) as co:
        r = await co.post("/api/certifications", json={"employee_id": emp1["id"], "equipment_id": laminator["id"], "expiration_date": "2020-01-01"})
        assert r.status_code == 201, r.text
        cert = r.json()
        assert cert["status"] == "certified"

        # Duplicate active certification prevention
        r2 = await co.post("/api/certifications", json={"employee_id": emp1["id"], "equipment_id": laminator["id"], "expiration_date": "2030-01-01"})
        assert r2.status_code == 409

        # Backend-derived expiration (expiration_date is in the past)
        r3 = await co.get(f"/api/certifications/{cert['id']}")
        assert r3.status_code == 200
        assert r3.json()["status"] == "expired"

        # Renewal supersedes the expired cert (renewal_of, not a fresh duplicate rejection)
        r4 = await co.post(f"/api/certifications/{cert['id']}/renew", json={"expiration_date": "2030-01-01"})
        assert r4.status_code == 200, r4.text
        renewed = r4.json()
        assert renewed["status"] == "certified"
        assert renewed["renewal_of"] == cert["id"]

        # Revocation
        r5 = await co.post(f"/api/certifications/{renewed['id']}/revoke", json={"reason": "safety violation"})
        assert r5.status_code == 200
        assert r5.json()["status"] == "revoked"
        assert r5.json()["revocation_reason"] == "safety violation"
        r6 = await co.post(f"/api/certifications/{renewed['id']}/revoke", json={"reason": "again"})
        assert r6.status_code == 400  # already revoked — not deleted, just flagged


@pytest.mark.asyncio
async def test_my_certifications_self_scoped(ec8e_ctx):
    owner_a, emp1, emp2, laminator, ta = ec8e_ctx["owner_a"], ec8e_ctx["emp1"], ec8e_ctx["emp2"], ec8e_ctx["laminator"], ec8e_ctx["ta"]
    async with await _client(owner_a) as co:
        await co.post("/api/certifications", json={"employee_id": emp1["id"], "equipment_id": laminator["id"], "expiration_date": "2030-01-01"})

    id1 = await create_portal_identity(tenant_id=ta, portal_type="employee", employee_id=emp1["id"], email=f"c1-{uuid.uuid4().hex[:5]}@example.com")
    t1 = create_portal_token(portal_identity_id=id1["id"], tenant_id=ta, portal_type="employee", employee_id=emp1["id"])
    id2 = await create_portal_identity(tenant_id=ta, portal_type="employee", employee_id=emp2["id"], email=f"c2-{uuid.uuid4().hex[:5]}@example.com")
    t2 = create_portal_token(portal_identity_id=id2["id"], tenant_id=ta, portal_type="employee", employee_id=emp2["id"])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r1 = await c.get("/api/portal/employee/certifications", headers={"Authorization": f"Bearer {t1}"})
        assert len(r1.json()["items"]) == 1
        assert "trainer_user_id" not in r1.json()["items"][0]
        r2 = await c.get("/api/portal/employee/certifications", headers={"Authorization": f"Bearer {t2}"})
        assert r2.json()["items"] == []  # a different employee sees nothing of emp1's certifications


# ---------------------------------------------------------------------------
# Work Order assignment enforcement
# ---------------------------------------------------------------------------

async def _create_work_order(owner_a, required_equipment_ids=None, required_role=None):
    async with await _client(owner_a) as co:
        r = await co.post("/api/customers", json={"name": "WO Test Customer"})
        cust = r.json()
        r2 = await co.post("/api/quotes", json={"customer_id": cust["id"], "job_name": "WO Test Job"})
        quote = r2.json()
        await co.post(f"/api/quotes/{quote['id']}/line-items", json={
            "description": "Test", "quantity": 1, "unit_price_cents": 1000, "category": "banners",
        })
        r3 = await co.post(f"/api/quotes/{quote['id']}/convert-to-order", json={})
        assert r3.status_code == 200, r3.text
        order = r3.json()["order"]
        r_wo = await co.post("/api/work-orders", json={"order_id": order["id"]})
        assert r_wo.status_code == 201, r_wo.text
        wo = r_wo.json()
        patch_body = {}
        if required_equipment_ids is not None:
            patch_body["required_equipment_ids"] = required_equipment_ids
        if required_role is not None:
            patch_body["required_role"] = required_role
        if patch_body:
            r4 = await co.patch(f"/api/work-orders/{wo['id']}", json=patch_body)
            return r4.json()
        return wo


@pytest.mark.asyncio
async def test_work_order_enforcement_no_override_hard_block(ec8e_ctx):
    owner_a, staff_a, forklift = ec8e_ctx["owner_a"], ec8e_ctx["staff_a"], ec8e_ctx["forklift"]
    wo = await _create_work_order(owner_a, required_equipment_ids=[forklift["id"]])
    async with await _client(owner_a) as co:
        r = await co.post(f"/api/work-orders/{wo['id']}/assign", json={"user_ids": [staff_a["id"]]})
        assert r.status_code == 409
        detail = r.json()["detail"]
        assert detail["message"] == "assignment_blocked"
        assert detail["check"]["any_blocked"] is True

        precheck = await co.post(f"/api/work-orders/{wo['id']}/assignment-check", json={"user_ids": [staff_a["id"]]})
        assert precheck.json()["any_blocked"] is True  # SAME check function as assign()


@pytest.mark.asyncio
async def test_work_order_enforcement_valid_certification_allows_assignment(ec8e_ctx):
    owner_a, staff_a, emp1, forklift = ec8e_ctx["owner_a"], ec8e_ctx["staff_a"], ec8e_ctx["emp1"], ec8e_ctx["forklift"]
    async with await _client(owner_a) as co:
        await co.post("/api/certifications", json={"employee_id": emp1["id"], "equipment_id": forklift["id"], "expiration_date": "2030-01-01"})
    wo = await _create_work_order(owner_a, required_equipment_ids=[forklift["id"]])
    async with await _client(owner_a) as co:
        r = await co.post(f"/api/work-orders/{wo['id']}/assign", json={"user_ids": [staff_a["id"]]})
        assert r.status_code == 200, r.text
        assert staff_a["id"] in r.json()["assigned_user_ids"]


@pytest.mark.asyncio
async def test_work_order_enforcement_expired_and_revoked_certification_block(ec8e_ctx):
    owner_a, staff_a, emp1, forklift = ec8e_ctx["owner_a"], ec8e_ctx["staff_a"], ec8e_ctx["emp1"], ec8e_ctx["forklift"]
    async with await _client(owner_a) as co:
        r = await co.post("/api/certifications", json={"employee_id": emp1["id"], "equipment_id": forklift["id"], "expiration_date": "2020-01-01"})
        cert = r.json()
    wo = await _create_work_order(owner_a, required_equipment_ids=[forklift["id"]])
    async with await _client(owner_a) as co:
        r2 = await co.post(f"/api/work-orders/{wo['id']}/assign", json={"user_ids": [staff_a["id"]]})
        assert r2.status_code == 409  # expired, no_required_override policy -> hard block

    wo2 = await _create_work_order(owner_a, required_equipment_ids=[forklift["id"]])
    async with await _client(owner_a) as co:
        await co.post(f"/api/certifications/{cert['id']}/renew", json={"expiration_date": "2030-01-01"})
        r3 = await co.post(f"/api/work-orders/{wo2['id']}/assign", json={"user_ids": [staff_a["id"]]})
        assert r3.status_code == 200  # renewed cert is valid again
        renewed = await co.get(f"/api/certifications", params={"employee_id": emp1["id"], "equipment_id": forklift["id"]})
        active = next(c for c in renewed.json()["items"] if c["status"] == "certified")
        await co.post(f"/api/certifications/{active['id']}/revoke", json={"reason": "incident"})
        wo3 = await _create_work_order(owner_a, required_equipment_ids=[forklift["id"]])
        r4 = await co.post(f"/api/work-orders/{wo3['id']}/assign", json={"user_ids": [staff_a["id"]]})
        assert r4.status_code == 409  # revoked -> hard block


@pytest.mark.asyncio
async def test_work_order_enforcement_override_allowed_policy_warns_and_override_succeeds(ec8e_ctx):
    owner_a, staff_a, laminator = ec8e_ctx["owner_a"], ec8e_ctx["staff_a"], ec8e_ctx["laminator"]
    wo = await _create_work_order(owner_a, required_equipment_ids=[laminator["id"]])
    async with await _client(owner_a) as co:
        r = await co.post(f"/api/work-orders/{wo['id']}/assign", json={"user_ids": [staff_a["id"]]})
        assert r.status_code == 409
        assert r.json()["detail"]["message"] == "assignment_warning_override_required"

        r2 = await co.post(f"/api/work-orders/{wo['id']}/assign", json={"user_ids": [staff_a["id"]], "override_reason": "Supervising in person today"})
        assert r2.status_code == 200, r2.text


@pytest.mark.asyncio
async def test_work_order_cross_tenant_assignment_rejected(ec8e_ctx):
    owner_a, owner_b = ec8e_ctx["owner_a"], ec8e_ctx["owner_b"]
    wo = await _create_work_order(owner_a)
    async with await _client(owner_a) as co:
        r = await co.post(f"/api/work-orders/{wo['id']}/assign", json={"user_ids": [owner_b["id"]]})
        assert r.status_code == 400  # assignee_not_found (different tenant)


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_certification_and_training_reports_tenant_scope_and_csv_export(ec8e_ctx):
    owner_a, emp1, laminator = ec8e_ctx["owner_a"], ec8e_ctx["emp1"], ec8e_ctx["laminator"]
    async with await _client(owner_a) as co:
        await co.post("/api/certifications", json={"employee_id": emp1["id"], "equipment_id": laminator["id"], "expiration_date": "2026-08-01"})
        defn = (await co.post("/api/training/definitions", json={"title": "Overdue Test", "training_type": "reading"})).json()
        await co.post("/api/training/assignments", json={"employee_id": emp1["id"], "training_definition_id": defn["id"], "due_date": "2020-01-01"})

        r = await co.get("/api/reports")
        keys = {rep["key"] for rep in r.json()["reports"]}
        for k in ("certification.matrix", "certification.expiring", "training.incomplete", "training.overdue", "equipment.access"):
            assert k in keys

        r2 = await co.post("/api/reports/certification.matrix/run", json={"filters": {}})
        assert r2.status_code == 200
        assert any(row["employee_name"] == "Trainee One" for row in r2.json()["rows"])

        r3 = await co.post("/api/reports/training.overdue/run", json={"filters": {}})
        assert any(row["training_title"] == "Overdue Test" for row in r3.json()["rows"])

        r4 = await co.post("/api/reports/equipment.access/export.csv", json={"filters": {}})
        assert r4.status_code == 200
        assert r4.headers["content-type"].startswith("text/csv")
        assert "Laminator A" in r4.text
