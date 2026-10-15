"""F3 — Shop Schedule feed reads a whole window in bounded pages."""
from __future__ import annotations

import uuid

import pytest

from app.core.db import db
from app.services import calendar_service
from app.services.calendar_service import CalendarError

WINDOW = {"start_at": "2026-08-01T00:00:00+00:00", "end_at": "2026-09-12T00:00:00+00:00"}  # six-week month grid


async def _seed(tenant_id: str, count: int) -> None:
    await db.calendar_events.insert_many([{
        "id": f"ev-{tenant_id}-{i:02d}", "tenant_id": tenant_id, "title": f"Job {i:02d}", "event_type": "installation",
        "status": "scheduled", "archived_at": None,
        "start_at": f"2026-08-{1 + i % 28:02d}T{8 + i % 9:02d}:00:00+00:00", "end_at": f"2026-08-{1 + i % 28:02d}T{9 + i % 9:02d}:00:00+00:00",
    } for i in range(count)])


@pytest.mark.asyncio
async def test_window_pages_return_every_item_exactly_once_for_the_tenant_only():
    tenant, other = f"t-f3feed-{uuid.uuid4().hex[:8]}", f"t-f3feed-{uuid.uuid4().hex[:8]}"
    await _seed(tenant, 23)
    await _seed(other, 5)
    seen, skip = [], 0
    while True:
        page = await calendar_service.list_events(tenant_id=tenant, **WINDOW, limit=10, skip=skip, window_first=True)
        assert len(page["items"]) <= 10 and page["total"] == 23
        seen += [item["id"] for item in page["items"]]
        if not page["has_more"]:
            break
        skip += 10
    assert skip == 20
    assert len(seen) == len(set(seen)) == 23
    assert all(other not in item_id for item_id in seen)


@pytest.mark.asyncio
async def test_window_first_rejects_unbounded_windows():
    with pytest.raises(CalendarError) as too_large:
        await calendar_service.list_events(tenant_id="t-f3feed-x", start_at="2026-01-01T00:00:00+00:00",
                                           end_at="2027-01-01T00:00:00+00:00", window_first=True)
    assert too_large.value.code == "window_too_large"
