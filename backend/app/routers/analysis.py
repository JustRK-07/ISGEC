"""Analysis trigger + status polling."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.deps import get_db
from app.models.project import Project
from app.services import analyze
from app.services.llm_gemini import gemini_configured
from app.services.llm_ollama import ollama_configured

router = APIRouter(prefix="/api/projects", tags=["analysis"])


@router.post("/{project_id}/analyze")
def trigger_analysis(
    project_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> dict:
    settings = get_settings()
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    provider = settings.llm_provider
    llm_ready = (
        gemini_configured() if provider == "gemini" else ollama_configured()
    )
    if not llm_ready:
        return {
            "ok": False,
            "status": "skipped",
            "reason": f"LLM_PROVIDER={provider} not configured",
        }

    background_tasks.add_task(_background_analyze, project_id)
    return {"ok": True, "status": "running"}


@router.get("/{project_id}/analysis")
def get_analysis(project_id: str, db: Session = Depends(get_db)) -> dict:
    if not db.get(Project, project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    state = analyze.get_analysis_state(project_id)
    return {
        "status": state.status,
        "phase": state.phase,
        "llmStatus": state.llm_status,
        "llmError": state.llm_error,
        "summary": state.summary,
        "issueCount": state.issue_count,
        "error": state.error,
        "startedAt": state.started_at,
        "finishedAt": state.finished_at,
    }


def _background_analyze(project_id: str) -> None:
    import asyncio

    from app.db import SessionLocal

    async def _runner() -> None:
        with SessionLocal() as db:
            try:
                await analyze.run_analysis(db, project_id)
            except Exception as exc:  # noqa: BLE001
                print(f"[analyze] {project_id}: {exc}")

    asyncio.run(_runner())
