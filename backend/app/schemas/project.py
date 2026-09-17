"""Project Pydantic schemas — mirror the JSON shapes from server.js."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.file import FileOut
from app.schemas.issue import IssueOut


class ProjectCreate(BaseModel):
    """Multipart form fields parsed alongside the file uploads."""

    label: str | None = None
    rev: str | None = None


class ProjectSummary(BaseModel):
    """Shape returned by GET /api/projects (list)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    label: str
    short_name: str = Field(alias="shortName")
    rev: str | None
    kind: str
    status: Literal["processing", "ready", "error"]
    created_at: int = Field(alias="createdAt")
    last_opened: int = Field(alias="lastOpened")
    summary: dict[str, int] = Field(default_factory=lambda: {"pass": 0, "warn": 0, "fail": 0})


class ProjectOut(BaseModel):
    """Shape returned by POST /api/projects (after upload)."""

    id: str
    label: str
    shortName: str
    rev: str | None
    status: str
    createdAt: int
    lastOpened: int
    files: dict[str, FileSummary | None]


class ProjectDetail(BaseModel):
    """Shape returned by GET /api/projects/{id} (full detail)."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    label: str
    shortName: str = Field(alias="short_name")
    rev: str | None
    kind: str
    status: str
    createdAt: int = Field(alias="created_at")
    lastOpened: int = Field(alias="last_opened")
    files: list[FileOut]
    issues: list[IssueOut]
    entities: dict[str, list[dict]]
    sheets: list[str]
    analysis: dict
    summary: dict[str, int]
