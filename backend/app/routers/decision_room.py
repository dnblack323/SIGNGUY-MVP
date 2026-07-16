"""EC10 Phase 10D — Customer Decision Room router.

Staff-only, EXCEPT the `/{room_id}/share` (mint) and `/share-tokens/{id}`
(revoke) endpoints below, which are staff-only actions that produce a
customer-facing artifact (a Public Token) — the actual customer-facing
retrieval lives in `decision_room_portal.py` (Customer Portal) and
`public_actions.py` (Public Token), added in Phase 10E-1.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from ..core.permissions import Perm, permissions_for_role
from ..core.time_utils import serialize_doc
from ..deps import require_permission
from ..services import decision_room_service as svc
from ..services.audit import record_audit
from ..services.decision_room_service import DecisionRoomError
from ..services.portal_tokens import mint_public_action_token, revoke_public_action_token

router = APIRouter(prefix="/decision-rooms", tags=["decision-rooms"])

_ERROR_STATUS = {
    "customer_not_found": 404, "intake_not_found": 404, "quote_not_found": 404,
    "order_not_found": 404, "order_item_not_found": 404, "quote_line_item_not_found": 404,
    "file_not_found": 404, "proof_not_found": 404, "visual_markup_not_found": 404,
    "pricing_snapshot_not_found": 404, "room_not_found": 404, "option_not_found": 404,
    "version_not_found": 404, "decision_not_found": 404,
    "title_required": 400, "room_locked": 400, "invalid_transition": 400, "readiness_failed": 400,
    "invalid_badge_type": 400, "invalid_price_display_mode": 400, "reorder_mismatch": 400,
    "order_item_order_mismatch": 400, "quote_converted": 400,
    "decision_not_applicable": 400, "decision_superseded": 409,
    "decision_apply_target_required": 400,
    # EC10 Phase 10E-3
    "question_not_found": 404, "question_message_required": 400,
}


def _raise(ex: DecisionRoomError) -> None:
    detail: Any = {"message": str(ex), "errors": ex.details} if ex.details else str(ex)
    raise HTTPException(status_code=_ERROR_STATUS.get(ex.code, 400), detail=detail)


class DecisionRoomCreateIn(BaseModel):
    title: str
    internal_name: Optional[str] = None
    customer_safe_intro: Optional[str] = None
    customer_id: Optional[str] = None
    intake_id: Optional[str] = None
    quote_id: Optional[str] = None
    order_id: Optional[str] = None
    order_item_id: Optional[str] = None
    expiration_at: Optional[str] = None
    allow_save_for_later: bool = False
    allow_customer_comments: bool = False
    allow_customer_questions: bool = False
    allow_change_requests: bool = False
    allow_reject_all: bool = False
    require_internal_acceptance: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class DecisionRoomUpdateIn(BaseModel):
    title: Optional[str] = None
    internal_name: Optional[str] = None
    customer_safe_intro: Optional[str] = None
    customer_id: Optional[str] = None
    intake_id: Optional[str] = None
    quote_id: Optional[str] = None
    order_id: Optional[str] = None
    order_item_id: Optional[str] = None
    expiration_at: Optional[str] = None
    allow_save_for_later: Optional[bool] = None
    allow_customer_comments: Optional[bool] = None
    allow_customer_questions: Optional[bool] = None
    allow_change_requests: Optional[bool] = None
    allow_reject_all: Optional[bool] = None
    require_internal_acceptance: Optional[bool] = None
    metadata: Optional[dict[str, Any]] = None


class DecisionOptionIn(BaseModel):
    internal_name: Optional[str] = None
    customer_label: Optional[str] = None
    badge_type: str = "none"
    custom_badge_text: Optional[str] = None
    headline: Optional[str] = None
    customer_safe_description: Optional[str] = None
    included_features: list[str] = Field(default_factory=list)
    excluded_features: list[str] = Field(default_factory=list)
    expected_timing: Optional[str] = None
    price_display_mode: str = "show_price"
    pricing_snapshot_id: Optional[str] = None
    manual_price_cents: Optional[int] = None
    selected_price_source: str = "manual"
    quote_line_item_id: Optional[str] = None
    order_item_id: Optional[str] = None
    proof_id: Optional[str] = None
    file_ids: list[str] = Field(default_factory=list)
    visual_markup_id: Optional[str] = None
    rendered_preview_file_id: Optional[str] = None
    thumbnail_file_id: Optional[str] = None
    internal_notes: Optional[str] = None
    customer_safe_notes: Optional[str] = None


class DecisionOptionUpdateIn(BaseModel):
    internal_name: Optional[str] = None
    customer_label: Optional[str] = None
    badge_type: Optional[str] = None
    custom_badge_text: Optional[str] = None
    headline: Optional[str] = None
    customer_safe_description: Optional[str] = None
    included_features: Optional[list[str]] = None
    excluded_features: Optional[list[str]] = None
    expected_timing: Optional[str] = None
    price_display_mode: Optional[str] = None
    pricing_snapshot_id: Optional[str] = None
    manual_price_cents: Optional[int] = None
    selected_price_source: Optional[str] = None
    quote_line_item_id: Optional[str] = None
    order_item_id: Optional[str] = None
    proof_id: Optional[str] = None
    file_ids: Optional[list[str]] = None
    visual_markup_id: Optional[str] = None
    rendered_preview_file_id: Optional[str] = None
    thumbnail_file_id: Optional[str] = None
    internal_notes: Optional[str] = None
    customer_safe_notes: Optional[str] = None
    active: Optional[bool] = None


class ReorderIn(BaseModel):
    option_ids: list[str]


class AttachMediaIn(BaseModel):
    file_ids: Optional[list[str]] = None
    proof_id: Optional[str] = None
    visual_markup_id: Optional[str] = None
    rendered_preview_file_id: Optional[str] = None
    thumbnail_file_id: Optional[str] = None


class DetachMediaIn(BaseModel):
    field_names: list[str]


class AttachPricingSnapshotIn(BaseModel):
    pricing_snapshot_id: str


class TransitionIn(BaseModel):
    target: str


class ShareMintIn(BaseModel):
    audience_email: Optional[str] = None
    ttl_hours: int = 168
    single_use: bool = False


class DecisionApplyIn(BaseModel):
    note: Optional[str] = None


@router.post("", status_code=201)
async def create_room(payload: DecisionRoomCreateIn, user: dict = Depends(require_permission(Perm.DECISION_ROOM_WRITE))) -> dict:
    try:
        return await svc.create_room(tenant_id=user["tenant_id"], payload=payload.model_dump(), actor_user_id=user["id"], actor_email=user["email"])
    except DecisionRoomError as ex:
        _raise(ex)


@router.get("")
async def list_rooms(
    status: Optional[list[str]] = Query(None), customer_id: Optional[str] = Query(None),
    quote_id: Optional[str] = Query(None), order_id: Optional[str] = Query(None),
    intake_id: Optional[str] = Query(None), user: dict = Depends(require_permission(Perm.DECISION_ROOM_READ)),
) -> dict:
    items = await svc.list_rooms(
        tenant_id=user["tenant_id"], status=status, customer_id=customer_id,
        quote_id=quote_id, order_id=order_id, intake_id=intake_id,
    )
    return {"items": items}


@router.get("/{room_id}")
async def get_room(room_id: str, user: dict = Depends(require_permission(Perm.DECISION_ROOM_READ))) -> dict:
    try:
        return await svc.get_room(tenant_id=user["tenant_id"], room_id=room_id)
    except DecisionRoomError as ex:
        _raise(ex)


@router.patch("/{room_id}")
async def update_room(room_id: str, payload: DecisionRoomUpdateIn, user: dict = Depends(require_permission(Perm.DECISION_ROOM_WRITE))) -> dict:
    try:
        return await svc.update_room(
            tenant_id=user["tenant_id"], room_id=room_id, changes=payload.model_dump(exclude_unset=True),
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except DecisionRoomError as ex:
        _raise(ex)


@router.get("/{room_id}/readiness")
async def readiness(room_id: str, user: dict = Depends(require_permission(Perm.DECISION_ROOM_READ))) -> dict:
    try:
        return await svc.readiness_report(tenant_id=user["tenant_id"], room_id=room_id)
    except DecisionRoomError as ex:
        _raise(ex)


@router.get("/{room_id}/preview")
async def preview(room_id: str, user: dict = Depends(require_permission(Perm.DECISION_ROOM_READ))) -> dict:
    try:
        return await svc.internal_preview(tenant_id=user["tenant_id"], room_id=room_id)
    except DecisionRoomError as ex:
        _raise(ex)


@router.post("/{room_id}/options", status_code=201)
async def add_option(room_id: str, payload: DecisionOptionIn, user: dict = Depends(require_permission(Perm.DECISION_ROOM_WRITE))) -> dict:
    try:
        return await svc.add_option(
            tenant_id=user["tenant_id"], room_id=room_id, option_in=payload.model_dump(),
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except DecisionRoomError as ex:
        _raise(ex)


@router.patch("/{room_id}/options/reorder")
async def reorder_options(room_id: str, payload: ReorderIn, user: dict = Depends(require_permission(Perm.DECISION_ROOM_WRITE))) -> dict:
    try:
        return await svc.reorder_options(
            tenant_id=user["tenant_id"], room_id=room_id, ordered_option_ids=payload.option_ids,
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except DecisionRoomError as ex:
        _raise(ex)


@router.patch("/{room_id}/options/{option_id}")
async def update_option(
    room_id: str, option_id: str, payload: DecisionOptionUpdateIn, user: dict = Depends(require_permission(Perm.DECISION_ROOM_WRITE)),
) -> dict:
    try:
        return await svc.update_option(
            tenant_id=user["tenant_id"], room_id=room_id, option_id=option_id,
            changes=payload.model_dump(exclude_unset=True), actor_user_id=user["id"], actor_email=user["email"],
        )
    except DecisionRoomError as ex:
        _raise(ex)


@router.post("/{room_id}/options/{option_id}/duplicate", status_code=201)
async def duplicate_option(room_id: str, option_id: str, user: dict = Depends(require_permission(Perm.DECISION_ROOM_WRITE))) -> dict:
    try:
        return await svc.duplicate_option(
            tenant_id=user["tenant_id"], room_id=room_id, option_id=option_id,
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except DecisionRoomError as ex:
        _raise(ex)


@router.post("/{room_id}/options/{option_id}/archive")
async def archive_option(room_id: str, option_id: str, user: dict = Depends(require_permission(Perm.DECISION_ROOM_WRITE))) -> dict:
    try:
        return await svc.archive_option(
            tenant_id=user["tenant_id"], room_id=room_id, option_id=option_id,
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except DecisionRoomError as ex:
        _raise(ex)


@router.post("/{room_id}/options/{option_id}/restore")
async def restore_option(room_id: str, option_id: str, user: dict = Depends(require_permission(Perm.DECISION_ROOM_WRITE))) -> dict:
    try:
        return await svc.restore_option(
            tenant_id=user["tenant_id"], room_id=room_id, option_id=option_id,
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except DecisionRoomError as ex:
        _raise(ex)


@router.post("/{room_id}/options/{option_id}/media/attach")
async def attach_media(
    room_id: str, option_id: str, payload: AttachMediaIn, user: dict = Depends(require_permission(Perm.DECISION_ROOM_WRITE)),
) -> dict:
    try:
        return await svc.attach_media(
            tenant_id=user["tenant_id"], room_id=room_id, option_id=option_id,
            fields=payload.model_dump(exclude_unset=True), actor_user_id=user["id"], actor_email=user["email"],
        )
    except DecisionRoomError as ex:
        _raise(ex)


@router.post("/{room_id}/options/{option_id}/media/detach")
async def detach_media(
    room_id: str, option_id: str, payload: DetachMediaIn, user: dict = Depends(require_permission(Perm.DECISION_ROOM_WRITE)),
) -> dict:
    try:
        return await svc.detach_media(
            tenant_id=user["tenant_id"], room_id=room_id, option_id=option_id,
            field_names=payload.field_names, actor_user_id=user["id"], actor_email=user["email"],
        )
    except DecisionRoomError as ex:
        _raise(ex)


@router.post("/{room_id}/options/{option_id}/pricing-snapshot/attach")
async def attach_pricing_snapshot(
    room_id: str, option_id: str, payload: AttachPricingSnapshotIn, user: dict = Depends(require_permission(Perm.DECISION_ROOM_WRITE)),
) -> dict:
    try:
        return await svc.attach_pricing_snapshot(
            tenant_id=user["tenant_id"], room_id=room_id, option_id=option_id,
            pricing_snapshot_id=payload.pricing_snapshot_id, actor_user_id=user["id"], actor_email=user["email"],
        )
    except DecisionRoomError as ex:
        _raise(ex)


@router.post("/{room_id}/options/{option_id}/pricing-snapshot/detach")
async def detach_pricing_snapshot(
    room_id: str, option_id: str, user: dict = Depends(require_permission(Perm.DECISION_ROOM_WRITE)),
) -> dict:
    try:
        return await svc.detach_pricing_snapshot(
            tenant_id=user["tenant_id"], room_id=room_id, option_id=option_id,
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except DecisionRoomError as ex:
        _raise(ex)


@router.post("/{room_id}/transition")
async def transition(room_id: str, payload: TransitionIn, user: dict = Depends(require_permission(Perm.DECISION_ROOM_WRITE))) -> dict:
    # "archived" is gated behind the separate archive permission even though
    # this endpoint's baseline dependency is `decision_room:write` — mirrors
    # the dedicated `/{room_id}/archive` route's permission.
    if payload.target == "archived" and Perm.DECISION_ROOM_ARCHIVE.value not in set(permissions_for_role(user.get("role", "staff"))):
        raise HTTPException(status_code=403, detail=f"Missing permission: {Perm.DECISION_ROOM_ARCHIVE.value}")
    try:
        return await svc.transition(
            tenant_id=user["tenant_id"], room_id=room_id, target=payload.target,
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except DecisionRoomError as ex:
        _raise(ex)


@router.post("/{room_id}/publish")
async def publish(room_id: str, user: dict = Depends(require_permission(Perm.DECISION_ROOM_PUBLISH))) -> dict:
    try:
        return await svc.publish_room(tenant_id=user["tenant_id"], room_id=room_id, actor_user_id=user["id"], actor_email=user["email"])
    except DecisionRoomError as ex:
        _raise(ex)


@router.get("/{room_id}/versions")
async def list_versions(room_id: str, user: dict = Depends(require_permission(Perm.DECISION_ROOM_READ))) -> dict:
    try:
        return {"items": await svc.list_versions(tenant_id=user["tenant_id"], room_id=room_id)}
    except DecisionRoomError as ex:
        _raise(ex)


@router.get("/{room_id}/versions/{version_id}")
async def get_version(room_id: str, version_id: str, user: dict = Depends(require_permission(Perm.DECISION_ROOM_READ))) -> dict:
    try:
        return await svc.get_version(tenant_id=user["tenant_id"], room_id=room_id, version_id=version_id)
    except DecisionRoomError as ex:
        _raise(ex)


@router.post("/{room_id}/archive")
async def archive_room(room_id: str, user: dict = Depends(require_permission(Perm.DECISION_ROOM_ARCHIVE))) -> dict:
    try:
        return await svc.archive_room(tenant_id=user["tenant_id"], room_id=room_id, actor_user_id=user["id"], actor_email=user["email"])
    except DecisionRoomError as ex:
        _raise(ex)


@router.post("/{room_id}/restore")
async def restore_room(room_id: str, user: dict = Depends(require_permission(Perm.DECISION_ROOM_ARCHIVE))) -> dict:
    try:
        return await svc.restore_room(tenant_id=user["tenant_id"], room_id=room_id, actor_user_id=user["id"], actor_email=user["email"])
    except DecisionRoomError as ex:
        _raise(ex)


# ---- EC10 Phase 10E-1 — mint/revoke a customer-facing share link ---------
# The room itself must exist in-tenant, but is intentionally NOT required to
# already be "published"/"ready" here — staff may prepare a link ahead of
# time; `get_customer_view()` (Phase 10E-1) independently re-checks the
# room's actual accessible status on every resolution, so an unpublished
# room's link simply 404s until the room is actually published.
@router.post("/{room_id}/share", status_code=201)
async def mint_share(room_id: str, payload: ShareMintIn, request: Request, user: dict = Depends(require_permission(Perm.DECISION_ROOM_WRITE))) -> dict:
    try:
        await svc.get_room(tenant_id=user["tenant_id"], room_id=room_id)
    except DecisionRoomError as ex:
        _raise(ex)
    raw, token_doc = await mint_public_action_token(
        tenant_id=user["tenant_id"], action="decision_room_view", parent_type="decision_room", parent_id=room_id,
        audience_email=payload.audience_email, ttl_hours=payload.ttl_hours, single_use=payload.single_use,
        issued_by=user["id"], ip_issued=(request.client.host if request.client else None),
    )
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="decision_room.share_token_mint", entity_type="decision_room", entity_id=room_id,
        summary="Decision Room share token minted", diff={"audience_email": payload.audience_email},
    )
    token_doc.pop("token_hash", None)
    return {"token": raw, "record": serialize_doc(token_doc)}


@router.delete("/share-tokens/{token_id}", status_code=204)
async def revoke_share(token_id: str, user: dict = Depends(require_permission(Perm.DECISION_ROOM_WRITE))):
    await revoke_public_action_token(token_id, user["tenant_id"])
    return Response(status_code=204)


# ---- EC10 Phase 10E-2 — staff-facing, READ-ONLY view of customer decisions
# Staff may view pending/superseded decisions and acknowledge receipt only.
# Accepting a decision, applying it to a Quote/Order Item, or changing
# pricing is explicitly NOT built here — that is Phase 10F.
@router.get("/{room_id}/decisions")
async def list_decisions(room_id: str, user: dict = Depends(require_permission(Perm.DECISION_ROOM_READ))) -> dict:
    try:
        return {"items": await svc.list_customer_decisions(tenant_id=user["tenant_id"], room_id=room_id)}
    except DecisionRoomError as ex:
        _raise(ex)


@router.post("/{room_id}/decisions/{decision_id}/acknowledge")
async def acknowledge_decision(
    room_id: str, decision_id: str, user: dict = Depends(require_permission(Perm.DECISION_ROOM_WRITE)),
) -> dict:
    try:
        return await svc.acknowledge_customer_decision(
            tenant_id=user["tenant_id"], room_id=room_id, decision_id=decision_id,
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except DecisionRoomError as ex:
        _raise(ex)


# ---- EC10 Phase 10E-3 — staff-facing questions/overlays -------------------
# Staff may view every question/overlay and respond/resolve QUESTIONS ONLY.
# Overlays remain customer-owned history — staff never edits/withdraws them.

class StaffQuestionResponseIn(BaseModel):
    staff_response: str


@router.get("/{room_id}/questions")
async def list_questions(room_id: str, user: dict = Depends(require_permission(Perm.DECISION_ROOM_READ))) -> dict:
    try:
        return {"items": await svc.list_customer_questions(tenant_id=user["tenant_id"], room_id=room_id)}
    except DecisionRoomError as ex:
        _raise(ex)


@router.post("/{room_id}/questions/{question_id}/respond")
async def respond_question(
    room_id: str, question_id: str, payload: StaffQuestionResponseIn,
    user: dict = Depends(require_permission(Perm.DECISION_ROOM_WRITE)),
) -> dict:
    try:
        return await svc.respond_to_question(
            tenant_id=user["tenant_id"], room_id=room_id, question_id=question_id,
            staff_response=payload.staff_response, actor_user_id=user["id"], actor_email=user["email"],
        )
    except DecisionRoomError as ex:
        _raise(ex)


@router.post("/{room_id}/questions/{question_id}/resolve")
async def resolve_question_route(
    room_id: str, question_id: str, user: dict = Depends(require_permission(Perm.DECISION_ROOM_WRITE)),
) -> dict:
    try:
        return await svc.resolve_question(
            tenant_id=user["tenant_id"], room_id=room_id, question_id=question_id,
            actor_user_id=user["id"], actor_email=user["email"],
        )
    except DecisionRoomError as ex:
        _raise(ex)


@router.get("/{room_id}/overlays")
async def list_overlays(room_id: str, user: dict = Depends(require_permission(Perm.DECISION_ROOM_READ))) -> dict:
    try:
        return {"items": await svc.list_customer_overlays(tenant_id=user["tenant_id"], room_id=room_id)}
    except DecisionRoomError as ex:
        _raise(ex)
