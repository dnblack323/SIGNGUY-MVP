"""Collection-level Webstore routes."""
from __future__ import annotations

from .webstores_common import *

router = APIRouter(prefix="/webstores", tags=["webstores"])

@router.get("")
async def list_webstores(status: Optional[str] = Query(None), user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.list_webstores(user, status=status)
    except WebstoreError as e:
        _raise(e)


@router.post("", status_code=201)
async def create_webstore(payload: WebstoreIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_webstore(user, payload.model_dump(exclude_none=True))
    except WebstoreError as e:
        _raise(e)
