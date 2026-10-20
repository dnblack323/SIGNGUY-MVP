"""Read-only list of Webstore questionnaires. Editing happens in Form Maker."""
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

