"""Launch packet and commerce bridge operation routes."""
from __future__ import annotations

from .webstores_common import *

router = APIRouter(prefix="/webstores", tags=["webstores"])

@router.post("/{webstore_id}/launch-packets", status_code=201)
async def generate_launch_packet(webstore_id: str, payload: LaunchPacketIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.generate_launch_packet(user, webstore_id, payload.model_dump(exclude_none=True))
    except WebstoreError as e:
        _raise(e)


@router.post("/{webstore_id}/launch-packets/{packet_id}/send")
async def send_launch_packet(webstore_id: str, packet_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.send_launch_packet(user, webstore_id, packet_id)
    except WebstoreError as e:
        _raise(e)


@router.post("/{webstore_id}/change-requests/{request_id}")
async def update_change_request(webstore_id: str, request_id: str, payload: ChangeRequestUpdateIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.staff_update_change_request(user, webstore_id, request_id, payload.model_dump(exclude_none=True))
    except WebstoreError as e:
        _raise(e)


@router.post("/buyer-orders/{buyer_order_id}/bridge")
async def bridge_buyer_order(buyer_order_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.bridge_buyer_order_to_order(user, buyer_order_id)
    except WebstoreError as e:
        _raise(e)


@router.post("/ledger/{ledger_entry_id}/platform-fee-reversals", status_code=201)
async def reverse_platform_fee(ledger_entry_id: str, payload: PlatformFeeReversalIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.reverse_platform_fee(user, ledger_entry_id, payload.refund_basis_amount_cents)
    except WebstoreError as e:
        _raise(e)
