"""F2 — Repository for per-user Home dashboard preferences (tenant + user scoped)."""
from __future__ import annotations

from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.home_dashboard import DashboardPreferences


class DashboardPreferencesRepository:
    collection_name = "dashboard_preferences"

    @property
    def collection(self):
        return db[self.collection_name]

    async def get(self, *, tenant_id: str, user_id: str) -> Optional[dict[str, Any]]:
        doc = await self.collection.find_one({"tenant_id": tenant_id, "user_id": user_id}, {"_id": 0})
        return serialize_doc(doc) if doc else None

    async def save(self, *, tenant_id: str, user_id: str, layout: dict[str, Any]) -> dict[str, Any]:
        now = utc_now().isoformat()
        fields = {"version": layout["version"], "order": layout["order"], "hidden": layout["hidden"],
                  "collapsed": layout["collapsed"], "updated_at": now}
        new_doc = prepare_for_mongo(DashboardPreferences(tenant_id=tenant_id, user_id=user_id, **layout).model_dump())
        insert_only = {k: v for k, v in new_doc.items() if k not in fields}
        await self.collection.update_one(
            {"tenant_id": tenant_id, "user_id": user_id},
            {"$set": fields, "$setOnInsert": insert_only},
            upsert=True,
        )
        return await self.get(tenant_id=tenant_id, user_id=user_id)  # type: ignore[return-value]

    async def delete(self, *, tenant_id: str, user_id: str) -> None:
        await self.collection.delete_one({"tenant_id": tenant_id, "user_id": user_id})


dashboard_preferences = DashboardPreferencesRepository()
