"""EC19 Help Center and contextual help service.

Documentation content has one authoritative source: ``app/help_content`` (Markdown articles + catalog). It is
synced into ``help_articles`` / ``contextual_help_definitions`` by ``sync_seed_content``; edits made through the
platform API are marked ``content_source="custom"`` and are never overwritten by a later sync.
"""
from __future__ import annotations

import re
from typing import Any, Optional

from pymongo.errors import DuplicateKeyError

from ..core.db import db
from ..core.permissions import has_platform_admin_access
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..help_content import load_articles
from ..help_content.catalog import CATEGORIES, CATEGORY_KEYS, CONTEXTUAL_HELP
from ..models.onboarding import ContextualHelpDefinition, HelpArticle, HelpFeedback
from .activity import record_activity_with_audit


class HelpCenterError(Exception):
    def __init__(self, code: str, detail: str, status_code: int = 400):
        self.code = code
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


# Fields the HelpArticle model does not declare; stored alongside it (the model ignores extras).
_SEED_FIELDS = ("summary", "order", "links", "related", "aliases", "release", "release_date")
MAX_SEARCH_TERMS = 8
SEARCH_RESULT_LIMIT = 200


def _now_iso() -> str:
    return utc_now().isoformat()


def _is_platform_admin(user: dict) -> bool:
    return has_platform_admin_access(user)


def _require_platform_admin(user: dict) -> None:
    if not _is_platform_admin(user):
        raise HelpCenterError("platform_admin_required", "Platform admin access is required", 403)


async def _audit(user: dict, action: str, entity_type: str, entity_id: str, summary: str, diff: Optional[dict[str, Any]] = None) -> None:
    await record_activity_with_audit(
        tenant_id=user["tenant_id"],
        actor_user_id=user["id"],
        actor_email=user.get("email", "help"),
        module="help_center",
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        diff=diff or {},
    )


def _is_seed_managed(doc: dict) -> bool:
    """Seeded and never edited through the platform API (legacy rows predate ``content_source``)."""
    source = doc.get("content_source")
    if source:
        return source == "seed"
    return not doc.get("updated_by_user_id")


def _seed_extra(item: dict[str, Any]) -> dict[str, Any]:
    extra = {key: item[key] for key in _SEED_FIELDS if item.get(key) not in (None, [])}
    extra.update(content_source="seed", seed_hash=item["seed_hash"])
    return extra


async def sync_seed_content() -> dict:
    """Idempotently load the packaged documentation. Safe on every start and from several workers."""
    now = _now_iso()
    out = {"inserted": {"help_articles": 0, "contextual_help": 0}, "updated": 0, "archived": 0}
    seen: set[str] = set()
    for item in load_articles():
        seen.add(item["slug"])
        existing = await db.help_articles.find_one({"slug": item["slug"]}, {"_id": 0})
        core = {
            "title": item["title"], "category": item["category"], "module": item["module"],
            "body": item["body"], "search_keywords": item["search_keywords"],
        }
        if existing is None:
            published_at = f"{item['release_date']}T00:00:00+00:00" if item.get("release_date") else now
            doc = HelpArticle(slug=item["slug"], status="published", published_at=published_at, **core).model_dump()
            doc.update(_seed_extra(item))
            try:
                await db.help_articles.insert_one(prepare_for_mongo(doc))
            except DuplicateKeyError:
                continue
            out["inserted"]["help_articles"] += 1
        elif _is_seed_managed(existing) and existing.get("seed_hash") != item["seed_hash"]:
            patch = {**core, **_seed_extra(item), "updated_at": now}
            await db.help_articles.update_one({"slug": item["slug"]}, {"$set": prepare_for_mongo(patch)})
            out["updated"] += 1
    async for doc in db.help_articles.find({"slug": {"$nin": sorted(seen)}, "status": {"$ne": "archived"}}, {"_id": 0}):
        if _is_seed_managed(doc):
            await db.help_articles.update_one({"slug": doc["slug"]}, {"$set": {"status": "archived", "archived_at": now, "updated_at": now}})
            out["archived"] += 1
    for item in CONTEXTUAL_HELP:
        doc = ContextualHelpDefinition(**item).model_dump()
        key = {"surface_key": doc.pop("surface_key"), "help_key": doc.pop("help_key")}
        patch = {k: item[k] for k in ("module", "title", "body", "article_slug", "keywords")}
        for k in (*patch, "status", "updated_at"):
            doc.pop(k, None)
        res = await db.contextual_help_definitions.update_one(
            key,
            {"$set": prepare_for_mongo({**patch, "status": "published", "updated_at": now}), "$setOnInsert": prepare_for_mongo(doc)},
            upsert=True,
        )
        out["inserted"]["contextual_help"] += int(bool(res.upserted_id))
    return out


