"""EC12 Phase 12G - community, feedback, Founder access, and support contracts."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import Field

from .base import BaseDoc

SpaceScope = Literal["platform", "tenant", "founders"]
PostType = Literal["discussion", "question", "announcement", "showcase", "bug_report", "feature_request"]
PostStatus = Literal["open", "answered", "closed", "duplicate", "hidden"]
FeatureStatus = Literal["submitted", "under_review", "planned", "in_progress", "released", "declined", "duplicate"]
BugStatus = Literal["submitted", "triaged", "needs_info", "confirmed", "in_progress", "fixed", "closed", "duplicate", "not_reproducible"]
SupportStatus = Literal["open", "acknowledged", "waiting_on_user", "waiting_on_support", "resolved", "closed"]
SupportDestination = Literal["tenant_admin", "platform_admin"]
IdentityType = Literal["user", "employee"]


class CommunitySpace(BaseDoc):
    scope_type: SpaceScope
    tenant_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    visibility: str = "visible"
    posting_policy: str = "open"
    moderation_policy: str = "post_moderation"
    voting_enabled: bool = True
    active: bool = True
    archived_at: Optional[str] = None
    created_by_user_id: Optional[str] = None


class CommunityPost(BaseDoc):
    space_id: str
    scope_type: SpaceScope
    tenant_id: Optional[str] = None
    author_user_id: Optional[str] = None
    author_employee_id: Optional[str] = None
    post_type: PostType = "discussion"
    title: str
    body: str
    status: PostStatus = "open"
    visibility: str = "visible"
    linked_record_type: Optional[str] = None
    linked_record_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    pinned: bool = False
    locked: bool = False
    moderated: bool = False
    moderation_reason: Optional[str] = None
    duplicate_of_post_id: Optional[str] = None
    vote_count: int = 0
    comment_count: int = 0
    archived_at: Optional[str] = None
    history: list[dict] = Field(default_factory=list)


class CommunityComment(BaseDoc):
    post_id: str
    parent_comment_id: Optional[str] = None
    scope_type: SpaceScope
    tenant_id: Optional[str] = None
    author_user_id: Optional[str] = None
    author_employee_id: Optional[str] = None
    body: str
    visibility: str = "visible"
    moderated: bool = False
    moderation_reason: Optional[str] = None
    edited_at: Optional[str] = None
    archived_at: Optional[str] = None


class CommunityVote(BaseDoc):
    record_type: Literal["community_post", "feature_request"]
    record_id: str
    scope_type: SpaceScope
    tenant_id: Optional[str] = None
    identity_type: IdentityType = "user"
    identity_id: str
    active: bool = True
    removed_at: Optional[str] = None


class FeatureRequest(BaseDoc):
    tenant_id: str
    submitter_user_id: str
    title: str
    description: str
    category: str = "general"
    status: FeatureStatus = "submitted"
    priority: str = "normal"
    staff_response: Optional[str] = None
    duplicate_of_request_id: Optional[str] = None
    related_release_note_id: Optional[str] = None
    vote_count: int = 0
    archived_at: Optional[str] = None
    idempotency_key: Optional[str] = None


class BugReport(BaseDoc):
    tenant_id: str
    submitter_user_id: str
    title: str
    description: str
    severity: str = "medium"
    reproducibility: Optional[str] = None
    steps: list[str] = Field(default_factory=list)
    expected_behavior: Optional[str] = None
    actual_behavior: Optional[str] = None
    browser_metadata: dict = Field(default_factory=dict)
    attachment_file_ids: list[str] = Field(default_factory=list)
    status: BugStatus = "submitted"
    staff_response: Optional[str] = None
    duplicate_of_bug_id: Optional[str] = None
    linked_support_request_id: Optional[str] = None
    archived_at: Optional[str] = None
    idempotency_key: Optional[str] = None


class FounderAccess(BaseDoc):
    user_id: str
    tenant_id: str
    granted_by_user_id: str
    revoked_at: Optional[str] = None
    revoked_by_user_id: Optional[str] = None
    reason: Optional[str] = None


class SupportRequest(BaseDoc):
    tenant_id: str
    request_type: str
    destination_type: SupportDestination
    requester_user_id: Optional[str] = None
    requester_employee_id: Optional[str] = None
    subject: str
    description: str
    status: SupportStatus = "open"
    priority: str = "normal"
    assigned_user_id: Optional[str] = None
    linked_customer_id: Optional[str] = None
    linked_order_id: Optional[str] = None
    linked_task_id: Optional[str] = None
    linked_bug_report_id: Optional[str] = None
    linked_feature_request_id: Optional[str] = None
    internal_note_count: int = 0
    closed_at: Optional[str] = None
    archived_at: Optional[str] = None
    idempotency_key: Optional[str] = None
    route_history: list[dict] = Field(default_factory=list)


class SupportRequestNote(BaseDoc):
    tenant_id: str
    support_request_id: str
    author_user_id: str
    body: str
    visibility: str = "internal"
    archived_at: Optional[str] = None
