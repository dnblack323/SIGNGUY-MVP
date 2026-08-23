"""Questionnaire template management routes."""
from __future__ import annotations

from .webstores_common import *

router = APIRouter(prefix="/webstores", tags=["webstores"])

@router.get("/setup/questionnaire-templates")
async def list_questionnaire_templates(
    store_type: Optional[str] = Query(None),
    active_only: bool = Query(False),
    user: dict = Depends(get_current_user),
) -> dict:
    try:
        return await setup_svc.list_questionnaire_templates(user, store_type=store_type, active_only=active_only)
    except WebstoreSetupError as e:
        _raise_setup(e)


@router.post("/setup/questionnaire-templates", status_code=201)
async def create_questionnaire_template(payload: QuestionnaireTemplateIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await setup_svc.save_questionnaire_template(user, payload.model_dump())
    except WebstoreSetupError as e:
        _raise_setup(e)


@router.patch("/setup/questionnaire-templates/{template_id}")
async def update_questionnaire_template(template_id: str, payload: QuestionnaireTemplateIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await setup_svc.save_questionnaire_template(user, payload.model_dump(exclude_unset=True), template_id=template_id)
    except WebstoreSetupError as e:
        _raise_setup(e)
