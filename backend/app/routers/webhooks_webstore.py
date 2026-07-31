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
from ..services.webstores import WebstoreError

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
