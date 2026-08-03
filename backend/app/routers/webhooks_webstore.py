"""Dev-only Webstore payment-provider acceptance boundary."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field, StrictInt

from ..core.config import get_settings
from ..services import webstore_payments
from ..services.webstore_payment_provider import (
    VerifiedProviderPayment,
    financial_event_from_provider_result,
    get_webstore_payment_provider,
)
from ..services.webstores import WebstoreError, provider_authority_for_webstore

router = APIRouter(prefix="/webhooks/webstores", tags=["webhooks"])


class WebstoreTestPaymentEventIn(BaseModel):
    tenant_id: str
    purchase_intent_id: str
    provider_event_id: str
    provider_payment_id: str
    amount_cents: StrictInt = Field(ge=0)
    currency: str = "usd"
    provider: str = "local_test_provider"
    raw_event_snapshot: dict[str, Any] = Field(default_factory=dict)


def _signature_secret() -> str:
    settings = get_settings()
    return os.environ.get("WEBSTORE_TEST_WEBHOOK_SECRET") or settings.jwt_secret


def _verify_signature(body: bytes, signature: str | None) -> None:
    if not signature:
        raise HTTPException(status_code=401, detail="Missing Webstore test-provider signature")
    expected = hmac.new(_signature_secret().encode("utf-8"), body, hashlib.sha256).hexdigest()
    received = signature.removeprefix("sha256=").strip()
    if not hmac.compare_digest(expected, received):
        raise HTTPException(status_code=401, detail="Invalid Webstore test-provider signature")


@router.post("/test-provider")
async def test_provider_event(request: Request, x_webstore_test_signature: str | None = Header(None)) -> dict:
    settings = get_settings()
    if not settings.auth_dev_bypass:
        raise HTTPException(status_code=404, detail="Not found")
    body = await request.body()
    _verify_signature(body, x_webstore_test_signature)
    try:
        payload = WebstoreTestPaymentEventIn(**json.loads(body.decode("utf-8")))
        fields = payload.model_dump()
        fields["provider"] = "local_test_provider"
        fields["raw_event_snapshot"] = {**fields.get("raw_event_snapshot", {}), "boundary": "signed_dev_test_provider"}
        return await webstore_payments.process_verified_payment_event(fields)
    except WebstoreError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.post("/stripe")
async def stripe_event(request: Request, stripe_signature: str | None = Header(None, alias="Stripe-Signature")) -> dict:
    """Verify one Stripe event and hold the payment for Stage 8 handoff."""
    body = await request.body()
    provider = get_webstore_payment_provider(get_settings())
    result = provider.verify_webhook_signature_and_parse(payload=body, signature=stripe_signature)
    if not result.ok:
        raise HTTPException(status_code=400, detail=result.message)
    data = dict(result.data or {})
    if data.get("ignored"):
        return {"accepted": True, "ignored": True, "provider_event_id": data.get("provider_event_id")}
    try:
        authority = await provider_authority_for_webstore(str(data["tenant_id"]), str(data["webstore_id"]))
        if data.get("event_kind") in {"payment_failure", "payment_pending"}:
            return await webstore_payments.reconcile_webstore_payment_status_event(
                tenant_id=str(data["tenant_id"]),
                webstore_id=str(data["webstore_id"]),
                provider_result=result,
                provider_authority=authority,
            )
        if data.get("event_kind") == "refund":
            return await webstore_payments.reconcile_webstore_refund_event(
                tenant_id=str(data["tenant_id"]),
                webstore_id=str(data["webstore_id"]),
                provider_result=result,
                provider_authority=authority,
            )
        if data.get("event_kind") == "financial":
            provider_event = financial_event_from_provider_result(result)
            return await webstore_payments.reconcile_webstore_financial_event(
                tenant_id=str(data["tenant_id"]),
                webstore_id=str(data["webstore_id"]),
                provider_event=provider_event,
                provider_authority=authority,
            )
        verified_payment = VerifiedProviderPayment(
            provider=str(data["provider"]),
            provider_mode=str(data["provider_mode"]),
            provider_account_reference=data.get("provider_account_reference"),
            provider_event_id=str(data["provider_event_id"]),
            provider_payment_id=str(data["provider_payment_id"]),
            purchase_intent_id=str(data["purchase_intent_id"]),
            tenant_id=str(data["tenant_id"]),
            webstore_id=str(data["webstore_id"]),
            amount_cents=int(data["amount_cents"]),
            currency=str(data["currency"]),
            raw_event_snapshot=data.get("raw_event_snapshot"),
        )
        return await webstore_payments.process_verified_payment_event(
            verified_payment=verified_payment,
            provider_authority=authority,
            create_downstream_records=False,
        )
    except (KeyError, WebstoreError) as e:
        if isinstance(e, WebstoreError):
            raise HTTPException(status_code=e.status_code, detail=e.detail) from e
        raise HTTPException(status_code=400, detail="Stripe payment event is incomplete") from e
