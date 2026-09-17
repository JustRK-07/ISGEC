"""Health check — also confirms LLM provider is loaded."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import __version__
from app.config import get_settings
from app.db import engine
from app.deps import get_db
from app.models.project import Project
from app.services.llm_gemini import gemini_configured
from app.services.llm_ollama import ollama_configured

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    provider = settings.llm_provider
    llm_ready = gemini_configured() if provider == "gemini" else ollama_configured()

    project_count = db.query(Project).count()

    return {
        "ok": True,
        "version": __version__,
        "llm": {"provider": provider, "ready": llm_ready},
        "uptimeSec": 0,
        "dbFile": str(engine.url.database) if engine.url else None,
        "projectCount": project_count,
    }
