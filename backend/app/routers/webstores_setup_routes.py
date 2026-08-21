"""Webstore setup, assignments, questionnaires, and setup-file routes."""
from __future__ import annotations

from .webstores_common import *

router = APIRouter(prefix="/webstores", tags=["webstores"])

@router.get("/{webstore_id}/setup-progress")
async def setup_progress(webstore_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await setup_svc.setup_progress_for_staff(user, webstore_id)
    except WebstoreSetupError as e:
        _raise_setup(e)


@router.get("/{webstore_id}/assignments")
async def list_assignments(webstore_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await setup_svc.list_assignments(user, webstore_id)
    except WebstoreSetupError as e:
        _raise_setup(e)


@router.post("/{webstore_id}/assignments", status_code=201)
async def create_assignment(webstore_id: str, payload: AssignmentIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await setup_svc.create_assignment(user, webstore_id, payload.model_dump(exclude_none=True), send=payload.send_invitation)
    except WebstoreSetupError as e:
        _raise_setup(e)


@router.post("/{webstore_id}/assignments/{assignment_id}/resend")
async def resend_assignment_invite(webstore_id: str, assignment_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await setup_svc.resend_invitation(user, webstore_id, assignment_id)
    except WebstoreSetupError as e:
        _raise_setup(e)


@router.post("/{webstore_id}/assignments/{assignment_id}/revoke")
async def revoke_assignment(webstore_id: str, assignment_id: str, payload: RevokeAssignmentIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await setup_svc.revoke_assignment(user, webstore_id, assignment_id, payload.reason)
    except WebstoreSetupError as e:
        _raise_setup(e)


@router.post("/{webstore_id}/primary-owner")
async def change_primary_owner(webstore_id: str, payload: PrimaryOwnerIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await setup_svc.change_primary_owner(user, webstore_id, payload.assignment_id, payload.confirm, payload.reason)
    except WebstoreSetupError as e:
        _raise_setup(e)


@router.get("/{webstore_id}/questionnaire")
async def bound_questionnaire(webstore_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await setup_svc.bind_questionnaire_templates(user, webstore_id)
    except WebstoreSetupError as e:
        _raise_setup(e)


@router.post("/{webstore_id}/questionnaire/send")
async def send_questionnaire(webstore_id: str, payload: QuestionnaireSendIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await setup_svc.send_questionnaire_to_owner(user, webstore_id, payload.model_dump(exclude_none=True))
    except WebstoreSetupError as e:
        _raise_setup(e)


@router.get("/{webstore_id}/questionnaire-response")
async def questionnaire_response(webstore_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await setup_svc.latest_questionnaire_response(user, webstore_id)
    except WebstoreSetupError as e:
        _raise_setup(e)


@router.post("/{webstore_id}/questionnaire/{submission_id}/return")
async def return_questionnaire(webstore_id: str, submission_id: str, payload: QuestionnaireReturnIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await setup_svc.return_questionnaire(user, webstore_id, submission_id, payload.reason)
    except WebstoreSetupError as e:
        _raise_setup(e)


@router.post("/{webstore_id}/questionnaire/apply-preview")
async def questionnaire_apply_preview(webstore_id: str, payload: AnswerApplicationIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await setup_svc.answer_application_preview(user, webstore_id, payload.model_dump(exclude_none=True))
    except WebstoreSetupError as e:
        _raise_setup(e)


@router.post("/{webstore_id}/questionnaire/apply")
async def questionnaire_apply(webstore_id: str, payload: AnswerApplicationIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await setup_svc.apply_questionnaire_answers(user, webstore_id, payload.model_dump(exclude_none=True))
    except WebstoreSetupError as e:
        _raise_setup(e)


@router.post("/{webstore_id}/answer-applications/{application_id}/reverse")
async def reverse_answer_application(webstore_id: str, application_id: str, payload: ReverseApplicationIn, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await setup_svc.reverse_answer_application(user, webstore_id, application_id, payload.model_dump(exclude_none=True))
    except WebstoreSetupError as e:
        _raise_setup(e)


@router.get("/{webstore_id}/setup-files")
async def list_setup_files(webstore_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await setup_svc.list_setup_files(user, webstore_id)
    except WebstoreSetupError as e:
        _raise_setup(e)


@router.post("/{webstore_id}/setup-files", status_code=201)
async def upload_setup_file(
    webstore_id: str,
    category: str = Form(...),
    notes: Optional[str] = Form(None),
    replaces_file_id: Optional[str] = Form(None),
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
) -> dict:
    try:
        data = await _read_upload_limited(file)
        return await setup_svc.upload_setup_file(
            user,
            webstore_id,
            filename=file.filename or "upload.bin",
            content_type=file.content_type or "application/octet-stream",
            data=data,
            category=category,
            notes=notes,
            replaces_file_id=replaces_file_id,
        )
    except WebstoreSetupError as e:
        _raise_setup(e)


@router.get("/{webstore_id}/setup-files/{file_id}/download")
async def download_setup_file(webstore_id: str, file_id: str, user: dict = Depends(get_current_user)) -> Response:
    try:
        doc, data, content_type = await setup_svc.download_setup_file(user["tenant_id"], webstore_id, file_id)
        return Response(
            content=data,
            media_type=content_type,
            headers={"Content-Disposition": f'attachment; filename="{doc.get("file_name", "setup-file")}"'},
        )
    except WebstoreSetupError as e:
        _raise_setup(e)


@router.get("/{webstore_id}/setup-files/{file_id}/preview")
async def preview_setup_file(webstore_id: str, file_id: str, user: dict = Depends(get_current_user)) -> Response:
    try:
        doc, data, content_type = await setup_svc.preview_setup_file(user, webstore_id, file_id)
        return Response(
            content=data,
            media_type=content_type,
            headers={"Content-Disposition": f'inline; filename="{doc.get("file_name", "setup-file")}"'},
        )
    except WebstoreSetupError as e:
        _raise_setup(e)