async def bootstrap_help_content(user: dict) -> dict:
    _require_platform_admin(user)
    return await sync_seed_content()


def _plain(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    return re.sub(r"[#*`>_]+", "", text)


def _snippet(body: str, terms: list[str]) -> str:
    plain = re.sub(r"\s+", " ", _plain(body)).strip()
    lowered = plain.lower()
    hits = [i for i in (lowered.find(t.lower()) for t in terms) if i >= 0]
    if not hits:
        return plain[:160]
    start = max(min(hits) - 60, 0)
    text = plain[start:start + 180].strip()
    return ("..." if start else "") + text + ("..." if start + 180 < len(plain) else "")


def _score(doc: dict, terms: list[str]) -> int:
    score = 0
    for term in terms:
        t = term.lower()
        score += 10 * (t in (doc.get("title") or "").lower())
        score += 5 * any(t in k.lower() for k in doc.get("search_keywords") or [])
        score += 3 * (t in (doc.get("summary") or "").lower())
        score += 2 * ((t in (doc.get("module") or "").lower()) or (t in (doc.get("category") or "").lower()))
        score += 1 * (t in (doc.get("body") or "").lower())
    return score


async def search_help(
    *,
    q: Optional[str] = None,
    category: Optional[str] = None,
    module: Optional[str] = None,
    include_archived: bool = False,
    include_body: bool = False,
) -> dict:
    """Every search term must match a title, summary, body, keyword, alias, module or category (key or label)."""
    filt: dict[str, Any] = {}
    if not include_archived:
        filt["status"] = "published"
    if category:
        filt["category"] = category
    if module:
        filt["module"] = module
    terms = [t for t in (q or "").split() if t][:MAX_SEARCH_TERMS]
    clauses = []
    for term in terms:
        pattern = {"$regex": re.escape(term), "$options": "i"}
        label_keys = [c["key"] for c in CATEGORIES if term.lower() in c["label"].lower()]
        clauses.append({"$or": [
            {"title": pattern}, {"summary": pattern}, {"body": pattern}, {"search_keywords": pattern},
            {"aliases": pattern}, {"module": pattern}, {"category": pattern}, {"category": {"$in": label_keys}},
        ]})
    if clauses:
        filt["$and"] = clauses
    rank = {key: i for i, key in enumerate(CATEGORY_KEYS)}
    docs = [serialize_doc(d) async for d in db.help_articles.find(filt, {"_id": 0}).limit(SEARCH_RESULT_LIMIT)]
    docs.sort(key=lambda d: (-_score(d, terms), rank.get(d.get("category"), 99), d.get("order") or 100, d.get("title") or ""))
    for doc in docs:
        if terms:
            doc["snippet"] = _snippet(doc.get("body") or "", terms)
        if not include_body:
            doc.pop("body", None)
    return {"items": docs, "total": len(docs)}


async def list_categories() -> dict:
    counts: dict[str, int] = {}
    async for row in db.help_articles.aggregate([{"$match": {"status": "published"}}, {"$group": {"_id": "$category", "count": {"$sum": 1}}}]):
        counts[row["_id"]] = row["count"]
    return {"items": [{**c, "count": counts.get(c["key"], 0)} for c in CATEGORIES]}


async def get_article(slug: str, *, include_archived: bool = False) -> dict:
    """Resolve by slug first, then by alias, so renamed and onboarding-era slugs keep working."""
    slug = (slug or "").strip().lower()
    base: dict[str, Any] = {} if include_archived else {"status": "published"}
    doc = await db.help_articles.find_one({**base, "slug": slug}, {"_id": 0})
    if not doc:
        doc = await db.help_articles.find_one({**base, "aliases": slug}, {"_id": 0})
    if not doc:
        raise HelpCenterError("help_article_not_found", "Help article not found", 404)
    return serialize_doc(doc)


async def _check_slug_and_aliases(slug: str, aliases: list[str]) -> None:
    others = [name for name in aliases if name != slug]
    clash = await db.help_articles.find_one({"slug": {"$in": others}}, {"_id": 0, "slug": 1})
    if not clash:
        clash = await db.help_articles.find_one(
            {"slug": {"$ne": slug}, "$or": [{"aliases": {"$in": others}}, {"aliases": slug}]}, {"_id": 0, "slug": 1}
        )
    if clash:
        raise HelpCenterError("help_alias_conflict", "A slug or alias is already used by another article", 409)


async def upsert_article(user: dict, payload: dict[str, Any]) -> dict:
    _require_platform_admin(user)
    slug = (payload.get("slug") or "").strip().lower()
    if not slug:
        raise HelpCenterError("slug_required", "slug is required", 400)
    existing = await db.help_articles.find_one({"slug": slug}, {"_id": 0})
    status = payload.get("status") or (existing or {}).get("status") or "draft"
    if status not in {"draft", "published", "archived"}:
        raise HelpCenterError("invalid_status", "Invalid help article status", 400)
    aliases = [a.strip().lower() for a in (payload.get("aliases") or (existing or {}).get("aliases") or []) if a and a.strip()]
    await _check_slug_and_aliases(slug, aliases)
    patch = {
        "slug": slug,
        "title": (payload.get("title") or (existing or {}).get("title") or slug).strip(),
        "category": payload.get("category") or (existing or {}).get("category") or "general",
        "module": payload.get("module") or (existing or {}).get("module"),
        "body": payload.get("body") or (existing or {}).get("body") or "",
        "status": status,
        "audience": payload.get("audience") or (existing or {}).get("audience") or ["owner", "admin", "staff"],
        "search_keywords": payload.get("search_keywords") or (existing or {}).get("search_keywords") or [],
        "summary": payload.get("summary") or (existing or {}).get("summary") or "",
        "related": payload.get("related") or (existing or {}).get("related") or [],
        "aliases": aliases,
        "links": payload.get("links") or (existing or {}).get("links") or [],
        "content_source": "custom",
        "platform_managed": True,
        "updated_by_user_id": user["id"],
        "updated_at": _now_iso(),
    }
    if payload.get("order") is not None:
        patch["order"] = payload["order"]
    if status == "published" and not (existing or {}).get("published_at"):
        patch["published_at"] = _now_iso()
    if status == "archived":
        patch["archived_at"] = _now_iso()
    if existing:
        await db.help_articles.update_one({"slug": slug}, {"$set": prepare_for_mongo(patch)})
    else:
        doc_to_insert = HelpArticle(
            slug=slug,
            title=patch["title"],
            category=patch["category"],
            module=patch.get("module"),
            body=patch["body"],
            status=status,  # type: ignore[arg-type]
            audience=patch["audience"],
            search_keywords=patch["search_keywords"],
            published_at=patch.get("published_at"),
            archived_at=patch.get("archived_at"),
            created_by_user_id=user["id"],
            updated_by_user_id=user["id"],
        ).model_dump()
        doc_to_insert.update({k: patch[k] for k in ("summary", "related", "aliases", "links", "content_source") if k in patch})
        if "order" in patch:
            doc_to_insert["order"] = patch["order"]
        await db.help_articles.insert_one(prepare_for_mongo(doc_to_insert))
    doc = serialize_doc(await db.help_articles.find_one({"slug": slug}, {"_id": 0}))
    await _audit(user, "help.article_upserted", "help_article", doc["id"], "Help article saved", {"slug": slug, "status": status})
    return doc


async def transition_article(user: dict, slug: str, status: str) -> dict:
    _require_platform_admin(user)
    if status not in {"draft", "published", "archived"}:
        raise HelpCenterError("invalid_status", "Invalid help article status", 400)
    patch: dict[str, Any] = {"status": status, "updated_by_user_id": user["id"], "updated_at": _now_iso()}
    if status == "published":
        patch["published_at"] = _now_iso()
        patch["archived_at"] = None
    if status == "archived":
        patch["archived_at"] = _now_iso()
    result = await db.help_articles.update_one({"slug": slug}, {"$set": patch})
    if not result.matched_count:
        raise HelpCenterError("help_article_not_found", "Help article not found", 404)
    doc = serialize_doc(await db.help_articles.find_one({"slug": slug}, {"_id": 0}))
    await _audit(user, "help.article_status_changed", "help_article", doc["id"], "Help article status changed", {"status": status})
    return doc


async def contextual_help(surface_key: str, *, module: Optional[str] = None) -> dict:
    filt: dict[str, Any] = {"status": "published", "surface_key": surface_key}
    if module:
        filt["module"] = module
    cursor = db.contextual_help_definitions.find(filt, {"_id": 0}).sort("help_key", 1)
    return {"items": [serialize_doc(doc) async for doc in cursor]}


async def role_guides(role: str) -> dict:
    module = "role_owner" if role in {"owner", "admin"} else "role_staff"
    return await search_help(category="role_guides", module=module)


async def feedback(user: dict, payload: dict[str, Any]) -> dict:
    existing = None
    if payload.get("idempotency_key"):
        existing = await db.help_feedback.find_one({"tenant_id": user["tenant_id"], "idempotency_key": payload["idempotency_key"]}, {"_id": 0})
    if existing:
        return serialize_doc(existing)
    doc = HelpFeedback(
        tenant_id=user["tenant_id"],
        article_id=payload.get("article_id"),
        article_slug=payload.get("article_slug"),
        helpful=payload.get("helpful"),
        comment=payload.get("comment"),
        idempotency_key=payload.get("idempotency_key"),
        created_by_user_id=user["id"],
    ).model_dump()
    try:
        await db.help_feedback.insert_one(prepare_for_mongo(doc))
    except DuplicateKeyError:
        return serialize_doc(await db.help_feedback.find_one({"tenant_id": user["tenant_id"], "idempotency_key": payload["idempotency_key"]}, {"_id": 0}))
    return serialize_doc(doc)


async def failed_subscription_guidance(user: dict) -> dict:
    sub = await db.tenant_subscriptions.find_one({"tenant_id": user["tenant_id"], "status": {"$in": ["past_due", "unpaid", "incomplete"]}}, {"_id": 0}, sort=[("updated_at", -1)])
    account = await db.tenant_billing_accounts.find_one({"tenant_id": user["tenant_id"]}, {"_id": 0})
    dunning_state = (sub or {}).get("dunning_state") or (account or {}).get("status") or "current"
    if dunning_state == "current":
        message = "No failed subscription payment is currently recorded for this tenant."
    elif dunning_state == "day_1_7_warning":
        message = "Payment is recently past due. Update billing details or retry payment from the billing portal."
    elif dunning_state == "day_8_14_soft_restriction":
        message = "Payment remains past due. Owner/admin should resolve billing to avoid deeper restrictions."
    elif dunning_state in {"eligible_for_suspension", "suspended"}:
        message = "The subscription is eligible for suspension or already suspended. Contact support if billing details are already corrected."
    else:
        message = "Review the Subscriptions page for the current EC13 billing state."
    return {"dunning_state": dunning_state, "subscription": serialize_doc(sub), "billing_account": serialize_doc(account), "guidance": message, "mutated_billing": False}
