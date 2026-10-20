"""READ-ONLY report of Webstore questionnaire data left behind by Phase 2a.

Phase 2a stopped reading and writing ``webstore_questionnaire_templates`` and
made Form Maker the only questionnaire template store. This script only counts
what remains so the owner can decide on migration or deletion. It never writes.

Usage (from backend/):  MONGO_URL=... DB_NAME=... python -m scripts.report_webstore_legacy_questionnaire_data
"""
from __future__ import annotations

import asyncio
import json

from app.core.db import db


async def build_report() -> dict:
    legacy = db.webstore_questionnaire_templates
    tenant_ids = await legacy.distinct("tenant_id")
    test_prefix = "t-"  # automated-test tenants use t-<suite>-<suffix> ids
    return {
        "legacy_questionnaire_templates": {
            "total": await legacy.count_documents({}),
            "tenants": len(tenant_ids),
            "test_suite_tenants": sum(1 for t in tenant_ids if str(t).startswith(test_prefix)),
            "other_tenants": sorted(str(t) for t in tenant_ids if not str(t).startswith(test_prefix)),
        },
        # Form Maker copies mirrored from the legacy store (still usable; they predate the Starter pack).
        "legacy_mirrored_form_templates": await db.form_templates.count_documents(
            {"module": "webstores", "private_config.legacy_template_id": {"$exists": True}}
        ),
        "starter_pack_form_templates": await db.form_templates.count_documents(
            {"module": "webstores", "private_config.pack_id": "webstore_starter"}
        ),
        "stores_bound_to_unknown_template_ids": await _stores_with_stale_bindings(),
        "submissions_without_revision": await db.webstore_questionnaire_submissions.count_documents(
            {"status": {"$in": ["submitted", "reviewed", "returned_for_changes"]}, "revision": None}
        ),
        "setup_files_rows": await db.webstore_setup_files.count_documents({}),
    }


async def _stores_with_stale_bindings() -> int:
    stale = 0
    async for store in db.webstores.find(
        {"setup_requirements.questionnaire_template_ids.0": {"$exists": True}},
        {"_id": 0, "tenant_id": 1, "setup_requirements.questionnaire_template_ids": 1},
    ):
        ids = store["setup_requirements"]["questionnaire_template_ids"]
        found = await db.form_templates.count_documents({"tenant_id": store["tenant_id"], "id": {"$in": ids}})
        stale += int(found == 0)  # rebinds automatically on next owner/staff read
    return stale


if __name__ == "__main__":
    print(json.dumps(asyncio.run(build_report()), indent=2, default=str))
