"""Real raster composition and canonical submission/security regressions; no provider calls."""
import hashlib
import io

import pytest
from PIL import Image

from app.core.db import db
from app.services.webstore_mockup_composition import _render
from app.services.webstore_shared_contracts import WebstoreError
from tests.test_webstores_stage4b_owner_approval import (
    stage4b_ctx, _client_as, _portal_client, _create_ready_store, _owner_token,
    _submit_product_for_approval, _submit_mockup_for_approval, _approve_product_and_mockup,
)
from tests.test_webstores_owner_product_visibility import _owner_read


def _png(size, color):
    image = Image.new("RGBA", size, color)
    result = io.BytesIO(); image.save(result, format="PNG")
    return result.getvalue()


async def _setup(staff, ctx):
    built = await _create_ready_store(staff, ctx)
    store = built["store"]
    product = (await staff.post(f"/api/webstores/{store['id']}/products", json={"name": "Navy School T-shirt", "product_type": "t-shirt",
        "selling_price_cents": 2500, "variants": [{"id": "navy-m", "color": "Navy", "size": "M", "selling_price_cents": 2500}]})).json()
    files = []
    source_bytes = [_png((400, 400), (20, 40, 80, 255)), _png((80, 40), (255, 200, 0, 128))]
    for name, data in zip(["navy-blank.png", "original-logo.png"], source_bytes):
        response = await staff.post(f"/api/webstores/{store['id']}/setup-files", data={"category": "artwork"}, files={"file": (name, data, "image/png")})
        assert response.status_code == 201, response.text
        files.append(response.json()["file"])
    fields = {"expected_revision": product["revision"], "blank_file_id": files[0]["id"], "artwork_file_id": files[1]["id"],
        "variant_id": "navy-m", "blank_matches_product": True, "placement": {"x": .25, "y": .25, "width": .5, "height": .5}}
    return built, product, files, source_bytes, fields


