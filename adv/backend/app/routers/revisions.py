"""Revision ledger router — POST /api/projects/{id}/revisions.

Per BACKEND_ARCHITECTURE §1 (Layer 0):
- SHA-256 dedupe: same bytes → 409 Conflict, returns existing revision id
- Family chain: same family_id + different sha → next revision letter
- supersedes: previous revision id (or null for the first revision in a family)
"""

from __future__ import annotations

import time
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models.file import File as FileModel
from app.models.project import Project
from app.models.revision import Revision
from app.services import revisions as rev_service
from app.services.events import emit_event
from app.utils.storage import persist_upload

router = APIRouter(prefix="/api/projects", tags=["revisions"])


@router.post("/{project_id}/revisions", status_code=status.HTTP_201_CREATED)
async def upload_revision(
    project_id: str,
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
    uploaded_by: str | None = Form(None),
) -> dict:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    contents = await file.read()
    stored = persist_upload(contents, project_id, "rev", file.filename or "")
    family_id = rev_service.normalize_family_id(file.filename or "")

    # Idempotent — duplicate SHA-256 returns 409 with the existing revision id
    try:
        rev = rev_service.register_revision(
            db,
            family_id=family_id,
            sha256=stored.sha256,
            filename=file.filename or "",
            size_bytes=stored.size_bytes,
            project_id=project_id,
            uploaded_by=uploaded_by,
        )
    except rev_service.DuplicateRevision as e:
        emit_event(
            db,
            project_id,
            "revision.duplicate",
            f"Duplicate revision ignored: {file.filename}.",
            tone="warn",
            payload={"filename": file.filename, "revisionId": e.revision_id},
            dedupe_key=f"revision.duplicate:{stored.sha256}",
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "File already ingested",
                "code": "DUPLICATE_REVISION",
                "revision_id": e.revision_id,
            },
        )

    # Also record the file row (mirror the create_project behaviour)
    db.add(
        FileModel(
            id=str(uuid.uuid4()),
            project_id=project_id,
            discipline="extra",  # revisions are tracked alongside the project's primary files
            filename=file.filename or "",
            format=stored.format,
            size_bytes=stored.size_bytes,
            sha256=stored.sha256,
            stored_path=stored.stored_path,
            parse_status="pending",
        )
    )
    emit_event(
        db,
        project_id,
        "revision.registered",
        f"Revision {rev.revision_letter} registered for {file.filename}.",
        tone="ok",
        payload={"filename": file.filename, "revisionId": rev.id, "letter": rev.revision_letter},
        dedupe_key=f"revision.registered:{rev.id}",
    )
    db.commit()

    return {
        "id": rev.id,
        "family_id": rev.family_id,
        "revision_letter": rev.revision_letter,
        "supersedes": rev.supersedes,
        "sha256": rev.sha256,
        "filename": rev.filename,
        "size_bytes": rev.size_bytes,
        "uploaded_by": rev.uploaded_by,
        "uploaded_at": rev.uploaded_at,
    }


@router.get("/{project_id}/revisions")
def list_revisions(project_id: str, db: Session = Depends(get_db)) -> list[dict]:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    revisions = db.query(Revision).filter(Revision.project_id == project_id).all()
    return [
        {
            "id": r.id,
            "family_id": r.family_id,
            "revision_letter": r.revision_letter,
            "supersedes": r.supersedes,
            "sha256": r.sha256,
            "filename": r.filename,
            "size_bytes": r.size_bytes,
            "uploaded_at": r.uploaded_at,
        }
        for r in revisions
    ]
