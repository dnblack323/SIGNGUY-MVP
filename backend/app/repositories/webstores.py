"""EC14 - tenant-scoped Webstores repository helpers."""
from __future__ import annotations

from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now


class WebstoreRepository:
    def __init__(self, collection_name: str):
        self.collection = db[collection_name]

    async def insert(self, doc: dict[str, Any]) -> dict:
        await self.collection.insert_one(prepare_for_mongo(doc))
        return serialize_doc(doc)  # type: ignore[return-value]

    async def get(self, *, tenant_id: str, entity_id: str) -> Optional[dict]:
        doc = await self.collection.find_one({"tenant_id": tenant_id, "id": entity_id}, {"_id": 0})
        return serialize_doc(doc)

    async def find_one(self, filter_doc: dict[str, Any]) -> Optional[dict]:
        doc = await self.collection.find_one(filter_doc, {"_id": 0})
        return serialize_doc(doc)

    async def list(
        self,
        *,
        tenant_id: str,
        filters: Optional[dict[str, Any]] = None,
        sort: Optional[list[tuple[str, int]]] = None,
        limit: int = 100,
        skip: int = 0,
    ) -> dict:
        q = {"tenant_id": tenant_id, **(filters or {})}
        total = await self.collection.count_documents(q)
        cursor = self.collection.find(q, {"_id": 0}).sort(sort or [("created_at", -1)]).skip(skip).limit(limit)
        items = [serialize_doc(doc) async for doc in cursor]
        return {"items": items, "total": total, "limit": limit, "skip": skip}

    async def update(self, *, tenant_id: str, entity_id: str, updates: dict[str, Any]) -> Optional[dict]:
        updates = {**updates, "updated_at": utc_now().isoformat()}
        result = await self.collection.update_one({"tenant_id": tenant_id, "id": entity_id}, {"$set": updates})
        if result.matched_count == 0:
            return None
        return await self.get(tenant_id=tenant_id, entity_id=entity_id)
