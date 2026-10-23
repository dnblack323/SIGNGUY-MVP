"""Manual mockups use canonical private files and submitted product evidence."""
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.core.portal_security import create_portal_token
from app.services.portal_identity import create_portal_identity
from server import app
from tests.test_webstores_stage4b_owner_approval import (
    stage4b_ctx, _client_as, _portal_client, _create_ready_store, _owner_token,
    _submit_product_for_approval, _submit_mockup_for_approval, _approve_product_and_mockup,
)
from tests.test_webstores_owner_product_visibility import _owner_read


async def _upload(client, store, name, content, category, replaces=None):
    response = await client.post(f"/api/webstores/{store['id']}/setup-files",
        data={"category": category, **({"replaces_file_id": replaces} if replaces else {})}, files={"file": (name, b"\x89PNG\r\n\x1a\n" + content, "image/png")})
    assert response.status_code == 201, response.text
    return response.json()["file"]


@pytest.mark.parametrize("decision", ["approve", "request_changes"])
async def test_private_mockup_preparation_submission_review_and_replacement(stage4b_ctx, decision):
    ctx = stage4b_ctx
    async with await _client_as(ctx["staff"]) as staff:
        built = await _create_ready_store(staff, ctx)
        store, original = built["store"], built["product"]
        token = await _owner_token(ctx, built["owner"])
    await _approve_product_and_mockup(ctx, token, store, original, built["mockup"])
    original_view = (await _owner_read(token, store))["products"][0]
    async with await _client_as(ctx["staff"]) as staff:
        product = (await staff.post(f"/api/webstores/{store['id']}/products", json={"name": "Navy Hat", "product_type": "hat"})).json()
        artwork_file = await _upload(staff, store, "customer-art.png", b"art", "artwork")
        image = await _upload(staff, store, "hat-front.png", b"first-mockup", "mockup")
        art = await staff.post(f"/api/webstores/{store['id']}/artwork", json={"product_id": product["id"], "file_id": artwork_file["id"], "file_name": "Customer artwork"})
        assert art.status_code == 201, art.text
        mockup = await staff.post(f"/api/webstores/{store['id']}/mockups", json={"product_id": product["id"], "artwork_id": art.json()["id"], "mockup_file_id": image["id"], "alt_text": "Navy Hat front", "shop_approved": True})
        assert mockup.status_code == 201, mockup.text
        mockup = mockup.json()
        edit = await staff.patch(f"/api/webstores/{store['id']}/products/{product['id']}", json={"expected_revision": product["revision"], "selling_price_cents": 3200,
            "variants": [{"id": "navy", "color": "Navy", "size": "Adjustable", "selling_price_cents": 3200}],
            "artwork_associations": [{"artwork_id": art.json()["id"]}], "mockup_associations": [{"mockup_id": mockup["id"]}]})
        assert edit.status_code == 200, edit.text
        product = edit.json()
        listed = (await staff.get(f"/api/webstores/{store['id']}/mockups", params={"product_id": product["id"]})).json()["items"]
        assert listed[0]["mockup_file_id"] == image["id"]
    path = f"/api/portal/webstores/{store['id']}/products/{product['id']}/mockups/{mockup['id']}/image"
    assert product["id"] not in str(await _owner_read(token, store))
    async with await _portal_client(token) as owner:
        assert (await owner.get(path)).status_code == 404
        files = (await owner.get(f"/api/portal/webstores/{store['id']}/setup-files")).json()
        assert image["id"] not in str(files) and artwork_file["id"] not in str(files)
        for file in (image, artwork_file):
            assert (await owner.get(f"/api/portal/webstores/{store['id']}/setup-files/{file['id']}/download")).status_code == 404
    async with await _client_as(ctx["staff"]) as staff:
        await _submit_product_for_approval(staff, store, product)
        await _submit_mockup_for_approval(staff, store, mockup)
    shared = next(p for p in (await _owner_read(token, store))["products"] if p["id"] == product["id"])
    assert shared["mockups"][0]["image_url"].startswith(path)
    assert "mockup_file_id" not in str(shared) and "storage_key" not in str(shared)
    async with await _portal_client(token) as owner:
        response = await owner.get(path)
        assert response.status_code == 200 and response.content.endswith(b"first-mockup")
        assert response.headers["cache-control"] == "private, no-store"
        # A customer may review the mockup before the product itself.
        response = await owner.post(f"/api/portal/webstores/{store['id']}/mockups/{mockup['id']}/approval", json={"decision": decision, "comment": "Review result"})
        assert response.status_code == 200, response.text
        if decision == "approve":
            response = await owner.post(f"/api/portal/webstores/{store['id']}/products/{product['id']}/approval", json={"decision": "approve"})
            assert response.status_code == 200, response.text
    persisted = await db.webstore_products.find_one({"tenant_id": ctx["tenant_id"], "id": product["id"]})
    submitted_snapshot = persisted["approval_snapshot"]
    async with await _client_as(ctx["staff"]) as staff:
        replacement = await _upload(staff, store, "PRIVATE-hat-back.png", b"private-replacement", "mockup", replaces=image["id"])
        new_mockup = (await staff.post(f"/api/webstores/{store['id']}/mockups", json={"product_id": product["id"], "mockup_file_id": replacement["id"], "alt_text": "PRIVATE back view", "shop_approved": True})).json()
        response = await staff.patch(f"/api/webstores/{store['id']}/products/{product['id']}", json={"expected_revision": product["revision"], "name": "PRIVATE Hat revision", "mockup_associations": [{"mockup_id": new_mockup["id"]}]})
        assert response.status_code == 200, response.text
        product = response.json()
    private_path = path.replace(mockup["id"], new_mockup["id"])
    detail = await _owner_read(token, store)
    retained = next(p for p in detail["products"] if p["id"] == product["id"])
    assert "PRIVATE" not in str(detail) and retained["review_notice"]
    assert retained["mockups"][0]["id"] == mockup["id"]
    assert retained["mockups"][0]["approval_status"] == ("approved" if decision == "approve" else "changes_requested")
    assert next(p for p in detail["products"] if p["id"] == original["id"]) == original_view
    persisted = await db.webstore_products.find_one({"tenant_id": ctx["tenant_id"], "id": product["id"]})
    assert persisted["approval_snapshot"] == submitted_snapshot
    async with await _portal_client(token) as owner:
        assert (await owner.get(path)).content.endswith(b"first-mockup")
        assert (await owner.get(private_path)).status_code == 404
        assert (await owner.post(f"/api/portal/webstores/{store['id']}/mockups/{mockup['id']}/approval", json={"decision": "approve"})).status_code == 409
    async with await _client_as(ctx["staff"]) as staff:
        await _submit_product_for_approval(staff, store, product)
        await _submit_mockup_for_approval(staff, store, new_mockup)
    async with await _portal_client(token) as owner:
        assert (await owner.get(private_path)).content.endswith(b"private-replacement")
        assert (await owner.get(path)).status_code == 404
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as public:
        assert (await public.get(private_path)).status_code == 401
    # Removing all explicit selections must not resurrect owner_visible records.
    async with await _client_as(ctx["staff"]) as staff:
        removed = await staff.patch(f"/api/webstores/{store['id']}/products/{product['id']}", json={"expected_revision": product["revision"], "mockup_associations": []})
        assert removed.status_code == 200, removed.text
        await _submit_product_for_approval(staff, store, removed.json())
    empty = next(p for p in (await _owner_read(token, store))["products"] if p["id"] == product["id"])
    assert empty["mockups"] == []


