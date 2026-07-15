"""EC10 Phase 10D — Customer Decision Room router.

Staff-only. No customer-facing or public route exists here — see the module
docstring on `services/decision_room_service.py` for the full scope boundary.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..core.permissions import Perm, permissions_for_role
from ..deps import require_permission
from ..services import decision_room_service as svc
from ..services.decision_room_service import DecisionRoomError

router = APIRouter(prefix="/decision-rooms", tags=["decision-rooms"])

_ERROR_STATUS = {
    "customer_not_found": 404, "intake_not_found": 404, "quote_not_found": 404,
    "order_not_found": 404, "order_item_not_found": 404, "quote_line_item_not_found": 404,
    "file_not_found": 404, "proof_not_found": 404, "visual_markup_not_found": 404,
    "pricing_snapshot_not_found": 404, "room_not_found": 404, "option_not_found": 404,
    "version_not_found": 404,
    "title_required": 400, "room_locked": 400, "invalid_transition": 400, "readiness_failed": 400,
    "invalid_badge_type": 400, "invalid_price_display_mode": 400, "reorder_mismatch": 400,
    "order_item_order_mismatch": 400,
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
