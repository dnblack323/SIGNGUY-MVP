"""EC12 Phase 12G - community, founders, feedback, voting, and support routes."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..core.permissions import Perm
from ..deps import require_permission
from ..services import community_service
from ..services.community_service import CommunityError

router = APIRouter(prefix="/community", tags=["community"])


def _raise(e: CommunityError) -> None:
    raise HTTPException(status_code=e.status_code, detail=e.detail)


class SpaceIn(BaseModel):
    scope_type: str
    name: str
    description: Optional[str] = None
    visibility: Optional[str] = None
    posting_policy: Optional[str] = None
    moderation_policy: Optional[str] = None
    voting_enabled: bool = True


class SpaceUpdateIn(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    visibility: Optional[str] = None
    posting_policy: Optional[str] = None
    moderation_policy: Optional[str] = None
    voting_enabled: Optional[bool] = None
    active: Optional[bool] = None


class PostIn(BaseModel):
    space_id: str
    post_type: str = "discussion"
    title: str
    body: str
    visibility: str = "visible"
    linked_record_type: Optional[str] = None
    linked_record_id: Optional[str] = None
    idempotency_key: Optional[str] = None


class PostUpdateIn(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None


class CommentIn(BaseModel):
    body: str
    parent_comment_id: Optional[str] = None


class ModerationIn(BaseModel):
    action: str
    reason: Optional[str] = None
    target_space_id: Optional[str] = None
    duplicate_of_post_id: Optional[str] = None


class VoteIn(BaseModel):
    active: bool = True


class FeatureIn(BaseModel):
    title: str
    description: str
    category: str = "general"
    idempotency_key: Optional[str] = None


class FeatureStatusIn(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    staff_response: Optional[str] = None


class DuplicateFeatureIn(BaseModel):
    duplicate_of_request_id: str


class BugIn(BaseModel):
    title: str
    description: str
    severity: str = "medium"
    reproducibility: Optional[str] = None
    steps: list[str] = Field(default_factory=list)
    expected_behavior: Optional[str] = None
    actual_behavior: Optional[str] = None
    browser_metadata: dict[str, Any] = Field(default_factory=dict)
    attachment_file_ids: list[str] = Field(default_factory=list)
    idempotency_key: Optional[str] = None


class BugStatusIn(BaseModel):
    status: Optional[str] = None
    staff_response: Optional[str] = None
    linked_support_request_id: Optional[str] = None


class DuplicateBugIn(BaseModel):
    duplicate_of_bug_id: str


class FounderGrantIn(BaseModel):
    user_id: str
    tenant_id: str
    reason: Optional[str] = None


class SupportIn(BaseModel):
    request_type: str
    destination_type: Optional[str] = None
    subject: str
    description: str
    linked_customer_id: Optional[str] = None
    linked_order_id: Optional[str] = None
    linked_task_id: Optional[str] = None
    linked_bug_report_id: Optional[str] = None
    linked_feature_request_id: Optional[str] = None
    idempotency_key: Optional[str] = None


class SupportUpdateIn(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    assigned_user_id: Optional[str] = None


class SupportNoteIn(BaseModel):
    body: str


@router.get("/spaces")
async def list_spaces(user: dict = Depends(require_permission(Perm.COMMUNITY_READ))) -> dict:
    try:
        return await community_service.list_spaces(user)
    except CommunityError as e:
        _raise(e)


@router.post("/spaces", status_code=201)
async def create_space(payload: SpaceIn, user: dict = Depends(require_permission(Perm.COMMUNITY_MODERATE))) -> dict:
    try:
        return await community_service.create_space(user, payload.model_dump(exclude_none=True))
    except CommunityError as e:
        _raise(e)


@router.patch("/spaces/{space_id}")
async def update_space(space_id: str, payload: SpaceUpdateIn, user: dict = Depends(require_permission(Perm.COMMUNITY_MODERATE))) -> dict:
    try:
        return await community_service.update_space(user, space_id, payload.model_dump(exclude_none=True))
    except CommunityError as e:
        _raise(e)


@router.post("/spaces/{space_id}/archive")
async def archive_space(space_id: str, user: dict = Depends(require_permission(Perm.COMMUNITY_MODERATE))) -> dict:
    try:
        return await community_service.archive_space(user, space_id)
    except CommunityError as e:
        _raise(e)


@router.post("/spaces/{space_id}/restore")
async def restore_space(space_id: str, user: dict = Depends(require_permission(Perm.COMMUNITY_MODERATE))) -> dict:
    try:
        return await community_service.archive_space(user, space_id, restore=True)
    except CommunityError as e:
        _raise(e)


@router.get("/posts")
async def list_posts(
    space_id: Optional[str] = None,
    post_type: Optional[str] = None,
    q: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(100, ge=1, le=200),
    skip: int = Query(0, ge=0),
    user: dict = Depends(require_permission(Perm.COMMUNITY_READ)),
) -> dict:
    try:
        return await community_service.list_posts(user, space_id=space_id, post_type=post_type, q=q, status=status, limit=limit, skip=skip)
    except CommunityError as e:
        _raise(e)


@router.post("/posts", status_code=201)
async def create_post(payload: PostIn, user: dict = Depends(require_permission(Perm.COMMUNITY_POST))) -> dict:
    try:
        return await community_service.create_post(user, payload.model_dump(exclude_none=True))
    except CommunityError as e:
        _raise(e)


@router.get("/posts/{post_id}")
async def get_post(post_id: str, user: dict = Depends(require_permission(Perm.COMMUNITY_READ))) -> dict:
    try:
        return await community_service.get_post(user, post_id)
    except CommunityError as e:
        _raise(e)


@router.patch("/posts/{post_id}")
async def edit_post(post_id: str, payload: PostUpdateIn, user: dict = Depends(require_permission(Perm.COMMUNITY_POST))) -> dict:
    try:
        return await community_service.edit_post(user, post_id, payload.model_dump(exclude_none=True))
    except CommunityError as e:
        _raise(e)


@router.post("/posts/{post_id}/comments", status_code=201)
async def create_comment(post_id: str, payload: CommentIn, user: dict = Depends(require_permission(Perm.COMMUNITY_POST))) -> dict:
    try:
        return await community_service.create_comment(user, post_id, payload.model_dump(exclude_none=True))
    except CommunityError as e:
        _raise(e)


@router.post("/posts/{post_id}/vote")
async def vote_post(post_id: str, payload: VoteIn, user: dict = Depends(require_permission(Perm.COMMUNITY_POST))) -> dict:
    try:
        return await community_service.vote_post(user, post_id, payload.active)
    except CommunityError as e:
        _raise(e)


@router.post("/posts/{post_id}/moderate")
async def moderate_post(post_id: str, payload: ModerationIn, user: dict = Depends(require_permission(Perm.COMMUNITY_MODERATE))) -> dict:
    try:
        return await community_service.moderate_post(user, post_id, payload.action, payload.reason, payload.target_space_id, payload.duplicate_of_post_id)
    except CommunityError as e:
        _raise(e)


@router.post("/comments/{comment_id}/moderate")
async def moderate_comment(comment_id: str, payload: ModerationIn, user: dict = Depends(require_permission(Perm.COMMUNITY_MODERATE))) -> dict:
    try:
        return await community_service.moderate_comment(user, comment_id, payload.action, payload.reason)
    except CommunityError as e:
        _raise(e)


@router.post("/posts/{post_id}/report")
async def report_post(post_id: str, payload: SupportNoteIn, user: dict = Depends(require_permission(Perm.COMMUNITY_POST))) -> dict:
    try:
        return await community_service.report_post(user, post_id, payload.body)
    except CommunityError as e:
        _raise(e)


@router.get("/feature-requests")
async def list_feature_requests(user: dict = Depends(require_permission(Perm.COMMUNITY_READ))) -> dict:
    return await community_service.list_feature_requests(user)


@router.post("/feature-requests", status_code=201)
async def create_feature_request(payload: FeatureIn, user: dict = Depends(require_permission(Perm.COMMUNITY_POST))) -> dict:
    try:
        return await community_service.create_feature_request(user, payload.model_dump(exclude_none=True))
    except CommunityError as e:
        _raise(e)


@router.patch("/feature-requests/{request_id}/status")
async def update_feature_status(request_id: str, payload: FeatureStatusIn, user: dict = Depends(require_permission(Perm.COMMUNITY_MODERATE))) -> dict:
    try:
        return await community_service.update_feature_status(user, request_id, payload.model_dump(exclude_none=True))
    except CommunityError as e:
        _raise(e)


@router.post("/feature-requests/{request_id}/duplicate")
async def mark_feature_duplicate(request_id: str, payload: DuplicateFeatureIn, user: dict = Depends(require_permission(Perm.COMMUNITY_MODERATE))) -> dict:
    try:
        return await community_service.mark_feature_duplicate(user, request_id, payload.duplicate_of_request_id)
    except CommunityError as e:
        _raise(e)


@router.post("/feature-requests/{request_id}/vote")
async def vote_feature_request(request_id: str, payload: VoteIn, user: dict = Depends(require_permission(Perm.COMMUNITY_POST))) -> dict:
    try:
        return await community_service.vote_feature_request(user, request_id, payload.active)
    except CommunityError as e:
        _raise(e)


@router.get("/bug-reports")
async def list_bug_reports(user: dict = Depends(require_permission(Perm.COMMUNITY_READ))) -> dict:
    return await community_service.list_bug_reports(user)


@router.post("/bug-reports", status_code=201)
async def create_bug_report(payload: BugIn, user: dict = Depends(require_permission(Perm.COMMUNITY_POST))) -> dict:
    try:
        return await community_service.create_bug_report(user, payload.model_dump(exclude_none=True))
    except CommunityError as e:
        _raise(e)


@router.patch("/bug-reports/{bug_id}/status")
async def update_bug_status(bug_id: str, payload: BugStatusIn, user: dict = Depends(require_permission(Perm.COMMUNITY_MODERATE))) -> dict:
    try:
        return await community_service.update_bug_status(user, bug_id, payload.model_dump(exclude_none=True))
    except CommunityError as e:
        _raise(e)


@router.post("/bug-reports/{bug_id}/duplicate")
async def mark_bug_duplicate(bug_id: str, payload: DuplicateBugIn, user: dict = Depends(require_permission(Perm.COMMUNITY_MODERATE))) -> dict:
    try:
        return await community_service.mark_bug_duplicate(user, bug_id, payload.duplicate_of_bug_id)
    except CommunityError as e:
        _raise(e)


@router.get("/founders")
async def list_founder_members(user: dict = Depends(require_permission(Perm.COMMUNITY_MODERATE))) -> dict:
    try:
        return await community_service.list_founder_members(user)
    except CommunityError as e:
        _raise(e)


@router.post("/founders/grants", status_code=201)
async def grant_founder_access(payload: FounderGrantIn, user: dict = Depends(require_permission(Perm.COMMUNITY_MODERATE))) -> dict:
    try:
        return await community_service.grant_founder_access(user, payload.user_id, payload.tenant_id, payload.reason)
    except CommunityError as e:
        _raise(e)


@router.post("/founders/grants/{access_id}/revoke")
async def revoke_founder_access(access_id: str, user: dict = Depends(require_permission(Perm.COMMUNITY_MODERATE))) -> dict:
    try:
        return await community_service.revoke_founder_access(user, access_id)
    except CommunityError as e:
        _raise(e)


@router.get("/support/route-preview")
async def support_route_preview(request_type: str, user: dict = Depends(require_permission(Perm.SUPPORT_WRITE))) -> dict:
    try:
        return await community_service.support_route_preview(user, request_type)
    except CommunityError as e:
        _raise(e)


@router.get("/support")
async def list_support_requests(user: dict = Depends(require_permission(Perm.SUPPORT_READ))) -> dict:
    return await community_service.list_support_requests(user)


@router.post("/support", status_code=201)
async def create_support_request(payload: SupportIn, user: dict = Depends(require_permission(Perm.SUPPORT_WRITE))) -> dict:
    try:
        return await community_service.create_support_request(user, payload.model_dump(exclude_none=True))
    except CommunityError as e:
        _raise(e)


@router.get("/support/{ticket_id}")
async def get_support_request(ticket_id: str, include_internal_notes: bool = False, user: dict = Depends(require_permission(Perm.SUPPORT_READ))) -> dict:
    try:
        return await community_service.get_support_request(user, ticket_id, include_internal_notes=include_internal_notes)
    except CommunityError as e:
        _raise(e)


@router.patch("/support/{ticket_id}")
async def update_support_request(ticket_id: str, payload: SupportUpdateIn, user: dict = Depends(require_permission(Perm.SUPPORT_READ))) -> dict:
    try:
        return await community_service.update_support_request(user, ticket_id, payload.model_dump(exclude_none=True))
    except CommunityError as e:
        _raise(e)


@router.post("/support/{ticket_id}/notes", status_code=201)
async def add_support_note(ticket_id: str, payload: SupportNoteIn, user: dict = Depends(require_permission(Perm.SUPPORT_READ))) -> dict:
    try:
        return await community_service.add_support_note(user, ticket_id, payload.body)
    except CommunityError as e:
        _raise(e)
