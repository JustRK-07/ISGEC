"""Issue Pydantic schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class IssueOut(BaseModel):
    """Shape returned by GET /api/projects/{id} (issue row)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    severity: Literal["high", "medium", "low", "pass"]
    category: str
    code: str
    title: str
    evidence: str | None
    sheet: str | None
    grid: str | None
    mech_ref: str | None
    str_ref: str | None
    formula: str | None
    result: Any | None = None
    state: str = "open"
    assigned: str | None = None
    created_at: int


class IssuePatch(BaseModel):
    """Body for PATCH /api/issues/{id}."""

    state: Literal["open", "resolved", "dismissed"] | None = None
    assigned: str | None = None
