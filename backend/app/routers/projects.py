"""Project CRUD + multipart upload."""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.deps import get_db
from app.models.entity import Entity
from app.models.file import File as FileModel
from app.models.issue import Issue
from app.models.project import Project
from app.services import analyze
from app.services.events import _event_to_dict, aggregate_checks, emit_event, list_events
from app.utils.storage import (
    ALLOWED_EXTS,
    persist_upload,
    remove_project_uploads,
)

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _summarize_issues(issues: list[Issue]) -> dict[str, int]:
    summary = {"pass": 0, "warn": 0, "fail": 0}
    for it in issues:
        if it.severity == "high":
            summary["fail"] += 1
        elif it.severity in ("medium", "low"):
            summary["warn"] += 1
        elif it.severity == "pass":
            summary["pass"] += 1
    return summary


def _issue_to_dict(issue: Issue) -> dict:
    return {
        "id": issue.id,
        "severity": issue.severity,
        "category": issue.category,
        "code": issue.code,
        "title": issue.title,
        "evidence": issue.evidence,
        "sheet": issue.sheet,
        "grid": issue.grid,
        "mech_ref": issue.mech_ref,
        "str_ref": issue.str_ref,
        "formula": issue.formula,
        "result": json.loads(issue.result_json) if issue.result_json else None,
        "state": issue.state,
        "assigned": issue.assigned,
        "created_at": issue.created_at,
    }


def _file_to_dict(file: FileModel) -> dict:
    return {
        "id": file.id,
        "discipline": file.discipline,
        "filename": file.filename,
        "format": file.format,
        "sizeBytes": file.size_bytes,
        "sha256": file.sha256,
        "parseStatus": file.parse_status,
        "parseMeta": json.loads(file.parse_meta) if file.parse_meta else None,
    }