async def test_mockup_staff_review_and_tenant_authorization(stage4b_ctx):
    ctx = stage4b_ctx
    async with await _client_as(ctx["staff"]) as staff:
        built = await _create_ready_store(staff, ctx)
        store, product = built["store"], built["product"]
        file = await _upload(staff, store, "unreviewed.png", b"unreviewed", "mockup")
        draft = (await staff.post(f"/api/webstores/{store['id']}/mockups", json={"product_id": product["id"], "mockup_file_id": file["id"]})).json()
        assert (await staff.post(f"/api/webstores/{store['id']}/mockups/{draft['id']}/submit-approval", json={})).status_code == 409
        updated = (await staff.patch(f"/api/webstores/{store['id']}/products/{product['id']}", json={"expected_revision": product["revision"], "mockup_associations": [{"mockup_id": draft["id"]}]})).json()
        assert (await staff.post(f"/api/webstores/{store['id']}/products/{product['id']}/submit-approval", json={"expected_revision": updated["revision"]})).status_code == 409
        await db.webstore_artwork_files.insert_one({"tenant_id": ctx["other_tenant_id"], "webstore_id": store["id"], "id": "foreign-art"})
        assert (await staff.post(f"/api/webstores/{store['id']}/mockups", json={"product_id": product["id"], "artwork_id": "foreign-art", "mockup_file_id": file["id"]})).status_code == 404
    async with await _client_as(ctx["other_staff"]) as foreign:
        assert (await foreign.get(f"/api/webstores/{store['id']}/mockups")).status_code == 404
        assert (await foreign.get(f"/api/webstores/{store['id']}/setup-files/{file['id']}/preview")).status_code in {403, 404}
    async with await _client_as({**ctx["staff"], "role": "viewer"}) as readonly:
        assert (await readonly.post(f"/api/webstores/{store['id']}/mockups", json={"product_id": product["id"]})).status_code == 403
    token = await _owner_token(ctx, built["owner"])
    foreign = await create_portal_identity(tenant_id=ctx["other_tenant_id"], portal_type="webstore_owner", webstore_owner_id=built["owner"]["id"], email="foreign-" + ctx["suffix"] + "@example.com", full_name="Foreign")
    foreign_token = create_portal_token(portal_identity_id=foreign["id"], tenant_id=ctx["other_tenant_id"], portal_type="webstore_owner")
    path = f"/api/portal/webstores/{store['id']}/products/{product['id']}/mockups/{draft['id']}/image"
    async with await _portal_client(foreign_token) as owner:
        assert (await owner.get(path)).status_code in {403, 404}
    await db.webstore_access_assignments.update_one({"tenant_id": ctx["tenant_id"], "webstore_id": store["id"], "portal_identity_id": built["owner"]["portal_identity_id"]}, {"$set": {"status": "revoked"}})
    async with await _portal_client(token) as owner:
        assert (await owner.get(path)).status_code == 403
