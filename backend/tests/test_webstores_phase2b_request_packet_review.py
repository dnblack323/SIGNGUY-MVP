"""Webstores Phase 2b: request -> information packet -> conditional questionnaire -> review -> applied draft settings."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.db import db, ensure_indexes
from app.deps import get_current_user
from app.services.email import public_url
from app.services.webstore_questionnaire_review import consistency_checks
from server import app
from tests.webstore_questionnaire_answers import complete_answers


def _override(user: dict):
    async def _get():
        return {**user}

    return _get


async def _staff(user: dict) -> AsyncClient:
    app.dependency_overrides[get_current_user] = _override(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _portal(token: str) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"Authorization": f"Bearer {token}"})


@pytest.fixture
async def ctx():
    await ensure_indexes()
    suffix = uuid.uuid4().hex[:8]
    tenant_id = f"t-ws-p2b-{suffix}"
    other_tenant_id = f"t-ws-p2b-other-{suffix}"
    user = {"id": f"user-{suffix}", "tenant_id": tenant_id, "email": f"staff-{suffix}@example.com", "role": "owner", "is_active": True}
    other_user = {"id": f"other-{suffix}", "tenant_id": other_tenant_id, "email": f"other-{suffix}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_many([
        {"id": tenant_id, "slug": f"p2b-{suffix}", "name": f"Sign Shop {suffix}"},
        {"id": other_tenant_id, "slug": f"p2b-other-{suffix}", "name": f"Other Shop {suffix}"},
    ])
    await db.users.insert_many([user, other_user])
    await db.settings.insert_one({"id": f"s-{suffix}", "tenant_id": tenant_id, "namespace": "company_profile", "key": "email", "value": f"orders-{suffix}@signshop.example", "value_type": "string"})
    yield {"suffix": suffix, "tenant_id": tenant_id, "user": user, "other_user": other_user}
    app.dependency_overrides.pop(get_current_user, None)


async def _request(client: AsyncClient, suffix: str, store_type: str = "event", **extra) -> dict:
    resp = await client.post("/api/webstores/requests", json={
        "new_customer": {"name": f"Lincoln Boosters {suffix}", "email": f"boosters-{suffix}@example.com", "phone": "555-201-0000"},
        "contact": {"name": "Pat Organizer"},
        "store_type": store_type,
        "store_name": f"Lincoln Store {suffix}",
        "purpose": "Spirit wear",
        **extra,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _accept(link: str) -> str:
    raw = link.split("t=", 1)[1]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as public:
        accepted = await public.post("/api/portal/webstores/invitations/accept", json={"token": raw})
    assert accepted.status_code == 200, accepted.text
    return accepted.json()["token"]


async def _sent_store(client: AsyncClient, suffix: str, store_type: str = "event") -> tuple[dict, str]:
    created = await _request(client, suffix, store_type)
    sent = (await client.post(f"/api/webstores/{created['webstore']['id']}/information-packet/send", json={})).json()
    return created["webstore"], await _accept(sent["questionnaire_link"])


async def test_request_links_customer_dedupes_and_shows_request_received(ctx):
    async with await _staff(ctx["user"]) as client:
        created = await _request(client, ctx["suffix"])
        store = created["webstore"]
        assert store["status"] == "draft" and store["store_type"] == "event"
        owner = await db.webstore_owners.find_one({"id": created["owner_id"]}, {"_id": 0})
        assert owner["customer_id"] == created["customer_id"] and owner.get("organization") is None
        assert await db.webstore_invitations.count_documents({"tenant_id": ctx["tenant_id"], "webstore_id": store["id"], "status": "sent"}) == 0

        matches = (await client.get("/api/webstores/setup/customer-matches", params={"email": f"BOOSTERS-{ctx['suffix']}@example.com"})).json()["items"]
        assert [m["customer"]["id"] for m in matches] == [created["customer_id"]] and matches[0]["strong"]
        duplicate = await client.post("/api/webstores/requests", json={
            "new_customer": {"name": "Someone Else", "phone": "(555) 201-0000"}, "contact": {"email": f"x-{ctx['suffix']}@example.com"}, "store_type": "general",
        })
        assert duplicate.status_code == 409 and "already exists" in duplicate.text

        again = await client.post("/api/webstores/requests", json={"customer_id": created["customer_id"], "store_type": "employee_company", "store_name": f"Staff Store {ctx['suffix']}"})
        assert again.status_code == 201, again.text
        assert again.json()["owner_id"] == created["owner_id"]  # same contact email reused
        assert again.json()["webstore"]["store_type"] == "b2b"
        assert again.json()["webstore"]["setup_profile"]["b2b_preset"] == "employee_company"
        assert await db.customers.count_documents({"tenant_id": ctx["tenant_id"]}) == 1

        bad_email = await client.post("/api/webstores/requests", json={"new_customer": {"name": "Bad Email Co", "email": "not-an-email@@x"}, "store_type": "general"})
        assert bad_email.status_code == 400 and "email" in bad_email.text

    async with await _staff(ctx["other_user"]) as other:
        assert (await other.get("/api/webstores/setup/customer-matches", params={"email": f"boosters-{ctx['suffix']}@example.com"})).json()["items"] == []


async def test_intake_starts_the_same_request_once(ctx):
    customer_id = f"cust-{ctx['suffix']}"
    await db.customers.insert_one({"id": customer_id, "tenant_id": ctx["tenant_id"], "name": "Field Day Club", "email": f"club-{ctx['suffix']}@example.com"})
    intake_id = f"intake-{ctx['suffix']}"
    await db.intake_submissions.insert_one({"id": intake_id, "tenant_id": ctx["tenant_id"], "intake_number": 7, "status": "submitted", "customer_id": customer_id, "intake_type": "webstore"})
    async with await _staff(ctx["user"]) as client:
        resp = await client.post("/api/webstores/requests", json={"intake_id": intake_id, "store_type": "general"})
        assert resp.status_code == 201, resp.text
        intake = await db.intake_submissions.find_one({"id": intake_id}, {"_id": 0})
        assert intake["status"] == "converted_to_webstore" and intake["webstore_id"] == resp.json()["webstore"]["id"]
        assert resp.json()["webstore"]["source_intake_id"] == intake_id
        assert (await client.post("/api/webstores/requests", json={"intake_id": intake_id})).status_code == 409


async def test_packet_preview_send_once_resend_and_failure_fallback(ctx):
    async with await _staff(ctx["user"]) as client:
        store = (await _request(client, ctx["suffix"], "fundraiser"))["webstore"]
        preview = (await client.get(f"/api/webstores/{store['id']}/information-packet")).json()
        assert preview["delivery"]["status"] == "prepared"
        assert "fundraiser" in preview["preview"]["body"].lower() and "final sale" in preview["preview"]["body"].lower()
        assert preview["preview"]["reply_to"] == f"orders-{ctx['suffix']}@signshop.example"
        assert "bank" in preview["preview"]["body"] and "{{" not in preview["preview"]["body"]

        sent = (await client.post(f"/api/webstores/{store['id']}/information-packet/send", json={})).json()
        link = sent["questionnaire_link"]
        assert link.startswith(public_url("/portal/webstores/invitations/accept?t="))
        assert sent["delivery"]["status"] == "failed"  # SendGrid is not configured in tests: never a real email
        log = await db.email_logs.find_one({"tenant_id": ctx["tenant_id"], "related_id": store["id"], "template": "webstore_information_packet"}, {"_id": 0})
        assert log["status"] == "skipped" and link in log["body"] and log["reply_to"] == preview["preview"]["reply_to"]
        assert (await db.webstores.find_one({"id": store["id"]}, {"_id": 0}))["status"] == "questionnaire_sent"

        repeat = (await client.post(f"/api/webstores/{store['id']}/information-packet/send", json={})).json()
        assert repeat["already_sent"] is True and repeat["sent_count"] == 1
        resent = (await client.post(f"/api/webstores/{store['id']}/information-packet/send", json={"resend": True})).json()
        assert resent["sent_count"] == 2 and resent["questionnaire_link"] != link
        statuses = [i["status"] async for i in db.webstore_invitations.find({"tenant_id": ctx["tenant_id"], "webstore_id": store["id"]}, {"_id": 0})]
        assert statuses.count("superseded") >= 1 and await db.email_logs.count_documents({"related_id": store["id"], "template": "webstore_information_packet"}) == 2

        # A verified SendGrid "delivered" event for this email's log shows as delivered.
        last = await db.email_logs.find_one({"related_id": store["id"], "template": "webstore_information_packet"}, {"_id": 0}, sort=[("created_at", -1)])
        await db.email_activity.insert_one({"id": f"a-{ctx['suffix']}", "tenant_id": ctx["tenant_id"], "provider": "sendgrid", "provider_event_id": f"ev-{ctx['suffix']}",
                                            "email_log_id": last["id"], "to_email": last["to_email"], "event": "delivered", "event_timestamp": "2099-01-01T00:00:00+00:00"})
        assert (await client.get(f"/api/webstores/{store['id']}/information-packet")).json()["delivery"]["status"] == "delivered"


async def test_owner_sees_shop_supported_methods_and_conditional_questions(ctx):
    async with await _staff(ctx["user"]) as client:
        bad = await client.put("/api/webstores/setup/fulfillment-settings", json={"supported_methods": ["teleport"]})
        assert bad.status_code == 400
        saved = await client.put("/api/webstores/setup/fulfillment-settings", json={"supported_methods": ["shop_pickup", "organizer_pickup"], "default_pickup_location": "123 Main St"})
        assert saved.status_code == 200 and saved.json()["supported_methods"] == ["shop_pickup", "organizer_pickup"]
        store, token = await _sent_store(client, ctx["suffix"])
    async with _portal(token) as portal:
        q = (await portal.get(f"/api/portal/webstores/{store['id']}/questionnaire")).json()
        assert [t["store_type"] for t in q["templates"]] == ["base", "event"]
        assert "Thanks for choosing" in q["welcome"]["body"]
        questions = {qq["key"]: qq for t in q["templates"] for s in t["sections"] for qq in s["questions"]}
        assert [o["value"] for o in questions["fulfillment_methods"]["options"]] == ["shop_pickup", "organizer_pickup"]
        assert questions["pickup_window_2_date"]["conditional"]["depends_on"] == "pickup_window_count"
        assert not any(k in questions for k in ("bank_account", "routing_number", "stripe_email", "signature"))

        # Hidden required questions (personalization details, pickup window 2) never block.
        answers = complete_answers("event", fulfillment_methods=["organizer_pickup"], pickup_window_count="1",
                                   pickup_window_1_date="2099-03-25", pickup_window_1_start="15:00", pickup_window_1_end="18:00")
        missing_window = await portal.post(f"/api/portal/webstores/{store['id']}/questionnaire", json={"answers": {**answers, "pickup_window_count": "2"}})
        assert missing_window.status_code == 400 and "pickup_window_2_date" in missing_window.text
        ok = await portal.post(f"/api/portal/webstores/{store['id']}/questionnaire", json={"answers": answers})
        assert ok.status_code == 200, ok.text
        assert ok.json()["acknowledgement"]["version"] and ok.json()["acknowledgement"]["revision"] == 1


async def test_review_brief_checks_approve_apply_and_revision_comparison(ctx):
    async with await _staff(ctx["user"]) as client:
        store, token = await _sent_store(client, ctx["suffix"], "fundraiser")
    first = complete_answers(
        "fundraiser", fulfillment_methods=["organizer_pickup", "individual_shipping"], pickup_window_count="2",
        pickup_window_1_date="2099-03-25", pickup_window_1_start="15:00", pickup_window_1_end="18:00",
        pickup_window_2_date="2099-02-01", pickup_window_2_start="10:00", pickup_window_2_end="12:00", pickup_window_2_location="North lot",
        fundraiser_goal_amount="2500.50", allow_checkout_donations="yes", bag_label_orders="yes",
        personalization_needed="yes", personalization_details="Player names",
    )
    async with _portal(token) as portal:
        sub1 = (await portal.post(f"/api/portal/webstores/{store['id']}/questionnaire", json={"answers": first})).json()
        retry = (await portal.post(f"/api/portal/webstores/{store['id']}/questionnaire", json={"answers": first})).json()
    assert retry["id"] == sub1["id"]
    notes = [n async for n in db.notifications.find({"tenant_id": ctx["tenant_id"], "entity_id": store["id"]}, {"_id": 0, "kind": 1})]
    assert [n["kind"] for n in notes].count("webstore.questionnaire_submitted") == 1
    assert [n["kind"] for n in notes].count("webstore.questionnaire_correction_needed") == 1  # pickup before opening

    async with await _staff(ctx["user"]) as client:
        review = (await client.get(f"/api/webstores/{store['id']}/questionnaire/review")).json()
        assert {w["code"] for w in review["warnings"]} == {"pickup_before_store_opens"}
        assert any(s["title"] == "Fundraiser" for s in review["brief"]) and review["comparison"] == []
        returned = await client.post(f"/api/webstores/{store['id']}/questionnaire/{sub1['id']}/return", json={"reason": "Fix pickup 2 date"})
        assert returned.status_code == 200
        assert await db.notifications.count_documents({"tenant_id": ctx["tenant_id"], "kind": "webstore.questionnaire_returned"}) == 1

    second = {**first, "pickup_window_2_date": "2099-03-26", "pickup_location": "Lincoln High main gym", "colors_to_avoid": "Red"}
    async with _portal(token) as portal:
        reopened = (await portal.get(f"/api/portal/webstores/{store['id']}/questionnaire")).json()
        assert reopened["submission"]["id"] == sub1["id"] and reopened["latest_revision"]["status"] == "returned_for_changes"
        sub2 = (await portal.post(f"/api/portal/webstores/{store['id']}/questionnaire", json={"answers": second})).json()
        after = (await portal.get(f"/api/portal/webstores/{store['id']}/questionnaire")).json()
    assert sub2["revision"] == 2
    assert after["submission"] is None and after["latest_revision"]["status"] == "submitted"  # form closes after resubmit

    async with await _staff(ctx["user"]) as client:
        review = (await client.get(f"/api/webstores/{store['id']}/questionnaire/review")).json()
        assert review["warnings"] == [] and review["previous_revision"] == 1
        rows = {r["key"]: r for r in review["comparison"]}
        assert rows["pickup_location"]["change"] == "changed" and rows["pickup_location"]["material"] is True
        assert rows["colors_to_avoid"]["change"] == "added" and rows["colors_to_avoid"]["material"] is False
        assert rows["pickup_window_2_date"]["affects_settings"] is True

        approved = await client.post(f"/api/webstores/{store['id']}/questionnaire/{sub2['id']}/approve")
        assert approved.status_code == 200, approved.text
        again = await client.post(f"/api/webstores/{store['id']}/questionnaire/{sub2['id']}/approve")
        assert again.json()["idempotent_replay"] is True
    applied = await db.webstores.find_one({"id": store["id"]}, {"_id": 0})
    settings = applied["store_settings"]
    assert settings["fulfillment"]["methods"] == ["organizer_pickup", "individual_shipping"]
    assert settings["fulfillment"]["method"] == "organizer_pickup"
    assert settings["fulfillment"]["pickup_location"] == "Lincoln High main gym"
    assert settings["fulfillment"]["pickup_windows"] == [
        {"date": "2099-03-25", "start": "15:00", "end": "18:00", "location": "", "instructions": ""},
        {"date": "2099-03-26", "start": "10:00", "end": "12:00", "location": "North lot", "instructions": ""},
    ]
    assert settings["fulfillment"]["bag_and_label"] is True
    assert settings["fundraiser"]["purpose"] == "New band uniforms" and settings["fundraiser"]["goal_amount_cents"] == 250050
    assert settings["donation"]["enabled"] is True and settings["production"]["personalization_enabled"] is True
    assert applied["deadline_at"] == "2099-03-20" and applied["name"] == "Lincoln Spirit Store"
    assert applied["setup_state"] in {"setup_in_progress", "setup_complete"}
    assert (await db.webstore_questionnaire_submissions.find_one({"id": sub1["id"]}, {"_id": 0}))["submitted_snapshot"]["answers"]["pickup_window_2_date"] == "2099-02-01"


def test_core_consistency_checks():
    def submission(answers: dict, sections: list) -> dict:
        return {"submitted_snapshot": {"answers": answers, "template_snapshot": {"templates": [{"sections": sections}]}}}

    sections = [{"id": "s", "questions": [
        {"key": k, "type": "text"} for k in ("target_launch_at", "deadline_at", "event_start_at", "fulfillment_methods", "allow_checkout_donations", "bag_label_orders", "pickup_window_1_date")
    ]}]
    sub = submission({
        "target_launch_at": "2099-03-10", "deadline_at": "2099-03-01", "event_start_at": "2099-03-05",
        "fulfillment_methods": ["individual_shipping", "local_delivery"], "allow_checkout_donations": "yes",
        "bag_label_orders": "yes", "pickup_window_1_date": "2099-03-08",
    }, sections)
    codes = {w["code"] for w in consistency_checks({}, sub, {"supported_methods": ["individual_shipping"]})}
    assert codes == {"closing_before_opening", "pickup_before_store_opens", "pickup_after_event", "unsupported_fulfillment_method", "donations_without_purpose"}
    only_shipping = submission({"fulfillment_methods": ["individual_shipping"], "bag_label_orders": "yes"}, sections)
    assert {w["code"] for w in consistency_checks({}, only_shipping, {"supported_methods": ["individual_shipping"]})} == {"bagging_with_individual_shipping"}


async def test_questionnaire_uploads_use_canonical_files(ctx):
    async with await _staff(ctx["user"]) as client:
        store, token = await _sent_store(client, ctx["suffix"])
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    async with _portal(token) as portal:
        up = await portal.post(f"/api/portal/webstores/{store['id']}/setup-files", data={"category": "logo_file"}, files={"file": ("logo.png", png, "image/png")})
        assert up.status_code == 201, up.text
        listed = (await portal.get(f"/api/portal/webstores/{store['id']}/setup-files")).json()["items"]
    link = await db.file_links.find_one({"tenant_id": ctx["tenant_id"], "id": up.json()["file"]["id"]}, {"_id": 0})
    assert link["parent_type"] == "webstore" and link["parent_id"] == store["id"] and link["role"] == "logo_file"
    assert await db.files.count_documents({"tenant_id": ctx["tenant_id"], "id": link["file_id"]}) == 1
    assert [i["id"] for i in listed] == [link["id"]]