@router.get("")
def list_projects(db: Session = Depends(get_db)) -> list[dict]:
    projects = db.query(Project).order_by(Project.last_opened.desc()).all()
    out = []
    for project in projects:
        issues = db.query(Issue).filter(Issue.project_id == project.id).all()
        out.append(
            {
                "id": project.id,
                "label": project.label,
                "shortName": project.short_name,
                "rev": project.rev,
                "kind": project.kind,
                "status": project.status,
                "createdAt": project.created_at,
                "lastOpened": project.last_opened,
                "summary": _summarize_issues(issues),
            }
        )
    return out


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_project(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    str_file: UploadFile = File(..., alias="str"),
    mech_file: UploadFile = File(..., alias="mech"),
    extra_file: UploadFile | None = File(None, alias="extra"),
    label: str | None = Form(None),
    rev: str | None = Form(None),
) -> dict:
    settings = get_settings()

    # Validate extensions
    for upload in (str_file, mech_file, extra_file):
        if upload is None:
            continue
        ext = Path(upload.filename or "").suffix.lower()
        if ext not in ALLOWED_EXTS:
            raise HTTPException(
                status_code=415,
                detail=f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_EXTS)}",
            )

    project_id = str(uuid.uuid4())
    now = int(time.time() * 1000)
    clean_label = (label or "").strip() or f"Untitled · {datetime.utcnow().isoformat(timespec='minutes')}"

    project = Project(
        id=project_id,
        label=clean_label,
        short_name=clean_label,
        rev=(rev or "").strip() or None,
        kind="Str + Mech",
        status="processing",
        created_at=now,
        last_opened=now,
    )
    db.add(project)
    emit_event(
        db,
        project_id,
        "upload.started",
        "Project upload started.",
        dedupe_key=f"upload.started:{project_id}",
        created_at=now,
    )
    db.commit()

    files_meta: dict[str, dict | None] = {"str": None, "mech": None, "extra": None}
    for discipline, upload in (
        ("str", str_file),
        ("mech", mech_file),
        ("extra", extra_file),
    ):
        if upload is None:
            continue
        contents = await upload.read()
        if len(contents) > settings.max_upload_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File '{upload.filename}' exceeds {settings.max_upload_mb} MB cap",
            )
        stored = persist_upload(contents, project_id, discipline, upload.filename or "")
        db.add(
            FileModel(
                id=str(uuid.uuid4()),
                project_id=project_id,
                discipline=discipline,
                filename=upload.filename or "",
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
            f"upload.{discipline}",
            f"Uploaded {discipline.upper()} drawing {upload.filename}.",
            tone="ok",
            payload={"filename": upload.filename, "sizeBytes": stored.size_bytes, "sha256": stored.sha256},
            dedupe_key=f"upload.{discipline}:{stored.sha256}",
        )
        files_meta[discipline] = {
            "id": stored.sha256[:12],
            "filename": upload.filename,
            "format": stored.format,
            "sizeBytes": stored.size_bytes,
            "sha256": stored.sha256,
        }
    emit_event(
        db,
        project_id,
        "upload.complete",
        "Drawing upload completed; analysis queued.",
        tone="ok",
        dedupe_key=f"upload.complete:{project_id}",
    )
    db.commit()

    # Kick off the analyze pipeline. Each request owns its DB session, so we
    # fire-and-forget — the client polls /api/projects/{id}/analysis.
    background_tasks.add_task(_background_run_analysis, project_id)

    return {
        "id": project_id,
        "label": clean_label,
        "shortName": clean_label,
        "rev": project.rev,
        "status": "processing",
        "createdAt": now,
        "lastOpened": now,
        "files": files_meta,
    }


def _background_run_analysis(project_id: str) -> None:
    """Open a fresh DB session for the background task and run analyze."""
    import asyncio

    from app.db import SessionLocal

    async def _runner() -> None:
        with SessionLocal() as db:
            try:
                await analyze.run_analysis(db, project_id)
            except Exception as exc:  # noqa: BLE001
                print(f"[analyze] {project_id}: {exc}")

    asyncio.run(_runner())


@router.get("/{project_id}")
def get_project(project_id: str, db: Session = Depends(get_db)) -> dict:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    files = db.query(FileModel).filter(FileModel.project_id == project_id).all()
    issues = db.query(Issue).filter(Issue.project_id == project_id).all()
    entities = db.query(Entity).filter(Entity.project_id == project_id).all()

    entity_buckets: dict[str, list[dict]] = {"str": [], "mech": []}
    sheets: set[str] = {"0001"}
    for entity in entities:
        meta = json.loads(entity.meta) if entity.meta else None
        entity_buckets.setdefault(entity.discipline, []).append(
            {
                "id": entity.id,
                "discipline": entity.discipline,
                "sheet": entity.sheet,
                "kind": entity.kind,
                "label": entity.label,
                "x_mm": entity.x_mm,
                "y_mm": entity.y_mm,
                "w_mm": entity.w_mm,
                "h_mm": entity.h_mm,
                "rotation": entity.rotation,
                "meta": meta,
            }
        )
        if entity.sheet:
            sheets.add(entity.sheet)

    state = analyze.get_analysis_state(project_id)
    return {
        "id": project.id,
        "label": project.label,
        "shortName": project.short_name,
        "rev": project.rev,
        "kind": project.kind,
        "status": project.status,
        "createdAt": project.created_at,
        "lastOpened": project.last_opened,
        "files": [_file_to_dict(f) for f in files],
        "issues": [_issue_to_dict(i) for i in issues],
        "entities": entity_buckets,
        "sheets": sorted(sheets),
        "analysis": {
            "status": state.status,
            "phase": state.phase,
            "llmStatus": state.llm_status,
            "llmError": state.llm_error,
            "summary": state.summary,
            "issueCount": state.issue_count,
            "error": state.error,
            "startedAt": state.started_at,
            "finishedAt": state.finished_at,
        },
        "checks": aggregate_checks(issues),
        "events": [_event_to_dict(event) for event in list_events(db, project_id)],
        "summary": _summarize_issues(issues),
    }


@router.get("/{project_id}/events")
def get_project_events(project_id: str, limit: int = 200, db: Session = Depends(get_db)) -> list[dict]:
    if not db.get(Project, project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return [_event_to_dict(event) for event in list_events(db, project_id, limit)]


@router.delete("/{project_id}")
def delete_project(project_id: str, db: Session = Depends(get_db)) -> dict:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    remove_project_uploads(project_id)
    db.delete(project)  # cascades to files / issues / entities
    db.commit()
    return {"ok": True}
