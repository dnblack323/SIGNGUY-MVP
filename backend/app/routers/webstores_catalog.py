"""Product, category, artwork, mockup, and AI catalog routes."""
from __future__ import annotations

from .webstores_common import *

router = APIRouter(prefix="/webstores", tags=["webstores"])

@router.post("/{webstore_id}/products", status_code=201)
async def create_product(webstore_id: str, payload: ProductIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_product(user, webstore_id, payload.model_dump(exclude_none=True, exclude_unset=True))
    except WebstoreError as e:
        _raise(e)


@router.get("/{webstore_id}/products")
async def list_products(
    webstore_id: str,
    status: Optional[str] = Query(None),
    category_id: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
) -> dict:
    try:
        return await svc.list_products(user, webstore_id=webstore_id, status=status, category_id=category_id, q=q)
    except WebstoreError as e:
        _raise(e)


@router.patch("/{webstore_id}/products/reorder")
async def reorder_products(webstore_id: str, payload: ProductReorderIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.reorder_products(user, webstore_id, payload.product_ids)
    except WebstoreError as e:
        _raise(e)


@router.patch("/{webstore_id}/products/{product_id}")
async def update_product(webstore_id: str, product_id: str, payload: ProductPatchIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.update_product(user, webstore_id, product_id, payload.model_dump(exclude_unset=True))
    except WebstoreError as e:
        _raise(e)


@router.post("/{webstore_id}/products/{product_id}/duplicate", status_code=201)
async def duplicate_product(webstore_id: str, product_id: str, payload: ProductDuplicateIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.duplicate_product(user, webstore_id, product_id, payload.model_dump(exclude_none=True))
    except WebstoreError as e:
        _raise(e)


@router.post("/{webstore_id}/products/{product_id}/submit-approval")
async def submit_product_approval(webstore_id: str, product_id: str, payload: ProductApprovalSubmitIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.submit_product_for_approval(user, webstore_id, product_id, payload.model_dump(exclude_none=True))
    except WebstoreError as e:
        _raise(e)


@router.post("/{webstore_id}/products/{product_id}/archive")
async def archive_product(webstore_id: str, product_id: str, payload: LifecycleRevisionIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.archive_product(user, webstore_id, product_id, payload.expected_revision)
    except WebstoreError as e:
        _raise(e)


@router.post("/{webstore_id}/products/{product_id}/restore")
async def restore_product(webstore_id: str, product_id: str, payload: LifecycleRevisionIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.restore_product(user, webstore_id, product_id, payload.expected_revision)
    except WebstoreError as e:
        _raise(e)


@router.get("/{webstore_id}/product-categories")
async def list_categories(webstore_id: str, status: Optional[str] = Query(None), user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.list_categories(user, webstore_id, status=status)
    except WebstoreError as e:
        _raise(e)


@router.post("/{webstore_id}/product-categories", status_code=201)
async def create_category(webstore_id: str, payload: CategoryIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_category(user, webstore_id, payload.model_dump(exclude_none=True))
    except WebstoreError as e:
        _raise(e)


@router.patch("/{webstore_id}/product-categories/{category_id}")
async def update_category(webstore_id: str, category_id: str, payload: CategoryPatchIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.update_category(user, webstore_id, category_id, payload.model_dump(exclude_unset=True))
    except WebstoreError as e:
        _raise(e)


@router.post("/{webstore_id}/product-categories/{category_id}/archive")
async def archive_category(webstore_id: str, category_id: str, payload: LifecycleRevisionIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.archive_category(user, webstore_id, category_id, payload.expected_revision)
    except WebstoreError as e:
        _raise(e)


@router.post("/{webstore_id}/product-categories/{category_id}/restore")
async def restore_category(webstore_id: str, category_id: str, payload: LifecycleRevisionIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.restore_category(user, webstore_id, category_id, payload.expected_revision)
    except WebstoreError as e:
        _raise(e)


@router.post("/{webstore_id}/artwork", status_code=201)
async def create_artwork(webstore_id: str, payload: ArtworkIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_artwork(user, webstore_id, payload.model_dump(exclude_none=True))
    except WebstoreError as e:
        _raise(e)


@router.get("/{webstore_id}/artwork")
async def list_artwork(webstore_id: str, product_id: Optional[str] = Query(None), user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.list_artwork(user, webstore_id, product_id=product_id)
    except WebstoreError as e:
        _raise(e)


@router.post("/{webstore_id}/mockups", status_code=201)
async def create_mockup(webstore_id: str, payload: MockupIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_mockup(user, webstore_id, payload.model_dump(exclude_none=True))
    except WebstoreError as e:
        _raise(e)


@router.post("/{webstore_id}/mockups/{mockup_id}/submit-approval")
async def submit_mockup_approval(webstore_id: str, mockup_id: str, payload: MockupApprovalSubmitIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.submit_mockup_for_approval(user, webstore_id, mockup_id, payload.model_dump(exclude_none=True))
    except WebstoreError as e:
        _raise(e)


@router.get("/{webstore_id}/mockups")
async def list_mockups(webstore_id: str, product_id: Optional[str] = Query(None), user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.list_mockups(user, webstore_id, product_id=product_id)
    except WebstoreError as e:
        _raise(e)


@router.post("/{webstore_id}/ai-contracts", status_code=201)
async def create_ai_contract(webstore_id: str, payload: AIContractIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.create_ai_usage_event(user, webstore_id, payload.model_dump(exclude_none=True))
    except WebstoreError as e:
        _raise(e)


@router.post("/{webstore_id}/products/{product_id}/ai-actions/preview")
async def preview_product_ai_action(webstore_id: str, product_id: str, payload: ProductAIActionPreviewIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.preview_product_ai_action(user, webstore_id, product_id, payload.action)
    except WebstoreError as e:
        _raise(e)


@router.post("/{webstore_id}/products/{product_id}/ai-actions", status_code=201)
async def run_product_ai_action(webstore_id: str, product_id: str, payload: ProductAIActionRunIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await svc.run_product_ai_action(user, webstore_id, product_id, payload.model_dump(exclude_none=True))
    except WebstoreError as e:
        _raise(e)
