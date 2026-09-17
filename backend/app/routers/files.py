"""Raw file serving — GET /uploads/{project_id}/{filename}."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.config import get_settings
from app.utils.storage import upload_path

router = APIRouter(prefix="/uploads", tags=["files"])


@router.get("/{project_id}/{filename}")
def get_upload(project_id: str, filename: str) -> FileResponse:
    full_path = upload_path(project_id, filename)
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(full_path)
