"""File Pydantic schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class FileSummary(BaseModel):
    """Returned in the POST /api/projects response (per-discipline metadata)."""

    id: str
    filename: str
    format: str
    sizeBytes: int
    sha256: str


class FileOut(BaseModel):
    """Returned in the GET /api/projects/{id} response (full file row)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    discipline: Literal["str", "mech", "extra"]
    filename: str
    format: str
    sizeBytes: int = Field(alias="size_bytes")
    sha256: str
    parseStatus: str = Field(alias="parse_status")
    parseMeta: Any | None = Field(default=None, alias="parse_meta")
