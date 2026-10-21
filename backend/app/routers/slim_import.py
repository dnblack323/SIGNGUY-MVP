from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from ..deps import get_current_user
from ..services import slim_import
from ..services.audit import record_audit

router = APIRouter(prefix="/slim-import", tags=["slim-import"])


def _raise(error: slim_import.SlimImportError) -> None:
    raise HTTPException(status_code=error.status_code, detail=error.code)


@router.post("/preview")
async def preview_slim_import(
    file: UploadFile = File(...),
    passphrase: str = Form(...),
    target_tenant_id: str = Form(...),
    user: dict = Depends(get_current_user),
) -> dict:
    content = await file.read()
    try:
        result = await slim_import.preview_import(
            target_tenant_id=target_tenant_id,
            actor=user,
            content=content,
            passphrase=passphrase,
        )
        await record_audit(
            tenant_id=target_tenant_id,
            actor_user_id=user["id"],
            actor_email=user["email"],
            action="slim_import.preview_generated" if result["import_permitted"] else "slim_import.preview_blocked",
            entity_type="tenant",
            entity_id=target_tenant_id,
            summary="SignGuy Slim import preview generated",
            diff={"backup_id": result.get("backup_id"), "blocking_error_count": len(result.get("blocking_errors") or [])},
        )
        return result
    except slim_import.SlimImportError as exc:
        try:
            await record_audit(
                tenant_id=target_tenant_id,
                actor_user_id=user["id"],
                actor_email=user["email"],
                action="slim_import.validation_failed",
                entity_type="tenant",
                entity_id=target_tenant_id,
                summary="SignGuy Slim import validation failed",
                diff={"error": exc.code},
            )
        finally:
            _raise(exc)


@router.post("/confirm")
async def confirm_slim_import(
    file: UploadFile = File(...),
    passphrase: str = Form(...),
    target_tenant_id: str = Form(...),
    confirmation_phrase: str = Form(...),
    import_unassigned: Literal["true", "false"] = Form("false"),
    user: dict = Depends(get_current_user),
) -> dict:
    content = await file.read()
    try:
        return await slim_import.confirm_import(
            target_tenant_id=target_tenant_id,
            actor=user,
            content=content,
            passphrase=passphrase,
            confirmation_phrase=confirmation_phrase,
            import_unassigned=import_unassigned == "true",
        )
    except slim_import.SlimImportError as exc:
        _raise(exc)


@router.get("/runs/{import_run_id}")
async def get_slim_import_report(import_run_id: str, user: dict = Depends(get_current_user)) -> dict:
    try:
        return await slim_import.get_import_report(
            tenant_id=user["tenant_id"],
            import_run_id=import_run_id,
            actor=user,
        )
    except slim_import.SlimImportError as exc:
        _raise(exc)
