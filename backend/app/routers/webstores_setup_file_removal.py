"""Setup-file removal route kept separate to preserve route ordering."""
from __future__ import annotations

from .webstores_common import *

router = APIRouter(prefix="/webstores", tags=["webstores"])

@router.post("/{webstore_id}/setup-files/{file_id}/remove")
async def remove_setup_file(webstore_id: str, file_id: str, payload: RemoveFileIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await setup_svc.remove_setup_file(user, webstore_id, file_id, payload.reason)
    except WebstoreSetupError as e:
        _raise_setup(e)
