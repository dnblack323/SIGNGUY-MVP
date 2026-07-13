"""EC9 Phase 9C — Grouped Pricing Setup Quiz router.

Additive setup path alongside the existing detailed CategorySetupWizard
(`/pricing/settings/categories/{id}/wizard/*`). Suggestions are always
provisional and require an explicit apply step naming exactly which
shop_defaults fields to write — nothing is ever auto-applied.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..core.permissions import Perm
from ..core.time_utils import serialize_doc
from ..deps import require_permission
from ..routers.pricing import ShopDefaultsIn
from ..services.audit import record_audit
from ..services.pricing_quiz import (
    apply_quiz_suggestions,
    get_submission,
    list_submissions,
    skip_submission,
    submit_quiz,
)

router = APIRouter(prefix="/pricing/quiz", tags=["pricing"])


class QuizAnswersIn(BaseModel):
    category: str
    job_duration_hours: float = Field(..., gt=0)
    crew_size: int = Field(..., ge=1)
    material_cost_estimate: Optional[float] = Field(None, ge=0)
    customer_charge: float = Field(..., gt=0)
    price_floor: float = Field(..., ge=0)
    includes_design: bool = False
    includes_install: bool = False
    includes_setup: bool = False
    includes_finishing: bool = False
    difficulty: str = "typical"


class QuizApplyIn(BaseModel):
    # Reuses the exact same field names + validated ranges (ge=0, le=..., etc.)
    # as manual Pricing Foundation edits (`PATCH /pricing/settings/shop-defaults`)
    # — the quiz can never write an unknown key, a negative rate, or an
    # out-of-range margin/markup that manual editing wouldn't also allow.
    accepted_shop_defaults: ShopDefaultsIn


@router.post("/submit", status_code=201)
async def post_submit_quiz(payload: QuizAnswersIn, user: dict = Depends(require_permission(Perm.PRICING_WRITE))) -> dict:
    try:
        doc = await submit_quiz(user["tenant_id"], payload.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return serialize_doc(doc)


@router.get("/submissions")
async def get_submissions(status: Optional[str] = None, user: dict = Depends(require_permission(Perm.PRICING_READ))) -> dict:
    items = await list_submissions(user["tenant_id"], status=status)
    return {"items": [serialize_doc(d) for d in items]}


@router.get("/submissions/{submission_id}")
async def get_one_submission(submission_id: str, user: dict = Depends(require_permission(Perm.PRICING_READ))) -> dict:
    doc = await get_submission(user["tenant_id"], submission_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Quiz submission not found")
    return serialize_doc(doc)


@router.post("/submissions/{submission_id}/apply")
async def post_apply_submission(submission_id: str, payload: QuizApplyIn, user: dict = Depends(require_permission(Perm.PRICING_WRITE))) -> dict:
    accepted = payload.accepted_shop_defaults.model_dump(exclude_none=True)
    try:
        doc = await apply_quiz_suggestions(user["tenant_id"], submission_id, accepted, actor_user_id=user["id"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await record_audit(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"],
        action="pricing.quiz.apply", entity_type="pricing_quiz_submission", entity_id=submission_id,
        summary=f"Applied grouped pricing quiz suggestions: {list(accepted.keys())}",
        diff={"applied": accepted},
    )
    return serialize_doc(doc)


@router.post("/submissions/{submission_id}/skip")
async def post_skip_submission(submission_id: str, user: dict = Depends(require_permission(Perm.PRICING_WRITE))) -> dict:
    try:
        doc = await skip_submission(user["tenant_id"], submission_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return serialize_doc(doc)
