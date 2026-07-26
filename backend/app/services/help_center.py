"""EC19 Help Center and contextual help service."""
from __future__ import annotations

from typing import Any, Optional

from pymongo.errors import DuplicateKeyError

from ..core.db import db
from ..core.permissions import has_platform_admin_access
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.onboarding import ContextualHelpDefinition, HelpArticle, HelpFeedback, SupportEscalation
from .activity import record_activity_with_audit


class HelpCenterError(Exception):
    def __init__(self, code: str, detail: str, status_code: int = 400):
        self.code = code
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


HELP_ARTICLES: list[dict[str, Any]] = [
    {"slug": "getting-started", "title": "Getting started", "category": "onboarding", "module": "onboarding", "body": "Set up company profile, pricing, production workflow, templates, and a first order in a short guided checklist.", "search_keywords": ["onboarding", "setup", "launch"]},
    {"slug": "owner-guide", "title": "Owner guide", "category": "role_guides", "module": "role_owner", "body": "Owners manage billing, settings, users, pricing defaults, templates, and final setup approvals.", "search_keywords": ["owner", "admin", "permissions"]},
    {"slug": "staff-guide", "title": "Staff guide", "category": "role_guides", "module": "role_staff", "body": "Staff can work from customers, quotes, orders, production, tasks, documents, and help based on granted permissions.", "search_keywords": ["staff", "permissions"]},
    {"slug": "pricing-setup-guide", "title": "Pricing setup guide", "category": "module_guides", "module": "pricing", "body": "Use Pricing Foundation and the grouped pricing quiz to derive provisional shop defaults, then approve only the fields you want to apply.", "search_keywords": ["pricing", "quiz", "defaults"]},
    {"slug": "templates-and-placeholders", "title": "Templates and placeholders", "category": "module_guides", "module": "templates", "body": "Templates reuse approved placeholders and preview missing values before they are applied to operational records.", "search_keywords": ["templates", "placeholders"]},
    {"slug": "failed-subscription-guidance", "title": "Failed subscription guidance", "category": "billing", "module": "billing", "body": "Past-due billing states come from EC13. Guidance explains the current state and safe next steps without mutating billing records.", "search_keywords": ["billing", "subscription", "failed payment", "dunning"]},
    {"slug": "ai-boundaries", "title": "AI boundaries", "category": "ai", "module": "ai", "body": "AI tools route through EC16/EC17/EC18 contracts. Live providers and final numeric credit pricing remain controlled by H7.", "search_keywords": ["ai", "credits", "provider", "H7"]},
    {"slug": "privacy-data-deletion", "title": "Privacy and data deletion", "category": "trust", "module": "data_security", "body": "Data-security guidance explains where tenant records, audit trails, generated assets, and support requests are managed.", "search_keywords": ["privacy", "delete", "security"]},
    {"slug": "release-notes", "title": "Release notes", "category": "release_notes", "module": "release_notes", "body": "Recent checkpoints delivered Webstores, Wrap Lab, AI Gateway, Studio AI, Business Assistant, and EC19 onboarding/help.", "search_keywords": ["release", "what's new"]},
]

CONTEXTUAL_HELP: list[dict[str, Any]] = [
    {"surface_key": "onboarding.dashboard", "help_key": "progress", "module": "onboarding", "title": "Setup progress", "body": "Required steps drive launch readiness; skipped required steps remain visible until completed.", "article_slug": "getting-started", "keywords": ["progress", "required"]},
    {"surface_key": "pricing.quiz", "help_key": "approval", "module": "pricing", "title": "Pricing approval", "body": "Quiz suggestions are provisional. Pricing settings change only after owner/admin approval.", "article_slug": "pricing-setup-guide", "keywords": ["pricing", "approval"]},
    {"surface_key": "templates.editor", "help_key": "placeholders", "module": "templates", "title": "Placeholders", "body": "Use approved placeholder tokens and preview missing values before saving reusable templates.", "article_slug": "templates-and-placeholders", "keywords": ["placeholder"]},
    {"surface_key": "billing.subscriptions", "help_key": "failed_payment", "module": "billing", "title": "Failed payments", "body": "Failed-payment states are informational in help; EC13 remains the billing source of truth.", "article_slug": "failed-subscription-guidance", "keywords": ["billing"]},
    {"surface_key": "studio.assistant", "help_key": "assistant_boundary", "module": "ai", "title": "Assistant boundary", "body": "The Business Assistant is the canonical assistant. EC19 links to guidance and does not duplicate assistant behavior.", "article_slug": "ai-boundaries", "keywords": ["assistant"]},
]


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


