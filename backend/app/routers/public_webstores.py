"""EC14 - public Webstore storefront routes."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field

from ..services import webstores as svc
from ..services import webstore_branding as branding_svc
from ..services.webstore_branding import WebstoreBrandingError
from ..services.webstores import WebstoreError

router = APIRouter(prefix="/public/webstores", tags=["public-webstores"])


def _raise(e: WebstoreError) -> None:
    raise HTTPException(status_code=e.status_code, detail=e.detail)


def _raise_branding(e: WebstoreBrandingError) -> None:
    raise HTTPException(status_code=e.status_code, detail=e.detail)


class BuyerLineIn(BaseModel):
    product_id: str
    quantity: int = Field(ge=1)
    variant: dict[str, Any] = Field(default_factory=dict)
    personalization: dict[str, Any] = Field(default_factory=dict)
    fulfillment_method: Optional[str] = None


class CartQuoteIn(BaseModel):
    line_items: list[BuyerLineIn] = Field(default_factory=list)
    donation_cents: int = Field(default=0, ge=0)
    promo_code: Optional[str] = None


class BuyerOrderIn(BaseModel):
    model_config = ConfigDict(extra="allow")

    buyer_name: str
    buyer_email: str
    buyer_phone: Optional[str] = None
    line_items: list[BuyerLineIn] = Field(default_factory=list)
    idempotency_key: Optional[str] = None


@router.get("/{slug}")
async def storefront(slug: str) -> dict:
    try:
        return await svc.public_storefront(slug)
    except WebstoreError as e:
        _raise(e)


@router.get("/{slug}/products/{product_id}")
async def product_detail(slug: str, product_id: str) -> dict:
    try:
        return await svc.public_product_detail(slug, product_id)
    except WebstoreError as e:
        _raise(e)


@router.get("/{slug}/branding-assets/{file_id}")
async def branding_asset(slug: str, file_id: str) -> Response:
    try:
        doc, data, content_type = await branding_svc.public_branding_asset(slug, file_id)
        return Response(
            content=data,
            media_type=content_type,
            headers={"Content-Disposition": f'inline; filename="{doc.get("file_name", "branding-asset")}"'},
        )
    except WebstoreBrandingError as e:
        _raise_branding(e)


@router.get("/{slug}/product-images/{product_id}/{slot}")
async def product_image(slug: str, product_id: str, slot: str) -> Response:
    try:
        doc, data, content_type = await svc.public_product_image(slug, product_id, slot)
        return Response(
            content=data,
            media_type=content_type,
            headers={"Content-Disposition": f'inline; filename="{doc.get("file_name", "product-image")}"'},
        )
    except WebstoreError as e:
        _raise(e)


@router.post("/{slug}/buyer-orders", status_code=201)
async def create_buyer_order(slug: str, payload: BuyerOrderIn) -> dict:
    try:
        return await svc.create_purchase_intent(slug, payload.model_dump(exclude_none=True))
    except WebstoreError as e:
        _raise(e)


@router.post("/{slug}/cart-quote")
async def create_cart_quote(slug: str, payload: CartQuoteIn) -> dict:
    try:
        return await svc.quote_public_cart(slug, payload.model_dump(exclude_none=True))
    except WebstoreError as e:
        _raise(e)


@router.post("/{slug}/purchase-intents", status_code=201)
async def create_purchase_intent(slug: str, payload: BuyerOrderIn) -> dict:
    try:
        return await svc.create_purchase_intent(slug, payload.model_dump(exclude_none=True))
    except WebstoreError as e:
        _raise(e)


@router.get("/{slug}/confirmations/{confirmation_token}")
async def confirmation(slug: str, confirmation_token: str) -> dict:
    try:
        return await svc.public_confirmation(slug, confirmation_token)
    except WebstoreError as e:
        _raise(e)
