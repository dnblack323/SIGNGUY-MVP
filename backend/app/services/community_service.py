"""EC12 Phase 12G - community, feedback, voting, founder, and support services."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Optional

from pymongo.errors import DuplicateKeyError

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.community import (
    BugReport,
    CommunityComment,
    CommunityPost,
    CommunitySpace,
    CommunityVote,
    FeatureRequest,
    FounderAccess,
    SupportRequest,
    SupportRequestNote,
)
from .activity import record_activity_with_audit
from . import notifications


class CommunityError(Exception):
    def __init__(self, code: str, detail: str, status_code: int = 400):
        self.code = code
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


SPACE_SCOPES = {"platform", "tenant", "founders"}
POST_TYPES = {"discussion", "question", "announcement", "showcase", "bug_report", "feature_request"}
FEATURE_STATUSES = {"submitted", "under_review", "planned", "in_progress", "released", "declined", "duplicate"}
BUG_STATUSES = {"submitted", "triaged", "needs_info", "confirmed", "in_progress", "fixed", "closed", "duplicate", "not_reproducible"}
SUPPORT_STATUSES = {"open", "acknowledged", "waiting_on_user", "waiting_on_support", "resolved", "closed"}
TENANT_SUPPORT_TYPES = {"internal_workflow_help", "local_employee_access_help", "shop_configuration_question", "tenant_operational_issue"}
PLATFORM_SUPPORT_TYPES = {"product_bug", "feature_request", "login_platform_access_problem", "billing_platform_issue", "data_privacy_request", "platform_service_problem"}
LINK_COLLECTIONS = {"customer": "customers", "order": "orders", "task": "tasks", "work_order": "work_orders"}


def _now() -> str:
    return utc_now().isoformat()


def _is_platform_admin(user: dict) -> bool:
    return bool(
        user.get("platform_admin")
        or user.get("founder_access_admin")
        or user.get("platform_role") in {"admin", "owner"}
        or "platform:admin" in set(user.get("permissions") or [])
    )


def _is_tenant_admin(user: dict) -> bool:
    return user.get("role") in {"owner", "admin"}


def _has_founder_access(user: dict) -> bool:
    return bool(user.get("founder_access") or user.get("founder_member") or user.get("platform_founder"))


async def _fresh_user(user: dict) -> dict:
    doc = await db.users.find_one({"tenant_id": user["tenant_id"], "id": user["id"]}, {"_id": 0})
    return {**user, **(doc or {})}


async def _actor(user: dict) -> dict:
    return await _fresh_user(user)


async def _audit(user: dict, action: str, entity_type: str, entity_id: str, summary: str, metadata: Optional[dict] = None) -> None:
    await record_activity_with_audit(
        tenant_id=user["tenant_id"],
        actor_user_id=user["id"],
        actor_email=user.get("email", "staff"),
        module="community",
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        metadata=metadata or {},
    )


def _clean_body(text: str, *, limit: int = 5000) -> str:
    value = (text or "").strip()
    if not value:
        raise CommunityError("body_required", "Body is required", 400)
    if len(value) > limit:
        raise CommunityError("body_too_long", f"Body must be {limit} characters or fewer", 400)
    lowered = value.lower()
    for marker in ("authorization:", "bearer ", "cookie:", "set-cookie:", "x-api-key", "password="):
        if marker in lowered:
            raise CommunityError("secret_like_content", "Remove secrets, tokens, or raw headers before submitting", 400)
    return value


def _clean_title(text: str, *, limit: int = 180) -> str:
    value = (text or "").strip()
    if not value:
        raise CommunityError("title_required", "Title is required", 400)
    if len(value) > limit:
        raise CommunityError("title_too_long", f"Title must be {limit} characters or fewer", 400)
    return value


async def _rate_limit(tenant_id: str, actor_id: str, collection: str, field: str, *, limit: int, window_seconds: int = 60) -> None:
    since = (utc_now() - timedelta(seconds=window_seconds)).isoformat()
    count = await db[collection].count_documents({"tenant_id": tenant_id, field: actor_id, "created_at": {"$gte": since}})
    if count >= limit:
        raise CommunityError("rate_limited", "Too many recent actions. Try again shortly.", 429)


async def _validate_file_refs(tenant_id: str, file_ids: list[str]) -> list[str]:
    if len(file_ids) > 5:
        raise CommunityError("too_many_attachments", "At most 5 attachments are allowed", 400)
    clean = []
    for fid in file_ids:
        if not fid:
            continue
        doc = await db.files.find_one({"tenant_id": tenant_id, "id": fid}, {"_id": 0, "id": 1})
        if not doc:
            raise CommunityError("file_not_found", "Attachment file does not belong to this tenant", 404)
        clean.append(fid)
    return clean


async def _validate_link(tenant_id: str, record_type: Optional[str], record_id: Optional[str]) -> None:
    if not record_type and not record_id:
        return
    if record_type not in LINK_COLLECTIONS or not record_id:
        raise CommunityError("invalid_link", "Unsupported linked record", 400)
    doc = await db[LINK_COLLECTIONS[record_type]].find_one({"tenant_id": tenant_id, "id": record_id}, {"_id": 0, "id": 1})
    if not doc:
        raise CommunityError("linked_record_not_found", "Linked record does not belong to this tenant", 404)


def _space_filter_for_user(user: dict) -> dict:
    clauses: list[dict] = [
        {"scope_type": "platform", "archived_at": None, "active": True},
        {"scope_type": "tenant", "tenant_id": user["tenant_id"], "archived_at": None, "active": True},
    ]
    if _has_founder_access(user) or _is_platform_admin(user):
        clauses.append({"scope_type": "founders", "archived_at": None, "active": True})
    return {"$or": clauses}


async def _require_space(user: dict, space_id: str, *, manage: bool = False) -> dict:
    user = await _actor(user)
    space = await db.community_spaces.find_one({"id": space_id}, {"_id": 0})
    if not space:
        raise CommunityError("space_not_found", "Community space not found", 404)
    if space.get("archived_at") and not manage:
        raise CommunityError("space_archived", "Community space is archived", 410)
    scope = space.get("scope_type")
    if scope == "tenant" and space.get("tenant_id") != user["tenant_id"]:
        raise CommunityError("space_not_found", "Community space not found", 404)
    if scope == "founders" and not (_has_founder_access(user) or _is_platform_admin(user)):
        raise CommunityError("founder_access_required", "Founder access is required", 403)
    if scope == "platform" and manage and not _is_platform_admin(user):
        raise CommunityError("platform_admin_required", "Platform admin access is required", 403)
    if scope == "founders" and manage and not _is_platform_admin(user):
        raise CommunityError("platform_admin_required", "Platform admin access is required", 403)
    if scope == "tenant" and manage and not _is_tenant_admin(user):
        raise CommunityError("tenant_admin_required", "Tenant admin access is required", 403)
    return space


async def create_space(user: dict, payload: dict) -> dict:
    user = await _actor(user)
    scope = payload.get("scope_type")
    if scope not in SPACE_SCOPES:
        raise CommunityError("invalid_scope", "Unsupported community scope", 400)
    if scope in {"platform", "founders"} and not _is_platform_admin(user):
        raise CommunityError("platform_admin_required", "Platform admin access is required", 403)
    if scope == "tenant" and not _is_tenant_admin(user):
        raise CommunityError("tenant_admin_required", "Tenant admin access is required", 403)
    doc = CommunitySpace(
        scope_type=scope,
        tenant_id=user["tenant_id"] if scope == "tenant" else None,
        name=_clean_title(payload.get("name", "")),
        description=(payload.get("description") or "").strip() or None,
        visibility=payload.get("visibility") or ("founders" if scope == "founders" else "visible"),
        posting_policy=payload.get("posting_policy") or "open",
        moderation_policy=payload.get("moderation_policy") or "post_moderation",
        voting_enabled=bool(payload.get("voting_enabled", True)),
        created_by_user_id=user["id"],
    ).model_dump()
    await db.community_spaces.insert_one(prepare_for_mongo(dict(doc)))
    await _audit(user, "community.space_created", "community_space", doc["id"], f"Community space created: {doc['name']}", {"scope_type": scope})
    return serialize_doc(doc)


async def list_spaces(user: dict) -> dict:
    user = await _actor(user)
    cur = db.community_spaces.find(_space_filter_for_user(user), {"_id": 0}).sort([("scope_type", 1), ("name", 1)])
    return {"items": [serialize_doc(d) async for d in cur]}


async def update_space(user: dict, space_id: str, updates: dict) -> dict:
    space = await _require_space(user, space_id, manage=True)
    allowed = {k: v for k, v in updates.items() if k in {"name", "description", "visibility", "posting_policy", "moderation_policy", "voting_enabled", "active"}}
    if "name" in allowed:
        allowed["name"] = _clean_title(allowed["name"])
    allowed["updated_at"] = _now()
    await db.community_spaces.update_one({"id": space["id"]}, {"$set": allowed})
    await _audit(await _actor(user), "community.space_updated", "community_space", space_id, "Community space updated", {"fields": sorted(allowed)})
    return serialize_doc(await db.community_spaces.find_one({"id": space_id}, {"_id": 0}))


async def archive_space(user: dict, space_id: str, *, restore: bool = False) -> dict:
    await _require_space(user, space_id, manage=True)
    update = {"archived_at": None, "active": True, "updated_at": _now()} if restore else {"archived_at": _now(), "active": False, "updated_at": _now()}
    await db.community_spaces.update_one({"id": space_id}, {"$set": update})
    await _audit(await _actor(user), "community.space_restored" if restore else "community.space_archived", "community_space", space_id, "Community space restored" if restore else "Community space archived")
    return serialize_doc(await db.community_spaces.find_one({"id": space_id}, {"_id": 0}))


async def create_post(user: dict, payload: dict) -> dict:
    user = await _actor(user)
    await _rate_limit(user["tenant_id"], user["id"], "community_posts", "author_user_id", limit=20)
    space = await _require_space(user, payload.get("space_id"))
    if space.get("posting_policy") == "moderators" and not (_is_platform_admin(user) or _is_tenant_admin(user)):
        raise CommunityError("posting_forbidden", "Posting is restricted in this space", 403)
    post_type = payload.get("post_type") or "discussion"
    if post_type not in POST_TYPES:
        raise CommunityError("invalid_post_type", "Unsupported post type", 400)
    if space["scope_type"] == "tenant":
        await _validate_link(user["tenant_id"], payload.get("linked_record_type"), payload.get("linked_record_id"))
    if payload.get("idempotency_key"):
        existing = await db.community_posts.find_one({"author_user_id": user["id"], "space_id": space["id"], "idempotency_key": payload["idempotency_key"]}, {"_id": 0})
        if existing:
            return serialize_doc(existing)
    doc = CommunityPost(
        space_id=space["id"],
        scope_type=space["scope_type"],
        tenant_id=space.get("tenant_id"),
        author_user_id=user["id"],
        post_type=post_type,
        title=_clean_title(payload.get("title", "")),
        body=_clean_body(payload.get("body", "")),
        visibility=payload.get("visibility") or "visible",
        linked_record_type=payload.get("linked_record_type"),
        linked_record_id=payload.get("linked_record_id"),
        idempotency_key=payload.get("idempotency_key"),
        history=[{"at": _now(), "action": "created", "actor_user_id": user["id"]}],
    ).model_dump()
    try:
        await db.community_posts.insert_one(prepare_for_mongo(dict(doc)))
    except DuplicateKeyError:
        if payload.get("idempotency_key"):
            existing = await db.community_posts.find_one({"author_user_id": user["id"], "space_id": space["id"], "idempotency_key": payload["idempotency_key"]}, {"_id": 0})
            if existing:
                return serialize_doc(existing)
        raise
    await _audit(user, "community.post_created", "community_post", doc["id"], f"Community post created: {doc['title']}", {"space_id": space["id"], "post_type": post_type})
    return serialize_doc(doc)


async def list_posts(user: dict, *, space_id: Optional[str] = None, post_type: Optional[str] = None, q: Optional[str] = None, status: Optional[str] = None, limit: int = 100, skip: int = 0) -> dict:
    user = await _actor(user)
    spaces = [d["id"] async for d in db.community_spaces.find(_space_filter_for_user(user), {"_id": 0, "id": 1})]
    filt: dict[str, Any] = {"space_id": {"$in": spaces}, "archived_at": None}
    if space_id:
        await _require_space(user, space_id)
        filt["space_id"] = space_id
    if post_type:
        filt["post_type"] = post_type
    if status:
        filt["status"] = status
    if q:
        filt["$or"] = [{"title": {"$regex": q, "$options": "i"}}, {"body": {"$regex": q, "$options": "i"}}]
    total = await db.community_posts.count_documents(filt)
    cur = db.community_posts.find(filt, {"_id": 0}).sort([("pinned", -1), ("updated_at", -1)]).skip(skip).limit(limit)
    return {"items": [serialize_doc(d) async for d in cur], "total": total}


async def _require_post(user: dict, post_id: str, *, manage: bool = False) -> dict:
    post = await db.community_posts.find_one({"id": post_id}, {"_id": 0})
    if not post:
        raise CommunityError("post_not_found", "Community post not found", 404)
    await _require_space(user, post["space_id"], manage=manage)
    if post.get("moderated") and not manage and post.get("author_user_id") != user.get("id"):
        raise CommunityError("post_hidden", "Community post is hidden", 404)
    return post


async def get_post(user: dict, post_id: str) -> dict:
    post = await _require_post(await _actor(user), post_id)
    comments = await list_comments(user, post_id)
    out = serialize_doc(post)
    out["comments"] = comments["items"]
    return out


async def edit_post(user: dict, post_id: str, updates: dict) -> dict:
    user = await _actor(user)
    post = await _require_post(user, post_id)
    if post.get("locked") and post.get("author_user_id") != user["id"] and not _is_tenant_admin(user):
        raise CommunityError("post_locked", "Post is locked", 409)
    if post.get("author_user_id") != user["id"] and not _is_tenant_admin(user) and not _is_platform_admin(user):
        raise CommunityError("post_forbidden", "Only the author or a moderator may edit this post", 403)
    clean = {k: v for k, v in updates.items() if k in {"title", "body"}}
    if "title" in clean:
        clean["title"] = _clean_title(clean["title"])
    if "body" in clean:
        clean["body"] = _clean_body(clean["body"])
    clean["updated_at"] = _now()
    clean["history"] = (post.get("history") or []) + [{"at": _now(), "action": "edited", "actor_user_id": user["id"]}]
    await db.community_posts.update_one({"id": post_id}, {"$set": clean})
    await _audit(user, "community.post_edited", "community_post", post_id, "Community post edited", {"fields": sorted(clean)})
    return serialize_doc(await db.community_posts.find_one({"id": post_id}, {"_id": 0}))


async def moderate_post(user: dict, post_id: str, action: str, reason: Optional[str] = None, target_space_id: Optional[str] = None, duplicate_of_post_id: Optional[str] = None) -> dict:
    user = await _actor(user)
    post = await _require_post(user, post_id, manage=True)
    now = _now()
    updates: dict[str, Any] = {"updated_at": now}
    if action == "hide":
        updates.update({"moderated": True, "status": "hidden", "moderation_reason": reason or "Hidden by moderator"})
    elif action == "unhide":
        updates.update({"moderated": False, "status": "open", "moderation_reason": None})
    elif action in {"lock", "unlock"}:
        updates["locked"] = action == "lock"
    elif action in {"pin", "unpin"}:
        updates["pinned"] = action == "pin"
    elif action in {"archive", "restore"}:
        updates["archived_at"] = None if action == "restore" else now
    elif action == "mark_duplicate":
        if not duplicate_of_post_id:
            raise CommunityError("duplicate_target_required", "duplicate_of_post_id is required", 400)
        updates.update({"status": "duplicate", "duplicate_of_post_id": duplicate_of_post_id})
    elif action == "move":
        if not target_space_id:
            raise CommunityError("target_space_required", "target_space_id is required", 400)
        target = await _require_space(user, target_space_id, manage=True)
        updates.update({"space_id": target["id"], "scope_type": target["scope_type"], "tenant_id": target.get("tenant_id")})
    else:
        raise CommunityError("invalid_moderation_action", "Unsupported moderation action", 400)
    updates["history"] = (post.get("history") or []) + [{"at": now, "action": action, "actor_user_id": user["id"], "reason": reason}]
    await db.community_posts.update_one({"id": post_id}, {"$set": updates})
    await _audit(user, f"community.post_{action}", "community_post", post_id, f"Community post moderation: {action}", {"reason": reason})
    return serialize_doc(await db.community_posts.find_one({"id": post_id}, {"_id": 0}))


async def create_comment(user: dict, post_id: str, payload: dict) -> dict:
    user = await _actor(user)
    post = await _require_post(user, post_id)
    if post.get("locked") or post.get("archived_at"):
        raise CommunityError("post_closed", "Post is locked or archived", 409)
    parent_id = payload.get("parent_comment_id")
    if parent_id:
        parent = await db.community_comments.find_one({"id": parent_id, "post_id": post_id, "archived_at": None}, {"_id": 0, "id": 1})
        if not parent:
            raise CommunityError("parent_comment_not_found", "Parent comment not found", 404)
    doc = CommunityComment(
        post_id=post_id,
        parent_comment_id=parent_id,
        scope_type=post["scope_type"],
        tenant_id=post.get("tenant_id"),
        author_user_id=user["id"],
        body=_clean_body(payload.get("body", ""), limit=2500),
    ).model_dump()
    await db.community_comments.insert_one(prepare_for_mongo(dict(doc)))
    await db.community_posts.update_one({"id": post_id}, {"$inc": {"comment_count": 1}, "$set": {"updated_at": _now()}})
    if post.get("author_user_id") and post.get("author_user_id") != user["id"] and post.get("tenant_id"):
        try:
            await notifications.notify(
                tenant_id=post["tenant_id"], recipient_user_id=post["author_user_id"], module="community",
                kind="community.reply", title="New reply", body=f"Reply on {post.get('title')}",
                entity_type="community_post", entity_id=post_id, link="/help/community",
            )
        except Exception:
            pass
    await _audit(user, "community.comment_created", "community_comment", doc["id"], "Community comment created", {"post_id": post_id})
    return serialize_doc(doc)


async def list_comments(user: dict, post_id: str) -> dict:
    await _require_post(await _actor(user), post_id)
    cur = db.community_comments.find({"post_id": post_id, "archived_at": None}, {"_id": 0}).sort("created_at", 1)
    return {"items": [serialize_doc(d) async for d in cur]}


async def moderate_comment(user: dict, comment_id: str, action: str, reason: Optional[str] = None) -> dict:
    user = await _actor(user)
    comment = await db.community_comments.find_one({"id": comment_id}, {"_id": 0})
    if not comment:
        raise CommunityError("comment_not_found", "Comment not found", 404)
    await _require_post(user, comment["post_id"], manage=True)
    now = _now()
    updates: dict[str, Any] = {"updated_at": now}
    if action == "hide":
        updates.update({"moderated": True, "moderation_reason": reason or "Hidden by moderator"})
    elif action == "unhide":
        updates.update({"moderated": False, "moderation_reason": None})
    elif action in {"archive", "restore"}:
        updates["archived_at"] = None if action == "restore" else now
    else:
        raise CommunityError("invalid_comment_action", "Unsupported comment moderation action", 400)
    await db.community_comments.update_one({"id": comment_id}, {"$set": updates})
    await _audit(user, f"community.comment_{action}", "community_comment", comment_id, f"Community comment moderation: {action}", {"reason": reason})
    return serialize_doc(await db.community_comments.find_one({"id": comment_id}, {"_id": 0}))


async def report_post(user: dict, post_id: str, reason: str) -> dict:
    user = await _actor(user)
    await _require_post(user, post_id)
    doc = {"tenant_id": user["tenant_id"], "post_id": post_id, "reported_by_user_id": user["id"], "reason": _clean_body(reason, limit=1000), "status": "open", "created_at": _now(), "updated_at": _now()}
    await db.community_moderation_reports.insert_one(doc)
    await _audit(user, "community.post_reported", "community_post", post_id, "Community post reported")
    return {"ok": True}


async def _vote(user: dict, record_type: str, record_id: str, active: bool) -> dict:
    user = await _actor(user)
    await _rate_limit(user["tenant_id"], user["id"], "community_votes", "identity_id", limit=60)
    if record_type == "community_post":
        post = await _require_post(user, record_id)
        space = await _require_space(user, post["space_id"])
        if not space.get("voting_enabled", True) or post.get("locked") or post.get("moderated"):
            raise CommunityError("voting_disabled", "Voting is disabled for this record", 409)
        scope, tenant_id = post["scope_type"], post.get("tenant_id")
        target_coll, target_field = "community_posts", "vote_count"
    elif record_type == "feature_request":
        fr = await db.feature_requests.find_one({"id": record_id, "archived_at": None}, {"_id": 0})
        if not fr:
            raise CommunityError("feature_request_not_found", "Feature request not found", 404)
        scope, tenant_id = "platform", fr.get("tenant_id")
        target_coll, target_field = "feature_requests", "vote_count"
    else:
        raise CommunityError("invalid_vote_target", "Unsupported vote target", 400)
    filt = {"record_type": record_type, "record_id": record_id, "identity_type": "user", "identity_id": user["id"]}
    existing = await db.community_votes.find_one(filt, {"_id": 0})
    if existing and existing.get("active") == active:
        return {"ok": True, "active": active, "vote_count": await _recount_votes(record_type, record_id, target_coll, target_field)}
    update = {"active": active, "removed_at": None if active else _now(), "updated_at": _now()}
    if existing:
        await db.community_votes.update_one(filt, {"$set": update})
    else:
        doc = CommunityVote(record_type=record_type, record_id=record_id, scope_type=scope, tenant_id=tenant_id, identity_id=user["id"], active=active, removed_at=None if active else _now()).model_dump()
        await db.community_votes.insert_one(prepare_for_mongo(dict(doc)))
    count = await _recount_votes(record_type, record_id, target_coll, target_field)
    await _audit(user, "community.vote_changed", record_type, record_id, "Community vote changed", {"active": active})
    return {"ok": True, "active": active, "vote_count": count}


async def _recount_votes(record_type: str, record_id: str, target_coll: str, target_field: str) -> int:
    count = await db.community_votes.count_documents({"record_type": record_type, "record_id": record_id, "active": True})
    await db[target_coll].update_one({"id": record_id}, {"$set": {target_field: count, "updated_at": _now()}})
    return count


async def vote_post(user: dict, post_id: str, active: bool) -> dict:
    return await _vote(user, "community_post", post_id, active)


async def create_feature_request(user: dict, payload: dict) -> dict:
    user = await _actor(user)
    if payload.get("idempotency_key"):
        existing = await db.feature_requests.find_one({"tenant_id": user["tenant_id"], "submitter_user_id": user["id"], "idempotency_key": payload["idempotency_key"]}, {"_id": 0})
        if existing:
            return serialize_doc(existing)
    doc = FeatureRequest(
        tenant_id=user["tenant_id"],
        submitter_user_id=user["id"],
        title=_clean_title(payload.get("title", "")),
        description=_clean_body(payload.get("description", "")),
        category=(payload.get("category") or "general")[:80],
        idempotency_key=payload.get("idempotency_key"),
    ).model_dump()
    await db.feature_requests.insert_one(prepare_for_mongo(dict(doc)))
    await _audit(user, "community.feature_request_created", "feature_request", doc["id"], f"Feature request created: {doc['title']}", {"category": doc["category"]})
    return serialize_doc(doc)


async def list_feature_requests(user: dict) -> dict:
    await _actor(user)
    cur = db.feature_requests.find({"archived_at": None}, {"_id": 0}).sort([("vote_count", -1), ("created_at", -1)])
    return {"items": [serialize_doc(d) async for d in cur]}


async def update_feature_status(user: dict, request_id: str, updates: dict) -> dict:
    user = await _actor(user)
    if not _is_platform_admin(user):
        raise CommunityError("platform_admin_required", "Platform admin access is required", 403)
    fr = await db.feature_requests.find_one({"id": request_id}, {"_id": 0})
    if not fr:
        raise CommunityError("feature_request_not_found", "Feature request not found", 404)
    clean = {k: v for k, v in updates.items() if k in {"status", "priority", "staff_response"}}
    if "status" in clean and clean["status"] not in FEATURE_STATUSES:
        raise CommunityError("invalid_status", "Unsupported feature request status", 400)
    clean["updated_at"] = _now()
    await db.feature_requests.update_one({"id": request_id}, {"$set": clean})
    if fr.get("submitter_user_id"):
        try:
            await notifications.notify(tenant_id=fr["tenant_id"], recipient_user_id=fr["submitter_user_id"], module="community", kind="feature.status", title="Feature request updated", body=clean.get("status"), entity_type="feature_request", entity_id=request_id, link="/help/community")
        except Exception:
            pass
    await _audit(user, "community.feature_status_changed", "feature_request", request_id, "Feature request status changed", {k: v for k, v in clean.items() if k != "staff_response"})
    return serialize_doc(await db.feature_requests.find_one({"id": request_id}, {"_id": 0}))


async def mark_feature_duplicate(user: dict, request_id: str, duplicate_of_request_id: str) -> dict:
    user = await _actor(user)
    if not _is_platform_admin(user):
        raise CommunityError("platform_admin_required", "Platform admin access is required", 403)
    source = await db.feature_requests.find_one({"id": request_id}, {"_id": 0})
    target = await db.feature_requests.find_one({"id": duplicate_of_request_id}, {"_id": 0})
    if not source or not target:
        raise CommunityError("feature_request_not_found", "Feature request not found", 404)
    source_voters = [v["identity_id"] async for v in db.community_votes.find({"record_type": "feature_request", "record_id": request_id, "active": True}, {"_id": 0, "identity_id": 1})]
    for uid in source_voters:
        existing = await db.community_votes.find_one(
            {"record_type": "feature_request", "record_id": duplicate_of_request_id, "identity_type": "user", "identity_id": uid},
            {"_id": 0, "id": 1},
        )
        if existing:
            await db.community_votes.update_one(
                {"id": existing["id"]},
                {"$set": {"active": True, "removed_at": None, "updated_at": _now()}},
            )
            continue
        vote = CommunityVote(
            record_type="feature_request",
            record_id=duplicate_of_request_id,
            scope_type="platform",
            tenant_id=target.get("tenant_id"),
            identity_type="user",
            identity_id=uid,
            active=True,
        ).model_dump()
        try:
            await db.community_votes.insert_one(prepare_for_mongo(vote))
        except DuplicateKeyError:
            await db.community_votes.update_one(
                {"record_type": "feature_request", "record_id": duplicate_of_request_id, "identity_type": "user", "identity_id": uid},
                {"$set": {"active": True, "removed_at": None, "updated_at": _now()}},
            )
    await db.feature_requests.update_one({"id": request_id}, {"$set": {"status": "duplicate", "duplicate_of_request_id": duplicate_of_request_id, "updated_at": _now()}})
    await _recount_votes("feature_request", duplicate_of_request_id, "feature_requests", "vote_count")
    await _audit(user, "community.feature_duplicate", "feature_request", request_id, "Feature request marked duplicate", {"duplicate_of_request_id": duplicate_of_request_id})
    return serialize_doc(await db.feature_requests.find_one({"id": request_id}, {"_id": 0}))


async def vote_feature_request(user: dict, request_id: str, active: bool) -> dict:
    return await _vote(user, "feature_request", request_id, active)


def _safe_metadata(metadata: dict | None) -> dict:
    if not metadata:
        return {}
    blocked = {"authorization", "cookie", "set-cookie", "token", "password", "secret", "api_key", "x-api-key"}
    out = {}
    for k, v in metadata.items():
        lk = str(k).lower()
        if any(b in lk for b in blocked):
            continue
        if isinstance(v, (str, int, float, bool)) or v is None:
            out[str(k)[:60]] = str(v)[:300] if isinstance(v, str) else v
    return out


async def create_bug_report(user: dict, payload: dict) -> dict:
    user = await _actor(user)
    if payload.get("idempotency_key"):
        existing = await db.bug_reports.find_one({"tenant_id": user["tenant_id"], "submitter_user_id": user["id"], "idempotency_key": payload["idempotency_key"]}, {"_id": 0})
        if existing:
            return serialize_doc(existing)
    files = await _validate_file_refs(user["tenant_id"], payload.get("attachment_file_ids") or [])
    doc = BugReport(
        tenant_id=user["tenant_id"],
        submitter_user_id=user["id"],
        title=_clean_title(payload.get("title", "")),
        description=_clean_body(payload.get("description", "")),
        severity=payload.get("severity") or "medium",
        reproducibility=payload.get("reproducibility"),
        steps=[str(s)[:500] for s in (payload.get("steps") or [])][:20],
        expected_behavior=payload.get("expected_behavior"),
        actual_behavior=payload.get("actual_behavior"),
        browser_metadata=_safe_metadata(payload.get("browser_metadata")),
        attachment_file_ids=files,
        idempotency_key=payload.get("idempotency_key"),
    ).model_dump()
    await db.bug_reports.insert_one(prepare_for_mongo(dict(doc)))
    await _audit(user, "community.bug_report_created", "bug_report", doc["id"], f"Bug report created: {doc['title']}", {"severity": doc["severity"]})
    return serialize_doc(doc)


async def list_bug_reports(user: dict) -> dict:
    user = await _actor(user)
    filt: dict[str, Any] = {} if _is_platform_admin(user) else {"tenant_id": user["tenant_id"], "submitter_user_id": user["id"]}
    filt["archived_at"] = None
    cur = db.bug_reports.find(filt, {"_id": 0}).sort("created_at", -1)
    return {"items": [serialize_doc(d) async for d in cur]}


async def update_bug_status(user: dict, bug_id: str, updates: dict) -> dict:
    user = await _actor(user)
    if not _is_platform_admin(user):
        raise CommunityError("platform_admin_required", "Platform admin access is required", 403)
    bug = await db.bug_reports.find_one({"id": bug_id}, {"_id": 0})
    if not bug:
        raise CommunityError("bug_report_not_found", "Bug report not found", 404)
    clean = {k: v for k, v in updates.items() if k in {"status", "staff_response", "linked_support_request_id"}}
    if "status" in clean and clean["status"] not in BUG_STATUSES:
        raise CommunityError("invalid_status", "Unsupported bug report status", 400)
    clean["updated_at"] = _now()
    await db.bug_reports.update_one({"id": bug_id}, {"$set": clean})
    try:
        await notifications.notify(tenant_id=bug["tenant_id"], recipient_user_id=bug["submitter_user_id"], module="community", kind="bug.status", title="Bug report updated", body=clean.get("status"), entity_type="bug_report", entity_id=bug_id, link="/help/community")
    except Exception:
        pass
    await _audit(user, "community.bug_status_changed", "bug_report", bug_id, "Bug report status changed", {k: v for k, v in clean.items() if k != "staff_response"})
    return serialize_doc(await db.bug_reports.find_one({"id": bug_id}, {"_id": 0}))


async def mark_bug_duplicate(user: dict, bug_id: str, duplicate_of_bug_id: str) -> dict:
    user = await _actor(user)
    if not _is_platform_admin(user):
        raise CommunityError("platform_admin_required", "Platform admin access is required", 403)
    if not await db.bug_reports.find_one({"id": duplicate_of_bug_id}, {"_id": 0, "id": 1}):
        raise CommunityError("bug_report_not_found", "Bug report not found", 404)
    await db.bug_reports.update_one({"id": bug_id}, {"$set": {"status": "duplicate", "duplicate_of_bug_id": duplicate_of_bug_id, "updated_at": _now()}})
    await _audit(user, "community.bug_duplicate", "bug_report", bug_id, "Bug report marked duplicate", {"duplicate_of_bug_id": duplicate_of_bug_id})
    return serialize_doc(await db.bug_reports.find_one({"id": bug_id}, {"_id": 0}))


async def grant_founder_access(user: dict, target_user_id: str, target_tenant_id: str, reason: Optional[str] = None) -> dict:
    user = await _actor(user)
    if not _is_platform_admin(user):
        raise CommunityError("platform_admin_required", "Platform admin access is required", 403)
    target = await db.users.find_one({"tenant_id": target_tenant_id, "id": target_user_id, "is_active": True}, {"_id": 0})
    if not target:
        raise CommunityError("user_not_found", "User not found", 404)
    existing = await db.founder_access.find_one({"user_id": target_user_id, "tenant_id": target_tenant_id, "revoked_at": None}, {"_id": 0})
    if existing:
        return serialize_doc(existing)
    doc = FounderAccess(user_id=target_user_id, tenant_id=target_tenant_id, granted_by_user_id=user["id"], reason=reason).model_dump()
    await db.founder_access.insert_one(prepare_for_mongo(dict(doc)))
    await db.users.update_one({"tenant_id": target_tenant_id, "id": target_user_id}, {"$set": {"founder_access": True, "updated_at": _now()}})
    await _audit(user, "community.founder_access_granted", "founder_access", doc["id"], "Founder access granted", {"target_user_id": target_user_id, "target_tenant_id": target_tenant_id})
    return serialize_doc(doc)


async def revoke_founder_access(user: dict, access_id: str) -> dict:
    user = await _actor(user)
    if not _is_platform_admin(user):
        raise CommunityError("platform_admin_required", "Platform admin access is required", 403)
    access = await db.founder_access.find_one({"id": access_id, "revoked_at": None}, {"_id": 0})
    if not access:
        raise CommunityError("founder_access_not_found", "Founder access grant not found", 404)
    await db.founder_access.update_one({"id": access_id}, {"$set": {"revoked_at": _now(), "revoked_by_user_id": user["id"], "updated_at": _now()}})
    await db.users.update_one({"tenant_id": access["tenant_id"], "id": access["user_id"]}, {"$set": {"founder_access": False, "updated_at": _now()}})
    await _audit(user, "community.founder_access_revoked", "founder_access", access_id, "Founder access revoked", {"target_user_id": access["user_id"]})
    return serialize_doc(await db.founder_access.find_one({"id": access_id}, {"_id": 0}))


async def list_founder_members(user: dict) -> dict:
    user = await _actor(user)
    if not _is_platform_admin(user):
        raise CommunityError("platform_admin_required", "Platform admin access is required", 403)
    cur = db.founder_access.find({"revoked_at": None}, {"_id": 0}).sort("created_at", -1)
    return {"items": [serialize_doc(d) async for d in cur]}


async def support_route_preview(user: dict, request_type: str) -> dict:
    user = await _actor(user)
    if request_type in TENANT_SUPPORT_TYPES:
        has_tenant_admin = await db.users.count_documents({"tenant_id": user["tenant_id"], "role": {"$in": ["owner", "admin"]}, "is_active": True}) > 0
        destination = "tenant_admin" if has_tenant_admin else "platform_admin"
    elif request_type in PLATFORM_SUPPORT_TYPES:
        destination = "platform_admin"
    else:
        raise CommunityError("invalid_request_type", "Unsupported support request type", 400)
    return {"request_type": request_type, "destination_type": destination, "destination_label": "Tenant admins" if destination == "tenant_admin" else "SignGuy platform admins"}


async def create_support_request(user: dict, payload: dict) -> dict:
    user = await _actor(user)
    route = await support_route_preview(user, payload.get("request_type"))
    if payload.get("destination_type") and payload["destination_type"] != route["destination_type"]:
        raise CommunityError("invalid_destination", "Destination does not match support routing rules", 400)
    if payload.get("idempotency_key"):
        existing = await db.support_requests.find_one({"tenant_id": user["tenant_id"], "requester_user_id": user["id"], "idempotency_key": payload["idempotency_key"]}, {"_id": 0})
        if existing:
            return serialize_doc(existing)
    await _validate_link(user["tenant_id"], "customer" if payload.get("linked_customer_id") else None, payload.get("linked_customer_id"))
    await _validate_link(user["tenant_id"], "order" if payload.get("linked_order_id") else None, payload.get("linked_order_id"))
    await _validate_link(user["tenant_id"], "task" if payload.get("linked_task_id") else None, payload.get("linked_task_id"))
    doc = SupportRequest(
        tenant_id=user["tenant_id"],
        request_type=payload["request_type"],
        destination_type=route["destination_type"],
        requester_user_id=user["id"],
        subject=_clean_title(payload.get("subject", "")),
        description=_clean_body(payload.get("description", "")),
        linked_customer_id=payload.get("linked_customer_id"),
        linked_order_id=payload.get("linked_order_id"),
        linked_task_id=payload.get("linked_task_id"),
        linked_bug_report_id=payload.get("linked_bug_report_id"),
        linked_feature_request_id=payload.get("linked_feature_request_id"),
        idempotency_key=payload.get("idempotency_key"),
        route_history=[{"at": _now(), "destination_type": route["destination_type"], "actor_user_id": user["id"]}],
    ).model_dump()
    await db.support_requests.insert_one(prepare_for_mongo(dict(doc)))
    try:
        if route["destination_type"] == "tenant_admin":
            await notifications.notify_tenant_owners(tenant_id=user["tenant_id"], module="community", kind="support.created", title="New support request", body=doc["subject"], entity_type="support_request", entity_id=doc["id"], link="/help/community")
        else:
            await _notify_platform_admins("New platform support request", doc["subject"], "support_request", doc["id"])
    except Exception:
        pass
    await _audit(user, "community.support_created", "support_request", doc["id"], f"Support request created: {doc['subject']}", {"destination_type": route["destination_type"]})
    return serialize_doc(doc)


async def _notify_platform_admins(title: str, body: str, entity_type: str, entity_id: str) -> None:
    async for admin in db.users.find({"platform_admin": True, "is_active": True}, {"_id": 0, "tenant_id": 1, "id": 1}):
        await notifications.notify(tenant_id=admin["tenant_id"], recipient_user_id=admin["id"], module="community", kind="platform.notice", title=title, body=body, entity_type=entity_type, entity_id=entity_id, link="/help/community")


async def _can_view_support(user: dict, ticket: dict) -> bool:
    if ticket.get("requester_user_id") == user["id"] and ticket.get("tenant_id") == user["tenant_id"]:
        return True
    if ticket.get("destination_type") == "tenant_admin":
        return ticket.get("tenant_id") == user["tenant_id"] and _is_tenant_admin(user)
    return _is_platform_admin(user)


async def list_support_requests(user: dict) -> dict:
    user = await _actor(user)
    if _is_platform_admin(user):
        filt: dict[str, Any] = {"archived_at": None}
    elif _is_tenant_admin(user):
        filt = {"tenant_id": user["tenant_id"], "destination_type": "tenant_admin", "archived_at": None}
    else:
        filt = {"tenant_id": user["tenant_id"], "requester_user_id": user["id"], "archived_at": None}
    cur = db.support_requests.find(filt, {"_id": 0}).sort("created_at", -1)
    return {"items": [serialize_doc(d) async for d in cur]}


async def get_support_request(user: dict, ticket_id: str, *, include_internal_notes: bool = False) -> dict:
    user = await _actor(user)
    ticket = await db.support_requests.find_one({"id": ticket_id}, {"_id": 0})
    if not ticket or not await _can_view_support(user, ticket):
        raise CommunityError("support_request_not_found", "Support request not found", 404)
    out = serialize_doc(ticket)
    if include_internal_notes and (ticket["destination_type"] == "platform_admin" and _is_platform_admin(user) or ticket["destination_type"] == "tenant_admin" and _is_tenant_admin(user)):
        cur = db.support_request_notes.find({"tenant_id": ticket["tenant_id"], "support_request_id": ticket_id, "archived_at": None}, {"_id": 0}).sort("created_at", 1)
        out["internal_notes"] = [serialize_doc(d) async for d in cur]
    return out


async def update_support_request(user: dict, ticket_id: str, updates: dict) -> dict:
    user = await _actor(user)
    ticket = await db.support_requests.find_one({"id": ticket_id}, {"_id": 0})
    if not ticket:
        raise CommunityError("support_request_not_found", "Support request not found", 404)
    if ticket["destination_type"] == "platform_admin" and not _is_platform_admin(user):
        raise CommunityError("platform_admin_required", "Platform admin access is required", 403)
    if ticket["destination_type"] == "tenant_admin" and not (ticket["tenant_id"] == user["tenant_id"] and _is_tenant_admin(user)):
        raise CommunityError("tenant_admin_required", "Tenant admin access is required", 403)
    clean = {k: v for k, v in updates.items() if k in {"status", "priority", "assigned_user_id"}}
    if "status" in clean and clean["status"] not in SUPPORT_STATUSES:
        raise CommunityError("invalid_status", "Unsupported support status", 400)
    if clean.get("status") in {"resolved", "closed"}:
        clean["closed_at"] = _now()
    clean["updated_at"] = _now()
    await db.support_requests.update_one({"id": ticket_id}, {"$set": clean})
    if ticket.get("requester_user_id"):
        try:
            await notifications.notify(tenant_id=ticket["tenant_id"], recipient_user_id=ticket["requester_user_id"], module="community", kind="support.status", title="Support request updated", body=clean.get("status"), entity_type="support_request", entity_id=ticket_id, link="/help/community")
        except Exception:
            pass
    await _audit(user, "community.support_status_changed", "support_request", ticket_id, "Support request status changed", clean)
    return serialize_doc(await db.support_requests.find_one({"id": ticket_id}, {"_id": 0}))


async def add_support_note(user: dict, ticket_id: str, body: str) -> dict:
    user = await _actor(user)
    await get_support_request(user, ticket_id)
    ticket = await db.support_requests.find_one({"id": ticket_id}, {"_id": 0})
    if ticket["destination_type"] == "platform_admin" and not _is_platform_admin(user):
        raise CommunityError("platform_admin_required", "Platform admin access is required", 403)
    if ticket["destination_type"] == "tenant_admin" and not _is_tenant_admin(user):
        raise CommunityError("tenant_admin_required", "Tenant admin access is required", 403)
    doc = SupportRequestNote(tenant_id=ticket["tenant_id"], support_request_id=ticket_id, author_user_id=user["id"], body=_clean_body(body, limit=2500)).model_dump()
    await db.support_request_notes.insert_one(prepare_for_mongo(dict(doc)))
    await db.support_requests.update_one({"id": ticket_id}, {"$inc": {"internal_note_count": 1}, "$set": {"updated_at": _now()}})
    await _audit(user, "community.support_note_added", "support_request", ticket_id, "Internal support note added")
    return serialize_doc(doc)
