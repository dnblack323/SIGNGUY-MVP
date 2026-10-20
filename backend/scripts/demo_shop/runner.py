"""Orchestrates reset/seed/status for the demo shop. Imported only after guard.resolve_target() passed."""
from __future__ import annotations

import sys
from dataclasses import dataclass, field

from pymongo import MongoClient

from scripts.demo_shop.client import DemoApi, DemoSeedError
from scripts.demo_shop.guard import DEV_DATABASE, DemoTarget, UnsafeDemoTargetError

DEMO_SHOP_NAME = "SIGNGUY DEMO SHOP"
DEMO_SHOP_SLUG = "dev-shop"  # the dev-login contract: the frontend auto-login resolves this slug


@dataclass
class Ctx:
    api: DemoApi
    ids: dict[str, str] = field(default_factory=dict)
    created: dict[str, int] = field(default_factory=dict)
    skipped: dict[str, int] = field(default_factory=dict)

    def note(self, kind: str, created: bool) -> None:
        bucket = self.created if created else self.skipped
        bucket[kind] = bucket.get(kind, 0) + 1


def reset_database(target: DemoTarget, confirm: str | None) -> None:
    """Drop the one verified development database. Never a wildcard, never another name."""
    if target.mode != "development" or target.db_name != DEV_DATABASE:
        raise UnsafeDemoTargetError("reset only ever drops the local development database")
    if confirm != target.db_name:
        raise UnsafeDemoTargetError(f"reset requires --confirm {target.db_name}")
    client = MongoClient(target.mongo_url, serverSelectionTimeoutMS=5000)
    try:
        if target.db_name in client.list_database_names():
            busy = [op for op in client.admin.command("currentOp", {"$all": True, "ns": {"$regex": "^" + target.db_name + "[.]"}, "active": True})["inprog"]
                    if op.get("op") not in ("none",) and "currentOp" not in str(op.get("command", ""))]
            if busy:
                raise UnsafeDemoTargetError(f"{len(busy)} active operation(s) are running on {target.db_name}; stop the app first")
            tenants = client[target.db_name]["tenants"].estimated_document_count()
            print(f"dropping {target.db_name} ({len(client[target.db_name].list_collection_names())} collections, ~{tenants} tenants)")
            client.drop_database(target.db_name)
        else:
            print(f"{target.db_name} does not exist; nothing to drop")
    finally:
        client.close()


async def _prepare_tenant(api_db) -> None:
    """Exactly one business tenant: create it (or rename the dev-shop one) before the first login."""
    from app.models.user import Tenant
    from app.core.time_utils import prepare_for_mongo

    others = await api_db.tenants.count_documents({"slug": {"$ne": DEMO_SHOP_SLUG}})
    if others:
        raise UnsafeDemoTargetError(f"{others} other tenant(s) exist; seed only runs on a database whose sole tenant is the demo shop (use reset)")
    existing = await api_db.tenants.find_one({"slug": DEMO_SHOP_SLUG})
    if not existing:
        await api_db.tenants.insert_one(prepare_for_mongo(Tenant(name=DEMO_SHOP_NAME, slug=DEMO_SHOP_SLUG).model_dump()))
    elif existing.get("name") != DEMO_SHOP_NAME:
        await api_db.tenants.update_one({"slug": DEMO_SHOP_SLUG}, {"$set": {"name": DEMO_SHOP_NAME}})


async def seed(target: DemoTarget) -> Ctx:
    import logging

    for noisy in ("httpx", "app", "signguy"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    from server import app
    from app.core.db import db, ensure_indexes
    from app.services.storage import initialize as init_storage
    from scripts.demo_shop import steps

    await ensure_indexes()
    init_storage()
    await _prepare_tenant(db)
    api = DemoApi(app)
    ctx = Ctx(api)
    try:
        await api.login()
        for name, step in steps.ORDERED:
            print(f"== {name}", flush=True)
            await step(ctx)
    finally:
        await api.aclose()
    return ctx


async def verify_demo(target: DemoTarget) -> int:
    import logging

    for noisy in ("httpx", "app", "signguy"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    from server import app
    from scripts.demo_shop import verify

    api = DemoApi(app)
    try:
        await api.login()
        return await verify.run(api)
    finally:
        await api.aclose()


async def run(command: str, target: DemoTarget, *, confirm: str | None) -> int:
    if command == "reset":
        reset_database(target, confirm)
    if command == "verify":
        return await verify_demo(target)
    if command in ("seed", "reset"):
        try:
            ctx = await seed(target)
        except DemoSeedError as exc:
            sys.stderr.write(f"SEED FAILED: {exc}\n")
            return 1
        print("created:", dict(sorted(ctx.created.items())))
        print("already present:", dict(sorted(ctx.skipped.items())))
    from scripts.demo_shop import status

    await status.print_status()
    return 0
