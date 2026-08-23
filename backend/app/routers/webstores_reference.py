"""Owner and product-template reference routes."""
from __future__ import annotations

from .webstores_common import *

router = APIRouter(prefix="/webstores", tags=["webstores"])

@router.get("/owners/list")
async def list_owners(user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.list_owners(user)
    except WebstoreError as e:
        _raise(e)


@router.post("/owners", status_code=201)
async def create_owner(payload: OwnerIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_owner(user, payload.model_dump(exclude_none=True))
    except WebstoreError as e:
        _raise(e)


@router.get("/product-templates/list")
async def list_templates(
    active: Optional[bool] = Query(None),
    scope: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
) -> dict:
    try:
        return await svc.list_templates(user, active=active, scope=scope, status=status)
    except WebstoreError as e:
        _raise(e)


@router.post("/product-templates", status_code=201)
async def create_template(payload: TemplateIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_template(user, payload.model_dump(exclude_none=True))
    except WebstoreError as e:
        _raise(e)


@router.patch("/product-templates/{template_id}")
async def update_template(template_id: str, payload: TemplatePatchIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.update_template(user, template_id, payload.model_dump(exclude_unset=True))
    except WebstoreError as e:
        _raise(e)


@router.post("/product-templates/{template_id}/archive")
async def archive_template(template_id: str, payload: LifecycleRevisionIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.archive_template(user, template_id, payload.expected_revision)
    except WebstoreError as e:
        _raise(e)


@router.post("/product-templates/{template_id}/restore")
async def restore_template(template_id: str, payload: LifecycleRevisionIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.restore_template(user, template_id, payload.expected_revision)
    except WebstoreError as e:
        _raise(e)
