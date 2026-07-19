"""EC14 - public Webstore storefront routes."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, StrictInt

from ..services import webstores as svc
from ..services.webstores import WebstoreError

router = APIRouter(prefix="/public/webstores", tags=["public-webstores"])


def _raise(e: WebstoreError) -> None:
    raise HTTPException(status_code=e.status_code, detail=e.detail)


class BuyerLineIn(BaseModel):
    product_id: str
    quantity: int = Field(ge=1)
    variant: dict[str, Any] = Field(default_factory=dict)
    personalization: dict[str, Any] = Field(default_factory=dict)


class BuyerOrderIn(BaseModel):
    buyer_name: str
    buyer_email: str
    buyer_phone: Optional[str] = None
    line_items: list[BuyerLineIn] = Field(default_factory=list)
    donation_cents: StrictInt = Field(default=0, ge=0)
    shipping_cents: StrictInt = Field(default=0, ge=0)
    tax_cents: StrictInt = Field(default=0, ge=0)
    idempotency_key: Optional[str] = None


@router.get("/{slug}")
async def storefront(slug: str) -> dict:
    try:
        return await svc.public_storefront(slug)
    except WebstoreError as e:
        _raise(e)


@router.post("/{slug}/buyer-orders", status_code=201)
async def create_buyer_order(slug: str, payload: BuyerOrderIn) -> dict:
    try:
        return await svc.create_buyer_order(slug, payload.model_dump(exclude_none=True))
    except WebstoreError as e:
        _raise(e)