async def bootstrap_help_content(user: dict) -> dict:
    _require_platform_admin(user)
    inserted = {"help_articles": 0, "contextual_help": 0}
    for item in HELP_ARTICLES:
        doc = HelpArticle(**item, status="published", published_at=_now_iso(), created_by_user_id=user.get("id")).model_dump()
        res = await db.help_articles.update_one({"slug": doc["slug"]}, {"$setOnInsert": prepare_for_mongo(doc)}, upsert=True)
        inserted["help_articles"] += int(bool(res.upserted_id))
    for item in CONTEXTUAL_HELP:
        doc = ContextualHelpDefinition(**item).model_dump()
        res = await db.contextual_help_definitions.update_one(
            {"surface_key": doc["surface_key"], "help_key": doc["help_key"]},
            {"$setOnInsert": prepare_for_mongo(doc)},
            upsert=True,
        )
        inserted["contextual_help"] += int(bool(res.upserted_id))
    return {"inserted": inserted}


async def search_help(*, q: Optional[str] = None, category: Optional[str] = None, module: Optional[str] = None, include_archived: bool = False) -> dict:
    filt: dict[str, Any] = {}
    if not include_archived:
        filt["status"] = "published"
    if category:
        filt["category"] = category
    if module:
        filt["module"] = module
    if q:
        pattern = {"$regex": q, "$options": "i"}
        filt["$or"] = [{"title": pattern}, {"body": pattern}, {"search_keywords": pattern}, {"module": pattern}]
    cursor = db.help_articles.find(filt, {"_id": 0}).sort([("category", 1), ("title", 1)]).limit(100)
    return {"items": [serialize_doc(doc) async for doc in cursor]}


async def get_article(slug: str, *, include_archived: bool = False) -> dict:
    filt: dict[str, Any] = {"slug": slug}
    if not include_archived:
        filt["status"] = "published"
    doc = await db.help_articles.find_one(filt, {"_id": 0})
    if not doc:
        raise HelpCenterError("help_article_not_found", "Help article not found", 404)
    return serialize_doc(doc)


async def upsert_article(user: dict, payload: dict[str, Any]) -> dict:
    _require_platform_admin(user)
    slug = (payload.get("slug") or "").strip().lower()
    if not slug:
        raise HelpCenterError("slug_required", "slug is required", 400)
    existing = await db.help_articles.find_one({"slug": slug}, {"_id": 0})
    status = payload.get("status") or (existing or {}).get("status") or "draft"
    if status not in {"draft", "published", "archived"}:
        raise HelpCenterError("invalid_status", "Invalid help article status", 400)
    patch = {
        "slug": slug,
        "title": (payload.get("title") or (existing or {}).get("title") or slug).strip(),
        "category": payload.get("category") or (existing or {}).get("category") or "general",
        "module": payload.get("module") or (existing or {}).get("module"),
        "body": payload.get("body") or (existing or {}).get("body") or "",
        "status": status,
        "audience": payload.get("audience") or (existing or {}).get("audience") or ["owner", "admin", "staff"],
        "search_keywords": payload.get("search_keywords") or (existing or {}).get("search_keywords") or [],
        "platform_managed": True,
        "updated_by_user_id": user["id"],
        "updated_at": _now_iso(),
    }
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


async def support_escalation(user: dict, payload: dict[str, Any]) -> dict:
    subject = (payload.get("subject") or "").strip()
    message = (payload.get("message") or "").strip()
    if not subject or not message:
        raise HelpCenterError("support_subject_message_required", "subject and message are required", 400)
    existing = None
    if payload.get("idempotency_key"):
        existing = await db.support_escalations.find_one({"tenant_id": user["tenant_id"], "idempotency_key": payload["idempotency_key"]}, {"_id": 0})
    if existing:
        return serialize_doc(existing)
    doc = SupportEscalation(
        tenant_id=user["tenant_id"],
        subject=subject[:180],
        message=message[:5000],
        source_surface=payload.get("source_surface"),
        idempotency_key=payload.get("idempotency_key"),
        created_by_user_id=user["id"],
    ).model_dump()
    await db.support_escalations.insert_one(prepare_for_mongo(doc))
    await _audit(user, "help.support_escalated", "support_escalation", doc["id"], "Support escalation created", {"source_surface": payload.get("source_surface")})
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
