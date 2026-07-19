"""Repository helpers for EC16 AI gateway collections."""
from __future__ import annotations

from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc


class TenantAIRepository:
    def __init__(self, collection_name: str):
        self.collection = db[collection_name]

    async def insert(self, doc: dict[str, Any]) -> dict[str, Any]:
        await self.collection.insert_one(prepare_for_mongo(dict(doc)))
        return serialize_doc(doc)

    async def get(self, tenant_id: str, doc_id: str) -> Optional[dict[str, Any]]:
        return await self.collection.find_one({"tenant_id": tenant_id, "id": doc_id}, {"_id": 0})

    async def find_one(self, tenant_id: str, filt: dict[str, Any]) -> Optional[dict[str, Any]]:
        return await self.collection.find_one({"tenant_id": tenant_id, **filt}, {"_id": 0})

    async def list(
        self,
        tenant_id: str,
        filt: Optional[dict[str, Any]] = None,
        *,
        sort: str = "created_at",
        direction: int = -1,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        cursor = self.collection.find({"tenant_id": tenant_id, **(filt or {})}, {"_id": 0}).sort(sort, direction).limit(limit)
        return [serialize_doc(doc) async for doc in cursor]

    async def update(self, tenant_id: str, doc_id: str, updates: dict[str, Any]) -> Optional[dict[str, Any]]:
        await self.collection.update_one({"tenant_id": tenant_id, "id": doc_id}, {"$set": prepare_for_mongo(updates)})
        return await self.get(tenant_id, doc_id)


class PlatformAIRepository:
    def __init__(self, collection_name: str):
        self.collection = db[collection_name]

    async def insert(self, doc: dict[str, Any]) -> dict[str, Any]:
        await self.collection.insert_one(prepare_for_mongo(dict(doc)))
        return serialize_doc(doc)

    async def get(self, doc_id: str) -> Optional[dict[str, Any]]:
        return await self.collection.find_one({"id": doc_id}, {"_id": 0})

    async def find_one(self, filt: dict[str, Any]) -> Optional[dict[str, Any]]:
        return await self.collection.find_one(filt, {"_id": 0})

    async def list(
        self,
        filt: Optional[dict[str, Any]] = None,
        *,
        sort: str = "created_at",
        direction: int = -1,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        cursor = self.collection.find(filt or {}, {"_id": 0}).sort(sort, direction).limit(limit)
        return [serialize_doc(doc) async for doc in cursor]

    async def update(self, doc_id: str, updates: dict[str, Any]) -> Optional[dict[str, Any]]:
        await self.collection.update_one({"id": doc_id}, {"$set": prepare_for_mongo(updates)})
        return await self.get(doc_id)


providers_repo = PlatformAIRepository("ai_provider_configs")
models_repo = PlatformAIRepository("ai_model_profiles")
capabilities_repo = PlatformAIRepository("ai_capabilities")
prompts_repo = PlatformAIRepository("ai_prompt_versions")
governance_repo = PlatformAIRepository("ai_governance_policies")
provider_health_repo = PlatformAIRepository("ai_provider_health_events")

context_repo = TenantAIRepository("ai_context_packets")
actions_repo = TenantAIRepository("ai_action_requests")
usage_repo = TenantAIRepository("ai_usage_ledger_entries")
provider_cost_repo = TenantAIRepository("ai_provider_cost_ledger_entries")
credit_accounts_repo = TenantAIRepository("ai_credit_accounts")
credit_ledger_repo = TenantAIRepository("ai_credit_ledger_entries")
budget_alerts_repo = TenantAIRepository("ai_budget_alerts")
