"""Webstore orders, payment, refund, and reporting routes."""
from __future__ import annotations

from .webstores_common import *

router = APIRouter(prefix="/webstores", tags=["webstores"])

@router.post("/{webstore_id}/orders/handoff")
async def complete_verified_payment_handoff(
    webstore_id: str,
    payload: VerifiedPaymentHandoffIn,
    user: dict = Depends(require_permission(Perm.WEBSTORE_MANAGE)),
) -> dict:
    try:
        return await webstore_payments.complete_verified_payment_handoff(
            tenant_id=user["tenant_id"],
            webstore_id=webstore_id,
            purchase_intent_id=payload.purchase_intent_id,
            actor_user_id=user["id"],
            actor_email=user["email"],
        )
    except WebstoreError as e:
        _raise(e)


@router.get("/{webstore_id}/orders")
async def webstore_orders(
    webstore_id: str,
    status: Optional[str] = Query(None, min_length=1, max_length=40),
    limit: int = Query(50, ge=1, le=100),
    user: dict = Depends(require_permission(Perm.WEBSTORE_READ)),
) -> dict:
    try:
        return await webstore_orders_svc.list_webstore_orders(
            user,
            webstore_id,
            status=status,
            limit=limit,
        )
    except WebstoreError as e:
        _raise(e)


@router.get("/{webstore_id}/reports")
async def reports(webstore_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await webstore_reports.staff_report(user, webstore_id)
    except WebstoreError as e:
        _raise(e)


@router.post("/{webstore_id}/orders/{order_id}/production-handoff")
async def production_handoff(
    webstore_id: str,
    order_id: str,
    user: dict = Depends(require_permission(Perm.WEBSTORE_MANAGE)),
) -> dict:
    try:
        return await webstore_production.handoff_webstore_order_to_production(user, webstore_id, order_id)
    except WebstoreError as e:
        _raise(e)


@router.get("/{webstore_id}/activity")
async def activity(webstore_id: str, limit: int = Query(30, ge=1, le=100), user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.list_activity(user, webstore_id, limit=limit)
    except WebstoreError as e:
        _raise(e)


@router.get("/{webstore_id}/payment-provider")
async def payment_provider(webstore_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.payment_provider_status(user, webstore_id)
    except WebstoreError as e:
        _raise(e)


@router.post("/{webstore_id}/payment-provider/{action}")
async def payment_provider_action(webstore_id: str, action: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.payment_provider_action(user, webstore_id, action)
    except WebstoreError as e:
        _raise(e)


@router.post("/{webstore_id}/payments/{payment_id}/refund", status_code=201)
async def refund_webstore_payment(
    webstore_id: str,
    payment_id: str,
    payload: WebstoreRefundIn,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user: dict = Depends(get_current_user),
) -> dict:
    try:
        return await svc.refund_webstore_payment(user, webstore_id, payment_id, payload.model_dump(exclude_none=True), idempotency_key)
    except WebstoreError as e:
        _raise(e)