async def test_composition_preview_accept_submit_approve_and_private_revision(stage4b_ctx):
    ctx = stage4b_ctx
    async with await _client_as(ctx["staff"]) as staff:
        built, product, sources, original_bytes, fields = await _setup(staff, ctx)
        store = built["store"]; base = f"/api/webstores/{store['id']}/products/{product['id']}/mockup-composition"
        token = await _owner_token(ctx, built["owner"])
        count = await db.file_links.count_documents({"tenant_id": ctx["tenant_id"]})
        preview = await staff.post(base + "/preview", json=fields)
        assert preview.status_code == 200, preview.text
        assert preview.headers["content-type"] == "image/png" and preview.headers["cache-control"] == "private, no-store"
        assert preview.headers["access-control-expose-headers"] == "X-Preview-SHA256"
        assert await db.file_links.count_documents({"tenant_id": ctx["tenant_id"]}) == count
        image = Image.open(io.BytesIO(preview.content))
        assert image.size == (400, 400)
        assert image.getpixel((0, 0)) == (20, 40, 80, 255)
        assert image.getpixel((200, 200)) != image.getpixel((0, 0))
        accepted = await staff.post(base, json={**fields, "preview_sha256": preview.headers["x-preview-sha256"], "reviewed": True, "alt_text": "Navy school tee with original logo"})
        assert accepted.status_code == 201, accepted.text
        result = accepted.json(); mockup = result["mockup"]
        assert mockup["shop_approved"] and not mockup["owner_visible"] and mockup["approval_status"] == "not_submitted"
        assert mockup["generation_source"] == "deterministic_composition"
        assert mockup["preparation"]["artwork_sha256"] == hashlib.sha256(original_bytes[1]).hexdigest()
        for file, data in zip(sources, original_bytes):
            assert (await staff.get(f"/api/webstores/{store['id']}/setup-files/{file['id']}/preview")).content == data
        stored = await staff.get(f"/api/webstores/{store['id']}/setup-files/{result['file']['id']}/preview")
        assert stored.content == preview.content
        product = (await staff.patch(f"/api/webstores/{store['id']}/products/{product['id']}", json={"expected_revision": product["revision"],
            "artwork_associations": [{"artwork_id": result["artwork"]["id"]}], "mockup_associations": [{"mockup_id": mockup["id"]}]})).json()
    assert product["id"] not in str(await _owner_read(token, store))
    owner_image = f"/api/portal/webstores/{store['id']}/products/{product['id']}/mockups/{mockup['id']}/image"
    async with await _portal_client(token) as owner:
        assert (await owner.get(owner_image)).status_code == 404
        for file in [*sources, result["file"]]:
            assert (await owner.get(f"/api/portal/webstores/{store['id']}/setup-files/{file['id']}/download")).status_code == 404
        assert (await owner.post(base + "/preview", json=fields)).status_code in {401, 403}
    async with await _client_as(ctx["staff"]) as staff:
        await _submit_product_for_approval(staff, store, product)
        await _submit_mockup_for_approval(staff, store, mockup)
    await _approve_product_and_mockup(ctx, token, store, product, mockup)
    async with await _portal_client(token) as owner:
        assert (await owner.get(owner_image)).content == preview.content
    frozen = (await db.webstore_products.find_one({"tenant_id": ctx["tenant_id"], "id": product["id"]}))["approval_snapshot"]
    async with await _client_as(ctx["staff"]) as staff:
        revised_fields = {**fields, "expected_revision": product["revision"], "placement": {"x": .1, "y": .1, "width": .3, "height": .3}}
        private = await staff.post(base + "/preview", json=revised_fields)
        revision = (await staff.post(base, json={**revised_fields, "preview_sha256": private.headers["x-preview-sha256"], "reviewed": True, "alt_text": "PRIVATE placement revision"})).json()
        changed = await staff.patch(f"/api/webstores/{store['id']}/products/{product['id']}", json={"expected_revision": product["revision"], "mockup_associations": [{"mockup_id": revision["mockup"]["id"]}]})
        assert changed.status_code == 200, changed.text
    async with await _portal_client(token) as owner:
        assert (await owner.get(owner_image)).content == preview.content
        assert (await owner.get(owner_image.replace(mockup["id"], revision["mockup"]["id"]))).status_code == 404
    assert "PRIVATE" not in str(await _owner_read(token, store))
    persisted = await db.webstore_products.find_one({"tenant_id": ctx["tenant_id"], "id": product["id"]})
    assert persisted["approval_snapshot"] == frozen
    for collection in (db.ai_action_requests, db.ai_credit_ledger_entries, db.ai_usage_ledger_entries, db.ai_provider_cost_ledger_entries):
        assert await collection.count_documents({"tenant_id": ctx["tenant_id"]}) == 0


