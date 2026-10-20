"""Webstore request, information packet, questionnaire review and shop fulfillment settings routes."""
from __future__ import annotations

from .webstores_common import *
from ..services import webstore_requests as requests_svc

router = APIRouter(prefix="/webstores", tags=["webstores"])


def _raise_shop(e: "setup_svc.ShopSettingsError") -> None:
    raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.post("/requests", status_code=201)
async def create_request(payload: WebstoreRequestIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await requests_svc.create_webstore_request(user, payload.model_dump())
    except WebstoreError as e:
        _raise(e)
    except WebstoreSetupError as e:
        _raise_setup(e)


@router.get("/setup/customer-matches")
async def customer_matches(
    name: Optional[str] = Query(None), email: Optional[str] = Query(None), phone: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
) -> dict:
    try:
        return await requests_svc.customer_matches(user, name=name, email=email, phone=phone)
    except WebstoreError as e:
        _raise(e)


@router.get("/setup/fulfillment-settings")
async def get_fulfillment_settings(user: dict = Depends(require_permission(Perm.WEBSTORE_READ))) -> dict:
    return await setup_svc.get_fulfillment_settings(user["tenant_id"])


@router.put("/setup/fulfillment-settings")
async def put_fulfillment_settings(payload: FulfillmentSettingsIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await setup_svc.update_fulfillment_settings(user, payload.model_dump(exclude_none=True))
    except setup_svc.ShopSettingsError as e:
        _raise_shop(e)


@router.get("/{webstore_id}/information-packet")
async def information_packet(webstore_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await setup_svc.packet_preview(user, webstore_id)
    except WebstoreSetupError as e:
        _raise_setup(e)


@router.post("/{webstore_id}/information-packet/send")
async def send_information_packet(webstore_id: str, payload: PacketSendIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await setup_svc.send_information_packet(user, webstore_id, resend=payload.resend)
    except WebstoreSetupError as e:
        _raise_setup(e)


@router.get("/{webstore_id}/questionnaire/review")
async def questionnaire_review(webstore_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await setup_svc.questionnaire_review(user, webstore_id)
    except WebstoreSetupError as e:
        _raise_setup(e)


@router.post("/{webstore_id}/questionnaire/{submission_id}/approve")
async def approve_questionnaire(webstore_id: str, submission_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await setup_svc.approve_and_apply(user, webstore_id, submission_id)
    except WebstoreSetupError as e:
        _raise_setup(e)
