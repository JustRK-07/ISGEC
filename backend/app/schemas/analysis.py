"""AnalysisState Pydantic schema — returned by GET /api/projects/{id}/analysis."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class AnalysisState(BaseModel):
    status: Literal["idle", "running", "done", "error"] = "idle"
    phase: str | None = None
    llmStatus: str | None = None
    llmError: str | None = None
    summary: dict[str, int] | None = None
    issueCount: int | None = None
    error: str | None = None
    startedAt: int | None = None
    finishedAt: int | None = None