async def test_composition_validation_permissions_and_preview_identity(stage4b_ctx):
    ctx = stage4b_ctx
    async with await _client_as(ctx["staff"]) as staff:
        built, product, files, _, fields = await _setup(staff, ctx)
        store = built["store"]; base = f"/api/webstores/{store['id']}/products/{product['id']}/mockup-composition"
        for edit, expected in [({"expected_revision": 900}, 409), ({"variant_id": "foreign"}, 409), ({"blank_matches_product": False}, 422),
            ({"artwork_file_id": "foreign-file"}, 404), ({"placement": {"x": .9, "y": .2, "width": .5, "height": .5}}, 422), ({"free": True}, 422)]:
            response = await staff.post(base + "/preview", json={**fields, **edit})
            assert response.status_code == expected, response.text
        preview = await staff.post(base + "/preview", json=fields)
        accepted = {**fields, "preview_sha256": preview.headers["x-preview-sha256"], "reviewed": True, "alt_text": "Logo on front"}
        assert (await staff.post(base, json={**accepted, "reviewed": False})).status_code == 422
        assert (await staff.post(base, json={**accepted, "placement": {"x": .1, "y": .1, "width": .5, "height": .5}})).status_code == 409
        assert (await staff.post(base, json={**accepted, "preview_sha256": "0" * 64})).status_code == 409
        # The existing upload signature alone cannot make a malformed raster safe to decode.
        bad = (await staff.post(f"/api/webstores/{store['id']}/setup-files", data={"category": "artwork"}, files={"file": ("broken.png", b"\x89PNG\r\n\x1a\ninvalid", "image/png")})).json()["file"]
        assert (await staff.post(base + "/preview", json={**fields, "artwork_file_id": bad["id"]})).status_code == 400
        for name, content, mime in [("vector.svg", b'<svg width="40" height="40"><path d="M0 0h40v40z"/></svg>', "image/svg+xml"), ("art.pdf", b"%PDF-1.4 fixture", "application/pdf")]:
            vector = await staff.post(f"/api/webstores/{store['id']}/setup-files", data={"category": "artwork"}, files={"file": (name, content, mime)})
            assert vector.status_code == 201, vector.text
            assert (await staff.post(base + "/preview", json={**fields, "artwork_file_id": vector.json()["file"]["id"]})).status_code == 400
        await db.file_links.insert_one({"id": "foreign-" + ctx["suffix"], "tenant_id": ctx["other_tenant_id"],
            "parent_type": "webstore", "parent_id": store["id"], "file_id": files[1]["file_id"] if "file_id" in files[1] else "foreign-record", "role": "artwork"})
        assert (await staff.post(base + "/preview", json={**fields, "artwork_file_id": "foreign-" + ctx["suffix"]})).status_code == 404
        await db.webstore_products.update_one({"tenant_id": ctx["tenant_id"], "id": product["id"]}, {"$set": {"variants.0.available": False}})
        assert (await staff.post(base + "/preview", json=fields)).status_code == 409
        await db.webstore_products.update_one({"tenant_id": ctx["tenant_id"], "id": product["id"]}, {"$set": {"product_type": "hat"}})
        assert (await staff.post(base + "/preview", json=fields)).status_code == 409
    for user, status in [(ctx["other_staff"], 404), ({**ctx["staff"], "role": "viewer"}, 403), ({**ctx["staff"], "webstore_id": "different"}, 403)]:
        async with await _client_as(user) as client:
            assert (await client.post(base + "/preview", json=fields)).status_code == status


def test_composition_preserves_artwork_aspect_ratio_pixels_and_transparency():
    source = Image.new("RGBA", (200, 200), (0, 0, 100, 255))
    private_exif = Image.Exif(); private_exif[270] = "Private camera metadata"
    raw = io.BytesIO(); source.save(raw, format="PNG", exif=private_exif)
    blank = raw.getvalue()
    art = Image.new("RGBA", (80, 40), (0, 0, 0, 0)); art.putpixel((40, 20), (255, 10, 20, 255))
    data = io.BytesIO(); art.save(data, format="PNG")
    png, _ = _render(blank, data.getvalue(), {"x": .3, "y": .4, "width": .4, "height": .2})
    result = Image.open(io.BytesIO(png))
    assert result.getpixel((100, 100)) == (255, 10, 20, 255)
    assert result.getpixel((60, 80)) == (0, 0, 100, 255)
    assert result.getpixel((0, 0)) == (0, 0, 100, 255)
    assert not result.info.get("exif") and not result.getexif()


@pytest.mark.parametrize("kind", ["animated", "oversized", "invalid"])
def test_composition_rejects_unsafe_or_unsupported_decode(kind):
    stream = io.BytesIO()
    if kind == "animated":
        Image.new("RGBA", (20, 20), "red").save(stream, format="PNG", save_all=True, append_images=[Image.new("RGBA", (20, 20), "blue")])
    elif kind == "oversized":
        Image.new("RGB", (6001, 16)).save(stream, format="PNG")
    else:
        stream.write(b"not an image")
    with pytest.raises(WebstoreError):
        _render(_png((200, 200), "white"), stream.getvalue(), {"x": 0, "y": 0, "width": 1, "height": 1})
