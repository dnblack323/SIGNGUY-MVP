"""Disposable browser host with an HTTP provider double, never live execution.

Run only via the existing guarded Webstores browser harness environment.
"""
import asyncio
import json
import os
from pathlib import Path

import uvicorn

from tests import webstores_browser_harness as base
import pytest  # Import after the existing harness guard and settings initialize.
from tests.test_webstores_ai_presentations import configure
from tests.webstore_image_provider_double import install


async def main():
    # Importing base enforces the private DB/storage/loopback harness guard.
    await base.ensure_indexes()
    base.init_storage()
    fixture = await base._seed()
    staff = await base.db.users.find_one({"tenant_id": fixture["tenant_a"]["id"], "email": fixture["staff_a"]["email"]}, {"_id": 0})
    await configure({"tenant_id": fixture["tenant_a"]["id"], "staff": staff})
    monkeypatch = pytest.MonkeyPatch()
    calls = install(monkeypatch)
    Path(os.environ["WEBSTORES_BROWSER_FIXTURE_PATH"]).write_text(json.dumps(fixture), encoding="utf-8")
    try:
        await uvicorn.Server(uvicorn.Config(base.app, host="127.0.0.1", port=int(os.environ["WEBSTORES_BROWSER_BACKEND_PORT"]), log_level="warning")).serve()
    finally:
        monkeypatch.undo()
        print(f"Isolated image transport double handled {len(calls)} requests. Live provider calls: 0.", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
