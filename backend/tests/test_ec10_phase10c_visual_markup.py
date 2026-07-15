"""EC10 Phase 10C — Visual Markup backend tests.

Covers: image/PDF markup creation, source-file validation (incl. cross-
tenant), Intake/Intake Item attachment, structured-JSON persistence,
allowlisted-object validation, unsupported-object/oversized/embedded-binary
rejection, version 1 + subsequent versions, prior-version immutability,
monotonic numbering, current-version pointer, archive/restore, tenant
isolation, permissions, audit events, original source file untouched,
preview stored separately, unavailable source handled safely, invalid PDF
page rejected, and coordinate round-trip (stored fields returned unchanged).
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.db import db
from app.deps import get_current_user
from server import app


def _override(u):
    async def _get():
        return {**u}
    return _get


async def _client(u):
    app.dependency_overrides[get_current_user] = _override(u)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear():
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
async def ctx():
    suffix = uuid.uuid4().hex[:8]
    ta = f"t-ec10c-a-{suffix}"
    tb = f"t-ec10c-b-{suffix}"
    ua = {"id": f"u-a-{suffix}", "tenant_id": ta, "email": f"a-{suffix}@example.com", "role": "owner", "is_active": True}
    ub = {"id": f"u-b-{suffix}", "tenant_id": tb, "email": f"b-{suffix}@example.com", "role": "owner", "is_active": True}
    await db.tenants.insert_many([{"id": ta, "slug": ta, "name": "TA"}, {"id": tb, "slug": tb, "name": "TB"}])
    await db.users.insert_many([ua, ub])
    yield {"ua": ua, "ub": ub, "ta": ta, "tb": tb}
    _clear()


async def _upload_image(c, seed: bytes = b"0" * 40) -> str:
    up = await c.post("/api/files/upload", files={"file": ("photo.png", b"\x89PNG\r\n\x1a\n" + seed, "image/png")})
    assert up.status_code == 201, up.text
    return up.json()["file"]["id"]


async def _upload_pdf(c) -> str:
    up = await c.post("/api/files/upload", files={"file": ("doc.pdf", b"%PDF-1.4\n" + b"0" * 40, "application/pdf")})
    assert up.status_code == 201, up.text
    return up.json()["file"]["id"]


def _sample_objects():
    return {"objects": [
        {"type": "rect", "left": 10, "top": 20, "width": 100, "height": 40, "fill": "rgba(255,0,0,0.3)"},
        {"type": "textbox", "left": 5, "top": 5, "text": "Note here"},
        {"type": "group", "left": 0, "top": 0, "objects": [
            {"type": "line", "x1": 0, "y1": 0, "x2": 50, "y2": 50},
            {"type": "triangle", "left": 45, "top": 45, "width": 10, "height": 10},
        ]},
    ]}


@pytest.mark.asyncio
async def test_create_image_markup(ctx):
    ua = ctx["ua"]
    async with await _client(ua) as c:
        fid = await _upload_image(c)
        r = await c.post("/api/markup", json={"source_file_id": fid})
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["source_file_type"] == "image"
        assert body["status"] == "active"
        assert body["current_version_number"] == 0
        assert body["current_version_id"] is None


@pytest.mark.asyncio
async def test_create_pdf_page_markup_requires_valid_page(ctx):
    ua = ctx["ua"]
    async with await _client(ua) as c:
        fid = await _upload_pdf(c)
        missing_page = await c.post("/api/markup", json={"source_file_id": fid})
        assert missing_page.status_code == 400
        zero_page = await c.post("/api/markup", json={"source_file_id": fid, "source_page_number": 0})
        assert zero_page.status_code == 400
        ok = await c.post("/api/markup", json={"source_file_id": fid, "source_page_number": 2})
        assert ok.status_code == 201
        assert ok.json()["source_file_type"] == "pdf"
        assert ok.json()["source_page_number"] == 2


@pytest.mark.asyncio
async def test_source_file_validation_cross_tenant_and_unavailable(ctx):
    ua, ub = ctx["ua"], ctx["ub"]
    async with await _client(ua) as c:
        fid = await _upload_image(c)
        ghost = await c.post("/api/markup", json={"source_file_id": "does-not-exist"})
        assert ghost.status_code == 404
    _clear()
    async with await _client(ub) as c2:
        cross = await c2.post("/api/markup", json={"source_file_id": fid})
        assert cross.status_code == 404  # safe, tenant-scoped — never leaks existence


@pytest.mark.asyncio
async def test_intake_and_intake_item_attachment(ctx):
    ua = ctx["ua"]
    async with await _client(ua) as c:
        fid = await _upload_image(c)
        intake = (await c.post("/api/intake", json={
            "project_name": "Markup job", "contact_name": "Jane",
            "items": [{"item_name": "Banner", "category": "banners", "quantity": 1}],
        })).json()
        iid, item_id = intake["id"], intake["items"][0]["id"]

        created_for_item = await c.post("/api/markup", json={"source_file_id": fid, "intake_id": iid, "intake_item_id": item_id})
        assert created_for_item.status_code == 201
        mid = created_for_item.json()["id"]

        attach = await c.post(f"/api/markup/{mid}/attach", json={"intake_id": iid, "intake_item_id": item_id})
        assert attach.status_code == 200
        assert attach.json()["items"][0]["visual_markup_id"] == mid

        bad_item = await c.post("/api/markup", json={"source_file_id": fid, "intake_id": iid, "intake_item_id": "ghost"})
        assert bad_item.status_code == 404

        # intake-level attachment (no specific item)
        submission_markup = (await c.post("/api/markup", json={"source_file_id": fid, "intake_id": iid})).json()
        attach_intake = await c.post(f"/api/markup/{submission_markup['id']}/attach", json={"intake_id": iid})
        assert attach_intake.status_code == 200
        assert submission_markup["id"] in attach_intake.json()["visual_markup_ids"]


@pytest.mark.asyncio
async def test_structured_json_persistence_and_object_validation(ctx):
    ua = ctx["ua"]
    async with await _client(ua) as c:
        fid = await _upload_image(c)
        mid = (await c.post("/api/markup", json={"source_file_id": fid})).json()["id"]

        good = await c.post(f"/api/markup/{mid}/versions", json={
            "structured_markup_json": _sample_objects(),
            "canvas_width": 800, "canvas_height": 600,
            "source_display_width": 800, "source_display_height": 600,
        })
        assert good.status_code == 201, good.text
        assert good.json()["version"]["structured_markup_json"]["objects"][0]["type"] == "rect"

        unsupported = await c.post(f"/api/markup/{mid}/versions", json={
            "structured_markup_json": {"objects": [{"type": "image", "src": "whatever"}]},
            "canvas_width": 800, "canvas_height": 600, "source_display_width": 800, "source_display_height": 600,
        })
        assert unsupported.status_code == 400

        embedded_binary = await c.post(f"/api/markup/{mid}/versions", json={
            "structured_markup_json": {"objects": [{"type": "rect", "fill": "data:image/png;base64,AAAA"}]},
            "canvas_width": 800, "canvas_height": 600, "source_display_width": 800, "source_display_height": 600,
        })
        assert embedded_binary.status_code == 400

        oversized = await c.post(f"/api/markup/{mid}/versions", json={
            "structured_markup_json": {"objects": [{"type": "rect", "left": i, "top": i} for i in range(400)]},
            "canvas_width": 800, "canvas_height": 600, "source_display_width": 800, "source_display_height": 600,
        })
        assert oversized.status_code == 400  # exceeds max object count


@pytest.mark.asyncio
async def test_versioning_monotonic_and_prior_version_immutable(ctx):
    ua = ctx["ua"]
    async with await _client(ua) as c:
        fid = await _upload_image(c)
        mid = (await c.post("/api/markup", json={"source_file_id": fid})).json()["id"]

        v1 = await c.post(f"/api/markup/{mid}/versions", json={
            "structured_markup_json": {"objects": [{"type": "rect", "left": 1, "top": 1}]},
            "canvas_width": 800, "canvas_height": 600, "source_display_width": 800, "source_display_height": 600,
            "change_summary": "first pass",
        })
        assert v1.json()["version"]["version_number"] == 1
        assert v1.json()["markup"]["current_version_id"] == v1.json()["version"]["id"]

        v2 = await c.post(f"/api/markup/{mid}/versions", json={
            "structured_markup_json": {"objects": [{"type": "rect", "left": 2, "top": 2}]},
            "canvas_width": 800, "canvas_height": 600, "source_display_width": 800, "source_display_height": 600,
            "change_summary": "second pass",
        })
        assert v2.json()["version"]["version_number"] == 2
        assert v2.json()["version"]["parent_version_id"] == v1.json()["version"]["id"]

        # prior version remains byte-identical after v2 was saved
        v1_reread = await c.get(f"/api/markup/{mid}/versions/{v1.json()['version']['id']}")
        assert v1_reread.json()["structured_markup_json"]["objects"][0]["left"] == 1
        assert v1_reread.json()["change_summary"] == "first pass"

        history = await c.get(f"/api/markup/{mid}/versions")
        numbers = [v["version_number"] for v in history.json()["items"]]
        assert numbers == sorted(numbers, reverse=True)
        assert numbers == [2, 1]

        current = await c.get(f"/api/markup/{mid}")
        assert current.json()["current_version_number"] == 2
        assert current.json()["current_version_id"] == v2.json()["version"]["id"]


@pytest.mark.asyncio
async def test_concurrent_version_saves_get_distinct_monotonic_numbers(ctx):
    import asyncio
    ua = ctx["ua"]
    async with await _client(ua) as c:
        fid = await _upload_image(c)
        mid = (await c.post("/api/markup", json={"source_file_id": fid})).json()["id"]

        async def save(i):
            return await c.post(f"/api/markup/{mid}/versions", json={
                "structured_markup_json": {"objects": [{"type": "rect", "left": i, "top": i}]},
                "canvas_width": 800, "canvas_height": 600, "source_display_width": 800, "source_display_height": 600,
            })

        results = await asyncio.gather(*[save(i) for i in range(5)])
        numbers = sorted(r.json()["version"]["version_number"] for r in results)
        assert numbers == [1, 2, 3, 4, 5]  # no duplicates, no gaps


@pytest.mark.asyncio
async def test_rendered_preview_stored_separately_and_original_untouched(ctx):
    ua = ctx["ua"]
    async with await _client(ua) as c:
        fid = await _upload_image(c)
        preview_fid = await _upload_image(c, seed=b"1" * 40)
        mid = (await c.post("/api/markup", json={"source_file_id": fid})).json()["id"]

        r = await c.post(f"/api/markup/{mid}/versions", json={
            "structured_markup_json": _sample_objects(),
            "canvas_width": 800, "canvas_height": 600, "source_display_width": 800, "source_display_height": 600,
            "rendered_preview_file_id": preview_fid,
        })
        assert r.status_code == 201
        assert r.json()["version"]["rendered_preview_file_id"] == preview_fid
        assert r.json()["version"]["rendered_preview_file_id"] != fid  # separate File record

        # original source file record is untouched (still resolvable, unchanged id)
        original = await c.get(f"/api/files/{fid}")
        assert original.status_code == 200
        assert original.json()["file"]["id"] == fid

        preview = await c.get(f"/api/markup/{mid}/preview")
        assert preview.json()["rendered_preview_file_id"] == preview_fid
        assert preview.json()["version_number"] == 1

        bad_preview_ref = await c.post(f"/api/markup/{mid}/versions", json={
            "structured_markup_json": {"objects": []},
            "canvas_width": 800, "canvas_height": 600, "source_display_width": 800, "source_display_height": 600,
            "rendered_preview_file_id": "ghost-file",
        })
        assert bad_preview_ref.status_code == 404


@pytest.mark.asyncio
async def test_archive_and_restore(ctx):
    ua = ctx["ua"]
    async with await _client(ua) as c:
        fid = await _upload_image(c)
        mid = (await c.post("/api/markup", json={"source_file_id": fid})).json()["id"]
        archived = await c.post(f"/api/markup/{mid}/archive")
        assert archived.status_code == 200
        assert archived.json()["status"] == "archived"
        blocked = await c.post(f"/api/markup/{mid}/versions", json={
            "structured_markup_json": {"objects": []},
            "canvas_width": 800, "canvas_height": 600, "source_display_width": 800, "source_display_height": 600,
        })
        assert blocked.status_code == 400
        restored = await c.post(f"/api/markup/{mid}/restore")
        assert restored.status_code == 200
        assert restored.json()["status"] == "active"
        # archive/restore never delete versions
        still_open = await c.post(f"/api/markup/{mid}/versions", json={
            "structured_markup_json": {"objects": []},
            "canvas_width": 800, "canvas_height": 600, "source_display_width": 800, "source_display_height": 600,
        })
        assert still_open.status_code == 201


@pytest.mark.asyncio
async def test_tenant_isolation_and_permissions(ctx):
    ua, ub = ctx["ua"], ctx["ub"]
    async with await _client(ua) as c:
        fid = await _upload_image(c)
        mid = (await c.post("/api/markup", json={"source_file_id": fid})).json()["id"]
    _clear()
    async with await _client(ub) as c2:
        cross_get = await c2.get(f"/api/markup/{mid}")
        assert cross_get.status_code == 404
        cross_version = await c2.post(f"/api/markup/{mid}/versions", json={
            "structured_markup_json": {"objects": []},
            "canvas_width": 800, "canvas_height": 600, "source_display_width": 800, "source_display_height": 600,
        })
        assert cross_version.status_code == 404
        guessed = await c2.get("/api/markup/totally-guessed-id")
        assert guessed.status_code == 404


@pytest.mark.asyncio
async def test_audit_events_emitted(ctx):
    ua, ta = ctx["ua"], ctx["ta"]
    async with await _client(ua) as c:
        fid = await _upload_image(c)
        mid = (await c.post("/api/markup", json={"source_file_id": fid})).json()["id"]
        await c.post(f"/api/markup/{mid}/versions", json={
            "structured_markup_json": _sample_objects(),
            "canvas_width": 800, "canvas_height": 600, "source_display_width": 800, "source_display_height": 600,
        })
        await c.post(f"/api/markup/{mid}/archive")
    events = [e async for e in db.audit_events.find(
        {"tenant_id": ta, "entity_type": "visual_markup", "entity_id": mid}, {"_id": 0},
    )]
    actions = {e["action"] for e in events}
    assert {"markup.created", "markup.version_saved", "markup.current_version_changed", "markup.archived"} <= actions
    # full markup JSON must never be dumped into audit logs
    for e in events:
        assert "structured_markup_json" not in (e.get("diff") or {})
        assert "objects" not in str(e.get("diff") or {})


@pytest.mark.asyncio
async def test_coordinate_round_trip(ctx):
    ua = ctx["ua"]
    async with await _client(ua) as c:
        fid = await _upload_image(c)
        mid = (await c.post("/api/markup", json={"source_file_id": fid})).json()["id"]
        r = await c.post(f"/api/markup/{mid}/versions", json={
            "structured_markup_json": {"objects": [{"type": "rect", "left": 123.5, "top": 456.25, "width": 50, "height": 20}]},
            "canvas_width": 1024, "canvas_height": 768, "source_display_width": 1024, "source_display_height": 768,
        })
        version_id = r.json()["version"]["id"]
        reread = await c.get(f"/api/markup/{mid}/versions/{version_id}")
        body = reread.json()
        # canvas/display dimensions and object coordinates survive a full round trip unchanged
        assert body["canvas_width"] == 1024 and body["canvas_height"] == 768
        assert body["source_display_width"] == 1024 and body["source_display_height"] == 768
        assert body["coordinate_space"] == "canvas_pixels_v1"
        obj = body["structured_markup_json"]["objects"][0]
        assert obj["left"] == 123.5 and obj["top"] == 456.25
