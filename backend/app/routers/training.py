"""EC8 phase 8e — Training router (manager-facing): definitions, assignments,
quiz attempts, practical signoff."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..core.permissions import Perm
from ..deps import require_permission
from ..services import training_service
from ..services.training_service import TrainingError

router = APIRouter(prefix="/training", tags=["training"])


def _raise(e: TrainingError):
    raise HTTPException(status_code=e.status_code, detail=e.detail)


class TrainingDefinitionIn(BaseModel):
    title: str
    description: Optional[str] = None
    equipment_id: Optional[str] = None
    training_type: str = "reading"
    required_role: Optional[str] = None
    required_steps: list[dict] = Field(default_factory=list)
    quiz_questions: list[dict] = Field(default_factory=list)
    passing_score: Optional[int] = None
    practical_signoff_required: bool = False
    expiration_interval_days: Optional[int] = None


class TrainingDefinitionUpdateIn(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    equipment_id: Optional[str] = None
    training_type: Optional[str] = None
    required_role: Optional[str] = None
    required_steps: Optional[list[dict]] = None
    quiz_questions: Optional[list[dict]] = None
    passing_score: Optional[int] = None
    practical_signoff_required: Optional[bool] = None
    expiration_interval_days: Optional[int] = None
    active: Optional[bool] = None


@router.get("/definitions")
async def list_definitions(equipment_id: Optional[str] = None, active_only: bool = False,
                            user: dict = Depends(require_permission(Perm.TRAINING_MANAGE))) -> dict:
    return {"items": await training_service.list_training_definitions(tenant_id=user["tenant_id"], equipment_id=equipment_id, active_only=active_only)}


@router.post("/definitions", status_code=201)
async def create_definition(payload: TrainingDefinitionIn, user: dict = Depends(require_permission(Perm.TRAINING_MANAGE))) -> dict:
    return await training_service.create_training_definition(
        tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"], **payload.model_dump(),
    )


@router.get("/definitions/{definition_id}")
async def get_definition(definition_id: str, user: dict = Depends(require_permission(Perm.TRAINING_MANAGE))) -> dict:
    try:
        defn = await training_service.get_training_definition(tenant_id=user["tenant_id"], training_definition_id=definition_id)
        docs = await training_service.list_documents(tenant_id=user["tenant_id"], training_definition_id=definition_id)
        return {**defn, "documents": docs}
    except TrainingError as e:
        _raise(e)


@router.patch("/definitions/{definition_id}")
async def update_definition(definition_id: str, payload: TrainingDefinitionUpdateIn, user: dict = Depends(require_permission(Perm.TRAINING_MANAGE))) -> dict:
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No updates")
    try:
        return await training_service.update_training_definition(
            tenant_id=user["tenant_id"], training_definition_id=definition_id, actor_user_id=user["id"], actor_email=user["email"], **updates,
        )
    except TrainingError as e:
        _raise(e)


@router.post("/definitions/{definition_id}/archive")
async def archive_definition(definition_id: str, user: dict = Depends(require_permission(Perm.TRAINING_MANAGE))) -> dict:
    try:
        return await training_service.archive_training_definition(tenant_id=user["tenant_id"], training_definition_id=definition_id, actor_user_id=user["id"], actor_email=user["email"])
    except TrainingError as e:
        _raise(e)


class LinkDocumentIn(BaseModel):
    document_id: str
    portal_visible: bool = False


@router.post("/definitions/{definition_id}/documents")
async def link_document(definition_id: str, payload: LinkDocumentIn, user: dict = Depends(require_permission(Perm.TRAINING_MANAGE))) -> dict:
    try:
        return await training_service.link_document(
            tenant_id=user["tenant_id"], training_definition_id=definition_id, document_id=payload.document_id,
            portal_visible=payload.portal_visible, actor_user_id=user["id"],
        )
    except TrainingError as e:
        _raise(e)


# ---- Assignments ----

class AssignIn(BaseModel):
    employee_id: str
    training_definition_id: str
    due_date: Optional[str] = None
    manager_notes: Optional[str] = None
    renewal_of: Optional[str] = None


@router.get("/assignments")
async def list_assignments(employee_id: Optional[str] = None, training_definition_id: Optional[str] = None,
                            equipment_id: Optional[str] = None, status: Optional[str] = None,
                            user: dict = Depends(require_permission(Perm.TRAINING_MANAGE))) -> dict:
    status_in = [status] if status else None
    return {"items": await training_service.list_assignments(
        tenant_id=user["tenant_id"], employee_id=employee_id, training_definition_id=training_definition_id,
        equipment_id=equipment_id, status_in=status_in,
    )}


@router.post("/assignments", status_code=201)
async def assign(payload: AssignIn, user: dict = Depends(require_permission(Perm.TRAINING_MANAGE))) -> dict:
    try:
        return await training_service.assign_training(
            tenant_id=user["tenant_id"], actor_user_id=user["id"], actor_email=user["email"], **payload.model_dump(),
        )
    except TrainingError as e:
        _raise(e)


@router.get("/assignments/{assignment_id}")
async def get_assignment(assignment_id: str, user: dict = Depends(require_permission(Perm.TRAINING_MANAGE))) -> dict:
    try:
        a = await training_service.get_assignment(tenant_id=user["tenant_id"], assignment_id=assignment_id)
        return {
            **a,
            "quiz_attempts": await training_service.list_quiz_attempts(tenant_id=user["tenant_id"], assignment_id=assignment_id),
            "practical_signoffs": await training_service.list_practical_signoffs(tenant_id=user["tenant_id"], assignment_id=assignment_id),
        }
    except TrainingError as e:
        _raise(e)


@router.post("/assignments/{assignment_id}/fail")
async def fail_assignment(assignment_id: str, reason: Optional[str] = None, user: dict = Depends(require_permission(Perm.TRAINING_MANAGE))) -> dict:
    try:
        return await training_service.fail_assignment(tenant_id=user["tenant_id"], assignment_id=assignment_id, actor_user_id=user["id"], actor_email=user["email"], reason=reason)
    except TrainingError as e:
        _raise(e)


@router.post("/assignments/{assignment_id}/cancel")
async def cancel_assignment(assignment_id: str, user: dict = Depends(require_permission(Perm.TRAINING_MANAGE))) -> dict:
    try:
        return await training_service.cancel_assignment(tenant_id=user["tenant_id"], assignment_id=assignment_id, actor_user_id=user["id"], actor_email=user["email"])
    except TrainingError as e:
        _raise(e)


class SignoffIn(BaseModel):
    result: str
    notes: Optional[str] = None
    restrictions: Optional[str] = None
    evidence_document_ids: list[str] = Field(default_factory=list)


@router.post("/assignments/{assignment_id}/signoff")
async def signoff(assignment_id: str, payload: SignoffIn, user: dict = Depends(require_permission(Perm.TRAINING_MANAGE))) -> dict:
    try:
        return await training_service.record_practical_signoff(
            tenant_id=user["tenant_id"], assignment_id=assignment_id, evaluator_user_id=user["id"], actor_email=user["email"],
            result=payload.result, notes=payload.notes, restrictions=payload.restrictions,
            evidence_document_ids=payload.evidence_document_ids,
        )
    except TrainingError as e:
        _raise(e)
