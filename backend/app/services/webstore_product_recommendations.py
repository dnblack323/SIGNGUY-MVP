"""Explained, read-only template matches for staff product planning.

Uses existing templates and frozen questionnaire answers. No AI, catalog
creation, stock inference, price calculation or approval side effects.
"""
from __future__ import annotations

import re

from ..core.permissions import Perm
from .forms_service import visible_question_keys
from .webstore_constants import PLATFORM_TEMPLATE_TENANT_ID
from .webstore_context import db
from .webstore_questionnaire_content import PRODUCT_OPTIONS
from .webstore_questionnaire_review import _answers, _sections, build_brief
from .webstore_shared_access import _require_staff_perm, _require_webstore_assignment_scope
from .webstore_shared_repository import _get_store

# Match declared product types/categories, never infer capability from prose.
PRODUCT_TYPES = {
    "tshirts": {"tshirt", "tshirts", "t shirt", "t shirts", "tee", "tees"},
    "hoodies": {"hoodie", "hoodies", "hooded sweatshirt"},
    "crewnecks": {"crewneck", "crewnecks", "crewneck sweatshirt"},
    "long_sleeve": {"long sleeve", "long sleeve shirt", "long sleeve shirts"},
    "hats": {"hat", "hats", "cap", "caps", "beanie"},
    "polos": {"polo", "polos"},
    "yard_signs": {"yard sign", "yard signs"},
    "banners": {"banner", "banners"},
    "decals": {"decal", "decals", "sticker", "stickers"},
    "drinkware": {"drinkware", "tumbler", "tumblers", "mug", "mugs", "bottle", "bottles"},
    "bags": {"bag", "bags", "tote", "totes"},
}
PRODUCT_LABELS = {o["value"]: o["label"] for o in PRODUCT_OPTIONS}
CONTEXT_KEYS = {"audience", "employee_audience", "product_notes", "personalization_needed", "fulfillment_methods"}


def _normal(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


async def product_recommendations(user: dict, webstore_id: str) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    tenant_id = user["tenant_id"]
    store = await _get_store(tenant_id, webstore_id)
    await _require_webstore_assignment_scope(user, webstore_id)
    latest = await db.webstore_questionnaire_submissions.find_one(
        {"tenant_id": tenant_id, "webstore_id": webstore_id, "revision": {"$ne": None}},
        {"_id": 0}, sort=[("revision", -1), ("updated_at", -1)],
    )
    complete = latest and latest.get("status") in {"submitted", "reviewed"}
    sections = _sections(latest) if complete else []
    raw_answers = _answers(latest) if complete else {}
    if not isinstance(raw_answers, dict):
        raw_answers = {}
    visible = visible_question_keys({"sections": sections}, raw_answers) if sections else set()
    answers = {k: v for k, v in raw_answers.items() if k in visible}
    wanted = answers.get("products_wanted") or []
    # Malformed legacy answers do not turn arbitrary prose into preferences.
    requested = sorted({key for key in wanted if isinstance(key, str)}) if isinstance(wanted, list) else []
    requested = [key for key in requested if key != "other"]
    labels = {**PRODUCT_LABELS, **{o.get("value"): o.get("label") for s in sections for q in s.get("questions") or []
                                if q.get("key") == "products_wanted" for o in q.get("options") or []}}
    selected = {p.get("source_template_id") for p in await db.webstore_products.find(
        {"tenant_id": tenant_id, "webstore_id": webstore_id, "status": {"$ne": "archived"}},
        {"_id": 0, "source_template_id": 1},
    ).to_list(None)}
    query = {"$or": [
        {"tenant_id": tenant_id, "scope": {"$ne": "platform"}},
        {"tenant_id": PLATFORM_TEMPLATE_TENANT_ID, "scope": "platform"},
    ], "status": "active", "active": {"$ne": False}}
    # Only presentation/selection metadata leaves this query. No cost, money,
    # private file refs, supplier notes or AI output is used by this read model.
    projection = {"_id": 0, "id": 1, "template_name": 1, "product_type": 1, "product_category": 1,
                  "scope": 1, "best_store_types": 1}
    items, matched = [], set()
    async for template in db.webstore_product_templates.find(query, projection):
        types = {_normal(template.get("product_type")), _normal(template.get("product_category"))}
        matches = [key for key in requested if types & PRODUCT_TYPES.get(key, {_normal(key)})]
        store_match = store.get("store_type") in (template.get("best_store_types") or [])
        if not matches and (not store_match or answers.get("open_to_suggestions") == "no"):
            continue
        matched.update(matches)
        reasons = [f"Requested in questionnaire: {labels.get(key) or key}." for key in matches]
        if store_match:
            reasons.append("This template is marked as suitable for this store type.")
        items.append({"template_id": template["id"], "name": template.get("template_name"),
                      "product_type": template.get("product_type"), "category": template.get("product_category"),
                      "scope": template.get("scope", "tenant"), "reasons": reasons,
                      "already_selected": template["id"] in selected, "_rank": (bool(matches), store_match)})
    items.sort(key=lambda item: (-int(item["_rank"][0]), -int(item["_rank"][1]),
                                 str(item["name"] or "").casefold(), item["template_id"]))
    for item in items:
        item.pop("_rank")
    context = [item for section in build_brief(latest) for item in section["items"]
               if item["key"] in CONTEXT_KEYS] if complete else []
    return {"items": items, "total": len(items),
            "questionnaire_status": (latest or {}).get("status") or "not_submitted",
            "submission_id": latest["id"] if complete else None,
            "submission_revision": latest.get("revision") if complete else None,
            "context": context,
            "unmatched_requests": [labels.get(key) or key for key in requested if key not in matched],
            "extra_suggestions_declined": answers.get("open_to_suggestions") == "no",
            "review_note": "Templates are starting points. Confirm supplier stock, sizes, colors, fulfillment, mockups and pricing before customer approval."}
