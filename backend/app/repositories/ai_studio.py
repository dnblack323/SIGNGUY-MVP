"""Repository helpers for EC17 AI Studio."""
from __future__ import annotations

from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc


async def insert(collection_name: str, doc: dict[str, Any]) -> dict[str, Any]:
    await getattr(db, collection_name).insert_one(prepare_for_mongo(doc))
    return serialize_doc(doc)


async def find_one(collection_name: str, filt: dict[str, Any]) -> Optional[dict[str, Any]]:
    doc = await getattr(db, collection_name).find_one(filt, {"_id": 0})
    return serialize_doc(doc) if doc else None


async def update_one(collection_name: str, filt: dict[str, Any], updates: dict[str, Any]) -> Optional[dict[str, Any]]:
    await getattr(db, collection_name).update_one(filt, {"$set": prepare_for_mongo(updates)})
    return await find_one(collection_name, filt)


async def list_many(collection_name: str, filt: dict[str, Any], *, sort: list[tuple[str, int]], limit: int = 100) -> list[dict[str, Any]]:
    cursor = getattr(db, collection_name).find(filt, {"_id": 0}).sort(sort).limit(limit)
    return [serialize_doc(d) async for d in cursor]
