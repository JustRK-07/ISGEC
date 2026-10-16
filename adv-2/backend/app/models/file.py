"""File ORM model — port of `files` table from lib/db.js."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.project import Project


class File(Base):
    __tablename__ = "files"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # 'str' | 'mech' | 'extra'
    discipline: Mapped[str] = mapped_column(String, nullable=False)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    # 'dwg' | 'dxf' | 'ifc' | 'pdf'
    format: Mapped[str] = mapped_column(String, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String, nullable=False)
    stored_path: Mapped[str] = mapped_column(String, nullable=False)
    parse_meta: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 'pending' | 'ok' | 'partial' | 'failed' | 'skipped'
    parse_status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    project: Mapped["Project"] = relationship("Project", back_populates="files")
