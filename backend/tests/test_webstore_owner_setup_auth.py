"""Owner-only Store Setup reads preserve the staff/portal permission boundary."""
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.core.security import create_access_token
from app.deps import get_current_user
from server import app
from tests.test_webstores_stage2_setup import stage2_ctx, _client_as, _create_store  # noqa: F401


@pytest.mark.asyncio
async def test_owner_only_setup_files_are_scoped_and_staff_auth_stays_separate(stage2_ctx):
    async with await _client_as(stage2_ctx["user"]) as staff:
        created = await _create_store(staff, stage2_ctx["suffix"])
        other = await _create_store(staff, stage2_ctx["suffix"] + "-other")
        store_id = created["store"]["id"]
        assignment = (await staff.get(f"/api/webstores/{store_id}/assignments")).json()["items"][0]
        invitation = (await staff.post(f"/api/webstores/{store_id}/assignments/{assignment['id']}/resend")).json()
    app.dependency_overrides.pop(get_current_user, None)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as public:
        accepted = await public.post("/api/portal/webstores/invitations/accept", json={
            "token": invitation["invitation"]["invitation_url"].split("t=", 1)[1],
        })
        assert accepted.status_code == 200, accepted.text
        assert (await public.get(f"/api/portal/webstores/{store_id}/setup-files")).status_code == 401

    base = {"tenant_id": stage2_ctx["tenant_id"], "webstore_id": store_id,
            "category": "logo", "status": "active", "file_name": "owner-logo.png",
            "uploaded_by_id": "private-staff-id", "storage_key": "private-key"}
    await db.webstore_setup_files.insert_many([
        {**base, "id": "visible-logo"},
        {**base, "id": "removed-logo", "status": "removed"},
        {**base, "id": "other-store-logo", "webstore_id": other["store"]["id"]},
        {**base, "id": "other-tenant-logo", "tenant_id": stage2_ctx["other_tenant_id"]},
    ])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test",
                           headers={"Authorization": f"Bearer {accepted.json()['token']}"}) as owner:
        response = await owner.get(f"/api/portal/webstores/{store_id}/setup-files")
        assert response.status_code == 200, response.text
        assert [row["id"] for row in response.json()["items"]] == ["visible-logo"]
        assert not ({"storage_key", "uploaded_by_id", "preview_url", "tenant_id"} & response.json()["items"][0].keys())
        for suffix in ("", "/setup-files", "/setup-progress", "/branding", "/questionnaire"):
            assert (await owner.get(f"/api/portal/webstores/{store_id}{suffix}")).status_code == 200
        assert (await owner.get(f"/api/portal/webstores/{other['store']['id']}/setup-files")).status_code == 403
        assert (await owner.get(f"/api/webstores/{store_id}/setup-files")).status_code == 401
        assert (await owner.get(f"/api/portal/webstores/{store_id}/setup-files")).status_code == 200

    async with await _client_as(stage2_ctx["other_user"]) as staff:
        foreign = await _create_store(staff, stage2_ctx["suffix"] + "-foreign")
    app.dependency_overrides.pop(get_current_user, None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test",
                           headers={"Authorization": f"Bearer {accepted.json()['token']}"}) as owner:
        assert (await owner.get(f"/api/portal/webstores/{foreign['store']['id']}/setup-files")).status_code == 403
    staff_token = create_access_token(subject=stage2_ctx["user"]["id"], tenant_id=stage2_ctx["tenant_id"])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test",
                           headers={"Authorization": f"Bearer {staff_token}"}) as staff:
        assert (await staff.get(f"/api/portal/webstores/{store_id}/setup-files")).status_code == 401
