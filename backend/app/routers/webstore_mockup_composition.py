"""Staff-only preparation over canonical Webstore files and mockups."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from .webstores_common import APIRouter, Depends, Response, get_current_user, WebstoreError, _raise
from ..services import webstore_mockup_composition as service

router = APIRouter(prefix="/webstores", tags=["webstores"])


class PlacementIn(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def bounded(self):
        if self.x + self.width > 1 or self.y + self.height > 1:
            raise ValueError("Decoration area must stay inside the product image")
        return self


class CompositionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: StrictInt = Field(ge=1)
    blank_file_id: str = Field(min_length=1, max_length=120)
    artwork_file_id: str = Field(min_length=1, max_length=120)
    variant_id: str = Field(min_length=1, max_length=120)
    placement: PlacementIn
    blank_matches_product: Literal[True]


class AcceptedCompositionIn(CompositionIn):
    preview_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    reviewed: Literal[True]
    alt_text: str = Field(min_length=1, max_length=200, pattern=r"\S")


@router.post("/{webstore_id}/products/{product_id}/mockup-composition/preview")
async def preview_composition(webstore_id: str, product_id: str, payload: CompositionIn, user: dict = Depends(get_current_user)):
    try:
        png, _, digest = await service.prepare_composition(user, webstore_id, product_id, payload.model_dump())
        return Response(content=png, media_type="image/png", headers={"Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff", "X-Preview-SHA256": digest,
            "Access-Control-Expose-Headers": "X-Preview-SHA256"})
    except WebstoreError as exc:
        _raise(exc)


@router.post("/{webstore_id}/products/{product_id}/mockup-composition", status_code=201)
async def accept_composition(webstore_id: str, product_id: str, payload: AcceptedCompositionIn, user: dict = Depends(get_current_user)):
    try:
        return await service.save_composition(user, webstore_id, product_id, payload.model_dump())
    except WebstoreError as exc:
        _raise(exc)
